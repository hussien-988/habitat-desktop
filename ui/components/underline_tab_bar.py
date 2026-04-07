# -*- coding: utf-8 -*-
"""
UnderlineTabBar — Chrome/VSCode-style tab bar with animated underline indicator.
"""

import logging
from typing import List, Optional

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QRect, pyqtProperty, QTimer
)
from PyQt5.QtGui import QPainter, QColor, QFont, QCursor

from ..design_system import Colors, ScreenScale
from ..font_utils import create_font, FontManager

logger = logging.getLogger(__name__)


class _TabLabel(QLabel):
    """Single tab label with hover effect."""

    clicked = pyqtSignal(int)

    def __init__(self, text: str, index: int, parent=None):
        super().__init__(text, parent)
        self._index = index
        self._active = False
        self._hover = False
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAlignment(Qt.AlignCenter)
        self._apply_style()

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            color = Colors.PRIMARY_BLUE
            weight = "bold"
        elif self._hover:
            color = Colors.TEXT_PRIMARY
            weight = "normal"
        else:
            color = Colors.TEXT_SECONDARY
            weight = "normal"

        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: {weight};
                padding: 8px 20px;
                background: transparent;
                border: none;
            }}
        """)

    def enterEvent(self, event):
        self._hover = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._index)
        super().mousePressEvent(event)


class UnderlineTabBar(QWidget):
    """
    Tab bar with animated underline indicator.

    Signals:
        tab_changed(int): Emitted when the active tab changes (0-indexed)
    """

    tab_changed = pyqtSignal(int)

    def __init__(self, tabs: List[str], parent=None):
        super().__init__(parent)
        self._tabs: List[_TabLabel] = []
        self._active_index = 0

        # Animated underline position
        self._indicator_rect = QRect(0, 0, 0, 0)
        self._indicator_color = QColor(Colors.PRIMARY_BLUE)

        # Animation
        self._anim = QPropertyAnimation(self, b"indicatorRect")
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        # Glow pulse
        self._glow_opacity = 0.0
        self._glow_anim = QPropertyAnimation(self, b"glowOpacity")
        self._glow_anim.setDuration(600)
        self._glow_anim.setEasingCurve(QEasingCurve.OutQuad)

        self._setup_ui(tabs)

    def _setup_ui(self, tabs: List[str]):
        self.setFixedHeight(ScreenScale.h(44))
        self.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        font = create_font(size=FontManager.SIZE_BODY, weight=QFont.DemiBold)

        for i, title in enumerate(tabs):
            label = _TabLabel(title, i, self)
            label.setFont(font)
            label.clicked.connect(self._on_tab_clicked)
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            layout.addWidget(label)
            self._tabs.append(label)

        layout.addWidget(QWidget(), 1)  # spacer

        if self._tabs:
            self._tabs[0].set_active(True)

        QTimer.singleShot(0, self._init_indicator)

    def _init_indicator(self):
        """Initialize indicator position after layout is settled."""
        if self._tabs:
            tab = self._tabs[0]
            self._indicator_rect = QRect(
                tab.x(), self.height() - 3, tab.width(), 3
            )
            self.update()

    def _on_tab_clicked(self, index: int):
        if index == self._active_index:
            return
        self.set_active_tab(index)
        self.tab_changed.emit(index)

    def set_active_tab(self, index: int):
        if index < 0 or index >= len(self._tabs):
            return

        # Deactivate old
        self._tabs[self._active_index].set_active(False)
        self._active_index = index
        self._tabs[index].set_active(True)

        # Animate underline
        tab = self._tabs[index]
        target = QRect(tab.x(), self.height() - 3, tab.width(), 3)
        self._anim.stop()
        self._anim.setStartValue(self._indicator_rect)
        self._anim.setEndValue(target)
        self._anim.start()

        # Trigger glow pulse
        self._glow_anim.stop()
        self._glow_anim.setStartValue(0.5)
        self._glow_anim.setEndValue(0.0)
        self._glow_anim.start()

    def active_index(self) -> int:
        return self._active_index

    # -- Qt properties for animation --

    @pyqtProperty(QRect)
    def indicatorRect(self):
        return self._indicator_rect

    @indicatorRect.setter
    def indicatorRect(self, rect: QRect):
        self._indicator_rect = rect
        self.update()

    @pyqtProperty(float)
    def glowOpacity(self):
        return self._glow_opacity

    @glowOpacity.setter
    def glowOpacity(self, val: float):
        self._glow_opacity = val
        self.update()

    # -- Paint --

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._indicator_rect.width():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self._indicator_rect

        # Glow effect (soft shadow behind the indicator)
        if self._glow_opacity > 0.01:
            glow_color = QColor(Colors.PRIMARY_BLUE)
            glow_color.setAlphaF(self._glow_opacity * 0.4)
            glow_rect = QRect(r.x() - 4, r.y() - 4, r.width() + 8, r.height() + 8)
            painter.setBrush(glow_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(glow_rect, 4, 4)

        # Main indicator line
        painter.setBrush(self._indicator_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(r, 1.5, 1.5)

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._tabs and self._active_index < len(self._tabs):
            tab = self._tabs[self._active_index]
            self._indicator_rect = QRect(
                tab.x(), self.height() - 3, tab.width(), 3
            )
            self.update()
