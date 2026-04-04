# -*- coding: utf-8 -*-
"""Centralized error handler for UI layer."""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QEventLoop

from services.error_mapper import map_exception
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorHandler:
    """Centralized error handler using NotificationBar and BottomSheet."""

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
        from ui.components.notification_bar import NotificationBar
        NotificationBar.notify(parent, message, NotificationBar.ERROR)

    @staticmethod
    def show_warning(parent: QWidget, message: str, title: str = None):
        from ui.components.notification_bar import NotificationBar
        NotificationBar.notify(parent, message, NotificationBar.WARNING)

    @staticmethod
    def show_success(parent: QWidget, message: str, title: str = None):
        from ui.components.notification_bar import NotificationBar
        NotificationBar.notify(parent, message, NotificationBar.SUCCESS)

    @staticmethod
    def show_info(parent: QWidget, message: str, title: str = None):
        from ui.components.notification_bar import NotificationBar
        NotificationBar.notify(parent, message, NotificationBar.INFO)

    @staticmethod
    def confirm(parent: QWidget, message: str, title: str = None) -> bool:
        if title is None:
            title = tr("dialog.confirm")
        from ui.components.bottom_sheet import BottomSheet
        result = [False]
        loop = QEventLoop()

        sheet = BottomSheet(parent)
        sheet.confirmed.connect(lambda: _set_and_quit(result, True, loop))
        sheet.cancelled.connect(lambda: _set_and_quit(result, False, loop))
        sheet.show_confirm(title, message)
        loop.exec_()
        return result[0]


def _set_and_quit(container, value, loop):
    container[0] = value
    loop.quit()
