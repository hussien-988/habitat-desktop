# -*- coding: utf-8 -*-
"""
Error Boundary for Wizard Steps.
"""

from typing import Optional, Callable
from functools import wraps
import traceback

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, QObject

from utils.logger import get_logger
from ui.error_handler import ErrorHandler
from services.translation_manager import tr

logger = get_logger(__name__)


class ErrorBoundary(QObject):
    """Error boundary for wizard steps."""

    error_occurred = pyqtSignal(str, str)  # error_type, error_message

    def __init__(self, step_name: str, parent: Optional[QWidget] = None):
        """Initialize error boundary."""
        super().__init__(parent)
        self.step_name = step_name
        self.parent_widget = parent
        self.error_count = 0
        self.last_error: Optional[Exception] = None

    def protect(self, func: Callable, operation_name: str = "operation") -> Callable:
        """Wrap a function with error boundary."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                self._handle_error(e, operation_name)
                return None

        return wrapper

    def _handle_error(self, error: Exception, operation: str):
        """Handle an error that occurred in a step."""
        self.error_count += 1
        self.last_error = error

        # Log error with full traceback
        error_msg = f"Error in {self.step_name} during {operation}: {str(error)}"
        logger.error(error_msg, exc_info=True)

        # Emit signal
        error_type = type(error).__name__
        self.error_occurred.emit(error_type, str(error))

        # Show user-friendly error dialog
        self._show_error_dialog(error, operation)

    def _show_error_dialog(self, error: Exception, operation: str):
        """Show error dialog to user."""
        if not self.parent_widget:
            return

        error_title = tr("error_boundary.step_error", step_name=self.step_name)
        error_message = tr(
            "error_boundary.operation_error",
            operation=operation,
            error_type=type(error).__name__,
            error_msg=str(error),
        )

        ErrorHandler.show_error(
            self.parent_widget,
            error_message,
            error_title
        )

    def get_error_summary(self) -> str:
        """Get summary of errors that occurred."""
        if self.error_count == 0:
            return "No errors"

        return (
            f"Step: {self.step_name}\n"
            f"Errors: {self.error_count}\n"
            f"Last error: {type(self.last_error).__name__} - {str(self.last_error)}"
        )


def with_error_boundary(step_name: str, operation_name: str = "operation"):
    """Decorator to add error boundary to a method."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)

            except Exception as e:
                # Log error
                logger.error(
                    f"Error in {step_name} during {operation_name}: {str(e)}",
                    exc_info=True
                )

                # Show error to user if step has parent
                parent = getattr(self, 'parent', None)
                if parent and callable(getattr(parent, 'window', None)):
                    parent_window = parent.window()
                else:
                    parent_window = None

                if parent_window:
                    from services.translation_manager import tr as _tr
                    ErrorHandler.show_error(
                        parent_window,
                        _tr("error_boundary.operation_error_simple", operation=operation_name, error_msg=str(e)),
                        _tr("error_boundary.step_error", step_name=step_name),
                    )

                # Re-raise if critical
                if isinstance(e, (MemoryError, KeyboardInterrupt)):
                    raise

                return None

        return wrapper
    return decorator


class StepErrorRecovery:
    """Provides error recovery strategies for wizard steps."""

    @staticmethod
    def should_retry(error_count: int, max_retries: int = 3) -> bool:
        """Check if operation should be retried."""
        return error_count < max_retries

    @staticmethod
    def get_recovery_options(error: Exception) -> list:
        """Get available recovery options for an error."""
        from services.translation_manager import tr as _tr
        # Network errors - retry makes sense
        if "Network" in type(error).__name__ or "Connection" in type(error).__name__:
            return [
                ("retry", _tr("error_boundary.retry")),
                ("skip", _tr("error_boundary.skip")),
                ("exit", _tr("error_boundary.exit")),
            ]

        # Validation errors - usually require user action
        if "Validation" in type(error).__name__:
            return [
                ("reset", _tr("error_boundary.reset")),
                ("exit", _tr("error_boundary.exit")),
            ]

        # Default options
        return [
            ("retry", _tr("error_boundary.retry")),
            ("reset", _tr("error_boundary.reset")),
            ("exit", _tr("error_boundary.exit")),
        ]
