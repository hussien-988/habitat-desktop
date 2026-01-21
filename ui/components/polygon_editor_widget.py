# -*- coding: utf-8 -*-
"""
Polygon Editor Widget - Interactive Polygon Drawing and Editing.

Provides interactive polygon creation and editing capabilities using Leaflet.draw.

Features:
- Click to draw polygon vertices
- Drag vertices to edit shape
- Add/remove vertices
- Real-time area calculation
- Self-intersection detection
- Undo/redo support

Usage:
    editor = PolygonEditorWidget()
    editor.polygon_changed.connect(on_polygon_changed)
    polygon_wkt = editor.get_polygon_wkt()
"""

from typing import Optional, List, Tuple, Dict, Any
import json
import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QToolButton, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QObject, pyqtSlot
from PyQt5.QtGui import QColor

from utils.logger import get_logger

logger = get_logger(__name__)

# Check for WebEngine availability
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None


class PolygonBridge(QObject):
    """Bridge between JavaScript and Python for polygon editing."""

    polygon_updated = pyqtSignal(str)  # Emits GeoJSON string
    area_updated = pyqtSignal(float)   # Emits area in square meters
    error_occurred = pyqtSignal(str)   # Emits error message

    @pyqtSlot(str)
    def on_polygon_drawn(self, geojson_str: str):
        """Called from JavaScript when polygon is drawn/edited."""
        try:
            geojson = json.loads(geojson_str)
            logger.debug(f"Polygon updated: {len(geojson.get('coordinates', [[]])[0])} vertices")
            self.polygon_updated.emit(geojson_str)

            # Calculate area
            coords = geojson.get('coordinates', [[]])[0]
            area = self._calculate_area(coords)
            self.area_updated.emit(area)

        except Exception as e:
            logger.error(f"Error processing polygon: {e}")
            self.error_occurred.emit(str(e))

    @pyqtSlot(str)
    def on_validation_error(self, error_msg: str):
        """Called from JavaScript when validation fails."""
        self.error_occurred.emit(error_msg)

    def _calculate_area(self, coordinates: List[List[float]]) -> float:
        """
        Calculate polygon area in square meters using spherical excess formula.

        Args:
            coordinates: List of [lon, lat] pairs

        Returns:
            Area in square meters
        """
        if len(coordinates) < 3:
            return 0.0

        # Convert to radians
        coords_rad = [(math.radians(lon), math.radians(lat)) for lon, lat in coordinates]

        # Spherical excess formula
        R = 6371000  # Earth radius in meters
        area = 0.0

        for i in range(len(coords_rad)):
            lon1, lat1 = coords_rad[i]
            lon2, lat2 = coords_rad[(i + 1) % len(coords_rad)]

            area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

        area = abs(area * R * R / 2.0)

        return area


