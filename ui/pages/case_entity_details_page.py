# -*- coding: utf-8 -*-
"""
Case Entity Details Page — Full details of a Case entity with
survey/claim mini-cards, toggle-editable action, and revisit flow.
"""

import math
import random
import time
from typing import Optional, List, Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QSizePolicy, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QDialog, QComboBox, QTextEdit,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QTimer, QRectF, QPoint,
    QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QRadialGradient, QPen, QFont,
    QPainterPath, QCursor, QIcon,
)

from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.logo import LogoWidget
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from services.api_worker import ApiWorker
from models.case import Case
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
#  Status style maps (same as case_management_page)
# ---------------------------------------------------------------------------

_CASE_STATUS_STYLES = {
    1: {  # Open
        "bg": "#ECFDF5", "fg": "#059669", "border": "#6EE7B7",
        "glow": "rgba(5, 150, 105, 0.12)", "label_key": "page.case_entity.status_open",
        "strip": "#059669",
    },
    2: {  # Closed
        "bg": "#FEF2F2", "fg": "#DC2626", "border": "#FECACA",
        "glow": "rgba(220, 38, 38, 0.12)", "label_key": "page.case_entity.status_closed",
        "strip": "#DC2626",
    },
}


# ---------------------------------------------------------------------------
#  _AccentLine — Thin animated blue gradient line
# ---------------------------------------------------------------------------

