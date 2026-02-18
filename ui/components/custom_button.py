# -*- coding: utf-8 -*-
"""
Reusable custom button component.
"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt


class CustomButton(QPushButton):
    """
    Reusable custom button with predefined styles.

    Usage:
        # Primary button (blue solid)
        btn = CustomButton.primary("إضافة بناء جديد", parent)
        btn.clicked.connect(callback)

        # Secondary button (transparent with blue border)
        btn = CustomButton.secondary("تجهيز عمل ميداني", parent)

        # Danger button (red solid)
        btn = CustomButton.danger("حذف", parent)

        # Success button (green solid)
        btn = CustomButton.success("حفظ", parent)

        # Custom button
        btn = CustomButton("نص الزر", parent, bg_color="#3498db", text_color="white")
    """

    # Predefined styles
    PRIMARY = {"bg": "#3498db", "hover": "#2980b9", "text": "white"}
    SECONDARY = {"bg": "transparent", "hover": "#e3f2fd", "text": "#3498db", "border": "#3498db"}
    DANGER = {"bg": "#e74c3c", "hover": "#c0392b", "text": "white"}
    SUCCESS = {"bg": "#27ae60", "hover": "#229954", "text": "white"}
    WARNING = {"bg": "#f39c12", "hover": "#e67e22", "text": "white"}

    def __init__(self, text, parent=None, width=160, height=45,
                 bg_color="#3498db", hover_color=None, text_color="white",
                 border_color=None, icon=None):
        """
        Create a custom button.

        Args:
            text: Button text
            parent: Parent widget
            width: Button width
            height: Button height
            bg_color: Background color
            hover_color: Hover background color (auto-calculated if None)
            text_color: Text color
            border_color: Border color (None for no border)
            icon: Icon text (emoji) to show before text
        """
        super().__init__(parent)

        # Add icon if provided
        display_text = f"{icon}  {text}" if icon else text
        self.setText(display_text)

        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)

        # Auto-calculate hover color if not provided
        if hover_color is None:
            hover_color = self._darken_color(bg_color) if bg_color != "transparent" else "#f0f0f0"

        # Build stylesheet
        border_style = f"border: 2px solid {border_color};" if border_color else "border: none;"

        stylesheet = f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                {border_style}
                border-radius: 8px;
                font-size: 10pt;
                font-weight: 600;
                padding: 0px 15px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(hover_color)};
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #7f8c8d;
                border: none;
            }}
        """
        self.setStyleSheet(stylesheet)

    def _darken_color(self, color):
        """Darken a hex color by 10%."""
        if color == "transparent":
            return "#e0e0e0"

        try:
            # Remove # if present
            color = color.lstrip('#')

            # Convert to RGB
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)

            # Darken by 10%
            r = max(0, int(r * 0.9))
            g = max(0, int(g * 0.9))
            b = max(0, int(b * 0.9))

            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return "#2c3e50"

    @classmethod
    def primary(cls, text, parent=None, width=160, height=45, icon=None):
        """Create a primary button (blue solid)."""
        style = cls.PRIMARY
        return cls(text, parent, width, height,
                  bg_color=style["bg"],
                  hover_color=style["hover"],
                  text_color=style["text"],
                  icon=icon)

    @classmethod
    def secondary(cls, text, parent=None, width=160, height=45, icon=None):
        """Create a secondary button (transparent with blue border)."""
        style = cls.SECONDARY
        return cls(text, parent, width, height,
                  bg_color=style["bg"],
                  hover_color=style["hover"],
                  text_color=style["text"],
                  border_color=style["border"],
                  icon=icon)

    @classmethod
    def danger(cls, text, parent=None, width=120, height=40, icon=None):
        """Create a danger button (red solid)."""
        style = cls.DANGER
        return cls(text, parent, width, height,
                  bg_color=style["bg"],
                  hover_color=style["hover"],
                  text_color=style["text"],
                  icon=icon)

    @classmethod
    def success(cls, text, parent=None, width=120, height=40, icon=None):
        """Create a success button (green solid)."""
        style = cls.SUCCESS
        return cls(text, parent, width, height,
                  bg_color=style["bg"],
                  hover_color=style["hover"],
                  text_color=style["text"],
                  icon=icon)

    @classmethod
    def warning(cls, text, parent=None, width=120, height=40, icon=None):
        """Create a warning button (orange solid)."""
        style = cls.WARNING
        return cls(text, parent, width, height,
                  bg_color=style["bg"],
                  hover_color=style["hover"],
                  text_color=style["text"],
                  icon=icon)
