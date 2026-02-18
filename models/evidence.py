# -*- coding: utf-8 -*-
"""
Evidence entity model.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, date
import uuid


@dataclass
class Evidence:
    """
    Evidence entity representing proof supporting a Person-Unit Relation.
    """

    # Primary identifier
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Foreign keys
    relation_id: str = ""  # FK to PersonUnitRelation
    document_id: Optional[str] = None  # FK to Document (nullable for non-doc evidence)

    # Evidence details
    reference_number: Optional[str] = None
    reference_date: Optional[date] = None
    evidence_description: str = ""

    # Type (for categorization)
    evidence_type: str = "document"  # document, witness, community, other

    # Verification
    verification_status: str = "pending"  # pending, verified, rejected
    verification_notes: Optional[str] = None
    verified_by: Optional[str] = None
    verification_date: Optional[date] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @property
    def evidence_type_display(self) -> str:
        """Get display name for evidence type."""
        types = {
            "document": "Document",
            "witness": "Witness Statement",
            "community": "Community Affirmation",
            "other": "Other",
        }
        return types.get(self.evidence_type, self.evidence_type)

    @property
    def evidence_type_display_ar(self) -> str:
        """Get Arabic display name for evidence type."""
        types = {
            "document": "وثيقة",
            "witness": "إفادة شاهد",
            "community": "تأكيد مجتمعي",
            "other": "آخر",
        }
        return types.get(self.evidence_type, self.evidence_type)

    @property
    def verification_status_display(self) -> str:
        """Get display name for verification status."""
        statuses = {
            "pending": "Pending",
            "verified": "Verified",
            "rejected": "Rejected",
        }
        return statuses.get(self.verification_status, self.verification_status)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "evidence_id": self.evidence_id,
            "relation_id": self.relation_id,
            "document_id": self.document_id,
            "reference_number": self.reference_number,
            "reference_date": self.reference_date.isoformat() if self.reference_date else None,
            "evidence_description": self.evidence_description,
            "evidence_type": self.evidence_type,
            "verification_status": self.verification_status,
            "verification_notes": self.verification_notes,
            "verified_by": self.verified_by,
            "verification_date": self.verification_date.isoformat() if self.verification_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        """Create Evidence from dictionary."""
        for field_name in ["reference_date", "verification_date"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = date.fromisoformat(data[field_name])

        for field_name in ["created_at", "updated_at"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
