# -*- coding: utf-8 -*-
"""Success Modal Component - modal dialog shown after successful operations."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from ..design_system import Colors
from services.translation_manager import tr


class SuccessModal(QDialog):
    """Success modal dialog with claim ID display."""

    def __init__(self,
                 title: str = None,
                 claim_id: str = "CL-2025-000001",
                 message: str = None,
                 parent=None):
        super().__init__(parent)
        self.title_text = title if title is not None else tr("component.success_modal.default_title")
        self.claim_id = claim_id
        self.message_text = message if message is not None else tr("component.success_modal.default_message")

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Setup modal UI."""
        # Remove window decorations for custom dialog
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedWidth(420)
        self.setMinimumHeight(300)

        # Container widget for rounded corners
        container = QWidget(self)
        container.setObjectName("modal_container")
        container.setStyleSheet(f"""
            QWidget#modal_container {{
                background-color: {Colors.PRIMARY_WHITE};
                border-radius: 12px;
            }}
        """)

        # Main layout
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 40, 32, 32)
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
        title_font = create_font(size=20, weight=QFont.Bold, letter_spacing=0)
        title_label.setFont(title_font)
        title_label.setStyleSheet(StyleManager.label_title())
        layout.addWidget(title_label)

        # Spacing (12px)
        layout.addSpacing(12)

        # Claim ID display
        claim_id_label = QLabel(self.claim_id)
        claim_id_label.setAlignment(Qt.AlignCenter)
        claim_id_font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.DemiBold, letter_spacing=0)
        claim_id_label.setFont(claim_id_font)
        claim_id_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.PRIMARY_BLUE};
                background: transparent;
            }}
        """)
        layout.addWidget(claim_id_label)

        # Spacing (16px)
        layout.addSpacing(16)

        # Message
        message_label = QLabel(self.message_text)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        message_font = create_font(size=14, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0)
        message_label.setFont(message_font)
        message_label.setStyleSheet(StyleManager.label_subtitle())
        layout.addWidget(message_label)

        # Spacing before button (32px)
        layout.addSpacing(32)

        # Close button
        close_btn = QPushButton(tr("component.success_modal.ok_button"))
        close_btn.setFixedHeight(44)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn_font = create_font(size=14, weight=QFont.DemiBold, letter_spacing=0)
        close_btn.setFont(close_btn_font)
        close_btn.setStyleSheet(StyleManager.button_primary())
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Set container as the main widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _apply_styling(self):
        """Apply shadow effect."""
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
        """Show success modal."""
        if message is None:
            message = tr("component.success_modal.default_message")

        modal = SuccessModal(title, claim_id, message, parent)
        modal.exec_()
