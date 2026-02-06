# -*- coding: utf-8 -*-
"""
PropertyUnit API Service - Handles property unit operations via REST API.

Connects to /api/v1/PropertyUnits endpoint.
"""

import json
import ssl
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import Config
from models.unit import PropertyUnit
from utils.logger import get_logger

logger = get_logger(__name__)


class PropertyUnitApiService:
    """
    Service for property unit operations via REST API.

    Uses the API_BASE_URL from Config to connect to /api/v1/PropertyUnits endpoint.
    """

    def __init__(self, auth_token: Optional[str] = None):
        """
        Initialize the PropertyUnit API Service.

        Args:
            auth_token: Optional JWT/Bearer token for authentication
        """
        self.base_url = Config.API_BASE_URL.rstrip('/')
        self.timeout = Config.API_TIMEOUT
        self._auth_token = auth_token

        # Create SSL context that doesn't verify certificates (for development)
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
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/v1/PropertyUnits")
            data: Request body data (for POST/PUT)

        Returns:
            Dict with response data or error
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

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
            if data:
                logger.debug(f"Request body: {json.dumps(data, ensure_ascii=False)}")

            with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                response_data = response.read().decode('utf-8')

                if response_data:
                    result = json.loads(response_data)
                    logger.debug(f"API Response: {type(result)}")
                    return {"success": True, "data": result}
                else:
                    return {"success": True, "data": None}

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

    def create_property_unit(self, unit_data: Dict[str, Any], survey_id: str = None) -> Dict[str, Any]:
        """
        Create a new property unit via API.

        POST /v1/Surveys/{surveyId}/property-units
        Body: {
            "surveyId": "uuid",
            "unitIdentifier": "string",
            "floorNumber": 0,
            "unitType": 0,
            "status": 0,
            "areaSquareMeters": 0,
            "numberOfRooms": 0,
            "description": "string"
        }

        Args:
            unit_data: Dictionary with unit data (snake_case keys)
            survey_id: Survey UUID (required for the survey-scoped endpoint)

        Returns:
            Dict with success status and created unit data or error
        """
        # Convert from app format to API format
        api_data = self._to_api_format(unit_data, survey_id=survey_id)

        # Use survey-scoped endpoint if survey_id is provided
        if survey_id:
            endpoint = f"/v1/Surveys/{survey_id}/property-units"
        else:
            endpoint = "/v1/PropertyUnits"

        logger.info(f"Creating property unit via {endpoint}: {api_data}")

        response = self._make_request("POST", endpoint, data=api_data)

        if response.get("success"):
            logger.info(f"Property unit created successfully")
            return response
        else:
            logger.error(f"Failed to create property unit: {response.get('error')}")
            return response

    def link_unit_to_survey(self, survey_id: str, unit_id: str) -> Dict[str, Any]:
        """
        Link an existing property unit to a survey.

        POST /v1/Surveys/{surveyId}/property-units/{unitId}/link

        Args:
            survey_id: Survey UUID
            unit_id: Property Unit UUID

        Returns:
            Dict with success status and updated survey data or error
        """
        if not survey_id or not unit_id:
            logger.warning(f"Missing survey_id ({survey_id}) or unit_id ({unit_id}) for link")
            return {"success": False, "error": "Missing surveyId or unitId", "error_code": "E_PARAM"}

        endpoint = f"/v1/Surveys/{survey_id}/property-units/{unit_id}/link"
        logger.info(f"Linking unit {unit_id} to survey {survey_id} via POST {endpoint}")

        response = self._make_request("POST", endpoint)

        if response.get("success"):
            logger.info(f"Unit {unit_id} linked to survey {survey_id} successfully")
            return response
        else:
            logger.error(f"Failed to link unit to survey: {response.get('error')}")
            return response

    def get_all(self, limit: int = 1000) -> List[PropertyUnit]:
        """
        Get all property units.

        GET /v1/PropertyUnits

        Args:
            limit: Maximum number of units to return (not used by API but kept for compatibility)

        Returns:
            List of PropertyUnit objects
        """
        logger.info("Fetching all property units from API")
        response = self._make_request("GET", "/v1/PropertyUnits")

        if not response.get("success"):
            logger.error(f"Failed to fetch property units: {response.get('error')}")
            return []

        data = response.get("data", [])
        logger.debug(f"API response data type: {type(data)}")

        # Handle wrapper object
        if isinstance(data, dict):
            logger.debug(f"Response is dict with keys: {list(data.keys())}")
            if "data" in data:
                data = data["data"]
            elif "units" in data:
                data = data["units"]
            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        logger.info(f"Found {len(data)} property units")

        units = []
        for item in data:
            try:
                unit = self._api_response_to_unit(item)
                units.append(unit)
            except Exception as e:
                logger.warning(f"Failed to parse unit: {e}")
                continue

        return units

    def get_units_for_building(self, building_id: str) -> List[PropertyUnit]:
        """
        Get all property units for a building.

        GET /v1/PropertyUnits/building/{buildingId}

        Args:
            building_id: Building UUID

        Returns:
            List of PropertyUnit objects
        """
        if not building_id:
            logger.warning("No building_id provided for get_units_for_building")
            return []

        logger.info(f"Fetching units for building: {building_id}")
        response = self._make_request("GET", f"/v1/PropertyUnits/building/{building_id}")

        if not response.get("success"):
            logger.error(f"Failed to fetch units for building {building_id}: {response.get('error')}")
            return []

        data = response.get("data", [])
        logger.debug(f"API response data type: {type(data)}")

        # Handle wrapper object
        if isinstance(data, dict):
            logger.debug(f"Response is dict with keys: {list(data.keys())}")
            if "data" in data:
                data = data["data"]
            elif "units" in data:
                data = data["units"]
            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        logger.info(f"Found {len(data)} units for building {building_id}")

        units = []
        for item in data:
            try:
                unit = self._api_response_to_unit(item)
                units.append(unit)
            except Exception as e:
                logger.warning(f"Failed to parse unit: {e}")
                continue

        return units

    def _to_api_format(self, unit_data: Dict[str, Any], survey_id: str = None) -> Dict[str, Any]:
        """
        Convert app unit data format to API format.

        App uses snake_case, API uses camelCase.
        App may use string types, API expects integer codes.
        """
        # Unit type mapping (string to int if needed)
        unit_type_map = {
            "apartment": 1,
            "shop": 2,
            "office": 3,
            "warehouse": 4,
            "other": 5,
        }

        # Unit status mapping (string to int if needed)
        unit_status_map = {
            "occupied": 1,
            "vacant": 2,
            "damaged": 3,
            "underrenovation": 4,
            "uninhabitable": 5,
            "locked": 6,
            "unknown": 99,
            # Legacy mappings
            "intact": 1,  # Map old "intact" to "occupied"
            "destroyed": 3,  # Map old "destroyed" to "damaged"
        }

        # Get unit type - handle both int and string
        unit_type = unit_data.get('unit_type', 1)
        if isinstance(unit_type, str):
            unit_type = unit_type_map.get(unit_type.lower(), 5)
        elif not isinstance(unit_type, int):
            unit_type = 1

        # Get status - handle both int and string
        status = unit_data.get('apartment_status') or unit_data.get('status', 1)
        if isinstance(status, str):
            status = unit_status_map.get(status.lower().replace("_", ""), 99)
        elif not isinstance(status, int):
            status = 1

        # Get area - ensure it's a number or 0
        area = unit_data.get('area_sqm') or unit_data.get('areaSquareMeters', 0)
        try:
            area = float(area) if area else 0
        except (ValueError, TypeError):
            area = 0

        # Get number of rooms
        rooms = unit_data.get('number_of_rooms') or unit_data.get('numberOfRooms', 0)
        try:
            rooms = int(rooms) if rooms else 0
        except (ValueError, TypeError):
            rooms = 0

        # Build API format
        api_data = {
            "unitIdentifier": unit_data.get('unit_number') or unit_data.get('apartment_number') or unit_data.get('unitIdentifier', ''),
            "floorNumber": int(unit_data.get('floor_number', 0)),
            "unitType": unit_type,
            "status": status,
            "areaSquareMeters": area,
            "numberOfRooms": rooms,
            "description": unit_data.get('property_description') or unit_data.get('description', '')
        }

        # Use surveyId for survey-scoped endpoint, buildingId for legacy endpoint
        if survey_id:
            api_data["surveyId"] = survey_id
        else:
            api_data["buildingId"] = unit_data.get('building_uuid') or unit_data.get('buildingId', '')

        return api_data

    def _api_response_to_unit(self, data: Dict[str, Any]) -> PropertyUnit:
        """
        Convert API response to PropertyUnit object.

        API response format:
        {
            "id": "uuid",
            "buildingId": "uuid",
            "buildingNumber": "00001",
            "unitIdentifier": "1A",
            "floorNumber": 1,
            "unitType": "Apartment",
            "status": "Occupied",
            "areaSquareMeters": 85.5,
            "numberOfRooms": 3,
            "description": "شقة سكنية",
            "createdAtUtc": "2026-01-29T12:00:00Z"
        }
        """
        # Unit type mapping (string or int to app format)
        unit_type_map_str = {
            "apartment": "apartment",
            "shop": "shop",
            "office": "office",
            "warehouse": "warehouse",
            "other": "other",
        }
        unit_type_map_int = {
            1: "apartment",
            2: "shop",
            3: "office",
            4: "warehouse",
            5: "other",
        }

        # Unit status mapping (string or int to app format)
        unit_status_map_str = {
            "occupied": "occupied",
            "vacant": "vacant",
            "damaged": "damaged",
            "underrenovation": "under_renovation",
            "under_renovation": "under_renovation",
            "uninhabitable": "uninhabitable",
            "locked": "locked",
            "unknown": "unknown",
        }
        unit_status_map_int = {
            1: "occupied",
            2: "vacant",
            3: "damaged",
            4: "under_renovation",
            5: "uninhabitable",
            6: "locked",
            99: "unknown",
        }

        # Get unit type - handle string (from API) or int
        unit_type_raw = data.get('unitType') or data.get('unit_type', 'other')
        if isinstance(unit_type_raw, str):
            unit_type = unit_type_map_str.get(unit_type_raw.lower(), "other")
        else:
            unit_type = unit_type_map_int.get(unit_type_raw, "other")

        # Get status - handle string (from API) or int
        status_raw = data.get('status') or data.get('apartment_status', 'unknown')
        if isinstance(status_raw, str):
            status = unit_status_map_str.get(status_raw.lower().replace(" ", ""), "unknown")
        else:
            status = unit_status_map_int.get(status_raw, "unknown")

        # Get number of rooms
        rooms = data.get('numberOfRooms') or data.get('number_of_rooms')
        rooms_str = str(rooms) if rooms else ""

        # Build unit_id from buildingNumber + unitIdentifier if not present
        unit_identifier = data.get('unitIdentifier') or data.get('unit_number', '')
        building_number = data.get('buildingNumber') or ''
        building_id = data.get('buildingId') or data.get('building_id', '')

        # Create a display unit_id
        if building_number and unit_identifier:
            unit_id = f"{building_number}-{unit_identifier}"
        else:
            unit_id = data.get('unit_id') or unit_identifier

        unit = PropertyUnit(
            unit_uuid=data.get('id') or data.get('unit_uuid') or data.get('unitId', ''),
            unit_id=unit_id,
            building_id=building_id,
            unit_type=unit_type,
            unit_number=unit_identifier,
            floor_number=data.get('floorNumber') or data.get('floor_number', 0),
            apartment_number=rooms_str,  # Using numberOfRooms as apartment_number for display
            apartment_status=status,
            property_description=data.get('description') or data.get('property_description', ''),
            area_sqm=data.get('areaSquareMeters') or data.get('area_sqm'),
        )

        return unit
