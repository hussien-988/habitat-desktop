# -*- coding: utf-8 -*-
"""
Person-Unit Relation entity model.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, date
import uuid


@dataclass
class PersonUnitRelation:
    """
    Person-Unit Relation entity linking a Person to a PropertyUnit.
    Represents ownership, tenancy, inheritance, and other relationships.
    """

    # Primary identifier
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Foreign keys
    person_id: str = ""
    unit_id: str = ""

    # Relation type
    relation_type: str = "owner"  # owner, tenant, heir, guest, occupant, other
    relation_type_other_description: Optional[str] = None

    # Ownership details (for owner/heir types)
    ownership_share: int = 0  # 0-2400 shares
    tenure_contract_type: Optional[str] = None

    # Dates
    relation_start_date: Optional[date] = None
    relation_end_date: Optional[date] = None

    # Verification
    verification_status: str = "pending"  # pending, verified, rejected
    verification_date: Optional[date] = None
    verified_by: Optional[str] = None

    # Notes
    relation_notes: Optional[str] = None

    # Evidence links (stored as comma-separated IDs)
    evidence_ids: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @property
    def relation_type_display(self) -> str:
        """Get display name for relation type."""
        types = {
            "owner": "Owner",
            "tenant": "Tenant",
            "heir": "Heir",
            "guest": "Guest",
            "occupant": "Occupant",
            "other": "Other",
        }
        return types.get(self.relation_type, self.relation_type)

    @property
    def relation_type_display_ar(self) -> str:
        """Get Arabic display name for relation type."""
        types = {
            "owner": "مالك",
            "tenant": "مستأجر",
            "heir": "وريث",
            "guest": "ضيف",
            "occupant": "شاغل",
            "other": "آخر",
        }
        return types.get(self.relation_type, self.relation_type)

    @property
    def verification_status_display(self) -> str:
        """Get display name for verification status."""
        statuses = {
            "pending": "Pending",
            "verified": "Verified",
            "rejected": "Rejected",
        }
        return statuses.get(self.verification_status, self.verification_status)

    @property
    def ownership_percentage(self) -> float:
        """Calculate ownership percentage from shares (2400 = 100%)."""
        if self.ownership_share > 0:
            return (self.ownership_share / 2400.0) * 100
        return 0.0

    @property
    def evidence_id_list(self) -> List[str]:
        """Get list of evidence IDs."""
        if self.evidence_ids:
            return [eid.strip() for eid in self.evidence_ids.split(",") if eid.strip()]
        return []

    def add_evidence(self, evidence_id: str):
        """Add an evidence ID to the relation."""
        ids = self.evidence_id_list
        if evidence_id not in ids:
            ids.append(evidence_id)
            self.evidence_ids = ",".join(ids)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "relation_id": self.relation_id,
            "person_id": self.person_id,
            "unit_id": self.unit_id,
            "relation_type": self.relation_type,
            "relation_type_other_description": self.relation_type_other_description,
            "ownership_share": self.ownership_share,
            "tenure_contract_type": self.tenure_contract_type,
            "relation_start_date": self.relation_start_date.isoformat() if self.relation_start_date else None,
            "relation_end_date": self.relation_end_date.isoformat() if self.relation_end_date else None,
            "verification_status": self.verification_status,
            "verification_date": self.verification_date.isoformat() if self.verification_date else None,
            "verified_by": self.verified_by,
            "relation_notes": self.relation_notes,
            "evidence_ids": self.evidence_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PersonUnitRelation":
        """Create PersonUnitRelation from dictionary."""
        # Handle date fields
        for field_name in ["relation_start_date", "relation_end_date", "verification_date"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = date.fromisoformat(data[field_name])

        # Handle datetime fields
        for field_name in ["created_at", "updated_at"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
