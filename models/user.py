# -*- coding: utf-8 -*-
"""
User entity model for authentication.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid
import hashlib


@dataclass
class User:
    """
    User entity for system authentication and authorization.
    """

    # Primary identifier
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Credentials
    username: str = ""
    password_hash: str = ""  # SHA-256 hash
    email: Optional[str] = None

    # Profile
    full_name: str = ""
    full_name_ar: str = ""
    role: str = "analyst"  # admin, data_manager, office_clerk, field_supervisor, analyst

    # Status
    is_active: bool = True
    is_locked: bool = False
    failed_attempts: int = 0

    # Session
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

    def set_password(self, password: str):
        """Set user password (hashed)."""
        self.password_hash = self.hash_password(password)

    def check_password(self, password: str) -> bool:
        """Check if password matches."""
        return self.password_hash == self.hash_password(password)

    @property
    def role_display(self) -> str:
        """Get display name for role."""
        roles = {
            "admin": "Administrator",
            "data_manager": "Data Manager",
            "office_clerk": "Office Clerk",
            "field_supervisor": "Field Supervisor",
            "analyst": "Analyst",
        }
        return roles.get(self.role, self.role)

    @property
    def role_display_ar(self) -> str:
        """Get Arabic display name for role."""
        roles = {
            "admin": "مدير النظام",
            "data_manager": "مدير البيانات",
            "office_clerk": "موظف المكتب",
            "field_supervisor": "مشرف ميداني",
            "analyst": "محلل",
        }
        return roles.get(self.role, self.role)

    @property
    def display_name(self) -> str:
        """Get display name (Arabic if available, else English)."""
        if self.full_name_ar:
            return self.full_name_ar
        return self.full_name or self.username

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        permissions = {
            "admin": ["all"],
            "data_manager": ["import", "export", "review", "approve", "report"],
            "office_clerk": ["create", "edit", "scan", "print"],
            "field_supervisor": ["view", "export", "report"],
            "analyst": ["view", "export", "report"],
        }

        user_perms = permissions.get(self.role, [])
        return "all" in user_perms or permission in user_perms

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization (excluding password)."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "full_name_ar": self.full_name_ar,
            "role": self.role,
            "is_active": self.is_active,
            "is_locked": self.is_locked,
            "failed_attempts": self.failed_attempts,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create User from dictionary."""
        for field_name in ["last_login", "last_activity", "created_at", "updated_at"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
