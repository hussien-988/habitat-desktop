# -*- coding: utf-8 -*-
"""
Office Survey Wizard - UC-004 Complete Implementation.

Complete workflow for office-based property surveys including:
- Building identification and selection (with map integration)
- Property unit management (with uniqueness validation)
- Household/occupancy profiling (with adults/minors)
- Person registration (add/edit with validation)
- Relation and evidence capture (linked evidences)
- Claim creation
- Final review and submission
- Full persistence support
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, date
import uuid
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QTableView, QHeaderView,
    QAbstractItemView, QLineEdit, QComboBox, QSpinBox,
    QTextEdit, QListWidget, QListWidgetItem, QFormLayout,
    QGroupBox, QScrollArea, QSplitter, QMessageBox,
    QDialog, QFileDialog, QDateEdit, QCheckBox,
    QGraphicsDropShadowEffect, QRadioButton, QButtonGroup,
    QTabWidget, QGridLayout, QSizePolicy, QToolButton, QLayout,
    QMenu, QDoubleSpinBox, QSpacerItem
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QColor

from app.config import Config
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.unit_repository import UnitRepository
from repositories.person_repository import PersonRepository
from repositories.claim_repository import ClaimRepository
from repositories.survey_repository import SurveyRepository
from services.validation_service import ValidationService
from models.building import Building
from models.unit import PropertyUnit as Unit
from models.person import Person
from models.claim import Claim
from ui.components.toast import Toast
from ui.wizards.office_survey.dialogs import PersonDialog, EvidenceDialog
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

# Check for WebEngine availability
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBENGINE = False
    HAS_WEBCHANNEL = False


# ============================================================================
# Survey Context - Central data holder
# ============================================================================

class SurveyContext:
    """Holds all data for the current office survey session."""

    def __init__(self):
        self.survey_id = str(uuid.uuid4())
        self.status = "draft"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.clerk_id = None
        self.reference_number = self._generate_reference_number()

        # Selected entities
        self.building: Optional[Building] = None
        self.unit: Optional[Unit] = None
        self.is_new_unit = False
        self.new_unit_data: Optional[Dict] = None

        # Household data
        self.households: List[Dict] = []

        # Persons and relations
        self.persons: List[Dict] = []
        self.relations: List[Dict] = []

        # Claim
        self.claim_data: Optional[Dict] = None

    def _generate_reference_number(self) -> str:
        """Generate a reference number for the survey (Comment 1 in UC-004)."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        short_id = self.survey_id[:4].upper()
        return f"SRV-{timestamp}-{short_id}"

    def to_dict(self) -> Dict:
        """Serialize context to dictionary for persistence."""
        return {
            "survey_id": self.survey_id,
            "reference_number": self.reference_number,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "clerk_id": self.clerk_id,
            "building_id": self.building.building_id if self.building else None,
            "building_uuid": self.building.building_uuid if self.building else None,
            "unit_id": self.unit.unit_id if self.unit else None,
            "unit_uuid": self.unit.unit_uuid if self.unit else None,
            "is_new_unit": self.is_new_unit,
            "new_unit_data": self.new_unit_data,
            "households": self.households,
            "persons": self.persons,
            "relations": self.relations,
            "claim_data": self.claim_data
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SurveyContext':
        """Restore context from dictionary."""
        ctx = cls()
        ctx.survey_id = data.get("survey_id", ctx.survey_id)
        ctx.reference_number = data.get("reference_number", ctx.reference_number)
        ctx.status = data.get("status", "draft")
        ctx.clerk_id = data.get("clerk_id")
        ctx.is_new_unit = data.get("is_new_unit", False)
        ctx.new_unit_data = data.get("new_unit_data")
        ctx.households = data.get("households", [])
        ctx.persons = data.get("persons", [])
        ctx.relations = data.get("relations", [])
        ctx.claim_data = data.get("claim_data")
        return ctx


# ============================================================================
# Evidence Data Structure
# ============================================================================

class Evidence:
    """Evidence document linked to a relation."""

    def __init__(self, evidence_id: str = None):
        self.evidence_id = evidence_id or str(uuid.uuid4())
        self.document_type: str = "supporting_doc"
        self.document_number: Optional[str] = None
        self.issue_date: Optional[str] = None
        self.issuing_authority: Optional[str] = None
        self.file_path: Optional[str] = None
        self.file_name: Optional[str] = None
        self.notes: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "evidence_id": self.evidence_id,
            "document_type": self.document_type,
            "document_number": self.document_number,
            "issue_date": self.issue_date,
            "issuing_authority": self.issuing_authority,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "notes": self.notes
        }


# ============================================================================
# Add Evidence Dialog
# ============================================================================

# ============================================================================
# DEPRECATED: Dialogs moved to ui/wizards/office_survey/dialogs/
# Keeping as comments for reference during migration
# ============================================================================

"""
class AddEvidenceDialog(QDialog):
    # Dialog for adding evidence with full metadata.

    DOCUMENT_TYPES = [
        ("TAPU_GREEN", "صك ملكية (طابو أخضر)"),
        ("PROPERTY_REG", "بيان قيد عقاري"),
        ("COURT_RULING", "حكم قضائي"),
        ("SALE_NOTARIZED", "عقد بيع موثق"),
        ("SALE_INFORMAL", "عقد بيع غير موثق"),
        ("RENT_REGISTERED", "عقد إيجار مسجل"),
        ("RENT_INFORMAL", "عقد إيجار غير مسجل"),
        ("UTILITY_BILL", "فاتورة مرافق"),
        ("MUKHTAR_CERT", "شهادة المختار"),
        ("INHERITANCE", "حصر إرث"),
        ("WITNESS_STATEMENT", "إفادة شاهد"),
        ("OTHER", "أخرى"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_file = None
        self.setWindowTitle("إضافة دليل / وثيقة")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        # Document type
        self.type_combo = QComboBox()
        for code, ar in self.DOCUMENT_TYPES:
            self.type_combo.addItem(ar, code)
        form.addRow("نوع الوثيقة:", self.type_combo)

        # Document number
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("رقم الوثيقة (اختياري)")
        form.addRow("رقم الوثيقة:", self.number_edit)

        # Issue date
        self.issue_date = QDateEdit()
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDate(QDate.currentDate())
        self.issue_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("تاريخ الإصدار:", self.issue_date)

        # Issuing authority
        self.authority_edit = QLineEdit()
        self.authority_edit.setPlaceholderText("الجهة المصدرة")
        form.addRow("الجهة المصدرة:", self.authority_edit)

        layout.addLayout(form)

        # File selection
        file_frame = QGroupBox("ملف الوثيقة")
        file_layout = QHBoxLayout(file_frame)

        self.file_label = QLabel("لم يتم اختيار ملف")
        self.file_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        file_layout.addWidget(self.file_label)

        browse_btn = QPushButton("استعراض...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_frame)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("ملاحظات (اختياري)")
        self.notes_edit.setMaximumHeight(80)
        layout.addWidget(self.notes_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("إضافة")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف الوثيقة", "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.doc *.docx);;All Files (*)"
        )
        if file_path:
            self.selected_file = file_path
            from pathlib import Path
            self.file_label.setText(Path(file_path).name)
            self.file_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

    def get_evidence(self) -> Evidence:
        evidence = Evidence()
        evidence.document_type = self.type_combo.currentData()
        evidence.document_number = self.number_edit.text().strip() or None
        evidence.issue_date = self.issue_date.date().toString("yyyy-MM-dd")
        evidence.issuing_authority = self.authority_edit.text().strip() or None
        evidence.file_path = self.selected_file
        if self.selected_file:
            from pathlib import Path
            evidence.file_name = Path(self.selected_file).name
        evidence.notes = self.notes_edit.toPlainText().strip() or None
        return evidence
"""

# ============================================================================
# Person Dialog - DEPRECATED (moved to dialogs/)
# ============================================================================

