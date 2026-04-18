# -*- coding: utf-8 -*-
"""
Case Management Page -- Dark navy header with constellation, navbar-style tabs,
animated shimmer cards, pagination, and cohesive blue palette.
Displays Open & Closed cases for a property registration system.
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
    QGraphicsOpacityEffect, QStackedWidget, QGridLayout,
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
from ui.components.nav_style_tab import NavStyleTab
from ui.components.accent_line import AccentLine
from ui.components.dark_header_zone import DarkHeaderZone
from app.config import Pages
from ui.components.toast import Toast
from ui.components.empty_state import EmptyState
from services.translation_manager import get_layout_direction, tr
from services.api_worker import ApiWorker
from ui.components.icon import Icon
from models.case import Case

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Status style maps
# ---------------------------------------------------------------------------

_CASE_STATUS_STYLES = {
    1: {  # Open
        "bg": "#ECFDF5", "fg": "#059669", "border": "#6EE7B7",
        "glow": "rgba(5, 150, 105, 0.12)", "label_key": "page.case_mgmt.status_open",
        "strip": "#059669",
    },
    2: {  # Closed
        "bg": "#FEF2F2", "fg": "#DC2626", "border": "#FECACA",
        "glow": "rgba(220, 38, 38, 0.12)", "label_key": "page.case_mgmt.status_closed",
        "strip": "#DC2626",
    },
}


# ---------------------------------------------------------------------------
#  Dark input style (matches DarkHeaderZone)
# ---------------------------------------------------------------------------

_DARK_INPUT_STYLE = """
    QLineEdit {
        background: rgba(10, 22, 40, 140);
        color: white;
        border: 1px solid rgba(56, 144, 223, 35);
        border-radius: 8px;
        padding: 0 12px 0 12px;
    }
    QLineEdit:focus {
        border: 1.5px solid rgba(56, 144, 223, 140);
        background: rgba(10, 22, 40, 180);
    }
    QLineEdit::placeholder {
        color: rgba(139, 172, 200, 130);
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
#  Stat pill helper
# ---------------------------------------------------------------------------

def _make_stat_pill(label: str, value: int, bg: str, fg: str, border: str) -> QLabel:
    pill = QLabel(f"  {label}: {value}  ")
    pill.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
    pill.setAlignment(Qt.AlignCenter)
    pill.setFixedHeight(ScreenScale.h(26))
    pill.setStyleSheet(
        f"QLabel {{ background: {bg}; color: {fg}; "
        f"border: 1px solid {border}; border-radius: 13px; "
        f"padding: 0 12px; }}"
    )
    return pill


# ---------------------------------------------------------------------------
#  _CaseCard -- Shimmer card for a single Case
# ---------------------------------------------------------------------------

class _CaseCard(QFrame):
    """Case card with blue-tinted background, animated shimmer sweep,
    prominent hover effects, and directional chevron."""

    clicked = pyqtSignal(str)  # case_id

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

    def __init__(self, case: Case, parent=None):
        super().__init__(parent)
        self._case = case
        self._case_id = case.id
        self._status = case.status
        self._hovered = False
        self._pressed = False
        self._entrance_anim = None
        self._entrance_effect = None
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(ScreenScale.h(120))
        self.setMouseTracking(True)
        self._build_ui()

    def _build_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            _CaseCard {{
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

        # Content area
        content = QVBoxLayout()
        content.setContentsMargins(20, 10, 0, 10)
        content.setSpacing(4)

        # Row 1: case number + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        case_number_text = self._case.case_number or self._case.id[:16]
        name_label = QLabel(case_number_text)
        name_label.setFont(create_font(size=14, weight=QFont.Bold))
        name_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        name_label.setMaximumWidth(ScreenScale.w(600))
        row1.addWidget(name_label)
        row1.addStretch()

        style = _CASE_STATUS_STYLES.get(self._status, _CASE_STATUS_STYLES[1])
        badge = QLabel(tr(style["label_key"]))
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(22))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 11px; "
            f"padding: 0 10px; }}"
        )
        row1.addWidget(badge)
        content.addLayout(row1)

        # Row 2: opened date
        opened_str = ""
        if self._case.opened_date:
            opened_str = self._case.opened_date[:10]
        if opened_str and not opened_str.startswith("0001"):
            date_label = QLabel(tr("page.case_mgmt.opened_date", date=opened_str))
        else:
            date_label = QLabel("")
        date_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        date_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        content.addWidget(date_label)

        content.addSpacing(4)

        # Row 3: chips (survey count, claim count) + lock icon
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)

        chip_style_tpl = (
            "QLabel {{ background-color: {bg}; color: {fg}; "
            "border: 1px solid {border}; border-radius: 4px; "
            "padding: 2px 8px; }}"
        )

        # Survey count chip (blue)
        survey_chip = QLabel(tr("page.case_mgmt.chip_surveys", count=self._case.survey_count))
        survey_chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
        survey_chip.setStyleSheet(chip_style_tpl.format(
            bg="#EBF5FF", fg="#0369A1", border="#BAE6FD"
        ))
        chips_row.addWidget(survey_chip)

        # Claim count chip (purple)
        claim_chip = QLabel(tr("page.case_mgmt.chip_claims", count=self._case.claim_count))
        claim_chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
        claim_chip.setStyleSheet(chip_style_tpl.format(
            bg="#F3E8FF", fg="#7C3AED", border="#DDD6FE"
        ))
        chips_row.addWidget(claim_chip)

        chips_row.addStretch()

        # Lock icon if not editable
        if not self._case.is_editable:
            lock_label = QLabel("\U0001F512")
            lock_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            lock_label.setStyleSheet("background: transparent; border: none;")
            lock_label.setToolTip(tr("page.case_mgmt.not_editable"))
            chips_row.addWidget(lock_label)

        content.addLayout(chips_row)

        outer.addLayout(content, 1)

    # -- Paint: shimmer + top accent + chevron --

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

    # -- Hover / lift animations --

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
            _CaseCard {{
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
            _CaseCard {{
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
            if self._case_id:
                self.clicked.emit(self._case_id)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            eff = self.graphicsEffect()
            if isinstance(eff, QGraphicsDropShadowEffect):
                if self._hovered:
                    eff.setBlurRadius(36)
                    eff.setOffset(0, 8)
                    eff.setColor(QColor(56, 144, 223, 40))
                else:
                    eff.setBlurRadius(20)
                    eff.setOffset(0, 4)
                    eff.setColor(QColor(0, 0, 0, 22))
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
#  _EmptyStateCases -- Light professional empty state
# ---------------------------------------------------------------------------

class _EmptyStateCases(QWidget):
    """Light-themed institutional empty state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        self._inner = EmptyState(
            icon_name="folder",
            title=tr("page.case_mgmt.empty_title"),
            description=tr("page.case_mgmt.empty_desc"),
        )
        layout.addWidget(self._inner, 0, Qt.AlignCenter)

    def set_title(self, text: str):
        self._inner.set_title(text)

    def set_description(self, text: str):
        self._inner.set_description(text)


# ---------------------------------------------------------------------------
#  CaseManagementPage -- Main page widget
# ---------------------------------------------------------------------------

class CaseManagementPage(QWidget):
    """Case management listing page with dark header zone, shimmer cards,
    pagination, and comprehensive loading states."""

    case_selected = pyqtSignal(str)  # case_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._api = None
        self._auth_token = None
        self._user_role = "admin"
        self._cases: List[Case] = []
        self._current_filter: Optional[int] = None  # None=all, 1=Open, 2=Closed
        self._current_page = 1
        self._page_size = 20
        self._total_count = 0
        self._open_count = 0
        self._closed_count = 0
        self._search_text = ""
        self._card_widgets: List[_CaseCard] = []
        self._loading = False
        self._navigating = False
        self._worker = None

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._build_ui()

    # -- Public API --

    def configure_for_user(self, role: str, token: str = None):
        """Set user context (role & auth token)."""
        self._user_role = role
        if token:
            self._auth_token = token

    def refresh(self, data=None):
        """Load/reload data from the API."""
        self._navigating = False
        self._load_cases()

    def update_language(self, is_arabic=True):
        """Re-apply RTL direction and refresh label text."""
        direction = get_layout_direction()
        self.setLayoutDirection(direction)
        self._header.get_title_label().setText(tr("page.case_mgmt.title"))
        self._search.setPlaceholderText(tr("page.case_mgmt.search_placeholder"))
        self._scroll.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)
        self._update_tab_labels()
        if self._cases:
            self._populate_cards(self._cases)
        else:
            self._update_empty_text()

    # -- UI Setup --

    def _build_ui(self):
        self.setStyleSheet("background: transparent;")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.case_mgmt.title"))
        self._header.set_help(Pages.CASE_MANAGEMENT)

        # Stat pills
        self._pill_total = _make_stat_pill(
            tr("page.case_mgmt.pill_total"), 0,
            "rgba(255,255,255,0.12)", "#FFFFFF", "rgba(255,255,255,0.20)"
        )
        self._pill_open = _make_stat_pill(
            tr("page.case_mgmt.pill_open"), 0,
            "rgba(5,150,105,0.15)", "#6EE7B7", "rgba(110,231,183,0.30)"
        )
        self._pill_closed = _make_stat_pill(
            tr("page.case_mgmt.pill_closed"), 0,
            "rgba(220,38,38,0.15)", "#FCA5A5", "rgba(252,165,165,0.30)"
        )
        self._header.add_stat_pill(self._pill_total)
        self._header.add_stat_pill(self._pill_open)
        self._header.add_stat_pill(self._pill_closed)

        # Tabs (row 2)
        tab_font = create_font(size=12, weight=QFont.DemiBold)

        self._tab_all = NavStyleTab(tr("page.case_mgmt.tab_all"))
        self._tab_all.setFixedSize(ScreenScale.w(100), ScreenScale.h(38))
        self._tab_all.set_font(tab_font)
        self._tab_all.set_active(True)
        self._tab_all.clicked.connect(lambda: self._on_tab(None))
        self._header.add_tab(self._tab_all)

        self._tab_open = NavStyleTab(tr("page.case_mgmt.tab_open"))
        self._tab_open.setFixedSize(ScreenScale.w(120), ScreenScale.h(38))
        self._tab_open.set_font(tab_font)
        self._tab_open.set_active(False)
        self._tab_open.clicked.connect(lambda: self._on_tab(1))
        self._header.add_tab(self._tab_open)

        self._tab_closed = NavStyleTab(tr("page.case_mgmt.tab_closed"))
        self._tab_closed.setFixedSize(ScreenScale.w(120), ScreenScale.h(38))
        self._tab_closed.set_font(tab_font)
        self._tab_closed.set_active(False)
        self._tab_closed.clicked.connect(lambda: self._on_tab(2))
        self._header.add_tab(self._tab_closed)

        # Search field (row 1, matches cases_page style)
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("page.case_mgmt.search_placeholder"))
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
        self._search.returnPressed.connect(self._on_search_changed)
        self._header.add_action_widget(self._search)

        main.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        main.addWidget(self._accent_line)

        # Light content area
        self._content_wrapper = QWidget()
        self._content_wrapper.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
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
        self._grid_layout = QGridLayout(self._scroll_content)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setColumnStretch(0, 1)
        self._grid_layout.setColumnStretch(1, 1)

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)

        self._empty_state = _EmptyStateCases()
        self._stack.addWidget(self._empty_state)

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

    # -- Tab & filter handlers --

    def _on_tab(self, status_filter: Optional[int]):
        if self._loading or status_filter == self._current_filter:
            return
        self._current_filter = status_filter
        self._current_page = 1
        self._tab_all.set_active(status_filter is None)
        self._tab_open.set_active(status_filter == 1)
        self._tab_closed.set_active(status_filter == 2)
        self._accent_line.pulse()
        self._load_cases()

    def _on_search_changed(self):
        self._current_page = 1
        self._load_cases()

    # -- Pagination --

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_cases()

    def _on_next_page(self):
        total_pages = max(1, -(-self._total_count // self._page_size))
        if self._current_page < total_pages:
            self._current_page += 1
            self._load_cases()

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

    # -- Stat pill & tab label updates --

    def _update_stat_pills(self):
        total = self._open_count + self._closed_count
        self._pill_total.setText(f"  {tr('page.case_mgmt.pill_total_count', count=total)}  ")
        self._pill_open.setText(f"  {tr('page.case_mgmt.pill_open_count', count=self._open_count)}  ")
        self._pill_closed.setText(f"  {tr('page.case_mgmt.pill_closed_count', count=self._closed_count)}  ")

    def _update_tab_labels(self):
        self._tab_all.set_text(tr("page.case_mgmt.tab_all"))
        self._tab_open.set_text(tr("page.case_mgmt.tab_open"))
        self._tab_closed.set_text(tr("page.case_mgmt.tab_closed"))

    # -- Data loading --

    def _load_cases(self):
        if self._loading:
            return
        self._loading = True
        self._spinner.show_loading(tr("page.case_mgmt.loading"))

        self._worker = ApiWorker(self._fetch_cases_data)
        self._worker.finished.connect(self._on_cases_loaded)
        self._worker.error.connect(self._on_cases_load_error)
        self._worker.start()

    def _fetch_cases_data(self):
        from services.api_client import get_api_client
        api = get_api_client()

        if self._auth_token:
            api.set_access_token(self._auth_token)

        search_text = self._search.text().strip()

        # Fetch paginated cases
        try:
            params = {
                "page": self._current_page,
                "page_size": self._page_size,
            }
            if self._current_filter is not None:
                params["status"] = self._current_filter
            if search_text:
                params["building_code"] = search_text

            raw = api.get_cases(**params)
        except Exception as e:
            logger.warning(f"Cases fetch failed: {e}")
            raise

        if isinstance(raw, dict):
            items = raw.get("cases", raw.get("items", []))
            total_count = raw.get("totalCount", len(items))
        elif isinstance(raw, list):
            items = raw
            total_count = len(items)
        else:
            items = []
            total_count = 0

        cases = []
        for item in items:
            try:
                cases.append(Case.from_api_dict(item))
            except Exception as exc:
                logger.debug(f"Skipping malformed case item: {exc}")

        # Fetch counts for stat pills
        open_count = 0
        closed_count = 0
        for st in [1, 2]:
            try:
                count_raw = api.get_cases(status=st, page=1, page_size=1)
                if isinstance(count_raw, dict):
                    ct = count_raw.get("totalCount", 0)
                else:
                    ct = 0
                if st == 1:
                    open_count = ct
                else:
                    closed_count = ct
            except Exception:
                pass

        return {
            "cases": cases,
            "total_count": total_count,
            "open_count": open_count,
            "closed_count": closed_count,
        }

    def _on_cases_loaded(self, result):
        try:
            self._cases = result.get("cases", [])
            self._total_count = result.get("total_count", 0)
            self._open_count = result.get("open_count", 0)
            self._closed_count = result.get("closed_count", 0)

            logger.info(
                f"Loaded {len(self._cases)} cases "
                f"(filter={self._current_filter}, page={self._current_page})"
            )
            self._populate_cards(self._cases)
            self._update_stat_pills()
            self._update_tab_labels()
            self._update_pagination()
        except Exception as e:
            logger.error(f"Error processing cases: {e}")
            self._cases = []
            self._populate_cards(self._cases)
        finally:
            self._loading = False
            self._spinner.hide_loading()

    def _on_cases_load_error(self, error_msg):
        self._loading = False
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.case_mgmt.load_error"), Toast.ERROR)
        logger.warning(f"Error loading cases: {error_msg}")
        self._cases = []
        self._populate_cards(self._cases)

    # -- Card population --

    def _populate_cards(self, cases: List[Case]):
        try:
            self._clear_cards()

            if not cases:
                self._stack.setCurrentIndex(1)
                self._update_empty_text()
                self._update_pagination()
                return

            self._stack.setCurrentIndex(0)

            for idx, case in enumerate(cases):
                card = _CaseCard(case)
                card.clicked.connect(self._on_card_clicked)
                row = idx // 2
                col = idx % 2
                self._grid_layout.addWidget(card, row, col)
                self._card_widgets.append(card)

            # Add vertical spacer at the end
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            spacer.setStyleSheet("background: transparent;")
            total_rows = (len(cases) + 1) // 2
            self._grid_layout.addWidget(spacer, total_rows, 0, 1, 2)

            self._update_pagination()
            self._animate_card_entrance()

            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()
        except Exception as e:
            logger.error(f"Error populating case cards: {e}")
            self._stack.setCurrentIndex(1)
            self._update_empty_text()

    def _animate_card_entrance(self):
        count = len(self._card_widgets)
        if count > 30 or count == 0:
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
            if hasattr(card, "_entrance_anim") and card._entrance_anim:
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

        # Clear grid layout
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _update_card_shimmer(self):
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    def _update_empty_text(self):
        if self._current_filter == 1:
            self._empty_state.set_title(tr("page.case_mgmt.empty_open"))
        elif self._current_filter == 2:
            self._empty_state.set_title(tr("page.case_mgmt.empty_closed"))
        else:
            self._empty_state.set_title(tr("page.case_mgmt.empty_all"))
        self._empty_state.set_description(tr("page.case_mgmt.empty_desc"))

    # -- Card click --

    def _on_card_clicked(self, case_id: str):
        if self._navigating or not case_id:
            return
        self._navigating = True
        self._spinner.show_loading(tr("page.case_mgmt.loading_case"))
        self.case_selected.emit(case_id)
