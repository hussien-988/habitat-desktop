# -*- coding: utf-8 -*-
"""Slide-in side panel replacing modal QDialogs.

Usage:
    panel = SlidePanel(parent, title="Add Person", width=520)
    panel.set_content(my_form_widget)
    panel.closed.connect(on_panel_closed)
    panel.open()
"""

import math
import time

from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, QRect,
    pyqtSignal, pyqtProperty, QTimer, QParallelAnimationGroup,
)
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QPen, QFont, QCursor,
)

from ui.design_system import Colors, Spacing, AnimationTimings, BorderRadius
from ui.font_utils import create_font, FontManager
from services.translation_manager import get_layout_direction


class _PanelOverlay(QWidget):
    """Semi-transparent backdrop behind the panel."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def _get_opacity(self):
        return self._opacity

    def _set_opacity(self, val):
        self._opacity = val
        self.update()

    opacity_val = pyqtProperty(float, _get_opacity, _set_opacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(10, 22, 40)
        color.setAlphaF(min(0.55 * self._opacity, 0.55))
        painter.fillRect(self.rect(), color)
        painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit()


class SlidePanel(QWidget):
    """Side-sliding panel that replaces modal QDialogs.

    Opens from the right edge (or left edge in RTL) with a frosted-glass
    header bar and scrollable content area. Matches the app's dark-navy
    cartographic aesthetic.

    Signals:
        closed: Emitted when panel is closed (cancel or backdrop click)
        submitted: Emitted when the panel's submit action fires
    """

    closed = pyqtSignal()
    submitted = pyqtSignal()

    _HEADER_HEIGHT = 56
    _ANIM_DURATION = 280
    _PANEL_SHADOW_BLUR = 40

    def __init__(self, parent=None, title: str = "", width: int = 520):
        super().__init__(parent)
        self._title_text = title
        self._panel_width = min(width, 640)
        self._is_open = False
        self._is_animating = False
        self._content_widget = None

        self._anim_group = None
        self._overlay = _PanelOverlay(self)
        self._overlay.clicked.connect(self.close_panel)

        self._panel = QFrame(self)
        self._panel.setObjectName("SlidePanel")

        self._build_panel()
        self.hide()

    def _build_panel(self):
        """Build the panel structure: header + scrollable content."""
        self._panel.setStyleSheet("""
            QFrame#SlidePanel {
                background-color: #FFFFFF;
                border: none;
            }
        """)

        panel_shadow = QGraphicsDropShadowEffect(self._panel)
        panel_shadow.setBlurRadius(self._PANEL_SHADOW_BLUR)
        panel_shadow.setOffset(-6, 0)
        panel_shadow.setColor(QColor(10, 22, 40, 80))
        self._panel.setGraphicsEffect(panel_shadow)

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar (dark navy, matching app navbar)
        self._header = QFrame()
        self._header.setFixedHeight(self._HEADER_HEIGHT)
        self._header.setObjectName("SlidePanelHeader")

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(12)

        # Close button
        self._close_btn = QPushButton("\u2715")
        self._close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(200, 220, 255, 0.85);
                border: 1px solid rgba(56, 144, 223, 0.15);
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: rgba(56, 144, 223, 0.35);
                color: white;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.06);
            }
        """)
        self._close_btn.clicked.connect(self.close_panel)
        header_layout.addWidget(self._close_btn)

        # Title
        self._title_label = QLabel(self._title_text)
        self._title_label.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
        self._title_label.setStyleSheet(
            "color: white; background: transparent; border: none;"
        )
        header_layout.addWidget(self._title_label, 1)

        layout.addWidget(self._header)

        # Accent line below header
        accent = QFrame()
        accent.setFixedHeight(2)
        accent.setObjectName("SlidePanelAccent")
        layout.addWidget(accent)

        # Scrollable content area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { border: none; background: #FAFBFD; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(56, 144, 223, 0.25);
                border-radius: 3px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(56, 144, 223, 0.45);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self._content_container = QWidget()
        self._content_container.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_container)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        self._scroll.setWidget(self._content_container)
        layout.addWidget(self._scroll, 1)

        self._apply_header_style()

    def _apply_header_style(self):
        """Apply the dark navy cartographic header style."""
        self._header.setStyleSheet("""
            QFrame#SlidePanelHeader {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0E2035, stop:0.5 #122C49, stop:1 #152F4E);
                border: none;
            }
        """)

        # Accent line: gradient blue glow
        accent = self._panel.findChild(QFrame, "SlidePanelAccent")
        if accent:
            accent.setStyleSheet("""
                QFrame#SlidePanelAccent {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(56, 144, 223, 0),
                        stop:0.2 rgba(56, 144, 223, 130),
                        stop:0.5 rgba(91, 168, 240, 200),
                        stop:0.8 rgba(56, 144, 223, 130),
                        stop:1 rgba(56, 144, 223, 0));
                }
            """)

    def set_title(self, title: str):
        """Update the panel title."""
        self._title_text = title
        self._title_label.setText(title)

    def set_content(self, widget: QWidget):
        """Set the main content widget inside the scrollable area."""
        # Remove existing content
        if self._content_widget:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)

        self._content_widget = widget
        self._content_layout.addWidget(widget)

    def set_panel_width(self, width: int):
        """Update panel width (before opening)."""
        self._panel_width = min(width, 640)

    def is_open(self) -> bool:
        return self._is_open

    def open(self):
        """Open the panel with slide-in animation."""
        if self._is_open or self._is_animating:
            return

        self._is_animating = True

        # Set layout direction
        self.setLayoutDirection(get_layout_direction())
        self._panel.setLayoutDirection(get_layout_direction())

        # Size to parent
        if self.parent():
            self.resize(self.parent().size())
        self._overlay.resize(self.size())

        pw = min(self._panel_width, self.width() - 24)
        ph = self.height()
        self._panel.setFixedSize(pw, ph)

        is_rtl = get_layout_direction() == Qt.RightToLeft

        # Starting position: off-screen
        if is_rtl:
            start_x = -pw
            end_x = 0
        else:
            start_x = self.width()
            end_x = self.width() - pw

        self._panel.move(start_x, 0)
        self._overlay._set_opacity(0.0)

        self.show()
        self.raise_()

        # Animate overlay fade + panel slide
        self._anim_group = QParallelAnimationGroup(self)

        overlay_anim = QPropertyAnimation(self._overlay, b"opacity_val", self)
        overlay_anim.setDuration(self._ANIM_DURATION)
        overlay_anim.setStartValue(0.0)
        overlay_anim.setEndValue(1.0)
        overlay_anim.setEasingCurve(QEasingCurve.OutCubic)

        panel_anim = QPropertyAnimation(self._panel, b"pos", self)
        panel_anim.setDuration(self._ANIM_DURATION)
        panel_anim.setStartValue(QPoint(start_x, 0))
        panel_anim.setEndValue(QPoint(end_x, 0))
        panel_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_group.addAnimation(overlay_anim)
        self._anim_group.addAnimation(panel_anim)

        self._anim_group.finished.connect(self._on_open_finished)
        self._anim_group.start()

    def _on_open_finished(self):
        self._is_open = True
        self._is_animating = False

    def close_panel(self):
        """Close the panel with slide-out animation."""
        if not self._is_open or self._is_animating:
            return

        self._is_animating = True

        is_rtl = get_layout_direction() == Qt.RightToLeft
        pw = self._panel.width()

        if is_rtl:
            end_x = -pw
        else:
            end_x = self.width()

        self._anim_group = QParallelAnimationGroup(self)

        overlay_anim = QPropertyAnimation(self._overlay, b"opacity_val", self)
        overlay_anim.setDuration(self._ANIM_DURATION - 50)
        overlay_anim.setStartValue(self._overlay._get_opacity())
        overlay_anim.setEndValue(0.0)
        overlay_anim.setEasingCurve(QEasingCurve.InCubic)

        panel_anim = QPropertyAnimation(self._panel, b"pos", self)
        panel_anim.setDuration(self._ANIM_DURATION)
        panel_anim.setStartValue(self._panel.pos())
        panel_anim.setEndValue(QPoint(end_x, 0))
        panel_anim.setEasingCurve(QEasingCurve.InCubic)

        self._anim_group.addAnimation(overlay_anim)
        self._anim_group.addAnimation(panel_anim)

        self._anim_group.finished.connect(self._on_close_finished)
        self._anim_group.start()

    def _on_close_finished(self):
        self._is_open = False
        self._is_animating = False
        self.hide()
        self.closed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.resize(self.size())
        if self._is_open and not self._is_animating:
            pw = min(self._panel_width, self.width() - 24)
            ph = self.height()
            self._panel.setFixedSize(pw, ph)
            is_rtl = get_layout_direction() == Qt.RightToLeft
            if is_rtl:
                self._panel.move(0, 0)
            else:
                self._panel.move(self.width() - pw, 0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._is_open:
            self.close_panel()
        else:
            super().keyPressEvent(event)
