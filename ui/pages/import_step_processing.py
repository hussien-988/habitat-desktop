# -*- coding: utf-8 -*-
"""Import wizard — processing view (3-step flow, real-progress mode).

Drop-in replacement for the legacy ImportStep2Staging widget. The view is
strictly status-driven: the title and detail come from a fixed string per
backend status code (Pending / Validating / Staging / DetectingDuplicates /
ReviewingConflicts / ReadyToCommit / ValidationFailed / Quarantined). There
are NO rotating "fake progress" frames anymore — the previous cycle was
misleading because the backend does not expose per-validator signals.

What the user sees while a transient state is active:
  • Status badge in the header strip (real backend status)
  • One static title + detail describing what this state means
  • Spinner dots (proves UI is alive)
  • "بدء هذه المرحلة منذ: MM:SS" — local elapsed counter, reset on every
    sub-state change. This is HONEST: it measures wall-clock time spent in
    the current backend state, not made-up backend progress.
  • "● آخر استجابة من الخادم: قبل Ns" — heartbeat, fed by the wizard via
    set_heartbeat() on every poll response. Color of the dot reflects the
    last poll: green=ok, amber=slow (>3s latency), red=failed, grey=idle.

Stuck warnings and timeout decisions live in the wizard's top inline banner
(single source of truth for messages with action buttons), so this widget
no longer renders a stuck sub-state.

Constructor signature is kept drop-in compatible with the legacy
ImportStep2Staging (controller, package_id, duplicates_data, skip_load).
"""

from typing import Any, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QDateTime

from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from services.import_status_map import status_meta, PkgStatus
from ui.font_utils import create_font, FontManager
from ui.design_system import Colors, ScreenScale
from utils.logger import get_logger

logger = get_logger(__name__)


_SUB_STATE_PENDING = "pending"
_SUB_STATE_STAGING = "staging"
_SUB_STATE_VALIDATING = "validating"
_SUB_STATE_DETECTING = "detecting_duplicates"
_SUB_STATE_VALIDATION_FAILED = "validation_failed"
_SUB_STATE_QUARANTINED = "quarantined"
_SUB_STATE_REVIEWING_CONFLICTS = "reviewing_conflicts"
_SUB_STATE_READY = "ready_to_commit"


_STATUS_TO_SUB_STATE = {
    PkgStatus.PENDING: _SUB_STATE_PENDING,
    PkgStatus.VALIDATING: _SUB_STATE_VALIDATING,
    PkgStatus.STAGING: _SUB_STATE_STAGING,
    PkgStatus.VALIDATION_FAILED: _SUB_STATE_VALIDATION_FAILED,
    PkgStatus.QUARANTINED: _SUB_STATE_QUARANTINED,
    PkgStatus.REVIEWING_CONFLICTS: _SUB_STATE_REVIEWING_CONFLICTS,
    PkgStatus.READY_TO_COMMIT: _SUB_STATE_READY,
}


# A transient sub-state shows the spinner + elapsed counter + heartbeat.
_TRANSIENT_SUB_STATES = {
    _SUB_STATE_PENDING,
    _SUB_STATE_STAGING,
    _SUB_STATE_VALIDATING,
    _SUB_STATE_DETECTING,
}


def _format_mmss(seconds: int) -> str:
    s = max(0, int(seconds or 0))
    return f"{s // 60:02d}:{s % 60:02d}"


