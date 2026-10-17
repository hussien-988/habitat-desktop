# -*- coding: utf-8 -*-
"""HTML template of the printed case report (see html_parts)."""

from typing import List, Optional

from services.printing.case_print_model import CasePrintModel, ClaimDetail
from services.printing.html_parts import (
    claims_table, document, grid_table, header, note, rows_table, section, signatures, text,
)
from services.translation_manager import tr


def build_case_html(model: CasePrintModel, claim_details: Optional[List[ClaimDetail]] = None) -> str:
    """Case report; `claim_details` adds the claims table and one section per claim."""
    rtl = model.rtl
    parts = [
        header(tr("print.case.title"), [
            (tr("page.case_entity.field_case_number"), f"<b>{text(model.case_number, rtl)}</b>"),
            (tr("page.case_entity.field_status"), text(model.status, rtl)),
            (tr("print.print_date"), text(model.print_date, rtl)),
        ], rtl),
        section(tr("page.case_entity.section_case_info"), rows_table(model.case_rows, rtl)),
        section(tr("page.case_entity.section_property"), rows_table(model.property_rows, rtl)),
        section(tr("page.case_entity.section_surveys", count=len(model.surveys)), _surveys_table(model)),
    ]
    if model.notes:
        parts.append(section(tr("page.case_entity.section_notes"), note(model.notes)))
    if claim_details is not None:
        parts.append(section(tr("print.section.claims"),
                             claims_table(model.claims, rtl) if model.claims else note(tr("print.no_claims"))))
    for detail in claim_details or []:
        parts.append(section(tr("print.case.claim_details", number=detail.number), _claim_detail(detail, rtl)))
    parts.append(signatures([tr("print.case.prepared_by"), tr("print.case.signature"),
                             tr("print.signature.date")], rtl))
    return document(parts)


def _surveys_table(model: CasePrintModel) -> str:
    if not model.surveys:
        return note(tr("page.case_entity.empty_surveys"))
    rtl = model.rtl
    columns = [tr("print.reference_code"), tr("print.survey_type"), tr("print.survey_date"), tr("print.col.status")]
    rows = [
        [text(s.reference, rtl), text(s.survey_type, rtl), text(s.date, rtl), text(s.status, rtl)]
        for s in model.surveys
    ]
    return grid_table(columns, rows, rtl)


def _claim_detail(detail: ClaimDetail, rtl: bool) -> str:
    if detail.unavailable:
        return note(tr("print.case.claim_unavailable"))
    body = rows_table(detail.rows, rtl)
    if detail.evidences:
        columns = [tr("print.case.col.document_type"), tr("print.case.col.file_name")]
        body += grid_table(columns, [[text(t, rtl), text(n, rtl)] for t, n in detail.evidences], rtl)
    else:
        body += note(tr("print.case.no_evidences"))
    return body
