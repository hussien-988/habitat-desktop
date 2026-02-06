# -*- coding: utf-8 -*-
"""
Building assignment service for field teams.
Implements UC-012: Assign Buildings to Field Teams
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid
import json

from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)

# Import API client (optional - for Backend sync)
try:
    from services.api_client import TRRCMSApiClient, get_api_client
    API_CLIENT_AVAILABLE = True
except ImportError:
    API_CLIENT_AVAILABLE = False
    logger.warning("API client not available - assignments will be local only")


@dataclass
class BuildingAssignment:
    """Building assignment to field team."""
    assignment_id: str = None
    building_id: str = None
    assigned_to: str = None
    field_team_name: str = None
    tablet_device_id: str = None
    assignment_status: str = "pending"  # pending, assigned, completed, cancelled
    assignment_date: datetime = None
    assigned_by: str = None
    transfer_status: str = "not_transferred"  # not_transferred, transferring, transferred, failed
    transfer_date: datetime = None
    transfer_error: str = None
    requires_revisit: bool = False
    revisit_reason: str = None
    notes: str = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if not self.assignment_id:
            self.assignment_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now()


@dataclass
class FieldTeam:
    """Field team definition."""
    team_id: str
    team_name: str
    supervisor_id: str = None
    device_ids: List[str] = None
    is_active: bool = True


class AssignmentService:
    """
    Service for managing building assignments to field teams.
    Implements UC-012 Assign Buildings to Field Teams.
    """

    def __init__(self, db: Database, api_client: Optional['TRRCMSApiClient'] = None):
        """
        Initialize assignment service.

        Args:
            db: Local database connection
            api_client: Optional API client for Backend sync
        """
        self.db = db
        self.api = api_client or (get_api_client() if API_CLIENT_AVAILABLE else None)
        self.sync_enabled = self.api is not None

        if self.sync_enabled:
            logger.info("✅ AssignmentService: Backend sync enabled")
        else:
            logger.info("⚠️ AssignmentService: Local-only mode (no Backend sync)")

    # ========== Assignment Management ==========

    def create_assignment(
        self,
        building_id: str,
        field_team_name: str,
        assigned_by: str = None,
        requires_revisit: bool = False,
        revisit_reason: str = None,
        notes: str = None
    ) -> BuildingAssignment:
        """
        Create a building assignment (UC-012 S06).

        Args:
            building_id: ID of building to assign
            field_team_name: Name of field team
            assigned_by: User creating assignment
            requires_revisit: Whether building needs revisit
            revisit_reason: Reason for revisit if applicable
            notes: Additional notes
        """
        # Check for existing active assignment
        existing = self.get_assignment_for_building(building_id)
        if existing and existing.assignment_status not in ("completed", "cancelled"):
            raise ValueError(f"Building {building_id} already has an active assignment")

        assignment = BuildingAssignment(
            building_id=building_id,
            field_team_name=field_team_name,
            assigned_by=assigned_by,
            assignment_status="pending",
            assignment_date=datetime.now(),
            requires_revisit=requires_revisit,
            revisit_reason=revisit_reason,
            notes=notes
        )

        query = """
            INSERT INTO building_assignments (
                assignment_id, building_id, assigned_to, field_team_name,
                tablet_device_id, assignment_status, assignment_date, assigned_by,
                transfer_status, requires_revisit, revisit_reason, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            assignment.assignment_id,
            assignment.building_id,
            assignment.assigned_to,
            assignment.field_team_name,
            assignment.tablet_device_id,
            assignment.assignment_status,
            assignment.assignment_date.isoformat() if assignment.assignment_date else None,
            assignment.assigned_by,
            assignment.transfer_status,
            1 if assignment.requires_revisit else 0,
            assignment.revisit_reason,
            assignment.notes,
            assignment.created_at.isoformat() if assignment.created_at else None,
            datetime.now().isoformat()
        )
        self.db.execute(query, params)

        logger.info(f"Created building assignment: {building_id} -> {field_team_name}")
        return assignment

    def create_batch_assignments(
        self,
        building_ids: List[str],
        field_team_name: str,
        assigned_by: str = None,
        notes: str = None
    ) -> List[BuildingAssignment]:
        """
        Create assignments for multiple buildings (UC-012 S07).

        Args:
            building_ids: List of building IDs
            field_team_name: Target field team
            assigned_by: User creating assignments
            notes: Common notes for all assignments
        """
        assignments = []
        errors = []

        for building_id in building_ids:
            try:
                assignment = self.create_assignment(
                    building_id=building_id,
                    field_team_name=field_team_name,
                    assigned_by=assigned_by,
                    notes=notes
                )
                assignments.append(assignment)
            except ValueError as e:
                errors.append(f"{building_id}: {str(e)}")
                logger.warning(f"Skipping assignment for {building_id}: {e}")

        if errors:
            logger.warning(f"Batch assignment completed with {len(errors)} errors")

        # Sync to Backend API if enabled
        if self.sync_enabled and assignments:
            try:
                self.sync_assignments_to_backend(assignments)
            except Exception as e:
                logger.warning(f"Failed to sync assignments to Backend (will remain local): {e}")

        return assignments

    def sync_assignments_to_backend(self, assignments: List[BuildingAssignment]) -> bool:
        """
        مزامنة التعيينات مع Backend API.

        Args:
            assignments: قائمة التعيينات المراد مزامنتها

        Returns:
            True إذا نجحت المزامنة
        """
        if not self.sync_enabled:
            logger.warning("Backend sync is disabled")
            return False

        try:
            # Group assignments by researcher
            by_researcher = {}
            for assignment in assignments:
                researcher = assignment.field_team_name or "unknown"
                if researcher not in by_researcher:
                    by_researcher[researcher] = []
                by_researcher[researcher].append(assignment.building_id)

            # Create assignments in Backend
            for researcher_id, building_ids in by_researcher.items():
                response = self.api.create_assignment(
                    building_ids=building_ids,
                    assigned_to=researcher_id,
                    notes=assignments[0].notes if assignments else None
                )
                logger.info(f"✅ Synced {len(building_ids)} buildings to Backend for researcher: {researcher_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to sync to Backend: {e}", exc_info=True)
            return False

    def get_assignment(self, assignment_id: str) -> Optional[BuildingAssignment]:
        """Get assignment by ID."""
        query = "SELECT * FROM building_assignments WHERE assignment_id = ?"
        row = self.db.fetch_one(query, (assignment_id,))
        if row:
            return self._row_to_assignment(row)
        return None

    def get_assignment_for_building(self, building_id: str) -> Optional[BuildingAssignment]:
        """Get current assignment for a building."""
        query = """
            SELECT * FROM building_assignments
            WHERE building_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = self.db.fetch_one(query, (building_id,))
        if row:
            return self._row_to_assignment(row)
        return None

    def get_assignments(
        self,
        field_team_name: str = None,
        assignment_status: str = None,
        transfer_status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[BuildingAssignment]:
        """Get assignments with optional filters."""
        query = "SELECT * FROM building_assignments WHERE 1=1"
        params = []

        if field_team_name:
            query += " AND field_team_name = ?"
            params.append(field_team_name)

        if assignment_status:
            query += " AND assignment_status = ?"
            params.append(assignment_status)

        if transfer_status:
            query += " AND transfer_status = ?"
            params.append(transfer_status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_assignment(row) for row in rows]

    def get_pending_transfers(self, field_team_name: str = None) -> List[BuildingAssignment]:
        """Get assignments pending transfer."""
        return self.get_assignments(
            field_team_name=field_team_name,
            assignment_status="pending",
            transfer_status="not_transferred"
        )

    def update_assignment_status(
        self,
        assignment_id: str,
        status: str
    ) -> bool:
        """Update assignment status."""
        query = """
            UPDATE building_assignments
            SET assignment_status = ?, updated_at = ?
            WHERE assignment_id = ?
        """
        self.db.execute(query, (status, datetime.now().isoformat(), assignment_id))
        logger.info(f"Updated assignment {assignment_id} status to {status}")
        return True

    def cancel_assignment(self, assignment_id: str, reason: str = None) -> bool:
        """Cancel an assignment."""
        query = """
            UPDATE building_assignments
            SET assignment_status = 'cancelled', notes = ?, updated_at = ?
            WHERE assignment_id = ?
        """
        self.db.execute(query, (reason, datetime.now().isoformat(), assignment_id))
        logger.info(f"Cancelled assignment {assignment_id}")
        return True

    # ========== Transfer Operations (UC-012 S08-S12) ==========

    def initiate_transfer(
        self,
        assignment_ids: List[str],
        tablet_device_id: str
    ) -> Dict[str, Any]:
        """
        Initiate transfer of assignments to tablet (UC-012 S08).

        In a real implementation, this would:
        1. Prepare payload with building data
        2. Connect to tablet via LAN
        3. Send data and await acknowledgment

        For this simulation, we mark as transferring.
        """
        results = {
            "success": [],
            "failed": [],
            "payload_prepared": True
        }

        for assignment_id in assignment_ids:
            try:
                query = """
                    UPDATE building_assignments
                    SET transfer_status = 'transferring',
                        tablet_device_id = ?,
                        updated_at = ?
                    WHERE assignment_id = ?
                """
                self.db.execute(query, (tablet_device_id, datetime.now().isoformat(), assignment_id))
                results["success"].append(assignment_id)
            except Exception as e:
                results["failed"].append({"id": assignment_id, "error": str(e)})

        logger.info(f"Initiated transfer for {len(results['success'])} assignments")
        return results

    def complete_transfer(self, assignment_id: str) -> bool:
        """
        Mark transfer as complete (UC-012 S10).
        Called after tablet acknowledges receipt.
        """
        query = """
            UPDATE building_assignments
            SET transfer_status = 'transferred',
                transfer_date = ?,
                assignment_status = 'assigned',
                updated_at = ?
            WHERE assignment_id = ?
        """
        self.db.execute(query, (
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            assignment_id
        ))
        logger.info(f"Transfer completed for assignment {assignment_id}")
        return True

    def fail_transfer(self, assignment_id: str, error_message: str) -> bool:
        """
        Mark transfer as failed (UC-012 S11).
        """
        query = """
            UPDATE building_assignments
            SET transfer_status = 'failed',
                transfer_error = ?,
                updated_at = ?
            WHERE assignment_id = ?
        """
        self.db.execute(query, (error_message, datetime.now().isoformat(), assignment_id))
        logger.warning(f"Transfer failed for assignment {assignment_id}: {error_message}")
        return True

    def retry_transfer(self, assignment_id: str) -> bool:
        """
        Reset transfer status for retry (UC-012 S12).
        """
        query = """
            UPDATE building_assignments
            SET transfer_status = 'not_transferred',
                transfer_error = NULL,
                updated_at = ?
            WHERE assignment_id = ?
        """
        self.db.execute(query, (datetime.now().isoformat(), assignment_id))
        logger.info(f"Reset transfer for retry: {assignment_id}")
        return True

    # ========== Field Teams ==========

    def get_field_teams(self) -> List[Dict[str, str]]:
        """
        Get list of field researchers from users table.
        Returns users with role='field_researcher'.
        """
        query = """
            SELECT user_id, username, full_name, full_name_ar
            FROM users
            WHERE role = 'field_researcher' AND is_active = 1
            ORDER BY full_name_ar, full_name
        """
        rows = self.db.fetch_all(query)

        teams = []
        for row in rows:
            display_name = row.get("full_name_ar") or row.get("full_name") or row.get("username")
            teams.append({
                "team_id": row["user_id"],
                "team_name": display_name,
                "researcher_id": row["user_id"]
            })

        # Fallback: if no field_researchers, return empty list with message
        if not teams:
            logger.warning("No field researchers found in database")

        return teams

    def get_available_tablets(self) -> List[Dict[str, str]]:
        """
        Get list of available tablet devices.

        TODO: Implement LAN device discovery (mDNS/Bonjour).
        For now, returns simulated list + manual IP entry option.
        """
        # Simulated tablets for development
        tablets = [
            {"device_id": "tablet_001", "device_name": "Tablet 001 (192.168.1.50)", "status": "connected", "ip": "192.168.1.50"},
            {"device_id": "tablet_002", "device_name": "Tablet 002 (192.168.1.51)", "status": "connected", "ip": "192.168.1.51"},
            {"device_id": "manual", "device_name": "إدخال IP يدوياً...", "status": "manual", "ip": None},
        ]

        # TODO: Add real LAN discovery using zeroconf/mDNS
        # try:
        #     from services.sync_server_service import SyncServerService
        #     discovered = SyncServerService.discover_tablets_on_lan()
        #     tablets.extend(discovered)
        # except Exception as e:
        #     logger.warning(f"Failed to discover tablets: {e}")

        return tablets

    # ========== Statistics ==========

    def get_assignment_statistics(self) -> Dict[str, Any]:
        """Get assignment statistics for dashboard."""
        stats = {}

        # Total assignments
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM building_assignments")
        stats["total"] = result["count"] if result else 0

        # By status
        rows = self.db.fetch_all("""
            SELECT assignment_status, COUNT(*) as count
            FROM building_assignments
            GROUP BY assignment_status
        """)
        stats["by_status"] = {row["assignment_status"]: row["count"] for row in rows}

        # By transfer status
        rows = self.db.fetch_all("""
            SELECT transfer_status, COUNT(*) as count
            FROM building_assignments
            GROUP BY transfer_status
        """)
        stats["by_transfer"] = {row["transfer_status"]: row["count"] for row in rows}

        # By team
        rows = self.db.fetch_all("""
            SELECT field_team_name, COUNT(*) as count
            FROM building_assignments
            WHERE field_team_name IS NOT NULL
            GROUP BY field_team_name
        """)
        stats["by_team"] = {row["field_team_name"]: row["count"] for row in rows}

        # Pending transfers
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM building_assignments
            WHERE transfer_status = 'not_transferred' AND assignment_status = 'pending'
        """)
        stats["pending_transfers"] = result["count"] if result else 0

        return stats

    def _row_to_assignment(self, row) -> BuildingAssignment:
        """Convert database row to BuildingAssignment."""
        data = dict(row)

        # Parse datetime fields
        for field in ["assignment_date", "transfer_date", "created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Parse boolean fields
        data["requires_revisit"] = bool(data.get("requires_revisit", 0))

        return BuildingAssignment(**{k: v for k, v in data.items()
                                     if k in BuildingAssignment.__dataclass_fields__})
