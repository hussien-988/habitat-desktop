# -*- coding: utf-8 -*-
"""Reusable building location map preview component."""

import math
import os

from PyQt5.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QTimer, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen

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


_PREVIEW_BG = "#E8E8E8"

_DEBUG_TIMING = bool(os.environ.get("TRRCMS_PREVIEW_MAP_TIMING"))


class _PlainArcSpinner(QWidget):

    def __init__(self, diameter: int = 28, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        margin = 3
        rect = QRectF(margin, margin, side - 2 * margin, side - 2 * margin)

        # Faint track ring
        track_pen = QPen(QColor(56, 144, 223, 35), 2.5)
        track_pen.setCapStyle(Qt.RoundCap)
        p.setPen(track_pen)
        p.drawEllipse(rect)

        # Rotating arc
        arc_pen = QPen(QColor(56, 144, 223), 2.5)
        arc_pen.setCapStyle(Qt.RoundCap)
        p.setPen(arc_pen)
        # Qt arc angles are in 1/16 of a degree, counter-clockwise from 3 o'clock
        start_angle = int((90 - self._angle) * 16)
        span_angle = -100 * 16
        p.drawArc(rect, start_angle, span_angle)
        p.end()


class BuildingLocationMapPreview(QFrame):
    """Preview map for a single building location."""

    expand_requested = pyqtSignal()

    def __init__(self, button_text=None, height=260, parent=None):
        super().__init__(parent)

        self._building = None
        self._rendered_key = None
        self._pending_key = None

        self._web_view = None
        self._fallback_label = None
        self._height = ScreenScale.h(height)
        self._html_worker = None
        self._suspended = False
        self._map_loaded = False
        self._button_text = button_text

        self.setObjectName("buildingLocationMapPreview")
        self.setMinimumHeight(self._height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QFrame#buildingLocationMapPreview {{
                background-color: {_PREVIEW_BG};
                border-radius: 12px;
                border: none;
            }}
        """)

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
                border: 1px solid rgba(0, 0, 0, 30);
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

        self._expand_btn.clicked.connect(self.expand_requested.emit)

        self._spinner = _PlainArcSpinner(diameter=ScreenScale.w(28), parent=self)
        self._spinner.hide()

        self._show_fallback()

    # Lifecycle

    def _ensure_web_view(self):
        if self._web_view is not None or not HAS_WEBENGINE:
            return self._web_view

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

        try:
            self._web_view.page().setBackgroundColor(QColor(_PREVIEW_BG))
        except Exception:
            pass

        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, False)

        self._web_view.setGeometry(0, 0, self.width(), self.height())
        self._web_view.hide()
        self._web_view.loadFinished.connect(self._on_map_loaded)
        return self._web_view

    def _on_map_loaded(self, ok: bool):
        if _DEBUG_TIMING:
            logger.info(f"[PREVIEW_MAP] loadFinished ok={ok}")
        self._map_loaded = bool(ok)
        self._stop_spinner()
        if ok and self._web_view is not None and not self._suspended:
            self._web_view.show()
        self._expand_btn.raise_()

    def _start_spinner(self):
        if self._spinner is None:
            return
        self._position_spinner()
        self._spinner.show()
        self._spinner.raise_()
        self._spinner.start()

    def _stop_spinner(self):
        if self._spinner is None:
            return
        self._spinner.stop()
        self._spinner.hide()

    def _position_spinner(self):
        if self._spinner is None:
            return
        sw = self._spinner.width()
        sh = self._spinner.height()
        x = (self.width() - sw) // 2
        y = (self.height() - sh) // 2
        self._spinner.move(max(0, x), max(0, y))

    # Public API

    def update_language(self):
        self._expand_btn.setToolTip(self._button_text or tr("page.building_details.open_map"))

    def suspend(self):
        self._suspended = True
        self._stop_spinner()
        if self._web_view is not None:
            try:
                self._web_view.stop()
            except Exception:
                pass
            self._web_view.hide()
        if self._html_worker is not None:
            self._disconnect_worker(self._html_worker)
            self._html_worker = None

    def resume(self):
        if not self._suspended:
            return
        self._suspended = False
        if self._pending_key is not None and self._pending_key != self._rendered_key:
            self._rendered_key = None
            self.set_building(self._building)
        elif self._web_view is not None and self._map_loaded:
            self._web_view.show()
            self._expand_btn.raise_()

    def set_building(self, building):
        self._building = building

        center = self._get_building_center(building)

        if not HAS_WEBENGINE or not center:
            self._rendered_key = None
            self._pending_key = None
            self._stop_spinner()
            self._show_fallback()
            return

        key = (round(center[0], 7), round(center[1], 7))
        if key == self._rendered_key and self._web_view is not None and self._map_loaded:
            return

        self._pending_key = key
        if self._suspended:
            return

        self._fallback_label.hide()
        self._start_spinner()

        if self._html_worker is not None:
            self._disconnect_worker(self._html_worker)
            self._html_worker = None

        if _DEBUG_TIMING:
            logger.info(f"[PREVIEW_MAP] set_building start key={key}")

        try:
            from services.api_worker import ApiWorker
            self._html_worker = ApiWorker(self._build_preview_html, center)
            self._html_worker.finished.connect(self._on_html_ready)
            self._html_worker.error.connect(self._on_html_error)
            self._html_worker.start()
        except Exception as e:
            logger.warning(f"Async HTML build failed, falling back to sync: {e}")
            try:
                html = self._build_preview_html(center)
                self._on_html_ready(html)
            except Exception:
                self._show_fallback()

    # Internals

    def _build_preview_html(self, center):
        from services.tile_server_manager import get_tile_server_url
        from services.leaflet_html_generator import generate_leaflet_preview_html

        center_lat, center_lon = center
        b = self._building
        label = ""
        if b is not None:
            label = getattr(b, "building_number", None) or ""
            if not label:
                bid = getattr(b, "building_id", None) or ""
                bid = str(bid).replace("-", "")
                if len(bid) >= 5:
                    label = bid[-5:]
            label = str(label).strip()

        return generate_leaflet_preview_html(
            tile_server_url=get_tile_server_url(),
            center_lat=center_lat,
            center_lon=center_lon,
            zoom=18,
            max_zoom=20,
            building_label=label,
        )

    def _on_html_ready(self, html: str):
        if self._suspended:
            return
        if not html:
            self._show_fallback()
            return
        view = self._ensure_web_view()
        if view is None:
            self._show_fallback()
            return
        self._rendered_key = self._pending_key
        self._map_loaded = False
        view.setHtml(html)
        self._expand_btn.raise_()

    def _on_html_error(self, msg: str):
        logger.warning(f"Could not build building location preview HTML: {msg}")
        self._rendered_key = None
        self._show_fallback()

    def _disconnect_worker(self, worker):
        for sig in ("finished", "error"):
            try:
                getattr(worker, sig).disconnect()
            except Exception:
                pass

    def _get_building_center(self, building):
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
        self._stop_spinner()
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

        margin = ScreenScale.w(12)
        btn_width = self._expand_btn.width()

        x = width - btn_width - margin

        self._expand_btn.move(x, ScreenScale.h(12))

        self._position_spinner()

        if self._fallback_label and self._fallback_label.isVisible():
            self._show_fallback()

    def closeEvent(self, event):
        try:
            self._teardown()
        finally:
            super().closeEvent(event)

    def deleteLater(self):
        try:
            self._teardown()
        except Exception:
            pass
        super().deleteLater()

    def _teardown(self):
        self._stop_spinner()
        if self._html_worker is not None:
            self._disconnect_worker(self._html_worker)
            self._html_worker = None
        view = self._web_view
        if view is None:
            return
        try:
            view.stop()
        except Exception:
            pass
        try:
            view.loadFinished.disconnect(self._on_map_loaded)
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
        self._web_view = None
