# -*- coding: utf-8 -*-
"""
Sync & Data Page — صفحة المزامنة والبيانات
Displays all building assignments with sync status using animated cards,
sync pulse overlay, status change notifications, and unassign.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QComboBox,
    QPushButton, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QColor, QLinearGradient

from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from ui.components.icon import Icon
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.animated_card import AnimatedCard, animate_card_entrance
from ui.components.empty_state import EmptyState
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

def _get_status_config():
    return {
        'not_transferred': (tr("page.sync.status_pending"), '#9CA3AF', '#F3F4F6'),
        'pending': (tr("page.sync.status_pending"), '#9CA3AF', '#F3F4F6'),
        '0': (tr("page.sync.status_pending"), '#9CA3AF', '#F3F4F6'),
        'transferring': (tr("page.sync.status_syncing"), '#3890DF', '#EBF5FF'),
        'in_progress': (tr("page.sync.status_syncing"), '#3890DF', '#EBF5FF'),
        '1': (tr("page.sync.status_syncing"), '#3890DF', '#EBF5FF'),
        'transferred': (tr("page.sync.status_synced"), '#10B981', '#ECFDF5'),
        'completed': (tr("page.sync.status_synced"), '#10B981', '#ECFDF5'),
        '2': (tr("page.sync.status_synced"), '#10B981', '#ECFDF5'),
        'failed': (tr("page.sync.status_failed"), '#EF4444', '#FEF2F2'),
        '3': (tr("page.sync.status_failed"), '#EF4444', '#FEF2F2'),
        '4': (tr("page.sync.status_retrying"), '#F59E0B', '#FFFBEB'),
        'retry': (tr("page.sync.status_retrying"), '#F59E0B', '#FFFBEB'),
        '5': (tr("page.sync.status_cancelled"), '#6B7280', '#F9FAFB'),
        'cancelled': (tr("page.sync.status_cancelled"), '#6B7280', '#F9FAFB'),
    }

_SYNCING_STATUSES = {'transferring', 'in_progress', '1'}
_PENDING_STATUSES = {'not_transferred', 'pending', '0'}
_COMPLETED_STATUSES = {'transferred', 'completed', '2'}
_CANCELLED_STATUSES = {'cancelled', '5'}

# Status string -> strip color mapping
_STATUS_STRIP_COLOR = {
    'not_transferred': '#9CA3AF', 'pending': '#9CA3AF', '0': '#9CA3AF',
    'transferring': '#3890DF', 'in_progress': '#3890DF', '1': '#3890DF',
    'transferred': '#10B981', 'completed': '#10B981', '2': '#10B981',
    'failed': '#EF4444', '3': '#EF4444',
    '4': '#F59E0B', 'retry': '#F59E0B',
    '5': '#6B7280', 'cancelled': '#6B7280',
}

def _get_unit_type_ar():
    return {
        1: tr("page.sync.unit_apartment"), 2: tr("page.sync.unit_shop"),
        3: tr("page.sync.unit_office"), 4: tr("page.sync.unit_warehouse"), 5: tr("page.sync.unit_other"),
        "apartment": tr("page.sync.unit_apartment"), "shop": tr("page.sync.unit_shop"),
        "office": tr("page.sync.unit_office"), "warehouse": tr("page.sync.unit_warehouse"),
        "garage": tr("page.sync.unit_garage"), "other": tr("page.sync.unit_other"),
    }


class _SyncPulseOverlay(QWidget):
    """Blue sweep overlay for syncing card headers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self._sweep = 0.0

        self._anim = QPropertyAnimation(self, b"sweep")
        self._anim.setDuration(2200)
        self._anim.setStartValue(-0.3)
        self._anim.setEndValue(1.3)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def _get_sweep(self):
        return self._sweep

    def _set_sweep(self, val):
        self._sweep = val
        self.update()

    sweep = pyqtProperty(float, _get_sweep, _set_sweep)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        rect = self.rect()
        w = rect.width()

        # Base: visible blue tint
        painter.setBrush(QColor(56, 144, 223, 30))
        painter.drawRoundedRect(rect, 12, 12)

        # Sweep band (brighter) moves right-to-left (RTL)
        band_w = int(w * 0.35)
        center_x = int(w * (1.0 - self._sweep))
        bx = center_x - band_w // 2

        gradient = QLinearGradient(bx, 0, bx + band_w, 0)
        gradient.setColorAt(0.0, QColor(56, 144, 223, 0))
        gradient.setColorAt(0.5, QColor(56, 144, 223, 60))
        gradient.setColorAt(1.0, QColor(56, 144, 223, 0))

        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 12, 12)
        painter.end()

    def stop(self):
        self._anim.stop()


