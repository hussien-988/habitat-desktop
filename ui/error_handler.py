# -*- coding: utf-8 -*-
"""Centralized error handler for UI layer."""

from PyQt5.QtWidgets import QWidget

from services.error_mapper import map_exception
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorHandler:
    """Centralized error handler that maps exceptions to user-friendly dialogs."""

    @staticmethod
    def handle(error: Exception, parent: QWidget = None,
               context: str = None, show_dialog: bool = True) -> str:
        """
        Handle any exception: log it, map it, optionally show dialog.

        Args:
            error: The exception to handle
            parent: Parent widget for dialog
            context: Context for error mapping (e.g., "building", "unit")
            show_dialog: Whether to show dialog to user

        Returns:
            User-friendly error message string
        """
        logger.error(f"Error in {context or 'unknown'}: {error}", exc_info=True)

        message = map_exception(error, context)

        if show_dialog and parent:
            ErrorHandler._show_error_dialog(parent, message)

        return message

    @staticmethod
    def show_error(parent: QWidget, message: str, title: str = None):
        """Show error dialog with translated title."""
        if title is None:
            title = tr("dialog.error")
        ErrorHandler._show_error_dialog(parent, message, title)

    @staticmethod
    def show_warning(parent: QWidget, message: str, title: str = None):
        """Show warning dialog with translated title."""
        if title is None:
            title = tr("dialog.warning")
        ErrorHandler._show_warning_dialog(parent, message, title)

    @staticmethod
    def show_success(parent: QWidget, message: str, title: str = None):
        """Show success dialog with translated title."""
        if title is None:
            title = tr("dialog.success")
        ErrorHandler._show_success_dialog(parent, message, title)

    @staticmethod
    def confirm(parent: QWidget, message: str, title: str = None) -> bool:
        """Show confirmation dialog, return True if confirmed."""
        if title is None:
            title = tr("dialog.confirm")
        return ErrorHandler._show_question_dialog(parent, message, title)

    @staticmethod
    def _show_error_dialog(parent: QWidget, message: str, title: str = None):
        try:
            from ui.components.dialogs import MessageDialog
            MessageDialog.show_error(parent, title or tr("dialog.error"), message)
        except Exception:
            _fallback_dialog(parent, title or tr("dialog.error"), message, is_error=True)

    @staticmethod
    def _show_warning_dialog(parent: QWidget, message: str, title: str = None):
        try:
            from ui.components.dialogs import MessageDialog
            MessageDialog.show_warning(parent, title or tr("dialog.warning"), message)
        except Exception:
            _fallback_dialog(parent, title or tr("dialog.warning"), message)

    @staticmethod
    def _show_success_dialog(parent: QWidget, message: str, title: str = None):
        try:
            from ui.components.dialogs import MessageDialog
            MessageDialog.show_success(parent, title or tr("dialog.success"), message)
        except Exception:
            _fallback_dialog(parent, title or tr("dialog.success"), message)

    @staticmethod
    def _show_question_dialog(parent: QWidget, message: str, title: str = None) -> bool:
        try:
            from ui.components.dialogs import MessageDialog
            return MessageDialog.show_question(parent, title or tr("dialog.confirm"), message)
        except Exception:
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(parent, title or tr("dialog.confirm"), message)
            return reply == QMessageBox.Yes


def _fallback_dialog(parent, title, message, is_error=False):
    """Fallback to QMessageBox if custom dialogs fail."""
    from PyQt5.QtWidgets import QMessageBox
    if is_error:
        QMessageBox.critical(parent, title, message)
    else:
        QMessageBox.information(parent, title, message)
