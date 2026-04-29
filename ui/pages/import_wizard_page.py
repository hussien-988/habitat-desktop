# -*- coding: utf-8 -*-
"""Import wizard page with 3-step processing pipeline (processing → review/commit → final report)."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QFrame, QPushButton,
    QHBoxLayout, QLabel, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, QDateTime
from PyQt5.QtGui import QColor

from ui.components.wizard_header import WizardHeader
from app.config import Pages
from ui.components.accent_line import AccentLine
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.exceptions import NetworkException, ApiException
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger
from ui.design_system import ScreenScale

logger = get_logger(__name__)


def _prompt_reason_via_bottom_sheet(
    parent,
    title: str,
    field_label: str,
    submit_text: str,
    cancel_text: str,
) -> str:
    """Prompt the user for a reason via the project's BottomSheet design.

    Returns the trimmed string the user submitted, or "" if they cancelled
    or left the field empty. Synchronous (blocks the calling slot via a
    nested QEventLoop) — matches the existing pattern used in
    `app/main_window_v2.py` for the office-survey cancellation reason.
    """
    from ui.components.bottom_sheet import BottomSheet
    from PyQt5.QtCore import QEventLoop

    sheet = BottomSheet(parent)
    loop = QEventLoop()
    result = {"value": None}

    def _on_confirmed():
        data = sheet.get_form_data()
        result["value"] = (data.get("reason") or "").strip()
        loop.quit()

    def _on_cancelled():
        result["value"] = None
        loop.quit()

    sheet.confirmed.connect(_on_confirmed)
    sheet.cancelled.connect(_on_cancelled)
    sheet.show_form(
        title,
        [("reason", field_label, "multiline")],
        submit_text=submit_text,
        cancel_text=cancel_text,
    )
    loop.exec_()
    return result["value"] or ""


from services.import_status_map import (
    PkgStatus as _ImportPkgStatus,
    TRANSIENT as _IMPORT_TRANSIENT,
    HISTORY as _IMPORT_HISTORY,
    target_wizard_step,
)

# Visible wizard pills are now 3; internal QStackedWidget still has 5 panels
# because the legacy step widgets are reused as sub-panels.
TOTAL_STEPS = 3
INTERNAL_STEPS = 4

# Visible step pills (3)
_VISIBLE_STEP_KEYS = [
    "wizard.import.step_processing",
    "wizard.import.step_review_approve",
    "wizard.import.step_final_report",
]
_STEP_NAMES_KEYS = _VISIBLE_STEP_KEYS  # backwards-compat alias

# Internal panel index -> visible pill index.
# 0 = step2 staging/validation       -> Processing (pill 0)
# 1 = step_review staged entities    -> Review & Approve (pill 1)
# 2 = step_commit commit confirm     -> Review & Approve (pill 1)
# 3 = step_report final report       -> Final Report (pill 2)
_INTERNAL_TO_PILL = [0, 1, 1, 2]


class _PkgStatus:
    """Package status codes — re-exported for backwards compat. Prefer
    importing from services.import_status_map."""
    PENDING = _ImportPkgStatus.PENDING
    VALIDATING = _ImportPkgStatus.VALIDATING
    STAGING = _ImportPkgStatus.STAGING
    VALIDATION_FAILED = _ImportPkgStatus.VALIDATION_FAILED
    QUARANTINED = _ImportPkgStatus.QUARANTINED
    REVIEWING_CONFLICTS = _ImportPkgStatus.REVIEWING_CONFLICTS
    READY_TO_COMMIT = _ImportPkgStatus.READY_TO_COMMIT
    COMMITTING = _ImportPkgStatus.COMMITTING
    COMPLETED = _ImportPkgStatus.COMPLETED
    FAILED = _ImportPkgStatus.FAILED
    PARTIALLY_COMPLETED = _ImportPkgStatus.PARTIALLY_COMPLETED
    CANCELLED = _ImportPkgStatus.CANCELLED

    TRANSIENT = _IMPORT_TRANSIENT
    TERMINAL = _IMPORT_HISTORY | {FAILED}


_STATUS_POLL_INTERVAL_MS = 5000  # 5 seconds
_MAX_POLL_COUNT = 24  # 24 polls × 5s = 120s default timeout (was 300s)
_TIMEOUT_EXTENSION_POLLS = 12  # +60s if user clicks "wait more" (one-time)
_STUCK_WARN_POLLS = 6   # 6 polls × 5s = 30s with same transient status
_STUCK_RETRY_POLLS = 12  # 12 polls × 5s = 1 minute with same transient status → show retry toast


def _status_name(code) -> str:
    """Human-readable status name for log lines (defensive, returns 'unknown')."""
    try:
        for attr in (
            "PENDING", "VALIDATING", "STAGING", "VALIDATION_FAILED", "QUARANTINED",
            "REVIEWING_CONFLICTS", "READY_TO_COMMIT", "COMMITTING", "COMPLETED",
            "FAILED", "PARTIALLY_COMPLETED", "CANCELLED",
        ):
            if getattr(_PkgStatus, attr) == code:
                return attr
    except Exception:
        pass
    return "unknown"

class _ApiWorker(QThread):
    """Worker thread for non-blocking API calls."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str, str)  # error_type ('network'|'api'|'unknown'), message_ar

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        from services.exceptions import humanize_exception, log_exception
        try:
            result = self._fn()
            self.finished.emit(result)
        except NetworkException as e:
            log_exception(e, logger, context="wizard_api_worker")
            self.error.emit("network", humanize_exception(e))
        except ApiException as e:
            log_exception(e, logger, context="wizard_api_worker")
            self.error.emit("api", humanize_exception(e))
        except Exception as e:
            logger.error(f"Unexpected worker error: {e}")
            self.error.emit("unknown", tr("error.unexpected_retry"))


