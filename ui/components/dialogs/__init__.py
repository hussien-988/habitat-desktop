# -*- coding: utf-8 -*-
"""
Dialog Components Package

Unified dialog system for the application following Figma design specifications.

This package provides:
- BaseDialog: Core dialog with overlay and consistent styling
- MessageDialog: Pre-configured dialogs for common use cases (success, error, warning, info, question)
- ConfirmationDialog: Reusable confirmation dialogs with custom buttons (save draft, discard, etc.)
- DialogType: Constants for dialog types

BACKWARD COMPATIBILITY:
- ConfirmDialog, ErrorDialog, InfoDialog: Legacy dialogs (deprecated, use MessageDialog instead)

Usage:
    from ui.components.dialogs import MessageDialog, ConfirmationDialog

    # Show success message
    MessageDialog.show_success(self, "نجح", "تم حفظ البيانات بنجاح")

    # Show error message
    MessageDialog.show_error(self, "خطأ", "حدث خطأ أثناء الحفظ")

    # Show warning
    MessageDialog.show_warning(self, "تحذير", "يجب إدخال البيانات المطلوبة")

    # Show info
    MessageDialog.show_info(self, "معلومة", "استخدم زر البحث للمتابعة")

    # Show question (returns bool)
    if MessageDialog.show_question(self, "تأكيد", "هل تريد حفظ التغييرات؟"):
        # User clicked Yes
        save_data()

    # Show save draft confirmation (UC-001 S28, UC-004 S22)
    result = ConfirmationDialog.save_draft_confirmation(
        parent=self,
        title="هل تريد الحفظ؟",
        message="لديك تغييرات غير محفوظة.\\nهل تريد حفظها كمسودة؟"
    )
    if result == ConfirmationDialog.SAVE:
        save_as_draft()
    elif result == ConfirmationDialog.DISCARD:
        discard_changes()
    # else: cancelled (do nothing)
"""

from .base_dialog import BaseDialog, DialogType
from .message_dialog import MessageDialog
from .confirmation_dialog import ConfirmationDialog
from .password_dialog import PasswordDialog
from .language_dialog import LanguageDialog
from .logout_dialog import LogoutDialog
from .security_dialog import SecurityDialog

# Import legacy dialogs for backward compatibility
try:
    from .common_dialogs import ConfirmDialog, ErrorDialog, InfoDialog, ExportDialog
except ImportError:
    # If common_dialogs doesn't exist or has issues, create minimal aliases
    # This ensures the app doesn't crash
    ConfirmDialog = None
    ErrorDialog = None
    InfoDialog = None
    ExportDialog = None

__all__ = [
    'BaseDialog',
    'DialogType',
    'MessageDialog',
    'ConfirmationDialog',
    'PasswordDialog',
    'LanguageDialog',
    'LogoutDialog',
    'SecurityDialog',
    # Legacy exports (for backward compatibility)
    'ConfirmDialog',
    'ErrorDialog',
    'InfoDialog',
    'ExportDialog'
]
