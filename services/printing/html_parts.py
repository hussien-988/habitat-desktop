# -*- coding: utf-8 -*-
"""
Building blocks of the printed documents (claim application, case report).

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

from services.translation_manager import tr

LOGO_RESOURCE = "logo"

TITLE_COLOR = "#1B3A5C"
TEXT_COLOR = "#111827"
MUTED_COLOR = "#4B5563"
DRAFT_COLOR = "#B91C1C"
_SECTION_BG = "#E8F1FB"
_BORDER_COLOR = "#9DB4CC"
_LABEL_BG = "#F5F8FC"

_ARABIC = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LTR_EMBEDDING, _POP_DIRECTIONAL = "‪", "‬"


def document(parts: List[str]) -> str:
    return f'<html><body style="font-size: 9pt; color: {TEXT_COLOR};">{"".join(parts)}</body></html>'


def row(cells: List[str], rtl: bool) -> str:
    """Table row with cells in reading order (mirrored for RTL)."""
    return "<tr>" + "".join(reversed(cells) if rtl else cells) + "</tr>"


def text(value, rtl: bool) -> str:
    """Escaped cell text; in RTL, values without Arabic letters (dates,
    codes, numbers, Latin names) are embedded as LTR so they keep their order."""
    value = "" if value is None else str(value).strip()
    if not value:
        return "—"
    if rtl and not _ARABIC.search(value):
        value = f"{_LTR_EMBEDDING}{value}{_POP_DIRECTIONAL}"
    return escape(value)


def header(title: str, info: List[Tuple[str, str]], rtl: bool) -> str:
    """Logo, title and the document's key facts (label, already-escaped value)."""
    info_rows = "".join(
        row([f'<td style="color: {MUTED_COLOR};">{escape(label)}:</td>', f"<td>{value}</td>"], rtl)
        for label, value in info
    )
    cells = [
        f'<td width="84" valign="middle"><img src="{LOGO_RESOURCE}" width="72" height="72"></td>',
        '<td valign="middle">'
        f'<p style="font-size: 16pt; font-weight: bold; color: {TITLE_COLOR};">{escape(title)}</p>'
        f'<p style="color: {MUTED_COLOR};">{escape(tr("print.system_name"))} — UN-Habitat</p></td>',
        f'<td valign="middle"><table cellspacing="0" cellpadding="2">{info_rows}</table></td>',
    ]
    return f'<table width="100%" cellspacing="0" cellpadding="0">{row(cells, rtl)}</table>'


def section(title: str, body: str) -> str:
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


def grid_table(columns: List[str], rows: List[List[str]], rtl: bool) -> str:
    """Table with a header row; `rows` hold already-escaped cell text."""
    head = row([f'<td bgcolor="{_LABEL_BG}" style="font-weight: bold;">{escape(c)}</td>' for c in columns], rtl)
    body = "".join(row([f"<td>{cell}</td>" for cell in cells], rtl) for cells in rows)
    return _bordered_table(head + body)


def rows_table(rows: List[Tuple[str, str]], rtl: bool) -> str:
    """Label/value pairs laid out two pairs per line."""
    if not rows:
        return note("—")
    cells = []
    for label, value in rows:
        cells.append(f'<td bgcolor="{_LABEL_BG}" width="18%" style="font-weight: bold;">{escape(label)}</td>')
        cells.append(f'<td width="32%">{text(value, rtl)}</td>')
    if len(cells) % 4:
        cells.extend(["<td></td>", "<td></td>"])
    return _bordered_table("".join(row(cells[i:i + 4], rtl) for i in range(0, len(cells), 4)))


def claims_table(claims, rtl: bool) -> str:
    """Claim number, claimant, type and status of each claim (ClaimRow)."""
    columns = [
        tr("print.col.claim_number"), tr("print.col.claimant"),
        tr("print.col.claim_type"), tr("print.col.status"),
    ]
    rows = [
        [text(c.number, rtl), text(c.claimant, rtl), text(c.claim_type, rtl), text(c.status, rtl)]
        for c in claims
    ]
    return grid_table(columns, rows, rtl)


def signatures(labels: List[str], rtl: bool) -> str:
    width = 100 // len(labels)
    cells = [
        f'<td width="{width}%" valign="top">{escape(label)}<br><br>'
        f'<span style="color: #6B7280;">______________________</span></td>'
        for label in labels
    ]
    return f'<table width="100%" cellspacing="0" cellpadding="6" style="margin-top: 24px;">{row(cells, rtl)}</table>'


def note(message: str) -> str:
    return f'<p style="color: #374151;">{escape(message)}</p>'
