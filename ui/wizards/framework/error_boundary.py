# -*- coding: utf-8 -*-
"""
Error Boundary for Wizard Steps.

Provides graceful error handling and recovery for wizard steps:
- Catches exceptions during step lifecycle
- Logs errors with context
- Shows user-friendly error messages
- Allows step retry or wizard exit
"""

from typing import Optional, Callable
from functools import wraps
import traceback

from PyQt5.QtWidgets import QMessageBox, QWidget
from PyQt5.QtCore import pyqtSignal, QObject

from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorBoundary(QObject):
    """
    Error boundary for wizard steps.

    Wraps step methods with error handling to prevent crashes.
    """

    error_occurred = pyqtSignal(str, str)  # error_type, error_message

    def __init__(self, step_name: str, parent: Optional[QWidget] = None):
        """
        Initialize error boundary.

        Args:
            step_name: Name of the step being protected
            parent: Parent widget for error dialogs
        """
        super().__init__(parent)
        self.step_name = step_name
        self.parent_widget = parent
        self.error_count = 0
        self.last_error: Optional[Exception] = None

    def protect(self, func: Callable, operation_name: str = "operation") -> Callable:
        """
        Wrap a function with error boundary.

        Args:
            func: Function to protect
            operation_name: Name of operation for logging

        Returns:
            Wrapped function that catches errors
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                self._handle_error(e, operation_name)
                return None

        return wrapper

    def _handle_error(self, error: Exception, operation: str):
        """
        Handle an error that occurred in a step.

        Args:
            error: The exception that was raised
            operation: Name of the operation that failed
        """
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

        error_title = f"خطأ في {self.step_name}"
        error_message = (
            f"حدث خطأ أثناء {operation}:\n\n"
            f"{type(error).__name__}: {str(error)}\n\n"
            f"يمكنك المحاولة مرة أخرى أو الاتصال بالدعم الفني."
        )

        QMessageBox.critical(
            self.parent_widget,
            error_title,
            error_message,
            QMessageBox.Ok
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
    """
    Decorator to add error boundary to a method.

    Usage:
        @with_error_boundary("Building Selection", "loading buildings")
        def load_buildings(self):
            # ... method code ...

    Args:
        step_name: Name of the step
        operation_name: Name of the operation

    Returns:
        Decorator function
    """
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
                    QMessageBox.critical(
                        parent_window,
                        f"خطأ في {step_name}",
                        f"حدث خطأ أثناء {operation_name}:\n\n{str(e)}\n\n"
                        f"يرجى المحاولة مرة أخرى أو الاتصال بالدعم الفني.",
                        QMessageBox.Ok
                    )

                # Re-raise if critical
                if isinstance(e, (MemoryError, KeyboardInterrupt)):
                    raise

                return None

        return wrapper
    return decorator


class StepErrorRecovery:
    """
    Provides error recovery strategies for wizard steps.

    Strategies:
    - Retry: Retry the failed operation
    - Skip: Skip the current step
    - Reset: Reset step to initial state
    - Exit: Exit the wizard
    """

    @staticmethod
    def should_retry(error_count: int, max_retries: int = 3) -> bool:
        """Check if operation should be retried."""
        return error_count < max_retries

    @staticmethod
    def get_recovery_options(error: Exception) -> list:
        """
        Get available recovery options for an error.

        Returns:
            List of (option_name, option_label) tuples
        """
        # Network errors - retry makes sense
        if "Network" in type(error).__name__ or "Connection" in type(error).__name__:
            return [
                ("retry", "إعادة المحاولة"),
                ("skip", "تخطي"),
                ("exit", "خروج")
            ]

        # Validation errors - usually require user action
        if "Validation" in type(error).__name__:
            return [
                ("reset", "إعادة تعيين"),
                ("exit", "خروج")
            ]

        # Default options
        return [
            ("retry", "إعادة المحاولة"),
            ("reset", "إعادة تعيين"),
            ("exit", "خروج")
        ]
