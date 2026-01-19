# -*- coding: utf-8 -*-
"""
Review Step - Step 7 of Office Survey Wizard.

Final review and submission step.
"""

from typing import Dict, Any, Tuple
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame, QGroupBox,
    QHBoxLayout, QGridLayout, QLineEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class ReviewStep(BaseStep):
    """Step 7: Review & Submit."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        """Setup the step's UI - exact copy from old wizard."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet("""
            QLabel {
                color: #444;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                background-color: #f9fafb;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 10px;
                color: #606266;
            }
        """)

        layout = self.main_layout
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(15)

        # --- Header Section ---
        header_layout = QHBoxLayout()

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("المراجعة النهائية")
        title_lbl.setStyleSheet("font-size: 22px; color: #2c3e50; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignRight)
        sub_lbl = QLabel("مراجعة جميع البيانات المدخلة قبل الإرسال")
        sub_lbl.setStyleSheet("font-weight: normal; color: #909399; font-size: 14px;")
        sub_lbl.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)

        # Reference number badge
        self.review_ref_label = QLabel("")
        self.review_ref_label.setStyleSheet(f"""
            background-color: {Config.SUCCESS_COLOR};
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: bold;
        """)

        header_layout.addWidget(self.review_ref_label)
        header_layout.addStretch()
        header_layout.addLayout(title_vbox)
        layout.addLayout(header_layout)

        # --- Validation Status Frame ---
        self.validation_frame = QFrame()
        self.validation_frame.setStyleSheet("""
            QFrame { border-radius: 8px; padding: 12px; }
        """)
        val_layout = QVBoxLayout(self.validation_frame)
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setAlignment(Qt.AlignRight)
        val_layout.addWidget(self.validation_label)
        layout.addWidget(self.validation_frame)

        # --- Scroll Area for Review Cards ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        review_content = QWidget()
        review_layout = QVBoxLayout(review_content)
        review_layout.setSpacing(20)

        # Card 1: Unit Information (Step 2)
        self.review_unit_card = self._create_review_card("الوحدة العقارية", "step2")
        review_layout.addWidget(self.review_unit_card)

        # Card 2: Household Information (Step 3)
        self.review_household_card = self._create_review_card("الأسرة والإشغال", "step3")
        review_layout.addWidget(self.review_household_card)

        # Card 3: Persons Information (Step 4)
        self.review_persons_card = self._create_review_card("الأشخاص المسجلين", "step4")
        review_layout.addWidget(self.review_persons_card)

        # Card 4: Relations Information (Step 5)
        self.review_relations_card = self._create_review_card("العلاقات والأدلة", "step5")
        review_layout.addWidget(self.review_relations_card)

        # Card 5: Claim Information (Step 6)
        self.review_claim_card = self._create_review_card("تسجيل الحالة", "step6")
        review_layout.addWidget(self.review_claim_card)

        review_layout.addStretch()
        scroll.setWidget(review_content)
        layout.addWidget(scroll)

    def _create_review_card(self, title: str, step_id: str) -> QFrame:
        """Create a review card matching the style of other steps - exact copy from old wizard."""
        card = QFrame()
        card.setObjectName(f"review_card_{step_id}")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 20, 25, 20)
        card_layout.setSpacing(15)

        # Card Header
        header_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; color: #2c3e50; font-weight: bold;")
        title_label.setAlignment(Qt.AlignRight)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # Content Grid (will be populated dynamically)
        content_widget = QWidget()
        content_widget.setObjectName(f"content_{step_id}")
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_layout = QGridLayout(content_widget)
        content_layout.setSpacing(15)
        for i in range(4):
            content_layout.setColumnStretch(i, 1)
        card_layout.addWidget(content_widget)

        return card

    def _create_review_field(self, label_text: str, value_text: str) -> QVBoxLayout:
        """Create a read-only field for review display - exact copy from old wizard."""
        v = QVBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-weight: bold; color: #444; font-size: 12px;")
        lbl.setAlignment(Qt.AlignRight)
        lbl.setLayoutDirection(Qt.RightToLeft)

        value = QLineEdit(value_text)
        value.setReadOnly(True)
        value.setAlignment(Qt.AlignRight)
        value.setLayoutDirection(Qt.RightToLeft)
        value.setStyleSheet("""
            QLineEdit {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 10px;
                color: #374151;
                text-align: right;
            }
        """)

        v.addWidget(lbl)
        v.addWidget(value)
        return v

    def _run_final_validation(self) -> Tuple[list, list]:
        """Run comprehensive final validation - exact copy from old wizard."""
        errors = []
        warnings = []

        # Required checks
        if not self.context.building:
            errors.append("لم يتم اختيار مبنى")

        if not self.context.unit and not self.context.is_new_unit:
            errors.append("لم يتم اختيار أو إنشاء وحدة عقارية")

        if len(self.context.households) == 0:
            warnings.append("لم يتم تسجيل أي أسرة")

        if len(self.context.persons) == 0:
            errors.append("لم يتم تسجيل أي شخص")

        if len(self.context.relations) == 0:
            warnings.append("لم يتم تحديد أي علاقات")

        # Check for contact person
        has_contact = any(p.get('is_contact_person') for p in self.context.persons)
        if not has_contact and len(self.context.persons) > 0:
            warnings.append("لم يتم تحديد شخص تواصل رئيسي")

        # Check evidences
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)
        if total_evidences == 0:
            warnings.append("لم يتم إرفاق أي وثائق داعمة")

        # Check claim
        if not self.context.claim_data:
            warnings.append("لم يتم إنشاء المطالبة")

        return errors, warnings

    def _populate_review(self):
        """Populate the review step with all collected data - exact copy from old wizard."""
        # Reference number
        self.review_ref_label.setText(f"الرقم المرجعي: {self.context.reference_number}")

        # Run validation
        errors, warnings = self._run_final_validation()

        if errors:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FEE2E2;
                    border: 1px solid {Config.ERROR_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            val_text = "أخطاء يجب تصحيحها:\n" + "\n".join(f"• {e}" for e in errors)
            if warnings:
                val_text += "\n\nتحذيرات:\n" + "\n".join(f"• {w}" for w in warnings)
            self.validation_label.setText(val_text)
        elif warnings:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FEF3C7;
                    border: 1px solid {Config.WARNING_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            self.validation_label.setText("تحذيرات:\n" + "\n".join(f"• {w}" for w in warnings))
        else:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #D1FAE5;
                    border: 1px solid {Config.SUCCESS_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            self.validation_label.setText("جميع البيانات مكتملة وجاهزة للحفظ")

        # Populate Card 1: Unit Information (Step 2)
        self._populate_unit_review_card()

        # Populate Card 2: Household Information (Step 3)
        self._populate_household_review_card()

        # Populate Card 3: Persons Information (Step 4)
        self._populate_persons_review_card()

        # Populate Card 4: Relations Information (Step 5)
        self._populate_relations_review_card()

        # Populate Card 5: Claim Information (Step 6)
        self._populate_claim_review_card()

    def _clear_grid_layout(self, grid_layout):
        """Clear all items from a grid layout - exact copy from old wizard."""
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        """Recursively clear a layout - exact copy from old wizard."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _populate_unit_review_card(self):
        """Populate the unit review card (Step 2 data) - exact copy from old wizard."""
        content_widget = self.review_unit_card.findChild(QWidget, "content_step2")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        # Building info
        building_id = self.context.building.building_id if self.context.building else "-"
        building_type = self.context.building.building_type_display if self.context.building and hasattr(self.context.building, 'building_type_display') else "-"

        # Unit info
        if self.context.unit:
            unit_id = str(self.context.unit.unit_id) if self.context.unit.unit_id else "-"
            unit_type = self.context.unit.unit_type_display if hasattr(self.context.unit, 'unit_type_display') else "-"
            floor = str(self.context.unit.floor_number) if hasattr(self.context.unit, 'floor_number') and self.context.unit.floor_number else "-"
            apartment = str(self.context.unit.apartment_number) if hasattr(self.context.unit, 'apartment_number') and self.context.unit.apartment_number else "-"
        elif self.context.is_new_unit and self.context.new_unit_data:
            unit_id = "جديد"
            unit_type = self.context.new_unit_data.get('unit_type', '-')
            floor = str(self.context.new_unit_data.get('floor_number', '-'))
            apartment = str(self.context.new_unit_data.get('apartment_number', '-'))
        else:
            unit_id = "-"
            unit_type = "-"
            floor = "-"
            apartment = "-"

        # Add fields to grid (RTL order)
        grid.addLayout(self._create_review_field("رقم المبنى", building_id), 0, 0)
        grid.addLayout(self._create_review_field("نوع المبنى", building_type), 0, 1)
        grid.addLayout(self._create_review_field("رقم الوحدة", unit_id), 0, 2)
        grid.addLayout(self._create_review_field("نوع الوحدة", unit_type), 0, 3)
        grid.addLayout(self._create_review_field("الطابق", floor), 1, 0)
        grid.addLayout(self._create_review_field("رقم الشقة", apartment), 1, 1)

    def _populate_household_review_card(self):
        """Populate the household review card (Step 3 data) - exact copy from old wizard."""
        content_widget = self.review_household_card.findChild(QWidget, "content_step3")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        num_households = str(len(self.context.households))
        total_persons = str(sum(h.get('size', 0) for h in self.context.households))
        total_adults = str(sum(h.get('adults', 0) for h in self.context.households))
        total_minors = str(sum(h.get('minors', 0) for h in self.context.households))

        # First household head name
        head_name = self.context.households[0].get('head_name', '-') if self.context.households else "-"

        grid.addLayout(self._create_review_field("عدد الأسر", num_households), 0, 0)
        grid.addLayout(self._create_review_field("إجمالي الأفراد", total_persons), 0, 1)
        grid.addLayout(self._create_review_field("البالغين", total_adults), 0, 2)
        grid.addLayout(self._create_review_field("القاصرين", total_minors), 0, 3)
        grid.addLayout(self._create_review_field("رب الأسرة", head_name), 1, 0)

    def _populate_persons_review_card(self):
        """Populate the persons review card (Step 4 data) - exact copy from old wizard."""
        content_widget = self.review_persons_card.findChild(QWidget, "content_step4")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        num_persons = str(len(self.context.persons))
        contact_person = next((f"{p['first_name']} {p['last_name']}" for p in self.context.persons if p.get('is_contact_person')), "-")

        # List first 3 persons
        person_names = []
        for i, p in enumerate(self.context.persons[:3]):
            person_names.append(f"{p['first_name']} {p['last_name']}")

        grid.addLayout(self._create_review_field("عدد الأشخاص", num_persons), 0, 0)
        grid.addLayout(self._create_review_field("شخص التواصل", contact_person), 0, 1)

        # Show persons in remaining columns
        for i, name in enumerate(person_names):
            grid.addLayout(self._create_review_field(f"الشخص {i+1}", name), 0 if i < 2 else 1, 2 + (i % 2))

    def _populate_relations_review_card(self):
        """Populate the relations review card (Step 5 data) - exact copy from old wizard."""
        content_widget = self.review_relations_card.findChild(QWidget, "content_step5")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        num_relations = str(len(self.context.relations))
        total_evidences = str(sum(len(r.get('evidences', [])) for r in self.context.relations))

        rel_type_map = {"owner": "مالك", "co_owner": "شريك", "tenant": "مستأجر", "occupant": "شاغل", "heir": "وارث"}

        # Count by relation type
        owners = len([r for r in self.context.relations if r['relation_type'] in ('owner', 'co_owner')])
        tenants = len([r for r in self.context.relations if r['relation_type'] == 'tenant'])

        grid.addLayout(self._create_review_field("عدد العلاقات", num_relations), 0, 0)
        grid.addLayout(self._create_review_field("إجمالي الوثائق", total_evidences), 0, 1)
        grid.addLayout(self._create_review_field("الملاك/الشركاء", str(owners)), 0, 2)
        grid.addLayout(self._create_review_field("المستأجرين", str(tenants)), 0, 3)

        # Show first relation details
        if self.context.relations:
            r = self.context.relations[0]
            type_ar = rel_type_map.get(r['relation_type'], r['relation_type'])
            grid.addLayout(self._create_review_field("الشخص", r.get('person_name', '-')), 1, 0)
            grid.addLayout(self._create_review_field("نوع العلاقة", type_ar), 1, 1)

    def _populate_claim_review_card(self):
        """Populate the claim review card (Step 6 data) - exact copy from old wizard."""
        content_widget = self.review_claim_card.findChild(QWidget, "content_step6")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        claim_types = {"ownership": "ملكية", "occupancy": "إشغال", "tenancy": "إيجار", "": "-", None: "-"}
        priorities = {"low": "منخفض", "normal": "عادي", "high": "عالي", "urgent": "عاجل", "": "-", None: "-"}
        business_types = {"residential": "سكني", "commercial": "تجاري", "agricultural": "زراعي", "": "-", None: "-"}
        sources = {"field_survey": "مسح ميداني", "direct_request": "طلب مباشر", "referral": "إحالة", "OFFICE_SUBMISSION": "تقديم مكتبي", "": "-", None: "-"}
        statuses = {"new": "جديد", "under_review": "قيد المراجعة", "completed": "مكتمل", "pending": "معلق", "": "-", None: "-"}

        if self.context.claim_data:
            claim_type = claim_types.get(self.context.claim_data.get('claim_type'), '-')
            priority = priorities.get(self.context.claim_data.get('priority'), '-')
            business = business_types.get(self.context.claim_data.get('business_nature'), '-')
            source = sources.get(self.context.claim_data.get('source'), '-')
            status = statuses.get(self.context.claim_data.get('case_status'), '-')
            survey_date = self.context.claim_data.get('survey_date', '-') or '-'
            next_date = self.context.claim_data.get('next_action_date', '-') or '-'
            num_claimants = str(len(self.context.claim_data.get('claimant_person_ids', [])))
        else:
            claim_type = "-"
            priority = "-"
            business = "-"
            source = "-"
            status = "-"
            survey_date = "-"
            next_date = "-"
            num_claimants = "0"

        # Row 1
        grid.addLayout(self._create_review_field("نوع الحالة", claim_type), 0, 0)
        grid.addLayout(self._create_review_field("طبيعة الأعمال", business), 0, 1)
        grid.addLayout(self._create_review_field("الأولوية", priority), 0, 2)
        grid.addLayout(self._create_review_field("المصدر", source), 0, 3)

        # Row 2
        grid.addLayout(self._create_review_field("حالة الحالة", status), 1, 0)
        grid.addLayout(self._create_review_field("تاريخ المسح", survey_date), 1, 1)
        grid.addLayout(self._create_review_field("تاريخ الإجراء التالي", next_date), 1, 2)
        grid.addLayout(self._create_review_field("عدد المطالبين", num_claimants), 1, 3)

    def validate(self) -> StepValidationResult:
        result = self.create_validation_result()

        # Ensure all required data is present
        if not self.context.building:
            result.add_error("لا يوجد مبنى مختار")
        if not self.context.unit:
            result.add_error("لا يوجد وحدة مختارة")
        if len(self.context.persons) == 0:
            result.add_error("لا يوجد أشخاص مسجلين")

        return result

    def collect_data(self) -> Dict[str, Any]:
        return self.context.get_summary()

    def on_show(self):
        """Refresh summary when shown - exact copy from old wizard."""
        super().on_show()
        self._populate_review()

    def get_step_title(self) -> str:
        return "المراجعة النهائية"

    def get_step_description(self) -> str:
        return "راجع جميع البيانات المدخلة قبل الإرسال"
