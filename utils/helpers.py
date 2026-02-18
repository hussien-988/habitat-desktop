# -*- coding: utf-8 -*-
"""
Utility helper functions.
"""

from datetime import datetime, date
from typing import Optional, Union
import locale


def format_date(
    value: Optional[Union[datetime, date, str]],
    format_str: str = "%d/%m/%Y"
) -> str:
    """
    Format a date value for display.

    Args:
        value: Date, datetime, or ISO string
        format_str: Output format string

    Returns:
        Formatted date string or empty string
    """
    if value is None:
        return ""

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value

    if isinstance(value, (datetime, date)):
        return value.strftime(format_str)

    return str(value)


def format_datetime(
    value: Optional[Union[datetime, str]],
    format_str: str = "%d/%m/%Y %H:%M"
) -> str:
    """
    Format a datetime value for display.

    Args:
        value: Datetime or ISO string
        format_str: Output format string

    Returns:
        Formatted datetime string or empty string
    """
    if value is None:
        return ""

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value

    if isinstance(value, datetime):
        return value.strftime(format_str)

    return str(value)


def format_number(value: Optional[Union[int, float]], decimals: int = 0) -> str:
    """
    Format a number with thousands separator.

    Args:
        value: Number to format
        decimals: Decimal places

    Returns:
        Formatted number string
    """
    if value is None:
        return ""

    try:
        if decimals == 0:
            return f"{int(value):,}"
        else:
            return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def format_arabic_number(value: Optional[Union[int, float]]) -> str:
    """
    Format a number using Arabic-Indic numerals.

    Args:
        value: Number to format

    Returns:
        Number string with Arabic-Indic numerals
    """
    if value is None:
        return ""

    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    latin_digits = "0123456789"

    num_str = str(value)
    result = ""

    for char in num_str:
        if char in latin_digits:
            result += arabic_digits[int(char)]
        else:
            result += char

    return result


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename


def parse_building_id(building_id: str) -> dict:
    """
    Parse a 17-digit building ID into components.

    Args:
        building_id: Building ID string (e.g., "01-01-01-001-001-00001")

    Returns:
        Dictionary with parsed components
    """
    parts = building_id.split("-")

    if len(parts) != 6:
        return {"error": "Invalid building ID format"}

    return {
        "governorate_code": parts[0],
        "district_code": parts[1],
        "subdistrict_code": parts[2],
        "community_code": parts[3],
        "neighborhood_code": parts[4],
        "building_number": parts[5],
    }


def generate_building_id(
    governorate: str = "01",
    district: str = "01",
    subdistrict: str = "01",
    community: str = "001",
    neighborhood: str = "001",
    building: str = "00001"
) -> str:
    """
    Generate a building ID from components.

    Returns:
        17-digit building ID string
    """
    return f"{governorate}-{district}-{subdistrict}-{community}-{neighborhood}-{building}"


def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate latitude and longitude values.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        True if valid
    """
    return -90 <= lat <= 90 and -180 <= lon <= 180


def is_aleppo_region(lat: float, lon: float) -> bool:
    """
    Check if coordinates are within Aleppo region bounds.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        True if within Aleppo bounds
    """
    from app.config import Config
    return (Config.MAP_BOUNDS_MIN_LAT <= lat <= Config.MAP_BOUNDS_MAX_LAT and
            Config.MAP_BOUNDS_MIN_LNG <= lon <= Config.MAP_BOUNDS_MAX_LNG)


def build_hierarchical_address(
    building_obj=None,
    unit_obj=None,
    separator: str = " - ",
    include_unit: bool = True
) -> str:
    """
    Build hierarchical address from building and unit objects.

    DRY + SOLID Principle:
    - Single Source of Truth for address formatting
    - Reusable across all components (cards, steps, forms)
    - Consistent format: "حلب - المنطقة - الناحية - الحي - رقم البناء - رقم الوحدة"

    Args:
        building_obj: Building model object with location attributes
        unit_obj: Optional unit model object for unit number
        separator: Separator between address parts (default: " - ")
        include_unit: Whether to include unit number (default: True)

    Returns:
        Formatted hierarchical address string

    Example:
        >>> build_hierarchical_address(building, unit)
        "حلب - مدينة حلب - حلب المركز - الجميلية - 01-01-01-001-001-00001 - 12"
    """
    address_parts = []

    if building_obj:
        # Add governorate (حلب) - code 01
        if hasattr(building_obj, 'governorate_name_ar') and building_obj.governorate_name_ar:
            address_parts.append(building_obj.governorate_name_ar)

        # Add district (المنطقة) - code 01
        if hasattr(building_obj, 'district_name_ar') and building_obj.district_name_ar:
            address_parts.append(building_obj.district_name_ar)

        # Add subdistrict (الناحية) - code 01
        if hasattr(building_obj, 'subdistrict_name_ar') and building_obj.subdistrict_name_ar:
            address_parts.append(building_obj.subdistrict_name_ar)

        # Add neighborhood (الحي) - code 001
        if hasattr(building_obj, 'neighborhood_name_ar') and building_obj.neighborhood_name_ar:
            address_parts.append(building_obj.neighborhood_name_ar)

        # Add building NUMBER only (last 5 digits: 00001) - NOT full building_id
        # Because we converted codes to names, only show the unique building number
        if hasattr(building_obj, 'building_number') and building_obj.building_number:
            address_parts.append(building_obj.building_number)
        elif hasattr(building_obj, 'building_id') and building_obj.building_id:
            # Fallback: extract last 5 digits from building_id
            # building_id format: 17 digits without dashes (01010100200302518)
            bid = building_obj.building_id.replace("-", "")
            building_number = bid[-5:] if len(bid) >= 5 else bid
            address_parts.append(building_number)

    # Add unit number if requested and available (رقم الوحدة)
    if include_unit and unit_obj:
        unit_number = None
        if hasattr(unit_obj, 'unit_number') and unit_obj.unit_number:
            unit_number = unit_obj.unit_number
        elif hasattr(unit_obj, 'apartment_number') and unit_obj.apartment_number:
            unit_number = unit_obj.apartment_number

        if unit_number:
            address_parts.append(str(unit_number))

    # Join with separator or return fallback
    return separator.join(address_parts) if address_parts else "عنوان البناء"
