# -*- coding: utf-8 -*-
"""
TRRCMS API Client - للاتصال بالـ Backend API
==================================================

يوفر وصولاً كاملاً لجميع endpoints الخاصة بالخريطة والمباني.
"""

import requests
import urllib3
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from utils.logger import get_logger

# Suppress SSL warnings for self-signed certificates in development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


@dataclass
class ApiConfig:
    """
    تكوين الاتصال بالـ API.

    ✅ DYNAMIC: Reads from .env file via Config
    🔧 TEAM READY: Each member sets their own API_BASE_URL in .env

    Example .env:
        API_BASE_URL=http://192.168.100.221:8080  # Team member's .env
        API_USERNAME=admin
        API_PASSWORD=Admin@123
    """
    base_url: str = None  # Will be loaded from Config
    username: str = None  # Will be loaded from Config
    password: str = None  # Will be loaded from Config
    timeout: int = 30

    def __post_init__(self):
        """Load from Config if not provided."""
        # ✅ Load from Config (which reads from .env)
        if self.base_url is None or self.username is None or self.password is None:
            from app.config import Config

            if self.base_url is None:
                self.base_url = Config.API_BASE_URL
            if self.username is None:
                self.username = Config.API_USERNAME
            if self.password is None:
                self.password = Config.API_PASSWORD
            if self.timeout == 30:  # if default
                self.timeout = Config.API_TIMEOUT


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
                f"{self.base_url}/v1/Auth/login",
                json={"username": username, "password": password},
                timeout=self.config.timeout,
                verify=False  # Allow self-signed certificates in development
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
                f"{self.base_url}/v1/Auth/refresh",
                json={"refreshToken": self.refresh_token},
                timeout=self.config.timeout,
                verify=False  # Allow self-signed certificates in development
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
            endpoint: API endpoint (e.g., "/v1/Buildings/map")
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
                timeout=self.config.timeout,
                verify=False  # Allow self-signed certificates in development
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
        buildings = self._request("POST", "/v1/Buildings/map", json_data=payload)
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
        response = self._request("POST", "/v1/Buildings/polygon", json_data=payload)

        # API returns: {"buildings": [...], "totalCount": N, "page": 1, ...}
        buildings = response.get("buildings", [])
        total_count = response.get("totalCount", 0)

        logger.info(f"✅ Fetched {len(buildings)} buildings (total: {total_count}) from polygon API")

        if buildings:
            sample = buildings[0]
            has_geometry_wkt = "buildingGeometryWkt" in sample
            logger.debug(f"[API Response] Sample building keys: {list(sample.keys())[:10]}")
            logger.debug(f"[API Response] Has 'buildingGeometryWkt': {has_geometry_wkt}")
            if has_geometry_wkt and sample.get("buildingGeometryWkt"):
                logger.debug(f"[API Response] Sample WKT: {sample.get('buildingGeometryWkt')[:80]}...")

        return buildings

    def search_buildings_for_assignment(
        self,
        polygon_wkt: str,
        has_active_assignment: Optional[bool] = None,
        survey_status: Optional[str] = None,
        governorate_code: Optional[str] = None,
        subdistrict_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        البحث عن المباني داخل polygon لـ Building Assignment (API الصحيح).

        ✅ CORRECT API: /api/v1/BuildingAssignments/buildings/search
        هذا هو الـ endpoint الصحيح لـ Building Assignment workflow!

        Args:
            polygon_wkt: Polygon في صيغة WKT
                        Example: "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
            has_active_assignment: فلتر حسب وجود assignment نشط (optional)
                                  True: فقط المباني المُعيّنة
                                  False: فقط المباني غير المُعيّنة
                                  None: جميع المباني
            survey_status: فلتر حالة المسح (optional)
                          not_surveyed, in_progress, completed, verified, etc.
            governorate_code: كود المحافظة (optional)
            subdistrict_code: كود المنطقة الفرعية (optional)
            page: رقم الصفحة (default: 1)
            page_size: عدد النتائج في الصفحة (default: 100)

        Returns:
            {
                "items": [...],  # List of BuildingDto
                "totalCount": int,
                "page": int,
                "pageSize": int,
                "totalPages": int,
                "polygonWkt": str,
                "polygonAreaSquareMeters": float
            }

        Example:
            # البحث عن مباني غير مُعيّنة في polygon
            result = client.search_buildings_for_assignment(
                polygon_wkt="POLYGON((37.0 36.1, 37.3 36.1, 37.3 36.3, 37.0 36.3, 37.0 36.1))",
                has_active_assignment=False,
                page=1,
                page_size=100
            )
            buildings = result.get("items", [])
        """
        # Parse WKT to coordinates array [[lng, lat], ...]
        # WKT format: "POLYGON((lon1 lat1, lon2 lat2, ...))"
        try:
            # Extract coordinates from WKT
            coords_str = polygon_wkt.replace("POLYGON((", "").replace("))", "")
            coord_pairs = coords_str.split(", ")
            coordinates = []
            for pair in coord_pairs:
                lon, lat = pair.split(" ")
                coordinates.append([float(lon), float(lat)])

            logger.debug(f"Parsed {len(coordinates)} coordinates from WKT")
        except Exception as e:
            logger.error(f"Failed to parse polygon WKT: {e}")
            raise ValueError(f"Invalid polygon WKT format: {polygon_wkt}")

        payload = {
            "coordinates": coordinates,
            "governorateCode": governorate_code or "01",  # Default: Aleppo
            "page": page,
            "pageSize": page_size
        }

        # Add optional filters
        if has_active_assignment is not None:
            payload["hasActiveAssignment"] = has_active_assignment

        if survey_status:
            payload["surveyStatus"] = survey_status

        if subdistrict_code:
            payload["subdistrictCode"] = subdistrict_code

        # ✅ DETAILED LOGGING: Print full request payload
        print(f"\n{'='*80}")
        print(f"🔍 POLYGON SEARCH API CALL (BuildingAssignments)")
        print(f"{'='*80}")
        print(f"📊 Parsed {len(coordinates)} coordinates from WKT")
        print(f"📐 Coordinates array (first 3): {coordinates[:3]}")
        print(f"📋 Full Request Payload:")
        import json
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"{'='*80}\n")

        logger.debug(f"Searching buildings for assignment: governorateCode=01, page={page}, pageSize={page_size}, hasActiveAssignment={has_active_assignment}")
        response = self._request("POST", "/v1/BuildingAssignments/buildings/search", json_data=payload)

        # API returns paginated response
        items = response.get("items", [])
        total_count = response.get("totalCount", 0)

        logger.info(f"✅ Found {len(items)} buildings for assignment (total: {total_count}) using BuildingAssignments API")

        return response

    def get_buildings_for_assignment(
        self,
        governorate_code: Optional[str] = None,
        subdistrict_code: Optional[str] = None,
        survey_status: Optional[str] = None,
        has_active_assignment: Optional[bool] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        ✅ الحصول على المباني للتعيين مع دعم الفلاتر (بدون polygon).

        هذا هو الـ endpoint المُخصص لـ Field Assignment مع فلاتر!
        لا يحتاج polygon - مناسب تماماً للـ Step 1 filters.

        Args:
            governorate_code: كود المحافظة (optional)
            subdistrict_code: كود المنطقة الفرعية (optional)
            survey_status: فلتر حالة المسح (optional)
                          not_surveyed, in_progress, completed, verified, etc.
            has_active_assignment: فلتر حسب وجود assignment نشط (optional)
                                  True: فقط المباني المُعيّنة
                                  False: فقط المباني غير المُعيّنة
                                  None: جميع المباني
            page: رقم الصفحة (default: 1)
            page_size: عدد النتائج في الصفحة (default: 100)

        Returns:
            {
                "items": [...],  # List of BuildingDto
                "totalCount": int,
                "page": int,
                "pageSize": int,
                "totalPages": int
            }

        Example:
            # بحث عن مباني غير مُعيّنة في محافظة حلب
            result = client.get_buildings_for_assignment(
                governorate_code="01",
                has_active_assignment=False,
                page=1,
                page_size=100
            )
            buildings = result.get("items", [])

        Endpoint: GET /api/v1/BuildingAssignment/buildings
        """
        params = {
            "page": page,
            "pageSize": page_size
        }

        # Add optional filters
        if governorate_code:
            params["governorateCode"] = governorate_code

        if subdistrict_code:
            params["subdistrictCode"] = subdistrict_code

        if survey_status:
            params["surveyStatus"] = survey_status

        if has_active_assignment is not None:
            params["hasActiveAssignment"] = str(has_active_assignment).lower()

        # ✅ DETAILED LOGGING
        print(f"\n{'='*80}")
        print(f"🔍 FILTER-BASED SEARCH API CALL (BuildingAssignment/buildings)")
        print(f"{'='*80}")
        print(f"📋 Query Parameters:")
        import json
        print(json.dumps(params, indent=2, ensure_ascii=False))
        print(f"{'='*80}\n")

        logger.debug(f"Fetching buildings for assignment with filters: {params}")
        response = self._request("GET", "/v1/BuildingAssignment/buildings", params=params)

        # API returns paginated response
        items = response.get("items", [])
        total_count = response.get("totalCount", 0)

        logger.info(f"✅ Found {len(items)} buildings for assignment (total: {total_count}) using filter API")

        return response

    def get_building_by_id(self, building_id: str) -> Dict[str, Any]:
        """
        الحصول على تفاصيل مبنى محدد.

        Args:
            building_id: UUID للمبنى

        Returns:
            BuildingDto
        """
        return self._request("GET", f"/v1/Buildings/{building_id}")

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
            payload["buildingGeometryWkt"] = building_geometry_wkt

        if not payload:
            raise ValueError("At least one geometry field must be provided")

        logger.info(f"Updating geometry for building {building_id}")
        result = self._request(
            "PUT",
            f"/v1/Buildings/{building_id}/geometry",
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

        return self._request("POST", "/v1/Buildings/search", json_data=payload)

    def create_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        إنشاء مبنى جديد.

        Args:
            building_data: بيانات المبنى (CreateBuildingCommand)

        Returns:
            BuildingDto المُنشأ
        """
        result = self._request("POST", "/v1/Buildings", json_data=building_data)
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
        return self._request("GET", f"/v1/PropertyUnits/building/{building_id}")

    # ==================== Utility ====================

    def health_check(self) -> bool:
        """
        فحص حالة الاتصال بالـ API.

        Returns:
            True إذا كان الاتصال يعمل
        """
        try:
            # Try to get current user info as health check
            self._request("GET", "/v1/Auth/me")
            logger.info("✅ API health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ API health check failed: {e}")
            return False

    def get_current_user(self) -> Dict[str, Any]:
        """الحصول على معلومات المستخدم الحالي."""
        return self._request("GET", "/v1/Auth/me")

    # ==================== Building Assignments API ====================

    def create_assignment(
        self,
        building_ids: List[str],
        assigned_to: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        إنشاء تعيين مباني لباحث ميداني.

        Args:
            building_ids: قائمة UUIDs للمباني
            assigned_to: User ID للباحث الميداني
            notes: ملاحظات إضافية

        Returns:
            Assignment response من API

        Endpoint: POST /api/v1/BuildingAssignments
        """
        payload = {
            "buildingIds": building_ids,
            "assignedTo": assigned_to,
            "notes": notes
        }

        logger.info(f"Creating assignment for {len(building_ids)} buildings → researcher: {assigned_to}")
        return self._request("POST", "/v1/BuildingAssignments", json_data=payload)

    def get_assignment(self, assignment_id: str) -> Dict[str, Any]:
        """
        جلب تفاصيل تعيين محدد.

        Args:
            assignment_id: UUID للتعيين

        Returns:
            Assignment details

        Endpoint: GET /api/v1/BuildingAssignments/{id}
        """
        return self._request("GET", f"/v1/BuildingAssignments/{assignment_id}")

    def get_pending_assignments(
        self,
        researcher_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        جلب التعيينات المعلقة (جاهزة للنقل).

        Args:
            researcher_id: User ID للباحث (optional - لجلب مهام باحث محدد)
            page: رقم الصفحة
            page_size: عدد النتائج

        Returns:
            Paginated list of pending assignments

        Endpoint: GET /api/v1/BuildingAssignments/pending
        """
        params = {
            "page": page,
            "pageSize": page_size
        }
        if researcher_id:
            params["researcherId"] = researcher_id

        return self._request("GET", "/v1/BuildingAssignments/pending", params=params)

    def update_assignment_transfer_status(
        self,
        assignment_id: str,
        transfer_status: str,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        تحديث حالة نقل التعيين.

        Args:
            assignment_id: UUID للتعيين
            transfer_status: الحالة (not_transferred, transferring, transferred, failed)
            device_id: Device/Tablet ID (optional)

        Returns:
            Updated assignment

        Endpoint: PUT /api/v1/BuildingAssignments/{id}/transfer-status
        """
        payload = {
            "transferStatus": transfer_status,
            "deviceId": device_id
        }

        logger.info(f"Updating assignment {assignment_id} transfer status → {transfer_status}")
        return self._request(
            "PUT",
            f"/v1/BuildingAssignments/{assignment_id}/transfer-status",
            json_data=payload
        )

    def get_assignment_statistics(self) -> Dict[str, Any]:
        """
        جلب إحصائيات التعيينات.

        Returns:
            Statistics object {total, pending, transferred, by_researcher, etc.}

        Endpoint: GET /api/v1/BuildingAssignments/statistics
        """
        return self._request("GET", "/v1/BuildingAssignments/statistics")

    # ==================== PropertyUnits APIs ====================

    def create_property_unit(self, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new property unit via API.

        Args:
            unit_data: Property unit data (snake_case or camelCase supported)
                - building_id/buildingId: Building UUID
                - unit_number/unitNumber: Unit identifier
                - unit_type/unitType: Type code (1=Apartment, 2=Shop, etc.)
                - floor_number/floorNumber (optional)
                - owner_name/ownerName (optional)
                - occupancy_status/occupancyStatus (optional)
                - Other fields as needed

        Returns:
            Created property unit data with id
        """
        api_data = self._convert_property_unit_to_api_format(unit_data)
        logger.info(f"Creating property unit: {api_data.get('unitNumber', 'N/A')}")
        result = self._request("POST", "/v1/PropertyUnits", json_data=api_data)
        logger.info(f"Property unit created: {result.get('id', 'N/A')}")
        return result

    def update_property_unit(self, unit_id: str, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing property unit.

        Args:
            unit_id: Property unit UUID
            unit_data: Fields to update

        Returns:
            Updated property unit data
        """
        api_data = self._convert_property_unit_to_api_format(unit_data)
        result = self._request("PUT", f"/v1/PropertyUnits/{unit_id}", json_data=api_data)
        logger.info(f"Property unit updated: {unit_id}")
        return result

    def _convert_property_unit_to_api_format(self, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert property unit data to API format (camelCase)."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return unit_data.get(snake_key) or unit_data.get(camel_key) or default

        api_data = {
            "buildingId": get_value('building_id', 'buildingId', ''),
            "unitNumber": get_value('unit_number', 'unitNumber', ''),
            "unitType": get_value('unit_type', 'unitType'),
            "floorNumber": get_value('floor_number', 'floorNumber'),
            "ownerName": get_value('owner_name', 'ownerName', ''),
            "ownerNameAr": get_value('owner_name_ar', 'ownerNameAr', ''),
            "tenantName": get_value('tenant_name', 'tenantName', ''),
            "occupancyStatus": get_value('occupancy_status', 'occupancyStatus'),
            "numberOfRooms": get_value('number_of_rooms', 'numberOfRooms'),
            "areaSquareMeters": get_value('area_square_meters', 'areaSquareMeters'),
            "hasElectricity": get_value('has_electricity', 'hasElectricity'),
            "hasWater": get_value('has_water', 'hasWater'),
            "hasSewage": get_value('has_sewage', 'hasSewage'),
            "notes": get_value('notes', 'notes', ''),
            "surveyId": get_value('survey_id', 'surveyId')
        }
        return {k: v for k, v in api_data.items() if v is not None}

    # ==================== Households APIs ====================

    def create_household(self, household_data: Dict[str, Any], survey_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new household via API.

        Args:
            household_data: Household data (snake_case or camelCase supported)
                - property_unit_id/propertyUnitId: Property unit UUID
                - head_name/headOfHouseholdName: Head of household name
                - size/householdSize: Number of members
                - Other demographic fields (optional)
            survey_id: Optional survey UUID

        Returns:
            Created household data with id
        """
        api_data = self._convert_household_to_api_format(household_data, survey_id)
        endpoint = f"/v1/Surveys/{survey_id}/households" if survey_id else "/v1/Households"

        logger.info(f"Creating household: {api_data.get('headOfHouseholdName', 'N/A')}")
        result = self._request("POST", endpoint, json_data=api_data)
        logger.info(f"Household created: {result.get('id', 'N/A')}")
        return result

    def get_households_for_unit(self, unit_id: str) -> List[Dict[str, Any]]:
        """
        Get all households for a property unit.

        Args:
            unit_id: Property unit UUID

        Returns:
            List of household dictionaries
        """
        if not unit_id:
            logger.warning("No unit_id provided")
            return []

        try:
            result = self._request("GET", f"/v1/Households/unit/{unit_id}")

            if isinstance(result, list):
                households = result
            elif isinstance(result, dict):
                households = result.get("data") or result.get("households") or result.get("items") or []
            else:
                logger.warning(f"Unexpected response format: {type(result)}")
                return []

            logger.info(f"Found {len(households)} households for unit {unit_id}")
            return households if isinstance(households, list) else []

        except Exception as e:
            logger.error(f"Failed to fetch households: {e}")
            return []

    def _convert_household_to_api_format(self, household_data: Dict[str, Any], survey_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert household data to API format (camelCase)."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return household_data.get(snake_key) or household_data.get(camel_key) or default

        api_data = {
            "propertyUnitId": get_value('property_unit_id', 'propertyUnitId', ''),
            "headOfHouseholdName": get_value('head_name', 'headOfHouseholdName', ''),
            "householdSize": int(get_value('size', 'householdSize', 0)),
            "maleCount": int(get_value('adult_males', 'maleCount', 0)),
            "femaleCount": int(get_value('adult_females', 'femaleCount', 0)),
            "maleChildCount": int(get_value('male_children_under18', 'maleChildCount', 0)),
            "femaleChildCount": int(get_value('female_children_under18', 'femaleChildCount', 0)),
            "maleElderlyCount": int(get_value('male_elderly_over65', 'maleElderlyCount', 0)),
            "femaleElderlyCount": int(get_value('female_elderly_over65', 'femaleElderlyCount', 0)),
            "maleDisabledCount": int(get_value('disabled_males', 'maleDisabledCount', 0)),
            "femaleDisabledCount": int(get_value('disabled_females', 'femaleDisabledCount', 0)),
            "notes": get_value('notes', 'notes', '')
        }
        if survey_id:
            api_data["surveyId"] = survey_id
        return api_data

    # ==================== Persons APIs ====================

    def create_person(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new person via API.

        Args:
            person_data: Person data (snake_case or camelCase supported)
                - full_name/fullName: Person's full name
                - full_name_ar/fullNameAr: Arabic name
                - national_id/nationalId: National ID number
                - household_id/householdId: Link to household (optional)
                - Other fields as needed

        Returns:
            Created person data with id
        """
        api_data = self._convert_person_to_api_format(person_data)
        logger.info(f"Creating person: {api_data.get('fullName', 'N/A')}")
        result = self._request("POST", "/v1/Persons", json_data=api_data)
        logger.info(f"Person created: {result.get('id', 'N/A')}")
        return result

    def _convert_person_to_api_format(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert person data to API format (camelCase)."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return person_data.get(snake_key) or person_data.get(camel_key) or default

        api_data = {
            "fullName": get_value('full_name', 'fullName', ''),
            "fullNameAr": get_value('full_name_ar', 'fullNameAr', ''),
            "nationalId": get_value('national_id', 'nationalId', ''),
            "householdId": get_value('household_id', 'householdId'),
            "dateOfBirth": get_value('date_of_birth', 'dateOfBirth'),
            "gender": get_value('gender', 'gender'),
            "relationshipToHead": get_value('relationship_to_head', 'relationshipToHead'),
            "phoneNumber": get_value('phone_number', 'phoneNumber', ''),
            "email": get_value('email', 'email', ''),
            "notes": get_value('notes', 'notes', '')
        }
        return {k: v for k, v in api_data.items() if v is not None}

    # ==================== Surveys APIs ====================

    def create_survey(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new survey via API.

        Args:
            survey_data: Survey data (snake_case or camelCase supported)
                - building_id/buildingId: Building UUID
                - surveyor_id/surveyorId: Surveyor user UUID
                - survey_date/surveyDate: Date of survey
                - Other fields as needed

        Returns:
            Created survey data with id
        """
        api_data = self._convert_survey_to_api_format(survey_data)
        logger.info(f"Creating survey for building: {api_data.get('buildingId', 'N/A')}")
        result = self._request("POST", "/v1/Surveys", json_data=api_data)
        logger.info(f"Survey created: {result.get('id', 'N/A')}")
        return result

    def _convert_survey_to_api_format(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert survey data to API format (camelCase)."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return survey_data.get(snake_key) or survey_data.get(camel_key) or default

        api_data = {
            "buildingId": get_value('building_id', 'buildingId', ''),
            "surveyorId": get_value('surveyor_id', 'surveyorId', ''),
            "surveyDate": get_value('survey_date', 'surveyDate'),
            "surveyStatus": get_value('survey_status', 'surveyStatus'),
            "notes": get_value('notes', 'notes', '')
        }
        return {k: v for k, v in api_data.items() if v is not None}

    # ==================== Neighborhoods APIs ====================

    def get_neighborhoods_by_bounds(self, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> List[Dict[str, Any]]:
        """
        Get neighborhoods visible in map viewport.

        Args:
            sw_lat: Southwest corner latitude
            sw_lng: Southwest corner longitude
            ne_lat: Northeast corner latitude
            ne_lng: Northeast corner longitude

        Returns:
            List of neighborhoods with boundaries (WKT format)
        """
        params = {"swLat": sw_lat, "swLng": sw_lng, "neLat": ne_lat, "neLng": ne_lng}
        logger.info(f"Fetching neighborhoods in viewport: [{sw_lat:.4f},{sw_lng:.4f} - {ne_lat:.4f},{ne_lng:.4f}]")
        neighborhoods = self._request("GET", "/v1/Neighborhoods/by-bounds", params=params)
        logger.info(f"Fetched {len(neighborhoods)} neighborhoods")
        return neighborhoods

    def get_neighborhood_by_point(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get neighborhood containing a given point (reverse geocoding).

        Args:
            latitude: Point latitude
            longitude: Point longitude

        Returns:
            Neighborhood data or None if point is outside all neighborhoods
        """
        params = {"latitude": latitude, "longitude": longitude}
        logger.debug(f"Finding neighborhood at ({latitude:.6f}, {longitude:.6f})")

        try:
            neighborhood = self._request("GET", "/v1/Neighborhoods/by-point", params=params)
            if neighborhood:
                logger.info(f"Found neighborhood: {neighborhood.get('nameArabic', 'N/A')}")
            return neighborhood
        except Exception as e:
            logger.warning(f"No neighborhood found at ({latitude}, {longitude}): {e}")
            return None

    def get_neighborhoods(self, governorate_code: Optional[str] = None, district_code: Optional[str] = None,
                         subdistrict_code: Optional[str] = None, community_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all neighborhoods with optional hierarchy filters.

        Args:
            governorate_code: Filter by governorate
            district_code: Filter by district
            subdistrict_code: Filter by sub-district
            community_code: Filter by community

        Returns:
            List of neighborhoods with full details
        """
        params = {}
        if governorate_code:
            params["governorateCode"] = governorate_code
        if district_code:
            params["districtCode"] = district_code
        if subdistrict_code:
            params["subDistrictCode"] = subdistrict_code
        if community_code:
            params["communityCode"] = community_code

        logger.info(f"Fetching neighborhoods with filters: {params or 'none'}")
        neighborhoods = self._request("GET", "/v1/Neighborhoods", params=params)
        logger.info(f"Fetched {len(neighborhoods)} neighborhoods")
        return neighborhoods

    def get_neighborhood_by_code(self, full_code: str) -> Optional[Dict[str, Any]]:
        """
        Get neighborhood by full 12-digit composite code.

        Args:
            full_code: 12-digit composite code (GGDDSSCCCCNNN)

        Returns:
            Neighborhood data or None if not found
        """
        try:
            neighborhood = self._request("GET", f"/v1/Neighborhoods/{full_code}")
            if neighborhood:
                logger.info(f"Found neighborhood: {neighborhood.get('nameArabic', 'N/A')}")
            return neighborhood
        except Exception as e:
            logger.warning(f"Neighborhood not found: {full_code}")
            return None


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
