# -*- coding: utf-8 -*-
"""
Person entity model.
Implements FR-D-8 STDM legacy integration support.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class Person:
    """
    Person entity representing individuals in the system.
    Supports Arabic names and Syrian national ID format.

    Implements FR-D-8.3 STDM Integration for Persons.
    """

    # Primary identifier
    person_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Personal details (Arabic)
    first_name: str = ""
    first_name_ar: str = ""
    father_name: str = ""
    father_name_ar: str = ""
    mother_name: str = ""
    mother_name_ar: str = ""
    last_name: str = ""
    last_name_ar: str = ""

    # Demographics
    gender: str = "male"  # male, female
    year_of_birth: Optional[int] = None
    nationality: str = "Syrian"

    # Identification
    national_id: str = ""  # Syrian National ID (11 digits)
    passport_number: Optional[str] = None

    # Contact
    phone_number: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

    # Status flags
    is_contact_person: bool = False
    is_deceased: bool = False

    # Legacy STDM Integration (FR-D-8.3)
    legacy_stdm_id: Optional[str] = None  # Original STDM party identifier
    legacy_stdm_party_type: Optional[str] = None  # STDM party type (individual, group, etc.)
    legacy_stdm_social_tenure_id: Optional[str] = None  # STDM social tenure relationship ID

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get full name in English."""
        parts = [self.first_name, self.father_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def full_name_ar(self) -> str:
        """Get full name in Arabic."""
        parts = [self.first_name_ar, self.father_name_ar, self.last_name_ar]
        return " ".join(p for p in parts if p)

    @property
    def display_name(self) -> str:
        """Get display name (Arabic if available, else English)."""
        if self.full_name_ar:
            return self.full_name_ar
        return self.full_name

    @property
    def gender_display(self) -> str:
        """Get gender display name."""
        from services.vocab_service import get_label
        return get_label("Gender", self.gender, lang="en")

    @property
    def gender_display_ar(self) -> str:
        """Get gender display name in Arabic."""
        from services.vocab_service import get_label
        return get_label("Gender", self.gender, lang="ar")

    @property
    def age(self) -> Optional[int]:
        """Calculate approximate age."""
        if self.year_of_birth:
            return datetime.now().year - self.year_of_birth
        return None

    def validate_national_id(self) -> bool:
        """Validate Syrian National ID format (11 digits)."""
        if not self.national_id:
            return True  # Optional field
        return self.national_id.isdigit() and len(self.national_id) == 11

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "person_id": self.person_id,
            "first_name": self.first_name,
            "first_name_ar": self.first_name_ar,
            "father_name": self.father_name,
            "father_name_ar": self.father_name_ar,
            "mother_name": self.mother_name,
            "mother_name_ar": self.mother_name_ar,
            "last_name": self.last_name,
            "last_name_ar": self.last_name_ar,
            "gender": self.gender,
            "year_of_birth": self.year_of_birth,
            "nationality": self.nationality,
            "national_id": self.national_id,
            "passport_number": self.passport_number,
            "phone_number": self.phone_number,
            "mobile_number": self.mobile_number,
            "email": self.email,
            "address": self.address,
            "is_contact_person": self.is_contact_person,
            "is_deceased": self.is_deceased,
            "legacy_stdm_id": self.legacy_stdm_id,
            "legacy_stdm_party_type": self.legacy_stdm_party_type,
            "legacy_stdm_social_tenure_id": self.legacy_stdm_social_tenure_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Person":
        """Create Person from dictionary."""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
