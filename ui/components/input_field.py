# -*- coding: utf-8 -*-
"""
Input Field Component - حقل إدخال قابل لإعادة الاستخدام
Reusable input field component following Figma design system.

Implements DRY, SOLID, Clean Code principles.
"""

from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtCore import Qt

from ..style_manager import StyleManager, InputVariant
from ..font_utils import create_font, FontManager


class InputField(QLineEdit):
    """
    Input field component with Figma styling.

    Features:
    - Configurable placeholder
    - Error/success states
    - Figma-compliant styling (border, padding, colors)
    - Reusable across the application

    Usage:
        # Default input
        field = InputField(placeholder="أدخل الاسم...")

        # Error state
        field = InputField(placeholder="البريد الإلكتروني...", variant="error")

        # Success state
        field = InputField(placeholder="كلمة المرور...", variant="success")
    """

    def __init__(self, placeholder: str = "", variant: str = "default", parent=None):
        """
        Initialize input field.

        Args:
            placeholder: Placeholder text (Arabic RTL supported)
            variant: Input variant ("default", "error", "success")
            parent: Parent widget
        """
        super().__init__(parent)
        self.variant = variant
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        """Setup input field UI with Figma specifications."""
        # Set placeholder
        if placeholder:
            self.setPlaceholderText(placeholder)

        # Use centralized font utility (DRY + eliminates stylesheet conflicts)
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
        """
        Change input variant dynamically.

        Args:
            variant: New variant ("default", "error", "success")
        """
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
