# -*- coding: utf-8 -*-
"""
Import Wizard - Step 3 (Review): Review Staged Entities
UC-003: Import Pipeline

Displays all staged entities grouped by type in a table for review
before committing. Uses the grouped API response from GET .../staged-entities.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Entity sections matching API response keys
_ENTITY_SECTIONS = [
    ('surveys', 'المسوحات', '#6366F1', '#EEF2FF'),
    ('buildings', 'المباني', '#3890DF', '#EBF5FF'),
    ('propertyUnits', 'الوحدات العقارية', '#10B981', '#ECFDF5'),
    ('persons', 'الأشخاص', '#8B5CF6', '#F5F3FF'),
    ('households', 'الأسر', '#EC4899', '#FDF2F8'),
    ('personPropertyRelations', 'علاقات الأشخاص بالعقارات', '#14B8A6', '#F0FDFA'),
    ('evidences', 'المستندات', '#F97316', '#FFF7ED'),
    ('claims', 'المطالبات', '#F59E0B', '#FFFBEB'),
]

# Validation status display
_STATUS_CONFIG = {
    'Valid': {'label': 'صالح', 'color': '#10B981', 'bg': '#ECFDF5'},
    'Invalid': {'label': 'غير صالح', 'color': '#EF4444', 'bg': '#FEF2F2'},
    'Warning': {'label': 'تحذير', 'color': '#F59E0B', 'bg': '#FFFBEB'},
    'Pending': {'label': 'قيد الانتظار', 'color': '#9CA3AF', 'bg': '#F3F4F6'},
    'Skipped': {'label': 'تم تخطيه', 'color': '#6B7280', 'bg': '#F9FAFB'},
}

_DEFAULT_STATUS = {'label': 'غير معروف', 'color': '#9CA3AF', 'bg': '#F3F4F6'}


class ImportStep4Review(QWidget):
    """Step 3 (Review): Review all staged entities before commit."""

    def __init__(self, import_controller, package_id, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id
        self._data = {}
        self._setup_ui()
        self.load_entities(package_id)

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 24, 0, 24)
        main_layout.setSpacing(20)

        # --- Card 1: Summary counts ---
        summary_card = self._create_card()
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(32, 24, 32, 24)
        summary_layout.setSpacing(16)

        title = QLabel("مراجعة الكيانات المرحلية")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        summary_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        summary_layout.addWidget(sep)

        # Total count
        self._total_label = QLabel("إجمالي الكيانات: 0")
        self._total_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._total_label.setStyleSheet("color: #212B36; background: transparent;")
        summary_layout.addWidget(self._total_label)

        # Count badges (2 rows of 4)
        self._count_labels = {}

        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(16)
        for key, ar_name, color, bg in _ENTITY_SECTIONS[:4]:
            badge, count_label = self._create_count_badge(ar_name, "0", color, bg)
            self._count_labels[key] = count_label
            row1_layout.addWidget(badge)
        row1_layout.addStretch()
        summary_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(16)
        for key, ar_name, color, bg in _ENTITY_SECTIONS[4:]:
            badge, count_label = self._create_count_badge(ar_name, "0", color, bg)
            self._count_labels[key] = count_label
            row2_layout.addWidget(badge)
        row2_layout.addStretch()
        summary_layout.addLayout(row2_layout)

        main_layout.addWidget(summary_card)

        # --- Card 2: Entities table ---
        table_card = self._create_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(32, 24, 32, 24)
        table_layout.setSpacing(16)

        table_title = QLabel("تفاصيل الكيانات")
        table_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        table_title.setStyleSheet("color: #212B36; background: transparent;")
        table_layout.addWidget(table_title)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "النوع", "المعرّف", "الوصف", "حالة التحقق", "معتمد للإدخال"
        ])
        self._table.setLayoutDirection(Qt.RightToLeft)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(350)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 160)
        self._table.setColumnWidth(1, 180)
        self._table.setColumnWidth(3, 120)
        self._table.setColumnWidth(4, 120)

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

        table_layout.addWidget(self._table)
        main_layout.addWidget(table_card)

        main_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _create_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        return card

    def _create_count_badge(self, label_text: str, count_text: str,
                            color: str, bg: str):
        """Create a summary count badge. Returns (container, count_label)."""
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

        return container, count_label

    def load_entities(self, package_id: str):
        """Load staged entities from the controller (grouped response)."""
        logger.info(f"Loading staged entities for package {package_id}")
        self._package_id = package_id

        result = self.import_controller.get_staged_entities(package_id)

        if not result.success:
            logger.error(f"Failed to load entities: {result.message}")
            return

        self._data = result.data or {}
        self._update_ui()

    def _update_ui(self):
        """Update UI with grouped entity data."""
        d = self._data
        total = d.get("totalCount", 0)
        self._total_label.setText(f"إجمالي الكيانات: {total}")

        # Update count badges
        for key, _, _, _ in _ENTITY_SECTIONS:
            section_items = d.get(key, [])
            count = len(section_items) if isinstance(section_items, list) else 0
            if key in self._count_labels:
                self._count_labels[key].setText(str(count))

        # Flatten all entities for the table
        all_rows = []
        section_names = {k: ar for k, ar, _, _ in _ENTITY_SECTIONS}

        for key, ar_name, _, _ in _ENTITY_SECTIONS:
            section_items = d.get(key, [])
            if not isinstance(section_items, list):
                continue
            for entity in section_items:
                all_rows.append((ar_name, entity))

        self._table.setRowCount(len(all_rows))
        for row_idx, (type_name, entity) in enumerate(all_rows):
            identifier = entity.get("identifier", "")
            display_info = entity.get("displayInfo", "")
            validation_status = entity.get("validationStatus", "Pending")
            is_approved = entity.get("isApprovedForCommit", False)

            # Type column
            type_item = QTableWidgetItem(type_name)
            type_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 0, type_item)

            # Identifier column
            id_item = QTableWidgetItem(str(identifier))
            id_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row_idx, 1, id_item)

            # Display info column
            info_item = QTableWidgetItem(str(display_info))
            info_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row_idx, 2, info_item)

            # Validation status column
            status_config = _STATUS_CONFIG.get(validation_status, _DEFAULT_STATUS)
            status_widget = self._create_status_badge(status_config)
            self._table.setCellWidget(row_idx, 3, status_widget)

            # Approved column
            approved_widget = self._create_approval_badge(is_approved)
            self._table.setCellWidget(row_idx, 4, approved_widget)

            self._table.setRowHeight(row_idx, 44)

    def _create_status_badge(self, config: dict) -> QWidget:
        """Create a validation status badge widget for table cell."""
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

    def _create_approval_badge(self, is_approved: bool) -> QWidget:
        """Create an approval status badge."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignCenter)

        if is_approved:
            label = "معتمد"
            color = "#10B981"
            bg = "#ECFDF5"
        else:
            label = "غير معتمد"
            color = "#9CA3AF"
            bg = "#F3F4F6"

        badge = QLabel(label)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(26)
        badge.setMinimumWidth(80)
        badge.setStyleSheet(f"""
            padding: 2px 12px;
            border-radius: 13px;
            color: {color};
            background-color: {bg};
        """)
        layout.addWidget(badge)
        return container

    def get_entities(self) -> dict:
        """Return the loaded grouped entities dict."""
        return self._data

    def reset(self):
        """Reset the step to initial state."""
        self._data = {}
        self._total_label.setText("إجمالي الكيانات: 0")
        for label in self._count_labels.values():
            label.setText("0")
        self._table.setRowCount(0)
