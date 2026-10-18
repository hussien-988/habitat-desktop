# -*- coding: utf-8 -*-
"""
Contact Point / Rights Claimant badges — جهة الاتصال / صاحب حق

A person can hold both designations:
- Contact Point: the survey's contact person.
- Rights Claimant: has an active relation (claim) on the unit.
"""

from typing import Optional, Tuple

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSizePolicy

from services.translation_manager import tr
from ui.font_utils import FontManager, create_font

CONTACT_POINT = "contact_point"
RIGHTS_CLAIMANT = "rights_claimant"

_BADGES = {
    CONTACT_POINT: ("wizard.review.designation_contact_person", "#E0F2FE", "#0369A1"),
    RIGHTS_CLAIMANT: ("wizard.review.designation_right_claimant", "#DCFCE7", "#166534"),
}


def server_designations(person: dict) -> Tuple[bool, bool]:
    """(is_contact_point, is_rights_claimant) from the server's person flags."""
    is_contact = bool(person.get("isContactPoint") or person.get("isContactPerson"))
    is_claimant = bool(person.get("isRightsClaimant"))
    return is_contact, is_claimant


def wizard_designations(person: dict, contact_person_id: Optional[str]) -> Tuple[bool, bool]:
    """(is_contact_point, is_rights_claimant) from the wizard's live state,
    by the same rules the server uses: the survey's contact person, and a
    relation (claim) on the unit."""
    person_id = str(person.get("person_id") or "").strip()
    contact_person_id = str(contact_person_id or "").strip()
    if contact_person_id:
        is_contact = bool(person_id) and person_id == contact_person_id
    else:
        is_contact = bool(person.get("_is_applicant") or person.get("_is_contact_person"))
    rel = person.get("relation_data") or {}
    is_claimant = bool(rel.get("rel_type") or rel.get("claim_type"))
    return is_contact, is_claimant


def create_designation_badge(kind: str) -> QLabel:
    key, background, color = _BADGES[kind]
    badge = QLabel(tr(key))
    badge.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
    badge.setStyleSheet(f"""
        QLabel {{
            background-color: {background};
            color: {color};
            border: none;
            border-radius: 8px;
            padding: 4px 8px;
        }}
    """)
    badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return badge


def build_designation_row(is_contact: bool, is_claimant: bool, spacing: int = 6) -> Optional[QHBoxLayout]:
    """A row with the badges the person holds, or None when it holds none."""
    if not (is_contact or is_claimant):
        return None
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(spacing)
    if is_contact:
        row.addWidget(create_designation_badge(CONTACT_POINT))
    if is_claimant:
        row.addWidget(create_designation_badge(RIGHTS_CLAIMANT))
    row.addStretch(1)
    return row
