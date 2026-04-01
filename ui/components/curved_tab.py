# -*- coding: utf-8 -*-
"""Rounded tab widget: flowing line handles framing, tab is simple rounded rect."""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt5.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QPen, QLinearGradient,
)

from ui.design_system import Colors


class CurvedTab(QWidget):
    """Tab: rounded rect (dark theme) or trapezoid (light theme)."""

    clicked = pyqtSignal()

    _RADIUS = 12

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
        if self._theme == "dark":
            return QSize(text_w + 60, self.height() or 32)
        return QSize(text_w + self._slant * 2 + 20, self.height() or 32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        if self._theme == "dark":
            if self._active:
                self._paint_active_dark(painter, w, h)
            elif self._hovered:
                self._paint_hovered_dark(painter, w, h)
            else:
                self._paint_inactive_dark(painter, w, h)
        else:
            # Light theme trapezoid (unchanged)
            s = self._slant
            path = QPainterPath()
            path.moveTo(0, h)
            path.cubicTo(s * 0.3, h, s * 0.5, 0, s, 0)
            path.lineTo(w - s, 0)
            path.cubicTo(w - s * 0.5, 0, w - s * 0.3, h, w, h)
            path.closeSubpath()

            if self._active:
                painter.fillPath(path, QColor(Colors.SURFACE))
                painter.strokePath(path, QPen(QColor(Colors.PRIMARY_BLUE), 1.5))
                font = QFont(self._font)
                font.setWeight(QFont.DemiBold)
                painter.setFont(font)
                painter.setPen(QColor(Colors.PRIMARY_BLUE))
                painter.drawText(self.rect(), Qt.AlignCenter, self._text)
            elif self._hovered:
                painter.fillPath(path, QColor("#F0F4F8"))
                painter.setFont(self._font)
                painter.setPen(QColor(Colors.WIZARD_TITLE))
                painter.drawText(self.rect(), Qt.AlignCenter, self._text)
            else:
                painter.fillPath(path, QColor(Colors.SURFACE))
                painter.setFont(self._font)
                painter.setPen(QColor(Colors.WIZARD_TITLE))
                painter.drawText(self.rect(), Qt.AlignCenter, self._text)

        painter.end()

    def _paint_active_dark(self, painter, w, h):
        r = self._RADIUS
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)

        # Blue gradient fill
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor("#3890DF"))
        grad.setColorAt(1, QColor("#5BA8F0"))
        painter.fillPath(path, grad)

        # Edge glow border
        painter.setPen(QPen(QColor(91, 168, 240, 50), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Inner top highlight shimmer
        painter.setClipPath(path)
        shimmer = QLinearGradient(0, 0, 0, 12)
        shimmer.setColorAt(0, QColor(255, 255, 255, 30))
        shimmer.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(0, 0, w, 12), shimmer)
        painter.setClipping(False)

        # Text
        font = QFont(self._font)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)

    def _paint_hovered_dark(self, painter, w, h):
        r = self._RADIUS
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)

        # Frosted glass fill
        painter.fillPath(path, QColor(15, 31, 61, 130))

        # Border glow
        painter.setPen(QPen(QColor(56, 144, 223, 50), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Subtle inner shimmer
        painter.setClipPath(path)
        shimmer = QLinearGradient(0, 1, 0, 8)
        shimmer.setColorAt(0, QColor(56, 144, 223, 15))
        shimmer.setColorAt(1, QColor(56, 144, 223, 0))
        painter.fillRect(QRectF(0, 1, w, 8), shimmer)
        painter.setClipping(False)

        # Text
        painter.setFont(self._font)
        painter.setPen(QColor(200, 220, 255, 245))
        painter.drawText(self.rect(), Qt.AlignCenter, self._text)

    def _paint_inactive_dark(self, painter, w, h):
        # No shape -- just text
        painter.setFont(self._font)
        painter.setPen(QColor(139, 172, 200, 180))
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
