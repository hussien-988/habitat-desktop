# -*- coding: utf-8 -*-
"""Duplicates page for conflict resolution — dark header design system."""

import math
import random
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox,
    QScrollArea, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QThread, pyqtSignal as Signal,
    QTimer,
)
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QLinearGradient,
    QPainterPath,
)

from repositories.database import Database
from services.duplicate_service import DuplicateService
from ui.components.dark_header_zone import DarkHeaderZone
from app.config import Pages
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.components.animated_card import AnimatedCard, animate_card_entrance
from ui.components.empty_state import EmptyState
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

# Status display config
_STATUS_COLORS = {
    "Pending": {"color": "#F59E0B", "bg": "#FEF3C7"},
    "PendingReview": {"color": "#F59E0B", "bg": "#FEF3C7"},
    "InReview": {"color": "#3B82F6", "bg": "#DBEAFE"},
    "Resolved": {"color": "#10B981", "bg": "#D1FAE5"},
    "Escalated": {"color": "#EF4444", "bg": "#FEE2E2"},
    "AutoResolved": {"color": "#8B5CF6", "bg": "#EDE9FE"},
}
_STATUS_LABEL_KEYS = {
    "Pending": "page.duplicates.status_pending",
    "PendingReview": "page.duplicates.status_pending_review",
    "InReview": "page.duplicates.status_in_review",
    "Resolved": "page.duplicates.status_resolved",
    "Escalated": "page.duplicates.status_escalated",
    "AutoResolved": "page.duplicates.status_auto_resolved",
}

_PRIORITY_COLORS = {
    "Critical": {"color": "#DC2626", "bg": "#FEE2E2"},
    "High": {"color": "#EA580C", "bg": "#FFEDD5"},
    "Medium": {"color": "#CA8A04", "bg": "#FEF9C3"},
    "Low": {"color": "#16A34A", "bg": "#DCFCE7"},
}
_PRIORITY_LABEL_KEYS = {
    "Critical": "page.duplicates.priority_critical",
    "High": "page.duplicates.priority_high",
    "Medium": "page.duplicates.priority_medium",
    "Low": "page.duplicates.priority_low",
}

_TYPE_LABEL_KEYS = {
    "PropertyDuplicate": "page.duplicates.type_property",
    "PersonDuplicate": "page.duplicates.type_person",
}


def _get_status_config(key):
    colors = _STATUS_COLORS.get(key, {"color": "#6B7280", "bg": "#F3F4F6"})
    label_key = _STATUS_LABEL_KEYS.get(key, "")
    return {"label": tr(label_key) if label_key else key, "color": colors["color"], "bg": colors["bg"]}


def _get_priority_config(key):
    colors = _PRIORITY_COLORS.get(key, {"color": "#6B7280", "bg": "#F3F4F6"})
    label_key = _PRIORITY_LABEL_KEYS.get(key, "")
    return {"label": tr(label_key) if label_key else key, "color": colors["color"]}


def _get_type_config(key):
    label_key = _TYPE_LABEL_KEYS.get(key, "")
    return {"label": tr(label_key) if label_key else key}


_PAGINATION_BTN_STYLE = """
    QPushButton {
        background: #F0F7FF;
        border: 1px solid rgba(56, 144, 223, 0.20);
        border-radius: 6px;
        color: #3890DF;
        font-size: 10pt;
        font-weight: 600;
        padding: 6px 16px;
    }
    QPushButton:hover { background: #E0EFFF; }
    QPushButton:disabled {
        background: #E8EDF2;
        color: #B0BEC5;
        border-color: #DDE3EA;
    }
"""


# ---------------------------------------------------------------------------
#  Priority → strip color mapping for cards
# ---------------------------------------------------------------------------

_PRIORITY_STRIP_COLORS = {
    "Critical": "#EF4444",
    "High": "#F59E0B",
    "Medium": "#3890DF",
    "Low": "#10B981",
}

_PRIORITY_BADGE_COLORS = {
    "Critical": {"color": "#FFFFFF", "bg": "#EF4444"},
    "High": {"color": "#FFFFFF", "bg": "#F59E0B"},
    "Medium": {"color": "#FFFFFF", "bg": "#3890DF"},
    "Low": {"color": "#FFFFFF", "bg": "#10B981"},
}


