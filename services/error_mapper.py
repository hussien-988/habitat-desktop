# -*- coding: utf-8 -*-
"""Centralized error message mapper."""

from services.translation_manager import tr
from services.exceptions import ApiException, ValidationException, NetworkException
from utils.logger import get_logger

logger = get_logger(__name__)


def map_api_error(error: ApiException) -> str:
    """Map API exception to a user-friendly translated message based on HTTP status."""
    status = error.status_code

    if status == 400:
        details = _extract_validation_details(error.response_data)
        if details:
            logger.warning(f"API validation error (400): {details}")
            return tr("error.api.validation", details=details)
        logger.warning(f"API error (400): {error}")
        return tr("error.api.validation", details=str(error))

    if status == 401:
        logger.warning(f"API unauthorized (401): {error}")
        return tr("error.api.unauthorized")

    if status == 403:
        logger.warning(f"API forbidden (403): {error}")
        return tr("error.api.forbidden")

    if status == 404:
        logger.warning(f"API not found (404): {error}")
        return tr("error.api.not_found")

    if status == 409:
        logger.warning(f"API conflict (409): {error}")
        return tr("error.api.conflict")

    if status and status >= 500:
        logger.error(f"API server error ({status}): {error}")
        validation_details = _extract_validation_from_500(error)
        if validation_details:
            return tr("error.api.validation", details=validation_details)
        return tr("error.api.server")

    if status:
        logger.warning(f"API error ({status}): {error}")
        return tr("error.api.unknown")

    logger.warning(f"API error (no status): {error}")
    return tr("error.api.connection")


def map_network_error(error: NetworkException) -> str:
    """Map network exception to user-friendly translated message."""
    msg = str(error.original_error) if error.original_error else ""
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return tr("error.api.timeout")
    return tr("error.api.connection")


def map_exception(error: Exception, context: str = None) -> str:
    """Map any exception to a user-friendly translated message."""
    if isinstance(error, ApiException):
        if not error.context and context:
            error.context = context
        return map_api_error(error)

    if isinstance(error, NetworkException):
        return map_network_error(error)

    if isinstance(error, ValidationException):
        if error.errors:
            details = "\n".join(f"- {e}" for e in error.errors)
            logger.warning(f"Validation error: {error.errors}")
            return tr("error.api.validation", details=details)
        return tr("error.api.unknown")

    logger.warning(f"Unexpected error: {error}")
    return tr("error.api.unknown")


def _extract_validation_from_500(error: ApiException) -> str:
    """Extract validation details from 500 errors caused by backend FluentValidation leaks."""
    import re
    error_text = str(error)
    response_data = getattr(error, 'response_data', {}) or {}

    details = _extract_validation_details(response_data)
    if details:
        return details

    pattern = r'--\s*(\w+):\s*(.+?)(?:\s*Severity:|$)'
    matches = re.findall(pattern, error_text)
    if matches:
        return "\n".join(f"- {field}: {msg.strip()}" for field, msg in matches)

    if 'ValidationException' in error_text and 'Validation failed' in error_text:
        start = error_text.find('Validation failed:')
        if start >= 0:
            msg = error_text[start:start + 200].split('\n')[0]
            return msg

    return ""


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


def build_duplicate_person_message(response_data: dict) -> str:
    """Build Arabic warning message from 409 duplicate national ID response."""
    msg = "يوجد شخص مسجّل مسبقاً بنفس الرقم الوطني."
    conflict = (response_data or {}).get("conflictData", {})
    if conflict:
        first = conflict.get("firstNameArabic", "")
        father = conflict.get("fatherNameArabic", "")
        family = conflict.get("familyNameArabic", "")
        full_name = " ".join(part for part in [first, father, family] if part)
        if full_name:
            msg += f"\nالاسم: {full_name}"
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
                for msg in messages:
                    lines.append(f"- {field}: {msg}")
            else:
                lines.append(f"- {field}: {messages}")
        return "\n".join(lines)

    if isinstance(errors, list):
        return "\n".join(f"- {e}" for e in errors)

    title = response_data.get("title", "")
    if title:
        return title

    return ""
