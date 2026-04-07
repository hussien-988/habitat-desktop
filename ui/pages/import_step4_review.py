# -*- coding: utf-8 -*-
"""Import wizard step 3: review staged entities before commit."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from ui.components.animated_card import EmptyStateAnimated
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger
import re

logger = get_logger(__name__)


def _translate_display(entity_type: str, field: str, value: str) -> str:
    """Translate API display values to Arabic using vocab service."""
    if not value or value == "-":
        return value

    # Households: "Size: N" → "N أفراد"
    size_match = re.match(r"^Size:\s*(\d+)$", value, re.IGNORECASE)
    if size_match:
        return tr("wizard.import.step4.household_members", count=size_match.group(1))

    # Use vocab service for known types
    if entity_type == "personPropertyRelations" and field == "displayInfo":
        from services.display_mappings import get_relation_type_display
        label = get_relation_type_display(value)
        if label and label != value:
            return label

    if entity_type == "claims" and field == "identifier":
        _claim_type_keys = {
            "Ownership": "wizard.import.step4.claim_ownership",
            "Tenancy": "wizard.import.step4.claim_tenancy",
            "Occupancy": "wizard.import.step4.claim_occupancy",
            "Inheritance": "wizard.import.step4.claim_inheritance",
            "Other": "wizard.import.step4.claim_other",
        }
        key = _claim_type_keys.get(value)
        return tr(key) if key else value

    if entity_type == "claims" and field == "displayInfo":
        _collection_keys = {
            "FieldCollection": "wizard.import.step4.collection_field",
            "OfficeEntry": "wizard.import.step4.collection_office",
            "Import": "wizard.import.step4.collection_import",
            "Migration": "wizard.import.step4.collection_migration",
        }
        key = _collection_keys.get(value)
        return tr(key) if key else value

    return value

# Entity sections matching API response keys
_ENTITY_SECTION_KEYS = [
    ('surveys', 'wizard.import.entity.surveys', '#6366F1', '#EEF2FF'),
    ('buildings', 'wizard.import.entity.buildings', '#3890DF', '#EBF5FF'),
    ('propertyUnits', 'wizard.import.entity.property_units', '#10B981', '#ECFDF5'),
    ('persons', 'wizard.import.entity.persons', '#8B5CF6', '#F5F3FF'),
    ('households', 'wizard.import.entity.households', '#EC4899', '#FDF2F8'),
    ('personPropertyRelations', 'wizard.import.entity.person_property_relations', '#14B8A6', '#F0FDFA'),
    ('evidences', 'wizard.import.entity.evidences', '#F97316', '#FFF7ED'),
    ('claims', 'wizard.import.entity.claims', '#F59E0B', '#FFFBEB'),
]


def _get_entity_sections():
    return [(k, tr(tr_key), c, bg) for k, tr_key, c, bg in _ENTITY_SECTION_KEYS]

# Validation status display
_STATUS_CONFIG_KEYS = {
    'Valid': {'tr_key': 'wizard.import.step4.status_valid', 'color': '#10B981', 'bg': '#ECFDF5'},
    'Invalid': {'tr_key': 'wizard.import.step4.status_invalid', 'color': '#EF4444', 'bg': '#FEF2F2'},
    'Warning': {'tr_key': 'wizard.import.step4.status_warning', 'color': '#F59E0B', 'bg': '#FFFBEB'},
    'Pending': {'tr_key': 'wizard.import.step4.status_pending', 'color': '#9CA3AF', 'bg': '#F3F4F6'},
    'Skipped': {'tr_key': 'wizard.import.step4.status_skipped', 'color': '#6B7280', 'bg': '#F9FAFB'},
}

_DEFAULT_STATUS_KEY = {'tr_key': 'wizard.import.step4.status_unknown', 'color': '#9CA3AF', 'bg': '#F3F4F6'}


def _get_status_config(status_key):
    cfg = _STATUS_CONFIG_KEYS.get(status_key, _DEFAULT_STATUS_KEY)
    return {'label': tr(cfg['tr_key']), 'color': cfg['color'], 'bg': cfg['bg']}


class ImportStep4Review(QWidget):
    """Step 3 (Review): Review all staged entities before commit."""

    def __init__(self, import_controller, package_id, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id
        self._data = {}
        self._dots_count = 0
        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()
        self.load_entities(package_id)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

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

        title = QLabel(tr("wizard.import.step4.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        summary_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        summary_layout.addWidget(sep)

        # Total count
        self._total_label = QLabel(tr("wizard.import.step4.total_entities", count=0))
        self._total_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._total_label.setStyleSheet("color: #212B36; background: transparent;")
        summary_layout.addWidget(self._total_label)

        # Count badges (2 rows of 4)
        self._count_labels = {}

        entity_sections = _get_entity_sections()

        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(16)
        for key, ar_name, color, bg in entity_sections[:4]:
            badge, count_label = self._create_count_badge(ar_name, "0", color, bg)
            self._count_labels[key] = count_label
            row1_layout.addWidget(badge)
        row1_layout.addStretch()
        summary_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(16)
        for key, ar_name, color, bg in entity_sections[4:]:
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

        table_title = QLabel(tr("wizard.import.step4.entity_details"))
        table_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        table_title.setStyleSheet("color: #212B36; background: transparent;")
        table_layout.addWidget(table_title)

        # Empty state label
        self._empty_label = EmptyStateAnimated(
            title=tr("wizard.import.step4.no_staged_entities"),
        )
        self._empty_label.setMinimumHeight(ScreenScale.h(200))
        self._empty_label.setVisible(False)
        table_layout.addWidget(self._empty_label)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            tr("wizard.import.step4.col_type"),
            tr("wizard.import.step4.col_identifier"),
            tr("wizard.import.step4.col_description"),
            tr("wizard.import.step4.col_validation_status"),
            tr("wizard.import.step4.col_approved"),
        ])
        self._table.setLayoutDirection(get_layout_direction())
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(ScreenScale.h(350))

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
        """ + StyleManager.scrollbar())
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border-radius: 16px;
                border: 1px solid #E2EAF2;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 22))
        card.setGraphicsEffect(shadow)
        return card

    def _create_count_badge(self, label_text: str, count_text: str,
                            color: str, bg: str):
        """Create a summary count badge. Returns (container, count_label)."""
        container = QFrame()
        container.setFixedHeight(ScreenScale.h(50))
        container.setMinimumWidth(ScreenScale.w(130))
        container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg}, stop:1 #FFFFFF);
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

    # -- Loading overlay -------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 200); }")
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(ScreenScale.w(240), ScreenScale.h(90))
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(6)

        self._loading_label = QLabel(tr("wizard.import.step4.loading"))
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_label)

        self._loading_dots = QLabel("")
        self._loading_dots.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._loading_dots.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_dots.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_dots)

        overlay_layout.addWidget(card)

        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)

        return overlay

    def _show_loading(self, message: str):
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)

    def _hide_loading(self):
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

    def _animate_dots(self):
        self._dots_count = (self._dots_count + 1) % 4
        self._loading_dots.setText("." * self._dots_count)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Data loading ----------------------------------------------------------

    def load_entities(self, package_id: str):
        """Load staged entities from the controller (grouped response)."""
        logger.info(f"Loading staged entities for package {package_id}")
        self._package_id = package_id

        self._show_loading(tr("wizard.import.step4.loading_entities"))
        result = self.import_controller.get_staged_entities(package_id)
        self._hide_loading()

        if not result.success:
            logger.error(f"Failed to load entities: {result.message}")
            from ui.components.message_dialog import MessageDialog
            MessageDialog.error(self, tr("wizard.import.step4.error"), result.message_ar or tr("wizard.import.step4.entities_load_failed"))
            return

        self._data = result.data or {}
        self._update_ui()

    def _update_ui(self):
        """Update UI with grouped entity data."""
        d = self._data
        total = d.get("totalCount", 0)
        self._total_label.setText(tr("wizard.import.step4.total_entities", count=total))

        # Update count badges
        for key, _, _, _ in _ENTITY_SECTION_KEYS:
            section_items = d.get(key, [])
            count = len(section_items) if isinstance(section_items, list) else 0
            if key in self._count_labels:
                self._count_labels[key].setText(str(count))

        # Flatten all entities for the table
        all_rows = []

        for key, ar_name, _, _ in _get_entity_sections():
            section_items = d.get(key, [])
            if not isinstance(section_items, list):
                continue
            for entity in section_items:
                all_rows.append((key, ar_name, entity))

        # Empty state
        if not all_rows:
            self._table.setVisible(False)
            self._empty_label.setVisible(True)
            return

        self._table.setVisible(True)
        self._empty_label.setVisible(False)

        self._table.setRowCount(len(all_rows))
        for row_idx, (type_key, type_name, entity) in enumerate(all_rows):
            identifier = entity.get("identifier", "")
            display_info = entity.get("displayInfo", "")
            validation_status = entity.get("validationStatus", "Pending")
            is_approved = entity.get("isApprovedForCommit", False)

            # Translate to Arabic
            identifier = _translate_display(type_key, "identifier", str(identifier))
            display_info = _translate_display(type_key, "displayInfo", str(display_info))

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
            status_config = _get_status_config(validation_status)
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
        badge.setFixedHeight(ScreenScale.h(26))
        badge.setMinimumWidth(ScreenScale.w(80))
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
            label = tr("wizard.import.step4.approved")
            color = "#10B981"
            bg = "#ECFDF5"
        else:
            label = tr("wizard.import.step4.not_approved")
            color = "#9CA3AF"
            bg = "#F3F4F6"

        badge = QLabel(label)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(26))
        badge.setMinimumWidth(ScreenScale.w(80))
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
        self._total_label.setText(tr("wizard.import.step4.total_entities", count=0))
        for label in self._count_labels.values():
            label.setText("0")
        self._table.setRowCount(0)
        self._table.setVisible(True)
        self._empty_label.setVisible(False)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Total label
        total = self._data.get("totalCount", 0) if self._data else 0
        self._total_label.setText(tr("wizard.import.step4.total_entities", count=total))

        # Empty state label
        self._empty_label.set_title(tr("wizard.import.step4.no_staged_entities"))

        # Loading label
        self._loading_label.setText(tr("wizard.import.step4.loading"))

        # Table header labels
        self._table.setHorizontalHeaderLabels([
            tr("wizard.import.step4.col_type"),
            tr("wizard.import.step4.col_identifier"),
            tr("wizard.import.step4.col_description"),
            tr("wizard.import.step4.col_validation_status"),
            tr("wizard.import.step4.col_approved"),
        ])
        self._table.setLayoutDirection(get_layout_direction())

        # Re-populate table and count badges with updated translations
        if self._data:
            self._update_ui()
