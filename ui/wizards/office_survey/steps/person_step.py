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

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
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
        """Setup the step's UI."""
        # Header
        header = QLabel("الخطوة 4: تسجيل الأشخاص")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        # Description
        desc = QLabel("سجل الأشخاص المرتبطين بالوحدة العقارية")
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 16px;")
        self.main_layout.addWidget(desc)

        # Add person button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.add_person_btn = QPushButton("+ إضافة شخص")
        self.add_person_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #005A9C;
            }}
        """)
        self.add_person_btn.clicked.connect(self._add_person)
        btn_layout.addWidget(self.add_person_btn)

        self.main_layout.addLayout(btn_layout)

        # Persons table
        self.persons_table = QTableWidget()
        self.persons_table.setColumnCount(7)
        self.persons_table.setHorizontalHeaderLabels([
            "الاسم الكامل",
            "الرقم الوطني",
            "تاريخ الميلاد",
            "الهاتف",
            "البريد الإلكتروني",
            "نوع العلاقة",
            "الإجراءات"
        ])
        self.persons_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.persons_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.persons_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.persons_table.setAlternatingRowColors(True)
        self.persons_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)

        self.main_layout.addWidget(self.persons_table, 1)

        # Info label
        self.info_label = QLabel("لم يتم تسجيل أي شخص بعد")
        self.info_label.setStyleSheet("color: #7f8c8d; font-style: italic; margin-top: 8px;")
        self.main_layout.addWidget(self.info_label)

    def _add_person(self):
        """Show dialog to add a new person."""
        dialog = PersonDialog(existing_persons=self.context.persons, parent=self)

        if dialog.exec_():
            person_data = dialog.get_person_data()
            self.context.add_person(person_data)
            self._refresh_table()
            logger.info(f"Person added: {person_data['first_name']} {person_data['last_name']}")

    def _edit_person(self, person_index: int):
        """Edit an existing person."""
        if 0 <= person_index < len(self.context.persons):
            person_data = self.context.persons[person_index]
            dialog = PersonDialog(
                person_data=person_data,
                existing_persons=self.context.persons,
                parent=self
            )

            if dialog.exec_():
                updated_data = dialog.get_person_data()
                self.context.persons[person_index] = updated_data
                self._refresh_table()
                logger.info(f"Person updated: {updated_data['first_name']} {updated_data['last_name']}")

    def _delete_person(self, person_index: int):
        """Delete a person."""
        if 0 <= person_index < len(self.context.persons):
            person = self.context.persons[person_index]
            reply = QMessageBox.question(
                self,
                "تأكيد الحذف",
                f"هل أنت متأكد من حذف {person['first_name']} {person['last_name']}؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                del self.context.persons[person_index]
                self._refresh_table()
                logger.info(f"Person deleted: {person['first_name']} {person['last_name']}")

    def _refresh_table(self):
        """Refresh the persons table."""
        self.persons_table.setRowCount(len(self.context.persons))

        for row, person in enumerate(self.context.persons):
            # Full name
            full_name = f"{person['first_name']} {person.get('father_name', '')} {person['last_name']}"
            self.persons_table.setItem(row, 0, QTableWidgetItem(full_name.strip()))

            # National ID
            self.persons_table.setItem(row, 1, QTableWidgetItem(person.get('national_id', '-') or '-'))

            # Birth date
            self.persons_table.setItem(row, 2, QTableWidgetItem(person.get('birth_date', '-')))

            # Phone
            self.persons_table.setItem(row, 3, QTableWidgetItem(person.get('phone', '-') or '-'))

            # Email
            self.persons_table.setItem(row, 4, QTableWidgetItem(person.get('email', '-') or '-'))

            # Relationship type
            rel_type = person.get('relationship_type', '-') or '-'
            rel_labels = {
                'owner': 'مالك',
                'tenant': 'مستأجر',
                'occupant': 'ساكن',
                'co_owner': 'شريك في الملكية',
                'heir': 'وارث',
                'guardian': 'ولي/وصي',
                'other': 'أخرى'
            }
            rel_display = rel_labels.get(rel_type, rel_type)
            self.persons_table.setItem(row, 5, QTableWidgetItem(rel_display))

            # Actions buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            actions_layout.setSpacing(4)

            # Edit button
            edit_btn = QPushButton("تعديل")
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)
            edit_btn.clicked.connect(lambda checked, idx=row: self._edit_person(idx))
            actions_layout.addWidget(edit_btn)

            # Delete button
            delete_btn = QPushButton("حذف")
            delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            delete_btn.clicked.connect(lambda checked, idx=row: self._delete_person(idx))
            actions_layout.addWidget(delete_btn)

            self.persons_table.setCellWidget(row, 6, actions_widget)

        # Update info label
        count = len(self.context.persons)
        if count == 0:
            self.info_label.setText("لم يتم تسجيل أي شخص بعد")
        else:
            self.info_label.setText(f"تم تسجيل {count} شخص/أشخاص")

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
        self._refresh_table()

    def on_show(self):
        """Called when step is shown."""
        super().on_show()
        self._refresh_table()

    def get_step_title(self) -> str:
        """Get step title."""
        return "تسجيل الأشخاص"

    def get_step_description(self) -> str:
        """Get step description."""
        return "سجل الأشخاص المرتبطين بالوحدة العقارية"
