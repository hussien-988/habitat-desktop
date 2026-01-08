"""
Import Wizard Service
=====================
Implements comprehensive data import functionality as per UC-002 specifications.

Features:
- Multi-format support (CSV, Excel, JSON, GeoJSON, Shapefile)
- Watched folder monitoring for automatic imports
- Data validation and transformation
- Column mapping interface
- Duplicate detection during import
- Staging area for review before commit
- Import progress tracking and reporting
- Rollback capability
- Coordinate system transformation
- Encoding detection and handling
"""

import json
import csv
import hashlib
import shutil
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Callable, Generator
import logging
import uuid
import re

from repositories.db_adapter import DatabaseFactory, DatabaseAdapter, RowProxy

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas not available - Excel import disabled")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    logger.warning("watchdog not available - folder monitoring disabled")


class ImportFormat(Enum):
    """Supported import formats."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    GEOJSON = "geojson"
    SHAPEFILE = "shapefile"


class ImportStatus(Enum):
    """Status of an import job."""
    PENDING = "pending"
    VALIDATING = "validating"
    STAGING = "staging"
    REVIEWING = "reviewing"
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ValidationSeverity(Enum):
    """Severity of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class EntityTarget(Enum):
    """Target entity types for import."""
    BUILDING = "building"
    CLAIM = "claim"
    PERSON = "person"
    OWNERSHIP = "ownership"
    DOCUMENT = "document"


@dataclass
class ColumnMapping:
    """Mapping between source column and target field."""
    source_column: str
    target_field: str
    data_type: str = "text"  # text, integer, float, date, boolean, geometry
    is_required: bool = False
    default_value: Any = None
    transformation: Optional[str] = None  # e.g., "uppercase", "trim", "date_format"
    validation_regex: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationIssue:
    """Represents a validation issue found during import."""
    row_number: int
    column: str
    value: Any
    severity: ValidationSeverity
    message: str
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_number": self.row_number,
            "column": self.column,
            "value": str(self.value),
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion
        }


@dataclass
class ImportStatistics:
    """Statistics for an import job."""
    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    skipped_rows: int = 0
    imported_rows: int = 0
    errors: int = 0
    warnings: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
            "duplicate_rows": self.duplicate_rows,
            "skipped_rows": self.skipped_rows,
            "imported_rows": self.imported_rows,
            "errors": self.errors,
            "warnings": self.warnings,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None
        }


@dataclass
class ImportJob:
    """Represents an import job."""
    job_id: str
    file_name: str
    file_path: str
    file_format: ImportFormat
    target_entity: EntityTarget
    status: ImportStatus = ImportStatus.PENDING
    column_mappings: List[ColumnMapping] = field(default_factory=list)
    statistics: ImportStatistics = field(default_factory=ImportStatistics)
    validation_issues: List[ValidationIssue] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    completed_at: Optional[datetime] = None
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_format": self.file_format.value,
            "target_entity": self.target_entity.value,
            "status": self.status.value,
            "column_mappings": [m.to_dict() for m in self.column_mappings],
            "statistics": self.statistics.to_dict(),
            "validation_issues_count": len(self.validation_issues),
            "options": self.options,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message
        }


@dataclass
class WatchedFolder:
    """Configuration for a watched folder."""
    folder_id: str
    path: str
    target_entity: EntityTarget
    file_pattern: str = "*.*"  # Glob pattern
    auto_import: bool = False
    column_mappings: List[ColumnMapping] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder_id": self.folder_id,
            "path": self.path,
            "target_entity": self.target_entity.value,
            "file_pattern": self.file_pattern,
            "auto_import": self.auto_import,
            "column_mappings": [m.to_dict() for m in self.column_mappings],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by
        }


