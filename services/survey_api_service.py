# -*- coding: utf-8 -*-
"""
Survey API Service - Handles survey operations via REST API.

Connects to /api/v1/Surveys endpoint.
"""

import json
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class SurveyApiService:
    """
    Service for survey operations via REST API.

    Uses the API_BASE_URL from Config to connect to /api/v1/Surveys endpoint.
    """

    def __init__(self, auth_token: Optional[str] = None):
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
            endpoint: API endpoint (e.g., "/v1/Surveys/office")
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

    def create_office_survey(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new office survey via API.

        POST /v1/Surveys/office
        Body: {
            "buildingId": "uuid",
            "surveyDate": "2026-02-05T21:21:46.318Z"
        }

        Args:
            survey_data: Dictionary with survey data

        Returns:
            Dict with success status and created survey data or error
        """
        api_data = self._to_api_format(survey_data)

        logger.info(f"Creating office survey via API: {api_data}")
        logger.info(f"POST URL: {self.base_url}/v1/Surveys/office")

        response = self._make_request("POST", "/v1/Surveys/office", data=api_data)

        if response.get("success"):
            logger.info("Office survey created successfully via API")
            return response
        else:
            logger.error(f"Failed to create office survey: {response.get('error')}")
            return response

    def _to_api_format(self, survey_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert app survey data format to API format.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        building_id = survey_data.get('building_uuid') or survey_data.get('buildingId', '')

        api_data = {
            "buildingId": building_id,
            "surveyDate": survey_data.get('survey_date') or now,
        }

        return api_data
