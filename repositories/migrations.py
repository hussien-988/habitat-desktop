# -*- coding: utf-8 -*-
"""
Database migrations system for PostgreSQL.
Tracks and applies schema changes incrementally.
"""

from typing import List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Migration:
    """Represents a database migration."""
    version: str
    name: str
    up_sql: str
    down_sql: str = ""
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = hashlib.md5(self.up_sql.encode()).hexdigest()


class MigrationManager:
    """
    Manages database migrations.

    Usage:
        manager = MigrationManager(db)
        manager.migrate()  # Apply all pending migrations
    """

    def __init__(self, db):
        self.db = db
        self._migrations: List[Migration] = []
        self._register_migrations()

    def _register_migrations(self):
        """Register all migrations in order."""

        # V001: Initial PostGIS setup
        self._migrations.append(Migration(
            version="001",
            name="enable_postgis",
            up_sql="""
                CREATE EXTENSION IF NOT EXISTS postgis;
                CREATE EXTENSION IF NOT EXISTS postgis_topology;
            """,
            down_sql="-- Cannot disable PostGIS safely"
        ))

        # V002: Add building geometry column if not exists
        self._migrations.append(Migration(
            version="002",
            name="add_building_geometry",
            up_sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'buildings' AND column_name = 'building_geometry'
                    ) THEN
                        ALTER TABLE buildings
                        ADD COLUMN building_geometry GEOMETRY(Polygon, 4326);
                    END IF;
                END $$;
            """,
            down_sql="ALTER TABLE buildings DROP COLUMN IF EXISTS building_geometry;"
        ))

        # V003: Add spatial indexes
        self._migrations.append(Migration(
            version="003",
            name="add_spatial_indexes",
            up_sql="""
                CREATE INDEX IF NOT EXISTS idx_buildings_geo_location
                ON buildings USING GIST (geo_location);

                CREATE INDEX IF NOT EXISTS idx_buildings_geometry
                ON buildings USING GIST (building_geometry);
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_buildings_geo_location;
                DROP INDEX IF EXISTS idx_buildings_geometry;
            """
        ))

        # V004: Add staging tables for import
        self._migrations.append(Migration(
            version="004",
            name="add_staging_tables",
            up_sql="""
                CREATE TABLE IF NOT EXISTS staging_buildings (
                    id SERIAL PRIMARY KEY,
                    import_id UUID NOT NULL,
                    data JSONB NOT NULL,
                    validation_status VARCHAR(50) DEFAULT 'pending',
                    validation_errors JSONB,
                    processed_at TIMESTAMPTZ,
                    committed_at TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS staging_persons (
                    id SERIAL PRIMARY KEY,
                    import_id UUID NOT NULL,
                    data JSONB NOT NULL,
                    validation_status VARCHAR(50) DEFAULT 'pending',
                    validation_errors JSONB,
                    duplicate_of UUID,
                    processed_at TIMESTAMPTZ,
                    committed_at TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS staging_units (
                    id SERIAL PRIMARY KEY,
                    import_id UUID NOT NULL,
                    data JSONB NOT NULL,
                    validation_status VARCHAR(50) DEFAULT 'pending',
                    validation_errors JSONB,
                    processed_at TIMESTAMPTZ,
                    committed_at TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS staging_claims (
                    id SERIAL PRIMARY KEY,
                    import_id UUID NOT NULL,
                    data JSONB NOT NULL,
                    validation_status VARCHAR(50) DEFAULT 'pending',
                    validation_errors JSONB,
                    processed_at TIMESTAMPTZ,
                    committed_at TIMESTAMPTZ
                );
            """,
            down_sql="""
                DROP TABLE IF EXISTS staging_claims;
                DROP TABLE IF EXISTS staging_units;
                DROP TABLE IF EXISTS staging_persons;
                DROP TABLE IF EXISTS staging_buildings;
            """
        ))

        # V005: Add duplicate detection tables
        self._migrations.append(Migration(
            version="005",
            name="add_duplicate_tables",
            up_sql="""
                CREATE TABLE IF NOT EXISTS duplicate_candidates (
                    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    entity_type VARCHAR(50) NOT NULL,
                    group_key VARCHAR(255) NOT NULL,
                    record_ids UUID[] NOT NULL,
                    match_score DECIMAL(5,2),
                    match_reasons JSONB,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_dup_candidates_type
                ON duplicate_candidates(entity_type);

                CREATE INDEX IF NOT EXISTS idx_dup_candidates_status
                ON duplicate_candidates(status);
            """,
            down_sql="DROP TABLE IF EXISTS duplicate_candidates;"
        ))

        # V006: Add attachments table with SHA-256 deduplication
        self._migrations.append(Migration(
            version="006",
            name="add_attachments_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS attachments (
                    attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    sha256_hash VARCHAR(64) UNIQUE NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size BIGINT NOT NULL,
                    mime_type VARCHAR(100),
                    original_filename VARCHAR(255),
                    upload_date TIMESTAMPTZ DEFAULT NOW(),
                    uploaded_by UUID,
                    reference_count INTEGER DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_attachments_hash
                ON attachments(sha256_hash);
            """,
            down_sql="DROP TABLE IF EXISTS attachments;"
        ))

        # V007: Add UHC archives table
        self._migrations.append(Migration(
            version="007",
            name="add_uhc_archives",
            up_sql="""
                CREATE TABLE IF NOT EXISTS uhc_archives (
                    archive_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    package_id UUID UNIQUE NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash VARCHAR(64) NOT NULL,
                    file_size BIGINT NOT NULL,
                    signature VARCHAR(255),
                    import_id UUID,
                    archived_at TIMESTAMPTZ DEFAULT NOW(),
                    archived_by UUID
                );

                CREATE INDEX IF NOT EXISTS idx_uhc_archives_package
                ON uhc_archives(package_id);
            """,
            down_sql="DROP TABLE IF EXISTS uhc_archives;"
        ))

        # V008: Add households table
        self._migrations.append(Migration(
            version="008",
            name="add_households_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS households (
                    household_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    unit_id VARCHAR(25) NOT NULL,
                    main_occupant_id UUID,
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
                    created_by UUID,
                    updated_by UUID
                );

                CREATE INDEX IF NOT EXISTS idx_households_unit
                ON households(unit_id);
            """,
            down_sql="DROP TABLE IF EXISTS households;"
        ))

        # V009: Add referrals table
        self._migrations.append(Migration(
            version="009",
            name="add_referrals_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS referrals (
                    referral_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    claim_uuid UUID NOT NULL,
                    from_role VARCHAR(50) NOT NULL,
                    to_role VARCHAR(50) NOT NULL,
                    referral_reason VARCHAR(100),
                    referral_notes TEXT,
                    referral_date TIMESTAMPTZ DEFAULT NOW(),
                    referred_by UUID,
                    status VARCHAR(50) DEFAULT 'pending',
                    resolved_at TIMESTAMPTZ,
                    resolved_by UUID
                );

                CREATE INDEX IF NOT EXISTS idx_referrals_claim
                ON referrals(claim_uuid);

                CREATE INDEX IF NOT EXISTS idx_referrals_status
                ON referrals(status);
            """,
            down_sql="DROP TABLE IF EXISTS referrals;"
        ))

        # V010: Add claim conflicts table
        self._migrations.append(Migration(
            version="010",
            name="add_claim_conflicts",
            up_sql="""
                CREATE TABLE IF NOT EXISTS claim_conflicts (
                    conflict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    claim_uuid_1 UUID NOT NULL,
                    claim_uuid_2 UUID NOT NULL,
                    conflict_type VARCHAR(50),
                    conflict_description TEXT,
                    detected_at TIMESTAMPTZ DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ,
                    resolved_by UUID,
                    resolution_type VARCHAR(50),
                    resolution_notes TEXT,
                    status VARCHAR(50) DEFAULT 'pending'
                );

                CREATE INDEX IF NOT EXISTS idx_conflicts_status
                ON claim_conflicts(status);
            """,
            down_sql="DROP TABLE IF EXISTS claim_conflicts;"
        ))

        # V011: Add surveys table
        self._migrations.append(Migration(
            version="011",
            name="add_surveys_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS surveys (
                    survey_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    building_id VARCHAR(20),
                    unit_id VARCHAR(25),
                    field_collector_id UUID,
                    survey_date DATE,
                    survey_type VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'draft',
                    reference_code VARCHAR(50),
                    source VARCHAR(50) DEFAULT 'field',
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    finalized_at TIMESTAMPTZ
                );

                CREATE INDEX IF NOT EXISTS idx_surveys_building
                ON surveys(building_id);

                CREATE INDEX IF NOT EXISTS idx_surveys_status
                ON surveys(status);
            """,
            down_sql="DROP TABLE IF EXISTS surveys;"
        ))

        # V012: Add legacy STDM columns
        self._migrations.append(Migration(
            version="012",
            name="add_legacy_stdm_columns",
            up_sql="""
                DO $$
                BEGIN
                    -- Add to buildings
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'buildings' AND column_name = 'legacy_stdm_id'
                    ) THEN
                        ALTER TABLE buildings ADD COLUMN legacy_stdm_id VARCHAR(100);
                        ALTER TABLE buildings ADD COLUMN migration_date TIMESTAMPTZ;
                        ALTER TABLE buildings ADD COLUMN migration_status VARCHAR(50);
                    END IF;

                    -- Add to property_units
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'property_units' AND column_name = 'legacy_stdm_id'
                    ) THEN
                        ALTER TABLE property_units ADD COLUMN legacy_stdm_id VARCHAR(100);
                    END IF;

                    -- Add to persons
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'persons' AND column_name = 'legacy_stdm_id'
                    ) THEN
                        ALTER TABLE persons ADD COLUMN legacy_stdm_id VARCHAR(100);
                    END IF;

                    -- Add to claims
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'claims' AND column_name = 'legacy_stdm_id'
                    ) THEN
                        ALTER TABLE claims ADD COLUMN legacy_stdm_id VARCHAR(100);
                    END IF;
                END $$;
            """,
            down_sql="""
                ALTER TABLE buildings DROP COLUMN IF EXISTS legacy_stdm_id;
                ALTER TABLE buildings DROP COLUMN IF EXISTS migration_date;
                ALTER TABLE buildings DROP COLUMN IF EXISTS migration_status;
                ALTER TABLE property_units DROP COLUMN IF EXISTS legacy_stdm_id;
                ALTER TABLE persons DROP COLUMN IF EXISTS legacy_stdm_id;
                ALTER TABLE claims DROP COLUMN IF EXISTS legacy_stdm_id;
            """
        ))

        # V013: Add context_data column to surveys table
        self._migrations.append(Migration(
            version="013",
            name="add_surveys_context_data",
            up_sql="""
                DO $$
                BEGIN
                    -- Add context_data column to surveys table for UC-005
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'surveys' AND column_name = 'context_data'
                    ) THEN
                        ALTER TABLE surveys ADD COLUMN context_data JSONB;
                    END IF;

                    -- Add index for JSON queries
                    CREATE INDEX IF NOT EXISTS idx_surveys_context_data
                    ON surveys USING gin(context_data);
                END $$;
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_surveys_context_data;
                ALTER TABLE surveys DROP COLUMN IF EXISTS context_data;
            """
        ))

    def _ensure_migrations_table(self, cursor):
        """Create migrations tracking table if it doesn't exist."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(20) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                checksum VARCHAR(32) NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW(),
                applied_by VARCHAR(100)
            )
        """)

    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        with self.db.cursor() as cursor:
            self._ensure_migrations_table(cursor)
            cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
            return [row['version'] for row in cursor.fetchall()]

    def get_pending_migrations(self) -> List[Migration]:
        """Get list of migrations not yet applied."""
        applied = set(self.get_applied_migrations())
        return [m for m in self._migrations if m.version not in applied]

    def migrate(self, target_version: Optional[str] = None) -> List[str]:
        """
        Apply pending migrations.

        Args:
            target_version: Apply up to this version (None = all)

        Returns:
            List of applied migration versions
        """
        applied = []
        pending = self.get_pending_migrations()

        if not pending:
            logger.info("No pending migrations")
            return applied

        for migration in pending:
            if target_version and migration.version > target_version:
                break

            try:
                self._apply_migration(migration)
                applied.append(migration.version)
                logger.info(f"Applied migration {migration.version}: {migration.name}")
            except Exception as e:
                logger.error(f"Failed to apply migration {migration.version}: {e}")
                raise

        return applied

    def _apply_migration(self, migration: Migration):
        """Apply a single migration."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()

            # Apply the migration SQL
            cursor.execute(migration.up_sql)

            # Record the migration
            cursor.execute("""
                INSERT INTO schema_migrations (version, name, checksum)
                VALUES (%s, %s, %s)
            """, (migration.version, migration.name, migration.checksum))

    def rollback(self, target_version: str) -> List[str]:
        """
        Rollback migrations to target version.

        Args:
            target_version: Rollback to this version (exclusive)

        Returns:
            List of rolled back migration versions
        """
        rolled_back = []
        applied = self.get_applied_migrations()

        # Get migrations to rollback (in reverse order)
        to_rollback = [
            m for m in reversed(self._migrations)
            if m.version in applied and m.version > target_version
        ]

        for migration in to_rollback:
            if not migration.down_sql:
                logger.warning(f"Migration {migration.version} has no rollback SQL")
                continue

            try:
                self._rollback_migration(migration)
                rolled_back.append(migration.version)
                logger.info(f"Rolled back migration {migration.version}: {migration.name}")
            except Exception as e:
                logger.error(f"Failed to rollback migration {migration.version}: {e}")
                raise

        return rolled_back

    def _rollback_migration(self, migration: Migration):
        """Rollback a single migration."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()

            # Apply the rollback SQL
            cursor.execute(migration.down_sql)

            # Remove migration record
            cursor.execute(
                "DELETE FROM schema_migrations WHERE version = %s",
                (migration.version,)
            )

    def status(self) -> dict:
        """Get migration status."""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()

        return {
            "current_version": applied[-1] if applied else None,
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied": applied,
            "pending": [m.version for m in pending]
        }