# ---------------------------------------------------------------------------
#  _DuplicateCard — animated card for a single conflict group
# ---------------------------------------------------------------------------

class _DuplicateCard(AnimatedCard):
    """Card representing a single conflict group in the duplicates list.

    Row 1: Conflict group ID (bold) + Priority badge (top-right, colored)
    Row 2: Type (Property/Person) + affected claims count + detection date
    Row 3: Status chip + matching field names
    """

    card_clicked = pyqtSignal(dict)

    def __init__(self, conflict: dict, parent=None):
        self._conflict = conflict
        priority = conflict.get("priority", "Medium")
        strip_color = _PRIORITY_STRIP_COLORS.get(priority, "#3890DF")

        super().__init__(
            parent,
            card_height=100,
            border_radius=12,
            status_color=strip_color,
            show_chevron=True,
            show_strip=False,
            strip_width=5,
        )
        self.clicked.connect(lambda: self.card_clicked.emit(self._conflict))

    def _build_content(self, layout: QVBoxLayout):
        conflict = self._conflict
        priority = conflict.get("priority", "Medium")

        # Row 1: Conflict ID (bold) + Priority badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        conflict_num = conflict.get("conflictNumber", "-")
        id_label = QLabel(f"#{conflict_num}")
        id_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_BOLD))
        id_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        apply_label_alignment(id_label)
        row1.addWidget(id_label)
        row1.addStretch()

        # Priority badge
        pri_cfg = _PRIORITY_BADGE_COLORS.get(priority, {"color": "#FFF", "bg": "#6B7280"})
        pri_label_key = _PRIORITY_LABEL_KEYS.get(priority, "")
        pri_text = tr(pri_label_key) if pri_label_key else priority
        badge = QLabel(pri_text)
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_BOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(22))
        badge.setStyleSheet(
            f"color: {pri_cfg['color']}; background: {pri_cfg['bg']};"
            f"border-radius: 6px; padding: 2px 10px; border: none;"
        )
        row1.addWidget(badge)

        layout.addLayout(row1)

        # Row 2: Type + affected claims count + detection date (dot-separated)
        row2 = QHBoxLayout()
        row2.setSpacing(0)

        ctype = conflict.get("conflictType", "")
        type_cfg = _get_type_config(ctype) if ctype else {"label": "-"}
        type_text = type_cfg["label"]

        first_id = conflict.get("firstEntityIdentifier", conflict.get("firstEntityId", "-"))
        second_id = conflict.get("secondEntityIdentifier", conflict.get("secondEntityId", "-"))
        claims_text = f"{first_id} / {second_id}"

        date_str = conflict.get("detectedDate", conflict.get("assignedDate", ""))
        if date_str and "T" in str(date_str):
            date_str = str(date_str).split("T")[0]

        score = conflict.get("similarityScore", 0)
        score_pct = f"{score * 100:.0f}%" if isinstance(score, float) and score <= 1 else f"{score}%"

        parts = [type_text, claims_text]
        if date_str:
            parts.append(str(date_str))
        info_str = "  \u00B7  ".join(parts)

        info_label = QLabel(info_str)
        info_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        info_label.setStyleSheet(
            "color: #6B7280; background: transparent; border: none;"
        )
        apply_label_alignment(info_label)
        row2.addWidget(info_label)
        row2.addStretch()

        # Similarity score badge
        sv = score if isinstance(score, (int, float)) else 0
        score_color = "#EF4444" if sv >= 0.9 else "#F59E0B" if sv >= 0.7 else "#6B7280"
        score_label = QLabel(score_pct)
        score_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
        score_label.setStyleSheet(
            f"color: {score_color}; background: transparent; border: none;"
        )
        row2.addWidget(score_label)

        layout.addLayout(row2)

        # Row 3: Status chip + matching fields
        row3 = QHBoxLayout()
        row3.setSpacing(8)

        status = conflict.get("status", "Pending")
        st_cfg = _get_status_config(status) if status else {"label": "-", "color": "#6B7280", "bg": "#F3F4F6"}
        status_chip = QLabel(st_cfg["label"])
        status_chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        status_chip.setAlignment(Qt.AlignCenter)
        status_chip.setFixedHeight(ScreenScale.h(20))
        status_chip.setStyleSheet(
            f"color: {st_cfg['color']}; background: {st_cfg['bg']};"
            f"border-radius: 5px; padding: 1px 8px; border: none;"
        )
        row3.addWidget(status_chip)

        # Matching field names (if available)
        match_fields = conflict.get("matchingFields", conflict.get("matchFields", []))
        if match_fields:
            if isinstance(match_fields, list):
                fields_text = ", ".join(str(f) for f in match_fields[:3])
            else:
                fields_text = str(match_fields)
            fields_label = QLabel(fields_text)
            fields_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            fields_label.setStyleSheet(
                "color: #9CA3AF; background: transparent; border: none;"
            )
            row3.addWidget(fields_label)

        row3.addStretch()
        layout.addLayout(row3)


