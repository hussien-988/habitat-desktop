# -*- coding: utf-8 -*-
"""
Persons management page with search, CRUD, and validation.
Implements UC-003: Person Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QFileDialog,
    QAbstractItemView, QGraphicsDropShadowEffect, QMessageBox, QCheckBox,
    QGroupBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor
import re

from app.config import Config, Vocabularies
from repositories.database import Database
from repositories.person_repository import PersonRepository
from models.person import Person
from services.validation_service import ValidationService
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonsTableModel(QAbstractTableModel):
    """Table model for persons."""

    def __init__(self, is_arabic: bool = True):
        super().__init__()
        self._persons = []
        self._is_arabic = is_arabic
        self._headers_en = ["Name", "Father Name", "National ID", "Nationality", "Gender", "Phone", "Email"]
        self._headers_ar = ["الاسم", "اسم الأب", "الرقم الوطني", "الجنسية", "الجنس", "الهاتف", "البريد"]

    def rowCount(self, parent=None):
        return len(self._persons)

    def columnCount(self, parent=None):
        return len(self._headers_en)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._persons):
            return None

        person = self._persons[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return person.full_name_ar if self._is_arabic else person.full_name
            elif col == 1:
                return person.father_name_ar if self._is_arabic else person.father_name
            elif col == 2:
                return person.national_id or "-"
            elif col == 3:
                return person.nationality or "-"
            elif col == 4:
                return person.gender_display_ar if self._is_arabic else person.gender_display
            elif col == 5:
                return person.phone_number or person.mobile_number or "-"
            elif col == 6:
                return person.email or "-"
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = self._headers_ar if self._is_arabic else self._headers_en
            return headers[section] if section < len(headers) else ""
        return None

    def set_persons(self, persons: list):
        self.beginResetModel()
        self._persons = persons
        self.endResetModel()

    def get_person(self, row: int):
        if 0 <= row < len(self._persons):
            return self._persons[row]
        return None

    def set_language(self, is_arabic: bool):
        self._is_arabic = is_arabic
        self.layoutChanged.emit()


class PersonDialog(QDialog):
    """Dialog for creating/editing a person."""

    # ID Document types
    ID_DOCUMENT_TYPES = [
        ("", "-- اختر نوع الوثيقة --"),
        ("national_id_card", "بطاقة الهوية الوطنية"),
        ("passport", "جواز السفر"),
        ("family_booklet", "دفتر العائلة"),
        ("birth_certificate", "شهادة الميلاد"),
        ("driver_license", "رخصة القيادة"),
        ("other", "أخرى"),
    ]

    # Nationality options
    NATIONALITIES = [
        ("Syrian", "سوري"),
        ("Palestinian", "فلسطيني"),
        ("Iraqi", "عراقي"),
        ("Lebanese", "لبناني"),
        ("Jordanian", "أردني"),
        ("Egyptian", "مصري"),
        ("Other", "أخرى"),
    ]

    def __init__(self, db: Database, i18n: I18n, person: Person = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.person = person
        self.validation = ValidationService()
        self._id_document_image_path = None

        self.setWindowTitle(i18n.t("edit_person") if person else i18n.t("add_person"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(650)
        self._setup_ui()

        if person:
            self._populate_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(16)

        # === Personal Information Group ===
        personal_group = QGroupBox("المعلومات الشخصية")
        personal_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: {Config.FONT_SIZE}pt;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 0 8px;
            }}
        """)
        personal_form = QFormLayout(personal_group)
        personal_form.setSpacing(10)

        # Arabic names
        self.first_name_ar = QLineEdit()
        self.first_name_ar.setPlaceholderText("الاسم الأول بالعربية")
        self._style_input(self.first_name_ar)
        personal_form.addRow("الاسم الأول *:", self.first_name_ar)

        self.father_name_ar = QLineEdit()
        self.father_name_ar.setPlaceholderText("اسم الأب بالعربية")
        self._style_input(self.father_name_ar)
        personal_form.addRow("اسم الأب *:", self.father_name_ar)

        self.mother_name_ar = QLineEdit()
        self.mother_name_ar.setPlaceholderText("اسم الأم بالعربية")
        self._style_input(self.mother_name_ar)
        personal_form.addRow("اسم الأم:", self.mother_name_ar)

        self.last_name_ar = QLineEdit()
        self.last_name_ar.setPlaceholderText("اسم العائلة بالعربية")
        self._style_input(self.last_name_ar)
        personal_form.addRow("اسم العائلة *:", self.last_name_ar)

        # Gender
        self.gender_combo = QComboBox()
        for code, en, ar in Vocabularies.GENDERS:
            self.gender_combo.addItem(ar, code)
        personal_form.addRow("الجنس:", self.gender_combo)

        # Year of birth
        self.year_birth = QSpinBox()
        self.year_birth.setRange(1900, 2025)
        self.year_birth.setValue(1980)
        personal_form.addRow("سنة الميلاد:", self.year_birth)

        # Nationality
        self.nationality_combo = QComboBox()
        for code, ar in self.NATIONALITIES:
            self.nationality_combo.addItem(ar, code)
        personal_form.addRow("الجنسية:", self.nationality_combo)

        layout.addWidget(personal_group)

        # === Contact Information Group ===
        contact_group = QGroupBox("معلومات الاتصال")
        contact_group.setStyleSheet(personal_group.styleSheet())
        contact_form = QFormLayout(contact_group)
        contact_form.setSpacing(10)

        # Phone number
        phone_container = QWidget()
        phone_layout = QVBoxLayout(phone_container)
        phone_layout.setContentsMargins(0, 0, 0, 0)
        phone_layout.setSpacing(2)

        self.phone_number = QLineEdit()
        self.phone_number.setPlaceholderText("+963 11 XXXXXXX")
        self._style_input(self.phone_number)
        self.phone_number.textChanged.connect(self._validate_phone_live)
        phone_layout.addWidget(self.phone_number)

        self.phone_error = QLabel("")
        self.phone_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.phone_error.setVisible(False)
        phone_layout.addWidget(self.phone_error)

        contact_form.addRow("رقم الهاتف:", phone_container)

        # Mobile number
        self.mobile = QLineEdit()
        self.mobile.setPlaceholderText("+963 9XXXXXXXX")
        self._style_input(self.mobile)
        contact_form.addRow("رقم الجوال:", self.mobile)

        # Email
        email_container = QWidget()
        email_layout = QVBoxLayout(email_container)
        email_layout.setContentsMargins(0, 0, 0, 0)
        email_layout.setSpacing(2)

        self.email = QLineEdit()
        self.email.setPlaceholderText("example@domain.com")
        self._style_input(self.email)
        self.email.textChanged.connect(self._validate_email_live)
        email_layout.addWidget(self.email)

        self.email_error = QLabel("")
        self.email_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.email_error.setVisible(False)
        email_layout.addWidget(self.email_error)

        contact_form.addRow("البريد الإلكتروني:", email_container)

        # Address
        self.address = QLineEdit()
        self.address.setPlaceholderText("العنوان الكامل")
        self._style_input(self.address)
        contact_form.addRow("العنوان:", self.address)

        layout.addWidget(contact_group)

        # === ID Document Group ===
        id_group = QGroupBox("وثائق الهوية")
        id_group.setStyleSheet(personal_group.styleSheet())
        id_form = QFormLayout(id_group)
        id_form.setSpacing(10)

        # National ID (11 digits)
        nid_container = QWidget()
        nid_layout = QVBoxLayout(nid_container)
        nid_layout.setContentsMargins(0, 0, 0, 0)
        nid_layout.setSpacing(2)

        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("11 رقم")
        self.national_id.setMaxLength(11)
        self._style_input(self.national_id)
        nid_layout.addWidget(self.national_id)

        nid_hint = QLabel("الرقم الوطني السوري: 11 رقم")
        nid_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 10px;")
        nid_layout.addWidget(nid_hint)

        id_form.addRow("الرقم الوطني:", nid_container)

        # Passport number
        self.passport_number = QLineEdit()
        self.passport_number.setPlaceholderText("رقم جواز السفر")
        self._style_input(self.passport_number)
        id_form.addRow("رقم جواز السفر:", self.passport_number)

        # ID Document Type
        self.id_doc_type = QComboBox()
        for code, ar in self.ID_DOCUMENT_TYPES:
            self.id_doc_type.addItem(ar, code)
        self.id_doc_type.currentIndexChanged.connect(self._on_id_doc_type_changed)
        id_form.addRow("نوع وثيقة إضافية:", self.id_doc_type)

        # ID Document Number
        doc_num_container = QWidget()
        doc_num_layout = QVBoxLayout(doc_num_container)
        doc_num_layout.setContentsMargins(0, 0, 0, 0)
        doc_num_layout.setSpacing(2)

        self.id_doc_number = QLineEdit()
        self.id_doc_number.setPlaceholderText("رقم الوثيقة")
        self._style_input(self.id_doc_number)
        self.id_doc_number.setEnabled(False)
        doc_num_layout.addWidget(self.id_doc_number)

        self.id_doc_error = QLabel("")
        self.id_doc_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.id_doc_error.setVisible(False)
        doc_num_layout.addWidget(self.id_doc_error)

        id_form.addRow("رقم الوثيقة:", doc_num_container)

        # ID Document Image
        img_container = QWidget()
        img_layout = QHBoxLayout(img_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(8)

        self.id_doc_image_label = QLabel("لم يتم اختيار صورة")
        self.id_doc_image_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 11px;")
        img_layout.addWidget(self.id_doc_image_label)

        self.id_doc_image_btn = QPushButton("اختر صورة...")
        self.id_doc_image_btn.setEnabled(False)
        self.id_doc_image_btn.clicked.connect(self._select_id_image)
        self.id_doc_image_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                background: #F8FAFC;
            }
            QPushButton:hover {
                background: #E2E8F0;
            }
            QPushButton:disabled {
                color: #94A3B8;
            }
        """)
        img_layout.addWidget(self.id_doc_image_btn)
        img_layout.addStretch()

        id_form.addRow("صورة الوثيقة:", img_container)

        layout.addWidget(id_group)

        # === Status Flags ===
        flags_layout = QHBoxLayout()
        self.is_contact = QCheckBox("شخص الاتصال")
        self.is_deceased = QCheckBox("متوفى")
        flags_layout.addWidget(self.is_contact)
        flags_layout.addWidget(self.is_deceased)
        flags_layout.addStretch()
        layout.addLayout(flags_layout)

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Validation error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"""
            color: {Config.ERROR_COLOR};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 6px;
            padding: 8px;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _style_input(self, widget):
        """Apply consistent style to input widgets."""
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
            }}
            QLineEdit:disabled {{
                background-color: #E2E8F0;
            }}
        """)

    def _on_id_doc_type_changed(self):
        """Enable/disable document fields based on type selection."""
        has_type = bool(self.id_doc_type.currentData())
        self.id_doc_number.setEnabled(has_type)
        self.id_doc_image_btn.setEnabled(has_type)
        if not has_type:
            self.id_doc_number.clear()
            self.id_doc_error.setVisible(False)
            self._id_document_image_path = None
            self.id_doc_image_label.setText("لم يتم اختيار صورة")

    def _select_id_image(self):
        """Open file dialog to select ID document image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر صورة الوثيقة",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.pdf)"
        )
        if file_path:
            self._id_document_image_path = file_path
            # Show just filename
            import os
            filename = os.path.basename(file_path)
            self.id_doc_image_label.setText(filename)
            self.id_doc_image_label.setStyleSheet("color: #059669; font-size: 11px;")

    def _validate_phone_live(self):
        """Live validation for phone number."""
        phone = self.phone_number.text().strip()
        if phone and not self._is_valid_phone(phone):
            self.phone_error.setText("صيغة غير صحيحة (أرقام و + فقط)")
            self.phone_error.setVisible(True)
            self._set_input_error(self.phone_number, True)
        else:
            self.phone_error.setVisible(False)
            self._set_input_error(self.phone_number, False)

    def _validate_email_live(self):
        """Live validation for email."""
        email = self.email.text().strip()
        if email and not self._is_valid_email(email):
            self.email_error.setText("صيغة غير صحيحة (مثال: name@domain.com)")
            self.email_error.setVisible(True)
            self._set_input_error(self.email, True)
        else:
            self.email_error.setVisible(False)
            self._set_input_error(self.email, False)

    def _set_input_error(self, widget, has_error: bool):
        """Set error styling on input widget."""
        if has_error:
            widget.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #FEF2F2;
                    border: 2px solid #DC2626;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 13px;
                }}
            """)
        else:
            self._style_input(widget)

    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format (digits and optional +)."""
        # Allow digits, spaces, dashes, and optional + at start
        pattern = r'^\+?[\d\s\-]{6,20}$'
        return bool(re.match(pattern, phone))

    def _is_valid_email(self, email: str) -> bool:
        """Validate email format (contains @ and a dot)."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _populate_data(self):
        """Populate form with existing person data."""
        if not self.person:
            return

        self.first_name_ar.setText(self.person.first_name_ar or "")
        self.father_name_ar.setText(self.person.father_name_ar or "")
        self.mother_name_ar.setText(self.person.mother_name_ar or "")
        self.last_name_ar.setText(self.person.last_name_ar or "")

        idx = self.gender_combo.findData(self.person.gender)
        if idx >= 0:
            self.gender_combo.setCurrentIndex(idx)

        if self.person.year_of_birth:
            self.year_birth.setValue(self.person.year_of_birth)

        # Nationality
        idx = self.nationality_combo.findData(self.person.nationality)
        if idx >= 0:
            self.nationality_combo.setCurrentIndex(idx)

        # Contact info
        self.phone_number.setText(self.person.phone_number or "")
        self.mobile.setText(self.person.mobile_number or "")
        self.email.setText(self.person.email or "")
        self.address.setText(self.person.address or "")

        # ID documents
        self.national_id.setText(self.person.national_id or "")
        self.passport_number.setText(self.person.passport_number or "")

        # Flags
        self.is_contact.setChecked(self.person.is_contact_person)
        self.is_deceased.setChecked(self.person.is_deceased)

    def _on_save(self):
        """Validate and save."""
        errors = []

        # Validate required Arabic names
        if not self.first_name_ar.text().strip():
            errors.append("الاسم الأول مطلوب")
        if not self.father_name_ar.text().strip():
            errors.append("اسم الأب مطلوب")
        if not self.last_name_ar.text().strip():
            errors.append("اسم العائلة مطلوب")

        # Validate national ID (11 digits)
        nid = self.national_id.text().strip()
        if nid and (not nid.isdigit() or len(nid) != 11):
            errors.append("الرقم الوطني يجب أن يكون 11 رقم")

        # Validate phone number
        phone = self.phone_number.text().strip()
        if phone and not self._is_valid_phone(phone):
            errors.append("رقم الهاتف غير صحيح")

        # Validate email
        email = self.email.text().strip()
        if email and not self._is_valid_email(email):
            errors.append("البريد الإلكتروني غير صحيح")

        # Validate ID document - number required if type selected
        id_doc_type = self.id_doc_type.currentData()
        id_doc_number = self.id_doc_number.text().strip()
        if id_doc_type and not id_doc_number:
            errors.append("رقم الوثيقة مطلوب عند اختيار نوع الوثيقة")
            self.id_doc_error.setText("مطلوب")
            self.id_doc_error.setVisible(True)
        else:
            self.id_doc_error.setVisible(False)

        if errors:
            self.error_label.setText(" • ".join(errors))
            self.error_label.setVisible(True)
            return

        self.error_label.setVisible(False)
        self.accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        return {
            "first_name_ar": self.first_name_ar.text().strip(),
            "first_name": self.first_name_ar.text().strip(),  # Fallback
            "father_name_ar": self.father_name_ar.text().strip(),
            "father_name": self.father_name_ar.text().strip(),
            "mother_name_ar": self.mother_name_ar.text().strip(),
            "mother_name": self.mother_name_ar.text().strip(),
            "last_name_ar": self.last_name_ar.text().strip(),
            "last_name": self.last_name_ar.text().strip(),
            "gender": self.gender_combo.currentData(),
            "year_of_birth": self.year_birth.value(),
            "nationality": self.nationality_combo.currentData(),
            "national_id": self.national_id.text().strip() or None,
            "passport_number": self.passport_number.text().strip() or None,
            "phone_number": self.phone_number.text().strip() or None,
            "mobile_number": self.mobile.text().strip() or None,
            "email": self.email.text().strip() or None,
            "address": self.address.text().strip() or None,
            "is_contact_person": self.is_contact.isChecked(),
            "is_deceased": self.is_deceased.isChecked(),
        }


class PersonsPage(QWidget):
    """Persons management page."""

    view_person = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.person_repo = PersonRepository(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel(self.i18n.t("persons"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Add person button
        add_btn = QPushButton("+ " + self.i18n.t("add_person"))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #219A52;
            }}
        """)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_person)
        header_layout.addWidget(add_btn)

        layout.addLayout(header_layout)

        # Filters
        filters_frame = QFrame()
        filters_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        filters_frame.setGraphicsEffect(shadow)

        filters_layout = QHBoxLayout(filters_frame)
        filters_layout.setContentsMargins(24, 20, 24, 20)
        filters_layout.setSpacing(20)

        # Name search
        self.name_search = QLineEdit()
        self.name_search.setPlaceholderText("بحث بالاسم...")
        self.name_search.setMinimumWidth(200)
        self.name_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        self.name_search.textChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.name_search)

        # National ID search
        self.nid_search = QLineEdit()
        self.nid_search.setPlaceholderText("الرقم الوطني...")
        self.nid_search.setMaximumWidth(150)
        self.nid_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        self.nid_search.textChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.nid_search)

        # Gender filter
        self.gender_combo = QComboBox()
        self.gender_combo.addItem(self.i18n.t("all"), "")
        for code, en, ar in Vocabularies.GENDERS:
            self.gender_combo.addItem(ar, code)
        self.gender_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.gender_combo)

        filters_layout.addStretch()
        layout.addWidget(filters_frame)

        # Results count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.count_label)

        # Table
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        table_shadow = QGraphicsDropShadowEffect()
        table_shadow.setBlurRadius(20)
        table_shadow.setColor(QColor(0, 0, 0, 20))
        table_shadow.setOffset(0, 4)
        table_frame.setGraphicsEffect(table_shadow)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
                border-radius: 12px;
            }}
            QTableView::item {{
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)
        self.table.doubleClicked.connect(self._on_row_double_click)

        self.table_model = PersonsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        table_layout.addWidget(self.table)
        layout.addWidget(table_frame)

    def refresh(self, data=None):
        """Refresh the persons list."""
        logger.debug("Refreshing persons page")
        self._load_persons()

    def _load_persons(self):
        """Load persons with filters."""
        name = self.name_search.text().strip()
        nid = self.nid_search.text().strip()
        gender = self.gender_combo.currentData()

        persons = self.person_repo.search(
            name=name or None,
            national_id=nid or None,
            gender=gender or None,
            limit=500
        )

        self.table_model.set_persons(persons)
        self.count_label.setText(f"تم العثور على {len(persons)} شخص")

    def _on_filter_changed(self):
        self._load_persons()

    def _on_row_double_click(self, index):
        person = self.table_model.get_person(index.row())
        if person:
            self._edit_person(person)

    def _on_add_person(self):
        """Add new person."""
        dialog = PersonDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            person = Person(**data)

            try:
                self.person_repo.create(person)
                Toast.show_toast(self, "تم إضافة الشخص بنجاح", Toast.SUCCESS)
                self._load_persons()
            except Exception as e:
                logger.error(f"Failed to create person: {e}")
                Toast.show_toast(self, f"فشل في إضافة الشخص: {str(e)}", Toast.ERROR)

    def _edit_person(self, person: Person):
        """Edit existing person."""
        dialog = PersonDialog(self.db, self.i18n, person=person, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(person, key, value)

            try:
                self.person_repo.update(person)
                Toast.show_toast(self, "تم تحديث بيانات الشخص بنجاح", Toast.SUCCESS)
                self._load_persons()
            except Exception as e:
                logger.error(f"Failed to update person: {e}")
                Toast.show_toast(self, f"فشل في تحديث البيانات: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        self.table_model.set_language(is_arabic)
