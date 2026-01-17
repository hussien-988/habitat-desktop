# -*- coding: utf-8 -*-
"""
Validation Strategy Pattern - Abstract interface for record validation.

Provides a pluggable architecture for different validation rules without
modifying existing validation logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ValidationStrategy(ABC):
    """
    Abstract base class for validation strategies.

    Each strategy implements specific validation rules for different record types.
    """

    @abstractmethod
    def validate(self, record: Dict[str, Any]) -> List[str]:
        """
        Validate a record and return list of error messages.

        Args:
            record: Dictionary containing record data to validate

        Returns:
            List of error messages (empty list if valid)
        """
        pass

    def is_valid(self, record: Dict[str, Any]) -> bool:
        """
        Check if record is valid.

        Args:
            record: Dictionary containing record data

        Returns:
            True if record passes all validations, False otherwise
        """
        return len(self.validate(record)) == 0


class GenericRequiredFieldsValidator(ValidationStrategy):
    """
    Generic validator for checking required fields.

    Validates that specified fields exist and are not empty.
    """

    def __init__(self, required_fields: List[str], field_labels: Optional[Dict[str, str]] = None):
        """
        Initialize validator with required fields.

        Args:
            required_fields: List of field names that must be present and non-empty
            field_labels: Optional mapping of field names to human-readable labels
        """
        self.required_fields = required_fields
        self.field_labels = field_labels or {}

    def validate(self, record: Dict[str, Any]) -> List[str]:
        """
        Validate that all required fields are present and non-empty.

        Args:
            record: Dictionary containing record data

        Returns:
            List of error messages for missing or empty fields
        """
        errors = []

        for field in self.required_fields:
            # Get human-readable label or use field name
            label = self.field_labels.get(field, field)

            # Check if field exists
            if field not in record:
                errors.append(f"Missing required field: {label}")
                continue

            # Check if field is not empty
            value = record[field]
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Required field cannot be empty: {label}")

        return errors

    def add_required_field(self, field_name: str, label: Optional[str] = None):
        """
        Add a required field to validation.

        Args:
            field_name: Name of the field to require
            label: Optional human-readable label for error messages
        """
        if field_name not in self.required_fields:
            self.required_fields.append(field_name)
        if label:
            self.field_labels[field_name] = label

    def remove_required_field(self, field_name: str):
        """
        Remove a required field from validation.

        Args:
            field_name: Name of the field to remove
        """
        if field_name in self.required_fields:
            self.required_fields.remove(field_name)
        self.field_labels.pop(field_name, None)
