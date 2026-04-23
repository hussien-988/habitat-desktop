# -*- coding: utf-8 -*-
"""
Viewport Bridge - للتواصل بين JavaScript و Python
Bridges Leaflet map viewport changes to Python via QWebChannel.
"""

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class ViewportBridge(QObject):
    """جسر التواصل بين Leaflet.js (JavaScript) و PyQt5 (Python) مع debouncing."""

    viewportChanged = pyqtSignal(dict)

    def __init__(self, debounce_ms: int = 300, parent: Optional[QObject] = None):
        """Initialize viewport bridge."""
        super().__init__(parent)

        self.debounce_ms = debounce_ms
        self._debounce_timer: Optional[QTimer] = None
        self._pending_viewport: Optional[Dict] = None
        self._last_viewport: Optional[Dict] = None

        self._stats = {
            'total_events': 0,
            'debounced_events': 0,
            'ignored_events': 0,
        }

        logger.info(f"ViewportBridge initialized (debounce={debounce_ms}ms)")

    @pyqtSlot(float, float, float, float, int, float, float)
    def onViewportChanged(
        self,
        ne_lat: float,
        ne_lng: float,
        sw_lat: float,
        sw_lng: float,
        zoom: int,
        center_lat: float,
        center_lng: float,
    ):
        """يُستدعى من JavaScript عند تغيير viewport مع debouncing."""
        self._stats['total_events'] += 1

        viewport = {
            'ne_lat': ne_lat,
            'ne_lng': ne_lng,
            'sw_lat': sw_lat,
            'sw_lng': sw_lng,
            'zoom': zoom,
            'center_lat': center_lat,
            'center_lng': center_lng,
        }

        if self._last_viewport == viewport:
            self._stats['ignored_events'] += 1
            return

        self._pending_viewport = viewport

        if self._debounce_timer is not None:
            self._debounce_timer.stop()

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_viewport_changed)
        self._debounce_timer.start(self.debounce_ms)

    def _emit_viewport_changed(self):
        """Emit the debounced viewport change."""
        if self._pending_viewport is None:
            return
        self._last_viewport = self._pending_viewport
        self._stats['debounced_events'] += 1
        self.viewportChanged.emit(self._pending_viewport)
        self._pending_viewport = None

    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            'total_events': 0,
            'debounced_events': 0,
            'ignored_events': 0,
        }
        logger.debug("ViewportBridge stats reset")

    def get_stats(self) -> Dict:
        """Return tracking statistics."""
        return dict(self._stats)

    def __del__(self):
        try:
            logger.debug(
                f"ViewportBridge destroyed - Stats: {self._stats}"
            )
        except Exception:
            pass
