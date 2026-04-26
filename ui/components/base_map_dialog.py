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
from services.viewport_map_loader import ViewportMapLoader, get_shared_viewport_loader
from services.building_cache_service import get_building_cache
from services.translation_manager import tr

logger = get_logger(__name__)

# Check for WebEngine availability
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None
    QWebEnginePage = None


# Forward console messages from the page to Python logs and to the active
# MapPerfTrace if any. JS in the HTML can emit `console.log("[MAP_PERF_JS]
# phase=name extra=value")` to attach renderer-side phase marks to the trace.
if HAS_WEBENGINE:
    class _PerfWebEnginePage(QWebEnginePage):
        """QWebEnginePage that captures all JS console messages."""

        def javaScriptConsoleMessage(self, level, message, line_number, source_id):
            try:
                # Only log [MAP_PERF_JS]-prefixed messages at WARNING (visible in
                # the terminal); everything else at DEBUG to avoid noise.
                if isinstance(message, str) and message.startswith('[MAP_PERF_JS]'):
                    # Translate into a phase mark if a trace is active so the
                    # JS-side timeline merges into our existing [MAP_PERF] log.
                    try:
                        from services.map_perf_logger import get_active_trace
                        trace = get_active_trace()
                    except Exception:
                        trace = None
                    if trace is not None:
                        # message format: "[MAP_PERF_JS] phase=<name> k1=v1 k2=v2 ..."
                        body = message[len('[MAP_PERF_JS]'):].strip()
                        parts = body.split()
                        phase = 'js_unknown'
                        fields = {}
                        for p in parts:
                            if '=' in p:
                                k, v = p.split('=', 1)
                                if k == 'phase':
                                    phase = v
                                else:
                                    fields[k] = v
                        try:
                            trace.mark('js_' + phase, **fields)
                        except Exception:
                            pass
                    else:
                        logger.warning(message)
                else:
                    logger.debug(f"[JS:{line_number}] {message}")
            except Exception:
                pass

# Check for WebChannel availability
try:
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBCHANNEL = False


