# -*- coding: utf-8 -*-
"""
TRRCMS Service Layer
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "AuthService",
    "ValidationService",
    "ImportService",
    "ExportService",
    "DashboardService",
    "UHCImporter",
    "MatchingService",
    "ConflictResolutionService",
    "SyncServer",
    # Data Provider abstraction layer
    "DataProvider",
    "DataProviderType",
    "ApiResponse",
    "QueryParams",
    "MockDataProvider",
    "HttpDataProvider",
    "LocalDbDataProvider",
    "DataProviderFactory",
    "get_data_provider",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "AuthService":
        from .auth_service import AuthService
        return AuthService
    elif name == "ValidationService":
        from .validation_service import ValidationService
        return ValidationService
    elif name == "ImportService":
        from .import_service import ImportService
        return ImportService
    elif name == "ExportService":
        from .export_service import ExportService
        return ExportService
    elif name == "DashboardService":
        from .dashboard_service import DashboardService
        return DashboardService
    elif name == "UHCImporter":
        from .uhc_importer import UHCImporter
        return UHCImporter
    elif name == "MatchingService":
        from .matching_service import MatchingService
        return MatchingService
    elif name == "ConflictResolutionService":
        from .conflict_resolution import ConflictResolutionService
        return ConflictResolutionService
    elif name == "SyncServer":
        from .sync_server import SyncServer
        return SyncServer
    # Data Provider classes
    elif name == "DataProvider":
        from .data_provider import DataProvider
        return DataProvider
    elif name == "DataProviderType":
        from .data_provider import DataProviderType
        return DataProviderType
    elif name == "ApiResponse":
        from .data_provider import ApiResponse
        return ApiResponse
    elif name == "QueryParams":
        from .data_provider import QueryParams
        return QueryParams
    elif name == "MockDataProvider":
        from .mock_data_provider import MockDataProvider
        return MockDataProvider
    elif name == "HttpDataProvider":
        from .http_data_provider import HttpDataProvider
        return HttpDataProvider
    elif name == "LocalDbDataProvider":
        from .local_db_data_provider import LocalDbDataProvider
        return LocalDbDataProvider
    elif name == "DataProviderFactory":
        from .data_provider_factory import DataProviderFactory
        return DataProviderFactory
    elif name == "get_data_provider":
        from .data_provider_factory import get_data_provider
        return get_data_provider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
