# -*- coding: utf-8 -*-
"""HTML template of the printed claim application (see html_parts)."""

from html import escape

from services.printing.application_print_model import ApplicationPrintModel
from services.printing.html_parts import (
    DRAFT_COLOR, claims_table, document, grid_table, header, note, rows_table, section, signatures, text,
)
from services.translation_manager import tr


def build_application_html(model: ApplicationPrintModel, include_attachments: bool) -> str:
    rtl = model.rtl
    reference = (
        f'<span style="color: {DRAFT_COLOR}; font-weight: bold;">{escape(tr("print.draft_marker"))}</span>'
        if model.is_draft else f"<b>{text(model.reference_code, rtl)}</b>"
    )
    parts = [header(tr("print.title"), [
        (tr("print.reference_code"), reference),
        (tr("print.survey_date"), text(model.survey_date, rtl)),
        (tr("print.survey_type"), text(model.survey_type, rtl)),
        (tr("print.print_date"), text(model.print_date, rtl)),
    ], rtl)]
    if model.is_draft:
        parts.append(
            f'<p align="center" style="font-size: 12pt; font-weight: bold; color: {DRAFT_COLOR};">'
            f'{escape(tr("print.draft_marker"))}</p>'
        )
    parts += [
        section(tr("wizard.review.building_card_title"), rows_table(model.building, rtl)),
        section(tr("wizard.review.unit_card_title"), rows_table(model.unit, rtl)),
        section(tr("review.applicant.title"), rows_table(model.applicant, rtl)),
        section(tr("print.section.household"), rows_table(model.household, rtl)),
        section(tr("print.section.persons"), _persons_table(model)),
        section(tr("print.section.claims"), _claims_table(model)),
        section(tr("print.section.attachments"), _attachments_summary(model, include_attachments)),
        signatures([tr("print.signature.applicant"), tr("print.signature.officer"),
                    tr("print.signature.date")], rtl),
    ]
    return document(parts)


def _persons_table(model: ApplicationPrintModel) -> str:
    if not model.persons:
        return note(tr("wizard.person.no_persons"))
    columns = [
        tr("print.col.name"), tr("wizard.applicant.national_id"), tr("print.col.relation"),
        tr("wizard.review.ownership_share"), tr("print.col.documents"),
    ]
    rtl = model.rtl
    rows = [
        [text(p.name, rtl), text(p.national_id, rtl), text(p.relation, rtl),
         text(p.share, rtl), text(p.documents, rtl)]
        for p in model.persons
    ]
    return grid_table(columns, rows, rtl)


def _claims_table(model: ApplicationPrintModel) -> str:
    if not model.claims:
        return note(tr("print.no_claims"))
    return claims_table(model.claims, model.rtl)


def _attachments_summary(model: ApplicationPrintModel, include_attachments: bool) -> str:
    counts = tr(
        "print.attachments_counts",
        id_docs=model.id_documents_count, evidence=model.evidence_count,
    )
    attached = tr("print.attachments_included") if include_attachments else tr("print.attachments_not_included")
    return note(f"{counts} — {attached}")
