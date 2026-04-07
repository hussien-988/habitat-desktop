# -*- coding: utf-8 -*-
"""Persons management page with animated card layout, DarkHeaderZone, and CRUD."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QFileDialog,
    QAbstractItemView, QGraphicsDropShadowEffect, QCheckBox,
    QGroupBox, QScrollArea, QStackedWidget, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QModelIndex, QTimer, QPropertyAnimation, QEasingCurve
)
from PyQt5.QtGui import QColor, QCursor, QFont
import re

from app.config import Config
from services.translation_manager import tr, get_layout_direction
from services.vocab_service import get_options as vocab_get_options
from repositories.database import Database
from controllers.person_controller import PersonController, PersonFilter
from models.person import Person
from services.api_worker import ApiWorker
from services.validation_service import ValidationService
from ui.components.toast import Toast
from ui.components.base_table_model import BaseTableModel
from ui.components.animated_card import AnimatedCard, EmptyStateAnimated, animate_card_entrance
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonsTableModel(BaseTableModel):
    """Table model for persons."""

    def __init__(self, is_arabic: bool = True):
        columns = [
            ('full_name', "Name", tr("table.persons.name")),
            ('father_name', "Father Name", tr("table.persons.father_name")),
            ('national_id', "National ID", tr("table.persons.national_id")),
            ('nationality', "Nationality", tr("table.persons.nationality")),
            ('gender', "Gender", tr("table.persons.gender")),
            ('phone', "Phone", tr("table.persons.phone")),
            ('email', "Email", tr("table.persons.email")),
        ]
        super().__init__(items=[], columns=columns)
        self._is_arabic = is_arabic

    def get_item_value(self, item, field_name: str):
        """Extract field value from person object."""
        if field_name == 'full_name':
            return item.full_name_ar if self._is_arabic else item.full_name
        elif field_name == 'father_name':
            return item.father_name_ar if self._is_arabic else item.father_name
        elif field_name == 'gender':
            return item.gender_display_ar if self._is_arabic else item.gender_display
        elif field_name == 'phone':
            return item.phone_number or item.mobile_number or "-"
        return getattr(item, field_name, None) or "-"

    def set_persons(self, persons: list):
        self.set_items(persons)

    def get_person(self, row: int):
        return self.get_item(row)


class PersonDialog(QDialog):
    """Dialog for creating/editing a person."""

    # ID Document types (code, translation_key)
    ID_DOCUMENT_TYPES_KEYS = [
        ("", "page.persons.select_doc_type"),
        ("national_id_card", "page.persons.doc_national_id_card"),
        ("passport", "page.persons.doc_passport"),
        ("family_booklet", "page.persons.doc_family_booklet"),
        ("birth_certificate", "page.persons.doc_birth_certificate"),
        ("driver_license", "page.persons.doc_driver_license"),
        ("other", "page.persons.doc_other"),
    ]

    # Nationality options (code, translation_key)
    NATIONALITY_KEYS = [
        ("Syrian", "page.persons.nat_syrian"),
        ("Palestinian", "page.persons.nat_palestinian"),
        ("Iraqi", "page.persons.nat_iraqi"),
        ("Lebanese", "page.persons.nat_lebanese"),
        ("Jordanian", "page.persons.nat_jordanian"),
        ("Egyptian", "page.persons.nat_egyptian"),
        ("Other", "page.persons.nat_other"),
    ]

    def __init__(self, db: Database, i18n: I18n, person: Person = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.person = person
        self.validation = ValidationService()
        self._id_document_image_path = None

        self.setWindowTitle(tr("dialog.persons.edit_title") if person else tr("dialog.persons.add_title"))
        self.setMinimumWidth(ScreenScale.w(600))
        self.setMinimumHeight(ScreenScale.h(650))
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
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(16)
        personal_group = QGroupBox(tr("page.persons.personal_info"))
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
        self.first_name_ar.setPlaceholderText(tr("page.persons.placeholder_first_name"))
        self._style_input(self.first_name_ar)
        personal_form.addRow(tr("page.persons.first_name_label"), self.first_name_ar)

        self.father_name_ar = QLineEdit()
        self.father_name_ar.setPlaceholderText(tr("page.persons.placeholder_father_name"))
        self._style_input(self.father_name_ar)
        personal_form.addRow(tr("page.persons.father_name_label"), self.father_name_ar)

        self.mother_name_ar = QLineEdit()
        self.mother_name_ar.setPlaceholderText(tr("page.persons.placeholder_mother_name"))
        self._style_input(self.mother_name_ar)
        personal_form.addRow(tr("page.persons.mother_name_label"), self.mother_name_ar)

        self.last_name_ar = QLineEdit()
        self.last_name_ar.setPlaceholderText(tr("page.persons.placeholder_last_name"))
        self._style_input(self.last_name_ar)
        personal_form.addRow(tr("page.persons.last_name_label"), self.last_name_ar)

        # Gender
        self.gender_combo = QComboBox()
        for code, label in vocab_get_options("Gender"):
            self.gender_combo.addItem(label, code)
        personal_form.addRow(tr("page.persons.gender_label"), self.gender_combo)

        # Year of birth
        self.year_birth = QSpinBox()
        self.year_birth.setRange(1900, 2025)
        self.year_birth.setValue(1980)
        personal_form.addRow(tr("page.persons.year_of_birth_label"), self.year_birth)

        # Nationality
        self.nationality_combo = QComboBox()
        for code, key in self.NATIONALITY_KEYS:
            self.nationality_combo.addItem(tr(key), code)
        personal_form.addRow(tr("page.persons.nationality_label"), self.nationality_combo)

        layout.addWidget(personal_group)
        contact_group = QGroupBox(tr("page.persons.contact_info"))
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

        contact_form.addRow(tr("page.persons.phone_label"), phone_container)

        # Mobile number
        self.mobile = QLineEdit()
        self.mobile.setPlaceholderText("+963 9XXXXXXXX")
        self._style_input(self.mobile)
        contact_form.addRow(tr("page.persons.mobile_label"), self.mobile)

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

        contact_form.addRow(tr("page.persons.email_label"), email_container)

        # Address
        self.address = QLineEdit()
        self.address.setPlaceholderText(tr("page.persons.placeholder_address"))
        self._style_input(self.address)
        contact_form.addRow(tr("page.persons.address_label"), self.address)

        layout.addWidget(contact_group)
        id_group = QGroupBox(tr("page.persons.id_documents"))
        id_group.setStyleSheet(personal_group.styleSheet())
        id_form = QFormLayout(id_group)
        id_form.setSpacing(10)

        # National ID (11 digits)
        nid_container = QWidget()
        nid_layout = QVBoxLayout(nid_container)
        nid_layout.setContentsMargins(0, 0, 0, 0)
        nid_layout.setSpacing(2)

        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText(tr("page.persons.placeholder_national_id"))
        self.national_id.setMaxLength(11)
        self._style_input(self.national_id)
        nid_layout.addWidget(self.national_id)

        nid_hint = QLabel(tr("page.persons.national_id_hint"))
        nid_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 10px;")
        nid_layout.addWidget(nid_hint)

        id_form.addRow(tr("page.persons.national_id_label"), nid_container)

        # Passport number
        self.passport_number = QLineEdit()
        self.passport_number.setPlaceholderText(tr("page.persons.placeholder_passport"))
        self._style_input(self.passport_number)
        id_form.addRow(tr("page.persons.passport_label"), self.passport_number)

        # ID Document Type
        self.id_doc_type = QComboBox()
        for code, key in self.ID_DOCUMENT_TYPES_KEYS:
            self.id_doc_type.addItem(tr(key), code)
        self.id_doc_type.currentIndexChanged.connect(self._on_id_doc_type_changed)
        id_form.addRow(tr("page.persons.additional_doc_type_label"), self.id_doc_type)

        # ID Document Number
        doc_num_container = QWidget()
        doc_num_layout = QVBoxLayout(doc_num_container)
        doc_num_layout.setContentsMargins(0, 0, 0, 0)
        doc_num_layout.setSpacing(2)

        self.id_doc_number = QLineEdit()
        self.id_doc_number.setPlaceholderText(tr("page.persons.placeholder_doc_number"))
        self._style_input(self.id_doc_number)
        self.id_doc_number.setEnabled(False)
        doc_num_layout.addWidget(self.id_doc_number)

        self.id_doc_error = QLabel("")
        self.id_doc_error.setStyleSheet("color: #DC2626; font-size: 10px;")
        self.id_doc_error.setVisible(False)
        doc_num_layout.addWidget(self.id_doc_error)

        id_form.addRow(tr("page.persons.doc_number_label"), doc_num_container)

        # ID Document Image
        img_container = QWidget()
        img_layout = QHBoxLayout(img_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(8)

        self.id_doc_image_label = QLabel(tr("page.persons.no_image_selected"))
        self.id_doc_image_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 11px;")
        img_layout.addWidget(self.id_doc_image_label)

        self.id_doc_image_btn = QPushButton(tr("page.persons.select_image"))
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

        id_form.addRow(tr("page.persons.doc_image_label"), img_container)

        layout.addWidget(id_group)
        flags_layout = QHBoxLayout()
        self.is_contact = QCheckBox(tr("page.persons.is_contact_person"))
        self.is_deceased = QCheckBox(tr("page.persons.is_deceased"))
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

        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr("button.save"))
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
            self.id_doc_image_label.setText(tr("page.persons.no_image_selected"))

    def _select_id_image(self):
        """Open file dialog to select ID document image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("page.persons.select_doc_image_title"),
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
            self.phone_error.setText(tr("page.persons.error_phone_format"))
            self.phone_error.setVisible(True)
            self._set_input_error(self.phone_number, True)
        else:
            self.phone_error.setVisible(False)
            self._set_input_error(self.phone_number, False)

    def _validate_email_live(self):
        """Live validation for email."""
        email = self.email.text().strip()
        if email and not self._is_valid_email(email):
            self.email_error.setText(tr("page.persons.error_email_format"))
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
            errors.append(tr("page.persons.error_first_name_required"))
        if not self.father_name_ar.text().strip():
            errors.append(tr("page.persons.error_father_name_required"))
        if not self.last_name_ar.text().strip():
            errors.append(tr("page.persons.error_last_name_required"))

        # Validate national ID (11 digits)
        nid = self.national_id.text().strip()
        if nid and (not nid.isdigit() or len(nid) != 11):
            errors.append(tr("page.persons.error_national_id_format"))

        # Validate phone number
        phone = self.phone_number.text().strip()
        if phone and not self._is_valid_phone(phone):
            errors.append(tr("page.persons.error_phone_invalid"))

        # Validate email
        email = self.email.text().strip()
        if email and not self._is_valid_email(email):
            errors.append(tr("page.persons.error_email_invalid"))

        # Validate ID document - number required if type selected
        id_doc_type = self.id_doc_type.currentData()
        id_doc_number = self.id_doc_number.text().strip()
        if id_doc_type and not id_doc_number:
            errors.append(tr("page.persons.error_doc_number_required"))
            self.id_doc_error.setText(tr("page.persons.required"))
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


