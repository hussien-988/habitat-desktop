# -*- coding: utf-8 -*-
"""
Local Network Sync Server Service - FR-D-15 Implementation.
Provides REST endpoint for tablet synchronization over LAN/Wi-Fi.
"""

import json
import os
import ssl
import socket
import threading
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

try:
    from zeroconf import ServiceInfo, Zeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

from utils.logger import get_logger

logger = get_logger(__name__)

# Default configuration
DEFAULT_PORT = 8443
SERVICE_TYPE = "_trrcms._tcp.local."
SERVICE_NAME = "TRRCMS-Desktop"


@dataclass
class SyncSession:
    """Represents an active sync session with a tablet."""
    session_id: str
    device_id: str
    device_name: str
    connected_at: datetime
    last_activity: datetime
    status: str  # connected, syncing, idle, disconnected
    bytes_transferred: int = 0
    records_synced: int = 0
    current_operation: Optional[str] = None


@dataclass
class SyncStatus:
    """Overall sync server status."""
    is_running: bool
    port: int
    local_ip: str
    connected_tablets: int
    active_transfers: int
    total_synced_today: int
    uptime_seconds: float


class SyncRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for sync server."""

    server: 'SyncHTTPServer'

    def log_message(self, format: str, *args):
        """Override to use our logger."""
        logger.debug(f"Sync Server: {format % args}")

    def _send_json_response(self, data: Dict, status_code: int = 200):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _send_error_response(self, message: str, status_code: int = 400):
        """Send error response."""
        self._send_json_response({"error": message, "success": False}, status_code)

    def _authenticate_request(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Authenticate incoming request."""
        auth_header = self.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return False, None, "Missing or invalid authorization header"

        token = auth_header[7:]

        # Validate token (in production, use proper JWT validation)
        if self.server.sync_service.validate_auth_token(token):
            device_id = self.server.sync_service.get_device_from_token(token)
            return True, device_id, None

        return False, None, "Invalid authentication token"

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Health check endpoint (no auth required)
        if path == "/api/health":
            self._send_json_response({
                "status": "healthy",
                "service": "TRRCMS-Sync-Server",
                "version": "1.0.0",
                "timestamp": datetime.utcnow().isoformat()
            })
            return

        # Discovery endpoint (no auth required)
        if path == "/api/discover":
            self._send_json_response({
                "service": "TRRCMS-Sync-Server",
                "version": "1.0.0",
                "capabilities": ["sync", "vocabularies", "assignments"],
                "requires_auth": True
            })
            return

        # Authenticated endpoints
        is_auth, device_id, error = self._authenticate_request()
        if not is_auth:
            self._send_error_response(error, 401)
            return

        if path == "/api/sync/status":
            status = self.server.sync_service.get_sync_status(device_id)
            self._send_json_response(status)

        elif path == "/api/vocabularies":
            vocabularies = self.server.sync_service.get_vocabularies()
            self._send_json_response(vocabularies)

        elif path == "/api/assignments":
            assignments = self.server.sync_service.get_device_assignments(device_id)
            self._send_json_response(assignments)

        elif path.startswith("/api/buildings/"):
            building_id = path.split("/")[-1]
            building = self.server.sync_service.get_building(building_id)
            if building:
                self._send_json_response(building)
            else:
                self._send_error_response("Building not found", 404)

        else:
            self._send_error_response("Endpoint not found", 404)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Auth endpoint (no auth required)
        if path == "/api/auth":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(body)
                result = self.server.sync_service.authenticate_device(
                    data.get("device_id"),
                    data.get("username"),
                    data.get("password")
                )
                if result.get("success"):
                    self._send_json_response(result)
                else:
                    self._send_error_response(result.get("error", "Authentication failed"), 401)
            except json.JSONDecodeError:
                self._send_error_response("Invalid JSON", 400)
            return

        # Authenticated endpoints
        is_auth, device_id, error = self._authenticate_request()
        if not is_auth:
            self._send_error_response(error, 401)
            return

        if path == "/api/sync/upload":
            self._handle_upload(device_id)

        elif path == "/api/sync/start":
            result = self.server.sync_service.start_sync_session(device_id)
            self._send_json_response(result)

        elif path == "/api/sync/complete":
            result = self.server.sync_service.complete_sync_session(device_id)
            self._send_json_response(result)

        else:
            self._send_error_response("Endpoint not found", 404)

    def _handle_upload(self, device_id: str):
        """Handle .uhc package upload from tablet."""
        content_length = int(self.headers.get("Content-Length", 0))

        if content_length > 500 * 1024 * 1024:  # 500MB limit
            self._send_error_response("File too large", 413)
            return

        # Update session status
        self.server.sync_service.update_session_status(device_id, "syncing", "Receiving data")

        try:
            # Read the uploaded file
            file_data = self.rfile.read(content_length)

            # Save to temp location
            result = self.server.sync_service.receive_package(device_id, file_data)

            if result.get("success"):
                self._send_json_response(result)
            else:
                self._send_error_response(result.get("error", "Upload failed"), 500)

        except Exception as e:
            logger.error(f"Upload error: {e}", exc_info=True)
            self._send_error_response(f"Upload error: {str(e)}", 500)
        finally:
            self.server.sync_service.update_session_status(device_id, "idle")


