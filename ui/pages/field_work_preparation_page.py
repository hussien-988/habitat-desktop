# -*- coding: utf-8 -*-
"""
Field Work Preparation Page - Like Wizard Pattern
UC-012: Assign Buildings to Field Teams

Structure (SAME as BaseWizard):
- Header (fixed)
- QStackedWidget (content changes between steps)
- Footer (fixed)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QFrame, QPushButton,
    QHBoxLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from controllers.building_controller import BuildingController
from ui.components.wizard_header import WizardHeader
from ui.font_utils import create_font, FontManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class FieldWorkPreparationPage(QWidget):
    """
    Field Work Preparation - Wizard-like Structure (DRY).

    Same structure as BaseWizard:
    1. Fixed header
    2. QStackedWidget for steps
    3. Fixed footer
    """

    # Signals (use 'object' to pass Python dicts with complex values)
    completed = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, building_controller: BuildingController, i18n: I18n, parent=None):
        """Initialize field work preparation."""
        super().__init__(parent)
        self.building_controller = building_controller
        self.i18n = i18n

        self._setup_ui()
        self._create_steps()

    def _setup_ui(self):
        """Setup UI (SAME structure as BaseWizard)."""
        self.setLayoutDirection(Qt.RightToLeft)

        # Background
        from ui.style_manager import StyleManager
        self.setStyleSheet(StyleManager.page_background())

        # === OUTER LAYOUT (NO PADDING) for full-width footer ===
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # === CONTENT CONTAINER (WITH PADDING) ===
        content_container = QWidget()
        content_container.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(content_container)
        from ui.design_system import PageDimensions
        content_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 32px
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            0                                         # Bottom: 0
        )
        content_layout.setSpacing(0)

        # === HEADER (FIXED) ===
        self.header = WizardHeader(
            title="تجهيز العمل الميداني",
            subtitle="المباني  •  تجهيز العمل الميداني"
        )
        content_layout.addWidget(self.header)

        # No spacing - step1 will handle its own top spacing (15px)

        # === STEP CONTAINER (QStackedWidget) ===
        self.step_container = QStackedWidget()
        content_layout.addWidget(self.step_container, 1)  # Stretch to fill available space

        # Add content to outer layout
        outer_layout.addWidget(content_container, 1)

        # === FOOTER (FIXED, FULL WIDTH) ===
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    def _create_footer(self):
        """Create footer (SAME as BaseFieldWorkStep)."""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top: 1px solid #E1E8ED;
            }
        """)
        footer.setFixedHeight(74)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(130, 12, 130, 12)
        layout.setSpacing(0)

        # Back button
        self.btn_back = QPushButton("<   السابق")
        self.btn_back.setFixedSize(252, 50)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_back = QGraphicsDropShadowEffect()
        shadow_back.setBlurRadius(8)
        shadow_back.setXOffset(0)
        shadow_back.setYOffset(2)
        shadow_back.setColor(QColor("#E5EAF6"))
        self.btn_back.setGraphicsEffect(shadow_back)

        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #414D5A;
                border: none;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #F8F9FA;
            }
            QPushButton:disabled {
                background-color: transparent;
                color: transparent;
                border: none;
            }
        """)
        self.btn_back.clicked.connect(self._on_back)
        self.btn_back.setEnabled(False)  # Disabled on Step 1
        layout.addWidget(self.btn_back)

        layout.addStretch()

        # Next button
        self.btn_next = QPushButton("التالي   >")
        self.btn_next.setFixedSize(252, 50)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_next = QGraphicsDropShadowEffect()
        shadow_next.setBlurRadius(8)
        shadow_next.setXOffset(0)
        shadow_next.setYOffset(2)
        shadow_next.setColor(QColor("#E5EAF6"))
        self.btn_next.setGraphicsEffect(shadow_next)

        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #f0f7ff;
                color: #3890DF;
                border: 1px solid #3890DF;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #E3F2FD;
            }
            QPushButton:disabled {
                background-color: #F8F9FA;
                color: #9CA3AF;
                border-color: #E1E8ED;
            }
        """)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_next.setEnabled(False)  # Initially disabled
        layout.addWidget(self.btn_next)

        return footer

    def _create_steps(self):
        """Create steps and add to container."""
        # Import here to avoid circular import
        from ui.pages.field_work_preparation_step1 import FieldWorkPreparationStep1

        # Step 1: Select Buildings
        self.step1 = FieldWorkPreparationStep1(
            self.building_controller,
            self.i18n,
            parent=self
        )
        self.step_container.addWidget(self.step1)

        # Step 2: Select Researcher (will be created when needed)
        self.step2 = None

        self.current_step = 0

    def _on_back(self):
        """Handle back button."""
        if self.current_step > 0:
            self.current_step -= 1
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

    def _on_next(self):
        """Handle next button."""
        if self.current_step == 0:
            # Moving from Step 1 to Step 2
            selected_buildings = self.step1.get_selected_buildings()
            if not selected_buildings:
                return

            # Create Step 2 if not exists
            if self.step2 is None:
                from ui.pages.field_work_preparation_step2 import FieldWorkPreparationStep2
                self.step2 = FieldWorkPreparationStep2(
                    selected_buildings,
                    self.i18n,
                    parent=self
                )
                self.step_container.addWidget(self.step2)

            self.current_step = 1
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

        elif self.current_step == 1:
            try:
                # Show confirmation dialog before completing
                researcher = self.step2.get_selected_researcher()
                buildings = self.step1.get_selected_buildings()
                logger.info(f"Step 2 finish: researcher={researcher}, buildings={len(buildings)}")

                # Show confirmation dialog
                from ui.components.field_work_confirmation_dialog import FieldWorkConfirmationDialog
                building_count = len(buildings)
                researcher_name = researcher.get('name', 'N/A') if researcher else 'N/A'

                confirmed = FieldWorkConfirmationDialog.show_confirmation(
                    building_count,
                    researcher_name,
                    self
                )
                logger.info(f"Confirmation dialog result: {confirmed}")

                if confirmed:
                    workflow_data = {
                        'buildings': buildings,
                        'researcher': researcher
                    }
                    logger.info(f"Completing field work with {building_count} buildings")
                    # Call main window handler directly (signal approach had delivery issues)
                    main_window = self.window()
                    if hasattr(main_window, '_on_field_work_completed'):
                        main_window._on_field_work_completed(workflow_data)
                    else:
                        logger.error("Main window missing _on_field_work_completed handler")
            except Exception as e:
                logger.error(f"Error in field work completion: {e}", exc_info=True)

    def _update_navigation(self):
        """Update navigation buttons based on current step."""
        if self.current_step == 0:
            # Step 1
            self.btn_back.setEnabled(False)
            self.btn_next.setText("التالي   >")
            # Enable next if buildings selected
            has_selection = len(self.step1.get_selected_buildings()) > 0 if hasattr(self, 'step1') else False
            self.btn_next.setEnabled(has_selection)

        elif self.current_step == 1:
            # Step 2
            self.btn_back.setEnabled(True)
            self.btn_next.setText("إنهاء   >")
            # Enable next if researcher selected
            has_researcher = self.step2.get_selected_researcher() is not None if self.step2 else False
            self.btn_next.setEnabled(has_researcher)

    def enable_next_button(self, enabled: bool):
        """Allow steps to enable/disable next button."""
        self.btn_next.setEnabled(enabled)
