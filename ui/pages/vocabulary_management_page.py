# -*- coding: utf-8 -*-
"""
Vocabulary Management Page
===========================
Implements UC-010 Vocabulary Management requirements.

Features:
- View and edit controlled vocabularies via API
- Add/remove/deprecate vocabulary terms
- Import vocabulary updates from file (S04/S04a)
- Export vocabularies for mobile devices (S09)
- Audit logging of all actions (S10)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit,
    QGroupBox, QFormLayout, QHeaderView, QDialog, QFileDialog,
    QDialogButtonBox, QCheckBox, QSpinBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from utils.i18n import I18n
from repositories.database import Database
from services.api_client import get_api_client
from services.vocab_service import get_all_vocabularies, refresh_vocabularies
from services.security_service import SecurityService
from ui.components.dialogs.base_dialog import BaseDialog
from ui.error_handler import ErrorHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class VocabularyEditDialog(BaseDialog):
    """Dialog for adding/editing vocabulary terms."""

    def __init__(self, parent=None, term_data: dict = None, i18n: I18n = None, db=None):
        self.term_data = term_data or {}
        i18n = i18n or I18n()

        title_key = "edit_term" if term_data else "add_term"

        super().__init__(
            db=db,
            i18n=i18n,
            title_key=title_key,
            parent=parent,
            size=(400, 300)
        )
        self._setup_ui()

    def _setup_ui(self):
        layout = self.main_layout

        form = QFormLayout()

        # Code
        self.code_input = QLineEdit()
        self.code_input.setText(str(self.term_data.get("code", "")))
        if self.term_data:
            self.code_input.setEnabled(False)
        form.addRow(self.i18n.t("code") + ":", self.code_input)

        # Arabic label
        self.label_ar_input = QLineEdit()
        self.label_ar_input.setText(self.term_data.get("labelArabic", ""))
        self.label_ar_input.setLayoutDirection(Qt.RightToLeft)
        form.addRow(self.i18n.t("label_ar") + ":", self.label_ar_input)

        # English label
        self.label_en_input = QLineEdit()
        self.label_en_input.setText(self.term_data.get("labelEnglish", ""))
        form.addRow(self.i18n.t("label_en") + ":", self.label_en_input)

        # Display order
        self.order_input = QSpinBox()
        self.order_input.setRange(0, 9999)
        self.order_input.setValue(self.term_data.get("displayOrder", 0))
        form.addRow(self.i18n.t("display_order") + ":", self.order_input)

        # Active status
        self.active_check = QCheckBox(self.i18n.t("active"))
        is_active = self.term_data.get("isActive", True)
        self.active_check.setChecked(bool(is_active))
        form.addRow("", self.active_check)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        """Get entered data in API-compatible format."""
        return {
            "code": self.code_input.text().strip(),
            "labelArabic": self.label_ar_input.text().strip(),
            "labelEnglish": self.label_en_input.text().strip(),
            "displayOrder": self.order_input.value(),
            "isActive": self.active_check.isChecked()
        }


class VocabularyManagementPage(QWidget):
    """
    Vocabulary Management Page.

    Implements UC-010:
    - S02: View vocabularies list
    - S03: Select vocabulary to edit (with status display)
    - S04: Import vocabulary update from file
    - S04a: Invalid file handling
    - S05: Add/Edit/Deprecate terms via API
    - S09: Export for mobile
    - S10: Audit logging
    """

    vocabulary_updated = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n or I18n()
        self.current_vocabulary = None
        self.security_service = SecurityService(db)
        self._user_role = None
        self._setup_ui()
        self._load_vocabularies()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()

        title = QLabel(self.i18n.t("vocabulary_management"))
        title.setProperty("class", "page-title")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        # Refresh from API button
        self.refresh_btn = QPushButton("تحديث من API")
        self.refresh_btn.clicked.connect(self._refresh_from_api)
        header.addWidget(self.refresh_btn)

        # Import button (UC-010 S04)
        self.import_btn = QPushButton("استيراد من ملف")
        self.import_btn.clicked.connect(self._import_vocabularies)
        header.addWidget(self.import_btn)

        # Export button (UC-010 S09)
        self.export_btn = QPushButton(self.i18n.t("export_for_mobile"))
        self.export_btn.clicked.connect(self._export_vocabularies)
        header.addWidget(self.export_btn)

        layout.addLayout(header)

        # Main content
        content = QHBoxLayout()

        # Left panel - Vocabulary list
        left_panel = QGroupBox(self.i18n.t("vocabularies"))
        left_layout = QVBoxLayout(left_panel)

        self.vocab_list = QComboBox()
        self.vocab_list.currentTextChanged.connect(self._on_vocabulary_selected)
        left_layout.addWidget(self.vocab_list)

        # Add new vocabulary
        add_vocab_layout = QHBoxLayout()
        self.new_vocab_input = QLineEdit()
        self.new_vocab_input.setPlaceholderText(self.i18n.t("new_vocabulary_name"))
        add_vocab_layout.addWidget(self.new_vocab_input)

        add_vocab_btn = QPushButton(self.i18n.t("add"))
        add_vocab_btn.clicked.connect(self._add_vocabulary)
        add_vocab_layout.addWidget(add_vocab_btn)

        left_layout.addLayout(add_vocab_layout)

        # Vocabulary info
        info_group = QGroupBox(self.i18n.t("vocabulary_info"))
        info_layout = QFormLayout(info_group)

        self.term_count_label = QLabel("0")
        info_layout.addRow(self.i18n.t("term_count") + ":", self.term_count_label)

        left_layout.addWidget(info_group)

        # Show deprecated checkbox (UC-010 S03)
        self.show_deprecated_check = QCheckBox("إظهار المصطلحات المتقادمة")
        self.show_deprecated_check.stateChanged.connect(
            lambda: self._load_terms(self.current_vocabulary)
        )
        left_layout.addWidget(self.show_deprecated_check)

        left_layout.addStretch()

        content.addWidget(left_panel, 1)

        # Right panel - Terms table
        right_panel = QGroupBox(self.i18n.t("terms"))
        right_layout = QVBoxLayout(right_panel)

        # Toolbar
        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.i18n.t("search_terms"))
        self.search_input.textChanged.connect(self._filter_terms)
        toolbar.addWidget(self.search_input, 1)

        self.add_term_btn = QPushButton(self.i18n.t("add_term"))
        self.add_term_btn.clicked.connect(self._add_term)
        toolbar.addWidget(self.add_term_btn)

        self.edit_term_btn = QPushButton(self.i18n.t("edit"))
        self.edit_term_btn.clicked.connect(self._edit_term)
        self.edit_term_btn.setEnabled(False)
        toolbar.addWidget(self.edit_term_btn)

        self.delete_term_btn = QPushButton(self.i18n.t("delete"))
        self.delete_term_btn.clicked.connect(self._delete_term)
        self.delete_term_btn.setEnabled(False)
        toolbar.addWidget(self.delete_term_btn)

        right_layout.addLayout(toolbar)

        # Terms table
        self.terms_table = QTableWidget()
        self.terms_table.setColumnCount(5)
        self.terms_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.terms_table.setHorizontalHeaderLabels([
            self.i18n.t("code"),
            self.i18n.t("label_ar"),
            self.i18n.t("label_en"),
            self.i18n.t("order"),
            self.i18n.t("active")
        ])
        self.terms_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.terms_table.setSelectionMode(QTableWidget.SingleSelection)
        self.terms_table.setAlternatingRowColors(True)
        self.terms_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.terms_table.itemSelectionChanged.connect(self._on_term_selected)
        self.terms_table.cellDoubleClicked.connect(self._edit_term)

        right_layout.addWidget(self.terms_table)

        content.addWidget(right_panel, 3)

        layout.addLayout(content)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _load_vocabularies(self):
        """Load vocabulary list from backend API."""
        self.vocab_list.clear()
        try:
            for v in get_all_vocabularies():
                name = v.get("vocabularyName", "")
                if name:
                    self.vocab_list.addItem(name)
        except Exception as e:
            logger.error(f"Failed to load vocabularies: {e}")

    def _refresh_from_api(self):
        """Re-fetch vocabularies from backend API and reload the UI."""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("جارٍ التحديث...")
        try:
            refresh_vocabularies()
            self._load_vocabularies()
            logger.info("Vocabularies refreshed from API successfully")
        except Exception as e:
            logger.error(f"Failed to refresh vocabularies: {e}")
        finally:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("تحديث من API")

    def _on_vocabulary_selected(self, vocabulary_name: str):
        """Handle vocabulary selection."""
        self.current_vocabulary = vocabulary_name
        self._load_terms(vocabulary_name)

    def _load_terms(self, vocabulary_name: str):
        """Load terms for selected vocabulary from API."""
        self.terms_table.setRowCount(0)
        if not vocabulary_name:
            return

        self._spinner.show_loading("جاري تحميل المصطلحات...")
        try:
            show_deprecated = self.show_deprecated_check.isChecked()

            try:
                api = get_api_client()
                result = api.get_vocabulary_terms(vocabulary_name)
                terms = result.get("values", []) if isinstance(result, dict) else []
            except Exception as e:
                logger.error(f"Failed to load terms from API: {e}")
                return

            if not show_deprecated:
                terms = [t for t in terms if t.get("isActive", True)]

            self.terms_table.setRowCount(len(terms))
            for i, t in enumerate(terms):
                code = str(t.get("code", ""))
                label_ar = t.get("labelArabic", "") or ""
                label_en = t.get("labelEnglish", "") or ""
                order = str(t.get("displayOrder", 0))
                is_active = t.get("isActive", True)

                self.terms_table.setItem(i, 0, QTableWidgetItem(code))
                self.terms_table.setItem(i, 1, QTableWidgetItem(label_ar))
                self.terms_table.setItem(i, 2, QTableWidgetItem(label_en))
                self.terms_table.setItem(i, 3, QTableWidgetItem(order))

                status_text = "نشط" if is_active else "متقادم"
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                if not is_active:
                    status_item.setBackground(QColor("#FEE2E2"))
                self.terms_table.setItem(i, 4, status_item)

            self.term_count_label.setText(str(len(terms)))
        finally:
            self._spinner.hide_loading()

    def _filter_terms(self, search_text: str):
        """Filter terms table by search text."""
        for row in range(self.terms_table.rowCount()):
            match = False
            for col in range(self.terms_table.columnCount()):
                item = self.terms_table.item(row, col)
                if item and search_text.lower() in item.text().lower():
                    match = True
                    break
            self.terms_table.setRowHidden(row, not match)

    def _on_term_selected(self):
        """Handle term selection."""
        has_selection = len(self.terms_table.selectedItems()) > 0
        self.edit_term_btn.setEnabled(has_selection)
        self.delete_term_btn.setEnabled(has_selection)

    def _add_vocabulary(self):
        """Add a new vocabulary via API."""
        name = self.new_vocab_input.text().strip()
        if not name:
            return

        if self.vocab_list.findText(name) != -1:
            ErrorHandler.show_warning(
                self,
                self.i18n.t("vocabulary_exists"),
                self.i18n.t("error")
            )
            return

        try:
            get_api_client().create_vocabulary({"name": name, "displayName": name})
            refresh_vocabularies()
            self._load_vocabularies()
            self.vocab_list.setCurrentText(name)
            self.new_vocab_input.clear()
            self.security_service.log_action(
                action="vocabulary_created",
                entity_type="vocabulary",
                entity_id=name,
                details=f"تم إنشاء تصنيف جديد: {name}"
            )
        except Exception as e:
            logger.error(f"Failed to create vocabulary: {e}")
            ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _add_term(self):
        """Add a new term to current vocabulary via API (UC-010 S05)."""
        if not self.current_vocabulary:
            return

        dialog = VocabularyEditDialog(self, i18n=self.i18n)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            if not data["code"]:
                ErrorHandler.show_warning(self, self.i18n.t("code_required"), self.i18n.t("error"))
                return

            try:
                get_api_client().create_vocabulary_term(self.current_vocabulary, data)
                refresh_vocabularies()
                self._load_terms(self.current_vocabulary)
                self.vocabulary_updated.emit(self.current_vocabulary)
                self.security_service.log_action(
                    action="vocabulary_term_created",
                    entity_type="vocabulary",
                    entity_id=f"{self.current_vocabulary}/{data['code']}",
                    details=f"تم إضافة تصنيف: {data['labelArabic']}"
                )
            except Exception as e:
                logger.error(f"Failed to add term: {e}")
                ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _edit_term(self):
        """Edit selected term via API (UC-010 S05)."""
        selected = self.terms_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        is_active_text = self.terms_table.item(row, 4).text()
        term_data = {
            "code": self.terms_table.item(row, 0).text(),
            "labelArabic": self.terms_table.item(row, 1).text(),
            "labelEnglish": self.terms_table.item(row, 2).text(),
            "displayOrder": int(self.terms_table.item(row, 3).text() or 0),
            "isActive": is_active_text == "نشط"
        }
        original_code = term_data["code"]

        dialog = VocabularyEditDialog(self, term_data, self.i18n)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                get_api_client().update_vocabulary_term(
                    self.current_vocabulary, original_code, data
                )
                refresh_vocabularies()
                self._load_terms(self.current_vocabulary)
                self.vocabulary_updated.emit(self.current_vocabulary)
                self.security_service.log_action(
                    action="vocabulary_term_updated",
                    entity_type="vocabulary",
                    entity_id=f"{self.current_vocabulary}/{original_code}",
                    details=f"تم تحديث تصنيف: {data['labelArabic']}"
                )
            except Exception as e:
                logger.error(f"Failed to update term: {e}")
                ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def configure_for_role(self, role: str):
        self._user_role = role

    def _delete_term(self):
        """Deactivate selected term via API (UC-010 S05)."""
        if self._user_role and self._user_role not in ("admin", "data_manager"):
            return
        selected = self.terms_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        code = self.terms_table.item(row, 0).text()
        label = self.terms_table.item(row, 1).text()

        if ErrorHandler.confirm(
            self,
            self.i18n.t("confirm_delete_term").format(code=code),
            self.i18n.t("confirm_delete")
        ):
            try:
                get_api_client().deactivate_vocabulary_term(self.current_vocabulary, code)
                refresh_vocabularies()
                self._load_terms(self.current_vocabulary)
                self.vocabulary_updated.emit(self.current_vocabulary)
                self.security_service.log_action(
                    action="vocabulary_term_deprecated",
                    entity_type="vocabulary",
                    entity_id=f"{self.current_vocabulary}/{code}",
                    details=f"تم إيقاف تصنيف: {label}"
                )
            except Exception as e:
                logger.error(f"Failed to deactivate term: {e}")
                ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _import_vocabularies(self):
        """Import vocabulary update from file (UC-010 S04/S04a)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "استيراد التصنيف",
            "",
            "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            import json
            import csv

            data = None
            if file_path.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif file_path.endswith(".csv"):
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            else:
                ErrorHandler.show_warning(
                    self,
                    "نوع الملف غير مدعوم. استخدم JSON أو CSV",
                    self.i18n.t("error")
                )
                return

            if not data:
                ErrorHandler.show_warning(
                    self,
                    "الملف فارغ أو غير صالح",
                    self.i18n.t("error")
                )
                return

            # Validate file structure (S04a)
            if isinstance(data, list) and len(data) > 0:
                sample = data[0]
                if "code" not in sample:
                    ErrorHandler.show_warning(
                        self,
                        "الملف لا يحتوي على الأعمدة المطلوبة (code). تحقق من بنية الملف.",
                        self.i18n.t("error")
                    )
                    return

            api = get_api_client()
            api.import_vocabularies(data)
            refresh_vocabularies()
            self._load_vocabularies()
            self._load_terms(self.current_vocabulary)

            self.security_service.log_action(
                action="vocabulary_imported",
                entity_type="vocabulary",
                entity_id=self.current_vocabulary or "all",
                details=f"تم استيراد من ملف: {file_path}"
            )

            ErrorHandler.show_success(
                self,
                "تم الاستيراد بنجاح",
                self.i18n.t("success")
            )

        except Exception as e:
            logger.error(f"Failed to import vocabularies: {e}")
            ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _export_vocabularies(self):
        """Export vocabularies for mobile devices (UC-010 S09) via API."""
        try:
            import json
            from datetime import datetime

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.i18n.t("export_vocabularies"),
                f"vocabularies_{datetime.now().strftime('%Y%m%d')}.json",
                "JSON Files (*.json)"
            )

            if not file_path:
                return

            export_data = get_api_client().export_vocabularies()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            self.security_service.log_action(
                action="vocabulary_exported",
                entity_type="vocabulary",
                entity_id="all",
                details=f"تم التصدير إلى: {file_path}"
            )

            ErrorHandler.show_success(
                self,
                self.i18n.t("vocabularies_exported"),
                self.i18n.t("success")
            )

        except Exception as e:
            logger.error(f"Failed to export vocabularies: {e}")
            ErrorHandler.show_error(self, str(e), self.i18n.t("error"))