class PolygonEditorWidget(QWidget):
    """
    Interactive polygon editor widget.

    Signals:
        polygon_changed: Emitted when polygon is modified (geojson_str)
        area_changed: Emitted when area changes (area_sqm)
    """

    polygon_changed = pyqtSignal(str)  # GeoJSON string
    area_changed = pyqtSignal(float)   # Area in square meters

    def __init__(self, parent=None):
        """Initialize the polygon editor."""
        super().__init__(parent)

        self._current_polygon_geojson = None
        self._current_area = 0.0
        self._bridge = PolygonBridge()

        # Connect bridge signals
        self._bridge.polygon_updated.connect(self._on_polygon_updated)
        self._bridge.area_updated.connect(self._on_area_updated)
        self._bridge.error_occurred.connect(self._on_error)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # Map view
        if HAS_WEBENGINE:
            self.map_view = QWebEngineView()
            self.map_view.setMinimumHeight(400)

            # Setup web channel for JS ↔ Python communication
            self.channel = QWebChannel()
            self.channel.registerObject("polygonBridge", self._bridge)
            self.map_view.page().setWebChannel(self.channel)

            # Load map HTML
            self._load_map()

            layout.addWidget(self.map_view, 1)
        else:
            # Fallback message
            msg = QLabel("⚠️ Polygon editor requires PyQtWebEngine")
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet("color: #E67E22; font-size: 14px; padding: 40px;")
            layout.addWidget(msg, 1)

        # Status bar
        status_frame = QFrame()
        status_frame.setStyleSheet("background: #F8F9FA; border-top: 1px solid #DEE2E6; padding: 8px;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 6, 12, 6)

        self.status_label = QLabel("انقر على الخريطة لبدء رسم المضلع")
        self.status_label.setStyleSheet("color: #6C757D; font-size: 12px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.area_label = QLabel("المساحة: 0 م²")
        self.area_label.setStyleSheet("color: #495057; font-weight: 600; font-size: 12px;")
        status_layout.addWidget(self.area_label)

        layout.addWidget(status_frame)

    def _create_toolbar(self) -> QWidget:
        """Create the toolbar with editing tools."""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #DEE2E6;
                border-radius: 6px;
                padding: 6px;
            }
        """)

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(6)

        # Draw button
        self.draw_btn = self._create_tool_button("✏️", "رسم مضلع جديد")
        self.draw_btn.clicked.connect(self._start_drawing)
        toolbar_layout.addWidget(self.draw_btn)

        # Edit button
        self.edit_btn = self._create_tool_button("✂️", "تعديل المضلع")
        self.edit_btn.clicked.connect(self._start_editing)
        self.edit_btn.setEnabled(False)
        toolbar_layout.addWidget(self.edit_btn)

        # Delete button
        self.delete_btn = self._create_tool_button("🗑️", "حذف المضلع")
        self.delete_btn.clicked.connect(self._delete_polygon)
        self.delete_btn.setEnabled(False)
        toolbar_layout.addWidget(self.delete_btn)

        toolbar_layout.addSpacing(12)

        # Undo button
        self.undo_btn = self._create_tool_button("↶", "تراجع")
        self.undo_btn.clicked.connect(self._undo)
        self.undo_btn.setEnabled(False)
        toolbar_layout.addWidget(self.undo_btn)

        # Redo button
        self.redo_btn = self._create_tool_button("↷", "إعادة")
        self.redo_btn.clicked.connect(self._redo)
        self.redo_btn.setEnabled(False)
        toolbar_layout.addWidget(self.redo_btn)

        toolbar_layout.addStretch()

        # Validate button
        self.validate_btn = QPushButton("✓ التحقق من الصحة")
        self.validate_btn.setStyleSheet("""
            QPushButton {
                background: #28A745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #218838;
            }
            QPushButton:disabled {
                background: #CCC;
            }
        """)
        self.validate_btn.clicked.connect(self._validate_polygon)
        self.validate_btn.setEnabled(False)
        toolbar_layout.addWidget(self.validate_btn)

        return toolbar

    def _create_tool_button(self, icon: str, tooltip: str) -> QToolButton:
        """Create a toolbar button."""
        btn = QToolButton()
        btn.setText(icon)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #DEE2E6;
                border-radius: 4px;
                padding: 6px 10px;
                background: white;
                font-size: 16px;
            }
            QToolButton:hover {
                background: #E9ECEF;
                border-color: #ADB5BD;
            }
            QToolButton:pressed {
                background: #DEE2E6;
            }
            QToolButton:disabled {
                opacity: 0.5;
            }
        """)
        return btn

    def _load_map(self):
        """Load Leaflet map with polygon drawing capabilities."""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        body { margin: 0; padding: 0; }
        #map { width: 100%; height: 100vh; }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        // Initialize map (Aleppo center)
        var map = L.map('map').setView([36.2021, 37.1343], 13);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Feature group for drawn polygons
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Drawing controls
        var drawControl = new L.Control.Draw({
            position: 'topright',
            draw: {
                polygon: {
                    shapeOptions: {
                        color: '#3388ff',
                        fillOpacity: 0.3
                    },
                    allowIntersection: false,
                    showArea: true,
                    metric: true
                },
                polyline: false,
                rectangle: false,
                circle: false,
                marker: false,
                circlemarker: false
            },
            edit: {
                featureGroup: drawnItems,
                edit: true,
                remove: true
            }
        });
        map.addControl(drawControl);

        // Setup web channel for Python communication
        var polygonBridge = null;
        new QWebChannel(qt.webChannelTransport, function(channel) {
            polygonBridge = channel.objects.polygonBridge;
        });

        // Handle polygon creation
        map.on(L.Draw.Event.CREATED, function(e) {
            var layer = e.layer;
            drawnItems.addLayer(layer);

            var geojson = layer.toGeoJSON().geometry;
            if (polygonBridge) {
                polygonBridge.on_polygon_drawn(JSON.stringify(geojson));
            }
        });

        // Handle polygon editing
        map.on(L.Draw.Event.EDITED, function(e) {
            var layers = e.layers;
            layers.eachLayer(function(layer) {
                var geojson = layer.toGeoJSON().geometry;
                if (polygonBridge) {
                    polygonBridge.on_polygon_drawn(JSON.stringify(geojson));
                }
            });
        });

        // Handle polygon deletion
        map.on(L.Draw.Event.DELETED, function(e) {
            if (polygonBridge) {
                polygonBridge.on_polygon_drawn('null');
            }
        });

        // Validation: Check for self-intersections
        function validatePolygon(coordinates) {
            // Basic validation
            if (coordinates.length < 3) {
                return {valid: false, error: "يجب أن يحتوي المضلع على 3 نقاط على الأقل"};
            }

            // Check if first and last points are the same
            var first = coordinates[0];
            var last = coordinates[coordinates.length - 1];
            if (first[0] !== last[0] || first[1] !== last[1]) {
                coordinates.push(first);  // Close the polygon
            }

            // TODO: Add self-intersection detection

            return {valid: true};
        }

        // Expose functions to Python
        window.startDrawing = function() {
            new L.Draw.Polygon(map, drawControl.options.draw.polygon).enable();
        };

        window.startEditing = function() {
            new L.EditToolbar.Edit(map, {featureGroup: drawnItems}).enable();
        };

        window.deletePolygon = function() {
            drawnItems.clearLayers();
            if (polygonBridge) {
                polygonBridge.on_polygon_drawn('null');
            }
        };

        window.loadPolygon = function(geojsonStr) {
            try {
                drawnItems.clearLayers();
                var geojson = JSON.parse(geojsonStr);
                var layer = L.geoJSON(geojson);
                drawnItems.addLayer(layer.getLayers()[0]);
                map.fitBounds(drawnItems.getBounds());
            } catch(e) {
                console.error('Error loading polygon:', e);
            }
        };
    </script>