class ImportStepProcessing(QWidget):
    """Real-progress processing view. No rotating fake text."""

    resolve_duplicates_requested = pyqtSignal()

    def __init__(
        self,
        import_controller=None,
        package_id: str = "",
        duplicates_data: Optional[Dict[str, Any]] = None,
        skip_load: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id or ""
        self._duplicates_data = duplicates_data or {}
        self._current_status: Optional[int] = None
        self._current_sub_state: Optional[str] = None

        self._state_started_at: Optional[QDateTime] = None

        self._last_heartbeat_at: Optional[QDateTime] = None
        self._last_heartbeat_ok: Optional[bool] = None
        self._last_heartbeat_latency_ms: int = -1
        self._backend_updated_at_str: str = ""

        self._setup_ui()

        if not skip_load and self._package_id:
            QTimer.singleShot(0, self._load_package_summary)

    # -- UI ------------------------------------------------------------------

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            ScreenScale.w(40), ScreenScale.h(24),
            ScreenScale.w(40), ScreenScale.h(24),
        )
        root.setSpacing(ScreenScale.h(18))

        # Package summary strip
        summary = QFrame()
        summary.setStyleSheet(
            "QFrame { background: #F7FAFF; border: 1px solid #E2EAF2;"
            " border-radius: 12px; }"
        )
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(14)

        self._pkg_name_label = QLabel(tr("page.import_wizard.loading_package"))
        self._pkg_name_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._pkg_name_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        apply_label_alignment(self._pkg_name_label)
        summary_layout.addWidget(self._pkg_name_label, 1)

        self._pkg_status_badge = QLabel("")
        self._pkg_status_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._pkg_status_badge.setAlignment(Qt.AlignCenter)
        self._pkg_status_badge.setFixedHeight(ScreenScale.h(24))
        self._pkg_status_badge.setVisible(False)
        summary_layout.addWidget(self._pkg_status_badge)

        root.addWidget(summary)

        # Central state panel
        self._state_panel = QFrame()
        self._state_panel.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 1px solid #E2EAF2;"
            " border-radius: 14px; }"
        )
        self._state_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        state_layout = QVBoxLayout(self._state_panel)
        state_layout.setContentsMargins(32, 28, 32, 28)
        state_layout.setSpacing(12)
        state_layout.setAlignment(Qt.AlignCenter)

        self._state_icon = QLabel("⏳")
        self._state_icon.setAlignment(Qt.AlignCenter)
        self._state_icon.setFont(create_font(size=28, weight=FontManager.WEIGHT_BOLD))
        self._state_icon.setStyleSheet(
            "color: #3890DF; background: transparent; border: none;"
        )
        state_layout.addWidget(self._state_icon)

        self._state_title = QLabel(tr("wizard.import.processing.processing_label"))
        self._state_title.setAlignment(Qt.AlignCenter)
        self._state_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._state_title.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        state_layout.addWidget(self._state_title)

        self._state_detail = QLabel("")
        self._state_detail.setAlignment(Qt.AlignCenter)
        self._state_detail.setWordWrap(True)
        self._state_detail.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._state_detail.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        state_layout.addWidget(self._state_detail)

        # Spinner dots — proves the UI thread is alive.
        self._dots_label = QLabel("")
        self._dots_label.setAlignment(Qt.AlignCenter)
        self._dots_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._dots_label.setStyleSheet(
            "color: #3890DF; background: transparent; border: none;"
        )
        state_layout.addWidget(self._dots_label)

        # Real elapsed-in-state line.
        self._state_elapsed_label = QLabel("")
        self._state_elapsed_label.setAlignment(Qt.AlignCenter)
        self._state_elapsed_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._state_elapsed_label.setStyleSheet(
            "color: #1F2937; background: transparent; border: none;"
        )
        self._state_elapsed_label.setVisible(False)
        state_layout.addWidget(self._state_elapsed_label)

        self._heartbeat_label = QLabel("")
        self._heartbeat_label.setAlignment(Qt.AlignCenter)
        self._heartbeat_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._heartbeat_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self._heartbeat_label.setVisible(False)
        state_layout.addWidget(self._heartbeat_label)

        self._backend_updated_label = QLabel("")
        self._backend_updated_label.setAlignment(Qt.AlignCenter)
        self._backend_updated_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._backend_updated_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self._backend_updated_label.setVisible(False)
        state_layout.addWidget(self._backend_updated_label)

        self._conflict_box = QFrame()
        self._conflict_box.setStyleSheet(
            "QFrame { background: #FAF5FF; border: 1px solid #C4B5FD;"
            " border-radius: 10px; }"
        )
        conflict_layout = QVBoxLayout(self._conflict_box)
        conflict_layout.setContentsMargins(16, 12, 16, 12)
        conflict_layout.setSpacing(8)
        self._conflict_label = QLabel(
            tr("wizard.import.processing.conflicts_summary").format(count=0)
        )
        self._conflict_label.setAlignment(Qt.AlignCenter)
        self._conflict_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._conflict_label.setStyleSheet(
            "color: #6D28D9; background: transparent; border: none;"
        )
        conflict_layout.addWidget(self._conflict_label)

        self._resolve_btn = QPushButton(
            tr("wizard.import.processing.resolve_conflicts_btn")
        )
        self._resolve_btn.setCursor(Qt.PointingHandCursor)
        self._resolve_btn.setFixedHeight(ScreenScale.h(40))
        self._resolve_btn.setStyleSheet(
            "QPushButton { background: #8B5CF6; color: white;"
            " border: none; border-radius: 8px; padding: 8px 24px;"
            " font-size: 11pt; font-weight: 600; }"
            " QPushButton:hover { background: #7C3AED; }"
        )
        self._resolve_btn.clicked.connect(self.resolve_duplicates_requested.emit)
        conflict_layout.addWidget(self._resolve_btn)

        self._conflict_box.setVisible(False)
        state_layout.addWidget(self._conflict_box)

        root.addWidget(self._state_panel, 1)

        # Spinner dots animation timer.
        self._dots_count = 0
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._tick_dots)

        # Per-second tick that refreshes the elapsed + heartbeat lines.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._refresh_live_lines)

        self._apply_sub_state(_SUB_STATE_PENDING)

    # -- Public API ----------------------------------------------------------

    def set_status(self, status_code: int, extra: Optional[Dict[str, Any]] = None):
        """Update the view for a new backend status code."""
        self._current_status = status_code
        sub_state = _STATUS_TO_SUB_STATE.get(status_code, _SUB_STATE_PENDING)
        self._apply_sub_state(sub_state, extra=extra or {})

        meta = status_meta(status_code)
        self._pkg_status_badge.setText(tr(meta["label_key"]))
        self._pkg_status_badge.setStyleSheet(
            f"QLabel {{ background: {meta['bg_rgba']}; color: {meta['color_hex']};"
            f" border: 1px solid {meta['border_hex']}; border-radius: 12px;"
            f" padding: 0 12px; }}"
        )
        self._pkg_status_badge.setVisible(True)

    def set_conflict_count(self, count: int):
        """Called by the wizard when it detects conflicts for this package."""
        self._conflict_label.setText(
            tr("wizard.import.processing.conflicts_summary").format(count=int(count or 0))
        )
        if count and self._current_status == PkgStatus.REVIEWING_CONFLICTS:
            self._conflict_box.setVisible(True)

    def set_heartbeat(self, success: bool, latency_ms: int, backend_updated_at: str = ""):
        """Called by the wizard on every poll response."""
        self._last_heartbeat_at = QDateTime.currentDateTime()
        self._last_heartbeat_ok = bool(success)
        self._last_heartbeat_latency_ms = int(latency_ms if latency_ms is not None else -1)
        self._backend_updated_at_str = backend_updated_at or ""
        self._refresh_live_lines()

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        if self._current_status is not None:
            self.set_status(self._current_status)

    # -- Internal helpers ----------------------------------------------------

    def _load_package_summary(self):
        if not self.import_controller or not self._package_id:
            return
        try:
            result = self.import_controller.get_package(self._package_id)
        except Exception as e:
            logger.warning(f"Processing view: package load failed: {e}")
            return
        if not getattr(result, "success", False):
            return
        data = result.data or {}
        name = data.get("fileName") or data.get("packageName") or self._package_id
        self._pkg_name_label.setText(str(name))
        status = data.get("status", 0)
        if isinstance(status, str) and status.isdigit():
            status = int(status)
        if status:
            self.set_status(status)

    def _apply_sub_state(self, sub_state: str, extra: Optional[Dict[str, Any]] = None):
        # Reset state-elapsed timer whenever the sub-state actually changes,
        # so the counter reflects time spent in the CURRENT backend state.
        if sub_state != self._current_sub_state:
            logger.info(
                f"[import-flow] sub-state pkg={self._package_id} "
                f"{self._current_sub_state}→{sub_state}"
            )
            self._current_sub_state = sub_state
            self._state_started_at = QDateTime.currentDateTime()

        # Hide conflict CTA by default.
        self._conflict_box.setVisible(False)

        if sub_state == _SUB_STATE_PENDING:
            self._state_icon.setText("⏳")
            self._state_icon.setStyleSheet(
                "color: #6B7280; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.pending_title"))
            self._state_detail.setText(tr("wizard.import.processing.pending_detail"))
        elif sub_state == _SUB_STATE_VALIDATING:
            self._state_icon.setText("⚙")
            self._state_icon.setStyleSheet(
                "color: #3890DF; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.validating_title"))
            self._state_detail.setText(tr("wizard.import.processing.validating_detail"))
        elif sub_state == _SUB_STATE_STAGING:
            self._state_icon.setText("⚙")
            self._state_icon.setStyleSheet(
                "color: #F59E0B; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.staging_title"))
            self._state_detail.setText(tr("wizard.import.processing.staging_detail"))
        elif sub_state == _SUB_STATE_DETECTING:
            self._state_icon.setText("⚙")
            self._state_icon.setStyleSheet(
                "color: #8B5CF6; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.detecting_title"))
            self._state_detail.setText(tr("wizard.import.processing.detecting_detail"))
        elif sub_state == _SUB_STATE_VALIDATION_FAILED:
            self._state_icon.setText("⚠")
            self._state_icon.setStyleSheet(
                "color: #B91C1C; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.validation_failed_title"))
            self._state_detail.setText(tr("wizard.import.processing.validation_failed_detail"))
        elif sub_state == _SUB_STATE_QUARANTINED:
            self._state_icon.setText("🔒")
            self._state_icon.setStyleSheet(
                "color: #B91C1C; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.quarantined_title"))
            self._state_detail.setText(tr("wizard.import.processing.quarantined_detail"))
        elif sub_state == _SUB_STATE_REVIEWING_CONFLICTS:
            self._state_icon.setText("⚡")
            self._state_icon.setStyleSheet(
                "color: #6D28D9; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.conflicts_title"))
            self._state_detail.setText(tr("wizard.import.processing.conflicts_detail"))
            self._conflict_box.setVisible(True)
        elif sub_state == _SUB_STATE_READY:
            self._state_icon.setText("✓")
            self._state_icon.setStyleSheet(
                "color: #059669; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.ready_title"))
            self._state_detail.setText(tr("wizard.import.processing.ready_detail"))

        is_transient = sub_state in _TRANSIENT_SUB_STATES
        if is_transient:
            self._start_dots()
            self._state_elapsed_label.setVisible(True)
            self._heartbeat_label.setVisible(True)
            if not self._refresh_timer.isActive():
                self._refresh_timer.start()
            self._refresh_live_lines()
        else:
            self._stop_dots()
            self._refresh_timer.stop()
            self._state_elapsed_label.setVisible(False)
            self._heartbeat_label.setVisible(False)
            self._backend_updated_label.setVisible(False)

    def _refresh_live_lines(self):
        if self._state_started_at is not None:
            elapsed = max(0, int(self._state_started_at.secsTo(QDateTime.currentDateTime())))
            self._state_elapsed_label.setText(
                tr("wizard.import.processing.state_elapsed").format(time=_format_mmss(elapsed))
            )

        self._refresh_heartbeat_line()
        self._refresh_backend_updated_line()

    def _refresh_heartbeat_line(self):
        if self._last_heartbeat_at is None:
            self._heartbeat_label.setText(
                "● " + tr("wizard.import.processing.last_response_idle")
            )
            self._heartbeat_label.setStyleSheet(
                "color: #9CA3AF; background: transparent; border: none;"
            )
            return

        seconds_ago = max(0, int(self._last_heartbeat_at.secsTo(QDateTime.currentDateTime())))
        if self._last_heartbeat_ok:
            slow = self._last_heartbeat_latency_ms >= 0 and self._last_heartbeat_latency_ms > 3000
            color = "#F59E0B" if slow else "#10B981"
            self._heartbeat_label.setText(
                "● " + tr("wizard.import.processing.last_response_seconds_ago").format(
                    seconds=seconds_ago
                )
            )
            self._heartbeat_label.setStyleSheet(
                f"color: {color}; background: transparent; border: none;"
            )
        else:
            self._heartbeat_label.setText(
                "● " + tr("wizard.import.processing.last_response_failed").format(
                    seconds=seconds_ago
                )
            )
            self._heartbeat_label.setStyleSheet(
                "color: #DC2626; background: transparent; border: none;"
            )

    def _refresh_backend_updated_line(self):
        if not self._backend_updated_at_str:
            self._backend_updated_label.setVisible(False)
            return

        parsed = QDateTime.fromString(self._backend_updated_at_str, Qt.ISODate)
        if not parsed.isValid():
            parsed = QDateTime.fromString(self._backend_updated_at_str, Qt.ISODateWithMs)
        if not parsed.isValid():
            self._backend_updated_label.setVisible(False)
            return

        secs_ago = max(0, parsed.secsTo(QDateTime.currentDateTimeUtc()))
        if secs_ago < 60:
            text = tr("wizard.import.processing.backend_last_updated_seconds_ago").format(
                seconds=secs_ago
            )
        else:
            text = tr("wizard.import.processing.backend_last_updated_minutes_ago").format(
                minutes=secs_ago // 60
            )
        self._backend_updated_label.setText(text)
        self._backend_updated_label.setVisible(True)

    # -- Spinner dots --------------------------------------------------------

    def _start_dots(self):
        self._dots_count = 0
        if not self._dots_timer.isActive():
            self._dots_timer.start(400)

    def _stop_dots(self):
        self._dots_timer.stop()
        self._dots_label.setText("")

    def _tick_dots(self):
        self._dots_count = (self._dots_count + 1) % 4
        self._dots_label.setText("." * self._dots_count)

    # -- Lifecycle -----------------------------------------------------------

    def hideEvent(self, event):
        try:
            self._stop_dots()
            self._refresh_timer.stop()
        except Exception:
            pass
        super().hideEvent(event)
