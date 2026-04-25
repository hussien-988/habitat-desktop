# -*- coding: utf-8 -*-
"""Import wizard — processing view (new 3-step flow).

This replaces the legacy `import_step2_staging.py` which showed an
ad-hoc validation summary (zeros table + "clean data" banner) that
confused users during the wizard's processing phase.

The new widget is minimal and status-driven:

  • Package summary strip at the top
  • Centered state panel:
        - animated spinner + "processing…" label for transient backend work
        - conflict count card + "Resolve Conflicts" button when
          the backend reports ReviewingConflicts
        - error panel (filled from the wizard's inline banner for
          stage/detect failures)

The widget intentionally does NOT show a validation-report table —
that belongs in Step 2 (Review & Approve), not in Step 1 processing.

Constructor signature is kept drop-in compatible with the legacy
ImportStep2Staging (controller, package_id, duplicates_data, skip_load)
so the wizard's _ensure_step2 only needed to swap the import.
"""

from typing import Any, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

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


# Backend-truthful micro-stage cycle.
# Backend status `Staging` covers BOTH unpacking AND the 8-level validation
# pipeline (no per-level signal exposed by the API). We rotate through copy
# that mirrors what the server is actually doing — matching the order of the
# real validators in TRRCMS-Backend/src/TRRCMS.Infrastructure/Services/Validators.
# Cycle advances every 5s. Text-only — no icon changes, no timer display.
_STAGING_CYCLE = [
    ("wizard.import.processing.staging.cycle.1.title",
     "wizard.import.processing.staging.cycle.1.detail"),
    ("wizard.import.processing.staging.cycle.2.title",
     "wizard.import.processing.staging.cycle.2.detail"),
    ("wizard.import.processing.staging.cycle.3.title",   # ~ L1 DataConsistency
     "wizard.import.processing.staging.cycle.3.detail"),
    ("wizard.import.processing.staging.cycle.4.title",   # ~ L2 CrossEntityRelation
     "wizard.import.processing.staging.cycle.4.detail"),
    ("wizard.import.processing.staging.cycle.5.title",   # ~ L3 OwnershipEvidence
     "wizard.import.processing.staging.cycle.5.detail"),
    ("wizard.import.processing.staging.cycle.6.title",   # ~ L4 HouseholdStructure
     "wizard.import.processing.staging.cycle.6.detail"),
    ("wizard.import.processing.staging.cycle.7.title",   # ~ L5 SpatialGeometry
     "wizard.import.processing.staging.cycle.7.detail"),
    ("wizard.import.processing.staging.cycle.8.title",   # ~ L6 ClaimLifecycle
     "wizard.import.processing.staging.cycle.8.detail"),
    ("wizard.import.processing.staging.cycle.9.title",   # ~ L7 VocabularyVersion
     "wizard.import.processing.staging.cycle.9.detail"),
    ("wizard.import.processing.staging.cycle.10.title",  # ~ L8 BuildingUnitCode
     "wizard.import.processing.staging.cycle.10.detail"),
    ("wizard.import.processing.staging.cycle.11.title",  # duplicate detection
     "wizard.import.processing.staging.cycle.11.detail"),
    ("wizard.import.processing.staging.cycle.12.title",  # finalising
     "wizard.import.processing.staging.cycle.12.detail"),
]

# When the package is at status=Validating, we have just fired POST /stage.
# This brief window before the backend flips to Staging shows a "starting"
# message.
_VALIDATING_CYCLE = [
    ("wizard.import.processing.validating.cycle.1.title",
     "wizard.import.processing.validating.cycle.1.detail"),
    ("wizard.import.processing.validating.cycle.2.title",
     "wizard.import.processing.validating.cycle.2.detail"),
]

# Committing — wizard's _handle_committing already routes to the commit
# step (internal index 2) which has its own progress UI; this list is a
# fallback in case the processing widget receives a Committing status.
_COMMITTING_CYCLE = [
    ("wizard.import.processing.committing.cycle.1.title",
     "wizard.import.processing.committing.cycle.1.detail"),
    ("wizard.import.processing.committing.cycle.2.title",
     "wizard.import.processing.committing.cycle.2.detail"),
    ("wizard.import.processing.committing.cycle.3.title",
     "wizard.import.processing.committing.cycle.3.detail"),
    ("wizard.import.processing.committing.cycle.4.title",
     "wizard.import.processing.committing.cycle.4.detail"),
]

_SUB_STATE_TO_CYCLE = {
    _SUB_STATE_VALIDATING: _VALIDATING_CYCLE,
    _SUB_STATE_STAGING: _STAGING_CYCLE,
    _SUB_STATE_DETECTING: _STAGING_CYCLE,  # detection runs inside Staging
}

_CYCLE_INTERVAL_MS = 5000


