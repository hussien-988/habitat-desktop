# -*- coding: utf-8 -*-
"""
Centralized display mappings for status/type dictionaries (DRY).

Display functions delegate to vocab_service for API-sourced labels,
with string-key fallback for legacy data. Options functions delegate
to vocab_service.get_options().
"""

from services.translation_manager import tr


# ============ Helper for vocab_service delegation ============

def _vocab_label(vocab_name: str, key, str_fallback: dict = None) -> str:
    """
    Try vocab_service first (handles int codes from API).
    Fall back to str_fallback dict for legacy string keys.
    """
    from services.vocab_service import get_label, is_initialized
    if is_initialized():
        result = get_label(vocab_name, key)
        if result != str(key):
            return result
    # Fallback for string keys not in API vocab
    if str_fallback and not isinstance(key, int):
        tr_key = str_fallback.get(str(key).lower().replace("_", "") if key else "")
        if tr_key:
            return tr(tr_key)
    return tr("mapping.not_specified")


def _vocab_options(vocab_name: str) -> list:
    """Delegate to vocab_service.get_options()."""
    from services.vocab_service import get_options
    return get_options(vocab_name)


# ============ Building Type ============

def get_building_type_display(type_key) -> str:
    _str_fallback = {
        "residential": "mapping.building_type.residential",
        "commercial": "mapping.building_type.commercial",
        "mixed_use": "mapping.building_type.mixed_use",
        "mixeduse": "mapping.building_type.mixed_use",
        "industrial": "mapping.building_type.industrial",
        "public": "mapping.building_type.public",
    }
    return _vocab_label("BuildingType", type_key, _str_fallback)


# ============ Building Status ============

def get_building_status_display(status_key) -> str:
    _str_fallback = {
        "intact": "mapping.building_status.intact",
        "standing": "mapping.building_status.intact",
        "minordamage": "mapping.building_status.minor_damage",
        "minor_damage": "mapping.building_status.minor_damage",
        "moderatedamage": "mapping.building_status.moderate_damage",
        "moderate_damage": "mapping.building_status.moderate_damage",
        "damaged": "mapping.building_status.moderate_damage",
        "partiallydamaged": "mapping.building_status.moderate_damage",
        "partially_damaged": "mapping.building_status.moderate_damage",
        "majordamage": "mapping.building_status.major_damage",
        "major_damage": "mapping.building_status.major_damage",
        "severelydamaged": "mapping.building_status.severely_damaged",
        "severely_damaged": "mapping.building_status.severely_damaged",
        "destroyed": "mapping.building_status.destroyed",
        "demolished": "mapping.building_status.destroyed",
        "rubble": "mapping.building_status.destroyed",
        "underconstruction": "mapping.building_status.under_construction",
        "under_construction": "mapping.building_status.under_construction",
        "abandoned": "mapping.building_status.abandoned",
        "unknown": "mapping.building_status.unknown",
    }
    return _vocab_label("BuildingStatus", status_key, _str_fallback)


def get_building_type_options() -> list:
    return _vocab_options("BuildingType")


def get_building_status_options() -> list:
    return _vocab_options("BuildingStatus")


# ============ Unit Type ============

def get_unit_type_display(type_key) -> str:
    _str_fallback = {
        "apartment": "mapping.unit_type.apartment",
        "shop": "mapping.unit_type.shop",
        "office": "mapping.unit_type.office",
        "warehouse": "mapping.unit_type.warehouse",
        "garage": "mapping.unit_type.garage",
        "other": "mapping.unit_type.other",
    }
    return _vocab_label("UnitType", type_key, _str_fallback)


def get_unit_type_options() -> list:
    return _vocab_options("UnitType")


# ============ Unit Status ============

def get_unit_status_display(status_key) -> str:
    _str_fallback = {
        "occupied": "mapping.unit_status.occupied",
        "vacant": "mapping.unit_status.vacant",
        "damaged": "mapping.unit_status.damaged",
        "under_renovation": "mapping.unit_status.under_renovation",
        "uninhabitable": "mapping.unit_status.uninhabitable",
        "locked": "mapping.unit_status.locked",
        "unknown": "mapping.unit_status.unknown",
    }
    return _vocab_label("UnitStatus", status_key, _str_fallback)


def get_unit_status_options() -> list:
    return _vocab_options("UnitStatus")


# ============ Relation Type ============

def get_relation_type_display(rel_key) -> str:
    _str_fallback = {
        "owner": "mapping.relation_type.owner",
        "coowner": "mapping.relation_type.co_owner",
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
    return _vocab_label("RelationType", rel_key, _str_fallback)


def get_relation_type_options() -> list:
    return _vocab_options("RelationType")


# ============ Contract Type ============

def get_contract_type_options() -> list:
    return _vocab_options("ContractType")


# ============ Evidence Type ============

def get_evidence_type_options() -> list:
    return _vocab_options("EvidenceType")


# ============ Occupancy Type ============

def get_occupancy_type_options() -> list:
    return _vocab_options("OccupancyType")


def get_occupancy_type_display(type_key) -> str:
    _str_fallback = {
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
    return _vocab_label("OccupancyType", type_key, _str_fallback)


# ============ Occupancy Nature ============

def get_occupancy_nature_options() -> list:
    return _vocab_options("OccupancyNature")


def get_occupancy_nature_display(nature_key) -> str:
    _str_fallback = {
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
    return _vocab_label("OccupancyNature", nature_key, _str_fallback)


# ============ Gender ============

def get_gender_options() -> list:
    return _vocab_options("Gender")


# ============ Nationality ============

def get_nationality_options() -> list:
    return _vocab_options("Nationality")


# ============ Claim Type ============

def get_claim_type_display(claim_key) -> str:
    _str_fallback = {
        "ownership": "mapping.claim_type.ownership",
        "occupancy": "mapping.claim_type.occupancy",
        "tenancy": "mapping.claim_type.tenancy",
    }
    return _vocab_label("ClaimType", claim_key, _str_fallback)


# ============ Priority ============

def get_priority_display(priority_key) -> str:
    _str_fallback = {
        "low": "mapping.priority.low",
        "normal": "mapping.priority.normal",
        "high": "mapping.priority.high",
        "urgent": "mapping.priority.urgent",
    }
    return _vocab_label("CasePriority", priority_key, _str_fallback)


# ============ Business Type ============

def get_business_type_display(btype_key) -> str:
    _str_fallback = {
        "residential": "mapping.business_type.residential",
        "commercial": "mapping.business_type.commercial",
        "agricultural": "mapping.business_type.agricultural",
    }
    return _vocab_label("BusinessNature", btype_key, _str_fallback)


# ============ Source ============

def get_source_display(source_key) -> str:
    _str_fallback = {
        "field_survey": "mapping.source.field_survey",
        "fieldsurvey": "mapping.source.field_survey",
        "direct_request": "mapping.source.direct_request",
        "directrequest": "mapping.source.direct_request",
        "referral": "mapping.source.referral",
        "office_submission": "mapping.source.office_submission",
        "officesubmission": "mapping.source.office_submission",
    }
    return _vocab_label("ClaimSource", source_key, _str_fallback)


# ============ Claim Status ============

def get_claim_status_display(status_key) -> str:
    _str_fallback = {
        "new": "mapping.claim_status.new",
        "underreview": "mapping.claim_status.under_review",
        "under_review": "mapping.claim_status.under_review",
        "completed": "mapping.claim_status.completed",
        "pending": "mapping.claim_status.pending",
        "draft": "mapping.claim_status.draft",
    }
    return _vocab_label("ClaimStatus", status_key, _str_fallback)
