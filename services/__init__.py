# -*- coding: utf-8 -*-
"""
TRRCMS Service Layer
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "AuthService",
    "ValidationService",
    "ExportService",
    "DashboardService",
    "SyncServer",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "AuthService":
        from .auth_service import AuthService
        return AuthService
    elif name == "ValidationService":
        from .validation_service import ValidationService
        return ValidationService
    elif name == "ExportService":
        from .export_service import ExportService
        return ExportService
    elif name == "DashboardService":
        from .dashboard_service import DashboardService
        return DashboardService
    elif name == "SyncServer":
        from .sync_server import SyncServer
        return SyncServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
