# -*- coding: utf-8 -*-
"""
Property Unit entity model.
Implements FR-D-8 STDM legacy integration support.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class PropertyUnit:
    """
    Property Unit entity representing a unit within a building.

    Unit ID Format:
    BUILDING_ID-UUU
    - BUILDING_ID: 17-digit building ID
    - UUU: Unit number (3 digits)

    Implements FR-D-8.2 STDM Integration for Units.
    """

    # Primary identifiers
    unit_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    unit_id: str = ""  # Building ID + unit number
    building_id: str = ""  # Foreign key to Building

    # Unit attributes
    unit_type: str = "apartment"  # apartment, shop, office, warehouse, garage, other
    unit_number: str = "001"
    floor_number: int = 0
    apartment_number: str = ""

    # Status
    apartment_status: str = "occupied"  # occupied, vacant, unknown
    property_description: str = ""

    # Area (optional, approximate)
    area_sqm: Optional[float] = None

    # Legacy STDM Integration (FR-D-8.2)
    legacy_stdm_id: Optional[str] = None  # Original STDM unit identifier
    legacy_stdm_party_id: Optional[str] = None  # STDM party reference
    legacy_stdm_spatial_unit_id: Optional[str] = None  # STDM spatial unit reference

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    def __post_init__(self):
        """Generate unit_id if not provided."""
        if not self.unit_id and self.building_id:
            self.unit_id = f"{self.building_id}-{self.unit_number}"

    @property
    def unit_type_display(self) -> str:
        """Get display name for unit type."""
        # Integer codes from API
        int_types = {1: "Apartment", 2: "Shop", 3: "Office", 4: "Warehouse", 5: "Other"}
        # String keys from local DB
        str_types = {
            "apartment": "Apartment", "shop": "Shop", "office": "Office",
            "warehouse": "Warehouse", "garage": "Garage", "other": "Other",
        }
        try:
            return int_types.get(int(self.unit_type), str(self.unit_type))
        except (ValueError, TypeError):
            pass
        if isinstance(self.unit_type, str):
            return str_types.get(self.unit_type.lower(), self.unit_type)
        return str(self.unit_type) if self.unit_type else "-"

    @property
    def unit_type_display_ar(self) -> str:
        """Get Arabic display name for unit type."""
        # Integer codes from API (matching Vocabularies.UNIT_TYPES)
        int_types = {1: "شقة سكنية", 2: "محل تجاري", 3: "مكتب", 4: "مستودع", 5: "أخرى"}
        # String keys from local DB
        str_types = {
            "apartment": "شقة سكنية", "shop": "محل تجاري", "office": "مكتب",
            "warehouse": "مستودع", "garage": "كراج", "other": "أخرى",
        }
        try:
            return int_types.get(int(self.unit_type), str(self.unit_type))
        except (ValueError, TypeError):
            pass
        if isinstance(self.unit_type, str):
            return str_types.get(self.unit_type.lower(), self.unit_type)
        return str(self.unit_type) if self.unit_type else "-"

    @property
    def status_display(self) -> str:
        """Get display name for status."""
        statuses = {
            "occupied": "Occupied",
            "vacant": "Vacant",
            "unknown": "Unknown",
        }
        return statuses.get(self.apartment_status, self.apartment_status)

    @property
    def floor_display(self) -> str:
        """Get floor display (0 = Ground, negative = basement)."""
        if self.floor_number == 0:
            return "Ground Floor"
        elif self.floor_number < 0:
            return f"Basement {abs(self.floor_number)}"
        else:
            return f"Floor {self.floor_number}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "unit_uuid": self.unit_uuid,
            "unit_id": self.unit_id,
            "building_id": self.building_id,
            "unit_type": self.unit_type,
            "unit_number": self.unit_number,
            "floor_number": self.floor_number,
            "apartment_number": self.apartment_number,
            "apartment_status": self.apartment_status,
            "property_description": self.property_description,
            "area_sqm": self.area_sqm,
            "legacy_stdm_id": self.legacy_stdm_id,
            "legacy_stdm_party_id": self.legacy_stdm_party_id,
            "legacy_stdm_spatial_unit_id": self.legacy_stdm_spatial_unit_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PropertyUnit":
        """Create PropertyUnit from dictionary."""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
