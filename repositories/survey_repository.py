# -*- coding: utf-8 -*-
"""
Survey repository for database operations.
Implements UC-005: Complete Draft Office Survey - draft management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
import uuid
import json

from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class SurveyRepository:
    """Repository for Survey CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, survey_data: Dict[str, Any]) -> str:
        """
        Create a new survey record.

        Args:
            survey_data: Dictionary containing survey context data

        Returns:
            survey_id of the created record
        """
        survey_id = survey_data.get('survey_id') or str(uuid.uuid4())

        query = """
            INSERT INTO surveys (
                survey_id, building_id, unit_id, field_collector_id,
                survey_date, survey_type, status, reference_code,
                source, notes, created_at, updated_at,
                context_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            survey_id,
            survey_data.get('building', {}).get('building_id') if survey_data.get('building') else None,
            survey_data.get('unit', {}).get('unit_id') if survey_data.get('unit') else None,
            survey_data.get('clerk_id'),
            survey_data.get('survey_date', datetime.now().date()).isoformat() if survey_data.get('survey_date') else datetime.now().date().isoformat(),
            survey_data.get('survey_type', 'office'),
            survey_data.get('status', 'draft'),
            survey_data.get('reference_number'),
            survey_data.get('source', 'office'),
            survey_data.get('notes', ''),
            survey_data.get('created_at', datetime.now()).isoformat() if survey_data.get('created_at') else datetime.now().isoformat(),
            survey_data.get('updated_at', datetime.now()).isoformat() if survey_data.get('updated_at') else datetime.now().isoformat(),
            json.dumps(survey_data, ensure_ascii=False, default=str)
        )

        self.db.execute(query, params)
        logger.debug(f"Created survey: {survey_id}")
        return survey_id

    def update(self, survey_id: str, survey_data: Dict[str, Any]) -> bool:
        """
        Update an existing survey record.

        Args:
            survey_id: Survey UUID
            survey_data: Updated survey context data

        Returns:
            True if updated successfully
        """
        survey_data['updated_at'] = datetime.now()

        query = """
            UPDATE surveys SET
                building_id = ?,
                unit_id = ?,
                field_collector_id = ?,
                survey_date = ?,
                survey_type = ?,
                status = ?,
                reference_code = ?,
                source = ?,
                notes = ?,
                updated_at = ?,
                context_data = ?,
                finalized_at = ?
            WHERE survey_id = ?
        """

        finalized_at = None
        if survey_data.get('status') == 'finalized':
            finalized_at = datetime.now().isoformat()

        params = (
            survey_data.get('building', {}).get('building_id') if survey_data.get('building') else None,
            survey_data.get('unit', {}).get('unit_id') if survey_data.get('unit') else None,
            survey_data.get('clerk_id'),
            survey_data.get('survey_date', datetime.now().date()).isoformat() if survey_data.get('survey_date') else datetime.now().date().isoformat(),
            survey_data.get('survey_type', 'office'),
            survey_data.get('status', 'draft'),
            survey_data.get('reference_number'),
            survey_data.get('source', 'office'),
            survey_data.get('notes', ''),
            survey_data['updated_at'].isoformat(),
            json.dumps(survey_data, ensure_ascii=False, default=str),
            finalized_at,
            survey_id
        )

        cursor = self.db.execute(query, params)
        logger.debug(f"Updated survey: {survey_id}")
        return cursor.rowcount > 0

    def get_by_id(self, survey_id: str) -> Optional[Dict[str, Any]]:
        """
        Get survey by survey_id.

        Args:
            survey_id: Survey UUID

        Returns:
            Survey data dictionary or None
        """
        query = "SELECT * FROM surveys WHERE survey_id = ?"
        row = self.db.fetch_one(query, (survey_id,))

        if row:
            return self._row_to_dict(row)
        return None

    def get_drafts_for_office(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all draft office surveys.
        Implements UC-005 S01: Open Draft Office Surveys List.

        Args:
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of draft survey dictionaries
        """
        query = """
            SELECT * FROM surveys
            WHERE status = 'draft' AND source = 'office'
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_dict(row) for row in rows]

    def get_drafts_for_field(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all draft field surveys.
        Implements UC-002: Complete Draft Field Survey.

        Args:
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of draft survey dictionaries
        """
        query = """
            SELECT * FROM surveys
            WHERE status = 'draft' AND source = 'field'
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_dict(row) for row in rows]

    def search_drafts(
        self,
        source: str = 'office',
        building_id: Optional[str] = None,
        reference_code: Optional[str] = None,
        person_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search and filter draft surveys.
        Implements UC-005 S02: Filter or Search Draft Office Surveys.

        Args:
            source: 'office' or 'field'
            building_id: Filter by building ID
            reference_code: Search by reference code
            person_name: Search by contact person name (searches in context_data JSON)
            start_date: Filter by created date >= start_date
            end_date: Filter by created date <= end_date
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of matching draft surveys
        """
        query = """
            SELECT * FROM surveys
            WHERE status = 'draft' AND source = ?
        """
        params = [source]

        if building_id:
            query += " AND building_id = ?"
            params.append(building_id)

        if reference_code:
            query += " AND reference_code LIKE ?"
            params.append(f"%{reference_code}%")

        if person_name:
            # Search in JSON context_data for person names
            query += " AND context_data LIKE ?"
            params.append(f'%"name":"%{person_name}%"%')

        if start_date:
            query += " AND DATE(created_at) >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND DATE(created_at) <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_dict(row) for row in rows]

    def count_drafts(self, source: str = 'office') -> int:
        """
        Count draft surveys by source.

        Args:
            source: 'office' or 'field'

        Returns:
            Number of draft surveys
        """
        query = "SELECT COUNT(*) as count FROM surveys WHERE status = 'draft' AND source = ?"
        result = self.db.fetch_one(query, (source,))
        return result["count"] if result else 0

    def update_status(self, survey_id: str, status: str) -> bool:
        """
        Update survey status.

        Args:
            survey_id: Survey UUID
            status: New status ('draft', 'finalized', 'cancelled')

        Returns:
            True if updated successfully
        """
        finalized_at = None
        if status == 'finalized':
            finalized_at = datetime.now().isoformat()

        query = """
            UPDATE surveys
            SET status = ?, updated_at = ?, finalized_at = ?
            WHERE survey_id = ?
        """
        params = (status, datetime.now().isoformat(), finalized_at, survey_id)
        cursor = self.db.execute(query, params)
        logger.debug(f"Updated survey {survey_id} status to {status}")
        return cursor.rowcount > 0

    def delete(self, survey_id: str) -> bool:
        """
        Delete a survey record.

        Args:
            survey_id: Survey UUID

        Returns:
            True if deleted successfully
        """
        query = "DELETE FROM surveys WHERE survey_id = ?"
        cursor = self.db.execute(query, (survey_id,))
        return cursor.rowcount > 0

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get survey statistics for dashboard.

        Returns:
            Dictionary with survey counts by status and source
        """
        stats = {}

        # Total count
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM surveys")
        stats["total"] = result["count"] if result else 0

        # Count by status
        rows = self.db.fetch_all("""
            SELECT status, COUNT(*) as count
            FROM surveys
            GROUP BY status
        """)
        stats["by_status"] = {row["status"]: row["count"] for row in rows}

        # Count by source
        rows = self.db.fetch_all("""
            SELECT source, COUNT(*) as count
            FROM surveys
            GROUP BY source
        """)
        stats["by_source"] = {row["source"]: row["count"] for row in rows}

        # Draft surveys
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM surveys WHERE status = 'draft'
        """)
        stats["draft_count"] = result["count"] if result else 0

        # Recent surveys (last 7 days)
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM surveys
            WHERE created_at >= date('now', '-7 days')
        """)
        stats["recent"] = result["count"] if result else 0

        return stats

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """
        Convert database row to dictionary.

        Args:
            row: Database row

        Returns:
            Survey data dictionary with parsed context
        """
        data = dict(row)

        # Parse context_data JSON
        if data.get("context_data"):
            try:
                context = json.loads(data["context_data"])
                data["context"] = context
            except json.JSONDecodeError:
                logger.error(f"Failed to parse context_data for survey {data.get('survey_id')}")
                data["context"] = {}
        else:
            data["context"] = {}

        # Parse dates
        for field in ["survey_date"]:
            if data.get(field):
                try:
                    data[field] = date.fromisoformat(data[field])
                except (ValueError, TypeError):
                    data[field] = None

        for field in ["created_at", "updated_at", "finalized_at"]:
            if data.get(field):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except (ValueError, TypeError):
                    data[field] = None

        return data
