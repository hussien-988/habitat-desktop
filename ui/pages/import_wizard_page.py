# -*- coding: utf-8 -*-
"""Import wizard page with 5-step processing pipeline."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QFrame, QPushButton,
    QHBoxLayout, QLabel, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QColor

from ui.components.wizard_header import WizardHeader
from ui.components.accent_line import AccentLine
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.exceptions import NetworkException, ApiException
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger
from ui.design_system import ScreenScale

logger = get_logger(__name__)

TOTAL_STEPS = 5

_STEP_NAMES_KEYS = [
    "wizard.import.step_select_package",
    "wizard.import.step_staging_validation",
    "wizard.import.step_review",
    "wizard.import.step_confirm",
    "wizard.import.step_report",
]


class _PkgStatus:
    """Package status codes from backend."""
    PENDING = 1
    VALIDATING = 2
    STAGING = 3
    VALIDATION_FAILED = 4
    QUARANTINED = 5
    REVIEWING_CONFLICTS = 6
    READY_TO_COMMIT = 7
    COMMITTING = 8
    COMPLETED = 9
    FAILED = 10
    PARTIALLY_COMPLETED = 11
    CANCELLED = 12

    # Transient states (backend is processing)
    TRANSIENT = {VALIDATING, STAGING, COMMITTING}
    # Terminal states (no more actions)
    TERMINAL = {COMPLETED, FAILED, PARTIALLY_COMPLETED, CANCELLED}


_STATUS_POLL_INTERVAL_MS = 5000  # 5 seconds
_MAX_POLL_COUNT = 60  # 60 polls × 5s = 5 minutes max


class _ApiWorker(QThread):
    """Worker thread for non-blocking API calls."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str, str)  # error_type ('network'|'api'|'unknown'), message_ar

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            self.finished.emit(result)
        except NetworkException as e:
            self.error.emit("network", tr("error.network_connection_failed"))
        except ApiException as e:
            from controllers.import_controller import ImportController
            msg = ImportController._api_error_msg(e, tr("error.server_error"))
            self.error.emit("api", msg)
        except Exception as e:
            logger.error(f"Unexpected worker error: {e}")
            self.error.emit("unknown", tr("error.unexpected_retry"))