class _AccentLine(QWidget):
    """Thin gradient line with animated glow pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self._glow_opacity = 0.0
        self._glow_anim = QPropertyAnimation(self, b"glowOpacity")
        self._glow_anim.setDuration(600)
        self._glow_anim.setEasingCurve(QEasingCurve.OutQuad)

    @pyqtProperty(float)
    def glowOpacity(self):
        return self._glow_opacity

    @glowOpacity.setter
    def glowOpacity(self, val: float):
        self._glow_opacity = val
        self.update()

    def pulse(self):
        self._glow_anim.stop()
        self._glow_anim.setStartValue(0.7)
        self._glow_anim.setEndValue(0.0)
        self._glow_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(56, 144, 223, 0))
        grad.setColorAt(0.2, QColor(56, 144, 223, 80))
        grad.setColorAt(0.5, QColor(120, 190, 255, 140))
        grad.setColorAt(0.8, QColor(56, 144, 223, 80))
        grad.setColorAt(1.0, QColor(56, 144, 223, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawRect(0, 0, w, h)

        if self._glow_opacity > 0.01:
            glow_alpha = int(self._glow_opacity * 180)
            glow_grad = QLinearGradient(0, 0, w, 0)
            glow_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
            glow_grad.setColorAt(0.3, QColor(91, 168, 240, glow_alpha))
            glow_grad.setColorAt(0.5, QColor(120, 190, 255, min(255, int(glow_alpha * 1.3))))
            glow_grad.setColorAt(0.7, QColor(91, 168, 240, glow_alpha))
            glow_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
            painter.setBrush(glow_grad)
            painter.drawRect(0, 0, w, h)

        painter.end()


# ---------------------------------------------------------------------------
#  _GlowingCard — Card with animated orbiting blue border light
# ---------------------------------------------------------------------------

class _GlowingCard(QFrame):
    """Card base with animated glowing border effect."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow_phase = 0.0
        self._glow_enabled = True

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 25))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(
            f"_GlowingCard {{ background-color: {Colors.SURFACE}; border: none; border-radius: 12px; }}"
        )

        self._phase_anim = QPropertyAnimation(self, b"glowPhase")
        self._phase_anim.setDuration(3000)
        self._phase_anim.setStartValue(0.0)
        self._phase_anim.setEndValue(1.0)
        self._phase_anim.setLoopCount(-1)
        self._phase_anim.setEasingCurve(QEasingCurve.Linear)
        self._phase_anim.start()

    @pyqtProperty(float)
    def glowPhase(self):
        return self._glow_phase

    @glowPhase.setter
    def glowPhase(self, val):
        self._glow_phase = val
        self.update()

    def set_glow_enabled(self, enabled):
        self._glow_enabled = enabled
        if enabled and self._phase_anim.state() != QPropertyAnimation.Running:
            self._phase_anim.start()
        elif not enabled:
            self._phase_anim.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        r = 12

        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)
        painter.fillPath(bg_path, QColor(Colors.SURFACE))

        if self._glow_enabled:
            perimeter = 2 * (w + h)
            light_pos = self._glow_phase * perimeter
            border_path = QPainterPath()
            border_path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

            painter.setPen(QPen(QColor(56, 144, 223, 25), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(border_path)

            for offset in range(-3, 4):
                pos = (light_pos + offset * (perimeter * 0.15 / 6)) % perimeter
                alpha = int(60 * (1 - abs(offset) / 3.5))
                px, py = self._pos_on_rect(pos, w, h)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(56, 144, 223, alpha))
                painter.drawEllipse(int(px) - 3, int(py) - 3, 6, 6)

        painter.end()

    def _pos_on_rect(self, pos, w, h):
        if pos < w:
            return pos, 0
        pos -= w
        if pos < h:
            return w, pos
        pos -= h
        if pos < w:
            return w - pos, h
        pos -= w
        return 0, h - pos


# ---------------------------------------------------------------------------
#  _WatermarkScrollArea — Scroll area with pulsing logo watermark
# ---------------------------------------------------------------------------

class _WatermarkScrollArea(QScrollArea):
    """Scroll area with pulsing logo watermark behind content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logo = LogoWidget(height=120, parent=self)
        self._logo_effect = QGraphicsOpacityEffect(self._logo)
        self._logo_effect.setOpacity(0.04)
        self._logo.setGraphicsEffect(self._logo_effect)
        self._logo.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._logo.setStyleSheet("background: transparent;")

        self._logo_opacity = 0.04
        self._logo_anim = QPropertyAnimation(self, b"logoOpacity")
        self._logo_anim.setDuration(5000)
        self._logo_anim.setStartValue(0.03)
        self._logo_anim.setKeyValueAt(0.5, 0.06)
        self._logo_anim.setEndValue(0.03)
        self._logo_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._logo_anim.setLoopCount(-1)
        self._logo_anim.start()

    @pyqtProperty(float)
    def logoOpacity(self):
        return self._logo_opacity

    @logoOpacity.setter
    def logoOpacity(self, val):
        self._logo_opacity = val
        self._logo_effect.setOpacity(val)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        lw = self._logo.width() if self._logo.pixmap() else 120
        lh = self._logo.height() if self._logo.pixmap() else 120
        self._logo.move(
            (self.width() - lw) // 2,
            (self.height() - lh) // 2,
        )
        self._logo.raise_()


# ---------------------------------------------------------------------------
#  _CaseEntityHeader — Light header with back, case number, badges, actions
# ---------------------------------------------------------------------------

class _CaseEntityHeader(QWidget):
    """Light header with case identification, status badges, and action buttons."""

    back_clicked = pyqtSignal()
    toggle_editable_clicked = pyqtSignal()
    revisit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Row 1: Back button + Case number + action buttons
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # Back button
        self._back_btn = QPushButton()
        self._back_btn.setFixedSize(ScreenScale.w(40), ScreenScale.h(40))
        self._back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(56, 144, 223, 0.2);
                border-radius: 12px;
                color: #3890DF; font-size: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #EFF6FF, stop:1 #DBEAFE
                );
                border: 1.5px solid rgba(56, 144, 223, 0.4);
            }
            QPushButton:pressed { background: #DBEAFE; }
        """)
        back_pixmap = Icon.load_pixmap("arrow_back", 16)
        if back_pixmap and not back_pixmap.isNull():
            self._back_btn.setIcon(QIcon(back_pixmap))
        else:
            self._back_btn.setText("\u2190")
        self._back_btn.clicked.connect(self.back_clicked.emit)
        row1.addWidget(self._back_btn)

        # Case number label
        self._num_label = QLabel("")
        self._num_label.setFont(create_font(size=15, weight=QFont.Bold))
        self._num_label.setStyleSheet("color: #2A6CB5; background: transparent;")
        self._num_label.setMinimumWidth(ScreenScale.w(200))
        self._num_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._num_label.setLayoutDirection(Qt.LeftToRight)
        self._num_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
            if get_layout_direction() == Qt.RightToLeft
            else Qt.AlignLeft | Qt.AlignVCenter
        )
        num_glow = QGraphicsDropShadowEffect(self._num_label)
        num_glow.setBlurRadius(12)
        num_glow.setOffset(0, 0)
        num_glow.setColor(QColor(56, 144, 223, 80))
        self._num_label.setGraphicsEffect(num_glow)
        row1.addWidget(self._num_label)

        row1.addStretch()

        # Toggle editable button (admin/data_manager only)
        self._toggle_editable_btn = QPushButton(tr("page.case_entity.lock_editing"))
        self._toggle_editable_btn.setFixedSize(ScreenScale.w(140), ScreenScale.h(38))
        self._toggle_editable_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle_editable_btn.setVisible(False)
        self._toggle_editable_btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._toggle_editable_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(56, 144, 223, 0.2);
                border-radius: 12px;
                color: #64748B; padding: 0 14px;
            }
            QPushButton:hover {
                background: #FFF7ED;
                border: 1.5px solid rgba(234, 179, 8, 0.3);
                color: #B45309;
            }
            QPushButton:pressed { background: #FEF3C7; }
            QPushButton:disabled {
                color: #C0C8D0; background: #F5F7FA;
                border-color: #E8ECF0;
            }
        """)
        self._toggle_editable_btn.clicked.connect(self.toggle_editable_clicked.emit)
        row1.addWidget(self._toggle_editable_btn)

        # Revisit button (admin/data_manager only)
        self._revisit_btn = QPushButton(tr("page.case_entity.revisit"))
        self._revisit_btn.setFixedSize(ScreenScale.w(140), ScreenScale.h(38))
        self._revisit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._revisit_btn.setVisible(False)
        self._revisit_btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._revisit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3890DF, stop:1 #5BA8F0
                );
                color: white; border: none;
                border-radius: 12px; padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2A7BC9, stop:1 #4A98E0
                );
            }
            QPushButton:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1E6CB5, stop:1 #3A88D0
                );
            }
            QPushButton:disabled {
                background: #E2E8F0; color: #94A3B8;
            }
        """)
        self._revisit_btn.clicked.connect(self.revisit_clicked.emit)
        row1.addWidget(self._revisit_btn)

        outer.addLayout(row1)
        outer.addSpacing(8)

        # Row 2: Badges
        self._badges_widget = QWidget()
        self._badges_widget.setStyleSheet("background: transparent;")
        self._badges_layout = QHBoxLayout(self._badges_widget)
        self._badges_layout.setContentsMargins(48, 0, 0, 0)
        self._badges_layout.setSpacing(8)
        self._badges_layout.addStretch()
        outer.addWidget(self._badges_widget)
        outer.addSpacing(8)

        # Accent line
        self._accent_line = _AccentLine()
        outer.addWidget(self._accent_line)

    def set_case_info(self, case_number: str, badges: list):
        """Update header with case identification and badges."""
        self._num_label.setText(case_number)

        # Clear old badges
        while self._badges_layout.count():
            item = self._badges_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for text, bg, fg in badges:
            badge = QLabel(text)
            badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedHeight(ScreenScale.h(22))
            badge.setStyleSheet(
                f"QLabel {{ background: {bg}; color: {fg}; "
                f"border-radius: 11px; padding: 0 10px; border: none; }}"
            )
            self._badges_layout.insertWidget(self._badges_layout.count() - 1, badge)

    def update_editable_state(self, is_editable: bool):
        """Update toggle button text based on current editable state."""
        if is_editable:
            self._toggle_editable_btn.setText(tr("page.case_entity.lock_editing"))
        else:
            self._toggle_editable_btn.setText(tr("page.case_entity.unlock_editing"))
        self._revisit_btn.setEnabled(is_editable)

    def set_actions_visible(self, visible: bool):
        """Show/hide action buttons based on role."""
        self._toggle_editable_btn.setVisible(visible)
        self._revisit_btn.setVisible(visible)

    def update_texts(self):
        """Update texts and layout direction for language change."""
        self.setLayoutDirection(get_layout_direction())
        self._revisit_btn.setText(tr("page.case_entity.revisit"))
        is_rtl = get_layout_direction() == Qt.RightToLeft
        self._num_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter if is_rtl else Qt.AlignLeft | Qt.AlignVCenter
        )

    def pulse_accent(self):
        self._accent_line.pulse()


