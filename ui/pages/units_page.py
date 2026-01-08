# -*- coding: utf-8 -*-
"""
Property Units list page with filters and CRUD operations.
Implements UC-002: Property Unit Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QTextEdit,
    QAbstractItemView, QGraphicsDropShadowEffect, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor

from app.config import Config, Vocabularies
from repositories.database import Database
from repositories.unit_repository import UnitRepository
from repositories.building_repository import BuildingRepository
from models.unit import PropertyUnit
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitsTableModel(QAbstractTableModel):
    """Table model for property units."""

    def __init__(self, is_arabic: bool = True):
        super().__init__()
        self._units = []
        self._is_arabic = is_arabic
        self._headers_en = ["Unit ID", "Building ID", "Type", "Floor", "Number", "Status", "Area (m²)"]
        self._headers_ar = ["رقم الوحدة", "رقم المبنى", "النوع", "الطابق", "الرقم", "الحالة", "المساحة"]

    def rowCount(self, parent=None):
        return len(self._units)

    def columnCount(self, parent=None):
        return len(self._headers_en)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._units):
            return None

        unit = self._units[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return unit.unit_id
            elif col == 1:
                return unit.building_id
            elif col == 2:
                return unit.unit_type_display_ar if self._is_arabic else unit.unit_type_display
            elif col == 3:
                return str(unit.floor_number)
            elif col == 4:
                return unit.apartment_number
            elif col == 5:
                return unit.status_display
            elif col == 6:
                return f"{unit.area_sqm:.1f}" if unit.area_sqm else "-"
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = self._headers_ar if self._is_arabic else self._headers_en
            return headers[section] if section < len(headers) else ""
        return None

    def set_units(self, units: list):
        self.beginResetModel()
        self._units = units
        self.endResetModel()

    def get_unit(self, row: int):
        if 0 <= row < len(self._units):
            return self._units[row]
        return None

    def set_language(self, is_arabic: bool):
        self._is_arabic = is_arabic
        self.layoutChanged.emit()


class UnitDialog(QDialog):
    """Dialog for creating/editing a property unit."""

    def __init__(self, db: Database, i18n: I18n, unit: PropertyUnit = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit = unit
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self._is_edit_mode = unit is not None

        self.setWindowTitle(i18n.t("edit_unit") if unit else i18n.t("add_unit"))
        self.setMinimumWidth(500)
        self._setup_ui()

        if unit:
            self._populate_data()
        else:
            # Auto-suggest first unit number for selected building
            self._on_building_changed()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        # Building selection
        self.building_combo = QComboBox()
        buildings = self.building_repo.get_all(limit=500)
        for b in buildings:
            display = f"{b.building_id} - {b.neighborhood_name_ar}"
            self.building_combo.addItem(display, b.building_id)
        self.building_combo.currentIndexChanged.connect(self._on_building_changed)
        form.addRow(self.i18n.t("building") + ":", self.building_combo)

        # Unit number (3-digit suffix)
        unit_number_container = QWidget()
        unit_number_layout = QVBoxLayout(unit_number_container)
        unit_number_layout.setContentsMargins(0, 0, 0, 0)
        unit_number_layout.setSpacing(4)

        self.unit_number_input = QLineEdit()
        self.unit_number_input.setPlaceholderText("001")
        self.unit_number_input.setMaxLength(3)
        self.unit_number_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
            }}
        """)
        self.unit_number_input.textChanged.connect(self._validate_unit_number)
        unit_number_layout.addWidget(self.unit_number_input)

        self.unit_number_hint = QLabel("رقم الوحدة: 3 أرقام (001-999)")
        self.unit_number_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 11px;")
        unit_number_layout.addWidget(self.unit_number_hint)

        self.unit_number_error = QLabel("")
        self.unit_number_error.setStyleSheet("color: #DC2626; font-size: 11px;")
        self.unit_number_error.setVisible(False)
        unit_number_layout.addWidget(self.unit_number_error)

        form.addRow("رقم الوحدة:", unit_number_container)

        # Unit type
        self.type_combo = QComboBox()
        for code, en, ar in Vocabularies.UNIT_TYPES:
            self.type_combo.addItem(ar, code)
        form.addRow(self.i18n.t("unit_type") + ":", self.type_combo)

        # Floor number
        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 50)
        self.floor_spin.setValue(0)
        form.addRow(self.i18n.t("floor") + ":", self.floor_spin)

        # Apartment number
        self.apt_number = QLineEdit()
        self.apt_number.setPlaceholderText("مثال: 101")
        form.addRow(self.i18n.t("apartment_number") + ":", self.apt_number)

        # Status
        self.status_combo = QComboBox()
        statuses = [("occupied", "مشغول"), ("vacant", "شاغر"), ("unknown", "غير معروف")]
        for code, ar in statuses:
            self.status_combo.addItem(ar, code)
        form.addRow(self.i18n.t("status") + ":", self.status_combo)

        # Area
        self.area_spin = QSpinBox()
        self.area_spin.setRange(0, 10000)
        self.area_spin.setSuffix(" م²")
        form.addRow(self.i18n.t("area") + ":", self.area_spin)

        # Description
        self.description = QTextEdit()
        self.description.setMaximumHeight(80)
        self.description.setPlaceholderText("وصف الوحدة...")
        form.addRow(self.i18n.t("description") + ":", self.description)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate_data(self):
        """Populate form with existing unit data."""
        if not self.unit:
            return

        # Find and select building (block signal to avoid auto-suggest overwriting)
        self.building_combo.blockSignals(True)
        idx = self.building_combo.findData(self.unit.building_id)
        if idx >= 0:
            self.building_combo.setCurrentIndex(idx)
        self.building_combo.blockSignals(False)

        # Unit number
        self.unit_number_input.setText(self.unit.unit_number or "001")

        # Unit type
        idx = self.type_combo.findData(self.unit.unit_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.floor_spin.setValue(self.unit.floor_number)
        self.apt_number.setText(self.unit.apartment_number)

        idx = self.status_combo.findData(self.unit.apartment_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        if self.unit.area_sqm:
            self.area_spin.setValue(int(self.unit.area_sqm))

        self.description.setPlainText(self.unit.property_description or "")

    def _on_building_changed(self):
        """Handle building selection change - auto-suggest next unit number."""
        if self._is_edit_mode:
            return  # Don't auto-suggest in edit mode

        building_id = self.building_combo.currentData()
        if building_id:
            next_number = self.unit_repo.get_next_unit_number(building_id)
            self.unit_number_input.setText(next_number)
            self.unit_number_hint.setText(f"رقم الوحدة التالي المتاح: {next_number}")

    def _validate_unit_number(self):
        """Validate unit number format and uniqueness."""
        text = self.unit_number_input.text().strip()

        # Check if empty
        if not text:
            self._show_unit_number_error("رقم الوحدة مطلوب")
            return False

        # Check if numeric
        if not text.isdigit():
            self._show_unit_number_error("يجب أن يكون رقم الوحدة أرقاماً فقط")
            return False

        # Check range (001-999)
        num = int(text)
        if num < 1 or num > 999:
            self._show_unit_number_error("يجب أن يكون الرقم بين 001 و 999")
            return False

        # Check uniqueness
        building_id = self.building_combo.currentData()
        padded_number = text.zfill(3)
        exclude_uuid = self.unit.unit_uuid if self.unit else None

        if self.unit_repo.unit_number_exists(building_id, padded_number, exclude_uuid):
            self._show_unit_number_error("رقم الوحدة موجود مسبقاً في هذا المبنى")
            return False

        # Valid
        self._hide_unit_number_error()
        return True

    def _show_unit_number_error(self, message: str):
        """Show unit number validation error."""
        self.unit_number_error.setText(message)
        self.unit_number_error.setVisible(True)
        self.unit_number_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #FEF2F2;
                border: 2px solid #DC2626;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
        """)

    def _hide_unit_number_error(self):
        """Hide unit number validation error."""
        self.unit_number_error.setVisible(False)
        self.unit_number_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
            }}
        """)

    def _get_padded_unit_number(self) -> str:
        """Get unit number padded to 3 digits."""
        text = self.unit_number_input.text().strip()
        if text.isdigit():
            return text.zfill(3)
        return "001"

    def accept(self):
        """Override accept to validate before closing."""
        if not self._validate_unit_number():
            QMessageBox.warning(
                self,
                "خطأ في البيانات",
                "الرجاء تصحيح رقم الوحدة قبل الحفظ"
            )
            return
        super().accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        unit_number = self._get_padded_unit_number()
        building_id = self.building_combo.currentData()
        # Generate unit_id from building_id + unit_number
        unit_id = f"{building_id}-{unit_number}"

        return {
            "building_id": building_id,
            "unit_number": unit_number,
            "unit_id": unit_id,
            "unit_type": self.type_combo.currentData(),
            "floor_number": self.floor_spin.value(),
            "apartment_number": self.apt_number.text().strip(),
            "apartment_status": self.status_combo.currentData(),
            "area_sqm": float(self.area_spin.value()) if self.area_spin.value() > 0 else None,
            "property_description": self.description.toPlainText().strip(),
        }


class UnitsPage(QWidget):
    """Property Units management page."""

    view_unit = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.building_repo = BuildingRepository(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel(self.i18n.t("property_units"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Add unit button
        add_btn = QPushButton("+ " + self.i18n.t("add_unit"))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #219A52;
            }}
        """)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_unit)
        header_layout.addWidget(add_btn)

        layout.addLayout(header_layout)

        # Filters
        filters_frame = QFrame()
        filters_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        filters_frame.setGraphicsEffect(shadow)

        filters_layout = QHBoxLayout(filters_frame)
        filters_layout.setContentsMargins(24, 20, 24, 20)
        filters_layout.setSpacing(20)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("بحث بالرقم...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
            }}
        """)
        self.search_input.textChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.search_input)

        # Building filter
        self.building_combo = QComboBox()
        self.building_combo.addItem(self.i18n.t("all"), "")
        self.building_combo.setMinimumWidth(200)
        self.building_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.building_combo)

        # Type filter
        self.type_combo = QComboBox()
        self.type_combo.addItem(self.i18n.t("all"), "")
        for code, en, ar in Vocabularies.UNIT_TYPES:
            self.type_combo.addItem(ar, code)
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.type_combo)

        filters_layout.addStretch()
        layout.addWidget(filters_frame)

        # Results count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.count_label)

        # Table
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        table_shadow = QGraphicsDropShadowEffect()
        table_shadow.setBlurRadius(20)
        table_shadow.setColor(QColor(0, 0, 0, 20))
        table_shadow.setOffset(0, 4)
        table_frame.setGraphicsEffect(table_shadow)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
                border-radius: 12px;
            }}
            QTableView::item {{
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)
        self.table.doubleClicked.connect(self._on_row_double_click)

        self.table_model = UnitsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        table_layout.addWidget(self.table)
        layout.addWidget(table_frame)

    def refresh(self, data=None):
        """Refresh the units list."""
        logger.debug("Refreshing units page")
        self._load_buildings_filter()
        self._load_units()

    def _load_buildings_filter(self):
        """Load buildings into filter combo."""
        current = self.building_combo.currentData()
        self.building_combo.clear()
        self.building_combo.addItem(self.i18n.t("all"), "")

        buildings = self.building_repo.get_all(limit=200)
        for b in buildings:
            display = f"{b.building_id[:15]}... - {b.neighborhood_name_ar}"
            self.building_combo.addItem(display, b.building_id)

        if current:
            idx = self.building_combo.findData(current)
            if idx >= 0:
                self.building_combo.setCurrentIndex(idx)

    def _load_units(self):
        """Load units with filters."""
        search = self.search_input.text().strip()
        building_id = self.building_combo.currentData()
        unit_type = self.type_combo.currentData()

        units = self.unit_repo.search(
            building_id=building_id or None,
            unit_type=unit_type or None,
            search_text=search or None,
            limit=500
        )

        self.table_model.set_units(units)
        self.count_label.setText(f"تم العثور على {len(units)} وحدة")

    def _on_filter_changed(self):
        self._load_units()

    def _on_row_double_click(self, index):
        """Handle double-click to edit unit."""
        unit = self.table_model.get_unit(index.row())
        if unit:
            self._edit_unit(unit)

    def _on_add_unit(self):
        """Add new unit."""
        dialog = UnitDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            unit = PropertyUnit(**data)

            try:
                self.unit_repo.create(unit)
                Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"Failed to create unit: {e}")
                Toast.show_toast(self, f"فشل في إضافة الوحدة: {str(e)}", Toast.ERROR)

    def _edit_unit(self, unit: PropertyUnit):
        """Edit existing unit."""
        dialog = UnitDialog(self.db, self.i18n, unit=unit, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(unit, key, value)

            try:
                self.unit_repo.update(unit)
                Toast.show_toast(self, "تم تحديث الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"Failed to update unit: {e}")
                Toast.show_toast(self, f"فشل في تحديث الوحدة: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update language."""
        self.table_model.set_language(is_arabic)
