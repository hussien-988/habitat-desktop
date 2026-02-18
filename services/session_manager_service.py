# -*- coding: utf-8 -*-
"""
Session Manager Service - UC-011 Security Settings Enforcement.
Implements session timeout, auto-logout, and security policy enforcement.
"""

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SecurityPolicy:
    """Security policy configuration (UC-011)."""
    # Password policies (S03)
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digits: bool = True
    password_require_symbols: bool = False
    password_expiry_days: int = 90
    password_reuse_history: int = 5

    # Session policies (S04)
    session_timeout_minutes: int = 30
    max_failed_login_attempts: int = 5
    account_lockout_duration_minutes: int = 30

    # Access control (S05)
    allowed_auth_methods: List[str] = field(default_factory=lambda: ["password"])
    ip_whitelist: List[str] = field(default_factory=list)
    ip_blacklist: List[str] = field(default_factory=list)
    require_2fa_for_admin: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> 'SecurityPolicy':
        """Create from dictionary."""
        return cls(
            password_min_length=data.get("password_min_length", 8),
            password_require_uppercase=data.get("password_require_uppercase", True),
            password_require_lowercase=data.get("password_require_lowercase", True),
            password_require_digits=data.get("password_require_digits", True),
            password_require_symbols=data.get("password_require_symbols", False),
            password_expiry_days=data.get("password_expiry_days", 90),
            password_reuse_history=data.get("password_reuse_history", 5),
            session_timeout_minutes=data.get("session_timeout_minutes", 30),
            max_failed_login_attempts=data.get("max_failed_login_attempts", 5),
            account_lockout_duration_minutes=data.get("account_lockout_duration_minutes", 30),
            allowed_auth_methods=data.get("allowed_auth_methods", ["password"]),
            ip_whitelist=data.get("ip_whitelist", []),
            ip_blacklist=data.get("ip_blacklist", []),
            require_2fa_for_admin=data.get("require_2fa_for_admin", False)
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "password_min_length": self.password_min_length,
            "password_require_uppercase": self.password_require_uppercase,
            "password_require_lowercase": self.password_require_lowercase,
            "password_require_digits": self.password_require_digits,
            "password_require_symbols": self.password_require_symbols,
            "password_expiry_days": self.password_expiry_days,
            "password_reuse_history": self.password_reuse_history,
            "session_timeout_minutes": self.session_timeout_minutes,
            "max_failed_login_attempts": self.max_failed_login_attempts,
            "account_lockout_duration_minutes": self.account_lockout_duration_minutes,
            "allowed_auth_methods": self.allowed_auth_methods,
            "ip_whitelist": self.ip_whitelist,
            "ip_blacklist": self.ip_blacklist,
            "require_2fa_for_admin": self.require_2fa_for_admin
        }


@dataclass
class UserSession:
    """Active user session."""
    session_id: str
    user_id: str
    username: str
    role: str
    login_time: datetime
    last_activity: datetime
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    is_active: bool = True


@dataclass
class LoginAttempt:
    """Track login attempts for lockout."""
    user_id: str
    attempts: int = 0
    last_attempt: datetime = None
    locked_until: datetime = None


