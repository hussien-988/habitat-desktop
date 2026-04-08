# -*- coding: utf-8 -*-
"""Login page — Cartographic Authority design."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import (
    QColor, QPainter, QPaintEvent, QFont, QFontDatabase, QPixmap,
    QLinearGradient, QRadialGradient, QPen, QCursor, QIcon
)
import math
import os
import random
import re
import time
from app.config import Config
from services.api_auth_service import ApiAuthService
from services.translation_manager import tr, get_layout_direction, set_language as tm_set_language, get_language as tm_get_language
from app.config import save_language
from utils.i18n import I18n
from utils.logger import get_logger
from ui.font_utils import create_font, FontManager
from ui.design_system import Colors, ScreenScale

logger = get_logger(__name__)


class _RotatingLogo(QWidget):
    """Logo that rotates calmly around a vertical (Y) axis."""

    def __init__(self, pixmap: QPixmap, size: int = 100, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        cx = self._size / 2
        cy = self._size / 2
        pw = self._pixmap.width()
        ph = self._pixmap.height()
        painter.drawPixmap(int(cx - pw / 2), int(cy - ph / 2), self._pixmap)
        painter.end()


class LoginPage(QWidget):
    """Login page with Cartographic Authority dark split-layout design."""

    login_successful = pyqtSignal(object)

    def __init__(self, i18n: I18n, db=None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.db = db
        self.auth_service = ApiAuthService()
        self.password_visible = False
        self._arabic_re = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

        # Login lockout tracking
        self._failed_attempts = 0
        self._lockout_until = None

        # Constellation particles
        random.seed(99)
        self._particles = []
        for _ in range(18):
            self._particles.append({
                "x": random.uniform(0.05, 0.55),
                "y": random.uniform(0.08, 0.92),
                "dx": random.uniform(0.3, 0.8) * random.choice([-1, 1]),
                "dy": random.uniform(0.2, 0.6) * random.choice([-1, 1]),
                "phase": random.uniform(0, math.tau),
            })

        # Load watermark pixmap for paintEvent background
        self._watermark_pixmap = None
        wm_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "images", "login-watermark.png")
        wm_path = os.path.normpath(wm_path)
        wm_pix = QPixmap(wm_path)
        if not wm_pix.isNull():
            self._watermark_pixmap = wm_pix.scaled(500, 400, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        # Load custom fonts
        self._load_fonts()
        self._setup_ui()
        self._setup_login_navbar()

        # Animation timer (~15fps)
        self._anim_start = time.time()
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start(66)

    def _anim_tick(self):
        self.update()

    def _load_fonts(self):
        """Load Noto Kufi Arabic fonts"""
        fonts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts", "Noto_Kufi_Arabic")
        font_files = [
            "NotoKufiArabic-Regular.ttf",
            "NotoKufiArabic-Bold.ttf",
            "NotoKufiArabic-SemiBold.ttf",
            "NotoKufiArabic-Medium.ttf"
        ]

        for font_file in font_files:
            font_path = os.path.join(fonts_dir, font_file)
            if os.path.exists(font_path):
                QFontDatabase.addApplicationFont(font_path)

    def paintEvent(self, event: QPaintEvent):
        """Dark navy background with geometric grid, constellation, and breathing glow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        t = time.time() - self._anim_start

        # Institutional navy gradient (lightened for professional look)
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#132640"))
        grad.setColorAt(0.5, QColor("#1A3358"))
        grad.setColorAt(1.0, QColor("#224068"))
        painter.fillRect(0, 0, w, h, grad)

        # Geometric cadastral grid (decorative area only, left ~58%)
        deco_w = int(w * 0.58)
        grid_spacing = 60
        painter.setPen(QPen(QColor(56, 144, 223, 16), 1))
        x = grid_spacing
        while x < deco_w:
            painter.drawLine(x, 33, x, h)
            x += grid_spacing
        y = 33 + grid_spacing
        while y < h:
            painter.drawLine(0, y, deco_w, y)
            y += grid_spacing

        # Diamond accents at intersections
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(56, 144, 223, 12))
        gx = grid_spacing
        while gx < deco_w:
            gy = 33 + grid_spacing
            while gy < h:
                painter.save()
                painter.translate(gx, gy)
                painter.rotate(45)
                painter.drawRect(-2, -2, 4, 4)
                painter.restore()
                gy += grid_spacing
            gx += grid_spacing

        # Subtle ambient light wash across center
        light_wash = QLinearGradient(0, h * 0.3, 0, h * 0.7)
        light_wash.setColorAt(0.0, QColor(56, 144, 223, 0))
        light_wash.setColorAt(0.4, QColor(56, 144, 223, 8))
        light_wash.setColorAt(0.5, QColor(100, 160, 220, 12))
        light_wash.setColorAt(0.6, QColor(56, 144, 223, 8))
        light_wash.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.NoBrush)
        painter.fillRect(0, 0, w, h, light_wash)

        # Constellation particles
        painter.setPen(Qt.NoPen)
        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.012 * math.sin(t * p["dx"] + p["phase"])) * w)
            py = int((p["y"] + 0.010 * math.cos(t * p["dy"] + p["phase"])) * h)
            px = max(4, min(deco_w - 4, px))
            py = max(37, min(h - 4, py))
            positions.append((px, py))
            alpha = 38 + int(18 * math.sin(t * 1.5 + p["phase"]))
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        # Connecting lines between nearby particles
        painter.setPen(QPen(QColor(139, 172, 200, 12), 1))
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 150:
                    painter.drawLine(positions[i][0], positions[i][1],
                                     positions[j][0], positions[j][1])

        # Breathing glow behind logo area
        if hasattr(self, "_deco_panel"):
            deco_rect = self._deco_panel.geometry()
            cx = deco_rect.x() + deco_rect.width() // 2
            cy = deco_rect.y() + int(deco_rect.height() * 0.45)
            glow_alpha = 18 + int(12 * math.sin(t * 1.25))
            glow_r = 140
            glow_grad = QRadialGradient(cx, cy, glow_r)
            glow_grad.setColorAt(0.0, QColor(56, 144, 223, glow_alpha))
            glow_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow_grad)
            painter.drawEllipse(QPoint(cx, cy), glow_r, glow_r)

        # Pulsing watermark logo in the decorative area
        if self._watermark_pixmap and hasattr(self, "_deco_panel"):
            deco_rect = self._deco_panel.geometry()
            wm_w = self._watermark_pixmap.width()
            wm_h = self._watermark_pixmap.height()
            wm_x = deco_rect.x() + (deco_rect.width() - wm_w) // 2
            wm_y = deco_rect.y() + (deco_rect.height() - wm_h) // 2
            wm_opacity = 0.05 + 0.05 * math.sin(t * 0.8)
            painter.setOpacity(wm_opacity)
            painter.drawPixmap(wm_x, wm_y, self._watermark_pixmap)
            painter.setOpacity(1.0)

        # Subtle vertical divider between panels
        div_x = deco_w
        div_grad = QLinearGradient(div_x, 33, div_x, h)
        div_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
        div_grad.setColorAt(0.3, QColor(56, 144, 223, 25))
        div_grad.setColorAt(0.5, QColor(56, 144, 223, 40))
        div_grad.setColorAt(0.7, QColor(56, 144, 223, 25))
        div_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(QPen(div_grad, 1))
        painter.drawLine(div_x, 33, div_x, h)

        # Static ring around logo (no rotation)
        if hasattr(self, "_rotating_logo"):
            logo_pos = self._rotating_logo.mapTo(self, QPoint(0, 0))
            ring_cx = logo_pos.x() + 50
            ring_cy = logo_pos.y() + 50
            painter.setPen(QPen(QColor(56, 144, 223, 15), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(ring_cx - 70, ring_cy - 35, 140, 70)

        # 5b: Corner brackets in the right panel
        login_x = deco_w + 40
        bracket_color = QColor(56, 144, 223, 20)
        painter.setPen(QPen(bracket_color, 1))
        # Top-right bracket
        painter.drawLine(w - 40, 60, w - 40, 90)
        painter.drawLine(w - 40, 60, w - 70, 60)
        # Bottom-left bracket (in right panel)
        painter.drawLine(login_x, h - 70, login_x, h - 40)
        painter.drawLine(login_x, h - 70, login_x + 30, h - 70)

        # 5c: Accent line near bottom
        line_y = h - 3
        line_grad = QLinearGradient(0, line_y, w, line_y)
        line_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
        line_grad.setColorAt(0.3, QColor(56, 144, 223, 15))
        line_grad.setColorAt(0.5, QColor(56, 144, 223, 25))
        line_grad.setColorAt(0.7, QColor(56, 144, 223, 15))
        line_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(QPen(line_grad, 1))
        painter.drawLine(0, line_y, w, line_y)

        # 5d: Coordinate labels on grid (map-style)
        painter.setPen(QColor(56, 144, 223, 18))
        coord_font = create_font(size=6, weight=FontManager.WEIGHT_REGULAR)
        painter.setFont(coord_font)
        for i, gx in enumerate(range(grid_spacing * 2, deco_w, grid_spacing * 3)):
            for j, gy in enumerate(range(33 + grid_spacing * 2, h, grid_spacing * 4)):
                painter.drawText(gx + 4, gy - 4, f"{35+i*0.5:.1f}N {36+j*0.3:.1f}E")

        painter.end()

    def _setup_ui(self):
        """Setup split layout: decorative panel (left) + login panel (right)."""
        self.setObjectName("LoginPage")
        self.setStyleSheet("QWidget#LoginPage { background: transparent; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Spacer for titlebar
        titlebar_spacer = QWidget()
        titlebar_spacer.setFixedHeight(ScreenScale.h(33))
        titlebar_spacer.setStyleSheet("background: transparent;")
        main_layout.addWidget(titlebar_spacer)

        # Split container (always LTR so panels don't swap on language change)
        split = QWidget()
        split.setStyleSheet("background: transparent;")
        split.setLayoutDirection(Qt.LeftToRight)
        self._split_container = split
        split_layout = QHBoxLayout(split)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(0)

        # Decorative panel (left)
        self._deco_panel = self._create_decorative_panel()
        split_layout.addWidget(self._deco_panel, 58)

        # Login panel (right) — centered vertically via stretches
        login_container = QWidget()
        login_container.setStyleSheet("background: transparent;")
        login_container_layout = QVBoxLayout(login_container)
        login_container_layout.setContentsMargins(30, 0, 30, 0)

        login_container_layout.addStretch(1)
        self.login_card = self._create_login_panel()
        login_container_layout.addWidget(self.login_card, 0, Qt.AlignHCenter)
        login_container_layout.addStretch(1)

        split_layout.addWidget(login_container, 42)

        main_layout.addWidget(split, 1)

        # Floating settings pill at bottom-left
        self._create_settings_pill()

    def _create_settings_pill(self):
        """Floating expandable pill at the bottom-left corner."""
        self._pill_expanded = False
        _PILL_H = 40
        self._pill_collapsed_w = 150
        self._pill_expanded_w = 380

        self._pill = QFrame(self)
        self._pill.setObjectName("settings_pill")
        self._pill.setFixedHeight(_PILL_H)
        self._pill.setFixedWidth(self._pill_collapsed_w)
        self._pill.setStyleSheet("""
            QFrame#settings_pill {
                background: rgba(10, 22, 40, 180);
                border: 1px solid rgba(56, 144, 223, 40);
                border-radius: 20px;
            }
        """)
        self._pill.setCursor(QCursor(Qt.PointingHandCursor))

        pill_layout = QHBoxLayout(self._pill)
        pill_layout.setContentsMargins(14, 0, 14, 0)
        pill_layout.setSpacing(0)

        _BTN_STYLE = """
            QPushButton {
                color: rgba(139, 172, 200, 200);
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.10);
                color: white;
            }
            QPushButton:pressed {
                background: rgba(255,255,255,0.16);
            }
        """

        pill_text = "\u0627\u0644\u0625\u0639\u062f\u0627\u062f\u0627\u062a" if tm_get_language() == "ar" else "Settings"
        self._pill_label = QPushButton("\u25C8  " + pill_text)
        self._pill_label.setObjectName("pill_trigger")
        self._pill_label.setStyleSheet("""
            QPushButton#pill_trigger {
                color: rgba(139, 172, 200, 200);
                background: transparent;
                border: none;
                padding: 0;
            }
            QPushButton#pill_trigger:hover {
                color: white;
            }
        """)
        self._pill_label.setFont(create_font(size=10, weight=QFont.DemiBold))
        self._pill_label.setCursor(QCursor(Qt.PointingHandCursor))
        self._pill_label.setFocusPolicy(Qt.NoFocus)
        self._pill_label.clicked.connect(self._toggle_pill)
        pill_layout.addWidget(self._pill_label)

        pill_layout.addStretch(1)

        # Expandable content (hidden initially)
        self._pill_content = QWidget()
        self._pill_content.setStyleSheet("background: transparent;")
        self._pill_content.setVisible(False)
        content_lay = QHBoxLayout(self._pill_content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)

        # Separator
        sep = QFrame()
        sep.setFixedSize(1, ScreenScale.h(18))
        sep.setStyleSheet("background: rgba(139,172,200,40);")
        content_lay.addWidget(sep)
        content_lay.addSpacing(8)

        # Language toggle button
        self._lang_btn = QPushButton()
        self._lang_btn.setStyleSheet(_BTN_STYLE)
        self._lang_btn.setFixedHeight(ScreenScale.h(30))
        self._lang_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._lang_btn.setFocusPolicy(Qt.NoFocus)
        self._lang_btn.setFont(create_font(size=9, weight=QFont.DemiBold))
        try:
            from ui.components.icon import Icon
            lang_pixmap = Icon.load_pixmap("language", size=14)
            if lang_pixmap and not lang_pixmap.isNull():
                self._lang_btn.setIcon(QIcon(lang_pixmap))
                self._lang_btn.setIconSize(QSize(14, 14))
        except Exception:
            pass
        self._lang_btn.clicked.connect(self._toggle_language)
        self._update_lang_button()
        content_lay.addWidget(self._lang_btn)

        content_lay.addSpacing(4)

        # Separator
        sep2 = QFrame()
        sep2.setFixedSize(1, ScreenScale.h(18))
        sep2.setStyleSheet("background: rgba(139,172,200,40);")
        content_lay.addWidget(sep2)
        content_lay.addSpacing(4)

        server_text = "\u0627\u0644\u062e\u0627\u062f\u0645" if tm_get_language() == "ar" else "Server"
        self._btn_settings = QPushButton("\u25A3  " + server_text)
        self._btn_settings.setStyleSheet(_BTN_STYLE)
        self._btn_settings.setFixedHeight(ScreenScale.h(30))
        self._btn_settings.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_settings.setFocusPolicy(Qt.NoFocus)
        self._btn_settings.setFont(create_font(size=9, weight=QFont.DemiBold))
        self._btn_settings.clicked.connect(self._open_server_settings)
        content_lay.addWidget(self._btn_settings)

        pill_layout.addWidget(self._pill_content)

        self._pill.raise_()

    def _toggle_pill(self):
        """Toggle the settings pill between collapsed and expanded."""
        self._pill_expanded = not self._pill_expanded

        if self._pill_expanded:
            self._pill_content.setVisible(True)
            self._pill_anim = QPropertyAnimation(self._pill, b"minimumWidth")
            self._pill_anim.setDuration(250)
            self._pill_anim.setStartValue(self._pill_collapsed_w)
            self._pill_anim.setEndValue(self._pill_expanded_w)
            self._pill_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._pill_anim2 = QPropertyAnimation(self._pill, b"maximumWidth")
            self._pill_anim2.setDuration(250)
            self._pill_anim2.setStartValue(self._pill_collapsed_w)
            self._pill_anim2.setEndValue(self._pill_expanded_w)
            self._pill_anim2.setEasingCurve(QEasingCurve.OutCubic)
            self._pill_anim.start()
            self._pill_anim2.start()
        else:
            self._pill_anim = QPropertyAnimation(self._pill, b"minimumWidth")
            self._pill_anim.setDuration(200)
            self._pill_anim.setStartValue(self._pill_expanded_w)
            self._pill_anim.setEndValue(self._pill_collapsed_w)
            self._pill_anim.setEasingCurve(QEasingCurve.InCubic)
            self._pill_anim2 = QPropertyAnimation(self._pill, b"maximumWidth")
            self._pill_anim2.setDuration(200)
            self._pill_anim2.setStartValue(self._pill_expanded_w)
            self._pill_anim2.setEndValue(self._pill_collapsed_w)
            self._pill_anim2.setEasingCurve(QEasingCurve.InCubic)
            self._pill_anim.finished.connect(lambda: self._pill_content.setVisible(False))
            self._pill_anim.start()
            self._pill_anim2.start()

    def _create_decorative_panel(self) -> QWidget:
        """Left decorative panel with logo, titles, version."""
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 20, 40, 30)
        layout.setSpacing(0)

        # Top stretch for vertical centering
        layout.addStretch(1)

        # Rotating logo
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, "..", "..", "assets", "images", "Layer_1.png")
        logo_path = os.path.normpath(logo_path)

        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            self._rotating_logo = _RotatingLogo(pixmap, size=100, parent=panel)
            layout.addWidget(self._rotating_logo, 0, Qt.AlignCenter)
        else:
            logo_label = QLabel("UN-HABITAT")
            logo_label.setAlignment(Qt.AlignCenter)
            logo_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent;")
            layout.addWidget(logo_label, 0, Qt.AlignCenter)

        layout.addSpacing(20)

        # Title "TRRCMS"
        title = QLabel("TRRCMS")
        title.setAlignment(Qt.AlignCenter)
        title_font = create_font(size=20, weight=QFont.DemiBold, letter_spacing=4.0)
        title.setFont(title_font)
        title.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(title, 0, Qt.AlignCenter)
        layout.addSpacing(10)

        # Arabic subtitle
        self._deco_ar_label = QLabel(tr("page.login.title"))
        self._deco_ar_label.setAlignment(Qt.AlignCenter)
        self._deco_ar_label.setWordWrap(True)
        ar_font = create_font(size=11, weight=QFont.DemiBold)
        self._deco_ar_label.setFont(ar_font)
        self._deco_ar_label.setStyleSheet("color: rgba(139,172,200, 217); background: transparent;")
        layout.addWidget(self._deco_ar_label)
        layout.addSpacing(14)

        # Separator line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setFixedWidth(ScreenScale.w(260))
        sep.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                          "stop:0 transparent, stop:0.3 #3890DF, stop:0.7 #3890DF, stop:1 transparent);")
        layout.addWidget(sep, 0, Qt.AlignCenter)
        layout.addSpacing(14)

        # English subtitle
        self._deco_en_label = QLabel(tr("page.login.subtitle"))
        self._deco_en_label.setAlignment(Qt.AlignCenter)
        self._deco_en_label.setWordWrap(True)
        en_font = create_font(size=9, weight=FontManager.WEIGHT_REGULAR)
        self._deco_en_label.setFont(en_font)
        self._deco_en_label.setStyleSheet("color: rgba(139,172,200, 166); background: transparent;")
        layout.addWidget(self._deco_en_label)

        layout.addStretch(1)

        # Version at bottom
        version_label = QLabel(f"v{Config.VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        ver_font = create_font(size=10, weight=FontManager.WEIGHT_MEDIUM)
        version_label.setFont(ver_font)
        version_label.setStyleSheet("color: rgba(139,172,200, 100); background: transparent;")
        layout.addWidget(version_label, 0, Qt.AlignCenter)

        return panel

    def _create_login_panel(self) -> QFrame:
        """Frosted glass login panel."""
        card = QFrame()
        card.setObjectName("login_panel")
        card.setMinimumWidth(ScreenScale.w(380))
        card.setMaximumWidth(ScreenScale.w(520))
        card.setStyleSheet("""
            QFrame#login_panel {
                background-color: rgba(20, 42, 78, 175);
                border: 1px solid rgba(56, 144, 223, 45);
                border-radius: 16px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 76))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(18)
        card_layout.setContentsMargins(36, 56, 36, 56)

        # Panel heading
        self._panel_title = QLabel(tr("page.login.sign_in"))
        self._panel_title.setAlignment(Qt.AlignCenter)
        heading_font = create_font(size=16, weight=QFont.Bold)
        self._panel_title.setFont(heading_font)
        self._panel_title.setStyleSheet("color: white; background: transparent;")
        card_layout.addWidget(self._panel_title)

        # Panel subtitle
        self._panel_subtitle = QLabel(tr("page.login.subtitle"))
        self._panel_subtitle.setAlignment(Qt.AlignCenter)
        sub_font = create_font(size=9, weight=FontManager.WEIGHT_REGULAR)
        self._panel_subtitle.setFont(sub_font)
        self._panel_subtitle.setStyleSheet("color: #8BACC8; background: transparent;")
        card_layout.addWidget(self._panel_subtitle)

        card_layout.addSpacing(20)

        # Username label (with required indicator)
        self._username_label = QLabel()
        self._username_label.setText(
            f"{tr('page.login.username')} <span style='color:#E74C3C;'>*</span>"
        )
        lbl_font = create_font(size=10, weight=QFont.DemiBold)
        self._username_label.setFont(lbl_font)
        self._username_label.setStyleSheet("color: #8BACC8; background: transparent;")
        card_layout.addWidget(self._username_label)

        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(tr("page.login.username_placeholder"))
        self.username_input.setLayoutDirection(get_layout_direction())
        self.username_input.setFixedHeight(ScreenScale.h(48))
        input_font = create_font(size=10, weight=FontManager.WEIGHT_REGULAR)
        self.username_input.setFont(input_font)
        self.username_input.setStyleSheet(self._dark_input_style())
        self.username_input.textChanged.connect(self._hide_error)
        card_layout.addWidget(self.username_input)

        card_layout.addSpacing(10)

        # Password label (with required indicator)
        self._password_label = QLabel()
        self._password_label.setText(
            f"{tr('page.login.password')} <span style='color:#E74C3C;'>*</span>"
        )
        self._password_label.setFont(lbl_font)
        self._password_label.setStyleSheet("color: #8BACC8; background: transparent;")
        card_layout.addWidget(self._password_label)

        # Password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(tr("page.login.password_placeholder"))
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(ScreenScale.h(48))
        self.password_input.setFont(input_font)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        eye_path = os.path.join(current_dir, "..", "..", "assets", "images", "Eye.png")
        eye_path = os.path.normpath(eye_path)

        eye_icon = QIcon(eye_path)
        self.eye_action = self.password_input.addAction(eye_icon, QLineEdit.TrailingPosition)
        self.eye_action.triggered.connect(self._toggle_password_visibility)

        self._apply_password_style(icon_on_left=True)
        self.password_input.textChanged.connect(self._on_password_text_changed)
        self.password_input.returnPressed.connect(self._on_login)
        card_layout.addWidget(self.password_input)

        # Error message
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("""
            background-color: rgba(231, 76, 60, 38);
            color: #E74C3C;
            font-size: 10px;
            padding: 8px 10px;
            border-radius: 8px;
            border: 1px solid rgba(231, 76, 60, 102);
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        card_layout.addSpacing(14)

        # Login button
        self.login_btn = QPushButton(tr("page.login.sign_in"))
        self.login_btn.setFixedHeight(ScreenScale.h(52))
        self.login_btn.setCursor(Qt.PointingHandCursor)
        button_font = create_font(size=12, weight=QFont.Bold)
        self.login_btn.setFont(button_font)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3890DF, stop:1 #5BA8F0);
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4DA0EF, stop:1 #6DB8FF);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2A7BC9, stop:1 #4A98E0);
            }
            QPushButton:disabled {
                background: rgba(56, 144, 223, 60);
                color: rgba(255, 255, 255, 100);
            }
        """)
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(20)
        btn_shadow.setColor(QColor(56, 144, 223, 76))
        btn_shadow.setOffset(0, 4)
        self.login_btn.setGraphicsEffect(btn_shadow)
        self.login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self.login_btn)

        return card

    @staticmethod
    def _dark_input_style():
        return """
            QLineEdit {
                background-color: rgba(18, 38, 65, 160);
                border: 1px solid rgba(56, 144, 223, 65);
                border-radius: 10px;
                padding: 0 12px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid rgba(56, 144, 223, 180);
                outline: none;
            }
            QLineEdit::placeholder {
                color: rgba(139, 172, 200, 120);
            }
        """

    def _setup_login_navbar(self):
        """Dark themed titlebar with animated sliding logo."""
        from ui.components.navbar import DraggableFrame

        self.titlebar = DraggableFrame(self)
        self.titlebar.setLayoutDirection(Qt.LeftToRight)
        self.titlebar.setFixedHeight(ScreenScale.h(33))
        self.titlebar.setObjectName("login_titlebar")
        self.titlebar.setStyleSheet("""
            QFrame#login_titlebar {
                background: #152D4A;
                border-bottom: 1px solid rgba(56, 144, 223, 50);
            }
            QPushButton#win_btn, QPushButton#win_close {
                color: rgba(139, 172, 200, 180);
                background: transparent;
                border: none;
                font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
                font-size: 14px;
                font-weight: 400;
                line-height: 16px;
                border-radius: 6px;
            }
            QPushButton#win_btn:hover {
                background: rgba(255,255,255,0.08);
                color: white;
            }
            QPushButton#win_btn:pressed {
                background: rgba(255,255,255,0.12);
            }
            QPushButton#win_close:hover {
                background: rgba(255, 59, 48, 0.90);
                color: white;
            }
            QPushButton#win_close:pressed {
                background: rgba(255, 59, 48, 0.75);
                color: white;
            }
        """)

        lay = QHBoxLayout(self.titlebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Animated logo (absolute-positioned inside titlebar for sliding)
        self._tb_logo = QLabel(self.titlebar)
        self._tb_logo.setStyleSheet("background: transparent;")
        target_w = ScreenScale.w(143)
        target_h = ScreenScale.h(22)
        self._tb_logo.setFixedSize(target_w, target_h)

        logo_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "assets", "images", "header.png"
        )
        logo_path = os.path.normpath(logo_path)

        logo_pixmap = QPixmap(logo_path)
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(
                target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._tb_logo.setPixmap(scaled_logo)
        else:
            self._tb_logo.setText("UN-HABITAT")
            self._tb_logo.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            self._tb_logo.setStyleSheet("color: #3890DF; background: transparent;")

        self._tb_logo.move(ScreenScale.w(12), ScreenScale.h(5))

        # Spacer to push window controls to the right
        spacer = QWidget()
        spacer.setStyleSheet("background: transparent;")
        lay.addWidget(spacer, 1)

        # Window control buttons
        btn_min = QPushButton("\u2013")
        btn_max = QPushButton("\u25a1")
        btn_close = QPushButton("\u2715")

        btn_max.setStyleSheet("""
            QPushButton {
                font-size: 28px;
                margin-bottom: 4px;
            }
        """)

        btn_min.setObjectName("win_btn")
        btn_max.setObjectName("win_btn")
        btn_close.setObjectName("win_close")

        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(ScreenScale.w(46), ScreenScale.h(32))
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setFocusPolicy(Qt.NoFocus)

        btn_min.clicked.connect(lambda: self.window().showMinimized())
        btn_close.clicked.connect(lambda: self.window().close())

        lay.addWidget(btn_min)
        lay.addWidget(btn_max)
        lay.addWidget(btn_close)

        self.titlebar.raise_()

    # ── Logic methods ──

    def set_data_mode(self, mode: str, db=None):
        """Set auth service (always API)."""
        self.auth_service = ApiAuthService()
        logger.info("Login: using API auth")

    def _toggle_password_visibility(self):
        """Toggle password visibility"""
        self.password_visible = not self.password_visible
        if self.password_visible:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def _on_login(self):
        """Handle login attempt with lockout enforcement."""
        from datetime import datetime, timedelta

        if self._lockout_until and datetime.now() < self._lockout_until:
            remaining = int((self._lockout_until - datetime.now()).total_seconds()) // 60 + 1
            self._show_error(tr("page.login.account_locked", minutes=remaining))
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error(tr("page.login.fields_required"))
            return

        self._set_login_loading(True)

        from services.api_worker import ApiWorker
        worker = ApiWorker(self.auth_service.authenticate, username, password)
        worker.finished.connect(lambda result: self._on_login_result(result, username))
        worker.error.connect(lambda msg: self._on_login_error(msg))
        worker.start()
        self._login_worker = worker

    def _on_login_result(self, result, username):
        """Handle login result from async worker."""
        from datetime import datetime, timedelta
        self._set_login_loading(False)

        if isinstance(result, Exception):
            self._show_error(tr("page.login.connection_error"))
            return

        user, error = result

        if user:
            from app.config import Roles
            if user.role in Roles.NON_LOGIN_ROLES:
                self._show_error(tr("page.login.not_authorized"))
                return

            self._failed_attempts = 0
            self._lockout_until = None
            logger.info(f"Login successful: {username}")
            self.error_label.hide()
            self.login_successful.emit(user)
        else:
            self._failed_attempts += 1
            logger.warning(f"Login failed: {username} (attempt {self._failed_attempts})")

            max_attempts, lockout_minutes = self._get_lockout_settings()
            if max_attempts > 0 and self._failed_attempts >= max_attempts:
                self._lockout_until = datetime.now() + timedelta(minutes=lockout_minutes)
                self._show_error(tr("page.login.lockout_exceeded", minutes=lockout_minutes))
                logger.warning(f"Account locked for {lockout_minutes} min after {self._failed_attempts} failed attempts")
            else:
                remaining = max_attempts - self._failed_attempts
                if max_attempts > 0 and remaining <= 3:
                    self._show_error(tr("page.login.invalid_credentials_remaining", remaining=remaining))
                else:
                    self._show_error(tr("page.login.invalid_credentials"))

    def _on_login_error(self, error_msg: str):
        """Handle login worker exception — reset loading state and show error."""
        self._set_login_loading(False)
        logger.error(f"Login error: {error_msg}")
        self._show_error(tr("page.login.connection_error"))

    def _set_login_loading(self, loading: bool):
        """Toggle login button loading state."""
        self.login_btn.setEnabled(not loading)
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
        if loading:
            self._original_btn_text = self.login_btn.text()
            self.login_btn.setText(tr("page.login.signing_in"))
        else:
            self.login_btn.setText(getattr(self, '_original_btn_text', tr("page.login.sign_in")))

    def _get_lockout_settings(self) -> tuple:
        """Get lockout settings from SecurityService."""
        try:
            from services.security_service import SecurityService
            if self.db:
                svc = SecurityService(self.db)
            else:
                from repositories.database import Database
                svc = SecurityService(Database())
            settings = svc.get_settings()
            return settings.max_failed_login_attempts, settings.account_lockout_duration_minutes
        except Exception as e:
            logger.warning(f"Could not load lockout settings: {e}")
            return 5, 15

    def _show_error(self, message: str):
        """Show error message"""
        self.error_label.setText(message)
        self.error_label.show()

    def _hide_error(self):
        """Hide error message"""
        if self.error_label.isVisible():
            self.error_label.hide()

    def _clear_form(self):
        """Clear form fields"""
        self.username_input.clear()
        self.password_input.clear()
        self.error_label.hide()

    def refresh(self, data=None):
        """Refresh the page"""
        self._clear_form()
        self.username_input.setFocus()
        QTimer.singleShot(100, self._animate_card_entrance)

    def _animate_card_entrance(self):
        """Slide the login panel in from the right."""
        start_pos = self.login_card.pos() + QPoint(40, 0)
        end_pos = self.login_card.pos()
        self._card_slide = QPropertyAnimation(self.login_card, b"pos")
        self._card_slide.setDuration(700)
        self._card_slide.setStartValue(start_pos)
        self._card_slide.setEndValue(end_pos)
        self._card_slide.setEasingCurve(QEasingCurve.OutCubic)
        self._card_slide.start()

    def update_language(self, is_arabic: bool):
        """Update language — text direction changes but panel positions stay fixed."""
        direction = get_layout_direction()
        self.setLayoutDirection(direction)
        # Keep split container fixed (deco always left, card always right)
        if hasattr(self, '_split_container'):
            self._split_container.setLayoutDirection(Qt.LeftToRight)
        # Inner panels follow text direction for proper alignment
        if hasattr(self, '_deco_panel'):
            self._deco_panel.setLayoutDirection(direction)
        if hasattr(self, 'login_card'):
            self.login_card.setLayoutDirection(direction)
        self._panel_title.setText(tr("page.login.sign_in"))
        self._panel_subtitle.setText(tr("page.login.subtitle"))
        self._username_label.setText(tr("page.login.username"))
        self.username_input.setPlaceholderText(tr("page.login.username_placeholder"))
        self._password_label.setText(tr("page.login.password"))
        self.password_input.setPlaceholderText(tr("page.login.password_placeholder"))
        self.login_btn.setText(tr("page.login.sign_in"))
        if hasattr(self, "_deco_ar_label"):
            self._deco_ar_label.setText(tr("page.login.title"))
        if hasattr(self, "_deco_en_label"):
            self._deco_en_label.setText(tr("page.login.subtitle"))
        if hasattr(self, "_lang_btn"):
            self._update_lang_button()
        if hasattr(self, "_pill_label"):
            pill_text = "\u0627\u0644\u0625\u0639\u062f\u0627\u062f\u0627\u062a" if tm_get_language() == "ar" else "Settings"
            self._pill_label.setText("\u25C8  " + pill_text)
        if hasattr(self, "_btn_settings"):
            server_text = "\u0627\u0644\u062e\u0627\u062f\u0645" if tm_get_language() == "ar" else "Server"
            self._btn_settings.setText("\u25A3  " + server_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "titlebar") and self.titlebar:
            self.titlebar.setGeometry(0, 0, self.width(), 33)
            self.titlebar.raise_()
        if hasattr(self, "_pill") and self._pill:
            self._pill.move(16, 43)
            self._pill.raise_()
        # Responsive card width based on right panel size
        if hasattr(self, "login_card") and self.login_card:
            right_panel_w = int(self.width() * 0.42)
            card_w = max(380, min(520, int(right_panel_w * 0.78)))
            self.login_card.setFixedWidth(card_w)

    def _open_server_settings(self):
        """Open the server settings dialog."""
        from ui.components.dialogs.server_settings_dialog import ServerSettingsDialog
        ServerSettingsDialog.show_settings(parent=self)

    def _toggle_language(self):
        """Toggle between Arabic and English."""
        current = tm_get_language()
        new_lang = "en" if current == "ar" else "ar"
        tm_set_language(new_lang)
        save_language(new_lang)
        is_arabic = (new_lang == "ar")
        self.update_language(is_arabic)

    def _update_lang_button(self):
        """Update language button text based on current language."""
        current = tm_get_language()
        self._lang_btn.setText("English" if current == "ar" else "\u0639\u0631\u0628\u064a")

    def _apply_password_style(self, icon_on_left: bool):
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(10, 22, 40, 153);
                border: 1px solid rgba(56, 144, 223, 51);
                border-radius: 10px;
                padding: 0 4px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid rgba(56, 144, 223, 153);
                outline: none;
            }
            QLineEdit::placeholder {
                color: rgba(139, 172, 200, 102);
            }
            QLineEdit QToolButton {
                border: none;
                background: transparent;
                padding: 0px 6px;
            }
            QLineEdit QToolButton:hover {
                background: rgba(56,144,223,0.12);
                border-radius: 8px;
            }
        """)

    def _on_password_text_changed(self, text):
        if (not text.strip()) or self._arabic_re.search(text):
            self.password_input.setLayoutDirection(Qt.RightToLeft)
            self.password_input.setAlignment(Qt.AlignRight)
            self.password_input.setTextMargins(44, 0, 12, 0)
        else:
            self.password_input.setLayoutDirection(Qt.LeftToRight)
            self.password_input.setAlignment(Qt.AlignLeft)
            self.password_input.setTextMargins(12, 0, 44, 0)
