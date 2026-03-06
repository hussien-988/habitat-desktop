# -*- coding: utf-8 -*-
"""
BoundaryService: loads and caches administrative boundary GeoJSON files.

Files are read from assets/geojson/ (produced by tools/convert_shapefiles.py).
Each level is cached in memory after the first read.
"""

import json
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Path resolution: this file is in services/, assets/ is one level up
_ASSETS_DIR = Path(__file__).parent.parent / 'assets' / 'geojson'

_LEVEL_FILES = {
    'country':          'country.geojson',
    'governorates':     'governorates.geojson',
    'districts':        'districts.geojson',
    'subdistricts':     'subdistricts.geojson',
    'neighbourhoods':   'neighbourhoods.geojson',
    'populated_places': 'populated_places.json',
}

_cache: dict = {}
# Separate cache for the parsed places list (list of dicts, not raw JSON string)
_places_list_cache: list = []


def is_available(level: str) -> bool:
    """Return True if the GeoJSON file for the given level exists on disk."""
    filename = _LEVEL_FILES.get(level)
    if not filename:
        return False
    return (_ASSETS_DIR / filename).exists()


def get(level: str) -> Optional[str]:
    """
    Return GeoJSON string for the given administrative level.

    Results are cached after the first disk read.
    Returns None if the level is unknown or the file does not exist.
    """
    if level in _cache:
        return _cache[level]

    filename = _LEVEL_FILES.get(level)
    if not filename:
        logger.warning(f"BoundaryService: unknown level '{level}'")
        return None

    file_path = _ASSETS_DIR / filename
    if not file_path.exists():
        logger.warning(f"BoundaryService: file not found: {file_path}")
        return None

    try:
        text = file_path.read_text(encoding='utf-8')
        _cache[level] = text
        size_kb = file_path.stat().st_size // 1024
        logger.info(f"BoundaryService: loaded '{level}' ({size_kb} KB)")
        return text
    except Exception as e:
        logger.error(f"BoundaryService: failed to read '{level}': {e}")
        return None


def get_feature_count(level: str) -> int:
    """Return number of features in the given level (0 if unavailable)."""
    raw = get(level)
    if not raw:
        return 0
    try:
        return len(json.loads(raw).get('features', []))
    except Exception:
        return 0


def get_places_list(
    admin1_pcode: str = None,
    admin2_pcode: str = None,
    admin3_pcode: str = None,
) -> list:
    """
    Return list of populated place dicts, optionally filtered by admin codes.

    Each dict: {name_ar, name_en, lat, lng, pcode,
                admin1_pcode, admin1_ar, admin2_pcode, admin2_ar,
                admin3_pcode, admin3_ar, is_capital}

    Results are cached after the first disk read.
    Returns [] if the file is unavailable.
    """
    global _places_list_cache

    if not _places_list_cache:
        raw = get('populated_places')
        if not raw:
            return []
        try:
            _places_list_cache = json.loads(raw)
        except Exception as e:
            logger.error(f"BoundaryService: failed to parse populated_places: {e}")
            return []

    places = _places_list_cache
    if admin1_pcode:
        places = [p for p in places if p.get('admin1_pcode') == admin1_pcode]
    if admin2_pcode:
        places = [p for p in places if p.get('admin2_pcode') == admin2_pcode]
    if admin3_pcode:
        places = [p for p in places if p.get('admin3_pcode') == admin3_pcode]
    return places


def get_places_json(admin1_pcode: str = None) -> Optional[str]:
    """
    Return JSON string of populated places (optionally filtered by governorate).

    Suitable for embedding directly in Leaflet HTML.
    Returns None if file is unavailable.
    """
    places = get_places_list(admin1_pcode=admin1_pcode)
    if not places and admin1_pcode is None:
        return None
    return json.dumps(places, ensure_ascii=False, separators=(',', ':'))


def clear_cache():
    """Clear in-memory cache (useful for testing)."""
    global _places_list_cache
    _cache.clear()
    _places_list_cache = []
