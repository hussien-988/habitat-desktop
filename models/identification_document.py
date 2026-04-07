# -*- coding: utf-8 -*-
"""
IdentificationDocument entity model.

Represents personal identification documents (ID photo, family record, photo)
linked to a Person. Separated from Evidence entity as of API v1.7.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class IdentificationDocument:
    """
    Personal identification document linked to a Person.
    Maps to IdentificationDocumentDto from the backend API.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    person_id: str = ""
    document_type: int = 1  # 1=PersonalIdPhoto, 2=FamilyRecord, 3=Photo
    description: Optional[str] = None
    original_file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    mime_type: Optional[str] = None
    file_hash: Optional[str] = None
    document_issued_date: Optional[str] = None
    document_expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    document_reference_number: Optional[str] = None
    notes: Optional[str] = None
    is_expired: bool = False
    created_at_utc: Optional[str] = None
    last_modified_at_utc: Optional[str] = None

    @property
    def document_type_display_ar(self) -> str:
        types = {
            1: "صورة الهوية الشخصية",
            2: "إخراج قيد",
            3: "صورة",
        }
        return types.get(self.document_type, str(self.document_type))

    @property
    def file_extension(self) -> str:
        if self.original_file_name:
            parts = self.original_file_name.rsplit(".", 1)
            if len(parts) == 2:
                return parts[1].lower()
        return ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "personId": self.person_id,
            "documentType": self.document_type,
            "description": self.description,
            "originalFileName": self.original_file_name,
            "filePath": self.file_path,
            "fileSizeBytes": self.file_size_bytes,
            "mimeType": self.mime_type,
            "fileHash": self.file_hash,
            "documentIssuedDate": self.document_issued_date,
            "documentExpiryDate": self.document_expiry_date,
            "issuingAuthority": self.issuing_authority,
            "documentReferenceNumber": self.document_reference_number,
            "notes": self.notes,
            "isExpired": self.is_expired,
            "createdAtUtc": self.created_at_utc,
            "lastModifiedAtUtc": self.last_modified_at_utc,
        }

    @classmethod
    def from_api_dict(cls, data: dict) -> "IdentificationDocument":
        """Create from backend API response (camelCase keys)."""
        return cls(
            id=str(data.get("id", "")),
            person_id=str(data.get("personId", "")),
            document_type=data.get("documentType", 1),
            description=data.get("description"),
            original_file_name=data.get("originalFileName"),
            file_path=data.get("filePath"),
            file_size_bytes=data.get("fileSizeBytes", 0),
            mime_type=data.get("mimeType"),
            file_hash=data.get("fileHash"),
            document_issued_date=data.get("documentIssuedDate"),
            document_expiry_date=data.get("documentExpiryDate"),
            issuing_authority=data.get("issuingAuthority"),
            document_reference_number=data.get("documentReferenceNumber"),
            notes=data.get("notes"),
            is_expired=data.get("isExpired", False),
            created_at_utc=data.get("createdAtUtc"),
            last_modified_at_utc=data.get("lastModifiedAtUtc"),
        )
