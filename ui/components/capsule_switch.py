# -*- coding: utf-8 -*-
"""Pill-shaped segmented switch for dark header zones."""

from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor, QFont

from ui.font_utils import create_font
from ui.design_system import ScreenScale


class CapsuleSwitch(QFrame):
    """Row of capsule options; the current one is filled blue.

    Clicking emits `clicked(key)` without changing the selection: the owner
    calls `set_current()` once it accepts the change (e.g. not while loading).
    """

    clicked = pyqtSignal(object)

    def __init__(self, options, parent=None):
        """options: list of (key, text) in display order."""
        super().__init__(parent)
        self.setObjectName("capsule_switch")
        height = ScreenScale.h(36)
        self.setFixedHeight(height)
        # Hug the option texts instead of stretching across the header row
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QFrame#capsule_switch {{
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(120, 190, 255, 0.25);
                border-radius: {height // 2}px;
            }}
            QFrame#capsule_switch QPushButton {{
                background: transparent;
                color: rgba(200, 220, 240, 0.80);
                border: none;
                border-radius: {(height - 6) // 2}px;
                padding: 0 18px;
            }}
            QFrame#capsule_switch QPushButton:hover {{
                color: white;
            }}
            QFrame#capsule_switch QPushButton[current="true"] {{
                background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                    stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
                color: white;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self._buttons = {}
        for key, text in options:
            btn = QPushButton(text)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setFixedHeight(height - 6)
            btn.setFont(create_font(size=11, weight=QFont.DemiBold))
            btn.setProperty("current", False)
            btn.clicked.connect(lambda _=False, k=key: self.clicked.emit(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

    def set_current(self, key):
        for k, btn in self._buttons.items():
            btn.setProperty("current", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_text(self, key, text: str):
        self._buttons[key].setText(text)
