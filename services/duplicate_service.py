# -*- coding: utf-8 -*-
"""
Duplicate detection and resolution service.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates

Detects duplicates by fetching data via REST API and grouping in Python.
Resolution actions use API CRUD endpoints.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict
import uuid

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DuplicateGroup:
    """Represents a group of potential duplicate records."""
    group_id: str
    entity_type: str  # "building", "unit", "person", or "person_unit_relation"
    group_key: str  # The shared key (building_id, unit composite key, or national_id)
    records: List[Dict[str, Any]]
    status: str = "pending"  # pending, resolved, escalated


class DuplicateService:
    """
    Service for detecting and resolving duplicate records via REST API.

    Property duplicates (UC-007): Detected by identical buildingId or
    buildingId + unitIdentifier composite key.

    Person duplicates (UC-008): Detected by identical nationalId.
    """

    def __init__(self, db=None):
        self.db = db

    def _get_api(self):
        """Get the API client instance."""
        from services.api_client import get_api_client
        api = get_api_client()
        if not api:
            raise RuntimeError("API client not available")
        return api

    # ========== Property Duplicate Detection (UC-007) ==========

    def detect_building_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect buildings with duplicate buildingId values via REST API.
        Fetches all buildings paginated, groups by buildingId in Python.
        """
        try:
            api = self._get_api()
            all_buildings = []
            page = 1
            while True:
                result = api.search_buildings(page=page, page_size=200)
                items = result.get("items", [])
                if not items:
                    break
                all_buildings.extend(items)
                total_pages = result.get("totalPages", 1)
                if page >= total_pages:
                    break
                page += 1

            groups_map = defaultdict(list)
            for b in all_buildings:
                key = b.get("buildingId", "")
                if key:
                    groups_map[key].append(b)

            groups = []
            for key, records in groups_map.items():
                if len(records) > 1:
                    groups.append(DuplicateGroup(
                        group_id=str(uuid.uuid4()),
                        entity_type="building",
                        group_key=key,
                        records=records,
                        status="pending"
                    ))

            logger.info(f"Detected {len(groups)} building duplicate groups from API")
            return groups

        except Exception as e:
            logger.error(f"Failed to detect building duplicates: {e}")
            return []

    def detect_unit_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect units with duplicate buildingId + unitIdentifier + floorNumber composite keys.
        Fetches all property units via REST API, groups in Python.
        """
        try:
            api = self._get_api()
            all_units = api.get_all_property_units(limit=5000)

            groups_map = defaultdict(list)
            for u in all_units:
                building_id = u.get("buildingId", "")
                unit_id = u.get("unitIdentifier", "")
                floor = str(u.get("floorNumber", ""))
                if unit_id:
                    composite_key = f"{building_id}:{unit_id}:{floor}"
                    groups_map[composite_key].append(u)

            groups = []
            for key, records in groups_map.items():
                if len(records) > 1:
                    groups.append(DuplicateGroup(
                        group_id=str(uuid.uuid4()),
                        entity_type="unit",
                        group_key=key,
                        records=records,
                        status="pending"
                    ))

            logger.info(f"Detected {len(groups)} unit duplicate groups from API")
            return groups

        except Exception as e:
            logger.error(f"Failed to detect unit duplicates: {e}")
            return []

    def get_all_property_duplicates(self) -> List[DuplicateGroup]:
        """Get all property (building + unit) duplicate groups."""
        building_dups = self.detect_building_duplicates()
        unit_dups = self.detect_unit_duplicates()
        return building_dups + unit_dups

    # ========== Person Duplicate Detection (UC-008) ==========

    def detect_person_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect persons with duplicate nationalId values via REST API.
        Fetches all persons paginated, groups by nationalId in Python.
        """
        try:
            api = self._get_api()
            all_persons = []
            page = 1
            while True:
                result = api.get_persons(page=page, page_size=200)
                items = result.get("items", [])
                if not items:
                    break
                all_persons.extend(items)
                total_pages = result.get("totalPages", 1)
                if page >= total_pages:
                    break
                page += 1

            groups_map = defaultdict(list)
            for p in all_persons:
                nid = p.get("nationalId", "")
                if nid:
                    groups_map[nid].append(p)

            groups = []
            for key, records in groups_map.items():
                if len(records) > 1:
                    groups.append(DuplicateGroup(
                        group_id=str(uuid.uuid4()),
                        entity_type="person",
                        group_key=key,
                        records=records,
                        status="pending"
                    ))

            logger.info(f"Detected {len(groups)} person duplicate groups from API")
            return groups

        except Exception as e:
            logger.error(f"Failed to detect person duplicates: {e}")
            return []

    # ========== Resolution Actions ==========

    def resolve_as_merge(
        self,
        group: DuplicateGroup,
        master_record_id: str,
        justification: str,
        user_id: str = None
    ) -> bool:
        """
        Resolve duplicates by merging into a master record.
        The master record is kept, others are deleted via API.
        """
        try:
            self._save_resolution(
                group=group,
                resolution_type="merge",
                master_record_id=master_record_id,
                justification=justification,
                user_id=user_id
            )

            if group.entity_type == "building":
                self._merge_buildings(group.records, master_record_id)
            elif group.entity_type == "unit":
                self._merge_units(group.records, master_record_id)
            elif group.entity_type == "person":
                self._merge_persons(group.records, master_record_id)

            logger.info(f"Merged {group.entity_type} duplicates: {group.group_key} -> {master_record_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to merge duplicates: {e}")
            return False

    def resolve_as_separate(
        self,
        group: DuplicateGroup,
        justification: str,
        user_id: str = None
    ) -> bool:
        """
        Resolve by marking records as intentionally separate (not duplicates).
        Prevents re-surfacing in future detection.
        """
        try:
            self._save_resolution(
                group=group,
                resolution_type="keep_separate",
                master_record_id=None,
                justification=justification,
                user_id=user_id
            )
            logger.info(f"Marked {group.entity_type} as separate: {group.group_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark as separate: {e}")
            return False

    def escalate_for_review(
        self,
        group: DuplicateGroup,
        justification: str,
        user_id: str = None
    ) -> bool:
        """
        Escalate complex case for senior review.
        UC-007/UC-008 S05a: Request field verification.
        """
        try:
            self._save_resolution(
                group=group,
                resolution_type="escalated",
                master_record_id=None,
                justification=justification,
                user_id=user_id,
                status="escalated"
            )
            logger.info(f"Escalated {group.entity_type} for review: {group.group_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to escalate: {e}")
            return False

    def request_field_verification(
        self,
        group: DuplicateGroup,
        justification: str,
        user_id: str = None
    ) -> bool:
        """
        Request field verification for a duplicate group.
        UC-007 S05: Request field verification option.
        """
        try:
            self._save_resolution(
                group=group,
                resolution_type="field_verification",
                master_record_id=None,
                justification=justification,
                user_id=user_id,
                status="pending_verification"
            )
            logger.info(f"Requested field verification for {group.entity_type}: {group.group_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to request field verification: {e}")
            return False

    # ========== Comparison Data ==========

    def get_person_comparison_data(self, group: DuplicateGroup) -> List[Dict[str, Any]]:
        """Get full comparison data for each person in a duplicate group.

        For each person: find their claims, linked units, and buildings via API.
        Returns list of dicts with keys: person, claims, units, buildings.
        """
        try:
            api = self._get_api()
        except Exception:
            return []

        results = []
        for person_record in group.records:
            person_id = person_record.get("id", "")
            national_id = person_record.get("nationalId", "")

            claims = []
            units = []
            buildings = []

            try:
                # Get claims where this person is the primary claimant
                all_claims = api.get_claims(primary_claimant_id=person_id)
                if isinstance(all_claims, list):
                    claims = all_claims
                elif isinstance(all_claims, dict):
                    claims = all_claims.get("items", [])
            except Exception as e:
                logger.warning(f"Failed to fetch claims for person {person_id}: {e}")

            # Get units and buildings from claims
            seen_unit_ids = set()
            seen_building_ids = set()

            for claim in claims:
                unit_id = claim.get("propertyUnitId", "")
                if unit_id and unit_id not in seen_unit_ids:
                    seen_unit_ids.add(unit_id)
                    try:
                        # Get units for the building associated with this claim
                        building_id_from_claim = claim.get("buildingId", "")
                        if building_id_from_claim and building_id_from_claim not in seen_building_ids:
                            seen_building_ids.add(building_id_from_claim)
                            building = api.get_building_by_id(building_id_from_claim)
                            if building:
                                buildings.append(building)
                                bld_units = api.get_property_units_by_building(building_id_from_claim)
                                for u in bld_units:
                                    if u.get("id") == unit_id:
                                        units.append(u)
                    except Exception as e:
                        logger.warning(f"Failed to fetch building/unit details: {e}")

            results.append({
                "person": person_record,
                "claims": claims,
                "units": units,
                "buildings": buildings,
            })

        return results

    def get_pending_count(self) -> Dict[str, int]:
        """Get count of pending duplicates by entity type."""
        building_dups = self.detect_building_duplicates()
        unit_dups = self.detect_unit_duplicates()
        person_dups = self.detect_person_duplicates()

        return {
            "building": len(building_dups),
            "unit": len(unit_dups),
            "person": len(person_dups),
            "total": len(building_dups) + len(unit_dups) + len(person_dups)
        }

    # ========== Private Merge Methods ==========

    def _merge_buildings(self, records: List[Dict], master_id: str):
        """Merge building records — keep master, delete duplicates via API."""
        api = self._get_api()
        master = next((r for r in records if r.get("id") == master_id), None)
        if not master:
            raise ValueError(f"Master building not found: {master_id}")

        for record in records:
            if record.get("id") != master_id:
                try:
                    api.delete_building(record["id"])
                except Exception as e:
                    logger.error(f"Failed to delete duplicate building {record.get('id')}: {e}")

    def _merge_units(self, records: List[Dict], master_id: str):
        """Merge unit records — keep master, delete duplicates via API."""
        api = self._get_api()
        for record in records:
            if record.get("id") != master_id:
                try:
                    # Soft-delete by updating status (no direct delete endpoint for units)
                    api.update_property_unit(record["id"], {"isDeleted": True})
                except Exception as e:
                    logger.error(f"Failed to soft-delete duplicate unit {record.get('id')}: {e}")

    def _merge_persons(self, records: List[Dict], master_id: str):
        """Merge person records — keep master, delete duplicates via API."""
        api = self._get_api()
        for record in records:
            if record.get("id") != master_id:
                try:
                    api.delete_person(record["id"])
                except Exception as e:
                    logger.error(f"Failed to delete duplicate person {record.get('id')}: {e}")

    # ========== Resolution Logging ==========

    def _save_resolution(
        self,
        group: DuplicateGroup,
        resolution_type: str,
        master_record_id: Optional[str],
        justification: str,
        user_id: str = None,
        status: str = "resolved"
    ):
        """Save resolution decision to local database (audit trail)."""
        if not self.db:
            logger.warning("No local DB available for resolution logging")
            return

        resolution_id = str(uuid.uuid4())
        record_ids = ",".join(
            r.get("id", "") for r in group.records
        )

        try:
            # Ensure table exists
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS duplicate_resolutions (
                    resolution_id TEXT PRIMARY KEY,
                    entity_type TEXT,
                    group_key TEXT,
                    record_ids TEXT,
                    resolution_type TEXT,
                    master_record_id TEXT,
                    justification TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    status TEXT
                )
            """)

            self.db.execute(
                """INSERT INTO duplicate_resolutions (
                    resolution_id, entity_type, group_key, record_ids,
                    resolution_type, master_record_id, justification,
                    resolved_by, resolved_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolution_id,
                    group.entity_type,
                    group.group_key,
                    record_ids,
                    resolution_type,
                    master_record_id,
                    justification,
                    user_id,
                    datetime.now().isoformat(),
                    status
                )
            )
        except Exception as e:
            logger.warning(f"Failed to save resolution to local DB: {e}")

    def get_resolution_history(self, entity_type: str = None) -> List[Dict[str, Any]]:
        """Get history of duplicate resolutions from local DB."""
        if not self.db:
            return []

        try:
            query = "SELECT * FROM duplicate_resolutions"
            params = []
            if entity_type:
                query += " WHERE entity_type = ?"
                params.append(entity_type)
            query += " ORDER BY resolved_at DESC"
            rows = self.db.fetch_all(query, tuple(params))
            return [dict(row) for row in rows]
        except Exception:
            return []

    def get_resolved_group_keys(self) -> set:
        """Get set of group_keys already resolved (to filter out from detection)."""
        if not self.db:
            return set()

        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS duplicate_resolutions (
                    resolution_id TEXT PRIMARY KEY,
                    entity_type TEXT,
                    group_key TEXT,
                    record_ids TEXT,
                    resolution_type TEXT,
                    master_record_id TEXT,
                    justification TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    status TEXT
                )
            """)
            rows = self.db.fetch_all(
                "SELECT group_key FROM duplicate_resolutions WHERE status IN ('resolved', 'pending_verification')"
            )
            return {row["group_key"] for row in rows}
        except Exception:
            return set()
