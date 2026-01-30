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

from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QLineEdit, QFrame, QToolButton
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

    Signals:
        geometry_selected(type, wkt): Geometry drawn on map
        building_selected(building_id): Building clicked on map
        coordinates_updated(lat, lon, zoom): Map moved
    """

    geometry_selected = pyqtSignal(str, str)
    building_selected = pyqtSignal(str)
    coordinates_updated = pyqtSignal(float, float, int)

    def __init__(
        self,
        title: str = "بحث على الخريطة",
        show_search: bool = True,
        parent=None
    ):
        """
        Initialize base map dialog.

        Args:
            title: Dialog title
            show_search: Show search bar
            parent: Parent widget
        """
        super().__init__(parent)

        self.dialog_title = title
        self.show_search = show_search
        self.web_view = None
        self._bridge = None
        self._overlay = None

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

    def _setup_webchannel(self):
        """Setup WebChannel for JavaScript communication."""
        self._bridge = MapBridge()
        self._bridge.geometry_drawn.connect(self._on_geometry_drawn)
        self._bridge.coordinates_update.connect(self._on_coordinates_update)
        self._bridge.building_selected.connect(self._on_building_selected)

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
        self.geometry_selected.emit(geom_type, wkt)

    def _on_coordinates_update(self, lat: float, lon: float, zoom: int):
        """Handle coordinates update - emit signal."""
        self.coordinates_updated.emit(lat, lon, zoom)

    def _on_building_selected(self, building_id: str):
        """Handle building selected - emit signal."""
        self.building_selected.emit(building_id)

    def _on_search_submitted(self):
        """Handle search submission - subclass should override."""
        pass

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

    def _cleanup_overlay(self):
        """Remove overlay from screen."""
        if self._overlay:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None

    def accept(self):
        """Override accept to clean up overlay."""
        self._cleanup_overlay()
        super().accept()

    def reject(self):
        """Override reject to clean up overlay."""
        self._cleanup_overlay()
        super().reject()

    def closeEvent(self, event):
        """Clean up overlay when dialog closes."""
        self._cleanup_overlay()
        super().closeEvent(event)
