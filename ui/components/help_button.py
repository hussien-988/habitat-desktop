# -*- coding: utf-8 -*-
"""HelpButton component."""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt

from ui.design_system import ScreenScale, DialogColors
from services.translation_manager import tr


class HelpButton(QPushButton):

    def __init__(self, page_id: str, variant: str = "light", parent=None):
        super().__init__("?", parent)
        self._page_id = page_id
        self._variant = variant

        size = ScreenScale.w(26)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("help.button.tooltip"))
        self.setStyleSheet(self._style(variant, size // 2))
        self.clicked.connect(self._open)

    def _open(self):
        from ui.components.dialogs.help_dialog import HelpDialog
        dlg = HelpDialog(self.window(), self._page_id)
        dlg.show()

    @staticmethod
    def _style(variant: str, radius: int) -> str:
        if variant == "dark":
            return f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 0.14);
                    color: #E6F2FF;
                    border: 1px solid rgba(139, 172, 200, 0.35);
                    border-radius: {radius}px;
                    font-size: 12pt;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{
                    background-color: rgba(255, 255, 255, 0.22);
                }}
                QPushButton:pressed {{
                    background-color: rgba(255, 255, 255, 0.10);
                }}
            """
        return f"""
            QPushButton {{
                background-color: {DialogColors.INFO_BG};
                color: {DialogColors.INFO_ICON};
                border: none;
                border-radius: {radius}px;
                font-size: 12pt;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: #CFE4F7;
            }}
            QPushButton:pressed {{
                background-color: #B5D4F0;
            }}
        """
