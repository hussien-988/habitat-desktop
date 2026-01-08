# -*- coding: utf-8 -*-
"""
Geo API Service - REST API Endpoints for GIS
=============================================
Implements REST API endpoints for geographic data as per FSD 15.4 requirements.

Endpoints:
- /api/geo/buildings - Building polygons/points with spatial attributes
- /api/geo/units - Property unit locations linked to buildings
- /api/geo/claims - Claim locations with status and claimant information
- /api/geo/damage - Damage assessment locations with severity and type
- /api/geo/occupancy - Occupancy distribution and household density
- /api/geo/heatmap - Density heatmap data
- /api/geo/search - Spatial search within radius or polygon
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Enums and Data Classes ====================

class SpatialQueryType(Enum):
    """Types of spatial queries."""
    WITHIN_RADIUS = "within_radius"
    WITHIN_POLYGON = "within_polygon"
    WITHIN_BBOX = "within_bbox"
    NEAREST = "nearest"
    INTERSECTS = "intersects"


class GeoDataFormat(Enum):
    """Output formats for geo data."""
    GEOJSON = "geojson"
    WKT = "wkt"
    SIMPLE = "simple"  # lat/lng only


@dataclass
class GeoAPIResponse:
    """Standard response structure for Geo API."""
    success: bool
    data: Any
    count: int = 0
    total: int = 0
    page: int = 1
    page_size: int = 100
    message: str = ""
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "data": self.data,
            "count": self.count,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size
        }
        if self.message:
            result["message"] = self.message
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass
class SpatialFilter:
    """Spatial filter parameters."""
    # Bounding box
    min_lat: Optional[float] = None
    min_lng: Optional[float] = None
    max_lat: Optional[float] = None
    max_lng: Optional[float] = None

    # Radius search
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_meters: Optional[float] = None

    # Polygon search (list of [lng, lat] pairs)
    polygon: Optional[List[List[float]]] = None

    # Attribute filters
    neighborhood_code: Optional[str] = None
    district_code: Optional[str] = None
    status: Optional[str] = None

    # Pagination
    limit: int = 100
    offset: int = 0

    def has_bbox(self) -> bool:
        return all([self.min_lat, self.min_lng, self.max_lat, self.max_lng])

    def has_radius(self) -> bool:
        return all([self.center_lat, self.center_lng, self.radius_meters])


# ==================== Geo API Service ====================

class GeoAPIService:
    """
    REST API service for geographic data.

    Implements FSD 15.4 REST API endpoints for geo-layers.
    """

    # Constants
    EARTH_RADIUS_METERS = 6371000
    DEFAULT_PAGE_SIZE = 100
    MAX_PAGE_SIZE = 1000

    def __init__(self, db_connection):
        self.db = db_connection

    # ==================== Buildings API ====================

    def get_buildings(
        self,
        filters: Optional[SpatialFilter] = None,
        output_format: GeoDataFormat = GeoDataFormat.GEOJSON
    ) -> GeoAPIResponse:
        """
        GET /api/geo/buildings

        Returns building polygons/points with spatial attributes.
        """
        try:
            filters = filters or SpatialFilter()

            # Build query
            query = """
                SELECT building_uuid, building_id, neighborhood_code,
                       building_type, building_status, number_of_units,
                       latitude, longitude, polygon_wkt,
                       created_at, updated_at
                FROM buildings
                WHERE (latitude IS NOT NULL OR polygon_wkt IS NOT NULL)
            """
            params = []

            # Apply spatial filters
            query, params = self._apply_spatial_filters(query, params, filters)

            # Apply attribute filters
            if filters.neighborhood_code:
                query += " AND neighborhood_code = ?"
                params.append(filters.neighborhood_code)

            if filters.status:
                query += " AND building_status = ?"
                params.append(filters.status)

            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM ({query})"
            cursor = self.db.cursor()
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Apply pagination
            query += f" LIMIT {min(filters.limit, self.MAX_PAGE_SIZE)} OFFSET {filters.offset}"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Format output
            if output_format == GeoDataFormat.GEOJSON:
                data = self._buildings_to_geojson(rows)
            elif output_format == GeoDataFormat.WKT:
                data = self._buildings_to_wkt(rows)
            else:
                data = self._buildings_to_simple(rows)

            return GeoAPIResponse(
                success=True,
                data=data,
                count=len(rows),
                total=total,
                page=filters.offset // filters.limit + 1,
                page_size=filters.limit,
                metadata={
                    "format": output_format.value,
                    "crs": "EPSG:4326"
                }
            )

        except Exception as e:
            logger.error(f"Error in get_buildings: {e}", exc_info=True)
            return GeoAPIResponse(
                success=False,
                data=None,
                message=str(e)
            )

    def _buildings_to_geojson(self, rows: List) -> Dict:
        """Convert building rows to GeoJSON FeatureCollection."""
        features = []

        for row in rows:
            geometry = None
            if row[8]:  # polygon_wkt
                geometry = self._wkt_to_geojson(row[8])
            elif row[6] and row[7]:  # lat, lng
                geometry = {"type": "Point", "coordinates": [row[7], row[6]]}

            if geometry:
                features.append({
                    "type": "Feature",
                    "id": row[0],
                    "geometry": geometry,
                    "properties": {
                        "building_uuid": row[0],
                        "building_id": row[1],
                        "neighborhood_code": row[2],
                        "building_type": row[3],
                        "building_status": row[4],
                        "number_of_units": row[5],
                        "created_at": row[9],
                        "updated_at": row[10]
                    }
                })

        return {
            "type": "FeatureCollection",
            "name": "buildings",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}
            },
            "features": features
        }

    def _buildings_to_wkt(self, rows: List) -> List[Dict]:
        """Convert building rows to WKT format."""
        results = []
        for row in rows:
            wkt = row[8] if row[8] else f"POINT({row[7]} {row[6]})" if row[6] and row[7] else None
            if wkt:
                results.append({
                    "building_uuid": row[0],
                    "building_id": row[1],
                    "geometry_wkt": wkt,
                    "properties": {
                        "neighborhood_code": row[2],
                        "building_type": row[3],
                        "building_status": row[4],
                        "number_of_units": row[5]
                    }
                })
        return results

    def _buildings_to_simple(self, rows: List) -> List[Dict]:
        """Convert building rows to simple format."""
        results = []
        for row in rows:
            if row[6] and row[7]:
                results.append({
                    "building_uuid": row[0],
                    "building_id": row[1],
                    "latitude": row[6],
                    "longitude": row[7],
                    "neighborhood_code": row[2],
                    "building_type": row[3],
                    "building_status": row[4],
                    "number_of_units": row[5]
                })
        return results

    # ==================== Units API ====================

    def get_units(
        self,
        filters: Optional[SpatialFilter] = None,
        building_uuid: Optional[str] = None,
        output_format: GeoDataFormat = GeoDataFormat.GEOJSON
    ) -> GeoAPIResponse:
        """
        GET /api/geo/units

        Returns property unit locations linked to buildings.
        """
        try:
            filters = filters or SpatialFilter()

            query = """
                SELECT u.unit_uuid, u.unit_id, u.building_uuid, u.unit_type,
                       u.floor_number, u.unit_area, u.occupancy_status,
                       b.latitude, b.longitude, b.building_id
                FROM units u
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
            """
            params = []

            if building_uuid:
                query += " AND u.building_uuid = ?"
                params.append(building_uuid)

            # Apply spatial filters on building location
            query, params = self._apply_spatial_filters(query, params, filters, lat_col="b.latitude", lng_col="b.longitude")

            # Get total
            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor = self.db.cursor()
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Pagination
            query += f" LIMIT {min(filters.limit, self.MAX_PAGE_SIZE)} OFFSET {filters.offset}"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Format output
            if output_format == GeoDataFormat.GEOJSON:
                features = []
                for row in rows:
                    features.append({
                        "type": "Feature",
                        "id": row[0],
                        "geometry": {"type": "Point", "coordinates": [row[8], row[7]]},
                        "properties": {
                            "unit_uuid": row[0],
                            "unit_id": row[1],
                            "building_uuid": row[2],
                            "building_id": row[9],
                            "unit_type": row[3],
                            "floor_number": row[4],
                            "unit_area": row[5],
                            "occupancy_status": row[6]
                        }
                    })
                data = {
                    "type": "FeatureCollection",
                    "name": "units",
                    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
                    "features": features
                }
            else:
                data = [
                    {
                        "unit_uuid": row[0],
                        "unit_id": row[1],
                        "building_id": row[9],
                        "latitude": row[7],
                        "longitude": row[8],
                        "unit_type": row[3],
                        "floor_number": row[4]
                    }
                    for row in rows
                ]

            return GeoAPIResponse(
                success=True,
                data=data,
                count=len(rows),
                total=total,
                page=filters.offset // filters.limit + 1,
                page_size=filters.limit
            )

        except Exception as e:
            logger.error(f"Error in get_units: {e}", exc_info=True)
            return GeoAPIResponse(success=False, data=None, message=str(e))

    # ==================== Claims API ====================

    def get_claims(
        self,
        filters: Optional[SpatialFilter] = None,
        output_format: GeoDataFormat = GeoDataFormat.GEOJSON
    ) -> GeoAPIResponse:
        """
        GET /api/geo/claims

        Returns claim locations with status and claimant information.
        """
        try:
            filters = filters or SpatialFilter()

            query = """
                SELECT c.claim_uuid, c.case_number, c.case_status, c.claim_type,
                       c.created_at, c.updated_at,
                       b.building_id, b.latitude, b.longitude,
                       u.unit_id, u.unit_type,
                       p.full_name as claimant_name
                FROM claims c
                JOIN units u ON c.unit_uuid = u.unit_uuid
                JOIN buildings b ON u.building_uuid = b.building_uuid
                LEFT JOIN persons p ON c.claimant_uuid = p.person_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
            """
            params = []

            if filters.status:
                query += " AND c.case_status = ?"
                params.append(filters.status)

            query, params = self._apply_spatial_filters(query, params, filters, lat_col="b.latitude", lng_col="b.longitude")

            # Get total
            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor = self.db.cursor()
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Pagination
            query += f" LIMIT {min(filters.limit, self.MAX_PAGE_SIZE)} OFFSET {filters.offset}"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            if output_format == GeoDataFormat.GEOJSON:
                features = []
                for row in rows:
                    # Color based on status
                    status_colors = {
                        'approved': '#28A745',
                        'rejected': '#DC3545',
                        'pending': '#FFC107',
                        'in_progress': '#17A2B8'
                    }

                    features.append({
                        "type": "Feature",
                        "id": row[0],
                        "geometry": {"type": "Point", "coordinates": [row[8], row[7]]},
                        "properties": {
                            "claim_uuid": row[0],
                            "case_number": row[1],
                            "case_status": row[2],
                            "claim_type": row[3],
                            "building_id": row[6],
                            "unit_id": row[9],
                            "unit_type": row[10],
                            "claimant_name": row[11],
                            "created_at": row[4],
                            "updated_at": row[5],
                            "marker_color": status_colors.get(row[2], '#6C757D')
                        }
                    })

                data = {
                    "type": "FeatureCollection",
                    "name": "claims",
                    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
                    "features": features
                }
            else:
                data = [
                    {
                        "claim_uuid": row[0],
                        "case_number": row[1],
                        "case_status": row[2],
                        "latitude": row[7],
                        "longitude": row[8],
                        "building_id": row[6],
                        "unit_id": row[9]
                    }
                    for row in rows
                ]

            return GeoAPIResponse(
                success=True,
                data=data,
                count=len(rows),
                total=total,
                page=filters.offset // filters.limit + 1,
                page_size=filters.limit
            )

        except Exception as e:
            logger.error(f"Error in get_claims: {e}", exc_info=True)
            return GeoAPIResponse(success=False, data=None, message=str(e))

    # ==================== Damage API ====================

    def get_damage_assessments(
        self,
        filters: Optional[SpatialFilter] = None,
        severity: Optional[str] = None,
        output_format: GeoDataFormat = GeoDataFormat.GEOJSON
    ) -> GeoAPIResponse:
        """
        GET /api/geo/damage

        Returns damage assessment locations with severity and type.
        """
        try:
            filters = filters or SpatialFilter()

            query = """
                SELECT d.damage_id, d.building_uuid, d.damage_type, d.severity,
                       d.damage_description, d.assessment_date, d.assessed_by,
                       b.building_id, b.latitude, b.longitude
                FROM damage_assessments d
                JOIN buildings b ON d.building_uuid = b.building_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
            """
            params = []

            if severity:
                query += " AND d.severity = ?"
                params.append(severity)

            query, params = self._apply_spatial_filters(query, params, filters, lat_col="b.latitude", lng_col="b.longitude")

            # Get total
            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor = self.db.cursor()
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Pagination
            query += f" LIMIT {min(filters.limit, self.MAX_PAGE_SIZE)} OFFSET {filters.offset}"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            if output_format == GeoDataFormat.GEOJSON:
                severity_colors = {
                    'minor': '#FFC107',
                    'moderate': '#FD7E14',
                    'major': '#DC3545',
                    'destroyed': '#343A40'
                }

                features = []
                for row in rows:
                    features.append({
                        "type": "Feature",
                        "id": row[0],
                        "geometry": {"type": "Point", "coordinates": [row[9], row[8]]},
                        "properties": {
                            "damage_id": row[0],
                            "building_uuid": row[1],
                            "building_id": row[7],
                            "damage_type": row[2],
                            "severity": row[3],
                            "damage_description": row[4],
                            "assessment_date": row[5],
                            "assessed_by": row[6],
                            "marker_color": severity_colors.get(row[3], '#6C757D')
                        }
                    })

                data = {
                    "type": "FeatureCollection",
                    "name": "damage_assessments",
                    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
                    "features": features
                }
            else:
                data = [
                    {
                        "damage_id": row[0],
                        "building_id": row[7],
                        "damage_type": row[2],
                        "severity": row[3],
                        "latitude": row[8],
                        "longitude": row[9]
                    }
                    for row in rows
                ]

            return GeoAPIResponse(
                success=True,
                data=data,
                count=len(rows),
                total=total,
                page=filters.offset // filters.limit + 1,
                page_size=filters.limit
            )

        except Exception as e:
            logger.error(f"Error in get_damage: {e}", exc_info=True)
            return GeoAPIResponse(success=False, data=None, message=str(e))

    # ==================== Occupancy API ====================

    def get_occupancy_distribution(
        self,
        filters: Optional[SpatialFilter] = None,
        output_format: GeoDataFormat = GeoDataFormat.GEOJSON
    ) -> GeoAPIResponse:
        """
        GET /api/geo/occupancy

        Returns occupancy distribution and household density.
        """
        try:
            filters = filters or SpatialFilter()

            query = """
                SELECT u.unit_uuid, u.unit_id, u.occupancy_status,
                       COUNT(h.household_id) as household_count,
                       SUM(COALESCE(h.total_members, 0)) as total_persons,
                       b.building_id, b.latitude, b.longitude
                FROM units u
                JOIN buildings b ON u.building_uuid = b.building_uuid
                LEFT JOIN households h ON u.unit_uuid = h.unit_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                GROUP BY u.unit_uuid
            """
            params = []

            # Note: spatial filters need to be applied differently for GROUP BY
            base_query = query

            # Get total
            count_query = f"SELECT COUNT(*) FROM ({base_query})"
            cursor = self.db.cursor()
            cursor.execute(count_query)
            total = cursor.fetchone()[0]

            # Pagination
            query = base_query + f" LIMIT {min(filters.limit, self.MAX_PAGE_SIZE)} OFFSET {filters.offset}"

            cursor.execute(query)
            rows = cursor.fetchall()

            if output_format == GeoDataFormat.GEOJSON:
                features = []
                for row in rows:
                    # Size based on density
                    density = row[4] or 0
                    marker_size = min(5 + density, 20)

                    features.append({
                        "type": "Feature",
                        "id": row[0],
                        "geometry": {"type": "Point", "coordinates": [row[7], row[6]]},
                        "properties": {
                            "unit_uuid": row[0],
                            "unit_id": row[1],
                            "occupancy_status": row[2],
                            "household_count": row[3] or 0,
                            "total_persons": row[4] or 0,
                            "building_id": row[5],
                            "marker_size": marker_size
                        }
                    })

                data = {
                    "type": "FeatureCollection",
                    "name": "occupancy",
                    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
                    "features": features
                }
            else:
                data = [
                    {
                        "unit_id": row[1],
                        "building_id": row[5],
                        "latitude": row[6],
                        "longitude": row[7],
                        "occupancy_status": row[2],
                        "household_count": row[3] or 0,
                        "total_persons": row[4] or 0
                    }
                    for row in rows
                ]

            return GeoAPIResponse(
                success=True,
                data=data,
                count=len(rows),
                total=total,
                page=filters.offset // filters.limit + 1,
                page_size=filters.limit
            )

        except Exception as e:
            logger.error(f"Error in get_occupancy: {e}", exc_info=True)
            return GeoAPIResponse(success=False, data=None, message=str(e))

    # ==================== Heatmap API ====================

    def get_heatmap_data(
        self,
        layer: str = "claims",
        cell_size: float = 0.01,
        filters: Optional[SpatialFilter] = None
    ) -> GeoAPIResponse:
        """
        GET /api/geo/heatmap

        Returns density data for heatmap visualization.
        """
        try:
            filters = filters or SpatialFilter()

            if layer == "claims":
                query = """
                    SELECT
                        ROUND(b.latitude / ?, 0) * ? as lat_cell,
                        ROUND(b.longitude / ?, 0) * ? as lng_cell,
                        COUNT(*) as intensity
                    FROM claims c
                    JOIN units u ON c.unit_uuid = u.unit_uuid
                    JOIN buildings b ON u.building_uuid = b.building_uuid
                    WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                    GROUP BY lat_cell, lng_cell
                """
                params = [cell_size, cell_size, cell_size, cell_size]
            elif layer == "buildings":
                query = """
                    SELECT
                        ROUND(latitude / ?, 0) * ? as lat_cell,
                        ROUND(longitude / ?, 0) * ? as lng_cell,
                        COUNT(*) as intensity
                    FROM buildings
                    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                    GROUP BY lat_cell, lng_cell
                """
                params = [cell_size, cell_size, cell_size, cell_size]
            elif layer == "damage":
                query = """
                    SELECT
                        ROUND(b.latitude / ?, 0) * ? as lat_cell,
                        ROUND(b.longitude / ?, 0) * ? as lng_cell,
                        COUNT(*) as intensity,
                        SUM(CASE WHEN d.severity = 'major' OR d.severity = 'destroyed' THEN 1 ELSE 0 END) as severe_count
                    FROM damage_assessments d
                    JOIN buildings b ON d.building_uuid = b.building_uuid
                    WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                    GROUP BY lat_cell, lng_cell
                """
                params = [cell_size, cell_size, cell_size, cell_size]
            else:
                return GeoAPIResponse(
                    success=False,
                    data=None,
                    message=f"Unknown layer: {layer}"
                )

            cursor = self.db.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            heatmap_points = []
            max_intensity = 1

            for row in rows:
                intensity = row[2]
                max_intensity = max(max_intensity, intensity)
                heatmap_points.append({
                    "lat": row[0],
                    "lng": row[1],
                    "intensity": intensity
                })

            # Normalize intensities
            for point in heatmap_points:
                point["normalized_intensity"] = point["intensity"] / max_intensity

            return GeoAPIResponse(
                success=True,
                data={
                    "points": heatmap_points,
                    "max_intensity": max_intensity,
                    "cell_size": cell_size,
                    "layer": layer
                },
                count=len(heatmap_points),
                total=len(heatmap_points),
                metadata={
                    "format": "heatmap",
                    "crs": "EPSG:4326"
                }
            )

        except Exception as e:
            logger.error(f"Error in get_heatmap: {e}", exc_info=True)
            return GeoAPIResponse(success=False, data=None, message=str(e))

    # ==================== Spatial Search API ====================

    def spatial_search(
        self,
        query_type: SpatialQueryType,
        center_lat: Optional[float] = None,
        center_lng: Optional[float] = None,
        radius_meters: Optional[float] = None,
        polygon: Optional[List[List[float]]] = None,
        layers: Optional[List[str]] = None,
        limit: int = 100
    ) -> GeoAPIResponse:
        """
        GET /api/geo/search

        Perform spatial search across layers.
        """
        try:
            layers = layers or ["buildings", "claims"]
            results = {}

            for layer in layers:
                if query_type == SpatialQueryType.WITHIN_RADIUS:
                    if not all([center_lat, center_lng, radius_meters]):
                        return GeoAPIResponse(
                            success=False,
                            data=None,
                            message="Radius search requires center_lat, center_lng, and radius_meters"
                        )
                    results[layer] = self._search_within_radius(
                        layer, center_lat, center_lng, radius_meters, limit
                    )
                elif query_type == SpatialQueryType.WITHIN_POLYGON:
                    if not polygon:
                        return GeoAPIResponse(
                            success=False,
                            data=None,
                            message="Polygon search requires polygon parameter"
                        )
                    results[layer] = self._search_within_polygon(layer, polygon, limit)
                elif query_type == SpatialQueryType.NEAREST:
                    if not all([center_lat, center_lng]):
                        return GeoAPIResponse(
                            success=False,
                            data=None,
                            message="Nearest search requires center_lat and center_lng"
                        )
                    results[layer] = self._search_nearest(
                        layer, center_lat, center_lng, limit
                    )

            total_count = sum(len(r) for r in results.values())

            return GeoAPIResponse(
                success=True,
                data=results,
                count=total_count,
                total=total_count,
                metadata={
                    "query_type": query_type.value,
                    "layers": layers
                }
            )

        except Exception as e:
            logger.error(f"Error in spatial_search: {e}", exc_info=True)
            return GeoAPIResponse(success=False, data=None, message=str(e))

    def _search_within_radius(
        self,
        layer: str,
        center_lat: float,
        center_lng: float,
        radius_meters: float,
        limit: int
    ) -> List[Dict]:
        """Search within radius using Haversine formula."""
        # Approximate degree range
        lat_range = radius_meters / 111000
        lng_range = radius_meters / (111000 * abs(center_lat) * 0.0175)  # cos approximation

        if layer == "buildings":
            query = """
                SELECT building_uuid, building_id, latitude, longitude, building_type
                FROM buildings
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND latitude IS NOT NULL
            """
        elif layer == "claims":
            query = """
                SELECT c.claim_uuid, c.case_number, b.latitude, b.longitude, c.case_status
                FROM claims c
                JOIN units u ON c.unit_uuid = u.unit_uuid
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE b.latitude BETWEEN ? AND ?
                  AND b.longitude BETWEEN ? AND ?
            """
        else:
            return []

        cursor = self.db.cursor()
        cursor.execute(query, [
            center_lat - lat_range, center_lat + lat_range,
            center_lng - lng_range, center_lng + lng_range
        ])

        results = []
        for row in cursor.fetchall():
            lat, lng = row[2], row[3]
            distance = self._haversine_distance(center_lat, center_lng, lat, lng)

            if distance <= radius_meters:
                results.append({
                    "id": row[0],
                    "identifier": row[1],
                    "latitude": lat,
                    "longitude": lng,
                    "attribute": row[4],
                    "distance_meters": round(distance, 2)
                })

        # Sort by distance
        results.sort(key=lambda x: x["distance_meters"])
        return results[:limit]

    def _search_within_polygon(
        self,
        layer: str,
        polygon: List[List[float]],
        limit: int
    ) -> List[Dict]:
        """Search within polygon using point-in-polygon test."""
        # Get bounding box
        min_lng = min(p[0] for p in polygon)
        max_lng = max(p[0] for p in polygon)
        min_lat = min(p[1] for p in polygon)
        max_lat = max(p[1] for p in polygon)

        if layer == "buildings":
            query = """
                SELECT building_uuid, building_id, latitude, longitude, building_type
                FROM buildings
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
            """
        elif layer == "claims":
            query = """
                SELECT c.claim_uuid, c.case_number, b.latitude, b.longitude, c.case_status
                FROM claims c
                JOIN units u ON c.unit_uuid = u.unit_uuid
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE b.latitude BETWEEN ? AND ?
                  AND b.longitude BETWEEN ? AND ?
            """
        else:
            return []

        cursor = self.db.cursor()
        cursor.execute(query, [min_lat, max_lat, min_lng, max_lng])

        results = []
        for row in cursor.fetchall():
            lat, lng = row[2], row[3]

            if self._point_in_polygon(lng, lat, polygon):
                results.append({
                    "id": row[0],
                    "identifier": row[1],
                    "latitude": lat,
                    "longitude": lng,
                    "attribute": row[4]
                })

        return results[:limit]

    def _search_nearest(
        self,
        layer: str,
        center_lat: float,
        center_lng: float,
        limit: int
    ) -> List[Dict]:
        """Find nearest features."""
        # Search in expanding radius
        return self._search_within_radius(layer, center_lat, center_lng, 5000, limit)

    # ==================== Utility Methods ====================

    def _apply_spatial_filters(
        self,
        query: str,
        params: List,
        filters: SpatialFilter,
        lat_col: str = "latitude",
        lng_col: str = "longitude"
    ) -> Tuple[str, List]:
        """Apply spatial filters to query."""
        if filters.has_bbox():
            query += f" AND {lat_col} BETWEEN ? AND ? AND {lng_col} BETWEEN ? AND ?"
            params.extend([filters.min_lat, filters.max_lat, filters.min_lng, filters.max_lng])

        if filters.neighborhood_code:
            query += " AND neighborhood_code = ?"
            params.append(filters.neighborhood_code)

        if filters.district_code:
            query += " AND district_code = ?"
            params.append(filters.district_code)

        return query, params

    def _haversine_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula."""
        import math

        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)

        a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return self.EARTH_RADIUS_METERS * c

    def _point_in_polygon(self, x: float, y: float, polygon: List[List[float]]) -> bool:
        """Check if point is inside polygon using ray casting."""
        n = len(polygon)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = polygon[i][0], polygon[i][1]
            xj, yj = polygon[j][0], polygon[j][1]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside

    def _wkt_to_geojson(self, wkt: str) -> Optional[Dict]:
        """Convert WKT to GeoJSON geometry."""
        try:
            wkt = wkt.strip()

            if wkt.upper().startswith("POINT"):
                coords_str = wkt[wkt.index("(")+1:wkt.rindex(")")].strip()
                parts = coords_str.split()
                return {"type": "Point", "coordinates": [float(parts[0]), float(parts[1])]}

            elif wkt.upper().startswith("POLYGON"):
                coords_str = wkt[wkt.index("((")+2:wkt.rindex("))")]
                rings = []
                for ring_str in coords_str.split("),("):
                    ring = []
                    for point_str in ring_str.split(","):
                        parts = point_str.strip().split()
                        ring.append([float(parts[0]), float(parts[1])])
                    rings.append(ring)
                return {"type": "Polygon", "coordinates": rings}

        except Exception as e:
            logger.warning(f"Failed to parse WKT: {e}")

        return None


