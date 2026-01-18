# -*- coding: utf-8 -*-
"""
Claim Step - Step 6 of Office Survey Wizard.

Simplified step for creating claims.
Note: This is a simplified implementation.
"""

from typing import Dict, Any
import uuid

from PyQt5.QtWidgets import QVBoxLayout, QLabel, QComboBox, QTextEdit, QGroupBox, QFormLayout

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext


class ClaimStep(BaseStep):
    """Step 6: Claim Creation (Simplified)."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        header = QLabel("الخطوة 6: إنشاء المطالبة")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        group = QGroupBox("معلومات المطالبة")
        form = QFormLayout(group)

        self.tenure_type_combo = QComboBox()
        self.tenure_type_combo.addItems(["ملكية", "حيازة", "إيجار", "أخرى"])
        form.addRow("نوع الحيازة:", self.tenure_type_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        form.addRow("ملاحظات:", self.notes_edit)

        self.main_layout.addWidget(group)
        self.main_layout.addStretch()

    def validate(self) -> StepValidationResult:
        result = self.create_validation_result()
        if not self.tenure_type_combo.currentText():
            result.add_error("يجب اختيار نوع الحيازة")
        return result

    def collect_data(self) -> Dict[str, Any]:
        claim_data = {
            'claim_id': str(uuid.uuid4()),
            'tenure_type': self.tenure_type_combo.currentText(),
            'notes': self.notes_edit.toPlainText().strip()
        }
        self.context.set_claim_data(claim_data)
        return claim_data

    def get_step_title(self) -> str:
        return "إنشاء المطالبة"
