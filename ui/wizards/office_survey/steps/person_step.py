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
    QFrame, QScrollArea, QWidget, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QSpacerItem,
    QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.dialogs.person_dialog import PersonDialog
from app.config import Config
from utils.logger import get_logger

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

    def setup_ui(self):
        """Setup the step's UI - exact copy from old wizard."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet("background-color: #F8FAFC;")
        layout = self.main_layout
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(16)

        # Main Card Container
        table_frame = QFrame()
        table_frame.setLayoutDirection(Qt.RightToLeft)
        table_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(20, 20, 20, 20)
        table_layout.setSpacing(10)

        # Header with Title on right and Add Button on left (RTL layout)
        persons_header = QHBoxLayout()

        # Title on the right (appears first in RTL)
        title_vbox = QVBoxLayout()
        title_label = QLabel("بيانات الأشخاص")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; border: none; color: #1A202C;")
        title_label.setAlignment(Qt.AlignRight)
        subtitle_label = QLabel("قائمة الأشخاص المسجلين")
        subtitle_label.setStyleSheet("color: #A0AEC0; font-size: 12px; border: none;")
        subtitle_label.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(subtitle_label)

        # Add button on the left (appears last in RTL)
        add_person_btn = QPushButton("+ اضافة شخص جديد")
        add_person_btn.setLayoutDirection(Qt.RightToLeft)
        add_person_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #3182CE;
                border: 1px solid #3182CE;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBF8FF;
            }
        """)
        add_person_btn.clicked.connect(self._add_person)

        persons_header.addLayout(title_vbox)
        persons_header.addStretch()
        persons_header.addWidget(add_person_btn)

        table_layout.addLayout(persons_header)
        table_layout.addSpacing(10)

        # Scroll area for person cards
        scroll_area = QScrollArea()
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
        """Show dialog to add a new person - exact copy from old wizard."""
        dialog = PersonDialog(
            person_data=None,
            existing_persons=self.context.persons,
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            person_data = dialog.get_person_data()
            person_data['person_id'] = str(uuid.uuid4())
            self.context.persons.append(person_data)
            self._refresh_persons_list()
            logger.info(f"Person added: {person_data['first_name']} {person_data['last_name']}")

    def _create_person_row_card(self, person: dict, index: int = 0) -> QFrame:
        """Create a person row card matching the new design layout - exact copy from old wizard."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setFixedHeight(80)
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }
        """)

        # Main row layout (RTL: items added left-to-right appear right-to-left)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(15, 0, 15, 0)

        # 1. Right Side Group: Icon and Text (appears on right in RTL)
        right_group = QHBoxLayout()
        right_group.setSpacing(12)

        # Icon
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #F4F8FF;
                color: #3182CE;
                border-radius: 18px;
                font-size: 16px;
                border: none;
            }
        """)
        icon_lbl.setText("👤")

        # Text Container (Name and Role)
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        # Person name
        full_name = f"{person['first_name']} {person.get('father_name', '')} {person['last_name']}".strip()
        name_lbl = QLabel(full_name)
        name_lbl.setStyleSheet("font-weight: bold; color: #333333; font-size: 14px; border: none;")
        name_lbl.setAlignment(Qt.AlignRight)

        # Person role/status
        rel_type_map = {
            "owner": "مالك",
            "tenant": "مستأجر",
            "occupant": "ساكن",
            "co_owner": "شريك في الملكية",
            "heir": "وارث",
            "guardian": "ولي/وصي",
            "other": "أخرى"
        }
        role_text = rel_type_map.get(person.get('relationship_type'), "ساكن")
        role_lbl = QLabel(role_text)
        role_lbl.setStyleSheet("color: #8C8C8C; font-size: 12px; border: none;")
        role_lbl.setAlignment(Qt.AlignRight)

        text_vbox.addWidget(name_lbl)
        text_vbox.addWidget(role_lbl)

        # Assemble the Right Group (Icon first, then text in RTL)
        right_group.addWidget(icon_lbl)
        right_group.addLayout(text_vbox)

        # 2. Spacer: Pushes content to the edges
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 3. Left Side: Menu Button (appears on left in RTL)
        menu_btn = QPushButton("•••")
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
        view_action = menu.addAction("👁 عرض")
        view_action.triggered.connect(lambda _, pid=person['person_id']: self._view_person(pid))

        # Delete action with icon
        delete_action = menu.addAction("🗑 حذف")
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
            dialog = PersonDialog(
                person_data=person_data,
                existing_persons=self.context.persons,
                parent=self
            )

            if dialog.exec_() == QDialog.Accepted:
                updated_data = dialog.get_person_data()
                updated_data['person_id'] = person_id  # Keep the same ID
                self.context.persons[person_index] = updated_data
                self._refresh_persons_list()
                logger.info(f"Person updated: {updated_data['first_name']} {updated_data['last_name']}")

    def _delete_person_by_id(self, person_id: str):
        """Delete person by ID with confirmation - exact copy from old wizard."""
        # Check if person has relations
        has_relations = any(r['person_id'] == person_id for r in self.context.relations)

        if has_relations:
            reply = QMessageBox.question(
                self,
                "تحذير",
                "هذا الشخص مرتبط بعلاقات. سيتم حذف العلاقات أيضاً.\nهل تريد المتابعة؟",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # Remove relations
            self.context.relations = [r for r in self.context.relations if r['person_id'] != person_id]
        else:
            reply = QMessageBox.question(
                self,
                "تأكيد الحذف",
                "هل أنت متأكد من حذف هذا الشخص؟",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.context.persons = [p for p in self.context.persons if p['person_id'] != person_id]
        self._refresh_persons_list()
        logger.info("Person deleted")

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        # At least one person must be registered
        if len(self.context.persons) == 0:
            result.add_error("يجب تسجيل شخص واحد على الأقل")

        # Check if at least one person has a relationship type
        has_relationship = any(
            person.get('relationship_type') for person in self.context.persons
        )
        if not has_relationship:
            result.add_warning("لا يوجد أشخاص مع نوع علاقة محدد")

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
        """Called when step is shown."""
        super().on_show()
        self._refresh_persons_list()

    def get_step_title(self) -> str:
        """Get step title."""
        return "تسجيل الأشخاص"

    def get_step_description(self) -> str:
        """Get step description."""
        return "سجل الأشخاص المرتبطين بالوحدة العقارية"
