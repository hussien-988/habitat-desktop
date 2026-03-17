# -*- coding: utf-8 -*-
"""
Base Step - Abstract base class for wizard steps.
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
    """Abstract base class for wizard steps."""

    # Signals
    step_completed = pyqtSignal()
    step_data_changed = pyqtSignal(dict)
    validation_changed = pyqtSignal(bool)

    def __init__(self, context: 'WizardContext', parent: Optional[QWidget] = None):
        """Initialize the step."""
        super().__init__(parent)
        self.context = context
        self._is_initialized = False

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(16)

    def initialize(self):
        """Initialize the step (called once when first shown)."""
        if not self._is_initialized:
            self.setup_ui()
            self._is_initialized = True

    def on_show(self):
        """Called when the step is shown."""
        if not self._is_initialized:
            self.initialize()
        self.populate_data()

    def on_hide(self):
        """Called when the step is hidden."""
        pass

    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    def setup_ui(self):
        """Setup the step's UI."""
        pass

    @abstractmethod
    def validate(self) -> StepValidationResult:
        """Validate the step's data."""
        pass

    @abstractmethod
    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step's UI."""
        pass

    # =========================================================================
    # Optional Methods - Can be overridden by subclasses
    # =========================================================================

    def populate_data(self):
        """Populate the step's UI with data from context."""
        pass

    def reset(self):
        """Reset step UI to a clean state."""
        pass

    def get_step_title(self) -> str:
        """Get the step's title."""
        return self.__class__.__name__

    def get_step_description(self) -> str:
        """Get the step's description."""
        return ""

    def can_skip(self) -> bool:
        """Check if the step can be skipped."""
        return False

    def is_optional(self) -> bool:
        """Check if the step is optional."""
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

    def _set_auth_token(self):
        """Set auth token from main window on all API service attributes."""
        main_window = self.window()
        if not (main_window and hasattr(main_window, '_api_token') and main_window._api_token):
            return
        token = main_window._api_token
        for attr_name in ('_api_service', '_api_client', '_survey_api_service'):
            service = getattr(self, attr_name, None)
            if service and hasattr(service, 'set_access_token'):
                service.set_access_token(token)