class _AssignmentCard(AnimatedCard):
    """Animated card for a building assignment.

    Row 1: Assignment/building info (bold) + status badge (top-right)
    Row 2: Collector name, building count, date (dot-separated)
    Row 3: Status chips (transferred/pending counts)
    """

    def __init__(self, assignment: dict, parent=None):
        self._assignment = assignment
        self._status_str = self._resolve_status(assignment)
        strip_color = _STATUS_STRIP_COLOR.get(self._status_str, '#9CA3AF')

        self._status_badge = None
        self._meta_lbl = None
        self._chip_transferred = None
        self._chip_pending = None

        super().__init__(
            parent,
            card_height=100,
            border_radius=12,
            show_chevron=True,
            show_strip=False,
            status_color=strip_color,
            strip_width=5,
            clickable=True,
        )

        self._assignment_id = self._resolve_id(assignment)

    @staticmethod
    def _resolve_status(assignment: dict) -> str:
        status = (
            assignment.get("transferStatusName")
            or assignment.get("transferStatus")
            or assignment.get("transfer_status")
            or "not_transferred"
        )
        return str(status).lower().replace(" ", "_")

    @staticmethod
    def _resolve_id(assignment: dict) -> str:
        return (
            assignment.get("id")
            or assignment.get("assignmentId")
            or assignment.get("assignment_id")
            or ""
        )

    def _build_content(self, layout: QVBoxLayout):
        a = self._assignment
        status_str = self._status_str

        # -- Row 1: building info + status badge --
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # Building icon
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(24), ScreenScale.h(24))
        icon_container.setStyleSheet(
            "QLabel { background-color: #EBF5FF; border-radius: 6px; border: none; }"
        )
        icon_container.setAlignment(Qt.AlignCenter)
        icon_pixmap = Icon.load_pixmap("building-03", size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            icon_container.setText("B")
            icon_container.setStyleSheet(
                "QLabel { background-color: #EBF5FF; border-radius: 6px; "
                "border: none; color: #3890DF; font-size: 10px; }"
            )
        row1.addWidget(icon_container)

        # Building code
        building_code = (
            a.get("buildingCode")
            or a.get("buildingId")
            or a.get("building_id")
            or "---"
        )
        title_lbl = QLabel(building_code)
        title_lbl.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet("color: #212B36; background: transparent; border: none;")
        row1.addWidget(title_lbl)

        row1.addStretch()

        # Status badge
        status_badge = QLabel()
        is_completed = status_str in _COMPLETED_STATUSES
        if is_completed:
            sync_date = (
                a.get("transferDate")
                or a.get("transfer_date")
                or a.get("assignedDate")
                or a.get("created_at")
                or ""
            )
            date_str = str(sync_date)[:10] if sync_date else ""
            status_badge.setText(date_str)
            status_badge.setFont(create_font(size=FontManager.SIZE_CAPTION, weight=QFont.Normal))
            status_badge.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
            )
        else:
            label, color, bg = _get_status_config().get(
                status_str, _get_status_config()['not_transferred']
            )
            status_badge.setText(label)
            status_badge.setFont(create_font(
                size=FontManager.SIZE_CAPTION,
                weight=FontManager.WEIGHT_SEMIBOLD
            ))
            status_badge.setAlignment(Qt.AlignCenter)
            status_badge.setFixedHeight(ScreenScale.h(22))
            status_badge.setMinimumWidth(ScreenScale.w(80))
            status_badge.setStyleSheet(StyleManager.status_badge(color, bg))

        self._status_badge = status_badge
        row1.addWidget(status_badge)
        layout.addLayout(row1)

        # -- Row 2: collector name + building count + date (dot-separated) --
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        parts = []

        researcher_name = (
            a.get("fieldCollectorName")
            or a.get("fieldCollectorNameAr")
            or a.get("assignedTo")
            or a.get("field_team_name")
            or ""
        )
        if researcher_name:
            parts.append(researcher_name)

        units_count = a.get("propertyUnitsCount") or a.get("unitsCount") or 0
        if units_count:
            parts.append(tr("page.sync.units_count", count=units_count))

        assigned_date = (
            a.get("assignedDate") or a.get("created_at") or ""
        )
        if assigned_date:
            parts.append(str(assigned_date)[:10])

        meta_text = "  \u00B7  ".join(parts) if parts else ""
        meta_lbl = QLabel(meta_text)
        meta_lbl.setFont(create_font(size=FontManager.SIZE_CAPTION, weight=FontManager.WEIGHT_REGULAR))
        meta_lbl.setStyleSheet("color: #637381; background: transparent; border: none;")
        self._meta_lbl = meta_lbl
        row2.addWidget(meta_lbl)
        row2.addStretch()
        layout.addLayout(row2)

        # -- Row 3: status chips --
        row3 = QHBoxLayout()
        row3.setSpacing(6)

        transferred_count = a.get("transferredCount") or a.get("syncedCount") or 0
        pending_count = a.get("pendingCount") or a.get("notTransferredCount") or 0

        if transferred_count:
            chip_transferred = QLabel(f"{tr('page.sync.status_synced')}: {transferred_count}")
            chip_transferred.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            chip_transferred.setStyleSheet(StyleManager.status_badge('#10B981', '#ECFDF5'))
            self._chip_transferred = chip_transferred
            row3.addWidget(chip_transferred)

        if pending_count:
            chip_pending = QLabel(f"{tr('page.sync.status_pending')}: {pending_count}")
            chip_pending.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            chip_pending.setStyleSheet(StyleManager.status_badge('#9CA3AF', '#F3F4F6'))
            self._chip_pending = chip_pending
            row3.addWidget(chip_pending)

        row3.addStretch()
        layout.addLayout(row3)

    def update_status(self, assignment: dict, new_status: str):
        """Update the status badge and strip color in-place."""
        self._status_str = new_status
        self._assignment = assignment

        strip_color = _STATUS_STRIP_COLOR.get(new_status, '#9CA3AF')
        self.set_status_color(strip_color)

        if not self._status_badge:
            return

        is_completed = new_status in _COMPLETED_STATUSES
        if is_completed:
            sync_date = (
                assignment.get("transferDate")
                or assignment.get("transfer_date")
                or assignment.get("assignedDate")
                or ""
            )
            date_str = str(sync_date)[:10] if sync_date else ""
            self._status_badge.setText(date_str)
            self._status_badge.setFixedHeight(ScreenScale.h(16777215))
            self._status_badge.setMinimumWidth(0)
            self._status_badge.setFont(create_font(size=FontManager.SIZE_CAPTION, weight=QFont.Normal))
            self._status_badge.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
            )
        else:
            label, color, bg = _get_status_config().get(
                new_status, _get_status_config()['not_transferred']
            )
            self._status_badge.setText(label)
            self._status_badge.setFont(create_font(
                size=FontManager.SIZE_CAPTION,
                weight=FontManager.WEIGHT_SEMIBOLD
            ))
            self._status_badge.setAlignment(Qt.AlignCenter)
            self._status_badge.setFixedHeight(ScreenScale.h(22))
            self._status_badge.setMinimumWidth(ScreenScale.w(80))
            self._status_badge.setStyleSheet(StyleManager.status_badge(color, bg))

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self.update_status(self._assignment, self._status_str)
        a = self._assignment
        parts = []
        researcher_name = (
            a.get("fieldCollectorName") or a.get("fieldCollectorNameAr")
            or a.get("assignedTo") or a.get("field_team_name") or ""
        )
        if researcher_name:
            parts.append(researcher_name)
        units_count = a.get("propertyUnitsCount") or a.get("unitsCount") or 0
        if units_count:
            parts.append(tr("page.sync.units_count", count=units_count))
        assigned_date = a.get("assignedDate") or a.get("created_at") or ""
        if assigned_date:
            parts.append(str(assigned_date)[:10])
        if self._meta_lbl:
            self._meta_lbl.setText("  \u00B7  ".join(parts) if parts else "")
        if self._chip_transferred:
            transferred_count = a.get("transferredCount") or a.get("syncedCount") or 0
            self._chip_transferred.setText(f"{tr('page.sync.status_synced')}: {transferred_count}")
        if self._chip_pending:
            pending_count = a.get("pendingCount") or a.get("notTransferredCount") or 0
            self._chip_pending.setText(f"{tr('page.sync.status_pending')}: {pending_count}")
        self.update()


