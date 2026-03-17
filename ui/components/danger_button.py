# -*- coding: utf-8 -*-
"""
Danger Button Component - زر خطر قابل لإعادة الاستخدام
Reusable danger button component for destructive actions.

"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt

from ..style_manager import StyleManager
from ..font_utils import create_font, FontManager


class DangerButton(QPushButton):
    """Reusable danger button for destructive actions."""

    def __init__(self, text: str = "", parent=None):
        """Initialize danger button."""
        super().__init__(text, parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup button UI."""
        # Set unique ObjectName for CSS specificity
        self.setObjectName("DangerButton")

        # Cursor
        self.setCursor(Qt.PointingHandCursor)

        # Use centralized font utility
        btn_font = create_font(
            size=FontManager.SIZE_BODY,  # 10pt
            weight=FontManager.WEIGHT_MEDIUM,  # 500
            letter_spacing=0
        )
        self.setFont(btn_font)

        # Apply colors and styling via StyleManager (Single Source of Truth)
        self.setStyleSheet(StyleManager.button_danger())
