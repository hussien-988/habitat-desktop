# -*- coding: utf-8 -*-
"""
Print model of a claim application.

Plain data with every value already turned into display text (in the
language the print was requested in), so the template and the renderer
never touch the API or the vocabularies.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# (label, value) pairs shown as a two-column table
Rows = List[Tuple[str, str]]


@dataclass
class PersonRow:
    name: str
    national_id: str
    relation: str
    share: str
    documents: int


@dataclass
class ClaimRow:
    number: str
    claimant: str
    claim_type: str
    status: str


@dataclass
class AttachmentItem:
    """One ID document or tenure evidence of a person."""
    kind: str                  # "id_document" | "evidence"
    doc_type: str
    person: str
    file_name: str
    person_id: str = ""
    document_id: str = ""
    local_path: Optional[str] = None   # set once downloaded


@dataclass
class ApplicationPrintModel:
    rtl: bool
    is_draft: bool
    reference_code: str
    survey_date: str
    survey_type: str
    print_date: str
    building: Rows = field(default_factory=list)
    unit: Rows = field(default_factory=list)
    applicant: Rows = field(default_factory=list)
    household: Rows = field(default_factory=list)
    persons: List[PersonRow] = field(default_factory=list)
    claims: List[ClaimRow] = field(default_factory=list)
    attachments: List[AttachmentItem] = field(default_factory=list)

    @property
    def id_documents_count(self) -> int:
        return sum(1 for a in self.attachments if a.kind == "id_document")

    @property
    def evidence_count(self) -> int:
        return sum(1 for a in self.attachments if a.kind == "evidence")
