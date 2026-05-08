# -*- coding: utf-8 -*-
"""
Reusable building location map preview component.

Shows an embedded Leaflet map for a building and emits expand_requested
when the user wants to open the full map dialog.
"""

from PyQt5.QtWidgets import (
    QFrame, QLabel, QPushButton, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon

from ui.components.icon import Icon
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None
    QWebEngineSettings = None
    QWebEnginePage = None
    HAS_WEBENGINE = False


class BuildingLocationMapPreview(QFrame):
    """Reusable preview map for displaying a building location."""

    expand_requested = pyqtSignal()

    def __init__(self, button_text=None, height=260, parent=None):
        super().__init__(parent)

        self._building = None
        self._web_view = None
        self._fallback_label = None
        self._height = ScreenScale.h(height)

        self.setObjectName("buildingLocationMapPreview")
        self.setMinimumHeight(self._height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("""
            QFrame#buildingLocationMapPreview {
                background-color: #E8E8E8;
                border-radius: 12px;
                border: none;
            }
        """)

        if HAS_WEBENGINE:
            self._web_view = QWebEngineView(self)
            self._web_view.setContextMenuPolicy(Qt.NoContextMenu)

            try:
                from services.web_profile import get_shared_map_profile
                shared_profile = get_shared_map_profile()
                if shared_profile is not None:
                    page = QWebEnginePage(shared_profile, self._web_view)
                    self._web_view.setPage(page)
            except Exception as e:
                logger.warning(f"Could not attach shared profile to preview map: {e}")

            settings = self._web_view.settings()
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

            self._web_view.hide()
            self._web_view.loadFinished.connect(self._on_map_loaded)

        self._fallback_label = QLabel(self)
        self._fallback_label.setAlignment(Qt.AlignCenter)
        self._fallback_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                border-radius: 12px;
            }
        """)

        self._expand_btn = QPushButton("↗", self)
        self._expand_btn.setFixedSize(ScreenScale.w(30), ScreenScale.h(30))
        self._expand_btn.setCursor(Qt.PointingHandCursor)
        self._expand_btn.setToolTip(button_text or tr("page.building_details.open_map"))

        self._expand_btn.setFont(create_font(
            size=12,
            weight=FontManager.WEIGHT_MEDIUM
        ))

        self._expand_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 230);
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 15px;
                padding-bottom: 1px;
            }}

            QPushButton:hover {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
            }}

            QPushButton:pressed {{
                background-color: #F0F0F0;
            }}
        """)

        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(10)
        btn_shadow.setXOffset(0)
        btn_shadow.setYOffset(2)
        btn_shadow.setColor(QColor(0, 0, 0, 70))
        self._expand_btn.setGraphicsEffect(btn_shadow)

        self._expand_btn.clicked.connect(self.expand_requested.emit)

        self._loading_label = QLabel(self)
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setText(tr("component.loading.default"))
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        self._loading_label.setStyleSheet("""
            QLabel {
                background-color: #E8E8E8;
                color: #64748B;
                border-radius: 12px;
                border: none;
            }
        """)
        self._loading_label.hide()

        self._show_fallback()

    def _on_map_loaded(self, ok: bool):
        """Hide loading overlay once the map finishes loading."""
        if hasattr(self, '_loading_label'):
            self._loading_label.hide()
        self._expand_btn.raise_()

    def set_building(self, building):
        """Render the building location on the embedded preview map."""
        self._building = building

        center = self._get_building_center(building)

        if not HAS_WEBENGINE or not center:
            self._show_fallback()
            return

        try:
            from services.tile_server_manager import get_tile_server_url
            from services.leaflet_html_generator import generate_leaflet_html
            from services.geojson_converter import GeoJSONConverter

            center_lat, center_lon = center

            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                [building],
                force_points=True
            )

            html = generate_leaflet_html(
                tile_server_url=get_tile_server_url().rstrip("/"),
                buildings_geojson=buildings_geojson,
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=18,
                max_zoom=20,
                show_legend=False,
                show_layer_control=False,
                enable_selection=False,
                enable_multiselect=False,
                enable_viewport_loading=False,
                enable_drawing=False,
                skip_fit_bounds=True,
                landmarks_json="[]",
                streets_json="[]",
                boundaries_geojson=None,
                neighborhoods_geojson=None,
                show_building_labels=True,
            )

            self._fallback_label.hide()
            self._loading_label.setGeometry(0, 0, self.width(), self.height())
            self._loading_label.show()
            self._loading_label.raise_()
            self._web_view.show()
            self._web_view.setHtml(html)
            self._expand_btn.raise_()

        except Exception as e:
            logger.warning(f"Could not render building location preview map: {e}")
            self._show_fallback()

    def _get_building_center(self, building):
        """Extract building center from latitude/longitude or geo_location."""
        if not building:
            return None

        lat = getattr(building, "latitude", None)
        lon = getattr(building, "longitude", None)

        try:
            if lat is not None and lon is not None:
                lat = float(lat)
                lon = float(lon)

                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
        except (TypeError, ValueError):
            pass

        geo_location = (
            getattr(building, "geo_location", None)
            or getattr(building, "building_geometry", None)
        )

        if not geo_location:
            return None

        try:
            from services.geojson_converter import GeoJSONConverter

            geometry, _ = GeoJSONConverter._parse_geo_location(geo_location)

            if not geometry:
                return None

            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
            else:
                centroid = GeoJSONConverter._calculate_centroid(geometry)
                coords = centroid.get("coordinates", []) if centroid else []

            if len(coords) >= 2:
                lon = float(coords[0])
                lat = float(coords[1])
                return lat, lon

        except Exception as e:
            logger.warning(f"Could not extract building center: {e}")

        return None

    def _show_fallback(self):
        """Show old static image fallback when map cannot be rendered."""
        if self._web_view:
            self._web_view.hide()

        self._fallback_label.show()

        map_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_pixmap or map_pixmap.isNull():
            map_pixmap = Icon.load_pixmap("map-placeholder", size=None)

        if map_pixmap and not map_pixmap.isNull():
            self._fallback_label.setPixmap(
                map_pixmap.scaled(
                    max(1, self.width()),
                    max(1, self.height()),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                )
            )
        else:
            loc_fallback = Icon.load_pixmap("carbon_location-filled", size=56)
            if loc_fallback and not loc_fallback.isNull():
                self._fallback_label.setPixmap(loc_fallback)

        self._expand_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)

        width = self.width()
        height = self.height()

        if self._web_view:
            self._web_view.setGeometry(0, 0, width, height)

        if self._fallback_label:
            self._fallback_label.setGeometry(0, 0, width, height)

        if hasattr(self, '_loading_label') and self._loading_label:
            self._loading_label.setGeometry(0, 0, width, height)

        margin = ScreenScale.w(12)
        btn_width = self._expand_btn.width()

        
        x = width - btn_width - margin

        self._expand_btn.move(x, ScreenScale.h(12))

        if self._fallback_label and self._fallback_label.isVisible():
            self._show_fallback()