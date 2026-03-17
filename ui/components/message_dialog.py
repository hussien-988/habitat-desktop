# -*- coding: utf-8 -*-
"""
Reusable message dialog component matching Figma design.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ui.font_utils import create_font, FontManager


# Dialog type definitions: (icon_char, icon_bg_color, title_color, btn_color, btn_hover)
_TYPES = {
    "error":   ("!", "#FEE2E2", "#DC2626", "#DC2626", "#B91C1C"),
    "warning": ("!", "#FEF3C7", "#D97706", "#D97706", "#B45309"),
    "info":    ("i", "#DBEAFE", "#2563EB", "#2563EB", "#1D4ED8"),
    "success": ("\u2713", "#D1FAE5", "#059669", "#059669", "#047857"),
    "confirm": ("?", "#FEF3C7", "#D97706", "#374151", "#1F2937"),
}


class MessageDialog(QDialog):
    """
    Reusable message dialog matching Figma design style.

    Usage:
        MessageDialog.error(self, "خطأ", "حدث خطأ غير متوقع")
        MessageDialog.warning(self, "تحذير", "لا يمكن إتمام العملية")
        MessageDialog.info(self, "معلومة", "تم الحفظ بنجاح")
        if MessageDialog.confirm(self, "تأكيد", "هل أنت متأكد؟"):
            ...
    """

    def __init__(self, parent, title, message, dialog_type="info",
                 ok_text="حسناً", cancel_text="إلغاء", show_cancel=False):
        super().__init__(parent)

        if dialog_type in ("error", "warning"):
            from services.error_mapper import sanitize_user_message
            message = sanitize_user_message(message)

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(420)

        icon_char, icon_bg, title_color, btn_color, btn_hover = _TYPES.get(
            dialog_type, _TYPES["info"]
        )

        container = QWidget(self)
        container.setObjectName("msg_dialog_container")
        container.setStyleSheet("""
            QWidget#msg_dialog_container {
                background-color: #FFFFFF;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 36, 32, 28)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        # Icon circle
        icon_container = QWidget()
        icon_container.setFixedSize(72, 72)
        icon_container.setStyleSheet(
            f"QWidget {{ background-color: {icon_bg}; border-radius: 36px; }}"
        )
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignCenter)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel(icon_char)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFont(create_font(size=28, weight=FontManager.WEIGHT_BOLD))
        icon_label.setStyleSheet(f"color: {title_color}; background: transparent;")
        icon_layout.addWidget(icon_label)

        layout.addWidget(icon_container, 0, Qt.AlignCenter)
        layout.addSpacing(20)

        # Title
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {title_color}; background: transparent;")
        layout.addWidget(title_label)
        layout.addSpacing(10)

        # Message
        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR))
        message_label.setStyleSheet("color: #7F8C9B; background: transparent;")
        layout.addWidget(message_label)
        layout.addSpacing(28)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        if show_cancel:
            cancel_btn = QPushButton(cancel_text)
            cancel_btn.setFixedHeight(42)
            cancel_btn.setCursor(Qt.PointingHandCursor)
            cancel_btn.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #F3F4F6;
                    color: #4B5563;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 24px;
                }
                QPushButton:hover { background-color: #E5E7EB; }
                QPushButton:pressed { background-color: #D1D5DB; }
            """)
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn, 1)

        ok_btn = QPushButton(ok_text)
        ok_btn.setFixedHeight(42)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
            }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn, 1)

        layout.addLayout(btn_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 8)
        container.setGraphicsEffect(shadow)

    @staticmethod
    def confirm(parent, title, message, ok_text="تأكيد", cancel_text="إلغاء"):
        """Show confirmation dialog and return True if OK clicked."""
        dlg = MessageDialog(parent, title, message, "confirm", ok_text, cancel_text, show_cancel=True)
        return dlg.exec_() == QDialog.Accepted

    @staticmethod
    def warning(parent, title, message, ok_text="حسناً"):
        """Show warning dialog."""
        MessageDialog(parent, title, message, "warning", ok_text).exec_()

    @staticmethod
    def error(parent, title, message, ok_text="حسناً"):
        """Show error dialog."""
        MessageDialog(parent, title, message, "error", ok_text).exec_()

    @staticmethod
    def info(parent, title, message, ok_text="حسناً"):
        """Show info dialog."""
        MessageDialog(parent, title, message, "info", ok_text).exec_()

    @staticmethod
    def success(parent, title, message, ok_text="حسناً"):
        """Show success dialog."""
        MessageDialog(parent, title, message, "success", ok_text).exec_()
