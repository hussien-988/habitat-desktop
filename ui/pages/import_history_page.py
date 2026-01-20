# -*- coding: utf-8 -*-
"""
Import History / Audit Trail Page (UC-003 Post-conditions)
Displays complete history of all imports with detailed information.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QLineEdit, QComboBox, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from app.config import Config
from repositories.database import Database
from ui.components.commit_report_dialog import CommitReportDialog
from ui.components.toast import Toast
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from datetime import datetime


class ImportHistoryPage(QWidget):
    """
    Import History / Audit Trail Page.

    Shows complete audit trail of all imports (UC-003 Post-conditions):
    - Import timestamp
    - Package ID
    - Original filename
    - Status (Success/Partial/Failed)
    - Records imported
    - Archive location
    - View detailed report for each import
    """

    def __init__(self, db: Database = None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_history = []

        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        """Setup the import history UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("📜 سجل الاستيرادات")
        # Use centralized font utility: 18pt Bold
        title_font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold, letter_spacing=0)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.setStyleSheet(StyleManager.button_primary())
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Filters
        filters_frame = QFrame()
        filters_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        filters_layout = QHBoxLayout(filters_frame)

        # Search by filename
        search_label = QLabel("🔍 بحث:")
        filters_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث بالملف أو معرف الحزمة...")
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(self._on_search)
        filters_layout.addWidget(self.search_input)

        # Status filter
        status_label = QLabel("الحالة:")
        filters_layout.addWidget(status_label)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["الكل", "ناجح", "جزئي", "فشل"])
        self.status_filter.setFixedWidth(120)
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.status_filter)

        filters_layout.addStretch()

        layout.addWidget(filters_frame)

        # Statistics cards
        stats_layout = QHBoxLayout()

        self.total_imports_card = self._create_stat_card("📦 إجمالي الاستيرادات", "0", Config.INFO_COLOR)
        stats_layout.addWidget(self.total_imports_card)

        self.success_card = self._create_stat_card("✅ ناجح", "0", Config.SUCCESS_COLOR)
        stats_layout.addWidget(self.success_card)

        self.partial_card = self._create_stat_card("⚠️ جزئي", "0", Config.WARNING_COLOR)
        stats_layout.addWidget(self.partial_card)

        self.failed_card = self._create_stat_card("❌ فشل", "0", Config.ERROR_COLOR)
        stats_layout.addWidget(self.failed_card)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "التاريخ والوقت",
            "معرف الحزمة",
            "اسم الملف",
            "الحالة",
            "السجلات المستوردة",
            "التخطيات",
            "الفشل",
            "الإجراءات"
        ])

        # Table styling
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setStretchLastSection(False)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Filename column

        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                gridline-color: {Config.BORDER_COLOR};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
            }}
            QHeaderView::section {{
                background-color: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_COLOR};
                padding: 10px;
                border: none;
                border-bottom: 2px solid {Config.PRIMARY_COLOR};
                font-weight: bold;
            }}
        """)

        layout.addWidget(self.history_table)

        # Empty state
        self.empty_state = QLabel("📭 لا توجد استيرادات حتى الآن")
        self.empty_state.setAlignment(Qt.AlignCenter)
        self.empty_state.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: 14pt;
            padding: 40px;
        """)
        self.empty_state.hide()
        layout.addWidget(self.empty_state)

    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a statistics card."""
        card = QFrame()
        card.setFixedHeight(90)
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
        value_label.setObjectName("stat_value")
        # 22pt Bold for stat values
        value_font = create_font(size=22, weight=QFont.Bold, letter_spacing=0)
        value_label.setFont(value_font)
        value_label.setStyleSheet(f"color: {color};")
        card_layout.addWidget(value_label)

        title_label = QLabel(title)
        # 9pt Normal for stat titles
        title_font = create_font(size=9, weight=QFont.Normal, letter_spacing=0)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        card_layout.addWidget(title_label)

        return card

    def refresh(self, data=None):
        """Refresh the import history from database."""
        if not self.db:
            # Mock data for testing
            self._load_mock_data()
            return

        try:
            # Load from audit_log table
            cursor = self.db.connection.cursor()
            cursor.execute("""
                SELECT
                    audit_log_id,
                    package_id,
                    original_filename,
                    timestamp,
                    status,
                    records_imported,
                    records_skipped,
                    records_failed,
                    archive_path
                FROM audit_log
                WHERE action = 'import'
                ORDER BY timestamp DESC
            """)

            self.import_history = []
            for row in cursor.fetchall():
                self.import_history.append({
                    'audit_log_id': row[0],
                    'package_id': row[1],
                    'filename': row[2],
                    'timestamp': row[3],
                    'status': row[4],
                    'imported': row[5] or 0,
                    'skipped': row[6] or 0,
                    'failed': row[7] or 0,
                    'archive_path': row[8]
                })

            self._update_display()

        except Exception as e:
            print(f"Error loading import history: {e}")

            # Show error dialog instead of toast
            from ui.components.dialogs import ErrorDialog
            ErrorDialog(
                title="⚠️ خطأ في تحميل السجل",
                message=f"حدث خطأ أثناء تحميل سجل الاستيرادات من قاعدة البيانات:\n\n{str(e)}\n\nسيتم عرض بيانات تجريبية للتوضيح.",
                parent=self
            ).exec_()

            self._load_mock_data()

    def _load_mock_data(self):
        """Load mock data for testing."""
        self.import_history = [
            {
                'audit_log_id': 'AL-001',
                'package_id': 'PKG-20250107-001',
                'filename': 'survey_data_2025_01_07.uhc',
                'timestamp': '2025-01-07 14:30:00',
                'status': 'success',
                'imported': 150,
                'skipped': 5,
                'failed': 0,
                'archive_path': '/data/archive/2025/01/07/'
            },
            {
                'audit_log_id': 'AL-002',
                'package_id': 'PKG-20250106-002',
                'filename': 'survey_batch_02.uhc',
                'timestamp': '2025-01-06 11:15:00',
                'status': 'partial',
                'imported': 89,
                'skipped': 12,
                'failed': 3,
                'archive_path': '/data/archive/2025/01/06/'
            },
            {
                'audit_log_id': 'AL-003',
                'package_id': 'PKG-20250105-001',
                'filename': 'test_import.uhc',
                'timestamp': '2025-01-05 09:00:00',
                'status': 'failed',
                'imported': 0,
                'skipped': 0,
                'failed': 50,
                'archive_path': '/data/archive/2025/01/05/'
            }
        ]

        self._update_display()

    def _update_display(self):
        """Update the display with current import history."""
        # Update statistics
        total = len(self.import_history)
        success_count = sum(1 for item in self.import_history if item['status'] == 'success')
        partial_count = sum(1 for item in self.import_history if item['status'] == 'partial')
        failed_count = sum(1 for item in self.import_history if item['status'] == 'failed')

        self.total_imports_card.findChild(QLabel, "stat_value").setText(str(total))
        self.success_card.findChild(QLabel, "stat_value").setText(str(success_count))
        self.partial_card.findChild(QLabel, "stat_value").setText(str(partial_count))
        self.failed_card.findChild(QLabel, "stat_value").setText(str(failed_count))

        # Update table
        self._populate_table(self.import_history)

        # Show/hide empty state
        if total == 0:
            self.history_table.hide()
            self.empty_state.show()
        else:
            self.history_table.show()
            self.empty_state.hide()

    def _populate_table(self, history_items: list):
        """Populate the history table."""
        self.history_table.setRowCount(len(history_items))

        for row, item in enumerate(history_items):
            # Timestamp
            timestamp_item = QTableWidgetItem(item['timestamp'])
            timestamp_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(row, 0, timestamp_item)

            # Package ID
            package_item = QTableWidgetItem(item['package_id'])
            package_item.setTextAlignment(Qt.AlignCenter)
            # 9pt monospace for package IDs
            package_font = create_font(size=9, weight=QFont.Normal, letter_spacing=0)
            package_item.setFont(package_font)
            self.history_table.setItem(row, 1, package_item)

            # Filename
            filename_item = QTableWidgetItem(item['filename'])
            self.history_table.setItem(row, 2, filename_item)

            # Status
            status = item['status']
            status_text = {
                'success': '✅ ناجح',
                'partial': '⚠️ جزئي',
                'failed': '❌ فشل'
            }.get(status, status)
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)

            status_color = {
                'success': QColor(Config.SUCCESS_COLOR),
                'partial': QColor(Config.WARNING_COLOR),
                'failed': QColor(Config.ERROR_COLOR)
            }.get(status, QColor(Config.TEXT_COLOR))
            status_item.setForeground(status_color)
            # 10pt Bold for status
            status_font = create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0)
            status_item.setFont(status_font)
            self.history_table.setItem(row, 3, status_item)

            # Imported count
            imported_item = QTableWidgetItem(str(item['imported']))
            imported_item.setTextAlignment(Qt.AlignCenter)
            imported_item.setForeground(QColor(Config.SUCCESS_COLOR))
            self.history_table.setItem(row, 4, imported_item)

            # Skipped count
            skipped_item = QTableWidgetItem(str(item['skipped']))
            skipped_item.setTextAlignment(Qt.AlignCenter)
            skipped_item.setForeground(QColor(Config.TEXT_LIGHT))
            self.history_table.setItem(row, 5, skipped_item)

            # Failed count
            failed_item = QTableWidgetItem(str(item['failed']))
            failed_item.setTextAlignment(Qt.AlignCenter)
            failed_item.setForeground(QColor(Config.ERROR_COLOR))
            self.history_table.setItem(row, 6, failed_item)

            # Actions button
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)

            view_btn = QPushButton("📄 عرض التقرير")
            view_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Config.INFO_COLOR};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: 600;
                    font-size: 9pt;
                }}
                QPushButton:hover {{
                    background-color: #0284C7;
                }}
            """)
            view_btn.clicked.connect(lambda checked, i=item: self._on_view_report(i))
            actions_layout.addWidget(view_btn)

            self.history_table.setCellWidget(row, 7, actions_widget)

        self.history_table.resizeRowsToContents()

    def _on_view_report(self, import_item: dict):
        """View detailed report for an import."""
        # Reconstruct commit_result and import_metadata for the report dialog
        commit_result = {
            'success': import_item['status'] == 'success',
            'imported': import_item['imported'],
            'skipped': import_item['skipped'],
            'failed': import_item['failed'],
            'warnings': 0,  # Could be stored in audit_log
            'records_by_type': {},  # Could be stored as JSON in audit_log
            'duration_seconds': 0
        }

        import_metadata = {
            'original_file': import_item['filename'],
            'archive_path': import_item['archive_path'],
            'package_id': import_item['package_id'],
            'audit_log_id': import_item['audit_log_id']
        }

        # Show commit report dialog
        report_dialog = CommitReportDialog(
            commit_result=commit_result,
            import_metadata=import_metadata,
            parent=self
        )
        report_dialog.exec_()

    def _on_search(self):
        """Handle search input."""
        search_text = self.search_input.text().lower()
        filtered = [
            item for item in self.import_history
            if search_text in item['filename'].lower() or search_text in item['package_id'].lower()
        ]
        self._populate_table(filtered)

    def _on_filter_changed(self):
        """Handle status filter change."""
        status_filter = self.status_filter.currentText()

        if status_filter == "الكل":
            filtered = self.import_history
        else:
            status_map = {
                "ناجح": "success",
                "جزئي": "partial",
                "فشل": "failed"
            }
            status = status_map.get(status_filter)
            filtered = [item for item in self.import_history if item['status'] == status]

        self._populate_table(filtered)

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        pass  # Would update all labels
