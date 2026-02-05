# -*- coding: utf-8 -*-
"""
Person API Service - Handles person operations via REST API.

Connects to /api/v1/Surveys/{surveyId}/households/{householdId}/persons endpoint.
"""

import json
import ssl
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonApiService:
    """
    Service for person operations via REST API.

    Uses the API_BASE_URL from Config to connect to
    /api/v1/Surveys/{surveyId}/households/{householdId}/persons endpoint.
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
            endpoint: API endpoint
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

    def create_person(self, person_data: Dict[str, Any], survey_id: str = None, household_id: str = None) -> Dict[str, Any]:
        """
        Create a new person in a household via API.

        POST /v1/Surveys/{surveyId}/households/{householdId}/persons
        Body: {
            "surveyId": "uuid",
            "householdId": "uuid",
            "familyNameArabic": "string",
            "firstNameArabic": "string",
            "fatherNameArabic": "string",
            "motherNameArabic": "string",
            "nationalId": "string",
            "yearOfBirth": 0,
            "email": "string",
            "mobileNumber": "string",
            "phoneNumber": "string",
            "relationshipToHead": "string"
        }

        Args:
            person_data: Dictionary with person data (snake_case keys)
            survey_id: Survey UUID (required for the survey-scoped endpoint)
            household_id: Household UUID (required for the household-scoped endpoint)

        Returns:
            Dict with success status and created person data or error
        """
        api_data = self._to_api_format(person_data, survey_id=survey_id, household_id=household_id)

        if survey_id and household_id:
            endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}/persons"
        else:
            endpoint = "/v1/Persons"

        logger.info(f"Creating person via {endpoint}: {api_data}")

        response = self._make_request("POST", endpoint, data=api_data)

        if response.get("success"):
            logger.info("Person created successfully via API")
            return response
        else:
            logger.error(f"Failed to create person: {response.get('error')}")
            return response

    def get_persons_for_household(self, survey_id: str, household_id: str) -> List[Dict[str, Any]]:
        """
        Get all persons in a household.

        GET /v1/Surveys/{surveyId}/households/{householdId}/persons

        Args:
            survey_id: Survey UUID
            household_id: Household UUID

        Returns:
            List of person dictionaries in app format
        """
        if not survey_id or not household_id:
            logger.warning(f"Missing survey_id ({survey_id}) or household_id ({household_id})")
            return []

        endpoint = f"/v1/Surveys/{survey_id}/households/{household_id}/persons"
        logger.info(f"Fetching persons via GET {endpoint}")

        response = self._make_request("GET", endpoint)

        if not response.get("success"):
            logger.error(f"Failed to fetch persons: {response.get('error')}")
            return []

        data = response.get("data", [])

        # Handle wrapper object
        if isinstance(data, dict):
            if "data" in data:
                data = data["data"]
            elif "persons" in data:
                data = data["persons"]
            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            logger.warning(f"Unexpected response format: {type(data)}")
            return []

        logger.info(f"Found {len(data)} persons for household {household_id}")

        persons = []
        for item in data:
            try:
                person = self._api_response_to_person(item)
                persons.append(person)
            except Exception as e:
                logger.warning(f"Failed to parse person: {e}")
                continue

        return persons

    def _api_response_to_person(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert API response to app person format.
        """
        return {
            "person_id": data.get("id") or data.get("personId", ""),
            "first_name": data.get("firstNameArabic", ""),
            "last_name": data.get("familyNameArabic", ""),
            "father_name": data.get("fatherNameArabic", ""),
            "mother_name": data.get("motherNameArabic", ""),
            "national_id": data.get("nationalId", ""),
            "birth_date": str(data.get("yearOfBirth", "")) + "-01-01" if data.get("yearOfBirth") else "",
            "email": data.get("email", ""),
            "phone": data.get("mobileNumber", ""),
            "landline": data.get("phoneNumber", ""),
            "relationship_type": data.get("relationshipToHead", ""),
            "gender": "male",
            "is_contact_person": False,
        }

    def link_person_to_unit(self, survey_id: str, unit_id: str, relation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Link a person to a property unit with relation type.

        POST /v1/Surveys/{surveyId}/property-units/{unitId}/relations
        Body: {
            "surveyId": "uuid",
            "personId": "uuid",
            "propertyUnitId": "uuid",
            "relationType": 1,
            "relationTypeOtherDesc": "string",
            "contractType": 1,
            "contractTypeOtherDesc": "string",
            "ownershipShare": 0,
            "contractDetails": "string",
            "startDate": "2026-02-05T09:57:14.054Z",
            "endDate": "2026-02-05T09:57:14.054Z",
            "notes": "string"
        }

        Args:
            survey_id: Survey UUID
            unit_id: Property Unit UUID
            relation_data: Dictionary with relation details

        Returns:
            Dict with success status and response data or error
        """
        if not survey_id or not unit_id:
            logger.warning(f"Missing survey_id ({survey_id}) or unit_id ({unit_id}) for relation link")
            return {"success": False, "error": "Missing surveyId or unitId", "error_code": "E_PARAM"}

        person_id = relation_data.get('person_id')
        if not person_id:
            logger.warning("Missing person_id in relation_data")
            return {"success": False, "error": "Missing personId", "error_code": "E_PARAM"}

        api_data = self._relation_to_api_format(relation_data, survey_id=survey_id, unit_id=unit_id)
        endpoint = f"/v1/Surveys/{survey_id}/property-units/{unit_id}/relations"

        logger.info(f"Linking person to unit via POST {endpoint}")
        logger.info(f"Relation data: {json.dumps(api_data, ensure_ascii=False, indent=2)}")

        response = self._make_request("POST", endpoint, data=api_data)

        if response.get("success"):
            logger.info("Person linked to unit successfully via API")
            return response
        else:
            error_details = response.get('details', '')
            logger.error(f"Failed to link person to unit: {response.get('error')}")
            logger.error(f"Error details: {error_details}")
            return response

    def _relation_to_api_format(self, relation_data: Dict[str, Any], survey_id: str = None, unit_id: str = None) -> Dict[str, Any]:
        """
        Convert app relation data format to API format for linking person to unit.

        Handles nullable DateTime fields (endDate) by sending null instead of empty string.
        Ensures all string fields are never None (uses empty string instead).
        """
        from datetime import datetime

        # Relation type mapping (string to int)
        relation_type_map = {
            "owner": 1,
            "co_owner": 2,
            "tenant": 3,
            "occupant": 4,
            "heir": 5,
            "guardian": 6,
            "other": 99,
        }

        # Contract type mapping (string to int)
        contract_type_map = {
            "عقد إيجار": 1,
            "عقد بيع": 2,
            "عقد شراكة": 3,
        }

        # Get relation type
        rel_type = relation_data.get('rel_type') or relation_data.get('relationship_type', '')

        # Log the relation type for debugging
        logger.debug(f"Relation type from data: {rel_type} (type: {type(rel_type)})")

        if isinstance(rel_type, str):
            relation_type_int = relation_type_map.get(rel_type, 99)
        elif isinstance(rel_type, int):
            relation_type_int = rel_type
        else:
            relation_type_int = 99

        # Validate that we have a valid relation type
        if relation_type_int == 99 and not rel_type:
            logger.warning("No relation type specified, defaulting to 99 (other)")

        # Get contract type
        contract_type_str = relation_data.get('contract_type', '')
        if isinstance(contract_type_str, str):
            contract_type_int = contract_type_map.get(contract_type_str, 0)
        elif isinstance(contract_type_str, int):
            contract_type_int = contract_type_str
        else:
            contract_type_int = 0

        # Format start date to ISO format
        # If no start date provided, use current date
        start_date = relation_data.get('start_date', '')
        if not start_date:
            # Use current date if no date provided
            start_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        elif 'T' not in start_date:
            # Format date string to ISO format
            start_date = f"{start_date}T00:00:00.000Z"

        # Ensure string fields are never None (API rejects null for string fields)
        contract_details = relation_data.get('evidence_desc') or ''
        notes = relation_data.get('notes') or ''
        relation_type_other = relation_data.get('relation_type_other_desc') or ''
        contract_type_other = relation_data.get('contract_type_other_desc') or ''

        # Build the command data - send as flat object (not wrapped)
        # The .NET API binds this to a command parameter.
        # startDate is required, endDate can be null for nullable DateTime fields.
        # UUIDs must be valid strings, not empty strings
        person_id = relation_data.get('person_id', '')
        if not person_id:
            logger.error("Missing person_id in relation data")
            raise ValueError("person_id is required for linking person to unit")

        if not survey_id:
            logger.error("Missing survey_id")
            raise ValueError("survey_id is required for linking person to unit")

        if not unit_id:
            logger.error("Missing unit_id")
            raise ValueError("unit_id is required for linking person to unit")

        api_data = {
            "surveyId": survey_id,
            "personId": person_id,
            "propertyUnitId": unit_id,
            "relationType": relation_type_int,
            "relationTypeOtherDesc": relation_type_other,
            "contractType": contract_type_int,
            "contractTypeOtherDesc": contract_type_other,
            "ownershipShare": relation_data.get('ownership_share', 0),
            "contractDetails": contract_details,
            "startDate": start_date,
            "endDate": None,
            "notes": notes,
        }

        return api_data

    def _to_api_format(self, person_data: Dict[str, Any], survey_id: str = None, household_id: str = None) -> Dict[str, Any]:
        """
        Convert app person data format to API format.

        App uses snake_case, API uses camelCase.
        Ensures required fields are never empty strings.
        """
        # Extract year from birth_date (app stores as "yyyy-MM-dd")
        year_of_birth = 0
        birth_date = person_data.get('birth_date', '')
        if birth_date:
            try:
                year_of_birth = int(birth_date.split('-')[0])
            except (ValueError, IndexError):
                year_of_birth = 0

        # Get names - ensure father name has a default value if empty
        father_name = person_data.get('father_name') or person_data.get('fatherNameArabic') or ''
        if not father_name.strip():
            father_name = '-'  # Default value for required field

        mother_name = person_data.get('mother_name') or person_data.get('motherNameArabic') or ''
        if not mother_name.strip():
            mother_name = '-'  # Default value for required field

        api_data = {
            "familyNameArabic": person_data.get('last_name') or person_data.get('familyNameArabic', ''),
            "firstNameArabic": person_data.get('first_name') or person_data.get('firstNameArabic', ''),
            "fatherNameArabic": father_name,
            "motherNameArabic": mother_name,
            "nationalId": person_data.get('national_id') or person_data.get('nationalId', ''),
            "yearOfBirth": year_of_birth,
            "email": person_data.get('email') or '',
            "mobileNumber": person_data.get('phone') or person_data.get('mobileNumber', ''),
            "phoneNumber": person_data.get('landline') or person_data.get('phoneNumber', ''),
            "relationshipToHead": person_data.get('relationship_type') or person_data.get('relationshipToHead', ''),
        }

        if survey_id:
            api_data["surveyId"] = survey_id
        if household_id:
            api_data["householdId"] = household_id

        return api_data
