# -*- coding: utf-8 -*-
"""
Lightweight utility functions for normalizing map data (landmarks, streets).
No heavy dependencies - safe to import from any module.
"""

import re

LANDMARK_TYPE_MAP = {
    1: "Police station",
    2: "Mosque",
    3: "Square",
    4: "Shop",
    5: "School",
    6: "Clinic",
    7: "Water Tank",
    8: "Fuel Station",
    9: "Hospital",
    10: "Park",
}


def normalize_landmark(lm):
    """Ensure landmark has latitude/longitude/typeName fields for Leaflet JS."""
    if "latitude" not in lm and "locationWkt" in lm:
        match = re.match(
            r'POINT\s*\(\s*([\d.+-]+)\s+([\d.+-]+)\s*\)',
            lm["locationWkt"],
            re.IGNORECASE,
        )
        if match:
            lm["longitude"] = float(match.group(1))
            lm["latitude"] = float(match.group(2))
    if "typeName" not in lm and "type" in lm:
        lm["typeName"] = LANDMARK_TYPE_MAP.get(lm["type"], "Unknown")
    return lm


def normalize_street(street):
    """Ensure street has geometryWkt field for Leaflet JS."""
    if "geometryWkt" not in street:
        for key in ("geometry_wkt", "wkt", "lineWkt"):
            if key in street:
                street["geometryWkt"] = street[key]
                break
    return street
