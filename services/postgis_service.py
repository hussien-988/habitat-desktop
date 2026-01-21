# -*- coding: utf-8 -*-
"""
PostGIS Service - PostgreSQL/PostGIS Integration
=================================================
Implements PostGIS spatial database integration as per FSD requirements.

Features:
- PostgreSQL/PostGIS connection management
- Spatial queries with ST_* functions
- Geometry indexing
- Spatial relationship queries
- Distance and area calculations
- Geometry validation and repair
- Coordinate reference system transformation
- Spatial clustering
- Buffer operations
- Intersection and union operations
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Enums and Constants ====================

class SpatialRelation(Enum):
    """PostGIS spatial relationships."""
    INTERSECTS = "ST_Intersects"
    CONTAINS = "ST_Contains"
    WITHIN = "ST_Within"
    OVERLAPS = "ST_Overlaps"
    TOUCHES = "ST_Touches"
    CROSSES = "ST_Crosses"
    DISJOINT = "ST_Disjoint"
    EQUALS = "ST_Equals"
    COVERS = "ST_Covers"
    COVERED_BY = "ST_CoveredBy"


class GeometryType(Enum):
    """PostGIS geometry types."""
    POINT = "Point"
    LINESTRING = "LineString"
    POLYGON = "Polygon"
    MULTIPOINT = "MultiPoint"
    MULTILINESTRING = "MultiLineString"
    MULTIPOLYGON = "MultiPolygon"
    GEOMETRYCOLLECTION = "GeometryCollection"


class SpatialIndex(Enum):
    """Spatial index types."""
    GIST = "GIST"
    BRIN = "BRIN"
    SP_GIST = "SP-GiST"


@dataclass
class PostGISConfig:
    """PostGIS connection configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "trrcms"
    user: str = "trrcms_user"
    password: str = ""
    schema: str = "public"
    srid: int = 4326  # WGS84
    connection_timeout: int = 30
    pool_size: int = 5
    ssl_mode: str = "prefer"


@dataclass
class SpatialQueryResult:
    """Result from a spatial query."""
    feature_id: str
    geometry_wkt: str
    geometry_geojson: Dict
    properties: Dict[str, Any]
    distance: Optional[float] = None
    area: Optional[float] = None


# ==================== PostGIS Service ====================

