# -*- coding: utf-8 -*-
"""
BaseDialog - Minimal base class for standardized dialog initialization.
Provides only structural foundation without any styling or UI components.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from repositories.database import Database
    from utils.i18n import I18n


class BaseDialog(QDialog):
    """
    Minimal base dialog with standardized initialization.

    Provides:
    - Window title setup via i18n
    - Minimum size configuration
    - Standard main layout container
    - i18n helper method

    Does NOT provide:
    - Styling/stylesheets
    - Buttons (OK/Cancel)
    - Any UI components
    """

    def __init__(self,
                 db: 'Database',
                 i18n: 'I18n',
                 title_key: str,
                 parent: Optional[QDialog] = None,
                 size: Tuple[int, int] = (700, 500)):
        """
        Initialize base dialog.

        Args:
            db: Database instance
            i18n: Internationalization instance
            title_key: Translation key for window title
            parent: Parent widget
            size: Minimum size as (width, height) tuple
        """
        super().__init__(parent)
        self.db = db
        self.i18n = i18n

        # Set window title via i18n
        if title_key:
            self.setWindowTitle(i18n.t(title_key))

        # Set minimum size only (no styling)
        self.setMinimumSize(*size)

        # Create main layout container
        self.main_layout = QVBoxLayout(self)

    def t(self, key: str) -> str:
        """
        Helper method for translation.

        Args:
            key: Translation key

        Returns:
            Translated string
        """
        return self.i18n.t(key)
