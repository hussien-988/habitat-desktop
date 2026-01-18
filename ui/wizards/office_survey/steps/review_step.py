# -*- coding: utf-8 -*-
"""
Review Step - Step 7 of Office Survey Wizard.

Final review and submission step.
"""

from typing import Dict, Any

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame, QGroupBox
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext


class ReviewStep(BaseStep):
    """Step 7: Review & Submit."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        header = QLabel("الخطوة 7: المراجعة النهائية")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        desc = QLabel("راجع جميع البيانات قبل الإرسال")
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 16px;")
        self.main_layout.addWidget(desc)

        # Scroll area for summary
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Summary sections
        self._add_summary_section(scroll_layout)

        scroll.setWidget(scroll_content)
        self.main_layout.addWidget(scroll, 1)

    def _add_summary_section(self, layout):
        """Add summary sections."""
        summary = self.context.get_summary()

        # Building info
        building_group = QGroupBox("معلومات المبنى")
        building_layout = QVBoxLayout(building_group)
        building_layout.addWidget(QLabel(f"رقم المرجع: {summary.get('reference_number', '-')}"))
        building_layout.addWidget(QLabel(f"رمز المبنى: {summary.get('building', {}).get('id', '-')}"))
        layout.addWidget(building_group)

        # Unit info
        unit_group = QGroupBox("معلومات الوحدة")
        unit_layout = QVBoxLayout(unit_group)
        unit_layout.addWidget(QLabel(f"رقم الوحدة: {summary.get('unit', {}).get('id', '-')}"))
        unit_layout.addWidget(QLabel(f"نوع الوحدة: {summary.get('unit', {}).get('type', '-')}"))
        layout.addWidget(unit_group)

        # Persons count
        persons_group = QGroupBox("الأشخاص")
        persons_layout = QVBoxLayout(persons_group)
        persons_layout.addWidget(QLabel(f"عدد الأشخاص: {summary.get('persons_count', 0)}"))
        layout.addWidget(persons_group)

        # Status
        status_label = QLabel(f"الحالة: {summary.get('status', 'draft')}")
        status_label.setStyleSheet("font-weight: bold; color: #27ae60; margin-top: 16px;")
        layout.addWidget(status_label)

        layout.addStretch()

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
        """Refresh summary when shown."""
        super().on_show()
        # Refresh summary display
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if isinstance(widget, QScrollArea):
                scroll_content = widget.widget()
                scroll_layout = scroll_content.layout()
                # Clear and rebuild
                while scroll_layout.count():
                    child = scroll_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                self._add_summary_section(scroll_layout)
                break

    def get_step_title(self) -> str:
        return "المراجعة النهائية"

    def get_step_description(self) -> str:
        return "راجع جميع البيانات المدخلة قبل الإرسال"
