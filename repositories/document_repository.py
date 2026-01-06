# -*- coding: utf-8 -*-
"""
Document repository for database operations.
Implements UC-006 document management requirements.
"""

from typing import List, Optional
from datetime import datetime, date
import uuid
import os
import hashlib
import shutil
from pathlib import Path

from models.document import Document
from .database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class DocumentRepository:
    """Repository for Document CRUD operations."""

    def __init__(self, db: Database):
        self.db = db
        # Attachments folder in data directory
        self.attachments_dir = Path(db.db_path).parent / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

    def create(self, document: Document) -> Document:
        """Create a new document record."""
        query = """
            INSERT INTO documents (
                document_id, document_type, document_number,
                issue_date, expiry_date,
                issuing_authority, issuing_location,
                verified, verified_by, verification_date,
                attachment_path, attachment_hash, attachment_size, mime_type,
                notes, created_at, updated_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            document.document_id, document.document_type, document.document_number,
            document.issue_date.isoformat() if document.issue_date else None,
            document.expiry_date.isoformat() if document.expiry_date else None,
            document.issuing_authority, document.issuing_location,
            1 if document.verified else 0, document.verified_by,
            document.verification_date.isoformat() if document.verification_date else None,
            document.attachment_path, document.attachment_hash,
            document.attachment_size, document.mime_type,
            document.notes,
            document.created_at.isoformat() if document.created_at else None,
            document.updated_at.isoformat() if document.updated_at else None,
            document.created_by, document.updated_by
        )
        self.db.execute(query, params)
        logger.debug(f"Created document: {document.document_id}")
        return document

    def get_by_id(self, document_id: str) -> Optional[Document]:
        """Get document by ID."""
        query = "SELECT * FROM documents WHERE document_id = ?"
        row = self.db.fetch_one(query, (document_id,))
        if row:
            return self._row_to_document(row)
        return None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[Document]:
        """Get all documents with pagination."""
        query = "SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = self.db.fetch_all(query, (limit, offset))
        return [self._row_to_document(row) for row in rows]

    def get_by_claim(self, claim_uuid: str) -> List[Document]:
        """Get all active documents for a claim."""
        query = """
            SELECT d.* FROM documents d
            JOIN claim_documents cd ON d.document_id = cd.document_id
            WHERE cd.claim_uuid = ? AND cd.is_active = 1
            ORDER BY d.created_at DESC
        """
        rows = self.db.fetch_all(query, (claim_uuid,))
        return [self._row_to_document(row) for row in rows]

    def update(self, document: Document) -> Document:
        """Update an existing document."""
        document.updated_at = datetime.now()
        query = """
            UPDATE documents SET
                document_type = ?, document_number = ?,
                issue_date = ?, expiry_date = ?,
                issuing_authority = ?, issuing_location = ?,
                verified = ?, verified_by = ?, verification_date = ?,
                attachment_path = ?, attachment_hash = ?,
                attachment_size = ?, mime_type = ?,
                notes = ?, updated_at = ?, updated_by = ?
            WHERE document_id = ?
        """
        params = (
            document.document_type, document.document_number,
            document.issue_date.isoformat() if document.issue_date else None,
            document.expiry_date.isoformat() if document.expiry_date else None,
            document.issuing_authority, document.issuing_location,
            1 if document.verified else 0, document.verified_by,
            document.verification_date.isoformat() if document.verification_date else None,
            document.attachment_path, document.attachment_hash,
            document.attachment_size, document.mime_type,
            document.notes, document.updated_at.isoformat(), document.updated_by,
            document.document_id
        )
        self.db.execute(query, params)
        logger.debug(f"Updated document: {document.document_id}")
        return document

    def delete(self, document_id: str) -> bool:
        """Delete a document by ID."""
        query = "DELETE FROM documents WHERE document_id = ?"
        cursor = self.db.execute(query, (document_id,))
        return cursor.rowcount > 0

    def link_to_claim(self, claim_uuid: str, document_id: str, user_id: str = None) -> bool:
        """Link a document to a claim."""
        query = """
            INSERT INTO claim_documents (claim_uuid, document_id, added_at, added_by, is_active)
            VALUES (?, ?, ?, ?, 1)
        """
        try:
            self.db.execute(query, (claim_uuid, document_id, datetime.now().isoformat(), user_id))
            logger.debug(f"Linked document {document_id} to claim {claim_uuid}")
            return True
        except Exception as e:
            logger.error(f"Failed to link document: {e}")
            return False

    def unlink_from_claim(self, claim_uuid: str, document_id: str, user_id: str = None) -> bool:
        """Unlink (soft delete) a document from a claim."""
        query = """
            UPDATE claim_documents
            SET is_active = 0, removed_at = ?, removed_by = ?
            WHERE claim_uuid = ? AND document_id = ?
        """
        try:
            self.db.execute(query, (datetime.now().isoformat(), user_id, claim_uuid, document_id))
            logger.debug(f"Unlinked document {document_id} from claim {claim_uuid}")
            return True
        except Exception as e:
            logger.error(f"Failed to unlink document: {e}")
            return False

    def store_attachment(self, source_path: str, document: Document) -> str:
        """
        Store attachment file with SHA-256 deduplication.
        Returns the relative path to the stored file.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Calculate SHA-256 hash
        sha256_hash = hashlib.sha256()
        with open(source, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        file_hash = sha256_hash.hexdigest()

        # Create subdirectory structure based on hash (first 4 chars)
        subdir = self.attachments_dir / file_hash[:2] / file_hash[2:4]
        subdir.mkdir(parents=True, exist_ok=True)

        # Target filename with extension
        ext = source.suffix.lower()
        target_name = f"{file_hash}{ext}"
        target_path = subdir / target_name

        # Copy file if not already exists (deduplication)
        if not target_path.exists():
            shutil.copy2(source, target_path)
            logger.debug(f"Stored new attachment: {target_path}")
        else:
            logger.debug(f"Attachment already exists (deduplicated): {file_hash}")

        # Update document with attachment info
        document.attachment_hash = file_hash
        document.attachment_path = str(target_path.relative_to(self.attachments_dir.parent))
        document.attachment_size = source.stat().st_size

        # Detect MIME type from extension
        mime_types = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        document.mime_type = mime_types.get(ext, "application/octet-stream")

        return document.attachment_path

    def _row_to_document(self, row) -> Document:
        """Convert database row to Document object."""
        data = dict(row)

        # Handle boolean fields
        data["verified"] = bool(data.get("verified", 0))

        # Handle date fields
        for field in ["issue_date", "expiry_date", "verification_date"]:
            if data.get(field):
                data[field] = date.fromisoformat(data[field])

        for field in ["created_at", "updated_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        return Document(**{k: v for k, v in data.items() if k in Document.__dataclass_fields__})
