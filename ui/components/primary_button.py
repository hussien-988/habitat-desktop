# -*- coding: utf-8 -*-
"""Primary Button Component - زر أساسي قابل لإعادة الاستخدام."""

from PyQt5.QtWidgets import QPushButton, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve

from ..design_system import ButtonDimensions
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from .icon import Icon


class PrimaryButton(QPushButton):
    """Reusable primary button with icon support and loading state."""

    def __init__(self, text: str = "", icon_name: str = None, parent=None):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self._original_text = text
        self._is_loading = False
        self._spinner_frame = 0
        self._spinner_timer = None
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("PrimaryButton")
        self.setFixedHeight(ButtonDimensions.PRIMARY_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        if self.icon_name:
            self._load_icon()

        btn_font = create_font(
            size=11,
            weight=FontManager.WEIGHT_SEMIBOLD,
            letter_spacing=0,
        )
        self.setFont(btn_font)
        self.setStyleSheet(StyleManager.button_primary())

    def _load_icon(self):
        q_icon = Icon.load_qicon(self.icon_name)
        if q_icon:
            self.setIcon(q_icon)
            self.setIconSize(QSize(20, 20))

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

    def mousePressEvent(self, event):
        if not self._is_loading:
            self._animate_press(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._is_loading:
            self._animate_press(False)
        super().mouseReleaseEvent(event)

    def _animate_press(self, pressed):
        from PyQt5.QtGui import QTransform
        scale = 0.97 if pressed else 1.0
        t = QTransform()
        t.scale(scale, scale)
        self.setGraphicsEffect(None)
        if pressed:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.9)
            self.setGraphicsEffect(effect)
