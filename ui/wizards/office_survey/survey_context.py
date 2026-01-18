# -*- coding: utf-8 -*-
"""
Survey Context - Manages state and data for office survey wizard.

This context extends WizardContext with survey-specific data:
- Building and unit selection
- Household information
- Persons and relations
- Claim data
"""

from typing import Optional, Dict, List, Any, TYPE_CHECKING
from datetime import datetime

from ui.wizards.framework import WizardContext
from models.building import Building
from models.unit import PropertyUnit as Unit

if TYPE_CHECKING:
    from repositories.database import Database


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
        ctx.clerk_id = data.get("clerk_id")

        # Note: Building and Unit objects would need to be restored from repository
        # based on the stored IDs. This should be done by the wizard on load.

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