class SyncDataPage(QWidget):
    """Page displaying all building assignments with sync status."""

    sync_notification = pyqtSignal(int)
    back_requested = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._collector_combo = None

        # Card state
        self._card_widgets = []             # list of _AssignmentCard
        self._card_map = {}                 # assignment_id -> _AssignmentCard
        self._sync_overlays = {}            # assignment_id -> _SyncPulseOverlay
        self._previous_statuses = {}        # assignment_id -> status_str
        self._current_items = []            # last API items
        self._pending_notifications = 0

        # Shimmer timer for card animation
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    # -- UI Setup --

    def _setup_ui(self):
        self.setStyleSheet("background-color: #f0f7ff;")
        self.setLayoutDirection(get_layout_direction())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.sync.title"))

        # Stat pills for status counts
        self._stat_pending = StatPill(tr("page.sync.status_pending"))
        self._header.add_stat_pill(self._stat_pending)

        self._stat_syncing = StatPill(tr("page.sync.status_syncing"))
        self._header.add_stat_pill(self._stat_syncing)

        self._stat_synced = StatPill(tr("page.sync.status_synced"))
        self._header.add_stat_pill(self._stat_synced)

        self._stat_failed = StatPill(tr("page.sync.status_failed"))
        self._header.add_stat_pill(self._stat_failed)

        # Collector filter combo in header (dark style)
        self._collector_combo = QComboBox()
        self._collector_combo.setFixedHeight(ScreenScale.h(34))
        self._collector_combo.setFixedWidth(ScreenScale.w(220))
        self._collector_combo.setEditable(True)
        self._collector_combo.lineEdit().setReadOnly(True)
        self._collector_combo.lineEdit().setPlaceholderText(tr("page.sync.all_collectors"))
        self._collector_combo.lineEdit().setAlignment(Qt.AlignCenter)
        self._collector_combo.setStyleSheet(StyleManager.dark_combo_box())
        self._collector_combo.currentIndexChanged.connect(self._on_collector_changed)
        self._header.add_row2_widget(self._collector_combo)

        # Back button in header actions
        self._back_btn = QPushButton(tr("action.back"))
        self._back_btn.setFixedSize(ScreenScale.w(100), ScreenScale.h(36))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self._back_btn.setStyleSheet(StyleManager.refresh_button_dark())
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._back_btn)

        # Refresh button in header actions
        self._refresh_btn = QPushButton(tr("page.sync.refresh"))
        self._refresh_btn.setFixedSize(ScreenScale.w(100), ScreenScale.h(36))
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self._refresh_btn.setStyleSheet(StyleManager.refresh_button_dark())
        self._refresh_btn.clicked.connect(self.refresh)
        self._header.add_action_widget(self._refresh_btn)

        main_layout.addWidget(self._header)

        # Accent line between header and content
        self._accent_line = AccentLine()
        main_layout.addWidget(self._accent_line)

        # Content area
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 16,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        content_layout.setSpacing(0)

        # Stacked widget: page 0 = scroll area, page 1 = empty state
        self._stack = QStackedWidget()

        # Page 0: Scroll area with card container
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
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

        # Page 1: Animated empty state
        self._empty_state = EmptyState(
            icon_name="data",
            title=tr("page.sync.no_assignments"),
            description="",
        )
        self._empty_state.setMinimumHeight(ScreenScale.h(260))
        self._stack.addWidget(self._empty_state)

        content_layout.addWidget(self._stack, 1)
        main_layout.addWidget(content_wrapper, 1)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _update_stat_pills(self):
        """Update stat pill counts from current assignment items."""
        pending = syncing = synced = failed = 0
        for item in self._current_items:
            status = self._normalize_status(item)
            if status in _PENDING_STATUSES:
                pending += 1
            elif status in _SYNCING_STATUSES:
                syncing += 1
            elif status in _COMPLETED_STATUSES:
                synced += 1
            elif status in {'failed', '3'}:
                failed += 1
        self._stat_pending.set_count(pending)
        self._stat_syncing.set_count(syncing)
        self._stat_synced.set_count(synced)
        self._stat_failed.set_count(failed)

    # -- Data loading --

    def _load_collectors(self):
        from services.api_client import get_api_client
        api = get_api_client()
        self._collectors_worker = ApiWorker(api.get_field_collectors)
        self._collectors_worker.finished.connect(self._on_collectors_loaded)
        self._collectors_worker.error.connect(
            lambda msg: logger.warning(f"Failed to load field collectors: {msg}")
        )
        self._collectors_worker.start()

    def _on_collectors_loaded(self, response):
        """Populate collector combo from API response."""
        try:
            collectors = (
                response if isinstance(response, list)
                else response.get("items", []) if isinstance(response, dict)
                else []
            )

            self._collector_combo.blockSignals(True)
            self._collector_combo.clear()
            self._collector_combo.addItem(tr("page.sync.all_collectors"), None)
            for c in collectors:
                name = (
                    c.get("fullNameArabic") or c.get("fullNameAr")
                    or c.get("fullNameEnglish") or c.get("fullName")
                    or c.get("full_name_ar") or c.get("full_name")
                    or c.get("username") or c.get("userName") or ""
                )
                cid = c.get("id") or c.get("userId") or c.get("user_id")
                if cid:
                    self._collector_combo.addItem(name or cid, cid)
            self._collector_combo.blockSignals(False)
        except Exception as e:
            logger.warning(f"Failed to process collectors response: {e}")

    def _on_collector_changed(self):
        self._load_assignments()

    def _filter_items_from_response(self, response) -> list:
        """Extract and filter assignment items from API response."""
        items = (
            response if isinstance(response, list)
            else response.get("items", []) if isinstance(response, dict)
            else []
        )
        selected_collector = (
            self._collector_combo.currentData()
            if self._collector_combo and self._collector_combo.currentIndex() > 0
            else None
        )
        if selected_collector:
            items = [
                a for a in items
                if (a.get("fieldCollectorId")
                    or a.get("field_collector_id")
                    or "") == selected_collector
            ]
        return items

    def _load_assignments(self):
        """Full rebuild of all card items (non-blocking)."""
        self._spinner.show_loading(tr("page.sync.loading_data"))
        self._clear_cards()

        from services.api_client import get_api_client
        api = get_api_client()
        self._assignments_worker = ApiWorker(api.get_all_assignments, page=1, page_size=100)
        self._assignments_worker.finished.connect(self._on_assignments_loaded)
        self._assignments_worker.error.connect(self._on_assignments_load_error)
        self._assignments_worker.start()

    def _on_assignments_loaded(self, response):
        """Handle assignment list API response."""
        try:
            items = self._filter_items_from_response(response)
            self._current_items = items
            self._clear_cards()

            if not items:
                self._empty_state.set_title(tr("page.sync.no_assignments"))
                self._stack.setCurrentIndex(1)
                return

            self._stack.setCurrentIndex(0)

            for assignment in items:
                aid = self._get_assignment_id(assignment)
                status_str = self._normalize_status(assignment)

                card = _AssignmentCard(assignment)
                card.clicked.connect(
                    lambda a=assignment, a_id=aid: self._on_card_clicked(a, a_id)
                )
                self._cards_layout.insertWidget(
                    self._cards_layout.count() - 1, card
                )
                self._card_widgets.append(card)
                self._card_map[aid] = card
                self._previous_statuses[aid] = status_str

                if status_str in _SYNCING_STATUSES:
                    self._add_sync_overlay(aid)

            self._update_stat_pills()
            animate_card_entrance(self._card_widgets)

            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()

        except Exception as e:
            logger.warning(f"Failed to load assignments: {e}")
            self._empty_state.set_title(tr("page.sync.load_failed"))
            self._stack.setCurrentIndex(1)
        finally:
            self._spinner.hide_loading()

    def _on_assignments_load_error(self, error_msg):
        """Handle assignment list API error."""
        logger.warning(f"Failed to load assignments: {error_msg}")
        self._empty_state.set_title(tr("page.sync.load_failed"))
        self._stack.setCurrentIndex(1)
        self._spinner.hide_loading()

    # -- Card click -> expand detail panel --

    def _on_card_clicked(self, assignment: dict, assignment_id: str):
        """Toggle detail panel below the clicked card."""
        card = self._card_map.get(assignment_id)
        if not card:
            return

        # Check if detail body already exists
        detail_key = f"_detail_{assignment_id}"
        detail_body = getattr(card, detail_key, None)

        if detail_body is not None:
            # Toggle visibility
            detail_body.setVisible(not detail_body.isVisible())
            return

        # Create new detail body below the card
        idx = self._cards_layout.indexOf(card)
        if idx < 0:
            return

        body = QFrame()
        body.setStyleSheet("""
            QFrame {
                background-color: #FBFCFF;
                border: 1px solid #E2EAF2;
                border-top: none;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(44, 8, 16, 12)
        body_layout.setSpacing(10)

        setattr(card, detail_key, body)
        self._cards_layout.insertWidget(idx + 1, body)

        # Load details asynchronously
        self._load_assignment_details(assignment_id, assignment, body)

    # -- Smart Refresh (polling every 10s) --

    def _smart_refresh(self):
        """Poll API and update status badges + overlays in-place (non-blocking)."""
        from services.api_client import get_api_client
        api = get_api_client()
        self._refresh_worker = ApiWorker(api.get_all_assignments, page=1, page_size=100)
        self._refresh_worker.finished.connect(self._on_smart_refresh_loaded)
        self._refresh_worker.error.connect(
            lambda msg: logger.debug(f"Smart refresh failed: {msg}")
        )
        self._refresh_worker.start()

    def _on_smart_refresh_loaded(self, response):
        """Process smart refresh API response."""
        try:
            items = self._filter_items_from_response(response)
        except Exception:
            return

        new_ids = set()
        needs_full_rebuild = False

        for assignment in items:
            aid = self._get_assignment_id(assignment)
            new_status = self._normalize_status(assignment)
            new_ids.add(aid)

            old_status = self._previous_statuses.get(aid)

            if aid not in self._card_map:
                needs_full_rebuild = True
                break

            # Status changed
            if old_status is not None and old_status != new_status:
                self._on_status_changed(assignment, old_status, new_status)
                self._update_card_status(aid, assignment, new_status)

                # Overlay management
                if new_status in _SYNCING_STATUSES and aid not in self._sync_overlays:
                    self._add_sync_overlay(aid)
                elif new_status not in _SYNCING_STATUSES and aid in self._sync_overlays:
                    self._remove_sync_overlay(aid)

            self._previous_statuses[aid] = new_status

        # Check for removed assignments
        old_ids = set(self._card_map.keys())
        if old_ids != new_ids:
            needs_full_rebuild = True

        if needs_full_rebuild:
            self._current_items = items
            self._load_assignments()

    def _on_status_changed(self, assignment: dict, old_status: str, new_status: str):
        """Notify navbar badge when an assignment's transfer status changes."""
        self._pending_notifications += 1
        self.sync_notification.emit(self._pending_notifications)

    def clear_notifications(self):
        """Clear pending notifications (called when page becomes visible)."""
        self._pending_notifications = 0
        self.sync_notification.emit(0)

    def _update_card_status(self, aid: str, assignment: dict, new_status: str):
        """Update the card's status badge and strip color in-place."""
        card = self._card_map.get(aid)
        if not card:
            return
        card.update_status(assignment, new_status)

    # -- Sync Pulse Overlay --

    def _add_sync_overlay(self, assignment_id: str):
        card = self._card_map.get(assignment_id)
        if not card or assignment_id in self._sync_overlays:
            return

        overlay = _SyncPulseOverlay(card)
        overlay.setGeometry(card.rect())
        overlay.show()
        self._sync_overlays[assignment_id] = overlay

        # Resize overlay when card resizes
        original_resize = card.resizeEvent

        def on_resize(event, ov=overlay, c=card, orig=original_resize):
            ov.setGeometry(c.rect())
            if orig:
                orig(event)

        card.resizeEvent = on_resize

    def _remove_sync_overlay(self, assignment_id: str):
        overlay = self._sync_overlays.pop(assignment_id, None)
        if overlay:
            overlay.stop()
            overlay.deleteLater()

    # -- Detail loading (lazy, on card click) --

    def _load_assignment_details(self, assignment_id: str, assignment: dict, body: QWidget):
        """Start background fetch of assignment details and units."""
        body_layout = body.layout()
        loading_label = QLabel(tr("page.sync.loading_details"))
        loading_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        loading_label.setStyleSheet("color: #637381; background: transparent; border: none;")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setObjectName("loadingIndicator")
        body_layout.addWidget(loading_label)

        self._detail_worker = ApiWorker(
            self._fetch_assignment_details, assignment_id, assignment
        )
        self._detail_worker.finished.connect(
            lambda result: self._on_details_loaded(result, assignment_id, assignment, body)
        )
        self._detail_worker.error.connect(
            lambda msg: self._on_details_load_error(msg, body)
        )
        self._detail_worker.start()

    @staticmethod
    def _fetch_assignment_details(assignment_id, assignment):
        """Fetch assignment details and units. Runs in background thread."""
        from services.api_client import get_api_client
        api = get_api_client()

        details = {}
        try:
            details = api.get_assignment(assignment_id) or {}
        except Exception as e:
            logger.debug(f"Could not fetch assignment details: {e}")

        building_id = (
            details.get("buildingId")
            or assignment.get("buildingId")
            or assignment.get("building_id")
            or ""
        )
        units = []
        if building_id:
            try:
                units = api.get_assignment_property_units(building_id)
                if not isinstance(units, list):
                    units = []
            except Exception as e:
                logger.debug(f"Could not fetch units: {e}")

        return {"details": details, "units": units}

    def _on_details_loaded(self, result, assignment_id, assignment, body):
        """Build detail UI from fetched data."""
        body_layout = body.layout()

        # Remove loading indicator
        for i in range(body_layout.count()):
            w = body_layout.itemAt(i)
            if w and w.widget() and w.widget().objectName() == "loadingIndicator":
                w.widget().deleteLater()
                break

        details = result.get("details", {})
        units = result.get("units", [])

        try:
            # Info section
            info_frame = QFrame()
            info_frame.setStyleSheet("""
                QFrame {
                    background-color: #F8FAFF;
                    border: 1px solid #E8EDF2;
                    border-radius: 8px;
                }
            """)
            info_layout = QVBoxLayout(info_frame)
            info_layout.setContentsMargins(12, 10, 12, 10)
            info_layout.setSpacing(8)

            researcher_name = (
                details.get("fieldCollectorName")
                or details.get("fieldCollectorNameAr")
                or assignment.get("fieldCollectorName")
                or assignment.get("fieldCollectorNameAr")
                or ""
            )
            building_count = details.get("buildingCount") or 1
            assigned_date = (
                details.get("assignedDate") or details.get("createdAt")
                or assignment.get("assignedDate") or assignment.get("created_at")
                or ""
            )
            date_str = str(assigned_date)[:10] if assigned_date else ""

            for label_text, value_text, value_color in [
                (tr("page.sync.field_researcher"), researcher_name, "#212B36"),
                (tr("page.sync.building_count"), str(building_count), "#3890DF"),
                (tr("page.sync.assignment_date"), date_str, "#212B36"),
            ]:
                row = QHBoxLayout()
                row.setSpacing(12)

                lbl = QLabel(label_text)
                lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                lbl.setStyleSheet("color: #637381; background: transparent; border: none;")
                lbl.setFixedWidth(ScreenScale.w(120))
                row.addWidget(lbl)

                val = QLabel(value_text)
                val.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
                val.setStyleSheet(f"color: {value_color}; background: transparent; border: none;")
                row.addWidget(val)

                row.addStretch()
                info_layout.addLayout(row)

            body_layout.addWidget(info_frame)

            if units:
                units_label = QLabel(tr("page.sync.property_units"))
                units_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                units_label.setStyleSheet("color: #637381; background: transparent; border: none;")
                body_layout.addWidget(units_label)

                for u in units:
                    unit_card = self._create_unit_card(u)
                    body_layout.addWidget(unit_card)

            # Unassign button (only for pending status)
            status_str = self._normalize_status(assignment)
            if status_str in _PENDING_STATUSES:
                btn_row = QHBoxLayout()
                btn_row.addStretch()

                unassign_btn = QPushButton(tr("page.sync.unassign"))
                unassign_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                unassign_btn.setCursor(Qt.PointingHandCursor)
                unassign_btn.setFixedHeight(ScreenScale.h(36))
                unassign_btn.setStyleSheet("""
                    QPushButton {
                        color: #EF4444;
                        background-color: #FEF2F2;
                        border: 1px solid #FECACA;
                        border-radius: 8px;
                        padding: 8px 20px;
                    }
                    QPushButton:hover {
                        background-color: #FEE2E2;
                    }
                """)
                unassign_btn.clicked.connect(
                    lambda _, aid=assignment_id: self._unassign_building(aid)
                )
                btn_row.addWidget(unassign_btn)
                btn_row.addStretch()
                body_layout.addLayout(btn_row)

        except Exception as e:
            logger.warning(f"Failed to build assignment details UI: {e}")
            err = QLabel(tr("page.sync.details_load_failed"))
            err.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            err.setStyleSheet("color: #EF4444; background: transparent; border: none;")
            err.setAlignment(Qt.AlignCenter)
            body_layout.addWidget(err)

    def _on_details_load_error(self, error_msg, body):
        """Handle failed assignment detail fetch."""
        logger.warning(f"Failed to load assignment details: {error_msg}")
        body_layout = body.layout()

        # Remove loading indicator
        for i in range(body_layout.count()):
            w = body_layout.itemAt(i)
            if w and w.widget() and w.widget().objectName() == "loadingIndicator":
                w.widget().deleteLater()
                break

        err = QLabel(tr("page.sync.details_load_failed"))
        err.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        err.setStyleSheet("color: #EF4444; background: transparent; border: none;")
        err.setAlignment(Qt.AlignCenter)
        body_layout.addWidget(err)

    # -- Unit card (same pattern as Step 3) --

    def _create_unit_card(self, unit_data: dict) -> QFrame:
        unit_type = unit_data.get('unitType') or unit_data.get('unit_type') or 'other'
        try:
            unit_type = int(unit_type)
        except (ValueError, TypeError):
            pass
        lookup_key = unit_type if isinstance(unit_type, int) else str(unit_type).lower()
        ar_type = _get_unit_type_ar().get(lookup_key, str(unit_type))

        unit_code = unit_data.get('unitCode') or unit_data.get('unit_code') or '-'
        floor = unit_data.get('floorNumber')
        floor_str = str(floor) if floor is not None else '-'
        description = unit_data.get('description') or ''
        has_survey = unit_data.get('hasCompletedSurvey', False)
        person_count = unit_data.get('personCount') or 0
        household_count = unit_data.get('householdCount') or 0
        claim_count = unit_data.get('claimCount') or 0

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E8EDF2;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        grid = QHBoxLayout()
        grid.setSpacing(0)

        data_points = [
            (tr("page.sync.unit_code"), unit_code),
            (tr("page.sync.floor"), floor_str),
            (tr("page.sync.type"), ar_type),
            (tr("page.sync.persons"), str(person_count)),
            (tr("page.sync.households"), str(household_count)),
            (tr("page.sync.claims"), str(claim_count)),
        ]

        for i, (label_text, value_text) in enumerate(data_points):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.setContentsMargins(6, 0, 6, 0)
            col.setAlignment(Qt.AlignCenter)

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            lbl.setStyleSheet("color: #9CA3AF;")
            lbl.setAlignment(Qt.AlignCenter)
            col.addWidget(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            val.setStyleSheet("color: #212B36;")
            val.setAlignment(Qt.AlignCenter)
            col.addWidget(val)

            grid.addLayout(col, stretch=1)

            if i < len(data_points) - 1:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setFixedHeight(ScreenScale.h(28))
                sep.setStyleSheet("background-color: #F0F0F0; border: none;")
                grid.addWidget(sep)

        card_layout.addLayout(grid)

        if description or has_survey is not None:
            bottom = QHBoxLayout()
            bottom.setSpacing(8)

            if description:
                desc = QLabel(description)
                desc.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
                desc.setStyleSheet("color: #637381;")
                desc.setWordWrap(True)
                bottom.addWidget(desc)

            bottom.addStretch()

            survey_text = tr("page.sync.survey_done") if has_survey else tr("page.sync.survey_not_done")
            survey_color = "#10B981" if has_survey else "#9CA3AF"
            survey_bg = "#ECFDF5" if has_survey else "#F3F4F6"
            survey_badge = QLabel(survey_text)
            survey_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            survey_badge.setStyleSheet(StyleManager.status_badge(survey_color, survey_bg))
            bottom.addWidget(survey_badge)

            card_layout.addLayout(bottom)

        return card

    # -- Unassign --

    def _unassign_building(self, assignment_id: str):
        from ui.error_handler import ErrorHandler

        if not ErrorHandler.confirm(
            self,
            tr("page.sync.confirm_unassign_message"),
            tr("page.sync.confirm_unassign_title"),
        ):
            return

        from services.api_client import get_api_client
        api = get_api_client()
        self._unassign_worker = ApiWorker(
            api.unassign_building, assignment_id, cancellation_reason=tr("page.sync.cancel_reason_supervisor")
        )
        self._unassign_worker.finished.connect(
            lambda _: self._on_unassign_success()
        )
        self._unassign_worker.error.connect(
            lambda msg: self._on_unassign_error(msg)
        )
        self._unassign_worker.start()

    def _on_unassign_success(self):
        """Handle successful unassign."""
        from ui.components.toast import Toast

        # رسالة نجاح
        Toast.show_toast(self.window(), tr("page.sync.unassign_success"), Toast.SUCCESS)

        # Invalidate building cache so map reflects updated assignment status
        try:
            from services.building_cache_service import BuildingCacheService
            BuildingCacheService.get_instance().invalidate_cache()
        except Exception:
            pass

        building_id = getattr(self, "_current_building_id", None)

        if building_id:
        
            if hasattr(self, "_already_selected_ids") and building_id in self._already_selected_ids:
                self._already_selected_ids.remove(building_id)

            if hasattr(self, "_selected_building_ids") and building_id in self._selected_building_ids:
                self._selected_building_ids.remove(building_id)

            if hasattr(self, "_confirmed_building_ids") and building_id in self._confirmed_building_ids:
                self._confirmed_building_ids.remove(building_id)

            if hasattr(self, "_selected_buildings") and building_id in self._selected_buildings:
                del self._selected_buildings[building_id]


            if hasattr(self, "_clear_cards"):
                self._clear_cards()

        self._load_assignments()


    def _on_unassign_error(self, error_msg):
        """Handle failed unassign."""
        from ui.components.toast import Toast
        logger.warning(f"Failed to unassign: {error_msg}")
        Toast.show_toast(self.window(), f"{tr('page.sync.unassign_failed')}: {error_msg}", Toast.ERROR)

    # -- Card management --

    def _clear_cards(self):
        """Remove all card widgets and stop overlays."""
        self._shimmer_timer.stop()

        # Stop all overlays
        for overlay in self._sync_overlays.values():
            overlay.stop()
            overlay.deleteLater()
        self._sync_overlays.clear()

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
            # Remove any detail bodies attached to the card
            for attr_name in list(vars(card)):
                if attr_name.startswith("_detail_"):
                    detail_body = getattr(card, attr_name, None)
                    if detail_body and isinstance(detail_body, QWidget):
                        detail_body.setParent(None)
                        detail_body.deleteLater()
            card.setParent(None)
            card.deleteLater()

        self._card_widgets.clear()
        self._card_map.clear()
        self._previous_statuses.clear()

    def _update_card_shimmer(self):
        """Trigger repaint on all visible cards for shimmer animation."""
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    # -- Helpers --

    @staticmethod
    def _get_assignment_id(assignment: dict) -> str:
        return (
            assignment.get("id")
            or assignment.get("assignmentId")
            or assignment.get("assignment_id")
            or ""
        )

    @staticmethod
    def _normalize_status(assignment: dict) -> str:
        status = (
            assignment.get("transferStatusName")
            or assignment.get("transferStatus")
            or assignment.get("transfer_status")
            or "not_transferred"
        )
        return str(status).lower().replace(" ", "_")

    def refresh(self, data=None):
        self._load_collectors()
        self._load_assignments()

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.sync.title"))
        self._back_btn.setText(tr("action.back"))
        self._refresh_btn.setText(tr("page.sync.refresh"))
        self._empty_state.set_title(tr("page.sync.no_assignments"))
        self._stat_pending.set_label(tr("page.sync.status_pending"))
        self._stat_syncing.set_label(tr("page.sync.status_syncing"))
        self._stat_synced.set_label(tr("page.sync.status_synced"))
        self._stat_failed.set_label(tr("page.sync.status_failed"))
        if self._collector_combo and self._collector_combo.lineEdit():
            self._collector_combo.lineEdit().setPlaceholderText(tr("page.sync.all_collectors"))
        if self._collector_combo and self._collector_combo.count() > 0:
            self._collector_combo.setItemText(0, tr("page.sync.all_collectors"))
        for card in self._card_widgets:
            card.update_language(is_arabic)

    def hideEvent(self, event):
        super().hideEvent(event)