# ---------------------------------------------------------------------------
#  Styles
# ---------------------------------------------------------------------------

_DARK_INPUT_STYLE = """
    QLineEdit {
        background: rgba(10, 22, 40, 140);
        color: white;
        border: 1px solid rgba(56, 144, 223, 35);
        border-radius: 8px;
        padding: 0 12px 0 12px;
    }
    QLineEdit:focus {
        border: 1.5px solid rgba(56, 144, 223, 140);
        background: rgba(10, 22, 40, 180);
    }
    QLineEdit::placeholder {
        color: rgba(139, 172, 200, 130);
    }
"""

_ADD_BTN_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
        color: white;
        border: 1px solid rgba(120, 190, 255, 0.35);
        border-radius: 10px;
        padding: 0 24px;
        font-weight: 700;
        font-size: 13pt;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.55);
    }
    QPushButton:pressed {
        background: #2E7BD6;
    }
    QPushButton:disabled {
        background: rgba(56, 144, 223, 0.35);
        color: rgba(255, 255, 255, 0.5);
    }
"""

_NAV_BTN_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #FAFBFF, stop:1 #F0F4FA);
        border: 1px solid rgba(56, 144, 223, 0.20);
        border-radius: 8px; color: #3890DF;
        padding: 0 10px; font-weight: 600;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #EBF5FF, stop:1 #E0EDFA);
        border-color: rgba(56, 144, 223, 0.40);
    }
    QPushButton:pressed {
        background: #E0EDFA;
    }
    QPushButton:disabled {
        color: #C0C8D0;
        background: #F5F7FA;
        border-color: #E8ECF0;
    }
"""


