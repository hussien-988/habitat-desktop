# -*- coding: utf-8 -*-
"""
TRRCMS Repository Layer
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "Database",
    "PostgresDatabase",
    "DatabaseFactory",
    "BuildingRepository",
    "UnitRepository",
    "PersonRepository",
    "ClaimRepository",
    "UserRepository",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "Database":
        from .database import Database
        return Database
    elif name == "PostgresDatabase":
        from .postgres_database import PostgresDatabase
        return PostgresDatabase
    elif name == "DatabaseFactory":
        from .db_factory import DatabaseFactory
        return DatabaseFactory
    elif name == "BuildingRepository":
        from .building_repository import BuildingRepository
        return BuildingRepository
    elif name == "UnitRepository":
        from .unit_repository import UnitRepository
        return UnitRepository
    elif name == "PersonRepository":
        from .person_repository import PersonRepository
        return PersonRepository
    elif name == "ClaimRepository":
        from .claim_repository import ClaimRepository
        return ClaimRepository
    elif name == "UserRepository":
        from .user_repository import UserRepository
        return UserRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
