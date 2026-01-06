# -*- coding: utf-8 -*-
"""
Claim repository for database operations.
Implements UC-006: Update Existing Claim with audit trail.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
import uuid
import json

from models.claim import Claim
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class ClaimRepository:
    """Repository for Claim CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, claim: Claim) -> Claim:
        """Create a new claim record."""
        query = """
            INSERT INTO claims (
                claim_uuid, claim_id, case_number, source,
                person_ids, unit_id, relation_ids,
                case_status, lifecycle_stage, claim_type, priority,
                assigned_to, assigned_date, awaiting_documents,
                submission_date, decision_date,
                notes, resolution_notes,
                has_conflict, conflict_claim_ids,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            claim.claim_uuid, claim.claim_id, claim.case_number, claim.source,
            claim.person_ids, claim.unit_id, claim.relation_ids,
            claim.case_status, claim.lifecycle_stage, claim.claim_type, claim.priority,
            claim.assigned_to,
            claim.assigned_date.isoformat() if claim.assigned_date else None,
            1 if claim.awaiting_documents else 0,
            claim.submission_date.isoformat() if claim.submission_date else None,
            claim.decision_date.isoformat() if claim.decision_date else None,
            claim.notes, claim.resolution_notes,
            1 if claim.has_conflict else 0, claim.conflict_claim_ids,
            claim.created_at.isoformat() if claim.created_at else None,
            claim.updated_at.isoformat() if claim.updated_at else None,
            claim.created_by, claim.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created claim: {claim.claim_id}")
        return claim

    def get_by_id(self, claim_id: str) -> Optional[Claim]:
        """Get claim by claim_id."""
        query = "SELECT * FROM claims WHERE claim_id = ?"
        row = self.db.fetch_one(query, (claim_id,))
        if row:
            return self._row_to_claim(row)
        return None

    def get_by_uuid(self, claim_uuid: str) -> Optional[Claim]:
        """Get claim by UUID."""
        query = "SELECT * FROM claims WHERE claim_uuid = ?"
        row = self.db.fetch_one(query, (claim_uuid,))
        if row:
            return self._row_to_claim(row)
        return None

    def get_by_unit(self, unit_id: str) -> List[Claim]:
        """Get all claims for a unit."""
        query = "SELECT * FROM claims WHERE unit_id = ? ORDER BY created_at DESC"
        rows = self.db.fetch_all(query, (unit_id,))
        return [self._row_to_claim(row) for row in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Claim]:
        """Get all claims with pagination."""
        query = "SELECT * FROM claims ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_claim(row) for row in rows]

    def search(
        self,
        claim_id: Optional[str] = None,
        status: Optional[str] = None,
        claim_type: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        has_conflict: Optional[bool] = None,
        unit_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Claim]:
        """
        Search claims with filters.
        Implements UC-006 S01: Search for Existing Claim.
        """
        query = "SELECT * FROM claims WHERE 1=1"
        params = []

        if claim_id:
            query += " AND (claim_id LIKE ? OR case_number LIKE ?)"
            params.extend([f"%{claim_id}%", f"%{claim_id}%"])

        if status:
            query += " AND case_status = ?"
            params.append(status)

        if claim_type:
            query += " AND claim_type = ?"
            params.append(claim_type)

        if priority:
            query += " AND priority = ?"
            params.append(priority)

        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)

        if has_conflict is not None:
            query += " AND has_conflict = ?"
            params.append(1 if has_conflict else 0)

        if unit_id:
            query += " AND unit_id = ?"
            params.append(unit_id)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_claim(row) for row in rows]

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count claims with optional filters."""
        query = "SELECT COUNT(*) as count FROM claims WHERE 1=1"
        params = []

        if filters:
            if filters.get("status"):
                query += " AND case_status = ?"
                params.append(filters["status"])

        result = self.db.fetch_one(query, tuple(params))
        return result["count"] if result else 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get claim statistics for dashboard."""
        stats = {}

        # Total count
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM claims")
        stats["total"] = result["count"] if result else 0

        # Count by status
        rows = self.db.fetch_all("""
            SELECT case_status, COUNT(*) as count
            FROM claims
            GROUP BY case_status
        """)
        stats["by_status"] = {row["case_status"]: row["count"] for row in rows}

        # Pending review
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM claims
            WHERE case_status IN ('submitted', 'screening', 'under_review')
        """)
        stats["pending_review"] = result["count"] if result else 0

        # With conflicts
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM claims WHERE has_conflict = 1
        """)
        stats["with_conflicts"] = result["count"] if result else 0

        # Recent claims (last 7 days)
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM claims
            WHERE created_at >= date('now', '-7 days')
        """)
        stats["recent"] = result["count"] if result else 0

        return stats

    def update(self, claim: Claim) -> Claim:
        """Update an existing claim."""
        claim.updated_at = datetime.now()
        query = """
            UPDATE claims SET
                case_number = ?, source = ?,
                person_ids = ?, unit_id = ?, relation_ids = ?,
                case_status = ?, lifecycle_stage = ?, claim_type = ?, priority = ?,
                assigned_to = ?, assigned_date = ?, awaiting_documents = ?,
                submission_date = ?, decision_date = ?,
                notes = ?, resolution_notes = ?,
                has_conflict = ?, conflict_claim_ids = ?,
                updated_at = ?, updated_by = ?
            WHERE claim_uuid = ?
        """
        params = (
            claim.case_number, claim.source,
            claim.person_ids, claim.unit_id, claim.relation_ids,
            claim.case_status, claim.lifecycle_stage, claim.claim_type, claim.priority,
            claim.assigned_to,
            claim.assigned_date.isoformat() if claim.assigned_date else None,
            1 if claim.awaiting_documents else 0,
            claim.submission_date.isoformat() if claim.submission_date else None,
            claim.decision_date.isoformat() if claim.decision_date else None,
            claim.notes, claim.resolution_notes,
            1 if claim.has_conflict else 0, claim.conflict_claim_ids,
            claim.updated_at.isoformat(), claim.updated_by,
            claim.claim_uuid
        )
        self.db.execute(query, params)
        logger.debug(f"Updated claim: {claim.claim_id}")
        return claim

    def delete(self, claim_uuid: str) -> bool:
        """Delete a claim by UUID."""
        query = "DELETE FROM claims WHERE claim_uuid = ?"
        cursor = self.db.execute(query, (claim_uuid,))
        return cursor.rowcount > 0

    def save_history(self, claim: Claim, change_reason: str, user_id: str = None) -> str:
        """
        Save claim snapshot to history table for audit trail.
        Implements UC-006 S10: Save Updated Claim with Audit Trail.

        Args:
            claim: The claim to snapshot
            change_reason: Mandatory reason for the modification
            user_id: ID of user making the change

        Returns:
            history_id of the created record
        """
        history_id = str(uuid.uuid4())
        snapshot_data = json.dumps(claim.to_dict(), ensure_ascii=False, default=str)

        query = """
            INSERT INTO claim_history (
                history_id, claim_uuid, claim_id, snapshot_data,
                change_reason, changed_by, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            history_id,
            claim.claim_uuid,
            claim.claim_id,
            snapshot_data,
            change_reason,
            user_id,
            datetime.now().isoformat()
        )
        self.db.execute(query, params)
        logger.info(f"Saved history for claim {claim.claim_id}: {change_reason}")
        return history_id

    def get_history(self, claim_uuid: str) -> List[Dict[str, Any]]:
        """
        Get claim modification history.

        Returns:
            List of history entries with parsed snapshot data
        """
        query = """
            SELECT history_id, claim_id, snapshot_data, change_reason,
                   changed_by, changed_at
            FROM claim_history
            WHERE claim_uuid = ?
            ORDER BY changed_at DESC
        """
        rows = self.db.fetch_all(query, (claim_uuid,))

        history = []
        for row in rows:
            entry = dict(row)
            # Parse snapshot JSON
            if entry.get("snapshot_data"):
                try:
                    entry["snapshot"] = json.loads(entry["snapshot_data"])
                except json.JSONDecodeError:
                    entry["snapshot"] = {}
            del entry["snapshot_data"]
            history.append(entry)

        return history

    def update_with_history(
        self,
        claim: Claim,
        change_reason: str,
        user_id: str = None
    ) -> Claim:
        """
        Update claim and save previous version to history.
        Implements UC-006 complete update workflow.

        Args:
            claim: The claim with updated values
            change_reason: Mandatory reason for modification
            user_id: ID of user making the change

        Returns:
            Updated claim
        """
        # Get current version before update
        current = self.get_by_uuid(claim.claim_uuid)
        if current:
            # Save current version to history
            self.save_history(current, change_reason, user_id)

        # Now update with new values
        claim.updated_by = user_id
        return self.update(claim)

    def _row_to_claim(self, row) -> Claim:
        """Convert database row to Claim object."""
        data = dict(row)

        # Handle boolean fields
        data["awaiting_documents"] = bool(data.get("awaiting_documents", 0))
        data["has_conflict"] = bool(data.get("has_conflict", 0))

        # Handle date fields
        for field in ["assigned_date", "submission_date", "decision_date"]:
            if data.get(field):
                data[field] = date.fromisoformat(data[field])

        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return Claim(**{k: v for k, v in data.items() if k in Claim.__dataclass_fields__})
