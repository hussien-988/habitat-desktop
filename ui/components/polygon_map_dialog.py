    # -*- coding: utf-8 -*-
"""
    Polygon Map Dialog - Dialog لاختيار المباني برسم مضلع على الخريطة.

    يستخدم نفس التصميم الحديث من MapPickerDialog مع إضافة وظيفة:
    - رسم مضلع لتحديد المباني
    - استعلام المباني داخل المضلع
    - إرجاع قائمة المباني المختارة

    Best Practices:
    - نفس التصميم: Radio buttons + Orange instruction + Bottom buttons
    - DRY: يعيد استخدام MapBridge و LeafletHTMLGenerator
    - SOLID: مسؤولية واحدة - اختيار المباني بالمضلع
"""

from typing import List, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QGroupBox, QRadioButton,
    QButtonGroup
    )
from ui.error_handler import ErrorHandler
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWebChannel import QWebChannel

from repositories.database import Database
from models.building import Building
from app.config import Config
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class DebugWebPage(QWebEnginePage):
    """Custom QWebEnginePage that logs console messages."""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Log JavaScript console messages."""
        logger.info(f"JS [{level}]: {message} (line {lineNumber})")


class BuildingSelectionBridge(QObject):
    """
    Bridge object for communication between Python and JavaScript.

    Extends MapBridge functionality for building selection within polygon.
    """

    polygon_drawn = pyqtSignal(str)  # WKT string
    buildings_selected = pyqtSignal(list)  # List of building IDs

    def __init__(self, parent=None):
        super().__init__(parent)
        self._polygon_wkt = None

    @pyqtSlot(str)
    def geometryDrawn(self, geojson_str: str):
        """
        Called from Leaflet.draw when a polygon is drawn.
        Converts GeoJSON to WKT and emits signal.
        """
        import json
        logger.info(f"Geometry drawn: {geojson_str[:100]}...")

        try:
            geom = json.loads(geojson_str)
            geom_type = geom.get('type')
            coords = geom.get('coordinates')

            if geom_type == 'Polygon':
                # Polygon: coordinates = [[[lon, lat], [lon, lat], ...]]
                ring = coords[0]
                wkt_coords = ', '.join([f"{lon} {lat}" for lon, lat in ring])
                wkt = f"POLYGON(({wkt_coords}))"
                self._polygon_wkt = wkt
                logger.info(f"Polygon WKT: {wkt[:100]}...")
                self.polygon_drawn.emit(wkt)
            else:
                logger.warning(f"Unsupported geometry type for building selection: {geom_type}")

        except Exception as e:
            logger.error(f"Failed to parse drawn geometry: {e}")


class PolygonMapDialog(QDialog):
    """
    Dialog لاختيار المباني برسم مضلع على الخريطة.

    Uses the same modern design as MapPickerDialog:
    - Radio buttons for Point/Polygon mode
    - Orange instruction label
    - Bottom buttons (مسح، إلغاء، تأكيد الاختيار)
    - Coordinate display

    Returns:
        List[Building]: المباني المختارة داخل المضلع
    """

    def __init__(self, db: Database, buildings: List[Building], parent=None):
        """
        Initialize the polygon map dialog.

        Args:
            db: Database instance
            buildings: List of all buildings to display on map
            parent: Parent widget
        """
        super().__init__(parent)
        self.db = db
        self.buildings = buildings
        self._selected_buildings = []

        self.setWindowTitle("اختيار المباني - رسم مضلع")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)

        self._setup_ui()
        self._load_map()

    def _get_tile_server_url(self):
        """Get tile server URL from centralized manager."""
        from services.tile_server_manager import get_tile_server_url
        return get_tile_server_url()

    def _get_buildings_geojson(self):
        """Get all buildings as GeoJSON for map display."""
        import json
        from services.geojson_converter import GeoJSONConverter

        try:
            return GeoJSONConverter.buildings_to_geojson(
                self.buildings,
                prefer_polygons=True
            )
        except Exception as e:
            logger.error(f"Failed to convert buildings to GeoJSON: {e}")
            return '{"type": "FeatureCollection", "features": []}'

    def _setup_ui(self):
        """Setup the UI - نفس تصميم MapPickerDialog."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Instructions
        instructions = QLabel(
            "استخدم أدوات الرسم لتحديد مضلع على الخريطة. سيتم اختيار جميع المباني داخل المضلع تلقائياً."
        )
        instructions.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: 10pt;
            padding: 8px;
            background-color: #F8FAFC;
            border-radius: 4px;
        """)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Mode selection with orange instruction
        mode_group = QGroupBox("نوع التحديد")
        mode_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        mode_layout = QVBoxLayout(mode_group)

        # Instruction label (Polygon mode only)
        self.mode_instruction = QLabel("👉 اضغط على أيقونة المضلع في الصندوق الأبيض يسار الخريطة، ثم ارسم مضلعاً حول المباني")
        self.mode_instruction.setStyleSheet("""
            color: #e67e22;
            font-size: 12px;
            font-weight: 600;
            padding: 10px;
            background-color: rgba(230, 126, 34, 0.1);
            border-radius: 6px;
            border-left: 3px solid #e67e22;
        """)
        self.mode_instruction.setWordWrap(True)
        mode_layout.addWidget(self.mode_instruction)

        layout.addWidget(mode_group)

        # Map container
        map_container = QFrame()
        map_container.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                background-color: #F8FAFC;
            }}
        """)
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(2, 2, 2, 2)

        # Web view for map with custom page for debugging
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(450)

        # Create profile with cache disabled
        profile = QWebEngineProfile(self.web_view)
        profile.setHttpCacheType(QWebEngineProfile.NoCache)

        # Set custom page
        debug_page = DebugWebPage(profile, self.web_view)
        self.web_view.setPage(debug_page)

        # Enable hardware acceleration
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

        map_layout.addWidget(self.web_view)

        # Setup web channel for JS-Python communication
        self.bridge = BuildingSelectionBridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.bridge.polygon_drawn.connect(self._on_polygon_drawn)

        layout.addWidget(map_container)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"""
            color: {Colors.SUCCESS};
            font-size: 12px;
            font-weight: 600;
            padding: 8px;
            background-color: rgba(34, 197, 94, 0.1);
            border-radius: 4px;
            border-left: 3px solid {Colors.SUCCESS};
        """)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Buttons (same as MapPickerDialog)
        btn_layout = QHBoxLayout()
        btn_layout.setDirection(QHBoxLayout.RightToLeft)
        btn_layout.addStretch()

        # Clear button
        clear_btn = QPushButton("مسح")
        clear_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BACKGROUND};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 10px 24px;
            }}
            QPushButton:hover {{
                background-color: {Colors.SURFACE};
            }}
        """)
        clear_btn.clicked.connect(self._clear_selection)
        btn_layout.addWidget(clear_btn)

        # Cancel button
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BACKGROUND};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 10px 24px;
            }}
            QPushButton:hover {{
                background-color: {Colors.SURFACE};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        # Confirm button
        self.confirm_btn = QPushButton("تأكيد الاختيار")
        self.confirm_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.confirm_btn.setEnabled(False)  # Disabled until polygon is drawn
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SUCCESS};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
            }}
            QPushButton:hover {{
                background-color: #16A34A;
            }}
            QPushButton:disabled {{
                background-color: {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

    def _load_map(self, drawing_mode: str = 'polygon'):
        """Load the Leaflet map with drawing tools."""
        html = self._generate_map_html(drawing_mode=drawing_mode)
        tile_server_url = self._get_tile_server_url()
        base_url = QUrl(tile_server_url)
        self.web_view.setHtml(html, base_url)

    def _generate_map_html(self, drawing_mode: str = 'polygon') -> str:
        """Generate HTML for the Leaflet map using unified generator."""
        tile_server_url = self._get_tile_server_url()
        buildings_geojson = self._get_buildings_geojson()

        # استخدام LeafletHTMLGenerator الموحد
        from services.leaflet_html_generator import generate_leaflet_html

        html = generate_leaflet_html(
            tile_server_url=tile_server_url,
            buildings_geojson=buildings_geojson,
            center_lat=36.2021,
            center_lon=37.1343,
            zoom=15,  #
            show_legend=True,
            show_layer_control=False,
            enable_selection=False,
            enable_drawing=True,
            drawing_mode=drawing_mode
        )

        return html

    def _on_mode_changed(self, button):
        """Handle mode change (Polygon only)."""
        # Always polygon mode
        drawing_mode = 'polygon'
        logger.info("Drawing mode: Polygon")

        # Reload map with polygon mode
        self._load_map(drawing_mode=drawing_mode)

    def _on_polygon_drawn(self, wkt: str):
        """
        Handle polygon drawn event.
        Query buildings within the polygon and show confirmation.
        """
        logger.info(f"Polygon drawn: {wkt[:100]}...")

        # Query buildings within polygon
        try:
            self._selected_buildings = self._query_buildings_in_polygon(wkt)

            if self._selected_buildings:
                count = len(self._selected_buildings)
                self.status_label.setText(f"✓ تم العثور على {count} مبنى داخل المضلع")
                self.status_label.setVisible(True)
                self.confirm_btn.setEnabled(True)
                logger.info(f"Found {count} buildings in polygon")
            else:
                self.status_label.setText("⚠ المضلع المرسوم لا يحتوي على أي مباني")
                self.status_label.setStyleSheet(f"""
                    color: #f59e0b;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 8px;
                    background-color: rgba(245, 158, 11, 0.1);
                    border-radius: 4px;
                    border-left: 3px solid #f59e0b;
                """)
                self.status_label.setVisible(True)
                self.confirm_btn.setEnabled(False)
                logger.warning("No buildings found in polygon")

        except Exception as e:
            logger.error(f"Error querying buildings in polygon: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"حدث خطأ أثناء البحث عن المباني:\n{str(e)}",
                "خطأ"
            )

    def _query_buildings_in_polygon(self, polygon_wkt: str) -> List[Building]:
        """
        Query buildings that are within the drawn polygon.

        Args:
            polygon_wkt: WKT string of the polygon

        Returns:
            List of buildings within the polygon
        """
        from services.map_service import MapService

        map_service = MapService()
        buildings_in_polygon = []

        for building in self.buildings:
            # Check if building has location
            if not building.latitude or not building.longitude:
                continue

            # Check if building point is within polygon
            try:
                is_inside = map_service.is_point_in_polygon(
                    building.latitude,
                    building.longitude,
                    polygon_wkt
                )

                if is_inside:
                    buildings_in_polygon.append(building)

            except Exception as e:
                logger.warning(f"Error checking building {building.building_id}: {e}")
                continue

        return buildings_in_polygon

    def _clear_selection(self):
        """Clear the current selection and reload map."""
        self._selected_buildings = []
        self.status_label.setVisible(False)
        self.confirm_btn.setEnabled(False)

        # Reload map to clear drawn shapes (Polygon only)
        self._load_map(drawing_mode='polygon')

        logger.info("Selection cleared")

    def _on_confirm(self):
        """Confirm the selection and close dialog."""
        if not self._selected_buildings:
            ErrorHandler.show_warning(
                self,
                "لم يتم تحديد أي مباني. يرجى رسم مضلع يحتوي على مباني.",
                "تنبيه"
            )
            return

        logger.info(f"Confirming selection of {len(self._selected_buildings)} buildings")
        self.accept()

    def get_selected_buildings(self) -> List[Building]:
        """
        Get the list of selected buildings.

        Returns:
            List of buildings within the drawn polygon
        """
        return self._selected_buildings


def show_polygon_map_dialog(
    db: Database,
    buildings: List[Building],
    parent=None
    ) -> Optional[List[Building]]:
    """
    Convenience function to show polygon map dialog and get selected buildings.

    Args:
        db: Database instance
        buildings: List of all buildings to display on map
        parent: Parent widget

    Returns:
        List of selected buildings, or None if cancelled
    """
    dialog = PolygonMapDialog(db, buildings, parent)
    result = dialog.exec_()

    if result == QDialog.Accepted:
        return dialog.get_selected_buildings()

    return None
