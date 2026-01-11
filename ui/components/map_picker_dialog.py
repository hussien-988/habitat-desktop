# -*- coding: utf-8 -*-
"""
Map Picker Dialog - UC-000 S04 Implementation.

Allows users to pick a location or draw a polygon on an interactive map.
Uses Leaflet.js via QWebEngineView for the map interface.
Works OFFLINE using local tiles and libraries.
"""

import json
import sqlite3
import base64
from typing import Dict, Optional
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socket

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QFrame, QLineEdit, QGroupBox, QRadioButton,
    QButtonGroup, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# Paths to local assets
ASSETS_PATH = Path(__file__).parent.parent.parent / "assets" / "leaflet"
MBTILES_PATH = Path(__file__).parent.parent.parent / "data" / "aleppo_tiles.mbtiles"


class TileServer(BaseHTTPRequestHandler):
    """HTTP server to serve tiles from MBTiles file and static assets."""

    mbtiles_path = None
    assets_path = None

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    def do_GET(self):
        """Handle GET requests for tiles and static files."""
        try:
            path = self.path.split('?')[0]  # Remove query string

            # Serve Leaflet JS
            if path == '/leaflet.js':
                self._serve_static_file(self.assets_path / 'leaflet.js', 'application/javascript')
            # Serve Leaflet CSS
            elif path == '/leaflet.css':
                self._serve_static_file(self.assets_path / 'leaflet.css', 'text/css')
            # Serve Leaflet Draw JS
            elif path == '/leaflet.draw.js':
                self._serve_static_file(self.assets_path / 'leaflet.draw.js', 'application/javascript')
            # Serve Leaflet Draw CSS
            elif path == '/leaflet.draw.css':
                self._serve_static_file(self.assets_path / 'leaflet.draw.css', 'text/css')
            # Serve Leaflet images
            elif path.startswith('/images/'):
                image_name = path[8:]  # Remove '/images/'
                self._serve_static_file(self.assets_path / 'images' / image_name, 'image/png')
            # Serve tiles: /tiles/{z}/{x}/{y}.png
            elif path.startswith('/tiles/'):
                parts = path.split('/')
                if len(parts) >= 5:
                    z = int(parts[2])
                    x = int(parts[3])
                    y = int(parts[4].replace('.png', ''))
                    self._serve_tile(z, x, y)
                else:
                    self.send_response(404)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            logger.error(f"Tile server error: {e}")
            self.send_response(500)
            self.end_headers()

    def _serve_static_file(self, filepath, content_type):
        """Serve a static file."""
        if filepath.exists():
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=86400')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            logger.warning(f"File not found: {filepath}")
            self.send_response(404)
            self.end_headers()

    def _serve_tile(self, z, x, y):
        """Serve a map tile."""
        tile_data = self._get_tile(z, x, y)

        if tile_data:
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=86400')
            self.end_headers()
            self.wfile.write(tile_data)
        else:
            # Return transparent tile for missing tiles
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # 1x1 transparent PNG
            self.wfile.write(base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
            ))

    def _get_tile(self, z, x, y):
        """Get tile from MBTiles database."""
        if not self.mbtiles_path or not self.mbtiles_path.exists():
            return None

        try:
            conn = sqlite3.connect(str(self.mbtiles_path))
            cursor = conn.cursor()

            # MBTiles uses TMS scheme (y is flipped)
            tms_y = (2 ** z) - 1 - y

            cursor.execute(
                'SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?',
                (z, x, tms_y)
            )
            row = cursor.fetchone()
            conn.close()

            return row[0] if row else None
        except Exception as e:
            logger.error(f"Error reading tile: {e}")
            return None


