# -*- coding: utf-8 -*-
"""
MessageDialog - Helper functions for common dialog types.
"""

import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QEventLoop

from .base_dialog import BaseDialog, DialogType
from utils.logger import get_logger

logger = get_logger(__name__)


class MessageDialog:
    """Static helper class for showing common dialog types."""

    @staticmethod
    def show_success(
        parent: QWidget,
        title: str,
        message: str,
        button_text: str = "حسناً"
    ) -> None:
        """Show success dialog with green checkmark icon."""
        # Try to load success icon
        icon_path = MessageDialog._get_icon_path("success.png")

        def on_ok():
            pass  # Just close dialog

        dialog = BaseDialog(
            parent=parent,
            dialog_type=DialogType.SUCCESS,
            title=title,
            message=message,
            buttons=[(button_text, on_ok)],
            icon_path=icon_path
        )

        dialog.show()
        MessageDialog._exec_blocking(dialog)

    @staticmethod
    def show_error(
        parent: QWidget,
        title: str,
        message: str,
        button_text: str = "حسناً"
    ) -> None:
        """Show error dialog with red X icon."""
        # Try to load error icon
        icon_path = MessageDialog._get_icon_path("error.png")

        def on_ok():
            pass  # Just close dialog

        dialog = BaseDialog(
            parent=parent,
            dialog_type=DialogType.ERROR,
            title=title,
            message=message,
            buttons=[(button_text, on_ok)],
            icon_path=icon_path
        )

        dialog.show()
        MessageDialog._exec_blocking(dialog)

    @staticmethod
    def show_warning(
        parent: QWidget,
        title: str,
        message: str,
        button_text: str = "حسناً"
    ) -> None:
        """Show warning dialog with orange exclamation icon."""
        # Try to load warning icon
        icon_path = MessageDialog._get_icon_path("warning.png")

        def on_ok():
            pass  # Just close dialog

        dialog = BaseDialog(
            parent=parent,
            dialog_type=DialogType.WARNING,
            title=title,
            message=message,
            buttons=[(button_text, on_ok)],
            icon_path=icon_path
        )

        dialog.show()
        MessageDialog._exec_blocking(dialog)

    @staticmethod
    def show_info(
        parent: QWidget,
        title: str,
        message: str,
        button_text: str = "حسناً"
    ) -> None:
        """Show info dialog with blue info icon."""
        # Try to load info icon
        icon_path = MessageDialog._get_icon_path("info.png")

        def on_ok():
            pass  # Just close dialog

        dialog = BaseDialog(
            parent=parent,
            dialog_type=DialogType.INFO,
            title=title,
            message=message,
            buttons=[(button_text, on_ok)],
            icon_path=icon_path
        )

        dialog.show()
        MessageDialog._exec_blocking(dialog)

    @staticmethod
    def show_question(
        parent: QWidget,
        title: str,
        message: str,
        yes_text: str = "نعم",
        no_text: str = "لا"
    ) -> bool:
        """Show question dialog with Yes/No buttons. Returns True if confirmed."""
        # Try to load question icon
        icon_path = MessageDialog._get_icon_path("info.png")  # Use info icon for questions

        result = {"confirmed": False}

        def on_yes():
            result["confirmed"] = True

        def on_no():
            result["confirmed"] = False

        dialog = BaseDialog(
            parent=parent,
            dialog_type=DialogType.QUESTION,
            title=title,
            message=message,
            buttons=[(no_text, on_no), (yes_text, on_yes)],  # No first (safer default)
            icon_path=icon_path
        )

        dialog.show()
        MessageDialog._exec_blocking(dialog)

        return result["confirmed"]

    @staticmethod
    def _get_icon_path(filename: str) -> str:
        """Get full path to icon file, or None if not found."""
        # Try multiple possible locations
        possible_paths = [
            f"assets/images/{filename}",
            f"assets/icons/{filename}",
            f"ui/assets/images/{filename}",
            f"ui/assets/icons/{filename}",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                logger.debug(f"Found icon at: {path}")
                return path

        logger.debug(f"Icon not found: {filename}, using text symbol fallback")
        return None  # Will fall back to text symbols

    @staticmethod
    def _exec_blocking(dialog: BaseDialog):
        """Execute dialog in blocking mode (like QMessageBox.exec_())."""
        # Create event loop to block execution
        loop = QEventLoop()
        dialog.closed.connect(loop.quit)
        loop.exec_()
