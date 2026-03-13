# -*- coding: utf-8 -*-
"""
Import Wizard - Step 4: Review Staged Entities
UC-003: Import Pipeline

Displays all staged entities in a table for review before committing.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy
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

# Status display configuration
_STATUS_CONFIG = {
    'pending': {
        'label': 'قيد الانتظار',
        'color': '#9CA3AF',
        'bg': '#F3F4F6',
    },
    'valid': {
        'label': 'صالح',
        'color': '#10B981',
        'bg': '#ECFDF5',
    },
    'invalid': {
        'label': 'غير صالح',
        'color': '#EF4444',
        'bg': '#FEF2F2',
    },
    'duplicate': {
        'label': 'مكرر',
        'color': '#F59E0B',
        'bg': '#FFFBEB',
    },
    'staged': {
        'label': 'مرحلي',
        'color': '#3B82F6',
        'bg': '#EFF6FF',
    },
}


class ImportStep4Review(QWidget):
    """Step 4: Review all staged entities."""

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._entities = []
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Review card
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
        title = QLabel("مراجعة الكيانات المرحلية")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Summary counts row
        self._summary_layout = QHBoxLayout()
        self._summary_layout.setSpacing(20)

        self._buildings_count = self._create_count_badge("مبنى", "0", "#3890DF", "#EBF5FF")
        self._persons_count = self._create_count_badge("شخص", "0", "#8B5CF6", "#F5F3FF")
        self._units_count = self._create_count_badge("وحدة عقارية", "0", "#10B981", "#ECFDF5")
        self._claims_count = self._create_count_badge("مطالبة", "0", "#F59E0B", "#FFFBEB")

        self._summary_layout.addStretch()
        card_layout.addLayout(self._summary_layout)

        # Entities table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["النوع", "المعرّف", "الحالة"])
        self._table.setLayoutDirection(Qt.RightToLeft)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(300)
        self._table.setMaximumHeight(450)

        # Column widths
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 140)
        self._table.setColumnWidth(2, 140)

        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                gridline-color: #F4F6F8;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #EFF6FF;
                color: #212B36;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                color: #637381;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid #E1E8ED;
                font-weight: 600;
            }
        """)
        self._table.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))

        card_layout.addWidget(self._table)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def _create_count_badge(self, label_text: str, count_text: str,
                            color: str, bg: str) -> QLabel:
        """Create a summary count badge."""
        container = QFrame()
        container.setFixedHeight(50)
        container.setMinimumWidth(130)
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border-radius: 10px;
                border: none;
            }}
            QFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(12, 6, 12, 6)
        c_layout.setSpacing(8)

        count_label = QLabel(count_text)
        count_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        count_label.setStyleSheet(f"color: {color};")
        c_layout.addWidget(count_label)

        name_label = QLabel(label_text)
        name_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        name_label.setStyleSheet("color: #637381;")
        c_layout.addWidget(name_label)

        self._summary_layout.addWidget(container)
        return count_label

    def load_entities(self, package_id: str):
        """Load staged entities from the controller."""
        logger.info(f"Loading staged entities for package {package_id}")

        result = self.import_controller.get_staged_entities(package_id)

        if not result.success:
            logger.error(f"Failed to load entities: {result.message}")
            return

        self._entities = result.data or []
        self._update_ui()

    def _update_ui(self):
        """Update UI with entity data."""
        # Count by type
        counts = {
            'building': 0,
            'person': 0,
            'property_unit': 0,
            'claim': 0,
            'survey': 0,
        }
        for entity in self._entities:
            entity_type = entity.get("entityType", "unknown")
            if entity_type in counts:
                counts[entity_type] += 1

        self._buildings_count.setText(str(counts['building']))
        self._persons_count.setText(str(counts['person']))
        self._units_count.setText(str(counts['property_unit']))
        self._claims_count.setText(str(counts['claim']))

        # Populate table
        self._table.setRowCount(len(self._entities))
        for row_idx, entity in enumerate(self._entities):
            entity_type = entity.get("entityType", "unknown")
            source_id = entity.get("sourceId", "") or entity.get("id", "")
            status = entity.get("status", "pending")

            # Type column
            type_text = _ENTITY_TYPE_AR.get(entity_type, entity_type)
            type_item = QTableWidgetItem(type_text)
            type_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 0, type_item)

            # ID column
            id_item = QTableWidgetItem(str(source_id))
            id_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row_idx, 1, id_item)

            # Status column (text-only, styled via delegate or cell widget)
            status_config = _STATUS_CONFIG.get(status, _STATUS_CONFIG['pending'])
            status_widget = self._create_status_badge(status_config)
            self._table.setCellWidget(row_idx, 2, status_widget)

            self._table.setRowHeight(row_idx, 44)

    def _create_status_badge(self, config: dict) -> QWidget:
        """Create a status badge widget for table cell."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignCenter)

        badge = QLabel(config['label'])
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(26)
        badge.setMinimumWidth(80)
        badge.setStyleSheet(f"""
            padding: 2px 12px;
            border-radius: 13px;
            color: {config['color']};
            background-color: {config['bg']};
        """)
        layout.addWidget(badge)

        return container

    def get_entities(self) -> list:
        """Return the loaded entities list."""
        return self._entities
