# -*- coding: utf-8 -*-
"""
Base Step - Abstract base class for wizard steps.

All wizard steps should inherit from this class and implement:
- setup_ui(): Create the step's UI
- validate(): Validate step data
- collect_data(): Collect data from UI
- populate_data(): Populate UI with data
"""

from typing import List, Dict, Any, Optional
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal


@dataclass
class StepValidationResult:
    """Result of step validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0


# Combine PyQt5 metaclass with ABC metaclass
class ABCQWidgetMeta(type(QWidget), ABCMeta):
    """Metaclass that combines PyQt5's metaclass with ABC."""
    pass


class BaseStep(QWidget, metaclass=ABCQWidgetMeta):
    """
    Abstract base class for wizard steps.

    Provides common functionality for:
    - UI setup and lifecycle
    - Data validation
    - Data collection
    - Navigation signals
    """

    # Signals
    step_completed = pyqtSignal()
    step_data_changed = pyqtSignal(dict)
    validation_changed = pyqtSignal(bool)

    def __init__(self, context: 'WizardContext', parent: Optional[QWidget] = None):
        """
        Initialize the step.

        Args:
            context: The wizard context for data sharing
            parent: Parent widget
        """
        super().__init__(parent)
        self.context = context
        self._is_initialized = False

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(16)

    def initialize(self):
        """
        Initialize the step (called once).

        This method is called the first time the step is shown.
        """
        if not self._is_initialized:
            self.setup_ui()
            self._is_initialized = True

    def on_show(self):
        """
        Called when the step is shown.

        Override this method to update UI based on context data.
        """
        if not self._is_initialized:
            self.initialize()
        self.populate_data()

    def on_hide(self):
        """
        Called when the step is hidden (moving to another step).

        Override this method to perform cleanup if needed.
        """
        pass

    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    def setup_ui(self):
        """
        Setup the step's UI.

        This method is called once during initialization.
        Create all widgets and layouts here.
        """
        pass

    @abstractmethod
    def validate(self) -> StepValidationResult:
        """
        Validate the step's data.

        Returns:
            StepValidationResult with validation status and messages
        """
        pass

    @abstractmethod
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect data from the step's UI.

        Returns:
            Dictionary containing step data
        """
        pass

    # =========================================================================
    # Optional Methods - Can be overridden by subclasses
    # =========================================================================

    def populate_data(self):
        """
        Populate the step's UI with data from context.

        Override this method to restore data when navigating back to the step.
        """
        pass

    def get_step_title(self) -> str:
        """
        Get the step's title.

        Override this method to provide a custom title.
        Default implementation returns the class name.
        """
        return self.__class__.__name__

    def get_step_description(self) -> str:
        """
        Get the step's description.

        Override this method to provide a description shown to the user.
        """
        return ""

    def can_skip(self) -> bool:
        """
        Check if the step can be skipped.

        Override this method to allow conditional skipping.
        Default: False
        """
        return False

    def is_optional(self) -> bool:
        """
        Check if the step is optional.

        Override this method to mark the step as optional.
        Default: False
        """
        return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def save_to_context(self, key: str, value: Any):
        """Save data to context."""
        self.context.update_data(key, value)
        self.step_data_changed.emit({key: value})

    def get_from_context(self, key: str, default: Any = None) -> Any:
        """Get data from context."""
        return self.context.get_data(key, default)

    def emit_validation_changed(self, is_valid: bool):
        """Emit validation changed signal."""
        self.validation_changed.emit(is_valid)

    def create_validation_result(self) -> StepValidationResult:
        """Create a new validation result object."""
        return StepValidationResult(is_valid=True, errors=[], warnings=[])