class ImportWizardService:
    """
    Comprehensive import wizard service.

    Implements UC-002 requirements:
    - Multi-format file import
    - Column mapping with transformations
    - Data validation
    - Duplicate detection
    - Staging area review
    - Watched folder monitoring
    - Import rollback
    """

    # Target field definitions per entity type
    ENTITY_FIELDS = {
        EntityTarget.BUILDING: {
            "building_id": {"type": "text", "required": True, "description": "UN-Habitat Building ID (17 digits)"},
            "governorate_code": {"type": "text", "required": True, "description": "Governorate code (2 digits)"},
            "district_code": {"type": "text", "required": True, "description": "District code (2 digits)"},
            "subdistrict_code": {"type": "text", "required": True, "description": "Sub-district code (2 digits)"},
            "community_code": {"type": "text", "required": True, "description": "Community code (3 digits)"},
            "neighborhood_code": {"type": "text", "required": True, "description": "Neighborhood code (3 digits)"},
            "building_number": {"type": "text", "required": True, "description": "Building number (5 digits)"},
            "building_type": {"type": "text", "required": False, "description": "Type of building"},
            "building_condition": {"type": "text", "required": False, "description": "Condition of building"},
            "floors_count": {"type": "integer", "required": False, "description": "Number of floors"},
            "units_count": {"type": "integer", "required": False, "description": "Number of units"},
            "latitude": {"type": "float", "required": False, "description": "GPS latitude"},
            "longitude": {"type": "float", "required": False, "description": "GPS longitude"},
            "address": {"type": "text", "required": False, "description": "Street address"},
            "address_ar": {"type": "text", "required": False, "description": "Arabic address"},
        },
        EntityTarget.CLAIM: {
            "claim_id": {"type": "text", "required": False, "description": "Claim ID"},
            "building_id": {"type": "text", "required": True, "description": "Building ID"},
            "claimant_name": {"type": "text", "required": True, "description": "Name of claimant"},
            "claimant_national_id": {"type": "text", "required": True, "description": "National ID"},
            "claim_type": {"type": "text", "required": True, "description": "Type of claim"},
            "claim_status": {"type": "text", "required": False, "description": "Status"},
            "claim_date": {"type": "date", "required": False, "description": "Date of claim"},
            "description": {"type": "text", "required": False, "description": "Claim description"},
        },
        EntityTarget.PERSON: {
            "person_id": {"type": "text", "required": False, "description": "Person ID"},
            "national_id": {"type": "text", "required": True, "description": "National ID"},
            "full_name": {"type": "text", "required": True, "description": "Full name"},
            "full_name_ar": {"type": "text", "required": False, "description": "Arabic name"},
            "date_of_birth": {"type": "date", "required": False, "description": "Date of birth"},
            "gender": {"type": "text", "required": False, "description": "Gender (M/F)"},
            "phone": {"type": "text", "required": False, "description": "Phone number"},
            "email": {"type": "text", "required": False, "description": "Email address"},
        }
    }

    # Building ID pattern: GG-DD-SS-CCC-NNN-BBBBB
    BUILDING_ID_PATTERN = r'^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}-\d{5}$'

    def __init__(self, db_path: str, staging_path: str, watched_folders_path: str):
        """
        Initialize import wizard service.

        Args:
            db_path: Path to database (used for SQLite path, ignored for PostgreSQL)
            staging_path: Base path for staging imported data
            watched_folders_path: Base path for watched folders
        """
        self.db_path = db_path
        self.staging_path = Path(staging_path)
        self.watched_folders_path = Path(watched_folders_path)

        # Use the unified database adapter
        self._adapter: DatabaseAdapter = DatabaseFactory.create()

        self.staging_path.mkdir(parents=True, exist_ok=True)
        self.watched_folders_path.mkdir(parents=True, exist_ok=True)

        self._ensure_tables()

        # Folder watchers
        self._watchers: Dict[str, Any] = {}
        self._watcher_callbacks: Dict[str, Callable] = {}

    def _ensure_tables(self):
        """Ensure import tables exist."""
        from repositories.db_adapter import DatabaseType

        is_postgres = self._adapter.db_type == DatabaseType.POSTGRESQL
        serial_type = "SERIAL" if is_postgres else "INTEGER"
        autoincrement = "" if is_postgres else "AUTOINCREMENT"

        with self._adapter.cursor() as cursor:
            # Import jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_jobs (
                    job_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    column_mappings TEXT,
                    statistics TEXT,
                    options TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    completed_at TIMESTAMP,
                    error_message TEXT
                )
            """)

            # Import validation issues
            if is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_validation_issues (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        column_name TEXT,
                        value TEXT,
                        severity TEXT,
                        message TEXT,
                        suggestion TEXT,
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_validation_issues (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        column_name TEXT,
                        value TEXT,
                        severity TEXT,
                        message TEXT,
                        suggestion TEXT,
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

            # Staging tables for each entity type
            if is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staging_buildings (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        data TEXT NOT NULL,
                        is_valid INTEGER DEFAULT 1,
                        is_duplicate INTEGER DEFAULT 0,
                        duplicate_of TEXT,
                        import_status TEXT DEFAULT 'pending',
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staging_claims (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        data TEXT NOT NULL,
                        is_valid INTEGER DEFAULT 1,
                        is_duplicate INTEGER DEFAULT 0,
                        duplicate_of TEXT,
                        import_status TEXT DEFAULT 'pending',
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staging_persons (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        data TEXT NOT NULL,
                        is_valid INTEGER DEFAULT 1,
                        is_duplicate INTEGER DEFAULT 0,
                        duplicate_of TEXT,
                        import_status TEXT DEFAULT 'pending',
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staging_buildings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        data TEXT NOT NULL,
                        is_valid INTEGER DEFAULT 1,
                        is_duplicate INTEGER DEFAULT 0,
                        duplicate_of TEXT,
                        import_status TEXT DEFAULT 'pending',
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staging_claims (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        data TEXT NOT NULL,
                        is_valid INTEGER DEFAULT 1,
                        is_duplicate INTEGER DEFAULT 0,
                        duplicate_of TEXT,
                        import_status TEXT DEFAULT 'pending',
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS staging_persons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        row_number INTEGER,
                        data TEXT NOT NULL,
                        is_valid INTEGER DEFAULT 1,
                        is_duplicate INTEGER DEFAULT 0,
                        duplicate_of TEXT,
                        import_status TEXT DEFAULT 'pending',
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

            # Watched folders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watched_folders (
                    folder_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    target_entity TEXT NOT NULL,
                    file_pattern TEXT DEFAULT '*.*',
                    auto_import INTEGER DEFAULT 0,
                    column_mappings TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT
                )
            """)

            # Import history/audit
            if is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_audit_log (
                        id SERIAL PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        performed_by TEXT,
                        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        performed_by TEXT,
                        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id)
                    )
                """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_jobs_status ON import_jobs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staging_job ON staging_buildings(job_id)")

        logger.info("Import wizard tables initialized")

    # ==================== Import Job Management ====================

    def create_import_job(
        self,
        file_path: str,
        target_entity: EntityTarget,
        created_by: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ImportJob:
        """
        Create a new import job from a file.

        Args:
            file_path: Path to the file to import
            target_entity: Target entity type
            created_by: User creating the import
            options: Import options (encoding, delimiter, etc.)

        Returns:
            Created ImportJob object
        """
        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect file format
        file_format = self._detect_format(source_path)

        job_id = str(uuid.uuid4())

        # Copy file to staging area
        staging_file_path = self.staging_path / job_id / source_path.name
        staging_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, staging_file_path)

        job = ImportJob(
            job_id=job_id,
            file_name=source_path.name,
            file_path=str(staging_file_path),
            file_format=file_format,
            target_entity=target_entity,
            status=ImportStatus.PENDING,
            options=options or {},
            created_by=created_by
        )

        # Save to database
        with self._adapter.cursor() as cursor:
            cursor.execute("""
                INSERT INTO import_jobs (
                    job_id, file_name, file_path, file_format, target_entity,
                    status, options, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, source_path.name, str(staging_file_path),
                file_format.value, target_entity.value,
                ImportStatus.PENDING.value, json.dumps(options or {}), created_by
            ))

            self._log_import_action(cursor, job_id, "job_created", {
                "file_name": source_path.name,
                "target_entity": target_entity.value
            }, created_by)

        logger.info(f"Created import job: {job_id}")
        return job

    def _detect_format(self, file_path: Path) -> ImportFormat:
        """Detect file format from extension."""
        ext = file_path.suffix.lower()
        format_map = {
            ".csv": ImportFormat.CSV,
            ".xlsx": ImportFormat.EXCEL,
            ".xls": ImportFormat.EXCEL,
            ".json": ImportFormat.JSON,
            ".geojson": ImportFormat.GEOJSON,
            ".shp": ImportFormat.SHAPEFILE
        }
        return format_map.get(ext, ImportFormat.CSV)

    def get_import_job(self, job_id: str) -> Optional[ImportJob]:
        """Get import job by ID."""
        row = self._adapter.fetch_one("SELECT * FROM import_jobs WHERE job_id = ?", (job_id,))
        if not row:
            return None

        # Get validation issues
        issue_rows = self._adapter.fetch_all(
            "SELECT * FROM import_validation_issues WHERE job_id = ?", (job_id,)
        )

        issues = []
        for issue_row in issue_rows:
            issues.append(ValidationIssue(
                row_number=issue_row["row_number"],
                column=issue_row["column_name"],
                value=issue_row["value"],
                severity=ValidationSeverity(issue_row["severity"]),
                message=issue_row["message"],
                suggestion=issue_row["suggestion"]
            ))

        return ImportJob(
            job_id=row["job_id"],
            file_name=row["file_name"],
            file_path=row["file_path"],
            file_format=ImportFormat(row["file_format"]),
            target_entity=EntityTarget(row["target_entity"]),
            status=ImportStatus(row["status"]),
            column_mappings=[ColumnMapping(**m) for m in json.loads(row["column_mappings"] or "[]")],
            statistics=ImportStatistics(**json.loads(row["statistics"] or "{}")),
            validation_issues=issues,
            options=json.loads(row["options"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            created_by=row["created_by"] or "",
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            error_message=row["error_message"] or ""
        )

    def list_import_jobs(
        self,
        status: Optional[ImportStatus] = None,
        target_entity: Optional[EntityTarget] = None,
        created_by: Optional[str] = None,
        limit: int = 50
    ) -> List[ImportJob]:
        """List import jobs with filters."""
        query = "SELECT job_id FROM import_jobs WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if target_entity:
            query += " AND target_entity = ?"
            params.append(target_entity.value)

        if created_by:
            query += " AND created_by = ?"
            params.append(created_by)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._adapter.fetch_all(query, tuple(params))

        jobs = []
        for row in rows:
            job = self.get_import_job(row["job_id"])
            if job:
                jobs.append(job)

        return jobs

    # ==================== Column Detection and Mapping ====================

    def detect_columns(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Detect columns in the import file and suggest mappings.

        Returns list of detected columns with suggested target field mappings.
        """
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        file_path = Path(job.file_path)

        # Read sample rows
        sample_data = self._read_sample_data(file_path, job.file_format, job.options)

        if not sample_data:
            return []

        columns = list(sample_data[0].keys()) if sample_data else []

        # Get target fields for entity type
        target_fields = self.ENTITY_FIELDS.get(job.target_entity, {})

        detected = []
        for col in columns:
            # Sample values
            sample_values = [str(row.get(col, ""))[:50] for row in sample_data[:5]]

            # Suggest mapping based on column name
            suggested_target = self._suggest_mapping(col, target_fields)

            detected.append({
                "source_column": col,
                "sample_values": sample_values,
                "suggested_target": suggested_target,
                "data_type": self._detect_data_type(sample_values),
                "non_empty_count": len([v for v in sample_values if v])
            })

        return detected

    def _read_sample_data(
        self,
        file_path: Path,
        file_format: ImportFormat,
        options: Dict[str, Any],
        max_rows: int = 100
    ) -> List[Dict[str, Any]]:
        """Read sample data from file."""
        encoding = options.get("encoding", "utf-8")
        delimiter = options.get("delimiter", ",")

        try:
            if file_format == ImportFormat.CSV:
                return self._read_csv_sample(file_path, encoding, delimiter, max_rows)
            elif file_format == ImportFormat.EXCEL:
                return self._read_excel_sample(file_path, options, max_rows)
            elif file_format == ImportFormat.JSON:
                return self._read_json_sample(file_path, encoding, max_rows)
            elif file_format == ImportFormat.GEOJSON:
                return self._read_geojson_sample(file_path, encoding, max_rows)
            else:
                logger.warning(f"Unsupported format: {file_format}")
                return []
        except Exception as e:
            logger.error(f"Error reading sample data: {e}")
            return []

    def _read_csv_sample(
        self,
        file_path: Path,
        encoding: str,
        delimiter: str,
        max_rows: int
    ) -> List[Dict[str, Any]]:
        """Read sample from CSV file."""
        rows = []
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(dict(row))
        return rows

    def _read_excel_sample(
        self,
        file_path: Path,
        options: Dict[str, Any],
        max_rows: int
    ) -> List[Dict[str, Any]]:
        """Read sample from Excel file."""
        if not HAS_PANDAS:
            raise ImportError("pandas required for Excel import")

        sheet = options.get("sheet", 0)
        df = pd.read_excel(file_path, sheet_name=sheet, nrows=max_rows)
        return df.fillna("").to_dict('records')

    def _read_json_sample(
        self,
        file_path: Path,
        encoding: str,
        max_rows: int
    ) -> List[Dict[str, Any]]:
        """Read sample from JSON file."""
        with open(file_path, 'r', encoding=encoding) as f:
            data = json.load(f)

        if isinstance(data, list):
            return data[:max_rows]
        elif isinstance(data, dict):
            # Look for array in common keys
            for key in ['data', 'records', 'items', 'features']:
                if key in data and isinstance(data[key], list):
                    return data[key][:max_rows]
            return [data]

        return []

    def _read_geojson_sample(
        self,
        file_path: Path,
        encoding: str,
        max_rows: int
    ) -> List[Dict[str, Any]]:
        """Read sample from GeoJSON file."""
        with open(file_path, 'r', encoding=encoding) as f:
            data = json.load(f)

        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])[:max_rows]
            return [
                {
                    **f.get("properties", {}),
                    "_geometry": f.get("geometry")
                }
                for f in features
            ]

        return []

    def _suggest_mapping(self, column: str, target_fields: Dict) -> Optional[str]:
        """Suggest target field mapping based on column name."""
        col_lower = column.lower().replace("_", "").replace(" ", "").replace("-", "")

        # Direct matches
        for field_name, field_info in target_fields.items():
            field_lower = field_name.lower().replace("_", "")
            if col_lower == field_lower:
                return field_name

        # Partial matches
        mapping_hints = {
            "buildingid": "building_id",
            "bldgid": "building_id",
            "nationalid": "national_id",
            "idnumber": "national_id",
            "lat": "latitude",
            "lng": "longitude",
            "lon": "longitude",
            "long": "longitude",
            "name": "full_name",
            "fullname": "full_name",
            "namear": "full_name_ar",
            "arabicname": "full_name_ar",
            "addr": "address",
            "street": "address",
            "phone": "phone",
            "tel": "phone",
            "mobile": "phone",
            "email": "email",
            "dob": "date_of_birth",
            "birthdate": "date_of_birth",
            "gender": "gender",
            "sex": "gender",
            "floors": "floors_count",
            "numfloors": "floors_count",
            "units": "units_count",
            "numunits": "units_count",
            "type": "building_type",
            "bldgtype": "building_type",
            "condition": "building_condition",
            "status": "claim_status",
        }

        for hint, target in mapping_hints.items():
            if hint in col_lower and target in target_fields:
                return target

        return None

    def _detect_data_type(self, values: List[str]) -> str:
        """Detect data type from sample values."""
        non_empty = [v for v in values if v]
        if not non_empty:
            return "text"

        # Check for integer
        if all(v.isdigit() or (v.startswith('-') and v[1:].isdigit()) for v in non_empty):
            return "integer"

        # Check for float
        try:
            for v in non_empty:
                float(v.replace(',', ''))
            return "float"
        except ValueError:
            pass

        # Check for date patterns
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}$',
            r'^\d{2}/\d{2}/\d{4}$',
            r'^\d{2}-\d{2}-\d{4}$'
        ]
        for pattern in date_patterns:
            if all(re.match(pattern, v) for v in non_empty):
                return "date"

        # Check for boolean
        bool_values = {'true', 'false', 'yes', 'no', '1', '0', 'y', 'n'}
        if all(v.lower() in bool_values for v in non_empty):
            return "boolean"

        return "text"

    def set_column_mappings(
        self,
        job_id: str,
        mappings: List[ColumnMapping],
        updated_by: str
    ) -> ImportJob:
        """Set column mappings for an import job."""
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE import_jobs SET column_mappings = ?
                WHERE job_id = ?
            """, (json.dumps([m.to_dict() for m in mappings]), job_id))

            self._log_import_action(cursor, job_id, "mappings_set", {
                "mapping_count": len(mappings)
            }, updated_by)

        return self.get_import_job(job_id)

    # ==================== Validation ====================

    def validate_import(self, job_id: str, validated_by: str) -> ImportJob:
        """
        Validate import data according to mappings and rules.

        This reads the file, applies mappings, and validates each row.
        """
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if not job.column_mappings:
            raise ValueError("Column mappings not set")

        try:
            # Update status
            self._adapter.execute("""
                UPDATE import_jobs SET status = 'validating'
                WHERE job_id = ?
            """, (job_id,))

            # Clear previous validation issues
            self._adapter.execute("DELETE FROM import_validation_issues WHERE job_id = ?", (job_id,))

            # Read all data
            file_path = Path(job.file_path)
            all_data = self._read_sample_data(file_path, job.file_format, job.options, max_rows=1000000)

            stats = ImportStatistics(
                total_rows=len(all_data),
                start_time=datetime.utcnow()
            )

            issues = []
            valid_count = 0
            invalid_count = 0

            # Get staging table
            staging_table = f"staging_{job.target_entity.value}s"

            # Clear staging
            self._adapter.execute(f"DELETE FROM {staging_table} WHERE job_id = ?", (job_id,))

            with self._adapter.cursor() as cursor:
                for row_num, row_data in enumerate(all_data, start=1):
                    # Apply mappings and transform
                    transformed = self._apply_mappings(row_data, job.column_mappings)

                    # Validate row
                    row_issues = self._validate_row(row_num, transformed, job.target_entity)
                    issues.extend(row_issues)

                    is_valid = not any(i.severity == ValidationSeverity.ERROR for i in row_issues)

                    if is_valid:
                        valid_count += 1
                    else:
                        invalid_count += 1

                    # Check for duplicates
                    is_duplicate, duplicate_of = self._check_duplicate(transformed, job.target_entity, cursor)

                    # Insert into staging
                    cursor.execute(f"""
                        INSERT INTO {staging_table} (job_id, row_number, data, is_valid, is_duplicate, duplicate_of)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        job_id, row_num, json.dumps(transformed),
                        1 if is_valid else 0,
                        1 if is_duplicate else 0,
                        duplicate_of
                    ))

                    if is_duplicate:
                        stats.duplicate_rows += 1

                # Save validation issues
                for issue in issues:
                    cursor.execute("""
                        INSERT INTO import_validation_issues
                        (job_id, row_number, column_name, value, severity, message, suggestion)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job_id, issue.row_number, issue.column, str(issue.value),
                        issue.severity.value, issue.message, issue.suggestion
                    ))

                stats.valid_rows = valid_count
                stats.invalid_rows = invalid_count
                stats.errors = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
                stats.warnings = len([i for i in issues if i.severity == ValidationSeverity.WARNING])
                stats.end_time = datetime.utcnow()

                # Update job
                cursor.execute("""
                    UPDATE import_jobs SET
                        status = 'staging',
                        statistics = ?
                    WHERE job_id = ?
                """, (json.dumps(stats.to_dict()), job_id))

                self._log_import_action(cursor, job_id, "validation_completed", stats.to_dict(), validated_by)

            return self.get_import_job(job_id)

        except Exception as e:
            self._adapter.execute("""
                UPDATE import_jobs SET status = 'failed', error_message = ?
                WHERE job_id = ?
            """, (str(e), job_id))
            raise

    def _apply_mappings(
        self,
        row_data: Dict[str, Any],
        mappings: List[ColumnMapping]
    ) -> Dict[str, Any]:
        """Apply column mappings and transformations to a row."""
        result = {}

        for mapping in mappings:
            value = row_data.get(mapping.source_column, mapping.default_value)

            # Apply transformation
            if value is not None and mapping.transformation:
                value = self._apply_transformation(value, mapping.transformation)

            # Type conversion
            if value is not None and value != "":
                value = self._convert_type(value, mapping.data_type)

            result[mapping.target_field] = value

        return result

    def _apply_transformation(self, value: Any, transformation: str) -> Any:
        """Apply a transformation to a value."""
        if value is None:
            return None

        str_value = str(value)

        transformations = {
            "uppercase": lambda v: v.upper(),
            "lowercase": lambda v: v.lower(),
            "trim": lambda v: v.strip(),
            "capitalize": lambda v: v.title(),
            "remove_spaces": lambda v: v.replace(" ", ""),
        }

        if transformation in transformations:
            return transformations[transformation](str_value)

        return str_value

    def _convert_type(self, value: Any, data_type: str) -> Any:
        """Convert value to specified data type."""
        if value is None or value == "":
            return None

        try:
            if data_type == "integer":
                return int(float(str(value).replace(",", "")))
            elif data_type == "float":
                return float(str(value).replace(",", ""))
            elif data_type == "boolean":
                return str(value).lower() in ('true', 'yes', '1', 'y')
            elif data_type == "date":
                # Try common date formats
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(str(value), fmt).date().isoformat()
                    except ValueError:
                        continue
                return str(value)
            else:
                return str(value)
        except (ValueError, TypeError):
            return str(value)

    def _validate_row(
        self,
        row_num: int,
        data: Dict[str, Any],
        target_entity: EntityTarget
    ) -> List[ValidationIssue]:
        """Validate a single row of data."""
        issues = []
        target_fields = self.ENTITY_FIELDS.get(target_entity, {})

        # Check required fields
        for field_name, field_info in target_fields.items():
            if field_info.get("required", False):
                value = data.get(field_name)
                if value is None or value == "":
                    issues.append(ValidationIssue(
                        row_number=row_num,
                        column=field_name,
                        value=value,
                        severity=ValidationSeverity.ERROR,
                        message=f"Required field '{field_name}' is missing",
                        suggestion=f"Provide a value for {field_info.get('description', field_name)}"
                    ))

        # Entity-specific validation
        if target_entity == EntityTarget.BUILDING:
            issues.extend(self._validate_building_row(row_num, data))
        elif target_entity == EntityTarget.CLAIM:
            issues.extend(self._validate_claim_row(row_num, data))
        elif target_entity == EntityTarget.PERSON:
            issues.extend(self._validate_person_row(row_num, data))

        return issues

    def _validate_building_row(self, row_num: int, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate building-specific fields."""
        issues = []

        # Validate building ID format
        building_id = data.get("building_id")
        if building_id and not re.match(self.BUILDING_ID_PATTERN, building_id):
            issues.append(ValidationIssue(
                row_number=row_num,
                column="building_id",
                value=building_id,
                severity=ValidationSeverity.ERROR,
                message="Invalid building ID format",
                suggestion="Use format: GG-DD-SS-CCC-NNN-BBBBB (e.g., 01-02-03-001-002-00001)"
            ))

        # Validate coordinates
        lat = data.get("latitude")
        lng = data.get("longitude")

        if lat is not None:
            try:
                lat_val = float(lat)
                if not (-90 <= lat_val <= 90):
                    issues.append(ValidationIssue(
                        row_number=row_num,
                        column="latitude",
                        value=lat,
                        severity=ValidationSeverity.ERROR,
                        message="Latitude must be between -90 and 90"
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    row_number=row_num,
                    column="latitude",
                    value=lat,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid latitude value"
                ))

        if lng is not None:
            try:
                lng_val = float(lng)
                if not (-180 <= lng_val <= 180):
                    issues.append(ValidationIssue(
                        row_number=row_num,
                        column="longitude",
                        value=lng,
                        severity=ValidationSeverity.ERROR,
                        message="Longitude must be between -180 and 180"
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    row_number=row_num,
                    column="longitude",
                    value=lng,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid longitude value"
                ))

        return issues

    def _validate_claim_row(self, row_num: int, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate claim-specific fields."""
        issues = []

        # Validate national ID format
        national_id = data.get("claimant_national_id")
        if national_id and len(str(national_id)) < 5:
            issues.append(ValidationIssue(
                row_number=row_num,
                column="claimant_national_id",
                value=national_id,
                severity=ValidationSeverity.WARNING,
                message="National ID seems too short"
            ))

        return issues

    def _validate_person_row(self, row_num: int, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate person-specific fields."""
        issues = []

        # Validate gender
        gender = data.get("gender")
        if gender and str(gender).upper() not in ['M', 'F', 'MALE', 'FEMALE']:
            issues.append(ValidationIssue(
                row_number=row_num,
                column="gender",
                value=gender,
                severity=ValidationSeverity.WARNING,
                message="Gender should be M or F",
                suggestion="Use 'M' for male or 'F' for female"
            ))

        # Validate email
        email = data.get("email")
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', str(email)):
            issues.append(ValidationIssue(
                row_number=row_num,
                column="email",
                value=email,
                severity=ValidationSeverity.WARNING,
                message="Invalid email format"
            ))

        return issues

    def _check_duplicate(
        self,
        data: Dict[str, Any],
        target_entity: EntityTarget,
        cursor: Any
    ) -> Tuple[bool, Optional[str]]:
        """Check if data is a duplicate of existing records."""
        # Check based on entity type
        if target_entity == EntityTarget.BUILDING:
            building_id = data.get("building_id")
            if building_id:
                cursor.execute("SELECT building_id FROM buildings WHERE building_id = ?", (building_id,))
                existing = cursor.fetchone()
                if existing:
                    return True, existing[0]

        elif target_entity == EntityTarget.PERSON:
            national_id = data.get("national_id")
            if national_id:
                cursor.execute("SELECT person_id FROM persons WHERE national_id = ?", (national_id,))
                existing = cursor.fetchone()
                if existing:
                    return True, existing[0]

        return False, None

    # ==================== Staging Review ====================

    def get_staging_data(
        self,
        job_id: str,
        include_valid: bool = True,
        include_invalid: bool = True,
        include_duplicates: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get staged data for review."""
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        staging_table = f"staging_{job.target_entity.value}s"

        conditions = []
        if not include_valid:
            conditions.append("is_valid = 0")
        if not include_invalid:
            conditions.append("is_valid = 1")
        if not include_duplicates:
            conditions.append("is_duplicate = 0")

        where_clause = f"job_id = ?"
        if conditions:
            where_clause += " AND (" + " OR ".join(conditions) + ")"

        rows = self._adapter.fetch_all(f"""
            SELECT * FROM {staging_table}
            WHERE {where_clause}
            ORDER BY row_number
            LIMIT ? OFFSET ?
        """, (job_id, limit, offset))

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "row_number": row["row_number"],
                "data": json.loads(row["data"]),
                "is_valid": bool(row["is_valid"]),
                "is_duplicate": bool(row["is_duplicate"]),
                "duplicate_of": row["duplicate_of"],
                "import_status": row["import_status"]
            })

        return results

    def update_staging_row(
        self,
        job_id: str,
        row_id: int,
        data: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """Update a row in staging."""
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        staging_table = f"staging_{job.target_entity.value}s"

        with self._adapter.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {staging_table}
                SET data = ?, is_valid = 1
                WHERE id = ? AND job_id = ?
            """, (json.dumps(data), row_id, job_id))

            self._log_import_action(cursor, job_id, "staging_row_updated", {
                "row_id": row_id
            }, updated_by)

            return cursor.rowcount > 0

    def skip_staging_row(self, job_id: str, row_id: int, skipped_by: str) -> bool:
        """Mark a staging row to be skipped during import."""
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        staging_table = f"staging_{job.target_entity.value}s"

        with self._adapter.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {staging_table}
                SET import_status = 'skipped'
                WHERE id = ? AND job_id = ?
            """, (row_id, job_id))

            return cursor.rowcount > 0

    # ==================== Commit Import ====================

    def commit_import(self, job_id: str, committed_by: str) -> ImportJob:
        """
        Commit validated data from staging to production tables.
        """
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status not in [ImportStatus.STAGING, ImportStatus.REVIEWING]:
            raise ValueError(f"Cannot commit job with status: {job.status.value}")

        try:
            # Update status
            self._adapter.execute("""
                UPDATE import_jobs SET status = 'committing'
                WHERE job_id = ?
            """, (job_id,))

            staging_table = f"staging_{job.target_entity.value}s"

            # Get valid, non-skipped rows
            rows = self._adapter.fetch_all(f"""
                SELECT * FROM {staging_table}
                WHERE job_id = ? AND is_valid = 1 AND import_status = 'pending'
            """, (job_id,))

            imported_count = 0
            skipped_count = 0

            with self._adapter.cursor() as cursor:
                for row in rows:
                    data = json.loads(row["data"])

                    try:
                        # Insert into production table
                        if job.target_entity == EntityTarget.BUILDING:
                            self._insert_building(cursor, data)
                        elif job.target_entity == EntityTarget.CLAIM:
                            self._insert_claim(cursor, data)
                        elif job.target_entity == EntityTarget.PERSON:
                            self._insert_person(cursor, data)

                        # Mark as imported
                        cursor.execute(f"""
                            UPDATE {staging_table}
                            SET import_status = 'imported'
                            WHERE id = ?
                        """, (row["id"],))

                        imported_count += 1

                    except Exception as e:
                        logger.error(f"Error importing row {row['row_number']}: {e}")
                        cursor.execute(f"""
                            UPDATE {staging_table}
                            SET import_status = 'failed'
                            WHERE id = ?
                        """, (row["id"],))
                        skipped_count += 1

                # Update statistics
                stats = job.statistics
                stats.imported_rows = imported_count
                stats.skipped_rows = skipped_count
                stats.end_time = datetime.utcnow()

                cursor.execute("""
                    UPDATE import_jobs SET
                        status = 'completed',
                        statistics = ?,
                        completed_at = ?
                    WHERE job_id = ?
                """, (json.dumps(stats.to_dict()), datetime.utcnow().isoformat(), job_id))

                self._log_import_action(cursor, job_id, "import_committed", {
                    "imported_rows": imported_count,
                    "skipped_rows": skipped_count
                }, committed_by)

            logger.info(f"Import committed: {imported_count} rows imported")
            return self.get_import_job(job_id)

        except Exception as e:
            self._adapter.execute("""
                UPDATE import_jobs SET status = 'failed', error_message = ?
                WHERE job_id = ?
            """, (str(e), job_id))
            raise

    def _insert_building(self, cursor: Any, data: Dict[str, Any]):
        """Insert building record."""
        cursor.execute("""
            INSERT INTO buildings (
                building_id, governorate_code, district_code, subdistrict_code,
                community_code, neighborhood_code, building_number, building_type,
                building_condition, floors_count, units_count, latitude, longitude,
                address, address_ar, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("building_id"),
            data.get("governorate_code"),
            data.get("district_code"),
            data.get("subdistrict_code"),
            data.get("community_code"),
            data.get("neighborhood_code"),
            data.get("building_number"),
            data.get("building_type"),
            data.get("building_condition"),
            data.get("floors_count"),
            data.get("units_count"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("address"),
            data.get("address_ar"),
            datetime.utcnow().isoformat()
        ))

    def _insert_claim(self, cursor: Any, data: Dict[str, Any]):
        """Insert claim record."""
        claim_id = data.get("claim_id") or str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO claims (
                claim_id, building_id, claimant_name, claimant_national_id,
                claim_type, claim_status, claim_date, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            claim_id,
            data.get("building_id"),
            data.get("claimant_name"),
            data.get("claimant_national_id"),
            data.get("claim_type"),
            data.get("claim_status", "pending"),
            data.get("claim_date"),
            data.get("description"),
            datetime.utcnow().isoformat()
        ))

    def _insert_person(self, cursor: Any, data: Dict[str, Any]):
        """Insert person record."""
        person_id = data.get("person_id") or str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO persons (
                person_id, national_id, full_name, full_name_ar,
                date_of_birth, gender, phone, email, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            person_id,
            data.get("national_id"),
            data.get("full_name"),
            data.get("full_name_ar"),
            data.get("date_of_birth"),
            data.get("gender"),
            data.get("phone"),
            data.get("email"),
            datetime.utcnow().isoformat()
        ))

    # ==================== Watched Folders ====================

    def create_watched_folder(
        self,
        path: str,
        target_entity: EntityTarget,
        created_by: str,
        file_pattern: str = "*.*",
        auto_import: bool = False,
        column_mappings: Optional[List[ColumnMapping]] = None
    ) -> WatchedFolder:
        """Create a new watched folder configuration."""
        folder_path = Path(path)
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)

        folder_id = str(uuid.uuid4())

        folder = WatchedFolder(
            folder_id=folder_id,
            path=str(folder_path),
            target_entity=target_entity,
            file_pattern=file_pattern,
            auto_import=auto_import,
            column_mappings=column_mappings or [],
            created_by=created_by
        )

        self._adapter.execute("""
            INSERT INTO watched_folders (
                folder_id, path, target_entity, file_pattern,
                auto_import, column_mappings, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            folder_id, str(folder_path), target_entity.value,
            file_pattern, 1 if auto_import else 0,
            json.dumps([m.to_dict() for m in (column_mappings or [])]),
            created_by
        ))

        logger.info(f"Created watched folder: {folder_id}")
        return folder

    def list_watched_folders(self) -> List[WatchedFolder]:
        """List all watched folders."""
        rows = self._adapter.fetch_all("SELECT * FROM watched_folders WHERE is_active = 1")

        folders = []
        for row in rows:
            folders.append(WatchedFolder(
                folder_id=row["folder_id"],
                path=row["path"],
                target_entity=EntityTarget(row["target_entity"]),
                file_pattern=row["file_pattern"],
                auto_import=bool(row["auto_import"]),
                column_mappings=[ColumnMapping(**m) for m in json.loads(row["column_mappings"] or "[]")],
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                created_by=row["created_by"] or ""
            ))

        return folders

    def start_folder_monitoring(
        self,
        folder_id: str,
        on_file_detected: Optional[Callable[[str, WatchedFolder], None]] = None
    ):
        """Start monitoring a watched folder."""
        if not HAS_WATCHDOG:
            raise ImportError("watchdog library required for folder monitoring")

        row = self._adapter.fetch_one("SELECT * FROM watched_folders WHERE folder_id = ?", (folder_id,))
        if not row:
            raise ValueError(f"Watched folder not found: {folder_id}")

        folder = WatchedFolder(
            folder_id=row["folder_id"],
            path=row["path"],
            target_entity=EntityTarget(row["target_entity"]),
            file_pattern=row["file_pattern"],
            auto_import=bool(row["auto_import"]),
            column_mappings=[ColumnMapping(**m) for m in json.loads(row["column_mappings"] or "[]")]
        )

        # Create event handler
        class ImportEventHandler(FileSystemEventHandler):
            def __init__(handler_self, service, folder, callback):
                handler_self.service = service
                handler_self.folder = folder
                handler_self.callback = callback

            def on_created(handler_self, event):
                if isinstance(event, FileCreatedEvent):
                    file_path = Path(event.src_path)
                    # Check pattern match
                    if file_path.match(handler_self.folder.file_pattern):
                        logger.info(f"New file detected: {file_path}")
                        if handler_self.callback:
                            handler_self.callback(str(file_path), handler_self.folder)
                        elif handler_self.folder.auto_import:
                            # Auto-create import job
                            try:
                                job = handler_self.service.create_import_job(
                                    str(file_path),
                                    handler_self.folder.target_entity,
                                    "auto_import"
                                )
                                if handler_self.folder.column_mappings:
                                    handler_self.service.set_column_mappings(
                                        job.job_id,
                                        handler_self.folder.column_mappings,
                                        "auto_import"
                                    )
                                logger.info(f"Auto-created import job: {job.job_id}")
                            except Exception as e:
                                logger.error(f"Error creating auto-import job: {e}")

        event_handler = ImportEventHandler(self, folder, on_file_detected)
        observer = Observer()
        observer.schedule(event_handler, folder.path, recursive=False)
        observer.start()

        self._watchers[folder_id] = observer
        logger.info(f"Started monitoring folder: {folder.path}")

    def stop_folder_monitoring(self, folder_id: str):
        """Stop monitoring a watched folder."""
        if folder_id in self._watchers:
            observer = self._watchers[folder_id]
            observer.stop()
            observer.join()
            del self._watchers[folder_id]
            logger.info(f"Stopped monitoring folder: {folder_id}")

    def stop_all_monitoring(self):
        """Stop all folder monitoring."""
        for folder_id in list(self._watchers.keys()):
            self.stop_folder_monitoring(folder_id)

    # ==================== Rollback ====================

    def rollback_import(self, job_id: str, rolled_back_by: str) -> bool:
        """
        Rollback a completed import.

        This removes all records that were imported by this job.
        """
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != ImportStatus.COMPLETED:
            raise ValueError("Can only rollback completed imports")

        staging_table = f"staging_{job.target_entity.value}s"

        # Get imported records
        rows = self._adapter.fetch_all(f"""
            SELECT data FROM {staging_table}
            WHERE job_id = ? AND import_status = 'imported'
        """, (job_id,))

        rollback_count = 0

        with self._adapter.cursor() as cursor:
            for row in rows:
                data = json.loads(row["data"])

                try:
                    if job.target_entity == EntityTarget.BUILDING:
                        cursor.execute("DELETE FROM buildings WHERE building_id = ?", (data.get("building_id"),))
                    elif job.target_entity == EntityTarget.CLAIM:
                        cursor.execute("DELETE FROM claims WHERE claim_id = ?", (data.get("claim_id"),))
                    elif job.target_entity == EntityTarget.PERSON:
                        cursor.execute("DELETE FROM persons WHERE person_id = ?", (data.get("person_id"),))

                    rollback_count += cursor.rowcount

                except Exception as e:
                    logger.error(f"Error rolling back record: {e}")

            # Update job status
            cursor.execute("""
                UPDATE import_jobs SET status = 'rolled_back'
                WHERE job_id = ?
            """, (job_id,))

            self._log_import_action(cursor, job_id, "import_rolled_back", {
                "rollback_count": rollback_count
            }, rolled_back_by)

        logger.info(f"Rolled back import {job_id}: {rollback_count} records removed")
        return True

    # ==================== Audit Log ====================

    def _log_import_action(
        self,
        cursor: Any,
        job_id: str,
        action: str,
        details: Dict[str, Any],
        performed_by: str
    ):
        """Log an import action."""
        cursor.execute("""
            INSERT INTO import_audit_log (job_id, action, details, performed_by)
            VALUES (?, ?, ?, ?)
        """, (job_id, action, json.dumps(details), performed_by))

    def get_import_audit_log(self, job_id: str) -> List[Dict[str, Any]]:
        """Get audit log for an import job."""
        rows = self._adapter.fetch_all("""
            SELECT * FROM import_audit_log
            WHERE job_id = ?
            ORDER BY performed_at DESC
        """, (job_id,))

        entries = []
        for row in rows:
            entries.append({
                "id": row["id"],
                "job_id": row["job_id"],
                "action": row["action"],
                "details": json.loads(row["details"]) if row["details"] else {},
                "performed_by": row["performed_by"],
                "performed_at": row["performed_at"]
            })

        return entries

    # ==================== Utility Methods ====================

    def get_target_fields(self, target_entity: EntityTarget) -> Dict[str, Dict[str, Any]]:
        """Get available target fields for an entity type."""
        return self.ENTITY_FIELDS.get(target_entity, {})

    def cancel_import(self, job_id: str, cancelled_by: str) -> bool:
        """Cancel a pending or in-progress import."""
        job = self.get_import_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status in [ImportStatus.COMPLETED, ImportStatus.ROLLED_BACK]:
            raise ValueError("Cannot cancel completed or rolled back import")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE import_jobs SET status = 'cancelled'
                WHERE job_id = ?
            """, (job_id,))

            self._log_import_action(cursor, job_id, "import_cancelled", {}, cancelled_by)

        return True

    def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """Clean up old import jobs and their staging data."""
        from repositories.db_adapter import DatabaseType

        cutoff = datetime.utcnow().isoformat()

        # Different date arithmetic for SQLite vs PostgreSQL
        if self._adapter.db_type == DatabaseType.POSTGRESQL:
            rows = self._adapter.fetch_all("""
                SELECT job_id FROM import_jobs
                WHERE status IN ('completed', 'failed', 'cancelled', 'rolled_back')
                AND created_at < (CURRENT_TIMESTAMP - INTERVAL '%s days')
            """, (days_old,))
        else:
            rows = self._adapter.fetch_all("""
                SELECT job_id FROM import_jobs
                WHERE status IN ('completed', 'failed', 'cancelled', 'rolled_back')
                AND created_at < datetime(?, '-' || ? || ' days')
            """, (cutoff, days_old))

        deleted_count = 0
        with self._adapter.cursor() as cursor:
            for row in rows:
                job_id = row["job_id"]

                # Clean staging data
                for table in ['staging_buildings', 'staging_claims', 'staging_persons']:
                    cursor.execute(f"DELETE FROM {table} WHERE job_id = ?", (job_id,))

                cursor.execute("DELETE FROM import_validation_issues WHERE job_id = ?", (job_id,))
                cursor.execute("DELETE FROM import_audit_log WHERE job_id = ?", (job_id,))
                cursor.execute("DELETE FROM import_jobs WHERE job_id = ?", (job_id,))

                # Remove staging files
                staging_dir = self.staging_path / job_id
                if staging_dir.exists():
                    shutil.rmtree(staging_dir)

                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old import jobs")
        return deleted_count
