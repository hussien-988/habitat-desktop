# -*- coding: utf-8 -*-
"""
Circular loading spinner overlay.
Replicates the map loading spinner for PyQt5 pages.
"""
from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, QTimer, QRectF, QEvent
from PyQt5.QtGui import QPainter, QColor, QPen

from ui.font_utils import create_font, FontManager
from services.translation_manager import tr

# Safety timeout: auto-hide spinner after 30 seconds to prevent infinite hang
_DEFAULT_TIMEOUT_MS = 30_000


class _SpinnerWidget(QWidget):
    """Animated circular spinner drawn with QPainter."""

    def __init__(self, size: int = 48, pen_width: int = 4, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._pen_width = pen_width
        self._rotation_angle = 0.0
        self._track_color = QColor(255, 255, 255, 38)
        self._arc_color = QColor(0, 114, 188)  # #0072BC

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self._rotation_angle = (self._rotation_angle + 7.2) % 360.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())
        margin = self._pen_width / 2
        rect = QRectF(margin, margin, side - self._pen_width, side - self._pen_width)

        track_pen = QPen(self._track_color, self._pen_width)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        arc_pen = QPen(self._arc_color, self._pen_width)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        start = int(self._rotation_angle * 16)
        span = 90 * 16
        painter.drawArc(rect, start, span)

        painter.end()


class LoadingSpinnerOverlay(QWidget):
    """Dark overlay with circular spinner and text label.

    Features:
    - Safety timeout (default 30s) auto-hides spinner to prevent infinite hang
    - Reentrant guard prevents double-loading
    - Always use try/finally when wrapping sync calls
    """

    def __init__(self, parent: Optional[QWidget] = None,
                 timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self._is_loading = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        self._spinner = _SpinnerWidget(size=48, pen_width=4, parent=self)
        layout.addWidget(self._spinner, 0, Qt.AlignCenter)

        self._label = QLabel(tr("component.loading.default"))
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.7); background: transparent;"
        )
        self._label.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(self._label, 0, Qt.AlignCenter)

        # Safety timeout timer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self.hide_loading)
        self._timeout_ms = timeout_ms

        if parent:
            parent.installEventFilter(self)

        self.hide()

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    def show_loading(self, message: str = None) -> None:
        """Show overlay with spinner and message.

        Safe to call multiple times - will update message if already showing.
        """
        self._is_loading = True
        self._label.setText(message or tr("component.loading.default"))
        parent = self.parent()
        if parent and isinstance(parent, QWidget):
            self.setGeometry(parent.rect())
        self._spinner.start()
        self.show()
        self.raise_()

        # Start safety timeout
        self._timeout_timer.start(self._timeout_ms)

        QApplication.processEvents()

    def hide_loading(self) -> None:
        """Hide overlay and stop animation. Safe to call even if not showing."""
        self._timeout_timer.stop()
        self._spinner.stop()
        self._is_loading = False
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 50, 180))
        super().paintEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.parent() and event.type() == QEvent.Resize:
            if self.isVisible():
                self.setGeometry(obj.rect())
        return super().eventFilter(obj, event)
