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
from ui.components.toast import Toast

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
        self._editing_household_index = None

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        widget = self
        layout = self.main_layout
        # No horizontal padding - wizard applies 131px (DRY principle)
        # Only vertical spacing between elements
        layout.setContentsMargins(0, 16, 0, 16)  # Top: 16px, Bottom: 16px
        layout.setSpacing(8)

        # Building info card with all content in one bordered container
        self.household_building_frame = QFrame()
        self.household_building_frame.setObjectName("householdBuildingInfoCard")
        self.household_building_frame.setStyleSheet("""
            QFrame#householdBuildingInfoCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)

        # Card layout with compact spacing
        self.household_building_layout = QVBoxLayout(self.household_building_frame)
        self.household_building_layout.setSpacing(12)
        self.household_building_layout.setContentsMargins(16, 16, 16, 16)

        # Building address row with icon (centered, no separate border)
        address_container = QWidget()
        address_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)

        address_row = QHBoxLayout(address_container)
        address_row.setSpacing(6)
        address_row.setContentsMargins(6, 6, 6, 6)

        # Add stretch to center the content
        address_row.addStretch()

        # Building icon
        building_icon = QLabel("🏢")
        building_icon.setStyleSheet("""
            QLabel {
                font-size: 16px;
                border: none;
                background-color: transparent;
            }
        """)
        building_icon.setAlignment(Qt.AlignCenter)
        address_row.addWidget(building_icon)

        # Building address label
        self.household_building_address = QLabel("حلب الحميدية")
        self.household_building_address.setAlignment(Qt.AlignCenter)
        self.household_building_address.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
                font-size: 12px;
                color: #6B7280;
                font-weight: 500;
            }
        """)
        address_row.addWidget(self.household_building_address)

        # Add stretch to center the content
        address_row.addStretch()

        self.household_building_layout.addWidget(address_container)

        # Metrics row container (no separate border, transparent background)
        metrics_container = QWidget()
        metrics_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        self.household_building_metrics_layout = QHBoxLayout(metrics_container)
        self.household_building_metrics_layout.setSpacing(16)
        self.household_building_metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.household_building_layout.addWidget(metrics_container)

        # Unit info layout (no separate border, transparent background)
        unit_info_container = QWidget()
        unit_info_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        self.household_unit_layout = QVBoxLayout(unit_info_container)
        self.household_unit_layout.setSpacing(6)
        self.household_unit_layout.setContentsMargins(0, 0, 0, 0)
        self.household_building_layout.addWidget(unit_info_container)

        layout.addWidget(self.household_building_frame)

        # Create scroll area for family information sections
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #F3F4F6;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #9CA3AF;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6B7280;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

        # Container widget for scroll area content
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        # معلومات الاسرة (Family Information) Section
        family_info_frame = QFrame()
        family_info_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        family_info_layout = QVBoxLayout(family_info_frame)
        family_info_layout.setSpacing(12)

        # Header
        family_info_header = QLabel("📋 معلومات الاسرة")
        family_info_header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        family_info_layout.addWidget(family_info_header)

        # Grid layout for family info fields (2 columns, RTL: right=0, left=1)
        family_info_grid = QGridLayout()
        family_info_grid.setSpacing(12)
        family_info_grid.setColumnStretch(0, 1)
        family_info_grid.setColumnStretch(1, 1)

        # Right side (RTL): عدد الأفراد should appear on right (column 1)
        total_members_label = QLabel("عدد الأفراد")
        total_members_label.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 4px; border: none; background-color: transparent;")
        family_info_grid.addWidget(total_members_label, 0, 1)

        self.hh_total_members = QSpinBox()
        self.hh_total_members.setRange(0, 50)
        self.hh_total_members.setValue(0)
        self.hh_total_members.setStyleSheet("""
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        family_info_grid.addWidget(self.hh_total_members, 1, 1)

        # Left side (RTL): رب الأسرة/العائل should appear on left (column 0)
        head_name_label = QLabel("رب الأسرة/العائل")
        head_name_label.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 4px; border: none; background-color: transparent;")
        family_info_grid.addWidget(head_name_label, 0, 0)

        self.hh_head_name = QLineEdit()
        self.hh_head_name.setPlaceholderText("اسم رب الأسرة")
        self.hh_head_name.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        family_info_grid.addWidget(self.hh_head_name, 1, 0)

        family_info_layout.addLayout(family_info_grid)
        scroll_layout.addWidget(family_info_frame)

        # تكوين الأسرة (Family Composition) Section
        composition_frame = QFrame()
        composition_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        composition_layout = QVBoxLayout(composition_frame)
        composition_layout.setSpacing(12)

        # Header
        composition_header = QLabel("👥 تكوين الأسرة")
        composition_header.setStyleSheet("""
            font-size: 13px;
            font-weight: 200;
            color: #1F2937;
            padding: 4px 0px;
        """)
        composition_layout.addWidget(composition_header)

        # Grid layout for composition fields (2 columns x multiple rows)
        composition_grid = QGridLayout()
        composition_grid.setSpacing(12)
        composition_grid.setColumnStretch(0, 1)
        composition_grid.setColumnStretch(1, 1)

        label_style = "font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 4px; border: none; background-color: transparent;"
        spinbox_style = """
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """

        # Row 0-1: عدد البالغين الإناث (RIGHT side for RTL, column 1)
        adult_females_label = QLabel("عدد البالغين الإناث")
        adult_females_label.setStyleSheet(label_style)
        composition_grid.addWidget(adult_females_label, 0, 1)

        self.hh_adult_females = QSpinBox()
        self.hh_adult_females.setRange(0, 50)
        self.hh_adult_females.setValue(0)
        self.hh_adult_females.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_adult_females, 1, 1)

        # Row 0-1: عدد البالغين الذكور (LEFT side for RTL, column 0)
        adult_males_label = QLabel("عدد البالغين الذكور")
        adult_males_label.setStyleSheet(label_style)
        composition_grid.addWidget(adult_males_label, 0, 0)

        self.hh_adult_males = QSpinBox()
        self.hh_adult_males.setRange(0, 50)
        self.hh_adult_males.setValue(0)
        self.hh_adult_males.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_adult_males, 1, 0)

        # Row 2-3: عدد الأطفال الإناث (أقل من 18) (RIGHT side for RTL, column 1)
        female_children_label = QLabel("عدد الأطفال الإناث (أقل من 18)")
        female_children_label.setStyleSheet(label_style)
        composition_grid.addWidget(female_children_label, 2, 1)

        self.hh_female_children_under18 = QSpinBox()
        self.hh_female_children_under18.setRange(0, 50)
        self.hh_female_children_under18.setValue(0)
        self.hh_female_children_under18.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_female_children_under18, 3, 1)

        # Row 2-3: عدد الأطفال الذكور (أقل من 18) (LEFT side for RTL, column 0)
        male_children_label = QLabel("عدد الأطفال الذكور (أقل من 18)")
        male_children_label.setStyleSheet(label_style)
        composition_grid.addWidget(male_children_label, 2, 0)

        self.hh_male_children_under18 = QSpinBox()
        self.hh_male_children_under18.setRange(0, 50)
        self.hh_male_children_under18.setValue(0)
        self.hh_male_children_under18.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_male_children_under18, 3, 0)

        # Row 4-5: عدد كبار السن الإناث (أكبر من 65) (RIGHT side for RTL, column 1)
        female_elderly_label = QLabel("عدد كبار السن الإناث (أكبر من 65)")
        female_elderly_label.setStyleSheet(label_style)
        composition_grid.addWidget(female_elderly_label, 4, 1)

        self.hh_female_elderly_over65 = QSpinBox()
        self.hh_female_elderly_over65.setRange(0, 50)
        self.hh_female_elderly_over65.setValue(0)
        self.hh_female_elderly_over65.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_female_elderly_over65, 5, 1)

        # Row 4-5: عدد كبار السن الذكور (أكبر من 65) (LEFT side for RTL, column 0)
        male_elderly_label = QLabel("عدد كبار السن الذكور (أكبر من 65)")
        male_elderly_label.setStyleSheet(label_style)
        composition_grid.addWidget(male_elderly_label, 4, 0)

        self.hh_male_elderly_over65 = QSpinBox()
        self.hh_male_elderly_over65.setRange(0, 50)
        self.hh_male_elderly_over65.setValue(0)
        self.hh_male_elderly_over65.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_male_elderly_over65, 5, 0)

        # Row 6-7: عدد المعاقين الإناث (RIGHT side for RTL, column 1)
        disabled_females_label = QLabel("عدد المعاقين الإناث")
        disabled_females_label.setStyleSheet(label_style)
        composition_grid.addWidget(disabled_females_label, 6, 1)

        self.hh_disabled_females = QSpinBox()
        self.hh_disabled_females.setRange(0, 50)
        self.hh_disabled_females.setValue(0)
        self.hh_disabled_females.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_disabled_females, 7, 1)

        # Row 6-7: عدد المعاقين الذكور (LEFT side for RTL, column 0)
        disabled_males_label = QLabel("عدد المعاقين الذكور")
        disabled_males_label.setStyleSheet(label_style)
        composition_grid.addWidget(disabled_males_label, 6, 0)

        self.hh_disabled_males = QSpinBox()
        self.hh_disabled_males.setRange(0, 50)
        self.hh_disabled_males.setValue(0)
        self.hh_disabled_males.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_disabled_males, 7, 0)

        composition_layout.addLayout(composition_grid)
        scroll_layout.addWidget(composition_frame)

        # ادخل ملاحظاتك (Notes) Section
        notes_frame = QFrame()
        notes_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        notes_layout = QVBoxLayout(notes_frame)
        notes_layout.setSpacing(12)

        # Header
        notes_header = QLabel("📝 ادخل ملاحظاتك")
        notes_header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        notes_layout.addWidget(notes_header)

        # Notes text area
        self.hh_notes = QTextEdit()
        self.hh_notes.setPlaceholderText("أدخل ملاحظاتك هنا...")
        self.hh_notes.setMaximumHeight(100)
        self.hh_notes.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        notes_layout.addWidget(self.hh_notes)

        scroll_layout.addWidget(notes_frame)

        # Add save button at the bottom of scroll content
        save_btn_container = QWidget()
        save_btn_layout = QHBoxLayout(save_btn_container)
        save_btn_layout.setContentsMargins(0, 12, 0, 0)

        add_hh_btn = QPushButton("+ إضافة أسرة")
        add_hh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        add_hh_btn.clicked.connect(self._save_household)
        save_btn_layout.addStretch()
        save_btn_layout.addWidget(add_hh_btn)
        save_btn_layout.addStretch()

        scroll_layout.addWidget(save_btn_container)

        # Set scroll content and add to main layout
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def _save_household(self):
        """Save current household data - exact copy from old wizard."""
        if not self.hh_head_name.text().strip():
            QMessageBox.warning(self, "خطأ", "يجب إدخال اسم رب الأسرة")
            return

        household = {
            "household_id": str(uuid.uuid4()) if not hasattr(self, '_editing_household_index') or self._editing_household_index is None else self.context.households[self._editing_household_index]['household_id'],
            "head_name": self.hh_head_name.text().strip(),
            "size": self.hh_total_members.value(),
            "adult_males": self.hh_adult_males.value(),
            "adult_females": self.hh_adult_females.value(),
            "male_children_under18": self.hh_male_children_under18.value(),
            "female_children_under18": self.hh_female_children_under18.value(),
            "male_elderly_over65": self.hh_male_elderly_over65.value(),
            "female_elderly_over65": self.hh_female_elderly_over65.value(),
            "disabled_males": self.hh_disabled_males.value(),
            "disabled_females": self.hh_disabled_females.value(),
            "notes": self.hh_notes.toPlainText().strip()
        }

        if hasattr(self, '_editing_household_index') and self._editing_household_index is not None:
            self.context.households[self._editing_household_index] = household
            Toast.show_toast(self, "تم تحديث بيانات الأسرة", Toast.SUCCESS)
        else:
            self.context.households.append(household)
            Toast.show_toast(self, "تم إضافة الأسرة", Toast.SUCCESS)

        self._clear_household_form()

    def _clear_household_form(self):
        """Clear household form fields - exact copy from old wizard."""
        self._editing_household_index = None
        self.hh_head_name.clear()
        self.hh_total_members.setValue(0)
        self.hh_adult_males.setValue(0)
        self.hh_adult_females.setValue(0)
        self.hh_male_children_under18.setValue(0)
        self.hh_female_children_under18.setValue(0)
        self.hh_male_elderly_over65.setValue(0)
        self.hh_female_elderly_over65.setValue(0)
        self.hh_disabled_males.setValue(0)
        self.hh_disabled_females.setValue(0)
        self.hh_notes.clear()

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        # Check if at least one household exists
        if len(self.context.households) == 0:
            result.add_error("يجب تسجيل أسرة واحدة على الأقل")

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "households": self.context.households,
            "households_count": len(self.context.households)
        }

    def populate_data(self):
        """Populate the step with data from context."""
        pass

    def get_step_title(self) -> str:
        """Get step title."""
        return "معلومات الأسرة"

    def get_step_description(self) -> str:
        """Get step description."""
        return "سجل المعلومات الديموغرافية للأسرة القاطنة في الوحدة"
