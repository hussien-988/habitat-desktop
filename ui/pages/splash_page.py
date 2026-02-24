# -*- coding: utf-8 -*-
"""
Splash Page — شاشة البداية مع اختيار مصدر البيانات.
Shows UN-Habitat logo + app title + two cards (Local Demo / Central API).
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPixmap, QPainter, QPaintEvent, QFont

from app.config import Config
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class _ModeCard(QFrame):
    """Clickable card for selecting data mode."""

    clicked = pyqtSignal()

    def __init__(self, icon_text: str, title: str, subtitle: str,
                 description: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 200)
        self.setCursor(Qt.PointingHandCursor)
        self._color = color
        self._hovered = False

        self.setObjectName("modeCard")
        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # Icon
        icon_label = QLabel(icon_text)
        icon_label.setFont(create_font(size=28, weight=QFont.Normal))
        icon_label.setStyleSheet(f"color: {color}; background: transparent;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Subtitle
        sub_label = QLabel(subtitle)
        sub_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        sub_label.setStyleSheet("color: #6B7280; background: transparent;")
        sub_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

    def _apply_style(self, hovered: bool):
        border_color = self._color if hovered else "#E5E7EB"
        self.setStyleSheet(f"""
            QFrame#modeCard {{
                background-color: white;
                border: 2px solid {border_color};
                border-radius: 16px;
            }}
        """)

    def enterEvent(self, event):
        self._hovered = True
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SplashPage(QWidget):
    """Splash screen with UN-Habitat branding and data mode selection."""

    mode_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Top blue section (~45%)
        blue_h = int(h * 0.45)
        painter.fillRect(0, 0, w, blue_h, QColor(Colors.PRIMARY_BLUE))

        # Bottom light section
        painter.fillRect(0, blue_h, w, h - blue_h, QColor(Colors.BACKGROUND))

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Center everything
        main.addStretch(2)

        # Logo
        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)
        logo_label = QLabel()
        logo_path = os.path.join(
            str(Config.ASSETS_DIR), "images", "Layer_1.png"
        )
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("background: transparent;")
        logo_layout.addWidget(logo_label)
        main.addLayout(logo_layout)

        main.addSpacing(16)

        # App title (English)
        title_en = QLabel(Config.APP_TITLE)
        title_en.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_en.setStyleSheet("color: white; background: transparent;")
        title_en.setAlignment(Qt.AlignCenter)
        main.addWidget(title_en)

        # App title (Arabic)
        title_ar = QLabel(Config.APP_TITLE_AR)
        title_ar.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title_ar.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        title_ar.setAlignment(Qt.AlignCenter)
        main.addWidget(title_ar)

        # Version
        version_label = QLabel(f"v{Config.VERSION}")
        version_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        version_label.setStyleSheet("color: rgba(255,255,255,0.6); background: transparent;")
        version_label.setAlignment(Qt.AlignCenter)
        main.addWidget(version_label)

        main.addStretch(1)

        # Mode selection label
        choose_label = QLabel("اختر مصدر البيانات")
        choose_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        choose_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        choose_label.setAlignment(Qt.AlignCenter)
        main.addWidget(choose_label)

        main.addSpacing(16)

        # Cards row
        cards_layout = QHBoxLayout()
        cards_layout.setAlignment(Qt.AlignCenter)
        cards_layout.setSpacing(24)

        # Local Demo card
        local_card = _ModeCard(
            icon_text="\u26C1",
            title="بيانات محلية",
            subtitle="Local Demo",
            description="العمل بدون اتصال بالشبكة\nبيانات تجريبية جاهزة",
            color="#10B981",
        )
        local_card.clicked.connect(lambda: self._on_mode("local"))
        cards_layout.addWidget(local_card)

        # Central API card
        api_card = _ModeCard(
            icon_text="\u2601",
            title="بيانات مركزية",
            subtitle="Central Database",
            description="الاتصال بقاعدة البيانات المركزية\nيتطلب اتصال بالشبكة",
            color=Colors.PRIMARY_BLUE,
        )
        api_card.clicked.connect(lambda: self._on_mode("api"))
        cards_layout.addWidget(api_card)

        main.addLayout(cards_layout)

        main.addStretch(2)

        # Footer
        footer = QLabel(f"\u00A9 2024 {Config.ORGANIZATION}")
        footer.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        footer.setStyleSheet("color: #9CA3AF; background: transparent;")
        footer.setAlignment(Qt.AlignCenter)
        main.addWidget(footer)
        main.addSpacing(16)

    def _on_mode(self, mode: str):
        logger.info(f"Data mode selected: {mode}")
        self.mode_selected.emit(mode)
