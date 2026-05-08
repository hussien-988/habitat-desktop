# -*- coding: utf-8 -*-
"""Deprecated stub.

All security policy enforcement (login lockout, password complexity,
session timeout) is now handled exclusively by the backend. The desktop
client submits requests and surfaces backend error responses to the user.

This file is kept only so that legacy `from services.security_service import ...`
imports don't break. New code should not use it.
"""

from utils.logger import get_logger

logger = get_logger(__name__)
