# -*- coding: utf-8 -*-
"""
Map Integration Service - PostGIS and GIS functionality.
Implements UC-000 S04, UC-007 S04, UC-012 S02a map-based features.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GeoPoint:
    """Geographic point coordinates."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None

    def to_wkt(self) -> str:
        """Convert to Well-Known Text format."""
        if self.altitude:
            return f"POINT Z ({self.longitude} {self.latitude} {self.altitude})"
        return f"POINT ({self.longitude} {self.latitude})"

    def to_geojson(self) -> Dict:
        """Convert to GeoJSON format."""
        coords = [self.longitude, self.latitude]
        if self.altitude:
            coords.append(self.altitude)
        return {
            "type": "Point",
            "coordinates": coords
        }

    @classmethod
    def from_wkt(cls, wkt: str) -> Optional['GeoPoint']:
        """Create from WKT string."""
        try:
            # Simple parser for POINT format
            wkt = wkt.strip().upper()
            if wkt.startswith("POINT"):
                coords_str = wkt.split("(")[1].split(")")[0].strip()
                parts = coords_str.split()
                lon = float(parts[0])
                lat = float(parts[1])
                alt = float(parts[2]) if len(parts) > 2 else None
                return cls(latitude=lat, longitude=lon, altitude=alt)
        except Exception as e:
            logger.warning(f"Failed to parse WKT: {e}")
        return None


@dataclass
class GeoPolygon:
    """Geographic polygon coordinates."""
    coordinates: List[List[Tuple[float, float]]]  # List of rings, each ring is list of (lon, lat) tuples

    def to_wkt(self) -> str:
        """Convert to Well-Known Text format."""
        rings = []
        for ring in self.coordinates:
            points = ", ".join([f"{lon} {lat}" for lon, lat in ring])
            rings.append(f"({points})")
        return f"POLYGON ({', '.join(rings)})"

    def to_geojson(self) -> Dict:
        """Convert to GeoJSON format."""
        return {
            "type": "Polygon",
            "coordinates": [[[lon, lat] for lon, lat in ring] for ring in self.coordinates]
        }

    @classmethod
    def from_wkt(cls, wkt: str) -> Optional['GeoPolygon']:
        """Create from WKT string."""
        try:
            wkt = wkt.strip()
            if wkt.upper().startswith("POLYGON"):
                # Extract coordinates
                coords_str = wkt[wkt.index("(")+1:wkt.rindex(")")]
                rings = []
                for ring_str in coords_str.split("),"):
                    ring_str = ring_str.strip().strip("(").strip(")")
                    ring = []
                    for point_str in ring_str.split(","):
                        parts = point_str.strip().split()
                        ring.append((float(parts[0]), float(parts[1])))
                    rings.append(ring)
                return cls(coordinates=rings)
        except Exception as e:
            logger.warning(f"Failed to parse WKT polygon: {e}")
        return None

    def get_centroid(self) -> GeoPoint:
        """Calculate centroid of the polygon."""
        if not self.coordinates or not self.coordinates[0]:
            return GeoPoint(0, 0)

        outer_ring = self.coordinates[0]
        n = len(outer_ring)
        if n == 0:
            return GeoPoint(0, 0)

        sum_lon = sum(p[0] for p in outer_ring)
        sum_lat = sum(p[1] for p in outer_ring)

        return GeoPoint(latitude=sum_lat/n, longitude=sum_lon/n)


@dataclass
class BuildingGeoData:
    """Geographic data for a building."""
    building_uuid: str
    building_id: str
    geometry_type: str  # 'point' or 'polygon'
    point: Optional[GeoPoint]
    polygon: Optional[GeoPolygon]
    neighborhood_code: str
    status: str
    properties: Dict[str, Any]


