# -*- coding: utf-8 -*-
"""
Building Controller
===================
Controller for building management operations.

Handles:
- Building CRUD operations
- Building search and filtering
- Building validation
- Building statistics

Uses API backend for all data operations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from models.building import Building
from repositories.building_repository import BuildingRepository
from repositories.database import Database
from services.api_client import get_api_client
from services.validation_service import ValidationService
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BuildingFilter:
    """Filter criteria for building search."""
    neighborhood_code: Optional[str] = None
    building_type: Optional[str] = None
    building_status: Optional[str] = None
    search_text: Optional[str] = None
    has_coordinates: Optional[bool] = None
    has_claims: Optional[bool] = None
    assigned_to: Optional[str] = None
    limit: int = 100
    offset: int = 0


class BuildingController(BaseController):
    """
    Controller for building management.

    Provides a clean interface between UI and data layer for building operations.
    """

    # Signals
    building_created = pyqtSignal(str)  # building_uuid
    building_updated = pyqtSignal(str)  # building_uuid
    building_deleted = pyqtSignal(str)  # building_uuid
    buildings_loaded = pyqtSignal(list)  # list of buildings
    building_selected = pyqtSignal(object)  # Building object

    def __init__(self, db: Database = None, parent=None, **kwargs):
        super().__init__(parent)
        self.db = db

        # Repository kept for local-only helpers (unit sync, dependency checks)
        self.repository = BuildingRepository(db) if db else None

        # Always use API backend
        self._api_service = get_api_client()
        logger.info("BuildingController using API backend")

        self.validation_service = ValidationService()

        self._current_building: Optional[Building] = None
        self._buildings_cache: List[Building] = []
        self._current_filter = BuildingFilter()

    @classmethod
    def _get_neighborhood_name(cls, code: str) -> str:
        """Lookup neighborhood Arabic name by code via API."""
        if not code:
            return ""

        try:
            api = get_api_client()
            neighborhoods = api.get_neighborhoods()
            for n in neighborhoods:
                if n.get("neighborhoodCode") == code:
                    return n.get("nameArabic", code)
        except Exception as e:
            logger.debug(f"API neighborhood lookup failed: {e}")
            raise

        return code

    @classmethod
    def _resolve_admin_names(cls, gov_code: str, dist_code: str,
                              subdist_code: str, community_code: str = "") -> Dict[str, str]:
        """
        Resolve governorate/district/subdistrict/community names from codes.
        Uses DivisionsService (API-first with JSON fallback).
        """
        result = {
            "governorate_name_ar": "",
            "district_name_ar": "",
            "subdistrict_name_ar": "",
            "community_name_ar": ""
        }

        if not gov_code:
            return result

        try:
            from services.divisions_service import DivisionsService
            service = DivisionsService()

            _, name_ar = service.get_governorate_name(gov_code)
            result["governorate_name_ar"] = name_ar

            if dist_code:
                _, name_ar = service.get_district_name(gov_code, dist_code)
                result["district_name_ar"] = name_ar

            if dist_code and subdist_code:
                _, name_ar = service.get_subdistrict_name(gov_code, dist_code, subdist_code)
                result["subdistrict_name_ar"] = name_ar

            if dist_code and subdist_code and community_code:
                _, name_ar = service.get_community_name(gov_code, dist_code, subdist_code, community_code)
                result["community_name_ar"] = name_ar

        except Exception as e:
            logger.warning(f"Error resolving admin division names: {e}")

        return result

    # ==================== Properties ====================

    @property
    def current_building(self) -> Optional[Building]:
        """Get currently selected building."""
        return self._current_building

    @property
    def buildings(self) -> List[Building]:
        """Get cached buildings list."""
        return self._buildings_cache

    @property
    def is_using_api(self) -> bool:
        """Check if controller is using API backend."""
        return True

    def set_auth_token(self, token: str):
        """
        Set authentication token for API calls.

        Args:
            token: JWT/Bearer token
        """
        if self._api_service:
            self._api_service.set_access_token(token)

    # ==================== CRUD Operations ====================

    def create_building(self, data: Dict[str, Any]) -> OperationResult[Building]:
        """
        Create a new building.

        Args:
            data: Building data dictionary

        Returns:
            OperationResult with created Building or error
        """
        self._log_operation("create_building", data=data)

        try:
            self._emit_started("create_building")

            # Validate data
            validation_result = self._validate_building_data(data)
            if not validation_result.success:
                self._emit_error("create_building", validation_result.message)
                return validation_result

            # Generate building ID if not provided
            if not data.get("building_id"):
                data["building_id"] = self._generate_building_id(data)

            # Create building via API
            response = self._api_service.create_building(data)
            saved_building = self._api_dto_to_building(response)

            if saved_building:
                self._emit_completed("create_building", True)
                self.building_created.emit(saved_building.building_uuid)
                self._trigger_callbacks("on_building_created", saved_building)

                return OperationResult.ok(
                    data=saved_building,
                    message="Building created successfully",
                    message_ar="تم إنشاء المبنى بنجاح"
                )
            else:
                self._emit_error("create_building", "Failed to create building")
                return OperationResult.fail(
                    message="Failed to create building",
                    message_ar="فشل في إنشاء المبنى"
                )

        except Exception as e:
            error_msg = f"Error creating building: {str(e)}"
            self._emit_error("create_building", error_msg)
            return OperationResult.fail(message=error_msg)

    def update_building(self, building_uuid: str, data: Dict[str, Any]) -> OperationResult[Building]:
        """
        Update an existing building.

        Args:
            building_uuid: UUID of building to update
            data: Updated building data

        Returns:
            OperationResult with updated Building or error
        """
        self._log_operation("update_building", building_uuid=building_uuid, data=data)

        try:
            self._emit_started("update_building")

            # Get existing building via API
            response = self._api_service.get_building_by_id(building_uuid)
            existing = self._api_dto_to_building(response) if response else None

            if not existing:
                self._emit_error("update_building", "Building not found")
                return OperationResult.fail(
                    message="Building not found",
                    message_ar="المبنى غير موجود"
                )

            # Validate data
            validation_result = self._validate_building_data(data, is_update=True)
            if not validation_result.success:
                self._emit_error("update_building", validation_result.message)
                return validation_result

            # Update building via API
            merged_data = existing.to_dict()
            merged_data.update(data)
            response = self._api_service.update_building(building_uuid, merged_data)
            updated_building = self._api_dto_to_building(response)

            if updated_building:
                self._emit_completed("update_building", True)
                self.building_updated.emit(building_uuid)
                self._trigger_callbacks("on_building_updated", updated_building)

                # Update current building if it's the one being edited
                if self._current_building and self._current_building.building_uuid == building_uuid:
                    self._current_building = updated_building

                return OperationResult.ok(
                    data=updated_building,
                    message="Building updated successfully",
                    message_ar="تم تحديث المبنى بنجاح"
                )
            else:
                self._emit_error("update_building", "Failed to update building")
                return OperationResult.fail(
                    message="Failed to update building",
                    message_ar="فشل في تحديث المبنى"
                )

        except Exception as e:
            error_msg = f"Error updating building: {str(e)}"
            self._emit_error("update_building", error_msg)
            return OperationResult.fail(message=error_msg)

    def delete_building(self, building_uuid: str) -> OperationResult[bool]:
        """
        Delete a building.

        Args:
            building_uuid: UUID of building to delete

        Returns:
            OperationResult with success status
        """
        self._log_operation("delete_building", building_uuid=building_uuid)

        try:
            self._emit_started("delete_building")

            # Check if building exists via API
            existing = self._api_service.get_building_by_id(building_uuid)

            if not existing:
                self._emit_error("delete_building", "Building not found")
                return OperationResult.fail(
                    message="Building not found",
                    message_ar="المبنى غير موجود"
                )

            # Delete building via API
            success = self._api_service.delete_building(building_uuid)

            if success:
                self._emit_completed("delete_building", True)
                self.building_deleted.emit(building_uuid)
                self._trigger_callbacks("on_building_deleted", building_uuid)

                # Clear current building if it was deleted
                if self._current_building and self._current_building.building_uuid == building_uuid:
                    self._current_building = None

                return OperationResult.ok(
                    data=True,
                    message="Building deleted successfully",
                    message_ar="تم حذف المبنى بنجاح"
                )
            else:
                self._emit_error("delete_building", "Failed to delete building")
                return OperationResult.fail(
                    message="Failed to delete building",
                    message_ar="فشل في حذف المبنى"
                )

        except Exception as e:
            error_msg = f"Error deleting building: {str(e)}"
            self._emit_error("delete_building", error_msg)
            return OperationResult.fail(message=error_msg)

    def update_geometry(
        self,
        building_uuid: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        polygon_wkt: Optional[str] = None
    ) -> OperationResult[Building]:
        """
        Update building geometry (location and/or polygon footprint).

        Args:
            building_uuid: UUID of building to update
            latitude: GPS latitude coordinate (optional)
            longitude: GPS longitude coordinate (optional)
            polygon_wkt: WKT polygon string for building footprint (optional)

        Returns:
            OperationResult with updated Building or error
        """
        try:
            # Validate that at least one geometry field is provided
            if latitude is None and longitude is None and polygon_wkt is None:
                return OperationResult.fail(
                    message="At least one geometry field must be provided",
                    message_ar="يجب توفير حقل هندسي واحد على الأقل"
                )

            response = self._api_service.update_building_geometry(
                building_id=building_uuid,
                latitude=latitude,
                longitude=longitude,
                building_geometry_wkt=polygon_wkt
            )
            building = self._api_dto_to_building(response) if response else None

            if building:
                # Emit signals
                self.building_updated.emit(building)

                # Trigger callbacks
                if self._on_building_updated:
                    self._on_building_updated(building)

                return OperationResult.ok(
                    data=building,
                    message="Building geometry updated successfully",
                    message_ar="تم تحديث موقع المبنى بنجاح"
                )
            else:
                self._emit_error("update_geometry", "Failed to update building geometry")
                return OperationResult.fail(
                    message="Failed to update building geometry",
                    message_ar="فشل في تحديث موقع المبنى"
                )

        except Exception as e:
            error_msg = f"Error updating building geometry: {str(e)}"
            self._emit_error("update_geometry", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_building(self, building_uuid: str) -> OperationResult[Building]:
        """
        Get a building by UUID.

        Args:
            building_uuid: UUID of building

        Returns:
            OperationResult with Building or error
        """
        try:
            response = self._api_service.get_building_by_id(building_uuid)
            building = self._api_dto_to_building(response) if response else None

            if building:
                return OperationResult.ok(data=building)
            else:
                return OperationResult.fail(
                    message="Building not found",
                    message_ar="المبنى غير موجود"
                )

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_building_by_id(self, building_id: str) -> OperationResult[Building]:
        """
        Get a building by its 17-digit ID.

        Args:
            building_id: 17-digit building ID

        Returns:
            OperationResult with Building or error
        """
        try:
            response = self._api_service.get_building_by_id(building_id)
            building = self._api_dto_to_building(response) if response else None

            if building:
                return OperationResult.ok(data=building)
            else:
                return OperationResult.fail(
                    message="Building not found",
                    message_ar="المبنى غير موجود"
                )

        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Selection ====================

    def select_building(self, building_uuid: str) -> OperationResult[Building]:
        """
        Select a building as current.

        Args:
            building_uuid: UUID of building to select

        Returns:
            OperationResult with selected Building
        """
        result = self.get_building(building_uuid)

        if result.success:
            self._current_building = result.data
            self.building_selected.emit(result.data)
            self._trigger_callbacks("on_building_selected", result.data)

        return result

    def clear_selection(self):
        """Clear current building selection."""
        self._current_building = None
        self.building_selected.emit(None)

    # ==================== Search and Filter ====================

    def load_buildings(self, filter_: Optional[BuildingFilter] = None) -> OperationResult[List[Building]]:
        """
        Load buildings with optional filter.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Buildings
        """
        try:
            self._emit_started("load_buildings")

            filter_ = filter_ or self._current_filter

            # Load buildings via API
            response = self._api_service.get_buildings_for_assignment(
                page_size=filter_.limit if filter_ else 100
            )
            buildings = []
            for item in response.get("items", []):
                building = self._api_dto_to_building(item)
                buildings.append(building)

            self._buildings_cache = buildings
            self._current_filter = filter_

            self._emit_completed("load_buildings", True)
            self.buildings_loaded.emit(buildings)

            return OperationResult.ok(data=buildings)

        except Exception as e:
            error_msg = f"Error loading buildings: {str(e)}"
            self._emit_error("load_buildings", error_msg)
            return OperationResult.fail(message=error_msg)

    def search_buildings(self, search_text: str) -> OperationResult[List[Building]]:
        """
        Search buildings by text via API.

        Args:
            search_text: Text to search for (building ID)

        Returns:
            OperationResult with list of matching Buildings
        """
        try:
            self._emit_started("search_buildings")

            response = self._api_service.search_buildings(building_id=search_text, page_size=100)
            buildings = []
            for item in response.get("buildings", response.get("items", [])):
                building = self._api_dto_to_building(item)
                buildings.append(building)
            logger.info(f"Search found {len(buildings)} buildings for query: {search_text}")
            self._buildings_cache = buildings
            self._emit_completed("search_buildings", True)
            self.buildings_loaded.emit(buildings)
            return OperationResult.ok(data=buildings)

        except Exception as e:
            error_msg = f"Error searching buildings: {str(e)}"
            self._emit_error("search_buildings", error_msg)
            return OperationResult.fail(message=error_msg)

    def filter_by_neighborhood(self, neighborhood_code: str) -> OperationResult[List[Building]]:
        """
        Filter buildings by neighborhood.

        Args:
            neighborhood_code: Neighborhood code

        Returns:
            OperationResult with list of Buildings
        """
        filter_ = BuildingFilter(neighborhood_code=neighborhood_code)
        return self.load_buildings(filter_)

    def search_for_assignment(
        self,
        polygon_wkt: str,
        governorate_code: Optional[str] = None,
        subdistrict_code: Optional[str] = None,
        survey_status: Optional[str] = None,
        has_active_assignment: Optional[bool] = None
    ) -> OperationResult[List[Building]]:
        """
        البحث عن مباني للتعيين باستخدام Backend API (أفضل ممارسة).

        يستخدم BuildingAssignments API بدلاً من البحث المحلي - يقلل الحمل على قاعدة البيانات المحلية.

        Args:
            polygon_wkt: Polygon في صيغة WKT
            governorate_code: كود المحافظة (optional)
            subdistrict_code: كود المنطقة الفرعية (optional)
            survey_status: حالة المسح (optional) - not_surveyed, in_progress, completed
            has_active_assignment: فلتر حسب assignment (optional)

        Returns:
            OperationResult with list of Buildings from API
        """
        try:
            self._emit_started("search_for_assignment")

            # Call Backend API
            response = self._api_service.search_buildings_for_assignment(
                polygon_wkt=polygon_wkt,
                governorate_code=governorate_code,
                subdistrict_code=subdistrict_code,
                survey_status=survey_status,
                has_active_assignment=has_active_assignment,
                page=1,
                page_size=500  # Get more results
            )

            # Convert API response to Building objects
            buildings = []
            for item in response.get("buildings", response.get("items", [])):
                building = self._api_dto_to_building(item)
                buildings.append(building)

            logger.info(f"✅ Found {len(buildings)} buildings via API (total: {response.get('totalCount', 0)})")
            self._emit_completed("search_for_assignment", True)

            return OperationResult.ok(data=buildings)

        except Exception as e:
            error_msg = f"Error searching buildings for assignment: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._emit_error("search_for_assignment", error_msg)
            return OperationResult.fail(message=error_msg)

    def search_for_assignment_by_filters(
        self,
        governorate_code: Optional[str] = None,
        subdistrict_code: Optional[str] = None,
        survey_status: Optional[str] = None,
        has_active_assignment: Optional[bool] = None,
        page: int = 1,
        page_size: int = 100
    ) -> OperationResult[List[Building]]:
        """
        ✅ البحث عن مباني للتعيين باستخدام الفلاتر فقط (بدون polygon).

        أفضل ممارسة: يقلل الحمل على قاعدة البيانات المحلية بالبحث مباشرة في Backend.
        مثالي لـ Step 1 حيث يستخدم المستخدم الفلاتر بدون رسم polygon.

        Args:
            governorate_code: كود المحافظة (optional)
            subdistrict_code: كود المنطقة الفرعية (optional)
            survey_status: حالة المسح (optional) - not_surveyed, in_progress, completed
            has_active_assignment: فلتر حسب assignment (optional)
            page: رقم الصفحة
            page_size: عدد النتائج في الصفحة

        Returns:
            OperationResult with list of Buildings from API

        Example:
            # البحث عن مباني غير مُعيّنة في محافظة حلب
            result = controller.search_for_assignment_by_filters(
                governorate_code="01",
                has_active_assignment=False
            )
        """
        try:
            self._emit_started("search_for_assignment_by_filters")

            # Call Backend API with filters only (no polygon needed)
            response = self._api_service.get_buildings_for_assignment(
                governorate_code=governorate_code,
                subdistrict_code=subdistrict_code,
                survey_status=survey_status,
                has_active_assignment=has_active_assignment,
                page=page,
                page_size=page_size
            )

            # Convert API response to Building objects
            buildings = []
            for item in response.get("buildings", response.get("items", [])):
                building = self._api_dto_to_building(item)
                buildings.append(building)

            logger.info(f"✅ Found {len(buildings)} buildings via filter API (total: {response.get('totalCount', 0)})")
            self._emit_completed("search_for_assignment_by_filters", True)

            return OperationResult.ok(
                data=buildings,
                message=f"Found {len(buildings)} buildings",
                message_ar=f"تم العثور على {len(buildings)} مبنى"
            )

        except Exception as e:
            error_msg = f"Error searching buildings by filters: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._emit_error("search_for_assignment_by_filters", error_msg)
            return OperationResult.fail(message=error_msg)

    def _api_dto_to_building(self, dto: Dict[str, Any]) -> Building:
        """
        تحويل BuildingDto من API إلى Building object.

        Strategy: API names first → JSON fallback for missing names.
        """
        # Building ID & UUID
        building_id = dto.get("buildingCode") or dto.get("buildingId", "")
        building_uuid = dto.get("id") or dto.get("buildingUuid") or dto.get("BuildingUuid") or ""

        # Extract codes from API
        gov_code = dto.get("governorateCode", "")
        dist_code = dto.get("districtCode", "")
        subdist_code = dto.get("subDistrictCode") or dto.get("subdistrictCode", "")
        community_code = dto.get("communityCode", "")
        neighborhood_code = dto.get("neighborhoodCode", "")

        # Fallback: extract codes from building_id (17 digits: GG-DD-SS-CCC-NNN-BBBBB)
        if not gov_code and len(building_id) == 17 and building_id.isdigit():
            gov_code = building_id[0:2]
            dist_code = dist_code or building_id[2:4]
            subdist_code = subdist_code or building_id[4:6]
            community_code = community_code or building_id[6:9]
            neighborhood_code = neighborhood_code or building_id[9:12]

        # Try API name fields first
        gov_name = dto.get("governorateNameAr") or dto.get("governorateName", "")
        dist_name = dto.get("districtNameAr") or dto.get("districtName", "")
        subdist_name = dto.get("subDistrictNameAr") or dto.get("subDistrictName") or dto.get("subdistrictName", "")
        community_name = dto.get("communityNameAr") or dto.get("communityName", "")
        neighborhood_name = dto.get("neighborhoodName") or dto.get("neighborhoodNameAr") or dto.get("nameArabic") or ""
        neighborhood_name = neighborhood_name.strip() if neighborhood_name else ""

        # Resolve missing names from local JSON files
        if not gov_name or not dist_name or not subdist_name:
            resolved = self._resolve_admin_names(gov_code, dist_code, subdist_code, community_code)
            gov_name = gov_name or resolved["governorate_name_ar"]
            dist_name = dist_name or resolved["district_name_ar"]
            subdist_name = subdist_name or resolved["subdistrict_name_ar"]
            community_name = community_name or resolved["community_name_ar"]

        # Neighborhood name: API
        if not neighborhood_name and neighborhood_code:
            neighborhood_name = self._get_neighborhood_name(neighborhood_code)

        logger.debug(f"API DTO: building={building_id}, gov='{gov_name}', dist='{dist_name}', subdist='{subdist_name}', neighborhood='{neighborhood_name}'")

        return Building(
            building_uuid=building_uuid,
            building_id=building_id,
            building_id_formatted=dto.get("buildingIdFormatted", ""),
            governorate_code=gov_code,
            governorate_name=gov_name,
            governorate_name_ar=gov_name,
            district_code=dist_code,
            district_name=dist_name,
            district_name_ar=dist_name,
            subdistrict_code=subdist_code,
            subdistrict_name=subdist_name,
            subdistrict_name_ar=subdist_name,
            community_code=community_code,
            community_name=community_name,
            community_name_ar=community_name,
            neighborhood_code=neighborhood_code,
            neighborhood_name=neighborhood_name or neighborhood_code,
            neighborhood_name_ar=neighborhood_name,
            building_number=dto.get("buildingNumber", ""),
            building_type=dto.get("buildingType") or 1,
            building_status=dto.get("status") or dto.get("buildingStatus") or 1,
            number_of_units=dto.get("numberOfUnits") or dto.get("numberOfPropertyUnits", 0),
            number_of_apartments=dto.get("numberOfApartments", 0),
            number_of_shops=dto.get("numberOfShops", 0),
            number_of_floors=dto.get("numberOfFloors", 1),
            latitude=dto.get("latitude"),
            longitude=dto.get("longitude"),
            geo_location=dto.get("buildingGeometryWkt") or dto.get("geoLocation")
        )

    # ==================== Statistics ====================

    def get_statistics(self) -> OperationResult[Dict[str, Any]]:
        """
        Get building statistics.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            stats = self.repository.get_statistics()
            return OperationResult.ok(data=stats)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_buildings_by_neighborhood(self) -> OperationResult[Dict[str, int]]:
        """
        Get building count by neighborhood.

        Returns:
            OperationResult with neighborhood counts
        """
        try:
            rows = self.db.fetch_all("""
                SELECT neighborhood_code, COUNT(*) as count
                FROM buildings
                WHERE neighborhood_code IS NOT NULL
                GROUP BY neighborhood_code
                ORDER BY count DESC
            """)

            result = {}
            for row in rows:
                result[row['neighborhood_code']] = row['count']

            return OperationResult.ok(data=result)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Geometry Operations ====================

    def update_geometry(
        self,
        building_uuid: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        polygon_wkt: Optional[str] = None
    ) -> OperationResult[Building]:
        """
        Update building geometry.

        Args:
            building_uuid: Building UUID
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            polygon_wkt: WKT polygon string

        Returns:
            OperationResult with updated Building
        """
        data = {}

        if latitude is not None:
            data["latitude"] = latitude
        if longitude is not None:
            data["longitude"] = longitude
        if polygon_wkt is not None:
            data["geo_location"] = polygon_wkt

        return self.update_building(building_uuid, data)

    # ==================== Validation ====================

    def _validate_building_data(
        self,
        data: Dict[str, Any],
        is_update: bool = False
    ) -> OperationResult:
        """Validate building data."""
        errors = []

        # Required fields for new buildings
        if not is_update:
            required = ["neighborhood_code"]
            for field in required:
                if not data.get(field):
                    errors.append(f"Missing required field: {field}")

        # Validate building ID format if provided
        if data.get("building_id"):
            building_id = data["building_id"]
            if not self._validate_building_id_format(building_id):
                errors.append("Invalid building ID format")

        # Validate coordinates if provided
        if data.get("latitude") is not None:
            lat = data["latitude"]
            if not (-90 <= lat <= 90):
                errors.append("Invalid latitude value")

        if data.get("longitude") is not None:
            lng = data["longitude"]
            if not (-180 <= lng <= 180):
                errors.append("Invalid longitude value")

        if errors:
            return OperationResult.fail(
                message="; ".join(errors),
                message_ar="أخطاء التحقق من البيانات",
                errors=errors
            )

        return OperationResult.ok()

    def _validate_building_id_format(self, building_id: str) -> bool:
        """Validate building ID format (dashed or dashless 17-digit)."""
        import re
        # Dashed: GG-DD-SS-CCC-NNN-BBBBB (22 chars)
        pattern_dashed = r"^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}-\d{5}$"
        # Dashless: 17 digits
        pattern_plain = r"^\d{17}$"
        return bool(re.match(pattern_dashed, building_id) or re.match(pattern_plain, building_id))

    def _generate_building_id(self, data: Dict[str, Any]) -> str:
        """Generate 17-digit building ID from administrative codes (dashless)."""
        gov = data.get("governorate_code", "00")[:2].zfill(2)
        dist = data.get("district_code", "00")[:2].zfill(2)
        sub = data.get("subdistrict_code", "00")[:2].zfill(2)
        comm = data.get("community_code", "000")[:3].zfill(3)
        neigh = data.get("neighborhood_code", "000")[:3].zfill(3)

        # DB stores dashless 17-digit IDs: 12-char prefix + 5-digit building number
        prefix = f"{gov}{dist}{sub}{comm}{neigh}"

        result = self.db.fetch_one("""
            SELECT MAX(CAST(SUBSTR(building_id, 13, 5) AS INTEGER)) as max_num
            FROM buildings
            WHERE building_id LIKE ?
        """, (f"{prefix}%",))

        next_num = (result['max_num'] or 0) + 1 if result and result['max_num'] else 1
        building_num = str(next_num).zfill(5)

        return f"{prefix}{building_num}"

    def _auto_create_units(self, building: Building, data: dict):
        """Create unit records automatically based on building's unit counts."""
        if not self.db:
            return

        from repositories.unit_repository import UnitRepository
        from models.unit import PropertyUnit
        unit_repo = UnitRepository(self.db)

        residential = data.get("number_of_apartments", 0)
        non_residential = data.get("number_of_shops", 0)

        if residential + non_residential == 0:
            return

        unit_num = 1

        for _ in range(residential):
            unit = PropertyUnit(
                building_id=building.building_id,
                unit_type="apartment",
                unit_number=str(unit_num).zfill(3),
                apartment_status="unknown",
            )
            unit_repo.create(unit)
            unit_num += 1

        for _ in range(non_residential):
            unit = PropertyUnit(
                building_id=building.building_id,
                unit_type="shop",
                unit_number=str(unit_num).zfill(3),
                apartment_status="unknown",
            )
            unit_repo.create(unit)
            unit_num += 1

        total = residential + non_residential
        logger.info(f"Auto-created {total} units for building {building.building_id} ({residential} residential, {non_residential} non-residential)")

    def sync_building_unit_counts(self, building_id: str):
        """Update building's unit counts from actual unit records."""
        if not self.db:
            return

        residential = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM property_units WHERE building_id = ? AND unit_type = 'apartment'",
            (building_id,)
        )
        non_residential = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM property_units WHERE building_id = ? AND unit_type != 'apartment'",
            (building_id,)
        )

        res_count = residential["c"] if residential else 0
        non_res_count = non_residential["c"] if non_residential else 0
        total = res_count + non_res_count

        self.db.execute(
            """UPDATE buildings
               SET number_of_apartments = ?, number_of_shops = ?, number_of_units = ?, updated_at = ?
               WHERE building_id = ?""",
            (res_count, non_res_count, total, datetime.now().isoformat(), building_id)
        )
        logger.info(f"Synced building {building_id} unit counts: {res_count} residential, {non_res_count} non-residential, {total} total")

    def _unit_has_data(self, unit_id: str) -> bool:
        """Check if a unit has associated claims, relations, households, or surveys."""
        for table in ("claims", "person_unit_relations", "households", "surveys"):
            result = self.db.fetch_one(
                f"SELECT COUNT(*) as c FROM {table} WHERE unit_id = ?", (unit_id,))
            if result and result['c'] > 0:
                return True
        return False

    def _sync_units_on_edit(self, building: 'Building', new_apartments: int, new_shops: int):
        """Sync unit records when building unit counts change during edit."""
        if not self.db:
            return

        from repositories.unit_repository import UnitRepository
        unit_repo = UnitRepository(self.db)

        existing = unit_repo.get_by_building(building.building_id)
        current_apts = [u for u in existing if u.unit_type == "apartment"]
        current_shops = [u for u in existing if u.unit_type != "apartment"]

        self._adjust_unit_count(unit_repo, building, current_apts, new_apartments, "apartment")
        self._adjust_unit_count(unit_repo, building, current_shops, new_shops, "shop")

    def _adjust_unit_count(self, unit_repo, building: 'Building',
                           existing_of_type: list, desired: int, unit_type: str):
        """Add or remove unit records to match the desired count for a given type."""
        from models.unit import PropertyUnit
        current = len(existing_of_type)

        if desired > current:
            next_num = int(unit_repo.get_next_unit_number(building.building_id))
            for i in range(desired - current):
                unit = PropertyUnit(
                    building_id=building.building_id,
                    unit_type=unit_type,
                    unit_number=str(next_num + i).zfill(3),
                    apartment_status="unknown",
                )
                unit_repo.create(unit)
            logger.info(f"Created {desired - current} {unit_type} units for building {building.building_id}")

        elif desired < current:
            sorted_desc = sorted(existing_of_type, key=lambda u: u.unit_number, reverse=True)
            to_remove = current - desired
            removed = 0
            for unit in sorted_desc:
                if removed >= to_remove:
                    break
                if not self._unit_has_data(unit.unit_id):
                    unit_repo.delete(unit.unit_uuid)
                    removed += 1
            if removed > 0:
                logger.info(f"Deleted {removed} empty {unit_type} units for building {building.building_id}")
            if removed < to_remove:
                logger.warning(
                    f"Could only remove {removed}/{to_remove} {unit_type} units "
                    f"(remaining have associated data)")

    # ==================== Export ====================

    def export_buildings(
        self,
        format_: str = "csv",
        filter_: Optional[BuildingFilter] = None
    ) -> OperationResult[str]:
        """
        Export buildings to file.

        Args:
            format_: Export format (csv, excel, geojson)
            filter_: Optional filter

        Returns:
            OperationResult with file path
        """
        try:
            result = self.load_buildings(filter_ or BuildingFilter(limit=10000))
            buildings = result.data if result.success else []

            # Delegate to export service
            from services.export_service import ExportService
            export_service = ExportService(self.db)

            if format_ == "geojson":
                from services.map_service import MapService
                map_service = MapService(self.db)
                # Convert to GeoJSON format
                # Implementation would go here
                pass

            # Return path to exported file
            return OperationResult.ok(data="export_path")

        except Exception as e:
            return OperationResult.fail(message=str(e))
