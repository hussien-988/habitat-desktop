# -*- coding: utf-8 -*-
"""
Data validation service.
"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ValidationService:
    """Service for data validation."""

    # Syrian National ID regex (11 digits)
    NATIONAL_ID_PATTERN = re.compile(r"^\d{11}$")

    # Building ID pattern (17 digits with dashes)
    BUILDING_ID_PATTERN = re.compile(r"^\d{2}-\d{2}-\d{2}-\d{3}-\d{3}-\d{5}$")

    # Phone number pattern (Syrian format)
    PHONE_PATTERN = re.compile(r"^(\+963|0)?9\d{8}$")

    def validate_building_id(self, building_id: str) -> ValidationResult:
        """Validate building ID format."""
        errors = []
        warnings = []

        if not building_id:
            errors.append("Building ID is required")
        elif not self.BUILDING_ID_PATTERN.match(building_id):
            errors.append("Building ID must be in format: XX-XX-XX-XXX-XXX-XXXXX")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_national_id(self, national_id: str) -> ValidationResult:
        """Validate Syrian National ID."""
        errors = []
        warnings = []

        if national_id:  # Optional field
            if not self.NATIONAL_ID_PATTERN.match(national_id):
                errors.append("National ID must be 11 digits")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_phone(self, phone: str) -> ValidationResult:
        """Validate phone number."""
        errors = []
        warnings = []

        if phone:  # Optional field
            # Remove spaces and dashes
            clean_phone = re.sub(r"[\s\-]", "", phone)
            if not self.PHONE_PATTERN.match(clean_phone):
                warnings.append("Phone number may not be in valid Syrian format")

        return ValidationResult(
            is_valid=True,  # Phone is optional
            errors=errors,
            warnings=warnings
        )

    def validate_person(self, person_data: Dict[str, Any]) -> ValidationResult:
        """Validate person data."""
        errors = []
        warnings = []

        # Required fields
        if not person_data.get("first_name") and not person_data.get("first_name_ar"):
            errors.append("First name (English or Arabic) is required")

        if not person_data.get("last_name") and not person_data.get("last_name_ar"):
            errors.append("Last name (English or Arabic) is required")

        # Validate national ID if provided
        if person_data.get("national_id"):
            id_result = self.validate_national_id(person_data["national_id"])
            errors.extend(id_result.errors)
            warnings.extend(id_result.warnings)

        # Validate phone if provided
        if person_data.get("mobile_number"):
            phone_result = self.validate_phone(person_data["mobile_number"])
            warnings.extend(phone_result.warnings)

        # Year of birth validation
        if person_data.get("year_of_birth"):
            year = person_data["year_of_birth"]
            if year < 1900 or year > 2024:
                errors.append("Year of birth must be between 1900 and 2024")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_building(self, building_data: Dict[str, Any]) -> ValidationResult:
        """Validate building data."""
        errors = []
        warnings = []

        # Validate building ID
        if building_data.get("building_id"):
            id_result = self.validate_building_id(building_data["building_id"])
            errors.extend(id_result.errors)

        # Required codes
        required_codes = [
            ("governorate_code", "Governorate code"),
            ("district_code", "District code"),
            ("neighborhood_code", "Neighborhood code"),
        ]

        for field, label in required_codes:
            if not building_data.get(field):
                errors.append(f"{label} is required")

        # Validate coordinates if provided
        lat = building_data.get("latitude")
        lon = building_data.get("longitude")

        if lat is not None:
            if lat < -90 or lat > 90:
                errors.append("Latitude must be between -90 and 90")
            # Aleppo approximate bounds
            if lat < 35.5 or lat > 37.0:
                warnings.append("Latitude is outside Aleppo region")

        if lon is not None:
            if lon < -180 or lon > 180:
                errors.append("Longitude must be between -180 and 180")
            # Aleppo approximate bounds
            if lon < 36.5 or lon > 38.0:
                warnings.append("Longitude is outside Aleppo region")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_unit(self, unit_data: Dict[str, Any]) -> ValidationResult:
        """Validate property unit data."""
        errors = []
        warnings = []

        if not unit_data.get("building_id"):
            errors.append("Building ID is required")

        if not unit_data.get("unit_type"):
            errors.append("Unit type is required")

        floor = unit_data.get("floor_number", 0)
        if floor < -5 or floor > 50:
            warnings.append("Floor number seems unusual")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_claim(self, claim_data: Dict[str, Any]) -> ValidationResult:
        """Validate claim data."""
        errors = []
        warnings = []

        if not claim_data.get("unit_id"):
            errors.append("Property unit is required")

        if not claim_data.get("person_ids"):
            errors.append("At least one claimant is required")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_import_record(self, record: Dict[str, Any], record_type: str) -> ValidationResult:
        """Validate a record from import file."""
        if record_type == "building":
            return self.validate_building(record)
        elif record_type == "person":
            return self.validate_person(record)
        elif record_type == "unit":
            return self.validate_unit(record)
        elif record_type == "claim":
            return self.validate_claim(record)
        else:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown record type: {record_type}"],
                warnings=[]
            )
