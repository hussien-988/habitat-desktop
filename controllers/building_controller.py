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

Supports both API and local database backends based on Config.DATA_PROVIDER.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal

from app.config import Config
from controllers.base_controller import BaseController, OperationResult
from models.building import Building
from repositories.building_repository import BuildingRepository
from repositories.database import Database
from services.validation_service import ValidationService
from utils.logger import get_logger

logger = get_logger(__name__)

# Optional: API client for Backend search
try:
    from services.api_client import get_api_client
    API_CLIENT_AVAILABLE = True
except ImportError:
    API_CLIENT_AVAILABLE = False


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

    def __init__(self, db: Database = None, parent=None, use_api: bool = None):
        super().__init__(parent)
        self.db = db

        # Determine whether to use API or local database
        # Priority: explicit parameter > Config setting
        if use_api is not None:
            self._use_api = use_api
        else:
            # Check if DATA_PROVIDER is set to "http" in config
            self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

        # Initialize appropriate backend
        if self._use_api:
            self._api_service = get_api_client()
            self.repository = None
            logger.info("BuildingController using API backend")
        else:
            self.repository = BuildingRepository(db) if db else None
            self._api_service = None
            logger.info("BuildingController using local database backend")

        self.validation_service = ValidationService()

        self._current_building: Optional[Building] = None
        self._buildings_cache: List[Building] = []
        self._current_filter = BuildingFilter()

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
        return self._use_api

    def set_auth_token(self, token: str):
        """
        Set authentication token for API calls.

        Args:
            token: JWT/Bearer token
        """
        if self._api_service:
            self._api_service.set_access_token(token)

    def switch_to_api(self):
        """Switch to API backend."""
        if not self._use_api:
            self._api_service = get_api_client()
            self._use_api = True
            logger.info("BuildingController switched to API backend")

    def switch_to_local_db(self):
        """Switch to local database backend."""
        if self._use_api:
            if self.db:
                self.repository = BuildingRepository(self.db)
            self._use_api = False
            logger.info("BuildingController switched to local database backend")

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

            # Create building via API or local database
            if self._use_api and self._api_service:
                logger.info(f"🌐 Using API backend for building creation (Config.DATA_PROVIDER={Config.DATA_PROVIDER})")
                response = self._api_service.create_building(data)
                saved_building = self._api_dto_to_building(response)
            else:
                logger.info(f"💾 Using local DB for building creation (Config.DATA_PROVIDER={Config.DATA_PROVIDER})")
                building = Building(**data)
                saved_building = self.repository.create(building)

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

            # Get existing building
            if self._use_api and self._api_service:
                response = self._api_service.get_building_by_id(building_uuid)
                existing = self._api_dto_to_building(response) if response else None
            else:
                existing = self.repository.get_by_uuid(building_uuid)

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

            # Update building via API or local database
            if self._use_api and self._api_service:
                # Merge existing data with new data
                merged_data = existing.to_dict()
                merged_data.update(data)
                response = self._api_service.update_building(building_uuid, merged_data)
                updated_building = self._api_dto_to_building(response)
            else:
                # Update building locally
                for key, value in data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)

                existing.updated_at = datetime.now()
                updated_building = self.repository.update(existing)

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

            # Check if building exists
            if self._use_api and self._api_service:
                existing = self._api_service.get_building_by_id(building_uuid)
            else:
                existing = self.repository.get_by_uuid(building_uuid)

            if not existing:
                self._emit_error("delete_building", "Building not found")
                return OperationResult.fail(
                    message="Building not found",
                    message_ar="المبنى غير موجود"
                )

            # Check if building has dependencies (only for local database)
            if not self._use_api and self._has_dependencies(building_uuid):
                self._emit_error("delete_building", "Building has related records")
                return OperationResult.fail(
                    message="Cannot delete building with related claims or units",
                    message_ar="لا يمكن حذف مبنى له مطالبات أو وحدات مرتبطة"
                )

            # Delete building via API or local database
            if self._use_api and self._api_service:
                success = self._api_service.delete_building(building_uuid)
            else:
                success = self.repository.delete(building_uuid)

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

            if self._use_api and self._api_service:
                # Use API service
                response = self._api_service.update_building_geometry(
                    building_id=building_uuid,
                    latitude=latitude,
                    longitude=longitude,
                    building_geometry_wkt=polygon_wkt
                )
                building = self._api_dto_to_building(response) if response else None
            else:
                # Use local repository
                building = self.repository.update_geometry(
                    building_uuid=building_uuid,
                    latitude=latitude,
                    longitude=longitude,
                    polygon_wkt=polygon_wkt
                )

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
            if self._use_api and self._api_service:
                response = self._api_service.get_building_by_id(building_uuid)
                building = self._api_dto_to_building(response) if response else None
            else:
                building = self.repository.get_by_uuid(building_uuid)

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
            if self._use_api and self._api_service:
                response = self._api_service.get_building_by_id(building_id)
                building = self._api_dto_to_building(response) if response else None
            else:
                building = self.repository.get_by_building_id(building_id)

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

            # Use API or local database based on configuration
            if self._use_api and self._api_service:
                try:
                    # Use search_buildings API with pagination
                    response = self._api_service.search_buildings(
                        building_id=filter_.search_text if filter_ and filter_.search_text else None,
                        neighborhood_code=filter_.neighborhood_code if filter_ else None,
                        page_size=filter_.limit if filter_ else 100
                    )
                    # Convert API response to Building objects
                    buildings = []
                    for item in response.get("items", []):
                        building = self._api_dto_to_building(item)
                        buildings.append(building)
                except Exception as e:
                    logger.error(f"API search failed: {e}")
                    buildings = []
            else:
                # Build query based on filter
                buildings = self._query_buildings(filter_)

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
        Search buildings by text.

        When using API backend, calls POST /v1/Buildings/search with {"buildingId": "..."}
        When using local database, filters buildings by building_id or address.

        Args:
            search_text: Text to search for (building ID)

        Returns:
            OperationResult with list of matching Buildings
        """
        try:
            self._emit_started("search_buildings")

            if self._use_api and self._api_service:
                # Use dedicated search API endpoint
                logger.info(f"🌐 Using API backend for building search (Config.DATA_PROVIDER={Config.DATA_PROVIDER})")
                response = self._api_service.search_buildings(building_id=search_text, page_size=100)
                # Convert API response to Building objects
                buildings = []
                for item in response.get("items", []):
                    building = self._api_dto_to_building(item)
                    buildings.append(building)
                logger.info(f"Search found {len(buildings)} buildings for query: {search_text}")
                self._buildings_cache = buildings
                self._emit_completed("search_buildings", True)
                self.buildings_loaded.emit(buildings)
                return OperationResult.ok(data=buildings)
            else:
                # Use local database filter
                logger.info(f"💾 Using local DB for building search (Config.DATA_PROVIDER={Config.DATA_PROVIDER})")
                filter_ = BuildingFilter(search_text=search_text)
                return self.load_buildings(filter_)

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
            if not API_CLIENT_AVAILABLE:
                logger.warning("API client not available - falling back to local search")
                return OperationResult.fail(message="API client not available")

            self._emit_started("search_for_assignment")

            # Call Backend API
            api_client = get_api_client()
            response = api_client.search_buildings_for_assignment(
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
            for item in response.get("items", []):
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
            if not API_CLIENT_AVAILABLE:
                logger.warning("API client not available for filter-based search")
                return OperationResult.fail(
                    message="API client not available",
                    message_ar="عميل API غير متوفر"
                )

            self._emit_started("search_for_assignment_by_filters")

            # Call Backend API with filters only (no polygon needed!)
            api_client = get_api_client()
            response = api_client.get_buildings_for_assignment(
                governorate_code=governorate_code,
                subdistrict_code=subdistrict_code,
                survey_status=survey_status,
                has_active_assignment=has_active_assignment,
                page=page,
                page_size=page_size
            )

            # Convert API response to Building objects
            buildings = []
            for item in response.get("items", []):
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

        ✅ FIX: BuildingAssignments API uses 'buildingCode' not 'buildingId'!
        """
        # ✅ CRITICAL FIX: Try 'buildingCode' first (BuildingAssignments API), then 'buildingId'
        building_id = dto.get("buildingCode") or dto.get("buildingId", "")

        logger.debug(f"API DTO building_id: {building_id} (from buildingCode={dto.get('buildingCode')}, buildingId={dto.get('buildingId')})")

        return Building(
            building_uuid=dto.get("buildingUuid", ""),
            building_id=building_id,
            building_id_formatted=dto.get("buildingIdFormatted", ""),
            governorate_code=dto.get("governorateCode", ""),
            governorate_name=dto.get("governorateName", ""),
            governorate_name_ar=dto.get("governorateNameAr", ""),
            district_code=dto.get("districtCode", ""),
            district_name=dto.get("districtName", ""),
            district_name_ar=dto.get("districtNameAr", ""),
            subdistrict_code=dto.get("subdistrictCode", ""),
            subdistrict_name=dto.get("subdistrictName", ""),
            subdistrict_name_ar=dto.get("subdistrictNameAr", ""),
            community_code=dto.get("communityCode", ""),
            community_name=dto.get("communityName", ""),
            community_name_ar=dto.get("communityNameAr", ""),
            neighborhood_code=dto.get("neighborhoodCode", ""),
            neighborhood_name=dto.get("neighborhoodName", ""),
            neighborhood_name_ar=dto.get("neighborhoodNameAr", ""),
            building_number=dto.get("buildingNumber", ""),
            building_type=dto.get("buildingType", 1),
            building_status=dto.get("buildingStatus", 1),
            number_of_units=dto.get("numberOfUnits", 0),
            number_of_apartments=dto.get("numberOfApartments", 0),
            number_of_shops=dto.get("numberOfShops", 0),
            number_of_floors=dto.get("numberOfFloors", 1),
            latitude=dto.get("latitude"),
            longitude=dto.get("longitude"),
            geo_location=dto.get("geoLocation")
        )

    def _query_buildings(self, filter_: BuildingFilter) -> List[Building]:
        """Execute building query with filter."""
        query = "SELECT * FROM buildings WHERE 1=1"
        params = []

        if filter_.neighborhood_code:
            query += " AND neighborhood_code = ?"
            params.append(filter_.neighborhood_code)

        if filter_.building_type:
            query += " AND building_type = ?"
            params.append(filter_.building_type)

        if filter_.building_status:
            query += " AND building_status = ?"
            params.append(filter_.building_status)

        if filter_.search_text:
            # Search in building_id, address, AND neighborhood names (Best Practice)
            query += " AND (building_id LIKE ? OR address LIKE ? OR neighborhood_name_ar LIKE ? OR neighborhood_name LIKE ?)"
            search_param = f"%{filter_.search_text}%"
            params.extend([search_param, search_param, search_param, search_param])

        if filter_.has_coordinates is not None:
            if filter_.has_coordinates:
                query += " AND latitude IS NOT NULL AND longitude IS NOT NULL"
            else:
                query += " AND (latitude IS NULL OR longitude IS NULL)"

        if filter_.assigned_to:
            query += """ AND building_uuid IN (
                SELECT building_uuid FROM field_assignments WHERE assigned_to = ?
            )"""
            params.append(filter_.assigned_to)

        query += f" ORDER BY created_at DESC LIMIT {filter_.limit} OFFSET {filter_.offset}"

        # استخدام fetch_all من Database بدلاً من cursor مباشرة
        rows = self.db.fetch_all(query, tuple(params) if params else None)

        buildings = []
        for row in rows:
            buildings.append(self.repository._row_to_building(row))

        return buildings

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
        """Validate 17-digit building ID format."""
        # Format: GG-DD-SS-CCC-NNN-BBBBB
        import re
        pattern = r"^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}-\d{5}$"
        return bool(re.match(pattern, building_id))

    def _generate_building_id(self, data: Dict[str, Any]) -> str:
        """Generate 17-digit building ID from administrative codes."""
        gov = data.get("governorate_code", "00")[:2].zfill(2)
        dist = data.get("district_code", "00")[:2].zfill(2)
        sub = data.get("subdistrict_code", "00")[:2].zfill(2)
        comm = data.get("community_code", "000")[:3].zfill(3)
        neigh = data.get("neighborhood_code", "000")[:3].zfill(3)

        # Get next building number
        result = self.db.fetch_one("""
            SELECT MAX(CAST(SUBSTR(building_id, 18, 5) AS INTEGER)) as max_num
            FROM buildings
            WHERE building_id LIKE ?
        """, (f"{gov}-{dist}-{sub}-{comm}-{neigh}-%",))

        next_num = (result['max_num'] or 0) + 1 if result and result['max_num'] else 1
        building_num = str(next_num).zfill(5)

        return f"{gov}-{dist}-{sub}-{comm}-{neigh}-{building_num}"

    def _has_dependencies(self, building_uuid: str) -> bool:
        """Check if building has dependent records."""
        # Get building_id from building_uuid
        building_result = self.db.fetch_one(
            "SELECT building_id FROM buildings WHERE building_uuid = ?",
            (building_uuid,)
        )
        if not building_result:
            return False

        # Check for units
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM property_units WHERE building_id = ?",
            (building_result['building_id'],)
        )
        if result and result['count'] > 0:
            return True

        return False

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
            buildings = self._query_buildings(filter_ or BuildingFilter(limit=10000))

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
