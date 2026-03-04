# -*- coding: utf-8 -*-
"""
Claim Controller
================
Controller for claim management operations.

Handles:
- Claim read operations (load, get, delete)
- Claim workflow transitions
- Claim validation
- Claim search and filtering
- Claim statistics
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from models.claim import Claim
from services.api_client import get_api_client
from utils.logger import get_logger

logger = get_logger(__name__)

# Claim status string <-> API int mapping
_STATUS_STR_TO_INT = {
    "draft": 1, "submitted": 2, "under_review": 3,
    "verified": 4, "approved": 5, "rejected": 6, "archived": 7,
}
_STATUS_INT_TO_STR = {v: k for k, v in _STATUS_STR_TO_INT.items()}

_PRIORITY_STR_TO_INT = {"low": 1, "normal": 2, "high": 3, "urgent": 4}
_PRIORITY_INT_TO_STR = {v: k for k, v in _PRIORITY_STR_TO_INT.items()}


@dataclass
class ClaimFilter:
    """Filter criteria for claim search."""
    case_status: Optional[str] = None
    claim_type: Optional[str] = None
    building_uuid: Optional[str] = None
    unit_uuid: Optional[str] = None
    claimant_uuid: Optional[str] = None
    assigned_to: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search_text: Optional[str] = None
    neighborhood_code: Optional[str] = None
    limit: int = 100
    offset: int = 0


class ClaimController(BaseController):
    """
    Controller for claim management.

    Provides a clean interface between UI and data layer for claim operations.
    """

    # Signals
    claim_created = pyqtSignal(str)  # claim_uuid
    claim_updated = pyqtSignal(str)  # claim_uuid
    claim_deleted = pyqtSignal(str)  # claim_uuid
    claims_loaded = pyqtSignal(list)  # list of claims
    claim_selected = pyqtSignal(object)  # Claim object
    status_changed = pyqtSignal(str, str, str)  # claim_uuid, old_status, new_status

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self._api = get_api_client()

        self._current_claim: Optional[Claim] = None
        self._claims_cache: List[Claim] = []
        self._current_filter = ClaimFilter()

    # ==================== Properties ====================

    @property
    def current_claim(self) -> Optional[Claim]:
        """Get currently selected claim."""
        return self._current_claim

    @property
    def claims(self) -> List[Claim]:
        """Get cached claims list."""
        return self._claims_cache

    # ==================== CRUD Operations ====================

    def create_claim(self, data: Dict[str, Any]) -> OperationResult[Claim]:
        """
        Not supported directly - claims are created via Survey wizard.

        Returns:
            OperationResult failure
        """
        return OperationResult.fail(
            message="Claims are created via the Survey wizard, not directly",
            message_ar="يتم إنشاء المطالبات عبر معالج المسح"
        )

    def update_claim(self, claim_uuid: str, data: Dict[str, Any]) -> OperationResult[Claim]:
        """
        Not supported directly - no claim update API endpoint.

        Returns:
            OperationResult failure
        """
        return OperationResult.fail(
            message="Direct claim update is not supported via API",
            message_ar="تحديث المطالبة المباشر غير مدعوم عبر API"
        )

    def delete_claim(self, claim_uuid: str) -> OperationResult[bool]:
        """
        Delete a claim via API.

        Args:
            claim_uuid: UUID of claim to delete

        Returns:
            OperationResult with success status
        """
        self._log_operation("delete_claim", claim_uuid=claim_uuid)

        try:
            self._emit_started("delete_claim")

            # Fetch claim to verify status before delete
            try:
                dto = self._api.get_claim_by_id(claim_uuid)
                claim = self._api_dto_to_claim(dto)
                status_str = claim.case_status
                if status_str not in ["draft", "cancelled", "rejected"]:
                    return OperationResult.fail(
                        message="Only draft, cancelled, or rejected claims can be deleted",
                        message_ar="يمكن حذف المطالبات المسودة أو الملغاة أو المرفوضة فقط"
                    )
            except Exception:
                pass  # Proceed with delete even if pre-check fails

            self._api.delete_claim(claim_uuid)

            self._emit_completed("delete_claim", True)
            self.claim_deleted.emit(claim_uuid)
            self._trigger_callbacks("on_claim_deleted", claim_uuid)

            if self._current_claim and self._current_claim.claim_uuid == claim_uuid:
                self._current_claim = None

            return OperationResult.ok(
                data=True,
                message="Claim deleted successfully",
                message_ar="تم حذف المطالبة بنجاح"
            )

        except Exception as e:
            error_msg = f"Error deleting claim: {str(e)}"
            self._emit_error("delete_claim", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_claim(self, claim_uuid: str) -> OperationResult[Claim]:
        """
        Get a claim by UUID via API.

        Args:
            claim_uuid: UUID of claim

        Returns:
            OperationResult with Claim or error
        """
        try:
            dto = self._api.get_claim_by_id(claim_uuid)
            if dto:
                return OperationResult.ok(data=self._api_dto_to_claim(dto))
            return OperationResult.fail(
                message="Claim not found",
                message_ar="المطالبة غير موجودة"
            )
        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Selection ====================

    def select_claim(self, claim_uuid: str) -> OperationResult[Claim]:
        """
        Select a claim as current.

        Args:
            claim_uuid: UUID of claim to select

        Returns:
            OperationResult with selected Claim
        """
        result = self.get_claim(claim_uuid)

        if result.success:
            self._current_claim = result.data
            self.claim_selected.emit(result.data)
            self._trigger_callbacks("on_claim_selected", result.data)

        return result

    def clear_selection(self):
        """Clear current claim selection."""
        self._current_claim = None
        self.claim_selected.emit(None)

    # ==================== Search and Filter ====================

    def load_claims(self, filter_: Optional[ClaimFilter] = None) -> OperationResult[List[Claim]]:
        """
        Load claims with optional filter via API.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Claims
        """
        try:
            self._emit_started("load_claims")

            filter_ = filter_ or self._current_filter

            status_int = _STATUS_STR_TO_INT.get(filter_.case_status) if filter_.case_status else None

            dtos = self._api.get_claims(
                status=status_int,
                property_unit_id=filter_.unit_uuid,
                primary_claimant_id=filter_.claimant_uuid,
            )

            claims = [self._api_dto_to_claim(dto) for dto in dtos]

            # Apply local text filter if needed
            if filter_.search_text:
                search = filter_.search_text.lower()
                claims = [
                    c for c in claims
                    if search in (c.case_number or "").lower()
                    or search in (c.notes or "").lower()
                ]

            self._claims_cache = claims
            self._current_filter = filter_

            self._emit_completed("load_claims", True)
            self.claims_loaded.emit(claims)

            return OperationResult.ok(data=claims)

        except Exception as e:
            error_msg = f"Error loading claims: {str(e)}"
            self._emit_error("load_claims", error_msg)
            return OperationResult.fail(message=error_msg)

    def search_claims(self, search_text: str) -> OperationResult[List[Claim]]:
        """
        Search claims by text.

        Args:
            search_text: Text to search for

        Returns:
            OperationResult with list of matching Claims
        """
        filter_ = ClaimFilter(search_text=search_text)
        return self.load_claims(filter_)

    def filter_by_status(self, status: str) -> OperationResult[List[Claim]]:
        """
        Filter claims by status.

        Args:
            status: Status string to filter by

        Returns:
            OperationResult with list of Claims
        """
        filter_ = ClaimFilter(case_status=status)
        return self.load_claims(filter_)

    def get_claims_for_building(self, building_uuid: str) -> OperationResult[List[Claim]]:
        """
        Get claims for a specific building via API summaries.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult with list of Claims
        """
        try:
            summaries = self._api.get_claims_summaries()
            # Filter by building UUID if available in summary data
            filtered = [
                s for s in summaries
                if s.get("buildingId") == building_uuid or s.get("buildingCode") == building_uuid
            ]
            claims = [self._api_summary_to_claim(s) for s in filtered]
            return OperationResult.ok(data=claims)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_claims_for_unit(self, unit_uuid: str) -> OperationResult[List[Claim]]:
        """
        Get claims for a specific unit via API.

        Args:
            unit_uuid: Unit UUID

        Returns:
            OperationResult with list of Claims
        """
        filter_ = ClaimFilter(unit_uuid=unit_uuid)
        return self.load_claims(filter_)

    def _api_dto_to_claim(self, dto: Dict[str, Any]) -> Claim:
        """Convert API ClaimDto (camelCase) to Claim model."""
        raw_status = dto.get("status")
        case_status = _STATUS_INT_TO_STR.get(raw_status, str(raw_status or "draft"))

        raw_priority = dto.get("priority")
        priority = _PRIORITY_INT_TO_STR.get(raw_priority, str(raw_priority or "normal"))

        return Claim(
            claim_uuid=dto.get("id") or dto.get("claimId") or "",
            case_number=dto.get("claimNumber") or "",
            claim_type=str(dto.get("claimType") or "ownership"),
            case_status=case_status,
            priority=priority,
            unit_id=dto.get("propertyUnitId") or "",
            person_ids=dto.get("primaryClaimantId") or "",
            notes=dto.get("claimDescription") or dto.get("processingNotes") or "",
            source=str(dto.get("claimSource") or "OFFICE_SUBMISSION"),
            has_conflict=bool(dto.get("hasConflict") or dto.get("hasConflicts")),
            created_by=dto.get("createdByUserId") or "",
        )

    def _api_summary_to_claim(self, dto: Dict[str, Any]) -> Claim:
        """Convert API CreatedClaimSummaryDto to Claim model."""
        raw_status = dto.get("claimStatus") or dto.get("status")
        case_status = _STATUS_INT_TO_STR.get(raw_status, str(raw_status or "draft"))

        return Claim(
            claim_uuid=dto.get("claimId") or dto.get("id") or "",
            case_number=dto.get("claimNumber") or "",
            claim_type=str(dto.get("claimType") or ""),
            case_status=case_status,
        )

    # ==================== Workflow Operations ====================

    def submit_claim(self, claim_uuid: str) -> OperationResult[Claim]:
        """Submit a draft claim for review."""
        return OperationResult.fail(
            message="Claim workflow transitions require API endpoint not yet implemented",
            message_ar="انتقالات سير عمل المطالبة تتطلب endpoint API"
        )

    def approve_claim(self, claim_uuid: str, notes: str = "") -> OperationResult[Claim]:
        """Approve a claim."""
        return OperationResult.fail(
            message="Claim workflow transitions require API endpoint not yet implemented",
            message_ar="انتقالات سير عمل المطالبة تتطلب endpoint API"
        )

    def reject_claim(self, claim_uuid: str, reason: str) -> OperationResult[Claim]:
        """Reject a claim."""
        return OperationResult.fail(
            message="Claim workflow transitions require API endpoint not yet implemented",
            message_ar="انتقالات سير عمل المطالبة تتطلب endpoint API"
        )

    def request_review(self, claim_uuid: str) -> OperationResult[Claim]:
        """Request review for a claim."""
        return OperationResult.fail(
            message="Claim workflow transitions require API endpoint not yet implemented",
            message_ar="انتقالات سير عمل المطالبة تتطلب endpoint API"
        )

    def _can_change_status(self, from_status: str, to_status: str) -> bool:
        """Check if status transition is allowed."""
        allowed_transitions = {
            "draft": ["submitted", "cancelled"],
            "submitted": ["under_review", "draft", "cancelled"],
            "under_review": ["approved", "rejected", "pending"],
            "pending": ["under_review", "approved", "rejected"],
            "approved": [],
            "rejected": ["under_review"],
            "cancelled": []
        }
        return to_status in allowed_transitions.get(from_status, [])

    # ==================== Backend API Methods ====================

    def get_claim_full_context(self, claim_id: str) -> OperationResult:
        """
        Fetch full claim + building + unit + persons + households from API.

        Returns dict compatible with SurveyContext.from_dict().
        """
        try:
            claim = self._api.get_claim_by_id(claim_id)
            property_unit_id = claim.get("propertyUnitId")
            building_data = {}
            unit_data = {}
            households = []
            persons = []
            survey_id = None

            # Get survey_id from summaries (needed for households/relations)
            try:
                summaries = self._api.get_claims_summaries()
                for s in summaries:
                    if s.get("claimId") == claim_id:
                        survey_id = s.get("surveyId")
                        break
            except Exception as e:
                logger.warning(f"Failed to get survey_id: {e}")

            if property_unit_id:
                try:
                    unit_dto = self._api._request("GET", f"/v1/PropertyUnits/{property_unit_id}")
                    unit_data = self._map_unit_dto(unit_dto)
                    building_id = unit_dto.get("buildingId")
                    if building_id:
                        building_dto = self._api.get_building_by_id(building_id)
                        building_data = self._map_building_dto(building_dto)
                except Exception as e:
                    logger.warning(f"Failed to fetch building/unit: {e}")

            if survey_id:
                try:
                    raw_households = self._api._request("GET", f"/v1/Surveys/{survey_id}/households")
                    if isinstance(raw_households, list):
                        households = [self._map_household_dto(h) for h in raw_households]
                except Exception as e:
                    logger.warning(f"Failed to fetch households: {e}")

            if survey_id and property_unit_id:
                try:
                    relations = self._api._request(
                        "GET", "/v1/PersonPropertyRelations",
                        params={"surveyId": survey_id, "propertyUnitId": property_unit_id}
                    )
                    if isinstance(relations, list):
                        for rel in relations:
                            person_id = rel.get("personId")
                            if not person_id:
                                continue
                            try:
                                person_dto = self._api._request("GET", f"/v1/Persons/{person_id}")
                                persons.append(self._map_person_dto(person_dto, rel))
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"Failed to fetch persons: {e}")

            if not persons and claim.get("primaryClaimantName"):
                persons.append({
                    "first_name": claim["primaryClaimantName"],
                    "person_role": "claimant",
                })

            context = {
                "building": building_data,
                "unit": unit_data,
                "households": households,
                "persons": persons,
                "claim_data": self._map_claim_data(claim),
                "claims": [{
                    "claim_id": claim.get("claimNumber") or claim.get("id"),
                    "claim_type": claim.get("claimType"),
                    "status": claim.get("status"),
                }],
            }
            logger.info(f"Built full context for claim {claim_id}")
            return OperationResult.ok(data=context)

        except Exception as e:
            logger.error(f"Failed to get claim context: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    @staticmethod
    def _map_building_dto(dto: dict) -> dict:
        """Map API BuildingDto to Building-compatible dict format."""
        return {
            "building_id": dto.get("buildingCode") or dto.get("id", ""),
            "building_uuid": dto.get("id", ""),
            "governorate_name_ar": dto.get("governorateNameArabic", ""),
            "district_name_ar": dto.get("districtNameArabic", ""),
            "subdistrict_name_ar": dto.get("subDistrictNameArabic", ""),
            "community_name_ar": dto.get("communityNameArabic", ""),
            "neighborhood_name_ar": dto.get("neighborhoodNameArabic", ""),
            "building_number": dto.get("buildingNumber", ""),
            "building_type": dto.get("buildingType", 0),
            "building_status": dto.get("buildingStatus", 0),
            "number_of_floors": dto.get("numberOfFloors", 0),
            "number_of_units": dto.get("numberOfPropertyUnits", 0),
            "number_of_apartments": dto.get("numberOfApartments", 0),
            "number_of_shops": dto.get("numberOfShops", 0),
            "location_description": dto.get("locationDescription", ""),
            "general_description": dto.get("generalDescription", ""),
            "latitude": dto.get("latitude"),
            "longitude": dto.get("longitude"),
        }

    @staticmethod
    def _map_unit_dto(dto: dict) -> dict:
        """Map API PropertyUnitDto to Unit-compatible dict format."""
        return {
            "unit_id": dto.get("id", ""),
            "unit_uuid": dto.get("id", ""),
            "building_id": dto.get("buildingId", ""),
            "unit_number": dto.get("unitIdentifier") or dto.get("unitNumber", ""),
            "floor_number": dto.get("floorNumber", 0),
            "unit_type": dto.get("unitType", 0),
            "apartment_status": dto.get("status") or dto.get("unitStatus", 0),
            "apartment_number": str(dto.get("numberOfRooms", 0)),
            "area_sqm": dto.get("areaSquareMeters") or dto.get("areaSqm", 0),
            "property_description": dto.get("description", ""),
        }

    @staticmethod
    def _map_person_dto(person_dto: dict, relation_dto: dict) -> dict:
        """Map API PersonDto + RelationDto to person dict for SurveyContext."""
        return {
            "person_id": person_dto.get("id", ""),
            "first_name": person_dto.get("firstNameArabic", ""),
            "father_name": person_dto.get("fatherNameArabic", ""),
            "last_name": person_dto.get("familyNameArabic", ""),
            "full_name": person_dto.get("fullNameArabic", ""),
            "mother_name": person_dto.get("motherNameArabic", ""),
            "gender": person_dto.get("gender"),
            "date_of_birth": person_dto.get("dateOfBirth", ""),
            "national_id": person_dto.get("nationalId", ""),
            "nationality": person_dto.get("nationality"),
            "person_role": relation_dto.get("relationType", ""),
            "relationship_type": relation_dto.get("relationType", ""),
            "_relation_id": relation_dto.get("id", ""),
        }

    @staticmethod
    def _map_household_dto(dto: dict) -> dict:
        """Map API HouseholdDto to household dict for SurveyContext demographics."""
        return {
            "household_id": dto.get("id", ""),
            "size": dto.get("householdSize", 0),
            "adult_male": dto.get("maleCount", 0),
            "adult_female": dto.get("femaleCount", 0),
            "minor_male": dto.get("maleChildCount", 0),
            "minor_female": dto.get("femaleChildCount", 0),
            "elderly_male": dto.get("maleElderlyCount", 0),
            "elderly_female": dto.get("femaleElderlyCount", 0),
            "disabled_male": dto.get("maleDisabledCount", 0),
            "disabled_female": dto.get("femaleDisabledCount", 0),
            "occupancy_type": dto.get("occupancyType"),
            "occupancy_nature": dto.get("occupancyNature"),
            "notes": dto.get("notes", ""),
        }

    @staticmethod
    def _map_claim_data(claim: dict) -> dict:
        """Map API ClaimDto to claim_data dict for ReviewStep."""
        return {
            "claim_type": claim.get("claimType", ""),
            "priority": claim.get("priority"),
            "source": claim.get("claimSource"),
            "case_status": claim.get("status"),
            "person_name": claim.get("primaryClaimantName", ""),
            "unit_display_id": claim.get("propertyUnitCode", ""),
            "business_nature": claim.get("claimType", ""),
            "survey_date": (claim.get("createdAtUtc") or "")[:10],
            "notes": claim.get("claimDescription") or claim.get("processingNotes") or "",
            "next_action_date": (claim.get("targetCompletionDate") or "")[:10] if claim.get("targetCompletionDate") else "",
            "evidence_count": claim.get("evidenceCount", 0),
        }

    # ==================== Statistics ====================

    def get_statistics(self) -> OperationResult[Dict[str, Any]]:
        """
        Get claim statistics via API.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            summaries = self._api.get_claims_summaries()
            total = len(summaries)
            by_status: Dict[str, int] = {}
            for s in summaries:
                raw_status = s.get("claimStatus") or s.get("status")
                status_str = _STATUS_INT_TO_STR.get(raw_status, str(raw_status or "unknown"))
                by_status[status_str] = by_status.get(status_str, 0) + 1
            stats = {"total": total, "by_status": by_status}
            return OperationResult.ok(data=stats)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_claims_by_status(self) -> OperationResult[Dict[str, int]]:
        """
        Get claim count by status via API.

        Returns:
            OperationResult with status counts
        """
        try:
            summaries = self._api.get_claims_summaries()
            result: Dict[str, int] = {}
            for s in summaries:
                raw_status = s.get("claimStatus") or s.get("status")
                status_str = _STATUS_INT_TO_STR.get(raw_status, str(raw_status or "unknown"))
                result[status_str] = result.get(status_str, 0) + 1
            return OperationResult.ok(data=result)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Validation ====================

    def _validate_claim_data(
        self,
        data: Dict[str, Any],
        is_update: bool = False
    ) -> OperationResult:
        """Validate claim data."""
        errors = []

        if not is_update:
            if not data.get("unit_uuid") and not data.get("unit_id"):
                errors.append("Missing required field: unit_uuid or unit_id")

        if errors:
            return OperationResult.fail(
                message="; ".join(errors),
                message_ar="أخطاء التحقق من البيانات",
                errors=errors
            )

        return OperationResult.ok()
