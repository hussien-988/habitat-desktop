# -*- coding: utf-8 -*-
"""
Duplicate detection and resolution service.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import uuid

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.unit_repository import UnitRepository
from repositories.person_repository import PersonRepository
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DuplicateGroup:
    """Represents a group of potential duplicate records."""
    group_id: str
    entity_type: str  # "building", "unit", or "person"
    group_key: str  # The shared key (building_id, unit composite key, or national_id)
    records: List[Dict[str, Any]]
    status: str = "pending"  # pending, resolved, escalated


class DuplicateService:
    """
    Service for detecting and resolving duplicate records.

    Property duplicates (UC-007): Detected by identical building_id or
    building_id + unit_number composite key.

    Person duplicates (UC-008): Detected by identical national_id.
    """

    def __init__(self, db: Database):
        self.db = db
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self.person_repo = PersonRepository(db)

    # ========== Property Duplicate Detection (UC-007) ==========

    def detect_building_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect buildings with duplicate building_id values.
        Per UC-007: Detect when two or more building records share the same building_id.
        """
        query = """
            SELECT building_id, COUNT(*) as cnt
            FROM buildings
            GROUP BY building_id
            HAVING COUNT(*) > 1
        """
        rows = self.db.fetch_all(query)

        groups = []
        for row in rows:
            building_id = row["building_id"]
            # Get all buildings with this ID
            buildings = self._get_buildings_by_id(building_id)

            if len(buildings) > 1:
                group = DuplicateGroup(
                    group_id=str(uuid.uuid4()),
                    entity_type="building",
                    group_key=building_id,
                    records=buildings,
                    status="pending"
                )
                groups.append(group)

        logger.info(f"Detected {len(groups)} building duplicate groups")
        return groups

    def detect_unit_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect units with duplicate building_id + unit_number composite keys.
        Per UC-007: Detect identical composite key (building_id + unit_number).
        """
        query = """
            SELECT building_id, unit_number, COUNT(*) as cnt
            FROM property_units
            WHERE unit_number IS NOT NULL AND unit_number != ''
            GROUP BY building_id, unit_number
            HAVING COUNT(*) > 1
        """
        rows = self.db.fetch_all(query)

        groups = []
        for row in rows:
            building_id = row["building_id"]
            unit_number = row["unit_number"]
            composite_key = f"{building_id}:{unit_number}"

            # Get all units with this composite key
            units = self._get_units_by_composite_key(building_id, unit_number)

            if len(units) > 1:
                group = DuplicateGroup(
                    group_id=str(uuid.uuid4()),
                    entity_type="unit",
                    group_key=composite_key,
                    records=units,
                    status="pending"
                )
                groups.append(group)

        logger.info(f"Detected {len(groups)} unit duplicate groups")
        return groups

    def get_all_property_duplicates(self) -> List[DuplicateGroup]:
        """Get all property (building + unit) duplicate groups."""
        building_dups = self.detect_building_duplicates()
        unit_dups = self.detect_unit_duplicates()
        return building_dups + unit_dups

    # ========== Person Duplicate Detection (UC-008) ==========

    def detect_person_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect persons with duplicate national_id values.
        Per UC-008: Detect when two or more Person records share the same national_id.
        """
        query = """
            SELECT national_id, COUNT(*) as cnt
            FROM persons
            WHERE national_id IS NOT NULL AND national_id != ''
            GROUP BY national_id
            HAVING COUNT(*) > 1
        """
        rows = self.db.fetch_all(query)

        groups = []
        for row in rows:
            national_id = row["national_id"]
            # Get all persons with this ID
            persons = self._get_persons_by_national_id(national_id)

            if len(persons) > 1:
                group = DuplicateGroup(
                    group_id=str(uuid.uuid4()),
                    entity_type="person",
                    group_key=national_id,
                    records=persons,
                    status="pending"
                )
                groups.append(group)

        logger.info(f"Detected {len(groups)} person duplicate groups")
        return groups

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
        The master record is kept, others are merged into it.

        Args:
            group: The duplicate group to resolve
            master_record_id: ID of the record to keep as master
            justification: Reason for the merge decision
            user_id: ID of user performing the resolution
        """
        try:
            record_ids = [r.get("building_uuid") or r.get("unit_uuid") or r.get("person_uuid")
                         for r in group.records]

            # Log the resolution
            self._save_resolution(
                group=group,
                resolution_type="merge",
                master_record_id=master_record_id,
                justification=justification,
                user_id=user_id
            )

            # Perform entity-specific merge
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
        Per UC-007/UC-008: Keep-separate decisions prevent re-surfacing.
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
        Per UC-007/UC-008 S05a: Complex cases requiring investigation.
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

    # ========== Helper Methods ==========

    def _get_buildings_by_id(self, building_id: str) -> List[Dict[str, Any]]:
        """Get all building records with a specific building_id."""
        query = "SELECT * FROM buildings WHERE building_id = ?"
        rows = self.db.fetch_all(query, (building_id,))
        return [dict(row) for row in rows]

    def _get_units_by_composite_key(self, building_id: str, unit_number: str) -> List[Dict[str, Any]]:
        """Get all unit records with a specific building_id + unit_number."""
        query = "SELECT * FROM property_units WHERE building_id = ? AND unit_number = ?"
        rows = self.db.fetch_all(query, (building_id, unit_number))
        return [dict(row) for row in rows]

    def _get_persons_by_national_id(self, national_id: str) -> List[Dict[str, Any]]:
        """Get all person records with a specific national_id."""
        query = "SELECT * FROM persons WHERE national_id = ?"
        rows = self.db.fetch_all(query, (national_id,))
        return [dict(row) for row in rows]

    def _save_resolution(
        self,
        group: DuplicateGroup,
        resolution_type: str,
        master_record_id: Optional[str],
        justification: str,
        user_id: str = None,
        status: str = "resolved"
    ):
        """Save resolution decision to database."""
        resolution_id = str(uuid.uuid4())
        record_ids = ",".join(
            r.get("building_uuid") or r.get("unit_uuid") or r.get("person_uuid") or ""
            for r in group.records
        )

        query = """
            INSERT INTO duplicate_resolutions (
                resolution_id, entity_type, group_key, record_ids,
                resolution_type, master_record_id, justification,
                resolved_by, resolved_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
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
        self.db.execute(query, params)

    def _merge_buildings(self, records: List[Dict], master_uuid: str):
        """
        Merge building records into master.
        Updates all references (units, claims) to point to master.
        """
        master = next((r for r in records if r["building_uuid"] == master_uuid), None)
        if not master:
            raise ValueError(f"Master building not found: {master_uuid}")

        for record in records:
            if record["building_uuid"] != master_uuid:
                # Update units to reference master building
                self.db.execute(
                    "UPDATE property_units SET building_id = ? WHERE building_id = ?",
                    (master["building_id"], record["building_id"])
                )
                # Delete the duplicate building
                self.db.execute(
                    "DELETE FROM buildings WHERE building_uuid = ?",
                    (record["building_uuid"],)
                )

    def _merge_units(self, records: List[Dict], master_uuid: str):
        """
        Merge unit records into master.
        Updates all references (relations, claims) to point to master.
        """
        master = next((r for r in records if r["unit_uuid"] == master_uuid), None)
        if not master:
            raise ValueError(f"Master unit not found: {master_uuid}")

        for record in records:
            if record["unit_uuid"] != master_uuid:
                # Update person-unit relations to reference master
                self.db.execute(
                    "UPDATE person_unit_relations SET unit_id = ? WHERE unit_id = ?",
                    (master["unit_id"], record["unit_id"])
                )
                # Update claims to reference master
                self.db.execute(
                    "UPDATE claims SET unit_id = ? WHERE unit_id = ?",
                    (master["unit_id"], record["unit_id"])
                )
                # Delete the duplicate unit
                self.db.execute(
                    "DELETE FROM property_units WHERE unit_uuid = ?",
                    (record["unit_uuid"],)
                )

    def _merge_persons(self, records: List[Dict], master_uuid: str):
        """
        Merge person records into master.
        Updates all references (relations, claims, households) to point to master.
        """
        master = next((r for r in records if r["person_uuid"] == master_uuid), None)
        if not master:
            raise ValueError(f"Master person not found: {master_uuid}")

        for record in records:
            if record["person_uuid"] != master_uuid:
                # Update person-unit relations to reference master
                self.db.execute(
                    "UPDATE person_unit_relations SET person_id = ? WHERE person_id = ?",
                    (master["person_id"], record["person_id"])
                )
                # Update claims to reference master (person_ids is comma-separated)
                self._update_claim_person_references(record["person_id"], master["person_id"])
                # Delete the duplicate person
                self.db.execute(
                    "DELETE FROM persons WHERE person_uuid = ?",
                    (record["person_uuid"],)
                )

    def _update_claim_person_references(self, old_person_id: str, new_person_id: str):
        """Update person_ids field in claims (comma-separated list)."""
        query = "SELECT claim_uuid, person_ids FROM claims WHERE person_ids LIKE ?"
        rows = self.db.fetch_all(query, (f"%{old_person_id}%",))

        for row in rows:
            person_ids = row["person_ids"]
            # Replace old ID with new ID
            updated_ids = person_ids.replace(old_person_id, new_person_id)
            # Remove any duplicate IDs that might result
            id_list = [p.strip() for p in updated_ids.split(",") if p.strip()]
            unique_ids = list(dict.fromkeys(id_list))  # Preserve order, remove dups

            self.db.execute(
                "UPDATE claims SET person_ids = ? WHERE claim_uuid = ?",
                (",".join(unique_ids), row["claim_uuid"])
            )

    def get_resolution_history(self, entity_type: str = None) -> List[Dict[str, Any]]:
        """Get history of duplicate resolutions."""
        query = "SELECT * FROM duplicate_resolutions"
        params = []

        if entity_type:
            query += " WHERE entity_type = ?"
            params.append(entity_type)

        query += " ORDER BY resolved_at DESC"

        rows = self.db.fetch_all(query, tuple(params))
        return [dict(row) for row in rows]

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
