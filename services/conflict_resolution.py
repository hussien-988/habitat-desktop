# -*- coding: utf-8 -*-
"""
Conflict Resolution Service
===========================
Implements FR-D-7 from FSD v5.0

Features:
- Field-level conflict detection
- Conflict resolution queue with human review
- Automated resolution policies
- Merge strategies for duplicate entities
- Audit trail for all resolutions
- Priority-based queue management
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts."""
    DUPLICATE_PERSON = "duplicate_person"
    DUPLICATE_BUILDING = "duplicate_building"
    DUPLICATE_UNIT = "duplicate_unit"
    DUPLICATE_CLAIM = "duplicate_claim"
    FIELD_MISMATCH = "field_mismatch"
    OWNERSHIP_CONFLICT = "ownership_conflict"
    BOUNDARY_OVERLAP = "boundary_overlap"
    CLAIM_OVERLAP = "claim_overlap"


class ConflictPriority(Enum):
    """Priority levels for conflicts."""
    CRITICAL = "critical"    # Must resolve before commit
    HIGH = "high"            # Should resolve soon
    MEDIUM = "medium"        # Normal priority
    LOW = "low"              # Can wait


class ConflictStatus(Enum):
    """Status of a conflict."""
    PENDING = "pending"              # Awaiting review
    IN_REVIEW = "in_review"          # Being reviewed
    AUTO_RESOLVED = "auto_resolved"  # Resolved by policy
    RESOLVED = "resolved"            # Manually resolved
    ESCALATED = "escalated"          # Escalated to supervisor
    DEFERRED = "deferred"            # Deferred for later


class ResolutionAction(Enum):
    """Resolution actions for conflicts."""
    MERGE = "merge"                  # Merge records
    KEEP_EXISTING = "keep_existing"  # Keep existing record
    KEEP_NEW = "keep_new"            # Keep new record
    KEEP_BOTH = "keep_both"          # Keep both as separate
    MANUAL_EDIT = "manual_edit"      # Manual editing required
    SKIP = "skip"                    # Skip the new record


class MergeStrategy(Enum):
    """Strategies for merging conflicting fields."""
    KEEP_SOURCE = "keep_source"      # Keep source value
    KEEP_TARGET = "keep_target"      # Keep target value
    KEEP_NEWEST = "keep_newest"      # Keep most recent
    KEEP_OLDEST = "keep_oldest"      # Keep oldest
    CONCATENATE = "concatenate"      # Combine values
    PREFER_COMPLETE = "prefer_complete"  # Prefer non-null


@dataclass
class FieldConflict:
    """A conflict on a specific field."""
    field_name: str
    source_value: Any
    target_value: Any
    resolution: Optional[str] = None
    resolved_value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'field_name': self.field_name,
            'source_value': str(self.source_value) if self.source_value is not None else None,
            'target_value': str(self.target_value) if self.target_value is not None else None,
            'resolution': self.resolution,
            'resolved_value': str(self.resolved_value) if self.resolved_value is not None else None
        }


@dataclass
class Conflict:
    """A conflict requiring resolution."""
    conflict_id: str
    conflict_type: ConflictType
    priority: ConflictPriority
    status: ConflictStatus
    source_entity_type: str
    source_entity_id: str
    source_data: Dict[str, Any]
    target_entity_id: Optional[str]
    target_data: Optional[Dict[str, Any]]
    field_conflicts: List[FieldConflict] = field(default_factory=list)
    match_score: float = 0.0
    import_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution: Optional[ResolutionAction] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'conflict_id': self.conflict_id,
            'conflict_type': self.conflict_type.value,
            'priority': self.priority.value,
            'status': self.status.value,
            'source_entity_type': self.source_entity_type,
            'source_entity_id': self.source_entity_id,
            'source_data': self.source_data,
            'target_entity_id': self.target_entity_id,
            'target_data': self.target_data,
            'field_conflicts': [f.to_dict() for f in self.field_conflicts],
            'match_score': self.match_score,
            'import_id': self.import_id,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'assigned_to': self.assigned_to,
            'resolution': self.resolution.value if self.resolution else None,
            'resolution_notes': self.resolution_notes,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by
        }


