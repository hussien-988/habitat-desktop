# -*- coding: utf-8 -*-
"""Commit Report Dialog - displays detailed commit report with download/print options."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from datetime import datetime

from app.config import Config
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr


class CommitReportDialog(QDialog):
    """Detailed commit report dialog with import summary and export options."""

    def __init__(self, commit_result: dict, import_metadata: dict, parent=None):
        super().__init__(parent)
        self.commit_result = commit_result
        self.import_metadata = import_metadata

        self.setWindowTitle(tr("component.commit_report.window_title"))
        self.setMinimumWidth(900)
        self.setMinimumHeight(750)
        self.resize(1000, 800)  # Set initial size
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Success Header
        header_frame = QFrame()
        success = self.commit_result.get('success', False)
        header_color = Config.SUCCESS_COLOR if success else Config.WARNING_COLOR

        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {'#D1FAE5' if success else '#FEF3C7'};
                border: 2px solid {header_color};
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)

        # Icon
        icon = "✅" if success else "⚠️"
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 56pt;")
        header_layout.addWidget(icon_label)

        # Title and summary
        title_layout = QVBoxLayout()

        title_text = tr("component.commit_report.import_success") if success else tr("component.commit_report.import_with_notes")
        title = QLabel(title_text)
        title.setFont(create_font(size=18, weight=QFont.Bold, letter_spacing=0))
        title.setStyleSheet(f"color: {header_color};")
        title_layout.addWidget(title)

        summary = QLabel(
            tr("component.commit_report.import_summary", count=self.commit_result.get('imported', 0))
        )
        summary.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        title_layout.addWidget(summary)

        timestamp = QLabel(
            tr("component.commit_report.timestamp", datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        timestamp.setStyleSheet("color: #6B7280;")
        title_layout.addWidget(timestamp)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addWidget(header_frame)

        # Statistics Cards
        stats_layout = QGridLayout()
        stats_layout.setSpacing(12)

        self._add_stat_card(stats_layout, 0, 0, tr("component.commit_report.stat_imported"),
                           str(self.commit_result.get('imported', 0)),
                           Config.SUCCESS_COLOR)

        self._add_stat_card(stats_layout, 0, 1, tr("component.commit_report.stat_skipped"),
                           str(self.commit_result.get('skipped', 0)),
                           Config.TEXT_LIGHT)

        self._add_stat_card(stats_layout, 0, 2, tr("component.commit_report.stat_warnings"),
                           str(self.commit_result.get('warnings', 0)),
                           Config.WARNING_COLOR)

        self._add_stat_card(stats_layout, 0, 3, tr("component.commit_report.stat_failed"),
                           str(self.commit_result.get('failed', 0)),
                           Config.ERROR_COLOR)

        layout.addLayout(stats_layout)

        # Imported Records Breakdown
        breakdown_group = QGroupBox(tr("component.commit_report.section_records_breakdown"))
        breakdown_group.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        breakdown_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
            }}
        """)
        breakdown_layout = QGridLayout(breakdown_group)

        records_by_type = self.commit_result.get('records_by_type', {})
        row = 0
        for record_type, count in records_by_type.items():
            type_icons = {
                'buildings': '🏢',
                'units': '🏠',
                'persons': '👤',
                'households': '👨\u200d👩\u200d👧\u200d👦',
                'claims': '📋',
                'documents': '📄'
            }
            icon = type_icons.get(record_type, '📦')
            type_ar = {
                'buildings': tr("component.commit_report.type_buildings"),
                'units': tr("component.commit_report.type_units"),
                'persons': tr("component.commit_report.type_persons"),
                'households': tr("component.commit_report.type_households"),
                'claims': tr("component.commit_report.type_claims"),
                'documents': tr("component.commit_report.type_documents"),
            }.get(record_type, record_type)

            label = QLabel(f"{icon} {type_ar}:")
            label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
            breakdown_layout.addWidget(label, row, 0)

            value = QLabel(tr("component.commit_report.record_count", count=count))
            value.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
            value.setStyleSheet(f"color: {Config.PRIMARY_COLOR};")
            breakdown_layout.addWidget(value, row, 1)

            row += 1

        layout.addWidget(breakdown_group)

        # Archive and Audit Information
        archive_group = QGroupBox(tr("component.commit_report.section_archive_info"))
        archive_group.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        archive_group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
            }}
        """)
        archive_layout = QVBoxLayout(archive_group)

        archive_items = [
            (tr("component.commit_report.original_package"), self.import_metadata.get('original_file', 'N/A')),
            (tr("component.commit_report.archive_location"), self.import_metadata.get('archive_path', '/data/archive/')),
            (tr("component.commit_report.package_id"), self.import_metadata.get('package_id', 'N/A')),
            (tr("component.commit_report.audit_log_id"), self.import_metadata.get('audit_log_id', 'N/A')),
            (tr("component.commit_report.import_duration"), tr("component.commit_report.duration_seconds", seconds=f"{self.commit_result.get('duration_seconds', 0):.2f}")),
        ]

        for label_text, value_text in archive_items:
            row_layout = QHBoxLayout()

            label = QLabel(label_text)
            label.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            label.setMinimumWidth(180)
            row_layout.addWidget(label)

            value = QLabel(str(value_text))
            value.setWordWrap(True)
            value.setStyleSheet(f"color: {Config.TEXT_COLOR};")
            row_layout.addWidget(value, 1)

            archive_layout.addLayout(row_layout)

        layout.addWidget(archive_group)

        # Full Report Text (for export)
        report_label = QLabel(tr("component.commit_report.full_report"))
        report_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(report_label)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlainText(self._generate_full_report())
        self.report_text.setMaximumHeight(200)
        self.report_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #F9FAFB;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 12px;
                font-family: 'Courier New';
                font-size: 9pt;
            }}
        """)
        layout.addWidget(self.report_text)

        # Add spacing before buttons
        layout.addSpacing(20)

        # Action Buttons Section
        buttons_frame = QFrame()
        buttons_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Config.BACKGROUND_COLOR};
                border-top: 2px solid {Config.BORDER_COLOR};
                padding: 16px;
                margin-top: 10px;
            }}
        """)
        buttons_frame_layout = QVBoxLayout(buttons_frame)

        buttons_label = QLabel(tr("component.commit_report.report_options"))
        buttons_label.setFont(create_font(size=11, weight=QFont.Bold, letter_spacing=0))
        buttons_frame_layout.addWidget(buttons_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        # Download Report
        download_btn = QPushButton(tr("component.commit_report.btn_download"))
        download_btn.setMinimumHeight(45)
        download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 28px;
                font-weight: 600;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                background-color: #16A34A;
            }}
            QPushButton:pressed {{
                background-color: #1E8449;
            }}
        """)
        download_btn.clicked.connect(self._on_download_report)
        button_layout.addWidget(download_btn)

        # Print Report
        print_btn = QPushButton(tr("component.commit_report.btn_print"))
        print_btn.setMinimumHeight(45)
        print_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 28px;
                font-weight: 600;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                background-color: #0284C7;
            }}
            QPushButton:pressed {{
                background-color: #1A5A8A;
            }}
        """)
        print_btn.clicked.connect(self._on_print_report)
        button_layout.addWidget(print_btn)

        # Close
        close_btn = QPushButton(tr("component.commit_report.btn_close"))
        close_btn.setMinimumHeight(45)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.TEXT_LIGHT};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 28px;
                font-weight: 600;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                background-color: #4B5563;
            }}
            QPushButton:pressed {{
                background-color: #374151;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        buttons_frame_layout.addLayout(button_layout)
        layout.addWidget(buttons_frame)

    def _add_stat_card(self, parent_layout: QGridLayout, row: int, col: int,
                      title: str, value: str, color: str):
        """Add a statistics card."""
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 8px;
                border-left: 5px solid {color};
                padding: 12px;
            }}
        """)

        card_layout = QVBoxLayout(card)

        value_label = QLabel(value)
        value_label.setFont(create_font(size=24, weight=QFont.Bold, letter_spacing=0))
        value_label.setStyleSheet(f"color: {color};")
        card_layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        title_label.setStyleSheet("color: #6B7280;")
        card_layout.addWidget(title_label)

        parent_layout.addWidget(card, row, col)

    def _generate_full_report(self) -> str:
        """Generate full text report for export."""
        report = "=" * 80 + "\n"
        report += tr("component.commit_report.report_header") + "\n"
        report += "=" * 80 + "\n\n"

        report += tr("component.commit_report.report_timestamp", datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "\n"
        status_text = tr("component.commit_report.report_status_success") if self.commit_result.get('success') else tr("component.commit_report.report_status_notes")
        report += tr("component.commit_report.report_status", status=status_text) + "\n\n"

        report += "-" * 80 + "\n"
        report += tr("component.commit_report.report_import_stats") + "\n"
        report += "-" * 80 + "\n"
        report += tr("component.commit_report.report_imported", count=self.commit_result.get('imported', 0)) + "\n"
        report += tr("component.commit_report.report_skipped", count=self.commit_result.get('skipped', 0)) + "\n"
        report += tr("component.commit_report.report_warnings", count=self.commit_result.get('warnings', 0)) + "\n"
        report += tr("component.commit_report.report_failed", count=self.commit_result.get('failed', 0)) + "\n\n"

        report += "-" * 80 + "\n"
        report += tr("component.commit_report.report_records_by_type") + "\n"
        report += "-" * 80 + "\n"
        for record_type, count in self.commit_result.get('records_by_type', {}).items():
            report += tr("component.commit_report.report_record_line", type=record_type, count=count) + "\n"

        report += "\n" + "-" * 80 + "\n"
        report += tr("component.commit_report.report_archive_info") + "\n"
        report += "-" * 80 + "\n"
        report += tr("component.commit_report.report_original_package", value=self.import_metadata.get('original_file', 'N/A')) + "\n"
        report += tr("component.commit_report.report_archive_location", value=self.import_metadata.get('archive_path', 'N/A')) + "\n"
        report += tr("component.commit_report.report_package_id", value=self.import_metadata.get('package_id', 'N/A')) + "\n"
        report += tr("component.commit_report.report_audit_log_id", value=self.import_metadata.get('audit_log_id', 'N/A')) + "\n\n"

        report += "=" * 80 + "\n"
        report += tr("component.commit_report.report_end") + "\n"
        report += "=" * 80 + "\n"

        return report

    def _on_download_report(self):
        """Download report as text file."""
        from PyQt5.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("component.commit_report.save_report_dialog_title"),
            f"import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self._generate_full_report())

                from ui.components.toast import Toast
                Toast.show_toast(
                    self,
                    tr("component.commit_report.save_success_message", filename=filename),
                    Toast.SUCCESS
                )
            except Exception as e:
                from ui.components.toast import Toast
                Toast.show_toast(
                    self,
                    tr("component.commit_report.save_error_message", error=str(e)),
                    Toast.ERROR
                )

    def _on_print_report(self):
        """Print the report."""
        from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt5.QtGui import QTextDocument

        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)

        if dialog.exec_() == QPrintDialog.Accepted:
            document = QTextDocument()
            document.setPlainText(self._generate_full_report())
            document.print_(printer)

            from ui.components.toast import Toast
            Toast.show_toast(
                self,
                tr("component.commit_report.print_success_message"),
                Toast.SUCCESS
            )
