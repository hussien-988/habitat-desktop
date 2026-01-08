# -*- coding: utf-8 -*-
"""
Base Controller
===============
Abstract base class for all controllers in TRRCMS.

Provides common functionality and patterns for controllers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from PyQt5.QtCore import QObject, pyqtSignal

from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class OperationResult(Generic[T]):
    """Result of a controller operation."""
    success: bool
    data: Optional[T] = None
    message: str = ""
    message_ar: str = ""
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @classmethod
    def ok(cls, data: T = None, message: str = "", message_ar: str = "") -> 'OperationResult[T]':
        """Create a successful result."""
        return cls(success=True, data=data, message=message, message_ar=message_ar)

    @classmethod
    def fail(cls, message: str, message_ar: str = "", errors: List[str] = None) -> 'OperationResult[T]':
        """Create a failed result."""
        return cls(success=False, message=message, message_ar=message_ar, errors=errors or [])


class BaseController(QObject):
    """
    Abstract base controller class.

    Provides:
    - Common signal patterns
    - Error handling
    - Logging
    - State management
    """

    # Common signals
    operation_started = pyqtSignal(str)  # operation name
    operation_completed = pyqtSignal(str, bool)  # operation name, success
    operation_error = pyqtSignal(str, str)  # operation name, error message
    data_changed = pyqtSignal()
    loading_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_loading = False
        self._last_error = ""
        self._callbacks: Dict[str, List[Callable]] = {}

    @property
    def is_loading(self) -> bool:
        """Check if controller is performing an operation."""
        return self._is_loading

    @property
    def last_error(self) -> str:
        """Get last error message."""
        return self._last_error

    def _set_loading(self, loading: bool):
        """Set loading state and emit signal."""
        self._is_loading = loading
        self.loading_changed.emit(loading)

    def _set_error(self, error: str):
        """Set error message."""
        self._last_error = error
        if error:
            logger.error(f"{self.__class__.__name__}: {error}")

    def _log_operation(self, operation: str, **kwargs):
        """Log an operation."""
        logger.info(f"{self.__class__.__name__}.{operation}: {kwargs}")

    def _emit_started(self, operation: str):
        """Emit operation started signal."""
        self.operation_started.emit(operation)
        self._set_loading(True)

    def _emit_completed(self, operation: str, success: bool):
        """Emit operation completed signal."""
        self.operation_completed.emit(operation, success)
        self._set_loading(False)
        if success:
            self.data_changed.emit()

    def _emit_error(self, operation: str, error: str):
        """Emit operation error signal."""
        self._set_error(error)
        self.operation_error.emit(operation, error)
        self._set_loading(False)

    def register_callback(self, event: str, callback: Callable):
        """Register a callback for an event."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def unregister_callback(self, event: str, callback: Callable):
        """Unregister a callback."""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _trigger_callbacks(self, event: str, *args, **kwargs):
        """Trigger callbacks for an event."""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in callback for {event}: {e}")

    def execute_with_error_handling(
        self,
        operation: str,
        func: Callable,
        *args,
        **kwargs
    ) -> OperationResult:
        """Execute a function with standard error handling."""
        try:
            self._emit_started(operation)
            result = func(*args, **kwargs)
            self._emit_completed(operation, True)
            return OperationResult.ok(data=result)
        except Exception as e:
            error_msg = str(e)
            self._emit_error(operation, error_msg)
            return OperationResult.fail(message=error_msg)
