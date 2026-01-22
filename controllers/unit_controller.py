# -*- coding: utf-8 -*-
"""
Unit Controller
===============
Controller for property unit management operations.

Handles:
- Unit CRUD operations
- Unit search and filtering
- Unit validation
- Unit-building relationships
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from models.unit import PropertyUnit
from repositories.unit_repository import UnitRepository
from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UnitFilter:
    """Filter criteria for unit search."""
    building_uuid: Optional[str] = None
    unit_type: Optional[str] = None
    occupancy_status: Optional[str] = None
    floor_number: Optional[int] = None
    has_claims: Optional[bool] = None
    search_text: Optional[str] = None
    limit: int = 100
    offset: int = 0


class UnitController(BaseController):
    """
    Controller for property unit management.

    Provides a clean interface between UI and data layer for unit operations.
    """

    # Signals
    unit_created = pyqtSignal(str)  # unit_uuid
    unit_updated = pyqtSignal(str)  # unit_uuid
    unit_deleted = pyqtSignal(str)  # unit_uuid
    units_loaded = pyqtSignal(list)  # list of units
    unit_selected = pyqtSignal(object)  # Unit object

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.repository = UnitRepository(db)

        self._current_unit: Optional[PropertyUnit] = None
        self._units_cache: List[PropertyUnit] = []
        self._current_filter = UnitFilter()

    # ==================== Properties ====================

    @property
    def current_unit(self) -> Optional[PropertyUnit]:
        """Get currently selected unit."""
        return self._current_unit

    @property
    def units(self) -> List[PropertyUnit]:
        """Get cached units list."""
        return self._units_cache

    # ==================== CRUD Operations ====================

    def create_unit(self, data: Dict[str, Any]) -> OperationResult[PropertyUnit]:
        """
        Create a new unit.

        Args:
            data: Unit data dictionary

        Returns:
            OperationResult with created Unit or error
        """
        self._log_operation("create_unit", data=data)

        try:
            self._emit_started("create_unit")

            # Validate data
            validation_result = self._validate_unit_data(data)
            if not validation_result.success:
                self._emit_error("create_unit", validation_result.message)
                return validation_result

            # Generate unit ID if not provided
            if not data.get("unit_id"):
                data["unit_id"] = self._generate_unit_id(data)

            # Create unit
            unit = Unit(**data)
            saved_unit = self.repository.create(unit)

            if saved_unit:
                self._emit_completed("create_unit", True)
                self.unit_created.emit(saved_unit.unit_uuid)
                self._trigger_callbacks("on_unit_created", saved_unit)
                return OperationResult.ok(
                    data=saved_unit,
                    message="Unit created successfully",
                    message_ar="تم إنشاء الوحدة بنجاح"
                )
            else:
                self._emit_error("create_unit", "Failed to create unit")
                return OperationResult.fail(
                    message="Failed to create unit",
                    message_ar="فشل في إنشاء الوحدة"
                )

        except Exception as e:
            error_msg = f"Error creating unit: {str(e)}"
            self._emit_error("create_unit", error_msg)
            return OperationResult.fail(message=error_msg)

    def update_unit(self, unit_uuid: str, data: Dict[str, Any]) -> OperationResult[PropertyUnit]:
        """
        Update an existing unit.

        Args:
            unit_uuid: UUID of unit to update
            data: Updated unit data

        Returns:
            OperationResult with updated Unit or error
        """
        self._log_operation("update_unit", unit_uuid=unit_uuid, data=data)

        try:
            self._emit_started("update_unit")

            # Get existing unit
            existing = self.repository.get_by_uuid(unit_uuid)
            if not existing:
                self._emit_error("update_unit", "Unit not found")
                return OperationResult.fail(
                    message="Unit not found",
                    message_ar="الوحدة غير موجودة"
                )

            # Validate data
            validation_result = self._validate_unit_data(data, is_update=True)
            if not validation_result.success:
                self._emit_error("update_unit", validation_result.message)
                return validation_result

            # Update unit
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            existing.updated_at = datetime.now()

            updated_unit = self.repository.update(existing)

            if updated_unit:
                self._emit_completed("update_unit", True)
                self.unit_updated.emit(unit_uuid)
                self._trigger_callbacks("on_unit_updated", updated_unit)

                # Update current unit if it's the one being edited
                if self._current_unit and self._current_unit.unit_uuid == unit_uuid:
                    self._current_unit = updated_unit

                return OperationResult.ok(
                    data=updated_unit,
                    message="Unit updated successfully",
                    message_ar="تم تحديث الوحدة بنجاح"
                )
            else:
                self._emit_error("update_unit", "Failed to update unit")
                return OperationResult.fail(
                    message="Failed to update unit",
                    message_ar="فشل في تحديث الوحدة"
                )

        except Exception as e:
            error_msg = f"Error updating unit: {str(e)}"
            self._emit_error("update_unit", error_msg)
            return OperationResult.fail(message=error_msg)

    def delete_unit(self, unit_uuid: str) -> OperationResult[bool]:
        """
        Delete a unit.

        Args:
            unit_uuid: UUID of unit to delete

        Returns:
            OperationResult with success status
        """
        self._log_operation("delete_unit", unit_uuid=unit_uuid)

        try:
            self._emit_started("delete_unit")

            # Check if unit exists
            existing = self.repository.get_by_uuid(unit_uuid)
            if not existing:
                self._emit_error("delete_unit", "Unit not found")
                return OperationResult.fail(
                    message="Unit not found",
                    message_ar="الوحدة غير موجودة"
                )

            # Check if unit has dependencies
            if self._has_dependencies(unit_uuid):
                return OperationResult.fail(
                    message="Cannot delete unit with active claims or relations",
                    message_ar="لا يمكن حذف وحدة لها مطالبات أو علاقات نشطة"
                )

            # Delete unit
            success = self.repository.delete(unit_uuid)

            if success:
                self._emit_completed("delete_unit", True)
                self.unit_deleted.emit(unit_uuid)
                self._trigger_callbacks("on_unit_deleted", unit_uuid)

                # Clear current unit if it was deleted
                if self._current_unit and self._current_unit.unit_uuid == unit_uuid:
                    self._current_unit = None

                return OperationResult.ok(
                    data=True,
                    message="Unit deleted successfully",
                    message_ar="تم حذف الوحدة بنجاح"
                )
            else:
                self._emit_error("delete_unit", "Failed to delete unit")
                return OperationResult.fail(
                    message="Failed to delete unit",
                    message_ar="فشل في حذف الوحدة"
                )

        except Exception as e:
            error_msg = f"Error deleting unit: {str(e)}"
            self._emit_error("delete_unit", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_unit(self, unit_uuid: str) -> OperationResult[PropertyUnit]:
        """
        Get a unit by UUID.

        Args:
            unit_uuid: UUID of unit

        Returns:
            OperationResult with Unit or error
        """
        try:
            unit = self.repository.get_by_uuid(unit_uuid)

            if unit:
                return OperationResult.ok(data=unit)
            else:
                return OperationResult.fail(
                    message="Unit not found",
                    message_ar="الوحدة غير موجودة"
                )

        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Selection ====================

    def select_unit(self, unit_uuid: str) -> OperationResult[PropertyUnit]:
        """
        Select a unit as current.

        Args:
            unit_uuid: UUID of unit to select

        Returns:
            OperationResult with selected Unit
        """
        result = self.get_unit(unit_uuid)

        if result.success:
            self._current_unit = result.data
            self.unit_selected.emit(result.data)
            self._trigger_callbacks("on_unit_selected", result.data)

        return result

    def clear_selection(self):
        """Clear current unit selection."""
        self._current_unit = None
        self.unit_selected.emit(None)

    # ==================== Search and Filter ====================

    def load_units(self, filter_: Optional[UnitFilter] = None) -> OperationResult[List[PropertyUnit]]:
        """
        Load units with optional filter.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Units
        """
        try:
            self._emit_started("load_units")

            filter_ = filter_ or self._current_filter

            # Build query based on filter
            units = self._query_units(filter_)

            self._units_cache = units
            self._current_filter = filter_

            self._emit_completed("load_units", True)
            self.units_loaded.emit(units)

            return OperationResult.ok(data=units)

        except Exception as e:
            error_msg = f"Error loading units: {str(e)}"
            self._emit_error("load_units", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_units_for_building(self, building_uuid: str) -> OperationResult[List[PropertyUnit]]:
        """
        Get units for a specific building.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult with list of Units
        """
        filter_ = UnitFilter(building_uuid=building_uuid)
        return self.load_units(filter_)

    def search_units(self, search_text: str) -> OperationResult[List[PropertyUnit]]:
        """
        Search units by text.

        Args:
            search_text: Text to search for

        Returns:
            OperationResult with list of matching Units
        """
        filter_ = UnitFilter(search_text=search_text)
        return self.load_units(filter_)

    def filter_by_type(self, unit_type: str) -> OperationResult[List[PropertyUnit]]:
        """
        Filter units by type.

        Args:
            unit_type: Unit type

        Returns:
            OperationResult with list of Units
        """
        filter_ = UnitFilter(unit_type=unit_type)
        return self.load_units(filter_)

    def _query_units(self, filter_: UnitFilter) -> List[PropertyUnit]:
        """Execute unit query with filter."""
        query = "SELECT * FROM property_units WHERE 1=1"
        params = []

        if filter_.building_uuid:
            # Convert building_uuid to building_id since table uses building_id
            building_result = self.db.fetch_one(
                "SELECT building_id FROM buildings WHERE building_uuid = ?",
                (filter_.building_uuid,)
            )
            if building_result:
                query += " AND building_id = ?"
                params.append(building_result['building_id'])
            else:
                # Building not found, return empty list
                return []

        if filter_.unit_type:
            query += " AND unit_type = ?"
            params.append(filter_.unit_type)

        if filter_.occupancy_status:
            query += " AND occupancy_status = ?"
            params.append(filter_.occupancy_status)

        if filter_.floor_number is not None:
            query += " AND floor_number = ?"
            params.append(filter_.floor_number)

        if filter_.has_claims is not None:
            if filter_.has_claims:
                query += " AND unit_uuid IN (SELECT DISTINCT unit_uuid FROM claims)"
            else:
                query += " AND unit_uuid NOT IN (SELECT DISTINCT unit_uuid FROM claims)"

        if filter_.search_text:
            query += " AND (unit_id LIKE ? OR notes LIKE ?)"
            search_param = f"%{filter_.search_text}%"
            params.extend([search_param, search_param])

        query += f" ORDER BY floor_number, unit_id LIMIT {filter_.limit} OFFSET {filter_.offset}"

        rows = self.db.fetch_all(query, tuple(params) if params else None)

        units = []
        for row in rows:
            units.append(self.repository._row_to_unit(row))

        return units

    # ==================== Validation ====================

    def _validate_unit_data(
        self,
        data: Dict[str, Any],
        is_update: bool = False
    ) -> OperationResult:
        """Validate unit data."""
        errors = []

        # Required fields for new units
        if not is_update:
            required = ["building_uuid"]
            for field in required:
                if not data.get(field):
                    errors.append(f"Missing required field: {field}")

            # Verify building exists
            if data.get("building_uuid"):
                result = self.db.fetch_one(
                    "SELECT COUNT(*) as count FROM buildings WHERE building_uuid = ?",
                    (data["building_uuid"],)
                )
                if not result or result['count'] == 0:
                    errors.append("Building not found")

        # Validate floor number
        if data.get("floor_number") is not None:
            floor = data["floor_number"]
            if not isinstance(floor, int) or floor < -10 or floor > 200:
                errors.append("Invalid floor number")

        # Validate unit area
        if data.get("unit_area") is not None:
            area = data["unit_area"]
            if area <= 0 or area > 10000:
                errors.append("Invalid unit area")

        if errors:
            return OperationResult.fail(
                message="; ".join(errors),
                message_ar="أخطاء التحقق من البيانات",
                errors=errors
            )

        return OperationResult.ok()

    def _generate_unit_id(self, data: Dict[str, Any]) -> str:
        """Generate unit ID based on building and sequence."""
        building_uuid = data.get("building_uuid")

        if not building_uuid:
            return ""

        # Get building ID
        result = self.db.fetch_one(
            "SELECT building_id FROM buildings WHERE building_uuid = ?",
            (building_uuid,)
        )
        building_id = result['building_id'] if result else "UNKNOWN"

        # Get next unit number for this building (using building_id)
        result = self.db.fetch_one("""
            SELECT COUNT(*) + 1 as next_num FROM property_units WHERE building_id = ?
        """, (building_id,))

        unit_num = result['next_num'] if result else 1

        # Format: BuildingID-UnitNum
        return f"{building_id}-U{str(unit_num).zfill(3)}"

    def _has_dependencies(self, unit_uuid: str) -> bool:
        """Check if unit has dependent records."""
        # Check for claims
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM claims WHERE unit_uuid = ?",
            (unit_uuid,)
        )
        if result and result['count'] > 0:
            return True

        # Check for relations
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM relations WHERE unit_uuid = ?",
            (unit_uuid,)
        )
        if result and result['count'] > 0:
            return True

        # Check for households
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM households WHERE unit_uuid = ?",
            (unit_uuid,)
        )
        if result and result['count'] > 0:
            return True

        return False

    # ==================== Statistics ====================

    def get_statistics(self) -> OperationResult[Dict[str, Any]]:
        """
        Get unit statistics.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            # Total count
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM property_units")
            total = result['count'] if result else 0

            # By type
            rows = self.db.fetch_all("""
                SELECT unit_type, COUNT(*) as count
                FROM property_units
                WHERE unit_type IS NOT NULL
                GROUP BY unit_type
            """)
            by_type = {row['unit_type']: row['count'] for row in rows}

            # By occupancy status
            rows = self.db.fetch_all("""
                SELECT occupancy_status, COUNT(*) as count
                FROM property_units
                WHERE occupancy_status IS NOT NULL
                GROUP BY occupancy_status
            """)
            by_occupancy = {row['occupancy_status']: row['count'] for row in rows}

            # Average area
            result = self.db.fetch_one("""
                SELECT AVG(unit_area) as avg_area FROM property_units WHERE unit_area > 0
            """)
            avg_area = result['avg_area'] if result and result['avg_area'] else 0

            stats = {
                "total": total,
                "by_type": by_type,
                "by_occupancy_status": by_occupancy,
                "average_area": round(avg_area, 2)
            }

            return OperationResult.ok(data=stats)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_units_count_for_building(self, building_uuid: str) -> int:
        """
        Get count of units for a building.

        Args:
            building_uuid: Building UUID

        Returns:
            Number of units
        """
        # Get building_id from building_uuid
        building_result = self.db.fetch_one(
            "SELECT building_id FROM buildings WHERE building_uuid = ?",
            (building_uuid,)
        )
        if not building_result:
            return 0

        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM property_units WHERE building_id = ?",
            (building_result['building_id'],)
        )
        return result['count'] if result else 0
