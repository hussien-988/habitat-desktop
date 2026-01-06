# -*- coding: utf-8 -*-
"""
SQLite Database connection manager.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Any
from contextlib import contextmanager

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        self.db_path = db_path or Config.DB_PATH
        self._connection: Optional[sqlite3.Connection] = None

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self):
        """Initialize database and create tables."""
        logger.info(f"Initializing database at: {self.db_path}")

        conn = self.get_connection()
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Create tables
        self._create_tables(cursor)

        conn.commit()
        logger.info("Database initialized successfully")

    def _create_tables(self, cursor: sqlite3.Cursor):
        """Create all database tables."""

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
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
                notes TEXT
            )
        """)

        # Claim history table for audit trail (UC-006)
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

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_neighborhood ON buildings(neighborhood_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_status ON buildings(building_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_building ON property_units(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_person ON person_unit_relations(person_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_unit ON person_unit_relations(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(case_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_unit ON claims(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_history_claim ON claim_history(claim_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_documents_claim ON claim_documents(claim_uuid)")

        # Duplicate resolution tracking table (UC-007, UC-008)
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_resolutions_type ON duplicate_resolutions(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_resolutions_status ON duplicate_resolutions(status)")

        # Vocabulary terms table (UC-010)
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_name ON vocabulary_terms(vocabulary_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary_terms(status)")

        # Seed default vocabulary terms if empty
        cursor.execute("SELECT COUNT(*) FROM vocabulary_terms")
        if cursor.fetchone()[0] == 0:
            self._seed_default_vocabularies(cursor)

        # Security settings table (UC-011)
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

        # Audit log table (UC-011)
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")

        # Building assignments table (UC-012)
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_building ON building_assignments(building_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_status ON building_assignments(assignment_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_transfer ON building_assignments(transfer_status)")

        # Seed default security settings if empty
        cursor.execute("SELECT COUNT(*) FROM security_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO security_settings (setting_id, updated_at)
                VALUES ('default', datetime('now'))
            """)

        logger.debug("All tables created successfully")

    def _seed_default_vocabularies(self, cursor):
        """Seed default vocabulary terms from config."""
        from datetime import datetime
        import uuid

        now = datetime.now().isoformat()

        # Building types
        building_types = [
            ("residential", "Residential", "سكني"),
            ("commercial", "Commercial", "تجاري"),
            ("mixed_use", "Mixed Use", "متعدد الاستخدامات"),
            ("industrial", "Industrial", "صناعي"),
            ("public", "Public", "عام"),
        ]
        for code, en, ar in building_types:
            cursor.execute(
                "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "building_type", code, en, ar, now)
            )

        # Building status
        building_status = [
            ("intact", "Intact", "سليم"),
            ("minor_damage", "Minor Damage", "ضرر طفيف"),
            ("major_damage", "Major Damage", "ضرر كبير"),
            ("destroyed", "Destroyed", "مدمر"),
            ("under_construction", "Under Construction", "قيد البناء"),
        ]
        for code, en, ar in building_status:
            cursor.execute(
                "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "building_status", code, en, ar, now)
            )

        # Unit types
        unit_types = [
            ("apartment", "Apartment", "شقة"),
            ("shop", "Shop", "محل"),
            ("office", "Office", "مكتب"),
            ("warehouse", "Warehouse", "مستودع"),
            ("garage", "Garage", "كراج"),
            ("other", "Other", "آخر"),
        ]
        for code, en, ar in unit_types:
            cursor.execute(
                "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "unit_type", code, en, ar, now)
            )

        # Relation types
        relation_types = [
            ("owner", "Owner", "مالك"),
            ("tenant", "Tenant", "مستأجر"),
            ("heir", "Heir", "وريث"),
            ("guest", "Guest", "ضيف"),
            ("occupant", "Occupant", "شاغل"),
            ("other", "Other", "آخر"),
        ]
        for code, en, ar in relation_types:
            cursor.execute(
                "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "relation_type", code, en, ar, now)
            )

        # Case status
        case_status = [
            ("draft", "Draft", "مسودة"),
            ("submitted", "Submitted", "مقدمة"),
            ("screening", "Screening", "تدقيق أولي"),
            ("under_review", "Under Review", "قيد المراجعة"),
            ("awaiting_docs", "Awaiting Documents", "بانتظار الوثائق"),
            ("conflict", "Conflict", "تعارض"),
            ("approved", "Approved", "موافق عليها"),
            ("rejected", "Rejected", "مرفوضة"),
        ]
        for code, en, ar in case_status:
            cursor.execute(
                "INSERT INTO vocabulary_terms (term_id, vocabulary_name, term_code, term_label, term_label_ar, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "case_status", code, en, ar, now)
            )

        logger.debug("Seeded default vocabulary terms")

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection (creates if needed)."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection

    @contextmanager
    def cursor(self):
        """Context manager for database cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute query and fetch one row."""
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute query and fetch all rows."""
        cursor = self.execute(query, params)
        return cursor.fetchall()

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    def is_empty(self) -> bool:
        """Check if database has no data."""
        result = self.fetch_one("SELECT COUNT(*) as count FROM buildings")
        return result["count"] == 0 if result else True
