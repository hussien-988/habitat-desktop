# -*- coding: utf-8 -*-
"""
PostgreSQL + PostGIS Database connection manager.
Implements FSD Section 5.2: "Central DB is PostgreSQL with PostGIS extension"
"""

import os
from typing import Optional, List, Any, Dict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import uuid

try:
    import psycopg2
    from psycopg2 import pool, extras, sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    psycopg2 = None

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PostgresConfig:
    """PostgreSQL connection configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "trrcms"
    user: str = "trrcms_user"
    password: str = "trrcms_password"
    min_connections: int = 1
    max_connections: int = 10

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("TRRCMS_DB_HOST", "localhost"),
            port=int(os.getenv("TRRCMS_DB_PORT", "5432")),
            database=os.getenv("TRRCMS_DB_NAME", "trrcms"),
            user=os.getenv("TRRCMS_DB_USER", "trrcms_user"),
            password=os.getenv("TRRCMS_DB_PASSWORD", "trrcms_password"),
            min_connections=int(os.getenv("TRRCMS_DB_MIN_CONN", "1")),
            max_connections=int(os.getenv("TRRCMS_DB_MAX_CONN", "10")),
        )


class PostgresDatabase:
    """
    PostgreSQL + PostGIS database connection manager.

    Implements:
    - FSD 5.2: PostgreSQL 16 + PostGIS
    - FSD 5.2: Support PostgreSQL versions 12+
    - FSD 13.1: Data Encryption
    - FSD 13.5: Active Data Retention
    """

    def __init__(self, config: Optional[PostgresConfig] = None):
        """Initialize database connection pool."""
        if not POSTGRES_AVAILABLE:
            raise ImportError(
                "psycopg2 is not installed. Install it with: pip install psycopg2-binary"
            )

        self.config = config or PostgresConfig.from_env()
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._initialized = False

    def connect(self) -> bool:
        """
        Establish connection pool to PostgreSQL.
        Returns True if successful.
        """
        try:
            # First, ensure database exists
            self._ensure_database_exists()

            # Create connection pool
            self._pool = pool.ThreadedConnectionPool(
                self.config.min_connections,
                self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )

            logger.info(f"Connected to PostgreSQL at {self.config.host}:{self.config.port}/{self.config.database}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    def _ensure_database_exists(self):
        """Create database if it doesn't exist."""
        try:
            # Connect to default 'postgres' database
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database="postgres",
                user=self.config.user,
                password=self.config.password,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.config.database,)
            )

            if not cursor.fetchone():
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(self.config.database)
                    )
                )
                logger.info(f"Created database: {self.config.database}")

            cursor.close()
            conn.close()

        except Exception as e:
            logger.warning(f"Could not ensure database exists: {e}")

    def initialize(self):
        """
        Initialize database schema with PostGIS extension and all tables.
        Implements FSD Section 6 Data Model.
        """
        if not self._pool:
            if not self.connect():
                raise ConnectionError("Cannot connect to PostgreSQL")

        logger.info("Initializing PostgreSQL database schema...")

        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # Enable PostGIS extension (FSD 5.2)
            self._enable_postgis(cursor)

            # Create all tables
            self._create_tables(cursor)

            # Create indexes
            self._create_indexes(cursor)

            # Seed default data
            self._seed_defaults(cursor)

            conn.commit()
            self._initialized = True
            logger.info("PostgreSQL database initialized successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to initialize database: {e}")
            raise
        finally:
            self.return_connection(conn)

    def _enable_postgis(self, cursor):
        """Enable PostGIS extension for spatial queries."""
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
            logger.info("PostGIS extension enabled")
        except Exception as e:
            logger.warning(f"PostGIS may already be enabled or not available: {e}")

    def _create_tables(self, cursor):
        """Create all database tables per FSD Section 6."""

        # Users table (FSD 3: System Access Levels)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                password_salt VARCHAR(255),
                email VARCHAR(255),
                full_name VARCHAR(255),
                full_name_ar VARCHAR(255),
                role VARCHAR(50) NOT NULL DEFAULT 'analyst',
                is_active BOOLEAN DEFAULT TRUE,
                is_locked BOOLEAN DEFAULT FALSE,
                failed_attempts INTEGER DEFAULT 0,
                last_login TIMESTAMPTZ,
                last_activity TIMESTAMPTZ,
                password_changed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                CONSTRAINT valid_role CHECK (role IN ('admin', 'data_manager', 'office_clerk', 'field_supervisor', 'analyst'))
            )
        """)

        # Buildings table (FSD 6.1.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS buildings (
                building_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                building_id VARCHAR(20) UNIQUE NOT NULL,
                governorate_code VARCHAR(2) NOT NULL,
                governorate_name VARCHAR(100),
                governorate_name_ar VARCHAR(100),
                district_code VARCHAR(2) NOT NULL,
                district_name VARCHAR(100),
                district_name_ar VARCHAR(100),
                subdistrict_code VARCHAR(2) NOT NULL,
                subdistrict_name VARCHAR(100),
                subdistrict_name_ar VARCHAR(100),
                community_code VARCHAR(3) NOT NULL,
                community_name VARCHAR(100),
                community_name_ar VARCHAR(100),
                neighborhood_code VARCHAR(3) NOT NULL,
                neighborhood_name VARCHAR(100),
                neighborhood_name_ar VARCHAR(100),
                building_number VARCHAR(5) NOT NULL,
                building_type VARCHAR(50),
                building_status VARCHAR(50),
                number_of_units INTEGER DEFAULT 0,
                number_of_apartments INTEGER DEFAULT 0,
                number_of_shops INTEGER DEFAULT 0,
                number_of_floors INTEGER DEFAULT 1,
                geo_location GEOMETRY(Point, 4326),
                building_geometry GEOMETRY(Polygon, 4326),
                legacy_stdm_id VARCHAR(100),
                migration_date TIMESTAMPTZ,
                migration_status VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id),
                CONSTRAINT valid_building_id CHECK (
                    building_id ~ '^[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{3}-[0-9]{3}-[0-9]{5}$'
                )
            )
        """)

        # Property Units table (FSD 6.1.2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS property_units (
                unit_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                unit_id VARCHAR(25) UNIQUE NOT NULL,
                building_id VARCHAR(20) NOT NULL REFERENCES buildings(building_id),
                unit_type VARCHAR(50),
                unit_number VARCHAR(10),
                floor_number INTEGER DEFAULT 0,
                apartment_number VARCHAR(20),
                apartment_status VARCHAR(50),
                property_description TEXT,
                area_sqm DECIMAL(10,2),
                number_of_rooms INTEGER,
                legacy_stdm_id VARCHAR(100),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id),
                CONSTRAINT valid_unit_id CHECK (
                    unit_id ~ '^[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{3}-[0-9]{3}-[0-9]{5}-[0-9]{3}$'
                ),
                CONSTRAINT unique_unit_in_building UNIQUE (building_id, unit_number)
            )
        """)

        # Persons table (FSD 6.1.3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                person_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                first_name VARCHAR(100),
                first_name_ar VARCHAR(100),
                father_name VARCHAR(100),
                father_name_ar VARCHAR(100),
                mother_name VARCHAR(100),
                mother_name_ar VARCHAR(100),
                last_name VARCHAR(100),
                last_name_ar VARCHAR(100),
                gender VARCHAR(20),
                year_of_birth INTEGER,
                nationality VARCHAR(100),
                national_id VARCHAR(20),
                passport_number VARCHAR(50),
                phone_number VARCHAR(30),
                mobile_number VARCHAR(30),
                email VARCHAR(255),
                address TEXT,
                is_contact_person BOOLEAN DEFAULT FALSE,
                is_deceased BOOLEAN DEFAULT FALSE,
                legacy_stdm_id VARCHAR(100),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id),
                CONSTRAINT valid_national_id CHECK (
                    national_id IS NULL OR national_id ~ '^[0-9]{11}$'
                )
            )
        """)

        # Create unique index on national_id for duplicate detection (FSD FR-D-5)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_persons_national_id
            ON persons(national_id)
            WHERE national_id IS NOT NULL
        """)

        # Person-Unit Relations table (FSD 6.1.4)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS person_unit_relations (
                relation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                person_id UUID NOT NULL REFERENCES persons(person_id),
                unit_id VARCHAR(25) NOT NULL REFERENCES property_units(unit_id),
                relation_type VARCHAR(50) NOT NULL,
                relation_type_other_description TEXT,
                ownership_share INTEGER DEFAULT 0 CHECK (ownership_share >= 0 AND ownership_share <= 2400),
                tenure_contract_type VARCHAR(100),
                relation_start_date DATE,
                relation_end_date DATE,
                verification_status VARCHAR(50) DEFAULT 'pending',
                verification_date TIMESTAMPTZ,
                verified_by UUID REFERENCES users(user_id),
                relation_notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id),
                CONSTRAINT valid_verification_status CHECK (
                    verification_status IN ('pending', 'verified', 'rejected')
                ),
                CONSTRAINT valid_relation_type CHECK (
                    relation_type IN ('owner', 'tenant', 'heir', 'guest', 'occupant', 'other')
                )
            )
        """)

        # Documents table (FSD 6.2.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_type VARCHAR(100),
                document_number VARCHAR(100),
                issue_date DATE,
                expiry_date DATE,
                issuing_authority VARCHAR(255),
                issuing_location VARCHAR(255),
                verified BOOLEAN DEFAULT FALSE,
                verified_by UUID REFERENCES users(user_id),
                verification_date TIMESTAMPTZ,
                attachment_path TEXT,
                attachment_hash VARCHAR(64),
                attachment_size BIGINT,
                mime_type VARCHAR(100),
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id)
            )
        """)

        # Attachments table for SHA-256 deduplication (FSD FR-D-9)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                sha256_hash VARCHAR(64) UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                file_size BIGINT NOT NULL,
                mime_type VARCHAR(100),
                original_filename VARCHAR(255),
                upload_date TIMESTAMPTZ DEFAULT NOW(),
                uploaded_by UUID REFERENCES users(user_id),
                reference_count INTEGER DEFAULT 1
            )
        """)

        # Evidence table (FSD 6.1.5)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                relation_id UUID NOT NULL REFERENCES person_unit_relations(relation_id),
                document_id UUID REFERENCES documents(document_id),
                reference_number VARCHAR(100),
                reference_date DATE,
                evidence_description TEXT,
                evidence_type VARCHAR(100),
                verification_status VARCHAR(50) DEFAULT 'pending',
                verification_notes TEXT,
                verified_by UUID REFERENCES users(user_id),
                verification_date TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id)
            )
        """)

        # Households/Occupancy table (FSD 6.1.6)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS households (
                household_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                unit_id VARCHAR(25) NOT NULL REFERENCES property_units(unit_id),
                main_occupant_id UUID REFERENCES persons(person_id),
                main_occupant_name VARCHAR(255),
                occupancy_size INTEGER DEFAULT 1,
                male_count INTEGER DEFAULT 0,
                female_count INTEGER DEFAULT 0,
                minors_count INTEGER DEFAULT 0,
                adults_count INTEGER DEFAULT 0,
                elderly_count INTEGER DEFAULT 0,
                with_disability_count INTEGER DEFAULT 0,
                occupancy_type VARCHAR(50),
                occupancy_nature VARCHAR(50),
                occupancy_start_date DATE,
                monthly_rent DECIMAL(12,2),
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id)
            )
        """)

        # Claims table (FSD 6.1.7)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_id VARCHAR(20) UNIQUE NOT NULL,
                case_number VARCHAR(50),
                source VARCHAR(50) NOT NULL DEFAULT 'office_submission',
                unit_id VARCHAR(25) NOT NULL REFERENCES property_units(unit_id),
                case_status VARCHAR(50) NOT NULL DEFAULT 'draft',
                lifecycle_stage VARCHAR(50),
                claim_type VARCHAR(50),
                priority VARCHAR(20) DEFAULT 'normal',
                assigned_to UUID REFERENCES users(user_id),
                assigned_date TIMESTAMPTZ,
                awaiting_documents BOOLEAN DEFAULT FALSE,
                submission_date TIMESTAMPTZ,
                decision_date TIMESTAMPTZ,
                notes TEXT,
                resolution_notes TEXT,
                has_conflict BOOLEAN DEFAULT FALSE,
                legacy_stdm_id VARCHAR(100),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id),
                CONSTRAINT valid_claim_id CHECK (
                    claim_id ~ '^CL-[0-9]{4}-[0-9]{6}$'
                ),
                CONSTRAINT valid_source CHECK (
                    source IN ('field_collection', 'office_submission', 'system_import')
                ),
                CONSTRAINT valid_case_status CHECK (
                    case_status IN ('draft', 'submitted', 'screening', 'under_review',
                                   'awaiting_docs', 'conflict', 'approved', 'rejected')
                )
            )
        """)

        # Claim-Person junction table (multiple claimants per claim)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_persons (
                id SERIAL PRIMARY KEY,
                claim_uuid UUID NOT NULL REFERENCES claims(claim_uuid) ON DELETE CASCADE,
                person_id UUID NOT NULL REFERENCES persons(person_id),
                is_primary BOOLEAN DEFAULT FALSE,
                added_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(claim_uuid, person_id)
            )
        """)

        # Claim-Relation junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_relations (
                id SERIAL PRIMARY KEY,
                claim_uuid UUID NOT NULL REFERENCES claims(claim_uuid) ON DELETE CASCADE,
                relation_id UUID NOT NULL REFERENCES person_unit_relations(relation_id),
                added_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(claim_uuid, relation_id)
            )
        """)

        # Claim conflicts table (FSD FR-D-7)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_conflicts (
                conflict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_uuid_1 UUID NOT NULL REFERENCES claims(claim_uuid),
                claim_uuid_2 UUID NOT NULL REFERENCES claims(claim_uuid),
                conflict_type VARCHAR(50),
                conflict_description TEXT,
                detected_at TIMESTAMPTZ DEFAULT NOW(),
                resolved_at TIMESTAMPTZ,
                resolved_by UUID REFERENCES users(user_id),
                resolution_type VARCHAR(50),
                resolution_notes TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                CONSTRAINT different_claims CHECK (claim_uuid_1 != claim_uuid_2)
            )
        """)

        # Claim documents junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_documents (
                id SERIAL PRIMARY KEY,
                claim_uuid UUID NOT NULL REFERENCES claims(claim_uuid) ON DELETE CASCADE,
                document_id UUID NOT NULL REFERENCES documents(document_id),
                added_at TIMESTAMPTZ DEFAULT NOW(),
                added_by UUID REFERENCES users(user_id),
                removed_at TIMESTAMPTZ,
                removed_by UUID REFERENCES users(user_id),
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE(claim_uuid, document_id)
            )
        """)

        # Claim history for audit trail (FSD 13.4)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claim_history (
                history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_uuid UUID NOT NULL REFERENCES claims(claim_uuid),
                claim_id VARCHAR(20) NOT NULL,
                snapshot_data JSONB NOT NULL,
                change_type VARCHAR(50) NOT NULL,
                change_reason TEXT,
                changed_fields TEXT[],
                changed_by UUID REFERENCES users(user_id),
                changed_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Referrals table (FSD 6.1.8)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_uuid UUID NOT NULL REFERENCES claims(claim_uuid),
                from_role VARCHAR(50) NOT NULL,
                to_role VARCHAR(50) NOT NULL,
                referral_reason VARCHAR(100),
                referral_notes TEXT,
                referral_date TIMESTAMPTZ DEFAULT NOW(),
                referred_by UUID REFERENCES users(user_id),
                status VARCHAR(50) DEFAULT 'pending',
                resolved_at TIMESTAMPTZ,
                resolved_by UUID REFERENCES users(user_id)
            )
        """)

        # Surveys table (FSD 6.2.2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                building_id VARCHAR(20) REFERENCES buildings(building_id),
                unit_id VARCHAR(25) REFERENCES property_units(unit_id),
                field_collector_id UUID REFERENCES users(user_id),
                survey_date DATE,
                survey_type VARCHAR(50),
                status VARCHAR(50) DEFAULT 'draft',
                reference_code VARCHAR(50),
                source VARCHAR(50) DEFAULT 'field',
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                finalized_at TIMESTAMPTZ,
                CONSTRAINT valid_survey_status CHECK (status IN ('draft', 'finalized'))
            )
        """)

        # Building assignments table (FSD 6.2.3, UC-012)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS building_assignments (
                assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                building_id VARCHAR(20) NOT NULL REFERENCES buildings(building_id),
                assigned_to UUID REFERENCES users(user_id),
                field_team_name VARCHAR(100),
                tablet_device_id VARCHAR(100),
                assignment_status VARCHAR(50) DEFAULT 'pending',
                assignment_date TIMESTAMPTZ,
                assigned_by UUID REFERENCES users(user_id),
                transfer_status VARCHAR(50) DEFAULT 'not_transferred',
                transfer_date TIMESTAMPTZ,
                transfer_error TEXT,
                requires_revisit BOOLEAN DEFAULT FALSE,
                revisit_reason TEXT,
                units_for_revisit TEXT[],
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Import history table (FSD FR-D-2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                import_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                package_id UUID UNIQUE NOT NULL,
                file_name VARCHAR(255),
                file_path TEXT,
                file_hash VARCHAR(64),
                import_date TIMESTAMPTZ DEFAULT NOW(),
                imported_by UUID REFERENCES users(user_id),
                status VARCHAR(50) DEFAULT 'pending',
                total_records INTEGER DEFAULT 0,
                imported_records INTEGER DEFAULT 0,
                failed_records INTEGER DEFAULT 0,
                warnings_count INTEGER DEFAULT 0,
                schema_version VARCHAR(20),
                app_version VARCHAR(20),
                device_id VARCHAR(100),
                vocab_versions JSONB,
                validation_report JSONB,
                errors JSONB,
                notes TEXT
            )
        """)

        # Staging tables for import validation (FSD FR-D-4)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staging_buildings (
                id SERIAL PRIMARY KEY,
                import_id UUID NOT NULL REFERENCES import_history(import_id) ON DELETE CASCADE,
                data JSONB NOT NULL,
                validation_status VARCHAR(50) DEFAULT 'pending',
                validation_errors JSONB,
                processed_at TIMESTAMPTZ,
                committed_at TIMESTAMPTZ
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staging_persons (
                id SERIAL PRIMARY KEY,
                import_id UUID NOT NULL REFERENCES import_history(import_id) ON DELETE CASCADE,
                data JSONB NOT NULL,
                validation_status VARCHAR(50) DEFAULT 'pending',
                validation_errors JSONB,
                duplicate_of UUID REFERENCES persons(person_id),
                processed_at TIMESTAMPTZ,
                committed_at TIMESTAMPTZ
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staging_units (
                id SERIAL PRIMARY KEY,
                import_id UUID NOT NULL REFERENCES import_history(import_id) ON DELETE CASCADE,
                data JSONB NOT NULL,
                validation_status VARCHAR(50) DEFAULT 'pending',
                validation_errors JSONB,
                processed_at TIMESTAMPTZ,
                committed_at TIMESTAMPTZ
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staging_claims (
                id SERIAL PRIMARY KEY,
                import_id UUID NOT NULL REFERENCES import_history(import_id) ON DELETE CASCADE,
                data JSONB NOT NULL,
                validation_status VARCHAR(50) DEFAULT 'pending',
                validation_errors JSONB,
                processed_at TIMESTAMPTZ,
                committed_at TIMESTAMPTZ
            )
        """)

        # Duplicate candidates table (FSD FR-D-5, FR-D-6, UC-007, UC-008)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_candidates (
                candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_type VARCHAR(50) NOT NULL,
                group_key VARCHAR(255) NOT NULL,
                record_ids UUID[] NOT NULL,
                match_score DECIMAL(5,2),
                match_reasons JSONB,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                CONSTRAINT valid_entity_type CHECK (entity_type IN ('person', 'property', 'claim'))
            )
        """)

        # Duplicate resolutions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_resolutions (
                resolution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                candidate_id UUID REFERENCES duplicate_candidates(candidate_id),
                entity_type VARCHAR(50) NOT NULL,
                group_key VARCHAR(255) NOT NULL,
                record_ids UUID[] NOT NULL,
                resolution_type VARCHAR(50) NOT NULL,
                master_record_id UUID,
                justification TEXT,
                resolved_by UUID REFERENCES users(user_id),
                resolved_at TIMESTAMPTZ DEFAULT NOW(),
                status VARCHAR(50) DEFAULT 'completed',
                CONSTRAINT valid_resolution_type CHECK (
                    resolution_type IN ('merge', 'keep_separate', 'field_verification', 'escalated')
                )
            )
        """)

        # Vocabulary terms table (FSD Section 7, UC-010)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary_terms (
                term_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                vocabulary_name VARCHAR(100) NOT NULL,
                term_code VARCHAR(100) NOT NULL,
                term_label VARCHAR(255) NOT NULL,
                term_label_ar VARCHAR(255),
                status VARCHAR(50) DEFAULT 'active',
                effective_from DATE,
                effective_to DATE,
                version_major INTEGER DEFAULT 1,
                version_minor INTEGER DEFAULT 0,
                version_patch INTEGER DEFAULT 0,
                source VARCHAR(50) DEFAULT 'manual',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                created_by UUID REFERENCES users(user_id),
                updated_by UUID REFERENCES users(user_id),
                UNIQUE(vocabulary_name, term_code)
            )
        """)

        # Security settings table (UC-011)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_settings (
                setting_id VARCHAR(50) PRIMARY KEY DEFAULT 'default',
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
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by UUID REFERENCES users(user_id)
            )
        """)

        # Audit log table (FSD 13.2, UC-011)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                user_id UUID REFERENCES users(user_id),
                username VARCHAR(100),
                device_id VARCHAR(100),
                action VARCHAR(100) NOT NULL,
                entity_type VARCHAR(100),
                entity_id VARCHAR(255),
                field VARCHAR(100),
                old_values JSONB,
                new_values JSONB,
                ip_address INET,
                package_id UUID,
                details TEXT,
                signature VARCHAR(255)
            )
        """)

        # UHC containers archive (FSD 13.5)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uhc_archives (
                archive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                package_id UUID UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                file_hash VARCHAR(64) NOT NULL,
                file_size BIGINT NOT NULL,
                signature VARCHAR(255),
                import_id UUID REFERENCES import_history(import_id),
                archived_at TIMESTAMPTZ DEFAULT NOW(),
                archived_by UUID REFERENCES users(user_id)
            )
        """)

        logger.info("All tables created successfully")

    def _create_indexes(self, cursor):
        """Create indexes for performance optimization."""

        # Spatial indexes for PostGIS (FSD FR-D-6)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_buildings_geo_location
            ON buildings USING GIST (geo_location)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_buildings_geometry
            ON buildings USING GIST (building_geometry)
        """)

        # Buildings indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_neighborhood ON buildings(neighborhood_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_status ON buildings(building_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_buildings_legacy ON buildings(legacy_stdm_id)")

        # Units indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_building ON property_units(building_id)")

        # Persons indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(last_name_ar, first_name_ar)")

        # Relations indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_person ON person_unit_relations(person_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relations_unit ON person_unit_relations(unit_id)")

        # Claims indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(case_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_unit ON claims(unit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_assigned ON claims(assigned_to)")

        # Claim history indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_history_claim ON claim_history(claim_uuid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_history_date ON claim_history(changed_at)")

        # Audit log indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id)")

        # Import history indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_package ON import_history(package_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_status ON import_history(status)")

        # Duplicate candidates indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_candidates_type ON duplicate_candidates(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_candidates_status ON duplicate_candidates(status)")

        # Vocabulary indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_name ON vocabulary_terms(vocabulary_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary_terms(status)")

        # Attachments indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_hash ON attachments(sha256_hash)")

        logger.info("All indexes created successfully")

    def _seed_defaults(self, cursor):
        """Seed default data if tables are empty."""

        # Check if vocabularies exist
        cursor.execute("SELECT COUNT(*) FROM vocabulary_terms")
        if cursor.fetchone()[0] == 0:
            self._seed_vocabularies(cursor)

        # Check if security settings exist
        cursor.execute("SELECT COUNT(*) FROM security_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO security_settings (setting_id) VALUES ('default')
            """)

        logger.info("Default data seeded successfully")

    def _seed_vocabularies(self, cursor):
        """Seed default vocabulary terms."""

        vocabularies = {
            "building_type": [
                ("residential", "Residential", "سكني"),
                ("commercial", "Commercial", "تجاري"),
                ("mixed_use", "Mixed Use", "متعدد الاستخدامات"),
                ("industrial", "Industrial", "صناعي"),
                ("public", "Public", "عام"),
            ],
            "building_status": [
                ("intact", "Intact", "سليم"),
                ("minor_damage", "Minor Damage", "ضرر طفيف"),
                ("major_damage", "Major Damage", "ضرر كبير"),
                ("destroyed", "Destroyed", "مدمر"),
                ("under_construction", "Under Construction", "قيد البناء"),
            ],
            "unit_type": [
                ("apartment", "Apartment", "شقة"),
                ("shop", "Shop", "محل"),
                ("office", "Office", "مكتب"),
                ("warehouse", "Warehouse", "مستودع"),
                ("garage", "Garage", "كراج"),
                ("other", "Other", "آخر"),
            ],
            "relation_type": [
                ("owner", "Owner", "مالك"),
                ("tenant", "Tenant", "مستأجر"),
                ("heir", "Heir", "وريث"),
                ("guest", "Guest", "ضيف"),
                ("occupant", "Occupant", "شاغل"),
                ("other", "Other", "آخر"),
            ],
            "case_status": [
                ("draft", "Draft", "مسودة"),
                ("submitted", "Submitted", "مقدمة"),
                ("screening", "Screening", "تدقيق أولي"),
                ("under_review", "Under Review", "قيد المراجعة"),
                ("awaiting_docs", "Awaiting Documents", "بانتظار الوثائق"),
                ("conflict", "Conflict", "تعارض"),
                ("approved", "Approved", "موافق عليها"),
                ("rejected", "Rejected", "مرفوضة"),
            ],
            "document_type": [
                ("TAPU_GREEN", "Property Deed (Green TaPu)", "سند ملكية (طابو أخضر)"),
                ("PROPERTY_REG", "Property Registration Statement", "بيان قيد عقاري"),
                ("TEMP_REG", "Temporary Registration Statement", "بيان قيد مؤقت"),
                ("COURT_RULING", "Court Ruling", "حكم محكمة"),
                ("POWER_ATTORNEY", "Special Power of Attorney", "وكالة خاصة"),
                ("SALE_NOTARIZED", "Notarized Sale Contract", "عقد بيع موثق"),
                ("SALE_INFORMAL", "Informal Sale Contract", "عقد بيع عرفي"),
                ("RENT_REGISTERED", "Registered Rental Contract", "عقد إيجار مسجل"),
                ("RENT_INFORMAL", "Informal Rental Contract", "عقد إيجار عرفي"),
                ("UTILITY_BILL", "Utility Bill", "فاتورة خدمات"),
                ("MUKHTAR_CERT", "Mukhtar Certificate", "شهادة مختار"),
                ("CLAIMANT_STATEMENT", "Claimant Statement", "إفادة مدعي"),
                ("WITNESS_STATEMENT", "Witness Statement", "شهادة شاهد"),
            ],
            "verification_status": [
                ("pending", "Pending", "قيد الانتظار"),
                ("verified", "Verified", "تم التحقق"),
                ("rejected", "Rejected", "مرفوض"),
            ],
        }

        for vocab_name, terms in vocabularies.items():
            for code, label_en, label_ar in terms:
                cursor.execute("""
                    INSERT INTO vocabulary_terms
                    (vocabulary_name, term_code, term_label, term_label_ar)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (vocabulary_name, term_code) DO NOTHING
                """, (vocab_name, code, label_en, label_ar))

        logger.info("Vocabulary terms seeded successfully")

    def get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            self.connect()
        return self._pool.getconn()

    def return_connection(self, conn):
        """Return a connection to the pool."""
        if self._pool:
            self._pool.putconn(conn)

    @contextmanager
    def cursor(self):
        """Context manager for database cursor with automatic commit/rollback."""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            self.return_connection(conn)

    @contextmanager
    def transaction(self):
        """Context manager for explicit transaction control."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction error: {e}")
            raise
        finally:
            self.return_connection(conn)

    def execute(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a query and return results."""
        with self.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchall()
            return []

    def execute_one(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute a query and return one row."""
        with self.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchone()
            return None

    def execute_many(self, query: str, params_list: List[tuple]):
        """Execute a query with multiple parameter sets."""
        with self.cursor() as cursor:
            cursor.executemany(query, params_list)

    def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._pool is not None

    def get_version(self) -> str:
        """Get PostgreSQL version."""
        result = self.execute_one("SELECT version()")
        return result["version"] if result else "Unknown"

    def has_postgis(self) -> bool:
        """Check if PostGIS is available."""
        result = self.execute_one(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
        )
        return result["exists"] if result else False
