# -*- coding: utf-8 -*-
"""
Household Step - Step 3 of Office Survey Wizard.

Allows user to:
- Enter household information
- Record family composition (adults, children, elderly, disabled)
- Add notes about the household
"""

from typing import Dict, Any
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QWidget, QMessageBox, QGroupBox,
    QSpinBox, QTextEdit, QGridLayout
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class HouseholdStep(BaseStep):
    """
    Step 3: Household Information.

    Collects household demographic information including:
    - Head of household
    - Total members
    - Family composition (adults, children, elderly, disabled)
    - Notes
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)

    def setup_ui(self):
        """Setup the step's UI."""
        # Header
        header = QLabel("الخطوة 3: معلومات الأسرة والإشغال")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        # Description
        desc = QLabel("سجل المعلومات الديموغرافية للأسرة القاطنة")
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 16px;")
        self.main_layout.addWidget(desc)

        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16)
        scroll_layout.setContentsMargins(0, 0, 10, 0)

        # Family Information Section
        family_info_frame = self._create_family_info_section()
        scroll_layout.addWidget(family_info_frame)

        # Family Composition Section
        composition_frame = self._create_composition_section()
        scroll_layout.addWidget(composition_frame)

        # Notes Section
        notes_frame = self._create_notes_section()
        scroll_layout.addWidget(notes_frame)

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        self.main_layout.addWidget(scroll, 1)

    def _create_family_info_section(self) -> QFrame:
        """Create family information section."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        # Header
        header = QLabel("📋 معلومات الأسرة")
        header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        layout.addWidget(header)

        # Grid for fields
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        label_style = "font-size: 12px; color: #374151; font-weight: 500;"

        # Total members (right column)
        total_members_label = QLabel("عدد أفراد الأسرة")
        total_members_label.setStyleSheet(label_style)
        grid.addWidget(total_members_label, 0, 1)

        self.total_members_spin = QSpinBox()
        self.total_members_spin.setRange(0, 50)
        self.total_members_spin.setValue(0)
        self.total_members_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.total_members_spin, 1, 1)

        # Head of household (left column)
        head_name_label = QLabel("رب الأسرة/العائل")
        head_name_label.setStyleSheet(label_style)
        grid.addWidget(head_name_label, 0, 0)

        self.head_name_input = QLineEdit()
        self.head_name_input.setPlaceholderText("اسم رب الأسرة")
        self.head_name_input.setStyleSheet(self._input_style())
        grid.addWidget(self.head_name_input, 1, 0)

        layout.addLayout(grid)

        return frame

    def _create_composition_section(self) -> QFrame:
        """Create family composition section."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        # Header
        header = QLabel("👥 تكوين الأسرة")
        header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        layout.addWidget(header)

        # Grid for composition fields
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        label_style = "font-size: 12px; color: #374151; font-weight: 500;"

        # Row 0: Adult females (right) and males (left)
        adult_females_label = QLabel("عدد البالغين الإناث")
        adult_females_label.setStyleSheet(label_style)
        grid.addWidget(adult_females_label, 0, 1)

        self.adult_females_spin = QSpinBox()
        self.adult_females_spin.setRange(0, 50)
        self.adult_females_spin.setValue(0)
        self.adult_females_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.adult_females_spin, 1, 1)

        adult_males_label = QLabel("عدد البالغين الذكور")
        adult_males_label.setStyleSheet(label_style)
        grid.addWidget(adult_males_label, 0, 0)

        self.adult_males_spin = QSpinBox()
        self.adult_males_spin.setRange(0, 50)
        self.adult_males_spin.setValue(0)
        self.adult_males_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.adult_males_spin, 1, 0)

        # Row 2: Female children (right) and male children (left)
        female_children_label = QLabel("عدد الأطفال الإناث (أقل من 18)")
        female_children_label.setStyleSheet(label_style)
        grid.addWidget(female_children_label, 2, 1)

        self.female_children_spin = QSpinBox()
        self.female_children_spin.setRange(0, 50)
        self.female_children_spin.setValue(0)
        self.female_children_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.female_children_spin, 3, 1)

        male_children_label = QLabel("عدد الأطفال الذكور (أقل من 18)")
        male_children_label.setStyleSheet(label_style)
        grid.addWidget(male_children_label, 2, 0)

        self.male_children_spin = QSpinBox()
        self.male_children_spin.setRange(0, 50)
        self.male_children_spin.setValue(0)
        self.male_children_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.male_children_spin, 3, 0)

        # Row 4: Female elderly (right) and male elderly (left)
        female_elderly_label = QLabel("عدد كبار السن الإناث (أكبر من 65)")
        female_elderly_label.setStyleSheet(label_style)
        grid.addWidget(female_elderly_label, 4, 1)

        self.female_elderly_spin = QSpinBox()
        self.female_elderly_spin.setRange(0, 50)
        self.female_elderly_spin.setValue(0)
        self.female_elderly_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.female_elderly_spin, 5, 1)

        male_elderly_label = QLabel("عدد كبار السن الذكور (أكبر من 65)")
        male_elderly_label.setStyleSheet(label_style)
        grid.addWidget(male_elderly_label, 4, 0)

        self.male_elderly_spin = QSpinBox()
        self.male_elderly_spin.setRange(0, 50)
        self.male_elderly_spin.setValue(0)
        self.male_elderly_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.male_elderly_spin, 5, 0)

        # Row 6: Disabled females (right) and males (left)
        disabled_females_label = QLabel("عدد المعاقين الإناث")
        disabled_females_label.setStyleSheet(label_style)
        grid.addWidget(disabled_females_label, 6, 1)

        self.disabled_females_spin = QSpinBox()
        self.disabled_females_spin.setRange(0, 50)
        self.disabled_females_spin.setValue(0)
        self.disabled_females_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.disabled_females_spin, 7, 1)

        disabled_males_label = QLabel("عدد المعاقين الذكور")
        disabled_males_label.setStyleSheet(label_style)
        grid.addWidget(disabled_males_label, 6, 0)

        self.disabled_males_spin = QSpinBox()
        self.disabled_males_spin.setRange(0, 50)
        self.disabled_males_spin.setValue(0)
        self.disabled_males_spin.setStyleSheet(self._spinbox_style())
        grid.addWidget(self.disabled_males_spin, 7, 0)

        layout.addLayout(grid)

        return frame

    def _create_notes_section(self) -> QFrame:
        """Create notes section."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        # Header
        header = QLabel("📝 ملاحظات")
        header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        layout.addWidget(header)

        # Notes text area
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("أدخل ملاحظاتك حول الأسرة هنا...")
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.notes_edit)

        return frame

    def _spinbox_style(self) -> str:
        """Get spinbox stylesheet."""
        return """
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
            QSpinBox:focus {
                border-color: #3498db;
            }
        """

    def _input_style(self) -> str:
        """Get input stylesheet."""
        return """
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        # Head of household name is required
        if not self.head_name_input.text().strip():
            result.add_error("يجب إدخال اسم رب الأسرة")

        # At least one family member should be entered
        total_entered = (
            self.adult_males_spin.value() +
            self.adult_females_spin.value() +
            self.male_children_spin.value() +
            self.female_children_spin.value() +
            self.male_elderly_spin.value() +
            self.female_elderly_spin.value()
        )

        if total_entered == 0:
            result.add_warning("لم يتم إدخال أي أفراد في تكوين الأسرة")

        # Warn if total members doesn't match composition
        total_members = self.total_members_spin.value()
        if total_members > 0 and total_entered > 0 and total_members != total_entered:
            result.add_warning(
                f"عدد الأفراد ({total_members}) لا يطابق مجموع التكوين ({total_entered})"
            )

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        household_data = {
            "household_id": str(uuid.uuid4()),
            "head_name": self.head_name_input.text().strip(),
            "size": self.total_members_spin.value(),
            "adult_males": self.adult_males_spin.value(),
            "adult_females": self.adult_females_spin.value(),
            "male_children_under18": self.male_children_spin.value(),
            "female_children_under18": self.female_children_spin.value(),
            "male_elderly_over65": self.male_elderly_spin.value(),
            "female_elderly_over65": self.female_elderly_spin.value(),
            "disabled_males": self.disabled_males_spin.value(),
            "disabled_females": self.disabled_females_spin.value(),
            "notes": self.notes_edit.toPlainText().strip() or None
        }

        # Save to context
        self.context.add_household(household_data)

        return household_data

    def populate_data(self):
        """Populate the step with data from context."""
        # If household data exists in context, load the first one
        if self.context.households and len(self.context.households) > 0:
            household = self.context.households[0]

            self.head_name_input.setText(household.get('head_name', ''))
            self.total_members_spin.setValue(household.get('size', 0))
            self.adult_males_spin.setValue(household.get('adult_males', 0))
            self.adult_females_spin.setValue(household.get('adult_females', 0))
            self.male_children_spin.setValue(household.get('male_children_under18', 0))
            self.female_children_spin.setValue(household.get('female_children_under18', 0))
            self.male_elderly_spin.setValue(household.get('male_elderly_over65', 0))
            self.female_elderly_spin.setValue(household.get('female_elderly_over65', 0))
            self.disabled_males_spin.setValue(household.get('disabled_males', 0))
            self.disabled_females_spin.setValue(household.get('disabled_females', 0))

            if household.get('notes'):
                self.notes_edit.setPlainText(household['notes'])

    def get_step_title(self) -> str:
        """Get step title."""
        return "معلومات الأسرة"

    def get_step_description(self) -> str:
        """Get step description."""
        return "سجل المعلومات الديموغرافية للأسرة القاطنة في الوحدة"
