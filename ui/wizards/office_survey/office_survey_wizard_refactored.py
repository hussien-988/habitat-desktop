# -*- coding: utf-8 -*-
"""
Office Survey Wizard - UC-004.

Multi-step wizard for conducting office-based property surveys.

This implementation uses the unified Wizard Framework.

Steps:
1. Building Selection - Search and select building
2. Unit Selection/Creation - Select existing or create new unit
3. Occupancy Details - Record occupancy demographics
4. Occupancy Claims - Add persons with relation data
5. Claim Creation - Create tenure claim
6. Review & Submit - Review and submit survey
"""

from typing import List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QSpacerItem, QSizePolicy
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QFont, QColor
from ui.error_handler import ErrorHandler
from services.error_mapper import map_exception

from ui.wizards.framework import BaseWizard, BaseStep
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.steps import (
    BuildingSelectionStep,
    UnitSelectionStep,
    HouseholdStep,
    OccupancyClaimsStep,
    ClaimStep,
    ReviewStep
)

from repositories.survey_repository import SurveyRepository
from repositories.database import Database
from ui.design_system import PageDimensions, Colors, ButtonDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from ui.components.success_popup import SuccessPopup
from utils.logger import get_logger
from services.translation_manager import tr

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

    @classmethod
    def get_step_names(cls):
        """Get step names (translated at runtime)."""
        return [
            ("1", tr("wizard.step.building_registration")),
            ("2", tr("wizard.step.property_unit")),
            ("3", tr("wizard.step.occupation_details")),
            ("4", tr("wizard.step.occupancy_claims")),
            ("5", tr("wizard.step.claim")),
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
            OccupancyClaimsStep(self.context, self),
            ClaimStep(self.context, self),
            ReviewStep(self.context, self)
        ]
        return steps

    def set_auth_token(self, token: str):
        """
        Set authentication token for API calls.

        Passes the token to the BuildingController in the building selection step.

        Args:
            token: JWT/Bearer token from user login
        """
        if not token:
            logger.warning("No token provided to wizard")
            return

        # Find the building selection step and set the token on its controller
        for step in self.steps:
            if isinstance(step, BuildingSelectionStep):
                if hasattr(step, 'building_controller') and step.building_controller:
                    step.building_controller.set_auth_token(token)
                    logger.info("API token set for wizard's BuildingController")
                break

    def get_wizard_title(self) -> str:
        """Get wizard title."""
        return tr("wizard.title")

    def get_submit_button_text(self) -> str:
        """Get submit button text."""
        return tr("wizard.button.finish_survey")

    def on_submit(self) -> bool:
        """
        Handle wizard submission.

        Calls the finalize API to transition the survey from Draft to Finalized status.

        POST /api/v1/Surveys/office/{id}/finalize

        Returns:
            True if submission was successful
        """
        from services.api_client import get_api_client
        from app.config import Config
        import json

        try:
            # Check if API mode is enabled
            use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

            if use_api:
                # Get survey_id from context
                survey_id = self.context.get_data("survey_id")

                if not survey_id:
                    logger.error("No survey_id found in context for finalization")
                    ErrorHandler.show_warning(
                        self,
                        tr("wizard.error.no_survey_id"),
                        tr("common.error")
                    )
                    return False

                # Initialize API service and set auth token
                api_service = get_api_client()

                # Get auth token from main window
                main_window = self.window()
                if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
                    api_service.set_access_token(main_window._api_token)
                    logger.info(f"Auth token set for finalize API call")

                # Call the finalize API
                logger.info(f"Calling finalize API for survey {survey_id}")
                print(f"\n[FINALIZE] POST /api/v1/Surveys/office/{survey_id}/finalize")

                try:
                    response = api_service.finalize_survey_status(survey_id)

                    print(f"[FINALIZE] Response: {json.dumps(response, indent=2, ensure_ascii=False, default=str)}")

                    # Update context status
                    self.context.status = "finalized"

                    logger.info(f"Survey {survey_id} finalized successfully via API")

                    # Get claim number from context or response
                    claim_number = self.context.reference_number or survey_id

                    # Show success popup with claim number
                    SuccessPopup.show_success(
                        claim_number=claim_number,
                        title=tr("wizard.success.title"),
                        description=tr("wizard.success.description"),
                        auto_close_ms=0,  # No auto-close, user must click
                        parent=self
                    )

                    # Mark finalization as complete to prevent "save draft" dialog
                    self._finalization_complete = True

                    return True

                except Exception as api_error:
                    error_msg = str(api_error)
                    logger.error(f"Failed to finalize survey: {error_msg}")

                    ErrorHandler.show_error(
                        self,
                        f"{tr('wizard.error.finalize_failed')}\n{error_msg}",
                        tr("common.error")
                    )
                    return False
            else:
                # Local database mode - use original logic
                survey_data = self.context.to_dict()
                survey_id = self.survey_repo.create_survey(survey_data)

                self.context.status = "completed"

                logger.info(f"Survey completed successfully: {survey_id}")

                # Get claim number from context
                claim_number = self.context.reference_number or survey_id

                # Show success popup with claim number
                SuccessPopup.show_success(
                    claim_number=claim_number,
                    title=tr("wizard.success.title"),
                    description=tr("wizard.success.description"),
                    auto_close_ms=0,  # No auto-close, user must click
                    parent=self
                )

                # Mark finalization as complete to prevent "save draft" dialog
                self._finalization_complete = True

                return True

        except Exception as e:
            logger.error(f"Error submitting survey: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            ErrorHandler.show_error(
                self,
                f"{tr('wizard.error.save_failed')}\n{map_exception(e)}",
                tr("common.error")
            )
            return False

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

            # Save draft to database (using create method)
            # UC-005: Office surveys are saved as drafts with status='draft'
            draft_id = self.survey_repo.create(draft_data)

            logger.info(f"Draft saved: {draft_id}")

            return draft_id

        except Exception as e:
            logger.error(f"Error saving draft: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"{tr('wizard.error.draft_save_failed')}\n{map_exception(e)}",
                tr("common.error")
            )
            return None

    def _handle_close(self):
        """Handle close button click - triggers wizard cancellation."""
        if self.on_cancel():
            self.wizard_cancelled.emit()
            self.close()

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

    # =========================================================================
    # UI Overrides - Exact copy from old wizard
    # =========================================================================

    def _setup_ui(self):
        """
        Setup the wizard UI with proper layout structure.

        Layout Structure (Senior PyQt5 Pattern):
        - Outer layout (no padding): Contains content widget + footer
        - Content widget (with padding 131px horizontal): Contains header + steps
        - Footer (no padding): Full width, extends to window edges

        This ensures the footer extends to the full window width without being
        affected by the content padding.

        Padding from Figma:
        - Content horizontal: 131px each side
        - Content top: 32px from navbar
        - Footer: Full width (no horizontal padding)
        """
        from PyQt5.QtWidgets import QVBoxLayout, QStackedWidget

        # Background color from Figma
        self.setStyleSheet(StyleManager.page_background())

        # ========== OUTER LAYOUT (NO PADDING) ==========
        # This contains everything and ensures footer can extend full width
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)  # No padding at all
        outer_layout.setSpacing(0)  # No spacing between content and footer

        # ========== CONTENT WIDGET (WITH PADDING) ==========
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

        # ========== ADD CONTENT TO OUTER LAYOUT ==========
        outer_layout.addWidget(content_widget)

        # ========== FOOTER (FULL WIDTH, NO PADDING) ==========
        # Footer is added directly to outer_layout, so it extends to full window width
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    def _create_header(self) -> QWidget:
        """
        Create wizard header with title, subtitle, and save button.

        Figma Specs Applied:
        - Title: "إضافة حالة جديدة" - 24px (18pt) Bold, Text/Primary
        - Subtitle: "المطالبات المكتملة • [Step Name]" - Desktop/Body2, Text/Secondary
        - Save button: Figma button specs
        """
        header = QWidget()
        header.setStyleSheet("background-color: transparent;")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        # DRY: Using PageDimensions.HEADER_GAP (30px from Figma) for gap between elements
        layout.setSpacing(PageDimensions.HEADER_GAP)  # 30px: title → tabs, same as completed_claims_page

        # ========== TITLE ROW: Title + Save button ==========
        title_row = QHBoxLayout()
        title_row.setSpacing(16)

        # Title/Subtitle container (vertical)
        title_subtitle_container = QVBoxLayout()
        title_subtitle_container.setSpacing(4)  # Small gap between title and subtitle

        # Title: "إضافة حالة جديدة"
        # Figma: Desktop/H4 24px = 18pt Bold
        self.title_label = QLabel(tr("wizard.header.title"))
        title_font = create_font(
            size=FontManager.SIZE_TITLE,  # 18pt (24px Figma)
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
            size=FontManager.SIZE_BODY,  # 9pt (12px Figma)
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

        # Close button FIRST (DRY: Using ButtonDimensions and Colors constants)
        # Figma specs: 52×48px, White background, X in Primary/Main color
        self.close_btn = QPushButton("✕")
        self.close_btn.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions from Figma (DRY: ButtonDimensions)
        self.close_btn.setFixedSize(ButtonDimensions.CLOSE_WIDTH, ButtonDimensions.CLOSE_HEIGHT)

        # Apply font (DRY: Using create_font utility + ButtonDimensions)
        close_btn_font = create_font(
            size=ButtonDimensions.CLOSE_FONT_SIZE,  # 12pt (16px Figma)
            weight=QFont.Normal,  # 400 - lighter weight
            letter_spacing=0
        )
        self.close_btn.setFont(close_btn_font)

        # Figma styling (DRY: Using Colors and ButtonDimensions constants)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {ButtonDimensions.CLOSE_BORDER_RADIUS}px;
                padding: {ButtonDimensions.CLOSE_PADDING_V}px {ButtonDimensions.CLOSE_PADDING_H}px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BACKGROUND_LIGHT};
            }}
        """)
        self.close_btn.clicked.connect(self._handle_close)
        title_row.addWidget(self.close_btn)

        # Save button SECOND with icon (DRY: Using ButtonDimensions constants)
        # Figma specs: 114×48px, padding 24×12, icon 14×14, spacing 10px
        self.save_btn = QPushButton(f" {tr('wizard.button.save')}")  # Space for icon
        self.save_btn.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions from Figma (DRY: ButtonDimensions)
        self.save_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)

        # Load save icon from assets (DRY: reusing Icon component pattern)
        from PyQt5.QtGui import QIcon
        import os
        save_icon_path = os.path.join("assets", "images", "save.png")
        if os.path.exists(save_icon_path):
            self.save_btn.setIcon(QIcon(save_icon_path))
            # DRY: Using ButtonDimensions.SAVE_ICON_SIZE
            self.save_btn.setIconSize(QSize(ButtonDimensions.SAVE_ICON_SIZE, ButtonDimensions.SAVE_ICON_SIZE))

        # Apply font (DRY: Using create_font utility + ButtonDimensions)
        save_btn_font = create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,  # 12pt (16px Figma)
            weight=QFont.Normal,  # 400 - lighter weight
            letter_spacing=0
        )
        self.save_btn.setFont(save_btn_font)

        # Figma styling (DRY: Using Colors and ButtonDimensions constants)
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
        self.save_btn.clicked.connect(self._handle_save_draft)
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

        # Horizontal layout for step indicators (DRY: respecting main_layout padding)
        steps_layout = QHBoxLayout(steps_frame)
        # Add vertical margins to accommodate shadow effect (prevent clipping)
        # Top: 2px, Bottom: 4px to prevent shadow from being cut off
        steps_layout.setContentsMargins(0, 2, 0, 4)
        # DRY: Using ButtonDimensions.STEP_TAB_GAP (20px from Figma)
        steps_layout.setSpacing(ButtonDimensions.STEP_TAB_GAP)  # 20px gap between tabs

        # Create step indicator tabs (Figma: white background, 111×35px, border-radius 14px)
        # No numbers shown, only step names with proper padding
        self.step_labels = []
        # Steps 3,4 (index 2,3) have longer names - use smaller font
        self._step_font_sizes = []
        for num, name in self.get_step_names():
            # Display only the step name (no number) - Figma spec
            step_widget = QLabel(name)
            step_widget.setAlignment(Qt.AlignCenter)

            # Fixed dimensions from Figma (DRY: ButtonDimensions)
            step_widget.setFixedSize(ButtonDimensions.STEP_TAB_WIDTH, ButtonDimensions.STEP_TAB_HEIGHT)

            # Smaller font for long step names (تفاصيل الإشغال، ادعاءات الإشغال)
            tab_font_size = 7 if num in ("3", "4") else ButtonDimensions.STEP_TAB_FONT_SIZE
            self._step_font_sizes.append(tab_font_size)

            # Default state: White background, gray text, no border
            # DRY: Using Colors and ButtonDimensions constants
            # Padding: 16px horizontal, 10px vertical (Figma)
            step_widget.setStyleSheet(f"""
                background-color: {Colors.SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-radius: {ButtonDimensions.STEP_TAB_BORDER_RADIUS}px;
                padding: {ButtonDimensions.STEP_TAB_PADDING_V}px {ButtonDimensions.STEP_TAB_PADDING_H}px;
                font-size: {tab_font_size}pt;
            """)

            # Apply subtle shadow effect for visual depth
            # Best Practice: Consistent shadow across step tabs
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
        """
        Create wizard footer as white card with navigation buttons.

        Figma Specs:
        - White card: Full width × 74px height
        - Design width: 1512px (reference)
        - Internal padding: 130px left/right, 12px top/bottom
        - Drop shadow effect
        - Navigation buttons inside

        Returns:
            QFrame: Footer card with navigation buttons
        """
        # Create footer as QFrame (white card)
        footer = QFrame()
        footer.setObjectName("WizardFooter")

        # Fixed HEIGHT only - width is responsive (extends to full window width)
        # Height from Figma: 74px
        footer.setFixedHeight(ButtonDimensions.FOOTER_HEIGHT)

        # Apply white card styling with border (DRY: StyleManager)
        footer.setStyleSheet(StyleManager.wizard_footer())

        # Apply drop shadow effect (Figma shadow specs from PageDimensions)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(PageDimensions.CARD_SHADOW_BLUR)  # 8px blur
        shadow.setXOffset(PageDimensions.CARD_SHADOW_X)  # 0px X offset
        shadow.setYOffset(PageDimensions.CARD_SHADOW_Y)  # 4px Y offset
        # Shadow color: #919EAB with 16% opacity
        shadow_color = QColor(PageDimensions.CARD_SHADOW_COLOR)
        shadow_color.setAlpha(int(255 * PageDimensions.CARD_SHADOW_OPACITY / 100))  # Convert 16% to alpha
        shadow.setColor(shadow_color)
        footer.setGraphicsEffect(shadow)

        # Internal layout with Figma padding (130px left/right, 12px top/bottom)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            ButtonDimensions.FOOTER_PADDING_H,  # Left: 130px
            ButtonDimensions.FOOTER_PADDING_V,  # Top: 12px
            ButtonDimensions.FOOTER_PADDING_H,  # Right: 130px
            ButtonDimensions.FOOTER_PADDING_V   # Bottom: 12px
        )
        layout.setSpacing(0)  # No spacing in main layout

        # Apply font for navigation buttons (DRY: Using create_font utility)
        # Figma: 16px font size, Normal weight (400)
        nav_btn_font = create_font(
            size=ButtonDimensions.NAV_BUTTON_FONT_SIZE,  # 12pt (16px Figma)
            weight=QFont.Normal,  # 400 - lighter weight
            letter_spacing=0
        )

        # ========== "السابق" Button (Previous - Right side) ==========
        # Figma: 252×50px, White background, shadow, border-radius 8px, text color #414D5A
        # Text format: "< السابق" with 10px spacing between arrow and text
        # Note: Button uses transparent state instead of hide() to maintain layout position
        self.btn_previous = QPushButton(f"<   {tr('wizard.button.previous')}")
        self.btn_previous.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions from Figma (DRY: ButtonDimensions)
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

        # Apply drop shadow to previous button (Figma shadow)
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

        # Spacer between buttons (748px gap - calculated from Figma)
        # Formula: 1512 - (130*2 padding) - (252*2 buttons) = 748px
        spacer = QSpacerItem(
            ButtonDimensions.NAV_BUTTON_GAP,  # 748px
            ButtonDimensions.NAV_BUTTON_HEIGHT,  # 50px
            QSizePolicy.Fixed,
            QSizePolicy.Fixed
        )
        layout.addItem(spacer)

        # ========== "التالي" Button (Next - Left side) ==========
        # Figma: 252×50px, Light blue background (#F0F7FF), Blue text, Blue border
        # Text format: "التالي >" with 10px spacing between text and arrow
        self.btn_next = QPushButton(f"{tr('wizard.button.next')}   >")
        self.btn_next.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions from Figma (DRY: ButtonDimensions)
        self.btn_next.setFixedSize(
            ButtonDimensions.NAV_BUTTON_WIDTH,   # 252px
            ButtonDimensions.NAV_BUTTON_HEIGHT   # 50px
        )

        # Apply font
        self.btn_next.setFont(nav_btn_font)

        # Figma styling: Light blue background (#F0F7FF), blue text and border
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

        # ========== "حفظ" Button (Save - Left side, shown only on final step) ==========
        # Figma: Same dimensions as next button, Primary blue background, white text
        from PyQt5.QtGui import QIcon
        import os

        self.btn_final_save = QPushButton(tr("wizard.button.save"))
        self.btn_final_save.setCursor(Qt.PointingHandCursor)

        # Fixed dimensions from Figma (same as next button)
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

        # Figma styling: Primary blue background, white text
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

    def _on_step_changed(self, old_index: int, new_index: int):
        """
        Handle step change.

        Updates:
        - Step container display
        - Subtitle with current step name (Figma spec: dynamic subtitle)
        - Step indicators
        - Navigation buttons
        """
        # Update step container
        self.step_container.setCurrentIndex(new_index)

        # Update subtitle part 2 with current step name (Figma: dynamic subtitle)
        step_names = self.get_step_names()
        if hasattr(self, 'subtitle_part2') and 0 <= new_index < len(step_names):
            step_name = step_names[new_index][1]
            self.subtitle_part2.setText(step_name)

        # Update step indicators
        self._update_step_display()

        # Update navigation buttons
        self._update_navigation_buttons()

    def _update_step_display(self):
        """
        Update step indicators with proper state styling.

        Figma specs (all tabs):
        - Background: White (#FFFFFF)
        - Active: Blue text + blue border
        - Inactive: Gray text + no border
        - Border-radius: 14px (same as pill)

        DRY: Uses Colors and ButtonDimensions constants.
        """
        current_step = self.navigator.current_index

        for i, label in enumerate(self.step_labels):
            tab_font = self._step_font_sizes[i] if i < len(self._step_font_sizes) else ButtonDimensions.STEP_TAB_FONT_SIZE
            if i == current_step:
                # Active tab (Figma: white bg, blue text, blue border, padding 10×16)
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
        """
        Update navigation button states based on current step.

        Figma Specs:
        - Step 1: Previous button is INVISIBLE (transparent, maintains space)
        - Step 2+: Previous button is VISIBLE and enabled
        - Last step: Next button is HIDDEN (removed from layout)
        - Other steps: Next button is VISIBLE (enabled based on validation)

        Best Practice: Uses CSS transparency for Previous button to maintain fixed layout,
        avoiding container widgets or dynamic layout changes.
        """
        current_step = self.navigator.current_index

        # ========== Previous Button Logic ==========
        # Make transparent on first step, visible on all other steps
        if current_step == 0:
            # First step: make button invisible (transparent) but keep in layout
            self.btn_previous.setStyleSheet(self.btn_previous_hidden_style)
            self.btn_previous.setEnabled(False)
            self.btn_previous.setCursor(Qt.ArrowCursor)  # Normal cursor when invisible
            # Disable shadow when invisible
            self.prev_shadow.setEnabled(False)
        else:
            # Steps 2+: make button visible with proper styling
            self.btn_previous.setStyleSheet(self.btn_previous_visible_style)
            self.btn_previous.setEnabled(True)
            self.btn_previous.setCursor(Qt.PointingHandCursor)  # Pointer cursor when visible
            # Enable shadow when visible
            self.prev_shadow.setEnabled(True)

        # ========== Next Button Logic ==========
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
