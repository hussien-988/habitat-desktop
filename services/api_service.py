# -*- coding: utf-8 -*-
"""
REST API Service - FR-D-13 Implementation.
Provides RESTful APIs for system integration with OAuth 2.0 authentication.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from functools import wraps
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from utils.logger import get_logger

logger = get_logger(__name__)

# API Configuration
API_VERSION = "v1"
DEFAULT_PORT = 8080
TOKEN_EXPIRY_HOURS = 24
RATE_LIMIT_REQUESTS = 100  # per minute
API_SECRET_KEY = b"TRRCMS-API-SECRET-2025"  # Use secure key management in production


@dataclass
class APIToken:
    """OAuth 2.0 access token."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24 hours
    refresh_token: Optional[str] = None
    scope: str = "read"
    created_at: datetime = None
    user_id: Optional[str] = None
    client_id: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def is_expired(self) -> bool:
        if self.created_at is None:
            return True
        return datetime.now() > self.created_at + timedelta(seconds=self.expires_in)


@dataclass
class APIClient:
    """Registered API client."""
    client_id: str
    client_secret_hash: str
    name: str
    allowed_scopes: List[str]
    is_active: bool = True
    created_at: datetime = None
    rate_limit: int = RATE_LIMIT_REQUESTS


@dataclass
class RateLimitInfo:
    """Rate limiting information for a client."""
    requests: int = 0
    window_start: datetime = None
    blocked_until: Optional[datetime] = None


class APIError(Exception):
    """API error with HTTP status code."""
    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"E{status_code}"


class APIRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for REST API."""

    server: 'APIHTTPServer'

    def log_message(self, format: str, *args):
        logger.debug(f"API: {format % args}")

    def _send_json_response(self, data: Any, status_code: int = 200):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-API-Version", API_VERSION)
        self.end_headers()

        response = {
            "success": status_code < 400,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False, default=str).encode("utf-8"))

    def _send_error_response(self, error: APIError):
        """Send error response."""
        self.send_response(error.status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        response = {
            "success": False,
            "error": {
                "code": error.error_code,
                "message": error.message
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    def _get_request_body(self) -> Dict:
        """Parse request body as JSON."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}

        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise APIError("Invalid JSON in request body", 400, "E001")

    def _authenticate(self) -> Tuple[bool, Optional[APIToken], Optional[str]]:
        """Authenticate request and return token info."""
        auth_header = self.headers.get("Authorization", "")

        # Check for Bearer token
        if auth_header.startswith("Bearer "):
            token_str = auth_header[7:]
            token = self.server.api_service.validate_token(token_str)
            if token:
                return True, token, None
            return False, None, "Invalid or expired token"

        # Check for API Key
        api_key = self.headers.get("X-API-Key")
        if api_key:
            if self.server.api_service.validate_api_key(api_key):
                return True, None, None
            return False, None, "Invalid API key"

        return False, None, "Authentication required"

    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if request is within rate limits."""
        return self.server.api_service.check_rate_limit(client_id)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)

            # Public endpoints
            if path == f"/api/{API_VERSION}/health":
                self._send_json_response({
                    "status": "healthy",
                    "version": API_VERSION,
                    "service": "TRRCMS-API"
                })
                return

            if path == f"/api/{API_VERSION}/vocabularies":
                # Public vocabularies endpoint
                result = self.server.api_service.get_vocabularies()
                self._send_json_response(result)
                return

            # Authenticated endpoints
            is_auth, token, error = self._authenticate()
            if not is_auth:
                raise APIError(error, 401, "E401")

            # Route to appropriate handler
            if path == f"/api/{API_VERSION}/claims":
                result = self.server.api_service.search_claims(query)
                self._send_json_response(result)

            elif path.startswith(f"/api/{API_VERSION}/claims/"):
                claim_id = path.split("/")[-1]
                result = self.server.api_service.get_claim(claim_id)
                self._send_json_response(result)

            elif path.startswith(f"/api/{API_VERSION}/documents/"):
                doc_id = path.split("/")[-1]
                result = self.server.api_service.get_document(doc_id)
                self._send_json_response(result)

            elif path == f"/api/{API_VERSION}/statistics":
                result = self.server.api_service.get_statistics()
                self._send_json_response(result)

            elif path == f"/api/{API_VERSION}/buildings":
                result = self.server.api_service.search_buildings(query)
                self._send_json_response(result)

            elif path.startswith(f"/api/{API_VERSION}/buildings/"):
                building_id = path.split("/")[-1]
                result = self.server.api_service.get_building(building_id)
                self._send_json_response(result)

            # GeoJSON endpoints
            elif path == f"/api/{API_VERSION}/geo/buildings":
                result = self.server.api_service.get_buildings_geojson(query)
                self._send_json_response(result)

            elif path == f"/api/{API_VERSION}/geo/claims":
                result = self.server.api_service.get_claims_geojson(query)
                self._send_json_response(result)

            else:
                raise APIError("Endpoint not found", 404, "E404")

        except APIError as e:
            self._send_error_response(e)
        except Exception as e:
            logger.error(f"API error: {e}", exc_info=True)
            self._send_error_response(APIError(str(e), 500, "E500"))

    def do_POST(self):
        """Handle POST requests."""
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            # OAuth token endpoint
            if path == f"/api/{API_VERSION}/oauth/token":
                body = self._get_request_body()
                result = self.server.api_service.generate_token(body)
                self._send_json_response(result)
                return

            # Authenticated endpoints
            is_auth, token, error = self._authenticate()
            if not is_auth:
                raise APIError(error, 401, "E401")

            body = self._get_request_body()

            if path == f"/api/{API_VERSION}/claims":
                result = self.server.api_service.create_claim(body, token)
                self._send_json_response(result, 201)

            elif path == f"/api/{API_VERSION}/claims/search":
                result = self.server.api_service.search_claims_advanced(body)
                self._send_json_response(result)

            elif path == f"/api/{API_VERSION}/export":
                result = self.server.api_service.export_data(body, token)
                self._send_json_response(result)

            else:
                raise APIError("Endpoint not found", 404, "E404")

        except APIError as e:
            self._send_error_response(e)
        except Exception as e:
            logger.error(f"API error: {e}", exc_info=True)
            self._send_error_response(APIError(str(e), 500, "E500"))

    def do_PUT(self):
        """Handle PUT requests."""
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            is_auth, token, error = self._authenticate()
            if not is_auth:
                raise APIError(error, 401, "E401")

            body = self._get_request_body()

            if path.startswith(f"/api/{API_VERSION}/claims/"):
                claim_id = path.split("/")[-1]
                result = self.server.api_service.update_claim(claim_id, body, token)
                self._send_json_response(result)

            else:
                raise APIError("Endpoint not found", 404, "E404")

        except APIError as e:
            self._send_error_response(e)
        except Exception as e:
            logger.error(f"API error: {e}", exc_info=True)
            self._send_error_response(APIError(str(e), 500, "E500"))


class APIHTTPServer(HTTPServer):
    """Extended HTTPServer with API service reference."""

    def __init__(self, server_address, RequestHandlerClass, api_service):
        super().__init__(server_address, RequestHandlerClass)
        self.api_service = api_service


class RESTAPIService:
    """
    REST API Service implementing FR-D-13.

    Provides:
    - OAuth 2.0 authentication
    - Rate limiting
    - RESTful endpoints for all entities
    - Webhook support
    - OpenAPI documentation generation
    """

    def __init__(self, db_connection, map_service=None, port: int = DEFAULT_PORT):
        self.db = db_connection
        self.map_service = map_service
        self.port = port

        self.server: Optional[APIHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None

        # Token and client management
        self.tokens: Dict[str, APIToken] = {}
        self.clients: Dict[str, APIClient] = {}
        self.api_keys: Dict[str, str] = {}  # api_key -> client_id
        self.rate_limits: Dict[str, RateLimitInfo] = {}

        # Webhook subscriptions
        self.webhooks: Dict[str, List[Dict]] = {
            "claim.created": [],
            "claim.updated": [],
            "claim.approved": [],
            "claim.rejected": [],
            "document.verified": []
        }

        self._load_api_clients()

    def _load_api_clients(self):
        """Load registered API clients from database."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT client_id, client_secret_hash, name, allowed_scopes,
                       is_active, rate_limit
                FROM api_clients
                WHERE is_active = 1
            """)

            for row in cursor.fetchall():
                self.clients[row[0]] = APIClient(
                    client_id=row[0],
                    client_secret_hash=row[1],
                    name=row[2],
                    allowed_scopes=json.loads(row[3]) if row[3] else ["read"],
                    is_active=row[4],
                    rate_limit=row[5] or RATE_LIMIT_REQUESTS
                )

        except Exception as e:
            logger.warning(f"Could not load API clients: {e}")
            # Create default client for development
            self.clients["default"] = APIClient(
                client_id="default",
                client_secret_hash=hashlib.sha256(b"default_secret").hexdigest(),
                name="Default Client",
                allowed_scopes=["read", "write"]
            )

    def start(self) -> bool:
        """Start the API server."""
        try:
            self.server = APIHTTPServer(
                ("0.0.0.0", self.port),
                APIRequestHandler,
                self
            )

            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()

            logger.info(f"REST API server started on port {self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start API server: {e}", exc_info=True)
            return False

    def stop(self):
        """Stop the API server."""
        if self.server:
            self.server.shutdown()
            logger.info("REST API server stopped")

    def generate_token(self, request: Dict) -> Dict:
        """
        Generate OAuth 2.0 access token.

        Supports grant types:
        - client_credentials
        - password
        - refresh_token
        """
        grant_type = request.get("grant_type")

        if grant_type == "client_credentials":
            client_id = request.get("client_id")
            client_secret = request.get("client_secret")

            client = self.clients.get(client_id)
            if not client:
                raise APIError("Invalid client", 401)

            secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()
            if secret_hash != client.client_secret_hash:
                raise APIError("Invalid client credentials", 401)

            return self._create_token(client_id, client.allowed_scopes)

        elif grant_type == "password":
            username = request.get("username")
            password = request.get("password")

            user = self._authenticate_user(username, password)
            if not user:
                raise APIError("Invalid credentials", 401)

            return self._create_token(user["user_id"], ["read", "write"], user["user_id"])

        elif grant_type == "refresh_token":
            refresh_token = request.get("refresh_token")
            return self._refresh_token(refresh_token)

        else:
            raise APIError(f"Unsupported grant type: {grant_type}", 400)

    def _create_token(
        self,
        client_id: str,
        scopes: List[str],
        user_id: str = None
    ) -> Dict:
        """Create a new access token."""
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        token = APIToken(
            access_token=access_token,
            refresh_token=refresh_token,
            scope=" ".join(scopes),
            client_id=client_id,
            user_id=user_id
        )

        self.tokens[access_token] = token

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": token.expires_in,
            "refresh_token": refresh_token,
            "scope": token.scope
        }

    def _refresh_token(self, refresh_token: str) -> Dict:
        """Refresh an access token."""
        # Find token by refresh token
        for token in self.tokens.values():
            if token.refresh_token == refresh_token:
                # Create new token
                return self._create_token(
                    token.client_id,
                    token.scope.split(),
                    token.user_id
                )

        raise APIError("Invalid refresh token", 401)

    def _authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user credentials."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT user_id, password_hash, role
                FROM users
                WHERE username = ? AND is_active = 1
            """, (username,))

            row = cursor.fetchone()
            if not row:
                return None

            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash != row[1]:
                return None

            return {
                "user_id": row[0],
                "role": row[2]
            }

        except Exception:
            return None

    def validate_token(self, token_str: str) -> Optional[APIToken]:
        """Validate an access token."""
        token = self.tokens.get(token_str)
        if token and not token.is_expired():
            return token
        return None

    def validate_api_key(self, api_key: str) -> bool:
        """Validate an API key."""
        return api_key in self.api_keys

    def check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limits."""
        now = datetime.now()
        info = self.rate_limits.get(client_id)

        if not info:
            info = RateLimitInfo(window_start=now)
            self.rate_limits[client_id] = info

        # Check if blocked
        if info.blocked_until and now < info.blocked_until:
            return False

        # Reset window if expired
        if info.window_start and (now - info.window_start).total_seconds() > 60:
            info.requests = 0
            info.window_start = now

        # Check limit
        client = self.clients.get(client_id)
        limit = client.rate_limit if client else RATE_LIMIT_REQUESTS

        if info.requests >= limit:
            info.blocked_until = now + timedelta(minutes=1)
            return False

        info.requests += 1
        return True

    def get_vocabularies(self) -> Dict:
        """Get all controlled vocabularies (public endpoint)."""
        try:
            cursor = self.db.cursor()
            vocabularies = {}

            cursor.execute("""
                SELECT vocabulary_name, code, label_ar, label_en, is_active
                FROM vocabularies
                ORDER BY vocabulary_name, display_order
            """)

            for row in cursor.fetchall():
                vocab_name = row[0]
                if vocab_name not in vocabularies:
                    vocabularies[vocab_name] = []

                vocabularies[vocab_name].append({
                    "code": row[1],
                    "label_ar": row[2],
                    "label_en": row[3],
                    "is_active": bool(row[4])
                })

            return vocabularies

        except Exception as e:
            logger.error(f"Error getting vocabularies: {e}")
            return {}

    def search_claims(self, query: Dict) -> Dict:
        """Search claims with pagination."""
        try:
            cursor = self.db.cursor()

            # Pagination
            page = int(query.get("page", ["1"])[0])
            per_page = min(int(query.get("per_page", ["20"])[0]), 100)
            offset = (page - 1) * per_page

            # Build query
            where_clauses = ["1=1"]
            params = []

            if "status" in query:
                where_clauses.append("case_status = ?")
                params.append(query["status"][0])

            if "case_number" in query:
                where_clauses.append("case_number LIKE ?")
                params.append(f"%{query['case_number'][0]}%")

            where_sql = " AND ".join(where_clauses)

            # Get total count
            cursor.execute(f"SELECT COUNT(*) FROM claims WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # Get results
            cursor.execute(f"""
                SELECT claim_uuid, case_number, case_status, source,
                       created_at, updated_at
                FROM claims
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [per_page, offset])

            columns = ["claim_uuid", "case_number", "case_status", "source",
                      "created_at", "updated_at"]
            claims = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {
                "claims": claims,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page
                }
            }

        except Exception as e:
            logger.error(f"Error searching claims: {e}")
            raise APIError(str(e), 500)

    def get_claim(self, claim_id: str) -> Dict:
        """Get claim details by ID."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT c.*, u.unit_id, u.unit_type, b.building_id
                FROM claims c
                LEFT JOIN units u ON c.unit_uuid = u.unit_uuid
                LEFT JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE c.claim_uuid = ? OR c.case_number = ?
            """, (claim_id, claim_id))

            row = cursor.fetchone()
            if not row:
                raise APIError("Claim not found", 404)

            columns = [desc[0] for desc in cursor.description]
            claim = dict(zip(columns, row))

            # Get related persons
            cursor.execute("""
                SELECT p.person_uuid, p.first_name, p.father_name, p.last_name,
                       r.relation_type
                FROM claim_persons cp
                JOIN persons p ON cp.person_uuid = p.person_uuid
                LEFT JOIN person_unit_relations r ON p.person_uuid = r.person_uuid
                WHERE cp.claim_uuid = ?
            """, (claim["claim_uuid"],))

            claim["claimants"] = [
                dict(zip(["person_uuid", "first_name", "father_name", "last_name", "relation_type"], row))
                for row in cursor.fetchall()
            ]

            # Get related documents
            cursor.execute("""
                SELECT d.document_uuid, d.document_type, d.document_number,
                       d.issue_date, d.verified
                FROM claim_documents cd
                JOIN documents d ON cd.document_uuid = d.document_uuid
                WHERE cd.claim_uuid = ?
            """, (claim["claim_uuid"],))

            claim["documents"] = [
                dict(zip(["document_uuid", "document_type", "document_number",
                         "issue_date", "verified"], row))
                for row in cursor.fetchall()
            ]

            return claim

        except APIError:
            raise
        except Exception as e:
            logger.error(f"Error getting claim: {e}")
            raise APIError(str(e), 500)

    def create_claim(self, data: Dict, token: APIToken) -> Dict:
        """Create a new claim."""
        try:
            claim_uuid = str(uuid.uuid4())
            case_number = self._generate_case_number()

            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO claims (
                    claim_uuid, case_number, unit_uuid, case_status,
                    source, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_uuid,
                case_number,
                data.get("unit_uuid"),
                "Draft",
                "API",
                datetime.now().isoformat(),
                token.user_id if token else None
            ))

            self.db.commit()

            # Trigger webhook
            self._trigger_webhook("claim.created", {
                "claim_uuid": claim_uuid,
                "case_number": case_number
            })

            return {
                "claim_uuid": claim_uuid,
                "case_number": case_number,
                "status": "created"
            }

        except Exception as e:
            logger.error(f"Error creating claim: {e}")
            raise APIError(str(e), 500)

    def update_claim(self, claim_id: str, data: Dict, token: APIToken) -> Dict:
        """Update an existing claim."""
        try:
            cursor = self.db.cursor()

            # Verify claim exists
            cursor.execute("SELECT claim_uuid FROM claims WHERE claim_uuid = ?", (claim_id,))
            if not cursor.fetchone():
                raise APIError("Claim not found", 404)

            # Build update query
            update_fields = []
            params = []

            for field in ["case_status", "notes"]:
                if field in data:
                    update_fields.append(f"{field} = ?")
                    params.append(data[field])

            if not update_fields:
                raise APIError("No fields to update", 400)

            update_fields.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            update_fields.append("updated_by = ?")
            params.append(token.user_id if token else None)

            params.append(claim_id)

            cursor.execute(f"""
                UPDATE claims
                SET {', '.join(update_fields)}
                WHERE claim_uuid = ?
            """, params)

            self.db.commit()

            # Trigger webhook
            self._trigger_webhook("claim.updated", {
                "claim_uuid": claim_id,
                "updated_fields": list(data.keys())
            })

            return {"status": "updated", "claim_uuid": claim_id}

        except APIError:
            raise
        except Exception as e:
            logger.error(f"Error updating claim: {e}")
            raise APIError(str(e), 500)

    def get_document(self, doc_id: str) -> Dict:
        """Get document details."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT document_uuid, document_type, document_number,
                       issue_date, verified, attachment_hash, created_at
                FROM documents
                WHERE document_uuid = ?
            """, (doc_id,))

            row = cursor.fetchone()
            if not row:
                raise APIError("Document not found", 404)

            columns = ["document_uuid", "document_type", "document_number",
                      "issue_date", "verified", "attachment_hash", "created_at"]
            return dict(zip(columns, row))

        except APIError:
            raise
        except Exception as e:
            logger.error(f"Error getting document: {e}")
            raise APIError(str(e), 500)

    def get_statistics(self) -> Dict:
        """Get system statistics."""
        try:
            cursor = self.db.cursor()
            stats = {}

            # Claims by status
            cursor.execute("""
                SELECT case_status, COUNT(*)
                FROM claims
                GROUP BY case_status
            """)
            stats["claims_by_status"] = dict(cursor.fetchall())

            # Total counts
            cursor.execute("SELECT COUNT(*) FROM claims")
            stats["total_claims"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM buildings")
            stats["total_buildings"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM persons")
            stats["total_persons"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = cursor.fetchone()[0]

            # Recent activity
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM claims
                WHERE created_at >= DATE('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            stats["claims_last_30_days"] = [
                {"date": row[0], "count": row[1]}
                for row in cursor.fetchall()
            ]

            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise APIError(str(e), 500)

    def search_buildings(self, query: Dict) -> Dict:
        """Search buildings."""
        try:
            cursor = self.db.cursor()

            page = int(query.get("page", ["1"])[0])
            per_page = min(int(query.get("per_page", ["20"])[0]), 100)
            offset = (page - 1) * per_page

            where_clauses = ["1=1"]
            params = []

            if "neighborhood_code" in query:
                where_clauses.append("neighborhood_code = ?")
                params.append(query["neighborhood_code"][0])

            if "building_id" in query:
                where_clauses.append("building_id LIKE ?")
                params.append(f"%{query['building_id'][0]}%")

            where_sql = " AND ".join(where_clauses)

            cursor.execute(f"SELECT COUNT(*) FROM buildings WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT building_uuid, building_id, neighborhood_code,
                       building_type, building_status, latitude, longitude
                FROM buildings
                WHERE {where_sql}
                ORDER BY building_id
                LIMIT ? OFFSET ?
            """, params + [per_page, offset])

            columns = ["building_uuid", "building_id", "neighborhood_code",
                      "building_type", "building_status", "latitude", "longitude"]
            buildings = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {
                "buildings": buildings,
                "pagination": {
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": (total + per_page - 1) // per_page
                }
            }

        except Exception as e:
            logger.error(f"Error searching buildings: {e}")
            raise APIError(str(e), 500)

    def get_building(self, building_id: str) -> Dict:
        """Get building details."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT * FROM buildings
                WHERE building_uuid = ? OR building_id = ?
            """, (building_id, building_id))

            row = cursor.fetchone()
            if not row:
                raise APIError("Building not found", 404)

            columns = [desc[0] for desc in cursor.description]
            building = dict(zip(columns, row))

            # Get units
            cursor.execute("""
                SELECT unit_uuid, unit_id, unit_type, floor_number
                FROM units
                WHERE building_uuid = ?
            """, (building["building_uuid"],))

            building["units"] = [
                dict(zip(["unit_uuid", "unit_id", "unit_type", "floor_number"], row))
                for row in cursor.fetchall()
            ]

            return building

        except APIError:
            raise
        except Exception as e:
            logger.error(f"Error getting building: {e}")
            raise APIError(str(e), 500)

    def get_buildings_geojson(self, query: Dict) -> Dict:
        """Get buildings as GeoJSON."""
        if self.map_service:
            filters = {}
            if "neighborhood_code" in query:
                filters["neighborhood_code"] = query["neighborhood_code"][0]
            if "status" in query:
                filters["status"] = query["status"][0]

            buildings = self.map_service.get_buildings_by_neighborhood(
                filters.get("neighborhood_code", "")
            ) if filters.get("neighborhood_code") else []

            return self.map_service.export_to_geojson(buildings)

        return {"type": "FeatureCollection", "features": []}

    def get_claims_geojson(self, query: Dict) -> Dict:
        """Get claims as GeoJSON."""
        if self.map_service:
            filters = {}
            if "status" in query:
                filters["status"] = query["status"][0]
            return self.map_service.get_claims_geojson(filters)

        return {"type": "FeatureCollection", "features": []}

    def export_data(self, data: Dict, token: APIToken) -> Dict:
        """Export data in various formats."""
        export_format = data.get("format", "json")
        entity_type = data.get("entity", "claims")
        filters = data.get("filters", {})

        # This would integrate with export_service
        return {
            "status": "queued",
            "job_id": str(uuid.uuid4()),
            "format": export_format,
            "entity": entity_type
        }

    def search_claims_advanced(self, data: Dict) -> Dict:
        """Advanced claim search with complex filters."""
        return self.search_claims(data)

    def _generate_case_number(self) -> str:
        """Generate unique case number."""
        year = datetime.now().year
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT MAX(CAST(SUBSTR(case_number, 9) AS INTEGER))
                FROM claims
                WHERE case_number LIKE ?
            """, (f"CL-{year}-%",))

            max_seq = cursor.fetchone()[0] or 0
            return f"CL-{year}-{max_seq + 1:06d}"
        except Exception:
            return f"CL-{year}-{int(time.time()) % 1000000:06d}"

    def register_webhook(self, event: str, url: str, secret: str = None) -> str:
        """Register a webhook for an event."""
        if event not in self.webhooks:
            raise APIError(f"Unknown event: {event}", 400)

        webhook_id = str(uuid.uuid4())
        self.webhooks[event].append({
            "id": webhook_id,
            "url": url,
            "secret": secret,
            "created_at": datetime.now().isoformat()
        })

        return webhook_id

    def _trigger_webhook(self, event: str, data: Dict):
        """Trigger webhooks for an event."""
        import urllib.request

        for webhook in self.webhooks.get(event, []):
            try:
                payload = json.dumps({
                    "event": event,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }).encode("utf-8")

                # Add signature if secret is configured
                headers = {"Content-Type": "application/json"}
                if webhook.get("secret"):
                    signature = hmac.new(
                        webhook["secret"].encode(),
                        payload,
                        hashlib.sha256
                    ).hexdigest()
                    headers["X-Webhook-Signature"] = signature

                req = urllib.request.Request(
                    webhook["url"],
                    data=payload,
                    headers=headers,
                    method="POST"
                )

                # Fire and forget (async in production)
                threading.Thread(
                    target=lambda: urllib.request.urlopen(req, timeout=10)
                ).start()

            except Exception as e:
                logger.warning(f"Webhook delivery failed: {e}")

    def get_openapi_spec(self) -> Dict:
        """Generate OpenAPI specification."""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "TRRCMS REST API",
                "version": API_VERSION,
                "description": "Tenure Rights Registration and Claims Management System API"
            },
            "servers": [
                {"url": f"http://localhost:{self.port}/api/{API_VERSION}"}
            ],
            "paths": {
                "/claims": {
                    "get": {
                        "summary": "Search claims",
                        "security": [{"bearerAuth": []}],
                        "responses": {"200": {"description": "List of claims"}}
                    },
                    "post": {
                        "summary": "Create a new claim",
                        "security": [{"bearerAuth": []}],
                        "responses": {"201": {"description": "Claim created"}}
                    }
                },
                "/claims/{id}": {
                    "get": {
                        "summary": "Get claim details",
                        "security": [{"bearerAuth": []}],
                        "responses": {"200": {"description": "Claim details"}}
                    },
                    "put": {
                        "summary": "Update claim",
                        "security": [{"bearerAuth": []}],
                        "responses": {"200": {"description": "Claim updated"}}
                    }
                },
                "/vocabularies": {
                    "get": {
                        "summary": "Get controlled vocabularies",
                        "responses": {"200": {"description": "Vocabularies"}}
                    }
                },
                "/statistics": {
                    "get": {
                        "summary": "Get system statistics",
                        "security": [{"apiKey": []}],
                        "responses": {"200": {"description": "Statistics"}}
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer"
                    },
                    "apiKey": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    }
                }
            }
        }
