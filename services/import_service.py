# -*- coding: utf-8 -*-
"""
Import service for .uhc container files.
Provides a pluggable interface for import processing.
"""

import json
import random
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class ImportStatus(Enum):
    """Import record status."""
    PENDING = "pending"
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    IMPORTED = "imported"
    SKIPPED = "skipped"


@dataclass
class ImportRecord:
    """A record in the import staging area."""
    record_id: str
    record_type: str  # building, unit, person, claim
    data: Dict[str, Any]
    status: ImportStatus = ImportStatus.PENDING
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duplicate_of: Optional[str] = None
    resolution: Optional[str] = None  # merge, keep_existing, keep_new, skip


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    total_records: int
    imported: int
    failed: int
    skipped: int
    warnings: int
    errors: List[str]
    import_id: str


class ImporterInterface(ABC):
    """Abstract interface for import implementations."""

    @abstractmethod
    def read_file(self, file_path: Path) -> Dict[str, Any]:
        """Read and parse the import file."""
        pass

    @abstractmethod
    def validate_manifest(self, manifest: Dict[str, Any]) -> bool:
        """Validate the file manifest."""
        pass

    @abstractmethod
    def extract_records(self, data: Dict[str, Any]) -> Generator[ImportRecord, None, None]:
        """Extract records from import data."""
        pass

    @abstractmethod
    def validate_record(self, record: ImportRecord) -> ImportRecord:
        """Validate a single record."""
        pass

    @abstractmethod
    def detect_duplicates(self, record: ImportRecord) -> ImportRecord:
        """Check for duplicates in existing data."""
        pass

    @abstractmethod
    def commit_record(self, record: ImportRecord) -> bool:
        """Commit a record to the database."""
        pass


class SimulatedImporter(ImporterInterface):
    """
    Simulated importer for prototype.
    Generates realistic validation results without actual file parsing.
    """

    def __init__(self, db: Database):
        self.db = db

    def read_file(self, file_path: Path) -> Dict[str, Any]:
        """Simulate reading a .uhc file."""
        # Generate simulated manifest
        file_hash = hashlib.sha256(str(file_path).encode()).hexdigest()[:16]

        return {
            "manifest": {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "source_device": "TABLET-001",
                "collector_id": "FC-001",
                "record_count": random.randint(15, 50),
                "checksum": file_hash,
                "vocab_versions": {
                    "building_types": "1.0.0",
                    "document_types": "1.2.0"
                }
            },
            "records": self._generate_simulated_records(random.randint(15, 50))
        }

    def _generate_simulated_records(self, count: int) -> List[Dict[str, Any]]:
        """Generate simulated import records."""
        records = []

        for i in range(count):
            record_type = random.choice(["building", "unit", "person", "claim"])

            record = {
                "type": record_type,
                "id": f"REC-{i+1:04d}",
                "data": self._generate_record_data(record_type, i)
            }
            records.append(record)

        return records

    def _generate_record_data(self, record_type: str, index: int) -> Dict[str, Any]:
        """Generate simulated record data."""
        if record_type == "building":
            return {
                "building_id": f"01-01-01-001-00{random.randint(1,9)}-{index+1:05d}",
                "neighborhood_code": f"00{random.randint(1,10)}",
                "building_type": random.choice(["residential", "commercial", "mixed_use"]),
                "building_status": random.choice(["intact", "minor_damage", "major_damage"]),
            }
        elif record_type == "unit":
            return {
                "unit_id": f"01-01-01-001-001-0000{index+1}-00{random.randint(1,9)}",
                "unit_type": random.choice(["apartment", "shop", "office"]),
                "floor_number": random.randint(0, 5),
            }
        elif record_type == "person":
            return {
                "first_name_ar": random.choice(["محمد", "أحمد", "علي", "فاطمة", "زهرة"]),
                "last_name_ar": random.choice(["الحلبي", "الشامي", "الأحمد", "العلي"]),
                "national_id": str(random.randint(10000000000, 99999999999)),
                "gender": random.choice(["male", "female"]),
            }
        else:  # claim
            return {
                "claim_type": "ownership",
                "status": "draft",
            }

    def validate_manifest(self, manifest: Dict[str, Any]) -> bool:
        """Validate import manifest."""
        required_fields = ["version", "created_at", "record_count", "checksum"]
        return all(field in manifest for field in required_fields)

    def extract_records(self, data: Dict[str, Any]) -> Generator[ImportRecord, None, None]:
        """Extract records from import data."""
        records = data.get("records", [])

        for record in records:
            yield ImportRecord(
                record_id=record["id"],
                record_type=record["type"],
                data=record["data"],
                status=ImportStatus.PENDING
            )

    def validate_record(self, record: ImportRecord) -> ImportRecord:
        """Validate a record with simulated results."""
        # Simulate various validation outcomes
        outcome = random.random()

        if outcome < 0.7:  # 70% valid
            record.status = ImportStatus.VALID
        elif outcome < 0.85:  # 15% warnings
            record.status = ImportStatus.WARNING
            record.warnings = [
                random.choice([
                    "Phone number format may be incorrect",
                    "Coordinates outside expected region",
                    "Missing optional field: email",
                    "Document type deprecated, using alternative",
                ])
            ]
        elif outcome < 0.95:  # 10% errors
            record.status = ImportStatus.ERROR
            record.errors = [
                random.choice([
                    "Required field missing: national_id",
                    "Invalid building ID format",
                    "Invalid date format",
                    "Unit type not in vocabulary",
                ])
            ]
        else:  # 5% duplicates
            record.status = ImportStatus.DUPLICATE
            record.duplicate_of = f"EXISTING-{random.randint(100, 999)}"
            record.warnings = ["Potential duplicate detected"]

        return record

    def detect_duplicates(self, record: ImportRecord) -> ImportRecord:
        """Simulate duplicate detection."""
        # Already handled in validate_record for simulation
        return record

    def commit_record(self, record: ImportRecord) -> bool:
        """Simulate committing a record."""
        if record.status in [ImportStatus.VALID, ImportStatus.WARNING]:
            record.status = ImportStatus.IMPORTED
            return True
        return False