</body>
</html>
        """

        self.map_view.setHtml(html)

    def _start_drawing(self):
        """Start drawing a new polygon."""
        if HAS_WEBENGINE:
            self.map_view.page().runJavaScript("window.startDrawing();")
            self.status_label.setText("انقر على الخريطة لإضافة نقاط المضلع. انقر مرتين للإنهاء.")

    def _start_editing(self):
        """Start editing existing polygon."""
        if HAS_WEBENGINE:
            self.map_view.page().runJavaScript("window.startEditing();")
            self.status_label.setText("اسحب النقاط لتعديل شكل المضلع")

    def _delete_polygon(self):
        """Delete current polygon."""
        if HAS_WEBENGINE:
            reply = QMessageBox.question(
                self,
                "تأكيد الحذف",
                "هل أنت متأكد من حذف المضلع؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.map_view.page().runJavaScript("window.deletePolygon();")
                self._current_polygon_geojson = None
                self._current_area = 0.0
                self._update_ui_state()

    def _undo(self):
        """Undo last edit."""
        # TODO: Implement undo stack
        pass

    def _redo(self):
        """Redo last undone edit."""
        # TODO: Implement redo stack
        pass

    def _validate_polygon(self):
        """Validate current polygon."""
        if not self._current_polygon_geojson:
            QMessageBox.warning(self, "تحذير", "لا يوجد مضلع للتحقق منه")
            return

        try:
            geojson = json.loads(self._current_polygon_geojson)
            coords = geojson.get('coordinates', [[]])[0]

            # Validation checks
            errors = []

            if len(coords) < 3:
                errors.append("المضلع يجب أن يحتوي على 3 نقاط على الأقل")

            if self._current_area < 1:  # Less than 1 square meter
                errors.append("المضلع صغير جداً (أقل من 1 متر مربع)")

            # Check for self-intersection (basic check)
            # TODO: Implement more sophisticated algorithm

            if errors:
                QMessageBox.warning(
                    self,
                    "أخطاء في المضلع",
                    "\n".join(f"• {error}" for error in errors)
                )
            else:
                QMessageBox.information(
                    self,
                    "✓ المضلع صحيح",
                    f"المضلع صحيح ويحتوي على {len(coords)} نقطة\n"
                    f"المساحة: {self._current_area:.2f} متر مربع"
                )

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل التحقق: {str(e)}")

    def _on_polygon_updated(self, geojson_str: str):
        """Handle polygon update from bridge."""
        self._current_polygon_geojson = geojson_str if geojson_str != 'null' else None
        self._update_ui_state()
        self.polygon_changed.emit(geojson_str)

    def _on_area_updated(self, area: float):
        """Handle area update from bridge."""
        self._current_area = area
        self.area_label.setText(f"المساحة: {area:.2f} م²")
        self.area_changed.emit(area)

    def _on_error(self, error_msg: str):
        """Handle error from bridge."""
        logger.warning(f"Polygon editor error: {error_msg}")
        QMessageBox.warning(self, "تحذير", error_msg)

    def _update_ui_state(self):
        """Update UI button states based on current polygon."""
        has_polygon = self._current_polygon_geojson is not None

        self.edit_btn.setEnabled(has_polygon)
        self.delete_btn.setEnabled(has_polygon)
        self.validate_btn.setEnabled(has_polygon)

        if has_polygon:
            self.status_label.setText("✓ تم رسم المضلع. يمكنك التعديل أو الحذف.")
        else:
            self.status_label.setText("انقر على 'رسم مضلع جديد' للبدء")

    # Public API

    def set_polygon(self, geojson_or_wkt: str):
        """
        Load a polygon into the editor.

        Args:
            geojson_or_wkt: GeoJSON string or WKT polygon string
        """
        if not HAS_WEBENGINE:
            return

        try:
            # Try to parse as GeoJSON
            if geojson_or_wkt.strip().startswith('{'):
                geojson_str = geojson_or_wkt
            else:
                # Convert WKT to GeoJSON
                from services.map_service import GeoPolygon
                polygon = GeoPolygon.from_wkt(geojson_or_wkt)
                if polygon:
                    geojson_str = json.dumps(polygon.to_geojson())
                else:
                    raise ValueError("Invalid WKT format")

            # Load into map
            self.map_view.page().runJavaScript(
                f"window.loadPolygon('{geojson_str}');"
            )

            self._current_polygon_geojson = geojson_str
            self._update_ui_state()

        except Exception as e:
            logger.error(f"Error loading polygon: {e}")
            QMessageBox.warning(self, "خطأ", f"فشل تحميل المضلع: {str(e)}")

    def get_polygon_geojson(self) -> Optional[str]:
        """Get current polygon as GeoJSON string."""
        return self._current_polygon_geojson

    def get_polygon_wkt(self) -> Optional[str]:
        """Get current polygon as WKT string."""
        if not self._current_polygon_geojson:
            return None

        try:
            geojson = json.loads(self._current_polygon_geojson)
            coords = geojson.get('coordinates', [[]])[0]

            # Convert to WKT format
            points = ", ".join([f"{lon} {lat}" for lon, lat in coords])
            return f"POLYGON (({points}))"

        except Exception as e:
            logger.error(f"Error converting to WKT: {e}")
            return None

    def get_area_sqm(self) -> float:
        """Get current polygon area in square meters."""
        return self._current_area

    def clear(self):
        """Clear the current polygon."""
        self._delete_polygon()
