# -*- coding: utf-8 -*-
"""
Survey Context - Manages state and data for office survey wizard.

This context extends WizardContext with survey-specific data:
- Building and unit selection
- Household information
- Persons and relations
- Claim data
"""

import logging
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from datetime import datetime

from ui.wizards.framework import WizardContext
from models.building import Building
from models.unit import PropertyUnit as Unit

if TYPE_CHECKING:
    from repositories.database import Database

logger = logging.getLogger(__name__)


class SurveyContext(WizardContext):
    """Context for office survey wizard (UC-004)."""

    def __init__(self, db: 'Database' = None):
        """Initialize survey context."""
        super().__init__()
        if db is None:
            from repositories.database import Database
            db = Database()
        self.db = db

        # Selected entities
        self.building: Optional[Building] = None
        self.unit: Optional[Unit] = None
        self.is_new_unit: bool = False
        self.new_unit_data: Optional[Dict] = None

        # Household data
        self.households: List[Dict] = []

        # Persons and relations
        self.persons: List[Dict] = []
        self.relations: List[Dict] = []

        # Claim data
        self.claim_data: Optional[Dict] = None
        self.claims: List[Dict] = []

        # Finalize survey API response (from Step 5 -> Step 6 transition)
        self.finalize_response: Optional[Dict] = None

        # Clerk information
        self.clerk_id: Optional[str] = None

    def _get_reference_prefix(self) -> str:
        """Override to use survey-specific prefix."""
        return "SRV"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary."""
        # Get base fields
        base_data = super().to_dict()

        # Add survey-specific fields
        survey_data = {
            "building_id": self.building.building_id if self.building else None,
            "building_uuid": self.building.building_uuid if self.building else None,
            "unit_id": self.unit.unit_id if self.unit else None,
            "unit_uuid": self.unit.unit_uuid if self.unit else None,
            "is_new_unit": self.is_new_unit,
            "new_unit_data": self.new_unit_data,
            "households": self.households,
            "persons": self.persons,
            "relations": self.relations,
            "claim_data": self.claim_data,
            "claims": self.claims,
            "finalize_response": self.finalize_response,
            "clerk_id": self.clerk_id
        }

        # Merge and return
        base_data.update(survey_data)
        return base_data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SurveyContext':
        """Restore context from dictionary."""
        ctx = cls()

        # Restore base fields
        cls._restore_base_fields(ctx, data)

        # Restore survey-specific fields
        ctx.is_new_unit = data.get("is_new_unit", False)
        ctx.new_unit_data = data.get("new_unit_data")
        ctx.households = data.get("households", [])
        ctx.persons = data.get("persons", [])
        ctx.relations = data.get("relations", [])
        ctx.claim_data = data.get("claim_data")
        ctx.claims = data.get("claims", [])
        ctx.finalize_response = data.get("finalize_response")
        ctx.clerk_id = data.get("clerk_id")

        building_data = data.get("building")
        if building_data and isinstance(building_data, dict):
            try:
                ctx.building = Building.from_dict(building_data)
            except Exception as e:
                logger.warning(f"Failed to restore building: {e}")

        unit_data = data.get("unit")
        if unit_data and isinstance(unit_data, dict):
            try:
                ctx.unit = Unit.from_dict(unit_data)
            except Exception as e:
                logger.warning(f"Failed to restore unit: {e}")

        return ctx

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def set_building(self, building: Building):
        """Set the selected building."""
        self.building = building
        self.update_data("building_selected", True)

    def set_unit(self, unit: Unit, is_new: bool = False):
        """Set the selected unit."""
        self.unit = unit
        self.is_new_unit = is_new
        self.update_data("unit_selected", True)

    def add_person(self, person_data: Dict):
        """Add a person to the survey."""
        self.persons.append(person_data)
        self.update_data("persons_count", len(self.persons))

    def add_relation(self, relation_data: Dict):
        """Add a person-unit relation."""
        self.relations.append(relation_data)
        self.update_data("relations_count", len(self.relations))

    def add_household(self, household_data: Dict):
        """Add household information."""
        self.households.append(household_data)
        self.update_data("households_count", len(self.households))

    def set_claim_data(self, claim_data: Dict):
        """Set claim information."""
        self.claim_data = claim_data
        self.update_data("claim_created", True)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the survey data for review."""
        return {
            "reference_number": self.reference_number,
            "building": {
                "id": self.building.building_id if self.building else None,
                "address": getattr(self.building, "address", None) if self.building else None
            },
            "unit": {
                "id": self.unit.unit_id if self.unit else None,
                "type": getattr(self.unit, "unit_type", None) if self.unit else None,
                "is_new": self.is_new_unit
            },
            "households_count": len(self.households),
            "persons_count": len(self.persons),
            "relations_count": len(self.relations),
            "has_claim": self.claim_data is not None,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }

    def cleanup_on_building_change(self, api_client) -> None:
        """Full cleanup when building changes. Deletes everything from API.
        Order: Relations (cascade deletes evidence) -> Persons -> Household."""
        survey_id = self.get_data("survey_id")
        if not survey_id:
            return

        self._delete_relations_from_api(api_client, survey_id)
        self._delete_persons_from_api(api_client)
        self._delete_household_from_api(api_client, survey_id)

        self.persons = []
        self.relations = []
        self.households = []
        self.claims = []
        self.finalize_response = None
        for key in ("household_id", "unit_linked", "linked_unit_uuid",
                    "claims_count", "created_claims"):
            self.update_data(key, None)

    def cleanup_on_unit_change(self, api_client) -> None:
        """Partial cleanup when unit changes. Deletes relations only.
        Persons and household stay (they belong to the survey/household)."""
        survey_id = self.get_data("survey_id")
        if not survey_id:
            return

        self._delete_relations_from_api(api_client, survey_id)

        for person in self.persons:
            person['_relation_id'] = None

        self.relations = []
        self.claims = []
        self.finalize_response = None
        for key in ("unit_linked", "linked_unit_uuid",
                    "claims_count", "created_claims"):
            self.update_data(key, None)

    def _delete_relations_from_api(self, api_client, survey_id: str) -> None:
        """Delete all person-unit relations from API."""
        for person in self.persons:
            relation_id = person.get('_relation_id')
            if relation_id:
                try:
                    api_client.delete_relation(survey_id, relation_id)
                except Exception as e:
                    logger.warning(f"Failed to delete relation {relation_id}: {e}")

    def _delete_persons_from_api(self, api_client) -> None:
        """Delete all persons from API."""
        for person in self.persons:
            person_id = person.get('person_id')
            if person_id:
                try:
                    api_client.delete_person(person_id)
                except Exception as e:
                    logger.warning(f"Failed to delete person {person_id}: {e}")

    def _delete_household_from_api(self, api_client, survey_id: str) -> None:
        """Delete household from API."""
        household_id = self.get_data("household_id")
        if household_id:
            try:
                api_client.delete_household(household_id, survey_id)
            except Exception as e:
                logger.warning(f"Failed to delete household {household_id}: {e}")
