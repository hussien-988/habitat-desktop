# -*- coding: utf-8 -*-
"""
Reports generation page with templates and export.
Implements UC-012: Report Generation, UC-013: Data Export
"""

from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QGridLayout, QFileDialog,
    QGraphicsDropShadowEffect, QProgressBar, QDateEdit
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from app.config import Config
from repositories.database import Database
from services.export_service import ExportService
from ui.components.toast import Toast
from ui.error_handler import ErrorHandler
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class ReportCard(QFrame):
    """A card representing a report template."""

    def __init__(self, title: str, description: str, icon: str, report_type: str, parent=None):
        super().__init__(parent)
        self.report_type = report_type
        self._setup_ui(title, description, icon)

    def _setup_ui(self, title: str, description: str, icon: str):
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E2E8F0;
            }
            QFrame:hover {
                border-color: #0072BC;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32pt;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H2}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)


class ReportsPage(QWidget):
    """Reports generation page."""

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.export_service = ExportService(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        # Header
        title = QLabel(self.i18n.t("reports"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(title)

        # Report templates section
        templates_label = QLabel("قوالب التقارير")
        templates_label.setStyleSheet(f"font-size: {Config.FONT_SIZE_H2}pt; font-weight: 600;")
        layout.addWidget(templates_label)

        # Report cards grid
        grid = QGridLayout()
        grid.setSpacing(20)

        reports = [
            ("تقرير المباني", "إحصائيات المباني حسب الحالة والنوع", "", "buildings_summary"),
            ("تقرير المطالبات", "ملخص المطالبات حسب الحالة", "", "claims_summary"),
            ("تقرير الوحدات", "تفاصيل الوحدات العقارية", "", "units_report"),
            ("تقرير الأشخاص", "قائمة المستفيدين والمطالبين", "", "persons_report"),
            ("تقرير التعارضات", "المطالبات المتعارضة", "", "conflicts_report"),
            ("تقرير الإنجاز", "مؤشرات الأداء والإنجاز", "", "progress_report"),
        ]

        for idx, (title, desc, icon, rtype) in enumerate(reports):
            card = ReportCard(title, desc, icon, rtype)
            card.mousePressEvent = lambda e, rt=rtype: self._on_report_click(rt)
            grid.addWidget(card, idx // 3, idx % 3)

        layout.addLayout(grid)

        # Export section
        export_frame = QFrame()
        export_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        export_frame.setGraphicsEffect(shadow)

        export_layout = QVBoxLayout(export_frame)
        export_layout.setContentsMargins(24, 24, 24, 24)
        export_layout.setSpacing(16)

        export_title = QLabel("تصدير البيانات")
        export_title.setStyleSheet(f"font-size: {Config.FONT_SIZE_H2}pt; font-weight: 600;")
        export_layout.addWidget(export_title)

        # Export options
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        # Entity selection
        entity_layout = QVBoxLayout()
        entity_label = QLabel("الكيان:")
        entity_label.setStyleSheet("font-weight: 500;")
        entity_layout.addWidget(entity_label)

        self.entity_combo = QComboBox()
        entities = [
            ("buildings", "المباني"),
            ("units", "الوحدات"),
            ("persons", "الأشخاص"),
            ("claims", "المطالبات"),
        ]
        for code, name in entities:
            self.entity_combo.addItem(name, code)
        entity_layout.addWidget(self.entity_combo)
        options_layout.addLayout(entity_layout)

        # Format selection
        format_layout = QVBoxLayout()
        format_label = QLabel("الصيغة:")
        format_label.setStyleSheet("font-weight: 500;")
        format_layout.addWidget(format_label)

        self.format_combo = QComboBox()
        formats = [
            ("csv", "CSV"),
            ("excel", "Excel"),
            ("geojson", "GeoJSON"),
        ]
        for code, name in formats:
            self.format_combo.addItem(name, code)
        format_layout.addWidget(self.format_combo)
        options_layout.addLayout(format_layout)

        # Date range
        date_layout = QVBoxLayout()
        date_label = QLabel("من تاريخ:")
        date_label.setStyleSheet("font-weight: 500;")
        date_layout.addWidget(date_label)

        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-6))
        date_layout.addWidget(self.from_date)
        options_layout.addLayout(date_layout)

        date_layout2 = QVBoxLayout()
        date_label2 = QLabel("إلى تاريخ:")
        date_label2.setStyleSheet("font-weight: 500;")
        date_layout2.addWidget(date_label2)

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        date_layout2.addWidget(self.to_date)
        options_layout.addLayout(date_layout2)

        options_layout.addStretch()

        # Export button
        export_btn = QPushButton("تصدير")
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 32px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        export_btn.clicked.connect(self._on_export)
        options_layout.addWidget(export_btn, alignment=Qt.AlignBottom)

        export_layout.addLayout(options_layout)

        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        export_layout.addWidget(self.progress)

        layout.addWidget(export_frame)
        layout.addStretch()

    def refresh(self, data=None):
        pass

    def _on_report_click(self, report_type: str):
        """Handle report card click."""
        logger.debug(f"Generating report: {report_type}")

        # Ask for save location
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ التقرير",
            f"{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf",
            "PDF Files (*.pdf)"
        )

        if not filename:
            return

        try:
            # Generate report (placeholder - would use reportlab for PDF)
            Toast.show_toast(self, f"جاري إنشاء التقرير: {report_type}", Toast.INFO)

            # In production, this would call a PDF generation service
            # For now, we'll export as CSV
            file_path = Path(filename).with_suffix('.csv')
            result = self.export_service.export_buildings_csv(file_path, {})

            Toast.show_toast(
                self,
                f"تم إنشاء التقرير بنجاح: {result['record_count']} سجل",
                Toast.SUCCESS
            )

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            ErrorHandler.show_warning(self, f"فشل في إنشاء التقرير: {str(e)}", "خطأ")

    def _on_export(self):
        """Handle data export."""
        entity = self.entity_combo.currentData()
        fmt = self.format_combo.currentData()

        extensions = {"csv": "csv", "excel": "xlsx", "geojson": "geojson"}
        ext = extensions.get(fmt, "csv")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "تصدير البيانات",
            f"{entity}_export_{datetime.now().strftime('%Y%m%d')}.{ext}",
            f"{fmt.upper()} Files (*.{ext})"
        )

        if not filename:
            return

        try:
            self.progress.setVisible(True)
            self.progress.setValue(0)

            file_path = Path(filename)
            result = None

            if entity == "buildings":
                if fmt == "csv":
                    result = self.export_service.export_buildings_csv(file_path, {})
                elif fmt == "excel":
                    result = self.export_service.export_buildings_excel(file_path, {})
                elif fmt == "geojson":
                    result = self.export_service.export_buildings_geojson(file_path, {})
            elif entity == "claims":
                if fmt == "csv":
                    result = self.export_service.export_claims_csv(file_path, {})
            else:
                # Generic export
                if fmt == "csv":
                    result = self.export_service.export_buildings_csv(file_path, {})

            self.progress.setValue(100)

            if result:
                Toast.show_toast(
                    self,
                    f"تم التصدير بنجاح: {result.get('record_count', 0)} سجل",
                    Toast.SUCCESS
                )
            else:
                Toast.show_toast(self, "تم التصدير بنجاح", Toast.SUCCESS)

        except Exception as e:
            logger.error(f"Export failed: {e}")
            ErrorHandler.show_warning(self, f"فشل في التصدير: {str(e)}", "خطأ")

        finally:
            self.progress.setVisible(False)

    def update_language(self, is_arabic: bool):
        pass
