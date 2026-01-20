# -*- coding: utf-8 -*-
"""
Confirmation Modal Component - Figma Design (Page 25)
Warning/Confirmation dialog before destructive actions
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ..font_utils import create_font, FontManager


class ConfirmationModal(QDialog):
    """
    Confirmation modal matching Figma Page 25 design.
    """

    def __init__(self,
                 title: str = "هل تريد حفظ التغييرات؟",
                 message: str = "لديك بيانات غير محفوظة، يمكنك حفظها كمسودة، والمتابعة لاحقاً، أو الخروج بدون حفظ.",
                 confirm_text: str = "حفظ كمسودة",
                 cancel_text: str = "عدم الحفظ",
                 confirm_style: str = "dark",
                 parent=None):
        super().__init__(parent)
        self.title_text = title
        self.message_text = message
        self.confirm_text = confirm_text
        self.cancel_text = cancel_text
        self.confirm_style = confirm_style
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Setup modal UI matching Figma Page 25."""
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(420)
        self.setMinimumHeight(280)

        container = QWidget(self)
        container.setObjectName("modal_container")
        container.setStyleSheet("""
            QWidget#modal_container {
                background-color: #FFFFFF;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 40, 32, 32)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        # Warning icon
        icon_container = QWidget()
        icon_container.setFixedSize(80, 80)
        icon_container.setStyleSheet("QWidget { background-color: #FEF3C7; border-radius: 40px; }")
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignCenter)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("⚠")
        icon_label.setAlignment(Qt.AlignCenter)
        # Use centralized font for icon: 32pt (42px × 0.75 ≈ 32pt)
        icon_font = create_font(size=32, weight=QFont.Normal, letter_spacing=0)
        icon_label.setFont(icon_font)
        icon_label.setStyleSheet("background: transparent;")
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_container, 0, Qt.AlignCenter)
        layout.addSpacing(24)

        # Title
        title_label = QLabel(self.title_text)
        title_label.setAlignment(Qt.AlignCenter)
        # Use centralized font: 18pt Bold (24px × 0.75 = 18pt)
        title_font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold, letter_spacing=0)
        title_label.setFont(title_font)
        title_label.setStyleSheet("QLabel { color: #2C3E50; background: transparent; }")
        layout.addWidget(title_label)
        layout.addSpacing(12)

        # Message
        message_label = QLabel(self.message_text)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        # Use centralized font: 14pt Normal (18px × 0.75 ≈ 14pt)
        message_font = create_font(size=14, weight=QFont.Normal, letter_spacing=0)
        message_label.setFont(message_font)
        message_label.setStyleSheet("QLabel { color: #7F8C9B; background: transparent; }")
        layout.addWidget(message_label)
        layout.addSpacing(32)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        cancel_btn = QPushButton(self.cancel_text)
        cancel_btn.setFixedHeight(44)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        # Use centralized font: 14pt Medium (18px × 0.75 ≈ 14pt)
        cancel_font = create_font(size=14, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0)
        cancel_btn.setFont(cancel_font)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
            QPushButton:pressed { background-color: #D1D5DB; }
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn, 1)

        confirm_btn = QPushButton(self.confirm_text)
        confirm_btn.setFixedHeight(44)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        # Use centralized font: 14pt DemiBold (18px × 0.75 ≈ 14pt)
        confirm_font = create_font(size=14, weight=QFont.DemiBold, letter_spacing=0)
        confirm_btn.setFont(confirm_font)

        if self.confirm_style == "danger":
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #DC2626;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                }
                QPushButton:hover { background-color: #B91C1C; }
                QPushButton:pressed { background-color: #991B1B; }
            """)
        else:
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background-color: #374151;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                }
                QPushButton:hover { background-color: #1F2937; }
                QPushButton:pressed { background-color: #111827; }
            """)
        confirm_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(confirm_btn, 1)

        layout.addLayout(buttons_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _apply_styling(self):
        """Apply shadow effect."""
        container = self.findChild(QWidget, "modal_container")
        if container:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(40)
            shadow.setColor(QColor(0, 0, 0, 50))
            shadow.setOffset(0, 8)
            container.setGraphicsEffect(shadow)

    @staticmethod
    def ask_confirmation(parent, title: str, message: str,
                        confirm_text: str = "تأكيد",
                        cancel_text: str = "إلغاء",
                        confirm_style: str = "dark") -> bool:
        """Show confirmation modal and return user choice."""
        modal = ConfirmationModal(title, message, confirm_text, cancel_text, confirm_style, parent)
        return modal.exec_() == QDialog.Accepted
