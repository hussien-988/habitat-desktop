# -*- coding: utf-8 -*-
"""
Unified Database Adapter - Backend-agnostic database abstraction layer.

Implements FSD 5.2: Central DB is PostgreSQL 16 with PostGIS extension.
Provides a consistent interface for both SQLite (development/fallback) and PostgreSQL (production).

This module is the ONLY place that should import sqlite3 or psycopg2 for the main database.
(.uhc container parsing is exempt as .uhc files are SQLite format by design)
"""

import os
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseType(Enum):
    """Supported database backends."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    db_type: DatabaseType = DatabaseType.POSTGRESQL  # Default to PostgreSQL
    # PostgreSQL settings
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "trrcms"
    pg_user: str = "trrcms_user"
    pg_password: str = ""
    pg_pool_min: int = 2
    pg_pool_max: int = 10
    # SQLite settings (fallback)
    sqlite_path: Optional[Path] = None

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Load configuration from environment variables."""
        db_type_str = os.getenv("TRRCMS_DB_TYPE", "postgresql").lower()
        db_type = DatabaseType.POSTGRESQL if db_type_str == "postgresql" else DatabaseType.SQLITE

        return cls(
            db_type=db_type,
            pg_host=os.getenv("TRRCMS_DB_HOST", "localhost"),
            pg_port=int(os.getenv("TRRCMS_DB_PORT", "5432")),
            pg_database=os.getenv("TRRCMS_DB_NAME", "trrcms"),
            pg_user=os.getenv("TRRCMS_DB_USER", "trrcms_user"),
            pg_password=os.getenv("TRRCMS_DB_PASSWORD", ""),
            pg_pool_min=int(os.getenv("TRRCMS_DB_POOL_MIN", "2")),
            pg_pool_max=int(os.getenv("TRRCMS_DB_POOL_MAX", "10")),
            sqlite_path=Path(os.getenv("TRRCMS_SQLITE_PATH", "")) if os.getenv("TRRCMS_SQLITE_PATH") else None
        )


class RowProxy:
    """
    A dict-like row proxy that supports both dict access and attribute access.
    Provides consistent interface regardless of backend.
    """

    def __init__(self, data: Dict[str, Any], columns: Optional[List[str]] = None):
        self._data = data
        self._columns = columns or list(data.keys())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._columns[key]]
        return self._data[key]

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data.values())

    def __len__(self):
        return len(self._data)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def __repr__(self):
        return f"RowProxy({self._data})"


