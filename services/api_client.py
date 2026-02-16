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
from services.exceptions import ApiException, NetworkException

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
API للاتصال بـ TRRCMS Backend.

    الميزات:
    - تسجيل دخول تلقائي
    - إدارة Token
    - إعادة محاولة عند انتهاء Token
    - معالجة الأخطاء

    Usage:
        config = ApiConfig(base_url="http://localhost:8080")
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

        # Log request
        import json as _json
        logger.info(f"[API REQ] {method} {endpoint}")
        if params:
            logger.info(f"[API REQ] Params: {params}")
        if json_data:
            try:
                logger.info(f"[API REQ] Body: {_json.dumps(json_data, indent=2, ensure_ascii=False, default=str)}")
            except Exception:
                logger.info(f"[API REQ] Body: {json_data}")

        try:
            response = requests.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                headers=self._headers(),
                timeout=self.config.timeout,
                verify=False
            )
            response.raise_for_status()

            result = None
            if response.text:
                result = response.json()

            # Log successful response
            logger.info(f"[API RES] {response.status_code} {endpoint}")
            if result:
                try:
                    res_str = _json.dumps(result, indent=2, ensure_ascii=False, default=str)
                    if len(res_str) > 1000:
                        logger.info(f"[API RES] Body (truncated): {res_str[:1000]}...")
                    else:
                        logger.info(f"[API RES] Body: {res_str}")
                except Exception:
                    logger.info(f"[API RES] Body: {result}")

            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            response_data = {}
            try:
                response_data = e.response.json() if e.response is not None else {}
            except (ValueError, AttributeError):
                pass
            response_text = ''
            try:
                response_text = e.response.text[:500] if e.response is not None else ''
            except Exception:
                pass
            logger.error(f"[API ERR] {status_code} {method} {endpoint} | Response: {response_data or response_text}")
            raise ApiException(
                message=str(e),
                status_code=status_code,
                response_data=response_data
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Network error: {endpoint} - {e}")
            raise NetworkException(
                message=str(e),
                original_error=e
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {endpoint} - {e}")
            raise NetworkException(
                message=str(e),
                original_error=e
            )

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

        logger.debug(f"Fetching buildings for assignment with filters: {params}")
        response = self._request("GET", "/v1/BuildingAssignments/buildings", params=params)

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
            payload["geometryWkt"] = building_geometry_wkt

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
        api_data = self._convert_building_to_api_format(building_data)
        logger.info(f"Creating building: {api_data.get('buildingId', 'N/A')}")
        result = self._request("POST", "/v1/Buildings", json_data=api_data)
        logger.info(f"✅ Created building: {result.get('buildingId')}")
        return result

    def update_building(self, building_id: str, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        تحديث مبنى موجود.

        Uses two independent API calls:
        1. PUT /v1/Buildings/{id} - UpdateBuildingCommand (general data)
        2. PUT /v1/Buildings/{id}/geometry - UpdateBuildingGeometryCommand (coordinates + polygon)

        Both are independent - if one fails, the other still runs.
        """
        result = None

        # Step 1: Update general building data (UpdateBuildingCommand)
        update_data = self._build_update_command(building_data)
        if update_data:
            try:
                logger.info(f"Step 1: Updating building data: {building_id}")
                logger.info(f"  Payload: {update_data}")
                result = self._request("PUT", f"/v1/Buildings/{building_id}", json_data=update_data)
                logger.info(f"✅ Step 1: Building data updated")
            except Exception as e:
                logger.warning(f"Step 1 failed: {e}")

        # Step 2: Update geometry separately (UpdateBuildingGeometryCommand)
        geo_wkt = building_data.get('geo_location') or building_data.get('buildingGeometryWkt')
        lat = building_data.get('latitude')
        lng = building_data.get('longitude')

        if geo_wkt or (lat is not None and lng is not None):
            try:
                logger.info(f"Step 2: Updating geometry: lat={lat}, lng={lng}, wkt={'YES' if geo_wkt else 'NO'}")
                result = self.update_building_geometry(
                    building_id=building_id,
                    latitude=lat,
                    longitude=lng,
                    building_geometry_wkt=geo_wkt
                )
                logger.info(f"✅ Step 2: Geometry updated")
            except Exception as e:
                logger.warning(f"Step 2 failed: {e}")

        if result is None:
            raise Exception(f"Both update steps failed for building {building_id}")

        return result

    def _build_update_command(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build UpdateBuildingCommand payload matching API schema."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return building_data.get(snake_key) or building_data.get(camel_key) or default

        api_data = {
            "buildingType": get_value('building_type', 'buildingType'),
            "buildingStatus": get_value('building_status', 'buildingStatus'),
            "numberOfPropertyUnits": get_value('number_of_units', 'numberOfPropertyUnits'),
            "numberOfApartments": get_value('number_of_apartments', 'numberOfApartments'),
            "numberOfShops": get_value('number_of_shops', 'numberOfShops'),
            "latitude": get_value('latitude', 'latitude'),
            "longitude": get_value('longitude', 'longitude'),
            "locationDescription": get_value('location_description', 'locationDescription', ''),
            "notes": get_value('notes', 'notes', ''),
        }
        return {k: v for k, v in api_data.items() if v is not None}

    def _convert_building_to_api_format(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert building data to API format (camelCase) - used for CREATE."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return building_data.get(snake_key) or building_data.get(camel_key) or default

        api_data = {
            "buildingId": get_value('building_id', 'buildingId', ''),
            "governorateCode": get_value('governorate_code', 'governorateCode', ''),
            "governorateName": get_value('governorate_name', 'governorateName', ''),
            "governorateNameAr": get_value('governorate_name_ar', 'governorateNameAr', ''),
            "districtCode": get_value('district_code', 'districtCode', ''),
            "districtName": get_value('district_name', 'districtName', ''),
            "districtNameAr": get_value('district_name_ar', 'districtNameAr', ''),
            "subDistrictCode": get_value('subdistrict_code', 'subDistrictCode', ''),
            "subDistrictName": get_value('subdistrict_name', 'subDistrictName', ''),
            "subDistrictNameAr": get_value('subdistrict_name_ar', 'subDistrictNameAr', ''),
            "communityCode": get_value('community_code', 'communityCode', ''),
            "communityName": get_value('community_name', 'communityName', ''),
            "communityNameAr": get_value('community_name_ar', 'communityNameAr', ''),
            "neighborhoodCode": get_value('neighborhood_code', 'neighborhoodCode', ''),
            "neighborhoodName": get_value('neighborhood_name', 'neighborhoodName', ''),
            "neighborhoodNameAr": get_value('neighborhood_name_ar', 'neighborhoodNameAr', ''),
            "buildingNumber": get_value('building_number', 'buildingNumber', ''),
            "buildingType": get_value('building_type', 'buildingType'),
            "buildingStatus": get_value('building_status', 'buildingStatus'),
            "numberOfFloors": get_value('number_of_floors', 'numberOfFloors'),
            "numberOfApartments": get_value('number_of_apartments', 'numberOfApartments'),
            "numberOfShops": get_value('number_of_shops', 'numberOfShops'),
            "numberOfUnits": get_value('number_of_units', 'numberOfUnits'),
            "latitude": get_value('latitude', 'latitude'),
            "longitude": get_value('longitude', 'longitude'),
            "buildingGeometryWkt": get_value('geo_location', 'buildingGeometryWkt'),
            "generalDescription": get_value('general_description', 'generalDescription', ''),
            "locationDescription": get_value('location_description', 'locationDescription', ''),
            "notes": get_value('notes', 'notes', '')
        }
        # Remove None values
        return {k: v for k, v in api_data.items() if v is not None}

    def delete_building(self, building_id: str) -> bool:
        """
        حذف مبنى.

        Args:
            building_id: UUID للمبنى

        Returns:
            True إذا تم الحذف بنجاح
        """
        logger.info(f"Deleting building: {building_id}")
        self._request("DELETE", f"/v1/Buildings/{building_id}")
        logger.info(f"✅ Building deleted: {building_id}")
        return True

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
        """Convert property unit data to API format (camelCase).

        API Schema (CreatePropertyUnitCommand):
            buildingId: uuid (REQUIRED)
            unitIdentifier: string max 50 (REQUIRED)
            unitType: int 1-5 (REQUIRED)
            status: int 1-6 or 99 (REQUIRED)
            floorNumber: int -5 to 200 (optional)
            areaSquareMeters: double > 0 (optional)
            numberOfRooms: int 0-100 (optional)
            description: string max 2000 (optional)
        """
        def get_value(snake_key: str, camel_key: str, default=None):
            return unit_data.get(snake_key) or unit_data.get(camel_key) or default

        # buildingId must be UUID - try multiple field names
        building_id = get_value('building_uuid', 'buildingId', None)
        if not building_id:
            logger.warning("No building UUID found in unit data - buildingId will be missing")

        api_data = {
            "buildingId": building_id,
            # unitIdentifier: unique within building (was unitNumber)
            "unitIdentifier": get_value('unit_number', 'unitIdentifier') or get_value('apartment_number', 'unitNumber', ''),
            "unitType": get_value('unit_type', 'unitType'),
            "status": get_value('status', 'status') or get_value('apartment_status', 'apartmentStatus', 1),
            "floorNumber": get_value('floor_number', 'floorNumber'),
            "areaSquareMeters": get_value('area_sqm', 'areaSquareMeters') or get_value('area_square_meters', 'areaSquareMeters'),
            "numberOfRooms": get_value('number_of_rooms', 'numberOfRooms'),
            "description": get_value('property_description', 'description') or get_value('notes', 'notes'),
        }
        # Filter None and empty strings - don't send invalid values to API
        return {k: v for k, v in api_data.items() if v is not None and v != ''}

    def link_unit_to_survey(self, survey_id: str, unit_id: str) -> Dict[str, Any]:
        """
        Link an existing property unit to a survey.

        Args:
            survey_id: Survey UUID
            unit_id: Property Unit UUID

        Returns:
            Updated survey data

        Endpoint: POST /api/v1/Surveys/{surveyId}/property-units/{unitId}/link
        """
        if not survey_id or not unit_id:
            raise ValueError("survey_id and unit_id are required")

        logger.info(f"Linking unit {unit_id} to survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/{survey_id}/property-units/{unit_id}/link")
        logger.info(f"Unit linked successfully")
        return result

    def get_all_property_units(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get all property units.

        Args:
            limit: Maximum number of units to return (not enforced by API)

        Returns:
            List of property unit dictionaries

        Endpoint: GET /api/v1/PropertyUnits
        """
        logger.info("Fetching all property units")
        result = self._request("GET", "/v1/PropertyUnits")

        if isinstance(result, list):
            units = result
        elif isinstance(result, dict):
            units = result.get("data") or result.get("units") or result.get("items") or []
        else:
            logger.warning(f"Unexpected response format: {type(result)}")
            return []

        logger.info(f"Fetched {len(units)} property units")
        return units if isinstance(units, list) else []

    def get_units_for_building(self, building_id: str) -> List[Dict[str, Any]]:
        """
        Get all property units for a building.

        Args:
            building_id: Building UUID

        Returns:
            List of property unit dictionaries

        Endpoint: GET /api/v1/PropertyUnits/building/{buildingId}
        """
        if not building_id:
            logger.warning("No building_id provided")
            return []

        logger.info(f"Fetching units for building: {building_id}")
        result = self._request("GET", f"/v1/PropertyUnits/building/{building_id}")

        if isinstance(result, list):
            units = result
        elif isinstance(result, dict):
            units = result.get("data") or result.get("units") or result.get("items") or []
        else:
            logger.warning(f"Unexpected response format: {type(result)}")
            return []

        logger.info(f"Fetched {len(units)} units for building {building_id}")
        return units if isinstance(units, list) else []

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

        logger.info(f"Creating household via {endpoint}: propertyUnitId={api_data.get('propertyUnitId')}, size={api_data.get('householdSize')}")
        result = self._request("POST", endpoint, json_data=api_data)
        logger.info(f"Household created: {result.get('id', 'N/A')}")
        return result

    def update_household(self, household_id: str, household_data: Dict[str, Any], survey_id: str) -> Dict[str, Any]:
        """Update an existing household via API."""
        api_data = self._convert_household_to_api_format(household_data, survey_id)
        api_data["surveyId"] = survey_id
        api_data["householdId"] = household_id

        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}"
        logger.info(f"Updating household {household_id} via {endpoint}")
        result = self._request("PUT", endpoint, json_data=api_data)
        logger.info(f"Household {household_id} updated successfully")
        return result

    def delete_household(self, household_id: str, survey_id: str) -> bool:
        """Delete a household via API. DELETE /api/v1/Surveys/{surveyId}/households/{householdId}"""
        if not household_id or not survey_id:
            raise ValueError("household_id and survey_id are required")
        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}"
        self._request("DELETE", endpoint)
        logger.info(f"Household {household_id} deleted from API")
        return True

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

        # propertyUnitId: UUID field - must be null (not empty string) when no value
        property_unit_id = get_value('property_unit_id', 'propertyUnitId', None)
        if property_unit_id == '':
            property_unit_id = None

        occupancy_type = get_value('occupancy_type', 'occupancyType', 0)
        occupancy_nature = get_value('occupancy_nature', 'occupancyNature', 0)

        api_data = {
            "propertyUnitId": property_unit_id,
            "householdSize": int(get_value('size', 'householdSize', 0)),
            "occupancyType": int(occupancy_type) if occupancy_type else None,
            "occupancyNature": int(occupancy_nature) if occupancy_nature else None,
            "maleCount": int(get_value('adult_males', 'maleCount', 0)),
            "femaleCount": int(get_value('adult_females', 'femaleCount', 0)),
            "maleChildCount": int(get_value('male_children_under18', 'maleChildCount', 0)),
            "femaleChildCount": int(get_value('female_children_under18', 'femaleChildCount', 0)),
            "maleElderlyCount": int(get_value('male_elderly_over65', 'maleElderlyCount', 0)),
            "femaleElderlyCount": int(get_value('female_elderly_over65', 'femaleElderlyCount', 0)),
            "maleDisabledCount": int(get_value('disabled_males', 'maleDisabledCount', 0)),
            "femaleDisabledCount": int(get_value('disabled_females', 'femaleDisabledCount', 0)),
            "notes": get_value('notes', 'notes', '') or None
        }
        if survey_id:
            api_data["surveyId"] = survey_id

        logger.info(f"Household API payload: {api_data}")
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

    def create_person_in_household(self, person_data: Dict[str, Any], survey_id: str, household_id: str) -> Dict[str, Any]:
        """
        Create a new person in a household via survey-scoped API.

        Args:
            person_data: Person data (snake_case or camelCase supported)
            survey_id: Survey UUID
            household_id: Household UUID

        Returns:
            Created person data with id

        Endpoint: POST /api/v1/Surveys/{surveyId}/households/{householdId}/persons
        """
        if not survey_id or not household_id:
            raise ValueError("survey_id and household_id are required")

        api_data = self._convert_person_to_api_format_with_household(person_data, survey_id, household_id)
        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}/persons"

        logger.info(f"Creating person in household via {endpoint}")
        result = self._request("POST", endpoint, json_data=api_data)
        logger.info(f"Person created in household: {result.get('id', 'N/A')}")
        return result

    def get_persons_for_household(self, survey_id: str, household_id: str) -> List[Dict[str, Any]]:
        """
        Get all persons in a household.

        Args:
            survey_id: Survey UUID
            household_id: Household UUID

        Returns:
            List of person dictionaries

        Endpoint: GET /api/v1/Surveys/{surveyId}/households/{householdId}/persons
        """
        if not survey_id or not household_id:
            logger.warning(f"Missing survey_id or household_id")
            return []

        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}/persons"
        logger.info(f"Fetching persons for household: {household_id}")

        try:
            result = self._request("GET", endpoint)

            if isinstance(result, list):
                persons = result
            elif isinstance(result, dict):
                persons = result.get("data") or result.get("persons") or result.get("items") or []
            else:
                logger.warning(f"Unexpected response format: {type(result)}")
                return []

            logger.info(f"Fetched {len(persons)} persons for household {household_id}")
            return persons if isinstance(persons, list) else []

        except Exception as e:
            logger.error(f"Failed to fetch persons: {e}")
            return []

    def link_person_to_unit(self, survey_id: str, unit_id: str, relation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Link a person to a property unit with relation type.

        Args:
            survey_id: Survey UUID
            unit_id: Property Unit UUID
            relation_data: Relation details (person_id, relation_type, contract_type, etc.)

        Returns:
            Created relation data

        Endpoint: POST /api/v1/Surveys/{surveyId}/property-units/{unitId}/relations
        """
        if not survey_id or not unit_id:
            raise ValueError("survey_id and unit_id are required")

        person_id = relation_data.get('person_id')
        if not person_id:
            raise ValueError("person_id is required in relation_data")

        api_data = self._convert_relation_to_api_format(relation_data, survey_id, unit_id)
        endpoint = f"/v1/Surveys/{survey_id}/property-units/{unit_id}/relations"

        logger.info(f"Linking person {person_id} to unit {unit_id}, api_data={api_data}")
        result = self._request("POST", endpoint, json_data=api_data)
        logger.info(f"Person linked to unit successfully")
        return result

    def update_person(self, person_id: str, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing person via PUT /api/v1/Persons/{id}."""
        if not person_id:
            raise ValueError("person_id is required")

        api_data = {
            "id": person_id,
            "familyNameArabic": person_data.get("last_name"),
            "firstNameArabic": person_data.get("first_name"),
            "fatherNameArabic": person_data.get("father_name"),
            "motherNameArabic": person_data.get("mother_name"),
            "nationalId": person_data.get("national_id"),
            "gender": int(person_data["gender"]) if person_data.get("gender") else None,
            "nationality": int(person_data["nationality"]) if person_data.get("nationality") else None,
            "email": person_data.get("email"),
            "mobileNumber": person_data.get("phone"),
            "phoneNumber": person_data.get("landline"),
        }

        birth_date = person_data.get("birth_date")
        if birth_date:
            api_data["dateOfBirth"] = f"{birth_date}T00:00:00Z" if "T" not in str(birth_date) else str(birth_date)

        api_data = {k: v for k, v in api_data.items() if v is not None}
        api_data["id"] = person_id

        logger.info(f"Updating person {person_id}")
        result = self._request("PUT", f"/v1/Persons/{person_id}", json_data=api_data)
        logger.info(f"Person {person_id} updated successfully")
        return result

    def update_person_in_survey(self, survey_id: str, household_id: str,
                               person_id: str, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update person within survey context.
        Endpoint: PUT /api/v1/Surveys/{surveyId}/households/{householdId}/persons/{personId}
        Provides better audit trail than standalone PUT /api/v1/Persons/{id}."""
        if not all([survey_id, household_id, person_id]):
            raise ValueError("survey_id, household_id, and person_id are all required")

        api_data = {
            "surveyId": survey_id,
            "householdId": household_id,
            "personId": person_id,
            "familyNameArabic": person_data.get("last_name"),
            "firstNameArabic": person_data.get("first_name"),
            "fatherNameArabic": person_data.get("father_name"),
            "motherNameArabic": person_data.get("mother_name"),
            "nationalId": person_data.get("national_id"),
            "gender": int(person_data["gender"]) if person_data.get("gender") else None,
            "nationality": int(person_data["nationality"]) if person_data.get("nationality") else None,
            "email": person_data.get("email"),
            "mobileNumber": person_data.get("phone"),
            "phoneNumber": person_data.get("landline"),
        }

        birth_date = person_data.get("birth_date")
        if birth_date:
            api_data["dateOfBirth"] = f"{birth_date}T00:00:00Z" if "T" not in str(birth_date) else str(birth_date)

        api_data = {k: v for k, v in api_data.items() if v is not None}
        api_data["surveyId"] = survey_id
        api_data["householdId"] = household_id
        api_data["personId"] = person_id

        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}/persons/{person_id}"
        logger.info(f"Updating person {person_id} in survey context")
        result = self._request("PUT", endpoint, json_data=api_data)
        logger.info(f"Person {person_id} updated in survey {survey_id}")
        return result

    def delete_person(self, person_id: str) -> None:
        """Soft delete a person via DELETE /api/v1/Persons/{id}."""
        if not person_id:
            raise ValueError("person_id is required")

        logger.info(f"Deleting person {person_id}")
        self._request("DELETE", f"/v1/Persons/{person_id}")
        logger.info(f"Person {person_id} deleted successfully")

    def delete_relation(self, survey_id: str, relation_id: str) -> bool:
        """Delete a person-property relation (cascade deletes evidence).
        Endpoint: DELETE /api/v1/Surveys/{surveyId}/relations/{relationId}"""
        if not survey_id or not relation_id:
            raise ValueError("survey_id and relation_id are required")

        logger.info(f"Deleting relation {relation_id} from survey {survey_id}")
        self._request("DELETE", f"/v1/Surveys/{survey_id}/relations/{relation_id}")
        logger.info(f"Relation {relation_id} deleted successfully")
        return True

    def update_relation(self, survey_id: str, relation_id: str, relation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a person-property relation (partial update).
        Endpoint: PATCH /api/v1/Surveys/{surveyId}/relations/{relationId}"""
        if not survey_id or not relation_id:
            raise ValueError("survey_id and relation_id are required")

        api_data = {}
        if 'rel_type' in relation_data or 'relationship_type' in relation_data:
            api_data["relationType"] = int(relation_data.get('rel_type') or relation_data.get('relationship_type', 99))
        if 'contract_type' in relation_data or 'occupancy_type' in relation_data:
            val = relation_data.get('contract_type') or relation_data.get('occupancy_type')
            if val:
                api_data["occupancyType"] = int(val)
        if 'ownership_share' in relation_data:
            api_data["ownershipShare"] = relation_data['ownership_share'] / 100.0
        if 'has_documents' in relation_data:
            api_data["hasEvidence"] = relation_data['has_documents']

        logger.info(f"Updating relation {relation_id}: {api_data}")
        result = self._request("PATCH", f"/v1/Surveys/{survey_id}/relations/{relation_id}", json_data=api_data)
        logger.info(f"Relation {relation_id} updated successfully")
        return result

    def upload_relation_document(
        self,
        survey_id: str,
        relation_id: str,
        file_path: str,
        issue_date: str = "",
        file_hash: str = "",
        evidence_type: int = 2,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Upload a tenure/relation evidence document via multipart/form-data.

        Endpoint: POST /api/v1/Surveys/{surveyId}/evidence/tenure
        """
        import os
        import json as _json
        import mimetypes

        if not survey_id or not relation_id:
            raise ValueError("survey_id and relation_id are required")
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        endpoint = f"/v1/Surveys/{survey_id}/evidence/tenure"
        url = f"{self.base_url}{endpoint}"

        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

        form_fields = {
            "PersonPropertyRelationId": (None, relation_id),
            "EvidenceType": (None, str(evidence_type)),
            "Description": (None, description or file_name),
        }
        if issue_date:
            date_val = f"{issue_date}T00:00:00Z" if 'T' not in issue_date else issue_date
            form_fields["DocumentIssuedDate"] = (None, date_val)

        logger.info(f"[API REQ] POST {endpoint} File: {file_name} ({mime_type})")

        try:
            with open(file_path, "rb") as f:
                files = {"File": (file_name, f, mime_type)}
                files.update(form_fields)
                response = requests.post(
                    url,
                    files=files,
                    headers=headers,
                    timeout=self.config.timeout,
                    verify=False
                )

            response.raise_for_status()

            result = None
            if response.text:
                result = response.json()

            logger.info(f"[API RES] {response.status_code} {endpoint}")
            logger.info(f"Document uploaded: {file_name} for relation {relation_id}")
            return result or {}

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            response_data = {}
            try:
                response_data = e.response.json() if e.response is not None else {}
            except (ValueError, AttributeError):
                pass
            logger.error(f"[API ERR] {status_code} POST {endpoint}: {response_data}")
            raise ApiException(
                message=str(e),
                status_code=status_code,
                response_data=response_data
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Network error during upload: {e}")
            raise NetworkException(message=str(e), original_error=e)

    def upload_identification_document(
        self,
        survey_id: str,
        person_id: str,
        file_path: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Upload an identification document for a person.

        Endpoint: POST /api/v1/Surveys/{surveyId}/evidence/identification
        """
        import os
        import mimetypes

        if not survey_id or not person_id:
            raise ValueError("survey_id and person_id are required")
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        endpoint = f"/v1/Surveys/{survey_id}/evidence/identification"
        url = f"{self.base_url}{endpoint}"

        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

        form_fields = {
            "PersonId": (None, person_id),
            "Description": (None, description or file_name),
        }

        logger.info(f"[API REQ] POST {endpoint} File: {file_name} for person {person_id}")

        try:
            with open(file_path, "rb") as f:
                files = {"File": (file_name, f, mime_type)}
                files.update(form_fields)
                response = requests.post(
                    url,
                    files=files,
                    headers=headers,
                    timeout=self.config.timeout,
                    verify=False
                )

            response.raise_for_status()
            result = response.json() if response.text else {}
            logger.info(f"Identification uploaded: {file_name} for person {person_id}")
            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            response_data = {}
            try:
                response_data = e.response.json() if e.response is not None else {}
            except (ValueError, AttributeError):
                pass
            logger.error(f"[API ERR] {status_code} POST {endpoint}: {response_data}")
            raise ApiException(
                message=str(e),
                status_code=status_code,
                response_data=response_data
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Network error during upload: {e}")
            raise NetworkException(message=str(e), original_error=e)

    def update_identification_evidence(
        self,
        survey_id: str,
        evidence_id: str,
        person_id: str,
        file_path: str = None,
        description: str = "",
        notes: str = ""
    ) -> Dict[str, Any]:
        """Update an existing identification document.
        Endpoint: PUT /api/v1/Surveys/{surveyId}/evidence/identification/{evidenceId}
        File is optional — send only metadata update if no new file."""
        import os
        import mimetypes

        if not survey_id or not evidence_id:
            raise ValueError("survey_id and evidence_id are required")

        endpoint = f"/v1/Surveys/{survey_id}/evidence/identification/{evidence_id}"
        url = f"{self.base_url}{endpoint}"

        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

        form_fields = {
            "EvidenceId": (None, evidence_id),
            "PersonId": (None, person_id),
        }
        if description:
            form_fields["Description"] = (None, description)
        if notes:
            form_fields["Notes"] = (None, notes)

        logger.info(f"[API REQ] PUT {endpoint}")

        try:
            if file_path and os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                with open(file_path, "rb") as f:
                    files = {"File": (file_name, f, mime_type)}
                    files.update(form_fields)
                    response = requests.put(url, files=files, headers=headers,
                                            timeout=self.config.timeout, verify=False)
            else:
                response = requests.put(url, files=form_fields, headers=headers,
                                        timeout=self.config.timeout, verify=False)

            response.raise_for_status()
            result = response.json() if response.text else {}
            logger.info(f"Identification evidence {evidence_id} updated")
            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            response_data = {}
            try:
                response_data = e.response.json() if e.response is not None else {}
            except (ValueError, AttributeError):
                pass
            logger.error(f"[API ERR] {status_code} PUT {endpoint}: {response_data}")
            raise ApiException(message=str(e), status_code=status_code, response_data=response_data)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Network error during evidence update: {e}")
            raise NetworkException(message=str(e), original_error=e)

    def update_tenure_evidence(
        self,
        survey_id: str,
        evidence_id: str,
        relation_id: str,
        file_path: str = None,
        issue_date: str = "",
        evidence_type: int = 2,
        description: str = "",
        notes: str = ""
    ) -> Dict[str, Any]:
        """Update an existing tenure/ownership document.
        Endpoint: PUT /api/v1/Surveys/{surveyId}/evidence/tenure/{evidenceId}
        File is optional — send only metadata update if no new file."""
        import os
        import mimetypes

        if not survey_id or not evidence_id:
            raise ValueError("survey_id and evidence_id are required")

        endpoint = f"/v1/Surveys/{survey_id}/evidence/tenure/{evidence_id}"
        url = f"{self.base_url}{endpoint}"

        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

        form_fields = {
            "EvidenceId": (None, evidence_id),
            "PersonPropertyRelationId": (None, relation_id),
            "EvidenceType": (None, str(evidence_type)),
        }
        if description:
            form_fields["Description"] = (None, description)
        if notes:
            form_fields["Notes"] = (None, notes)
        if issue_date:
            date_val = f"{issue_date}T00:00:00Z" if 'T' not in issue_date else issue_date
            form_fields["DocumentIssuedDate"] = (None, date_val)

        logger.info(f"[API REQ] PUT {endpoint}")

        try:
            if file_path and os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                with open(file_path, "rb") as f:
                    files = {"File": (file_name, f, mime_type)}
                    files.update(form_fields)
                    response = requests.put(url, files=files, headers=headers,
                                            timeout=self.config.timeout, verify=False)
            else:
                response = requests.put(url, files=form_fields, headers=headers,
                                        timeout=self.config.timeout, verify=False)

            response.raise_for_status()
            result = response.json() if response.text else {}
            logger.info(f"Tenure evidence {evidence_id} updated")
            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            response_data = {}
            try:
                response_data = e.response.json() if e.response is not None else {}
            except (ValueError, AttributeError):
                pass
            logger.error(f"[API ERR] {status_code} PUT {endpoint}: {response_data}")
            raise ApiException(message=str(e), status_code=status_code, response_data=response_data)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Network error during evidence update: {e}")
            raise NetworkException(message=str(e), original_error=e)

    def get_survey_evidences(self, survey_id: str, evidence_type: str = None) -> List[Dict[str, Any]]:
        """
        Get all evidence records for a survey.

        Endpoint: GET /api/v1/Surveys/{surveyId}/evidence
        """
        params = {}
        if evidence_type:
            params["evidenceType"] = evidence_type
        result = self._request("GET", f"/v1/Surveys/{survey_id}/evidence", params=params)
        return result if isinstance(result, list) else []

    def get_relation_evidences(
        self,
        survey_id: str,
        relation_id: str,
        evidence_type: str = None,
        only_current: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get evidence records for a person-property relation.

        Endpoint: GET /api/v1/Surveys/{surveyId}/relations/{relationId}/evidences
        """
        params = {"onlyCurrentVersions": str(only_current).lower()}
        if evidence_type:
            params["evidenceType"] = evidence_type
        result = self._request(
            "GET", f"/v1/Surveys/{survey_id}/relations/{relation_id}/evidences", params=params
        )
        return result if isinstance(result, list) else []

    def delete_evidence(self, survey_id: str, evidence_id: str) -> bool:
        """
        Soft delete an evidence record.

        Endpoint: DELETE /api/v1/Surveys/{surveyId}/evidence/{evidenceId}
        Returns 204 on success.
        """
        self._request("DELETE", f"/v1/Surveys/{survey_id}/evidence/{evidence_id}")
        return True

    def download_evidence(self, evidence_id: str, save_path: str) -> str:
        """
        Download an evidence file to disk.

        Endpoint: GET /api/v1/Surveys/evidence/{evidenceId}/download
        """
        import os
        url = f"{self.base_url}/v1/Surveys/evidence/{evidence_id}/download"
        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "*/*"
        }

        logger.info(f"[API REQ] GET /v1/Surveys/evidence/{evidence_id}/download")

        try:
            response = requests.get(url, headers=headers, timeout=self.config.timeout, verify=False)
            response.raise_for_status()
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Evidence downloaded: {evidence_id} -> {save_path}")
            return save_path
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else 0
            logger.error(f"[API ERR] {status_code} download evidence {evidence_id}")
            raise ApiException(message=str(e), status_code=status_code)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(f"Network error during download: {e}")
            raise NetworkException(message=str(e), original_error=e)

    def _convert_person_to_api_format_with_household(self, person_data: Dict[str, Any], survey_id: str, household_id: str) -> Dict[str, Any]:
        """Convert person data to API format for household-scoped endpoint."""
        import re
        from datetime import datetime

        def get_value(snake_key: str, camel_key: str, default=None):
            return person_data.get(snake_key) or person_data.get(camel_key) or default

        birth_date = get_value('birth_date', 'dateOfBirth', '')
        date_of_birth = None
        if birth_date:
            if 'T' not in str(birth_date):
                date_of_birth = f"{birth_date}T00:00:00Z"
            else:
                date_of_birth = str(birth_date)

        father_name = get_value('father_name', 'fatherNameArabic', '')
        if not father_name.strip():
            father_name = '-'

        mother_name = get_value('mother_name', 'motherNameArabic', '')
        if not mother_name.strip():
            mother_name = '-'

        email = get_value('email', 'email', '')
        if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            email = ''

        gender = get_value('gender', 'gender', None)
        nationality = get_value('nationality', 'nationality', None)
        # Note: person_role (owner/tenant) is RelationType, NOT RelationshipToHead.
        # RelationshipToHead is household role (head/spouse/child) - different enum.
        # Don't send relationship_type as relationshipToHead to avoid enum mismatch.

        api_data = {
            "surveyId": survey_id,
            "householdId": household_id,
            "familyNameArabic": get_value('last_name', 'familyNameArabic', ''),
            "firstNameArabic": get_value('first_name', 'firstNameArabic', ''),
            "fatherNameArabic": father_name,
            "motherNameArabic": mother_name,
            "nationalId": get_value('national_id', 'nationalId', ''),
            "gender": int(gender) if gender else None,
            "nationality": int(nationality) if nationality else None,
            "dateOfBirth": date_of_birth,
            "email": email,
            "mobileNumber": get_value('phone', 'mobileNumber', ''),
            "phoneNumber": get_value('landline', 'phoneNumber', ''),
        }
        return {k: v for k, v in api_data.items() if v is not None}

    def _convert_relation_to_api_format(self, relation_data: Dict[str, Any], survey_id: str, unit_id: str) -> Dict[str, Any]:
        """Convert relation data to API format (LinkPersonToPropertyUnitCommand)."""
        rel_type = relation_data.get('rel_type') or relation_data.get('relationship_type', 99)
        if isinstance(rel_type, int):
            relation_type_int = rel_type
        else:
            relation_type_int = 99

        occupancy_type = relation_data.get('contract_type') or relation_data.get('occupancy_type', None)
        if isinstance(occupancy_type, int) and occupancy_type > 0:
            occupancy_type_int = occupancy_type
        else:
            occupancy_type_int = None

        ownership_share_pct = relation_data.get('ownership_share', None)
        if ownership_share_pct is not None and ownership_share_pct > 0:
            ownership_share_decimal = ownership_share_pct / 100.0
            # Safety: if result > 1.0, user may have entered a fraction directly
            if ownership_share_decimal > 1.0:
                logger.warning(f"OwnershipShare: {ownership_share_pct}/100={ownership_share_decimal} > 1.0, using raw value as fraction")
                ownership_share_decimal = min(ownership_share_pct, 1.0)
            logger.info(f"OwnershipShare: input={ownership_share_pct}% -> API={ownership_share_decimal}")
        else:
            ownership_share_decimal = None

        has_evidence = relation_data.get('has_documents', False)

        api_data = {
            "surveyId": survey_id,
            "personId": relation_data.get('person_id', ''),
            "propertyUnitId": unit_id,
            "relationType": relation_type_int,
            "hasEvidence": has_evidence,
        }

        if occupancy_type_int:
            api_data["occupancyType"] = occupancy_type_int
        if ownership_share_decimal is not None:
            api_data["ownershipShare"] = ownership_share_decimal
        elif relation_type_int == 1:
            # Backend requires ownershipShare for Owner type, default to 1.0 (100%)
            api_data["ownershipShare"] = 1.0
            logger.info("OwnershipShare: defaulting to 1.0 (100%) for Owner relation type")

        contract_details = relation_data.get('evidence_desc', '') or relation_data.get('contract_details', '')
        if contract_details:
            api_data["contractDetails"] = contract_details

        notes = relation_data.get('notes', '')
        if notes:
            api_data["notes"] = notes

        return api_data

    def _convert_person_to_api_format(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert person data to API format matching CreatePersonCommand schema."""
        def get_value(snake_key: str, camel_key: str, default=None):
            return person_data.get(snake_key) or person_data.get(camel_key) or default

        gender = get_value('gender', 'gender', None)
        nationality = get_value('nationality', 'nationality', None)

        birth_date = get_value('birth_date', 'dateOfBirth', '')
        date_of_birth = None
        if birth_date:
            if 'T' not in str(birth_date):
                date_of_birth = f"{birth_date}T00:00:00Z"
            else:
                date_of_birth = str(birth_date)

        api_data = {
            "familyNameArabic": get_value('last_name', 'familyNameArabic', ''),
            "firstNameArabic": get_value('first_name', 'firstNameArabic', ''),
            "fatherNameArabic": get_value('father_name', 'fatherNameArabic', '-'),
            "motherNameArabic": get_value('mother_name', 'motherNameArabic', '-'),
            "nationalId": get_value('national_id', 'nationalId', ''),
            "gender": int(gender) if gender else None,
            "nationality": int(nationality) if nationality else None,
            "dateOfBirth": date_of_birth,
            "email": get_value('email', 'email', ''),
            "mobileNumber": get_value('phone', 'mobileNumber', ''),
            "phoneNumber": get_value('landline', 'phoneNumber', ''),
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

    def create_office_survey(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new office survey via API.

        Args:
            survey_data: Survey data (snake_case or camelCase supported)
                - building_uuid/buildingId: Building UUID

        Returns:
            Created survey data with id

        Endpoint: POST /api/v1/Surveys/office
        """
        api_data = self._convert_survey_to_api_format(survey_data)
        logger.info(f"Creating office survey for building: {api_data.get('buildingId', 'N/A')}")
        result = self._request("POST", "/v1/Surveys/office", json_data=api_data)
        logger.info(f"Office survey created: {result.get('id', 'N/A')}")
        return result

    def finalize_office_survey(self, survey_id: str, finalize_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process claims for an office survey.

        Args:
            survey_id: Survey UUID
            finalize_options: Processing options
                - finalNotes: Final notes for the survey
                - durationMinutes: Survey duration in minutes
                - autoCreateClaim: Whether to automatically create a claim

        Returns:
            Response data with survey details, claim info, warnings, etc.

        Endpoint: POST /api/v1/Surveys/office/{id}/process-claims
        """
        if not survey_id:
            raise ValueError("survey_id is required")

        api_data = {
            "surveyId": survey_id,
            "finalNotes": "",
            "durationMinutes": 10,
            "autoCreateClaim": True
        }

        if finalize_options:
            if 'finalNotes' in finalize_options:
                api_data['finalNotes'] = finalize_options['finalNotes'] or ""
            if 'durationMinutes' in finalize_options:
                api_data['durationMinutes'] = finalize_options['durationMinutes'] or 0
            if 'autoCreateClaim' in finalize_options:
                api_data['autoCreateClaim'] = finalize_options['autoCreateClaim']

        logger.info(f"Processing claims for office survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/office/{survey_id}/process-claims", json_data=api_data)
        logger.info(f"Office survey claims processed successfully")
        return result

    def finalize_survey_status(self, survey_id: str) -> Dict[str, Any]:
        """
        Finalize an office survey (transition from Draft to Finalized).

        Args:
            survey_id: Survey UUID

        Returns:
            Updated survey data

        Endpoint: POST /api/v1/Surveys/office/{id}/finalize
        """
        if not survey_id:
            raise ValueError("survey_id is required")

        logger.info(f"Finalizing office survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/office/{survey_id}/finalize")
        logger.info(f"Office survey finalized successfully")
        return result

    def save_draft_to_backend(self, survey_id: str, draft_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Save survey progress as draft on backend.
        Endpoint: PUT /api/v1/Surveys/{id}/draft
        Schema: SaveDraftSurveyCommand {surveyId, propertyUnitId, gpsCoordinates,
                intervieweeName, intervieweeRelationship, notes, durationMinutes}"""
        if not survey_id:
            raise ValueError("survey_id is required")

        api_data = {"surveyId": survey_id}
        if draft_data:
            field_map = {
                "property_unit_id": "propertyUnitId",
                "gps_coordinates": "gpsCoordinates",
                "interviewee_name": "intervieweeName",
                "interviewee_relationship": "intervieweeRelationship",
                "notes": "notes",
                "duration_minutes": "durationMinutes",
            }
            for snake_key, camel_key in field_map.items():
                val = draft_data.get(snake_key) or draft_data.get(camel_key)
                if val is not None:
                    api_data[camel_key] = val

        logger.info(f"Saving draft to backend for survey {survey_id}")
        result = self._request("PUT", f"/v1/Surveys/{survey_id}/draft", json_data=api_data)
        logger.info(f"Draft saved to backend for survey {survey_id}")
        return result

    def _convert_survey_to_api_format(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert survey data to API format (camelCase).

        API Schema (CreateOfficeSurveyCommand):
            buildingId: uuid (REQUIRED)
            surveyDate: datetime ISO 8601 (REQUIRED)
            inPersonVisit: boolean (REQUIRED)
            propertyUnitId: uuid (optional)
            intervieweeName, intervieweeRelationship, notes,
            officeLocation, registrationNumber, appointmentReference,
            contactPhone, contactEmail: string (optional)
        """
        def get_value(snake_key: str, camel_key: str, default=None):
            return survey_data.get(snake_key) or survey_data.get(camel_key) or default

        api_data = {
            "buildingId": get_value('building_uuid', 'buildingId', None),
            "surveyDate": get_value('survey_date', 'surveyDate'),
            "inPersonVisit": survey_data.get('inPersonVisit', True),
            "propertyUnitId": get_value('property_unit_id', 'propertyUnitId'),
            "intervieweeName": get_value('interviewee_name', 'intervieweeName'),
            "intervieweeRelationship": get_value('interviewee_relationship', 'intervieweeRelationship'),
            "notes": get_value('notes', 'notes'),
            "officeLocation": get_value('office_location', 'officeLocation'),
            "registrationNumber": get_value('registration_number', 'registrationNumber'),
            "contactPhone": get_value('contact_phone', 'contactPhone'),
            "contactEmail": get_value('contact_email', 'contactEmail'),
        }
        return {k: v for k, v in api_data.items() if v is not None and v != ''}

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
