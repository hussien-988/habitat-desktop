# -*- coding: utf-8 -*-
"""
Security Settings Service
==========================
Implements UC-011 Security Settings requirements.

Features:
- Password policy management
- Session timeout configuration
- Account lockout settings
- Security audit logging
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
import json

from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SecurityPolicy:
    """
    Security policy configuration as per UC-011.

    Implements:
    - S03: Password policies
    - S04: Session/Lockout settings
    - S05: Access control
    """
    # Password Policy (UC-011 S03)
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_numbers: bool = True
    password_require_special: bool = True
    password_expiry_days: int = 90  # 0 = never expires
    password_reuse_history: int = 5  # Number of previous passwords to check

    # Session Settings (UC-011 S04)
    session_timeout_minutes: int = 30
    session_max_concurrent: int = 3

    # Lockout Settings (UC-011 S04)
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30
    auto_unlock: bool = True

    # 2FA Settings
    require_2fa_admin: bool = True
    require_2fa_all: bool = False

    # Audit Settings
    audit_login_attempts: bool = True
    audit_data_changes: bool = True
    audit_retention_days: int = 365

    def to_dict(self) -> Dict[str, Any]:
        return {
            "password_min_length": self.password_min_length,
            "password_require_uppercase": self.password_require_uppercase,
            "password_require_lowercase": self.password_require_lowercase,
            "password_require_numbers": self.password_require_numbers,
            "password_require_special": self.password_require_special,
            "password_expiry_days": self.password_expiry_days,
            "password_reuse_history": self.password_reuse_history,
            "session_timeout_minutes": self.session_timeout_minutes,
            "session_max_concurrent": self.session_max_concurrent,
            "max_failed_attempts": self.max_failed_attempts,
            "lockout_duration_minutes": self.lockout_duration_minutes,
            "auto_unlock": self.auto_unlock,
            "require_2fa_admin": self.require_2fa_admin,
            "require_2fa_all": self.require_2fa_all,
            "audit_login_attempts": self.audit_login_attempts,
            "audit_data_changes": self.audit_data_changes,
            "audit_retention_days": self.audit_retention_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityPolicy":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SecuritySettingsService:
    """
    Security settings management service.

    Implements UC-011 Security Settings use case.
    """

    def __init__(self, db: Database):
        self.db = db
        self._policy: Optional[SecurityPolicy] = None
        self._ensure_tables()
        self._load_policy()

    def _ensure_tables(self):
        """Create security settings tables."""
        cursor = self.db.cursor()

        # Security settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TEXT,
                updated_by TEXT
            )
        """)

        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                username TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                old_value TEXT,
                new_value TEXT,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT
            )
        """)

        # Session tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_activity TEXT,
                ip_address TEXT,
                user_agent TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Login attempts tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                attempt_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                success INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                failure_reason TEXT
            )
        """)

        self.db.connection.commit()

    def _load_policy(self):
        """Load security policy from database."""
        cursor = self.db.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM security_settings")
        rows = cursor.fetchall()

        if rows:
            settings = {}
            for row in rows:
                key = row[0]
                try:
                    settings[key] = json.loads(row[1])
                except json.JSONDecodeError:
                    settings[key] = row[1]

            self._policy = SecurityPolicy.from_dict(settings)
        else:
            # Use default policy
            self._policy = SecurityPolicy()
            self._save_policy()

    def _save_policy(self, updated_by: str = None):
        """Save security policy to database."""
        cursor = self.db.cursor()
        now = datetime.now().isoformat()

        for key, value in self._policy.to_dict().items():
            cursor.execute("""
                INSERT OR REPLACE INTO security_settings (setting_key, setting_value, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
            """, (key, json.dumps(value), now, updated_by))

        self.db.connection.commit()

    @property
    def policy(self) -> SecurityPolicy:
        """Get current security policy."""
        return self._policy

    def update_policy(self, updates: Dict[str, Any], updated_by: str = None) -> bool:
        """
        Update security policy settings.

        Args:
            updates: Dictionary of settings to update
            updated_by: User making the update

        Returns:
            True if successful
        """
        try:
            old_policy = self._policy.to_dict()

            for key, value in updates.items():
                if hasattr(self._policy, key):
                    setattr(self._policy, key, value)

            self._save_policy(updated_by)

            # Log the change
            self.log_audit(
                user_id=updated_by,
                action="security_policy_updated",
                entity_type="security_settings",
                old_value=old_policy,
                new_value=self._policy.to_dict()
            )

            logger.info(f"Security policy updated by {updated_by}")
            return True
        except Exception as e:
            logger.error(f"Failed to update security policy: {e}")
            return False

    # ==================== Password Validation ====================

    def validate_password(self, password: str) -> tuple:
        """
        Validate password against security policy.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if len(password) < self._policy.password_min_length:
            errors.append(f"Password must be at least {self._policy.password_min_length} characters")

        if self._policy.password_require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if self._policy.password_require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if self._policy.password_require_numbers and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")

        if self._policy.password_require_special:
            special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
            if not any(c in special_chars for c in password):
                errors.append("Password must contain at least one special character")

        return len(errors) == 0, errors

    def get_password_requirements_text(self) -> str:
        """Get human-readable password requirements."""
        reqs = [f"Minimum {self._policy.password_min_length} characters"]

        if self._policy.password_require_uppercase:
            reqs.append("At least one uppercase letter")
        if self._policy.password_require_lowercase:
            reqs.append("At least one lowercase letter")
        if self._policy.password_require_numbers:
            reqs.append("At least one number")
        if self._policy.password_require_special:
            reqs.append("At least one special character")

        return "\n".join(f"• {r}" for r in reqs)

    # ==================== Account Lockout ====================

    def record_login_attempt(
        self,
        username: str,
        success: bool,
        ip_address: str = None,
        user_agent: str = None,
        failure_reason: str = None
    ):
        """Record a login attempt."""
        import uuid
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT INTO login_attempts (attempt_id, username, timestamp, success, ip_address, user_agent, failure_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            username,
            datetime.now().isoformat(),
            1 if success else 0,
            ip_address,
            user_agent,
            failure_reason
        ))

        self.db.connection.commit()

        # Check for lockout
        if not success:
            self._check_lockout(username)

    def _check_lockout(self, username: str):
        """Check if account should be locked."""
        cursor = self.db.cursor()

        # Get recent failed attempts
        lockout_window = datetime.now().isoformat()[:10]  # Today

        cursor.execute("""
            SELECT COUNT(*) FROM login_attempts
            WHERE username = ? AND success = 0 AND timestamp >= ?
        """, (username, lockout_window))

        failed_count = cursor.fetchone()[0]

        if failed_count >= self._policy.max_failed_attempts:
            # Lock the account
            cursor.execute("""
                UPDATE users SET is_locked = 1, failed_attempts = ?
                WHERE username = ?
            """, (failed_count, username))
            self.db.connection.commit()

            logger.warning(f"Account locked due to too many failed attempts: {username}")

    def check_account_locked(self, username: str) -> tuple:
        """
        Check if account is locked.

        Returns:
            Tuple of (is_locked, unlock_time)
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT is_locked, failed_attempts FROM users WHERE username = ?
        """, (username,))
        row = cursor.fetchone()

        if not row:
            return False, None

        if row[0]:  # is_locked
            if self._policy.auto_unlock:
                # Check if lockout duration has passed
                cursor.execute("""
                    SELECT MAX(timestamp) FROM login_attempts
                    WHERE username = ? AND success = 0
                """, (username,))
                last_failure = cursor.fetchone()[0]

                if last_failure:
                    from datetime import timedelta
                    last_failure_time = datetime.fromisoformat(last_failure)
                    unlock_time = last_failure_time + timedelta(minutes=self._policy.lockout_duration_minutes)

                    if datetime.now() > unlock_time:
                        # Auto unlock
                        self.unlock_account(username)
                        return False, None
                    else:
                        return True, unlock_time

            return True, None

        return False, None

    def unlock_account(self, username: str, unlocked_by: str = None):
        """Manually unlock an account."""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE users SET is_locked = 0, failed_attempts = 0
            WHERE username = ?
        """, (username,))
        self.db.connection.commit()

        self.log_audit(
            user_id=unlocked_by,
            action="account_unlocked",
            entity_type="user",
            entity_id=username,
            details=f"Account unlocked by {unlocked_by or 'system'}"
        )

        logger.info(f"Account unlocked: {username}")

    # ==================== Session Management ====================

    def create_session(
        self,
        user_id: str,
        ip_address: str = None,
        user_agent: str = None
    ) -> str:
        """Create a new session for user."""
        import uuid
        session_id = str(uuid.uuid4())
        cursor = self.db.cursor()

        # Check concurrent sessions
        cursor.execute("""
            SELECT COUNT(*) FROM user_sessions
            WHERE user_id = ? AND is_active = 1
        """, (user_id,))
        active_sessions = cursor.fetchone()[0]

        if active_sessions >= self._policy.session_max_concurrent:
            # Invalidate oldest session
            cursor.execute("""
                UPDATE user_sessions SET is_active = 0
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at ASC LIMIT 1
            """, (user_id,))

        # Create new session
        cursor.execute("""
            INSERT INTO user_sessions (session_id, user_id, created_at, last_activity, ip_address, user_agent, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (session_id, user_id, datetime.now().isoformat(), datetime.now().isoformat(), ip_address, user_agent))

        self.db.connection.commit()
        return session_id

    def validate_session(self, session_id: str) -> tuple:
        """
        Validate a session.

        Returns:
            Tuple of (is_valid, user_id)
        """
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT user_id, last_activity FROM user_sessions
            WHERE session_id = ? AND is_active = 1
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return False, None

        user_id, last_activity = row

        # Check timeout
        from datetime import timedelta
        last_activity_time = datetime.fromisoformat(last_activity)
        timeout_time = last_activity_time + timedelta(minutes=self._policy.session_timeout_minutes)

        if datetime.now() > timeout_time:
            self.invalidate_session(session_id)
            return False, None

        # Update last activity
        cursor.execute("""
            UPDATE user_sessions SET last_activity = ?
            WHERE session_id = ?
        """, (datetime.now().isoformat(), session_id))
        self.db.connection.commit()

        return True, user_id

    def invalidate_session(self, session_id: str):
        """Invalidate a session."""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE user_sessions SET is_active = 0
            WHERE session_id = ?
        """, (session_id,))
        self.db.connection.commit()

    def invalidate_all_sessions(self, user_id: str):
        """Invalidate all sessions for a user."""
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE user_sessions SET is_active = 0
            WHERE user_id = ?
        """, (user_id,))
        self.db.connection.commit()

    # ==================== Audit Logging ====================

    def log_audit(
        self,
        action: str,
        entity_type: str = None,
        entity_id: str = None,
        user_id: str = None,
        username: str = None,
        old_value: Any = None,
        new_value: Any = None,
        ip_address: str = None,
        user_agent: str = None,
        details: str = None
    ):
        """Log an audit event."""
        if not self._policy.audit_data_changes and action not in ["login", "logout", "login_failed"]:
            return

        import uuid
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT INTO audit_log (
                log_id, timestamp, user_id, username, action, entity_type, entity_id,
                old_value, new_value, ip_address, user_agent, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            datetime.now().isoformat(),
            user_id,
            username,
            action,
            entity_type,
            entity_id,
            json.dumps(old_value, ensure_ascii=False) if old_value else None,
            json.dumps(new_value, ensure_ascii=False) if new_value else None,
            ip_address,
            user_agent,
            details
        ))

        self.db.connection.commit()

    def get_audit_log(
        self,
        user_id: str = None,
        action: str = None,
        entity_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> list:
        """Get audit log entries with optional filters."""
        cursor = self.db.cursor()

        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if action:
            query += " AND action = ?"
            params.append(action)

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        query += f" ORDER BY timestamp DESC LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        logs = []
        for row in rows:
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

    def cleanup_old_audit_logs(self):
        """Clean up audit logs older than retention period."""
        if self._policy.audit_retention_days <= 0:
            return

        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=self._policy.audit_retention_days)).isoformat()

        cursor = self.db.cursor()
        cursor.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff_date,))
        deleted = cursor.rowcount
        self.db.connection.commit()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old audit log entries")
