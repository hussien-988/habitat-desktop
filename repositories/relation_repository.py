# -*- coding: utf-8 -*-
"""
Person-Unit Relation repository for database operations.
"""

from typing import List, Optional
from datetime import datetime, date

from models.relation import PersonUnitRelation
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class RelationRepository:
    """Repository for PersonUnitRelation CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, relation: PersonUnitRelation) -> PersonUnitRelation:
        """Create a new person-unit relation record."""
        query = """
            INSERT INTO person_unit_relations (
                relation_id, person_id, unit_id, relation_type,
                relation_type_other_description, ownership_share,
                tenure_contract_type, relation_start_date, relation_end_date,
                verification_status, verification_date, verified_by,
                relation_notes, evidence_ids,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            relation.relation_id, relation.person_id, relation.unit_id,
            relation.relation_type, relation.relation_type_other_description,
            relation.ownership_share, relation.tenure_contract_type,
            relation.relation_start_date.isoformat() if relation.relation_start_date else None,
            relation.relation_end_date.isoformat() if relation.relation_end_date else None,
            relation.verification_status,
            relation.verification_date.isoformat() if relation.verification_date else None,
            relation.verified_by, relation.relation_notes, relation.evidence_ids,
            relation.created_at.isoformat() if relation.created_at else None,
            relation.updated_at.isoformat() if relation.updated_at else None,
            relation.created_by, relation.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created relation: {relation.relation_id}")
        return relation

    def get_by_id(self, relation_id: str) -> Optional[PersonUnitRelation]:
        """Get relation by ID."""
        query = "SELECT * FROM person_unit_relations WHERE relation_id = ?"
        row = self.db.fetch_one(query, (relation_id,))
        if row:
            return self._row_to_relation(row)
        return None

    def get_by_person(self, person_id: str) -> List[PersonUnitRelation]:
        """Get all relations for a person."""
        query = "SELECT * FROM person_unit_relations WHERE person_id = ? ORDER BY created_at DESC"
        rows = self.db.fetch_all(query, (person_id,))
        return [self._row_to_relation(row) for row in rows]

    def get_by_unit(self, unit_id: str) -> List[PersonUnitRelation]:
        """Get all relations for a unit."""
        query = "SELECT * FROM person_unit_relations WHERE unit_id = ? ORDER BY created_at DESC"
        rows = self.db.fetch_all(query, (unit_id,))
        return [self._row_to_relation(row) for row in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> List[PersonUnitRelation]:
        """Get all relations with pagination."""
        query = "SELECT * FROM person_unit_relations ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_relation(row) for row in rows]

    def search(self, person_id: str = None, unit_id: str = None,
               relation_type: str = None, verification_status: str = None,
               limit: int = 100) -> List[PersonUnitRelation]:
        """Search relations with filters."""
        query = "SELECT * FROM person_unit_relations WHERE 1=1"
        params = []

        if person_id:
            query += " AND person_id = ?"
            params.append(person_id)

        if unit_id:
            query += " AND unit_id = ?"
            params.append(unit_id)

        if relation_type:
            query += " AND relation_type = ?"
            params.append(relation_type)

        if verification_status:
            query += " AND verification_status = ?"
            params.append(verification_status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_relation(row) for row in rows]

    def exists(self, person_id: str, unit_id: str, relation_type: str,
               exclude_relation_id: str = None) -> bool:
        """
        Check if a relation already exists (for duplicate prevention).
        Optionally exclude a specific relation (for edit mode).
        """
        if exclude_relation_id:
            query = """
                SELECT COUNT(*) as count FROM person_unit_relations
                WHERE person_id = ? AND unit_id = ? AND relation_type = ?
                AND relation_id != ?
            """
            result = self.db.fetch_one(query, (person_id, unit_id, relation_type, exclude_relation_id))
        else:
            query = """
                SELECT COUNT(*) as count FROM person_unit_relations
                WHERE person_id = ? AND unit_id = ? AND relation_type = ?
            """
            result = self.db.fetch_one(query, (person_id, unit_id, relation_type))

        return result["count"] > 0 if result else False

    def count(self) -> int:
        """Count total relations."""
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM person_unit_relations")
        return result["count"] if result else 0

    def count_by_unit(self, unit_id: str) -> int:
        """Count relations for a unit."""
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM person_unit_relations WHERE unit_id = ?",
            (unit_id,)
        )
        return result["count"] if result else 0

    def count_by_person(self, person_id: str) -> int:
        """Count relations for a person."""
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM person_unit_relations WHERE person_id = ?",
            (person_id,)
        )
        return result["count"] if result else 0

    def get_total_ownership_share(self, unit_id: str, exclude_relation_id: str = None) -> int:
        """Get total ownership share for a unit (to validate max 100%)."""
        if exclude_relation_id:
            query = """
                SELECT COALESCE(SUM(ownership_share), 0) as total
                FROM person_unit_relations
                WHERE unit_id = ? AND relation_type = 'owner' AND relation_id != ?
            """
            result = self.db.fetch_one(query, (unit_id, exclude_relation_id))
        else:
            query = """
                SELECT COALESCE(SUM(ownership_share), 0) as total
                FROM person_unit_relations
                WHERE unit_id = ? AND relation_type = 'owner'
            """
            result = self.db.fetch_one(query, (unit_id,))

        return result["total"] if result else 0

    def update(self, relation: PersonUnitRelation) -> PersonUnitRelation:
        """Update an existing relation."""
        relation.updated_at = datetime.now()
        query = """
            UPDATE person_unit_relations SET
                person_id = ?, unit_id = ?, relation_type = ?,
                relation_type_other_description = ?, ownership_share = ?,
                tenure_contract_type = ?, relation_start_date = ?,
                relation_end_date = ?, verification_status = ?,
                verification_date = ?, verified_by = ?,
                relation_notes = ?, evidence_ids = ?,
                updated_at = ?, updated_by = ?
            WHERE relation_id = ?
        """
        params = (
            relation.person_id, relation.unit_id, relation.relation_type,
            relation.relation_type_other_description, relation.ownership_share,
            relation.tenure_contract_type,
            relation.relation_start_date.isoformat() if relation.relation_start_date else None,
            relation.relation_end_date.isoformat() if relation.relation_end_date else None,
            relation.verification_status,
            relation.verification_date.isoformat() if relation.verification_date else None,
            relation.verified_by, relation.relation_notes, relation.evidence_ids,
            relation.updated_at.isoformat(), relation.updated_by,
            relation.relation_id
        )
        self.db.execute(query, params)
        logger.debug(f"Updated relation: {relation.relation_id}")
        return relation

    def delete(self, relation_id: str) -> bool:
        """Delete a relation by ID."""
        query = "DELETE FROM person_unit_relations WHERE relation_id = ?"
        self.db.execute(query, (relation_id,))
        return self.get_by_id(relation_id) is None

    def _row_to_relation(self, row) -> PersonUnitRelation:
        """Convert database row to PersonUnitRelation object."""
        data = dict(row)

        # Handle date fields
        for field in ["relation_start_date", "relation_end_date", "verification_date"]:
            if data.get(field):
                data[field] = date.fromisoformat(data[field])

        # Handle datetime fields
        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return PersonUnitRelation(**{k: v for k, v in data.items() if k in PersonUnitRelation.__dataclass_fields__})
