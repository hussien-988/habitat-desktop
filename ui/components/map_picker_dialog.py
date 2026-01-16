# -*- coding: utf-8 -*-
"""
Map Picker Dialog - UC-000 S04 Implementation.

Allows users to pick a location or draw a polygon on an interactive map.
Uses Leaflet.js via QWebEngineView for the map interface.
Works OFFLINE using local tiles and libraries.
"""

from typing import Dict, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QGroupBox, QRadioButton,
    QButtonGroup, QMessageBox
)
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebChannel import QWebChannel

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


# NOTE: TileServer has been moved to services/tile_server_manager.py
# This file now uses the centralized tile server manager


class DebugWebPage(QWebEnginePage):
    """Custom QWebEnginePage that logs console messages."""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Log JavaScript console messages."""
        logger.info(f"JS [{level}]: {message} (line {lineNumber})")


class TileRequestInterceptor(QWebEngineUrlRequestInterceptor):
    """
    Interceptor to add required headers for tile loading.

    Fixes blank/gray map issue by adding Accept-Language header.
    Reference: https://help.openstreetmap.org/questions/79955/openstreetmap-tiles-not-loading-pyqt5/
    """

    def interceptRequest(self, info):
        """Add required headers to tile requests."""
        info.setHttpHeader(b"Accept-Language", b"en-US,en;q=0.9,ar;q=0.8")
        info.setHttpHeader(b"User-Agent", b"UN-Habitat TRRCMS/1.0")


class MapBridge(QObject):
    """Bridge object for communication between Python and JavaScript."""

    location_selected = pyqtSignal(float, float)  # lat, lon
    polygon_selected = pyqtSignal(str)  # WKT string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._latitude = None
        self._longitude = None
        self._polygon_wkt = None

    @pyqtSlot(float, float)
    def set_location(self, lat: float, lon: float):
        """Called from JavaScript when a point is selected."""
        self._latitude = lat
        self._longitude = lon
        self._polygon_wkt = None
        self.location_selected.emit(lat, lon)
        logger.debug(f"Location selected: {lat}, {lon}")

    @pyqtSlot(str)
    def set_polygon(self, wkt: str):
        """Called from JavaScript when a polygon is drawn."""
        logger.info(f"✅ Polygon received from JavaScript: {wkt[:100]}...")
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
            logger.info(f"✅ Centroid calculated: lat={self._latitude}, lon={self._longitude}")
        except Exception as e:
            logger.error(f"❌ Could not extract centroid: {e}")

        self.polygon_selected.emit(wkt)
        logger.info(f"✅ Polygon signal emitted")


class MapPickerDialog(QDialog):
    """
    Dialog for picking a location or drawing a polygon on a map.

    Implements UC-000 S04: Enter geo location/Geometry
    Works completely OFFLINE using local MBTiles and Leaflet.

    Uses Singleton Pattern for performance optimization.
    """

    _shared_instance = None  # Singleton instance

    def __init__(
        self,
        initial_lat: float = 36.2,
        initial_lon: float = 37.15,
        allow_polygon: bool = True,
        read_only: bool = False,
        highlight_location: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.initial_lat = initial_lat
        self.initial_lon = initial_lon
        self.allow_polygon = allow_polygon
        self.read_only = read_only
        self.highlight_location = highlight_location

        # Initialize result with initial coordinates so Confirm works immediately
        self._result = {
            "latitude": initial_lat,
            "longitude": initial_lon,
            "polygon_wkt": None
        }

        self.setWindowTitle("اختيار الموقع على الخريطة")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self._setup_ui()
        self._load_map()

    @classmethod
    def get_instance(cls, initial_lat: float = 36.2, initial_lon: float = 37.15, allow_polygon: bool = True, read_only: bool = False, highlight_location: bool = False, parent=None):
        """
        Get or create singleton instance.
        Reuses existing dialog for performance, but recreates if widgets were deleted.
        """
        # Check if instance exists and widgets are still valid
        needs_recreation = False

        if cls._shared_instance is None:
            needs_recreation = True
        else:
            # Check if Qt widgets were deleted
            try:
                # Try to access a widget to check if it's still valid
                if hasattr(cls._shared_instance, 'lat_input'):
                    _ = cls._shared_instance.lat_input.text()  # Raises RuntimeError if deleted
                else:
                    needs_recreation = True
            except RuntimeError:
                logger.info("Previous dialog widgets were deleted by Qt, recreating...")
                needs_recreation = True

        if needs_recreation:
            logger.info("Creating new MapPickerDialog instance")
            cls._shared_instance = cls(initial_lat, initial_lon, allow_polygon, read_only, highlight_location, parent)
        else:
            logger.info("Reusing existing MapPickerDialog instance (Singleton)")
            # Update parameters and reset map
            cls._shared_instance.initial_lat = initial_lat
            cls._shared_instance.initial_lon = initial_lon
            cls._shared_instance.allow_polygon = allow_polygon
            cls._shared_instance.read_only = read_only
            cls._shared_instance.highlight_location = highlight_location
            # Initialize result with initial coordinates so Confirm works immediately
            cls._shared_instance._result = {
                "latitude": initial_lat,
                "longitude": initial_lon,
                "polygon_wkt": None
            }
            try:
                cls._shared_instance._reset_map()
            except RuntimeError:
                # Failed to reset, recreate the dialog
                logger.warning("Failed to reset map (widgets deleted), recreating dialog...")
                cls._shared_instance = cls(initial_lat, initial_lon, allow_polygon, read_only, highlight_location, parent)

        return cls._shared_instance

    def _reset_map(self):
        """Reset map to new location without recreating QWebEngineView."""
        logger.info(f"Resetting map to {self.initial_lat}, {self.initial_lon}")

        # Check if widgets still exist (Qt may have deleted them)
        try:
            # Reset bridge if it exists
            if hasattr(self, 'bridge'):
                self.bridge._latitude = None
                self.bridge._longitude = None
                self.bridge._polygon_wkt = None

            # Update coordinate displays if they exist and are valid
            if hasattr(self, 'lat_input') and self.lat_input is not None:
                self.lat_input.setText(f"{self.initial_lat:.6f}")
            if hasattr(self, 'lon_input') and self.lon_input is not None:
                self.lon_input.setText(f"{self.initial_lon:.6f}")

            # Clear geometry label if exists
            if hasattr(self, 'geometry_label') and self.geometry_label is not None:
                self.geometry_label.setText("")

            # Reload map HTML with new coordinates
            if hasattr(self, 'web_view') and self.web_view is not None:
                self._load_map()
        except RuntimeError as e:
            # Widget was deleted by Qt - recreate the dialog
            logger.warning(f"Widgets were deleted, need to recreate dialog: {e}")
            # Force recreation by clearing the instance
            MapPickerDialog._shared_instance = None
            raise

    def _get_tile_server_url(self):
        """Get tile server URL from centralized manager."""
        from services.tile_server_manager import get_tile_server_url
        return get_tile_server_url()

    def _get_buildings_json(self):
        """Get all buildings as JSON for map markers."""
        import json
        try:
            from repositories.database import Database
            from repositories.building_repository import BuildingRepository

            db = Database()
            building_repo = BuildingRepository(db)
            buildings = building_repo.get_all(limit=1000)  # Get up to 1000 buildings

            buildings_list = []
            for b in buildings:
                if b.latitude and b.longitude:
                    # Map status codes to ensure correct colors
                    status_code = b.building_status or "unknown"
                    buildings_list.append({
                        "id": b.building_id,
                        "lat": b.latitude,
                        "lon": b.longitude,
                        "status": status_code,  # Send the code itself
                        "type": b.building_type or "غير محدد"
                    })

            return json.dumps(buildings_list)
        except Exception as e:
            logger.error(f"Failed to load buildings for map: {e}")
            return "[]"

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Instructions
        if self.read_only:
            instructions = QLabel("عرض موقع المبنى على الخريطة")
        else:
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

        # Mode selection (hidden in read-only mode)
        if self.allow_polygon and not self.read_only:
            mode_group = QGroupBox("نوع التحديد")
            mode_layout = QVBoxLayout(mode_group)

            # Radio buttons
            radio_layout = QHBoxLayout()
            self.point_radio = QRadioButton("نقطة (Point)")
            self.point_radio.setChecked(True)
            self.polygon_radio = QRadioButton("مضلع (Polygon)")

            self.mode_group = QButtonGroup()
            self.mode_group.addButton(self.point_radio, 0)
            self.mode_group.addButton(self.polygon_radio, 1)
            self.mode_group.buttonClicked.connect(self._on_mode_changed)

            radio_layout.addWidget(self.point_radio)
            radio_layout.addWidget(self.polygon_radio)
            radio_layout.addStretch()
            mode_layout.addLayout(radio_layout)

            # Instruction label (below radio buttons)
            self.mode_instruction = QLabel("👉 اضغط على الأيقونة في الصندوق الأبيض يسار الخريطة")
            self.mode_instruction.setStyleSheet("""
                color: #e67e22;
                font-size: 12px;
                font-weight: 600;
                padding: 8px;
                background-color: rgba(230, 126, 34, 0.1);
                border-radius: 4px;
                border-left: 3px solid #e67e22;
            """)
            self.mode_instruction.setWordWrap(True)
            mode_layout.addWidget(self.mode_instruction)

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

        # Web view for map with custom page for debugging
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)

        # Create profile with cache disabled to force fresh tile requests
        profile = QWebEngineProfile(self.web_view)
        profile.setHttpCacheType(QWebEngineProfile.NoCache)  # CRITICAL: Disable HTTP cache

        # Set custom page with no-cache profile
        debug_page = DebugWebPage(profile, self.web_view)
        self.web_view.setPage(debug_page)

        # Simple settings - just enable hardware acceleration
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

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
        """Load the Leaflet map - WITH base URL like test_map_simple.py."""
        html = self._generate_map_html()
        tile_server_url = self._get_tile_server_url()
        # CRITICAL: Set base URL so QWebEngineView can resolve requests
        base_url = QUrl(tile_server_url)
        self.web_view.setHtml(html, base_url)

    def _generate_map_html(self) -> str:
        """Generate HTML for the Leaflet map - SIMPLE offline version."""
        tile_server_url = self._get_tile_server_url()

        # Load all buildings from database
        buildings_json = self._get_buildings_json()

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <link rel="stylesheet" href="{tile_server_url}/leaflet.draw.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}

        /* OPTIMIZATION 1: Skeleton UI with shimmer animation */
        .loading-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                90deg,
                #e8f1f9 0%,
                #f0f7fc 20%,
                #e8f1f9 40%,
                #e8f1f9 100%
            );
            background-size: 200% 100%;
            animation: shimmer 2s infinite linear;
            z-index: 9998;
        }}

        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}

        .loading-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            z-index: 9999;
        }}

        .map-skeleton {{
            width: 60px;
            height: 60px;
            margin: 0 auto 20px;
            position: relative;
        }}

        .skeleton-marker {{
            width: 30px;
            height: 40px;
            background: #0072BC;
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            margin: 10px auto;
            opacity: 0.3;
            animation: pulse 1.5s ease-in-out infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 0.3; transform: rotate(-45deg) scale(1); }}
            50% {{ opacity: 0.6; transform: rotate(-45deg) scale(1.1); }}
        }}

        .loading-text {{
            color: #0072BC;
            font-size: 15px;
            font-weight: 600;
            font-family: 'Segoe UI', Tahoma, sans-serif;
            margin-bottom: 8px;
        }}

        .loading-subtext {{
            color: #5D6D7E;
            font-size: 12px;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}

        /* Low-quality tiles placeholder */
        .leaflet-tile.lqip {{
            filter: blur(8px);
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <div id="loading" class="loading-overlay">
        <div class="loading-content">
            <div class="map-skeleton">
                <div class="skeleton-marker"></div>
            </div>
            <div class="loading-text">جارٍ تحميل الخريطة...</div>
            <div class="loading-subtext">يعمل بدون اتصال بالإنترنت</div>
        </div>
    </div>
    <div id="map"></div>

    <script src="{tile_server_url}/leaflet.js"></script>
    <script src="{tile_server_url}/leaflet.draw.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>
        console.log('=== MAP INITIALIZATION START ===');
        console.log('Leaflet version:', L.version);
        console.log('Tile server URL:', '{tile_server_url}');

        // Simple map initialization
        var map = L.map('map', {{
            preferCanvas: true,
            zoomAnimation: true,
            fadeAnimation: false
        }}).setView([{self.initial_lat}, {self.initial_lon}], 17);

        console.log('Map created, center:', map.getCenter(), 'zoom:', map.getZoom());

        // Simple tile layer - like office_survey_wizard
        var tileUrl = '{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png';
        console.log('Tile URL template:', tileUrl);

        var tileLayer = L.tileLayer(tileUrl, {{
            maxZoom: 16,
            minZoom: 10,
            attribution: 'UN-Habitat Syria'
        }});

        tileLayer.on('tileloadstart', function(e) {{
            console.log('TILE LOAD START - z:', e.coords.z, 'x:', e.coords.x, 'y:', e.coords.y);
            if (e.tile && e.tile.src) {{
                console.log('  Tile SRC:', e.tile.src);
            }}
        }});

        tileLayer.on('tileload', function(e) {{
            console.log('TILE LOADED OK - z:', e.coords.z, 'x:', e.coords.x, 'y:', e.coords.y);
            if (e.tile && e.tile.src) {{
                console.log('  Tile SRC:', e.tile.src);
            }}
        }});

        tileLayer.on('tileerror', function(e) {{
            console.error('TILE ERROR - z:', e.coords.z, 'x:', e.coords.x, 'y:', e.coords.y);
            if (e.tile && e.tile.src) {{
                console.error('  Tile SRC:', e.tile.src);
            }}
        }});

        tileLayer.addTo(map);
        console.log('Tile layer added to map');

        // Hide loading after short delay
        setTimeout(function() {{
            document.getElementById('loading').style.display = 'none';
        }}, 500);

        var marker = null;
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        var readOnly = {'true' if self.read_only else 'false'};
        console.log('Read-only mode:', readOnly);

        var drawControl = null;
        var currentMode = 0; // 0 = point, 1 = polygon

        // Add drawing controls only if NOT read-only
        if (!readOnly) {{
            drawControl = new L.Control.Draw({{
                draw: {{
                    polygon: false,
                    polyline: false,
                    circle: false,
                    circlemarker: false,
                    rectangle: false,
                    marker: true  // Start with marker (point) enabled
                }},
                edit: {{
                    featureGroup: drawnItems,
                    remove: true
                }}
            }});
            map.addControl(drawControl);
        }}

        // Load all buildings as markers
        var buildings = {buildings_json};
        var highlightLocation = {'true' if self.highlight_location else 'false'};
        console.log('Loading', buildings.length, 'buildings on map');

        // Color by damage status
        function getMarkerColor(status) {{
            // Check for destroyed/demolished
            if (status === 'destroyed' || status === 'demolished' || status === 'rubble') return '#e74c3c';
            // Check for damaged
            if (status === 'damaged' || status === 'partially_damaged' || status === 'severely_damaged' ||
                status === 'minor_damage' || status === 'major_damage') return '#f39c12';
            // Check for intact
            if (status === 'intact' || status === 'standing') return '#27ae60';
            // Default gray for unknown
            return '#95a5a6';
        }}

        // Custom icon (medium size for regular buildings)
        function createIcon(color) {{
            return L.icon({{
                iconUrl: 'data:image/svg+xml;base64,' + btoa(
                    '<svg width="26" height="38" xmlns="http://www.w3.org/2000/svg">' +
                    '<path d="M13 0C5.8 0 0 5.8 0 13c0 9.75 13 25 13 25s13-15.25 13-25c0-7.2-5.8-13-13-13z" fill="' + color + '" stroke="white" stroke-width="2"/>' +
                    '<circle cx="13" cy="13" r="5.5" fill="white"/>' +
                    '</svg>'
                ),
                iconSize: [26, 38],
                iconAnchor: [13, 38],
                popupAnchor: [0, -38]
            }});
        }}

        // Custom big icon for highlighted (bigger and blue)
        function createBigIcon() {{
            return L.icon({{
                iconUrl: 'data:image/svg+xml;base64,' + btoa(
                    '<svg width="38" height="56" xmlns="http://www.w3.org/2000/svg">' +
                    '<path d="M19 0C8.5 0 0 8.5 0 19c0 14.25 19 37 19 37s19-22.75 19-37c0-10.5-8.5-19-19-19z" fill="#3498db" stroke="white" stroke-width="2.5"/>' +
                    '<circle cx="19" cy="19" r="8" fill="white"/>' +
                    '</svg>'
                ),
                iconSize: [38, 56],
                iconAnchor: [19, 56],
                popupAnchor: [0, -56]
            }});
        }}

        // Add all building markers
        buildings.forEach(function(building) {{
            var isHighlighted = highlightLocation &&
                                Math.abs(building.lat - {self.initial_lat}) < 0.00001 &&
                                Math.abs(building.lon - {self.initial_lon}) < 0.00001;

            if (!isHighlighted) {{
                var markerColor = getMarkerColor(building.status);
                var icon = createIcon(markerColor);

                var buildingMarker = L.marker([building.lat, building.lon], {{
                    icon: icon,
                    riseOnHover: true
                }}).addTo(map);

                buildingMarker.bindPopup(
                    '<b>رمز البناء: ' + building.id + '</b><br>' +
                    'الحالة: ' + building.status + '<br>' +
                    'النوع: ' + building.type
                );
            }}
        }});

        // Initial marker (highlighted if needed, draggable only if NOT read-only)
        var markerOptions = {{draggable: !readOnly, riseOnHover: true}};
        if (highlightLocation) {{
            // Highlighted marker (bigger, blue)
            var bigIcon = createBigIcon();
            markerOptions.icon = bigIcon;
            marker = L.marker([{self.initial_lat}, {self.initial_lon}], markerOptions).addTo(map);
            marker.bindPopup('<b>الموقع المحدد</b>').openPopup();
        }} else {{
            // Normal marker
            marker = L.marker([{self.initial_lat}, {self.initial_lon}], markerOptions).addTo(map);
        }}

        if (!readOnly) {{
            marker.on('dragend', function(e) {{
                var pos = e.target.getLatLng();
                sendLocation(pos.lat, pos.lng);
            }});
        }}

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

        // Click to place marker (only if NOT read-only)
        if (!readOnly) {{
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
        }}

        // Handle drawn items (only if NOT read-only)
        if (!readOnly) {{
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
                    console.log('Polygon WKT:', wkt);
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
        }}

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
            if (!drawControl) {{
                console.log('❌ No draw control available');
                return;
            }}

            // mode: 0 = point, 1 = polygon
            console.log('🔄 Switching to mode:', mode === 0 ? 'Point' : 'Polygon');
            currentMode = mode;

            // Remove old draw control
            try {{
                map.removeControl(drawControl);
            }} catch(e) {{
                console.log('Warning: Could not remove control:', e);
            }}

            // Create new draw control with updated options
            if (mode === 0) {{
                console.log('📍 Enabling Point marker');
                drawControl = new L.Control.Draw({{
                    draw: {{
                        polygon: false,
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
            }} else {{
                console.log('🔷 Enabling Polygon drawing');
                drawControl = new L.Control.Draw({{
                    draw: {{
                        polygon: true,
                        polyline: false,
                        circle: false,
                        circlemarker: false,
                        rectangle: false,
                        marker: false
                    }},
                    edit: {{
                        featureGroup: drawnItems,
                        remove: true
                    }}
                }});
            }}

            // Add new draw control
            try {{
                map.addControl(drawControl);
                console.log('✅ Draw control updated and ready');
            }} catch(e) {{
                console.log('❌ Error adding control:', e);
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
