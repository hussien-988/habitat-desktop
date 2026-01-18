# -*- coding: utf-8 -*-
"""
Relation Step - Step 5 of Office Survey Wizard.

Simplified step for managing relations and evidence.
Note: This is a simplified implementation.
"""

from typing import Dict, Any

from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext


class RelationStep(BaseStep):
    """Step 5: Relations & Evidence (Simplified)."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        header = QLabel("الخطوة 5: العلاقات والأدلة")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        desc = QLabel("تم حفظ معلومات الأشخاص والعلاقات.\nيمكنك المتابعة للخطوة التالية.")
        desc.setStyleSheet("color: #7f8c8d; margin: 20px;")
        self.main_layout.addWidget(desc)
        self.main_layout.addStretch()

    def validate(self) -> StepValidationResult:
        return self.create_validation_result()

    def collect_data(self) -> Dict[str, Any]:
        return {"relations": self.context.relations}

    def get_step_title(self) -> str:
        return "العلاقات والأدلة"
