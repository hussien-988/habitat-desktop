# -*- coding: utf-8 -*-
"""
Authentication service.
"""

from typing import Optional, Tuple
from datetime import datetime

from models.user import User
from repositories.database import Database
from repositories.user_repository import UserRepository
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_FAILED_ATTEMPTS = 5


class AuthService:
    """Service for user authentication."""

    def __init__(self, db: Database):
        self.db = db
        self.user_repo = UserRepository(db)

    def authenticate(self, username: str, password: str) -> Tuple[Optional[User], str]:
        """
        Authenticate a user.

        Returns:
            Tuple of (User or None, error message)
        """
        if not username or not password:
            return None, "Username and password are required"

        # Get user by username
        user = self.user_repo.get_by_username(username)

        if not user:
            logger.warning(f"Login attempt with unknown username: {username}")
            return None, "Invalid username or password"

        # Check if account is locked
        if user.is_locked:
            logger.warning(f"Login attempt on locked account: {username}")
            return None, "Account is locked. Please contact administrator."

        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt on inactive account: {username}")
            return None, "Account is inactive. Please contact administrator."

        # Verify password
        if not user.check_password(password):
            # Increment failed attempts
            attempts = self.user_repo.increment_failed_attempts(user.user_id)
            logger.warning(f"Failed login attempt for {username} ({attempts}/{MAX_FAILED_ATTEMPTS})")

            if attempts >= MAX_FAILED_ATTEMPTS:
                self.user_repo.lock_user(user.user_id)
                logger.warning(f"Account locked due to too many failed attempts: {username}")
                return None, "Account locked due to too many failed attempts."

            return None, "Invalid username or password"

        # Successful login
        self.user_repo.reset_failed_attempts(user.user_id)
        self.user_repo.update_last_login(user.user_id)

        # Refresh user data
        user = self.user_repo.get_by_id(user.user_id)

        logger.info(f"User logged in successfully: {username} ({user.role})")
        return user, ""

    def change_password(self, user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Change user password.

        Returns:
            Tuple of (success, error message)
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return False, "User not found"

        if not user.check_password(old_password):
            return False, "Current password is incorrect"

        if len(new_password) < 6:
            return False, "Password must be at least 6 characters"

        password_hash = User.hash_password(new_password)
        self.user_repo.update_password(user_id, password_hash)

        logger.info(f"Password changed for user: {user.username}")
        return True, ""

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.user_repo.get_by_id(user_id)

    def update_activity(self, user_id: str):
        """Update user's last activity timestamp."""
        query = "UPDATE users SET last_activity = ? WHERE user_id = ?"
        self.db.execute(query, (datetime.now().isoformat(), user_id))
