# -*- coding: utf-8 -*-
"""Reusable animated gradient divider line."""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPainter, QLinearGradient


class AccentLine(QWidget):
    """Dual-tone gradient line with animated glow pulse on tab switch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)

        self._glow_opacity = 0.0
        self._glow_anim = QPropertyAnimation(self, b"glowOpacity")
        self._glow_anim.setDuration(600)
        self._glow_anim.setEasingCurve(QEasingCurve.OutQuad)

    @pyqtProperty(float)
    def glowOpacity(self):
        return self._glow_opacity

    @glowOpacity.setter
    def glowOpacity(self, val: float):
        self._glow_opacity = val
        self.update()

    def pulse(self):
        self._glow_anim.stop()
        self._glow_anim.setStartValue(0.9)
        self._glow_anim.setEndValue(0.0)
        self._glow_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(56, 144, 223, 0))
        grad.setColorAt(0.1, QColor(56, 144, 223, 80))
        grad.setColorAt(0.3, QColor(0, 178, 227, 140))
        grad.setColorAt(0.5, QColor(120, 190, 255, 200))
        grad.setColorAt(0.7, QColor(0, 178, 227, 140))
        grad.setColorAt(0.9, QColor(56, 144, 223, 80))
        grad.setColorAt(1.0, QColor(56, 144, 223, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawRect(0, 0, w, h)

        if self._glow_opacity > 0.01:
            glow_grad = QLinearGradient(0, 0, w, 0)
            ga = int(self._glow_opacity * 220)
            glow_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
            glow_grad.setColorAt(0.2, QColor(0, 178, 227, int(ga * 0.9)))
            glow_grad.setColorAt(0.5, QColor(120, 190, 255, min(255, int(ga * 1.4))))
            glow_grad.setColorAt(0.8, QColor(91, 168, 240, ga))
            glow_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
            painter.setBrush(glow_grad)
            painter.drawRect(0, 0, w, h)

        painter.end()
