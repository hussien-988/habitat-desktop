# -*- coding: utf-8 -*-
"""Slide-down notification bar replacing all QMessageBox informational dialogs."""

from PyQt5.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QPushButton, QWidget,
    QGraphicsOpacityEffect, QVBoxLayout, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
)
from PyQt5.QtGui import QColor

from ui.design_system import (
    NotificationDimensions as ND, Colors, BorderRadius,
    Typography, AnimationTimings
)
from ui.font_utils import create_font, FontManager
from services.translation_manager import get_layout_direction


class NotificationBar(QFrame):
    """Slide-down notification bar anchored to top of content area."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    action_clicked = pyqtSignal()
    dismissed = pyqtSignal()

    _ICONS = {
        SUCCESS: "\u2713",
        ERROR: "\u2717",
        WARNING: "\u26A0",
        INFO: "\u2139",
    }

    _DURATIONS = {
        SUCCESS: ND.AUTO_DISMISS_SUCCESS,
        ERROR: ND.AUTO_DISMISS_ERROR,
        WARNING: ND.AUTO_DISMISS_WARNING,
        INFO: ND.AUTO_DISMISS_INFO,
    }

    _BG = {
        SUCCESS: ND.BG_SUCCESS,
        ERROR: ND.BG_ERROR,
        WARNING: ND.BG_WARNING,
        INFO: ND.BG_INFO,
    }

    _BORDER = {
        SUCCESS: ND.BORDER_SUCCESS,
        ERROR: ND.BORDER_ERROR,
        WARNING: ND.BORDER_WARNING,
        INFO: ND.BORDER_INFO,
    }

    _ACCENT = {
        SUCCESS: ND.ACCENT_SUCCESS,
        ERROR: ND.ACCENT_ERROR,
        WARNING: ND.ACCENT_WARNING,
        INFO: ND.ACCENT_INFO,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notification_bar")
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.dismiss)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(30)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._total_ms = 0
        self._elapsed_ms = 0
        self._current_anim = None
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setMaximumWidth(ND.MAX_WIDTH)
        self.setMinimumHeight(ND.HEIGHT)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QHBoxLayout()
        content.setContentsMargins(ND.PADDING_H, ND.PADDING_V,
                                   ND.PADDING_H, ND.PADDING_V)
        content.setSpacing(12)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(ND.ICON_SIZE + 12, ND.ICON_SIZE + 12)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setFont(
            create_font(size=12, weight=FontManager.WEIGHT_BOLD)
        )
        content.addWidget(self._icon_lbl)

        self._msg_lbl = QLabel()
        self._msg_lbl.setWordWrap(True)
        self._msg_lbl.setAlignment(Qt.AlignVCenter)
        self._msg_lbl.setFont(
            create_font(size=FontManager.SIZE_BODY,
                        weight=FontManager.WEIGHT_MEDIUM)
        )
        content.addWidget(self._msg_lbl, 1)

        self._action_btn = QPushButton()
        self._action_btn.setVisible(False)
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.clicked.connect(self.action_clicked.emit)
        self._action_btn.setFont(
            create_font(size=FontManager.SIZE_BODY,
                        weight=FontManager.WEIGHT_SEMIBOLD)
        )
        content.addWidget(self._action_btn)

        self._close_btn = QPushButton("\u00D7")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.dismiss)
        self._close_btn.setFont(
            create_font(size=14, weight=FontManager.WEIGHT_BOLD)
        )
        content.addWidget(self._close_btn)

        outer.addLayout(content)

        self._progress = QFrame()
        self._progress.setFixedHeight(ND.PROGRESS_HEIGHT)
        self._progress.setStyleSheet("background: transparent;")
        outer.addWidget(self._progress)

    def show_message(self, message: str, level: str = INFO,
                     action_text: str = "", duration_override: int = None):
        self._auto_timer.stop()
        self._progress_timer.stop()

        if level in (self.ERROR, self.WARNING):
            from services.error_mapper import sanitize_user_message
            message = sanitize_user_message(message)

        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        bg = self._BG.get(level, self._BG[self.INFO])
        border = self._BORDER.get(level, self._BORDER[self.INFO])
        accent = self._ACCENT.get(level, self._ACCENT[self.INFO])

        self.setStyleSheet(f"""
            QFrame#notification_bar {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: {ND.BORDER_RADIUS}px;
            }}
        """)

        self._icon_lbl.setText(self._ICONS.get(level, self._ICONS[self.INFO]))
        self._icon_lbl.setStyleSheet(f"""
            background-color: {accent};
            color: white;
            border-radius: {(ND.ICON_SIZE + 12) // 2}px;
            border: none;
        """)

        self._msg_lbl.setText(message)
        self._msg_lbl.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            background: transparent;
            border: none;
        """)

        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: rgba(0, 0, 0, 0.06);
            }}
        """)

        if action_text:
            self._action_btn.setText(action_text)
            self._action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {accent};
                    border: none;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    text-decoration: underline;
                }}
            """)
            self._action_btn.setVisible(True)
        else:
            self._action_btn.setVisible(False)

        duration = duration_override if duration_override is not None \
            else self._DURATIONS.get(level, ND.AUTO_DISMISS_INFO)

        if duration > 0:
            self._progress.setStyleSheet(f"background: {accent};")
            self._progress.setFixedWidth(self.width() or ND.MAX_WIDTH)
            self._total_ms = duration
            self._elapsed_ms = 0
            self._progress_timer.start()
            self._auto_timer.start(duration)
        else:
            self._progress.setStyleSheet("background: transparent;")
            self._progress.setFixedWidth(0)

        self._position_in_parent()
        self._animate_in()

    def _position_in_parent(self):
        if not self.parent():
            return
        p = self.parent()
        pw = p.width()
        if pw <= 0:
            QTimer.singleShot(0, self._position_in_parent)
            return
        self.adjustSize()
        w = max(300, min(self.sizeHint().width(), ND.MAX_WIDTH))
        self.setFixedWidth(w)
        x = (pw - w) // 2
        self.move(x, 12)
        self.raise_()

    def _animate_in(self):
        self.show()
        self.raise_()
        effect = self.findChild(QGraphicsOpacityEffect)
        if not effect:
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(AnimationTimings.SLIDE_DOWN)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._current_anim = anim
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def dismiss(self):
        self._auto_timer.stop()
        self._progress_timer.stop()
        effect = self.findChild(QGraphicsOpacityEffect)
        if not effect:
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(AnimationTimings.FADE_OUT)
        anim.setStartValue(effect.opacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self._on_dismissed)
        self._current_anim = anim
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def _on_dismissed(self):
        self.hide()
        self.dismissed.emit()

    def _tick_progress(self):
        self._elapsed_ms += 30
        if self._total_ms > 0:
            ratio = max(0.0, 1.0 - self._elapsed_ms / self._total_ms)
            total_w = self.width() - 2
            self._progress.setFixedWidth(max(0, int(total_w * ratio)))

    @staticmethod
    def notify(parent: QWidget, message: str, level: str = "info",
               action_text: str = "", duration: int = None):
        bar = parent.findChild(NotificationBar, "notification_bar")
        if not bar:
            bar = NotificationBar(parent)
        bar.show_message(message, level, action_text, duration)
        return bar
