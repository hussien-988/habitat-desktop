# -*- coding: utf-8 -*-
"""
Step Navigator - Manages navigation between wizard steps.

Handles:
- Step progression (next/previous)
- Step validation before navigation
- Progress tracking
- Step state management
"""

from typing import List, Optional
from PyQt5.QtCore import QObject, pyqtSignal

from .base_step import BaseStep, StepValidationResult
from .wizard_context import WizardContext
from utils.logger import get_logger

logger = get_logger(__name__)


class StepNavigator(QObject):
    """
    Manages navigation between wizard steps.

    Responsibilities:
    - Track current step
    - Validate before navigation
    - Emit signals for UI updates
    - Manage step lifecycle (show/hide)
    """

    # Signals
    step_changed = pyqtSignal(int, int)  # old_index, new_index
    can_go_next_changed = pyqtSignal(bool)
    can_go_previous_changed = pyqtSignal(bool)
    validation_failed = pyqtSignal(StepValidationResult)

    def __init__(self, context: WizardContext, steps: List[BaseStep]):
        """
        Initialize the navigator.

        Args:
            context: Wizard context
            steps: List of wizard steps
        """
        super().__init__()
        self.context = context
        self.steps = steps
        self.current_index = 0

        # Connect step signals
        for step in self.steps:
            step.validation_changed.connect(self._on_step_validation_changed)
            step.step_data_changed.connect(self._on_step_data_changed)

    def get_current_step(self) -> Optional[BaseStep]:
        """Get the current step."""
        if 0 <= self.current_index < len(self.steps):
            return self.steps[self.current_index]
        return None

    def get_step_count(self) -> int:
        """Get total number of steps."""
        return len(self.steps)

    def can_go_next(self) -> bool:
        """Check if we can navigate to the next step."""
        return self.current_index < len(self.steps) - 1

    def can_go_previous(self) -> bool:
        """Check if we can navigate to the previous step."""
        return self.current_index > 0

    def next_step(self, skip_validation: bool = False) -> bool:
        """
        Navigate to the next step.

        Args:
            skip_validation: If True, skip validation

        Returns:
            True if navigation was successful
        """
        if not self.can_go_next():
            logger.debug(f"Cannot go next: already at last step ({self.current_index})")
            return False

        logger.info(f"Navigating: Step {self.current_index} → {self.current_index + 1}")

        # Validate current step
        if not skip_validation:
            current_step = self.get_current_step()
            if current_step:
                logger.debug(f"Validating step {self.current_index}...")
                validation_result = current_step.validate()
                if not validation_result.is_valid:
                    logger.warning(
                        f"Step {self.current_index} validation failed: {validation_result.errors}"
                    )
                    self.validation_failed.emit(validation_result)
                    return False

                logger.debug(f"Step {self.current_index} validated successfully")
                # Mark step as completed
                self.context.mark_step_completed(self.current_index)

                # Call on_next() hook if the step has it
                if hasattr(current_step, 'on_next') and callable(current_step.on_next):
                    logger.debug(f"Calling on_next() for step {self.current_index}")
                    current_step.on_next()

        # Move to next step
        result = self._navigate_to(self.current_index + 1)
        if result:
            logger.info(f"Successfully navigated to step {self.current_index}")
        return result

    def previous_step(self) -> bool:
        """Navigate to the previous step."""
        if not self.can_go_previous():
            logger.debug(f"Cannot go previous: already at first step ({self.current_index})")
            return False

        logger.info(f"Navigating back: Step {self.current_index} → {self.current_index - 1}")
        result = self._navigate_to(self.current_index - 1)
        if result:
            logger.info(f"Successfully navigated back to step {self.current_index}")
        return result

    def goto_step(self, index: int, skip_validation: bool = False) -> bool:
        """
        Navigate to a specific step.

        Args:
            index: Target step index
            skip_validation: If True, skip validation

        Returns:
            True if navigation was successful
        """
        if index < 0 or index >= len(self.steps):
            return False

        if index == self.current_index:
            return True

        # If going forward, validate current step
        if index > self.current_index and not skip_validation:
            current_step = self.get_current_step()
            if current_step:
                validation_result = current_step.validate()
                if not validation_result.is_valid:
                    self.validation_failed.emit(validation_result)
                    return False

        return self._navigate_to(index)

    def _navigate_to(self, new_index: int) -> bool:
        """
        Internal method to navigate to a step.

        Args:
            new_index: Target step index

        Returns:
            True if navigation was successful
        """
        if new_index < 0 or new_index >= len(self.steps):
            logger.error(f"Invalid step index: {new_index} (valid range: 0-{len(self.steps)-1})")
            return False

        old_index = self.current_index
        logger.debug(f"_navigate_to: {old_index} → {new_index}")

        # Hide current step
        current_step = self.get_current_step()
        if current_step:
            step_name = current_step.get_step_title()
            logger.debug(f"Hiding step {old_index}: {step_name}")
            current_step.on_hide()

        # Update index and context
        self.current_index = new_index
        self.context.current_step_index = new_index

        # Show new step
        new_step = self.get_current_step()
        if new_step:
            step_name = new_step.get_step_title()
            logger.debug(f"Showing step {new_index}: {step_name}")
            new_step.on_show()

        # Emit signals
        self.step_changed.emit(old_index, new_index)
        self.can_go_next_changed.emit(self.can_go_next())
        self.can_go_previous_changed.emit(self.can_go_previous())

        logger.info(f"Navigation complete: Step {new_index} is now active")
        return True

    def reset(self):
        """Reset navigator to first step."""
        self._navigate_to(0)

    def get_progress_percentage(self) -> float:
        """
        Get current progress as percentage.

        Returns:
            Progress percentage (0.0 to 100.0)
        """
        if len(self.steps) == 0:
            return 0.0
        return (self.current_index / (len(self.steps) - 1)) * 100.0

    def get_completed_steps_count(self) -> int:
        """Get number of completed steps."""
        return len(self.context.completed_steps)

    # =========================================================================
    # Signal Handlers
    # =========================================================================

    def _on_step_validation_changed(self, is_valid: bool):
        """Handle validation changed in a step."""
        # Update navigation button states
        self.can_go_next_changed.emit(self.can_go_next())

    def _on_step_data_changed(self, data: dict):
        """Handle data changed in a step."""
        # Update context (already done in BaseStep)
        pass
