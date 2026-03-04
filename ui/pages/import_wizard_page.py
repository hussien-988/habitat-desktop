# -*- coding: utf-8 -*-
"""
Import Wizard Page - Stub
=========================
Placeholder for bulk data import functionality (CSV/Excel).
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

from app.config import Config


class ImportWizardPage(QWidget):
    """Stub page for Import Wizard - to be implemented."""

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("📥")
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("معالج الاستيراد")
        title.setStyleSheet(f"font-size: 20pt; font-weight: 700; color: {Config.PRIMARY_COLOR};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("سيتم إضافة هذه الميزة قريباً\nاستيراد البيانات من ملفات CSV / Excel")
        subtitle.setStyleSheet("font-size: 11pt; color: #666; margin-top: 12px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

    def refresh(self, data=None):
        pass
