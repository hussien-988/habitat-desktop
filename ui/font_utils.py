# -*- coding: utf-8 -*-
"""
Font Utilities - أدوات الخطوط
Centralized font management following DRY, SOLID, Clean Code principles.

This module provides a single source of truth for font configuration
and eliminates stylesheet conflicts by using QFont directly.

Best Practice:
    ALWAYS use these utility functions instead of:
    - Setting fonts in QSS (causes conflicts)
    - Creating QFont instances manually (violates DRY)
    - Using QFont constructor with font name (unreliable)

Usage:
    from ui.font_utils import apply_default_font, create_font

    # Apply default font to any widget
    apply_default_font(widget)

    # Create custom font
    font = create_font(size=18, weight=QFont.Bold)
    widget.setFont(font)
"""

from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QWidget, QApplication
from typing import Optional, List


class FontManager:
    """
    Centralized font manager following Singleton pattern.

    Responsibilities (Single Responsibility Principle):
    - Load and register custom fonts
    - Provide consistent font configuration
    - Apply fonts to widgets and application
    """

    # Font configuration (Single Source of Truth - DRY)
    PRIMARY_FONT_FAMILY = "IBM Plex Sans Arabic"
    FALLBACK_FONT_FAMILY = "Calibri"

    # Default sizes (in points)
    SIZE_SMALL = 8
    SIZE_BODY = 10
    SIZE_SUBHEADING = 12
    SIZE_HEADING = 14
    SIZE_TITLE = 18
    SIZE_LARGE_TITLE = 24

    # Weights
    WEIGHT_LIGHT = 300
    WEIGHT_REGULAR = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_SEMIBOLD = 600
    WEIGHT_BOLD = 700

    _instance = None
    _initialized = False

    def __new__(cls):
        """Singleton pattern - one instance only."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize font manager (only once)."""
        if not FontManager._initialized:
            self._load_custom_fonts()
            FontManager._initialized = True

    def _load_custom_fonts(self):
        """Load custom font files from resources."""
        # TODO: Load custom font files if they exist
        # Example:
        # font_paths = [
        #     "resources/fonts/IBMPlexSansArabic-Regular.ttf",
        #     "resources/fonts/IBMPlexSansArabic-Bold.ttf",
        # ]
        # for font_path in font_paths:
        #     if os.path.exists(font_path):
        #         QFontDatabase.addApplicationFont(font_path)
        pass

    @staticmethod
    def create_font(
        size: int = SIZE_BODY,
        weight: int = WEIGHT_REGULAR,
        letter_spacing: float = 0.0,
        families: Optional[List[str]] = None
    ) -> QFont:
        """
        Create a QFont with proper configuration (DRY - Single Source of Truth).

        Args:
            size: Font size in points (default: 10pt)
            weight: Font weight (default: 400)
            letter_spacing: Letter spacing in pixels (default: 0)
            families: Custom font family list (default: uses PRIMARY_FONT_FAMILY)

        Returns:
            Configured QFont instance

        Example:
            font = FontManager.create_font(size=18, weight=QFont.Bold)
            label.setFont(font)
        """
        if families is None:
            families = [
                FontManager.PRIMARY_FONT_FAMILY,
                FontManager.FALLBACK_FONT_FAMILY
            ]

        font = QFont()
        font.setFamilies(families)
        font.setPointSize(size)
        font.setWeight(weight)
        font.setLetterSpacing(QFont.AbsoluteSpacing, letter_spacing)

        return font

    @staticmethod
    def apply_to_widget(
        widget: QWidget,
        size: int = SIZE_BODY,
        weight: int = WEIGHT_REGULAR,
        letter_spacing: float = 0.0
    ):
        """
        Apply font to a widget (convenience method).

        Args:
            widget: Widget to apply font to
            size: Font size in points
            weight: Font weight
            letter_spacing: Letter spacing in pixels

        Example:
            FontManager.apply_to_widget(label, size=18, weight=QFont.Bold)
        """
        font = FontManager.create_font(size, weight, letter_spacing)
        widget.setFont(font)

    @staticmethod
    def set_application_default():
        """
        Set default font for entire application.

        This should be called once at application startup in main.py.

        Example:
            app = QApplication(sys.argv)
            FontManager.set_application_default()
        """
        default_font = FontManager.create_font()
        QApplication.setFont(default_font)


# Convenience functions (Facade Pattern - simplify interface)

def create_font(
    size: int = FontManager.SIZE_BODY,
    weight: int = FontManager.WEIGHT_REGULAR,
    letter_spacing: float = 0.0,
    families: Optional[List[str]] = None
) -> QFont:
    """
    Create a font with proper configuration.

    Convenience wrapper for FontManager.create_font().

    Args:
        size: Font size in points (default: 10pt)
        weight: Font weight (default: 400)
        letter_spacing: Letter spacing in pixels (default: 0)
        families: Custom font family list

    Returns:
        Configured QFont instance

    Example:
        from ui.font_utils import create_font
        from PyQt5.QtGui import QFont

        title_font = create_font(size=18, weight=QFont.Bold)
        label.setFont(title_font)
    """
    return FontManager.create_font(size, weight, letter_spacing, families)


def apply_font_to_widget(
    widget: QWidget,
    size: int = FontManager.SIZE_BODY,
    weight: int = FontManager.WEIGHT_REGULAR,
    letter_spacing: float = 0.0
):
    """
    Apply font to a widget.

    Convenience wrapper for FontManager.apply_to_widget().

    Args:
        widget: Widget to apply font to
        size: Font size in points
        weight: Font weight
        letter_spacing: Letter spacing in pixels

    Example:
        from ui.font_utils import apply_font_to_widget
        from PyQt5.QtGui import QFont

        apply_font_to_widget(label, size=18, weight=QFont.Bold)
    """
    FontManager.apply_to_widget(widget, size, weight, letter_spacing)


def set_application_default_font():
    """
    Set default font for entire application.

    Should be called once at application startup.

    Example:
        from ui.font_utils import set_application_default_font

        app = QApplication(sys.argv)
        set_application_default_font()
    """
    FontManager.set_application_default()


# Initialize FontManager singleton
_font_manager = FontManager()
