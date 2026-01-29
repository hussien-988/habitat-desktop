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
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QWidget
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath, QRegion

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from models.building import Building
from utils.logger import get_logger
from ui.design_system import Colors
from ui.font_utils import FontManager, create_font

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
    """
    Custom QDialog with rounded corners.

    Args:
        radius: Border radius in pixels
        parent: Parent widget
    """

    def __init__(self, radius: int = 32, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.search_input = None  # Will be set after creation

    def paintEvent(self, event):
        """Paint dialog with rounded corners."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw rounded rectangle background
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.radius, self.radius)

        # Fill with background color
        painter.fillPath(path, QColor(Colors.SURFACE))

        # Draw border (optional - can be removed if not needed)
        # painter.strokePath(path, QPen(QColor(Colors.BORDER_DEFAULT), 1))

    def keyPressEvent(self, event):
        """
        Override keyPressEvent to prevent Enter/Return from closing dialog.

        Senior PyQt5 Best Practice:
        - Intercept Enter key BEFORE dialog's default behavior
        - Only let search field handle Enter, not dialog
        """
        from PyQt5.QtCore import Qt

        # If Enter/Return pressed and search input has focus
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.search_input and self.search_input.hasFocus():
                # Let search input handle it - don't propagate to dialog
                event.accept()
                # Manually trigger the search (redundant but ensures it works)
                self.search_input.returnPressed.emit()
                return

        # For Escape key, close dialog
        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        # For all other keys, use default behavior
        super().keyPressEvent(event)


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

    def show_dialog(self, selected_building_id: Optional[str] = None) -> Optional[Building]:
        """
        Show the map selection dialog.

        Args:
            selected_building_id: Optional building ID to focus on when map loads

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

        # Clear previous selection
        self._selected_building = None

        # Create overlay on parent (gray transparent layer)
        parent_widget = None
        if self.parent() and hasattr(self.parent(), 'rect'):
            parent_widget = self.parent()

        overlay = None
        if parent_widget:
            overlay = self._create_overlay(parent_widget)
            overlay.show()

        # Create dialog if not exists (reuse for performance)
        if self._dialog is None:
            self._dialog = self._create_dialog()

        # Load/reload map with optional building focus
        self._load_map(selected_building_id=selected_building_id)

        # Show dialog (modal)
        result = self._dialog.exec_()

        # Remove overlay after dialog closes
        if overlay:
            overlay.hide()
            overlay.deleteLater()

        # Return selected building if accepted
        if result == QDialog.Accepted and self._selected_building:
            return self._selected_building
        return None

    def _create_overlay(self, parent: QWidget) -> QWidget:
        """
        Create gray transparent overlay covering the entire application window.

        Args:
            parent: Parent widget to find top-level window

        Returns:
            Overlay widget covering entire window
        """
        # Find the top-level window (MainWindow)
        top_window = parent.window()  # Get the top-level QMainWindow/QWidget

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

    def _create_dialog(self) -> QDialog:
        """
        Create the map dialog UI.

        Enhanced Specifications (Senior PyQt5 Best Practice):
        - Size: 1100×700px (width × height) - Larger for better map visibility
        - Border-radius: 32px (زيادة للشكل الخارجي)
        - Internal padding: 24px
        - Title: "بحث على الخريطة" with 12px gap below
        - Search bar: 42px height, border-radius 8px
        - Map: Remaining space with border-radius 8px
        """
        # Create custom dialog with rounded corners
        dialog = RoundedDialog(radius=32)
        dialog.setModal(True)
        dialog.setWindowTitle("بحث على الخريطة")

        # إزالة شريط العنوان القياسي (الجزء العلوي المشار إليه)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        # Enhanced size: 1100×700px (much larger for better map interaction)
        dialog.setFixedSize(1100, 700)

        # Enable transparency for rounded corners
        dialog.setAttribute(Qt.WA_TranslucentBackground, True)

        # Main layout (no margins - we control everything)
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content container with 24px padding
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(12)  # Gap: 12px (Figma)

        # Title bar with close button (RTL)
        title_bar = self._create_title_bar(dialog)
        content_layout.addWidget(title_bar)

        # Search bar (42px height, border-radius 8px)
        search_bar = self._create_search_bar()
        content_layout.addWidget(search_bar)

        # Senior PyQt5 Best Practice: Link search input to dialog for key handling
        dialog.search_input = self.search_input

        # Map view (remaining space)
        # Calculate: 700 - 48 (padding top+bottom) = 652
        # 652 - title_bar (60) - 12 (gap) - search_bar (42) - 12 (gap) = space for map
        # Approximately: 652 - 60 - 12 - 42 - 12 = 526px height
        # Width: 1100 - 48 (padding) = 1052px
        if HAS_WEBENGINE:
            self._map_view = QWebEngineView(dialog)
            self._map_view.setFixedSize(1052, 526)

            # Enable settings
            settings = self._map_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

            # Setup WebChannel for building selection
            if HAS_WEBCHANNEL:
                self._setup_webchannel()

            # Map styling with border-radius 8px
            self._map_view.setStyleSheet("border-radius: 8px;")

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
            map_layout.addWidget(self._map_view)
            self._map_view.hide()

            # Connect load finished signal
            self._map_view.loadFinished.connect(self._on_map_loaded)

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

        # Center dialog on screen
        self._center_dialog(dialog)

        return dialog

    def _create_title_bar(self, dialog: QDialog) -> QWidget:
        """
        Create title bar with close button (X).

        Returns:
            QWidget containing title + close button
        """
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet("background: transparent;")

        # RTL layout
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.setDirection(QHBoxLayout.RightToLeft)

        # Title
        title = QLabel("بحث على الخريطة")
        title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title)

        # Spacer
        layout.addStretch()

        # Close button (X)
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
        close_btn.clicked.connect(dialog.reject)

        # Senior PyQt5 Best Practice: Prevent this button from being default
        # This ensures Enter key doesn't trigger close
        close_btn.setDefault(False)
        close_btn.setAutoDefault(False)

        layout.addWidget(close_btn)

        return title_bar

    def _create_search_bar(self) -> QFrame:
        """
        Create search bar (42px height, border-radius 8px).

        Returns:
            QFrame containing search input + icon
        """
        search_frame = QFrame()
        search_frame.setObjectName("searchBar")
        search_frame.setFixedHeight(42)

        # Figma: border-radius 8px
        search_frame.setStyleSheet(f"""
            QFrame#searchBar {{
                background-color: {Colors.SEARCH_BAR_BG};
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
            }}
        """)

        # RTL layout
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(14, 8, 14, 8)
        search_layout.setSpacing(8)
        search_layout.setDirection(QHBoxLayout.RightToLeft)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("بحث عن اسم المنطقة (مثال: Al-Jamiliyah)")
        self.search_input.setAlignment(Qt.AlignRight)  # RTL alignment
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

        # Connect search functionality
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._on_search_submitted)

        search_layout.addWidget(self.search_input, 1)

        # Search icon (على اليسار - الجهة الأخرى)
        search_icon = QLabel()
        search_icon.setFixedSize(20, 20)
        search_icon.setAlignment(Qt.AlignCenter)

        # Try to load icon from assets
        from ui.components.icon import Icon
        icon_pixmap = Icon.load_pixmap("search", size=16)
        if icon_pixmap and not icon_pixmap.isNull():
            search_icon.setPixmap(icon_pixmap)
        else:
            search_icon.setText("🔍")
            search_icon.setFont(create_font(size=10))

        search_icon.setStyleSheet("background: transparent;")

        # إضافة الأيقونة في البداية (على اليسار في RTL)
        search_layout.insertWidget(0, search_icon)

        return search_frame

    def _center_dialog(self, dialog: QDialog):
        """Center dialog on screen."""
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - dialog.width()) // 2
        y = (screen.height() - dialog.height()) // 2
        dialog.move(x, y)

    def _on_map_loaded(self, success: bool):
        """Called when map finishes loading."""
        if success:
            logger.info("Map loaded successfully")
            if hasattr(self, '_loading_label'):
                self._loading_label.hide()
            if self._map_view:
                self._map_view.show()
        else:
            logger.error("Map failed to load")
            if hasattr(self, '_loading_label'):
                self._loading_label.setText("❌ فشل تحميل الخريطة")
                self._loading_label.setStyleSheet(f"""
                    background-color: {Colors.BACKGROUND};
                    color: {Colors.ERROR};
                    border-radius: 8px;
                """)

    def _on_search_text_changed(self, text: str):
        """Handle search text changes (real-time search)."""
        # Optional: Add real-time suggestions here
        pass

    def _on_search_submitted(self):
        """
        Handle search submission (Enter key pressed).

        Search for neighborhood/area and fly to location on map.

        Senior PyQt5 Best Practice:
        - Explicit logging for debugging
        - Visual feedback to user
        - Error handling with user notification
        """
        search_text = self.search_input.text().strip()

        if not search_text:
            logger.info("Search submitted but text is empty - ignoring")
            return

        if not self._map_view:
            logger.warning("Map view not available for search")
            return

        logger.info(f"🔍 SEARCH TRIGGERED: '{search_text}'")

        # Search in buildings for matching neighborhood
        try:
            buildings = self.building_repo.get_all(limit=500)
            logger.info(f"Loaded {len(buildings)} buildings for search")

            # Find buildings in matching neighborhoods
            matching_buildings = []
            matched_neighborhoods = set()

            for building in buildings:
                # Search in both Arabic and English names
                neighborhood_ar = (building.neighborhood_name_ar or "").lower()
                neighborhood_en = (building.neighborhood_name or "").lower()
                search_lower = search_text.lower()

                if search_lower in neighborhood_ar or search_lower in neighborhood_en:
                    matching_buildings.append(building)
                    # Track which neighborhood matched
                    matched_neighborhoods.add(building.neighborhood_name or building.neighborhood_name_ar)

            logger.info(f"Found {len(matching_buildings)} matching buildings in neighborhoods: {matched_neighborhoods}")

            if matching_buildings:
                # Get center point of matching buildings
                lats = [b.latitude for b in matching_buildings if b.latitude]
                lons = [b.longitude for b in matching_buildings if b.longitude]

                if lats and lons:
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)

                    logger.info(f"Flying to center: ({center_lat}, {center_lon})")

                    # Fly to location on map using JavaScript
                    # Zoom level increased to 17 for better focus
                    js_code = f"""
                    console.log('🔍 SEARCH: Flying to [{center_lat}, {center_lon}] with {len(matching_buildings)} buildings');
                    if (typeof map !== 'undefined') {{
                        map.flyTo([{center_lat}, {center_lon}], 17, {{
                            duration: 2.0,
                            easeLinearity: 0.25
                        }});
                        console.log('✅ Map flyTo executed successfully');
                    }} else {{
                        console.error('❌ Map object not found!');
                    }}
                    """

                    def log_js_result(result):
                        logger.info(f"JavaScript execution completed: {result}")

                    self._map_view.page().runJavaScript(js_code, log_js_result)

                    logger.info(f"✅ Search successful: {len(matching_buildings)} buildings in '{search_text}'")

                    # Visual feedback: briefly change search bar color
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
                else:
                    logger.warning(f"⚠️ Buildings found but no coordinates available")
            else:
                logger.warning(f"❌ No buildings found for neighborhood: '{search_text}'")

        except Exception as e:
            logger.error(f"❌ Error searching for neighborhood: {e}", exc_info=True)

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

    def _load_map(self, selected_building_id: Optional[str] = None):
        """
        Load the interactive map with building markers and polygons.

        Args:
            selected_building_id: Optional building ID to focus on when map loads
        """
        if not self._map_view:
            return

        from services.tile_server_manager import get_tile_server_url
        from services.leaflet_html_generator import generate_leaflet_html
        import json

        tile_server_url = get_tile_server_url()
        logger.info(f"Tile server URL: {tile_server_url}")

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

        # If we have a selected building, focus on it
        center_lat = 36.2021
        center_lon = 37.1343
        zoom = 13
        focus_building_id = None

        if selected_building_id:
            # Find the selected building to focus on it
            focus_building = next((b for b in buildings if b.building_id == selected_building_id), None)
            if focus_building and focus_building.latitude and focus_building.longitude:
                center_lat = focus_building.latitude
                center_lon = focus_building.longitude
                zoom = 17  # Closer zoom for selected building
                focus_building_id = selected_building_id
                logger.info(f"Focusing on building {selected_building_id} at ({center_lat}, {center_lon})")

        # استخدام LeafletHTMLGenerator الموحد مع تفعيل زر الاختيار
        # الـ popup يفتح تلقائياً عند النقر، والزر داخل الـ popup
        html = generate_leaflet_html(
            tile_server_url=tile_server_url.rstrip('/'),
            buildings_geojson=buildings_geojson,
            center_lat=center_lat,
            center_lon=center_lon,
            zoom=zoom,
            show_legend=True,
            show_layer_control=False,
            enable_selection=True,
            enable_drawing=False
        )

        # LeafletHTMLGenerator يتعامل مع كل شيء
        self._map_view.setHtml(html, base_url)

        # If we focused on a building, open its popup after map loads
        if focus_building_id:
            def open_building_popup():
                js = f"""
                if (typeof buildingsLayer !== 'undefined') {{
                    buildingsLayer.eachLayer(function(layer) {{
                        if (layer.feature && layer.feature.properties.building_id === '{focus_building_id}') {{
                            layer.openPopup();
                            console.log('Opened popup for building {focus_building_id}');
                        }}
                    }});
                }}
                """
                self._map_view.page().runJavaScript(js)

            # Open popup after a short delay to ensure map is fully loaded
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1500, open_building_popup)


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
