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
    _str_map = {
        "owner": "mapping.relation_type.owner",
        "co_owner": "mapping.relation_type.co_owner",
        "tenant": "mapping.relation_type.tenant",
        "occupant": "mapping.relation_type.occupant",
        "heir": "mapping.relation_type.heir",
        "guardian": "mapping.relation_type.guardian",
        "guest": "mapping.relation_type.guest",
        "head": "mapping.relation_type.head",
        "spouse": "mapping.relation_type.spouse",
        "child": "mapping.relation_type.child",
        "relative": "mapping.relation_type.relative",
        "worker": "mapping.relation_type.worker",
        "other": "mapping.relation_type.other",
    }
    _int_map = {
        1: "mapping.relation_type.owner",
        2: "mapping.relation_type.occupant",
        3: "mapping.relation_type.tenant",
        4: "mapping.relation_type.guest",
        5: "mapping.relation_type.heir",
        99: "mapping.relation_type.other",
    }
    if isinstance(rel_key, int):
        key = _int_map.get(rel_key)
    else:
        key = _str_map.get(str(rel_key).lower() if rel_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_relation_type_options() -> list:
    return [
        (1, tr("mapping.relation_type.owner")),
        (2, tr("mapping.relation_type.occupant")),
        (3, tr("mapping.relation_type.tenant")),
        (4, tr("mapping.relation_type.guest")),
        (5, tr("mapping.relation_type.heir")),
        (99, tr("mapping.relation_type.other")),
    ]


def get_contract_type_options() -> list:
    return [
        (0, tr("mapping.select")),
        (1, tr("mapping.contract_type.full_ownership")),
        (2, tr("mapping.contract_type.shared_ownership")),
        (3, tr("mapping.contract_type.long_term_rental")),
        (4, tr("mapping.contract_type.short_term_rental")),
        (5, tr("mapping.contract_type.informal_tenure")),
        (6, tr("mapping.contract_type.unauthorized_occupation")),
        (7, tr("mapping.contract_type.customary_rights")),
        (8, tr("mapping.contract_type.inheritance_based")),
        (9, tr("mapping.contract_type.hosted_guest")),
        (10, tr("mapping.contract_type.temporary_shelter")),
        (11, tr("mapping.contract_type.government_allocation")),
        (12, tr("mapping.contract_type.usufruct")),
        (99, tr("mapping.contract_type.other")),
    ]


def get_evidence_type_options() -> list:
    return [
        (0, tr("mapping.select")),
        (1, tr("mapping.evidence_type.identification_document")),
        (2, tr("mapping.evidence_type.ownership_deed")),
        (3, tr("mapping.evidence_type.rental_contract")),
        (4, tr("mapping.evidence_type.utility_bill")),
        (5, tr("mapping.evidence_type.photo")),
        (6, tr("mapping.evidence_type.official_letter")),
        (7, tr("mapping.evidence_type.court_order")),
        (8, tr("mapping.evidence_type.inheritance_document")),
        (9, tr("mapping.evidence_type.tax_receipt")),
        (99, tr("mapping.evidence_type.other")),
    ]


def get_occupancy_type_options() -> list:
    return [
        (0, tr("mapping.select")),
        (1, tr("mapping.occupancy_type.owner_occupied")),
        (2, tr("mapping.occupancy_type.tenant_occupied")),
        (3, tr("mapping.occupancy_type.family_occupied")),
        (4, tr("mapping.occupancy_type.mixed_occupancy")),
        (5, tr("mapping.occupancy_type.vacant")),
        (6, tr("mapping.occupancy_type.temporary_seasonal")),
        (7, tr("mapping.occupancy_type.commercial_use")),
        (8, tr("mapping.occupancy_type.abandoned")),
        (9, tr("mapping.occupancy_type.disputed")),
        (99, tr("mapping.occupancy_type.unknown")),
    ]


def get_occupancy_nature_options() -> list:
    return [
        (0, tr("mapping.select")),
        (1, tr("mapping.occupancy_nature.legal_formal")),
        (2, tr("mapping.occupancy_nature.informal")),
        (3, tr("mapping.occupancy_nature.customary")),
        (4, tr("mapping.occupancy_nature.temporary_emergency")),
        (5, tr("mapping.occupancy_nature.authorized")),
        (6, tr("mapping.occupancy_nature.unauthorized")),
        (7, tr("mapping.occupancy_nature.pending_regularization")),
        (8, tr("mapping.occupancy_nature.contested")),
        (99, tr("mapping.occupancy_nature.unknown")),
    ]


def get_gender_options() -> list:
    return [
        (1, tr("mapping.gender.male")),
        (2, tr("mapping.gender.female")),
    ]


def get_nationality_options() -> list:
    return [
        (1, tr("mapping.nationality.syrian")),
        (2, tr("mapping.nationality.palestinian")),
        (3, tr("mapping.nationality.iraqi")),
        (4, tr("mapping.nationality.lebanese")),
        (5, tr("mapping.nationality.jordanian")),
        (6, tr("mapping.nationality.turkish")),
        (7, tr("mapping.nationality.egyptian")),
        (8, tr("mapping.nationality.yemeni")),
        (9, tr("mapping.nationality.sudanese")),
        (10, tr("mapping.nationality.libyan")),
        (11, tr("mapping.nationality.somali")),
        (12, tr("mapping.nationality.afghan")),
        (97, tr("mapping.nationality.stateless")),
        (98, tr("mapping.nationality.other")),
        (99, tr("mapping.nationality.unknown")),
    ]


def get_occupancy_type_display(type_key) -> str:
    _int_map = {
        1: "mapping.occupancy_type.owner_occupied",
        2: "mapping.occupancy_type.tenant_occupied",
        3: "mapping.occupancy_type.family_occupied",
        4: "mapping.occupancy_type.mixed_occupancy",
        5: "mapping.occupancy_type.vacant",
        6: "mapping.occupancy_type.temporary_seasonal",
        7: "mapping.occupancy_type.commercial_use",
        8: "mapping.occupancy_type.abandoned",
        9: "mapping.occupancy_type.disputed",
        99: "mapping.occupancy_type.unknown",
    }
    _str_map = {
        "owneroccupied": "mapping.occupancy_type.owner_occupied",
        "tenantoccupied": "mapping.occupancy_type.tenant_occupied",
        "familyoccupied": "mapping.occupancy_type.family_occupied",
        "mixedoccupancy": "mapping.occupancy_type.mixed_occupancy",
        "vacant": "mapping.occupancy_type.vacant",
        "temporaryseasonal": "mapping.occupancy_type.temporary_seasonal",
        "commercialuse": "mapping.occupancy_type.commercial_use",
        "abandoned": "mapping.occupancy_type.abandoned",
        "disputed": "mapping.occupancy_type.disputed",
        "unknown": "mapping.occupancy_type.unknown",
    }
    if isinstance(type_key, int):
        key = _int_map.get(type_key)
    else:
        key = _str_map.get(str(type_key).lower().replace("_", "") if type_key else "")
    return tr(key) if key else tr("mapping.not_specified")


def get_occupancy_nature_display(nature_key) -> str:
    _int_map = {
        1: "mapping.occupancy_nature.legal_formal",
        2: "mapping.occupancy_nature.informal",
        3: "mapping.occupancy_nature.customary",
        4: "mapping.occupancy_nature.temporary_emergency",
        5: "mapping.occupancy_nature.authorized",
        6: "mapping.occupancy_nature.unauthorized",
        7: "mapping.occupancy_nature.pending_regularization",
        8: "mapping.occupancy_nature.contested",
        99: "mapping.occupancy_nature.unknown",
    }
    _str_map = {
        "legalformal": "mapping.occupancy_nature.legal_formal",
        "informal": "mapping.occupancy_nature.informal",
        "customary": "mapping.occupancy_nature.customary",
        "temporaryemergency": "mapping.occupancy_nature.temporary_emergency",
        "authorized": "mapping.occupancy_nature.authorized",
        "unauthorized": "mapping.occupancy_nature.unauthorized",
        "pendingregularization": "mapping.occupancy_nature.pending_regularization",
        "contested": "mapping.occupancy_nature.contested",
        "unknown": "mapping.occupancy_nature.unknown",
    }
    if isinstance(nature_key, int):
        key = _int_map.get(nature_key)
    else:
        key = _str_map.get(str(nature_key).lower().replace("_", "") if nature_key else "")
    return tr(key) if key else tr("mapping.not_specified")


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
