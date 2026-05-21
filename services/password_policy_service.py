# -*- coding: utf-8 -*-
"""
Password Policy Service - Single source of truth for password policy.

Fetches policy from backend (GET /api/v1/security-settings/current, anonymous)
at app startup. Applies a conservative fallback if the call fails so the user
is not blocked. The backend remains the authoritative validator on submit;
client-side validation only improves UX.
"""

import re
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

_FALLBACK_POLICY: Dict = {
    "minLength": 8,
    "requireUppercase": True,
    "requireLowercase": True,
    "requireDigit": True,
    "requireSpecialCharacter": True,
}

_policy_cache: Dict = dict(_FALLBACK_POLICY)
_initialized: bool = False


def initialize_password_policy():
    """Fetch policy once and cache. Falls back to conservative defaults on failure."""
    global _policy_cache, _initialized
    try:
        from services.api_client import get_api_client
        response = get_api_client().get_password_policy()
        policy = (response or {}).get("passwordPolicy") if isinstance(response, dict) else None
        if isinstance(policy, dict) and policy:
            _policy_cache = {
                "minLength": int(policy.get("minLength", _FALLBACK_POLICY["minLength"])),
                "requireUppercase": bool(policy.get("requireUppercase", True)),
                "requireLowercase": bool(policy.get("requireLowercase", True)),
                "requireDigit": bool(policy.get("requireDigit", True)),
                "requireSpecialCharacter": bool(policy.get("requireSpecialCharacter", True)),
            }
            logger.info(f"Password policy loaded: {_policy_cache}")
        else:
            logger.warning("passwordPolicy missing in response; applying fallback")
            _policy_cache = dict(_FALLBACK_POLICY)
    except Exception as e:
        logger.warning(f"Could not load password policy ({e}); applying fallback")
        _policy_cache = dict(_FALLBACK_POLICY)
    _initialized = True


def get_password_policy() -> Dict:
    return dict(_policy_cache)


def validate_password(pwd: str, current_pwd: Optional[str] = None) -> List[Dict]:
    """Return a list of {key, params} describing each rule violation.

    Empty list = valid. Keys are i18n keys for the dialog to display.
    """
    errors: List[Dict] = []
    p = _policy_cache

    min_len = p.get("minLength", 8)
    if len(pwd) < min_len:
        errors.append({"key": "dialog.password.policy.min_length", "params": {"n": min_len}})
    if p.get("requireUppercase") and not re.search(r"[A-Z]", pwd):
        errors.append({"key": "dialog.password.policy.uppercase", "params": {}})
    if p.get("requireLowercase") and not re.search(r"[a-z]", pwd):
        errors.append({"key": "dialog.password.policy.lowercase", "params": {}})
    if p.get("requireDigit") and not re.search(r"[0-9]", pwd):
        errors.append({"key": "dialog.password.policy.digit", "params": {}})
    if p.get("requireSpecialCharacter") and not re.search(r"[^a-zA-Z0-9]", pwd):
        errors.append({"key": "dialog.password.policy.special", "params": {}})
    if current_pwd is not None and pwd == current_pwd:
        errors.append({"key": "dialog.password.policy.same_as_current", "params": {}})

    return errors
