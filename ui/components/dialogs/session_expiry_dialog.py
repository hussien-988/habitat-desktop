# -*- coding: utf-8 -*-
"""
Session Expiry Dialog — تحذير انتهاء الجلسة

Shown shortly before the session ends: "the session will end in {n}
seconds, continue?" with [OK] to renew it and [Log out]. It counts down
until the owner closes it (renewed, logged out or timed out).
"""

from typing import Callable, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from services.translation_manager import get_layout_direction, tr
from ui.design_system import Colors, ScreenScale
from ui.font_utils import FontManager, create_font


class SessionExpiryDialog(QDialog):
    """Countdown warning with [OK] (continue the session) and [Log out]."""

    continue_requested = pyqtSignal()
    logout_requested = pyqtSignal()

    def __init__(self, seconds_remaining: Callable[[], Optional[int]], parent=None):
        super().__init__(parent)
        self._seconds_remaining = seconds_remaining

        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self.setMinimumWidth(ScreenScale.w(460))
        self._setup_ui()

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._update_message)
        self._countdown.start()
        self._update_message()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("sessionExpiryContainer")
        container.setStyleSheet("""
            QFrame#sessionExpiryContainer { background-color: #FFFFFF; border-radius: 24px; }
            QFrame#sessionExpiryContainer QLabel { background-color: transparent; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(tr("session.expiring_title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._message.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self._message)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()
        self._logout_btn = self._create_button(tr("dialog.logout.logout"), primary=False)
        self._logout_btn.clicked.connect(self.logout_requested.emit)
        self._ok_btn = self._create_button(tr("button.ok"), primary=True)
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self.continue_requested.emit)
        buttons.addWidget(self._ok_btn)
        buttons.addWidget(self._logout_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        outer.addWidget(container)

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(ScreenScale.w(150), ScreenScale.h(46))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=QFont.Medium))
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {Colors.PRIMARY_BLUE}; color: white;
                               border: none; border-radius: 8px; }}
                QPushButton:hover {{ background-color: #2D7BC9; }}
                QPushButton:disabled {{ background-color: #A9C9EC; }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background-color: white; color: #6B7280;
                              border: 1px solid #E5E7EB; border-radius: 8px; }
                QPushButton:hover { background-color: #F9FAFB; }
                QPushButton:disabled { color: #C0C8D0; }
            """)
        return btn

    def _update_message(self):
        seconds = self._seconds_remaining()
        self._message.setText(tr("session.expiring_prompt", seconds=max(1, seconds or 0)))

    def set_busy(self, busy: bool):
        """Disable the buttons while the session is being renewed."""
        self._ok_btn.setEnabled(not busy)
        self._logout_btn.setEnabled(not busy)

    def keyPressEvent(self, event):
        # The user must choose: Escape neither renews nor logs out
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)

    def done(self, result_code: int):
        self._countdown.stop()
        super().done(result_code)