# ---------------------------------------------------------------------------
#  _PersonCard
# ---------------------------------------------------------------------------

class _PersonCard(AnimatedCard):
    """Person card showing name, father, ID, gender, contact."""

    _GENDER_COLORS = {
        "male": "#3890DF",
        "female": "#EC4899",
        "unknown": "#9CA3AF",
    }
    _GENDER_STYLES = {
        "male": {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
        "female": {"bg": "#FDF2F8", "fg": "#9D174D", "border": "#F9A8D4"},
        "unknown": {"bg": "#F3F4F6", "fg": "#6B7280", "border": "#D1D5DB"},
    }

    def __init__(self, person, is_arabic=True, parent=None):
        self._person = person
        self._is_arabic = is_arabic
        gender_key = self._get_gender_key(person)
        color = self._GENDER_COLORS.get(gender_key, "#9CA3AF")
        super().__init__(parent, card_height=100, status_color=color)

    def _get_gender_key(self, person):
        g = getattr(person, 'gender', None)
        if g is None:
            return "unknown"
        s = str(g).strip().lower()
        if s in ("male", "\u0630\u0643\u0631", "m", "1"):
            return "male"
        elif s in ("female", "\u0623\u0646\u062b\u0649", "f", "2"):
            return "female"
        return "unknown"

    def _build_content(self, layout):
        from PyQt5.QtWidgets import QHBoxLayout, QLabel
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        from ui.font_utils import create_font, FontManager
        from ui.design_system import Colors
        from services.translation_manager import tr

        p = self._person

        # Row 1: Full name + gender badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        name = p.full_name_ar if self._is_arabic else p.full_name
        name_label = QLabel(name or "-")
        name_label.setFont(create_font(size=13, weight=QFont.Bold))
        name_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        name_label.setMaximumWidth(ScreenScale.w(500))
        row1.addWidget(name_label)
        row1.addStretch()

        gender_key = self._get_gender_key(p)
        style = self._GENDER_STYLES.get(gender_key, self._GENDER_STYLES["unknown"])
        gender_text = p.gender_display_ar if self._is_arabic else (p.gender_display or "-")
        badge = QLabel(gender_text or "-")
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(22))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 11px; "
            f"padding: 0 10px; }}"
        )
        row1.addWidget(badge)
        layout.addLayout(row1)

        # Row 2: Father name + National ID
        parts = []
        father = p.father_name_ar if self._is_arabic else p.father_name
        if father:
            parts.append(f"{tr('table.persons.father_name')}: {father}")
        if p.national_id:
            parts.append(f"{tr('table.persons.national_id')}: {p.national_id}")
        details = QLabel(" \u2009\u00b7\u2009 ".join(parts) if parts else "-")
        details.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        details.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(details)

        # Row 3: Contact chips
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        chip_style = (
            "QLabel {{ background-color: {bg}; color: {fg}; "
            "border: 1px solid {border}; border-radius: 4px; "
            "padding: 2px 8px; }}"
        )
        phone = p.phone_number or p.mobile_number
        if phone:
            chip = QLabel(phone)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#F0F4FA", fg="#475569", border="#E2E8F0"))
            chips_row.addWidget(chip)
        if p.email:
            chip = QLabel(p.email)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#EEF2FF", fg="#4338CA", border="#E0E7FF"))
            chips_row.addWidget(chip)
        if p.nationality:
            chip = QLabel(p.nationality)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#F0FDF4", fg="#15803D", border="#DCFCE7"))
            chips_row.addWidget(chip)
        chips_row.addStretch()
        layout.addLayout(chips_row)

    def get_person(self):
        """Return the underlying Person object."""
        return self._person


