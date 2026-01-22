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

    @pyqtSlot(str)
    def geometryDrawn(self, geojson_str: str):
        """
        Called from Leaflet.draw when a shape is drawn.
        Converts GeoJSON to WKT and processes it.
        """
        import json
        logger.info(f"✅ Geometry drawn from Leaflet.draw: {geojson_str[:100]}...")

        try:
            geom = json.loads(geojson_str)
            geom_type = geom.get('type')
            coords = geom.get('coordinates')

            if geom_type == 'Point':
                # Point: coordinates = [lon, lat]
                lon, lat = coords[0], coords[1]
                self.set_location(lat, lon)

            elif geom_type == 'Polygon':
                # Polygon: coordinates = [[[lon, lat], [lon, lat], ...]]
                # Convert to WKT
                ring = coords[0]
                wkt_coords = ', '.join([f"{lon} {lat}" for lon, lat in ring])
                wkt = f"POLYGON(({wkt_coords}))"
                self.set_polygon(wkt)

            else:
                logger.warning(f"Unsupported geometry type: {geom_type}")

        except Exception as e:
            logger.error(f"❌ Failed to parse drawn geometry: {e}")

    # Alias for compatibility
    shapeDrawn = geometryDrawn


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

    def _get_buildings_geojson(self):
        """Get all buildings as GeoJSON for unified map display."""
        import json
        try:
            from repositories.database import Database
            from repositories.building_repository import BuildingRepository

            db = Database()
            building_repo = BuildingRepository(db)
            buildings = building_repo.get_all(limit=1000)  # Get up to 1000 buildings

            # تحويل المباني إلى GeoJSON باستخدام نفس منطق map_page.py
            features = []
            for building in buildings:
                geometry = None

                # أولوية للمضلع إذا كان موجوداً
                if building.geo_location and 'POLYGON' in building.geo_location.upper():
                    geometry = self._parse_wkt_to_geojson(building.geo_location)

                # إذا لم يكن هناك مضلع، استخدم النقطة
                if not geometry and building.latitude and building.longitude:
                    geometry = {
                        "type": "Point",
                        "coordinates": [building.longitude, building.latitude]
                    }

                if geometry:
                    features.append({
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {
                            "building_id": building.building_id or "",
                            "neighborhood": building.neighborhood_name_ar or building.neighborhood_name or "",
                            "status": building.building_status or "intact",
                            "units": building.number_of_units or 0,
                            "type": building.building_type or "",
                            "geometry_type": geometry["type"]
                        }
                    })

            return json.dumps({
                "type": "FeatureCollection",
                "features": features
            })
        except Exception as e:
            logger.error(f"Failed to load buildings for map: {e}")
            return '{"type": "FeatureCollection", "features": []}'

    def _parse_wkt_to_geojson(self, wkt: str) -> dict:
        """تحليل WKT (POLYGON/MULTIPOLYGON) إلى GeoJSON - نفس منطق map_page.py"""
        try:
            wkt = wkt.strip()

            # معالجة MULTIPOLYGON
            if wkt.upper().startswith('MULTIPOLYGON'):
                content = wkt[wkt.index('(')+1:wkt.rindex(')')]

                polygons = []
                depth = 0
                current_polygon = []
                current_pos = 0

                for i, char in enumerate(content):
                    if char == '(':
                        depth += 1
                        if depth == 2:
                            current_pos = i + 1
                    elif char == ')':
                        if depth == 2:
                            polygon_str = content[current_pos:i]
                            coords = self._parse_polygon_coords(polygon_str)
                            if coords:
                                polygons.append(coords)
                        depth -= 1

                if polygons:
                    return {
                        "type": "MultiPolygon",
                        "coordinates": polygons
                    }

            # معالجة POLYGON عادي
            elif wkt.upper().startswith('POLYGON'):
                content = wkt[wkt.index('(')+1:wkt.rindex(')')]
                coords = self._parse_polygon_coords(content)

                if coords:
                    return {
                        "type": "Polygon",
                        "coordinates": coords
                    }

        except Exception as e:
            logger.warning(f"Failed to parse WKT: {e}")

        return None

    def _parse_polygon_coords(self, polygon_str: str) -> list:
        """تحليل إحداثيات المضلع - نفس منطق map_page.py"""
        rings = []

        # تقسيم الحلقات (خارجية + ثقوب)
        depth = 0
        ring_parts = []
        current_start = 0

        for i, char in enumerate(polygon_str):
            if char == '(':
                if depth == 0:
                    current_start = i + 1
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    ring_parts.append(polygon_str[current_start:i])

        # إذا لم تكن هناك أقواس داخلية، استخدم النص كله
        if not ring_parts:
            ring_parts = [polygon_str.strip('()')]

        for ring_str in ring_parts:
            ring = []
            for point_str in ring_str.split(','):
                point_str = point_str.strip()
                if point_str:
                    parts = point_str.split()
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        ring.append([lon, lat])

            if ring:
                rings.append(ring)

        return rings if rings else None

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

    def _load_map(self, drawing_mode: str = 'both'):
        """Load the Leaflet map - WITH base URL like test_map_simple.py."""
        html = self._generate_map_html(drawing_mode=drawing_mode)
        tile_server_url = self._get_tile_server_url()
        # CRITICAL: Set base URL so QWebEngineView can resolve requests
        base_url = QUrl(tile_server_url)
        self.web_view.setHtml(html, base_url)

    def _generate_map_html(self, drawing_mode: str = 'both') -> str:
        """Generate HTML for the Leaflet map - استخدام LeafletHTMLGenerator الموحد."""
        tile_server_url = self._get_tile_server_url()

        # Load all buildings from database as GeoJSON
        buildings_geojson = self._get_buildings_geojson()

        # استخدام LeafletHTMLGenerator الموحد - DRY Principle
        from services.leaflet_html_generator import generate_leaflet_html

        html = generate_leaflet_html(
            tile_server_url=tile_server_url,
            buildings_geojson=buildings_geojson,
            center_lat=self.initial_lat,
            center_lon=self.initial_lon,
            zoom=17,
            show_legend=True,
            show_layer_control=False,
            enable_selection=False,  # هذا للاختيار من خريطة، ليس لاختيار مبنى موجود
            enable_drawing=True,     # تفعيل أدوات الرسم لإضافة نقطة أو مضلع جديدة
            drawing_mode=drawing_mode  # تحديد نوع الرسم: point, polygon, both
        )

        return html

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
        # تحديد الوضع بناءً على الزر المختار
        if self.point_radio.isChecked():
            drawing_mode = 'point'
            logger.info("Drawing mode changed to: Point")
        else:
            drawing_mode = 'polygon'
            logger.info("Drawing mode changed to: Polygon")

        # إعادة تحميل الخريطة مع الوضع الجديد
        self._load_map(drawing_mode=drawing_mode)

    def _clear_selection(self):
        """Clear the current selection."""
        # مسح العرض فقط، الخريطة ثابتة
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
