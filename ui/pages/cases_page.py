# -*- coding: utf-8 -*-
"""
Surveys Page v2 — Dark navy header with constellation, navbar-style tabs,
animated shimmer cards, pagination, and cohesive blue palette.
Displays Draft & Finalized office surveys.
"""

import logging
import math
import random
import time
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QLineEdit, QPushButton,
    QSizePolicy, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QStackedWidget,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QTimer, QRectF, QPoint, QSize,
    QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient, QPen,
    QPainterPath, QCursor,
)

from ui.design_system import Colors, PageDimensions, Spacing, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.nav_style_tab import NavStyleTab
from ui.components.accent_line import AccentLine
from ui.components.dark_header_zone import DarkHeaderZone
from services.translation_manager import tr, get_layout_direction, get_language
from services.display_mappings import get_survey_type_display
from services.api_worker import ApiWorker
from ui.components.toast import Toast
from ui.components.empty_state import EmptyState

logger = logging.getLogger(__name__)

_STATUS_STYLES = {
    "draft":      {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74", "glow": "rgba(194, 65, 12, 0.12)"},
    "finalized":  {"bg": "#EBF5FF", "fg": "#0369A1", "border": "#7DD3FC", "glow": "rgba(3, 105, 161, 0.10)"},
    "obstructed": {"bg": "#FFFBEB", "fg": "#B45309", "border": "#FCD34D", "glow": "rgba(180, 83, 9, 0.12)"},
}

_DARK_INPUT_STYLE = """
    QLineEdit {
        background: rgba(10, 22, 40, 140);
        color: white;
        border: 1px solid rgba(56, 144, 223, 35);
        border-radius: 8px;
        padding: 0 12px 0 34px;
    }
    QLineEdit:focus {
        border: 1.5px solid rgba(56, 144, 223, 140);
        background: rgba(10, 22, 40, 180);
    }
    QLineEdit::placeholder {
        color: rgba(139, 172, 200, 130);
    }
"""

_ADD_BTN_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
        color: white;
        border: 1px solid rgba(120, 190, 255, 0.35);
        border-radius: 10px;
        padding: 0 24px;
        font-weight: 700;
        font-size: 13pt;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.55);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #3890DF, stop:0.5 #2E7BD6, stop:1 #266FC0);
        border: 1px solid rgba(100, 170, 240, 0.25);
    }
"""

_NAV_BTN_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #FAFBFF, stop:1 #F0F4FA);
        border: 1px solid rgba(56, 144, 223, 0.20);
        border-radius: 8px; color: #3890DF;
        padding: 0 10px; font-weight: 600;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #EBF5FF, stop:1 #E0EDFA);
        border-color: rgba(56, 144, 223, 0.40);
    }
    QPushButton:pressed {
        background: #E0EDFA;
    }
    QPushButton:disabled {
        color: #C0C8D0;
        background: #F5F7FA;
        border-color: #E8ECF0;
    }
"""


# ---------------------------------------------------------------------------
#  _SurveyCard — Card with blue tint, animated shimmer, hover lift, chevron
# ---------------------------------------------------------------------------

