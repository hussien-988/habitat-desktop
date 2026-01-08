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
from ui.components.validation_error_dialog import ValidationErrorDialog
from ui.components.vocabulary_incompatibility_dialog import VocabularyIncompatibilityDialog
from ui.components.commit_report_dialog import CommitReportDialog
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

    def _highlight_next_button(self):
        """Highlight Next button in green when ready to proceed."""
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 32px;
                font-weight: 600;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                background-color: #16A34A;
            }}
            QPushButton:disabled {{
                background-color: #D1D5DB;
                color: #9CA3AF;
            }}
        """)

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

        # RTL-aware navigation arrows (FR-D-1.2)
        # In RTL layout, arrows should point in the correct direction
        self.prev_btn = QPushButton(f"→ {self.i18n.t('previous')}")  # Right arrow for previous in RTL
        self.prev_btn.clicked.connect(self._on_previous)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton(f"{self.i18n.t('next')} ←")  # Left arrow for next in RTL
        self.next_btn.clicked.connect(self._on_next)
        self.next_btn.setEnabled(False)
        # Set consistent button style
        self.next_btn.setMinimumHeight(45)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.TEXT_LIGHT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 32px;
                font-weight: 600;
                font-size: 12pt;
            }}
            QPushButton:disabled {{
                background-color: #D1D5DB;
                color: #9CA3AF;
            }}
        """)
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
        """Create step 3: Conflict resolution per UC-003 S15/S15a."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with summary
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #FEF3C7;
                border: 1px solid #F59E0B;
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(8)

        info_label = QLabel(
            "⚠️ مراجعة التعارضات والمكررات\n"
            "يرجى مراجعة السجلات التالية وتحديد الإجراء المناسب لكل منها"
        )
        info_label.setStyleSheet("color: #92400E; font-weight: bold;")
        info_label.setWordWrap(True)
        header_layout.addWidget(info_label)

        # Quick stats
        self.resolve_stats_label = QLabel("")
        self.resolve_stats_label.setStyleSheet("color: #B45309;")
        header_layout.addWidget(self.resolve_stats_label)

        layout.addWidget(header_frame)

        # Tabs for different conflict types
        from PyQt5.QtWidgets import QTabWidget
        self.resolve_tabs = QTabWidget()

        # Tab 1: Duplicates
        duplicates_tab = QWidget()
        dup_layout = QVBoxLayout(duplicates_tab)

        self.duplicates_table = QTableView()
        self.duplicates_table.setAlternatingRowColors(True)
        self.duplicates_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.duplicates_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.duplicates_table.verticalHeader().setVisible(False)
        self.duplicates_table.horizontalHeader().setStretchLastSection(True)
        self.duplicates_table.clicked.connect(self._on_duplicate_selected)

        self.duplicates_model = ImportRecordsTableModel()
        self.duplicates_table.setModel(self.duplicates_model)
        dup_layout.addWidget(self.duplicates_table)

        # Duplicate comparison panel
        compare_frame = QFrame()
        compare_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
            }}
        """)
        compare_frame.setFixedHeight(150)
        compare_layout = QHBoxLayout(compare_frame)

        # New record preview
        new_frame = QFrame()
        new_layout = QVBoxLayout(new_frame)
        new_title = QLabel("📥 السجل الجديد")
        new_title.setStyleSheet(f"font-weight: bold; color: {Config.PRIMARY_COLOR};")
        new_layout.addWidget(new_title)
        self.new_record_preview = QLabel("اختر سجلاً للمقارنة")
        self.new_record_preview.setStyleSheet("color: #666;")
        self.new_record_preview.setWordWrap(True)
        new_layout.addWidget(self.new_record_preview)
        new_layout.addStretch()
        compare_layout.addWidget(new_frame)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setStyleSheet(f"background-color: {Config.BORDER_COLOR};")
        compare_layout.addWidget(divider)

        # Existing record preview
        existing_frame = QFrame()
        existing_layout = QVBoxLayout(existing_frame)
        existing_title = QLabel("📋 السجل الموجود")
        existing_title.setStyleSheet(f"font-weight: bold; color: {Config.WARNING_COLOR};")
        existing_layout.addWidget(existing_title)
        self.existing_record_preview = QLabel("--")
        self.existing_record_preview.setStyleSheet("color: #666;")
        self.existing_record_preview.setWordWrap(True)
        existing_layout.addWidget(self.existing_record_preview)
        existing_layout.addStretch()
        compare_layout.addWidget(existing_frame)

        dup_layout.addWidget(compare_frame)

        # Duplicate resolution buttons
        dup_actions = QHBoxLayout()
        dup_actions.addStretch()

        self.skip_dup_btn = QPushButton("⏭️ تخطي هذا السجل")
        self.skip_dup_btn.clicked.connect(lambda: self._resolve_current_duplicate("skip"))
        self.skip_dup_btn.setEnabled(False)
        dup_actions.addWidget(self.skip_dup_btn)

        self.keep_existing_btn = QPushButton("📋 الإبقاء على الموجود")
        self.keep_existing_btn.clicked.connect(lambda: self._resolve_current_duplicate("keep_existing"))
        self.keep_existing_btn.setEnabled(False)
        dup_actions.addWidget(self.keep_existing_btn)

        self.keep_new_btn = QPushButton("📥 استخدام الجديد")
        self.keep_new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }}
        """)
        self.keep_new_btn.clicked.connect(lambda: self._resolve_current_duplicate("keep_new"))
        self.keep_new_btn.setEnabled(False)
        dup_actions.addWidget(self.keep_new_btn)

        dup_layout.addLayout(dup_actions)

        self.resolve_tabs.addTab(duplicates_tab, f"📋 المكررات (0)")

        # Tab 2: Warnings
        warnings_tab = QWidget()
        warn_layout = QVBoxLayout(warnings_tab)

        self.warnings_table = QTableView()
        self.warnings_table.setAlternatingRowColors(True)
        self.warnings_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.warnings_table.verticalHeader().setVisible(False)
        self.warnings_table.horizontalHeader().setStretchLastSection(True)

        self.warnings_model = ImportRecordsTableModel()
        self.warnings_table.setModel(self.warnings_model)
        warn_layout.addWidget(self.warnings_table)

        warn_info = QLabel("💡 السجلات ذات التحذيرات سيتم استيرادها مع تسجيل التحذيرات")
        warn_info.setStyleSheet(f"color: {Config.WARNING_COLOR}; padding: 8px;")
        warn_layout.addWidget(warn_info)

        self.resolve_tabs.addTab(warnings_tab, f"⚠️ تحذيرات (0)")

        layout.addWidget(self.resolve_tabs)

        # Bulk actions
        bulk_frame = QFrame()
        bulk_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #F8FAFC;
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        bulk_layout = QHBoxLayout(bulk_frame)

        bulk_label = QLabel("إجراءات جماعية:")
        bulk_label.setStyleSheet("font-weight: bold;")
        bulk_layout.addWidget(bulk_label)

        skip_all_btn = QPushButton("تخطي كل المكررات")
        skip_all_btn.clicked.connect(self._on_skip_duplicates)
        bulk_layout.addWidget(skip_all_btn)

        keep_all_btn = QPushButton("استيراد الكل (الجديد)")
        keep_all_btn.setProperty("class", "success")
        keep_all_btn.clicked.connect(self._on_keep_all)
        bulk_layout.addWidget(keep_all_btn)

        bulk_layout.addStretch()

        layout.addWidget(bulk_frame)

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
        """Start file validation (UC-003 S12a-S12c)."""
        if not self.selected_file:
            return

        self.loading.show_loading(self.i18n.t("validating"))

        try:
            # Load file
            self.import_service.load_file(self.selected_file)

            # Check for validation errors (UC-003 S12b - Invalid signature/hash)
            validation_error = self.import_service.get_validation_error()
            if validation_error:
                self.loading.hide_loading()

                # Show detailed validation error dialog (S12b)
                error_dialog = ValidationErrorDialog(
                    error_type=validation_error.get('error_type', 'invalid_signature'),
                    error_details=validation_error,
                    parent=self
                )
                error_dialog.exec_()

                # Stop the import process
                self._reset_wizard()
                return

            # Check for vocabulary incompatibilities (UC-003 S12c)
            incompatible_vocabs = self.import_service.get_incompatible_vocabularies()
            if incompatible_vocabs:
                self.loading.hide_loading()

                # Show vocabulary incompatibility dialog (S12c)
                package_info = {
                    'filename': self.selected_file.name,
                    'package_id': self.import_service.get_package_id(),
                    'timestamp': self.import_service.get_package_timestamp()
                }
                vocab_dialog = VocabularyIncompatibilityDialog(
                    incompatible_vocabs=incompatible_vocabs,
                    package_info=package_info,
                    parent=self
                )
                vocab_dialog.exec_()

                # Stop the import process
                self._reset_wizard()
                return

            # Run validation in background
            self.validation_worker = ValidationWorker(self.import_service)
            self.validation_worker.progress.connect(self._on_validation_progress)
            self.validation_worker.finished.connect(self._on_validation_complete)
            self.validation_worker.start()

        except Exception as e:
            self.loading.hide_loading()

            # Print full error to terminal for debugging
            import traceback
            logger.error(f"خطأ في تحميل ملف الاستيراد: {self.selected_file}")
            logger.error(f"نوع الخطأ: {type(e).__name__}")
            logger.error(f"رسالة الخطأ: {str(e)}")
            logger.error("التفاصيل الكاملة:")
            logger.error(traceback.format_exc())

            # Translate error to simple Arabic message for user
            user_message = self._get_user_friendly_error(str(e))

            # Show simple error dialog to user
            from ui.components.dialogs import ErrorDialog
            error_dialog = ErrorDialog(
                title="⚠️ خطأ في تحميل الملف",
                message=user_message,
                parent=self
            )
            error_dialog.exec_()

    def _get_user_friendly_error(self, error_text: str) -> str:
        """تحويل رسالة الخطأ التقنية إلى رسالة بسيطة للمستخدم"""
        error_lower = error_text.lower()

        # Check for common errors and return simple Arabic message
        if "no such file" in error_lower or "file not found" in error_lower:
            return "❌ الملف غير موجود\n\nالرجاء التأكد من اختيار ملف .uhc صحيح"

        elif "permission" in error_lower:
            return "❌ لا يوجد صلاحية للوصول للملف\n\nالرجاء التحقق من صلاحيات الملف"

        elif "not a database" in error_lower or "malformed" in error_lower:
            return "❌ الملف تالف أو غير صحيح\n\nالرجاء التأكد من أن الملف هو .uhc صحيح"

        elif "manifest" in error_lower:
            return "❌ الملف لا يحتوي على البيانات المطلوبة\n\nتأكد من أن الملف تم تصديره بشكل صحيح من التابلت"

        else:
            return "❌ حدث خطأ أثناء قراءة الملف\n\nالرجاء التحقق من الملف والمحاولة مرة أخرى\n\n💡 تم تسجيل تفاصيل الخطأ في السجلات"

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

        # Enable and highlight Next button
        self.next_btn.setEnabled(True)
        self._highlight_next_button()

    def _show_resolve_step(self):
        """Show resolve step with conflicts/duplicates per UC-003 S15/S15a."""
        # Get duplicates and warnings
        duplicates = self.import_service.get_records_by_status(ImportStatus.DUPLICATE)
        warnings = self.import_service.get_records_by_status(ImportStatus.WARNING)

        # Update duplicates table and tab
        self.duplicates_model.set_records(duplicates)
        self.resolve_tabs.setTabText(0, f"📋 المكررات ({len(duplicates)})")

        # Update warnings table and tab
        self.warnings_model.set_records(warnings)
        self.resolve_tabs.setTabText(1, f"⚠️ تحذيرات ({len(warnings)})")

        # Update stats label
        summary = self.import_service.get_validation_summary()
        self.resolve_stats_label.setText(
            f"📊 الإجمالي: {summary['total']} | "
            f"✅ صالح: {summary['valid']} | "
            f"⚠️ تحذيرات: {summary['warnings']} | "
            f"📋 مكررات: {summary['duplicates']} | "
            f"❌ أخطاء: {summary['errors']}"
        )

        # Update commit summary
        total_to_import = summary["valid"] + summary["warnings"]
        self.commit_summary.setText(
            f"جاهز لاستيراد {total_to_import} سجل.\n"
            f"(سيتم تخطي {summary['errors']} سجل بسبب أخطاء)"
        )

        # Track current duplicate for individual resolution
        self._current_duplicate_record = None

        # If no duplicates or warnings, show success message AFTER the page is shown
        if len(duplicates) == 0 and len(warnings) == 0:
            # Enable and highlight Next button
            self.next_btn.setEnabled(True)
            self._highlight_next_button()

            # Show dialog after page renders
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._show_no_conflicts_dialog())

    def _show_no_conflicts_dialog(self):
        """Show dialog when there are no conflicts."""
        from ui.components.dialogs import InfoDialog
        InfoDialog(
            title="✅ لا توجد تعارضات",
            message="تم التحقق من جميع السجلات بنجاح!\n\n"
                    "لا توجد مكررات أو تحذيرات تحتاج إلى معالجة.\n\n"
                    "يمكنك الضغط على زر 'التالي' للمتابعة إلى مرحلة الحفظ.",
            parent=self
        ).exec_()

    def _on_duplicate_selected(self, index):
        """Handle duplicate record selection for comparison."""
        row = index.row()
        duplicates = self.import_service.get_records_by_status(ImportStatus.DUPLICATE)

        if 0 <= row < len(duplicates):
            record = duplicates[row]
            self._current_duplicate_record = record

            # Update new record preview
            preview_text = self._format_record_preview(record)
            self.new_record_preview.setText(preview_text)

            # Update existing record preview
            if record.duplicate_of:
                self.existing_record_preview.setText(
                    f"ID: {record.duplicate_of}\n"
                    f"(سجل موجود في قاعدة البيانات)"
                )
            else:
                self.existing_record_preview.setText("--")

            # Enable action buttons
            self.skip_dup_btn.setEnabled(True)
            self.keep_existing_btn.setEnabled(True)
            self.keep_new_btn.setEnabled(True)

    def _format_record_preview(self, record) -> str:
        """Format record data for preview display."""
        lines = [f"النوع: {record.record_type}", f"المعرف: {record.record_id}"]

        # Add key fields based on record type
        data = record.data
        if record.record_type == "building":
            if "building_id" in data:
                lines.append(f"رقم المبنى: {data['building_id']}")
            if "building_type" in data:
                lines.append(f"نوع المبنى: {data['building_type']}")
        elif record.record_type == "person":
            name_parts = []
            if "first_name_ar" in data:
                name_parts.append(data["first_name_ar"])
            if "last_name_ar" in data:
                name_parts.append(data["last_name_ar"])
            if name_parts:
                lines.append(f"الاسم: {' '.join(name_parts)}")
            if "national_id" in data:
                lines.append(f"الرقم الوطني: {data['national_id']}")
        elif record.record_type == "unit":
            if "unit_id" in data:
                lines.append(f"رقم الوحدة: {data['unit_id']}")
            if "unit_type" in data:
                lines.append(f"نوع الوحدة: {data['unit_type']}")

        return "\n".join(lines)

    def _resolve_current_duplicate(self, resolution: str):
        """Resolve the currently selected duplicate record."""
        if not self._current_duplicate_record:
            return

        record_id = self._current_duplicate_record.record_id
        self.import_service.resolve_record(record_id, resolution)

        # Show feedback
        resolution_text = {
            "skip": "تم تخطي السجل",
            "keep_existing": "سيتم الإبقاء على السجل الموجود",
            "keep_new": "سيتم استخدام السجل الجديد"
        }.get(resolution, resolution)

        # Show success message with InfoDialog
        from ui.components.dialogs import InfoDialog
        info_dialog = InfoDialog(
            title="✅ تم حفظ الاختيار",
            message=resolution_text,
            parent=self
        )
        info_dialog.exec_()

        # Refresh the duplicates list
        duplicates = self.import_service.get_records_by_status(ImportStatus.DUPLICATE)
        self.duplicates_model.set_records(duplicates)
        self.resolve_tabs.setTabText(0, f"📋 المكررات ({len(duplicates)})")

        # Reset selection
        self._current_duplicate_record = None
        self.new_record_preview.setText("اختر سجلاً للمقارنة")
        self.existing_record_preview.setText("--")
        self.skip_dup_btn.setEnabled(False)
        self.keep_existing_btn.setEnabled(False)
        self.keep_new_btn.setEnabled(False)

        # Update commit summary
        summary = self.import_service.get_validation_summary()
        total_to_import = summary["valid"] + summary["warnings"]
        self.commit_summary.setText(
            f"جاهز لاستيراد {total_to_import} سجل.\n"
            f"(سيتم تخطي {summary['errors']} سجل بسبب أخطاء)"
        )

    def _on_skip_duplicates(self):
        """Skip all duplicate records."""
        duplicates = self.import_service.get_records_by_status(ImportStatus.DUPLICATE)
        count = len(duplicates)

        if count == 0:
            from ui.components.dialogs import InfoDialog
            InfoDialog(
                title="📋 لا توجد مكررات",
                message="لا توجد سجلات مكررة للتخطي",
                parent=self
            ).exec_()
            return

        # Ask for confirmation
        from ui.components.dialogs import ConfirmDialog
        confirm = ConfirmDialog(
            title="⚠️ تأكيد التخطي الجماعي",
            message=f"هل أنت متأكد من تخطي جميع السجلات المكررة؟\n\nسيتم تخطي {count} سجل.",
            parent=self
        )
        if confirm.exec_():
            for record in duplicates:
                self.import_service.resolve_record(record.record_id, "skip")

            # Show success message
            from ui.components.dialogs import InfoDialog
            InfoDialog(
                title="✅ تم التخطي",
                message=f"تم تخطي {count} سجل مكرر بنجاح",
                parent=self
            ).exec_()

            # Refresh display
            self._show_resolve_step()

    def _on_keep_all(self):
        """Keep all new records."""
        duplicates = self.import_service.get_records_by_status(ImportStatus.DUPLICATE)
        count = len(duplicates)

        if count == 0:
            from ui.components.dialogs import InfoDialog
            InfoDialog(
                title="📋 لا توجد مكررات",
                message="لا توجد سجلات مكررة",
                parent=self
            ).exec_()
            return

        # Ask for confirmation
        from ui.components.dialogs import ConfirmDialog
        confirm = ConfirmDialog(
            title="⚠️ تأكيد الاستيراد الجماعي",
            message=f"هل أنت متأكد من استيراد جميع السجلات الجديدة (استبدال المكررات)؟\n\nسيتم استيراد {count} سجل جديد.",
            parent=self
        )
        if confirm.exec_():
            for record in duplicates:
                self.import_service.resolve_record(record.record_id, "keep_new")

            # Show success message
            from ui.components.dialogs import InfoDialog
            InfoDialog(
                title="✅ تم الحفظ",
                message=f"تم تحديد {count} سجل للاستيراد بنجاح",
                parent=self
            ).exec_()

            # Refresh display
            self._show_resolve_step()

    def _start_commit(self):
        """Start commit process."""
        # Get summary for confirmation dialog
        summary = self.import_service.get_validation_summary()
        total_to_import = summary["valid"] + summary["warnings"]

        # Ask for confirmation before committing
        from ui.components.dialogs import ConfirmDialog
        confirm = ConfirmDialog(
            title="⚠️ تأكيد الاستيراد النهائي",
            message=f"هل أنت متأكد من استيراد البيانات إلى قاعدة البيانات؟\n\n"
                    f"📊 سيتم استيراد: {total_to_import} سجل\n"
                    f"⏭️ سيتم تخطي: {summary['errors']} سجل\n\n"
                    f"⚠️ لا يمكن التراجع عن هذه العملية!",
            parent=self
        )

        if not confirm.exec_():
            # User cancelled
            return

        # User confirmed, proceed with commit
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
        """Handle commit completion (UC-003 S17 + Post-conditions)."""
        self.commit_progress.setValue(100)

        # Prepare commit result data for detailed report (UC-003 S17)
        commit_result = {
            'success': result.success,
            'imported': result.imported,
            'skipped': result.skipped,
            'warnings': result.warnings,
            'failed': getattr(result, 'failed', 0),
            'records_by_type': getattr(result, 'records_by_type', {}),
            'duration_seconds': getattr(result, 'duration_seconds', 0)
        }

        # Prepare archive and audit metadata (Post-conditions)
        import_metadata = {
            'original_file': str(self.selected_file.name) if self.selected_file else 'N/A',
            'archive_path': getattr(result, 'archive_path', '/data/archive/'),
            'package_id': self.import_service.get_package_id() if hasattr(self.import_service, 'get_package_id') else 'N/A',
            'audit_log_id': getattr(result, 'audit_log_id', 'N/A')
        }

        # Show success message first
        from ui.components.dialogs import InfoDialog
        if result.success:
            InfoDialog(
                title="✅ تم الاستيراد بنجاح!",
                message=f"تم استيراد البيانات إلى قاعدة البيانات بنجاح!\n\n"
                        f"📊 تم استيراد: {result.imported} سجل\n"
                        f"⏭️ تم التخطي: {result.skipped} سجل\n"
                        f"⚠️ تحذيرات: {result.warnings}\n\n"
                        f"سيتم عرض التقرير المفصل الآن.",
                parent=self
            ).exec_()
        else:
            InfoDialog(
                title="⚠️ اكتمل الاستيراد مع ملاحظات",
                message=f"تم استيراد البيانات مع بعض الملاحظات.\n\n"
                        f"✅ تم استيراد: {result.imported} سجل\n"
                        f"❌ فشل: {result.failed} سجل\n\n"
                        f"سيتم عرض التقرير المفصل الآن.",
                parent=self
            ).exec_()

        # Refresh dashboard and pages to reflect new data
        self._refresh_all_pages()

        # Show detailed commit report dialog (UC-003 S17 + Post-conditions)
        report_dialog = CommitReportDialog(
            commit_result=commit_result,
            import_metadata=import_metadata,
            parent=self
        )
        report_dialog.exec_()

        # Update UI with summary (on the page)
        if result.success:
            self.result_icon.setText("✅")
            self.result_message.setText(
                f"تم الاستيراد بنجاح - {result.imported} سجل"
            )
            self.result_message.setStyleSheet(f"font-size: 12pt; color: {Config.SUCCESS_COLOR};")
        else:
            self.result_icon.setText("⚠️")
            self.result_message.setText(
                f"اكتمل مع ملاحظات - {result.imported} سجل"
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
        self.next_btn.setText(f"{self.i18n.t('next')} ←")  # RTL-aware arrow

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

    def _refresh_all_pages(self):
        """Refresh dashboard and all data pages after import."""
        try:
            # Get parent window (MainWindow)
            parent_window = self.parent()
            if not parent_window:
                return

            # Refresh dashboard
            from app.pages_enum import Pages
            if hasattr(parent_window, 'pages'):
                if Pages.DASHBOARD in parent_window.pages:
                    parent_window.pages[Pages.DASHBOARD].refresh()

                # Refresh buildings page
                if Pages.BUILDINGS in parent_window.pages:
                    parent_window.pages[Pages.BUILDINGS].refresh()

                # Refresh units page
                if Pages.UNITS in parent_window.pages:
                    parent_window.pages[Pages.UNITS].refresh()

                # Refresh persons page
                if Pages.PERSONS in parent_window.pages:
                    parent_window.pages[Pages.PERSONS].refresh()

                logger.info("Refreshed all pages after import")
        except Exception as e:
            logger.warning(f"Failed to refresh pages after import: {e}")

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        pass  # Would update all labels