def find_free_port():
    """Find a free port for the tile server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class MapBridge(QWidget):
    """Bridge object for communication between Python and JavaScript."""

    location_selected = pyqtSignal(float, float)  # lat, lon
    polygon_selected = pyqtSignal(str)  # WKT string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._latitude = None
        self._longitude = None
        self._polygon_wkt = None

    def set_location(self, lat: float, lon: float):
        """Called from JavaScript when a point is selected."""
        self._latitude = lat
        self._longitude = lon
        self._polygon_wkt = None
        self.location_selected.emit(lat, lon)
        logger.debug(f"Location selected: {lat}, {lon}")

    def set_polygon(self, wkt: str):
        """Called from JavaScript when a polygon is drawn."""
        self._polygon_wkt = wkt
        # Extract centroid for lat/lon
        try:
            # Simple centroid extraction from WKT
            coords_str = wkt.split("((")[1].split("))")[0]
            points = coords_str.split(",")
            lats = []
            lons = []
            for p in points:
                parts = p.strip().split()
                lons.append(float(parts[0]))
                lats.append(float(parts[1]))
            self._latitude = sum(lats) / len(lats)
            self._longitude = sum(lons) / len(lons)
        except Exception as e:
            logger.warning(f"Could not extract centroid: {e}")

        self.polygon_selected.emit(wkt)
        logger.debug(f"Polygon selected: {wkt[:100]}...")


class MapPickerDialog(QDialog):
    """
    Dialog for picking a location or drawing a polygon on a map.

    Implements UC-000 S04: Enter geo location/Geometry
    Works completely OFFLINE using local MBTiles and Leaflet.
    """

    _tile_server = None
    _tile_server_port = None
    _tile_server_thread = None

    def __init__(
        self,
        initial_lat: float = 36.2,
        initial_lon: float = 37.15,
        allow_polygon: bool = True,
        parent=None
    ):
        super().__init__(parent)
        self.initial_lat = initial_lat
        self.initial_lon = initial_lon
        self.allow_polygon = allow_polygon

        self._result = None

        self.setWindowTitle("اختيار الموقع على الخريطة")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        # Start local tile server
        self._start_tile_server()

        self._setup_ui()
        self._load_map()

    def _start_tile_server(self):
        """Start local HTTP server for tiles and Leaflet files."""
        if MapPickerDialog._tile_server is None:
            # Find free port
            MapPickerDialog._tile_server_port = find_free_port()

            # Set paths
            TileServer.mbtiles_path = MBTILES_PATH
            TileServer.assets_path = ASSETS_PATH

            # Create server
            MapPickerDialog._tile_server = HTTPServer(
                ('127.0.0.1', MapPickerDialog._tile_server_port),
                TileServer
            )

            # Start server in background thread
            MapPickerDialog._tile_server_thread = threading.Thread(
                target=MapPickerDialog._tile_server.serve_forever,
                daemon=True
            )
            MapPickerDialog._tile_server_thread.start()

            logger.info(f"Tile server started on port {MapPickerDialog._tile_server_port}")

        self.tile_server_port = MapPickerDialog._tile_server_port

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Instructions
        instructions = QLabel(
            "انقر على الخريطة لتحديد موقع المبنى، أو استخدم أدوات الرسم لتحديد حدود المبنى"
        )
        instructions.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: 10pt;
            padding: 8px;
            background-color: #F8FAFC;
            border-radius: 4px;
        """)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Mode selection
        if self.allow_polygon:
            mode_group = QGroupBox("نوع التحديد")
            mode_layout = QHBoxLayout(mode_group)

            self.point_radio = QRadioButton("نقطة (Point)")
            self.point_radio.setChecked(True)
            self.polygon_radio = QRadioButton("مضلع (Polygon)")

            self.mode_group = QButtonGroup()
            self.mode_group.addButton(self.point_radio, 0)
            self.mode_group.addButton(self.polygon_radio, 1)
            self.mode_group.buttonClicked.connect(self._on_mode_changed)

            mode_layout.addWidget(self.point_radio)
            mode_layout.addWidget(self.polygon_radio)
            mode_layout.addStretch()

            layout.addWidget(mode_group)

        # Map container
        map_container = QFrame()
        map_container.setStyleSheet("""
            QFrame {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background-color: #F8FAFC;
            }
        """)
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(2, 2, 2, 2)

        # Web view for map
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)
        map_layout.addWidget(self.web_view)

        # Setup web channel for JS-Python communication
        self.bridge = MapBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.bridge.location_selected.connect(self._on_location_selected)
        self.bridge.polygon_selected.connect(self._on_polygon_selected)

        layout.addWidget(map_container)

        # Coordinates display
        coords_layout = QHBoxLayout()

        lat_label = QLabel("خط العرض:")
        self.lat_input = QLineEdit()
        self.lat_input.setReadOnly(True)
        self.lat_input.setPlaceholderText("--")
        self.lat_input.setMaximumWidth(150)

        lon_label = QLabel("خط الطول:")
        self.lon_input = QLineEdit()
        self.lon_input.setReadOnly(True)
        self.lon_input.setPlaceholderText("--")
        self.lon_input.setMaximumWidth(150)

        self.geometry_label = QLabel("")
        self.geometry_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

        coords_layout.addWidget(lat_label)
        coords_layout.addWidget(self.lat_input)
        coords_layout.addSpacing(16)
        coords_layout.addWidget(lon_label)
        coords_layout.addWidget(self.lon_input)
        coords_layout.addSpacing(16)
        coords_layout.addWidget(self.geometry_label)
        coords_layout.addStretch()

        layout.addLayout(coords_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # Clear button
        clear_btn = QPushButton("مسح")
        clear_btn.clicked.connect(self._clear_selection)
        btn_layout.addWidget(clear_btn)

        # Cancel button
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        # Confirm button
        confirm_btn = QPushButton("تأكيد الموقع")
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #16A34A;
            }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def _load_map(self):
        """Load the Leaflet map."""
        html = self._generate_map_html()
        self.web_view.setHtml(html)

    def _generate_map_html(self) -> str:
        """Generate HTML for the Leaflet map (OFFLINE VERSION)."""
        tile_server_url = f"http://127.0.0.1:{self.tile_server_port}"

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <link rel="stylesheet" href="{tile_server_url}/leaflet.draw.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .loading-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}
        .loading-content {{
            text-align: center;
        }}
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #0072BC;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div id="loading" class="loading-overlay">
        <div class="loading-content">
            <div class="spinner"></div>
            <div style="color: #0072BC; font-size: 14px; font-weight: 600;">جارٍ تحميل الخريطة...</div>
            <div style="color: #5D6D7E; font-size: 12px; margin-top: 8px;">يعمل بدون اتصال بالإنترنت</div>
        </div>
    </div>
    <div id="map"></div>

    <script src="{tile_server_url}/leaflet.js"></script>
    <script src="{tile_server_url}/leaflet.draw.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>
        // Hide loading when map is ready
        function hideLoading() {{
            var loading = document.getElementById('loading');
            if (loading) {{
                loading.style.display = 'none';
            }}
        }}

        var map = L.map('map').setView([{self.initial_lat}, {self.initial_lon}], 15);

        // Use LOCAL tiles from MBTiles
        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            attribution: 'Map data &copy; OpenStreetMap | UN-Habitat Syria',
            maxZoom: 18,
            minZoom: 10
        }}).addTo(map);

        // Hide loading after map loads
        map.whenReady(function() {{
            setTimeout(hideLoading, 500);
        }});

        var marker = null;
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        var drawControl = new L.Control.Draw({{
            draw: {{
                polygon: {'true' if self.allow_polygon else 'false'},
                polyline: false,
                circle: false,
                circlemarker: false,
                rectangle: false,
                marker: true
            }},
            edit: {{
                featureGroup: drawnItems,
                remove: true
            }}
        }});
        map.addControl(drawControl);

        // Initial marker
        marker = L.marker([{self.initial_lat}, {self.initial_lon}], {{draggable: true}}).addTo(map);
        marker.on('dragend', function(e) {{
            var pos = e.target.getLatLng();
            sendLocation(pos.lat, pos.lng);
        }});

        // Connect to Python
        var bridge = null;
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            bridge = channel.objects.bridge;
            // Send initial position
            sendLocation({self.initial_lat}, {self.initial_lon});
        }});

        function sendLocation(lat, lng) {{
            if (bridge) {{
                bridge.set_location(lat, lng);
            }}
        }}

        function sendPolygon(wkt) {{
            if (bridge) {{
                bridge.set_polygon(wkt);
            }}
        }}

        // Click to place marker
        map.on('click', function(e) {{
            if (marker) {{
                map.removeLayer(marker);
            }}
            marker = L.marker(e.latlng, {{draggable: true}}).addTo(map);
            marker.on('dragend', function(ev) {{
                var pos = ev.target.getLatLng();
                sendLocation(pos.lat, pos.lng);
            }});
            sendLocation(e.latlng.lat, e.latlng.lng);
        }});

        // Handle drawn items
        map.on(L.Draw.Event.CREATED, function(e) {{
            var layer = e.layer;
            var type = e.layerType;

            drawnItems.clearLayers();
            drawnItems.addLayer(layer);

            if (type === 'polygon') {{
                var latlngs = layer.getLatLngs()[0];
                var wkt = 'POLYGON((';
                for (var i = 0; i < latlngs.length; i++) {{
                    wkt += latlngs[i].lng + ' ' + latlngs[i].lat + ', ';
                }}
                // Close the polygon
                wkt += latlngs[0].lng + ' ' + latlngs[0].lat + '))';
                sendPolygon(wkt);
            }} else if (type === 'marker') {{
                var pos = layer.getLatLng();
                sendLocation(pos.lat, pos.lng);
            }}
        }});

        // Handle edit
        map.on(L.Draw.Event.EDITED, function(e) {{
            var layers = e.layers;
            layers.eachLayer(function(layer) {{
                if (layer instanceof L.Polygon) {{
                    var latlngs = layer.getLatLngs()[0];
                    var wkt = 'POLYGON((';
                    for (var i = 0; i < latlngs.length; i++) {{
                        wkt += latlngs[i].lng + ' ' + latlngs[i].lat + ', ';
                    }}
                    wkt += latlngs[0].lng + ' ' + latlngs[0].lat + '))';
                    sendPolygon(wkt);
                }} else if (layer instanceof L.Marker) {{
                    var pos = layer.getLatLng();
                    sendLocation(pos.lat, pos.lng);
                }}
            }});
        }});

        // Clear function
        window.clearSelection = function() {{
            drawnItems.clearLayers();
            if (marker) {{
                map.removeLayer(marker);
                marker = null;
            }}
        }};

        // Set mode function
        window.setMode = function(mode) {{
            // mode: 0 = point, 1 = polygon
            if (mode === 0) {{
                drawControl.setDrawingOptions({{
                    polygon: false,
                    marker: true
                }});
            }} else {{
                drawControl.setDrawingOptions({{
                    polygon: true,
                    marker: false
                }});
            }}
        }};
    </script>