class _SurveyCard(QFrame):
    """Survey card with blue-tinted background, animated shimmer sweep,
    prominent hover effects, and directional chevron."""

    clicked = pyqtSignal(str)

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

    def __init__(self, card_data: Dict, parent=None):
        super().__init__(parent)
        self._claim_id = card_data.get("claim_id", "")
        self._claim_uuid = card_data.get("claim_uuid", "")
        self._status = card_data.get("status", "draft")
        self._hovered = False
        self._pressed = False
        self._badge = None
        self._entrance_anim = None
        self._entrance_effect = None
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(ScreenScale.h(110))
        self.setMouseTracking(True)
        self._build_ui(card_data)

    def _build_ui(self, d: Dict):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            _SurveyCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG}, stop:1 #F0F5FF);
                border-radius: 14px;
                border: 1px solid #E2EAF2;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 22))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 20, 0)
        outer.setSpacing(0)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(20, 14, 0, 14)
        content.setSpacing(4)

        # Row 1: contact person name + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        name_label = QLabel(d.get("claimant_name", "-"))
        name_label.setFont(create_font(size=13, weight=QFont.Bold))
        name_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        name_label.setMaximumWidth(ScreenScale.w(600))
        row1.addWidget(name_label)
        row1.addStretch()

        status_text = self._get_status_text(self._status)
        style = _STATUS_STYLES.get(self._status, _STATUS_STYLES["draft"])
        badge = QLabel(status_text)
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(22))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 11px; "
            f"padding: 0 10px; }}"
        )
        self._badge = badge
        row1.addWidget(badge)
        content.addLayout(row1)

        # Row 2: reference code
        ref_label = QLabel(d.get("claim_id", "N/A"))
        id_font = create_font(size=9, weight=FontManager.WEIGHT_MEDIUM)
        id_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)
        ref_label.setFont(id_font)
        ref_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        content.addWidget(ref_label)

        content.addSpacing(4)

        # Row 3: info chips (building, source, date)
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)

        chip_style = (
            "QLabel {{ background-color: {bg}; color: {fg}; "
            "border: 1px solid {border}; border-radius: 4px; "
            "padding: 2px 8px; }}"
        )

        building_id = d.get("building_id", "")
        if building_id:
            chip = QLabel(building_id)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(
                bg="#F0F4FA", fg="#475569", border="#E2E8F0"
            ))
            chips_row.addWidget(chip)

        source_label = d.get("source_label", "")
        if source_label:
            chip = QLabel(source_label)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(
                bg="#EEF2FF", fg="#4338CA", border="#E0E7FF"
            ))
            chips_row.addWidget(chip)

        date_str = d.get("date", "")
        if date_str and not date_str.startswith("0001"):
            chip = QLabel(date_str)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(
                bg="#F0FDF4", fg="#15803D", border="#DCFCE7"
            ))
            chips_row.addWidget(chip)

        chips_row.addStretch()
        content.addLayout(chips_row)

        outer.addLayout(content, 1)

    def _get_status_text(self, status: str) -> str:
        key_map = {
            "draft": "page.cases.tab_draft",
            "finalized": "page.cases.tab_finalized",
            "obstructed": "page.cases.tab_obstructed",
        }
        return tr(key_map.get(status, "page.cases.tab_draft"))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time()

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 13, 13)
        painter.setClipPath(clip)

        # Subtle cartographic grid pattern
        painter.setPen(QPen(QColor(56, 144, 223, 5), 0.5))
        for gx in range(0, w + 60, 60):
            painter.drawLine(gx, 0, gx, h)
        for gy in range(0, h + 60, 60):
            painter.drawLine(0, gy, w, gy)

        # Animated blue shimmer sweep
        sweep_pos = (math.sin(t * 0.6 + self._shimmer_offset) + 1) / 2
        sweep_x = int(sweep_pos * w)
        shimmer_grad = QLinearGradient(sweep_x - 150, 0, sweep_x + 150, 0)
        shimmer_grad.setColorAt(0, QColor(56, 144, 223, 0))
        shimmer_grad.setColorAt(0.5, QColor(120, 190, 255, 10))
        shimmer_grad.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.fillRect(QRectF(0, 0, w, h), shimmer_grad)

        # Top edge accent on hover
        if self._hovered:
            top_grad = QLinearGradient(0, 0, w, 0)
            top_grad.setColorAt(0, QColor(56, 144, 223, 0))
            top_grad.setColorAt(0.2, QColor(56, 144, 223, 40))
            top_grad.setColorAt(0.5, QColor(91, 168, 240, 65))
            top_grad.setColorAt(0.8, QColor(56, 144, 223, 40))
            top_grad.setColorAt(1, QColor(56, 144, 223, 0))
            painter.fillRect(QRectF(0, 0, w, 2.5), top_grad)

        painter.setClipping(False)

        # Chevron arrow (RTL-aware) with smooth opacity
        is_rtl = self.layoutDirection() == Qt.RightToLeft
        chevron_x = 16 if is_rtl else w - 24
        chevron_alpha = 160 if self._hovered else 40
        painter.setPen(QPen(QColor(56, 144, 223, chevron_alpha), 1.8,
                            Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cy = h / 2
        if is_rtl:
            painter.drawLine(int(chevron_x + 6), int(cy - 5), int(chevron_x), int(cy))
            painter.drawLine(int(chevron_x), int(cy), int(chevron_x + 6), int(cy + 5))
        else:
            painter.drawLine(int(chevron_x), int(cy - 5), int(chevron_x + 6), int(cy))
            painter.drawLine(int(chevron_x + 6), int(cy), int(chevron_x), int(cy + 5))

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
            _SurveyCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG_HOVER}, stop:1 #E8F0FE);
                border-radius: 14px;
                border: 1.5px solid rgba(56, 144, 223, 0.30);
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(36)
            eff.setOffset(0, 8)
            eff.setColor(QColor(56, 144, 223, 40))
        self._animate_lift(4.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.setStyleSheet(f"""
            _SurveyCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._CARD_BG}, stop:1 #F0F5FF);
                border-radius: 14px;
                border: 1px solid #E2EAF2;
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(20)
            eff.setOffset(0, 4)
            eff.setColor(QColor(0, 0, 0, 22))
        self._animate_lift(0.0)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            eff = self.graphicsEffect()
            if isinstance(eff, QGraphicsDropShadowEffect):
                eff.setBlurRadius(8)
                eff.setOffset(0, 1)
                eff.setColor(QColor(0, 0, 0, 18))
            if self._claim_id:
                self.clicked.emit(self._claim_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            if self._hovered:
                eff = self.graphicsEffect()
                if isinstance(eff, QGraphicsDropShadowEffect):
                    eff.setBlurRadius(32)
                    eff.setOffset(0, 8)
                    eff.setColor(QColor(56, 144, 223, 35))
            else:
                eff = self.graphicsEffect()
                if isinstance(eff, QGraphicsDropShadowEffect):
                    eff.setBlurRadius(20)
                    eff.setOffset(0, 4)
                    eff.setColor(QColor(0, 0, 0, 22))
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
#  _EmptyStateAnimated — Light professional empty state
# ---------------------------------------------------------------------------

class _EmptyStateAnimated(QWidget):
    """Light-themed institutional empty state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = EmptyState(
            icon_name="folder",
            title=tr("page.cases.no_drafts"),
            description=tr("page.cases.empty_description"),
        )
        layout.addWidget(self._inner, 0, Qt.AlignCenter)

    def set_title(self, text: str):
        self._inner.set_title(text)

    def set_description(self, text: str):
        self._inner.set_description(text)


# ---------------------------------------------------------------------------
#  CasesPage — Main page widget
# ---------------------------------------------------------------------------

class CasesPage(QWidget):
    """Surveys listing page with dark header zone, shimmer cards,
    pagination, and comprehensive loading states."""

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()
    survey_finalized = pyqtSignal(str)
    resume_survey = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._all_data: List[Dict] = []
        self._active_tab = "draft"
        self._buildings_cache: Dict[str, object] = {}
        self._last_refresh_ms = 0
        self._draft_count = 0
        self._finalized_count = 0
        self._obstructed_count = 0
        self._card_widgets: List[_SurveyCard] = []
        self._loading = False
        self._navigating = False
        self._worker = None
        self._current_page = 1
        self._total_count = 0
        self._page_size = 20
        self._user_role = None
        self._user_id = None
        self._search_mode = False
        self._tabs_visibility = {}

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._load_surveys)

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    # -- UI Setup --

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("cases.page.title"))

        # Add button in header actions
        self._add_btn = QPushButton(tr("wizard.button.add_case"))
        self._add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._add_btn.setFixedHeight(ScreenScale.h(42))
        self._add_btn.setMinimumWidth(ScreenScale.w(150))
        self._add_btn.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        self._add_btn.setStyleSheet(_ADD_BTN_STYLE)
        self._add_btn.clicked.connect(self.add_claim_clicked.emit)
        self._header.add_action_widget(self._add_btn)

        # Tabs (row 2)
        tab_font = create_font(size=12, weight=QFont.DemiBold)

        self._tab_draft = NavStyleTab(tr("page.cases.tab_draft"))
        self._tab_draft.setFixedSize(ScreenScale.w(130), ScreenScale.h(38))
        self._tab_draft.set_font(tab_font)
        self._tab_draft.set_active(True)
        self._tab_draft.clicked.connect(lambda: self._on_tab("draft"))
        self._header.add_tab(self._tab_draft)

        self._tab_finalized = NavStyleTab(tr("page.cases.tab_finalized"))
        self._tab_finalized.setFixedSize(ScreenScale.w(130), ScreenScale.h(38))
        self._tab_finalized.set_font(tab_font)
        self._tab_finalized.set_active(False)
        self._tab_finalized.clicked.connect(lambda: self._on_tab("finalized"))
        self._header.add_tab(self._tab_finalized)

        self._tab_obstructed = NavStyleTab(tr("page.cases.tab_obstructed"))
        self._tab_obstructed.setFixedSize(ScreenScale.w(130), ScreenScale.h(38))
        self._tab_obstructed.set_font(tab_font)
        self._tab_obstructed.set_active(False)
        self._tab_obstructed.setVisible(False)
        self._tab_obstructed.clicked.connect(lambda: self._on_tab("obstructed"))
        self._header.add_tab(self._tab_obstructed)

        # Search field (row 1)
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("page.claims.search_reference_code"))
        self._search.setFixedSize(ScreenScale.w(280), ScreenScale.h(34))
        self._search.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._search.setStyleSheet(_DARK_INPUT_STYLE)
        search_icon = Icon.load_pixmap("search", 16)
        if search_icon and not search_icon.isNull():
            icon_label = QLabel(self._search)
            icon_label.setPixmap(search_icon)
            icon_label.setFixedSize(ScreenScale.w(16), ScreenScale.h(16))
            icon_label.move(10, 9)
            icon_label.setStyleSheet("background: transparent; border: none;")
        self._search.textChanged.connect(self._on_search_changed)
        self._search.returnPressed.connect(self._on_search_submitted)
        self._header.add_action_widget(self._search)

        main.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        main.addWidget(self._accent_line)

        # Light content area
        self._content_wrapper = QWidget()
        self._content_wrapper.setStyleSheet("background-color: white;")
        content_layout = QVBoxLayout(self._content_wrapper)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        content_layout.setSpacing(0)

        # Stacked widget: cards vs empty
        self._stack = QStackedWidget()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)

        self._empty_state = _EmptyStateAnimated()
        self._stack.addWidget(self._empty_state)

        self._results_bar = self._build_results_bar()
        content_layout.addWidget(self._results_bar)
        self._results_bar.hide()
        content_layout.addWidget(self._stack, 1)

        self._pagination = self._create_pagination()
        content_layout.addWidget(self._pagination)

        main.addWidget(self._content_wrapper, 1)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_pagination(self):
        bar = QFrame()
        bar.setFixedHeight(ScreenScale.h(40))
        bar.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 6, 4, 0)
        layout.addStretch()

        self._prev_btn = QPushButton("\u276E")
        self._prev_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prev_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._prev_btn.clicked.connect(self._on_prev_page)
        layout.addWidget(self._prev_btn)

        self._page_info = QLabel("")
        self._page_info.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._page_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._page_info.setAlignment(Qt.AlignCenter)
        self._page_info.setMinimumWidth(ScreenScale.w(80))
        layout.addWidget(self._page_info)

        self._next_btn = QPushButton("\u276F")
        self._next_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._next_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._next_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_btn)

        return bar

    # -- Role-based configuration --

    def configure_for_user(self, role: str, user_id: str):
        """Set user context for filtering surveys by ownership."""
        self._user_role = role
        self._user_id = user_id
        self._all_data = []
        self._buildings_cache = {}
        self._clear_cards()

        if role == "admin":
            self._tab_draft.setVisible(False)
            self._tab_finalized.setVisible(False)
            self._tab_obstructed.setVisible(True)
            self._active_tab = "finalized"
            self._tab_draft.set_active(False)
            self._tab_finalized.set_active(True)
            self._tab_obstructed.set_active(False)
            self._add_btn.setVisible(False)
        elif role == "data_manager":
            self._tab_draft.setVisible(True)
            self._tab_finalized.setVisible(True)
            self._tab_obstructed.setVisible(True)
            self._active_tab = "draft"
            self._tab_draft.set_active(True)
            self._tab_finalized.set_active(False)
            self._tab_obstructed.set_active(False)
            self._add_btn.setVisible(True)
        elif role == "field_supervisor":
            self._tab_draft.setVisible(True)
            self._tab_finalized.setVisible(True)
            self._tab_obstructed.setVisible(True)
            self._active_tab = "draft"
            self._tab_draft.set_active(True)
            self._tab_finalized.set_active(False)
            self._tab_obstructed.set_active(False)
            self._add_btn.setVisible(True)
        elif role == "office_clerk":
            self._tab_draft.setVisible(True)
            self._tab_finalized.setVisible(True)
            self._tab_obstructed.setVisible(False)
            self._active_tab = "draft"
            self._tab_draft.set_active(True)
            self._tab_finalized.set_active(False)
            self._tab_obstructed.set_active(False)
            self._add_btn.setVisible(True)
        else:
            self._tab_draft.setVisible(True)
            self._tab_finalized.setVisible(True)
            self._tab_obstructed.setVisible(False)
            self._tab_draft.set_active(True)
            self._tab_finalized.set_active(False)
            self._tab_obstructed.set_active(False)
            self._add_btn.setVisible(True)

    # -- Tab & filter handlers --

    def _on_tab(self, which: str):
        if self._loading or which == self._active_tab:
            return
        self._active_tab = which
        self._current_page = 1
        self._tab_draft.set_active(which == "draft")
        self._tab_finalized.set_active(which == "finalized")
        self._tab_obstructed.set_active(which == "obstructed")
        self._accent_line.pulse()
        self._load_surveys()

    def _on_search_changed(self):
        # Exit search mode when text is cleared — no auto-search timer
        if not self._search.text().strip() and self._search_mode:
            self._exit_search_mode()

    def _on_search_submitted(self):
        """Triggered on Enter — enters search mode and loads results."""
        self._current_page = 1
        name = self._search.text().strip()
        if name:
            self._enter_search_mode()
            self._load_surveys()
        else:
            self._exit_search_mode()

    def _enter_search_mode(self):
        if self._search_mode:
            return
        self._search_mode = True
        self._tabs_visibility = {
            "draft": self._tab_draft.isVisible(),
            "finalized": self._tab_finalized.isVisible(),
            "obstructed": self._tab_obstructed.isVisible(),
        }
        self._tab_draft.hide()
        self._tab_finalized.hide()
        self._tab_obstructed.hide()
        self._results_bar.show()

    def _exit_search_mode(self):
        if not self._search_mode:
            return
        self._search_mode = False
        self._tab_draft.setVisible(self._tabs_visibility.get("draft", True))
        self._tab_finalized.setVisible(self._tabs_visibility.get("finalized", True))
        self._tab_obstructed.setVisible(self._tabs_visibility.get("obstructed", True))
        self._results_bar.hide()
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._current_page = 1
        self._load_surveys()

    def _build_results_bar(self):
        bar = QFrame()
        bar.setFixedHeight(ScreenScale.h(44))
        bar.setStyleSheet(
            "QFrame { background: rgba(56, 144, 223, 0.07);"
            " border-radius: 8px; border: 1px solid rgba(56, 144, 223, 0.15);"
            " margin-bottom: 10px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)
        self._back_btn = QPushButton("رجوع")
        self._back_btn.setFixedSize(ScreenScale.w(80), ScreenScale.h(30))
        self._back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._back_btn.setStyleSheet(
            "QPushButton { background: rgba(56, 144, 223, 0.15);"
            " border: 1px solid rgba(56, 144, 223, 0.3); border-radius: 6px;"
            " color: #3890DF; font-weight: 600; font-size: 12px; }"
            " QPushButton:hover { background: rgba(56, 144, 223, 0.25); }"
        )
        self._back_btn.clicked.connect(self._exit_search_mode)
        layout.addWidget(self._back_btn)
        self._results_title = QLabel("نتائج البحث")
        self._results_title.setStyleSheet(
            "color: #1E3A5F; font-weight: 700; font-size: 14px;"
            " background: transparent; border: none;"
        )
        layout.addWidget(self._results_title)
        layout.addStretch()
        return bar

    # -- Pagination --

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_surveys()

    def _on_next_page(self):
        total_pages = max(1, -(-self._total_count // self._page_size))
        if self._current_page < total_pages:
            self._current_page += 1
            self._load_surveys()

    def _update_pagination(self):
        total = self._total_count
        ps = self._page_size
        total_pages = max(1, -(-total // ps))
        page = self._current_page
        start = (page - 1) * ps + 1
        end = min(page * ps, total)
        if total > 0:
            self._page_info.setText(f"{start}-{end}  /  {total}")
        else:
            self._page_info.setText("")
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < total_pages)

    # -- Tab labels with counts --

    def _update_tab_labels(self):
        self._tab_draft.set_text(tr("page.cases.tab_draft"))
        self._tab_finalized.set_text(tr("page.cases.tab_finalized"))
        self._tab_obstructed.set_text(tr("page.cases.tab_obstructed"))

    # -- Data loading --

    def refresh(self, data=None):
        self._navigating = False
        self._last_refresh_ms = int(time.time() * 1000)
        self._load_surveys()

    def _load_surveys(self):
        if self._loading:
            return
        self._loading = True
        self._spinner.show_loading(tr("page.cases.loading"))

        if self._active_tab == "draft":
            status = "Draft"
        elif self._active_tab == "obstructed":
            status = "Obstructed"
        else:
            status = "Finalized"
        name = self._search.text().strip() if self._search_mode else None
        clerk_id = self._user_id if self._user_role == "office_clerk" else None

        self._worker = ApiWorker(
            self._fetch_surveys_data, status, name, clerk_id
        )
        self._worker.finished.connect(self._on_surveys_loaded)
        self._worker.error.connect(self._on_surveys_load_error)
        self._worker.start()

    def _fetch_surveys_data(self, status, name, clerk_id):
        from services.api_client import get_api_client
        from controllers.building_controller import BuildingController

        api = get_api_client()
        total_count = 0

        # Fetch paginated surveys
        try:
            params = {
                "page": self._current_page,
                "pageSize": self._page_size,
                "sortBy": "SurveyDate",
                "sortDirection": "desc",
            }
            if name:
                params["referenceCode"] = name
                # No status filter — search across all statuses
            else:
                params["status"] = status
            if clerk_id:
                params["clerkId"] = clerk_id

            raw = api._request("GET", "/v1/Surveys/office", params=params)
            if isinstance(raw, dict):
                surveys = raw.get("surveys", [])
                total_count = raw.get("totalCount", len(surveys))
            else:
                surveys = raw if isinstance(raw, list) else []
                total_count = len(surveys)
        except Exception as e:
            logger.warning(f"Paginated surveys fetch failed: {e}")
            surveys = []

        # Fetch counts for stat pills
        draft_count = 0
        finalized_count = 0
        obstructed_count = 0
        for st, key in [("Draft", "draft"), ("Finalized", "finalized"), ("Obstructed", "obstructed")]:
            try:
                count_params = {"status": st, "page": 1, "pageSize": 1}
                if clerk_id:
                    count_params["clerkId"] = clerk_id
                raw_count = api._request("GET", "/v1/Surveys/office", params=count_params)
                count_val = raw_count.get("totalCount", 0) if isinstance(raw_count, dict) else 0
                if key == "draft":
                    draft_count = count_val
                elif key == "finalized":
                    finalized_count = count_val
                else:
                    obstructed_count = count_val
            except Exception:
                pass

        # Building enrichment
        new_buildings = {}
        building_ids = {s.get("buildingId", "") for s in surveys if s.get("buildingId")}
        if building_ids:
            try:
                bc = BuildingController(self.db)
                for bid in building_ids:
                    if not bid or bid in self._buildings_cache:
                        continue
                    try:
                        dto = api.get_building_by_id(bid)
                        new_buildings[bid] = bc._api_dto_to_building(dto)
                    except Exception:
                        pass
            except Exception:
                pass

        return {
            "surveys": surveys,
            "new_buildings": new_buildings,
            "status": status,
            "draft_count": draft_count,
            "finalized_count": finalized_count,
            "obstructed_count": obstructed_count,
            "total_count": total_count,
        }

    def _on_surveys_loaded(self, result):
        try:
            self._buildings_cache.update(result.get("new_buildings", {}))
            self._draft_count = result.get("draft_count", 0)
            self._finalized_count = result.get("finalized_count", 0)
            self._obstructed_count = result.get("obstructed_count", 0)
            self._total_count = result.get("total_count", 0)

            surveys = result.get("surveys", [])
            self._all_data = [self._map_survey(s) for s in surveys]

            logger.info(f"Loaded {len(self._all_data)} surveys (status={result.get('status')})")
            self._populate_cards(self._all_data)
            self._update_tab_labels()
            self._update_pagination()
            if self._search_mode:
                total = result.get("total_count", 0)
                self._results_title.setText(f"نتائج البحث ({total} نتيجة)")
        except Exception as e:
            logger.error(f"Error processing surveys: {e}")
            self._all_data = []
            self._populate_cards(self._all_data)
        finally:
            self._loading = False
            self._spinner.hide_loading()

    def _on_surveys_load_error(self, error_msg):
        self._loading = False
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.cases.load_error"), Toast.ERROR)
        logger.warning(f"Error loading surveys: {error_msg}")
        self._all_data = []
        self._populate_cards(self._all_data)

    def _map_survey(self, s: Dict) -> Dict:
        building_id = s.get("buildingId", "")
        building_obj = self._buildings_cache.get(building_id)

        unit_num = s.get("unitIdentifier", "")
        unit_obj = None
        if unit_num:
            class _NS:
                def __init__(self, **kw): self.__dict__.update(kw)
            unit_obj = _NS(unit_number=unit_num)

        return {
            "claim_id": s.get("referenceCode") or s.get("id", "N/A"),
            "claim_uuid": s.get("id", ""),
            "claimant_name": s.get("contactPersonFullName") or s.get("intervieweeName") or tr("page.cases.unspecified"),
            "date": (s.get("surveyDate") or "")[:10],
            "status": self._active_tab,
            "building_id": s.get("buildingNumber") or (building_obj.building_id if building_obj else ""),
            "unit_number": unit_num,
            "source_label": get_survey_type_display(s.get("surveyType", 0)),
            "survey_type": s.get("surveyType"),
            "building": building_obj,
            "unit": unit_obj,
            "unit_id": s.get("propertyUnitId", ""),
        }

    # -- Card population --

    def _populate_cards(self, data: List[Dict]):
        try:
            self._clear_cards()

            if not data:
                self._stack.setCurrentIndex(1)
                self._update_empty_text()
                self._update_pagination()
                return

            self._stack.setCurrentIndex(0)

            for item in data:
                card = _SurveyCard(item)
                card.clicked.connect(self._on_card_clicked)
                self._cards_layout.insertWidget(
                    self._cards_layout.count() - 1, card
                )
                self._card_widgets.append(card)

            self._update_pagination()
            self._animate_card_entrance()

            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()
        except Exception as e:
            logger.error(f"Error populating cards: {e}")
            self._stack.setCurrentIndex(1)
            self._update_empty_text()

    def _animate_card_entrance(self):
        count = len(self._card_widgets)
        if count > 20 or count == 0:
            return

        for i, card in enumerate(self._card_widgets):
            opacity_eff = QGraphicsOpacityEffect(card)
            opacity_eff.setOpacity(0.0)
            card.setGraphicsEffect(opacity_eff)

            anim = QPropertyAnimation(opacity_eff, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _restore_shadow(c=card):
                try:
                    s = QGraphicsDropShadowEffect(c)
                    s.setBlurRadius(20)
                    s.setOffset(0, 4)
                    s.setColor(QColor(0, 0, 0, 22))
                    c.setGraphicsEffect(s)
                except RuntimeError:
                    pass

            anim.finished.connect(_restore_shadow)
            QTimer.singleShot(i * 40, anim.start)

            card._entrance_anim = anim
            card._entrance_effect = opacity_eff

    def _clear_cards(self):
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            if hasattr(card, '_entrance_anim') and card._entrance_anim:
                try:
                    card._entrance_anim.stop()
                except RuntimeError:
                    pass
            try:
                card.clicked.disconnect()
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_card_shimmer(self):
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    def _update_empty_text(self):
        if self._active_tab == "draft":
            msg = tr("page.cases.no_drafts")
        elif self._active_tab == "obstructed":
            msg = tr("page.cases.no_obstructed")
        else:
            msg = tr("page.cases.no_finalized")
        self._empty_state.set_title(msg)
        self._empty_state.set_description(tr("page.cases.empty_description"))

    # -- Card click --

    def _on_card_clicked(self, claim_id: str):
        if self._navigating or not claim_id:
            return
        self._navigating = True
        self._spinner.show_loading(tr("page.cases.loading"))
        self.claim_selected.emit(claim_id)

    # -- Public interface (backward compatibility) --

    def search_claims(self, query: str, mode: str = "name"):
        pass

    def apply_filters(self, filters: dict):
        pass

    def update_language(self, is_arabic=True):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        self._header.get_title_label().setText(tr("cases.page.title"))
        self._search.setPlaceholderText(tr("page.claims.search_reference_code"))
        self._add_btn.setText(tr("wizard.button.add_case"))

        self._update_tab_labels()

        self._scroll.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)

        if self._all_data:
            self._populate_cards(self._all_data)
        else:
            self._update_empty_text()