class MapService:
    """
    Map and GIS integration service.

    Provides:
    - Coordinate handling (WKT, GeoJSON)
    - PostGIS-compatible queries
    - GeoJSON export for QGIS
    - Map-based building selection
    - Spatial proximity analysis
    """

    # Map bounding box (from .env / Config)
    ALEPPO_BOUNDS = {
        "min_lat": Config.MAP_BOUNDS_MIN_LAT,
        "max_lat": Config.MAP_BOUNDS_MAX_LAT,
        "min_lon": Config.MAP_BOUNDS_MIN_LNG,
        "max_lon": Config.MAP_BOUNDS_MAX_LNG
    }

    def __init__(self, db_connection):
        self.db = db_connection

    def get_building_location(self, building_uuid: str) -> Optional[BuildingGeoData]:
        """Get geographic data for a building."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT building_uuid, building_id, geometry_type,
                       latitude, longitude, polygon_wkt,
                       neighborhood_code, building_status,
                       building_type, number_of_units
                FROM buildings
                WHERE building_uuid = ?
            """, (building_uuid,))

            row = cursor.fetchone()
            if not row:
                return None

            point = None
            polygon = None

            if row[3] and row[4]:  # latitude, longitude
                point = GeoPoint(latitude=row[3], longitude=row[4])

            if row[5]:  # polygon_wkt
                polygon = GeoPolygon.from_wkt(row[5])

            return BuildingGeoData(
                building_uuid=row[0],
                building_id=row[1],
                geometry_type=row[2] or ("polygon" if polygon else "point"),
                point=point,
                polygon=polygon,
                neighborhood_code=row[6] or "",
                status=row[7] or "",
                properties={
                    "building_type": row[8],
                    "number_of_units": row[9]
                }
            )

        except Exception as e:
            logger.error(f"Error getting building location: {e}", exc_info=True)
            return None

    def update_building_geometry(
        self,
        building_uuid: str,
        point: Optional[GeoPoint] = None,
        polygon: Optional[GeoPolygon] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Update building geometry from map selection.

        Implements UC-000 S04: Enter geo location/Geometry
        """
        try:
            cursor = self.db.cursor()

            geometry_type = "polygon" if polygon else "point"
            latitude = point.latitude if point else None
            longitude = point.longitude if point else None
            polygon_wkt = polygon.to_wkt() if polygon else None
            geojson = json.dumps(
                polygon.to_geojson() if polygon else (point.to_geojson() if point else None)
            )

            cursor.execute("""
                UPDATE buildings
                SET geometry_type = ?,
                    latitude = ?,
                    longitude = ?,
                    polygon_wkt = ?,
                    geometry_geojson = ?,
                    updated_at = ?,
                    updated_by = ?
                WHERE building_uuid = ?
            """, (
                geometry_type,
                latitude,
                longitude,
                polygon_wkt,
                geojson,
                datetime.now().isoformat(),
                user_id,
                building_uuid
            ))

            self.db.commit()

            # Log audit
            self._log_geometry_change(building_uuid, geometry_type, user_id)

            return True

        except Exception as e:
            logger.error(f"Error updating building geometry: {e}", exc_info=True)
            return False

    def search_buildings_by_location(
        self,
        center: GeoPoint,
        radius_meters: float = 1000
    ) -> List[BuildingGeoData]:
        """
        Search buildings within radius of a point.

        Uses Haversine formula for distance calculation.
        """
        try:
            cursor = self.db.cursor()

            # Approximate degree to meters conversion at Aleppo's latitude
            # 1 degree latitude ≈ 111km, 1 degree longitude ≈ 85km at 36°N
            lat_range = radius_meters / 111000
            lon_range = radius_meters / 85000

            cursor.execute("""
                SELECT building_uuid, building_id, geometry_type,
                       latitude, longitude, polygon_wkt,
                       neighborhood_code, building_status,
                       building_type, number_of_units
                FROM buildings
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
            """, (
                center.latitude - lat_range,
                center.latitude + lat_range,
                center.longitude - lon_range,
                center.longitude + lon_range
            ))

            results = []
            for row in cursor.fetchall():
                point = GeoPoint(latitude=row[3], longitude=row[4]) if row[3] and row[4] else None
                polygon = GeoPolygon.from_wkt(row[5]) if row[5] else None

                # Calculate actual distance
                if point:
                    distance = self._haversine_distance(center, point)
                    if distance <= radius_meters:
                        results.append(BuildingGeoData(
                            building_uuid=row[0],
                            building_id=row[1],
                            geometry_type=row[2] or "point",
                            point=point,
                            polygon=polygon,
                            neighborhood_code=row[6] or "",
                            status=row[7] or "",
                            properties={
                                "building_type": row[8],
                                "number_of_units": row[9],
                                "distance_meters": distance
                            }
                        ))

            return sorted(results, key=lambda x: x.properties.get("distance_meters", 0))

        except Exception as e:
            logger.error(f"Error searching buildings by location: {e}", exc_info=True)
            return []

    def search_buildings_in_polygon(self, polygon: GeoPolygon) -> List[BuildingGeoData]:
        """
        Search buildings within a polygon.

        Implements UC-012 S02a: Locate building on the map
        """
        try:
            # Get bounding box for initial filter
            all_coords = [coord for ring in polygon.coordinates for coord in ring]
            min_lon = min(c[0] for c in all_coords)
            max_lon = max(c[0] for c in all_coords)
            min_lat = min(c[1] for c in all_coords)
            max_lat = max(c[1] for c in all_coords)

            cursor = self.db.cursor()
            cursor.execute("""
                SELECT building_uuid, building_id, geometry_type,
                       latitude, longitude, polygon_wkt,
                       neighborhood_code, building_status,
                       building_type, number_of_units
                FROM buildings
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
            """, (min_lat, max_lat, min_lon, max_lon))

            results = []
            for row in cursor.fetchall():
                point = GeoPoint(latitude=row[3], longitude=row[4]) if row[3] and row[4] else None

                if point and self._point_in_polygon(point, polygon):
                    building_polygon = GeoPolygon.from_wkt(row[5]) if row[5] else None
                    results.append(BuildingGeoData(
                        building_uuid=row[0],
                        building_id=row[1],
                        geometry_type=row[2] or "point",
                        point=point,
                        polygon=building_polygon,
                        neighborhood_code=row[6] or "",
                        status=row[7] or "",
                        properties={
                            "building_type": row[8],
                            "number_of_units": row[9]
                        }
                    ))

            return results

        except Exception as e:
            logger.error(f"Error searching buildings in polygon: {e}", exc_info=True)
            return []

    def get_buildings_by_neighborhood(self, neighborhood_code: str) -> List[BuildingGeoData]:
        """Get all buildings in a neighborhood."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT building_uuid, building_id, geometry_type,
                       latitude, longitude, polygon_wkt,
                       neighborhood_code, building_status,
                       building_type, number_of_units
                FROM buildings
                WHERE neighborhood_code = ?
            """, (neighborhood_code,))

            results = []
            for row in cursor.fetchall():
                point = GeoPoint(latitude=row[3], longitude=row[4]) if row[3] and row[4] else None
                polygon = GeoPolygon.from_wkt(row[5]) if row[5] else None

                results.append(BuildingGeoData(
                    building_uuid=row[0],
                    building_id=row[1],
                    geometry_type=row[2] or "point",
                    point=point,
                    polygon=polygon,
                    neighborhood_code=row[6] or "",
                    status=row[7] or "",
                    properties={
                        "building_type": row[8],
                        "number_of_units": row[9]
                    }
                ))

            return results

        except Exception as e:
            logger.error(f"Error getting buildings by neighborhood: {e}", exc_info=True)
            return []

    def check_proximity_overlap(
        self,
        building1_uuid: str,
        building2_uuid: str
    ) -> Dict[str, Any]:
        """
        Check proximity/overlap between two buildings.

        Implements UC-007 S04: Check Location, Geometry and Documents
        """
        building1 = self.get_building_location(building1_uuid)
        building2 = self.get_building_location(building2_uuid)

        if not building1 or not building2:
            return {"error": "Building not found"}

        result = {
            "building1_id": building1.building_id,
            "building2_id": building2.building_id,
            "same_neighborhood": building1.neighborhood_code == building2.neighborhood_code,
            "distance_meters": None,
            "overlapping": False,
            "overlap_percentage": 0.0
        }

        # Calculate distance between centroids
        point1 = building1.point or (building1.polygon.get_centroid() if building1.polygon else None)
        point2 = building2.point or (building2.polygon.get_centroid() if building2.polygon else None)

        if point1 and point2:
            result["distance_meters"] = self._haversine_distance(point1, point2)

        # Check polygon overlap if both have polygons
        if building1.polygon and building2.polygon:
            result["overlapping"], result["overlap_percentage"] = self._check_polygon_overlap(
                building1.polygon, building2.polygon
            )

        return result

    def export_to_geojson(
        self,
        buildings: List[BuildingGeoData],
        include_properties: bool = True
    ) -> Dict:
        """
        Export buildings to GeoJSON format for QGIS.

        Implements FR-D-17: GeoJSON export with full geometry preservation.
        """
        features = []

        for building in buildings:
            geometry = None
            if building.polygon:
                geometry = building.polygon.to_geojson()
            elif building.point:
                geometry = building.point.to_geojson()
            else:
                continue

            feature = {
                "type": "Feature",
                "id": building.building_uuid,
                "geometry": geometry,
                "properties": {
                    "building_id": building.building_id,
                    "building_uuid": building.building_uuid,
                    "neighborhood_code": building.neighborhood_code,
                    "status": building.status
                }
            }

            if include_properties:
                feature["properties"].update(building.properties)

            features.append(feature)

        return {
            "type": "FeatureCollection",
            "name": "TRRCMS_Buildings",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}
            },
            "features": features
        }

    def export_buildings_geojson_file(
        self,
        file_path: Path,
        filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Export buildings to a GeoJSON file."""
        try:
            cursor = self.db.cursor()

            # Build query
            query = """
                SELECT building_uuid, building_id, geometry_type,
                       latitude, longitude, polygon_wkt,
                       neighborhood_code, building_status,
                       building_type, number_of_units
                FROM buildings
                WHERE (latitude IS NOT NULL OR polygon_wkt IS NOT NULL)
            """
            params = []

            if filters:
                if filters.get("neighborhood_code"):
                    query += " AND neighborhood_code = ?"
                    params.append(filters["neighborhood_code"])
                if filters.get("status"):
                    query += " AND building_status = ?"
                    params.append(filters["status"])

            cursor.execute(query, params)

            buildings = []
            for row in cursor.fetchall():
                point = GeoPoint(latitude=row[3], longitude=row[4]) if row[3] and row[4] else None
                polygon = GeoPolygon.from_wkt(row[5]) if row[5] else None

                buildings.append(BuildingGeoData(
                    building_uuid=row[0],
                    building_id=row[1],
                    geometry_type=row[2] or "point",
                    point=point,
                    polygon=polygon,
                    neighborhood_code=row[6] or "",
                    status=row[7] or "",
                    properties={
                        "building_type": row[8],
                        "number_of_units": row[9]
                    }
                ))

            geojson = self.export_to_geojson(buildings)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(geojson, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            logger.error(f"Error exporting GeoJSON: {e}", exc_info=True)
            return False

    def validate_coordinates(
        self,
        latitude: float,
        longitude: float
    ) -> Tuple[bool, str]:
        """Validate coordinates are within Aleppo bounds."""
        if latitude < self.ALEPPO_BOUNDS["min_lat"] or latitude > self.ALEPPO_BOUNDS["max_lat"]:
            return False, "الإحداثيات خارج نطاق حلب (خط العرض)"

        if longitude < self.ALEPPO_BOUNDS["min_lon"] or longitude > self.ALEPPO_BOUNDS["max_lon"]:
            return False, "الإحداثيات خارج نطاق حلب (خط الطول)"

        return True, ""

    def _haversine_distance(self, point1: GeoPoint, point2: GeoPoint) -> float:
        """Calculate distance between two points using Haversine formula."""
        import math

        R = 6371000  # Earth radius in meters

        lat1 = math.radians(point1.latitude)
        lat2 = math.radians(point2.latitude)
        dlat = math.radians(point2.latitude - point1.latitude)
        dlon = math.radians(point2.longitude - point1.longitude)

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def _point_in_polygon(self, point: GeoPoint, polygon: GeoPolygon) -> bool:
        """Check if a point is inside a polygon using ray casting."""
        if not polygon.coordinates:
            return False

        outer_ring = polygon.coordinates[0]
        n = len(outer_ring)
        inside = False

        x = point.longitude
        y = point.latitude

        j = n - 1
        for i in range(n):
            xi, yi = outer_ring[i]
            xj, yj = outer_ring[j]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside

    def _check_polygon_overlap(
        self,
        polygon1: GeoPolygon,
        polygon2: GeoPolygon
    ) -> Tuple[bool, float]:
        """
        Check if two polygons overlap.

        Returns (overlapping, overlap_percentage)
        """
        # Simplified overlap check - check if any vertex of one is inside the other
        if not polygon1.coordinates or not polygon2.coordinates:
            return False, 0.0

        outer1 = polygon1.coordinates[0]
        outer2 = polygon2.coordinates[0]

        # Check if any point of polygon1 is inside polygon2
        for lon, lat in outer1:
            test_point = GeoPoint(latitude=lat, longitude=lon)
            if self._point_in_polygon(test_point, polygon2):
                return True, 50.0  # Simplified percentage

        # Check if any point of polygon2 is inside polygon1
        for lon, lat in outer2:
            test_point = GeoPoint(latitude=lat, longitude=lon)
            if self._point_in_polygon(test_point, polygon1):
                return True, 50.0

        return False, 0.0

    def _log_geometry_change(
        self,
        building_uuid: str,
        geometry_type: str,
        user_id: Optional[str]
    ):
        """Log geometry change to audit trail."""
        try:
            import uuid as uuid_module
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO audit_log (
                    event_id, timestamp, user_id, action, entity, entity_id, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid_module.uuid4()),
                datetime.now().isoformat(),
                user_id,
                "UPDATE_GEOMETRY",
                "building",
                building_uuid,
                json.dumps({"geometry_type": geometry_type})
            ))
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not log geometry change: {e}")

    def get_claims_geojson(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Get claims as GeoJSON for map visualization.

        Implements FSD 15.1 GIS Dashboard requirements.
        """
        try:
            cursor = self.db.cursor()

            query = """
                SELECT c.claim_uuid, c.case_number, c.case_status,
                       b.building_uuid, b.building_id,
                       b.latitude, b.longitude, b.polygon_wkt,
                       u.unit_id, u.unit_type
                FROM claims c
                JOIN units u ON c.unit_uuid = u.unit_uuid
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE (b.latitude IS NOT NULL OR b.polygon_wkt IS NOT NULL)
            """
            params = []

            if filters:
                if filters.get("status"):
                    query += " AND c.case_status = ?"
                    params.append(filters["status"])
                if filters.get("neighborhood_code"):
                    query += " AND b.neighborhood_code = ?"
                    params.append(filters["neighborhood_code"])

            cursor.execute(query, params)

            features = []
            for row in cursor.fetchall():
                geometry = None
                if row[7]:  # polygon_wkt
                    polygon = GeoPolygon.from_wkt(row[7])
                    if polygon:
                        geometry = polygon.to_geojson()
                elif row[5] and row[6]:  # lat, lon
                    geometry = GeoPoint(latitude=row[5], longitude=row[6]).to_geojson()

                if geometry:
                    features.append({
                        "type": "Feature",
                        "id": row[0],  # claim_uuid
                        "geometry": geometry,
                        "properties": {
                            "claim_uuid": row[0],
                            "case_number": row[1],
                            "case_status": row[2],
                            "building_uuid": row[3],
                            "building_id": row[4],
                            "unit_id": row[8],
                            "unit_type": row[9]
                        }
                    })

            return {
                "type": "FeatureCollection",
                "name": "TRRCMS_Claims",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::4326"}
                },
                "features": features
            }

        except Exception as e:
            logger.error(f"Error getting claims GeoJSON: {e}", exc_info=True)
            return {"type": "FeatureCollection", "features": []}

    def get_density_heatmap_data(
        self,
        cell_size_degrees: float = 0.01
    ) -> List[Dict]:
        """
        Get data for density heatmap visualization.

        Returns grid cells with claim counts for heatmap rendering.
        """
        try:
            cursor = self.db.cursor()

            # Get all claim locations
            cursor.execute("""
                SELECT b.latitude, b.longitude, COUNT(*) as claim_count
                FROM claims c
                JOIN units u ON c.unit_uuid = u.unit_uuid
                JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
                GROUP BY
                    ROUND(b.latitude / ?, 0) * ?,
                    ROUND(b.longitude / ?, 0) * ?
            """, (cell_size_degrees, cell_size_degrees, cell_size_degrees, cell_size_degrees))

            heatmap_data = []
            for row in cursor.fetchall():
                heatmap_data.append({
                    "latitude": row[0],
                    "longitude": row[1],
                    "intensity": row[2]
                })

            return heatmap_data

        except Exception as e:
            logger.error(f"Error getting heatmap data: {e}", exc_info=True)
            return []
