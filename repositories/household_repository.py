# -*- coding: utf-8 -*-
"""
Household repository for database operations.
"""

from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

from models.household import Household
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class HouseholdRepository:
    """Repository for Household CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, household: Household) -> Household:
        """Create a new household record."""
        query = """
            INSERT INTO households (
                household_id, unit_id, main_occupant_id, main_occupant_name,
                occupancy_size, male_count, female_count,
                minors_count, adults_count, elderly_count, with_disability_count,
                occupancy_type, occupancy_nature, occupancy_start_date,
                monthly_rent, notes,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            household.household_id, household.unit_id,
            household.main_occupant_id, household.main_occupant_name,
            household.occupancy_size, household.male_count, household.female_count,
            household.minors_count, household.adults_count, household.elderly_count,
            household.with_disability_count,
            household.occupancy_type, household.occupancy_nature,
            household.occupancy_start_date.isoformat() if household.occupancy_start_date else None,
            float(household.monthly_rent) if household.monthly_rent else None,
            household.notes,
            household.created_at.isoformat() if household.created_at else None,
            household.updated_at.isoformat() if household.updated_at else None,
            household.created_by, household.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created household: {household.household_id}")
        return household

    def get_by_id(self, household_id: str) -> Optional[Household]:
        """Get household by ID."""
        query = "SELECT * FROM households WHERE household_id = ?"
        row = self.db.fetch_one(query, (household_id,))
        if row:
            return self._row_to_household(row)
        return None

    def get_by_unit(self, unit_id: str) -> List[Household]:
        """Get all households for a unit."""
        query = "SELECT * FROM households WHERE unit_id = ? ORDER BY created_at DESC"
        rows = self.db.fetch_all(query, (unit_id,))
        return [self._row_to_household(row) for row in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Household]:
        """Get all households with pagination."""
        query = "SELECT * FROM households ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_household(row) for row in rows]

    def search(self, unit_id: str = None, occupancy_type: str = None,
               occupancy_nature: str = None, limit: int = 100) -> List[Household]:
        """Search households with filters."""
        query = "SELECT * FROM households WHERE 1=1"
        params = []

        if unit_id:
            query += " AND unit_id = ?"
            params.append(unit_id)

        if occupancy_type:
            query += " AND occupancy_type = ?"
            params.append(occupancy_type)

        if occupancy_nature:
            query += " AND occupancy_nature = ?"
            params.append(occupancy_nature)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_household(row) for row in rows]

    def count(self) -> int:
        """Count total households."""
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM households")
        return result["count"] if result else 0

    def count_by_unit(self, unit_id: str) -> int:
        """Count households for a unit."""
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM households WHERE unit_id = ?",
            (unit_id,)
        )
        return result["count"] if result else 0

    def get_unit_occupancy_stats(self, unit_id: str) -> dict:
        """Get aggregated occupancy statistics for a unit."""
        query = """
            SELECT
                COUNT(*) as household_count,
                COALESCE(SUM(occupancy_size), 0) as total_occupants,
                COALESCE(SUM(male_count), 0) as total_males,
                COALESCE(SUM(female_count), 0) as total_females,
                COALESCE(SUM(minors_count), 0) as total_minors,
                COALESCE(SUM(adults_count), 0) as total_adults,
                COALESCE(SUM(elderly_count), 0) as total_elderly,
                COALESCE(SUM(with_disability_count), 0) as total_with_disability
            FROM households WHERE unit_id = ?
        """
        result = self.db.fetch_one(query, (unit_id,))
        if result:
            return dict(result)
        return {
            "household_count": 0,
            "total_occupants": 0,
            "total_males": 0,
            "total_females": 0,
            "total_minors": 0,
            "total_adults": 0,
            "total_elderly": 0,
            "total_with_disability": 0,
        }

    def update(self, household: Household) -> Household:
        """Update an existing household."""
        household.updated_at = datetime.now()
        query = """
            UPDATE households SET
                unit_id = ?, main_occupant_id = ?, main_occupant_name = ?,
                occupancy_size = ?, male_count = ?, female_count = ?,
                minors_count = ?, adults_count = ?, elderly_count = ?,
                with_disability_count = ?,
                occupancy_type = ?, occupancy_nature = ?,
                occupancy_start_date = ?, monthly_rent = ?, notes = ?,
                updated_at = ?, updated_by = ?
            WHERE household_id = ?
        """
        params = (
            household.unit_id, household.main_occupant_id, household.main_occupant_name,
            household.occupancy_size, household.male_count, household.female_count,
            household.minors_count, household.adults_count, household.elderly_count,
            household.with_disability_count,
            household.occupancy_type, household.occupancy_nature,
            household.occupancy_start_date.isoformat() if household.occupancy_start_date else None,
            float(household.monthly_rent) if household.monthly_rent else None,
            household.notes,
            household.updated_at.isoformat(), household.updated_by,
            household.household_id
        )
        self.db.execute(query, params)
        logger.debug(f"Updated household: {household.household_id}")
        return household

    def delete(self, household_id: str) -> bool:
        """Delete a household by ID."""
        query = "DELETE FROM households WHERE household_id = ?"
        self.db.execute(query, (household_id,))
        return self.get_by_id(household_id) is None

    def delete_by_unit(self, unit_id: str) -> int:
        """Delete all households for a unit. Returns count of deleted records."""
        count_result = self.db.fetch_one(
            "SELECT COUNT(*) as c FROM households WHERE unit_id = ?", (unit_id,))
        count = count_result['c'] if count_result else 0
        self.db.execute("DELETE FROM households WHERE unit_id = ?", (unit_id,))
        return count

    def _row_to_household(self, row) -> Household:
        """Convert database row to Household object."""
        data = dict(row)

        # Handle date field
        if data.get("occupancy_start_date"):
            data["occupancy_start_date"] = date.fromisoformat(data["occupancy_start_date"])

        # Handle datetime fields
        for field_name in ["created_at", "updated_at"]:
            if data.get(field_name):
                data[field_name] = datetime.fromisoformat(data[field_name])

        # Handle Decimal
        if data.get("monthly_rent") is not None:
            data["monthly_rent"] = Decimal(str(data["monthly_rent"]))

        return Household(**{k: v for k, v in data.items() if k in Household.__dataclass_fields__})
