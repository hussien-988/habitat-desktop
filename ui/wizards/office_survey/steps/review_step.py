# -*- coding: utf-8 -*-
"""
Review Step - Step 6 of Office Survey Wizard.

Final review and submission step with GlowingCard grid layout,
watermark scroll area, and animated accent decorations matching
the CaseDetailsPage design language.
"""

from typing import Dict, Any
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
    QHBoxLayout, QGridLayout, QGraphicsDropShadowEffect,
    QPushButton, QMenu, QSizePolicy, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QSize,
    QPropertyAnimation, QEasingCurve, QRectF,
)
from PyQt5.QtGui import (
    QColor, QIcon, QPainter, QLinearGradient, QPen, QPainterPath, QCursor,
)

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.error_handler import ErrorHandler
from ui.design_system import Colors, ScreenScale
from ui.wizards.office_survey.wizard_styles import (
    STEP_CARD_STYLE, make_step_card, make_icon_header, make_divider,
    DIVIDER_COLOR, ADDRESS_TEXT_COLOR, READONLY_BG,
    PERSON_CARD_STYLE, CONTEXT_MENU_STYLE, MENU_DOTS_STYLE,
    EVIDENCE_AVAILABLE_STYLE, EVIDENCE_WAITING_STYLE,
)
from ui.style_manager import StyleManager
from ui.font_utils import FontManager, create_font
from ui.components.icon import Icon
from ui.components.logo import LogoWidget
from ui.components.toast import Toast
from utils.logger import get_logger
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from services.error_mapper import map_exception
from ui.wizards.office_survey.steps.occupancy_claims_step import _is_owner_relation
from services.display_mappings import (
    get_relation_type_display, get_relationship_to_head_display,
    get_unit_status_display,
    get_claim_type_display, get_priority_display,
    get_business_type_display, get_source_display,
    get_claim_status_display,
)
from utils.helpers import build_hierarchical_address
from ui.components.loading_spinner import LoadingSpinnerOverlay

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
#  _AccentLine  (animated gradient separator)
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
#  _GlowingCard  (card with animated orbiting blue border light)
# ---------------------------------------------------------------------------

class _GlowingCard(QFrame):
    """Card with animated orbiting blue border light."""

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
#  _WatermarkScrollArea  (scroll area with pulsing logo watermark)
# ---------------------------------------------------------------------------