class SyncHTTPServer(HTTPServer):
    """Extended HTTPServer with sync service reference."""

    def __init__(self, server_address, RequestHandlerClass, sync_service):
        super().__init__(server_address, RequestHandlerClass)
        self.sync_service = sync_service


class LocalNetworkSyncService:
    """
    Local Network Sync Server Service.

    Implements FR-D-15:
    - REST endpoint on configurable port
    - mDNS/Bonjour for automatic discovery
    - TLS encryption
    - Authentication via local credentials
    - Real-time sync status
    - Multiple simultaneous tablet connections
    """

    def __init__(
        self,
        db_connection,
        uhc_service,
        port: int = DEFAULT_PORT,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        upload_dir: Optional[str] = None
    ):
        self.db = db_connection
        self.uhc_service = uhc_service
        self.port = port
        self.cert_file = cert_file
        self.key_file = key_file
        self.upload_dir = Path(upload_dir) if upload_dir else Path("uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        self.server: Optional[SyncHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.zeroconf: Optional['Zeroconf'] = None
        self.service_info: Optional['ServiceInfo'] = None

        self.sessions: Dict[str, SyncSession] = {}
        self.auth_tokens: Dict[str, str] = {}  # token -> device_id
        self.start_time: Optional[datetime] = None

        self._callbacks: Dict[str, List[Callable]] = {
            "tablet_connected": [],
            "tablet_disconnected": [],
            "sync_started": [],
            "sync_completed": [],
            "sync_failed": [],
            "package_received": []
        }

    def start(self) -> bool:
        """Start the sync server."""
        try:
            self.local_ip = self._get_local_ip()

            # Create server
            self.server = SyncHTTPServer(
                ("0.0.0.0", self.port),
                SyncRequestHandler,
                self
            )

            # Enable TLS if certificates provided
            if self.cert_file and self.key_file and os.path.exists(self.cert_file):
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(self.cert_file, self.key_file)
                self.server.socket = context.wrap_socket(
                    self.server.socket,
                    server_side=True
                )
                logger.info("TLS enabled for sync server")

            # Start server thread
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()

            self.start_time = datetime.now()

            # Register mDNS service
            self._register_mdns_service()

            logger.info(f"Sync server started on {self.local_ip}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start sync server: {e}", exc_info=True)
            return False

    def stop(self):
        """Stop the sync server."""
        try:
            # Unregister mDNS
            if self.zeroconf and self.service_info:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()

            # Stop server
            if self.server:
                self.server.shutdown()

            logger.info("Sync server stopped")

        except Exception as e:
            logger.error(f"Error stopping sync server: {e}", exc_info=True)

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _register_mdns_service(self):
        """Register service for mDNS/Bonjour discovery."""
        if not ZEROCONF_AVAILABLE:
            logger.warning("Zeroconf not available, mDNS discovery disabled")
            return

        try:
            self.zeroconf = Zeroconf()

            self.service_info = ServiceInfo(
                SERVICE_TYPE,
                f"{SERVICE_NAME}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(self.local_ip)],
                port=self.port,
                properties={
                    "version": "1.0.0",
                    "service": "TRRCMS",
                    "protocol": "https" if self.cert_file else "http"
                }
            )

            self.zeroconf.register_service(self.service_info)
            logger.info(f"mDNS service registered: {SERVICE_NAME}")

        except Exception as e:
            logger.warning(f"Could not register mDNS service: {e}")

    def get_status(self) -> SyncStatus:
        """Get current server status."""
        uptime = 0.0
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()

        active_transfers = sum(1 for s in self.sessions.values() if s.status == "syncing")

        return SyncStatus(
            is_running=self.server is not None,
            port=self.port,
            local_ip=self.local_ip if hasattr(self, 'local_ip') else "unknown",
            connected_tablets=len([s for s in self.sessions.values() if s.status != "disconnected"]),
            active_transfers=active_transfers,
            total_synced_today=self._get_today_sync_count(),
            uptime_seconds=uptime
        )

    def _get_today_sync_count(self) -> int:
        """Get count of sync operations today."""
        try:
            cursor = self.db.cursor()
            today = datetime.now().date().isoformat()
            cursor.execute("""
                SELECT COUNT(*) FROM sync_log
                WHERE DATE(synced_at) = ?
            """, (today,))
            return cursor.fetchone()[0]
        except Exception:
            return 0

    def get_connected_devices(self) -> List[Dict]:
        """Get list of connected devices."""
        return [
            asdict(session)
            for session in self.sessions.values()
            if session.status != "disconnected"
        ]

    def authenticate_device(
        self,
        device_id: str,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate a device/user.

        Returns:
            Dict with success status and token if successful
        """
        try:
            # Validate credentials against database
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT user_id, password_hash, role
                FROM users
                WHERE username = ? AND is_active = 1
            """, (username,))

            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Invalid credentials"}

            user_id, password_hash, role = row

            # Verify password (simplified - use proper hashing in production)
            import hashlib
            computed_hash = hashlib.sha256(password.encode()).hexdigest()
            if computed_hash != password_hash:
                return {"success": False, "error": "Invalid credentials"}

            # Generate auth token
            token = str(uuid.uuid4())
            self.auth_tokens[token] = device_id

            # Create session
            session = SyncSession(
                session_id=str(uuid.uuid4()),
                device_id=device_id,
                device_name=f"Tablet-{device_id[:8]}",
                connected_at=datetime.now(),
                last_activity=datetime.now(),
                status="connected"
            )
            self.sessions[device_id] = session

            # Trigger callback
            self._trigger_callback("tablet_connected", session)

            logger.info(f"Device authenticated: {device_id}")

            return {
                "success": True,
                "token": token,
                "user_id": user_id,
                "role": role,
                "expires_in": 3600 * 24  # 24 hours
            }

        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def validate_auth_token(self, token: str) -> bool:
        """Validate an authentication token."""
        return token in self.auth_tokens

    def get_device_from_token(self, token: str) -> Optional[str]:
        """Get device ID from token."""
        return self.auth_tokens.get(token)

    def get_sync_status(self, device_id: str) -> Dict[str, Any]:
        """Get sync status for a device."""
        session = self.sessions.get(device_id)
        if not session:
            return {"status": "not_connected"}

        return asdict(session)

    def update_session_status(
        self,
        device_id: str,
        status: str,
        operation: Optional[str] = None
    ):
        """Update session status."""
        session = self.sessions.get(device_id)
        if session:
            session.status = status
            session.current_operation = operation
            session.last_activity = datetime.now()

    def start_sync_session(self, device_id: str) -> Dict[str, Any]:
        """Start a sync session for a device."""
        session = self.sessions.get(device_id)
        if not session:
            return {"success": False, "error": "Device not connected"}

        session.status = "syncing"
        session.current_operation = "Starting sync"

        self._trigger_callback("sync_started", session)

        return {"success": True, "session_id": session.session_id}

    def complete_sync_session(self, device_id: str) -> Dict[str, Any]:
        """Complete a sync session."""
        session = self.sessions.get(device_id)
        if not session:
            return {"success": False, "error": "Device not connected"}

        session.status = "idle"
        session.current_operation = None

        # Log sync
        self._log_sync(session)

        self._trigger_callback("sync_completed", session)

        return {
            "success": True,
            "records_synced": session.records_synced,
            "bytes_transferred": session.bytes_transferred
        }

    def receive_package(self, device_id: str, file_data: bytes) -> Dict[str, Any]:
        """
        Receive and process a .uhc package from a tablet.

        Implements S12-S14 from UC-003.
        """
        session = self.sessions.get(device_id)

        try:
            # Save to temp file
            package_id = str(uuid.uuid4())
            file_path = self.upload_dir / f"{package_id}.uhc"

            with open(file_path, "wb") as f:
                f.write(file_data)

            # Update session
            if session:
                session.bytes_transferred += len(file_data)

            # Verify and import using UHC service
            import_result = self.uhc_service.import_from_uhc(
                file_path,
                imported_by=f"sync:{device_id}"
            )

            if import_result.get("success"):
                if session:
                    session.records_synced += sum(
                        import_result.get("record_counts", {}).values()
                    )

                self._trigger_callback("package_received", {
                    "device_id": device_id,
                    "package_id": package_id,
                    "result": import_result
                })

                return {
                    "success": True,
                    "package_id": package_id,
                    "staging_id": import_result.get("staging_id"),
                    "record_counts": import_result.get("record_counts", {}),
                    "duplicates_found": import_result.get("duplicates_found", {})
                }
            else:
                # Quarantine failed package
                quarantine_path = self.upload_dir / "quarantine" / f"{package_id}.uhc"
                quarantine_path.parent.mkdir(exist_ok=True)
                file_path.rename(quarantine_path)

                return {
                    "success": False,
                    "error": import_result.get("error", "Import failed"),
                    "package_id": package_id
                }

        except Exception as e:
            logger.error(f"Package receive error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def get_vocabularies(self) -> Dict[str, Any]:
        """Get all vocabularies for sync to tablet."""
        try:
            cursor = self.db.cursor()
            vocabularies = {}

            # Get all vocabulary tables
            vocab_tables = [
                "building_type", "unit_type", "relation_type",
                "case_status", "document_type", "occupancy_type"
            ]

            for table in vocab_tables:
                try:
                    cursor.execute(f"""
                        SELECT code, label_ar, label_en, is_active
                        FROM vocabularies
                        WHERE vocabulary_name = ?
                        ORDER BY display_order
                    """, (table,))

                    vocabularies[table] = {
                        "terms": [
                            {
                                "code": row[0],
                                "label_ar": row[1],
                                "label_en": row[2],
                                "is_active": bool(row[3])
                            }
                            for row in cursor.fetchall()
                        ],
                        "version": self._get_vocab_version(table)
                    }
                except Exception as e:
                    logger.warning(f"Could not load vocabulary {table}: {e}")

            return {
                "success": True,
                "vocabularies": vocabularies,
                "updated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting vocabularies: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _get_vocab_version(self, vocab_name: str) -> str:
        """Get current version of a vocabulary."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT version FROM vocabulary_versions
                WHERE vocabulary_name = ?
                ORDER BY effective_from DESC
                LIMIT 1
            """, (vocab_name,))
            row = cursor.fetchone()
            return row[0] if row else "1.0.0"
        except Exception:
            return "1.0.0"

    def get_device_assignments(self, device_id: str) -> Dict[str, Any]:
        """Get building assignments for a device."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT ba.building_uuid, ba.assigned_at, ba.transfer_status,
                       b.building_id, b.neighborhood_code
                FROM building_assignments ba
                JOIN buildings b ON ba.building_uuid = b.building_uuid
                WHERE ba.device_id = ? AND ba.transfer_status != 'completed'
            """, (device_id,))

            assignments = []
            for row in cursor.fetchall():
                assignments.append({
                    "building_uuid": row[0],
                    "assigned_at": row[1],
                    "transfer_status": row[2],
                    "building_id": row[3],
                    "neighborhood_code": row[4]
                })

            return {
                "success": True,
                "assignments": assignments,
                "count": len(assignments)
            }

        except Exception as e:
            logger.error(f"Error getting assignments: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def get_building(self, building_id: str) -> Optional[Dict]:
        """Get full building data for sync."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT * FROM buildings WHERE building_uuid = ? OR building_id = ?
            """, (building_id, building_id))

            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            building = dict(zip(columns, row))

            # Get units
            cursor.execute("""
                SELECT * FROM units WHERE building_uuid = ?
            """, (building["building_uuid"],))

            unit_columns = [desc[0] for desc in cursor.description]
            building["units"] = [dict(zip(unit_columns, r)) for r in cursor.fetchall()]

            return building

        except Exception as e:
            logger.error(f"Error getting building: {e}", exc_info=True)
            return None

    def _log_sync(self, session: SyncSession):
        """Log sync operation."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO sync_log (
                    sync_id, device_id, synced_at, records_synced,
                    bytes_transferred, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                session.device_id,
                datetime.now().isoformat(),
                session.records_synced,
                session.bytes_transferred,
                "completed"
            ))
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not log sync: {e}")

    def on(self, event: str, callback: Callable):
        """Register event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _trigger_callback(self, event: str, data: Any):
        """Trigger event callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"Callback error for {event}: {e}")
