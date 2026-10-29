# -*- coding: utf-8 -*-
"""
User-facing wording for import-package validation messages.

The backend's staging validators report in English technical text
(e.g. "GovernorateCode is required"). Users see the translated line built
here; the raw text is only offered through "copy details for support".
Unrecognised messages fall back to a generic line — add a rule or a field
key (import_error.field.<Name> in ar.py / en.py) when the backend gains a
new message. Mirrors the dashboard's core/utils/import-error-messages.ts.
"""

import json
import re
from typing import Any, Callable, List, Optional, Tuple

from services.translation_manager import tr

# Entity types as named by the backend (staging groups and references)
ENTITY_TYPES = (
    "Survey", "Building", "PropertyUnit", "Person", "Household",
    "PersonPropertyRelation", "Claim", "Evidence", "BuildingDocument",
    "IdentificationDocument",
)

# Field names that appear in validator messages
_FIELDS = {
    "GovernorateCode", "DistrictCode", "SubDistrictCode", "CommunityCode",
    "NeighborhoodCode", "BuildingNumber", "BuildingStatus", "BuildingType",
    "NumberOfPropertyUnits", "NumberOfApartments", "NumberOfShops",
    "UnitIdentifier", "PropertyUnitStatus", "PropertyUnitType",
    "FirstNameArabic", "FatherNameArabic", "FamilyNameArabic", "SurveyDate",
    "ClaimSource", "ClaimType", "RelationType", "DocumentType", "EvidenceType",
    "OriginalFileName", "Latitude", "Longitude",
}


def entity_label(entity_type: str) -> str:
    """Translated record type ("Person" → شخص); the raw name when unknown."""
    return tr(f"import_error.entity.{entity_type}") if entity_type in ENTITY_TYPES else entity_type


def _field(name: str) -> Optional[str]:
    return tr(f"import_error.field.{name}") if name in _FIELDS else None


def _entity(name: str) -> Optional[str]:
    return tr(f"import_error.entity.{name}") if name in ENTITY_TYPES else None


def _with(key: str, **parts: Optional[str]) -> Optional[str]:
    """tr(key, **parts), or None when a part couldn't be translated."""
    if any(v is None for v in parts.values()):
        return None
    return tr(key, **parts)


_Rule = Tuple["re.Pattern[str]", Callable[["re.Match[str]"], Optional[str]]]

_RULES: List[_Rule] = [
    (re.compile(r"^Original(\w+)Id is required$"),
     lambda m: _with("import_error.link_missing", entity=_entity(m[1]))),
    (re.compile(r"^(\w+) is required$"),
     lambda m: _with("import_error.required", field=_field(m[1]))),
    (re.compile(r"^(\w+) must be (\d+) digits$"),
     lambda m: _with("import_error.digits", field=_field(m[1]), count=m[2])),
    (re.compile(r"^(\w+) cannot be negative$"),
     lambda m: _with("import_error.negative", field=_field(m[1]))),
    (re.compile(r"^(?:Invalid (\w+):|Unknown (\w+) value:)"),
     lambda m: _with("import_error.invalid_value", field=_field(m[1] or m[2]))),
    (re.compile(r"^(Latitude|Longitude) .*outside Syria bounds"),
     lambda m: _with("import_error.outside_syria", field=_field(m[1]))),
    (re.compile(r"^Latitude and Longitude must be provided together$"),
     lambda m: tr("import_error.lat_lng_together")),
    (re.compile(r"^SurveyDate .* is in the future$"),
     lambda m: tr("import_error.survey_date_future")),
    (re.compile(r"^DateOfBirth .* seems invalid$"),
     lambda m: tr("import_error.birth_date_invalid")),
    (re.compile(r"^NationalId length .* exceeds expected maximum$"),
     lambda m: tr("import_error.national_id_too_long")),
    (re.compile(r"^OwnershipShare must be 0-2400"),
     lambda m: tr("import_error.ownership_share_range")),
    (re.compile(r"^Apartments \+ Shops exceeds total PropertyUnits$"),
     lambda m: tr("import_error.units_exceeded")),
    (re.compile(r"^AreaSquareMeters should be positive$"),
     lambda m: tr("import_error.area_positive")),
    (re.compile(r"^HouseholdSize must be > 0$"),
     lambda m: tr("import_error.household_size_positive")),
    (re.compile(r"^Gender counts cannot be negative$"),
     lambda m: tr("import_error.gender_counts_negative")),
    (re.compile(r"^Property unit reported empty but HouseholdSize"),
     lambda m: tr("import_error.empty_with_members")),
    (re.compile(r"^Property unit reported empty without a justification"),
     lambda m: tr("import_error.empty_without_reason")),
    (re.compile(r"^EmptyPropertyJustification must not exceed"),
     lambda m: tr("import_error.empty_reason_too_long")),
    (re.compile(r"^Referenced (\w+) .* not found in batch$"),
     lambda m: _with("import_error.reference_missing", entity=_entity(m[1]))),
    (re.compile(r"references (\w+) .* which does not exist in the package"),
     lambda m: _with("import_error.reference_missing", entity=_entity(m[1]))),
    (re.compile(r"^Evidence has no linked Person, Relation, or Claim$"),
     lambda m: tr("import_error.evidence_unlinked")),
    (re.compile(r"^FileSizeBytes is 0 or negative$"),
     lambda m: tr("import_error.file_size_invalid")),
    (re.compile(r"^(?:File '.*' is not present in server storage|No file stored for)"),
     lambda m: tr("import_error.file_missing")),
    (re.compile(r"^Composite building ID .*(?:non-digit|expected 17)"),
     lambda m: tr("import_error.building_code_invalid")),
    (re.compile(r"^Provided BuildingId .* doesn't match computed"),
     lambda m: tr("import_error.building_code_mismatch")),
    (re.compile(r"^Duplicate building code .* in batch$"),
     lambda m: tr("import_error.building_code_duplicate")),
    (re.compile(r"^Duplicate unit identifier .* within building"),
     lambda m: tr("import_error.unit_duplicate")),
    (re.compile(r"^ClaimSource=.*expected Field"),
     lambda m: tr("import_error.claim_source_invalid")),
]


def translate_import_error(raw: str) -> str:
    """Translated wording for one backend validation message (generic line when unknown)."""
    text = (raw or "").strip()
    for pattern, build in _RULES:
        m = pattern.search(text)
        if m:
            translated = build(m)
            if translated:
                return translated
    return tr("import_error.unknown")


def parse_import_messages(raw: Any) -> List[str]:
    """Staging validationErrors / validationWarnings arrive as a JSON-encoded string array."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return [str(raw)]
    if isinstance(parsed, list):
        return [str(x) for x in parsed if str(x).strip()]
    return [str(raw)]
