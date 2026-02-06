# -*- coding: utf-8 -*-
"""
Tile Server Manager - Centralized tile server management.

Provides a single point of access to the tile server for all UI components.
Makes it easy to switch between local and production servers.
"""

import os
import socket
import sqlite3
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from app.config import Config
from app.api_config import get_active_tile_server_url, get_tile_server_settings
from utils.logger import get_logger

logger = get_logger(__name__)


def find_free_port() -> int:
    """Find a free port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class TileServer(BaseHTTPRequestHandler):
    """HTTP server to serve tiles from MBTiles file and static assets - OPTIMIZED."""

    mbtiles_path = None
    assets_path = None
    _tile_cache = {}  # In-memory tile cache
    _db_connection = None  # Persistent database connection
    _static_cache = {}  # Cache for static files
    _html_cache = {}  # Cache for dynamically generated HTML pages
    _perf_stats = {
        'cache_hits': 0,
        'cache_misses': 0,
        'db_queries': 0,
        'total_requests': 0
    }

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    @classmethod
    def _get_db_connection(cls):
        """Get persistent database connection."""
        if cls._db_connection is None and cls.mbtiles_path:
            cls._db_connection = sqlite3.connect(
                str(cls.mbtiles_path),
                check_same_thread=False,
                timeout=10.0
            )
            cls._db_connection.execute("PRAGMA mmap_size = 268435456")
            cls._db_connection.execute("PRAGMA page_size = 4096")
            cls._db_connection.execute("PRAGMA cache_size = -64000")
        return cls._db_connection

    def do_GET(self):
        """Handle GET requests for tiles and static files."""
        try:
            path = self.path.split('?')[0]

            # DEBUG: Log ALL requests including tiles (temporarily for debugging)
            logger.info(f"Tile server request: {path}")

            if path == '/leaflet.js':
                self._serve_static_file_cached(self.assets_path / 'leaflet.js', 'application/javascript')
            elif path == '/leaflet.css':
                self._serve_static_file_cached(self.assets_path / 'leaflet.css', 'text/css')
            elif path == '/leaflet-draw.js' or path == '/leaflet.draw.js':
                self._serve_static_file_cached(self.assets_path / 'leaflet.draw.js', 'application/javascript')
            elif path == '/leaflet-draw.css' or path == '/leaflet.draw.css':
                self._serve_static_file_cached(self.assets_path / 'leaflet.draw.css', 'text/css')
            elif path.startswith('/images/'):
                image_name = path[8:]
                self._serve_static_file_cached(self.assets_path / 'images' / image_name, 'image/png')
            elif path.startswith('/tiles/'):
                parts = path.split('/')
                if len(parts) >= 5:
                    z = int(parts[2])
                    x = int(parts[3])
                    y = int(parts[4].replace('.png', ''))
                    self._serve_tile_cached(z, x, y)
                else:
                    self.send_response(404)
                    self.end_headers()
            elif path == '/qwebchannel.js':
                # Serve Qt WebChannel JavaScript file
                self._serve_qwebchannel()
            elif path.startswith('/map/picker'):
                # Serve map picker HTML page
                self._serve_map_picker_html()
            elif path.startswith('/map/buildings'):
                # Serve buildings map HTML page
                self._serve_buildings_map_html()
            else:
                self.send_response(404)
                self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            # Normal browser behavior - connection closed prematurely (e.g., tab closed, navigation)
            # Don't log these as errors - they're expected in web applications
            pass
        except Exception as e:
            logger.error(f"Tile server error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                # Connection already closed, can't send error response
                pass

    def _serve_qwebchannel(self):
        """Serve Qt WebChannel JavaScript as empty placeholder."""
        # QWebChannel is loaded from qrc:///qtwebchannel/qwebchannel.js
        # This endpoint is for compatibility if code tries to load from server
        js_code = b"// QWebChannel loaded from Qt resources\n"
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(js_code))
        self.end_headers()
        self.wfile.write(js_code)

    def _serve_map_picker_html(self):
        """Serve map picker HTML page from query parameters."""
        from urllib.parse import parse_qs, urlparse

        # Parse query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Get parameters with defaults
        lat = float(params.get('lat', ['36.2021'])[0])
        lon = float(params.get('lon', ['37.1343'])[0])
        mode = params.get('mode', ['point'])[0]

        # Generate HTML (will be implemented by UI component)
        # For now, serve a basic template
        html = self._get_basic_map_html(lat, lon, mode)

        html_bytes = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', len(html_bytes))
        self.end_headers()
        self.wfile.write(html_bytes)

    def _serve_buildings_map_html(self):
        """Serve buildings map HTML page."""
        from urllib.parse import parse_qs, urlparse

        # Parse query parameters
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Get GeoJSON data from query (if provided)
        geojson = params.get('geojson', ['{"type":"FeatureCollection","features":[]}'])[0]

        # Generate HTML
        html = self._get_buildings_map_html(geojson)

        html_bytes = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', len(html_bytes))
        self.end_headers()
        self.wfile.write(html_bytes)

    def _get_basic_map_html(self, lat, lon, mode):
        """Generate basic map HTML for picker."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="/leaflet.css" />
    <link rel="stylesheet" href="/leaflet.draw.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="/leaflet.js"></script>
    <script src="/leaflet.draw.js"></script>
    <script>
        var map = L.map('map').setView([{lat}, {lon}], 13);
        L.tileLayer('/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 16,
            minZoom: 10,
            attribution: 'UN-Habitat'
        }}).addTo(map);
    </script>
