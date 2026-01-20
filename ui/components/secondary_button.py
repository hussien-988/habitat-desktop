# -*- coding: utf-8 -*-
"""
Secondary Button Component - زر ثانوي قابل لإعادة الاستخدام
Reusable secondary button component following Figma design system.

Implements DRY, SOLID, Clean Code principles.
"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt

from ..style_manager import StyleManager
from ..font_utils import create_font, FontManager


class SecondaryButton(QPushButton):
    """
    Secondary button component with Figma styling.

    Features:
    - Border style with transparent background
    - Configurable text
    - Hover and pressed states
    - Figma-compliant styling
    - Reusable across the application

    Usage:
        btn = SecondaryButton("إلغاء")
        btn.clicked.connect(self.on_cancel)
    """

    def __init__(self, text: str = "", parent=None):
        """
        Initialize secondary button.

        Args:
            text: Button text (Arabic RTL supported)
            parent: Parent widget
        """
        super().__init__(text, parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup button UI with Figma specifications."""
        # Set unique ObjectName for CSS specificity
        self.setObjectName("SecondaryButton")

        # Cursor
        self.setCursor(Qt.PointingHandCursor)

        # Use centralized font utility (DRY + eliminates stylesheet conflicts)
        btn_font = create_font(
            size=FontManager.SIZE_BODY,  # 10pt
            weight=FontManager.WEIGHT_MEDIUM,  # 500
            letter_spacing=0
        )
        self.setFont(btn_font)

        # Apply colors and styling via StyleManager (Single Source of Truth)
        self.setStyleSheet(StyleManager.button_secondary())
