# -*- coding: utf-8 -*-
"""Reusable frosted glass count pill widget."""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QPainterPath

from ui.font_utils import create_font, FontManager
from ui.design_system import ScreenScale


class StatPill(QWidget):
    """Small frosted glass pill showing a count + label."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._count = 0
        self._label_text = label
        self.setFixedHeight(ScreenScale.h(28))
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)

        self._count_lbl = QLabel("0")
        self._count_lbl.setFont(create_font(size=11, weight=QFont.Bold))
        self._count_lbl.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(self._count_lbl)

        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._text_lbl.setStyleSheet("color: rgba(139, 172, 200, 220); background: transparent;")
        layout.addWidget(self._text_lbl)

    def set_count(self, count: int):
        self._count = count
        self._count_lbl.setText(str(count))
        self.update()

    def set_label(self, text: str):
        self._label_text = text
        self._text_lbl.setText(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 14, 14)
        painter.fillPath(path, QColor(15, 31, 61, 140))
        painter.setPen(QPen(QColor(56, 144, 223, 35), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.end()
        super().paintEvent(event)
