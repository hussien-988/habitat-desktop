# -*- coding: utf-8 -*-
"""
Dialog Components Package - نظام الحوارات الموحد
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
