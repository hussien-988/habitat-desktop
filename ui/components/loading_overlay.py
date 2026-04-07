# -*- coding: utf-8 -*-
"""
Loading overlay component with progress bar and branded theme.
"""
from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QPainter, QColor, QPaintEvent, QLinearGradient

from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction
from ui.design_system import ScreenScale

_CONTAINER_STYLE = """
    QWidget#_overlay_container {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(15, 31, 61, 240),
            stop:1 rgba(18, 44, 73, 240));
        border-radius: 12px;
        border: 1px solid rgba(56, 144, 223, 0.15);
    }
"""

_PROGRESS_STYLE = """
    QProgressBar {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(56, 144, 223, 0.2);
        border-radius: 4px;
        min-height: 6px;
        max-height: 6px;
        text-align: center;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #3890DF, stop:1 #64B4F0);
        border-radius: 3px;
    }
"""


class LoadingOverlay(QWidget):
    """Semi-transparent loading overlay with progress indicator."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        if parent:
            parent.installEventFilter(self)
        self.hide()

    def _setup_ui(self) -> None:
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        container = QWidget()
        container.setObjectName("_overlay_container")
        container.setFixedSize(ScreenScale.w(340), ScreenScale.h(110))
        container.setStyleSheet(_CONTAINER_STYLE)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(28, 22, 28, 22)
        container_layout.setSpacing(14)

        self.message_label = QLabel(tr("component.loading.default"))
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setFont(
            create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD)
        )
        self.message_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.9); background: transparent;"
        )
        self.message_label.setLayoutDirection(get_layout_direction())
        container_layout.addWidget(self.message_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setStyleSheet(_PROGRESS_STYLE)
        container_layout.addWidget(self.progress_bar)

        layout.addWidget(container)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor(10, 22, 40, 180))
        grad.setColorAt(1.0, QColor(15, 30, 55, 180))
        painter.fillRect(self.rect(), grad)
        super().paintEvent(event)

    def show_loading(self, message: str = None, progress: int = -1) -> None:
        self.message_label.setText(message or tr("component.loading.default"))
        self.message_label.setLayoutDirection(get_layout_direction())

        if progress < 0:
            self.progress_bar.setMaximum(0)
        else:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(progress)

        parent_widget = self.parent()
        if parent_widget and isinstance(parent_widget, QWidget):
            self.setGeometry(parent_widget.rect())

        self.show()
        self.raise_()

    def update_progress(self, progress: int, message: Optional[str] = None) -> None:
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(progress)
        if message:
            self.message_label.setText(message)

    def hide_loading(self) -> None:
        self.hide()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.parent() and event.type() == QEvent.Resize:
            if self.isVisible():
                self.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

    @classmethod
    def create(cls, parent: Optional[QWidget]) -> "LoadingOverlay":
        overlay = cls(parent)
        return overlay
