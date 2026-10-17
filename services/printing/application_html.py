# -*- coding: utf-8 -*-
"""
HTML template of the printed claim application.

Rendered by QTextDocument, which supports only a subset of HTML/CSS: the
layout is built from tables, with inline attributes for borders and colors.
QTextDocument does not mirror table columns for RTL text, so in Arabic the
cells of every row are emitted right-to-left here; the renderer sets the
paragraph direction. The logo is the "logo" image resource added by the
renderer.
"""

import re
from html import escape
from typing import List, Tuple

from services.printing.application_print_model import ApplicationPrintModel
from services.translation_manager import tr

LOGO_RESOURCE = "logo"

TITLE_COLOR = "#1B3A5C"
_TEXT_COLOR = "#111827"
_MUTED_COLOR = "#4B5563"
_SECTION_BG = "#E8F1FB"
_BORDER_COLOR = "#9DB4CC"
_LABEL_BG = "#F5F8FC"
_DRAFT_COLOR = "#B91C1C"

_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LTR_EMBEDDING, _POP_DIRECTIONAL = "‪", "‬"


def build_application_html(model: ApplicationPrintModel, include_attachments: bool) -> str:
    rtl = model.rtl
    sections = [
        (tr("wizard.review.building_card_title"), _rows_table(model.building, rtl)),
        (tr("wizard.review.unit_card_title"), _rows_table(model.unit, rtl)),
        (tr("review.applicant.title"), _rows_table(model.applicant, rtl)),
        (tr("print.section.household"), _rows_table(model.household, rtl)),
        (tr("print.section.persons"), _persons_table(model)),
        (tr("print.section.claims"), _claims_table(model)),
        (tr("print.section.attachments"), _attachments_summary(model, include_attachments)),
    ]
    parts = [f'<html><body style="font-size: 9pt; color: {_TEXT_COLOR};">', _header(model)]
    if model.is_draft:
        parts.append(
            f'<p align="center" style="font-size: 12pt; font-weight: bold; color: {_DRAFT_COLOR};">'
            f'{escape(tr("print.draft_marker"))}</p>'
        )
    parts.extend(_section(title, body) for title, body in sections)
    parts.append(_signatures(rtl))
    parts.append("</body></html>")
    return "".join(parts)


def _row(cells: List[str], rtl: bool) -> str:
    """Table row with cells in reading order (mirrored for RTL)."""
    return "<tr>" + "".join(reversed(cells) if rtl else cells) + "</tr>"


def _text(value, rtl: bool) -> str:
    """Escaped cell text; in RTL, values without Arabic letters (dates,
    codes, numbers, Latin names) are embedded as LTR so they keep their order."""
    text = "" if value is None else str(value).strip()
    if not text:
        return "—"
    if rtl and not _ARABIC.search(text):
        text = f"{_LTR_EMBEDDING}{text}{_POP_DIRECTIONAL}"
    return escape(text)


def _header(model: ApplicationPrintModel) -> str:
    rtl = model.rtl
    reference = (
        f'<span style="color: {_DRAFT_COLOR}; font-weight: bold;">{escape(tr("print.draft_marker"))}</span>'
        if model.is_draft else f"<b>{_text(model.reference_code, rtl)}</b>"
    )
    info = [
        (tr("print.reference_code"), reference),
        (tr("print.survey_date"), _text(model.survey_date, rtl)),
        (tr("print.survey_type"), _text(model.survey_type, rtl)),
        (tr("print.print_date"), _text(model.print_date, rtl)),
    ]
    info_rows = "".join(
        _row([f'<td style="color: {_MUTED_COLOR};">{escape(label)}:</td>', f"<td>{value}</td>"], rtl)
        for label, value in info
    )
    cells = [
        f'<td width="84" valign="middle"><img src="{LOGO_RESOURCE}" width="72" height="72"></td>',
        '<td valign="middle">'
        f'<p style="font-size: 16pt; font-weight: bold; color: {TITLE_COLOR};">{escape(tr("print.title"))}</p>'
        f'<p style="color: {_MUTED_COLOR};">{escape(tr("print.system_name"))} — UN-Habitat</p></td>',
        f'<td valign="middle"><table cellspacing="0" cellpadding="2">{info_rows}</table></td>',
    ]
    return f'<table width="100%" cellspacing="0" cellpadding="0">{_row(cells, rtl)}</table>'