class _WatermarkScrollArea(QScrollArea):
    """Scroll area with pulsing logo watermark."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logo = LogoWidget(height=120, parent=self)
        self._logo_effect = QGraphicsOpacityEffect(self._logo)
        self._logo_effect.setOpacity(0.04)
        self._logo.setGraphicsEffect(self._logo_effect)
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
#  ReviewStep
# ---------------------------------------------------------------------------

class ReviewStep(BaseStep):
    """Step 6: Review & Submit — GlowingCard grid layout."""

    edit_requested = pyqtSignal(int)  # Emits step index to edit

    def __init__(self, context: SurveyContext, parent=None, read_only=False):
        self._read_only = read_only
        super().__init__(context, parent)

        self._api_service = get_api_client()

    # ── UI Setup ─────────────────────────────────────────────────────────

    def setup_ui(self):
        """Build the GlowingCard grid inside a watermark scroll area."""
        widget = self
        widget.setLayoutDirection(get_layout_direction())
        widget.setStyleSheet(f"QWidget {{ background-color: {Colors.BACKGROUND}; }}")

        layout = self.main_layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Accent line at the top
        self._accent_line = _AccentLine()
        layout.addWidget(self._accent_line)

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
        self._scroll_layout.setContentsMargins(16, 16, 16, 40)
        self._scroll_layout.setSpacing(16)

        # Case status banner (shown only in read-only/case-details mode)
        self.case_status_banner = self._create_case_status_banner()
        self.case_status_banner.hide()
        self._scroll_layout.addWidget(self.case_status_banner)

        # ── Card 1: Survey Info (full width) ────────────────────────
        self._survey_card = _GlowingCard()
        self._survey_card_layout = QVBoxLayout(self._survey_card)
        self._survey_card_layout.setContentsMargins(24, 20, 24, 20)
        self._survey_card_layout.setSpacing(12)
        self._survey_content = QVBoxLayout()
        self._survey_content.setSpacing(12)
        self._survey_card_layout.addLayout(self._survey_content)
        self._scroll_layout.addWidget(self._survey_card)

        # ── Row: Building (half) | Applicant (half) ─────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        self._building_card = _GlowingCard()
        self._building_card_layout = QVBoxLayout(self._building_card)
        self._building_card_layout.setContentsMargins(24, 20, 24, 20)
        self._building_card_layout.setSpacing(12)
        self._building_content = QVBoxLayout()
        self._building_content.setSpacing(12)
        self._building_card_layout.addLayout(self._building_content)
        top_row.addWidget(self._building_card, 1)

        self._applicant_card_widget = _GlowingCard()
        self._applicant_card_layout = QVBoxLayout(self._applicant_card_widget)
        self._applicant_card_layout.setContentsMargins(24, 20, 24, 20)
        self._applicant_card_layout.setSpacing(12)
        self._applicant_content = QVBoxLayout()
        self._applicant_content.setSpacing(12)
        self._applicant_card_layout.addLayout(self._applicant_content)
        top_row.addWidget(self._applicant_card_widget, 1)

        if self._read_only:
            self._applicant_card_widget.hide()

        self._scroll_layout.addLayout(top_row)

        # ── Card 3: Unit & Household (full width) ───────────────────
        self._unit_household_card = _GlowingCard()
        self._unit_household_card_layout = QVBoxLayout(self._unit_household_card)
        self._unit_household_card_layout.setContentsMargins(24, 20, 24, 20)
        self._unit_household_card_layout.setSpacing(12)
        self._unit_content = QVBoxLayout()
        self._unit_content.setSpacing(12)
        self._unit_household_card_layout.addLayout(self._unit_content)
        self._household_content = QVBoxLayout()
        self._household_content.setSpacing(12)
        self._unit_household_card_layout.addLayout(self._household_content)
        self._scroll_layout.addWidget(self._unit_household_card)

        # ── Card 4: Persons & Relations (full width) ─────────────────
        self._persons_card = _GlowingCard()
        self._persons_card_layout = QVBoxLayout(self._persons_card)
        self._persons_card_layout.setContentsMargins(24, 20, 24, 20)
        self._persons_card_layout.setSpacing(12)
        self._persons_content = QVBoxLayout()
        self._persons_content.setSpacing(10)
        self._persons_card_layout.addLayout(self._persons_content)
        self._scroll_layout.addWidget(self._persons_card)

        self._scroll_layout.addStretch()

        self._scroll.setWidget(scroll_content)
        layout.addWidget(self._scroll, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    # ── Section header helper (matches case_details_page style) ──────

    def _add_section_header(self, layout, icon_name, title, subtitle="", edit_callback=None):
        """Build an icon + title + subtitle header row with optional edit button."""
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            "QLabel { background-color: #EBF5FF; border: 1px solid #DBEAFE; border-radius: 8px; }"
        )
        icon_pixmap = Icon.load_pixmap(icon_name, size=16)
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

        if edit_callback and not self._read_only:
            edit_btn = self._create_edit_icon_button(edit_callback)
            h_layout.addWidget(edit_btn)

        layout.addWidget(header)

    # ── Field helpers ────────────────────────────────────────────────

    def _create_field_pair(self, label_text, value_text):
        """Create a label + value widget pair for grid display."""
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

    def _create_section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        return lbl

    def _create_badge(self, text, bg_color, text_color):
        badge = QLabel(str(text))
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(24))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {bg_color}; color: {text_color}; "
            f"border: none; border-radius: 12px; padding: 2px 12px; }}"
        )
        return badge

    def _create_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {Colors.BORDER_DEFAULT}; border: none;")
        return line

    def _create_empty_state(self, message):
        lbl = QLabel(message)
        lbl.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setMinimumHeight(ScreenScale.h(40))
        return lbl

    # ── Edit buttons ─────────────────────────────────────────────────

    def _request_edit(self, step_index: int):
        """Emit signal requesting wizard to enter edit mode for a step."""
        self.edit_requested.emit(step_index)

    def _create_edit_icon_button(self, callback) -> QPushButton:
        """Create a small edit icon button for card headers."""
        btn = QPushButton()
        btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(56, 144, 223, 0.2);
                border-radius: 8px;
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
        icon_pixmap = Icon.load_pixmap("edit-02", 14)
        if icon_pixmap and not icon_pixmap.isNull():
            btn.setIcon(QIcon(icon_pixmap))
            btn.setIconSize(QSize(14, 14))
        else:
            btn.setText("\u270E")
            btn.setStyleSheet(btn.styleSheet() + "QPushButton { color: #3890DF; font-size: 14px; }")
        btn.clicked.connect(callback)
        return btn

    def _create_edit_menu_button(self, callback) -> QPushButton:
        """Create a menu button with a single edit action (legacy support)."""
        menu_btn = QPushButton("\u22EE")
        menu_btn.setFixedSize(ScreenScale.w(36), ScreenScale.h(36))
        menu_btn.setStyleSheet(MENU_DOTS_STYLE)
        menu_btn.setCursor(Qt.PointingHandCursor)

        menu = QMenu(menu_btn)
        menu.setLayoutDirection(get_layout_direction())
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        edit_action = menu.addAction(tr("wizard.review.edit"))
        edit_action.triggered.connect(callback)

        menu_btn.clicked.connect(
            lambda: menu.exec_(menu_btn.mapToGlobal(menu_btn.rect().bottomRight()))
        )
        return menu_btn

    # ── Case status banner ───────────────────────────────────────────

    def _create_case_status_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("caseStatusBanner")
        banner.setFixedHeight(ScreenScale.h(48))
        banner.setStyleSheet("""
            QFrame#caseStatusBanner {
                background-color: #FFF7ED;
                border: 1px solid #FED7AA;
                border-radius: 8px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(16, 0, 16, 0)

        self._case_status_label = QLabel(tr("review.case.open"))
        self._case_status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._case_status_label.setStyleSheet("color: #C2410C; background: transparent; border: none;")
        self._case_status_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        b_layout.addWidget(self._case_status_label)
        return banner

    # ── Layout helpers ───────────────────────────────────────────────

    def _add_shadow(self, widget: QWidget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 18))
        widget.setGraphicsEffect(shadow)

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

    # ── Person row ───────────────────────────────────────────────────

    def _create_person_row(self, person: dict) -> QWidget:
        """Create a person row card with blue left border accent."""
        row = QFrame()
        row.setLayoutDirection(get_layout_direction())
        row.setFixedHeight(ScreenScale.h(80))
        row.setStyleSheet(PERSON_CARD_STYLE)

        card_layout = QHBoxLayout(row)
        card_layout.setContentsMargins(15, 0, 15, 0)

        # Icon + Text
        right_group = QHBoxLayout()
        right_group.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(ScreenScale.w(36), ScreenScale.h(36))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #EBF5FF;
                color: #3890DF;
                border-radius: 18px;
                border: 1px solid #DBEAFE;
            }
        """)
        user_pixmap = Icon.load_pixmap("user", size=20)
        if user_pixmap and not user_pixmap.isNull():
            icon_lbl.setPixmap(user_pixmap)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        full_name = f"{person.get('first_name', '')} {person.get('father_name', '')} {person.get('last_name', '')}".strip()
        if not full_name:
            full_name = person.get('full_name', person.get('name', '-'))
        name_lbl = QLabel(full_name)
        name_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        role_key = person.get('person_role') or person.get('relationship_type')
        role_text = get_relationship_to_head_display(role_key) if role_key else ""

        # Role badge
        role_widget = QWidget()
        role_widget.setStyleSheet("background: transparent; border: none;")
        role_row = QHBoxLayout(role_widget)
        role_row.setContentsMargins(0, 0, 0, 0)
        role_row.setSpacing(6)
        if role_text:
            role_badge = self._create_badge(role_text, "#DBEAFE", "#1E40AF")
            role_row.addWidget(role_badge)
        role_row.addStretch()

        text_vbox.addWidget(name_lbl)
        text_vbox.addWidget(role_widget)

        right_group.addWidget(icon_lbl)
        right_group.addLayout(text_vbox)

        card_layout.addLayout(right_group)
        card_layout.addStretch()

        # "View personal info" link
        if not self._read_only:
            view_lbl = QLabel(tr("wizard.review.view_personal_info"))
            view_lbl.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_MEDIUM))
            view_lbl.setStyleSheet("color: #3890DF; background: transparent; border: none;")
            view_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            view_lbl.setCursor(Qt.PointingHandCursor)
            view_lbl.mousePressEvent = lambda e, p=person: self._view_person_editable(p)
            card_layout.addWidget(view_lbl)

        return row

    # ── Map dialog ───────────────────────────────────────────────────

    def _open_map_dialog(self):
        from ui.components.building_map_dialog_v2 import show_building_map_dialog

        auth_token = None
        try:
            main_window = self
            while main_window and not hasattr(main_window, 'current_user'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                auth_token = getattr(main_window.current_user, '_api_token', None)
        except Exception as e:
            logger.warning(f"Could not get auth token: {e}")
            Toast.show_toast(self, tr("wizard.review.load_failed"), Toast.ERROR)

        building = self.context.building
        if building:
            show_building_map_dialog(
                db=self.context.db,
                selected_building_id=building.building_uuid or building.building_id,
                auth_token=auth_token,
                read_only=True,
                selected_building=building,
                parent=self
            )

    # ══════════════════════════════════════════════════════════════════
    #  POPULATE ALL CARDS
    # ══════════════════════════════════════════════════════════════════

    def _populate_review(self):
        """Populate all summary cards with data from context."""
        self._populate_case_status_banner()
        self._populate_survey_card()
        self._populate_building_card()
        self._populate_applicant_card()
        self._populate_unit_card()
        self._populate_household_card()
        self._populate_persons_card()
        self._accent_line.pulse()

    # ── Case Status Banner ───────────────────────────────────────────

    def _populate_case_status_banner(self):
        has_owner = False
        owner_has_evidence = False

        for p in (self.context.persons or []):
            role = p.get('person_role') or p.get('relationship_type')
            if _is_owner_relation(role):
                has_owner = True
                rel_files = p.get('_relation_uploaded_files') or []
                has_docs_flag = p.get('relation_data', {}).get('has_documents', False)
                if rel_files or has_docs_flag:
                    owner_has_evidence = True
                break

        if has_owner and owner_has_evidence:
            text = tr("review.case.closed")
            text_color = "#15803D"
            bg_color, border_color = "#F0FDF4", "#BBF7D0"
        elif has_owner:
            text = tr("review.case.pending_evidence")
            text_color = "#92400E"
            bg_color, border_color = "#FFFBEB", "#FDE68A"
        else:
            text = tr("review.case.open")
            text_color = "#C2410C"
            bg_color, border_color = "#FFF7ED", "#FED7AA"

        self._case_status_label.setText(text)
        self._case_status_label.setStyleSheet(
            f"color: {text_color}; background: transparent; border: none;"
        )
        self.case_status_banner.setStyleSheet(f"""
            QFrame#caseStatusBanner {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """)

    # ── Survey Info Card ─────────────────────────────────────────────

    def _populate_survey_card(self):
        self._clear_layout(self._survey_content)

        self._add_section_header(
            self._survey_content, "data",
            tr("wizard.review.step_title"),
            tr("wizard.review.step_description"),
        )

        grid = QGridLayout()
        grid.setSpacing(16)

        ctx = self.context
        ref = ctx.get_data("survey_id") or "-"
        created = ""
        if ctx.created_at:
            try:
                created = ctx.created_at.strftime("%Y-%m-%d")
            except Exception:
                created = str(ctx.created_at)

        status = getattr(ctx, 'status', '') or ctx.get_data("status") or ""
        is_draft = str(status).lower() in ("draft", "1", "")
        status_display = tr("page.case_details.status_draft") if is_draft else tr("page.case_details.status_completed")

        source = getattr(ctx, 'source', '') or ctx.get_data("source") or ""
        source_display = get_source_display(source) if source else "-"

        grid.addWidget(self._create_field_pair(tr("page.case_details.ref_number"), ref), 0, 0)
        grid.addWidget(self._create_field_pair(tr("wizard.review.survey_date"), created or "-"), 0, 1)
        grid.addWidget(self._create_field_pair(tr("wizard.review.case_status"), status_display), 0, 2)
        grid.addWidget(self._create_field_pair(tr("wizard.review.source"), source_display), 0, 3)

        self._survey_content.addLayout(grid)

    # ── Building Card (half width) ───────────────────────────────────

    def _populate_building_card(self):
        self._clear_layout(self._building_content)

        self._add_section_header(
            self._building_content, "blue",
            tr("wizard.review.building_card_title"),
            tr("wizard.review.building_card_subtitle"),
        )

        if not self.context.building:
            self._building_content.addWidget(
                self._create_empty_state(tr("wizard.building.not_selected"))
            )
            return

        building = self.context.building
        building_code = str(building.building_id) if hasattr(building, 'building_id') else "-"

        # Building code
        code_lbl = QLabel(building_code)
        code_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        code_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        code_lbl.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        self._building_content.addWidget(code_lbl)

        # Address bar
        address = build_hierarchical_address(building_obj=building, unit_obj=None, include_unit=False)
        addr_bar = QFrame()
        addr_bar.setLayoutDirection(get_layout_direction())
        addr_bar.setFixedHeight(ScreenScale.h(32))
        addr_bar.setStyleSheet("QFrame { background-color: #F0F4FA; border: 1px solid #DBEAFE; border-radius: 10px; }")
        addr_row = QHBoxLayout(addr_bar)
        addr_row.setContentsMargins(12, 0, 12, 0)
        addr_row.setSpacing(8)
        addr_row.addStretch()
        addr_icon = QLabel()
        addr_icon.setStyleSheet("background: transparent; border: none;")
        addr_icon_pixmap = Icon.load_pixmap("dec", size=16)
        if addr_icon_pixmap and not addr_icon_pixmap.isNull():
            addr_icon.setPixmap(addr_icon_pixmap)
        addr_row.addWidget(addr_icon)
        addr_text = QLabel(address if address else "-")
        addr_text.setAlignment(Qt.AlignCenter)
        addr_text.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        addr_text.setStyleSheet(f"color: {ADDRESS_TEXT_COLOR}; background: transparent; border: none;")
        addr_row.addWidget(addr_text)
        addr_row.addStretch()
        self._building_content.addWidget(addr_bar)

        # Stats grid
        building_type = building.building_type_display if hasattr(building, 'building_type_display') else "-"
        status = building.building_status_display if hasattr(building, 'building_status_display') else "-"
        units_count = str(building.number_of_units) if hasattr(building, 'number_of_units') else "0"

        stats_grid = QGridLayout()
        stats_grid.setSpacing(12)
        stats_grid.addWidget(self._create_field_pair(tr("wizard.building.status"), status), 0, 0)
        stats_grid.addWidget(self._create_field_pair(tr("wizard.building.type"), building_type), 0, 1)
        stats_grid.addWidget(self._create_field_pair(tr("wizard.building.units_count"), units_count), 1, 0)

        parcels_count = str(getattr(building, 'number_of_apartments', 0))
        shops_count = str(building.number_of_shops) if hasattr(building, 'number_of_shops') else "0"
        stats_grid.addWidget(self._create_field_pair(tr("wizard.building.parcels_count"), parcels_count), 1, 1)

        self._building_content.addLayout(stats_grid)

        # Map thumbnail
        map_container = QLabel()
        map_container.setFixedHeight(ScreenScale.h(100))
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("reviewMapContainer")
        map_container.setStyleSheet("QLabel#reviewMapContainer { background-color: #E8E8E8; border-radius: 8px; }")
        map_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_pixmap or map_pixmap.isNull():
            map_pixmap = Icon.load_pixmap("map-placeholder", size=None)
        if map_pixmap and not map_pixmap.isNull():
            map_container.setPixmap(map_pixmap.scaled(map_container.width() or 300, 100, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        else:
            loc_fallback = Icon.load_pixmap("carbon_location-filled", size=36)
            if loc_fallback and not loc_fallback.isNull():
                map_container.setPixmap(loc_fallback)

        map_button = QPushButton(map_container)
        map_button.setFixedSize(ScreenScale.w(94), ScreenScale.h(20))
        map_button.move(8, 8)
        map_button.setCursor(Qt.PointingHandCursor)
        icon_pixmap = Icon.load_pixmap("pill", size=12)
        if icon_pixmap and not icon_pixmap.isNull():
            map_button.setIcon(QIcon(icon_pixmap))
            map_button.setIconSize(QSize(12, 12))
        map_button.setText(tr("wizard.building.open_map"))
        map_button.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
            }}
        """)
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(8)
        btn_shadow.setXOffset(0)
        btn_shadow.setYOffset(2)
        btn_shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(btn_shadow)
        map_button.clicked.connect(self._open_map_dialog)

        self._building_content.addWidget(map_container)

    # ── Applicant Card (half width) ──────────────────────────────────

    def _populate_applicant_card(self):
        self._clear_layout(self._applicant_content)

        self._add_section_header(
            self._applicant_content, "user",
            tr("review.applicant.title"),
            "",
            edit_callback=lambda: self._request_edit(1),
        )

        applicant = getattr(self.context, 'applicant', None)
        if not applicant:
            self._applicant_content.addWidget(
                self._create_empty_state("-")
            )
            return

        full_name_display = " ".join(filter(None, [
            applicant.get("first_name_ar"),
            applicant.get("father_name_ar"),
            applicant.get("last_name_ar"),
        ])) or applicant.get("full_name", "-")

        fields = [
            (tr("wizard.applicant.full_name"), full_name_display),
            (tr("wizard.applicant.national_id"), applicant.get("national_id", "")),
            (tr("wizard.applicant.phone"), applicant.get("phone", "")),
            (tr("wizard.applicant.email"), applicant.get("email", "")),
        ]

        grid = QGridLayout()
        grid.setSpacing(12)
        idx = 0
        for label_text, value_text in fields:
            if not value_text or value_text == "-":
                continue
            grid.addWidget(self._create_field_pair(label_text, value_text), idx // 2, idx % 2)
            idx += 1

        self._applicant_content.addLayout(grid)

    # ── Unit Card (inside Unit & Household GlowingCard) ──────────────

    def _populate_unit_card(self):
        self._clear_layout(self._unit_content)

        self._add_section_header(
            self._unit_content, "move",
            tr("wizard.review.unit_card_title"),
            tr("wizard.review.unit_card_subtitle"),
            edit_callback=lambda: self._request_edit(2),
        )

        unit = self.context.unit
        new_unit_data = self.context.new_unit_data if self.context.is_new_unit else None

        if unit or new_unit_data:
            if unit:
                unit_num = str(unit.unit_number or unit.apartment_number or "-")
                floor = str(unit.floor_number) if unit.floor_number is not None else "-"
                rooms = str(unit.apartment_number) if unit.apartment_number and str(unit.apartment_number) != "0" else "-"
                if unit.area_sqm:
                    try:
                        area = tr("wizard.unit.area_format", value=f"{float(unit.area_sqm):.2f}")
                    except (ValueError, TypeError):
                        area = "-"
                else:
                    area = "-"
                unit_type = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else "-"
                status_raw = getattr(unit, 'apartment_status', None)
                if status_raw is not None:
                    status = get_unit_status_display(status_raw)
                else:
                    status = "-"
            else:
                unit_num = str(new_unit_data.get('unit_number', tr("wizard.review.new_unit")))
                floor = str(new_unit_data.get('floor_number', '-'))
                rooms = str(new_unit_data.get('number_of_rooms', '-'))
                area_raw = new_unit_data.get('area_sqm')
                area = tr("wizard.unit.area_format", value=f"{float(area_raw):.2f}") if area_raw else "-"
                unit_type = new_unit_data.get('unit_type', '-')
                status = tr("wizard.review.new_unit")

            # Unit info container
            unit_info_container = QFrame()
            unit_info_container.setLayoutDirection(get_layout_direction())
            unit_info_container.setFixedHeight(ScreenScale.h(73))
            unit_info_container.setStyleSheet("""
                QFrame {
                    background-color: #F8FAFF;
                    border: 1px solid #E2EAF2;
                    border-radius: 10px;
                }
            """)

            unit_info_row = QHBoxLayout(unit_info_container)
            unit_info_row.setSpacing(0)
            unit_info_row.setContentsMargins(8, 8, 8, 8)

            data_points = [
                (tr("wizard.unit.number"), unit_num),
                (tr("wizard.unit.floor_number"), floor),
                (tr("wizard.unit.rooms_count"), rooms),
                (tr("wizard.unit.area"), area),
                (tr("wizard.unit.type"), unit_type),
                (tr("wizard.unit.status"), status),
            ]

            for label_text, value_text in data_points:
                section, _ = self._create_unit_stat_section(label_text, value_text)
                unit_info_row.addWidget(section, stretch=1)

            self._unit_content.addWidget(unit_info_container)

            # Property description
            desc_text_content = ""
            if unit and hasattr(unit, 'property_description') and unit.property_description:
                desc_text_content = unit.property_description
            elif new_unit_data and new_unit_data.get('property_description'):
                desc_text_content = new_unit_data.get('property_description')
            else:
                desc_text_content = tr("wizard.unit.property_description_placeholder")

            desc_container = QWidget()
            desc_container.setLayoutDirection(get_layout_direction())
            desc_container.setStyleSheet("background: transparent; border: none;")
            desc_layout = QVBoxLayout(desc_container)
            desc_layout.setContentsMargins(0, 0, 0, 0)
            desc_layout.setSpacing(2)

            desc_title = QLabel(tr("wizard.unit.property_description"))
            desc_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            desc_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

            desc_text = QLabel(desc_text_content)
            desc_text.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            desc_text.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            desc_text.setWordWrap(True)
            desc_text.setMaximumHeight(ScreenScale.h(40))

            desc_layout.addWidget(desc_title)
            desc_layout.addWidget(desc_text)
            self._unit_content.addWidget(desc_container)
        else:
            self._unit_content.addWidget(
                self._create_empty_state(tr("wizard.unit.not_selected"))
            )

        # Divider between unit and household
        self._unit_content.addWidget(self._create_divider())

    def _create_unit_stat_section(self, label_text: str, value_text: str = "-"):
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 0, 8, 0)
        section_layout.setSpacing(4)
        section_layout.setAlignment(Qt.AlignCenter)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        value = QLabel(value_text)
        value.setAlignment(Qt.AlignCenter)
        value.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        section_layout.addWidget(label)
        section_layout.addWidget(value)
        return section, value

    # ── Household Card (inside Unit & Household GlowingCard) ─────────

    def _populate_household_card(self):
        self._clear_layout(self._household_content)

        self._add_section_header(
            self._household_content, "user-group",
            tr("wizard.review.household_card_title"),
            tr("wizard.review.household_card_subtitle"),
            edit_callback=lambda: self._request_edit(3),
        )

        if not self.context.households:
            self._household_content.addWidget(
                self._create_empty_state(tr("wizard.household.no_data"))
            )
            return

        hh = self.context.households[0] if self.context.households else {}
        total_size = hh.get('size', 0)

        main_occupant_name = "-"
        if self.context.persons:
            p = self.context.persons[0]
            main_occupant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
            if not main_occupant_name:
                main_occupant_name = p.get('full_name', p.get('name', '-'))

        # Summary row
        summary_container = QWidget()
        summary_container.setLayoutDirection(get_layout_direction())
        summary_container.setStyleSheet("background: transparent; border: none;")
        summary_layout = QHBoxLayout(summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)

        occupant_block = QVBoxLayout()
        occupant_block.setSpacing(4)
        occupant_title = self._create_section_label(tr("wizard.review.main_occupant_info"))
        occupant_val = QLabel(main_occupant_name)
        occupant_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        occupant_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        occupant_block.addWidget(occupant_title)
        occupant_block.addWidget(occupant_val)

        count_block = QVBoxLayout()
        count_block.setSpacing(4)
        count_title = self._create_section_label(tr("wizard.household.family_size"))
        count_title.setAlignment(Qt.AlignCenter)
        count_val = QLabel(str(total_size))
        count_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        count_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        count_val.setAlignment(Qt.AlignCenter)
        count_block.addWidget(count_title)
        count_block.addWidget(count_val)

        summary_layout.addLayout(occupant_block)
        summary_layout.addStretch()
        summary_layout.addLayout(count_block)
        summary_layout.addStretch()

        self._household_content.addWidget(summary_container)

        # Demographics cards (gender + age side by side)
        gender_items = [
            (tr("wizard.household.males"), hh.get('male_count', 0)),
            (tr("wizard.household.females"), hh.get('female_count', 0)),
        ]

        age_items = [
            (tr("wizard.household.adults"), hh.get('adult_count', 0)),
            (tr("wizard.household.children"), hh.get('child_count', 0)),
            (tr("wizard.household.elderly"), hh.get('elderly_count', 0)),
            (tr("wizard.household.disabled"), hh.get('disabled_count', 0)),
        ]

        cards_container = QWidget()
        cards_container.setLayoutDirection(get_layout_direction())
        cards_container.setStyleSheet("background: transparent; border: none;")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(20)

        cards_layout.addWidget(self._create_demographic_card(gender_items))
        cards_layout.addWidget(self._create_demographic_card(age_items))

        self._household_content.addWidget(cards_container)

    def _create_demographic_card(self, items: list) -> QFrame:
        frame = QFrame()
        frame.setLayoutDirection(get_layout_direction())
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2EAF2;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(18)

        ALIGN_ABS_RIGHT = Qt.AlignRight | Qt.AlignAbsolute

        for i, (text, value) in enumerate(items):
            item_block = QVBoxLayout()
            item_block.setSpacing(4)

            txt_lbl = QLabel(text)
            txt_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            txt_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            txt_lbl.setAlignment(ALIGN_ABS_RIGHT)

            val_lbl = QLabel(str(value))
            val_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            val_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            val_lbl.setAlignment(ALIGN_ABS_RIGHT)

            item_block.addWidget(txt_lbl)
            item_block.addWidget(val_lbl)
            card_layout.addLayout(item_block)

            if i < len(items) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet("background-color: #f1f5f9; border: none;")
                card_layout.addWidget(separator)

        return frame

    # ── Persons Card ─────────────────────────────────────────────────

    def _populate_persons_card(self):
        self._clear_layout(self._persons_content)

        self._add_section_header(
            self._persons_content, "user-account",
            tr("wizard.review.persons_card_title"),
            tr("wizard.review.persons_card_subtitle"),
            edit_callback=lambda: self._request_edit(4),
        )

        if not self.context.persons:
            self._persons_content.addWidget(
                self._create_empty_state(tr("wizard.person.no_persons"))
            )
            return

        for person in self.context.persons:
            row = self._create_person_row(person)
            self._persons_content.addWidget(row)

    # ── View/Edit Person Dialog ──────────────────────────────────────

    def _view_person_editable(self, person: dict):
        """Open PersonDialog in editable mode to view/edit person details from review."""
        from ui.wizards.office_survey.dialogs.person_dialog import PersonDialog
        from PyQt5.QtWidgets import QDialog

        auth_token = None
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            auth_token = main_window._api_token

        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")
        unit_id = None
        if self.context.unit:
            unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            unit_id = self.context.new_unit_data.get('unit_uuid')

        is_finalized = self._read_only or self.context.status == "finalized"

        dialog = PersonDialog(
            person_data=person,
            existing_persons=self.context.persons,
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id,
            household_id=household_id,
            unit_id=unit_id,
            read_only=is_finalized
        )

        if dialog.exec_() == QDialog.Accepted and not is_finalized:
            updated_data = dialog.get_person_data()
            person_id = person.get('person_id')
            updated_data['person_id'] = person_id

            is_applicant = person.get('_is_applicant', False) or person.get('_is_contact_person', False)
            if not is_applicant:
                contact_person_id = self.context.get_data('contact_person_id')
                if contact_person_id and person_id == contact_person_id:
                    is_applicant = True

            if person_id:
                try:
                    self._set_auth_token()
                    if is_applicant and survey_id:
                        self._api_service.update_contact_person(
                            survey_id, person_id, updated_data)
                    elif survey_id and household_id:
                        self._api_service.update_person_in_survey(
                            survey_id, household_id, person_id, updated_data)
                    else:
                        logger.warning(f"Missing survey_id or household_id for person {person_id}")
                        Toast.show_toast(self, tr("wizard.review.load_failed"), Toast.ERROR)
                    logger.info(f"Person {person_id} updated via API from review step")

                    relation_id = updated_data.get('_relation_id') or person.get('_relation_id')
                    if relation_id and survey_id:
                        try:
                            self._api_service.update_relation(survey_id, relation_id, updated_data)
                            logger.info(f"Relation {relation_id} updated via API")
                        except Exception as e:
                            logger.warning(f"Failed to update relation {relation_id}: {e}")
                            Toast.show_toast(self, tr("wizard.review.load_failed"), Toast.ERROR)
                except Exception as e:
                    from services.error_mapper import is_duplicate_nid_error, build_duplicate_person_message
                    if is_duplicate_nid_error(e):
                        ErrorHandler.show_warning(self, build_duplicate_person_message(getattr(e, 'response_data', {})), tr("common.warning"))
                    else:
                        logger.error(f"Failed to update person via API: {e}")
                        from services.error_mapper import map_exception
                        ErrorHandler.show_error(self, map_exception(e), tr("common.error"))
                    return

            for i, p in enumerate(self.context.persons):
                if p.get('person_id') == person_id:
                    self.context.persons[i] = updated_data
                    break

            self._populate_persons_card()
            logger.info(f"Person updated from review: {updated_data.get('first_name', '')} {updated_data.get('last_name', '')}")

    # ── Claim Card ───────────────────────────────────────────────────

    def _create_claim_data_card(self, claim_data: dict) -> QFrame:
        """Create a single read-only claim card."""
        card = QFrame()
        card.setLayoutDirection(get_layout_direction())
        card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: 1px solid #E2EAF2;
                border-radius: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(12)

        ro_field_style = f"""
            QLabel {{
                background-color: {READONLY_BG};
                border: 1px solid #D0D7E2;
                border-radius: 8px;
                padding: 10px;
                color: #2C3E50;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
        """

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for i in range(3):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, value_text, row, col):
            v = QVBoxLayout()
            v.setSpacing(4)
            lbl = self._create_section_label(label_text)
            v.addWidget(lbl)
            val = QLabel(str(value_text) if value_text else "-")
            val.setStyleSheet(ro_field_style)
            v.addWidget(val)
            grid.addLayout(v, row, col)

        # Claimant name
        claimant_name = claim_data.get('person_name', '').strip()
        if not claimant_name:
            claimant_ids = claim_data.get('claimant_person_ids', [])
            if claimant_ids and self.context.persons:
                for p in self.context.persons:
                    if p.get('person_id') in claimant_ids:
                        claimant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
                        break
            if not claimant_name and self.context.persons:
                p = self.context.persons[0]
                claimant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
        if not claimant_name:
            claimant_name = "-"

        unit_display = claim_data.get('unit_display_id', '').strip()
        if not unit_display:
            unit_display = claim_data.get('unit_id', '-') or "-"

        add_field(tr("wizard.review.claimant_id"), claimant_name, 0, 0)
        add_field(tr("wizard.review.unit_claim_id"), unit_display, 0, 1)
        add_field(tr("wizard.review.claim_type"), get_claim_type_display(claim_data.get('claim_type', '')), 0, 2)

        add_field(tr("wizard.review.case_status"), get_claim_status_display(claim_data.get('case_status', 'new')), 1, 0)
        add_field(tr("wizard.review.source"), get_source_display(claim_data.get('source', '')), 1, 1)
        add_field(tr("wizard.review.survey_date"), str(claim_data.get('survey_date', '-') or '-'), 1, 2)

        card_layout.addLayout(grid)
        card_layout.addSpacing(4)

        # Notes
        notes_text = claim_data.get('notes', '')
        notes_title = self._create_section_label(tr("wizard.review.review_notes"))
        card_layout.addWidget(notes_title)

        notes_val = QLabel(notes_text if notes_text else tr("wizard.review.review_notes_placeholder"))
        notes_val.setAlignment(Qt.AlignTop)
        notes_val.setWordWrap(True)
        notes_val.setMinimumHeight(ScreenScale.h(80))
        notes_val.setMaximumHeight(ScreenScale.h(100))
        notes_val.setStyleSheet(f"""
            QLabel {{
                background-color: {READONLY_BG};
                border: 1px solid #D0D7E2;
                border-radius: 8px;
                padding: 8px;
                color: {Colors.TEXT_SECONDARY if not notes_text else '#2C3E50'};
                font-size: 13px;
            }}
        """)
        card_layout.addWidget(notes_val)
        card_layout.addSpacing(4)

        # Evidence status
        evidence_count = claim_data.get('evidence_count', 0)
        if not evidence_count:
            evidence_ids = claim_data.get('evidence_ids', [])
            evidence_count = len(evidence_ids) if evidence_ids else 0

        eval_label = QLabel()
        eval_label.setAlignment(Qt.AlignCenter)
        eval_label.setFixedHeight(ScreenScale.h(36))
        eval_label.setFont(create_font(size=FontManager.WIZARD_BADGE, weight=FontManager.WEIGHT_SEMIBOLD))

        if evidence_count > 0:
            self._set_evidence_label(eval_label, evidence_count)
        else:
            eval_label.setText(tr("wizard.review.waiting_documents"))
            eval_label.setStyleSheet(EVIDENCE_WAITING_STYLE)
            survey_id = self.context.get_data("survey_id")
            if survey_id:
                self._fetch_evidence_count_async(survey_id, eval_label)

        card_layout.addWidget(eval_label)

        return card

    def _set_evidence_label(self, label, count):
        count_text = f" ({count})" if count else ""
        label.setText(f"\u2713  {tr('wizard.review.evidence_available')}{count_text}")
        label.setStyleSheet(EVIDENCE_AVAILABLE_STYLE)

    def _fetch_evidence_count_async(self, survey_id, label):
        api = get_api_client()

        def _do_fetch():
            return api.get_survey_evidences(survey_id)

        def _on_fetched(evidences):
            self._spinner.hide_loading()
            count = len(evidences) if evidences else 0
            if count > 0:
                self._set_evidence_label(label, count)

        self._spinner.show_loading(tr("component.loading.default"))
        self._review_evidence_worker = ApiWorker(_do_fetch)
        self._review_evidence_worker.finished.connect(_on_fetched)
        self._review_evidence_worker.error.connect(
            lambda msg: (self._spinner.hide_loading(),
                         logger.warning(f"Failed to fetch evidence count: {msg}"),
                         Toast.show_toast(self, tr("wizard.review.load_failed"), Toast.ERROR))
        )
        self._review_evidence_worker.start()

    def _populate_claim_card(self):
        """Populate claim information (used by claim_step and case_details)."""
        # This is called externally; claims are shown via _create_claim_data_card
        pass

    # ══════════════════════════════════════════════════════════════════
    #  LIFECYCLE / VALIDATION / SUBMISSION
    # ══════════════════════════════════════════════════════════════════

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._populate_review()

    def validate(self) -> StepValidationResult:
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error(tr("wizard.review.no_building"))
        if not self.context.unit and not self.context.is_new_unit:
            result.add_error(tr("wizard.review.no_unit"))
        if len(self.context.persons) == 0:
            result.add_error(tr("wizard.review.no_persons"))

        return result

    def collect_data(self) -> Dict[str, Any]:
        return self.context.get_summary()

    def on_next(self):
        """Called when user clicks Next/Submit button. Finalize the survey via API."""
        self._set_auth_token()
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            logger.error("No survey_id found in context. Cannot finalize.")
            ErrorHandler.show_error(self, tr("wizard.review.no_survey_id"), tr("common.error"))
            return

        self._spinner.show_loading(tr("component.loading.default"))
        try:
            # Save intervieweeName before finalizing
            try:
                a = self.context.applicant or {}
                parts = [a.get("first_name_ar", ""), a.get("father_name_ar", ""), a.get("last_name_ar", "")]
                name = " ".join(p for p in parts if p) or a.get("full_name")
                if name:
                    self._api_service.save_draft_to_backend(survey_id, {"interviewee_name": name})
            except Exception as e:
                logger.warning(f"Could not save interviewee name: {e}")
                Toast.show_toast(self, tr("wizard.review.load_failed"), Toast.ERROR)

            # Step 1: process-claims if not already done
            if not (hasattr(self.context, 'finalize_response') and self.context.finalize_response):
                self._finalize_survey_via_api(survey_id)
                if not (hasattr(self.context, 'finalize_response') and self.context.finalize_response):
                    return

            # Step 2: finalize survey status
            self._call_finalize_endpoint(survey_id)
        finally:
            self._spinner.hide_loading()

    def _finalize_survey_via_api(self, survey_id: str):
        finalize_options = {
            "finalNotes": "Survey completed successfully",
            "durationMinutes": 10,
            "autoCreateClaim": True
        }
        try:
            response = self._api_service.finalize_office_survey(survey_id, finalize_options)
            logger.info(f"Survey {survey_id} process-claims succeeded")
            self.context.finalize_response = response
        except Exception as e:
            logger.error(f"Failed to process claims for survey {survey_id}: {e}")
            from services.error_mapper import map_exception
            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))

    def _call_finalize_endpoint(self, survey_id: str):
        try:
            self._api_service.finalize_survey_status(survey_id)
            logger.info(f"Survey {survey_id} finalized successfully")
            self.context.status = "finalized"
            # Fetch updated survey to get the proper referenceCode
            try:
                updated = self._api_service.get_office_survey(survey_id)
                ref_code = updated.get("referenceCode", "")
                if ref_code:
                    self.context.reference_number = ref_code
                    if hasattr(self.context, 'finalize_response') and self.context.finalize_response:
                        if "survey" not in self.context.finalize_response:
                            self.context.finalize_response["survey"] = {}
                        self.context.finalize_response["survey"]["referenceCode"] = ref_code
            except Exception as e:
                logger.debug(f"Could not refresh reference code: {e}")
        except Exception as e:
            logger.error(f"Failed to finalize survey status {survey_id}: {e}")
            from services.error_mapper import map_exception
            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))

    def on_show(self):
        super().on_show()
        self._populate_review()

    def get_step_title(self) -> str:
        return tr("wizard.review.step_title")

    def get_step_description(self) -> str:
        return tr("wizard.review.step_description")
