# -*- coding: utf-8 -*-
"""
Wizard Context - Base class for managing wizard state and data.

Provides unified interface for:
- Data persistence
- Serialization/deserialization
- State tracking
- Reference number generation
"""

from typing import Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
import uuid


class WizardContext(ABC):
    """
    Base class for wizard context.

    All wizard contexts should inherit from this class and implement:
    - to_dict(): Serialize context to dictionary
    - from_dict(): Restore context from dictionary
    """

    def __init__(self):
        """Initialize base context properties."""
        self.wizard_id: str = str(uuid.uuid4())
        self.status: str = "draft"  # draft, in_progress, completed, cancelled
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
        self.current_step_index: int = 0
        self.user_id: Optional[str] = None
        self.reference_number: str = self._generate_reference_number()

        # Step completion tracking
        self.completed_steps: set = set()

        # Custom data storage
        self.data: Dict[str, Any] = {}

    def _generate_reference_number(self) -> str:
        """
        Generate a unique reference number for the wizard session.

        Format: {PREFIX}-{YYYYMMDDHHMMSS}-{SHORT_UUID}
        Example: WIZ-20260118153045-A3F2

        Override this method in subclasses to customize the format.
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        short_id = self.wizard_id[:4].upper()
        prefix = self._get_reference_prefix()
        return f"{prefix}-{timestamp}-{short_id}"

    def _get_reference_prefix(self) -> str:
        """Get the prefix for reference number. Override in subclasses."""
        return "WIZ"

    def mark_step_completed(self, step_index: int):
        """Mark a step as completed."""
        self.completed_steps.add(step_index)
        self.updated_at = datetime.now()

    def is_step_completed(self, step_index: int) -> bool:
        """Check if a step is completed."""
        return step_index in self.completed_steps

    def update_data(self, key: str, value: Any):
        """Update data in the context."""
        self.data[key] = value
        self.updated_at = datetime.now()

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data from the context."""
        return self.data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize context to dictionary.

        Subclasses should call super().to_dict() and add their own fields.
        """
        return {
            "wizard_id": self.wizard_id,
            "reference_number": self.reference_number,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_step_index": self.current_step_index,
            "user_id": self.user_id,
            "completed_steps": list(self.completed_steps),
            "data": self.data
        }

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WizardContext':
        """
        Restore context from dictionary.

        Subclasses must implement this method.
        """
        pass

    @classmethod
    def _restore_base_fields(cls, context: 'WizardContext', data: Dict[str, Any]):
        """Helper method to restore base fields from dictionary."""
        context.wizard_id = data.get("wizard_id", context.wizard_id)
        context.reference_number = data.get("reference_number", context.reference_number)
        context.status = data.get("status", "draft")
        context.current_step_index = data.get("current_step_index", 0)
        context.user_id = data.get("user_id")
        context.completed_steps = set(data.get("completed_steps", []))
        context.data = data.get("data", {})

        # Parse datetime strings
        if "created_at" in data:
            context.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            context.updated_at = datetime.fromisoformat(data["updated_at"])
