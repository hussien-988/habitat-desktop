# -*- coding: utf-8 -*-
"""
HTTP Data Provider for REST API Backend.

Connects to a real REST API backend server for data operations.
Supports authentication, token refresh, and automatic retry.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode, urljoin
import urllib.request
import urllib.error

from .data_provider import (
    ApiResponse,
    DataProvider,
    DataProviderType,
    DataProviderEventEmitter,
    QueryParams,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class HttpDataProvider(DataProvider, DataProviderEventEmitter):
    """
    HTTP Data Provider for connecting to REST API backend.

    Features:
    - OAuth 2.0 / JWT authentication
    - Automatic token refresh
    - Request retry with exponential backoff
    - Connection pooling (via urllib)
    - Request/response logging
    """

    def __init__(
        self,
        base_url: str,
        api_version: str = "v1",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize HTTP data provider.

        Args:
            base_url: Base URL of the API (e.g., "https://api.trrcms.org")
            api_version: API version string (e.g., "v1")
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (doubles each retry)
        """
        DataProviderEventEmitter.__init__(self)

        self.base_url = base_url.rstrip('/')
        self.api_version = api_version
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._connected = False
        self._auth_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._current_user: Optional[Dict] = None

    @property
    def provider_type(self) -> DataProviderType:
        return DataProviderType.HTTP_API

    @property
    def api_url(self) -> str:
        """Get full API URL with version."""
        return f"{self.base_url}/api/{self.api_version}"

    def _get_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": content_type,
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
    ) -> ApiResponse:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/buildings")
            data: Request body data (for POST/PUT)
            params: Query parameters

        Returns:
            ApiResponse with data or error
        """
        url = f"{self.api_url}{endpoint}"

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

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                request = urllib.request.Request(
                    url,
                    data=body,
                    headers=headers,
                    method=method
                )

                logger.debug(f"HTTP {method} {url}")

                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    response_data = response.read().decode('utf-8')
                    result = json.loads(response_data)

                    # Handle standard API response format
                    if isinstance(result, dict):
                        if result.get("success", True):
                            return ApiResponse.ok(
                                data=result.get("data", result),
                                total_count=result.get("total_count") or result.get("pagination", {}).get("total"),
                                page=result.get("page", 1),
                                page_size=result.get("page_size", 50)
                            )
                        else:
                            return ApiResponse.error(
                                result.get("error", {}).get("message", "Unknown error"),
                                result.get("error", {}).get("code", "E500")
                            )

                    return ApiResponse.ok(result)

            except urllib.error.HTTPError as e:
                last_error = e
                error_body = e.read().decode('utf-8') if e.fp else ""

                # Handle specific HTTP errors
                if e.code == 401:
                    # Try to refresh token
                    if self._refresh_token and attempt == 0:
                        if self._refresh_auth_token():
                            continue  # Retry with new token
                    return ApiResponse.error("Unauthorized", "E401")

                elif e.code == 403:
                    return ApiResponse.error("Forbidden", "E403")

                elif e.code == 404:
                    return ApiResponse.error("Not found", "E404")

                elif e.code == 422:
                    try:
                        error_data = json.loads(error_body)
                        return ApiResponse.error(
                            error_data.get("message", "Validation error"),
                            "E422"
                        )
                    except json.JSONDecodeError:
                        return ApiResponse.error("Validation error", "E422")

                elif e.code >= 500:
                    logger.warning(f"Server error {e.code}, attempt {attempt + 1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue

                return ApiResponse.error(f"HTTP Error {e.code}: {e.reason}", f"E{e.code}")

            except urllib.error.URLError as e:
                last_error = e
                logger.warning(f"Connection error: {e.reason}, attempt {attempt + 1}/{self.max_retries}")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue

                self._connected = False
                self.emit("disconnected", {"reason": str(e.reason)})
                return ApiResponse.error(f"Connection error: {e.reason}", "E_CONN")

            except json.JSONDecodeError as e:
                return ApiResponse.error(f"Invalid JSON response: {e}", "E_JSON")

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {e}", exc_info=True)
                return ApiResponse.error(str(e), "E500")

        return ApiResponse.error(f"Request failed after {self.max_retries} attempts: {last_error}", "E_RETRY")

    def _refresh_auth_token(self) -> bool:
        """Attempt to refresh the auth token."""
        if not self._refresh_token:
            return False

        try:
            url = f"{self.api_url}/oauth/token"
            data = json.dumps({
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token
            }).encode('utf-8')

            request = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))

                if result.get("success") and result.get("data"):
                    token_data = result["data"]
                    self._auth_token = token_data.get("access_token")
                    self._refresh_token = token_data.get("refresh_token")
                    self._token_expiry = datetime.now() + timedelta(
                        seconds=token_data.get("expires_in", 86400)
                    )
                    logger.info("Auth token refreshed successfully")
                    return True

        except Exception as e:
            logger.error(f"Token refresh failed: {e}")

        return False

    # ==================== Connection ====================

    def connect(self) -> bool:
        """Test connection to API server."""
        logger.info(f"Connecting to HTTP API at {self.base_url}...")

        response = self._make_request("GET", "/health")

        if response.success:
            self._connected = True
            self.emit("connected", {"url": self.base_url})
            logger.info("HTTP Data Provider connected successfully")
            return True

        logger.error(f"Failed to connect: {response.error}")
        return False

    def disconnect(self) -> None:
        """Disconnect from API server."""
        self._auth_token = None
        self._refresh_token = None
        self._current_user = None
        self._connected = False
        self.emit("disconnected", {"url": self.base_url})
        logger.info("HTTP Data Provider disconnected")

    def is_connected(self) -> bool:
        return self._connected

    def health_check(self) -> Dict[str, Any]:
        response = self._make_request("GET", "/health")
        if response.success:
            return response.data
        return {
            "status": "error",
            "error": response.error,
            "provider": "http",
            "url": self.base_url
        }

    # ==================== Buildings ====================

    def get_buildings(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
            "sort_by": params.sort_by,
            "sort_order": params.sort_order,
            "search": params.search,
        }
        query.update(params.filters)
        return self._make_request("GET", "/buildings", params=query)

    def get_building(self, building_id: str) -> ApiResponse:
        return self._make_request("GET", f"/buildings/{building_id}")

    def create_building(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/buildings", data=data)

    def update_building(self, building_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/buildings/{building_id}", data=data)

    def delete_building(self, building_id: str) -> ApiResponse:
        return self._make_request("DELETE", f"/buildings/{building_id}")

    # ==================== Units ====================

    def get_units(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
            "search": params.search,
        }
        query.update(params.filters)
        return self._make_request("GET", "/units", params=query)

    def get_unit(self, unit_id: str) -> ApiResponse:
        return self._make_request("GET", f"/units/{unit_id}")

    def create_unit(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/units", data=data)

    def update_unit(self, unit_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/units/{unit_id}", data=data)

    def delete_unit(self, unit_id: str) -> ApiResponse:
        return self._make_request("DELETE", f"/units/{unit_id}")

    # ==================== Persons ====================

    def get_persons(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
            "search": params.search,
        }
        query.update(params.filters)
        return self._make_request("GET", "/persons", params=query)

    def get_person(self, person_id: str) -> ApiResponse:
        return self._make_request("GET", f"/persons/{person_id}")

    def create_person(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/persons", data=data)

    def update_person(self, person_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/persons/{person_id}", data=data)

    def delete_person(self, person_id: str) -> ApiResponse:
        return self._make_request("DELETE", f"/persons/{person_id}")

    # ==================== Claims ====================

    def get_claims(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
            "search": params.search,
        }
        query.update(params.filters)
        return self._make_request("GET", "/claims", params=query)

    def get_claim(self, claim_id: str) -> ApiResponse:
        return self._make_request("GET", f"/claims/{claim_id}")

    def create_claim(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/claims", data=data)

    def update_claim(self, claim_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/claims/{claim_id}", data=data)

    def delete_claim(self, claim_id: str) -> ApiResponse:
        return self._make_request("DELETE", f"/claims/{claim_id}")

    # ==================== Relations ====================

    def get_relations(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
        }
        query.update(params.filters)
        return self._make_request("GET", "/relations", params=query)

    def get_relation(self, relation_id: str) -> ApiResponse:
        return self._make_request("GET", f"/relations/{relation_id}")

    def create_relation(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/relations", data=data)

    def update_relation(self, relation_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/relations/{relation_id}", data=data)

    def delete_relation(self, relation_id: str) -> ApiResponse:
        return self._make_request("DELETE", f"/relations/{relation_id}")

    # ==================== Documents ====================

    def get_documents(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
        }
        query.update(params.filters)
        return self._make_request("GET", "/documents", params=query)

    def get_document(self, document_id: str) -> ApiResponse:
        return self._make_request("GET", f"/documents/{document_id}")

    def create_document(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/documents", data=data)

    def update_document(self, document_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/documents/{document_id}", data=data)

    def delete_document(self, document_id: str) -> ApiResponse:
        return self._make_request("DELETE", f"/documents/{document_id}")

    # ==================== Users & Auth ====================

    def authenticate(self, username: str, password: str) -> ApiResponse:
        """Authenticate with username and password."""
        response = self._make_request("POST", "/oauth/token", data={
            "grant_type": "password",
            "username": username,
            "password": password
        })

        if response.success and response.data:
            self._auth_token = response.data.get("access_token")
            self._refresh_token = response.data.get("refresh_token")
            self._token_expiry = datetime.now() + timedelta(
                seconds=response.data.get("expires_in", 86400)
            )

            # Fetch user info
            user_response = self.get_current_user()
            if user_response.success:
                self._current_user = user_response.data

            return ApiResponse.ok({
                "token": self._auth_token,
                "user": self._current_user
            })

        return response

    def get_current_user(self) -> ApiResponse:
        return self._make_request("GET", "/users/me")

    def get_users(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
        }
        return self._make_request("GET", "/users", params=query)

    def create_user(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/users", data=data)

    def update_user(self, user_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/users/{user_id}", data=data)

    # ==================== Vocabularies ====================

    def get_vocabularies(self) -> ApiResponse:
        return self._make_request("GET", "/vocabularies")

    def get_vocabulary(self, vocab_name: str) -> ApiResponse:
        return self._make_request("GET", f"/vocabularies/{vocab_name}")

    def update_vocabulary_term(self, vocab_name: str, term_code: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/vocabularies/{vocab_name}/{term_code}", data=data)

    # ==================== Dashboard & Statistics ====================

    def get_dashboard_stats(self) -> ApiResponse:
        return self._make_request("GET", "/statistics")

    def get_building_stats(self) -> ApiResponse:
        return self._make_request("GET", "/statistics/buildings")

    def get_claim_stats(self) -> ApiResponse:
        return self._make_request("GET", "/statistics/claims")

    # ==================== Duplicates ====================

    def get_duplicate_candidates(self, entity_type: str, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
            "entity_type": entity_type
        }
        return self._make_request("GET", "/duplicates", params=query)

    def resolve_duplicate(self, resolution_data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/duplicates/resolve", data=resolution_data)

    # ==================== Import/Export ====================

    def import_data(self, file_path: str, import_type: str) -> ApiResponse:
        # For file uploads, would need multipart form data
        # Simplified implementation - real implementation would use requests library
        return self._make_request("POST", "/import", data={
            "file_path": file_path,
            "import_type": import_type
        })

    def export_data(self, export_type: str, filters: Dict[str, Any] = None) -> ApiResponse:
        return self._make_request("POST", "/export", data={
            "export_type": export_type,
            "filters": filters or {}
        })

    # ==================== Assignments ====================

    def get_building_assignments(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
        }
        query.update(params.filters)
        return self._make_request("GET", "/assignments", params=query)

    def create_assignment(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("POST", "/assignments", data=data)

    def update_assignment(self, assignment_id: str, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", f"/assignments/{assignment_id}", data=data)

    # ==================== Audit ====================

    def get_audit_log(self, params: QueryParams = None) -> ApiResponse:
        params = params or QueryParams()
        query = {
            "page": params.page,
            "per_page": params.page_size,
        }
        query.update(params.filters)
        return self._make_request("GET", "/audit", params=query)

    # ==================== Settings ====================

    def get_security_settings(self) -> ApiResponse:
        return self._make_request("GET", "/settings/security")

    def update_security_settings(self, data: Dict[str, Any]) -> ApiResponse:
        return self._make_request("PUT", "/settings/security", data=data)
