# -*- coding: utf-8 -*-
"""Centralized error handler for UI layer."""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QEventLoop, QTimer

from services.error_mapper import map_exception
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)

# Hard ceiling on how long ``confirm()`` will block the caller. The dialog is
# modal so the user is in control, but if a programming error leaves the
# bottom sheet without firing either signal the local event loop would hang
# forever. Ten minutes is far longer than any legitimate confirmation, short
# enough that an actual stuck dialog is recoverable instead of freezing the app.
_CONFIRM_MAX_WAIT_MS = 10 * 60 * 1000


class ErrorHandler:
    """Centralized error handler using Toast and BottomSheet."""

    @staticmethod
    def handle(error: Exception, parent: QWidget = None,
               context: str = None, show_dialog: bool = True) -> str:
        logger.error(f"Error in {context or 'unknown'}: {error}", exc_info=True)
        message = map_exception(error, context)
        if show_dialog and parent:
            ErrorHandler.show_error(parent, message)
        return message

    @staticmethod
    def show_error(parent: QWidget, message: str, title: str = None):
        from ui.components.toast import Toast
        Toast.show_toast(parent, message, Toast.ERROR)

    @staticmethod
    def show_warning(parent: QWidget, message: str, title: str = None):
        from ui.components.toast import Toast
        Toast.show_toast(parent, message, Toast.WARNING)

    @staticmethod
    def show_success(parent: QWidget, message: str, title: str = None):
        from ui.components.toast import Toast
        Toast.show_toast(parent, message, Toast.SUCCESS)

    @staticmethod
    def show_info(parent: QWidget, message: str, title: str = None):
        from ui.components.toast import Toast
        Toast.show_toast(parent, message, Toast.INFO)

    @staticmethod
    def confirm(parent: QWidget, message: str, title: str = None) -> bool:
        """Modal yes/no confirmation; blocks until user answers.

        Falls back to ``False`` (i.e. as if the user cancelled) if the
        sheet is destroyed without emitting a signal or if the safety
        timeout fires — this keeps an unresponsive sheet from freezing
        the whole app while still treating ambiguity as the safer choice
        for destructive actions (delete, discard, etc.).
        """
        if title is None:
            title = tr("dialog.confirm")
        from ui.components.bottom_sheet import BottomSheet
        result = [False]
        loop = QEventLoop()

        sheet = BottomSheet(parent)
        sheet.confirmed.connect(lambda: _set_and_quit(result, True, loop))
        sheet.cancelled.connect(lambda: _set_and_quit(result, False, loop))
        # If the sheet is destroyed (e.g. parent window closed) before
        # either signal fires, treat it as a cancel rather than block forever.
        sheet.destroyed.connect(lambda *_: _safe_quit(loop))
        # Belt-and-braces: a single-shot timer is the last line of defence
        # against a completely stuck dialog. Logged so we can find the bug
        # if this ever fires in production.
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.setInterval(_CONFIRM_MAX_WAIT_MS)
        timeout.timeout.connect(lambda: (
            logger.warning("ErrorHandler.confirm timed out; treating as cancel"),
            _safe_quit(loop),
        ))
        timeout.start()
        try:
            sheet.show_confirm(title, message)
            loop.exec_()
        finally:
            timeout.stop()
        return result[0]


def _set_and_quit(container, value, loop):
    container[0] = value
    _safe_quit(loop)


def _safe_quit(loop: QEventLoop) -> None:
    """Quit a local event loop only if it is still running.

    ``QEventLoop.quit`` is a no-op on a loop that never started or already
    exited, but calling it on a loop owned by a destroyed C++ object would
    raise. Guarding with ``isRunning`` keeps the destroyed-signal fallback
    safe when Qt tears widgets down out of order during shutdown.
    """
    try:
        if loop.isRunning():
            loop.quit()
    except RuntimeError:
        pass
