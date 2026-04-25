# -*- coding: utf-8 -*-
"""Conflict classification helper.

Robustly determines whether a conflict should be displayed as a Person or
Property duplicate by examining both entityType and conflictType — so a
conflict with entityType=Person always opens the person comparison UI even
when conflictType is not "PersonDuplicate".
"""

from typing import Any, Dict
from utils.logger import get_logger

logger = get_logger(__name__)


PERSON = "person"
PROPERTY = "property"
UNKNOWN = "unknown"


_PERSON_ENTITY_TYPES = {"person", "persons"}
_PROPERTY_ENTITY_TYPES = {
    "propertyunit", "property_unit", "propertyunits",
    "building", "buildings", "property",
}

_PERSON_CONFLICT_TYPES = {"personduplicate", "persons_duplicate"}
_PROPERTY_CONFLICT_TYPES = {
    "propertyduplicate", "propertyunitduplicate", "buildingduplicate",
}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "")


def get_conflict_display_category(conflict: Dict) -> str:
    """Return "person" | "property" | "unknown" for a conflict dict.

    Decision priority:
      1. entityType (wins — Person entity always = person UI)
      2. conflictType
      3. firstEntityType / secondEntityType
      4. unknown (caller treats as property for safety, but we log it)
    """
    if not isinstance(conflict, dict):
        return UNKNOWN

    entity_type = _norm(conflict.get("entityType"))
    if entity_type in _PERSON_ENTITY_TYPES:
        return PERSON
    if entity_type in _PROPERTY_ENTITY_TYPES:
        return PROPERTY

    conflict_type = _norm(conflict.get("conflictType"))
    if conflict_type in _PERSON_CONFLICT_TYPES:
        return PERSON
    if conflict_type in _PROPERTY_CONFLICT_TYPES:
        return PROPERTY

    first_type = _norm(conflict.get("firstEntityType"))
    second_type = _norm(conflict.get("secondEntityType"))
    for t in (first_type, second_type):
        if t in _PERSON_ENTITY_TYPES:
            return PERSON
        if t in _PROPERTY_ENTITY_TYPES:
            return PROPERTY

    logger.info(
        "Conflict category unknown: id=%s entityType=%s conflictType=%s",
        conflict.get("id", "?"), conflict.get("entityType"), conflict.get("conflictType"),
    )
    return UNKNOWN
