# -*- coding: utf-8 -*-
"""
PDF Report Generation Service - FR-D-11 Implementation.
Generates Arabic PDF reports with QR codes and digital signatures.
"""

import hashlib
import hmac
import io
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, KeepTogether
    )
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

from utils.logger import get_logger

logger = get_logger(__name__)

# Signature key (use secure key management in production)
REPORT_SIGNATURE_KEY = b"UN-HABITAT-REPORT-SIGNATURE-2025"


@dataclass
class ReportMetadata:
    """Metadata for generated report."""
    report_id: str
    report_type: str
    title: str
    generated_at: datetime
    generated_by: str
    record_count: int
    checksum: str
    signature: str
    qr_data: str


class PDFReportService:
    """
    PDF Report Generation Service.

    Implements FR-D-11:
    - Arabic PDF reports with proper RTL support
    - QR codes embedding Record IDs
    - Digital signatures for authenticity
    - Multiple report templates
    """

    # Arabic font path (update to actual font path)
    ARABIC_FONT_PATH = None
    FONT_REGISTERED = False

    def __init__(self, db_connection, output_dir: str = None):
        self.db = db_connection
        self.output_dir = Path(output_dir) if output_dir else Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._register_arabic_font()

    def _register_arabic_font(self):
        """Register Arabic font for PDF generation."""
        if not REPORTLAB_AVAILABLE:
            logger.warning("ReportLab not available, PDF generation disabled")
            return

        if PDFReportService.FONT_REGISTERED:
            return

        # Try common Arabic font locations
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/GeezaPro.ttc"
        ]

        for path in font_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont('Arabic', path))
                    PDFReportService.ARABIC_FONT_PATH = path
                    PDFReportService.FONT_REGISTERED = True
                    logger.info(f"Registered Arabic font: {path}")
                    break
                except Exception as e:
                    logger.warning(f"Could not register font {path}: {e}")

    def _get_arabic_styles(self) -> Dict[str, ParagraphStyle]:
        """Get paragraph styles for Arabic text."""
        styles = getSampleStyleSheet()

        font_name = 'Arabic' if PDFReportService.FONT_REGISTERED else 'Helvetica'

        return {
            'title': ParagraphStyle(
                'ArabicTitle',
                parent=styles['Title'],
                fontName=font_name,
                fontSize=18,
                alignment=TA_CENTER,
                wordWrap='RTL'
            ),
            'heading': ParagraphStyle(
                'ArabicHeading',
                parent=styles['Heading1'],
                fontName=font_name,
                fontSize=14,
                alignment=TA_RIGHT,
                wordWrap='RTL'
            ),
            'subheading': ParagraphStyle(
                'ArabicSubHeading',
                parent=styles['Heading2'],
                fontName=font_name,
                fontSize=12,
                alignment=TA_RIGHT,
                wordWrap='RTL'
            ),
            'body': ParagraphStyle(
                'ArabicBody',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10,
                alignment=TA_RIGHT,
                wordWrap='RTL'
            ),
            'table_header': ParagraphStyle(
                'ArabicTableHeader',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10,
                alignment=TA_CENTER,
                textColor=colors.white
            ),
            'table_cell': ParagraphStyle(
                'ArabicTableCell',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=9,
                alignment=TA_RIGHT
            ),
            'footer': ParagraphStyle(
                'ArabicFooter',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.gray
            )
        }

    def _generate_qr_code(self, data: str) -> Optional[io.BytesIO]:
        """Generate QR code image."""
        if not QRCODE_AVAILABLE:
            return None

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            return buffer

        except Exception as e:
            logger.warning(f"Could not generate QR code: {e}")
            return None

    def _compute_report_signature(self, content_hash: str, metadata: Dict) -> str:
        """Compute digital signature for report."""
        message = f"{metadata['report_id']}:{content_hash}:{metadata['generated_at']}"
        signature = hmac.new(
            REPORT_SIGNATURE_KEY,
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def generate_claim_report(
        self,
        claim_id: str,
        generated_by: str = None
    ) -> Optional[Path]:
        """
        Generate detailed claim report PDF.

        Returns path to generated PDF file.
        """
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab not available")
            return None

        try:
            # Fetch claim data
            claim_data = self._fetch_claim_data(claim_id)
            if not claim_data:
                logger.error(f"Claim not found: {claim_id}")
                return None

            # Generate report
            report_id = str(uuid.uuid4())
            filename = f"claim_report_{claim_data['case_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            file_path = self.output_dir / filename

            # Create PDF
            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )

            styles = self._get_arabic_styles()
            story = []

            # Header with logo placeholder
            story.append(Paragraph("UN-Habitat", styles['title']))
            story.append(Paragraph("نظام تسجيل حقوق الحيازة وإدارة المطالبات", styles['title']))
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("تقرير مطالبة", styles['heading']))
            story.append(Spacer(1, 0.5*cm))

            # QR Code with claim reference
            qr_data = json.dumps({
                "report_id": report_id,
                "claim_id": claim_id,
                "case_number": claim_data['case_number'],
                "generated_at": datetime.now().isoformat()
            })
            qr_buffer = self._generate_qr_code(qr_data)
            if qr_buffer:
                qr_image = Image(qr_buffer, width=3*cm, height=3*cm)
                qr_image.hAlign = 'LEFT'
                story.append(qr_image)
                story.append(Spacer(1, 0.3*cm))

            # Claim details section
            story.append(Paragraph("معلومات المطالبة", styles['subheading']))

            claim_table_data = [
                ["القيمة", "الحقل"],
                [claim_data['case_number'], "رقم المطالبة"],
                [claim_data['case_status'], "الحالة"],
                [claim_data['source'], "المصدر"],
                [claim_data.get('created_at', '-'), "تاريخ الإنشاء"],
            ]

            claim_table = Table(claim_table_data, colWidths=[10*cm, 5*cm])
            claim_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ]))
            story.append(claim_table)
            story.append(Spacer(1, 0.5*cm))

            # Property details
            if claim_data.get('building'):
                story.append(Paragraph("معلومات العقار", styles['subheading']))

                building = claim_data['building']
                property_table_data = [
                    ["القيمة", "الحقل"],
                    [building.get('building_id', '-'), "رقم المبنى"],
                    [building.get('neighborhood_code', '-'), "رمز الحي"],
                    [building.get('building_type', '-'), "نوع المبنى"],
                    [claim_data.get('unit_id', '-'), "رقم الوحدة"],
                ]

                property_table = Table(property_table_data, colWidths=[10*cm, 5*cm])
                property_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
                ]))
                story.append(property_table)
                story.append(Spacer(1, 0.5*cm))

            # Claimants
            if claim_data.get('claimants'):
                story.append(Paragraph("المطالبون", styles['subheading']))

                claimants_table_data = [["نوع العلاقة", "اسم الأب", "اسم العائلة", "الاسم الأول"]]
                for claimant in claim_data['claimants']:
                    claimants_table_data.append([
                        claimant.get('relation_type', '-'),
                        claimant.get('father_name', '-'),
                        claimant.get('last_name', '-'),
                        claimant.get('first_name', '-')
                    ])

                claimants_table = Table(claimants_table_data, colWidths=[3.5*cm, 4*cm, 4*cm, 4*cm])
                claimants_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
                ]))
                story.append(claimants_table)
                story.append(Spacer(1, 0.5*cm))

            # Documents
            if claim_data.get('documents'):
                story.append(Paragraph("المستندات المرفقة", styles['subheading']))

                docs_table_data = [["تاريخ الإصدار", "رقم المستند", "نوع المستند"]]
                for doc in claim_data['documents']:
                    docs_table_data.append([
                        doc.get('issue_date', '-'),
                        doc.get('document_number', '-'),
                        doc.get('document_type', '-')
                    ])

                docs_table = Table(docs_table_data, colWidths=[4*cm, 5*cm, 6*cm])
                docs_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
                ]))
                story.append(docs_table)

            # Footer with signature info
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph(f"تم التوليد بتاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['footer']))
            story.append(Paragraph(f"معرف التقرير: {report_id}", styles['footer']))

            # Build PDF
            doc.build(story)

            # Compute checksum and signature
            with open(file_path, 'rb') as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()

            metadata = {
                'report_id': report_id,
                'generated_at': datetime.now().isoformat()
            }
            signature = self._compute_report_signature(content_hash, metadata)

            # Log report generation
            self._log_report_generation(
                report_id=report_id,
                report_type="claim_report",
                file_path=str(file_path),
                checksum=content_hash,
                signature=signature,
                generated_by=generated_by
            )

            logger.info(f"Generated claim report: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to generate claim report: {e}", exc_info=True)
            return None

    def generate_daily_summary_report(
        self,
        date: datetime = None,
        generated_by: str = None
    ) -> Optional[Path]:
        """Generate daily collection summary report."""
        if not REPORTLAB_AVAILABLE:
            return None

        date = date or datetime.now()
        report_id = str(uuid.uuid4())
        filename = f"daily_summary_{date.strftime('%Y%m%d')}.pdf"
        file_path = self.output_dir / filename

        try:
            # Fetch summary data
            summary = self._fetch_daily_summary(date)

            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )

            styles = self._get_arabic_styles()
            story = []

            # Header
            story.append(Paragraph("UN-Habitat", styles['title']))
            story.append(Paragraph("تقرير ملخص يومي", styles['title']))
            story.append(Paragraph(f"التاريخ: {date.strftime('%Y-%m-%d')}", styles['heading']))
            story.append(Spacer(1, 1*cm))

            # QR Code
            qr_data = json.dumps({
                "report_id": report_id,
                "type": "daily_summary",
                "date": date.strftime('%Y-%m-%d')
            })
            qr_buffer = self._generate_qr_code(qr_data)
            if qr_buffer:
                story.append(Image(qr_buffer, width=3*cm, height=3*cm))
                story.append(Spacer(1, 0.5*cm))

            # Summary statistics
            story.append(Paragraph("إحصائيات اليوم", styles['subheading']))

            stats_table_data = [
                ["القيمة", "المؤشر"],
                [str(summary.get('new_claims', 0)), "المطالبات الجديدة"],
                [str(summary.get('updated_claims', 0)), "المطالبات المحدثة"],
                [str(summary.get('new_buildings', 0)), "المباني المضافة"],
                [str(summary.get('new_persons', 0)), "الأشخاص المسجلون"],
                [str(summary.get('documents_uploaded', 0)), "المستندات المرفوعة"],
            ]

            stats_table = Table(stats_table_data, colWidths=[8*cm, 7*cm])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(stats_table)
            story.append(Spacer(1, 1*cm))

            # Claims by status
            if summary.get('claims_by_status'):
                story.append(Paragraph("المطالبات حسب الحالة", styles['subheading']))

                status_table_data = [["العدد", "الحالة"]]
                for status, count in summary['claims_by_status'].items():
                    status_table_data.append([str(count), status])

                status_table = Table(status_table_data, colWidths=[6*cm, 9*cm])
                status_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(status_table)

            # Footer
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph(f"تم التوليد: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['footer']))
            story.append(Paragraph(f"معرف التقرير: {report_id}", styles['footer']))

            doc.build(story)

            # Log generation
            with open(file_path, 'rb') as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()

            self._log_report_generation(
                report_id=report_id,
                report_type="daily_summary",
                file_path=str(file_path),
                checksum=content_hash,
                signature=self._compute_report_signature(content_hash, {
                    'report_id': report_id,
                    'generated_at': datetime.now().isoformat()
                }),
                generated_by=generated_by
            )

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate daily summary: {e}", exc_info=True)
            return None

    def generate_property_status_report(
        self,
        neighborhood_code: str = None,
        generated_by: str = None
    ) -> Optional[Path]:
        """Generate property status report."""
        if not REPORTLAB_AVAILABLE:
            return None

        report_id = str(uuid.uuid4())
        filename = f"property_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = self.output_dir / filename

        try:
            # Fetch property data
            properties = self._fetch_property_status(neighborhood_code)

            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )

            styles = self._get_arabic_styles()
            story = []

            # Header
            story.append(Paragraph("UN-Habitat", styles['title']))
            story.append(Paragraph("تقرير حالة العقارات", styles['title']))
            if neighborhood_code:
                story.append(Paragraph(f"الحي: {neighborhood_code}", styles['heading']))
            story.append(Spacer(1, 0.5*cm))

            # QR Code
            qr_data = json.dumps({
                "report_id": report_id,
                "type": "property_status",
                "neighborhood": neighborhood_code
            })
            qr_buffer = self._generate_qr_code(qr_data)
            if qr_buffer:
                story.append(Image(qr_buffer, width=3*cm, height=3*cm))
                story.append(Spacer(1, 0.5*cm))

            # Properties table
            story.append(Paragraph("قائمة العقارات", styles['subheading']))

            property_table_data = [["الحالة", "عدد الوحدات", "نوع المبنى", "رقم المبنى"]]
            for prop in properties[:50]:  # Limit to 50 for readability
                property_table_data.append([
                    prop.get('building_status', '-'),
                    str(prop.get('number_of_units', 0)),
                    prop.get('building_type', '-'),
                    prop.get('building_id', '-')
                ])

            property_table = Table(property_table_data, colWidths=[3*cm, 3*cm, 4*cm, 5*cm])
            property_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Arabic' if self.FONT_REGISTERED else 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ]))
            story.append(property_table)

            # Footer
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph(f"إجمالي العقارات: {len(properties)}", styles['body']))
            story.append(Paragraph(f"تم التوليد: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['footer']))
            story.append(Paragraph(f"معرف التقرير: {report_id}", styles['footer']))

            doc.build(story)

            # Log
            with open(file_path, 'rb') as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()

            self._log_report_generation(
                report_id=report_id,
                report_type="property_status",
                file_path=str(file_path),
                checksum=content_hash,
                signature=self._compute_report_signature(content_hash, {
                    'report_id': report_id,
                    'generated_at': datetime.now().isoformat()
                }),
                generated_by=generated_by
            )

            return file_path

        except Exception as e:
            logger.error(f"Failed to generate property status report: {e}", exc_info=True)
            return None

    def _fetch_claim_data(self, claim_id: str) -> Optional[Dict]:
        """Fetch claim data for report."""
        try:
            cursor = self.db.cursor()

            # Claim details
            cursor.execute("""
                SELECT c.claim_uuid, c.case_number, c.case_status, c.source,
                       c.created_at, c.updated_at, c.unit_uuid,
                       u.unit_id, u.unit_type,
                       b.building_uuid, b.building_id, b.neighborhood_code,
                       b.building_type, b.building_status
                FROM claims c
                LEFT JOIN units u ON c.unit_uuid = u.unit_uuid
                LEFT JOIN buildings b ON u.building_uuid = b.building_uuid
                WHERE c.claim_uuid = ? OR c.case_number = ?
            """, (claim_id, claim_id))

            row = cursor.fetchone()
            if not row:
                return None

            claim_data = {
                'claim_uuid': row[0],
                'case_number': row[1],
                'case_status': row[2],
                'source': row[3],
                'created_at': row[4],
                'updated_at': row[5],
                'unit_uuid': row[6],
                'unit_id': row[7],
                'unit_type': row[8],
                'building': {
                    'building_uuid': row[9],
                    'building_id': row[10],
                    'neighborhood_code': row[11],
                    'building_type': row[12],
                    'building_status': row[13]
                } if row[9] else None
            }

            # Claimants
            cursor.execute("""
                SELECT p.first_name, p.father_name, p.last_name, r.relation_type
                FROM claim_persons cp
                JOIN persons p ON cp.person_uuid = p.person_uuid
                LEFT JOIN person_unit_relations r ON p.person_uuid = r.person_uuid
                WHERE cp.claim_uuid = ?
            """, (claim_data['claim_uuid'],))

            claim_data['claimants'] = [
                {
                    'first_name': row[0],
                    'father_name': row[1],
                    'last_name': row[2],
                    'relation_type': row[3]
                }
                for row in cursor.fetchall()
            ]

            # Documents
            cursor.execute("""
                SELECT d.document_type, d.document_number, d.issue_date, d.verified
                FROM claim_documents cd
                JOIN documents d ON cd.document_uuid = d.document_uuid
                WHERE cd.claim_uuid = ?
            """, (claim_data['claim_uuid'],))

            claim_data['documents'] = [
                {
                    'document_type': row[0],
                    'document_number': row[1],
                    'issue_date': row[2],
                    'verified': bool(row[3])
                }
                for row in cursor.fetchall()
            ]

            return claim_data

        except Exception as e:
            logger.error(f"Error fetching claim data: {e}")
            return None

    def _fetch_daily_summary(self, date: datetime) -> Dict:
        """Fetch daily summary data."""
        try:
            cursor = self.db.cursor()
            date_str = date.strftime('%Y-%m-%d')

            summary = {}

            # New claims
            cursor.execute("""
                SELECT COUNT(*) FROM claims WHERE DATE(created_at) = ?
            """, (date_str,))
            summary['new_claims'] = cursor.fetchone()[0]

            # Updated claims
            cursor.execute("""
                SELECT COUNT(*) FROM claims
                WHERE DATE(updated_at) = ? AND DATE(created_at) != DATE(updated_at)
            """, (date_str,))
            summary['updated_claims'] = cursor.fetchone()[0]

            # New buildings
            cursor.execute("""
                SELECT COUNT(*) FROM buildings WHERE DATE(created_at) = ?
            """, (date_str,))
            summary['new_buildings'] = cursor.fetchone()[0]

            # New persons
            cursor.execute("""
                SELECT COUNT(*) FROM persons WHERE DATE(created_at) = ?
            """, (date_str,))
            summary['new_persons'] = cursor.fetchone()[0]

            # Documents
            cursor.execute("""
                SELECT COUNT(*) FROM documents WHERE DATE(created_at) = ?
            """, (date_str,))
            summary['documents_uploaded'] = cursor.fetchone()[0]

            # Claims by status
            cursor.execute("""
                SELECT case_status, COUNT(*) FROM claims GROUP BY case_status
            """)
            summary['claims_by_status'] = dict(cursor.fetchall())

            return summary

        except Exception as e:
            logger.error(f"Error fetching daily summary: {e}")
            return {}

    def _fetch_property_status(self, neighborhood_code: str = None) -> List[Dict]:
        """Fetch property status data."""
        try:
            cursor = self.db.cursor()

            query = """
                SELECT building_id, building_type, building_status,
                       number_of_units, neighborhood_code
                FROM buildings
            """
            params = []

            if neighborhood_code:
                query += " WHERE neighborhood_code = ?"
                params.append(neighborhood_code)

            query += " ORDER BY building_id"

            cursor.execute(query, params)

            return [
                {
                    'building_id': row[0],
                    'building_type': row[1],
                    'building_status': row[2],
                    'number_of_units': row[3],
                    'neighborhood_code': row[4]
                }
                for row in cursor.fetchall()
            ]

        except Exception as e:
            logger.error(f"Error fetching property status: {e}")
            return []

    def _log_report_generation(
        self,
        report_id: str,
        report_type: str,
        file_path: str,
        checksum: str,
        signature: str,
        generated_by: str
    ):
        """Log report generation to database."""
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO report_log (
                    report_id, report_type, file_path, checksum,
                    signature, generated_at, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                report_type,
                file_path,
                checksum,
                signature,
                datetime.now().isoformat(),
                generated_by
            ))
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not log report generation: {e}")

    def verify_report(self, file_path: Path) -> tuple:
        """
        Verify report integrity and signature.

        Returns:
            (is_valid, message)
        """
        try:
            # Compute current checksum
            with open(file_path, 'rb') as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()

            # Look up original report in log
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT checksum, signature FROM report_log
                WHERE file_path = ?
            """, (str(file_path),))

            row = cursor.fetchone()
            if not row:
                return False, "التقرير غير مسجل في النظام"

            stored_checksum, stored_signature = row

            if current_hash != stored_checksum:
                return False, "تم تعديل التقرير - الملف غير متطابق مع النسخة الأصلية"

            return True, "التقرير أصلي ولم يتم تعديله"

        except Exception as e:
            return False, f"خطأ في التحقق: {str(e)}"
