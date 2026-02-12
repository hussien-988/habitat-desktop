# -*- coding: utf-8 -*-
"""Centralized error message mapper."""

from services.translation_manager import tr
from services.exceptions import ApiException, ValidationException, NetworkException
from utils.logger import get_logger

logger = get_logger(__name__)


def map_api_error(error: ApiException) -> str:
    """Map API exception to generic user-friendly message.

    Technical details are logged only - never shown to the user.
    User sees only a generic connection/system error message.
    """
    status = error.status_code

    # Log technical details for debugging (never shown to user)
    if status == 400:
        details = _extract_validation_details(error.response_data)
        if details:
            logger.warning(f"API validation error (400): {details}")
    elif status:
        logger.warning(f"API error ({status}): {error}")

    # Always return generic connection error for user display
    return tr("error.api.connection")


def map_network_error(error: NetworkException) -> str:
    """Map network exception to user-friendly translated message."""
    msg = str(error.original_error) if error.original_error else ""
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return tr("error.api.timeout")
    return tr("error.api.connection")


def map_exception(error: Exception, context: str = None) -> str:
    """Map any exception to generic user-friendly message.

    Technical details are logged only - never shown to the user.
    """
    if isinstance(error, ApiException):
        if not error.context and context:
            error.context = context
        return map_api_error(error)

    if isinstance(error, NetworkException):
        return map_network_error(error)

    if isinstance(error, ValidationException):
        # Log details for debugging
        if error.errors:
            logger.warning(f"Validation error: {error.errors}")
        return tr("error.api.connection")

    # Log unexpected errors
    logger.warning(f"Unexpected error: {error}")
    return tr("error.api.connection")


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
                    lines.append(f"• {field}: {msg}")
            else:
                lines.append(f"• {field}: {messages}")
        return "\n".join(lines)

    if isinstance(errors, list):
        return "\n".join(f"• {e}" for e in errors)

    title = response_data.get("title", "")
    if title:
        return title

    return ""