# ---------------------------------------------------------------------------
#  Shimmer placeholder
# ---------------------------------------------------------------------------

class _ShimmerWidget(QWidget):
    """Animated shimmer placeholder for loading states."""

    def __init__(self, width=200, height=20, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)

    def _animate(self):
        self._offset = (self._offset + 4) % (self.width() * 2)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor("#F0F4F8"))
        grad = QLinearGradient(self._offset - self.width(), 0, self._offset, 0)
        grad.setColorAt(0.0, QColor(240, 244, 248, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 180))
        grad.setColorAt(1.0, QColor(240, 244, 248, 0))
        painter.fillRect(self.rect(), grad)
        painter.end()

    def stop(self):
        self._timer.stop()


# ---------------------------------------------------------------------------
#  Summary glow card
# ---------------------------------------------------------------------------

class _GlowCard(QFrame):
    """Summary card with subtle glow on hover, clickable for filtering."""

    clicked = Signal()

    def __init__(self, title: str, count: int, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._active = False
        self._setup(title, count, color)

    def _setup(self, title: str, count: int, color: str):
        self.setFixedHeight(ScreenScale.h(86))
        self.setMinimumWidth(ScreenScale.w(150))
        self.setCursor(Qt.PointingHandCursor)
        self._apply_inactive_style(color)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        sc = QColor(color)
        sc.setAlpha(25)
        shadow.setColor(sc)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

        self.count_label = QLabel(str(count))
        self.count_label.setFont(create_font(size=20, weight=FontManager.WEIGHT_BOLD))
        self.count_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        layout.addWidget(self.count_label)

        self.title_label = QLabel(title)
        self.title_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self.title_label.setStyleSheet("color: #78909C; background: transparent; border: none;")
        layout.addWidget(self.title_label)

    def _apply_inactive_style(self, color):
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 white, stop:1 #F8FAFC);
                border-radius: 14px;
                border: 1px solid {color}22;
            }}
            QFrame:hover {{
                border: 1.5px solid {color}66;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 white, stop:1 {color}08);
            }}
        """)

    def update_count(self, count: int):
        self.count_label.setText(str(count))

    def set_active(self, active: bool):
        self._active = active
        c = self._color
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background: {c}12;
                    border-radius: 14px;
                    border: 2px solid {c};
                }}
            """)
        else:
            self._apply_inactive_style(c)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


# ---------------------------------------------------------------------------
#  Background workers
# ---------------------------------------------------------------------------

class _ConflictWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, service: DuplicateService, page=1, page_size=20, filters=None):
        super().__init__()
        self.service = service
        self.page = page
        self.page_size = page_size
        self.filters = filters or {}

    def run(self):
        try:
            result = self.service.get_conflicts(
                page=self.page,
                page_size=self.page_size,
                conflict_type=self.filters.get("conflict_type"),
                status=self.filters.get("status"),
                priority=self.filters.get("priority"),
                is_escalated=self.filters.get("is_escalated"),
            )
            summary = self.service.get_conflicts_summary()
            self.finished.emit({"conflicts": result, "summary": summary})
        except Exception as e:
            self.error.emit(str(e))