class SessionManagerService(QObject):
    """
    Session manager with security policy enforcement.

    Implements UC-011:
    - S03: Password policies
    - S04: Session timeout and lockout
    - S05: Access control policies
    - S08: Policy enforcement

    Signals:
        session_timeout: Emitted when session times out
        session_warning: Emitted before timeout (1 minute warning)
        user_locked_out: Emitted when user is locked out
        password_expiring: Emitted when password is about to expire
    """

    session_timeout = pyqtSignal()
    session_warning = pyqtSignal(int)  # seconds remaining
    user_locked_out = pyqtSignal(str, int)  # username, minutes locked
    password_expiring = pyqtSignal(int)  # days remaining
    activity_detected = pyqtSignal()

    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.policy = self._load_security_policy()
        self.current_session: Optional[UserSession] = None
        self.login_attempts: Dict[str, LoginAttempt] = {}

        # Activity monitoring
        self._activity_timer = QTimer(self)
        self._activity_timer.timeout.connect(self._check_session_timeout)
        self._warning_shown = False
        self._last_activity = datetime.now()

        # Install global event filter for activity detection
        self._event_filter = ActivityEventFilter(self)

    def _load_security_policy(self) -> SecurityPolicy:
        """Load security policy from database."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT policy_data FROM security_policies
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return SecurityPolicy.from_dict(json.loads(row[0]))
        except Exception as e:
            logger.warning(f"Could not load security policy: {e}")

        return SecurityPolicy()

    def save_security_policy(self, policy: SecurityPolicy, user_id: str) -> bool:
        """
        Save security policy to database.

        Implements UC-011 S07: Apply Security Policy
        """
        try:
            # Validate policy first
            is_valid, errors = self._validate_policy(policy)
            if not is_valid:
                logger.error(f"Policy validation failed: {errors}")
                return False

            cursor = self.db.cursor()

            # Deactivate existing policies
            cursor.execute("UPDATE security_policies SET is_active = 0")

            # Insert new policy
            policy_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO security_policies (
                    policy_id, policy_data, is_active, created_at, created_by
                ) VALUES (?, ?, 1, ?, ?)
            """, (
                policy_id,
                json.dumps(policy.to_dict()),
                datetime.now().isoformat(),
                user_id
            ))

            # Log audit
            cursor.execute("""
                INSERT INTO audit_log (
                    event_id, timestamp, user_id, action, entity, entity_id, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                datetime.now().isoformat(),
                user_id,
                "UPDATE_SECURITY_POLICY",
                "security_policy",
                policy_id,
                json.dumps({"policy": policy.to_dict()})
            ))

            self.db.commit()
            self.policy = policy

            logger.info(f"Security policy updated by {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save security policy: {e}", exc_info=True)
            return False

    def _validate_policy(self, policy: SecurityPolicy) -> tuple:
        """
        Validate security policy configuration.

        Implements UC-011 S06: Validate Security Policy Configuration
        """
        errors = []

        # Password policy validation
        if policy.password_min_length < 6:
            errors.append("الحد الأدنى لطول كلمة المرور يجب أن يكون 6 على الأقل")

        if policy.password_expiry_days < 1:
            errors.append("فترة انتهاء كلمة المرور يجب أن تكون يوم واحد على الأقل")

        # Session policy validation
        if policy.session_timeout_minutes < 1:
            errors.append("مهلة الجلسة يجب أن تكون دقيقة واحدة على الأقل")

        if policy.session_timeout_minutes > 1440:  # 24 hours
            errors.append("مهلة الجلسة يجب أن لا تتجاوز 24 ساعة")

        if policy.max_failed_login_attempts < 1:
            errors.append("عدد محاولات تسجيل الدخول يجب أن يكون 1 على الأقل")

        if policy.account_lockout_duration_minutes < 1:
            errors.append("مدة قفل الحساب يجب أن تكون دقيقة واحدة على الأقل")

        return len(errors) == 0, errors

    def validate_password(self, password: str) -> tuple:
        """
        Validate password against security policy.

        Implements UC-011 S03: Password Policies
        """
        errors = []

        if len(password) < self.policy.password_min_length:
            errors.append(f"كلمة المرور يجب أن تكون {self.policy.password_min_length} أحرف على الأقل")

        if self.policy.password_require_uppercase and not any(c.isupper() for c in password):
            errors.append("كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل")

        if self.policy.password_require_lowercase and not any(c.islower() for c in password):
            errors.append("كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل")

        if self.policy.password_require_digits and not any(c.isdigit() for c in password):
            errors.append("كلمة المرور يجب أن تحتوي على رقم واحد على الأقل")

        if self.policy.password_require_symbols:
            symbols = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
            if not any(c in symbols for c in password):
                errors.append("كلمة المرور يجب أن تحتوي على رمز خاص واحد على الأقل")

        return len(errors) == 0, errors

    def check_password_reuse(self, user_id: str, new_password_hash: str) -> bool:
        """Check if password was recently used."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT password_hash FROM password_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, self.policy.password_reuse_history))

            for row in cursor.fetchall():
                if row[0] == new_password_hash:
                    return False  # Password was recently used

            return True

        except Exception:
            return True

    def check_password_expiry(self, user_id: str) -> Optional[int]:
        """
        Check if user's password is expiring.

        Returns days until expiry, or None if not expiring soon.
        """
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT password_changed_at FROM users WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            if row and row[0]:
                changed_at = datetime.fromisoformat(row[0])
                expiry_date = changed_at + timedelta(days=self.policy.password_expiry_days)
                days_remaining = (expiry_date - datetime.now()).days

                if days_remaining <= 14:  # Warn 14 days before expiry
                    return days_remaining

            return None

        except Exception as e:
            logger.warning(f"Could not check password expiry: {e}")
            return None

    def login(
        self,
        username: str,
        password: str,
        ip_address: str = None
    ) -> tuple:
        """
        Authenticate user with security policy enforcement.

        Implements:
        - UC-011 S04: Max failed login attempts and lockout
        - UC-011 S05: IP restrictions

        Returns:
            (success, user_data or error_message)
        """
        # Check IP restrictions
        if ip_address:
            if self.policy.ip_blacklist and ip_address in self.policy.ip_blacklist:
                self._log_security_event("LOGIN_BLOCKED_IP", username, {"ip": ip_address})
                return False, "الوصول مرفوض من هذا العنوان"

            if self.policy.ip_whitelist and ip_address not in self.policy.ip_whitelist:
                self._log_security_event("LOGIN_BLOCKED_IP", username, {"ip": ip_address})
                return False, "الوصول مرفوض من هذا العنوان"

        # Check if user is locked out
        attempt = self.login_attempts.get(username)
        if attempt and attempt.locked_until:
            if datetime.now() < attempt.locked_until:
                remaining = int((attempt.locked_until - datetime.now()).total_seconds() / 60)
                return False, f"الحساب مقفل. يرجى المحاولة بعد {remaining} دقيقة"
            else:
                # Lockout expired, reset
                attempt.locked_until = None
                attempt.attempts = 0

        # Authenticate
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT user_id, password_hash, role, is_active,
                       password_changed_at
                FROM users
                WHERE username = ?
            """, (username,))

            row = cursor.fetchone()
            if not row:
                self._record_failed_login(username)
                return False, "اسم المستخدم أو كلمة المرور غير صحيحة"

            user_id, password_hash, role, is_active, password_changed_at = row

            if not is_active:
                return False, "الحساب معطل"

            # Verify password
            computed_hash = hashlib.sha256(password.encode()).hexdigest()
            if computed_hash != password_hash:
                self._record_failed_login(username)
                return False, "اسم المستخدم أو كلمة المرور غير صحيحة"

            # Clear failed attempts on successful login
            if username in self.login_attempts:
                del self.login_attempts[username]

            # Check password expiry
            days_until_expiry = self.check_password_expiry(user_id)
            if days_until_expiry is not None and days_until_expiry <= 0:
                return False, "انتهت صلاحية كلمة المرور. يرجى تغييرها"

            # Create session
            session = UserSession(
                session_id=str(uuid.uuid4()),
                user_id=user_id,
                username=username,
                role=role,
                login_time=datetime.now(),
                last_activity=datetime.now(),
                ip_address=ip_address
            )

            self.current_session = session
            self._last_activity = datetime.now()
            self._warning_shown = False

            # Start session monitoring
            self._start_session_monitoring()

            # Log login
            self._log_security_event("LOGIN_SUCCESS", username, {"session_id": session.session_id})

            # Update last login
            cursor.execute("""
                UPDATE users SET last_login = ? WHERE user_id = ?
            """, (datetime.now().isoformat(), user_id))
            self.db.commit()

            # Emit password expiry warning if needed
            if days_until_expiry is not None and days_until_expiry > 0:
                self.password_expiring.emit(days_until_expiry)

            return True, {
                "user_id": user_id,
                "username": username,
                "role": role,
                "session_id": session.session_id
            }

        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            return False, "حدث خطأ أثناء تسجيل الدخول"

    def _record_failed_login(self, username: str):
        """Record failed login attempt and check for lockout."""
        attempt = self.login_attempts.get(username)
        if not attempt:
            attempt = LoginAttempt(user_id=username)
            self.login_attempts[username] = attempt

        attempt.attempts += 1
        attempt.last_attempt = datetime.now()

        # Check if should lock out
        if attempt.attempts >= self.policy.max_failed_login_attempts:
            attempt.locked_until = datetime.now() + timedelta(
                minutes=self.policy.account_lockout_duration_minutes
            )
            self._log_security_event("ACCOUNT_LOCKED", username, {
                "attempts": attempt.attempts,
                "locked_minutes": self.policy.account_lockout_duration_minutes
            })
            self.user_locked_out.emit(username, self.policy.account_lockout_duration_minutes)
        else:
            self._log_security_event("LOGIN_FAILED", username, {"attempts": attempt.attempts})

    def logout(self):
        """Log out current user."""
        if self.current_session:
            self._log_security_event(
                "LOGOUT",
                self.current_session.username,
                {"session_id": self.current_session.session_id}
            )
            self.current_session = None

        self._activity_timer.stop()

    def record_activity(self):
        """Record user activity to reset timeout."""
        self._last_activity = datetime.now()
        self._warning_shown = False

        if self.current_session:
            self.current_session.last_activity = datetime.now()

        self.activity_detected.emit()

    def _start_session_monitoring(self):
        """Start monitoring session for timeout."""
        # Check every 10 seconds
        self._activity_timer.start(10000)

    def _check_session_timeout(self):
        """
        Check if session has timed out.

        Implements UC-011 S04: Session timeout enforcement
        """
        if not self.current_session:
            return

        timeout_seconds = self.policy.session_timeout_minutes * 60
        elapsed = (datetime.now() - self._last_activity).total_seconds()
        remaining = timeout_seconds - elapsed

        # Warning 60 seconds before timeout
        if remaining <= 60 and remaining > 0 and not self._warning_shown:
            self._warning_shown = True
            self.session_warning.emit(int(remaining))
            logger.info(f"Session timeout warning: {int(remaining)} seconds remaining")

        # Timeout
        if remaining <= 0:
            logger.info("Session timed out due to inactivity")
            self._log_security_event(
                "SESSION_TIMEOUT",
                self.current_session.username,
                {"session_id": self.current_session.session_id}
            )
            self.session_timeout.emit()
            self.logout()

    def extend_session(self):
        """Extend session after warning."""
        self.record_activity()
        logger.info("Session extended by user")

    def _log_security_event(self, event_type: str, username: str, details: Dict):
        """Log security event to audit trail."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO security_log (
                    event_id, event_type, username, timestamp, details, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                event_type,
                username,
                datetime.now().isoformat(),
                json.dumps(details),
                self.current_session.ip_address if self.current_session else None
            ))
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not log security event: {e}")

    def get_active_sessions(self) -> List[Dict]:
        """Get all active sessions (for admin view)."""
        # In a full implementation, this would track multiple sessions
        if self.current_session:
            return [{
                "session_id": self.current_session.session_id,
                "user_id": self.current_session.user_id,
                "username": self.current_session.username,
                "role": self.current_session.role,
                "login_time": self.current_session.login_time.isoformat(),
                "last_activity": self.current_session.last_activity.isoformat(),
                "ip_address": self.current_session.ip_address
            }]
        return []

    def force_logout_user(self, user_id: str, reason: str = None):
        """Force logout a specific user (admin function)."""
        if self.current_session and self.current_session.user_id == user_id:
            self._log_security_event(
                "FORCED_LOGOUT",
                self.current_session.username,
                {"reason": reason}
            )
            self.session_timeout.emit()
            self.logout()

    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> tuple:
        """
        Change user password with policy enforcement.

        Returns:
            (success, message)
        """
        # Validate new password against policy
        is_valid, errors = self.validate_password(new_password)
        if not is_valid:
            return False, errors[0]

        try:
            cursor = self.db.cursor()

            # Verify old password
            cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return False, "المستخدم غير موجود"

            old_hash = hashlib.sha256(old_password.encode()).hexdigest()
            if old_hash != row[0]:
                return False, "كلمة المرور الحالية غير صحيحة"

            # Check password reuse
            new_hash = hashlib.sha256(new_password.encode()).hexdigest()
            if not self.check_password_reuse(user_id, new_hash):
                return False, f"لا يمكن استخدام كلمة مرور تم استخدامها في آخر {self.policy.password_reuse_history} مرات"

            # Update password
            cursor.execute("""
                UPDATE users
                SET password_hash = ?, password_changed_at = ?
                WHERE user_id = ?
            """, (new_hash, datetime.now().isoformat(), user_id))

            # Add to password history
            cursor.execute("""
                INSERT INTO password_history (user_id, password_hash, created_at)
                VALUES (?, ?, ?)
            """, (user_id, new_hash, datetime.now().isoformat()))

            self.db.commit()

            self._log_security_event("PASSWORD_CHANGED", user_id, {})
            return True, "تم تغيير كلمة المرور بنجاح"

        except Exception as e:
            logger.error(f"Password change error: {e}", exc_info=True)
            return False, "حدث خطأ أثناء تغيير كلمة المرور"


