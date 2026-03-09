# -*- coding: utf-8 -*-
"""
Applicant Info Step - Step 1 of Office Survey Wizard.

Collects visitor/applicant information:
- Full name (required) -> intervieweeName
- National ID -> first person in OccupancyClaimsStep
- Phone number -> contactPhone
- Email (optional) -> contactEmail
- In-person visit checkbox -> inPersonVisit
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QCheckBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)


class ApplicantInfoStep(BaseStep):
    """
    Step 1: Applicant (Visitor) Information.

    Maps to CreateOfficeSurveyCommand fields:
    - intervieweeName: full_name
    - contactPhone: phone
    - contactEmail: email
    - inPersonVisit: in_person
    """

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        layout = self.main_layout
        layout.setContentsMargins(0, 8, 0, 16)
        layout.setSpacing(0)

        # Card
        card = QFrame()
        card.setObjectName("applicantCard")
        card.setStyleSheet("""
            QFrame#applicantCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #EFF6FF;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
                font-size: 18px;
            }
        """)
        icon_label.setText("👤")
        header_row.addWidget(icon_label)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title_label = QLabel(tr("wizard.step.applicant_info"))
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        header_text.addWidget(title_label)

        subtitle_label = QLabel(tr("wizard.applicant.subtitle"))
        subtitle_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        header_text.addWidget(subtitle_label)

        header_row.addLayout(header_text)
        header_row.addStretch()
        card_layout.addLayout(header_row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #E1E8ED; border: none; background-color: #E1E8ED;")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        # Field style
        input_style = """
            QLineEdit {
                background-color: #F8FAFF;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                padding: 8px 12px;
                color: #374151;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #3890DF;
            }
        """
        label_font = create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD)

        # Row 1: Full name + National ID
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        full_name_col = QVBoxLayout()
        full_name_col.setSpacing(6)
        lbl_name = QLabel(tr("wizard.applicant.full_name") + " *")
        lbl_name.setFont(label_font)
        lbl_name.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.full_name_edit = QLineEdit()
        self.full_name_edit.setPlaceholderText(tr("wizard.applicant.full_name"))
        self.full_name_edit.setStyleSheet(input_style)
        self.full_name_edit.setFixedHeight(42)
        self.full_name_edit.setLayoutDirection(Qt.RightToLeft)
        full_name_col.addWidget(lbl_name)
        full_name_col.addWidget(self.full_name_edit)
        row1.addLayout(full_name_col, 2)

        nat_id_col = QVBoxLayout()
        nat_id_col.setSpacing(6)
        lbl_nat = QLabel(tr("wizard.applicant.national_id"))
        lbl_nat.setFont(label_font)
        lbl_nat.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.national_id_edit = QLineEdit()
        self.national_id_edit.setPlaceholderText(tr("wizard.applicant.national_id"))
        self.national_id_edit.setStyleSheet(input_style)
        self.national_id_edit.setFixedHeight(42)
        self.national_id_edit.setLayoutDirection(Qt.RightToLeft)
        nat_id_col.addWidget(lbl_nat)
        nat_id_col.addWidget(self.national_id_edit)
        row1.addLayout(nat_id_col, 1)

        card_layout.addLayout(row1)

        # Row 2: Phone + Email
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        phone_col = QVBoxLayout()
        phone_col.setSpacing(6)
        lbl_phone = QLabel(tr("wizard.applicant.phone"))
        lbl_phone.setFont(label_font)
        lbl_phone.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText(tr("wizard.applicant.phone"))
        self.phone_edit.setStyleSheet(input_style)
        self.phone_edit.setFixedHeight(42)
        phone_col.addWidget(lbl_phone)
        phone_col.addWidget(self.phone_edit)
        row2.addLayout(phone_col, 1)

        email_col = QVBoxLayout()
        email_col.setSpacing(6)
        lbl_email = QLabel(tr("wizard.applicant.email"))
        lbl_email.setFont(label_font)
        lbl_email.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText(tr("wizard.applicant.email"))
        self.email_edit.setStyleSheet(input_style)
        self.email_edit.setFixedHeight(42)
        email_col.addWidget(lbl_email)
        email_col.addWidget(self.email_edit)
        row2.addLayout(email_col, 1)

        card_layout.addLayout(row2)

        # Row 3: In-person checkbox
        self.in_person_check = QCheckBox(tr("wizard.applicant.in_person"))
        self.in_person_check.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.in_person_check.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.in_person_check.setChecked(True)
        card_layout.addWidget(self.in_person_check)

        layout.addWidget(card)
        layout.addStretch()

    def validate(self) -> StepValidationResult:
        result = StepValidationResult(is_valid=True, errors=[])
        name = self.full_name_edit.text().strip()
        if not name:
            result.add_error("الاسم الكامل مطلوب")
        return result

    def collect_data(self) -> dict:
        data = {
            "full_name": self.full_name_edit.text().strip(),
            "national_id": self.national_id_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "in_person": self.in_person_check.isChecked(),
        }
        self.context.applicant = data
        return data

    def populate_data(self):
        if self.context.applicant:
            a = self.context.applicant
            self.full_name_edit.setText(a.get("full_name", ""))
            self.national_id_edit.setText(a.get("national_id", ""))
            self.phone_edit.setText(a.get("phone", ""))
            self.email_edit.setText(a.get("email", ""))
            self.in_person_check.setChecked(a.get("in_person", True))

    def get_name(self) -> str:
        return tr("wizard.step.applicant_info")
