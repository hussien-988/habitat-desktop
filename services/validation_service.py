# -*- coding: utf-8 -*-
"""
Data validation service.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from services.validation.validation_factory import ValidationFactory
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

    def __init__(self, use_factory: bool = False):
        """
        Initialize validation service.

        Args:
            use_factory: If True, use ValidationFactory for basic field validation
                        (Optional enhancement, defaults to False for backwards compatibility)
        """
        self._use_factory = use_factory
        self._validation_factory = ValidationFactory() if use_factory else None

    def validate_building_id(self, building_id: str) -> ValidationResult:
        """Validate building ID format."""
        errors = []
        warnings = []

        if not building_id:
            errors.append("رمز البناء مطلوب (Building ID is required)")
        elif not self.BUILDING_ID_PATTERN.match(building_id):
            errors.append("صيغة رمز البناء غير صحيحة. الصيغة المطلوبة: GG-DD-SS-CCC-NNN-BBBBB")

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

        # Required codes - رسائل عربية واضحة
        required_codes = [
            ("governorate_code", "رمز المحافظة مطلوب (Governorate code is required)"),
            ("district_code", "رمز المنطقة مطلوب (District code is required)"),
            ("subdistrict_code", "رمز المنطقة الفرعية مطلوب (Subdistrict code is required)"),
            ("community_code", "رمز المجتمع مطلوب (Community code is required)"),
            ("neighborhood_code", "رمز الحي مطلوب (Neighborhood code is required)"),
        ]

        for field, error_msg in required_codes:
            if not building_data.get(field):
                errors.append(error_msg)

        # Validate coordinates if provided
        lat = building_data.get("latitude")
        lon = building_data.get("longitude")

        if lat is not None:
            if lat < -90 or lat > 90:
                errors.append("خط العرض يجب أن يكون بين -90 و 90 (Latitude must be between -90 and 90)")
            # Aleppo approximate bounds (relaxed - just a warning)
            if lat < 35.0 or lat > 37.5:
                warnings.append("الإحداثيات قد تكون خارج منطقة حلب (Coordinates may be outside Aleppo)")

        if lon is not None:
            if lon < -180 or lon > 180:
                errors.append("خط الطول يجب أن يكون بين -180 و 180 (Longitude must be between -180 and 180)")
            # Aleppo approximate bounds (relaxed - just a warning)
            if lon < 36.0 or lon > 38.5:
                warnings.append("الإحداثيات قد تكون خارج منطقة حلب (Coordinates may be outside Aleppo)")

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

    def _validate_with_factory(self, record: Dict[str, Any], record_type: str) -> List[str]:
        """
        Internal helper to perform basic field validation using ValidationFactory.

        Returns:
            List of error messages from factory validation
        """
        if not self._validation_factory:
            return []

        return self._validation_factory.validate(record, record_type)

    def validate_import_record(self, record: Dict[str, Any], record_type: str) -> ValidationResult:
        """Validate a record from import file."""
        # Optional: Perform basic field validation using factory if enabled
        factory_errors = self._validate_with_factory(record, record_type) if self._use_factory else []

        # Perform specialized validation (domain logic, patterns, etc.)
        if record_type == "building":
            result = self.validate_building(record)
        elif record_type == "person":
            result = self.validate_person(record)
        elif record_type == "unit":
            result = self.validate_unit(record)
        elif record_type == "claim":
            result = self.validate_claim(record)
        else:
            return ValidationResult(
                is_valid=False,
                errors=[f"Unknown record type: {record_type}"],
                warnings=[]
            )

        # Merge factory errors with specialized validation errors
        if factory_errors:
            result.errors = factory_errors + result.errors
            result.is_valid = len(result.errors) == 0

        return result
