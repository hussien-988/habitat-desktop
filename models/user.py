# -*- coding: utf-8 -*-
"""
User entity model for authentication.
Implements FR-D-16 security requirements with bcrypt hashing and 2FA support.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import uuid
import hashlib
import secrets
import base64

# Try to import bcrypt, fall back to hashlib if not available
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

# Try to import pyotp for 2FA
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False


@dataclass
class User:
    """
    User entity for system authentication and authorization.
    Implements FR-D-16 security requirements:
    - Bcrypt password hashing with salt
    - Two-factor authentication (2FA) support
    - Password history tracking
    - Password expiry management
    """

    # Primary identifier
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Credentials
    username: str = ""
    password_hash: str = ""  # Bcrypt hash with salt (FR-D-16.1)
    password_salt: str = ""  # Explicit salt storage for compatibility
    email: Optional[str] = None

    # Profile
    full_name: str = ""
    full_name_ar: str = ""
    role: str = "analyst"  # admin, data_manager, office_clerk, field_supervisor, analyst

    # Status
    is_active: bool = True
    is_locked: bool = False
    failed_attempts: int = 0

    # Two-Factor Authentication (FR-D-16.3)
    totp_secret: Optional[str] = None  # Base32 encoded secret for TOTP
    is_2fa_enabled: bool = False
    backup_codes: str = ""  # Comma-separated hashed backup codes

    # Password Management (UC-011)
    password_history: str = ""  # Comma-separated previous password hashes
    password_changed_at: Optional[datetime] = None
    password_expires_at: Optional[datetime] = None
    must_change_password: bool = False

    # Session
    last_login: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None

    # API token (set when authenticating via API backend)
    _api_token: Optional[str] = None

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple:
        """
        Hash a password using bcrypt with salt (FR-D-16.1).
        Falls back to SHA-256 with salt if bcrypt is not available.

        Returns:
            Tuple of (hash, salt)
        """
        if BCRYPT_AVAILABLE:
            # Use bcrypt for secure hashing
            if salt:
                salt_bytes = salt.encode('utf-8')
            else:
                salt_bytes = bcrypt.gensalt(rounds=12)

            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt_bytes)
            return password_hash.decode('utf-8'), salt_bytes.decode('utf-8')
        else:
            # Fallback: SHA-256 with salt
            if not salt:
                salt = secrets.token_hex(32)

            salted_password = f"{salt}{password}"
            password_hash = hashlib.sha256(salted_password.encode()).hexdigest()
            return password_hash, salt

    def set_password(self, password: str, track_history: bool = True):
        """
        Set user password with history tracking (UC-011).

        Args:
            password: New password
            track_history: Whether to add old password to history
        """
        # Track password history before changing
        if track_history and self.password_hash:
            history = self.get_password_history()
            history.insert(0, self.password_hash)
            # Keep only last 5 passwords (UC-011 password_reuse_history)
            history = history[:5]
            self.password_history = ",".join(history)

        # Hash new password
        self.password_hash, self.password_salt = self.hash_password(password)
        self.password_changed_at = datetime.now()
        self.must_change_password = False

    def check_password(self, password: str) -> bool:
        """Check if password matches using secure comparison."""
        if BCRYPT_AVAILABLE and self.password_hash.startswith('$2'):
            # Bcrypt hash
            try:
                return bcrypt.checkpw(
                    password.encode('utf-8'),
                    self.password_hash.encode('utf-8')
                )
            except Exception:
                return False
        else:
            # SHA-256 with salt fallback
            computed_hash, _ = self.hash_password(password, self.password_salt)
            return secrets.compare_digest(computed_hash, self.password_hash)

    def is_password_in_history(self, password: str) -> bool:
        """Check if password was used recently (UC-011)."""
        history = self.get_password_history()
        for old_hash in history:
            if BCRYPT_AVAILABLE and old_hash.startswith('$2'):
                try:
                    if bcrypt.checkpw(password.encode('utf-8'), old_hash.encode('utf-8')):
                        return True
                except Exception:
                    pass
            else:
                # Check with current salt
                computed_hash, _ = self.hash_password(password, self.password_salt)
                if secrets.compare_digest(computed_hash, old_hash):
                    return True
        return False

    def get_password_history(self) -> List[str]:
        """Get list of previous password hashes."""
        if self.password_history:
            return [h.strip() for h in self.password_history.split(",") if h.strip()]
        return []

    def is_password_expired(self, expiry_days: int = 90) -> bool:
        """Check if password has expired (UC-011)."""
        if not self.password_changed_at:
            return False

        from datetime import timedelta
        expiry_date = self.password_changed_at + timedelta(days=expiry_days)
        return datetime.now() > expiry_date

    # ==================== Two-Factor Authentication (FR-D-16.3) ====================

    def setup_2fa(self) -> str:
        """
        Setup 2FA for user and return provisioning URI.

        Returns:
            Provisioning URI for QR code generation
        """
        if not PYOTP_AVAILABLE:
            raise ImportError("pyotp is required for 2FA. Install with: pip install pyotp")

        # Generate new secret
        self.totp_secret = pyotp.random_base32()

        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
        self.backup_codes = ",".join([
            hashlib.sha256(code.encode()).hexdigest() for code in backup_codes
        ])

        # Generate provisioning URI
        totp = pyotp.TOTP(self.totp_secret)
        return totp.provisioning_uri(
            name=self.username,
            issuer_name="UN-Habitat TRRCMS"
        ), backup_codes

    def verify_2fa_code(self, code: str) -> bool:
        """
        Verify 2FA TOTP code.

        Args:
            code: 6-digit TOTP code

        Returns:
            True if valid
        """
        if not self.is_2fa_enabled or not self.totp_secret:
            return True  # 2FA not enabled

        if not PYOTP_AVAILABLE:
            return False

        # Check TOTP code
        totp = pyotp.TOTP(self.totp_secret)
        if totp.verify(code, valid_window=1):
            return True

        # Check backup codes
        if len(code) == 8:  # Backup codes are 8 chars
            code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
            backup_list = self.backup_codes.split(",")
            if code_hash in backup_list:
                # Remove used backup code
                backup_list.remove(code_hash)
                self.backup_codes = ",".join(backup_list)
                return True

        return False

    def enable_2fa(self):
        """Enable 2FA after successful verification."""
        if self.totp_secret:
            self.is_2fa_enabled = True

    def disable_2fa(self):
        """Disable 2FA."""
        self.is_2fa_enabled = False
        self.totp_secret = None
        self.backup_codes = ""

    def requires_2fa(self) -> bool:
        """Check if user requires 2FA (admins always require it per FR-D-16.3)."""
        return self.role == "admin" or self.is_2fa_enabled

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
            "is_2fa_enabled": self.is_2fa_enabled,
            "must_change_password": self.must_change_password,
            "password_changed_at": self.password_changed_at.isoformat() if self.password_changed_at else None,
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
