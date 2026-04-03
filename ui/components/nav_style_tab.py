# -*- coding: utf-8 -*-
"""Reusable navbar-style underline tab widget."""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPainterPath, QCursor,
)


class NavStyleTab(QWidget):
    """Tab styled like navbar tabs: text + glowing blue underline when active."""

    clicked = pyqtSignal()

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self._active = False
        self._hovered = False
        self._font = QFont()
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_text(self, text: str):
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def set_active(self, active: bool):
        self._active = active
        self.update()

    def is_active(self) -> bool:
        return self._active

    def set_font(self, font: QFont):
        self._font = font
        self.update()

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self._text) if hasattr(fm, 'horizontalAdvance') else fm.width(self._text)
        return QSize(tw + 40, self.height() or 38)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Text
        if self._active:
            font = QFont(self._font)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
        elif self._hovered:
            painter.setFont(self._font)
            painter.setPen(QColor(200, 220, 255, 220))
        else:
            painter.setFont(self._font)
            painter.setPen(QColor(139, 172, 200, 180))

        text_rect = QRectF(0, 0, w, h - 6)
        painter.drawText(text_rect, Qt.AlignCenter, self._text)

        # Underline indicator
        if self._active:
            bar_w = min(w - 16, 70)
            bar_x = (w - bar_w) / 2
            bar_y = h - 4

            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            grad.setColorAt(0, QColor(56, 144, 223, 0))
            grad.setColorAt(0.15, QColor(56, 144, 223, 180))
            grad.setColorAt(0.5, QColor(120, 190, 255, 255))
            grad.setColorAt(0.85, QColor(56, 144, 223, 180))
            grad.setColorAt(1, QColor(56, 144, 223, 0))

            painter.setPen(Qt.NoPen)
            bar_path = QPainterPath()
            bar_path.addRoundedRect(QRectF(bar_x, bar_y, bar_w, 3), 1.5, 1.5)
            painter.fillPath(bar_path, grad)

            # Glow under bar
            glow = QRadialGradient(w / 2, h - 2, bar_w * 0.6)
            glow.setColorAt(0, QColor(56, 144, 223, 20))
            glow.setColorAt(1, QColor(56, 144, 223, 0))
            painter.setBrush(glow)
            painter.drawEllipse(QRectF(bar_x - 8, bar_y - 4, bar_w + 16, 12))

        elif self._hovered:
            bar_w = min(w - 24, 40)
            bar_x = (w - bar_w) / 2
            bar_y = h - 3
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(56, 144, 223, 35))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, 2), 1, 1)

        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
