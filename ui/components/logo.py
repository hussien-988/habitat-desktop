# -*- coding: utf-8 -*-
"""
UN-HABITAT Logo Component - Reusable Logo Widget
مكون شعار الأمم المتحدة للموئل - قابل لإعادة الاستخدام

This component displays the UN-HABITAT logo with exact Figma specifications.
Specifications from Figma:
- Default size: 142.77×21.77 (Figma)
- Scaled for PyQt5: height=22px for visual balance
- Supports custom scaling
- Loads from assets/images/header.png
"""

from pathlib import Path
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QFont

from ..design_system import NavbarDimensions


class LogoWidget(QLabel):
    """
    Reusable UN-HABITAT Logo Widget

    Usage:
        logo = LogoWidget()  # Default size
        logo = LogoWidget(height=30)  # Custom height
        logo = LogoWidget(scale_factor=1.5)  # Scale by factor
    """

    def __init__(self, height=None, scale_factor=1.0, fallback_text="UN-HABITAT", parent=None):
        """
        Initialize logo widget

        Args:
            height: Custom height in pixels (overrides scale_factor)
            scale_factor: Scale multiplier for default size (default: 1.0)
            fallback_text: Text to display if image not found
            parent: Parent widget
        """
        super().__init__(parent)

        self.fallback_text = fallback_text

        # Determine final height
        if height is not None:
            self.logo_height = height
        else:
            self.logo_height = int(NavbarDimensions.LOGO_SCALED_HEIGHT * scale_factor)

        self._setup_logo()

    def _setup_logo(self):
        """Setup logo image or fallback text"""
        # Try to load logo image from assets
        logo_path = Path(__file__).parent.parent.parent / "assets" / "images" / "header.png"

        if logo_path.exists():
            # Load and scale logo image
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaledToHeight(
                self.logo_height,
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        else:
            # Fallback to text if image not found
            self.setText(self.fallback_text)

            # Fallback font styling
            font = QFont("IBM Plex Sans Arabic", 10, QFont.Bold)
            self.setFont(font)

        # Transparent background
        self.setStyleSheet("""
            QLabel {
                background: transparent;
            }
        """)

    def set_height(self, height):
        """
        Update logo height dynamically

        Args:
            height: New height in pixels
        """
        self.logo_height = height
        self._setup_logo()

    def set_scale(self, scale_factor):
        """
        Update logo scale dynamically

        Args:
            scale_factor: Scale multiplier for default size
        """
        self.logo_height = int(NavbarDimensions.LOGO_SCALED_HEIGHT * scale_factor)
        self._setup_logo()
