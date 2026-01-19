# -*- coding: utf-8 -*-
"""
Claim Step - Step 6 of Office Survey Wizard.

Simplified step for creating claims.
Note: This is a simplified implementation.
"""

from typing import Dict, Any
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QGroupBox, QFormLayout,
    QLineEdit, QDateEdit, QGridLayout, QFrame
)
from PyQt5.QtCore import Qt, QDate

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from utils.logger import get_logger

logger = get_logger(__name__)


class ClaimStep(BaseStep):
    """Step 6: Claim Creation (Simplified)."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        """Setup the step's UI - exact copy from old wizard."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet("""
            QLabel {
                color: #444;
                font-weight: bold;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 10px;
                color: #606266;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #409eff;
            }
        """)

        main_layout = self.main_layout
        main_layout.setContentsMargins(40, 20, 40, 40)
        main_layout.setSpacing(10)

        # --- Header Section (Outside the Card) ---
        header_layout = QHBoxLayout()

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("تسجيل الحالة")
        title_lbl.setStyleSheet("font-size: 22px; color: #2c3e50; font-weight: bold;")
        sub_lbl = QLabel("ربط المطالبين بالوحدات العقارية وتتبع مطالبات تسجيل حقوق الحيازة")
        sub_lbl.setStyleSheet("font-weight: normal; color: #909399; font-size: 14px;")
        sub_lbl.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)

        icon_label = QLabel()
        icon_label.setFixedSize(50, 50)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 24px; background: #ffffff; border-radius: 10px; border: 1px solid #ebeef5;")

        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(10)

        # --- The Main Card (QFrame) ---
        card = QFrame()
        card.setStyleSheet("""
            QFrame#ClaimCard {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        card.setObjectName("ClaimCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 25, 25, 25)
        card_layout.setSpacing(20)

        # 1. Grid Layout for top fields (RTL order: right to left)
        grid = QGridLayout()
        grid.setSpacing(15)

        # Ensure columns stretch to fill full width
        for i in range(4):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, field_widget, row, col):
            v = QVBoxLayout()
            lbl = QLabel(label_text)
            v.addWidget(lbl)
            v.addWidget(field_widget)
            grid.addLayout(v, row, col)

        # Row 1 (RTL): معرف المطالب | معرف الوحدة المطالب بها | نوع الحالة | طبيعة الأعمال
        self.claim_person_search = QLineEdit()
        self.claim_person_search.setPlaceholderText("اسم الشخص")
        add_field("معرف المطالب", self.claim_person_search, 0, 0)

        self.claim_unit_search = QLineEdit()
        self.claim_unit_search.setPlaceholderText("رقم الوحدة")
        add_field("معرف الوحدة المطالب بها", self.claim_unit_search, 0, 1)

        self.claim_type_combo = QComboBox()
        self.claim_type_combo.addItem("اختر", "")
        self.claim_type_combo.addItem("ملكية", "ownership")
        self.claim_type_combo.addItem("إشغال", "occupancy")
        self.claim_type_combo.addItem("إيجار", "tenancy")
        add_field("نوع الحالة", self.claim_type_combo, 0, 2)

        self.claim_business_nature = QComboBox()
        self.claim_business_nature.addItem("اختر", "")
        self.claim_business_nature.addItem("سكني", "residential")
        self.claim_business_nature.addItem("تجاري", "commercial")
        self.claim_business_nature.addItem("زراعي", "agricultural")
        add_field("طبيعة الأعمال", self.claim_business_nature, 0, 3)

        # Row 2 (RTL): حالة الحالة | المصدر | تاريخ المسح | الأولوية
        self.claim_status_combo = QComboBox()
        self.claim_status_combo.addItem("اختر", "")
        self.claim_status_combo.addItem("جديد", "new")
        self.claim_status_combo.addItem("قيد المراجعة", "under_review")
        self.claim_status_combo.addItem("مكتمل", "completed")
        self.claim_status_combo.addItem("معلق", "pending")
        add_field("حالة الحالة", self.claim_status_combo, 1, 0)

        self.claim_source_combo = QComboBox()
        self.claim_source_combo.addItem("اختر", "")
        self.claim_source_combo.addItem("مسح ميداني", "field_survey")
        self.claim_source_combo.addItem("طلب مباشر", "direct_request")
        self.claim_source_combo.addItem("إحالة", "referral")
        add_field("المصدر", self.claim_source_combo, 1, 1)

        self.claim_survey_date = QDateEdit()
        self.claim_survey_date.setCalendarPopup(True)
        self.claim_survey_date.setDisplayFormat("dd-MM-yyyy")
        self.claim_survey_date.setDate(QDate.currentDate())
        add_field("تاريخ المسح", self.claim_survey_date, 1, 2)

        self.claim_priority_combo = QComboBox()
        self.claim_priority_combo.addItem("اختر", "")
        self.claim_priority_combo.addItem("منخفض", "low")
        self.claim_priority_combo.addItem("عادي", "normal")
        self.claim_priority_combo.addItem("عالي", "high")
        self.claim_priority_combo.addItem("عاجل", "urgent")
        self.claim_priority_combo.setCurrentIndex(2)  # Default to normal
        add_field("الأولوية", self.claim_priority_combo, 1, 3)

        card_layout.addLayout(grid)

        # 2. Notes Section
        notes_label = QLabel("ملاحظات المراجعة")
        card_layout.addWidget(notes_label)
        self.claim_notes = QTextEdit()
        self.claim_notes.setPlaceholderText("ملاحظات إضافية")
        self.claim_notes.setMinimumHeight(100)
        self.claim_notes.setMaximumHeight(120)
        card_layout.addWidget(self.claim_notes)

        # 3. Next Action Date Section
        next_date_label = QLabel("تاريخ الإجراء التالي")
        card_layout.addWidget(next_date_label)
        next_date_container = QHBoxLayout()
        self.claim_next_action_date = QDateEdit()
        self.claim_next_action_date.setCalendarPopup(True)
        self.claim_next_action_date.setDisplayFormat("dd-MM-yyyy")
        self.claim_next_action_date.setMinimumHeight(45)
        next_date_container.addWidget(self.claim_next_action_date)
        card_layout.addLayout(next_date_container)

        # 4. Status Bar (Inside Card) - Evidence available indicator
        self.claim_eval_label = QLabel("الأدلة متوفرة")
        self.claim_eval_label.setAlignment(Qt.AlignCenter)
        self.claim_eval_label.setFixedHeight(50)
        self.claim_eval_label.setStyleSheet("""
            background-color: #e1f7ef;
            color: #10b981;
            border-radius: 8px;
            font-weight: bold;
            font-size: 15px;
        """)
        card_layout.addWidget(self.claim_eval_label)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def _evaluate_for_claim(self):
        """Evaluate relations for claim creation - exact copy from old wizard."""
        owners = [r for r in self.context.relations if r['relation_type'] in ('owner', 'co_owner')]
        tenants = [r for r in self.context.relations if r['relation_type'] == 'tenant']
        occupants = [r for r in self.context.relations if r['relation_type'] == 'occupant']
        heirs = [r for r in self.context.relations if r['relation_type'] == 'heir']

        # Count total evidences
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)

        # Auto-populate unit ID if available
        if self.context.unit:
            self.claim_unit_search.setText(str(self.context.unit.unit_id or ""))

        # Auto-populate claimant name from first person
        if self.context.persons:
            first_person = self.context.persons[0]
            full_name = f"{first_person.get('first_name', '')} {first_person.get('last_name', '')}"
            self.claim_person_search.setText(full_name.strip())

        # Auto-select claim type based on relations
        if owners or heirs:
            # Find index for "ownership"
            for i in range(self.claim_type_combo.count()):
                if self.claim_type_combo.itemData(i) == "ownership":
                    self.claim_type_combo.setCurrentIndex(i)
                    break
        elif tenants:
            for i in range(self.claim_type_combo.count()):
                if self.claim_type_combo.itemData(i) == "tenancy":
                    self.claim_type_combo.setCurrentIndex(i)
                    break
        elif occupants:
            for i in range(self.claim_type_combo.count()):
                if self.claim_type_combo.itemData(i) == "occupancy":
                    self.claim_type_combo.setCurrentIndex(i)
                    break

        # Update status bar based on evidence availability
        if total_evidences > 0:
            self.claim_eval_label.setText(f"الأدلة متوفرة ({total_evidences})")
            self.claim_eval_label.setStyleSheet("""
                background-color: #e1f7ef;
                color: #10b981;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            """)
        else:
            self.claim_eval_label.setText("لا توجد أدلة مرفقة")
            self.claim_eval_label.setStyleSheet("""
                background-color: #fef3c7;
                color: #f59e0b;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            """)

    def on_show(self):
        """Called when step is shown - exact copy from old wizard."""
        super().on_show()
        self._evaluate_for_claim()

    def validate(self) -> StepValidationResult:
        result = self.create_validation_result()

        claim_type = self.claim_type_combo.currentData()
        if not claim_type:
            result.add_error("يجب اختيار نوع الحالة")

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect claim data from form - exact copy from old wizard."""
        # Collect all claimant person IDs
        claimant_ids = [r['person_id'] for r in self.context.relations
                        if r['relation_type'] in ('owner', 'co_owner', 'heir')]
        if not claimant_ids:
            claimant_ids = [r['person_id'] for r in self.context.relations]

        # Collect all evidences
        all_evidences = []
        for rel in self.context.relations:
            all_evidences.extend(rel.get('evidences', []))

        claim_data = {
            "claim_type": self.claim_type_combo.currentData(),
            "priority": self.claim_priority_combo.currentData(),
            "business_nature": self.claim_business_nature.currentData(),
            "source": self.claim_source_combo.currentData() or "OFFICE_SUBMISSION",
            "case_status": self.claim_status_combo.currentData() or "new",
            "survey_date": self.claim_survey_date.date().toString("yyyy-MM-dd"),
            "next_action_date": self.claim_next_action_date.date().toString("yyyy-MM-dd"),
            "notes": self.claim_notes.toPlainText().strip(),
            "status": "draft",
            "claimant_person_ids": claimant_ids,
            "evidence_ids": [e['evidence_id'] for e in all_evidences],
            "unit_id": self.context.unit.unit_id if self.context.unit else None,
            "building_id": self.context.building.building_id if self.context.building else None
        }

        self.context.claim_data = claim_data
        return claim_data

    def get_step_title(self) -> str:
        return "تسجيل الحالة"

    def get_step_description(self) -> str:
        return "ربط المطالبين بالوحدات العقارية وتتبع مطالبات تسجيل حقوق الحيازة"
