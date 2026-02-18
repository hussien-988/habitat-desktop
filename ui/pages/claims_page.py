# -*- coding: utf-8 -*-
"""
Claims/Cases management page with workflow and lifecycle.
Implements UC-007: Claim Creation, UC-008: Claim Lifecycle Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QTextEdit, QTabWidget,
    QAbstractItemView, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem, QSplitter, QScrollArea,
    QFileDialog, QGroupBox, QDateEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QDate
from PyQt5.QtGui import QColor

from app.config import Config
from services.vocab_service import get_options as vocab_get_options
from repositories.database import Database
from ui.components.dialogs.base_dialog import BaseDialog
from ui.components.dialogs import MessageDialog
from controllers.claim_controller import ClaimController
from repositories.unit_repository import UnitRepository
from repositories.person_repository import PersonRepository
from repositories.document_repository import DocumentRepository
from models.claim import Claim
from models.document import Document
from services.workflow_service import WorkflowService
from ui.components.toast import Toast
from ui.components.base_table_model import BaseTableModel
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


# Document types from FSD vocabulary
DOCUMENT_TYPES = [
    ("TAPU_GREEN", "صك ملكية (طابو أخضر)"),
    ("PROPERTY_REG", "بيان قيد عقاري"),
    ("TEMP_REG", "بيان قيد مؤقت"),
    ("COURT_RULING", "حكم قضائي"),
    ("POWER_ATTORNEY", "وكالة خاصة"),
    ("SALE_NOTARIZED", "عقد بيع موثق"),
    ("SALE_INFORMAL", "عقد بيع غير موثق"),
    ("RENT_REGISTERED", "عقد إيجار مسجل"),
    ("RENT_INFORMAL", "عقد إيجار غير مسجل"),
    ("UTILITY_BILL", "فاتورة مرافق"),
    ("MUKHTAR_CERT", "شهادة المختار"),
    ("INHERITANCE", "حصر إرث"),
    ("WITNESS_STATEMENT", "إفادة شاهد"),
    ("CLAIMANT_STATEMENT", "تصريح المطالب"),
]


class ClaimsTableModel(BaseTableModel):
    """Table model for claims."""

    def __init__(self, is_arabic: bool = True):
        columns = [
            ('claim_id', "Claim ID", "رقم المطالبة"),
            ('unit_id', "Unit ID", "رقم الوحدة"),
            ('claim_type', "Type", "النوع"),
            ('status', "Status", "الحالة"),
            ('priority', "Priority", "الأولوية"),
            ('submission_date', "Submission Date", "تاريخ التقديم"),
            ('conflict', "Conflict", "تعارض"),
        ]
        super().__init__(items=[], columns=columns)
        self._is_arabic = is_arabic

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        """Override to add BackgroundRole support for status and conflict."""
        if role == Qt.BackgroundRole:
            if not index.isValid() or index.row() >= len(self._items):
                return None
            claim = self._items[index.row()]
            col = index.column()
            if col == 3:
                status_colors = {
                    "draft": QColor("#F3F4F6"),
                    "submitted": QColor("#DBEAFE"),
                    "screening": QColor("#FEF3C7"),
                    "under_review": QColor("#E0E7FF"),
                    "awaiting_docs": QColor("#FFEDD5"),
                    "conflict": QColor("#FEE2E2"),
                    "approved": QColor("#D1FAE5"),
                    "rejected": QColor("#FEE2E2"),
                }
                return status_colors.get(claim.case_status, QColor("white"))
            if col == 6 and claim.has_conflict:
                return QColor("#FEE2E2")
        return super().data(index, role)

    def get_item_value(self, item, field_name: str):
        """Extract field value from claim object."""
        if field_name == 'claim_id':
            return item.claim_id
        elif field_name == 'unit_id':
            return item.unit_id or "-"
        elif field_name == 'claim_type':
            from services.vocab_service import get_label as vocab_get_label
            return vocab_get_label("ClaimType", item.claim_type)
        elif field_name == 'status':
            from services.vocab_service import get_label as vocab_get_label
            return vocab_get_label("ClaimStatus", item.case_status)
        elif field_name == 'priority':
            from services.vocab_service import get_label as vocab_get_label
            return vocab_get_label("CasePriority", item.priority)
        elif field_name == 'submission_date':
            return str(item.submission_date) if item.submission_date else "-"
        elif field_name == 'conflict':
            return "نعم" if item.has_conflict else "لا"
        return "-"

    def set_claims(self, claims: list):
        self.set_items(claims)

    def get_claim(self, row: int):
        return self.get_item(row)


class ClaimDialog(QDialog):
    """Dialog for creating a new claim."""

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.person_repo = PersonRepository(db)

        self.setWindowTitle(i18n.t("create_claim"))
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("إنشاء مطالبة جديدة")
        title.setStyleSheet(f"font-size: {Config.FONT_SIZE_H2}pt; font-weight: 700;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        # Claim type
        self.type_combo = QComboBox()
        for code, label in vocab_get_options("ClaimType"):
            self.type_combo.addItem(label, code)
        form.addRow("نوع المطالبة:", self.type_combo)

        # Priority
        self.priority_combo = QComboBox()
        for code, label in vocab_get_options("CasePriority"):
            self.priority_combo.addItem(label, code)
        self.priority_combo.setCurrentIndex(1)  # Default to normal
        form.addRow("الأولوية:", self.priority_combo)

        # Source
        self.source_combo = QComboBox()
        for code, label in vocab_get_options("ClaimSource"):
            self.source_combo.addItem(label, code)
        form.addRow("المصدر:", self.source_combo)

        layout.addLayout(form)

        # Splitter for unit and person selection
        splitter = QSplitter(Qt.Horizontal)

        # Unit selection
        unit_frame = QFrame()
        unit_frame.setStyleSheet("background-color: #F8FAFC; border-radius: 8px;")
        unit_layout = QVBoxLayout(unit_frame)

        unit_label = QLabel("اختر المقسم:")
        unit_label.setStyleSheet("font-weight: 600;")
        unit_layout.addWidget(unit_label)

        self.unit_search = QLineEdit()
        self.unit_search.setPlaceholderText("بحث...")
        self.unit_search.textChanged.connect(self._filter_units)
        unit_layout.addWidget(self.unit_search)

        self.unit_list = QListWidget()
        self.unit_list.setSelectionMode(QAbstractItemView.SingleSelection)
        unit_layout.addWidget(self.unit_list)

        splitter.addWidget(unit_frame)

        # Person selection
        person_frame = QFrame()
        person_frame.setStyleSheet("background-color: #F8FAFC; border-radius: 8px;")
        person_layout = QVBoxLayout(person_frame)

        person_label = QLabel("اختر المطالبين (يمكن اختيار أكثر من شخص):")
        person_label.setStyleSheet("font-weight: 600;")
        person_layout.addWidget(person_label)

        self.person_search = QLineEdit()
        self.person_search.setPlaceholderText("بحث بالاسم...")
        self.person_search.textChanged.connect(self._filter_persons)
        person_layout.addWidget(self.person_search)

        self.person_list = QListWidget()
        self.person_list.setSelectionMode(QAbstractItemView.MultiSelection)
        person_layout.addWidget(self.person_list)

        splitter.addWidget(person_frame)
        layout.addWidget(splitter)

        # Notes
        notes_label = QLabel("ملاحظات:")
        layout.addWidget(notes_label)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        layout.addWidget(self.notes)

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
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # Load data
        self._load_units()
        self._load_persons()

    def _load_units(self):
        """Load units into list."""
        units = self.unit_repo.get_all(limit=200)
        for unit in units:
            item = QListWidgetItem(f"{unit.unit_id} - {unit.unit_type_display_ar}")
            item.setData(Qt.UserRole, unit.unit_id)
            self.unit_list.addItem(item)

    def _load_persons(self):
        """Load persons into list."""
        persons = self.person_repo.get_all(limit=200)
        for person in persons:
            item = QListWidgetItem(f"{person.full_name_ar} ({person.national_id or 'N/A'})")
            item.setData(Qt.UserRole, person.person_id)
            self.person_list.addItem(item)

    def _filter_units(self, text):
        """Filter units list."""
        for i in range(self.unit_list.count()):
            item = self.unit_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _filter_persons(self, text):
        """Filter persons list."""
        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_save(self):
        """Validate and save."""
        # Validate unit selection
        selected_unit = self.unit_list.selectedItems()
        if not selected_unit:
            MessageDialog.show_warning(parent=self, title="خطأ", message="يجب اختيار وحدة عقارية")
            return

        # Validate person selection
        selected_persons = self.person_list.selectedItems()
        if not selected_persons:
            MessageDialog.show_warning(parent=self, title="خطأ", message="يجب اختيار شخص واحد على الأقل")
            return

        self.accept()

    def get_data(self) -> dict:
        """Get form data."""
        selected_unit = self.unit_list.selectedItems()[0]
        selected_persons = self.person_list.selectedItems()

        person_ids = [item.data(Qt.UserRole) for item in selected_persons]

        return {
            "claim_type": self.type_combo.currentData(),
            "priority": self.priority_combo.currentData(),
            "source": self.source_combo.currentData(),
            "unit_id": selected_unit.data(Qt.UserRole),
            "person_ids": ",".join(person_ids),
            "notes": self.notes.toPlainText().strip(),
            "case_status": "draft",
        }


class ClaimDetailsDialog(QDialog):
    """
    Dialog for viewing/editing claim details with workflow actions.
    Implements UC-006: Update Existing Claim.
    """

    def __init__(self, db: Database, i18n: I18n, claim: Claim, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claim = claim
        self.workflow = WorkflowService(db)
        self.claim_controller = ClaimController(db)
        self.doc_repo = DocumentRepository(db)
        self.edit_mode = False
        self.documents = []
        self.pending_docs = []  # New documents to add

        self.setWindowTitle(f"تفاصيل المطالبة - {claim.claim_id}")
        self.setMinimumSize(900, 700)
        self._load_documents()
        self._setup_ui()

    def _load_documents(self):
        """Load documents linked to this claim."""
        self.documents = self.doc_repo.get_by_claim(self.claim.claim_uuid)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header with status and edit button
        header = QHBoxLayout()

        title = QLabel(f"المطالبة: {self.claim.claim_id}")
        title.setStyleSheet(f"font-size: {Config.FONT_SIZE_H1}pt; font-weight: 700;")
        header.addWidget(title)

        header.addStretch()

        # Edit button (UC-006 S03)
        self.edit_btn = QPushButton("تعديل المطالبة")
        self.edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        self.edit_btn.clicked.connect(self._toggle_edit_mode)
        header.addWidget(self.edit_btn)

        status_label = QLabel(self.claim.case_status_display_ar)
        status_colors = {
            "draft": Config.TEXT_LIGHT,
            "submitted": Config.INFO_COLOR,
            "screening": Config.WARNING_COLOR,
            "under_review": Config.PRIMARY_COLOR,
            "awaiting_docs": Config.WARNING_COLOR,
            "conflict": Config.ERROR_COLOR,
            "approved": Config.SUCCESS_COLOR,
            "rejected": Config.ERROR_COLOR,
        }
        color = status_colors.get(self.claim.case_status, Config.TEXT_LIGHT)
        status_label.setStyleSheet(f"""
            background-color: {color};
            color: white;
            padding: 8px 16px;
            border-radius: 16px;
            font-weight: 600;
        """)
        header.addWidget(status_label)

        layout.addLayout(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background-color: white; border-radius: 8px; }}
            QTabBar::tab {{ padding: 10px 20px; }}
            QTabBar::tab:selected {{ background-color: {Config.PRIMARY_COLOR}; color: white; }}
        """)

        # Details tab (editable fields)
        self._create_details_tab()

        # Documents tab (UC-006 S06)
        self._create_documents_tab()

        # Workflow tab
        self._create_workflow_tab()

        # History tab (UC-006 audit trail)
        self._create_history_tab()

        layout.addWidget(self.tabs)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_edit)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("حفظ التعديلات")
        self.save_btn.setVisible(False)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
        """)
        self.save_btn.clicked.connect(self._save_changes)
        btn_layout.addWidget(self.save_btn)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _create_details_tab(self):
        """Create the details tab with editable fields."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        details_widget = QWidget()
        details_layout = QFormLayout(details_widget)
        details_layout.setSpacing(12)
        details_layout.setContentsMargins(20, 20, 20, 20)

        # Read-only fields
        details_layout.addRow("رقم المطالبة:", QLabel(self.claim.claim_id))
        details_layout.addRow("رقم الوحدة:", QLabel(self.claim.unit_id or "-"))

        # Editable fields (UC-006 S04, S05)
        self.type_combo = QComboBox()
        for code, label in vocab_get_options("ClaimType"):
            self.type_combo.addItem(label, code)
        idx = self.type_combo.findData(self.claim.claim_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.setEnabled(False)
        details_layout.addRow("النوع:", self.type_combo)

        self.priority_combo = QComboBox()
        for code, label in vocab_get_options("CasePriority"):
            self.priority_combo.addItem(label, code)
        idx = self.priority_combo.findData(self.claim.priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        self.priority_combo.setEnabled(False)
        details_layout.addRow("الأولوية:", self.priority_combo)

        details_layout.addRow("المصدر:", QLabel(self.claim.source_display))
        details_layout.addRow("تاريخ التقديم:", QLabel(str(self.claim.submission_date) if self.claim.submission_date else "-"))
        details_layout.addRow("تعارض:", QLabel("نعم" if self.claim.has_conflict else "لا"))

        # Editable notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(self.claim.notes or "")
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setEnabled(False)
        details_layout.addRow("ملاحظات:", self.notes_edit)

        # Resolution notes
        self.resolution_edit = QTextEdit()
        self.resolution_edit.setPlainText(self.claim.resolution_notes or "")
        self.resolution_edit.setMaximumHeight(80)
        self.resolution_edit.setEnabled(False)
        details_layout.addRow("ملاحظات القرار:", self.resolution_edit)

        scroll.setWidget(details_widget)
        self.tabs.addTab(scroll, "التفاصيل")

    def _create_documents_tab(self):
        """Create documents management tab (UC-006 S06)."""
        docs_widget = QWidget()
        docs_layout = QVBoxLayout(docs_widget)
        docs_layout.setContentsMargins(20, 20, 20, 20)
        docs_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("الوثائق المرفقة:"))
        header.addStretch()

        self.add_doc_btn = QPushButton("+ إضافة وثيقة")
        self.add_doc_btn.setEnabled(False)
        self.add_doc_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:disabled {{ background-color: #ccc; }}
        """)
        self.add_doc_btn.clicked.connect(self._add_document)
        header.addWidget(self.add_doc_btn)

        docs_layout.addLayout(header)

        # Documents list
        self.docs_list = QListWidget()
        self.docs_list.setStyleSheet("""
            QListWidget { border: 1px solid #E5E7EB; border-radius: 8px; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #F3F4F6; }
        """)
        self._refresh_documents_list()
        docs_layout.addWidget(self.docs_list)

        # Info label
        info = QLabel("ملاحظة: لا يمكن استبدال الوثائق، فقط إضافة وثائق جديدة أو إزالة الموجودة")
        info.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        docs_layout.addWidget(info)

        self.tabs.addTab(docs_widget, f"الوثائق ({len(self.documents)})")

    def _refresh_documents_list(self):
        """Refresh the documents list widget."""
        self.docs_list.clear()
        for doc in self.documents:
            item_text = f"{doc.document_type_display_ar}"
            if doc.document_number:
                item_text += f" - رقم: {doc.document_number}"
            if doc.issue_date:
                item_text += f" - تاريخ: {doc.issue_date}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, doc.document_id)
            self.docs_list.addItem(item)

        # Add pending docs
        for doc in self.pending_docs:
            item_text = f"[جديد] {doc.document_type_display_ar}"
            if doc.document_number:
                item_text += f" - رقم: {doc.document_number}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, doc.document_id)
            item.setBackground(QColor("#E8F5E9"))
            self.docs_list.addItem(item)

    def _create_workflow_tab(self):
        """Create workflow actions tab."""
        workflow_widget = QWidget()
        workflow_layout = QVBoxLayout(workflow_widget)
        workflow_layout.setContentsMargins(20, 20, 20, 20)

        workflow_label = QLabel("إجراءات سير العمل:")
        workflow_label.setStyleSheet("font-weight: 600; font-size: 11pt;")
        workflow_layout.addWidget(workflow_label)

        # Available transitions
        transitions = self.workflow.get_available_transitions(self.claim.case_status)

        if transitions:
            for next_status, action_name in transitions:
                btn = QPushButton(action_name)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Config.PRIMARY_COLOR};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 20px;
                        font-weight: 500;
                        margin: 4px;
                    }}
                    QPushButton:hover {{
                        background-color: {Config.PRIMARY_DARK};
                    }}
                """)
                btn.clicked.connect(lambda checked, ns=next_status: self._do_transition(ns))
                workflow_layout.addWidget(btn)
        else:
            no_actions = QLabel("لا توجد إجراءات متاحة لهذه الحالة")
            no_actions.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            workflow_layout.addWidget(no_actions)

        workflow_layout.addStretch()
        self.tabs.addTab(workflow_widget, "سير العمل")

    def _create_history_tab(self):
        """Create history/audit trail tab (UC-006 audit requirement)."""
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(20, 20, 20, 20)

        # Load history using controller
        result = self.claim_controller.get_claim_history(self.claim.claim_uuid)
        history = result.data if result.success else []

        if history:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; }")

            content = QWidget()
            content_layout = QVBoxLayout(content)

            for entry in history:
                frame = QFrame()
                frame.setStyleSheet("""
                    QFrame { background-color: #F8FAFC; border-radius: 8px; padding: 12px; }
                """)
                frame_layout = QVBoxLayout(frame)

                # Header
                header = QLabel(f"تعديل بتاريخ: {entry.get('changed_at', '-')}")
                header.setStyleSheet("font-weight: 600;")
                frame_layout.addWidget(header)

                if entry.get('changed_by'):
                    user = QLabel(f"بواسطة: {entry['changed_by']}")
                    frame_layout.addWidget(user)

                reason = QLabel(f"السبب: {entry.get('change_reason', '-')}")
                reason.setWordWrap(True)
                frame_layout.addWidget(reason)

                content_layout.addWidget(frame)

            content_layout.addStretch()
            scroll.setWidget(content)
            history_layout.addWidget(scroll)
        else:
            no_history = QLabel("لا يوجد سجل تعديلات لهذه المطالبة")
            no_history.setAlignment(Qt.AlignCenter)
            no_history.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            history_layout.addWidget(no_history)

        self.tabs.addTab(history_widget, "السجل")

    def _toggle_edit_mode(self):
        """Toggle between view and edit mode."""
        self.edit_mode = not self.edit_mode

        # Enable/disable editable fields
        self.type_combo.setEnabled(self.edit_mode)
        self.priority_combo.setEnabled(self.edit_mode)
        self.notes_edit.setEnabled(self.edit_mode)
        self.resolution_edit.setEnabled(self.edit_mode)
        self.add_doc_btn.setEnabled(self.edit_mode)

        # Show/hide buttons
        self.save_btn.setVisible(self.edit_mode)
        self.cancel_btn.setVisible(self.edit_mode)

        # Update edit button text
        self.edit_btn.setText("إلغاء التعديل" if self.edit_mode else "تعديل المطالبة")

    def _cancel_edit(self):
        """Cancel editing and revert changes."""
        # Reset fields to original values
        idx = self.type_combo.findData(self.claim.claim_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        idx = self.priority_combo.findData(self.claim.priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)

        self.notes_edit.setPlainText(self.claim.notes or "")
        self.resolution_edit.setPlainText(self.claim.resolution_notes or "")
        self.pending_docs.clear()
        self._refresh_documents_list()

        self._toggle_edit_mode()

    def _add_document(self):
        """Add a new document (UC-006 S06)."""
        dialog = AddDocumentDialog(self.i18n, self)
        if dialog.exec_() == QDialog.Accepted:
            doc_data = dialog.get_data()
            doc = Document(**doc_data)

            # If file was selected, store it
            if dialog.selected_file:
                try:
                    self.doc_repo.store_attachment(dialog.selected_file, doc)
                except Exception as e:
                    logger.error(f"Failed to store attachment: {e}")
                    MessageDialog.show_warning(parent=self, title="خطأ", message=f"فشل في حفظ الملف: {str(e)}")
                    return

            self.pending_docs.append(doc)
            self._refresh_documents_list()
            Toast.show(self, "تمت إضافة الوثيقة (سيتم الحفظ عند تأكيد التعديلات)", Toast.INFO)

    def _save_changes(self):
        """Save changes with audit trail (UC-006 S08-S11)."""
        # Get reason for modification (mandatory per UC-006 S08)
        reason, ok = self._get_modification_reason()
        if not ok or not reason.strip():
            MessageDialog.show_warning(parent=self, title="خطأ", message="يجب إدخال سبب التعديل")
            return

        # Update claim fields
        self.claim.claim_type = self.type_combo.currentData()
        self.claim.priority = self.priority_combo.currentData()
        self.claim.notes = self.notes_edit.toPlainText().strip()
        self.claim.resolution_notes = self.resolution_edit.toPlainText().strip()

        try:
            # Update claim using controller
            data = {
                'claim_type': self.claim.claim_type,
                'priority': self.claim.priority,
                'notes': self.claim.notes,
                'resolution_notes': self.claim.resolution_notes
            }

            result = self.claim_controller.update_claim(
                self.claim.claim_uuid,
                data,
                modification_reason=reason
            )

            if result.success:
                # Save new documents
                for doc in self.pending_docs:
                    self.doc_repo.create(doc)
                    self.doc_repo.link_to_claim(self.claim.claim_uuid, doc.document_id)

                self.pending_docs.clear()
                self._load_documents()
                self._refresh_documents_list()

                Toast.show(self, "تم حفظ التعديلات بنجاح", Toast.SUCCESS)
                self._toggle_edit_mode()
            else:
                MessageDialog.show_error(parent=self, title="خطأ", message=f"فشل في حفظ التعديلات: {result.message}")

        except Exception as e:
            logger.error(f"Failed to save claim changes: {e}")
            MessageDialog.show_error(parent=self, title="خطأ", message=f"فشل في حفظ التعديلات: {str(e)}")

    def _get_modification_reason(self):
        """Get modification reason from user (UC-006 S08)."""
        from PyQt5.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getMultiLineText(
            self,
            "سبب التعديل",
            "يرجى إدخال سبب التعديل (مطلوب):",
            ""
        )
        return reason, ok

    def _do_transition(self, next_status: str):
        """Perform status transition."""
        try:
            self.workflow.transition_claim(self.claim, next_status)
            Toast.show(self, f"تم تغيير الحالة إلى: {next_status}", Toast.SUCCESS)
            self.accept()
        except Exception as e:
            logger.error(f"Transition failed: {e}")
            MessageDialog.show_warning(parent=self, title="خطأ", message=str(e))


class AddDocumentDialog(BaseDialog):
    """Dialog for adding a new document to a claim."""

    def __init__(self, i18n: I18n, parent=None, db=None):
        self.selected_file = None

        super().__init__(
            db=db,
            i18n=i18n,
            title_key="",  # Will use hardcoded title via setWindowTitle below
            parent=parent,
            size=(500, 400)
        )
        # Override title with hardcoded Arabic (preserving existing behavior)
        self.setWindowTitle("إضافة وثيقة جديدة")
        self._setup_ui()

    def _setup_ui(self):
        layout = self.main_layout
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        # Document type
        self.type_combo = QComboBox()
        for code, ar in DOCUMENT_TYPES:
            self.type_combo.addItem(ar, code)
        form.addRow("نوع الوثيقة:", self.type_combo)

        # Document number
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("رقم الوثيقة (اختياري)")
        form.addRow("رقم الوثيقة:", self.number_edit)

        # Issue date
        self.issue_date = QDateEdit()
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDate(QDate.currentDate())
        self.issue_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("تاريخ الإصدار:", self.issue_date)

        # Issuing authority
        self.authority_edit = QLineEdit()
        self.authority_edit.setPlaceholderText("الجهة المصدرة (اختياري)")
        form.addRow("الجهة المصدرة:", self.authority_edit)

        layout.addLayout(form)

        # File selection
        file_frame = QGroupBox("ملف الوثيقة")
        file_layout = QHBoxLayout(file_frame)

        self.file_label = QLabel("لم يتم اختيار ملف")
        self.file_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        file_layout.addWidget(self.file_label)

        browse_btn = QPushButton("استعراض...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_frame)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("ملاحظات (اختياري)")
        self.notes_edit.setMaximumHeight(80)
        layout.addWidget(self.notes_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("إضافة")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """Browse for a document file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر ملف الوثيقة",
            "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.doc *.docx);;All Files (*)"
        )
        if file_path:
            self.selected_file = file_path
            # Show just filename
            from pathlib import Path
            self.file_label.setText(Path(file_path).name)
            self.file_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

    def _on_save(self):
        """Validate and accept."""
        self.accept()

    def get_data(self) -> dict:
        """Get document data."""
        from datetime import date
        return {
            "document_type": self.type_combo.currentData(),
            "document_number": self.number_edit.text().strip() or None,
            "issue_date": self.issue_date.date().toPyDate(),
            "issuing_authority": self.authority_edit.text().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None,
        }


class ClaimsPage(QWidget):
    """Claims management page."""

    view_claim = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claim_controller = ClaimController(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel(self.i18n.t("claims"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Add claim button
        from ui.components.custom_button import CustomButton
        add_btn = CustomButton.primary(self.i18n.t("create_claim"), self, width=160, height=45, icon="+")
        add_btn.clicked.connect(self._on_add_claim)
        header_layout.addWidget(add_btn)

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

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("بحث برقم المطالبة...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        self.search_input.textChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.search_input)

        # Status filter
        self.status_combo = QComboBox()
        self.status_combo.addItem(self.i18n.t("all"), "")
        for code, label in vocab_get_options("ClaimStatus"):
            self.status_combo.addItem(label, code)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.status_combo)

        # Type filter
        self.type_combo = QComboBox()
        self.type_combo.addItem(self.i18n.t("all"), "")
        for code, label in vocab_get_options("ClaimType"):
            self.type_combo.addItem(label, code)
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.type_combo)

        # Conflicts only
        self.conflicts_btn = QPushButton("التعارضات فقط")
        self.conflicts_btn.setCheckable(True)
        self.conflicts_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Config.ERROR_COLOR};
                border: 1px solid {Config.ERROR_COLOR};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:checked {{
                background-color: {Config.ERROR_COLOR};
                color: white;
            }}
        """)
        self.conflicts_btn.clicked.connect(self._on_filter_changed)
        filters_layout.addWidget(self.conflicts_btn)

        filters_layout.addStretch()
        layout.addWidget(filters_frame)

        # Results count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.count_label)

        # Table
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

        self.table_model = ClaimsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        table_layout.addWidget(self.table)
        layout.addWidget(table_frame)

    def refresh(self, data=None):
        """Refresh the claims list."""
        logger.debug("Refreshing claims page")
        self._load_claims()

    def _load_claims(self):
        """Load claims with filters."""
        search = self.search_input.text().strip()
        status = self.status_combo.currentData()
        claim_type = self.type_combo.currentData()
        conflicts_only = self.conflicts_btn.isChecked()

        # Use controller to search claims
        result = self.claim_controller.search_claims(
            claim_id=search or None,
            status=status or None,
            claim_type=claim_type or None,
            has_conflict=True if conflicts_only else None,
            limit=500
        )

        if result.success:
            claims = result.data
            self.table_model.set_claims(claims)
            self.count_label.setText(f"تم العثور على {len(claims)} مطالبة")
        else:
            logger.error(f"Failed to load claims: {result.message}")
            self.table_model.set_claims([])
            self.count_label.setText("تم العثور على 0 مطالبة")

    def _on_filter_changed(self):
        self._load_claims()

    def _on_row_double_click(self, index):
        claim = self.table_model.get_claim(index.row())
        if claim:
            dialog = ClaimDetailsDialog(self.db, self.i18n, claim, self)
            dialog.exec_()
            self._load_claims()  # Refresh after potential changes

    def _on_add_claim(self):
        """Add new claim."""
        dialog = ClaimDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            # Use controller to create claim
            result = self.claim_controller.create_claim(data)

            if result.success:
                Toast.show(self, "تم إنشاء المطالبة بنجاح", Toast.SUCCESS)

                # Show conflict warning if exists
                if hasattr(result, 'conflict_warning') and result.conflict_warning:
                    Toast.show(self, "تحذير: تم الكشف عن مطالبات متعارضة", Toast.WARNING)

                self._load_claims()
            else:
                error_msg = result.message
                if hasattr(result, 'validation_errors') and result.validation_errors:
                    error_msg += "\n" + "\n".join(result.validation_errors)
                Toast.show(self, f"فشل في إنشاء المطالبة: {error_msg}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        self.table_model.set_language(is_arabic)
