# -*- coding: utf-8 -*-
"""Centralized error message mapper."""

from services.translation_manager import tr
from services.exceptions import ApiException, ValidationException, NetworkException
from utils.logger import get_logger

logger = get_logger(__name__)


def map_api_error(error: ApiException) -> str:
    """Map API exception to a user-friendly translated message.

    Thin delegate around ApiException.humanize() — kept for backward
    compatibility with existing imports. The single source of truth for
    backend-message-vs-translation resolution lives in services/exceptions.py.
    """
    return error.humanize()


def map_network_error(error: NetworkException) -> str:
    """Map network exception to user-friendly translated message."""
    msg = str(error.original_error) if error.original_error else str(error)
    msg_lower = msg.lower()
    if "timeout" in msg_lower or "timed out" in msg_lower:
        return tr("error.api.timeout")
    if "remote end closed" in msg_lower or "connection aborted" in msg_lower or "remotedisconnected" in msg_lower:
        return tr("error.server.dropped")
    return tr("error.api.connection")


def map_exception(error: Exception, context: str = None) -> str:
    """Map any exception to a user-friendly translated message.

    Delegates to humanize_exception (services/exceptions.py) so backend
    `message`/`detail` wins for localized requests, validation field errors
    are surfaced for 400/422, and the existing translation fallbacks apply
    otherwise. Kept as a thin wrapper for callers that still import this name.
    """
    if isinstance(error, ValidationException):
        # Local frontend validation — keep specialized handling.
        if error.errors:
            details = "\n".join(f"- {e}" for e in error.errors)
            logger.warning(f"Validation error: {error.errors}")
            return tr("error.api.validation", details=details)
        return tr("error.api.unknown")

    if isinstance(error, ApiException) and context and not error.context:
        try:
            error.context = context
        except Exception:
            pass

    from services.exceptions import humanize_exception
    return humanize_exception(error, context=context or "generic")


def sanitize_user_message(msg: str) -> str:
    """Sanitize a message before showing it to the user.

    Detects technical patterns (HTTP codes, URLs, exception names, tracebacks)
    and replaces the technical part with a friendly Arabic message,
    keeping any Arabic prefix that was already there.
    """
    import re
    if not msg or not isinstance(msg, str):
        return msg or ""

    _TECHNICAL_PATTERNS = [
        r'\[\d{3}\]\s*\d{3}\s*(Client|Server)\s*Error',
        r'\d{3}\s*(Client|Server)\s*Error:\s*\w+\s+for\s+url:',
        r'https?://\S+',
        r'Traceback\s*\(most\s+recent',
        r'File\s+"[^"]+",\s*line\s+\d+',
        r'\w+Error:\s',
        r'\w+Exception:\s',
        r'ConnectionRefusedError',
        r'TimeoutError',
        r'OSError',
        r'HTTPSConnectionPool',
        r'Max retries exceeded',
        r'errno\s+\d+',
        r'WinError\s+\d+',
        r'socket\.timeout',
        r'requests\.exceptions\.',
        r'at System\.\w+',
        r'\.cs:line\s+\d+',
        r'KeyError',
        r'AttributeError',
        r'TypeError',
        r'ValueError',
    ]

    has_technical = any(re.search(p, msg) for p in _TECHNICAL_PATTERNS)
    if not has_technical:
        return msg

    arabic_prefix_match = re.match(r'^([\u0600-\u06FF\s\u060C\u061B\u061F:\.]+)', msg)
    prefix = ""
    if arabic_prefix_match:
        prefix = arabic_prefix_match.group(1).rstrip(': ').strip()

    fallback = tr("error.api.unknown")
    if re.search(r'timeout|timed?\s*out', msg, re.IGNORECASE):
        fallback = tr("error.api.timeout")
    elif re.search(r'connect|connection|refused|unreachable', msg, re.IGNORECASE):
        fallback = tr("error.api.connection")
    elif re.search(r'401|[Uu]nauthorized', msg):
        fallback = tr("error.api.unauthorized")
    elif re.search(r'403|[Ff]orbidden', msg):
        fallback = tr("error.api.forbidden")
    elif re.search(r'404\s+\w|[Nn]ot\s*[Ff]ound', msg):
        fallback = tr("error.api.not_found")
    elif re.search(r'409|[Cc]onflict', msg):
        fallback = tr("error.api.conflict")
    elif re.search(r'5\d{2}\s*(Server|Internal)', msg, re.IGNORECASE):
        fallback = tr("error.api.server")

    if prefix and len(prefix) > 8:
        return prefix
    return fallback


def is_duplicate_nid_error(exc: Exception) -> bool:
    """Check if exception is a duplicate NationalId error (409 or DB constraint)."""
    from services.exceptions import ApiException
    if not isinstance(exc, ApiException):
        return False
    if exc.status_code == 409:
        return True
    error_str = str(exc.response_data) + exc.message
    return "IX_Person_NationalId" in error_str


def build_duplicate_person_message(response_data: dict) -> str:
    """Build warning message from 409 duplicate response.

    Uses the backend's localized message verbatim. Appends the conflicting
    person's full name from conflictData when present (the backend doesn't
    inline it in the message).
    """
    rd = response_data or {}
    msg = (rd.get("message") or "").strip()
    if not msg:
        msg = (rd.get("detail") or "").strip()
    if not msg:
        msg = tr("error.api.conflict")
    conflict = rd.get("conflictData", {}) or {}
    first = conflict.get("firstNameArabic", "")
    father = conflict.get("fatherNameArabic", "")
    family = conflict.get("familyNameArabic", "")
    full_name = " ".join(part for part in [first, father, family] if part)
    if full_name:
        msg += f"\n{full_name}"
    return msg


def _extract_validation_details(response_data: dict) -> str:
    """Extract validation error details from API response."""
    if not response_data:
        return ""

    errors = response_data.get("errors", {})
    if isinstance(errors, dict):
        lines = []
        for field, messages in errors.items():
            if isinstance(messages, list):
                for msg in messages[:1]:
                    lines.append(f"- {msg}")
            else:
                lines.append(f"- {messages}")
        return "\n".join(lines)

    if isinstance(errors, list):
        return "\n".join(f"- {e}" for e in errors)

    title = response_data.get("title", "")
    if title:
        return title

    return ""
