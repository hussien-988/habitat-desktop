"""
Document Version Management Service
====================================
Implements comprehensive document versioning and management as per FSD requirements.

Features:
- Version control for documents with full history
- Hash-based integrity verification (SHA-256)
- Verification status tracking
- Document type classification
- Multi-format support (PDF, images, scanned documents)
- Metadata management
- Audit trail for all document operations
- Document relationship linking (to buildings, claims, persons)
- Duplicate detection via hash
"""

import json
import hashlib
import shutil
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, BinaryIO
import logging
import uuid

from repositories.db_adapter import DatabaseFactory, DatabaseAdapter, RowProxy, DatabaseType

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Types of documents in the system."""
    ID_CARD = "id_card"
    PASSPORT = "passport"
    DEED = "deed"
    CONTRACT = "contract"
    PHOTO = "photo"
    SITE_PHOTO = "site_photo"
    BUILDING_PHOTO = "building_photo"
    CLAIM_FORM = "claim_form"
    SURVEY_FORM = "survey_form"
    OFFICIAL_LETTER = "official_letter"
    COURT_DOCUMENT = "court_document"
    MAP = "map"
    OTHER = "other"


class VerificationStatus(Enum):
    """Document verification status."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"
    EXPIRED = "expired"


class DocumentStatus(Enum):
    """Document lifecycle status."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    SUPERSEDED = "superseded"  # Replaced by newer version


class EntityType(Enum):
    """Entity types that documents can be linked to."""
    BUILDING = "building"
    CLAIM = "claim"
    PERSON = "person"
    CASE = "case"
    OWNERSHIP = "ownership"


@dataclass
class DocumentMetadata:
    """Metadata for a document."""
    title: str = ""
    title_ar: str = ""
    description: str = ""
    description_ar: str = ""
    document_number: str = ""  # Official document number
    issue_date: Optional[str] = None  # Date document was issued
    expiry_date: Optional[str] = None  # Date document expires
    issuing_authority: str = ""
    issuing_authority_ar: str = ""
    language: str = "ar"  # Primary language of document
    page_count: int = 1
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentMetadata':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DocumentVersion:
    """Represents a single version of a document."""
    version_id: str
    document_id: str
    version_number: int
    file_path: str  # Relative path in storage
    file_name: str
    file_size: int
    mime_type: str
    file_hash: str  # SHA-256 hash
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    change_notes: str = ""  # Description of changes in this version
    is_current: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "file_hash": self.file_hash,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "change_notes": self.change_notes,
            "is_current": self.is_current
        }


@dataclass
class Document:
    """Represents a document with version history."""
    document_id: str
    document_type: DocumentType
    status: DocumentStatus = DocumentStatus.ACTIVE
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verified_by: str = ""
    verified_at: Optional[datetime] = None
    verification_notes: str = ""
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    current_version: int = 1
    versions: List[DocumentVersion] = field(default_factory=list)
    linked_entities: List[Dict[str, str]] = field(default_factory=list)  # [{entity_type, entity_id}]
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    modified_at: Optional[datetime] = None
    modified_by: str = ""

    def to_dict(self, include_versions: bool = True) -> Dict[str, Any]:
        result = {
            "document_id": self.document_id,
            "document_type": self.document_type.value,
            "status": self.status.value,
            "verification_status": self.verification_status.value,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verification_notes": self.verification_notes,
            "metadata": self.metadata.to_dict(),
            "current_version": self.current_version,
            "linked_entities": self.linked_entities,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "modified_by": self.modified_by
        }
        if include_versions:
            result["versions"] = [v.to_dict() for v in self.versions]
        return result


@dataclass
class DocumentAuditEntry:
    """Audit log entry for document operations."""
    id: int = 0
    document_id: str = ""
    action: str = ""  # created, version_added, verified, status_changed, etc.
    details: Dict[str, Any] = field(default_factory=dict)
    performed_by: str = ""
    performed_at: datetime = field(default_factory=datetime.utcnow)


class DocumentVersionService:
    """
    Comprehensive document version management service.

    Implements FSD requirements for document management:
    - Version control with full history
    - Hash-based integrity verification
    - Verification workflow
    - Entity linking
    - Audit trail
    """

    # Supported MIME types
    SUPPORTED_MIME_TYPES = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx"
    }

    # Max file size (50 MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    def __init__(self, db_path: str = None, storage_path: str = None):
        """
        Initialize document version service.

        Args:
            db_path: Path to SQLite database (optional, uses adapter)
            storage_path: Base path for document storage
        """
        self.db_path = db_path
        self._adapter: DatabaseAdapter = DatabaseFactory.create()

        # Set up storage path
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default storage path
            self.storage_path = Path("./document_storage")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure document tables exist."""
        with self._adapter.cursor() as cursor:
            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    document_type TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    verification_status TEXT DEFAULT 'pending',
                    verified_by TEXT,
                    verified_at TIMESTAMP,
                    verification_notes TEXT,
                    metadata TEXT,
                    current_version INTEGER DEFAULT 1,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    modified_at TIMESTAMP,
                    modified_by TEXT
                )
            """)

            # Document versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_versions (
                    version_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    change_notes TEXT,
                    is_current INTEGER DEFAULT 1,
                    FOREIGN KEY (document_id) REFERENCES documents(document_id),
                    UNIQUE(document_id, version_number)
                )
            """)

            # Document-entity links table
            if self._adapter.db_type == DatabaseType.POSTGRESQL:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_entity_links (
                        id SERIAL PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        linked_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES documents(document_id),
                        UNIQUE(document_id, entity_type, entity_id)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_entity_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT NOT NULL,
                        entity_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        linked_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES documents(document_id),
                        UNIQUE(document_id, entity_type, entity_id)
                    )
                """)

            # Document audit log
            if self._adapter.db_type == DatabaseType.POSTGRESQL:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_audit_log (
                        id SERIAL PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        performed_by TEXT NOT NULL,
                        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents(document_id)
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS document_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        details TEXT,
                        performed_by TEXT NOT NULL,
                        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents(document_id)
                    )
                """)

            # Hash index for duplicate detection
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_versions_hash
                ON document_versions(file_hash)
            """)

            # Entity links index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_doc_entity_links
                ON document_entity_links(entity_type, entity_id)
            """)

            # Document type index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_type
                ON documents(document_type, status)
            """)

            logger.info("Document versioning tables initialized")

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _compute_stream_hash(self, file_stream: BinaryIO) -> str:
        """Compute SHA-256 hash from a file stream."""
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: file_stream.read(8192), b''):
            sha256.update(chunk)
        file_stream.seek(0)  # Reset stream position
        return sha256.hexdigest()

    def _get_storage_path(self, document_id: str, version: int, file_ext: str) -> Path:
        """Generate storage path for a document version."""
        # Use hierarchical structure to avoid too many files in one directory
        prefix = document_id[:2]
        subdir = self.storage_path / prefix / document_id
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir / f"v{version}{file_ext}"

    def _detect_mime_type(self, file_path: Path) -> str:
        """Detect MIME type from file extension."""
        ext = file_path.suffix.lower()
        mime_map = {v: k for k, v in self.SUPPORTED_MIME_TYPES.items()}
        return mime_map.get(ext, "application/octet-stream")

    # ==================== Document Operations ====================

    def create_document(
        self,
        file_path: str,
        document_type: DocumentType,
        created_by: str,
        metadata: Optional[DocumentMetadata] = None,
        linked_entities: Optional[List[Dict[str, str]]] = None,
        tags: Optional[List[str]] = None
    ) -> Document:
        """
        Create a new document from a file.

        Args:
            file_path: Path to the source file
            document_type: Type of document
            created_by: User creating the document
            metadata: Document metadata
            linked_entities: List of {entity_type, entity_id} to link
            tags: List of tags

        Returns:
            Created Document object
        """
        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = source_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum ({self.MAX_FILE_SIZE / 1024 / 1024} MB)")

        mime_type = self._detect_mime_type(source_path)
        if mime_type not in self.SUPPORTED_MIME_TYPES and mime_type != "application/octet-stream":
            logger.warning(f"Unsupported MIME type: {mime_type}")

        # Compute hash
        file_hash = self._compute_file_hash(source_path)

        # Check for duplicates
        duplicate = self.find_by_hash(file_hash)
        if duplicate:
            logger.warning(f"Duplicate file detected: {duplicate.document_id}")

        # Generate IDs
        document_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        # Get file extension
        file_ext = source_path.suffix or self.SUPPORTED_MIME_TYPES.get(mime_type, "")

        # Copy file to storage
        storage_path = self._get_storage_path(document_id, 1, file_ext)
        shutil.copy2(source_path, storage_path)

        # Create document version
        version = DocumentVersion(
            version_id=version_id,
            document_id=document_id,
            version_number=1,
            file_path=str(storage_path.relative_to(self.storage_path)),
            file_name=source_path.name,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            created_by=created_by,
            is_current=True
        )

        # Create document
        document = Document(
            document_id=document_id,
            document_type=document_type,
            metadata=metadata or DocumentMetadata(),
            current_version=1,
            versions=[version],
            linked_entities=linked_entities or [],
            tags=tags or [],
            created_by=created_by
        )

        # Save to database
        try:
            with self._adapter.cursor() as cursor:
                # Insert document
                cursor.execute("""
                    INSERT INTO documents (
                        document_id, document_type, status, verification_status,
                        metadata, current_version, tags, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    document_type.value,
                    DocumentStatus.ACTIVE.value,
                    VerificationStatus.PENDING.value,
                    json.dumps(document.metadata.to_dict()),
                    1,
                    json.dumps(tags or []),
                    created_by
                ))

                # Insert version
                cursor.execute("""
                    INSERT INTO document_versions (
                        version_id, document_id, version_number, file_path,
                        file_name, file_size, mime_type, file_hash, created_by, is_current
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    version_id, document_id, 1, version.file_path,
                    version.file_name, file_size, mime_type, file_hash, created_by
                ))

                # Insert entity links
                for link in (linked_entities or []):
                    cursor.execute("""
                        INSERT INTO document_entity_links (
                            document_id, entity_type, entity_id, linked_by
                        ) VALUES (?, ?, ?, ?)
                    """, (document_id, link["entity_type"], link["entity_id"], created_by))

                # Audit log
                self._log_action(
                    cursor, document_id, "created",
                    {"document_type": document_type.value, "file_name": source_path.name},
                    created_by
                )

                logger.info(f"Created document: {document_id}")

            return document

        except Exception as e:
            # Clean up stored file on error
            if storage_path.exists():
                storage_path.unlink()
            raise e

    def add_version(
        self,
        document_id: str,
        file_path: str,
        created_by: str,
        change_notes: str = ""
    ) -> DocumentVersion:
        """
        Add a new version to an existing document.

        Args:
            document_id: ID of the document to update
            file_path: Path to the new file
            created_by: User adding the version
            change_notes: Description of changes

        Returns:
            Created DocumentVersion object
        """
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        if document.status != DocumentStatus.ACTIVE:
            raise ValueError(f"Cannot add version to {document.status.value} document")

        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = source_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum")

        mime_type = self._detect_mime_type(source_path)
        file_hash = self._compute_file_hash(source_path)

        # Check if file is same as current version
        current = self.get_current_version(document_id)
        if current and current.file_hash == file_hash:
            raise ValueError("New file is identical to current version")

        # Generate new version
        new_version_number = document.current_version + 1
        version_id = str(uuid.uuid4())

        file_ext = source_path.suffix or self.SUPPORTED_MIME_TYPES.get(mime_type, "")
        storage_path = self._get_storage_path(document_id, new_version_number, file_ext)
        shutil.copy2(source_path, storage_path)

        version = DocumentVersion(
            version_id=version_id,
            document_id=document_id,
            version_number=new_version_number,
            file_path=str(storage_path.relative_to(self.storage_path)),
            file_name=source_path.name,
            file_size=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            created_by=created_by,
            change_notes=change_notes,
            is_current=True
        )

        try:
            with self._adapter.cursor() as cursor:
                # Mark previous version as not current
                cursor.execute("""
                    UPDATE document_versions SET is_current = 0
                    WHERE document_id = ? AND is_current = 1
                """, (document_id,))

                # Insert new version
                cursor.execute("""
                    INSERT INTO document_versions (
                        version_id, document_id, version_number, file_path,
                        file_name, file_size, mime_type, file_hash,
                        created_by, change_notes, is_current
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    version_id, document_id, new_version_number, version.file_path,
                    version.file_name, file_size, mime_type, file_hash,
                    created_by, change_notes
                ))

                # Update document
                cursor.execute("""
                    UPDATE documents SET
                        current_version = ?,
                        modified_at = ?,
                        modified_by = ?
                    WHERE document_id = ?
                """, (new_version_number, datetime.utcnow().isoformat(), created_by, document_id))

                # Audit log
                self._log_action(
                    cursor, document_id, "version_added",
                    {
                        "version_number": new_version_number,
                        "file_name": source_path.name,
                        "change_notes": change_notes
                    },
                    created_by
                )

                logger.info(f"Added version {new_version_number} to document {document_id}")

            return version

        except Exception as e:
            if storage_path.exists():
                storage_path.unlink()
            raise e

    def get_document(self, document_id: str, include_versions: bool = True) -> Optional[Document]:
        """Get document by ID."""
        row = self._adapter.fetch_one("SELECT * FROM documents WHERE document_id = ?", (document_id,))
        if not row:
            return None

        # Get versions if requested
        versions = []
        if include_versions:
            version_rows = self._adapter.fetch_all("""
                SELECT * FROM document_versions
                WHERE document_id = ?
                ORDER BY version_number DESC
            """, (document_id,))

            for v_row in version_rows:
                versions.append(DocumentVersion(
                    version_id=v_row["version_id"],
                    document_id=v_row["document_id"],
                    version_number=v_row["version_number"],
                    file_path=v_row["file_path"],
                    file_name=v_row["file_name"],
                    file_size=v_row["file_size"],
                    mime_type=v_row["mime_type"],
                    file_hash=v_row["file_hash"],
                    created_at=datetime.fromisoformat(v_row["created_at"]) if v_row["created_at"] else datetime.utcnow(),
                    created_by=v_row["created_by"] or "",
                    change_notes=v_row["change_notes"] or "",
                    is_current=bool(v_row["is_current"])
                ))

        # Get linked entities
        link_rows = self._adapter.fetch_all("""
            SELECT entity_type, entity_id FROM document_entity_links
            WHERE document_id = ?
        """, (document_id,))
        linked_entities = [
            {"entity_type": r["entity_type"], "entity_id": r["entity_id"]}
            for r in link_rows
        ]

        return Document(
            document_id=row["document_id"],
            document_type=DocumentType(row["document_type"]),
            status=DocumentStatus(row["status"]) if row["status"] else DocumentStatus.ACTIVE,
            verification_status=VerificationStatus(row["verification_status"]) if row["verification_status"] else VerificationStatus.PENDING,
            verified_by=row["verified_by"] or "",
            verified_at=datetime.fromisoformat(row["verified_at"]) if row["verified_at"] else None,
            verification_notes=row["verification_notes"] or "",
            metadata=DocumentMetadata.from_dict(json.loads(row["metadata"])) if row["metadata"] else DocumentMetadata(),
            current_version=row["current_version"],
            versions=versions,
            linked_entities=linked_entities,
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            created_by=row["created_by"] or "",
            modified_at=datetime.fromisoformat(row["modified_at"]) if row["modified_at"] else None,
            modified_by=row["modified_by"] or ""
        )

    def get_current_version(self, document_id: str) -> Optional[DocumentVersion]:
        """Get current version of a document."""
        row = self._adapter.fetch_one("""
            SELECT * FROM document_versions
            WHERE document_id = ? AND is_current = 1
        """, (document_id,))

        if not row:
            return None

        return DocumentVersion(
            version_id=row["version_id"],
            document_id=row["document_id"],
            version_number=row["version_number"],
            file_path=row["file_path"],
            file_name=row["file_name"],
            file_size=row["file_size"],
            mime_type=row["mime_type"],
            file_hash=row["file_hash"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            created_by=row["created_by"] or "",
            change_notes=row["change_notes"] or "",
            is_current=True
        )

    def get_version(self, document_id: str, version_number: int) -> Optional[DocumentVersion]:
        """Get specific version of a document."""
        row = self._adapter.fetch_one("""
            SELECT * FROM document_versions
            WHERE document_id = ? AND version_number = ?
        """, (document_id, version_number))

        if not row:
            return None

        return DocumentVersion(
            version_id=row["version_id"],
            document_id=row["document_id"],
            version_number=row["version_number"],
            file_path=row["file_path"],
            file_name=row["file_name"],
            file_size=row["file_size"],
            mime_type=row["mime_type"],
            file_hash=row["file_hash"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            created_by=row["created_by"] or "",
            change_notes=row["change_notes"] or "",
            is_current=bool(row["is_current"])
        )

    def get_file_path(self, document_id: str, version_number: Optional[int] = None) -> Optional[Path]:
        """Get full file path for a document version."""
        if version_number:
            version = self.get_version(document_id, version_number)
        else:
            version = self.get_current_version(document_id)

        if not version:
            return None

        return self.storage_path / version.file_path

    def list_documents(
        self,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        verification_status: Optional[VerificationStatus] = None,
        entity_type: Optional[EntityType] = None,
        entity_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """List documents with filters."""
        query = "SELECT DISTINCT d.* FROM documents d"
        params = []
        conditions = []

        if entity_type or entity_id:
            query += " JOIN document_entity_links del ON d.document_id = del.document_id"
            if entity_type:
                conditions.append("del.entity_type = ?")
                params.append(entity_type.value)
            if entity_id:
                conditions.append("del.entity_id = ?")
                params.append(entity_id)

        if document_type:
            conditions.append("d.document_type = ?")
            params.append(document_type.value)

        if status:
            conditions.append("d.status = ?")
            params.append(status.value)

        if verification_status:
            conditions.append("d.verification_status = ?")
            params.append(verification_status.value)

        if tags:
            for tag in tags:
                conditions.append("d.tags LIKE ?")
                params.append(f'%"{tag}"%')

        if search:
            conditions.append("(d.metadata LIKE ? OR d.document_id LIKE ?)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY d.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._adapter.fetch_all(query, tuple(params))

        documents = []
        for row in rows:
            doc = self.get_document(row["document_id"], include_versions=False)
            if doc:
                documents.append(doc)

        return documents

    def get_documents_for_entity(
        self,
        entity_type: EntityType,
        entity_id: str
    ) -> List[Document]:
        """Get all documents linked to an entity."""
        return self.list_documents(entity_type=entity_type, entity_id=entity_id)

    # ==================== Verification Operations ====================

    def verify_document(
        self,
        document_id: str,
        verified_by: str,
        status: VerificationStatus,
        notes: str = ""
    ) -> Document:
        """Update document verification status."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE documents SET
                    verification_status = ?,
                    verified_by = ?,
                    verified_at = ?,
                    verification_notes = ?,
                    modified_at = ?,
                    modified_by = ?
                WHERE document_id = ?
            """, (
                status.value,
                verified_by,
                datetime.utcnow().isoformat(),
                notes,
                datetime.utcnow().isoformat(),
                verified_by,
                document_id
            ))

            self._log_action(
                cursor, document_id, "verification_status_changed",
                {
                    "old_status": document.verification_status.value,
                    "new_status": status.value,
                    "notes": notes
                },
                verified_by
            )

        return self.get_document(document_id)

    def verify_file_integrity(self, document_id: str, version_number: Optional[int] = None) -> Tuple[bool, str]:
        """
        Verify file integrity by comparing stored hash with computed hash.

        Returns:
            Tuple of (is_valid, message)
        """
        if version_number:
            version = self.get_version(document_id, version_number)
        else:
            version = self.get_current_version(document_id)

        if not version:
            return False, "Version not found"

        file_path = self.storage_path / version.file_path
        if not file_path.exists():
            return False, "File not found in storage"

        computed_hash = self._compute_file_hash(file_path)
        if computed_hash != version.file_hash:
            return False, f"Hash mismatch: expected {version.file_hash}, got {computed_hash}"

        return True, "File integrity verified"

    # ==================== Entity Linking ====================

    def link_to_entity(
        self,
        document_id: str,
        entity_type: EntityType,
        entity_id: str,
        linked_by: str
    ) -> bool:
        """Link document to an entity."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                INSERT OR IGNORE INTO document_entity_links
                (document_id, entity_type, entity_id, linked_by)
                VALUES (?, ?, ?, ?)
            """, (document_id, entity_type.value, entity_id, linked_by))

            if cursor.rowcount > 0:
                self._log_action(
                    cursor, document_id, "entity_linked",
                    {"entity_type": entity_type.value, "entity_id": entity_id},
                    linked_by
                )

        return True

    def unlink_from_entity(
        self,
        document_id: str,
        entity_type: EntityType,
        entity_id: str,
        unlinked_by: str
    ) -> bool:
        """Unlink document from an entity."""
        with self._adapter.cursor() as cursor:
            cursor.execute("""
                DELETE FROM document_entity_links
                WHERE document_id = ? AND entity_type = ? AND entity_id = ?
            """, (document_id, entity_type.value, entity_id))

            if cursor.rowcount > 0:
                self._log_action(
                    cursor, document_id, "entity_unlinked",
                    {"entity_type": entity_type.value, "entity_id": entity_id},
                    unlinked_by
                )

        return True

    # ==================== Status Operations ====================

    def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        updated_by: str
    ) -> Document:
        """Update document status."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE documents SET
                    status = ?,
                    modified_at = ?,
                    modified_by = ?
                WHERE document_id = ?
            """, (status.value, datetime.utcnow().isoformat(), updated_by, document_id))

            self._log_action(
                cursor, document_id, "status_changed",
                {"old_status": document.status.value, "new_status": status.value},
                updated_by
            )

        return self.get_document(document_id)

    def archive_document(self, document_id: str, archived_by: str) -> Document:
        """Archive a document."""
        return self.update_status(document_id, DocumentStatus.ARCHIVED, archived_by)

    def delete_document(self, document_id: str, deleted_by: str, hard_delete: bool = False) -> bool:
        """
        Delete a document.

        Args:
            document_id: Document to delete
            deleted_by: User deleting the document
            hard_delete: If True, physically remove files; otherwise soft delete
        """
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        with self._adapter.cursor() as cursor:
            if hard_delete:
                # Remove physical files
                for version in document.versions:
                    file_path = self.storage_path / version.file_path
                    if file_path.exists():
                        file_path.unlink()

                # Remove from database
                cursor.execute("DELETE FROM document_entity_links WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM document_versions WHERE document_id = ?", (document_id,))
                cursor.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

                self._log_action(
                    cursor, document_id, "hard_deleted",
                    {"versions_removed": len(document.versions)},
                    deleted_by
                )
            else:
                # Soft delete
                cursor.execute("""
                    UPDATE documents SET
                        status = 'deleted',
                        modified_at = ?,
                        modified_by = ?
                    WHERE document_id = ?
                """, (datetime.utcnow().isoformat(), deleted_by, document_id))

                self._log_action(
                    cursor, document_id, "soft_deleted",
                    {},
                    deleted_by
                )

        return True

    # ==================== Metadata Operations ====================

    def update_metadata(
        self,
        document_id: str,
        metadata: DocumentMetadata,
        updated_by: str
    ) -> Document:
        """Update document metadata."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE documents SET
                    metadata = ?,
                    modified_at = ?,
                    modified_by = ?
                WHERE document_id = ?
            """, (
                json.dumps(metadata.to_dict()),
                datetime.utcnow().isoformat(),
                updated_by,
                document_id
            ))

            self._log_action(
                cursor, document_id, "metadata_updated",
                {"old": document.metadata.to_dict(), "new": metadata.to_dict()},
                updated_by
            )

        return self.get_document(document_id)

    def update_tags(
        self,
        document_id: str,
        tags: List[str],
        updated_by: str
    ) -> Document:
        """Update document tags."""
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        with self._adapter.cursor() as cursor:
            cursor.execute("""
                UPDATE documents SET
                    tags = ?,
                    modified_at = ?,
                    modified_by = ?
                WHERE document_id = ?
            """, (
                json.dumps(tags),
                datetime.utcnow().isoformat(),
                updated_by,
                document_id
            ))

            self._log_action(
                cursor, document_id, "tags_updated",
                {"old_tags": document.tags, "new_tags": tags},
                updated_by
            )

        return self.get_document(document_id)

    # ==================== Search and Lookup ====================

    def find_by_hash(self, file_hash: str) -> Optional[Document]:
        """Find document by file hash (for duplicate detection)."""
        row = self._adapter.fetch_one("""
            SELECT document_id FROM document_versions WHERE file_hash = ?
        """, (file_hash,))

        if row:
            return self.get_document(row["document_id"])
        return None

    def find_duplicates(self) -> List[Dict[str, Any]]:
        """Find all duplicate documents based on file hash."""
        rows = self._adapter.fetch_all("""
            SELECT file_hash, COUNT(*) as count, GROUP_CONCAT(document_id) as document_ids
            FROM document_versions
            WHERE is_current = 1
            GROUP BY file_hash
            HAVING count > 1
        """)

        duplicates = []
        for row in rows:
            duplicates.append({
                "file_hash": row["file_hash"],
                "count": row["count"],
                "document_ids": row["document_ids"].split(",")
            })

        return duplicates

    # ==================== Version Comparison ====================

    def compare_versions(
        self,
        document_id: str,
        version1: int,
        version2: int
    ) -> Dict[str, Any]:
        """Compare two versions of a document."""
        v1 = self.get_version(document_id, version1)
        v2 = self.get_version(document_id, version2)

        if not v1 or not v2:
            raise ValueError("One or both versions not found")

        return {
            "document_id": document_id,
            "version1": v1.to_dict(),
            "version2": v2.to_dict(),
            "differences": {
                "file_name": v1.file_name != v2.file_name,
                "file_size": v1.file_size != v2.file_size,
                "file_hash": v1.file_hash != v2.file_hash,
                "mime_type": v1.mime_type != v2.mime_type,
                "size_change": v2.file_size - v1.file_size
            }
        }

    def restore_version(
        self,
        document_id: str,
        version_number: int,
        restored_by: str
    ) -> DocumentVersion:
        """
        Restore a previous version as the current version.

        This creates a new version with the same content as the specified version.
        """
        version = self.get_version(document_id, version_number)
        if not version:
            raise ValueError(f"Version {version_number} not found")

        if version.is_current:
            raise ValueError("Version is already current")

        # Get the file path
        file_path = self.storage_path / version.file_path
        if not file_path.exists():
            raise FileNotFoundError("Version file not found in storage")

        # Add as new version
        return self.add_version(
            document_id,
            str(file_path),
            restored_by,
            f"Restored from version {version_number}"
        )

    # ==================== Audit Log ====================

    def _log_action(
        self,
        cursor: Any,
        document_id: str,
        action: str,
        details: Dict[str, Any],
        performed_by: str
    ):
        """Log a document action to audit trail."""
        cursor.execute("""
            INSERT INTO document_audit_log
            (document_id, action, details, performed_by)
            VALUES (?, ?, ?, ?)
        """, (document_id, action, json.dumps(details), performed_by))

    def get_audit_log(
        self,
        document_id: Optional[str] = None,
        action: Optional[str] = None,
        performed_by: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[DocumentAuditEntry]:
        """Get document audit log with filters."""
        query = "SELECT * FROM document_audit_log WHERE 1=1"
        params = []

        if document_id:
            query += " AND document_id = ?"
            params.append(document_id)

        if action:
            query += " AND action = ?"
            params.append(action)

        if performed_by:
            query += " AND performed_by = ?"
            params.append(performed_by)

        if from_date:
            query += " AND performed_at >= ?"
            params.append(from_date.isoformat())

        if to_date:
            query += " AND performed_at <= ?"
            params.append(to_date.isoformat())

        query += " ORDER BY performed_at DESC LIMIT ?"
        params.append(limit)

        rows = self._adapter.fetch_all(query, tuple(params))

        entries = []
        for row in rows:
            entries.append(DocumentAuditEntry(
                id=row["id"],
                document_id=row["document_id"],
                action=row["action"],
                details=json.loads(row["details"]) if row["details"] else {},
                performed_by=row["performed_by"],
                performed_at=datetime.fromisoformat(row["performed_at"]) if row["performed_at"] else datetime.utcnow()
            ))

        return entries

    # ==================== Statistics ====================

    def get_statistics(self) -> Dict[str, Any]:
        """Get document statistics."""
        stats = {}

        # Total documents
        result = self._adapter.fetch_one("SELECT COUNT(*) as count FROM documents WHERE status != 'deleted'")
        stats["total_documents"] = result["count"] if result else 0

        # By type
        type_rows = self._adapter.fetch_all("""
            SELECT document_type, COUNT(*) as count
            FROM documents WHERE status != 'deleted'
            GROUP BY document_type
        """)
        stats["by_type"] = {row["document_type"]: row["count"] for row in type_rows}

        # By verification status
        verification_rows = self._adapter.fetch_all("""
            SELECT verification_status, COUNT(*) as count
            FROM documents WHERE status != 'deleted'
            GROUP BY verification_status
        """)
        stats["by_verification_status"] = {row["verification_status"]: row["count"] for row in verification_rows}

        # Total versions
        result = self._adapter.fetch_one("SELECT COUNT(*) as count FROM document_versions")
        stats["total_versions"] = result["count"] if result else 0

        # Total storage size
        result = self._adapter.fetch_one("SELECT SUM(file_size) as total FROM document_versions WHERE is_current = 1")
        stats["total_storage_bytes"] = result["total"] or 0 if result else 0

        # Average versions per document
        result = self._adapter.fetch_one("""
            SELECT AVG(version_count) as avg FROM (
                SELECT COUNT(*) as version_count FROM document_versions
                GROUP BY document_id
            )
        """)
        stats["avg_versions_per_document"] = round(result["avg"] or 0, 2) if result else 0

        return stats