class ImportStepProcessing(QWidget):
    """New 3-step-flow processing view. Drop-in for the legacy step2 widget."""

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

        self._setup_ui()

        if not skip_load and self._package_id:
            # Lazy-fetch the package metadata so the summary strip has real
            # data. Failures here are non-fatal — the wizard owns the error
            # banner and will surface them if load_package_failed.
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

        # --- Package summary strip ----------------------------------------
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

        # --- Central state panel ------------------------------------------
        self._state_panel = QFrame()
        self._state_panel.setStyleSheet(
            "QFrame { background: #FFFFFF; border: 1px solid #E2EAF2;"
            " border-radius: 14px; }"
        )
        self._state_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        state_layout = QVBoxLayout(self._state_panel)
        state_layout.setContentsMargins(32, 28, 32, 28)
        state_layout.setSpacing(14)
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

        # Animated dots (shows only for transient sub-states).
        self._dots_label = QLabel("")
        self._dots_label.setAlignment(Qt.AlignCenter)
        self._dots_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._dots_label.setStyleSheet(
            "color: #3890DF; background: transparent; border: none;"
        )
        state_layout.addWidget(self._dots_label)

        # Conflict CTA (hidden unless status == ReviewingConflicts).
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

        # Dots animation timer.
        self._dots_count = 0
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._tick_dots)

        # Micro-stage cycling — advances title/detail text every 5s during
        # transient sub-states so the screen never feels frozen during a
        # long synchronous /stage call. Text-only; no icon changes.
        self._cycle_idx = 0
        self._cycle_active_state: Optional[str] = None
        self._cycle_timer = QTimer(self)
        self._cycle_timer.timeout.connect(self._tick_cycle)

        # Apply initial state if we already know it from the wizard.
        self._apply_sub_state(_SUB_STATE_PENDING)

    # -- Public API -----------------------------------------------------------

    def set_status(self, status_code: int, extra: Optional[Dict[str, Any]] = None):
        """Update the view for a new backend status code."""
        self._current_status = status_code
        sub_state = _STATUS_TO_SUB_STATE.get(status_code, _SUB_STATE_PENDING)
        self._apply_sub_state(sub_state, extra=extra or {})
        # Status badge on the package summary strip.
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

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        # Re-apply current state to pick up new translations.
        if self._current_status is not None:
            self.set_status(self._current_status)

    # -- Internal helpers -----------------------------------------------------

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
        extra = extra or {}
        # Hide conflict CTA by default; only the conflict branch shows it.
        self._conflict_box.setVisible(False)

        if sub_state == _SUB_STATE_PENDING:
            self._state_icon.setText("⏳")
            self._state_icon.setStyleSheet(
                "color: #6B7280; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.pending_title"))
            self._state_detail.setText(tr("wizard.import.processing.pending_detail"))
            self._stop_dots()
            self._stop_cycle()
        elif sub_state in (_SUB_STATE_STAGING, _SUB_STATE_VALIDATING, _SUB_STATE_DETECTING):
            # Same icon for all transient sub-states (no icon changes per
            # request — just rotating text).
            self._state_icon.setText("⚙")
            self._state_icon.setStyleSheet(
                "color: #3890DF; background: transparent; border: none;"
            )
            self._start_cycle(sub_state)
            self._start_dots()
        elif sub_state == _SUB_STATE_VALIDATION_FAILED:
            self._state_icon.setText("⚠")
            self._state_icon.setStyleSheet(
                "color: #B91C1C; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.validation_failed_title"))
            self._state_detail.setText(tr("wizard.import.processing.validation_failed_detail"))
            self._stop_dots()
            self._stop_cycle()
        elif sub_state == _SUB_STATE_QUARANTINED:
            self._state_icon.setText("🔒")
            self._state_icon.setStyleSheet(
                "color: #B91C1C; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.quarantined_title"))
            self._state_detail.setText(tr("wizard.import.processing.quarantined_detail"))
            self._stop_dots()
            self._stop_cycle()
        elif sub_state == _SUB_STATE_REVIEWING_CONFLICTS:
            self._state_icon.setText("⚡")
            self._state_icon.setStyleSheet(
                "color: #6D28D9; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.conflicts_title"))
            self._state_detail.setText(tr("wizard.import.processing.conflicts_detail"))
            self._conflict_box.setVisible(True)
            self._stop_dots()
            self._stop_cycle()
        elif sub_state == _SUB_STATE_READY:
            self._state_icon.setText("✓")
            self._state_icon.setStyleSheet(
                "color: #059669; background: transparent; border: none;"
            )
            self._state_title.setText(tr("wizard.import.processing.ready_title"))
            self._state_detail.setText(tr("wizard.import.processing.ready_detail"))
            self._stop_dots()
            self._stop_cycle()

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

    # -- Micro-stage text cycling -------------------------------------------

    def _start_cycle(self, sub_state: str):
        """Begin (or resume) cycling the title/detail through the list for
        this sub-state. Idempotent: if the cycle is already running for the
        same sub-state, just continue from the current index."""
        cycle = _SUB_STATE_TO_CYCLE.get(sub_state)
        if not cycle:
            self._stop_cycle()
            return
        if self._cycle_active_state != sub_state:
            self._cycle_active_state = sub_state
            self._cycle_idx = 0
        # Render the current frame immediately so the user sees a real
        # message instead of blank text.
        self._render_cycle_frame()
        if not self._cycle_timer.isActive():
            self._cycle_timer.start(_CYCLE_INTERVAL_MS)

    def _stop_cycle(self):
        """Stop cycling. Called when the widget enters a non-transient
        sub-state or is hidden."""
        self._cycle_timer.stop()
        self._cycle_active_state = None
        self._cycle_idx = 0

    def _tick_cycle(self):
        cycle = _SUB_STATE_TO_CYCLE.get(self._cycle_active_state or "")
        if not cycle:
            self._stop_cycle()
            return
        self._cycle_idx = (self._cycle_idx + 1) % len(cycle)
        self._render_cycle_frame()

    def _render_cycle_frame(self):
        cycle = _SUB_STATE_TO_CYCLE.get(self._cycle_active_state or "")
        if not cycle:
            return
        title_key, detail_key = cycle[self._cycle_idx % len(cycle)]
        self._state_title.setText(tr(title_key))
        self._state_detail.setText(tr(detail_key))

    # -- Lifecycle ----------------------------------------------------------

    def hideEvent(self, event):
        # Stop all timers when this widget leaves the active step so it
        # doesn't keep ticking in the background.
        try:
            self._stop_dots()
            self._stop_cycle()
        except Exception:
            pass
        super().hideEvent(event)
