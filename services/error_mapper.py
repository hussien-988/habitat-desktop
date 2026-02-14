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
