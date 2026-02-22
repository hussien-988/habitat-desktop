# -*- coding: utf-8 -*-
"""
Person repository for database operations.
"""

from typing import List, Optional
from datetime import datetime

from models.person import Person
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonRepository:
    """Repository for Person CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, person: Person) -> Person:
        """Create a new person record."""
        query = """
            INSERT INTO persons (
                person_id, first_name, first_name_ar, father_name, father_name_ar,
                mother_name, mother_name_ar, last_name, last_name_ar,
                gender, year_of_birth, nationality, national_id, passport_number,
                phone_number, mobile_number, email, address,
                is_contact_person, is_deceased,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            person.person_id, person.first_name, person.first_name_ar,
            person.father_name, person.father_name_ar,
            person.mother_name, person.mother_name_ar,
            person.last_name, person.last_name_ar,
            person.gender, person.year_of_birth, person.nationality,
            person.national_id, person.passport_number,
            person.phone_number, person.mobile_number, person.email, person.address,
            1 if person.is_contact_person else 0,
            1 if person.is_deceased else 0,
            person.created_at.isoformat() if person.created_at else None,
            person.updated_at.isoformat() if person.updated_at else None,
            person.created_by, person.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created person: {person.person_id}")
        return person

    def get_by_id(self, person_id: str) -> Optional[Person]:
        """Get person by ID."""
        query = "SELECT * FROM persons WHERE person_id = ?"
        row = self.db.fetch_one(query, (person_id,))
        if row:
            return self._row_to_person(row)
        return None

    def get_by_national_id(self, national_id: str) -> Optional[Person]:
        """Get person by national ID."""
        query = "SELECT * FROM persons WHERE national_id = ?"
        row = self.db.fetch_one(query, (national_id,))
        if row:
            return self._row_to_person(row)
        return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Person]:
        """Get all persons with pagination."""
        query = "SELECT * FROM persons ORDER BY last_name_ar, first_name_ar LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_person(row) for row in rows]

    def search(self, name: str = None, national_id: str = None,
               gender: str = None, search_text: str = None, limit: int = 50) -> List[Person]:
        """Search persons by name, national ID, or gender."""
        query = "SELECT * FROM persons WHERE 1=1"
        params = []

        if name:
            query += """ AND (
                first_name LIKE ? OR first_name_ar LIKE ? OR
                last_name LIKE ? OR last_name_ar LIKE ?
            )"""
            pattern = f"%{name}%"
            params.extend([pattern, pattern, pattern, pattern])

        if national_id:
            query += " AND national_id LIKE ?"
            params.append(f"%{national_id}%")

        if gender:
            query += " AND gender = ?"
            params.append(gender)

        if search_text:
            query += """ AND (
                first_name LIKE ? OR first_name_ar LIKE ? OR
                last_name LIKE ? OR last_name_ar LIKE ? OR
                national_id LIKE ?
            )"""
            pattern = f"%{search_text}%"
            params.extend([pattern, pattern, pattern, pattern, pattern])

        query += " ORDER BY last_name_ar, first_name_ar LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_person(row) for row in rows]

    def get_by_unit(self, unit_id: str) -> List[Person]:
        """Get all persons related to a unit."""
        query = """
            SELECT p.* FROM persons p
            INNER JOIN person_unit_relations r ON p.person_id = r.person_id
            WHERE r.unit_id = ?
            ORDER BY p.last_name_ar, p.first_name_ar
        """
        rows = self.db.fetch_all(query, (unit_id,))
        return [self._row_to_person(row) for row in rows]

    def count(self) -> int:
        """Count total persons."""
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM persons")
        return result["count"] if result else 0

    def update(self, person: Person) -> Person:
        """Update an existing person."""
        person.updated_at = datetime.now()
        query = """
            UPDATE persons SET
                first_name = ?, first_name_ar = ?,
                father_name = ?, father_name_ar = ?,
                mother_name = ?, mother_name_ar = ?,
                last_name = ?, last_name_ar = ?,
                gender = ?, year_of_birth = ?, nationality = ?,
                national_id = ?, passport_number = ?,
                phone_number = ?, mobile_number = ?, email = ?, address = ?,
                is_contact_person = ?, is_deceased = ?,
                updated_at = ?, updated_by = ?
            WHERE person_id = ?
        """
        params = (
            person.first_name, person.first_name_ar,
            person.father_name, person.father_name_ar,
            person.mother_name, person.mother_name_ar,
            person.last_name, person.last_name_ar,
            person.gender, person.year_of_birth, person.nationality,
            person.national_id, person.passport_number,
            person.phone_number, person.mobile_number, person.email, person.address,
            1 if person.is_contact_person else 0,
            1 if person.is_deceased else 0,
            person.updated_at.isoformat(), person.updated_by,
            person.person_id
        )
        self.db.execute(query, params)
        logger.debug(f"Updated person: {person.person_id}")
        return person

    def delete(self, person_id: str) -> bool:
        """Delete a person by ID."""
        query = "DELETE FROM persons WHERE person_id = ?"
        self.db.execute(query, (person_id,))
        return self.get_by_id(person_id) is None

    def _row_to_person(self, row) -> Person:
        """Convert database row to Person object."""
        data = dict(row)

        # Handle boolean fields
        data["is_contact_person"] = bool(data.get("is_contact_person", 0))
        data["is_deceased"] = bool(data.get("is_deceased", 0))

        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return Person(**{k: v for k, v in data.items() if k in Person.__dataclass_fields__})
