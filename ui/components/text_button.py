# -*- coding: utf-8 -*-
"""Text Button Component - زر نصي قابل لإعادة الاستخدام."""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt

from ..style_manager import StyleManager
from ..font_utils import create_font, FontManager


class TextButton(QPushButton):
    """Reusable text-only button."""

    def __init__(self, text: str = "", parent=None):
        """Initialize text button."""
        super().__init__(text, parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup button UI."""
        # Set unique ObjectName for CSS specificity
        self.setObjectName("TextButton")

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
        self.setStyleSheet(StyleManager.button_text())
