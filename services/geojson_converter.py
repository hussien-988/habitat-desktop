# -*- coding: utf-8 -*-
"""
GeoJSON Converter Service - Unified Building Geometry Conversion.

Converts buildings to GeoJSON format supporting both Point and Polygon geometries.
Follows SOLID principles and DRY methodology.

Best Practices:
- Single Responsibility: Only handles GeoJSON conversion
- Open/Closed: Extensible for new geometry types
- Liskov Substitution: Works with any Building model
- Interface Segregation: Clear, focused interface
- Dependency Inversion: Depends on abstractions (Building model)

References:
- https://leafletjs.com/examples/geojson/
- https://geojson.org/
- https://tools.ietf.org/html/rfc7946
"""

import json
from typing import List, Dict, Any, Optional
from enum import Enum

from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)


class GeometryType(Enum):
    """Supported geometry types."""
    POINT = "Point"
    POLYGON = "Polygon"
    MULTI_POLYGON = "MultiPolygon"


class GeoJSONConverter:
    """
    Unified GeoJSON converter for building geometries.

    Supports multiple geometry types (Point, Polygon, MultiPolygon)
    and provides a single, consistent interface for map visualization.

    Design Patterns:
    - Strategy Pattern: Different conversion strategies for different geometries
    - Factory Pattern: Creates appropriate GeoJSON features based on geometry type
    """

    @staticmethod
    def buildings_to_geojson(
        buildings: List[Building],
        include_properties: Optional[List[str]] = None,
        prefer_polygons: bool = True
    ) -> str:
        """
        Convert list of buildings to GeoJSON FeatureCollection.

        Args:
            buildings: List of Building objects
            include_properties: Optional list of property names to include
            prefer_polygons: If True, prefer polygon geometry over point when available

        Returns:
            GeoJSON string (FeatureCollection)

        Design:
            - Uses pointToLayer for points (Leaflet best practice)
            - Uses style function for polygons (Leaflet best practice)
            - Unified layer management via FeatureGroup
        """
        features = []

        for building in buildings:
            feature = GeoJSONConverter._building_to_feature(
                building,
                include_properties=include_properties,
                prefer_polygons=prefer_polygons
            )

            if feature:
                features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "crs": {
                "type": "name",
                "properties": {
                    "name": "EPSG:4326"  # WGS84
                }
            }
        }

        return json.dumps(geojson, ensure_ascii=False, indent=None)

    @staticmethod
    def _building_to_feature(
        building: Building,
        include_properties: Optional[List[str]] = None,
        prefer_polygons: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Convert single building to GeoJSON Feature.

        Strategy Pattern: Selects appropriate conversion strategy based on
        available geometry data.

        Priority (when prefer_polygons=True):
        1. Polygon from geo_location field
        2. Polygon from building_geometry field
        3. Point from latitude/longitude

        Returns:
            GeoJSON Feature dict or None if no valid geometry
        """
        geometry = None
        geometry_type = None

        # Strategy 1: Try polygon from geo_location
        if prefer_polygons and building.geo_location:
            geometry, geometry_type = GeoJSONConverter._parse_geo_location(
                building.geo_location
            )

        # Strategy 2: Fallback to building_geometry if available
        if prefer_polygons and not geometry and hasattr(building, 'building_geometry') and building.building_geometry:
            geometry, geometry_type = GeoJSONConverter._parse_geo_location(
                building.building_geometry
            )

        # Strategy 3: Fallback to point coordinates
        if not geometry and building.latitude and building.longitude:
            geometry = {
                "type": "Point",
                "coordinates": [building.longitude, building.latitude]
            }
            geometry_type = GeometryType.POINT

        # No valid geometry found
        if not geometry:
            logger.debug(f"Building {building.building_id} has no valid geometry")
            return None

        # Build properties
        properties = GeoJSONConverter._extract_properties(
            building,
            include_properties,
            geometry_type
        )

        return {
            "type": "Feature",
            "id": building.building_uuid or building.building_id,
            "geometry": geometry,
            "properties": properties
        }

    @staticmethod
    def _parse_geo_location(geo_location: str) -> tuple[Optional[Dict], Optional[GeometryType]]:
        """
        Parse geo_location string (WKT or GeoJSON) to GeoJSON geometry.

        Supports:
        - WKT: POLYGON((lon lat, lon lat, ...))
        - WKT: POINT(lon lat)
        - GeoJSON: {"type": "Polygon", "coordinates": [...]}

        Returns:
            Tuple of (geometry_dict, geometry_type) or (None, None)
        """
        if not geo_location or not isinstance(geo_location, str):
            return None, None

        geo_location = geo_location.strip()

        # Try parsing as GeoJSON first
        if geo_location.startswith('{'):
            try:
                geojson = json.loads(geo_location)
                if 'type' in geojson and 'coordinates' in geojson:
                    geom_type_str = geojson['type'].upper()
                    if geom_type_str == 'POLYGON':
                        return geojson, GeometryType.POLYGON
                    elif geom_type_str == 'MULTIPOLYGON':
                        return geojson, GeometryType.MULTI_POLYGON
                    elif geom_type_str == 'POINT':
                        return geojson, GeometryType.POINT
            except json.JSONDecodeError:
                pass

        # Try parsing as WKT
        if geo_location.upper().startswith('MULTIPOLYGON'):
            geometry = GeoJSONConverter._wkt_multipolygon_to_geojson(geo_location)
            if geometry:
                return geometry, GeometryType.MULTI_POLYGON

        elif geo_location.upper().startswith('POLYGON'):
            geometry = GeoJSONConverter._wkt_polygon_to_geojson(geo_location)
            if geometry:
                return geometry, GeometryType.POLYGON

        elif geo_location.upper().startswith('POINT'):
            geometry = GeoJSONConverter._wkt_point_to_geojson(geo_location)
            if geometry:
                return geometry, GeometryType.POINT

        logger.warning(f"Unable to parse geo_location: {geo_location[:50]}...")
        return None, None

    @staticmethod
    def _wkt_polygon_to_geojson(wkt: str) -> Optional[Dict]:
        """
        Convert WKT POLYGON to GeoJSON geometry.

        Example WKT: POLYGON((lon lat, lon lat, lon lat, lon lat))
        """
        try:
            # Extract coordinates from WKT
            import re
            match = re.search(r'POLYGON\s*\(\s*\((.*?)\)\s*\)', wkt, re.IGNORECASE)
            if not match:
                return None

            coords_str = match.group(1)
            points = []

            for point_str in coords_str.split(','):
                point_str = point_str.strip()
                if not point_str:
                    continue

                parts = point_str.split()
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    points.append([lon, lat])

            if len(points) >= 4:  # Polygon must have at least 4 points (closed ring)
                return {
                    "type": "Polygon",
                    "coordinates": [points]  # Outer ring only (no holes for now)
                }

        except Exception as e:
            logger.error(f"Error parsing WKT polygon: {e}")

        return None

    @staticmethod
    def _wkt_multipolygon_to_geojson(wkt: str) -> Optional[Dict]:
        """
        Convert WKT MULTIPOLYGON to GeoJSON geometry.

        Example WKT: MULTIPOLYGON(((lon lat, lon lat, ...)), ((lon lat, lon lat, ...)))
        """
        try:
            import re

            # Remove MULTIPOLYGON wrapper and get inner content
            # MULTIPOLYGON(((coords)), ((coords))) -> ((coords)), ((coords))
            inner_match = re.search(r'MULTIPOLYGON\s*\(\s*(.*)\s*\)', wkt, re.IGNORECASE)
            if not inner_match:
                return None

            inner_content = inner_match.group(1)

            # Split into individual polygons by finding balanced parentheses
            # Each polygon is in format ((coords))
            all_polygons = []
            depth = 0
            current_polygon = ""

            for char in inner_content:
                if char == '(':
                    depth += 1
                    current_polygon += char
                elif char == ')':
                    depth -= 1
                    current_polygon += char
                    # When we close a complete polygon (depth returns to 0)
                    if depth == 0 and current_polygon.strip():
                        # Parse this polygon - remove exactly 2 outer parens
                        # ((coords)) -> coords or , ((coords)) -> coords
                        polygon_str = current_polygon.strip().lstrip(',').strip()
                        if polygon_str.startswith('((') and polygon_str.endswith('))'):
                            polygon_coords = polygon_str[2:-2]  # Remove (( and ))
                        else:
                            polygon_coords = polygon_str.strip('() ')

                        points = []
                        for point_str in polygon_coords.split(','):
                            point_str = point_str.strip()
                            if not point_str:
                                continue

                            parts = point_str.split()
                            if len(parts) >= 2:
                                lon, lat = float(parts[0]), float(parts[1])
                                points.append([lon, lat])

                        if len(points) >= 4:  # Valid polygon ring
                            all_polygons.append([points])

                        current_polygon = ""
                else:
                    current_polygon += char

            if all_polygons:
                return {
                    "type": "MultiPolygon",
                    "coordinates": all_polygons
                }

        except Exception as e:
            logger.error(f"Error parsing WKT multipolygon: {e}")

        return None

    @staticmethod
    def _wkt_point_to_geojson(wkt: str) -> Optional[Dict]:
        """
        Convert WKT POINT to GeoJSON geometry.

        Example WKT: POINT(lon lat)
        """
        try:
            import re
            match = re.search(r'POINT\s*\(\s*([\d.-]+)\s+([\d.-]+)\s*\)', wkt, re.IGNORECASE)
            if match:
                lon, lat = float(match.group(1)), float(match.group(2))
                return {
                    "type": "Point",
                    "coordinates": [lon, lat]
                }
        except Exception as e:
            logger.error(f"Error parsing WKT point: {e}")

        return None

    @staticmethod
    def _extract_properties(
        building: Building,
        include_properties: Optional[List[str]],
        geometry_type: Optional[GeometryType]
    ) -> Dict[str, Any]:
        """
        Extract building properties for GeoJSON feature.

        Default properties (always included):
        - building_id
        - building_uuid
        - status
        - neighborhood
        - geometry_type (for styling on map)

        Args:
            building: Building object
            include_properties: Additional properties to include
            geometry_type: Type of geometry (for styling hints)
        """
        properties = {
            "building_id": building.building_id,
            "building_uuid": building.building_uuid or building.building_id,
            "status": building.building_status or "intact",
            "neighborhood": building.neighborhood_name_ar or building.neighborhood_name or "",
            "units": building.number_of_units or 0,
            "type": building.building_type or "",
            "geometry_type": geometry_type.value if geometry_type else "Point"
        }

        # Add custom properties
        if include_properties:
            for prop_name in include_properties:
                if hasattr(building, prop_name):
                    properties[prop_name] = getattr(building, prop_name)

        return properties

    @staticmethod
    def validate_geojson(geojson_str: str) -> bool:
        """
        Validate GeoJSON string.

        Basic validation checks:
        - Valid JSON
        - Has 'type' field
        - Has 'features' (for FeatureCollection)

        Returns:
            True if valid, False otherwise
        """
        try:
            data = json.loads(geojson_str)

            if not isinstance(data, dict):
                return False

            if 'type' not in data:
                return False

            if data['type'] == 'FeatureCollection':
                return 'features' in data and isinstance(data['features'], list)

            elif data['type'] == 'Feature':
                return 'geometry' in data and 'properties' in data

            return False

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"GeoJSON validation error: {e}")
            return False


# Export convenience function
def buildings_to_geojson(
    buildings: List[Building],
    prefer_polygons: bool = True
) -> str:
    """
    Convenience function for converting buildings to GeoJSON.

    Args:
        buildings: List of Building objects
        prefer_polygons: Prefer polygon geometry over points when available

    Returns:
        GeoJSON FeatureCollection string
    """
    return GeoJSONConverter.buildings_to_geojson(
        buildings,
        prefer_polygons=prefer_polygons
    )
