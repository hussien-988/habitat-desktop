# -*- coding: utf-8 -*-
"""Reusable dark navy header zone with constellation particles and cadastral grid.

Usage:
    header = DarkHeaderZone(parent)
    header.set_title("Page Title")
    header.add_stat_pill(pill_widget)
    header.add_tab(tab_widget)
    header.set_search_field(search_widget)
    header.add_action_widget(button_widget)
"""

import math
import random
import time

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath,
)

from ui.design_system import PageDimensions, ScreenScale
from ui.font_utils import create_font


class DarkHeaderZone(QFrame):
    """Dark header zone with constellation particles, cadastral grid,
    and breathing glow. Visually extends the navbar.

    Configurable: title, stat pills, tabs, search field, and custom action
    widgets can be added after construction.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(ScreenScale.h(110))
        self.setAttribute(Qt.WA_StyledBackground, False)

        self._anim_start = time.time()

        random.seed(42)
        self._particles = []
        for _ in range(6):
            self._particles.append({
                "x": random.uniform(0.05, 0.95),
                "y": random.uniform(0.1, 0.9),
                "speed": random.uniform(0.3, 0.8),
                "phase": random.uniform(0, math.tau),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)

        # Internal layout refs
        self._title_label = None
        self._row1 = None
        self._row2 = None

        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(
            PageDimensions.content_padding_h(), 16,
            PageDimensions.content_padding_h(), 14
        )
        main.setSpacing(0)

        # Row 1: title + stats + action widgets
        self._row1 = QHBoxLayout()
        self._row1.setSpacing(12)

        self._title_label = QLabel()
        self._title_label.setFont(create_font(size=18, weight=QFont.Bold))
        self._title_label.setStyleSheet("color: white; background: transparent;")
        self._row1.addWidget(self._title_label)

        self._row1.addSpacing(16)

        # Placeholder for stat pills — they will be inserted here
        self._stats_start_index = self._row1.count()

        self._row1.addStretch()

        # Action widgets go after the stretch
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setSpacing(8)
        self._row1.addLayout(self._actions_layout)

        main.addLayout(self._row1)
        main.addSpacing(12)

        # Row 2: tabs + search
        self._row2 = QHBoxLayout()
        self._row2.setSpacing(6)
        self._tabs_start_index = 0

        self._row2.addStretch()

        # Search field will be appended after the stretch
        self._search_index = self._row2.count()

        main.addLayout(self._row2)

    # --- Public configuration API ---

    def set_title(self, text: str):
        self._title_label.setText(text)

    def add_stat_pill(self, pill: QWidget):
        """Insert a stat pill into row 1 (before the stretch)."""
        stretch_idx = self._row1.count() - 2  # before stretch and actions
        self._row1.insertWidget(stretch_idx, pill)

    def add_tab(self, tab: QWidget):
        """Insert a tab into row 2 (before the stretch)."""
        idx = self._row2.count() - 1  # before stretch
        self._row2.insertWidget(idx, tab)

    def set_search_field(self, search: QWidget):
        """Add a search field at the end of row 2."""
        self._row2.addWidget(search)

    def add_action_widget(self, widget: QWidget):
        """Add an action widget (button, etc.) in the top-right area."""
        self._actions_layout.addWidget(widget)

    def add_row2_widget(self, widget: QWidget):
        """Add a custom widget to row 2 (before the stretch)."""
        idx = self._row2.count() - 1
        self._row2.insertWidget(idx, widget)

    def set_help(self, page_id: str):
        from ui.components.help_button import HelpButton
        btn = HelpButton(page_id, variant="dark", parent=self)
        self._row1.insertWidget(1, btn)

    def get_title_label(self) -> QLabel:
        return self._title_label

    # --- Paint ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self._anim_start

        # Lighter navy gradient with rounded bottom corners
        path = QPainterPath()
        r = 16.0
        path.moveTo(0, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h - r)
        path.quadTo(w, h, w - r, h)
        path.lineTo(r, h)
        path.quadTo(0, h, 0, h - r)
        path.closeSubpath()

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#152D4A"))
        grad.setColorAt(0.5, QColor("#1A3A5C"))
        grad.setColorAt(1.0, QColor("#1E4468"))
        painter.fillPath(path, grad)

        painter.setClipPath(path)

        # Cadastral grid
        painter.setPen(QPen(QColor(56, 144, 223, 18), 1))
        for x in range(60, w, 60):
            painter.drawLine(x, 0, x, h)
        for y in range(60, h, 60):
            painter.drawLine(0, y, w, y)

        # Simple diamond accents at grid intersections
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(56, 144, 223, 12))
        for gx in range(60, w, 60):
            for gy in range(60, h, 60):
                painter.save()
                painter.translate(gx, gy)
                painter.rotate(45)
                painter.drawRect(-2, -2, 4, 4)
                painter.restore()

        # Corner bracket accents
        bracket_color = QColor(56, 144, 223, 22)
        painter.setPen(QPen(bracket_color, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(12, 12, 12, 30)
        painter.drawLine(12, 12, 30, 12)
        painter.drawLine(w - 12, h - 16, w - 12, h - 34)
        painter.drawLine(w - 12, h - 16, w - 30, h - 16)

        # Breathing radial glow
        glow_alpha = 20 + int(12 * math.sin(t * 1.0))
        glow = QRadialGradient(w / 2, h * 0.5, w * 0.28)
        glow.setColorAt(0, QColor(56, 144, 223, glow_alpha))
        glow.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            int(w / 2 - w * 0.28), int(h * 0.22),
            int(w * 0.56), int(h * 0.56)
        )

        # Constellation particles
        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.01 * math.sin(t * p["speed"] + p["phase"])) * w)
            py = int((p["y"] + 0.008 * math.cos(t * p["speed"] * 0.7 + p["phase"])) * h)
            px = max(4, min(w - 4, px))
            py = max(4, min(h - 4, py))
            positions.append((px, py))
            alpha = 38 + int(18 * math.sin(t * 1.2 + p["phase"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        # Connecting lines
        connection_midpoints = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 200:
                    alpha = int(14 * (1 - dist / 200))
                    painter.setPen(QPen(QColor(139, 172, 200, alpha), 1))
                    painter.drawLine(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1]
                    )
                    mx = (positions[i][0] + positions[j][0]) // 2
                    my = (positions[i][1] + positions[j][1]) // 2
                    connection_midpoints.append((mx, my))

        # Periodic glow at constellation node points
        pulse = (math.sin(t * 1.5) + 1) / 2
        node_glow_alpha = int(10 + 30 * pulse)
        painter.setPen(Qt.NoPen)
        for (px, py) in positions:
            ng = QRadialGradient(px, py, 8)
            ng.setColorAt(0, QColor(139, 200, 255, node_glow_alpha))
            ng.setColorAt(1, QColor(139, 200, 255, 0))
            painter.setBrush(ng)
            painter.drawEllipse(px - 8, py - 8, 16, 16)

        # Subtle glow at connection midpoints
        mid_pulse = (math.sin(t * 0.8 + 1.5) + 1) / 2
        mid_alpha = int(6 + 18 * mid_pulse)
        for (mx, my) in connection_midpoints:
            mg = QRadialGradient(mx, my, 6)
            mg.setColorAt(0, QColor(56, 144, 223, mid_alpha))
            mg.setColorAt(1, QColor(56, 144, 223, 0))
            painter.setBrush(mg)
            painter.drawEllipse(mx - 6, my - 6, 12, 12)

        painter.setClipping(False)
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
