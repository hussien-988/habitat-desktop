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
from services.viewport_map_loader import ViewportMapLoader
from services.building_cache_service import get_building_cache

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
    viewport_changed = pyqtSignal(float, float, float, float, int)  # (ne_lat, ne_lng, sw_lat, sw_lng, zoom)
    bridge_ready = pyqtSignal()  # Emitted when QWebChannel bridge is fully initialized

    @pyqtSlot(str, str)
    def onGeometryDrawn(self, geom_type: str, wkt: str):
        """Called from JavaScript when geometry is drawn."""
        logger.info(f"🎨 MapBridge.onGeometryDrawn called from JavaScript!")
        logger.info(f"   geom_type: {geom_type}")
        logger.info(f"   wkt: {wkt[:100] if wkt else 'None'}...")
        self.geometry_drawn.emit(geom_type, wkt)
        logger.info(f"   ✅ geometry_drawn signal emitted")

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

    @pyqtSlot(float, float, float, float, int, float, float)
    def onViewportChanged(self, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float, zoom: int, center_lat: float, center_lng: float):
        """
        Called from JavaScript when map viewport changes (pan/zoom).

        Args:
            ne_lat: North-East latitude
            ne_lng: North-East longitude
            sw_lat: South-West latitude
            sw_lng: South-West longitude
            zoom: Current zoom level
            center_lat: Map center latitude
            center_lng: Map center longitude
        """
        logger.debug(f"Viewport changed: NE({ne_lat:.6f}, {ne_lng:.6f}), SW({sw_lat:.6f}, {sw_lng:.6f}), Center({center_lat:.6f}, {center_lng:.6f}), Zoom={zoom}")
        self.viewport_changed.emit(ne_lat, ne_lng, sw_lat, sw_lng, zoom)

    @pyqtSlot()
    def onBridgeReady(self):
        """Called from JavaScript when QWebChannel bridge is fully initialized and ready."""
        logger.info("✅ QWebChannel bridge confirmed ready by JavaScript")
        self.bridge_ready.emit()


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
        enable_viewport_loading: bool = False,
        parent=None
    ):
        """
        Initialize base map dialog.

        Args:
            title: Dialog title
            show_search: Show search bar
            show_confirm_button: Show confirm button and coordinates display
            show_multiselect_ui: Show multi-select UI (counter, list, clear button)
            enable_viewport_loading: Enable viewport-based loading for millions of buildings
            parent: Parent widget
        """
        super().__init__(parent)

        self.dialog_title = title
        self.show_search = show_search
        self.show_confirm_button = show_confirm_button
        self.show_multiselect_ui = show_multiselect_ui
        self.enable_viewport_loading = enable_viewport_loading
        self.web_view = None
        self._bridge = None
        self._overlay = None
        self._current_coordinates = None  # Store current selected coordinates
        self._selected_building_ids = []  # Store selected building IDs
        self._viewport_loader = None  # ViewportMapLoader instance
        self._auth_token = None  # ✅ Store auth token for API calls (set by subclass)

        # Initialize viewport loader if enabled (Best Practice: with cache + spatial sampling)
        if self.enable_viewport_loading:
            # Get application-wide cache service (Singleton)
            # NOTE: BuildingCacheService disabled for now - Database.get_instance() not available
            # TODO: Pass db instance from parent to enable caching
            building_cache = None

            self._viewport_loader = ViewportMapLoader(
                cache_enabled=True,
                cache_max_size=50,
                cache_max_age_minutes=10,
                building_cache_service=building_cache,  # Disabled - needs db instance
                use_spatial_sampling=True  # Grid-based sampling (Best Practice!)
            )
            logger.info("✅ Viewport loading enabled (cache disabled - needs db instance)")

        # ✅ UNIFIED: Get auth token if not provided (DRY principle)
        if not self._auth_token and parent:
            self._auth_token = self._get_auth_token_from_parent(parent)

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
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)

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

        # Connect viewport changed signal if viewport loading enabled
        if self.enable_viewport_loading:
            self._bridge.viewport_changed.connect(self._on_viewport_changed)
            logger.debug("Viewport changed signal connected")

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
        """Called when map finishes loading - WAIT for QWebChannel bridge ready."""
        if success:
            logger.info("✅ Map HTML loaded - checking QWebChannel bridge status...")

            # Check if QWebChannel is ready using proper async check
            # Reference: https://doc.qt.io/qt-6/qtwebchannel-javascript.html
            check_js = """
            console.log('🔍 Checking QWebChannel bridge after map load...');
            console.log('  - qt:', typeof qt);
            console.log('  - qt.webChannelTransport:', typeof qt !== 'undefined' ? typeof qt.webChannelTransport : 'N/A');
            console.log('  - QWebChannel:', typeof QWebChannel);
            console.log('  - bridge:', typeof bridge);
            console.log('  - bridgeReady:', typeof bridgeReady !== 'undefined' ? bridgeReady : 'undefined');

            // The bridge should be initializing now via QWebChannel callback
            // We just log status - the callback in leaflet_html_generator will notify Python
            """
            self.web_view.page().runJavaScript(check_js)

            # Show map immediately (hide loading indicator)
            if hasattr(self, '_loading_label'):
                self._loading_label.hide()
            if self.web_view:
                self.web_view.show()
        else:
            logger.error("❌ Map failed to load")
            if hasattr(self, '_loading_label'):
                self._loading_label.setText("❌ فشل تحميل الخريطة")
                self._loading_label.setStyleSheet(f"""
                    background-color: {Colors.BACKGROUND};
                    color: {Colors.ERROR};
                    border-radius: 8px;
                """)

    def _on_geometry_drawn(self, geom_type: str, wkt: str):
        """Handle geometry drawn - emit signal."""
        logger.info(f"📍 BaseMapDialog._on_geometry_drawn called")
        logger.info(f"   geom_type: {geom_type}")
        logger.info(f"   wkt: {wkt[:100] if wkt else 'None'}...")

        # Update coordinates display if enabled
        if self.show_confirm_button:
            self._update_coordinates_display(geom_type, wkt)

        logger.info(f"   Emitting geometry_selected signal...")
        self.geometry_selected.emit(geom_type, wkt)
        logger.info(f"   ✅ geometry_selected signal emitted")

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

    def _on_viewport_changed(self, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float, zoom: int):
        """
        Handle viewport changed event from JavaScript.

        Loads buildings for the new viewport and updates the map.

        Args:
            ne_lat: North-East latitude
            ne_lng: North-East longitude
            sw_lat: South-West latitude
            sw_lng: South-West longitude
            zoom: Current zoom level
        """
        if not self._viewport_loader:
            return

        try:
            # ✅ FIX: Use stored auth token first, fallback to parent
            auth_token = self._auth_token

            # Fallback: Get auth token from parent if not set
            if not auth_token:
                try:
                    if self.parent():
                        main_window = self.parent()
                        while main_window and not hasattr(main_window, 'current_user'):
                            main_window = main_window.parent()
                        if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                            auth_token = getattr(main_window.current_user, '_api_token', None)
                except Exception as e:
                    logger.debug(f"Could not get auth token from parent: {e}")

            if auth_token:
                logger.debug("✅ Using auth token for viewport loading")
            else:
                logger.warning("⚠️ No auth token available for viewport loading")

            # Load buildings for viewport (with cache + spatial sampling)
            buildings = self._viewport_loader.load_buildings_for_viewport(
                north_east_lat=ne_lat,
                north_east_lng=ne_lng,
                south_west_lat=sw_lat,
                south_west_lng=sw_lng,
                zoom_level=zoom,
                auth_token=auth_token
            )

            # Convert to GeoJSON
            from services.geojson_converter import GeoJSONConverter
            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                buildings,
                prefer_polygons=True
            )

            # Update map via JavaScript
            self._update_map_buildings(buildings_geojson)

        except Exception as e:
            logger.error(f"Error loading viewport buildings: {e}", exc_info=True)

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

    def _update_map_buildings(self, buildings_geojson: str):
        """
        Update buildings on map dynamically via JavaScript.

        Args:
            buildings_geojson: GeoJSON string with new buildings
        """
        if not self.web_view:
            logger.warning("WebView not available for updating buildings")
            return

        try:
            import json

            # Parse and re-stringify to ensure valid JSON
            geojson_obj = json.loads(buildings_geojson)

            # Direct JSON injection (no escaping needed - json.dumps produces valid JavaScript)
            # This is the same approach used in initial map load (leaflet_html_generator.py:439)
            geojson_json = json.dumps(geojson_obj)

            # Call JavaScript function to update buildings
            js_code = f"if (typeof updateBuildingsOnMap === 'function') {{ updateBuildingsOnMap({geojson_json}); }}"

            self.web_view.page().runJavaScript(js_code)

        except Exception as e:
            logger.error(f"Error updating map buildings: {e}", exc_info=True)

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
        from controllers.building_controller import BuildingController, BuildingFilter
        from services.geojson_converter import GeoJSONConverter
        import json

        try:
            # Use BuildingController (DRY + SOLID) - automatically selects API or local DB
            building_controller = BuildingController(db)

            # CRITICAL FIX: Set auth token BEFORE any operations!
            logger.info(f"🔍 load_buildings_geojson: auth_token={bool(auth_token)}, is_using_api={building_controller.is_using_api}")
            if auth_token and building_controller.is_using_api:
                building_controller.set_auth_token(auth_token)
                logger.info(f"✅ Auth token set for BuildingController (token length: {len(auth_token)})")
            elif not auth_token:
                logger.error(f"❌ NO AUTH TOKEN provided to load_buildings_geojson!")
            elif not building_controller.is_using_api:
                logger.info(f"ℹ️ BuildingController using local DB (auth token not needed)")

            # PROFESSIONAL FIX: Pass limit to API via BuildingFilter (no over-fetching!)
            building_filter = BuildingFilter(limit=limit)
            result = building_controller.load_buildings(building_filter)

            if not result.success:
                logger.error(f"Failed to load buildings: {result.message}")
                buildings = []
            else:
                buildings = result.data
                logger.info(f"✅ Loaded {len(buildings)} buildings from {'API' if building_controller.is_using_api else 'DB'}")

            # Convert to GeoJSON
            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                buildings,
                prefer_polygons=True
            )

            return buildings_geojson

        except Exception as e:
            logger.error(f"Error loading buildings: {e}", exc_info=True)
            # Return empty GeoJSON on error
            return '{"type":"FeatureCollection","features":[]}'

    def _get_auth_token_from_parent(self, parent) -> Optional[str]:
        """
        Get auth token from parent window (MainWindow.current_user).

        ✅ DRY: Single source of truth for auth_token retrieval (Best Practice).

        Args:
            parent: Parent widget

        Returns:
            Auth token string or None
        """
        if not parent:
            return None

        try:
            main_window = parent
            while main_window and not hasattr(main_window, 'current_user'):
                main_window = main_window.parent()

            if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                token = getattr(main_window.current_user, '_api_token', None)
                if token:
                    logger.debug(f"✅ Auth token retrieved from MainWindow (length: {len(token)})")
                return token
        except Exception as e:
            logger.warning(f"Could not get auth token from parent: {e}")

        return None

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
