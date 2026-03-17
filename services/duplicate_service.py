# -*- coding: utf-8 -*-
"""Conflict resolution service using the Backend Conflicts API."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from utils.logger import get_logger

logger = get_logger(__name__)


class DuplicateService:
    """Service for managing conflicts/duplicates via Backend Conflicts API."""

    def __init__(self, db=None):
        self.db = db

    def _get_api(self):
        from services.api_client import get_api_client
        api = get_api_client()
        if not api:
            raise RuntimeError("API client not available")
        return api

    # ========== List / Query ==========

    def get_conflicts(
        self,
        page: int = 1,
        page_size: int = 20,
        conflict_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        is_escalated: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of conflicts with filters.

        Returns: {items: [...], totalCount, page, pageSize, totalPages}
        """
        try:
            api = self._get_api()
            return api.get_conflicts(
                page=page,
                page_size=page_size,
                conflict_type=conflict_type,
                status=status,
                priority=priority,
                is_escalated=is_escalated,
            )
        except Exception as e:
            logger.error(f"Failed to get conflicts: {e}")
            return {"items": [], "totalCount": 0, "page": page, "pageSize": page_size, "totalPages": 0}

    def get_property_duplicates(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get property duplicate conflicts."""
        try:
            api = self._get_api()
            return api.get_property_duplicates(page, page_size)
        except Exception as e:
            logger.error(f"Failed to get property duplicates: {e}")
            return {"items": [], "totalCount": 0, "page": page, "pageSize": page_size, "totalPages": 0}

    def get_person_duplicates(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get person duplicate conflicts."""
        try:
            api = self._get_api()
            return api.get_person_duplicates(page, page_size)
        except Exception as e:
            logger.error(f"Failed to get person duplicates: {e}")
            return {"items": [], "totalCount": 0, "page": page, "pageSize": page_size, "totalPages": 0}

    def get_escalated_conflicts(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get escalated conflicts awaiting senior review."""
        try:
            api = self._get_api()
            return api.get_escalated_conflicts(page, page_size)
        except Exception as e:
            logger.error(f"Failed to get escalated conflicts: {e}")
            return {"items": [], "totalCount": 0, "page": page, "pageSize": page_size, "totalPages": 0}

    # ========== Summary ==========

    def get_conflicts_summary(self) -> Dict[str, Any]:
        """Get aggregate conflict counts for dashboard."""
        try:
            api = self._get_api()
            return api.get_conflicts_summary()
        except Exception as e:
            logger.error(f"Failed to get conflicts summary: {e}")
            return {}

    def get_pending_count(self) -> Dict[str, int]:
        """Get count of pending conflicts by type (backwards-compatible)."""
        try:
            summary = self.get_conflicts_summary()
            return {
                "property": summary.get("pendingPropertyDuplicates", 0),
                "person": summary.get("pendingPersonDuplicates", 0),
                "total": summary.get("pendingReviewCount", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get pending count: {e}")
            return {"property": 0, "person": 0, "total": 0}

    # ========== Details / Comparison ==========

    def get_conflict_details(self, conflict_id: str) -> Dict[str, Any]:
        """Get side-by-side comparison details for a conflict."""
        try:
            api = self._get_api()
            return api.get_conflict_details(conflict_id)
        except Exception as e:
            logger.error(f"Failed to get conflict details: {e}")
            return {}

    def get_document_comparison(self, conflict_id: str) -> Dict[str, Any]:
        """Get document comparison for a conflict."""
        try:
            api = self._get_api()
            return api.get_conflict_document_comparison(conflict_id)
        except Exception as e:
            logger.error(f"Failed to get document comparison: {e}")
            return {}

    def get_person_data(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Fetch person record by ID for comparison display."""
        api = self._get_api()
        return api.get_person_by_id(person_id)

    # ========== Resolution Actions ==========

    def merge_conflict(
        self, conflict_id: str, master_record_id: str, justification: str = ""
    ) -> bool:
        """Merge duplicate records (choose master record)."""
        try:
            api = self._get_api()
            api.merge_conflict(conflict_id, master_record_id, justification)
            self._save_local_audit(conflict_id, "merge", justification, master_record_id)
            logger.info(f"Merged conflict {conflict_id}, master={master_record_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to merge conflict {conflict_id}: {e}")
            return False

    def keep_separate(self, conflict_id: str, justification: str = "") -> bool:
        """Mark conflict records as intentionally separate."""
        try:
            api = self._get_api()
            api.keep_separate_conflict(conflict_id, justification)
            self._save_local_audit(conflict_id, "keep_separate", justification)
            logger.info(f"Kept separate conflict {conflict_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to keep separate {conflict_id}: {e}")
            return False

    def resolve_conflict(
        self, conflict_id: str, resolution_type: str = "", justification: str = ""
    ) -> bool:
        """General conflict resolution."""
        try:
            api = self._get_api()
            api.resolve_conflict(conflict_id, resolution_type, justification)
            self._save_local_audit(conflict_id, resolution_type, justification)
            logger.info(f"Resolved conflict {conflict_id} as {resolution_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to resolve conflict {conflict_id}: {e}")
            return False

    def escalate_conflict(self, conflict_id: str, justification: str = "") -> bool:
        """Escalate conflict to supervisor for review."""
        try:
            api = self._get_api()
            api.escalate_conflict(conflict_id, justification)
            self._save_local_audit(conflict_id, "escalate", justification)
            logger.info(f"Escalated conflict {conflict_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to escalate conflict {conflict_id}: {e}")
            return False

    # ========== Local Audit Trail ==========

    def _save_local_audit(
        self,
        conflict_id: str,
        resolution_type: str,
        justification: str,
        master_record_id: Optional[str] = None,
    ):
        """Save resolution to local DB for offline audit trail."""
        if not self.db:
            return

        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS duplicate_resolutions (
                    resolution_id TEXT PRIMARY KEY,
                    conflict_id TEXT,
                    resolution_type TEXT,
                    master_record_id TEXT,
                    justification TEXT,
                    resolved_at TEXT
                )
            """)
            self.db.execute(
                """INSERT INTO duplicate_resolutions
                   (resolution_id, conflict_id, resolution_type,
                    master_record_id, justification, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    conflict_id,
                    resolution_type,
                    master_record_id,
                    justification,
                    datetime.now().isoformat(),
                )
            )
        except Exception as e:
            logger.warning(f"Failed to save local audit: {e}")
