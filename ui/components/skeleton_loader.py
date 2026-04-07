# -*- coding: utf-8 -*-
"""Shimmer skeleton loading placeholders."""

import random

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtProperty
from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QBrush

from ui.design_system import (
    SkeletonColors, AnimationTimings, Colors, BorderRadius,
    Typography, Spacing
, ScreenScale, ScreenScale)
from services.translation_manager import get_layout_direction


class _ShimmerBar(QWidget):
    """Single animated skeleton bar with diagonal shimmer sweep."""

    def __init__(self, width_pct: float = 1.0, height: int = 14,
                 radius: int = SkeletonColors.BORDER_RADIUS, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._width_pct = width_pct
        self._bar_height = height
        self._radius = radius
        self.setFixedHeight(height)
        if width_pct < 1.0:
            self.setMaximumWidth(int(300 * width_pct))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _get_phase(self):
        return self._phase

    def _set_phase(self, val):
        self._phase = val
        self.update()

    phase = pyqtProperty(float, _get_phase, _set_phase)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        bar_w = int(w * self._width_pct)

        is_rtl = get_layout_direction() == Qt.RightToLeft
        if is_rtl:
            x_start = w - bar_w
        else:
            x_start = 0

        rect = QRectF(x_start, 0, bar_w, h)

        base_color = QColor(SkeletonColors.BASE)
        shimmer_color = QColor(SkeletonColors.SHIMMER)

        gradient = QLinearGradient(rect.left() - bar_w, 0,
                                   rect.right() + bar_w, 0)
        phase = self._phase

        gradient.setColorAt(0.0, base_color)
        gradient.setColorAt(max(0.0, phase - 0.15), base_color)
        gradient.setColorAt(phase, shimmer_color)
        gradient.setColorAt(min(1.0, phase + 0.15), base_color)
        gradient.setColorAt(1.0, base_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, self._radius, self._radius)
        painter.end()


class SkeletonBase(QFrame):
    """Base skeleton with shimmer animation loop."""

    def __init__(self, message: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("skeleton_loader")
        self._bars = []
        self._phase = 0.0
        self._message = message

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

        self.setStyleSheet(f"""
            QFrame#skeleton_loader {{
                background: transparent;
                border: none;
            }}
        """)

    def _register_bar(self, bar: _ShimmerBar):
        self._bars.append(bar)

    def _tick(self):
        self._phase += 0.02
        if self._phase > 1.3:
            self._phase = -0.3
        for bar in self._bars:
            bar.phase = max(0.0, min(1.0, self._phase))

    def start(self):
        self._phase = -0.3
        self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()


class TableSkeleton(SkeletonBase):
    """Table-shaped skeleton with header + rows."""

    def __init__(self, columns: int = 4, rows: int = 6,
                 message: str = "", parent=None):
        super().__init__(message, parent)
        self._build(columns, rows, message)

    def _build(self, columns: int, rows: int, message: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayoutDirection(get_layout_direction())

        if message:
            msg_label = QLabel(message)
            msg_label.setAlignment(Qt.AlignCenter)
            msg_label.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.SIZE_BODY}px;
                padding: {Spacing.SM}px;
                background: transparent;
            """)
            layout.addWidget(msg_label)
            layout.addSpacing(Spacing.SM)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.LG}px;
            }}
        """)
        grid = QGridLayout(container)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        for col in range(columns):
            bar = _ShimmerBar(
                width_pct=random.uniform(0.5, 0.9),
                height=12
            )
            bar.setStyleSheet("")
            grid.addWidget(bar, 0, col)
            self._register_bar(bar)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background: {Colors.BORDER_DEFAULT};")
        grid.addWidget(separator, 1, 0, 1, columns)

        for row_idx in range(rows):
            for col in range(columns):
                bar = _ShimmerBar(
                    width_pct=random.uniform(0.3, 0.95),
                    height=14
                )
                grid.addWidget(bar, row_idx + 2, col)
                self._register_bar(bar)

        layout.addWidget(container)


class CardSkeleton(SkeletonBase):
    """Card-shaped skeleton for card-based layouts."""

    def __init__(self, cards: int = 4, message: str = "", parent=None):
        super().__init__(message, parent)
        self._build(cards, message)

    def _build(self, cards: int, message: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)
        self.setLayoutDirection(get_layout_direction())

        if message:
            msg_label = QLabel(message)
            msg_label.setAlignment(Qt.AlignCenter)
            msg_label.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.SIZE_BODY}px;
                background: transparent;
            """)
            layout.addWidget(msg_label)

        grid = QGridLayout()
        grid.setSpacing(Spacing.MD)

        for i in range(cards):
            card = QFrame()
            card.setFixedHeight(ScreenScale.h(120))
            card.setStyleSheet(f"""
                QFrame {{
                    background: {Colors.SURFACE};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {BorderRadius.MD}px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(10)

            title_bar = _ShimmerBar(width_pct=0.6, height=16)
            self._register_bar(title_bar)
            card_layout.addWidget(title_bar)

            for _ in range(2):
                line = _ShimmerBar(
                    width_pct=random.uniform(0.4, 0.9),
                    height=12
                )
                self._register_bar(line)
                card_layout.addWidget(line)

            card_layout.addStretch()

            row = i // 2
            col = i % 2
            grid.addWidget(card, row, col)

        layout.addLayout(grid)


class DetailSkeleton(SkeletonBase):
    """Detail page skeleton with header + field groups."""

    def __init__(self, groups: int = 3, fields_per_group: int = 3,
                 message: str = "", parent=None):
        super().__init__(message, parent)
        self._build(groups, fields_per_group, message)

    def _build(self, groups: int, fields_per_group: int, message: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.LG)
        self.setLayoutDirection(get_layout_direction())

        if message:
            msg_label = QLabel(message)
            msg_label.setAlignment(Qt.AlignCenter)
            msg_label.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.SIZE_BODY}px;
                background: transparent;
            """)
            layout.addWidget(msg_label)

        title_bar = _ShimmerBar(width_pct=0.4, height=24)
        self._register_bar(title_bar)
        layout.addWidget(title_bar)

        for _ in range(groups):
            group = QFrame()
            group.setStyleSheet(f"""
                QFrame {{
                    background: {Colors.SURFACE};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {BorderRadius.MD}px;
                }}
            """)
            g_layout = QVBoxLayout(group)
            g_layout.setContentsMargins(16, 14, 16, 14)
            g_layout.setSpacing(12)

            section_title = _ShimmerBar(width_pct=0.3, height=14)
            self._register_bar(section_title)
            g_layout.addWidget(section_title)

            for _ in range(fields_per_group):
                row = QHBoxLayout()
                row.setSpacing(12)

                label = _ShimmerBar(width_pct=0.25, height=12)
                self._register_bar(label)
                row.addWidget(label)

                value = _ShimmerBar(
                    width_pct=random.uniform(0.4, 0.7),
                    height=12
                )
                self._register_bar(value)
                row.addWidget(value)

                g_layout.addLayout(row)

            layout.addWidget(group)

        layout.addStretch()
