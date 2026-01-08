# -*- coding: utf-8 -*-
"""
Database Factory - Backward compatibility module.

This module re-exports from db_adapter for backward compatibility.
New code should import directly from repositories.db_adapter.
"""

# Re-export everything from db_adapter for backward compatibility
from repositories.db_adapter import (
    DatabaseType,
    DatabaseConfig,
    DatabaseAdapter,
    SQLiteAdapter,
    PostgreSQLAdapter,
    DatabaseFactory,
    RowProxy,
    get_database,
)

# Legacy alias
DatabaseAdapter_Legacy = DatabaseAdapter

__all__ = [
    'DatabaseType',
    'DatabaseConfig',
    'DatabaseAdapter',
    'SQLiteAdapter',
    'PostgreSQLAdapter',
    'DatabaseFactory',
    'RowProxy',
    'get_database',
]
