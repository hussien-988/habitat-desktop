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

Uses API backend for data fetching.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from models.unit import PropertyUnit
from services.api_client import get_api_client
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
    Uses API backend for data fetching.
    """

    # Signals
    unit_created = pyqtSignal(str)  # unit_uuid
    unit_updated = pyqtSignal(str)  # unit_uuid
    unit_deleted = pyqtSignal(str)  # unit_uuid
    units_loaded = pyqtSignal(list)  # list of units
    unit_selected = pyqtSignal(object)  # Unit object

    def __init__(self, db=None, parent=None, use_api: bool = None):
        super().__init__(parent)
        self._api_service = get_api_client()
        logger.info("UnitController using API backend")

        self._current_unit: Optional[PropertyUnit] = None
        self._units_cache: List[PropertyUnit] = []
        self._current_filter = UnitFilter()

    def set_auth_token(self, token: str):
        """Set authentication token for API calls."""
        if self._api_service:
            self._api_service.set_access_token(token)
            logger.info("API token set for UnitController")

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

            # Create unit via API
            result_dto = self._api_service.create_property_unit(data)
            saved_unit = self._api_dto_to_unit(result_dto)

            self._emit_completed("create_unit", True)
            self.unit_created.emit(saved_unit.unit_uuid)
            self._trigger_callbacks("on_unit_created", saved_unit)
            return OperationResult.ok(
                data=saved_unit,
                message="Unit created successfully",
                message_ar="تم إنشاء الوحدة بنجاح"
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

            # Validate data
            validation_result = self._validate_unit_data(data, is_update=True)
            if not validation_result.success:
                self._emit_error("update_unit", validation_result.message)
                return validation_result

            # Update unit via API
            result_dto = self._api_service.update_property_unit(unit_uuid, data)
            updated_unit = self._api_dto_to_unit(result_dto)

            self._emit_completed("update_unit", True)
            self.unit_updated.emit(unit_uuid)
            self._trigger_callbacks("on_unit_updated", updated_unit)

            if self._current_unit and self._current_unit.unit_uuid == unit_uuid:
                self._current_unit = updated_unit

            return OperationResult.ok(
                data=updated_unit,
                message="Unit updated successfully",
                message_ar="تم تحديث الوحدة بنجاح"
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

            api_success = self._api_service.delete_property_unit(unit_uuid)
            if not api_success:
                self._emit_error("delete_unit", "API delete failed")
                return OperationResult.fail(
                    message="Failed to delete unit via API",
                    message_ar="فشل في حذف الوحدة"
                )

            self._emit_completed("delete_unit", True)
            self.unit_deleted.emit(unit_uuid)
            self._trigger_callbacks("on_unit_deleted", unit_uuid)

            if self._current_unit and self._current_unit.unit_uuid == unit_uuid:
                self._current_unit = None

            return OperationResult.ok(
                data=True,
                message="Unit deleted successfully",
                message_ar="تم حذف الوحدة بنجاح"
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
            dto = self._api_service.get_property_unit_by_id(unit_uuid)
            if dto:
                return OperationResult.ok(data=self._api_dto_to_unit(dto))
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
        Load units with optional filter via API.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Units
        """
        try:
            self._emit_started("load_units")

            filter_ = filter_ or self._current_filter

            if filter_.building_uuid:
                units_data = self._api_service.get_units_for_building(filter_.building_uuid)
            else:
                units_data = self._api_service.get_all_property_units(limit=filter_.limit)

            units = [self._api_dto_to_unit(dto) for dto in units_data]

            # Apply local text filter if needed
            if filter_.search_text:
                search = filter_.search_text.lower()
                units = [
                    u for u in units
                    if search in (u.unit_id or "").lower()
                    or search in (u.unit_number or "").lower()
                    or search in (u.property_description or "").lower()
                ]

            self._units_cache = units
            self._current_filter = filter_

            self._emit_completed("load_units", True)
            self.units_loaded.emit(units)

            return OperationResult.ok(data=units)

        except Exception as e:
            error_msg = f"Error loading units: {str(e)}"
            self._emit_error("load_units", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_units_grouped(
        self,
        building_id: Optional[str] = None,
        unit_type: Optional[int] = None,
        status: Optional[int] = None
    ) -> OperationResult[List[Dict[str, Any]]]:
        """
        Get units grouped by building from API.

        Returns:
            OperationResult with list of BuildingWithUnitsDto dicts:
            [{buildingId, buildingNumber, unitCount, propertyUnits: [PropertyUnitDto]}]
        """
        try:
            self._emit_started("get_units_grouped")
            response = self._api_service.get_units_grouped(building_id, unit_type, status)
            groups = response.get("groupedByBuilding", [])
            total_units = response.get("totalUnits", 0)
            total_buildings = response.get("totalBuildings", 0)
            logger.info(f"Loaded {total_units} units across {total_buildings} buildings")
            self._emit_completed("get_units_grouped", True)
            return OperationResult.ok(data=groups)
        except Exception as e:
            error_msg = f"Error loading grouped units: {str(e)}"
            self._emit_error("get_units_grouped", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_units_for_building(self, building_uuid: str) -> OperationResult[List[PropertyUnit]]:
        """
        Get units for a specific building.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult with list of Units
        """
        try:
            self._emit_started("get_units_for_building")

            units_data = self._api_service.get_units_for_building(building_uuid)
            units = [self._api_dto_to_unit(dto) for dto in units_data]
            self._units_cache = units
            self._emit_completed("get_units_for_building", True)
            self.units_loaded.emit(units)
            return OperationResult.ok(data=units)

        except Exception as e:
            error_msg = f"Error getting units for building: {str(e)}"
            self._emit_error("get_units_for_building", error_msg)
            return OperationResult.fail(message=error_msg)

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

    def _api_dto_to_unit(self, dto: dict) -> PropertyUnit:
        """Convert API DTO (camelCase dict) to PropertyUnit model object."""
        return PropertyUnit(
            unit_uuid=dto.get("id") or dto.get("unitUuid") or "",
            unit_id=dto.get("unitId") or "",
            building_id=dto.get("buildingId") or "",
            unit_type=dto.get("unitType") or "apartment",
            unit_number=dto.get("unitIdentifier") or dto.get("unitNumber") or "001",
            floor_number=dto.get("floorNumber") or 0,
            apartment_number=dto.get("apartmentNumber") or dto.get("unitIdentifier") or "",
            apartment_status=dto.get("status") or dto.get("apartmentStatus") or "occupied",
            property_description=dto.get("description") or dto.get("propertyDescription") or "",
            area_sqm=dto.get("areaSquareMeters") or dto.get("areaSqm"),
        )

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

    # ==================== Statistics ====================

    def get_statistics(self) -> OperationResult[Dict[str, Any]]:
        """
        Get unit statistics via API.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            response = self._api_service.get_units_grouped()
            stats = {
                "total": response.get("totalUnits", 0),
                "total_buildings": response.get("totalBuildings", 0),
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
        try:
            units_data = self._api_service.get_units_for_building(building_uuid)
            return len(units_data)
        except Exception:
            return 0
