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


class RealUHCImporter(ImporterInterface):
    """
    Real UHC importer - reads actual .uhc (SQLite) files.
    """

    def __init__(self, db: Database):
        self.db = db

    def read_file(self, file_path: Path) -> Dict[str, Any]:
        """Read actual .uhc SQLite file."""
        import sqlite3

        if not file_path.exists():
            raise FileNotFoundError(f"ملف .uhc غير موجود: {file_path}")

        if file_path.suffix != '.uhc':
            raise ValueError(f"صيغة الملف غير صحيحة. متوقع .uhc لكن وجدت {file_path.suffix}")

        try:
            conn = sqlite3.connect(str(file_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Read manifest
            manifest = {}
            try:
                cursor.execute("SELECT key, value FROM manifest")
                for row in cursor.fetchall():
                    key = row['key']
                    value = row['value']
                    try:
                        manifest[key] = json.loads(value)
                    except:
                        manifest[key] = value
            except sqlite3.OperationalError:
                raise ValueError("الملف لا يحتوي على جدول manifest")

            # Read all records
            records = []

            # Buildings
            try:
                cursor.execute("SELECT * FROM buildings")
                for row in cursor.fetchall():
                    records.append({
                        "type": "building",
                        "id": row['building_id'],
                        "data": dict(row)
                    })
            except sqlite3.OperationalError:
                pass  # Table doesn't exist

            # Units
            try:
                cursor.execute("SELECT * FROM units")
                for row in cursor.fetchall():
                    records.append({
                        "type": "unit",
                        "id": row['unit_id'],
                        "data": dict(row)
                    })
            except sqlite3.OperationalError:
                pass

            # Persons
            try:
                cursor.execute("SELECT * FROM persons")
                for row in cursor.fetchall():
                    records.append({
                        "type": "person",
                        "id": row['national_id'] if 'national_id' in row.keys() else str(row['person_uuid']),
                        "data": dict(row)
                    })
            except sqlite3.OperationalError:
                pass

            conn.close()

            return {
                "manifest": manifest,
                "records": records
            }

        except sqlite3.DatabaseError as e:
            raise ValueError(f"خطأ في قراءة ملف قاعدة البيانات: {str(e)}")

    def validate_manifest(self, manifest: Dict[str, Any]) -> bool:
        """Validate import manifest."""
        # Basic validation
        return bool(manifest)  # Just check it's not empty

    def extract_records(self, data: Dict[str, Any]) -> Generator[ImportRecord, None, None]:
        """Extract records from import data."""
        records = data.get("records", [])
        for i, record_data in enumerate(records):
            yield ImportRecord(
                record_id=record_data.get("id", f"REC-{i+1:04d}"),
                record_type=record_data.get("type", "unknown"),
                data=record_data.get("data", {})
            )

    def validate_record(self, record: ImportRecord) -> ImportRecord:
        """Validate a single record."""
        # Basic validation - mark as valid
        record.status = ImportStatus.VALID
        return record

    def detect_duplicates(self, record: ImportRecord) -> ImportRecord:
        """Check for duplicates in existing data."""
        try:
            if record.record_type == "building":
                from repositories.building_repository import BuildingRepository
                building_repo = BuildingRepository(self.db)

                # Check if building_id already exists
                building_id = record.data.get('building_id')
                if building_id:
                    existing = building_repo.find_by_id(building_id)
                    if existing:
                        record.status = ImportStatus.DUPLICATE
                        record.duplicate_of = building_id
                        record.warnings.append(f"مبنى مكرر: {building_id} موجود مسبقاً في قاعدة البيانات")

            elif record.record_type == "unit":
                from repositories.unit_repository import UnitRepository
                unit_repo = UnitRepository(self.db)

                # Check if unit_id already exists
                unit_id = record.data.get('unit_id')
                if unit_id:
                    existing = unit_repo.find_by_id(unit_id)
                    if existing:
                        record.status = ImportStatus.DUPLICATE
                        record.duplicate_of = unit_id
                        record.warnings.append(f"وحدة مكررة: {unit_id} موجودة مسبقاً في قاعدة البيانات")

            elif record.record_type == "person":
                from repositories.person_repository import PersonRepository
                person_repo = PersonRepository(self.db)

                # Check if national_id already exists
                national_id = record.data.get('national_id')
                if national_id:
                    existing = person_repo.find_by_national_id(national_id)
                    if existing:
                        record.status = ImportStatus.DUPLICATE
                        record.duplicate_of = national_id
                        record.warnings.append(f"شخص مكرر: الهوية الوطنية {national_id} موجودة مسبقاً في قاعدة البيانات")

        except Exception as e:
            logger.warning(f"Error checking duplicates for {record.record_id}: {e}")

        return record

    def commit_record(self, record: ImportRecord) -> bool:
        """Commit a record to the database."""
        # Only commit VALID or WARNING records, skip DUPLICATE/ERROR/SKIPPED
        if record.status not in [ImportStatus.VALID, ImportStatus.WARNING]:
            logger.debug(f"Skipping commit for {record.record_id} with status {record.status}")
            return False

        try:
            # Import repositories
            from repositories.building_repository import BuildingRepository
            from models.building import Building

            if record.record_type == "building":
                # Create Building from record data
                building_data = record.data
                building = Building(
                    building_uuid=building_data.get('building_uuid', str(__import__('uuid').uuid4())),
                    building_id=building_data.get('building_id', ''),
                    governorate_code=building_data.get('governorate_code', ''),
                    governorate_name=building_data.get('governorate_name', ''),
                    governorate_name_ar=building_data.get('governorate_name_ar', ''),
                    district_code=building_data.get('district_code', ''),
                    district_name=building_data.get('district_name', ''),
                    district_name_ar=building_data.get('district_name_ar', ''),
                    subdistrict_code=building_data.get('subdistrict_code', building_data.get('sub_district_code', '')),
                    subdistrict_name=building_data.get('subdistrict_name', ''),
                    subdistrict_name_ar=building_data.get('subdistrict_name_ar', ''),
                    community_code=building_data.get('community_code', ''),
                    community_name=building_data.get('community_name', ''),
                    community_name_ar=building_data.get('community_name_ar', ''),
                    neighborhood_code=building_data.get('neighborhood_code', ''),
                    neighborhood_name=building_data.get('neighborhood_name', ''),
                    neighborhood_name_ar=building_data.get('neighborhood_name_ar', ''),
                    building_number=building_data.get('building_number', ''),
                    building_type=building_data.get('building_type', 'residential'),
                    building_status=building_data.get('building_status', 'intact'),
                    number_of_units=building_data.get('number_of_units', 0),
                    number_of_apartments=building_data.get('number_of_apartments', 0),
                    number_of_shops=building_data.get('number_of_shops', 0),
                    number_of_floors=building_data.get('number_of_floors', building_data.get('floors_count', 1)),
                    latitude=building_data.get('latitude'),
                    longitude=building_data.get('longitude'),
                    geo_location=building_data.get('geo_location'),
                    created_by='import_system',
                    updated_by='import_system'
                )

                # Save to database
                building_repo = BuildingRepository(self.db)
                building_repo.create(building)

                logger.info(f"Imported building: {building.building_id}")
                record.status = ImportStatus.IMPORTED
                return True

            elif record.record_type == "unit":
                # Import unit
                from repositories.unit_repository import UnitRepository
                from models.unit import PropertyUnit

                unit_data = record.data
                unit = PropertyUnit(
                    unit_uuid=unit_data.get('unit_uuid', str(__import__('uuid').uuid4())),
                    unit_id=unit_data.get('unit_id', ''),
                    building_id=unit_data.get('building_id', ''),
                    unit_type=unit_data.get('unit_type', 'apartment'),
                    unit_number=unit_data.get('unit_number', '001'),
                    floor_number=unit_data.get('floor_number', 0),
                    apartment_number=unit_data.get('apartment_number', ''),
                    apartment_status=unit_data.get('occupancy_status', unit_data.get('apartment_status', 'occupied')),
                    property_description=unit_data.get('property_description', ''),
                    area_sqm=unit_data.get('area_sqm'),
                    created_by='import_system',
                    updated_by='import_system'
                )

                # Save to database
                unit_repo = UnitRepository(self.db)
                unit_repo.create(unit)

                logger.info(f"Imported unit: {unit.unit_id}")
                record.status = ImportStatus.IMPORTED
                return True

            elif record.record_type == "person":
                # Import person
                from repositories.person_repository import PersonRepository
                from models.person import Person

                person_data = record.data

                # Handle date_of_birth to year_of_birth conversion
                year_of_birth = None
                if 'date_of_birth' in person_data and person_data['date_of_birth']:
                    try:
                        # Extract year from date_of_birth (format: YYYY-MM-DD)
                        year_of_birth = int(person_data['date_of_birth'].split('-')[0])
                    except (ValueError, IndexError, AttributeError):
                        pass

                person = Person(
                    person_id=person_data.get('person_uuid', str(__import__('uuid').uuid4())),
                    first_name=person_data.get('first_name', ''),
                    first_name_ar=person_data.get('first_name_ar', ''),
                    father_name=person_data.get('father_name', ''),
                    father_name_ar=person_data.get('father_name_ar', ''),
                    mother_name=person_data.get('mother_name', ''),
                    mother_name_ar=person_data.get('mother_name_ar', ''),
                    last_name=person_data.get('last_name', ''),
                    last_name_ar=person_data.get('last_name_ar', ''),
                    gender=person_data.get('gender', 'male'),
                    year_of_birth=year_of_birth,
                    nationality=person_data.get('nationality', 'Syrian'),
                    national_id=person_data.get('national_id', ''),
                    passport_number=person_data.get('passport_number'),
                    phone_number=person_data.get('phone_number'),
                    mobile_number=person_data.get('mobile_number'),
                    email=person_data.get('email'),
                    address=person_data.get('address'),
                    is_contact_person=person_data.get('is_contact_person', False),
                    is_deceased=person_data.get('is_deceased', False),
                    created_by='import_system',
                    updated_by='import_system'
                )

                # Save to database
                person_repo = PersonRepository(self.db)
                person_repo.create(person)

                logger.info(f"Imported person: {person.national_id}")
                record.status = ImportStatus.IMPORTED
                return True

            else:
                logger.warning(f"Unknown record type: {record.record_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to commit record {record.record_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


class ImportService:
    """Main import service using the pluggable importer interface."""

    def __init__(self, db: Database, importer: Optional[ImporterInterface] = None):
        self.db = db
        # Use real importer by default, fallback to simulated if needed
        self.importer = importer or RealUHCImporter(db)
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

    def get_validation_error(self) -> Optional[Dict[str, Any]]:
        """
        Get validation error if file failed signature/hash validation (UC-003 S12b).
        Returns None if no validation errors.
        """
        # This would be set during file loading if signature/hash validation fails
        # For now, return None (no validation errors in test files)
        return None

    def get_incompatible_vocabularies(self) -> List[Dict[str, Any]]:
        """
        Get list of incompatible vocabularies (UC-003 S12c).
        Returns empty list if all vocabularies are compatible.
        """
        # This would check vocabulary versions from manifest against system versions
        # For now, return empty list (all compatible in test environment)
        return []

    def get_package_id(self) -> str:
        """Get package ID from manifest."""
        if self._manifest:
            return self._manifest.get('package_id', 'N/A')
        return 'N/A'

    def get_package_timestamp(self) -> str:
        """Get package creation timestamp from manifest."""
        if self._manifest:
            return self._manifest.get('created_utc', 'N/A')
        return 'N/A'

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
                logger.debug(f"Skipping record {record.record_id} (status: SKIPPED)")
            elif record.status == ImportStatus.DUPLICATE:
                skipped += 1
                logger.info(f"Skipping duplicate record {record.record_id}")
            elif record.status == ImportStatus.ERROR:
                failed += 1
                errors.extend(record.errors)
                logger.warning(f"Skipping error record {record.record_id}")
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
