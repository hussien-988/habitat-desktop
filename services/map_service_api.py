# -*- coding: utf-8 -*-
"""
Map Service API - نسخة MapService تستخدم Backend API بدلاً من قاعدة البيانات المحلية
====================================================================================

يوفر نفس الواجهة (interface) مثل MapService الأصلي، لكن يتصل بالـ Backend API.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import json

from services.api_client import TRRCMSApiClient, get_api_client, ApiConfig
from services.map_service import GeoPoint, GeoPolygon, BuildingGeoData
from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)


class MapServiceAPI:
    """
    Map service يستخدم Backend API.

    يوفر نفس الوظائف مثل MapService لكن يتصل بالـ API بدلاً من قاعدة البيانات.

    Usage:
        # Option 1: Using singleton
        map_service = MapServiceAPI()

        # Option 2: With custom API client
        api_client = TRRCMSApiClient(ApiConfig(base_url="http://api.example.com"))
        map_service = MapServiceAPI(api_client)
    """

    # Aleppo approximate bounding box (same as original MapService)
    ALEPPO_BOUNDS = {
        "min_lat": 36.0,
        "max_lat": 36.5,
        "min_lon": 36.8,
        "max_lon": 37.5
    }

    def __init__(self, api_client: Optional[TRRCMSApiClient] = None):
        """
        Initialize map service.

        Args:
            api_client: API client instance (يُنشأ تلقائياً إذا لم يُقدّم)
        """
        print("[DEBUG] Initializing MapServiceAPI...")
        self.api = api_client or get_api_client()
        print(f"[DEBUG] API Base URL: {self.api.base_url}")
        logger.info("✅ MapServiceAPI initialized with Backend API")

    def set_auth_token(self, token: str, expires_in: int = 3600):
        """
        Update API client auth token from external source.

        Professional Best Practice: Sync token with current user session.

        Args:
            token: Access token from current user
            expires_in: Token expiration time in seconds
        """
        if token:
            self.api.set_access_token(token, expires_in)
            logger.debug("✅ MapServiceAPI: Auth token synchronized")

    # ==================== Building Location ====================

    def get_building_location(self, building_uuid: str) -> Optional[BuildingGeoData]:
        """
        الحصول على موقع مبنى من الـ API.

        Args:
            building_uuid: UUID للمبنى

        Returns:
            BuildingGeoData أو None
        """
        try:
            building_data = self.api.get_building_by_id(building_uuid)

            if not building_data:
                return None

            # Convert API response to BuildingGeoData
            point = None
            polygon = None

            if building_data.get("latitude") and building_data.get("longitude"):
                point = GeoPoint(
                    latitude=building_data["latitude"],
                    longitude=building_data["longitude"]
                )

            if building_data.get("buildingGeometryWkt"):
                polygon = GeoPolygon.from_wkt(building_data["buildingGeometryWkt"])

            return BuildingGeoData(
                building_uuid=building_data["id"],
                building_id=building_data.get("buildingId", ""),
                geometry_type="polygon" if polygon else "point",
                point=point,
                polygon=polygon,
                neighborhood_code=building_data.get("neighborhoodCode", ""),
                status=building_data.get("status", ""),
                properties={
                    "building_type": building_data.get("buildingType"),
                    "number_of_units": building_data.get("numberOfPropertyUnits", 0)
                }
            )

        except Exception as e:
            logger.error(f"Error getting building location from API: {e}", exc_info=True)
            return None

    def update_building_geometry(
        self,
        building_uuid: str,
        point: Optional[GeoPoint] = None,
        polygon: Optional[GeoPolygon] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        تحديث موقع المبنى عبر الـ API.

        Args:
            building_uuid: UUID للمبنى
            point: موقع نقطة (optional)
            polygon: مضلع (optional)
            user_id: معرّف المستخدم (يُستخدم للـ audit)

        Returns:
            True إذا نجح التحديث
        """
        try:
            self.api.update_building_geometry(
                building_id=building_uuid,
                latitude=point.latitude if point else None,
                longitude=point.longitude if point else None,
                building_geometry_wkt=polygon.to_wkt() if polygon else None
            )

            logger.info(f"✅ Updated geometry for building {building_uuid}")
            return True

        except Exception as e:
            logger.error(f"❌ Error updating building geometry: {e}", exc_info=True)
            return False

    # ==================== Spatial Queries ====================

    def get_buildings_in_bbox(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        status_filter: Optional[str] = None,
        page_size: int = 1000
    ) -> List[Building]:
        """
        الحصول على المباني ضمن bounding box من الـ API.

        Uses /Buildings/polygon endpoint with PostGIS spatial filtering.

        Professional Best Practice:
        - Default page_size increased to 1000 for better coverage
        - Configurable for different use cases

        Args:
            north_east_lat: حد الشمال الشرقي (latitude)
            north_east_lng: حد الشمال الشرقي (longitude)
            south_west_lat: حد الجنوب الغربي (latitude)
            south_west_lng: حد الجنوب الغربي (longitude)
            status_filter: فلتر حسب حالة المبنى
            page_size: Maximum number of buildings to load (default: 1000)

        Returns:
            قائمة بـ Building objects
        """
        try:
            print(f"\n[DEBUG] MapServiceAPI.get_buildings_in_bbox() called")
            print(f"[DEBUG] BBox: NE({north_east_lat}, {north_east_lng}) - SW({south_west_lat}, {south_west_lng})")
            print(f"[DEBUG] Page Size: {page_size}")
            print(f"[DEBUG] Calling: POST /api/v1/Buildings/polygon")

            # Convert bounding box to polygon WKT
            # Polygon: SW corner → SE corner → NE corner → NW corner → SW corner (close)
            polygon_wkt = f"POLYGON(({south_west_lng} {south_west_lat}, {north_east_lng} {south_west_lat}, {north_east_lng} {north_east_lat}, {south_west_lng} {north_east_lat}, {south_west_lng} {south_west_lat}))"
            print(f"[DEBUG] Polygon WKT: {polygon_wkt}")

            buildings_data = self.api.get_buildings_in_polygon(
                polygon_wkt=polygon_wkt,
                status=status_filter,
                page=1,
                page_size=page_size  # Professional: Configurable page size
            )

            print(f"[DEBUG] API Response: {len(buildings_data)} buildings received")

            buildings = []
            for data in buildings_data:
                building = self._convert_api_building_to_model(data)
                buildings.append(building)

            print(f"[DEBUG] Converted to {len(buildings)} Building objects\n")
            logger.info(f"✅ Fetched {len(buildings)} buildings from API (polygon filter)")
            return buildings

        except Exception as e:
            logger.error(f"❌ Error fetching buildings from API: {e}", exc_info=True)
            return []

    def search_buildings_by_location(
        self,
        center: GeoPoint,
        radius_meters: float = 1000
    ) -> List[BuildingGeoData]:
        """
        البحث عن المباني ضمن دائرة.

        Args:
            center: مركز الدائرة
            radius_meters: نصف القطر بالأمتار

        Returns:
            قائمة بـ BuildingGeoData
        """
        # تحويل الدائرة إلى bounding box تقريبي
        # 1 degree latitude ≈ 111km, 1 degree longitude ≈ 85km at 36°N
        lat_range = radius_meters / 111000
        lng_range = radius_meters / 85000

        return self._fetch_buildings_as_geodata(
            north_east_lat=center.latitude + lat_range,
            north_east_lng=center.longitude + lng_range,
            south_west_lat=center.latitude - lat_range,
            south_west_lng=center.longitude - lng_range
        )

    def search_buildings_in_polygon(self, polygon: GeoPolygon) -> List[BuildingGeoData]:
        """
        البحث عن المباني داخل مضلع.

        Args:
            polygon: المضلع

        Returns:
            قائمة بـ BuildingGeoData
        """
        # Get bounding box for polygon
        all_coords = [coord for ring in polygon.coordinates for coord in ring]
        min_lng = min(c[0] for c in all_coords)
        max_lng = max(c[0] for c in all_coords)
        min_lat = min(c[1] for c in all_coords)
        max_lat = max(c[1] for c in all_coords)

        # Fetch buildings in bounding box
        all_buildings = self._fetch_buildings_as_geodata(
            north_east_lat=max_lat,
            north_east_lng=max_lng,
            south_west_lat=min_lat,
            south_west_lng=min_lng
        )

        # Filter to only buildings inside polygon
        buildings_in_polygon = []
        for building in all_buildings:
            if building.point and self._point_in_polygon(building.point, polygon):
                buildings_in_polygon.append(building)

        return buildings_in_polygon

    def get_buildings_by_neighborhood(
        self,
        neighborhood_code: str
    ) -> List[BuildingGeoData]:
        """
        الحصول على جميع المباني في حي معين.

        Args:
            neighborhood_code: رمز الحي

        Returns:
            قائمة بـ BuildingGeoData
        """
        try:
            result = self.api.search_buildings(
                neighborhood_code=neighborhood_code,
                page_size=1000
            )

            buildings = result.get("items", [])
            return [self._convert_api_building_to_geodata(b) for b in buildings]

        except Exception as e:
            logger.error(f"Error fetching buildings by neighborhood: {e}")
            return []

    # ==================== Proximity & Overlap ====================

    def check_proximity_overlap(
        self,
        building1_uuid: str,
        building2_uuid: str
    ) -> Dict[str, Any]:
        """
        فحص التقارب والتداخل بين مبنيين.

        Args:
            building1_uuid: UUID للمبنى الأول
            building2_uuid: UUID للمبنى الثاني

        Returns:
            معلومات التقارب والتداخل
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

        # Calculate distance
        point1 = building1.point or (building1.polygon.get_centroid() if building1.polygon else None)
        point2 = building2.point or (building2.polygon.get_centroid() if building2.polygon else None)

        if point1 and point2:
            result["distance_meters"] = self._haversine_distance(point1, point2)

        return result

    # ==================== GeoJSON Export ====================

    def export_to_geojson(
        self,
        buildings: List[BuildingGeoData],
        include_properties: bool = True
    ) -> Dict:
        """
        تصدير المباني إلى GeoJSON.

        Args:
            buildings: قائمة BuildingGeoData
            include_properties: تضمين الخصائص

        Returns:
            GeoJSON FeatureCollection
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

    # ==================== Validation ====================

    def validate_coordinates(
        self,
        latitude: float,
        longitude: float
    ) -> Tuple[bool, str]:
        """
        التحقق من صحة الإحداثيات (ضمن نطاق حلب).

        Args:
            latitude: خط العرض
            longitude: خط الطول

        Returns:
            (is_valid, error_message)
        """
        if latitude < self.ALEPPO_BOUNDS["min_lat"] or latitude > self.ALEPPO_BOUNDS["max_lat"]:
            return False, "الإحداثيات خارج نطاق حلب (خط العرض)"

        if longitude < self.ALEPPO_BOUNDS["min_lon"] or longitude > self.ALEPPO_BOUNDS["max_lon"]:
            return False, "الإحداثيات خارج نطاق حلب (خط الطول)"

        return True, ""

    # ==================== Helper Methods ====================

    def _convert_api_building_to_model(self, data: Dict[str, Any]) -> Building:
        """تحويل API response إلى Building model."""
        return Building(
            building_uuid=data["id"],
            building_id=data.get("buildingId", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            building_status=data.get("status"),
            building_type=data.get("buildingType", 1),
            number_of_units=data.get("numberOfPropertyUnits", 0),
            # Add more fields as needed
        )

    def _convert_api_building_to_geodata(self, data: Dict[str, Any]) -> BuildingGeoData:
        """تحويل API response إلى BuildingGeoData."""
        point = None
        polygon = None

        if data.get("latitude") and data.get("longitude"):
            point = GeoPoint(
                latitude=data["latitude"],
                longitude=data["longitude"]
            )

        if data.get("buildingGeometryWkt"):
            polygon = GeoPolygon.from_wkt(data["buildingGeometryWkt"])

        return BuildingGeoData(
            building_uuid=data["id"],
            building_id=data.get("buildingId", ""),
            geometry_type="polygon" if polygon else "point",
            point=point,
            polygon=polygon,
            neighborhood_code=data.get("neighborhoodCode", ""),
            status=data.get("status", ""),
            properties={
                "building_type": data.get("buildingType"),
                "number_of_units": data.get("numberOfPropertyUnits", 0)
            }
        )

    def _fetch_buildings_as_geodata(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float
    ) -> List[BuildingGeoData]:
        """جلب المباني كـ BuildingGeoData."""
        print(f"[DEBUG] _fetch_buildings_as_geodata: NE({north_east_lat}, {north_east_lng}) SW({south_west_lat}, {south_west_lng})")
        buildings_data = self.api.get_buildings_for_map(
            north_east_lat, north_east_lng,
            south_west_lat, south_west_lng
        )
        print(f"[DEBUG] API returned {len(buildings_data)} buildings")

        result = [self._convert_api_building_to_geodata(b) for b in buildings_data]
        print(f"[DEBUG] Converted to {len(result)} BuildingGeoData objects")
        return result

    def _haversine_distance(self, point1: GeoPoint, point2: GeoPoint) -> float:
        """حساب المسافة بين نقطتين (Haversine formula)."""
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
        """التحقق من وجود نقطة داخل مضلع (ray casting)."""
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