class DatabaseAdapter(ABC):
    """
    Abstract base class for database adapters.
    Defines the interface that all database backends must implement.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish database connection."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if database is connected."""
        pass

    @abstractmethod
    def execute(self, query: str, params: Optional[Tuple] = None) -> List[RowProxy]:
        """Execute a query and return results."""
        pass

    @abstractmethod
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        pass

    @abstractmethod
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[RowProxy]:
        """Execute query and fetch single row."""
        pass

    @abstractmethod
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[RowProxy]:
        """Execute query and fetch all rows."""
        pass

    @abstractmethod
    @contextmanager
    def cursor(self) -> Iterator[Any]:
        """Get a cursor context manager."""
        pass

    @abstractmethod
    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Transaction context manager with auto-commit/rollback."""
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize database schema."""
        pass

    @property
    @abstractmethod
    def db_type(self) -> DatabaseType:
        """Return the database type."""
        pass


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize SQLite adapter."""
        # Import sqlite3 only here
        import sqlite3 as _sqlite3
        self._sqlite3 = _sqlite3

        if db_path is None:
            from app.config import Config
            db_path = Config.DB_PATH

        self._db_path = db_path
        self._connection = None

        # Ensure directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_type(self) -> DatabaseType:
        return DatabaseType.SQLITE

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        return self._db_path

    def connect(self) -> bool:
        """Establish SQLite connection."""
        try:
            if self._connection is None:
                self._connection = self._sqlite3.connect(
                    str(self._db_path),
                    check_same_thread=False,
                    detect_types=self._sqlite3.PARSE_DECLTYPES
                )
                # Use dict-like row factory
                self._connection.row_factory = self._dict_factory
                # Enable foreign keys
                self._connection.execute("PRAGMA foreign_keys = ON")
            return True
        except Exception as e:
            logger.error(f"SQLite connection error: {e}")
            return False

    def _dict_factory(self, cursor, row):
        """Convert row to dictionary."""
        columns = [col[0] for col in cursor.description]
        return {col: row[idx] for idx, col in enumerate(columns)}

    def close(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("SQLite connection closed")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connection is not None

    def _get_connection(self):
        """Get connection, connecting if needed."""
        if not self._connection:
            self.connect()
        return self._connection

    def execute(self, query: str, params: Optional[Tuple] = None) -> List[RowProxy]:
        """Execute query and return results."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            conn.commit()

            if cursor.description:
                columns = [col[0] for col in cursor.description]
                return [RowProxy(row, columns) for row in cursor.fetchall()]
            return []
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite execute error: {e}\nQuery: {query}")
            raise

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute query with multiple parameter sets."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite executemany error: {e}")
            raise

    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[RowProxy]:
        """Fetch single row."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            row = cursor.fetchone()
            if row and cursor.description:
                columns = [col[0] for col in cursor.description]
                return RowProxy(row, columns)
            return None
        except Exception as e:
            logger.error(f"SQLite fetch_one error: {e}\nQuery: {query}")
            raise

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[RowProxy]:
        """Fetch all rows."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                return [RowProxy(row, columns) for row in cursor.fetchall()]
            return []
        except Exception as e:
            logger.error(f"SQLite fetch_all error: {e}\nQuery: {query}")
            raise

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        """Cursor context manager."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite cursor error: {e}")
            raise
        finally:
            cursor.close()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Transaction context manager."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"SQLite transaction error: {e}")
            raise

    def initialize(self) -> None:
        """Initialize SQLite schema."""
        logger.info(f"Initializing SQLite database at: {self._db_path}")
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create all tables
        self._create_tables(cursor)
        conn.commit()
        logger.info("SQLite database initialized successfully")

    def _create_tables(self, cursor) -> None:
        """Create all database tables."""
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT,
                email TEXT,
                full_name TEXT,
                full_name_ar TEXT,
                role TEXT NOT NULL DEFAULT 'analyst',
                is_active INTEGER DEFAULT 1,
                is_locked INTEGER DEFAULT 0,
                failed_attempts INTEGER DEFAULT 0,
                last_login TEXT,
                last_activity TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT
            )
        """)

        # Migration: add permissions column if missing
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT ''")
        except Exception:
            pass

        # Buildings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS buildings (
                building_uuid TEXT PRIMARY KEY,
                building_id TEXT UNIQUE NOT NULL,
                governorate_code TEXT,
                governorate_name TEXT,
                governorate_name_ar TEXT,
                district_code TEXT,
                district_name TEXT,
                district_name_ar TEXT,
                subdistrict_code TEXT,
                subdistrict_name TEXT,
                subdistrict_name_ar TEXT,
                community_code TEXT,
                community_name TEXT,
                community_name_ar TEXT,
                neighborhood_code TEXT,
                neighborhood_name TEXT,
                neighborhood_name_ar TEXT,
                building_number TEXT,
                building_type TEXT,
                building_status TEXT,
                number_of_units INTEGER DEFAULT 0,
                number_of_apartments INTEGER DEFAULT 0,
                number_of_shops INTEGER DEFAULT 0,
                number_of_floors INTEGER DEFAULT 1,
                latitude REAL,
                longitude REAL,
                geo_location TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                legacy_stdm_id TEXT
            )
        """)

        # Property Units table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_units (
                unit_uuid TEXT PRIMARY KEY,
                unit_id TEXT UNIQUE NOT NULL,
                building_id TEXT NOT NULL,
                unit_type TEXT,
                unit_number TEXT,
                floor_number INTEGER DEFAULT 0,
                apartment_number TEXT,
                apartment_status TEXT,
                property_description TEXT,
                area_sqm REAL,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                FOREIGN KEY (building_id) REFERENCES buildings(building_id)
            )
        """)

        # Persons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                person_id TEXT PRIMARY KEY,
                first_name TEXT,
                first_name_ar TEXT,
                father_name TEXT,
                father_name_ar TEXT,
                mother_name TEXT,
                mother_name_ar TEXT,
                last_name TEXT,
                last_name_ar TEXT,
                gender TEXT,
                year_of_birth INTEGER,
                nationality TEXT,
                national_id TEXT,
                passport_number TEXT,
                phone_number TEXT,
                mobile_number TEXT,
                email TEXT,
                address TEXT,
                is_contact_person INTEGER DEFAULT 0,
                is_deceased INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Person-Unit Relations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person_unit_relations (
                relation_id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                relation_type TEXT,
                relation_type_other_description TEXT,
                ownership_share INTEGER DEFAULT 0,
                tenure_contract_type TEXT,
                relation_start_date TEXT,
                relation_end_date TEXT,
                verification_status TEXT DEFAULT 'pending',
                verification_date TEXT,
                verified_by TEXT,
                relation_notes TEXT,
                evidence_ids TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                FOREIGN KEY (person_id) REFERENCES persons(person_id),
                FOREIGN KEY (unit_id) REFERENCES property_units(unit_id)
            )
        """)

        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                document_type TEXT,
                document_number TEXT,
                issue_date TEXT,
                expiry_date TEXT,
                issuing_authority TEXT,
                issuing_location TEXT,
                verified INTEGER DEFAULT 0,
                verified_by TEXT,
                verification_date TEXT,
                attachment_path TEXT,
                attachment_hash TEXT,
                attachment_size INTEGER,
                mime_type TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Evidence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL,
                document_id TEXT,
                reference_number TEXT,
                reference_date TEXT,
                evidence_description TEXT,
                evidence_type TEXT,
                verification_status TEXT DEFAULT 'pending',
                verification_notes TEXT,
                verified_by TEXT,
                verification_date TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                FOREIGN KEY (relation_id) REFERENCES person_unit_relations(relation_id),
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            )
        """)

        # Claims table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_uuid TEXT PRIMARY KEY,
                claim_id TEXT UNIQUE NOT NULL,
                case_number TEXT,
                source TEXT,
                person_ids TEXT,
                unit_id TEXT,
                relation_ids TEXT,
                case_status TEXT DEFAULT 'draft',
                lifecycle_stage TEXT,
                claim_type TEXT,
                priority TEXT DEFAULT 'normal',
                assigned_to TEXT,
                assigned_date TEXT,
                awaiting_documents INTEGER DEFAULT 0,
                submission_date TEXT,
                decision_date TEXT,
                notes TEXT,
                resolution_notes TEXT,
                has_conflict INTEGER DEFAULT 0,
                conflict_claim_ids TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                FOREIGN KEY (unit_id) REFERENCES property_units(unit_id)
            )
        """)

        # Import history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                import_id TEXT PRIMARY KEY,
                file_name TEXT,
                file_path TEXT,
                file_hash TEXT,
                import_date TEXT,
                imported_by TEXT,
                status TEXT,
                total_records INTEGER,
                imported_records INTEGER,
                failed_records INTEGER,
                warnings_count INTEGER,
                errors TEXT,
                notes TEXT,
                updated_at TEXT
            )
        """)

        # Claim history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_history (
                history_id TEXT PRIMARY KEY,
                claim_uuid TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                snapshot_data TEXT NOT NULL,
                change_reason TEXT,
                changed_by TEXT,
                changed_at TEXT NOT NULL,
                FOREIGN KEY (claim_uuid) REFERENCES claims(claim_uuid)
            )
        """)

        # Claim documents junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_uuid TEXT NOT NULL,
                document_id TEXT NOT NULL,
                added_at TEXT,
                added_by TEXT,
                removed_at TEXT,
                removed_by TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (claim_uuid) REFERENCES claims(claim_uuid),
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            )
        """)

        # Duplicate resolutions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_resolutions (
                resolution_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                group_key TEXT NOT NULL,
                record_ids TEXT NOT NULL,
                resolution_type TEXT NOT NULL,
                master_record_id TEXT,
                justification TEXT,
                resolved_by TEXT,
                resolved_at TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)

        # Households/Occupancy table (FSD 6.1.6)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS households (
                household_id TEXT PRIMARY KEY,
                unit_id TEXT NOT NULL,
                main_occupant_id TEXT,
                main_occupant_name TEXT,
                occupancy_size INTEGER DEFAULT 1,
                male_count INTEGER DEFAULT 0,
                female_count INTEGER DEFAULT 0,
                minors_count INTEGER DEFAULT 0,
                adults_count INTEGER DEFAULT 0,
                elderly_count INTEGER DEFAULT 0,
                with_disability_count INTEGER DEFAULT 0,
                occupancy_type TEXT,
                occupancy_nature TEXT,
                occupancy_start_date TEXT,
                monthly_rent REAL,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                FOREIGN KEY (unit_id) REFERENCES property_units(unit_id),
                FOREIGN KEY (main_occupant_id) REFERENCES persons(person_id)
            )
        """)

        # Vocabulary terms table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary_terms (
                term_id TEXT PRIMARY KEY,
                vocabulary_name TEXT NOT NULL,
                term_code TEXT NOT NULL,
                term_label TEXT NOT NULL,
                term_label_ar TEXT,
                status TEXT DEFAULT 'active',
                effective_from TEXT,
                effective_to TEXT,
                version_number INTEGER DEFAULT 1,
                source TEXT DEFAULT 'manual',
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                UNIQUE(vocabulary_name, term_code)
            )
        """)

        # Security settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_settings (
                setting_id TEXT PRIMARY KEY,
                password_min_length INTEGER DEFAULT 8,
                password_require_uppercase INTEGER DEFAULT 1,
                password_require_lowercase INTEGER DEFAULT 1,
                password_require_digit INTEGER DEFAULT 1,
                password_require_symbol INTEGER DEFAULT 0,
                password_expiry_days INTEGER DEFAULT 90,
                password_reuse_history INTEGER DEFAULT 5,
                session_timeout_minutes INTEGER DEFAULT 30,
                max_failed_login_attempts INTEGER DEFAULT 5,
                account_lockout_duration_minutes INTEGER DEFAULT 15,
                updated_at TEXT,
                updated_by TEXT
            )
        """)

        # Audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                username TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                details TEXT
            )
        """)

        # Building assignments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS building_assignments (
                assignment_id TEXT PRIMARY KEY,
                building_id TEXT NOT NULL,
                assigned_to TEXT,
                field_team_name TEXT,
                tablet_device_id TEXT,
                assignment_status TEXT DEFAULT 'pending',
                assignment_date TEXT,
                assigned_by TEXT,
                transfer_status TEXT DEFAULT 'not_transferred',
                transfer_date TEXT,
                transfer_error TEXT,
                requires_revisit INTEGER DEFAULT 0,
                revisit_reason TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (building_id) REFERENCES buildings(building_id)
            )
        """)

        # Conflicts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                conflict_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                source_entity_type TEXT NOT NULL,
                source_entity_id TEXT NOT NULL,
                source_data TEXT,
                target_entity_id TEXT,
                target_data TEXT,
                field_conflicts TEXT,
                match_score REAL,
                import_id TEXT,
                created_at TEXT,
                created_by TEXT,
                assigned_to TEXT,
                resolution TEXT,
                resolution_notes TEXT,
                resolved_at TEXT,
                resolved_by TEXT
            )
        """)

        # Conflict audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflict_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conflict_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                details TEXT,
                performed_by TEXT,
                performed_at TEXT
            )
        """)

        # Duplicate candidates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_candidates (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                score REAL,
                matched_fields TEXT,
                status TEXT DEFAULT 'pending',
                resolution TEXT,
                created_at TEXT,
                resolved_at TEXT,
                resolved_by TEXT
            )
        """)

        # Sync log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                sync_date TEXT,
                status TEXT
            )
        """)

        # Registered devices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registered_devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                registered_at TEXT
            )
        """)

        # Surveys table (UC-004, UC-005)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                survey_id TEXT PRIMARY KEY,
                building_id TEXT,
                unit_id TEXT,
                field_collector_id TEXT,
                survey_date TEXT,
                survey_type TEXT,
                status TEXT DEFAULT 'draft',
                reference_code TEXT,
                source TEXT DEFAULT 'field',
                notes TEXT,
                context_data TEXT,
                created_at TEXT,
                updated_at TEXT,
                finalized_at TEXT,
                FOREIGN KEY (building_id) REFERENCES buildings(building_id),
                FOREIGN KEY (unit_id) REFERENCES property_units(unit_id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_neighborhood ON buildings(neighborhood_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_status ON buildings(building_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_building ON property_units(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_person ON person_unit_relations(person_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_unit ON person_unit_relations(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(case_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_unit ON claims(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_history_claim ON claim_history(claim_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_documents_claim ON claim_documents(claim_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_resolutions_type ON duplicate_resolutions(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_resolutions_status ON duplicate_resolutions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_name ON vocabulary_terms(vocabulary_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary_terms(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_building ON building_assignments(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_status ON building_assignments(assignment_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_transfer ON building_assignments(transfer_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_priority ON conflicts(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_type ON conflicts(conflict_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveys_building ON surveys(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveys_status ON surveys(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_surveys_source ON surveys(source)")

        # Seed default data
        self._seed_defaults(cursor)

        logger.debug("All SQLite tables created successfully")

    def _seed_defaults(self, cursor) -> None:
        """Seed default data."""
        import uuid

        now = datetime.now().isoformat()

        # Seed security settings if empty
        cursor.execute("SELECT COUNT(*) as count FROM security_settings")
        row = cursor.fetchone()
        if row and row['count'] == 0:
            cursor.execute(
                "INSERT INTO security_settings (setting_id, updated_at) VALUES (?, ?)",
                ('default', now)
            )

        # Seed vocabularies if empty
        cursor.execute("SELECT COUNT(*) as count FROM vocabulary_terms")
        row = cursor.fetchone()
        if row and row['count'] == 0:
            self._seed_vocabularies(cursor, now)

    def _seed_vocabularies(self, cursor, now: str) -> None:
        """Seed default vocabulary terms."""
        import uuid

        vocabularies = {
            'building_type': [
                ("residential", "Residential", "سكني"),
                ("commercial", "Commercial", "تجاري"),
                ("mixed_use", "Mixed Use", "متعدد الاستخدامات"),
                ("industrial", "Industrial", "صناعي"),
                ("public", "Public", "عام"),
            ],
            'building_status': [
                ("intact", "Intact", "سليم"),
                ("minor_damage", "Minor Damage", "ضرر طفيف"),
                ("major_damage", "Major Damage", "ضرر كبير"),
                ("destroyed", "Destroyed", "مدمر"),
                ("under_construction", "Under Construction", "قيد البناء"),
            ],
            'unit_type': [
                ("apartment", "Apartment", "شقة"),
                ("shop", "Shop", "محل"),
                ("office", "Office", "مكتب"),
                ("warehouse", "Warehouse", "مستودع"),
                ("garage", "Garage", "كراج"),
                ("other", "Other", "آخر"),
            ],
            'relation_type': [
                ("owner", "Owner", "مالك"),
                ("tenant", "Tenant", "مستأجر"),
                ("heir", "Heir", "وريث"),
                ("guest", "Guest", "ضيف"),
                ("occupant", "Occupant", "شاغل"),
                ("other", "Other", "آخر"),
            ],
            'case_status': [
                ("draft", "Draft", "مسودة"),
                ("submitted", "Submitted", "مقدمة"),
                ("screening", "Screening", "تدقيق أولي"),
                ("under_review", "Under Review", "قيد المراجعة"),
                ("awaiting_docs", "Awaiting Documents", "بانتظار الوثائق"),
                ("conflict", "Conflict", "تعارض"),
                ("approved", "Approved", "موافق عليها"),
                ("rejected", "Rejected", "مرفوضة"),
            ],
            'contract_type': [
                ("full_ownership", "Full Ownership", "ملكية كاملة"),
                ("shared_ownership", "Shared Ownership", "ملكية مشتركة"),
                ("long_term_rental", "Long-term Rental", "إيجار طويل الأمد"),
                ("short_term_rental", "Short-term Rental", "إيجار قصير الأمد"),
                ("informal_tenure", "Informal Tenure", "حيازة غير رسمية"),
                ("unauthorized_occupation", "Unauthorized Occupation", "إشغال غير مرخص"),
                ("customary_rights", "Customary Rights", "حقوق عرفية"),
                ("inheritance_based", "Inheritance-based", "قائم على الإرث"),
                ("hosted_guest", "Hosted/Guest", "مستضاف/ضيف"),
                ("temporary_shelter", "Temporary Shelter", "مأوى مؤقت"),
                ("government_allocation", "Government Allocation", "تخصيص حكومي"),
                ("usufruct", "Usufruct", "حق الانتفاع"),
                ("other", "Other", "أخرى"),
            ],
            'evidence_type': [
                ("identification_document", "Identification Document", "وثيقة هوية"),
                ("ownership_deed", "Ownership Deed", "سند ملكية"),
                ("rental_contract", "Rental Contract", "عقد إيجار"),
                ("utility_bill", "Utility Bill", "فاتورة خدمات"),
                ("photo", "Photo", "صورة"),
                ("official_letter", "Official Letter", "خطاب رسمي"),
                ("court_order", "Court Order", "أمر محكمة"),
                ("inheritance_document", "Inheritance Document", "وثيقة إرث"),
                ("tax_receipt", "Tax Receipt", "إيصال ضريبي"),
                ("other", "Other", "أخرى"),
            ],
            'occupancy_type': [
                ("owner_occupied", "Owner Occupied", "مشغول من المالك"),
                ("tenant_occupied", "Tenant Occupied", "مشغول من المستأجر"),
                ("family_occupied", "Family Occupied", "مشغول من العائلة"),
                ("mixed_occupancy", "Mixed Occupancy", "إشغال مختلط"),
                ("vacant", "Vacant", "شاغر"),
                ("temporary_seasonal", "Temporary/Seasonal", "مؤقت/موسمي"),
                ("commercial_use", "Commercial Use", "استخدام تجاري"),
                ("abandoned", "Abandoned", "مهجور"),
                ("disputed", "Disputed", "متنازع عليه"),
                ("unknown", "Unknown", "غير معروف"),
            ],
            'occupancy_nature': [
                ("legal_formal", "Legal/Formal", "قانوني/رسمي"),
                ("informal", "Informal", "غير رسمي"),
                ("customary", "Customary", "عرفي"),
                ("temporary_emergency", "Temporary/Emergency", "مؤقت/طوارئ"),
                ("authorized", "Authorized", "مرخص"),
                ("unauthorized", "Unauthorized", "غير مرخص"),
                ("pending_regularization", "Pending Regularization", "بانتظار التسوية"),
                ("contested", "Contested", "متنازع عليه"),
                ("unknown", "Unknown", "غير معروف"),
            ],
            'nationality': [
                ("syrian", "Syrian", "سوري"),
                ("palestinian", "Palestinian", "فلسطيني"),
                ("iraqi", "Iraqi", "عراقي"),
                ("lebanese", "Lebanese", "لبناني"),
                ("jordanian", "Jordanian", "أردني"),
                ("turkish", "Turkish", "تركي"),
                ("egyptian", "Egyptian", "مصري"),
                ("yemeni", "Yemeni", "يمني"),
                ("sudanese", "Sudanese", "سوداني"),
                ("libyan", "Libyan", "ليبي"),
                ("somali", "Somali", "صومالي"),
                ("afghan", "Afghan", "أفغاني"),
                ("stateless", "Stateless", "عديم الجنسية"),
                ("other", "Other", "أخرى"),
                ("unknown", "Unknown", "غير معروف"),
            ],
            'claim_type': [
                ("ownership", "Ownership", "ملكية"),
                ("occupancy", "Occupancy", "إشغال"),
                ("tenancy", "Tenancy", "إيجار"),
            ],
            'claim_status': [
                ("new", "New", "جديدة"),
                ("under_review", "Under Review", "قيد المراجعة"),
                ("completed", "Completed", "مكتملة"),
                ("pending", "Pending", "معلقة"),
                ("draft", "Draft", "مسودة"),
            ],
            'case_priority': [
                ("low", "Low", "منخفضة"),
                ("normal", "Normal", "عادية"),
                ("high", "High", "عالية"),
                ("urgent", "Urgent", "عاجلة"),
            ],
            'claim_source': [
                ("field_survey", "Field Survey", "مسح ميداني"),
                ("direct_request", "Direct Request", "طلب مباشر"),
                ("referral", "Referral", "إحالة"),
                ("office_submission", "Office Submission", "تقديم مكتبي"),
            ],
            'business_nature': [
                ("residential", "Residential", "سكني"),
                ("commercial", "Commercial", "تجاري"),
                ("agricultural", "Agricultural", "زراعي"),
            ],
        }

        for vocab_name, terms in vocabularies.items():
            for code, en, ar in terms:
                cursor.execute(
                    "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), vocab_name, code, en, ar, now)
                )

        logger.debug("Seeded default vocabularies")

    def is_empty(self) -> bool:
        """Check if database has no data."""
        result = self.fetch_one("SELECT COUNT(*) as count FROM buildings")
        return result["count"] == 0 if result else True


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter with connection pooling and PostGIS support."""

    def __init__(self, config: DatabaseConfig):
        """Initialize PostgreSQL adapter."""
        self._config = config
        self._pool = None

        # Check for psycopg2
        try:
            import psycopg2
            from psycopg2 import pool as pg_pool
            from psycopg2.extras import RealDictCursor
            self._psycopg2 = psycopg2
            self._pg_pool = pg_pool
            self._RealDictCursor = RealDictCursor
            self._available = True
        except ImportError:
            logger.warning("psycopg2 not installed. PostgreSQL support unavailable.")
            self._available = False

    @property
    def db_type(self) -> DatabaseType:
        return DatabaseType.POSTGRESQL

    @property
    def is_available(self) -> bool:
        """Check if PostgreSQL driver is available."""
        return self._available

    def connect(self) -> bool:
        """Establish PostgreSQL connection pool."""
        if not self._available:
            return False

        try:
            self._pool = self._pg_pool.ThreadedConnectionPool(
                minconn=self._config.pg_pool_min,
                maxconn=self._config.pg_pool_max,
                host=self._config.pg_host,
                port=self._config.pg_port,
                database=self._config.pg_database,
                user=self._config.pg_user,
                password=self._config.pg_password
            )
            logger.info(f"PostgreSQL connection pool established: {self._config.pg_host}:{self._config.pg_port}/{self._config.pg_database}")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection error: {e}")
            return False

    def close(self) -> None:
        """Close PostgreSQL connection pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    def is_connected(self) -> bool:
        """Check if pool is active."""
        return self._pool is not None

    def _get_connection(self):
        """Get connection from pool."""
        if not self._pool:
            if not self.connect():
                raise RuntimeError("Could not connect to PostgreSQL")
        return self._pool.getconn()

    def _put_connection(self, conn):
        """Return connection to pool."""
        if self._pool and conn:
            self._pool.putconn(conn)

    def execute(self, query: str, params: Optional[Tuple] = None) -> List[RowProxy]:
        """Execute query and return results."""
        # Convert ? to %s for PostgreSQL
        query = self._convert_placeholders(query)

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cursor:
                cursor.execute(query, params)
                conn.commit()

                if cursor.description:
                    columns = [col.name for col in cursor.description]
                    return [RowProxy(dict(row), columns) for row in cursor.fetchall()]
                return []
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL execute error: {e}\nQuery: {query}")
            raise
        finally:
            self._put_connection(conn)

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute query with multiple parameter sets."""
        query = self._convert_placeholders(query)

        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL executemany error: {e}")
            raise
        finally:
            self._put_connection(conn)

    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[RowProxy]:
        """Fetch single row."""
        query = self._convert_placeholders(query)

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                if row and cursor.description:
                    columns = [col.name for col in cursor.description]
                    return RowProxy(dict(row), columns)
                return None
        except Exception as e:
            logger.error(f"PostgreSQL fetch_one error: {e}\nQuery: {query}")
            raise
        finally:
            self._put_connection(conn)

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[RowProxy]:
        """Fetch all rows."""
        query = self._convert_placeholders(query)

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=self._RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    columns = [col.name for col in cursor.description]
                    return [RowProxy(dict(row), columns) for row in cursor.fetchall()]
                return []
        except Exception as e:
            logger.error(f"PostgreSQL fetch_all error: {e}\nQuery: {query}")
            raise
        finally:
            self._put_connection(conn)

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        """Cursor context manager."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=self._RealDictCursor)
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL cursor error: {e}")
            raise
        finally:
            cursor.close()
            self._put_connection(conn)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Transaction context manager."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL transaction error: {e}")
            raise
        finally:
            self._put_connection(conn)

    def _convert_placeholders(self, query: str) -> str:
        """Convert ? placeholders to %s for PostgreSQL."""
        # Simple replacement - works for most cases
        return query.replace("?", "%s")

    def initialize(self) -> None:
        """Initialize PostgreSQL schema with PostGIS."""
        logger.info(f"Initializing PostgreSQL database: {self._config.pg_database}")

        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Enable PostGIS
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # For text search

                # Create tables
                self._create_tables(cursor)

                conn.commit()
                logger.info("PostgreSQL database initialized with PostGIS")
        finally:
            self._put_connection(conn)

    def _create_tables(self, cursor) -> None:
        """Create PostgreSQL tables with PostGIS geometry support."""

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT,
                email TEXT,
                full_name TEXT,
                full_name_ar TEXT,
                role TEXT NOT NULL DEFAULT 'analyst',
                is_active BOOLEAN DEFAULT TRUE,
                is_locked BOOLEAN DEFAULT FALSE,
                failed_attempts INTEGER DEFAULT 0,
                last_login TIMESTAMP,
                last_activity TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT
            )
        """)

        # Migration: add permissions column if missing
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT ''")
        except Exception:
            pass

        # Buildings table with PostGIS geometry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS buildings (
                building_uuid TEXT PRIMARY KEY,
                building_id TEXT UNIQUE NOT NULL,
                governorate_code TEXT,
                governorate_name TEXT,
                governorate_name_ar TEXT,
                district_code TEXT,
                district_name TEXT,
                district_name_ar TEXT,
                subdistrict_code TEXT,
                subdistrict_name TEXT,
                subdistrict_name_ar TEXT,
                community_code TEXT,
                community_name TEXT,
                community_name_ar TEXT,
                neighborhood_code TEXT,
                neighborhood_name TEXT,
                neighborhood_name_ar TEXT,
                building_number TEXT,
                building_type TEXT,
                building_status TEXT,
                number_of_units INTEGER DEFAULT 0,
                number_of_apartments INTEGER DEFAULT 0,
                number_of_shops INTEGER DEFAULT 0,
                number_of_floors INTEGER DEFAULT 1,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                geo_location GEOGRAPHY(POINT, 4326),
                building_geometry GEOMETRY(POLYGON, 4326),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                legacy_stdm_id TEXT,
                CONSTRAINT chk_building_id_format CHECK (building_id ~ '^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}-\d{5}$')
            )
        """)

        # Property Units table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_units (
                unit_uuid TEXT PRIMARY KEY,
                unit_id TEXT UNIQUE NOT NULL,
                building_id TEXT NOT NULL REFERENCES buildings(building_id),
                unit_type TEXT,
                unit_number TEXT,
                floor_number INTEGER DEFAULT 0,
                apartment_number TEXT,
                apartment_status TEXT,
                property_description TEXT,
                area_sqm DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Persons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                person_id TEXT PRIMARY KEY,
                first_name TEXT,
                first_name_ar TEXT,
                father_name TEXT,
                father_name_ar TEXT,
                mother_name TEXT,
                mother_name_ar TEXT,
                last_name TEXT,
                last_name_ar TEXT,
                gender TEXT,
                year_of_birth INTEGER,
                nationality TEXT,
                national_id TEXT,
                passport_number TEXT,
                phone_number TEXT,
                mobile_number TEXT,
                email TEXT,
                address TEXT,
                is_contact_person BOOLEAN DEFAULT FALSE,
                is_deceased BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Person-Unit Relations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person_unit_relations (
                relation_id TEXT PRIMARY KEY,
                person_id TEXT NOT NULL REFERENCES persons(person_id),
                unit_id TEXT NOT NULL REFERENCES property_units(unit_id),
                relation_type TEXT,
                relation_type_other_description TEXT,
                ownership_share INTEGER DEFAULT 0,
                tenure_contract_type TEXT,
                relation_start_date DATE,
                relation_end_date DATE,
                verification_status TEXT DEFAULT 'pending',
                verification_date TIMESTAMP,
                verified_by TEXT,
                relation_notes TEXT,
                evidence_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                document_type TEXT,
                document_number TEXT,
                issue_date DATE,
                expiry_date DATE,
                issuing_authority TEXT,
                issuing_location TEXT,
                verified BOOLEAN DEFAULT FALSE,
                verified_by TEXT,
                verification_date TIMESTAMP,
                attachment_path TEXT,
                attachment_hash TEXT,
                attachment_size BIGINT,
                mime_type TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Evidence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL REFERENCES person_unit_relations(relation_id),
                document_id TEXT REFERENCES documents(document_id),
                reference_number TEXT,
                reference_date DATE,
                evidence_description TEXT,
                evidence_type TEXT,
                verification_status TEXT DEFAULT 'pending',
                verification_notes TEXT,
                verified_by TEXT,
                verification_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Claims table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_uuid TEXT PRIMARY KEY,
                claim_id TEXT UNIQUE NOT NULL,
                case_number TEXT,
                source TEXT,
                person_ids TEXT,
                unit_id TEXT REFERENCES property_units(unit_id),
                relation_ids TEXT,
                case_status TEXT DEFAULT 'draft',
                lifecycle_stage TEXT,
                claim_type TEXT,
                priority TEXT DEFAULT 'normal',
                assigned_to TEXT,
                assigned_date TIMESTAMP,
                awaiting_documents BOOLEAN DEFAULT FALSE,
                submission_date TIMESTAMP,
                decision_date TIMESTAMP,
                notes TEXT,
                resolution_notes TEXT,
                has_conflict BOOLEAN DEFAULT FALSE,
                conflict_claim_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT
            )
        """)

        # Import history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                import_id TEXT PRIMARY KEY,
                file_name TEXT,
                file_path TEXT,
                file_hash TEXT,
                import_date TIMESTAMP,
                imported_by TEXT,
                status TEXT,
                total_records INTEGER,
                imported_records INTEGER,
                failed_records INTEGER,
                warnings_count INTEGER,
                errors JSONB,
                notes TEXT,
                updated_at TIMESTAMP
            )
        """)

        # Additional tables (claim_history, claim_documents, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_history (
                history_id TEXT PRIMARY KEY,
                claim_uuid TEXT NOT NULL REFERENCES claims(claim_uuid),
                claim_id TEXT NOT NULL,
                snapshot_data JSONB NOT NULL,
                change_reason TEXT,
                changed_by TEXT,
                changed_at TIMESTAMP NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_documents (
                id SERIAL PRIMARY KEY,
                claim_uuid TEXT NOT NULL REFERENCES claims(claim_uuid),
                document_id TEXT NOT NULL REFERENCES documents(document_id),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by TEXT,
                removed_at TIMESTAMP,
                removed_by TEXT,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_resolutions (
                resolution_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                group_key TEXT NOT NULL,
                record_ids TEXT NOT NULL,
                resolution_type TEXT NOT NULL,
                master_record_id TEXT,
                justification TEXT,
                resolved_by TEXT,
                resolved_at TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary_terms (
                term_id TEXT PRIMARY KEY,
                vocabulary_name TEXT NOT NULL,
                term_code TEXT NOT NULL,
                term_label TEXT NOT NULL,
                term_label_ar TEXT,
                status TEXT DEFAULT 'active',
                effective_from DATE,
                effective_to DATE,
                version_number INTEGER DEFAULT 1,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                UNIQUE(vocabulary_name, term_code)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_settings (
                setting_id TEXT PRIMARY KEY,
                password_min_length INTEGER DEFAULT 8,
                password_require_uppercase BOOLEAN DEFAULT TRUE,
                password_require_lowercase BOOLEAN DEFAULT TRUE,
                password_require_digit BOOLEAN DEFAULT TRUE,
                password_require_symbol BOOLEAN DEFAULT FALSE,
                password_expiry_days INTEGER DEFAULT 90,
                password_reuse_history INTEGER DEFAULT 5,
                session_timeout_minutes INTEGER DEFAULT 30,
                max_failed_login_attempts INTEGER DEFAULT 5,
                account_lockout_duration_minutes INTEGER DEFAULT 15,
                updated_at TIMESTAMP,
                updated_by TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                user_id TEXT,
                username TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                old_values JSONB,
                new_values JSONB,
                ip_address TEXT,
                details TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS building_assignments (
                assignment_id TEXT PRIMARY KEY,
                building_id TEXT NOT NULL REFERENCES buildings(building_id),
                assigned_to TEXT,
                field_team_name TEXT,
                tablet_device_id TEXT,
                assignment_status TEXT DEFAULT 'pending',
                assignment_date TIMESTAMP,
                assigned_by TEXT,
                transfer_status TEXT DEFAULT 'not_transferred',
                transfer_date TIMESTAMP,
                transfer_error TEXT,
                requires_revisit BOOLEAN DEFAULT FALSE,
                revisit_reason TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                conflict_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                source_entity_type TEXT NOT NULL,
                source_entity_id TEXT NOT NULL,
                source_data JSONB,
                target_entity_id TEXT,
                target_data JSONB,
                field_conflicts JSONB,
                match_score DOUBLE PRECISION,
                import_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                assigned_to TEXT,
                resolution TEXT,
                resolution_notes TEXT,
                resolved_at TIMESTAMP,
                resolved_by TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflict_audit (
                id SERIAL PRIMARY KEY,
                conflict_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                details JSONB,
                performed_by TEXT,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_candidates (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                score DOUBLE PRECISION,
                matched_fields TEXT,
                status TEXT DEFAULT 'pending',
                resolution TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_by TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details JSONB,
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registered_devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_neighborhood ON buildings(neighborhood_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_status ON buildings(building_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_geo ON buildings USING GIST(geo_location)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_geometry ON buildings USING GIST(building_geometry)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_building ON property_units(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_person ON person_unit_relations(person_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_unit ON person_unit_relations(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(case_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_unit ON claims(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_history_claim ON claim_history(claim_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_documents_claim ON claim_documents(claim_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_resolutions_type ON duplicate_resolutions(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_resolutions_status ON duplicate_resolutions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_name ON vocabulary_terms(vocabulary_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary_terms(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_building ON building_assignments(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_status ON building_assignments(assignment_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_transfer ON building_assignments(transfer_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_priority ON conflicts(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_type ON conflicts(conflict_type)")

        # Seed defaults
        self._seed_defaults(cursor)

        logger.debug("All PostgreSQL tables created successfully")

    def _seed_defaults(self, cursor) -> None:
        """Seed default data."""
        import uuid

        # Seed security settings if empty
        cursor.execute("SELECT COUNT(*) as count FROM security_settings")
        row = cursor.fetchone()
        if row and row[0] == 0:
            cursor.execute(
                "INSERT INTO security_settings (setting_id, updated_at) VALUES (%s, %s)",
                ('default', datetime.now())
            )

        # Seed vocabularies if empty
        cursor.execute("SELECT COUNT(*) as count FROM vocabulary_terms")
        row = cursor.fetchone()
        if row and row[0] == 0:
            self._seed_vocabularies(cursor)

    def _seed_vocabularies(self, cursor) -> None:
        """Seed default vocabulary terms."""
        import uuid

        now = datetime.now()

        vocabularies = {
            'building_type': [
                ("residential", "Residential", "سكني"),
                ("commercial", "Commercial", "تجاري"),
                ("mixed_use", "Mixed Use", "متعدد الاستخدامات"),
            ],
            'building_status': [
                ("intact", "Intact", "سليم"),
                ("minor_damage", "Minor Damage", "ضرر طفيف"),
                ("major_damage", "Major Damage", "ضرر كبير"),
                ("destroyed", "Destroyed", "مدمر"),
            ],
            'unit_type': [
                ("apartment", "Apartment", "شقة"),
                ("shop", "Shop", "محل"),
                ("office", "Office", "مكتب"),
            ],
            'relation_type': [
                ("owner", "Owner", "مالك"),
                ("tenant", "Tenant", "مستأجر"),
                ("heir", "Heir", "وريث"),
                ("guest", "Guest", "ضيف"),
                ("occupant", "Occupant", "شاغل"),
            ],
            'case_status': [
                ("draft", "Draft", "مسودة"),
                ("submitted", "Submitted", "مقدمة"),
                ("under_review", "Under Review", "قيد المراجعة"),
                ("approved", "Approved", "موافق عليها"),
                ("rejected", "Rejected", "مرفوضة"),
            ],
        }

        for vocab_name, terms in vocabularies.items():
            for code, en, ar in terms:
                cursor.execute(
                    "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), vocab_name, code, en, ar, now)
                )

    def get_postgis_version(self) -> Optional[str]:
        """Get PostGIS version."""
        try:
            result = self.fetch_one("SELECT PostGIS_Version()")
            return result[0] if result else None
        except Exception:
            return None

    def is_empty(self) -> bool:
        """Check if database has no data."""
        result = self.fetch_one("SELECT COUNT(*) as count FROM buildings")
        return result["count"] == 0 if result else True


class DatabaseFactory:
    """
    Factory for creating database adapters.
    Defaults to PostgreSQL as per FSD 5.2.
    """

    _instance: Optional[DatabaseAdapter] = None
    _config: Optional[DatabaseConfig] = None

    @classmethod
    def create(cls, config: Optional[DatabaseConfig] = None) -> DatabaseAdapter:
        """
        Create or return existing database adapter.

        Args:
            config: Database configuration. If None, loads from environment.

        Returns:
            DatabaseAdapter instance
        """
        if config is None:
            config = DatabaseConfig.from_env()

        # Return existing if same config
        if cls._instance is not None and cls._config == config:
            return cls._instance

        cls._config = config

        # Try PostgreSQL first (default)
        if config.db_type == DatabaseType.POSTGRESQL:
            adapter = PostgreSQLAdapter(config)
            if adapter.is_available and adapter.connect():
                logger.info(f"Using PostgreSQL database: {config.pg_host}:{config.pg_port}/{config.pg_database}")
                cls._instance = adapter
                return adapter
            else:
                logger.warning("PostgreSQL unavailable, falling back to SQLite")

        # Fallback to SQLite
        adapter = SQLiteAdapter(config.sqlite_path)
        adapter.connect()
        logger.info(f"Using SQLite database: {adapter.db_path}")
        cls._instance = adapter
        return adapter

    @classmethod
    def get_instance(cls) -> Optional[DatabaseAdapter]:
        """Get current database instance."""
        return cls._instance

    @classmethod
    def get_type(cls) -> Optional[DatabaseType]:
        """Get current database type."""
        if cls._instance:
            return cls._instance.db_type
        return None

    @classmethod
    def is_postgres(cls) -> bool:
        """Check if using PostgreSQL."""
        return cls._instance and cls._instance.db_type == DatabaseType.POSTGRESQL

    @classmethod
    def reset(cls) -> None:
        """Reset factory and close connections."""
        if cls._instance:
            try:
                cls._instance.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")
        cls._instance = None
        cls._config = None


# Convenience function
def get_database() -> DatabaseAdapter:
    """Get the configured database adapter."""
    return DatabaseFactory.create()
