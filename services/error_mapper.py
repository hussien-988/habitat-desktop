# -*- coding: utf-8 -*-
"""Centralized error message mapper."""

from services.translation_manager import tr
from services.exceptions import ApiException, ValidationException, NetworkException
from utils.logger import get_logger

logger = get_logger(__name__)


def map_api_error(error: ApiException) -> str:
    """Map API exception to user-friendly translated message."""
    status = error.status_code
    context = error.context or ""

    if status == 400:
        details = _extract_validation_details(error.response_data)
        if details:
            return tr("error.api.validation", details=details)
        if context:
            return tr(f"error.{context}.create_failed")
        return tr("validation.check_data")

    if status == 401:
        return tr("error.api.unauthorized")

    if status == 403:
        return tr("error.api.forbidden")

    if status == 404:
        if context:
            return tr(f"error.{context}.not_found")
        return tr("error.api.not_found")

    if status and status >= 500:
        return tr("error.api.server")

    return tr("error.api.unknown")


def map_network_error(error: NetworkException) -> str:
    """Map network exception to user-friendly translated message."""
    msg = str(error.original_error) if error.original_error else ""
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return tr("error.api.timeout")
    return tr("error.api.connection")


def map_exception(error: Exception, context: str = None) -> str:
    """Map any exception to user-friendly translated message."""
    if isinstance(error, ApiException):
        if not error.context and context:
            error.context = context
        return map_api_error(error)

    if isinstance(error, NetworkException):
        return map_network_error(error)

    if isinstance(error, ValidationException):
        if error.errors:
            details = "\n".join(f"• {e}" for e in error.errors)
            return tr("error.api.validation", details=details)
        return error.message

    return tr("error.unexpected")


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
