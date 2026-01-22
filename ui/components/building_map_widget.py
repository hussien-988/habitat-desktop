# -*- coding: utf-8 -*-
"""
Building Map Widget - Shared Component for Map Services.

Reusable component that provides interactive building selection map.
Follows DRY and SOLID principles - single source of truth for map functionality.

Usage:
    widget = BuildingMapWidget(db)
    widget.building_selected.connect(on_building_selected)
    widget.show_dialog()
"""

from typing import Optional, Callable
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QUrl

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)

# Check for WebEngine availability
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None

# Check for WebChannel availability
try:
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBCHANNEL = False


class BuildingMapWidget(QObject):
    """
    Shared component for building selection via interactive map.

    Provides:
    - Interactive Leaflet map with building markers
    - Color-coded building status
    - Building selection via popup
    - Reusable across different parts of the application

    Signals:
        building_selected: Emitted when user selects a building (Building object)
    """

    building_selected = pyqtSignal(object)  # Emits Building object

    def __init__(self, db: Database, parent=None):
        """
        Initialize the map widget.

        Args:
            db: Database instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.db = db
        self.building_repo = BuildingRepository(db)
        self._dialog = None
        self._map_view = None

    def show_dialog(self) -> Optional[Building]:
        """
        Show the map selection dialog.

        Returns:
            Selected Building object, or None if cancelled
        """
        if not HAS_WEBENGINE:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                None,
                "غير متوفر",
                "البحث على الخريطة غير متوفر (يتطلب PyQtWebEngine)"
            )
            return None

        # Create dialog if not exists (reuse for performance)
        if self._dialog is None:
            self._dialog = self._create_dialog()

        # Load/reload map
        self._load_map()

        # Show dialog (modal)
        result = self._dialog.exec_()

        # Return selected building if accepted
        if result == QDialog.Accepted and hasattr(self, '_selected_building'):
            return self._selected_building
        return None

    def _create_dialog(self) -> QDialog:
        """Create the map dialog UI."""
        dialog = QDialog()
        dialog.setModal(True)
        dialog.setWindowTitle("بحث على الخريطة - اختر مبنى من الخريطة")
        dialog.resize(900, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title
        title = QLabel("🗺️ اضغط على علامة مبنى لاختياره")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2C3E50;
                padding: 8px;
                background-color: #E8F4F8;
                border-radius: 6px;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Map view
        if HAS_WEBENGINE:
            self._map_view = QWebEngineView(dialog)

            # Enable hardware acceleration
            settings = self._map_view.settings()
            settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

            # Setup WebChannel for JS-Python communication
            if HAS_WEBCHANNEL:
                self._setup_webchannel()

            layout.addWidget(self._map_view, stretch=1)
        else:
            placeholder = QLabel("🗺️ الخريطة غير متاحة (QtWebEngine غير مثبت)")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("padding: 40px; color: #999;")
            layout.addWidget(placeholder)

        # Close button
        close_btn = QPushButton("إغلاق")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dialog.reject)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #C0392B; }
        """)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        return dialog

    def _setup_webchannel(self):
        """Setup WebChannel for JavaScript-Python communication."""
        class MapBridge(QObject):
            """Bridge for map selection events."""

            def __init__(self, parent_widget):
                super().__init__()
                self.parent_widget = parent_widget

            @pyqtSlot(str)
            def selectBuilding(self, building_id: str):
                """Called from JavaScript when user selects a building."""
                self.parent_widget._on_building_selected_from_map(building_id)

        self._bridge = MapBridge(self)
        self._channel = QWebChannel(self._map_view.page())
        self._channel.registerObject('buildingBridge', self._bridge)
        self._map_view.page().setWebChannel(self._channel)

    def _parse_wkt_to_geojson(self, wkt: str) -> Optional[dict]:
        """
        تحويل WKT إلى GeoJSON.

        Args:
            wkt: WKT string (e.g., "POLYGON((lon lat, lon lat, ...))")

        Returns:
            GeoJSON geometry dict or None if invalid
        """
        try:
            wkt = wkt.strip().upper()

            if not wkt.startswith('POLYGON'):
                return None

            # Extract coordinates from WKT
            # Format: POLYGON((lon1 lat1, lon2 lat2, lon3 lat3, lon1 lat1))
            coords_str = wkt.replace('POLYGON', '').replace('((', '').replace('))', '').strip()

            # Split into coordinate pairs
            pairs = [p.strip() for p in coords_str.split(',')]

            # Convert to GeoJSON format [lon, lat]
            coordinates = []
            for pair in pairs:
                parts = pair.split()
                if len(parts) == 2:
                    try:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        coordinates.append([lon, lat])
                    except ValueError:
                        continue

            if len(coordinates) < 3:
                return None

            # GeoJSON polygon requires array of rings
            return {
                "type": "Polygon",
                "coordinates": [coordinates]
            }

        except Exception as e:
            logger.error(f"Failed to parse WKT: {e}")
            return None

    def _load_map(self):
        """Load the interactive map with building markers and polygons - استخدام LeafletHTMLGenerator الموحد."""
        if not self._map_view:
            return

        from services.tile_server_manager import get_tile_server_url
        from services.leaflet_html_generator import generate_leaflet_html
        import json

        tile_server_url = get_tile_server_url()
        if not tile_server_url.endswith('/'):
            tile_server_url += '/'

        base_url = QUrl(tile_server_url)

        # تحويل المباني إلى GeoJSON باستخدام نفس منطق map_page.py
        buildings = self.building_repo.get_all(limit=200)

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

        buildings_geojson = json.dumps({
            "type": "FeatureCollection",
            "features": features
        })

        # استخدام LeafletHTMLGenerator الموحد مع تفعيل زر الاختيار
        # الـ popup يفتح تلقائياً عند النقر، والزر داخل الـ popup
        html = generate_leaflet_html(
            tile_server_url=tile_server_url.rstrip('/'),
            buildings_geojson=buildings_geojson,
            center_lat=36.2021,
            center_lon=37.1343,
            zoom=13,
            show_legend=True,
            show_layer_control=False,
            enable_selection=True,
            enable_drawing=False
        )

        # LeafletHTMLGenerator يتعامل مع كل شيء - لا حاجة لإضافة JavaScript إضافي
        self._map_view.setHtml(html, base_url)


    def _on_building_selected_from_map(self, building_id: str):
        """Handle building selection from map."""
        logger.info(f"Building selected from map: {building_id}")

        # Find building in database
        building = self.building_repo.get_by_id(building_id)

        if building:
            self._selected_building = building
            self.building_selected.emit(building)

            # Close dialog
            if self._dialog:
                self._dialog.accept()
        else:
            logger.error(f"Building not found: {building_id}")
