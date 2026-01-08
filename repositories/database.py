# -*- coding: utf-8 -*-
"""
Database compatibility layer.

This module provides backward compatibility with existing code that imports from
repositories.database. All database operations are now delegated to the unified
db_adapter module.

For new code, use: from repositories.db_adapter import get_database, DatabaseFactory
"""

from pathlib import Path
from typing import Optional, List, Any
from contextlib import contextmanager

from repositories.db_adapter import (
    DatabaseAdapter,
    DatabaseFactory,
    DatabaseConfig,
    DatabaseType,
    SQLiteAdapter,
    RowProxy,
    get_database as _get_database
)
from utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """
    Backward-compatible Database class.

    Wraps the new DatabaseAdapter to maintain compatibility with existing code.
    New code should use DatabaseFactory.create() or get_database() directly.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database.

        Args:
            db_path: Optional path for SQLite database. If provided, forces SQLite mode.
        """
        if db_path is not None:
            # Force SQLite mode with specific path
            self._adapter = SQLiteAdapter(db_path)
            self._adapter.connect()
        else:
            # Use factory (respects TRRCMS_DB_TYPE env var)
            self._adapter = DatabaseFactory.create()

    @property
    def db_path(self) -> Optional[Path]:
        """Get database path (SQLite only)."""
        if isinstance(self._adapter, SQLiteAdapter):
            return self._adapter.db_path
        return None

    @property
    def db_type(self) -> DatabaseType:
        """Get database type."""
        return self._adapter.db_type

    def initialize(self) -> None:
        """Initialize database schema."""
        self._adapter.initialize()

    def get_connection(self):
        """
        Get database connection.

        For SQLite, returns the sqlite3 connection.
        For PostgreSQL, returns a connection from the pool.

        Note: New code should use cursor() context manager instead.
        """
        if isinstance(self._adapter, SQLiteAdapter):
            return self._adapter._get_connection()
        else:
            # For PostgreSQL, return connection from pool
            return self._adapter._get_connection()

    @property
    def connection(self):
        """Alias for get_connection()."""
        return self.get_connection()

    @contextmanager
    def cursor(self):
        """
        Context manager for database cursor.

        Usage:
            with db.cursor() as cursor:
                cursor.execute("SELECT ...")
        """
        with self._adapter.cursor() as cursor:
            yield cursor

    @contextmanager
    def transaction(self):
        """
        Transaction context manager.

        Usage:
            with db.transaction() as conn:
                # Operations auto-commit on success, rollback on error
        """
        with self._adapter.transaction() as conn:
            yield conn

    def execute(self, query: str, params: tuple = ()) -> Any:
        """
        Execute a query and return results.

        Args:
            query: SQL query (can use ? placeholders for both SQLite and PostgreSQL)
            params: Query parameters

        Returns:
            List of RowProxy objects for SELECT queries,
            or a cursor-like object for compatibility
        """
        return self._adapter.execute(query, params)

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[RowProxy]:
        """
        Execute query and fetch single row.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            RowProxy or None
        """
        return self._adapter.fetch_one(query, params)

    def fetch_all(self, query: str, params: tuple = ()) -> List[RowProxy]:
        """
        Execute query and fetch all rows.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of RowProxy objects
        """
        return self._adapter.fetch_all(query, params)

    def close(self) -> None:
        """Close database connection."""
        self._adapter.close()

    def is_empty(self) -> bool:
        """Check if database has no data."""
        result = self.fetch_one("SELECT COUNT(*) as count FROM buildings")
        return result["count"] == 0 if result else True

    def commit(self) -> None:
        """Commit current transaction (for compatibility)."""
        # The adapter auto-commits, but provide this for compatibility
        if isinstance(self._adapter, SQLiteAdapter):
            conn = self._adapter._get_connection()
            conn.commit()


# Convenience functions for backward compatibility
def get_database() -> Database:
    """Get a Database instance."""
    return Database()
