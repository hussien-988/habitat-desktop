# -*- coding: utf-8 -*-
"""Help content registry."""

from app.config import Pages


OFFICE_SURVEY_WIZARD_ID = "office_survey_wizard"


HELP_PAGES = {
    Pages.BUILDINGS: 4,
    Pages.UNITS: 3,
    Pages.PERSONS: 3,
    Pages.HOUSEHOLDS: 3,
    Pages.RELATIONS: 3,
    Pages.CLAIMS: 4,
    Pages.SURVEYS: 4,
    Pages.CASE_MANAGEMENT: 3,
    Pages.DUPLICATES: 4,
    Pages.CLAIM_EDIT: 4,
    Pages.CLAIM_COMPARISON: 3,
    Pages.FIELD_ASSIGNMENT: 5,
    Pages.IMPORT_PACKAGES: 3,
    Pages.IMPORT_WIZARD: 6,
    Pages.SYNC_DATA: 3,
    OFFICE_SURVEY_WIZARD_ID: 7,
}


def has_help(page_id: str) -> bool:
    return page_id in HELP_PAGES


def get_keys(page_id: str):
    n = HELP_PAGES.get(page_id)
    if n is None:
        return None
    return (
        f"help.{page_id}.title",
        f"help.{page_id}.description",
        [f"help.{page_id}.step.{i + 1}" for i in range(n)],
    )
