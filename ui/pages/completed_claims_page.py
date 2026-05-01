# -*- coding: utf-8 -*-
"""
Claims Page v3 — Dark navy header with constellation, navbar-style tabs,
animated shimmer cards, and cohesive blue palette.
"""

import logging
import math
import random
import time
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QFrame, QLineEdit, QPushButton,
    QSizePolicy, QGraphicsDropShadowEffect,
    QStackedWidget,
)
from PyQt5.QtCore import (
    QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtSignal, pyqtProperty, QTimer,
)
from PyQt5.QtGui import (
    QFont, QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QPen,
)

from ui.design_system import Colors, PageDimensions, Spacing, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.nav_style_tab import NavStyleTab
from ui.components.empty_state import EmptyState
from ui.components.accent_line import AccentLine
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.search_context_bar import SearchContextBar
from app.config import Pages
from services.translation_manager import tr, get_layout_direction, get_language, apply_label_alignment
from services.display_mappings import get_source_display, get_claim_type_display
from services.api_worker import ApiWorker
from ui.components.toast import Toast

logger = logging.getLogger(__name__)

CASE_STATUS_OPEN = 1
CASE_STATUS_CLOSED = 2

_STATUS_STYLES = {
    "open":         {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74"},
    "draft":        {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74"},
    "submitted":    {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "under_review": {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "screening":    {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "awaiting_docs": {"bg": "#FFFBEB", "fg": "#92400E", "border": "#FCD34D"},
    "conflict":     {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
    "approved":     {"bg": "#EBF5FF", "fg": "#0369A1", "border": "#7DD3FC"},
    "closed":       {"bg": "#EBF5FF", "fg": "#0369A1", "border": "#7DD3FC"},
    "rejected":     {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
}


# ---------------------------------------------------------------------------
#  _ClaimCard — Card with blue tint, animated shimmer, press-down, chevron
# ---------------------------------------------------------------------------

class _ClaimCard(QFrame):
    """Claim card with blue-tinted background, animated shimmer sweep,
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

    def __init__(self, claim_data: Dict, parent=None):
        super().__init__(parent)
        self._claim_uuid = claim_data.get("claim_uuid", "")
        self._status = claim_data.get("status", "open")
        self._hovered = False
        self._pressed = False
        self._badge = None
        self._entrance_anim = None
        self._entrance_effect = None
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(ScreenScale.h(120))
        self.setMouseTracking(True)
        self._build_ui(claim_data)

    def _build_ui(self, d: Dict):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            _ClaimCard {{
                background: {self._CARD_BG};
                border-radius: 12px;
                border: 1px solid #E2EAF2;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 22))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 16, 0)
        outer.setSpacing(0)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(20, 12, 0, 12)
        content.setSpacing(6)

        # Row 1: claim number + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        claim_id_label = QLabel(d.get("claim_id", "N/A"))
        id_font = create_font(size=10, weight=FontManager.WEIGHT_MEDIUM)
        id_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        claim_id_label.setFont(id_font)
        claim_id_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        apply_label_alignment(claim_id_label)
        row1.addWidget(claim_id_label)
        row1.addStretch()

        status_text = self._get_status_text(self._status)
        style = _STATUS_STYLES.get(self._status, _STATUS_STYLES["open"])
        badge = QLabel(status_text)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(24))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 12px; "
            f"padding: 0 12px; }}"
        )
        self._badge = badge
        row1.addWidget(badge)
        content.addLayout(row1)

        # Row 2: claimant name
        name_label = QLabel(d.get("claimant_name", "-"))
        name_label.setFont(create_font(size=13, weight=QFont.Bold))
        name_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        name_label.setMaximumWidth(ScreenScale.w(600))
        apply_label_alignment(name_label)
        content.addWidget(name_label)

        # Row 3: details
        details_parts = []
        address = d.get("address", "")
        if address:
            details_parts.append(address)
        building_code = d.get("building_code", "")
        if building_code:
            details_parts.append(f"{tr('page.claims.card_building')}: {building_code}")
        claim_type = d.get("claim_type", "")
        if claim_type:
            display = self._get_type_display(claim_type)
            if display:
                details_parts.append(display)
        date_str = d.get("date", "")
        if date_str:
            details_parts.append(date_str)
        source_label = d.get("source_label", "")
        if source_label:
            details_parts.append(source_label)

        details_text = " \u2009\u00b7\u2009 ".join(details_parts)
        details = QLabel(details_text)
        details.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        details.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        apply_label_alignment(details)
        content.addWidget(details)

        outer.addLayout(content, 1)

    def _get_status_text(self, status: str) -> str:
        key_map = {
            "open": "page.claims.tab_open",
            "closed": "page.claims.tab_closed",
        }
        return tr(key_map.get(status, "page.claims.tab_open"))

    def _get_type_display(self, claim_type) -> str:
        try:
            return get_claim_type_display(claim_type)
        except Exception:
            return str(claim_type) if claim_type else ""

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time()

        # Animated blue shimmer sweep across the card
        sweep_pos = (math.sin(t * 0.7 + self._shimmer_offset) + 1) / 2
        sweep_x = int(sweep_pos * w)
        shimmer_grad = QLinearGradient(sweep_x - 120, 0, sweep_x + 120, 0)
        shimmer_grad.setColorAt(0, QColor(56, 144, 223, 0))
        shimmer_grad.setColorAt(0.5, QColor(120, 190, 255, 12))
        shimmer_grad.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 11, 11)
        painter.setClipPath(clip)
        painter.fillRect(QRectF(0, 0, w, h), shimmer_grad)

        # Top edge shimmer on hover
        if self._hovered:
            top_grad = QLinearGradient(0, 0, w, 0)
            top_grad.setColorAt(0, QColor(56, 144, 223, 0))
            top_grad.setColorAt(0.15, QColor(56, 144, 223, 35))
            top_grad.setColorAt(0.5, QColor(120, 190, 255, 55))
            top_grad.setColorAt(0.85, QColor(56, 144, 223, 35))
            top_grad.setColorAt(1, QColor(56, 144, 223, 0))
            painter.fillRect(QRectF(0, 0, w, 3.5), top_grad)

        painter.setClipping(False)

        # Chevron arrow
        is_rtl = self.layoutDirection() == Qt.RightToLeft
        chevron_x = 14 if is_rtl else w - 22
        chevron_alpha = 130 if self._hovered else 45
        painter.setPen(QPen(QColor(56, 144, 223, chevron_alpha), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cy = h / 2
        if is_rtl:
            painter.drawLine(int(chevron_x + 6), int(cy - 6), int(chevron_x), int(cy))
            painter.drawLine(int(chevron_x), int(cy), int(chevron_x + 6), int(cy + 6))
        else:
            painter.drawLine(int(chevron_x), int(cy - 6), int(chevron_x + 6), int(cy))
            painter.drawLine(int(chevron_x + 6), int(cy), int(chevron_x), int(cy + 6))

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
            _ClaimCard {{
                background: {self._CARD_BG_HOVER};
                border-radius: 12px;
                border: 1px solid rgba(56, 144, 223, 0.3);
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(32)
            eff.setOffset(0, 8)
            eff.setColor(QColor(56, 144, 223, 35))
        if self._badge:
            style = _STATUS_STYLES.get(self._status, _STATUS_STYLES["open"])
            glow = QGraphicsDropShadowEffect(self._badge)
            glow.setBlurRadius(8)
            glow.setOffset(0, 0)
            glow.setColor(QColor(style['fg']))
            self._badge.setGraphicsEffect(glow)
        self._animate_lift(5.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.setStyleSheet(f"""
            _ClaimCard {{
                background: {self._CARD_BG};
                border-radius: 12px;
                border: 1px solid #E2EAF2;
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(20)
            eff.setOffset(0, 4)
            eff.setColor(QColor(0, 0, 0, 22))
        if self._badge:
            self._badge.setGraphicsEffect(None)
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
            if self._claim_uuid:
                self.clicked.emit(self._claim_uuid)
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
#  CompletedClaimsPage — Main page widget
# ---------------------------------------------------------------------------

class CompletedClaimsPage(QWidget):
    """Claims listing page with dark header zone, shimmer cards,
    and comprehensive loading states."""

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claims_data: List[Dict] = []
        self._active_tab = "open"
        self._buildings_cache: Dict[str, object] = {}
        self._last_refresh_ms = 0
        self._card_widgets: List[_ClaimCard] = []
        self._loading = False
        self._navigating = False
        self._worker = None
        self._current_page = 1
        self._total_count = 0
        self._page_size = 20
        self._search_mode = False

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._on_search_triggered)

        # Shared timer for card shimmer animation
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.claims.subtitle"))
        self._header.set_help(Pages.CLAIMS)

        tab_font = create_font(size=12, weight=QFont.DemiBold)

        self._tab_open = NavStyleTab(tr("page.claims.tab_open"))
        self._tab_open.setFixedSize(ScreenScale.w(130), ScreenScale.h(38))
        self._tab_open.set_font(tab_font)
        self._tab_open.set_active(True)
        self._tab_open.clicked.connect(lambda: self._on_tab("open"))
        self._header.add_tab(self._tab_open)

        self._tab_closed = NavStyleTab(tr("page.claims.tab_closed"))
        self._tab_closed.setFixedSize(ScreenScale.w(130), ScreenScale.h(38))
        self._tab_closed.set_font(tab_font)
        self._tab_closed.set_active(False)
        self._tab_closed.clicked.connect(lambda: self._on_tab("closed"))
        self._header.add_tab(self._tab_closed)

        # Search context bar (shown when search is active, hidden initially)
        self._search_bar = SearchContextBar(tabs=[self._tab_open, self._tab_closed])
        self._search_bar.back_clicked.connect(self._exit_search_mode)
        self._search_bar.hide()
        self._header.add_row2_widget(self._search_bar)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("page.claims.search_placeholder"))
        self._search.setFixedSize(ScreenScale.w(280), ScreenScale.h(34))
        self._search.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._search.setStyleSheet("""
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
        """)
        search_icon = Icon.load_pixmap("search", 16)
        if search_icon and not search_icon.isNull():
            icon_label = QLabel(self._search)
            icon_label.setPixmap(search_icon)
            icon_label.setFixedSize(ScreenScale.w(16), ScreenScale.h(16))
            icon_label.move(10, 9)
            icon_label.setStyleSheet("background: transparent; border: none;")
        self._search.returnPressed.connect(self._on_search_triggered)
        self._search.textChanged.connect(self._on_search_text_changed)

        # Attach clear action to search field
        self._search_bar.attach_clear_action(self._search)

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

        # Card stream area
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
        self._cards_layout = QGridLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(16)
        self._cards_layout.setColumnStretch(0, 1)
        self._cards_layout.setColumnStretch(1, 1)

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)

        self._empty_state = EmptyState(
            icon_name="folder",
            title=tr("page.claims.empty_open"),
            description=tr("page.claims.empty_description"),
        )
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

        _NAV_BTN = """
            QPushButton {
                background: rgba(56, 144, 223, 0.08);
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 6px; color: #3890DF;
                padding: 0 10px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(56, 144, 223, 0.18); }
            QPushButton:disabled { color: #B0BEC5; background: transparent; border-color: #E0E0E0; }
        """
        self._prev_btn = QPushButton("\u276E")
        self._prev_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prev_btn.setStyleSheet(_NAV_BTN)
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
        self._next_btn.setStyleSheet(_NAV_BTN)
        self._next_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_btn)

        return bar

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_claims()

    def _on_next_page(self):
        total_pages = max(1, -(-self._total_count // self._page_size))
        if self._current_page < total_pages:
            self._current_page += 1
            self._load_claims()

    def _update_card_shimmer(self):
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    # -- Tab labels with counts --

    def _update_tab_labels(self):
        self._tab_open.set_text(tr("page.claims.tab_open"))
        self._tab_closed.set_text(tr("page.claims.tab_closed"))

    # -- Events --

    def _on_search_triggered(self):
        self._current_page = 1
        search_text = self._search.text().strip()
        if search_text:
            self._enter_search_mode()
            self._load_claims()
        else:
            self._exit_search_mode()

    def _on_search_changed(self):
        self._current_page = 1
        self._search_timer.start(500)

    def _on_search_text_changed(self, text: str):
        if not text.strip() and self._search_mode:
            self._exit_search_mode()

    def _enter_search_mode(self):
        if self._search_mode:
            return
        self._search_mode = True
        self._search_bar.enter_search_mode()

    def _exit_search_mode(self):
        if not self._search_mode:
            return
        self._search_mode = False
        self._search_bar.exit_search_mode()
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._current_page = 1
        self._load_claims()

    def _on_tab(self, which: str):
        if self._loading or which == self._active_tab:
            return
        self._active_tab = which
        self._current_page = 1
        self._tab_open.set_active(which == "open")
        self._tab_closed.set_active(which == "closed")
        self._accent_line.pulse()
        self._load_claims()

    # -- Data loading --

    def refresh(self, data=None):
        self._navigating = False
        now = int(time.time() * 1000)
        if now - self._last_refresh_ms < 5000 and self.claims_data:
            return
        self._last_refresh_ms = now
        self._load_claims()

    def _load_claims(self):
        if self._loading:
            return
        self._loading = True
        self._spinner.show_loading(tr("page.claims.loading"))

        case_status = CASE_STATUS_OPEN if self._active_tab == "open" else CASE_STATUS_CLOSED
        search_text = self._search.text().strip() if self._search_mode else ""

        self._worker = ApiWorker(
            self._fetch_claims_data, case_status, search_text
        )
        self._worker.finished.connect(self._on_claims_loaded)
        self._worker.error.connect(self._on_claims_error)
        self._worker.start()

    def _fetch_claims_data(self, case_status, search_text):
        from services.api_client import get_api_client

        api = get_api_client()
        total_count = 0

        if search_text:
            normalized = search_text.strip().upper()
            summaries = []
            try:
                claim = api.get_claim_by_number(normalized)
                if isinstance(claim, dict) and claim.get("claimNumber"):
                    # Normalize ClaimDto -> summary shape expected by _map_summary.
                    # Claim status enum (1=draft..7=archived); approved/rejected/archived = closed.
                    raw_status = claim.get("status", 0)
                    case_status = CASE_STATUS_CLOSED if raw_status in (5, 6, 7) else CASE_STATUS_OPEN
                    normalized_claim = dict(claim)
                    normalized_claim["caseStatus"] = case_status
                    normalized_claim["buildingCode"] = (
                        claim.get("buildingCode")
                        or claim.get("buildingId")
                        or claim.get("propertyUnitId")
                        or ""
                    )
                    normalized_claim["referenceCode"] = (
                        claim.get("referenceCode") or claim.get("claimNumber", "")
                    )
                    summaries = [normalized_claim]
                    total_count = 1
            except Exception as e:
                logger.warning(f"Claim number lookup failed: {e}")
                summaries = []
                total_count = 0
        else:
            try:
                raw = api._request("GET", "/v2/claims/summaries", params={
                    "caseStatus": case_status,
                    "page": self._current_page,
                    "pageSize": self._page_size,
                })
                if isinstance(raw, dict):
                    summaries = raw.get("items", [])
                    total_count = raw.get("totalCount", len(summaries))
                else:
                    summaries = raw if isinstance(raw, list) else []
                    total_count = len(summaries)
            except Exception as e:
                logger.warning(f"Paginated claims fetch failed: {e}")
                summaries = api.get_claims_summaries(claim_status=case_status)
                total_count = len(summaries)

        return {
            "summaries": summaries,
            "case_status": case_status,
            "total_count": total_count,
        }

    def _on_claims_loaded(self, result):
        try:
            self._total_count = result.get("total_count", 0)

            summaries = result.get("summaries", [])
            self.claims_data = [self._map_summary(s) for s in summaries]

            logger.info(f"Loaded {len(self.claims_data)} claims (status={result.get('case_status')})")
            self._populate_cards()
            self._update_tab_labels()
            self._update_pagination()
        except Exception as e:
            logger.error(f"Error processing claims: {e}")
            self.claims_data = []
            self._populate_cards()
        finally:
            self._loading = False
            self._spinner.hide_loading()

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

    def _on_claims_error(self, error_msg):
        self._loading = False
        self._spinner.hide_loading()
        logger.warning(f"Error loading claims: {error_msg}")
        self.claims_data = []
        from ui.utils.page_helpers import show_error_state
        show_error_state(self._empty_state, self._stack, error_msg, self._load_claims)
        self._update_pagination()

    def _map_summary(self, s: Dict) -> Dict:
        try:
            source = s.get("claimSource", 0)
            claimant = (
                s.get("primaryClaimantName")
                or s.get("fullNameArabic")
                or tr("page.claims.unknown_claimant")
            )
            date_str = s.get("createdAtUtc") or s.get("surveyDate") or ""
            building_code = s.get("buildingCode", "")
            status_int = s.get("caseStatus", 0)
            status_str = "open" if status_int == CASE_STATUS_OPEN else "closed"
            claim_type = s.get("claimType", "")

            address = ""
            if building_code and building_code in self._buildings_cache:
                b = self._buildings_cache[building_code]
                parts = []
                for attr in ("governorate_name", "district_name", "subdistrict_name", "neighbourhood_name"):
                    val = getattr(b, attr, None) or ""
                    if val:
                        parts.append(val)
                if parts:
                    address = " > ".join(parts)

            return {
                "claim_id": s.get("referenceCode") or s.get("claimNumber", "") or s.get("claimId", "N/A"),
                "claim_uuid": s.get("claimId", "") or s.get("id", ""),
                "claimant_name": claimant,
                "date": date_str[:10] if date_str and not date_str.startswith("0001") else "",
                "status": status_str,
                "claim_type": claim_type,
                "source": source,
                "source_label": get_source_display(source),
                "building_code": building_code,
                "address": address,
            }
        except Exception as e:
            logger.warning(f"Error mapping claim summary: {e}")
            return {
                "claim_id": "N/A", "claim_uuid": "",
                "claimant_name": "-", "date": "", "status": "open",
                "claim_type": "", "source": 0, "source_label": "",
                "building_code": "", "address": "",
            }

    # -- Card population --

    def _populate_cards(self):
        try:
            self._clear_cards()

            if not self.claims_data:
                self._empty_state.clear_action()
                self._stack.setCurrentIndex(1)
                self._update_empty_text()
                self._update_pagination()
                return

            self._stack.setCurrentIndex(0)

            # Update search result count in header
            if self._search_mode:
                total = len(self.claims_data)
                term = self._search.text().strip()
                self._search_bar.update_count(term, total)

            for idx, claim in enumerate(self.claims_data):
                card = _ClaimCard(claim)
                card.clicked.connect(self._on_card_clicked)
                row = idx // 2
                col = idx % 2
                self._cards_layout.addWidget(card, row, col)
                self._card_widgets.append(card)

            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            spacer.setStyleSheet("background: transparent;")
            total_rows = (len(self.claims_data) + 1) // 2
            self._cards_layout.addWidget(spacer, total_rows, 0, 1, 2)

            self._update_pagination()

            # Start shimmer timer for card animation
            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()
        except Exception as e:
            logger.error(f"Error populating cards: {e}")
            self._stack.setCurrentIndex(1)
            self._update_empty_text()

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

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _update_empty_text(self):
        if self._search_mode:
            term = self._search.text().strip()
            self._empty_state.set_title(tr("page.claims.no_search_results"))
            self._empty_state.set_description(f"\"{term}\"")
        else:
            msg = tr("page.claims.empty_open") if self._active_tab == "open" else tr("page.claims.empty_closed")
            self._empty_state.set_title(msg)
            self._empty_state.set_description(tr("page.claims.empty_description"))

    # -- Interaction --

    def _on_card_clicked(self, claim_uuid: str):
        if self._navigating or not claim_uuid:
            return
        self._navigating = True
        self._spinner.show_loading(tr("page.claims.loading"))
        self.claim_selected.emit(claim_uuid)

    # -- Public interface --

    def load_claims(self, claims_data):
        self.claims_data = claims_data
        self._populate_cards()

    def search_claims(self, query: str, mode: str = "name"):
        pass

    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        self._header.get_title_label().setText(tr("page.claims.subtitle"))
        self._search.setPlaceholderText(tr("page.claims.search_reference_code"))

        self._search_bar.update_language()
        self._update_tab_labels()

        self._scroll.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)

        if self.claims_data:
            self._populate_cards()
        else:
            self._update_empty_text()

    def set_tab_title(self, title: str):
        pass

    def configure_for_role(self, role: str):
        pass

    def showEvent(self, event):
        super().showEvent(event)
        if self._card_widgets and not self._shimmer_timer.isActive():
            self._shimmer_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._shimmer_timer.stop()