# No-op shim for legacy _perf() calls — instrumentation has been removed.
def _perf(*args, **kwargs):
    pass


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
    finished = pyqtSignal(str)       # GeoJSON string
    buildings_loaded = pyqtSignal(list)  # Building objects for cache
    network_error = pyqtSignal(str)  # user-friendly error message

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
            import json as _json
            geojson = GeoJSONConverter.buildings_to_geojson(
                buildings, force_points=True
            )
            try:
                _feat_count = len(_json.loads(geojson).get('features', []))
            except Exception:
                _feat_count = 0
            if self.isInterruptionRequested():
                return
            self.buildings_loaded.emit(buildings)
            self.finished.emit(geojson)
        except Exception as e:
            if not self.isInterruptionRequested():
                logger.error(f"Viewport worker error: {e}")
                err_str = str(e)
                if any(k in err_str for k in ("SSL", "ConnectionError", "Timeout", "Max retries", "Connection refused")):
                    self.network_error.emit("network")
                else:
                    self.network_error.emit("server")
                self.finished.emit('{"type":"FeatureCollection","features":[]}')


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
            from services.map_service_api import MapServiceAPI
            _provider = getattr(self, '_map_data_provider', None)
            provider_key = type(_provider).__name__ if _provider else 'default'
            map_svc = MapServiceAPI(data_provider=_provider)
            self._viewport_loader = get_shared_viewport_loader(
                provider_key=provider_key,
                map_service=map_svc,
                cache_max_age_minutes=30,
            )
            logger.info(f"Viewport loading enabled (session cache, provider={provider_key})")

        # Get auth token if not provided
        if not self._auth_token and parent:
            self._auth_token = self._get_auth_token_from_parent(parent)

        # Create overlay (gray transparent layer) — kept hidden until the dialog
        # actually becomes visible (showEvent). This is critical for pre-warm flows
        # where the dialog widget is instantiated but never exec_()-ed — showing the
        # overlay in __init__ would dim the parent (MainWindow) with no dialog on top.
        if parent:
            self._overlay = self._create_overlay(parent)
            self._overlay.hide()

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
        self.resize(w, h)
        self.setMinimumSize(800, 500)
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
            # map_container is a plain fixed-size widget — children are positioned
            # absolutely so the loading label can float on top of the web view.
            self._map_container = QWidget()
            self._map_container.setFixedSize(map_w, map_h)

            self.web_view = QWebEngineView(self._map_container)
            self.web_view.setGeometry(0, 0, map_w, map_h)

            # Install the perf-capturing page so JS console.log("[MAP_PERF_JS]...")
            # statements flow into our MapPerfTrace timeline.
            try:
                _perf_page = _PerfWebEnginePage(self.web_view)
                self.web_view.setPage(_perf_page)
            except Exception as _e:
                logger.warning(f"Could not install perf page: {_e}")

            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
            # Leaflet 1.x doesn't use WebGL; disabling skips GPU context init (fewer
            # conflicts with other Chromium apps sharing the GPU).
            settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, False)
            settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)
            # Set dark background so web_view never flashes white before Chromium's first paint.
            self.web_view.page().setBackgroundColor(QColor('#1a1a2e'))
            if HAS_WEBCHANNEL:
                self._setup_webchannel()

            # Loading indicator — absolute overlay on top of web_view.
            # Stays visible until _on_load_finished so there is never a dark gap.
            self._loading_label = QLabel(tr("dialog.map.loading_map"), self._map_container)
            self._loading_label.setGeometry(0, 0, map_w, map_h)
            self._loading_label.setAlignment(Qt.AlignCenter)
            self._loading_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            self._loading_label.setStyleSheet(
                f"background-color: {Colors.BACKGROUND}; color: {Colors.TEXT_SECONDARY}; border-radius: 8px;"
            )
            self._loading_label.raise_()

            self.web_view.loadFinished.connect(self._on_load_finished)
            content_layout.addWidget(self._map_container)
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

        # Refresh button
        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setFont(create_font(size=16, weight=FontManager.WEIGHT_REGULAR))
        refresh_btn.setToolTip(tr("dialog.map.refresh_buildings"))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.PRIMARY_BLUE};
            }}
        """)
        refresh_btn.setDefault(False)
        refresh_btn.setAutoDefault(False)
        refresh_btn.clicked.connect(self._on_refresh_map)

        layout.addWidget(refresh_btn)

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
        search_layout.setContentsMargins(14, 6, 14, 6)
        search_layout.setSpacing(8)
        search_layout.setDirection(QHBoxLayout.RightToLeft)

        # Search input (disabled until map loads)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("dialog.map.search_placeholder"))
        self.search_input.setEnabled(False)
        self.search_input.setLayoutDirection(Qt.RightToLeft)
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

        def _auto_direction(text):
            if text and '\u0600' <= text[0] <= '\u06FF':
                self.search_input.setLayoutDirection(Qt.RightToLeft)
                self.search_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            elif text:
                self.search_input.setLayoutDirection(Qt.LeftToRight)
                self.search_input.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.search_input.textChanged.connect(_auto_direction)

        search_layout.addWidget(self.search_input, 1)

        # Search icon (now clickable)
        search_icon_btn = QToolButton()
        search_icon_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        search_icon_btn.setCursor(Qt.PointingHandCursor)

        from ui.components.icon import Icon
        from PyQt5.QtGui import QIcon
        icon_pixmap = Icon.load_pixmap("search", size=16)
        if icon_pixmap and not icon_pixmap.isNull():
            search_icon_btn.setIcon(QIcon(icon_pixmap))
        else:
            search_icon_btn.setText("🔍")
            search_icon_btn.setFont(create_font(size=10))

        search_icon_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {Colors.LIGHT_GRAY_BG};
                border-radius: 4px;
            }}
        """)
        search_icon_btn.clicked.connect(self._on_search_submitted)
        search_layout.insertWidget(0, search_icon_btn)

        return search_frame

    def _create_multiselect_ui(self) -> QFrame:
        """Create multi-select UI with chips bar below the map.

        [UNIFIED-DIALOG] When self._max_selection == 1, the UI adapts:
        - Counter label shows selected building ID instead of count
        - Clear-all button is hidden (clicking another building replaces)
        """
        is_single_select = getattr(self, '_max_selection', None) == 1

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

        from services.translation_manager import get_layout_direction as _get_dir, is_rtl as _is_rtl
        _dir_qt = _get_dir()
        _rtl = _is_rtl()

        # Counter label
        _initial_text = (
            tr("dialog.map.select_building_prompt") if is_single_select
            else tr("dialog.map.zero_buildings_selected")
        )
        self.selection_counter_label = QLabel(_initial_text)
        self.selection_counter_label.setLayoutDirection(_dir_qt)
        self.selection_counter_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
        self.selection_counter_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY_BLUE};
                background: transparent;
                padding: 2px 4px;
            }}
        """)

        if is_single_select:
            # Single-select: label fills the full bar width and is always centered.
            self.selection_counter_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.selection_counter_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            # Dummy chips objects so the rest of the class doesn't break
            self._chips_container = QWidget()
            self._chips_layout = QHBoxLayout(self._chips_container)
            self._chips_layout.setContentsMargins(0, 0, 0, 0)

            self.clear_all_btn = QPushButton()
            self.clear_all_btn.hide()
            self.clear_all_btn.clicked.connect(self._on_clear_all_clicked)

            multiselect_layout.addWidget(self.selection_counter_label)
        else:
            # Multi-select: label on right (RTL) or left (LTR), chips in middle, clear btn on other side.
            self.selection_counter_label.setAlignment(Qt.AlignVCenter | (Qt.AlignRight if _rtl else Qt.AlignLeft))
            self.selection_counter_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

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

            # RTL: [clear_btn LEFT] [scroll MIDDLE] [label RIGHT]
            # LTR: [label LEFT] [scroll MIDDLE] [clear_btn RIGHT]
            if _rtl:
                multiselect_layout.addWidget(self.clear_all_btn)
                multiselect_layout.addWidget(scroll, 1)
                multiselect_layout.addWidget(self.selection_counter_label)
            else:
                multiselect_layout.addWidget(self.selection_counter_label)
                multiselect_layout.addWidget(scroll, 1)
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
        cancel_btn.clicked.connect(self._on_clear_all_clicked)
        buttons_row.addWidget(cancel_btn)

        # Confirm button
        # [UNIFIED-DIALOG] In single-select mode the button confirms a building choice.
        _is_single_select = getattr(self, '_max_selection', None) == 1
        _confirm_text = (
            tr("dialog.map.confirm_building_selection") if _is_single_select
            else tr("dialog.map.confirm_coordinates")
        )
        self.confirm_btn = QPushButton(_confirm_text)
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

    def resizeEvent(self, event):
        """Resize web_view and loading label to match new dialog size."""
        super().resizeEvent(event)
        map_w = self.width() - 48
        map_h = max(self.height() - 174, 300)
        if hasattr(self, '_map_container') and self._map_container:
            self._map_container.setFixedSize(map_w, map_h)
        if hasattr(self, 'web_view') and self.web_view:
            self.web_view.setGeometry(0, 0, map_w, map_h)
        if hasattr(self, '_loading_label') and self._loading_label:
            self._loading_label.setGeometry(0, 0, map_w, map_h)

    def _find_main_window(self):
        """Walk up the parent chain to find the MainWindow (has 'pages' dict)."""
        w = self.parent()
        while w is not None:
            if hasattr(w, 'pages'):
                return w
            try:
                w = w.parent()
            except Exception:
                return None
        return None

    def _pause_parent_decorative_timers(self):
        """Pause shimmer + constellation timers on every page of the main window
        while this dialog is visible. Modal dialogs do not trigger hideEvent on
        the parent page, so its decorative timers keep firing on the main thread
        and starve QWebEngineView during initialization. Resumed in hideEvent."""
        self._paused_parent_timers = []
        main_win = self._find_main_window()
        if not main_win or not hasattr(main_win, 'pages'):
            return
        for page in main_win.pages.values():
            t = getattr(page, '_shimmer_timer', None)
            if t is not None:
                try:
                    if t.isActive():
                        t.stop()
                        self._paused_parent_timers.append(t)
                except RuntimeError:
                    pass
            header = getattr(page, '_header', None)
            if header is not None:
                ht = getattr(header, '_timer', None)
                if ht is not None:
                    try:
                        if ht.isActive():
                            ht.stop()
                            self._paused_parent_timers.append(ht)
                    except RuntimeError:
                        pass

    def _resume_parent_decorative_timers(self):
        for t in getattr(self, '_paused_parent_timers', []):
            try:
                if not t.isActive():
                    t.start()
            except RuntimeError:
                pass
        self._paused_parent_timers = []

    def showEvent(self, event):
        """Show the gray overlay only when the dialog actually becomes visible.
        Supports pre-warm flows where the dialog is instantiated but not shown."""
        super().showEvent(event)
        self._pause_parent_decorative_timers()
        if getattr(self, '_overlay', None) is not None:
            try:
                self._overlay.show()
                self._overlay.raise_()
            except Exception:
                pass

    def hideEvent(self, event):
        """Hide the overlay when the dialog is hidden (on close/reject/accept)."""
        self._resume_parent_decorative_timers()
        if getattr(self, '_overlay', None) is not None:
            try:
                self._overlay.hide()
            except Exception:
                pass
        super().hideEvent(event)

    def _on_load_finished(self, success):
        """Called when web_view finishes loading HTML."""
        if success:
            # Hide the overlay label now that HTML (and its own spinner) is ready.
            if hasattr(self, '_loading_label') and self._loading_label:
                self._loading_label.hide()
            if self.web_view:
                self.web_view.page().runJavaScript(
                    "if(typeof map!=='undefined'&&map&&map.invalidateSize){map.invalidateSize(false);}"
                )
        else:
            logger.error("Map HTML failed to load")
            if hasattr(self, '_loading_label') and self._loading_label:
                self._loading_label.setText(tr("dialog.map.map_load_failed"))
                self._loading_label.setStyleSheet(
                    f"background-color: {Colors.BACKGROUND}; color: {Colors.ERROR}; border-radius: 8px;"
                )
                self._loading_label.show()
                self._loading_label.raise_()

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
        """Handle selection count update from JavaScript.

        [UNIFIED-DIALOG] In single-select mode the label text is driven by
        _on_buildings_multiselected (which has access to building display names),
        so we only toggle the clear-all button here — the label is overwritten later.
        """
        if not hasattr(self, 'selection_counter_label'):
            return
        is_single_select = getattr(self, '_max_selection', None) == 1
        if is_single_select:
            # Label is updated by subclass from building info (not a raw count).
            # Only manage enable state of clear-all (which is hidden in this mode anyway).
            if hasattr(self, 'clear_all_btn'):
                self.clear_all_btn.setEnabled(count > 0)
            return
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

    def _on_refresh_map(self):
        """Clear all caches, reset JS state, and reload buildings from API."""
        # 1. Clear Python-side caches
        try:
            from services.building_cache_service import BuildingCacheService
            BuildingCacheService.get_instance().invalidate_cache()
        except Exception:
            pass
        if self._viewport_loader:
            self._viewport_loader.clear_cache()

        # 2. Clear JS additive state so all buildings reload fresh
        if self.web_view:
            loading_text = tr("dialog.map.loading_buildings") or "جاري تحميل المباني..."
            self.web_view.page().runJavaScript(f"""
                if (typeof window.clearMapBuildings === 'function') window.clearMapBuildings();
                (function() {{
                    if (document.getElementById('loadingOverlay')) return;
                    var overlay = document.createElement('div');
                    overlay.id = 'loadingOverlay';
                    overlay.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);' +
                        'background:rgba(27,43,77,0.92);color:white;padding:8px 20px;border-radius:20px;' +
                        'font-size:13px;font-family:Arial;z-index:9999;direction:rtl;' +
                        'display:flex;align-items:center;gap:8px;';
                    overlay.innerHTML = '<span style="display:inline-block;width:10px;height:10px;border:2px solid white;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite"></span>' +
                        '<span>{loading_text}</span>';
                    if (!document.getElementById('mapSpinStyle')) {{
                        var s = document.createElement('style');
                        s.id = 'mapSpinStyle';
                        s.textContent = '@keyframes spin{{to{{transform:rotate(360deg)}}}}';
                        document.head.appendChild(s);
                    }}
                    document.body.appendChild(overlay);
                }})();
            """)

        # 3. Reload — use viewport if available, else trigger full viewport change
        if hasattr(self, '_pending_viewport') and self._pending_viewport:
            self._fire_viewport_load()
        elif self.web_view:
            self.web_view.page().runJavaScript(
                "if (typeof loadBuildingsForViewport === 'function') { "
                "isLoadingViewport = false; loadBuildingsForViewport(); }"
            )

    def _on_viewport_changed(self, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float, zoom: int):
        """Handle viewport changed event from JavaScript (JS already debounces at 300ms)."""
        if not self._viewport_loader:
            return
        if getattr(self, '_is_view_only', False):
            return
        self._pending_viewport = (ne_lat, ne_lng, sw_lat, sw_lng, zoom)
        self._fire_viewport_load()

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
        self._viewport_worker.network_error.connect(self._on_map_network_error)
        self._viewport_worker.start()

    def _on_map_network_error(self, error_type: str):
        """Show a temporary error banner on the map when the server is unreachable."""
        if not self.web_view:
            return
        if error_type == "network":
            msg = tr("dialog.map.error_server_unreachable") or "تعذّر الاتصال بالخادم — تحقق من الاتصال"
        else:
            msg = tr("dialog.map.error_server") or "خطأ في الخادم — يرجى المحاولة لاحقاً"
        self.web_view.page().runJavaScript(f"""
            (function() {{
                var existing = document.getElementById('mapNetworkError');
                if (existing) existing.remove();
                var banner = document.createElement('div');
                banner.id = 'mapNetworkError';
                banner.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
                    'background:rgba(185,28,28,0.93);color:white;padding:9px 22px;border-radius:20px;' +
                    'font-size:13px;font-family:Arial;z-index:9999;direction:rtl;' +
                    'display:flex;align-items:center;gap:8px;box-shadow:0 2px 8px rgba(0,0,0,0.3);';
                banner.innerHTML = '<span style="font-size:16px">⚠</span><span>{msg}</span>';
                document.body.appendChild(banner);
                setTimeout(function() {{ if (banner.parentNode) banner.parentNode.removeChild(banner); }}, 5000);
            }})();
        """)

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
        import json as _json
        has_buildings = False
        if geojson:
            try:
                _feats = _json.loads(geojson).get('features', [])
                has_buildings = bool(_feats)
            except Exception:
                pass
        if has_buildings:
            self._update_map_buildings(geojson)
        else:
            # Reset isLoadingViewport without clearing existing buildings
            if self.web_view:
                self.web_view.page().runJavaScript(
                    "if (typeof isLoadingViewport !== 'undefined') { isLoadingViewport = false; }"
                )

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
            if not isinstance(buildings_geojson, str) or not buildings_geojson.strip():
                return

            import json as _json
            js_code = f"if (typeof updateBuildingsOnMap === 'function') {{ updateBuildingsOnMap({buildings_geojson}); }}"
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

        Shows web_view before setHtml so Chromium is never throttled while hidden —
        preventing blank-tile areas on first pan. The HTML's own #map-loading-overlay
        (dark, z-index 9999) is the visual loading indicator from this point on.
        The dark page.setBackgroundColor ensures no white flash during the first paint.

        Args:
            html: Complete HTML string
        """
        if not self.web_view:
            logger.warning("WebView not available")
            return

        # Ensure the overlay label is visible and on top while the new HTML loads.
        if hasattr(self, '_loading_label') and self._loading_label:
            self._loading_label.setText(tr("dialog.map.loading_map"))
            self._loading_label.setStyleSheet(
                f"background-color: {Colors.BACKGROUND}; color: {Colors.TEXT_SECONDARY}; border-radius: 8px;"
            )
            self._loading_label.show()
            self._loading_label.raise_()

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
        """Stop viewport, buildings and layers workers + their debounce timer.

        Disconnects signals so a stale result from a worker that finishes after
        close cannot be injected into a destroyed dialog or compete with a
        freshly opened one.
        """
        if hasattr(self, '_viewport_debounce_timer'):
            self._viewport_debounce_timer.stop()
        for worker_attr in ('_viewport_worker', '_buildings_worker', '_layers_worker'):
            worker = getattr(self, worker_attr, None)
            if worker is None:
                continue
            try:
                worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                worker.error.disconnect()
            except (TypeError, RuntimeError, AttributeError):
                pass
            try:
                if worker.isRunning():
                    worker.requestInterruption()
            except RuntimeError:
                pass

    def _clear_perf_active_trace(self):
        """Drop the module-level active trace pointer so the next dialog's
        renderer console messages don't get attributed to this trace."""
        try:
            from services.map_perf_logger import set_active_trace, get_active_trace
            current = get_active_trace()
            # Only clear if THIS dialog set it; otherwise leave whatever the
            # next dialog already set.
            if current is not None and current is getattr(self, '_perf_trace', None):
                set_active_trace(None)
        except Exception:
            pass

    def _cleanup_web_view(self):
        """Tear down the QWebEngineView so the renderer process and pending
        network requests are released immediately.

        Without this, Python GC may keep the view alive after the dialog
        closes; its renderer continues to issue tile/asset requests against
        the local Python tile server, congesting the next dialog's load.
        """
        view = getattr(self, 'web_view', None)
        if view is None:
            return
        try:
            from PyQt5.QtCore import QUrl
            page = view.page()
            if page is not None:
                try:
                    page.runJavaScript("if(typeof map!=='undefined'&&map){try{map.remove();}catch(e){}}")
                except Exception:
                    pass
            try:
                view.stop()
            except Exception:
                pass
            try:
                view.setUrl(QUrl("about:blank"))
            except Exception:
                pass
            try:
                view.setParent(None)
            except Exception:
                pass
            try:
                view.deleteLater()
            except Exception:
                pass
        finally:
            self.web_view = None

    def accept(self):
        """Override accept to clean up overlay."""
        try:
            self._cleanup_overlay()
            self._cleanup_workers()
            self._cleanup_web_view()
            self._clear_perf_active_trace()
        finally:
            super().accept()

    def reject(self):
        """Override reject to clean up overlay."""
        try:
            self._cleanup_overlay()
            self._cleanup_workers()
            self._cleanup_web_view()
            self._clear_perf_active_trace()
        finally:
            super().reject()

    def closeEvent(self, event):
        """Clean up overlay when dialog closes."""
        try:
            self._cleanup_overlay()
            self._cleanup_workers()
            self._cleanup_web_view()
            self._clear_perf_active_trace()
        finally:
            super().closeEvent(event)
