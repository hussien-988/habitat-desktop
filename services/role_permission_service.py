"""
Role and Permission Management Service
=======================================
Implements comprehensive user, role, and permission management as per UC-009a specifications.

Features:
- User management (create, edit, activate/deactivate, lock/unlock)
- Role-based access control (RBAC)
- Granular per-module and per-action permissions
- Segregation of duties enforcement
- Password policy management
- Account status tracking (active, locked, disabled)
- Audit trail for all administrative actions
- System roles protection (cannot be deleted)
"""

import json
import hashlib
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Set, Tuple
import logging
import re

from repositories.db_adapter import DatabaseFactory, DatabaseAdapter, RowProxy, DatabaseType

logger = logging.getLogger(__name__)


class AccountStatus(Enum):
    """User account status."""
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"
    PENDING = "pending"  # Awaiting first login/activation


class PermissionScope(Enum):
    """Scope of a permission."""
    GLOBAL = "global"  # System-wide permission
    MODULE = "module"  # Module-specific permission
    ENTITY = "entity"  # Entity-level permission (e.g., specific building)


class PermissionAction(Enum):
    """Standard permission actions."""
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"
    EXPORT = "export"
    IMPORT = "import"
    ADMIN = "admin"


@dataclass
class Permission:
    """Represents a single permission."""
    permission_id: str
    name: str
    name_ar: str = ""
    description: str = ""
    module: str = ""  # e.g., "buildings", "claims", "admin"
    action: str = ""  # e.g., "view", "edit", "delete"
    scope: PermissionScope = PermissionScope.MODULE
    is_system: bool = False  # System permissions cannot be modified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "name": self.name,
            "name_ar": self.name_ar,
            "description": self.description,
            "module": self.module,
            "action": self.action,
            "scope": self.scope.value,
            "is_system": self.is_system
        }


@dataclass
class Role:
    """Represents a user role."""
    role_id: str
    role_name: str
    role_name_ar: str = ""
    description: str = ""
    description_ar: str = ""
    permissions: List[str] = field(default_factory=list)  # List of permission_ids
    is_system_role: bool = False  # System roles cannot be deleted
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    modified_at: Optional[datetime] = None
    modified_by: str = ""

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
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "modified_by": self.modified_by
        }


@dataclass
class PasswordPolicy:
    """Password policy configuration."""
    min_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special: bool = True
    special_characters: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    max_age_days: int = 90  # Password expiry in days
    history_count: int = 5  # Number of previous passwords to check
    lockout_threshold: int = 5  # Failed attempts before lockout
    lockout_duration_minutes: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class User:
    """Represents a system user."""
    user_id: str
    username: str
    full_name: str
    full_name_ar: str = ""
    email: str = ""
    phone: str = ""
    default_language: str = "en"  # en, ar
    roles: List[str] = field(default_factory=list)  # List of role_ids
    direct_permissions: List[str] = field(default_factory=list)  # Additional permissions
    status: AccountStatus = AccountStatus.ACTIVE
    password_hash: str = ""
    password_salt: str = ""
    password_changed_at: Optional[datetime] = None
    password_history: List[str] = field(default_factory=list)
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    modified_at: Optional[datetime] = None
    modified_by: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        result = {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "full_name_ar": self.full_name_ar,
            "email": self.email,
            "phone": self.phone,
            "default_language": self.default_language,
            "roles": self.roles,
            "direct_permissions": self.direct_permissions,
            "status": self.status.value,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "modified_by": self.modified_by
        }
        if include_sensitive:
            result["password_changed_at"] = self.password_changed_at.isoformat() if self.password_changed_at else None
            result["failed_login_attempts"] = self.failed_login_attempts
            result["locked_until"] = self.locked_until.isoformat() if self.locked_until else None
        return result


@dataclass
class AdminAuditLog:
    """Audit log entry for administrative actions."""
    id: int = 0
    action_type: str = ""  # user_created, role_modified, permission_changed, etc.
    target_type: str = ""  # user, role, permission
    target_id: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)  # before/after values
    performed_by: str = ""
    performed_at: datetime = field(default_factory=datetime.utcnow)
    ip_address: str = ""


