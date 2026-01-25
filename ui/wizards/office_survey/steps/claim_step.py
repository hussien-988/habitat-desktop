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
        """Setup the step's UI - matching person_step styling."""
        # Import StyleManager and other components
        from ui.style_manager import StyleManager
        from ui.font_utils import FontManager, create_font
        from ui.design_system import Colors
        from ui.components.icon import Icon

        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        # Set main window background color
        widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        # Match person_step margins: No horizontal padding - wizard handles it
        # Only vertical spacing for step content
        layout.setContentsMargins(0, 15, 0, 16)  # Top: 15px, Bottom: 16px
        layout.setSpacing(15)  # Unified spacing: 15px between cards

        # --- The Main Card (QFrame) - matching person_step card styling ---
        card = QFrame()
        card.setObjectName("ClaimCard")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame#ClaimCard {{
                background-color: {Colors.SURFACE};
                border-radius: 12px;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)  # Match person_step: 12px padding
        card_layout.setSpacing(12)  # Match person_step: 12px spacing

        # --- Header with Title and Icon (inside the card) ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Title text container
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)  # Match person_step spacing
        title_label = QLabel("تسجيل الحالة")
        # Title: 14px from Figma = 10pt, weight 600, color WIZARD_TITLE
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        subtitle_label = QLabel("ربط المطالبين بالوحدات العقارية وتتبع مطالبات تسجيل حقوق الحيازة")
        # Subtitle: 14px from Figma = 10pt, weight 400, color WIZARD_SUBTITLE
        subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        subtitle_label.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(subtitle_label)

        # Icon for title
        title_icon = QLabel()
        title_icon.setFixedSize(40, 40)
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        # Load elements.png icon using Icon.load_pixmap
        claim_icon_pixmap = Icon.load_pixmap("elements", size=24)
        if claim_icon_pixmap and not claim_icon_pixmap.isNull():
            title_icon.setPixmap(claim_icon_pixmap)
        else:
            # Fallback if image not found
            title_icon.setText("📋")
            title_icon.setStyleSheet(title_icon.styleSheet() + "font-size: 16px;")

        # Assemble title group (icon first in code = rightmost visually in RTL)
        header_layout.addWidget(title_icon)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)
        # Gap: 12px between header and content
        card_layout.addSpacing(12)

        # 1. Grid Layout for top fields (RTL order: right to left)
        grid = QGridLayout()
        # Reduced spacing for tighter layout
        grid.setHorizontalSpacing(8)  # Horizontal gap between columns
        grid.setVerticalSpacing(8)    # Vertical gap between rows

        # Ensure columns stretch to fill full width
        for i in range(4):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, field_widget, row, col):
            v = QVBoxLayout()
            v.setSpacing(4)  # Small gap between label and input
            lbl = QLabel(label_text)
            # Match label styling from person_step
            lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
            v.addWidget(lbl)
            v.addWidget(field_widget)
            grid.addLayout(v, row, col)

        # Row 1 (RTL): معرف المطالب | معرف الوحدة المطالب بها | نوع الحالة | طبيعة الأعمال
        self.claim_person_search = QLineEdit()
        self.claim_person_search.setPlaceholderText("اسم الشخص")
        self.claim_person_search.setStyleSheet(StyleManager.form_input())
        add_field("معرف المطالب", self.claim_person_search, 0, 0)

        self.claim_unit_search = QLineEdit()
        self.claim_unit_search.setPlaceholderText("رقم الوحدة")
        self.claim_unit_search.setStyleSheet(StyleManager.form_input())
        add_field("معرف الوحدة المطالب بها", self.claim_unit_search, 0, 1)

        self.claim_type_combo = QComboBox()
        self.claim_type_combo.addItem("اختر", "")
        self.claim_type_combo.addItem("ملكية", "ownership")
        self.claim_type_combo.addItem("إشغال", "occupancy")
        self.claim_type_combo.addItem("إيجار", "tenancy")
        self.claim_type_combo.setStyleSheet(StyleManager.form_input())
        add_field("نوع الحالة", self.claim_type_combo, 0, 2)

        self.claim_business_nature = QComboBox()
        self.claim_business_nature.addItem("اختر", "")
        self.claim_business_nature.addItem("سكني", "residential")
        self.claim_business_nature.addItem("تجاري", "commercial")
        self.claim_business_nature.addItem("زراعي", "agricultural")
        self.claim_business_nature.setStyleSheet(StyleManager.form_input())
        add_field("طبيعة الأعمال", self.claim_business_nature, 0, 3)

        # Row 2 (RTL): حالة الحالة | المصدر | تاريخ المسح | الأولوية
        self.claim_status_combo = QComboBox()
        self.claim_status_combo.addItem("اختر", "")
        self.claim_status_combo.addItem("جديد", "new")
        self.claim_status_combo.addItem("قيد المراجعة", "under_review")
        self.claim_status_combo.addItem("مكتمل", "completed")
        self.claim_status_combo.addItem("معلق", "pending")
        self.claim_status_combo.setStyleSheet(StyleManager.form_input())
        add_field("حالة الحالة", self.claim_status_combo, 1, 0)

        self.claim_source_combo = QComboBox()
        self.claim_source_combo.addItem("اختر", "")
        self.claim_source_combo.addItem("مسح ميداني", "field_survey")
        self.claim_source_combo.addItem("طلب مباشر", "direct_request")
        self.claim_source_combo.addItem("إحالة", "referral")
        self.claim_source_combo.setStyleSheet(StyleManager.form_input())
        add_field("المصدر", self.claim_source_combo, 1, 1)

        self.claim_survey_date = QDateEdit()
        self.claim_survey_date.setCalendarPopup(True)
        self.claim_survey_date.setDisplayFormat("yyyy-MM-dd")
        self.claim_survey_date.setDate(QDate.currentDate())
        self.claim_survey_date.setStyleSheet(StyleManager.date_input())
        add_field("تاريخ المسح", self.claim_survey_date, 1, 2)

        self.claim_priority_combo = QComboBox()
        self.claim_priority_combo.addItem("اختر", "")
        self.claim_priority_combo.addItem("منخفض", "low")
        self.claim_priority_combo.addItem("عادي", "normal")
        self.claim_priority_combo.addItem("عالي", "high")
        self.claim_priority_combo.addItem("عاجل", "urgent")
        self.claim_priority_combo.setCurrentIndex(2)  # Default to normal
        self.claim_priority_combo.setStyleSheet(StyleManager.form_input())
        add_field("الأولوية", self.claim_priority_combo, 1, 3)

        card_layout.addLayout(grid)
        card_layout.addSpacing(8)  # Gap between grid and notes section

        # 2. Notes Section
        notes_label = QLabel("ملاحظات المراجعة")
        notes_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        notes_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        card_layout.addWidget(notes_label)
        self.claim_notes = QTextEdit()
        self.claim_notes.setPlaceholderText("ملاحظات إضافية")
        self.claim_notes.setMinimumHeight(100)
        self.claim_notes.setMaximumHeight(120)
        self.claim_notes.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border: 1px solid {Colors.PRIMARY_BLUE};
            }}
        """)
        card_layout.addWidget(self.claim_notes)
        card_layout.addSpacing(8)  # Gap between sections

        # 3. Next Action Date Section
        next_date_label = QLabel("تاريخ الإجراء التالي")
        next_date_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        next_date_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        card_layout.addWidget(next_date_label)
        self.claim_next_action_date = QDateEdit()
        self.claim_next_action_date.setCalendarPopup(True)
        self.claim_next_action_date.setDisplayFormat("yyyy-MM-dd")
        self.claim_next_action_date.setStyleSheet(StyleManager.date_input())
        card_layout.addWidget(self.claim_next_action_date)
        card_layout.addSpacing(8)  # Gap between sections

        # 4. Status Bar (Inside Card) - Evidence available indicator
        self.claim_eval_label = QLabel("الأدلة متوفرة")
        self.claim_eval_label.setAlignment(Qt.AlignCenter)
        self.claim_eval_label.setFixedHeight(50)
        self.claim_eval_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self.claim_eval_label.setStyleSheet("""
            QLabel {
                background-color: #e1f7ef;
                color: #10b981;
                border-radius: 8px;
            }
        """)
        card_layout.addWidget(self.claim_eval_label)

        layout.addWidget(card)
        layout.addStretch()

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
                QLabel {
                    background-color: #e1f7ef;
                    color: #10b981;
                    border-radius: 8px;
                }
            """)
        else:
            self.claim_eval_label.setText("لا توجد أدلة مرفقة")
            self.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #fef3c7;
                    color: #f59e0b;
                    border-radius: 8px;
                }
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