# ---------------------------------------------------------------------------
#  PersonsPage
# ---------------------------------------------------------------------------

class PersonsPage(QWidget):
    """Persons management page with animated card layout."""

    view_person = pyqtSignal(str)

    _PAGE_SIZE = 20

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.person_controller = PersonController(db)

        self._card_widgets = []
        self._all_persons = []
        self._current_page = 1
        self._total_count = 0
        self._user_role = ""

        # Keep table model for backward compatibility
        self.table_model = PersonsTableModel(is_arabic=self.i18n.is_arabic())

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._load_persons)

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.persons.title"))

        # Stat pill
        self._stat_total = StatPill(tr("page.persons.total"))
        self._header.add_stat_pill(self._stat_total)

        # Add person button in header
        self.add_btn = QPushButton("+ " + tr("page.persons.add_new"))
        self.add_btn.setFixedHeight(ScreenScale.h(38))
        self.add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.add_btn.setFont(create_font(size=12, weight=QFont.Bold))
        self.add_btn.setStyleSheet(_ADD_BTN_STYLE)
        self.add_btn.clicked.connect(self._on_add_person)
        self._header.add_action_widget(self.add_btn)

        # Search field in header row 2
        self.name_search = QLineEdit()
        self.name_search.setPlaceholderText(tr("filter.persons.search_by_name"))
        self.name_search.setFixedSize(ScreenScale.w(280), ScreenScale.h(34))
        self.name_search.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self.name_search.setStyleSheet(_DARK_INPUT_STYLE)
        self.name_search.textChanged.connect(self._on_filter_changed)
        self._header.set_search_field(self.name_search)

        layout.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        layout.addWidget(self._accent_line)

        # Light content area
        self._content_wrapper = QWidget()
        self._content_wrapper.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        content_layout = QVBoxLayout(self._content_wrapper)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        content_layout.setSpacing(0)

        # Stacked widget: cards vs empty state
        self._stack = QStackedWidget()

        # Scroll area for cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)  # index 0

        # Empty state
        self._empty_state = EmptyStateAnimated(
            title=tr("page.persons.no_persons"),
            description=tr("page.persons.empty_description")
        )
        self._stack.addWidget(self._empty_state)  # index 1

        content_layout.addWidget(self._stack, 1)

        # Pagination
        self._pagination = self._create_pagination()
        content_layout.addWidget(self._pagination)

        layout.addWidget(self._content_wrapper, 1)

        # Loading spinner overlay
        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_pagination(self):
        """Build the pagination bar."""
        bar = QFrame()
        bar.setFixedHeight(ScreenScale.h(40))
        bar.setStyleSheet("QFrame { background: transparent; border: none; }")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 6, 4, 0)
        bar_layout.addStretch()

        self._prev_btn = QPushButton("\u276E")
        self._prev_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prev_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._prev_btn.clicked.connect(self._on_prev_page)
        bar_layout.addWidget(self._prev_btn)

        self._page_info = QLabel("")
        self._page_info.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._page_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._page_info.setAlignment(Qt.AlignCenter)
        self._page_info.setMinimumWidth(ScreenScale.w(80))
        bar_layout.addWidget(self._page_info)

        self._next_btn = QPushButton("\u276F")
        self._next_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._next_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._next_btn.clicked.connect(self._on_next_page)
        bar_layout.addWidget(self._next_btn)

        return bar

    # -- Public interface --

    def refresh(self, data=None):
        """Refresh the persons list."""
        logger.debug("Refreshing persons page")
        self._current_page = 1
        self._load_persons()

    def configure_for_role(self, role: str):
        """Enable/disable CRUD buttons based on user role."""
        self._user_role = role
        can_create = role in {"admin", "data_manager", "office_clerk", "field_researcher"}
        if hasattr(self, 'add_btn'):
            self.add_btn.setEnabled(can_create)

    # -- Data loading --

    def _load_persons(self):
        """Load persons with filters."""
        self._spinner.show_loading(tr("page.persons.loading_persons"))
        name = self.name_search.text().strip()

        filter_ = PersonFilter(
            full_name=name or None,
            limit=500
        )

        self._load_persons_worker = ApiWorker(self.person_controller.load_persons, filter_)
        self._load_persons_worker.finished.connect(self._on_load_persons_finished)
        self._load_persons_worker.error.connect(self._on_load_persons_error)
        self._load_persons_worker.start()

    def _on_load_persons_finished(self, result):
        self._spinner.hide_loading()
        if result.success:
            self._all_persons = result.data or []
            self._total_count = len(self._all_persons)
            self._stat_total.set_count(self._total_count)
            self.table_model.set_persons(self._all_persons)
            self._populate_cards()
        else:
            logger.error(f"Failed to load persons: {result.message}")
            Toast.show_toast(self, tr("page.persons.load_failed", error=result.message), Toast.ERROR)
            self._all_persons = []
            self._total_count = 0
            self._stat_total.set_count(0)
            self.table_model.set_persons([])
            self._populate_cards()

    def _on_load_persons_error(self, error_msg):
        self._spinner.hide_loading()
        logger.error(f"Failed to load persons: {error_msg}")
        Toast.show_toast(self, tr("page.persons.load_failed", error=error_msg), Toast.ERROR)
        self._all_persons = []
        self._total_count = 0
        self._stat_total.set_count(0)
        self.table_model.set_persons([])
        self._populate_cards()

    # -- Card population --

    def _populate_cards(self):
        """Populate card widgets from the current page slice of persons."""
        try:
            self._clear_cards()

            total = len(self._all_persons)
            if total == 0:
                self._stack.setCurrentIndex(1)
                self._empty_state.set_title(tr("page.persons.no_persons"))
                self._empty_state.set_description(tr("page.persons.empty_description"))
                self._update_pagination()
                return

            self._stack.setCurrentIndex(0)

            # Paginate
            ps = self._PAGE_SIZE
            total_pages = max(1, -(-total // ps))
            self._current_page = max(1, min(self._current_page, total_pages))
            start = (self._current_page - 1) * ps
            end = min(start + ps, total)
            page_persons = self._all_persons[start:end]

            is_arabic = self.i18n.is_arabic()
            for person in page_persons:
                card = _PersonCard(person, is_arabic=is_arabic, parent=self._scroll_content)
                card.clicked.connect(lambda p=person: self._edit_person(p))
                self._cards_layout.insertWidget(
                    self._cards_layout.count() - 1, card
                )
                self._card_widgets.append(card)

            self._update_pagination()
            self._animate_card_entrance()

            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()

        except Exception as e:
            logger.error(f"Error populating person cards: {e}")
            self._stack.setCurrentIndex(1)

    def _animate_card_entrance(self):
        """Stagger fade-in entrance for cards."""
        count = len(self._card_widgets)
        if count > 30 or count == 0:
            return

        for i, card in enumerate(self._card_widgets):
            from PyQt5.QtWidgets import QGraphicsOpacityEffect
            opacity_eff = QGraphicsOpacityEffect(card)
            opacity_eff.setOpacity(0.0)
            card.setGraphicsEffect(opacity_eff)

            anim = QPropertyAnimation(opacity_eff, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _restore_shadow(c=card):
                try:
                    s = QGraphicsDropShadowEffect(c)
                    s.setBlurRadius(20)
                    s.setOffset(0, 4)
                    s.setColor(QColor(0, 0, 0, 22))
                    c.setGraphicsEffect(s)
                except RuntimeError:
                    pass

            anim.finished.connect(_restore_shadow)
            QTimer.singleShot(i * 40, anim.start)

            card._entrance_anim = anim
            card._entrance_effect = opacity_eff

    def _clear_cards(self):
        """Remove all card widgets from the layout."""
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            if hasattr(card, '_entrance_anim') and card._entrance_anim:
                try:
                    card._entrance_anim.stop()
                except RuntimeError:
                    pass
            try:
                card.clicked.disconnect()
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_card_shimmer(self):
        """Repaint cards so shimmer animation progresses."""
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    # -- Pagination --

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._populate_cards()

    def _on_next_page(self):
        total_pages = max(1, -(-len(self._all_persons) // self._PAGE_SIZE))
        if self._current_page < total_pages:
            self._current_page += 1
            self._populate_cards()

    def _update_pagination(self):
        """Update pagination bar labels and button states."""
        total = len(self._all_persons)
        ps = self._PAGE_SIZE
        total_pages = max(1, -(-total // ps))
        page = self._current_page
        start = (page - 1) * ps + 1
        end = min(page * ps, total)
        if total > 0:
            self._page_info.setText(f"{start}-{end}  /  {total}")
        else:
            self._page_info.setText("")
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < total_pages)

    # -- Filter --

    def _on_filter_changed(self):
        self._current_page = 1
        self._search_timer.start()

    # -- Card click (edit) --

    def _on_card_clicked(self, person):
        """Handle card click to edit person."""
        if person:
            self._edit_person(person)

    # -- CRUD operations --

    def _on_add_person(self):
        """Add new person."""
        dialog = PersonDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            self.add_btn.setEnabled(False)
            self._spinner.show_loading(tr("page.persons.adding_person"))
            self._create_person_worker = ApiWorker(self.person_controller.create_person, data)
            self._create_person_worker.finished.connect(self._on_create_person_finished)
            self._create_person_worker.error.connect(self._on_create_person_error)
            self._create_person_worker.start()

    def _on_create_person_finished(self, result):
        self._spinner.hide_loading()
        self.add_btn.setEnabled(True)
        if result.success:
            Toast.show_toast(self, tr("page.persons.person_added"), Toast.SUCCESS)
            self._load_persons()
            if hasattr(result, 'duplicate_warning') and result.duplicate_warning:
                Toast.show_toast(self, tr("page.persons.duplicate_warning"), Toast.WARNING)
        else:
            error_msg = result.error or ""
            if tr("page.persons.already_registered_marker") in error_msg:
                from ui.error_handler import ErrorHandler
                ErrorHandler.show_warning(self, error_msg, tr("dialog.warning"))
            else:
                if hasattr(result, 'validation_errors') and result.validation_errors:
                    error_msg += "\n" + "\n".join(result.validation_errors)
                Toast.show_toast(self, tr("page.persons.add_failed", error=error_msg), Toast.ERROR)

    def _on_create_person_error(self, error_msg):
        self._spinner.hide_loading()
        self.add_btn.setEnabled(True)
        logger.error(f"Failed to create person: {error_msg}")
        Toast.show_toast(self, tr("page.persons.add_failed", error=error_msg), Toast.ERROR)

    def _edit_person(self, person: Person):
        """Edit existing person."""
        dialog = PersonDialog(self.db, self.i18n, person=person, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            self._spinner.show_loading(tr("page.persons.updating_person"))
            self._update_person_worker = ApiWorker(
                self.person_controller.update_person, person.person_id, data
            )
            self._update_person_worker.finished.connect(self._on_update_person_finished)
            self._update_person_worker.error.connect(self._on_update_person_error)
            self._update_person_worker.start()

    def _on_update_person_finished(self, result):
        self._spinner.hide_loading()
        if result.success:
            Toast.show_toast(self, tr("page.persons.person_updated"), Toast.SUCCESS)
            self._load_persons()
        else:
            error_msg = result.error
            if hasattr(result, 'validation_errors') and result.validation_errors:
                error_msg += "\n" + "\n".join(result.validation_errors)
            Toast.show_toast(self, tr("page.persons.update_failed", error=error_msg), Toast.ERROR)

    def _on_update_person_error(self, error_msg):
        self._spinner.hide_loading()
        logger.error(f"Failed to update person: {error_msg}")
        Toast.show_toast(self, tr("page.persons.update_failed", error=error_msg), Toast.ERROR)

    # -- Language --

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.persons.title"))
        self.add_btn.setText("+ " + tr("page.persons.add_new"))
        self.name_search.setPlaceholderText(tr("filter.persons.search_by_name"))
        self._stat_total.set_label(tr("page.persons.total"))
        self._empty_state.set_title(tr("page.persons.no_persons"))
        self._empty_state.set_description(tr("page.persons.empty_description"))
        self.table_model.set_language(is_arabic)
