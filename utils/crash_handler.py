# -*- coding: utf-8 -*-
"""Global crash handler — catches anything PyQt would otherwise swallow.

PyQt does not propagate exceptions from slots; it prints the traceback to
stderr and continues. In a packaged Windows .exe with no console attached,
that means a crash is invisible to both the user (the action just silently
does nothing) and to support staff trying to triage a bug report later.

Installing ``sys.excepthook`` lets us intercept the same exceptions, write
them to a per-crash log file, and surface a friendly dialog so the user
knows something went wrong and can copy the details.
"""

import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


def _crash_log_path() -> Path:
    """Return ``logs/crash-YYYYMMDD-HHMMSS.log`` under the user-writable root.

    The directory matches where ``setup_logger`` writes ``app.log`` so support
    staff find both files in the same place.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("logs") / f"crash-{timestamp}.log"


def _write_crash_log(traceback_text: str) -> Optional[Path]:
    """Persist the traceback to a unique file; never raise, never overwrite.

    Returns the path on success or ``None`` if the filesystem refused the
    write (read-only volume, full disk, permission denied — all real on
    field laptops). The caller still gets a dialog either way.
    """
    try:
        path = _crash_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(traceback_text, encoding="utf-8")
        return path
    except Exception as e:
        logger.error(f"Failed to write crash log: {e}")
        return None


def _show_crash_dialog(traceback_text: str, log_path: Optional[Path]) -> None:
    """Show the user a non-fatal crash dialog with copy-to-clipboard support.

    Imports are local because this can run very early (before QApplication
    or translation manager are ready) or very late (during shutdown), and we
    want the handler to degrade to plain stderr in those windows rather than
    fail to report anything.
    """
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMessageBox, QPushButton, QStyle,
        )
    except Exception:
        # Qt is not importable — best we can do is stderr.
        sys.stderr.write(traceback_text)
        return

    app = QApplication.instance()
    if app is None:
        # Excepthook fired before QApplication was created (e.g. during
        # bootstrap). Nothing to show; let the log file speak.
        sys.stderr.write(traceback_text)
        return

    try:
        from services.translation_manager import tr
        title = tr("error.crash.title") or "Unexpected error"
        body = tr("error.crash.body") or (
            "An unexpected error occurred. The full report has been saved "
            "to the application logs folder. You can copy the technical "
            "details below to share with support."
        )
    except Exception:
        title = "Unexpected error"
        body = (
            "An unexpected error occurred. The full report has been saved "
            "to the application logs folder."
        )

    if log_path:
        body = f"{body}\n\n{log_path}"

    box = QMessageBox()
    box.setIcon(QStyle.SP_MessageBoxCritical if False else QMessageBox.Critical)
    box.setWindowTitle(title)
    box.setText(body)
    # Show the traceback in the expandable "details" area so it does not
    # dominate the window; users who do not care can ignore it.
    box.setDetailedText(traceback_text)
    copy_btn = QPushButton(_safe_tr("error.crash.copy", "Copy details"))
    box.addButton(copy_btn, QMessageBox.ActionRole)
    box.addButton(QMessageBox.Close)

    def _copy():
        try:
            QApplication.clipboard().setText(traceback_text)
        except Exception:
            pass

    copy_btn.clicked.connect(_copy)
    try:
        box.exec_()
    except Exception:
        # Even the dialog can fail in extreme conditions — never re-raise.
        pass


def _safe_tr(key: str, fallback: str) -> str:
    try:
        from services.translation_manager import tr
        msg = tr(key)
        return msg if msg and msg != key else fallback
    except Exception:
        return fallback


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    """The actual hook installed onto ``sys.excepthook``.

    KeyboardInterrupt is intentionally allowed to fall through to the
    default handler so Ctrl+C still works for developers running the app
    from a terminal.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    # Always log to the rotating app.log first — this is the most reliable
    # destination because the logger is set up before the hook is installed.
    try:
        logger.critical(f"Unhandled exception:\n{tb_text}")
    except Exception:
        pass

    log_path = _write_crash_log(tb_text)
    _show_crash_dialog(tb_text, log_path)


def install() -> None:
    """Install the crash handler. Idempotent — safe to call once at startup."""
    if sys.excepthook is _excepthook:
        return
    sys.excepthook = _excepthook
    logger.info("Global crash handler installed")
