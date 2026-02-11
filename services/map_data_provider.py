# -*- coding: utf-8 -*-
"""
Map Data Provider - Strategy Pattern for Map APIs

Provides different implementations for map data retrieval based on use case.
Implements SOLID principles for clean architecture.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MapBounds:
    """Bounding box for map viewport."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


class IMapDataProvider(ABC):
    """
    Interface for map data providers.

    Implements Interface Segregation Principle (SOLID).
    Different providers can implement this interface for different use cases.
    """

    @abstractmethod
    def get_buildings_for_viewport(self, bounds: MapBounds, max_results: int = 2000) -> List[Dict]:
        """Get buildings visible in map viewport."""
        pass

    @abstractmethod
    def get_buildings_in_polygon(self, polygon_wkt: str, filters: Optional[Dict] = None, page_size: int = 1000) -> List[Dict]:
        """Get buildings within a polygon."""
        pass

    @abstractmethod
    def get_neighborhoods_in_viewport(self, bounds: MapBounds) -> List[Dict]:
        """Get neighborhood boundaries in viewport."""
        pass

    @abstractmethod
    def get_neighborhood_by_point(self, lat: float, lng: float) -> Optional[Dict]:
        """Get neighborhood containing a point (reverse geocoding)."""
        pass


class BuildingsMapProvider(IMapDataProvider):
    """
    Provider for general map viewing using Buildings APIs.

    Uses lightweight Buildings/map API for optimal performance.
    Implements Single Responsibility Principle (SOLID).
    """

    def __init__(self, api_client):
        self.api = api_client

    def get_buildings_for_viewport(self, bounds: MapBounds, max_results: int = 2000) -> List[Dict]:
        """Get buildings for viewport using lightweight API."""
        try:
            buildings = self.api.get_buildings_for_map(
                north_east_lat=bounds.max_lat,
                north_east_lng=bounds.max_lng,
                south_west_lat=bounds.min_lat,
                south_west_lng=bounds.min_lng,
                status=None
            )

            # Limit results if needed
            if len(buildings) > max_results:
                logger.warning(f"Truncating {len(buildings)} buildings to {max_results}")
                buildings = buildings[:max_results]

            logger.info(f"Loaded {len(buildings)} buildings for viewport (Buildings/map API)")
            return buildings

        except Exception as e:
            logger.error(f"Error loading buildings for viewport: {e}")
            return []

    def get_buildings_in_polygon(self, polygon_wkt: str, filters: Optional[Dict] = None, page_size: int = 1000) -> List[Dict]:
        """Get buildings in polygon using Buildings/polygon API."""
        try:
            response = self.api.get_buildings_in_polygon(
                polygon_wkt=polygon_wkt,
                building_type=filters.get('building_type') if filters else None,
                status=filters.get('status') if filters else None,
                page_size=page_size
            )

            buildings = response if isinstance(response, list) else response.get("buildings", [])
            logger.info(f"Found {len(buildings)} buildings in polygon (Buildings/polygon API)")
            return buildings

        except Exception as e:
            logger.error(f"Error searching buildings in polygon: {e}")
            return []

    def get_neighborhoods_in_viewport(self, bounds: MapBounds) -> List[Dict]:
        """Get neighborhoods in viewport."""
        try:
            neighborhoods = self.api.get_neighborhoods_by_bounds(
                sw_lat=bounds.min_lat,
                sw_lng=bounds.min_lng,
                ne_lat=bounds.max_lat,
                ne_lng=bounds.max_lng
            )
            logger.info(f"Loaded {len(neighborhoods)} neighborhoods")
            return neighborhoods

        except Exception as e:
            logger.error(f"Error loading neighborhoods: {e}")
            return []

    def get_neighborhood_by_point(self, lat: float, lng: float) -> Optional[Dict]:
        """Get neighborhood by point."""
        return self.api.get_neighborhood_by_point(latitude=lat, longitude=lng)


class FieldAssignmentMapProvider(IMapDataProvider):
    """
    Provider for field assignment workflow.

    Uses BuildingAssignments API with assignment-specific data.
    Implements Single Responsibility Principle (SOLID).
    """

    def __init__(self, api_client):
        self.api = api_client

    def get_buildings_for_viewport(self, bounds: MapBounds, max_results: int = 2000) -> List[Dict]:
        """Get buildings for viewport with assignment data."""
        try:
            polygon_wkt = self._bounds_to_polygon_wkt(bounds)

            result = self.api.search_buildings_for_assignment(
                polygon_wkt=polygon_wkt,
                has_active_assignment=None,
                page_size=max_results
            )

            buildings = result.get("items", []) if isinstance(result, dict) else result
            logger.info(f"Loaded {len(buildings)} buildings for viewport (BuildingAssignments API)")
            return buildings

        except Exception as e:
            logger.error(f"Error loading buildings for viewport: {e}")
            return []

    def get_buildings_in_polygon(self, polygon_wkt: str, filters: Optional[Dict] = None, page_size: int = 1000) -> List[Dict]:
        """Get buildings in polygon with assignment filters."""
        try:
            result = self.api.search_buildings_for_assignment(
                polygon_wkt=polygon_wkt,
                has_active_assignment=filters.get('has_active_assignment') if filters else None,
                survey_status=filters.get('survey_status') if filters else None,
                page_size=page_size
            )

            buildings = result.get("items", []) if isinstance(result, dict) else result
            logger.info(f"Found {len(buildings)} buildings in polygon (BuildingAssignments API)")
            return buildings

        except Exception as e:
            logger.error(f"Error searching buildings in polygon: {e}")
            return []

    def get_neighborhoods_in_viewport(self, bounds: MapBounds) -> List[Dict]:
        """Get neighborhoods in viewport."""
        try:
            neighborhoods = self.api.get_neighborhoods_by_bounds(
                sw_lat=bounds.min_lat,
                sw_lng=bounds.min_lng,
                ne_lat=bounds.max_lat,
                ne_lng=bounds.max_lng
            )
            return neighborhoods

        except Exception as e:
            logger.error(f"Error loading neighborhoods: {e}")
            return []

    def get_neighborhood_by_point(self, lat: float, lng: float) -> Optional[Dict]:
        """Get neighborhood by point."""
        return self.api.get_neighborhood_by_point(latitude=lat, longitude=lng)

    @staticmethod
    def _bounds_to_polygon_wkt(bounds: MapBounds) -> str:
        """Convert bounding box to WKT polygon."""
        return (
            f"POLYGON(("
            f"{bounds.min_lng} {bounds.min_lat}, "
            f"{bounds.max_lng} {bounds.min_lat}, "
            f"{bounds.max_lng} {bounds.max_lat}, "
            f"{bounds.min_lng} {bounds.max_lat}, "
            f"{bounds.min_lng} {bounds.min_lat}"
            f"))"
        )
