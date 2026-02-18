# -*- coding: utf-8 -*-
"""
Validation Factory - Creates appropriate validators for different record types.

Provides a central point for creating and managing validation strategies.
"""

from typing import Dict, Optional, List
from .validation_strategy import ValidationStrategy, GenericRequiredFieldsValidator


class ValidationFactory:
    """
    Factory for creating validation strategies based on record type.

    This class acts as a registry and factory for different validation strategies,
    allowing easy creation of validators for different record types.
    """

    def __init__(self):
        """Initialize the validation factory."""
        self._validators: Dict[str, ValidationStrategy] = {}
        self._register_default_validators()

    def _register_default_validators(self):
        """Register built-in validators for common record types."""
        # Example: Unit record validator
        self.register_validator(
            'unit',
            GenericRequiredFieldsValidator(
                required_fields=['unit_id', 'building_id'],
                field_labels={
                    'unit_id': 'Unit ID',
                    'building_id': 'Building ID'
                }
            )
        )

        # Example: Person record validator
        self.register_validator(
            'person',
            GenericRequiredFieldsValidator(
                required_fields=['person_id', 'full_name'],
                field_labels={
                    'person_id': 'Person ID',
                    'full_name': 'Full Name'
                }
            )
        )

        # Example: Household record validator
        self.register_validator(
            'household',
            GenericRequiredFieldsValidator(
                required_fields=['household_id', 'unit_id'],
                field_labels={
                    'household_id': 'Household ID',
                    'unit_id': 'Unit ID'
                }
            )
        )

    def register_validator(self, record_type: str, validator: ValidationStrategy):
        """
        Register a validation strategy for a specific record type.

        Args:
            record_type: Type identifier (e.g., 'unit', 'person', 'household')
            validator: ValidationStrategy instance
        """
        self._validators[record_type.lower()] = validator

    def get_validator(self, record_type: str) -> Optional[ValidationStrategy]:
        """
        Get a registered validator by record type.

        Args:
            record_type: Type identifier

        Returns:
            ValidationStrategy instance or None if not found
        """
        return self._validators.get(record_type.lower())

    def validate(self, record: Dict, record_type: str) -> List[str]:
        """
        Validate a record using the appropriate validator.

        Args:
            record: Dictionary containing record data
            record_type: Type of record to validate

        Returns:
            List of error messages (empty if valid)
        """
        validator = self.get_validator(record_type)
        if not validator:
            return [f"No validator registered for record type: {record_type}"]

        return validator.validate(record)

    def is_valid(self, record: Dict, record_type: str) -> bool:
        """
        Check if a record is valid.

        Args:
            record: Dictionary containing record data
            record_type: Type of record to validate

        Returns:
            True if record passes validation, False otherwise
        """
        return len(self.validate(record, record_type)) == 0

    def get_registered_types(self) -> List[str]:
        """
        Get list of registered record types.

        Returns:
            List of record type identifiers
        """
        return list(self._validators.keys())