def _section(title: str, body: str) -> str:
    return (
        '<table width="100%" cellspacing="0" cellpadding="4" style="margin-top: 10px;">'
        f'<tr><td bgcolor="{_SECTION_BG}" style="font-size: 10pt; font-weight: bold; '
        f'color: {TITLE_COLOR};">{escape(title)}</td></tr></table>{body}'
    )


def _bordered_table(rows_html: str) -> str:
    return (
        '<table width="100%" border="1" cellspacing="0" cellpadding="4" '
        f'style="border-collapse: collapse; border-color: {_BORDER_COLOR};">{rows_html}</table>'
    )


def _grid_table(header: List[str], rows: List[List[str]], rtl: bool) -> str:
    head = _row([f'<td bgcolor="{_LABEL_BG}" style="font-weight: bold;">{escape(h)}</td>' for h in header], rtl)
    body = "".join(_row([f"<td>{cell}</td>" for cell in row], rtl) for row in rows)
    return _bordered_table(head + body)


def _rows_table(rows: List[Tuple[str, str]], rtl: bool) -> str:
    """Label/value pairs laid out two pairs per line."""
    if not rows:
        return _note("—")
    cells = []
    for label, value in rows:
        cells.append(f'<td bgcolor="{_LABEL_BG}" width="18%" style="font-weight: bold;">{escape(label)}</td>')
        cells.append(f'<td width="32%">{_text(value, rtl)}</td>')
    if len(cells) % 4:
        cells.extend(["<td></td>", "<td></td>"])
    return _bordered_table("".join(_row(cells[i:i + 4], rtl) for i in range(0, len(cells), 4)))


def _persons_table(model: ApplicationPrintModel) -> str:
    if not model.persons:
        return _note(tr("wizard.person.no_persons"))
    header = [
        tr("print.col.name"), tr("wizard.applicant.national_id"), tr("print.col.relation"),
        tr("wizard.review.ownership_share"), tr("print.col.documents"),
    ]
    rtl = model.rtl
    rows = [
        [_text(p.name, rtl), _text(p.national_id, rtl), _text(p.relation, rtl),
         _text(p.share, rtl), _text(p.documents, rtl)]
        for p in model.persons
    ]
    return _grid_table(header, rows, rtl)


def _claims_table(model: ApplicationPrintModel) -> str:
    if not model.claims:
        return _note(tr("print.no_claims"))
    header = [
        tr("print.col.claim_number"), tr("print.col.claimant"),
        tr("print.col.claim_type"), tr("print.col.status"),
    ]
    rtl = model.rtl
    rows = [
        [_text(c.number, rtl), _text(c.claimant, rtl), _text(c.claim_type, rtl), _text(c.status, rtl)]
        for c in model.claims
    ]
    return _grid_table(header, rows, rtl)


def _attachments_summary(model: ApplicationPrintModel, include_attachments: bool) -> str:
    counts = tr(
        "print.attachments_counts",
        id_docs=model.id_documents_count, evidence=model.evidence_count,
    )
    attached = tr("print.attachments_included") if include_attachments else tr("print.attachments_not_included")
    return _note(f"{counts} — {attached}")


def _signatures(rtl: bool) -> str:
    labels = [tr("print.signature.applicant"), tr("print.signature.officer"), tr("print.signature.date")]
    cells = [
        f'<td width="33%" valign="top">{escape(label)}<br><br>'
        f'<span style="color: #6B7280;">______________________</span></td>'
        for label in labels
    ]
    return f'<table width="100%" cellspacing="0" cellpadding="6" style="margin-top: 24px;">{_row(cells, rtl)}</table>'


def _note(text: str) -> str:
    return f'<p style="color: #374151;">{escape(text)}</p>'
