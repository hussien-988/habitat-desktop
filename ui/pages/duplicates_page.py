# -*- coding: utf-8 -*-
"""Duplicates page for conflict resolution — dark header design system."""

import math
import random
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QRadioButton, QButtonGroup, QAbstractItemView,
    QSizePolicy, QTextEdit, QApplication, QComboBox,
    QScrollArea, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QThread, pyqtSignal as Signal,
    QTimer, QPoint,
)
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath,
)

from repositories.database import Database
from services.duplicate_service import DuplicateService
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction
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


RADIO_STYLE = f"""
    QRadioButton {{
        background: transparent;
        border: none;
        spacing: 0px;
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 2px solid #C4CDD5;
        background: {Colors.BACKGROUND};
    }}
    QRadioButton::indicator:hover {{
        border-color: {Colors.PRIMARY_BLUE};
    }}
    QRadioButton::indicator:checked {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 4px solid {Colors.PRIMARY_BLUE};
        background: {Colors.PRIMARY_BLUE};
    }}
"""

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
        self.setFixedHeight(86)
        self.setMinimumWidth(150)
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


# ---------------------------------------------------------------------------
#  Empty state (dark constellation)
# ---------------------------------------------------------------------------

class _EmptyStateConflicts(QWidget):
    """Dark constellation-themed empty state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(280)
        self._anim_start = time.time()

        random.seed(99)
        self._particles = []
        for _ in range(7):
            self._particles.append({
                "x": random.uniform(0.1, 0.9),
                "y": random.uniform(0.1, 0.9),
                "speed": random.uniform(0.3, 0.7),
                "phase": random.uniform(0, math.tau),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        self._title = QLabel(tr("page.duplicates.no_conflicts"))
        self._title.setFont(create_font(size=13, weight=QFont.Bold))
        self._title.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        self._subtitle = QLabel(tr("page.duplicates.no_conflicts_hint"))
        self._subtitle.setFont(create_font(size=10))
        self._subtitle.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")
        self._subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._subtitle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self._anim_start

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 16, 16)
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#0E2035"))
        grad.setColorAt(0.5, QColor("#132D50"))
        grad.setColorAt(1.0, QColor("#1A3860"))
        painter.fillPath(path, grad)
        painter.setClipPath(path)

        painter.setPen(QPen(QColor(56, 144, 223, 12), 1))
        for x in range(60, w, 60):
            painter.drawLine(x, 0, x, h)
        for y in range(60, h, 60):
            painter.drawLine(0, y, w, y)

        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.01 * math.sin(t * p["speed"] + p["phase"])) * w)
            py = int((p["y"] + 0.008 * math.cos(t * p["speed"] * 0.7 + p["phase"])) * h)
            px = max(4, min(w - 4, px))
            py = max(4, min(h - 4, py))
            positions.append((px, py))
            alpha = 28 + int(14 * math.sin(t * 1.2 + p["phase"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 180:
                    alpha = int(12 * (1 - dist / 180))
                    painter.setPen(QPen(QColor(139, 172, 200, alpha), 1))
                    painter.drawLine(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1],
                    )

        painter.setClipping(False)
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()


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
        self._selected_conflict_idx = -1
        self._detail_data = None
        self._exclude_resolved = False
        self._loading = False

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

        # Conflict list table card
        self._conflict_list_card = self._build_conflict_list()
        self._content_layout.addWidget(self._conflict_list_card)

        # Empty state (constellation)
        self._empty_state = _EmptyStateConflicts()
        self._content_layout.addWidget(self._empty_state)
        self._empty_state.setVisible(False)

        # Resolution section
        self._resolution_card = self._build_resolution_section()
        self._content_layout.addWidget(self._resolution_card)
        self._resolution_card.setVisible(False)

        self._content_layout.addStretch()

        content_layout.addWidget(scroll, 1)
        root.addWidget(content_area, 1)

        # Spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    # -- Import Banner -----------------------------------------------------

    def _build_import_banner(self) -> QFrame:
        banner = QFrame()
        banner.setFixedHeight(48)
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

        msg_lbl = QLabel(tr("page.duplicates.import_banner_msg"))
        msg_lbl.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        msg_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
        layout.addWidget(msg_lbl, 1)

        btn_return = QPushButton(tr("page.duplicates.return_to_import"))
        btn_return.setCursor(Qt.PointingHandCursor)
        btn_return.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        btn_return.setFixedSize(150, 36)
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
        self._card_overdue = _GlowCard(tr("page.duplicates.card_overdue"), 0, "#DC2626")

        self._summary_cards = [
            self._card_total, self._card_property, self._card_person,
            self._card_resolved, self._card_overdue,
        ]
        for card in self._summary_cards:
            layout.addWidget(card)

        self._card_total.clicked.connect(lambda: self._filter_by_card("all"))
        self._card_property.clicked.connect(lambda: self._filter_by_card("PropertyDuplicate"))
        self._card_person.clicked.connect(lambda: self._filter_by_card("PersonDuplicate"))
        self._card_resolved.clicked.connect(lambda: self._filter_by_card("Resolved"))
        self._card_overdue.clicked.connect(lambda: self._filter_by_card("overdue"))

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
            row.setFixedHeight(68)
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

    # -- Conflict List Table -----------------------------------------------

    def _build_conflict_list(self) -> QFrame:
        card = QFrame()
        card.setObjectName("conflictListCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setStyleSheet(
            StyleManager.table_card().replace("QFrame", "QFrame#conflictListCard")
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 18))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(0, 0, 0, 0)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setRowCount(0)
        self._table.setHorizontalHeaderLabels(self._table_header_labels())
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = self._table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setFixedHeight(52)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        vh = self._table.verticalHeader()
        vh.setDefaultSectionSize(50)

        self._table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: none;
                outline: none;
                font-size: 10pt;
                color: #212B36;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #F0F4F8;
                color: #212B36;
                font-size: 10pt;
            }
            QTableWidget::item:selected {
                background-color: #EBF5FF;
                color: #1F2937;
            }
            QTableWidget::item:hover {
                background-color: #F5F9FF;
            }
            QHeaderView {
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QHeaderView::section {
                background-color: #F0F7FF;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #E0EFFF;
                color: #3890DF;
                font-weight: 600;
                font-size: 9.5pt;
            }
            QHeaderView::section:hover {
                background-color: #E0EFFF;
            }
        """ + StyleManager.scrollbar())

        self._table.selectionModel().selectionChanged.connect(self._on_row_selected)
        card_layout.addWidget(self._table)

        # Footer with pagination
        footer = QFrame()
        footer.setFixedHeight(54)
        footer.setStyleSheet(
            StyleManager.nav_footer()
            + "QFrame { border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; }"
        )

        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 0, 16, 0)
        fl.setSpacing(10)

        self._prev_btn = QPushButton(tr("page.duplicates.previous"))
        self._prev_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setFixedHeight(34)
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
        self._next_btn.setFixedHeight(34)
        self._next_btn.setStyleSheet(_PAGINATION_BTN_STYLE)
        self._next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))
        fl.addWidget(self._next_btn)

        fl.addStretch()

        self._count_label = QLabel(tr("page.duplicates.showing_count", shown=0, total=0))
        self._count_label.setFont(create_font(size=9))
        self._count_label.setStyleSheet("color: #78909C; background: transparent; border: none;")
        fl.addWidget(self._count_label)

        card_layout.addWidget(footer)

        return card

    @staticmethod
    def _table_header_labels():
        return [
            tr("page.duplicates.col_conflict_number"),
            tr("page.duplicates.col_type"),
            tr("page.duplicates.col_first_record"),
            tr("page.duplicates.col_second_record"),
            tr("page.duplicates.col_match_score"),
            tr("page.duplicates.col_priority"),
            tr("page.duplicates.col_status"),
            tr("page.duplicates.col_date"),
        ]

    # -- Resolution Section ------------------------------------------------

    def _build_resolution_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("resolutionCard")
        card.setStyleSheet(
            StyleManager.form_card().replace("QFrame", "QFrame#resolutionCard")
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 15))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(20, 18, 20, 18)

        # Title row
        title_row = QHBoxLayout()
        self._resolution_title = QLabel(tr("page.duplicates.resolution_action"))
        self._resolution_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._resolution_title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        self._conflict_info_label = QLabel("")
        self._conflict_info_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._conflict_info_label.setStyleSheet("color: #78909C; background: transparent; border: none;")

        self._view_details_btn = QPushButton(tr("page.duplicates.view_details"))
        self._view_details_btn.setCursor(Qt.PointingHandCursor)
        self._view_details_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._view_details_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.PRIMARY_BLUE};
                background: {Colors.PRIMARY_BLUE}0D;
                border: 1px solid {Colors.PRIMARY_BLUE}33;
                border-radius: 8px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background: {Colors.PRIMARY_BLUE}1A;
                border-color: {Colors.PRIMARY_BLUE}66;
            }}
        """)
        self._view_details_btn.clicked.connect(self._on_view_details)

        title_row.addWidget(self._resolution_title)
        title_row.addWidget(self._conflict_info_label)
        title_row.addStretch()
        title_row.addWidget(self._view_details_btn)
        card_layout.addLayout(title_row)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #F0F4F8;")
        card_layout.addWidget(sep)

        # Comparison preview
        self._comparison_frame = QFrame()
        self._comparison_frame.setStyleSheet(StyleManager.data_card())
        comp_layout = QHBoxLayout(self._comparison_frame)
        comp_layout.setContentsMargins(16, 12, 16, 12)
        comp_layout.setSpacing(20)

        self._record_a_frame = self._build_record_preview(tr("page.duplicates.col_first_record"))
        comp_layout.addWidget(self._record_a_frame, 1)

        vs_label = QLabel("VS")
        vs_label.setAlignment(Qt.AlignCenter)
        vs_label.setFixedWidth(50)
        vs_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_BOLD))
        vs_label.setStyleSheet(f"""
            color: {Colors.PRIMARY_BLUE};
            background: {Colors.PRIMARY_BLUE}12;
            border-radius: 25px;
            padding: 8px;
            border: none;
        """)
        comp_layout.addWidget(vs_label)

        self._record_b_frame = self._build_record_preview(tr("page.duplicates.col_second_record"))
        comp_layout.addWidget(self._record_b_frame, 1)

        card_layout.addWidget(self._comparison_frame)

        # Interactive zone (hidden for resolved conflicts)
        self._interactive_zone = QWidget()
        self._interactive_zone.setStyleSheet("background: transparent;")
        iz_layout = QVBoxLayout(self._interactive_zone)
        iz_layout.setContentsMargins(0, 0, 0, 0)
        iz_layout.setSpacing(10)

        # Resolution options
        self._resolution_group = QButtonGroup(self)
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        for idx, (label, value) in enumerate([
            (tr("page.duplicates.merge_records"), "merge"),
            (tr("page.duplicates.keep_separate"), "keep_separate"),
        ]):
            radio = QRadioButton(label)
            radio.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            radio.setStyleSheet(RADIO_STYLE + " QRadioButton { padding: 8px 14px; }")
            radio.setProperty("resolution_type", value)
            self._resolution_group.addButton(radio, idx)
            options_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

        options_layout.addStretch()

        self._master_label = QLabel(tr("page.duplicates.master_record"))
        self._master_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._master_label.setStyleSheet("color: #78909C; background: transparent; border: none;")

        self._master_combo = QComboBox()
        self._master_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid #E5E7EB;
                border-radius: 8px;
                padding: 4px 12px;
                background: #FAFBFC;
                color: #374151;
                min-width: 180px;
            }}
            QComboBox:hover {{ border-color: {Colors.PRIMARY_BLUE}88; }}
        """)
        self._master_combo.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))

        options_layout.addWidget(self._master_label)
        options_layout.addWidget(self._master_combo)
        iz_layout.addLayout(options_layout)

        self._resolution_group.buttonClicked.connect(self._on_resolution_type_changed)

        # Justification
        just_label = QLabel(tr("page.duplicates.justification_label"))
        just_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        just_label.setStyleSheet("color: #78909C; background: transparent; border: none;")
        iz_layout.addWidget(just_label)

        self._justification_edit = QTextEdit()
        self._justification_edit.setPlaceholderText(tr("page.duplicates.justification_placeholder"))
        self._justification_edit.setFixedHeight(72)
        self._justification_edit.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._justification_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1.5px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px;
                background: #FAFBFC;
                color: #333;
            }}
            QTextEdit:focus {{
                border-color: {Colors.PRIMARY_BLUE};
                background: white;
            }}
        """)
        iz_layout.addWidget(self._justification_edit)

        # Action button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._action_btn = QPushButton(tr("page.duplicates.execute_action"))
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._action_btn.setFixedSize(160, 44)
        self._action_btn.setStyleSheet(StyleManager.dark_action_button())
        self._action_btn.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self._action_btn)

        iz_layout.addLayout(btn_layout)
        card_layout.addWidget(self._interactive_zone)

        # Resolved summary (shown instead of interactive zone for resolved conflicts)
        self._resolved_summary_frame = QFrame()
        self._resolved_summary_frame.setStyleSheet(
            StyleManager.data_card()
            + " QLabel { background: transparent; border: none; }"
        )
        self._resolved_summary_frame.setVisible(False)
        rs_layout = QVBoxLayout(self._resolved_summary_frame)
        rs_layout.setContentsMargins(16, 14, 16, 14)
        rs_layout.setSpacing(10)

        # Status banner
        self._rs_status_label = QLabel("")
        self._rs_status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_BOLD))
        self._rs_status_label.setAlignment(Qt.AlignCenter)
        self._rs_status_label.setFixedHeight(32)
        self._rs_status_label.setStyleSheet(
            "border-radius: 6px; padding: 4px 12px;"
        )
        rs_layout.addWidget(self._rs_status_label)

        # Info rows
        self._rs_type_row = self._make_summary_row()
        self._rs_master_row = self._make_summary_row()
        self._rs_just_row = self._make_summary_row()
        self._rs_date_row = self._make_summary_row()
        for row_w in (self._rs_type_row, self._rs_master_row, self._rs_just_row, self._rs_date_row):
            rs_layout.addWidget(row_w)

        card_layout.addWidget(self._resolved_summary_frame)

        return card

    def _build_record_preview(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet("color: #78909C; background: transparent;")
        layout.addWidget(title_lbl)

        id_lbl = QLabel("-")
        id_lbl.setObjectName("record_id")
        id_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_BOLD))
        id_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent;")
        layout.addWidget(id_lbl)

        desc_lbl = QLabel("-")
        desc_lbl.setObjectName("record_desc")
        desc_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        desc_lbl.setStyleSheet("color: #6B7280; background: transparent;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        return frame

    def _make_summary_row(self) -> QWidget:
        """Create a key-value row widget for the resolved summary panel."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        key_lbl = QLabel("")
        key_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        key_lbl.setStyleSheet("color: #78909C; background: transparent; border: none;")
        key_lbl.setFixedWidth(130)
        val_lbl = QLabel("")
        val_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        val_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        val_lbl.setWordWrap(True)
        row.addWidget(key_lbl)
        row.addWidget(val_lbl, 1)
        w.key_lbl = key_lbl
        w.val_lbl = val_lbl
        return w

    def _populate_resolved_summary(self, conflict: dict):
        """Fill the resolved summary panel from conflict data."""
        status = conflict.get("status", "")
        is_auto = status.lower() == "autoresolved"
        status_colors = {
            "resolved": ("#22C55E", "#F0FDF4"),
            "autoresolved": ("#A855F7", "#FAF5FF"),
        }
        fg, bg = status_colors.get(status.lower(), ("#22C55E", "#F0FDF4"))
        status_text = tr("page.duplicates.status_autoresolved") if is_auto else tr("page.duplicates.status_resolved")
        self._rs_status_label.setText(status_text)
        self._rs_status_label.setStyleSheet(
            f"border-radius: 6px; padding: 4px 12px; color: {fg}; background: {bg}; border: 1px solid {fg}33;"
        )

        res_type = conflict.get("resolutionType", "") or ""
        if res_type in ("merge_records", "merge"):
            type_display = tr("page.duplicates.merge_records")
        elif res_type in ("keep_separate",):
            type_display = tr("page.duplicates.keep_separate")
        else:
            type_display = res_type or "-"

        master_id = conflict.get("masterRecordId") or conflict.get("masterEntityId") or "-"
        justification = conflict.get("justification") or conflict.get("resolutionNotes") or "-"
        resolved_at = str(conflict.get("resolvedAt") or conflict.get("resolvedDate") or "")[:10] or "-"
        resolved_by = conflict.get("resolvedBy") or conflict.get("resolvedByUser") or "-"
        meta = f"{resolved_at}  |  {resolved_by}" if resolved_by != "-" else resolved_at

        for row_w, key_txt, val_txt, visible in [
            (self._rs_type_row, tr("page.duplicates.resolution_type"), type_display, bool(res_type)),
            (self._rs_master_row, tr("page.duplicates.master_record"), str(master_id),
             res_type in ("merge_records", "merge")),
            (self._rs_just_row, tr("page.duplicates.justification_label"), justification, True),
            (self._rs_date_row, tr("page.duplicates.resolved_meta"), meta, resolved_at != "-"),
        ]:
            row_w.key_lbl.setText(key_txt)
            row_w.val_lbl.setText(val_txt)
            row_w.setVisible(visible)

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
        self._conflict_list_card.setVisible(False)
        self._empty_state.setVisible(False)
        self._resolution_card.setVisible(False)

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
        self._card_overdue.update_count(summary.get("overdueCount", 0))

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
            self._conflict_list_card.setVisible(True)
            self._empty_state.setVisible(False)
            self._populate_table()
        else:
            self._conflict_list_card.setVisible(False)
            self._empty_state.setVisible(True)

        self._update_pagination()

    def _on_load_error(self, error_msg: str):
        self._loading = False
        self._spinner.hide_loading()

        for s in self._shimmer_widgets:
            s.stop()
        self._shimmer_container.setVisible(False)

        self._conflicts = []
        self._conflict_list_card.setVisible(False)
        self._empty_state.setVisible(True)
        Toast.show_toast(self, tr("page.duplicates.load_failed", error=error_msg), Toast.ERROR)
        logger.error("Conflict load error: %s", error_msg)

    # -- Table Population --------------------------------------------------

    def _populate_table(self):
        self._selected_conflict_idx = -1
        self._resolution_card.setVisible(False)

        self._table.setRowCount(len(self._conflicts))

        for row_idx, conflict in enumerate(self._conflicts):
            # Conflict number
            num_item = QTableWidgetItem(conflict.get("conflictNumber", "-"))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
            self._table.setItem(row_idx, 0, num_item)

            # Type
            ctype = conflict.get("conflictType", "")
            type_cfg = _get_type_config(ctype) if ctype else {"label": "-"}
            type_item = QTableWidgetItem(type_cfg["label"])
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            self._table.setItem(row_idx, 1, type_item)

            # First entity
            first_id = conflict.get("firstEntityIdentifier", conflict.get("firstEntityId", "-"))
            first_item = QTableWidgetItem(str(first_id))
            first_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 2, first_item)

            # Second entity
            second_id = conflict.get("secondEntityIdentifier", conflict.get("secondEntityId", "-"))
            second_item = QTableWidgetItem(str(second_id))
            second_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 3, second_item)

            # Similarity score
            score = conflict.get("similarityScore", 0)
            score_pct = f"{score * 100:.0f}%" if isinstance(score, float) and score <= 1 else f"{score}%"
            score_item = QTableWidgetItem(score_pct)
            score_item.setTextAlignment(Qt.AlignCenter)
            score_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
            sv = score if isinstance(score, (int, float)) else 0
            score_color = "#EF4444" if sv >= 0.9 else "#F59E0B" if sv >= 0.7 else "#6B7280"
            score_item.setForeground(QColor(score_color))
            self._table.setItem(row_idx, 4, score_item)

            # Priority
            priority = conflict.get("priority", "Medium")
            pri_cfg = _get_priority_config(priority) if priority else {"label": "-", "color": "#6B7280"}
            pri_item = QTableWidgetItem(pri_cfg["label"])
            pri_item.setTextAlignment(Qt.AlignCenter)
            pri_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            pri_item.setForeground(QColor(pri_cfg["color"]))
            self._table.setItem(row_idx, 5, pri_item)

            # Status
            status = conflict.get("status", "Pending")
            st_cfg = _get_status_config(status) if status else {"label": "-", "color": "#6B7280"}
            st_item = QTableWidgetItem(st_cfg["label"])
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            st_item.setForeground(QColor(st_cfg["color"]))
            self._table.setItem(row_idx, 6, st_item)

            # Date
            date_str = conflict.get("detectedDate", conflict.get("assignedDate", ""))
            if date_str and "T" in str(date_str):
                date_str = str(date_str).split("T")[0]
            date_item = QTableWidgetItem(str(date_str))
            date_item.setTextAlignment(Qt.AlignCenter)
            date_item.setFont(create_font(size=8))
            date_item.setForeground(QColor("#9CA3AF"))
            self._table.setItem(row_idx, 7, date_item)

    # -- Selection & Resolution --------------------------------------------

    def _on_row_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._selected_conflict_idx = -1
            self._resolution_card.setVisible(False)
            return

        idx = rows[0].row()
        if idx >= len(self._conflicts):
            self._table.clearSelection()
            self._selected_conflict_idx = -1
            self._resolution_card.setVisible(False)
            return

        self._selected_conflict_idx = idx
        conflict = self._conflicts[idx]

        self._resolution_card.setVisible(True)

        cnum = conflict.get("conflictNumber", "")
        ctype = conflict.get("conflictType", "")
        type_cfg = _get_type_config(ctype) if ctype else {"label": "-"}
        self._conflict_info_label.setText(f"#{cnum} \u2014 {type_cfg['label']}")

        first_id = conflict.get("firstEntityIdentifier", conflict.get("firstEntityId", "-"))
        second_id = conflict.get("secondEntityIdentifier", conflict.get("secondEntityId", "-"))

        a_id = self._record_a_frame.findChild(QLabel, "record_id")
        a_desc = self._record_a_frame.findChild(QLabel, "record_desc")
        b_id = self._record_b_frame.findChild(QLabel, "record_id")
        b_desc = self._record_b_frame.findChild(QLabel, "record_desc")

        if a_id:
            a_id.setText(str(first_id))
        if a_desc:
            a_desc.setText(tr("page.duplicates.identifier", id=conflict.get("firstEntityId", "-")))
        if b_id:
            b_id.setText(str(second_id))
        if b_desc:
            b_desc.setText(tr("page.duplicates.identifier", id=conflict.get("secondEntityId", "-")))

        self._master_combo.clear()
        self._master_combo.addItem(
            tr("page.duplicates.first_record_id", id=first_id),
            conflict.get("firstEntityId", ""),
        )
        self._master_combo.addItem(
            tr("page.duplicates.second_record_id", id=second_id),
            conflict.get("secondEntityId", ""),
        )

        is_resolved = conflict.get("status", "").lower() in ("resolved", "autoresolved")
        self._interactive_zone.setVisible(not is_resolved)
        self._resolved_summary_frame.setVisible(is_resolved)
        if is_resolved:
            self._populate_resolved_summary(conflict)
            return

        self._justification_edit.clear()
        self._on_resolution_type_changed()

    def _on_resolution_type_changed(self):
        selected = self._resolution_group.checkedButton()
        if not selected:
            return
        is_merge = selected.property("resolution_type") == "merge"
        self._master_label.setVisible(is_merge)
        self._master_combo.setVisible(is_merge)

    def _on_action_clicked(self):
        if self._selected_conflict_idx < 0 or self._selected_conflict_idx >= len(self._conflicts):
            Toast.show_toast(self, tr("page.duplicates.select_conflict"), Toast.WARNING)
            return

        justification = self._justification_edit.toPlainText().strip()
        if not justification:
            Toast.show_toast(self, tr("page.duplicates.enter_justification"), Toast.WARNING)
            return

        selected_radio = self._resolution_group.checkedButton()
        if not selected_radio:
            Toast.show_toast(self, tr("page.duplicates.select_action_type"), Toast.WARNING)
            return

        resolution_type = selected_radio.property("resolution_type")
        conflict = self._conflicts[self._selected_conflict_idx]
        conflict_id = conflict.get("id", "")

        action_labels = {
            "merge": tr("page.duplicates.merge_records"),
            "keep_separate": tr("page.duplicates.keep_records_separate"),
        }
        action_label = action_labels.get(resolution_type, tr("page.duplicates.execute_action"))

        from ui.error_handler import ErrorHandler
        if not ErrorHandler.confirm(
            self,
            tr("page.duplicates.confirm_action_msg", action=action_label),
            tr("page.duplicates.confirm_action_title"),
        ):
            return

        master_id = ""
        if resolution_type == "merge":
            master_id = self._master_combo.currentData()
            if not master_id:
                Toast.show_toast(self, tr("page.duplicates.select_master_record"), Toast.WARNING)
                return

        self._action_btn.setEnabled(False)
        self._spinner.show_loading(tr("page.duplicates.executing_action"))
        self._resolution_worker = _ResolutionWorker(
            self.duplicate_service, resolution_type,
            conflict_id, justification, master_id,
        )
        self._resolution_worker.finished.connect(self._on_resolution_finished)
        self._resolution_worker.error.connect(self._on_resolution_error)
        self._resolution_worker.start()

    def _on_resolution_finished(self, success: bool):
        self._spinner.hide_loading()
        self._action_btn.setEnabled(True)
        if success:
            self._justification_edit.clear()
            Toast.show_toast(self, tr("page.duplicates.action_success"), Toast.SUCCESS)
            self._load_conflicts()
        else:
            Toast.show_toast(self, tr("page.duplicates.action_failed"), Toast.ERROR)

    def _on_resolution_error(self, error_msg: str):
        self._spinner.hide_loading()
        self._action_btn.setEnabled(True)
        Toast.show_toast(
            self, tr("page.duplicates.action_failed_detail", error=error_msg), Toast.ERROR
        )

    def _on_view_details(self):
        if self._selected_conflict_idx < 0:
            return
        conflict = self._conflicts[self._selected_conflict_idx]
        self._spinner.show_loading()
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
        elif card_type == "overdue":
            self._type_filter.setCurrentIndex(0)
            self._status_filter.setCurrentIndex(0)
            self._card_overdue.set_active(True)

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
        super().hideEvent(event)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.duplicates.title"))
        self._stat_pending.set_label(tr("page.duplicates.stat_pending"))
        self._refresh_btn.setText(tr("page.duplicates.refresh"))
