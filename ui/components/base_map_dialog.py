# -*- coding: utf-8 -*-
"""Base Map Dialog - unified dialog for all map operations."""

from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QLineEdit, QFrame, QToolButton,
    QScrollArea, QSizePolicy
    )
from PyQt5.QtCore import Qt, pyqtSignal, QObject, pyqtSlot, QUrl, QThread
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPalette

from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger
from services.viewport_map_loader import ViewportMapLoader
from services.building_cache_service import get_building_cache
from services.translation_manager import tr

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
    """Custom QDialog with rounded corners."""

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
        logger.info(f"MapBridge.onGeometryDrawn called from JavaScript!")
        logger.info(f"   geom_type: {geom_type}")
        logger.info(f"   wkt: {wkt[:100] if wkt else 'None'}...")
        self.geometry_drawn.emit(geom_type, wkt)
        logger.info(f"geometry_drawn signal emitted")

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
        logger.info("QWebChannel bridge confirmed ready by JavaScript")
        self.bridge_ready.emit()


class _ViewportWorker(QThread):
    """Background worker for loading buildings in viewport without blocking UI."""
    finished = pyqtSignal(str)  # GeoJSON string
    buildings_loaded = pyqtSignal(list)  # Building objects for cache

    def __init__(self, viewport_loader, bounds, zoom, auth_token):
        super().__init__()
        self._viewport_loader = viewport_loader
        self._bounds = bounds  # (ne_lat, ne_lng, sw_lat, sw_lng)
        self._zoom = zoom
        self._auth_token = auth_token

    def run(self):
        try:
            buildings = self._viewport_loader.load_buildings_for_viewport(
                north_east_lat=self._bounds[0],
                north_east_lng=self._bounds[1],
                south_west_lat=self._bounds[2],
                south_west_lng=self._bounds[3],
                zoom_level=self._zoom,
                auth_token=self._auth_token
            )
            if self.isInterruptionRequested():
                return
            from services.geojson_converter import GeoJSONConverter
            geojson = GeoJSONConverter.buildings_to_geojson(
                buildings, force_points=True
            )
            if self.isInterruptionRequested():
                return
            self.buildings_loaded.emit(buildings)
            self.finished.emit(geojson)
        except Exception as e:
            if not self.isInterruptionRequested():
                logger.error(f"Viewport worker error: {e}")
                self.finished.emit("")


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
        title: str = None,
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

        if title is None:
            title = tr("dialog.map.search_on_map")
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
        self._viewport_worker = None  # Background thread for viewport loading
        self._auth_token = None # Store auth token for API calls (set by subclass)
        self._map_loaded = False  # Track whether map has finished loading

        if self.enable_viewport_loading:
            building_cache = None
            try:
                from services.building_cache_service import BuildingCacheService
                building_cache = BuildingCacheService.get_instance()
            except Exception:
                building_cache = None

            self._viewport_loader = ViewportMapLoader(
                cache_enabled=True,
                cache_max_size=50,
                cache_max_age_minutes=10,
                building_cache_service=building_cache,
                use_spatial_sampling=True
            )
            logger.info(f"Viewport loading enabled (cache={'active' if building_cache else 'disabled'})")

        # Get auth token if not provided
        if not self._auth_token and parent:
            self._auth_token = self._get_auth_token_from_parent(parent)

        # Create overlay (gray transparent layer)
        if parent:
            self._overlay = self._create_overlay(parent)
            self._overlay.show()

        # Create UI
        self._setup_ui()

        # Temporarily disable main window shadow effect (improves QWebEngineView performance)
        self._orig_shadow_effect = None
        main_win = self.parent()
        if main_win and hasattr(main_win, 'window_frame'):
            effect = main_win.window_frame.graphicsEffect()
            if effect:
                self._orig_shadow_effect = effect
                main_win.window_frame.setGraphicsEffect(None)

    def _setup_ui(self):
        """Setup dialog UI - matches BuildingMapWidget exactly."""
        # Window settings
        self.setModal(True)
        self.setWindowTitle(self.dialog_title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        screen = self.screen().availableGeometry()
        w = min(1455, int(screen.width() * 0.92))
        h = min(816, int(screen.height() * 0.88))
        self.setFixedSize(w, h)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content container with 24px padding
        content = QWidget()
        content.setObjectName("mapDialogContent")
        content.setStyleSheet(f"""
            QWidget#mapDialogContent {{
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

        # Map view
        map_w = self.width() - 48
        map_h = self.height() - 174
        if HAS_WEBENGINE:
            self.web_view = QWebEngineView(self)
            self.web_view.setFixedSize(map_w, map_h)

            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
            settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

            # Setup WebChannel
            if HAS_WEBCHANNEL:
                self._setup_webchannel()

            # Loading indicator
            self._loading_label = QLabel(tr("dialog.map.loading_map"))
            self._loading_label.setFixedSize(map_w, map_h)
            self._loading_label.setAlignment(Qt.AlignCenter)
            self._loading_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            self._loading_label.setStyleSheet(
                f"background-color: {Colors.BACKGROUND}; color: {Colors.TEXT_SECONDARY}; border-radius: 8px;"
            )

            map_container = QWidget()
            map_layout = QVBoxLayout(map_container)
            map_layout.setContentsMargins(0, 0, 0, 0)
            map_layout.setSpacing(0)
            map_layout.addWidget(self._loading_label)
            map_layout.addWidget(self.web_view)
            self.web_view.hide()

            self.web_view.loadFinished.connect(self._on_load_finished)
            content_layout.addWidget(map_container)
        else:
            placeholder = QLabel(tr("dialog.map.map_unavailable"))
            placeholder.setFixedSize(map_w, map_h)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            placeholder.setStyleSheet(f"""
                background-color: {Colors.BACKGROUND};
                color: {Colors.TEXT_SECONDARY};
                border-radius: 8px;
            """)
            content_layout.addWidget(placeholder)

        # Multi-select chips (optional) - below map
        if self.show_multiselect_ui:
            multiselect_ui = self._create_multiselect_ui()
            content_layout.addWidget(multiselect_ui)

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
        title_bar.setFixedHeight(ScreenScale.h(32))
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
        close_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
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
        search_frame.setFixedHeight(ScreenScale.h(42))
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

        # Search input (disabled until map loads)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("...")
        self.search_input.setEnabled(False)
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
        search_icon.setFixedSize(ScreenScale.w(20), ScreenScale.h(20))
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
        """Create multi-select UI with chips bar below the map."""
        multiselect_frame = QFrame()
        multiselect_frame.setObjectName("multiselectUI")
        multiselect_frame.setFixedHeight(ScreenScale.h(44))
        multiselect_frame.setStyleSheet(f"""
            QFrame#multiselectUI {{
                background-color: {Colors.LIGHT_GRAY_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)

        multiselect_layout = QHBoxLayout(multiselect_frame)
        multiselect_layout.setContentsMargins(12, 4, 12, 4)
        multiselect_layout.setSpacing(8)
        multiselect_layout.setDirection(QHBoxLayout.RightToLeft)

        # Counter label (right side in RTL)
        self.selection_counter_label = QLabel(tr("dialog.map.zero_buildings_selected"))
        self.selection_counter_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self.selection_counter_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY_BLUE};
                background: transparent;
                padding: 2px 4px;
            }}
        """)
        self.selection_counter_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        multiselect_layout.addWidget(self.selection_counter_label)

        # Scrollable chips area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(ScreenScale.h(34))
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._chips_container = QWidget()
        self._chips_container.setStyleSheet("background: transparent;")
        self._chips_layout = QHBoxLayout(self._chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        self._chips_layout.setDirection(QHBoxLayout.RightToLeft)
        self._chips_layout.addStretch()

        scroll.setWidget(self._chips_container)
        multiselect_layout.addWidget(scroll, 1)

        # Clear all button (left side in RTL)
        self.clear_all_btn = QPushButton(tr("dialog.map.clear_all"))
        self.clear_all_btn.setFixedSize(ScreenScale.w(80), ScreenScale.h(28))
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
        self.clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ERROR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 2px 6px;
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

    def _create_chip(self, building_id: str) -> QFrame:
        """Create a single chip widget for a selected building."""
        chip = QFrame()
        chip.setObjectName(f"chip_{building_id}")
        chip.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.PRIMARY_BLUE};
                border-radius: 12px;
                padding: 0px;
            }}
        """)
        chip.setFixedHeight(ScreenScale.h(26))

        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(8, 2, 4, 2)
        chip_layout.setSpacing(4)
        chip_layout.setDirection(QHBoxLayout.RightToLeft)

        label = QLabel(building_id)
        label.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
        label.setStyleSheet("QLabel { color: white; background: transparent; }")
        chip_layout.addWidget(label)

        close_btn = QToolButton()
        close_btn.setText("\u00d7")
        close_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QToolButton {{
                color: white;
                background: rgba(255,255,255,0.2);
                border: none;
                border-radius: 9px;
                font-size: 12px;
                font-weight: bold;
            }}
            QToolButton:hover {{
                background: rgba(255,255,255,0.4);
            }}
        """)
        close_btn.clicked.connect(lambda checked, bid=building_id: self._remove_chip(bid))
        chip_layout.addWidget(close_btn)

        return chip

    def _remove_chip(self, building_id: str):
        """Remove a single building from selection via JavaScript."""
        if self.web_view:
            self.web_view.page().runJavaScript(
                f"if (typeof toggleBuildingSelection === 'function') {{ toggleBuildingSelection('{building_id}'); }}"
            )

    def _create_confirm_area(self) -> QWidget:
        """Create confirmation area with coordinates display and buttons."""
        confirm_container = QWidget()
        confirm_container.setStyleSheet("background: transparent;")
        confirm_layout = QVBoxLayout(confirm_container)
        confirm_layout.setContentsMargins(0, 8, 0, 0)
        confirm_layout.setSpacing(12)

        # Coordinates display (hidden when multiselect UI is shown)
        self.coordinates_display = QLabel(tr("dialog.map.coordinates_not_selected"))
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
        if not self.show_multiselect_ui:
            confirm_layout.addWidget(self.coordinates_display)

        # Buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)
        buttons_row.addStretch()

        # Cancel button
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.setFixedSize(ScreenScale.w(120), ScreenScale.h(40))
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
        self.confirm_btn = QPushButton(tr("dialog.map.confirm_coordinates"))
        self.confirm_btn.setFixedSize(ScreenScale.w(160), ScreenScale.h(40))
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

        self._bridge.bridge_ready.connect(self._on_bridge_ready)

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
        overlay.setObjectName("mapDialogOverlay")
        overlay.setGeometry(0, 0, top_window.width(), top_window.height())
        overlay.setStyleSheet("""
            QWidget#mapDialogOverlay {
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

    def _on_load_finished(self, success):
        """Called when web_view finishes loading HTML."""
        if success:
            if hasattr(self, '_loading_label'):
                self._loading_label.hide()
            if self.web_view:
                self.web_view.show()
        else:
            logger.error("Map HTML failed to load")
            if hasattr(self, '_loading_label'):
                self._loading_label.setText(tr("dialog.map.map_load_failed"))
                self._loading_label.setStyleSheet(
                    f"background-color: {Colors.BACKGROUND}; color: {Colors.ERROR}; border-radius: 8px;"
                )

    def _on_bridge_ready(self):
        """Called when QWebChannel bridge is ready — map is interactive."""
        self._map_loaded = True
        logger.info("Map bridge ready")
        if hasattr(self, 'search_input') and self.search_input:
            self.search_input.setEnabled(True)
            self.search_input.setPlaceholderText(tr("dialog.map.search_placeholder"))

    def _show_map_error(self, message: str):
        """Log map error. No Qt overlay — web_view renders directly."""
        logger.error(f"Map error: {message}")

    def _on_geometry_drawn(self, geom_type: str, wkt: str):
        """Handle geometry drawn - emit signal."""
        logger.info(f"BaseMapDialog._on_geometry_drawn called")
        logger.info(f"   geom_type: {geom_type}")
        logger.info(f"   wkt: {wkt[:100] if wkt else 'None'}...")

        # Update coordinates display if enabled
        if self.show_confirm_button:
            self._update_coordinates_display(geom_type, wkt)

        logger.info(f"   Emitting geometry_selected signal...")
        self.geometry_selected.emit(geom_type, wkt)
        logger.info(f"geometry_selected signal emitted")

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
                self.selection_counter_label.setText(tr("dialog.map.zero_buildings_selected"))
                self.clear_all_btn.setEnabled(False)
            elif count == 1:
                self.selection_counter_label.setText(tr("dialog.map.one_building_selected"))
                self.clear_all_btn.setEnabled(True)
            elif count == 2:
                self.selection_counter_label.setText(tr("dialog.map.two_buildings_selected"))
                self.clear_all_btn.setEnabled(True)
            elif count <= 10:
                self.selection_counter_label.setText(tr("dialog.map.plural_buildings_selected", count=count))
                self.clear_all_btn.setEnabled(True)
            else:
                self.selection_counter_label.setText(tr("dialog.map.many_buildings_selected", count=count))
                self.clear_all_btn.setEnabled(True)

    def _on_viewport_changed(self, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float, zoom: int):
        """Handle viewport changed event from JavaScript (non-blocking)."""
        if not self._viewport_loader:
            return

        # Debounce: store pending bounds and use a single-shot timer
        self._pending_viewport = (ne_lat, ne_lng, sw_lat, sw_lng, zoom)
        if not hasattr(self, '_viewport_debounce_timer'):
            from PyQt5.QtCore import QTimer
            self._viewport_debounce_timer = QTimer(self)
            self._viewport_debounce_timer.setSingleShot(True)
            self._viewport_debounce_timer.setInterval(400)
            self._viewport_debounce_timer.timeout.connect(self._fire_viewport_load)
        if not self._viewport_debounce_timer.isActive():
            self._viewport_debounce_timer.start()

    def _fire_viewport_load(self):
        """Actually fire viewport loading after debounce."""
        if not hasattr(self, '_pending_viewport'):
            return
        ne_lat, ne_lng, sw_lat, sw_lng, zoom = self._pending_viewport

        # Cancel previous worker (requestInterruption + disconnect signals)
        if self._viewport_worker and self._viewport_worker.isRunning():
            self._viewport_worker.requestInterruption()
            try:
                self._viewport_worker.buildings_loaded.disconnect()
                self._viewport_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass

        # Get auth token
        auth_token = self._auth_token
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

        self._viewport_worker = _ViewportWorker(
            self._viewport_loader,
            (ne_lat, ne_lng, sw_lat, sw_lng),
            zoom, auth_token
        )
        self._viewport_worker.buildings_loaded.connect(self._on_viewport_buildings_cached)
        self._viewport_worker.finished.connect(self._on_viewport_geojson_ready)
        self._viewport_worker.start()

    def _on_viewport_buildings_cached(self, buildings):
        """Cache buildings loaded by viewport worker."""
        if not hasattr(self, '_viewport_buildings_cache'):
            self._viewport_buildings_cache = {}
        for b in buildings:
            if b.building_id:
                self._viewport_buildings_cache[b.building_id] = b
        if hasattr(self, '_buildings_cache') and isinstance(self._buildings_cache, list) and not self._buildings_cache:
            self._buildings_cache = buildings
        if self.web_view:
            self.web_view.page().runJavaScript(
                "var o=document.getElementById('loadingOverlay');if(o)o.remove();"
            )

    def _on_viewport_geojson_ready(self, geojson):
        """Update map with GeoJSON from viewport worker."""
        if geojson:
            self._update_map_buildings(geojson)

    def _update_buildings_list(self, building_ids: List[str]):
        """Update the chips container with selected building IDs."""
        if not hasattr(self, '_chips_layout'):
            return

        # Clear existing chips (keep the stretch at the end)
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add chip for each building
        for building_id in building_ids:
            chip = self._create_chip(building_id)
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)

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

    def _fly_to(self, lat, lng, zoom=17):
        """Execute smooth flyTo on the Leaflet map."""
        js_code = f"""
        if (typeof window._isFlying === 'undefined') {{
            window._isFlying = false;
        }}
        if (typeof map !== 'undefined') {{
            window._isFlying = true;
            map.flyTo([{lat}, {lng}], {zoom}, {{
                duration: 2.0,
                easeLinearity: 0.25
            }});
            setTimeout(function() {{
                window._isFlying = false;
            }}, 2200);
        }}
        """
        self.web_view.page().runJavaScript(js_code)

    def _search_landmark_or_street(self, search_text):
        """Search landmarks via API then streets via JS layer. Returns (found, name) or starts JS callback."""
        try:
            from services.api_client import get_api_client
            from services.map_utils import normalize_landmark
            api = get_api_client()

            landmarks = api.search_landmarks(search_text, max_results=5)
            if landmarks and isinstance(landmarks, list):
                lm = normalize_landmark(landmarks[0])
                lat = lm.get("latitude")
                lng = lm.get("longitude")
                if lat and lng:
                    self._fly_to(float(lat), float(lng), 17)
                    return True, lm.get("name", search_text)

            return False, None
        except Exception as e:
            logger.warning(f"Landmark/street search error: {e}")
            return False, None

    def _search_streets_js(self, search_text, not_found_callback=None):
        """Search loaded streets layer via JavaScript."""
        safe_text = search_text.replace("\\", "\\\\").replace("'", "\\'")
        js = f"""
        (function() {{
            if (typeof streetsLayer !== 'undefined') {{
                var found = false;
                streetsLayer.eachLayer(function(layer) {{
                    if (!found) {{
                        var name = '';
                        if (layer.getTooltip()) {{
                            name = layer.getTooltip().getContent() || '';
                        }}
                        if (name.indexOf('{safe_text}') !== -1) {{
                            var center = layer.getBounds().getCenter();
                            map.flyTo(center, 16, {{duration: 2.0}});
                            layer.openTooltip();
                            found = true;
                        }}
                    }}
                }});
                return found ? 'found' : 'not_found';
            }}
            return 'no_layer';
        }})()
        """

        def on_result(result):
            if result != 'found' and not_found_callback:
                not_found_callback()

        self.web_view.page().runJavaScript(js, on_result)

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
                tr("dialog.map.coordinates_point", lat=f"{lat:.6f}", lon=f"{lon:.6f}")
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
                    tr("dialog.map.coordinates_polygon", lat=f"{center_lat:.6f}", lon=f"{center_lon:.6f}", points=len(lats))
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

        from services.tile_server_manager import get_local_server_url
        base_url = QUrl(get_local_server_url())

        self.web_view.setHtml(html, base_url)
        logger.info("Map HTML loaded")

    @staticmethod
    def load_buildings_geojson(db, limit: int = 200, auth_token: Optional[str] = None) -> str:
        """
        Load buildings for map display via API.

        Args:
            db: Database instance (unused, kept for signature compatibility)
            limit: Maximum number of buildings to load
            auth_token: Authentication token for API calls

        Returns:
            GeoJSON string with buildings
        """
        from services.geojson_converter import GeoJSONConverter

        try:
            from services.map_service_api import MapServiceAPI
            map_service = MapServiceAPI()

            if auth_token:
                map_service.set_auth_token(auth_token)

            buildings = map_service.get_buildings_in_bbox(
                north_east_lat=36.5,
                north_east_lng=37.5,
                south_west_lat=36.0,
                south_west_lng=36.8,
                page_size=limit
            )

            if buildings:
                logger.info(f"Loaded {len(buildings)} buildings from API")
                return GeoJSONConverter.buildings_to_geojson(buildings, prefer_polygons=True)

        except Exception as e:
            logger.warning(f"API buildings load failed: {e}")

        return '{"type":"FeatureCollection","features":[]}'

    @staticmethod
    def load_neighborhoods_geojson(auth_token: Optional[str] = None) -> Optional[str]:
        """
        Load neighborhoods from API and convert to GeoJSON for map overlay.

        Returns:
            GeoJSON string with neighborhood center points, or None
        """
        try:
            from services.api_client import get_api_client
            api = get_api_client()

            neighborhoods = api.get_neighborhoods_by_bounds(
                sw_lat=36.14, sw_lng=37.07,
                ne_lat=36.26, ne_lng=37.23
            )

            if neighborhoods:
                result = BaseMapDialog._neighborhoods_to_geojson(neighborhoods)
                if result:
                    logger.info(f"Loaded neighborhoods from API")
                    return result

        except Exception as e:
            logger.warning(f"API neighborhoods failed: {e}")

        return None

    @staticmethod
    def _neighborhoods_to_geojson(neighborhoods: list) -> Optional[str]:
        """Convert API neighborhood response to GeoJSON center points."""
        import json as _json

        features = []
        for n in neighborhoods:
            boundaries = n.get('boundaries', '')
            if not boundaries or 'POLYGON' not in boundaries.upper():
                continue

            coords_str = boundaries.replace('POLYGON((', '').replace('))', '').strip()
            pairs = coords_str.split(',')
            lngs, lats = [], []
            for pair in pairs:
                parts = pair.strip().split()
                if len(parts) == 2:
                    lngs.append(float(parts[0]))
                    lats.append(float(parts[1]))

            if lats and lngs:
                center_lat = sum(lats) / len(lats)
                center_lng = sum(lngs) / len(lngs)
                features.append({
                    "type": "Feature",
                    "properties": {
                        "code": n.get('code', ''),
                        "name_ar": n.get('nameArabic', ''),
                        "center_lat": center_lat,
                        "center_lng": center_lng
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [center_lng, center_lat]
                    }
                })

        if features:
            logger.info(f"Created {len(features)} neighborhood features from API data")
            return _json.dumps({"type": "FeatureCollection", "features": features})
        return None

    def _get_auth_token_from_parent(self, parent) -> Optional[str]:
        """
        Get auth token from parent window (MainWindow.current_user).

 Single source of truth for auth_token retrieval.

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
                    logger.debug(f"Auth token retrieved from MainWindow (length: {len(token)})")
                return token
        except Exception as e:
            logger.warning(f"Could not get auth token from parent: {e}")

        return None

    def _cleanup_overlay(self):
        """Remove overlay from screen and restore main window shadow."""
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

        # Restore main window shadow effect
        if getattr(self, '_orig_shadow_effect', None):
            try:
                main_win = self.parent()
                if main_win and hasattr(main_win, 'window_frame'):
                    main_win.window_frame.setGraphicsEffect(self._orig_shadow_effect)
                self._orig_shadow_effect = None
            except (RuntimeError, Exception):
                self._orig_shadow_effect = None

    def _cleanup_workers(self):
        """Stop viewport workers and timers."""
        if hasattr(self, '_viewport_debounce_timer'):
            self._viewport_debounce_timer.stop()
        if self._viewport_worker and self._viewport_worker.isRunning():
            self._viewport_worker.requestInterruption()

    def accept(self):
        """Override accept to clean up overlay."""
        try:
            self._cleanup_overlay()
            self._cleanup_workers()
        finally:
            super().accept()

    def reject(self):
        """Override reject to clean up overlay."""
        try:
            self._cleanup_overlay()
            self._cleanup_workers()
        finally:
            super().reject()

    def closeEvent(self, event):
        """Clean up overlay when dialog closes."""
        try:
            self._cleanup_overlay()
            self._cleanup_workers()
        finally:
            super().closeEvent(event)