# ---------------------------------------------------------------------------
#  _SurveyMiniCard — Compact clickable card for a linked survey
# ---------------------------------------------------------------------------

class _SurveyMiniCard(QFrame):
    """Compact card showing survey summary, clickable to navigate."""

    clicked = pyqtSignal(str)  # survey_id

    _CARD_BG = "#F7FAFF"
    _CARD_BG_HOVER = "#F0F5FF"

    def _get_lift(self):
        return self._lift_value

    def _set_lift(self, v):
        self._lift_value = v
        lv = int(v)
        self.setContentsMargins(0, max(0, -lv), 0, max(0, lv))
        self.update()

    lift = pyqtProperty(float, _get_lift, _set_lift)

    def __init__(self, survey_data: dict, parent=None):
        super().__init__(parent)
        self._survey_data = survey_data
        self._survey_id = survey_data.get("id") or survey_data.get("surveyId", "")
        self._hovered = False
        self._pressed = False
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(ScreenScale.h(80))
        self.setMouseTracking(True)
        self._build_ui()

    def _build_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            _SurveyMiniCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG}, stop:1 #F0F5FF);
                border-radius: 12px;
                border: 1px solid #E2EAF2;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 18))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 16, 0)
        outer.setSpacing(0)

        content = QVBoxLayout()
        content.setContentsMargins(18, 8, 0, 8)
        content.setSpacing(3)

        # Row 1: Reference code + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        ref_code = self._survey_data.get("referenceCode") or self._survey_id[:12]
        ref_label = QLabel(str(ref_code))
        ref_label.setFont(create_font(size=12, weight=QFont.Bold))
        ref_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        ref_label.setMaximumWidth(ScreenScale.w(400))
        apply_label_alignment(ref_label)
        row1.addWidget(ref_label)
        row1.addStretch()


        content.addLayout(row1)

        # Row 2: Date
        date_str = ""
        for key in ("createdAtUtc", "surveyDate", "createdAt"):
            val = self._survey_data.get(key)
            if val:
                date_str = str(val)[:10]
                break
        if date_str and not date_str.startswith("0001"):
            date_label = QLabel(date_str)
            date_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            date_label.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
            )
            apply_label_alignment(date_label)
            content.addWidget(date_label)

        outer.addLayout(content, 1)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 11, 11)
        painter.setClipPath(clip)

        # Subtle shimmer sweep
        sweep_pos = (math.sin(t * 0.6 + self._shimmer_offset) + 1) / 2
        sweep_x = int(sweep_pos * w)
        shimmer_grad = QLinearGradient(sweep_x - 120, 0, sweep_x + 120, 0)
        shimmer_grad.setColorAt(0, QColor(56, 144, 223, 0))
        shimmer_grad.setColorAt(0.5, QColor(120, 190, 255, 8))
        shimmer_grad.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.fillRect(QRectF(0, 0, w, h), shimmer_grad)

        # Top edge accent on hover
        if self._hovered:
            top_grad = QLinearGradient(0, 0, w, 0)
            top_grad.setColorAt(0, QColor(56, 144, 223, 0))
            top_grad.setColorAt(0.2, QColor(56, 144, 223, 35))
            top_grad.setColorAt(0.5, QColor(91, 168, 240, 55))
            top_grad.setColorAt(0.8, QColor(56, 144, 223, 35))
            top_grad.setColorAt(1, QColor(56, 144, 223, 0))
            painter.fillRect(QRectF(0, 0, w, 2), top_grad)

        painter.setClipping(False)

        # Chevron (RTL-aware)
        is_rtl = self.layoutDirection() == Qt.RightToLeft
        chevron_x = 14 if is_rtl else w - 22
        chevron_alpha = 140 if self._hovered else 35
        painter.setPen(QPen(QColor(56, 144, 223, chevron_alpha), 1.5,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cy = h / 2
        if is_rtl:
            painter.drawLine(int(chevron_x + 5), int(cy - 4), int(chevron_x), int(cy))
            painter.drawLine(int(chevron_x), int(cy), int(chevron_x + 5), int(cy + 4))
        else:
            painter.drawLine(int(chevron_x), int(cy - 4), int(chevron_x + 5), int(cy))
            painter.drawLine(int(chevron_x + 5), int(cy), int(chevron_x), int(cy + 4))

        painter.end()

    def _animate_lift(self, target):
        if self._lift_anim and self._lift_anim.state() == QPropertyAnimation.Running:
            self._lift_anim.stop()
        self._lift_anim = QPropertyAnimation(self, b"lift")
        self._lift_anim.setDuration(180)
        self._lift_anim.setStartValue(self._lift_value)
        self._lift_anim.setEndValue(target)
        self._lift_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._lift_anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(f"""
            _SurveyMiniCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG_HOVER}, stop:1 #E8F0FE);
                border-radius: 12px;
                border: 1.5px solid rgba(56, 144, 223, 0.30);
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(30)
            eff.setOffset(0, 6)
            eff.setColor(QColor(56, 144, 223, 35))
        self._animate_lift(3.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.setStyleSheet(f"""
            _SurveyMiniCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG}, stop:1 #F0F5FF);
                border-radius: 12px;
                border: 1px solid #E2EAF2;
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(16)
            eff.setOffset(0, 3)
            eff.setColor(QColor(0, 0, 0, 18))
        self._animate_lift(0.0)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            if self._survey_id:
                self.clicked.emit(self._survey_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
#  _ClaimMiniCard — Compact clickable card for a linked claim
# ---------------------------------------------------------------------------

class _ClaimMiniCard(QFrame):
    """Compact card showing claim summary, clickable to navigate."""

    clicked = pyqtSignal(str)  # claim_id

    _CARD_BG = "#FFFBF7"
    _CARD_BG_HOVER = "#FFF5ED"

    def _get_lift(self):
        return self._lift_value

    def _set_lift(self, v):
        self._lift_value = v
        lv = int(v)
        self.setContentsMargins(0, max(0, -lv), 0, max(0, lv))
        self.update()

    lift = pyqtProperty(float, _get_lift, _set_lift)

    def __init__(self, claim_data: dict, parent=None):
        super().__init__(parent)
        self._claim_data = claim_data
        self._claim_id = claim_data.get("id") or claim_data.get("claimId", "")
        self._hovered = False
        self._pressed = False
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(ScreenScale.h(80))
        self.setMouseTracking(True)
        self._build_ui()

    def _build_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            _ClaimMiniCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG}, stop:1 #FFF0E5);
                border-radius: 12px;
                border: 1px solid #FDE8D8;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 18))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 16, 0)
        outer.setSpacing(0)

        # Orange/amber status strip
        strip = QFrame()
        strip.setFixedWidth(4)
        is_rtl = get_layout_direction() == Qt.RightToLeft
        corner = "right" if is_rtl else "left"
        strip.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 #F59E0B, stop:0.5 #FBBF24, stop:1 #F59E0B); "
            f"border-top-{corner}-radius: 12px; border-bottom-{corner}-radius: 12px;"
        )
        outer.addWidget(strip)

        content = QVBoxLayout()
        content.setContentsMargins(14, 8, 0, 8)
        content.setSpacing(3)

        # Row 1: Claim number + type badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        claim_number = self._claim_data.get("claimNumber") or self._claim_id[:12]
        num_label = QLabel(str(claim_number))
        num_label.setFont(create_font(size=12, weight=QFont.Bold))
        num_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        num_label.setMaximumWidth(ScreenScale.w(400))
        apply_label_alignment(num_label)
        row1.addWidget(num_label)
        row1.addStretch()


        content.addLayout(row1)

        # Row 2: Claimant name or date
        claimant = self._claim_data.get("primaryClaimantName") or ""
        if claimant:
            name_label = QLabel(str(claimant))
            name_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            name_label.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
            )
            name_label.setMaximumWidth(ScreenScale.w(300))
            apply_label_alignment(name_label)
            content.addWidget(name_label)

        outer.addLayout(content, 1)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 11, 11)
        painter.setClipPath(clip)

        # Subtle shimmer sweep (warm tint)
        sweep_pos = (math.sin(t * 0.6 + self._shimmer_offset) + 1) / 2
        sweep_x = int(sweep_pos * w)
        shimmer_grad = QLinearGradient(sweep_x - 120, 0, sweep_x + 120, 0)
        shimmer_grad.setColorAt(0, QColor(245, 158, 11, 0))
        shimmer_grad.setColorAt(0.5, QColor(251, 191, 36, 8))
        shimmer_grad.setColorAt(1, QColor(245, 158, 11, 0))
        painter.setPen(Qt.NoPen)
        painter.fillRect(QRectF(0, 0, w, h), shimmer_grad)

        # Top edge accent on hover
        if self._hovered:
            top_grad = QLinearGradient(0, 0, w, 0)
            top_grad.setColorAt(0, QColor(245, 158, 11, 0))
            top_grad.setColorAt(0.2, QColor(245, 158, 11, 35))
            top_grad.setColorAt(0.5, QColor(251, 191, 36, 55))
            top_grad.setColorAt(0.8, QColor(245, 158, 11, 35))
            top_grad.setColorAt(1, QColor(245, 158, 11, 0))
            painter.fillRect(QRectF(0, 0, w, 2), top_grad)

        painter.setClipping(False)

        # Chevron (RTL-aware)
        is_rtl = self.layoutDirection() == Qt.RightToLeft
        chevron_x = 14 if is_rtl else w - 22
        chevron_alpha = 140 if self._hovered else 35
        painter.setPen(QPen(QColor(245, 158, 11, chevron_alpha), 1.5,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cy = h / 2
        if is_rtl:
            painter.drawLine(int(chevron_x + 5), int(cy - 4), int(chevron_x), int(cy))
            painter.drawLine(int(chevron_x), int(cy), int(chevron_x + 5), int(cy + 4))
        else:
            painter.drawLine(int(chevron_x), int(cy - 4), int(chevron_x + 5), int(cy))
            painter.drawLine(int(chevron_x + 5), int(cy), int(chevron_x), int(cy + 4))

        painter.end()

    def _animate_lift(self, target):
        if self._lift_anim and self._lift_anim.state() == QPropertyAnimation.Running:
            self._lift_anim.stop()
        self._lift_anim = QPropertyAnimation(self, b"lift")
        self._lift_anim.setDuration(180)
        self._lift_anim.setStartValue(self._lift_value)
        self._lift_anim.setEndValue(target)
        self._lift_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._lift_anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(f"""
            _ClaimMiniCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG_HOVER}, stop:1 #FFEDD5);
                border-radius: 12px;
                border: 1.5px solid rgba(245, 158, 11, 0.30);
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(30)
            eff.setOffset(0, 6)
            eff.setColor(QColor(245, 158, 11, 30))
        self._animate_lift(3.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.setStyleSheet(f"""
            _ClaimMiniCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG}, stop:1 #FFF0E5);
                border-radius: 12px;
                border: 1px solid #FDE8D8;
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(16)
            eff.setOffset(0, 3)
            eff.setColor(QColor(0, 0, 0, 18))
        self._animate_lift(0.0)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            if self._claim_id:
                self.clicked.emit(self._claim_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
#  CaseEntityDetailsPage — Main page
# ---------------------------------------------------------------------------

class CaseEntityDetailsPage(QWidget):
    """Full details page for a Case entity with mini-cards and actions."""

    back_requested = pyqtSignal()
    survey_clicked = pyqtSignal(str)
    claim_clicked = pyqtSignal(str)
    toggle_editable_requested = pyqtSignal(str, bool)  # case_id, new_value
    revisit_requested = pyqtSignal(dict)  # case data for revisit flow

    def __init__(self, parent=None):
        super().__init__(parent)
        self._case: Optional[Case] = None
        self._case_id: Optional[str] = None
        self._survey_details: List[dict] = []
        self._claim_details: List[dict] = []
        self._unit_details: dict = {}
        self._building_details: dict = {}
        self._loading = False
        self._user_role = "admin"
        self._show_actions = True

        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(StyleManager.page_background())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.content_padding_h(),
            PageDimensions.content_padding_v_top(),
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        main_layout.setSpacing(0)

        # Header
        self._header = _CaseEntityHeader()
        self._header.back_clicked.connect(self.back_requested.emit)
        self._header.toggle_editable_clicked.connect(self._on_toggle_editable)
        self._header.revisit_clicked.connect(self._on_revisit)
        main_layout.addWidget(self._header)
        main_layout.addSpacing(16)

        # Watermark scroll area
        self._scroll = _WatermarkScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(get_layout_direction())
        scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 40)
        self._scroll_layout.setSpacing(16)

        # Row 1: Case info + Property unit (side by side)
        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        self._case_info_card = _GlowingCard()
        self._case_info_layout = QVBoxLayout(self._case_info_card)
        self._case_info_layout.setContentsMargins(20, 20, 20, 20)
        self._case_info_layout.setSpacing(12)
        self._case_info_content = QVBoxLayout()
        self._case_info_content.setSpacing(12)
        self._case_info_layout.addLayout(self._case_info_content)
        info_row.addWidget(self._case_info_card, 1)

        self._property_card = _GlowingCard()
        self._property_layout = QVBoxLayout(self._property_card)
        self._property_layout.setContentsMargins(20, 20, 20, 20)
        self._property_layout.setSpacing(12)
        self._property_content = QVBoxLayout()
        self._property_content.setSpacing(12)
        self._property_layout.addLayout(self._property_content)
        info_row.addWidget(self._property_card, 1)

        self._scroll_layout.addLayout(info_row)

        # Surveys section
        self._surveys_card = _GlowingCard()
        self._surveys_card.set_glow_enabled(False)
        self._surveys_layout = QVBoxLayout(self._surveys_card)
        self._surveys_layout.setContentsMargins(20, 16, 20, 16)
        self._surveys_layout.setSpacing(10)
        self._surveys_content = QVBoxLayout()
        self._surveys_content.setSpacing(8)
        self._surveys_layout.addLayout(self._surveys_content)
        self._scroll_layout.addWidget(self._surveys_card)

        # Claims section
        self._claims_card = _GlowingCard()
        self._claims_card.set_glow_enabled(False)
        self._claims_layout = QVBoxLayout(self._claims_card)
        self._claims_layout.setContentsMargins(20, 16, 20, 16)
        self._claims_layout.setSpacing(10)
        self._claims_content = QVBoxLayout()
        self._claims_content.setSpacing(8)
        self._claims_layout.addLayout(self._claims_content)
        self._scroll_layout.addWidget(self._claims_card)

        # Notes section (hidden by default)
        self._notes_card = _GlowingCard()
        self._notes_card.set_glow_enabled(False)
        self._notes_card.setVisible(False)
        self._notes_layout = QVBoxLayout(self._notes_card)
        self._notes_layout.setContentsMargins(20, 16, 20, 16)
        self._notes_layout.setSpacing(8)
        self._notes_content = QVBoxLayout()
        self._notes_content.setSpacing(8)
        self._notes_layout.addLayout(self._notes_content)
        self._scroll_layout.addWidget(self._notes_card)

        self._scroll_layout.addStretch()
        self._scroll.setWidget(scroll_content)
        main_layout.addWidget(self._scroll, 1)

    # -- Section header helper --

    def _add_section_header(self, layout, icon_name, title, subtitle=""):
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            "QLabel { background-color: #ffffff; border: 1px solid #DBEAFE; border-radius: 7px; }"
        )
        icon_pixmap = Icon.load_pixmap(icon_name, size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        title_box.addWidget(title_lbl)
        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
            sub_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            title_box.addWidget(sub_lbl)

        h_layout.addWidget(icon_label)
        h_layout.addLayout(title_box)
        h_layout.addStretch()
        layout.addWidget(header)

    # -- Field helpers --

    def _create_field_pair(self, label_text, value_text):
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        lbl.setAlignment(Qt.AlignCenter)

        val = QLabel(str(value_text) if value_text else "-")
        val.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        val.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        val.setAlignment(Qt.AlignCenter)
        val.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addWidget(val)
        return container

    def _create_badge(self, text, bg_color, text_color):
        badge = QLabel(str(text))
        badge.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(26))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {bg_color}; color: {text_color}; "
            f"border: none; border-radius: 13px; padding: 2px 14px; }}"
        )
        return badge

    def _clear_layout(self, layout):
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # -- RBAC --

    def configure_for_role(self, role: str):
        """Configure visible actions based on user role."""
        self._user_role = role
        self._show_actions = role in ("admin", "data_manager")
        self._header.set_actions_visible(self._show_actions)

    # -- Data loading --

    def refresh(self, data=None):
        """Load case entity details. Accepts {case_id: ...}."""
        if data is None:
            return

        case_id = data.get("case_id") if isinstance(data, dict) else None
        if case_id:
            self._load_case_by_id(case_id)
        else:
            logger.warning("refresh() called with no usable data")

    def _load_case_by_id(self, case_id: str):
        if self._loading:
            return
        self._loading = True
        self._case_id = case_id
        self._spinner.show_loading(tr("page.case_entity.loading"))

        def _fetch(cid):
            from services.api_client import get_api_client
            api = get_api_client()
            return api.get_case_by_id(cid)

        self._load_worker = ApiWorker(_fetch, case_id)
        self._load_worker.finished.connect(self._on_case_loaded)
        self._load_worker.error.connect(self._on_case_load_error)
        self._load_worker.start()

    def _on_case_loaded(self, data):
        self._loading = False
        self._spinner.hide_loading()
        if data:
            self._case = Case.from_api_dict(data)
            self._populate_all()
            self._load_linked_entities()
            self._header.pulse_accent()
        else:
            Toast.show_toast(
                self,
                tr("page.case_entity.load_error"),
                Toast.ERROR,
            )
            logger.warning("Failed to load case data — empty result")

    def _on_case_load_error(self, error_msg):
        self._loading = False
        self._spinner.hide_loading()
        Toast.show_toast(
            self,
            tr("page.case_entity.load_error"),
            Toast.ERROR,
        )
        logger.warning(f"Failed to load case data: {error_msg}")

    def _load_linked_entities(self):
        """Fetch survey/claim summaries and property unit/building details."""
        if not self._case:
            return

        survey_ids = self._case.survey_ids or []
        claim_ids = self._case.claim_ids or []
        property_unit_id = self._case.property_unit_id or ""

        def _fetch_linked():
            from services.api_client import get_api_client
            api = get_api_client()
            surveys = []
            claims = []

            for sid in survey_ids:
                try:
                    detail = api.get_office_survey_detail(sid)
                    surveys.append(detail)
                except Exception as e:
                    logger.warning(f"Failed to fetch survey {sid}: {e}")
                    surveys.append({"id": sid, "referenceCode": sid[:12]})

            for cid in claim_ids:
                try:
                    detail = api.get_claim_by_id(cid)
                    claims.append(detail)
                except Exception as e:
                    logger.warning(f"Failed to fetch claim {cid}: {e}")
                    claims.append({"id": cid, "claimNumber": cid[:12]})

            unit_data = {}
            building_data = {}
            if property_unit_id:
                try:
                    unit_data = api.get_property_unit_by_id(property_unit_id) or {}
                    bid = unit_data.get("buildingId")
                    if bid:
                        building_data = api.get_building_by_id(bid) or {}
                except Exception as e:
                    logger.warning(f"Failed to fetch unit/building details: {e}")

            return {
                "surveys": surveys, "claims": claims,
                "unit": unit_data, "building": building_data,
            }

        self._linked_worker = ApiWorker(_fetch_linked)
        self._linked_worker.finished.connect(self._on_linked_loaded)
        self._linked_worker.error.connect(self._on_linked_load_error)
        self._linked_worker.start()

    def _on_linked_loaded(self, data):
        if not data:
            return
        self._survey_details = data.get("surveys", [])
        self._claim_details = data.get("claims", [])
        self._unit_details = data.get("unit", {})
        self._building_details = data.get("building", {})
        self._populate_surveys_section()
        self._populate_claims_section()
        self._populate_property_info()

    def _on_linked_load_error(self, error_msg):
        logger.warning(f"Failed to load linked entities: {error_msg}")

    # -- Populate sections --

    def _populate_all(self):
        """Populate all sections from self._case."""
        self._populate_header()
        self._populate_case_info()
        self._populate_property_info()
        self._populate_surveys_section()
        self._populate_claims_section()
        self._populate_notes_section()

    def _populate_header(self):
        if not self._case:
            return

        case_number = self._case.case_number or self._case.id[:16]

        badges = []

        if not self._case.is_editable:
            badges.append((
                tr("page.case_entity.not_editable"),
                "#FEF2F2", "#DC2626",
            ))
        else:
            badges.append((
                tr("page.case_entity.editable"),
                "#ECFDF5", "#059669",
            ))

        opened = (self._case.opened_date or "")[:10]
        if opened and not opened.startswith("0001"):
            badges.append((opened, "#F8FAFC", "#64748B"))

        self._header.set_case_info(case_number, badges)
        self._header.update_editable_state(self._case.is_editable)
        self._header.set_actions_visible(self._show_actions)

    def _populate_case_info(self):
        if not self._case:
            return
        self._clear_layout(self._case_info_content)

        self._add_section_header(
            self._case_info_content, "blue",
            tr("page.case_entity.section_case_info"),
            tr("page.case_entity.section_case_info_sub"),
        )

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        for c in range(3):
            grid.setColumnStretch(c, 1)

        status_style = _CASE_STATUS_STYLES.get(self._case.status, _CASE_STATUS_STYLES[1])

        opened = (self._case.opened_date or "")[:10]
        if not opened or opened.startswith("0001"):
            opened = "-"
        closed = (self._case.closed_date or "")[:10]
        if not closed or closed.startswith("0001"):
            closed = "-"

        fields = [
            (tr("page.case_entity.field_case_number"),
             self._case.case_number or "-"),
            (tr("page.case_entity.field_status"),
             tr(status_style["label_key"])),
            (tr("page.case_entity.field_open_date"),
             opened),
            (tr("page.case_entity.field_close_date"),
             closed),
            (tr("page.case_entity.field_survey_count"),
             str(self._case.survey_count)),
            (tr("page.case_entity.field_claim_count"),
             str(self._case.claim_count)),
        ]

        for i, (label, value) in enumerate(fields):
            row = i // 3
            col = i % 3
            grid.addWidget(self._create_field_pair(label, value), row, col)

        self._case_info_content.addLayout(grid)

    def _populate_property_info(self):
        if not self._case:
            return
        self._clear_layout(self._property_content)

        self._add_section_header(
            self._property_content, "blue",
            tr("page.case_entity.section_property"),
            tr("page.case_entity.section_property_sub"),
        )

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        for c in range(3):
            grid.setColumnStretch(c, 1)

        bd = self._building_details
        ud = self._unit_details

        # Building code (formatted with dashes)
        raw_code = (bd.get("buildingCode") or bd.get("buildingId") or
                    bd.get("building_id") or "")
        if isinstance(raw_code, str) and len(raw_code) == 17 and "-" not in raw_code:
            building_code = (f"{raw_code[0:2]}-{raw_code[2:4]}-{raw_code[4:6]}-"
                             f"{raw_code[6:9]}-{raw_code[9:12]}-{raw_code[12:17]}")
        else:
            building_code = raw_code or "-"

        # Unit number
        unit_number = str(ud.get("unitIdentifier") or ud.get("unitNumber") or "-")

        # Floor display
        floor_val = ud.get("floorNumber")
        if floor_val is not None:
            try:
                fn = int(floor_val)
                if fn == 0:
                    floor_display = tr("page.case_entity.floor_ground")
                elif fn < 0:
                    floor_display = tr("page.case_entity.floor_basement", n=abs(fn))
                else:
                    floor_display = str(fn)
            except (ValueError, TypeError):
                floor_display = str(floor_val)
        else:
            floor_display = "-"

        # Unit type
        from services.display_mappings import get_unit_type_display
        unit_type_raw = ud.get("unitType")
        unit_type_display = get_unit_type_display(unit_type_raw) if unit_type_raw else "-"

        # Location from building
        gov_name = bd.get("governorateNameArabic") or bd.get("governorate_name_ar") or bd.get("governorateName") or ""
        sub_name = bd.get("subdistrictNameArabic") or bd.get("subdistrict_name_ar") or bd.get("subdistrictName") or ""
        location_parts = [p for p in (sub_name, gov_name) if p]
        location = " - ".join(location_parts) if location_parts else "-"

        fields = [
            (tr("page.case_entity.field_building_code"), building_code),
            (tr("page.case_entity.field_unit_number"), unit_number),
            (tr("page.case_entity.field_floor"), floor_display),
            (tr("page.case_entity.field_unit_type"), unit_type_display),
            (tr("page.case_entity.field_location"), location),
            (tr("page.case_entity.field_relations_count"),
             str(self._case.person_property_relation_count)),
        ]

        for i, (label, value) in enumerate(fields):
            row = i // 3
            col = i % 3
            grid.addWidget(self._create_field_pair(label, value), row, col)

        self._property_content.addLayout(grid)

    def _populate_surveys_section(self):
        self._clear_layout(self._surveys_content)

        count = self._case.survey_count if self._case else 0
        self._add_section_header(
            self._surveys_content, "blue",
            tr("page.case_entity.section_surveys", count=count),
            tr("page.case_entity.section_surveys_sub"),
        )

        if self._survey_details:
            for survey_data in self._survey_details:
                card = _SurveyMiniCard(survey_data)
                card.clicked.connect(self.survey_clicked.emit)
                self._surveys_content.addWidget(card)
        elif self._case and self._case.survey_ids:
            loading_lbl = QLabel(tr("page.case_entity.loading_surveys"))
            loading_lbl.setFont(create_font(size=10))
            loading_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            loading_lbl.setAlignment(Qt.AlignCenter)
            self._surveys_content.addWidget(loading_lbl)
        else:
            empty_lbl = QLabel(tr("page.case_entity.empty_surveys"))
            empty_lbl.setFont(create_font(size=10))
            empty_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self._surveys_content.addWidget(empty_lbl)

    def _populate_claims_section(self):
        self._clear_layout(self._claims_content)

        count = self._case.claim_count if self._case else 0
        self._add_section_header(
            self._claims_content, "blue",
            tr("page.case_entity.section_claims", count=count),
            tr("page.case_entity.section_claims_sub"),
        )

        if self._claim_details:
            for claim_data in self._claim_details:
                card = _ClaimMiniCard(claim_data)
                card.clicked.connect(self.claim_clicked.emit)
                self._claims_content.addWidget(card)
        elif self._case and self._case.claim_ids:
            loading_lbl = QLabel(tr("page.case_entity.loading_claims"))
            loading_lbl.setFont(create_font(size=10))
            loading_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            loading_lbl.setAlignment(Qt.AlignCenter)
            self._claims_content.addWidget(loading_lbl)
        else:
            empty_lbl = QLabel(tr("page.case_entity.empty_claims"))
            empty_lbl.setFont(create_font(size=10))
            empty_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self._claims_content.addWidget(empty_lbl)

    def _populate_notes_section(self):
        self._clear_layout(self._notes_content)

        if not self._case or not self._case.notes:
            self._notes_card.setVisible(False)
            return

        self._notes_card.setVisible(True)
        self._add_section_header(
            self._notes_content, "blue",
            tr("page.case_entity.section_notes"),
        )

        notes_lbl = QLabel(self._case.notes)
        notes_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        notes_lbl.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none; "
            f"padding: 8px 0;"
        )
        notes_lbl.setWordWrap(True)
        self._notes_content.addWidget(notes_lbl)

    # -- Actions --

    def _on_toggle_editable(self):
        if not self._case:
            return
        new_value = not self._case.is_editable
        self.toggle_editable_requested.emit(self._case.id, new_value)

    def _on_revisit(self):
        if not self._case:
            return
        if not self._case.is_editable:
            Toast.show_toast(
                self,
                tr("page.case_entity.case_not_editable"),
                Toast.WARNING,
            )
            return
        property_unit_id = getattr(self._case, 'property_unit_id', None) or ''
        if not property_unit_id:
            Toast.show_toast(self, tr("page.case_entity.no_unit_linked"), Toast.WARNING)
            return
        self.revisit_requested.emit({
            'case_id': self._case.id,
            'property_unit_id': property_unit_id,
        })

    def update_after_editable_toggle(self, is_editable: bool):
        """Called by MainWindow after successful API call to update UI."""
        if self._case:
            self._case.is_editable = is_editable
            self._populate_header()

    def update_language(self, is_arabic=True):
        """Re-apply RTL direction and refresh all text for language change."""
        direction = get_layout_direction()
        self.setLayoutDirection(direction)
        self._scroll.setLayoutDirection(direction)
        scroll_widget = self._scroll.widget()
        if scroll_widget:
            scroll_widget.setLayoutDirection(direction)
        self._header.update_texts()
        if self._case:
            self._populate_all()