class ActivityEventFilter(QObject):
    """
    Event filter to detect user activity.

    Monitors mouse and keyboard events to reset session timeout.
    """

    def __init__(self, session_manager: SessionManagerService):
        super().__init__()
        self.session_manager = session_manager

        # Install on application
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events to detect activity."""
        from PyQt5.QtCore import QEvent

        # Detect mouse and keyboard activity
        if event.type() in [
            QEvent.MouseButtonPress,
            QEvent.MouseMove,
            QEvent.KeyPress,
            QEvent.Wheel
        ]:
            self.session_manager.record_activity()

        return False  # Don't filter the event


class SessionTimeoutDialog(QMessageBox):
    """Dialog shown before session timeout."""

    def __init__(self, seconds_remaining: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تحذير انتهاء الجلسة")
        self.setText(f"ستنتهي جلستك خلال {seconds_remaining} ثانية بسبب عدم النشاط.")
        self.setInformativeText("هل تريد تمديد الجلسة؟")
        self.setIcon(QMessageBox.Warning)
        self.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.setDefaultButton(QMessageBox.Yes)

        # Arabic button text
        self.button(QMessageBox.Yes).setText("نعم، تمديد الجلسة")
        self.button(QMessageBox.No).setText("لا، تسجيل الخروج")

        # Auto-close timer
        self.remaining = seconds_remaining
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_countdown)
        self.timer.start(1000)

    def _update_countdown(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.timer.stop()
            self.reject()
        else:
            self.setText(f"ستنتهي جلستك خلال {self.remaining} ثانية بسبب عدم النشاط.")
