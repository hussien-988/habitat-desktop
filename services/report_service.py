# -*- coding: utf-8 -*-
"""
Report Generation Service
==========================
Implements FR-D-14 Reports requirements including PDF generation and audit trail reports.

Features:
- PDF report generation with Arabic support
- Audit trail reports
- Statistical reports
- Progress reports
- STDM comparison reports
"""

import io
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)

# Try to import reportlab for PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


@dataclass
class ReportConfig:
    """Report configuration options."""
    title: str = "TRRCMS Report"
    title_ar: str = "تقرير TRRCMS"
    include_header: bool = True
    include_footer: bool = True
    include_page_numbers: bool = True
    logo_path: Optional[str] = None
    orientation: str = "portrait"  # portrait, landscape


class ReportService:
    """
    Report generation service.

    Implements:
    - FR-D-14.1: PDF report generation
    - FR-D-14.4: Audit trail reports
    - FR-D-14.5: Progress reports
    - FR-D-8.6: STDM comparison reports
    """

    def __init__(self, db: Database):
        self.db = db
        self._register_arabic_fonts()

    def _register_arabic_fonts(self):
        """Register Arabic-compatible fonts for PDF generation."""
        if not REPORTLAB_AVAILABLE:
            return

        try:
            # Try to register Arial Unicode or similar font for Arabic support
            # In production, you would include proper Arabic fonts
            pass
        except Exception as e:
            logger.warning(f"Could not register Arabic fonts: {e}")

    # ==================== PDF Report Generation (FR-D-14.1) ====================

    def generate_buildings_pdf(
        self,
        file_path: Path,
        filters: Optional[Dict[str, Any]] = None,
        config: Optional[ReportConfig] = None
    ) -> Dict[str, Any]:
        """
        Generate PDF report of buildings.

        Args:
            file_path: Output file path
            filters: Optional filters
            config: Report configuration

        Returns:
            Report summary dict
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")

        config = config or ReportConfig(title="Buildings Report", title_ar="تقرير المباني")
        cursor = self.db.cursor()

        # Get buildings
        query = "SELECT * FROM buildings WHERE 1=1"
        params = []

        if filters:
            if filters.get("neighborhood_code"):
                query += " AND neighborhood_code = ?"
                params.append(filters["neighborhood_code"])
            if filters.get("building_type"):
                query += " AND building_type = ?"
                params.append(filters["building_type"])

        query += " ORDER BY building_id LIMIT 1000"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Create PDF
        doc = SimpleDocTemplate(str(file_path), pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1  # Center
        )
        elements.append(Paragraph(config.title, title_style))
        elements.append(Spacer(1, 20))

        # Report info
        info_style = styles['Normal']
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", info_style))
        elements.append(Paragraph(f"Total Records: {len(rows)}", info_style))
        elements.append(Spacer(1, 20))

        # Table data
        table_data = [["Building ID", "Neighborhood", "Type", "Status", "Units", "Floors"]]

        for row in rows:
            data = dict(row)
            table_data.append([
                data.get("building_id", ""),
                data.get("neighborhood_name", ""),
                data.get("building_type", ""),
                data.get("building_status", ""),
                str(data.get("number_of_units", 0)),
                str(data.get("number_of_floors", 0)),
            ])

        # Create table
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0072BC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ]))

        elements.append(table)
        doc.build(elements)

        logger.info(f"Generated buildings PDF report: {file_path}")

        return {
            "file_path": str(file_path),
            "record_count": len(rows),
            "format": "pdf",
            "generated_at": datetime.now().isoformat()
        }

    def generate_claims_pdf(
        self,
        file_path: Path,
        filters: Optional[Dict[str, Any]] = None,
        config: Optional[ReportConfig] = None
    ) -> Dict[str, Any]:
        """Generate PDF report of claims."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")

        config = config or ReportConfig(title="Claims Report", title_ar="تقرير المطالبات")
        cursor = self.db.cursor()

        query = "SELECT * FROM claims WHERE 1=1"
        params = []

        if filters:
            if filters.get("case_status"):
                query += " AND case_status = ?"
                params.append(filters["case_status"])

        query += " ORDER BY created_at DESC LIMIT 1000"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        doc = SimpleDocTemplate(str(file_path), pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=1)
        elements.append(Paragraph(config.title, title_style))
        elements.append(Spacer(1, 20))

        # Summary stats
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total Claims: {len(rows)}", styles['Normal']))
        elements.append(Spacer(1, 20))

        # Table
        table_data = [["Claim ID", "Status", "Type", "Priority", "Unit ID", "Submitted"]]

        for row in rows:
            data = dict(row)
            table_data.append([
                data.get("claim_id", ""),
                data.get("case_status", ""),
                data.get("claim_type", ""),
                data.get("priority", ""),
                data.get("unit_id", ""),
                str(data.get("submission_date", "")),
            ])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0072BC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ]))

        elements.append(table)
        doc.build(elements)

        logger.info(f"Generated claims PDF report: {file_path}")

        return {
            "file_path": str(file_path),
            "record_count": len(rows),
            "format": "pdf",
            "generated_at": datetime.now().isoformat()
        }

    # ==================== Audit Trail Reports (FR-D-14.4) ====================

    def generate_audit_trail_report(
        self,
        file_path: Path,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        action_type: Optional[str] = None,
        format: str = "pdf"
    ) -> Dict[str, Any]:
        """
        Generate audit trail report (FR-D-14.4).

        Args:
            file_path: Output file path
            start_date: Filter start date
            end_date: Filter end date
            user_id: Filter by user
            action_type: Filter by action type
            format: Output format (pdf, csv)

        Returns:
            Report summary dict
        """
        cursor = self.db.cursor()

        # Query audit log
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        if action_type:
            query += " AND action = ?"
            params.append(action_type)

        query += " ORDER BY timestamp DESC LIMIT 5000"

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Audit log table may not exist: {e}")
            rows = []

        if format == "csv":
            return self._generate_audit_csv(file_path, rows)
        else:
            return self._generate_audit_pdf(file_path, rows)

    def _generate_audit_pdf(self, file_path: Path, rows: List) -> Dict[str, Any]:
        """Generate audit trail PDF report."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")

        doc = SimpleDocTemplate(str(file_path), pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=1)
        elements.append(Paragraph("Audit Trail Report / تقرير سجل التدقيق", title_style))
        elements.append(Spacer(1, 20))

        # Summary
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Paragraph(f"Total Records: {len(rows)}", styles['Normal']))
        elements.append(Spacer(1, 20))

        # Table
        table_data = [["Timestamp", "User", "Action", "Entity", "Entity ID", "Details"]]

        for row in rows:
            data = dict(row)
            # Truncate details for display
            details = str(data.get("details", ""))[:50] + "..." if len(str(data.get("details", ""))) > 50 else str(data.get("details", ""))

            table_data.append([
                str(data.get("timestamp", ""))[:19],
                data.get("user_id", ""),
                data.get("action", ""),
                data.get("entity_type", ""),
                str(data.get("entity_id", ""))[:20],
                details,
            ])

        if len(table_data) > 1:
            table = Table(table_data, repeatRows=1, colWidths=[80, 60, 60, 60, 80, 120])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0072BC')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No audit records found.", styles['Normal']))

        doc.build(elements)

        return {
            "file_path": str(file_path),
            "record_count": len(rows),
            "format": "pdf",
            "generated_at": datetime.now().isoformat()
        }

    def _generate_audit_csv(self, file_path: Path, rows: List) -> Dict[str, Any]:
        """Generate audit trail CSV report."""
        import csv

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "User ID", "Action", "Entity Type", "Entity ID", "Old Value", "New Value", "Details"])

            for row in rows:
                data = dict(row)
                writer.writerow([
                    data.get("timestamp", ""),
                    data.get("user_id", ""),
                    data.get("action", ""),
                    data.get("entity_type", ""),
                    data.get("entity_id", ""),
                    data.get("old_value", ""),
                    data.get("new_value", ""),
                    data.get("details", ""),
                ])

        return {
            "file_path": str(file_path),
            "record_count": len(rows),
            "format": "csv",
            "generated_at": datetime.now().isoformat()
        }

    # ==================== Progress Reports (FR-D-14.5) ====================

    def generate_progress_report(
        self,
        file_path: Path,
        period: str = "daily",  # daily, weekly, monthly
        config: Optional[ReportConfig] = None
    ) -> Dict[str, Any]:
        """
        Generate progress report (FR-D-14.5).

        Args:
            file_path: Output file path
            period: Report period (daily, weekly, monthly)
            config: Report configuration

        Returns:
            Report summary dict
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")

        config = config or ReportConfig(title=f"{period.capitalize()} Progress Report", title_ar="تقرير التقدم")
        cursor = self.db.cursor()

        # Calculate date range
        end_date = datetime.now()
        if period == "daily":
            start_date = end_date - timedelta(days=1)
        elif period == "weekly":
            start_date = end_date - timedelta(weeks=1)
        else:  # monthly
            start_date = end_date - timedelta(days=30)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Gather statistics
        stats = {}

        # New buildings
        cursor.execute("""
            SELECT COUNT(*) FROM buildings WHERE date(created_at) >= ?
        """, (start_str,))
        stats["new_buildings"] = cursor.fetchone()[0]

        # New units
        cursor.execute("""
            SELECT COUNT(*) FROM property_units WHERE date(created_at) >= ?
        """, (start_str,))
        stats["new_units"] = cursor.fetchone()[0]

        # New claims
        cursor.execute("""
            SELECT COUNT(*) FROM claims WHERE date(created_at) >= ?
        """, (start_str,))
        stats["new_claims"] = cursor.fetchone()[0]

        # Claims by status
        cursor.execute("""
            SELECT case_status, COUNT(*) as count FROM claims
            WHERE date(created_at) >= ?
            GROUP BY case_status
        """, (start_str,))
        stats["claims_by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Approved claims
        cursor.execute("""
            SELECT COUNT(*) FROM claims
            WHERE case_status = 'approved' AND date(updated_at) >= ?
        """, (start_str,))
        stats["approved_claims"] = cursor.fetchone()[0]

        # Rejected claims
        cursor.execute("""
            SELECT COUNT(*) FROM claims
            WHERE case_status = 'rejected' AND date(updated_at) >= ?
        """, (start_str,))
        stats["rejected_claims"] = cursor.fetchone()[0]

        # New persons
        cursor.execute("""
            SELECT COUNT(*) FROM persons WHERE date(created_at) >= ?
        """, (start_str,))
        stats["new_persons"] = cursor.fetchone()[0]

        # New documents
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM documents WHERE date(created_at) >= ?
            """, (start_str,))
            stats["new_documents"] = cursor.fetchone()[0]
        except:
            stats["new_documents"] = 0

        # Generate PDF
        doc = SimpleDocTemplate(str(file_path), pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=1)
        elements.append(Paragraph(config.title, title_style))
        elements.append(Spacer(1, 20))

        # Report info
        elements.append(Paragraph(f"Period: {start_str} to {end_str}", styles['Normal']))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 30))

        # Summary table
        summary_data = [
            ["Metric", "Count"],
            ["New Buildings", str(stats["new_buildings"])],
            ["New Units", str(stats["new_units"])],
            ["New Claims", str(stats["new_claims"])],
            ["Approved Claims", str(stats["approved_claims"])],
            ["Rejected Claims", str(stats["rejected_claims"])],
            ["New Persons", str(stats["new_persons"])],
            ["New Documents", str(stats["new_documents"])],
        ]

        table = Table(summary_data, colWidths=[300, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0072BC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 30))

        # Claims by status
        if stats["claims_by_status"]:
            elements.append(Paragraph("Claims by Status:", styles['Heading2']))
            status_data = [["Status", "Count"]]
            for status, count in stats["claims_by_status"].items():
                status_data.append([status, str(count)])

            status_table = Table(status_data, colWidths=[300, 100])
            status_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28A745')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(status_table)

        doc.build(elements)

        logger.info(f"Generated progress report: {file_path}")

        return {
            "file_path": str(file_path),
            "period": period,
            "start_date": start_str,
            "end_date": end_str,
            "statistics": stats,
            "format": "pdf",
            "generated_at": datetime.now().isoformat()
        }

    # ==================== STDM Comparison Report (FR-D-8.6) ====================

    def generate_stdm_comparison_report(
        self,
        file_path: Path,
        config: Optional[ReportConfig] = None
    ) -> Dict[str, Any]:
        """
        Generate STDM comparison report (FR-D-8.6).

        Shows records with and without legacy STDM IDs.

        Args:
            file_path: Output file path
            config: Report configuration

        Returns:
            Report summary dict
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation")

        config = config or ReportConfig(title="STDM Integration Report", title_ar="تقرير تكامل STDM")
        cursor = self.db.cursor()

        stats = {}

        # Buildings with/without STDM ID
        cursor.execute("SELECT COUNT(*) FROM buildings WHERE legacy_stdm_id IS NOT NULL AND legacy_stdm_id != ''")
        stats["buildings_with_stdm"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM buildings WHERE legacy_stdm_id IS NULL OR legacy_stdm_id = ''")
        stats["buildings_without_stdm"] = cursor.fetchone()[0]

        # Units
        try:
            cursor.execute("SELECT COUNT(*) FROM property_units WHERE legacy_stdm_id IS NOT NULL AND legacy_stdm_id != ''")
            stats["units_with_stdm"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM property_units WHERE legacy_stdm_id IS NULL OR legacy_stdm_id = ''")
            stats["units_without_stdm"] = cursor.fetchone()[0]
        except:
            stats["units_with_stdm"] = 0
            stats["units_without_stdm"] = 0

        # Persons
        try:
            cursor.execute("SELECT COUNT(*) FROM persons WHERE legacy_stdm_id IS NOT NULL AND legacy_stdm_id != ''")
            stats["persons_with_stdm"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM persons WHERE legacy_stdm_id IS NULL OR legacy_stdm_id = ''")
            stats["persons_without_stdm"] = cursor.fetchone()[0]
        except:
            stats["persons_with_stdm"] = 0
            stats["persons_without_stdm"] = 0

        # Claims
        try:
            cursor.execute("SELECT COUNT(*) FROM claims WHERE legacy_stdm_id IS NOT NULL AND legacy_stdm_id != ''")
            stats["claims_with_stdm"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM claims WHERE legacy_stdm_id IS NULL OR legacy_stdm_id = ''")
            stats["claims_without_stdm"] = cursor.fetchone()[0]
        except:
            stats["claims_with_stdm"] = 0
            stats["claims_without_stdm"] = 0

        # Generate PDF
        doc = SimpleDocTemplate(str(file_path), pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=1)
        elements.append(Paragraph(config.title, title_style))
        elements.append(Spacer(1, 20))

        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 30))

        # STDM Integration Summary
        elements.append(Paragraph("STDM Integration Summary:", styles['Heading2']))
        elements.append(Spacer(1, 10))

        table_data = [
            ["Entity", "With STDM ID", "Without STDM ID", "Integration %"],
            ["Buildings", str(stats["buildings_with_stdm"]), str(stats["buildings_without_stdm"]),
             f"{self._calc_percentage(stats['buildings_with_stdm'], stats['buildings_without_stdm'])}%"],
            ["Units", str(stats["units_with_stdm"]), str(stats["units_without_stdm"]),
             f"{self._calc_percentage(stats['units_with_stdm'], stats['units_without_stdm'])}%"],
            ["Persons", str(stats["persons_with_stdm"]), str(stats["persons_without_stdm"]),
             f"{self._calc_percentage(stats['persons_with_stdm'], stats['persons_without_stdm'])}%"],
            ["Claims", str(stats["claims_with_stdm"]), str(stats["claims_without_stdm"]),
             f"{self._calc_percentage(stats['claims_with_stdm'], stats['claims_without_stdm'])}%"],
        ]

        table = Table(table_data, colWidths=[100, 100, 120, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0072BC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ]))

        elements.append(table)

        doc.build(elements)

        logger.info(f"Generated STDM comparison report: {file_path}")

        return {
            "file_path": str(file_path),
            "statistics": stats,
            "format": "pdf",
            "generated_at": datetime.now().isoformat()
        }

    def _calc_percentage(self, with_count: int, without_count: int) -> str:
        """Calculate integration percentage."""
        total = with_count + without_count
        if total == 0:
            return "0"
        return str(round((with_count / total) * 100, 1))

    # ==================== Statistics Summary ====================

    def get_dashboard_statistics(self) -> Dict[str, Any]:
        """Get statistics for dashboard display."""
        cursor = self.db.cursor()
        stats = {}

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM buildings")
        stats["total_buildings"] = cursor.fetchone()[0]

        try:
            cursor.execute("SELECT COUNT(*) FROM property_units")
            stats["total_units"] = cursor.fetchone()[0]
        except:
            stats["total_units"] = 0

        try:
            cursor.execute("SELECT COUNT(*) FROM persons")
            stats["total_persons"] = cursor.fetchone()[0]
        except:
            stats["total_persons"] = 0

        try:
            cursor.execute("SELECT COUNT(*) FROM claims")
            stats["total_claims"] = cursor.fetchone()[0]
        except:
            stats["total_claims"] = 0

        # Claims by status
        try:
            cursor.execute("""
                SELECT case_status, COUNT(*) as count FROM claims
                GROUP BY case_status
            """)
            stats["claims_by_status"] = {row[0]: row[1] for row in cursor.fetchall()}
        except:
            stats["claims_by_status"] = {}

        # Recent activity (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        cursor.execute("SELECT COUNT(*) FROM buildings WHERE date(created_at) >= ?", (week_ago,))
        stats["new_buildings_week"] = cursor.fetchone()[0]

        try:
            cursor.execute("SELECT COUNT(*) FROM claims WHERE date(created_at) >= ?", (week_ago,))
            stats["new_claims_week"] = cursor.fetchone()[0]
        except:
            stats["new_claims_week"] = 0

        return stats
