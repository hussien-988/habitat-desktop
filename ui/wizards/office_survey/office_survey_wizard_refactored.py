# -*- coding: utf-8 -*-
"""
Office Survey Wizard - معالج المسح المكتبي
Multi-step wizard for conducting office-based property surveys.
"""

from typing import List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QSpacerItem, QSizePolicy
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QFont, QColor
from ui.error_handler import ErrorHandler
from services.error_mapper import map_exception
from services.api_worker import ApiWorker

from ui.wizards.framework import BaseWizard, BaseStep
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.steps import (
    BuildingInfoStep,
    ApplicantInfoStep,
    UnitSelectionStep,
    HouseholdStep,
    OccupancyClaimsStep,
    ReviewStep
)
from ui.wizards.office_survey.steps.claim_step import ClaimStep

from repositories.survey_repository import SurveyRepository
from repositories.database import Database
from ui.design_system import PageDimensions, Colors, ButtonDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from ui.components.success_popup import SuccessPopup
from utils.logger import get_logger
from services.translation_manager import tr
from ui.wizards.office_survey.steps.occupancy_claims_step import _is_owner_relation

logger = get_logger(__name__)


class OfficeSurveyWizard(BaseWizard):
    """Office Survey Wizard."""

    @classmethod
    def get_step_names(cls):
        """Get step names (translated at runtime)."""
        return [
            ("1", tr("wizard.step.building_registration")),
            ("2", tr("wizard.step.applicant_info")),
            ("3", tr("wizard.step.property_unit")),
            ("4", tr("wizard.step.occupation_details")),
            ("5", tr("wizard.step.occupancy_claims")),
            ("6", tr("wizard.step.final_review")),
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
        self._finalization_complete = False  # Flag to track successful finalization
        self._edit_mode = False  # True when editing a step from review
        self._edit_return_index = 5  # Always return to review step (index 5)
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
            BuildingInfoStep(self.context, self),     # 0 - Building info (read-only)
            ApplicantInfoStep(self.context, self),    # 1 - Applicant info
            UnitSelectionStep(self.context, self),    # 2 - Unit selection
            HouseholdStep(self.context, self),        # 3 - Occupancy details
            OccupancyClaimsStep(self.context, self),  # 4 - Tenure claims
            ReviewStep(self.context, self),           # 5 - Final review
            ClaimStep(self.context, self),            # 6 - Claim display
        ]
        # Connect edit signal from review step
        steps[5].edit_requested.connect(self._enter_edit_mode)
        return steps

    def set_auth_token(self, token: str):
        """
        Set authentication token for API calls.

        Args:
            token: JWT/Bearer token from user login
        """
        if not token:
            logger.warning("No token provided to wizard")
            return

        # Store token for use by individual steps
        self._auth_token = token
        logger.info("API token stored in wizard")

    def get_wizard_title(self) -> str:
        """Get wizard title."""
        return tr("wizard.title")

    def get_submit_button_text(self) -> str:
        """Get submit button text."""
        return tr("wizard.button.finish_survey")

    def on_submit(self) -> bool:
        """
        Handle wizard submission — saves survey with appropriate status.

        Sets status to 'finalized' if a claim was created, 'draft' otherwise.

        Returns:
            True if submission was successful
        """
        try:
            # If ReviewStep.on_next() already finalized the survey on the backend,
            # skip all draft-save logic and show success directly
            if self.context.status == "finalized":
                finalize_resp = getattr(self.context, 'finalize_response', None) or {}
                claim_number = (
                    finalize_resp.get("claimNumber")
                    or finalize_resp.get("claimId")
                    or ""
                )
                if not claim_number:
                    # Fetch asynchronously, show popup on callback
                    self._fetch_claim_number_from_api(
                        callback=self._show_finalized_success_popup
                    )
                    return True
                if not claim_number:
                    claim_number = self.context.reference_number or ""
                self._show_finalized_success_popup(claim_number)
                return True

            # Determine status based on claim creation result
            finalize_resp = getattr(self.context, 'finalize_response', None)
            has_claim = False
            if finalize_resp and finalize_resp.get("claimCreated"):
                has_claim = True
            if not has_claim and self.context.claims:
                # Fallback: check if claims were collected with valid owner claimants
                for c in self.context.claims:
                    if c.get("claimant_person_ids"):
                        has_claim = True
                        break
            if not has_claim and self.context.persons:
                # Last resort: check persons directly for owner/heir role
                for p in self.context.persons:
                    role = p.get('person_role') or p.get('relationship_type')
                    if _is_owner_relation(role):
                        has_claim = True
                        logger.info(f"on_submit: Owner found in persons (role={role}), setting finalized")
                        break

            if has_claim:
                self.context.status = "finalized"
                self.context.case_status = 2  # Closed
            else:
                self.context.status = "draft"
                self.context.case_status = 1  # Open

            draft_id = self.on_save_draft()
            if draft_id:
                claim_number = self.context.reference_number or draft_id
                SuccessPopup.show_success(
                    claim_number=claim_number,
                    title=tr("wizard.success.title"),
                    description=tr("wizard.success.description"),
                    auto_close_ms=0,
                    parent=self
                )
                self._finalization_complete = True
                return True
            return False

        except Exception as e:
            logger.error(f"Error submitting survey: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"{tr('wizard.error.save_failed')}\n{map_exception(e)}",
                tr("common.error")
            )
            return False

    def _fetch_claim_number_from_api(self, callback=None):
        """Fetch claim number from claims summaries API in background.

        Args:
            callback: Optional callable(str) invoked with the claim number.
        """
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            if callback:
                callback("")
            return

        from services.api_client import get_api_client
        api = get_api_client()
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            api.set_token(main_window._api_token)

        def _do_fetch():
            return api.get_claims_summaries(survey_visit_id=survey_id)

        def _on_finished(response):
            items = response if isinstance(response, list) else response.get("items", [])
            claim_number = items[0].get("claimNumber", "") if items else ""
            if callback:
                callback(claim_number)

        def _on_error(msg):
            logger.warning(f"Could not fetch claim number from API: {msg}")
            if callback:
                callback("")

        self._claim_number_worker = ApiWorker(_do_fetch)
        self._claim_number_worker.finished.connect(_on_finished)
        self._claim_number_worker.error.connect(_on_error)
        self._claim_number_worker.start()

    def _show_finalized_success_popup(self, claim_number: str):
        """Show success popup after finalization with the resolved claim number."""
        if not claim_number:
            claim_number = self.context.reference_number or ""
        SuccessPopup.show_success(
            claim_number=claim_number,
            title=tr("wizard.success.title"),
            description=tr("wizard.success.description"),
            auto_close_ms=0,
            parent=self
        )
        self._finalization_complete = True

    def on_cancel(self) -> bool:
        """Handle wizard cancellation."""
        # Ask for confirmation
        confirmed = ErrorHandler.confirm(
            self,
            tr("wizard.confirm.cancel_message"),
            tr("wizard.confirm.cancel_title")
        )

        if confirmed:
            self.context.status = "cancelled"
            logger.info(f"Survey cancelled: {self.context.reference_number}")
            return True

        return False

    def on_save_draft(self) -> str:
        """
        Handle draft saving via backend API (non-blocking).

        Saves draft notes to backend (PUT /api/v1/Surveys/{id}/draft).

        Returns:
            Survey ID if pre-checks pass and worker is started, None otherwise.
        """
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            ErrorHandler.show_error(
                self,
                tr("wizard.error.no_survey_id"),
                tr("common.error")
            )
            return None

        contact_person_id = self.context.get_data("contact_person_id")
        if not contact_person_id:
            ErrorHandler.show_error(
                self,
                "يجب إكمال بيانات مقدم الطلب قبل حفظ المسودة",
                tr("common.error")
            )
            return None

        if self.context.status == "finalized":
            logger.info(f"Survey {survey_id} is finalized, skipping draft save")
            return survey_id

        if not self.context.status or self.context.status == "in_progress":
            self.context.status = "draft"

        from services.api_client import get_api_client
        api_service = get_api_client()
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            api_service.set_access_token(main_window._api_token)

        interviewee_name = None
        if self.context.applicant:
            a = self.context.applicant
            parts_ap = [a.get("first_name_ar", ""), a.get("father_name_ar", ""), a.get("last_name_ar", "")]
            interviewee_name = " ".join(p for p in parts_ap if p) or a.get("full_name")
        if not interviewee_name and self.context.persons:
            p = self.context.persons[0]
            parts = [p.get("first_name", ""), p.get("father_name", ""), p.get("last_name", "")]
            interviewee_name = " ".join(part for part in parts if part)
            if not interviewee_name:
                interviewee_name = p.get("full_name")

        backend_draft_data = {
            "property_unit_id": self.context.unit.unit_uuid if self.context.unit else None,
            "interviewee_name": interviewee_name,
            "notes": self.context.get_data("notes"),
        }

        def _do_save():
            return api_service.save_draft_to_backend(survey_id, backend_draft_data)

        def _on_saved(_result):
            logger.info(f"Draft saved to backend: {survey_id}")

        def _on_save_error(msg):
            if "Finalized" in msg or "finalized" in msg:
                logger.warning(f"Draft save skipped (survey already finalized): {msg}")
                return
            logger.error(f"Error saving draft: {msg}")
            ErrorHandler.show_error(
                self,
                f"{tr('wizard.error.draft_save_failed')}\n{msg}",
                tr("common.error")
            )

        self._save_draft_worker = ApiWorker(_do_save)
        self._save_draft_worker.finished.connect(_on_saved)
        self._save_draft_worker.error.connect(_on_save_error)
        self._save_draft_worker.start()

        return survey_id

    def _handle_header_save(self):
        """Header save button: finalize on last step, save draft on others."""
        if self.navigator.current_index == len(self.steps) - 1:
            self._handle_submit()
        else:
            self._handle_save_draft()

    def _handle_save_draft(self):
        """Override base class to prevent duplicate notifications."""
        draft_id = self.on_save_draft()
        if draft_id:
            self._finalization_complete = True
            self.draft_saved.emit(draft_id)
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("wizard.draft.saved_success"), Toast.SUCCESS)

    def _handle_close(self):
        """Handle close button click - offers save draft before closing."""
        # If finalization already completed, just close without prompting
        if self._finalization_complete:
            self.wizard_cancelled.emit()
            self.close()
            return

        # Check if there's unsaved data worth saving
        has_data = (
            self.navigator.current_index >= 1
            or (hasattr(self.context, 'building') and self.context.building)
        )

        if has_data:
            # Show save-draft confirmation dialog
            from ui.components.dialogs.confirmation_dialog import ConfirmationDialog

            result = ConfirmationDialog.save_draft_confirmation(
                parent=self,
                title=tr("wizard.confirm.save_title"),
                message=tr("wizard.confirm.save_message")
            )

            if result == ConfirmationDialog.SAVE:
                # Save as draft
                draft_id = self.on_save_draft()
                if draft_id:
                    self._finalization_complete = True
                    from ui.components.toast import Toast
                    Toast.show_toast(self, tr("wizard.draft.saved_success"), Toast.SUCCESS)
                else:
                    # Save failed - stay in wizard
                    return

            elif result == ConfirmationDialog.DISCARD:
                # Cancel survey on server with reason
                survey_id = self.context.get_data("survey_id")
                if survey_id:
                    from PyQt5.QtWidgets import QInputDialog
                    reason, ok = QInputDialog.getMultiLineText(
                        self, "سبب الإلغاء",
                        "يرجى إدخال سبب إلغاء المسح:", ""
                    )
                    if not ok or not reason.strip():
                        return
                    self._cancel_survey_async(survey_id, reason.strip())
                self._finalization_complete = True
                logger.info("User discarded wizard changes on close")

            else:
                # User cancelled - stay in wizard
                return

        self.wizard_cancelled.emit()
        self.close()

    def _cancel_survey_async(self, survey_id: str, reason: str):
        """Cancel survey on the server in a background thread."""
        from services.api_client import get_api_client
        api = get_api_client()

        def _do_cancel():
            return api.cancel_survey(survey_id, reason)

        def _on_cancelled(_result):
            logger.info(f"Survey {survey_id} cancelled: {reason}")

        def _on_cancel_error(msg):
            logger.warning(f"Failed to cancel survey {survey_id}: {msg}")

        self._cancel_survey_worker = ApiWorker(_do_cancel)
        self._cancel_survey_worker.finished.connect(_on_cancelled)
        self._cancel_survey_worker.error.connect(_on_cancel_error)
        self._cancel_survey_worker.start()

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
            ErrorHandler.show_error(
                None,
                f"{tr('wizard.error.draft_load_failed')}\n{map_exception(e)}",
                tr("common.error")
            )
            return None

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        # Header
        self.title_label.setText(tr("wizard.header.title"))
        self._subtitle_part1.setText(tr("wizard.header.breadcrumb"))
        self.save_btn.setText(f" {tr('wizard.button.save')}")

        # Step indicator tabs
        step_names = self.get_step_names()
        for i, (num, name) in enumerate(step_names):
            if i < len(self.step_labels):
                self.step_labels[i].setText(name)

        # Footer buttons
        self.btn_previous.setText(f"<   {tr('wizard.button.previous')}")
        self.btn_next.setText(f"{tr('wizard.button.next')}   >")
        self.btn_final_save.setText(tr("wizard.button.save"))

        # Update current step subtitle
        current_idx = getattr(self, 'current_step_index', 0)
        if current_idx < len(step_names):
            self.subtitle_part2.setText(step_names[current_idx][1])

        # Propagate to all steps
        for step in self.steps:
            if hasattr(step, 'update_language'):
                step.update_language(is_arabic)
    # UI Overrides - Exact copy from old wizard

    def _setup_ui(self):
        """
        Setup the wizard UI with proper layout structure.

        Layout Structure (Senior PyQt5 Pattern):
        - Outer layout (no padding): Contains content widget + footer
        - Content widget (with padding 131px horizontal): Contains header + steps
        - Footer (no padding): Full width, extends to window edges

        This ensures the footer extends to the full window width without being
        affected by the content padding.

        Padding:
        - Content horizontal: 131px each side
        - Content top: 32px from navbar
        - Footer: Full width (no horizontal padding)
        """
        from PyQt5.QtWidgets import QVBoxLayout, QStackedWidget

        # Background color
        self.setStyleSheet(StyleManager.page_background())
        # This contains everything and ensures footer can extend full width
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)  # No padding at all
        outer_layout.setSpacing(0)  # No spacing between content and footer
        # This contains header and steps with proper padding
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")  # Inherit parent background

        content_layout = QVBoxLayout(content_widget)
        # Apply padding (EXACTLY like completed_claims_page.py)
        content_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 32px
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            PageDimensions.CONTENT_PADDING_V_BOTTOM  # Bottom: 0px
        )
        content_layout.setSpacing(PageDimensions.HEADER_GAP)  # 30px gap after header

        # Header (Step indicators)
        header = self._create_header()
        content_layout.addWidget(header)

        # Step container
        self.step_container = QStackedWidget()
        for step in self.steps:
            self.step_container.addWidget(step)
        content_layout.addWidget(self.step_container, 1)
        outer_layout.addWidget(content_widget)
        # Footer is added directly to outer_layout, so it extends to full window width
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    def _create_header(self) -> QWidget:
        """Create wizard header with title, subtitle, and save button."""
        header = QWidget()
        header.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        # PageDimensions.HEADER_GAP (30px) for gap between elements
        layout.setSpacing(PageDimensions.HEADER_GAP)  # 30px: title → tabs, same as completed_claims_page
        title_row = QHBoxLayout()
        title_row.setSpacing(16)

        # Title/Subtitle container (vertical)
        title_subtitle_container = QVBoxLayout()
        title_subtitle_container.setSpacing(4)  # Small gap between title and subtitle

        # Title: "إضافة حالة جديدة"

        self.title_label = QLabel(tr("wizard.header.title"))
        title_font = create_font(
            size=FontManager.SIZE_TITLE,  # 18pt
            weight=QFont.Bold,
            letter_spacing=0
        )
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none; background: transparent;")
        title_subtitle_container.addWidget(self.title_label)

        # Subtitle: "المطالبات المكتملة • [Step Name]"
        # Desktop/Body2 (smaller size), Text/Secondary
        subtitle_layout = QHBoxLayout()
        subtitle_layout.setSpacing(8)  # Gap between parts
        subtitle_layout.setContentsMargins(0, 0, 0, 0)

        # Part 1: "المطالبات المكتملة" (fixed)
        self._subtitle_part1 = QLabel(tr("wizard.header.breadcrumb"))
        subtitle_font = create_font(
            size=FontManager.SIZE_BODY,  # 9pt
            weight=QFont.Normal,
            letter_spacing=0
        )
        self._subtitle_part1.setFont(subtitle_font)
        self._subtitle_part1.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        subtitle_layout.addWidget(self._subtitle_part1)

        # Dot separator: "•"
        dot_label = QLabel("•")
        dot_label.setFont(subtitle_font)
        dot_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        subtitle_layout.addWidget(dot_label)

        # Part 2: Current step name (dynamic)
        self.subtitle_part2 = QLabel(tr("wizard.step.building_registration"))  # Default: first step
        self.subtitle_part2.setFont(subtitle_font)
        self.subtitle_part2.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        subtitle_layout.addWidget(self.subtitle_part2)

        subtitle_layout.addStretch()  # Push to the right

        # Add subtitle to container
        title_subtitle_container.addLayout(subtitle_layout)

        title_row.addLayout(title_subtitle_container)
        title_row.addStretch()

        # Save button with icon

        self.save_btn = QPushButton(f" {tr('wizard.button.save')}")  # Space for icon
        self.save_btn.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions
        self.save_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)

        # Load save icon from assets
        from PyQt5.QtGui import QIcon
        import os
        save_icon_path = os.path.join("assets", "images", "save.png")
        if os.path.exists(save_icon_path):
            self.save_btn.setIcon(QIcon(save_icon_path))
            # ButtonDimensions.SAVE_ICON_SIZE
            self.save_btn.setIconSize(QSize(ButtonDimensions.SAVE_ICON_SIZE, ButtonDimensions.SAVE_ICON_SIZE))

        # Apply font
        save_btn_font = create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,  # 12pt
            weight=QFont.Normal,  # 400 - lighter weight
            letter_spacing=0
        )
        self.save_btn.setFont(save_btn_font)

        # Styling
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                padding: {ButtonDimensions.SAVE_PADDING_V}px {ButtonDimensions.SAVE_PADDING_H}px;
                border-radius: {ButtonDimensions.SAVE_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
                icon-size: {ButtonDimensions.SAVE_ICON_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
        """)
        self.save_btn.clicked.connect(self._handle_header_save)
        title_row.addWidget(self.save_btn)

        layout.addLayout(title_row)

        # Step indicators (Tabs bar)
        # IMPORTANT: No padding here - main_layout already has 131px horizontal padding
        # This ensures tabs start at same position as title (131px from window edge)
        steps_frame = QFrame()
        steps_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)

        # Horizontal layout for step indicators (respecting main_layout padding)
        steps_layout = QHBoxLayout(steps_frame)
        # Add vertical margins to accommodate shadow effect (prevent clipping)
        # Top: 2px, Bottom: 4px to prevent shadow from being cut off
        steps_layout.setContentsMargins(0, 2, 0, 4)
        # ButtonDimensions.STEP_TAB_GAP (20px)
        steps_layout.setSpacing(ButtonDimensions.STEP_TAB_GAP)  # 20px gap between tabs

        # Create step indicator tabs
        # No numbers shown, only step names with proper padding
        self.step_labels = []
        # Steps 3,4 (index 2,3) have longer names - use smaller font
        self._step_font_sizes = []
        for num, name in self.get_step_names():
            # Display only the step name (no number)
            step_widget = QLabel(name)
            step_widget.setAlignment(Qt.AlignCenter)

            # Fixed dimensions
            step_widget.setFixedSize(ButtonDimensions.STEP_TAB_WIDTH, ButtonDimensions.STEP_TAB_HEIGHT)

            # Smaller font for long step names (تفاصيل الإشغال، ادعاءات الإشغال)
            tab_font_size = 7 if num in ("3", "4") else ButtonDimensions.STEP_TAB_FONT_SIZE
            self._step_font_sizes.append(tab_font_size)

            # Default state: White background, gray text, no border
            # Default state styling
            step_widget.setStyleSheet(f"""
                background-color: {Colors.SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-radius: {ButtonDimensions.STEP_TAB_BORDER_RADIUS}px;
                padding: {ButtonDimensions.STEP_TAB_PADDING_V}px {ButtonDimensions.STEP_TAB_PADDING_H}px;
                font-size: {tab_font_size}pt;
            """)

            # Apply subtle shadow effect for visual depth
            # Consistent shadow across step tabs
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            from PyQt5.QtGui import QColor
            tab_shadow = QGraphicsDropShadowEffect()
            tab_shadow.setBlurRadius(6)  # Softer blur for tabs
            tab_shadow.setXOffset(0)
            tab_shadow.setYOffset(1)  # Very slight offset
            tab_shadow.setColor(QColor(0, 0, 0, 40))  # More subtle alpha
            step_widget.setGraphicsEffect(tab_shadow)

            self.step_labels.append(step_widget)
            steps_layout.addWidget(step_widget)

        steps_layout.addStretch()
        layout.addWidget(steps_frame)

        return header

    def _create_footer(self) -> QWidget:
        """Create wizard footer with navigation buttons."""
        # Create footer as QFrame (white card)
        footer = QFrame()
        footer.setObjectName("WizardFooter")

        # Fixed HEIGHT only - width is responsive (extends to full window width)
        # Height: 74px
        footer.setFixedHeight(ButtonDimensions.FOOTER_HEIGHT)

        # Apply white card styling with border
        footer.setStyleSheet(StyleManager.wizard_footer())

        # Apply drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(PageDimensions.CARD_SHADOW_BLUR)  # 8px blur
        shadow.setXOffset(PageDimensions.CARD_SHADOW_X)  # 0px X offset
        shadow.setYOffset(PageDimensions.CARD_SHADOW_Y)  # 4px Y offset
        # Shadow color: #919EAB with 16% opacity
        shadow_color = QColor(PageDimensions.CARD_SHADOW_COLOR)
        shadow_color.setAlpha(int(255 * PageDimensions.CARD_SHADOW_OPACITY / 100))  # Convert 16% to alpha
        shadow.setColor(shadow_color)
        footer.setGraphicsEffect(shadow)

        # Internal layout with padding
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            ButtonDimensions.FOOTER_PADDING_H,  # Left: 130px
            ButtonDimensions.FOOTER_PADDING_V,  # Top: 12px
            ButtonDimensions.FOOTER_PADDING_H,  # Right: 130px
            ButtonDimensions.FOOTER_PADDING_V   # Bottom: 12px
        )
        layout.setSpacing(0)  # No spacing in main layout

        # Apply font for navigation buttons
        # Navigation button font
        nav_btn_font = create_font(
            size=ButtonDimensions.NAV_BUTTON_FONT_SIZE,  # 12pt
            weight=QFont.Normal,  # 400 - lighter weight
            letter_spacing=0
        )
        # Previous button
        # Text format: "< السابق" with 10px spacing between arrow and text
        # Note: Button uses transparent state instead of hide() to maintain layout position
        self.btn_previous = QPushButton(f"<   {tr('wizard.button.previous')}")
        self.btn_previous.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions
        self.btn_previous.setFixedSize(
            ButtonDimensions.NAV_BUTTON_WIDTH,   # 252px
            ButtonDimensions.NAV_BUTTON_HEIGHT   # 50px
        )

        # Apply font
        self.btn_previous.setFont(nav_btn_font)

        # Store visible/hidden states as properties for easy management
        self.btn_previous_visible_style = f"""
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: #414D5A;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {ButtonDimensions.NAV_BUTTON_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: {ButtonDimensions.NAV_BUTTON_FONT_SIZE}pt;
            }}
            QPushButton:hover {{
                background-color: {Colors.BACKGROUND_LIGHT};
            }}
            QPushButton:disabled {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_DISABLED};
            }}
        """

        # Invisible state: completely transparent (maintains space in layout)
        self.btn_previous_hidden_style = """
            QPushButton {
                background-color: transparent;
                color: transparent;
                border: none;
            }
        """

        # Apply drop shadow to previous button
        # Will be visible only when button is visible
        self.prev_shadow = QGraphicsDropShadowEffect()
        self.prev_shadow.setBlurRadius(8)  # 8px blur
        self.prev_shadow.setXOffset(0)  # 0px X offset
        self.prev_shadow.setYOffset(2)  # 2px Y offset
        prev_shadow_color = QColor("#919EAB")
        prev_shadow_color.setAlpha(int(255 * 0.16))  # 16% opacity
        self.prev_shadow.setColor(prev_shadow_color)
        self.btn_previous.setGraphicsEffect(self.prev_shadow)

        self.btn_previous.clicked.connect(self._handle_previous)

        # Start invisible on Step 1 (transparent style + disabled)
        self.btn_previous.setStyleSheet(self.btn_previous_hidden_style)
        self.btn_previous.setEnabled(False)

        layout.addWidget(self.btn_previous)

        # Spacer between buttons (748px gap - calculated)
        # Formula: 1512 - (130*2 padding) - (252*2 buttons) = 748px
        spacer = QSpacerItem(
            ButtonDimensions.NAV_BUTTON_GAP,  # 748px
            ButtonDimensions.NAV_BUTTON_HEIGHT,  # 50px
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )
        layout.addItem(spacer)
        # Next button
        # Text format: "التالي >" with 10px spacing between text and arrow
        self.btn_next = QPushButton(f"{tr('wizard.button.next')}   >")
        self.btn_next.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions
        self.btn_next.setFixedSize(
            ButtonDimensions.NAV_BUTTON_WIDTH,   # 252px
            ButtonDimensions.NAV_BUTTON_HEIGHT   # 50px
        )

        # Apply font
        self.btn_next.setFont(nav_btn_font)

        # Styling: Light blue background (#F0F7FF), blue text and border
        self.btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: #F0F7FF;
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.PRIMARY_BLUE};
                border-radius: {ButtonDimensions.NAV_BUTTON_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: {ButtonDimensions.NAV_BUTTON_FONT_SIZE}pt;
            }}
            QPushButton:hover {{
                background-color: rgba(56, 144, 223, 0.15);
            }}
            QPushButton:disabled {{
                background-color: {Colors.BORDER_DEFAULT};
                border: 1px solid {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_DISABLED};
            }}
        """)
        self.btn_next.clicked.connect(self._handle_next)
        layout.addWidget(self.btn_next)
        # Submit button
        from PyQt5.QtGui import QIcon
        import os

        self.btn_final_save = QPushButton(tr("wizard.button.save"))
        self.btn_final_save.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions (same as next button)
        self.btn_final_save.setFixedSize(
            ButtonDimensions.NAV_BUTTON_WIDTH,   # 252px
            ButtonDimensions.NAV_BUTTON_HEIGHT   # 50px
        )

        # Apply font
        self.btn_final_save.setFont(nav_btn_font)

        # Load save icon
        save_icon_path = os.path.join("assets", "images", "save.png")
        if os.path.exists(save_icon_path):
            self.btn_final_save.setIcon(QIcon(save_icon_path))
            self.btn_final_save.setIconSize(QSize(16, 16))

        # Styling: Primary blue background, white text
        self.btn_final_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: {ButtonDimensions.NAV_BUTTON_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: {ButtonDimensions.NAV_BUTTON_FONT_SIZE}pt;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
        """)
        self.btn_final_save.clicked.connect(self._handle_submit)
        self.btn_final_save.hide()  # Hidden by default, shown only on final step
        layout.addWidget(self.btn_final_save)

        # Push everything to the right (RTL)
        layout.addStretch()

        return footer

    def _enter_edit_mode(self, step_index: int):
        """Enter edit mode: navigate from review to a target step for editing."""
        self._edit_mode = True
        self.navigator.goto_step(step_index, skip_validation=True)

    def _exit_edit_mode(self):
        """Exit edit mode and return to the review step."""
        return_index = self._edit_return_index
        self._edit_mode = False
        self.navigator.goto_step(return_index, skip_validation=True)

    def _handle_previous(self):
        """Override back navigation with edit mode support and step-1 warning."""
        # Edit mode: Cancel → return to review
        if self._edit_mode:
            self._exit_edit_mode()
            return

        # Normal mode: warn when going back from step 1 to step 0
        if self.navigator.current_index == 1:
            from ui.components.confirmation_modal import ConfirmationModal
            confirmed = ConfirmationModal.ask_confirmation(
                self,
                title="تأكيد العودة",
                message="في حالة العودة إلى اختيار المبنى ستفقد جميع المعلومات المدخلة وسيتم بدء حالة جديدة.",
                confirm_text="موافق",
                cancel_text="إلغاء",
                confirm_style="danger"
            )
            if confirmed:
                survey_id = self.context.get_data("survey_id")
                if survey_id:
                    self._cancel_survey_async(survey_id, "User returned to building selection")
                    for key in ("survey_id", "survey_data", "survey_building_uuid",
                                "contact_person_id", "household_id",
                                "applicant_household_person_id"):
                        self.context.update_data(key, None)
                    self.context.applicant = None
                    self.context.unit = None
                    self.context.is_new_unit = False
                    self.context.new_unit_data = None
                    self.context.households = []
                    self.context.persons = []
                    self.context.relations = []
                    self.context.claims = []
                    self.context.claim_data = None
                    self.context.finalize_response = None
                self.navigator.previous_step()
            return

        super()._handle_previous()

    def _handle_next(self):
        """Override next button with edit mode support."""
        if self._edit_mode:
            # Validate current step before saving
            current_step = self.navigator.get_current_step()
            if current_step:
                validation_result = current_step.validate()
                if not validation_result.is_valid:
                    self._on_validation_failed(validation_result)
                    return
                # Call on_next() hook (API calls, data persistence)
                if hasattr(current_step, 'on_next') and callable(current_step.on_next):
                    current_step.on_next()
            self._exit_edit_mode()
            return

        super()._handle_next()

    def _on_step_changed(self, old_index: int, new_index: int):
        """
        Handle step change.

        Updates:
        - Step container display
        - Subtitle with current step name
        - Step indicators
        - Navigation buttons
        """
        # Update step container
        self.step_container.setCurrentIndex(new_index)

        step_names = self.get_step_names()
        if hasattr(self, 'subtitle_part2') and 0 <= new_index < len(step_names):
            step_name = step_names[new_index][1]
            self.subtitle_part2.setText(step_name)

        # Update step indicators
        self._update_step_display()

        # Update navigation buttons
        self._update_navigation_buttons()

    def _update_step_display(self):
        """Update step indicators with proper state styling."""
        current_step = self.navigator.current_index

        for i, label in enumerate(self.step_labels):
            tab_font = self._step_font_sizes[i] if i < len(self._step_font_sizes) else ButtonDimensions.STEP_TAB_FONT_SIZE
            if i == current_step:
                # Active tab
                label.setStyleSheet(f"""
                    background-color: {Colors.SURFACE};
                    color: {Colors.PRIMARY_BLUE};
                    border: 1px solid {Colors.PRIMARY_BLUE};
                    border-radius: {ButtonDimensions.STEP_TAB_BORDER_RADIUS}px;
                    padding: {ButtonDimensions.STEP_TAB_PADDING_V}px {ButtonDimensions.STEP_TAB_PADDING_H}px;
                    font-size: {tab_font}pt;
                    font-weight: 600;
                """)
            else:
                # Inactive tabs (Same color as title: WIZARD_TITLE)
                # Completed and Pending use same style
                label.setStyleSheet(f"""
                    background-color: {Colors.SURFACE};
                    color: {Colors.WIZARD_TITLE};
                    border: none;
                    border-radius: {ButtonDimensions.STEP_TAB_BORDER_RADIUS}px;
                    padding: {ButtonDimensions.STEP_TAB_PADDING_V}px {ButtonDimensions.STEP_TAB_PADDING_H}px;
                    font-size: {tab_font}pt;
                """)

        self.step_container.setCurrentIndex(current_step)
        self.btn_previous.setEnabled(current_step > 0)

        # Update next/save buttons for final step
        if current_step == len(self.steps) - 1:
            self.btn_next.hide()
            if hasattr(self, 'btn_final_save'):
                self.btn_final_save.show()
        else:
            self.btn_next.show()
            if hasattr(self, 'btn_final_save'):
                self.btn_final_save.hide()

    def _update_navigation_buttons(self):
        """Update navigation button states based on current step."""
        current_step = self.navigator.current_index
        if self._edit_mode:
            # Previous → "إلغاء" (Cancel)
            self.btn_previous.setStyleSheet(self.btn_previous_visible_style)
            self.btn_previous.setEnabled(True)
            self.btn_previous.setCursor(Qt.PointingHandCursor)
            self.prev_shadow.setEnabled(True)
            self.btn_previous.setText(f"<   {tr('wizard.button.cancel_edit')}")

            # Next → "حفظ التعديلات" (Save Changes)
            self.btn_next.show()
            self.btn_next.setEnabled(True)
            self.btn_next.setText(f"{tr('wizard.button.save_changes')}   >")

            # Hide final save
            if hasattr(self, 'btn_final_save'):
                self.btn_final_save.hide()
            return
        self.btn_previous.setText(f"<   {tr('wizard.button.previous')}")
        self.btn_next.setText(f"{tr('wizard.button.next')}   >")
        # Make transparent on first step and last step (ClaimStep), visible on other steps
        if current_step == 0 or current_step == len(self.steps) - 1:
            self.btn_previous.setStyleSheet(self.btn_previous_hidden_style)
            self.btn_previous.setEnabled(False)
            self.btn_previous.setCursor(Qt.ArrowCursor)
            self.prev_shadow.setEnabled(False)
        else:
            self.btn_previous.setStyleSheet(self.btn_previous_visible_style)
            self.btn_previous.setEnabled(True)
            self.btn_previous.setCursor(Qt.PointingHandCursor)
            self.prev_shadow.setEnabled(True)
        # Hide on last step, show on all other steps (with validation check)
        if current_step == len(self.steps) - 1:
            # Last step: hide next button, show save button
            self.btn_next.hide()
            if hasattr(self, 'btn_final_save'):
                self.btn_final_save.show()
        else:
            # Other steps: show next button, hide save button
            self.btn_next.show()
            if hasattr(self, 'btn_final_save'):
                self.btn_final_save.hide()
            # Enable next button based on can_go_next from navigator
            self.btn_next.setEnabled(self.navigator.can_go_next())
