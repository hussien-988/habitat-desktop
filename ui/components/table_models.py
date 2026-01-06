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


class UnitsTableModel(QAbstractTableModel):
    """Table model for property units list."""

    def __init__(self, units: List[PropertyUnit] = None, is_arabic: bool = False, parent=None):
        super().__init__(parent)
        self._units = units or []
        self._is_arabic = is_arabic
        self._columns = [
            ("unit_number", "Unit #", "رقم الوحدة"),
            ("unit_type", "Type", "النوع"),
            ("floor_number", "Floor", "الطابق"),
            ("apartment_status", "Status", "الحالة"),
            ("area_sqm", "Area (m²)", "المساحة (م²)"),
        ]

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._units)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not self._units:
            return QVariant()

        unit = self._units[index.row()]
        column_key = self._columns[index.column()][0]

        if role == Qt.DisplayRole:
            if column_key == "unit_number":
                return unit.unit_number
            elif column_key == "unit_type":
                return unit.unit_type_display_ar if self._is_arabic else unit.unit_type_display
            elif column_key == "floor_number":
                return unit.floor_display
            elif column_key == "apartment_status":
                return unit.status_display
            elif column_key == "area_sqm":
                return f"{unit.area_sqm:.1f}" if unit.area_sqm else "-"

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        elif role == Qt.UserRole:
            return unit.unit_id

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            col = self._columns[section]
            return col[2] if self._is_arabic else col[1]
        return QVariant()

    def set_units(self, units: List[PropertyUnit]):
        """Update the units list."""
        self.beginResetModel()
        self._units = units
        self.endResetModel()


class PersonsTableModel(QAbstractTableModel):
    """Table model for persons list."""

    def __init__(self, persons: List[Person] = None, is_arabic: bool = False, parent=None):
        super().__init__(parent)
        self._persons = persons or []
        self._is_arabic = is_arabic
        self._columns = [
            ("name", "Name", "الاسم"),
            ("national_id", "National ID", "الرقم الوطني"),
            ("gender", "Gender", "الجنس"),
            ("phone", "Phone", "الهاتف"),
        ]

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._persons)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not self._persons:
            return QVariant()

        person = self._persons[index.row()]
        column_key = self._columns[index.column()][0]

        if role == Qt.DisplayRole:
            if column_key == "name":
                return person.full_name_ar if self._is_arabic else person.full_name
            elif column_key == "national_id":
                return person.national_id or "-"
            elif column_key == "gender":
                return person.gender_display_ar if self._is_arabic else person.gender_display
            elif column_key == "phone":
                return person.mobile_number or person.phone_number or "-"

        elif role == Qt.UserRole:
            return person.person_id

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            col = self._columns[section]
            return col[2] if self._is_arabic else col[1]
        return QVariant()

    def set_persons(self, persons: List[Person]):
        """Update the persons list."""
        self.beginResetModel()
        self._persons = persons
        self.endResetModel()


class ImportRecordsTableModel(QAbstractTableModel):
    """Table model for import validation results."""

    def __init__(self, records=None, parent=None):
        super().__init__(parent)
        self._records = records or []
        self._columns = [
            ("record_id", "Record ID"),
            ("record_type", "Type"),
            ("status", "Status"),
            ("message", "Message"),
        ]

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not self._records:
            return QVariant()

        record = self._records[index.row()]
        column_key = self._columns[index.column()][0]

        if role == Qt.DisplayRole:
            if column_key == "record_id":
                return record.record_id
            elif column_key == "record_type":
                return record.record_type.title()
            elif column_key == "status":
                return record.status.value.title()
            elif column_key == "message":
                if record.errors:
                    return "; ".join(record.errors)
                elif record.warnings:
                    return "; ".join(record.warnings)
                return "Valid"

        elif role == Qt.BackgroundRole:
            status = record.status.value
            colors = {
                "valid": QColor("#e8f5e9"),
                "warning": QColor("#fff8e1"),
                "error": QColor("#ffebee"),
                "duplicate": QColor("#e3f2fd"),
            }
            return QBrush(colors.get(status, QColor("#ffffff")))

        elif role == Qt.UserRole:
            return record.record_id

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._columns[section][1]
        return QVariant()

    def set_records(self, records):
        """Update the records list."""
        self.beginResetModel()
        self._records = records
        self.endResetModel()
