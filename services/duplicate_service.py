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

    def get_conflicts(
        self,
        page: int = 1,
        page_size: int = 20,
        conflict_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        is_escalated: Optional[bool] = None,
        import_package_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get paginated list of conflicts with filters.

        Returns: {items: [...], totalCount, page, pageSize, totalPages}

        Raises: ApiException / NetworkException on backend failure. The
        previous implementation swallowed errors and returned a fake
        zero-result dict, which silently corrupted summary counts.
        """
        api = self._get_api()
        return api.get_conflicts(
            page=page,
            page_size=page_size,
            conflict_type=conflict_type,
            status=status,
            priority=priority,
            is_escalated=is_escalated,
            import_package_id=import_package_id,
        )

    @staticmethod
    def compute_local_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate counts from a filtered conflict list.

        Used when viewing package-specific conflicts — /conflicts/summary is
        global only, so import-context mode computes counts client-side.
        Returns the same shape callers already read from the summary endpoint.
        """
        from services.conflict_classifier import get_conflict_display_category, PERSON, PROPERTY

        pending_statuses = {"pending", "pendingreview", "inreview"}
        resolved_statuses = {"resolved", "autoresolved"}

        person_pending = 0
        property_pending = 0
        escalated = 0
        resolved = 0
        pending_total = 0

        for item in items or []:
            status_raw = str(item.get("status", "")).lower().replace("_", "").replace(" ", "")
            category = get_conflict_display_category(item)
            if item.get("isEscalated") or status_raw == "escalated":
                escalated += 1
            if status_raw in resolved_statuses:
                resolved += 1
                continue
            if status_raw in pending_statuses:
                pending_total += 1
                if category == PERSON:
                    person_pending += 1
                elif category == PROPERTY:
                    property_pending += 1

        return {
            "pendingReviewCount": pending_total,
            "totalConflicts": len(items or []),
            "pendingPersonDuplicates": person_pending,
            "personDuplicateCount": person_pending,
            "pendingPropertyDuplicates": property_pending,
            "propertyDuplicateCount": property_pending,
            "escalatedCount": escalated,
            "resolvedCount": resolved,
        }

    def get_property_duplicates(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get property duplicate conflicts. Raises on backend failure."""
        return self._get_api().get_property_duplicates(page, page_size)

    def get_person_duplicates(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get person duplicate conflicts. Raises on backend failure."""
        return self._get_api().get_person_duplicates(page, page_size)

    def get_escalated_conflicts(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """Get escalated conflicts awaiting senior review. Raises on failure."""
        return self._get_api().get_escalated_conflicts(page, page_size)

    def get_conflicts_summary(self) -> Dict[str, Any]:
        """Get aggregate conflict counts for dashboard. Raises on failure."""
        return self._get_api().get_conflicts_summary()

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

    def get_conflict_details(self, conflict_id: str) -> Dict[str, Any]:
        """Get side-by-side comparison details. Raises on backend failure.

        The comparison page catches the exception and shows an inline
        placeholder rather than a misleading blank record card.
        """
        return self._get_api().get_conflict_details(conflict_id)

    def get_document_comparison(self, conflict_id: str) -> Dict[str, Any]:
        """Get document comparison for a conflict. Raises on backend failure."""
        return self._get_api().get_conflict_document_comparison(conflict_id)

    def get_person_data(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Fetch person record by ID for comparison display."""
        api = self._get_api()
        return api.get_person_by_id(person_id)

    def merge_conflict(
        self, conflict_id: str, master_record_id: str, justification: str = ""
    ) -> bool:
        """Merge duplicate records. Raises on backend failure so the UI never
        removes a conflict optimistically when the server rejected the call."""
        self._get_api().merge_conflict(conflict_id, master_record_id, justification)
        self._save_local_audit(conflict_id, "merge", justification, master_record_id)
        logger.info(f"Merged conflict {conflict_id}, master={master_record_id}")
        return True

    def keep_separate(self, conflict_id: str, justification: str = "") -> bool:
        """Mark conflict records as intentionally separate. Raises on failure."""
        self._get_api().keep_separate_conflict(conflict_id, justification)
        self._save_local_audit(conflict_id, "keep_separate", justification)
        logger.info(f"Kept separate conflict {conflict_id}")
        return True

    def resolve_conflict(
        self, conflict_id: str, resolution_type: str = "", justification: str = ""
    ) -> bool:
        """General conflict resolution. Raises on failure."""
        self._get_api().resolve_conflict(conflict_id, resolution_type, justification)
        self._save_local_audit(conflict_id, resolution_type, justification)
        logger.info(f"Resolved conflict {conflict_id} as {resolution_type}")
        return True

    def escalate_conflict(self, conflict_id: str, justification: str = "") -> bool:
        """Escalate conflict to supervisor. Raises on failure."""
        self._get_api().escalate_conflict(conflict_id, justification)
        self._save_local_audit(conflict_id, "escalate", justification)
        logger.info(f"Escalated conflict {conflict_id}")
        return True

    def _save_local_audit(
        self,
        conflict_id: str,
        resolution_type: str,
        justification: str,
        master_record_id: Optional[str] = None,
    ):
        """Save resolution to local DB for offline audit trail.

        The table may have been created earlier with a legacy schema
        (entity_type/group_key/record_ids NOT NULL, no conflict_id) by
        db_adapter. CREATE TABLE IF NOT EXISTS is a no-op in that case,
        so the INSERT fails with "no column named conflict_id". Detect
        the legacy schema and migrate it once — nothing reads from this
        table (it's write-only audit), so dropping it is safe.
        """
        if not self.db:
            return

        try:
            self._ensure_audit_schema()
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

    def _ensure_audit_schema(self):
        """Make sure duplicate_resolutions has the modern schema.

        Drops a legacy table that lacks the `conflict_id` column (or has
        the old NOT NULL columns we no longer populate) and recreates it.
        """
        if not self.db:
            return
        try:
            # Probe for the column. If it errors, the table either doesn't
            # exist or has the legacy schema — both are handled by the
            # DROP+CREATE below.
            self.db.execute(
                "SELECT conflict_id FROM duplicate_resolutions LIMIT 1"
            )
        except Exception:
            try:
                self.db.execute("DROP TABLE IF EXISTS duplicate_resolutions")
            except Exception as drop_err:
                logger.warning(
                    f"Could not drop legacy duplicate_resolutions: {drop_err}"
                )
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
