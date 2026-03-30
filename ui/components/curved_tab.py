# -*- coding: utf-8 -*-
"""Curved trapezoid tab widget."""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QPen,
)

from ui.design_system import Colors


class CurvedTab(QWidget):
    """Tab with curved/trapezoid shape (slanted edges)."""

    clicked = pyqtSignal()

    def __init__(self, text: str, theme: str = "dark", parent=None):
        super().__init__(parent)
        self._text = text
        self._theme = theme
        self._active = False
        self._hovered = False
        self._font = QFont()
        self._slant = 14
        self.setMouseTracking(True)

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

    def set_theme(self, theme: str):
        self._theme = theme
        self.update()

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self._text) if hasattr(fm, 'horizontalAdvance') else fm.width(self._text)
        return QSize(text_w + self._slant * 2 + 20, self.height() or 32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        s = self._slant

        # Build trapezoid path with curved corners
        path = QPainterPath()
        path.moveTo(0, h)
        path.cubicTo(s * 0.3, h, s * 0.5, 0, s, 0)
        path.lineTo(w - s, 0)
        path.cubicTo(w - s * 0.5, 0, w - s * 0.3, h, w, h)
        path.closeSubpath()

        if self._active:
            self._draw_active(painter, path)
        elif self._hovered:
            self._draw_hovered(painter, path)
        else:
            self._draw_inactive(painter, path)

        painter.end()

    def _draw_active(self, painter: QPainter, path: QPainterPath):
        if self._theme == "dark":
            painter.fillPath(path, QColor("#DEEBFF"))
            text_color = QColor("#3B86FF")
        else:
            painter.fillPath(path, QColor(Colors.SURFACE))
            painter.strokePath(path, QPen(QColor(Colors.PRIMARY_BLUE), 1.5))
            text_color = QColor(Colors.PRIMARY_BLUE)

        font = QFont(self._font)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)

    def _draw_hovered(self, painter: QPainter, path: QPainterPath):
        if self._theme == "dark":
            painter.fillPath(path, QColor(255, 255, 255, 18))
            text_color = QColor(255, 255, 255, 230)
        else:
            painter.fillPath(path, QColor("#F0F4F8"))
            text_color = QColor(Colors.WIZARD_TITLE)

        painter.setFont(self._font)
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)

    def _draw_inactive(self, painter: QPainter, path: QPainterPath):
        if self._theme == "dark":
            text_color = QColor(255, 255, 255, 178)
        else:
            painter.fillPath(path, QColor(Colors.SURFACE))
            text_color = QColor(Colors.WIZARD_TITLE)

        painter.setFont(self._font)
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)

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
