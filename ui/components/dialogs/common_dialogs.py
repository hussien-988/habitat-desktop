# -*- coding: utf-8 -*-
"""
Common dialog components.
"""
from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QWidget
)
from PyQt5.QtCore import Qt


class BaseDialog(QDialog):
    """Base dialog with consistent styling."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        # Remove question mark button on Windows
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

    def _create_button_row(self, buttons: list[QPushButton]) -> QWidget:
        """Create a row of buttons."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.addStretch()

        for btn in buttons:
            layout.addWidget(btn)

        return widget


class ConfirmDialog(BaseDialog):
    """Confirmation dialog with Yes/No buttons."""

    def __init__(self, title: str, message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._setup_ui(message)

    def _setup_ui(self, message: str) -> None:
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # Buttons
        self.yes_btn = QPushButton("Yes")
        self.yes_btn.clicked.connect(self.accept)

        self.no_btn = QPushButton("No")
        self.no_btn.setProperty("class", "secondary")
        self.no_btn.clicked.connect(self.reject)
        self.no_btn.setDefault(True)

        layout.addWidget(self._create_button_row([self.no_btn, self.yes_btn]))

    @classmethod
    def confirm(cls, parent: Optional[QWidget], title: str, message: str) -> bool:
        """Show confirm dialog and return True if confirmed."""
        dialog = cls(title, message, parent)
        return dialog.exec_() == QDialog.Accepted


class ErrorDialog(BaseDialog):
    """Error message dialog."""

    def __init__(self, title: str, message: str, details: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self._setup_ui(message, details)

    def _setup_ui(self, message: str, details: Optional[str]):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Icon and message
        msg_layout = QHBoxLayout()
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 24pt;")
        msg_layout.addWidget(icon_label)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        msg_layout.addWidget(msg_label, 1)
        layout.addLayout(msg_layout)

        # Details
        if details:
            details_label = QLabel(details)
            details_label.setWordWrap(True)
            details_label.setStyleSheet("color: #666; font-size: 9pt;")
            layout.addWidget(details_label)

        # OK button
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)

        layout.addWidget(self._create_button_row([ok_btn]))

    @classmethod
    def show_error(cls, parent: Optional[QWidget], title: str, message: str, details: Optional[str] = None) -> None:
        """Show error dialog."""
        dialog = cls(title, message, details, parent)
        dialog.exec_()


class InfoDialog(BaseDialog):
    """Information message dialog."""

    def __init__(self, title: str, message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._setup_ui(message)

    def _setup_ui(self, message: str) -> None:
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # OK button
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)

        layout.addWidget(self._create_button_row([ok_btn]))

    @classmethod
    def show_info(cls, parent: Optional[QWidget], title: str, message: str) -> None:
        """Show info dialog."""
        dialog = cls(title, message, parent)
        dialog.exec_()


class ExportDialog(BaseDialog):
    """Export options dialog."""

    def __init__(self, parent=None, i18n=None):
        super().__init__("Export", parent)
        self.i18n = i18n
        self.export_format = "csv"
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Format selection
        format_label = QLabel("Select export format:")
        layout.addWidget(format_label)

        # CSV button
        csv_btn = QPushButton("📄 Export as CSV")
        csv_btn.clicked.connect(lambda: self._select_format("csv"))
        layout.addWidget(csv_btn)

        # Excel button
        excel_btn = QPushButton("📊 Export as Excel")
        excel_btn.clicked.connect(lambda: self._select_format("xlsx"))
        layout.addWidget(excel_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select_format(self, fmt: str):
        """Select format and close."""
        self.export_format = fmt
        self.accept()

    @classmethod
    def get_format(cls, parent: QWidget, i18n=None) -> str:
        """Show dialog and return selected format or empty string."""
        dialog = cls(parent, i18n)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.export_format
        return ""
