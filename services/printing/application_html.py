# -*- coding: utf-8 -*-
"""
HTML template of the printed claim application.

Rendered by QTextDocument, which supports only a subset of HTML/CSS: the
layout is built from tables, with inline attributes for borders and colors.
The logo is referenced as the "logo" image resource added by the renderer.
"""

from html import escape
from typing import List, Tuple

from services.printing.application_print_model import ApplicationPrintModel
from services.translation_manager import tr

LOGO_RESOURCE = "logo"

_TITLE_COLOR = "#1B3A5C"
_SECTION_BG = "#E8F1FB"
_BORDER_COLOR = "#9DB4CC"
_LABEL_BG = "#F5F8FC"
_DRAFT_COLOR = "#B91C1C"


def _text(value) -> str:
    text = "" if value is None else str(value).strip()
    return escape(text) if text else "—"


def build_application_html(model: ApplicationPrintModel, include_attachments: bool) -> str:
    direction = "rtl" if model.rtl else "ltr"
    align = "right" if model.rtl else "left"
    parts = [
        f'<html><body dir="{direction}" style="font-size: 9pt; color: #111827;">',
        _header(model, direction, align),
    ]
    if model.is_draft:
        parts.append(
            f'<p dir="{direction}" align="center" style="font-size: 12pt; font-weight: bold; '
            f'color: {_DRAFT_COLOR};">{escape(tr("print.draft_marker"))}</p>'
        )
    parts.append(_section(tr("wizard.review.building_card_title"), _rows_table(model.building, direction, align), direction, align))
    parts.append(_section(tr("wizard.review.unit_card_title"), _rows_table(model.unit, direction, align), direction, align))
    parts.append(_section(tr("review.applicant.title"), _rows_table(model.applicant, direction, align), direction, align))
    parts.append(_section(tr("print.section.household"), _rows_table(model.household, direction, align), direction, align))
    parts.append(_section(tr("print.section.persons"), _persons_table(model, direction, align), direction, align))
    parts.append(_section(tr("print.section.claims"), _claims_table(model, direction, align), direction, align))
    parts.append(_section(tr("print.section.attachments"), _attachments_summary(model, include_attachments, direction, align), direction, align))
    parts.append(_signatures(direction, align))
    parts.append("</body></html>")
    return "".join(parts)


def _header(model: ApplicationPrintModel, direction: str, align: str) -> str:
    reference = (
        f'<span style="color: {_DRAFT_COLOR}; font-weight: bold;">{escape(tr("print.draft_marker"))}</span>'
        if model.is_draft else f"<b>{_text(model.reference_code)}</b>"
    )
    info = [
        (tr("print.reference_code"), reference),
        (tr("print.survey_date"), _text(model.survey_date)),
        (tr("print.survey_type"), _text(model.survey_type)),
        (tr("print.print_date"), _text(model.print_date)),
    ]
    info_cells = "".join(
        f'<tr><td style="color: #4B5563;">{escape(label)}:</td><td>{value}</td></tr>'
        for label, value in info
    )
    return (
        f'<table dir="{direction}" width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="80" valign="middle"><img src="{LOGO_RESOURCE}" width="72" height="72"></td>'
        f'<td valign="middle" align="{align}">'
        f'<p style="font-size: 16pt; font-weight: bold; color: {_TITLE_COLOR};">{escape(tr("print.title"))}</p>'
        f'<p style="color: #4B5563;">UN-Habitat — {escape(tr("print.system_name"))}</p></td>'
        f'<td valign="middle" align="{align}"><table dir="{direction}" cellspacing="0" cellpadding="2">{info_cells}</table></td>'
        f'</tr></table>'
    )


def _section(title: str, body: str, direction: str, align: str) -> str:
    return (
        f'<table dir="{direction}" width="100%" cellspacing="0" cellpadding="4" style="margin-top: 10px;">'
        f'<tr><td bgcolor="{_SECTION_BG}" align="{align}" style="font-size: 10pt; font-weight: bold; '
        f'color: {_TITLE_COLOR};">{escape(title)}</td></tr></table>{body}'
    )


