# -*- coding: utf-8 -*-
"""
Relation Step - Step 5 of Office Survey Wizard.

Allows user to:
- Link persons to units with relations
- Define relation type and ownership details
- Upload evidence documents
"""

from typing import Dict, Any, List
import uuid
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QDateEdit,
    QDoubleSpinBox, QLineEdit, QTextEdit, QFrame, QGridLayout, QButtonGroup,
    QRadioButton, QFileDialog
)
from PyQt5.QtCore import Qt, QDate

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from utils.logger import get_logger
from ui.components.toast import Toast

logger = get_logger(__name__)


class RelationStep(BaseStep):
    """Step 5: Relations & Evidence."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._editing_relation_index = None
        self._current_relation_evidences = []
        self._relation_file_paths = []

    def setup_ui(self):
        """Setup the step's UI - exact copy from old wizard."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        outer = self.main_layout
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        # Header (title + subtitle) placed outside the card
        title_box = QVBoxLayout()
        title = QLabel("العلاقة والأدلة")
        title.setStyleSheet("color: #111827; font-weight: 700; font-size: 16px;")
        subtitle = QLabel("تسجيل تفاصيل ملكية شخص للوحدة عقارية")
        subtitle.setStyleSheet("color: #6B7280; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout = QHBoxLayout()
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        outer.addLayout(header_layout)

        # Card Container (holds all fields & actions)
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)
        outer.addWidget(card)

        # Small icon button inside the card aligned to the right
        top_btn = QPushButton("⚙")
        top_btn.setFixedSize(34, 34)
        top_btn.setStyleSheet("""
            QPushButton {
                background-color: #F9FAFB;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #F3F4F6; }
        """)
        top_btn_row = QHBoxLayout()
        top_btn_row.addStretch(1)
        top_btn_row.addWidget(top_btn)
        card_layout.addLayout(top_btn_row)

        # Person row with dropdown
        person_row = QHBoxLayout()
        person_row.setSpacing(10)

        # Person selector combo
        self.rel_person_combo = QComboBox()
        self.rel_person_combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 700;
                color: #111827;
                min-width: 200px;
            }
        """)

        avatar = QLabel("👤")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(38, 38)
        avatar.setStyleSheet("""
            QLabel {
                background-color: #EEF2FF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                font-size: 16px;
            }
        """)

        person_row.addWidget(avatar)
        person_row.addWidget(self.rel_person_combo)
        person_row.addStretch(1)
        card_layout.addLayout(person_row)

        # Grid fields
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        label_style = "color: #374151; font-weight: 600; font-size: 12px;"
        input_style = """
            QComboBox, QDateEdit, QDoubleSpinBox, QLineEdit {
                background: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
        """

        # Row 0 labels
        contract_type_lbl = QLabel("نوع العقد")
        contract_type_lbl.setStyleSheet(label_style)
        grid.addWidget(contract_type_lbl, 0, 0)

        relation_type_lbl = QLabel("نوع العلاقة")
        relation_type_lbl.setStyleSheet(label_style)
        grid.addWidget(relation_type_lbl, 0, 1)

        start_date_lbl = QLabel("تاريخ بدء العلاقة")
        start_date_lbl.setStyleSheet(label_style)
        grid.addWidget(start_date_lbl, 0, 2)

        # Row 1 inputs
        self.rel_contract_type = QComboBox()
        self.rel_contract_type.addItems(["اختر", "عقد إيجار", "عقد بيع", "عقد شراكة"])
        self.rel_contract_type.setStyleSheet(input_style)

        self.rel_type_combo = QComboBox()
        rel_types = [
            ("owner", "مالك"), ("co_owner", "شريك في الملكية"),
            ("tenant", "مستأجر"), ("occupant", "شاغل"),
            ("heir", "وارث"), ("guardian", "ولي/وصي"), ("other", "أخرى")
        ]
        for code, ar in rel_types:
            self.rel_type_combo.addItem(ar, code)
        self.rel_type_combo.setStyleSheet(input_style)

        self.rel_start_date = QDateEdit()
        self.rel_start_date.setCalendarPopup(True)
        self.rel_start_date.setDisplayFormat("yyyy-MM-dd")
        self.rel_start_date.setDate(QDate.currentDate())
        self.rel_start_date.setStyleSheet(input_style)

        grid.addWidget(self.rel_contract_type, 1, 0)
        grid.addWidget(self.rel_type_combo, 1, 1)
        grid.addWidget(self.rel_start_date, 1, 2)

        # Row 2 labels
        ownership_share_lbl = QLabel("حصة الملكية")
        ownership_share_lbl.setStyleSheet(label_style)
        grid.addWidget(ownership_share_lbl, 2, 0)

        evidence_type_lbl = QLabel("نوع الدليل")
        evidence_type_lbl.setStyleSheet(label_style)
        grid.addWidget(evidence_type_lbl, 2, 1)

        evidence_desc_lbl = QLabel("وصف الدليل")
        evidence_desc_lbl.setStyleSheet(label_style)
        grid.addWidget(evidence_desc_lbl, 2, 2)

        # Row 3 inputs
        self.rel_share = QDoubleSpinBox()
        self.rel_share.setRange(0, 100)
        self.rel_share.setDecimals(2)
        self.rel_share.setSuffix(" %")
        self.rel_share.setValue(0)
        self.rel_share.setStyleSheet(input_style)

        self.rel_evidence_type = QComboBox()
        self.rel_evidence_type.addItems(["اختر", "صك", "عقد", "وكالة", "إقرار"])
        self.rel_evidence_type.setStyleSheet(input_style)

        self.rel_evidence_desc = QLineEdit()
        self.rel_evidence_desc.setPlaceholderText("-")
        self.rel_evidence_desc.setStyleSheet(input_style)

        grid.addWidget(self.rel_share, 3, 0)
        grid.addWidget(self.rel_evidence_type, 3, 1)
        grid.addWidget(self.rel_evidence_desc, 3, 2)

        # Notes label + full-width notes
        notes_lbl = QLabel("ادخل ملاحظاتك")
        notes_lbl.setStyleSheet(label_style)
        self.rel_notes = QTextEdit()
        self.rel_notes.setPlaceholderText("-")
        self.rel_notes.setMinimumHeight(70)
        self.rel_notes.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QTextEdit:focus {
                border: 1px solid #3B82F6;
            }
        """)

        grid.addWidget(notes_lbl, 4, 0, 1, 3)
        grid.addWidget(self.rel_notes, 5, 0, 1, 3)

        card_layout.addLayout(grid)

        # Documents section
        docs_title = QLabel("صور المستندات")
        docs_title.setStyleSheet(label_style)
        card_layout.addWidget(docs_title)

        docs_row = QHBoxLayout()
        docs_row.setSpacing(18)

        self.rel_rb_has = QRadioButton("يوجد مستندات")
        self.rel_rb_none = QRadioButton("لا يوجد مستندات")
        self.rel_rb_has.setChecked(True)

        grp = QButtonGroup(self)
        grp.addButton(self.rel_rb_has)
        grp.addButton(self.rel_rb_none)

        docs_row.addWidget(self.rel_rb_has)
        docs_row.addWidget(self.rel_rb_none)
        docs_row.addStretch(1)

        card_layout.addLayout(docs_row)

        # Upload box
        upload_box = QFrame()
        upload_box.setStyleSheet("""
            QFrame {
                border: 2px dashed #D1D5DB;
                border-radius: 12px;
                background-color: #FBFDFF;
                min-height: 70px;
            }
        """)
        up = QHBoxLayout(upload_box)
        up.setContentsMargins(12, 10, 12, 10)
        up.setSpacing(12)

        self.rel_thumb = QLabel("📄")
        self.rel_thumb.setAlignment(Qt.AlignCenter)
        self.rel_thumb.setStyleSheet("""
            QLabel {
                background-color: #EEF2FF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                min-width: 54px;
                min-height: 54px;
                font-size: 24px;
            }
        """)
        up.addWidget(self.rel_thumb)

        # Center content (link-like button)
        center_col = QVBoxLayout()
        center_col.setSpacing(4)

        self.rel_upload_btn = QPushButton("ارفع صور المستندات")
        self.rel_upload_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #2563EB;
                font-weight: 700;
                text-decoration: underline;
                text-align: right;
            }
        """)
        self.rel_upload_btn.clicked.connect(self._pick_evidence_files)

        hint = QLabel("PNG / JPG / PDF")
        hint.setStyleSheet("color: #6B7280; font-size: 11px;")

        center_col.addWidget(self.rel_upload_btn, alignment=Qt.AlignRight)
        center_col.addWidget(hint, alignment=Qt.AlignRight)

        up.addLayout(center_col)
        up.addStretch(1)

        # Optional right icon button
        self.rel_action_btn = QPushButton("⬆")
        self.rel_action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 700;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: #1D4ED8;
            }}
        """)
        self.rel_action_btn.setFixedHeight(44)
        self.rel_action_btn.clicked.connect(self._pick_evidence_files)
        up.addWidget(self.rel_action_btn)

        card_layout.addWidget(upload_box)

        # Save relation button
        save_btn_row = QHBoxLayout()
        save_btn_row.addStretch(1)

        self.btn_save_relation = QPushButton("حفظ العلاقة ✓")
        self.btn_save_relation.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 32px;
                font-weight: 700;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #1D4ED8;
            }}
        """)
        self.btn_save_relation.clicked.connect(self._save_relation)
        save_btn_row.addWidget(self.btn_save_relation)

        card_layout.addLayout(save_btn_row)

        # Saved relations list
        outer.addSpacing(12)
        saved_title = QLabel("العلاقات المحفوظة")
        saved_title.setStyleSheet("color: #111827; font-weight: 700; font-size: 14px;")
        outer.addWidget(saved_title)

        self.relations_list_frame = QFrame()
        self.relations_list_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        self.relations_list_layout = QVBoxLayout(self.relations_list_frame)
        self.relations_list_layout.setContentsMargins(12, 12, 12, 12)
        self.relations_list_layout.setSpacing(8)
        outer.addWidget(self.relations_list_frame)

        outer.addStretch(1)

    def _pick_evidence_files(self):
        """Pick evidence files for relation - exact copy from old wizard."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "اختر المستندات",
            "",
            "Images/PDF (*.png *.jpg *.jpeg *.pdf);;All Files (*.*)"
        )
        if files:
            self.rel_thumb.setText(str(len(files)))
            self.rel_thumb.setToolTip("\n".join(files))
            # Store file paths for later processing
            self._relation_file_paths = files

    def _populate_relations_persons(self):
        """Populate the persons combo for relations - exact copy from old wizard."""
        self.rel_person_combo.clear()
        for person in self.context.persons:
            full_name = f"{person['first_name']} {person['last_name']}"
            self.rel_person_combo.addItem(full_name, person['person_id'])

    def _save_relation(self):
        """Save person-unit relation with linked evidences - exact copy from old wizard."""
        if self.rel_person_combo.count() == 0:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "خطأ", "لا يوجد أشخاص لتحديد العلاقة")
            return

        # Build evidence list from uploaded files
        evidences = []
        if hasattr(self, '_relation_file_paths') and self._relation_file_paths:
            for file_path in self._relation_file_paths:
                evidence = {
                    "evidence_id": str(uuid.uuid4()),
                    "document_type": self.rel_evidence_type.currentText() if self.rel_evidence_type.currentIndex() > 0 else "غير محدد",
                    "description": self.rel_evidence_desc.text().strip() or None,
                    "file_path": file_path,
                    "upload_date": datetime.now().strftime("%Y-%m-%d")
                }
                evidences.append(evidence)

        relation = {
            "relation_id": str(uuid.uuid4()) if not hasattr(self, '_editing_relation_index') or self._editing_relation_index is None else self.context.relations[self._editing_relation_index]['relation_id'],
            "person_id": self.rel_person_combo.currentData(),
            "person_name": self.rel_person_combo.currentText(),
            "relation_type": self.rel_type_combo.currentData(),
            "ownership_share": self.rel_share.value(),
            "start_date": self.rel_start_date.date().toString("yyyy-MM-dd"),
            "contract_type": self.rel_contract_type.currentText() if self.rel_contract_type.currentIndex() > 0 else None,
            "evidence_type": self.rel_evidence_type.currentText() if self.rel_evidence_type.currentIndex() > 0 else None,
            "evidence_description": self.rel_evidence_desc.text().strip() or None,
            "notes": self.rel_notes.toPlainText().strip(),
            "evidences": evidences
        }

        if hasattr(self, '_editing_relation_index') and self._editing_relation_index is not None:
            self.context.relations[self._editing_relation_index] = relation
            Toast.show_toast(self, "تم تحديث العلاقة", Toast.SUCCESS)
        else:
            self.context.relations.append(relation)
            Toast.show_toast(self, "تم حفظ العلاقة", Toast.SUCCESS)

        self._clear_relation_form()
        self._update_relations_list()

    def _update_relations_list(self):
        """Update the list of saved relations."""
        # Clear existing items
        while self.relations_list_layout.count():
            child = self.relations_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if len(self.context.relations) == 0:
            empty_label = QLabel("لم يتم إضافة أي علاقات بعد")
            empty_label.setStyleSheet("color: #6B7280; font-size: 12px; padding: 12px;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.relations_list_layout.addWidget(empty_label)
        else:
            for idx, relation in enumerate(self.context.relations):
                rel_card = QFrame()
                rel_card.setStyleSheet("""
                    QFrame {
                        background-color: #F9FAFB;
                        border: 1px solid #E1E8ED;
                        border-radius: 8px;
                        padding: 8px;
                    }
                """)
                rel_layout = QHBoxLayout(rel_card)
                rel_layout.setContentsMargins(12, 8, 12, 8)

                # Relation info
                info_label = QLabel(f"👤 {relation['person_name']} - {self._get_relation_type_ar(relation['relation_type'])} ({relation['ownership_share']}%)")
                info_label.setStyleSheet("color: #111827; font-weight: 600; font-size: 12px;")
                rel_layout.addWidget(info_label)
                rel_layout.addStretch()

                # Delete button
                delete_btn = QPushButton("🗑")
                delete_btn.setFixedSize(28, 28)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FEE2E2;
                        border: none;
                        border-radius: 6px;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background-color: #FCA5A5;
                    }
                """)
                delete_btn.clicked.connect(lambda checked, i=idx: self._delete_relation(i))
                rel_layout.addWidget(delete_btn)

                self.relations_list_layout.addWidget(rel_card)

    def _get_relation_type_ar(self, relation_type: str) -> str:
        """Get Arabic name for relation type."""
        types = {
            "owner": "مالك",
            "co_owner": "شريك في الملكية",
            "tenant": "مستأجر",
            "occupant": "شاغل",
            "heir": "وارث",
            "guardian": "ولي/وصي",
            "other": "أخرى"
        }
        return types.get(relation_type, relation_type)

    def _delete_relation(self, index: int):
        """Delete a relation."""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            "هل أنت متأكد من حذف هذه العلاقة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.context.relations.pop(index)
            self._update_relations_list()
            Toast.show_toast(self, "تم حذف العلاقة", Toast.WARNING)

    def _clear_relation_form(self):
        """Clear relation form fields - exact copy from old wizard."""
        self._editing_relation_index = None
        self._current_relation_evidences = []
        self._relation_file_paths = []

        # Reset form fields
        self.rel_share.setValue(0)
        self.rel_start_date.setDate(QDate.currentDate())
        self.rel_notes.clear()
        self.rel_contract_type.setCurrentIndex(0)
        self.rel_type_combo.setCurrentIndex(0)
        self.rel_evidence_type.setCurrentIndex(0)
        self.rel_evidence_desc.clear()
        self.rel_thumb.setText("📄")
        self.rel_thumb.setToolTip("")

        self._populate_relations_persons()

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        # Check if at least one relation exists
        if len(self.context.relations) == 0:
            result.add_error("يجب تسجيل علاقة واحدة على الأقل")

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "relations": self.context.relations,
            "relations_count": len(self.context.relations)
        }

    def populate_data(self):
        """Populate the step with data from context."""
        self._populate_relations_persons()
        self._update_relations_list()

    def on_show(self):
        """Called when step is shown."""
        super().on_show()
        self._populate_relations_persons()
        self._update_relations_list()

    def get_step_title(self) -> str:
        """Get step title."""
        return "العلاقات والأدلة"

    def get_step_description(self) -> str:
        """Get step description."""
        return "تسجيل تفاصيل ملكية شخص للوحدة عقارية"
