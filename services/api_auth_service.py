# -*- coding: utf-8 -*-
"""
API Authentication Service - connects to REST API for login.

Replaces the local DB-based AuthService with calls to the
remote backend at Config.API_BASE_URL + /Auth/login
"""

import json
import ssl
import urllib.request
import urllib.error
from typing import Optional, Tuple

from models.user import User
from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class ApiAuthService:
    """Authentication service that delegates to the REST API."""

    def __init__(self):
        self.base_url = Config.API_BASE_URL.rstrip("/")
        self.login_url = f"{self.base_url}/v1/Auth/login"
        self.timeout = Config.API_TIMEOUT

        # SSL context that skips verification for localhost self-signed certs
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def authenticate(self, username: str, password: str) -> Tuple[Optional[User], str]:
        """
        Authenticate a user against the REST API.

        POST /Auth/login
        Body: {"username": "...", "password": "..."}

        Expected success response (200):
            {
                "user_id": "...",
                "username": "...",
                "full_name": "...",
                "full_name_ar": "...",
                "role": "...",
                "email": "...",
                "is_active": true,
                "token": "..."   // optional JWT token
            }

        Returns:
            Tuple of (User or None, error_message)
        """
        if not username or not password:
            return None, "يرجى إدخال اسم المستخدم وكلمة المرور"

        payload = json.dumps({
            "username": username,
            "password": password
        }).encode("utf-8")

        req = urllib.request.Request(
            self.login_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_ctx) as resp:
                body = resp.read().decode("utf-8")
                data = json.loads(body)

            logger.info(f"API login successful for: {username}")
            logger.debug(f"API login response keys: {list(data.keys())}")
            user = self._build_user(data)
            logger.debug(f"User token set: {bool(user._api_token)}")
            return user, ""

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            logger.warning(f"API login failed ({e.code}) for {username}: {body}")

            if e.code == 401:
                return None, "اسم المستخدم أو كلمة المرور غير صحيحة"
            if e.code == 403:
                return None, "الحساب مغلق. يرجى التواصل مع المدير."
            if e.code == 429:
                return None, "عدد المحاولات تجاوز الحد المسموح. حاول لاحقًا."
            return None, f"خطأ من الخدمة ({e.code})"

        except urllib.error.URLError as e:
            logger.error(f"Cannot connect to API at {self.login_url}: {e.reason}")
            return None, "لا يمكن الاتصال بالخدمة. تحقق من الاتصال بالشبكة."

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Invalid API response: {e}")
            return None, "استجابة غير صالحة من الخدمة."

        except Exception as e:
            logger.error(f"Unexpected error during API login: {e}")
            return None, "حدث خطأ غير متوقع."

    @staticmethod
    def _build_user(data: dict) -> User:
        """Build a User model from the API response JSON."""
        user = User()
        user.user_id = data.get("user_id") or data.get("userId") or data.get("id") or ""
        user.username = data.get("username") or data.get("userName") or ""
        user.full_name = data.get("full_name") or data.get("fullName") or ""
        user.full_name_ar = data.get("full_name_ar") or data.get("fullNameAr") or ""
        user.role = data.get("role") or "analyst"
        user.email = data.get("email")
        user.is_active = data.get("is_active", data.get("isActive", True))
        user.is_locked = data.get("is_locked", data.get("isLocked", False))

        # Store token if provided (handle various field names)
        # Common token field names: token, accessToken, access_token, jwtToken, jwt
        token = (
            data.get("token") or
            data.get("accessToken") or
            data.get("access_token") or
            data.get("jwtToken") or
            data.get("jwt") or
            data.get("bearerToken") or
            data.get("authToken")
        )
        if token:
            user._api_token = token
            logger.info(f"API token received for user: {user.username}")

        return user
