# -*- coding: utf-8 -*-
"""
Neighborhood Geocoder Service

Provides reverse geocoding: converts coordinates to neighborhood information.

Architecture:
- Uses local JSON file for temporary solution
- Ready for migration to Backend API when available
- Supports both Point and Polygon geometries

Design Patterns:
- Strategy Pattern: LocalProvider vs ApiProvider (future)
- Single Responsibility: Only handles neighborhood geocoding
- Open/Closed: Extensible for new providers without modification
"""

import json
from pathlib import Path
from typing import Optional, Dict, Tuple, List
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
    """
    Reverse geocoding service for neighborhoods.

    Converts geographic coordinates (Point or Polygon) to neighborhood information.
    Currently uses local JSON file, ready for Backend API migration.
    """

    def __init__(self, data_file: Optional[Path] = None):
        """
        Initialize geocoder.

        Args:
            data_file: Path to neighborhoods.json (optional)
        """
        self._neighborhoods = []
        self._data_file = data_file or self._get_default_data_file()
        self._load_neighborhoods()

    def _get_default_data_file(self) -> Path:
        """Get default path to neighborhoods.json."""
        base_path = Path(__file__).parent.parent
        return base_path / "data" / "neighborhoods.json"

    def _load_neighborhoods(self):
        """Load neighborhood polygons from JSON file."""
        try:
            if not self._data_file.exists():
                logger.warning(f"Neighborhoods file not found: {self._data_file}")
                return

            with open(self._data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._neighborhoods = data.get('neighborhoods', [])

            logger.info(f"Loaded {len(self._neighborhoods)} neighborhoods from {self._data_file}")

        except Exception as e:
            logger.error(f"Failed to load neighborhoods: {e}")
            self._neighborhoods = []

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
        try:
            point = self._extract_point_from_wkt(geometry_wkt)
            if not point:
                return None

            lng, lat = point
            return self._find_by_point(lng, lat)

        except Exception as e:
            logger.error(f"Error finding neighborhood: {e}")
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

            centroid = self._calculate_centroid(points)
            return centroid

        else:
            logger.warning(f"Unsupported geometry type: {wkt[:20]}")
            return None

    def _calculate_centroid(self, points: List[Tuple[float, float]]) -> Tuple[float, float]:
        """Calculate centroid of polygon."""
        if not points:
            return None

        lng_sum = sum(p[0] for p in points)
        lat_sum = sum(p[1] for p in points)
        count = len(points)

        return lng_sum / count, lat_sum / count

    def _find_by_point(self, lng: float, lat: float) -> Optional[NeighborhoodInfo]:
        """
        Find neighborhood containing the point.

        Uses ray-casting algorithm for point-in-polygon test.

        Args:
            lng: Longitude
            lat: Latitude

        Returns:
            NeighborhoodInfo if found, None otherwise
        """
        for neighborhood in self._neighborhoods:
            polygon = neighborhood.get('polygon', [])

            if self._point_in_polygon(lng, lat, polygon):
                return NeighborhoodInfo(
                    code=neighborhood['code'],
                    name_en=neighborhood['name_en'],
                    name_ar=neighborhood['name_ar'],
                    confidence=1.0
                )

        logger.debug(f"No neighborhood found for point ({lng}, {lat})")
        return None

    def _point_in_polygon(self, lng: float, lat: float, polygon: List[List[float]]) -> bool:
        """
        Ray-casting algorithm for point-in-polygon test.

        Args:
            lng: Point longitude
            lat: Point latitude
            polygon: List of [lng, lat] coordinates

        Returns:
            True if point is inside polygon
        """
        if not polygon or len(polygon) < 3:
            return False

        n = len(polygon)
        inside = False

        p1_lng, p1_lat = polygon[0]

        for i in range(1, n + 1):
            p2_lng, p2_lat = polygon[i % n]

            if lat > min(p1_lat, p2_lat):
                if lat <= max(p1_lat, p2_lat):
                    if lng <= max(p1_lng, p2_lng):
                        if p1_lat != p2_lat:
                            x_intersection = (lat - p1_lat) * (p2_lng - p1_lng) / (p2_lat - p1_lat) + p1_lng

                        if p1_lng == p2_lng or lng <= x_intersection:
                            inside = not inside

            p1_lng, p1_lat = p2_lng, p2_lat

        return inside

    def get_neighborhood_by_code(self, code: str) -> Optional[NeighborhoodInfo]:
        """
        Get neighborhood information by code.

        Args:
            code: Neighborhood code (e.g., "002")

        Returns:
            NeighborhoodInfo if found, None otherwise
        """
        for neighborhood in self._neighborhoods:
            if neighborhood['code'] == code:
                return NeighborhoodInfo(
                    code=neighborhood['code'],
                    name_en=neighborhood['name_en'],
                    name_ar=neighborhood['name_ar'],
                    confidence=1.0
                )

        return None


class NeighborhoodGeocoderFactory:
    """
    Factory for creating NeighborhoodGeocoder instances.

    Future: Will support ApiProvider when Backend is ready.
    """

    @staticmethod
    def create(provider: str = "local") -> NeighborhoodGeocoder:
        """
        Create geocoder instance.

        Args:
            provider: "local" (current) or "api" (future)

        Returns:
            NeighborhoodGeocoder instance
        """
        if provider == "local":
            return NeighborhoodGeocoder()
        elif provider == "api":
            raise NotImplementedError("API provider not yet implemented")
        else:
            raise ValueError(f"Unknown provider: {provider}")
