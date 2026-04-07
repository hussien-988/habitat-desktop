# -*- coding: utf-8 -*-
"""
Person-Unit Relations management page with search, CRUD, and validation.
Implements Person-Unit relationship management with Evidence support.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QTextEdit,
    QAbstractItemView, QGraphicsDropShadowEffect,
    QDateEdit, QGroupBox, QFileDialog, QSplitter, QListWidget,
    QListWidgetItem, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QDate
from PyQt5.QtGui import QColor, QIcon

from app.config import Config
from services.vocab_service import get_options as vocab_get_options
from repositories.database import Database
from repositories.relation_repository import RelationRepository
from repositories.person_repository import PersonRepository
from repositories.unit_repository import UnitRepository
from repositories.evidence_repository import EvidenceRepository
from models.relation import PersonUnitRelation
from models.evidence import Evidence
from ui.components.toast import Toast
from ui.components.base_table_model import BaseTableModel
from ui.error_handler import ErrorHandler
from utils.i18n import I18n
from utils.logger import get_logger
from services.translation_manager import tr, get_layout_direction
from ui.design_system import ScreenScale

logger = get_logger(__name__)


class RelationsTableModel(BaseTableModel):
    """Table model for person-unit relations."""

    def __init__(self, is_arabic: bool = True):
        columns = [
            ('person', "Person", tr("table.relations.person")),
            ('unit', "Unit", tr("table.relations.unit")),
            ('relation_type', "Relation Type", tr("table.relations.relation_type")),
            ('share', "Share %", tr("table.relations.share")),
            ('status', "Status", tr("table.relations.status")),
            ('start_date', "Start Date", tr("table.relations.start_date")),
            ('notes', "Notes", tr("table.relations.notes")),
        ]
        super().__init__(items=[], columns=columns)
        self._is_arabic = is_arabic
        self._persons_cache = {}
        self._units_cache = {}

    def set_cache(self, persons_cache: dict, units_cache: dict):
        """Set the cache for persons and units lookups."""
        self._persons_cache = persons_cache
        self._units_cache = units_cache

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        """Override to add BackgroundRole support for verification status."""
        if role == Qt.BackgroundRole:
            if not index.isValid() or index.row() >= len(self._items):
                return None
            relation = self._items[index.row()]
            if relation.verification_status == "verified":
                return QColor("#ECFDF5")  # Light green
            elif relation.verification_status == "rejected":
                return QColor("#FEF2F2")  # Light red
        return super().data(index, role)

    def get_item_value(self, item, field_name: str):
        """Extract field value from relation object."""
        if field_name == 'person':
            person = self._persons_cache.get(item.person_id)
            if person:
                return person.full_name_ar if self._is_arabic else person.full_name
            return item.person_id[:8] + "..."
        elif field_name == 'unit':
            unit = self._units_cache.get(item.unit_id)
            if unit:
                return unit.unit_id
            return item.unit_id[:15] + "..."
        elif field_name == 'relation_type':
            return item.relation_type_display_ar if self._is_arabic else item.relation_type_display
        elif field_name == 'share':
            return f"{item.ownership_percentage:.1f}%" if item.ownership_share > 0 else "-"
        elif field_name == 'status':
            statuses_ar = {"pending": tr("page.relations.status_pending"), "verified": tr("page.relations.status_verified"), "rejected": tr("page.relations.status_rejected")}
            return statuses_ar.get(item.verification_status, item.verification_status) if self._is_arabic else item.verification_status_display
        elif field_name == 'start_date':
            return item.relation_start_date.strftime("%Y-%m-%d") if item.relation_start_date else "-"
        elif field_name == 'notes':
            notes = item.relation_notes or ""
            return notes[:30] + "..." if len(notes) > 30 else notes if notes else "-"
        return "-"

    def set_relations(self, relations: list):
        self.set_items(relations)

    def get_relation(self, row: int):
        return self.get_item(row)


class EvidenceTableModel(BaseTableModel):
    """Table model for evidence list."""

    def __init__(self, is_arabic: bool = True):
        columns = [
            ('type', "Type", tr("table.evidence.type")),
            ('reference', "Reference #", tr("table.evidence.reference")),
            ('date', "Date", tr("table.evidence.date")),
            ('status', "Status", tr("table.evidence.status")),
            ('description', "Description", tr("table.evidence.description")),
        ]
        super().__init__(items=[], columns=columns)
        self._is_arabic = is_arabic

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        """Override to add BackgroundRole support for verification status."""
        if role == Qt.BackgroundRole:
            if not index.isValid() or index.row() >= len(self._items):
                return None
            evidence = self._items[index.row()]
            if evidence.verification_status == "verified":
                return QColor("#ECFDF5")
            elif evidence.verification_status == "rejected":
                return QColor("#FEF2F2")
        return super().data(index, role)

    def get_item_value(self, item, field_name: str):
        """Extract field value from evidence object."""
        if field_name == 'type':
            return item.evidence_type_display_ar if self._is_arabic else item.evidence_type_display
        elif field_name == 'reference':
            return item.reference_number or "-"
        elif field_name == 'date':
            return item.reference_date.strftime("%Y-%m-%d") if item.reference_date else "-"
        elif field_name == 'status':
            statuses_ar = {"pending": tr("page.relations.status_pending"), "verified": tr("page.relations.status_verified"), "rejected": tr("page.relations.status_rejected")}
            return statuses_ar.get(item.verification_status, item.verification_status) if self._is_arabic else item.verification_status_display
        elif field_name == 'description':
            desc = item.evidence_description or ""
            return desc[:40] + "..." if len(desc) > 40 else desc if desc else "-"
        return "-"

    def set_evidence(self, evidence_list: list):
        self.set_items(evidence_list)

    def get_evidence(self, row: int):
        return self.get_item(row)


class EvidenceDialog(QDialog):
    """Dialog for creating/editing evidence."""

    EVIDENCE_TYPES_KEYS = [
        ("document", "page.relations.evidence_type_document"),
        ("witness", "page.relations.evidence_type_witness"),
        ("community", "page.relations.evidence_type_community"),
        ("other", "page.relations.evidence_type_other"),
    ]

    VERIFICATION_STATUSES_KEYS = [
        ("pending", "page.relations.verification_pending"),
        ("verified", "page.relations.verification_verified"),
        ("rejected", "page.relations.verification_rejected"),
    ]

    def __init__(self, i18n: I18n, evidence: Evidence = None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.evidence = evidence
        self._is_edit_mode = evidence is not None
        self._selected_file_path = None

        self.setWindowTitle(i18n.t("edit_evidence") if evidence else i18n.t("add_evidence"))
        self.setMinimumWidth(ScreenScale.w(500))
        self.setMinimumHeight(ScreenScale.h(450))
        self._setup_ui()

        if evidence:
            self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Evidence Type
        type_group = QGroupBox(tr("page.relations.evidence_type_group"))
        type_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: {Config.FONT_SIZE}pt;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 0 8px;
            }}
        """)
        type_form = QFormLayout(type_group)
        type_form.setSpacing(10)

        self.type_combo = QComboBox()
        for code, key in self.EVIDENCE_TYPES_KEYS:
            self.type_combo.addItem(tr(key), code)
        type_form.addRow(tr("page.relations.type_required"), self.type_combo)

        layout.addWidget(type_group)

        # Reference Details
        ref_group = QGroupBox(tr("page.relations.reference_info_group"))
        ref_group.setStyleSheet(type_group.styleSheet())
        ref_form = QFormLayout(ref_group)
        ref_form.setSpacing(10)

        self.ref_number = QLineEdit()
        self.ref_number.setPlaceholderText(tr("page.relations.ref_number_placeholder"))
        ref_form.addRow(tr("page.relations.ref_number_label"), self.ref_number)

        self.ref_date = QDateEdit()
        self.ref_date.setCalendarPopup(True)
        self.ref_date.setDisplayFormat("yyyy-MM-dd")
        self.ref_date.setSpecialValueText(tr("page.relations.not_specified"))
        self.ref_date.setDate(QDate.currentDate())
        ref_form.addRow(tr("page.relations.ref_date_label"), self.ref_date)

        layout.addWidget(ref_group)

        # Description
        desc_group = QGroupBox(tr("page.relations.description_group"))
        desc_group.setStyleSheet(type_group.styleSheet())
        desc_layout = QVBoxLayout(desc_group)

        self.description = QTextEdit()
        self.description.setMaximumHeight(ScreenScale.h(80))
        self.description.setPlaceholderText(tr("page.relations.evidence_description_placeholder"))
        desc_layout.addWidget(self.description)

        layout.addWidget(desc_group)

        # Verification Status
        status_group = QGroupBox(tr("page.relations.verification_status_group"))
        status_group.setStyleSheet(type_group.styleSheet())
        status_form = QFormLayout(status_group)
        status_form.setSpacing(10)

        self.status_combo = QComboBox()
        for code, key in self.VERIFICATION_STATUSES_KEYS:
            self.status_combo.addItem(tr(key), code)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        status_form.addRow(tr("page.relations.status_label"), self.status_combo)

        self.verification_notes = QTextEdit()
        self.verification_notes.setMaximumHeight(ScreenScale.h(60))
        self.verification_notes.setPlaceholderText(tr("page.relations.verification_notes_placeholder"))
        status_form.addRow(tr("page.relations.notes_label"), self.verification_notes)

        layout.addWidget(status_group)

        # File Attachment (placeholder - in real app would link to Document)
        file_group = QGroupBox(tr("page.relations.attachment_group"))
        file_group.setStyleSheet(type_group.styleSheet())
        file_layout = QHBoxLayout(file_group)

        self.file_label = QLabel(tr("page.relations.no_attachment"))
        self.file_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        file_layout.addWidget(self.file_label)

        file_layout.addStretch()

        self.select_file_btn = QPushButton(tr("page.relations.select_file"))
        self.select_file_btn.clicked.connect(self._select_file)
        file_layout.addWidget(self.select_file_btn)

        self.clear_file_btn = QPushButton(tr("page.relations.clear"))
        self.clear_file_btn.clicked.connect(self._clear_file)
        self.clear_file_btn.setEnabled(False)
        file_layout.addWidget(self.clear_file_btn)

        layout.addWidget(file_group)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"""
            color: {Config.ERROR_COLOR};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 6px;
            padding: 8px;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_status_changed(self):
        """Enable notes field when status is not pending."""
        status = self.status_combo.currentData()
        self.verification_notes.setEnabled(status != "pending")

    def _select_file(self):
        """Select a file attachment."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("page.relations.select_file"),
            "",
            "All Files (*);;Images (*.png *.jpg *.jpeg);;Documents (*.pdf *.doc *.docx)"
        )
        if file_path:
            self._selected_file_path = file_path
            # Show just the filename
            import os
            self.file_label.setText(os.path.basename(file_path))
            self.file_label.setStyleSheet(f"color: {Config.TEXT_COLOR};")
            self.clear_file_btn.setEnabled(True)

    def _clear_file(self):
        """Clear file attachment."""
        self._selected_file_path = None
        self.file_label.setText(tr("page.relations.no_attachment"))
        self.file_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        self.clear_file_btn.setEnabled(False)

    def _populate_data(self):
        """Populate form with existing evidence data."""
        if not self.evidence:
            return

        # Type
        idx = self.type_combo.findData(self.evidence.evidence_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        # Reference number
        if self.evidence.reference_number:
            self.ref_number.setText(self.evidence.reference_number)

        # Reference date
        if self.evidence.reference_date:
            self.ref_date.setDate(QDate(
                self.evidence.reference_date.year,
                self.evidence.reference_date.month,
                self.evidence.reference_date.day
            ))

        # Description
        if self.evidence.evidence_description:
            self.description.setPlainText(self.evidence.evidence_description)

        # Status
        idx = self.status_combo.findData(self.evidence.verification_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        # Verification notes
        if self.evidence.verification_notes:
            self.verification_notes.setPlainText(self.evidence.verification_notes)

        # Document ID (show if attached)
        if self.evidence.document_id:
            self.file_label.setText(f"{tr('page.relations.attached')}: {self.evidence.document_id[:12]}...")
            self.file_label.setStyleSheet(f"color: {Config.TEXT_COLOR};")

    def _on_save(self):
        """Validate and save."""
        self.error_label.setVisible(False)
        self.accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        ref_date = self.ref_date.date().toPyDate() if self.ref_date.date().isValid() else None

        return {
            "evidence_type": self.type_combo.currentData(),
            "reference_number": self.ref_number.text().strip() or None,
            "reference_date": ref_date,
            "evidence_description": self.description.toPlainText().strip() or "",
            "verification_status": self.status_combo.currentData(),
            "verification_notes": self.verification_notes.toPlainText().strip() or None,
            # document_id would be set after file upload in real implementation
        }

    def get_selected_file(self):
        """Get the selected file path."""
        return self._selected_file_path


class RelationDialog(QDialog):
    """Dialog for creating/editing a person-unit relation."""

    def __init__(self, db: Database, i18n: I18n, relation: PersonUnitRelation = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.relation = relation
        self.person_repo = PersonRepository(db)
        self.unit_repo = UnitRepository(db)
        self.relation_repo = RelationRepository(db)
        self._is_edit_mode = relation is not None

        self.setWindowTitle(i18n.t("edit_relation") if relation else i18n.t("add_relation"))
        self.setMinimumWidth(ScreenScale.w(550))
        self.setMinimumHeight(ScreenScale.h(500))
        self._setup_ui()

        if relation:
            self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        main_group = QGroupBox(tr("page.relations.basic_info_group"))
        main_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: {Config.FONT_SIZE}pt;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 0 8px;
            }}
        """)
        main_form = QFormLayout(main_group)
        main_form.setSpacing(10)

        # Person selection
        person_container = QWidget()
        person_layout = QVBoxLayout(person_container)
        person_layout.setContentsMargins(0, 0, 0, 0)
        person_layout.setSpacing(4)

        self.person_combo = QComboBox()
        self.person_combo.setMinimumWidth(ScreenScale.w(300))
        persons = self.person_repo.get_all(limit=500)
        self.person_combo.addItem(tr("page.relations.select_person"), "")
        for p in persons:
            display = f"{p.full_name_ar} ({p.national_id or tr('page.relations.no_national_id')})"
            self.person_combo.addItem(display, p.person_id)
        person_layout.addWidget(self.person_combo)

        self.person_error = QLabel("")
        self.person_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.person_error.setVisible(False)
        person_layout.addWidget(self.person_error)

        main_form.addRow(tr("page.relations.person_required"), person_container)

        # Unit selection
        unit_container = QWidget()
        unit_layout = QVBoxLayout(unit_container)
        unit_layout.setContentsMargins(0, 0, 0, 0)
        unit_layout.setSpacing(4)

        self.unit_combo = QComboBox()
        self.unit_combo.setMinimumWidth(ScreenScale.w(300))
        units = self.unit_repo.get_all(limit=500)
        self.unit_combo.addItem(tr("page.relations.select_unit"), "")
        for u in units:
            display = f"{u.unit_id} ({u.unit_type_display_ar})"
            self.unit_combo.addItem(display, u.unit_id)
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        unit_layout.addWidget(self.unit_combo)

        self.unit_error = QLabel("")
        self.unit_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.unit_error.setVisible(False)
        unit_layout.addWidget(self.unit_error)

        main_form.addRow(tr("page.relations.unit_required"), unit_container)

        # Relation type
        type_container = QWidget()
        type_layout = QVBoxLayout(type_container)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.setSpacing(4)

        self.type_combo = QComboBox()
        for code, label in vocab_get_options("RelationType"):
            self.type_combo.addItem(label, code)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)

        self.type_error = QLabel("")
        self.type_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.type_error.setVisible(False)
        type_layout.addWidget(self.type_error)

        main_form.addRow(tr("page.relations.relation_type_required"), type_container)

        # Other description (for "other" type)
        self.other_desc = QLineEdit()
        self.other_desc.setPlaceholderText(tr("page.relations.relation_description_placeholder"))
        self.other_desc.setEnabled(False)
        main_form.addRow(tr("page.relations.other_description"), self.other_desc)

        layout.addWidget(main_group)
        ownership_group = QGroupBox(tr("page.relations.ownership_details_group"))
        ownership_group.setStyleSheet(main_group.styleSheet())
        ownership_form = QFormLayout(ownership_group)
        ownership_form.setSpacing(10)

        # Ownership share (0-100%)
        share_container = QWidget()
        share_layout = QVBoxLayout(share_container)
        share_layout.setContentsMargins(0, 0, 0, 0)
        share_layout.setSpacing(4)

        self.share_spin = QSpinBox()
        self.share_spin.setRange(0, 2400)
        self.share_spin.setSuffix(f" {tr('unit.shares')}")
        self.share_spin.setValue(0)
        self.share_spin.valueChanged.connect(self._validate_share)
        share_layout.addWidget(self.share_spin)

        self.share_hint = QLabel(tr("page.relations.ownership_share_hint"))
        self.share_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 10px;")
        share_layout.addWidget(self.share_hint)

        self.share_error = QLabel("")
        self.share_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.share_error.setVisible(False)
        share_layout.addWidget(self.share_error)

        ownership_form.addRow(tr("page.relations.share_percentage"), share_container)

        layout.addWidget(ownership_group)
        dates_group = QGroupBox(tr("page.relations.dates_group"))
        dates_group.setStyleSheet(main_group.styleSheet())
        dates_form = QFormLayout(dates_group)
        dates_form.setSpacing(10)

        # Start date
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setSpecialValueText(tr("page.relations.not_specified"))
        dates_form.addRow(tr("page.relations.start_date_label"), self.start_date)

        # End date
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setSpecialValueText(tr("page.relations.not_specified"))
        self.end_date.setDate(QDate.currentDate())
        dates_form.addRow(tr("page.relations.end_date_label"), self.end_date)

        # Clear dates checkboxes
        dates_hint = QLabel(tr("page.relations.dates_hint"))
        dates_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 10px;")
        dates_form.addRow("", dates_hint)

        layout.addWidget(dates_group)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(ScreenScale.h(80))
        self.notes.setPlaceholderText(tr("page.relations.additional_notes_placeholder"))
        layout.addWidget(QLabel(tr("page.relations.notes_label")))
        layout.addWidget(self.notes)

        # Validation error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"""
            color: {Config.ERROR_COLOR};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 6px;
            padding: 8px;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_type_changed(self):
        """Enable/disable other description based on type."""
        relation_type = self.type_combo.currentData()
        self.other_desc.setEnabled(relation_type == "other")
        if relation_type != "other":
            self.other_desc.clear()

    def _on_unit_changed(self):
        """Update share hint when unit changes."""
        unit_id = self.unit_combo.currentData()
        if unit_id:
            exclude_id = self.relation.relation_id if self.relation else None
            current_total = self.relation_repo.get_total_ownership_share(unit_id, exclude_id)
            remaining = 2400 - current_total
            self.share_hint.setText(f"{tr('page.relations.remaining_shares')}: {remaining}")

    def _validate_share(self):
        """Validate ownership share doesn't exceed 100% total."""
        unit_id = self.unit_combo.currentData()
        if not unit_id:
            return True

        new_share = self.share_spin.value()
        if new_share == 0:
            self.share_error.setVisible(False)
            return True

        exclude_id = self.relation.relation_id if self.relation else None
        current_total = self.relation_repo.get_total_ownership_share(unit_id, exclude_id)

        if current_total + new_share > 2400:
            self.share_error.setText(f"{tr('page.relations.err_shares_exceed')} ({current_total}/2400)")
            self.share_error.setVisible(True)
            return False

        self.share_error.setVisible(False)
        return True

    def _populate_data(self):
        """Populate form with existing relation data."""
        if not self.relation:
            return

        # Person
        idx = self.person_combo.findData(self.relation.person_id)
        if idx >= 0:
            self.person_combo.setCurrentIndex(idx)

        # Unit
        idx = self.unit_combo.findData(self.relation.unit_id)
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)

        # Relation type
        idx = self.type_combo.findData(self.relation.relation_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        # Other description
        if self.relation.relation_type_other_description:
            self.other_desc.setText(self.relation.relation_type_other_description)

        # Ownership share (direct value in shares 0-2400)
        if self.relation.ownership_share > 0:
            self.share_spin.setValue(self.relation.ownership_share)

        # Dates
        if self.relation.relation_start_date:
            self.start_date.setDate(QDate(
                self.relation.relation_start_date.year,
                self.relation.relation_start_date.month,
                self.relation.relation_start_date.day
            ))

        if self.relation.relation_end_date:
            self.end_date.setDate(QDate(
                self.relation.relation_end_date.year,
                self.relation.relation_end_date.month,
                self.relation.relation_end_date.day
            ))

        # Notes
        if self.relation.relation_notes:
            self.notes.setPlainText(self.relation.relation_notes)

        # Update hint
        self._on_unit_changed()

    def _on_save(self):
        """Validate and save."""
        errors = []

        # Validate required fields
        person_id = self.person_combo.currentData()
        if not person_id:
            errors.append(tr("page.relations.err_select_person"))
            self.person_error.setText(tr("page.relations.required"))
            self.person_error.setVisible(True)
        else:
            self.person_error.setVisible(False)

        unit_id = self.unit_combo.currentData()
        if not unit_id:
            errors.append(tr("page.relations.err_select_unit"))
            self.unit_error.setText(tr("page.relations.required"))
            self.unit_error.setVisible(True)
        else:
            self.unit_error.setVisible(False)

        relation_type = self.type_combo.currentData()

        # Validate "other" type description
        if relation_type == "other" and not self.other_desc.text().strip():
            errors.append(tr("page.relations.err_other_description_required"))

        # Validate share
        if not self._validate_share():
            errors.append(tr("page.relations.err_invalid_share"))

        # Check for duplicate relation
        if person_id and unit_id and relation_type:
            exclude_id = self.relation.relation_id if self.relation else None
            if self.relation_repo.exists(person_id, unit_id, relation_type, exclude_id):
                errors.append(tr("page.relations.err_duplicate_relation"))
                self.type_error.setText(tr("page.relations.duplicate_relation"))
                self.type_error.setVisible(True)
            else:
                self.type_error.setVisible(False)

        if errors:
            self.error_label.setText(" • ".join(errors))
            self.error_label.setVisible(True)
            return

        self.error_label.setVisible(False)
        self.accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        share_2400 = self.share_spin.value()

        # Get dates
        start_date = self.start_date.date().toPyDate() if self.start_date.date().isValid() else None
        end_date = self.end_date.date().toPyDate() if self.end_date.date().isValid() else None

        return {
            "person_id": self.person_combo.currentData(),
            "unit_id": self.unit_combo.currentData(),
            "relation_type": self.type_combo.currentData(),
            "relation_type_other_description": self.other_desc.text().strip() if self.type_combo.currentData() == "other" else None,
            "ownership_share": share_2400,
            "relation_start_date": start_date,
            "relation_end_date": end_date,
            "relation_notes": self.notes.toPlainText().strip() or None,
        }


class RelationsPage(QWidget):
    """Person-Unit Relations management page with Evidence support."""

    view_relation = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.relation_repo = RelationRepository(db)
        self.person_repo = PersonRepository(db)
        self.unit_repo = UnitRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self._persons_cache = {}
        self._units_cache = {}
        self._selected_relation = None  # Currently selected relation for evidence
        self._user_role = None

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        self._title = QLabel(self.i18n.t("relations"))
        self._title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(self._title)
        header_layout.addStretch()

        # Add relation button
        self._add_btn = QPushButton("+ " + self.i18n.t("add_relation"))
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #219A52;
            }}
        """)
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.clicked.connect(self._on_add_relation)
        header_layout.addWidget(self._add_btn)

        layout.addLayout(header_layout)

        # Filters
        filters_frame = QFrame()
        filters_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        filters_frame.setGraphicsEffect(shadow)

        filters_layout = QHBoxLayout(filters_frame)
        filters_layout.setContentsMargins(24, 20, 24, 20)
        filters_layout.setSpacing(20)

        # Person filter
        self._person_filter_label = QLabel(tr("page.relations.person_filter"))
        filters_layout.addWidget(self._person_filter_label)
        self.person_filter = QComboBox()
        self.person_filter.setMinimumWidth(ScreenScale.w(200))
        self.person_filter.addItem(self.i18n.t("all"), "")
        self.person_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.person_filter)

        # Unit filter
        self._unit_filter_label = QLabel(tr("page.relations.unit_filter"))
        filters_layout.addWidget(self._unit_filter_label)
        self.unit_filter = QComboBox()
        self.unit_filter.setMinimumWidth(ScreenScale.w(200))
        self.unit_filter.addItem(self.i18n.t("all"), "")
        self.unit_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.unit_filter)

        # Type filter
        self._type_filter_label = QLabel(tr("page.relations.type_filter"))
        filters_layout.addWidget(self._type_filter_label)
        self.type_filter = QComboBox()
        self.type_filter.addItem(self.i18n.t("all"), "")
        for code, label in vocab_get_options("RelationType"):
            self.type_filter.addItem(label, code)
        self.type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.type_filter)

        filters_layout.addStretch()
        layout.addWidget(filters_frame)

        # Results count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.count_label)

        # Main content splitter (Relations table on left, Evidence on right)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E2E8F0;
                width: 4px;
            }
        """)

        # Relations Table Frame
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        table_shadow = QGraphicsDropShadowEffect()
        table_shadow.setBlurRadius(20)
        table_shadow.setColor(QColor(0, 0, 0, 20))
        table_shadow.setOffset(0, 4)
        table_frame.setGraphicsEffect(table_shadow)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
                border-radius: 12px;
            }}
            QTableView::item {{
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)
        self.table.doubleClicked.connect(self._on_row_double_click)
        self.table.clicked.connect(self._on_relation_selected)

        self.table_model = RelationsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        # Context menu for delete
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        table_layout.addWidget(self.table)
        splitter.addWidget(table_frame)

        # Evidence Panel Frame
        evidence_frame = QFrame()
        evidence_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        evidence_shadow = QGraphicsDropShadowEffect()
        evidence_shadow.setBlurRadius(20)
        evidence_shadow.setColor(QColor(0, 0, 0, 20))
        evidence_shadow.setOffset(0, 4)
        evidence_frame.setGraphicsEffect(evidence_shadow)

        evidence_layout = QVBoxLayout(evidence_frame)
        evidence_layout.setContentsMargins(16, 16, 16, 16)
        evidence_layout.setSpacing(12)

        # Evidence header
        evidence_header = QHBoxLayout()
        self._evidence_title = QLabel(self.i18n.t("evidence"))
        self._evidence_title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_HEADING}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        evidence_header.addWidget(self._evidence_title)
        evidence_header.addStretch()

        # Add evidence button
        self.add_evidence_btn = QPushButton("+ " + self.i18n.t("add_evidence"))
        self.add_evidence_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
            QPushButton:disabled {{
                background-color: #CBD5E0;
            }}
        """)
        self.add_evidence_btn.setCursor(Qt.PointingHandCursor)
        self.add_evidence_btn.clicked.connect(self._on_add_evidence)
        self.add_evidence_btn.setEnabled(False)
        evidence_header.addWidget(self.add_evidence_btn)

        evidence_layout.addLayout(evidence_header)

        # Selected relation info
        self.selected_relation_label = QLabel(self.i18n.t("select_relation_first"))
        self.selected_relation_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 8px;
            background-color: #F8FAFC;
            border-radius: 6px;
        """)
        self.selected_relation_label.setWordWrap(True)
        evidence_layout.addWidget(self.selected_relation_label)

        # Evidence status filter
        status_filter_layout = QHBoxLayout()
        self._status_filter_label = QLabel(tr("page.relations.status_filter"))
        status_filter_layout.addWidget(self._status_filter_label)
        self.evidence_status_filter = QComboBox()
        self.evidence_status_filter.addItem(self.i18n.t("all"), "")
        from services.display_mappings import get_evidence_status_options
        for code, label in get_evidence_status_options():
            self.evidence_status_filter.addItem(label, code)
        self.evidence_status_filter.currentIndexChanged.connect(self._on_evidence_filter_changed)
        self.evidence_status_filter.setEnabled(False)
        status_filter_layout.addWidget(self.evidence_status_filter)
        status_filter_layout.addStretch()
        evidence_layout.addLayout(status_filter_layout)

        # Evidence count
        self.evidence_count_label = QLabel("")
        self.evidence_count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        evidence_layout.addWidget(self.evidence_count_label)

        # Evidence table
        self.evidence_table = QTableView()
        self.evidence_table.setAlternatingRowColors(True)
        self.evidence_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.evidence_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.evidence_table.setShowGrid(False)
        self.evidence_table.verticalHeader().setVisible(False)
        self.evidence_table.horizontalHeader().setStretchLastSection(True)
        self.evidence_table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
            }}
            QTableView::item {{
                padding: 8px 6px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 8px 6px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)
        self.evidence_table.doubleClicked.connect(self._on_evidence_double_click)
        self.evidence_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.evidence_table.customContextMenuRequested.connect(self._show_evidence_context_menu)

        self.evidence_model = EvidenceTableModel(is_arabic=self.i18n.is_arabic())
        self.evidence_table.setModel(self.evidence_model)

        evidence_layout.addWidget(self.evidence_table)

        splitter.addWidget(evidence_frame)

        # Set initial sizes (70% relations, 30% evidence)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

    def _show_context_menu(self, pos):
        """Show context menu for table actions."""
        from PyQt5.QtWidgets import QMenu, QAction

        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)

        edit_action = QAction(tr("page.relations.edit"), self)
        edit_action.triggered.connect(lambda: self._on_row_double_click(index))
        menu.addAction(edit_action)

        delete_action = QAction(tr("page.relations.delete"), self)
        delete_action.triggered.connect(lambda: self._delete_relation(index))
        menu.addAction(delete_action)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def configure_for_role(self, role: str):
        self._user_role = role

    def _delete_relation(self, index):
        """Delete a relation."""
        if self._user_role and self._user_role not in ("admin", "data_manager"):
            return
        relation = self.table_model.get_relation(index.row())
        if not relation:
            return

        if ErrorHandler.confirm(
            self,
            tr("page.relations.confirm_delete_msg"),
            tr("page.relations.confirm_delete_title")
        ):
            try:
                self.relation_repo.delete(relation.relation_id)
                Toast.show_toast(self, tr("page.relations.relation_deleted"), Toast.SUCCESS)
                self._load_relations()
            except Exception as e:
                logger.error(f"Failed to delete relation: {e}")
                Toast.show_toast(self, f"{tr('page.relations.err_delete_failed')}: {str(e)}", Toast.ERROR)

    def refresh(self, data=None):
        """Refresh the relations list."""
        logger.debug("Refreshing relations page")
        self._load_filters()
        self._load_relations()

    def _load_filters(self):
        """Load filter dropdowns."""
        # Cache persons and units
        persons = self.person_repo.get_all(limit=500)
        units = self.unit_repo.get_all(limit=500)

        self._persons_cache = {p.person_id: p for p in persons}
        self._units_cache = {u.unit_id: u for u in units}

        # Update table model cache
        self.table_model.set_cache(self._persons_cache, self._units_cache)

        # Person filter
        current_person = self.person_filter.currentData()
        self.person_filter.clear()
        self.person_filter.addItem(self.i18n.t("all"), "")
        for p in persons:
            self.person_filter.addItem(p.full_name_ar, p.person_id)
        if current_person:
            idx = self.person_filter.findData(current_person)
            if idx >= 0:
                self.person_filter.setCurrentIndex(idx)

        # Unit filter
        current_unit = self.unit_filter.currentData()
        self.unit_filter.clear()
        self.unit_filter.addItem(self.i18n.t("all"), "")
        for u in units:
            self.unit_filter.addItem(u.unit_id, u.unit_id)
        if current_unit:
            idx = self.unit_filter.findData(current_unit)
            if idx >= 0:
                self.unit_filter.setCurrentIndex(idx)

    def _load_relations(self):
        """Load relations with filters."""
        person_id = self.person_filter.currentData()
        unit_id = self.unit_filter.currentData()
        relation_type = self.type_filter.currentData()

        relations = self.relation_repo.search(
            person_id=person_id or None,
            unit_id=unit_id or None,
            relation_type=relation_type or None,
            limit=500
        )

        self.table_model.set_relations(relations)
        self.count_label.setText(f"{tr('page.relations.found')} {len(relations)} {tr('page.relations.relation_unit')}")

    def _on_filter_changed(self):
        self._load_relations()

    def _on_row_double_click(self, index):
        """Handle double-click to edit relation."""
        relation = self.table_model.get_relation(index.row())
        if relation:
            self._edit_relation(relation)

    def _on_add_relation(self):
        """Add new relation."""
        dialog = RelationDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            relation = PersonUnitRelation(**data)

            try:
                self.relation_repo.create(relation)
                Toast.show_toast(self, tr("page.relations.relation_added"), Toast.SUCCESS)
                self._load_relations()
            except Exception as e:
                logger.error(f"Failed to create relation: {e}")
                Toast.show_toast(self, f"{tr('page.relations.err_add_failed')}: {str(e)}", Toast.ERROR)

    def _edit_relation(self, relation: PersonUnitRelation):
        """Edit existing relation."""
        dialog = RelationDialog(self.db, self.i18n, relation=relation, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(relation, key, value)

            try:
                self.relation_repo.update(relation)
                Toast.show_toast(self, tr("page.relations.relation_updated"), Toast.SUCCESS)
                self._load_relations()
            except Exception as e:
                logger.error(f"Failed to update relation: {e}")
                Toast.show_toast(self, f"{tr('page.relations.err_update_failed')}: {str(e)}", Toast.ERROR)

    def _on_relation_selected(self, index):
        """Handle relation selection to update evidence panel."""
        relation = self.table_model.get_relation(index.row())
        if relation:
            self._selected_relation = relation
            self.add_evidence_btn.setEnabled(True)
            self.evidence_status_filter.setEnabled(True)

            # Update selected relation label
            person = self._persons_cache.get(relation.person_id)
            unit = self._units_cache.get(relation.unit_id)
            person_name = person.full_name_ar if person else relation.person_id[:8]
            unit_id = unit.unit_id if unit else relation.unit_id[:15]
            relation_type = relation.relation_type_display_ar

            self.selected_relation_label.setText(
                f"{tr('page.relations.selected_relation')}: {person_name} - {unit_id} ({relation_type})"
            )
            self.selected_relation_label.setStyleSheet(f"""
                color: {Config.TEXT_COLOR};
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 8px;
                background-color: #EBF5FF;
                border-radius: 6px;
                border: 1px solid {Config.PRIMARY_LIGHT};
            """)

            # Load evidence for this relation
            self._load_evidence()
        else:
            self._clear_evidence_panel()

    def _clear_evidence_panel(self):
        """Clear the evidence panel when no relation is selected."""
        self._selected_relation = None
        self.add_evidence_btn.setEnabled(False)
        self.evidence_status_filter.setEnabled(False)
        self.selected_relation_label.setText(self.i18n.t("select_relation_first"))
        self.selected_relation_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 8px;
            background-color: #F8FAFC;
            border-radius: 6px;
        """)
        self.evidence_model.set_evidence([])
        self.evidence_count_label.setText("")

    def _load_evidence(self):
        """Load evidence for the selected relation."""
        if not self._selected_relation:
            return

        status_filter = self.evidence_status_filter.currentData()

        if status_filter:
            evidence_list = self.evidence_repo.search(
                relation_id=self._selected_relation.relation_id,
                verification_status=status_filter
            )
        else:
            evidence_list = self.evidence_repo.get_by_relation(self._selected_relation.relation_id)

        self.evidence_model.set_evidence(evidence_list)
        self.evidence_count_label.setText(f"{len(evidence_list)} {tr('page.relations.evidence_unit')}")

    def _on_evidence_filter_changed(self):
        """Handle evidence status filter change."""
        self._load_evidence()

    def _on_add_evidence(self):
        """Add new evidence for the selected relation."""
        if not self._selected_relation:
            Toast.show_toast(self, self.i18n.t("select_relation_first"), Toast.WARNING)
            return

        dialog = EvidenceDialog(self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            evidence = Evidence(
                relation_id=self._selected_relation.relation_id,
                **data
            )

            try:
                self.evidence_repo.create(evidence)
                Toast.show_toast(self, self.i18n.t("evidence_added"), Toast.SUCCESS)
                self._load_evidence()
            except Exception as e:
                logger.error(f"Failed to create evidence: {e}")
                Toast.show_toast(self, f"{tr('page.relations.err_add_evidence')}: {str(e)}", Toast.ERROR)

    def _on_evidence_double_click(self, index):
        """Handle double-click to edit evidence."""
        evidence = self.evidence_model.get_evidence(index.row())
        if evidence:
            self._edit_evidence(evidence)

    def _edit_evidence(self, evidence: Evidence):
        """Edit existing evidence."""
        dialog = EvidenceDialog(self.i18n, evidence=evidence, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(evidence, key, value)

            try:
                self.evidence_repo.update(evidence)
                Toast.show_toast(self, self.i18n.t("evidence_updated"), Toast.SUCCESS)
                self._load_evidence()
            except Exception as e:
                logger.error(f"Failed to update evidence: {e}")
                Toast.show_toast(self, f"{tr('page.relations.err_update_evidence')}: {str(e)}", Toast.ERROR)

    def _show_evidence_context_menu(self, pos):
        """Show context menu for evidence table actions."""
        from PyQt5.QtWidgets import QMenu, QAction

        index = self.evidence_table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)

        edit_action = QAction(tr("page.relations.edit"), self)
        edit_action.triggered.connect(lambda: self._on_evidence_double_click(index))
        menu.addAction(edit_action)

        delete_action = QAction(tr("page.relations.delete"), self)
        delete_action.triggered.connect(lambda: self._delete_evidence(index))
        menu.addAction(delete_action)

        menu.addSeparator()

        # Verification actions
        verify_action = QAction(tr("page.relations.verify"), self)
        verify_action.triggered.connect(lambda: self._verify_evidence(index, "verified"))
        menu.addAction(verify_action)

        reject_action = QAction(tr("page.relations.reject"), self)
        reject_action.triggered.connect(lambda: self._verify_evidence(index, "rejected"))
        menu.addAction(reject_action)

        menu.exec_(self.evidence_table.viewport().mapToGlobal(pos))

    def _delete_evidence(self, index):
        """Delete an evidence record."""
        if self._user_role and self._user_role not in ("admin", "data_manager"):
            return
        evidence = self.evidence_model.get_evidence(index.row())
        if not evidence:
            return

        if ErrorHandler.confirm(
            self,
            tr("page.relations.confirm_delete_evidence_msg"),
            tr("page.relations.confirm_delete_title")
        ):
            try:
                self.evidence_repo.delete(evidence.evidence_id)
                Toast.show_toast(self, self.i18n.t("evidence_deleted"), Toast.SUCCESS)
                self._load_evidence()
            except Exception as e:
                logger.error(f"Failed to delete evidence: {e}")
                Toast.show_toast(self, f"{tr('page.relations.err_delete_evidence')}: {str(e)}", Toast.ERROR)

    def _verify_evidence(self, index, status: str):
        """Update verification status of evidence."""
        evidence = self.evidence_model.get_evidence(index.row())
        if not evidence:
            return

        try:
            self.evidence_repo.verify(evidence.evidence_id, status)
            status_text = tr("page.relations.status_verified") if status == "verified" else tr("page.relations.status_rejected")
            Toast.show_toast(self, f"{tr('page.relations.evidence_status_updated')}: {status_text}", Toast.SUCCESS)
            self._load_evidence()
        except Exception as e:
            logger.error(f"Failed to verify evidence: {e}")
            Toast.show_toast(self, f"{tr('page.relations.err_verify_evidence')}: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update language."""
        self.setLayoutDirection(get_layout_direction())
        self._title.setText(self.i18n.t("relations"))
        self._add_btn.setText("+ " + self.i18n.t("add_relation"))
        self._person_filter_label.setText(tr("page.relations.person_filter"))
        self._unit_filter_label.setText(tr("page.relations.unit_filter"))
        self._type_filter_label.setText(tr("page.relations.type_filter"))
        self._evidence_title.setText(self.i18n.t("evidence"))
        self.add_evidence_btn.setText("+ " + self.i18n.t("add_evidence"))
        self._status_filter_label.setText(tr("page.relations.status_filter"))
        if not self._selected_relation:
            self.selected_relation_label.setText(self.i18n.t("select_relation_first"))
        self.table_model._columns = [
            ('person', "Person", tr("table.relations.person")),
            ('unit', "Unit", tr("table.relations.unit")),
            ('relation_type', "Relation Type", tr("table.relations.relation_type")),
            ('share', "Share %", tr("table.relations.share")),
            ('status', "Status", tr("table.relations.status")),
            ('start_date', "Start Date", tr("table.relations.start_date")),
            ('notes', "Notes", tr("table.relations.notes")),
        ]
        self.table_model.set_language(is_arabic)
        self.evidence_model._columns = [
            ('type', "Type", tr("table.evidence.type")),
            ('reference', "Reference #", tr("table.evidence.reference")),
            ('date', "Date", tr("table.evidence.date")),
            ('status', "Status", tr("table.evidence.status")),
            ('description', "Description", tr("table.evidence.description")),
        ]
        self.evidence_model.set_language(is_arabic)
