# -*- coding: utf-8 -*-
"""
Input Field Component - حقل إدخال قابل لإعادة الاستخدام
Reusable input field component.
"""

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt

from ..style_manager import StyleManager, InputVariant
from ..font_utils import create_font, FontManager


class InputField(QLineEdit):
    """Reusable input field component with variant styling."""

    def __init__(self, placeholder: str = "", variant: str = "default", parent=None):
        """Initialize input field."""
        super().__init__(parent)
        self.variant = variant
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        """Setup input field UI."""
        if placeholder:
            self.setPlaceholderText(placeholder)

        # Use centralized font utility
        input_font = create_font(
            size=FontManager.SIZE_BODY,  # 10pt
            weight=FontManager.WEIGHT_REGULAR,  # 400
            letter_spacing=0,
        )
        self.setFont(input_font)

        # Apply variant-specific styling via StyleManager
        self._apply_variant()

    def _apply_variant(self):
        """Apply variant-specific styling."""
        if self.variant == "error":
            self.setStyleSheet(StyleManager.input_field(InputVariant.ERROR))
        elif self.variant == "success":
            self.setStyleSheet(StyleManager.input_field(InputVariant.SUCCESS))
        else:
            self.setStyleSheet(StyleManager.input_field(InputVariant.DEFAULT))

    def set_variant(self, variant: str):
        """Change input variant dynamically."""
        self.variant = variant
        self._apply_variant()

    def set_error(self):
        """Set input to error state (convenience method)."""
        self.set_variant("error")

    def set_success(self):
        """Set input to success state (convenience method)."""
        self.set_variant("success")

    def set_default(self):
        """Reset input to default state (convenience method)."""
        self.set_variant("default")
