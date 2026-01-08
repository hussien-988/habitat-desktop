"""
Vocabulary Version Management Service
=====================================
Implements comprehensive vocabulary versioning system as per UC-009b specifications.

Features:
- Semantic versioning (MAJOR.MINOR.PATCH)
- Version history and rollback support
- Effective date management with no overlap validation
- Import/export vocabulary definitions (CSV/JSON)
- Deprecation handling for terms still in use
- Multi-language support (Arabic, English)
- Audit trail for all vocabulary changes
- Mobile sync export generation
"""

import json
import csv
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import logging
import re

from repositories.db_adapter import DatabaseFactory, DatabaseAdapter, RowProxy, DatabaseType

logger = logging.getLogger(__name__)


class VersionChangeType(Enum):
    """Type of version change."""
    MAJOR = "major"  # Breaking changes, incompatible with previous versions
    MINOR = "minor"  # New terms added, backwards compatible
    PATCH = "patch"  # Bug fixes, translations, no structural changes


class TermStatus(Enum):
    """Status of a vocabulary term."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PENDING = "pending"  # In staging, not yet activated


class VocabularySource(Enum):
    """Source of vocabulary update."""
    MANUAL = "manual_edit"
    IMPORT = "imported_file"
    CENTRAL = "central_configuration"


@dataclass
class VocabularyTerm:
    """Represents a single vocabulary term."""
    term_code: str
    term_label: str  # Default language (English)
    term_label_ar: str = ""  # Arabic translation
    term_label_local: str = ""  # Other local translations
    description: str = ""
    description_ar: str = ""
    status: TermStatus = TermStatus.ACTIVE
    sort_order: int = 0
    parent_code: Optional[str] = None  # For hierarchical vocabularies
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term_code": self.term_code,
            "term_label": self.term_label,
            "term_label_ar": self.term_label_ar,
            "term_label_local": self.term_label_local,
            "description": self.description,
            "description_ar": self.description_ar,
            "status": self.status.value,
            "sort_order": self.sort_order,
            "parent_code": self.parent_code,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VocabularyTerm':
        """Create from dictionary."""
        status = data.get("status", "active")
        if isinstance(status, str):
            status = TermStatus(status)
        return cls(
            term_code=data["term_code"],
            term_label=data["term_label"],
            term_label_ar=data.get("term_label_ar", ""),
            term_label_local=data.get("term_label_local", ""),
            description=data.get("description", ""),
            description_ar=data.get("description_ar", ""),
            status=status,
            sort_order=data.get("sort_order", 0),
            parent_code=data.get("parent_code"),
            metadata=data.get("metadata", {})
        )


@dataclass
class VocabularyVersion:
    """Represents a version of a vocabulary."""
    vocabulary_name: str
    version: str  # MAJOR.MINOR.PATCH format
    description: str = ""
    description_ar: str = ""
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    source: VocabularySource = VocabularySource.MANUAL
    source_file: Optional[str] = None
    is_active: bool = False
    is_superseded: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    activated_at: Optional[datetime] = None
    activated_by: str = ""
    terms: List[VocabularyTerm] = field(default_factory=list)
    checksum: str = ""

    def __post_init__(self):
        """Validate version format."""
        if not self._validate_version_format(self.version):
            raise ValueError(f"Invalid version format: {self.version}. Expected MAJOR.MINOR.PATCH")
        if not self.checksum:
            self.checksum = self._compute_checksum()

    @staticmethod
    def _validate_version_format(version: str) -> bool:
        """Validate semantic version format."""
        pattern = r'^\d+\.\d+\.\d+$'
        return bool(re.match(pattern, version))

    def _compute_checksum(self) -> str:
        """Compute checksum of vocabulary content."""
        content = json.dumps(
            [t.to_dict() for t in sorted(self.terms, key=lambda x: x.term_code)],
            sort_keys=True
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_version_tuple(self) -> Tuple[int, int, int]:
        """Get version as tuple for comparison."""
        parts = self.version.split('.')
        return (int(parts[0]), int(parts[1]), int(parts[2]))

    def increment_version(self, change_type: VersionChangeType) -> str:
        """Calculate next version based on change type."""
        major, minor, patch = self.get_version_tuple()
        if change_type == VersionChangeType.MAJOR:
            return f"{major + 1}.0.0"
        elif change_type == VersionChangeType.MINOR:
            return f"{major}.{minor + 1}.0"
        else:
            return f"{major}.{minor}.{patch + 1}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "vocabulary_name": self.vocabulary_name,
            "version": self.version,
            "description": self.description,
            "description_ar": self.description_ar,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "source": self.source.value,
            "source_file": self.source_file,
            "is_active": self.is_active,
            "is_superseded": self.is_superseded,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "activated_by": self.activated_by,
            "terms": [t.to_dict() for t in self.terms],
            "checksum": self.checksum
        }


@dataclass
class VocabularyChangeLog:
    """Audit log entry for vocabulary changes."""
    id: int = 0
    vocabulary_name: str = ""
    version_from: Optional[str] = None
    version_to: str = ""
    change_type: str = ""  # created, activated, superseded, term_added, term_deprecated, etc.
    change_details: Dict[str, Any] = field(default_factory=dict)
    changed_by: str = ""
    changed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VocabularyVersionService:
    """
    Comprehensive vocabulary version management service.

    Implements UC-009b requirements:
    - Semantic versioning (MAJOR.MINOR.PATCH)
    - Effective date management
    - Import/export functionality
    - Deprecation handling
    - Audit trail
    - Mobile sync export
    """

    # Standard vocabularies as per FSD
    STANDARD_VOCABULARIES = [
        "building_type",
        "ownership_type",
        "case_type",
        "nature_of_works",
        "claim_status",
        "document_type",
        "building_condition",
        "land_use_type",
        "verification_status",
        "resolution_type"
    ]

    def __init__(self, db_path: str = None):
        """Initialize vocabulary version service."""
        self.db_path = db_path
        self._adapter: DatabaseAdapter = DatabaseFactory.create()
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure vocabulary versioning tables exist."""
        with self._adapter.cursor() as cursor:
            # Vocabulary versions table - handle AUTOINCREMENT difference
            if self._adapter.db_type == DatabaseType.POSTGRESQL:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_versions (
                        id SERIAL PRIMARY KEY,
                        vocabulary_name TEXT NOT NULL,
                        version TEXT NOT NULL,
                        description TEXT,
                        description_ar TEXT,
                        effective_from DATE,
                        effective_to DATE,
                        source TEXT DEFAULT 'manual_edit',
                        source_file TEXT,
                        is_active INTEGER DEFAULT 0,
                        is_superseded INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        activated_at TIMESTAMP,
                        activated_by TEXT,
                        checksum TEXT,
                        UNIQUE(vocabulary_name, version)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vocabulary_name TEXT NOT NULL,
                        version TEXT NOT NULL,
                        description TEXT,
                        description_ar TEXT,
                        effective_from DATE,
                        effective_to DATE,
                        source TEXT DEFAULT 'manual_edit',
                        source_file TEXT,
                        is_active INTEGER DEFAULT 0,
                        is_superseded INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        activated_at TIMESTAMP,
                        activated_by TEXT,
                        checksum TEXT,
                        UNIQUE(vocabulary_name, version)
                    )
                """)

            # Vocabulary terms table
            if self._adapter.db_type == DatabaseType.POSTGRESQL:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_terms (
                        id SERIAL PRIMARY KEY,
                        version_id INTEGER NOT NULL,
                        term_code TEXT NOT NULL,
                        term_label TEXT NOT NULL,
                        term_label_ar TEXT,
                        term_label_local TEXT,
                        description TEXT,
                        description_ar TEXT,
                        status TEXT DEFAULT 'active',
                        sort_order INTEGER DEFAULT 0,
                        parent_code TEXT,
                        metadata TEXT,
                        FOREIGN KEY (version_id) REFERENCES vocabulary_versions(id),
                        UNIQUE(version_id, term_code)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_terms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_id INTEGER NOT NULL,
                        term_code TEXT NOT NULL,
                        term_label TEXT NOT NULL,
                        term_label_ar TEXT,
                        term_label_local TEXT,
                        description TEXT,
                        description_ar TEXT,
                        status TEXT DEFAULT 'active',
                        sort_order INTEGER DEFAULT 0,
                        parent_code TEXT,
                        metadata TEXT,
                        FOREIGN KEY (version_id) REFERENCES vocabulary_versions(id),
                        UNIQUE(version_id, term_code)
                    )
                """)

            # Vocabulary change log table
            if self._adapter.db_type == DatabaseType.POSTGRESQL:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_change_log (
                        id SERIAL PRIMARY KEY,
                        vocabulary_name TEXT NOT NULL,
                        version_from TEXT,
                        version_to TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        change_details TEXT,
                        changed_by TEXT NOT NULL,
                        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_change_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vocabulary_name TEXT NOT NULL,
                        version_from TEXT,
                        version_to TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        change_details TEXT,
                        changed_by TEXT NOT NULL,
                        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Vocabulary usage tracking (to prevent deletion of terms in use)
            if self._adapter.db_type == DatabaseType.POSTGRESQL:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_usage (
                        id SERIAL PRIMARY KEY,
                        vocabulary_name TEXT NOT NULL,
                        term_code TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        column_name TEXT NOT NULL,
                        record_count INTEGER DEFAULT 0,
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vocabulary_name TEXT NOT NULL,
                        term_code TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        column_name TEXT NOT NULL,
                        record_count INTEGER DEFAULT 0,
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vocab_versions_name
                ON vocabulary_versions(vocabulary_name, is_active)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vocab_terms_code
                ON vocabulary_terms(version_id, term_code)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vocab_changelog
                ON vocabulary_change_log(vocabulary_name, changed_at)
            """)

            logger.info("Vocabulary versioning tables initialized")

    def get_vocabulary_list(self) -> List[Dict[str, Any]]:
        """Get list of all vocabularies with their current active version."""
        rows = self._adapter.fetch_all("""
            SELECT
                vocabulary_name,
                version,
                description,
                effective_from,
                is_active,
                created_at,
                (SELECT COUNT(*) FROM vocabulary_terms WHERE version_id = vv.id) as term_count
            FROM vocabulary_versions vv
            WHERE is_active = 1
            ORDER BY vocabulary_name
        """)

        results = []
        for row in rows:
            results.append({
                "vocabulary_name": row["vocabulary_name"],
                "current_version": row["version"],
                "description": row["description"],
                "effective_from": row["effective_from"],
                "term_count": row["term_count"],
                "created_at": row["created_at"]
            })

        return results

    def get_vocabulary_versions(self, vocabulary_name: str) -> List[VocabularyVersion]:
        """Get all versions of a vocabulary."""
        rows = self._adapter.fetch_all("""
            SELECT * FROM vocabulary_versions
            WHERE vocabulary_name = ?
            ORDER BY created_at DESC
        """, (vocabulary_name,))

        versions = []
        for row in rows:
            version = VocabularyVersion(
                vocabulary_name=row["vocabulary_name"],
                version=row["version"],
                description=row["description"] or "",
                description_ar=row["description_ar"] or "",
                effective_from=date.fromisoformat(row["effective_from"]) if row["effective_from"] else None,
                effective_to=date.fromisoformat(row["effective_to"]) if row["effective_to"] else None,
                source=VocabularySource(row["source"]) if row["source"] else VocabularySource.MANUAL,
                source_file=row["source_file"],
                is_active=bool(row["is_active"]),
                is_superseded=bool(row["is_superseded"]),
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
                created_by=row["created_by"] or "",
                activated_at=datetime.fromisoformat(row["activated_at"]) if row["activated_at"] else None,
                activated_by=row["activated_by"] or "",
                checksum=row["checksum"] or ""
            )

            # Load terms
            term_rows = self._adapter.fetch_all("""
                SELECT * FROM vocabulary_terms WHERE version_id = ?
                ORDER BY sort_order, term_code
            """, (row["id"],))

            for term_row in term_rows:
                version.terms.append(VocabularyTerm(
                    term_code=term_row["term_code"],
                    term_label=term_row["term_label"],
                    term_label_ar=term_row["term_label_ar"] or "",
                    term_label_local=term_row["term_label_local"] or "",
                    description=term_row["description"] or "",
                    description_ar=term_row["description_ar"] or "",
                    status=TermStatus(term_row["status"]) if term_row["status"] else TermStatus.ACTIVE,
                    sort_order=term_row["sort_order"] or 0,
                    parent_code=term_row["parent_code"],
                    metadata=json.loads(term_row["metadata"]) if term_row["metadata"] else {}
                ))

            versions.append(version)

        return versions

    def get_active_version(self, vocabulary_name: str) -> Optional[VocabularyVersion]:
        """Get the currently active version of a vocabulary."""
        versions = self.get_vocabulary_versions(vocabulary_name)
        for v in versions:
            if v.is_active:
                return v
        return None

    def create_vocabulary_version(
        self,
        vocabulary_name: str,
        version: str,
        terms: List[VocabularyTerm],
        description: str = "",
        description_ar: str = "",
        effective_from: Optional[date] = None,
        effective_to: Optional[date] = None,
        source: VocabularySource = VocabularySource.MANUAL,
        source_file: Optional[str] = None,
        created_by: str = "system"
    ) -> VocabularyVersion:
        """Create a new vocabulary version in staging (not yet active)."""

        # Validate term codes are unique
        codes = [t.term_code for t in terms]
        if len(codes) != len(set(codes)):
            raise ValueError("Duplicate term codes found in vocabulary")

        # Check if version already exists
        existing = self._adapter.fetch_one("""
            SELECT id FROM vocabulary_versions
            WHERE vocabulary_name = ? AND version = ?
        """, (vocabulary_name, version))

        if existing:
            raise ValueError(f"Version {version} already exists for {vocabulary_name}")

        # Create vocabulary version
        vocab_version = VocabularyVersion(
            vocabulary_name=vocabulary_name,
            version=version,
            description=description,
            description_ar=description_ar,
            effective_from=effective_from,
            effective_to=effective_to,
            source=source,
            source_file=source_file,
            is_active=False,
            created_by=created_by,
            terms=terms
        )

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                INSERT INTO vocabulary_versions (
                    vocabulary_name, version, description, description_ar,
                    effective_from, effective_to, source, source_file,
                    is_active, created_by, checksum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                vocabulary_name, version, description, description_ar,
                effective_from.isoformat() if effective_from else None,
                effective_to.isoformat() if effective_to else None,
                source.value, source_file, created_by, vocab_version.checksum
            ))

            version_id = cursor.lastrowid

            # Insert terms
            for term in terms:
                cursor.execute("""
                    INSERT INTO vocabulary_terms (
                        version_id, term_code, term_label, term_label_ar,
                        term_label_local, description, description_ar,
                        status, sort_order, parent_code, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    version_id, term.term_code, term.term_label, term.term_label_ar,
                    term.term_label_local, term.description, term.description_ar,
                    term.status.value, term.sort_order, term.parent_code,
                    json.dumps(term.metadata) if term.metadata else None
                ))

            # Log the change
            self._log_change(
                cursor, vocabulary_name, None, version,
                "version_created",
                {"term_count": len(terms), "source": source.value},
                created_by
            )

            logger.info(f"Created vocabulary version {vocabulary_name} v{version}")

        return vocab_version

    def validate_vocabulary_version(
        self,
        vocabulary_name: str,
        version: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate a vocabulary version before activation.

        Checks:
        - No duplicate codes
        - No overlapping effective date ranges with other active versions
        - Required translations present
        - Valid parent codes for hierarchical terms
        """
        errors = []

        # Get the version
        row = self._adapter.fetch_one("""
            SELECT * FROM vocabulary_versions
            WHERE vocabulary_name = ? AND version = ?
        """, (vocabulary_name, version))

        if not row:
            return False, [f"Version {version} not found"]

        version_id = row["id"]
        effective_from = row["effective_from"]
        effective_to = row["effective_to"]

        # Check for overlapping date ranges
        if effective_from:
            overlaps = self._adapter.fetch_all("""
                SELECT version, effective_from, effective_to
                FROM vocabulary_versions
                WHERE vocabulary_name = ?
                AND id != ?
                AND is_active = 1
                AND (
                    (effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?))
                    OR (effective_from >= ? AND (? IS NULL OR effective_from <= ?))
                )
            """, (
                vocabulary_name, version_id,
                effective_from, effective_from,
                effective_from, effective_to, effective_to
            ))

            for overlap in overlaps:
                errors.append(
                    f"Effective date range overlaps with version {overlap['version']} "
                    f"({overlap['effective_from']} - {overlap['effective_to'] or 'ongoing'})"
                )

        # Get terms
        terms = self._adapter.fetch_all("""
            SELECT * FROM vocabulary_terms WHERE version_id = ?
        """, (version_id,))

        # Check for duplicate codes
        codes = [t["term_code"] for t in terms]
        duplicates = [c for c in codes if codes.count(c) > 1]
        if duplicates:
            errors.append(f"Duplicate term codes: {set(duplicates)}")

        # Check parent codes exist
        for term in terms:
            if term["parent_code"]:
                if term["parent_code"] not in codes:
                    errors.append(
                        f"Term {term['term_code']} has invalid parent_code: {term['parent_code']}"
                    )

        # Check for terms without Arabic translations (warning)
        terms_without_ar = [t["term_code"] for t in terms if not t["term_label_ar"]]
        if terms_without_ar:
            errors.append(
                f"Warning: {len(terms_without_ar)} terms missing Arabic translations"
            )

        return len([e for e in errors if not e.startswith("Warning")]) == 0, errors

    def activate_vocabulary_version(
        self,
        vocabulary_name: str,
        version: str,
        activated_by: str
    ) -> bool:
        """
        Activate a vocabulary version.

        This will:
        - Mark the previous active version as superseded
        - Mark this version as active
        - Update activation timestamp
        """
        # First validate
        is_valid, errors = self.validate_vocabulary_version(vocabulary_name, version)
        if not is_valid:
            raise ValueError(f"Validation failed: {'; '.join(errors)}")

        with self._adapter.cursor() as cursor:
            # Get previous active version
            cursor.execute("""
                SELECT version FROM vocabulary_versions
                WHERE vocabulary_name = ? AND is_active = 1
            """, (vocabulary_name,))

            previous = cursor.fetchone()
            previous_version = previous["version"] if previous else None

            # Mark previous as superseded
            if previous:
                cursor.execute("""
                    UPDATE vocabulary_versions
                    SET is_active = 0, is_superseded = 1
                    WHERE vocabulary_name = ? AND is_active = 1
                """, (vocabulary_name,))

            # Activate new version
            activation_time = datetime.utcnow().isoformat()
            cursor.execute("""
                UPDATE vocabulary_versions
                SET is_active = 1, activated_at = ?, activated_by = ?
                WHERE vocabulary_name = ? AND version = ?
            """, (activation_time, activated_by, vocabulary_name, version))

            # Log the change
            self._log_change(
                cursor, vocabulary_name, previous_version, version,
                "version_activated",
                {"previous_version": previous_version},
                activated_by
            )

            logger.info(f"Activated vocabulary {vocabulary_name} v{version}")

        return True

    def import_vocabulary_file(
        self,
        file_path: str,
        vocabulary_name: str,
        imported_by: str
    ) -> Tuple[bool, List[VocabularyTerm], List[str]]:
        """
        Import vocabulary terms from CSV or JSON file.

        Returns:
        - Success flag
        - List of parsed terms (for staging)
        - List of validation errors/warnings
        """
        errors = []
        terms = []

        path = Path(file_path)
        if not path.exists():
            return False, [], [f"File not found: {file_path}"]

        try:
            if path.suffix.lower() == '.json':
                terms, errors = self._import_json(path)
            elif path.suffix.lower() == '.csv':
                terms, errors = self._import_csv(path)
            else:
                return False, [], [f"Unsupported file format: {path.suffix}"]

            # Validate imported terms
            codes = [t.term_code for t in terms]
            duplicates = [c for c in codes if codes.count(c) > 1]
            if duplicates:
                errors.append(f"Duplicate term codes in file: {set(duplicates)}")
                return False, [], errors

            return True, terms, errors

        except Exception as e:
            logger.error(f"Error importing vocabulary file: {e}")
            return False, [], [str(e)]

    def _import_json(self, path: Path) -> Tuple[List[VocabularyTerm], List[str]]:
        """Import terms from JSON file."""
        errors = []
        terms = []

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both array format and object format with "terms" key
        term_list = data if isinstance(data, list) else data.get("terms", [])

        for i, item in enumerate(term_list):
            try:
                if "term_code" not in item:
                    errors.append(f"Row {i+1}: Missing required field 'term_code'")
                    continue
                if "term_label" not in item:
                    errors.append(f"Row {i+1}: Missing required field 'term_label'")
                    continue

                terms.append(VocabularyTerm.from_dict(item))
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)}")

        return terms, errors

    def _import_csv(self, path: Path) -> Tuple[List[VocabularyTerm], List[str]]:
        """Import terms from CSV file."""
        errors = []
        terms = []

        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # Check required columns
            required = ['term_code', 'term_label']
            if reader.fieldnames:
                missing = [r for r in required if r not in reader.fieldnames]
                if missing:
                    return [], [f"Missing required columns: {missing}"]

            for i, row in enumerate(reader, start=2):
                try:
                    if not row.get('term_code'):
                        errors.append(f"Row {i}: Missing term_code")
                        continue
                    if not row.get('term_label'):
                        errors.append(f"Row {i}: Missing term_label")
                        continue

                    terms.append(VocabularyTerm(
                        term_code=row['term_code'].strip(),
                        term_label=row['term_label'].strip(),
                        term_label_ar=row.get('term_label_ar', '').strip(),
                        term_label_local=row.get('term_label_local', '').strip(),
                        description=row.get('description', '').strip(),
                        description_ar=row.get('description_ar', '').strip(),
                        status=TermStatus(row.get('status', 'active').strip().lower()),
                        sort_order=int(row.get('sort_order', 0) or 0),
                        parent_code=row.get('parent_code', '').strip() or None
                    ))
                except Exception as e:
                    errors.append(f"Row {i}: {str(e)}")

        return terms, errors

    def export_vocabulary(
        self,
        vocabulary_name: str,
        version: Optional[str] = None,
        format: str = "json"
    ) -> Tuple[str, str]:
        """
        Export vocabulary to file content.

        Args:
            vocabulary_name: Name of vocabulary to export
            version: Specific version or None for active
            format: 'json' or 'csv'

        Returns:
            Tuple of (content, filename)
        """
        if version:
            versions = self.get_vocabulary_versions(vocabulary_name)
            vocab = next((v for v in versions if v.version == version), None)
        else:
            vocab = self.get_active_version(vocabulary_name)

        if not vocab:
            raise ValueError(f"Vocabulary version not found")

        filename = f"{vocabulary_name}_v{vocab.version}"

        if format == "json":
            content = json.dumps(vocab.to_dict(), indent=2, ensure_ascii=False)
            return content, f"{filename}.json"
        elif format == "csv":
            return self._export_csv(vocab), f"{filename}.csv"
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_csv(self, vocab: VocabularyVersion) -> str:
        """Export vocabulary to CSV format."""
        import io
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'term_code', 'term_label', 'term_label_ar', 'term_label_local',
            'description', 'description_ar', 'status', 'sort_order', 'parent_code'
        ])

        # Data
        for term in sorted(vocab.terms, key=lambda t: t.sort_order):
            writer.writerow([
                term.term_code, term.term_label, term.term_label_ar,
                term.term_label_local, term.description, term.description_ar,
                term.status.value, term.sort_order, term.parent_code or ''
            ])

        return output.getvalue()

    def generate_mobile_sync_export(self) -> Dict[str, Any]:
        """
        Generate vocabulary export package for mobile/tablet sync.

        Returns a dictionary with all active vocabularies ready for mobile consumption.
        """
        export = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "vocabularies": {}
        }

        vocabularies = self.get_vocabulary_list()

        for vocab_info in vocabularies:
            vocab = self.get_active_version(vocab_info["vocabulary_name"])
            if vocab:
                export["vocabularies"][vocab.vocabulary_name] = {
                    "version": vocab.version,
                    "checksum": vocab.checksum,
                    "effective_from": vocab.effective_from.isoformat() if vocab.effective_from else None,
                    "terms": [
                        {
                            "code": t.term_code,
                            "label": t.term_label,
                            "label_ar": t.term_label_ar,
                            "status": t.status.value,
                            "parent": t.parent_code
                        }
                        for t in vocab.terms
                        if t.status == TermStatus.ACTIVE
                    ]
                }

        # Add overall checksum
        export["checksum"] = hashlib.sha256(
            json.dumps(export["vocabularies"], sort_keys=True).encode()
        ).hexdigest()[:16]

        return export

    def check_term_usage(
        self,
        vocabulary_name: str,
        term_code: str
    ) -> List[Dict[str, Any]]:
        """
        Check if a term is currently in use in the database.

        This prevents deletion of terms that are referenced by records.
        """
        usage = []

        # Define mappings of vocabularies to tables/columns
        usage_mappings = {
            "building_type": [("buildings", "building_type")],
            "ownership_type": [("ownership_records", "ownership_type")],
            "case_type": [("cases", "case_type")],
            "claim_status": [("claims", "status")],
            "document_type": [("documents", "document_type")],
            "building_condition": [("buildings", "condition")],
            "verification_status": [("documents", "verification_status")]
        }

        mappings = usage_mappings.get(vocabulary_name, [])

        for table, column in mappings:
            try:
                result = self._adapter.fetch_one(f"""
                    SELECT COUNT(*) as count FROM {table} WHERE {column} = ?
                """, (term_code,))

                if result and result["count"] > 0:
                    usage.append({
                        "table": table,
                        "column": column,
                        "count": result["count"]
                    })
            except Exception:
                # Table doesn't exist, skip
                pass

        return usage

    def deprecate_term(
        self,
        vocabulary_name: str,
        version: str,
        term_code: str,
        deprecated_by: str,
        reason: str = ""
    ) -> bool:
        """
        Mark a term as deprecated (instead of deleting).

        Deprecated terms remain visible but are hidden from new data entry.
        """
        # Get version ID
        row = self._adapter.fetch_one("""
            SELECT id FROM vocabulary_versions
            WHERE vocabulary_name = ? AND version = ?
        """, (vocabulary_name, version))

        if not row:
            raise ValueError(f"Version not found: {vocabulary_name} v{version}")

        version_id = row["id"]

        with self._adapter.cursor() as cursor:
            # Update term status
            cursor.execute("""
                UPDATE vocabulary_terms
                SET status = 'deprecated',
                    metadata = json_set(COALESCE(metadata, '{}'),
                        '$.deprecated_at', ?,
                        '$.deprecated_by', ?,
                        '$.deprecation_reason', ?)
                WHERE version_id = ? AND term_code = ?
            """, (
                datetime.utcnow().isoformat(),
                deprecated_by,
                reason,
                version_id,
                term_code
            ))

            if cursor.rowcount == 0:
                raise ValueError(f"Term not found: {term_code}")

            # Log the change
            self._log_change(
                cursor, vocabulary_name, version, version,
                "term_deprecated",
                {"term_code": term_code, "reason": reason},
                deprecated_by
            )

            logger.info(f"Deprecated term {term_code} in {vocabulary_name} v{version}")

        return True

    def get_change_log(
        self,
        vocabulary_name: Optional[str] = None,
        limit: int = 100
    ) -> List[VocabularyChangeLog]:
        """Get vocabulary change history."""
        if vocabulary_name:
            rows = self._adapter.fetch_all("""
                SELECT * FROM vocabulary_change_log
                WHERE vocabulary_name = ?
                ORDER BY changed_at DESC
                LIMIT ?
            """, (vocabulary_name, limit))
        else:
            rows = self._adapter.fetch_all("""
                SELECT * FROM vocabulary_change_log
                ORDER BY changed_at DESC
                LIMIT ?
            """, (limit,))

        logs = []
        for row in rows:
            logs.append(VocabularyChangeLog(
                id=row["id"],
                vocabulary_name=row["vocabulary_name"],
                version_from=row["version_from"],
                version_to=row["version_to"],
                change_type=row["change_type"],
                change_details=json.loads(row["change_details"]) if row["change_details"] else {},
                changed_by=row["changed_by"],
                changed_at=datetime.fromisoformat(row["changed_at"]) if row["changed_at"] else datetime.utcnow()
            ))

        return logs

    def _log_change(
        self,
        cursor: Any,
        vocabulary_name: str,
        version_from: Optional[str],
        version_to: str,
        change_type: str,
        details: Dict[str, Any],
        changed_by: str
    ):
        """Log a vocabulary change to the audit trail."""
        cursor.execute("""
            INSERT INTO vocabulary_change_log (
                vocabulary_name, version_from, version_to,
                change_type, change_details, changed_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            vocabulary_name, version_from, version_to,
            change_type, json.dumps(details), changed_by
        ))

    def rollback_to_version(
        self,
        vocabulary_name: str,
        target_version: str,
        rolled_back_by: str
    ) -> bool:
        """
        Rollback vocabulary to a previous version.

        This deactivates the current version and reactivates the target version.
        """
        with self._adapter.cursor() as cursor:
            # Get current active version
            cursor.execute("""
                SELECT version FROM vocabulary_versions
                WHERE vocabulary_name = ? AND is_active = 1
            """, (vocabulary_name,))

            current = cursor.fetchone()
            if not current:
                raise ValueError(f"No active version found for {vocabulary_name}")

            current_version = current["version"]

            # Verify target version exists
            cursor.execute("""
                SELECT id FROM vocabulary_versions
                WHERE vocabulary_name = ? AND version = ?
            """, (vocabulary_name, target_version))

            if not cursor.fetchone():
                raise ValueError(f"Target version not found: {target_version}")

            # Deactivate current
            cursor.execute("""
                UPDATE vocabulary_versions
                SET is_active = 0
                WHERE vocabulary_name = ? AND is_active = 1
            """, (vocabulary_name,))

            # Activate target
            cursor.execute("""
                UPDATE vocabulary_versions
                SET is_active = 1, is_superseded = 0,
                    activated_at = ?, activated_by = ?
                WHERE vocabulary_name = ? AND version = ?
            """, (
                datetime.utcnow().isoformat(),
                rolled_back_by,
                vocabulary_name,
                target_version
            ))

            # Log the rollback
            self._log_change(
                cursor, vocabulary_name, current_version, target_version,
                "version_rollback",
                {"from_version": current_version, "to_version": target_version},
                rolled_back_by
            )

            logger.info(f"Rolled back {vocabulary_name} from v{current_version} to v{target_version}")

        return True

    def compare_versions(
        self,
        vocabulary_name: str,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two vocabulary versions.

        Returns differences in terms (added, removed, modified).
        """
        versions = self.get_vocabulary_versions(vocabulary_name)

        v1 = next((v for v in versions if v.version == version1), None)
        v2 = next((v for v in versions if v.version == version2), None)

        if not v1:
            raise ValueError(f"Version {version1} not found")
        if not v2:
            raise ValueError(f"Version {version2} not found")

        v1_codes = {t.term_code: t for t in v1.terms}
        v2_codes = {t.term_code: t for t in v2.terms}

        added = []
        removed = []
        modified = []

        # Find added and modified
        for code, term in v2_codes.items():
            if code not in v1_codes:
                added.append(term.to_dict())
            else:
                # Check for modifications
                old_term = v1_codes[code]
                if term.to_dict() != old_term.to_dict():
                    modified.append({
                        "term_code": code,
                        "old": old_term.to_dict(),
                        "new": term.to_dict()
                    })

        # Find removed
        for code in v1_codes:
            if code not in v2_codes:
                removed.append(v1_codes[code].to_dict())

        return {
            "vocabulary_name": vocabulary_name,
            "version1": version1,
            "version2": version2,
            "added": added,
            "removed": removed,
            "modified": modified,
            "summary": {
                "added_count": len(added),
                "removed_count": len(removed),
                "modified_count": len(modified)
            }
        }