</body>
</html>
"""

    def _on_location_selected(self, lat: float, lon: float):
        """Handle point selection."""
        self.lat_input.setText(f"{lat:.6f}")
        self.lon_input.setText(f"{lon:.6f}")
        self.geometry_label.setText("✓ تم تحديد النقطة")
        self._result = {
            "latitude": lat,
            "longitude": lon,
            "polygon_wkt": None
        }

    def _on_polygon_selected(self, wkt: str):
        """Handle polygon selection."""
        if self.bridge._latitude and self.bridge._longitude:
            self.lat_input.setText(f"{self.bridge._latitude:.6f}")
            self.lon_input.setText(f"{self.bridge._longitude:.6f}")
        self.geometry_label.setText("✓ تم رسم المضلع")
        self._result = {
            "latitude": self.bridge._latitude,
            "longitude": self.bridge._longitude,
            "polygon_wkt": wkt
        }

    def _on_mode_changed(self, button):
        """Handle mode change between point and polygon."""
        mode = self.mode_group.id(button)
        self.web_view.page().runJavaScript(f"setMode({mode});")

    def _clear_selection(self):
        """Clear the current selection."""
        self.web_view.page().runJavaScript("clearSelection();")
        self.lat_input.clear()
        self.lon_input.clear()
        self.geometry_label.setText("")
        self._result = None

    def _on_confirm(self):
        """Confirm the selection."""
        if not self._result:
            QMessageBox.warning(
                self,
                "تنبيه",
                "يرجى تحديد موقع على الخريطة أولاً"
            )
            return

        self.accept()

    def get_result(self) -> Optional[Dict]:
        """Get the selected location/polygon."""
        return self._result