</body>
</html>"""

    def _get_buildings_map_html(self, geojson):
        """Generate buildings map HTML."""
        return f"""<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([36.2021, 37.1343], 13);
        L.tileLayer('/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 16,
            minZoom: 10,
            attribution: 'UN-Habitat Syria'
        }}).addTo(map);

        var buildingsData = {geojson};
        L.geoJSON(buildingsData).addTo(map);
    </script>
</body>
</html>"""

    def _serve_static_file_cached(self, filepath, content_type):
        """Serve a static file with caching."""
        try:
            cache_key = str(filepath)

            if cache_key in TileServer._static_cache:
                data = TileServer._static_cache[cache_key]
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
                return

            if filepath.exists():
                with open(filepath, 'rb') as f:
                    data = f.read()

                if len(data) < 500000:
                    TileServer._static_cache[cache_key] = data

                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Connection closed by client - ignore
            pass

    def _serve_tile_cached(self, z, x, y):
        """Serve a map tile with aggressive caching."""
        TileServer._perf_stats['total_requests'] += 1
        cache_key = f"{z}/{x}/{y}"

        if cache_key in TileServer._tile_cache:
            TileServer._perf_stats['cache_hits'] += 1
            tile_data = TileServer._tile_cache[cache_key]
            self._send_tile(tile_data)
            return

        TileServer._perf_stats['cache_misses'] += 1
        conn = self._get_db_connection()

        if conn:
            try:
                TileServer._perf_stats['db_queries'] += 1
                y_tms = (2 ** z) - 1 - y
                cursor = conn.execute(
                    "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (z, x, y_tms)
                )
                row = cursor.fetchone()

                if row:
                    tile_data = row[0]
                    TileServer._tile_cache[cache_key] = tile_data
                    self._send_tile(tile_data)
                else:
                    self._send_empty_tile()
            except Exception as e:
                logger.error(f"Database error: {e}")
                self._send_empty_tile()
        else:
            self._send_empty_tile()

    def _send_tile(self, tile_data):
        """Send tile data with proper headers."""
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
            self.send_header('Content-Length', len(tile_data))
            self.end_headers()
            self.wfile.write(tile_data)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Connection closed by client - ignore
            pass

    def _send_empty_tile(self):
        """Send an empty transparent tile."""
        empty_tile = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00\x5c\x72\xa8\x66\x00\x00\x00\x15IDATx\x9c\xed\xc1\x01\r\x00\x00\x00\xc2\xa0\xf7Om\x0e7\xa0\x00\x00\x00\x00\x00\x00\xbe\r!\x00\x00\x01\x9a`\xe1\xd5\x00\x00\x00\x00IEND\xaeB`\x82'
        self.send_response(200)
        self.send_header('Content-Type', 'image/png')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=31536000')
        self.send_header('Content-Length', len(empty_tile))
        self.end_headers()
        self.wfile.write(empty_tile)


class TileServerManager:
    """
    Singleton manager for the tile server.

    Provides a centralized way to start and access the tile server.
    All UI components should use this instead of managing the server directly.
    """

    _instance: Optional['TileServerManager'] = None
    _server: Optional[HTTPServer] = None
    _server_thread: Optional[threading.Thread] = None
    _port: Optional[int] = None
    _is_production: bool = False
    _production_url: Optional[str] = None

    def __new__(cls):
        """Ensure only one instance exists (Singleton)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the manager (only once)."""
        if not hasattr(self, '_initialized'):
            self._initialized = True

            # Use smart tile server URL with health check and fallback
            # get_active_tile_server_url() returns None for embedded tiles
            production_url = get_active_tile_server_url()
            if production_url:
                print(f"\n[DEBUG] Tile Server: DOCKER/EXTERNAL")
                print(f"[DEBUG] URL: {production_url}")
                print(f"[DEBUG] Health Check: PASSED\n")
                logger.info(f"✅ Using external tile server: {production_url}")
                self._is_production = True
                self._production_url = production_url
            else:
                print(f"\n[DEBUG] Tile Server: EMBEDDED/LOCAL")
                print(f"[DEBUG] Starting local tile server on random port\n")
                logger.info("📦 Using embedded local tile server")
                self._is_production = False

    def get_tile_server_url(self) -> str:
        """
        Get the tile server URL.

        Returns either the production URL (if configured) or the local server URL.
        Starts the local server if not already running.

        Returns:
            str: Full URL to the tile server (e.g., "http://127.0.0.1:54321")
        """
        if self._is_production:
            return self._production_url

        # Start local server if not running
        if self._port is None:
            self._start_local_server()

        return f"http://127.0.0.1:{self._port}"

    def _start_local_server(self):
        """Start the local tile server."""
        if self._server is not None:
            return  # Already running

        # Find free port
        self._port = find_free_port()

        # Set paths
        base_path = Path(__file__).parent.parent
        TileServer.mbtiles_path = base_path / "data" / "aleppo_tiles.mbtiles"
        TileServer.assets_path = base_path / "assets" / "leaflet"

        # Create server - listen on all interfaces (0.0.0.0) to allow network access
        # ✅ NETWORK ACCESS: 0.0.0.0 allows other team members to connect
        # 🔒 SECURITY: Only use on trusted networks (not public Wi-Fi!)
        self._server = HTTPServer(('0.0.0.0', self._port), TileServer)

        # Start server in background thread
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True
        )
        self._server_thread.start()

        logger.info(f"Local tile server started on port {self._port}")

    def stop(self):
        """Stop the local tile server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            self._server_thread = None
            self._port = None
            logger.info("Local tile server stopped")

    @classmethod
    def get_instance(cls) -> 'TileServerManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Global helper function for easy access
def get_tile_server_url() -> str:
    """
    Get the tile server URL.

    This is the main function that all UI components should use.

    Returns:
        str: Full URL to the tile server
    """
    manager = TileServerManager.get_instance()
    return manager.get_tile_server_url()
