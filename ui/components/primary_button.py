# -*- coding: utf-8 -*-
"""
Primary Button Component - زر أساسي قابل لإعادة الاستخدام
Reusable button component following Figma design system.

Implements DRY, SOLID, Clean Code principles.
"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt, QSize

from ..design_system import ButtonDimensions
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from .icon import Icon


class PrimaryButton(QPushButton):
    """
    Primary button component with Figma styling.

    Features:
    - Configurable text and icon
    - Hover and pressed states
    - Figma-compliant styling (exact dimensions: 199×48px)
    - Reusable across the application

    Usage:
        btn = PrimaryButton("إضافة حالة جديدة", icon_name="icon")
        btn.clicked.connect(self.on_button_clicked)
    """

    def __init__(self, text: str = "", icon_name: str = None, parent=None):
        """
        Initialize primary button.

        Args:
            text: Button text (Arabic RTL supported)
            icon_name: Icon file name (without extension, looks for .png/.svg in assets/icons)
            parent: Parent widget
        """
        super().__init__(text, parent)
        self.icon_name = icon_name
        self._setup_ui()

    def _setup_ui(self):
        """Setup button UI with Figma specifications (exact: 199×48px)."""

        # Set unique ObjectName for CSS specificity
        self.setObjectName("PrimaryButton")

        # Figma: Exact dimensions (199×48px - no adjustment)
        self.setFixedSize(ButtonDimensions.PRIMARY_WIDTH, ButtonDimensions.PRIMARY_HEIGHT)

        # Cursor
        self.setCursor(Qt.PointingHandCursor)

        # Load icon if provided
        if self.icon_name:
            self._load_icon()

        # Use centralized font utility (DRY + eliminates stylesheet conflicts)
        # Figma: 16px SemiBold → PyQt5: 10pt weight 600
        btn_font = create_font(
            size=FontManager.SIZE_BODY,  # 10pt
            weight=FontManager.WEIGHT_SEMIBOLD,  # 600
            letter_spacing=0,
        )
        self.setFont(btn_font)

        # Apply colors and styling via StyleManager (Single Source of Truth)
        self.setStyleSheet(StyleManager.button_primary())

    def _load_icon(self):
        """Load icon from assets folder using reusable Icon component (DRY + SOLID)."""
        # Use Icon component static method for loading (follows DRY principle)
        q_icon = Icon.load_qicon(self.icon_name)

        if q_icon:
            self.setIcon(q_icon)
            self.setIconSize(QSize(20, 20))  # Icon size for 48px button
        else:
            # If icon not found, log warning but don't fail
            print(f"Warning: Icon '{self.icon_name}' not found in assets folder")
