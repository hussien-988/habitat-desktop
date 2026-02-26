# -*- coding: utf-8 -*-
"""
User Controller
===============
Controller for user management operations via backend API.
No local SQLite usage — all operations go through the API.
"""

from typing import Any, Dict, List, Optional

from controllers.base_controller import BaseController, OperationResult
from services.api_client import get_api_client
from utils.logger import get_logger

logger = get_logger(__name__)


class UserController(BaseController):
    """Controller for user management via backend API."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def set_auth_token(self, token: str):
        """Set API auth token."""
        api = get_api_client()
        if api:
            api.set_access_token(token)

    def get_all_users(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> OperationResult:
        try:
            response = get_api_client().get_all_users(role=role, is_active=is_active)
            items = response.get("items", response if isinstance(response, list) else [])
            return OperationResult.ok(data=items)
        except Exception as e:
            logger.error(f"get_all_users failed: {e}")
            return OperationResult.fail(str(e))

    def get_user(self, user_id: str) -> OperationResult:
        try:
            data = get_api_client().get_user(user_id)
            return OperationResult.ok(data=data)
        except Exception as e:
            logger.error(f"get_user({user_id}) failed: {e}")
            return OperationResult.fail(str(e))

    def create_user(self, data: Dict[str, Any]) -> OperationResult:
        try:
            result = get_api_client().create_user(data)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"create_user failed: {e}")
            return OperationResult.fail(str(e))

    def update_user(self, user_id: str, data: Dict[str, Any]) -> OperationResult:
        try:
            result = get_api_client().update_user(user_id, data)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"update_user({user_id}) failed: {e}")
            return OperationResult.fail(str(e))

    def delete_user(self, user_id: str) -> OperationResult:
        try:
            get_api_client().delete_user(user_id)
            return OperationResult.ok()
        except Exception as e:
            logger.error(f"delete_user({user_id}) failed: {e}")
            return OperationResult.fail(str(e))

    def activate_user(self, user_id: str) -> OperationResult:
        try:
            result = get_api_client().activate_user(user_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"activate_user({user_id}) failed: {e}")
            return OperationResult.fail(str(e))

    def deactivate_user(self, user_id: str) -> OperationResult:
        try:
            result = get_api_client().deactivate_user(user_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"deactivate_user({user_id}) failed: {e}")
            return OperationResult.fail(str(e))

    def unlock_user(self, user_id: str) -> OperationResult:
        try:
            result = get_api_client().unlock_user(user_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"unlock_user({user_id}) failed: {e}")
            return OperationResult.fail(str(e))

    def admin_change_user_password(self, user_id: str, new_password: str) -> OperationResult:
        try:
            get_api_client().admin_change_user_password(user_id, new_password)
            return OperationResult.ok()
        except Exception as e:
            logger.error(f"admin_change_user_password({user_id}) failed: {e}")
            return OperationResult.fail(str(e))
