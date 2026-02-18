# -*- coding: utf-8 -*-
"""
Vocabulary Management Page
===========================
Implements UC-010 Vocabulary Management requirements.

Features:
- View and edit controlled vocabularies
- Add/remove vocabulary terms
- Export vocabularies for mobile devices
- Version management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit,
    QGroupBox, QFormLayout, QHeaderView,
    QDialogButtonBox, QCheckBox, QSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from utils.i18n import I18n
from repositories.database import Database
from ui.components.dialogs.base_dialog import BaseDialog
from ui.error_handler import ErrorHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class VocabularyEditDialog(BaseDialog):
    """Dialog for adding/editing vocabulary terms."""

    def __init__(self, parent=None, term_data: dict = None, i18n: I18n = None, db=None):
        self.term_data = term_data or {}
        i18n = i18n or I18n()

        # Determine title key based on edit/add mode
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
        self.code_input.setText(self.term_data.get("code", ""))
        form.addRow(self.i18n.t("code") + ":", self.code_input)

        # Arabic label
        self.label_ar_input = QLineEdit()
        self.label_ar_input.setText(self.term_data.get("label_ar", ""))
        self.label_ar_input.setLayoutDirection(Qt.RightToLeft)
        form.addRow(self.i18n.t("label_ar") + ":", self.label_ar_input)

        # English label
        self.label_en_input = QLineEdit()
        self.label_en_input.setText(self.term_data.get("label_en", ""))
        form.addRow(self.i18n.t("label_en") + ":", self.label_en_input)

        # Display order
        self.order_input = QSpinBox()
        self.order_input.setRange(0, 9999)
        self.order_input.setValue(self.term_data.get("display_order", 0))
        form.addRow(self.i18n.t("display_order") + ":", self.order_input)

        # Active status
        self.active_check = QCheckBox(self.i18n.t("active"))
        self.active_check.setChecked(self.term_data.get("is_active", True))
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
        """Get entered data."""
        return {
            "code": self.code_input.text().strip(),
            "label_ar": self.label_ar_input.text().strip(),
            "label_en": self.label_en_input.text().strip(),
            "display_order": self.order_input.value(),
            "is_active": self.active_check.isChecked()
        }


class VocabularyManagementPage(QWidget):
    """
    Vocabulary Management Page.

    Implements UC-010:
    - S02: View vocabularies list
    - S03: Select vocabulary to edit
    - S04-S06: Add/Edit/Delete terms
    - S07: Save changes
    - S08: Manage versions
    - S09: Export for mobile
    """

    vocabulary_updated = pyqtSignal(str)  # vocabulary_name

    def __init__(self, db: Database, i18n: I18n = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n or I18n()
        self.current_vocabulary = None
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

        # Export button
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

        self.version_label = QLabel("1.0")
        info_layout.addRow(self.i18n.t("version") + ":", self.version_label)

        left_layout.addWidget(info_group)
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

    def _load_vocabularies(self):
        """Load vocabulary list from database."""
        self.vocab_list.clear()

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT DISTINCT vocabulary_name FROM vocabularies
                ORDER BY vocabulary_name
            """)

            for row in cursor.fetchall():
                self.vocab_list.addItem(row[0])

            # Add predefined vocabularies if not exist
            predefined = [
                "building_type", "building_status", "unit_type",
                "claim_type", "claim_status", "document_type",
                "relation_type", "gender", "nationality"
            ]

            for vocab in predefined:
                if self.vocab_list.findText(vocab) == -1:
                    self.vocab_list.addItem(vocab)

        except Exception as e:
            logger.error(f"Failed to load vocabularies: {e}")

    def _on_vocabulary_selected(self, vocabulary_name: str):
        """Handle vocabulary selection."""
        self.current_vocabulary = vocabulary_name
        self._load_terms(vocabulary_name)

    def _load_terms(self, vocabulary_name: str):
        """Load terms for selected vocabulary."""
        self.terms_table.setRowCount(0)

        if not vocabulary_name:
            return

        try:
            cursor = self.db.cursor()
            cursor.execute("""
                SELECT code, label_ar, label_en, display_order, is_active
                FROM vocabularies
                WHERE vocabulary_name = ?
                ORDER BY display_order, code
            """, (vocabulary_name,))

            rows = cursor.fetchall()

            self.terms_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                self.terms_table.setItem(i, 0, QTableWidgetItem(row[0] or ""))
                self.terms_table.setItem(i, 1, QTableWidgetItem(row[1] or ""))
                self.terms_table.setItem(i, 2, QTableWidgetItem(row[2] or ""))
                self.terms_table.setItem(i, 3, QTableWidgetItem(str(row[3] or 0)))

                active_item = QTableWidgetItem("✓" if row[4] else "✗")
                active_item.setTextAlignment(Qt.AlignCenter)
                self.terms_table.setItem(i, 4, active_item)

            self.term_count_label.setText(str(len(rows)))

        except Exception as e:
            logger.error(f"Failed to load terms: {e}")

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
        """Add a new vocabulary."""
        name = self.new_vocab_input.text().strip()
        if not name:
            return

        # Check if already exists
        if self.vocab_list.findText(name) != -1:
            ErrorHandler.show_warning(
                self,
                self.i18n.t("vocabulary_exists"),
                self.i18n.t("error")
            )
            return

        self.vocab_list.addItem(name)
        self.vocab_list.setCurrentText(name)
        self.new_vocab_input.clear()

    def _add_term(self):
        """Add a new term to current vocabulary."""
        if not self.current_vocabulary:
            return

        dialog = VocabularyEditDialog(self, i18n=self.i18n)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            if not data["code"]:
                ErrorHandler.show_warning(self, self.i18n.t("code_required"), self.i18n.t("error"))
                return

            try:
                cursor = self.db.cursor()

                # Check for duplicate code
                cursor.execute("""
                    SELECT COUNT(*) FROM vocabularies
                    WHERE vocabulary_name = ? AND code = ?
                """, (self.current_vocabulary, data["code"]))

                if cursor.fetchone()[0] > 0:
                    ErrorHandler.show_warning(
                        self,
                        self.i18n.t("code_exists"),
                        self.i18n.t("error")
                    )
                    return

                cursor.execute("""
                    INSERT INTO vocabularies (vocabulary_name, code, label_ar, label_en, display_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.current_vocabulary,
                    data["code"],
                    data["label_ar"],
                    data["label_en"],
                    data["display_order"],
                    1 if data["is_active"] else 0
                ))

                self.db.connection.commit()
                self._load_terms(self.current_vocabulary)
                self.vocabulary_updated.emit(self.current_vocabulary)

            except Exception as e:
                logger.error(f"Failed to add term: {e}")
                ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _edit_term(self):
        """Edit selected term."""
        selected = self.terms_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        term_data = {
            "code": self.terms_table.item(row, 0).text(),
            "label_ar": self.terms_table.item(row, 1).text(),
            "label_en": self.terms_table.item(row, 2).text(),
            "display_order": int(self.terms_table.item(row, 3).text() or 0),
            "is_active": self.terms_table.item(row, 4).text() == "✓"
        }
        original_code = term_data["code"]

        dialog = VocabularyEditDialog(self, term_data, self.i18n)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                cursor = self.db.cursor()
                cursor.execute("""
                    UPDATE vocabularies
                    SET code = ?, label_ar = ?, label_en = ?, display_order = ?, is_active = ?
                    WHERE vocabulary_name = ? AND code = ?
                """, (
                    data["code"],
                    data["label_ar"],
                    data["label_en"],
                    data["display_order"],
                    1 if data["is_active"] else 0,
                    self.current_vocabulary,
                    original_code
                ))

                self.db.connection.commit()
                self._load_terms(self.current_vocabulary)
                self.vocabulary_updated.emit(self.current_vocabulary)

            except Exception as e:
                logger.error(f"Failed to update term: {e}")
                ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _delete_term(self):
        """Delete selected term."""
        selected = self.terms_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        code = self.terms_table.item(row, 0).text()

        if ErrorHandler.confirm(
            self,
            self.i18n.t("confirm_delete_term").format(code=code),
            self.i18n.t("confirm_delete")
        ):
            try:
                cursor = self.db.cursor()
                cursor.execute("""
                    DELETE FROM vocabularies
                    WHERE vocabulary_name = ? AND code = ?
                """, (self.current_vocabulary, code))

                self.db.connection.commit()
                self._load_terms(self.current_vocabulary)
                self.vocabulary_updated.emit(self.current_vocabulary)

            except Exception as e:
                logger.error(f"Failed to delete term: {e}")
                ErrorHandler.show_error(self, str(e), self.i18n.t("error"))

    def _export_vocabularies(self):
        """Export vocabularies for mobile devices (UC-010 S09)."""
        try:
            from PyQt5.QtWidgets import QFileDialog
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

            cursor = self.db.cursor()
            cursor.execute("""
                SELECT vocabulary_name, code, label_ar, label_en, display_order, is_active
                FROM vocabularies
                WHERE is_active = 1
                ORDER BY vocabulary_name, display_order, code
            """)

            vocabularies = {}
            for row in cursor.fetchall():
                vocab_name = row[0]
                if vocab_name not in vocabularies:
                    vocabularies[vocab_name] = []

                vocabularies[vocab_name].append({
                    "code": row[1],
                    "label_ar": row[2],
                    "label_en": row[3],
                    "display_order": row[4]
                })

            export_data = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "vocabularies": vocabularies
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            ErrorHandler.show_success(
                self,
                self.i18n.t("vocabularies_exported"),
                self.i18n.t("success")
            )

        except Exception as e:
            logger.error(f"Failed to export vocabularies: {e}")
            ErrorHandler.show_error(self, str(e), self.i18n.t("error"))
