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
from services.exceptions import ApiException, NetworkException, PasswordChangeRequiredException

# Suppress SSL warnings for self-signed certificates in development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)


@dataclass
class ApiConfig:
    """API connection configuration."""
    base_url: str = None  # Will be loaded from Config
    username: str = None  # Will be loaded from Config
    password: str = None  # Will be loaded from Config
    timeout: int = 30

    def __post_init__(self):
        """Load from Config if not provided."""
        # Load from Config (which reads from .env)
        if self.base_url is None or self.username is None or self.password is None:
            from app.config import Config

            if self.base_url is None:
                from app.config import get_api_base_url
                self.base_url = get_api_base_url()
            if self.username is None:
                self.username = Config.API_USERNAME
            if self.password is None:
                self.password = Config.API_PASSWORD
            if self.timeout == 30:  # if default
                self.timeout = Config.API_TIMEOUT


class TRRCMSApiClient:
    """API client for TRRCMS Backend."""

    def __init__(self, config: ApiConfig):
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._login_failures: int = 0
        self._login_cooldown_until: Optional[datetime] = None
        self._on_session_expired = None
        self._on_password_change_required = None
        logger.info(f"API client initialized for {self.base_url}")

    def set_session_expired_callback(self, callback):
        """Set callback to invoke when the session expires (token refresh failed or 401)."""
        self._on_session_expired = callback

    def set_password_change_required_callback(self, callback):
        """Set callback to invoke when password change is required (403 PasswordChangeRequired)."""
        self._on_password_change_required = callback

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate and obtain access token."""
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

            self._login_failures = 0
            self._login_cooldown_until = None
            logger.info(f"Logged in as {username}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Login failed: {e}")
            raise

    def set_access_token(self, token: str, expires_in: int = 3600):
        """Set access token from external source."""
        self.access_token = token
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        logger.debug(f"Access token updated externally (expires in {expires_in}s)")

    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
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

            logger.info("Token refreshed")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    def logout(self) -> Dict[str, Any]:
        """POST /v1/Auth/logout — invalidate refresh token server-side."""
        body = {"refreshToken": self.refresh_token} if self.refresh_token else {}
        result = self._request("POST", "/v1/Auth/logout", body)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        return result or {}

    def change_password(self, current_password: str, new_password: str, user_id: str = None) -> Dict[str, Any]:
        """POST /v1/auth/change-password."""
        body = {
            "currentPassword": current_password,
            "newPassword": new_password,
            "confirmPassword": new_password,
        }
        if user_id:
            body["userId"] = user_id
        return self._request("POST", "/v1/auth/change-password", body) or {}

    def lock_building(self, building_id: str, is_locked: bool) -> Dict[str, Any]:
        """PUT /v1/Buildings/{id}/lock — toggle building lock state."""
        return self._request("PUT", f"/v1/Buildings/{building_id}/lock", {"isLocked": is_locked}) or {}

    def _ensure_valid_token(self):
        """التأكد من صلاحية الـ Token قبل الطلب."""
        if not self.access_token:
            raise RuntimeError("Not authenticated")

        if self.token_expires_at:
            time_until_expiry = (self.token_expires_at - datetime.now()).total_seconds()
            if time_until_expiry < 300:
                logger.info("Token expiring soon, refreshing...")
                if not self.refresh_access_token():
                    logger.warning("Token refresh failed — session expired")
                    self.access_token = None
                    if self._on_session_expired:
                        self._on_session_expired()
                    raise RuntimeError("Session expired")

    def _headers(self) -> Dict[str, str]:
        """الحصول على Headers مع Authorization."""
        self._ensure_valid_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    _MAX_RETRIES = 2

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Any:
        """Execute HTTP request with error handling and automatic retry."""
        url = f"{self.base_url}{endpoint}"

        import json as _json
        logger.info(f"[API REQ] {method} {endpoint}")
        if params:
            logger.info(f"[API REQ] Params: {params}")
        if json_data:
            try:
                logger.info(f"[API REQ] Body: {_json.dumps(json_data, indent=2, ensure_ascii=False, default=str)}")
            except Exception:
                logger.info(f"[API REQ] Body: {json_data}")

        last_error = None
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                token_used = self.access_token
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

                logger.info(f"[API RES] {response.status_code} {endpoint}")
                if result:
                    try:
                        res_str = _json.dumps(result, indent=2, ensure_ascii=False, default=str)
                        if len(res_str) > 5000:
                            logger.info(f"[API RES] Body (truncated): {res_str[:5000]}...")
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
                if status_code == 401:
                    # Only handle if the token hasn't changed (new login) since our request
                    if self.access_token and self.access_token == token_used:
                        if self.refresh_token and self.refresh_access_token():
                            continue  # Retry with refreshed token
                        logger.warning(f"[API ERR] 401 {method} {endpoint} — session expired")
                        self.access_token = None
                        if self._on_session_expired:
                            self._on_session_expired()
                    elif self.access_token != token_used:
                        logger.info(f"401 on {endpoint} ignored — token changed by new session")
                if status_code == 403:
                    error_code = str(response_data.get("code", "") or response_data.get("errorCode", "") or response_data.get("error", ""))
                    if "PasswordChangeRequired" in error_code or "PasswordChangeRequired" in str(response_data):
                        logger.warning(f"[API ERR] 403 PasswordChangeRequired on {endpoint}")
                        if self._on_password_change_required:
                            self._on_password_change_required()
                        raise PasswordChangeRequiredException(
                            message=f"Password change required on {endpoint}",
                            response_data=response_data
                        )
                log_fn = logger.warning if status_code in (401, 403, 404) else logger.error
                log_fn(f"[API ERR] {status_code} {method} {endpoint} | Response: {response_data or response_text}")
                raise ApiException(
                    message=str(e),
                    status_code=status_code,
                    response_data=response_data
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_error = e
                if attempt < self._MAX_RETRIES:
                    import time
                    wait = attempt + 1
                    logger.warning(
                        f"Network error (attempt {attempt + 1}/{self._MAX_RETRIES + 1}), "
                        f"retrying in {wait}s: {endpoint}"
                    )
                    time.sleep(wait)
                    continue
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

    def get_buildings_for_map(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get buildings within bounding box for map display."""
        payload = {
            "northEastLat": north_east_lat,
            "northEastLng": north_east_lng,
            "southWestLat": south_west_lat,
            "southWestLng": south_west_lng
        }

        if status:
            payload["status"] = status

        logger.debug(f"Fetching buildings for map: bbox={payload}")
        result = self._request("POST", "/v2/buildings/map", json_data=payload)
        buildings = result.get("items", []) if isinstance(result, dict) else result
        logger.info(f"Fetched {len(buildings)} buildings from API")

        return buildings

    def get_landmarks_for_map(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        landmark_type: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch landmarks within bounding box for map display."""
        params = {
            "southWestLat": south_west_lat,
            "southWestLng": south_west_lng,
            "northEastLat": north_east_lat,
            "northEastLng": north_east_lng
        }
        if landmark_type is not None:
            params["type"] = landmark_type

        try:
            result = self._request("GET", "/v2/landmarks/map", params=params)
            landmarks = result.get("items", []) if isinstance(result, dict) else result
            logger.info(f"Fetched {len(landmarks)} landmarks for map")
            return landmarks
        except Exception as e:
            logger.error(f"Failed to fetch landmarks for map: {e}", exc_info=True)
            return []

    def search_landmarks(
        self,
        query: str,
        landmark_type: Optional[int] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search landmarks by name/description.

        Args:
            query: Search text
            landmark_type: Optional type filter (int)
            max_results: Max results to return

        Returns:
            List of LandmarkDto
        """
        params = {"query": query, "maxResults": max_results}
        if landmark_type is not None:
            params["type"] = landmark_type

        try:
            result = self._request("GET", "/v2/landmarks/search", params=params)
            return result.get("items", []) if isinstance(result, dict) else result
        except Exception as e:
            logger.warning(f"Failed to search landmarks: {e}")
            return []

    def get_landmark_types(self) -> List[Dict[str, Any]]:
        """Fetch all landmark types with their SVG icons."""
        try:
            result = self._request("GET", "/v1/landmarks/types")
            items = result.get("items", []) if isinstance(result, dict) else result
            logger.info(f"Fetched {len(items)} landmark types")
            return items
        except Exception as e:
            logger.warning(f"Failed to fetch landmark types: {e}")
            return []

    def get_streets_for_map(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float
    ) -> List[Dict[str, Any]]:
        """
        Fetch streets within bounding box for map display.

        Args:
            north_east_lat: NE corner latitude
            north_east_lng: NE corner longitude
            south_west_lat: SW corner latitude
            south_west_lng: SW corner longitude

        Returns:
            List of StreetMapDto with geometryWkt
        """
        params = {
            "southWestLat": south_west_lat,
            "southWestLng": south_west_lng,
            "northEastLat": north_east_lat,
            "northEastLng": north_east_lng
        }

        try:
            result = self._request("GET", "/v2/streets/map", params=params)
            streets = result.get("items", []) if isinstance(result, dict) else result
            logger.info(f"Fetched {len(streets)} streets for map")
            return streets
        except Exception as e:
            logger.error(f"Failed to fetch streets for map: {e}", exc_info=True)
            return []

    def get_buildings_in_polygon(
        self,
        polygon_wkt: str,
        status: Optional[str] = None,
        building_type: Optional[int] = None,
        damage_level: Optional[int] = None,
        page: int = 1,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """Get buildings within a polygon area."""
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

        buildings = response.get("buildings", [])
        total_count = response.get("totalCount", 0)
        logger.info(f"Fetched {len(buildings)} buildings in polygon (totalCount={total_count})")

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

        logger.info(f"Found {len(items)} buildings for assignment (total: {total_count}) using BuildingAssignments API")

        return response

    def get_buildings_for_assignment(
        self,
        governorate_code=None,
        district_code=None,
        sub_district_code=None,
        community_code=None,
        neighborhood_code=None,
        building_code=None,
        building_type=None,
        building_status=None,
        survey_status=None,
        has_active_assignment=None,
        latitude=None,
        longitude=None,
        radius_meters=None,
        polygon_wkt=None,
        page=1,
        page_size=100,
        sort_by=None,
        sort_descending=None
    ) -> Dict[str, Any]:
        """
        GET /api/v1/BuildingAssignments/buildings — all Swagger parameters.
        """
        params = {"page": page, "pageSize": page_size}

        if governorate_code:
            params["governorateCode"] = governorate_code
        if district_code:
            params["districtCode"] = district_code
        if sub_district_code:
            params["subDistrictCode"] = sub_district_code
        if community_code:
            params["communityCode"] = community_code
        if neighborhood_code:
            params["neighborhoodCode"] = neighborhood_code
        if building_code:
            params["buildingCode"] = building_code
        if building_type is not None:
            params["buildingType"] = building_type
        if building_status is not None:
            params["buildingStatus"] = building_status
        if survey_status is not None:
            params["surveyStatus"] = survey_status
        if has_active_assignment is not None:
            params["hasActiveAssignment"] = str(has_active_assignment).lower()
        if latitude is not None:
            params["latitude"] = latitude
        if longitude is not None:
            params["longitude"] = longitude
        if radius_meters is not None:
            params["radiusMeters"] = radius_meters
        if polygon_wkt:
            params["polygonWkt"] = polygon_wkt
        if sort_by:
            params["sortBy"] = sort_by
        if sort_descending is not None:
            params["sortDescending"] = str(sort_descending).lower()

        logger.debug(f"Fetching buildings for assignment with filters: {params}")
        response = self._request("GET", "/v1/BuildingAssignments/buildings", params=params)

        items = response.get("items", [])
        total_count = response.get("totalCount", 0)
        logger.info(f"Found {len(items)} buildings for assignment (total: {total_count})")

        return response

    def get_building_by_id(self, building_id: str) -> Dict[str, Any]:
        """Get building details by ID."""
        return self._request("GET", f"/v1/Buildings/{building_id}")

    def update_building_geometry(
        self,
        building_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        building_geometry_wkt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update building location (point or polygon)."""
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
        logger.info(f"Geometry updated for building {building_id}")

        return result

    def search_buildings(
        self,
        building_id: Optional[str] = None,
        neighborhood_code: Optional[str] = None,
        building_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Search buildings with multiple criteria."""
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
        """Create a new building."""
        api_data = self._convert_building_to_api_format(building_data)
        logger.info(f"Creating building: {api_data.get('buildingId', 'N/A')}")
        result = self._request("POST", "/v1/Buildings", json_data=api_data)
        logger.info(f"Created building: {result.get('buildingId')}")
        return result

    def update_building(self, building_id: str, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing building."""
        result = None

        # Update general building data
        update_data = self._build_update_command(building_data)
        if update_data:
            try:
                logger.info(f"Updating building data: {building_id}")
                logger.info(f"  Payload: {update_data}")
                result = self._request("PUT", f"/v1/Buildings/{building_id}", json_data=update_data)
                logger.info(f"Building data updated")
            except Exception as e:
                logger.warning(f"Building data update failed: {e}")

        # Update geometry separately
        geo_wkt = building_data.get('geo_location') or building_data.get('buildingGeometryWkt')
        lat = building_data.get('latitude')
        lng = building_data.get('longitude')

        if geo_wkt or (lat is not None and lng is not None):
            try:
                logger.info(f"Updating geometry: lat={lat}, lng={lng}, wkt={'YES' if geo_wkt else 'NO'}")
                result = self.update_building_geometry(
                    building_id=building_id,
                    latitude=lat,
                    longitude=lng,
                    building_geometry_wkt=geo_wkt
                )
                logger.info(f"Geometry updated")
            except Exception as e:
                logger.warning(f"Geometry update failed: {e}")

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
            "numberOfUnits": get_value('number_of_units', 'numberOfUnits'),
            "numberOfApartments": get_value('number_of_apartments', 'numberOfApartments'),
            "numberOfShops": get_value('number_of_shops', 'numberOfShops'),
            "numberOfFloors": get_value('number_of_floors', 'numberOfFloors'),
            "latitude": get_value('latitude', 'latitude'),
            "longitude": get_value('longitude', 'longitude'),
            "locationDescription": get_value('location_description', 'locationDescription', ''),
            "generalDescription": get_value('general_description', 'generalDescription', ''),
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
        """Delete a building."""
        logger.info(f"Deleting building: {building_id}")
        self._request("DELETE", f"/v1/Buildings/{building_id}")
        logger.info(f"Building deleted: {building_id}")
        return True

    def get_property_units_by_building(self, building_id: str) -> List[Dict[str, Any]]:
        """Get property units for a building."""
        return self._request("GET", f"/v1/PropertyUnits/building/{building_id}")

    def get_building_documents(self, building_id: str) -> List[Dict[str, Any]]:
        """Get documents attached to a building."""
        try:
            return self._request("GET", f"/v1/building-documents/by-building/{building_id}") or []
        except Exception as e:
            logger.warning(f"Failed to fetch building documents for {building_id}: {e}")
            return []

    def health_check(self) -> bool:
        """Check API connectivity."""
        try:
            # Try to get current user info as health check
            self._request("GET", "/v1/Auth/me")
            logger.info("API health check passed")
            return True
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

    def get_current_user(self) -> Dict[str, Any]:
        """الحصول على معلومات المستخدم الحالي."""
        return self._request("GET", "/v1/Auth/me")

    def create_assignment(
        self,
        buildings: List[Dict[str, Any]],
        field_collector_id: str,
        assignment_notes: Optional[str] = None,
        priority: Optional[str] = None,
        target_completion_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create building assignments for a field researcher."""
        payload = {
            "fieldCollectorId": field_collector_id,
            "buildings": buildings,
        }
        if assignment_notes:
            payload["assignmentNotes"] = assignment_notes
        if priority:
            payload["priority"] = priority
        if target_completion_date:
            payload["targetCompletionDate"] = target_completion_date

        logger.info(f"Creating assignment for {len(buildings)} buildings → researcher: {field_collector_id}")
        return self._request("POST", "/v1/BuildingAssignments/assign", json_data=payload)

    def get_all_assignments(
        self,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """Get all building assignments with pagination."""
        params = {"page": page, "pageSize": page_size}
        return self._request("GET", "/v1/BuildingAssignments", params=params)

    def get_assignment(self, assignment_id: str) -> Dict[str, Any]:
        """Get assignment details by ID."""
        return self._request("GET", f"/v1/BuildingAssignments/{assignment_id}")

    def get_pending_assignments(
        self,
        researcher_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Get pending assignments ready for transfer."""
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
        """Update assignment transfer status."""
        payload = {
            "transferStatus": transfer_status,
            "deviceId": device_id
        }

        logger.info(f"Updating assignment {assignment_id} transfer status → {transfer_status}")
        return self._request(
            "POST",
            f"/v1/BuildingAssignments/{assignment_id}/transfer-status",
            json_data=payload
        )

    def unassign_building(
        self,
        assignment_id: str,
        cancellation_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unassign a field assignment."""
        if not assignment_id:
            raise ValueError("assignment_id is required")
        payload = {}
        if cancellation_reason:
            payload["cancellationReason"] = cancellation_reason
        result = self._request(
            "POST", f"/v1/BuildingAssignments/{assignment_id}/unassign",
            json_data=payload if payload else None
        )
        logger.info(f"Assignment {assignment_id} unassigned")
        return result

    def get_assignment_statistics(self) -> Dict[str, Any]:
        """Get assignment statistics."""
        return self._request("GET", "/v1/BuildingAssignments/statistics")

    def get_field_collectors(self) -> List[Dict[str, Any]]:
        """Get available field collectors."""
        return self._request("GET", "/v1/BuildingAssignments/field-collectors")

    def get_field_collector_assignments(
        self, collector_id: str
    ) -> List[Dict[str, Any]]:
        """Get assignments for a specific field collector."""
        return self._request(
            "GET",
            f"/v1/BuildingAssignments/field-collectors/{collector_id}/assignments"
        )

    def get_assignment_property_units(
        self, building_id: str
    ) -> List[Dict[str, Any]]:
        """Get property units for an assigned building."""
        return self._request(
            "GET",
            f"/v1/BuildingAssignments/buildings/{building_id}/property-units"
        )

    def initiate_transfer(
        self,
        assignment_ids: List[str],
        field_collector_id: str
    ) -> Dict[str, Any]:
        """Initiate transfer of assignments to tablets."""
        payload = {
            "fieldCollectorId": field_collector_id,
            "assignmentIds": assignment_ids
        }
        logger.info(f"Initiating transfer for {len(assignment_ids)} assignments")
        return self._request(
            "POST", "/v1/BuildingAssignments/initiate-transfer", json_data=payload
        )

    def check_transfer_timeout(
        self,
        timeout_minutes: int = 30,
        field_collector_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check for timed-out assignments."""
        payload = {"timeoutMinutes": timeout_minutes}
        if field_collector_id:
            payload["fieldCollectorId"] = field_collector_id
        return self._request(
            "POST", "/v1/BuildingAssignments/check-transfer-timeout",
            json_data=payload
        )

    def retry_transfer(self, assignment_ids: List[str]) -> Dict[str, Any]:
        """Retry failed assignment transfers."""
        payload = {"assignmentIds": assignment_ids}
        logger.info(f"Retrying transfer for {len(assignment_ids)} assignments")
        return self._request(
            "POST", "/v1/BuildingAssignments/retry-transfer", json_data=payload
        )

    def create_property_unit(self, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new property unit."""
        api_data = self._convert_property_unit_to_api_format(unit_data)
        logger.info(f"Creating property unit: {api_data.get('unitNumber', 'N/A')}")
        result = self._request("POST", "/v1/PropertyUnits", json_data=api_data)
        logger.info(f"Property unit created: {result.get('id', 'N/A')}")
        return result

    def update_property_unit(self, unit_id: str, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing property unit."""
        api_data = self._convert_property_unit_to_api_format(unit_data)
        api_data["id"] = unit_id
        result = self._request("PUT", f"/v1/PropertyUnits/{unit_id}", json_data=api_data)
        logger.info(f"Property unit updated: {unit_id}")
        return result

    def _convert_property_unit_to_api_format(self, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert property unit data to API format (camelCase)."""
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

    def get_survey_property_units(self, survey_id: str) -> List[Dict[str, Any]]:
        """Get property units for a building via survey-scoped endpoint."""
        if not survey_id:
            raise ValueError("survey_id is required")
        result = self._request("GET", f"/v2/surveys/{survey_id}/property-units")
        return result.get("items", []) if isinstance(result, dict) else result

    def update_contact_person(self, survey_id: str, person_id: str, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update contact person via survey-scoped endpoint."""
        if not survey_id or not person_id:
            raise ValueError("survey_id and person_id are required")

        api_data: Dict[str, Any] = {}

        field_map = {
            'first_name_ar': 'firstNameArabic',
            'father_name_ar': 'fatherNameArabic',
            'last_name_ar': 'familyNameArabic',
            'mother_name_ar': 'motherNameArabic',
            'first_name': 'firstNameArabic',
            'father_name': 'fatherNameArabic',
            'last_name': 'familyNameArabic',
            'mother_name': 'motherNameArabic',
            'national_id': 'nationalId',
            'email': 'email',
            'phone': 'mobileNumber',
            'landline': 'phoneNumber',
        }
        for local_key, api_key in field_map.items():
            val = person_data.get(local_key)
            if val is not None:
                str_val = str(val).strip() if isinstance(val, str) else val
                if str_val:  # skip empty strings to avoid API validation errors
                    api_data[api_key] = str_val

        for int_field in ('gender', 'nationality'):
            val = person_data.get(int_field)
            if val is not None:
                try:
                    api_data[int_field] = int(val)
                except (ValueError, TypeError):
                    pass

        birth_date = person_data.get('birth_date')
        if birth_date:
            api_data['dateOfBirth'] = f"{birth_date}T00:00:00Z" if "T" not in str(birth_date) else str(birth_date)

        logger.info(f"Updating contact person {person_id} for survey {survey_id}")
        result = self._request("PUT", f"/v1/Surveys/{survey_id}/contact-person/{person_id}", json_data=api_data)
        logger.info(f"Contact person {person_id} updated successfully")
        return result

    def link_unit_to_survey(self, survey_id: str, unit_id: str) -> Dict[str, Any]:
        """Link a property unit to a survey."""
        if not survey_id or not unit_id:
            raise ValueError("survey_id and unit_id are required")

        logger.info(f"Linking unit {unit_id} to survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/{survey_id}/property-units/{unit_id}/link")
        logger.info(f"Unit linked successfully")
        return result

    def get_all_property_units(
        self,
        building_id: Optional[str] = None,
        unit_type: Optional[int] = None,
        status: Optional[int] = None,
        group_by_building: bool = False,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get property units as a flat list."""
        params: Dict[str, Any] = {"groupByBuilding": "false"}
        if building_id:
            params["buildingId"] = building_id
        if unit_type is not None:
            params["unitType"] = unit_type
        if status is not None:
            params["status"] = status
        if group_by_building:
            params["groupByBuilding"] = "true"

        logger.info(f"Fetching property units (groupByBuilding={group_by_building})")
        result = self._request("GET", "/v1/PropertyUnits", params=params)

        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # GroupedPropertyUnitsResponseDto — flatten if grouped
            grouped = result.get("groupedByBuilding", [])
            if grouped:
                units: List[Dict[str, Any]] = []
                for g in grouped:
                    units.extend(g.get("propertyUnits", []))
                logger.info(f"Fetched {len(units)} units (flattened from {len(grouped)} buildings)")
                return units
            return result.get("data") or result.get("units") or result.get("items") or []
        logger.warning(f"Unexpected response format: {type(result)}")
        return []

    def get_units_grouped(
        self,
        building_id: Optional[str] = None,
        unit_type: Optional[int] = None,
        status: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get property units grouped by building.
        """
        params: Dict[str, Any] = {"groupByBuilding": "true"}
        if building_id:
            params["buildingId"] = building_id
        if unit_type is not None:
            params["unitType"] = unit_type
        if status is not None:
            params["status"] = status

        logger.info("Fetching grouped property units")
        result = self._request("GET", "/v1/PropertyUnits", params=params)
        if isinstance(result, dict):
            return result
        return {"groupedByBuilding": [], "totalUnits": 0, "totalBuildings": 0}

    def get_property_unit_by_id(self, unit_id: str) -> Optional[Dict[str, Any]]:
        """Get a single property unit by UUID."""
        if not unit_id:
            return None
        logger.info(f"Fetching property unit: {unit_id}")
        return self._request("GET", f"/v1/PropertyUnits/{unit_id}")

    def delete_property_unit(self, unit_id: str) -> bool:
        """Soft-delete a property unit."""
        if not unit_id:
            return False
        try:
            logger.info(f"Deleting property unit: {unit_id}")
            self._request("DELETE", f"/v1/PropertyUnits/{unit_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete property unit {unit_id}: {e}")
            return False

    def get_units_for_building(self, building_id: str) -> List[Dict[str, Any]]:
        """Get all property units for a building."""
        if not building_id:
            logger.warning("No building_id provided")
            return []

        logger.info(f"Fetching units for building: {building_id}")
        result = self._request("GET", f"/v1/PropertyUnits/building/{building_id}")

        if isinstance(result, dict):
            units = result.get("items", [])
        elif isinstance(result, list):
            units = result
        else:
            logger.warning(f"Unexpected response format: {type(result)}")
            return []

        logger.info(f"Fetched {len(units)} units for building {building_id}")
        return units if isinstance(units, list) else []

    def create_household(self, household_data: Dict[str, Any], survey_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new household."""
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
        """Delete a household."""
        if not household_id or not survey_id:
            raise ValueError("household_id and survey_id are required")
        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}"
        self._request("DELETE", endpoint)
        logger.info(f"Household {household_id} deleted from API")
        return True

    def get_households_for_unit(self, unit_id: str) -> List[Dict[str, Any]]:
        """Get all households for a property unit."""
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

    def create_person(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new person."""
        api_data = self._convert_person_to_api_format(person_data)
        logger.info(f"Creating person: {api_data.get('fullName', 'N/A')}")
        result = self._request("POST", "/v1/Persons", json_data=api_data)
        logger.info(f"Person created: {result.get('id', 'N/A')}")
        return result

    def create_person_in_household(self, person_data: Dict[str, Any], survey_id: str, household_id: str,
                                   is_contact_person: bool = False) -> Dict[str, Any]:
        """Create a new person in a household."""
        if not survey_id or not household_id:
            raise ValueError("survey_id and household_id are required")

        api_data = self._convert_person_to_api_format_with_household(person_data, survey_id, household_id)
        if is_contact_person:
            api_data["isContactPerson"] = True
        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}/persons"

        logger.info(f"Creating person in household via {endpoint} (isContactPerson={is_contact_person})")
        result = self._request("POST", endpoint, json_data=api_data)
        logger.info(f"Person created in household: {result.get('id', 'N/A')}")
        return result

    def get_persons_for_household(self, survey_id: str, household_id: str) -> List[Dict[str, Any]]:
        """Get all persons in a household."""
        if not survey_id or not household_id:
            logger.warning(f"Missing survey_id or household_id")
            return []

        endpoint = f"/v2/surveys/{survey_id}/households/{household_id}/persons"
        logger.info(f"Fetching persons for household: {household_id}")

        try:
            result = self._request("GET", endpoint)

            if isinstance(result, dict):
                persons = result.get("items", [])
            elif isinstance(result, list):
                persons = result
            else:
                logger.warning(f"Unexpected response format: {type(result)}")
                return []

            logger.info(f"Fetched {len(persons)} persons for household {household_id}")
            return persons if isinstance(persons, list) else []

        except Exception as e:
            logger.error(f"Failed to fetch persons: {e}")
            return []

    def link_person_to_unit(self, survey_id: str, unit_id: str, relation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Link a person to a property unit with relation type."""
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
        """Update person within survey context."""
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

    def get_persons(self, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """
        Get paginated list of all persons.

        Endpoint: GET /api/v1/Persons
        """
        params = {"page": page, "pageSize": page_size}
        return self._request("GET", "/v1/Persons", params=params)

    def delete_person(self, person_id: str) -> None:
        """Soft delete a person via DELETE /api/v1/Persons/{id}."""
        if not person_id:
            raise ValueError("person_id is required")

        logger.info(f"Deleting person {person_id}")
        self._request("DELETE", f"/v1/Persons/{person_id}")
        logger.info(f"Person {person_id} deleted successfully")

    def delete_relation(self, survey_id: str, relation_id: str) -> bool:
        """Delete a person-property relation."""
        if not survey_id or not relation_id:
            raise ValueError("survey_id and relation_id are required")

        logger.info(f"Deleting relation {relation_id} from survey {survey_id}")
        self._request("DELETE", f"/v1/Surveys/{survey_id}/relations/{relation_id}")
        logger.info(f"Relation {relation_id} deleted successfully")
        return True

    def update_relation(self, survey_id: str, relation_id: str, relation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a person-property relation."""
        if not survey_id or not relation_id:
            raise ValueError("survey_id and relation_id are required")

        api_data = {}
        if 'propertyUnitId' in relation_data:
            api_data["propertyUnitId"] = relation_data['propertyUnitId']
        if 'rel_type' in relation_data or 'relationship_type' in relation_data:
            api_data["relationType"] = int(relation_data.get('rel_type') or relation_data.get('relationship_type', 99))
        if 'contract_type' in relation_data or 'occupancy_type' in relation_data:
            val = relation_data.get('contract_type') or relation_data.get('occupancy_type')
            if val:
                api_data["occupancyType"] = int(val)
        if 'ownership_share' in relation_data:
            api_data["ownershipShare"] = relation_data['ownership_share'] / 2400.0
        if 'has_documents' in relation_data:
            api_data["hasEvidence"] = relation_data['has_documents']

        logger.info(f"Updating relation {relation_id}: {api_data}")
        result = self._request("PATCH", f"/v1/Surveys/{survey_id}/relations/{relation_id}", json_data=api_data)
        logger.info(f"Relation {relation_id} updated successfully")
        return result

    def get_unit_relations(self, survey_id: str, unit_id: str) -> List[Dict[str, Any]]:
        """Get person-property relations for a unit within a survey."""
        if not survey_id or not unit_id:
            raise ValueError("survey_id and unit_id are required")
        result = self._request(
            "GET", f"/v2/surveys/{survey_id}/property-units/{unit_id}/relations"
        )
        return result.get("items", []) if isinstance(result, dict) else result

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
        """Upload a tenure evidence document."""
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
        description: str = "",
        document_type: int = 1,
        document_issued_date: str = "",
        document_expiry_date: str = "",
        issuing_authority: str = "",
        document_reference_number: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        """Upload an identification document for a person.

        Returns: EvidenceDto
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
            "SurveyId": (None, survey_id),
            "PersonId": (None, person_id),
            "Description": (None, description or file_name),
        }
        if document_issued_date:
            dt = f"{document_issued_date}T00:00:00Z" if "T" not in document_issued_date else document_issued_date
            form_fields["DocumentIssuedDate"] = (None, dt)
        if document_expiry_date:
            dt = f"{document_expiry_date}T00:00:00Z" if "T" not in document_expiry_date else document_expiry_date
            form_fields["DocumentExpiryDate"] = (None, dt)
        if issuing_authority:
            form_fields["IssuingAuthority"] = (None, issuing_authority)
        if document_reference_number:
            form_fields["DocumentReferenceNumber"] = (None, document_reference_number)
        if notes:
            form_fields["Notes"] = (None, notes)

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

    def update_identification_document(
        self,
        survey_id: str,
        document_id: str,
        person_id: str = "",
        file_path: str = None,
        description: str = "",
        notes: str = "",
        document_type: int = None,
        document_issued_date: str = "",
        document_expiry_date: str = "",
        issuing_authority: str = "",
        document_reference_number: str = "",
    ) -> Dict[str, Any]:
        """Update an existing identification document.

        Endpoint changed in v1.7: /identification-documents/{id} (was /evidence/identification/{id})
        Returns: IdentificationDocumentDto
        """
        import os
        import mimetypes

        if not survey_id or not document_id:
            raise ValueError("survey_id and document_id are required")

        endpoint = f"/v1/Surveys/{survey_id}/identification-documents/{document_id}"
        url = f"{self.base_url}{endpoint}"

        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

        form_fields = {}
        if person_id:
            form_fields["PersonId"] = (None, person_id)
        if description:
            form_fields["Description"] = (None, description)
        if notes:
            form_fields["Notes"] = (None, notes)
        if document_type is not None:
            form_fields["DocumentType"] = (None, str(document_type))
        if document_issued_date:
            dt = f"{document_issued_date}T00:00:00Z" if "T" not in document_issued_date else document_issued_date
            form_fields["DocumentIssuedDate"] = (None, dt)
        if document_expiry_date:
            dt = f"{document_expiry_date}T00:00:00Z" if "T" not in document_expiry_date else document_expiry_date
            form_fields["DocumentExpiryDate"] = (None, dt)
        if issuing_authority:
            form_fields["IssuingAuthority"] = (None, issuing_authority)
        if document_reference_number:
            form_fields["DocumentReferenceNumber"] = (None, document_reference_number)

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
            logger.info(f"Identification document {document_id} updated")
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
            logger.error(f"Network error during identification document update: {e}")
            raise NetworkException(message=str(e), original_error=e)

    def get_person_identification_documents(
        self, person_id: str
    ) -> List[Dict[str, Any]]:
        """Get all identification documents for a person.

        Endpoint: GET /v1/Surveys/persons/{personId}/identification-documents
        Returns: List[IdentificationDocumentDto]
        """
        if not person_id:
            raise ValueError("person_id is required")
        endpoint = f"/v1/Surveys/persons/{person_id}/identification-documents"
        result = self._request("GET", endpoint)
        if isinstance(result, dict):
            return result.get("items", result.get("$values", []))
        return result if isinstance(result, list) else []

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
        """Update an existing tenure document."""
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

    def link_evidence_to_relation(
        self, survey_id: str, evidence_id: str, relation_id: str
    ) -> Dict[str, Any]:
        """
        Link an existing evidence record to a person-property relation.

        Endpoint: POST /api/v1/Surveys/{surveyId}/evidence/{evidenceId}/link-to-relation
        """
        if not survey_id or not evidence_id or not relation_id:
            raise ValueError("survey_id, evidence_id, and relation_id are required")
        endpoint = f"/v1/Surveys/{survey_id}/evidence/{evidence_id}/link-to-relation"
        body = {"personPropertyRelationId": relation_id}
        logger.info(f"Linking evidence {evidence_id} to relation {relation_id}")
        result = self._request("POST", endpoint, json_data=body)
        logger.info(f"Evidence linked: {result.get('id', 'N/A')}")
        return result

    def get_survey_evidences(self, survey_id: str, evidence_type: str = None) -> List[Dict[str, Any]]:
        """Get all evidence records for a survey."""
        params = {}
        if evidence_type:
            params["evidenceType"] = evidence_type
        result = self._request("GET", f"/v2/surveys/{survey_id}/evidence", params=params)
        if isinstance(result, dict):
            return result.get("items", [])
        return result if isinstance(result, list) else []

    def get_relation_evidences(
        self,
        survey_id: str,
        relation_id: str,
        evidence_type: str = None,
        only_current: bool = True
    ) -> List[Dict[str, Any]]:
        """Get evidence records for a person-property relation."""
        params = {"onlyCurrentVersions": str(only_current).lower()}
        if evidence_type:
            params["evidenceType"] = evidence_type
        result = self._request(
            "GET", f"/v2/surveys/{survey_id}/relations/{relation_id}/evidences", params=params
        )
        if isinstance(result, dict):
            return result.get("items", [])
        return result if isinstance(result, list) else []

    def get_evidence_by_id(self, evidence_id: str) -> Dict[str, Any]:
        """Get evidence metadata by ID. Tries v1 then v2."""
        try:
            return self._request("GET", f"/v1/Surveys/evidence/{evidence_id}")
        except Exception:
            return self._request("GET", f"/v2/surveys/evidence/{evidence_id}")

    def delete_evidence(self, survey_id: str, evidence_id: str) -> bool:
        """Soft delete an evidence record."""
        self._request("DELETE", f"/v1/Surveys/{survey_id}/evidence/{evidence_id}")
        return True

    def download_evidence(self, evidence_id: str, save_path: str) -> str:
        """Download an evidence file to disk. Tries v1 then v2 endpoints."""
        import os
        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "*/*"
        }

        urls = [
            f"{self.base_url}/v1/Surveys/evidence/{evidence_id}/download",
        ]

        last_error = None
        for url in urls:
            try:
                logger.info(f"[API REQ] GET {url.replace(self.base_url, '')}")
                response = requests.get(url, headers=headers, timeout=self.config.timeout, verify=False)
                response.raise_for_status()
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                if os.path.getsize(save_path) > 0:
                    logger.info(f"Evidence downloaded: {evidence_id} -> {save_path}")
                    return save_path
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                logger.debug(f"[API ERR] {status_code} {url.replace(self.base_url, '')}")
                last_error = e
                continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                logger.error(f"Network error during download: {e}")
                raise NetworkException(message=str(e), original_error=e)

        if last_error:
            status_code = last_error.response.status_code if last_error.response is not None else 0
            raise ApiException(message=str(last_error), status_code=status_code)
        raise ApiException(message=f"No download URL succeeded for {evidence_id}", status_code=404)

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

        ownership_share_raw = relation_data.get('ownership_share', None)
        if ownership_share_raw is not None and ownership_share_raw > 0:
            ownership_share_decimal = ownership_share_raw / 2400.0
            if ownership_share_decimal > 1.0:
                logger.warning(f"OwnershipShare: {ownership_share_raw}/2400={ownership_share_decimal} > 1.0, capping")
                ownership_share_decimal = 1.0
            logger.info(f"OwnershipShare: input={ownership_share_raw} shares -> API={ownership_share_decimal}")
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

        if relation_data.get('is_contact'):
            api_data["isContact"] = True

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

    def create_survey(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new survey."""
        api_data = self._convert_survey_to_api_format(survey_data)
        logger.info(f"Creating survey for building: {api_data.get('buildingId', 'N/A')}")
        result = self._request("POST", "/v1/Surveys", json_data=api_data)
        logger.info(f"Survey created: {result.get('id', 'N/A')}")
        return result

    def create_office_survey(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new office survey."""
        api_data = self._convert_survey_to_api_format(survey_data)
        logger.info(f"Creating office survey for building: {api_data.get('buildingId', 'N/A')}")
        result = self._request("POST", "/v1/Surveys/office", json_data=api_data)
        logger.info(f"Office survey created: {result.get('id', 'N/A')}")
        return result

    def create_contact_person(self, survey_id: str, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set the contact person for an office survey."""
        if not survey_id:
            raise ValueError("survey_id is required")

        import re as _re

        father_name = person_data.get("father_name_ar", "").strip()
        if not father_name:
            father_name = "-"

        mother_name = person_data.get("mother_name_ar", "").strip()
        if not mother_name:
            mother_name = "-"

        api_data: Dict[str, Any] = {
            "command": "CreateContactPerson",
            "firstNameArabic":  person_data.get("first_name_ar", "").strip(),
            "fatherNameArabic": father_name,
            "familyNameArabic": person_data.get("last_name_ar", "").strip(),
            "motherNameArabic": mother_name,
        }

        if person_data.get("national_id"):
            api_data["nationalId"] = person_data["national_id"].strip()

        gender = person_data.get("gender")
        if gender is not None:
            try:
                api_data["gender"] = int(gender)
            except (ValueError, TypeError):
                pass

        nationality = person_data.get("nationality")
        if nationality is not None:
            try:
                api_data["nationality"] = int(nationality)
            except (ValueError, TypeError):
                pass

        birth_date = (person_data.get("birth_date") or "").strip()
        if birth_date:
            api_data["dateOfBirth"] = f"{birth_date}T00:00:00Z" if "T" not in birth_date else birth_date
        elif person_data.get("birth_year"):
            api_data["dateOfBirth"] = f"{person_data['birth_year']}-01-01T00:00:00Z"

        email = person_data.get("email", "").strip()
        if email and _re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            api_data["email"] = email

        if person_data.get("phone"):
            api_data["mobileNumber"] = person_data["phone"].strip()
        if person_data.get("landline"):
            api_data["phoneNumber"] = person_data["landline"].strip()

        endpoint = f"/v1/Surveys/{survey_id}/contact-person"
        logger.info(f"Setting contact person for survey {survey_id}")
        result = self._request("POST", endpoint, json_data=api_data)
        logger.info(f"Contact person set: {result.get('id', 'N/A')}")
        return result

    def get_contact_person(self, survey_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the contact person for a survey."""
        if not survey_id:
            return None
        endpoint = f"/v1/Surveys/{survey_id}/contact-person"
        return self._request("GET", endpoint)

    def get_office_surveys(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        building_id: Optional[str] = None,
        clerk_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        reference_code: Optional[str] = None,
        contact_person_name: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_direction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of office surveys."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = status
        if building_id:
            params["buildingId"] = building_id
        if clerk_id:
            params["clerkId"] = clerk_id
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if reference_code:
            params["referenceCode"] = reference_code
        if contact_person_name:
            params["contactPersonName"] = contact_person_name
        if sort_by:
            params["sortBy"] = sort_by
        if sort_direction:
            params["sortDirection"] = sort_direction
        return self._request("GET", "/v1/Surveys/office", params=params)

    def get_office_survey_detail(self, survey_id: str) -> Dict[str, Any]:
        """Get full office survey detail."""
        if not survey_id:
            raise ValueError("survey_id is required")
        return self._request("GET", f"/v1/Surveys/office/{survey_id}")

    def delete_survey(self, survey_id: str) -> bool:
        """Delete a survey."""
        if not survey_id:
            raise ValueError("survey_id is required")
        self._request("DELETE", f"/v1/Surveys/office/{survey_id}")
        logger.info(f"Survey {survey_id} deleted")
        return True

    def finalize_office_survey(self, survey_id: str, finalize_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process claims for an office survey."""
        if not survey_id:
            raise ValueError("survey_id is required")

        api_data = {
            "surveyId": survey_id,
            "finalNotes": "",
            "durationMinutes": 10,
            "autoCreateClaim": True,
            "caseStatus": 1
        }

        if finalize_options:
            if 'finalNotes' in finalize_options:
                api_data['finalNotes'] = finalize_options['finalNotes'] or ""
            if 'durationMinutes' in finalize_options:
                api_data['durationMinutes'] = finalize_options['durationMinutes'] or 10
            if 'autoCreateClaim' in finalize_options:
                api_data['autoCreateClaim'] = finalize_options['autoCreateClaim']

        logger.info(f"Processing claims for office survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/office/{survey_id}/process-claims", json_data=api_data)
        logger.info(f"Office survey claims processed successfully")
        return result

    def finalize_survey_status(self, survey_id: str) -> Dict[str, Any]:
        """Finalize an office survey."""
        if not survey_id:
            raise ValueError("survey_id is required")

        logger.info(f"Finalizing office survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/office/{survey_id}/finalize")
        logger.info(f"Office survey finalized successfully")
        return result

    def cancel_survey(self, survey_id: str, reason: str) -> Dict[str, Any]:
        """Cancel a draft survey."""
        if not survey_id:
            raise ValueError("survey_id is required")
        payload = {"surveyId": survey_id, "reason": reason}
        logger.info(f"Cancelling survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/{survey_id}/cancel", json_data=payload)
        logger.info(f"Survey {survey_id} cancelled")
        return result

    def revert_survey_to_draft(self, survey_id: str, reason: str) -> Dict[str, Any]:
        """Revert a Finalized survey back to Draft. Admin/DataManager only.

        Endpoint: POST /v1/Surveys/{id}/revert-to-draft
        Permission: Surveys_EditAll
        """
        if not survey_id:
            raise ValueError("survey_id is required")
        payload = {"reason": reason}
        logger.info(f"Reverting survey {survey_id} to draft")
        result = self._request("POST", f"/v1/Surveys/{survey_id}/revert-to-draft", json_data=payload)
        logger.info(f"Survey {survey_id} reverted to draft")
        return result

    def mark_survey_obstructed(self, survey_id: str) -> Dict[str, Any]:
        """Mark a Draft survey as Obstructed.

        Endpoint: POST /v1/Surveys/{id}/mark-as-obstructed
        """
        if not survey_id:
            raise ValueError("survey_id is required")
        logger.info(f"Marking survey {survey_id} as obstructed")
        result = self._request("POST", f"/v1/Surveys/{survey_id}/mark-as-obstructed")
        logger.info(f"Survey {survey_id} marked as obstructed")
        return result

    def resume_obstructed_survey(self, survey_id: str) -> Dict[str, Any]:
        """Resume an Obstructed survey back to Draft.

        Endpoint: POST /v1/Surveys/{id}/resume
        """
        if not survey_id:
            raise ValueError("survey_id is required")
        logger.info(f"Resuming obstructed survey {survey_id}")
        result = self._request("POST", f"/v1/Surveys/{survey_id}/resume")
        logger.info(f"Survey {survey_id} resumed")
        return result

    # ── Case endpoints ──────────────────────────────────────────────

    def get_cases(
        self,
        building_code: str = "",
        unit_identifier: str = "",
        building_id: str = "",
        status: int = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List cases with filtering.

        Endpoint: GET /v1/Cases
        Permission: Claims_ViewAll (1000)
        """
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if building_code:
            params["buildingCode"] = building_code
        if unit_identifier:
            params["unitIdentifier"] = unit_identifier
        if building_id:
            params["buildingId"] = building_id
        if status is not None:
            params["status"] = status
        return self._request("GET", "/v1/Cases", params=params)

    def get_case_by_id(self, case_id: str) -> Dict[str, Any]:
        """Get full case details by ID.

        Endpoint: GET /v1/Cases/{id}
        Returns: Full CaseDto with surveyIds, claimIds, personPropertyRelationCount
        """
        if not case_id:
            raise ValueError("case_id is required")
        return self._request("GET", f"/v1/Cases/{case_id}")

    def get_case_by_property_unit(self, property_unit_id: str) -> Optional[Dict[str, Any]]:
        """Get case for a specific property unit.

        Endpoint: GET /v1/Cases/by-property-unit/{propertyUnitId}
        Returns: CaseDto or None (204 = no case exists yet)
        """
        if not property_unit_id:
            raise ValueError("property_unit_id is required")
        try:
            return self._request("GET", f"/v1/Cases/by-property-unit/{property_unit_id}")
        except ApiException as e:
            if e.status_code == 204:
                return None
            raise

    def set_case_editable(self, case_id: str, is_editable: bool) -> None:
        """Toggle the editable flag on a case. Admin/DataManager only.

        Endpoint: PUT /v1/Cases/{id}/editable
        Permission: Claims_Transition (1011)
        """
        if not case_id:
            raise ValueError("case_id is required")
        self._request("PUT", f"/v1/Cases/{case_id}/editable", json_data={"isEditable": is_editable})
        logger.info(f"Case {case_id} editable set to {is_editable}")

    # ── End Case endpoints ────────────────────────────────────────

    def save_draft_to_backend(self, survey_id: str, draft_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Save survey progress as draft on backend."""
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

    def get_governorates(self) -> List[Dict[str, Any]]:
        """Get all governorates."""
        return self._request("GET", "/v1/administrative-divisions/governorates")

    def get_districts(self, governorate_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get districts, optionally filtered by governorate."""
        params = {}
        if governorate_code:
            params["governorateCode"] = governorate_code
        return self._request("GET", "/v1/administrative-divisions/districts", params=params)

    def get_sub_districts(self, governorate_code: Optional[str] = None,
                          district_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get sub-districts, optionally filtered by governorate and district."""
        params = {}
        if governorate_code:
            params["governorateCode"] = governorate_code
        if district_code:
            params["districtCode"] = district_code
        return self._request("GET", "/v1/administrative-divisions/sub-districts", params=params)

    def get_communities(self, governorate_code: Optional[str] = None,
                        district_code: Optional[str] = None,
                        sub_district_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get communities, optionally filtered by governorate, district, and sub-district."""
        params = {}
        if governorate_code:
            params["governorateCode"] = governorate_code
        if district_code:
            params["districtCode"] = district_code
        if sub_district_code:
            params["subDistrictCode"] = sub_district_code
        return self._request("GET", "/v1/administrative-divisions/communities", params=params)

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
        result = self._request("GET", "/v2/neighborhoods/by-bounds", params=params)
        neighborhoods = result.get("items", []) if isinstance(result, dict) else result
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
        result = self._request("GET", "/v2/neighborhoods", params=params)
        neighborhoods = result.get("items", []) if isinstance(result, dict) else result
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

    def get_persons(
        self,
        search: Optional[str] = None,
        national_id: Optional[str] = None,
        household_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Get persons list with optional filters.

        Endpoint: GET /v1/Persons
        """
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if search:
            params["search"] = search
        if national_id:
            params["nationalId"] = national_id
        if household_id:
            params["householdId"] = household_id
        logger.info(f"Fetching persons with filters: {params}")
        return self._request("GET", "/v1/Persons", params=params) or {}

    def get_person_by_id(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Get a single person by UUID."""
        from services.exceptions import ApiException
        try:
            return self._request("GET", f"/v1/Persons/{person_id}")
        except ApiException as e:
            if e.status_code == 404:
                logger.warning(f"Person {person_id} not found (404)")
                return None
            raise

    def get_households(
        self,
        unit_id: Optional[str] = None,
        building_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Get households list with optional filters."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if unit_id:
            params["propertyUnitId"] = unit_id
        if building_id:
            params["buildingId"] = building_id
        logger.info(f"Fetching households with filters: {params}")
        return self._request("GET", "/v1/Households", params=params) or {}

    def get_claims_summaries(
        self,
        claim_status: Optional[int] = None,
        claim_source: Optional[int] = None,
        created_by_user_id: Optional[str] = None,
        survey_visit_id: Optional[str] = None,
        building_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get claim summaries for list pages."""
        params = {
            "page": page,
            "pageSize": page_size,
        }
        if claim_status is not None:
            params["caseStatus"] = claim_status
        if claim_source is not None:
            params["claimSource"] = claim_source
        if created_by_user_id:
            params["createdByUserId"] = created_by_user_id
        if survey_visit_id:
            params["surveyVisitId"] = survey_visit_id
        if building_code:
            params["buildingCode"] = building_code

        logger.info(f"Fetching claims summaries with filters: {params or 'none'}")
        result = self._request("GET", "/v2/claims/summaries", params=params)

        if isinstance(result, dict):
            summaries = result.get("items", [])
        elif isinstance(result, list):
            summaries = result
        else:
            summaries = []

        # Fallback: if backend ignores pagination, slice locally
        if len(summaries) > page_size:
            start = (page - 1) * page_size
            summaries = summaries[start:start + page_size]

        logger.info(f"Fetched {len(summaries)} claim summaries")
        return summaries

    def get_claims(
        self,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        property_unit_id: Optional[str] = None,
        primary_claimant_id: Optional[str] = None,
        has_conflicts: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get all claims with filters."""
        params = {}
        if status is not None:
            params["CaseStatus"] = status
        if priority is not None:
            params["Priority"] = priority
        if property_unit_id:
            params["PropertyUnitId"] = property_unit_id
        if primary_claimant_id:
            params["PrimaryClaimantId"] = primary_claimant_id
        if has_conflicts is not None:
            params["HasConflicts"] = str(has_conflicts).lower()

        logger.info(f"Fetching claims with filters: {params or 'none'}")
        result = self._request("GET", "/v1/Claims", params=params)
        if isinstance(result, list):
            claims = result
        elif isinstance(result, dict):
            claims = result.get("items", result.get("data", []))
        else:
            claims = []
        logger.info(f"Fetched {len(claims)} claims")
        return claims

    def get_claim_by_id(self, claim_id: str) -> Dict[str, Any]:
        """Get full claim details by ID."""
        if not claim_id:
            raise ValueError("claim_id is required")

        logger.info(f"Fetching claim details: {claim_id}")
        result = self._request("GET", f"/v1/Claims/{claim_id}")
        logger.info(f"Fetched claim: {result.get('claimNumber', 'N/A')}")
        return result

    def get_claim_by_number(self, claim_number: str) -> Dict[str, Any]:
        """Get claim by claim number."""
        if not claim_number:
            raise ValueError("claim_number is required")
        return self._request("GET", f"/v1/Claims/by-number/{claim_number}")

    def delete_claim(self, claim_id: str) -> bool:
        """Delete a claim."""
        if not claim_id:
            raise ValueError("claim_id is required")
        self._request("DELETE", f"/v1/Claims/{claim_id}")
        logger.info(f"Claim {claim_id} deleted")
        return True

    def update_claim(self, claim_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing claim."""
        if not claim_id:
            raise ValueError("claim_id is required")
        payload = {"claimId": claim_id, **update_data}
        logger.info(f"Updating claim: {claim_id}")
        return self._request("PUT", f"/v1/Claims/{claim_id}", json_data=payload)

    def submit_claim(self, claim_id: str, user_id: str) -> Dict[str, Any]:
        """Submit claim for processing."""
        return self._request("PUT", f"/v1/Claims/{claim_id}/submit",
                             json_data={"claimId": claim_id, "submittedByUserId": user_id})

    def verify_claim(self, claim_id: str, user_id: str, notes: str = "") -> Dict[str, Any]:
        """Verify claim."""
        return self._request("PUT", f"/v1/Claims/{claim_id}/verify",
                             json_data={"claimId": claim_id, "verifiedByUserId": user_id,
                                        "verificationNotes": notes})

    def assign_claim(self, claim_id: str, user_id: str,
                     target_date: Optional[str] = None) -> Dict[str, Any]:
        """Assign claim to case officer."""
        payload = {"claimId": claim_id, "assignToUserId": user_id}
        if target_date:
            payload["targetCompletionDate"] = target_date
        return self._request("PUT", f"/v1/Claims/{claim_id}/assign", json_data=payload)

    def get_all_users(
        self,
        page: int = 1,
        page_size: int = 100,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get all users with optional filters."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if role:
            params["role"] = role
        if is_active is not None:
            params["isActive"] = is_active
        return self._request("GET", "/v1/Users", params=params) or {}

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID."""
        return self._request("GET", f"/v1/Users/{user_id}") or {}

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user."""
        return self._request("POST", "/v1/Users", data) or {}

    def update_user(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a user."""
        return self._request("PUT", f"/v1/Users/{user_id}", data) or {}

    def delete_user(self, user_id: str) -> None:
        """Delete a user."""
        self._request("DELETE", f"/v1/Users/{user_id}")

    def activate_user(self, user_id: str) -> Dict[str, Any]:
        """Activate a user."""
        return self._request("PUT", f"/v1/Users/{user_id}/activate") or {}

    def deactivate_user(self, user_id: str) -> Dict[str, Any]:
        """Deactivate a user."""
        return self._request("PUT", f"/v1/Users/{user_id}/deactivate") or {}

    def unlock_user(self, user_id: str) -> Dict[str, Any]:
        """Unlock a user account."""
        return self._request("PUT", f"/v1/Users/{user_id}/unlock") or {}

    def admin_change_user_password(self, user_id: str, new_password: str) -> Dict[str, Any]:
        """Change a user's password (admin)."""
        return self._request("POST", "/v1/Auth/change-password", {
            "userId": user_id,
            "newPassword": new_password,
            "confirmPassword": new_password,
        }) or {}

    def grant_user_permissions(self, user_id: str, permissions: Dict[str, Any]) -> Dict[str, Any]:
        """Grant permissions to a user."""
        return self._request("POST", f"/v1/Users/{user_id}/permissions", permissions) or {}

    def revoke_user_permission(self, user_id: str, permission: str) -> None:
        """DELETE /v1/Users/{id}/permissions/{permission}"""
        self._request("DELETE", f"/v1/Users/{user_id}/permissions/{permission}")

    def get_vocabulary_terms(self, vocab_name: str) -> Dict[str, Any]:
        """GET /v1/Vocabularies/{name}"""
        return self._request("GET", f"/v1/Vocabularies/{vocab_name}") or {}

    def create_vocabulary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v1/Vocabularies"""
        return self._request("POST", "/v1/Vocabularies", data) or {}

    def create_vocabulary_term(self, vocab_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v1/Vocabularies/{name}/terms"""
        return self._request("POST", f"/v1/Vocabularies/{vocab_name}/terms", data) or {}

    def update_vocabulary_term(self, vocab_name: str, code: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PUT /v1/Vocabularies/{name}/terms/{code}"""
        return self._request("PUT", f"/v1/Vocabularies/{vocab_name}/terms/{code}", data) or {}

    def activate_vocabulary_term(self, vocab_name: str, code: str) -> Dict[str, Any]:
        """PATCH /v1/Vocabularies/{name}/terms/{code}/activate"""
        return self._request("PATCH", f"/v1/Vocabularies/{vocab_name}/terms/{code}/activate") or {}

    def deactivate_vocabulary_term(self, vocab_name: str, code: str) -> Dict[str, Any]:
        """PATCH /v1/Vocabularies/{name}/terms/{code}/deactivate"""
        return self._request("PATCH", f"/v1/Vocabularies/{vocab_name}/terms/{code}/deactivate") or {}

    def export_vocabularies(self) -> Any:
        """GET /v1/Vocabularies/export"""
        return self._request("GET", "/v1/Vocabularies/export")

    def import_vocabularies(self, data: Any) -> Dict[str, Any]:
        """POST /v1/Vocabularies/import"""
        return self._request("POST", "/v1/Vocabularies/import", data) or {}

    def import_upload(self, file_path: str) -> Dict[str, Any]:
        """
        Upload a .uhc package for import.
        Performs integrity checks (checksum, signature, vocabulary compatibility).

        Args:
            file_path: Path to the .uhc file

        Returns:
            Package metadata with ID

        Endpoint: POST /api/v1/import/upload
        """
        import os
        import mimetypes
        import requests

        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        url = f"{self.config.base_url}/v1/import/upload"
        headers = self._headers()
        headers.pop("Content-Type", None)

        logger.info(f"Uploading import package: {file_name}")
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_name, f, mime_type)}
                response = requests.post(
                    url, files=files, headers=headers,
                    timeout=self.config.timeout, verify=False
                )
            response.raise_for_status()
            result = response.json() if response.text else {}
            logger.info(f"Import package uploaded: {result}")
            return result
        except requests.exceptions.HTTPError as e:
            response_data = None
            try:
                response_data = e.response.json()
            except Exception:
                pass
            raise ApiException(
                status_code=e.response.status_code if e.response else 0,
                message=str(e),
                response_data=response_data
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise NetworkException(message=str(e), original_error=e)

    def get_import_packages(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all import packages with optional filtering."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if status_filter:
            params["status"] = status_filter
        return self._request("GET", "/v1/import/packages", params=params)

    def get_import_package(self, package_id: str) -> Dict[str, Any]:
        """Get import package details by ID."""
        return self._request("GET", f"/v1/import/packages/{package_id}")

    def stage_import_package(self, package_id: str) -> Dict[str, Any]:
        """Trigger staging and row-level validation."""
        logger.info(f"Staging import package: {package_id}")
        return self._request("POST", f"/v1/import/packages/{package_id}/stage")

    def get_validation_report(self, package_id: str) -> Dict[str, Any]:
        """Get the current validation report for a package."""
        return self._request("GET", f"/v1/import/packages/{package_id}/validation-report")

    def get_staged_entities(self, package_id: str) -> List[Dict[str, Any]]:
        """Get all staged entities for a package."""
        return self._request("GET", f"/v1/import/packages/{package_id}/staged-entities")

    def detect_duplicates(self, package_id: str) -> Dict[str, Any]:
        """Trigger duplicate detection."""
        logger.info(f"Detecting duplicates for package: {package_id}")
        return self._request("POST", f"/v1/import/packages/{package_id}/detect-duplicates")

    def approve_import_package(self, package_id: str) -> Dict[str, Any]:
        """Approve staging records for commit."""
        logger.info(f"Approving import package: {package_id}")
        return self._request(
            "POST",
            f"/v1/import/packages/{package_id}/approve",
            json_data={"packageId": package_id}
        )

    def commit_import_package(self, package_id: str) -> Dict[str, Any]:
        """Commit approved staging records to production tables."""
        logger.info(f"Committing import package: {package_id}")
        return self._request(
            "POST",
            f"/v1/import/packages/{package_id}/commit",
            json_data={"packageId": package_id}
        )

    def get_commit_report(self, package_id: str) -> Dict[str, Any]:
        """Get the commit report for an import package."""
        return self._request("GET", f"/v1/import/packages/{package_id}/commit-report")

    def reset_commit(self, package_id: str) -> Dict[str, Any]:
        """Reset a package back to ReadyToCommit status."""
        logger.info(f"Resetting commit for package: {package_id}")
        return self._request("POST", f"/v1/import/packages/{package_id}/reset-commit")

    def cancel_import_package(self, package_id: str, reason: str = "Cancelled by user") -> Dict[str, Any]:
        """Cancel an active import package."""
        logger.info(f"Cancelling import package: {package_id}")
        return self._request(
            "POST",
            f"/v1/import/packages/{package_id}/cancel",
            json_data={"packageId": package_id, "reason": reason},
        )

    def quarantine_import_package(self, package_id: str, reason: str = "") -> Dict[str, Any]:
        """Quarantine a suspicious import package."""
        logger.info(f"Quarantining import package: {package_id}")
        body = {
            "importPackageId": package_id,
            "reason": reason or "حجر يدوي",
        }
        return self._request("POST", f"/v1/import/packages/{package_id}/quarantine", json_data=body)

    def get_conflicts(
        self,
        page: int = 1,
        page_size: int = 20,
        conflict_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        import_package_id: Optional[str] = None,
        assigned_to_user_id: Optional[str] = None,
        is_escalated: Optional[bool] = None,
        is_overdue: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_descending: bool = True,
    ) -> Dict[str, Any]:
        """List conflict resolution queue with filtering."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if conflict_type:
            params["conflictType"] = conflict_type
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        if import_package_id:
            params["importPackageId"] = import_package_id
        if assigned_to_user_id:
            params["assignedToUserId"] = assigned_to_user_id
        if is_escalated is not None:
            params["isEscalated"] = is_escalated
        if is_overdue is not None:
            params["isOverdue"] = is_overdue
        if sort_by:
            params["sortBy"] = sort_by
        params["sortDescending"] = sort_descending
        return self._request("GET", "/v1/conflicts", params=params)

    def get_conflicts_summary(self) -> Dict[str, Any]:
        """Get aggregate conflict counts for dashboard."""
        return self._request("GET", "/v1/conflicts/summary")

    def get_property_duplicates(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get property duplicate conflicts."""
        params = {"page": page, "pageSize": page_size}
        return self._request("GET", "/v1/conflicts/property-duplicates", params=params)

    def get_person_duplicates(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get person duplicate conflicts."""
        params = {"page": page, "pageSize": page_size}
        return self._request("GET", "/v1/conflicts/person-duplicates", params=params)

    def get_escalated_conflicts(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get escalated conflicts awaiting senior review."""
        params = {"page": page, "pageSize": page_size}
        return self._request("GET", "/v1/conflicts/escalated", params=params)

    def get_conflict_details(self, conflict_id: str) -> Dict[str, Any]:
        """
        Get side-by-side comparison details for a conflict.

        Endpoint: GET /api/v1/conflicts/{id}/details
        """
        return self._request("GET", f"/v1/conflicts/{conflict_id}/details")

    def get_conflict_document_comparison(self, conflict_id: str) -> Dict[str, Any]:
        """
        Get document comparison for a conflict.

        Endpoint: GET /api/v1/conflicts/{id}/document-comparison
        """
        return self._request("GET", f"/v1/conflicts/{conflict_id}/document-comparison")

    def merge_conflict(
        self, conflict_id: str, master_record_id: str, justification: str = ""
    ) -> Dict[str, Any]:
        """
        Merge duplicate records (choose master record).

        Endpoint: POST /api/v1/conflicts/{id}/merge
        """
        body = {"masterRecordId": master_record_id, "reason": justification}
        return self._request("POST", f"/v1/conflicts/{conflict_id}/merge", json_data=body)

    def keep_separate_conflict(
        self, conflict_id: str, justification: str = ""
    ) -> Dict[str, Any]:
        """
        Mark conflict records as intentionally separate.

        Endpoint: POST /api/v1/conflicts/{id}/keep-separate
        """
        body = {"reason": justification}
        return self._request("POST", f"/v1/conflicts/{conflict_id}/keep-separate", json_data=body)

    def resolve_conflict(
        self, conflict_id: str, resolution_type: str = "", justification: str = ""
    ) -> Dict[str, Any]:
        """
        General conflict resolution.

        Endpoint: POST /api/v1/conflicts/{id}/resolve
        """
        body = {"resolutionType": resolution_type, "reason": justification}
        return self._request("POST", f"/v1/conflicts/{conflict_id}/resolve", json_data=body)

    def escalate_conflict(
        self, conflict_id: str, justification: str = ""
    ) -> Dict[str, Any]:
        """
        Escalate conflict to supervisor for review.

        Endpoint: POST /api/v1/conflicts/{id}/escalate
        """
        body = {"reason": justification}
        return self._request("POST", f"/v1/conflicts/{conflict_id}/escalate", json_data=body)

_api_client_instance: Optional[TRRCMSApiClient] = None


def get_api_client(config: Optional[ApiConfig] = None) -> Optional[TRRCMSApiClient]:
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
