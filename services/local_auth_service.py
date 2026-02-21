# -*- coding: utf-8 -*-
"""
Local Authentication Service — مصادقة محلية من SQLite.
Used in Demo/offline mode when no API backend is available.
"""

from typing import Optional, Tuple

from models.user import User
from utils.logger import get_logger

logger = get_logger(__name__)


class LocalAuthService:
    """Authentication service that checks credentials against local SQLite DB."""

    def __init__(self, db):
        self.db = db

    def authenticate(self, username: str, password: str) -> Tuple[Optional[User], str]:
        if not username or not password:
            return None, "يرجى إدخال اسم المستخدم وكلمة المرور"

        try:
            row = self.db.fetch_one(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            )
        except Exception as e:
            logger.error(f"Local auth DB error: {e}")
            return None, "خطأ في قاعدة البيانات المحلية"

        if not row:
            return None, "اسم المستخدم أو كلمة المرور غير صحيحة"

        user = User()
        user.user_id = row.get("user_id", "")
        user.username = row.get("username", "")
        user.full_name = row.get("full_name", "")
        user.full_name_ar = row.get("full_name_ar", "")
        user.role = row.get("role", "analyst")
        user.email = row.get("email")
        user.is_active = row.get("is_active", True)
        user.is_locked = row.get("is_locked", False)
        user.password_hash = row.get("password_hash", "")
        user.password_salt = row.get("password_salt", "")

        if user.is_locked:
            return None, "الحساب مغلق. يرجى التواصل مع المدير."

        # Data collectors cannot log in to the desktop application
        from app.config import Roles
        if user.role in Roles.NON_LOGIN_ROLES:
            return None, "جامعو البيانات لا يمكنهم الدخول لتطبيق سطح المكتب"

        if not user.check_password(password):
            return None, "اسم المستخدم أو كلمة المرور غير صحيحة"

        logger.info(f"Local auth successful for: {username}")
        return user, ""