def _grid_table(header: List[str], rows: List[List[str]], direction: str, align: str) -> str:
    head = "".join(
        f'<td bgcolor="{_LABEL_BG}" align="{align}" style="font-weight: bold;">{escape(h)}</td>'
        for h in header
    )
    body = "".join(
        "<tr>" + "".join(f'<td align="{align}">{cell}</td>' for cell in row) + "</tr>"
        for row in rows
    )
    return (
        f'<table dir="{direction}" width="100%" border="1" cellspacing="0" cellpadding="4" '
        f'style="border-collapse: collapse; border-color: {_BORDER_COLOR};">'
        f"<tr>{head}</tr>{body}</table>"
    )


def _rows_table(rows: List[Tuple[str, str]], direction: str, align: str) -> str:
    """Label/value pairs laid out two pairs per line."""
    if not rows:
        return _note("—", direction, align)
    cells = []
    for label, value in rows:
        cells.append(
            f'<td bgcolor="{_LABEL_BG}" width="18%" align="{align}" style="font-weight: bold;">{escape(label)}</td>'
            f'<td width="32%" align="{align}">{_text(value)}</td>'
        )
    if len(cells) % 2:
        cells.append('<td bgcolor="#FFFFFF"></td><td></td>')
    lines = "".join(f"<tr>{cells[i]}{cells[i + 1]}</tr>" for i in range(0, len(cells), 2))
    return (
        f'<table dir="{direction}" width="100%" border="1" cellspacing="0" cellpadding="4" '
        f'style="border-collapse: collapse; border-color: {_BORDER_COLOR};">{lines}</table>'
    )


def _persons_table(model: ApplicationPrintModel, direction: str, align: str) -> str:
    if not model.persons:
        return _note(tr("wizard.person.no_persons"), direction, align)
    header = [
        tr("print.col.name"), tr("wizard.applicant.national_id"), tr("print.col.relation"),
        tr("wizard.review.ownership_share"), tr("print.col.documents"),
    ]
    rows = [
        [_text(p.name), _text(p.national_id), _text(p.relation), _text(p.share), str(p.documents)]
        for p in model.persons
    ]
    return _grid_table(header, rows, direction, align)


def _claims_table(model: ApplicationPrintModel, direction: str, align: str) -> str:
    if not model.claims:
        return _note(tr("print.no_claims"), direction, align)
    header = [
        tr("print.col.claim_number"), tr("print.col.claimant"),
        tr("print.col.claim_type"), tr("print.col.status"),
    ]
    rows = [
        [_text(c.number), _text(c.claimant), _text(c.claim_type), _text(c.status)]
        for c in model.claims
    ]
    return _grid_table(header, rows, direction, align)


def _attachments_summary(model: ApplicationPrintModel, include_attachments: bool,
                         direction: str, align: str) -> str:
    counts = tr(
        "print.attachments_counts",
        id_docs=model.id_documents_count, evidence=model.evidence_count,
    )
    attached = tr("print.attachments_included") if include_attachments else tr("print.attachments_not_included")
    return _note(f"{counts} — {attached}", direction, align)


def _signatures(direction: str, align: str) -> str:
    labels = [tr("print.signature.applicant"), tr("print.signature.officer"), tr("print.signature.date")]
    cells = "".join(
        f'<td width="33%" align="{align}" valign="top">{escape(label)}<br><br>'
        f'<span style="color: #6B7280;">______________________</span></td>'
        for label in labels
    )
    return (
        f'<table dir="{direction}" width="100%" cellspacing="0" cellpadding="6" style="margin-top: 24px;">'
        f"<tr>{cells}</tr></table>"
    )


def _note(text: str, direction: str, align: str) -> str:
    return f'<p dir="{direction}" align="{align}" style="color: #374151;">{escape(text)}</p>'
