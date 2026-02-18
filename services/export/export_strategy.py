# -*- coding: utf-8 -*-
"""
Export Strategy Pattern - Abstract interface for export strategies.

Provides a pluggable architecture for different export formats without
modifying existing export services.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import csv


class ExportStrategy(ABC):
    """
    Abstract base class for export strategies.

    Each strategy implements a specific export format (CSV, Excel, PDF, etc.)
    """

    @abstractmethod
    def export(self, data: List[Dict[str, Any]], file_path: str, **kwargs) -> bool:
        """
        Export data to a file in the strategy's format.

        Args:
            data: List of dictionaries representing rows to export
            file_path: Target file path for export
            **kwargs: Additional format-specific options

        Returns:
            True if export succeeded, False otherwise
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get the file extension for this export format.

        Returns:
            File extension including the dot (e.g., '.csv')
        """
        pass


class CSVExportStrategy(ExportStrategy):
    """Strategy for exporting data to CSV format."""

    def export(self, data: List[Dict[str, Any]], file_path: str, **kwargs) -> bool:
        """
        Export data to CSV file.

        Args:
            data: List of dictionaries to export
            file_path: Target CSV file path
            **kwargs: Optional parameters:
                - delimiter: CSV delimiter (default: ',')
                - encoding: File encoding (default: 'utf-8-sig')
                - columns: List of column names to export (default: all keys from first row)

        Returns:
            True if export succeeded, False otherwise
        """
        if not data:
            return False

        try:
            delimiter = kwargs.get('delimiter', ',')
            encoding = kwargs.get('encoding', 'utf-8-sig')
            columns = kwargs.get('columns', list(data[0].keys()) if data else [])

            with open(file_path, 'w', newline='', encoding=encoding) as f:
                writer = csv.DictWriter(f, fieldnames=columns, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(data)

            return True

        except Exception as e:
            print(f"CSV export failed: {e}")
            return False

    def get_file_extension(self) -> str:
        """Return CSV file extension."""
        return '.csv'
