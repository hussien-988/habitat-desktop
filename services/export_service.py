# -*- coding: utf-8 -*-
"""
Export service for CSV and Excel exports.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from models.building import Building
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from utils.logger import get_logger

logger = get_logger(__name__)


class ExportService:
    """Service for exporting data to various formats."""

    def __init__(self, db: Database):
        self.db = db
        self.building_repo = BuildingRepository(db)

    def export_buildings_csv(
        self,
        file_path: Path,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Export buildings to CSV file.

        Args:
            file_path: Output file path
            filters: Optional filters (neighborhood, type, status)
            columns: Optional list of columns to include

        Returns:
            Export summary dict
        """
        # Default columns
        if columns is None:
            columns = [
                "building_id",
                "neighborhood_name",
                "neighborhood_name_ar",
                "building_type",
                "building_status",
                "number_of_units",
                "number_of_apartments",
                "number_of_shops",
                "number_of_floors",
                "latitude",
                "longitude",
            ]

        # Get buildings with filters
        buildings = self.building_repo.search(
            neighborhood_code=filters.get("neighborhood_code") if filters else None,
            building_type=filters.get("building_type") if filters else None,
            building_status=filters.get("building_status") if filters else None,
            limit=10000  # Max export
        )

        # Write CSV
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()

            for building in buildings:
                row = building.to_dict()
                writer.writerow({col: row.get(col, "") for col in columns})

        logger.info(f"Exported {len(buildings)} buildings to {file_path}")

        return {
            "file_path": str(file_path),
            "record_count": len(buildings),
            "format": "csv",
            "exported_at": datetime.now().isoformat()
        }

    def export_buildings_excel(
        self,
        file_path: Path,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Export buildings to Excel file.

        Args:
            file_path: Output file path
            filters: Optional filters

        Returns:
            Export summary dict
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            logger.error("openpyxl not installed")
            raise ImportError("openpyxl is required for Excel export")

        # Get buildings
        buildings = self.building_repo.search(
            neighborhood_code=filters.get("neighborhood_code") if filters else None,
            building_type=filters.get("building_type") if filters else None,
            building_status=filters.get("building_status") if filters else None,
            limit=10000
        )

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Buildings"

        # Define styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0072BC", end_color="0072BC", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        # Headers
        headers = [
            "Building ID", "Neighborhood", "Neighborhood (AR)",
            "Type", "Status", "Units", "Apartments", "Shops",
            "Floors", "Latitude", "Longitude"
        ]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Data rows
        for row_num, building in enumerate(buildings, 2):
            data = [
                building.building_id,
                building.neighborhood_name,
                building.neighborhood_name_ar,
                building.building_type_display,
                building.building_status_display,
                building.number_of_units,
                building.number_of_apartments,
                building.number_of_shops,
                building.number_of_floors,
                building.latitude,
                building.longitude,
            ]

            for col, value in enumerate(data, 1):
                cell = ws.cell(row=row_num, column=col, value=value)
                cell.border = thin_border

        # Adjust column widths
        column_widths = [25, 15, 15, 12, 12, 8, 10, 8, 8, 12, 12]
        for col, width in enumerate(column_widths, 1):
            ws.column_dimensions[chr(64 + col)].width = width

        # Save
        wb.save(file_path)
        logger.info(f"Exported {len(buildings)} buildings to {file_path}")

        return {
            "file_path": str(file_path),
            "record_count": len(buildings),
            "format": "xlsx",
            "exported_at": datetime.now().isoformat()
        }

    def get_export_preview(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get preview of data to be exported."""
        buildings = self.building_repo.search(
            neighborhood_code=filters.get("neighborhood_code") if filters else None,
            building_type=filters.get("building_type") if filters else None,
            building_status=filters.get("building_status") if filters else None,
            limit=limit
        )

        return [b.to_dict() for b in buildings]

    def get_export_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get count of records to be exported."""
        return self.building_repo.count(filters)
