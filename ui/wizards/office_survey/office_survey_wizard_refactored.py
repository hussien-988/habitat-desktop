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
from ui.components.loading_spinner import LoadingSpinnerOverlay

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
from ui.components.toast import Toast
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.nav_style_tab import NavStyleTab
from ui.components.accent_line import AccentLine
from ui.wizards.office_survey.wizard_styles import (
    FOOTER_PRIMARY_STYLE, FOOTER_SECONDARY_STYLE, FOOTER_HIDDEN_STYLE,
    HEADER_SAVE_STYLE,
)
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
                survey_data = finalize_resp.get("survey", {})
                ref_code = survey_data.get("referenceCode", "") or self.context.reference_number
                self._show_finalized_success_popup(ref_code)
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
                Toast.show_toast(
                    self, tr("wizard.success.description"), Toast.SUCCESS
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

    def _show_finalized_success_popup(self, ref_code: str = ""):
        """Show success dialog with survey reference code."""
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QFrame, QGraphicsDropShadowEffect, QLineEdit,
        )
        from PyQt5.QtGui import QColor

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setModal(True)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.resize(self.width(), self.height())
        dlg.move(self.mapToGlobal(self.rect().topLeft()))

        overlay = QFrame(dlg)
        overlay.setStyleSheet("background-color: rgba(10, 20, 35, 0.65);")
        overlay.setGeometry(0, 0, dlg.width(), dlg.height())

        card_w = min(480, self.width() - 40)
        card = QFrame(dlg)
        card.setFixedWidth(card_w)
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1B3555, stop:1 #152A42);
                border-radius: 20px;
            }
            QLabel { background: transparent; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 80))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 24)
        card_layout.setSpacing(16)

        icon_lbl = QLabel("\u2714")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "color: #4ADE80; font-size: 42px; font-weight: bold;"
            "background: rgba(74, 222, 128, 0.12); border-radius: 30px;"
            "min-width: 60px; max-width: 60px; min-height: 60px; max-height: 60px;"
        )
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(icon_lbl)
        icon_row.addStretch()
        card_layout.addLayout(icon_row)

        title = QLabel(tr("wizard.success.finalized_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: rgba(240, 248, 255, 0.95); font-size: 18px; font-weight: 700;")
        title.setWordWrap(True)
        card_layout.addWidget(title)

        if ref_code:
            hint_lbl = QLabel("رقم المراجعة")
            hint_lbl.setAlignment(Qt.AlignCenter)
            hint_lbl.setStyleSheet("color: rgba(140, 190, 240, 0.7); font-size: 12px;")
            card_layout.addWidget(hint_lbl)

            ref_field = QLineEdit(ref_code)
            ref_field.setReadOnly(True)
            ref_field.setAlignment(Qt.AlignCenter)
            ref_field.setStyleSheet(
                "QLineEdit {"
                "    background: rgba(74, 222, 128, 0.1);"
                "    border: 1px solid rgba(74, 222, 128, 0.4);"
                "    border-radius: 8px;"
                "    color: #4ADE80;"
                "    font-size: 20px;"
                "    font-weight: 700;"
                "    padding: 10px 16px;"
                "    letter-spacing: 2px;"
                "}"
            )
            card_layout.addWidget(ref_field)

        ok_btn = QPushButton(tr("button.ok"))
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setFixedHeight(44)
        ok_btn.setStyleSheet(
            "QPushButton {"
            "    background-color: #3890DF; color: white; border: none;"
            "    border-radius: 10px; font-size: 15px; font-weight: 600;"
            "    padding: 0 32px;"
            "}"
            "QPushButton:hover { background-color: #2A7BC8; }"
            "QPushButton:pressed { background-color: #1E6CB3; }"
        )
        ok_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        card.adjustSize()
        card_x = (dlg.width() - card_w) // 2
        card_y = (dlg.height() - card.sizeHint().height()) // 2
        card.move(card_x, card_y)

        dlg.exec_()
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
            self._spinner.hide_loading()
            logger.info(f"Draft saved to backend: {survey_id}")

        def _on_save_error(msg):
            self._spinner.hide_loading()
            if "Finalized" in msg or "finalized" in msg:
                logger.warning(f"Draft save skipped (survey already finalized): {msg}")
                return
            logger.error(f"Error saving draft: {msg}")
            ErrorHandler.show_error(
                self,
                f"{tr('wizard.error.draft_save_failed')}\n{msg}",
                tr("common.error")
            )

        self._spinner.show_loading(tr("component.loading.default"))
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
            from ui.components.bottom_sheet import BottomSheet
            from PyQt5.QtCore import QEventLoop
            loop = QEventLoop()
            choice_result = [None]

            def on_choice(c):
                choice_result[0] = c
                loop.quit()

            def on_cancel():
                choice_result[0] = "cancel"
                loop.quit()

            sheet = BottomSheet(self)
            sheet.choice_made.connect(on_choice)
            sheet.cancelled.connect(on_cancel)
            sheet.show_choices(
                tr("wizard.confirm.save_title"),
                [
                    ("save", tr("wizard.confirm.save_draft")),
                    ("discard", tr("wizard.confirm.discard")),
                ]
            )
            loop.exec_()

            if choice_result[0] == "save":
                draft_id = self.on_save_draft()
                if draft_id:
                    self._finalization_complete = True
                    Toast.show_toast(self, tr("wizard.draft.saved_success"), Toast.SUCCESS)
                else:
                    return

            elif choice_result[0] == "discard":
                # Cancel survey on server with reason
                survey_id = self.context.get_data("survey_id")
                if survey_id:
                    reason_loop = QEventLoop()
                    reason_result = [None]

                    def on_reason_confirmed():
                        reason_data = reason_sheet.get_form_data()
                        reason_result[0] = (reason_data.get("reason") or "").strip()
                        reason_loop.quit()

                    def on_reason_cancelled():
                        reason_result[0] = None
                        reason_loop.quit()

                    reason_sheet = BottomSheet(self)
                    reason_sheet.confirmed.connect(on_reason_confirmed)
                    reason_sheet.cancelled.connect(on_reason_cancelled)
                    reason_sheet.show_form(
                        tr("wizard.cancel_reason_title"),
                        [("reason", tr("wizard.cancel_reason_prompt"), "multiline")],
                        submit_text=tr("page.case_details.confirm_cancel"),
                        cancel_text=tr("action.dismiss"),
                    )
                    reason_loop.exec_()

                    if not reason_result[0]:
                        return
                    self._cancel_survey_async(survey_id, reason_result[0])
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
            self._spinner.hide_loading()
            logger.info(f"Survey {survey_id} cancelled: {reason}")

        def _on_cancel_error(msg):
            self._spinner.hide_loading()
            logger.warning(f"Failed to cancel survey {survey_id}: {msg}")

        self._spinner.show_loading(tr("component.loading.default"))
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
                self.step_labels[i].set_text(name)

        # Footer buttons
        self.btn_previous.setText(f"\u276E   {tr('wizard.button.previous')}")
        self.btn_next.setText(f"{tr('wizard.button.next')}   \u276F")
        self.btn_final_save.setText(tr("wizard.button.save"))

        # Update current step subtitle
        current_idx = getattr(self, 'current_step_index', 0)
        if current_idx < len(step_names):
            self.subtitle_part2.setText(step_names[current_idx][1])

        # Propagate to all steps
        for step in self.steps:
            if hasattr(step, 'update_language'):
                try:
                    step.update_language(is_arabic)
                except Exception:
                    pass
    # UI Overrides - Exact copy from old wizard

    def _setup_ui(self):
        """Setup wizard UI: DarkHeaderZone + AccentLine + content + footer."""
        from PyQt5.QtWidgets import QVBoxLayout, QStackedWidget

        self.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Dark header zone with step tabs
        self._header_zone = self._create_header()
        outer_layout.addWidget(self._header_zone)

        # Accent line separator
        self._accent_line = AccentLine()
        outer_layout.addWidget(self._accent_line)

        # Content area with padding
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(),
            20,
            PageDimensions.content_padding_h(),
            0
        )
        content_layout.setSpacing(0)

        # Step container
        self.step_container = QStackedWidget()
        for step in self.steps:
            self.step_container.addWidget(step)
        content_layout.addWidget(self.step_container, 1)
        outer_layout.addWidget(content_widget, 1)

        # Footer
        footer = self._create_footer()
        outer_layout.addWidget(footer)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_header(self) -> DarkHeaderZone:
        """Create dark header zone with title, subtitle, save button, and step tabs."""
        header = DarkHeaderZone()

        # Title
        self.title_label = header.get_title_label()
        header.set_title(tr("wizard.header.title"))

        # Subtitle row (breadcrumb + dot + step name) as a single widget in row1
        subtitle_widget = QWidget()
        subtitle_widget.setStyleSheet("background: transparent;")
        subtitle_layout = QHBoxLayout(subtitle_widget)
        subtitle_layout.setContentsMargins(0, 0, 0, 0)
        subtitle_layout.setSpacing(8)

        subtitle_font = create_font(size=FontManager.SIZE_BODY, weight=QFont.Normal)

        self._subtitle_part1 = QLabel(tr("wizard.header.breadcrumb"))
        self._subtitle_part1.setFont(subtitle_font)
        self._subtitle_part1.setStyleSheet("color: rgba(139, 172, 200, 0.8); background: transparent;")
        subtitle_layout.addWidget(self._subtitle_part1)

        dot_label = QLabel("\u2022")
        dot_label.setFont(subtitle_font)
        dot_label.setStyleSheet("color: rgba(139, 172, 200, 0.6); background: transparent;")
        subtitle_layout.addWidget(dot_label)

        self.subtitle_part2 = QLabel(tr("wizard.step.building_registration"))
        self.subtitle_part2.setFont(subtitle_font)
        self.subtitle_part2.setStyleSheet("color: rgba(200, 220, 255, 0.9); background: transparent;")
        subtitle_layout.addWidget(self.subtitle_part2)
        subtitle_layout.addStretch()

        # Insert subtitle below title in the header's row1 area
        # We add it as a stat pill position (before stretch)
        header.add_stat_pill(subtitle_widget)

        # Save button
        self.save_btn = QPushButton(f" {tr('wizard.button.save')}")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)

        from PyQt5.QtGui import QIcon
        import os
        save_icon_path = os.path.join("assets", "images", "save.png")
        if os.path.exists(save_icon_path):
            self.save_btn.setIcon(QIcon(save_icon_path))
            self.save_btn.setIconSize(QSize(ButtonDimensions.SAVE_ICON_SIZE, ButtonDimensions.SAVE_ICON_SIZE))

        self.save_btn.setFont(create_font(size=ButtonDimensions.SAVE_FONT_SIZE, weight=QFont.DemiBold))
        self.save_btn.setStyleSheet(HEADER_SAVE_STYLE)
        self.save_btn.clicked.connect(self._handle_header_save)
        header.add_action_widget(self.save_btn)

        # Step indicator tabs (NavStyleTab instead of CurvedTab)
        self.step_labels = []
        self._step_font_sizes = []
        tab_font = create_font(size=9, weight=FontManager.WEIGHT_REGULAR)

        for num, name in self.get_step_names():
            step_tab = NavStyleTab(name)
            step_tab.setFixedSize(ButtonDimensions.STEP_TAB_WIDTH + 20, ButtonDimensions.STEP_TAB_HEIGHT + 3)

            tab_font_size = 7 if num in ("3", "4") else 9
            self._step_font_sizes.append(tab_font_size)
            step_tab.set_font(create_font(size=tab_font_size, weight=FontManager.WEIGHT_REGULAR))

            self.step_labels.append(step_tab)
            header.add_tab(step_tab)

        return header

    def _create_footer(self) -> QWidget:
        """Create wizard footer with navigation buttons and progress accent."""
        footer_wrapper = QWidget()
        footer_wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QVBoxLayout(footer_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        # Progress accent line at top of footer
        self._footer_progress = QFrame()
        self._footer_progress.setFixedHeight(2)
        self._footer_progress.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(56, 144, 223, 0),
                    stop:0.15 rgba(56, 144, 223, 120),
                    stop:0.5 rgba(91, 168, 240, 180),
                    stop:0.85 rgba(56, 144, 223, 120),
                    stop:1 rgba(56, 144, 223, 0));
            }
        """)
        wrapper_layout.addWidget(self._footer_progress)

        footer = QFrame()
        footer.setObjectName("WizardFooter")
        footer.setFixedHeight(ButtonDimensions.FOOTER_HEIGHT)
        footer.setStyleSheet(StyleManager.wizard_footer())

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(-3)
        shadow.setColor(QColor(0, 0, 0, 20))
        footer.setGraphicsEffect(shadow)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            ButtonDimensions.FOOTER_PADDING_H,
            ButtonDimensions.FOOTER_PADDING_V,
            ButtonDimensions.FOOTER_PADDING_H,
            ButtonDimensions.FOOTER_PADDING_V
        )
        layout.setSpacing(0)

        nav_btn_font = create_font(size=ButtonDimensions.NAV_BUTTON_FONT_SIZE, weight=QFont.DemiBold)

        # Previous button (transparent state to maintain layout)
        self.btn_previous = QPushButton(f"\u276E   {tr('wizard.button.previous')}")
        self.btn_previous.setCursor(Qt.PointingHandCursor)
        self.btn_previous.setFixedSize(ButtonDimensions.NAV_BUTTON_WIDTH, ButtonDimensions.NAV_BUTTON_HEIGHT)
        self.btn_previous.setFont(nav_btn_font)

        self.btn_previous_visible_style = FOOTER_SECONDARY_STYLE
        self.btn_previous_hidden_style = FOOTER_HIDDEN_STYLE

        self.prev_shadow = QGraphicsDropShadowEffect()
        self.prev_shadow.setBlurRadius(8)
        self.prev_shadow.setXOffset(0)
        self.prev_shadow.setYOffset(2)
        prev_shadow_color = QColor("#919EAB")
        prev_shadow_color.setAlpha(40)
        self.prev_shadow.setColor(prev_shadow_color)
        self.btn_previous.setGraphicsEffect(self.prev_shadow)
        self.btn_previous.clicked.connect(self._handle_previous)

        self.btn_previous.setStyleSheet(self.btn_previous_hidden_style)
        self.btn_previous.setEnabled(False)
        layout.addWidget(self.btn_previous)

        spacer = QSpacerItem(0, ButtonDimensions.NAV_BUTTON_HEIGHT, QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addItem(spacer)

        # Next button (gradient blue)
        self.btn_next = QPushButton(f"{tr('wizard.button.next')}   \u276F")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFixedSize(ButtonDimensions.NAV_BUTTON_WIDTH, ButtonDimensions.NAV_BUTTON_HEIGHT)
        self.btn_next.setFont(nav_btn_font)
        self.btn_next.setStyleSheet(FOOTER_PRIMARY_STYLE)
        self.btn_next.clicked.connect(self._handle_next)
        layout.addWidget(self.btn_next)

        # Final save/submit button
        from PyQt5.QtGui import QIcon
        import os

        self.btn_final_save = QPushButton(tr("wizard.button.save"))
        self.btn_final_save.setCursor(Qt.PointingHandCursor)
        self.btn_final_save.setFixedSize(ButtonDimensions.NAV_BUTTON_WIDTH, ButtonDimensions.NAV_BUTTON_HEIGHT)
        self.btn_final_save.setFont(nav_btn_font)

        save_icon_path = os.path.join("assets", "images", "save.png")
        if os.path.exists(save_icon_path):
            self.btn_final_save.setIcon(QIcon(save_icon_path))
            self.btn_final_save.setIconSize(QSize(16, 16))

        self.btn_final_save.setStyleSheet(FOOTER_PRIMARY_STYLE)
        self.btn_final_save.clicked.connect(self._handle_submit)
        self.btn_final_save.hide()
        layout.addWidget(self.btn_final_save)

        layout.addStretch()

        wrapper_layout.addWidget(footer)
        return footer_wrapper

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
            confirmed = ErrorHandler.confirm(
                self,
                tr("wizard.confirm.back_message"),
                tr("wizard.confirm.back_title"),
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

        # Pulse accent line on step change
        if hasattr(self, '_accent_line'):
            self._accent_line.pulse()

        # Update navigation buttons
        self._update_navigation_buttons()

    def _update_step_display(self):
        """Update step indicators with proper state styling and completion marks."""
        current_step = self.navigator.current_index
        for i, tab in enumerate(self.step_labels):
            if i == current_step:
                tab.set_active(True)
            elif i < current_step:
                # Completed steps: keep inactive but show completed state
                tab.set_active(False)
                # Prefix with checkmark for completed steps
                step_names = self.get_step_names()
                if i < len(step_names):
                    tab.set_text(f"\u2713 {step_names[i][1]}")
            else:
                tab.set_active(False)
                # Reset text for future steps
                step_names = self.get_step_names()
                if i < len(step_names):
                    tab.set_text(step_names[i][1])

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
            self.btn_previous.setStyleSheet(self.btn_previous_visible_style)
            self.btn_previous.setEnabled(True)
            self.btn_previous.setCursor(Qt.PointingHandCursor)
            self.prev_shadow.setEnabled(True)
            self.btn_previous.setText(f"\u276E   {tr('wizard.button.cancel_edit')}")

            self.btn_next.show()
            self.btn_next.setEnabled(True)
            self.btn_next.setText(f"{tr('wizard.button.save_changes')}   \u276F")

            if hasattr(self, 'btn_final_save'):
                self.btn_final_save.hide()
            return
        self.btn_previous.setText(f"\u276E   {tr('wizard.button.previous')}")
        self.btn_next.setText(f"{tr('wizard.button.next')}   \u276F")
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
