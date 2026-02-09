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
    QGridLayout, QCheckBox, QTextEdit, QTabWidget, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QDate

from app.config import Config
from services.validation_service import ValidationService
from services.person_api_service import PersonApiService
from services.survey_api_service import SurveyApiService
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDialog(QDialog):
    """Dialog for creating or editing a person."""

    def __init__(self, person_data: Optional[Dict] = None, existing_persons: List[Dict] = None, parent=None,
                 auth_token: Optional[str] = None, survey_id: Optional[str] = None,
                 household_id: Optional[str] = None, unit_id: Optional[str] = None):
        """
        Initialize the dialog.

        Args:
            person_data: Optional existing person data for editing
            existing_persons: List of existing persons for validation
            parent: Parent widget
            auth_token: Optional JWT token for API calls
            survey_id: Survey UUID for creating persons under a survey
            household_id: Household UUID for creating persons under a household
            unit_id: Property Unit UUID for linking person to unit relation
        """
        super().__init__(parent)
        self.person_data = person_data
        self.existing_persons = existing_persons or []
        self.editing_mode = person_data is not None
        self.validation_service = ValidationService()
        self.uploaded_files = []  # Store uploaded file paths

        # API integration
        self._survey_id = survey_id
        self._household_id = household_id
        self._unit_id = unit_id
        self._api_service = PersonApiService(auth_token)
        self._survey_api_service = SurveyApiService(auth_token)
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

        self.setModal(True)
        self.setFixedSize(650, 750)

        # Remove system title bar (same as unit dialog)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
        """)

        self._setup_ui()

        if self.editing_mode and person_data:
            self._load_person_data(person_data)

    def _setup_ui(self):
        """Setup dialog UI."""
        self.setLayoutDirection(Qt.RightToLeft)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # White rounded content frame (same as unit dialog)
        content_frame = QFrame()
        content_frame.setObjectName("ContentFrame")
        content_frame.setStyleSheet("""
            QFrame#ContentFrame {
                background-color: #f5f7fa;
                border: 1px solid #E1E8ED;
                border-radius: 24px;
            }
        """)
        outer_layout.addWidget(content_frame)

        main_layout = QVBoxLayout(content_frame)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        label_style = "color: #555; font-weight: 600; font-size: 13px;"

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e6ed;
                border-radius: 8px;
                background-color: white;
                padding: 15px;
            }
            QTabBar::tab {
                background-color: #f5f7fa;
                border: 1px solid #e0e6ed;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 12px 40px;
                margin-left: 5px;
                font-size: 15px;
                font-weight: bold;
                color: #555;
                min-width: 150px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #4a90e2;
            }
            QTabBar::tab:hover {
                background-color: #e8f0fe;
            }
        """)

        # ===== TAB 1: Person Information =====
        person_tab = QWidget()
        person_tab.setLayoutDirection(Qt.RightToLeft)
        person_group = QFrame(person_tab)
        person_layout = QVBoxLayout(person_group)
        person_layout.setSpacing(15)

        # Section title
        person_title = QLabel("اضافة شخص جديد")
        person_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        person_layout.addWidget(person_title)

        # Person info grid - 2 columns layout
        person_grid = QGridLayout()
        person_grid.setHorizontalSpacing(15)
        person_grid.setVerticalSpacing(5)  # Smaller vertical spacing between label and input
        person_grid.setColumnStretch(0, 1)
        person_grid.setColumnStretch(1, 1)

        # Row 0: First Name | Last Name (Right to Left layout)
        row = 0
        first_name_label = QLabel("الاسم الأول")
        first_name_label.setStyleSheet(label_style)
        person_grid.addWidget(first_name_label, row, 0)

        last_name_label = QLabel("الكنية")
        last_name_label.setStyleSheet(label_style)
        person_grid.addWidget(last_name_label, row, 1)

        row += 1
        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("ادخل الاسم الأول")
        self.first_name.setStyleSheet(self._input_style())
        person_grid.addWidget(self.first_name, row, 0)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("ادخل اسم العائلة")
        self.last_name.setStyleSheet(self._input_style())
        person_grid.addWidget(self.last_name, row, 1)

        # Row 2: Father Name | Mother Name
        row += 1
        father_name_label = QLabel("اسم الأب")
        father_name_label.setStyleSheet(label_style)
        person_grid.addWidget(father_name_label, row, 0)

        mother_name_label = QLabel("اسم الأم")
        mother_name_label.setStyleSheet(label_style)
        person_grid.addWidget(mother_name_label, row, 1)

        row += 1
        self.father_name = QLineEdit()
        self.father_name.setPlaceholderText("ادخل اسم الأب")
        self.father_name.setStyleSheet(self._input_style())
        person_grid.addWidget(self.father_name, row, 0)

        self.mother_name = QLineEdit()
        self.mother_name.setPlaceholderText("ادخل اسم الأم")
        self.mother_name.setStyleSheet(self._input_style())
        person_grid.addWidget(self.mother_name, row, 1)

        # Row 4: Birth Date | National ID
        row += 1
        birth_date_label = QLabel("تاريخ الميلاد")
        birth_date_label.setStyleSheet(label_style)
        person_grid.addWidget(birth_date_label, row, 0)

        national_id_label = QLabel("الرقم الوطني")
        national_id_label.setStyleSheet(label_style)
        person_grid.addWidget(national_id_label, row, 1)

        row += 1
        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate(1980, 1, 1))
        self.birth_date.setDisplayFormat("yyyy-MM-dd")
        self.birth_date.setStyleSheet(self._date_input_style())
        person_grid.addWidget(self.birth_date, row, 0)

        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("00000000000")
        self.national_id.setMaxLength(11)
        self.national_id.setStyleSheet(self._input_style())
        self.national_id.textChanged.connect(self._validate_national_id)
        person_grid.addWidget(self.national_id, row, 1)

        # National ID status
        row += 1
        self.national_id_status = QLabel("")
        self.national_id_status.setAlignment(Qt.AlignRight)
        person_grid.addWidget(self.national_id_status, row, 0, 1, 2)

        # Row 7: Email | Relationship
        row += 1
        email_label = QLabel("البريد الالكتروني")
        email_label.setStyleSheet(label_style)
        person_grid.addWidget(email_label, row, 0)

        relationship_label = QLabel("علاقة الشخص بوحدة العقار")
        relationship_label.setStyleSheet(label_style)
        person_grid.addWidget(relationship_label, row, 1)

        row += 1
        self.email = QLineEdit()
        self.email.setPlaceholderText("*****@gmail.com")
        self.email.setStyleSheet(self._input_style())
        person_grid.addWidget(self.email, row, 0)

        self.relationship_combo = QComboBox()
        self.relationship_combo.addItem("اختر", None)
        relationship_types = [
            ("owner", "مالك"),
            ("co_owner", "شريك في الملكية"),
            ("tenant", "مستأجر"),
            ("occupant", "شاغل"),
            ("heir", "وارث"),
            ("guardian", "ولي/وصي"),
            ("other", "أخرى")
        ]
        for code, ar_name in relationship_types:
            self.relationship_combo.addItem(ar_name, code)
        self.relationship_combo.setStyleSheet(self._input_style())
        person_grid.addWidget(self.relationship_combo, row, 1)

        # Row 9: Landline | Mobile phone
        row += 1
        landline_label = QLabel("رقم الهاتف")
        landline_label.setStyleSheet(label_style)
        person_grid.addWidget(landline_label, row, 0)

        mobile_label = QLabel("رقم الموبايل")
        mobile_label.setStyleSheet(label_style)
        person_grid.addWidget(mobile_label, row, 1)

        row += 1
        self.landline = QLineEdit()
        self.landline.setPlaceholderText("0000000")
        self.landline.setStyleSheet(self._input_style())
        person_grid.addWidget(self.landline, row, 0)

        # Mobile with country code - using StyleManager
        from ui.style_manager import StyleManager

        mobile_container = QFrame()
        mobile_container.setStyleSheet(StyleManager.mobile_input_container())
        mobile_layout = QHBoxLayout(mobile_container)
        mobile_layout.setContentsMargins(0, 0, 0, 0)
        mobile_layout.setSpacing(0)
        mobile_layout.setDirection(QHBoxLayout.RightToLeft)

        # Country Code Label
        prefix_label = QLabel("+963 | 09")
        prefix_label.setFixedWidth(90)
        prefix_label.setAlignment(Qt.AlignCenter)
        prefix_label.setStyleSheet(StyleManager.mobile_input_prefix())

        # Phone Number Entry
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("00000000")
        self.phone.setAlignment(Qt.AlignRight)
        self.phone.setStyleSheet(StyleManager.mobile_input_field())

        mobile_layout.addWidget(prefix_label)
        mobile_layout.addWidget(self.phone)
        person_grid.addWidget(mobile_container, row, 1)

        # Row 11: Document upload
        row += 1
        doc_label = QLabel("المستندات")
        doc_label.setStyleSheet(label_style)
        person_grid.addWidget(doc_label, row, 0, 1, 2)

        row += 1
        # File upload frame - using StyleManager
        upload_frame = QFrame()
        upload_frame.setObjectName("UploadFrame")
        upload_frame.setCursor(Qt.PointingHandCursor)
        upload_frame.setStyleSheet(StyleManager.file_upload_frame())

        upload_layout = QVBoxLayout(upload_frame)
        upload_layout.setContentsMargins(20, 15, 20, 15)
        upload_layout.setAlignment(Qt.AlignCenter)
        upload_layout.setSpacing(5)

        # Upload icon - smaller and centered
        upload_icon = QLabel()
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("border: none;")

        # Load upload icon using Icon component
        from ui.components.icon import Icon
        upload_pixmap = Icon.load_pixmap("upload_file", size=24)
        if upload_pixmap and not upload_pixmap.isNull():
            upload_icon.setPixmap(upload_pixmap)
        else:
            # Fallback emoji
            upload_icon.setText("📁")
            upload_icon.setStyleSheet("border: none; font-size: 20px;")

        # Upload button - using StyleManager
        self.doc_upload_btn = QPushButton("ارفع صور المستندات")
        self.doc_upload_btn.setStyleSheet(StyleManager.file_upload_button())
        self.doc_upload_btn.clicked.connect(self._browse_files)

        upload_layout.addWidget(upload_icon)
        upload_layout.addWidget(self.doc_upload_btn)

        person_grid.addWidget(upload_frame, row, 0, 1, 2)

        person_layout.addLayout(person_grid)

        # Set layout for person tab
        person_tab_layout = QVBoxLayout(person_tab)
        person_tab_layout.setContentsMargins(0, 0, 0, 0)
        person_tab_layout.setSpacing(15)
        person_tab_layout.addWidget(person_group)

        # Buttons layout (Save and Cancel) - below the frame
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        # Cancel button (on the right in RTL)
        cancel_person_btn = QPushButton("إلغاء")
        cancel_person_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #4a90e2;
                border: 1px solid #e0e6ed;
                border-radius: 8px;
                padding: 12px 40px;
                font-weight: bold;
                font-size: 14px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #f5f7fa;
            }
        """)
        cancel_person_btn.clicked.connect(self.reject)

        # Save person button (on the left in RTL)
        save_person_btn = QPushButton("حفظ")
        save_person_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border-radius: 8px;
                padding: 12px 40px;
                font-weight: bold;
                font-size: 14px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        save_person_btn.clicked.connect(self._save_person_and_switch_tab)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_person_btn)
        buttons_layout.addWidget(save_person_btn)
        buttons_layout.addStretch()

        person_tab_layout.addLayout(buttons_layout)

        # ===== TAB 2: Relationship Information =====
        relation_tab = QWidget()
        relation_tab.setLayoutDirection(Qt.RightToLeft)
        relation_group = QFrame(relation_tab)
        relation_layout = QVBoxLayout(relation_group)
        relation_layout.setSpacing(15)

        # Section title
        relation_title = QLabel("العلاقة")
        relation_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        relation_layout.addWidget(relation_title)

        # Relationship info grid - 2 columns layout
        relation_grid = QGridLayout()
        relation_grid.setHorizontalSpacing(15)
        relation_grid.setVerticalSpacing(5)  # Smaller vertical spacing between label and input
        relation_grid.setColumnStretch(0, 1)
        relation_grid.setColumnStretch(1, 1)

        # Row 0: Contract Type | Relationship Type
        row = 0
        contract_type_label = QLabel("نوع العقد")
        contract_type_label.setStyleSheet(label_style)
        relation_grid.addWidget(contract_type_label, row, 0)

        rel_type_label = QLabel("نوع العلاقة")
        rel_type_label.setStyleSheet(label_style)
        relation_grid.addWidget(rel_type_label, row, 1)

        row += 1
        self.contract_type = QComboBox()
        self.contract_type.addItems(["اختر", "عقد إيجار", "عقد بيع", "عقد شراكة"])
        self.contract_type.setStyleSheet(self._input_style())
        relation_grid.addWidget(self.contract_type, row, 0)

        self.rel_type_combo = QComboBox()
        self.rel_type_combo.addItem("اختر", None)
        rel_types = [
            ("owner", "مالك"),
            ("co_owner", "شريك في الملكية"),
            ("tenant", "مستأجر"),
            ("occupant", "شاغل"),
            ("heir", "وارث"),
            ("guardian", "ولي/وصي"),
            ("other", "أخرى")
        ]
        for code, ar in rel_types:
            self.rel_type_combo.addItem(ar, code)
        self.rel_type_combo.setStyleSheet(self._input_style())
        relation_grid.addWidget(self.rel_type_combo, row, 1)

        # Row 2: Start Date | Ownership Share
        row += 1
        start_date_label = QLabel("تاريخ بدء العلاقة")
        start_date_label.setStyleSheet(label_style)
        relation_grid.addWidget(start_date_label, row, 0)

        ownership_share_label = QLabel("حصة الملكية")
        ownership_share_label.setStyleSheet(label_style)
        relation_grid.addWidget(ownership_share_label, row, 1)

        row += 1
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setStyleSheet(self._date_input_style())
        relation_grid.addWidget(self.start_date, row, 0)

        self.ownership_share = QDoubleSpinBox()
        self.ownership_share.setRange(0, 100)
        self.ownership_share.setDecimals(2)
        self.ownership_share.setSuffix(" %")
        self.ownership_share.setValue(0)
        self.ownership_share.setStyleSheet(StyleManager.numeric_input())
        relation_grid.addWidget(self.ownership_share, row, 1)

        # Row 4: Evidence Type | Evidence Description
        row += 1
        evidence_type_label = QLabel("نوع الدليل")
        evidence_type_label.setStyleSheet(label_style)
        relation_grid.addWidget(evidence_type_label, row, 0)

        evidence_desc_label = QLabel("وصف الدليل")
        evidence_desc_label.setStyleSheet(label_style)
        relation_grid.addWidget(evidence_desc_label, row, 1)

        row += 1
        self.evidence_type = QComboBox()
        self.evidence_type.addItems(["اختر", "صك", "عقد", "وكالة", "إقرار"])
        self.evidence_type.setStyleSheet(self._input_style())
        relation_grid.addWidget(self.evidence_type, row, 0)

        self.evidence_desc = QLineEdit()
        self.evidence_desc.setPlaceholderText("ادخل وصف الدليل")
        self.evidence_desc.setStyleSheet(self._input_style())
        relation_grid.addWidget(self.evidence_desc, row, 1)

        # Row 6: Notes
        row += 1
        notes_label = QLabel("ادخل ملاحظاتك")
        notes_label.setStyleSheet(label_style)
        relation_grid.addWidget(notes_label, row, 0, 1, 2)

        row += 1
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("ادخل ملاحظاتك هنا...")
        self.notes.setMaximumHeight(80)
        self.notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e6ed;
                border-radius: 8px;
                padding: 10px;
                background-color: white;
                color: #333;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid #4a90e2;
            }
        """)
        relation_grid.addWidget(self.notes, row, 0, 1, 2)

        # Row 8: Document upload
        row += 1
        doc_label2 = QLabel("المستندات")
        doc_label2.setStyleSheet(label_style)
        relation_grid.addWidget(doc_label2, row, 0, 1, 2)

        row += 1
        # File upload frame - using StyleManager
        rel_upload_frame = QFrame()
        rel_upload_frame.setObjectName("RelUploadFrame")
        rel_upload_frame.setCursor(Qt.PointingHandCursor)
        rel_upload_frame.setStyleSheet(StyleManager.file_upload_frame())

        rel_upload_layout = QVBoxLayout(rel_upload_frame)
        rel_upload_layout.setContentsMargins(20, 15, 20, 15)
        rel_upload_layout.setAlignment(Qt.AlignCenter)
        rel_upload_layout.setSpacing(5)

        # Upload icon - smaller and centered
        rel_upload_icon = QLabel()
        rel_upload_icon.setAlignment(Qt.AlignCenter)
        rel_upload_icon.setStyleSheet("border: none;")

        # Load upload icon using Icon component
        from ui.components.icon import Icon
        rel_upload_pixmap = Icon.load_pixmap("upload_file", size=24)
        if rel_upload_pixmap and not rel_upload_pixmap.isNull():
            rel_upload_icon.setPixmap(rel_upload_pixmap)
        else:
            # Fallback emoji
            rel_upload_icon.setText("📁")
            rel_upload_icon.setStyleSheet("border: none; font-size: 20px;")

        # Upload button - using StyleManager
        self.rel_doc_upload_btn = QPushButton("ارفع صور المستندات")
        self.rel_doc_upload_btn.setStyleSheet(StyleManager.file_upload_button())
        self.rel_doc_upload_btn.clicked.connect(self._browse_relation_files)

        rel_upload_layout.addWidget(rel_upload_icon)
        rel_upload_layout.addWidget(self.rel_doc_upload_btn)

        relation_grid.addWidget(rel_upload_frame, row, 0, 1, 2)

        relation_layout.addLayout(relation_grid)

        # Set layout for relation tab
        relation_tab_layout = QVBoxLayout(relation_tab)
        relation_tab_layout.setContentsMargins(0, 0, 0, 0)
        relation_tab_layout.setSpacing(15)
        relation_tab_layout.addWidget(relation_group)

        # Buttons layout (Save and Cancel) - below the frame
        relation_buttons_layout = QHBoxLayout()
        relation_buttons_layout.setSpacing(15)

        # Cancel button (on the right in RTL)
        cancel_relation_btn = QPushButton("إلغاء")
        cancel_relation_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #4a90e2;
                border: 1px solid #e0e6ed;
                border-radius: 8px;
                padding: 12px 40px;
                font-weight: bold;
                font-size: 14px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #f5f7fa;
            }
        """)
        cancel_relation_btn.clicked.connect(self.reject)

        # Save relationship button (on the left in RTL)
        save_relation_btn = QPushButton("حفظ")
        save_relation_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border-radius: 8px;
                padding: 12px 40px;
                font-weight: bold;
                font-size: 14px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        save_relation_btn.clicked.connect(self._on_final_save)

        relation_buttons_layout.addStretch()
        relation_buttons_layout.addWidget(cancel_relation_btn)
        relation_buttons_layout.addWidget(save_relation_btn)
        relation_buttons_layout.addStretch()

        relation_tab_layout.addLayout(relation_buttons_layout)

        # Add tabs to tab widget
        self.tab_widget.addTab(person_tab, "بيانات الشخص")
        self.tab_widget.addTab(relation_tab, "العلاقة")

        # Disable relation tab initially
        self.tab_widget.setTabEnabled(1, False)

        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)

        # Hidden fields for compatibility
        self.gender = QComboBox()
        self.gender.addItem("ذكر", "male")
        self.gender.addItem("أنثى", "female")
        self.gender.hide()

        self.is_contact = QCheckBox("شخص التواصل الرئيسي")
        self.is_contact.hide()

    def _input_style(self) -> str:
        """Return standard input style from StyleManager."""
        from ui.style_manager import StyleManager
        return StyleManager.form_input()

    def _date_input_style(self) -> str:
        """Return date input style from StyleManager."""
        from ui.style_manager import StyleManager
        return StyleManager.date_input()

    def _browse_files(self):
        """Browse for files to upload."""
        from PyQt5.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "اختر ملفات",
            "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            file_names = [f.split("/")[-1] for f in file_paths]
            self.doc_upload_btn.setText(f"تم اختيار {len(file_names)} ملف")
            # Store file paths for later use
            self.uploaded_files = file_paths

    def _browse_relation_files(self):
        """Browse for relation files to upload."""
        from PyQt5.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "اختر ملفات",
            "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            file_names = [f.split("/")[-1] for f in file_paths]
            self.rel_doc_upload_btn.setText(f"تم اختيار {len(file_names)} ملف")
            # Store file paths for later use
            if not hasattr(self, 'relation_uploaded_files'):
                self.relation_uploaded_files = []
            self.relation_uploaded_files = file_paths

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

        # If editing, enable relation tab
        if self.editing_mode:
            self.tab_widget.setTabEnabled(1, True)

    def _save_person_and_switch_tab(self):
        """Validate person data and switch to relation tab."""
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

        # Enable and switch to relation tab
        self.tab_widget.setTabEnabled(1, True)
        self.tab_widget.setCurrentIndex(1)
        Toast.show_toast(self, "تم حفظ بيانات الشخص بنجاح", Toast.SUCCESS)

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

    def _on_final_save(self):
        """Handle final save (from relation tab) - create person via API, then link to unit, then accept."""
        import json
        from PyQt5.QtWidgets import QMessageBox

        if self._use_api and not self.editing_mode:
            person_data = self.get_person_data()
            logger.info(f"Creating person via API: {person_data.get('first_name')} {person_data.get('last_name')}")
            print(f"[PERSON] Creating person for survey_id: {self._survey_id}, household_id: {self._household_id}")

            # Step 1: Create person in household
            response = self._api_service.create_person(
                person_data,
                survey_id=self._survey_id,
                household_id=self._household_id
            )

            # Show person creation API response
            response_text = json.dumps(response, indent=2, ensure_ascii=False, default=str)
            print(f"\n[PERSON API RESPONSE]\n{response_text}")
            QMessageBox.information(
                self,
                "Create Person API Response",
                f"POST /api/v1/Surveys/{self._survey_id}/households/{self._household_id}/persons\n\n{response_text[:1000]}"
            )

            if not response.get("success"):
                error_msg = response.get("error", "Unknown error")
                details = response.get("details", "")
                logger.error(f"Failed to create person via API: {error_msg} - {details}")
                return

            logger.info("Person created successfully via API")
            person_id = ""
            if response.get("data"):
                self._created_person_data = response.get("data")
                # Try multiple possible field names for person ID
                person_id = (
                    response["data"].get("id") or
                    response["data"].get("personId") or
                    response["data"].get("Id") or
                    response["data"].get("PersonId") or
                    ""
                )
                print(f"[PERSON] Person created successfully, person_id: {person_id}")
                print(f"[PERSON] Full API response: {response['data']}")

                if not person_id:
                    logger.error(f"Could not find person ID in response. Available keys: {list(response['data'].keys())}")
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.critical(
                        self,
                        "خطأ",
                        f"تم إنشاء الشخص ولكن لم نتمكن من الحصول على معرف الشخص من الاستجابة"
                    )
                    return

            # Step 1.5: Upload identification files if any
            if self.uploaded_files and self._survey_id and person_id:
                self._upload_identification_files(person_id)

            # Step 2: Link person to property unit with relation type
            if self._survey_id and self._unit_id and person_id:
                relation_data = person_data.get('relation_data', {})
                relation_data['person_id'] = person_id
                # Also pass the relationship_type from tab 1 if rel_type not set in tab 2
                if not relation_data.get('rel_type'):
                    relation_data['rel_type'] = person_data.get('relationship_type')

                print(f"[RELATION] Linking person {person_id} to unit {self._unit_id} in survey {self._survey_id}")
                relation_response = self._api_service.link_person_to_unit(
                    self._survey_id,
                    self._unit_id,
                    relation_data
                )

                # Show relation linking API response
                relation_response_text = json.dumps(relation_response, indent=2, ensure_ascii=False, default=str)
                print(f"\n[RELATION API RESPONSE]\n{relation_response_text}")
                QMessageBox.information(
                    self,
                    "Link Person to Unit API Response",
                    f"POST /api/v1/Surveys/{self._survey_id}/units/{self._unit_id}/relations\n\n{relation_response_text[:1000]}"
                )

                if not relation_response.get("success"):
                    error_msg = relation_response.get("error", "Unknown error")
                    error_details = relation_response.get("details", "")
                    error_code = relation_response.get("error_code", "")

                    logger.error(f"Failed to link person to unit: {error_msg}")
                    logger.error(f"Error code: {error_code}")
                    logger.error(f"Error details: {error_details}")
                else:
                    logger.info(f"Person {person_id} linked to unit {self._unit_id} successfully")
                    print(f"[RELATION] Person {person_id} linked to unit {self._unit_id} successfully")
                    if relation_response.get("data"):
                        print(f"[RELATION] Full API response: {relation_response['data']}")

                        # Get relation ID from response
                        relation_id = (
                            relation_response["data"].get("id") or
                            relation_response["data"].get("relationId") or
                            relation_response["data"].get("Id") or
                            relation_response["data"].get("RelationId") or
                            relation_response["data"].get("personPropertyRelationId") or
                            relation_response["data"].get("PersonPropertyRelationId") or
                            ""
                        )

                        # Upload tenure files if any
                        if relation_id and hasattr(self, 'relation_uploaded_files') and self.relation_uploaded_files:
                            self._upload_tenure_files(relation_id)

        self.accept()

    def _upload_identification_files(self, person_id: str):
        """Upload identification files for the created person."""
        import json
        from PyQt5.QtWidgets import QMessageBox

        if not self.uploaded_files:
            return

        print(f"[PERSON] Uploading {len(self.uploaded_files)} identification file(s) for person {person_id}")

        for file_path in self.uploaded_files:
            logger.info(f"Uploading identification file: {file_path}")
            print(f"[PERSON] Uploading file: {file_path}")

            response = self._survey_api_service.upload_identification_evidence(
                survey_id=self._survey_id,
                person_id=person_id,
                file_path=file_path,
                description=f"Identification document for person",
                issuing_authority="",
                document_reference_number=self.national_id.text().strip() or ""
            )

            # Show identification upload API response
            import os
            file_name = os.path.basename(file_path)
            response_text = json.dumps(response, indent=2, ensure_ascii=False, default=str)
            print(f"\n[IDENTIFICATION UPLOAD API RESPONSE]\n{response_text}")
            QMessageBox.information(
                self,
                "Upload Identification Evidence API Response",
                f"POST /api/v1/Surveys/{self._survey_id}/evidence/identification\n\nFile: {file_name}\nPersonId: {person_id}\n\n{response_text[:800]}"
            )

            if response.get("success"):
                logger.info(f"File uploaded successfully: {file_path}")
                print(f"[PERSON] File uploaded successfully: {file_path}")
            else:
                error_msg = response.get("error", "Unknown error")
                logger.warning(f"Failed to upload file {file_path}: {error_msg}")
                print(f"[PERSON] Failed to upload file: {error_msg}")
                # Don't fail the whole process, just warn
                Toast.show_toast(self, f"تحذير: فشل رفع الملف", Toast.WARNING)

    def _upload_tenure_files(self, relation_id: str):
        """Upload tenure evidence files for the created relation."""
        import json
        import os
        from PyQt5.QtWidgets import QMessageBox

        if not hasattr(self, 'relation_uploaded_files') or not self.relation_uploaded_files:
            return

        print(f"[RELATION] Uploading {len(self.relation_uploaded_files)} tenure file(s) for relation {relation_id}")

        # Get evidence type index from combo box
        evidence_type_index = self.evidence_type.currentIndex()
        evidence_type_value = evidence_type_index if evidence_type_index > 0 else 0

        for file_path in self.relation_uploaded_files:
            logger.info(f"Uploading tenure file: {file_path}")
            print(f"[RELATION] Uploading file: {file_path}")

            response = self._survey_api_service.upload_tenure_evidence(
                survey_id=self._survey_id,
                relation_id=relation_id,
                file_path=file_path,
                evidence_type=evidence_type_value,
                description=self.evidence_desc.text().strip() or "Tenure evidence document",
                issuing_authority="",
                document_reference_number="",
                notes=self.notes.toPlainText().strip() or ""
            )

            # Show tenure upload API response
            file_name = os.path.basename(file_path)
            response_text = json.dumps(response, indent=2, ensure_ascii=False, default=str)
            print(f"\n[TENURE UPLOAD API RESPONSE]\n{response_text}")
            QMessageBox.information(
                self,
                "Upload Tenure Evidence API Response",
                f"POST /api/v1/Surveys/{self._survey_id}/evidence/tenure\n\nFile: {file_name}\nRelationId: {relation_id}\n\n{response_text[:800]}"
            )

            if response.get("success"):
                logger.info(f"Tenure file uploaded successfully: {file_path}")
                print(f"[RELATION] Tenure file uploaded successfully: {file_path}")
            else:
                error_msg = response.get("error", "Unknown error")
                logger.warning(f"Failed to upload tenure file {file_path}: {error_msg}")
                print(f"[RELATION] Failed to upload tenure file: {error_msg}")
                # Don't fail the whole process, just warn
                Toast.show_toast(self, f"تحذير: فشل رفع ملف العلاقة", Toast.WARNING)

    def get_person_data(self) -> Dict[str, Any]:
        """Get person data from form including relationship data."""
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
            'is_contact_person': self.is_contact.isChecked(),
            # Relationship tab data
            'relation_data': {
                'contract_type': self.contract_type.currentText() if self.contract_type.currentIndex() > 0 else None,
                'rel_type': self.rel_type_combo.currentData(),
                'start_date': self.start_date.date().toString('yyyy-MM-dd'),
                'ownership_share': self.ownership_share.value(),
                'evidence_type': self.evidence_type.currentText() if self.evidence_type.currentIndex() > 0 else None,
                'evidence_desc': self.evidence_desc.text().strip() or None,
                'notes': self.notes.toPlainText().strip() or None
            }
        }
