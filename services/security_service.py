# -*- coding: utf-8 -*-
"""
Security settings and audit log service.
Implements UC-011: Security Settings
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid
import json

from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SecuritySettings:
    """Security policy configuration."""
    setting_id: str = "default"
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_symbol: bool = False
    password_expiry_days: int = 90
    password_reuse_history: int = 5
    session_timeout_minutes: int = 30
    max_failed_login_attempts: int = 5
    account_lockout_duration_minutes: int = 15
    updated_at: datetime = None
    updated_by: str = None


@dataclass
class AuditLogEntry:
    """Audit log entry."""
    log_id: str = None
    timestamp: datetime = None
    user_id: str = None
    username: str = None
    action: str = None
    entity_type: str = None
    entity_id: str = None
    old_values: dict = None
    new_values: dict = None
    ip_address: str = None
    details: str = None

    def __post_init__(self):
        if not self.log_id:
            self.log_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now()


class SecurityService:
    """
    Service for managing security settings and audit logging.
    Implements UC-011 Security Settings.
    """

    # Validation constraints
    MIN_PASSWORD_LENGTH = 6
    MAX_PASSWORD_LENGTH = 128
    MIN_SESSION_TIMEOUT = 5
    MAX_SESSION_TIMEOUT = 480  # 8 hours
    MIN_LOCKOUT_DURATION = 1
    MAX_LOCKOUT_DURATION = 1440  # 24 hours
    MAX_FAILED_ATTEMPTS = 20

    def __init__(self, db: Database):
        self.db = db

    # ========== Security Settings ==========

    def get_settings(self) -> SecuritySettings:
        """Get current security settings."""
        query = "SELECT * FROM security_settings WHERE setting_id = 'default'"
        row = self.db.fetch_one(query)

        if row:
            data = dict(row)
            # Convert boolean fields
            for field in ["password_require_uppercase", "password_require_lowercase",
                          "password_require_digit", "password_require_symbol"]:
                data[field] = bool(data.get(field, 0))

            # Parse datetime
            if data.get("updated_at"):
                data["updated_at"] = datetime.fromisoformat(data["updated_at"])

            return SecuritySettings(**{k: v for k, v in data.items()
                                       if k in SecuritySettings.__dataclass_fields__})

        return SecuritySettings()

    def update_settings(self, settings: SecuritySettings, user_id: str = None) -> tuple:
        """
        Update security settings after validation.
        Returns (success: bool, errors: list)
        """
        # Validate settings
        errors = self._validate_settings(settings)
        if errors:
            return False, errors

        settings.updated_at = datetime.now()
        settings.updated_by = user_id

        query = """
            UPDATE security_settings SET
                password_min_length = ?,
                password_require_uppercase = ?,
                password_require_lowercase = ?,
                password_require_digit = ?,
                password_require_symbol = ?,
                password_expiry_days = ?,
                password_reuse_history = ?,
                session_timeout_minutes = ?,
                max_failed_login_attempts = ?,
                account_lockout_duration_minutes = ?,
                updated_at = ?,
                updated_by = ?
            WHERE setting_id = 'default'
        """
        params = (
            settings.password_min_length,
            1 if settings.password_require_uppercase else 0,
            1 if settings.password_require_lowercase else 0,
            1 if settings.password_require_digit else 0,
            1 if settings.password_require_symbol else 0,
            settings.password_expiry_days,
            settings.password_reuse_history,
            settings.session_timeout_minutes,
            settings.max_failed_login_attempts,
            settings.account_lockout_duration_minutes,
            settings.updated_at.isoformat(),
            settings.updated_by
        )
        self.db.execute(query, params)

        # Log the change
        self.log_action(
            action="security_settings_updated",
            entity_type="security_settings",
            entity_id="default",
            details="Security policy updated",
            user_id=user_id
        )

        logger.info("Security settings updated")
        return True, []

    def _validate_settings(self, settings: SecuritySettings) -> List[str]:
        """Validate security settings (UC-011 S06)."""
        errors = []

        # Password length validation
        if settings.password_min_length < self.MIN_PASSWORD_LENGTH:
            errors.append(f"طول كلمة المرور يجب أن يكون {self.MIN_PASSWORD_LENGTH} على الأقل")
        if settings.password_min_length > self.MAX_PASSWORD_LENGTH:
            errors.append(f"طول كلمة المرور يجب ألا يتجاوز {self.MAX_PASSWORD_LENGTH}")

        # Session timeout validation
        if settings.session_timeout_minutes < self.MIN_SESSION_TIMEOUT:
            errors.append(f"مهلة الجلسة يجب أن تكون {self.MIN_SESSION_TIMEOUT} دقائق على الأقل")
        if settings.session_timeout_minutes > self.MAX_SESSION_TIMEOUT:
            errors.append(f"مهلة الجلسة يجب ألا تتجاوز {self.MAX_SESSION_TIMEOUT} دقيقة")

        # Lockout settings validation
        if settings.max_failed_login_attempts < 1:
            errors.append("عدد المحاولات الفاشلة يجب أن يكون 1 على الأقل")
        if settings.max_failed_login_attempts > self.MAX_FAILED_ATTEMPTS:
            errors.append(f"عدد المحاولات الفاشلة يجب ألا يتجاوز {self.MAX_FAILED_ATTEMPTS}")

        if settings.account_lockout_duration_minutes < self.MIN_LOCKOUT_DURATION:
            errors.append(f"مدة القفل يجب أن تكون {self.MIN_LOCKOUT_DURATION} دقيقة على الأقل")
        if settings.account_lockout_duration_minutes > self.MAX_LOCKOUT_DURATION:
            errors.append(f"مدة القفل يجب ألا تتجاوز {self.MAX_LOCKOUT_DURATION} دقيقة")

        # Password expiry validation
        if settings.password_expiry_days < 0:
            errors.append("أيام انتهاء كلمة المرور يجب أن تكون 0 أو أكثر")
        if settings.password_expiry_days > 365:
            errors.append("أيام انتهاء كلمة المرور يجب ألا تتجاوز 365")

        # Password reuse history
        if settings.password_reuse_history < 0:
            errors.append("سجل كلمات المرور السابقة يجب أن يكون 0 أو أكثر")
        if settings.password_reuse_history > 24:
            errors.append("سجل كلمات المرور السابقة يجب ألا يتجاوز 24")

        return errors

    def validate_password(self, password: str) -> tuple:
        """
        Validate a password against current security policy.
        Returns (is_valid: bool, errors: list)
        """
        settings = self.get_settings()
        errors = []

        if len(password) < settings.password_min_length:
            errors.append(f"كلمة المرور يجب أن تكون {settings.password_min_length} أحرف على الأقل")

        if settings.password_require_uppercase and not any(c.isupper() for c in password):
            errors.append("كلمة المرور يجب أن تحتوي على حرف كبير")

        if settings.password_require_lowercase and not any(c.islower() for c in password):
            errors.append("كلمة المرور يجب أن تحتوي على حرف صغير")

        if settings.password_require_digit and not any(c.isdigit() for c in password):
            errors.append("كلمة المرور يجب أن تحتوي على رقم")

        if settings.password_require_symbol:
            symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in symbols for c in password):
                errors.append("كلمة المرور يجب أن تحتوي على رمز خاص")

        return len(errors) == 0, errors

    # ========== Audit Logging ==========

    def log_action(
        self,
        action: str,
        entity_type: str = None,
        entity_id: str = None,
        old_values: dict = None,
        new_values: dict = None,
        details: str = None,
        user_id: str = None,
        username: str = None
    ) -> str:
        """
        Log an action to the audit trail.
        Returns the log_id.
        """
        log_id = str(uuid.uuid4())

        query = """
            INSERT INTO audit_log (
                log_id, timestamp, user_id, username, action,
                entity_type, entity_id, old_values, new_values, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            log_id,
            datetime.now().isoformat(),
            user_id,
            username,
            action,
            entity_type,
            entity_id,
            json.dumps(old_values, ensure_ascii=False) if old_values else None,
            json.dumps(new_values, ensure_ascii=False) if new_values else None,
            details
        )
        self.db.execute(query, params)

        logger.debug(f"Audit log: {action} on {entity_type}/{entity_id}")
        return log_id

    def get_audit_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: str = None,
        action: str = None,
        entity_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[AuditLogEntry]:
        """Get audit log entries with optional filters."""
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

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(query, tuple(params))

        logs = []
        for row in rows:
            data = dict(row)
            if data.get("timestamp"):
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            if data.get("old_values"):
                try:
                    data["old_values"] = json.loads(data["old_values"])
                except json.JSONDecodeError:
                    pass
            if data.get("new_values"):
                try:
                    data["new_values"] = json.loads(data["new_values"])
                except json.JSONDecodeError:
                    pass
            logs.append(AuditLogEntry(**{k: v for k, v in data.items()
                                         if k in AuditLogEntry.__dataclass_fields__}))

        return logs

    def get_audit_log_count(self) -> int:
        """Get total count of audit log entries."""
        query = "SELECT COUNT(*) FROM audit_log"
        row = self.db.fetch_one(query)
        return row[0] if row else 0

    def get_action_types(self) -> List[str]:
        """Get distinct action types from audit log."""
        query = "SELECT DISTINCT action FROM audit_log ORDER BY action"
        rows = self.db.fetch_all(query)
        return [row["action"] for row in rows]