class _ResolutionWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, service: DuplicateService, action: str,
                 conflict_id: str, justification: str, master_id: str = ""):
        super().__init__()
        self.service = service
        self.action = action
        self.conflict_id = conflict_id
        self.justification = justification
        self.master_id = master_id

    def run(self):
        try:
            if self.action == "merge":
                result = self.service.merge_conflict(
                    self.conflict_id, self.master_id, self.justification)
            elif self.action == "keep_separate":
                result = self.service.keep_separate(
                    self.conflict_id, self.justification)
            else:
                result = False
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# _EmptyStateConflicts removed — using EmptyStateAnimated from animated_card.py


# ---------------------------------------------------------------------------
#  Main Page
# ---------------------------------------------------------------------------

class DuplicatesPage(QWidget):
    """Duplicates/Conflicts resolution page with dark header design."""

    view_comparison_requested = pyqtSignal(object)
    return_to_import = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db)
        self._worker = None
        self._user_id = None
        self._conflicts = []
        self._current_page = 1
        self._total_pages = 1
        self._page_size = 20
        self._exclude_resolved = False
        self._loading = False
        self._conflict_cards = []

        # Shimmer timer for card animation (80ms)
        self._card_shimmer_timer = QTimer(self)
        self._card_shimmer_timer.setInterval(80)
        self._card_shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    def set_user_id(self, user_id: str):
        self._user_id = user_id

    # -- UI Setup ----------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet("background-color: #f0f7ff;")
        self.setLayoutDirection(get_layout_direction())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Dark header
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.duplicates.title"))
        self._header.set_help(Pages.DUPLICATES)

        self._stat_pending = StatPill(tr("page.duplicates.stat_pending"))
        self._stat_pending.set_count(0)
        self._header.add_stat_pill(self._stat_pending)

        # Refresh button
        self._refresh_btn = QPushButton(tr("page.duplicates.refresh"))
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setStyleSheet(StyleManager.refresh_button_dark())
        self._refresh_btn.clicked.connect(lambda: self.refresh())
        self._header.add_action_widget(self._refresh_btn)

        # Filters in header row2
        self._type_filter = QComboBox()
        self._type_filter.setLayoutDirection(get_layout_direction())
        self._type_filter.setStyleSheet(StyleManager.dark_combo_box())
        self._type_filter.addItem(tr("page.duplicates.all_types"), "")
        self._type_filter.addItem(tr("page.duplicates.card_property"), "PropertyDuplicate")
        self._type_filter.addItem(tr("page.duplicates.card_person"), "PersonDuplicate")
        self._type_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._header.add_row2_widget(self._type_filter)

        self._status_filter = QComboBox()
        self._status_filter.setLayoutDirection(get_layout_direction())
        self._status_filter.setStyleSheet(StyleManager.dark_combo_box())
        self._status_filter.addItem(tr("page.duplicates.all_statuses"), "")
        self._status_filter.addItem(tr("page.duplicates.status_pending"), "Pending")
        self._status_filter.addItem(tr("page.duplicates.status_pending_review"), "PendingReview")
        self._status_filter.addItem(tr("page.duplicates.status_in_review"), "InReview")
        self._status_filter.addItem(tr("page.duplicates.status_resolved"), "Resolved")
        self._status_filter.addItem(tr("page.duplicates.status_auto_resolved"), "AutoResolved")
        self._status_filter.addItem(tr("page.duplicates.status_escalated"), "Escalated")
        self._status_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._header.add_row2_widget(self._status_filter)

        self._priority_filter = QComboBox()
        self._priority_filter.setLayoutDirection(get_layout_direction())
        self._priority_filter.setStyleSheet(StyleManager.dark_combo_box())
        self._priority_filter.addItem(tr("page.duplicates.all_priorities"), "")
        self._priority_filter.addItem(tr("page.duplicates.priority_critical"), "Critical")
        self._priority_filter.addItem(tr("page.duplicates.priority_high"), "High")
        self._priority_filter.addItem(tr("page.duplicates.priority_medium"), "Medium")
        self._priority_filter.addItem(tr("page.duplicates.priority_low"), "Low")
        self._priority_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._header.add_row2_widget(self._priority_filter)

        root.addWidget(self._header)

        # Accent line
        self._accent = AccentLine()
        root.addWidget(self._accent)

        # Content area
        content_area = QWidget()
        content_area.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(), 14,
        )
        content_layout.setSpacing(12)

        # Return-to-import banner
        self._import_banner = self._build_import_banner()
        content_layout.addWidget(self._import_banner)
        self._import_banner.setVisible(False)

        # Summary cards row
        self._summary_container = self._build_summary_cards()
        content_layout.addWidget(self._summary_container)

        # Shimmer placeholders
        self._shimmer_container = self._build_shimmer()
        content_layout.addWidget(self._shimmer_container)
        self._shimmer_container.setVisible(False)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        scroll.setWidget(scroll_content)

        # Conflict cards container (replaces table)
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._content_layout.addWidget(self._cards_container)

        # Pagination footer
        self._pagination_footer = self._build_pagination_footer()
        self._content_layout.addWidget(self._pagination_footer)
        self._pagination_footer.setVisible(False)

        # Empty state (reusable EmptyState)
        self._empty_state = EmptyState(
            icon_name="tdesign_no-result",
            title=tr("page.duplicates.no_conflicts"),
            description=tr("page.duplicates.no_conflicts_hint"),
        )
        self._empty_state.setMinimumHeight(ScreenScale.h(280))
        self._content_layout.addWidget(self._empty_state)
        self._empty_state.setVisible(False)

        self._content_layout.addStretch()

        content_layout.addWidget(scroll, 1)
        root.addWidget(content_area, 1)

        # Spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    # -- Import Banner -----------------------------------------------------

    def _build_import_banner(self) -> QFrame:
        banner = QFrame()
        banner.setFixedHeight(ScreenScale.h(48))
        banner.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.PRIMARY_BLUE}12;
                border: 1px solid {Colors.PRIMARY_BLUE}33;
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(banner)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        icon_lbl = QLabel("\u2190")
        icon_lbl.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        icon_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        self._banner_msg = QLabel(tr("page.duplicates.import_banner_msg"))
        self._banner_msg.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self._banner_msg.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
        layout.addWidget(self._banner_msg, 1)

        btn_return = QPushButton(tr("page.duplicates.return_to_import"))
        btn_return.setCursor(Qt.PointingHandCursor)
        btn_return.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        btn_return.setMinimumWidth(ScreenScale.w(150))
        btn_return.setFixedHeight(ScreenScale.h(36))
        btn_return.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: #1A56DB;
            }}
        """)
        btn_return.clicked.connect(self.return_to_import.emit)
        layout.addWidget(btn_return)
        self._banner_btn = btn_return

        return banner

    def set_return_to_import(self, enabled: bool):
        self._import_banner.setVisible(enabled)

    # -- Summary Cards -----------------------------------------------------

    def _build_summary_cards(self) -> QFrame:
        container = QFrame()
        container.setStyleSheet("QFrame { background: transparent; border: none; }")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._card_total = _GlowCard(tr("page.duplicates.card_total"), 0, Colors.PRIMARY_BLUE)
        self._card_property = _GlowCard(tr("page.duplicates.card_property"), 0, "#F59E0B")
        self._card_person = _GlowCard(tr("page.duplicates.card_person"), 0, "#8B5CF6")
        self._card_resolved = _GlowCard(tr("page.duplicates.card_resolved"), 0, "#10B981")

        self._summary_cards = [
            self._card_total, self._card_property, self._card_person,
            self._card_resolved,
        ]
        for card in self._summary_cards:
            layout.addWidget(card)

        self._card_total.clicked.connect(lambda: self._filter_by_card("all"))
        self._card_property.clicked.connect(lambda: self._filter_by_card("PropertyDuplicate"))
        self._card_person.clicked.connect(lambda: self._filter_by_card("PersonDuplicate"))
        self._card_resolved.clicked.connect(lambda: self._filter_by_card("Resolved"))

        return container

    # -- Shimmer -----------------------------------------------------------

    def _build_shimmer(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self._shimmer_widgets = []
        for _ in range(4):
            row = QFrame()
            row.setStyleSheet("QFrame { background: white; border-radius: 12px; border: none; }")
            row.setFixedHeight(ScreenScale.h(68))
            rl = QHBoxLayout(row)
            rl.setContentsMargins(16, 12, 16, 12)
            rl.setSpacing(16)

            s1 = _ShimmerWidget(60, 16)
            s2 = _ShimmerWidget(200, 16)
            s3 = _ShimmerWidget(100, 16)
            s4 = _ShimmerWidget(80, 24)
            self._shimmer_widgets.extend([s1, s2, s3, s4])

            rl.addWidget(s1)
            rl.addWidget(s2)
            rl.addStretch()
            rl.addWidget(s3)
            rl.addWidget(s4)

            layout.addWidget(row)

        return container

    # -- Pagination Footer -------------------------------------------------

    def _build_pagination_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(ScreenScale.h(54))
        footer.setStyleSheet(
            "QFrame { background: #FAFCFF; border: 1px solid #E2EAF2; border-radius: 12px; }"
        )

        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 0, 16, 0)
        fl.setSpacing(10)

        self._prev_btn = QPushButton(tr("page.duplicates.previous"))
        self._prev_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setFixedHeight(ScreenScale.h(34))
        self._prev_btn.setStyleSheet(_PAGINATION_BTN_STYLE)
        self._prev_btn.clicked.connect(lambda: self._go_to_page(self._current_page - 1))
        fl.addWidget(self._prev_btn)

        self._page_label = QLabel("1 / 1")
        self._page_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setStyleSheet("color: #546E7A; background: transparent; border: none;")
        fl.addWidget(self._page_label)

        self._next_btn = QPushButton(tr("page.duplicates.next"))
        self._next_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setFixedHeight(ScreenScale.h(34))
        self._next_btn.setStyleSheet(_PAGINATION_BTN_STYLE)
        self._next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))
        fl.addWidget(self._next_btn)

        fl.addStretch()

        self._count_label = QLabel(tr("page.duplicates.showing_count", shown=0, total=0))
        self._count_label.setFont(create_font(size=9))
        self._count_label.setStyleSheet("color: #78909C; background: transparent; border: none;")
        fl.addWidget(self._count_label)

        return footer

    # -- Card management ---------------------------------------------------

    def _clear_cards(self):
        """Remove all existing conflict cards from the layout."""
        self._card_shimmer_timer.stop()
        for card in self._conflict_cards:
            card.setParent(None)
            card.deleteLater()
        self._conflict_cards.clear()

    def _update_card_shimmer(self):
        """Trigger repaint on all visible cards for shimmer animation."""
        for card in self._conflict_cards:
            if card.isVisible():
                card.update()


    # -- Data Loading ------------------------------------------------------

    def _get_active_filters(self) -> dict:
        filters = {}
        ct = self._type_filter.currentData()
        if ct:
            filters["conflict_type"] = ct
        st = self._status_filter.currentData()
        if st:
            filters["status"] = st
        pr = self._priority_filter.currentData()
        if pr:
            filters["priority"] = pr
        return filters

    def _load_conflicts(self):
        if self._loading:
            return
        self._loading = True

        # Cancel previous worker
        if self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except Exception:
                pass
            self._worker.quit()
            self._worker.wait(500)

        self._shimmer_container.setVisible(True)
        self._cards_container.setVisible(False)
        self._pagination_footer.setVisible(False)
        self._empty_state.setVisible(False)

        self._worker = _ConflictWorker(
            self.duplicate_service,
            page=self._current_page,
            page_size=self._page_size,
            filters=self._get_active_filters(),
        )
        self._spinner.show_loading(tr("page.duplicates.loading_conflicts"))
        self._worker.finished.connect(self._on_load_finished)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_load_finished(self, data: dict):
        self._loading = False
        self._spinner.hide_loading()

        for s in self._shimmer_widgets:
            s.stop()
        self._shimmer_container.setVisible(False)

        # Update summary cards
        summary = data.get("summary", {})
        pending_total = summary.get("pendingReviewCount", summary.get("totalConflicts", 0))
        pending_property = summary.get("pendingPropertyDuplicates", summary.get("propertyDuplicateCount", 0))
        pending_person = summary.get("pendingPersonDuplicates", summary.get("personDuplicateCount", 0))
        self._card_total.update_count(pending_total)
        self._card_property.update_count(pending_property)
        self._card_person.update_count(pending_person)
        self._card_resolved.update_count(summary.get("resolvedCount", 0))

        self._stat_pending.set_count(pending_total)

        # Update conflict list
        conflicts_data = data.get("conflicts", {})
        all_items = conflicts_data.get("items", [])
        self._total_pages = conflicts_data.get("totalPages", 1)
        total_count = conflicts_data.get("totalCount", 0)

        if self._exclude_resolved:
            _resolved = {"resolved", "autoresolved"}
            self._conflicts = [
                c for c in all_items
                if c.get("status", "").lower() not in _resolved
            ]
        else:
            self._conflicts = all_items

        self._count_label.setText(
            tr("page.duplicates.showing_count", shown=len(self._conflicts), total=total_count)
        )

        if self._conflicts:
            self._cards_container.setVisible(True)
            self._pagination_footer.setVisible(True)
            self._empty_state.setVisible(False)
            self._populate_cards()
        else:
            self._cards_container.setVisible(False)
            self._pagination_footer.setVisible(False)
            self._empty_state.setVisible(True)

        self._update_pagination()

    def _on_load_error(self, error_msg: str):
        self._loading = False
        self._spinner.hide_loading()

        for s in self._shimmer_widgets:
            s.stop()
        self._shimmer_container.setVisible(False)

        self._conflicts = []
        self._clear_cards()
        self._cards_container.setVisible(False)
        self._pagination_footer.setVisible(False)
        self._empty_state.setVisible(True)
        Toast.show_toast(self, tr("page.duplicates.load_failed", error=error_msg), Toast.ERROR)
        logger.error("Conflict load error: %s", error_msg)

    # -- Card Population ---------------------------------------------------

    def _populate_cards(self):
        self._clear_cards()

        for idx, conflict in enumerate(self._conflicts):
            card = _DuplicateCard(conflict, parent=self._cards_container)
            card.card_clicked.connect(lambda c, i=idx: self._on_card_clicked(i, c))
            self._cards_layout.addWidget(card)
            self._conflict_cards.append(card)

        # Animate entrance with stagger
        animate_card_entrance(self._conflict_cards, parent=self)

        # Start shimmer timer
        if self._conflict_cards:
            self._card_shimmer_timer.start()

    # -- Card Click → Navigate to Comparison Page --------------------------

    def _on_card_clicked(self, idx: int, conflict: dict):
        """Navigate to full-page comparison/resolution view."""
        if idx >= len(self._conflicts):
            return
        conflict = self._conflicts[idx]
        self.view_comparison_requested.emit(conflict)

    # -- Filter & Pagination -----------------------------------------------

    def _filter_by_card(self, card_type: str):
        self._type_filter.blockSignals(True)
        self._status_filter.blockSignals(True)

        for card in self._summary_cards:
            card.set_active(False)

        self._exclude_resolved = False

        if card_type == "all":
            self._type_filter.setCurrentIndex(0)
            self._status_filter.setCurrentIndex(0)
            self._exclude_resolved = True
            self._card_total.set_active(True)
        elif card_type == "PropertyDuplicate":
            self._type_filter.setCurrentIndex(self._type_filter.findData("PropertyDuplicate"))
            self._status_filter.setCurrentIndex(0)
            self._exclude_resolved = True
            self._card_property.set_active(True)
        elif card_type == "PersonDuplicate":
            self._type_filter.setCurrentIndex(self._type_filter.findData("PersonDuplicate"))
            self._status_filter.setCurrentIndex(0)
            self._exclude_resolved = True
            self._card_person.set_active(True)
        elif card_type == "Resolved":
            self._type_filter.setCurrentIndex(0)
            self._status_filter.setCurrentIndex(self._status_filter.findData("Resolved"))
            self._card_resolved.set_active(True)

        self._type_filter.blockSignals(False)
        self._status_filter.blockSignals(False)

        self._current_page = 1
        self._load_conflicts()

    def _on_filter_changed(self):
        for card in self._summary_cards:
            card.set_active(False)
        self._exclude_resolved = False
        self._current_page = 1
        self._load_conflicts()

    def _go_to_page(self, page: int):
        if page < 1 or page > self._total_pages:
            return
        self._current_page = page
        self._load_conflicts()

    def _update_pagination(self):
        self._page_label.setText(f"{self._current_page} / {self._total_pages}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    # -- Public API --------------------------------------------------------

    def refresh(self, data=None):
        logger.debug("Refreshing duplicates page")
        self._loading = False
        self._load_conflicts()

    def hideEvent(self, event):
        for s in self._shimmer_widgets:
            s.stop()
        self._card_shimmer_timer.stop()
        super().hideEvent(event)

    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        # Header
        self._header.set_title(tr("page.duplicates.title"))
        self._stat_pending.set_label(tr("page.duplicates.stat_pending"))
        self._refresh_btn.setText(tr("page.duplicates.refresh"))

        # Summary cards
        self._card_total.title_label.setText(tr("page.duplicates.card_total"))
        self._card_property.title_label.setText(tr("page.duplicates.card_property"))
        self._card_person.title_label.setText(tr("page.duplicates.card_person"))
        self._card_resolved.title_label.setText(tr("page.duplicates.card_resolved"))

        # Type filter
        self._type_filter.blockSignals(True)
        cur_type = self._type_filter.currentData()
        self._type_filter.clear()
        self._type_filter.addItem(tr("page.duplicates.all_types"), "")
        self._type_filter.addItem(tr("page.duplicates.card_property"), "PropertyDuplicate")
        self._type_filter.addItem(tr("page.duplicates.card_person"), "PersonDuplicate")
        if cur_type:
            idx = self._type_filter.findData(cur_type)
            if idx >= 0:
                self._type_filter.setCurrentIndex(idx)
        self._type_filter.setLayoutDirection(direction)
        self._type_filter.blockSignals(False)

        # Status filter
        self._status_filter.blockSignals(True)
        cur_status = self._status_filter.currentData()
        self._status_filter.clear()
        self._status_filter.addItem(tr("page.duplicates.all_statuses"), "")
        self._status_filter.addItem(tr("page.duplicates.status_pending"), "Pending")
        self._status_filter.addItem(tr("page.duplicates.status_pending_review"), "PendingReview")
        self._status_filter.addItem(tr("page.duplicates.status_in_review"), "InReview")
        self._status_filter.addItem(tr("page.duplicates.status_resolved"), "Resolved")
        self._status_filter.addItem(tr("page.duplicates.status_auto_resolved"), "AutoResolved")
        self._status_filter.addItem(tr("page.duplicates.status_escalated"), "Escalated")
        if cur_status:
            idx = self._status_filter.findData(cur_status)
            if idx >= 0:
                self._status_filter.setCurrentIndex(idx)
        self._status_filter.setLayoutDirection(direction)
        self._status_filter.blockSignals(False)

        # Priority filter
        self._priority_filter.blockSignals(True)
        cur_priority = self._priority_filter.currentData()
        self._priority_filter.clear()
        self._priority_filter.addItem(tr("page.duplicates.all_priorities"), "")
        self._priority_filter.addItem(tr("page.duplicates.priority_critical"), "Critical")
        self._priority_filter.addItem(tr("page.duplicates.priority_high"), "High")
        self._priority_filter.addItem(tr("page.duplicates.priority_medium"), "Medium")
        self._priority_filter.addItem(tr("page.duplicates.priority_low"), "Low")
        if cur_priority:
            idx = self._priority_filter.findData(cur_priority)
            if idx >= 0:
                self._priority_filter.setCurrentIndex(idx)
        self._priority_filter.setLayoutDirection(direction)
        self._priority_filter.blockSignals(False)

        # Pagination
        self._prev_btn.setText(tr("page.duplicates.previous"))
        self._next_btn.setText(tr("page.duplicates.next"))
        self._count_label.setText(
            tr("page.duplicates.showing_count", shown=len(self._conflicts), total=len(self._conflicts))
        )

        # Empty state
        self._empty_state.set_title(tr("page.duplicates.no_conflicts"))
        self._empty_state.set_description(tr("page.duplicates.no_conflicts_hint"))

        # Import banner
        if hasattr(self, '_banner_msg'):
            self._banner_msg.setText(tr("page.duplicates.import_banner_msg"))
            self._banner_btn.setText(tr("page.duplicates.return_to_import"))

        # Reload cards to pick up new translations
        self._load_conflicts()
