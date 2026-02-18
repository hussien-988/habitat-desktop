# -*- coding: utf-8 -*-
"""
Export Manager - Manages and dispatches export strategies.

Provides a central point for registering and executing different export formats.
"""

from typing import Dict, List, Any, Optional
from .export_strategy import ExportStrategy, CSVExportStrategy


class ExportManager:
    """
    Manages export strategies and provides format selection.

    This class acts as a registry for different export strategies and
    provides a unified interface for exporting data in various formats.
    """

    def __init__(self):
        """Initialize the export manager with default strategies."""
        self._strategies: Dict[str, ExportStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Register built-in export strategies."""
        self.register_strategy('csv', CSVExportStrategy())

    def register_strategy(self, format_name: str, strategy: ExportStrategy):
        """
        Register an export strategy for a specific format.

        Args:
            format_name: Format identifier (e.g., 'csv', 'excel', 'pdf')
            strategy: ExportStrategy implementation
        """
        self._strategies[format_name.lower()] = strategy

    def get_strategy(self, format_name: str) -> Optional[ExportStrategy]:
        """
        Get a registered export strategy by format name.

        Args:
            format_name: Format identifier

        Returns:
            ExportStrategy instance or None if not found
        """
        return self._strategies.get(format_name.lower())

    def export(self, data: List[Dict[str, Any]], file_path: str,
               format_name: str = 'csv', **kwargs) -> bool:
        """
        Export data using the specified format strategy.

        Args:
            data: List of dictionaries to export
            file_path: Target file path
            format_name: Export format identifier (default: 'csv')
            **kwargs: Format-specific options passed to strategy

        Returns:
            True if export succeeded, False otherwise
        """
        strategy = self.get_strategy(format_name)
        if not strategy:
            print(f"Export format '{format_name}' not registered")
            return False

        return strategy.export(data, file_path, **kwargs)

    def get_available_formats(self) -> List[str]:
        """
        Get list of registered export formats.

        Returns:
            List of format names
        """
        return list(self._strategies.keys())

    def get_file_extension(self, format_name: str) -> Optional[str]:
        """
        Get file extension for a specific format.

        Args:
            format_name: Format identifier

        Returns:
            File extension (e.g., '.csv') or None if format not found
        """
        strategy = self.get_strategy(format_name)
        return strategy.get_file_extension() if strategy else None
