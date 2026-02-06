# -*- coding: utf-8 -*-
"""
Household API Service - Handles household operations via REST API.

Connects to /api/v1/Households endpoint.
"""

import json
import ssl
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class HouseholdApiService:
    """
    Service for household operations via REST API.

    Uses the API_BASE_URL from Config to connect to /api/v1/Households endpoint.
    """

    def __init__(self, auth_token: Optional[str] = None):
        """
        Initialize the Household API Service.

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
            endpoint: API endpoint (e.g., "/v1/Households")
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

    def create_household(self, household_data: Dict[str, Any], survey_id: str = None) -> Dict[str, Any]:
        """
        Create a new household via API.

        POST /v1/Surveys/{surveyId}/households
        Body: {
            "surveyId": "uuid",
            "propertyUnitId": "uuid",
            "headOfHouseholdName": "string",
            "householdSize": 0,
            "notes": "string",
            "maleCount": 0,
            "femaleCount": 0,
            "maleChildCount": 0,
            "femaleChildCount": 0,
            "maleElderlyCount": 0,
            "femaleElderlyCount": 0,
            "maleDisabledCount": 0,
            "femaleDisabledCount": 0
        }

        Args:
            household_data: Dictionary with household data (snake_case keys)
            survey_id: Survey UUID (required for the survey-scoped endpoint)

        Returns:
            Dict with success status and created household data or error
        """
        # Convert from app format to API format
        api_data = self._to_api_format(household_data, survey_id=survey_id)

        # Use survey-scoped endpoint if survey_id is provided
        if survey_id:
            endpoint = f"/v1/Surveys/{survey_id}/households"
        else:
            endpoint = "/v1/Households"

        logger.info(f"Creating household via {endpoint}: {api_data}")

        response = self._make_request("POST", endpoint, data=api_data)

        if response.get("success"):
            logger.info("Household created successfully via API")
            return response
        else:
            logger.error(f"Failed to create household: {response.get('error')}")
            return response

    def get_households_for_unit(self, unit_id: str) -> List[Dict]:
        """
        Get all households for a property unit.

        Args:
            unit_id: Property Unit UUID

        Returns:
            List of household dictionaries
        """
        if not unit_id:
            logger.warning("No unit_id provided for get_households_for_unit")
            return []

        logger.info(f"Fetching households for unit: {unit_id}")
        response = self._make_request("GET", f"/v1/Households/unit/{unit_id}")

        if not response.get("success"):
            logger.error(f"Failed to fetch households for unit {unit_id}: {response.get('error')}")
            return []

        data = response.get("data", [])

        # Handle wrapper object
        if isinstance(data, dict):
            if "data" in data:
                data = data["data"]
            elif "households" in data:
                data = data["households"]
            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        logger.info(f"Found {len(data)} households for unit {unit_id}")
        return data

    def _to_api_format(self, household_data: Dict[str, Any], survey_id: str = None) -> Dict[str, Any]:
        """
        Convert app household data format to API format.

        App uses snake_case, API uses camelCase.
        """
        # Build API format matching the expected request structure
        api_data = {
            "propertyUnitId": household_data.get('property_unit_id') or household_data.get('unit_uuid') or household_data.get('propertyUnitId', ''),
            "headOfHouseholdName": household_data.get('head_name') or household_data.get('headOfHouseholdName', ''),
            "householdSize": int(household_data.get('size') or household_data.get('householdSize', 0)),
            "notes": household_data.get('notes') or household_data.get('notes', ''),
            "maleCount": int(household_data.get('adult_males') or household_data.get('maleCount', 0)),
            "femaleCount": int(household_data.get('adult_females') or household_data.get('femaleCount', 0)),
            "maleChildCount": int(household_data.get('male_children_under18') or household_data.get('maleChildCount', 0)),
            "femaleChildCount": int(household_data.get('female_children_under18') or household_data.get('femaleChildCount', 0)),
            "maleElderlyCount": int(household_data.get('male_elderly_over65') or household_data.get('maleElderlyCount', 0)),
            "femaleElderlyCount": int(household_data.get('female_elderly_over65') or household_data.get('femaleElderlyCount', 0)),
            "maleDisabledCount": int(household_data.get('disabled_males') or household_data.get('maleDisabledCount', 0)),
            "femaleDisabledCount": int(household_data.get('disabled_females') or household_data.get('femaleDisabledCount', 0)),
        }

        if survey_id:
            api_data["surveyId"] = survey_id

        return api_data

    def _api_response_to_household(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert API response to app household format.
        """
        return {
            "household_id": data.get('id') or data.get('household_id', ''),
            "property_unit_id": data.get('propertyUnitId') or data.get('property_unit_id', ''),
            "head_name": data.get('headOfHouseholdName') or data.get('head_name', ''),
            "size": data.get('householdSize') or data.get('size', 0),
            "adult_males": data.get('maleCount') or data.get('adult_males', 0),
            "adult_females": data.get('femaleCount') or data.get('adult_females', 0),
            "male_children_under18": data.get('maleChildCount') or data.get('male_children_under18', 0),
            "female_children_under18": data.get('femaleChildCount') or data.get('female_children_under18', 0),
            "male_elderly_over65": data.get('maleElderlyCount') or data.get('male_elderly_over65', 0),
            "female_elderly_over65": data.get('femaleElderlyCount') or data.get('female_elderly_over65', 0),
            "disabled_males": data.get('maleDisabledCount') or data.get('disabled_males', 0),
            "disabled_females": data.get('femaleDisabledCount') or data.get('disabled_females', 0),
            "notes": data.get('notes', '')
        }
