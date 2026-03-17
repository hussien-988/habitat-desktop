# -*- coding: utf-8 -*-
"""Primary Button Component - زر أساسي قابل لإعادة الاستخدام."""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt, QSize

from ..design_system import ButtonDimensions
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from .icon import Icon


class PrimaryButton(QPushButton):
    """Reusable primary button with icon support."""

    def __init__(self, text: str = "", icon_name: str = None, parent=None):
        """Initialize primary button."""
        super().__init__(text, parent)
        self.icon_name = icon_name
        self._setup_ui()

    def _setup_ui(self):
        """Setup button UI."""

        # Set unique ObjectName for CSS specificity
        self.setObjectName("PrimaryButton")

        # Fixed height, auto width based on content
        self.setFixedHeight(ButtonDimensions.PRIMARY_HEIGHT)

        # Cursor
        self.setCursor(Qt.PointingHandCursor)

        # Load icon if provided
        if self.icon_name:
            self._load_icon()

        btn_font = create_font(
            size=11,
            weight=FontManager.WEIGHT_SEMIBOLD,
            letter_spacing=0,
        )
        self.setFont(btn_font)

        # Apply colors and styling via StyleManager (Single Source of Truth)
        self.setStyleSheet(StyleManager.button_primary())

    def _load_icon(self):
        """Load icon from assets folder using reusable Icon component."""
        q_icon = Icon.load_qicon(self.icon_name)

        if q_icon:
            self.setIcon(q_icon)
            self.setIconSize(QSize(20, 20))  # Icon size for 48px button
        else:
            pass