class ImportService:
    """Main import service using the pluggable importer interface."""

    def __init__(self, db: Database, importer: Optional[ImporterInterface] = None):
        self.db = db
        self.importer = importer or SimulatedImporter(db)
        self._staging: List[ImportRecord] = []
        self._current_file: Optional[Path] = None
        self._manifest: Optional[Dict[str, Any]] = None

    def load_file(self, file_path: Path) -> Dict[str, Any]:
        """Load and parse import file."""
        self._current_file = file_path
        data = self.importer.read_file(file_path)
        self._manifest = data.get("manifest", {})

        if not self.importer.validate_manifest(self._manifest):
            raise ValueError("Invalid manifest in import file")

        logger.info(f"Loaded import file: {file_path.name}")
        logger.info(f"  Records: {self._manifest.get('record_count', 0)}")

        return {
            "file_name": file_path.name,
            "manifest": self._manifest,
            "record_count": self._manifest.get("record_count", 0)
        }

    def validate_all(self, progress_callback=None) -> List[ImportRecord]:
        """Validate all records from the loaded file."""
        if not self._current_file:
            raise ValueError("No file loaded")

        data = self.importer.read_file(self._current_file)
        self._staging = []
        total = len(data.get("records", []))

        for i, record in enumerate(self.importer.extract_records(data)):
            # Validate
            validated = self.importer.validate_record(record)
            # Check duplicates
            validated = self.importer.detect_duplicates(validated)
            self._staging.append(validated)

            if progress_callback:
                progress_callback(i + 1, total)

        logger.info(f"Validation complete: {len(self._staging)} records")
        return self._staging

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results."""
        summary = {
            "total": len(self._staging),
            "valid": 0,
            "warnings": 0,
            "errors": 0,
            "duplicates": 0,
        }

        for record in self._staging:
            if record.status == ImportStatus.VALID:
                summary["valid"] += 1
            elif record.status == ImportStatus.WARNING:
                summary["warnings"] += 1
            elif record.status == ImportStatus.ERROR:
                summary["errors"] += 1
            elif record.status == ImportStatus.DUPLICATE:
                summary["duplicates"] += 1

        return summary

    def get_records_by_status(self, status: ImportStatus) -> List[ImportRecord]:
        """Get records filtered by status."""
        return [r for r in self._staging if r.status == status]

    def resolve_record(self, record_id: str, resolution: str) -> bool:
        """Set resolution for a record (merge, keep_existing, keep_new, skip)."""
        for record in self._staging:
            if record.record_id == record_id:
                record.resolution = resolution
                if resolution == "skip":
                    record.status = ImportStatus.SKIPPED
                elif resolution in ["merge", "keep_new"]:
                    record.status = ImportStatus.VALID
                return True
        return False

    def commit(self, progress_callback=None) -> ImportResult:
        """Commit validated records to database."""
        import_id = f"IMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        imported = 0
        failed = 0
        skipped = 0
        warnings = 0
        errors = []

        total = len(self._staging)

        for i, record in enumerate(self._staging):
            if record.status == ImportStatus.SKIPPED:
                skipped += 1
            elif record.status == ImportStatus.ERROR:
                failed += 1
                errors.extend(record.errors)
            elif record.status in [ImportStatus.VALID, ImportStatus.WARNING]:
                if self.importer.commit_record(record):
                    imported += 1
                    if record.warnings:
                        warnings += 1
                else:
                    failed += 1

            if progress_callback:
                progress_callback(i + 1, total)

        # Record import history
        self._save_import_history(import_id, imported, failed, skipped, errors)

        result = ImportResult(
            success=failed == 0,
            total_records=total,
            imported=imported,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            errors=errors[:10],  # Limit errors
            import_id=import_id
        )

        logger.info(f"Import complete: {import_id}")
        logger.info(f"  Imported: {imported}, Failed: {failed}, Skipped: {skipped}")

        return result

    def _save_import_history(self, import_id: str, imported: int, failed: int, skipped: int, errors: List[str]):
        """Save import history to database."""
        query = """
            INSERT INTO import_history (
                import_id, file_name, file_path, file_hash, import_date,
                imported_by, status, total_records, imported_records,
                failed_records, warnings_count, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            import_id,
            self._current_file.name if self._current_file else "",
            str(self._current_file) if self._current_file else "",
            self._manifest.get("checksum", "") if self._manifest else "",
            datetime.now().isoformat(),
            "system",  # Would be actual user in production
            "completed" if failed == 0 else "completed_with_errors",
            len(self._staging),
            imported,
            failed,
            sum(1 for r in self._staging if r.warnings),
            json.dumps(errors[:10])
        )
        self.db.execute(query, params)

    def clear(self):
        """Clear staging area."""
        self._staging = []
        self._current_file = None
        self._manifest = None