class ImportWizardPage(QWidget):
    """
    Import Wizard - 3-Step Wizard (3 visible pills, 4 internal panels).

    Same structure as FieldWorkPreparationPage:
    1. Fixed header + step indicator
    2. QStackedWidget for steps
    3. Fixed footer with back/next + cancel button
    """

    completed = pyqtSignal(object)
    cancelled = pyqtSignal()
    # Emitted when the wizard bounces back to the packages list because
    # the package landed in a terminal/non-actionable state. Carries the
    # localized message to surface to the user via a Toast on the
    # packages page so they understand WHY nothing happened.
    # Args: (severity, message_ar) where severity is "error"|"warning"|"info".
    terminal_state_message = pyqtSignal(str, str)
    navigate_to_duplicates = pyqtSignal(str)  # carries the current package_id

    # Track package metadata so main_window can label the duplicates banner
    _current_package_name = ""

    def __init__(self, import_controller=None, db=None, i18n=None, parent=None):
        """Initialize import wizard."""
        super().__init__(parent)
        self.import_controller = import_controller
        self.db = db
        self.i18n = i18n
        self._user_role = None
        self._current_package_id = None
        self._current_package_status = 0
        self._status_poll_timer = None
        self._poll_count = 0
        self._poll_last_status = None
        self._poll_unchanged_count = 0
        self._poll_warned = False
        self._poll_started_at = None
        self._pipeline_in_flight = False
        # Timeout extension state — once user clicks "wait more" we allow 60
        # extra seconds, after which the final timeout error fires.
        self._timeout_extension_used = False
        self._max_polls_session = _MAX_POLL_COUNT
        # Stage call timing — for measuring total /stage round-trip duration.
        self._stage_started_at_ms = 0
        # Loading overlay timing state
        self._loading_started_at = None
        self._loading_elapsed_timer = None
        self._active_worker = None
        # When True, the wizard is in a hard-error state (e.g. /stage 500,
        # missing .uhc file). Forward navigation is blocked; only cancel
        # package and back-to-list remain enabled until the user recovers.
        self._blocking_error_active = False

        self._setup_ui()
        self._create_steps()

    def _setup_ui(self):
        """Setup UI with dark wizard header and step pills."""
        self.setLayoutDirection(get_layout_direction())

        self.setStyleSheet(StyleManager.page_background())

        # Outer layout (no padding) for full-width header and footer
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Dark header with integrated step indicator pills (full-width)
        step_names = [tr(key) for key in _STEP_NAMES_KEYS]
        self.header = WizardHeader(
            title=tr("wizard.import.title"),
            subtitle=tr("wizard.import.subtitle"),
            steps=step_names,
            help_page_id=Pages.IMPORT_WIZARD,
        )
        outer_layout.addWidget(self.header)

        # Accent line (full-width)
        self._accent = AccentLine()
        outer_layout.addWidget(self._accent)

        # Inline error banner (hidden by default). Used to surface API
        # failures near the affected step instead of relying on a toast.
        self._error_banner = self._create_error_banner()
        outer_layout.addWidget(self._error_banner)

        # Step container (QStackedWidget)
        self.step_container = QStackedWidget()
        outer_layout.addWidget(self.step_container, 1)

        # Loading overlay (hidden)
        self._loading_overlay = self._create_loading_overlay()

        # Footer (fixed, full width)
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    # -- Inline error banner --------------------------------------------------

    def _create_error_banner(self) -> QFrame:
        """Inline error/warning panel rendered above the active step.

        Shows the safe user message + optional action button + optional trace id.
        Backend stack traces never reach this label.
        """
        banner = QFrame()
        banner.setObjectName("wizardErrorBanner")
        banner.setStyleSheet(
            "QFrame#wizardErrorBanner { background: #FEF2F2;"
            " border-bottom: 1px solid #FCA5A5; }"
        )

        layout = QHBoxLayout(banner)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        self._error_icon = QLabel("⚠")
        self._error_icon.setStyleSheet(
            "color: #B91C1C; background: transparent; font-size: 16pt;"
        )
        layout.addWidget(self._error_icon)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        self._error_title = QLabel(tr("import.error.inline_title"))
        self._error_title.setStyleSheet(
            "color: #991B1B; background: transparent; font-weight: 700;"
        )
        text_box.addWidget(self._error_title)

        self._error_message = QLabel("")
        self._error_message.setWordWrap(True)
        self._error_message.setStyleSheet(
            "color: #7F1D1D; background: transparent;"
        )
        text_box.addWidget(self._error_message)

        self._error_trace = QLabel("")
        self._error_trace.setStyleSheet(
            "color: #9CA3AF; background: transparent; font-size: 9pt;"
        )
        self._error_trace.setVisible(False)
        text_box.addWidget(self._error_trace)

        layout.addLayout(text_box, 1)

        self._banner_secondary_btn = QPushButton("")
        self._banner_secondary_btn.setObjectName("bannerSecondaryButton")
        self._banner_secondary_btn.setVisible(False)
        self._banner_secondary_btn.setCursor(Qt.PointingHandCursor)
        self._banner_secondary_btn.setStyleSheet("""
            QPushButton#bannerSecondaryButton {
                background-color: #DC2626;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton#bannerSecondaryButton:hover {
                background-color: #B91C1C;
            }
        """)
        layout.addWidget(self._banner_secondary_btn)

        self._banner_action_btn = QPushButton("")
        self._banner_action_btn.setObjectName("bannerActionButton")
        self._banner_action_btn.setVisible(False)
        self._banner_action_btn.setCursor(Qt.PointingHandCursor)
        self._banner_action_btn.setStyleSheet("""
            QPushButton#bannerActionButton {
                background-color: #F59E0B;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton#bannerActionButton:hover {
                background-color: #D97706;
            }
        """)
        layout.addWidget(self._banner_action_btn)

        self._error_close = QPushButton("✕")
        self._error_close.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        self._error_close.setCursor(Qt.PointingHandCursor)
        self._error_close.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #991B1B; font-size: 14pt; }"
            "QPushButton:hover { color: #7F1D1D; }"
        )
        self._error_close.clicked.connect(self._on_error_close_clicked)
        layout.addWidget(self._error_close)

        banner.setVisible(False)
        return banner

    def _apply_banner_severity(self, severity: str):
        """Repaint the inline banner with the colors for the given severity.

        Centralised so that switching from a warning back to an error (or vice
        versa) doesn't leave stale colors on the next show. Severities:
          - "error":   red background / red text (api failures, hard stops)
          - "warning": amber background / amber text (slow server, recoverable)
        """
        if severity == "warning":
            banner_qss = (
                "QFrame#wizardErrorBanner { background: #FEF3C7;"
                " border-bottom: 1px solid #F59E0B; }"
            )
            icon_qss = "color: #D97706; background: transparent; font-size: 16pt;"
            title_qss = "color: #92400E; background: transparent; font-weight: 700;"
            message_qss = "color: #92400E; background: transparent;"
            close_qss = (
                "QPushButton { background: transparent; border: none;"
                " color: #92400E; font-size: 14pt; }"
                "QPushButton:hover { color: #78350F; }"
            )
        else:
            banner_qss = (
                "QFrame#wizardErrorBanner { background: #FEF2F2;"
                " border-bottom: 1px solid #FCA5A5; }"
            )
            icon_qss = "color: #B91C1C; background: transparent; font-size: 16pt;"
            title_qss = "color: #991B1B; background: transparent; font-weight: 700;"
            message_qss = "color: #7F1D1D; background: transparent;"
            close_qss = (
                "QPushButton { background: transparent; border: none;"
                " color: #991B1B; font-size: 14pt; }"
                "QPushButton:hover { color: #7F1D1D; }"
            )

        if hasattr(self, "_error_banner") and self._error_banner is not None:
            self._error_banner.setStyleSheet(banner_qss)
        if hasattr(self, "_error_icon") and self._error_icon is not None:
            self._error_icon.setStyleSheet(icon_qss)
        if hasattr(self, "_error_title") and self._error_title is not None:
            self._error_title.setStyleSheet(title_qss)
        if hasattr(self, "_error_message") and self._error_message is not None:
            self._error_message.setStyleSheet(message_qss)
        if hasattr(self, "_error_close") and self._error_close is not None:
            self._error_close.setStyleSheet(close_qss)


    def _show_error_banner(self, user_message: str, trace_id: str = ""):
        """Show the inline error banner with a safe message + optional trace id."""
        self._clear_banner_action()
        self._apply_banner_severity("error")
        self._error_title.setText(tr("import.error.inline_title"))
        self._error_message.setText(user_message or tr("api.error.generic"))
        if trace_id:
            self._error_trace.setText(f"{tr('api.error.trace_id_label')}: {trace_id}")
            self._error_trace.setVisible(True)
        else:
            self._error_trace.clear()
            self._error_trace.setVisible(False)
        self._error_banner.setVisible(True)


    def _show_warning_banner(self, message: str):
        """Show a non-blocking warning banner for slow backend progress."""
        self._clear_banner_action()
        self._apply_banner_severity("warning")
        self._error_title.setText(tr("wizard.import.warning_title"))
        self._error_message.setText(message)
        self._error_trace.clear()
        self._error_trace.setVisible(False)
        self._error_banner.setVisible(True)


    def _show_stuck_banner(self, elapsed_secs: int):
        """Show an actionable warning when backend status is unchanged too long."""
        seconds = max(0, int(elapsed_secs or 0))
        self._clear_banner_action()
        self._apply_banner_severity("warning")
        self._error_title.setText(tr("wizard.import.warning_title"))
        self._error_message.setText(
            tr("wizard.import.warning_stuck_actionable").format(seconds=seconds)
        )
        self._error_trace.clear()
        self._error_trace.setVisible(False)

        self._banner_action_btn.setText(tr("wizard.import.action_retry_now"))
        self._banner_action_btn.setVisible(True)

        def retry_now():
            self._poll_unchanged_count = 0
            self._poll_warned = False
            self._hide_error_banner()
            self._poll_package_status()

        self._banner_action_btn.clicked.connect(retry_now)
        self._error_banner.setVisible(True)


    def _show_initial_load_failed_banner(self):
        """Show an actionable banner when the initial package load fails."""
        self._clear_banner_action()
        self._apply_banner_severity("warning")
        self._error_title.setText(tr("wizard.import.warning_title"))
        self._error_message.setText(tr("wizard.import.initial_load_failed"))
        self._error_trace.clear()
        self._error_trace.setVisible(False)

        self._banner_action_btn.setText(tr("wizard.import.action_retry_now"))
        self._banner_action_btn.setVisible(True)

        def retry_load():
            self._hide_error_banner()
            if self._current_package_id:
                self.set_package_id(self._current_package_id)

        self._banner_action_btn.clicked.connect(retry_load)
        self._error_banner.setVisible(True)


    def _show_timeout_decision_banner(self, elapsed_secs: int):
        """Show the timeout banner with two explicit choices: wait more, or cancel."""
        seconds = max(0, int(elapsed_secs or 0))
        self._clear_banner_action()
        self._apply_banner_severity("warning")
        self._error_title.setText(tr("wizard.import.timeout_decision_title"))
        self._error_message.setText(
            tr("wizard.import.timeout_decision_body").format(seconds=seconds)
        )
        self._error_trace.clear()
        self._error_trace.setVisible(False)

        self._banner_action_btn.setText(tr("wizard.import.action_wait_more"))
        self._banner_action_btn.setVisible(True)

        def wait_more():
            self._timeout_extension_used = True
            self._max_polls_session = _MAX_POLL_COUNT + _TIMEOUT_EXTENSION_POLLS
            self._poll_unchanged_count = 0
            self._poll_warned = False
            logger.info(
                f"[import-flow] resume pkg={self._current_package_id} extension=60s "
                f"new_max_polls={self._max_polls_session}"
            )
            self._hide_error_banner()
            if self._status_poll_timer is not None:
                self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)

        self._banner_action_btn.clicked.connect(wait_more)

        self._banner_secondary_btn.setText(tr("wizard.import.action_cancel_package"))
        self._banner_secondary_btn.setVisible(True)

        def cancel_now():
            logger.info(
                f"[import-flow] timeout-decision-cancel pkg={self._current_package_id}"
            )
            self._hide_error_banner()
            self._on_cancel_package()

        self._banner_secondary_btn.clicked.connect(cancel_now)

        self._error_banner.setVisible(True)


    def _clear_banner_action(self):
        """Remove any active banner action buttons (primary + secondary)."""
        for attr in ("_banner_action_btn", "_banner_secondary_btn"):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            try:
                btn.clicked.disconnect()
            except TypeError:
                pass
            btn.setText("")
            btn.setVisible(False)


    def _on_error_close_clicked(self):
        """Handle closing the inline banner without losing recovery actions."""
        has_active_action = (
            hasattr(self, "_banner_action_btn")
            and self._banner_action_btn is not None
            and self._banner_action_btn.isVisible()
            and bool(self._banner_action_btn.text())
        )

        if has_active_action:
            # Do not hide the only visible recovery path by accident.
            # The user can still use the action button itself.
            return

        self._hide_error_banner()


    def _hide_error_banner(self):
        self._error_banner.setVisible(False)
        self._clear_banner_action()
        self._error_trace.clear()
        self._error_trace.setVisible(False)

    def _show_result_error(self, result, fallback_context: str = "generic"):
        """Render an OperationResult failure in the inline banner + log it.

        Reads the structured `error` from the result when available so we
        get the trace id and can re-humanize via the central layer. Falls
        back to result.message_ar if no structured error was attached.
        """
        from services.exceptions import humanize_exception
        error = getattr(result, "error", None) if result is not None else None
        if error is not None:
            user_msg = humanize_exception(error, context=fallback_context)
            trace_id = getattr(error, "trace_id", "") or ""
            try:
                logger.error(error.log_summary())
            except Exception:
                logger.error(f"API error: {error}")
        else:
            user_msg = (getattr(result, "message_ar", "") or tr("api.error.generic"))
            trace_id = ""
        self._show_error_banner(user_msg, trace_id)

    # -- Step Indicator -------------------------------------------------------

    def _update_step_indicator(self, current: int):
        """Update step indicator in the dark wizard header.

        The header shows 3 pills (Processing / Review / Report) while the
        internal stack still has 5 panels — map accordingly.
        """
        visible = _INTERNAL_TO_PILL[current] if 0 <= current < len(_INTERNAL_TO_PILL) else 0
        self.header.set_current_step(visible)

    # -- Loading Overlay ------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        """Create a loading overlay shown during blocking API calls."""
        overlay = QFrame(self)
        overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 200);
            }
        """)
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        # Spinner card
        card = QFrame()
        card.setFixedSize(ScreenScale.w(280), ScreenScale.h(100))
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(8)

        self._loading_label = QLabel(tr("status.processing"))
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_label)

        # Simple animated dots indicator
        self._loading_dots = QLabel("")
        self._loading_dots.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._loading_dots.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_dots.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_dots)
        self._loading_elapsed_label = QLabel("")
        self._loading_elapsed_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._loading_elapsed_label.setStyleSheet(
            "color: #6B7280; background: transparent; border: none;"
        )
        self._loading_elapsed_label.setAlignment(Qt.AlignCenter)
        self._loading_elapsed_label.setVisible(False)
        card_layout.addWidget(self._loading_elapsed_label)

        overlay_layout.addWidget(card)

        # Dots animation timer
        self._dots_count = 0
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)
        # Elapsed time timer for long blocking calls
        self._loading_elapsed_timer = QTimer(self)
        self._loading_elapsed_timer.setInterval(1000)
        self._loading_elapsed_timer.timeout.connect(self._update_loading_elapsed)
        return overlay

    def _show_loading(self, message: str):
        """Show loading overlay with a message."""
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)

        self._loading_started_at = QDateTime.currentDateTime()
        self._update_loading_elapsed()
        self._loading_elapsed_label.setVisible(True)
        if self._loading_elapsed_timer is not None:
            self._loading_elapsed_timer.start()

        self._dots_count = 0
        self._dots_timer.start(400)

    def _hide_loading(self):
        """Hide loading overlay."""
        self._dots_timer.stop()

        if self._loading_elapsed_timer is not None:
            self._loading_elapsed_timer.stop()

        self._loading_started_at = None
        self._loading_elapsed_label.setText("")
        self._loading_elapsed_label.setVisible(False)

        self._loading_overlay.setVisible(False)
    def _update_loading_elapsed(self):
        """Update elapsed-time text inside the loading overlay."""
        if self._loading_started_at is None:
            return

        elapsed = max(0, int(self._loading_started_at.secsTo(QDateTime.currentDateTime())))

        if hasattr(self, "_loading_elapsed_label") and self._loading_elapsed_label is not None:
            self._loading_elapsed_label.setText(
                tr("wizard.import.loading_elapsed").format(elapsed=elapsed)
            )

    def _animate_dots(self):
        """Animate loading dots."""
        self._dots_count = (self._dots_count + 1) % 4
        self._loading_dots.setText("." * self._dots_count)

    def resizeEvent(self, event):
        """Resize overlay with the widget."""
        super().resizeEvent(event)
        if self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Async API helpers ----------------------------------------------------

    def _run_api(self, fn, on_success, on_error=None, loading_msg=""):
        """Run an API call on a worker thread without blocking the UI.

        Args:
            fn: callable (no args) to run in the worker thread
            on_success: callback(result) on the main thread
            on_error: optional callback(error_type, msg_ar) override
            loading_msg: if set, show loading overlay with this message
        """
        self._cancel_active_worker()
        self._set_buttons_enabled(False)

        if loading_msg:
            self._show_loading(loading_msg)

        worker = _ApiWorker(fn)
        self._active_worker = worker

        error_handler = on_error or self._on_api_error
        worker.finished.connect(lambda result: self._on_worker_done(result, on_success))
        worker.error.connect(lambda t, m: self._on_worker_error(t, m, error_handler))
        worker.start()

    def _on_worker_done(self, result, on_success):
        """Handle successful worker completion on the main thread."""
        self._active_worker = None
        self._hide_loading()
        on_success(result)

    def _on_worker_error(self, error_type, msg_ar, error_handler):
        """Handle worker error on the main thread."""
        self._active_worker = None
        self._hide_loading()
        error_handler(error_type, msg_ar)

    def _cancel_active_worker(self):
        """Cancel any running worker (best-effort)."""
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.finished.disconnect()
            self._active_worker.error.disconnect()
            self._active_worker.quit()
            self._active_worker.wait(2000)
            self._active_worker = None

    def _on_api_error(self, error_type, msg_ar):
        """Default error handler for API worker errors."""
        self._set_buttons_enabled(True)
        if error_type == "network":
            self._show_error(f"{msg_ar}\n\n{tr('wizard.import.retry_hint')}")
        else:
            self._show_error(msg_ar)

    def _set_buttons_enabled(self, enabled: bool):
        """Enable or disable navigation buttons (prevents double-click)."""
        # Forward navigation is suppressed entirely while a blocking error
        # is active — see _enter_blocking_error_state.
        if self._blocking_error_active:
            self.btn_next.setEnabled(False)
        else:
            self.btn_next.setEnabled(enabled)
        # "Back to packages" stays enabled — it's non-destructive and must
        # remain reachable even during in-flight requests.
        self.btn_back.setEnabled(True)
        self.btn_cancel.setEnabled(enabled)

    def _enter_blocking_error_state(self):
        """Halt all wizard operations after a hard error.

        Triggered when /stage (or another required call) returns a server
        error such as 500 / missing .uhc file. We:
          1. Stop status polling and any active worker so nothing keeps
             firing in the background.
          2. Stop the processing widget's cycling animation so it doesn't
             keep showing fake progress text below the error banner.
          3. Set the blocking flag so _set_buttons_enabled / _update_
             navigation refuse to re-enable Next.
          4. Disable Next, keep Cancel-Package and Back-to-List enabled.
        The error banner stays visible above the buttons so the user knows
        why nothing is happening.
        """
        self._blocking_error_active = True
        try:
            self._stop_status_poll()
        except Exception:
            pass
        try:
            self._cancel_active_worker()
        except Exception:
            pass
        # Halt the cycling progress text in the processing widget — it
        # would otherwise keep claiming "the server is starting…" while
        # the error banner says the opposite.
        if self.step2 is not None and hasattr(self.step2, "_stop_cycle"):
            try:
                self.step2._stop_cycle()
            except Exception:
                pass
        self._hide_loading()
        self.btn_next.setEnabled(False)
        self.btn_next.setToolTip(tr("wizard.import.error_next_blocked"))
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.btn_back.setEnabled(True)

    # -- Footer ---------------------------------------------------------------

    def _create_footer(self):
        """Create footer with back, cancel, and next buttons."""
        footer = QFrame()
        footer.setStyleSheet(StyleManager.nav_footer())
        footer.setFixedHeight(ScreenScale.h(74))

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(ScreenScale.w(130), ScreenScale.h(12), ScreenScale.w(130), ScreenScale.h(12))
        layout.setSpacing(0)

        # Back button
        self.btn_back = QPushButton(tr("wizard.import.back_to_list"))
        self.btn_back.setFixedSize(ScreenScale.w(252), ScreenScale.h(50))
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self.btn_back.setStyleSheet(StyleManager.nav_button_secondary())
        self.btn_back.clicked.connect(self._on_back)
        # Always enabled — user can always leave the wizard without destructive side-effects.
        self.btn_back.setEnabled(True)
        layout.addWidget(self.btn_back)

        layout.addStretch()

        # Cancel package button (shown on steps 2-4)
        self.btn_cancel = QPushButton(tr("wizard.import.cancel_package"))
        self.btn_cancel.setFixedSize(ScreenScale.w(252), ScreenScale.h(50))
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FAFBFF, stop:1 #FFF5F5);
                color: #DC3545;
                border: 1px solid rgba(220, 53, 69, 0.25);
                border-radius: 10px;
                padding: 8px 32px;
                font-weight: 600;
                font-size: 12pt;
            }
            QPushButton:hover {
                background: #FFF0F0;
                border-color: rgba(220, 53, 69, 0.45);
            }
            QPushButton:disabled {
                color: #C0C8D0;
                background: #F5F7FA;
                border-color: #E8ECF0;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel_package)
        self.btn_cancel.setVisible(False)
        layout.addWidget(self.btn_cancel)

        # Spacer between cancel and next
        layout.addStretch()

        # Next button
        self.btn_next = QPushButton(tr("action.next_arrow"))
        self.btn_next.setFixedSize(ScreenScale.w(252), ScreenScale.h(50))
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self.btn_next.setStyleSheet(StyleManager.nav_button_primary())
        self.btn_next.clicked.connect(self._on_next)
        self.btn_next.setEnabled(False)
        layout.addWidget(self.btn_next)

        return footer

    def _create_steps(self):
        """Step widgets are created lazily when the wizard routes to them.

        The legacy ImportStep1Packages package-list widget has been removed —
        users enter the wizard from ImportPackagesPage with a specific
        package id (see set_package_id). Internal stack layout:
          index 0 = step2 (processing / validation)
          index 1 = step_review
          index 2 = step_commit
          index 3 = step_report
        """
        self.step2 = None         # staging + validation + duplicates
        self.step_review = None   # review (uses import_step4_review.py)
        self.step_commit = None   # commit (uses import_step5_commit.py)
        self.step_report = None   # report (uses import_step6_report.py)

        self.current_step = 0

    # -- Navigation ----------------------------------------------------------

    def _on_back(self):
        """Back button → leave the wizard and return to the packages list.

        Does NOT call any destructive backend endpoint. Polling and active
        workers are stopped, and the UI emits `cancelled` so main_window
        routes back to IMPORT_PACKAGES.
        """
        self._cancel_active_worker()
        self._stop_status_poll()
        # Clear the in-flight flag so the next package the user opens is
        # routed fresh (otherwise a stale flag from this session would make
        # _route_by_status skip /stage for a new VALIDATING package).
        self._pipeline_in_flight = False
        self._hide_loading()
        self.cancelled.emit()

    def _on_next(self):
        """Handle next button — step transitions with controller calls.

        Internal step indices: 0=validation, 1=review, 2=commit, 3=report.
        Legacy step1 (package list) has been removed; entry is always via
        set_package_id() from the packages list.
        """
        if self.current_step == 0:
            if self._current_package_status == _PkgStatus.VALIDATION_FAILED:
                self._cancel_validation_failed_package()
                return
            self._transition_step2_to_review()

        elif self.current_step == 1:
            self._transition_review_to_commit()

        elif self.current_step == 2:
            # Approve and Import Data — irreversible; confirm first.
            from ui.error_handler import ErrorHandler
            confirmed = ErrorHandler.confirm(
                self,
                tr("wizard.import.confirm_commit_body"),
                tr("wizard.import.confirm_commit_title"),
            )
            if not confirmed:
                return
            self._transition_commit_to_report()

        elif self.current_step == 3:
            if self._current_package_status == _PkgStatus.FAILED:
                self._retry_failed_commit()
            else:
                # Terminal state — leave the wizard.
                self.cancelled.emit()

    # -- State-aware routing --------------------------------------------------

    def _route_by_status(self, status: int):
        """Central router: direct to the correct wizard step based on package status."""
        self._current_package_status = status
        logger.info(
            f"[import-flow] route pkg={self._current_package_id} "
            f"status={status}({_status_name(status)})"
        )
        if status not in (_PkgStatus.VALIDATING, _PkgStatus.STAGING):
            self._pipeline_in_flight = False
        # Keep the processing widget in sync when it's visible.
        if self.step2 is not None and hasattr(self.step2, "set_status"):
            try:
                self.step2.set_status(status)
            except Exception:
                pass

        if status == _PkgStatus.PENDING:
            self._handle_pending()
        elif status == _PkgStatus.VALIDATING:
            # VALIDATING normally means "uploaded, waiting for /stage".
            # But if this wizard already triggered /stage for this package,
            # seeing VALIDATING again is a transient backend state, not a new
            # instruction to call /stage again.
            if self._pipeline_in_flight:
                logger.info(
                    f"Package {self._current_package_id} is still VALIDATING after /stage trigger; "
                    "keeping status polling instead of re-posting /stage."
                )
                self._handle_in_progress(status)
            else:
                self._handle_validating_start()
        elif status == _PkgStatus.STAGING:
            # Pipeline is already running on the server (likely triggered
            # by another session). Don't re-call /stage (returns 409); just
            # poll until completion.
            self._handle_in_progress(status)
        elif status == _PkgStatus.VALIDATION_FAILED:
            self._handle_validation_failed()
        elif status == _PkgStatus.QUARANTINED:
            self._handle_quarantined()
        elif status == _PkgStatus.REVIEWING_CONFLICTS:
            self._handle_reviewing_conflicts()
        elif status == _PkgStatus.READY_TO_COMMIT:
            self._handle_ready_to_commit()
        elif status == _PkgStatus.COMMITTING:
            self._handle_committing()
        elif status in (_PkgStatus.COMPLETED, _PkgStatus.PARTIALLY_COMPLETED):
            self._handle_terminal_report()
        elif status == _PkgStatus.FAILED:
            self._handle_failed()
        elif status == _PkgStatus.CANCELLED:
            self._handle_cancelled()
        else:
            logger.warning(f"Unknown package status: {status}")
            self._show_error(tr("wizard.import.error_unknown_status").format(status=status))
            # Unknown server state — bounce back to the packages list.
            self.cancelled.emit()

    def _handle_pending(self):
        """Status 1: Fresh package — stage + detect-duplicates in one call.

        Stops immediately on stage failure: no detect, no approve, no commit,
        no reset-commit, no auto-progress to step 2. Inline banner shows the
        humanized error.
        """
        pkg_id = self._current_package_id
        current_status = self._current_package_status or _PkgStatus.PENDING

        def on_done(result):
            if not result.success:
                self._hide_loading()
                self._show_initial_load_failed_banner()
                self._enter_blocking_error_state()
                return
            self._blocking_error_active = False
            duplicates_data = None
            if isinstance(result.data, dict):
                duplicates_data = result.data.get("detect")
            self._hide_error_banner()
            self._navigate_to_step2(duplicates_data)
            self._update_navigation()

        def on_error(error_type, msg_ar):
            # Synthesize a minimal failed result so _show_result_error
            # routes through the same UI path.
            class _SimpleResult:
                success = False
                message_ar = msg_ar
                message = msg_ar
                error = None
            self._show_result_error(_SimpleResult(), fallback_context="stage")
            self._enter_blocking_error_state()

        self._run_api(
            lambda: self.import_controller.stage_and_detect_if_pending(pkg_id, current_status),
            on_done,
            on_error=on_error,
            loading_msg=tr("wizard.import.loading_staging"),
        )

    def _handle_validating_start(self):
        """Status 2 (Validating): package was uploaded and is waiting for an
        explicit POST /stage trigger to start the pipeline.

        Backend reality (StagePackageCommandHandler):
          1. Updates DB status: Validating → Staging (early).
          2. Unpacks .uhc into staging tables.
          3. Runs the 8-level validation pipeline (synchronous).
          4. Auto-runs duplicate detection if validation passes.
          5. Final status: ReviewingConflicts | ReadyToCommit | ValidationFailed.

        The HTTP /stage call blocks for the full pipeline (tens of seconds
        to minutes). While it runs, we also poll /packages/{id} so the UI
        catches the early Validating→Staging flip and reflects the final
        status as soon as the request returns.
        """
        pkg_id = self._current_package_id
        if not pkg_id:
            return
        if self._pipeline_in_flight:
            logger.info(
                f"/stage already triggered for package {pkg_id}; keeping polling alive."
            )
            self._handle_in_progress(_PkgStatus.VALIDATING)
            return
        self._hide_error_banner()
        self._hide_loading()
        # Show the processing view immediately so the user gets feedback
        # while /stage runs synchronously on the backend.
        self._navigate_to_step2(duplicates_data=None, block_next=True)
        if self.step2 is not None and hasattr(self.step2, "set_status"):
            try:
                self.step2.set_status(_PkgStatus.VALIDATING)
            except Exception:
                pass

        # Run polling in parallel with the /stage request so we observe
        # the early Validating→Staging transition the backend writes to
        # the DB before the HTTP response returns.
        self._pipeline_in_flight = True
        self._stage_started_at_ms = QDateTime.currentMSecsSinceEpoch()
        logger.info(
            f"[import-flow] stage-start pkg={pkg_id} status_before={_PkgStatus.VALIDATING}"
            f"({_status_name(_PkgStatus.VALIDATING)})"
        )
        self._start_status_poll()

        def on_stage_done(result):
            duration = max(0, int(QDateTime.currentMSecsSinceEpoch() - self._stage_started_at_ms))
            if not result.success:
                # Stage failed (missing .uhc, validation pipeline crash, etc.).
                # Hard stop — block forward navigation, keep cancel and
                # back-to-list reachable.
                logger.warning(
                    f"[import-flow] stage-done pkg={pkg_id} ok=false "
                    f"duration={duration}ms msg={result.message}"
                )
                self._pipeline_in_flight = False
                self._stop_status_poll()
                self._show_result_error(result, fallback_context="stage")
                self._enter_blocking_error_state()
                return
            logger.info(
                f"[import-flow] stage-done pkg={pkg_id} ok=true duration={duration}ms"
            )
            # /stage succeeded. Re-fetch the package and route on the
            # canonical post-pipeline status (ReviewingConflicts /
            # ReadyToCommit / ValidationFailed).
            self._stop_status_poll()

            def _on_post_stage_fetched(pkg_result):
                if not pkg_result.success:
                    self._start_status_poll()
                    return
                new_status = pkg_result.data.get("status", 0)
                if isinstance(new_status, str) and new_status.isdigit():
                    new_status = int(new_status)
                self._current_package_status = new_status
                self._route_by_status(new_status)

            self._run_api(
                lambda: self.import_controller.get_package(pkg_id),
                _on_post_stage_fetched,
                on_error=lambda et, m: self._start_status_poll(),
                loading_msg="",
            )

        def on_stage_error(error_type, msg_ar):
            duration = max(0, int(QDateTime.currentMSecsSinceEpoch() - self._stage_started_at_ms))
            logger.warning(
                f"[import-flow] stage-error pkg={pkg_id} type={error_type} "
                f"duration={duration}ms msg={msg_ar}"
            )
            self._pipeline_in_flight = False
            self._stop_status_poll()
            class _SimpleResult:
                success = False
                message_ar = msg_ar
                message = msg_ar
                error = None
            self._show_result_error(_SimpleResult(), fallback_context="stage")
            self._enter_blocking_error_state()

        self._run_api(
            lambda: self.import_controller.stage_package(pkg_id),
            on_stage_done,
            on_error=on_stage_error,
            # No full-screen overlay — the processing widget shows the
            # active state with its own animated indicator.
            loading_msg="",
        )

    def _handle_in_progress(self, status: int):
        """Status 2/3: Backend is processing on the server. Show the new
        ImportStepProcessing view (which has its own animated sub-state
        indicator) and start polling. We do NOT call /stage again — that
        would make the backend re-attempt the same file and 500 every tick.
        We also do NOT show the wizard's full-screen loading overlay; the
        processing widget already conveys the active state.
        """
        self._hide_error_banner()
        self._hide_loading()
        self._navigate_to_step2(duplicates_data=None, block_next=True)
        # Make sure the new widget reflects the current sub-state.
        if self.step2 is not None and hasattr(self.step2, "set_status"):
            try:
                self.step2.set_status(status)
            except Exception:
                pass
        self._start_status_poll()

    def _handle_validation_failed(self):
        """Status 4: ValidationFailed — non-actionable terminal state."""
        self._set_buttons_enabled(True)
        self.terminal_state_message.emit(
            "error", tr("wizard.import.bounce_validation_failed")
        )
        self.cancelled.emit()

    def _handle_quarantined(self):
        """Status 5: Quarantined — non-actionable terminal state.

        Bounce back to the packages list AND emit a clear error toast so
        the user knows the package was quarantined (silent bounces caused
        confusion: users assumed the package had completed successfully).
        """
        self._set_buttons_enabled(True)
        self.terminal_state_message.emit(
            "error", tr("wizard.import.bounce_quarantined")
        )
        self.cancelled.emit()

    def _handle_reviewing_conflicts(self):
        """Status 6: Staged with conflicts.

        We DO NOT auto-emit `navigate_to_duplicates` here. That used to be
        convenient on first entry but caused an infinite redirect loop when
        the user came back from the duplicates page with conflicts still
        unresolved (set_package_id re-fetched, status was still 6, this
        handler emitted again, main_window navigated back to duplicates,
        repeat).

        Instead we:
          1. Show the new processing widget with sub-state=reviewing_conflicts
             — it has a built-in conflict-count card and a "حل التعارضات
             الآن" button that emits navigate_to_duplicates only when the
             user explicitly clicks.
          2. Fetch the live unresolved-conflicts count and feed it to the
             widget so the user sees exactly how many remain.
          3. If the count is 0 but status is still ReviewingConflicts (the
             rare case where the backend hasn't transitioned), call /approve
             which the backend accepts only if all conflicts are truly
             resolved — and re-route on the new status.
        """
        pkg_id = self._current_package_id or ""
        if not pkg_id:
            return

        self._hide_error_banner()
        # Show a generic loading state FIRST — do NOT render the
        # ReviewingConflicts card yet. Otherwise the user sees a momentary
        # "still has conflicts" UI flash before the auto-rescue kicks in.
        # The processing widget is only revealed once we know there's
        # actually something pending.
        self._show_loading(tr("wizard.import.loading_checking_status"))

        def on_count_done(count_result):
            count = (
                int(count_result.data or 0)
                if getattr(count_result, "success", False)
                else 0
            )

            if count == 0:
                # Backend status is still ReviewingConflicts but no
                # PendingReview conflicts remain. Skip showing the
                # conflict-count UI entirely — go straight to /approve.
                # The backend accepts only if all are truly resolved and
                # rejects safely otherwise.
                logger.info(
                    "Status=ReviewingConflicts but conflict count is 0 — "
                    "attempting /approve to force advance"
                )

                def on_approve_done(approve_result):
                    if not approve_result.success:
                        # Backend refused; surface the conflict-review UI
                        # now so the user can inspect what's still pending.
                        logger.warning(
                            "Approve rejected: %s — falling back to "
                            "conflict-review widget",
                            approve_result.message,
                        )
                        self._hide_loading()
                        self._show_reviewing_conflicts_widget(0)
                        return
                    # Re-fetch status and route from there. _route_by_status
                    # will hide the loading overlay when it draws the next
                    # screen.
                    self._refresh_status_and_route()

                self._run_api(
                    lambda: self.import_controller.approve_package(pkg_id),
                    on_approve_done,
                    on_error=lambda et, m: (
                        self._hide_loading(),
                        self._show_reviewing_conflicts_widget(0),
                    ),
                    loading_msg="",
                )
                return

            # count > 0 — there really are unresolved conflicts. Reveal the
            # processing widget with the count so the user can act on them.
            self._hide_loading()
            self._show_reviewing_conflicts_widget(count)

        def on_count_error(error_type, msg_ar):
            logger.warning(f"Conflict count fetch failed ({error_type}): {msg_ar}")
            # Best-effort: assume there might be conflicts and let the user
            # inspect them manually.
            self._hide_loading()
            self._show_reviewing_conflicts_widget(0)

        self._run_api(
            lambda: self.import_controller.get_conflict_count_for_package(pkg_id),
            on_count_done,
            on_error=on_count_error,
            loading_msg="",
        )

    def _show_reviewing_conflicts_widget(self, count: int):
        """Reveal the processing widget in ReviewingConflicts state."""
        self._navigate_to_step2(duplicates_data=None, block_next=True)
        if self.step2 is not None and hasattr(self.step2, "set_status"):
            try:
                self.step2.set_status(_PkgStatus.REVIEWING_CONFLICTS)
            except Exception:
                pass
        if self.step2 is not None and hasattr(self.step2, "set_conflict_count"):
            try:
                self.step2.set_conflict_count(int(count))
            except Exception:
                pass

    def _refresh_status_and_route(self):
        """Fetch the current package status from the server and route on it.

        Used as the success continuation after a /approve attempt during
        the ReviewingConflicts → ReadyToCommit rescue path.
        """
        pkg_id = self._current_package_id
        if not pkg_id:
            return

        def on_done(pkg_result):
            if not pkg_result.success:
                return
            new_status = pkg_result.data.get("status", 0)
            if isinstance(new_status, str) and new_status.isdigit():
                new_status = int(new_status)
            self._current_package_status = new_status
            self._route_by_status(new_status)

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_done,
            on_error=lambda et, m: None,
            loading_msg="",
        )

    def _handle_ready_to_commit(self):
        """Status 7: ReadyToCommit — land directly on the Review step.

        After conflicts are resolved (or none existed), the user comes
        back here. They've already done the processing/validation work,
        so showing step 1 (processing) again is a wasted click. Jump
        straight to step 2 (review staged entities) where they can
        inspect the data and press the commit button.
        """
        self._hide_error_banner()
        self._hide_loading()
        # Both ensure calls are needed: step2 lives at index 0 in the
        # stack and step_review at index 1. We build them lazily so the
        # stack ordering stays correct, then switch to index 1.
        self._ensure_step2(duplicates_data=None, skip_load=True)
        self._ensure_step_review()
        self.current_step = 1
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _handle_committing(self):
        """Status 8: Commit in progress — show progress and poll."""
        self._ensure_step2(duplicates_data=None)
        self._ensure_step_review()
        self._ensure_step_commit()
        self.current_step = 2  # step_commit (internal index 2)
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()
        if self.step_commit and hasattr(self.step_commit, 'set_committing'):
            self.step_commit.set_committing(True)
        self._show_loading(tr("wizard.import.loading_committing_server"))
        self._start_status_poll()

    def _handle_terminal_report(self):
        """Status 9: Completed — show the final report.

        Only Completed renders the report. PartiallyCompleted bounces to
        the packages list with a warning toast.
        """
        if self._current_package_status == _PkgStatus.COMPLETED:
            self._navigate_to_report()
            return
        # PartiallyCompleted — bounce with explicit warning.
        self._set_buttons_enabled(True)
        self.terminal_state_message.emit(
            "warning", tr("wizard.import.bounce_partially_completed")
        )
        self.cancelled.emit()

    def _handle_failed(self):
        """Status 10: Failed — non-actionable terminal state."""
        self._set_buttons_enabled(True)
        self.terminal_state_message.emit(
            "error", tr("wizard.import.bounce_failed")
        )
        self.cancelled.emit()

    def _handle_cancelled(self):
        """Status 12: Cancelled — non-actionable terminal state."""
        self._set_buttons_enabled(True)
        self.terminal_state_message.emit(
            "info", tr("wizard.import.bounce_cancelled")
        )
        self.cancelled.emit()

    # -- Navigation helpers ---------------------------------------------------

    def _navigate_to_step2(self, duplicates_data=None, block_next=False):
        """Navigate to the processing/validation step (internal index 0)."""
        self._ensure_step2(duplicates_data)
        self.current_step = 0
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()
        if block_next:
            self.btn_next.setEnabled(False)

    def _navigate_to_report(self):
        """Navigate directly to the Final Report step (terminal statuses only).

        We build ONLY step_report — there is no reason to spin up the
        processing/review/commit widgets for a terminal package the user
        will only view and then leave. setCurrentWidget locks the visible
        child regardless of QStackedWidget index ordering.
        """
        # Tear down any other step widgets first to keep the stack clean.
        for step_attr in ("step2", "step_review", "step_commit"):
            step = getattr(self, step_attr, None)
            if step is not None:
                try:
                    self.step_container.removeWidget(step)
                except Exception:
                    pass
                try:
                    step.deleteLater()
                except Exception:
                    pass
                setattr(self, step_attr, None)

        self._ensure_step_report()
        # current_step kept at 3 for _update_navigation's report-step branch.
        self.current_step = 3
        if self.step_report is not None:
            self.step_container.setCurrentWidget(self.step_report)
        self._update_navigation()

    # -- Status polling for transient states ----------------------------------

    def _reset_poll_tracking(self):
        """Reset local poll telemetry used to detect unchanged backend status."""
        self._poll_count = 0
        self._poll_last_status = None
        self._poll_unchanged_count = 0
        self._poll_warned = False
        self._poll_started_at = None

    def _start_status_poll(self):
        """Start polling package status for in-progress operations."""
        self._reset_poll_tracking()
        self._poll_started_at = QDateTime.currentDateTime()

        if self._status_poll_timer is None:
            self._status_poll_timer = QTimer(self)
            self._status_poll_timer.timeout.connect(self._poll_package_status)

        timeout_secs = self._max_polls_session * (_STATUS_POLL_INTERVAL_MS // 1000)
        logger.info(
            f"[import-flow] poll-start pkg={self._current_package_id} "
            f"interval={_STATUS_POLL_INTERVAL_MS // 1000}s timeout={timeout_secs}s"
        )
        self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)

    def _pause_status_poll(self):
        """Pause the poll timer while one API request is in flight.

        This preserves poll telemetry. A pause is not the end of the polling
        session; it only prevents overlapping get_package calls.
        """
        if self._status_poll_timer is not None:
            self._status_poll_timer.stop()

    def _stop_status_poll(self):
        """Stop status polling and clear transient poll tracking state."""
        if self._status_poll_timer is not None and self._poll_started_at is not None:
            elapsed_secs = self._current_poll_elapsed_secs()
            logger.info(
                f"[import-flow] poll-stop pkg={self._current_package_id} "
                f"polls={self._poll_count} elapsed={elapsed_secs}s"
            )
        self._pause_status_poll()
        self._reset_poll_tracking()

    def _current_poll_elapsed_secs(self) -> int:
        """Return elapsed seconds since the current polling session started."""
        if self._poll_started_at is None:
            return 0

        try:
            return max(0, int(self._poll_started_at.secsTo(QDateTime.currentDateTime())))
        except Exception:
            return 0

    def _poll_package_status(self):
        """Check current package status (async) and re-route if changed."""
        self._poll_count += 1
        if self._poll_count >= self._max_polls_session:
            elapsed_secs = self._current_poll_elapsed_secs()
            if not self._timeout_extension_used:
                # First timeout — give the user a choice instead of a silent
                # error. Polling stays paused until the user picks an option.
                logger.warning(
                    f"[import-flow] TIMEOUT pkg={self._current_package_id} "
                    f"polls={self._poll_count} elapsed={elapsed_secs}s next=user_decision"
                )
                self._pause_status_poll()
                self._hide_loading()
                self._show_timeout_decision_banner(elapsed_secs)
                return
            # Already extended — give up.
            logger.error(
                f"[import-flow] TIMEOUT-FINAL pkg={self._current_package_id} "
                f"polls={self._poll_count} elapsed={elapsed_secs}s"
            )
            self._stop_status_poll()
            self._hide_loading()
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._set_buttons_enabled(True)
            self._show_error(tr("wizard.import.error_timeout"))
            return

        # Pause the timer during the API call so a slow response does not
        # overlap with the next scheduled tick. This is only a pause: we must
        # keep poll telemetry alive across requests.
        self._pause_status_poll()
        pkg_id = self._current_package_id

        # Measure round-trip latency for honest heartbeat reporting.
        request_started_ms = QDateTime.currentMSecsSinceEpoch()
        poll_n = self._poll_count

        def on_poll_result(result):
            latency_ms = max(0, int(QDateTime.currentMSecsSinceEpoch() - request_started_ms))
            if not result.success:
                logger.warning(
                    f"[import-flow] poll-fail pkg={pkg_id} #{poll_n} "
                    f"latency={latency_ms}ms msg={result.message}"
                )
                if self.step2 is not None and hasattr(self.step2, "set_heartbeat"):
                    try:
                        self.step2.set_heartbeat(False, latency_ms)
                    except Exception:
                        pass
                self._show_loading(tr("wizard.import.loading_processing_server"))
                self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)
                return

            new_status = result.data.get("status", 0)
            old_status = self._poll_last_status

            backend_updated_at = ""
            if isinstance(result.data, dict):
                backend_updated_at = (
                    result.data.get("updatedAt")
                    or result.data.get("lastUpdatedAt")
                    or result.data.get("modifiedAt")
                    or ""
                )

            if new_status in _PkgStatus.TRANSIENT:
                self._hide_loading()

                if new_status == old_status:
                    self._poll_unchanged_count += 1
                else:
                    self._poll_last_status = new_status
                    self._poll_unchanged_count = 1
                    self._poll_warned = False

                if self.step2 is not None and hasattr(self.step2, "set_heartbeat"):
                    try:
                        self.step2.set_heartbeat(True, latency_ms, backend_updated_at)
                    except Exception:
                        pass

                if self.step2 is not None and hasattr(self.step2, "set_status"):
                    try:
                        self.step2.set_status(new_status)
                    except Exception:
                        pass

                if old_status is not None and new_status != old_status:
                    logger.info(
                        f"[import-flow] STATUS-CHANGE pkg={pkg_id} #{poll_n} "
                        f"{old_status}({_status_name(old_status)})->"
                        f"{new_status}({_status_name(new_status)}) latency={latency_ms}ms"
                    )
                else:
                    logger.info(
                        f"[import-flow] poll-tick #{poll_n} pkg={pkg_id} "
                        f"status={new_status}({_status_name(new_status)}) "
                        f"unchanged_x{self._poll_unchanged_count} latency={latency_ms}ms"
                    )

                if (
                    self._poll_unchanged_count >= _STUCK_WARN_POLLS
                    and not self._poll_warned
                ):
                    self._show_warning_banner(tr("wizard.import.warning_server_slow"))
                    self._poll_warned = True

                elapsed_secs = self._current_poll_elapsed_secs()
                if self._poll_unchanged_count >= _STUCK_RETRY_POLLS:
                    logger.warning(
                        f"[import-flow] STUCK pkg={pkg_id} status={new_status} "
                        f"unchanged_x{self._poll_unchanged_count} elapsed={elapsed_secs}s"
                    )
                    self._show_stuck_banner(elapsed_secs)

                self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)
                return

            logger.info(
                f"[import-flow] STATUS-CHANGE pkg={pkg_id} #{poll_n} "
                f"{old_status}({_status_name(old_status)})->"
                f"{new_status}({_status_name(new_status)}) latency={latency_ms}ms (transitioned out)"
            )
            self._hide_loading()
            if self.step2 is not None and hasattr(self.step2, "set_heartbeat"):
                try:
                    self.step2.set_heartbeat(True, latency_ms, backend_updated_at)
                except Exception:
                    pass
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._route_by_status(new_status)

        def on_poll_error(error_type, msg_ar):
            latency_ms = max(0, int(QDateTime.currentMSecsSinceEpoch() - request_started_ms))
            logger.warning(
                f"[import-flow] poll-error pkg={pkg_id} #{poll_n} "
                f"type={error_type} latency={latency_ms}ms msg={msg_ar}"
            )
            if self.step2 is not None and hasattr(self.step2, "set_heartbeat"):
                try:
                    self.step2.set_heartbeat(False, latency_ms, "")
                except Exception:
                    pass
            self._show_loading(tr("wizard.import.loading_processing_server"))
            self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_poll_result,
            on_error=on_poll_error,
            loading_msg=""
        )

    # -- Step transitions (with status guards) --------------------------------

    def _transition_step2_to_review(self):
        """Processing → Review: show staged entities for review."""
        self._ensure_step_review()
        self.current_step = 1  # step_review (internal index 1)
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_review_to_commit(self):
        """Review -> Commit: re-check status, then approve (only if not yet
        approved). Stop and show inline error on every failure — never let
        an approve-failure cascade into commit."""
        pkg_id = self._current_package_id

        def on_status_fetched(pkg_result):
            if not pkg_result.success:
                self._set_buttons_enabled(True)
                self._show_result_error(pkg_result, fallback_context="load_package")
                return
            status = pkg_result.data.get("status", 0)
            self._current_package_status = status

            if status == _PkgStatus.READY_TO_COMMIT:
                self._hide_error_banner()
                self._ensure_step_commit()
                self.current_step = 2  # step_commit
                self.step_container.setCurrentIndex(self.current_step)
                self._update_navigation()
                return

            if status in _PkgStatus.TERMINAL:
                self._navigate_to_report()
                return

            if status == _PkgStatus.VALIDATION_FAILED:
                self._set_buttons_enabled(True)
                self._show_error_banner(tr("wizard.import.error_validation_errors"))
                return

            # Status is something else (e.g. ReviewingConflicts) — don't try
            # to approve; surface a clear message.
            self._set_buttons_enabled(True)
            self._show_error_banner(tr("api.error.conflict"))

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_status_fetched,
            loading_msg=tr("wizard.import.loading_checking_status")
        )

    def _transition_commit_to_report(self):
        """Commit -> Report: approve first, then commit, then show report."""
        pkg_id = self._current_package_id

        def on_status_fetched(pkg_result):
            if pkg_result.success:
                status = pkg_result.data.get("status", 0)
                self._current_package_status = status

                if status in _PkgStatus.TERMINAL:
                    self._navigate_to_report()
                    self.completed.emit({"package_id": pkg_id})
                    return

                if status == _PkgStatus.COMMITTING:
                    if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                        self.step_commit.set_committing(True)
                    self._show_loading(tr("wizard.import.loading_committing_server"))
                    self._start_status_poll()
                    return

            # Always approve first, then commit
            self._run_api(
                lambda: self.import_controller.approve_package(pkg_id),
                on_approve_done,
                on_error=on_approve_error,
                loading_msg=tr("wizard.import.loading_approving")
            )

        def on_approve_done(approve_result):
            if not approve_result.success:
                # STOP. Do not call commit on a package the backend refused
                # to approve — that's how stage failures cascaded into
                # reset-commit before. Show the inline error.
                if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                    self.step_commit.set_committing(False)
                self._set_buttons_enabled(True)
                self._show_result_error(approve_result, fallback_context="approve")
                return

            self._hide_error_banner()
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(True)

            self._run_api(
                lambda: self.import_controller.commit_package(pkg_id),
                on_commit_done,
                on_error=on_commit_error,
                loading_msg=tr("wizard.import.loading_committing")
            )

        def on_approve_error(error_type, msg_ar):
            class _SimpleResult:
                success = False
                message_ar = msg_ar
                message = msg_ar
                error = None
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._set_buttons_enabled(True)
            self._show_result_error(_SimpleResult(), fallback_context="approve")

        def on_commit_done(commit_result):
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)

            if not commit_result.success:
                # Don't navigate to the Final Report just because commit
                # failed in flight — re-fetch status and let the wizard
                # route based on what the server actually says.
                self._set_buttons_enabled(True)
                self._show_result_error(commit_result, fallback_context="commit")
                self._refresh_status_silently()
                return

            self._hide_error_banner()
            self._current_package_status = _PkgStatus.COMPLETED
            self._ensure_step_report()
            self.current_step = 3  # step_report
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()
            self.completed.emit({"package_id": pkg_id})

        def on_commit_error(error_type, msg_ar):
            class _SimpleResult:
                success = False
                message_ar = msg_ar
                message = msg_ar
                error = None
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._set_buttons_enabled(True)
            self._show_result_error(_SimpleResult(), fallback_context="commit")
            # Network drop during commit: do NOT assume failure. Re-check
            # status from the server before changing the UI.
            self._refresh_status_silently()

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_status_fetched,
            loading_msg=tr("wizard.import.loading_checking_status")
        )

    def _refresh_status_silently(self):
        """Re-fetch the current package's backend status without re-routing.

        Used after an inline error to make sure the wizard reflects the
        true server state — e.g. if commit dropped the connection but the
        backend still completed it, we'll see status=Completed and route
        the user to the report.
        """
        pkg_id = self._current_package_id
        if not pkg_id:
            return

        def on_done(result):
            if not result.success:
                return
            new_status = result.data.get("status", 0)
            if isinstance(new_status, str) and new_status.isdigit():
                new_status = int(new_status)
            self._current_package_status = new_status

            if new_status == _PkgStatus.COMMITTING:
                logger.info(
                    f"Package {self._current_package_id} is still COMMITTING after apparent commit failure; resuming polling."
                )
                self._hide_error_banner()
                self._handle_committing()
                return

            # Only auto-navigate if the new state is meaningfully different
            # (e.g. backend confirmed Completed while we thought commit failed).
            if new_status in (
                _PkgStatus.COMPLETED, _PkgStatus.PARTIALLY_COMPLETED,
                _PkgStatus.FAILED,
            ):
                self._route_by_status(new_status)

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_done,
            on_error=lambda et, m: None,
            loading_msg="",
        )

    # -- Retry failed commit --------------------------------------------------

    def _retry_failed_commit(self):
        """Reset a failed commit, but only after the user explicitly confirms
        AND provides a reason (the backend persists it in the audit trail
        and rejects the request with 400 otherwise).
        """
        pkg_id = self._current_package_id
        if not pkg_id:
            return

        from ui.error_handler import ErrorHandler
        if not ErrorHandler.confirm(
            self,
            tr("import.error.reset_confirm_body"),
            tr("import.error.reset_confirm_title"),
        ):
            return

        # Same BottomSheet reason prompt as the cancel-package flow.
        reason = _prompt_reason_via_bottom_sheet(
            self,
            title=tr("import.error.reset_reason_title"),
            field_label=tr("import.error.reset_reason_prompt"),
            submit_text=tr("action.retry"),
            cancel_text=tr("action.dismiss"),
        )
        if not reason:
            self._show_error_banner(tr("import.error.reset_reason_required"))
            return

        def on_reset_done(result):
            if not result.success:
                self._set_buttons_enabled(True)
                self._show_result_error(result, fallback_context="reset_commit")
                return
            self._hide_error_banner()
            self._current_package_status = _PkgStatus.READY_TO_COMMIT
            self._ensure_step_commit()
            self.current_step = 2  # step_commit
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

        self._run_api(
            lambda: self.import_controller.reset_commit(pkg_id, reason=reason),
            on_reset_done,
            loading_msg=tr("wizard.import.loading_resetting")
        )

    # -- Lazy step creation ---------------------------------------------------

    def _ensure_step2(self, duplicates_data=None, skip_load=False):
        """Create or rebuild the processing-step widget at internal index 0.

        The legacy ImportStep2Staging (validation-zeros table + "clean data"
        banner) is intentionally NOT used anymore — see
        ui/pages/import_step_processing.py for the new clean UI.
        """
        if self.step2 is not None:
            self.step_container.removeWidget(self.step2)
            self.step2.deleteLater()

        from ui.pages.import_step_processing import ImportStepProcessing
        self.step2 = ImportStepProcessing(
            self.import_controller,
            self._current_package_id,
            duplicates_data=duplicates_data,
            skip_load=skip_load,
            parent=self,
        )
        self.step2.resolve_duplicates_requested.connect(self._on_resolve_duplicates)
        # Pre-paint the new widget with the current status so the user
        # never sees a blank processing pane before the first poll tick.
        if self._current_package_status:
            try:
                self.step2.set_status(self._current_package_status)
            except Exception:
                pass
        # insertWidget pins the slot (index 0) even if other steps already
        # exist, so setCurrentIndex(0) reliably shows the processing view.
        self.step_container.insertWidget(0, self.step2)

    def _ensure_step_review(self, skip_load=False):
        """Create or rebuild Review step at internal index 1."""
        if self.step_review is not None:
            self.step_container.removeWidget(self.step_review)
            self.step_review.deleteLater()

        from ui.pages.import_step4_review import ImportStep4Review
        self.step_review = ImportStep4Review(
            self.import_controller,
            self._current_package_id,
            skip_load=skip_load,
            parent=self
        )
        self.step_container.insertWidget(1, self.step_review)

    def _ensure_step_commit(self, skip_load=False):
        """Create or rebuild Commit step at internal index 2."""
        if self.step_commit is not None:
            self.step_container.removeWidget(self.step_commit)
            self.step_commit.deleteLater()

        from ui.pages.import_step5_commit import ImportStep5Commit
        self.step_commit = ImportStep5Commit(
            self.import_controller,
            self._current_package_id,
            skip_load=skip_load,
            parent=self
        )
        self.step_container.insertWidget(2, self.step_commit)

    def _ensure_step_report(self):
        """Create or rebuild Report step at internal index 3."""
        if self.step_report is not None:
            self.step_container.removeWidget(self.step_report)
            self.step_report.deleteLater()

        from ui.pages.import_step6_report import ImportStep6Report
        self.step_report = ImportStep6Report(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.insertWidget(3, self.step_report)

    # -- Navigation state -----------------------------------------------------

    def _update_navigation(self):
        """Update navigation buttons and step indicator based on current step.

        Internal step indices (post step1 removal):
          0 = processing / validation
          1 = review staged entities
          2 = commit confirmation / progress
          3 = final report (terminal)
        """
        self._update_step_indicator(self.current_step)

        # Cancel button visible AND enabled on processing / review / commit
        # steps (0-2). Without explicitly re-enabling here, a previous
        # `_set_buttons_enabled(False)` (fired during any in-flight API
        # worker) leaves the cancel button greyed out forever — even after
        # the call succeeds and the user lands on a step where cancelling
        # is a perfectly valid action. The Final Report step (3) hides
        # cancel entirely since the package is already terminal.
        cancel_visible = 0 <= self.current_step <= 2
        self.btn_cancel.setVisible(cancel_visible)
        self.btn_cancel.setEnabled(cancel_visible)
        # Back-to-list is always enabled and visible — it's non-destructive.
        self.btn_back.setEnabled(True)
        # Reset Next visibility; terminal report for non-failed statuses hides it below.
        self.btn_next.setVisible(True)

        # Hard-error state takes precedence over per-step logic — keep
        # Next disabled regardless of which step we're on.
        if self._blocking_error_active:
            self.btn_next.setEnabled(False)
            self.btn_next.setToolTip(tr("wizard.import.error_next_blocked"))
            return

        if self.current_step == 0:
            if self._current_package_status == _PkgStatus.VALIDATION_FAILED:
                self.btn_next.setText(tr("wizard.import.btn_validation_failed_cancel"))
                self.btn_next.setEnabled(True)
                self.btn_next.setToolTip("")
            elif self._current_package_status == _PkgStatus.REVIEWING_CONFLICTS:
                self.btn_next.setText(tr("wizard.import.btn_resolve_conflicts_first"))
                self.btn_next.setEnabled(False)
                self.btn_next.setToolTip("")
            elif self._current_package_status in (
                _PkgStatus.PENDING,
                _PkgStatus.VALIDATING,
                _PkgStatus.STAGING,
                _PkgStatus.COMMITTING,
            ):
                self.btn_next.setText(tr("action.next_arrow"))
                self.btn_next.setEnabled(False)
                self.btn_next.setToolTip(tr("wizard.import.next_blocked_transient"))
            else:
                self.btn_next.setText(tr("action.next_arrow"))
                self.btn_next.setEnabled(True)
                self.btn_next.setToolTip("")

        elif self.current_step == 1:
            # Review staged entities.
            self.btn_next.setText(tr("wizard.import.btn_approve_and_import"))
            self.btn_next.setEnabled(True)

        elif self.current_step == 2:
            # Commit confirmation — only enable when server confirms readiness.
            self.btn_next.setText(tr("wizard.import.btn_approve_and_import"))
            can_commit = self._current_package_status == _PkgStatus.READY_TO_COMMIT
            self.btn_next.setEnabled(can_commit)
            if not can_commit:
                if self._current_package_status == _PkgStatus.REVIEWING_CONFLICTS:
                    self.btn_next.setToolTip(tr("wizard.import.tooltip_approve_disabled_conflicts"))
                elif self._current_package_status == _PkgStatus.VALIDATION_FAILED:
                    self.btn_next.setToolTip(tr("wizard.import.tooltip_approve_disabled_validation"))
                else:
                    self.btn_next.setToolTip(tr("wizard.import.tooltip_approve_disabled_not_ready"))
            else:
                self.btn_next.setToolTip("")

        elif self.current_step == 3:
            # Final Report — Back-to-list is the normal exit; only FAILED
            # exposes a Retry primary action.
            self.btn_cancel.setVisible(False)
            if self._current_package_status == _PkgStatus.FAILED:
                self.btn_next.setText(tr("action.retry"))
                self.btn_next.setStyleSheet(StyleManager.nav_button_primary())
                self.btn_next.setVisible(True)
                self.btn_next.setEnabled(True)
            else:
                self.btn_next.setVisible(False)

    def enable_next_button(self, enabled: bool):
        """Allow steps to enable/disable next button."""
        self.btn_next.setEnabled(enabled)

    # -- Cancel package -------------------------------------------------------

    def _cancel_validation_failed_package(self):
        """Validation failed — cancel package and navigate to packages list."""
        pkg_id = self._current_package_id
        logger.info(f"Validation failed — leaving wizard for package: {pkg_id}")

        self.cancelled.emit()

        if pkg_id:
            def on_cancel_done(cancel_result):
                if not cancel_result.success:
                    logger.warning(f"Cancel failed: {cancel_result.message}")
                self.refresh()

            self._run_api(
                lambda: self.import_controller.cancel_package(pkg_id),
                on_cancel_done,
                loading_msg=""
            )
        else:
            self.refresh()

    def _on_cancel_package(self):
        """Cancel the current import package (async) and reset the wizard."""
        if not self._current_package_id:
            return

        # Block cancellation while the server is actively committing — the
        # backend does not support safe rollback mid-commit.
        if self._current_package_status == _PkgStatus.COMMITTING:
            self._show_error(tr("api.error.conflict"))
            return

        # Prompt for the cancellation reason via the project's BottomSheet
        # design (matches the office-survey cancel-reason flow in
        # main_window_v2). Reason is required — empty submission is rejected.
        reason = _prompt_reason_via_bottom_sheet(
            self,
            title=tr("wizard.import.cancel_reason_title"),
            field_label=tr("wizard.import.cancel_reason_prompt"),
            submit_text=tr("wizard.import.cancel_package"),
            cancel_text=tr("action.dismiss"),
        )
        if not reason:
            return

        logger.info(f"Cancelling package {self._current_package_id} — reason={reason!r}")
        pkg_id = self._current_package_id

        def on_cancel_done(cancel_result):
            if not cancel_result.success:
                logger.error(f"Cancel failed: {cancel_result.message}")
                self._set_buttons_enabled(True)
                self._show_error(cancel_result.message_ar or tr("wizard.import.error_cancel_failed"))
                return

            # Reset wizard internal state BEFORE emitting cancelled so the
            # packages page sees a clean slate when it gets focus. Then
            # navigate via cancelled.emit() — main_window is wired to
            # switch to IMPORT_PACKAGES on this signal. We do NOT call
            # self.refresh() afterwards: the wizard is no longer visible,
            # and a refresh would re-fetch the cancelled package's status
            # and re-route based on stale state.
            self._show_success(tr("wizard.import.success_package_cancelled"))
            self._stop_status_poll()
            self._cancel_active_worker()
            self._teardown_step_widgets()
            self._current_package_id = None
            self._current_package_status = 0
            self._current_package_name = ""
            self._pipeline_in_flight = False
            self._hide_loading()
            self._hide_error_banner()
            self.cancelled.emit()

        self._run_api(
            lambda: self.import_controller.cancel_package(pkg_id, reason=reason),
            on_cancel_done,
            loading_msg=tr("wizard.import.loading_cancelling")
        )

    # -- Error/Success display ------------------------------------------------

    def _show_error(self, message: str):
        """Show error message via notification."""
        from ui.error_handler import ErrorHandler
        ErrorHandler.show_error(self, message)

    def _show_success(self, message: str):
        """Show success message via notification."""
        from ui.error_handler import ErrorHandler
        ErrorHandler.show_success(self, message)

    # -- Public interface -----------------------------------------------------

    def refresh(self, data=None):
        """Refresh hook called by main_window when this page becomes visible.

        Behavior:
          • If `data` is a non-empty package id (string), route the wizard to
            the right step for that package. This is the normal entry path:
            the user clicked a package in ImportPackagesPage and main_window
            forwarded the id via `navigate_to(IMPORT_WIZARD, pkg_id)`.
          • If `data` is None and a package is already loaded/in-flight, do
            nothing — never tear down a routed sub-step a moment after it was
            set (would race the async status fetch).
          • Otherwise reset the wizard to a clean idle state. The legacy
            step1 package list is no longer the production entry point; we
            keep the reset path only for explicit "new import" scenarios.
        """
        # Case 1: data carries a package id → route to the right step.
        if isinstance(data, str) and data:
            self.set_package_id(data)
            return

        # Case 2: a package is loaded/in-flight → leave the routed UI alone.
        if self._current_package_id:
            return

        # Case 3: no package, no in-flight work → idle reset.
        # The wizard is only meant to be used with a specific package id;
        # entering it idle means the user navigated here by mistake (or
        # through a stale signal). Tear down any loaded step widgets and
        # bounce back to the packages list so we never leave the user on
        # an empty, confusing screen.
        self._cancel_active_worker()
        self._stop_status_poll()
        self._hide_loading()

        for step_attr in ('step_report', 'step_commit', 'step_review', 'step2'):
            step = getattr(self, step_attr, None)
            if step is not None:
                self.step_container.removeWidget(step)
                step.deleteLater()
                setattr(self, step_attr, None)

        self._current_package_id = None
        self._current_package_status = 0
        self._current_package_name = ""
        self.current_step = 0
        self.cancelled.emit()

    def _on_resolve_duplicates(self):
        """Handle resolve duplicates button from step 2."""
        from ui.error_handler import ErrorHandler
        confirmed = ErrorHandler.confirm(
            self,
            tr("wizard.import.resolve_duplicates_confirm_msg"),
            tr("wizard.import.resolve_duplicates_confirm_title")
        )
        if confirmed:
            self.navigate_to_duplicates.emit(self._current_package_id or "")

    # ----- Public API used by main_window_v2 ---------------------------------

    def _teardown_step_widgets(self):
        """Remove every step widget from the QStackedWidget.

        Called whenever a new package id arrives so the lazy `_ensure_step*`
        methods can rebuild the stack in the right order. Removing in
        reverse-creation order keeps Qt's child indices predictable.
        """
        for step_attr in ("step_report", "step_commit", "step_review", "step2"):
            step = getattr(self, step_attr, None)
            if step is not None:
                try:
                    self.step_container.removeWidget(step)
                except Exception:
                    pass
                try:
                    step.deleteLater()
                except Exception:
                    pass
                setattr(self, step_attr, None)
        self.current_step = 0

    def set_package_id(self, package_id: str):
        """Entry point from the packages list. Stores the id, fetches fresh
        status and routes to the right internal step."""
        package_id = str(package_id) if package_id else ""
        logger.info(f"[import-flow] open pkg={package_id}")
        self._current_package_id = package_id
        self._current_package_status = 0
        self._current_package_name = ""
        # New package = fresh slate. Clear any blocking-error state from
        # the previous package so Next is re-enabled by the per-step logic.
        self._blocking_error_active = False
        # Also clear the per-session pipeline flag — without this, a
        # VALIDATING status on the new package would be misread as
        # "/stage already triggered for this package" and we'd never
        # actually post /stage, leaving the wizard stuck.
        self._pipeline_in_flight = False
        # Fresh timeout budget for the new package.
        self._timeout_extension_used = False
        self._max_polls_session = _MAX_POLL_COUNT
        self._stop_status_poll()
        self._cancel_active_worker()
        # Tear down any step widgets left over from a previous package, so
        # the lazy _ensure_step* methods rebuild the QStackedWidget in the
        # correct order starting from an empty stack. Without this, stale
        # widgets keep their slots and setCurrentIndex(0) can land on the
        # wrong child (e.g. the step_review "Entity Review" screen instead
        # of the new processing view).
        self._teardown_step_widgets()
        self._hide_error_banner()
        if not package_id:
            self.refresh()
            return

        def on_status_fetched(pkg_result):
            if not pkg_result.success:
                self._hide_loading()
                self._set_buttons_enabled(True)
                self._show_initial_load_failed_banner()
                self._enter_blocking_error_state()
                return
            data = pkg_result.data or {}
            self._current_package_name = (
                data.get("fileName") or data.get("packageName") or data.get("id") or ""
            )
            status = data.get("status", 1)
            if isinstance(status, str) and status.isdigit():
                status = int(status)
            self._route_by_status(status)
            # Defensive: if routing failed to put SOMETHING on screen
            # (no widget added to the stack), at least show the processing
            # widget so the user isn't stuck on a blank pane.
            #
            # Skip the fallback for terminal/non-actionable statuses whose
            # handlers intentionally bounce back to the packages list via
            # cancelled.emit(). Drawing a processing widget after the bounce
            # creates a confusing flash and the empty-stack warning.
            from services.import_status_map import is_actionable_status
            if (
                self.step_container.count() == 0
                and is_actionable_status(status)
            ):
                logger.warning(
                    "Routing left an empty stack for status %s — showing processing fallback",
                    status,
                )
                self._navigate_to_step2(duplicates_data=None, block_next=True)

        def on_status_error(error_type, msg_ar):
            self._hide_loading()
            self._set_buttons_enabled(True)
            self._show_initial_load_failed_banner()
            self._enter_blocking_error_state()

        self._run_api(
            lambda: self.import_controller.get_package(package_id),
            on_status_fetched,
            on_error=on_status_error,
            loading_msg=tr("wizard.import.loading_checking_connection"),
        )

    def current_package_name(self) -> str:
        """Return the current package's display name (for UI banners)."""
        return self._current_package_name or ""

    def refresh_current_package(self):
        """Re-fetch the current package status and re-route accordingly.

        Called when returning from the duplicates page so the wizard reflects
        any conflicts resolved during navigation.
        """
        if not self._current_package_id:
            return
        # Reuse set_package_id for its status-fetch + routing logic.
        self.set_package_id(self._current_package_id)

    def hideEvent(self, event):
        """Stop polling + workers when this page is hidden (e.g. user
        navigates to another page).

        IMPORTANT: this must be hideEvent, NOT leaveEvent. Qt's leaveEvent
        fires whenever the mouse cursor merely leaves the widget area —
        which happens dozens of times during normal use. If we kill polling
        on every mouse-leave, the wizard appears frozen even though the
        backend is fine. Found via [import-flow] logs:
          [import-flow] poll-start ... timeout=120s
          [import-flow] poll-stop polls=0 elapsed=2s   ← caused by mouse move
        """
        try:
            self._cancel_active_worker()
            self._stop_status_poll()
            self._pipeline_in_flight = False
            self._hide_loading()
        except Exception:
            pass
        super().hideEvent(event)

    def refresh_from_duplicates(self):
        """Re-check package status after returning from duplicates page.

        If still REVIEWING_CONFLICTS, try to approve (backend verifies
        all conflicts for this package are resolved). If approve succeeds,
        the package advances to READY_TO_COMMIT.
        """
        if not self._current_package_id:
            return
        pkg_id = self._current_package_id

        self._show_loading(tr("page.import_wizard.checking_package"))

        def on_status_result(result):
            if not result.success:
                self._hide_loading()
                self._start_status_poll()
                return

            new_status = result.data.get("status", 0)
            logger.info(f"Post-duplicates status: package {pkg_id} -> status {new_status}")

            if new_status != _PkgStatus.REVIEWING_CONFLICTS:
                self._hide_loading()
                self._route_by_status(new_status)
                return

            # Still REVIEWING_CONFLICTS — try to approve directly
            # Backend will reject if conflicts remain for this package
            logger.info(f"Attempting to approve package {pkg_id} after conflict resolution")
            self._show_loading(tr("page.import_wizard.approving_package"))
            self._run_api(
                lambda: self.import_controller.approve_package(pkg_id),
                on_approve_done,
                on_error=on_approve_error,
                loading_msg=""
            )

        def on_approve_done(approve_result):
            logger.info(f"Approve result: success={approve_result.success}")
            self._hide_loading()
            # Re-poll to get the new status after approval
            self._start_status_poll()

        def on_approve_error(error_type, msg_ar):
            Toast.show_toast(self, tr("wizard.import.data_load_failed"), Toast.ERROR)
            logger.warning(f"Approve after conflicts failed ({error_type}): {msg_ar}")
            self._hide_loading()
            # Conflicts might not all be resolved — show step2 as before
            self._route_by_status(_PkgStatus.REVIEWING_CONFLICTS)

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_status_result,
            on_error=lambda et, m: (self._hide_loading(), self._start_status_poll()),
            loading_msg=""
        )

    def configure_for_role(self, role: str):
        """Store user role for RBAC and propagate to steps."""
        self._user_role = role
        for step_attr in ('step2', 'step_review', 'step_commit', 'step_report'):
            step = getattr(self, step_attr, None)
            if step is not None and hasattr(step, 'configure_for_role'):
                step.configure_for_role(role)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Wizard header
        self.header.set_title(tr("wizard.import.title"))
        self.header.set_subtitle(tr("wizard.import.subtitle"))

        # Update step names in header
        step_names = [tr(key) for key in _STEP_NAMES_KEYS]
        self.header.set_steps(step_names)

        # Footer buttons
        self.btn_back.setText(tr("wizard.import.back_to_list"))
        self.btn_cancel.setText(tr("wizard.import.cancel_package"))

        # Next button text depends on current step
        self._update_navigation()

        # Loading label
        self._loading_label.setText(tr("status.processing"))

        # Propagate to child steps
        for step_attr in ('step2', 'step_review', 'step_commit', 'step_report'):
            step = getattr(self, step_attr, None)
            if step is not None and hasattr(step, 'update_language'):
                step.update_language(is_arabic)
