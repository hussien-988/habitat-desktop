# -*- coding: utf-8 -*-
"""Action Button Component - Reusable button with consistent styling."""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import QSize, Qt

from .icon import Icon
from ui.design_system import ScreenScale


class ActionButton(QPushButton):
    """Reusable action button supporting primary, secondary, and outline variants."""

    def __init__(
        self,
        text: str,
        variant: str = "primary",
        icon_name: str = None,
        width: int = 114,
        height: int = 44,
        parent=None
    ):
        """Initialize action button."""
        super().__init__(text, parent)

        self.setFixedSize(ScreenScale.w(width), ScreenScale.h(height))

        # Store variant for icon coloring
        self.variant = variant

        # Load icon if provided
        if icon_name:
            icon_pixmap = Icon.load_pixmap(icon_name, size=16)
            if icon_pixmap and not icon_pixmap.isNull():
                # Color the icon based on variant
                colored_pixmap = self._colorize_icon(icon_pixmap, variant)
                self.setIcon(QIcon(colored_pixmap))
                # Set icon size for proper spacing between icon and text
                self.setIconSize(QSize(16, 16))

        # Apply variant styling
        self._apply_style(variant)

    def _apply_style(self, variant: str):
        """Apply button styling based on variant."""
        if variant == "primary":
            # Primary: Blue solid
            self.setStyleSheet("""
                QPushButton {
                    background-color: #0d6efd;
                    color: white;
                    border: none;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 13px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #0b5ed7;
                }
                QPushButton:disabled {
                    background-color: #6c757d;
                    opacity: 0.6;
                }
            """)
        elif variant == "secondary":
            # Secondary: Gray
            self.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 13px;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #5c636a;
                }
                QPushButton:disabled {
                    background-color: #adb5bd;
                    opacity: 0.6;
                }
            """)
        elif variant == "outline":
            # Outline: Light blue background with blue border
            self.setStyleSheet("""
                QPushButton {
                    background-color: #F0F7FF;
                    color: #3890DF;
                    border: 1px solid #3890DF;
                    padding: 8px 12px;
                    border-radius: 8px;
                    font-size: 10.5pt;
                    text-align: center;
                }
                QPushButton:hover {
                    background-color: #E0EAFF;
                    border-color: #2870BF;
                }
                QPushButton:disabled {
                    background-color: #F8F9FA;
                    color: #ADB5BD;
                    border-color: #DEE2E6;
                    opacity: 0.6;
                }
            """)
        else:
            raise ValueError(f"Invalid variant: {variant}. Must be 'primary', 'secondary', or 'outline'")

    def _colorize_icon(self, pixmap: QPixmap, variant: str) -> QPixmap:
        """Colorize icon based on button variant."""
        # Determine target color based on variant
        if variant == "primary":
            color = QColor("#FFFFFF")  # White for primary
        elif variant == "secondary":
            color = QColor("#FFFFFF")  # White for secondary
        elif variant == "outline":
            color = QColor("#3890DF")  # Blue for outline
        else:
            return pixmap  # Return original if unknown variant

        # Create a new pixmap with the same size
        colored_pixmap = QPixmap(pixmap.size())
        colored_pixmap.fill(Qt.transparent)

        # Use QPainter to draw the colored version
        painter = QPainter(colored_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(colored_pixmap.rect(), color)
        painter.end()

        return colored_pixmap
