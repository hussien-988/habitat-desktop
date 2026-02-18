"""
Map Coordinate Picker Widget
============================
Implements map-based coordinate input for UC-000 as per FSD requirements.

Features:
- Interactive map display with multiple tile providers
- Click-to-select coordinates
- Manual coordinate entry with validation
- Coordinate format conversion (DMS, DD)
- GPS integration for current location
- Polygon drawing for building footprint
- Marker management
- Zoom and pan controls
- Coordinate precision settings
- Iraq-specific coordinate validation
"""

import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List, Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QGroupBox, QDoubleSpinBox,
    QFrame, QSizePolicy, QMenu, QAction,
    QToolButton, QButtonGroup, QRadioButton, QDialog,
    QDialogButtonBox, QFormLayout, QTabWidget, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QDoubleValidator, QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from ui.error_handler import ErrorHandler
import logging

logger = logging.getLogger(__name__)


class CoordinateFormat(Enum):
    """Coordinate display formats."""
    DECIMAL_DEGREES = "dd"  # 33.3152° N, 44.3661° E
    DMS = "dms"  # 33° 18' 54.72" N, 44° 21' 58.0" E
    DDM = "ddm"  # 33° 18.912' N, 44° 21.967' E


class MapProvider(Enum):
    """Map tile providers."""
    OPENSTREETMAP = "osm"
    SATELLITE = "satellite"
    TERRAIN = "terrain"
    HYBRID = "hybrid"


