# -*- coding: utf-8 -*-
"""
Office Survey Wizard (Refactored) - UC-004.

Multi-step wizard for conducting office-based property surveys.

This is the refactored version using the unified Wizard Framework.
The old implementation (office_survey_wizard.py) is kept for reference.

Steps:
1. Building Selection - Search and select building
2. Unit Selection/Creation - Select existing or create new unit
3. Household Information - Record household demographics
4. Person Registration - Add/edit persons
5. Relations & Evidence - Link persons to unit with evidence
6. Claim Creation - Create tenure claim
7. Review & Submit - Review and submit survey
"""

from typing import List

from PyQt5.QtWidgets import QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt5.QtCore import pyqtSignal, Qt

from ui.wizards.framework import BaseWizard, BaseStep
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.steps import (
    BuildingSelectionStep,
    UnitSelectionStep,
    HouseholdStep,
    PersonStep,
    RelationStep,
    ClaimStep,
    ReviewStep
)

from repositories.survey_repository import SurveyRepository
from repositories.database import Database
from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class OfficeSurveyWizard(BaseWizard):
    """
    Office Survey Wizard (Refactored).

    This wizard guides office clerks through the property survey process:
    - Building selection
    - Unit identification
    - Household registration
    - Person and relation recording
    - Evidence collection
    - Claim creation
    """

    # Step names matching the old wizard - exact copy
    STEP_NAMES = [
        ("1", "اختيار المبنى"),
        ("2", "الوحدة العقارية"),
        ("3", "الأسرة والإشغال"),
        ("4", "تسجيل الأشخاص"),
        ("5", "العلاقات والأدلة"),
        ("6", "إنشاء المطالبة"),
        ("7", "المراجعة النهائية"),
    ]

    # Signals (aliases for BaseWizard signals for backward compatibility)
    survey_completed = pyqtSignal(dict)
    survey_cancelled = pyqtSignal()
    survey_saved_draft = pyqtSignal(str)

    def __init__(self, db: Database = None, parent=None):
        """Initialize the wizard."""
        self.db = db or Database()
        self.survey_repo = SurveyRepository(self.db)
        self.step_labels = []  # For step indicators
        super().__init__(parent)

        # Connect base wizard signals to survey-specific signals
        self.wizard_completed.connect(self.survey_completed.emit)
        self.wizard_cancelled.connect(self.survey_cancelled.emit)
        self.draft_saved.connect(self.survey_saved_draft.emit)

    def create_context(self) -> SurveyContext:
        """Create and return wizard context."""
        return SurveyContext(db=self.db)

    def create_steps(self) -> List[BaseStep]:
        """Create and return list of wizard steps."""
        steps = [
            BuildingSelectionStep(self.context, self),
            UnitSelectionStep(self.context, self),
            HouseholdStep(self.context, self),
            PersonStep(self.context, self),
            RelationStep(self.context, self),
            ClaimStep(self.context, self),
            ReviewStep(self.context, self)
        ]
        return steps

    def get_wizard_title(self) -> str:
        """Get wizard title."""
        return "معالج المسح المكتبي - Office Survey"

    def get_submit_button_text(self) -> str:
        """Get submit button text."""
        return "إنهاء المسح"

    def on_submit(self) -> bool:
        """
        Handle wizard submission.

        Saves the survey data to the database.

        Returns:
            True if submission was successful
        """
        try:
            # Get all collected data
            survey_data = self.context.to_dict()

            # Save to database
            survey_id = self.survey_repo.create_survey(survey_data)

            # Update context status
            self.context.status = "completed"

            logger.info(f"Survey completed successfully: {survey_id}")

            QMessageBox.information(
                self,
                "نجح",
                f"تم حفظ المسح بنجاح\n"
                f"رقم المرجع: {self.context.reference_number}\n"
                f"معرف المسح: {survey_id}"
            )

            return True

        except Exception as e:
            logger.error(f"Error submitting survey: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء حفظ المسح:\n{str(e)}"
            )
            return False

    def on_cancel(self) -> bool:
        """Handle wizard cancellation."""
        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "تأكيد الإلغاء",
            "هل أنت متأكد من إلغاء المسح؟\n"
            "سيتم فقد جميع البيانات المدخلة.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.context.status = "cancelled"
            logger.info(f"Survey cancelled: {self.context.reference_number}")
            return True

        return False

    def on_save_draft(self) -> str:
        """
        Handle draft saving.

        Saves the current survey state as a draft that can be resumed later.

        Returns:
            Draft ID if successful, None otherwise
        """
        try:
            # Update context status
            self.context.status = "draft"

            # Get draft data
            draft_data = self.context.to_dict()

            # Save draft to database
            draft_id = self.survey_repo.save_draft(draft_data)

            logger.info(f"Draft saved: {draft_id}")

            return draft_id

        except Exception as e:
            logger.error(f"Error saving draft: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء حفظ المسودة:\n{str(e)}"
            )
            return None

    @classmethod
    def load_from_draft(cls, draft_id: str, parent=None):
        """
        Load wizard from a saved draft.

        Args:
            draft_id: The draft ID to load
            parent: Parent widget

        Returns:
            OfficeSurveyWizard instance with restored state
        """
        try:
            # Load draft data
            survey_repo = SurveyRepository()
            draft_data = survey_repo.load_draft(draft_id)

            if not draft_data:
                raise ValueError(f"Draft not found: {draft_id}")

            # Create wizard
            wizard = cls(parent)

            # Restore context
            wizard.context = SurveyContext.from_dict(draft_data)

            # Navigate to saved step
            saved_step = wizard.context.current_step_index
            wizard.navigator.goto_step(saved_step, skip_validation=True)

            logger.info(f"Draft loaded: {draft_id}")

            return wizard

        except Exception as e:
            logger.error(f"Error loading draft: {e}", exc_info=True)
            QMessageBox.critical(
                None,
                "خطأ",
                f"حدث خطأ أثناء تحميل المسودة:\n{str(e)}"
            )
            return None

    # =========================================================================
    # UI Overrides - Exact copy from old wizard
    # =========================================================================

    def _setup_ui(self):
        """Setup the wizard UI - exact copy from old wizard (without separator)."""
        from PyQt5.QtWidgets import QVBoxLayout, QStackedWidget

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header (Step indicators)
        header = self._create_header()
        main_layout.addWidget(header)

        # Step container
        self.step_container = QStackedWidget()
        for step in self.steps:
            self.step_container.addWidget(step)
        main_layout.addWidget(self.step_container, 1)

        # Footer with navigation buttons
        footer = self._create_footer()
        main_layout.addWidget(footer)

    def _create_header(self) -> QWidget:
        """Create wizard header with title and save button - exact copy from old wizard."""
        header = QWidget()
        header.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row: Logo/Title + Save button
        header_layout = QHBoxLayout()

        # Title (matching old wizard)
        logo_label = QLabel("اضافة حالة جديدة")
        logo_label.setStyleSheet("font-family: 'Noto Kufi Arabic';font-size: 13pt; font-weight: bold; color: #000000;")
        header_layout.addWidget(logo_label)

        header_layout.addStretch()

        # Save button (matching old wizard)
        self.save_btn = QPushButton("حفظ")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                padding: 12px 24px;
                font-weight: 600;
                border-radius: 8px;
            }}
        """)
        self.save_btn.clicked.connect(self._handle_save_draft)
        header_layout.addWidget(self.save_btn)

        layout.addLayout(header_layout)

        # Step indicators
        steps_frame = QFrame()
        steps_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        steps_layout = QHBoxLayout(steps_frame)
        steps_layout.setSpacing(4)

        self.step_labels = []
        for num, name in self.STEP_NAMES:
            step_widget = QLabel(f" {num}. {name} ")
            step_widget.setAlignment(Qt.AlignCenter)
            step_widget.setStyleSheet(f"""
                background-color: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_LIGHT};
                padding: 6px 10px;
                border-radius: 12px;
                font-size: 9pt;
            """)
            self.step_labels.append(step_widget)
            steps_layout.addWidget(step_widget)

        steps_layout.addStretch()
        layout.addWidget(steps_frame)

        return header

    def _create_footer(self) -> QWidget:
        """Create wizard footer with navigation buttons - exact copy from old wizard."""
        footer = QWidget()
        footer.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Navigation buttons (Footer) - Matching the design in the old wizard
        nav_layout = QHBoxLayout()

        # Buttons on the LEFT side (start of layout)
        self.btn_previous = QPushButton("→ السابق")
        self.btn_previous.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
                margin-right: 5px;
            }}
        """)
        self.btn_previous.clicked.connect(self._handle_previous)
        self.btn_previous.setEnabled(False)
        nav_layout.addWidget(self.btn_previous)

        self.btn_next = QPushButton("التالي ←")
        self.btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
        """)
        self.btn_next.clicked.connect(self._handle_next)
        nav_layout.addWidget(self.btn_next)

        # Stretch pushes buttons to the left
        nav_layout.addStretch()

        layout.addLayout(nav_layout)

        return footer

    def _on_step_changed(self, old_index: int, new_index: int):
        """Handle step change - exact copy from old wizard."""
        # Update step container
        self.step_container.setCurrentIndex(new_index)

        # Update step indicators
        self._update_step_display()

        # Update navigation buttons
        self._update_navigation_buttons()

    def _update_step_display(self):
        """Update step indicators - exact copy from old wizard."""
        current_step = self.navigator.current_index

        for i, label in enumerate(self.step_labels):
            if i < current_step:
                # Completed
                label.setStyleSheet(f"""
                    background-color: {Config.SUCCESS_COLOR};
                    color: white;
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                """)
            elif i == current_step:
                # Active
                label.setStyleSheet(f"""
                    background-color: {Config.PRIMARY_COLOR};
                    color: white;
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                    font-weight: bold;
                """)
            else:
                # Pending
                label.setStyleSheet(f"""
                    background-color: {Config.BACKGROUND_COLOR};
                    color: {Config.TEXT_LIGHT};
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                """)

        self.step_container.setCurrentIndex(current_step)
        self.btn_previous.setEnabled(current_step > 0)

        # Update next button for final step
        if current_step == len(self.steps) - 1:
            self.btn_next.hide()
        else:
            self.btn_next.show()

    def _update_navigation_buttons(self):
        """Update navigation button states - exact copy from old wizard."""
        # Previous button
        current_step = self.navigator.current_index
        self.btn_previous.setEnabled(current_step > 0)

        # Next button - hide on last step, enable based on step readiness
        if current_step == len(self.steps) - 1:
            self.btn_next.hide()
        else:
            self.btn_next.show()
            # Enable next button based on can_go_next from navigator
            self.btn_next.setEnabled(self.navigator.can_go_next())
