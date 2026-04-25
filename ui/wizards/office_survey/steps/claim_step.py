# -*- coding: utf-8 -*-
"""
Claim Step - Step 6 of Office Survey Wizard.

Displays auto-created claims with GlowingCard layout, watermark scroll area,
and animated accent decorations matching the CaseDetailsPage design language.
"""

from typing import Dict, Any

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QGridLayout, QFrame, QScrollArea, QWidget,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt, pyqtProperty,
    QPropertyAnimation, QEasingCurve, QRectF,
)
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QPen, QPainterPath,
)

from ui.components.centered_text_edit import CenteredTextEdit
from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import (
    get_claim_type_display, get_claim_status_display,
    get_source_display
)
from services.api_worker import ApiWorker
from ui.components.toast import Toast
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.components.logo import LogoWidget
from ui.style_manager import StyleManager
from ui.wizards.office_survey.wizard_styles import (
    STEP_CARD_STYLE, READONLY_FIELD_STYLE,
    make_step_card, make_icon_header, EMPTY_STATE_ICON_STYLE,
    EVIDENCE_AVAILABLE_STYLE, EVIDENCE_WAITING_STYLE,
    CASE_CLOSED_FIELD_STYLE, CASE_OPEN_FIELD_STYLE, READONLY_BG,
)
from ui.font_utils import FontManager, create_font
from ui.design_system import Colors, ScreenScale
from ui.components.icon import Icon
from utils.logger import get_logger
from ui.wizards.office_survey.steps.occupancy_claims_step import _is_owner_relation

logger = get_logger(__name__)


def _find_combo_code_by_english(vocab_name: str, english_key: str) -> int:
    """Find the integer code for a vocabulary item by its English label."""
    from services.vocab_service import get_options
    english_key_lower = english_key.lower()
    for code, label in get_options(vocab_name, lang="en"):
        if label.lower() == english_key_lower:
            return code
    return 0


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
#  ClaimStep
# ---------------------------------------------------------------------------

