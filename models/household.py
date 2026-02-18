# -*- coding: utf-8 -*-
"""
Household/Occupancy entity model.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import uuid


@dataclass
class Household:
    """
    Household entity representing occupancy data for a property unit.
    Linked to a Unit (and indirectly to Claims through the unit).
    """

    # Primary identifier
    household_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Foreign keys
    unit_id: str = ""  # FK to PropertyUnit
    main_occupant_id: Optional[str] = None  # FK to Person (optional)
    main_occupant_name: Optional[str] = None  # Fallback if no person linked

    # Occupancy counts
    occupancy_size: int = 1  # Total household size
    male_count: int = 0
    female_count: int = 0
    minors_count: int = 0  # Under 18
    adults_count: int = 0  # 18-59
    elderly_count: int = 0  # 60+
    with_disability_count: int = 0

    # Occupancy details
    occupancy_type: Optional[str] = None  # owner, tenant, guest, etc.
    occupancy_nature: Optional[str] = None  # permanent, temporary, seasonal
    occupancy_start_date: Optional[date] = None
    monthly_rent: Optional[Decimal] = None

    # Notes
    notes: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    # Occupancy types
    OCCUPANCY_TYPES = [
        ("owner", "Owner", "مالك"),
        ("tenant", "Tenant", "مستأجر"),
        ("guest", "Guest", "ضيف"),
        ("caretaker", "Caretaker", "حارس"),
        ("relative", "Relative", "قريب"),
        ("other", "Other", "آخر"),
    ]

    # Occupancy natures
    OCCUPANCY_NATURES = [
        ("permanent", "Permanent", "دائم"),
        ("temporary", "Temporary", "مؤقت"),
        ("seasonal", "Seasonal", "موسمي"),
    ]

    @property
    def occupancy_type_display(self) -> str:
        """Get display name for occupancy type."""
        for code, en, ar in self.OCCUPANCY_TYPES:
            if code == self.occupancy_type:
                return en
        return self.occupancy_type or ""

    @property
    def occupancy_type_display_ar(self) -> str:
        """Get Arabic display name for occupancy type."""
        for code, en, ar in self.OCCUPANCY_TYPES:
            if code == self.occupancy_type:
                return ar
        return self.occupancy_type or ""

    @property
    def occupancy_nature_display(self) -> str:
        """Get display name for occupancy nature."""
        for code, en, ar in self.OCCUPANCY_NATURES:
            if code == self.occupancy_nature:
                return en
        return self.occupancy_nature or ""

    @property
    def occupancy_nature_display_ar(self) -> str:
        """Get Arabic display name for occupancy nature."""
        for code, en, ar in self.OCCUPANCY_NATURES:
            if code == self.occupancy_nature:
                return ar
        return self.occupancy_nature or ""

    def validate(self) -> list:
        """
        Validate household data.
        Returns list of error messages (empty if valid).
        """
        errors = []

        # Required fields
        if not self.unit_id:
            errors.append("الوحدة مطلوبة")

        # Non-negative counts
        if self.occupancy_size < 0:
            errors.append("حجم الأسرة لا يمكن أن يكون سالباً")
        if self.male_count < 0:
            errors.append("عدد الذكور لا يمكن أن يكون سالباً")
        if self.female_count < 0:
            errors.append("عدد الإناث لا يمكن أن يكون سالباً")
        if self.minors_count < 0:
            errors.append("عدد القاصرين لا يمكن أن يكون سالباً")
        if self.adults_count < 0:
            errors.append("عدد البالغين لا يمكن أن يكون سالباً")
        if self.elderly_count < 0:
            errors.append("عدد كبار السن لا يمكن أن يكون سالباً")
        if self.with_disability_count < 0:
            errors.append("عدد ذوي الإعاقة لا يمكن أن يكون سالباً")

        # Gender sum validation
        gender_sum = self.male_count + self.female_count
        if gender_sum > self.occupancy_size:
            errors.append(f"مجموع الذكور والإناث ({gender_sum}) يتجاوز حجم الأسرة ({self.occupancy_size})")

        # Age group sum validation
        age_sum = self.minors_count + self.adults_count + self.elderly_count
        if age_sum > self.occupancy_size:
            errors.append(f"مجموع الفئات العمرية ({age_sum}) يتجاوز حجم الأسرة ({self.occupancy_size})")

        # Disability count validation
        if self.with_disability_count > self.occupancy_size:
            errors.append(f"عدد ذوي الإعاقة ({self.with_disability_count}) يتجاوز حجم الأسرة ({self.occupancy_size})")

        # Monthly rent validation
        if self.monthly_rent is not None and self.monthly_rent < 0:
            errors.append("الإيجار الشهري لا يمكن أن يكون سالباً")

        return errors

    def is_valid(self) -> bool:
        """Check if household data is valid."""
        return len(self.validate()) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "household_id": self.household_id,
            "unit_id": self.unit_id,
            "main_occupant_id": self.main_occupant_id,
            "main_occupant_name": self.main_occupant_name,
            "occupancy_size": self.occupancy_size,
            "male_count": self.male_count,
            "female_count": self.female_count,
            "minors_count": self.minors_count,
            "adults_count": self.adults_count,
            "elderly_count": self.elderly_count,
            "with_disability_count": self.with_disability_count,
            "occupancy_type": self.occupancy_type,
            "occupancy_nature": self.occupancy_nature,
            "occupancy_start_date": self.occupancy_start_date.isoformat() if self.occupancy_start_date else None,
            "monthly_rent": float(self.monthly_rent) if self.monthly_rent else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Household":
        """Create Household from dictionary."""
        # Handle date field
        if isinstance(data.get("occupancy_start_date"), str):
            data["occupancy_start_date"] = date.fromisoformat(data["occupancy_start_date"])

        # Handle datetime fields
        for field_name in ["created_at", "updated_at"]:
            if isinstance(data.get(field_name), str):
                data[field_name] = datetime.fromisoformat(data[field_name])

        # Handle Decimal
        if data.get("monthly_rent") is not None:
            data["monthly_rent"] = Decimal(str(data["monthly_rent"]))

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
