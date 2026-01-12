# -*- coding: utf-8 -*-
"""
Building entity model.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class Building:
    """
    Building entity representing a physical building structure.

    Building ID Format (17 digits):
    GG-DD-SS-CCC-NNN-BBBBB
    - GG: Governorate code (2 digits)
    - DD: District code (2 digits)
    - SS: Sub-district code (2 digits)
    - CCC: Community code (3 digits)
    - NNN: Neighborhood code (3 digits)
    - BBBBB: Building number (5 digits)
    """

    # Primary identifiers
    building_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    building_id: str = ""  # 17-digit UN-Habitat code

    # Administrative hierarchy
    governorate_code: str = "01"
    governorate_name: str = "Aleppo"
    governorate_name_ar: str = "حلب"

    district_code: str = "01"
    district_name: str = "Aleppo City"
    district_name_ar: str = "مدينة حلب"

    subdistrict_code: str = "01"
    subdistrict_name: str = "Aleppo Center"
    subdistrict_name_ar: str = "حلب المركز"

    community_code: str = "001"
    community_name: str = "Downtown"
    community_name_ar: str = "وسط المدينة"

    neighborhood_code: str = "001"
    neighborhood_name: str = "Al-Jamiliyah"
    neighborhood_name_ar: str = "الجميلية"

    building_number: str = "00001"

    # Building attributes
    building_type: str = "residential"  # residential, commercial, mixed_use
    building_status: str = "intact"  # intact, minor_damage, major_damage, destroyed

    number_of_units: int = 0
    number_of_apartments: int = 0
    number_of_shops: int = 0
    number_of_floors: int = 1

    # Geometry (point coordinates for prototype)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_location: Optional[str] = None  # WKT or GeoJSON string

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    # Legacy support
    legacy_stdm_id: Optional[str] = None

    def __post_init__(self):
        """Generate building_id if not provided."""
        if not self.building_id:
            self.building_id = self.generate_building_id()

    def generate_building_id(self) -> str:
        """Generate the 17-digit UN-Habitat building ID."""
        return (
            f"{self.governorate_code}-"
            f"{self.district_code}-"
            f"{self.subdistrict_code}-"
            f"{self.community_code}-"
            f"{self.neighborhood_code}-"
            f"{self.building_number}"
        )

    @property
    def full_address(self) -> str:
        """Get full address in English."""
        return f"{self.neighborhood_name}, {self.district_name}, {self.governorate_name}"

    @property
    def full_address_ar(self) -> str:
        """Get full address in Arabic."""
        return f"{self.neighborhood_name_ar}، {self.district_name_ar}، {self.governorate_name_ar}"

    @property
    def building_type_display(self) -> str:
        """Get display name for building type (Arabic)."""
        types = {
            "residential": "سكني",
            "commercial": "تجاري",
            "mixed_use": "متعدد الاستخدامات",
            "industrial": "صناعي",
            "public": "عام",
        }
        return types.get(self.building_type, self.building_type)

    @property
    def building_status_display(self) -> str:
        """Get display name for building status (Arabic)."""
        statuses = {
            "intact": "سليم",
            "standing": "سليم",
            "minor_damage": "ضرر طفيف",
            "damaged": "متضرر",
            "partially_damaged": "متضرر جزئياً",
            "major_damage": "ضرر كبير",
            "severely_damaged": "متضرر بشدة",
            "destroyed": "مدمر",
            "demolished": "مهدم",
            "rubble": "ركام",
            "under_construction": "قيد البناء",
        }
        return statuses.get(self.building_status, self.building_status)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "building_uuid": self.building_uuid,
            "building_id": self.building_id,
            "governorate_code": self.governorate_code,
            "governorate_name": self.governorate_name,
            "governorate_name_ar": self.governorate_name_ar,
            "district_code": self.district_code,
            "district_name": self.district_name,
            "district_name_ar": self.district_name_ar,
            "subdistrict_code": self.subdistrict_code,
            "subdistrict_name": self.subdistrict_name,
            "subdistrict_name_ar": self.subdistrict_name_ar,
            "community_code": self.community_code,
            "community_name": self.community_name,
            "community_name_ar": self.community_name_ar,
            "neighborhood_code": self.neighborhood_code,
            "neighborhood_name": self.neighborhood_name,
            "neighborhood_name_ar": self.neighborhood_name_ar,
            "building_number": self.building_number,
            "building_type": self.building_type,
            "building_status": self.building_status,
            "number_of_units": self.number_of_units,
            "number_of_apartments": self.number_of_apartments,
            "number_of_shops": self.number_of_shops,
            "number_of_floors": self.number_of_floors,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "geo_location": self.geo_location,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "legacy_stdm_id": self.legacy_stdm_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Building":
        """Create Building from dictionary."""
        # Handle datetime fields
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
