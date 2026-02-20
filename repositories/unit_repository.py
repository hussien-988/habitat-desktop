# -*- coding: utf-8 -*-
"""
Property Unit repository for database operations.
"""

from typing import List, Optional
from datetime import datetime

from models.unit import PropertyUnit
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitRepository:
    """Repository for PropertyUnit CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, unit: PropertyUnit) -> PropertyUnit:
        """Create a new property unit record."""
        query = """
            INSERT INTO property_units (
                unit_uuid, unit_id, building_id, unit_type, unit_number,
                floor_number, apartment_number, apartment_status,
                property_description, area_sqm,
                created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            unit.unit_uuid, unit.unit_id, unit.building_id,
            unit.unit_type, unit.unit_number, unit.floor_number,
            unit.apartment_number, unit.apartment_status,
            unit.property_description, unit.area_sqm,
            unit.created_at.isoformat() if unit.created_at else None,
            unit.updated_at.isoformat() if unit.updated_at else None,
            unit.created_by, unit.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created unit: {unit.unit_id}")
        return unit

    def get_by_id(self, unit_id: str) -> Optional[PropertyUnit]:
        """Get unit by unit_id."""
        query = "SELECT * FROM property_units WHERE unit_id = ?"
        row = self.db.fetch_one(query, (unit_id,))
        if row:
            return self._row_to_unit(row)
        return None

    def get_by_uuid(self, unit_uuid: str) -> Optional[PropertyUnit]:
        """Get unit by unit_uuid."""
        query = "SELECT * FROM property_units WHERE unit_uuid = ?"
        row = self.db.fetch_one(query, (unit_uuid,))
        if row:
            return self._row_to_unit(row)
        return None

    def get_by_building(self, building_id: str) -> List[PropertyUnit]:
        """Get all units for a building."""
        query = "SELECT * FROM property_units WHERE building_id = ? ORDER BY floor_number, unit_number"
        rows = self.db.fetch_all(query, (building_id,))
        return [self._row_to_unit(row) for row in rows]

    def get_all(self, limit: int = 100, offset: int = 0) -> List[PropertyUnit]:
        """Get all units with pagination."""
        query = "SELECT * FROM property_units ORDER BY unit_id LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_unit(row) for row in rows]

    def search(self, building_id: str = None, unit_type: str = None,
               search_text: str = None, limit: int = 100) -> List[PropertyUnit]:
        """Search units with filters."""
        query = "SELECT * FROM property_units WHERE 1=1"
        params = []

        if building_id:
            query += " AND building_id = ?"
            params.append(building_id)

        if unit_type:
            query += " AND unit_type = ?"
            params.append(unit_type)

        if search_text:
            query += " AND (unit_id LIKE ? OR unit_number LIKE ? OR property_description LIKE ?)"
            search_pattern = f"%{search_text}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        query += " ORDER BY building_id, floor_number, unit_number LIMIT ?"
        params.append(limit)

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_unit(row) for row in rows]

    def count_by_building(self, building_id: str) -> int:
        """Count units for a building."""
        result = self.db.fetch_one(
            "SELECT COUNT(*) as count FROM property_units WHERE building_id = ?",
            (building_id,)
        )
        return result["count"] if result else 0

    def get_next_unit_number(self, building_id: str) -> str:
        """
        Get the next available unit_number for a building.
        Returns a 3-digit padded string (e.g., '001', '002', etc.)
        """
        result = self.db.fetch_one(
            "SELECT MAX(CAST(unit_number AS INTEGER)) as max_num FROM property_units WHERE building_id = ?",
            (building_id,)
        )
        max_num = result["max_num"] if result and result["max_num"] else 0
        next_num = max_num + 1
        return str(next_num).zfill(3)

    def unit_number_exists(self, building_id: str, unit_number: str, exclude_unit_uuid: str = None) -> bool:
        """
        Check if a unit_number already exists for a given building.
        Optionally exclude a specific unit (for edit mode).
        """
        if exclude_unit_uuid:
            result = self.db.fetch_one(
                "SELECT COUNT(*) as count FROM property_units WHERE building_id = ? AND unit_number = ? AND unit_uuid != ?",
                (building_id, unit_number, exclude_unit_uuid)
            )
        else:
            result = self.db.fetch_one(
                "SELECT COUNT(*) as count FROM property_units WHERE building_id = ? AND unit_number = ?",
                (building_id, unit_number)
            )
        return result["count"] > 0 if result else False

    def get_by_building_and_unit_number(self, building_id: str, unit_number: str) -> Optional[PropertyUnit]:
        """Get unit by building_id and unit_number combination."""
        query = "SELECT * FROM property_units WHERE building_id = ? AND unit_number = ?"
        row = self.db.fetch_one(query, (building_id, unit_number))
        if row:
            return self._row_to_unit(row)
        return None

    def update(self, unit: PropertyUnit) -> PropertyUnit:
        """Update an existing unit."""
        unit.updated_at = datetime.now()
        # Ensure unit_id is consistent with building_id and unit_number
        unit.unit_id = f"{unit.building_id}-{unit.unit_number}"

        query = """
            UPDATE property_units SET
                building_id = ?, unit_id = ?, unit_type = ?, unit_number = ?, floor_number = ?,
                apartment_number = ?, apartment_status = ?,
                property_description = ?, area_sqm = ?,
                updated_at = ?, updated_by = ?
            WHERE unit_uuid = ?
        """
        params = (
            unit.building_id, unit.unit_id, unit.unit_type, unit.unit_number, unit.floor_number,
            unit.apartment_number, unit.apartment_status,
            unit.property_description, unit.area_sqm,
            unit.updated_at.isoformat(), unit.updated_by,
            unit.unit_uuid
        )
        self.db.execute(query, params)
        logger.debug(f"Updated unit: {unit.unit_id}")
        return unit

    def delete(self, unit_uuid: str) -> bool:
        """Delete a unit by UUID."""
        query = "DELETE FROM property_units WHERE unit_uuid = ?"
        cursor = self.db.execute(query, (unit_uuid,))
        return cursor.rowcount > 0

    def _row_to_unit(self, row) -> PropertyUnit:
        """Convert database row to PropertyUnit object."""
        data = dict(row)

        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return PropertyUnit(**{k: v for k, v in data.items() if k in PropertyUnit.__dataclass_fields__})
