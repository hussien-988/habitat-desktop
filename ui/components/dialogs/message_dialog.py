# -*- coding: utf-8 -*-
"""
MessageDialog - Helper functions for common dialog types

Provides easy-to-use functions for showing dialogs:
- Success messages
- Error messages
- Warning messages
- Information messages
- Yes/No questions

All dialogs follow Figma design specifications and include overlay.

Usage:
    from ui.components.dialogs import MessageDialog

    # Show success
    MessageDialog.show_success(self, "نجح", "تم الحفظ بنجاح")

    # Show error
    MessageDialog.show_error(self, "خطأ", "حدث خطأ أثناء الحفظ")

    # Show warning
    MessageDialog.show_warning(self, "تحذير", "يجب إدخال البيانات")

    # Show info
    MessageDialog.show_info(self, "معلومة", "استخدم زر البحث")

    # Ask question
    if MessageDialog.show_question(self, "تأكيد", "هل تريد الحفظ؟"):
        # User clicked Yes
        save_data()
"""

import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QEventLoop

from .base_dialog import BaseDialog, DialogType
from utils.logger import get_logger

logger = get_logger(__name__)


class MessageDialog:
    """
    Static helper class for showing common dialog types.

    All methods are static and return appropriate values:
    - show_success, show_error, show_warning, show_info: No return value
    - show_question: Returns True if user confirms, False otherwise
    """

    @staticmethod
    def show_success(
        parent: QWidget,
        title: str,
        message: str,
        button_text: str = "حسناً"
    ) -> None:
        """
        Show success dialog with green checkmark icon.

        Args:
            parent: Parent widget
            title: Dialog title (e.g., "نجح")
            message: Success message (e.g., "تم حفظ البيانات بنجاح")
            button_text: OK button text (default: "حسناً")
        """
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
        """
        Show error dialog with red X icon.

        Args:
            parent: Parent widget
            title: Dialog title (e.g., "خطأ")
            message: Error message (e.g., "حدث خطأ أثناء الحفظ")
            button_text: OK button text (default: "حسناً")
        """
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
        """
        Show warning dialog with orange exclamation icon.

        Args:
            parent: Parent widget
            title: Dialog title (e.g., "تحذير")
            message: Warning message (e.g., "يجب إدخال البيانات المطلوبة")
            button_text: OK button text (default: "حسناً")
        """
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
        """
        Show info dialog with blue info icon.

        Args:
            parent: Parent widget
            title: Dialog title (e.g., "معلومة")
            message: Information message (e.g., "استخدم زر البحث للمتابعة")
            button_text: OK button text (default: "حسناً")
        """
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
        """
        Show question dialog with Yes/No buttons.

        Args:
            parent: Parent widget
            title: Dialog title (e.g., "تأكيد")
            message: Question message (e.g., "هل تريد حفظ التغييرات؟")
            yes_text: Yes button text (default: "نعم")
            no_text: No button text (default: "لا")

        Returns:
            True if user clicked Yes, False if clicked No
        """
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
        """
        Get full path to icon file.

        Args:
            filename: Icon filename (e.g., "success.png")

        Returns:
            Full path to icon, or None if not found
        """
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
        """
        Execute dialog in blocking mode (like QMessageBox.exec_()).

        This ensures the dialog blocks execution until it's closed,
        making it work like traditional QMessageBox.

        Args:
            dialog: BaseDialog instance to execute
        """
        # Create event loop to block execution
        loop = QEventLoop()
        dialog.closed.connect(loop.quit)
        loop.exec_()
