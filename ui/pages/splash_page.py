# -*- coding: utf-8 -*-
"""
Splash Page - Refined institutional design.
Shows UN-Habitat logo with glow aura + app title + frosted-glass mode cards.
"""

import math
import os
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import (
    QColor, QPixmap, QPainter, QPaintEvent, QFont,
    QLinearGradient, QRadialGradient, QPen, QPainterPath,
)

from app.config import Config
from services.translation_manager import tr, get_layout_direction
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom painter icons (replace emoji)
# ---------------------------------------------------------------------------

def _paint_database_icon(painter, rect, color):
    """Draw a database cylinder icon."""
    cx, cy = rect.center().x(), rect.center().y()
    cw, ch = 26, 30
    x = cx - cw // 2
    y = cy - ch // 2
    ry = 5

    pen = QPen(QColor(color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawEllipse(x, y, cw, ry * 2)
    painter.drawLine(x, y + ry, x, y + ch - ry)
    painter.drawLine(x + cw, y + ry, x + cw, y + ch - ry)
    painter.drawArc(x, y + ch - ry * 2, cw, ry * 2, 0, -180 * 16)
    mid_y = y + ch // 2
    painter.drawArc(x, mid_y - ry, cw, ry * 2, 0, -180 * 16)


def _paint_cloud_icon(painter, rect, color):
    """Draw a cloud with download arrow."""
    cx, cy = rect.center().x(), rect.center().y()
    pen = QPen(QColor(color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    cloud = QPainterPath()
    cloud.moveTo(cx - 16, cy - 2)
    cloud.cubicTo(cx - 16, cy - 12, cx - 8, cy - 16, cx - 2, cy - 14)
    cloud.cubicTo(cx + 2, cy - 20, cx + 14, cy - 18, cx + 14, cy - 10)
    cloud.cubicTo(cx + 20, cy - 10, cx + 20, cy - 2, cx + 14, cy - 2)
    cloud.lineTo(cx - 16, cy - 2)
    painter.drawPath(cloud)

    ay = cy + 4
    painter.drawLine(cx, ay, cx, ay + 12)
    painter.drawLine(cx - 5, ay + 7, cx, ay + 12)
    painter.drawLine(cx + 5, ay + 7, cx, ay + 12)


class _PainterIcon(QWidget):
    """Widget that renders an icon via QPainter."""

    def __init__(self, paint_func, color, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self._paint_func = paint_func
        self._color = color
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_func(p, self.rect(), self._color)
        p.end()


# ---------------------------------------------------------------------------
# Glow logo widget
# ---------------------------------------------------------------------------

class _GlowLogo(QWidget):
    """Logo with animated breathing glow aura."""

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._glow_phase = 0.8
        self._start = 0
        self.setFixedSize(160, 160)
        self.setStyleSheet("background: transparent;")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start_glow(self):
        self._start = time.time()
        self._timer.start(50)

    def _tick(self):
        t = time.time() - self._start
        self._glow_phase = 0.7 + 0.3 * math.sin(t * 1.4)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        cx, cy = self.width() / 2, self.height() / 2

        alpha = int(30 * self._glow_phase)
        glow = QRadialGradient(cx, cy, 75)
        glow.setColorAt(0.0, QColor(56, 144, 223, alpha))
        glow.setColorAt(0.4, QColor(56, 144, 223, int(alpha * 0.3)))
        glow.setColorAt(1.0, QColor(56, 144, 223, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(int(cx - 75), int(cy - 75), 150, 150)

        if self._pixmap:
            lx = int(cx - self._pixmap.width() / 2)
            ly = int(cy - self._pixmap.height() / 2)
            p.drawPixmap(lx, ly, self._pixmap)

        p.end()


# ---------------------------------------------------------------------------
# Mode card (frosted glass)
# ---------------------------------------------------------------------------

class _ModeCard(QFrame):
    """Frosted-glass card for selecting data mode."""

    clicked = pyqtSignal()

    def __init__(self, paint_func, title: str, subtitle: str,
                 description: str, accent_color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 220)
        self.setCursor(Qt.PointingHandCursor)
        self._accent = accent_color
        self._hovered = False

        self.setObjectName("modeCard")
        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        icon_widget = _PainterIcon(paint_func, accent_color)
        layout.addWidget(icon_widget, alignment=Qt.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        self.title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.sub_label = QLabel(subtitle)
        self.sub_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.sub_label.setStyleSheet("color: #8BACC8; background: transparent;")
        self.sub_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sub_label)

        self.desc_label = QLabel(description)
        self.desc_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        self.desc_label.setStyleSheet("color: rgba(139, 172, 200, 0.55); background: transparent;")
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def _apply_style(self, hovered: bool):
        if hovered:
            self.setStyleSheet("""
                QFrame#modeCard {
                    background-color: rgba(22, 43, 77, 220);
                    border: 1px solid rgba(56, 144, 223, 130);
                    border-radius: 16px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#modeCard {
                    background-color: rgba(15, 31, 61, 180);
                    border: 1px solid rgba(100, 180, 255, 38);
                    border-radius: 16px;
                }
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


# ---------------------------------------------------------------------------
# Main splash page
# ---------------------------------------------------------------------------

class SplashPage(QWidget):
    """Refined institutional splash with data mode selection."""

    mode_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animated = False
        self._animations = []
        self._setup_ui()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Full-page deep navy gradient
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor("#0A1628"))
        bg.setColorAt(0.4, QColor("#0F1F3D"))
        bg.setColorAt(1.0, QColor("#162B4D"))
        p.fillRect(0, 0, w, h, bg)

        # Perspective-grid overlay
        grid_pen = QPen(QColor(26, 50, 88, 16), 0.5)
        p.setPen(grid_pen)
        p.setBrush(Qt.NoBrush)
        cx = w / 2
        spacing = 70
        for i in range(-10, 11):
            x_off = i * spacing
            p.drawLine(int(cx + x_off * 0.85), 0, int(cx + x_off * 1.15), h)
        for y in range(0, h + 1, spacing):
            p.drawLine(0, y, w, y)

        # Ambient glow behind logo area
        lg = QRadialGradient(w / 2, h * 0.28, min(w, h) * 0.35)
        lg.setColorAt(0.0, QColor(56, 144, 223, 22))
        lg.setColorAt(0.5, QColor(56, 144, 223, 6))
        lg.setColorAt(1.0, QColor(56, 144, 223, 0))
        p.fillRect(0, 0, w, h, lg)

        # Luminous divider
        dy = int(h * 0.52)

        dg = QRadialGradient(w / 2, dy, w * 0.28)
        dg.setColorAt(0.0, QColor(56, 144, 223, 14))
        dg.setColorAt(1.0, QColor(56, 144, 223, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(dg)
        p.drawEllipse(int(w / 2 - w * 0.28), dy - 18, int(w * 0.56), 36)

        dl = QLinearGradient(w * 0.15, dy, w * 0.85, dy)
        dl.setColorAt(0.0, QColor(56, 144, 223, 0))
        dl.setColorAt(0.3, QColor(56, 144, 223, 55))
        dl.setColorAt(0.5, QColor(91, 168, 240, 90))
        dl.setColorAt(0.7, QColor(56, 144, 223, 55))
        dl.setColorAt(1.0, QColor(56, 144, 223, 0))
        p.setPen(QPen(dl, 1.0))
        p.drawLine(int(w * 0.15), dy, int(w * 0.85), dy)

        p.end()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addStretch(2)

        # Glow logo
        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)

        logo_pixmap = None
        logo_path = os.path.join(str(Config.ASSETS_DIR), "images", "Layer_1.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                logo_pixmap = pixmap.scaled(
                    100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

        self._glow_logo = _GlowLogo(logo_pixmap)
        logo_layout.addWidget(self._glow_logo)
        main.addLayout(logo_layout)

        main.addSpacing(8)

        # App title (English)
        self._title_en = QLabel(Config.APP_TITLE)
        self._title_en.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        self._title_en.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._title_en.setAlignment(Qt.AlignCenter)
        main.addWidget(self._title_en)

        # App title (Arabic)
        self._title_ar = QLabel(Config.APP_TITLE_AR)
        self._title_ar.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
        self._title_ar.setStyleSheet("color: rgba(139, 172, 200, 0.85); background: transparent;")
        self._title_ar.setAlignment(Qt.AlignCenter)
        main.addWidget(self._title_ar)

        # Version
        self._version_label = QLabel(f"v{Config.VERSION}")
        self._version_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._version_label.setStyleSheet("color: rgba(139, 172, 200, 0.5); background: transparent;")
        self._version_label.setAlignment(Qt.AlignCenter)
        main.addWidget(self._version_label)

        main.addStretch(1)

        # Mode selection label
        self.choose_label = QLabel(tr("page.splash.choose_data_source"))
        self.choose_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self.choose_label.setStyleSheet("color: #8BACC8; background: transparent;")
        self.choose_label.setAlignment(Qt.AlignCenter)
        main.addWidget(self.choose_label)

        main.addSpacing(20)

        # Cards row
        cards_layout = QHBoxLayout()
        cards_layout.setAlignment(Qt.AlignCenter)
        cards_layout.setSpacing(28)

        # Local card
        self._local_wrap = QWidget()
        self._local_wrap.setStyleSheet("background: transparent;")
        local_lay = QVBoxLayout(self._local_wrap)
        local_lay.setContentsMargins(0, 0, 0, 0)
        self.local_card = _ModeCard(
            paint_func=_paint_database_icon,
            title=tr("page.splash.local_title"),
            subtitle=tr("page.splash.local_subtitle"),
            description=tr("page.splash.local_description"),
            accent_color="#10B981",
        )
        self.local_card.clicked.connect(lambda: self._on_mode("local"))
        local_lay.addWidget(self.local_card)
        cards_layout.addWidget(self._local_wrap)

        # API card
        self._api_wrap = QWidget()
        self._api_wrap.setStyleSheet("background: transparent;")
        api_lay = QVBoxLayout(self._api_wrap)
        api_lay.setContentsMargins(0, 0, 0, 0)
        self.api_card = _ModeCard(
            paint_func=_paint_cloud_icon,
            title=tr("page.splash.api_title"),
            subtitle=tr("page.splash.api_subtitle"),
            description=tr("page.splash.api_description"),
            accent_color="#5BA8F0",
        )
        self.api_card.clicked.connect(lambda: self._on_mode("api"))
        api_lay.addWidget(self.api_card)
        cards_layout.addWidget(self._api_wrap)

        main.addLayout(cards_layout)

        main.addStretch(2)

        # Footer
        self._footer = QLabel(
            f"UN-Habitat  \u2502  United Nations Human Settlements Programme"
            f"  \u2502  \u00A9 2024\u20132026 {Config.ORGANIZATION}"
        )
        self._footer.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        self._footer.setStyleSheet("color: rgba(139, 172, 200, 0.3); background: transparent;")
        self._footer.setAlignment(Qt.AlignCenter)
        main.addWidget(self._footer)
        main.addSpacing(16)

        # Prepare opacity effects for animation (start invisible)
        self._opacity_effects = {}
        fade_widgets = [
            self._glow_logo, self._title_en, self._title_ar,
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
        """Staggered entrance with scale-fade, fade, and slide effects."""
        self._glow_logo.start_glow()

        schedule = [
            (self._glow_logo,     0,    900),
            (self._title_en,      400,  600),
            (self._title_ar,      550,  600),
            (self._version_label, 700,  400),
            (self.choose_label,   900,  500),
            (self._local_wrap,    1100, 600),
            (self._api_wrap,      1250, 600),
            (self._footer,        1500, 400),
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

        # Logo scale-up
        self._animate_logo_scale(0, 900)

        # Cards slide in from opposite sides
        self._animate_slide_horizontal(self._local_wrap, 1100, 600, -35)
        self._animate_slide_horizontal(self._api_wrap, 1250, 600, 35)

    def _animate_logo_scale(self, delay_ms, duration_ms):
        """Scale logo widget from 85% to 100%."""
        tw, th = 160, 160
        sw, sh = int(tw * 0.85), int(th * 0.85)

        def start():
            self._glow_logo.setFixedSize(sw, sh)
            steps = 20
            step_ms = duration_ms // steps
            for i in range(1, steps + 1):
                progress = i / steps
                eased = 1.0 - (1.0 - progress) ** 3
                cw = int(sw + (tw - sw) * eased)
                ch = int(sh + (th - sh) * eased)
                QTimer.singleShot(
                    i * step_ms,
                    lambda w=cw, h=ch: self._glow_logo.setFixedSize(w, h),
                )

        QTimer.singleShot(delay_ms, start)

    def _animate_slide_horizontal(self, widget, delay_ms, duration_ms, offset_px):
        """Slide a widget horizontally from offset_px to 0."""
        def start():
            steps = 18
            step_ms = duration_ms // steps
            abs_off = abs(offset_px)
            for i in range(steps + 1):
                progress = i / steps
                eased = 1.0 - (1.0 - progress) ** 3
                remaining = int(abs_off * (1.0 - eased))
                if offset_px < 0:
                    margins = (0, 0, remaining, 0)
                else:
                    margins = (remaining, 0, 0, 0)
                QTimer.singleShot(
                    i * step_ms,
                    lambda m=margins: widget.layout().setContentsMargins(*m),
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
