# -*- coding: utf-8 -*-
"""
Building API Service - Fetches buildings from REST API.

Connects to /api/v1/Buildings endpoint to get all buildings instead of SQLite.
"""

import json
import ssl
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.config import Config
from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingApiService:
    """
    Service for fetching buildings from REST API.

    Uses the API_BASE_URL from Config to connect to /api/v1/Buildings endpoint.
    """

    def __init__(self, auth_token: Optional[str] = None):
        """
        Initialize the Building API Service.

        Args:
            auth_token: Optional JWT/Bearer token for authentication
        """
        self.base_url = Config.API_BASE_URL.rstrip('/')
        self.timeout = Config.API_TIMEOUT
        self.max_retries = Config.API_MAX_RETRIES
        self._auth_token = auth_token

        # Create SSL context that doesn't verify certificates (for development with localhost)
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def set_auth_token(self, token: str):
        """Set the authentication token."""
        self._auth_token = token

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TRRCMS-Desktop/1.0"
        }

        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/v1/Buildings")
            data: Request body data (for POST/PUT)
            params: Query parameters

        Returns:
            Dict with response data or error
        """
        url = f"{self.base_url}{endpoint}"

        if params:
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}
            if params:
                url = f"{url}?{urlencode(params)}"

        headers = self._get_headers()

        # Prepare request body
        body = None
        if data:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')

        try:
            request = urllib.request.Request(
                url,
                data=body,
                headers=headers,
                method=method
            )

            logger.debug(f"API Request: {method} {url}")

            with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                response_data = response.read().decode('utf-8')

                if response_data:
                    result = json.loads(response_data)
                    logger.debug(f"API Response: {type(result)}")
                    return {"success": True, "data": result}
                else:
                    return {"success": True, "data": []}

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode('utf-8') if e.fp else ""
            except:
                pass

            logger.error(f"HTTP Error {e.code}: {e.reason} - {error_body}")
            return {
                "success": False,
                "error": f"HTTP Error {e.code}: {e.reason}",
                "error_code": f"E{e.code}",
                "details": error_body
            }

        except urllib.error.URLError as e:
            logger.error(f"Connection error: {e.reason}")
            return {
                "success": False,
                "error": f"Connection error: {e.reason}",
                "error_code": "E_CONN"
            }

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON response: {e}",
                "error_code": "E_JSON"
            }

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_code": "E500"
            }

    def get_all_buildings(self, search_text: str = None) -> List[Building]:
        """
        Get all buildings from the API.

        Args:
            search_text: Optional search text to filter buildings

        Returns:
            List of Building objects
        """
        params = {}
        if search_text:
            params["search"] = search_text

        response = self._make_request("GET", "/v1/Buildings", params=params if params else None)

        if not response.get("success"):
            logger.error(f"Failed to fetch buildings: {response.get('error')}")
            return []

        data = response.get("data", [])

        # Log the raw response for debugging
        logger.info(f"API Response type: {type(data)}")
        if isinstance(data, dict):
            logger.info(f"API Response keys: {list(data.keys())}")
        elif isinstance(data, list):
            logger.info(f"API Response: list with {len(data)} items")
            if data:
                logger.info(f"First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}")
                logger.info(f"First item: {data[0]}")

        # Handle case where API returns a wrapper object
        if isinstance(data, dict):
            # Check for common wrapper patterns
            logger.info(f"Response is dict, checking for wrapper patterns...")
            if "data" in data:
                data = data["data"]
                logger.info(f"Unwrapped 'data' key, now have {type(data)}")
            elif "buildings" in data:
                data = data["buildings"]
                logger.info(f"Unwrapped 'buildings' key, now have {type(data)}")
            elif "items" in data:
                data = data["items"]
                logger.info(f"Unwrapped 'items' key, now have {type(data)}")

        if not isinstance(data, list):
            logger.warning(f"Unexpected data format: {type(data)}")
            return []

        buildings = []
        for item in data:
            try:
                building = self._api_response_to_building(item)
                buildings.append(building)
            except Exception as e:
                logger.warning(f"Failed to parse building: {e}")
                continue

        logger.info(f"Fetched {len(buildings)} buildings from API")
        return buildings

    def get_building_by_id(self, building_id: str) -> Optional[Building]:
        """
        Get a building by its ID.

        Args:
            building_id: The building ID

        Returns:
            Building object or None
        """
        response = self._make_request("GET", f"/v1/Buildings/{building_id}")

        if not response.get("success"):
            logger.error(f"Failed to fetch building {building_id}: {response.get('error')}")
            return None

        data = response.get("data")
        if not data:
            return None

        try:
            return self._api_response_to_building(data)
        except Exception as e:
            logger.error(f"Failed to parse building: {e}")
            return None

    def create_building(self, building_data: Dict[str, Any]) -> Optional[Building]:
        """
        Create a new building via API.

        Args:
            building_data: Building data dictionary

        Returns:
            Created Building object or None
        """
        # Convert to API format
        api_data = self._building_data_to_api_format(building_data)

        response = self._make_request("POST", "/v1/Buildings", data=api_data)

        if not response.get("success"):
            logger.error(f"Failed to create building: {response.get('error')}")
            return None

        data = response.get("data")
        if not data:
            return None

        try:
            return self._api_response_to_building(data)
        except Exception as e:
            logger.error(f"Failed to parse created building: {e}")
            return None

    def update_building(self, building_id: str, building_data: Dict[str, Any]) -> Optional[Building]:
        """
        Update a building via API.

        Args:
            building_id: Building ID to update (should be UUID)
            building_data: Updated building data

        Returns:
            Updated Building object or None
        """
        # Convert to API format
        api_data = self._building_data_to_api_format(building_data)

        response = self._make_request("PUT", f"/v1/Buildings/{building_id}", data=api_data)

        if not response.get("success"):
            logger.error(f"Failed to update building: {response.get('error')}")
            return None

        data = response.get("data")
        if data:
            try:
                return self._api_response_to_building(data)
            except Exception as e:
                logger.error(f"Failed to parse updated building: {e}")

        # If no data returned, fetch the updated building
        return self.get_building_by_id(building_id)

    def delete_building(self, building_id: str) -> bool:
        """
        Delete a building via API.

        Args:
            building_id: Building ID to delete

        Returns:
            True if deleted successfully
        """
        response = self._make_request("DELETE", f"/v1/Buildings/{building_id}")
        return response.get("success", False)

    def search_buildings(self, building_id: str) -> List[Building]:
        """
        Search for buildings by building ID using the search API.

        POST /v1/Buildings/search
        Body: {"buildingId": "01010"}

        Args:
            building_id: Building ID to search for (partial match)

        Returns:
            List of matching Building objects
        """
        if not building_id or not building_id.strip():
            return []

        search_data = {"buildingId": building_id.strip()}

        response = self._make_request("POST", "/v1/Buildings/search", data=search_data)

        if not response.get("success"):
            logger.error(f"Failed to search buildings: {response.get('error')}")
            return []

        data = response.get("data", [])

        # Handle case where API returns a wrapper object
        if isinstance(data, dict):
            if "data" in data:
                data = data["data"]
            elif "buildings" in data:
                data = data["buildings"]
            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            logger.warning(f"Unexpected search response format: {type(data)}")
            return []

        buildings = []
        for item in data:
            try:
                building = self._api_response_to_building(item)
                buildings.append(building)
            except Exception as e:
                logger.warning(f"Failed to parse building from search: {e}")
                continue

        logger.info(f"Search found {len(buildings)} buildings for query: {building_id}")
        return buildings

    def _api_response_to_building(self, data: Dict[str, Any]) -> Building:
        """
        Convert API response to Building object.

        Maps API field names to Building model field names.
        """
        # Map API field names to Building model field names
        # The API might use different naming conventions (camelCase vs snake_case)
        field_mapping = {
            # UUID fields
            "buildingUuid": "building_uuid",
            "building_uuid": "building_uuid",
            "id": "building_uuid",

            # Building ID
            "buildingId": "building_id",
            "building_id": "building_id",
            "buildingIdFormatted": "building_id_formatted",
            "building_id_formatted": "building_id_formatted",

            # Administrative codes
            "governorateCode": "governorate_code",
            "governorate_code": "governorate_code",
            "governorateName": "governorate_name",
            "governorate_name": "governorate_name",
            "governorateNameAr": "governorate_name_ar",
            "governorate_name_ar": "governorate_name_ar",

            "districtCode": "district_code",
            "district_code": "district_code",
            "districtName": "district_name",
            "district_name": "district_name",
            "districtNameAr": "district_name_ar",
            "district_name_ar": "district_name_ar",

            "subdistrictCode": "subdistrict_code",
            "subdistrict_code": "subdistrict_code",
            "subdistrictName": "subdistrict_name",
            "subdistrict_name": "subdistrict_name",
            "subdistrictNameAr": "subdistrict_name_ar",
            "subdistrict_name_ar": "subdistrict_name_ar",

            "communityCode": "community_code",
            "community_code": "community_code",
            "communityName": "community_name",
            "community_name": "community_name",
            "communityNameAr": "community_name_ar",
            "community_name_ar": "community_name_ar",

            "neighborhoodCode": "neighborhood_code",
            "neighborhood_code": "neighborhood_code",
            "neighborhoodName": "neighborhood_name",
            "neighborhood_name": "neighborhood_name",
            "neighborhoodNameAr": "neighborhood_name_ar",
            "neighborhood_name_ar": "neighborhood_name_ar",

            "buildingNumber": "building_number",
            "building_number": "building_number",

            # Building attributes
            "buildingType": "building_type",
            "building_type": "building_type",
            "buildingStatus": "building_status",
            "building_status": "building_status",
            "status": "building_status",  # API uses "status" not "buildingStatus"

            "numberOfUnits": "number_of_units",
            "number_of_units": "number_of_units",
            "numberOfApartments": "number_of_apartments",
            "number_of_apartments": "number_of_apartments",
            "numberOfShops": "number_of_shops",
            "number_of_shops": "number_of_shops",
            "numberOfFloors": "number_of_floors",
            "number_of_floors": "number_of_floors",

            # Geometry
            "latitude": "latitude",
            "longitude": "longitude",
            "geoLocation": "geo_location",
            "geo_location": "geo_location",

            # Metadata
            "createdAt": "created_at",
            "createdAtUtc": "created_at",  # API uses this format
            "created_at": "created_at",
            "updatedAt": "updated_at",
            "lastModifiedAtUtc": "updated_at",  # API uses this format
            "updated_at": "updated_at",
            "createdBy": "created_by",
            "created_by": "created_by",
            "updatedBy": "updated_by",
            "updated_by": "updated_by",

            # Legacy
            "legacyStdmId": "legacy_stdm_id",
            "legacy_stdm_id": "legacy_stdm_id",
        }

        # Check for building type in API response with various key names
        bt_value = None
        for key in ["buildingType", "building_type", "BuildingType", "type"]:
            if key in data:
                bt_value = data[key]
                break

        # Map the data
        mapped_data = {}
        for api_key, value in data.items():
            model_key = field_mapping.get(api_key, api_key)
            if model_key in Building.__dataclass_fields__:
                mapped_data[model_key] = value

        # Building type mapping from API string values to integer codes
        # API returns: "Residential", "Commercial", "MixedUse", "Industrial"
        # UI expects: 1, 2, 3, 4
        building_type_str_to_int = {
            "residential": 1,
            "commercial": 2,
            "mixeduse": 3,
            "mixed": 3,
            "industrial": 4,
        }

        # Handle building_type - convert API string to integer
        if "building_type" in mapped_data:
            bt = mapped_data["building_type"]

            if isinstance(bt, int) and 1 <= bt <= 4:
                # Already an integer, keep it
                pass
            elif isinstance(bt, str):
                # API returns string like "Commercial", "Residential", etc.
                bt_lower = bt.lower().replace("_", "").replace(" ", "")
                mapped_data["building_type"] = building_type_str_to_int.get(bt_lower, 1)
            else:
                # Default to 1 (Residential) if invalid
                logger.warning(f"Invalid building_type value: {bt}, defaulting to 1")
                mapped_data["building_type"] = 1
        elif bt_value is not None:
            # Building type not found in mapped data, use the value we found earlier
            if isinstance(bt_value, int) and 1 <= bt_value <= 4:
                mapped_data["building_type"] = bt_value
            elif isinstance(bt_value, str):
                bt_lower = bt_value.lower().replace("_", "").replace(" ", "")
                mapped_data["building_type"] = building_type_str_to_int.get(bt_lower, 1)
            else:
                mapped_data["building_type"] = 1

        # Building status mapping from API string values to integer codes
        # API returns: "Intact", "MinorDamage", "ModerateDamage", "MajorDamage", "SeverelyDamaged",
        #              "Destroyed", "UnderConstruction", "Abandoned", "Unknown"
        # UI expects: 1, 2, 3, 4, 5, 6, 7, 8, 99
        building_status_str_to_int = {
            "intact": 1,
            "minordamage": 2,
            "moderatedamage": 3,
            "majordamage": 4,
            "severelydamaged": 5,
            "destroyed": 6,
            "underconstruction": 7,
            "abandoned": 8,
            "unknown": 99,
        }

        # Handle building_status - convert API string to integer
        if "building_status" in mapped_data:
            bs = mapped_data["building_status"]
            if isinstance(bs, int) and (1 <= bs <= 8 or bs == 99):
                # Already an integer, keep it
                pass
            elif isinstance(bs, str):
                # API returns string like "Intact", "MinorDamage", etc.
                bs_lower = bs.lower().replace("_", "").replace(" ", "")
                mapped_data["building_status"] = building_status_str_to_int.get(bs_lower, 1)
            else:
                mapped_data["building_status"] = 1

        # Handle datetime fields
        for dt_field in ["created_at", "updated_at"]:
            if dt_field in mapped_data and isinstance(mapped_data[dt_field], str):
                try:
                    # Handle ISO format with or without timezone
                    dt_str = mapped_data[dt_field]
                    if dt_str.endswith('Z'):
                        dt_str = dt_str[:-1]
                    if '+' in dt_str:
                        dt_str = dt_str.split('+')[0]
                    mapped_data[dt_field] = datetime.fromisoformat(dt_str)
                except ValueError:
                    mapped_data[dt_field] = datetime.now()

        # Ensure required fields have defaults
        if not mapped_data.get("created_at"):
            mapped_data["created_at"] = datetime.now()
        if not mapped_data.get("updated_at"):
            mapped_data["updated_at"] = datetime.now()

        return Building(**mapped_data)

    def _building_data_to_api_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Building data to API format.

        Maps snake_case field names to camelCase for API.
        API expects buildingType and buildingStatus as integers.
        """
        # Map snake_case to camelCase
        field_mapping = {
            "governorate_code": "governorateCode",
            "district_code": "districtCode",
            "subdistrict_code": "subDistrictCode",  # Note: API uses subDistrictCode
            "community_code": "communityCode",
            "neighborhood_code": "neighborhoodCode",
            "building_number": "buildingNumber",
            "building_type": "buildingType",
            "building_status": "buildingStatus",
            "number_of_units": "numberOfPropertyUnits",  # API uses numberOfPropertyUnits
            "number_of_apartments": "numberOfApartments",
            "number_of_shops": "numberOfShops",
            "number_of_floors": "numberOfFloors",
            "latitude": "latitude",
            "longitude": "longitude",
            "location_description": "locationDescription",
            "notes": "notes",
        }

        # Building type enum mapping (Python string value -> API integer)
        # Used for backward compatibility with old string codes
        # 1 = Residential, 2 = Commercial, 3 = MixedUse, 4 = Industrial
        building_type_string_mapping = {
            "residential": 1,
            "commercial": 2,
            "mixed_use": 3,
            "mixed": 3,
            "industrial": 4,
            "public": 1,  # Map to residential as fallback
        }

        # Building status enum mapping (Python string value -> API integer)
        # API: 1=Intact, 2=MinorDamage, 3=ModerateDamage, 4=MajorDamage, 5=SeverelyDamaged,
        #      6=Destroyed, 7=UnderConstruction, 8=Abandoned, 99=Unknown
        building_status_string_mapping = {
            "intact": 1,
            "standing": 1,
            "minor_damage": 2,
            "minordamage": 2,
            "moderate_damage": 3,
            "moderatedamage": 3,
            "damaged": 3,
            "partially_damaged": 3,
            "major_damage": 4,
            "majordamage": 4,
            "severely_damaged": 5,
            "severelydamaged": 5,
            "destroyed": 6,
            "demolished": 6,
            "rubble": 6,
            "under_construction": 7,
            "underconstruction": 7,
            "abandoned": 8,
            "unknown": 99,
        }

        api_data = {}

        # Only include fields that the API expects
        for key, value in data.items():
            if key not in field_mapping:
                continue  # Skip fields not in mapping

            api_key = field_mapping[key]

            # Handle building_type - accept both integer and string values
            if key == "building_type":
                if isinstance(value, int) and 1 <= value <= 4:
                    # Already an integer, use it directly
                    pass
                elif isinstance(value, str):
                    # Convert string to integer
                    value = building_type_string_mapping.get(value, 1)
                else:
                    value = 1  # Default to Residential

            # Handle building_status - accept both integer and string values
            if key == "building_status":
                if isinstance(value, int) and (1 <= value <= 8 or value == 99):
                    # Already an integer, use it directly
                    pass
                elif isinstance(value, str):
                    # Convert string to integer
                    value = building_status_string_mapping.get(value.lower().replace("_", "").replace(" ", ""), 1)
                else:
                    value = 1  # Default to Intact

            # Skip None values for optional fields
            if value is not None:
                api_data[api_key] = value

        # Ensure required fields have default values
        if "buildingType" not in api_data:
            api_data["buildingType"] = 1  # Residential

        if "buildingStatus" not in api_data:
            api_data["buildingStatus"] = 1  # Intact

        # Ensure numeric fields are integers
        for int_field in ["numberOfPropertyUnits", "numberOfApartments", "numberOfShops", "numberOfFloors"]:
            if int_field in api_data and api_data[int_field] is not None:
                api_data[int_field] = int(api_data[int_field])

        return api_data
