# -*- coding: utf-8 -*-
"""Toast notification component."""

from PyQt5.QtWidgets import (
    QFrame, QLabel, QWidget, QHBoxLayout,
    QGraphicsOpacityEffect, QPushButton
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt5.QtGui import QColor

from ui.design_system import Colors, DialogColors, BorderRadius
from ui.font_utils import create_font, FontManager
from services.translation_manager import get_layout_direction


class Toast(QFrame):
    """Toast notification popup matching the app design system."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    _TYPE_CONFIG = {
        "success": {
            "accent": Colors.SUCCESS,
            "icon": "\u2713",
            "icon_bg": DialogColors.SUCCESS_BG,
            "icon_color": DialogColors.SUCCESS_ICON,
        },
        "error": {
            "accent": Colors.ERROR,
            "icon": "\u2717",
            "icon_bg": DialogColors.ERROR_BG,
            "icon_color": DialogColors.ERROR_ICON,
        },
        "warning": {
            "accent": Colors.WARNING,
            "icon": "\u26A0",
            "icon_bg": DialogColors.WARNING_BG,
            "icon_color": DialogColors.WARNING_ICON,
        },
        "info": {
            "accent": Colors.INFO,
            "icon": "\u2139",
            "icon_bg": DialogColors.INFO_BG,
            "icon_color": DialogColors.INFO_ICON,
        },
    }

    _SEVERITY_DURATION = {
        "success": 4000,
        "error": 8000,
        "warning": 6000,
        "info": 4000,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toast-notification")
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._action_callback = None
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setMinimumWidth(360)
        self.setMaximumWidth(520)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(32, 32)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setFont(
            create_font(size=14, weight=FontManager.WEIGHT_BOLD)
        )
        layout.addWidget(self._icon_lbl)

        self._msg_lbl = QLabel()
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setAlignment(Qt.AlignVCenter)
        self._msg_lbl.setFont(
            create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_MEDIUM)
        )
        layout.addWidget(self._msg_lbl, 1)

        self._action_btn = QPushButton()
        self._action_btn.setVisible(False)
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.setFont(
            create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD)
        )
        self._action_btn.clicked.connect(self._on_action)
        layout.addWidget(self._action_btn)

        self._close_btn = QPushButton("\u00D7")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-radius: 12px;
            }}
            QPushButton:hover {{ background: rgba(0,0,0,0.06); }}
        """)
        self._close_btn.clicked.connect(self._fade_out)
        layout.addWidget(self._close_btn)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

        self.hide()

    def show_message(self, message: str, toast_type: str = INFO,
                     duration: int = None, action_text: str = "",
                     action_callback=None):
        self._hide_timer.stop()

        if toast_type in (self.ERROR, self.WARNING):
            from services.error_mapper import sanitize_user_message
            message = sanitize_user_message(message)

        if duration is None:
            duration = self._SEVERITY_DURATION.get(toast_type, 4000)

        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        self.setProperty("type", toast_type)
        config = self._TYPE_CONFIG.get(toast_type, self._TYPE_CONFIG[self.INFO])
        accent = config["accent"]

        border_side = "right" if direction == Qt.RightToLeft else "left"
        self.setStyleSheet(f"""
            background-color: #FFFFFF;
            border: 1px solid {Colors.BORDER_DEFAULT};
            border-{border_side}: 4px solid {accent};
            border-radius: {BorderRadius.LG}px;
        """)

        self._icon_lbl.setText(config["icon"])
        self._icon_lbl.setStyleSheet(f"""
            background-color: {config["icon_bg"]};
            color: {config["icon_color"]};
            border-radius: 16px;
            border: none;
        """)

        self._msg_lbl.setText(message)
        self._msg_lbl.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)

        if action_text and action_callback:
            self._action_callback = action_callback
            self._action_btn.setText(action_text)
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {accent};
                    border: none;
                    padding: 2px 6px;
                }}
                QPushButton:hover {{ text-decoration: underline; }}
            """)
            self._action_btn.setVisible(True)
        else:
            self._action_btn.setVisible(False)
            self._action_callback = None

        if self.parent():
            parent_rect = self.parent().rect()
            self.adjustSize()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 60
            self.move(x, y)

        self.show()
        self.raise_()

        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.start()

        self._hide_timer.start(duration)

    def _on_action(self):
        if self._action_callback:
            self._action_callback()
        self._fade_out()

    def _fade_out(self):
        """Fade out and hide."""
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.finished.connect(self.hide)
        self.fade_out.start()

    @staticmethod
    def show_toast(parent: QWidget, message: str, toast_type: str = "info", duration: int = 3000):
        """
        Convenience method to show a toast on a widget.

        Args:
            parent: Parent widget
            message: Message text
            toast_type: Type (success, error, warning, info)
            duration: Display duration in milliseconds
        """
        toast = parent.findChild(Toast, "toast-notification")
        if not toast:
            toast = Toast(parent)
        toast.show_message(message, toast_type, duration)
        return toast
