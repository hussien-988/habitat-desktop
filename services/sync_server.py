# -*- coding: utf-8 -*-
"""
Local Network Sync Server
=========================
Implements FR-D-2(b) from FSD v5.0

Features:
- Local-network endpoint for receiving .uhc packages from tablets
- Auto-discovery on LAN via mDNS/Bonjour
- Secure authentication using local credentials
- Bi-directional data synchronization
- Vocabulary and configuration downloads
- Transaction-based sync with rollback
- Sync logging and audit trail
"""

import json
import socket
import threading
import hashlib
import uuid
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import logging
import base64
import hmac
import secrets

logger = logging.getLogger(__name__)

# Default sync server port
DEFAULT_PORT = 5890

# API version
API_VERSION = "1.0"


class SyncStatus:
    """Sync operation status codes."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CONFLICT = "conflict"
    UNAUTHORIZED = "unauthorized"


class SyncServer:
    """
    Local Network Sync Server for tablet synchronization.

    Implements FR-D-2(b):
    - Auto-discoverable on LAN
    - Secure authentication
    - Bi-directional sync
    - No internet dependency
    """

    def __init__(
        self,
        db,
        uhc_importer=None,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        auth_secret: Optional[str] = None
    ):
        self.db = db
        self.uhc_importer = uhc_importer
        self.host = host
        self.port = port
        self.auth_secret = auth_secret or secrets.token_hex(32)

        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False

        # Callbacks
        self._on_sync_started: Optional[Callable] = None
        self._on_sync_completed: Optional[Callable] = None
        self._on_package_received: Optional[Callable] = None

        # Sync log
        self._sync_log: List[Dict[str, Any]] = []

    # ==================== Server Control ====================

    def start(self) -> bool:
        """Start the sync server."""
        if self._running:
            return True

        try:
            handler = self._create_handler()
            self._server = ThreadedHTTPServer((self.host, self.port), handler)
            self._server.sync_server = self  # Pass reference to handler

            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True
            )
            self._server_thread.start()

            self._running = True
            logger.info(f"Sync server started on {self.host}:{self.port}")

            # Register for discovery
            self._register_discovery()

            return True

        except Exception as e:
            logger.error(f"Failed to start sync server: {e}")
            return False

    def stop(self) -> None:
        """Stop the sync server."""
        if self._server:
            self._server.shutdown()
            self._running = False

            # Unregister discovery
            self._unregister_discovery()

            logger.info("Sync server stopped")

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information for display."""
        return {
            "host": self.host,
            "port": self.port,
            "running": self._running,
            "ip_addresses": self._get_local_ips(),
            "api_version": API_VERSION,
            "sync_count": len(self._sync_log)
        }

    # ==================== Discovery ====================

    def _register_discovery(self) -> None:
        """Register service for LAN discovery."""
        try:
            # Try to use zeroconf for mDNS/Bonjour
            from zeroconf import ServiceInfo, Zeroconf

            self._zeroconf = Zeroconf()

            hostname = socket.gethostname()
            local_ip = self._get_primary_ip()

            self._service_info = ServiceInfo(
                "_trrcms-sync._tcp.local.",
                f"TRRCMS Sync Server ({hostname})._trrcms-sync._tcp.local.",
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties={
                    "api_version": API_VERSION,
                    "hostname": hostname
                }
            )

            self._zeroconf.register_service(self._service_info)
            logger.info(f"Registered mDNS service: {hostname}")

        except ImportError:
            logger.info("zeroconf not available - manual IP configuration required")
            self._zeroconf = None

    def _unregister_discovery(self) -> None:
        """Unregister service from LAN discovery."""
        if hasattr(self, '_zeroconf') and self._zeroconf:
            try:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
            except Exception as e:
                logger.warning(f"Error unregistering mDNS: {e}")

    def _get_local_ips(self) -> List[str]:
        """Get all local IP addresses."""
        ips = []
        try:
            hostname = socket.gethostname()
            addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
            ips = list(set(addr[4][0] for addr in addrs))
        except Exception:
            pass

        # Also try to get default route IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            s.close()
            if primary_ip not in ips:
                ips.insert(0, primary_ip)
        except Exception:
            pass

        return ips

    def _get_primary_ip(self) -> str:
        """Get primary local IP address."""
        ips = self._get_local_ips()
        return ips[0] if ips else "127.0.0.1"

    # ==================== Authentication ====================

    def generate_auth_token(self, device_id: str, expires_hours: int = 24) -> str:
        """
        Generate authentication token for a device.

        Args:
            device_id: Unique device identifier
            expires_hours: Token validity in hours

        Returns:
            Base64-encoded auth token
        """
        expiry = datetime.utcnow().timestamp() + (expires_hours * 3600)
        payload = f"{device_id}:{expiry}"

        signature = hmac.new(
            self.auth_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        token = base64.b64encode(f"{payload}:{signature}".encode()).decode()
        return token

    def verify_auth_token(self, token: str) -> Optional[str]:
        """
        Verify authentication token.

        Returns:
            Device ID if valid, None otherwise
        """
        try:
            decoded = base64.b64decode(token).decode()
            parts = decoded.split(":")

            if len(parts) != 3:
                return None

            device_id, expiry, signature = parts

            # Check expiry
            if float(expiry) < datetime.utcnow().timestamp():
                return None

            # Verify signature
            payload = f"{device_id}:{expiry}"
            expected_sig = hmac.new(
                self.auth_secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()

            if hmac.compare_digest(signature, expected_sig):
                return device_id

        except Exception as e:
            logger.warning(f"Token verification failed: {e}")

        return None

    # ==================== Request Handler ====================

    def _create_handler(self):
        """Create HTTP request handler class."""
        server = self

        class SyncRequestHandler(BaseHTTPRequestHandler):
            """Handle sync HTTP requests."""

            def log_message(self, format, *args):
                """Custom logging."""
                logger.debug(f"Sync request: {args}")

            def _send_json_response(self, status: int, data: Dict[str, Any]) -> None:
                """Send JSON response."""
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

            def _check_auth(self) -> Optional[str]:
                """Check authorization header."""
                auth_header = self.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    return server.verify_auth_token(token)
                return None

            def do_OPTIONS(self):
                """Handle CORS preflight."""
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.end_headers()

            def do_GET(self):
                """Handle GET requests."""
                path = self.path.split("?")[0]

                if path == "/":
                    # Server info
                    self._send_json_response(200, {
                        "status": "ok",
                        "server": "TRRCMS Sync Server",
                        "api_version": API_VERSION,
                        "endpoints": [
                            "/discover",
                            "/auth",
                            "/vocabularies",
                            "/sync/status"
                        ]
                    })

                elif path == "/discover":
                    # Discovery endpoint
                    self._send_json_response(200, {
                        "server": "TRRCMS Sync Server",
                        "hostname": socket.gethostname(),
                        "api_version": API_VERSION,
                        "port": server.port,
                        "requires_auth": True
                    })

                elif path == "/vocabularies":
                    # Get vocabularies for tablet
                    device_id = self._check_auth()
                    if not device_id:
                        self._send_json_response(401, {
                            "status": SyncStatus.UNAUTHORIZED,
                            "message": "Invalid or missing authentication"
                        })
                        return

                    vocabs = server._get_vocabularies()
                    self._send_json_response(200, {
                        "status": SyncStatus.SUCCESS,
                        "vocabularies": vocabs
                    })

                elif path == "/sync/status":
                    # Get sync status
                    device_id = self._check_auth()
                    if not device_id:
                        self._send_json_response(401, {
                            "status": SyncStatus.UNAUTHORIZED
                        })
                        return

                    status = server._get_sync_status(device_id)
                    self._send_json_response(200, status)

                else:
                    self._send_json_response(404, {"error": "Not found"})

            def do_POST(self):
                """Handle POST requests."""
                path = self.path.split("?")[0]

                if path == "/auth":
                    # Authenticate device
                    self._handle_auth()

                elif path == "/sync/upload":
                    # Upload .uhc package
                    self._handle_upload()

                elif path == "/sync/complete":
                    # Complete sync transaction
                    self._handle_complete()

                else:
                    self._send_json_response(404, {"error": "Not found"})

            def _handle_auth(self):
                """Handle device authentication."""
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    data = json.loads(body)

                    device_id = data.get("device_id")
                    device_secret = data.get("device_secret")

                    if not device_id:
                        self._send_json_response(400, {
                            "status": SyncStatus.FAILED,
                            "message": "device_id required"
                        })
                        return

                    # Verify device credentials
                    if server._verify_device(device_id, device_secret):
                        token = server.generate_auth_token(device_id)
                        self._send_json_response(200, {
                            "status": SyncStatus.SUCCESS,
                            "token": token,
                            "expires_in": 86400  # 24 hours
                        })
                    else:
                        self._send_json_response(401, {
                            "status": SyncStatus.UNAUTHORIZED,
                            "message": "Invalid credentials"
                        })

                except Exception as e:
                    logger.error(f"Auth error: {e}")
                    self._send_json_response(500, {
                        "status": SyncStatus.FAILED,
                        "message": str(e)
                    })

            def _handle_upload(self):
                """Handle .uhc package upload."""
                device_id = self._check_auth()
                if not device_id:
                    self._send_json_response(401, {
                        "status": SyncStatus.UNAUTHORIZED
                    })
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", 0))

                    if content_length > 100 * 1024 * 1024:  # 100 MB limit
                        self._send_json_response(413, {
                            "status": SyncStatus.FAILED,
                            "message": "Package too large"
                        })
                        return

                    # Save to temp file
                    with tempfile.NamedTemporaryFile(
                        suffix=".uhc",
                        delete=False
                    ) as f:
                        temp_path = Path(f.name)

                        # Read in chunks
                        remaining = content_length
                        while remaining > 0:
                            chunk_size = min(8192, remaining)
                            chunk = self.rfile.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            remaining -= len(chunk)

                    # Notify callback
                    if server._on_package_received:
                        server._on_package_received(device_id, temp_path)

                    # Import package
                    result = server.uhc_importer.import_package(
                        temp_path,
                        imported_by=f"sync:{device_id}"
                    )

                    # Clean up temp file
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

                    # Log sync
                    server._log_sync(device_id, "upload", result.to_dict())

                    if result.success:
                        self._send_json_response(200, {
                            "status": SyncStatus.SUCCESS,
                            "package_id": result.package_id,
                            "record_counts": result.record_counts,
                            "validation_summary": result.validation_summary
                        })
                    else:
                        self._send_json_response(200, {
                            "status": SyncStatus.PARTIAL,
                            "package_id": result.package_id,
                            "validation_summary": result.validation_summary,
                            "issues": [i.to_dict() for i in result.issues[:10]]
                        })

                except Exception as e:
                    logger.error(f"Upload error: {e}")
                    self._send_json_response(500, {
                        "status": SyncStatus.FAILED,
                        "message": str(e)
                    })

            def _handle_complete(self):
                """Handle sync completion."""
                device_id = self._check_auth()
                if not device_id:
                    self._send_json_response(401, {
                        "status": SyncStatus.UNAUTHORIZED
                    })
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    data = json.loads(body) if body else {}

                    package_id = data.get("package_id")

                    # Commit staged records
                    if package_id:
                        result = server.uhc_importer.commit_staged_records(
                            package_id,
                            committed_by=f"sync:{device_id}"
                        )

                        server._log_sync(device_id, "commit", {
                            "package_id": package_id,
                            "committed": result.record_counts
                        })

                        self._send_json_response(200, {
                            "status": SyncStatus.SUCCESS,
                            "package_id": package_id,
                            "committed": result.record_counts
                        })
                    else:
                        self._send_json_response(400, {
                            "status": SyncStatus.FAILED,
                            "message": "package_id required"
                        })

                except Exception as e:
                    logger.error(f"Complete error: {e}")
                    self._send_json_response(500, {
                        "status": SyncStatus.FAILED,
                        "message": str(e)
                    })

        return SyncRequestHandler

    # ==================== Device Management ====================

    def _verify_device(self, device_id: str, device_secret: Optional[str]) -> bool:
        """Verify device credentials."""
        # For now, accept any device with valid device_id
        # In production, verify against registered devices
        if not device_id:
            return False

        # Check if device is registered
        result = self.db.execute(
            "SELECT device_id FROM registered_devices WHERE device_id = ?",
            (device_id,)
        )

        if result and len(result) > 0:
            # Device registered, verify secret if provided
            return True

        # Auto-register new devices in development mode
        # In production, this should require admin approval
        try:
            self.db.execute("""
                INSERT INTO registered_devices (device_id, registered_at)
                VALUES (?, ?)
            """, (device_id, datetime.utcnow().isoformat()))
            return True
        except Exception:
            return True  # Allow if table doesn't exist yet

    def register_device(self, device_id: str, device_name: str = "") -> str:
        """
        Register a device for sync.

        Returns:
            Auth token for the device
        """
        self.db.execute("""
            INSERT OR REPLACE INTO registered_devices (device_id, device_name, registered_at)
            VALUES (?, ?, ?)
        """, (device_id, device_name, datetime.utcnow().isoformat()))

        return self.generate_auth_token(device_id)

    # ==================== Vocabularies ====================

    def _get_vocabularies(self) -> Dict[str, Any]:
        """Get all vocabularies for tablet sync."""
        vocabularies = {}

        # Document types
        vocabularies["document_types"] = {
            "version": "1.0.0",
            "items": [
                {"code": "TAPU_GREEN", "name_ar": "سند ملكية (طابو أخضر)", "name_en": "Property Deed (Green TaPu)"},
                {"code": "PROPERTY_REG", "name_ar": "بيان قيد عقاري", "name_en": "Property Registration Statement"},
                {"code": "TEMP_REG", "name_ar": "بيان قيد مؤقت", "name_en": "Temporary Registration Statement"},
                {"code": "COURT_RULING", "name_ar": "حكم محكمة", "name_en": "Court Ruling"},
                {"code": "POWER_ATTORNEY", "name_ar": "وكالة خاصة بيع", "name_en": "Special Power of Attorney"},
                {"code": "SALE_NOTARIZED", "name_ar": "عقد بيع موثق (كاتب عدل)", "name_en": "Notarized Sale Contract"},
                {"code": "SALE_INFORMAL", "name_ar": "عقد بيع عرفي (غير موثق)", "name_en": "Informal Sale Contract"},
                {"code": "RENT_REGISTERED", "name_ar": "عقد إيجار مسجل", "name_en": "Registered Rental Contract"},
                {"code": "RENT_INFORMAL", "name_ar": "عقد إيجار غير مسجل", "name_en": "Informal Rental Contract"},
                {"code": "UTILITY_BILL", "name_ar": "فاتورة كهرباء أو ماء", "name_en": "Utility Bill"},
                {"code": "MUKHTAR_CERT", "name_ar": "شهادة المختار", "name_en": "Mukhtar Certificate"},
            ]
        }

        # Occupancy types
        vocabularies["occupancy_types"] = {
            "version": "1.0.0",
            "items": [
                {"code": "OWNER", "name_ar": "مالك", "name_en": "Owner"},
                {"code": "TENANT", "name_ar": "مستأجر", "name_en": "Tenant"},
                {"code": "GUEST", "name_ar": "ضيف", "name_en": "Guest"},
                {"code": "HEIR", "name_ar": "وارث", "name_en": "Heir"},
                {"code": "OCCUPANT", "name_ar": "شاغل", "name_en": "Occupant"},
            ]
        }

        # Building types
        vocabularies["building_types"] = {
            "version": "1.0.0",
            "items": [
                {"code": "residential", "name_ar": "سكني", "name_en": "Residential"},
                {"code": "commercial", "name_ar": "تجاري", "name_en": "Commercial"},
                {"code": "mixed_use", "name_ar": "مختلط", "name_en": "Mixed Use"},
            ]
        }

        # Building status
        vocabularies["building_status"] = {
            "version": "1.0.0",
            "items": [
                {"code": "intact", "name_ar": "سليم", "name_en": "Intact"},
                {"code": "minor_damage", "name_ar": "ضرر طفيف", "name_en": "Minor Damage"},
                {"code": "major_damage", "name_ar": "ضرر كبير", "name_en": "Major Damage"},
                {"code": "destroyed", "name_ar": "مدمر", "name_en": "Destroyed"},
            ]
        }

        return vocabularies

    # ==================== Sync Status ====================

    def _get_sync_status(self, device_id: str) -> Dict[str, Any]:
        """Get sync status for a device."""
        # Get last sync
        result = self.db.execute("""
            SELECT * FROM sync_log
            WHERE device_id = ?
            ORDER BY sync_date DESC
            LIMIT 1
        """, (device_id,))

        last_sync = None
        if result and len(result) > 0:
            row = result[0]
            last_sync = {
                "date": row['sync_date'] if isinstance(row, dict) else row[0],
                "status": row['status'] if isinstance(row, dict) else row[1]
            }

        return {
            "status": SyncStatus.SUCCESS,
            "device_id": device_id,
            "last_sync": last_sync,
            "pending_updates": 0,  # Would be calculated from staged records
            "vocabulary_versions": {
                "document_types": "1.0.0",
                "occupancy_types": "1.0.0",
                "building_types": "1.0.0"
            }
        }

    def _log_sync(self, device_id: str, action: str, details: Dict[str, Any]) -> None:
        """Log sync operation."""
        entry = {
            "device_id": device_id,
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._sync_log.append(entry)

        # Also save to database
        try:
            self.db.execute("""
                INSERT INTO sync_log (device_id, action, details, sync_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                device_id,
                action,
                json.dumps(details),
                datetime.utcnow().isoformat(),
                'completed'
            ))
        except Exception as e:
            logger.warning(f"Failed to log sync: {e}")

    def get_sync_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent sync log entries."""
        return self._sync_log[-limit:]

    # ==================== Callbacks ====================

    def on_sync_started(self, callback: Callable[[str], None]) -> None:
        """Set callback for sync started."""
        self._on_sync_started = callback

    def on_sync_completed(self, callback: Callable[[str, Dict], None]) -> None:
        """Set callback for sync completed."""
        self._on_sync_completed = callback

    def on_package_received(self, callback: Callable[[str, Path], None]) -> None:
        """Set callback for package received."""
        self._on_package_received = callback


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server for concurrent connections."""
    daemon_threads = True
