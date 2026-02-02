# -*- coding: utf-8 -*-
"""
Base Map Dialog - Unified Dialog for All Map Operations.

Matches BuildingMapWidget design exactly - DRY principle.

Design Specifications (من BuildingMapWidget):
- Size: 1100×700px
- Border-radius: 32px
- Padding: 24px
- Title bar + optional search bar + map
- Map size: 1052×526px
- Clean, professional design
"""

from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QLineEdit, QFrame, QToolButton, QListWidget,
    QListWidgetItem, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, pyqtSlot, QUrl, QSize
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QIcon

from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
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


class RoundedDialog(QDialog):
    """Custom QDialog with rounded corners - من BuildingMapWidget."""

    def __init__(self, radius: int = 32, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.search_input = None

    def paintEvent(self, event):
        """Paint dialog with rounded corners."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.radius, self.radius)

        painter.fillPath(path, QColor(Colors.SURFACE))

    def keyPressEvent(self, event):
        """Override to prevent Enter from closing dialog."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.search_input and self.search_input.hasFocus():
                event.accept()
                self.search_input.returnPressed.emit()
                return

        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        super().keyPressEvent(event)


class MapBridge(QObject):
    """Bridge for JavaScript-Python communication."""

    geometry_drawn = pyqtSignal(str, str)  # (type, wkt)
    coordinates_update = pyqtSignal(float, float, int)  # (lat, lon, zoom)
    building_selected = pyqtSignal(str)  # building_id
    buildings_multiselected = pyqtSignal(str)  # JSON string of building IDs
    selection_count_updated = pyqtSignal(int)  # count

    @pyqtSlot(str, str)
    def onGeometryDrawn(self, geom_type: str, wkt: str):
        """Called from JavaScript when geometry is drawn."""
        logger.info(f"Geometry drawn: {geom_type} - {wkt[:100]}...")
        self.geometry_drawn.emit(geom_type, wkt)

    @pyqtSlot(float, float, int)
    def onCoordinatesUpdate(self, lat: float, lon: float, zoom: int):
        """Called from JavaScript when map moves."""
        self.coordinates_update.emit(lat, lon, zoom)

    @pyqtSlot(str)
    def selectBuilding(self, building_id: str):
        """Called from JavaScript when building is selected."""
        logger.info(f"Building selected: {building_id}")
        self.building_selected.emit(building_id)

    @pyqtSlot(str)
    def onBuildingsSelected(self, building_ids_json: str):
        """Called from JavaScript when buildings are selected in multi-select mode."""
        logger.info(f"Buildings selected: {building_ids_json}")
        self.buildings_multiselected.emit(building_ids_json)

    @pyqtSlot(int)
    def updateSelectionCount(self, count: int):
        """Called from JavaScript to update selection count."""
        self.selection_count_updated.emit(count)


class BaseMapDialog(QDialog):
    """
    Unified base dialog for all map operations.

    Matches BuildingMapWidget design exactly.

    Features:
    - Title bar with close button
    - Optional search bar
    - Map view with Leaflet
    - WebChannel for JavaScript communication
    - Gray overlay behind dialog
    - Multi-select support with counter and list

    Signals:
        geometry_selected(type, wkt): Geometry drawn on map
        building_selected(building_id): Building clicked on map
        coordinates_updated(lat, lon, zoom): Map moved
        buildings_multiselected(building_ids): List of building IDs selected
    """

    geometry_selected = pyqtSignal(str, str)
    building_selected = pyqtSignal(str)
    coordinates_updated = pyqtSignal(float, float, int)
    buildings_multiselected = pyqtSignal(list)  # List[str] of building IDs

    def __init__(
        self,
        title: str = "بحث على الخريطة",
        show_search: bool = True,
        show_confirm_button: bool = False,
        show_multiselect_ui: bool = False,
        parent=None
    ):
        """
        Initialize base map dialog.

        Args:
            title: Dialog title
            show_search: Show search bar
            show_confirm_button: Show confirm button and coordinates display
            show_multiselect_ui: Show multi-select UI (counter, list, clear button)
            parent: Parent widget
        """
        super().__init__(parent)

        self.dialog_title = title
        self.show_search = show_search
        self.show_confirm_button = show_confirm_button
        self.show_multiselect_ui = show_multiselect_ui
        self.web_view = None
        self._bridge = None
        self._overlay = None
        self._current_coordinates = None  # Store current selected coordinates
        self._selected_building_ids = []  # Store selected building IDs

        # Create overlay (gray transparent layer)
        if parent:
            self._overlay = self._create_overlay(parent)
            self._overlay.show()

        # Create UI
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI - matches BuildingMapWidget exactly."""
        # Window settings
        self.setModal(True)
        self.setWindowTitle(self.dialog_title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(1100, 700)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content container with 24px padding
        content = QWidget()
        # White background for content with rounded corners (32px to match dialog)
        content.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.SURFACE};
                border-radius: 32px;
            }}
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(12)

        # Title bar
        title_bar = self._create_title_bar()
        content_layout.addWidget(title_bar)

        # Search bar (optional)
        if self.show_search:
            search_bar = self._create_search_bar()
            content_layout.addWidget(search_bar)
            self.search_input = self.search_input  # Link for key handling

        # Multi-select UI (optional) - above map
        if self.show_multiselect_ui:
            multiselect_ui = self._create_multiselect_ui()
            content_layout.addWidget(multiselect_ui)

        # Map view
        if HAS_WEBENGINE:
            self.web_view = QWebEngineView(self)
            self.web_view.setFixedSize(1052, 526)

            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

            # Setup WebChannel
            if HAS_WEBCHANNEL:
                self._setup_webchannel()

            self.web_view.setStyleSheet("border-radius: 8px;")

            # Loading indicator
            self._loading_label = QLabel("⏳ جاري تحميل الخريطة...")
            self._loading_label.setFixedSize(1052, 526)
            self._loading_label.setAlignment(Qt.AlignCenter)
            self._loading_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            self._loading_label.setStyleSheet(f"""
                background-color: {Colors.BACKGROUND};
                color: {Colors.TEXT_SECONDARY};
                border-radius: 8px;
            """)

            # Stack widgets
            map_container = QWidget()
            map_layout = QVBoxLayout(map_container)
            map_layout.setContentsMargins(0, 0, 0, 0)
            map_layout.setSpacing(0)
            map_layout.addWidget(self._loading_label)
            map_layout.addWidget(self.web_view)
            self.web_view.hide()

            self.web_view.loadFinished.connect(self._on_map_loaded)
            content_layout.addWidget(map_container)
        else:
            placeholder = QLabel("🗺️ الخريطة غير متاحة (QtWebEngine غير مثبت)")
            placeholder.setFixedSize(1052, 526)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            placeholder.setStyleSheet(f"""
                background-color: {Colors.BACKGROUND};
                color: {Colors.TEXT_SECONDARY};
                border-radius: 8px;
            """)
            content_layout.addWidget(placeholder)

        # Confirm button area (optional)
        if self.show_confirm_button:
            confirm_area = self._create_confirm_area()
            content_layout.addWidget(confirm_area)

        main_layout.addWidget(content)

        # Center dialog
        self._center_dialog()

    def _create_title_bar(self) -> QWidget:
        """Create title bar with close button."""
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.setDirection(QHBoxLayout.RightToLeft)

        # Title
        title = QLabel(self.dialog_title)
        title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFont(create_font(size=14, weight=FontManager.WEIGHT_REGULAR))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.ERROR};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        close_btn.setDefault(False)
        close_btn.setAutoDefault(False)

        layout.addWidget(close_btn)

        return title_bar

    def _create_search_bar(self) -> QFrame:
        """Create search bar - matches BuildingMapWidget."""
        search_frame = QFrame()
        search_frame.setObjectName("searchBar")
        search_frame.setFixedHeight(42)
        search_frame.setStyleSheet(f"""
            QFrame#searchBar {{
                background-color: {Colors.SEARCH_BAR_BG};
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
            }}
        """)

        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(14, 8, 14, 8)
        search_layout.setSpacing(8)
        search_layout.setDirection(QHBoxLayout.RightToLeft)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("بحث عن اسم المنطقة (مثال: Al-Jamiliyah)")
        self.search_input.setAlignment(Qt.AlignRight)
        self.search_input.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {Colors.TEXT_PRIMARY};
                padding: 0px;
                text-align: right;
            }}
            QLineEdit::placeholder {{
                color: {Colors.TEXT_SECONDARY};
                text-align: right;
            }}
        """)

        # Connect search (subclass will implement)
        self.search_input.returnPressed.connect(self._on_search_submitted)

        search_layout.addWidget(self.search_input, 1)

        # Search icon
        search_icon = QLabel()
        search_icon.setFixedSize(20, 20)
        search_icon.setAlignment(Qt.AlignCenter)

        from ui.components.icon import Icon
        icon_pixmap = Icon.load_pixmap("search", size=16)
        if icon_pixmap and not icon_pixmap.isNull():
            search_icon.setPixmap(icon_pixmap)
        else:
            search_icon.setText("🔍")
            search_icon.setFont(create_font(size=10))

        search_icon.setStyleSheet("background: transparent;")
        search_layout.insertWidget(0, search_icon)

        return search_frame

    def _create_multiselect_ui(self) -> QFrame:
        """Create multi-select UI with counter, list, and clear button."""
        multiselect_frame = QFrame()
        multiselect_frame.setObjectName("multiselectUI")
        multiselect_frame.setStyleSheet(f"""
            QFrame#multiselectUI {{
                background-color: {Colors.LIGHT_GRAY_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        multiselect_layout = QHBoxLayout(multiselect_frame)
        multiselect_layout.setContentsMargins(12, 8, 12, 8)
        multiselect_layout.setSpacing(12)
        multiselect_layout.setDirection(QHBoxLayout.RightToLeft)

        # Counter label
        self.selection_counter_label = QLabel("0 مبنى محدد")
        self.selection_counter_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.selection_counter_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY_BLUE};
                background: transparent;
                padding: 4px 8px;
            }}
        """)
        multiselect_layout.addWidget(self.selection_counter_label)

        # Buildings list (compact, scrollable)
        self.buildings_list_widget = QListWidget()
        self.buildings_list_widget.setMaximumHeight(80)
        self.buildings_list_widget.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.buildings_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: white;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px;
                direction: rtl;
            }}
            QListWidget::item {{
                padding: 4px;
                border-bottom: 1px solid {Colors.BACKGROUND};
            }}
            QListWidget::item:hover {{
                background-color: {Colors.LIGHT_GRAY_BG};
            }}
        """)
        multiselect_layout.addWidget(self.buildings_list_widget, 1)

        # Clear all button
        self.clear_all_btn = QPushButton("🗑️ مسح الكل")
        self.clear_all_btn.setFixedSize(100, 32)
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        self.clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ERROR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
            QPushButton:disabled {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        self.clear_all_btn.setEnabled(False)
        self.clear_all_btn.clicked.connect(self._on_clear_all_clicked)
        multiselect_layout.addWidget(self.clear_all_btn)

        return multiselect_frame

    def _create_confirm_area(self) -> QWidget:
        """Create confirmation area with coordinates display and buttons."""
        confirm_container = QWidget()
        confirm_container.setStyleSheet("background: transparent;")
        confirm_layout = QVBoxLayout(confirm_container)
        confirm_layout.setContentsMargins(0, 8, 0, 0)
        confirm_layout.setSpacing(12)

        # Coordinates display
        self.coordinates_display = QLabel("📍 الإحداثيات: لم يتم التحديد")
        self.coordinates_display.setAlignment(Qt.AlignCenter)
        self.coordinates_display.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self.coordinates_display.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 10px 16px;
            }}
        """)
        confirm_layout.addWidget(self.coordinates_display)

        # Buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)
        buttons_row.addStretch()

        # Cancel button
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BACKGROUND};
                border-color: {Colors.TEXT_SECONDARY};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_btn)

        # Confirm button
        self.confirm_btn = QPushButton("✓ تأكيد الإحداثيات")
        self.confirm_btn.setFixedSize(160, 40)
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
            QPushButton:disabled {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        self.confirm_btn.setEnabled(False)  # Disabled until coordinates selected
        self.confirm_btn.clicked.connect(self.accept)
        buttons_row.addWidget(self.confirm_btn)

        buttons_row.addStretch()
        confirm_layout.addLayout(buttons_row)

        return confirm_container

    def _setup_webchannel(self):
        """Setup WebChannel for JavaScript communication."""
        self._bridge = MapBridge()
        self._bridge.geometry_drawn.connect(self._on_geometry_drawn)
        self._bridge.coordinates_update.connect(self._on_coordinates_update)
        self._bridge.building_selected.connect(self._on_building_selected)
        self._bridge.buildings_multiselected.connect(self._on_buildings_multiselected)
        self._bridge.selection_count_updated.connect(self._on_selection_count_updated)

        channel = QWebChannel(self.web_view.page())
        # Register as 'buildingBridge' to match LeafletHTMLGenerator JavaScript
        channel.registerObject('buildingBridge', self._bridge)
        self.web_view.page().setWebChannel(channel)

    def _create_overlay(self, parent: QWidget) -> QWidget:
        """
        Create gray transparent overlay covering the entire application window.

        From BuildingMapWidget - exact match.

        Args:
            parent: Parent widget to find top-level window

        Returns:
            Overlay widget covering entire window
        """
        # Find the top-level window (MainWindow)
        top_window = parent.window()

        # Create overlay on top-level window to cover entire app
        overlay = QWidget(top_window)
        overlay.setGeometry(0, 0, top_window.width(), top_window.height())
        overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(45, 45, 45, 0.6);
            }
        """)
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        overlay.raise_()  # Bring to front
        return overlay

    def _center_dialog(self):
        """Center dialog on screen."""
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _on_map_loaded(self, success: bool):
        """Called when map finishes loading."""
        if success:
            logger.info("Map loaded successfully")
            if hasattr(self, '_loading_label'):
                self._loading_label.hide()
            if self.web_view:
                self.web_view.show()
        else:
            logger.error("Map failed to load")
            if hasattr(self, '_loading_label'):
                self._loading_label.setText("❌ فشل تحميل الخريطة")
                self._loading_label.setStyleSheet(f"""
                    background-color: {Colors.BACKGROUND};
                    color: {Colors.ERROR};
                    border-radius: 8px;
                """)

    def _on_geometry_drawn(self, geom_type: str, wkt: str):
        """Handle geometry drawn - emit signal."""
        # Update coordinates display if enabled
        if self.show_confirm_button:
            self._update_coordinates_display(geom_type, wkt)

        self.geometry_selected.emit(geom_type, wkt)

    def _on_coordinates_update(self, lat: float, lon: float, zoom: int):
        """Handle coordinates update - emit signal."""
        self.coordinates_updated.emit(lat, lon, zoom)

    def _on_building_selected(self, building_id: str):
        """Handle building selected - emit signal."""
        self.building_selected.emit(building_id)

    def _on_buildings_multiselected(self, building_ids_json: str):
        """Handle buildings multi-selected - parse JSON and emit signal."""
        import json
        try:
            building_ids = json.loads(building_ids_json)
            self._selected_building_ids = building_ids
            self._update_buildings_list(building_ids)
            self.buildings_multiselected.emit(building_ids)
            logger.info(f"Multi-selected {len(building_ids)} buildings")
        except Exception as e:
            logger.error(f"Error parsing building IDs: {e}")

    def _on_selection_count_updated(self, count: int):
        """Handle selection count update from JavaScript."""
        if hasattr(self, 'selection_counter_label'):
            if count == 0:
                self.selection_counter_label.setText("0 مبنى محدد")
                self.clear_all_btn.setEnabled(False)
            elif count == 1:
                self.selection_counter_label.setText("مبنى واحد محدد")
                self.clear_all_btn.setEnabled(True)
            elif count == 2:
                self.selection_counter_label.setText("مبنيان محددان")
                self.clear_all_btn.setEnabled(True)
            elif count <= 10:
                self.selection_counter_label.setText(f"{count} مباني محددة")
                self.clear_all_btn.setEnabled(True)
            else:
                self.selection_counter_label.setText(f"{count} مبنى محدد")
                self.clear_all_btn.setEnabled(True)

    def _update_buildings_list(self, building_ids: List[str]):
        """Update the buildings list widget with selected building IDs."""
        if not hasattr(self, 'buildings_list_widget'):
            return

        self.buildings_list_widget.clear()
        for building_id in building_ids:
            item = QListWidgetItem(f"🏢 {building_id}")
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.buildings_list_widget.addItem(item)

    def _on_clear_all_clicked(self):
        """Handle clear all button click - call JavaScript to clear selections."""
        if self.web_view:
            self.web_view.page().runJavaScript("if (typeof clearAllSelections === 'function') { clearAllSelections(); }")
            logger.info("Cleared all selections")

    def _on_search_submitted(self):
        """Handle search submission - subclass should override."""
        pass

    def _update_coordinates_display(self, geom_type: str, wkt: str):
        """
        Update coordinates display with selected location.

        Args:
            geom_type: Geometry type ('Point' or 'Polygon')
            wkt: WKT string
        """
        try:
            if geom_type == 'Point':
                # Parse: POINT(lon lat)
                coords = wkt.replace('POINT(', '').replace(')', '').strip()
                lon_str, lat_str = coords.split()
                lat = float(lat_str)
                lon = float(lon_str)

                self._current_coordinates = {'latitude': lat, 'longitude': lon, 'type': 'Point'}

                self.coordinates_display.setText(
                    f"📍 الإحداثيات: {lat:.6f}°, {lon:.6f}°"
                )
                self.confirm_btn.setEnabled(True)
                logger.info(f"Coordinates updated: Point ({lat}, {lon})")

            elif geom_type == 'Polygon':
                # Parse polygon to get centroid
                coords_str = wkt.replace('POLYGON((', '').replace('))', '').strip()
                pairs = coords_str.split(',')

                lats, lons = [], []
                for pair in pairs:
                    parts = pair.strip().split()
                    if len(parts) == 2:
                        lons.append(float(parts[0]))
                        lats.append(float(parts[1]))

                if lats and lons:
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)

                    self._current_coordinates = {
                        'latitude': center_lat,
                        'longitude': center_lon,
                        'type': 'Polygon',
                        'wkt': wkt
                    }

                    self.coordinates_display.setText(
                        f"⬡ المضلع: المركز ({center_lat:.6f}°, {center_lon:.6f}°) - {len(lats)} نقاط"
                    )
                    self.confirm_btn.setEnabled(True)
                    logger.info(f"Coordinates updated: Polygon centroid ({center_lat}, {center_lon})")

        except Exception as e:
            logger.error(f"Error updating coordinates display: {e}", exc_info=True)

    def get_selected_building_ids(self) -> List[str]:
        """
        Get list of selected building IDs from multi-select mode.

        Returns:
            List of building IDs
        """
        return self._selected_building_ids.copy()

    def load_map_html(self, html: str):
        """
        Load map HTML into web view.

        Args:
            html: Complete HTML string
        """
        if not self.web_view:
            logger.warning("WebView not available")
            return

        from services.tile_server_manager import get_tile_server_url
        tile_server_url = get_tile_server_url()
        base_url = QUrl(tile_server_url)

        self.web_view.setHtml(html, base_url)
        logger.info("Map HTML loaded")

    @staticmethod
    def load_buildings_geojson(db, limit: int = 200, auth_token: Optional[str] = None) -> str:
        """
        Load buildings from API/database and convert to GeoJSON.

        SINGLE SOURCE OF TRUTH for building loading (DRY principle).
        Uses BuildingController which automatically selects API or local DB.

        Args:
            db: Database instance
            limit: Maximum number of buildings to load
            auth_token: Optional authentication token for API calls

        Returns:
            GeoJSON string with buildings
        """
        from controllers.building_controller import BuildingController
        from services.geojson_converter import GeoJSONConverter
        import json

        try:
            # Use BuildingController (DRY + SOLID) - automatically selects API or DB
            building_controller = BuildingController(db)

            # Set auth token if provided (required for API calls)
            if auth_token and building_controller.is_using_api:
                building_controller.set_auth_token(auth_token)
                logger.debug(f"Auth token set for BuildingController (length: {len(auth_token)})")

            result = building_controller.load_buildings()

            if not result.success:
                logger.error(f"Failed to load buildings: {result.message}")
                buildings = []
            else:
                buildings = result.data[:limit]  # Apply limit after fetching

            logger.info(f"📊 Retrieved {len(buildings)} buildings from database")

            # Log diagnostics
            buildings_with_coords = [b for b in buildings if b.latitude and b.longitude]
            buildings_with_polygons = [b for b in buildings if b.geo_location]
            logger.info(f"  - Buildings with lat/lon: {len(buildings_with_coords)}")
            logger.info(f"  - Buildings with polygons: {len(buildings_with_polygons)}")

            # Convert to GeoJSON
            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                buildings,
                prefer_polygons=True
            )

            # Validate
            geojson_data = json.loads(buildings_geojson)
            feature_count = len(geojson_data.get('features', []))
            logger.info(f"  - GeoJSON features: {feature_count}")

            if feature_count == 0:
                logger.warning("⚠️ No buildings with valid geometry!")
            else:
                logger.info(f"✅ GeoJSON generated successfully with {feature_count} features")

            return buildings_geojson

        except Exception as e:
            logger.error(f"Error loading buildings: {e}", exc_info=True)
            # Return empty GeoJSON on error
            return '{"type":"FeatureCollection","features":[]}'

    def _cleanup_overlay(self):
        """Remove overlay from screen."""
        if self._overlay:
            try:
                self._overlay.hide()
                self._overlay.setParent(None)  # Detach from parent first
                self._overlay.close()  # Close explicitly
                self._overlay.deleteLater()
                self._overlay = None
                logger.debug("Overlay cleaned up successfully")
            except Exception as e:
                logger.warning(f"Error cleaning up overlay: {e}")
                self._overlay = None

    def accept(self):
        """Override accept to clean up overlay."""
        try:
            self._cleanup_overlay()
        finally:
            super().accept()

    def reject(self):
        """Override reject to clean up overlay."""
        try:
            self._cleanup_overlay()
        finally:
            super().reject()

    def closeEvent(self, event):
        """Clean up overlay when dialog closes."""
        try:
            self._cleanup_overlay()
        finally:
            super().closeEvent(event)
