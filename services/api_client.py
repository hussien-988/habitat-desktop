# -*- coding: utf-8 -*-
"""
TRRCMS API Client - للاتصال بالـ Backend API
==================================================

يوفر وصولاً كاملاً لجميع endpoints الخاصة بالخريطة والمباني.
"""

import requests
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ApiConfig:
    """تكوين الاتصال بالـ API"""
    base_url: str = "http://localhost:8080"  # Fixed: Changed from 8081 to 8080 (Docker Backend port)
    username: str = "admin"
    password: str = "Admin@123"
    timeout: int = 30


class TRRCMSApiClient:
    """
    عميل API للاتصال بـ TRRCMS Backend.

    الميزات:
    - تسجيل دخول تلقائي
    - إدارة Token
    - إعادة محاولة عند انتهاء Token
    - معالجة الأخطاء

    Usage:
        config = ApiConfig(base_url="http://localhost:8081")
        client = TRRCMSApiClient(config)
        buildings = client.get_buildings_for_map(36.5, 37.5, 36.0, 36.8)
    """

    def __init__(self, config: ApiConfig):
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

        # Login on initialization
        try:
            self.login(config.username, config.password)
            logger.info(f"✅ Connected to TRRCMS API at {self.base_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to API: {e}")
            raise

    # ==================== Authentication ====================

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        تسجيل الدخول والحصول على Token.

        Args:
            username: اسم المستخدم
            password: كلمة المرور

        Returns:
            بيانات المستخدم والـ Token
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/Auth/login",
                json={"username": username, "password": password},
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()
            self.access_token = data["accessToken"]
            self.refresh_token = data.get("refreshToken")

            # Calculate token expiration
            expires_in = data.get("expiresIn", 3600)  # default 1 hour
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"✅ Logged in as {username}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Login failed: {e}")
            raise

    def set_access_token(self, token: str, expires_in: int = 3600):
        """
        Set access token from external source (e.g., current_user._api_token).

        Professional Best Practice: Allow setting token from authenticated user session.

        Args:
            token: Access token to use
            expires_in: Token expiration time in seconds (default: 3600 = 1 hour)
        """
        self.access_token = token
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        logger.debug(f"✅ Access token updated externally (expires in {expires_in}s)")

    def refresh_access_token(self) -> bool:
        """
        تحديث الـ Access Token باستخدام Refresh Token.

        Returns:
            True إذا نجح التحديث
        """
        if not self.refresh_token:
            logger.warning("No refresh token available")
            return False

        try:
            response = requests.post(
                f"{self.base_url}/api/v1/Auth/refresh",
                json={"refreshToken": self.refresh_token},
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()
            self.access_token = data["accessToken"]
            self.refresh_token = data.get("refreshToken", self.refresh_token)

            expires_in = data.get("expiresIn", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info("✅ Token refreshed")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Token refresh failed: {e}")
            return False

    def _ensure_valid_token(self):
        """التأكد من صلاحية الـ Token قبل الطلب."""
        if not self.access_token:
            raise RuntimeError("Not authenticated")

        # Refresh token if it will expire in next 5 minutes
        if self.token_expires_at:
            time_until_expiry = (self.token_expires_at - datetime.now()).total_seconds()
            if time_until_expiry < 300:  # 5 minutes
                logger.info("Token expiring soon, refreshing...")
                if not self.refresh_access_token():
                    # Re-login if refresh fails
                    self.login(self.config.username, self.config.password)

    def _headers(self) -> Dict[str, str]:
        """الحصول على Headers مع Authorization."""
        self._ensure_valid_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Any:
        """
        تنفيذ HTTP request مع معالجة الأخطاء.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/api/v1/Buildings/map")
            json_data: JSON payload
            params: Query parameters

        Returns:
            Response JSON data
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                headers=self._headers(),
                timeout=self.config.timeout
            )
            response.raise_for_status()

            # Return JSON if available
            if response.text:
                return response.json()
            return None

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request failed: {e}")
            raise

    # ==================== Buildings - Map APIs ====================

    def get_buildings_for_map(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        الحصول على المباني للعرض على الخريطة (محسّن للأداء).

        Args:
            north_east_lat: حد الشمال الشرقي (latitude)
            north_east_lng: حد الشمال الشرقي (longitude)
            south_west_lat: حد الجنوب الغربي (latitude)
            south_west_lng: حد الجنوب الغربي (longitude)
            status: فلتر حسب حالة المبنى (optional)

        Returns:
            قائمة بـ BuildingMapDto

        Example:
            buildings = client.get_buildings_for_map(
                north_east_lat=36.5,
                north_east_lng=37.5,
                south_west_lat=36.0,
                south_west_lng=36.8
            )
        """
        payload = {
            "northEastLat": north_east_lat,
            "northEastLng": north_east_lng,
            "southWestLat": south_west_lat,
            "southWestLng": south_west_lng
        }

        if status:
            payload["status"] = status

        logger.debug(f"Fetching buildings for map: bbox={payload}")
        buildings = self._request("POST", "/api/v1/Buildings/map", json_data=payload)
        logger.info(f"✅ Fetched {len(buildings)} buildings from API")

        return buildings

    def get_buildings_in_polygon(
        self,
        polygon_wkt: str,
        status: Optional[str] = None,
        building_type: Optional[int] = None,
        damage_level: Optional[int] = None,
        page: int = 1,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        الحصول على المباني داخل polygon (محسّن للأداء مع PostGIS).

        Args:
            polygon_wkt: Polygon في صيغة WKT
            status: فلتر حسب حالة المبنى (optional)
            building_type: فلتر حسب نوع المبنى (optional)
            damage_level: فلتر حسب مستوى الضرر (optional)
            page: رقم الصفحة
            page_size: عدد النتائج في الصفحة

        Returns:
            قائمة بـ BuildingDto

        Example:
            buildings = client.get_buildings_in_polygon(
                polygon_wkt="POLYGON((37.0 36.1, 37.3 36.1, 37.3 36.3, 37.0 36.3, 37.0 36.1))",
                page=1,
                page_size=100
            )
        """
        payload = {
            "polygonWkt": polygon_wkt,
            "page": page,
            "pageSize": page_size
        }

        if status:
            payload["status"] = status
        if building_type is not None:
            payload["buildingType"] = building_type
        if damage_level is not None:
            payload["damageLevel"] = damage_level

        logger.debug(f"Fetching buildings in polygon: page={page}, pageSize={page_size}")
        response = self._request("POST", "/api/v1/Buildings/polygon", json_data=payload)

        # API returns: {"buildings": [...], "totalCount": N, "page": 1, ...}
        buildings = response.get("buildings", [])
        total_count = response.get("totalCount", 0)

        logger.info(f"✅ Fetched {len(buildings)} buildings (total: {total_count}) from polygon API")

        return buildings

    def get_building_by_id(self, building_id: str) -> Dict[str, Any]:
        """
        الحصول على تفاصيل مبنى محدد.

        Args:
            building_id: UUID للمبنى

        Returns:
            BuildingDto
        """
        return self._request("GET", f"/api/v1/Buildings/{building_id}")

    def update_building_geometry(
        self,
        building_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        building_geometry_wkt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        تحديث موقع المبنى (Point أو Polygon).

        Args:
            building_id: UUID للمبنى
            latitude: GPS latitude (optional)
            longitude: GPS longitude (optional)
            building_geometry_wkt: Polygon في صيغة WKT (optional)

        Returns:
            BuildingDto المُحدّث

        Example:
            # Update point location
            client.update_building_geometry(
                building_id="uuid",
                latitude=36.2021,
                longitude=37.1343
            )

            # Update with polygon
            client.update_building_geometry(
                building_id="uuid",
                building_geometry_wkt="POLYGON((37.13 36.20, 37.14 36.20, ...))"
            )
        """
        payload = {}

        if latitude is not None:
            payload["latitude"] = latitude
        if longitude is not None:
            payload["longitude"] = longitude
        if building_geometry_wkt is not None:
            payload["geometryWkt"] = building_geometry_wkt

        if not payload:
            raise ValueError("At least one geometry field must be provided")

        logger.info(f"Updating geometry for building {building_id}")
        result = self._request(
            "PUT",
            f"/api/v1/Buildings/{building_id}/geometry",
            json_data=payload
        )
        logger.info(f"✅ Geometry updated for building {building_id}")

        return result

    def search_buildings(
        self,
        building_id: Optional[str] = None,
        neighborhood_code: Optional[str] = None,
        building_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        البحث عن المباني بمعايير متعددة.

        Args:
            building_id: رمز المبنى (17 رقم)
            neighborhood_code: رمز الحي
            building_status: حالة المبنى
            page: رقم الصفحة
            page_size: عدد النتائج في الصفحة

        Returns:
            نتائج البحث مع pagination
        """
        payload = {
            "page": page,
            "pageSize": page_size
        }

        if building_id:
            payload["buildingId"] = building_id
        if neighborhood_code:
            payload["neighborhoodCode"] = neighborhood_code
        if building_status:
            payload["buildingStatus"] = building_status

        return self._request("POST", "/api/v1/Buildings/search", json_data=payload)

    def create_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        إنشاء مبنى جديد.

        Args:
            building_data: بيانات المبنى (CreateBuildingCommand)

        Returns:
            BuildingDto المُنشأ
        """
        result = self._request("POST", "/api/v1/Buildings", json_data=building_data)
        logger.info(f"✅ Created building: {result.get('buildingId')}")
        return result

    # ==================== Property Units ====================

    def get_property_units_by_building(self, building_id: str) -> List[Dict[str, Any]]:
        """
        الحصول على الوحدات العقارية لمبنى معين.

        Args:
            building_id: UUID للمبنى

        Returns:
            قائمة بالوحدات العقارية
        """
        return self._request("GET", f"/api/v1/PropertyUnits/building/{building_id}")

    # ==================== Utility ====================

    def health_check(self) -> bool:
        """
        فحص حالة الاتصال بالـ API.

        Returns:
            True إذا كان الاتصال يعمل
        """
        try:
            # Try to get current user info as health check
            self._request("GET", "/api/v1/Auth/me")
            logger.info("✅ API health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ API health check failed: {e}")
            return False

    def get_current_user(self) -> Dict[str, Any]:
        """الحصول على معلومات المستخدم الحالي."""
        return self._request("GET", "/api/v1/Auth/me")


# ==================== Singleton Instance ====================

_api_client_instance: Optional[TRRCMSApiClient] = None


def get_api_client(config: Optional[ApiConfig] = None) -> TRRCMSApiClient:
    """
    الحصول على instance واحد من ApiClient (Singleton).

    Args:
        config: تكوين API (يُستخدم فقط في المرة الأولى)

    Returns:
        TRRCMSApiClient instance
    """
    global _api_client_instance

    if _api_client_instance is None:
        if config is None:
            config = ApiConfig()
        _api_client_instance = TRRCMSApiClient(config)

    return _api_client_instance


def reset_api_client():
    """إعادة تعيين الـ API client (للاختبار)."""
    global _api_client_instance
    _api_client_instance = None
