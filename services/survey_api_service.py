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

            # Debug print for tracing
            print(f"\n[API REQUEST] {method} {url}")
            print(f"[HEADERS] {headers}")
            if data:
                print(f"[BODY] {json.dumps(data, ensure_ascii=False, indent=2)}")

            logger.debug(f"API Request: {method} {url}")
            if data:
                logger.debug(f"Request body: {json.dumps(data, ensure_ascii=False)}")

            with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                response_data = response.read().decode('utf-8')
                print(f"[API RESPONSE STATUS] {response.status}")
                print(f"[API RESPONSE DATA] {response_data[:500] if response_data else 'EMPTY'}...")

                if response_data:
                    result = json.loads(response_data)
                    logger.debug(f"API Response: {type(result)}")
                    print(f"[API PARSED] success=True, data keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                    return {"success": True, "data": result}
                else:
                    print(f"[API PARSED] success=True, data=None (empty response)")
                    return {"success": True, "data": None}

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode('utf-8') if e.fp else ""
            except:
                pass

            print(f"[API HTTP ERROR] {e.code}: {e.reason}")
            print(f"[API ERROR BODY] {error_body}")
            logger.error(f"HTTP Error {e.code}: {e.reason} - {error_body}")
            return {
                "success": False,
                "error": f"HTTP Error {e.code}: {e.reason}",
                "error_code": f"E{e.code}",
                "details": error_body
            }

        except urllib.error.URLError as e:
            print(f"[API URL ERROR] {e.reason}")
            logger.error(f"Connection error: {e.reason}")
            return {
                "success": False,
                "error": f"Connection error: {e.reason}",
                "error_code": "E_CONN"
            }

        except json.JSONDecodeError as e:
            print(f"[API JSON ERROR] {e}")
            logger.error(f"Invalid JSON response: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON response: {e}",
                "error_code": "E_JSON"
            }

        except Exception as e:
            print(f"[API UNEXPECTED ERROR] {e}")
            import traceback
            traceback.print_exc()
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

    def finalize_office_survey(self, survey_id: str, finalize_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process claims for an office survey.

        POST /v1/Surveys/office/{id}/process-claims
        Body: {
            "surveyId": "uuid",
            "finalNotes": "string",
            "durationMinutes": 0,
            "autoCreateClaim": true
        }

        Response structure:
        {
            "survey": { ... survey details ... },
            "claimCreated": true,
            "claimId": "uuid",
            "claimNumber": "string",
            "claimsCreatedCount": 0,
            "createdClaims": [ ... list of claim objects ... ],
            "claimNotCreatedReason": "string",
            "warnings": ["string"],
            "dataSummary": { ... counts ... }
        }

        Args:
            survey_id: UUID of the survey to process claims for
            finalize_options: Optional dictionary with processing options
                - finalNotes: Final notes for the survey
                - durationMinutes: Survey duration in minutes
                - autoCreateClaim: Whether to automatically create a claim

        Returns:
            Dict with success status and response data or error
        """
        if not survey_id:
            logger.error("Survey ID is required for processing claims")
            return {"success": False, "error": "Survey ID is required", "error_code": "E_PARAM"}

        # Request body is required for process-claims API
        api_data = {
            "surveyId": survey_id,
            "finalNotes": "",
            "durationMinutes": 10,
            "autoCreateClaim": True
        }

        # Override with provided options
        if finalize_options:
            if 'finalNotes' in finalize_options:
                api_data['finalNotes'] = finalize_options['finalNotes'] or ""
            if 'durationMinutes' in finalize_options:
                api_data['durationMinutes'] = finalize_options['durationMinutes'] or 0
            if 'autoCreateClaim' in finalize_options:
                api_data['autoCreateClaim'] = finalize_options['autoCreateClaim']

        endpoint = f"/v1/Surveys/office/{survey_id}/process-claims"
        logger.info(f"Processing claims for office survey {survey_id} via POST {endpoint}")
        logger.info(f"Request body: {json.dumps(api_data, ensure_ascii=False, indent=2)}")

        response = self._make_request("POST", endpoint, data=api_data)

        if response.get("success"):
            logger.info(f"Office survey {survey_id} claims processed successfully")
            return response
        else:
            error_details = response.get('details', '')
            logger.error(f"Failed to process claims for office survey: {response.get('error')}")
            logger.error(f"Error details: {error_details}")
            return response

    def finalize_survey_status(self, survey_id: str) -> Dict[str, Any]:
        """
        Finalize an office survey - transitions status from Draft to Finalized.

        POST /v1/Surveys/office/{id}/finalize

        Use Case: UC-004 S21 - Mark office survey as finalized
        Purpose: Transitions the survey status from Draft to Finalized.
                 Does NOT create claims - use process-claims endpoint for that.

        What it does:
        - Validates survey is an office survey in Draft status
        - Marks the survey as Finalized via domain method
        - Logs the status change in audit trail

        Required permissions: CanFinalizeSurveys

        Args:
            survey_id: UUID of the survey to finalize

        Returns:
            Dict with success status and response data or error
        """
        if not survey_id:
            logger.error("Survey ID is required for finalizing survey")
            return {"success": False, "error": "Survey ID is required", "error_code": "E_PARAM"}

        endpoint = f"/v1/Surveys/office/{survey_id}/finalize"
        logger.info(f"Finalizing office survey {survey_id} via POST {endpoint}")

        response = self._make_request("POST", endpoint)

        if response.get("success"):
            logger.info(f"Office survey {survey_id} finalized successfully")
            return response
        else:
            error_details = response.get('details', '')
            logger.error(f"Failed to finalize office survey: {response.get('error')}")
            logger.error(f"Error details: {error_details}")
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

    def upload_identification_evidence(
        self,
        survey_id: str,
        person_id: str,
        file_path: str,
        description: str = "",
        document_issued_date: Optional[str] = None,
        document_expiry_date: Optional[str] = None,
        issuing_authority: str = "",
        document_reference_number: str = ""
    ) -> Dict[str, Any]:
        """
        Upload identification evidence for a person in a survey.

        POST /v1/Surveys/{surveyId}/evidence/identification

        Args:
            survey_id: Survey UUID
            person_id: Person UUID
            file_path: Path to the file to upload
            description: Document description
            document_issued_date: Document issued date (ISO format)
            document_expiry_date: Document expiry date (ISO format)
            issuing_authority: Issuing authority name
            document_reference_number: Document reference number

        Returns:
            Dict with success status and response data or error
        """
        import os
        import mimetypes
        from datetime import datetime, timezone

        if not survey_id or not person_id:
            logger.error("Survey ID and Person ID are required")
            return {"success": False, "error": "Survey ID and Person ID are required", "error_code": "E_PARAM"}

        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {"success": False, "error": f"File not found: {file_path}", "error_code": "E_FILE"}

        # Generate default dates if not provided
        # Expiry date must be AFTER issue date per API validation
        now = datetime.now(timezone.utc)
        one_year_later = now.replace(year=now.year + 1)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        expiry_str = one_year_later.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        if not document_issued_date:
            document_issued_date = now_str
        if not document_expiry_date:
            document_expiry_date = expiry_str

        endpoint = f"/v1/Surveys/{survey_id}/evidence/identification"
        url = f"{self.base_url}{endpoint}"

        # Prepare multipart form data
        boundary = f"----WebKitFormBoundary{os.urandom(16).hex()}"

        # Get file info
        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Build multipart body
        body_parts = []

        # SurveyId field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="SurveyId"\r\n\r\n'.encode())
        body_parts.append(f'{survey_id}\r\n'.encode())

        # PersonId field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="PersonId"\r\n\r\n'.encode())
        body_parts.append(f'{person_id}\r\n'.encode())

        # File field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="File"; filename="{file_name}"\r\n'.encode())
        body_parts.append(f'Content-Type: {mime_type}\r\n\r\n'.encode())
        body_parts.append(file_content)
        body_parts.append(b'\r\n')

        # Description field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="Description"\r\n\r\n'.encode())
        body_parts.append(f'{description}\r\n'.encode())

        # DocumentIssuedDate field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="DocumentIssuedDate"\r\n\r\n'.encode())
        body_parts.append(f'{document_issued_date}\r\n'.encode())

        # DocumentExpiryDate field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="DocumentExpiryDate"\r\n\r\n'.encode())
        body_parts.append(f'{document_expiry_date}\r\n'.encode())

        # IssuingAuthority field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="IssuingAuthority"\r\n\r\n'.encode())
        body_parts.append(f'{issuing_authority}\r\n'.encode())

        # DocumentReferenceNumber field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="DocumentReferenceNumber"\r\n\r\n'.encode())
        body_parts.append(f'{document_reference_number}\r\n'.encode())

        # End boundary
        body_parts.append(f'--{boundary}--\r\n'.encode())

        body = b''.join(body_parts)

        # Prepare headers
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "TRRCMS-Desktop/1.0"
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        try:
            print(f"\n[UPLOAD EVIDENCE] POST {url}")
            print(f"[UPLOAD EVIDENCE] SurveyId: {survey_id}, PersonId: {person_id}")
            print(f"[UPLOAD EVIDENCE] File: {file_name} ({mime_type})")

            request = urllib.request.Request(url, data=body, headers=headers, method="POST")

            with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                response_data = response.read().decode('utf-8')
                print(f"[UPLOAD EVIDENCE] Response status: {response.status}")

                if response_data:
                    result = json.loads(response_data)
                    print(f"[UPLOAD EVIDENCE] Success: {result}")
                    return {"success": True, "data": result}
                else:
                    return {"success": True, "data": None}

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode('utf-8') if e.fp else ""
            except:
                pass

            print(f"[UPLOAD EVIDENCE] HTTP Error: {e.code} - {e.reason}")
            print(f"[UPLOAD EVIDENCE] Error body: {error_body}")
            logger.error(f"HTTP Error {e.code}: {e.reason} - {error_body}")
            return {
                "success": False,
                "error": f"HTTP Error {e.code}: {e.reason}",
                "error_code": f"E{e.code}",
                "details": error_body
            }

        except Exception as e:
            print(f"[UPLOAD EVIDENCE] Error: {e}")
            logger.error(f"Upload evidence error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_code": "E500"
            }

    def upload_tenure_evidence(
        self,
        survey_id: str,
        relation_id: str,
        file_path: str,
        evidence_type: int = 0,
        description: str = "",
        document_issued_date: Optional[str] = None,
        document_expiry_date: Optional[str] = None,
        issuing_authority: str = "",
        document_reference_number: str = "",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Upload tenure evidence for a person-property relation.

        POST /v1/Surveys/{surveyId}/evidence/tenure

        Args:
            survey_id: Survey UUID
            relation_id: Person Property Relation UUID
            file_path: Path to the file to upload
            evidence_type: Evidence type (integer)
            description: Document description
            document_issued_date: Document issued date (ISO format)
            document_expiry_date: Document expiry date (ISO format)
            issuing_authority: Issuing authority name
            document_reference_number: Document reference number
            notes: Additional notes

        Returns:
            Dict with success status and response data or error
        """
        import os
        import mimetypes
        from datetime import datetime, timezone

        if not survey_id or not relation_id:
            logger.error("Survey ID and Relation ID are required")
            return {"success": False, "error": "Survey ID and Relation ID are required", "error_code": "E_PARAM"}

        if not file_path or not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {"success": False, "error": f"File not found: {file_path}", "error_code": "E_FILE"}

        # Generate default dates if not provided
        # Expiry date must be AFTER issue date per API validation
        now = datetime.now(timezone.utc)
        one_year_later = now.replace(year=now.year + 1)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        expiry_str = one_year_later.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        if not document_issued_date:
            document_issued_date = now_str
        if not document_expiry_date:
            document_expiry_date = expiry_str

        endpoint = f"/v1/Surveys/{survey_id}/evidence/tenure"
        url = f"{self.base_url}{endpoint}"

        # Prepare multipart form data
        boundary = f"----WebKitFormBoundary{os.urandom(16).hex()}"

        # Get file info
        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Build multipart body
        body_parts = []

        # SurveyId field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="SurveyId"\r\n\r\n'.encode())
        body_parts.append(f'{survey_id}\r\n'.encode())

        # PersonPropertyRelationId field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="PersonPropertyRelationId"\r\n\r\n'.encode())
        body_parts.append(f'{relation_id}\r\n'.encode())

        # File field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="File"; filename="{file_name}"\r\n'.encode())
        body_parts.append(f'Content-Type: {mime_type}\r\n\r\n'.encode())
        body_parts.append(file_content)
        body_parts.append(b'\r\n')

        # EvidenceType field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="EvidenceType"\r\n\r\n'.encode())
        body_parts.append(f'{evidence_type}\r\n'.encode())

        # Description field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="Description"\r\n\r\n'.encode())
        body_parts.append(f'{description}\r\n'.encode())

        # DocumentIssuedDate field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="DocumentIssuedDate"\r\n\r\n'.encode())
        body_parts.append(f'{document_issued_date}\r\n'.encode())

        # DocumentExpiryDate field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="DocumentExpiryDate"\r\n\r\n'.encode())
        body_parts.append(f'{document_expiry_date}\r\n'.encode())

        # IssuingAuthority field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="IssuingAuthority"\r\n\r\n'.encode())
        body_parts.append(f'{issuing_authority}\r\n'.encode())

        # DocumentReferenceNumber field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="DocumentReferenceNumber"\r\n\r\n'.encode())
        body_parts.append(f'{document_reference_number}\r\n'.encode())

        # Notes field
        body_parts.append(f'--{boundary}\r\n'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="Notes"\r\n\r\n'.encode())
        body_parts.append(f'{notes}\r\n'.encode())

        # End boundary
        body_parts.append(f'--{boundary}--\r\n'.encode())

        body = b''.join(body_parts)

        # Prepare headers
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "TRRCMS-Desktop/1.0"
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        try:
            print(f"\n[UPLOAD TENURE EVIDENCE] POST {url}")
            print(f"[UPLOAD TENURE EVIDENCE] SurveyId: {survey_id}, RelationId: {relation_id}")
            print(f"[UPLOAD TENURE EVIDENCE] File: {file_name} ({mime_type})")

            request = urllib.request.Request(url, data=body, headers=headers, method="POST")

            with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                response_data = response.read().decode('utf-8')
                print(f"[UPLOAD TENURE EVIDENCE] Response status: {response.status}")

                if response_data:
                    result = json.loads(response_data)
                    print(f"[UPLOAD TENURE EVIDENCE] Success: {result}")
                    return {"success": True, "data": result}
                else:
                    return {"success": True, "data": None}

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode('utf-8') if e.fp else ""
            except:
                pass

            print(f"[UPLOAD TENURE EVIDENCE] HTTP Error: {e.code} - {e.reason}")
            print(f"[UPLOAD TENURE EVIDENCE] Error body: {error_body}")
            logger.error(f"HTTP Error {e.code}: {e.reason} - {error_body}")
            return {
                "success": False,
                "error": f"HTTP Error {e.code}: {e.reason}",
                "error_code": f"E{e.code}",
                "details": error_body
            }

        except Exception as e:
            print(f"[UPLOAD TENURE EVIDENCE] Error: {e}")
            logger.error(f"Upload tenure evidence error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_code": "E500"
            }
