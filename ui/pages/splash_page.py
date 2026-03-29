# -*- coding: utf-8 -*-
"""
Splash Page with entrance animations.
Shows UN-Habitat logo + app title + two cards (Local Demo / Central API).
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QColor, QPixmap, QPainter, QPaintEvent, QFont

from app.config import Config
from services.translation_manager import tr, get_layout_direction
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
        self.title_label = QLabel(title)
        self.title_label.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Subtitle
        self.sub_label = QLabel(subtitle)
        self.sub_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.sub_label.setStyleSheet("color: #6B7280; background: transparent;")
        self.sub_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sub_label)

        # Description
        self.desc_label = QLabel(description)
        self.desc_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        self.desc_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

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
        self._animated = False
        self._animations = []
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
        self.setLayoutDirection(get_layout_direction())

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Center everything
        main.addStretch(2)

        # Logo
        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)
        self._logo_label = QLabel()
        logo_path = os.path.join(
            str(Config.ASSETS_DIR), "images", "Layer_1.png"
        )
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._logo_label.setPixmap(scaled)
        self._logo_label.setAlignment(Qt.AlignCenter)
        self._logo_label.setStyleSheet("background: transparent;")
        logo_layout.addWidget(self._logo_label)
        main.addLayout(logo_layout)

        main.addSpacing(16)

        # App title (English)
        self._title_en = QLabel(Config.APP_TITLE)
        self._title_en.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._title_en.setStyleSheet("color: white; background: transparent;")
        self._title_en.setAlignment(Qt.AlignCenter)
        main.addWidget(self._title_en)

        # App title (Arabic)
        self._title_ar = QLabel(Config.APP_TITLE_AR)
        self._title_ar.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._title_ar.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        self._title_ar.setAlignment(Qt.AlignCenter)
        main.addWidget(self._title_ar)

        # Version
        self._version_label = QLabel(f"v{Config.VERSION}")
        self._version_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._version_label.setStyleSheet("color: rgba(255,255,255,0.6); background: transparent;")
        self._version_label.setAlignment(Qt.AlignCenter)
        main.addWidget(self._version_label)

        main.addStretch(1)

        # Mode selection label
        self.choose_label = QLabel(tr("page.splash.choose_data_source"))
        self.choose_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self.choose_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.choose_label.setAlignment(Qt.AlignCenter)
        main.addWidget(self.choose_label)

        main.addSpacing(16)

        # Cards row
        cards_layout = QHBoxLayout()
        cards_layout.setAlignment(Qt.AlignCenter)
        cards_layout.setSpacing(24)

        # Wrap each card in a container so we can apply opacity
        # (cards already have QGraphicsDropShadowEffect)
        self._local_wrap = QWidget()
        local_lay = QVBoxLayout(self._local_wrap)
        local_lay.setContentsMargins(0, 0, 0, 0)
        self.local_card = _ModeCard(
            icon_text="\u26C1",
            title=tr("page.splash.local_title"),
            subtitle=tr("page.splash.local_subtitle"),
            description=tr("page.splash.local_description"),
            color="#10B981",
        )
        self.local_card.clicked.connect(lambda: self._on_mode("local"))
        local_lay.addWidget(self.local_card)
        cards_layout.addWidget(self._local_wrap)

        self._api_wrap = QWidget()
        api_lay = QVBoxLayout(self._api_wrap)
        api_lay.setContentsMargins(0, 0, 0, 0)
        self.api_card = _ModeCard(
            icon_text="\u2601",
            title=tr("page.splash.api_title"),
            subtitle=tr("page.splash.api_subtitle"),
            description=tr("page.splash.api_description"),
            color=Colors.PRIMARY_BLUE,
        )
        self.api_card.clicked.connect(lambda: self._on_mode("api"))
        api_lay.addWidget(self.api_card)
        cards_layout.addWidget(self._api_wrap)

        main.addLayout(cards_layout)

        main.addStretch(2)

        # Footer
        self._footer = QLabel(f"\u00A9 2024 {Config.ORGANIZATION}")
        self._footer.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        self._footer.setStyleSheet("color: #9CA3AF; background: transparent;")
        self._footer.setAlignment(Qt.AlignCenter)
        main.addWidget(self._footer)
        main.addSpacing(16)

        # Prepare opacity effects for animation (start invisible)
        self._opacity_effects = {}
        fade_widgets = [
            self._logo_label, self._title_en, self._title_ar,
            self._version_label, self.choose_label,
            self._local_wrap, self._api_wrap, self._footer,
        ]
        for w in fade_widgets:
            effect = QGraphicsOpacityEffect(w)
            effect.setOpacity(0.0)
            w.setGraphicsEffect(effect)
            self._opacity_effects[w] = effect

    def showEvent(self, event):
        super().showEvent(event)
        if not self._animated:
            self._animated = True
            QTimer.singleShot(50, self._run_entrance_animations)

    def _run_entrance_animations(self):
        """Staggered fade-in entrance for all elements."""
        schedule = [
            (self._logo_label,    0,    800),
            (self._title_en,      300,  600),
            (self._title_ar,      450,  600),
            (self._version_label, 600,  400),
            (self.choose_label,   800,  500),
            (self._local_wrap,    1000, 500),
            (self._api_wrap,      1150, 500),
            (self._footer,        1400, 400),
        ]

        for widget, delay, duration in schedule:
            effect = self._opacity_effects.get(widget)
            if not effect:
                continue

            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(duration)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._animations.append(anim)

            if delay > 0:
                QTimer.singleShot(delay, anim.start)
            else:
                anim.start()

        # Slide-up effect for the two cards
        for widget, delay in [(self._local_wrap, 1000), (self._api_wrap, 1150)]:
            self._animate_slide_up(widget, delay, 500, 25)

    def _animate_slide_up(self, widget, delay_ms, duration_ms, offset_px):
        """Animate a widget sliding up from offset_px below its position."""
        def start():
            start_margins = widget.layout().contentsMargins()
            # Add extra top margin to push content down, then animate to 0
            widget.layout().setContentsMargins(0, offset_px, 0, 0)

            anim = QPropertyAnimation(widget, b"geometry", self)
            anim.setDuration(duration_ms)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._animations.append(anim)

            # Use a timer-based approach to smoothly reduce the top margin
            steps = 15
            step_ms = duration_ms // steps
            for i in range(1, steps + 1):
                progress = i / steps
                eased = 1.0 - (1.0 - progress) ** 3  # OutCubic
                margin = int(offset_px * (1.0 - eased))
                QTimer.singleShot(
                    i * step_ms,
                    lambda m=margin: widget.layout().setContentsMargins(0, m, 0, 0)
                )

        QTimer.singleShot(delay_ms, start)

    def _on_mode(self, mode: str):
        logger.info(f"Data mode selected: {mode}")
        self.mode_selected.emit(mode)

    def update_language(self, is_arabic: bool):
        """Update all translatable text when language changes."""
        self.setLayoutDirection(get_layout_direction())
        self.choose_label.setText(tr("page.splash.choose_data_source"))

        self.local_card.title_label.setText(tr("page.splash.local_title"))
        self.local_card.sub_label.setText(tr("page.splash.local_subtitle"))
        self.local_card.desc_label.setText(tr("page.splash.local_description"))

        self.api_card.title_label.setText(tr("page.splash.api_title"))
        self.api_card.sub_label.setText(tr("page.splash.api_subtitle"))
        self.api_card.desc_label.setText(tr("page.splash.api_description"))
