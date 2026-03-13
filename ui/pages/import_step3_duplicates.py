# -*- coding: utf-8 -*-
"""
Import Wizard - Step 3: Duplicate Detection Results
UC-003: Import Pipeline

Displays detected duplicate entities from the staged package.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Entity type Arabic labels
_ENTITY_TYPE_AR = {
    'building': 'مبنى',
    'person': 'شخص',
    'property_unit': 'وحدة عقارية',
    'claim': 'مطالبة',
    'survey': 'مسح',
}


class ImportStep3Duplicates(QWidget):
    """Step 3: Duplicate detection results."""

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._duplicates = []
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Duplicates card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(16)

        # Title
        title = QLabel("التكرارات المكتشفة")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Count summary
        self._count_label = QLabel("عدد التكرارات: 0")
        self._count_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._count_label.setStyleSheet("color: #637381; background: transparent;")
        card_layout.addWidget(self._count_label)

        # Scrollable rows
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setMaximumHeight(420)

        self._rows_container = QWidget()
        self._rows_container.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)

        # Initial empty state
        self._empty_label = QLabel("لا توجد تكرارات")
        self._empty_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._empty_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._rows_layout.addWidget(self._empty_label)
        self._rows_layout.addStretch()

        self._scroll.setWidget(self._rows_container)
        card_layout.addWidget(self._scroll)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def load_duplicates(self, package_id: str):
        """Load duplicate detection results for the package."""
        logger.info(f"Loading duplicates for package {package_id}")

        # First run duplicate detection
        detect_result = self.import_controller.detect_duplicates(package_id)
        if not detect_result.success:
            logger.warning(f"Duplicate detection call failed: {detect_result.message}")

        # Get staged entities and filter for duplicates
        result = self.import_controller.get_staged_entities(package_id)

        if not result.success:
            self._show_error(result.message_ar or "فشل تحميل البيانات")
            return

        entities = result.data or []
        self._duplicates = [
            e for e in entities
            if e.get("isDuplicate") or e.get("duplicateScore", 0) > 0
        ]

        self._update_ui()

    def _update_ui(self):
        """Update UI with duplicate data."""
        self._clear_rows()

        count = len(self._duplicates)
        self._count_label.setText(f"عدد التكرارات: {count}")

        if count == 0:
            empty = QLabel("لا توجد تكرارات")
            empty.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
            empty.setStyleSheet("color: #10B981; background: transparent;")
            empty.setAlignment(Qt.AlignCenter)
            self._rows_layout.addWidget(empty)
        else:
            for dup in self._duplicates:
                row = self._create_duplicate_row(dup)
                self._rows_layout.addWidget(row)

        self._rows_layout.addStretch()

    def _create_duplicate_row(self, entity: dict) -> QFrame:
        """Create a row for a single duplicate entity."""
        row = QFrame()
        row.setFixedHeight(56)
        row.setStyleSheet("""
            QFrame {
                background-color: #FFFBEB;
                border: 1px solid #FDE68A;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(12)

        # Entity type badge
        entity_type = entity.get("entityType", "unknown")
        type_text = _ENTITY_TYPE_AR.get(entity_type, entity_type)

        type_badge = QLabel(type_text)
        type_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        type_badge.setAlignment(Qt.AlignCenter)
        type_badge.setFixedHeight(26)
        type_badge.setFixedWidth(90)
        type_badge.setStyleSheet("""
            padding: 2px 12px;
            border-radius: 13px;
            color: #92400E;
            background-color: #FEF3C7;
        """)
        row_layout.addWidget(type_badge)

        # Source ID
        source_id = entity.get("sourceId", "") or entity.get("id", "")
        id_label = QLabel(source_id)
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        id_label.setStyleSheet("color: #212B36;")
        row_layout.addWidget(id_label)

        row_layout.addStretch()

        # Match score
        score = entity.get("duplicateScore", 0) or entity.get("matchScore", 0)
        if score:
            score_pct = int(score * 100) if score <= 1 else int(score)
            score_label = QLabel(f"تطابق: {score_pct}%")
            score_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            score_label.setStyleSheet("color: #F59E0B;")
            row_layout.addWidget(score_label)

        return row

    def _clear_rows(self):
        """Remove all rows from the layout."""
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_error(self, message: str):
        """Display an error message."""
        self._clear_rows()
        error_label = QLabel(message)
        error_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        error_label.setStyleSheet("color: #EF4444; background: transparent;")
        error_label.setAlignment(Qt.AlignCenter)
        self._rows_layout.addWidget(error_label)
        self._rows_layout.addStretch()

    def get_duplicates(self) -> list:
        """Return the loaded duplicates list."""
        return self._duplicates
