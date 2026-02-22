# -*- coding: utf-8 -*-
"""
Claim Controller
================
Controller for claim management operations.

Handles:
- Claim CRUD operations
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
from repositories.claim_repository import ClaimRepository
from repositories.database import Database
from services.workflow_service import WorkflowService
from utils.logger import get_logger

logger = get_logger(__name__)


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

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.repository = ClaimRepository(db)
        self.workflow_service = WorkflowService(db)

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
        Create a new claim.

        Args:
            data: Claim data dictionary

        Returns:
            OperationResult with created Claim or error
        """
        self._log_operation("create_claim", data=data)

        try:
            self._emit_started("create_claim")

            # Validate data
            validation_result = self._validate_claim_data(data)
            if not validation_result.success:
                self._emit_error("create_claim", validation_result.message)
                return validation_result

            # Generate case number if not provided
            if not data.get("case_number"):
                data["case_number"] = self._generate_case_number()

            # Set initial status
            if not data.get("case_status"):
                data["case_status"] = "draft"

            # Normalize: Claim model uses unit_id, callers may pass unit_uuid
            if data.get("unit_uuid") and not data.get("unit_id"):
                data["unit_id"] = data.pop("unit_uuid")

            # Create claim
            claim = Claim(**data)
            saved_claim = self.repository.create(claim)

            if saved_claim:
                self._emit_completed("create_claim", True)
                self.claim_created.emit(saved_claim.claim_uuid)
                self._trigger_callbacks("on_claim_created", saved_claim)
                return OperationResult.ok(
                    data=saved_claim,
                    message="Claim created successfully",
                    message_ar="تم إنشاء المطالبة بنجاح"
                )
            else:
                self._emit_error("create_claim", "Failed to create claim")
                return OperationResult.fail(
                    message="Failed to create claim",
                    message_ar="فشل في إنشاء المطالبة"
                )

        except Exception as e:
            error_msg = f"Error creating claim: {str(e)}"
            self._emit_error("create_claim", error_msg)
            return OperationResult.fail(message=error_msg)

    def update_claim(self, claim_uuid: str, data: Dict[str, Any]) -> OperationResult[Claim]:
        """
        Update an existing claim.

        Args:
            claim_uuid: UUID of claim to update
            data: Updated claim data

        Returns:
            OperationResult with updated Claim or error
        """
        self._log_operation("update_claim", claim_uuid=claim_uuid, data=data)

        try:
            self._emit_started("update_claim")

            # Get existing claim
            existing = self.repository.get_by_uuid(claim_uuid)
            if not existing:
                self._emit_error("update_claim", "Claim not found")
                return OperationResult.fail(
                    message="Claim not found",
                    message_ar="المطالبة غير موجودة"
                )

            # Check if status change is allowed
            if data.get("case_status") and data["case_status"] != existing.case_status:
                if not self._can_change_status(existing.case_status, data["case_status"]):
                    return OperationResult.fail(
                        message=f"Cannot change status from {existing.case_status} to {data['case_status']}",
                        message_ar="لا يمكن تغيير الحالة"
                    )

            # Validate data
            validation_result = self._validate_claim_data(data, is_update=True)
            if not validation_result.success:
                self._emit_error("update_claim", validation_result.message)
                return validation_result

            # Update claim
            old_status = existing.case_status
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            existing.updated_at = datetime.now()

            updated_claim = self.repository.update(existing)

            if updated_claim:
                self._emit_completed("update_claim", True)
                self.claim_updated.emit(claim_uuid)

                # Emit status change signal if status changed
                if data.get("case_status") and data["case_status"] != old_status:
                    self.status_changed.emit(claim_uuid, old_status, data["case_status"])

                self._trigger_callbacks("on_claim_updated", updated_claim)

                # Update current claim if it's the one being edited
                if self._current_claim and self._current_claim.claim_uuid == claim_uuid:
                    self._current_claim = updated_claim

                return OperationResult.ok(
                    data=updated_claim,
                    message="Claim updated successfully",
                    message_ar="تم تحديث المطالبة بنجاح"
                )
            else:
                self._emit_error("update_claim", "Failed to update claim")
                return OperationResult.fail(
                    message="Failed to update claim",
                    message_ar="فشل في تحديث المطالبة"
                )

        except Exception as e:
            error_msg = f"Error updating claim: {str(e)}"
            self._emit_error("update_claim", error_msg)
            return OperationResult.fail(message=error_msg)

    def delete_claim(self, claim_uuid: str) -> OperationResult[bool]:
        """
        Delete a claim.

        Args:
            claim_uuid: UUID of claim to delete

        Returns:
            OperationResult with success status
        """
        self._log_operation("delete_claim", claim_uuid=claim_uuid)

        try:
            self._emit_started("delete_claim")

            # Get existing claim
            existing = self.repository.get_by_uuid(claim_uuid)
            if not existing:
                self._emit_error("delete_claim", "Claim not found")
                return OperationResult.fail(
                    message="Claim not found",
                    message_ar="المطالبة غير موجودة"
                )

            # Check if claim can be deleted (only drafts)
            if existing.case_status not in ["draft", "cancelled"]:
                return OperationResult.fail(
                    message="Only draft or cancelled claims can be deleted",
                    message_ar="يمكن حذف المطالبات المسودة أو الملغاة فقط"
                )

            # Delete claim
            success = self.repository.delete(claim_uuid)

            if success:
                self._emit_completed("delete_claim", True)
                self.claim_deleted.emit(claim_uuid)
                self._trigger_callbacks("on_claim_deleted", claim_uuid)

                # Clear current claim if it was deleted
                if self._current_claim and self._current_claim.claim_uuid == claim_uuid:
                    self._current_claim = None

                return OperationResult.ok(
                    data=True,
                    message="Claim deleted successfully",
                    message_ar="تم حذف المطالبة بنجاح"
                )
            else:
                self._emit_error("delete_claim", "Failed to delete claim")
                return OperationResult.fail(
                    message="Failed to delete claim",
                    message_ar="فشل في حذف المطالبة"
                )

        except Exception as e:
            error_msg = f"Error deleting claim: {str(e)}"
            self._emit_error("delete_claim", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_claim(self, claim_uuid: str) -> OperationResult[Claim]:
        """
        Get a claim by UUID.

        Args:
            claim_uuid: UUID of claim

        Returns:
            OperationResult with Claim or error
        """
        try:
            claim = self.repository.get_by_uuid(claim_uuid)

            if claim:
                return OperationResult.ok(data=claim)
            else:
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
        Load claims with optional filter.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Claims
        """
        try:
            self._emit_started("load_claims")

            filter_ = filter_ or self._current_filter

            # Build query based on filter
            claims = self._query_claims(filter_)

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
            status: Status to filter by

        Returns:
            OperationResult with list of Claims
        """
        filter_ = ClaimFilter(case_status=status)
        return self.load_claims(filter_)

    def get_claims_for_building(self, building_uuid: str) -> OperationResult[List[Claim]]:
        """
        Get claims for a specific building.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult with list of Claims
        """
        filter_ = ClaimFilter(building_uuid=building_uuid)
        return self.load_claims(filter_)

    def get_claims_for_unit(self, unit_uuid: str) -> OperationResult[List[Claim]]:
        """
        Get claims for a specific unit.

        Args:
            unit_uuid: Unit UUID

        Returns:
            OperationResult with list of Claims
        """
        filter_ = ClaimFilter(unit_uuid=unit_uuid)
        return self.load_claims(filter_)

    def _query_claims(self, filter_: ClaimFilter) -> List[Claim]:
        """Execute claim query with filter."""
        query = "SELECT * FROM claims WHERE 1=1"
        params = []

        if filter_.case_status:
            query += " AND case_status = ?"
            params.append(filter_.case_status)

        if filter_.claim_type:
            query += " AND claim_type = ?"
            params.append(filter_.claim_type)

        if filter_.building_uuid:
            # Join with buildings table to convert building_uuid to building_id
            query += " AND unit_uuid IN (SELECT u.unit_uuid FROM property_units u JOIN buildings b ON u.building_id = b.building_id WHERE b.building_uuid = ?)"
            params.append(filter_.building_uuid)

        if filter_.unit_uuid:
            query += " AND unit_uuid = ?"
            params.append(filter_.unit_uuid)

        if filter_.claimant_uuid:
            query += " AND claimant_uuid = ?"
            params.append(filter_.claimant_uuid)

        if filter_.assigned_to:
            query += " AND assigned_to = ?"
            params.append(filter_.assigned_to)

        if filter_.search_text:
            query += " AND (case_number LIKE ? OR notes LIKE ?)"
            search_param = f"%{filter_.search_text}%"
            params.extend([search_param, search_param])

        if filter_.date_from:
            query += " AND created_at >= ?"
            params.append(filter_.date_from.isoformat())

        if filter_.date_to:
            query += " AND created_at <= ?"
            params.append(filter_.date_to.isoformat())

        query += f" ORDER BY created_at DESC LIMIT {filter_.limit} OFFSET {filter_.offset}"

        rows = self.db.execute(query, tuple(params))
        claims = []
        for row in rows:
            row_dict = dict(row) if hasattr(row, 'keys') else row
            claims.append(Claim.from_dict(row_dict))

        return claims

    # ==================== Workflow Operations ====================

    def submit_claim(self, claim_uuid: str) -> OperationResult[Claim]:
        """
        Submit a draft claim for review.

        Args:
            claim_uuid: UUID of claim to submit

        Returns:
            OperationResult with updated Claim
        """
        return self._change_status(claim_uuid, "submitted", "draft")

    def approve_claim(self, claim_uuid: str, notes: str = "") -> OperationResult[Claim]:
        """
        Approve a claim.

        Args:
            claim_uuid: UUID of claim to approve
            notes: Optional approval notes

        Returns:
            OperationResult with updated Claim
        """
        data = {"case_status": "approved"}
        if notes:
            data["review_notes"] = notes
        return self.update_claim(claim_uuid, data)

    def reject_claim(self, claim_uuid: str, reason: str) -> OperationResult[Claim]:
        """
        Reject a claim.

        Args:
            claim_uuid: UUID of claim to reject
            reason: Rejection reason

        Returns:
            OperationResult with updated Claim
        """
        data = {
            "case_status": "rejected",
            "rejection_reason": reason
        }
        return self.update_claim(claim_uuid, data)

    def request_review(self, claim_uuid: str) -> OperationResult[Claim]:
        """
        Request review for a claim.

        Args:
            claim_uuid: UUID of claim

        Returns:
            OperationResult with updated Claim
        """
        return self._change_status(claim_uuid, "under_review", "submitted")

    def _change_status(
        self,
        claim_uuid: str,
        new_status: str,
        expected_current_status: Optional[str] = None
    ) -> OperationResult[Claim]:
        """Change claim status with validation."""
        claim_result = self.get_claim(claim_uuid)
        if not claim_result.success:
            return claim_result

        claim = claim_result.data

        if expected_current_status and claim.case_status != expected_current_status:
            return OperationResult.fail(
                message=f"Claim must be in '{expected_current_status}' status",
                message_ar="حالة المطالبة غير صحيحة"
            )

        return self.update_claim(claim_uuid, {"case_status": new_status})

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

    def load_claims_from_api(self, status: int = None) -> OperationResult:
        """
        Load claims summaries from backend API.

        Args:
            status: ClaimStatus enum or None for all

        Returns:
            OperationResult with list of CreatedClaimSummaryDto dicts
        """
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            summaries = api.get_claims_summaries(claim_status=status)
            logger.info(f"Loaded {len(summaries)} claim summaries from API (status={status})")
            return OperationResult.ok(data=summaries)
        except Exception as e:
            logger.warning(f"API load failed, falling back to local: {e}")
            return OperationResult.fail(message=str(e))

    def get_claim_full_context(self, claim_id: str) -> OperationResult:
        """
        Fetch full claim + building + unit + persons + households from API.

        Returns dict compatible with SurveyContext.from_dict().
        """
        try:
            from services.api_client import get_api_client
            api = get_api_client()

            claim = api.get_claim_by_id(claim_id)
            property_unit_id = claim.get("propertyUnitId")
            building_data = {}
            unit_data = {}
            households = []
            persons = []
            survey_id = None

            # Get survey_id from summaries (needed for households/relations)
            try:
                summaries = api.get_claims_summaries()
                for s in summaries:
                    if s.get("claimId") == claim_id:
                        survey_id = s.get("surveyId")
                        break
            except Exception as e:
                logger.warning(f"Failed to get survey_id: {e}")

            if property_unit_id:
                # Fetch unit directly by ID
                try:
                    unit_dto = api._request("GET", f"/v1/PropertyUnits/{property_unit_id}")
                    unit_data = self._map_unit_dto(unit_dto)
                    building_id = unit_dto.get("buildingId")
                    if building_id:
                        building_dto = api.get_building_by_id(building_id)
                        building_data = self._map_building_dto(building_dto)
                except Exception as e:
                    logger.warning(f"Failed to fetch building/unit: {e}")

            # Fetch households via survey endpoint (has demographics)
            if survey_id:
                try:
                    raw_households = api._request("GET", f"/v1/Surveys/{survey_id}/households")
                    if isinstance(raw_households, list):
                        households = [self._map_household_dto(h) for h in raw_households]
                except Exception as e:
                    logger.warning(f"Failed to fetch households: {e}")

            # Fetch persons via relations (includes role and relation_id)
            if survey_id and property_unit_id:
                try:
                    relations = api._request(
                        "GET", "/v1/PersonPropertyRelations",
                        params={"surveyId": survey_id, "propertyUnitId": property_unit_id}
                    )
                    if isinstance(relations, list):
                        for rel in relations:
                            person_id = rel.get("personId")
                            if not person_id:
                                continue
                            try:
                                person_dto = api._request("GET", f"/v1/Persons/{person_id}")
                                persons.append(self._map_person_dto(person_dto, rel))
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"Failed to fetch persons: {e}")

            # Fallback: at least include primary claimant
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
        Get claim statistics.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            stats = self.repository.get_statistics()
            return OperationResult.ok(data=stats)
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_claims_by_status(self) -> OperationResult[Dict[str, int]]:
        """
        Get claim count by status.

        Returns:
            OperationResult with status counts
        """
        try:
            rows = self.db.execute("""
                SELECT case_status, COUNT(*) as count
                FROM claims
                GROUP BY case_status
            """)
            result = {}
            for row in rows:
                status = row.get("case_status") if hasattr(row, 'get') else row[0]
                count = row.get("count") if hasattr(row, 'get') else row[1]
                result[status or "unknown"] = count

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

        # Required fields for new claims
        if not is_update:
            # Accept either unit_uuid or unit_id
            if not data.get("unit_uuid") and not data.get("unit_id"):
                errors.append("Missing required field: unit_uuid or unit_id")

        if errors:
            return OperationResult.fail(
                message="; ".join(errors),
                message_ar="أخطاء التحقق من البيانات",
                errors=errors
            )

        return OperationResult.ok()

    def _generate_case_number(self) -> str:
        """Generate unique case number."""
        rows = self.db.execute(
            "SELECT MAX(CAST(SUBSTR(case_number, 5) AS INTEGER)) as max_num FROM claims WHERE case_number LIKE 'CLM-%'"
        )
        max_num = None
        if rows:
            max_num = rows[0].get("max_num") if hasattr(rows[0], 'get') else rows[0][0]
        next_num = (max_num or 0) + 1
        return f"CLM-{str(next_num).zfill(6)}"
