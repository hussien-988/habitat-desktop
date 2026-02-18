# -*- coding: utf-8 -*-
"""
DateTime Utilities - أدوات التاريخ والوقت

Centralized datetime handling following DRY and SOLID principles.

Single Responsibility: Handle all datetime conversions and formatting
Open/Closed: Extend with new formats without modifying existing code
Liskov Substitution: All converters return consistent types
Interface Segregation: Small, focused functions
Dependency Inversion: No dependencies on specific implementations
"""

from datetime import datetime, date
from typing import Union, Optional


def to_isoformat(value: Union[datetime, date, str, None]) -> str:
    """
    Convert any datetime-like value to ISO format string.

    This is the single source of truth for datetime serialization.
    Following DRY principle - used across repositories, contexts, and services.

    Args:
        value: datetime, date, ISO string, or None

    Returns:
        ISO format string (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD)

    Examples:
        >>> to_isoformat(datetime(2024, 1, 15, 10, 30))
        '2024-01-15T10:30:00'
        >>> to_isoformat(date(2024, 1, 15))
        '2024-01-15'
        >>> to_isoformat('2024-01-15T10:30:00')
        '2024-01-15T10:30:00'
        >>> to_isoformat(None)
        '2024-01-15T10:30:00'  # Current datetime
    """
    # None -> current datetime
    if value is None:
        return datetime.now().isoformat()

    # Already a string -> validate and return
    if isinstance(value, str):
        # Defensive: validate it's actually ISO format
        try:
            # Try parsing to ensure it's valid
            if 'T' in value:
                datetime.fromisoformat(value)
            else:
                date.fromisoformat(value)
            return value
        except (ValueError, AttributeError):
            # Invalid format, return current datetime
            return datetime.now().isoformat()

    # datetime or date -> convert to ISO
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # Unknown type -> convert to string (defensive)
    return str(value)


def from_isoformat(value: Union[str, datetime, date, None]) -> Optional[datetime]:
    """
    Convert ISO format string to datetime object.

    Reverse of to_isoformat() for deserialization.
    Following DRY principle - used across repositories and contexts.

    Args:
        value: ISO string, datetime, date, or None

    Returns:
        datetime object or None

    Examples:
        >>> from_isoformat('2024-01-15T10:30:00')
        datetime(2024, 1, 15, 10, 30)
        >>> from_isoformat('2024-01-15')
        datetime(2024, 1, 15, 0, 0)
        >>> from_isoformat(None)
        None
    """
    if value is None:
        return None

    # Already datetime -> return as-is
    if isinstance(value, datetime):
        return value

    # date -> convert to datetime
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    # String -> parse ISO format
    if isinstance(value, str):
        try:
            # Try full datetime first
            if 'T' in value:
                return datetime.fromisoformat(value)
            # Then try date-only
            else:
                parsed_date = date.fromisoformat(value)
                return datetime.combine(parsed_date, datetime.min.time())
        except (ValueError, AttributeError):
            return None

    return None


def to_date_isoformat(value: Union[datetime, date, str, None]) -> str:
    """
    Convert any datetime-like value to date-only ISO format (YYYY-MM-DD).

    Used for date fields (survey_date, birth_date, etc.)

    Args:
        value: datetime, date, ISO string, or None

    Returns:
        ISO date string (YYYY-MM-DD)

    Examples:
        >>> to_date_isoformat(datetime(2024, 1, 15, 10, 30))
        '2024-01-15'
        >>> to_date_isoformat(date(2024, 1, 15))
        '2024-01-15'
        >>> to_date_isoformat('2024-01-15')
        '2024-01-15'
    """
    if value is None:
        return datetime.now().date().isoformat()

    if isinstance(value, str):
        # Extract date part if it's a full datetime string
        if 'T' in value:
            value = value.split('T')[0]
        try:
            date.fromisoformat(value)
            return value
        except (ValueError, AttributeError):
            return datetime.now().date().isoformat()

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def now_isoformat() -> str:
    """
    Get current datetime in ISO format.

    Convenience function for consistency.

    Returns:
        Current datetime as ISO string
    """
    return datetime.now().isoformat()


def today_isoformat() -> str:
    """
    Get current date in ISO format.

    Convenience function for consistency.

    Returns:
        Current date as ISO string
    """
    return datetime.now().date().isoformat()
