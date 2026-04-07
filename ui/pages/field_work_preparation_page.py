# -*- coding: utf-8 -*-
"""Field work preparation page with wizard-style multi-step flow."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QFrame, QPushButton,
    QHBoxLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from controllers.building_controller import BuildingController
from services.translation_manager import tr, get_layout_direction
from ui.design_system import Colors
from ui.components.wizard_header import WizardHeader
from ui.components.accent_line import AccentLine
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class FieldWorkPreparationPage(QWidget):
    """Field work preparation wizard with header, steps, and footer."""

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

    _STEP_KEYS = [
        "wizard.field_work.step_select_buildings",
        "wizard.field_work.step_select_researcher",
        "wizard.field_work.step_summary",
    ]

    def _setup_ui(self):
        """Setup UI with dark wizard header and step pills."""
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(StyleManager.page_background())

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Dark header — FULL WIDTH (no padding)
        step_names = [tr(key) for key in self._STEP_KEYS]
        self.header = WizardHeader(
            title=tr("wizard.field_work.title"),
            subtitle=tr("wizard.field_work.subtitle"),
            steps=step_names,
        )
        outer_layout.addWidget(self.header)

        # Accent line — FULL WIDTH
        self._accent = AccentLine()
        outer_layout.addWidget(self._accent)

        # Step container — light content area
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(StyleManager.page_background())
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.step_container = QStackedWidget()
        content_layout.addWidget(self.step_container, 1)

        outer_layout.addWidget(content_wrapper, 1)

        # Footer — FULL WIDTH
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    def _create_footer(self):
        """Create footer with navigation buttons."""
        footer = QFrame()
        footer.setStyleSheet(StyleManager.nav_footer())
        footer.setFixedHeight(74)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(130, 12, 130, 12)
        layout.setSpacing(0)

        # Back button
        self.btn_back = QPushButton(tr("wizard.field_work.btn_back"))
        self.btn_back.setFixedSize(252, 50)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self.btn_back.setStyleSheet(StyleManager.nav_button_secondary())
        self.btn_back.clicked.connect(self._on_back)
        self.btn_back.setEnabled(False)
        layout.addWidget(self.btn_back)

        layout.addStretch()

        # Next button
        self.btn_next = QPushButton(tr("wizard.field_work.btn_next"))
        self.btn_next.setFixedSize(252, 50)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self.btn_next.setStyleSheet(StyleManager.nav_button_primary())
        self.btn_next.clicked.connect(self._on_next)
        self.btn_next.setEnabled(False)
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

        # Step 2: Select Researcher (created when needed)
        self.step2 = None

        # Step 3: Summary / Confirmation (created when needed)
        self.step3 = None

        # Step 4: Completion & Transfer Status (created after submission)
        self.step4 = None

        self.current_step = 0

        # Revisit mode state (set by _start_revisit_mode)
        self._revisit_buildings = None
        self._revisit_unit_id = None

    def load_data(self):
        """Load filter data for step 1 (call after login)."""
        if self.step1:
            self.step1.load_data()

    def _load_filter_data_async(self):
        """Load filter data for step 1 in background (non-blocking)."""
        if self.step1 and hasattr(self.step1, '_load_filter_data_async'):
            self.step1._load_filter_data_async()

    def _on_back(self):
        """Handle back button."""
        if self.current_step == 3:
            self.refresh()
            return
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
                from ui.components.toast import Toast
                Toast.show_toast(self, tr("wizard.field_work.select_building_warning"), Toast.WARNING)
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
            # Moving from Step 2 to Step 3 (summary)
            researcher = self.step2.get_selected_researcher()
            if not researcher:
                from ui.components.toast import Toast
                Toast.show_toast(self, tr("wizard.field_work.select_researcher_warning"), Toast.WARNING)
                return

            # Use revisit buildings if in revisit mode, otherwise from step1
            buildings = self._revisit_buildings or self.step1.get_selected_buildings()
            revisit_unit_id = self._revisit_unit_id
            revisit_building_id = self._revisit_buildings[0].building_id if self._revisit_buildings else ''

            # Rebuild step3 each time (fresh data)
            if self.step3 is not None:
                self.step_container.removeWidget(self.step3)
                self.step3.deleteLater()

            from ui.pages.field_work_preparation_step3 import FieldWorkPreparationStep3
            self.step3 = FieldWorkPreparationStep3(
                buildings, researcher,
                revisit_unit_id=revisit_unit_id,
                revisit_building_id=revisit_building_id,
                parent=self,
            )
            self.step_container.addWidget(self.step3)

            self.current_step = 2
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

        elif self.current_step == 2:
            # Step 3: Confirm and submit
            if not self.step3.validate():
                return
            try:
                summary = self.step3.get_summary()
                workflow_data = {
                    'buildings': summary['buildings'],
                    'researcher': summary['researcher'],
                    'revisit_reasons': summary.get('revisit_reasons', {}),
                }
                logger.info(f"Submitting field work: {len(workflow_data['buildings'])} buildings")
                main_window = self.window()
                if hasattr(main_window, '_on_field_work_completed'):
                    main_window._on_field_work_completed(workflow_data)
                else:
                    logger.error("Main window missing _on_field_work_completed handler")
            except Exception as e:
                logger.error(f"Error in field work submission: {e}", exc_info=True)

        elif self.current_step == 3:
            # Step 4: "New Assignment" button pressed — restart wizard
            self.refresh()

    def _update_navigation(self):
        """Update navigation buttons and step indicator."""
        self.header.set_current_step(min(self.current_step, len(self._STEP_KEYS) - 1))

        if self.current_step == 0:
            self.btn_back.setEnabled(False)
            self.btn_next.setText(tr("wizard.field_work.btn_next"))
            has_selection = len(self.step1.get_selected_buildings()) > 0 if hasattr(self, 'step1') else False
            self.btn_next.setEnabled(has_selection)

        elif self.current_step == 1:
            # In revisit mode there is no step1 to go back to
            self.btn_back.setEnabled(not bool(self._revisit_buildings))
            self.btn_next.setText(tr("wizard.field_work.btn_next"))
            has_researcher = self.step2.get_selected_researcher() is not None if self.step2 else False
            self.btn_next.setEnabled(has_researcher)

        elif self.current_step == 2:
            self.btn_back.setEnabled(True)
            self.btn_next.setText(tr("wizard.field_work.btn_confirm_send"))
            self.btn_next.setEnabled(True)

        elif self.current_step == 3:
            # Completion view — only "New Assignment" button
            self.btn_back.setEnabled(False)
            self.btn_next.setText(tr("wizard.field_work.btn_new_assignment"))
            self.btn_next.setEnabled(True)

    def enable_next_button(self, enabled: bool):
        """Allow steps to enable/disable next button."""
        self.btn_next.setEnabled(enabled)

    def show_completion(self, buildings, researcher_name, assignment_ids):
        """Show completion and transfer status view after successful assignment."""
        # Stop step4 refresh timer if exists from previous run
        if self.step4 is not None:
            if hasattr(self.step4, 'stop_refresh'):
                self.step4.stop_refresh()
            self.step_container.removeWidget(self.step4)
            self.step4.deleteLater()

        from ui.pages.field_work_preparation_step4 import FieldWorkPreparationStep4
        main_window = self.window()
        db = getattr(main_window, 'db', None)
        self.step4 = FieldWorkPreparationStep4(
            buildings, researcher_name, assignment_ids, db=db, parent=self
        )
        self.step_container.addWidget(self.step4)

        self.current_step = 3
        self.step_container.setCurrentIndex(self.step_container.indexOf(self.step4))
        self._update_navigation()

    def refresh(self, data=None):
        """Reset wizard to step 1 for a new assignment, or start at step 2 in revisit mode."""
        # Reset revisit state
        self._revisit_buildings = None
        self._revisit_unit_id = None

        # Remove step 4 if exists
        if self.step4 is not None:
            if hasattr(self.step4, 'stop_refresh'):
                self.step4.stop_refresh()
            self.step_container.removeWidget(self.step4)
            self.step4.deleteLater()
            self.step4 = None

        # Remove step 2 and 3 if they exist
        if self.step3 is not None:
            self.step_container.removeWidget(self.step3)
            self.step3.deleteLater()
            self.step3 = None
        if self.step2 is not None:
            self.step_container.removeWidget(self.step2)
            self.step2.deleteLater()
            self.step2 = None

        # Clear step 1 selections
        self.step1.clear_all_selections()

        # Reload filter data (communities/neighborhoods) if not yet loaded
        if hasattr(self.step1, '_load_filter_data') and not self.step1._all_communities:
            self.step1._load_filter_data()

        # If revisit mode, skip step 1 and go directly to step 2
        if data and data.get('revisit_mode'):
            self._start_revisit_mode(data['building_id'], data['unit_id'])
            return

        # Normal mode: reset to step 1
        self.current_step = 0
        self.step_container.setCurrentIndex(0)
        self._update_navigation()

    def _start_revisit_mode(self, building_id, unit_id):
        """Initialize revisit mode: pre-select building, skip to step 2."""
        from types import SimpleNamespace
        from ui.pages.field_work_preparation_step2 import FieldWorkPreparationStep2
        building_ns = SimpleNamespace(
            building_uuid=building_id,
            building_id=building_id,
        )
        self._revisit_buildings = [building_ns]
        self._revisit_unit_id = unit_id

        self.step2 = FieldWorkPreparationStep2(
            self._revisit_buildings, self.i18n, parent=self
        )
        self.step_container.addWidget(self.step2)
        self.step_container.setCurrentWidget(self.step2)
        self.current_step = 1
        self._update_navigation()

    def update_language(self, is_arabic=True):
        """Update all translatable strings when language changes."""
        self.setLayoutDirection(get_layout_direction())
        self.header.set_title(tr("wizard.field_work.title"))
        self.header.set_subtitle(tr("wizard.field_work.subtitle"))
        step_names = [tr(key) for key in self._STEP_KEYS]
        self.header.set_steps(step_names)
        self.btn_back.setText(tr("wizard.field_work.btn_back"))
        self._update_navigation()
        if self.step1 and hasattr(self.step1, 'update_language'):
            self.step1.update_language(is_arabic)
        if self.step2 and hasattr(self.step2, 'update_language'):
            self.step2.update_language(is_arabic)
        if self.step3 and hasattr(self.step3, 'update_language'):
            self.step3.update_language(is_arabic)
        if self.step4 and hasattr(self.step4, 'update_language'):
            self.step4.update_language(is_arabic)
