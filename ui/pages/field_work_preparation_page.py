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
from ui.font_utils import create_font, FontManager
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

    def _setup_ui(self):
        """Setup UI layout."""
        self.setLayoutDirection(get_layout_direction())

        # Background
        from ui.style_manager import StyleManager
        self.setStyleSheet(StyleManager.page_background())
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        content_container = QWidget()
        content_container.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(content_container)
        from ui.design_system import PageDimensions
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(),        # Left: 131px
            PageDimensions.content_padding_v_top(),    # Top: 32px
            PageDimensions.content_padding_h(),        # Right: 131px
            0                                         # Bottom: 0
        )
        content_layout.setSpacing(0)
        self.header = WizardHeader(
            title=tr("wizard.field_work.title"),
            subtitle=tr("wizard.field_work.subtitle")
        )
        content_layout.addWidget(self.header)

        # No spacing - step1 will handle its own top spacing (15px)
        self.step_container = QStackedWidget()
        content_layout.addWidget(self.step_container, 1)  # Stretch to fill available space

        # Add content to outer layout
        outer_layout.addWidget(content_container, 1)
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    def _create_footer(self):
        """Create footer with navigation buttons."""
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
        self.btn_back = QPushButton(tr("wizard.field_work.btn_back"))
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
        self.btn_next = QPushButton(tr("wizard.field_work.btn_next"))
        self.btn_next.setFixedSize(252, 50)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_next = QGraphicsDropShadowEffect()
        shadow_next.setBlurRadius(8)
        shadow_next.setXOffset(0)
        shadow_next.setYOffset(2)
        shadow_next.setColor(QColor("#E5EAF6"))
        self.btn_next.setGraphicsEffect(shadow_next)

        self.btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: #2A7BC8;
            }}
            QPushButton:disabled {{
                background-color: #F8F9FA;
                color: #9CA3AF;
                border: none;
            }}
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

        # Step 2: Select Researcher (created when needed)
        self.step2 = None

        # Step 3: Summary / Confirmation (created when needed)
        self.step3 = None

        # Step 4: Completion & Transfer Status (created after submission)
        self.step4 = None

        self.current_step = 0

    def load_data(self):
        """Load filter data for step 1 (call after login)."""
        if self.step1:
            self.step1.load_data()

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
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, tr("wizard.field_work.warning_title"), tr("wizard.field_work.select_building_warning"))
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
            buildings = self.step1.get_selected_buildings()
            if not researcher:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, tr("wizard.field_work.warning_title"), tr("wizard.field_work.select_researcher_warning"))
                return

            # Rebuild step3 each time (fresh data)
            if self.step3 is not None:
                self.step_container.removeWidget(self.step3)
                self.step3.deleteLater()

            from ui.pages.field_work_preparation_step3 import FieldWorkPreparationStep3
            self.step3 = FieldWorkPreparationStep3(buildings, researcher, parent=self)
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
                    'revisit_buildings': summary.get('revisit_buildings', []),
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
        """Update navigation buttons based on current step."""
        if self.current_step == 0:
            self.btn_back.setEnabled(False)
            self.btn_next.setText(tr("wizard.field_work.btn_next"))
            has_selection = len(self.step1.get_selected_buildings()) > 0 if hasattr(self, 'step1') else False
            self.btn_next.setEnabled(has_selection)

        elif self.current_step == 1:
            self.btn_back.setEnabled(True)
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
        """Reset wizard to step 1 for a new assignment."""
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

        # Reset to step 1
        self.current_step = 0
        self.step_container.setCurrentIndex(0)
        self._update_navigation()

        # Clear step 1 selections
        self.step1._selected_building_ids.clear()
        self.step1._confirmed_building_ids.clear()
        while self.step1.selected_table_layout.count():
            item = self.step1.selected_table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.step1.buildings_list.clear()
        self.step1._set_suggestions_visible(False)
        self.step1._update_selection_count()
        self.step1._update_selected_card_visibility()

        # Reload filter data (communities/neighborhoods) if not yet loaded
        if hasattr(self.step1, '_load_filter_data') and not self.step1._all_communities:
            self.step1._load_filter_data()

    def update_language(self, is_arabic=True):
        """Update all translatable strings when language changes."""
        self.setLayoutDirection(get_layout_direction())
        self.header.set_title(tr("wizard.field_work.title"))
        self.header.set_subtitle(tr("wizard.field_work.subtitle"))
        self.btn_back.setText(tr("wizard.field_work.btn_back"))
        self._update_navigation()
        if self.step1 and hasattr(self.step1, 'update_language'):
            self.step1.update_language(is_arabic)
        if self.step2 and hasattr(self.step2, 'update_language'):
            self.step2.update_language(is_arabic)
        if self.step3 and hasattr(self.step3, 'update_language'):
            self.step3.update_language(is_arabic)
