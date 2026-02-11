# -*- coding: utf-8 -*-
"""Custom exceptions for the application."""


class ApiException(Exception):
    """Exception raised for API errors."""

    def __init__(self, message: str, status_code: int = None,
                 response_data: dict = None, context: str = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.context = context

    def __str__(self):
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class ValidationException(Exception):
    """Exception raised for validation errors."""

    def __init__(self, message: str, field: str = None,
                 errors: list = None, context: str = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.errors = errors or []
        self.context = context


class NetworkException(Exception):
    """Exception raised for network/connection errors."""

    def __init__(self, message: str, original_error: Exception = None,
                 context: str = None):
        super().__init__(message)
        self.message = message
        self.original_error = original_error
        self.context = context
