# -*- coding: utf-8 -*-
"""
Loading overlay component.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor


class LoadingOverlay(QWidget):
    """Semi-transparent loading overlay with progress indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.hide()

    def _setup_ui(self):
        """Setup overlay UI."""
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Container for centering
        container = QWidget()
        container.setFixedSize(300, 120)
        container.setStyleSheet("""
            background-color: white;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(16)

        # Message label
        self.message_label = QLabel("Loading...")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("font-size: 12pt; color: #333;")
        container_layout.addWidget(self.message_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimumHeight(8)
        container_layout.addWidget(self.progress_bar)

        layout.addWidget(container)

    def paintEvent(self, event):
        """Paint semi-transparent background."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)

    def show_loading(self, message: str = "Loading...", progress: int = -1):
        """
        Show the loading overlay.

        Args:
            message: Message to display
            progress: Progress value (0-100), or -1 for indeterminate
        """
        self.message_label.setText(message)

        if progress < 0:
            self.progress_bar.setMaximum(0)  # Indeterminate
        else:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(progress)

        # Resize to parent
        if self.parent():
            self.setGeometry(self.parent().rect())

        self.show()
        self.raise_()

    def update_progress(self, progress: int, message: str = None):
        """
        Update progress and optionally message.

        Args:
            progress: Progress value (0-100)
            message: Optional new message
        """
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(progress)

        if message:
            self.message_label.setText(message)

    def hide_loading(self):
        """Hide the loading overlay."""
        self.hide()

    @classmethod
    def create(cls, parent: QWidget) -> "LoadingOverlay":
        """Create and return a loading overlay for a widget."""
        overlay = cls(parent)
        return overlay
