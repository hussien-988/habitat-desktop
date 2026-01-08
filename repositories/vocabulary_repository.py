# -*- coding: utf-8 -*-
"""
Vocabulary repository for managing controlled vocabularies.
Implements UC-010: Vocabulary Management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import uuid

from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VocabularyTerm:
    """Represents a vocabulary term."""
    term_id: str = None
    vocabulary_name: str = None
    term_code: str = None
    term_label: str = None
    term_label_ar: str = None
    status: str = "active"  # active, deprecated
    effective_from: str = None
    effective_to: str = None
    version_number: int = 1
    source: str = "manual"  # manual, imported
    created_at: datetime = None
    updated_at: datetime = None
    created_by: str = None
    updated_by: str = None

    def __post_init__(self):
        if not self.term_id:
            self.term_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now()


class VocabularyRepository:
    """Repository for vocabulary term CRUD operations."""

    # Available vocabulary types with display names
    VOCABULARY_TYPES = {
        "building_type": ("أنواع المباني", "Building Types"),
        "building_status": ("حالات المباني", "Building Status"),
        "unit_type": ("أنواع الوحدات", "Unit Types"),
        "relation_type": ("أنواع العلاقات", "Relation Types"),
        "document_type": ("أنواع المستندات", "Document Types"),
        "case_status": ("حالات المطالبات", "Case Status"),
        "claim_type": ("أنواع المطالبات", "Claim Types"),
    }

    def __init__(self, db: Database):
        self.db = db

    def get_vocabulary_types(self) -> List[tuple]:
        """Get list of available vocabulary types."""
        return [(k, v[0], v[1]) for k, v in self.VOCABULARY_TYPES.items()]

    def get_terms(self, vocabulary_name: str, include_deprecated: bool = False) -> List[VocabularyTerm]:
        """
        Get all terms for a vocabulary.

        Args:
            vocabulary_name: Name of the vocabulary
            include_deprecated: Whether to include deprecated terms
        """
        query = "SELECT * FROM vocabulary_terms WHERE vocabulary_name = ?"
        params = [vocabulary_name]

        if not include_deprecated:
            query += " AND status = 'active'"

        query += " ORDER BY term_label_ar, term_label"

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_term(row) for row in rows]

    def get_term_by_code(self, vocabulary_name: str, term_code: str) -> Optional[VocabularyTerm]:
        """Get a specific term by code."""
        query = "SELECT * FROM vocabulary_terms WHERE vocabulary_name = ? AND term_code = ?"
        row = self.db.fetch_one(query, (vocabulary_name, term_code))
        if row:
            return self._row_to_term(row)
        return None

    def get_term_by_id(self, term_id: str) -> Optional[VocabularyTerm]:
        """Get a term by ID."""
        query = "SELECT * FROM vocabulary_terms WHERE term_id = ?"
        row = self.db.fetch_one(query, (term_id,))
        if row:
            return self._row_to_term(row)
        return None

    def create_term(self, term: VocabularyTerm) -> VocabularyTerm:
        """
        Create a new vocabulary term.

        Args:
            term: The term to create

        Raises:
            ValueError: If term code already exists
        """
        # Check for duplicate code
        existing = self.get_term_by_code(term.vocabulary_name, term.term_code)
        if existing:
            raise ValueError(f"Term code '{term.term_code}' already exists in vocabulary '{term.vocabulary_name}'")

        query = """
            INSERT INTO vocabulary_terms (
                term_id, vocabulary_name, term_code, term_label, term_label_ar,
                status, effective_from, effective_to, version_number, source,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            term.term_id,
            term.vocabulary_name,
            term.term_code,
            term.term_label,
            term.term_label_ar,
            term.status,
            term.effective_from,
            term.effective_to,
            term.version_number,
            term.source,
            term.created_at.isoformat() if term.created_at else None,
            term.updated_at.isoformat() if term.updated_at else None,
            term.created_by,
            term.updated_by
        )
        self.db.execute(query, params)
        logger.info(f"Created vocabulary term: {term.vocabulary_name}/{term.term_code}")
        return term

    def update_term(self, term: VocabularyTerm) -> VocabularyTerm:
        """Update an existing vocabulary term."""
        term.updated_at = datetime.now()

        query = """
            UPDATE vocabulary_terms SET
                term_label = ?, term_label_ar = ?, status = ?,
                effective_from = ?, effective_to = ?,
                version_number = version_number + 1,
                updated_at = ?, updated_by = ?
            WHERE term_id = ?
        """
        params = (
            term.term_label,
            term.term_label_ar,
            term.status,
            term.effective_from,
            term.effective_to,
            term.updated_at.isoformat(),
            term.updated_by,
            term.term_id
        )
        self.db.execute(query, params)
        logger.info(f"Updated vocabulary term: {term.vocabulary_name}/{term.term_code}")
        return term

    def deprecate_term(self, term_id: str, user_id: str = None) -> bool:
        """
        Deprecate a vocabulary term (soft delete).
        Per UC-010: prevent deletion of terms in use, instead mark as deprecated.
        """
        query = """
            UPDATE vocabulary_terms
            SET status = 'deprecated', updated_at = ?, updated_by = ?
            WHERE term_id = ?
        """
        self.db.execute(query, (datetime.now().isoformat(), user_id, term_id))
        logger.info(f"Deprecated vocabulary term: {term_id}")
        return True

    def activate_term(self, term_id: str, user_id: str = None) -> bool:
        """Reactivate a deprecated term."""
        query = """
            UPDATE vocabulary_terms
            SET status = 'active', updated_at = ?, updated_by = ?
            WHERE term_id = ?
        """
        self.db.execute(query, (datetime.now().isoformat(), user_id, term_id))
        logger.info(f"Activated vocabulary term: {term_id}")
        return True

    def get_all_vocabularies(self) -> Dict[str, List[VocabularyTerm]]:
        """Get all vocabularies with their terms."""
        result = {}
        for vocab_name in self.VOCABULARY_TYPES.keys():
            result[vocab_name] = self.get_terms(vocab_name)
        return result

    def export_vocabulary(self, vocabulary_name: str = None) -> List[Dict[str, Any]]:
        """
        Export vocabulary terms for mobile sync (UC-010 S09).

        Returns:
            List of term dictionaries
        """
        query = "SELECT * FROM vocabulary_terms WHERE status = 'active'"
        params = []

        if vocabulary_name:
            query += " AND vocabulary_name = ?"
            params.append(vocabulary_name)

        query += " ORDER BY vocabulary_name, term_code"

        rows = self.db.fetch_all(query, tuple(params))
        return [dict(row) for row in rows]

    def import_vocabulary(self, vocabulary_name: str, terms: List[Dict], user_id: str = None) -> int:
        """
        Import vocabulary terms from a file (UC-010 S04).

        Args:
            vocabulary_name: Target vocabulary
            terms: List of term dicts with code, label, label_ar
            user_id: User performing import

        Returns:
            Number of terms imported
        """
        count = 0
        for term_data in terms:
            term_code = term_data.get("code") or term_data.get("term_code")
            if not term_code:
                continue

            existing = self.get_term_by_code(vocabulary_name, term_code)
            if existing:
                # Update existing term
                existing.term_label = term_data.get("label", term_data.get("term_label", existing.term_label))
                existing.term_label_ar = term_data.get("label_ar", term_data.get("term_label_ar", existing.term_label_ar))
                existing.updated_by = user_id
                existing.source = "imported"
                self.update_term(existing)
            else:
                # Create new term
                term = VocabularyTerm(
                    vocabulary_name=vocabulary_name,
                    term_code=term_code,
                    term_label=term_data.get("label", term_data.get("term_label", term_code)),
                    term_label_ar=term_data.get("label_ar", term_data.get("term_label_ar")),
                    source="imported",
                    created_by=user_id
                )
                self.create_term(term)

            count += 1

        logger.info(f"Imported {count} terms into vocabulary '{vocabulary_name}'")
        return count

    def _row_to_term(self, row) -> VocabularyTerm:
        """Convert database row to VocabularyTerm."""
        data = dict(row)

        # Parse datetime fields
        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return VocabularyTerm(**{k: v for k, v in data.items() if k in VocabularyTerm.__dataclass_fields__})

    def delete_term(self, term_id: str) -> bool:
        """
        Permanently delete a vocabulary term.
        Use with caution - this is for cleaning up test data only.
        For production use, prefer deprecate_term() instead.
        """
        query = "DELETE FROM vocabulary_terms WHERE term_id = ?"
        self.db.execute(query, (term_id,))
        logger.info(f"Deleted vocabulary term: {term_id}")
        return True

    def cleanup_test_data(self, vocabulary_name: str = None) -> int:
        """
        Remove non-default vocabulary terms (test data cleanup).

        Default terms are defined in database._seed_default_vocabularies().
        This method removes any terms that don't match those defaults.

        Returns:
            Number of terms deleted
        """
        # Default vocabulary codes from database.py
        default_codes = {
            "building_type": {"residential", "commercial", "mixed_use", "industrial", "public"},
            "building_status": {"intact", "minor_damage", "major_damage", "destroyed", "under_construction"},
            "unit_type": {"apartment", "shop", "office", "warehouse", "garage", "other"},
            "relation_type": {"owner", "tenant", "heir", "guest", "occupant", "other"},
            "case_status": {"draft", "submitted", "screening", "under_review", "awaiting_docs", "conflict", "approved", "rejected"},
        }

        count = 0
        vocabs = [vocabulary_name] if vocabulary_name else list(default_codes.keys())

        for vocab_name in vocabs:
            if vocab_name not in default_codes:
                continue

            terms = self.get_terms(vocab_name, include_deprecated=True)
            for term in terms:
                if term.term_code not in default_codes[vocab_name]:
                    self.delete_term(term.term_id)
                    count += 1
                    logger.info(f"Deleted test term: {vocab_name}/{term.term_code}")

        return count
