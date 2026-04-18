# -*- coding: utf-8 -*-
"""HelpDialog - per-page help viewer."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from ui.design_system import Colors, DialogColors, ScreenScale
from ui.font_utils import create_font
from services.translation_manager import tr, get_layout_direction
from services.help_renderer import render
from app.help_content import get_keys
from utils.logger import get_logger

logger = get_logger(__name__)


class HelpDialog(QWidget):

    closed = pyqtSignal()

    def __init__(self, parent: QWidget, page_id: str):
        super().__init__(parent)
        self._page_id = page_id

        self.setWindowFlags(
            Qt.Dialog |
            Qt.FramelessWindowHint |
            Qt.CustomizeWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowModality(Qt.ApplicationModal)
        self.setLayoutDirection(get_layout_direction())

        self._build_ui()
        self._center_on_parent()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("HelpCard")
        self._card.setFixedWidth(ScreenScale.w(520))
        self._card.setMaximumHeight(ScreenScale.h(620))
        self._card.setStyleSheet("""
            QFrame#HelpCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 60))
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(24, 24, 24, 20)
        card_layout.setSpacing(0)

        keys = get_keys(self._page_id)
        if keys is None:
            logger.warning(f"HelpDialog opened for page_id without content: {self._page_id}")
            title_text = tr("help.dialog.unavailable_title")
            desc_text = tr("help.dialog.unavailable_message")
            step_texts = []
        else:
            title_key, desc_key, step_keys = keys
            title_text = render(tr(title_key))
            desc_text = render(tr(desc_key))
            step_texts = [render(tr(k)) for k in step_keys]
            step_texts = [
                s for s, k in zip(step_texts, step_keys)
                if not s.startswith("help.")
            ]

        card_layout.addWidget(self._build_icon(), alignment=Qt.AlignCenter)
        card_layout.addSpacing(14)

        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setFont(create_font(size=16, weight=QFont.Bold))
        title_label.setStyleSheet("color: #1A1A1A; background: transparent;")
        card_layout.addWidget(title_label)
        card_layout.addSpacing(8)

        desc_label = QLabel(desc_text)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setFont(create_font(size=11, weight=QFont.Light))
        desc_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent;"
        )
        card_layout.addWidget(desc_label)
        card_layout.addSpacing(18)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #EEF2F5; border: none;")
        card_layout.addWidget(separator)
        card_layout.addSpacing(14)

        if step_texts:
            steps_label = QLabel(tr("help.dialog.steps_label"))
            steps_label.setFont(create_font(size=11, weight=QFont.Bold))
            steps_label.setStyleSheet("color: #2C3E50; background: transparent;")
            card_layout.addWidget(steps_label)
            card_layout.addSpacing(8)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setStyleSheet("background: transparent;")

            steps_container = QWidget()
            steps_container.setStyleSheet("background: transparent;")
            steps_layout = QVBoxLayout(steps_container)
            steps_layout.setContentsMargins(0, 0, 0, 0)
            steps_layout.setSpacing(10)

            for i, step_text in enumerate(step_texts, start=1):
                steps_layout.addWidget(self._build_step_row(i, step_text))

            steps_layout.addStretch()
            scroll.setWidget(steps_container)
            card_layout.addWidget(scroll, 1)

        card_layout.addSpacing(18)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        got_it_btn = QPushButton(tr("help.dialog.got_it"))
        got_it_btn.setCursor(Qt.PointingHandCursor)
        got_it_btn.setFixedHeight(ScreenScale.h(44))
        got_it_btn.setMinimumWidth(ScreenScale.w(140))
        got_it_btn.setFont(create_font(size=10, weight=QFont.Light))
        got_it_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DialogColors.INFO_ICON};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{ background-color: #2A7BC9; }}
            QPushButton:pressed {{ background-color: {DialogColors.INFO_ICON}; }}
        """)
        got_it_btn.clicked.connect(self.close)
        buttons_row.addWidget(got_it_btn)
        buttons_row.addStretch()
        card_layout.addLayout(buttons_row)

        main_layout.addWidget(self._card, alignment=Qt.AlignCenter)

    def _build_icon(self) -> QWidget:
        size = ScreenScale.w(48)
        icon_widget = QWidget()
        icon_widget.setFixedSize(size, size)
        icon_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {DialogColors.INFO_BG};
                border-radius: {size // 2}px;
            }}
        """)
        layout = QVBoxLayout(icon_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        symbol = QLabel("?")
        symbol.setAlignment(Qt.AlignCenter)
        symbol.setStyleSheet(f"""
            color: {DialogColors.INFO_ICON};
            font-size: 24pt;
            font-weight: bold;
            background: transparent;
        """)
        layout.addWidget(symbol)
        return icon_widget

    def _build_step_row(self, number: int, text: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)

        badge_size = ScreenScale.w(26)
        badge = QLabel(str(number))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(badge_size, badge_size)
        badge.setFont(create_font(size=10, weight=QFont.Bold))
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {DialogColors.INFO_BG};
                color: {DialogColors.INFO_ICON};
                border-radius: {badge_size // 2}px;
            }}
        """)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setFont(create_font(size=11, weight=QFont.Normal))
        body.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        body.setAlignment(Qt.AlignTop | Qt.AlignLeading)

        row_layout.addWidget(badge, 0, Qt.AlignTop)
        row_layout.addWidget(body, 1)
        return row

    def _center_on_parent(self):
        parent = self.parent()
        if not parent:
            return
        target = parent.window() or parent
        self.adjustSize()
        parent_rect = target.geometry()
        cx = parent_rect.x() + (parent_rect.width() - self.width()) // 2
        cy = parent_rect.y() + (parent_rect.height() - self.height()) // 2
        self.move(cx, cy)

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_parent()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
