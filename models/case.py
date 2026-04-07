# -*- coding: utf-8 -*-
"""
Case entity model.

A Case groups all work done on a specific PropertyUnit —
surveys, claims, person-property relations, and evidence.
Created automatically when the first survey is created,
closed automatically when an ownership/heir claim is created.
"""

from dataclasses import dataclass, field
from typing import Optional, List
import uuid


@dataclass
class Case:
    """Maps to CaseDto from the backend API."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_number: str = ""
    property_unit_id: str = ""
    status: int = 1  # 1=Open, 2=Closed
    status_name: str = "Open"
    opened_date: Optional[str] = None
    closed_date: Optional[str] = None
    closed_by_claim_id: Optional[str] = None
    is_editable: bool = True
    notes: Optional[str] = None
    survey_count: int = 0
    claim_count: int = 0
    person_property_relation_count: int = 0
    survey_ids: List[str] = field(default_factory=list)
    claim_ids: List[str] = field(default_factory=list)
    created_at_utc: Optional[str] = None
    last_modified_at_utc: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.status == 1

    @property
    def is_closed(self) -> bool:
        return self.status == 2

    @property
    def status_display_ar(self) -> str:
        return {1: "مفتوحة", 2: "مغلقة"}.get(self.status, str(self.status))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "caseNumber": self.case_number,
            "propertyUnitId": self.property_unit_id,
            "status": self.status,
            "statusName": self.status_name,
            "openedDate": self.opened_date,
            "closedDate": self.closed_date,
            "closedByClaimId": self.closed_by_claim_id,
            "isEditable": self.is_editable,
            "notes": self.notes,
            "surveyCount": self.survey_count,
            "claimCount": self.claim_count,
            "personPropertyRelationCount": self.person_property_relation_count,
            "surveyIds": self.survey_ids,
            "claimIds": self.claim_ids,
            "createdAtUtc": self.created_at_utc,
            "lastModifiedAtUtc": self.last_modified_at_utc,
        }

    @classmethod
    def from_api_dict(cls, data: dict) -> "Case":
        """Create from backend API response (camelCase keys)."""
        return cls(
            id=str(data.get("id", "")),
            case_number=data.get("caseNumber", ""),
            property_unit_id=str(data.get("propertyUnitId", "")),
            status=data.get("status", 1),
            status_name=data.get("statusName", "Open"),
            opened_date=data.get("openedDate"),
            closed_date=data.get("closedDate"),
            closed_by_claim_id=data.get("closedByClaimId"),
            is_editable=data.get("isEditable", True),
            notes=data.get("notes"),
            survey_count=data.get("surveyCount", 0),
            claim_count=data.get("claimCount", 0),
            person_property_relation_count=data.get("personPropertyRelationCount", 0),
            survey_ids=data.get("surveyIds") or [],
            claim_ids=data.get("claimIds") or [],
            created_at_utc=data.get("createdAtUtc"),
            last_modified_at_utc=data.get("lastModifiedAtUtc"),
        )
