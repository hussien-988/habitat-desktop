# -*- coding: utf-8 -*-
"""Reports generation page with templates and export."""

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
from services.translation_manager import tr, get_layout_direction
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
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H2}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Description
        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.desc_label)


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
        self._title = QLabel(tr("page.reports.title"))
        self._title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(self._title)

        # Report templates section
        self._templates_label = QLabel(tr("page.reports.templates_title"))
        self._templates_label.setStyleSheet(f"font-size: {Config.FONT_SIZE_H2}pt; font-weight: 600;")
        layout.addWidget(self._templates_label)

        # Report cards grid
        grid = QGridLayout()
        grid.setSpacing(20)

        self._report_cards_keys = [
            ("page.reports.buildings_report", "page.reports.buildings_report_desc", "", "buildings_summary"),
            ("page.reports.claims_report", "page.reports.claims_report_desc", "", "claims_summary"),
            ("page.reports.units_report", "page.reports.units_report_desc", "", "units_report"),
            ("page.reports.persons_report", "page.reports.persons_report_desc", "", "persons_report"),
            ("page.reports.conflicts_report", "page.reports.conflicts_report_desc", "", "conflicts_report"),
            ("page.reports.progress_report", "page.reports.progress_report_desc", "", "progress_report"),
        ]
        self._report_cards = []

        for idx, (title_key, desc_key, icon, rtype) in enumerate(self._report_cards_keys):
            card = ReportCard(tr(title_key), tr(desc_key), icon, rtype)
            card.mousePressEvent = lambda e, rt=rtype: self._on_report_click(rt)
            grid.addWidget(card, idx // 3, idx % 3)
            self._report_cards.append(card)

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

        self._export_title = QLabel(tr("page.reports.export_data"))
        self._export_title.setStyleSheet(f"font-size: {Config.FONT_SIZE_H2}pt; font-weight: 600;")
        export_layout.addWidget(self._export_title)

        # Export options
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        # Entity selection
        entity_layout = QVBoxLayout()
        self._entity_label = QLabel(tr("page.reports.entity"))
        self._entity_label.setStyleSheet("font-weight: 500;")
        entity_layout.addWidget(self._entity_label)

        self.entity_combo = QComboBox()
        entities = [
            ("buildings", tr("page.reports.entity_buildings")),
            ("units", tr("page.reports.entity_units")),
            ("persons", tr("page.reports.entity_persons")),
            ("claims", tr("page.reports.entity_claims")),
        ]
        for code, name in entities:
            self.entity_combo.addItem(name, code)
        entity_layout.addWidget(self.entity_combo)
        options_layout.addLayout(entity_layout)

        # Format selection
        format_layout = QVBoxLayout()
        self._format_label = QLabel(tr("page.reports.format"))
        self._format_label.setStyleSheet("font-weight: 500;")
        format_layout.addWidget(self._format_label)

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
        self._from_date_label = QLabel(tr("page.reports.from_date"))
        self._from_date_label.setStyleSheet("font-weight: 500;")
        date_layout.addWidget(self._from_date_label)

        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-6))
        date_layout.addWidget(self.from_date)
        options_layout.addLayout(date_layout)

        date_layout2 = QVBoxLayout()
        self._to_date_label = QLabel(tr("page.reports.to_date"))
        self._to_date_label.setStyleSheet("font-weight: 500;")
        date_layout2.addWidget(self._to_date_label)

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        date_layout2.addWidget(self.to_date)
        options_layout.addLayout(date_layout2)

        options_layout.addStretch()

        # Export button
        self._export_btn = QPushButton(tr("page.reports.export_btn"))
        self._export_btn.setStyleSheet(f"""
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
        self._export_btn.clicked.connect(self._on_export)
        options_layout.addWidget(self._export_btn, alignment=Qt.AlignBottom)

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
            tr("page.reports.save_report"),
            f"{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf",
            "PDF Files (*.pdf)"
        )

        if not filename:
            return

        try:
            # Generate report (placeholder - would use reportlab for PDF)
            Toast.show_toast(self, tr("page.reports.generating_report", report_type=report_type), Toast.INFO)

            # In production, this would call a PDF generation service
            # For now, we'll export as CSV
            file_path = Path(filename).with_suffix('.csv')
            result = self.export_service.export_buildings_csv(file_path, {})

            Toast.show_toast(
                self,
                tr("page.reports.report_success", count=result['record_count']),
                Toast.SUCCESS
            )

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            ErrorHandler.show_warning(self, tr("page.reports.report_failed", error=str(e)), tr("dialog.error"))

    def _on_export(self):
        """Handle data export."""
        entity = self.entity_combo.currentData()
        fmt = self.format_combo.currentData()

        extensions = {"csv": "csv", "excel": "xlsx", "geojson": "geojson"}
        ext = extensions.get(fmt, "csv")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("page.reports.export_data"),
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
                    tr("page.reports.export_success_count", count=result.get('record_count', 0)),
                    Toast.SUCCESS
                )
            else:
                Toast.show_toast(self, tr("page.reports.export_success"), Toast.SUCCESS)

        except Exception as e:
            logger.error(f"Export failed: {e}")
            ErrorHandler.show_warning(self, tr("page.reports.export_failed", error=str(e)), tr("dialog.error"))

        finally:
            self.progress.setVisible(False)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._title.setText(tr("page.reports.title"))
        self._templates_label.setText(tr("page.reports.templates_title"))
        self._export_title.setText(tr("page.reports.export_data"))
        self._entity_label.setText(tr("page.reports.entity"))
        self._format_label.setText(tr("page.reports.format"))
        self._from_date_label.setText(tr("page.reports.from_date"))
        self._to_date_label.setText(tr("page.reports.to_date"))
        self._export_btn.setText(tr("page.reports.export_btn"))

        entity_keys = [
            ("buildings", "page.reports.entity_buildings"),
            ("units", "page.reports.entity_units"),
            ("persons", "page.reports.entity_persons"),
            ("claims", "page.reports.entity_claims"),
        ]
        for i, (code, key) in enumerate(entity_keys):
            self.entity_combo.setItemText(i, tr(key))

        for i, (title_key, desc_key, _, _) in enumerate(self._report_cards_keys):
            card = self._report_cards[i]
            card.title_label.setText(tr(title_key))
            card.desc_label.setText(tr(desc_key))
