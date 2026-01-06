# -*- coding: utf-8 -*-
"""
Toast notification component.
"""

from PyQt5.QtWidgets import QLabel, QWidget, QHBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont


class Toast(QLabel):
    """Toast notification popup."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toast")
        self._setup_ui()

    def _setup_ui(self):
        """Setup toast UI."""
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)

        # Style
        self.setStyleSheet("""
            QLabel#toast {
                background-color: #333;
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 11pt;
            }
        """)

        # Opacity effect for fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

        self.hide()

    def show_message(self, message: str, toast_type: str = INFO, duration: int = 3000):
        """
        Show a toast message.

        Args:
            message: Message text
            toast_type: Type (success, error, warning, info)
            duration: Display duration in milliseconds
        """
        self.setText(message)
        self.setProperty("type", toast_type)

        # Update style based on type
        colors = {
            self.SUCCESS: "#28a745",
            self.ERROR: "#dc3545",
            self.WARNING: "#ffc107",
            self.INFO: "#17a2b8",
        }
        color = colors.get(toast_type, "#333")
        text_color = "#333" if toast_type == self.WARNING else "white"

        self.setStyleSheet(f"""
            QLabel#toast {{
                background-color: {color};
                color: {text_color};
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 11pt;
            }}
        """)

        # Position at bottom center of parent
        if self.parent():
            parent_rect = self.parent().rect()
            self.adjustSize()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 50
            self.move(x, y)

        # Show with fade in
        self.show()
        self.raise_()

        # Fade in animation
        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.start()

        # Auto hide timer
        QTimer.singleShot(duration, self._fade_out)

    def _fade_out(self):
        """Fade out and hide."""
        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.finished.connect(self.hide)
        self.fade_out.start()

    @classmethod
    def show(cls, parent: QWidget, message: str, toast_type: str = "info", duration: int = 3000):
        """
        Convenience method to show a toast on a widget.

        Args:
            parent: Parent widget
            message: Message text
            toast_type: Type (success, error, warning, info)
            duration: Display duration
        """
        # Find or create toast
        toast = parent.findChild(Toast, "toast-notification")
        if not toast:
            toast = Toast(parent)
            toast.setObjectName("toast-notification")

        toast.show_message(message, toast_type, duration)
        return toast
