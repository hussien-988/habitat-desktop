# -*- coding: utf-8 -*-
"""
Building repository for database operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from models.building import Building
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingRepository:
    """Repository for Building CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, building: Building) -> Building:
        """Create a new building record."""
        query = """
            INSERT INTO buildings (
                building_uuid, building_id, governorate_code, governorate_name,
                governorate_name_ar, district_code, district_name, district_name_ar,
                subdistrict_code, subdistrict_name, subdistrict_name_ar,
                community_code, community_name, community_name_ar,
                neighborhood_code, neighborhood_name, neighborhood_name_ar,
                building_number, building_type, building_status,
                number_of_units, number_of_apartments, number_of_shops,
                number_of_floors, latitude, longitude, geo_location,
                created_at, updated_at, created_by, updated_by, legacy_stdm_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            building.building_uuid, building.building_id,
            building.governorate_code, building.governorate_name, building.governorate_name_ar,
            building.district_code, building.district_name, building.district_name_ar,
            building.subdistrict_code, building.subdistrict_name, building.subdistrict_name_ar,
            building.community_code, building.community_name, building.community_name_ar,
            building.neighborhood_code, building.neighborhood_name, building.neighborhood_name_ar,
            building.building_number, building.building_type, building.building_status,
            building.number_of_units, building.number_of_apartments, building.number_of_shops,
            building.number_of_floors, building.latitude, building.longitude, building.geo_location,
            building.created_at.isoformat() if building.created_at else None,
            building.updated_at.isoformat() if building.updated_at else None,
            building.created_by, building.updated_by, building.legacy_stdm_id
        )
        self.db.execute(query, params)
        logger.debug(f"Created building: {building.building_id}")
        return building

    def get_by_id(self, building_id: str) -> Optional[Building]:
        """Get building by building_id."""
        query = "SELECT * FROM buildings WHERE building_id = ?"
        row = self.db.fetch_one(query, (building_id,))
        if row:
            return self._row_to_building(row)
        return None

    def get_by_uuid(self, building_uuid: str) -> Optional[Building]:
        """Get building by UUID."""
        query = "SELECT * FROM buildings WHERE building_uuid = ?"
        row = self.db.fetch_one(query, (building_uuid,))
        if row:
            return self._row_to_building(row)
        return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Building]:
        """Get all buildings with pagination."""
        query = "SELECT * FROM buildings ORDER BY building_id LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_building(row) for row in rows]

    def search(
        self,
        neighborhood_code: Optional[str] = None,
        building_type: Optional[str] = None,
        building_status: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Building]:
        """Search buildings with filters."""
        query = "SELECT * FROM buildings WHERE 1=1"
        params = []

        if neighborhood_code:
            query += " AND neighborhood_code = ?"
            params.append(neighborhood_code)

        if building_type:
            query += " AND building_type = ?"
            params.append(building_type)

        if building_status:
            query += " AND building_status = ?"
            params.append(building_status)

        if search_text:
            query += """ AND (
                building_id LIKE ? OR
                neighborhood_name LIKE ? OR
                neighborhood_name_ar LIKE ? OR
                district_name LIKE ? OR
                district_name_ar LIKE ? OR
                building_number LIKE ?
            )"""
            search_pattern = f"%{search_text}%"
            params.extend([search_pattern] * 6)

        query += " ORDER BY building_id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_building(row) for row in rows]

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count buildings with optional filters."""
        query = "SELECT COUNT(*) as count FROM buildings WHERE 1=1"
        params = []

        if filters:
            if filters.get("neighborhood_code"):
                query += " AND neighborhood_code = ?"
                params.append(filters["neighborhood_code"])
            if filters.get("building_type"):
                query += " AND building_type = ?"
                params.append(filters["building_type"])
            if filters.get("building_status"):
                query += " AND building_status = ?"
                params.append(filters["building_status"])

        result = self.db.fetch_one(query, tuple(params))
        return result["count"] if result else 0

    def update(self, building: Building) -> Building:
        """Update an existing building."""
        building.updated_at = datetime.now()
        query = """
            UPDATE buildings SET
                governorate_code = ?, governorate_name = ?, governorate_name_ar = ?,
                district_code = ?, district_name = ?, district_name_ar = ?,
                subdistrict_code = ?, subdistrict_name = ?, subdistrict_name_ar = ?,
                community_code = ?, community_name = ?, community_name_ar = ?,
                neighborhood_code = ?, neighborhood_name = ?, neighborhood_name_ar = ?,
                building_number = ?, building_type = ?, building_status = ?,
                number_of_units = ?, number_of_apartments = ?, number_of_shops = ?,
                number_of_floors = ?, latitude = ?, longitude = ?, geo_location = ?,
                updated_at = ?, updated_by = ?, legacy_stdm_id = ?
            WHERE building_uuid = ?
        """
        params = (
            building.governorate_code, building.governorate_name, building.governorate_name_ar,
            building.district_code, building.district_name, building.district_name_ar,
            building.subdistrict_code, building.subdistrict_name, building.subdistrict_name_ar,
            building.community_code, building.community_name, building.community_name_ar,
            building.neighborhood_code, building.neighborhood_name, building.neighborhood_name_ar,
            building.building_number, building.building_type, building.building_status,
            building.number_of_units, building.number_of_apartments, building.number_of_shops,
            building.number_of_floors, building.latitude, building.longitude, building.geo_location,
            building.updated_at.isoformat(), building.updated_by, building.legacy_stdm_id,
            building.building_uuid
        )
        self.db.execute(query, params)
        logger.debug(f"Updated building: {building.building_id}")
        return building

    def delete(self, building_uuid: str) -> bool:
        """Delete a building by UUID."""
        query = "DELETE FROM buildings WHERE building_uuid = ?"
        cursor = self.db.execute(query, (building_uuid,))
        return cursor.rowcount > 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get building statistics for dashboard."""
        stats = {}

        # Total count
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM buildings")
        stats["total"] = result["count"] if result else 0

        # Count by status
        rows = self.db.fetch_all("""
            SELECT building_status, COUNT(*) as count
            FROM buildings
            GROUP BY building_status
        """)
        stats["by_status"] = {row["building_status"]: row["count"] for row in rows}

        # Count by type
        rows = self.db.fetch_all("""
            SELECT building_type, COUNT(*) as count
            FROM buildings
            GROUP BY building_type
        """)
        stats["by_type"] = {row["building_type"]: row["count"] for row in rows}

        # Count by neighborhood
        rows = self.db.fetch_all("""
            SELECT neighborhood_name, COUNT(*) as count
            FROM buildings
            GROUP BY neighborhood_code
            ORDER BY count DESC
            LIMIT 10
        """)
        stats["by_neighborhood"] = {row["neighborhood_name"]: row["count"] for row in rows}

        # Total units
        result = self.db.fetch_one("SELECT SUM(number_of_units) as total FROM buildings")
        stats["total_units"] = result["total"] if result and result["total"] else 0

        return stats

    def get_neighborhoods(self) -> List[Dict[str, str]]:
        """Get list of unique neighborhoods."""
        query = """
            SELECT DISTINCT neighborhood_code, neighborhood_name, neighborhood_name_ar
            FROM buildings
            ORDER BY neighborhood_name
        """
        rows = self.db.fetch_all(query)
        return [
            {
                "code": row["neighborhood_code"],
                "name": row["neighborhood_name"],
                "name_ar": row["neighborhood_name_ar"]
            }
            for row in rows
        ]

    def _row_to_building(self, row) -> Building:
        """Convert database row to Building object."""
        data = dict(row)

        # Handle datetime fields
        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return Building(**{k: v for k, v in data.items() if k in Building.__dataclass_fields__})
