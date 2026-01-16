# -*- coding: utf-8 -*-
"""
Reusable message dialog component.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt


class MessageDialog(QDialog):
    """
    Reusable message dialog with customizable icon, title, and message.

    Usage:
        # Confirmation dialog
        if MessageDialog.confirm(self, "هل أنت متأكد؟", "سيتم حذف البيانات"):
            # User clicked OK

        # Warning dialog
        MessageDialog.warning(self, "تحذير", "لا يمكن إتمام العملية")

        # Error dialog
        MessageDialog.error(self, "خطأ", "حدث خطأ غير متوقع")

        # Info dialog
        MessageDialog.info(self, "نجاح", "تم الحفظ بنجاح")
    """

    # Dialog types with icons
    CONFIRM = ("⚠️", "#f39c12")
    WARNING = ("⚠️", "#e67e22")
    ERROR = ("❌", "#e74c3c")
    INFO = ("ℹ️", "#3498db")
    SUCCESS = ("✓", "#27ae60")

    def __init__(self, parent, title, message, dialog_type=INFO, ok_text="موافق", cancel_text="إلغاء", show_cancel=False):
        """
        Create a message dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Message text (supports HTML)
            dialog_type: Tuple of (icon, color) or use predefined types
            ok_text: Text for OK button
            cancel_text: Text for Cancel button
            show_cancel: Show cancel button
        """
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setStyleSheet("background-color: white;")

        # Calculate height based on message length
        message_length = len(message)
        if message_length < 100:
            height = 200
        elif message_length < 200:
            height = 240
        else:
            height = 280

        self.setFixedSize(450, height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)

        # Icon
        icon, color = dialog_type
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Message
        message_label = QLabel(message)
        message_label.setStyleSheet("font-size: 13px; color: #555; line-height: 1.6;")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        layout.addSpacing(10)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        if show_cancel:
            cancel_btn = QPushButton(cancel_text)
            cancel_btn.setFixedSize(120, 40)
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            cancel_btn.setCursor(Qt.PointingHandCursor)
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton(ok_text)
        ok_btn.setFixedSize(120, 40)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        if show_cancel:
            btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    @staticmethod
    def confirm(parent, title, message, ok_text="تأكيد", cancel_text="إلغاء"):
        """Show confirmation dialog and return True if OK clicked."""
        dialog = MessageDialog(parent, title, message, MessageDialog.CONFIRM, ok_text, cancel_text, show_cancel=True)
        return dialog.exec_() == QDialog.Accepted

    @staticmethod
    def warning(parent, title, message, ok_text="موافق"):
        """Show warning dialog."""
        dialog = MessageDialog(parent, title, message, MessageDialog.WARNING, ok_text)
        dialog.exec_()

    @staticmethod
    def error(parent, title, message, ok_text="موافق"):
        """Show error dialog."""
        dialog = MessageDialog(parent, title, message, MessageDialog.ERROR, ok_text)
        dialog.exec_()

    @staticmethod
    def info(parent, title, message, ok_text="موافق"):
        """Show info dialog."""
        dialog = MessageDialog(parent, title, message, MessageDialog.INFO, ok_text)
        dialog.exec_()

    @staticmethod
    def success(parent, title, message, ok_text="موافق"):
        """Show success dialog."""
        dialog = MessageDialog(parent, title, message, MessageDialog.SUCCESS, ok_text)
        dialog.exec_()
