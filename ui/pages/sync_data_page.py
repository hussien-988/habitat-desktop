# -*- coding: utf-8 -*-
"""
Sync & Data Page — صفحة المزامنة والبيانات
Displays sync log history from the local database.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.components.icon import Icon
from ui.design_system import Colors, PageDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class SyncDataPage(QWidget):
    """Page displaying sync log history."""

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._rows_container = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())
        self.setLayoutDirection(Qt.RightToLeft)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)

        # Header with title + breadcrumb
        header = self._create_header()
        main_layout.addWidget(header)

        # Scroll area for sync card
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        # Sync card container
        self._card = self._create_sync_card()
        scroll_layout.addWidget(self._card)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Title
        title = QLabel("المزامنة والبيانات")
        title.setFont(create_font(
            size=FontManager.SIZE_TITLE,
            weight=QFont.Bold,
            letter_spacing=0
        ))
        title.setStyleSheet(StyleManager.label_title())
        layout.addWidget(title)

        # Breadcrumb
        breadcrumb_layout = QHBoxLayout()
        breadcrumb_layout.setSpacing(8)
        breadcrumb_layout.setContentsMargins(0, 0, 0, 0)

        subtitle_font = create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal,
            letter_spacing=0
        )
        style = f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;"

        part1 = QLabel("المطالبات المكتملة")
        part1.setFont(subtitle_font)
        part1.setStyleSheet(style)
        breadcrumb_layout.addWidget(part1)

        dot = QLabel("•")
        dot.setFont(subtitle_font)
        dot.setStyleSheet(style)
        breadcrumb_layout.addWidget(dot)

        part2 = QLabel("المزامنة والبيانات")
        part2.setFont(subtitle_font)
        part2.setStyleSheet(style)
        breadcrumb_layout.addWidget(part2)

        breadcrumb_layout.addStretch()
        layout.addLayout(breadcrumb_layout)

        return header

    def _create_sync_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("syncCard")
        card.setStyleSheet("""
            QFrame#syncCard {
                background-color: white;
                border-radius: 8px;
            }
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Container for dynamic rows
        self._rows_container = QVBoxLayout()
        self._rows_container.setSpacing(8)
        layout.addLayout(self._rows_container)

        # Empty state label (hidden when rows exist)
        self._empty_label = QLabel("لا توجد سجلات مزامنة")
        self._empty_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal
        ))
        self._empty_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setMinimumHeight(100)
        layout.addWidget(self._empty_label)

        return card

    def _create_sync_row(self, device_id: str, case_count: int, sync_date: str) -> QFrame:
        row = QFrame()
        row.setFixedHeight(48)
        row.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #D6DBE9;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Sync icon
        icon_label = QLabel()
        icon_label.setFixedSize(18, 18)
        icon_label.setAlignment(Qt.AlignCenter)
        pixmap = Icon.load_pixmap("fluent", size=18)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        # Sync description text
        text = f"تمت مزامنة {case_count} حالة  من الجهاز ID {device_id}"
        text_label = QLabel(text)
        text_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal
        ))
        text_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(text_label)

        layout.addStretch()

        # Date
        date_label = QLabel(sync_date or "")
        date_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal
        ))
        date_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(date_label)

        return row

    def _clear_rows(self):
        if self._rows_container:
            while self._rows_container.count():
                item = self._rows_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def _get_mock_data(self):
        """Mock data for development/testing."""
        return [
            ("12345", "synced 12 cases", "12", "2024-12-01", "success"),
            ("12345", "synced 12 cases", "12", "2024-12-01", "success"),
            ("12345", "synced 12 cases", "12", "2024-12-01", "success"),
        ]

    def _load_sync_log(self):
        """Load sync log from local database."""
        if not self.db:
            return self._get_mock_data()

        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT device_id, action, details, sync_date, status
                FROM sync_log
                ORDER BY sync_date DESC
            """)
            rows = cursor.fetchall()
            if not rows:
                return self._get_mock_data()
            return rows
        except Exception as e:
            logger.warning(f"Failed to load sync log: {e}")
            return self._get_mock_data()

    def _parse_case_count(self, action: str, details: str) -> int:
        """Extract case count from action/details fields."""
        import re
        for text in [details or "", action or ""]:
            match = re.search(r'(\d+)', text)
            if match:
                return int(match.group(1))
        return 0

    def refresh(self, data=None):
        """Refresh sync log display."""
        self._clear_rows()

        rows = self._load_sync_log()

        if rows:
            self._empty_label.hide()
            for row in rows:
                device_id = row[0] or "---"
                action = row[1] or ""
                details = row[2] or ""
                sync_date = row[3] or ""
                case_count = self._parse_case_count(action, details)

                row_widget = self._create_sync_row(device_id, case_count, sync_date)
                self._rows_container.addWidget(row_widget)
        else:
            self._empty_label.show()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