class PostGISService:
    """
    PostGIS spatial database integration service.

    Implements FSD requirements for PostgreSQL/PostGIS spatial queries.
    """

    def __init__(self, config: Optional[PostGISConfig] = None):
        self.config = config or PostGISConfig()
        self._connection = None
        self._pool = None

    # ==================== Connection Management ====================

    def connect(self) -> bool:
        """Establish connection to PostGIS database."""
        try:
            import psycopg2
            from psycopg2 import pool

            connection_string = (
                f"host={self.config.host} "
                f"port={self.config.port} "
                f"dbname={self.config.database} "
                f"user={self.config.user} "
                f"password={self.config.password} "
                f"sslmode={self.config.ssl_mode} "
                f"connect_timeout={self.config.connection_timeout}"
            )

            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=self.config.pool_size,
                dsn=connection_string
            )

            # Test connection and PostGIS extension
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT PostGIS_Version()")
                version = cursor.fetchone()[0]
                logger.info(f"Connected to PostGIS {version}")

            return True

        except ImportError:
            logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
            return False
        except Exception as e:
            logger.error(f"Error connecting to PostGIS: {e}", exc_info=True)
            return False

    def disconnect(self):
        """Close database connection pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostGIS connection pool closed")

    def _get_connection(self):
        """Get connection from pool."""
        if not self._pool:
            raise RuntimeError("Not connected to database")
        return self._pool.getconn()

    def _return_connection(self, conn):
        """Return connection to pool."""
        if self._pool:
            self._pool.putconn(conn)

    def is_connected(self) -> bool:
        """Check if connected to database."""
        return self._pool is not None

    # ==================== Spatial Queries ====================

    def find_buildings_in_radius(
        self,
        center_lat: float,
        center_lng: float,
        radius_meters: float,
        limit: int = 100
    ) -> List[SpatialQueryResult]:
        """
        Find buildings within radius of a point.

        Uses PostGIS ST_DWithin for efficient spatial query.
        """
        query = f"""
            SELECT
                building_uuid,
                ST_AsText(geometry) as wkt,
                ST_AsGeoJSON(geometry) as geojson,
                building_id,
                neighborhood_code,
                building_type,
                building_status,
                ST_Distance(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), {self.config.srid})::geography
                ) as distance
            FROM {self.config.schema}.buildings
            WHERE ST_DWithin(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), {self.config.srid})::geography,
                %s
            )
            ORDER BY distance
            LIMIT %s
        """

        return self._execute_spatial_query(
            query,
            [center_lng, center_lat, center_lng, center_lat, radius_meters, limit]
        )

    def find_buildings_in_polygon(
        self,
        polygon_wkt: str,
        limit: int = 100
    ) -> List[SpatialQueryResult]:
        """
        Find buildings within a polygon.

        Uses PostGIS ST_Within for point-in-polygon query.
        """
        query = f"""
            SELECT
                building_uuid,
                ST_AsText(geometry) as wkt,
                ST_AsGeoJSON(geometry) as geojson,
                building_id,
                neighborhood_code,
                building_type,
                building_status,
                NULL as distance
            FROM {self.config.schema}.buildings
            WHERE ST_Within(
                geometry,
                ST_GeomFromText(%s, {self.config.srid})
            )
            LIMIT %s
        """

        return self._execute_spatial_query(query, [polygon_wkt, limit])

    def find_overlapping_buildings(
        self,
        building_uuid: str
    ) -> List[SpatialQueryResult]:
        """
        Find buildings that overlap with a given building.

        Uses PostGIS ST_Overlaps and ST_Intersects.
        """
        query = f"""
            SELECT
                b2.building_uuid,
                ST_AsText(b2.geometry) as wkt,
                ST_AsGeoJSON(b2.geometry) as geojson,
                b2.building_id,
                b2.neighborhood_code,
                b2.building_type,
                b2.building_status,
                ST_Area(ST_Intersection(b1.geometry, b2.geometry)::geography) as overlap_area
            FROM {self.config.schema}.buildings b1
            JOIN {self.config.schema}.buildings b2
                ON b1.building_uuid != b2.building_uuid
                AND (ST_Overlaps(b1.geometry, b2.geometry)
                     OR ST_Intersects(b1.geometry, b2.geometry))
            WHERE b1.building_uuid = %s
            ORDER BY overlap_area DESC
        """

        return self._execute_spatial_query(query, [building_uuid])

    def find_nearest_buildings(
        self,
        lat: float,
        lng: float,
        limit: int = 5
    ) -> List[SpatialQueryResult]:
        """
        Find nearest buildings to a point.

        Uses PostGIS KNN operator (<->) for efficient nearest neighbor search.
        """
        query = f"""
            SELECT
                building_uuid,
                ST_AsText(geometry) as wkt,
                ST_AsGeoJSON(geometry) as geojson,
                building_id,
                neighborhood_code,
                building_type,
                building_status,
                ST_Distance(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), {self.config.srid})::geography
                ) as distance
            FROM {self.config.schema}.buildings
            ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(%s, %s), {self.config.srid})
            LIMIT %s
        """

        return self._execute_spatial_query(
            query,
            [lng, lat, lng, lat, limit]
        )

    def get_buildings_by_bbox(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
        limit: int = 1000
    ) -> List[SpatialQueryResult]:
        """
        Get buildings within a bounding box.

        Uses PostGIS && operator for efficient bbox query.
        """
        query = f"""
            SELECT
                building_uuid,
                ST_AsText(geometry) as wkt,
                ST_AsGeoJSON(geometry) as geojson,
                building_id,
                neighborhood_code,
                building_type,
                building_status,
                NULL as distance
            FROM {self.config.schema}.buildings
            WHERE geometry && ST_MakeEnvelope(%s, %s, %s, %s, {self.config.srid})
            LIMIT %s
        """

        return self._execute_spatial_query(
            query,
            [min_lng, min_lat, max_lng, max_lat, limit]
        )

    def spatial_relationship_query(
        self,
        table1: str,
        table2: str,
        relation: SpatialRelation,
        filter_column: Optional[str] = None,
        filter_value: Optional[Any] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Execute a spatial relationship query between two tables.
        """
        query = f"""
            SELECT
                a.*,
                b.*
            FROM {self.config.schema}.{table1} a
            JOIN {self.config.schema}.{table2} b
                ON {relation.value}(a.geometry, b.geometry)
        """

        params = []
        if filter_column and filter_value:
            query += f" WHERE a.{filter_column} = %s"
            params.append(filter_value)

        query += f" LIMIT %s"
        params.append(limit)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results

        finally:
            self._return_connection(conn)

    # ==================== Geometry Operations ====================

    def calculate_area(self, geometry_wkt: str) -> float:
        """
        Calculate area of a geometry in square meters.

        Uses PostGIS ST_Area with geography type for accurate results.
        """
        query = f"""
            SELECT ST_Area(
                ST_GeomFromText(%s, {self.config.srid})::geography
            )
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt])
            result = cursor.fetchone()
            return result[0] if result else 0

        finally:
            self._return_connection(conn)

    def calculate_distance(
        self,
        point1_lng: float,
        point1_lat: float,
        point2_lng: float,
        point2_lat: float
    ) -> float:
        """
        Calculate distance between two points in meters.

        Uses PostGIS ST_Distance with geography type.
        """
        query = f"""
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(%s, %s), {self.config.srid})::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), {self.config.srid})::geography
            )
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [point1_lng, point1_lat, point2_lng, point2_lat])
            result = cursor.fetchone()
            return result[0] if result else 0

        finally:
            self._return_connection(conn)

    def create_buffer(
        self,
        geometry_wkt: str,
        buffer_meters: float
    ) -> str:
        """
        Create a buffer around a geometry.

        Uses PostGIS ST_Buffer with geography type.
        """
        query = f"""
            SELECT ST_AsText(
                ST_Buffer(
                    ST_GeomFromText(%s, {self.config.srid})::geography,
                    %s
                )::geometry
            )
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt, buffer_meters])
            result = cursor.fetchone()
            return result[0] if result else ""

        finally:
            self._return_connection(conn)

    def get_centroid(self, geometry_wkt: str) -> Tuple[float, float]:
        """
        Calculate centroid of a geometry.

        Uses PostGIS ST_Centroid.
        """
        query = f"""
            SELECT
                ST_X(ST_Centroid(ST_GeomFromText(%s, {self.config.srid}))),
                ST_Y(ST_Centroid(ST_GeomFromText(%s, {self.config.srid})))
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt, geometry_wkt])
            result = cursor.fetchone()
            return (result[0], result[1]) if result else (0, 0)

        finally:
            self._return_connection(conn)

    def simplify_geometry(
        self,
        geometry_wkt: str,
        tolerance: float = 0.0001
    ) -> str:
        """
        Simplify a geometry (reduce points).

        Uses PostGIS ST_Simplify.
        """
        query = f"""
            SELECT ST_AsText(
                ST_Simplify(
                    ST_GeomFromText(%s, {self.config.srid}),
                    %s
                )
            )
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt, tolerance])
            result = cursor.fetchone()
            return result[0] if result else geometry_wkt

        finally:
            self._return_connection(conn)

    def validate_geometry(self, geometry_wkt: str) -> Tuple[bool, str]:
        """
        Validate a geometry.

        Uses PostGIS ST_IsValid and ST_IsValidReason.
        """
        query = f"""
            SELECT
                ST_IsValid(ST_GeomFromText(%s, {self.config.srid})),
                ST_IsValidReason(ST_GeomFromText(%s, {self.config.srid}))
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt, geometry_wkt])
            result = cursor.fetchone()
            return (result[0], result[1]) if result else (False, "Unknown error")

        finally:
            self._return_connection(conn)

    def repair_geometry(self, geometry_wkt: str) -> str:
        """
        Repair an invalid geometry.

        Uses PostGIS ST_MakeValid.
        """
        query = f"""
            SELECT ST_AsText(
                ST_MakeValid(ST_GeomFromText(%s, {self.config.srid}))
            )
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt])
            result = cursor.fetchone()
            return result[0] if result else geometry_wkt

        finally:
            self._return_connection(conn)

    # ==================== CRS Transformation ====================

    def transform_geometry(
        self,
        geometry_wkt: str,
        from_srid: int,
        to_srid: int
    ) -> str:
        """
        Transform geometry from one CRS to another.

        Uses PostGIS ST_Transform.
        """
        query = f"""
            SELECT ST_AsText(
                ST_Transform(
                    ST_GeomFromText(%s, %s),
                    %s
                )
            )
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [geometry_wkt, from_srid, to_srid])
            result = cursor.fetchone()
            return result[0] if result else geometry_wkt

        finally:
            self._return_connection(conn)

    # ==================== Spatial Indexing ====================

    def create_spatial_index(
        self,
        table_name: str,
        geometry_column: str = "geometry",
        index_type: SpatialIndex = SpatialIndex.GIST
    ) -> bool:
        """
        Create spatial index on a table.

        Uses PostGIS GIST or BRIN index.
        """
        index_name = f"idx_{table_name}_{geometry_column}_spatial"

        query = f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {self.config.schema}.{table_name}
            USING {index_type.value} ({geometry_column})
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            logger.info(f"Created spatial index {index_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating spatial index: {e}")
            return False

        finally:
            self._return_connection(conn)

    def analyze_spatial_table(self, table_name: str) -> bool:
        """
        Update statistics for spatial query optimization.
        """
        query = f"ANALYZE {self.config.schema}.{table_name}"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error analyzing table: {e}")
            return False

        finally:
            self._return_connection(conn)

    # ==================== Clustering ====================

    def cluster_buildings_by_location(
        self,
        cluster_distance_meters: float = 100
    ) -> List[Dict]:
        """
        Cluster buildings by proximity.

        Uses PostGIS ST_ClusterDBSCAN.
        """
        query = f"""
            SELECT
                ST_ClusterDBSCAN(geometry::geography, eps := %s, minpoints := 1)
                    OVER () as cluster_id,
                building_uuid,
                building_id,
                ST_AsText(geometry) as geometry_wkt
            FROM {self.config.schema}.buildings
            WHERE geometry IS NOT NULL
            ORDER BY cluster_id
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [cluster_distance_meters])

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results

        finally:
            self._return_connection(conn)

    def get_cluster_summary(
        self,
        cluster_distance_meters: float = 100
    ) -> List[Dict]:
        """
        Get summary of building clusters.
        """
        query = f"""
            WITH clusters AS (
                SELECT
                    ST_ClusterDBSCAN(geometry::geography, eps := %s, minpoints := 1)
                        OVER () as cluster_id,
                    geometry
                FROM {self.config.schema}.buildings
                WHERE geometry IS NOT NULL
            )
            SELECT
                cluster_id,
                COUNT(*) as building_count,
                ST_AsText(ST_Centroid(ST_Collect(geometry))) as centroid_wkt,
                ST_AsText(ST_ConvexHull(ST_Collect(geometry))) as hull_wkt
            FROM clusters
            GROUP BY cluster_id
            ORDER BY building_count DESC
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [cluster_distance_meters])

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results

        finally:
            self._return_connection(conn)

    # ==================== Heatmap / Density ====================

    def get_density_grid(
        self,
        table_name: str,
        cell_size_degrees: float = 0.01
    ) -> List[Dict]:
        """
        Generate density grid for heatmap visualization.

        Uses PostGIS ST_SnapToGrid.
        """
        query = f"""
            SELECT
                ST_X(ST_SnapToGrid(geometry, %s)) as cell_x,
                ST_Y(ST_SnapToGrid(geometry, %s)) as cell_y,
                COUNT(*) as count
            FROM {self.config.schema}.{table_name}
            WHERE geometry IS NOT NULL
            GROUP BY cell_x, cell_y
            ORDER BY count DESC
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [cell_size_degrees, cell_size_degrees])

            results = []
            for row in cursor.fetchall():
                results.append({
                    "lng": row[0],
                    "lat": row[1],
                    "intensity": row[2]
                })

            return results

        finally:
            self._return_connection(conn)

    # ==================== Export Functions ====================

    def export_to_geojson(
        self,
        table_name: str,
        properties: List[str],
        where_clause: Optional[str] = None,
        limit: int = 10000
    ) -> Dict:
        """
        Export table data to GeoJSON format.
        """
        props_sql = ", ".join(properties)

        query = f"""
            SELECT
                ST_AsGeoJSON(geometry)::json as geometry,
                {props_sql}
            FROM {self.config.schema}.{table_name}
            WHERE geometry IS NOT NULL
        """

        if where_clause:
            query += f" AND {where_clause}"

        query += f" LIMIT {limit}"

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)

            features = []
            for row in cursor.fetchall():
                feature = {
                    "type": "Feature",
                    "geometry": row[0],
                    "properties": {}
                }
                for i, prop in enumerate(properties):
                    feature["properties"][prop] = row[i + 1]
                features.append(feature)

            return {
                "type": "FeatureCollection",
                "name": table_name,
                "crs": {
                    "type": "name",
                    "properties": {"name": f"urn:ogc:def:crs:EPSG::{self.config.srid}"}
                },
                "features": features
            }

        finally:
            self._return_connection(conn)

    # ==================== Enhanced Spatial Queries ====================

    def get_buildings_stats_in_polygon(
        self,
        polygon_wkt: str
    ) -> Dict[str, Any]:
        """
        Get statistical summary of buildings within a polygon.

        Returns:
            Dict with:
            - total_count: Total buildings in polygon
            - by_type: Count by building type
            - by_status: Count by building status
            - total_area: Sum of building areas (if available)
            - avg_distance_from_center: Average distance from polygon centroid
        """
        query = f"""
            WITH polygon_geom AS (
                SELECT ST_GeomFromText(%s, {self.config.srid}) as geom
            ),
            buildings_in_polygon AS (
                SELECT
                    b.*,
                    ST_Distance(
                        b.geometry::geography,
                        ST_Centroid((SELECT geom FROM polygon_geom))::geography
                    ) as dist_from_center
                FROM {self.config.schema}.buildings b, polygon_geom p
                WHERE ST_Within(b.geometry, p.geom)
            )
            SELECT
                COUNT(*) as total_count,
                json_object_agg(
                    COALESCE(building_type, 'unknown'),
                    type_count
                ) FILTER (WHERE building_type IS NOT NULL) as by_type,
                json_object_agg(
                    COALESCE(building_status, 'unknown'),
                    status_count
                ) FILTER (WHERE building_status IS NOT NULL) as by_status,
                AVG(dist_from_center) as avg_distance_from_center
            FROM (
                SELECT
                    building_type,
                    building_status,
                    dist_from_center,
                    COUNT(*) OVER (PARTITION BY building_type) as type_count,
                    COUNT(*) OVER (PARTITION BY building_status) as status_count
                FROM buildings_in_polygon
            ) stats
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [polygon_wkt])
            result = cursor.fetchone()

            if result:
                return {
                    "total_count": result[0] or 0,
                    "by_type": result[1] or {},
                    "by_status": result[2] or {},
                    "avg_distance_from_center": result[3] or 0
                }

            return {
                "total_count": 0,
                "by_type": {},
                "by_status": {},
                "avg_distance_from_center": 0
            }

        finally:
            self._return_connection(conn)

    def batch_check_buildings_in_polygons(
        self,
        polygons_wkt: List[str],
        building_uuids: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Check which buildings are contained in which polygons (batch operation).

        Args:
            polygons_wkt: List of polygon WKT strings
            building_uuids: Optional list of specific building UUIDs to check

        Returns:
            Dict mapping polygon index to list of building UUIDs contained
        """
        # Create temp table for polygons
        with self._get_connection() as conn:
            try:
                cursor = conn.cursor()

                # Create temporary table
                cursor.execute("""
                    CREATE TEMP TABLE IF NOT EXISTS temp_check_polygons (
                        polygon_id INTEGER,
                        geom GEOMETRY
                    )
                """)

                # Insert polygons
                for i, wkt in enumerate(polygons_wkt):
                    cursor.execute(
                        f"INSERT INTO temp_check_polygons VALUES (%s, ST_GeomFromText(%s, {self.config.srid}))",
                        [i, wkt]
                    )

                # Build buildings filter
                buildings_filter = ""
                params = []
                if building_uuids:
                    placeholders = ", ".join(["%s"] * len(building_uuids))
                    buildings_filter = f"AND b.building_uuid IN ({placeholders})"
                    params = building_uuids

                # Query for containment
                query = f"""
                    SELECT
                        p.polygon_id,
                        b.building_uuid
                    FROM temp_check_polygons p
                    JOIN {self.config.schema}.buildings b
                        ON ST_Within(b.geometry, p.geom)
                    WHERE 1=1 {buildings_filter}
                    ORDER BY p.polygon_id
                """

                cursor.execute(query, params)

                # Group results by polygon
                results = {}
                for row in cursor.fetchall():
                    polygon_idx = str(row[0])
                    building_uuid = row[1]

                    if polygon_idx not in results:
                        results[polygon_idx] = []
                    results[polygon_idx].append(building_uuid)

                # Clean up
                cursor.execute("DROP TABLE IF EXISTS temp_check_polygons")
                conn.commit()

                return results

            except Exception as e:
                logger.error(f"Error in batch polygon check: {e}")
                conn.rollback()
                return {}

    def get_polygon_intersection_areas(
        self,
        polygon1_wkt: str,
        polygon2_wkt: str
    ) -> Dict[str, float]:
        """
        Calculate intersection and union areas of two polygons.

        Returns:
            Dict with:
            - intersection_area: Area of intersection in square meters
            - union_area: Area of union in square meters
            - polygon1_area: Area of first polygon
            - polygon2_area: Area of second polygon
            - overlap_percentage: Percentage of polygon1 covered by polygon2
        """
        query = f"""
            WITH polys AS (
                SELECT
                    ST_GeomFromText(%s, {self.config.srid}) as geom1,
                    ST_GeomFromText(%s, {self.config.srid}) as geom2
            )
            SELECT
                ST_Area(ST_Intersection(geom1, geom2)::geography) as intersection_area,
                ST_Area(ST_Union(geom1, geom2)::geography) as union_area,
                ST_Area(geom1::geography) as area1,
                ST_Area(geom2::geography) as area2
            FROM polys
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [polygon1_wkt, polygon2_wkt])
            result = cursor.fetchone()

            if result:
                intersection_area = result[0] or 0
                union_area = result[1] or 0
                area1 = result[2] or 0
                area2 = result[3] or 0

                overlap_percentage = (intersection_area / area1 * 100) if area1 > 0 else 0

                return {
                    "intersection_area": intersection_area,
                    "union_area": union_area,
                    "polygon1_area": area1,
                    "polygon2_area": area2,
                    "overlap_percentage": overlap_percentage
                }

            return {
                "intersection_area": 0,
                "union_area": 0,
                "polygon1_area": 0,
                "polygon2_area": 0,
                "overlap_percentage": 0
            }

        finally:
            self._return_connection(conn)

    def find_buildings_intersecting_line(
        self,
        linestring_wkt: str,
        buffer_meters: float = 0
    ) -> List[SpatialQueryResult]:
        """
        Find buildings intersecting or near a line.

        Useful for infrastructure impact analysis (roads, pipelines, etc.).

        Args:
            linestring_wkt: WKT representation of line
            buffer_meters: Buffer distance around line (0 for exact intersection)
        """
        if buffer_meters > 0:
            geom_expr = f"ST_Buffer(ST_GeomFromText(%s, {self.config.srid})::geography, %s)::geometry"
            params = [linestring_wkt, buffer_meters]
        else:
            geom_expr = f"ST_GeomFromText(%s, {self.config.srid})"
            params = [linestring_wkt]

        query = f"""
            SELECT
                building_uuid,
                ST_AsText(geometry) as wkt,
                ST_AsGeoJSON(geometry) as geojson,
                building_id,
                neighborhood_code,
                building_type,
                building_status,
                ST_Distance(
                    geometry::geography,
                    ST_GeomFromText(%s, {self.config.srid})::geography
                ) as distance
            FROM {self.config.schema}.buildings
            WHERE ST_Intersects(
                geometry,
                {geom_expr}
            )
            ORDER BY distance
        """

        params.insert(0, linestring_wkt)  # For distance calculation

        return self._execute_spatial_query(query, params)

    def get_nearest_neighbor_analysis(
        self,
        sample_size: int = 100
    ) -> Dict[str, float]:
        """
        Perform nearest neighbor analysis on buildings.

        Returns:
            Dict with:
            - avg_nearest_distance: Average distance to nearest neighbor
            - median_nearest_distance: Median distance
            - min_distance: Minimum distance
            - max_distance: Maximum distance
            - clustering_index: Ratio indicating clustering (<1) or dispersion (>1)
        """
        query = f"""
            WITH nearest_distances AS (
                SELECT DISTINCT ON (b1.building_uuid)
                    b1.building_uuid,
                    ST_Distance(
                        b1.geometry::geography,
                        b2.geometry::geography
                    ) as distance
                FROM {self.config.schema}.buildings b1
                JOIN {self.config.schema}.buildings b2
                    ON b1.building_uuid != b2.building_uuid
                WHERE b1.geometry IS NOT NULL
                  AND b2.geometry IS NOT NULL
                ORDER BY b1.building_uuid, distance
                LIMIT %s
            )
            SELECT
                AVG(distance) as avg_distance,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY distance) as median_distance,
                MIN(distance) as min_distance,
                MAX(distance) as max_distance,
                COUNT(*) as sample_count
            FROM nearest_distances
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, [sample_size])
            result = cursor.fetchone()

            if result and result[4] > 0:  # sample_count > 0
                avg_dist = result[0] or 0
                median_dist = result[1] or 0

                # Calculate clustering index (simplified)
                # Real formula requires area and density, this is approximation
                clustering_index = median_dist / avg_dist if avg_dist > 0 else 1.0

                return {
                    "avg_nearest_distance": avg_dist,
                    "median_nearest_distance": median_dist,
                    "min_distance": result[2] or 0,
                    "max_distance": result[3] or 0,
                    "sample_size": result[4],
                    "clustering_index": clustering_index
                }

            return {
                "avg_nearest_distance": 0,
                "median_nearest_distance": 0,
                "min_distance": 0,
                "max_distance": 0,
                "sample_size": 0,
                "clustering_index": 1.0
            }

        finally:
            self._return_connection(conn)

    # ==================== Utility Methods ====================

    def _execute_spatial_query(
        self,
        query: str,
        params: List
    ) -> List[SpatialQueryResult]:
        """Execute a spatial query and return results."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                results.append(SpatialQueryResult(
                    feature_id=row[0],
                    geometry_wkt=row[1],
                    geometry_geojson=json.loads(row[2]) if row[2] else {},
                    properties={
                        "building_id": row[3],
                        "neighborhood_code": row[4],
                        "building_type": row[5],
                        "building_status": row[6]
                    },
                    distance=row[7] if len(row) > 7 else None
                ))

            return results

        finally:
            self._return_connection(conn)

    def execute_raw_query(
        self,
        query: str,
        params: Optional[List] = None
    ) -> List[Dict]:
        """Execute a raw SQL query and return results as dictionaries."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or [])

            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

            return results

        finally:
            self._return_connection(conn)

    def get_table_extent(self, table_name: str) -> Dict[str, float]:
        """Get the geographic extent of a table."""
        query = f"""
            SELECT
                ST_XMin(extent) as min_lng,
                ST_YMin(extent) as min_lat,
                ST_XMax(extent) as max_lng,
                ST_YMax(extent) as max_lat
            FROM (
                SELECT ST_Extent(geometry) as extent
                FROM {self.config.schema}.{table_name}
            ) t
        """

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()

            if result:
                return {
                    "min_lng": result[0],
                    "min_lat": result[1],
                    "max_lng": result[2],
                    "max_lat": result[3]
                }

            return {}

        finally:
            self._return_connection(conn)


# ==================== SQLite Fallback for PostGIS Functions ====================

class SQLiteSpatialService:
    """
    SQLite spatial service that emulates PostGIS functions.

    Provides spatial query capabilities for SQLite databases
    when PostGIS is not available.
    """

    def __init__(self, db_connection):
        self.db = db_connection

    def find_buildings_in_radius(
        self,
        center_lat: float,
        center_lng: float,
        radius_meters: float,
        limit: int = 100
    ) -> List[Dict]:
        """Find buildings within radius using Haversine formula."""
        # Approximate degree range for initial filter
        lat_range = radius_meters / 111000
        lng_range = radius_meters / (111000 * abs(center_lat) * 0.0175)

        cursor = self.db.cursor()
        cursor.execute("""
            SELECT building_uuid, building_id, latitude, longitude,
                   neighborhood_code, building_type, building_status,
                   polygon_wkt
            FROM buildings
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
              AND latitude IS NOT NULL
        """, [
            center_lat - lat_range, center_lat + lat_range,
            center_lng - lng_range, center_lng + lng_range
        ])

        results = []
        for row in cursor.fetchall():
            distance = self._haversine_distance(
                center_lat, center_lng,
                row[2], row[3]
            )

            if distance <= radius_meters:
                results.append({
                    'building_uuid': row[0],
                    'building_id': row[1],
                    'latitude': row[2],
                    'longitude': row[3],
                    'neighborhood_code': row[4],
                    'building_type': row[5],
                    'building_status': row[6],
                    'distance': distance
                })

        results.sort(key=lambda x: x['distance'])
        return results[:limit]

    def find_buildings_in_polygon(
        self,
        polygon_points: List[Tuple[float, float]],
        limit: int = 100
    ) -> List[Dict]:
        """Find buildings within polygon using ray casting."""
        # Get bounding box
        min_lng = min(p[0] for p in polygon_points)
        max_lng = max(p[0] for p in polygon_points)
        min_lat = min(p[1] for p in polygon_points)
        max_lat = max(p[1] for p in polygon_points)

        cursor = self.db.cursor()
        cursor.execute("""
            SELECT building_uuid, building_id, latitude, longitude,
                   neighborhood_code, building_type, building_status
            FROM buildings
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
        """, [min_lat, max_lat, min_lng, max_lng])

        results = []
        for row in cursor.fetchall():
            if self._point_in_polygon(row[3], row[2], polygon_points):
                results.append({
                    'building_uuid': row[0],
                    'building_id': row[1],
                    'latitude': row[2],
                    'longitude': row[3],
                    'neighborhood_code': row[4],
                    'building_type': row[5],
                    'building_status': row[6]
                })

        return results[:limit]

    def calculate_area(self, polygon_points: List[Tuple[float, float]]) -> float:
        """Calculate approximate area using Shoelace formula."""
        import math

        if len(polygon_points) < 3:
            return 0

        n = len(polygon_points)
        area = 0

        for i in range(n):
            j = (i + 1) % n
            lat1 = math.radians(polygon_points[i][1])
            lat2 = math.radians(polygon_points[j][1])
            lng1 = polygon_points[i][0]
            lng2 = polygon_points[j][0]

            area += lng1 * math.sin(lat2) - lng2 * math.sin(lat1)

        # Convert to square meters (rough approximation)
        return abs(area) * 6371000**2 / 2

    def _haversine_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """Calculate distance using Haversine formula."""
        import math

        R = 6371000  # Earth radius in meters

        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)

        a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def _point_in_polygon(
        self,
        x: float,
        y: float,
        polygon: List[Tuple[float, float]]
    ) -> bool:
        """Check if point is inside polygon using ray casting."""
        n = len(polygon)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside
