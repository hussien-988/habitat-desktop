# -*- coding: utf-8 -*-
"""
Neighborhood Geocoder Service — API-only.

Provides reverse geocoding: converts coordinates to neighborhood information
using Backend API.
"""

from typing import Optional, Tuple
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NeighborhoodInfo:
    """Neighborhood information result."""
    code: str
    name_en: str
    name_ar: str
    confidence: float = 1.0


class NeighborhoodGeocoder:
    """Reverse geocoding service for neighborhoods (API-only)."""

    def __init__(self):
        pass

    def find_neighborhood(self, geometry_wkt: str) -> Optional[NeighborhoodInfo]:
        """
        Find neighborhood from WKT geometry (Point or Polygon).

        Args:
            geometry_wkt: WKT format geometry
                         "POINT(37.146 36.199)" or
                         "POLYGON((37.13 36.20, ...))"

        Returns:
            NeighborhoodInfo if found, None otherwise
        """
        point = self._extract_point_from_wkt(geometry_wkt)
        if not point:
            return None

        lng, lat = point

        from services.api_client import get_api_client
        api = get_api_client()
        result = api.get_neighborhood_by_point(lat, lng)
        if result:
            return NeighborhoodInfo(
                code=result.get("neighborhoodCode", ""),
                name_en=result.get("nameEnglish", ""),
                name_ar=result.get("nameArabic", ""),
                confidence=1.0
            )
        return None

    def _extract_point_from_wkt(self, wkt: str) -> Optional[Tuple[float, float]]:
        """
        Extract a point from WKT geometry.

        For POINT: returns the point
        For POLYGON: returns centroid

        Args:
            wkt: WKT geometry string

        Returns:
            (longitude, latitude) or None
        """
        wkt = wkt.strip().upper()

        if wkt.startswith("POINT"):
            coords = wkt.replace("POINT(", "").replace(")", "").strip()
            lng, lat = coords.split()
            return float(lng), float(lat)

        elif wkt.startswith("POLYGON"):
            coords_str = wkt.replace("POLYGON((", "").replace("))", "").strip()
            coord_pairs = coords_str.split(",")

            points = []
            for pair in coord_pairs:
                lng, lat = pair.strip().split()
                points.append((float(lng), float(lat)))

            if not points:
                return None
            avg_lng = sum(p[0] for p in points) / len(points)
            avg_lat = sum(p[1] for p in points) / len(points)
            return avg_lng, avg_lat

        else:
            logger.warning(f"Unsupported geometry type: {wkt[:20]}")
            return None

    def get_neighborhood_by_code(self, code: str) -> Optional[NeighborhoodInfo]:
        """
        Get neighborhood information by code.

        Args:
            code: Neighborhood code (e.g., "002")

        Returns:
            NeighborhoodInfo if found, None otherwise
        """
        from services.api_client import get_api_client
        api = get_api_client()
        neighborhoods = api.get_neighborhoods()
        for n in neighborhoods:
            if n.get("neighborhoodCode") == code:
                return NeighborhoodInfo(
                    code=code,
                    name_en=n.get("nameEnglish", ""),
                    name_ar=n.get("nameArabic", ""),
                    confidence=1.0
                )
        return None
