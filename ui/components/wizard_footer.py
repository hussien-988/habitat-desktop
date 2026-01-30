# -*- coding: utf-8 -*-
"""
Wizard Footer Component - Reusable footer for wizards and multi-step forms.

Follows DRY and SOLID principles.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal

from ui.components.action_button import ActionButton
from ui.font_utils import create_font, FontManager


class WizardFooter(QWidget):
    """
    Reusable wizard footer component.

    Features:
    - Previous/Next navigation buttons
    - Optional cancel and save draft buttons
    - Consistent styling across all wizards

    Signals:
        previous_clicked: Emitted when Previous button is clicked
        next_clicked: Emitted when Next button is clicked
        cancel_clicked: Emitted when Cancel button is clicked
        save_draft_clicked: Emitted when Save Draft button is clicked

    Usage:
        footer = WizardFooter(
            show_cancel=True,
            show_save_draft=False,
            next_text="التالي"
        )
        footer.next_clicked.connect(self._on_next)
    """

    # Signals
    previous_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()
    save_draft_clicked = pyqtSignal()

    def __init__(
        self,
        show_cancel: bool = True,
        show_save_draft: bool = False,
        show_info_label: bool = False,
        next_text: str = "التالي",
        previous_text: str = "السابق",
        parent=None
    ):
        """
        Initialize wizard footer.

        Args:
            show_cancel: Whether to show cancel button
            show_save_draft: Whether to show save draft button
            show_info_label: Whether to show info label (e.g., selection count)
            next_text: Text for next button
            previous_text: Text for previous button
            parent: Parent widget
        """
        super().__init__(parent)
        self.show_cancel = show_cancel
        self.show_save_draft = show_save_draft
        self.show_info_label = show_info_label
        self.next_text = next_text
        self.previous_text = previous_text

        self._setup_ui()

    def _setup_ui(self):
        """Setup footer UI (DRY - extracted from base_wizard.py)."""
        # Same styling as BaseWizard footer
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)

        layout = QHBoxLayout(self)
        # Same padding as BaseWizard: 20px horizontal, 16px vertical
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Left side buttons (Cancel, Save Draft)
        if self.show_cancel:
            self.btn_cancel = ActionButton("إلغاء", variant="secondary", width=114, height=44)
            self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
            layout.addWidget(self.btn_cancel)

        if self.show_save_draft:
            self.btn_save_draft = ActionButton(
                text="حفظ كمسودة",
                variant="secondary",
                icon_name="save",
                width=140,
                height=44
            )
            self.btn_save_draft.clicked.connect(self.save_draft_clicked.emit)
            layout.addWidget(self.btn_save_draft)

        # Info label (e.g., selection count)
        if self.show_info_label:
            self.info_label = QLabel("")
            self.info_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            self.info_label.setStyleSheet("background: transparent; border: none; color: #6c757d;")
            layout.addWidget(self.info_label)

        layout.addStretch()

        # Right side buttons (Previous, Next)
        self.btn_previous = ActionButton(self.previous_text, variant="secondary", width=114, height=44)
        self.btn_previous.clicked.connect(self.previous_clicked.emit)
        layout.addWidget(self.btn_previous)

        self.btn_next = ActionButton(
            text=self.next_text,
            variant="primary",
            icon_name="icon",
            width=114,
            height=44
        )
        self.btn_next.clicked.connect(self.next_clicked.emit)
        layout.addWidget(self.btn_next)

    def set_next_enabled(self, enabled: bool):
        """Enable/disable next button."""
        self.btn_next.setEnabled(enabled)

    def set_previous_enabled(self, enabled: bool):
        """Enable/disable previous button."""
        self.btn_previous.setEnabled(enabled)

    def set_info_text(self, text: str):
        """Set info label text (if enabled)."""
        if self.show_info_label and hasattr(self, 'info_label'):
            self.info_label.setText(text)

    def set_next_text(self, text: str):
        """Update next button text."""
        self.btn_next.setText(text)
