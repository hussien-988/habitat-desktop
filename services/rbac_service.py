# -*- coding: utf-8 -*-
"""
Role-Based Access Control (RBAC) Service
=========================================
Implements FR-D-5 RBAC requirements and UC-009 User & Role Management.

Features:
- Granular permission management
- UI element visibility control
- Role hierarchy support
- Permission caching
- Audit trail for permission changes
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import json

from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class Permission(Enum):
    """System permissions as per FSD FR-D-5."""
    # Building permissions
    BUILDING_VIEW = "building:view"
    BUILDING_CREATE = "building:create"
    BUILDING_EDIT = "building:edit"
    BUILDING_DELETE = "building:delete"

    # Unit permissions
    UNIT_VIEW = "unit:view"
    UNIT_CREATE = "unit:create"
    UNIT_EDIT = "unit:edit"
    UNIT_DELETE = "unit:delete"

    # Person permissions
    PERSON_VIEW = "person:view"
    PERSON_CREATE = "person:create"
    PERSON_EDIT = "person:edit"
    PERSON_DELETE = "person:delete"

    # Claim permissions
    CLAIM_VIEW = "claim:view"
    CLAIM_CREATE = "claim:create"
    CLAIM_EDIT = "claim:edit"
    CLAIM_DELETE = "claim:delete"
    CLAIM_APPROVE = "claim:approve"
    CLAIM_REJECT = "claim:reject"
    CLAIM_ASSIGN = "claim:assign"

    # Document permissions
    DOCUMENT_VIEW = "document:view"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_VERIFY = "document:verify"

    # Import/Export permissions
    DATA_IMPORT = "data:import"
    DATA_EXPORT = "data:export"
    DATA_SYNC = "data:sync"

    # Report permissions
    REPORT_VIEW = "report:view"
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"

    # Admin permissions
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_VIEW = "audit:view"
    VOCABULARY_MANAGE = "vocabulary:manage"

    # Map permissions
    MAP_VIEW = "map:view"
    MAP_EDIT = "map:edit"

    # Duplicate resolution
    DUPLICATE_REVIEW = "duplicate:review"
    DUPLICATE_RESOLVE = "duplicate:resolve"


@dataclass
class Role:
    """Role definition with permissions."""
    role_id: str
    role_name: str
    role_name_ar: str
    description: str = ""
    description_ar: str = ""
    permissions: List[str] = field(default_factory=list)
    is_system_role: bool = False  # UC-009: System roles cannot be deleted
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def has_permission(self, permission: str) -> bool:
        """Check if role has a specific permission."""
        return permission in self.permissions or "all" in self.permissions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "role_name_ar": self.role_name_ar,
            "description": self.description,
            "description_ar": self.description_ar,
            "permissions": self.permissions,
            "is_system_role": self.is_system_role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RBACService:
    """
    Role-Based Access Control Service.

    Implements:
    - FR-D-5.1: Role-based access control
    - FR-D-5.2: UI element visibility based on permissions
    - UC-009: User & Role Management
    """

    # Default system roles as per FSD
    DEFAULT_ROLES = {
        "admin": Role(
            role_id="admin",
            role_name="Administrator",
            role_name_ar="مدير النظام",
            description="Full system access",
            description_ar="صلاحيات كاملة للنظام",
            permissions=["all"],
            is_system_role=True
        ),
        "data_manager": Role(
            role_id="data_manager",
            role_name="Data Manager",
            role_name_ar="مدير البيانات",
            description="Data import, export, and review",
            description_ar="استيراد وتصدير ومراجعة البيانات",
            permissions=[
                "building:view", "building:create", "building:edit",
                "unit:view", "unit:create", "unit:edit",
                "person:view", "person:create", "person:edit",
                "claim:view", "claim:create", "claim:edit", "claim:approve", "claim:reject", "claim:assign",
                "document:view", "document:upload", "document:verify",
                "data:import", "data:export", "data:sync",
                "report:view", "report:generate", "report:export",
                "map:view", "map:edit",
                "duplicate:review", "duplicate:resolve",
            ],
            is_system_role=True
        ),
        "office_clerk": Role(
            role_id="office_clerk",
            role_name="Office Clerk",
            role_name_ar="موظف المكتب",
            description="Data entry and document scanning",
            description_ar="إدخال البيانات ومسح الوثائق",
            permissions=[
                "building:view", "building:create", "building:edit",
                "unit:view", "unit:create", "unit:edit",
                "person:view", "person:create", "person:edit",
                "claim:view", "claim:create", "claim:edit",
                "document:view", "document:upload",
                "map:view",
            ],
            is_system_role=True
        ),
        "field_supervisor": Role(
            role_id="field_supervisor",
            role_name="Field Supervisor",
            role_name_ar="مشرف ميداني",
            description="Field data collection oversight",
            description_ar="الإشراف على جمع البيانات الميدانية",
            permissions=[
                "building:view",
                "unit:view",
                "person:view",
                "claim:view",
                "document:view",
                "data:export",
                "report:view", "report:generate",
                "map:view",
            ],
            is_system_role=True
        ),
        "analyst": Role(
            role_id="analyst",
            role_name="Analyst",
            role_name_ar="محلل",
            description="View and report generation",
            description_ar="عرض وإنشاء التقارير",
            permissions=[
                "building:view",
                "unit:view",
                "person:view",
                "claim:view",
                "document:view",
                "data:export",
                "report:view", "report:generate", "report:export",
                "map:view",
            ],
            is_system_role=True
        ),
    }

    # UI Elements to Permission mapping
    UI_PERMISSIONS = {
        # Navigation items
        "nav_buildings": ["building:view"],
        "nav_units": ["unit:view"],
        "nav_persons": ["person:view"],
        "nav_claims": ["claim:view"],
        "nav_documents": ["document:view"],
        "nav_map": ["map:view"],
        "nav_reports": ["report:view"],
        "nav_import": ["data:import"],
        "nav_admin": ["user:manage", "role:manage", "settings:manage"],
        "nav_duplicates": ["duplicate:review"],

        # Buttons
        "btn_create_building": ["building:create"],
        "btn_edit_building": ["building:edit"],
        "btn_delete_building": ["building:delete"],
        "btn_create_unit": ["unit:create"],
        "btn_edit_unit": ["unit:edit"],
        "btn_delete_unit": ["unit:delete"],
        "btn_create_person": ["person:create"],
        "btn_edit_person": ["person:edit"],
        "btn_delete_person": ["person:delete"],
        "btn_create_claim": ["claim:create"],
        "btn_edit_claim": ["claim:edit"],
        "btn_delete_claim": ["claim:delete"],
        "btn_approve_claim": ["claim:approve"],
        "btn_reject_claim": ["claim:reject"],
        "btn_assign_claim": ["claim:assign"],
        "btn_upload_document": ["document:upload"],
        "btn_delete_document": ["document:delete"],
        "btn_verify_document": ["document:verify"],
        "btn_import_data": ["data:import"],
        "btn_export_data": ["data:export"],
        "btn_sync_data": ["data:sync"],
        "btn_generate_report": ["report:generate"],
        "btn_export_report": ["report:export"],
        "btn_manage_users": ["user:manage"],
        "btn_manage_roles": ["role:manage"],
        "btn_manage_settings": ["settings:manage"],
        "btn_view_audit": ["audit:view"],
        "btn_manage_vocabulary": ["vocabulary:manage"],
        "btn_edit_map": ["map:edit"],
        "btn_resolve_duplicate": ["duplicate:resolve"],
    }

    def __init__(self, db: Database):
        self.db = db
        self._role_cache: Dict[str, Role] = {}
        self._user_permissions_cache: Dict[str, Set[str]] = {}
        self._ensure_tables()
        self._initialize_default_roles()

    def _ensure_tables(self):
        """Create RBAC tables if they don't exist."""
        cursor = self.db.cursor()

        # Roles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                role_id TEXT PRIMARY KEY,
                role_name TEXT NOT NULL,
                role_name_ar TEXT,
                description TEXT,
                description_ar TEXT,
                permissions TEXT,
                is_system_role INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # User-Role assignments (for multiple roles per user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                assigned_at TEXT,
                assigned_by TEXT,
                PRIMARY KEY (user_id, role_id)
            )
        """)

        # Permission change log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_audit_log (
                log_id TEXT PRIMARY KEY,
                timestamp TEXT,
                user_id TEXT,
                action TEXT,
                target_type TEXT,
                target_id TEXT,
                old_value TEXT,
                new_value TEXT,
                details TEXT
            )
        """)

        self.db.connection.commit()

    def _initialize_default_roles(self):
        """Initialize default system roles."""
        cursor = self.db.cursor()

        for role_id, role in self.DEFAULT_ROLES.items():
            cursor.execute("SELECT role_id FROM roles WHERE role_id = ?", (role_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO roles (
                        role_id, role_name, role_name_ar, description, description_ar,
                        permissions, is_system_role, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    role.role_id, role.role_name, role.role_name_ar,
                    role.description, role.description_ar,
                    json.dumps(role.permissions),
                    1 if role.is_system_role else 0,
                    1 if role.is_active else 0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

        self.db.connection.commit()
        logger.info("Default RBAC roles initialized")

    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role by ID."""
        if role_id in self._role_cache:
            return self._role_cache[role_id]

        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM roles WHERE role_id = ?", (role_id,))
        row = cursor.fetchone()

        if row:
            role = self._row_to_role(row)
            self._role_cache[role_id] = role
            return role
        return None

    def get_all_roles(self) -> List[Role]:
        """Get all roles."""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM roles WHERE is_active = 1 ORDER BY role_name")
        return [self._row_to_role(row) for row in cursor.fetchall()]

    def _row_to_role(self, row) -> Role:
        """Convert database row to Role object."""
        data = dict(row)
        permissions = json.loads(data.get("permissions", "[]"))
        return Role(
            role_id=data["role_id"],
            role_name=data["role_name"],
            role_name_ar=data.get("role_name_ar", ""),
            description=data.get("description", ""),
            description_ar=data.get("description_ar", ""),
            permissions=permissions,
            is_system_role=bool(data.get("is_system_role", 0)),
            is_active=bool(data.get("is_active", 1)),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    def create_role(self, role: Role, created_by: str = None) -> bool:
        """Create a new role."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO roles (
                    role_id, role_name, role_name_ar, description, description_ar,
                    permissions, is_system_role, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                role.role_id, role.role_name, role.role_name_ar,
                role.description, role.description_ar,
                json.dumps(role.permissions),
                1 if role.is_system_role else 0,
                1 if role.is_active else 0,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            self.db.connection.commit()

            # Log action
            self._log_action("role_created", "role", role.role_id, None, role.to_dict(), created_by)

            # Clear cache
            self._role_cache.pop(role.role_id, None)

            logger.info(f"Role created: {role.role_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create role: {e}")
            return False

    def update_role(self, role: Role, updated_by: str = None) -> bool:
        """Update an existing role."""
        try:
            old_role = self.get_role(role.role_id)
            if old_role and old_role.is_system_role and role.role_id != "admin":
                # System roles can only have permissions modified, not deleted
                pass

            cursor = self.db.cursor()
            cursor.execute("""
                UPDATE roles SET
                    role_name = ?, role_name_ar = ?, description = ?, description_ar = ?,
                    permissions = ?, is_active = ?, updated_at = ?
                WHERE role_id = ?
            """, (
                role.role_name, role.role_name_ar, role.description, role.description_ar,
                json.dumps(role.permissions), 1 if role.is_active else 0,
                datetime.now().isoformat(), role.role_id
            ))
            self.db.connection.commit()

            # Log action
            old_value = old_role.to_dict() if old_role else None
            self._log_action("role_updated", "role", role.role_id, old_value, role.to_dict(), updated_by)

            # Clear cache
            self._role_cache.pop(role.role_id, None)
            self._user_permissions_cache.clear()

            logger.info(f"Role updated: {role.role_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update role: {e}")
            return False

    def delete_role(self, role_id: str, deleted_by: str = None) -> tuple:
        """
        Delete a role (only non-system roles).

        Returns:
            Tuple of (success, error_message)
        """
        role = self.get_role(role_id)
        if not role:
            return False, "Role not found"

        if role.is_system_role:
            return False, "Cannot delete system roles"

        try:
            cursor = self.db.cursor()

            # Check if any users have this role
            cursor.execute("SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (role_id,))
            user_count = cursor.fetchone()[0]
            if user_count > 0:
                return False, f"Role is assigned to {user_count} users"

            cursor.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))
            self.db.connection.commit()

            # Log action
            self._log_action("role_deleted", "role", role_id, role.to_dict(), None, deleted_by)

            # Clear cache
            self._role_cache.pop(role_id, None)

            logger.info(f"Role deleted: {role_id}")
            return True, ""
        except Exception as e:
            logger.error(f"Failed to delete role: {e}")
            return False, str(e)

    # ==================== User Permission Methods ====================

    def get_user_permissions(self, user_role: str) -> Set[str]:
        """Get all permissions for a user's role."""
        if user_role in self._user_permissions_cache:
            return self._user_permissions_cache[user_role]

        role = self.get_role(user_role)
        if not role:
            return set()

        permissions = set(role.permissions)
        self._user_permissions_cache[user_role] = permissions
        return permissions

    def has_permission(self, user_role: str, permission: str) -> bool:
        """Check if user role has a specific permission."""
        permissions = self.get_user_permissions(user_role)
        return "all" in permissions or permission in permissions

    def has_any_permission(self, user_role: str, permissions: List[str]) -> bool:
        """Check if user role has any of the specified permissions."""
        user_perms = self.get_user_permissions(user_role)
        if "all" in user_perms:
            return True
        return bool(user_perms.intersection(set(permissions)))

    def has_all_permissions(self, user_role: str, permissions: List[str]) -> bool:
        """Check if user role has all specified permissions."""
        user_perms = self.get_user_permissions(user_role)
        if "all" in user_perms:
            return True
        return set(permissions).issubset(user_perms)

    # ==================== UI Visibility Methods (FR-D-5.2) ====================

    def is_ui_element_visible(self, user_role: str, element_id: str) -> bool:
        """
        Check if a UI element should be visible for the user's role.
        Implements FR-D-5.2 UI element visibility based on permissions.
        """
        required_permissions = self.UI_PERMISSIONS.get(element_id, [])
        if not required_permissions:
            return True  # No restrictions

        return self.has_any_permission(user_role, required_permissions)

    def get_visible_elements(self, user_role: str) -> List[str]:
        """Get list of visible UI elements for a role."""
        visible = []
        for element_id in self.UI_PERMISSIONS.keys():
            if self.is_ui_element_visible(user_role, element_id):
                visible.append(element_id)
        return visible

    def get_hidden_elements(self, user_role: str) -> List[str]:
        """Get list of hidden UI elements for a role."""
        hidden = []
        for element_id in self.UI_PERMISSIONS.keys():
            if not self.is_ui_element_visible(user_role, element_id):
                hidden.append(element_id)
        return hidden

    # ==================== Audit Logging ====================

    def _log_action(
        self,
        action: str,
        target_type: str,
        target_id: str,
        old_value: Any,
        new_value: Any,
        user_id: str = None
    ):
        """Log RBAC action to audit trail."""
        import uuid
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO rbac_audit_log (
                log_id, timestamp, user_id, action, target_type, target_id,
                old_value, new_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            datetime.now().isoformat(),
            user_id,
            action,
            target_type,
            target_id,
            json.dumps(old_value, ensure_ascii=False) if old_value else None,
            json.dumps(new_value, ensure_ascii=False) if new_value else None
        ))
        self.db.connection.commit()

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get RBAC audit log entries."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM rbac_audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        logs = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("old_value"):
                try:
                    data["old_value"] = json.loads(data["old_value"])
                except:
                    pass
            if data.get("new_value"):
                try:
                    data["new_value"] = json.loads(data["new_value"])
                except:
                    pass
            logs.append(data)
        return logs

    def clear_cache(self):
        """Clear permission cache."""
        self._role_cache.clear()
        self._user_permissions_cache.clear()
