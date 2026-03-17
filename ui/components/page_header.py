# -*- coding: utf-8 -*-
"""
Page Header Component - رأس الصفحة القابل لإعادة الاستخدام
Reusable page header component with title and optional add button.

"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ..design_system import Colors, PageDimensions
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from .primary_button import PrimaryButton


class PageHeader(QWidget):
    """Page header component with title and optional add button."""

    add_clicked = pyqtSignal()

    def __init__(
        self,
        title: str = "",
        show_add_button: bool = False,
        button_text: str = "إضافة حالة جديدة",
        button_icon: str = "icon",
        parent=None
    ):
        """Initialize page header."""
        super().__init__(parent)
        self.title_text = title
        self.show_add_button = show_add_button
        self.button_text = button_text
        self.button_icon = button_icon
        self._setup_ui()

    def _setup_ui(self):
        """Setup header UI."""
        self.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        self.setStyleSheet(StyleManager.page_header())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # No extra padding
        layout.setSpacing(16)

        # Page title
        self.title_label = QLabel(self.title_text)

        title_font = create_font(
            size=FontManager.SIZE_TITLE,  # 18pt
            weight=QFont.Bold,             # 700
            letter_spacing=0
        )
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(StyleManager.label_title())
        layout.addWidget(self.title_label)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Add button (optional)
        if self.show_add_button:
            add_btn = PrimaryButton(self.button_text, icon_name=self.button_icon)
            add_btn.clicked.connect(self.add_clicked.emit)
            layout.addWidget(add_btn)

    def set_title(self, title: str):
        """Update page title dynamically."""
        self.title_text = title
        self.title_label.setText(title)

    def show_button(self, show: bool = True):
        """Show/hide add button dynamically."""
        pass