class ClaimStep(BaseStep):
    """Step 6: Claim Creation — GlowingCard layout."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._claim_cards = []
        self._empty_title_label = None
        self._empty_desc_label = None

    def setup_ui(self):
        """Setup the step's UI with GlowingCard claim cards."""
        widget = self
        widget.setLayoutDirection(get_layout_direction())
        widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Accent line at the top
        self._accent_line = _AccentLine()
        layout.addWidget(self._accent_line)

        # Watermark scroll area
        self.scroll_area = _WatermarkScrollArea()
        self.scroll_area.setLayoutDirection(get_layout_direction())
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(get_layout_direction())
        scroll_content.setStyleSheet("background: transparent;")

        self.cards_layout = QVBoxLayout(scroll_content)
        self.cards_layout.setContentsMargins(16, 16, 16, 40)
        self.cards_layout.setSpacing(16)

        # Create the first (default) claim card
        first_card = self._create_claim_card_widget()
        self.cards_layout.addWidget(first_card)
        self._claim_cards.append(first_card)

        self.cards_layout.addStretch()

        self.scroll_area.setWidget(scroll_content)
        layout.addWidget(self.scroll_area)

        # Empty state widget (hidden by default)
        self.empty_state_widget = self._create_empty_state_widget()
        self.empty_state_widget.hide()
        layout.addWidget(self.empty_state_widget)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_empty_state_widget(self) -> QWidget:
        """Create empty state widget shown when no claims are created."""
        from PyQt5.QtGui import QPixmap

        container = QWidget()
        container.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        center_container = QWidget()
        center_container.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_container)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(15)

        # Icon with blue circle background
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(80), ScreenScale.h(80))
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet(EMPTY_STATE_ICON_STYLE)

        no_result_pixmap = Icon.load_pixmap("tdesign_no-result", size=40)
        if no_result_pixmap and not no_result_pixmap.isNull():
            icon_container.setPixmap(no_result_pixmap)
        else:
            import os
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                                      "assets", "images", "tdesign_no-result.png")
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                icon_container.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                icon_container.setText("\u26A0")
                icon_container.setStyleSheet(icon_container.styleSheet() + "font-size: 28px; color: #1a1a1a;")

        title_label = QLabel(tr("wizard.claim.empty_title"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        desc_label = QLabel(tr("wizard.claim.empty_desc"))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_DESC, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; line-height: 1.5;")

        center_layout.addWidget(icon_container, alignment=Qt.AlignCenter)
        center_layout.addWidget(title_label)
        center_layout.addWidget(desc_label)

        main_layout.addWidget(center_container)

        # Store references for language updates
        self._empty_title_label = title_label
        self._empty_desc_label = desc_label

        return container

    def _add_section_header(self, layout, icon_name, title, subtitle=""):
        """Build an icon + title + subtitle header row."""
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

        layout.addWidget(header)

    def _create_claim_card_widget(self, claim_data: Dict[str, Any] = None) -> _GlowingCard:
        """Create a single claim card widget with GlowingCard container."""
        card = _GlowingCard()
        card.setLayoutDirection(get_layout_direction())
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        # Section header
        self._add_section_header(
            card_layout,
            "elements",
            tr("wizard.claim.card_title"),
            tr("wizard.claim.card_subtitle"),
        )

        # Grid layout for fields
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for i in range(4):
            grid.setColumnStretch(i, 1)

        # Store field labels keyed by translation key for later retranslation
        card._field_labels = {}

        def add_field(tr_key, field_widget, row, col):
            v = QVBoxLayout()
            v.setSpacing(4)
            lbl = QLabel(tr(tr_key))
            lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            v.addWidget(lbl)
            v.addWidget(field_widget)
            grid.addLayout(v, row, col)
            card._field_labels[tr_key] = lbl

        ro_input_style = f"""
            QLineEdit {{
                border: 1px solid #D0D7E2;
                border-radius: 10px;
                padding: 10px;
                background-color: {READONLY_BG};
                color: #2C3E50;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
        """

        # Row 1: claimant | unit | claim type | case category
        claim_person_search = QLineEdit()
        claim_person_search.setPlaceholderText(tr("wizard.claim.person_name_placeholder"))
        claim_person_search.setStyleSheet(ro_input_style)
        claim_person_search.setReadOnly(True)
        add_field("wizard.claim.claimant_id", claim_person_search, 0, 0)

        claim_unit_search = QLineEdit()
        claim_unit_search.setPlaceholderText(tr("wizard.claim.unit_number_placeholder"))
        claim_unit_search.setStyleSheet(ro_input_style)
        claim_unit_search.setReadOnly(True)
        claim_unit_search.setAlignment(Qt.AlignRight)
        add_field("wizard.claim.claimed_unit_id", claim_unit_search, 0, 1)

        claim_type_field = QLineEdit()
        claim_type_field.setReadOnly(True)
        claim_type_field.setStyleSheet(ro_input_style)
        add_field("wizard.claim.case_type", claim_type_field, 0, 2)

        case_category_field = QLineEdit()
        case_category_field.setReadOnly(True)
        case_category_field.setStyleSheet(ro_input_style)
        add_field("wizard.claim.case_category", case_category_field, 0, 3)

        # Row 2: source | survey date
        # Case status field removed — backend is the only source of truth
        # for status, and during creation/review we don't have a real
        # value yet. Showing a local default ("New") was misleading.
        claim_source_field = QLineEdit()
        claim_source_field.setReadOnly(True)
        claim_source_field.setStyleSheet(ro_input_style)
        add_field("wizard.claim.source", claim_source_field, 1, 0)

        claim_survey_date = QLineEdit()
        claim_survey_date.setReadOnly(True)
        claim_survey_date.setStyleSheet(ro_input_style)
        add_field("wizard.claim.survey_date", claim_survey_date, 1, 1)

        card_layout.addLayout(grid)
        card_layout.addSpacing(8)

        # Notes section
        notes_label = QLabel(tr("wizard.claim.review_notes"))
        notes_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        notes_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        card_layout.addWidget(notes_label)
        card._notes_label = notes_label

        claim_notes = CenteredTextEdit()
        claim_notes.setPlaceholderText(tr("wizard.claim.additional_notes_placeholder"))
        claim_notes.setPlaceholderStyleSheet(
            "color: #9CA3AF; background: transparent; font-size: 16px; font-weight: 400;"
        )
        claim_notes.setReadOnly(True)
        claim_notes.setMinimumHeight(ScreenScale.h(100))
        claim_notes.setMaximumHeight(ScreenScale.h(120))
        claim_notes.setStyleSheet(f"""
            QTextEdit {{
                background-color: {READONLY_BG};
                border: 1px solid #D0D7E2;
                border-radius: 10px;
                padding: 8px;
                color: #2C3E50;
                font-size: 14px;
            }}
        """)
        card_layout.addWidget(claim_notes)
        card_layout.addSpacing(8)

        # Evidence status pill
        claim_eval_label = QLabel(tr("wizard.claim.evidence_available"))
        claim_eval_label.setAlignment(Qt.AlignCenter)
        claim_eval_label.setFixedHeight(ScreenScale.h(36))
        claim_eval_label.setFont(create_font(size=FontManager.WIZARD_BADGE, weight=FontManager.WEIGHT_SEMIBOLD))
        claim_eval_label.setStyleSheet(EVIDENCE_AVAILABLE_STYLE)
        card_layout.addWidget(claim_eval_label)

        # Store widget references
        card.claim_person_search = claim_person_search
        card.claim_unit_search = claim_unit_search
        card.claim_type_field = claim_type_field
        card.case_category_field = case_category_field
        card.claim_source_field = claim_source_field
        card.claim_survey_date = claim_survey_date
        card.claim_notes = claim_notes
        card.claim_eval_label = claim_eval_label

        if claim_data:
            self._populate_card_with_data(card, claim_data)

        return card

    def _populate_card_with_data(self, card, claim_data: Dict[str, Any]):
        """Populate a claim card with data from API response."""
        logger.info(f"Populating claim card with: relationType={claim_data.get('relationType')}, "
                     f"caseStatus={claim_data.get('caseStatus')}, "
                     f"casePriority={claim_data.get('casePriority')}, "
                     f"claimSource={claim_data.get('claimSource')}")
        card._claim_raw_data = claim_data

        claimant_name = claim_data.get('fullNameArabic', '')
        if claimant_name:
            card.claim_person_search.setText(claimant_name)

        unit_id = claim_data.get('propertyUnitIdNumber', '')
        if unit_id:
            card.claim_unit_search.setText(unit_id)

        relation_type = claim_data.get('relationType')
        is_ownership = False
        is_tenant = False
        is_occupant = False

        if isinstance(relation_type, int):
            is_ownership = relation_type in (1, 5)
            is_tenant = relation_type in (3,)
            is_occupant = relation_type in (2,)
        elif relation_type is not None:
            rt = str(relation_type).lower()
            is_ownership = rt in ('owner', 'co_owner', 'heir')
            is_tenant = rt == 'tenant'
            is_occupant = rt == 'occupant'

        _TYPE_FALLBACK = {
            "Ownership": tr("wizard.claim.type_ownership"),
            "Tenancy": tr("wizard.claim.type_tenancy"),
            "Occupancy": tr("wizard.claim.type_occupancy"),
        }

        if is_ownership:
            code = _find_combo_code_by_english("ClaimType", "Ownership")
            label = get_claim_type_display(code) if code else _TYPE_FALLBACK["Ownership"]
            card.claim_type_field.setText(label)
        elif is_tenant:
            code = _find_combo_code_by_english("ClaimType", "Tenancy")
            label = get_claim_type_display(code) if code else _TYPE_FALLBACK["Tenancy"]
            card.claim_type_field.setText(label)
        elif is_occupant:
            code = _find_combo_code_by_english("ClaimType", "Occupancy")
            label = get_claim_type_display(code) if code else _TYPE_FALLBACK["Occupancy"]
            card.claim_type_field.setText(label)
        else:
            logger.warning(f"Unknown relationType={relation_type}, defaulting to Ownership")
            code = _find_combo_code_by_english("ClaimType", "Ownership")
            label = get_claim_type_display(code) if code else _TYPE_FALLBACK["Ownership"]
            card.claim_type_field.setText(label)
            is_ownership = True

        if is_ownership:
            card.case_category_field.setText(tr("wizard.claim.case_closed"))
            card.case_category_field.setStyleSheet(CASE_CLOSED_FIELD_STYLE)
        else:
            card.case_category_field.setText(tr("wizard.claim.case_open"))
            card.case_category_field.setStyleSheet(CASE_OPEN_FIELD_STYLE)

        # Case-status field removed; status is backend-owned and not
        # populated locally during creation/review.

        claim_source = claim_data.get('source') or claim_data.get('claimSource')
        if claim_source:
            card.claim_source_field.setText(get_source_display(claim_source))

        survey_date_str = claim_data.get('surveyDate', '')
        if survey_date_str:
            try:
                from datetime import datetime
                survey_date = datetime.fromisoformat(survey_date_str.replace('Z', '+00:00'))
                card.claim_survey_date.setText(f"{survey_date.year}-{survey_date.month:02d}-{survey_date.day:02d}")
            except Exception as e:
                logger.warning(f"Failed to parse survey date: {e}")
                card.claim_survey_date.setText(str(survey_date_str))

        notes = claim_data.get('notes', '')
        if notes:
            card.claim_notes.setText(notes)

        has_evidence = claim_data.get('hasEvidence', False)
        if has_evidence:
            card.claim_eval_label.setText(tr("wizard.claim.evidence_available"))
            card.claim_eval_label.setStyleSheet(EVIDENCE_AVAILABLE_STYLE)
        else:
            card.claim_eval_label.setText(tr("wizard.claim.awaiting_documents"))
            card.claim_eval_label.setStyleSheet(EVIDENCE_WAITING_STYLE)

    def _fetch_evidence_count(self, callback=None) -> int:
        cached = getattr(self, '_cached_evidence_count', 0)
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            if callback:
                callback(0)
            return cached

        from services.api_client import get_api_client
        api = get_api_client()

        def _do_fetch():
            return api.get_survey_evidences(survey_id)

        def _on_fetched(evidences):
            self._spinner.hide_loading()
            count = len(evidences) if evidences else 0
            self._cached_evidence_count = count
            if callback:
                callback(count)

        def _on_error(msg):
            self._spinner.hide_loading()
            logger.warning(f"Failed to fetch evidence count: {msg}")
            Toast.show_toast(self, tr("wizard.claim.load_failed"), Toast.ERROR)
            if callback:
                callback(cached)

        self._spinner.show_loading(tr("component.loading.default"))
        self._evidence_count_worker = ApiWorker(_do_fetch)
        self._evidence_count_worker.finished.connect(_on_fetched)
        self._evidence_count_worker.error.connect(_on_error)
        self._evidence_count_worker.start()

        return cached

    def _evaluate_for_claim(self):
        if hasattr(self.context, 'finalize_response') and self.context.finalize_response:
            self._populate_from_api_response(self.context.finalize_response)
            return
        self._populate_from_context()

    def _populate_from_api_response(self, response: Dict[str, Any]):
        """Populate claim cards from process-claims API response."""
        logger.info("Populating claim cards from API response")

        survey_data = response.get('survey', {})
        claims_count = response.get('claimsCreatedCount', 0)
        created_claims = response.get('createdClaims', [])
        data_summary = response.get('dataSummary', {})
        claim_created = response.get('claimCreated', False)

        while len(self._claim_cards) > 1:
            card = self._claim_cards.pop()
            self.cards_layout.removeWidget(card)
            card.deleteLater()

        if not claim_created:
            logger.info("No claims created - showing empty state")
            self.scroll_area.hide()
            self.empty_state_widget.show()
            return

        self.empty_state_widget.hide()
        self.scroll_area.show()

        if created_claims and len(created_claims) > 0:
            first_claim = created_claims[0]
            self._populate_card_with_data(self._claim_cards[0], first_claim)

            survey_date_str = survey_data.get('surveyDate', '')
            if survey_date_str:
                try:
                    from datetime import datetime
                    survey_date = datetime.fromisoformat(survey_date_str.replace('Z', '+00:00'))
                    self._claim_cards[0].claim_survey_date.setText(f"{survey_date.year}-{survey_date.month:02d}-{survey_date.day:02d}")
                except Exception as e:
                    logger.warning(f"Failed to parse survey date: {e}")
                    self._claim_cards[0].claim_survey_date.setText(str(survey_date_str))

            for i in range(1, len(created_claims)):
                claim = created_claims[i]
                new_card = self._create_claim_card_widget(claim)
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, new_card)
                self._claim_cards.append(new_card)

            self.context.update_data("claims_count", claims_count)
            self.context.update_data("created_claims", created_claims)
        else:
            self._populate_from_context()
            return

        self._accent_line.pulse()

    def _populate_first_card_from_context(self, survey_data: Dict, data_summary: Dict, response: Dict):
        first_card = self._claim_cards[0]

        unit_identifier = survey_data.get('unitIdentifier', '')
        if unit_identifier:
            first_card.claim_unit_search.setText(unit_identifier)
        elif self.context.unit:
            first_card.claim_unit_search.setText(str(self.context.unit.unit_number or ""))

        if self.context.persons:
            first_person = self.context.persons[0]
            full_name = f"{first_person.get('first_name', '')} {first_person.get('last_name', '')}"
            first_card.claim_person_search.setText(full_name.strip())

        survey_date_str = survey_data.get('surveyDate', '')
        if survey_date_str:
            try:
                from datetime import datetime
                survey_date = datetime.fromisoformat(survey_date_str.replace('Z', '+00:00'))
                first_card.claim_survey_date.setText(f"{survey_date.year}-{survey_date.month:02d}-{survey_date.day:02d}")
            except Exception as e:
                logger.warning(f"Failed to parse survey date: {e}")
                first_card.claim_survey_date.setText(str(survey_date_str))

        _TYPE_FB = {"Ownership": tr("wizard.claim.type_ownership"), "Tenancy": tr("wizard.claim.type_tenancy"), "Occupancy": tr("wizard.claim.type_occupancy")}
        owners_or_heirs = [r for r in self.context.relations if _is_owner_relation(r.get('relation_type'))]
        tenants = [r for r in self.context.relations if r.get('relation_type') in ('tenant', 3)]
        occupants = [r for r in self.context.relations if r.get('relation_type') in ('occupant', 2)]

        if owners_or_heirs:
            code = _find_combo_code_by_english("ClaimType", "Ownership")
            first_card.claim_type_field.setText(get_claim_type_display(code) if code else _TYPE_FB["Ownership"])
        elif tenants:
            code = _find_combo_code_by_english("ClaimType", "Tenancy")
            first_card.claim_type_field.setText(get_claim_type_display(code) if code else _TYPE_FB["Tenancy"])
        elif occupants:
            code = _find_combo_code_by_english("ClaimType", "Occupancy")
            first_card.claim_type_field.setText(get_claim_type_display(code) if code else _TYPE_FB["Occupancy"])
        else:
            code = _find_combo_code_by_english("ClaimType", "Ownership")
            first_card.claim_type_field.setText(get_claim_type_display(code) if code else _TYPE_FB["Ownership"])

        first_card._claim_raw_data = {
            'source': response,
            'from_context': True
        }

        evidence_count = data_summary.get('evidenceCount', 0)
        reason = response.get('claimNotCreatedReason', '')

        if evidence_count > 0:
            self._update_evidence_label(first_card.claim_eval_label, evidence_count, reason)
        else:
            self._fetch_evidence_count(
                callback=lambda c: self._update_evidence_label(first_card.claim_eval_label, c, reason)
            )

    def _update_evidence_label(self, label, evidence_count, reason=""):
        if evidence_count > 0:
            label.setText(f"{tr('wizard.claim.evidence_available')} ({evidence_count})")
            label.setStyleSheet(EVIDENCE_AVAILABLE_STYLE)
        else:
            label.setText(reason if reason else tr("wizard.claim.awaiting_documents"))
            label.setStyleSheet(EVIDENCE_WAITING_STYLE)

    def _populate_from_context(self):
        self.empty_state_widget.hide()
        self.scroll_area.show()

        # Remove extra cards from previous run, keep only the first placeholder
        while len(self._claim_cards) > 1:
            card = self._claim_cards.pop()
            self.cards_layout.removeWidget(card)
            card.deleteLater()

        # Build claim list: use context.claims if available (built by OccupancyClaimsStep),
        # otherwise fall back to grouping relations by type.
        claims_preview = list(self.context.claims) if self.context.claims else []

        if not claims_preview:
            # Fallback: one entry per person who has a relation
            owners_or_heirs = [r for r in self.context.relations if _is_owner_relation(r.get('relation_type'))]
            tenants = [r for r in self.context.relations if r.get('relation_type') in ('tenant', 3)]
            occupants = [r for r in self.context.relations if r.get('relation_type') in ('occupant', 2)]
            unit_num = ""
            if self.context.unit:
                u = self.context.unit
                unit_num = str(u.unit_number or u.apartment_number or "")
            for r in owners_or_heirs:
                claims_preview.append({'claim_type': 'owner', 'person_name': r.get('person_name', ''), 'unit_display_id': unit_num})
            for r in tenants:
                claims_preview.append({'claim_type': 'tenant', 'person_name': r.get('person_name', ''), 'unit_display_id': unit_num})
            for r in occupants:
                claims_preview.append({'claim_type': 'occupant', 'person_name': r.get('person_name', ''), 'unit_display_id': unit_num})

        if not claims_preview:
            # No relations at all — show single card with basic context data
            claims_preview = [{'claim_type': 'owner', 'person_name': '', 'unit_display_id': ''}]

        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Case-status field removed; status is backend-owned.
        source_code = _find_combo_code_by_english("ClaimSource", "Office Submission")
        _TYPE_FB = {
            "Ownership": tr("wizard.claim.type_ownership"),
            "Tenancy": tr("wizard.claim.type_tenancy"),
            "Occupancy": tr("wizard.claim.type_occupancy"),
        }

        def _fill_card(card, claim):
            person_name = claim.get('claimant_name') or claim.get('person_name', '')
            if not person_name and self.context.persons:
                fp = self.context.persons[0]
                person_name = f"{fp.get('first_name', '')} {fp.get('last_name', '')}".strip()
            card.claim_person_search.setText(person_name)

            unit_display = claim.get('unit_display_id', '')
            if not unit_display and self.context.unit:
                u = self.context.unit
                unit_display = str(u.unit_number or u.apartment_number or "")
            card.claim_unit_search.setText(unit_display)

            role = claim.get('claim_type', 'owner')
            is_owner = _is_owner_relation(role)
            if is_owner:
                claim_type_en = "Ownership"
            elif role in ('tenant', 3, 'tenancy'):
                claim_type_en = "Tenancy"
            elif role in ('occupant', 2, 'occupancy'):
                claim_type_en = "Occupancy"
            else:
                claim_type_en = "Ownership"
                is_owner = True

            code = _find_combo_code_by_english("ClaimType", claim_type_en)
            card.claim_type_field.setText(get_claim_type_display(code) if code else _TYPE_FB[claim_type_en])

            if is_owner:
                card.case_category_field.setText(tr("wizard.claim.case_closed"))
                card.case_category_field.setStyleSheet(CASE_CLOSED_FIELD_STYLE)
            else:
                card.case_category_field.setText(tr("wizard.claim.case_open"))
                card.case_category_field.setStyleSheet(CASE_OPEN_FIELD_STYLE)

            card.claim_source_field.setText(get_source_display(source_code))

            survey_date = claim.get('survey_date') or today_str
            card.claim_survey_date.setText(str(survey_date)[:10])

            notes = claim.get('notes', '')
            if notes:
                card.claim_notes.setText(notes)

            card._claim_raw_data = {'from_context': True, 'claim_preview': claim}

        # Fill first card
        _fill_card(self._claim_cards[0], claims_preview[0])

        # Create additional cards for remaining claims
        for claim in claims_preview[1:]:
            new_card = self._create_claim_card_widget()
            _fill_card(new_card, claim)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, new_card)
            self._claim_cards.append(new_card)

        # Fetch evidence count and apply to all cards
        def _apply_evidence(count):
            for c in self._claim_cards:
                self._update_evidence_label(c.claim_eval_label, count)

        self._fetch_evidence_count(callback=_apply_evidence)

        self._accent_line.pulse()

    def reset(self):
        if not self._is_initialized:
            return
        while len(self._claim_cards) > 1:
            card = self._claim_cards.pop()
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        if self._claim_cards:
            first_card = self._claim_cards[0]
            first_card.claim_person_search.clear()
            first_card.claim_unit_search.clear()
            first_card.claim_type_field.clear()
            first_card.claim_survey_date.clear()
            first_card.claim_source_field.clear()
            first_card.claim_notes.clear()
            first_card.claim_eval_label.clear()
        self.scroll_area.show()
        self.empty_state_widget.hide()

    def on_show(self):
        super().on_show()
        self._evaluate_for_claim()

    def validate(self) -> StepValidationResult:
        result = self.create_validation_result()

        if hasattr(self, 'empty_state_widget') and self.empty_state_widget.isVisible():
            return result

        if self._claim_cards:
            first_card = self._claim_cards[0]
            if not first_card.claim_type_field.text().strip():
                result.add_error(tr("wizard.claim.type_required"))

        if result.is_valid and self._claim_cards:
            self.collect_data()

        return result

    def collect_data(self) -> Dict[str, Any]:
        if hasattr(self, 'empty_state_widget') and self.empty_state_widget.isVisible():
            return {"claims": [], "claim_data": None, "no_claims_created": True}

        claims_data = []

        for card in self._claim_cards:
            claimant_ids = [r['person_id'] for r in self.context.relations
                            if _is_owner_relation(r.get('relation_type'))]

            all_evidences = []
            for rel in self.context.relations:
                all_evidences.extend(rel.get('evidences', []))

            evidence_count = len(all_evidences)
            if not evidence_count:
                evidence_count = getattr(self, '_cached_evidence_count', 0)

            raw = getattr(card, '_claim_raw_data', {}) or {}

            claim_data = {
                "claim_type": raw.get('claimType') or _find_combo_code_by_english("ClaimType", "Ownership"),
                "source": raw.get('source') or raw.get('claimSource') or _find_combo_code_by_english("ClaimSource", "Office Submission"),
                # Backend owns case_status; do not invent a local default
                # ("New") here. If the backend hasn't returned one yet, leave
                # it empty so downstream readers know it's unset.
                "case_status": raw.get('claimStatus') or raw.get('caseStatus') or "",
                "survey_date": card.claim_survey_date.text().strip() or None,
                "notes": card.claim_notes.toPlainText().strip(),
                "status": "draft",
                "person_name": card.claim_person_search.text().strip(),
                "unit_display_id": card.claim_unit_search.text().strip(),
                "claimant_person_ids": claimant_ids,
                "evidence_ids": [e['evidence_id'] for e in all_evidences],
                "evidence_count": evidence_count,
                "unit_id": self.context.unit.unit_id if self.context.unit else None,
                "building_id": self.context.building.building_id if self.context.building else None
            }
            claims_data.append(claim_data)

        self.context.claims = claims_data
        if claims_data:
            self.context.claim_data = claims_data[0]

        return {"claims": claims_data, "claim_data": claims_data[0] if claims_data else None}

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self.scroll_area.setLayoutDirection(get_layout_direction())

        for card in self._claim_cards:
            card.setLayoutDirection(get_layout_direction())
            # Retranslate field labels
            for tr_key, lbl in getattr(card, '_field_labels', {}).items():
                lbl.setText(tr(tr_key))
            # Retranslate notes label
            notes_lbl = getattr(card, '_notes_label', None)
            if notes_lbl:
                notes_lbl.setText(tr("wizard.claim.review_notes"))
            # Update placeholder texts
            card.claim_person_search.setPlaceholderText(tr("wizard.claim.person_name_placeholder"))
            card.claim_unit_search.setPlaceholderText(tr("wizard.claim.unit_number_placeholder"))
            card.claim_notes.setPlaceholderText(tr("wizard.claim.additional_notes_placeholder"))
            # Retranslate dynamic value fields (evidence pill, case category)
            eval_lbl = card.claim_eval_label
            if eval_lbl.styleSheet() == EVIDENCE_AVAILABLE_STYLE:
                text = eval_lbl.text()
                # Keep count if present: "نص (N)" → update prefix only
                import re as _re
                m = _re.search(r'\((\d+)\)', text)
                if m:
                    eval_lbl.setText(f"{tr('wizard.claim.evidence_available')} ({m.group(1)})")
                else:
                    eval_lbl.setText(tr("wizard.claim.evidence_available"))
            else:
                current = eval_lbl.text()
                # Only update if it's one of the known translatable strings (not a custom reason)
                _known = {tr("wizard.claim.awaiting_documents"), "awaiting_documents"}
                if not current or current in _known:
                    eval_lbl.setText(tr("wizard.claim.awaiting_documents"))

        # Retranslate empty state labels
        if hasattr(self, '_empty_title_label') and self._empty_title_label:
            self._empty_title_label.setText(tr("wizard.claim.empty_title"))
        if hasattr(self, '_empty_desc_label') and self._empty_desc_label:
            self._empty_desc_label.setText(tr("wizard.claim.empty_desc"))

    def get_step_title(self) -> str:
        return tr("wizard.claim.step_title")

    def get_step_description(self) -> str:
        return tr("wizard.claim.step_description")
