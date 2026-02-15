# -*- coding: utf-8 -*-
"""
Occupancy Claims Step - Merged Person + Relation step.

Replaces the old PersonStep (Step 4) and RelationStep (Step 5).
Allows user to add/view/delete persons with their relation data
using the 3-tab PersonDialog.
"""

from typing import Dict, Any, List
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QMenu, QSpacerItem,
    QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt

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
from ui.components.toast import Toast
from ui.components.success_popup import SuccessPopup

logger = get_logger(__name__)


class OccupancyClaimsStep(BaseStep):
    """Step 4: Occupancy Claims - Person registration with relation data."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._api_service = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

    def setup_ui(self):
        """Setup the step UI - same card pattern as PersonStep."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        layout.setContentsMargins(0, 15, 0, 16)
        layout.setSpacing(15)

        # Main card
        table_frame = QFrame()
        table_frame.setObjectName("occupancyClaimsCard")
        table_frame.setLayoutDirection(Qt.RightToLeft)
        table_frame.setStyleSheet(f"""
            QFrame#occupancyClaimsCard {{
                background-color: {Colors.SURFACE};
                border-radius: 12px;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(12)

        # Header with title and add button
        header = QHBoxLayout()

        title_group = QHBoxLayout()
        title_group.setSpacing(8)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        self._title_label = QLabel(tr("wizard.occupancy_claims.title"))
        self._title_label.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        self._title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self._subtitle_label = QLabel(tr("wizard.occupancy_claims.subtitle"))
        self._subtitle_label.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        self._subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        self._subtitle_label.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(self._title_label)
        title_vbox.addWidget(self._subtitle_label)

        # Title icon
        from ui.components.icon import Icon
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
        user_icon_pixmap = Icon.load_pixmap("user", size=24)
        if user_icon_pixmap and not user_icon_pixmap.isNull():
            title_icon.setPixmap(user_icon_pixmap)
        else:
            title_icon.setText("U")
            title_icon.setStyleSheet(title_icon.styleSheet() + "font-size: 16px;")

        title_group.addWidget(title_icon)
        title_group.addLayout(title_vbox)

        # Add button
        self._add_person_btn = QPushButton(tr("wizard.occupancy_claims.add_person"))
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

        header.addLayout(title_group)
        header.addStretch()
        header.addWidget(self._add_person_btn)

        table_layout.addLayout(header)
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
        self._scroll_area = scroll_area

        # Empty state widget (shown when no persons added)
        self._empty_state = self._create_empty_state()

        table_layout.addWidget(self._empty_state)
        table_layout.addWidget(scroll_area)

        layout.addWidget(table_frame)

    def _create_empty_state(self) -> QWidget:
        """Create empty state widget shown when no persons are added."""
        from ui.components.icon import Icon
        from PyQt5.QtGui import QPixmap
        import os

        container = QWidget()
        container.setStyleSheet(f"background-color: transparent;")

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 40, 0, 40)

        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(15)

        # Icon with orange circle background (same as claim_step)
        icon_container = QLabel()
        icon_container.setFixedSize(70, 70)
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet("""
            background-color: #ffcc33;
            border-radius: 35px;
        """)

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "assets", "images", "tdesign_no-result.png"
        )
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_container.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            no_result_pixmap = Icon.load_pixmap("tdesign_no-result", size=40)
            if no_result_pixmap and not no_result_pixmap.isNull():
                icon_container.setPixmap(no_result_pixmap)
            else:
                icon_container.setText("!")
                icon_container.setStyleSheet(icon_container.styleSheet() + "font-size: 28px; color: #1a1a1a;")

        # Title
        title_label = QLabel(tr("wizard.occupancy_claims.empty_title"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Description
        desc_label = QLabel(tr("wizard.occupancy_claims.empty_desc"))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_DESC, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        center_layout.addWidget(icon_container, alignment=Qt.AlignCenter)
        center_layout.addWidget(title_label)
        center_layout.addWidget(desc_label)

        main_layout.addWidget(center_widget)

        return container

    def _get_context_ids(self):
        """Get survey_id, household_id, unit_id, and auth_token from context."""
        auth_token = None
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            auth_token = main_window._api_token

        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")

        unit_id = None
        if self.context.unit:
            unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            unit_id = self.context.new_unit_data.get('unit_uuid')

        return auth_token, survey_id, household_id, unit_id

    def _add_person(self):
        """Show PersonDialog to add a new person."""
        auth_token, survey_id, household_id, unit_id = self._get_context_ids()

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
            api_id = dialog.get_api_person_id()
            if api_id:
                person_data['person_id'] = api_id
            elif not person_data.get('person_id'):
                person_data['person_id'] = str(uuid.uuid4())
            rel_id = dialog.get_api_relation_id()
            if rel_id:
                person_data['_relation_id'] = rel_id
            self.context.persons.append(person_data)
            self.context.finalize_response = None
            self._refresh_persons_list()
            logger.info(f"Person added: {person_data['first_name']} {person_data['last_name']} (id={person_data['person_id']})")

    def _view_person(self, person_id: str):
        """Show PersonDialog to view/edit a person."""
        person_data = None
        person_index = None

        for i, person in enumerate(self.context.persons):
            if person['person_id'] == person_id:
                person_data = person
                person_index = i
                break

        if not person_data:
            return

        auth_token, survey_id, household_id, unit_id = self._get_context_ids()

        dialog = PersonDialog(
            person_data=person_data,
            existing_persons=self.context.persons,
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id,
            household_id=household_id,
            unit_id=unit_id
        )

        if dialog.exec_() == QDialog.Accepted:
            updated_data = dialog.get_person_data()
            updated_data['person_id'] = person_id
            if self._use_api and person_id:
                try:
                    self._set_auth_token()
                    self._api_service.update_person(person_id, updated_data)
                    logger.info(f"Person {person_id} updated via API")
                except Exception as e:
                    logger.error(f"Failed to update person via API: {e}")
                    ErrorHandler.show_error(self, map_exception(e), tr("common.error"))
                    return
            self.context.persons[person_index] = updated_data
            self.context.finalize_response = None
            self._refresh_persons_list()
            logger.info(f"Person updated: {updated_data['first_name']} {updated_data['last_name']}")

    def _delete_person(self, person_id: str):
        """Delete a person with confirmation."""
        has_relations = any(r['person_id'] == person_id for r in self.context.relations)

        if has_relations:
            if not ErrorHandler.confirm(
                self,
                tr("wizard.person.delete_with_relations_confirm"),
                tr("common.warning")
            ):
                return
            self.context.relations = [r for r in self.context.relations if r['person_id'] != person_id]
        else:
            if not ErrorHandler.confirm(
                self,
                tr("wizard.person.delete_confirm"),
                tr("wizard.confirm.cancel_title")
            ):
                return

        if self._use_api and person_id:
            try:
                self._set_auth_token()
                self._api_service.delete_person(person_id)
                logger.info(f"Person {person_id} deleted from API")
            except Exception as e:
                logger.error(f"Failed to delete person from API: {e}")
                ErrorHandler.show_error(self, map_exception(e), tr("common.error"))
                return

        self.context.persons = [p for p in self.context.persons if p['person_id'] != person_id]
        self.context.finalize_response = None
        self._refresh_persons_list()
        logger.info(f"Person {person_id} deleted")

    def _create_person_row_card(self, person: dict, index: int = 0) -> QFrame:
        """Create a person row card with name, role, and action menu."""
        from ui.components.icon import Icon

        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setFixedHeight(80)
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

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(15, 0, 15, 0)

        # Right side: icon + text
        right_group = QHBoxLayout()
        right_group.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #F4F8FF;
                color: #3182CE;
                border-radius: 18px;
                border: none;
            }
        """)
        user_pixmap = Icon.load_pixmap("user", size=20)
        if user_pixmap and not user_pixmap.isNull():
            icon_lbl.setPixmap(user_pixmap)
        else:
            icon_lbl.setText("U")
            icon_lbl.setStyleSheet(icon_lbl.styleSheet() + "font-size: 16px;")

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        full_name = f"{person['first_name']} {person.get('father_name', '')} {person['last_name']}".strip()
        name_lbl = QLabel(full_name)
        name_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        name_lbl.setAlignment(Qt.AlignRight)

        # Show role from person_role or relationship_type
        role_key = person.get('person_role') or person.get('relationship_type', '')
        role_text = get_relation_type_display(role_key)
        role_lbl = QLabel(role_text)
        role_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        role_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        text_vbox.addWidget(name_lbl)
        text_vbox.addWidget(role_lbl)

        right_group.addWidget(icon_lbl)
        right_group.addLayout(text_vbox)

        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Left side: menu button
        menu_btn = QPushButton("...")
        menu_btn.setFixedWidth(40)
        menu_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #A0A0A0;
                font-size: 18px;
                background: transparent;
            }
            QPushButton:hover {
                color: #333333;
            }
        """)
        menu_btn.setCursor(Qt.PointingHandCursor)

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

        view_action = menu.addAction(tr("wizard.occupancy_claims.view"))
        view_action.triggered.connect(lambda _, pid=person['person_id']: self._view_person(pid))

        delete_action = menu.addAction(tr("wizard.occupancy_claims.delete"))
        delete_action.triggered.connect(lambda _, pid=person['person_id']: self._delete_person(pid))

        menu_btn.clicked.connect(lambda: menu.exec_(menu_btn.mapToGlobal(menu_btn.rect().bottomRight())))

        card_layout.addLayout(right_group)
        card_layout.addSpacerItem(spacer)
        card_layout.addWidget(menu_btn)

        return card

    def _refresh_persons_list(self):
        """Refresh the persons list display and toggle empty state."""
        while self.persons_table_layout.count() > 1:
            item = self.persons_table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_persons = len(self.context.persons) > 0

        # Toggle empty state vs scroll area
        self._empty_state.setVisible(not has_persons)
        self._scroll_area.setVisible(has_persons)

        for idx, person in enumerate(self.context.persons):
            person_card = self._create_person_row_card(person, idx)
            self.persons_table_layout.insertWidget(idx, person_card)

    def _collect_relations_from_persons(self) -> List[Dict[str, Any]]:
        """Collect relation data from person records (stored in relation_data)."""
        relations = []
        for person in self.context.persons:
            rel_data = person.get('relation_data', {})
            rel_type = rel_data.get('rel_type') or person.get('relationship_type') or person.get('person_role')
            if not rel_type:
                continue

            relation = {
                "relation_id": str(uuid.uuid4()),
                "person_id": person.get('person_id'),
                "person_name": f"{person.get('first_name', '')} {person.get('last_name', '')}",
                "relation_type": rel_type,
                "ownership_share": rel_data.get('ownership_share', 0.0),
                "start_date": rel_data.get('start_date'),
                "contract_type": rel_data.get('contract_type'),
                "evidence_type": rel_data.get('evidence_type'),
                "evidence_description": rel_data.get('evidence_desc'),
                "notes": rel_data.get('notes'),
                "has_documents": rel_data.get('has_documents', False),
                "evidences": []
            }
            relations.append(relation)

        return relations

    # API Integration

    def _fetch_persons_from_api(self):
        """Fetch persons from API and update context."""
        # Skip fetch if persons already exist locally to avoid overwriting
        # with raw API data (camelCase keys) that crashes the UI
        if self.context.persons:
            logger.info(f"Using {len(self.context.persons)} existing persons from context, skipping API fetch")
            return

        self._set_auth_token()

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
                logger.info("No persons found from API")
        except Exception as e:
            logger.error(f"Failed to fetch persons from API: {e}")

    def _process_claims_via_api(self):
        """Process claims by calling the finalize API."""
        self._set_auth_token()

        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            logger.warning("No survey_id found in context. Skipping process-claims.")
            ErrorHandler.show_warning(self, tr("wizard.error.no_survey_id"), tr("common.error"))
            return

        logger.info(f"Processing claims for survey {survey_id}")

        # Only send notes on first finalization to prevent duplication
        already_finalized = self.context.get_data("_survey_finalized_once")
        process_options = {
            "finalNotes": "" if already_finalized else "Survey completed from office wizard",
            "durationMinutes": 10,
            "autoCreateClaim": True
        }

        try:
            api_data = self._api_service.finalize_office_survey(survey_id, process_options)
            logger.info(f"Survey {survey_id} claims processed successfully")
            self.context.finalize_response = api_data
            self.context.update_data("_survey_finalized_once", True)

            claims_count = api_data.get("claimsCreatedCount", 0)
            created_claims = api_data.get("createdClaims", [])

            if api_data.get("claimCreated") or claims_count > 0:
                logger.info(f"Claims created: {claims_count}")

                claim_number = created_claims[0].get('claimNumber', '') if created_claims else ''
                SuccessPopup.show_success(
                    claim_number=claim_number,
                    title=tr("wizard.success.title"),
                    description=tr("wizard.success.description"),
                    auto_close_ms=0,
                    parent=self
                )
            else:
                reason = api_data.get('claimNotCreatedReason', 'Unknown')
                logger.warning(f"Claim not created. Reason: {reason}")
                ErrorHandler.show_warning(
                    self,
                    tr("wizard.claims.no_claims_created", reason=reason),
                    tr("wizard.claims.process_title")
                )

        except Exception as e:
            logger.error(f"Failed to process claims: {e}")
            self.context.finalize_response = None
            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))
            Toast.show_toast(self, tr("wizard.relation.claims_failed"), Toast.WARNING)

    # BaseStep interface

    def update_language(self, is_arabic: bool):
        """Update translatable texts when language changes."""
        self._title_label.setText(tr("wizard.occupancy_claims.title"))
        self._subtitle_label.setText(tr("wizard.occupancy_claims.subtitle"))
        self._add_person_btn.setText(tr("wizard.occupancy_claims.add_person"))
        self._refresh_persons_list()

    def validate(self) -> StepValidationResult:
        """Validate - at least one person with a relation required."""
        result = self.create_validation_result()

        if len(self.context.persons) == 0:
            result.add_error(tr("wizard.person.min_one_required"))

        has_relationship = any(
            person.get('person_role') or person.get('relationship_type')
            for person in self.context.persons
        )
        if not has_relationship:
            result.add_warning(tr("wizard.person.no_relation_type_warning"))

        # Collect relations from person data into context
        self.context.relations = self._collect_relations_from_persons()

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect persons and relations data."""
        relations = self._collect_relations_from_persons()
        self.context.relations = relations
        return {
            "persons": self.context.persons,
            "persons_count": len(self.context.persons),
            "relations": relations,
            "relations_count": len(relations)
        }

    def populate_data(self):
        """Populate step with context data."""
        self._refresh_persons_list()

    def on_show(self):
        """Called when step is shown."""
        super().on_show()
        if self._use_api:
            self._fetch_persons_from_api()
        self._refresh_persons_list()

    def on_next(self):
        """Called when user clicks Next - process claims via API."""
        # Guard: only process claims once to prevent duplicate creation
        if hasattr(self.context, 'finalize_response') and self.context.finalize_response:
            logger.info("Claims already processed, skipping duplicate process-claims call")
            return
        if self._use_api:
            self._process_claims_via_api()

    def get_step_title(self) -> str:
        return tr("wizard.occupancy_claims.step_title")

    def get_step_description(self) -> str:
        return tr("wizard.occupancy_claims.step_description")