class ImportWizardPage(QWidget):
    """
    Import Wizard - 5-Step Wizard Structure.

    Same structure as FieldWorkPreparationPage:
    1. Fixed header + step indicator
    2. QStackedWidget for steps
    3. Fixed footer with back/next + cancel button
    """

    completed = pyqtSignal(object)
    cancelled = pyqtSignal()
    navigate_to_duplicates = pyqtSignal()

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
        self._active_worker = None

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
        )
        outer_layout.addWidget(self.header)

        # Accent line (full-width)
        self._accent = AccentLine()
        outer_layout.addWidget(self._accent)

        # Step container (QStackedWidget)
        self.step_container = QStackedWidget()
        outer_layout.addWidget(self.step_container, 1)

        # Loading overlay (hidden)
        self._loading_overlay = self._create_loading_overlay()

        # Footer (fixed, full width)
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    # -- Step Indicator -------------------------------------------------------

    def _update_step_indicator(self, current: int):
        """Update step indicator in the dark wizard header."""
        self.header.set_current_step(current)

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

        overlay_layout.addWidget(card)

        # Dots animation timer
        self._dots_count = 0
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)

        return overlay

    def _show_loading(self, message: str):
        """Show loading overlay with a message."""
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)

    def _hide_loading(self):
        """Hide loading overlay."""
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

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
        if self.current_step == 0:
            self.step1._start_polling()

    def _set_buttons_enabled(self, enabled: bool):
        """Enable or disable navigation buttons (prevents double-click)."""
        self.btn_next.setEnabled(enabled)
        self.btn_back.setEnabled(enabled and self.current_step > 0 and self.current_step < 3)
        self.btn_cancel.setEnabled(enabled)

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
        self.btn_back = QPushButton(tr("action.back_arrow"))
        self.btn_back.setFixedSize(ScreenScale.w(252), ScreenScale.h(50))
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self.btn_back.setStyleSheet(StyleManager.nav_button_secondary())
        self.btn_back.clicked.connect(self._on_back)
        self.btn_back.setEnabled(False)
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
        """Create step placeholders. Steps are created lazily."""
        # Step 1: Incoming packages (select a package to process)
        from ui.pages.import_step1_packages import ImportStep1Packages
        self.step1 = ImportStep1Packages(
            self.import_controller,
            parent=self
        )
        self.step1.package_selected.connect(self._on_package_selected)
        self.step1.upload_completed.connect(self._on_upload_completed)
        self.step1.back_requested.connect(self.cancelled.emit)
        self.step_container.addWidget(self.step1)

        # Steps 2-5: created lazily when needed
        self.step2 = None        # staging + validation + duplicates
        self.step_review = None   # review (uses import_step4_review.py)
        self.step_commit = None   # commit (uses import_step5_commit.py)
        self.step_report = None   # report (uses import_step6_report.py)

        self.current_step = 0

    # -- Navigation ----------------------------------------------------------

    def _on_back(self):
        """Handle back button."""
        if self.current_step > 0 and self.current_step < 3:
            self.current_step -= 1
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

    def _on_next(self):
        """Handle next button — step transitions with controller calls."""
        if self.current_step == 0:
            self._transition_step1_to_step2()

        elif self.current_step == 1:
            if self._current_package_status == _PkgStatus.VALIDATION_FAILED:
                self._cancel_validation_failed_package()
                return
            self._transition_step2_to_review()

        elif self.current_step == 2:
            self._transition_review_to_commit()

        elif self.current_step == 3:
            self._transition_commit_to_report()

        elif self.current_step == 4:
            if self._current_package_status == _PkgStatus.FAILED:
                self._retry_failed_commit()
            else:
                self.refresh()

    def _on_package_selected(self, package_id: str):
        """Handle package selection from Step 1."""
        self.btn_next.setEnabled(bool(package_id))

    def _on_upload_completed(self, package_id: str):
        """After successful upload, auto-advance to processing."""
        if package_id:
            self._current_package_id = package_id
            self._transition_step1_to_step2()

    # -- State-aware routing --------------------------------------------------

    def _transition_step1_to_step2(self):
        """Step 1 -> next: health check, fetch fresh status, route accordingly (async)."""
        package_id = self.step1.get_selected_package_id()
        if not package_id:
            return

        self._current_package_id = package_id
        self.step1._stop_polling()

        def do_health_and_status():
            from services.api_client import get_api_client
            api = get_api_client()
            if not api.health_check():
                raise NetworkException("Server unreachable")
            return self.import_controller.get_package(package_id)

        def on_status_fetched(pkg_result):
            if not pkg_result.success:
                self._set_buttons_enabled(True)
                self._show_error(pkg_result.message_ar or tr("wizard.import.error_load_package"))
                self.step1._start_polling()
                return
            status = pkg_result.data.get("status", 1)
            self._route_by_status(status)

        def on_health_error(error_type, msg_ar):
            self._set_buttons_enabled(True)
            if error_type == "network":
                self._show_error(tr("error.cannot_connect_server"))
            else:
                self._show_error(msg_ar)
            self.step1._start_polling()

        self._run_api(
            do_health_and_status,
            on_status_fetched,
            on_error=on_health_error,
            loading_msg=tr("wizard.import.loading_checking_connection")
        )

    def _route_by_status(self, status: int):
        """Central router: direct to the correct wizard step based on package status."""
        self._current_package_status = status
        logger.info(f"Routing package {self._current_package_id} with status {status}")

        if status == _PkgStatus.PENDING:
            self._handle_pending()
        elif status in (_PkgStatus.VALIDATING, _PkgStatus.STAGING):
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
            self.btn_next.setEnabled(True)
            self.step1._start_polling()

    def _handle_pending(self):
        """Status 1: Fresh package — run staging then duplicate detection (async)."""
        pkg_id = self._current_package_id

        def do_stage():
            return self.import_controller.stage_package(pkg_id)

        def on_stage_done(stage_result):
            if not stage_result.success:
                logger.error(f"Staging failed: {stage_result.message}")
                self._set_buttons_enabled(True)
                self._show_error(stage_result.message_ar or tr("wizard.import.error_staging_failed"))
                self.step1._start_polling()
                return
            self._show_loading(tr("wizard.import.loading_detecting_duplicates"))
            self._run_api(
                lambda: self.import_controller.detect_duplicates(pkg_id),
                on_dup_done,
                on_error=on_dup_error,
                loading_msg=""
            )

        def on_dup_done(dup_result):
            duplicates_data = dup_result.data if dup_result.success else None
            if not dup_result.success:
                Toast.show_toast(self, tr("error.failed_load_data"), Toast.ERROR)
                logger.warning(f"Duplicate detection failed: {dup_result.message}")
            self._navigate_to_step2(duplicates_data)
            self._update_navigation()

        def on_dup_error(error_type, msg_ar):
            Toast.show_toast(self, tr("error.failed_load_data"), Toast.ERROR)
            logger.warning(f"Duplicate detection error ({error_type}): {msg_ar}")
            self._navigate_to_step2(duplicates_data=None)
            self._update_navigation()

        self._run_api(do_stage, on_stage_done, loading_msg=tr("wizard.import.loading_staging"))

    def _handle_in_progress(self, status: int):
        """Status 2/3: Backend is processing — trigger stage if needed, then poll."""
        pkg_id = self._current_package_id

        if status == _PkgStatus.VALIDATING:
            # Backend may need explicit /stage call to start actual processing.
            # Try stage; whether it succeeds or fails (409 = already processing), poll.
            def on_stage_result(result):
                if result.success:
                    logger.info(f"Stage triggered for package {pkg_id}")
                else:
                    logger.info(f"Stage returned: {result.message} — polling anyway")
                self._show_loading(tr("wizard.import.loading_server_check"))
                self._start_status_poll()

            def on_stage_error(error_type, msg_ar):
                logger.info(f"Stage error ({error_type}): {msg_ar} — polling anyway")
                self._show_loading(tr("wizard.import.loading_server_check"))
                self._start_status_poll()

            self._run_api(
                lambda: self.import_controller.stage_package(pkg_id),
                on_stage_result,
                on_error=on_stage_error,
                loading_msg=tr("wizard.import.loading_start_processing")
            )
        else:
            self._show_loading(tr("wizard.import.loading_staging_server"))
            self._start_status_poll()

    def _handle_validation_failed(self):
        """Status 4: Validation failed — show report, block forward."""
        self._navigate_to_step2(duplicates_data=None, block_next=True)

    def _handle_quarantined(self):
        """Status 5: Quarantined — show message, block completely."""
        self._show_error(tr("wizard.import.error_quarantined"))
        self.btn_next.setEnabled(True)
        self.step1._start_polling()

    def _handle_reviewing_conflicts(self):
        """Status 6: Staged with conflicts — try approve first, then show report."""
        pkg_id = self._current_package_id
        if not pkg_id:
            self._navigate_to_step2(duplicates_data=None)
            return

        # Try to approve — backend will succeed only if all conflicts are resolved
        self._show_loading(tr("wizard.import.loading_checking_conflicts"))

        def on_approve_ok(result):
            self._hide_loading()
            if result.success:
                logger.info(f"Package {pkg_id} approved after conflicts resolved")
                # Re-poll to get new status (should be READY_TO_COMMIT)
                self._start_status_poll()
            else:
                logger.info(f"Approve rejected (conflicts remain): {result.message}")
                self._navigate_to_step2(duplicates_data=None)

        def on_approve_err(error_type, msg_ar):
            self._hide_loading()
            logger.info(f"Approve failed ({error_type}) — showing conflicts step")
            self._navigate_to_step2(duplicates_data=None)

        self._run_api(
            lambda: self.import_controller.approve_package(pkg_id),
            on_approve_ok,
            on_error=on_approve_err,
            loading_msg=""
        )

    def _handle_ready_to_commit(self):
        """Status 7: Approved — show validation report, user navigates forward."""
        self._navigate_to_step2(duplicates_data=None)

    def _handle_committing(self):
        """Status 8: Commit in progress — show progress and poll."""
        self._ensure_step2(duplicates_data=None)
        self._ensure_step_review()
        self._ensure_step_commit()
        self.current_step = 3
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()
        if self.step_commit and hasattr(self.step_commit, 'set_committing'):
            self.step_commit.set_committing(True)
        self._show_loading(tr("wizard.import.loading_committing_server"))
        self._start_status_poll()

    def _handle_terminal_report(self):
        """Status 9/11: Completed or partially completed — show report."""
        self._navigate_to_report()

    def _handle_failed(self):
        """Status 10: Commit failed — show report with retry option."""
        self._navigate_to_report()

    def _handle_cancelled(self):
        """Status 12: Cancelled — should not reach here (filtered)."""
        self._show_error(tr("wizard.import.error_cancelled_package"))
        self.btn_next.setEnabled(True)
        self.step1._start_polling()

    # -- Navigation helpers ---------------------------------------------------

    def _navigate_to_step2(self, duplicates_data=None, block_next=False):
        """Navigate to Step 2 (staging/validation) and optionally block next."""
        self._ensure_step2(duplicates_data)
        self.current_step = 1
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()
        if block_next:
            self.btn_next.setEnabled(False)

    def _navigate_to_report(self):
        """Navigate directly to the report step (for terminal/completed statuses)."""
        self._ensure_step2(duplicates_data=None)
        self._ensure_step_review()
        self._ensure_step_commit()
        self._ensure_step_report()
        self.current_step = 4
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    # -- Status polling for transient states ----------------------------------

    def _start_status_poll(self):
        """Start polling package status for in-progress operations."""
        self._poll_count = 0
        if self._status_poll_timer is None:
            self._status_poll_timer = QTimer(self)
            self._status_poll_timer.timeout.connect(self._poll_package_status)
        self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)

    def _stop_status_poll(self):
        """Stop status polling."""
        if self._status_poll_timer is not None:
            self._status_poll_timer.stop()

    def _poll_package_status(self):
        """Check current package status (async) and re-route if changed."""
        self._poll_count += 1
        if self._poll_count >= _MAX_POLL_COUNT:
            self._stop_status_poll()
            self._hide_loading()
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._set_buttons_enabled(True)
            self._show_error(tr("wizard.import.error_timeout"))
            return

        # Pause timer during the API call, resume if still transient
        self._stop_status_poll()
        pkg_id = self._current_package_id

        def on_poll_result(result):
            if not result.success:
                logger.warning(f"Status poll failed: {result.message}")
                self._show_loading(tr("wizard.import.loading_processing_server"))
                self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)
                return

            new_status = result.data.get("status", 0)
            logger.info(f"Status poll #{self._poll_count}: package {pkg_id} -> status {new_status}")

            if new_status in _PkgStatus.TRANSIENT:
                # Re-show loading (hidden by _on_worker_done)
                if new_status == _PkgStatus.VALIDATING:
                    status_label = tr("wizard.import.status_validating")
                elif new_status == _PkgStatus.STAGING:
                    status_label = tr("wizard.import.status_staging")
                else:
                    status_label = tr("wizard.import.status_committing")
                self._show_loading(tr("wizard.import.loading_server_attempt").format(
                    status=status_label, attempt=self._poll_count
                ))
                self._status_poll_timer.start(_STATUS_POLL_INTERVAL_MS)
                return

            self._hide_loading()
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._route_by_status(new_status)

        def on_poll_error(error_type, msg_ar):
            logger.warning(f"Status poll error ({error_type}): {msg_ar}")
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
        """Step 2 -> Review: show staged entities for review."""
        self._ensure_step_review()
        self.current_step = 2
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_review_to_commit(self):
        """Review -> Commit: check status (async), approve if needed, then show confirmation."""
        pkg_id = self._current_package_id

        def on_status_fetched(pkg_result):
            if pkg_result.success:
                status = pkg_result.data.get("status", 0)
                self._current_package_status = status

                if status == _PkgStatus.READY_TO_COMMIT:
                    self._ensure_step_commit()
                    self.current_step = 3
                    self.step_container.setCurrentIndex(self.current_step)
                    self._update_navigation()
                    return

                if status in _PkgStatus.TERMINAL:
                    self._navigate_to_report()
                    return

                if status == _PkgStatus.VALIDATION_FAILED:
                    self._set_buttons_enabled(True)
                    self._show_error(tr("wizard.import.error_validation_errors"))
                    return

            # Proceed to approve
            self._run_api(
                lambda: self.import_controller.approve_package(pkg_id),
                on_approve_done,
                loading_msg=tr("wizard.import.loading_approving")
            )

        def on_approve_done(approve_result):
            if not approve_result.success:
                logger.error(f"Approve failed: {approve_result.message}")
                self._set_buttons_enabled(True)
                self._show_error(approve_result.message_ar or tr("wizard.import.error_approve_failed"))
                return

            self._current_package_status = _PkgStatus.READY_TO_COMMIT
            self._ensure_step_commit()
            self.current_step = 3
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

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
                logger.warning(f"Approve returned: {approve_result.message}")
                # Continue to commit anyway (might already be approved)

            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(True)

            self._run_api(
                lambda: self.import_controller.commit_package(pkg_id),
                on_commit_done,
                on_error=on_commit_error,
                loading_msg=tr("wizard.import.loading_committing")
            )

        def on_approve_error(error_type, msg_ar):
            logger.warning(f"Approve error ({error_type}): {msg_ar} — proceeding to commit")
            # Proceed to commit even if approve fails (might already be approved)
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(True)

            self._run_api(
                lambda: self.import_controller.commit_package(pkg_id),
                on_commit_done,
                on_error=on_commit_error,
                loading_msg=tr("wizard.import.loading_committing")
            )

        def on_commit_done(commit_result):
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)

            if not commit_result.success:
                logger.error(f"Commit failed: {commit_result.message}")
                self._set_buttons_enabled(True)
                self._show_error(commit_result.message_ar or tr("wizard.import.error_commit_failed"))
                return

            self._current_package_status = _PkgStatus.COMPLETED
            self._ensure_step_report()
            self.current_step = 4
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()
            self.completed.emit({"package_id": pkg_id})

        def on_commit_error(error_type, msg_ar):
            if self.step_commit and hasattr(self.step_commit, 'set_committing'):
                self.step_commit.set_committing(False)
            self._set_buttons_enabled(True)
            self._show_error(msg_ar)

        self._run_api(
            lambda: self.import_controller.get_package(pkg_id),
            on_status_fetched,
            loading_msg=tr("wizard.import.loading_checking_status")
        )

    # -- Retry failed commit --------------------------------------------------

    def _retry_failed_commit(self):
        """Reset a failed commit (async) and navigate back to commit step."""
        pkg_id = self._current_package_id

        def on_reset_done(result):
            if not result.success:
                self._set_buttons_enabled(True)
                self._show_error(result.message_ar or tr("wizard.import.error_reset_failed"))
                return

            self._current_package_status = _PkgStatus.READY_TO_COMMIT
            self._ensure_step_commit()
            self.current_step = 3
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

        self._run_api(
            lambda: self.import_controller.reset_commit(pkg_id),
            on_reset_done,
            loading_msg=tr("wizard.import.loading_resetting")
        )

    # -- Lazy step creation ---------------------------------------------------

    def _ensure_step2(self, duplicates_data=None):
        """Create or rebuild Step 2: Staging + Validation + Duplicates."""
        if self.step2 is not None:
            self.step_container.removeWidget(self.step2)
            self.step2.deleteLater()

        from ui.pages.import_step2_staging import ImportStep2Staging
        self.step2 = ImportStep2Staging(
            self.import_controller,
            self._current_package_id,
            duplicates_data=duplicates_data,
            parent=self
        )
        self.step2.resolve_duplicates_requested.connect(self._on_resolve_duplicates)
        self.step_container.addWidget(self.step2)

    def _ensure_step_review(self):
        """Create or rebuild Review step (uses import_step4_review)."""
        if self.step_review is not None:
            self.step_container.removeWidget(self.step_review)
            self.step_review.deleteLater()

        from ui.pages.import_step4_review import ImportStep4Review
        self.step_review = ImportStep4Review(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step_review)

    def _ensure_step_commit(self):
        """Create or rebuild Commit step (uses import_step5_commit)."""
        if self.step_commit is not None:
            self.step_container.removeWidget(self.step_commit)
            self.step_commit.deleteLater()

        from ui.pages.import_step5_commit import ImportStep5Commit
        self.step_commit = ImportStep5Commit(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step_commit)

    def _ensure_step_report(self):
        """Create or rebuild Report step (uses import_step6_report)."""
        if self.step_report is not None:
            self.step_container.removeWidget(self.step_report)
            self.step_report.deleteLater()

        from ui.pages.import_step6_report import ImportStep6Report
        self.step_report = ImportStep6Report(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step_report)

    # -- Navigation state -----------------------------------------------------

    def _update_navigation(self):
        """Update navigation buttons and step indicator based on current step."""
        self._update_step_indicator(self.current_step)

        # Cancel button visible on steps 2-4 (index 1-3)
        self.btn_cancel.setVisible(1 <= self.current_step <= 3)

        if self.current_step == 0:
            self.btn_back.setEnabled(False)
            self.btn_next.setText(tr("wizard.import.btn_start_processing"))
            has_selection = (
                hasattr(self, 'step1')
                and hasattr(self.step1, 'get_selected_package_id')
                and bool(self.step1.get_selected_package_id())
            )
            self.btn_next.setEnabled(has_selection)

        elif self.current_step == 1:
            self.btn_back.setEnabled(True)
            if self._current_package_status == _PkgStatus.VALIDATION_FAILED:
                self.btn_next.setText(tr("wizard.import.btn_validation_failed_cancel"))
                self.btn_next.setEnabled(True)
            elif self._current_package_status == _PkgStatus.REVIEWING_CONFLICTS:
                self.btn_next.setText(tr("wizard.import.btn_resolve_conflicts_first"))
                self.btn_next.setEnabled(False)
            else:
                self.btn_next.setText(tr("action.next_arrow"))
                self.btn_next.setEnabled(True)

        elif self.current_step == 2:
            self.btn_back.setEnabled(True)
            self.btn_next.setText(tr("wizard.import.btn_approve_and_import"))
            self.btn_next.setEnabled(True)

        elif self.current_step == 3:
            self.btn_back.setEnabled(False)
            self.btn_next.setText(tr("wizard.import.btn_commit_data"))
            self.btn_next.setEnabled(True)

        elif self.current_step == 4:
            self.btn_back.setEnabled(False)
            self.btn_cancel.setVisible(False)
            if self._current_package_status == _PkgStatus.FAILED:
                self.btn_next.setText(tr("action.retry"))
            else:
                self.btn_next.setText(tr("wizard.import.btn_new_import"))
            self.btn_next.setEnabled(True)

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

        from ui.error_handler import ErrorHandler
        if not ErrorHandler.confirm(
            self,
            tr("dialog.import.confirm_cancel_message"),
            tr("dialog.import.confirm_cancel_title")
        ):
            return

        logger.info(f"Cancelling package: {self._current_package_id}")
        pkg_id = self._current_package_id

        def on_cancel_done(cancel_result):
            if not cancel_result.success:
                logger.error(f"Cancel failed: {cancel_result.message}")
                self._set_buttons_enabled(True)
                self._show_error(cancel_result.message_ar or tr("wizard.import.error_cancel_failed"))
                return

            self._show_success(tr("wizard.import.success_package_cancelled"))
            self.cancelled.emit()
            self.refresh()

        self._run_api(
            lambda: self.import_controller.cancel_package(pkg_id),
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
        """Reset wizard to step 1 for a new import."""
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
        self.current_step = 0
        self.step_container.setCurrentIndex(0)
        self._update_navigation()

        if hasattr(self.step1, 'reset'):
            self.step1.reset()
        if hasattr(self.step1, '_start_polling'):
            self.step1._start_polling()

    def _on_resolve_duplicates(self):
        """Handle resolve duplicates button from step 2."""
        from ui.error_handler import ErrorHandler
        confirmed = ErrorHandler.confirm(
            self,
            tr("wizard.import.resolve_duplicates_confirm_msg"),
            tr("wizard.import.resolve_duplicates_confirm_title")
        )
        if confirmed:
            self.navigate_to_duplicates.emit()

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
        for step_attr in ('step1', 'step2', 'step_review', 'step_commit', 'step_report'):
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
        self.btn_back.setText(tr("action.back_arrow"))
        self.btn_cancel.setText(tr("wizard.import.cancel_package"))

        # Next button text depends on current step
        self._update_navigation()

        # Loading label
        self._loading_label.setText(tr("status.processing"))

        # Propagate to child steps
        for step_attr in ('step1', 'step2', 'step_review', 'step_commit', 'step_report'):
            step = getattr(self, step_attr, None)
            if step is not None and hasattr(step, 'update_language'):
                step.update_language(is_arabic)
