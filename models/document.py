# -*- coding: utf-8 -*-
"""
Document entity model.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, date
import uuid


@dataclass
class Document:
    """
    Document entity representing supporting documentation.
    """

    # Primary identifier
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Document details
    document_type: str = "TAPU_GREEN"  # From controlled vocabulary
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None

    # Issuing authority
    issuing_authority: Optional[str] = None
    issuing_location: Optional[str] = None

    # Verification
    verified: bool = False
    verified_by: Optional[str] = None
    verification_date: Optional[date] = None

    # Attachment
    attachment_path: Optional[str] = None
    attachment_hash: Optional[str] = None  # SHA-256
    attachment_size: Optional[int] = None  # bytes
    mime_type: Optional[str] = None

    # Notes
    notes: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @property
    def document_type_display(self) -> str:
        """Get display name for document type."""
        types = {
            "TAPU_GREEN": "Property Deed (Green Tapu)",
            "PROPERTY_REG": "Property Registration",
            "COURT_RULING": "Court Ruling",
            "SALE_NOTARIZED": "Notarized Sale Contract",
            "SALE_INFORMAL": "Informal Sale Contract",
            "RENT_REGISTERED": "Registered Rental",
            "RENT_INFORMAL": "Informal Rental",
            "UTILITY_BILL": "Utility Bill",
            "MUKHTAR_CERT": "Mukhtar Certificate",
            "INHERITANCE": "Inheritance Certificate",
            "WITNESS_STATEMENT": "Witness Statement",
        }
        return types.get(self.document_type, self.document_type)

    @property
    def document_type_display_ar(self) -> str:
        """Get Arabic display name for document type."""
        types = {
            "TAPU_GREEN": "صك ملكية (طابو أخضر)",
            "PROPERTY_REG": "بيان قيد عقاري",
            "COURT_RULING": "حكم قضائي",
            "SALE_NOTARIZED": "عقد بيع موثق",
            "SALE_INFORMAL": "عقد بيع غير موثق",
            "RENT_REGISTERED": "عقد إيجار مثبت",
            "RENT_INFORMAL": "عقد إيجار غير مثبت",
            "UTILITY_BILL": "فاتورة مرافق",
            "MUKHTAR_CERT": "شهادة المختار",
            "INHERITANCE": "حصر إرث",
            "WITNESS_STATEMENT": "إفادة شاهد",
        }
        return types.get(self.document_type, self.document_type)

    @property
    def has_attachment(self) -> bool:
        """Check if document has an attachment."""
        return bool(self.attachment_path)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "document_number": self.document_number,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "issuing_authority": self.issuing_authority,
            "issuing_location": self.issuing_location,
            "verified": self.verified,
            "verified_by": self.verified_by,
            "verification_date": self.verification_date.isoformat() if self.verification_date else None,
            "attachment_path": self.attachment_path,
            "attachment_hash": self.attachment_hash,
            "attachment_size": self.attachment_size,
            "mime_type": self.mime_type,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Create Document from dictionary."""
        for field_name in ["issue_date", "expiry_date", "verification_date"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = date.fromisoformat(data[field_name])

        for field_name in ["created_at", "updated_at"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
