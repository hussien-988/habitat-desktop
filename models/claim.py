# -*- coding: utf-8 -*-
"""
Claim/Case entity model.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, date
import uuid


@dataclass
class Claim:
    """
    Claim/Case entity representing tenure rights claims.

    Claim ID Format: CL-YYYY-NNNNNN
    - CL: Fixed prefix
    - YYYY: Year of submission
    - NNNNNN: Sequential number (6 digits)
    """

    # Primary identifier
    claim_id: str = ""  # Will be generated
    claim_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Case number (human-readable)
    case_number: str = ""

    # Source
    source: str = "OFFICE_SUBMISSION"  # FIELD_COLLECTION, OFFICE_SUBMISSION, SYSTEM_IMPORT

    # Related entities (comma-separated IDs for multiple claimants)
    person_ids: str = ""  # Claimant person IDs
    unit_id: str = ""  # Property unit being claimed
    relation_ids: str = ""  # Related PersonUnitRelation IDs

    # Status
    case_status: str = "draft"  # draft, submitted, screening, under_review, awaiting_docs, conflict, approved, rejected
    lifecycle_stage: str = "draft"

    # Classification
    claim_type: str = "ownership"  # ownership, occupancy, tenancy
    priority: str = "normal"  # low, normal, high, urgent

    # Workflow
    assigned_to: Optional[str] = None
    assigned_date: Optional[date] = None
    awaiting_documents: bool = False

    # Dates
    submission_date: Optional[date] = None
    decision_date: Optional[date] = None

    # Notes
    notes: Optional[str] = None
    resolution_notes: Optional[str] = None

    # Conflict tracking
    has_conflict: bool = False
    conflict_claim_ids: str = ""  # Related conflicting claims

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    def __post_init__(self):
        """Generate claim_id if not provided."""
        if not self.claim_id:
            year = datetime.now().year
            # In production, this would query the database for the next sequence
            seq = str(uuid.uuid4().int)[:6].zfill(6)
            self.claim_id = f"CL-{year}-{seq}"

        if not self.case_number:
            self.case_number = self.claim_id

    @property
    def case_status_display(self) -> str:
        """Get display name for case status."""
        statuses = {
            "draft": "Draft",
            "submitted": "Submitted",
            "screening": "Initial Screening",
            "under_review": "Under Review",
            "awaiting_docs": "Awaiting Documents",
            "conflict": "Conflict Detected",
            "approved": "Approved",
            "rejected": "Rejected",
        }
        return statuses.get(self.case_status, self.case_status)

    @property
    def case_status_display_ar(self) -> str:
        """Get Arabic display name for case status."""
        statuses = {
            "draft": "مسودة",
            "submitted": "مقدم",
            "screening": "التدقيق الأولي",
            "under_review": "قيد المراجعة",
            "awaiting_docs": "في انتظار الوثائق",
            "conflict": "تعارض مكتشف",
            "approved": "موافق عليه",
            "rejected": "مرفوض",
        }
        return statuses.get(self.case_status, self.case_status)

    @property
    def source_display(self) -> str:
        """Get display name for source."""
        sources = {
            "FIELD_COLLECTION": "Field Collection",
            "OFFICE_SUBMISSION": "Office Submission",
            "SYSTEM_IMPORT": "System Import",
        }
        return sources.get(self.source, self.source)

    @property
    def person_id_list(self) -> List[str]:
        """Get list of person IDs."""
        if self.person_ids:
            return [pid.strip() for pid in self.person_ids.split(",") if pid.strip()]
        return []

    @property
    def relation_id_list(self) -> List[str]:
        """Get list of relation IDs."""
        if self.relation_ids:
            return [rid.strip() for rid in self.relation_ids.split(",") if rid.strip()]
        return []

    def add_person(self, person_id: str):
        """Add a person ID to the claim."""
        ids = self.person_id_list
        if person_id not in ids:
            ids.append(person_id)
            self.person_ids = ",".join(ids)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "claim_id": self.claim_id,
            "claim_uuid": self.claim_uuid,
            "case_number": self.case_number,
            "source": self.source,
            "person_ids": self.person_ids,
            "unit_id": self.unit_id,
            "relation_ids": self.relation_ids,
            "case_status": self.case_status,
            "lifecycle_stage": self.lifecycle_stage,
            "claim_type": self.claim_type,
            "priority": self.priority,
            "assigned_to": self.assigned_to,
            "assigned_date": self.assigned_date.isoformat() if self.assigned_date else None,
            "awaiting_documents": self.awaiting_documents,
            "submission_date": self.submission_date.isoformat() if self.submission_date else None,
            "decision_date": self.decision_date.isoformat() if self.decision_date else None,
            "notes": self.notes,
            "resolution_notes": self.resolution_notes,
            "has_conflict": self.has_conflict,
            "conflict_claim_ids": self.conflict_claim_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Claim":
        """Create Claim from dictionary."""
        for field_name in ["assigned_date", "submission_date", "decision_date"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = date.fromisoformat(data[field_name])

        for field_name in ["created_at", "updated_at"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
