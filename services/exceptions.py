# -*- coding: utf-8 -*-
"""Custom exceptions for the application.

This module is the single source of truth for backend error normalization
in Habitat-Desktop. ApiException is raised by services/api_client.py for
every non-2xx HTTP response, and every controller + UI page consumes the
same object. The class exposes parsed properties (title, trace_id,
field_errors) and a humanize() method that returns a safe, translated
user-facing message. No other error-parsing layer should exist.

Backend response shapes we normalize:

  5xx server exception:
    {"status": 500, "title": "...", "message": "FileNotFoundException: ...",
     "errors": {"exception": ["..."]}, "traceId": "..."}

  4xx validation problem:
    {"type": "...", "title": "One or more validation errors occurred.",
     "status": 400, "errors": {"": ["..."], "command": ["..."]},
     "traceId": "..."}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Error-context constants
# ---------------------------------------------------------------------------
# Callers pass one of these to humanize() so the message is anchored to the
# operation the user just tried. Keep the identifiers short — they are used
# only as keys into the fallback translation map.

CTX_GENERIC = "generic"
CTX_NETWORK = "network"
CTX_LOAD_PACKAGE = "load_package"
CTX_LOAD_REPORT = "load_report"
CTX_STAGE = "stage"
CTX_DETECT = "detect"
CTX_APPROVE = "approve"
CTX_COMMIT = "commit"
CTX_RESET_COMMIT = "reset_commit"
CTX_CANCEL = "cancel"
CTX_QUARANTINE = "quarantine"
CTX_LOAD_CONFLICTS = "load_conflicts"
CTX_RESOLVE_CONFLICT = "resolve_conflict"
CTX_LOAD_RECORD = "load_record"

_CTX_FALLBACK_KEY = {
    CTX_LOAD_PACKAGE: "import.error.load_package_failed",
    CTX_LOAD_REPORT: "import.error.load_report_failed",
    CTX_STAGE: "import.error.stage_failed",
    CTX_DETECT: "import.error.detect_failed",
    CTX_APPROVE: "import.error.approve_failed",
    CTX_COMMIT: "import.error.commit_failed",
    CTX_RESET_COMMIT: "import.error.reset_commit_failed",
    CTX_CANCEL: "import.error.cancel_failed",
    CTX_QUARANTINE: "import.error.quarantine_failed",
    CTX_LOAD_CONFLICTS: "duplicates.error.load_conflicts_failed",
    CTX_RESOLVE_CONFLICT: "duplicates.error.resolve_failed",
    CTX_LOAD_RECORD: "comparison.error.record_details_unavailable",
    CTX_GENERIC: "api.error.generic",
    CTX_NETWORK: "api.error.network",
}

# Domain-message substring matchers — when the technical message contains
# one of these keywords (case-insensitive), the user sees the mapped
# translation key instead of a generic HTTP-status message. Earlier entries
# win on first match.
_DOMAIN_MATCHERS: List[tuple] = [
    (("cannot find .uhc", "uhc file", "filenotfoundexception", "uploadedfilepath"),
        "import.error.missing_package_file"),
    # Re-uploading a package: backend has flagged a previous import for the
    # same content. Status code can vary across deployments (409 vs 400 vs
    # custom), so match on the message text to keep behavior stable.
    (("already imported", "package already", "duplicate package", "existing package id"),
        "import.error.duplicate_package"),
]


def _looks_like_stack(text: Optional[str]) -> bool:
    """Heuristic: does this string look like a .NET or Python stack trace?"""
    if not text:
        return False
    s = str(text).lower()
    return (
        "traceback" in s
        or "stack trace" in s
        or "\n   at " in s
        or (" at " in s and ".cs:" in s)
    )


def _flatten_field_errors(errors_obj: Any) -> Dict[str, List[str]]:
    """Normalize the backend `errors` payload to Dict[str, List[str]]."""
    result: Dict[str, List[str]] = {}
    if isinstance(errors_obj, dict):
        for k, v in errors_obj.items():
            if isinstance(v, list):
                result[str(k)] = [str(x) for x in v]
            elif v is not None:
                result[str(k)] = [str(v)]
    elif isinstance(errors_obj, list):
        result[""] = [str(x) for x in errors_obj]
    return result


# ---------------------------------------------------------------------------
# Exception types
# ---------------------------------------------------------------------------


class ApiException(Exception):
    """Raised for every non-2xx backend response.

    Attributes:
      status_code     : HTTP status code (e.g. 400, 500)
      message         : technical message (safe for logs, NEVER for UI)
      response_data   : raw backend JSON (dict)
      context         : operation label set by the controller (see CTX_*)
      endpoint        : HTTP path of the failing request (when available)
      method          : HTTP method of the failing request (when available)

    Derived (parsed on demand):
      title           : response_data["title"]
      trace_id        : response_data["traceId"]
      field_errors    : flattened response_data["errors"]
    """

    def __init__(
        self,
        message: str,
        status_code: int = None,
        response_data: dict = None,
        context: str = CTX_GENERIC,
        endpoint: str = "",
        method: str = "",
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.context = context or CTX_GENERIC
        self.endpoint = endpoint
        self.method = method

    # ----- Parsed properties -------------------------------------------------

    @property
    def title(self) -> str:
        return str(self.response_data.get("title") or "")

    @property
    def trace_id(self) -> str:
        return str(self.response_data.get("traceId") or "")

    @property
    def technical_message(self) -> str:
        """Prefer backend `message`/`detail`; fall back to exc.message."""
        rd = self.response_data or {}
        return str(rd.get("message") or rd.get("detail") or self.message or "")

    @property
    def field_errors(self) -> Dict[str, List[str]]:
        return _flatten_field_errors(self.response_data.get("errors"))

    # ----- Humanization ------------------------------------------------------

    def humanize(self, context: Optional[str] = None) -> str:
        """Return a safe, translated user-facing message.

        Resolution order:
          1. Domain-specific match against the technical message
          2. HTTP 400/422 with field_errors → validation headline +
             bulleted list of the field messages (so the user sees e.g.
             "سبب إعادة التعيين مطلوب لسجل التدقيق")
          3. HTTP status code → generic api.error.* key
          4. Operation context fallback (e.g. import.error.stage_failed)
          5. api.error.generic
        """
        ctx = context or self.context or CTX_GENERIC
        # Lazy import keeps this module importable from places that run
        # before the translation manager is initialised.
        from services.translation_manager import tr

        domain_key = self._match_domain_message()
        if domain_key:
            return tr(domain_key)

        # For validation failures, surface the backend's per-field messages
        # to the user — they're safe (no stack traces) and often explain
        # exactly what to fix ("Reason is required", "Email is invalid", ...).
        if self.status_code in (400, 422) and self.field_errors:
            headline_key = (
                "api.error.validation" if self.status_code == 400
                else "api.error.unprocessable"
            )
            headline = tr(headline_key)
            fields_text = self.field_error_summary(max_lines=6)
            if fields_text:
                return f"{headline}\n{fields_text}"

        status_key = _status_code_to_key(self.status_code or 0)
        msg = tr(status_key)
        if msg and msg != status_key:
            return msg

        ctx_key = _CTX_FALLBACK_KEY.get(ctx, "api.error.generic")
        msg = tr(ctx_key)
        if msg and msg != ctx_key:
            return msg

        return tr("api.error.generic")

    def _match_domain_message(self) -> Optional[str]:
        needle = (self.technical_message or "").lower()
        if not needle:
            return None
        for keywords, key in _DOMAIN_MATCHERS:
            for kw in keywords:
                if kw in needle:
                    return key
        return None

    # ----- Developer helpers -------------------------------------------------

    def log_summary(self) -> str:
        """Compact one-line representation suitable for logger.error()."""
        parts = [f"status={self.status_code}", f"context={self.context}"]
        if self.method or self.endpoint:
            parts.append(f"endpoint={self.method} {self.endpoint}".strip())
        if self.title:
            parts.append(f"title={self.title!r}")
        if self.technical_message:
            parts.append(f"technical={self.technical_message[:300]!r}")
        if self.trace_id:
            parts.append(f"trace_id={self.trace_id}")
        fe = self.field_errors
        if fe:
            parts.append(f"fields={list(fe)}")
        return " ".join(parts)

    def field_error_summary(self, max_lines: int = 4) -> str:
        """Multiline bulleted list of field errors — safe for UI display."""
        fe = self.field_errors
        if not fe:
            return ""
        lines: List[str] = []
        for key, msgs in fe.items():
            label = key if key else "*"
            for m in msgs:
                if _looks_like_stack(m):
                    continue
                lines.append(f"• {label}: {m}")
                if len(lines) >= max_lines:
                    return "\n".join(lines)
        return "\n".join(lines)

    def __str__(self):
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class ValidationException(Exception):
    """Exception raised for local (frontend) validation errors."""

    def __init__(self, message: str, field: str = None,
                 errors: list = None, context: str = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.errors = errors or []
        self.context = context


class PasswordChangeRequiredException(ApiException):
    """Raised when API returns 403 with PasswordChangeRequired."""

    def __init__(self, message: str = "Password change required",
                 response_data: dict = None):
        super().__init__(message=message, status_code=403,
                         response_data=response_data)


class NetworkException(Exception):
    """Raised for connection / timeout errors (no HTTP response)."""

    def __init__(self, message: str, original_error: Exception = None,
                 context: str = CTX_NETWORK):
        super().__init__(message)
        self.message = message
        self.original_error = original_error
        self.context = context or CTX_NETWORK

    def humanize(self, context: Optional[str] = None) -> str:
        """Route network errors through the same humanization path."""
        from services.translation_manager import tr
        return tr("api.error.network")

    def log_summary(self) -> str:
        return f"network_error context={self.context} detail={self.message!r}"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _status_code_to_key(status_code: int) -> str:
    if status_code == 0:
        return "api.error.network"
    if status_code == 401:
        return "api.error.unauthorized"
    if status_code == 403:
        return "api.error.forbidden"
    if status_code == 404:
        return "api.error.not_found"
    if status_code == 409:
        return "api.error.conflict"
    if status_code == 422:
        return "api.error.unprocessable"
    if 400 <= status_code < 500:
        return "api.error.validation"
    if status_code >= 500:
        return "api.error.server"
    return "api.error.generic"


def humanize_exception(exc: BaseException, context: str = CTX_GENERIC) -> str:
    """Uniform user-message helper for any caught exception.

    Controllers and UI code use this to render a safe message regardless of
    whether they caught ApiException, NetworkException, or a generic error.
    """
    if isinstance(exc, (ApiException, NetworkException)):
        return exc.humanize(context)
    from services.translation_manager import tr
    return tr("api.error.generic")


def log_exception(
    exc: BaseException,
    logger,
    context: str = CTX_GENERIC,
    extra: str = "",
):
    """Log the full technical detail of an exception through a project logger.

    Keeps the UI message separate from what developers see in the console /
    log file. Safe for all exception types.
    """
    try:
        if isinstance(exc, ApiException):
            logger.error(f"ApiException[{context}] {exc.log_summary()} {extra}".strip())
        elif isinstance(exc, NetworkException):
            logger.error(f"NetworkException[{context}] {exc.log_summary()} {extra}".strip())
        else:
            logger.error(f"Exception[{context}] {type(exc).__name__}: {exc} {extra}".strip())
    except Exception:
        # Logging must never raise.
        pass