class RolePermissionService:
    """
    Comprehensive role and permission management service.

    Implements UC-009a requirements:
    - User management with full CRUD operations
    - Role-based access control
    - Granular permissions per module/action
    - Password policy enforcement
    - Account lockout and status management
    - Segregation of duties
    - Complete audit trail
    """

    # Standard modules in the system
    SYSTEM_MODULES = [
        "buildings",
        "claims",
        "persons",
        "documents",
        "duplicates",
        "import",
        "export",
        "reports",
        "field_assignments",
        "dashboard",
        "admin",
        "vocabularies",
        "system"
    ]

    # Standard actions per module
    STANDARD_ACTIONS = ["view", "create", "edit", "delete", "approve", "export", "import"]

    # Default system roles
    DEFAULT_ROLES = {
        "system_admin": {
            "name": "System Administrator",
            "name_ar": "مدير النظام",
            "description": "Full system access including user and configuration management",
            "permissions": ["*"]  # All permissions
        },
        "data_manager": {
            "name": "Data Manager",
            "name_ar": "مدير البيانات",
            "description": "Manage buildings, claims, and data quality",
            "permissions": [
                "buildings.*", "claims.*", "persons.*", "documents.*",
                "duplicates.*", "import.*", "export.*", "reports.view"
            ]
        },
        "field_supervisor": {
            "name": "Field Supervisor",
            "name_ar": "مشرف ميداني",
            "description": "Manage field assignments and review submissions",
            "permissions": [
                "buildings.view", "claims.view", "field_assignments.*",
                "reports.view", "dashboard.view"
            ]
        },
        "viewer": {
            "name": "View Only",
            "name_ar": "مشاهدة فقط",
            "description": "Read-only access to system data",
            "permissions": [
                "buildings.view", "claims.view", "reports.view", "dashboard.view"
            ]
        },
        "auditor": {
            "name": "Auditor",
            "name_ar": "مدقق",
            "description": "View data and audit logs for compliance",
            "permissions": [
                "buildings.view", "claims.view", "reports.view",
                "dashboard.view", "admin.audit_view"
            ]
        }
    }

    def __init__(self, db_path: str = None):
        """Initialize role and permission service."""
        self.db_path = db_path
        self._adapter: DatabaseAdapter = DatabaseFactory.create()
        self.password_policy = PasswordPolicy()
        self._ensure_tables()
        self._initialize_system_data()

    def _ensure_tables(self):
        """Ensure user/role/permission tables exist."""
        is_postgres = self._adapter.db_type == DatabaseType.POSTGRESQL

        with self._adapter.cursor() as cursor:
            # Permissions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    permission_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    name_ar TEXT,
                    description TEXT,
                    module TEXT,
                    action TEXT,
                    scope TEXT DEFAULT 'module',
                    is_system INTEGER DEFAULT 0
                )
            """)

            # Roles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    role_id TEXT PRIMARY KEY,
                    role_name TEXT NOT NULL UNIQUE,
                    role_name_ar TEXT,
                    description TEXT,
                    description_ar TEXT,
                    is_system_role INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    modified_at TIMESTAMP,
                    modified_by TEXT
                )
            """)

            # Role permissions mapping
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id TEXT NOT NULL,
                    permission_id TEXT NOT NULL,
                    PRIMARY KEY (role_id, permission_id),
                    FOREIGN KEY (role_id) REFERENCES roles(role_id),
                    FOREIGN KEY (permission_id) REFERENCES permissions(permission_id)
                )
            """)

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    full_name_ar TEXT,
                    email TEXT,
                    phone TEXT,
                    default_language TEXT DEFAULT 'en',
                    status TEXT DEFAULT 'active',
                    password_hash TEXT,
                    password_salt TEXT,
                    password_changed_at TIMESTAMP,
                    password_history TEXT,
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    modified_at TIMESTAMP,
                    modified_by TEXT,
                    metadata TEXT
                )
            """)

            # User roles mapping
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_by TEXT,
                    PRIMARY KEY (user_id, role_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (role_id) REFERENCES roles(role_id)
                )
            """)

            # User direct permissions (beyond roles)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    user_id TEXT NOT NULL,
                    permission_id TEXT NOT NULL,
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    granted_by TEXT,
                    PRIMARY KEY (user_id, permission_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (permission_id) REFERENCES permissions(permission_id)
                )
            """)

            # Segregation of duties rules (backend-specific auto-increment)
            if is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sod_rules (
                        id SERIAL PRIMARY KEY,
                        rule_name TEXT NOT NULL,
                        description TEXT,
                        role1_id TEXT NOT NULL,
                        role2_id TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        UNIQUE(role1_id, role2_id)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sod_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_name TEXT NOT NULL,
                        description TEXT,
                        role1_id TEXT NOT NULL,
                        role2_id TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        UNIQUE(role1_id, role2_id)
                    )
                """)

            # Admin audit log (backend-specific auto-increment)
            if is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admin_audit_log (
                        id SERIAL PRIMARY KEY,
                        action_type TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        changes TEXT,
                        performed_by TEXT NOT NULL,
                        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ip_address TEXT
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admin_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action_type TEXT NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        changes TEXT,
                        performed_by TEXT NOT NULL,
                        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ip_address TEXT
                    )
                """)

            # Password policy table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_policy (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    min_length INTEGER DEFAULT 8,
                    require_uppercase INTEGER DEFAULT 1,
                    require_lowercase INTEGER DEFAULT 1,
                    require_digits INTEGER DEFAULT 1,
                    require_special INTEGER DEFAULT 1,
                    special_characters TEXT,
                    max_age_days INTEGER DEFAULT 90,
                    history_count INTEGER DEFAULT 5,
                    lockout_threshold INTEGER DEFAULT 5,
                    lockout_duration_minutes INTEGER DEFAULT 30
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_performed ON admin_audit_log(performed_at)")

        logger.info("Role and permission tables initialized")

    def _initialize_system_data(self):
        """Initialize system permissions and default roles."""
        with self._adapter.cursor() as cursor:
            # Check if already initialized
            cursor.execute("SELECT COUNT(*) FROM permissions")
            if cursor.fetchone()[0] > 0:
                return

            # Create system permissions
            for module in self.SYSTEM_MODULES:
                for action in self.STANDARD_ACTIONS:
                    perm_id = f"{module}.{action}"
                    cursor.execute("""
                        INSERT OR IGNORE INTO permissions
                        (permission_id, name, module, action, is_system)
                        VALUES (?, ?, ?, ?, 1)
                    """, (perm_id, f"{action.title()} {module}", module, action))

            # Add wildcard permission for each module
            for module in self.SYSTEM_MODULES:
                cursor.execute("""
                    INSERT OR IGNORE INTO permissions
                    (permission_id, name, module, action, is_system)
                    VALUES (?, ?, ?, ?, 1)
                """, (f"{module}.*", f"All {module} permissions", module, "*"))

            # Add global admin permission
            cursor.execute("""
                INSERT OR IGNORE INTO permissions
                (permission_id, name, module, action, scope, is_system)
                VALUES ('*', 'Super Admin - All Permissions', '*', '*', 'global', 1)
            """)

            # Create default roles
            for role_id, role_data in self.DEFAULT_ROLES.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO roles
                    (role_id, role_name, role_name_ar, description, is_system_role, created_by)
                    VALUES (?, ?, ?, ?, 1, 'system')
                """, (
                    role_id,
                    role_data["name"],
                    role_data["name_ar"],
                    role_data["description"]
                ))

                # Assign permissions to role
                for perm_pattern in role_data["permissions"]:
                    if perm_pattern == "*":
                        cursor.execute("""
                            INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                            VALUES (?, '*')
                        """, (role_id,))
                    else:
                        cursor.execute("""
                            INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                            VALUES (?, ?)
                        """, (role_id, perm_pattern))

            # Initialize password policy
            cursor.execute("""
                INSERT OR IGNORE INTO password_policy (id) VALUES (1)
            """)

            logger.info("System permissions and roles initialized")

    # ==================== User Management ====================

    def create_user(
        self,
        username: str,
        full_name: str,
        password: str,
        roles: List[str],
        created_by: str,
        email: str = "",
        phone: str = "",
        full_name_ar: str = "",
        default_language: str = "en",
        direct_permissions: List[str] = None
    ) -> User:
        """Create a new user."""
        # Validate username uniqueness
        if self.get_user_by_username(username):
            raise ValueError(f"Username '{username}' already exists")

        # Validate password
        is_valid, errors = self.validate_password(password)
        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        # Validate roles exist
        for role_id in roles:
            if not self.get_role(role_id):
                raise ValueError(f"Role not found: {role_id}")

        # Check segregation of duties
        sod_violations = self.check_sod_violations(roles)
        if sod_violations:
            raise ValueError(f"Segregation of duties violations: {sod_violations}")

        # Generate user ID and password hash
        user_id = secrets.token_hex(16)
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)

        user = User(
            user_id=user_id,
            username=username,
            full_name=full_name,
            full_name_ar=full_name_ar,
            email=email,
            phone=phone,
            default_language=default_language,
            roles=roles,
            direct_permissions=direct_permissions or [],
            status=AccountStatus.ACTIVE,
            password_hash=password_hash,
            password_salt=salt,
            password_changed_at=datetime.utcnow(),
            created_by=created_by
        )

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (
                    user_id, username, full_name, full_name_ar, email, phone,
                    default_language, status, password_hash, password_salt,
                    password_changed_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, username, full_name, full_name_ar, email, phone,
                default_language, AccountStatus.ACTIVE.value, password_hash, salt,
                datetime.utcnow().isoformat(), created_by
            ))

            # Assign roles
            for role_id in roles:
                cursor.execute("""
                    INSERT INTO user_roles (user_id, role_id, assigned_by)
                    VALUES (?, ?, ?)
                """, (user_id, role_id, created_by))

            # Assign direct permissions
            for perm_id in (direct_permissions or []):
                cursor.execute("""
                    INSERT INTO user_permissions (user_id, permission_id, granted_by)
                    VALUES (?, ?, ?)
                """, (user_id, perm_id, created_by))

            # Log the action
            self._log_admin_action(
                cursor, "user_created", "user", user_id,
                {"username": username, "roles": roles},
                created_by
            )

            logger.info(f"Created user: {username}")

            return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with self._adapter.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None

            return self._row_to_user(cursor, row)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        with self._adapter.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if not row:
                return None

            return self._row_to_user(cursor, row)

    def _row_to_user(self, cursor: Any, row: Any) -> User:
        """Convert database row to User object."""
        # Get roles
        cursor.execute("""
            SELECT role_id FROM user_roles WHERE user_id = ?
        """, (row["user_id"],))
        roles = [r["role_id"] for r in cursor.fetchall()]

        # Get direct permissions
        cursor.execute("""
            SELECT permission_id FROM user_permissions WHERE user_id = ?
        """, (row["user_id"],))
        permissions = [p["permission_id"] for p in cursor.fetchall()]

        return User(
            user_id=row["user_id"],
            username=row["username"],
            full_name=row["full_name"],
            full_name_ar=row["full_name_ar"] or "",
            email=row["email"] or "",
            phone=row["phone"] or "",
            default_language=row["default_language"] or "en",
            roles=roles,
            direct_permissions=permissions,
            status=AccountStatus(row["status"]) if row["status"] else AccountStatus.ACTIVE,
            password_hash=row["password_hash"] or "",
            password_salt=row["password_salt"] or "",
            password_changed_at=datetime.fromisoformat(row["password_changed_at"]) if row["password_changed_at"] else None,
            password_history=json.loads(row["password_history"]) if row["password_history"] else [],
            failed_login_attempts=row["failed_login_attempts"] or 0,
            locked_until=datetime.fromisoformat(row["locked_until"]) if row["locked_until"] else None,
            last_login=datetime.fromisoformat(row["last_login"]) if row["last_login"] else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            created_by=row["created_by"] or "",
            modified_at=datetime.fromisoformat(row["modified_at"]) if row["modified_at"] else None,
            modified_by=row["modified_by"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )

    def list_users(
        self,
        status: Optional[AccountStatus] = None,
        role_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[User]:
        """List users with optional filters."""
        with self._adapter.cursor() as cursor:
            query = "SELECT DISTINCT u.* FROM users u"
            params = []
            conditions = []

            if role_id:
                query += " JOIN user_roles ur ON u.user_id = ur.user_id"
                conditions.append("ur.role_id = ?")
                params.append(role_id)

            if status:
                conditions.append("u.status = ?")
                params.append(status.value)

            if search:
                conditions.append("(u.username LIKE ? OR u.full_name LIKE ? OR u.email LIKE ?)")
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern, search_pattern])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY u.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)

            users = []
            for row in cursor.fetchall():
                users.append(self._row_to_user(cursor, row))

            return users

    def update_user(
        self,
        user_id: str,
        modified_by: str,
        full_name: Optional[str] = None,
        full_name_ar: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        default_language: Optional[str] = None,
        roles: Optional[List[str]] = None,
        direct_permissions: Optional[List[str]] = None,
        status: Optional[AccountStatus] = None
    ) -> User:
        """Update user details."""
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Check SOD if roles are being changed
        if roles is not None:
            sod_violations = self.check_sod_violations(roles)
            if sod_violations:
                raise ValueError(f"Segregation of duties violations: {sod_violations}")

        with self._adapter.cursor() as cursor:
            # Build update query
            updates = []
            params = []
            changes = {}

            if full_name is not None:
                updates.append("full_name = ?")
                params.append(full_name)
                changes["full_name"] = {"old": user.full_name, "new": full_name}

            if full_name_ar is not None:
                updates.append("full_name_ar = ?")
                params.append(full_name_ar)
                changes["full_name_ar"] = {"old": user.full_name_ar, "new": full_name_ar}

            if email is not None:
                updates.append("email = ?")
                params.append(email)
                changes["email"] = {"old": user.email, "new": email}

            if phone is not None:
                updates.append("phone = ?")
                params.append(phone)
                changes["phone"] = {"old": user.phone, "new": phone}

            if default_language is not None:
                updates.append("default_language = ?")
                params.append(default_language)
                changes["default_language"] = {"old": user.default_language, "new": default_language}

            if status is not None:
                updates.append("status = ?")
                params.append(status.value)
                changes["status"] = {"old": user.status.value, "new": status.value}

            updates.append("modified_at = ?")
            params.append(datetime.utcnow().isoformat())
            updates.append("modified_by = ?")
            params.append(modified_by)

            params.append(user_id)

            if updates:
                cursor.execute(f"""
                    UPDATE users SET {", ".join(updates)} WHERE user_id = ?
                """, params)

            # Update roles if specified
            if roles is not None:
                changes["roles"] = {"old": user.roles, "new": roles}

                cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
                for role_id in roles:
                    cursor.execute("""
                        INSERT INTO user_roles (user_id, role_id, assigned_by)
                        VALUES (?, ?, ?)
                    """, (user_id, role_id, modified_by))

            # Update direct permissions if specified
            if direct_permissions is not None:
                changes["direct_permissions"] = {"old": user.direct_permissions, "new": direct_permissions}

                cursor.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
                for perm_id in direct_permissions:
                    cursor.execute("""
                        INSERT INTO user_permissions (user_id, permission_id, granted_by)
                        VALUES (?, ?, ?)
                    """, (user_id, perm_id, modified_by))

            # Log the action
            self._log_admin_action(
                cursor, "user_modified", "user", user_id, changes, modified_by
            )

            logger.info(f"Updated user: {user.username}")

            return self.get_user(user_id)

    def change_user_password(
        self,
        user_id: str,
        new_password: str,
        changed_by: str,
        require_old_password: bool = False,
        old_password: Optional[str] = None
    ) -> bool:
        """Change user password."""
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Validate old password if required
        if require_old_password:
            if not old_password or not self._verify_password(old_password, user.password_hash, user.password_salt):
                raise ValueError("Current password is incorrect")

        # Validate new password
        is_valid, errors = self.validate_password(new_password)
        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        # Check password history
        new_hash = self._hash_password(new_password, user.password_salt)
        if new_hash in user.password_history:
            raise ValueError("Password was used recently. Please choose a different password.")

        with self._adapter.cursor() as cursor:
            # Generate new salt and hash
            new_salt = secrets.token_hex(16)
            new_hash = self._hash_password(new_password, new_salt)

            # Update password history
            history = user.password_history[-self.password_policy.history_count:]
            history.append(user.password_hash)

            cursor.execute("""
                UPDATE users
                SET password_hash = ?, password_salt = ?,
                    password_changed_at = ?, password_history = ?,
                    modified_at = ?, modified_by = ?
                WHERE user_id = ?
            """, (
                new_hash, new_salt,
                datetime.utcnow().isoformat(),
                json.dumps(history),
                datetime.utcnow().isoformat(),
                changed_by,
                user_id
            ))

            # Log the action
            self._log_admin_action(
                cursor, "password_changed", "user", user_id,
                {"changed_by": changed_by},
                changed_by
            )

            logger.info(f"Password changed for user: {user.username}")

            return True

    def lock_user(self, user_id: str, locked_by: str, reason: str = "") -> bool:
        """Lock a user account."""
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE users
                SET status = 'locked', modified_at = ?, modified_by = ?
                WHERE user_id = ?
            """, (datetime.utcnow().isoformat(), locked_by, user_id))

            self._log_admin_action(
                cursor, "user_locked", "user", user_id,
                {"reason": reason},
                locked_by
            )

            return True

    def unlock_user(self, user_id: str, unlocked_by: str) -> bool:
        """Unlock a user account."""
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE users
                SET status = 'active', failed_login_attempts = 0,
                    locked_until = NULL, modified_at = ?, modified_by = ?
                WHERE user_id = ?
            """, (datetime.utcnow().isoformat(), unlocked_by, user_id))

            self._log_admin_action(
                cursor, "user_unlocked", "user", user_id,
                {},
                unlocked_by
            )

            return True

    # ==================== Role Management ====================

    def create_role(
        self,
        role_name: str,
        permissions: List[str],
        created_by: str,
        role_name_ar: str = "",
        description: str = "",
        description_ar: str = ""
    ) -> Role:
        """Create a new role."""
        role_id = role_name.lower().replace(" ", "_")

        # Check if role exists
        if self.get_role(role_id):
            raise ValueError(f"Role already exists: {role_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                INSERT INTO roles (
                    role_id, role_name, role_name_ar, description, description_ar,
                    is_system_role, created_by
                ) VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (role_id, role_name, role_name_ar, description, description_ar, created_by))

            # Assign permissions
            for perm_id in permissions:
                cursor.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                """, (role_id, perm_id))

            self._log_admin_action(
                cursor, "role_created", "role", role_id,
                {"role_name": role_name, "permissions": permissions},
                created_by
            )

            logger.info(f"Created role: {role_name}")

            return self.get_role(role_id)

    def get_role(self, role_id: str) -> Optional[Role]:
        """Get role by ID."""
        with self._adapter.cursor() as cursor:
            cursor.execute("SELECT * FROM roles WHERE role_id = ?", (role_id,))
            row = cursor.fetchone()
            if not row:
                return None

            # Get permissions
            cursor.execute("""
                SELECT permission_id FROM role_permissions WHERE role_id = ?
            """, (role_id,))
            permissions = [p["permission_id"] for p in cursor.fetchall()]

            return Role(
                role_id=row["role_id"],
                role_name=row["role_name"],
                role_name_ar=row["role_name_ar"] or "",
                description=row["description"] or "",
                description_ar=row["description_ar"] or "",
                permissions=permissions,
                is_system_role=bool(row["is_system_role"]),
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                created_by=row["created_by"] or "",
                modified_at=datetime.fromisoformat(row["modified_at"]) if row["modified_at"] else None,
                modified_by=row["modified_by"] or ""
            )

    def list_roles(self, include_inactive: bool = False) -> List[Role]:
        """List all roles."""
        with self._adapter.cursor() as cursor:
            if include_inactive:
                cursor.execute("SELECT * FROM roles ORDER BY role_name")
            else:
                cursor.execute("SELECT * FROM roles WHERE is_active = 1 ORDER BY role_name")

            roles = []
            for row in cursor.fetchall():
                cursor.execute("""
                    SELECT permission_id FROM role_permissions WHERE role_id = ?
                """, (row["role_id"],))
                permissions = [p["permission_id"] for p in cursor.fetchall()]

                roles.append(Role(
                    role_id=row["role_id"],
                    role_name=row["role_name"],
                    role_name_ar=row["role_name_ar"] or "",
                    description=row["description"] or "",
                    description_ar=row["description_ar"] or "",
                    permissions=permissions,
                    is_system_role=bool(row["is_system_role"]),
                    is_active=bool(row["is_active"]),
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                    created_by=row["created_by"] or ""
                ))

            return roles

    def update_role(
        self,
        role_id: str,
        modified_by: str,
        role_name: Optional[str] = None,
        role_name_ar: Optional[str] = None,
        description: Optional[str] = None,
        description_ar: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        is_active: Optional[bool] = None
    ) -> Role:
        """Update a role."""
        role = self.get_role(role_id)
        if not role:
            raise ValueError(f"Role not found: {role_id}")

        with self._adapter.cursor() as cursor:
            updates = []
            params = []
            changes = {}

            if role_name is not None:
                updates.append("role_name = ?")
                params.append(role_name)
                changes["role_name"] = {"old": role.role_name, "new": role_name}

            if role_name_ar is not None:
                updates.append("role_name_ar = ?")
                params.append(role_name_ar)

            if description is not None:
                updates.append("description = ?")
                params.append(description)

            if description_ar is not None:
                updates.append("description_ar = ?")
                params.append(description_ar)

            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
                changes["is_active"] = {"old": role.is_active, "new": is_active}

            updates.append("modified_at = ?")
            params.append(datetime.utcnow().isoformat())
            updates.append("modified_by = ?")
            params.append(modified_by)

            params.append(role_id)

            cursor.execute(f"""
                UPDATE roles SET {", ".join(updates)} WHERE role_id = ?
            """, params)

            # Update permissions if specified
            if permissions is not None:
                changes["permissions"] = {"old": role.permissions, "new": permissions}

                cursor.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
                for perm_id in permissions:
                    cursor.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (?, ?)
                    """, (role_id, perm_id))

            self._log_admin_action(
                cursor, "role_modified", "role", role_id, changes, modified_by
            )

            return self.get_role(role_id)

    def delete_role(self, role_id: str, deleted_by: str) -> bool:
        """Delete a role (if not system role and not assigned to users)."""
        role = self.get_role(role_id)
        if not role:
            raise ValueError(f"Role not found: {role_id}")

        if role.is_system_role:
            raise ValueError("Cannot delete system role")

        with self._adapter.cursor() as cursor:
            # Check if role is assigned to users
            cursor.execute("""
                SELECT COUNT(*) FROM user_roles WHERE role_id = ?
            """, (role_id,))

            if cursor.fetchone()[0] > 0:
                raise ValueError("Cannot delete role that is assigned to users. Reassign users first.")

            cursor.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
            cursor.execute("DELETE FROM roles WHERE role_id = ?", (role_id,))

            self._log_admin_action(
                cursor, "role_deleted", "role", role_id,
                {"role_name": role.role_name},
                deleted_by
            )

            return True

    def get_users_with_role(self, role_id: str) -> List[User]:
        """Get all users with a specific role."""
        return self.list_users(role_id=role_id)

    # ==================== Permission Checking ====================

    def get_user_effective_permissions(self, user_id: str) -> Set[str]:
        """Get all effective permissions for a user (from roles + direct)."""
        user = self.get_user(user_id)
        if not user:
            return set()

        permissions = set(user.direct_permissions)

        # Add permissions from roles
        for role_id in user.roles:
            role = self.get_role(role_id)
            if role and role.is_active:
                permissions.update(role.permissions)

        # Expand wildcard permissions
        expanded = set()
        for perm in permissions:
            if perm == "*":
                # Add all permissions
                rows = self._adapter.fetch_all("SELECT permission_id FROM permissions")
                expanded.update(r["permission_id"] for r in rows)
            elif perm.endswith(".*"):
                # Add all module permissions
                module = perm[:-2]
                rows = self._adapter.fetch_all("""
                    SELECT permission_id FROM permissions WHERE module = ?
                """, (module,))
                expanded.update(r["permission_id"] for r in rows)
            else:
                expanded.add(perm)

        return expanded

    def user_has_permission(self, user_id: str, permission_id: str) -> bool:
        """Check if user has a specific permission."""
        permissions = self.get_user_effective_permissions(user_id)
        return permission_id in permissions

    def user_has_any_permission(self, user_id: str, permission_ids: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        permissions = self.get_user_effective_permissions(user_id)
        return bool(permissions.intersection(permission_ids))

    def user_has_all_permissions(self, user_id: str, permission_ids: List[str]) -> bool:
        """Check if user has all of the specified permissions."""
        permissions = self.get_user_effective_permissions(user_id)
        return all(p in permissions for p in permission_ids)

    # ==================== Password Management ====================

    def validate_password(self, password: str) -> Tuple[bool, List[str]]:
        """Validate password against policy."""
        errors = []
        policy = self.password_policy

        if len(password) < policy.min_length:
            errors.append(f"Password must be at least {policy.min_length} characters")

        if policy.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        if policy.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        if policy.require_digits and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")

        if policy.require_special:
            special_pattern = f"[{re.escape(policy.special_characters)}]"
            if not re.search(special_pattern, password):
                errors.append("Password must contain at least one special character")

        return len(errors) == 0, errors

    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt."""
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def _verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash."""
        return self._hash_password(password, salt) == password_hash

    def get_password_policy(self) -> PasswordPolicy:
        """Get current password policy."""
        row = self._adapter.fetch_one("SELECT * FROM password_policy WHERE id = 1")
        if not row:
            return self.password_policy

        return PasswordPolicy(
            min_length=row["min_length"],
            require_uppercase=bool(row["require_uppercase"]),
            require_lowercase=bool(row["require_lowercase"]),
            require_digits=bool(row["require_digits"]),
            require_special=bool(row["require_special"]),
            special_characters=row["special_characters"] or "!@#$%^&*()_+-=[]{}|;:,.<>?",
            max_age_days=row["max_age_days"],
            history_count=row["history_count"],
            lockout_threshold=row["lockout_threshold"],
            lockout_duration_minutes=row["lockout_duration_minutes"]
        )

    def update_password_policy(self, policy: PasswordPolicy, updated_by: str) -> bool:
        """Update password policy."""
        old_policy = self.get_password_policy()

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE password_policy SET
                    min_length = ?,
                    require_uppercase = ?,
                    require_lowercase = ?,
                    require_digits = ?,
                    require_special = ?,
                    special_characters = ?,
                    max_age_days = ?,
                    history_count = ?,
                    lockout_threshold = ?,
                    lockout_duration_minutes = ?
                WHERE id = 1
            """, (
                policy.min_length,
                1 if policy.require_uppercase else 0,
                1 if policy.require_lowercase else 0,
                1 if policy.require_digits else 0,
                1 if policy.require_special else 0,
                policy.special_characters,
                policy.max_age_days,
                policy.history_count,
                policy.lockout_threshold,
                policy.lockout_duration_minutes
            ))

            self._log_admin_action(
                cursor, "password_policy_updated", "system", "password_policy",
                {"old": old_policy.to_dict(), "new": policy.to_dict()},
                updated_by
            )

            self.password_policy = policy

            return True

    # ==================== Segregation of Duties ====================

    def add_sod_rule(
        self,
        role1_id: str,
        role2_id: str,
        rule_name: str,
        description: str,
        created_by: str
    ) -> bool:
        """Add a segregation of duties rule."""
        with self._adapter.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sod_rules (rule_name, description, role1_id, role2_id, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (rule_name, description, role1_id, role2_id, created_by))

            self._log_admin_action(
                cursor, "sod_rule_created", "sod_rule", f"{role1_id}-{role2_id}",
                {"rule_name": rule_name, "role1": role1_id, "role2": role2_id},
                created_by
            )

            return True

    def check_sod_violations(self, roles: List[str]) -> List[str]:
        """Check if a set of roles violates any SOD rules."""
        violations = []

        with self._adapter.cursor() as cursor:
            for i, role1 in enumerate(roles):
                for role2 in roles[i+1:]:
                    cursor.execute("""
                        SELECT rule_name FROM sod_rules
                        WHERE is_active = 1
                        AND ((role1_id = ? AND role2_id = ?)
                             OR (role1_id = ? AND role2_id = ?))
                    """, (role1, role2, role2, role1))

                    for row in cursor.fetchall():
                        violations.append(f"{row['rule_name']}: {role1} conflicts with {role2}")

            return violations

    # ==================== Audit Log ====================

    def _log_admin_action(
        self,
        cursor: Any,
        action_type: str,
        target_type: str,
        target_id: str,
        changes: Dict[str, Any],
        performed_by: str,
        ip_address: str = ""
    ):
        """Log an administrative action."""
        cursor.execute("""
            INSERT INTO admin_audit_log (
                action_type, target_type, target_id, changes, performed_by, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            action_type, target_type, target_id,
            json.dumps(changes), performed_by, ip_address
        ))

    def get_audit_log(
        self,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        action_type: Optional[str] = None,
        performed_by: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AdminAuditLog]:
        """Query audit log with filters."""
        with self._adapter.cursor() as cursor:
            query = "SELECT * FROM admin_audit_log WHERE 1=1"
            params = []

            if target_type:
                query += " AND target_type = ?"
                params.append(target_type)

            if target_id:
                query += " AND target_id = ?"
                params.append(target_id)

            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)

            if performed_by:
                query += " AND performed_by = ?"
                params.append(performed_by)

            if from_date:
                query += " AND performed_at >= ?"
                params.append(from_date.isoformat())

            if to_date:
                query += " AND performed_at <= ?"
                params.append(to_date.isoformat())

            query += " ORDER BY performed_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            logs = []
            for row in cursor.fetchall():
                logs.append(AdminAuditLog(
                    id=row["id"],
                    action_type=row["action_type"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    changes=json.loads(row["changes"]) if row["changes"] else {},
                    performed_by=row["performed_by"],
                    performed_at=datetime.fromisoformat(row["performed_at"]) if row["performed_at"] else datetime.utcnow(),
                    ip_address=row["ip_address"] or ""
                ))

            return logs

    # ==================== Authentication ====================

    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[User], str]:
        """
        Authenticate a user.

        Returns:
            Tuple of (success, user, message)
        """
        user = self.get_user_by_username(username)
        if not user:
            return False, None, "Invalid username or password"

        # Check account status
        if user.status == AccountStatus.DISABLED:
            return False, None, "Account is disabled"

        if user.status == AccountStatus.LOCKED:
            # Check if lockout has expired
            if user.locked_until and user.locked_until > datetime.utcnow():
                remaining = (user.locked_until - datetime.utcnow()).seconds // 60
                return False, None, f"Account is locked. Try again in {remaining} minutes."
            else:
                # Auto-unlock
                self.unlock_user(user.user_id, "system")
                user = self.get_user(user.user_id)

        # Verify password
        if not self._verify_password(password, user.password_hash, user.password_salt):
            self._record_failed_login(user.user_id)
            return False, None, "Invalid username or password"

        # Check password expiry
        if user.password_changed_at:
            age = datetime.utcnow() - user.password_changed_at
            if age.days > self.password_policy.max_age_days:
                return False, user, "Password has expired. Please change your password."

        # Successful login
        self._record_successful_login(user.user_id)

        return True, user, "Login successful"

    def _record_failed_login(self, user_id: str):
        """Record a failed login attempt."""
        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET failed_login_attempts = failed_login_attempts + 1
                WHERE user_id = ?
            """, (user_id,))

            cursor.execute("SELECT failed_login_attempts FROM users WHERE user_id = ?", (user_id,))
            attempts = cursor.fetchone()[0]

            # Lock if threshold exceeded
            if attempts >= self.password_policy.lockout_threshold:
                lockout_until = datetime.utcnow() + timedelta(minutes=self.password_policy.lockout_duration_minutes)
                cursor.execute("""
                    UPDATE users SET status = 'locked', locked_until = ?
                    WHERE user_id = ?
                """, (lockout_until.isoformat(), user_id))

                self._log_admin_action(
                    cursor, "user_auto_locked", "user", user_id,
                    {"reason": "Too many failed login attempts"},
                    "system"
                )

    def _record_successful_login(self, user_id: str):
        """Record a successful login."""
        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET
                    failed_login_attempts = 0,
                    last_login = ?
                WHERE user_id = ?
            """, (datetime.utcnow().isoformat(), user_id))
