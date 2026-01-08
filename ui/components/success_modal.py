# -*- coding: utf-8 -*-
"""
Success Modal Component - Figma Design (Page 24)
Modal dialog shown after successful operations
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor


class SuccessModal(QDialog):
    """
    Success modal matching Figma Page 24 design.

    Specifications from Figma:
    - Modal size: 420px width
    - White background
    - Border radius: 12px
    - Shadow: large
    - Thumbs up icon in center
    - Success message
    - Claim ID display
    - Close button or auto-close
    """

    def __init__(self,
                 title: str = "تمت الإضافة بنجاح",
                 claim_id: str = "CL-2025-000001",
                 message: str = "تم حفظ جميع المعلومات، ويمكنك الآن المتابعة أو إضافة عنصر جديد.",
                 parent=None):
        super().__init__(parent)
        self.title_text = title
        self.claim_id = claim_id
        self.message_text = message

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Setup modal UI matching Figma Page 24."""
        # Remove window decorations for custom dialog
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Fixed width from Figma
        self.setFixedWidth(420)
        self.setMinimumHeight(300)

        # Container widget for rounded corners
        container = QWidget(self)
        container.setObjectName("modal_container")
        container.setStyleSheet("""
            QWidget#modal_container {
                background-color: #FFFFFF;
                border-radius: 12px;
            }
        """)

        # Main layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 40, 32, 32)  # Generous padding from Figma
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        # Thumbs up icon container (circular background)
        icon_container = QWidget()
        icon_container.setFixedSize(80, 80)
        icon_container.setStyleSheet("""
            QWidget {
                background-color: #D1FAE5;
                border-radius: 40px;
            }
        """)

        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignCenter)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        # Thumbs up emoji/icon
        icon_label = QLabel("👍")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFont(QFont("Segoe UI Emoji", 32))
        icon_label.setStyleSheet("background: transparent;")
        icon_layout.addWidget(icon_label)

        layout.addWidget(icon_container, 0, Qt.AlignCenter)

        # Spacing after icon (24px)
        layout.addSpacing(24)

        # Title
        title_label = QLabel(self.title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Noto Kufi Arabic", 20, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                background: transparent;
            }
        """)
        layout.addWidget(title_label)

        # Spacing (12px)
        layout.addSpacing(12)

        # Claim ID display
        claim_id_label = QLabel(self.claim_id)
        claim_id_label.setAlignment(Qt.AlignCenter)
        claim_id_label.setFont(QFont("Noto Kufi Arabic", 18, QFont.DemiBold))
        claim_id_label.setStyleSheet("""
            QLabel {
                color: #3890DF;
                background: transparent;
            }
        """)
        layout.addWidget(claim_id_label)

        # Spacing (16px)
        layout.addSpacing(16)

        # Message
        message_label = QLabel(self.message_text)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setFont(QFont("Noto Kufi Arabic", 14))
        message_label.setStyleSheet("""
            QLabel {
                color: #7F8C9B;
                background: transparent;
            }
        """)
        layout.addWidget(message_label)

        # Spacing before button (32px)
        layout.addSpacing(32)

        # Close button
        close_btn = QPushButton("حسناً")
        close_btn.setFixedHeight(44)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFont(QFont("Noto Kufi Arabic", 14, QFont.DemiBold))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 48px;
            }
            QPushButton:hover {
                background-color: #2A7BC9;
            }
            QPushButton:pressed {
                background-color: #1F68B3;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Set container as the main widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _apply_styling(self):
        """Apply shadow effect matching Figma."""
        # Find container widget
        container = self.findChild(QWidget, "modal_container")
        if container:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(40)
            shadow.setColor(QColor(0, 0, 0, 50))  # rgba(0, 0, 0, 0.2)
            shadow.setOffset(0, 8)
            container.setGraphicsEffect(shadow)

    @staticmethod
    def show_success(parent, title: str, claim_id: str, message: str = None):
        """
        Static method to show success modal.

        Usage:
            SuccessModal.show_success(
                parent=self,
                title="تمت الإضافة بنجاح",
                claim_id="CL-2025-000001"
            )
        """
        if message is None:
            message = "تم حفظ جميع المعلومات، ويمكنك الآن المتابعة أو إضافة عنصر جديد."

        modal = SuccessModal(title, claim_id, message, parent)
        modal.exec_()