@dataclass
class ResolutionPolicy:
    """Policy for automatic conflict resolution."""
    conflict_type: ConflictType
    field_name: Optional[str]
    condition: str
    strategy: MergeStrategy
    priority: int = 0

    def matches(self, conflict: Conflict, field_conflict: Optional[FieldConflict] = None) -> bool:
        """Check if policy matches conflict."""
        if self.conflict_type != conflict.conflict_type:
            return False

        if self.field_name and field_conflict:
            if self.field_name != field_conflict.field_name:
                return False

        return True


class ConflictResolutionService:
    """
    Conflict resolution service for managing data conflicts.

    Per FR-D-7: Conflicts queue for human review with automated policies.
    """

    # Default resolution policies
    DEFAULT_POLICIES = [
        # Keep newest for timestamps
        ResolutionPolicy(
            ConflictType.FIELD_MISMATCH,
            'updated_at',
            'always',
            MergeStrategy.KEEP_NEWEST,
            priority=10
        ),
        # Prefer complete data for optional fields
        ResolutionPolicy(
            ConflictType.FIELD_MISMATCH,
            'phone_number',
            'one_null',
            MergeStrategy.PREFER_COMPLETE,
            priority=5
        ),
        ResolutionPolicy(
            ConflictType.FIELD_MISMATCH,
            'mobile_number',
            'one_null',
            MergeStrategy.PREFER_COMPLETE,
            priority=5
        ),
        ResolutionPolicy(
            ConflictType.FIELD_MISMATCH,
            'email',
            'one_null',
            MergeStrategy.PREFER_COMPLETE,
            priority=5
        ),
    ]

    def __init__(self, db):
        """
        Initialize conflict resolution service.

        Args:
            db: Database instance
        """
        self.db = db
        self.policies: List[ResolutionPolicy] = list(self.DEFAULT_POLICIES)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure conflict tables exist."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    conflict_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_entity_type TEXT NOT NULL,
                    source_entity_id TEXT NOT NULL,
                    source_data TEXT,
                    target_entity_id TEXT,
                    target_data TEXT,
                    field_conflicts TEXT,
                    match_score REAL,
                    import_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    assigned_to TEXT,
                    resolution TEXT,
                    resolution_notes TEXT,
                    resolved_at TIMESTAMP,
                    resolved_by TEXT
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS conflict_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conflict_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    details TEXT,
                    performed_by TEXT,
                    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_priority ON conflicts(priority)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_type ON conflicts(conflict_type)")

        except Exception as e:
            logger.warning(f"Could not create conflict tables: {e}")

    # ==================== Conflict Detection ====================

    def detect_conflicts(
        self,
        source_data: Dict[str, Any],
        target_data: Dict[str, Any],
        entity_type: str,
        match_score: float = 0.0,
        import_id: Optional[str] = None
    ) -> Optional[Conflict]:
        """
        Detect conflicts between source and target entities.

        Args:
            source_data: New/incoming data
            target_data: Existing data
            entity_type: Type of entity (person, building, etc.)
            match_score: Match confidence score
            import_id: Associated import ID

        Returns:
            Conflict if detected, None otherwise
        """
        field_conflicts = []

        # Compare fields
        all_fields = set(source_data.keys()) | set(target_data.keys())

        for field_name in all_fields:
            # Skip internal fields
            if field_name in ['id', 'created_at', 'updated_at', 'version']:
                continue

            source_val = source_data.get(field_name)
            target_val = target_data.get(field_name)

            # Check for conflict
            if source_val != target_val:
                # Skip if both are None/empty
                if not source_val and not target_val:
                    continue

                field_conflicts.append(FieldConflict(
                    field_name=field_name,
                    source_value=source_val,
                    target_value=target_val
                ))

        if not field_conflicts:
            return None

        # Determine conflict type
        conflict_type = self._determine_conflict_type(entity_type, field_conflicts)

        # Determine priority
        priority = self._determine_priority(conflict_type, field_conflicts, match_score)

        # Create conflict
        conflict_id = f"CON-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{hash(str(source_data))}"

        return Conflict(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            priority=priority,
            status=ConflictStatus.PENDING,
            source_entity_type=entity_type,
            source_entity_id=source_data.get('id') or source_data.get(f'{entity_type}_id', 'new'),
            source_data=source_data,
            target_entity_id=target_data.get('id') or target_data.get(f'{entity_type}_id'),
            target_data=target_data,
            field_conflicts=field_conflicts,
            match_score=match_score,
            import_id=import_id
        )

    def _determine_conflict_type(
        self,
        entity_type: str,
        field_conflicts: List[FieldConflict]
    ) -> ConflictType:
        """Determine the type of conflict."""
        # Check for ownership conflicts
        ownership_fields = ['ownership_share', 'relation_type', 'claim_type']
        if any(fc.field_name in ownership_fields for fc in field_conflicts):
            return ConflictType.OWNERSHIP_CONFLICT

        # Check for claim conflicts
        claim_fields = ['claim_id', 'case_status', 'claimant_id']
        if any(fc.field_name in claim_fields for fc in field_conflicts):
            return ConflictType.CLAIM_OVERLAP

        # Entity-type based
        type_map = {
            'person': ConflictType.DUPLICATE_PERSON,
            'building': ConflictType.DUPLICATE_BUILDING,
            'unit': ConflictType.DUPLICATE_UNIT,
            'claim': ConflictType.DUPLICATE_CLAIM
        }

        return type_map.get(entity_type, ConflictType.FIELD_MISMATCH)

    def _determine_priority(
        self,
        conflict_type: ConflictType,
        field_conflicts: List[FieldConflict],
        match_score: float
    ) -> ConflictPriority:
        """Determine priority of conflict."""
        # Ownership and claim conflicts are high priority
        if conflict_type in [ConflictType.OWNERSHIP_CONFLICT, ConflictType.CLAIM_OVERLAP]:
            return ConflictPriority.CRITICAL

        # High match score = likely duplicate
        if match_score >= 0.9:
            return ConflictPriority.HIGH

        # Many field conflicts
        if len(field_conflicts) >= 5:
            return ConflictPriority.HIGH

        if match_score >= 0.7:
            return ConflictPriority.MEDIUM

        return ConflictPriority.LOW

    # ==================== Queue Management ====================

    def add_to_queue(self, conflict: Conflict, created_by: str = 'system') -> str:
        """
        Add a conflict to the resolution queue.

        Per FR-D-7: Conflicts queue for human review.
        """
        conflict.created_by = created_by

        self.db.execute("""
            INSERT INTO conflicts (
                conflict_id, conflict_type, priority, status,
                source_entity_type, source_entity_id, source_data,
                target_entity_id, target_data, field_conflicts,
                match_score, import_id, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conflict.conflict_id,
            conflict.conflict_type.value,
            conflict.priority.value,
            conflict.status.value,
            conflict.source_entity_type,
            conflict.source_entity_id,
            json.dumps(conflict.source_data),
            conflict.target_entity_id,
            json.dumps(conflict.target_data) if conflict.target_data else None,
            json.dumps([fc.to_dict() for fc in conflict.field_conflicts]),
            conflict.match_score,
            conflict.import_id,
            conflict.created_at.isoformat(),
            created_by
        ))

        self._log_action(conflict.conflict_id, 'created', None, conflict.status.value, {}, created_by)

        logger.info(f"Added conflict to queue: {conflict.conflict_id}")
        return conflict.conflict_id

    def get_queue(
        self,
        status: Optional[ConflictStatus] = None,
        priority: Optional[ConflictPriority] = None,
        conflict_type: Optional[ConflictType] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conflict]:
        """Get conflicts from queue with filters."""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        else:
            conditions.append("status IN ('pending', 'in_review')")

        if priority:
            conditions.append("priority = ?")
            params.append(priority.value)

        if conflict_type:
            conditions.append("conflict_type = ?")
            params.append(conflict_type.value)

        if assigned_to:
            conditions.append("assigned_to = ?")
            params.append(assigned_to)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM conflicts
            WHERE {where_clause}
            ORDER BY
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                created_at ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        result = self.db.execute(query, params)
        return [self._row_to_conflict(row) for row in result]

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the conflict queue."""
        result = self.db.execute("""
            SELECT
                status,
                priority,
                conflict_type,
                COUNT(*) as count
            FROM conflicts
            WHERE status IN ('pending', 'in_review')
            GROUP BY status, priority, conflict_type
        """)

        stats = {
            'total_pending': 0,
            'by_status': {},
            'by_priority': {},
            'by_type': {}
        }

        for row in result:
            status = row[0] if isinstance(row, tuple) else row['status']
            priority = row[1] if isinstance(row, tuple) else row['priority']
            ctype = row[2] if isinstance(row, tuple) else row['conflict_type']
            count = row[3] if isinstance(row, tuple) else row['count']

            stats['total_pending'] += count

            if status not in stats['by_status']:
                stats['by_status'][status] = 0
            stats['by_status'][status] += count

            if priority not in stats['by_priority']:
                stats['by_priority'][priority] = 0
            stats['by_priority'][priority] += count

            if ctype not in stats['by_type']:
                stats['by_type'][ctype] = 0
            stats['by_type'][ctype] += count

        return stats

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Get a specific conflict by ID."""
        result = self.db.execute(
            "SELECT * FROM conflicts WHERE conflict_id = ?",
            (conflict_id,)
        )

        if result and len(result) > 0:
            return self._row_to_conflict(result[0])
        return None

    # ==================== Resolution ====================

    def assign_conflict(
        self,
        conflict_id: str,
        assigned_to: str,
        assigned_by: str
    ) -> bool:
        """Assign a conflict to a user for review."""
        self.db.execute("""
            UPDATE conflicts
            SET assigned_to = ?, status = ?
            WHERE conflict_id = ?
        """, (assigned_to, ConflictStatus.IN_REVIEW.value, conflict_id))

        self._log_action(
            conflict_id,
            'assigned',
            ConflictStatus.PENDING.value,
            ConflictStatus.IN_REVIEW.value,
            {'assigned_to': assigned_to},
            assigned_by
        )

        return True

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: ResolutionAction,
        resolved_by: str,
        field_resolutions: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Resolve a conflict.

        Args:
            conflict_id: Conflict to resolve
            resolution: Resolution action
            resolved_by: User resolving
            field_resolutions: Per-field resolution values
            notes: Resolution notes

        Returns:
            True if resolved successfully
        """
        conflict = self.get_conflict(conflict_id)
        if not conflict:
            return False

        # Update field conflicts with resolutions
        if field_resolutions:
            for fc in conflict.field_conflicts:
                if fc.field_name in field_resolutions:
                    fc.resolution = 'manual'
                    fc.resolved_value = field_resolutions[fc.field_name]

        # Execute resolution
        if resolution == ResolutionAction.MERGE:
            self._execute_merge(conflict, field_resolutions)
        elif resolution == ResolutionAction.KEEP_EXISTING:
            pass  # No action needed
        elif resolution == ResolutionAction.KEEP_NEW:
            self._execute_replace(conflict)
        elif resolution == ResolutionAction.KEEP_BOTH:
            pass  # Both records remain

        # Update conflict record
        self.db.execute("""
            UPDATE conflicts
            SET status = ?, resolution = ?, resolution_notes = ?,
                resolved_at = ?, resolved_by = ?,
                field_conflicts = ?
            WHERE conflict_id = ?
        """, (
            ConflictStatus.RESOLVED.value,
            resolution.value,
            notes,
            datetime.utcnow().isoformat(),
            resolved_by,
            json.dumps([fc.to_dict() for fc in conflict.field_conflicts]),
            conflict_id
        ))

        self._log_action(
            conflict_id,
            'resolved',
            conflict.status.value,
            ConflictStatus.RESOLVED.value,
            {'resolution': resolution.value, 'notes': notes},
            resolved_by
        )

        logger.info(f"Resolved conflict {conflict_id} with action {resolution.value}")
        return True

    def auto_resolve(self, conflict: Conflict) -> Optional[ResolutionAction]:
        """
        Attempt automatic resolution based on policies.

        Returns:
            Resolution action if auto-resolved, None otherwise
        """
        resolved_fields = []

        for fc in conflict.field_conflicts:
            # Find applicable policy
            policy = self._find_applicable_policy(conflict, fc)

            if policy:
                resolved_value = self._apply_strategy(
                    policy.strategy,
                    fc.source_value,
                    fc.target_value,
                    conflict
                )
                fc.resolution = 'auto'
                fc.resolved_value = resolved_value
                resolved_fields.append(fc.field_name)

        # If all fields resolved, determine overall action
        if len(resolved_fields) == len(conflict.field_conflicts):
            # Update status
            self.db.execute("""
                UPDATE conflicts
                SET status = ?, resolution = ?,
                    field_conflicts = ?,
                    resolved_at = ?, resolved_by = ?
                WHERE conflict_id = ?
            """, (
                ConflictStatus.AUTO_RESOLVED.value,
                ResolutionAction.MERGE.value,
                json.dumps([fc.to_dict() for fc in conflict.field_conflicts]),
                datetime.utcnow().isoformat(),
                'system',
                conflict.conflict_id
            ))

            self._log_action(
                conflict.conflict_id,
                'auto_resolved',
                conflict.status.value,
                ConflictStatus.AUTO_RESOLVED.value,
                {'resolved_fields': resolved_fields},
                'system'
            )

            return ResolutionAction.MERGE

        return None

    def _find_applicable_policy(
        self,
        conflict: Conflict,
        field_conflict: FieldConflict
    ) -> Optional[ResolutionPolicy]:
        """Find the most applicable policy for a field conflict."""
        applicable = []

        for policy in self.policies:
            if policy.matches(conflict, field_conflict):
                # Check condition
                if self._check_condition(policy.condition, field_conflict):
                    applicable.append(policy)

        if not applicable:
            return None

        # Return highest priority policy
        applicable.sort(key=lambda p: p.priority, reverse=True)
        return applicable[0]

    def _check_condition(
        self,
        condition: str,
        field_conflict: FieldConflict
    ) -> bool:
        """Check if condition is met for policy application."""
        if condition == 'always':
            return True
        elif condition == 'one_null':
            return (field_conflict.source_value is None) != (field_conflict.target_value is None)
        elif condition == 'both_present':
            return field_conflict.source_value is not None and field_conflict.target_value is not None
        return False

    def _apply_strategy(
        self,
        strategy: MergeStrategy,
        source_value: Any,
        target_value: Any,
        conflict: Conflict
    ) -> Any:
        """Apply merge strategy to get resolved value."""
        if strategy == MergeStrategy.KEEP_SOURCE:
            return source_value
        elif strategy == MergeStrategy.KEEP_TARGET:
            return target_value
        elif strategy == MergeStrategy.PREFER_COMPLETE:
            if source_value is None or source_value == '':
                return target_value
            return source_value
        elif strategy == MergeStrategy.CONCATENATE:
            if source_value and target_value:
                return f"{source_value}; {target_value}"
            return source_value or target_value
        elif strategy == MergeStrategy.KEEP_NEWEST:
            # Would need timestamps to determine
            return source_value  # Assume source is newer
        elif strategy == MergeStrategy.KEEP_OLDEST:
            return target_value  # Assume target is older

        return source_value

    def _execute_merge(
        self,
        conflict: Conflict,
        field_resolutions: Optional[Dict[str, Any]] = None
    ) -> None:
        """Execute merge of records."""
        if not conflict.target_entity_id:
            return

        # Build merged data
        merged_data = dict(conflict.target_data or {})

        for fc in conflict.field_conflicts:
            if fc.resolved_value is not None:
                merged_data[fc.field_name] = fc.resolved_value

        # Override with manual resolutions
        if field_resolutions:
            merged_data.update(field_resolutions)

        # Update target record
        # Implementation depends on entity type
        entity_type = conflict.source_entity_type

        if entity_type == 'person':
            self._update_person(conflict.target_entity_id, merged_data)
        elif entity_type == 'building':
            self._update_building(conflict.target_entity_id, merged_data)

    def _execute_replace(self, conflict: Conflict) -> None:
        """Replace existing record with new data."""
        if not conflict.target_entity_id:
            return

        entity_type = conflict.source_entity_type

        if entity_type == 'person':
            self._update_person(conflict.target_entity_id, conflict.source_data)
        elif entity_type == 'building':
            self._update_building(conflict.target_entity_id, conflict.source_data)

    def _update_person(self, person_id: str, data: Dict[str, Any]) -> None:
        """Update person record."""
        # Build update query
        fields = ['first_name', 'father_name', 'last_name', 'phone_number',
                  'mobile_number', 'gender', 'year_of_birth', 'national_id']

        updates = []
        params = []

        for f in fields:
            if f in data:
                updates.append(f"{f} = ?")
                params.append(data[f])

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(person_id)

            self.db.execute(
                f"UPDATE persons SET {', '.join(updates)} WHERE person_id = ?",
                params
            )

    def _update_building(self, building_id: str, data: Dict[str, Any]) -> None:
        """Update building record."""
        fields = ['building_type', 'building_status', 'floors_count',
                  'units_count', 'latitude', 'longitude']

        updates = []
        params = []

        for f in fields:
            if f in data:
                updates.append(f"{f} = ?")
                params.append(data[f])

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(building_id)

            self.db.execute(
                f"UPDATE buildings SET {', '.join(updates)} WHERE building_id = ?",
                params
            )

    # ==================== Escalation ====================

    def escalate_conflict(
        self,
        conflict_id: str,
        escalated_by: str,
        reason: str
    ) -> bool:
        """Escalate a conflict to supervisor."""
        self.db.execute("""
            UPDATE conflicts
            SET status = ?, resolution_notes = ?
            WHERE conflict_id = ?
        """, (
            ConflictStatus.ESCALATED.value,
            f"Escalated: {reason}",
            conflict_id
        ))

        self._log_action(
            conflict_id,
            'escalated',
            ConflictStatus.IN_REVIEW.value,
            ConflictStatus.ESCALATED.value,
            {'reason': reason},
            escalated_by
        )

        return True

    def defer_conflict(
        self,
        conflict_id: str,
        deferred_by: str,
        reason: str
    ) -> bool:
        """Defer a conflict for later resolution."""
        self.db.execute("""
            UPDATE conflicts
            SET status = ?, resolution_notes = ?
            WHERE conflict_id = ?
        """, (
            ConflictStatus.DEFERRED.value,
            f"Deferred: {reason}",
            conflict_id
        ))

        self._log_action(
            conflict_id,
            'deferred',
            ConflictStatus.IN_REVIEW.value,
            ConflictStatus.DEFERRED.value,
            {'reason': reason},
            deferred_by
        )

        return True

    # ==================== Audit ====================

    def _log_action(
        self,
        conflict_id: str,
        action: str,
        old_status: Optional[str],
        new_status: str,
        details: Dict[str, Any],
        performed_by: str
    ) -> None:
        """Log conflict action for audit trail."""
        try:
            self.db.execute("""
                INSERT INTO conflict_audit (
                    conflict_id, action, old_status, new_status,
                    details, performed_by
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                conflict_id,
                action,
                old_status,
                new_status,
                json.dumps(details),
                performed_by
            ))
        except Exception as e:
            logger.warning(f"Failed to log conflict action: {e}")

    def get_audit_trail(self, conflict_id: str) -> List[Dict[str, Any]]:
        """Get audit trail for a conflict."""
        result = self.db.execute("""
            SELECT id, action, old_status, new_status,
                   details, performed_by, performed_at
            FROM conflict_audit
            WHERE conflict_id = ?
            ORDER BY performed_at ASC
        """, (conflict_id,))

        return [
            {
                'id': row[0] if isinstance(row, tuple) else row['id'],
                'action': row[1] if isinstance(row, tuple) else row['action'],
                'old_status': row[2] if isinstance(row, tuple) else row['old_status'],
                'new_status': row[3] if isinstance(row, tuple) else row['new_status'],
                'details': json.loads(row[4] if isinstance(row, tuple) else row['details'] or '{}'),
                'performed_by': row[5] if isinstance(row, tuple) else row['performed_by'],
                'performed_at': row[6] if isinstance(row, tuple) else row['performed_at']
            }
            for row in result
        ]

    # ==================== Utilities ====================

    def _row_to_conflict(self, row) -> Conflict:
        """Convert database row to Conflict object."""
        if hasattr(row, 'keys'):
            # Dict-like row
            return Conflict(
                conflict_id=row['conflict_id'],
                conflict_type=ConflictType(row['conflict_type']),
                priority=ConflictPriority(row['priority']),
                status=ConflictStatus(row['status']),
                source_entity_type=row['source_entity_type'],
                source_entity_id=row['source_entity_id'],
                source_data=json.loads(row['source_data'] or '{}'),
                target_entity_id=row['target_entity_id'],
                target_data=json.loads(row['target_data'] or '{}') if row['target_data'] else None,
                field_conflicts=[
                    FieldConflict(**fc)
                    for fc in json.loads(row['field_conflicts'] or '[]')
                ],
                match_score=row['match_score'] or 0.0,
                import_id=row['import_id'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.utcnow(),
                created_by=row['created_by'],
                assigned_to=row['assigned_to'],
                resolution=ResolutionAction(row['resolution']) if row['resolution'] else None,
                resolution_notes=row['resolution_notes'],
                resolved_at=datetime.fromisoformat(row['resolved_at']) if row['resolved_at'] else None,
                resolved_by=row['resolved_by']
            )
        else:
            # Tuple row
            return Conflict(
                conflict_id=row[0],
                conflict_type=ConflictType(row[1]),
                priority=ConflictPriority(row[2]),
                status=ConflictStatus(row[3]),
                source_entity_type=row[4],
                source_entity_id=row[5],
                source_data=json.loads(row[6] or '{}'),
                target_entity_id=row[7],
                target_data=json.loads(row[8] or '{}') if row[8] else None,
                field_conflicts=[
                    FieldConflict(**fc)
                    for fc in json.loads(row[9] or '[]')
                ],
                match_score=row[10] or 0.0,
                import_id=row[11],
                created_at=datetime.fromisoformat(row[12]) if row[12] else datetime.utcnow(),
                created_by=row[13],
                assigned_to=row[14],
                resolution=ResolutionAction(row[15]) if row[15] else None,
                resolution_notes=row[16],
                resolved_at=datetime.fromisoformat(row[17]) if row[17] else None,
                resolved_by=row[18]
            )

    def add_policy(self, policy: ResolutionPolicy) -> None:
        """Add a resolution policy."""
        self.policies.append(policy)
        self.policies.sort(key=lambda p: p.priority, reverse=True)

    def remove_policy(self, policy: ResolutionPolicy) -> bool:
        """Remove a resolution policy."""
        try:
            self.policies.remove(policy)
            return True
        except ValueError:
            return False
