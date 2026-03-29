# -*- coding: utf-8 -*-
"""
Landmark type icons service.
Fetches SVG icons from API and caches them in memory.
"""

from typing import Dict, Optional, Any
from utils.logger import get_logger

logger = get_logger(__name__)

# Fallback data when API is unavailable
_FALLBACK_TYPES = {
    1: {"typeName": "PoliceStation", "displayNameEnglish": "Police Station",
        "displayNameArabic": "مركز شرطة", "color": "#3B82F6"},
    2: {"typeName": "Mosque", "displayNameEnglish": "Mosque",
        "displayNameArabic": "مسجد", "color": "#10B981"},
    3: {"typeName": "Square", "displayNameEnglish": "Square",
        "displayNameArabic": "ساحة", "color": "#8B5CF6"},
    4: {"typeName": "Shop", "displayNameEnglish": "Shop",
        "displayNameArabic": "محل تجاري", "color": "#F59E0B"},
    5: {"typeName": "School", "displayNameEnglish": "School",
        "displayNameArabic": "مدرسة", "color": "#EF4444"},
    6: {"typeName": "Clinic", "displayNameEnglish": "Clinic",
        "displayNameArabic": "عيادة", "color": "#EC4899"},
    7: {"typeName": "WaterTank", "displayNameEnglish": "Water Tank",
        "displayNameArabic": "خزان مياه", "color": "#06B6D4"},
    8: {"typeName": "FuelStation", "displayNameEnglish": "Fuel Station",
        "displayNameArabic": "محطة وقود", "color": "#F97316"},
    9: {"typeName": "Hospital", "displayNameEnglish": "Hospital",
        "displayNameArabic": "مستشفى", "color": "#DC2626"},
    10: {"typeName": "Park", "displayNameEnglish": "Park",
         "displayNameArabic": "حديقة", "color": "#16A34A"},
}

# In-memory cache: {type_code: {typeName, displayNameArabic, displayNameEnglish, svgContent, ...}}
_cache: Dict[int, Dict[str, Any]] = {}
_loaded = False


def load_landmark_types() -> bool:
    """Fetch landmark types from API and cache them. Returns True on success."""
    global _cache, _loaded

    try:
        from services.api_client import get_api_client
        client = get_api_client()
        items = client.get_landmark_types()

        if items:
            _cache = {}
            for item in items:
                type_code = item.get("type")
                if type_code is not None:
                    _cache[type_code] = item
            _loaded = True
            logger.info(f"Cached {len(_cache)} landmark type icons from API")
            return True

    except Exception as e:
        logger.warning(f"Failed to load landmark types from API: {e}")

    # Fallback to local defaults (no SVG)
    if not _cache:
        _cache = {k: dict(v) for k, v in _FALLBACK_TYPES.items()}
        _loaded = True
        logger.info("Using fallback landmark types (no SVG icons)")

    return False


def reload() -> bool:
    """Force re-fetch landmark types from API (e.g. after login)."""
    global _loaded
    _loaded = False
    return load_landmark_types()


def get_type_info(type_code: int) -> Optional[Dict[str, Any]]:
    """Get cached info for a landmark type code."""
    if not _loaded:
        load_landmark_types()
    return _cache.get(type_code)


def get_svg(type_code: int) -> Optional[str]:
    """Get SVG content for a landmark type. Returns None if unavailable."""
    info = get_type_info(type_code)
    if info:
        return info.get("svgContent")
    return None


def get_display_name(type_code: int, lang: str = "ar") -> str:
    """Get display name for a landmark type in the given language."""
    info = get_type_info(type_code)
    if info:
        if lang == "ar":
            return info.get("displayNameArabic", info.get("typeName", ""))
        return info.get("displayNameEnglish", info.get("typeName", ""))
    return ""


def get_all_types() -> Dict[int, Dict[str, Any]]:
    """Get all cached landmark types."""
    if not _loaded:
        load_landmark_types()
    return dict(_cache)


def get_svg_icons_json() -> str:
    """Get all SVG icons as JSON dict {typeName: svgContent} for Leaflet injection."""
    import json
    if not _loaded:
        load_landmark_types()

    icons = {}
    for type_code, info in _cache.items():
        svg = info.get("svgContent")
        type_name = info.get("typeName", "")
        if svg and type_name:
            icons[type_name] = svg
    return json.dumps(icons, ensure_ascii=False)
