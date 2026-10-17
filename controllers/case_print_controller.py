# -*- coding: utf-8 -*-
"""
Case Print Controller
=====================
Builds the print model of a case report from what the case details page
already shows, and fetches each claim's details when they are requested.
Runs inside an ApiWorker.
"""

from datetime import datetime
from typing import Dict, List

from controllers.application_print_controller import claim_row
from controllers.base_controller import BaseController, OperationResult
from controllers.claim_controller import ClaimController
from services.display_mappings import (
    get_claim_status_display, get_claim_type_display, get_evidence_type_display,
    get_source_display, get_survey_status_display, get_survey_type_display,
)
from services.printing.case_print_model import CasePrintModel, ClaimDetail, SurveyRow
from services.translation_manager import get_language, tr
from utils.logger import get_logger

logger = get_logger(__name__)


class CasePrintController(BaseController):
    """Assembles printable case reports."""

    def build_model(self, case_number: str, status: str, case_rows: List, property_rows: List,
                    surveys: List[Dict], claims: List[Dict], notes: str = "") -> OperationResult:
        """Print model from the case page's data (its field rows and API dicts)."""
        try:
            model = CasePrintModel(
                rtl=get_language() == "ar",
                case_number=case_number,
                status=status,
                print_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                case_rows=case_rows,
                property_rows=property_rows,
                surveys=[_survey_row(s) for s in surveys],
                claims=[claim_row(c) for c in claims],
                claim_refs=[(str(c.get("id") or c.get("claimId")), c.get("claimNumber") or "")
                            for c in claims if c.get("id") or c.get("claimId")],
                notes=notes or "",
            )
            return OperationResult.ok(data=model)
        except Exception as e:
            logger.error(f"Failed to build the case print model: {e}", exc_info=True)
            return OperationResult.fail(str(e), tr("print.failed"))

    def load_claim_details(self, model: CasePrintModel) -> OperationResult:
        """Details of every claim of the case, in the order of the claims table."""
        claims = ClaimController()
        details = []
        for claim_id, number in model.claim_refs:
            result = claims.get_claim_full_detail(claim_id)
            if result.success:
                details.append(_claim_detail(result.data))
            else:
                logger.warning(f"Print: claim {claim_id} details unavailable: {result.message}")
                details.append(ClaimDetail(number=number, unavailable=True))
        return OperationResult.ok(data=details)


def _survey_row(survey: Dict) -> SurveyRow:
    survey_type = survey.get("surveyType")
    status = survey.get("status") or survey.get("surveyStatus")
    return SurveyRow(
        reference=survey.get("referenceCode") or "",
        survey_type=get_survey_type_display(survey_type) if survey_type else "",
        date=_date(survey.get("surveyDate") or survey.get("createdAtUtc")),
        status=get_survey_status_display(status) if status else "",
    )


def _claim_detail(data: Dict) -> ClaimDetail:
    claim = data.get("claim") or {}
    person = data.get("person") or {}
    claimant = " ".join(filter(None, [
        person.get("firstNameArabic"), person.get("fatherNameArabic"), person.get("familyNameArabic"),
    ])) or person.get("fullNameArabic") or claim.get("primaryClaimantName") or ""
    share = claim.get("ownershipShare")
    rows = [
        (tr("print.col.claim_type"), get_claim_type_display(claim["claimType"]) if claim.get("claimType") else ""),
        (tr("print.col.status"), get_claim_status_display(claim["status"]) if claim.get("status") else ""),
        (tr("print.case.col.source"), get_source_display(claim["claimSource"]) if claim.get("claimSource") else ""),
        (tr("print.case.col.claim_date"), _date(claim.get("createdAtUtc"))),
        (tr("print.case.col.linked_survey"), data.get("survey_ref_code") or ""),
        (tr("print.col.claimant"), claimant),
        (tr("wizard.applicant.national_id"), str(person.get("nationalId") or "")),
        (tr("wizard.review.ownership_share"), "" if share in (None, "", 0) else str(share)),
    ]
    evidences = []
    for evidence in data.get("evidences") or []:
        ev_type = evidence.get("evidenceType")
        evidences.append((
            get_evidence_type_display(ev_type) if ev_type else tr("print.evidence"),
            evidence.get("originalFileName") or evidence.get("fileName") or "",
        ))
    return ClaimDetail(number=claim.get("claimNumber") or "", rows=rows, evidences=evidences)


def _date(value) -> str:
    date = str(value or "")[:10]
    return "" if date.startswith("0001") else date
