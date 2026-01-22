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

        cursor = self.db.cursor()
        cursor.execute(query, params)

        claims = []
        for row in cursor.fetchall():
            claims.append(Claim.from_row(row))

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
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT case_status, COUNT(*) as count
                FROM claims
                GROUP BY case_status
            """)

            result = {}
            for row in cursor.fetchall():
                result[row[0] or "unknown"] = row[1]

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
            required = ["unit_uuid"]
            for field in required:
                if not data.get(field):
                    errors.append(f"Missing required field: {field}")

        if errors:
            return OperationResult.fail(
                message="; ".join(errors),
                message_ar="أخطاء التحقق من البيانات",
                errors=errors
            )

        return OperationResult.ok()

    def _generate_case_number(self) -> str:
        """Generate unique case number."""
        cursor = self.db.cursor()
        cursor.execute("SELECT MAX(CAST(SUBSTR(case_number, 5) AS INTEGER)) FROM claims WHERE case_number LIKE 'CLM-%'")

        result = cursor.fetchone()
        next_num = (result[0] or 0) + 1 if result else 1

        return f"CLM-{str(next_num).zfill(6)}"