# ==================== API Route Handler ====================

class GeoAPIRouter:
    """
    Router class for handling Geo API requests.

    Maps HTTP endpoints to service methods.
    """

    def __init__(self, service: GeoAPIService):
        self.service = service

    def route(self, path: str, params: Dict[str, Any]) -> GeoAPIResponse:
        """Route request to appropriate handler."""
        # Parse path
        parts = path.strip("/").split("/")

        if len(parts) < 2 or parts[0] != "api" or parts[1] != "geo":
            return GeoAPIResponse(
                success=False,
                data=None,
                message=f"Invalid path: {path}"
            )

        endpoint = parts[2] if len(parts) > 2 else ""

        # Build filters
        filters = SpatialFilter(
            min_lat=params.get("min_lat"),
            min_lng=params.get("min_lng"),
            max_lat=params.get("max_lat"),
            max_lng=params.get("max_lng"),
            center_lat=params.get("center_lat"),
            center_lng=params.get("center_lng"),
            radius_meters=params.get("radius"),
            neighborhood_code=params.get("neighborhood"),
            district_code=params.get("district"),
            status=params.get("status"),
            limit=int(params.get("limit", 100)),
            offset=int(params.get("offset", 0))
        )

        output_format = GeoDataFormat(params.get("format", "geojson"))

        # Route to handler
        if endpoint == "buildings":
            return self.service.get_buildings(filters, output_format)
        elif endpoint == "units":
            return self.service.get_units(filters, params.get("building_uuid"), output_format)
        elif endpoint == "claims":
            return self.service.get_claims(filters, output_format)
        elif endpoint == "damage":
            return self.service.get_damage_assessments(filters, params.get("severity"), output_format)
        elif endpoint == "occupancy":
            return self.service.get_occupancy_distribution(filters, output_format)
        elif endpoint == "heatmap":
            return self.service.get_heatmap_data(
                params.get("layer", "claims"),
                float(params.get("cell_size", 0.01)),
                filters
            )
        elif endpoint == "search":
            query_type = SpatialQueryType(params.get("query_type", "within_radius"))
            return self.service.spatial_search(
                query_type,
                filters.center_lat,
                filters.center_lng,
                filters.radius_meters,
                params.get("polygon"),
                params.get("layers", "").split(",") if params.get("layers") else None,
                filters.limit
            )
        else:
            return GeoAPIResponse(
                success=False,
                data=None,
                message=f"Unknown endpoint: {endpoint}"
            )
