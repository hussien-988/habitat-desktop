# -*- coding: utf-8 -*-
"""
Building entity model.
"""

from dataclasses import dataclass, field
from typing import Optional, Union
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
    building_id: str = ""  # ✅ 17-digit numeric ID (NO dashes): 01010010010000001
    building_id_formatted: str = ""  # ✅ Display format (WITH dashes): 01-01-01-001-001-00001

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
    # building_type: 1=Residential, 2=Commercial, 3=MixedUse, 4=Industrial (or string for legacy)
    building_type: Union[int, str] = 1
    # building_status: 1=Intact, 2=MinorDamage, 3=MajorDamage, 4=Destroyed, etc. (or string for legacy)
    building_status: Union[int, str] = 1

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
        """
        Generate building_id if not provided and ensure no dashes.

        ✅ FIXED: Clean existing data by removing dashes for API compatibility.
        """
        if not self.building_id:
            self.building_id = self.generate_building_id()
        else:
            # ✅ FIX: Remove dashes if present (clean existing data)
            self.building_id = self.building_id.replace("-", "")

        # ✅ Ensure building_id_formatted is set (for backward compatibility)
        if not self.building_id_formatted and self.building_id:
            self.building_id_formatted = self.building_id_display

    def generate_building_id(self) -> str:
        """
        Generate the 17-digit UN-Habitat building ID (NO dashes).

        ✅ FIXED: Removed dashes for API compatibility.
        Format: 01010010010000001 (17 digits)
        Example: governorate(01) + district(01) + subdistrict(01) +
                 community(001) + neighborhood(001) + building(00001)
        """
        return (
            f"{self.governorate_code}"
            f"{self.district_code}"
            f"{self.subdistrict_code}"
            f"{self.community_code}"
            f"{self.neighborhood_code}"
            f"{self.building_number}"
        )

    @property
    def building_id_display(self) -> str:
        """
        Get formatted building ID with dashes for display (UI only).

        ✅ Best Practice: Separate storage format (no dashes) from display format (with dashes).
        This property is for UI display only - NEVER use it for API calls!

        Returns:
            Formatted ID with dashes: 01-01-01-001-001-00001
        """
        if not self.building_id:
            # Generate formatted version from components
            return (
                f"{self.governorate_code}-"
                f"{self.district_code}-"
                f"{self.subdistrict_code}-"
                f"{self.community_code}-"
                f"{self.neighborhood_code}-"
                f"{self.building_number}"
            )

        # Format existing building_id (if stored without dashes)
        if len(self.building_id) == 17 and "-" not in self.building_id:
            return (
                f"{self.building_id[0:2]}-"
                f"{self.building_id[2:4]}-"
                f"{self.building_id[4:6]}-"
                f"{self.building_id[6:9]}-"
                f"{self.building_id[9:12]}-"
                f"{self.building_id[12:17]}"
            )

        # Already formatted or invalid - return as-is
        return self.building_id

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
        # Support both integer (API) and string (legacy) values
        types_int = {
            1: "سكني",
            2: "تجاري",
            3: "مختلط (سكني وتجاري)",
            4: "صناعي",
        }
        types_str = {
            "residential": "سكني",
            "commercial": "تجاري",
            "mixed_use": "مختلط (سكني وتجاري)",
            "industrial": "صناعي",
            "public": "عام",
        }
        if isinstance(self.building_type, int):
            return types_int.get(self.building_type, str(self.building_type))
        return types_str.get(self.building_type, str(self.building_type))

    @property
    def building_status_display(self) -> str:
        """Get display name for building status (Arabic)."""
        # Support both integer (API) and string (legacy) values
        # API: 1=Intact, 2=MinorDamage, 3=ModerateDamage, 4=MajorDamage, 5=SeverelyDamaged,
        #      6=Destroyed, 7=UnderConstruction, 8=Abandoned, 99=Unknown
        statuses_int = {
            1: "سليم",
            2: "أضرار طفيفة",
            3: "أضرار متوسطة",
            4: "أضرار كبيرة",
            5: "أضرار شديدة",
            6: "مدمر",
            7: "قيد الإنشاء",
            8: "مهجور",
            99: "غير معروف",
        }
        statuses_str = {
            "intact": "سليم",
            "standing": "سليم",
            "minordamage": "أضرار طفيفة",
            "minor_damage": "أضرار طفيفة",
            "moderatedamage": "أضرار متوسطة",
            "moderate_damage": "أضرار متوسطة",
            "damaged": "أضرار متوسطة",
            "partially_damaged": "أضرار متوسطة",
            "majordamage": "أضرار كبيرة",
            "major_damage": "أضرار كبيرة",
            "severelydamaged": "أضرار شديدة",
            "severely_damaged": "أضرار شديدة",
            "destroyed": "مدمر",
            "demolished": "مدمر",
            "rubble": "مدمر",
            "underconstruction": "قيد الإنشاء",
            "under_construction": "قيد الإنشاء",
            "abandoned": "مهجور",
            "unknown": "غير معروف",
        }
        if isinstance(self.building_status, int):
            return statuses_int.get(self.building_status, str(self.building_status))
        return statuses_str.get(self.building_status, str(self.building_status))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "building_uuid": self.building_uuid,
            "building_id": self.building_id,
            "building_id_formatted": self.building_id_formatted,
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
        """
        Create Building from dictionary.

        ✅ SOLID: Handles API field name mapping (DRY principle)
        Maps API response field names to Building dataclass field names.
        """
        # ✅ Field mapping: API → Building dataclass
        # This ensures compatibility with BuildingAssignments API response
        field_mapping = {
            "id": "building_uuid",  # API uses "id" for UUID
            "buildingCode": "building_id",  # API uses "buildingCode" for formatted ID
        }

        # Apply field name mapping
        mapped_data = {}
        for api_field, value in data.items():
            # Use mapped field name if exists, otherwise use original
            dataclass_field = field_mapping.get(api_field, api_field)
            mapped_data[dataclass_field] = value

        # Handle datetime fields
        if isinstance(mapped_data.get("created_at"), str):
            mapped_data["created_at"] = datetime.fromisoformat(mapped_data["created_at"])
        if isinstance(mapped_data.get("updated_at"), str):
            mapped_data["updated_at"] = datetime.fromisoformat(mapped_data["updated_at"])

        # ✅ SOLID: Only use fields that exist in dataclass (prevents errors)
        return cls(**{k: v for k, v in mapped_data.items() if k in cls.__dataclass_fields__})
