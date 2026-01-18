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

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import pyqtSignal

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

    # Signals (aliases for BaseWizard signals for backward compatibility)
    survey_completed = pyqtSignal(dict)
    survey_cancelled = pyqtSignal()
    survey_saved_draft = pyqtSignal(str)

    def __init__(self, db: Database = None, parent=None):
        """Initialize the wizard."""
        self.db = db or Database()
        self.survey_repo = SurveyRepository(self.db)
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
