# -*- coding: utf-8 -*-
"""
Dialog Components Package

Unified dialog system for the application following Figma design specifications.

This package provides:
- BaseDialog: Core dialog with overlay and consistent styling
- MessageDialog: Pre-configured dialogs for common use cases (success, error, warning, info, question)
- DialogType: Constants for dialog types

BACKWARD COMPATIBILITY:
- ConfirmDialog, ErrorDialog, InfoDialog: Legacy dialogs (deprecated, use MessageDialog instead)

Usage:
    from ui.components.dialogs import MessageDialog

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
"""

from .base_dialog import BaseDialog, DialogType
from .message_dialog import MessageDialog

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
    # Legacy exports (for backward compatibility)
    'ConfirmDialog',
    'ErrorDialog',
    'InfoDialog',
    'ExportDialog'
]
