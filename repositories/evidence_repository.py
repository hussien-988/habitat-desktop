# -*- coding: utf-8 -*-
"""
Evidence repository for database operations.
"""

from typing import List, Optional
from datetime import datetime, date

from models.evidence import Evidence
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class EvidenceRepository:
    """Repository for Evidence CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, evidence: Evidence) -> Evidence:
        """Create a new evidence record."""
        query = """
            INSERT INTO evidence (
                evidence_id, relation_id, document_id,
                reference_number, reference_date, evidence_description,
                evidence_type, verification_status, verification_notes,
                verified_by, verification_date,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            evidence.evidence_id, evidence.relation_id, evidence.document_id,
            evidence.reference_number,
            evidence.reference_date.isoformat() if evidence.reference_date else None,
            evidence.evidence_description, evidence.evidence_type,
            evidence.verification_status, evidence.verification_notes,
            evidence.verified_by,
            evidence.verification_date.isoformat() if evidence.verification_date else None,
            evidence.created_at.isoformat() if evidence.created_at else None,
            evidence.updated_at.isoformat() if evidence.updated_at else None,
            evidence.created_by, evidence.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created evidence: {evidence.evidence_id}")
        return evidence

    def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        """Get evidence by ID."""
        query = "SELECT * FROM evidence WHERE evidence_id = ?"
        row = self.db.fetch_one(query, (evidence_id,))
        if row:
            return self._row_to_evidence(row)
        return None

    def get_by_relation(self, relation_id: str) -> List[Evidence]:
        """Get all evidence for a relation."""
        query = "SELECT * FROM evidence WHERE relation_id = ? ORDER BY created_at DESC"
        rows = self.db.fetch_all(query, (relation_id,))
        return [self._row_to_evidence(row) for row in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Evidence]:
        """Get all evidence with pagination."""
        query = "SELECT * FROM evidence ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_evidence(row) for row in rows]

    def search(self, relation_id: str = None, evidence_type: str = None,
               verification_status: str = None, limit: int = 100) -> List[Evidence]:
        """Search evidence with filters."""
        query = "SELECT * FROM evidence WHERE 1=1"
        params = []

        if relation_id:
            query += " AND relation_id = ?"
            params.append(relation_id)

        if evidence_type:
            query += " AND evidence_type = ?"
            params.append(evidence_type)

        if verification_status:
            query += " AND verification_status = ?"
            params.append(verification_status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_evidence(row) for row in rows]

    def count(self) -> int:
        """Count total evidence records."""
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM evidence")
        return result["count"] if result else 0

    def count_by_relation(self, relation_id: str) -> int:
        """Count evidence for a relation."""
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM evidence WHERE relation_id = ?",
            (relation_id,)
        )
        return result["count"] if result else 0

    def count_by_status(self, verification_status: str) -> int:
        """Count evidence by verification status."""
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM evidence WHERE verification_status = ?",
            (verification_status,)
        )
        return result["count"] if result else 0

    def update(self, evidence: Evidence) -> Evidence:
        """Update an existing evidence record."""
        evidence.updated_at = datetime.now()
        query = """
            UPDATE evidence SET
                relation_id = ?, document_id = ?,
                reference_number = ?, reference_date = ?,
                evidence_description = ?, evidence_type = ?,
                verification_status = ?, verification_notes = ?,
                verified_by = ?, verification_date = ?,
                updated_at = ?, updated_by = ?
            WHERE evidence_id = ?
        """
        params = (
            evidence.relation_id, evidence.document_id,
            evidence.reference_number,
            evidence.reference_date.isoformat() if evidence.reference_date else None,
            evidence.evidence_description, evidence.evidence_type,
            evidence.verification_status, evidence.verification_notes,
            evidence.verified_by,
            evidence.verification_date.isoformat() if evidence.verification_date else None,
            evidence.updated_at.isoformat(), evidence.updated_by,
            evidence.evidence_id
        )
        self.db.execute(query, params)
        logger.debug(f"Updated evidence: {evidence.evidence_id}")
        return evidence

    def delete(self, evidence_id: str) -> bool:
        """Delete an evidence record by ID."""
        query = "DELETE FROM evidence WHERE evidence_id = ?"
        self.db.execute(query, (evidence_id,))
        return self.get_by_id(evidence_id) is None

    def delete_by_relation(self, relation_id: str) -> int:
        """Delete all evidence for a relation. Returns count of deleted records."""
        count_result = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM evidence WHERE relation_id = ?", (relation_id,))
        count = count_result['c'] if count_result else 0
        self.db.execute("DELETE FROM evidence WHERE relation_id = ?", (relation_id,))
        return count

    def verify(self, evidence_id: str, status: str, notes: str = None,
               verified_by: str = None) -> Optional[Evidence]:
        """Update verification status of evidence."""
        evidence = self.get_by_id(evidence_id)
        if evidence:
            evidence.verification_status = status
            evidence.verification_notes = notes
            evidence.verified_by = verified_by
            evidence.verification_date = date.today()
            return self.update(evidence)
        return None

    def _row_to_evidence(self, row) -> Evidence:
        """Convert database row to Evidence object."""
        data = dict(row)

        # Handle date fields
        for field in ["reference_date", "verification_date"]:
            if data.get(field):
                data[field] = date.fromisoformat(data[field])

        # Handle datetime fields
        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return Evidence(**{k: v for k, v in data.items() if k in Evidence.__dataclass_fields__})
