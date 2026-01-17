# -*- coding: utf-8 -*-
"""
Table models for QTableView.
"""

from typing import List, Any, Optional
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PyQt5.QtGui import QColor, QBrush

from models.building import Building
from models.unit import PropertyUnit
from models.person import Person
from models.claim import Claim
from ui.components.base_table_model import BaseTableModel


class BuildingsTableModel(QAbstractTableModel):
    """Table model for buildings list."""

    def __init__(self, buildings: List[Building] = None, is_arabic: bool = False, parent=None):
        super().__init__(parent)
        self._buildings = buildings or []
        self._is_arabic = is_arabic
        self._columns = [
            ("building_id", "Building ID", "رقم المبنى"),
            ("neighborhood_name", "Neighborhood", "الحي"),
            ("building_type", "Type", "النوع"),
            ("building_status", "Status", "الحالة"),
            ("number_of_units", "Units", "الوحدات"),
            ("number_of_floors", "Floors", "الطوابق"),
        ]

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._buildings)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not self._buildings:
            return QVariant()

        building = self._buildings[index.row()]
        column_key = self._columns[index.column()][0]

        if role == Qt.DisplayRole:
            if column_key == "building_id":
                return building.building_id
            elif column_key == "neighborhood_name":
                return building.neighborhood_name_ar if self._is_arabic else building.neighborhood_name
            elif column_key == "building_type":
                return building.building_type_display
            elif column_key == "building_status":
                return building.building_status_display
            elif column_key == "number_of_units":
                return building.number_of_units
            elif column_key == "number_of_floors":
                return building.number_of_floors

        elif role == Qt.BackgroundRole:
            # Color code by status
            if building.building_status == "destroyed":
                return QBrush(QColor("#ffebee"))
            elif building.building_status == "major_damage":
                return QBrush(QColor("#fff3e0"))

        elif role == Qt.TextAlignmentRole:
            if column_key in ["number_of_units", "number_of_floors"]:
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.UserRole:
            # Return building ID for selection
            return building.building_id

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            col = self._columns[section]
            return col[2] if self._is_arabic else col[1]
        return QVariant()

    def set_buildings(self, buildings: List[Building]):
        """Update the buildings list."""
        self.beginResetModel()
        self._buildings = buildings
        self.endResetModel()

    def set_language(self, is_arabic: bool):
        """Update language setting."""
        self._is_arabic = is_arabic
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self._columns) - 1)
        # Refresh data
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1)
        )

    def get_building(self, row: int) -> Optional[Building]:
        """Get building at row."""
        if 0 <= row < len(self._buildings):
            return self._buildings[row]
        return None

    def get_all_buildings(self) -> List[Building]:
        """Get all buildings in the model."""
        return self._buildings


class UnitsTableModel(BaseTableModel):
    """Table model for property units list."""

    def __init__(self, units: List[PropertyUnit] = None, is_arabic: bool = False, parent=None):
        columns = [
            ("unit_number", "Unit #", "رقم الوحدة"),
            ("unit_type", "Type", "النوع"),
            ("floor_number", "Floor", "الطابق"),
            ("apartment_status", "Status", "الحالة"),
            ("area_sqm", "Area (m²)", "المساحة (م²)"),
        ]
        super().__init__(items=units or [], columns=columns)
        self._is_arabic = is_arabic

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Override to add UserRole support."""
        if role == Qt.UserRole:
            if not index.isValid() or index.row() >= len(self._items):
                return QVariant()
            return self._items[index.row()].unit_id
        return super().data(index, role)

    def get_item_value(self, item, field_name: str):
        """Extract field value from unit object."""
        if field_name == "unit_number":
            return item.unit_number
        elif field_name == "unit_type":
            return item.unit_type_display_ar if self._is_arabic else item.unit_type_display
        elif field_name == "floor_number":
            return item.floor_display
        elif field_name == "apartment_status":
            return item.status_display
        elif field_name == "area_sqm":
            return f"{item.area_sqm:.1f}" if item.area_sqm else "-"
        return ""

    def set_units(self, units: List[PropertyUnit]):
        """Update the units list."""
        self.set_items(units)


class PersonsTableModel(BaseTableModel):
    """Table model for persons list."""

    def __init__(self, persons: List[Person] = None, is_arabic: bool = False, parent=None):
        columns = [
            ("name", "Name", "الاسم"),
            ("national_id", "National ID", "الرقم الوطني"),
            ("gender", "Gender", "الجنس"),
            ("phone", "Phone", "الهاتف"),
        ]
        super().__init__(items=persons or [], columns=columns)
        self._is_arabic = is_arabic

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Override to add UserRole support."""
        if role == Qt.UserRole:
            if not index.isValid() or index.row() >= len(self._items):
                return QVariant()
            return self._items[index.row()].person_id
        return super().data(index, role)

    def get_item_value(self, item, field_name: str):
        """Extract field value from person object."""
        if field_name == "name":
            return item.full_name_ar if self._is_arabic else item.full_name
        elif field_name == "national_id":
            return item.national_id or "-"
        elif field_name == "gender":
            return item.gender_display_ar if self._is_arabic else item.gender_display
        elif field_name == "phone":
            return item.mobile_number or item.phone_number or "-"
        return ""

    def set_persons(self, persons: List[Person]):
        """Update the persons list."""
        self.set_items(persons)


class ImportRecordsTableModel(BaseTableModel):
    """Table model for import validation results."""

    def __init__(self, records=None, parent=None):
        columns = [
            ("record_id", "Record ID", "Record ID"),
            ("record_type", "Type", "Type"),
            ("status", "Status", "Status"),
            ("message", "Message", "Message"),
        ]
        super().__init__(items=records or [], columns=columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Override to add BackgroundRole and UserRole support."""
        if role == Qt.BackgroundRole:
            if not index.isValid() or index.row() >= len(self._items):
                return QVariant()
            record = self._items[index.row()]
            status = record.status.value
            colors = {
                "valid": QColor("#e8f5e9"),
                "warning": QColor("#fff8e1"),
                "error": QColor("#ffebee"),
                "duplicate": QColor("#e3f2fd"),
            }
            return QBrush(colors.get(status, QColor("#ffffff")))
        elif role == Qt.UserRole:
            if not index.isValid() or index.row() >= len(self._items):
                return QVariant()
            return self._items[index.row()].record_id
        return super().data(index, role)

    def get_item_value(self, item, field_name: str):
        """Extract field value from record object."""
        if field_name == "record_id":
            return item.record_id
        elif field_name == "record_type":
            return item.record_type.title()
        elif field_name == "status":
            return item.status.value.title()
        elif field_name == "message":
            if item.errors:
                return "; ".join(item.errors)
            elif item.warnings:
                return "; ".join(item.warnings)
            return "Valid"
        return ""

    def set_records(self, records):
        """Update the records list."""
        self.set_items(records)
