# -*- coding: utf-8 -*-
"""
Person Step - Step 4 of Office Survey Wizard.

Allows user to:
- View list of registered persons
- Add new persons
- Edit existing persons
- Delete persons
"""

from typing import Dict, Any, List
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QSpacerItem,
    QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.dialogs.person_dialog import PersonDialog
from app.config import Config
from services.api_client import get_api_client
from utils.logger import get_logger
from ui.error_handler import ErrorHandler
from ui.font_utils import FontManager, create_font
from ui.design_system import Colors
from services.translation_manager import tr
from services.display_mappings import get_relation_type_display
from services.error_mapper import map_exception

logger = get_logger(__name__)


class PersonStep(BaseStep):
    """
    Step 4: Person Registration.

    User can:
    - Add multiple persons
    - Edit person information
    - Delete persons
    - View all registered persons in a table
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)

        # Initialize API service for fetching persons
        self._api_service = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

    def setup_ui(self):
        """Setup the step's UI - matching Step 1 styling."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        # Set main window background color
        widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        # Match Step 1 margins: No horizontal padding - wizard handles it (131px)
        # Only vertical spacing for step content
        layout.setContentsMargins(0, 15, 0, 16)  # Top: 15px, Bottom: 16px
        layout.setSpacing(15)  # Unified spacing: 15px between cards

        # Main Card Container - matching Step 1 card styling
        table_frame = QFrame()
        table_frame.setObjectName("personsCard")
        table_frame.setLayoutDirection(Qt.RightToLeft)
        table_frame.setStyleSheet(f"""
            QFrame#personsCard {{
                background-color: {Colors.SURFACE};
                border-radius: 12px;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(12, 12, 12, 12)  # Match Step 1: 12px padding
        table_layout.setSpacing(12)  # Match Step 1: 12px spacing

        # Header with Title on right and Add Button on left (RTL layout)
        persons_header = QHBoxLayout()

        # Title group with icon and text (appears first in RTL)
        title_group = QHBoxLayout()
        title_group.setSpacing(8)

        # Title text container
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)  # Match Step 1 spacing
        self._title_label = QLabel(tr("wizard.person.card_title"))
        # Title: 14px from Figma = 10pt, weight 600, color WIZARD_TITLE (matching Step 1)
        self._title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self._subtitle_label = QLabel(tr("wizard.person.subtitle"))
        # Subtitle: 14px from Figma = 10pt, weight 400, color WIZARD_SUBTITLE (matching Step 1)
        self._subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        self._subtitle_label.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(self._title_label)
        title_vbox.addWidget(self._subtitle_label)

        # Icon for title
        title_icon = QLabel()
        title_icon.setFixedSize(40, 40)
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        # Load user.png icon using Icon.load_pixmap for absolute path resolution
        from ui.components.icon import Icon
        user_icon_pixmap = Icon.load_pixmap("user", size=24)
        if user_icon_pixmap and not user_icon_pixmap.isNull():
            title_icon.setPixmap(user_icon_pixmap)
        else:
            # Fallback if image not found
            title_icon.setText("👤")
            title_icon.setStyleSheet(title_icon.styleSheet() + "font-size: 16px;")

        # Assemble title group (icon first in code = rightmost visually in RTL)
        title_group.addWidget(title_icon)
        title_group.addLayout(title_vbox)

        # Add button on the left (appears last in RTL) - matching Step 1 styling
        self._add_person_btn = QPushButton(tr("wizard.person.add_button"))
        self._add_person_btn.setLayoutDirection(Qt.RightToLeft)
        self._add_person_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._add_person_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.PRIMARY_BLUE};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #EBF8FF;
            }}
        """)
        self._add_person_btn.clicked.connect(self._add_person)

        persons_header.addLayout(title_group)
        persons_header.addStretch()
        persons_header.addWidget(self._add_person_btn)

        table_layout.addLayout(persons_header)
        # Gap: 12px between header and content (matching Step 1)
        table_layout.addSpacing(12)

        # Scroll area for person cards
        scroll_area = QScrollArea()
        scroll_area.setLayoutDirection(Qt.RightToLeft)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        scroll_widget = QWidget()
        scroll_widget.setLayoutDirection(Qt.RightToLeft)
        scroll_widget.setStyleSheet("background-color: transparent;")
        self.persons_table_layout = QVBoxLayout(scroll_widget)
        self.persons_table_layout.setSpacing(10)
        self.persons_table_layout.setContentsMargins(0, 0, 0, 0)
        self.persons_table_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        table_layout.addWidget(scroll_area)

        layout.addWidget(table_frame)

    def _add_person(self):
        """Show dialog to add a new person."""
        # Get auth token from main window
        auth_token = None
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            auth_token = main_window._api_token

        # Get survey_id, household_id, and unit_id from context
        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")

        # Get unit_id from selected unit or newly created unit
        unit_id = None
        if self.context.unit:
            unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            unit_id = self.context.new_unit_data.get('unit_uuid')

        dialog = PersonDialog(
            person_data=None,
            existing_persons=self.context.persons,
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id,
            household_id=household_id,
            unit_id=unit_id
        )

        if dialog.exec_() == QDialog.Accepted:
            person_data = dialog.get_person_data()
            person_data['person_id'] = str(uuid.uuid4())
            self.context.persons.append(person_data)
            self._refresh_persons_list()
            logger.info(f"Person added: {person_data['first_name']} {person_data['last_name']}")

    def _create_person_row_card(self, person: dict, index: int = 0) -> QFrame:
        """Create a person row card matching the photo design."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setFixedHeight(60)
        # Use main window background color - same for all rows
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
            }}
        """)

        # Main row layout (RTL: items added left-to-right appear right-to-left)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 0, 12, 0)

        # 1. Right Side Group: Icon and Text (appears on right in RTL)
        right_group = QHBoxLayout()
        right_group.setSpacing(12)

        # Icon - using user.png
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #F4F8FF;
                color: #3182CE;
                border-radius: 16px;
                border: none;
            }
        """)
        # Load user.png icon using Icon.load_pixmap for absolute path resolution
        from ui.components.icon import Icon
        user_pixmap = Icon.load_pixmap("user", size=20)
        if user_pixmap and not user_pixmap.isNull():
            icon_lbl.setPixmap(user_pixmap)
        else:
            # Fallback if image not found
            icon_lbl.setText("👤")
            icon_lbl.setStyleSheet(icon_lbl.styleSheet() + "font-size: 16px;")

        # Text Container (Name and Role)
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(0)
        text_vbox.setContentsMargins(0, 0, 0, 0)

        # Person name - matching Step 1 title font
        full_name = f"{person['first_name']} {person.get('father_name', '')} {person['last_name']}".strip()
        name_lbl = QLabel(full_name)
        name_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        name_lbl.setAlignment(Qt.AlignRight)

        # Person role/status - matching Step 1 subtitle font
        role_text = get_relation_type_display(person.get('relationship_type', ''))
        role_lbl = QLabel(role_text)
        role_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        role_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        #role_lbl.setAlignment(Qt.AlignRight)

        text_vbox.addWidget(name_lbl)
        text_vbox.addWidget(role_lbl)

        # Assemble the Right Group (Icon first in code = rightmost visually in RTL)
        right_group.addWidget(icon_lbl)
        right_group.addLayout(text_vbox)

        # 2. Spacer: Pushes content to the edges
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 3. Left Side: Menu Button (appears on left in RTL)
        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(36, 36)
        menu_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #64748B;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                border-radius: 18px;
            }
            QPushButton:hover {
                color: #1e293b;
                background-color: #F1F5F9;
            }
        """)
        menu_btn.setCursor(Qt.PointingHandCursor)

        # Create context menu
        menu = QMenu(menu_btn)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F3F4F6;
            }
        """)

        # View action with icon
        view_action = menu.addAction(f"👁 {tr('wizard.person.view_action')}")
        view_action.triggered.connect(lambda _, pid=person['person_id']: self._view_person(pid))

        # Delete action with icon
        delete_action = menu.addAction(f"🗑 {tr('wizard.person.delete_action')}")
        delete_action.triggered.connect(lambda _, pid=person['person_id']: self._delete_person_by_id(pid))

        menu_btn.clicked.connect(lambda: menu.exec_(menu_btn.mapToGlobal(menu_btn.rect().bottomRight())))

        # Add all to main layout (RTL order)
        card_layout.addLayout(right_group)   # Appears Right
        card_layout.addSpacerItem(spacer)    # Middle Gap
        card_layout.addWidget(menu_btn)      # Appears Left

        return card

    def _refresh_persons_list(self):
        """Refresh persons display table - exact copy from old wizard."""
        # Clear existing cards
        while self.persons_table_layout.count() > 1:  # Keep the stretch
            item = self.persons_table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add person cards
        for idx, person in enumerate(self.context.persons):
            person_card = self._create_person_row_card(person, idx)
            self.persons_table_layout.insertWidget(idx, person_card)

    def _view_person(self, person_id: str):
        """Show dialog to view/edit person data - exact copy from old wizard."""
        person_data = None
        person_index = None

        for i, person in enumerate(self.context.persons):
            if person['person_id'] == person_id:
                person_data = person
                person_index = i
                break

        if person_data:
            # Get auth token from main window
            auth_token = None
            main_window = self.window()
            if main_window and hasattr(main_window, '_api_token'):
                auth_token = main_window._api_token

            survey_id = self.context.get_data("survey_id")
            household_id = self.context.get_data("household_id")

            # Get unit_id from selected unit or newly created unit
            unit_id = None
            if self.context.unit:
                unit_id = getattr(self.context.unit, 'unit_uuid', None)
            elif self.context.new_unit_data:
                unit_id = self.context.new_unit_data.get('unit_uuid')

            dialog = PersonDialog(
                person_data=person_data,
                existing_persons=self.context.persons,
                parent=self,
                auth_token=auth_token,
                survey_id=survey_id,
                household_id=household_id,
                unit_id=unit_id,
                read_only=True
            )
            dialog.exec_()

    def _delete_person_by_id(self, person_id: str):
        """Delete person by ID with confirmation - exact copy from old wizard."""
        # Check if person has relations
        has_relations = any(r['person_id'] == person_id for r in self.context.relations)

        if has_relations:
            if not ErrorHandler.confirm(
                self,
                tr("wizard.person.delete_with_relations_confirm"),
                tr("common.warning")
            ):
                return
            # Remove relations
            self.context.relations = [r for r in self.context.relations if r['person_id'] != person_id]
        else:
            if not ErrorHandler.confirm(
                self,
                tr("wizard.person.delete_confirm"),
                tr("wizard.confirm.cancel_title")
            ):
                return

        self.context.persons = [p for p in self.context.persons if p['person_id'] != person_id]
        self._refresh_persons_list()
        logger.info("Person deleted")

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        self._title_label.setText(tr("wizard.person.card_title"))
        self._subtitle_label.setText(tr("wizard.person.subtitle"))
        self._add_person_btn.setText(tr("wizard.person.add_button"))
        # Reload person cards with new language
        self._load_persons()

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        # At least one person must be registered
        if len(self.context.persons) == 0:
            result.add_error(tr("wizard.person.min_one_required"))

        # Check if at least one person has a relationship type
        has_relationship = any(
            person.get('relationship_type') for person in self.context.persons
        )
        if not has_relationship:
            result.add_warning(tr("wizard.person.no_relation_type_warning"))

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "persons": self.context.persons,
            "persons_count": len(self.context.persons)
        }

    def populate_data(self):
        """Populate the step with data from context."""
        self._refresh_persons_list()

    def on_show(self):
        """Called when step is shown. Fetches persons from API if available."""
        super().on_show()

        if self._use_api:
            self._fetch_persons_from_api()

        self._refresh_persons_list()

    def _fetch_persons_from_api(self):
        """Fetch persons from API and update context."""
        # Set auth token
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._api_service.set_access_token(main_window._api_token)

        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")

        if not survey_id or not household_id:
            logger.warning(f"Missing survey_id ({survey_id}) or household_id ({household_id}), skipping fetch")
            return

        logger.info(f"Fetching persons for survey {survey_id}, household {household_id}")

        try:
            persons = self._api_service.get_persons_for_household(survey_id, household_id)

            if persons:
                self.context.persons = persons
                logger.info(f"Loaded {len(persons)} persons from API")
            else:
                logger.info("No persons found from API (or empty list)")

        except Exception as e:
            logger.error(f"Failed to fetch persons from API: {e}")
            # Don't block the UI, just log the error

    def get_step_title(self) -> str:
        """Get step title."""
        return tr("wizard.person.step_title")

    def get_step_description(self) -> str:
        """Get step description."""
        return tr("wizard.person.step_description")
