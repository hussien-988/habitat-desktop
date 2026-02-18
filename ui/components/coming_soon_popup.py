# -*- coding: utf-8 -*-
"""
Coming Soon cloud-style popup — lightweight bubble that appears and fades out.
"""

from PyQt5.QtWidgets import QWidget, QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QFont, QBrush


class ComingSoonPopup(QWidget):
    """A floating cloud/bubble popup that shows 'Coming Soon'."""

    _active = None  # Class-level ref to prevent garbage collection

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(260, 90)

        # Label
        self._label = QLabel("Coming Soon", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self._label.setStyleSheet("color: white; background: transparent;")
        self._label.setGeometry(10, 5, 240, 70)

        self._bg_color = QColor("#E53E3E")  # Red

    def paintEvent(self, event):
        """Draw cloud/bubble shape."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        # Rounded rectangle (cloud body)
        path.addRoundedRect(10, 5, 240, 70, 20, 20)

        # Small triangle at bottom center (speech bubble tail)
        path.moveTo(118, 75)
        path.lineTo(130, 88)
        path.lineTo(142, 75)

        painter.fillPath(path, QBrush(self._bg_color))
        painter.end()

    @staticmethod
    def popup(parent_widget):
        """Show the Coming Soon popup centered on the parent window."""
        # Close previous if still open
        if ComingSoonPopup._active is not None:
            try:
                ComingSoonPopup._active.close()
            except RuntimeError:
                pass
            ComingSoonPopup._active = None

        window = parent_widget.window() if parent_widget else None
        inst = ComingSoonPopup(window)  # Parent = window (prevents GC)

        # Center on window
        if window:
            center = window.mapToGlobal(window.rect().center())
            inst.setParent(None)  # Detach so it's a top-level window
            inst.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            inst.setAttribute(Qt.WA_TranslucentBackground)
            inst.move(center.x() - 130, center.y() - 45)
        else:
            inst.move(500, 300)

        ComingSoonPopup._active = inst  # prevent GC
        inst.show()
        inst.raise_()
        inst.activateWindow()

        # Auto-close after 1.5s
        QTimer.singleShot(1500, inst._fade_and_close)

    def _fade_and_close(self):
        """Fade out then close."""
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._cleanup)
        self._anim.start()

    def _cleanup(self):
        """Clean up after fade out."""
        ComingSoonPopup._active = None
        self.close()
        self.deleteLater()
