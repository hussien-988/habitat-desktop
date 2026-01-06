# -*- coding: utf-8 -*-
"""
Import wizard page with 4-step workflow.
"""

from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QFileDialog, QTableView,
    QHeaderView, QAbstractItemView, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

from app.config import Config
from repositories.database import Database
from services.import_service import ImportService, ImportStatus
from ui.components.table_models import ImportRecordsTableModel
from ui.components.loading_overlay import LoadingOverlay
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class ValidationWorker(QThread):
    """Background worker for validation."""

    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(list)  # records

    def __init__(self, import_service: ImportService):
        super().__init__()
        self.import_service = import_service

    def run(self):
        """Run validation in background."""
        def on_progress(current, total):
            self.progress.emit(current, total)

        records = self.import_service.validate_all(on_progress)
        self.finished.emit(records)


class CommitWorker(QThread):
    """Background worker for commit."""

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)  # ImportResult

    def __init__(self, import_service: ImportService):
        super().__init__()
        self.import_service = import_service

    def run(self):
        """Run commit in background."""
        def on_progress(current, total):
            self.progress.emit(current, total)

        result = self.import_service.commit(on_progress)
        self.finished.emit(result)


class ImportWizardPage(QWidget):
    """Import wizard with 4 steps: Select, Validate, Resolve, Commit."""

    import_completed = pyqtSignal(dict)  # Emits stats

    STEP_SELECT = 0
    STEP_VALIDATE = 1
    STEP_RESOLVE = 2
    STEP_COMMIT = 3

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_service = ImportService(db)

        self.current_step = 0
        self.selected_file = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup wizard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel(self.i18n.t("import_wizard"))
        header_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(header_label)

        # Step indicators
        self.steps_layout = QHBoxLayout()
        self.step_labels = []

        step_names = [
            ("1", self.i18n.t("select_file")),
            ("2", self.i18n.t("validate")),
            ("3", self.i18n.t("resolve")),
            ("4", self.i18n.t("commit")),
        ]

        for num, name in step_names:
            step_widget = QLabel(f"  {num}. {name}  ")
            step_widget.setObjectName("wizard-step")
            step_widget.setAlignment(Qt.AlignCenter)
            step_widget.setStyleSheet(f"""
                background-color: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_LIGHT};
                padding: 8px 16px;
                border-radius: 16px;
                font-weight: bold;
            """)
            self.step_labels.append(step_widget)
            self.steps_layout.addWidget(step_widget)

        self.steps_layout.addStretch()
        layout.addLayout(self.steps_layout)

        # Content area (stacked widget)
        self.content_stack = QStackedWidget()

        # Step 1: Select file
        self.content_stack.addWidget(self._create_select_step())

        # Step 2: Validate
        self.content_stack.addWidget(self._create_validate_step())

        # Step 3: Resolve
        self.content_stack.addWidget(self._create_resolve_step())

        # Step 4: Commit
        self.content_stack.addWidget(self._create_commit_step())

        layout.addWidget(self.content_stack)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()

        self.cancel_btn = QPushButton(self.i18n.t("cancel"))
        self.cancel_btn.setProperty("class", "secondary")
        self.cancel_btn.clicked.connect(self._on_cancel)
        nav_layout.addWidget(self.cancel_btn)

        self.prev_btn = QPushButton(f"← {self.i18n.t('previous')}")
        self.prev_btn.clicked.connect(self._on_previous)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton(f"{self.i18n.t('next')} →")
        self.next_btn.clicked.connect(self._on_next)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

        # Loading overlay
        self.loading = LoadingOverlay(self)

        # Update step display
        self._update_step_display()

    def _create_select_step(self) -> QWidget:
        """Create step 1: File selection."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 32, 16, 16)
        layout.setAlignment(Qt.AlignCenter)

        # Drop zone / file selector
        drop_zone = QFrame()
        drop_zone.setFixedSize(500, 200)
        drop_zone.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 2px dashed {Config.BORDER_COLOR};
                border-radius: 8px;
            }}
        """)

        drop_layout = QVBoxLayout(drop_zone)
        drop_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel("📁")
        icon_label.setStyleSheet("font-size: 48pt;")
        icon_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(icon_label)

        self.file_label = QLabel("Select a .uhc container file to import")
        self.file_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(self.file_label)

        browse_btn = QPushButton(f"📂 {self.i18n.t('browse')}")
        browse_btn.clicked.connect(self._on_browse)
        drop_layout.addWidget(browse_btn, alignment=Qt.AlignCenter)

        layout.addWidget(drop_zone)

        # Selected file info
        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("color: #666; margin-top: 16px;")
        self.file_info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.file_info_label)

        return widget

    def _create_validate_step(self) -> QWidget:
        """Create step 2: Validation results."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # Summary cards
        summary_layout = QHBoxLayout()

        self.valid_count = self._create_summary_card("Valid", "0", Config.SUCCESS_COLOR)
        summary_layout.addWidget(self.valid_count)

        self.warning_count = self._create_summary_card("Warnings", "0", Config.WARNING_COLOR)
        summary_layout.addWidget(self.warning_count)

        self.error_count = self._create_summary_card("Errors", "0", Config.ERROR_COLOR)
        summary_layout.addWidget(self.error_count)

        self.duplicate_count = self._create_summary_card("Duplicates", "0", Config.INFO_COLOR)
        summary_layout.addWidget(self.duplicate_count)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # Results table
        self.validation_table = QTableView()
        self.validation_table.setAlternatingRowColors(True)
        self.validation_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.validation_table.verticalHeader().setVisible(False)
        self.validation_table.horizontalHeader().setStretchLastSection(True)

        self.validation_model = ImportRecordsTableModel()
        self.validation_table.setModel(self.validation_model)

        layout.addWidget(self.validation_table)

        return widget

    def _create_summary_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a summary statistic card."""
        card = QFrame()
        card.setFixedSize(120, 80)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 8px;
                border-left: 4px solid {color};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"font-size: 20pt; font-weight: bold; color: {color};")
        layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(title_label)

        return card

    def _create_resolve_step(self) -> QWidget:
        """Create step 3: Conflict resolution."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # Info
        info_label = QLabel(
            "Review and resolve any conflicts or duplicates.\n"
            "For this prototype, records with warnings will be imported automatically."
        )
        info_label.setStyleSheet("color: #666; margin-bottom: 16px;")
        layout.addWidget(info_label)

        # Conflicts/duplicates table
        self.resolve_table = QTableView()
        self.resolve_table.setAlternatingRowColors(True)
        self.resolve_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resolve_table.verticalHeader().setVisible(False)
        self.resolve_table.horizontalHeader().setStretchLastSection(True)

        self.resolve_model = ImportRecordsTableModel()
        self.resolve_table.setModel(self.resolve_model)

        layout.addWidget(self.resolve_table)

        # Resolution actions
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        skip_btn = QPushButton("Skip All Duplicates")
        skip_btn.clicked.connect(self._on_skip_duplicates)
        actions_layout.addWidget(skip_btn)

        keep_btn = QPushButton("Import All (Keep New)")
        keep_btn.setProperty("class", "success")
        keep_btn.clicked.connect(self._on_keep_all)
        actions_layout.addWidget(keep_btn)

        layout.addLayout(actions_layout)

        return widget

    def _create_commit_step(self) -> QWidget:
        """Create step 4: Commit confirmation."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 32, 16, 16)
        layout.setAlignment(Qt.AlignCenter)

        # Commit summary
        self.commit_summary = QLabel("")
        self.commit_summary.setAlignment(Qt.AlignCenter)
        self.commit_summary.setStyleSheet("font-size: 14pt;")
        layout.addWidget(self.commit_summary)

        # Progress bar
        self.commit_progress = QProgressBar()
        self.commit_progress.setFixedWidth(400)
        self.commit_progress.setTextVisible(True)
        layout.addWidget(self.commit_progress, alignment=Qt.AlignCenter)

        # Result icon and message
        self.result_icon = QLabel("")
        self.result_icon.setStyleSheet("font-size: 48pt;")
        self.result_icon.setAlignment(Qt.AlignCenter)
        self.result_icon.hide()
        layout.addWidget(self.result_icon)

        self.result_message = QLabel("")
        self.result_message.setAlignment(Qt.AlignCenter)
        self.result_message.setStyleSheet("font-size: 12pt;")
        self.result_message.hide()
        layout.addWidget(self.result_message)

        return widget

    def _update_step_display(self):
        """Update step indicator display."""
        for i, label in enumerate(self.step_labels):
            if i < self.current_step:
                # Completed
                label.setStyleSheet(f"""
                    background-color: {Config.SUCCESS_COLOR};
                    color: white;
                    padding: 8px 16px;
                    border-radius: 16px;
                    font-weight: bold;
                """)
            elif i == self.current_step:
                # Active
                label.setStyleSheet(f"""
                    background-color: {Config.PRIMARY_COLOR};
                    color: white;
                    padding: 8px 16px;
                    border-radius: 16px;
                    font-weight: bold;
                """)
            else:
                # Pending
                label.setStyleSheet(f"""
                    background-color: {Config.BACKGROUND_COLOR};
                    color: {Config.TEXT_LIGHT};
                    padding: 8px 16px;
                    border-radius: 16px;
                    font-weight: bold;
                """)

        self.content_stack.setCurrentIndex(self.current_step)
        self.prev_btn.setEnabled(self.current_step > 0)

    def _on_browse(self):
        """Handle browse button click."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Import File",
            "",
            "UHC Container Files (*.uhc);;All Files (*.*)"
        )

        if filename:
            self.selected_file = Path(filename)
            self.file_label.setText(f"Selected: {self.selected_file.name}")
            self.file_info_label.setText(f"Path: {filename}")
            self.next_btn.setEnabled(True)

    def _on_previous(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_display()

    def _on_next(self):
        """Go to next step."""
        if self.current_step == self.STEP_SELECT:
            # Load and validate file
            self._start_validation()
        elif self.current_step == self.STEP_VALIDATE:
            self.current_step += 1
            self._show_resolve_step()
            self._update_step_display()
        elif self.current_step == self.STEP_RESOLVE:
            self.current_step += 1
            self._update_step_display()
            self._start_commit()

    def _start_validation(self):
        """Start file validation."""
        if not self.selected_file:
            return

        self.loading.show_loading(self.i18n.t("validating"))

        try:
            # Load file
            self.import_service.load_file(self.selected_file)

            # Run validation in background
            self.validation_worker = ValidationWorker(self.import_service)
            self.validation_worker.progress.connect(self._on_validation_progress)
            self.validation_worker.finished.connect(self._on_validation_complete)
            self.validation_worker.start()

        except Exception as e:
            self.loading.hide_loading()
            Toast.show(self, f"Error loading file: {str(e)}", Toast.ERROR)

    @pyqtSlot(int, int)
    def _on_validation_progress(self, current: int, total: int):
        """Handle validation progress update."""
        pct = int((current / total) * 100) if total > 0 else 0
        self.loading.update_progress(pct, f"Validating record {current}/{total}")

    @pyqtSlot(list)
    def _on_validation_complete(self, records):
        """Handle validation completion."""
        self.loading.hide_loading()

        # Update summary
        summary = self.import_service.get_validation_summary()

        self.valid_count.findChild(QLabel, "value").setText(str(summary["valid"]))
        self.warning_count.findChild(QLabel, "value").setText(str(summary["warnings"]))
        self.error_count.findChild(QLabel, "value").setText(str(summary["errors"]))
        self.duplicate_count.findChild(QLabel, "value").setText(str(summary["duplicates"]))

        # Update table
        self.validation_model.set_records(records)

        # Move to next step
        self.current_step = self.STEP_VALIDATE
        self._update_step_display()
        self.next_btn.setEnabled(True)

    def _show_resolve_step(self):
        """Show resolve step with conflicts/duplicates."""
        # Filter to show only items needing resolution
        items = self.import_service.get_records_by_status(ImportStatus.DUPLICATE)
        items += self.import_service.get_records_by_status(ImportStatus.WARNING)
        self.resolve_model.set_records(items)

        # Update commit summary
        summary = self.import_service.get_validation_summary()
        total_to_import = summary["valid"] + summary["warnings"]
        self.commit_summary.setText(
            f"Ready to import {total_to_import} records.\n"
            f"({summary['errors']} errors will be skipped)"
        )

    def _on_skip_duplicates(self):
        """Skip all duplicate records."""
        for record in self.import_service.get_records_by_status(ImportStatus.DUPLICATE):
            self.import_service.resolve_record(record.record_id, "skip")
        Toast.show(self, "Duplicates will be skipped", Toast.INFO)

    def _on_keep_all(self):
        """Keep all new records."""
        for record in self.import_service.get_records_by_status(ImportStatus.DUPLICATE):
            self.import_service.resolve_record(record.record_id, "keep_new")
        Toast.show(self, "All records will be imported", Toast.INFO)

    def _start_commit(self):
        """Start commit process."""
        self.commit_progress.setValue(0)
        self.result_icon.hide()
        self.result_message.hide()

        self.commit_worker = CommitWorker(self.import_service)
        self.commit_worker.progress.connect(self._on_commit_progress)
        self.commit_worker.finished.connect(self._on_commit_complete)
        self.commit_worker.start()

    @pyqtSlot(int, int)
    def _on_commit_progress(self, current: int, total: int):
        """Handle commit progress update."""
        pct = int((current / total) * 100) if total > 0 else 0
        self.commit_progress.setValue(pct)

    @pyqtSlot(object)
    def _on_commit_complete(self, result):
        """Handle commit completion."""
        self.commit_progress.setValue(100)

        if result.success:
            self.result_icon.setText("✅")
            self.result_message.setText(
                f"Successfully imported {result.imported} records!\n"
                f"(Skipped: {result.skipped}, Warnings: {result.warnings})"
            )
            self.result_message.setStyleSheet(f"font-size: 12pt; color: {Config.SUCCESS_COLOR};")
        else:
            self.result_icon.setText("⚠️")
            self.result_message.setText(
                f"Import completed with issues.\n"
                f"Imported: {result.imported}, Failed: {result.failed}"
            )
            self.result_message.setStyleSheet(f"font-size: 12pt; color: {Config.WARNING_COLOR};")

        self.result_icon.show()
        self.result_message.show()

        self.next_btn.setText(self.i18n.t("finish"))
        self.next_btn.clicked.disconnect()
        self.next_btn.clicked.connect(self._on_finish)

    def _on_finish(self):
        """Handle finish button click."""
        self.import_completed.emit({
            "imported": self.commit_progress.value()
        })
        self._reset_wizard()

    def _on_cancel(self):
        """Handle cancel button click."""
        self._reset_wizard()

    def _reset_wizard(self):
        """Reset wizard to initial state."""
        self.current_step = 0
        self.selected_file = None
        self.file_label.setText("Select a .uhc container file to import")
        self.file_info_label.setText("")
        self.next_btn.setEnabled(False)
        self.next_btn.setText(f"{self.i18n.t('next')} →")

        # Reconnect next button
        try:
            self.next_btn.clicked.disconnect()
        except:
            pass
        self.next_btn.clicked.connect(self._on_next)

        # Clear service
        self.import_service.clear()

        self._update_step_display()

    def refresh(self, data=None):
        """Refresh the page."""
        self._reset_wizard()

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        pass  # Would update all labels
