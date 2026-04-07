# -*- coding: utf-8 -*-
"""
Claim Details Page — Light integrated header, glowing-border section cards,
grid layout, pulsing logo watermark background. Supports self-loading from claim_id.
"""

import math
import time

from utils.logger import get_logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit,
    QSpacerItem, QSizePolicy, QGridLayout,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QComboBox, QFileDialog,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QTimer,
    QPropertyAnimation, QEasingCurve, QRectF,
)
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QPen, QFont,
    QPainterPath, QCursor,
)

from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.logo import LogoWidget
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import (
    get_unit_type_display, get_unit_status_display,
    get_claim_type_display, get_source_display, get_claim_status_display,
)
from services.api_worker import ApiWorker

logger = get_logger(__name__)


def _get_case_status_label(status):
    _keys = {1: "page.claim_details.status_open", 2: "page.claim_details.status_closed"}
    key = _keys.get(status)
    return tr(key) if key else tr("page.claim_details.status_unknown")


def _get_gender_label(gender):
    _keys = {1: "page.claim_details.gender_male", 2: "page.claim_details.gender_female", 0: "page.claim_details.gender_unspecified"}
    key = _keys.get(gender)
    return tr(key) if key else str(gender) if gender else "-"


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
            glow_grad = QLinearGradient(0, 0, w, 0)
            glow_alpha = int(self._glow_opacity * 180)
            glow_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
            glow_grad.setColorAt(0.3, QColor(91, 168, 240, glow_alpha))
            glow_grad.setColorAt(0.5, QColor(120, 190, 255, min(255, int(glow_alpha * 1.3))))
            glow_grad.setColorAt(0.7, QColor(91, 168, 240, glow_alpha))
            glow_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
            painter.setBrush(glow_grad)
            painter.drawRect(0, 0, w, h)

        painter.end()


# ---------------------------------------------------------------------------
#  _DetailsHeader — Light integrated header with back, claim info, edit button
# ---------------------------------------------------------------------------

