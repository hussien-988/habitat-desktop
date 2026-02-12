# -*- coding: utf-8 -*-
"""Centralized display mappings for status/type dictionaries (DRY)."""

from services.translation_manager import tr


def get_building_type_display(type_key) -> str:
    _str_map = {
        "residential": "mapping.building_type.residential",
        "commercial": "mapping.building_type.commercial",
        "mixed_use": "mapping.building_type.mixed_use",
        "industrial": "mapping.building_type.industrial",
        "public": "mapping.building_type.public",
    }
    _int_map = {
        1: "mapping.building_type.residential",
        2: "mapping.building_type.commercial",
        3: "mapping.building_type.mixed_use",
        4: "mapping.building_type.industrial",
    }
    if isinstance(type_key, int):
        key = _int_map.get(type_key)
    else:
        key = _str_map.get(str(type_key).lower() if type_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_building_status_display(status_key) -> str:
    _str_map = {
        "intact": "mapping.building_status.intact",
        "standing": "mapping.building_status.intact",
        "minor_damage": "mapping.building_status.minor_damage",
        "minordamage": "mapping.building_status.minor_damage",
        "moderate_damage": "mapping.building_status.moderate_damage",
        "moderatedamage": "mapping.building_status.moderate_damage",
        "damaged": "mapping.building_status.moderate_damage",
        "partially_damaged": "mapping.building_status.moderate_damage",
        "major_damage": "mapping.building_status.major_damage",
        "majordamage": "mapping.building_status.major_damage",
        "severely_damaged": "mapping.building_status.severely_damaged",
        "severelydamaged": "mapping.building_status.severely_damaged",
        "destroyed": "mapping.building_status.destroyed",
        "demolished": "mapping.building_status.destroyed",
        "rubble": "mapping.building_status.destroyed",
        "under_construction": "mapping.building_status.under_construction",
        "underconstruction": "mapping.building_status.under_construction",
        "abandoned": "mapping.building_status.abandoned",
        "unknown": "mapping.building_status.unknown",
    }
    _int_map = {
        1: "mapping.building_status.intact",
        2: "mapping.building_status.minor_damage",
        3: "mapping.building_status.moderate_damage",
        4: "mapping.building_status.major_damage",
        5: "mapping.building_status.severely_damaged",
        6: "mapping.building_status.destroyed",
        7: "mapping.building_status.under_construction",
        8: "mapping.building_status.abandoned",
        99: "mapping.building_status.unknown",
    }
    if isinstance(status_key, int):
        key = _int_map.get(status_key)
    else:
        key = _str_map.get(str(status_key).lower() if status_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_unit_type_display(type_key) -> str:
    _str_map = {
        "apartment": "mapping.unit_type.apartment",
        "shop": "mapping.unit_type.shop",
        "office": "mapping.unit_type.office",
        "warehouse": "mapping.unit_type.warehouse",
        "garage": "mapping.unit_type.garage",
        "other": "mapping.unit_type.other",
    }
    _int_map = {
        1: "mapping.unit_type.apartment",
        2: "mapping.unit_type.shop",
        3: "mapping.unit_type.office",
        4: "mapping.unit_type.warehouse",
        5: "mapping.unit_type.other",
    }
    if isinstance(type_key, int):
        key = _int_map.get(type_key)
    else:
        key = _str_map.get(str(type_key).lower() if type_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_unit_status_display(status_key) -> str:
    _str_map = {
        "occupied": "mapping.unit_status.occupied",
        "vacant": "mapping.unit_status.vacant",
        "damaged": "mapping.unit_status.damaged",
        "under_renovation": "mapping.unit_status.under_renovation",
        "uninhabitable": "mapping.unit_status.uninhabitable",
        "locked": "mapping.unit_status.locked",
        "unknown": "mapping.unit_status.unknown",
    }
    _int_map = {
        1: "mapping.unit_status.occupied",
        2: "mapping.unit_status.vacant",
        3: "mapping.unit_status.damaged",
        4: "mapping.unit_status.under_renovation",
        5: "mapping.unit_status.uninhabitable",
        6: "mapping.unit_status.locked",
        99: "mapping.unit_status.unknown",
    }
    if isinstance(status_key, int):
        key = _int_map.get(status_key)
    else:
        key = _str_map.get(str(status_key).lower() if status_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_relation_type_display(rel_key) -> str:
    _map = {
        "owner": "mapping.relation_type.owner",
        "co_owner": "mapping.relation_type.co_owner",
        "tenant": "mapping.relation_type.tenant",
        "occupant": "mapping.relation_type.occupant",
        "heir": "mapping.relation_type.heir",
        "guardian": "mapping.relation_type.guardian",
        "head": "mapping.relation_type.head",
        "spouse": "mapping.relation_type.spouse",
        "child": "mapping.relation_type.child",
        "relative": "mapping.relation_type.relative",
        "worker": "mapping.relation_type.worker",
        "other": "mapping.relation_type.other",
    }
    key = _map.get(str(rel_key).lower() if rel_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_relation_type_options() -> list:
    return [
        ("owner", tr("mapping.relation_type.owner")),
        ("co_owner", tr("mapping.relation_type.co_owner")),
        ("tenant", tr("mapping.relation_type.tenant")),
        ("occupant", tr("mapping.relation_type.occupant")),
        ("heir", tr("mapping.relation_type.heir")),
        ("guardian", tr("mapping.relation_type.guardian")),
        ("other", tr("mapping.relation_type.other")),
    ]


def get_contract_type_options() -> list:
    return [
        ("", tr("mapping.select")),
        ("lease", tr("mapping.contract_type.lease")),
        ("sale", tr("mapping.contract_type.sale")),
        ("partnership", tr("mapping.contract_type.partnership")),
    ]


def get_evidence_type_options() -> list:
    return [
        ("", tr("mapping.select")),
        ("deed", tr("mapping.evidence_type.deed")),
        ("contract", tr("mapping.evidence_type.contract")),
        ("proxy", tr("mapping.evidence_type.proxy")),
        ("acknowledgment", tr("mapping.evidence_type.acknowledgment")),
    ]


def get_claim_type_display(claim_key) -> str:
    _map = {
        "ownership": "mapping.claim_type.ownership",
        "occupancy": "mapping.claim_type.occupancy",
        "tenancy": "mapping.claim_type.tenancy",
    }
    key = _map.get(str(claim_key).lower() if claim_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_priority_display(priority_key) -> str:
    _map = {
        "low": "mapping.priority.low",
        "normal": "mapping.priority.normal",
        "high": "mapping.priority.high",
        "urgent": "mapping.priority.urgent",
    }
    key = _map.get(str(priority_key).lower() if priority_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_business_type_display(btype_key) -> str:
    _map = {
        "residential": "mapping.business_type.residential",
        "commercial": "mapping.business_type.commercial",
        "agricultural": "mapping.business_type.agricultural",
    }
    key = _map.get(str(btype_key).lower() if btype_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_source_display(source_key) -> str:
    _map = {
        "field_survey": "mapping.source.field_survey",
        "direct_request": "mapping.source.direct_request",
        "referral": "mapping.source.referral",
        "office_submission": "mapping.source.office_submission",
        "OFFICE_SUBMISSION": "mapping.source.office_submission",
    }
    key = _map.get(str(source_key) if source_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_claim_status_display(status_key) -> str:
    _map = {
        "new": "mapping.claim_status.new",
        "under_review": "mapping.claim_status.under_review",
        "completed": "mapping.claim_status.completed",
        "pending": "mapping.claim_status.pending",
        "draft": "mapping.claim_status.draft",
    }
    key = _map.get(str(status_key).lower() if status_key else "")
    return tr(key) if key else tr("mapping.not_specified")
