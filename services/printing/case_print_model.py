# -*- coding: utf-8 -*-
"""Print model of a case report: display text only, like the application model."""

from dataclasses import dataclass, field
from typing import List, Tuple

from services.printing.application_print_model import ClaimRow, Rows


@dataclass
class SurveyRow:
    reference: str
    survey_type: str
    date: str
    status: str


@dataclass
class ClaimDetail:
    """One claim's details: its data, claimant and supporting documents."""
    number: str
    rows: Rows
    evidences: List[Tuple[str, str]]  # (document type, file name)


@dataclass
class CasePrintModel:
    rtl: bool
    case_number: str
    status: str
    print_date: str
    case_rows: Rows = field(default_factory=list)
    property_rows: Rows = field(default_factory=list)
    surveys: List[SurveyRow] = field(default_factory=list)
    claims: List[ClaimRow] = field(default_factory=list)
    claim_ids: List[str] = field(default_factory=list)
    notes: str = ""
