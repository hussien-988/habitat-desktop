# -*- coding: utf-8 -*-
"""
Person Dialog - Dialog for creating/editing persons.

Allows user to input:
- Personal information (names, birth date, national ID)
- Contact information (phone, email)
- Relationship to property unit
"""

from typing import Dict, Any, Optional, List
import uuid

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDateEdit, QFrame, QWidget,
    QGridLayout, QCheckBox
)
from PyQt5.QtCore import Qt, QDate

from app.config import Config
from services.validation_service import ValidationService
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDialog(QDialog):
    """Dialog for creating or editing a person."""

    def __init__(self, person_data: Optional[Dict] = None, existing_persons: List[Dict] = None, parent=None):
        """
        Initialize the dialog.

        Args:
            person_data: Optional existing person data for editing
            existing_persons: List of existing persons for validation
            parent: Parent widget
        """
        super().__init__(parent)
        self.person_data = person_data
        self.existing_persons = existing_persons or []
        self.editing_mode = person_data is not None
        self.validation_service = ValidationService()

        self.setWindowTitle("تعديل بيانات الشخص" if self.editing_mode else "إضافة شخص جديد")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f7fa;
            }
        """)

        self._setup_ui()

        if self.editing_mode and person_data:
            self._load_person_data(person_data)

    def _setup_ui(self):
        """Setup dialog UI."""
        self.setLayoutDirection(Qt.RightToLeft)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("تعديل بيانات الشخص" if self.editing_mode else "إضافة شخص جديد")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title)

        # Form Grid
        grid = QGridLayout()
        grid.setSpacing(15)

        label_style = "color: #555; font-weight: 600; font-size: 13px;"

        # Row 0: First Name | Last Name
        first_name_label = QLabel("الاسم الأول")
        first_name_label.setStyleSheet(label_style)
        grid.addWidget(first_name_label, 0, 0)

        last_name_label = QLabel("الكنية")
        last_name_label.setStyleSheet(label_style)
        grid.addWidget(last_name_label, 0, 1)

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("ادخل الاسم الأول")
        self.first_name.setStyleSheet(self._input_style())
        grid.addWidget(self.first_name, 1, 0)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("ادخل اسم العائلة")
        self.last_name.setStyleSheet(self._input_style())
        grid.addWidget(self.last_name, 1, 1)

        # Row 2: Mother Name | Father Name
        mother_name_label = QLabel("اسم الأم")
        mother_name_label.setStyleSheet(label_style)
        grid.addWidget(mother_name_label, 2, 0)

        father_name_label = QLabel("اسم الأب")
        father_name_label.setStyleSheet(label_style)
        grid.addWidget(father_name_label, 2, 1)

        self.mother_name = QLineEdit()
        self.mother_name.setPlaceholderText("ادخل اسم الأم")
        self.mother_name.setStyleSheet(self._input_style())
        grid.addWidget(self.mother_name, 3, 0)

        self.father_name = QLineEdit()
        self.father_name.setPlaceholderText("ادخل اسم الأب")
        self.father_name.setStyleSheet(self._input_style())
        grid.addWidget(self.father_name, 3, 1)

        # Row 4: Birth Date | National ID
        birth_date_label = QLabel("تاريخ الميلاد")
        birth_date_label.setStyleSheet(label_style)
        grid.addWidget(birth_date_label, 4, 0)

        national_id_label = QLabel("الرقم الوطني")
        national_id_label.setStyleSheet(label_style)
        grid.addWidget(national_id_label, 4, 1)

        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate(1980, 1, 1))
        self.birth_date.setDisplayFormat("yyyy-MM-dd")
        self.birth_date.setStyleSheet(self._input_style())
        grid.addWidget(self.birth_date, 5, 0)

        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("00000000000")
        self.national_id.setMaxLength(11)
        self.national_id.setStyleSheet(self._input_style())
        self.national_id.textChanged.connect(self._validate_national_id)
        grid.addWidget(self.national_id, 5, 1)

        # National ID status
        self.national_id_status = QLabel("")
        self.national_id_status.setAlignment(Qt.AlignRight)
        grid.addWidget(self.national_id_status, 6, 0, 1, 2)

        # Row 7: Email | Relationship
        email_label = QLabel("البريد الالكتروني")
        email_label.setStyleSheet(label_style)
        grid.addWidget(email_label, 7, 0)

        relationship_label = QLabel("علاقة الشخص بوحدة العقار")
        relationship_label.setStyleSheet(label_style)
        grid.addWidget(relationship_label, 7, 1)

        self.email = QLineEdit()
        self.email.setPlaceholderText("*****@gmail.com")
        self.email.setStyleSheet(self._input_style())
        grid.addWidget(self.email, 8, 0)

        self.relationship_combo = QComboBox()
        self.relationship_combo.addItem("اختر", None)
        relationship_types = [
            ("owner", "مالك"),
            ("tenant", "مستأجر"),
            ("occupant", "ساكن"),
            ("co_owner", "شريك في الملكية"),
            ("heir", "وارث"),
            ("guardian", "ولي/وصي"),
            ("other", "أخرى")
        ]
        for code, ar_name in relationship_types:
            self.relationship_combo.addItem(ar_name, code)
        self.relationship_combo.setStyleSheet(self._input_style())
        grid.addWidget(self.relationship_combo, 8, 1)

        # Row 9: Landline | Mobile
        landline_label = QLabel("رقم الهاتف")
        landline_label.setStyleSheet(label_style)
        grid.addWidget(landline_label, 9, 0)

        mobile_label = QLabel("رقم الموبايل")
        mobile_label.setStyleSheet(label_style)
        grid.addWidget(mobile_label, 9, 1)

        self.landline = QLineEdit()
        self.landline.setPlaceholderText("0000000")
        self.landline.setStyleSheet(self._input_style())
        grid.addWidget(self.landline, 10, 0)

        # Mobile with country code
        mobile_widget = QWidget()
        mobile_layout = QHBoxLayout(mobile_widget)
        mobile_layout.setContentsMargins(0, 0, 0, 0)
        mobile_layout.setSpacing(8)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("09")
        self.phone.setStyleSheet(self._input_style())

        country_code = QLineEdit()
        country_code.setText("+963")
        country_code.setReadOnly(True)
        country_code.setMaximumWidth(60)
        country_code.setStyleSheet(self._input_style())

        mobile_layout.addWidget(self.phone)
        mobile_layout.addWidget(country_code)
        grid.addWidget(mobile_widget, 10, 1)

        main_layout.addLayout(grid)

        # Hidden fields for compatibility
        self.gender = QComboBox()
        self.gender.addItem("ذكر", "male")
        self.gender.addItem("أنثى", "female")
        self.gender.hide()

        self.is_contact = QCheckBox("شخص التواصل الرئيسي")
        self.is_contact.hide()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        save_btn = QPushButton("حفظ")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        save_btn.clicked.connect(self._save_person)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 12px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _input_style(self) -> str:
        """Return standard input style."""
        return """
            QLineEdit, QComboBox, QDateEdit {
                border: 1px solid #e0e6ed;
                border-radius: 8px;
                padding: 10px;
                background-color: white;
                color: #333;
                font-size: 14px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 1px solid #4a90e2;
                background-color: white;
            }
        """

    def _validate_national_id(self):
        """Validate national ID."""
        nid = self.national_id.text().strip()

        if not nid:
            self.national_id_status.setText("")
            return True

        if len(nid) != 11 or not nid.isdigit():
            self.national_id_status.setText("⚠️ يجب أن يكون 11 رقم")
            self.national_id_status.setStyleSheet(f"color: {Config.WARNING_COLOR};")
            return False

        # Check if ID exists in other persons (skip current if editing)
        for person in self.existing_persons:
            if person.get('national_id') == nid:
                if self.editing_mode and self.person_data and person.get('person_id') == self.person_data.get('person_id'):
                    continue
                self.national_id_status.setText("❌ الرقم موجود مسبقاً")
                self.national_id_status.setStyleSheet(f"color: {Config.ERROR_COLOR};")
                return False

        self.national_id_status.setText("✅ الرقم متاح")
        self.national_id_status.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")
        return True

    def _load_person_data(self, person_data: Dict):
        """Load person data into form."""
        self.first_name.setText(person_data.get('first_name', ''))
        self.father_name.setText(person_data.get('father_name', ''))
        self.mother_name.setText(person_data.get('mother_name', ''))
        self.last_name.setText(person_data.get('last_name', ''))
        self.national_id.setText(person_data.get('national_id', ''))
        self.phone.setText(person_data.get('phone', ''))
        self.email.setText(person_data.get('email', ''))
        self.landline.setText(person_data.get('landline', ''))

        # Gender
        gender = person_data.get('gender', 'male')
        idx = self.gender.findData(gender)
        if idx >= 0:
            self.gender.setCurrentIndex(idx)

        # Birth date
        if person_data.get('birth_date'):
            bd = QDate.fromString(person_data['birth_date'], 'yyyy-MM-dd')
            if bd.isValid():
                self.birth_date.setDate(bd)

        # Relationship type
        rel_type = person_data.get('relationship_type')
        if rel_type:
            idx = self.relationship_combo.findData(rel_type)
            if idx >= 0:
                self.relationship_combo.setCurrentIndex(idx)

        self.is_contact.setChecked(person_data.get('is_contact_person', False))

    def _save_person(self):
        """Validate and save person data."""
        # Validation
        if not self.first_name.text().strip():
            Toast.show_toast(self, "الرجاء إدخال الاسم الأول", Toast.WARNING)
            return

        if not self.last_name.text().strip():
            Toast.show_toast(self, "الرجاء إدخال اسم العائلة", Toast.WARNING)
            return

        # Validate national ID
        if self.national_id.text().strip() and not self._validate_national_id():
            return

        self.accept()

    def get_person_data(self) -> Dict[str, Any]:
        """Get person data from form."""
        return {
            'person_id': self.person_data.get('person_id') if self.person_data else str(uuid.uuid4()),
            'first_name': self.first_name.text().strip(),
            'father_name': self.father_name.text().strip(),
            'mother_name': self.mother_name.text().strip(),
            'last_name': self.last_name.text().strip(),
            'national_id': self.national_id.text().strip() or None,
            'gender': self.gender.currentData(),
            'birth_date': self.birth_date.date().toString('yyyy-MM-dd'),
            'phone': self.phone.text().strip() or None,
            'email': self.email.text().strip() or None,
            'landline': self.landline.text().strip() or None,
            'relationship_type': self.relationship_combo.currentData(),
            'is_contact_person': self.is_contact.isChecked()
        }
