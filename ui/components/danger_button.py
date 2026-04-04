# -*- coding: utf-8 -*-
"""
Danger Button Component - زر خطر قابل لإعادة الاستخدام
Reusable danger button component for destructive actions.

"""

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import Qt, QTimer

from ..style_manager import StyleManager
from ..font_utils import create_font, FontManager


class DangerButton(QPushButton):
    """Reusable danger button for destructive actions with loading state."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._original_text = text
        self._is_loading = False
        self._spinner_frame = 0
        self._spinner_timer = None
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("DangerButton")
        self.setCursor(Qt.PointingHandCursor)

        btn_font = create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_MEDIUM,
            letter_spacing=0
        )
        self.setFont(btn_font)
        self.setStyleSheet(StyleManager.button_danger())

    def set_loading(self, loading: bool, text: str = ""):
        self._is_loading = loading
        if loading:
            self._original_text = self.text()
            self.setEnabled(False)
            self.setCursor(Qt.WaitCursor)
            self._spinner_frame = 0
            self._spinner_timer = QTimer(self)
            self._spinner_timer.setInterval(120)
            self._spinner_timer.timeout.connect(self._animate_spinner)
            self._loading_text = text or self._original_text
            self._spinner_timer.start()
            self._animate_spinner()
        else:
            if self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None
            self.setText(self._original_text)
            self.setEnabled(True)
            self.setCursor(Qt.PointingHandCursor)

    _SPINNER_CHARS = ["\u25DC", "\u25DD", "\u25DE", "\u25DF"]

    def _animate_spinner(self):
        char = self._SPINNER_CHARS[self._spinner_frame % 4]
        self.setText(f"{char}  {self._loading_text}")
        self._spinner_frame += 1