"""
class PersonDialog(QDialog):
    """Dialog for adding/editing person information."""

    def __init__(self, parent=None, person_data: dict = None, households: list = None, existing_persons: list = None):
        super().__init__(parent)
        self.person_data = person_data
        self.households = households or []
        self.existing_persons = existing_persons or []
        self.editing_mode = person_data is not None

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
        """Setup dialog UI using GridLayout."""
        self.setLayoutDirection(Qt.RightToLeft)  # Set RTL for Arabic

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("تعديل بيانات الشخص" if self.editing_mode else "إضافة شخص جديد")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        #title.setAlignment(Qt.AlignRight)
        main_layout.addWidget(title)

        # Form Grid
        grid = QGridLayout()
        grid.setSpacing(15)

        # Label style - consistent right alignment
        label_style = "color: #555; font-weight: 600; font-size: 13px; text-align: right;"

        # Row 0: First Name | Last Name
        first_name_label = QLabel("الاسم الأول")
        first_name_label.setStyleSheet(label_style)
        #first_name_label.setAlignment(Qt.AlignRight)
        grid.addWidget(first_name_label, 0, 0)

        last_name_label = QLabel("الكنية")
        last_name_label.setStyleSheet(label_style)
        #last_name_label.setAlignment(Qt.AlignRight)
        grid.addWidget(last_name_label, 0, 1)

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("ادخل الاسم الاول")
        self.first_name.setStyleSheet(self._input_style())
        grid.addWidget(self.first_name, 1, 0)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("ادخل اسم العائلة")
        self.last_name.setStyleSheet(self._input_style())
        grid.addWidget(self.last_name, 1, 1)

        # Row 2: Mother Name | Father Name
        mother_name_label = QLabel("اسم الأم")
        mother_name_label.setStyleSheet(label_style)
       # mother_name_label.setAlignment(Qt.AlignRight)
        grid.addWidget(mother_name_label, 2, 0)

        father_name_label = QLabel("اسم الأب")
        father_name_label.setStyleSheet(label_style)
       # father_name_label.setAlignment(Qt.AlignRight)
        grid.addWidget(father_name_label, 2, 1)

        self.mother_name = QLineEdit()
        self.mother_name.setPlaceholderText("ادخل اسم الأم")
        self.mother_name.setStyleSheet(self._input_style())
        grid.addWidget(self.mother_name, 3, 0)

        self.father_name = QLineEdit()
        self.father_name.setPlaceholderText("ادخل اسم الاب")
        self.father_name.setStyleSheet(self._input_style())
        grid.addWidget(self.father_name, 3, 1)

        # Row 4: Birth Date | ID Number
        birth_date_label = QLabel("تاريخ الميلاد")
        birth_date_label.setStyleSheet(label_style)
       # birth_date_label.setAlignment(Qt.AlignRight)
        grid.addWidget(birth_date_label, 4, 0)

        national_id_label = QLabel("الرقم الوطني")
        national_id_label.setStyleSheet(label_style)
       # national_id_label.setAlignment(Qt.AlignRight)
        grid.addWidget(national_id_label, 4, 1)

        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate(1980, 1, 1))
        self.birth_date.setDisplayFormat("yyyy-MM-dd")
        self.birth_date.setStyleSheet(self._input_style())
        grid.addWidget(self.birth_date, 5, 0)

        # National ID with calendar button
        national_id_widget = QWidget()
        national_id_layout = QHBoxLayout(national_id_widget)
        national_id_layout.setContentsMargins(0, 0, 0, 0)
        national_id_layout.setSpacing(8)

        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("00000000000")
        self.national_id.setMaxLength(11)
        self.national_id.setStyleSheet(self._input_style())
        self.national_id.textChanged.connect(self._validate_national_id)

        calendar_btn = QPushButton("📅")
        calendar_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #e0e6ed;
                border-radius: 6px;
                padding: 10px;
                font-size: 16px;
            }
        """)

        national_id_layout.addWidget(self.national_id)
        national_id_layout.addWidget(calendar_btn)
        grid.addWidget(national_id_widget, 5, 1)

        # National ID status (spans both columns)
        self.national_id_status = QLabel("")
        self.national_id_status.setAlignment(Qt.AlignRight)
        grid.addWidget(self.national_id_status, 6, 0, 1, 2)

        # Row 7: Email | Relationship
        email_label = QLabel("البريد الالكتروني")
        email_label.setStyleSheet(label_style)
      #  email_label.setAlignment(Qt.AlignRight)
        grid.addWidget(email_label, 7, 0)

        relationship_label = QLabel("علاقة الشخص بوحدة العقار")
        relationship_label.setStyleSheet(label_style)
       # relationship_label.setAlignment(Qt.AlignRight)
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

        # Row 9: Phone | Mobile
        landline_label = QLabel("رقم الهاتف")
        landline_label.setStyleSheet(label_style)
        #landline_label.setAlignment(Qt.AlignRight)
        grid.addWidget(landline_label, 9, 0)

        mobile_label = QLabel("رقم الموبايل")
        mobile_label.setStyleSheet(label_style)
       # mobile_label.setAlignment(Qt.AlignRight)
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

        # Gender (hidden but kept for compatibility)
        self.gender = QComboBox()
        self.gender.addItem("ذكر", "male")
        self.gender.addItem("أنثى", "female")
        self.gender.hide()

        # Is contact person (hidden)
        self.is_contact = QCheckBox("شخص التواصل الرئيسي")
        self.is_contact.hide()

        # Upload Area
        upload_frame = QFrame()
        upload_frame.setObjectName("uploadArea")
        upload_frame.setStyleSheet("""
            QFrame#uploadArea {
                border: 2px dashed #d1d9e6;
                border-radius: 10px;
                background-color: #f0f4f8;
            }
        """)
        upload_frame.setFixedHeight(100)
        upload_layout = QVBoxLayout(upload_frame)
        upload_label = QLabel("📄  ارفع صور المستندات")
        #upload_label.setAlignment(Qt.AlignCenter)
        upload_label.setStyleSheet("color: #4a90e2; background: transparent; font-size: 14px; font-weight: bold;")
        upload_layout.addWidget(upload_label)
        main_layout.addWidget(upload_frame)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        save_btn = QPushButton("حفظ")
        save_btn.setObjectName("saveBtn")
        save_btn.setStyleSheet("""
            QPushButton#saveBtn {
                background-color: #4a90e2;
                color: white;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton#saveBtn:hover {
                background-color: #357ABD;
            }
        """)
        save_btn.clicked.connect(self._save_person)

        cancel_btn = QPushButton("الغاء")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setStyleSheet("""
            QPushButton#cancelBtn {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 12px;
                font-size: 16px;
            }
            QPushButton#cancelBtn:hover {
                background-color: #f5f5f5;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

    def _input_style(self):
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
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
        """

    def _validate_national_id(self):
        """Validate national ID."""
        nid = self.national_id.text().strip()

        if not nid:
            self.national_id_status.setText("")
            return True

        # Use ValidationService for format check
        format_result = self.parent().validation_service.validate_national_id(nid)
        if not format_result.is_valid:
            self.national_id_status.setText("⚠️ يجب أن يكون 11 رقم")
            self.national_id_status.setStyleSheet(f"color: {Config.WARNING_COLOR};")
            return False

        # Use ValidationService for uniqueness check
        exclude_id = self.person_data.get('person_id') if self.editing_mode and self.person_data else None
        is_unique = self.parent().validation_service.check_national_id_uniqueness(
            national_id=nid,
            existing_persons=self.existing_persons,
            exclude_person_id=exclude_id
        )

        if not is_unique:
            self.national_id_status.setText("❌ الرقم موجود مسبقاً")
            self.national_id_status.setStyleSheet(f"color: {Config.ERROR_COLOR};")
            return False

        self.national_id_status.setText("✅ الرقم متاح")
        self.national_id_status.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")
        return True

    def _load_person_data(self, person_data: dict):
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

    def get_person_data(self) -> dict:
        """Get person data from form."""
        return {
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
"""

# ============================================================================
# Main Wizard
# ============================================================================

class OfficeSurveyWizard(QWidget):
    """
    Office Survey Wizard implementing UC-004 at 100%.

    7 Stages:
    1. Building Search & Selection (with map)
    2. Property Unit Selection/Creation (with validation)
    3. Household/Occupancy Profiling (with adults/minors)
    4. Person Registration (add/edit)
    5. Relation & Evidence Capture (linked)
    6. Claim Creation
    7. Final Review & Submit
    """

    survey_completed = pyqtSignal(str)  # Emits survey_id
    survey_cancelled = pyqtSignal()
    survey_saved_draft = pyqtSignal(str)  # Emits survey_id

    STEP_BUILDING = 0
    STEP_UNIT = 1
    STEP_HOUSEHOLD = 2
    STEP_PERSONS = 3
    STEP_RELATIONS = 4
    STEP_CLAIM = 5
    STEP_REVIEW = 6

    STEP_NAMES = [
        ("1", "اختيار المبنى"),
        ("2", "الوحدة العقارية"),
        ("3", "الأسرة والإشغال"),
        ("4", "تسجيل الأشخاص"),
        ("5", "العلاقات والأدلة"),
        ("6", "إنشاء المطالبة"),
        ("7", "المراجعة النهائية"),
    ]

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n

        # Repositories
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self.person_repo = PersonRepository(db)
        self.claim_repo = ClaimRepository(db)
        self.survey_repo = SurveyRepository(db)

        # Services
        self.validation_service = ValidationService()

        # Survey context
        self.context = SurveyContext()
        self.current_step = 0

        # Edit tracking
        self._editing_person_index: Optional[int] = None

        # Map dialog (lazy initialization)
        self._map_dialog = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the wizard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        # Header (Matching the design in the image 100%)
        header_layout = QHBoxLayout()

        # UN-HABITAT Logo/Text placeholder (Matching image top left)
        logo_label = QLabel("اضافة حالة جديدة")
        # Assuming you have an actual logo image or can use a specific style
        logo_label.setStyleSheet("font-family: 'Noto Kufi Arabic';font-size: 13pt; font-weight: bold; color: #0000000;")
        header_layout.addWidget(logo_label)

        # ID Badge (Matching the design fh2999aa-7632-4ba5-b4f2-9dff1cab3943)
        # Using a dark blue background matching the image
        
        
        
        header_layout.addStretch() # Pushes remaining items to the right

        # Save button (Matching the blue button in the image)
        self.save_btn = QPushButton("حفظ")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR}; /* Use your primary color for blue background */
                color: white;
                border: none;
                padding: 12px 24px;
                font-weight: 600;
                border-radius: 8px;
            }}
        """)
        self.save_btn.clicked.connect(self._save_as_draft) # Connect to your existing save method
        header_layout.addWidget(self.save_btn)

        layout.addLayout(header_layout)

        # Step indicators frame - REMOVED COMPLETELY as requested
        # You should delete all the code related to steps_frame below this line


        # Step indicators
        steps_frame = QFrame()
        steps_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        steps_layout = QHBoxLayout(steps_frame)
        steps_layout.setSpacing(4)

        self.step_labels = []
        for num, name in self.STEP_NAMES:
            step_widget = QLabel(f" {num}. {name} ")
            step_widget.setAlignment(Qt.AlignCenter)
            step_widget.setStyleSheet(f"""
                background-color: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_LIGHT};
                padding: 6px 10px;
                border-radius: 12px;
                font-size: 9pt;
            """)
            self.step_labels.append(step_widget)
            steps_layout.addWidget(step_widget)

        steps_layout.addStretch()
        layout.addWidget(steps_frame)

        # Content area
        self.content_stack = QStackedWidget()

        # Create all step widgets
        self.content_stack.addWidget(self._create_building_step())  # 0
        self.content_stack.addWidget(self._create_unit_step())      # 1
        self.content_stack.addWidget(self._create_household_step()) # 2
        self.content_stack.addWidget(self._create_persons_step())   # 3
        self.content_stack.addWidget(self._create_relations_step()) # 4
        self.content_stack.addWidget(self._create_claim_step())     # 5
        self.content_stack.addWidget(self._create_review_step())    # 6

        layout.addWidget(self.content_stack)

        # Navigation buttons (Footer) - Matching the design in the image
        nav_layout = QHBoxLayout()

        # The stretch pushes buttons to the far left and far right
        nav_layout.addStretch() 

        self.prev_btn = QPushButton("→ السابق")
        # Style prev/next buttons similar to the 'Next' in your original code, as requested
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
                margin-right: 5px; /* Small gap between buttons */
            }}
        """)
        self.prev_btn.clicked.connect(self._on_previous)
        self.prev_btn.setEnabled(False) # This handles hiding/disabling on the first step
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("التالي ←")
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
        """)
        self.next_btn.clicked.connect(self._on_next)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

        # Update display (Remains the same)
        self._update_step_display()


    # ==================== Helper Methods ====================

    def _get_status_badge_style(self, status: str) -> tuple:
        """Get color and emoji for building status badge."""
        status_map = {
            "intact": ("#10B981", "🟢", "سليم"),
            "minor_damage": ("#F59E0B", "🟡", "ضرر بسيط"),
            "major_damage": ("#F97316", "🟠", "ضرر كبير"),
            "destroyed": ("#EF4444", "🔴", "مدمر"),
            "under_construction": ("#3B82F6", "🔵", "تحت الإنشاء")
        }
        return status_map.get(status, ("#6B7280", "⚪", status))

    def _create_metric_widget(self, label: str, value: str) -> QFrame:
        """Create a metric card widget with label and value."""
        metric_frame = QFrame()
        metric_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)

        metric_layout = QVBoxLayout(metric_frame)
        metric_layout.setSpacing(4)
        metric_layout.setContentsMargins(8, 8, 8, 8)
        metric_layout.setAlignment(Qt.AlignCenter)

        # Label
        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignCenter)
        label_widget.setStyleSheet("""
            font-size: 11px;
            color: #6B7280;
            font-weight: 500;
            border: none;
        """)
        metric_layout.addWidget(label_widget)

        # Value
        value_widget = QLabel(value)
        value_widget.setAlignment(Qt.AlignCenter)
        value_widget.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {Config.PRIMARY_COLOR};
            border: none;
        """)
        metric_layout.addWidget(value_widget)

        return metric_frame

    # ==================== Step 1: Building Selection (S01-S03) ====================

    def _create_building_step(self) -> QWidget:
        """Create Step 1: Building Search and Selection (New UI)"""
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

    # ===== Card: Building Data =====
        card = QFrame()
        card.setObjectName("buildingCard")
        card.setStyleSheet("""
            QFrame#buildingCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card_layout.setSizeConstraint(QLayout.SetMinimumSize)
        # Header (title + subtitle)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(1)
        title = QLabel("بيانات البناء")
        title.setStyleSheet("background: transparent;font-family:'Noto Kufi Arabic'; font-size: 8pt; font-weight: 900; color:#1F2D3D;")
        subtitle = QLabel("ابحث عن معلومات البناء والموقع الجغرافي")
        subtitle.setStyleSheet("background: transparent;font-family:'Noto Kufi Arabic'; font-size: 8pt; color:#7F8C9B;")

        header_text_col.addWidget(title)
        header_text_col.addWidget(subtitle)

        icon_lbl = QLabel("📄")
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
                font-size: 16px;
            }
        """)

        header_row.addWidget(icon_lbl)
        header_row.addLayout(header_text_col)
        header_row.addStretch(1)

        card_layout.addLayout(header_row)


        # Label: building code
        code_label = QLabel("رمز البناء")
        code_label.setStyleSheet("background: transparent;font-family:'Noto Kufi Arabic'; font-size: 8pt; color:#1F2D3D; font-weight:800;")
        card_layout.addWidget(code_label)

        # One long input bar (search icon right + link left) - matches design
        # --- Search bar (one row) ---
        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setStyleSheet("""
            QFrame#searchBar {
                background-color: #F0F7FF;
                border: 1px solid #E6EEF8;
                border-radius: 18px;
            }
        """)
        search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(10,4, 10, 4)
        sb.setSpacing(8)
        # ✅ زر العدسة (يظهر داخل الحقل لأن الشريط نفسه هو الحقل)
        search_icon_btn = QToolButton()
        search_icon_btn.setText("🔍")
        search_icon_btn.setCursor(Qt.PointingHandCursor)
        search_icon_btn.setFixedSize(30, 30)
        search_icon_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #EEF6FF;
                border-radius: 8px;
            }
        """)
        search_icon_btn.clicked.connect(self._search_buildings)
                # Input
        self.building_search = QLineEdit()
        self.building_search.setPlaceholderText("ابحث عن رمز البناء ...")
        self.building_search.setLayoutDirection(Qt.RightToLeft)
        
        self.building_search.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-family: 'Noto Kufi Arabic';
                font-size: 10pt;
                padding: 0px 6px;
                min-height: 28px;
                color: #2C3E50;
                    }
        """)
        self.building_search.textChanged.connect(self._on_building_code_changed)
        self.building_search.returnPressed.connect(self._search_buildings)

        # Left link
        self.search_on_map_btn = QPushButton("بحث على الخريطة")
        self.search_on_map_btn.setCursor(Qt.PointingHandCursor)
        self.search_on_map_btn.setFlat(True)
        self.search_on_map_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #3890DF;
                font-family: 'Noto Kufi Arabic';
                font-weight: 600;
                font-size: 7pt;
                text-decoration: underline;
                padding: 0;
                margin-top: 1px;
            }
        """)
        self.search_on_map_btn.clicked.connect(self._open_map_search_dialog)



        # Search icon inside input (Action)
        sb.addWidget(self.search_on_map_btn)   # left
        sb.addWidget(self.building_search)  # middle (stretch)
        sb.addWidget(search_icon_btn,1)
        
        # Add bar to card 
        card_layout.addWidget(search_bar)


        # Suggestions list (dropdown look)
        self.buildings_list = QListWidget()
        self.buildings_list.setVisible(False)
        self.buildings_list.setMaximumHeight(170)
        self.buildings_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                background-color: #FFFFFF;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #F1F5F9;
                color: #2C3E50;
                font-family: 'Noto Kufi Arabic';
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #EFF6FF;
            }
        """)
        self.buildings_list.itemClicked.connect(self._on_building_selected)
        self.buildings_list.itemDoubleClicked.connect(self._on_building_confirmed)
        card_layout.addWidget(self.buildings_list)
    

        layout.addWidget(card)
        layout.addStretch(1)


    # ===== Selected building details (New UI blocks) =====
        self.selected_building_frame = QFrame()
        self.selected_building_frame.setObjectName("selectedBuildingFrame")
        self.selected_building_frame.setStyleSheet("""
            QFrame#selectedBuildingFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        self.selected_building_frame.hide()

        sb = QVBoxLayout(self.selected_building_frame)
        sb.setContentsMargins(14, 6, 14, 6)
        sb.setSpacing(12)

        # 1) General info line (arrow 1)
        info_bar = QFrame()
        info_bar.setStyleSheet("""
            QFrame {
                background-color: #F5FAFF;
                border: 1px solid #DCE7F5;
                border-radius: 10px;
            }
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(12, 10, 12, 10)

    
        self.selected_building_label = QLabel("")
        self.selected_building_label.setStyleSheet("color: #2C3E50; font-weight: 600;")
        self.selected_building_label.setWordWrap(True)

        info_icon = QLabel("🏢")
        info_icon.setStyleSheet("font-size: 16px; color: #3890DF;")
        info_layout.addWidget(info_icon)
        info_layout.addWidget(self.selected_building_label, stretch=1)

        sb.addWidget(info_bar)

        # 2) Stats row (arrow 2) - placeholders for now (نعبّيها بالخطوة الجاية)
        stats = QFrame()
        stats.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(12)

        def _stat_block(title_text, value_text="-"):
            box = QFrame()
            box.setStyleSheet("QFrame { background: transparent; }")
            v = QVBoxLayout(box)
            v.setSpacing(4)
            t = QLabel(title_text)
            t.setStyleSheet("font-size: 12px; color: #7F8C9B; font-weight: 600;")
            val = QLabel(value_text)
            val.setStyleSheet("font-size: 13px; color: #2C3E50; font-weight: 700;")
            v.addWidget(t, alignment=Qt.AlignHCenter)
            v.addWidget(val, alignment=Qt.AlignHCenter)
            return box, val

        box_status, self.ui_building_status = _stat_block("حالة البناء")
        box_type, self.ui_building_type = _stat_block("نوع البناء")
        box_units, self.ui_units_count = _stat_block("عدد الوحدات")
        box_parcels, self.ui_parcels_count = _stat_block("عدد المقاسم")
        box_shops, self.ui_shops_count = _stat_block("عدد المحلات")

        for b in [box_status, box_type, box_units, box_parcels, box_shops]:
            stats_layout.addWidget(b, stretch=1)

        sb.addWidget(stats)

        # 3) Location card with thumbnail (arrow 3) - UI فقط الآن
        loc = QFrame()
        loc.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)
        loc_layout = QHBoxLayout(loc)
        loc_layout.setContentsMargins(12, 12, 12, 12)
        loc_layout.setSpacing(12)

        loc_text_col = QVBoxLayout()
        loc_title = QLabel("موقع البناء")
        loc_title.setStyleSheet("font-size: 12px; color: #2C3E50; font-weight: 700;")
        loc_desc = QLabel("وصف الموقع")
        loc_desc.setStyleSheet("font-size: 12px; color: #7F8C9B;")
        loc_text_col.addWidget(loc_title)
        loc_text_col.addWidget(loc_desc)
        loc_text_col.addStretch()

        loc_layout.addLayout(loc_text_col, stretch=1)

        thumb_col = QVBoxLayout()
        self.map_thumbnail = QLabel("خريطة مصغّرة")
        self.map_thumbnail.setAlignment(Qt.AlignCenter)
        self.map_thumbnail.setFixedSize(280, 120)
        self.map_thumbnail.setStyleSheet("""
            QLabel {
                background-color: #F8FAFC;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                color: #7F8C9B;
            }
        """)

        self.open_map_btn = QPushButton("قم بفتح الخريطة")
        self.open_map_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #DCE7F5;
                border-radius: 10px;
                padding: 8px 10px;
                color: #3890DF;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #EEF6FF; }
        """)
    # منربطه بالخطوة الجاية (منطق)
        self.open_map_btn.setEnabled(False)

        thumb_col.addWidget(self.map_thumbnail)
        thumb_col.addWidget(self.open_map_btn, alignment=Qt.AlignLeft)
        loc_layout.addLayout(thumb_col)

        sb.addWidget(loc)

        layout.addWidget(self.selected_building_frame)

        # Load initial buildings (نفس القديم)
        self._load_buildings()
        return widget
    def _on_building_code_changed(self):
        """UI behavior: filter + show/hide suggestions"""
        text = self.building_search.text().strip()
    # فلترة نفس القديم
        self._filter_buildings()
    # إظهار الاقتراحات فقط وقت في نص
        self.buildings_list.setVisible(bool(text))

    def _open_map_search_dialog(self):
        """Open SIMPLIFIED modal dialog with interactive map for building selection.

        SIMPLIFIED: Single dialog, no nested frames/shadows - direct QWebEngineView rendering.
        """
        # Create dialog once and reuse it
        if self._map_dialog is None:
            self._map_dialog = QDialog(self)
            self._map_dialog.setModal(True)
            self._map_dialog.setWindowTitle("بحث على الخريطة - اختر مبنى من الخريطة")
            self._map_dialog.resize(900, 600)  # Larger and resizable!

            # SIMPLIFIED: Single layout - NO nested frames, NO shadows!
            layout = QVBoxLayout(self._map_dialog)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(10)

            # Simple title
            title = QLabel("🗺️ اضغط على علامة مبنى لاختياره")
            title.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    color: #2C3E50;
                    padding: 8px;
                    background-color: #E8F4F8;
                    border-radius: 6px;
                }
            """)
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)

            # PERFORMANCE FIX: Create QWebEngineView ONCE - DIRECT child of dialog!
            try:
                from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

                self.building_map = QWebEngineView(self._map_dialog)  # Direct parent!

                # Enable hardware acceleration
                settings = self.building_map.settings()
                settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
                settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

                # Setup QWebChannel for JavaScript-Python communication
                if HAS_WEBCHANNEL:
                    from PyQt5.QtCore import QObject, pyqtSlot

                    # Simple bridge for building selection
                    class BuildingMapBridge(QObject):
                        def __init__(self, parent=None):
                            super().__init__(parent)

                        @pyqtSlot(str)
                        def selectBuilding(self, building_id):
                            pass  # Not used in wizard, just for compatibility

                    self.building_map_bridge = BuildingMapBridge()
                    self.building_map_channel = QWebChannel(self.building_map.page())
                    self.building_map_channel.registerObject('buildingBridge', self.building_map_bridge)
                    self.building_map.page().setWebChannel(self.building_map_channel)

                # Add directly to layout - NO intermediate containers!
                layout.addWidget(self.building_map, stretch=1)

            except ImportError:
                placeholder = QLabel("🗺️ الخريطة غير متاحة (QtWebEngine غير مثبت)")
                placeholder.setAlignment(Qt.AlignCenter)
                placeholder.setStyleSheet("padding: 40px; color: #999;")
                layout.addWidget(placeholder)

            # Close button
            close_btn = QPushButton("إغلاق")
            close_btn.setFixedWidth(100)
            close_btn.clicked.connect(self._map_dialog.reject)
            close_btn.setStyleSheet("""
                QPushButton {
                    padding: 8px 16px;
                    background-color: #E74C3C;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #C0392B; }
            """)
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)

        # Load map HTML
        self._load_buildings_map()

        # Show dialog (blocking) - Qt handles painting automatically
        self._map_dialog.exec_()


    def _load_buildings_map(self):
        """Load interactive map for building selection (S02) - OFFLINE VERSION with RELATIVE URLs."""
        if not hasattr(self, "building_map") or self.building_map is None:
            # Map view is created inside the dialog, so nothing to load yet.
            return

        from services.tile_server_manager import get_tile_server_url
        from PyQt5.QtCore import QUrl

        tile_server_url = get_tile_server_url()

        # Prepare base URL with trailing slash for relative URL resolution
        if not tile_server_url.endswith('/'):
            tile_server_url += '/'
        base_url = QUrl(tile_server_url)

        # Get buildings with coordinates
        buildings = self.building_repo.get_all(limit=200)
        markers_js = ""

        # Helper function: get marker color based on building status
        def get_marker_color(status):
            """Return color based on building status."""
            status_colors = {
                'intact': '#28A745',       # أخضر - سليم
                'standing': '#28A745',     # أخضر - سليم
                'damaged': '#FFC107',      # أصفر - متضرر
                'partially_damaged': '#FF9800',  # برتقالي - متضرر جزئياً
                'severely_damaged': '#FF5722',   # برتقالي غامق - متضرر بشدة
                'destroyed': '#DC3545',    # أحمر - مهدم
                'demolished': '#DC3545',   # أحمر - مهدم
                'rubble': '#8B0000'        # أحمر داكن - ركام
            }
            return status_colors.get(status, '#0072BC')  # أزرق افتراضي

        for b in buildings:
            if hasattr(b, 'latitude') and b.latitude and hasattr(b, 'longitude') and b.longitude:
                # Get building info
                building_type = getattr(b, 'building_type_display', getattr(b, 'building_type', 'مبنى'))
                building_status = getattr(b, 'building_status', 'unknown')
                status_display = getattr(b, 'building_status_display', building_status)

                # Get color based on status
                marker_color = get_marker_color(building_status)

                # Create custom colored marker icon (📍 small Google Maps style)
                markers_js += f"""
                    var icon_{b.building_id.replace('-', '_')} = L.divIcon({{
                        className: 'custom-pin-marker',
                        html: '<div class="pin-marker" style="background-color: {marker_color};"><div class="pin-point"></div></div>',
                        iconSize: [20, 26],  // SMALLER: Google Maps size
                        iconAnchor: [10, 26],  // نقطة الربط في أسفل الدبوس
                        popupAnchor: [0, -28]  // الـ popup يظهر فوق الدبوس
                    }});

                    // Popup content with confirm button
                    var popupContent_{b.building_id.replace('-', '_')} = `
                        <div style="text-align: center; min-width: 180px;">
                            <div style="font-size: 16px; font-weight: bold; color: #2C3E50; margin-bottom: 8px;">
                                {b.building_id}
                            </div>
                            <div style="font-size: 13px; color: #555; margin-bottom: 4px;">
                                النوع: {building_type}
                            </div>
                            <div style="font-size: 13px; color: {marker_color}; font-weight: bold; margin-bottom: 12px;">
                                الحالة: {status_display}
                            </div>
                            <button onclick="selectBuilding('{b.building_id}')"
                                style="width: 100%; padding: 8px 16px; background-color: #0072BC; color: white;
                                       border: none; border-radius: 6px; cursor: pointer; font-weight: bold;
                                       font-size: 14px;">
                                ✓ اختيار هذا المبنى
                            </button>
                        </div>
                    `;

                    var marker_{b.building_id.replace('-', '_')} = L.marker([{b.latitude}, {b.longitude}], {{ icon: icon_{b.building_id.replace('-', '_')} }})
                        .addTo(map)
                        .bindPopup(popupContent_{b.building_id.replace('-', '_')}, {{
                            closeButton: true,
                            maxWidth: 250,
                            className: 'custom-popup'
                        }});
                """

        # Get tile server URL for absolute paths
        tile_server_url = get_tile_server_url()

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}

        /* Pin marker style (📍 small Google Maps style) */
        .custom-pin-marker {{ cursor: pointer; }}
        .pin-marker {{
            width: 20px;
            height: 20px;
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            border: 2px solid white;
            box-shadow: 0 2px 6px rgba(0,0,0,0.4);
            position: relative;
            transition: transform 0.2s ease;
        }}
        .pin-marker:hover {{
            transform: rotate(-45deg) scale(1.2);
            box-shadow: 0 3px 10px rgba(0,0,0,0.6);
        }}
        .pin-point {{
            width: 6px;
            height: 6px;
            background: white;
            border-radius: 50%;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }}

        /* Custom popup styling (ناعم ومرتب) */
        .custom-popup .leaflet-popup-content-wrapper {{
            border-radius: 10px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            padding: 4px;
        }}
        .custom-popup .leaflet-popup-content {{
            margin: 12px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .custom-popup button:hover {{
            background-color: #005A94 !important;
            transform: scale(1.02);
            transition: all 0.2s ease;
        }}

        /* Improve Leaflet controls styling */
        .leaflet-control-zoom a {{
            width: 32px !important;
            height: 32px !important;
            line-height: 32px !important;
            font-size: 20px !important;
            font-weight: bold !important;
        }}
        .leaflet-popup-close-button {{
            font-size: 24px !important;
            padding: 4px 8px !important;
        }}

        .legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            font-size: 12px;
            z-index: 1000;
            max-width: 200px;
        }}
        .legend-title {{
            font-weight: bold;
            margin-bottom: 8px;
            color: #2C3E50;
            border-bottom: 1px solid #E1E8ED;
            padding-bottom: 4px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 4px 0;
        }}
        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-left: 8px;
            border: 1px solid #DDD;
        }}
    </style>
</head>
<body>
    <div id="map"></div>

    <!-- Legend (دليل الألوان) -->
    <div class="legend">
        <div class="legend-title">حالة المبنى</div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #28A745;"></span>
            <span>سليم</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FFC107;"></span>
            <span>متضرر</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FF9800;"></span>
            <span>متضرر جزئياً</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FF5722;"></span>
            <span>متضرر بشدة</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #DC3545;"></span>
            <span>مهدم</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #8B0000;"></span>
            <span>ركام</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #0072BC;"></span>
            <span>غير محدد</span>
        </div>
    </div>

    <script src="{tile_server_url}/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        var buildingBridge = null;

        // Initialize QWebChannel
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            buildingBridge = channel.objects.buildingBridge;
            console.log('QWebChannel initialized');
        }});

        var map = L.map('map', {{
            preferCanvas: true,
            zoomAnimation: true,
            fadeAnimation: false
            // No maxBounds - allow free panning for future tile expansion
        }}).setView([36.2, 37.15], 13);

        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 16,  // FIXED: Match MBTiles actual data (10-16)
            minZoom: 10,  // FIXED: Match MBTiles minimum
            maxNativeZoom: 16,  // Prevent requesting non-existent zoom levels
            attribution: 'UN-Habitat Syria - يعمل بدون اتصال بالإنترنت',
            updateWhenIdle: false,  // FIXED: Update immediately for better UX
            updateWhenZooming: false,  // Don't wait for zoom to finish
            keepBuffer: 4,  // INCREASED: Keep more tiles in memory
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        }}).addTo(map);

        {markers_js}

        function selectBuilding(buildingId) {{
            console.log('Selected building: ' + buildingId);

            // Visual feedback: disable button and show loading
            var button = event.target;
            button.disabled = true;
            button.innerHTML = '⏳ جاري الاختيار...';
            button.style.backgroundColor = '#6C757D';

            // Send selection to Python
            if (buildingBridge) {{
                buildingBridge.selectBuilding(buildingId);
                // Close popup after short delay
                setTimeout(function() {{
                    map.closePopup();
                }}, 500);
            }} else {{
                console.error('buildingBridge not initialized');
                button.innerHTML = '❌ خطأ في الاتصال';
                button.style.backgroundColor = '#DC3545';
            }}
        }}
    </script>
</body>
</html>
"""
        # Set HTML with base URL for relative URL resolution
        logger.info(f"Loading buildings map with base URL: {base_url.toString()}")
        self.building_map.setHtml(html, base_url)

    def _on_building_selected_from_map(self, building_id: str):
        """Handle building selection from map (UC-004 S02)."""
        logger.info(f"Building selected from map: {building_id}")

        # Close the map dialog (but keep instance for reuse)
        if self._map_dialog:
            self._map_dialog.accept()

        # Find the building in database
        building = self.building_repo.get_by_id(building_id)
        if not building:
            QMessageBox.warning(
                self,
                "مبنى غير موجود",
                f"لم يتم العثور على المبنى {building_id} في قاعدة البيانات."
            )
            return

        # Set building in context (same as _on_building_selected)
        self.context.building = building

        # Update the selected building label
        self.selected_building_label.setText(
            f"✅ المبنى المحدد: {building.building_id}\n"
            f"النوع: {building.building_type_display} | "
            f"الحالة: {building.building_status_display}"
        )
        self.selected_building_frame.show()
        self.next_btn.setEnabled(True)

        # Show success toast
        Toast.show_toast(
            self,
            f"تم اختيار المبنى {building_id} من الخريطة",
            toast_type=Toast.SUCCESS,
            duration=2000
        )

    def _load_buildings(self):
        """Load buildings into the list."""
        buildings = self.building_repo.get_all(limit=100)
        self.buildings_list.clear()

        for building in buildings:
            item = QListWidgetItem(
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display} | "
                f"الحالة: {building.building_status_display}"
            )
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _filter_buildings(self):
        """Filter buildings list based on search text."""
        search_text = self.building_search.text().lower()
        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            item.setHidden(search_text not in item.text().lower())

    def _search_buildings(self):
        """Search buildings from database."""
        search = self.building_search.text().strip()
        

        if search:
            buildings = self.building_repo.search(building_id=search, limit=50)
        else:
            buildings = self.building_repo.get_all(limit=100)

        self.buildings_list.clear()
        for building in buildings:
            item = QListWidgetItem(
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display}"
            )
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _on_building_selected(self, item):
        """Handle building selection."""
        building = item.data(Qt.UserRole)
        self.context.building = building

        self.selected_building_label.setText(
            f"✅ المبنى المحدد: {building.building_id}\n"
            f"النوع: {building.building_type_display} | "
            f"الحالة: {building.building_status_display}"
        )
        self.selected_building_frame.show()
        self.next_btn.setEnabled(True)

    def _on_building_confirmed(self, item):
        """Double-click to confirm and proceed."""
        self._on_building_selected(item)
        self._on_next()

    # ==================== Step 2: Unit Selection (S04-S06) ====================


    # ==================== Step 2: Unit Selection (S04-S06) ====================

    def _create_unit_step(self) -> QWidget:
        """Create Step 2: Property Unit Selection with uniqueness validation (S04-S06)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Selected building info card (search + metrics layout)
        self.unit_building_frame = QFrame()
        self.unit_building_frame.setObjectName("unitBuildingInfoCard")
        self.unit_building_frame.setStyleSheet("""
            QFrame#unitBuildingInfoCard {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)

        # Card layout
        self.unit_building_layout = QVBoxLayout(self.unit_building_frame)
        self.unit_building_layout.setSpacing(14)
        self.unit_building_layout.setContentsMargins(14, 14, 14, 14)

        # Building address row with icon (centered with border)
        address_container = QFrame()
        address_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)

        address_row = QHBoxLayout(address_container)
        address_row.setSpacing(8)
        address_row.setContentsMargins(8, 8, 8, 8)

        # Add stretch to center the content
        address_row.addStretch()

        # Building icon
        building_icon = QLabel("🏢")
        building_icon.setStyleSheet("""
            QLabel {
                font-size: 16px;
                border: none;
                background-color: transparent;
            }
        """)
        building_icon.setAlignment(Qt.AlignCenter)
        address_row.addWidget(building_icon)

        # Building address label
        self.unit_building_address = QLabel("حلب الحميدية")
        self.unit_building_address.setAlignment(Qt.AlignCenter)
        self.unit_building_address.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
                font-size: 12px;
                color: #6B7280;
                font-weight: 500;
            }
        """)
        address_row.addWidget(self.unit_building_address)

        # Add stretch to center the content
        address_row.addStretch()

        self.unit_building_layout.addWidget(address_container)

        # Metrics row container
        self.unit_building_metrics_layout = QHBoxLayout()
        self.unit_building_metrics_layout.setSpacing(22)
        self.unit_building_layout.addLayout(self.unit_building_metrics_layout)

        layout.addWidget(self.unit_building_frame)

        # White container frame for all units
        units_main_frame = QFrame()
        units_main_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        units_main_layout = QVBoxLayout(units_main_frame)
        units_main_layout.setSpacing(12)
        units_main_layout.setContentsMargins(16, 16, 16, 16)

        # Header with title/subtitle on right and button on left
        header_layout = QHBoxLayout()

        # Right side: Icon + Title and subtitle
        right_header = QHBoxLayout()
        right_header.setSpacing(8)

        # Icon
        icon_label = QLabel("🏘️")
        icon_label.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        right_header.addWidget(icon_label)

        # Title and subtitle
        title_subtitle_layout = QVBoxLayout()
        title_subtitle_layout.setSpacing(2)

        title_label = QLabel("اختر الوحدة العقارية")
        title_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 200;
            color: #111827;
            border: none;
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(title_label)

        subtitle_label = QLabel("اختر أو أضف معلومات الوحدة العقارية")
        subtitle_label.setStyleSheet("""
            font-size: 9px;
            font-weight: 100;
            color: #6B7280;
            border: none;
            background: transparent;
        """)
        subtitle_label.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(subtitle_label)

        right_header.addLayout(title_subtitle_layout)
        header_layout.addLayout(right_header)
        header_layout.addStretch()

        # Left side: Add unit button
        self.add_unit_btn = QPushButton("أضف وحدة")
        self.add_unit_btn.setIcon(QIcon.fromTheme("list-add"))
        self.add_unit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #005A9C;
            }}
        """)
        self.add_unit_btn.clicked.connect(self._show_add_unit_dialog)
        header_layout.addWidget(self.add_unit_btn)

        units_main_layout.addLayout(header_layout)

        # Units list container (inside white frame)
        self.units_container = QWidget()
        self.units_layout = QVBoxLayout(self.units_container)
        self.units_layout.setSpacing(10)
        self.units_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for units
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.units_container)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)
        units_main_layout.addWidget(scroll, 1)

        layout.addWidget(units_main_frame, 1)

        return widget

    def _check_unit_uniqueness(self):
        """Check if unit number is unique within building (S06 validation)."""
        if not self.context.building or not self.apt_number.text().strip():
            self.unit_uniqueness_label.setText("")
            return

        unit_number = self.apt_number.text().strip()
        floor = self.floor_spin.value()

        # Get existing units and convert to dict format for ValidationService
        existing_units_objs = self.unit_repo.get_by_building(self.context.building.building_id)
        existing_units = [
            {
                'unit_id': unit.unit_id if hasattr(unit, 'unit_id') else None,
                'building_id': unit.building_id if hasattr(unit, 'building_id') else None,
                'floor_number': unit.floor_number if hasattr(unit, 'floor_number') else None,
                'apartment_number': unit.apartment_number if hasattr(unit, 'apartment_number') else None,
                'unit_number': unit.unit_number if hasattr(unit, 'unit_number') else None
            }
            for unit in existing_units_objs
        ]

        # Use ValidationService for uniqueness check
        is_unique = self.validation_service.check_unit_uniqueness(
            unit_number=unit_number,
            floor_number=floor,
            building_id=self.context.building.building_id,
            existing_units=existing_units
        )

        if is_unique:
            self.unit_uniqueness_label.setText("✅ رقم الوحدة متاح")
            self.unit_uniqueness_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")
            self.next_btn.setEnabled(True)
        else:
            self.unit_uniqueness_label.setText("❌ يوجد وحدة بنفس الرقم والطابق")
            self.unit_uniqueness_label.setStyleSheet(f"color: {Config.ERROR_COLOR};")
            self.next_btn.setEnabled(False)

    def _on_unit_option_changed(self):
        """Handle unit option radio change."""
        if self.unit_existing_radio.isChecked():
            self.existing_units_frame.show()
            self.new_unit_frame.hide()
            self.context.is_new_unit = False
            self.next_btn.setEnabled(self.context.unit is not None)
        else:
            self.existing_units_frame.hide()
            self.new_unit_frame.show()
            self.context.is_new_unit = True
            self._check_unit_uniqueness()

    def _load_units_for_building(self):
        """Load units for the selected building and display as cards."""
        if not self.context.building:
            return

        # Populate building info (simple text display)
        if hasattr(self, 'unit_building_label'):
            self.unit_building_label.setText(
                f"🏢 المبنى المحدد: {self.context.building.building_id}"
            )

        # Clear existing unit cards
        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Load units from database
        units = self.unit_repo.get_by_building(self.context.building.building_id)

        if units:
            for unit in units:
                unit_card = self._create_unit_card(unit)
                self.units_layout.addWidget(unit_card)
        else:
            # Empty state message
            empty_label = QLabel("📭 لا توجد وحدات مسجلة. انقر على 'أضف وحدة' لإضافة وحدة جديدة")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("""
                color: #9CA3AF;
                font-size: 14px;
                padding: 40px;
            """)
            self.units_layout.addWidget(empty_label)

        self.units_layout.addStretch()

    def _create_unit_card(self, unit) -> QFrame:
        """Create a unit card widget matching the exact photo layout."""
        # Determine unit display number (from unit_number or apartment_number)
        unit_display_num = unit.unit_number or unit.apartment_number or "?"

        # Check if this is the selected unit
        is_selected = self.context.unit and self.context.unit.unit_id == unit.unit_id

        # Create card frame
        card = QFrame()
        card.setObjectName("unitCard")

        # Different styles for selected and normal cards
        if is_selected:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #f0f7ff;
                    border: 2px solid #3498db;
                    border-radius: 10px;
                }
                QFrame#unitCard QLabel {
                    border: none;
                    color: #2c3e50;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 10px;
                }
                QFrame#unitCard:hover {
                    border-color: #3498db;
                    background-color: #f9fbfd;
                }
                QFrame#unitCard QLabel {
                    border: none;
                    color: #2c3e50;
                }
            """)

        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda _: self._on_unit_card_clicked(unit)
        card.setLayoutDirection(Qt.RightToLeft)

        # Main layout
        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Get unit data
        unit_type_val = unit.unit_type_display if hasattr(unit, 'unit_type_display') else unit.unit_type
        status_val = unit.apartment_status_display if hasattr(unit, 'apartment_status_display') else unit.apartment_status or "جيدة"
        floor_val = str(unit.floor_number) if unit.floor_number is not None else "-"
        rooms_val = str(getattr(unit, 'number_of_rooms', 0)) if hasattr(unit, 'number_of_rooms') else "-"
        area_val = f"{unit.area_sqm}" if unit.area_sqm else "120"

        # Top Row (Data Grid)
        grid_layout = QHBoxLayout()
        grid_layout.setContentsMargins(20, 15, 20, 15)
        grid_layout.setSpacing(10)

        # Column Data (In order for RTL)
        data_points = [
            ("حالة الوحدة", status_val),
            ("نوع الوحدة", unit_type_val),
            ("مساحة القسم", f"{area_val} (م²)"),
            ("عدد الغرف", rooms_val),
            ("رقم الطابق", floor_val),
            ("رقم الوحدة", str(unit_display_num)),
        ]

        for label_text, value_text in data_points:
            col = QVBoxLayout()
            col.setSpacing(4)

            lbl_title = QLabel(label_text)
            lbl_title.setStyleSheet("font-weight: bold; color: #333; font-size: 11px;")
            lbl_title.setAlignment(Qt.AlignCenter)

            lbl_val = QLabel(str(value_text))
            lbl_val.setStyleSheet("color: #666; font-size: 11px;")
            lbl_val.setAlignment(Qt.AlignCenter)

            col.addWidget(lbl_title)
            col.addWidget(lbl_val)
            grid_layout.addLayout(col)

        main_layout.addLayout(grid_layout)

        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #eeeeee; border: none; max-height: 1px;")
        main_layout.addWidget(line)

        # Bottom Section (Description)
        desc_layout = QVBoxLayout()
        desc_layout.setContentsMargins(20, 12, 20, 15)
        desc_layout.setSpacing(6)

        desc_title = QLabel("وصف العقار")
        desc_title.setStyleSheet("font-weight: bold; color: #333; font-size: 11px;")
       # desc_title.setAlignment(Qt.AlignRight)

        desc_text_content = unit.property_description if unit.property_description else "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة."
        desc_text = QLabel(desc_text_content)
        desc_text.setStyleSheet("color: #7f8c8d; font-size: 10px;")
       # desc_text.setAlignment(Qt.AlignRight)
        desc_text.setWordWrap(True)
        desc_text.setMaximumHeight(40)

        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(desc_text)
        main_layout.addLayout(desc_layout)

        # Checkmark for selected item
        if is_selected:
            check_label = QLabel("✓")
            check_label.setStyleSheet("color: #3498db; font-size: 18px; font-weight: bold; border: none;")
            check_label.setAlignment(Qt.AlignLeft)
            main_layout.addWidget(check_label)

        return card

    def _create_detail_label(self, label: str, value: str) -> QWidget:
        """Create a detail label-value pair."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-size: 11px; color: #9CA3AF; font-weight: 500;")
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("font-size: 13px; color: #111827; font-weight: 600;")
        layout.addWidget(value_widget)

        return container

    def _on_unit_card_clicked(self, unit):
        """Handle unit card click."""
        self.context.unit = unit
        self.context.is_new_unit = False
        # Refresh cards to show selection
        self._load_units_for_building()
        self.next_btn.setEnabled(True)

    def _show_add_unit_dialog(self):
        """Show dialog to add a new unit (matching photo design)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("أضف معلومات الوحدة العقارية")
        dialog.setMinimumWidth(550)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #F9FAFB;
            }
        """)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setSpacing(20)
        dialog_layout.setContentsMargins(24, 24, 24, 24)

        # Content frame
        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(16)

        # Row 1: Unit Type and Unit Status (equal width columns)
        
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # Unit Type (left column - 50%)
        type_container = QVBoxLayout()
        type_label = QLabel("نوع الوحدة")
        type_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        self.unit_type_combo = QComboBox()
        self.unit_type_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
        """)
        unit_types = [
            ("", "اختر"),
            ("apartment", "شقة"), ("shop", "محل تجاري"), ("office", "مكتب"),
            ("warehouse", "مستودع"), ("garage", "مرآب"), ("other", "أخرى")
        ]
        for code, ar in unit_types:
            self.unit_type_combo.addItem(ar, code)
        type_container.addWidget(type_label)
        type_container.addWidget(self.unit_type_combo)
        row1.addLayout(type_container, 1)  # Stretch factor 1 = 50%

        # Unit Status (right column - 50%)
        status_container = QVBoxLayout()
        status_label = QLabel("حالة الوحدة")
        status_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        unit_status_combo = QComboBox()
        unit_status_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
        """)
        unit_statuses = [("", "اختر"), ("intact", "جيدة"), ("damaged", "متضررة"), ("destroyed", "مدمرة")]
        for code, ar in unit_statuses:
            unit_status_combo.addItem(ar, code)
        status_container.addWidget(status_label)
        status_container.addWidget(unit_status_combo)
        row1.addLayout(status_container, 1)  # Stretch factor 1 = 50%

        content_layout.addLayout(row1)

        # Row 2: Floor Number and Unit Number (equal width columns)
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # Floor Number (left column - 50%)
        floor_container = QVBoxLayout()
        floor_label = QLabel("رقم الطابق")
        floor_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 100)
        self.floor_spin.setValue(0)
        self.floor_spin.setStyleSheet("""
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
        """)
        floor_container.addWidget(floor_label)
        floor_container.addWidget(self.floor_spin)
        row2.addLayout(floor_container, 1)  # Stretch factor 1 = 50%

        # Unit Number (right column - 50%)
        unit_num_container = QVBoxLayout()
        unit_num_label = QLabel("رقم الوحدة")
        unit_num_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        self.apt_number = QLineEdit()
        self.apt_number.setPlaceholderText("0")
        self.apt_number.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
        """)
        unit_num_container.addWidget(unit_num_label)
        unit_num_container.addWidget(self.apt_number)
        row2.addLayout(unit_num_container, 1)  # Stretch factor 1 = 50%

        content_layout.addLayout(row2)

        # Row 3: Number of Rooms and Area (equal width columns)
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        # Number of Rooms (left column - 50%)
        rooms_container = QVBoxLayout()
        rooms_label = QLabel("عدد الغرف")
        rooms_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        self.unit_rooms = QSpinBox()
        self.unit_rooms.setRange(0, 20)
        self.unit_rooms.setValue(0)
        self.unit_rooms.setStyleSheet("""
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
        """)
        rooms_container.addWidget(rooms_label)
        rooms_container.addWidget(self.unit_rooms)
        row3.addLayout(rooms_container, 1)  # Stretch factor 1 = 50%

        # Area (right column - 50%)
        area_container = QVBoxLayout()
        area_label = QLabel("مساحة القسم")
        area_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        self.unit_area = QLineEdit()
        self.unit_area.setPlaceholderText("المساحة التقريبية أو المقاسة (م²)")
        self.unit_area.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
        """)
        area_container.addWidget(area_label)
        area_container.addWidget(self.unit_area)
        row3.addLayout(area_container, 1)  # Stretch factor 1 = 50%

        content_layout.addLayout(row3)

        # Description (full width)
        desc_label = QLabel("وصف القطار")
        desc_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px;")
        self.unit_desc = QTextEdit()
        self.unit_desc.setMaximumHeight(100)
        self.unit_desc.setPlaceholderText("وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة.")
        self.unit_desc.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
                color: #6B7280;
            }
        """)
        content_layout.addWidget(desc_label)
        content_layout.addWidget(self.unit_desc)

        dialog_layout.addWidget(content_frame)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        cancel_btn = QPushButton("الغاء")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)

        save_btn = QPushButton("حفظ")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
                color: white;
            }}
            QPushButton:hover {{
                background-color: #005A9C;
            }}
        """)
        save_btn.clicked.connect(dialog.accept)

        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(save_btn)
        dialog_layout.addLayout(buttons_layout)

        if dialog.exec_() == QDialog.Accepted:
            # Create new unit (will be saved when moving forward)
            self.context.is_new_unit = True

            # Parse area value
            area_value = None
            if self.unit_area.text().strip():
                try:
                    area_value = float(self.unit_area.text().strip())
                except ValueError:
                    pass

            self.context.new_unit_data = {
                'unit_type': self.unit_type_combo.currentData(),
                'apartment_status': unit_status_combo.currentData(),
                'floor_number': self.floor_spin.value(),
                'apartment_number': self.apt_number.text(),
                'area_sqm': area_value,
                'number_of_rooms': self.unit_rooms.value(),
                'property_description': self.unit_desc.toPlainText()
            }
            self.next_btn.setEnabled(True)
            QMessageBox.information(self, "تم", "سيتم إضافة الوحدة عند إتمام الاستمارة")

    def _on_unit_selected(self, item):
        """Handle unit selection."""
        unit = item.data(Qt.UserRole)
        if unit:
            self.context.unit = unit
            self.next_btn.setEnabled(True)

    def _save_new_unit_data(self):
        """Save new unit data to context."""
        if self.context.is_new_unit:
            # Check if widgets still exist before accessing them
            if not hasattr(self, 'unit_area') or self.unit_area is None:
                return

            # Parse area value
            area_value = None
            try:
                if hasattr(self, 'unit_area') and self.unit_area is not None and self.unit_area.text().strip():
                    area_value = float(self.unit_area.text().strip())
            except (ValueError, RuntimeError):
                pass

            # Safely get values from widgets with existence checks
            try:
                self.context.new_unit_data = {
                    "unit_type": self.unit_type_combo.currentData() if hasattr(self, 'unit_type_combo') and self.unit_type_combo is not None else None,
                    "floor_number": self.floor_spin.value() if hasattr(self, 'floor_spin') and self.floor_spin is not None else 0,
                    "apartment_number": self.apt_number.text().strip() if hasattr(self, 'apt_number') and self.apt_number is not None else "",
                    "area_sqm": area_value,
                    "number_of_rooms": self.unit_rooms.value() if hasattr(self, 'unit_rooms') and self.unit_rooms is not None else 0,
                    "property_description": self.unit_desc.toPlainText().strip() if hasattr(self, 'unit_desc') and self.unit_desc is not None else "",
                    "building_id": self.context.building.building_id if self.context.building else None
                }
            except RuntimeError:
                # Widgets were deleted, skip saving
                pass

    # ==================== Step 3: Household (S07-S10) ====================

    def _create_household_step(self) -> QWidget:
        """Create Step 3: Household/Occupancy with adults/minors (S07-S10)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        # Building info card with all content in one bordered container
        self.household_building_frame = QFrame()
        self.household_building_frame.setObjectName("householdBuildingInfoCard")
        self.household_building_frame.setStyleSheet("""
            QFrame#householdBuildingInfoCard {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }
        """)

        # Card layout with compact spacing
        self.household_building_layout = QVBoxLayout(self.household_building_frame)
        self.household_building_layout.setSpacing(8)
        self.household_building_layout.setContentsMargins(12, 12, 12, 12)

        # Building address row with icon (centered, no separate border)
        address_container = QWidget()
        address_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)

        address_row = QHBoxLayout(address_container)
        address_row.setSpacing(6)
        address_row.setContentsMargins(6, 6, 6, 6)

        # Add stretch to center the content
        address_row.addStretch()

        # Building icon
        building_icon = QLabel("🏢")
        building_icon.setStyleSheet("""
            QLabel {
                font-size: 16px;
                border: none;
                background-color: transparent;
            }
        """)
        building_icon.setAlignment(Qt.AlignCenter)
        address_row.addWidget(building_icon)

        # Building address label
        self.household_building_address = QLabel("حلب الحميدية")
        self.household_building_address.setAlignment(Qt.AlignCenter)
        self.household_building_address.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
                font-size: 12px;
                color: #6B7280;
                font-weight: 500;
            }
        """)
        address_row.addWidget(self.household_building_address)

        # Add stretch to center the content
        address_row.addStretch()

        self.household_building_layout.addWidget(address_container)

        # Metrics row container (no separate border, transparent background)
        metrics_container = QWidget()
        metrics_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        self.household_building_metrics_layout = QHBoxLayout(metrics_container)
        self.household_building_metrics_layout.setSpacing(16)
        self.household_building_metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.household_building_layout.addWidget(metrics_container)

        # Unit info layout (no separate border, transparent background)
        unit_info_container = QWidget()
        unit_info_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        self.household_unit_layout = QVBoxLayout(unit_info_container)
        self.household_unit_layout.setSpacing(6)
        self.household_unit_layout.setContentsMargins(0, 0, 0, 0)
        self.household_building_layout.addWidget(unit_info_container)

        layout.addWidget(self.household_building_frame)

        # Create scroll area for family information sections
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #F3F4F6;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #9CA3AF;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6B7280;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

        # Container widget for scroll area content
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        # معلومات الاسرة (Family Information) Section
        family_info_frame = QFrame()
        family_info_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        family_info_layout = QVBoxLayout(family_info_frame)
        family_info_layout.setSpacing(12)

        # Header
        family_info_header = QLabel("📋 معلومات الاسرة")
        family_info_header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        family_info_layout.addWidget(family_info_header)

        # Grid layout for family info fields (2 columns, RTL: right=0, left=1)
        family_info_grid = QGridLayout()
        family_info_grid.setSpacing(12)
        family_info_grid.setColumnStretch(0, 1)
        family_info_grid.setColumnStretch(1, 1)

        # Right side (RTL): عدد الأفراد should appear on right (column 1)
        total_members_label = QLabel("عدد الأفراد")
        total_members_label.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 4px; border: none; background-color: transparent;")
        #total_members_label.setAlignment(Qt.AlignRight)
        family_info_grid.addWidget(total_members_label, 0, 1)

        self.hh_total_members = QSpinBox()
        self.hh_total_members.setRange(0, 50)
        self.hh_total_members.setValue(0)
        self.hh_total_members.setStyleSheet("""
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        family_info_grid.addWidget(self.hh_total_members, 1, 1)

        # Left side (RTL): رب الأسرة/العائل should appear on left (column 0)
        head_name_label = QLabel("رب الأسرة/العائل")
        head_name_label.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 4px; border: none; background-color: transparent;")
       # head_name_label.setAlignment(Qt.AlignRight)
        family_info_grid.addWidget(head_name_label, 0, 0)

        self.hh_head_name = QLineEdit()
        self.hh_head_name.setPlaceholderText("اسم رب الأسرة")
        self.hh_head_name.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        family_info_grid.addWidget(self.hh_head_name, 1, 0)

        family_info_layout.addLayout(family_info_grid)
        scroll_layout.addWidget(family_info_frame)

        # تكوين الأسرة (Family Composition) Section
        composition_frame = QFrame()
        composition_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        composition_layout = QVBoxLayout(composition_frame)
        composition_layout.setSpacing(12)

        # Header
        composition_header = QLabel("👥 تكوين الأسرة")
        composition_header.setStyleSheet("""
            font-size: 13px;
            font-weight: 200;
            color: #1F2937;
            padding: 4px 0px;
        """)
        composition_layout.addWidget(composition_header)

        # Grid layout for composition fields (2 columns x multiple rows)
        composition_grid = QGridLayout()
        composition_grid.setSpacing(12)
        composition_grid.setColumnStretch(0, 1)
        composition_grid.setColumnStretch(1, 1)

        label_style = "font-size: 12px; color: #374151; font-weight: 500; margin-bottom: 4px; border: none; background-color: transparent;"
        spinbox_style = """
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """

        # Row 0-1: عدد البالغين الإناث (RIGHT side for RTL, column 1)
        adult_females_label = QLabel("عدد البالغين الإناث")
        adult_females_label.setStyleSheet(label_style)
       # adult_females_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(adult_females_label, 0, 1)

        self.hh_adult_females = QSpinBox()
        self.hh_adult_females.setRange(0, 50)
        self.hh_adult_females.setValue(0)
        self.hh_adult_females.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_adult_females, 1, 1)

        # Row 0-1: عدد البالغين الذكور (LEFT side for RTL, column 0)
        adult_males_label = QLabel("عدد البالغين الذكور")
        adult_males_label.setStyleSheet(label_style)
        #adult_males_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(adult_males_label, 0, 0)

        self.hh_adult_males = QSpinBox()
        self.hh_adult_males.setRange(0, 50)
        self.hh_adult_males.setValue(0)
        self.hh_adult_males.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_adult_males, 1, 0)

        # Row 2-3: عدد الأطفال الإناث (أقل من 18) (RIGHT side for RTL, column 1)
        female_children_label = QLabel("عدد الأطفال الإناث (أقل من 18)")
        female_children_label.setStyleSheet(label_style)
        #female_children_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(female_children_label, 2, 1)

        self.hh_female_children_under18 = QSpinBox()
        self.hh_female_children_under18.setRange(0, 50)
        self.hh_female_children_under18.setValue(0)
        self.hh_female_children_under18.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_female_children_under18, 3, 1)

        # Row 2-3: عدد الأطفال الذكور (أقل من 18) (LEFT side for RTL, column 0)
        male_children_label = QLabel("عدد الأطفال الذكور (أقل من 18)")
        male_children_label.setStyleSheet(label_style)
       # male_children_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(male_children_label, 2, 0)

        self.hh_male_children_under18 = QSpinBox()
        self.hh_male_children_under18.setRange(0, 50)
        self.hh_male_children_under18.setValue(0)
        self.hh_male_children_under18.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_male_children_under18, 3, 0)

        # Row 4-5: عدد كبار السن الإناث (أكبر من 65) (RIGHT side for RTL, column 1)
        female_elderly_label = QLabel("عدد كبار السن الإناث (أكبر من 65)")
        female_elderly_label.setStyleSheet(label_style)
        #female_elderly_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(female_elderly_label, 4, 1)

        self.hh_female_elderly_over65 = QSpinBox()
        self.hh_female_elderly_over65.setRange(0, 50)
        self.hh_female_elderly_over65.setValue(0)
        self.hh_female_elderly_over65.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_female_elderly_over65, 5, 1)

        # Row 4-5: عدد كبار السن الذكور (أكبر من 65) (LEFT side for RTL, column 0)
        male_elderly_label = QLabel("عدد كبار السن الذكور (أكبر من 65)")
        male_elderly_label.setStyleSheet(label_style)
        #male_elderly_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(male_elderly_label, 4, 0)

        self.hh_male_elderly_over65 = QSpinBox()
        self.hh_male_elderly_over65.setRange(0, 50)
        self.hh_male_elderly_over65.setValue(0)
        self.hh_male_elderly_over65.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_male_elderly_over65, 5, 0)

        # Row 6-7: عدد المعاقين الإناث (RIGHT side for RTL, column 1)
        disabled_females_label = QLabel("عدد المعاقين الإناث")
        disabled_females_label.setStyleSheet(label_style)
        #disabled_females_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(disabled_females_label, 6, 1)

        self.hh_disabled_females = QSpinBox()
        self.hh_disabled_females.setRange(0, 50)
        self.hh_disabled_females.setValue(0)
        self.hh_disabled_females.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_disabled_females, 7, 1)

        # Row 6-7: عدد المعاقين الذكور (LEFT side for RTL, column 0)
        disabled_males_label = QLabel("عدد المعاقين الذكور")
        disabled_males_label.setStyleSheet(label_style)
        #disabled_males_label.setAlignment(Qt.AlignRight)
        composition_grid.addWidget(disabled_males_label, 6, 0)

        self.hh_disabled_males = QSpinBox()
        self.hh_disabled_males.setRange(0, 50)
        self.hh_disabled_males.setValue(0)
        self.hh_disabled_males.setStyleSheet(spinbox_style)
        composition_grid.addWidget(self.hh_disabled_males, 7, 0)

        composition_layout.addLayout(composition_grid)
        scroll_layout.addWidget(composition_frame)

        # ادخل ملاحظاتك (Notes) Section
        notes_frame = QFrame()
        notes_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        notes_layout = QVBoxLayout(notes_frame)
        notes_layout.setSpacing(12)

        # Header
        notes_header = QLabel("📝 ادخل ملاحظاتك")
        notes_header.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #1F2937;
            padding: 4px 0px;
        """)
        notes_layout.addWidget(notes_header)

        # Notes text area
        self.hh_notes = QTextEdit()
        self.hh_notes.setPlaceholderText("أدخل ملاحظاتك هنا...")
        self.hh_notes.setMaximumHeight(100)
        self.hh_notes.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
            }
        """)
        notes_layout.addWidget(self.hh_notes)

        scroll_layout.addWidget(notes_frame)

        # Add save button at the bottom of scroll content
        save_btn_container = QWidget()
        save_btn_layout = QHBoxLayout(save_btn_container)
        save_btn_layout.setContentsMargins(0, 12, 0, 0)

        add_hh_btn = QPushButton("+ إضافة أسرة")
        add_hh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        add_hh_btn.clicked.connect(self._save_household)
        save_btn_layout.addStretch()
        save_btn_layout.addWidget(add_hh_btn)
        save_btn_layout.addStretch()

        scroll_layout.addWidget(save_btn_container)

        # Set scroll content and add to main layout
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        return widget

    def _on_household_selected(self, item):
        """Load household data for editing."""
        hh_id = item.data(Qt.UserRole)
        for i, hh in enumerate(self.context.households):
            if hh['household_id'] == hh_id:
                self._editing_household_index = i
                self.hh_head_name.setText(hh['head_name'])
                self.hh_total_members.setValue(hh.get('size', 0))
                self.hh_adult_males.setValue(hh.get('adult_males', 0))
                self.hh_adult_females.setValue(hh.get('adult_females', 0))
                self.hh_male_children_under18.setValue(hh.get('male_children_under18', 0))
                self.hh_female_children_under18.setValue(hh.get('female_children_under18', 0))
                self.hh_male_elderly_over65.setValue(hh.get('male_elderly_over65', 0))
                self.hh_female_elderly_over65.setValue(hh.get('female_elderly_over65', 0))
                self.hh_disabled_males.setValue(hh.get('disabled_males', 0))
                self.hh_disabled_females.setValue(hh.get('disabled_females', 0))
                self.hh_notes.setPlainText(hh.get('notes', ''))
                break

    def _save_household(self):
        """Save current household data."""
        if not self.hh_head_name.text().strip():
            QMessageBox.warning(self, "خطأ", "يجب إدخال اسم رب الأسرة")
            return

        household = {
            "household_id": str(uuid.uuid4()) if not hasattr(self, '_editing_household_index') or self._editing_household_index is None else self.context.households[self._editing_household_index]['household_id'],
            "head_name": self.hh_head_name.text().strip(),
            "size": self.hh_total_members.value(),
            "adult_males": self.hh_adult_males.value(),
            "adult_females": self.hh_adult_females.value(),
            "male_children_under18": self.hh_male_children_under18.value(),
            "female_children_under18": self.hh_female_children_under18.value(),
            "male_elderly_over65": self.hh_male_elderly_over65.value(),
            "female_elderly_over65": self.hh_female_elderly_over65.value(),
            "disabled_males": self.hh_disabled_males.value(),
            "disabled_females": self.hh_disabled_females.value(),
            "notes": self.hh_notes.toPlainText().strip()
        }

        if hasattr(self, '_editing_household_index') and self._editing_household_index is not None:
            self.context.households[self._editing_household_index] = household
            Toast.show_toast(self, "تم تحديث بيانات الأسرة", Toast.SUCCESS)
        else:
            self.context.households.append(household)
            Toast.show_toast(self, "تم إضافة الأسرة", Toast.SUCCESS)

        self._refresh_households_list()
        self._clear_household_form()  # Clear form
        self.next_btn.setEnabled(True)

    def _clear_household_form(self):
        """Clear household form fields."""
        self._editing_household_index = None
        self.hh_head_name.clear()
        self.hh_total_members.setValue(0)
        self.hh_adult_males.setValue(0)
        self.hh_adult_females.setValue(0)
        self.hh_male_children_under18.setValue(0)
        self.hh_female_children_under18.setValue(0)
        self.hh_male_elderly_over65.setValue(0)
        self.hh_female_elderly_over65.setValue(0)
        self.hh_disabled_males.setValue(0)
        self.hh_disabled_females.setValue(0)
        self.hh_notes.clear()

    def _delete_household(self):
        """Delete selected household."""
        current = self.households_list.currentItem()
        if not current:
            return

        hh_id = current.data(Qt.UserRole)
        self.context.households = [h for h in self.context.households if h['household_id'] != hh_id]
        self._refresh_households_list()
        self._clear_household_form()
        Toast.show_toast(self, "تم حذف الأسرة", Toast.INFO)

    def _refresh_households_list(self):
        """Refresh the households display list (no UI update needed)."""
        # No list widget to refresh since we removed it
        pass

    # ==================== Step 4: Persons (S11-S13) ====================

    def _create_persons_step(self) -> QWidget:
        """Create Step 4: Person Registration with Edit support (S11-S13)."""
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet("background-color: #F8FAFC;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(16)

        # Main Card Container
        table_frame = QFrame()
        table_frame.setLayoutDirection(Qt.RightToLeft)
        table_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E2E8F0;
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

        return widget

    def _add_person(self):
        """Show dialog to add a new person."""
        dialog = PersonDialog(
            parent=self,
            person_data=None,
            households=self.context.households,
            existing_persons=self.context.persons
        )

        if dialog.exec_() == QDialog.Accepted:
            person_data = dialog.get_person_data()
            person_data['person_id'] = str(uuid.uuid4())
            self.context.persons.append(person_data)
            self._refresh_persons_list()
            Toast.show_toast(self, "تم إضافة الشخص بنجاح", Toast.SUCCESS)

    def _create_person_row_card(self, person: dict, index: int = 0) -> QFrame:
        """Create a person row card matching the new design layout."""
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
        """Refresh persons display table."""
        # Clear existing cards
        while self.persons_table_layout.count() > 1:  # Keep the stretch
            item = self.persons_table_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add person cards
        for idx, person in enumerate(self.context.persons):
            person_card = self._create_person_row_card(person, idx)
            self.persons_table_layout.insertWidget(idx, person_card)

        # Enable next button if there are persons
        if self.current_step == self.STEP_PERSONS:
            self.next_btn.setEnabled(len(self.context.persons) > 0)

    def _view_person(self, person_id: str):
        """Show dialog to view/edit person data."""
        person_data = None
        person_index = None

        for i, person in enumerate(self.context.persons):
            if person['person_id'] == person_id:
                person_data = person
                person_index = i
                break

        if person_data:
            dialog = PersonDialog(
                parent=self,
                person_data=person_data,
                households=self.context.households,
                existing_persons=self.context.persons
            )

            if dialog.exec_() == QDialog.Accepted:
                updated_data = dialog.get_person_data()
                updated_data['person_id'] = person_id  # Keep the same ID
                self.context.persons[person_index] = updated_data
                self._refresh_persons_list()
                Toast.show_toast(self, "تم تحديث بيانات الشخص بنجاح", Toast.SUCCESS)

    def _delete_person_by_id(self, person_id: str):
        """Delete person by ID with confirmation."""
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
        Toast.show_toast(self, "تم حذف الشخص بنجاح", Toast.SUCCESS)

    # ==================== Step 5: Relations (S14-S16) ====================

    def _create_relations_step(self) -> QWidget:
        """Create Step 5: Relations with linked Evidence (S14-S16)."""
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        # Header (title + subtitle) placed outside the card
        title_box = QVBoxLayout()
        title = QLabel("العلاقة والأدلة")
        title.setStyleSheet("color: #111827; font-weight: 700; font-size: 16px;")
        subtitle = QLabel("تسجيل تفاصيل ملكية شخص للوحدة عقارية")
        subtitle.setStyleSheet("color: #6B7280; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout = QHBoxLayout()
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        outer.addLayout(header_layout)

        # Card Container (holds all fields & actions)
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)
        outer.addWidget(card)

        # Small icon button inside the card aligned to the right
        top_btn = QPushButton("⚙")
        top_btn.setFixedSize(34, 34)
        top_btn.setStyleSheet("""
            QPushButton {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #F3F4F6; }
        """)
        top_btn_row = QHBoxLayout()
        top_btn_row.addStretch(1)
        top_btn_row.addWidget(top_btn)
        card_layout.addLayout(top_btn_row)

        # Person row with dropdown
        person_row = QHBoxLayout()
        person_row.setSpacing(10)

        # Person selector combo
        self.rel_person_combo = QComboBox()
        self.rel_person_combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 700;
                color: #111827;
                min-width: 200px;
            }
        """)
        # Enable next button when person is selected
        self.rel_person_combo.currentIndexChanged.connect(self._on_relation_person_changed)

        avatar = QLabel("👤")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(38, 38)
        avatar.setStyleSheet("""
            QLabel {
                background-color: #EEF2FF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                font-size: 16px;
            }
        """)

        person_row.addWidget(avatar)
        person_row.addWidget(self.rel_person_combo)
        person_row.addStretch(1)
        card_layout.addLayout(person_row)

        # Grid fields
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        label_style = "color: #374151; font-weight: 600; font-size: 12px;"
        input_style = """
            QComboBox, QDateEdit, QDoubleSpinBox, QLineEdit {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
        """

        # Row 0 labels
        contract_type_lbl = QLabel("نوع العقد")
        contract_type_lbl.setStyleSheet(label_style)
        grid.addWidget(contract_type_lbl, 0, 0)

        relation_type_lbl = QLabel("نوع العلاقة")
        relation_type_lbl.setStyleSheet(label_style)
        grid.addWidget(relation_type_lbl, 0, 1)

        start_date_lbl = QLabel("تاريخ بدء العلاقة")
        start_date_lbl.setStyleSheet(label_style)
        grid.addWidget(start_date_lbl, 0, 2)

        # Row 1 inputs
        self.rel_contract_type = QComboBox()
        self.rel_contract_type.addItems(["اختر", "عقد إيجار", "عقد بيع", "عقد شراكة"])
        self.rel_contract_type.setStyleSheet(input_style)

        self.rel_type_combo = QComboBox()
        rel_types = [
            ("owner", "مالك"), ("co_owner", "شريك في الملكية"),
            ("tenant", "مستأجر"), ("occupant", "شاغل"),
            ("heir", "وارث"), ("guardian", "ولي/وصي"), ("other", "أخرى")
        ]
        for code, ar in rel_types:
            self.rel_type_combo.addItem(ar, code)
        self.rel_type_combo.setStyleSheet(input_style)

        self.rel_start_date = QDateEdit()
        self.rel_start_date.setCalendarPopup(True)
        self.rel_start_date.setDisplayFormat("yyyy-MM-dd")
        self.rel_start_date.setDate(QDate.currentDate())
        self.rel_start_date.setStyleSheet(input_style)

        grid.addWidget(self.rel_contract_type, 1, 0)
        grid.addWidget(self.rel_type_combo, 1, 1)
        grid.addWidget(self.rel_start_date, 1, 2)

        # Row 2 labels
        ownership_share_lbl = QLabel("حصة الملكية")
        ownership_share_lbl.setStyleSheet(label_style)
        grid.addWidget(ownership_share_lbl, 2, 0)

        evidence_type_lbl = QLabel("نوع الدليل")
        evidence_type_lbl.setStyleSheet(label_style)
        grid.addWidget(evidence_type_lbl, 2, 1)

        evidence_desc_lbl = QLabel("وصف الدليل")
        evidence_desc_lbl.setStyleSheet(label_style)
        grid.addWidget(evidence_desc_lbl, 2, 2)

        # Row 3 inputs
        self.rel_share = QDoubleSpinBox()
        self.rel_share.setRange(0, 100)
        self.rel_share.setDecimals(2)
        self.rel_share.setSuffix(" %")
        self.rel_share.setValue(0)
        self.rel_share.setStyleSheet(input_style)

        self.rel_evidence_type = QComboBox()
        self.rel_evidence_type.addItems(["اختر", "صك", "عقد", "وكالة", "إقرار"])
        self.rel_evidence_type.setStyleSheet(input_style)

        self.rel_evidence_desc = QLineEdit()
        self.rel_evidence_desc.setPlaceholderText("-")
        self.rel_evidence_desc.setStyleSheet(input_style)

        grid.addWidget(self.rel_share, 3, 0)
        grid.addWidget(self.rel_evidence_type, 3, 1)
        grid.addWidget(self.rel_evidence_desc, 3, 2)

        # Notes label + full-width notes
        notes_lbl = QLabel("ادخل ملاحظاتك")
        notes_lbl.setStyleSheet(label_style)
        self.rel_notes = QTextEdit()
        self.rel_notes.setPlaceholderText("-")
        self.rel_notes.setMinimumHeight(70)
        self.rel_notes.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QTextEdit:focus {
                border: 1px solid #3B82F6;
            }
        """)

        grid.addWidget(notes_lbl, 4, 0, 1, 3)
        grid.addWidget(self.rel_notes, 5, 0, 1, 3)

        card_layout.addLayout(grid)

        # Documents section
        docs_title = QLabel("صور المستندات")
        docs_title.setStyleSheet(label_style)
        card_layout.addWidget(docs_title)

        docs_row = QHBoxLayout()
        docs_row.setSpacing(18)

        self.rel_rb_has = QRadioButton("يوجد مستندات")
        self.rel_rb_none = QRadioButton("لا يوجد مستندات")
        self.rel_rb_has.setChecked(True)

        grp = QButtonGroup(self)
        grp.addButton(self.rel_rb_has)
        grp.addButton(self.rel_rb_none)

        docs_row.addWidget(self.rel_rb_has)
        docs_row.addWidget(self.rel_rb_none)
        docs_row.addStretch(1)

        card_layout.addLayout(docs_row)

        # Upload box
        upload_box = QFrame()
        upload_box.setStyleSheet("""
            QFrame {
                border: 2px dashed #D1D5DB;
                border-radius: 12px;
                background-color: #FBFDFF;
                min-height: 70px;
            }
        """)
        up = QHBoxLayout(upload_box)
        up.setContentsMargins(12, 10, 12, 10)
        up.setSpacing(12)

        self.rel_thumb = QLabel("📄")
        self.rel_thumb.setAlignment(Qt.AlignCenter)
        self.rel_thumb.setStyleSheet("""
            QLabel {
                background-color: #EEF2FF;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                min-width: 54px;
                min-height: 54px;
                font-size: 24px;
            }
        """)
        up.addWidget(self.rel_thumb)

        # Center content (link-like button)
        center_col = QVBoxLayout()
        center_col.setSpacing(4)

        self.rel_upload_btn = QPushButton("ارفع صور المستندات")
        self.rel_upload_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #2563EB;
                font-weight: 700;
                text-decoration: underline;
                text-align: right;
            }
        """)
        self.rel_upload_btn.clicked.connect(self._pick_evidence_files)

        hint = QLabel("PNG / JPG / PDF")
        hint.setStyleSheet("color: #6B7280; font-size: 11px;")

        center_col.addWidget(self.rel_upload_btn, alignment=Qt.AlignRight)
        center_col.addWidget(hint, alignment=Qt.AlignRight)

        up.addLayout(center_col)
        up.addStretch(1)

        # Optional right icon button
        self.rel_action_btn = QPushButton("⬆")
        self.rel_action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 700;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: #1D4ED8;
            }}
        """)
        self.rel_action_btn.setFixedHeight(44)
        self.rel_action_btn.clicked.connect(self._pick_evidence_files)
        up.addWidget(self.rel_action_btn)

        card_layout.addWidget(upload_box)

        # Store for uploaded files
        self._current_relation_evidences = []
        self._relation_file_paths = []

        return widget

    def _pick_evidence_files(self):
        """Pick evidence files for relation."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "اختر المستندات",
            "",
            "Images/PDF (*.png *.jpg *.jpeg *.pdf);;All Files (*.*)"
        )
        if files:
            self.rel_thumb.setText(str(len(files)))
            self.rel_thumb.setToolTip("\n".join(files))
            # Store file paths for later processing
            self._relation_file_paths = files

    def _populate_relations_persons(self):
        """Populate the persons combo for relations."""
        self.rel_person_combo.clear()
        for person in self.context.persons:
            full_name = f"{person['first_name']} {person['last_name']}"
            self.rel_person_combo.addItem(full_name, person['person_id'])

    def _on_relation_person_changed(self):
        """Enable next button when a person is selected."""
        if self.current_step == self.STEP_RELATIONS:
            has_person = self.rel_person_combo.currentData() is not None
            self.next_btn.setEnabled(has_person or len(self.context.relations) > 0)

    def _add_relation(self):
        """Clear form for new relation."""
        self._editing_relation_index = None
        self._current_relation_evidences = []
        self._relation_file_paths = []

        # Reset form fields
        self.rel_share.setValue(0)
        self.rel_start_date.setDate(QDate.currentDate())
        self.rel_notes.clear()
        self.rel_contract_type.setCurrentIndex(0)
        self.rel_type_combo.setCurrentIndex(0)
        self.rel_evidence_type.setCurrentIndex(0)
        self.rel_evidence_desc.clear()
        self.rel_thumb.setText("📄")
        self.rel_thumb.setToolTip("")

        self._populate_relations_persons()

    def _on_relation_selected(self, item):
        """Load relation for editing."""
        rel_id = item.data(Qt.UserRole)
        for i, rel in enumerate(self.context.relations):
            if rel['relation_id'] == rel_id:
                self._editing_relation_index = i
                self._populate_relations_persons()

                # Set person
                idx = self.rel_person_combo.findData(rel['person_id'])
                if idx >= 0:
                    self.rel_person_combo.setCurrentIndex(idx)

                # Set type
                idx = self.rel_type_combo.findData(rel['relation_type'])
                if idx >= 0:
                    self.rel_type_combo.setCurrentIndex(idx)

                self.rel_share.setValue(rel.get('ownership_share', 2400))
                if rel.get('start_date'):
                    self.rel_start_date.setDate(QDate.fromString(rel['start_date'], "yyyy-MM-dd"))
                self.rel_contract_number.setText(rel.get('contract_number', ''))
                if rel.get('contract_date'):
                    self.rel_contract_date.setDate(QDate.fromString(rel['contract_date'], "yyyy-MM-dd"))
                self.rel_notes.setPlainText(rel.get('notes', ''))

                # Load evidences linked to this relation
                self._current_relation_evidences = rel.get('evidences', [])
                self._refresh_relation_evidence_list()
                break

    def _add_evidence_to_relation(self):
        """Add evidence linked to current relation."""
        dialog = EvidenceDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            evidence_dict = dialog.get_evidence_data()
            if not hasattr(self, '_current_relation_evidences'):
                self._current_relation_evidences = []
            self._current_relation_evidences.append(evidence_dict)
            self._refresh_relation_evidence_list()
            Toast.show_toast(self, "تم إضافة الوثيقة", Toast.SUCCESS)

    def _remove_evidence_from_relation(self):
        """Remove selected evidence from relation."""
        current = self.relation_evidence_list.currentItem()
        if not current:
            return
        ev_id = current.data(Qt.UserRole)
        self._current_relation_evidences = [e for e in self._current_relation_evidences if e['evidence_id'] != ev_id]
        self._refresh_relation_evidence_list()

    def _refresh_relation_evidence_list(self):
        """Refresh evidence list for current relation."""
        self.relation_evidence_list.clear()
        doc_types = dict(EvidenceDialog.DOCUMENT_TYPES)
        for ev in getattr(self, '_current_relation_evidences', []):
            type_ar = doc_types.get(ev['document_type'], ev['document_type'])
            text = f"📄 {type_ar}"
            if ev.get('document_number'):
                text += f" - {ev['document_number']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, ev['evidence_id'])
            self.relation_evidence_list.addItem(item)

    def _save_relation(self):
        """Save person-unit relation with linked evidences."""
        # Check if widgets exist
        if not hasattr(self, 'rel_person_combo') or self.rel_person_combo is None:
            return

        try:
            if self.rel_person_combo.count() == 0:
                QMessageBox.warning(self, "خطأ", "لا يوجد أشخاص لتحديد العلاقة")
                return
        except RuntimeError:
            # Widget was deleted
            return

        # Build evidence list from uploaded files
        evidences = []
        if hasattr(self, '_relation_file_paths') and self._relation_file_paths:
            for file_path in self._relation_file_paths:
                try:
                    evidence = {
                        "evidence_id": str(uuid.uuid4()),
                        "document_type": self.rel_evidence_type.currentText() if hasattr(self, 'rel_evidence_type') and self.rel_evidence_type and self.rel_evidence_type.currentIndex() > 0 else "غير محدد",
                        "description": self.rel_evidence_desc.text().strip() if hasattr(self, 'rel_evidence_desc') and self.rel_evidence_desc else None,
                        "file_path": file_path,
                        "upload_date": datetime.now().strftime("%Y-%m-%d")
                    }
                    evidences.append(evidence)
                except RuntimeError:
                    continue

        try:
            relation = {
                "relation_id": str(uuid.uuid4()) if not hasattr(self, '_editing_relation_index') or self._editing_relation_index is None else self.context.relations[self._editing_relation_index]['relation_id'],
                "person_id": self.rel_person_combo.currentData() if hasattr(self, 'rel_person_combo') and self.rel_person_combo else None,
                "person_name": self.rel_person_combo.currentText() if hasattr(self, 'rel_person_combo') and self.rel_person_combo else "",
                "relation_type": self.rel_type_combo.currentData() if hasattr(self, 'rel_type_combo') and self.rel_type_combo else None,
                "ownership_share": self.rel_share.value() if hasattr(self, 'rel_share') and self.rel_share else 0,
                "start_date": self.rel_start_date.date().toString("yyyy-MM-dd") if hasattr(self, 'rel_start_date') and self.rel_start_date else datetime.now().strftime("%Y-%m-%d"),
                "contract_type": self.rel_contract_type.currentText() if hasattr(self, 'rel_contract_type') and self.rel_contract_type and self.rel_contract_type.currentIndex() > 0 else None,
                "evidence_type": self.rel_evidence_type.currentText() if hasattr(self, 'rel_evidence_type') and self.rel_evidence_type and self.rel_evidence_type.currentIndex() > 0 else None,
                "evidence_description": self.rel_evidence_desc.text().strip() if hasattr(self, 'rel_evidence_desc') and self.rel_evidence_desc else None,
                "notes": self.rel_notes.toPlainText().strip() if hasattr(self, 'rel_notes') and self.rel_notes else "",
                "evidences": evidences
            }
        except RuntimeError:
            # Widgets were deleted
            return

        if hasattr(self, '_editing_relation_index') and self._editing_relation_index is not None:
            self.context.relations[self._editing_relation_index] = relation
            Toast.show_toast(self, "تم تحديث العلاقة", Toast.SUCCESS)
        else:
            self.context.relations.append(relation)
            Toast.show_toast(self, "تم حفظ العلاقة", Toast.SUCCESS)

        self._refresh_relations_list()
        self._add_relation()
        self.next_btn.setEnabled(True)

    def _delete_relation(self):
        """Delete current relation (for unified card design)."""
        # In the new design, we don't have a list to select from
        # This method is kept for compatibility but may need reimplementation
        # if delete functionality is needed in the unified card design
        pass

    def _refresh_relations_list(self):
        """Refresh relations display (no-op for unified card design)."""
        # The new Step 5 design uses a single form instead of a list
        # This method is kept for compatibility but does nothing
        pass

    # ==================== Step 6: Claim (S17-S18) ====================

    def _create_claim_step(self) -> QWidget:
        """Create Step 6: Claim Creation (S17-S18)."""
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet("""
            QLabel {
                color: #444;
                font-weight: bold;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 10px;
                color: #606266;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #409eff;
            }
        """)

        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(40, 20, 40, 40)
        main_layout.setSpacing(10)

        # --- Header Section (Outside the Card) ---
        header_layout = QHBoxLayout()

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("تسجيل الحالة")
        title_lbl.setStyleSheet("font-size: 22px; color: #2c3e50; font-weight: bold;")
        #title_lbl.setAlignment(Qt.AlignRight)
        sub_lbl = QLabel("ربط المطالبين بالوحدات العقارية وتتبع مطالبات تسجيل حقوق الحيازة")
        sub_lbl.setStyleSheet("font-weight: normal; color: #909399; font-size: 14px;")
        sub_lbl.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)

        icon_label = QLabel()
        icon_label.setFixedSize(50, 50)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 24px; background: #ffffff; border-radius: 10px; border: 1px solid #ebeef5;")

        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(10)

        # --- The Main Card (QFrame) ---
        card = QFrame()
        card.setStyleSheet("""
            QFrame#ClaimCard {
                background-color: white;
                border-radius: 15px;
                border: 1px solid #e4e7ed;
            }
        """)
        card.setObjectName("ClaimCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 25, 25, 25)
        card_layout.setSpacing(20)

        # 1. Grid Layout for top fields (RTL order: right to left)
        grid = QGridLayout()
        grid.setSpacing(15)

        # Ensure columns stretch to fill full width
        for i in range(4):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, field_widget, row, col):
            v = QVBoxLayout()
            lbl = QLabel(label_text)
          #  lbl.setAlignment(Qt.AlignRight)
            v.addWidget(lbl)
            v.addWidget(field_widget)
            grid.addLayout(v, row, col)

        # Row 1 (RTL): معرف المطالب | معرف الوحدة المطالب بها | نوع الحالة | طبيعة الأعمال
        self.claim_person_search = QLineEdit()
        self.claim_person_search.setPlaceholderText("اسم الشخص")
        add_field("معرف المطالب", self.claim_person_search, 0, 0)

        self.claim_unit_search = QLineEdit()
        self.claim_unit_search.setPlaceholderText("رقم الوحدة")
        add_field("معرف الوحدة المطالب بها", self.claim_unit_search, 0, 1)

        self.claim_type_combo = QComboBox()
        self.claim_type_combo.addItem("اختر", "")
        self.claim_type_combo.addItem("ملكية", "ownership")
        self.claim_type_combo.addItem("إشغال", "occupancy")
        self.claim_type_combo.addItem("إيجار", "tenancy")
        add_field("نوع الحالة", self.claim_type_combo, 0, 2)

        self.claim_business_nature = QComboBox()
        self.claim_business_nature.addItem("اختر", "")
        self.claim_business_nature.addItem("سكني", "residential")
        self.claim_business_nature.addItem("تجاري", "commercial")
        self.claim_business_nature.addItem("زراعي", "agricultural")
        add_field("طبيعة الأعمال", self.claim_business_nature, 0, 3)

        # Row 2 (RTL): حالة الحالة | المصدر | تاريخ المسح | الأولوية
        self.claim_status_combo = QComboBox()
        self.claim_status_combo.addItem("اختر", "")
        self.claim_status_combo.addItem("جديد", "new")
        self.claim_status_combo.addItem("قيد المراجعة", "under_review")
        self.claim_status_combo.addItem("مكتمل", "completed")
        self.claim_status_combo.addItem("معلق", "pending")
        add_field("حالة الحالة", self.claim_status_combo, 1, 0)

        self.claim_source_combo = QComboBox()
        self.claim_source_combo.addItem("اختر", "")
        self.claim_source_combo.addItem("مسح ميداني", "field_survey")
        self.claim_source_combo.addItem("طلب مباشر", "direct_request")
        self.claim_source_combo.addItem("إحالة", "referral")
        add_field("المصدر", self.claim_source_combo, 1, 1)

        self.claim_survey_date = QDateEdit()
        self.claim_survey_date.setCalendarPopup(True)
        self.claim_survey_date.setDisplayFormat("dd-MM-yyyy")
        self.claim_survey_date.setDate(QDate.currentDate())
        add_field("تاريخ المسح", self.claim_survey_date, 1, 2)

        self.claim_priority_combo = QComboBox()
        self.claim_priority_combo.addItem("اختر", "")
        self.claim_priority_combo.addItem("منخفض", "low")
        self.claim_priority_combo.addItem("عادي", "normal")
        self.claim_priority_combo.addItem("عالي", "high")
        self.claim_priority_combo.addItem("عاجل", "urgent")
        self.claim_priority_combo.setCurrentIndex(2)  # Default to normal
        add_field("الأولوية", self.claim_priority_combo, 1, 3)

        card_layout.addLayout(grid)

        # 2. Notes Section
        notes_label = QLabel("ملاحظات المراجعة")
       # notes_label.setAlignment(Qt.AlignRight)
        card_layout.addWidget(notes_label)
        self.claim_notes = QTextEdit()
        self.claim_notes.setPlaceholderText("ملاحظات إضافية")
        self.claim_notes.setMinimumHeight(100)
        self.claim_notes.setMaximumHeight(120)
        card_layout.addWidget(self.claim_notes)

        # 3. Next Action Date Section
        next_date_label = QLabel("تاريخ الإجراء التالي")
       # next_date_label.setAlignment(Qt.AlignRight)
        card_layout.addWidget(next_date_label)
        next_date_container = QHBoxLayout()
        self.claim_next_action_date = QDateEdit()
        self.claim_next_action_date.setCalendarPopup(True)
        self.claim_next_action_date.setDisplayFormat("dd-MM-yyyy")
        self.claim_next_action_date.setMinimumHeight(45)
        next_date_container.addWidget(self.claim_next_action_date)
        card_layout.addLayout(next_date_container)

        # 4. Status Bar (Inside Card) - Evidence available indicator
        self.claim_eval_label = QLabel("الأدلة متوفرة")
        self.claim_eval_label.setAlignment(Qt.AlignCenter)
        self.claim_eval_label.setFixedHeight(50)
        self.claim_eval_label.setStyleSheet("""
            background-color: #e1f7ef;
            color: #10b981;
            border-radius: 8px;
            font-weight: bold;
            font-size: 15px;
        """)
        card_layout.addWidget(self.claim_eval_label)

        main_layout.addWidget(card)
        main_layout.addStretch()

        return widget

    def _evaluate_for_claim(self):
        """Evaluate relations for claim creation (S17)."""
        owners = [r for r in self.context.relations if r['relation_type'] in ('owner', 'co_owner')]
        tenants = [r for r in self.context.relations if r['relation_type'] == 'tenant']
        occupants = [r for r in self.context.relations if r['relation_type'] == 'occupant']
        heirs = [r for r in self.context.relations if r['relation_type'] == 'heir']

        # Count total evidences
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)

        # Auto-populate unit ID if available
        if self.context.unit:
            self.claim_unit_search.setText(str(self.context.unit.unit_id or ""))

        # Auto-populate claimant name from first person
        if self.context.persons:
            first_person = self.context.persons[0]
            full_name = f"{first_person.get('first_name', '')} {first_person.get('last_name', '')}"
            self.claim_person_search.setText(full_name.strip())

        # Auto-select claim type based on relations
        if owners or heirs:
            # Find index for "ownership"
            for i in range(self.claim_type_combo.count()):
                if self.claim_type_combo.itemData(i) == "ownership":
                    self.claim_type_combo.setCurrentIndex(i)
                    break
        elif tenants:
            for i in range(self.claim_type_combo.count()):
                if self.claim_type_combo.itemData(i) == "tenancy":
                    self.claim_type_combo.setCurrentIndex(i)
                    break
        elif occupants:
            for i in range(self.claim_type_combo.count()):
                if self.claim_type_combo.itemData(i) == "occupancy":
                    self.claim_type_combo.setCurrentIndex(i)
                    break

        # Update status bar based on evidence availability
        if total_evidences > 0:
            self.claim_eval_label.setText(f"الأدلة متوفرة ({total_evidences})")
            self.claim_eval_label.setStyleSheet("""
                background-color: #e1f7ef;
                color: #10b981;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            """)
        else:
            self.claim_eval_label.setText("لا توجد أدلة مرفقة")
            self.claim_eval_label.setStyleSheet("""
                background-color: #fef3c7;
                color: #f59e0b;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
            """)

    def _save_claim_data(self):
        """Save claim data from the form to context (auto-save on navigation)."""
        # Check if widgets exist
        if not hasattr(self, 'claim_type_combo') or self.claim_type_combo is None:
            return

        try:
            # Collect all claimant person IDs
            claimant_ids = [r['person_id'] for r in self.context.relations
                            if r['relation_type'] in ('owner', 'co_owner', 'heir')]
            if not claimant_ids:
                claimant_ids = [r['person_id'] for r in self.context.relations]

            # Collect all evidences
            all_evidences = []
            for rel in self.context.relations:
                all_evidences.extend(rel.get('evidences', []))

            self.context.claim_data = {
                "claim_type": self.claim_type_combo.currentData() if hasattr(self, 'claim_type_combo') and self.claim_type_combo else None,
                "priority": self.claim_priority_combo.currentData() if hasattr(self, 'claim_priority_combo') and self.claim_priority_combo else None,
                "business_nature": self.claim_business_nature.currentData() if hasattr(self, 'claim_business_nature') and self.claim_business_nature else None,
                "source": self.claim_source_combo.currentData() if hasattr(self, 'claim_source_combo') and self.claim_source_combo else "OFFICE_SUBMISSION",
                "case_status": self.claim_status_combo.currentData() if hasattr(self, 'claim_status_combo') and self.claim_status_combo else "new",
                "survey_date": self.claim_survey_date.date().toString("yyyy-MM-dd") if hasattr(self, 'claim_survey_date') and self.claim_survey_date else None,
                "next_action_date": self.claim_next_action_date.date().toString("yyyy-MM-dd") if hasattr(self, 'claim_next_action_date') and self.claim_next_action_date else None,
                "notes": self.claim_notes.toPlainText().strip() if hasattr(self, 'claim_notes') and self.claim_notes else "",
                "status": "draft",
                "claimant_person_ids": claimant_ids,
                "evidence_ids": [e['evidence_id'] for e in all_evidences],
                "unit_id": self.context.unit.unit_id if self.context.unit else None,
                "building_id": self.context.building.building_id if self.context.building else None
            }
        except RuntimeError:
            # Widgets were deleted
            pass

    def _create_claim(self):
        """Create the claim (S18) - legacy method, now uses _save_claim_data."""
        self._save_claim_data()
        Toast.show_toast(self, "تم إعداد المطالبة - انتقل للمراجعة النهائية", Toast.SUCCESS)
        self.next_btn.setEnabled(True)

    # ==================== Step 7: Review (S19-S21) ====================

    def _create_review_step(self) -> QWidget:
        """Create Step 7: Final Review with full validation (S19-S21)."""
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet("""
            QLabel {
                color: #444;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                background-color: #f9fafb;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 10px;
                color: #606266;
            }
        """)

        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(40, 20, 40, 40)
        main_layout.setSpacing(15)

        # --- Header Section ---
        header_layout = QHBoxLayout()

        title_vbox = QVBoxLayout()
        title_lbl = QLabel("المراجعة النهائية")
        title_lbl.setStyleSheet("font-size: 22px; color: #2c3e50; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignRight)
        sub_lbl = QLabel("مراجعة جميع البيانات المدخلة قبل الإرسال")
        sub_lbl.setStyleSheet("font-weight: normal; color: #909399; font-size: 14px;")
        sub_lbl.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)

        # Reference number badge
        self.review_ref_label = QLabel("")
        self.review_ref_label.setStyleSheet(f"""
            background-color: {Config.SUCCESS_COLOR};
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: bold;
        """)

        header_layout.addWidget(self.review_ref_label)
        header_layout.addStretch()
        header_layout.addLayout(title_vbox)
        main_layout.addLayout(header_layout)

        # --- Validation Status Frame ---
        self.validation_frame = QFrame()
        self.validation_frame.setStyleSheet("""
            QFrame { border-radius: 8px; padding: 12px; }
        """)
        val_layout = QVBoxLayout(self.validation_frame)
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setAlignment(Qt.AlignRight)
        val_layout.addWidget(self.validation_label)
        main_layout.addWidget(self.validation_frame)

        # --- Scroll Area for Review Cards ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        review_content = QWidget()
        review_layout = QVBoxLayout(review_content)
        review_layout.setSpacing(20)

        # Card 1: Unit Information (Step 2)
        self.review_unit_card = self._create_review_card("الوحدة العقارية", "step2")
        review_layout.addWidget(self.review_unit_card)

        # Card 2: Household Information (Step 3)
        self.review_household_card = self._create_review_card("الأسرة والإشغال", "step3")
        review_layout.addWidget(self.review_household_card)

        # Card 3: Persons Information (Step 4)
        self.review_persons_card = self._create_review_card("الأشخاص المسجلين", "step4")
        review_layout.addWidget(self.review_persons_card)

        # Card 4: Relations Information (Step 5)
        self.review_relations_card = self._create_review_card("العلاقات والأدلة", "step5")
        review_layout.addWidget(self.review_relations_card)

        # Card 5: Claim Information (Step 6)
        self.review_claim_card = self._create_review_card("تسجيل الحالة", "step6")
        review_layout.addWidget(self.review_claim_card)

        review_layout.addStretch()
        scroll.setWidget(review_content)
        main_layout.addWidget(scroll)

        # --- Final Submit Button ---
        submit_btn = QPushButton("تأكيد وإنهاء المسح")
        submit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 16px 32px;
                font-size: 14pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        submit_btn.clicked.connect(self._finalize_survey)
        main_layout.addWidget(submit_btn)

        return widget

    def _create_review_card(self, title: str, step_id: str) -> QFrame:
        """Create a review card matching the style of other steps."""
        card = QFrame()
        card.setObjectName(f"review_card_{step_id}")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 15px;
                border: 1px solid #e4e7ed;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 20, 25, 20)
        card_layout.setSpacing(15)

        # Card Header
        header_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; color: #2c3e50; font-weight: bold;")
        title_label.setAlignment(Qt.AlignRight)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # Content Grid (will be populated dynamically)
        content_widget = QWidget()
        content_widget.setObjectName(f"content_{step_id}")
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_layout = QGridLayout(content_widget)
        content_layout.setSpacing(15)
        for i in range(4):
            content_layout.setColumnStretch(i, 1)
        card_layout.addWidget(content_widget)

        return card

    def _create_review_field(self, label_text: str, value_text: str) -> QVBoxLayout:
        """Create a read-only field for review display."""
        v = QVBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-weight: bold; color: #444; font-size: 12px;")
        lbl.setAlignment(Qt.AlignRight)
        lbl.setLayoutDirection(Qt.RightToLeft)

        value = QLineEdit(value_text)
        value.setReadOnly(True)
        value.setAlignment(Qt.AlignRight)
        value.setLayoutDirection(Qt.RightToLeft)
        value.setStyleSheet("""
            QLineEdit {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 10px;
                color: #374151;
                text-align: right;
            }
        """)

        v.addWidget(lbl)
        v.addWidget(value)
        return v

    def _create_review_section(self, title: str, content: str) -> QFrame:
        """Create a review section frame (legacy method for compatibility)."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(frame)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: #374151; font-size: 11pt;")
        layout.addWidget(title_label)

        content_label = QLabel(content)
        content_label.setObjectName("content")
        content_label.setStyleSheet("color: #6B7280;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        return frame

    def _run_final_validation(self) -> tuple:
        """Run comprehensive final validation (S20)."""
        errors = []
        warnings = []

        # Required checks
        if not self.context.building:
            errors.append("لم يتم اختيار مبنى")

        if not self.context.unit and not self.context.is_new_unit:
            errors.append("لم يتم اختيار أو إنشاء وحدة عقارية")

        if len(self.context.households) == 0:
            warnings.append("لم يتم تسجيل أي أسرة")

        if len(self.context.persons) == 0:
            errors.append("لم يتم تسجيل أي شخص")

        if len(self.context.relations) == 0:
            warnings.append("لم يتم تحديد أي علاقات")

        # Check for contact person
        has_contact = any(p.get('is_contact_person') for p in self.context.persons)
        if not has_contact and len(self.context.persons) > 0:
            warnings.append("لم يتم تحديد شخص تواصل رئيسي")

        # Check evidences
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)
        if total_evidences == 0:
            warnings.append("لم يتم إرفاق أي وثائق داعمة")

        # Check claim
        if not self.context.claim_data:
            warnings.append("لم يتم إنشاء المطالبة")

        return errors, warnings

    def _populate_review(self):
        """Populate the review step with all collected data (S19)."""
        # Reference number
        self.review_ref_label.setText(f"الرقم المرجعي: {self.context.reference_number}")

        # Run validation
        errors, warnings = self._run_final_validation()

        if errors:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FEE2E2;
                    border: 1px solid {Config.ERROR_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            val_text = "أخطاء يجب تصحيحها:\n" + "\n".join(f"• {e}" for e in errors)
            if warnings:
                val_text += "\n\nتحذيرات:\n" + "\n".join(f"• {w}" for w in warnings)
            self.validation_label.setText(val_text)
        elif warnings:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FEF3C7;
                    border: 1px solid {Config.WARNING_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            self.validation_label.setText("تحذيرات:\n" + "\n".join(f"• {w}" for w in warnings))
        else:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #D1FAE5;
                    border: 1px solid {Config.SUCCESS_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            self.validation_label.setText("جميع البيانات مكتملة وجاهزة للحفظ")

        # Populate Card 1: Unit Information (Step 2)
        self._populate_unit_review_card()

        # Populate Card 2: Household Information (Step 3)
        self._populate_household_review_card()

        # Populate Card 3: Persons Information (Step 4)
        self._populate_persons_review_card()

        # Populate Card 4: Relations Information (Step 5)
        self._populate_relations_review_card()

        # Populate Card 5: Claim Information (Step 6)
        self._populate_claim_review_card()

    def _clear_grid_layout(self, grid_layout):
        """Clear all items from a grid layout."""
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        """Recursively clear a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _populate_unit_review_card(self):
        """Populate the unit review card (Step 2 data)."""
        content_widget = self.review_unit_card.findChild(QWidget, "content_step2")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        # Building info
        building_id = self.context.building.building_id if self.context.building else "-"
        building_type = self.context.building.building_type_display if self.context.building and hasattr(self.context.building, 'building_type_display') else "-"

        # Unit info
        if self.context.unit:
            unit_id = str(self.context.unit.unit_id) if self.context.unit.unit_id else "-"
            unit_type = self.context.unit.unit_type_display if hasattr(self.context.unit, 'unit_type_display') else "-"
            floor = str(self.context.unit.floor_number) if hasattr(self.context.unit, 'floor_number') and self.context.unit.floor_number else "-"
            apartment = str(self.context.unit.apartment_number) if hasattr(self.context.unit, 'apartment_number') and self.context.unit.apartment_number else "-"
        elif self.context.is_new_unit and self.context.new_unit_data:
            unit_id = "جديد"
            unit_type = self.context.new_unit_data.get('unit_type', '-')
            floor = str(self.context.new_unit_data.get('floor_number', '-'))
            apartment = str(self.context.new_unit_data.get('apartment_number', '-'))
        else:
            unit_id = "-"
            unit_type = "-"
            floor = "-"
            apartment = "-"

        # Add fields to grid (RTL order)
        grid.addLayout(self._create_review_field("رقم المبنى", building_id), 0, 0)
        grid.addLayout(self._create_review_field("نوع المبنى", building_type), 0, 1)
        grid.addLayout(self._create_review_field("رقم الوحدة", unit_id), 0, 2)
        grid.addLayout(self._create_review_field("نوع الوحدة", unit_type), 0, 3)
        grid.addLayout(self._create_review_field("الطابق", floor), 1, 0)
        grid.addLayout(self._create_review_field("رقم الشقة", apartment), 1, 1)

    def _populate_household_review_card(self):
        """Populate the household review card (Step 3 data)."""
        content_widget = self.review_household_card.findChild(QWidget, "content_step3")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        num_households = str(len(self.context.households))
        total_persons = str(sum(h.get('size', 0) for h in self.context.households))
        total_adults = str(sum(h.get('adults', 0) for h in self.context.households))
        total_minors = str(sum(h.get('minors', 0) for h in self.context.households))

        # First household head name
        head_name = self.context.households[0].get('head_name', '-') if self.context.households else "-"

        grid.addLayout(self._create_review_field("عدد الأسر", num_households), 0, 0)
        grid.addLayout(self._create_review_field("إجمالي الأفراد", total_persons), 0, 1)
        grid.addLayout(self._create_review_field("البالغين", total_adults), 0, 2)
        grid.addLayout(self._create_review_field("القاصرين", total_minors), 0, 3)
        grid.addLayout(self._create_review_field("رب الأسرة", head_name), 1, 0)

    def _populate_persons_review_card(self):
        """Populate the persons review card (Step 4 data)."""
        content_widget = self.review_persons_card.findChild(QWidget, "content_step4")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        num_persons = str(len(self.context.persons))
        contact_person = next((f"{p['first_name']} {p['last_name']}" for p in self.context.persons if p.get('is_contact_person')), "-")

        # List first 3 persons
        person_names = []
        for i, p in enumerate(self.context.persons[:3]):
            person_names.append(f"{p['first_name']} {p['last_name']}")

        grid.addLayout(self._create_review_field("عدد الأشخاص", num_persons), 0, 0)
        grid.addLayout(self._create_review_field("شخص التواصل", contact_person), 0, 1)

        # Show persons in remaining columns
        for i, name in enumerate(person_names):
            grid.addLayout(self._create_review_field(f"الشخص {i+1}", name), 0 if i < 2 else 1, 2 + (i % 2))

    def _populate_relations_review_card(self):
        """Populate the relations review card (Step 5 data)."""
        content_widget = self.review_relations_card.findChild(QWidget, "content_step5")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        num_relations = str(len(self.context.relations))
        total_evidences = str(sum(len(r.get('evidences', [])) for r in self.context.relations))

        rel_type_map = {"owner": "مالك", "co_owner": "شريك", "tenant": "مستأجر", "occupant": "شاغل", "heir": "وارث"}

        # Count by relation type
        owners = len([r for r in self.context.relations if r['relation_type'] in ('owner', 'co_owner')])
        tenants = len([r for r in self.context.relations if r['relation_type'] == 'tenant'])

        grid.addLayout(self._create_review_field("عدد العلاقات", num_relations), 0, 0)
        grid.addLayout(self._create_review_field("إجمالي الوثائق", total_evidences), 0, 1)
        grid.addLayout(self._create_review_field("الملاك/الشركاء", str(owners)), 0, 2)
        grid.addLayout(self._create_review_field("المستأجرين", str(tenants)), 0, 3)

        # Show first relation details
        if self.context.relations:
            r = self.context.relations[0]
            type_ar = rel_type_map.get(r['relation_type'], r['relation_type'])
            grid.addLayout(self._create_review_field("الشخص", r.get('person_name', '-')), 1, 0)
            grid.addLayout(self._create_review_field("نوع العلاقة", type_ar), 1, 1)

    def _populate_claim_review_card(self):
        """Populate the claim review card (Step 6 data)."""
        content_widget = self.review_claim_card.findChild(QWidget, "content_step6")
        grid = content_widget.layout()
        self._clear_grid_layout(grid)

        claim_types = {"ownership": "ملكية", "occupancy": "إشغال", "tenancy": "إيجار", "": "-", None: "-"}
        priorities = {"low": "منخفض", "normal": "عادي", "high": "عالي", "urgent": "عاجل", "": "-", None: "-"}
        business_types = {"residential": "سكني", "commercial": "تجاري", "agricultural": "زراعي", "": "-", None: "-"}
        sources = {"field_survey": "مسح ميداني", "direct_request": "طلب مباشر", "referral": "إحالة", "OFFICE_SUBMISSION": "تقديم مكتبي", "": "-", None: "-"}
        statuses = {"new": "جديد", "under_review": "قيد المراجعة", "completed": "مكتمل", "pending": "معلق", "": "-", None: "-"}

        if self.context.claim_data:
            claim_type = claim_types.get(self.context.claim_data.get('claim_type'), '-')
            priority = priorities.get(self.context.claim_data.get('priority'), '-')
            business = business_types.get(self.context.claim_data.get('business_nature'), '-')
            source = sources.get(self.context.claim_data.get('source'), '-')
            status = statuses.get(self.context.claim_data.get('case_status'), '-')
            survey_date = self.context.claim_data.get('survey_date', '-') or '-'
            next_date = self.context.claim_data.get('next_action_date', '-') or '-'
            num_claimants = str(len(self.context.claim_data.get('claimant_person_ids', [])))
        else:
            claim_type = "-"
            priority = "-"
            business = "-"
            source = "-"
            status = "-"
            survey_date = "-"
            next_date = "-"
            num_claimants = "0"

        # Row 1
        grid.addLayout(self._create_review_field("نوع الحالة", claim_type), 0, 0)
        grid.addLayout(self._create_review_field("طبيعة الأعمال", business), 0, 1)
        grid.addLayout(self._create_review_field("الأولوية", priority), 0, 2)
        grid.addLayout(self._create_review_field("المصدر", source), 0, 3)

        # Row 2
        grid.addLayout(self._create_review_field("حالة الحالة", status), 1, 0)
        grid.addLayout(self._create_review_field("تاريخ المسح", survey_date), 1, 1)
        grid.addLayout(self._create_review_field("تاريخ الإجراء التالي", next_date), 1, 2)
        grid.addLayout(self._create_review_field("عدد المطالبين", num_claimants), 1, 3)

    def _finalize_survey(self):
        """Finalize and save the survey (S20-S21)."""
        errors, warnings = self._run_final_validation()

        if errors:
            QMessageBox.critical(
                self, "خطأ",
                "لا يمكن إنهاء المسح بسبب الأخطاء التالية:\n\n" +
                "\n".join(f"• {e}" for e in errors)
            )
            return

        if warnings:
            reply = QMessageBox.question(
                self, "تحذير",
                "هناك تحذيرات:\n" + "\n".join(f"• {w}" for w in warnings) +
                "\n\nهل تريد المتابعة على أي حال؟",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Commit to database (S21)
        try:
            self._commit_survey()
            self.context.status = "finalized"
            self.context.updated_at = datetime.now()

            QMessageBox.information(
                self, "نجاح",
                f"تم إنهاء المسح بنجاح!\n\n"
                f"الرقم المرجعي: {self.context.reference_number}\n"
                f"رقم المسح: {self.context.survey_id[:8]}"
            )

            self.survey_completed.emit(self.context.survey_id)

        except Exception as e:
            logger.error(f"Failed to finalize survey: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل في حفظ المسح: {str(e)}")

    def _commit_survey(self):
        """
        Commit all survey data to database (S21 - Transactional save).
        Implements UC-005: Saves finalized survey to database.
        """
        logger.info(f"Committing survey {self.context.survey_id}")

        try:
            # 1. Create unit if new
            if self.context.is_new_unit and self.context.new_unit_data:
                unit_data = self.context.new_unit_data
                new_unit = Unit(
                    unit_type=unit_data.get('unit_type'),
                    floor_number=unit_data.get('floor_number'),
                    apartment_number=unit_data.get('apartment_number'),
                    area_sqm=unit_data.get('area'),
                    building_id=unit_data.get('building_id')
                )
                self.unit_repo.create(new_unit)
                self.context.unit = new_unit
                logger.info(f"  Created unit: {new_unit.unit_id}")

            # 2. Create/update persons
            for p_data in self.context.persons:
                person = Person(
                    first_name_ar=p_data['first_name'],
                    father_name_ar=p_data.get('father_name'),
                    last_name_ar=p_data['last_name'],
                    national_id=p_data.get('national_id'),
                    gender=p_data.get('gender'),
                    year_of_birth=p_data.get('year_of_birth'),
                    phone_primary=p_data.get('phone')
                )
                self.person_repo.create(person)
                p_data['db_person_id'] = person.person_id
                logger.info(f"  Created person: {person.person_id}")

            # 3. Create claim
            if self.context.claim_data:
                claim = Claim(
                    claim_type=self.context.claim_data['claim_type'],
                    priority=self.context.claim_data['priority'],
                    source=self.context.claim_data['source'],
                    unit_id=self.context.unit.unit_id if self.context.unit else None,
                    case_status='draft',
                    notes=self.context.claim_data.get('notes')
                )
                self.claim_repo.create(claim)
                logger.info(f"  Created claim: {claim.claim_id}")

            # 4. Save/update survey metadata to surveys table
            survey_data = self.context.to_dict()
            survey_data['status'] = 'finalized'  # Mark as finalized

            # Check if survey exists
            existing_survey = self.survey_repo.get_by_id(self.context.survey_id)

            if existing_survey:
                # Update existing survey (was draft, now finalized)
                self.survey_repo.update(self.context.survey_id, survey_data)
                logger.info(f"  Updated survey status to finalized: {self.context.survey_id}")
            else:
                # Create new survey record
                self.survey_repo.create(survey_data)
                logger.info(f"  Created finalized survey: {self.context.survey_id}")

            logger.info(f"Survey {self.context.survey_id} committed successfully")

        except Exception as e:
            logger.error(f"Transaction failed: {e}", exc_info=True)
            raise

    # ==================== Navigation ====================

    def _update_step_display(self):
        """Update step indicators."""
        for i, label in enumerate(self.step_labels):
            if i < self.current_step:
                # Completed
                label.setStyleSheet(f"""
                    background-color: {Config.SUCCESS_COLOR};
                    color: white;
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                """)
            elif i == self.current_step:
                # Active
                label.setStyleSheet(f"""
                    background-color: {Config.PRIMARY_COLOR};
                    color: white;
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                    font-weight: bold;
                """)
            else:
                # Pending
                label.setStyleSheet(f"""
                    background-color: {Config.BACKGROUND_COLOR};
                    color: {Config.TEXT_LIGHT};
                    padding: 6px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                """)

        self.content_stack.setCurrentIndex(self.current_step)
        self.prev_btn.setEnabled(self.current_step > 0)

        # Update next button for final step
        if self.current_step == self.STEP_REVIEW:
            self.next_btn.hide()
        else:
            self.next_btn.show()

    def _on_previous(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_display()
            self.next_btn.setEnabled(True)

    def _on_next(self):
        """Go to next step with validation."""
        if not self._validate_current_step():
            return

        if self.current_step < self.STEP_REVIEW:
            self.current_step += 1
            self._prepare_step(self.current_step)
            self._update_step_display()

    def _validate_current_step(self) -> bool:
        """Validate current step before proceeding."""
        if self.current_step == self.STEP_BUILDING:
            if not self.context.building:
                QMessageBox.warning(self, "خطأ", "يجب اختيار مبنى للمتابعة")
                return False

        elif self.current_step == self.STEP_UNIT:
            if not self.context.unit and not self.context.is_new_unit:
                QMessageBox.warning(self, "خطأ", "يجب اختيار أو إنشاء وحدة عقارية")
                return False
            if self.context.is_new_unit:
                self._save_new_unit_data()

        elif self.current_step == self.STEP_RELATIONS:
            # Auto-save the current relation when moving to next step
            if self.rel_person_combo.currentData():
                self._save_relation()
                return True
            # Allow moving to next step even without saving if there are existing relations
            elif len(self.context.relations) > 0:
                return True
            else:
                QMessageBox.warning(self, "خطأ", "يجب إضافة علاقة واحدة على الأقل للمتابعة")
                return False

        elif self.current_step == self.STEP_CLAIM:
            # Auto-save claim data when moving to review step
            self._save_claim_data()
            return True

        return True

    def _format_unit_building_info(self, building: Building):
        """Format building info for unit step with search + metrics layout."""
        if not building:
            return

        # Set building address label
        if hasattr(building, 'full_address_ar') and building.full_address_ar:
            address = building.full_address_ar
        else:
            address = "حلب - المحدثة - اسم الناحية - اسم التجمع - اسم الحي - رقم البناء - رقم الوحدة العقارية"
        self.unit_building_address.setText(address)

        # Clear existing metrics
        while self.unit_building_metrics_layout.count():
            child = self.unit_building_metrics_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Get building data
        status_display = building.building_status_display if hasattr(building, 'building_status_display') else "منتظر"
        type_display = building.building_type_display if hasattr(building, 'building_type_display') else "سكني"
        num_units = str(building.number_of_units) if hasattr(building, 'number_of_units') and building.number_of_units else "0"
        num_apartments = str(building.number_of_apartments) if hasattr(building, 'number_of_apartments') and building.number_of_apartments else "0"
        num_shops = str(building.number_of_shops) if hasattr(building, 'number_of_shops') and building.number_of_shops else "0"

        # Add metrics
        self.unit_building_metrics_layout.addWidget(self._create_metric_widget("حالة البناء", status_display))
        self.unit_building_metrics_layout.addWidget(self._create_metric_widget("نوع البناء", type_display))
        self.unit_building_metrics_layout.addWidget(self._create_metric_widget("عدد الوحدات", num_units))
        self.unit_building_metrics_layout.addWidget(self._create_metric_widget("عدد المقاسم", num_apartments))
        self.unit_building_metrics_layout.addWidget(self._create_metric_widget("عدد المحلات", num_shops))

    def _format_household_building_info(self, building: Building):
        """Format building info for household step with search + metrics layout."""
        if not building:
            return

        # Set building address label
        if hasattr(building, 'full_address_ar') and building.full_address_ar:
            address = building.full_address_ar
        else:
            address = "حلب - المحدثة - اسم الناحية - اسم التجمع - اسم الحي - رقم البناء - رقم الوحدة العقارية"
        self.household_building_address.setText(address)

        # Clear existing metrics
        while self.household_building_metrics_layout.count():
            child = self.household_building_metrics_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Get building data
        status_display = building.building_status_display if hasattr(building, 'building_status_display') else "منتظر"
        type_display = building.building_type_display if hasattr(building, 'building_type_display') else "سكني"
        num_units = str(building.number_of_units) if hasattr(building, 'number_of_units') and building.number_of_units else "0"
        num_apartments = str(building.number_of_apartments) if hasattr(building, 'number_of_apartments') and building.number_of_apartments else "0"
        num_shops = str(building.number_of_shops) if hasattr(building, 'number_of_shops') and building.number_of_shops else "0"

        # Add metrics
        self.household_building_metrics_layout.addWidget(self._create_metric_widget("حالة البناء", status_display))
        self.household_building_metrics_layout.addWidget(self._create_metric_widget("نوع البناء", type_display))
        self.household_building_metrics_layout.addWidget(self._create_metric_widget("عدد الوحدات", num_units))
        self.household_building_metrics_layout.addWidget(self._create_metric_widget("عدد المقاسم", num_apartments))
        self.household_building_metrics_layout.addWidget(self._create_metric_widget("عدد المحلات", num_shops))

    def _format_household_unit_info(self, unit):
        """Format unit info for household step with same layout as unit card."""
        # Clear existing widgets
        while self.household_unit_layout.count():
            child = self.household_unit_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        unit_display_num = unit.unit_number or unit.apartment_number or "?"

        # Get unit data
        unit_type_val = unit.unit_type_display if hasattr(unit, 'unit_type_display') else unit.unit_type
        status_val = unit.apartment_status_display if hasattr(unit, 'apartment_status_display') else unit.apartment_status or "جيدة"
        floor_val = str(unit.floor_number) if unit.floor_number is not None else "-"
        rooms_val = str(getattr(unit, 'number_of_rooms', 0)) if hasattr(unit, 'number_of_rooms') else "-"
        area_val = f"{unit.area_sqm} (م²)" if unit.area_sqm else "120 (م²)"

        # Create grid layout for labels and values (6 columns)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(6)

        # Define fields (RTL: first column appears on the right)
        fields = [
            ("رقم الوحدة", str(unit_display_num)),
            ("رقم الطابق", floor_val),
            ("عدد الغرف", rooms_val),
            ("مساحة القسم", area_val),
            ("نوع الوحدة", unit_type_val),
            ("حالة الوحدة", status_val),
        ]

        # Add labels (row 0) and values (row 1)
        for idx, (label_text, value_text) in enumerate(fields):
            # Reverse column order for RTL (rightmost = first item)
            col = 5 - idx

            # Label
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                color: #111827;
                font-weight: 900;
                font-size: 11px;
                border: none;
                background-color: transparent;
            """)
            grid.addWidget(label, 0, col)

            # Value
            value = QLabel(value_text)
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("""
                color: #6B7280;
                font-weight: 700;
                font-size: 12px;
                border: none;
                background-color: transparent;
            """)
            grid.addWidget(value, 1, col)

        self.household_unit_layout.addLayout(grid)

    def _format_household_new_unit_info(self, unit_data: dict):
        """Format new unit info for household step with same layout as unit card."""
        # Clear existing widgets
        while self.household_unit_layout.count():
            child = self.household_unit_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Get unit type display name
        unit_types_map = {
            "apartment": "شقة", "shop": "محل تجاري", "office": "مكتب",
            "warehouse": "مستودع", "garage": "مرآب", "other": "أخرى"
        }
        unit_type = unit_types_map.get(unit_data.get('unit_type', ''), unit_data.get('unit_type', 'شقة'))

        # Get status display name
        status_map = {"intact": "جيدة", "damaged": "متضررة", "destroyed": "مدمرة"}
        status = status_map.get(unit_data.get('apartment_status', ''), unit_data.get('apartment_status', 'جيدة'))

        unit_num = str(unit_data.get('apartment_number', '-'))
        floor = str(unit_data.get('floor_number', '-'))
        rooms = str(unit_data.get('number_of_rooms', '-'))
        area = f"{unit_data.get('area_sqm', '-')} (م²)" if unit_data.get('area_sqm') else "120 (م²)"

        # Create grid layout for labels and values (6 columns)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(6)

        # Define fields (RTL: first column appears on the right)
        fields = [
            ("رقم الوحدة", unit_num),
            ("رقم الطابق", floor),
            ("عدد الغرف", rooms),
            ("مساحة القسم", area),
            ("نوع الوحدة", unit_type),
            ("حالة الوحدة", status),
        ]

        # Add labels (row 0) and values (row 1)
        for idx, (label_text, value_text) in enumerate(fields):
            # Reverse column order for RTL (rightmost = first item)
            col = 5 - idx

            # Label
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                color: #111827;
                font-weight: 900;
                font-size: 11px;
                border: none;
                background-color: transparent;
            """)
            grid.addWidget(label, 0, col)

            # Value
            value = QLabel(value_text)
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("""
                color: #6B7280;
                font-weight: 700;
                font-size: 12px;
                border: none;
                background-color: transparent;
            """)
            grid.addWidget(value, 1, col)

        self.household_unit_layout.addLayout(grid)

    def _create_info_item(self, label: str, value: str) -> QWidget:
        """Create a compact info item (label + value)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-size: 10px; color: #9CA3AF; font-weight: 500;")
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("font-size: 12px; color: #111827; font-weight: 600;")
        layout.addWidget(value_widget)

        return container

    def _prepare_step(self, step: int):
        """Prepare data for a step."""
        if step == self.STEP_UNIT:
            # Populate building info card with search + metrics layout
            if self.context.building:
                self._format_unit_building_info(self.context.building)
            self._load_units_for_building()

        elif step == self.STEP_HOUSEHOLD:
            # Populate building info card
            if self.context.building:
                self._format_household_building_info(self.context.building)

            # Populate unit info card
            if self.context.unit:
                self._format_household_unit_info(self.context.unit)
            elif self.context.is_new_unit and self.context.new_unit_data:
                self._format_household_new_unit_info(self.context.new_unit_data)

            self._refresh_households_list()
            self.next_btn.setEnabled(len(self.context.households) > 0)

        elif step == self.STEP_PERSONS:
            self._refresh_persons_list()
            self.next_btn.setEnabled(len(self.context.persons) > 0)

        elif step == self.STEP_RELATIONS:
            self._populate_relations_persons()
            self._refresh_relations_list()
            self._add_relation()
            # Enable next button if there are existing relations OR if a person is selected
            has_relations = len(self.context.relations) > 0
            has_current_person = self.rel_person_combo.currentData() is not None
            self.next_btn.setEnabled(has_relations or has_current_person)

        elif step == self.STEP_CLAIM:
            self._evaluate_for_claim()
            # Enable next button - form can be filled and proceed to review
            self.next_btn.setEnabled(True)

        elif step == self.STEP_REVIEW:
            self._populate_review()

    def _save_as_draft(self):
        """
        Save current survey as draft with persistence (S22).
        Implements UC-005: Saves draft to database for later resumption.
        """
        self.context.status = "draft"
        self.context.updated_at = datetime.now()

        try:
            # Save draft to database
            draft_data = self.context.to_dict()

            # Check if survey already exists
            existing_survey = self.survey_repo.get_by_id(self.context.survey_id)

            if existing_survey:
                # Update existing draft
                success = self.survey_repo.update(self.context.survey_id, draft_data)
                logger.info(f"Updated draft survey: {self.context.survey_id}")
            else:
                # Create new draft
                survey_id = self.survey_repo.create(draft_data)
                logger.info(f"Created new draft survey: {survey_id}")

            Toast.show_toast(
                self,
                f"✅ تم حفظ المسودة بنجاح\nالرقم المرجعي: {self.context.reference_number}",
                Toast.SUCCESS
            )
            self.survey_saved_draft.emit(self.context.survey_id)

        except Exception as e:
            logger.error(f"Failed to save draft: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "خطأ في الحفظ",
                f"فشل في حفظ المسودة:\n{str(e)}"
            )

    def _on_cancel(self):
        """Cancel the survey (S22)."""
        reply = QMessageBox.question(
            self, "تأكيد الإلغاء",
            "هل تريد إلغاء المسح؟\n\n"
            "يمكنك حفظه كمسودة للعودة إليه لاحقاً.",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )

        if reply == QMessageBox.Save:
            self._save_as_draft()
        elif reply == QMessageBox.Discard:
            self.survey_cancelled.emit()
        # Cancel = do nothing

    def refresh(self, data=None):
        """Reset the wizard for a new survey."""
        self.context = SurveyContext()
        self.current_step = 0
        self._editing_person_index = None

        # Clear all forms
        self.building_search.clear()
        self.buildings_list.clear()

        # Reset button state
        self.next_btn.setEnabled(False)

        # Update display
        self.ref_badge.setText(f"الرقم المرجعي: {self.context.reference_number}")
        self.survey_badge.setText(f"#{self.context.survey_id[:8]}")
        self._update_step_display()
        self._load_buildings()

    def load_draft(self, draft_data: Dict):
        """Load a saved draft survey."""
        self.context = SurveyContext.from_dict(draft_data)
        self.current_step = 0

        # Update UI
        self.ref_badge.setText(f"الرقم المرجعي: {self.context.reference_number}")
        self.survey_badge.setText(f"#{self.context.survey_id[:8]}")
        self._update_step_display()

        Toast.show_toast(self, "تم تحميل المسودة", Toast.INFO)
