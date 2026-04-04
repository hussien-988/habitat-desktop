# -*- coding: utf-8 -*-
"""
Wizard Header Component - Dark-themed header for wizards and multi-step forms.

Uses DarkHeaderZone as the base to visually integrate with the navbar and
other dark-header pages. Supports title, subtitle, and an integrated step
progress indicator with connected frosted-glass pills.
"""

import math
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath,
)

from ui.font_utils import create_font, FontManager
from ui.design_system import Colors, PageDimensions
from ui.style_manager import StyleManager


class WizardHeader(QWidget):
    """Dark-themed wizard header with constellation background,
    title/subtitle, and optional step progress indicator pills.

    Drop-in replacement for the old gray WizardHeader.
    Maintains the same public API: set_title(), set_subtitle().
    Adds: set_steps(), set_current_step().
    """

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        steps: list = None,
        parent=None
    ):
        super().__init__(parent)
        self.title_text = title
        self.subtitle_text = subtitle
        self._steps = steps or []
        self._current_step = 0

        # Constellation particles
        self._anim_start = time.time()
        import random
        random.seed(77)
        self._particles = []
        for _ in range(5):
            self._particles.append({
                "x": random.uniform(0.05, 0.95),
                "y": random.uniform(0.1, 0.9),
                "speed": random.uniform(0.3, 0.8),
                "phase": random.uniform(0, math.tau),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)

        self._step_pills = []
        self._step_connectors = []

        self._setup_ui()

    def _setup_ui(self):
        """Build the dark header UI."""
        self.setAttribute(Qt.WA_StyledBackground, False)
        if self._steps:
            self.setMinimumHeight(130)
        else:
            self.setMinimumHeight(90)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(), 12
        )
        main_layout.setSpacing(0)

        # Row 1: Title + Subtitle
        title_row = QVBoxLayout()
        title_row.setSpacing(4)

        self.title_label = QLabel(self.title_text)
        self.title_label.setFont(create_font(size=17, weight=FontManager.WEIGHT_BOLD))
        self.title_label.setStyleSheet("color: white; background: transparent; border: none;")
        title_row.addWidget(self.title_label)

        self.subtitle_label = QLabel(self.subtitle_text)
        self.subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self.subtitle_label.setStyleSheet(
            "color: rgba(139, 172, 200, 180); background: transparent; "
            "border: none; letter-spacing: 0.5px;"
        )
        if not self.subtitle_text:
            self.subtitle_label.hide()
        title_row.addWidget(self.subtitle_label)

        main_layout.addLayout(title_row)

        # Row 2: Step indicator pills (if steps provided)
        if self._steps:
            main_layout.addSpacing(14)
            self._build_step_indicator(main_layout)
        else:
            main_layout.addStretch()

    def _build_step_indicator(self, parent_layout: QVBoxLayout):
        """Build connected step indicator pills inside the header."""
        steps_row = QHBoxLayout()
        steps_row.setSpacing(0)
        steps_row.setContentsMargins(0, 0, 0, 0)

        steps_row.addStretch()

        self._step_pills = []
        self._step_connectors = []

        for i, step_name in enumerate(self._steps):
            # Step pill
            pill = QLabel(f" {i + 1}. {step_name} ")
            pill.setAlignment(Qt.AlignCenter)
            pill.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            pill.setFixedHeight(28)
            pill.setMinimumWidth(60)
            self._step_pills.append(pill)
            steps_row.addWidget(pill)

            # Connector line between pills (not after last)
            if i < len(self._steps) - 1:
                connector = QFrame()
                connector.setFixedSize(28, 2)
                self._step_connectors.append(connector)
                steps_row.addWidget(connector, 0, Qt.AlignVCenter)

        steps_row.addStretch()

        parent_layout.addLayout(steps_row)
        self._update_step_styles()

    def _update_step_styles(self):
        """Apply styles to step pills based on current step."""
        for i, pill in enumerate(self._step_pills):
            if i < self._current_step:
                pill.setStyleSheet(StyleManager.wizard_step_pill(completed=True))
            elif i == self._current_step:
                pill.setStyleSheet(StyleManager.wizard_step_pill(active=True))
            else:
                pill.setStyleSheet(StyleManager.wizard_step_pill())

        for i, connector in enumerate(self._step_connectors):
            active = i < self._current_step
            connector.setStyleSheet(StyleManager.step_connector(active=active))

    # --- Public API ---

    def set_title(self, title: str):
        """Update title text."""
        self.title_text = title
        self.title_label.setText(title)

    def set_subtitle(self, subtitle: str):
        """Update subtitle text."""
        self.subtitle_text = subtitle
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(subtitle)
            self.subtitle_label.setVisible(bool(subtitle))

    def set_steps(self, steps: list):
        """Set the step names (rebuilds the step indicator)."""
        self._steps = steps
        self._current_step = 0
        # Rebuild step pills if already built
        if self._step_pills:
            for pill in self._step_pills:
                pill.deleteLater()
            for conn in self._step_connectors:
                conn.deleteLater()
            self._step_pills.clear()
            self._step_connectors.clear()
        if steps:
            self.setMinimumHeight(130)
            self._build_step_indicator(self.layout())
        else:
            self.setMinimumHeight(90)

    def set_current_step(self, step: int):
        """Set the currently active step index (0-based)."""
        self._current_step = step
        self._update_step_styles()

    def get_title_label(self) -> QLabel:
        return self.title_label

    # --- Paint (constellation background) ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self._anim_start

        # Dark navy gradient with rounded bottom corners
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
        grad.setColorAt(0.0, QColor("#0E2035"))
        grad.setColorAt(0.5, QColor("#132D50"))
        grad.setColorAt(1.0, QColor("#1A3860"))
        painter.fillPath(path, grad)

        painter.setClipPath(path)

        # Cadastral grid
        painter.setPen(QPen(QColor(56, 144, 223, 16), 1))
        for x in range(60, w, 60):
            painter.drawLine(x, 0, x, h)
        for y in range(60, h, 60):
            painter.drawLine(0, y, w, y)

        # Diamond accents at intersections
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(56, 144, 223, 10))
        for gx in range(60, w, 60):
            for gy in range(60, h, 60):
                painter.save()
                painter.translate(gx, gy)
                painter.rotate(45)
                painter.drawRect(-2, -2, 4, 4)
                painter.restore()

        # Corner bracket accents
        bracket_color = QColor(56, 144, 223, 20)
        painter.setPen(QPen(bracket_color, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(12, 12, 12, 28)
        painter.drawLine(12, 12, 28, 12)
        painter.drawLine(w - 12, h - 14, w - 12, h - 30)
        painter.drawLine(w - 12, h - 14, w - 30, h - 14)

        # Breathing radial glow
        glow_alpha = 18 + int(10 * math.sin(t * 1.0))
        glow = QRadialGradient(w / 2, h * 0.5, w * 0.25)
        glow.setColorAt(0, QColor(56, 144, 223, glow_alpha))
        glow.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            int(w / 2 - w * 0.25), int(h * 0.25),
            int(w * 0.5), int(h * 0.5)
        )

        # Constellation particles
        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.01 * math.sin(t * p["speed"] + p["phase"])) * w)
            py = int((p["y"] + 0.008 * math.cos(t * p["speed"] * 0.7 + p["phase"])) * h)
            px = max(4, min(w - 4, px))
            py = max(4, min(h - 4, py))
            positions.append((px, py))
            alpha = 35 + int(15 * math.sin(t * 1.2 + p["phase"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        # Connecting lines
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 180:
                    alpha = int(12 * (1 - dist / 180))
                    painter.setPen(QPen(QColor(139, 172, 200, alpha), 1))
                    painter.drawLine(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1]
                    )

        painter.setClipping(False)
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
