# -*- coding: utf-8 -*-
"""
Wizard Header Component - Reusable header for wizards and multi-step forms.

Follows DRY and SOLID principles.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.font_utils import create_font, FontManager


class WizardHeader(QWidget):
    """
    Reusable wizard header component.

    Features:
    - Title display
    - Subtitle/breadcrumb support
    - Consistent styling across all wizards

    Usage:
        header = WizardHeader(
            title="تجهيز العمل الميداني",
            subtitle="المباني  •  تجهيز العمل الميداني"
        )
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent=None
    ):
        """
        Initialize wizard header.

        Args:
            title: Main title text
            subtitle: Optional subtitle/breadcrumb text
            parent: Parent widget
        """
        super().__init__(parent)
        self.title_text = title
        self.subtitle_text = subtitle

        self._setup_ui()

    def _setup_ui(self):
        """Setup header UI (DRY - extracted from base_wizard.py)."""
        # Same styling as BaseWizard header
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)

        layout = QVBoxLayout(self)
        # Same padding as BaseWizard: 20px horizontal, 16px vertical
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)  # Gap between title and subtitle

        # Title (same style as BaseWizard)
        self.title_label = QLabel(self.title_text)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("background: transparent; border: none; color: #212529;")
        layout.addWidget(self.title_label)

        # Subtitle/breadcrumb (if provided)
        if self.subtitle_text:
            self.subtitle_label = QLabel(self.subtitle_text)
            self.subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            self.subtitle_label.setStyleSheet("background: transparent; border: none; color: #6c757d;")
            layout.addWidget(self.subtitle_label)

    def set_title(self, title: str):
        """Update title text."""
        self.title_text = title
        self.title_label.setText(title)

    def set_subtitle(self, subtitle: str):
        """Update subtitle text."""
        self.subtitle_text = subtitle
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(subtitle)