class _DetailsHeader(QWidget):
    """Light header with claim identification and action buttons."""

    back_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._claim_number = ""
        self._badges_data = []
        self._editing = False
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Row 1: Back button + Claim number
        row1 = QHBoxLayout()
        row1.setSpacing(12)

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
            QPushButton:pressed {
                background: #DBEAFE;
                border: 1.5px solid rgba(56, 144, 223, 0.5);
            }
        """)
        back_pixmap = Icon.load_pixmap("arrow_back", 16)
        if back_pixmap and not back_pixmap.isNull():
            from PyQt5.QtGui import QIcon
            self._back_btn.setIcon(QIcon(back_pixmap))
        else:
            self._back_btn.setText("\u2190")
        self._back_btn.clicked.connect(self.back_clicked.emit)
        row1.addWidget(self._back_btn)

        self._num_label = QLabel("")
        self._num_label.setFont(create_font(size=15, weight=QFont.Bold))
        self._num_label.setStyleSheet(
            "color: #2A6CB5; background: transparent;"
        )
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

        # Cancel button (hidden by default)
        self._cancel_btn = QPushButton(tr("page.claim_details.cancel"))
        self._cancel_btn.setFixedSize(ScreenScale.w(90), ScreenScale.h(36))
        self._cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(56, 144, 223, 0.2);
                border-radius: 10px;
                color: #64748B; padding: 0 14px;
            }
            QPushButton:hover {
                background: #FFF1F2;
                border: 1.5px solid rgba(239, 68, 68, 0.3);
                color: #DC2626;
            }
            QPushButton:pressed {
                background: #FEE2E2;
            }
        """)
        self._cancel_btn.clicked.connect(self.cancel_clicked.emit)
        row1.addWidget(self._cancel_btn)

        # Edit/Save button
        self._edit_btn = QPushButton(tr("page.claim_details.edit_claim"))
        self._edit_btn.setFixedSize(ScreenScale.w(160), ScreenScale.h(38))
        self._edit_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._edit_btn.setVisible(False)
        self._edit_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
        self._edit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3890DF, stop:1 #5BA8F0
                );
                color: white;
                border: none;
                border-radius: 12px;
                padding: 0 24px;
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
        """)
        self._edit_btn.clicked.connect(self.edit_clicked.emit)
        row1.addWidget(self._edit_btn)

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

    def set_claim_info(self, claim_number, badges):
        """Update header with claim identification."""
        self._claim_number = claim_number
        self._num_label.setText(claim_number)

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

    def set_edit_visible(self, visible):
        self._edit_btn.setVisible(visible)

    def set_editing(self, editing):
        self._editing = editing
        self._cancel_btn.setVisible(editing)
        if editing:
            self._edit_btn.setText(tr("page.claim_details.save_changes"))
        else:
            self._edit_btn.setText(tr("page.claim_details.edit_claim"))

    def set_edit_text(self, text):
        self._edit_btn.setText(text)

    def update_texts(self):
        self._cancel_btn.setText(tr("page.claim_details.cancel"))
        self._num_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
            if get_layout_direction() == Qt.RightToLeft
            else Qt.AlignLeft | Qt.AlignVCenter
        )


# ---------------------------------------------------------------------------
#  _GlowingCard — Card with animated orbiting blue border light
# ---------------------------------------------------------------------------

class _GlowingCard(QFrame):
    """Card base with animated glowing border effect."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow_phase = 0.0
        self._glow_enabled = True

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 25))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(
            f"_GlowingCard {{ background-color: {Colors.SURFACE}; border: none; border-radius: 12px; }}"
        )

        # Animation: phase loops 0 → 1
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

        # White background
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)
        painter.fillPath(bg_path, QColor(Colors.SURFACE))

        if self._glow_enabled:
            # Traveling light border
            perimeter = 2 * (w + h)
            light_pos = self._glow_phase * perimeter
            light_spread = perimeter * 0.15

            border_path = QPainterPath()
            border_path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

            # Base border (subtle)
            painter.setPen(QPen(QColor(56, 144, 223, 25), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(border_path)

            # Bright traveling segment
            for offset in range(-3, 4):
                pos = light_pos + offset * (light_spread / 6)
                pos = pos % perimeter
                alpha = int(60 * (1 - abs(offset) / 3.5))

                # Map position to x,y on perimeter
                px, py = self._pos_on_rect(pos, w, h)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(56, 144, 223, alpha))
                painter.drawEllipse(int(px) - 3, int(py) - 3, 6, 6)

        painter.end()

    def _pos_on_rect(self, pos, w, h):
        """Map a linear position along rectangle perimeter to x,y."""
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
        # Center logo
        lw = self._logo.width() if self._logo.pixmap() else 120
        lh = self._logo.height() if self._logo.pixmap() else 120
        self._logo.move(
            (self.width() - lw) // 2,
            (self.height() - lh) // 2,
        )
        self._logo.raise_()


# ---------------------------------------------------------------------------
#  ClaimDetailsPage — Main page
# ---------------------------------------------------------------------------

class ClaimDetailsPage(QWidget):
    """Claim details page with navy header, glowing cards, grid layout."""

    back_requested = pyqtSignal()
    edit_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._claim_data = {}
        self._person_data = {}
        self._unit_data = {}
        self._building_data = {}
        self._survey_id = None
        self._evidences = []
        self._claim_id = None
        self._is_editing = False
        self._original_claim_type = None
        self._relation_id = None
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._claim_type_combo = None
        self._ownership_share_input = None
        self._original_ownership_share = None
        self._loading = False
        self._edit_btn_widget = None
        self._dimmed_cards = []

        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _is_claim_open(self):
        """Check if current claim has open status using consistent fallback logic."""
        status = self._claim_data.get("caseStatus") or self._claim_data.get("status") or 1
        return status in (1, "1")

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

        # Navy header
        self._header = _DetailsHeader()
        self._header.back_clicked.connect(self.back_requested.emit)
        self._header.edit_clicked.connect(self._on_edit_or_save_clicked)
        self._header.cancel_clicked.connect(self._on_cancel_edit)
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
        self._scroll_content = scroll_content
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 40)
        self._scroll_layout.setSpacing(16)

        # Section 1: Main info card (claimant — full width)
        self._person_card = _GlowingCard()
        self._person_layout = QVBoxLayout(self._person_card)
        self._person_layout.setContentsMargins(20, 20, 20, 20)
        self._person_layout.setSpacing(12)
        self._person_content = QVBoxLayout()
        self._person_content.setSpacing(12)
        self._person_layout.addLayout(self._person_content)
        self._scroll_layout.addWidget(self._person_card)

        # Middle row: 2 cards side by side (property | relation+evidence)
        middle_row = QHBoxLayout()
        middle_row.setSpacing(16)

        # Property card
        self._property_card = _GlowingCard()
        self._property_card_layout = QVBoxLayout(self._property_card)
        self._property_card_layout.setContentsMargins(20, 20, 20, 20)
        self._property_card_layout.setSpacing(12)
        self._property_content = QVBoxLayout()
        self._property_content.setSpacing(12)
        self._property_card_layout.addLayout(self._property_content)
        middle_row.addWidget(self._property_card, 1)

        # Relation + Evidence card
        self._relation_card = _GlowingCard()
        self._relation_card_layout = QVBoxLayout(self._relation_card)
        self._relation_card_layout.setContentsMargins(20, 20, 20, 20)
        self._relation_card_layout.setSpacing(12)
        self._relation_content = QVBoxLayout()
        self._relation_content.setSpacing(12)
        self._relation_card_layout.addLayout(self._relation_content)
        middle_row.addWidget(self._relation_card, 1)

        self._scroll_layout.addLayout(middle_row)

        # Status summary card (full width)
        self._status_card = _GlowingCard()
        self._status_card.set_glow_enabled(False)
        self._status_card_layout = QVBoxLayout(self._status_card)
        self._status_card_layout.setContentsMargins(20, 16, 20, 16)
        self._status_card_layout.setSpacing(12)
        self._status_content = QVBoxLayout()
        self._status_content.setSpacing(12)
        self._status_card_layout.addLayout(self._status_content)
        self._scroll_layout.addWidget(self._status_card)

        self._scroll_layout.addStretch()
        self._scroll.setWidget(scroll_content)
        main_layout.addWidget(self._scroll, 1)

    # -- Card section headers --

    def _add_section_header(self, layout, icon_name, title, subtitle):
        """Add a styled section header to a card layout."""
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
        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        sub_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        title_box.addWidget(title_lbl)
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

    # -- Data loading --

    def refresh(self, data=None):
        """Load claim data. Accepts full data dict or {claim_id: ...}."""
        if self._is_editing:
            self._is_editing = False
            self._pending_uploads = []
            self._pending_deletes = []
            self._pending_links = []
            self._claim_type_combo = None
            self._ownership_share_input = None
            self._header.set_editing(False)

        if data is None:
            return

        # Case 1: Full data dict (from controller)
        if data.get("claim"):
            self._apply_data(data)
            return

        # Case 2: claim_id only — load from API
        claim_id = data.get("claim_id")
        if claim_id:
            self._load_claim_by_id(claim_id)
            return

        logger.warning("refresh() called with no usable data")

    def _apply_data(self, data):
        """Apply pre-loaded data dict to the page."""
        try:
            self._claim_data = data.get("claim") or {}
            self._person_data = data.get("person") or {}
            self._unit_data = data.get("unit") or {}
            self._building_data = data.get("building") or {}
            self._survey_id = data.get("survey_id")
            self._evidences = data.get("evidences") or []
            self._claim_id = self._claim_data.get("id") or self._claim_data.get("claimId", "")

            self._populate_header()
            self._populate_person_card()
            self._populate_property_card()
            self._populate_relation_card()
            self._populate_status_card()
            self._update_edit_visibility()

            logger.info(f"Claim details loaded: {self._claim_data.get('claimNumber', 'N/A')}")
        except Exception as e:
            logger.error(f"Error applying claim data: {e}")

    def _load_claim_by_id(self, claim_id):
        """Load full claim data from API by claim_id."""
        if self._loading:
            return
        self._loading = True
        self._claim_id = claim_id
        self._spinner.show_loading(tr("page.claims.loading"))

        def _fetch(cid):
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController()
            result = ctrl.get_claim_full_detail(cid)
            if result and result.success:
                return result.data
            return None

        self._load_worker = ApiWorker(_fetch, claim_id)
        self._load_worker.finished.connect(self._on_claim_loaded)
        self._load_worker.error.connect(self._on_claim_load_error)
        self._load_worker.start()

    def _on_claim_loaded(self, data):
        self._loading = False
        self._spinner.hide_loading()
        if data:
            self._apply_data(data)
        else:
            Toast.show_toast(self, tr("page.claims.load_error"), Toast.ERROR)
            logger.warning("Failed to load claim data — empty result")

    def _on_claim_load_error(self, error_msg):
        self._loading = False
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.claims.load_error"), Toast.ERROR)
        logger.warning(f"Failed to load claim data: {error_msg}")

    # -- Populate sections --

    def _populate_header(self):
        """Update the navy header with claim info and badges."""
        try:
            claim = self._claim_data
            claim_number = str(claim.get("claimNumber") or "N/A")
            claim_type = get_claim_type_display(claim.get("claimType") or "")
            case_status = claim.get("caseStatus") or claim.get("status") or 1
            status_label = _get_case_status_label(case_status)
            source = get_source_display(claim.get("claimSource") or 0)

            badges = []
            badges.append((claim_type, "#EFF6FF", "#1E40AF"))
            if case_status == 2:
                badges.append((status_label, "#F0FDF4", "#15803D"))
            else:
                badges.append((status_label, "#FFF7ED", "#C2410C"))
            badges.append((source, "#F5F3FF", "#6D28D9"))

            date_str = (str(claim.get("createdAtUtc") or ""))[:10]
            if date_str and not date_str.startswith("0001"):
                badges.append((date_str, "#F8FAFC", "#64748B"))

            self._header.set_claim_info(claim_number, badges)
        except Exception as e:
            logger.error(f"Error populating header: {e}")

    def _populate_person_card(self):
        try:
            self._clear_layout(self._person_content)

            self._add_section_header(
                self._person_content, "blue",
                tr("page.claim_details.claimant_data"),
                tr("page.claim_details.claimant_data_subtitle")
            )

            person = self._person_data
            if not person:
                name = self._claim_data.get("primaryClaimantName") or self._claim_data.get("fullNameArabic", "-")
                no_lbl = QLabel(tr("page.claim_details.claimant_name", name=name))
                no_lbl.setFont(create_font(size=FontManager.SIZE_BODY))
                no_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
                self._person_content.addWidget(no_lbl)
                return

            # Grid of fields
            grid = QGridLayout()
            grid.setSpacing(16)
            grid.setContentsMargins(0, 0, 0, 0)
            for c in range(4):
                grid.setColumnStretch(c, 1)

            gender_raw = person.get("gender", 0)
            gender_label = _get_gender_label(gender_raw)
            dob = person.get("dateOfBirth")
            dob_display = str(dob)[:10] if dob and not str(dob).startswith("0001") else "-"

            fields = [
                (tr("page.claim_details.first_name"), person.get("firstNameArabic") or "-"),
                (tr("page.claim_details.father_name"), person.get("fatherNameArabic") or "-"),
                (tr("page.claim_details.family_name"), person.get("familyNameArabic") or "-"),
                (tr("page.claim_details.mother_name"), person.get("motherNameArabic") or "-"),
                (tr("page.claim_details.national_id"), str(person.get("nationalId") or "-")),
                (tr("page.claim_details.gender"), gender_label),
                (tr("page.claim_details.date_of_birth"), dob_display),
            ]

            for i, (label, value) in enumerate(fields):
                row = i // 4
                col = i % 4
                grid.addWidget(self._create_field_pair(label, value), row, col)

            grid_widget = QWidget()
            grid_widget.setStyleSheet("background: transparent; border: none;")
            grid_widget.setLayout(grid)
            self._person_content.addWidget(grid_widget)
        except Exception as e:
            logger.error(f"Error populating person card: {e}")

    def _populate_property_card(self):
        try:
            self._clear_layout(self._property_content)

            self._add_section_header(
                self._property_content, "blue",
                tr("page.claim_details.property_unit"),
                tr("page.claim_details.property_unit_subtitle")
            )

            building = self._building_data
            unit = self._unit_data

            if not building and not unit:
                building_code = str(self._claim_data.get("buildingCode") or "-")
                no_lbl = QLabel(tr("page.claim_details.building_number_label", code=building_code))
                no_lbl.setFont(create_font(size=FontManager.SIZE_BODY))
                no_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
                self._property_content.addWidget(no_lbl)
                return

            # Address bar — try camelCase (raw API) then snake_case (mapped)
            gov = building.get("governorateNameArabic") or building.get("governorate_name_ar") or ""
            dist = building.get("districtNameArabic") or building.get("district_name_ar") or ""
            sub = building.get("subDistrictNameArabic") or building.get("subdistrict_name_ar") or ""
            neigh = building.get("neighborhoodNameArabic") or building.get("neighborhood_name_ar") or ""
            address_parts = [p for p in [gov, dist, sub, neigh] if p]
            address = " > ".join(address_parts) if address_parts else "-"

            addr_bar = QFrame()
            addr_bar.setLayoutDirection(get_layout_direction())
            addr_bar.setMinimumHeight(ScreenScale.h(28))
            addr_bar.setStyleSheet("QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }")
            addr_layout = QHBoxLayout(addr_bar)
            addr_layout.setContentsMargins(12, 6, 12, 6)
            addr_lbl = QLabel(address)
            addr_lbl.setWordWrap(True)
            addr_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
            addr_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            addr_layout.addWidget(addr_lbl)
            addr_layout.addStretch()
            self._property_content.addWidget(addr_bar)

            # Fields grid
            building_code = str(building.get("buildingCode") or building.get("buildingNumber") or "-")
            unit_number = str(unit.get("unitIdentifier") or unit.get("unitNumber") or "-")
            floor_raw = unit.get("floorNumber")
            floor = str(floor_raw) if floor_raw is not None else "-"
            unit_type_raw = unit.get("unitType", 0)
            unit_type = get_unit_type_display(unit_type_raw) if unit_type_raw else "-"
            area = unit.get("areaSquareMeters") or unit.get("areaSqm", 0)
            area_display = tr("page.claim_details.area_sqm", area=f"{area:.2f}") if area else "-"
            rooms_raw = unit.get("numberOfRooms")
            rooms = str(rooms_raw) if rooms_raw is not None else "-"
            unit_status_raw = unit.get("status") or unit.get("unitStatus", 0)
            unit_status = get_unit_status_display(unit_status_raw) if unit_status_raw else "-"

            grid = QGridLayout()
            grid.setSpacing(16)
            grid.setContentsMargins(0, 4, 0, 0)
            for c in range(3):
                grid.setColumnStretch(c, 1)

            props = [
                (tr("page.claim_details.building_number"), building_code),
                (tr("page.claim_details.unit_number"), unit_number),
                (tr("page.claim_details.floor_number"), floor),
                (tr("page.claim_details.unit_type"), unit_type),
                (tr("page.claim_details.area"), area_display),
                (tr("page.claim_details.rooms_count"), rooms),
                (tr("page.claim_details.unit_status"), unit_status),
            ]

            for i, (label, value) in enumerate(props):
                row = i // 3
                col = i % 3
                grid.addWidget(self._create_field_pair(label, value), row, col)

            grid_widget = QWidget()
            grid_widget.setStyleSheet("background: transparent; border: none;")
            grid_widget.setLayout(grid)
            self._property_content.addWidget(grid_widget)
        except Exception as e:
            logger.error(f"Error populating property card: {e}")

    def _populate_relation_card(self):
        try:
            # Preserve ownership share input value across rebuilds
            _saved_share_text = None
            if self._is_editing and self._ownership_share_input:
                _saved_share_text = self._ownership_share_input.text()

            self._clear_layout(self._relation_content)

            self._add_section_header(
                self._relation_content, "blue",
                tr("page.claim_details.claim_type_docs"),
                tr("page.claim_details.claim_type_docs_subtitle")
            )

            claim = self._claim_data
            current_type = claim.get("claimType", "")
            is_claim_open = self._is_claim_open()

            # Claim type row
            type_row = QHBoxLayout()
            type_row.setContentsMargins(0, 0, 0, 0)
            type_row.setSpacing(8)

            type_label = QLabel(tr("page.claim_details.claim_type_label"))
            type_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            type_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            type_row.addWidget(type_label)

            if self._is_editing:
                self._claim_type_combo = QComboBox()
                self._claim_type_combo.setFixedHeight(ScreenScale.h(36))
                self._claim_type_combo.setMinimumWidth(ScreenScale.w(160))
                self._claim_type_combo.setStyleSheet(StyleManager.combo_box())
                _CLAIM_TYPE_OPTIONS = [
                    (1, get_claim_type_display(1)),
                    (2, get_claim_type_display(2)),
                    (3, get_claim_type_display(3)),
                ]
                for code, label in _CLAIM_TYPE_OPTIONS:
                    self._claim_type_combo.addItem(label, code)
                idx = self._claim_type_combo.findData(current_type)
                if idx < 0 and isinstance(current_type, str):
                    try:
                        idx = self._claim_type_combo.findData(int(current_type))
                    except (ValueError, TypeError):
                        pass
                if idx < 0 and isinstance(current_type, int):
                    idx = self._claim_type_combo.findData(str(current_type))
                if idx >= 0:
                    self._claim_type_combo.setCurrentIndex(idx)
                if not is_claim_open:
                    self._claim_type_combo.setEnabled(False)
                self._claim_type_combo.currentIndexChanged.connect(self._on_claim_type_changed_in_edit)
                type_row.addWidget(self._claim_type_combo)
            else:
                type_value = QLabel(get_claim_type_display(current_type))
                type_value.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
                type_value.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
                type_row.addWidget(type_value)

            type_row.addStretch()
            type_widget = QWidget()
            type_widget.setStyleSheet("background: transparent; border: none;")
            type_widget.setLayout(type_row)
            self._relation_content.addWidget(type_widget)

            # Ownership share row — only for ownership claim type
            is_ownership_type = (current_type in (1, "1", "ownership"))
            self._ownership_share_input = None

            if is_ownership_type:
                share_row = QHBoxLayout()
                share_row.setContentsMargins(0, 0, 0, 0)
                share_row.setSpacing(8)

                share_label = QLabel(tr("page.claim_details.ownership_share_label"))
                share_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
                share_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
                share_row.addWidget(share_label)

                raw_share = claim.get("ownershipShare")

                if self._is_editing:
                    from PyQt5.QtGui import QIntValidator
                    self._ownership_share_input = QLineEdit()
                    self._ownership_share_input.setFixedHeight(ScreenScale.h(36))
                    self._ownership_share_input.setMinimumWidth(ScreenScale.w(160))
                    self._ownership_share_input.setPlaceholderText("0 - 2400")
                    self._ownership_share_input.setValidator(QIntValidator(0, 2400, self._ownership_share_input))
                    self._ownership_share_input.setFocusPolicy(Qt.StrongFocus)
                    self._ownership_share_input.setStyleSheet("""
                        QLineEdit {
                            border: 1.5px solid #D0D7E2;
                            border-radius: 8px;
                            padding: 6px 12px;
                            background-color: #FFFFFF;
                            color: #2C3E50;
                            font-size: 13px;
                        }
                        QLineEdit:hover { border-color: #93C5FD; }
                        QLineEdit:focus { border-color: #3890DF; }
                    """)
                    if _saved_share_text is not None:
                        self._ownership_share_input.setText(_saved_share_text)
                    elif raw_share is not None:
                        try:
                            self._ownership_share_input.setText(str(round(float(raw_share) * 2400)))
                        except (ValueError, TypeError):
                            pass
                    self._ownership_share_input.setEnabled(True)
                    share_row.addWidget(self._ownership_share_input)
                else:
                    if raw_share is not None and raw_share > 0:
                        shares = round(float(raw_share) * 2400)
                        display = f"{shares} {tr('unit.shares')}"
                    else:
                        display = "-"
                    share_value = QLabel(display)
                    share_value.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
                    share_value.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
                    share_row.addWidget(share_value)

                share_row.addStretch()
                share_widget = QWidget()
                share_widget.setStyleSheet("background: transparent; border: none;")
                share_widget.setLayout(share_row)
                self._relation_content.addWidget(share_widget)

            # Divider
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setFixedHeight(1)
            divider.setStyleSheet("background-color: #E2E8F0; border: none;")
            self._relation_content.addWidget(divider)

            # Evidence header
            ev_header = QHBoxLayout()
            ev_header.setContentsMargins(0, 0, 0, 0)
            ev_title = QLabel(tr("page.claim_details.attached_documents"))
            ev_title.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            ev_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            ev_header.addWidget(ev_title)
            ev_header.addStretch()

            if self._is_editing:
                upload_btn = QPushButton(tr("page.claim_details.upload_document"))
                upload_btn.setFixedHeight(ScreenScale.h(32))
                upload_btn.setCursor(Qt.PointingHandCursor)
                upload_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Colors.PRIMARY_BLUE}; color: white;
                        border: none; border-radius: 6px; padding: 0 16px;
                        font-size: 12px; font-weight: 600;
                    }}
                    QPushButton:hover {{ background-color: #2A7BC8; }}
                """)
                upload_btn.clicked.connect(self._on_upload_evidence)
                ev_header.addWidget(upload_btn)

            ev_header_widget = QWidget()
            ev_header_widget.setStyleSheet("background: transparent; border: none;")
            ev_header_widget.setLayout(ev_header)
            self._relation_content.addWidget(ev_header_widget)

            # Evidence thumbnails
            active_evidences = [ev for ev in self._evidences
                               if str(ev.get("id") or ev.get("evidenceId") or "") not in self._pending_deletes]

            if active_evidences or self._pending_uploads or self._pending_links:
                thumbs_container = QWidget()
                thumbs_container.setStyleSheet("background: transparent; border: none;")
                thumbs_layout = QHBoxLayout(thumbs_container)
                thumbs_layout.setContentsMargins(0, 0, 0, 0)
                thumbs_layout.setSpacing(10)

                for ev in active_evidences:
                    card = self._create_evidence_thumbnail(ev)
                    thumbs_layout.addWidget(card)

                for fp in self._pending_uploads:
                    card = self._create_pending_upload_card(fp)
                    thumbs_layout.addWidget(card)

                for ev_data in self._pending_links:
                    card = self._create_pending_link_card(ev_data)
                    thumbs_layout.addWidget(card)

                thumbs_layout.addStretch()
                self._relation_content.addWidget(thumbs_container)
            else:
                no_ev = QLabel(tr("page.claim_details.no_documents"))
                no_ev.setFont(create_font(size=FontManager.SIZE_BODY))
                no_ev.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
                no_ev.setAlignment(Qt.AlignCenter)
                self._relation_content.addWidget(no_ev)
        except Exception as e:
            logger.error(f"Error populating relation card: {e}")

    def _populate_status_card(self):
        try:
            self._clear_layout(self._status_content)

            claim = self._claim_data
            case_status = claim.get("caseStatus") or claim.get("status", 1)
            status_label = _get_case_status_label(case_status)
            has_conflict = claim.get("hasConflict") or claim.get("hasConflicts", False)
            evidence_count = claim.get("evidenceCount") or len(self._evidences)

            # Status banner
            if case_status == 2:
                banner_bg, banner_border, banner_color = "#F0FDF4", "#BBF7D0", "#15803D"
                banner_text = tr("page.claim_details.claim_closed")
            elif case_status == 1 and evidence_count == 0:
                banner_bg, banner_border, banner_color = "#FFFBEB", "#FDE68A", "#92400E"
                banner_text = tr("page.claim_details.awaiting_evidence")
            else:
                banner_bg, banner_border, banner_color = "#FFF7ED", "#FED7AA", "#C2410C"
                banner_text = tr("page.claim_details.claim_open")

            banner = QFrame()
            banner.setStyleSheet(
                f"QFrame {{ background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; }}"
            )
            banner_layout = QHBoxLayout(banner)
            banner_layout.setContentsMargins(16, 10, 16, 10)
            banner_lbl = QLabel(banner_text)
            banner_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
            banner_lbl.setStyleSheet(f"color: {banner_color}; background: transparent; border: none;")
            banner_layout.addWidget(banner_lbl)
            banner_layout.addStretch()
            self._status_content.addWidget(banner)

            # Stats grid
            stats_grid = QGridLayout()
            stats_grid.setSpacing(16)
            stats_grid.setContentsMargins(0, 4, 0, 0)
            for c in range(3):
                stats_grid.setColumnStretch(c, 1)

            stats_grid.addWidget(self._create_field_pair(tr("page.claim_details.status"), status_label), 0, 0)
            conflict_text = tr("page.claim_details.yes") if has_conflict else tr("page.claim_details.no_conflict")
            stats_grid.addWidget(self._create_field_pair(tr("page.claim_details.conflict"), conflict_text), 0, 1)
            stats_grid.addWidget(self._create_field_pair(tr("page.claim_details.documents_count"), str(evidence_count)), 0, 2)

            stats_widget = QWidget()
            stats_widget.setStyleSheet("background: transparent; border: none;")
            stats_widget.setLayout(stats_grid)
            self._status_content.addWidget(stats_widget)
        except Exception as e:
            logger.error(f"Error populating status card: {e}")

    # -- Evidence helpers --

    def _create_evidence_thumbnail(self, evidence):
        from PyQt5.QtGui import QPixmap

        ev_id = str(evidence.get("id") or evidence.get("evidenceId") or "")
        file_name = str(evidence.get("fileName") or evidence.get("originalFileName") or tr("page.claim_details.document"))

        card = QFrame()
        card.setFixedSize(ScreenScale.w(80), ScreenScale.h(105))
        card.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #E1E8ED; border-radius: 6px; }
            QFrame:hover { border-color: #3890DF; }
        """)
        card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb = QLabel()
        thumb.setFixedSize(ScreenScale.w(70), ScreenScale.h(70))
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")

        local_path = self._download_evidence_file(ev_id, file_name)
        if local_path:
            px = QPixmap(local_path)
            if not px.isNull():
                thumb.setPixmap(px.scaled(66, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._set_file_type_icon(thumb, file_name)
        else:
            self._set_file_type_icon(thumb, file_name)

        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_short = file_name[:12] + "..." if len(file_name) > 12 else file_name
        name_lbl = QLabel(name_short)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        if self._is_editing and ev_id and self._is_claim_open():
            del_btn = QPushButton("\u2715", card)
            del_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
            del_btn.move(60, 2)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton { background-color: #E53E3E; color: white; border: none; border-radius: 9px; font-size: 10px; font-weight: bold; }
                QPushButton:hover { background-color: #C53030; }
            """)
            del_btn.clicked.connect(lambda _, eid=ev_id: self._on_delete_evidence(eid))
        elif local_path:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            def _open_file(event, fp=local_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(fp))
            card.mousePressEvent = _open_file
        else:
            def _on_click_unavailable(event, page=self):
                Toast.show_toast(page, tr("page.claim_details.cannot_download"), Toast.WARNING)
            card.mousePressEvent = _on_click_unavailable

        return card

    def _create_pending_upload_card(self, file_path):
        import os
        from PyQt5.QtGui import QPixmap
        file_name = os.path.basename(file_path)

        card = QFrame()
        card.setFixedSize(ScreenScale.w(80), ScreenScale.h(105))
        card.setStyleSheet("""
            QFrame { background-color: #ffffff; border: 1px solid #68D391; border-radius: 6px; }
            QFrame:hover { border-color: #38A169; }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb = QLabel()
        thumb.setFixedSize(ScreenScale.w(70), ScreenScale.h(70))
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")

        px = QPixmap(file_path)
        if not px.isNull():
            thumb.setPixmap(px.scaled(66, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self._set_file_type_icon(thumb, file_name)

        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_short = file_name[:12] + "..." if len(file_name) > 12 else file_name
        name_lbl = QLabel(name_short)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet("color: #38A169; border: none; background: transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        del_btn = QPushButton("\u2715", card)
        del_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
        del_btn.move(60, 2)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton { background-color: #E53E3E; color: white; border: none; border-radius: 9px; font-size: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #C53030; }
        """)
        del_btn.clicked.connect(lambda _, fp=file_path: self._on_remove_pending_upload(fp))

        return card

    def _create_pending_link_card(self, ev_data):
        file_name = str(ev_data.get("originalFileName") or ev_data.get("fileName") or tr("page.claim_details.document"))
        ev_id = str(ev_data.get("id") or ev_data.get("evidenceId") or "")

        card = QFrame()
        card.setFixedSize(ScreenScale.w(80), ScreenScale.h(105))
        card.setStyleSheet(f"""
            QFrame {{ background-color: #ffffff; border: 1.5px solid {Colors.PRIMARY_BLUE}; border-radius: 6px; }}
            QFrame:hover {{ border-color: #2A7BC8; }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb = QLabel()
        thumb.setFixedSize(ScreenScale.w(70), ScreenScale.h(70))
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")
        self._set_file_type_icon(thumb, file_name)
        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_short = file_name[:12] + "..." if len(file_name) > 12 else file_name
        name_lbl = QLabel(name_short)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; border: none; background: transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        del_btn = QPushButton("\u2715", card)
        del_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
        del_btn.move(60, 2)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton { background-color: #E53E3E; color: white; border: none; border-radius: 9px; font-size: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #C53030; }
        """)
        del_btn.clicked.connect(lambda _, eid=ev_id: self._on_remove_pending_link(eid))

        return card

    def _set_file_type_icon(self, label, file_name):
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext == "pdf":
            icon_text, bg_color = "PDF", "#E53E3E"
        elif ext in ("jpg", "jpeg", "png", "bmp", "gif", "webp"):
            icon_text, bg_color = "IMG", "#3182CE"
        else:
            icon_text, bg_color = "DOC", "#718096"
        label.setText(icon_text)
        label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        label.setStyleSheet(
            f"color: white; background-color: {bg_color}; border-radius: 8px; border: none;"
        )

    def _download_evidence_file(self, evidence_id, file_name):
        try:
            from services.api_client import get_api_client
            get_api_client()._ensure_valid_token()
            from utils.helpers import download_evidence_file
            return download_evidence_file(evidence_id, file_name)
        except Exception as e:
            logger.debug(f"Evidence download failed: {e}")
            return None

    # -- Edit mode --

    def _animate_relation_card_edit(self, entering):
        """Elevate the relation card above siblings when editing."""
        card = self._relation_card

        if entering:
            # Dim other cards
            for sibling in (self._person_card, self._property_card, self._status_card):
                dim = QGraphicsOpacityEffect(sibling)
                dim.setOpacity(0.35)
                sibling.setGraphicsEffect(dim)
                self._dimmed_cards.append(sibling)

            # Elevate relation card — remove QGraphicsEffect so QComboBox popup works
            card.raise_()
            card.set_glow_enabled(False)
            card.setGraphicsEffect(None)
            card.setStyleSheet(
                "_GlowingCard { background-color: %s; "
                "border: 2px solid rgba(56, 144, 223, 0.35); border-radius: 12px; }" % Colors.SURFACE
            )

            # Add save/cancel buttons at bottom of card
            btn_container = QWidget()
            btn_container.setStyleSheet("background: transparent; border: none;")
            btn_row = QHBoxLayout(btn_container)
            btn_row.setContentsMargins(0, 8, 0, 0)
            btn_row.setSpacing(10)
            btn_row.addStretch()

            cancel_btn = QPushButton(tr("page.claim_details.cancel"))
            cancel_btn.setFixedSize(ScreenScale.w(100), ScreenScale.h(36))
            cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
            cancel_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 #FFFFFF, stop:1 #F0F4FA
                    );
                    border: 1.5px solid rgba(56, 144, 223, 0.2);
                    border-radius: 10px; color: #64748B;
                }
                QPushButton:hover {
                    background: #FFF1F2;
                    border: 1.5px solid rgba(239, 68, 68, 0.3);
                    color: #DC2626;
                }
            """)
            cancel_btn.clicked.connect(self._on_cancel_edit)
            btn_row.addWidget(cancel_btn)

            save_btn = QPushButton(tr("page.claim_details.save_changes"))
            save_btn.setFixedSize(ScreenScale.w(150), ScreenScale.h(36))
            save_btn.setCursor(QCursor(Qt.PointingHandCursor))
            save_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
            save_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 #3890DF, stop:1 #5BA8F0
                    );
                    color: white; border: none; border-radius: 10px;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 #2A7BC9, stop:1 #4A98E0
                    );
                }
            """)
            save_btn.clicked.connect(self._on_edit_or_save_clicked)
            btn_row.addWidget(save_btn)

            self._relation_card_layout.addWidget(btn_container)
            self._edit_btn_widget = btn_container

            # Scroll to bring the relation card into view
            QTimer.singleShot(100, lambda: self._scroll.ensureWidgetVisible(
                self._relation_card, 20, 40
            ))

        else:
            # Restore dimmed cards
            for sibling in self._dimmed_cards:
                shadow = QGraphicsDropShadowEffect(sibling)
                shadow.setBlurRadius(20)
                shadow.setOffset(0, 4)
                shadow.setColor(QColor(0, 0, 0, 25))
                sibling.setGraphicsEffect(shadow)
            self._dimmed_cards.clear()

            # Restore relation card shadow and glow
            card.setStyleSheet(
                "_GlowingCard { background-color: %s; border: none; border-radius: 12px; }" % Colors.SURFACE
            )
            shadow = QGraphicsDropShadowEffect(card)
            shadow.setBlurRadius(20)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 25))
            card.setGraphicsEffect(shadow)
            card.set_glow_enabled(True)

            # Remove edit buttons
            if self._edit_btn_widget:
                self._relation_card_layout.removeWidget(self._edit_btn_widget)
                self._edit_btn_widget.deleteLater()
                self._edit_btn_widget = None

    def _on_edit_or_save_clicked(self):
        if self._is_editing:
            self._on_save_edit()
            return
        if not self._claim_id:
            return
        self._is_editing = True
        self._original_claim_type = self._claim_data.get("claimType")
        raw_share = self._claim_data.get("ownershipShare")
        try:
            self._original_ownership_share = round(float(raw_share) * 2400) if raw_share is not None else None
        except (ValueError, TypeError):
            self._original_ownership_share = None
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._extract_relation_id()

        self._header.set_editing(True)
        self._header.set_edit_visible(False)
        self._animate_relation_card_edit(True)
        self._populate_relation_card()

    def _update_edit_visibility(self):
        main_window = self.window()
        can_edit = False
        if hasattr(main_window, 'current_user') and main_window.current_user:
            role = getattr(main_window.current_user, 'role', '')
            can_edit = role in ("admin", "data_manager")
        is_open = self._is_claim_open()
        if can_edit and not is_open:
            self._header.set_edit_text(tr("page.claim_details.edit_share_docs"))
        else:
            self._header.set_edit_text(tr("page.claim_details.edit_claim"))
        self._header.set_edit_visible(can_edit)
        self._header.set_editing(False)

    def _on_claim_type_changed_in_edit(self):
        if self._claim_type_combo:
            self._claim_data["claimType"] = self._claim_type_combo.currentData()
            self._populate_relation_card()

    def _extract_relation_id(self):
        rel_id = self._claim_data.get("sourceRelationId")
        if rel_id:
            self._relation_id = rel_id
            return
        for ev in self._evidences:
            for rel in (ev.get("evidenceRelations") or []):
                rel_id = rel.get("personPropertyRelationId")
                if rel_id:
                    self._relation_id = rel_id
                    return

    def _on_cancel_edit(self):
        self._is_editing = False
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._claim_type_combo = None
        self._ownership_share_input = None

        self._animate_relation_card_edit(False)
        self._header.set_editing(False)
        self._update_edit_visibility()
        self._populate_relation_card()

    def _on_upload_evidence(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("page.claim_details.select_documents"), "",
            "Images & PDF (*.png *.jpg *.jpeg *.pdf)")
        if not file_paths:
            return
        self._pending_uploads.extend(file_paths)
        self._populate_relation_card()

    def _on_delete_evidence(self, evidence_id):
        if evidence_id not in self._pending_deletes:
            self._pending_deletes.append(evidence_id)
        self._populate_relation_card()

    def _on_remove_pending_upload(self, file_path):
        if file_path in self._pending_uploads:
            self._pending_uploads.remove(file_path)
        self._populate_relation_card()

    def _on_pick_existing_evidence(self):
        if not self._survey_id:
            Toast.show_toast(self, tr("page.claim_details.survey_id_missing"), Toast.WARNING)
            return

        def _fetch_survey_evidences(survey_id):
            from services.api_client import get_api_client
            api = get_api_client()
            return api.get_survey_evidences(survey_id)

        self._pick_evidence_worker = ApiWorker(_fetch_survey_evidences, self._survey_id)
        self._pick_evidence_worker.finished.connect(self._on_pick_evidences_loaded)
        self._pick_evidence_worker.error.connect(self._on_pick_evidences_error)
        self._spinner.show_loading(tr("component.loading.default"))
        self._pick_evidence_worker.start()

    def _on_pick_evidences_loaded(self, all_evidences):
        self._spinner.hide_loading()

        linked_ids = {str(ev.get("id") or ev.get("evidenceId") or "") for ev in self._evidences}
        linked_ids -= set(self._pending_deletes)
        for ev_data in self._pending_links:
            linked_ids.add(str(ev_data.get("id") or ev_data.get("evidenceId") or ""))

        from ui.components.dialogs.evidence_picker_dialog import EvidencePickerDialog
        dialog = EvidencePickerDialog(all_evidences, linked_ids, parent=self)
        if dialog.exec_() == EvidencePickerDialog.Accepted:
            selected_data = dialog.get_selected_data()
            self._pending_links.extend(selected_data)
            self._populate_relation_card()

    def _on_pick_evidences_error(self, error_msg):
        self._spinner.hide_loading()
        logger.warning(f"Failed to load survey evidences: {error_msg}")
        Toast.show_toast(self, tr("page.claim_details.load_documents_failed"), Toast.ERROR)

    def _on_remove_pending_link(self, evidence_id):
        self._pending_links = [
            ev for ev in self._pending_links
            if str(ev.get("id") or ev.get("evidenceId") or "") != evidence_id
        ]
        self._populate_relation_card()

    # -- Save --

    def _on_save_edit(self):
        import os
        import hashlib
        from controllers.claim_controller import ClaimController

        ctrl = ClaimController()

        if not self._is_claim_open():
            self._pending_deletes = []

        new_type = self._claim_type_combo.currentData() if self._claim_type_combo else None
        type_changed = new_type is not None and new_type != self._original_claim_type

        new_share_text = self._ownership_share_input.text().strip() if self._ownership_share_input else ""
        try:
            new_share_val = int(new_share_text) if new_share_text else None
        except (ValueError, TypeError):
            Toast.show_toast(self, tr("page.claim_details.ownership_share_required"), Toast.WARNING)
            return
        share_changed = new_share_val != self._original_ownership_share

        # Validate: ownership claim type requires ownership share
        final_type = new_type if type_changed else self._original_claim_type
        is_ownership = (final_type in (1, "1", "ownership"))
        final_share = new_share_val if (share_changed and new_share_val is not None) else self._original_ownership_share
        if is_ownership and final_share is None:
            Toast.show_toast(self, tr("page.claim_details.ownership_share_required"), Toast.WARNING)
            return

        has_changes = type_changed or share_changed or self._pending_uploads or self._pending_deletes or self._pending_links
        if not has_changes:
            Toast.show_toast(self, tr("page.claim_details.no_changes"), Toast.INFO)
            self._on_cancel_edit()
            return

        from ui.components.dialogs.modification_reason_dialog import ModificationReasonDialog
        summary = []
        if type_changed:
            old_label = get_claim_type_display(self._original_claim_type)
            new_label = get_claim_type_display(new_type)
            summary.append(tr("page.claim_details.change_claim_type", old=old_label, new=new_label))
        if share_changed:
            old_display = f"{self._original_ownership_share} {tr('unit.shares')}" if self._original_ownership_share is not None else "-"
            new_display = f"{new_share_val} {tr('unit.shares')}" if new_share_val is not None else "-"
            summary.append(tr("page.claim_details.change_ownership_share", old=old_display, new=new_display))
        if self._pending_uploads:
            summary.append(tr("page.claim_details.upload_count", count=len(self._pending_uploads)))
        if self._pending_links:
            summary.append(tr("page.claim_details.link_count", count=len(self._pending_links)))
        if self._pending_deletes:
            summary.append(tr("page.claim_details.remove_count", count=len(self._pending_deletes)))

        dialog = ModificationReasonDialog(summary, parent=self)
        if dialog.exec_() != ModificationReasonDialog.Accepted:
            return
        reason = dialog.get_reason()

        update_data = {}

        if type_changed:
            update_data["relationType"] = new_type

        if share_changed and new_share_val is not None:
            update_data["ownershipShare"] = new_share_val / 2400.0

        if self._pending_uploads:
            new_evidence = []
            for fp in self._pending_uploads:
                try:
                    file_size = os.path.getsize(fp)
                    file_name = os.path.basename(fp)
                    ext = os.path.splitext(file_name)[1].lower()
                    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                                ".png": "image/png", ".pdf": "application/pdf"}
                    mime_type = mime_map.get(ext, "application/octet-stream")
                    with open(fp, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    new_evidence.append({
                        "evidenceType": 2,
                        "description": file_name,
                        "originalFileName": file_name,
                        "filePath": fp,
                        "fileSizeBytes": file_size,
                        "mimeType": mime_type,
                        "fileHash": file_hash,
                    })
                except Exception as e:
                    logger.error(f"Failed to read file {fp}: {e}")
            if new_evidence:
                update_data["newEvidence"] = new_evidence

        if self._pending_links:
            link_ids = []
            for ev_data in self._pending_links:
                ev_id = str(ev_data.get("id") or ev_data.get("evidenceId") or "")
                if ev_id:
                    link_ids.append(ev_id)
            if link_ids:
                update_data["linkExistingEvidenceIds"] = link_ids

        if self._pending_deletes:
            update_data["unlinkEvidenceRelationIds"] = list(self._pending_deletes)

        if reason:
            update_data["reasonForModification"] = reason

        self._spinner.show_loading(tr("component.loading.default"))
        self._header.edit_clicked.disconnect()
        self._save_worker = ApiWorker(ctrl.update_claim, self._claim_id, update_data)
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.error.connect(self._on_save_error)
        self._save_worker.start()

    def _on_save_finished(self, result):
        self._spinner.hide_loading()
        self._header.edit_clicked.connect(self._on_edit_or_save_clicked)

        if not result.success:
            Toast.show_toast(self, tr("page.claim_details.save_failed", error=result.message), Toast.ERROR)
        else:
            Toast.show_toast(self, tr("page.claim_details.save_success"), Toast.SUCCESS)

        self._is_editing = False
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._claim_type_combo = None
        self._ownership_share_input = None

        self._animate_relation_card_edit(False)
        self._header.set_editing(False)
        self._header.set_edit_visible(True)
        self._reload_claim_data()

    def _on_save_error(self, error_msg):
        self._spinner.hide_loading()
        self._header.set_edit_visible(True)
        self._header.edit_clicked.connect(self._on_edit_or_save_clicked)
        logger.error(f"Save error: {error_msg}")
        Toast.show_toast(self, tr("page.claim_details.save_failed", error=error_msg), Toast.ERROR)

    def _reload_claim_data(self):
        from controllers.claim_controller import ClaimController
        ctrl = ClaimController()
        self._spinner.show_loading(tr("component.loading.default"))
        self._reload_worker = ApiWorker(
            ctrl.get_claim_full_detail,
            self._claim_id,
            hint_survey_id=self._survey_id,
            hint_relation_id=self._relation_id,
        )
        self._reload_worker.finished.connect(self._on_reload_claim_finished)
        self._reload_worker.error.connect(self._on_reload_claim_error)
        self._reload_worker.start()

    def _on_reload_claim_finished(self, result):
        self._spinner.hide_loading()
        if result.success:
            self._apply_data(result.data)
        else:
            logger.warning(f"Failed to reload claim data: {result.message}")

    def _on_reload_claim_error(self, error_msg):
        self._spinner.hide_loading()
        logger.warning(f"Failed to reload claim data: {error_msg}")

    # -- Language --

    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)
        self._header.update_texts()
        if self._claim_data:
            self._populate_header()
            self._populate_person_card()
            self._populate_property_card()
            self._populate_relation_card()
            self._populate_status_card()
            self._update_edit_visibility()
