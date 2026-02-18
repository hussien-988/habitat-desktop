# -*- coding: utf-8 -*-
"""
User repository for database operations.
"""

from typing import List, Optional
from datetime import datetime

from models.user import User
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class UserRepository:
    """Repository for User CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, user: User) -> User:
        """Create a new user record."""
        query = """
            INSERT INTO users (
                user_id, username, password_hash, password_salt, email,
                full_name, full_name_ar, role,
                is_active, is_locked, failed_attempts,
                last_login, last_activity,
                created_at, updated_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            user.user_id, user.username, user.password_hash, user.password_salt, user.email,
            user.full_name, user.full_name_ar, user.role,
            1 if user.is_active else 0,
            1 if user.is_locked else 0,
            user.failed_attempts,
            user.last_login.isoformat() if user.last_login else None,
            user.last_activity.isoformat() if user.last_activity else None,
            user.created_at.isoformat() if user.created_at else None,
            user.updated_at.isoformat() if user.updated_at else None,
            user.created_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created user: {user.username}")
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        query = "SELECT * FROM users WHERE user_id = ?"
        row = self.db.fetch_one(query, (user_id,))
        if row:
            return self._row_to_user(row)
        return None

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        query = "SELECT * FROM users WHERE username = ?"
        row = self.db.fetch_one(query, (username,))
        if row:
            return self._row_to_user(row)
        return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Get all users with pagination."""
        query = "SELECT * FROM users ORDER BY username LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_user(row) for row in rows]

    def get_active_users(self) -> List[User]:
        """Get all active users."""
        query = "SELECT * FROM users WHERE is_active = 1 ORDER BY username"
        rows = self.db.fetch_all(query)
        return [self._row_to_user(row) for row in rows]

    def update(self, user: User) -> User:
        """Update an existing user."""
        user.updated_at = datetime.now()
        query = """
            UPDATE users SET
                email = ?, full_name = ?, full_name_ar = ?, role = ?,
                is_active = ?, is_locked = ?, failed_attempts = ?,
                last_login = ?, last_activity = ?,
                updated_at = ?
            WHERE user_id = ?
        """
        params = (
            user.email, user.full_name, user.full_name_ar, user.role,
            1 if user.is_active else 0,
            1 if user.is_locked else 0,
            user.failed_attempts,
            user.last_login.isoformat() if user.last_login else None,
            user.last_activity.isoformat() if user.last_activity else None,
            user.updated_at.isoformat(),
            user.user_id
        )
        self.db.execute(query, params)
        logger.debug(f"Updated user: {user.username}")
        return user

    def update_password(self, user_id: str, password_hash: str) -> bool:
        """Update user password."""
        query = "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?"
        self.db.execute(query, (password_hash, datetime.now().isoformat(), user_id))
        return True

    def update_last_login(self, user_id: str) -> bool:
        """Update user last login timestamp."""
        now = datetime.now().isoformat()
        query = "UPDATE users SET last_login = ?, last_activity = ? WHERE user_id = ?"
        self.db.execute(query, (now, now, user_id))
        return True

    def increment_failed_attempts(self, user_id: str) -> int:
        """Increment failed login attempts and return new count."""
        query = """
            UPDATE users SET failed_attempts = failed_attempts + 1
            WHERE user_id = ?
        """
        self.db.execute(query, (user_id,))

        result = self.db.fetch_one(
            "SELECT failed_attempts FROM users WHERE user_id = ?",
            (user_id,)
        )
        return result["failed_attempts"] if result else 0

    def reset_failed_attempts(self, user_id: str) -> bool:
        """Reset failed login attempts."""
        query = "UPDATE users SET failed_attempts = 0, is_locked = 0 WHERE user_id = ?"
        self.db.execute(query, (user_id,))
        return True

    def lock_user(self, user_id: str) -> bool:
        """Lock a user account."""
        query = "UPDATE users SET is_locked = 1 WHERE user_id = ?"
        self.db.execute(query, (user_id,))
        return True

    def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        query = "DELETE FROM users WHERE user_id = ?"
        self.db.execute(query, (user_id,))
        return True

    def count(self) -> int:
        """Count total users."""
        result = self.db.fetch_one("SELECT COUNT(*) as count FROM users")
        return result["count"] if result else 0

    def _row_to_user(self, row) -> User:
        """Convert database row to User object."""
        data = dict(row)

        # Handle boolean fields
        data["is_active"] = bool(data.get("is_active", 1))
        data["is_locked"] = bool(data.get("is_locked", 0))

        for field in ["last_login", "last_activity", "created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return User(**{k: v for k, v in data.items() if k in User.__dataclass_fields__})
