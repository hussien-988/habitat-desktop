# -*- coding: utf-8 -*-
"""Vocabulary Incompatibility Report Dialog."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFrame, QScrollArea, QWidget, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app.config import Config
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr
from ui.design_system import ScreenScale


class VocabularyIncompatibilityDialog(QDialog):
    """Dialog to display vocabulary incompatibility report."""

    def __init__(self, incompatible_vocabs: list, package_info: dict, parent=None):
        super().__init__(parent)
        self.incompatible_vocabs = incompatible_vocabs
        self.package_info = package_info

        self.setWindowTitle(tr("component.vocab_incompatibility.window_title"))
        self.setMinimumWidth(ScreenScale.w(700))
        self.setMinimumHeight(ScreenScale.h(600))
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Warning header
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #FEF3C7;
                border: 2px solid #F59E0B;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)

        # Icon
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 48pt;")
        header_layout.addWidget(icon_label)

        # Title and subtitle
        title_layout = QVBoxLayout()

        title = QLabel(tr("component.vocab_incompatibility.title"))
        title.setFont(create_font(size=16, weight=QFont.Bold, letter_spacing=0))
        title.setStyleSheet("color: #92400E;")
        title_layout.addWidget(title)

        subtitle = QLabel(tr("component.vocab_incompatibility.subtitle", count=len(self.incompatible_vocabs)))
        subtitle.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        subtitle.setStyleSheet("color: #B45309;")
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addWidget(header_frame)

        # Package Information
        pkg_label = QLabel(tr("component.vocab_incompatibility.section_package_info"))
        pkg_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(pkg_label)

        pkg_frame = QFrame()
        pkg_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        pkg_layout = QVBoxLayout(pkg_frame)

        pkg_items = [
            (tr("component.vocab_incompatibility.filename"), self.package_info.get('filename', tr("component.vocab_incompatibility.unspecified"))),
            (tr("component.vocab_incompatibility.package_id"), self.package_info.get('package_id', tr("component.vocab_incompatibility.unspecified"))),
            (tr("component.vocab_incompatibility.app_version"), self.package_info.get('app_version', tr("component.vocab_incompatibility.unspecified"))),
            (tr("component.vocab_incompatibility.created_date"), self.package_info.get('created_utc', tr("component.vocab_incompatibility.unspecified"))),
        ]

        for label_text, value_text in pkg_items:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            label.setMinimumWidth(ScreenScale.w(120))
            row.addWidget(label)

            value = QLabel(str(value_text))
            value.setStyleSheet(f"color: {Config.TEXT_COLOR};")
            row.addWidget(value, 1)

            pkg_layout.addLayout(row)

        layout.addWidget(pkg_frame)

        # Incompatible Vocabularies Table
        table_label = QLabel(tr("component.vocab_incompatibility.section_vocabs_needing_update"))
        table_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(table_label)

        self.vocab_table = QTableWidget()
        self.vocab_table.setColumnCount(5)
        self.vocab_table.setHorizontalHeaderLabels([
            tr("component.vocab_incompatibility.col_vocab_name"),
            tr("component.vocab_incompatibility.col_current_version"),
            tr("component.vocab_incompatibility.col_required_version"),
            tr("component.vocab_incompatibility.col_difference"),
            tr("component.vocab_incompatibility.col_impact"),
        ])
        self.vocab_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vocab_table.setAlternatingRowColors(True)
        self.vocab_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.vocab_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.vocab_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                gridline-color: #E5E7EB;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Config.PRIMARY_LIGHT};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 10px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)

        # Populate table
        self.vocab_table.setRowCount(len(self.incompatible_vocabs))
        for i, vocab in enumerate(self.incompatible_vocabs):
            # Vocabulary name
            name_item = QTableWidgetItem(vocab.get('name', 'N/A'))
            name_item.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            self.vocab_table.setItem(i, 0, name_item)

            # Current version
            current_ver = vocab.get('current_version', '0')
            current_item = QTableWidgetItem(f"v{current_ver}")
            self.vocab_table.setItem(i, 1, current_item)

            # Required version
            required_ver = vocab.get('required_version', '0')
            required_item = QTableWidgetItem(f"v{required_ver}")
            required_item.setForeground(Config.ERROR_COLOR)
            self.vocab_table.setItem(i, 2, required_item)

            # Version difference
            try:
                diff = int(required_ver) - int(current_ver)
                diff_text = tr("component.vocab_incompatibility.version_diff", diff=diff) if diff > 0 else str(diff)
                diff_item = QTableWidgetItem(diff_text)
                diff_item.setForeground(Config.WARNING_COLOR)
                self.vocab_table.setItem(i, 3, diff_item)
            except (ValueError, TypeError):
                self.vocab_table.setItem(i, 3, QTableWidgetItem(tr("component.vocab_incompatibility.unspecified")))

            # Impact
            impact = vocab.get('impact', 'medium')
            impact_text = {
                "high": tr("component.vocab_incompatibility.impact_high"),
                "medium": tr("component.vocab_incompatibility.impact_medium"),
                "low": tr("component.vocab_incompatibility.impact_low"),
            }.get(impact, impact)
            impact_item = QTableWidgetItem(impact_text)
            self.vocab_table.setItem(i, 4, impact_item)

        layout.addWidget(self.vocab_table)

        # Impact Assessment
        impact_label = QLabel(tr("component.vocab_incompatibility.section_impact_assessment"))
        impact_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(impact_label)

        impact_text = self._generate_impact_assessment()
        impact_display = QLabel(impact_text)
        impact_display.setWordWrap(True)
        impact_display.setStyleSheet(f"""
            background-color: #FEF3C7;
            border: 1px solid #F59E0B;
            border-radius: 6px;
            padding: 12px;
            color: #92400E;
        """)
        layout.addWidget(impact_display)

        # Recommended Actions
        actions_label = QLabel(tr("component.vocab_incompatibility.section_recommended_actions"))
        actions_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(actions_label)

        actions_text = tr("component.vocab_incompatibility.recommended_actions_text")
        actions_display = QLabel(actions_text)
        actions_display.setWordWrap(True)
        actions_display.setStyleSheet(f"""
            background-color: #DBEAFE;
            border: 1px solid {Config.INFO_COLOR};
            border-radius: 6px;
            padding: 12px;
            color: #1E40AF;
            line-height: 1.6;
        """)
        layout.addWidget(actions_display)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Go to Vocabulary Management
        vocab_mgmt_btn = QPushButton(tr("component.vocab_incompatibility.btn_vocab_management"))
        vocab_mgmt_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        vocab_mgmt_btn.clicked.connect(self._on_open_vocab_mgmt)
        button_layout.addWidget(vocab_mgmt_btn)

        # Export Report
        export_btn = QPushButton(tr("component.vocab_incompatibility.btn_export_report"))
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #0284C7;
            }}
        """)
        export_btn.clicked.connect(self._on_export_report)
        button_layout.addWidget(export_btn)

        # Close Button
        close_btn = QPushButton(tr("component.vocab_incompatibility.btn_close"))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.TEXT_LIGHT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #4B5563;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _generate_impact_assessment(self) -> str:
        """Generate impact assessment text."""
        high_impact = sum(1 for v in self.incompatible_vocabs if v.get('impact') == 'high')
        medium_impact = sum(1 for v in self.incompatible_vocabs if v.get('impact') == 'medium')
        low_impact = sum(1 for v in self.incompatible_vocabs if v.get('impact') == 'low')

        text = tr("component.vocab_incompatibility.impact_high_count", count=high_impact) + "\n"
        text += tr("component.vocab_incompatibility.impact_medium_count", count=medium_impact) + "\n"
        text += tr("component.vocab_incompatibility.impact_low_count", count=low_impact) + "\n\n"

        if high_impact > 0:
            text += tr("component.vocab_incompatibility.warning_high_impact")
        elif medium_impact > 0:
            text += tr("component.vocab_incompatibility.warning_medium_impact")
        else:
            text += tr("component.vocab_incompatibility.warning_low_impact")

        return text

    def _on_open_vocab_mgmt(self):
        """Open vocabulary management page."""
        from ui.components.toast import Toast
        Toast.show_toast(self.parent(), tr("component.vocab_incompatibility.opening_vocab_management"), Toast.INFO)
        # TODO: Navigate to vocabulary management page
        self.accept()

    def _on_export_report(self):
        """Export incompatibility report to file."""
        from PyQt5.QtWidgets import QFileDialog
        from datetime import datetime

        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("component.vocab_incompatibility.save_report_dialog_title"),
            f"vocab_incompatibility_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("=" * 70 + "\n")
                    f.write(tr("component.vocab_incompatibility.report_header") + "\n")
                    f.write("=" * 70 + "\n\n")

                    f.write(f"{tr('component.vocab_incompatibility.filename')} {self.package_info.get('filename', 'N/A')}\n")
                    f.write(f"{tr('component.vocab_incompatibility.package_id')} {self.package_info.get('package_id', 'N/A')}\n")
                    f.write(f"{tr('component.vocab_incompatibility.report_date')} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                    f.write("-" * 70 + "\n")
                    f.write(tr("component.vocab_incompatibility.incompatible_vocabs_header") + "\n")
                    f.write("-" * 70 + "\n\n")

                    for vocab in self.incompatible_vocabs:
                        f.write(f"{tr('component.vocab_incompatibility.report_vocab_name')} {vocab.get('name', 'N/A')}\n")
                        f.write(f"  {tr('component.vocab_incompatibility.report_current_version')} v{vocab.get('current_version', '0')}\n")
                        f.write(f"  {tr('component.vocab_incompatibility.report_required_version')} v{vocab.get('required_version', '0')}\n")
                        f.write(f"  {tr('component.vocab_incompatibility.report_impact')} {vocab.get('impact', 'N/A')}\n\n")

                from ui.components.toast import Toast
                Toast.show_toast(self.parent(), tr("component.vocab_incompatibility.report_saved", filename=filename), Toast.SUCCESS)
            except Exception as e:
                from ui.components.toast import Toast
                Toast.show_toast(self.parent(), tr("component.vocab_incompatibility.report_save_error", error=str(e)), Toast.ERROR)