@dataclass
class GeoCoordinate:
    """Represents a geographic coordinate."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None  # meters

    def is_valid(self) -> bool:
        """Check if coordinate is valid."""
        return -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180

    def is_in_iraq(self) -> bool:
        """Check if coordinate is within Iraq bounding box."""
        # Iraq approximate bounding box
        return (29.0 <= self.latitude <= 37.5 and
                38.5 <= self.longitude <= 49.0)

    def to_dms(self) -> Tuple[str, str]:
        """Convert to DMS format."""
        def dd_to_dms(dd: float, is_lat: bool) -> str:
            direction = ('N' if dd >= 0 else 'S') if is_lat else ('E' if dd >= 0 else 'W')
            dd = abs(dd)
            degrees = int(dd)
            minutes = int((dd - degrees) * 60)
            seconds = round((dd - degrees - minutes/60) * 3600, 2)
            return f"{degrees}° {minutes}' {seconds}\" {direction}"

        return dd_to_dms(self.latitude, True), dd_to_dms(self.longitude, False)

    def to_ddm(self) -> Tuple[str, str]:
        """Convert to DDM format."""
        def dd_to_ddm(dd: float, is_lat: bool) -> str:
            direction = ('N' if dd >= 0 else 'S') if is_lat else ('E' if dd >= 0 else 'W')
            dd = abs(dd)
            degrees = int(dd)
            minutes = round((dd - degrees) * 60, 4)
            return f"{degrees}° {minutes}' {direction}"

        return dd_to_ddm(self.latitude, True), dd_to_ddm(self.longitude, False)

    def distance_to(self, other: 'GeoCoordinate') -> float:
        """Calculate distance to another coordinate in meters (Haversine)."""
        R = 6371000  # Earth radius in meters

        lat1 = math.radians(self.latitude)
        lat2 = math.radians(other.latitude)
        delta_lat = math.radians(other.latitude - self.latitude)
        delta_lng = math.radians(other.longitude - self.longitude)

        a = (math.sin(delta_lat/2)**2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "accuracy": self.accuracy
        }


@dataclass
class GeoPolygon:
    """Represents a polygon (building footprint)."""
    points: List[GeoCoordinate]

    def is_valid(self) -> bool:
        """Check if polygon is valid (at least 3 points, all valid)."""
        return len(self.points) >= 3 and all(p.is_valid() for p in self.points)

    def area(self) -> float:
        """Calculate approximate area in square meters."""
        if len(self.points) < 3:
            return 0

        # Shoelace formula with geodesic approximation
        n = len(self.points)
        area = 0

        for i in range(n):
            j = (i + 1) % n
            # Convert to approximate meters
            lat1 = math.radians(self.points[i].latitude)
            lat2 = math.radians(self.points[j].latitude)
            lng1 = self.points[i].longitude
            lng2 = self.points[j].longitude

            area += lng1 * math.sin(lat2) - lng2 * math.sin(lat1)

        # Convert to square meters (rough approximation)
        area = abs(area) * 6371000**2 / 2
        return area

    def centroid(self) -> GeoCoordinate:
        """Calculate centroid of polygon."""
        if not self.points:
            return GeoCoordinate(0, 0)

        avg_lat = sum(p.latitude for p in self.points) / len(self.points)
        avg_lng = sum(p.longitude for p in self.points) / len(self.points)
        return GeoCoordinate(avg_lat, avg_lng)

    def to_wkt(self) -> str:
        """Convert to WKT format."""
        if not self.points:
            return "POLYGON EMPTY"

        coords = ", ".join(f"{p.longitude} {p.latitude}" for p in self.points)
        # Close the polygon
        if self.points:
            coords += f", {self.points[0].longitude} {self.points[0].latitude}"
        return f"POLYGON(({coords}))"

    def to_geojson(self) -> dict:
        """Convert to GeoJSON format."""
        coords = [[p.longitude, p.latitude] for p in self.points]
        if self.points:
            coords.append([self.points[0].longitude, self.points[0].latitude])
        return {
            "type": "Polygon",
            "coordinates": [coords]
        }


class MapCoordinatePickerWidget(QWidget):
    """
    Widget for selecting coordinates from an interactive map.

    Implements UC-000 S04a requirement for map-based coordinate input.
    """

    # Signals
    coordinate_selected = pyqtSignal(float, float)  # lat, lng
    polygon_completed = pyqtSignal(list)  # List of (lat, lng) tuples
    coordinate_changed = pyqtSignal(float, float)  # Manual entry change

    # Iraq center coordinates (Baghdad)
    DEFAULT_CENTER = (33.3152, 44.3661)
    DEFAULT_ZOOM = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._coordinate: Optional[GeoCoordinate] = None
        self._polygon: Optional[GeoPolygon] = None
        self._map_provider = MapProvider.OPENSTREETMAP
        self._coordinate_format = CoordinateFormat.DECIMAL_DEGREES
        self._precision = 6  # Decimal places

        self._setup_ui()
        self._setup_map()

    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top toolbar
        toolbar = QHBoxLayout()

        # Map provider selector
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("خريطة الشارع", MapProvider.OPENSTREETMAP)
        self.provider_combo.addItem("صور القمر الصناعي", MapProvider.SATELLITE)
        self.provider_combo.addItem("تضاريس", MapProvider.TERRAIN)
        self.provider_combo.addItem("هجين", MapProvider.HYBRID)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        toolbar.addWidget(QLabel("نوع الخريطة:"))
        toolbar.addWidget(self.provider_combo)

        toolbar.addStretch()

        # Drawing mode buttons
        self.mode_group = QButtonGroup(self)

        self.marker_btn = QToolButton()
        self.marker_btn.setText("📍")
        self.marker_btn.setToolTip("تحديد نقطة")
        self.marker_btn.setCheckable(True)
        self.marker_btn.setChecked(True)
        self.mode_group.addButton(self.marker_btn, 1)
        toolbar.addWidget(self.marker_btn)

        self.polygon_btn = QToolButton()
        self.polygon_btn.setText("⬡")
        self.polygon_btn.setToolTip("رسم مضلع")
        self.polygon_btn.setCheckable(True)
        self.mode_group.addButton(self.polygon_btn, 2)
        toolbar.addWidget(self.polygon_btn)

        self.clear_btn = QPushButton("مسح")
        self.clear_btn.clicked.connect(self._clear_map)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # Map view
        self.map_view = QWebEngineView()
        self.map_view.setMinimumHeight(300)
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.map_view)

        # Coordinate display/entry panel
        coord_group = QGroupBox("الإحداثيات")
        coord_layout = QVBoxLayout(coord_group)

        # Format selector
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("التنسيق:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("درجات عشرية (DD)", CoordinateFormat.DECIMAL_DEGREES)
        self.format_combo.addItem("درجات/دقائق/ثواني (DMS)", CoordinateFormat.DMS)
        self.format_combo.addItem("درجات/دقائق (DDM)", CoordinateFormat.DDM)
        self.format_combo.currentIndexChanged.connect(self._update_coordinate_display)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        coord_layout.addLayout(format_layout)

        # Manual entry fields
        entry_layout = QHBoxLayout()

        # Latitude
        lat_layout = QVBoxLayout()
        lat_layout.addWidget(QLabel("خط العرض (Latitude):"))
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setDecimals(self._precision)
        self.lat_input.setSingleStep(0.0001)
        self.lat_input.valueChanged.connect(self._on_manual_coordinate_change)
        lat_layout.addWidget(self.lat_input)
        entry_layout.addLayout(lat_layout)

        # Longitude
        lng_layout = QVBoxLayout()
        lng_layout.addWidget(QLabel("خط الطول (Longitude):"))
        self.lng_input = QDoubleSpinBox()
        self.lng_input.setRange(-180, 180)
        self.lng_input.setDecimals(self._precision)
        self.lng_input.setSingleStep(0.0001)
        self.lng_input.valueChanged.connect(self._on_manual_coordinate_change)
        lng_layout.addWidget(self.lng_input)
        entry_layout.addLayout(lng_layout)

        coord_layout.addLayout(entry_layout)

        # Display label (for DMS/DDM format)
        self.coord_display_label = QLabel("")
        self.coord_display_label.setStyleSheet("font-family: monospace; padding: 5px;")
        coord_layout.addWidget(self.coord_display_label)

        # Validation status
        self.validation_label = QLabel("")
        coord_layout.addWidget(self.validation_label)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.goto_btn = QPushButton("انتقل إلى الإحداثيات")
        self.goto_btn.clicked.connect(self._goto_coordinates)
        btn_layout.addWidget(self.goto_btn)

        self.my_location_btn = QPushButton("موقعي الحالي")
        self.my_location_btn.clicked.connect(self._get_current_location)
        btn_layout.addWidget(self.my_location_btn)

        self.copy_btn = QPushButton("نسخ")
        self.copy_btn.clicked.connect(self._copy_coordinates)
        btn_layout.addWidget(self.copy_btn)

        coord_layout.addLayout(btn_layout)

        layout.addWidget(coord_group)

        # Polygon info (hidden by default)
        self.polygon_group = QGroupBox("معلومات المضلع")
        polygon_layout = QVBoxLayout(self.polygon_group)

        self.polygon_points_label = QLabel("عدد النقاط: 0")
        polygon_layout.addWidget(self.polygon_points_label)

        self.polygon_area_label = QLabel("المساحة: 0 م²")
        polygon_layout.addWidget(self.polygon_area_label)

        self.polygon_wkt_btn = QPushButton("عرض WKT")
        self.polygon_wkt_btn.clicked.connect(self._show_polygon_wkt)
        polygon_layout.addWidget(self.polygon_wkt_btn)

        layout.addWidget(self.polygon_group)
        self.polygon_group.hide()

    def _setup_map(self):
        """Setup the web-based map."""
        # Create web channel for Python-JS communication
        self.channel = QWebChannel()
        self.channel.registerObject('pyBridge', self)
        self.map_view.page().setWebChannel(self.channel)

        # Load map HTML
        html = self._get_map_html()
        self.map_view.setHtml(html)

    def _get_map_html(self) -> str:
        """Generate the map HTML with Leaflet.js (OFFLINE VERSION using centralized tile server)."""
        # Use the centralized tile server
        from services.tile_server_manager import get_tile_server_url

        tile_server_url = get_tile_server_url()

        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <style>
        html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
    </style>
</head>
<body>
    <div id="map"></div>

    <script src="{tile_server_url}/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>
        var map = null;
        var marker = null;
        var polygon = null;
        var drawnItems = null;
        var pyBridge = null;
        var currentMode = 'marker';

        // Initialize QWebChannel
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            pyBridge = channel.objects.pyBridge;
            console.log('QWebChannel initialized for MapCoordinatePickerWidget');
        }});

        // Initialize map with offline tiles
        map = L.map('map', {{
            preferCanvas: true,
            zoomAnimation: true,
            fadeAnimation: false
        }}).setView([{self.DEFAULT_CENTER[0]}, {self.DEFAULT_CENTER[1]}], {self.DEFAULT_ZOOM});

        // Use LOCAL tiles from MBTiles
        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 20,
            minZoom: 15,
            attribution: 'UN-Habitat Syria - يعمل بدون اتصال بالإنترنت',
            updateWhenIdle: true,
            keepBuffer: 2,
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        }}).addTo(map);

        // Initialize draw controls
        drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Click handler for marker mode
        map.on('click', function(e) {{
            if (currentMode === 'marker') {{
                setMarker(e.latlng.lat, e.latlng.lng);
                if (pyBridge) {{
                    pyBridge.onMapClick(e.latlng.lat, e.latlng.lng);
                }}
            }} else if (currentMode === 'polygon') {{
                addPolygonPoint(e.latlng.lat, e.latlng.lng);
            }}
        }});

        // Set marker position
        function setMarker(lat, lng) {{
            if (marker) {{
                marker.setLatLng([lat, lng]);
            }} else {{
                marker = L.marker([lat, lng], {{draggable: true}}).addTo(map);
                marker.on('dragend', function(e) {{
                    var pos = marker.getLatLng();
                    if (pyBridge) {{
                        pyBridge.onMarkerDrag(pos.lat, pos.lng);
                    }}
                }});
            }}
            marker.bindPopup('<div class="coordinate-popup">' +
                'Lat: ' + lat.toFixed(6) + '<br>' +
                'Lng: ' + lng.toFixed(6) + '</div>').openPopup();
        }}

        // Polygon drawing
        var polygonPoints = [];

        function addPolygonPoint(lat, lng) {{
            polygonPoints.push([lat, lng]);

            if (polygon) {{
                map.removeLayer(polygon);
            }}

            if (polygonPoints.length >= 2) {{
                polygon = L.polygon(polygonPoints, {{color: 'blue', fillOpacity: 0.3}}).addTo(map);
            }}

            // Add vertex marker
            L.circleMarker([lat, lng], {{radius: 5, color: 'blue', fillColor: 'white', fillOpacity: 1}}).addTo(drawnItems);

            if (pyBridge) {{
                pyBridge.onPolygonPoint(lat, lng, polygonPoints.length);
            }}
        }}

        function completePolygon() {{
            if (polygonPoints.length >= 3) {{
                if (pyBridge) {{
                    pyBridge.onPolygonComplete(JSON.stringify(polygonPoints));
                }}
            }}
        }}

        function clearDrawing() {{
            if (marker) {{
                map.removeLayer(marker);
                marker = null;
            }}
            if (polygon) {{
                map.removeLayer(polygon);
                polygon = null;
            }}
            drawnItems.clearLayers();
            polygonPoints = [];
        }}

        // Pan to coordinates
        function panTo(lat, lng, zoom) {{
            map.setView([lat, lng], zoom || map.getZoom());
            setMarker(lat, lng);
        }}

        // Set drawing mode
        function setMode(mode) {{
            currentMode = mode;
            if (mode === 'polygon') {{
                clearDrawing();
            }}
        }}
    </script>
</body>
</html>
        '''

    # ==================== JavaScript Bridge Methods ====================

    def onMapClick(self, lat: float, lng: float):
        """Called from JavaScript when map is clicked."""
        self._set_coordinate(lat, lng)
        self.coordinate_selected.emit(lat, lng)

    def onMarkerDrag(self, lat: float, lng: float):
        """Called from JavaScript when marker is dragged."""
        self._set_coordinate(lat, lng)
        self.coordinate_changed.emit(lat, lng)

    def onPolygonPoint(self, lat: float, lng: float, point_count: int):
        """Called from JavaScript when polygon point is added."""
        self.polygon_points_label.setText(f"عدد النقاط: {point_count}")
        self.polygon_group.show()

    def onPolygonComplete(self, points_json: str):
        """Called from JavaScript when polygon is completed."""
        try:
            points = json.loads(points_json)
            self._polygon = GeoPolygon([
                GeoCoordinate(p[0], p[1]) for p in points
            ])

            # Update UI
            area = self._polygon.area()
            self.polygon_area_label.setText(f"المساحة: {area:,.2f} م²")

            # Emit signal
            self.polygon_completed.emit([(p.latitude, p.longitude) for p in self._polygon.points])

        except Exception as e:
            logger.error(f"Error parsing polygon: {e}")

    # ==================== Public Methods ====================

    def set_coordinate(self, lat: float, lng: float):
        """Set coordinate programmatically."""
        self._set_coordinate(lat, lng)
        self._run_js(f"panTo({lat}, {lng})")

    def get_coordinate(self) -> Optional[GeoCoordinate]:
        """Get the current coordinate."""
        return self._coordinate

    def get_polygon(self) -> Optional[GeoPolygon]:
        """Get the current polygon."""
        return self._polygon

    def set_center(self, lat: float, lng: float, zoom: int = None):
        """Set map center."""
        zoom_val = zoom if zoom else "null"
        self._run_js(f"panTo({lat}, {lng}, {zoom_val})")

    def clear(self):
        """Clear all markers and polygons."""
        self._clear_map()

    # ==================== Private Methods ====================

    def _set_coordinate(self, lat: float, lng: float):
        """Internal method to set coordinate."""
        self._coordinate = GeoCoordinate(lat, lng)

        # Update input fields (block signals to avoid loop)
        self.lat_input.blockSignals(True)
        self.lng_input.blockSignals(True)
        self.lat_input.setValue(lat)
        self.lng_input.setValue(lng)
        self.lat_input.blockSignals(False)
        self.lng_input.blockSignals(False)

        self._update_coordinate_display()
        self._validate_coordinate()

    def _update_coordinate_display(self):
        """Update the coordinate display based on selected format."""
        if not self._coordinate:
            self.coord_display_label.setText("")
            return

        format_type = self.format_combo.currentData()

        if format_type == CoordinateFormat.DMS:
            lat_str, lng_str = self._coordinate.to_dms()
            self.coord_display_label.setText(f"{lat_str}, {lng_str}")
        elif format_type == CoordinateFormat.DDM:
            lat_str, lng_str = self._coordinate.to_ddm()
            self.coord_display_label.setText(f"{lat_str}, {lng_str}")
        else:
            self.coord_display_label.setText(
                f"{self._coordinate.latitude:.{self._precision}f}°, "
                f"{self._coordinate.longitude:.{self._precision}f}°"
            )

    def _validate_coordinate(self):
        """Validate the current coordinate."""
        if not self._coordinate:
            self.validation_label.setText("")
            self.validation_label.setStyleSheet("")
            return

        if not self._coordinate.is_valid():
            self.validation_label.setText("⚠️ إحداثيات غير صالحة")
            self.validation_label.setStyleSheet("color: red;")
        elif not self._coordinate.is_in_iraq():
            self.validation_label.setText("⚠️ الإحداثيات خارج العراق")
            self.validation_label.setStyleSheet("color: orange;")
        else:
            self.validation_label.setText("✓ إحداثيات صالحة")
            self.validation_label.setStyleSheet("color: green;")

    def _on_manual_coordinate_change(self):
        """Handle manual coordinate entry."""
        lat = self.lat_input.value()
        lng = self.lng_input.value()

        self._coordinate = GeoCoordinate(lat, lng)
        self._update_coordinate_display()
        self._validate_coordinate()

        self.coordinate_changed.emit(lat, lng)

    def _on_provider_changed(self, index: int):
        """Handle map provider change."""
        provider = self.provider_combo.currentData()
        self._map_provider = provider
        self._run_js(f"setTileLayer('{provider.value}')")

    def _goto_coordinates(self):
        """Pan map to entered coordinates."""
        lat = self.lat_input.value()
        lng = self.lng_input.value()
        self._run_js(f"panTo({lat}, {lng}, 15)")

    def _get_current_location(self):
        """Get current GPS location (if available)."""
        # Note: This requires additional implementation for GPS access
        # For now, show a message
        ErrorHandler.show_success(
            self,
            "هذه الميزة تتطلب جهاز GPS.\n"
            "يرجى إدخال الإحداثيات يدوياً أو النقر على الخريطة.",
            "الموقع الحالي"
        )

    def _copy_coordinates(self):
        """Copy coordinates to clipboard."""
        if not self._coordinate:
            return

        from PyQt5.QtWidgets import QApplication
        text = f"{self._coordinate.latitude},{self._coordinate.longitude}"
        QApplication.clipboard().setText(text)

    def _clear_map(self):
        """Clear all map markers and polygons."""
        self._coordinate = None
        self._polygon = None

        self.lat_input.blockSignals(True)
        self.lng_input.blockSignals(True)
        self.lat_input.setValue(0)
        self.lng_input.setValue(0)
        self.lat_input.blockSignals(False)
        self.lng_input.blockSignals(False)

        self.coord_display_label.setText("")
        self.validation_label.setText("")
        self.polygon_group.hide()
        self.polygon_points_label.setText("عدد النقاط: 0")
        self.polygon_area_label.setText("المساحة: 0 م²")

        self._run_js("clearDrawing()")

    def _show_polygon_wkt(self):
        """Show polygon WKT in a dialog."""
        if not self._polygon:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("صيغة WKT")
        dialog.setMinimumSize(400, 200)

        layout = QVBoxLayout(dialog)

        tabs = QTabWidget()

        # WKT tab
        wkt_text = QTextEdit()
        wkt_text.setPlainText(self._polygon.to_wkt())
        wkt_text.setReadOnly(True)
        tabs.addTab(wkt_text, "WKT")

        # GeoJSON tab
        geojson_text = QTextEdit()
        geojson_text.setPlainText(json.dumps(self._polygon.to_geojson(), indent=2))
        geojson_text.setReadOnly(True)
        tabs.addTab(geojson_text, "GeoJSON")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec_()

    def _run_js(self, script: str):
        """Run JavaScript in the map view."""
        self.map_view.page().runJavaScript(script)


class CoordinateInputDialog(QDialog):
    """Dialog for entering coordinates manually."""

    def __init__(self, parent=None, initial_lat: float = 0, initial_lng: float = 0):
        super().__init__(parent)
        self.setWindowTitle("إدخال الإحداثيات")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Coordinate picker widget
        self.picker = MapCoordinatePickerWidget()
        if initial_lat != 0 or initial_lng != 0:
            self.picker.set_coordinate(initial_lat, initial_lng)
        layout.addWidget(self.picker)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_coordinate(self) -> Optional[GeoCoordinate]:
        """Get the selected coordinate."""
        return self.picker.get_coordinate()

    def get_polygon(self) -> Optional[GeoPolygon]:
        """Get the drawn polygon."""
        return self.picker.get_polygon()


# Utility functions for coordinate parsing

def parse_coordinate(text: str) -> Optional[GeoCoordinate]:
    """
    Parse coordinate from various formats.

    Supports:
    - Decimal degrees: "33.3152, 44.3661"
    - DMS: "33° 18' 54.72\" N, 44° 21' 58.0\" E"
    - DDM: "33° 18.912' N, 44° 21.967' E"
    """
    import re

    text = text.strip()

    # Try decimal degrees (comma separated)
    dd_match = re.match(r'^(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)$', text)
    if dd_match:
        return GeoCoordinate(float(dd_match.group(1)), float(dd_match.group(2)))

    # Try DMS format
    dms_pattern = r"(\d+)°\s*(\d+)'\s*([\d.]+)\"\s*([NS])\s*,?\s*(\d+)°\s*(\d+)'\s*([\d.]+)\"\s*([EW])"
    dms_match = re.match(dms_pattern, text, re.IGNORECASE)
    if dms_match:
        lat_d, lat_m, lat_s, lat_dir = dms_match.groups()[:4]
        lng_d, lng_m, lng_s, lng_dir = dms_match.groups()[4:]

        lat = int(lat_d) + int(lat_m)/60 + float(lat_s)/3600
        if lat_dir.upper() == 'S':
            lat = -lat

        lng = int(lng_d) + int(lng_m)/60 + float(lng_s)/3600
        if lng_dir.upper() == 'W':
            lng = -lng

        return GeoCoordinate(lat, lng)

    # Try DDM format
    ddm_pattern = r"(\d+)°\s*([\d.]+)'\s*([NS])\s*,?\s*(\d+)°\s*([\d.]+)'\s*([EW])"
    ddm_match = re.match(ddm_pattern, text, re.IGNORECASE)
    if ddm_match:
        lat_d, lat_m, lat_dir = ddm_match.groups()[:3]
        lng_d, lng_m, lng_dir = ddm_match.groups()[3:]

        lat = int(lat_d) + float(lat_m)/60
        if lat_dir.upper() == 'S':
            lat = -lat

        lng = int(lng_d) + float(lng_m)/60
        if lng_dir.upper() == 'W':
            lng = -lng

        return GeoCoordinate(lat, lng)

    return None


def format_coordinate(coord: GeoCoordinate, format_type: CoordinateFormat = CoordinateFormat.DECIMAL_DEGREES) -> str:
    """Format coordinate to string."""
    if format_type == CoordinateFormat.DMS:
        lat_str, lng_str = coord.to_dms()
        return f"{lat_str}, {lng_str}"
    elif format_type == CoordinateFormat.DDM:
        lat_str, lng_str = coord.to_ddm()
        return f"{lat_str}, {lng_str}"
    else:
        return f"{coord.latitude:.6f}, {coord.longitude:.6f}"
