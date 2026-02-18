# -*- coding: utf-8 -*-
"""
Workflow service for claim lifecycle management.
Implements UC-008: Claim Lifecycle Management
"""

from typing import List, Tuple, Optional
from datetime import datetime

from repositories.database import Database
from repositories.claim_repository import ClaimRepository
from models.claim import Claim
from utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowService:
    """Service for managing claim workflow and status transitions."""

    # Define valid status transitions
    # Format: current_status -> [(next_status, action_name_ar), ...]
    TRANSITIONS = {
        "draft": [
            ("submitted", "تقديم المطالبة"),
        ],
        "submitted": [
            ("screening", "بدء التدقيق الأولي"),
            ("draft", "إعادة إلى مسودة"),
        ],
        "screening": [
            ("under_review", "قبول للمراجعة"),
            ("awaiting_docs", "طلب وثائق إضافية"),
            ("rejected", "رفض"),
            ("draft", "إعادة إلى المقدم"),
        ],
        "under_review": [
            ("approved", "الموافقة"),
            ("rejected", "الرفض"),
            ("awaiting_docs", "طلب وثائق إضافية"),
            ("conflict", "وجود تعارض"),
        ],
        "awaiting_docs": [
            ("under_review", "استئناف المراجعة"),
            ("rejected", "رفض بسبب عدم تقديم الوثائق"),
        ],
        "conflict": [
            ("under_review", "حل التعارض"),
            ("rejected", "رفض"),
        ],
        "approved": [],  # Terminal state
        "rejected": [
            ("draft", "إعادة فتح كمسودة"),  # Allow reopening
        ],
    }

    def __init__(self, db: Database):
        self.db = db
        self.claim_repo = ClaimRepository(db)

    def get_available_transitions(self, current_status: str) -> List[Tuple[str, str]]:
        """
        Get available status transitions for a given status.

        Returns:
            List of (next_status, action_name) tuples
        """
        return self.TRANSITIONS.get(current_status, [])

    def can_transition(self, current_status: str, next_status: str) -> bool:
        """Check if a transition is valid."""
        transitions = self.get_available_transitions(current_status)
        return any(ns == next_status for ns, _ in transitions)

    def transition_claim(
        self,
        claim: Claim,
        next_status: str,
        notes: str = None,
        user_id: str = None
    ) -> Claim:
        """
        Transition a claim to a new status.

        Args:
            claim: The claim to transition
            next_status: Target status
            notes: Optional transition notes
            user_id: ID of user performing the transition

        Returns:
            Updated claim

        Raises:
            ValueError: If transition is not allowed
        """
        if not self.can_transition(claim.case_status, next_status):
            raise ValueError(
                f"Invalid transition from '{claim.case_status}' to '{next_status}'"
            )

        old_status = claim.case_status
        claim.case_status = next_status
        claim.lifecycle_stage = next_status
        claim.updated_at = datetime.now()

        if user_id:
            claim.updated_by = user_id

        if notes:
            existing = claim.notes or ""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            claim.notes = f"{existing}\n[{timestamp}] {old_status} -> {next_status}: {notes}".strip()

        # Handle specific transitions
        if next_status == "submitted" and not claim.submission_date:
            claim.submission_date = datetime.now().date()

        if next_status == "approved":
            claim.decision_date = datetime.now().date()

        if next_status == "rejected":
            claim.decision_date = datetime.now().date()

        if next_status == "awaiting_docs":
            claim.awaiting_documents = True
        else:
            claim.awaiting_documents = False

        # Update in database
        self.claim_repo.update(claim)

        logger.info(f"Claim {claim.claim_id} transitioned: {old_status} -> {next_status}")

        return claim

    def detect_conflicts(self, claim: Claim) -> List[Claim]:
        """
        Detect potential conflicts for a claim.

        Conflicts are other claims on the same property unit.

        Returns:
            List of conflicting claims
        """
        if not claim.unit_id:
            return []

        conflicts = self.claim_repo.find_by_unit(claim.unit_id)

        # Filter out the current claim and resolved claims
        conflicts = [
            c for c in conflicts
            if c.claim_id != claim.claim_id
            and c.case_status not in ("rejected", "draft")
        ]

        return conflicts

    def mark_conflict(self, claim: Claim, conflicting_claims: List[Claim]):
        """Mark a claim as having conflicts."""
        claim.has_conflict = True
        claim.conflict_claim_ids = ",".join(c.claim_id for c in conflicting_claims)
        claim.case_status = "conflict"
        claim.updated_at = datetime.now()

        self.claim_repo.update(claim)

        logger.info(f"Claim {claim.claim_id} marked with conflicts: {claim.conflict_claim_ids}")

    def resolve_conflict(self, claim: Claim, resolution_notes: str = None):
        """Resolve conflicts on a claim."""
        claim.has_conflict = False
        claim.conflict_claim_ids = ""
        claim.resolution_notes = resolution_notes
        claim.case_status = "under_review"
        claim.updated_at = datetime.now()

        self.claim_repo.update(claim)

        logger.info(f"Claim {claim.claim_id} conflicts resolved")

    def assign_claim(self, claim: Claim, user_id: str):
        """Assign a claim to a user for review."""
        claim.assigned_to = user_id
        claim.assigned_date = datetime.now().date()
        claim.updated_at = datetime.now()

        self.claim_repo.update(claim)

        logger.info(f"Claim {claim.claim_id} assigned to {user_id}")

    def get_claims_by_status(self, status: str, limit: int = 100) -> List[Claim]:
        """Get claims by status."""
        return self.claim_repo.search(status=status, limit=limit)

    def get_pending_review_claims(self, limit: int = 100) -> List[Claim]:
        """Get claims pending review."""
        return self.claim_repo.search(
            status="under_review",
            limit=limit
        )

    def get_claims_with_conflicts(self, limit: int = 100) -> List[Claim]:
        """Get claims with conflicts."""
        return self.claim_repo.search(
            has_conflict=True,
            limit=limit
        )

    def get_workflow_stats(self) -> dict:
        """Get workflow statistics."""
        stats = {}

        for status in self.TRANSITIONS.keys():
            claims = self.claim_repo.search(status=status, limit=10000)
            stats[status] = len(claims)

        # Additional stats
        conflicts = self.claim_repo.search(has_conflict=True, limit=10000)
        stats["with_conflicts"] = len(conflicts)

        return stats
