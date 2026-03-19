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

    @property
    def current_claim(self) -> Optional[Claim]:
        """Get currently selected claim."""
        return self._current_claim

    @property
    def claims(self) -> List[Claim]:
        """Get cached claims list."""
        return self._claims_cache

    def create_claim(self, data: Dict[str, Any]) -> OperationResult[Claim]:
        
        return OperationResult.fail(
            message="Claims are created via the Survey wizard, not directly",
            message_ar="يتم إنشاء المطالبات عبر معالج المسح"
        )

    def update_claim(self, claim_id: str, update_data: Dict[str, Any],
                     reason: str = "") -> OperationResult:
        
        try:
            if reason:
                update_data["reasonForModification"] = reason
            result = self._api.update_claim(claim_id, update_data)
            self.claim_updated.emit(claim_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            error_msg = str(e)
            # Extract backend response details for API errors
            if hasattr(e, 'status_code'):
                error_msg = f"HTTP {e.status_code}: {error_msg}"
            if hasattr(e, 'response_data') and e.response_data:
                detail = e.response_data.get('detail') or e.response_data.get('title') or ''
                if detail:
                    error_msg = f"{error_msg} — {detail}"
            logger.error(f"Failed to update claim {claim_id}: {error_msg}", exc_info=True)
            return OperationResult.fail(message=error_msg)

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

    def select_claim(self, claim_uuid: str) -> OperationResult[Claim]:
        
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

    def load_claims(self, filter_: Optional[ClaimFilter] = None) -> OperationResult[List[Claim]]:
        
        
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

    def load_claims_from_api(self, status: int) -> OperationResult:
        """Load raw claim dicts from API filtered by numeric status."""
        try:
            from services.api_client import get_api_client
            dtos = get_api_client().get_claims_summaries(claim_status=status)
            return OperationResult.ok(data=dtos)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def search_claims(self, search_text: str) -> OperationResult[List[Claim]]:
        
        filter_ = ClaimFilter(search_text=search_text)
        return self.load_claims(filter_)

    def filter_by_status(self, status: str) -> OperationResult[List[Claim]]:
        
        filter_ = ClaimFilter(case_status=status)
        return self.load_claims(filter_)

    def get_claims_for_building(self, building_uuid: str) -> OperationResult[List[Claim]]:
        
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

    def submit_claim(self, claim_id: str, user_id: str) -> OperationResult:
        """Submit a claim for processing via PUT /api/Claims/{id}/submit."""
        try:
            result = self._api.submit_claim(claim_id, user_id)
            self.status_changed.emit(claim_id, "draft", "submitted")
            return OperationResult.ok(data=result)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def verify_claim(self, claim_id: str, user_id: str,
                     notes: str = "") -> OperationResult:
        """Verify a claim via PUT /api/Claims/{id}/verify."""
        try:
            result = self._api.verify_claim(claim_id, user_id, notes)
            return OperationResult.ok(data=result)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def assign_claim(self, claim_id: str, user_id: str,
                     target_date: Optional[str] = None) -> OperationResult:
        """Assign a claim via PUT /api/Claims/{id}/assign."""
        try:
            result = self._api.assign_claim(claim_id, user_id, target_date)
            return OperationResult.ok(data=result)
        except Exception as e:
            return OperationResult.fail(message=str(e))

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

    def search_claims_from_api(self, case_status: Optional[int] = None,
                               claim_source: Optional[int] = None,
                               building_code: Optional[str] = None,
                               page: int = 1, page_size: int = 20) -> OperationResult:
        
        try:
            dtos = self._api.get_claims_summaries(
                claim_status=case_status,
                claim_source=claim_source,
                building_code=building_code,
            )
            return OperationResult.ok(data=dtos if isinstance(dtos, list) else [])
        except Exception as e:
            logger.error(f"Failed to search claims: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def get_claim_full_detail(self, claim_id: str,
                              hint_survey_id: str = None,
                              hint_relation_id: str = None) -> OperationResult:
        
        try:
            claim_dto = self._api.get_claim_by_id(claim_id)
            if not claim_dto:
                return OperationResult.fail(message="Claim not found")

            result = {"claim": claim_dto}

            # Person enrichment
            primary_claimant_id = claim_dto.get("primaryClaimantId")
            if primary_claimant_id:
                try:
                    result["person"] = self._api._request(
                        "GET", f"/v1/Persons/{primary_claimant_id}")
                except Exception as e:
                    logger.warning(f"Failed to fetch person {primary_claimant_id}: {e}")

            # Unit enrichment
            unit_id = claim_dto.get("propertyUnitId")
            if unit_id:
                try:
                    result["unit"] = self._api._request(
                        "GET", f"/v1/PropertyUnits/{unit_id}")
                except Exception as e:
                    logger.warning(f"Failed to fetch unit {unit_id}: {e}")

                # Building from unit
                building_id = (result.get("unit") or {}).get("buildingId")
                if building_id:
                    try:
                        result["building"] = self._api.get_building_by_id(building_id)
                    except Exception as e:
                        logger.warning(f"Failed to fetch building {building_id}: {e}")

            # Survey ID — use hint from navigation context first
            survey_id = (hint_survey_id or
                         claim_dto.get("originatingSurveyId") or
                         claim_dto.get("surveyId") or claim_dto.get("SurveyId")
                         or claim_dto.get("survey_id"))
            result["survey_id"] = survey_id

            # Evidences — use evidenceIds from claim DTO + get_evidence_by_id()
            relation_id = hint_relation_id or claim_dto.get("sourceRelationId")
            evidence_ids = claim_dto.get("evidenceIds") or []
            if evidence_ids:
                evidences = []
                for eid in evidence_ids:
                    try:
                        ev = self._api.get_evidence_by_id(eid)
                        if ev:
                            evidences.append(ev)
                    except Exception as e:
                        logger.warning(f"Failed to fetch evidence {eid}: {e}")
                result["evidences"] = evidences

            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Failed to get claim detail {claim_id}: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def update_person(self, person_id: str,
                      person_data: Dict[str, Any]) -> OperationResult:
        """Update person via PUT /v1/Persons/{id}."""
        try:
            result = self._api.update_person(person_id, person_data)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Failed to update person {person_id}: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def update_property_unit(self, unit_id: str,
                             unit_data: Dict[str, Any]) -> OperationResult:
        """Update property unit via PUT /v1/PropertyUnits/{id}."""
        try:
            result = self._api.update_property_unit(unit_id, unit_data)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Failed to update unit {unit_id}: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def add_tenure_evidence(self, survey_id: str, relation_id: str,
                            file_path: str, **kwargs) -> OperationResult:
        """Add tenure evidence document."""
        try:
            result = self._api.upload_relation_document(
                survey_id, relation_id, file_path, **kwargs)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Failed to add tenure evidence: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def add_identification_evidence(self, survey_id: str, person_id: str,
                                    file_path: str, **kwargs) -> OperationResult:
        """Add identification evidence document."""
        try:
            result = self._api.upload_identification_document(
                survey_id, person_id, file_path, **kwargs)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Failed to add identification evidence: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def delete_evidence(self, survey_id: str,
                        evidence_id: str) -> OperationResult:
        """Delete evidence document."""
        try:
            self._api.delete_evidence(survey_id, evidence_id)
            return OperationResult.ok(data=True)
        except Exception as e:
            logger.error(f"Failed to delete evidence {evidence_id}: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    def get_claim_full_context(self, claim_id: str) -> OperationResult:
        
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
            "apartment_number": str(dto.get("numberOfRooms") or 0),
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
            "_is_contact_person": bool(person_dto.get("isContactPerson")),
            "_household_id": person_dto.get("householdId"),
        }

    @staticmethod
    def _map_household_dto(dto: dict) -> dict:
        """Map API HouseholdDto to household dict for SurveyContext demographics."""
        return {
            "household_id": dto.get("id", ""),
            "size": dto.get("householdSize", 0),
            "adult_males": dto.get("maleCount", 0),
            "adult_females": dto.get("femaleCount", 0),
            "male_children_under18": dto.get("maleChildCount", 0),
            "female_children_under18": dto.get("femaleChildCount", 0),
            "male_elderly_over65": dto.get("maleElderlyCount", 0),
            "female_elderly_over65": dto.get("femaleElderlyCount", 0),
            "disabled_males": dto.get("maleDisabledCount", 0),
            "disabled_females": dto.get("femaleDisabledCount", 0),
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
