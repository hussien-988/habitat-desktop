# -*- coding: utf-8 -*-
"""User inactivity/session timeout monitoring for the desktop client."""

from datetime import datetime, timezone
from typing import Optional

from PyQt5.QtCore import QObject, QEvent, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from utils.logger import get_logger


logger = get_logger(__name__)


class IdleSessionMonitor(QObject):
    """Track meaningful user activity and emit warning/timeout events."""

    warning = pyqtSignal(int)
    timed_out = pyqtSignal()
    resumed_after_warning = pyqtSignal()

    def __init__(
        self,
        parent=None,
        warning_seconds: int = 60,
    ):
        super().__init__(parent)

        self.warning_seconds = warning_seconds
        self.timeout_seconds: Optional[int] = None

        self._last_activity_at: Optional[datetime] = None
        self._warning_emitted = False
        self._active = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check_timeout)

        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def start(self, timeout_minutes: int):
        """Start tracking a new authenticated session."""
        timeout_minutes = max(1, int(timeout_minutes))

        self.timeout_seconds = timeout_minutes * 60
        self._last_activity_at = datetime.now(timezone.utc)
        self._warning_emitted = False
        self._active = True

        self._timer.start()

        logger.info(
            "Idle session monitoring started (%s minutes)",
            timeout_minutes,
        )

    def update_timeout(self, timeout_minutes: int):
        """Update policy without resetting the user's last activity."""
        timeout_minutes = max(1, int(timeout_minutes))
        self.timeout_seconds = timeout_minutes * 60

        logger.info(
            "Idle session timeout updated to %s minutes",
            timeout_minutes,
        )

        self._check_timeout()

    def stop(self):
        self._active = False
        self._timer.stop()
        self._last_activity_at = None
        self._warning_emitted = False

    def record_activity(self):
        if not self._active:
            return

        was_in_warning = self._warning_emitted

        self._last_activity_at = datetime.now(timezone.utc)
        self._warning_emitted = False

        if was_in_warning:
            self.resumed_after_warning.emit()

    def extend(self):
        """Explicitly extend the session without emitting activity signals."""
        if not self._active:
            return

        self._last_activity_at = datetime.now(timezone.utc)
        self._warning_emitted = False

    def seconds_remaining(self) -> Optional[int]:
        if (
            not self._active
            or self.timeout_seconds is None
            or self._last_activity_at is None
        ):
            return None

        elapsed = (
            datetime.now(timezone.utc)
            - self._last_activity_at
        ).total_seconds()

        return int(self.timeout_seconds - elapsed)

    def _check_timeout(self):
        remaining = self.seconds_remaining()

        if remaining is None:
            return

        if remaining <= 0:
            logger.info("Session timed out because of inactivity")
            self.stop()
            self.timed_out.emit()
            return

        if (
            remaining <= self.warning_seconds
            and not self._warning_emitted
        ):
            self._warning_emitted = True

            logger.info(
                "Session warning emitted with %s seconds remaining",
                remaining,
            )

            self.warning.emit(remaining)

    def eventFilter(self, obj, event):
        if not self._active:
            return False

        event_type = event.type()

        # Deliberate user interaction.
        if event_type in (
            QEvent.MouseButtonPress,
            QEvent.KeyPress,
            QEvent.Wheel,
            QEvent.TouchBegin,
        ):
            self.record_activity()

        # Returning from background/sleep must check the real elapsed time
        # before treating anything as new activity.
        elif event_type == QEvent.ApplicationActivate:
            QTimer.singleShot(0, self._check_timeout)

        return False