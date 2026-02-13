# -*- coding: utf-8 -*-
"""
Person Dialog - Dialog for creating/editing persons.

3-Tab structure:
- Tab 1: Personal information (names, birth place, birth date, gender, nationality, national ID, ID photos)
- Tab 2: Contact information (person role, email, mobile, landline)
- Tab 3: Relation & Evidence (occupancy nature, claim type, dates, ownership, documents)
"""

from typing import Dict, Any, Optional, List
import uuid

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDateEdit, QFrame, QWidget,
    QGridLayout, QTextEdit, QTabWidget, QDoubleSpinBox,
    QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QDate

from app.config import Config
from services.validation_service import ValidationService
from services.api_client import get_api_client
from services.translation_manager import tr
from services.error_mapper import map_exception
from services.display_mappings import get_relation_type_options, get_contract_type_options, get_evidence_type_options
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDialog(QDialog):
    """Dialog for creating or editing a person - 3 tabs."""

    def __init__(self, person_data: Optional[Dict] = None, existing_persons: List[Dict] = None, parent=None,
                 auth_token: Optional[str] = None, survey_id: Optional[str] = None,
                 household_id: Optional[str] = None, unit_id: Optional[str] = None):
        super().__init__(parent)
        self.person_data = person_data
        self.existing_persons = existing_persons or []
        self.editing_mode = person_data is not None
        self.validation_service = ValidationService()
        self.uploaded_files = []
        self.relation_uploaded_files = []

        # API integration
        self._survey_id = survey_id
        self._household_id = household_id
        self._unit_id = unit_id
        self._api_service = get_api_client()
        if auth_token:
            self._api_service.set_access_token(auth_token)
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

        self.setModal(True)
        self.setFixedSize(650, 750)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

        if self.editing_mode and person_data:
            self._load_person_data(person_data)

    # UI Setup

    def _setup_ui(self):
        """Setup dialog UI with 3 tabs."""
        self.setLayoutDirection(Qt.RightToLeft)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # White rounded content frame (same as existing)
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
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Dialog title
        title_text = tr("wizard.person_dialog.title_edit") if self.editing_mode else tr("wizard.person_dialog.title_add")
        self._dialog_title = QLabel(title_text)
        self._dialog_title.setAlignment(Qt.AlignCenter)
        self._dialog_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(self._dialog_title)

        # Progress indicator (3 bars)
        self._setup_progress_indicator(main_layout)

        # Tab widget with hidden tab bar
        self.tab_widget = QTabWidget()
        self.tab_widget.tabBar().setVisible(False)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e6ed;
                border-radius: 8px;
                background-color: white;
                padding: 15px;
            }
        """)

        self._setup_tab1_personal()
        self._setup_tab2_contact()
        self._setup_tab3_relation()

        self.tab_widget.currentChanged.connect(self._update_progress)
        main_layout.addWidget(self.tab_widget)

    def _setup_progress_indicator(self, layout):
        """Create 3-bar progress indicator matching Figma design."""
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)
        self._progress_bars = []
        for _ in range(3):
            bar = QFrame()
            bar.setFixedHeight(4)
            bar.setStyleSheet("QFrame { background-color: #e0e6ed; border-radius: 2px; }")
            self._progress_bars.append(bar)
            progress_layout.addWidget(bar)
        layout.addLayout(progress_layout)
        self._update_progress(0)

    def _update_progress(self, current_tab: int):
        """Update progress bar indicators based on current tab."""
        for i, bar in enumerate(self._progress_bars):
            active = i <= current_tab
            bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#4a90e2' if active else '#e0e6ed'};
                    border-radius: 2px;
                }}
            """)
            bar.setFixedHeight(5 if active else 3)

    # Tab 1: Personal Information

    def _setup_tab1_personal(self):
        """Tab 1: Names, birth place, birth date, gender, nationality, national ID, ID photos."""
        tab = QWidget()
        tab.setLayoutDirection(Qt.RightToLeft)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(10)

        label_style = "color: #555; font-weight: 600; font-size: 13px;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0

        # Row: First Name | Last Name
        grid.addWidget(self._label(tr("wizard.person_dialog.first_name"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.last_name"), label_style), row, 1)
        row += 1
        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText(tr("wizard.person_dialog.first_name_placeholder"))
        self.first_name.setStyleSheet(self._input_style())
        grid.addWidget(self.first_name, row, 0)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText(tr("wizard.person_dialog.last_name_placeholder"))
        self.last_name.setStyleSheet(self._input_style())
        grid.addWidget(self.last_name, row, 1)
        row += 1

        # Row: Father Name | Mother Name
        grid.addWidget(self._label(tr("wizard.person_dialog.father_name"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.mother_name"), label_style), row, 1)
        row += 1
        self.father_name = QLineEdit()
        self.father_name.setPlaceholderText(tr("wizard.person_dialog.father_name_placeholder"))
        self.father_name.setStyleSheet(self._input_style())
        grid.addWidget(self.father_name, row, 0)

        self.mother_name = QLineEdit()
        self.mother_name.setPlaceholderText(tr("wizard.person_dialog.mother_name_placeholder"))
        self.mother_name.setStyleSheet(self._input_style())
        grid.addWidget(self.mother_name, row, 1)
        row += 1

        # Row: Birth Place | Birth Date
        grid.addWidget(self._label(tr("wizard.person_dialog.birth_place"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.birth_date"), label_style), row, 1)
        row += 1
        self.birth_place = QComboBox()
        self.birth_place.addItem(tr("wizard.person_dialog.select"), None)
        for code, name in self._get_governorate_options():
            self.birth_place.addItem(name, code)
        self.birth_place.setStyleSheet(self._input_style())
        grid.addWidget(self.birth_place, row, 0)

        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate(1980, 1, 1))
        self.birth_date.setMinimumDate(QDate(1900, 1, 1))
        self.birth_date.setDisplayFormat("yyyy-MM-dd")
        self.birth_date.setStyleSheet(self._date_input_style())
        grid.addWidget(self.birth_date, row, 1)
        row += 1

        # Row: Gender | Nationality
        grid.addWidget(self._label(tr("wizard.person_dialog.gender"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.nationality"), label_style), row, 1)
        row += 1
        self.gender = QComboBox()
        self.gender.addItem(tr("wizard.person_dialog.select"), None)
        self.gender.addItem(tr("wizard.person_dialog.gender_male"), "male")
        self.gender.addItem(tr("wizard.person_dialog.gender_female"), "female")
        self.gender.setStyleSheet(self._input_style())
        grid.addWidget(self.gender, row, 0)

        self.nationality = QComboBox()
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)
        self.nationality.addItem(tr("wizard.person_dialog.nationality_syrian"), "syrian")
        self.nationality.addItem(tr("wizard.person_dialog.nationality_palestinian"), "palestinian")
        self.nationality.addItem(tr("wizard.person_dialog.nationality_other"), "other")
        self.nationality.setStyleSheet(self._input_style())
        grid.addWidget(self.nationality, row, 1)
        row += 1

        # Row: National ID (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.national_id"), label_style), row, 0, 1, 2)
        row += 1
        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("0000000000")
        self.national_id.setMaxLength(11)
        self.national_id.setStyleSheet(self._input_style())
        self.national_id.textChanged.connect(self._validate_national_id)
        grid.addWidget(self.national_id, row, 0, 1, 2)
        row += 1

        # National ID status
        self.national_id_status = QLabel("")
        self.national_id_status.setAlignment(Qt.AlignRight)
        grid.addWidget(self.national_id_status, row, 0, 1, 2)
        row += 1

        # ID Photos upload
        grid.addWidget(self._label(tr("wizard.person_dialog.attach_id_photos"), label_style), row, 0, 1, 2)
        row += 1
        upload_frame = self._create_upload_frame(self._browse_files, "id_upload")
        grid.addWidget(upload_frame, row, 0, 1, 2)

        tab_layout.addLayout(grid)
        tab_layout.addStretch()

        # Buttons: Next | Cancel
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.addStretch()
        btn_layout.addWidget(self._create_btn(tr("common.cancel"), primary=False, callback=self.reject))
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab2))
        btn_layout.addStretch()
        tab_layout.addLayout(btn_layout)

        self.tab_widget.addTab(tab, "")

    # Tab 2: Contact Information

    def _setup_tab2_contact(self):
        """Tab 2: Person role, email, mobile, landline."""
        tab = QWidget()
        tab.setLayoutDirection(Qt.RightToLeft)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(10)

        label_style = "color: #555; font-weight: 600; font-size: 13px;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0

        # Person Role (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.person_role"), label_style), row, 0, 1, 2)
        row += 1
        self.person_role = QComboBox()
        self.person_role.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_relation_type_options():
            self.person_role.addItem(display_name, code)
        self.person_role.setStyleSheet(self._input_style())
        grid.addWidget(self.person_role, row, 0, 1, 2)
        row += 1

        # Email (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.email"), label_style), row, 0, 1, 2)
        row += 1
        self.email = QLineEdit()
        self.email.setPlaceholderText("*****@gmail.com")
        self.email.setStyleSheet(self._input_style())
        grid.addWidget(self.email, row, 0, 1, 2)
        row += 1

        # Mobile (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.mobile"), label_style), row, 0, 1, 2)
        row += 1
        from ui.style_manager import StyleManager
        mobile_container = QFrame()
        mobile_container.setStyleSheet(StyleManager.mobile_input_container())
        mobile_layout = QHBoxLayout(mobile_container)
        mobile_layout.setContentsMargins(0, 0, 0, 0)
        mobile_layout.setSpacing(0)
        mobile_layout.setDirection(QHBoxLayout.RightToLeft)

        prefix_label = QLabel("+963 | 09")
        prefix_label.setFixedWidth(90)
        prefix_label.setAlignment(Qt.AlignCenter)
        prefix_label.setStyleSheet(StyleManager.mobile_input_prefix())

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("00000000")
        self.phone.setAlignment(Qt.AlignRight)
        self.phone.setStyleSheet(StyleManager.mobile_input_field())

        mobile_layout.addWidget(prefix_label)
        mobile_layout.addWidget(self.phone)
        grid.addWidget(mobile_container, row, 0, 1, 2)
        row += 1

        # Landline (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.phone"), label_style), row, 0, 1, 2)
        row += 1
        self.landline = QLineEdit()
        self.landline.setPlaceholderText("0000000")
        self.landline.setStyleSheet(self._input_style())
        grid.addWidget(self.landline, row, 0, 1, 2)

        tab_layout.addLayout(grid)
        tab_layout.addStretch()

        # Buttons: Next | Previous
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.addStretch()
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab1))
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab3))
        btn_layout.addStretch()
        tab_layout.addLayout(btn_layout)

        self.tab_widget.addTab(tab, "")

    # Tab 3: Relation & Evidence

    def _setup_tab3_relation(self):
        """Tab 3: Occupancy nature, claim type, dates, ownership, documents."""
        tab = QWidget()
        tab.setLayoutDirection(Qt.RightToLeft)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(10)

        label_style = "color: #555; font-weight: 600; font-size: 13px;"
        from ui.style_manager import StyleManager

        grid = QGridLayout()
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0

        # Row: Occupancy Nature | Claim Type
        grid.addWidget(self._label(tr("wizard.person_dialog.occupancy_nature"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.claim_type_label"), label_style), row, 1)
        row += 1
        self.contract_type = QComboBox()
        self.contract_type.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_contract_type_options():
            self.contract_type.addItem(display_name, code)
        self.contract_type.setStyleSheet(self._input_style())
        grid.addWidget(self.contract_type, row, 0)

        self.rel_type_combo = QComboBox()
        self.rel_type_combo.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_relation_type_options():
            self.rel_type_combo.addItem(display_name, code)
        self.rel_type_combo.setStyleSheet(self._input_style())
        grid.addWidget(self.rel_type_combo, row, 1)
        row += 1

        # Row: Start Date | Ownership Share
        grid.addWidget(self._label(tr("wizard.person_dialog.relation_start_date"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.ownership_share"), label_style), row, 1)
        row += 1
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setMinimumDate(QDate(1900, 1, 1))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setStyleSheet(self._date_input_style())
        grid.addWidget(self.start_date, row, 0)

        self.ownership_share = QDoubleSpinBox()
        self.ownership_share.setRange(0, 100)
        self.ownership_share.setDecimals(2)
        self.ownership_share.setSuffix(" %")
        self.ownership_share.setValue(0)
        self.ownership_share.setStyleSheet(StyleManager.numeric_input())
        grid.addWidget(self.ownership_share, row, 1)
        row += 1

        # Row: Supporting Docs | Description
        grid.addWidget(self._label(tr("wizard.person_dialog.evidence_type"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.evidence_description"), label_style), row, 1)
        row += 1
        self.evidence_type = QComboBox()
        self.evidence_type.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_evidence_type_options():
            self.evidence_type.addItem(display_name, code)
        self.evidence_type.setStyleSheet(self._input_style())
        grid.addWidget(self.evidence_type, row, 0)

        self.evidence_desc = QLineEdit()
        self.evidence_desc.setPlaceholderText(tr("wizard.person_dialog.evidence_desc_placeholder"))
        self.evidence_desc.setStyleSheet(self._input_style())
        grid.addWidget(self.evidence_desc, row, 1)
        row += 1

        # Notes (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.notes_label"), label_style), row, 0, 1, 2)
        row += 1
        self.notes = QTextEdit()
        self.notes.setPlaceholderText(tr("wizard.person_dialog.notes_placeholder"))
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
        grid.addWidget(self.notes, row, 0, 1, 2)
        row += 1

        # Document images section
        grid.addWidget(self._label(tr("wizard.person_dialog.document_images"), label_style), row, 0, 1, 2)
        row += 1

        # Radio buttons: has / no documents
        radio_layout = QHBoxLayout()
        self.rb_has_docs = QRadioButton(tr("wizard.person_dialog.has_documents"))
        self.rb_no_docs = QRadioButton(tr("wizard.person_dialog.no_documents"))
        self.rb_has_docs.setChecked(True)
        self._doc_radio_group = QButtonGroup(self)
        self._doc_radio_group.addButton(self.rb_has_docs, 1)
        self._doc_radio_group.addButton(self.rb_no_docs, 0)
        radio_layout.addWidget(self.rb_has_docs)
        radio_layout.addWidget(self.rb_no_docs)
        radio_layout.addStretch()

        radio_widget = QWidget()
        radio_widget.setLayout(radio_layout)
        grid.addWidget(radio_widget, row, 0, 1, 2)
        row += 1

        # Upload frame for relation documents
        self._rel_upload_frame = self._create_upload_frame(self._browse_relation_files, "rel_upload")
        grid.addWidget(self._rel_upload_frame, row, 0, 1, 2)

        # Toggle upload frame visibility based on radio
        self.rb_no_docs.toggled.connect(lambda checked: self._rel_upload_frame.setVisible(not checked))

        tab_layout.addLayout(grid)
        tab_layout.addStretch()

        # Buttons: Save | Previous
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.addStretch()
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab2_back))
        btn_layout.addWidget(self._create_btn(tr("common.save"), primary=True, callback=self._on_final_save))
        btn_layout.addStretch()
        tab_layout.addLayout(btn_layout)

        self.tab_widget.addTab(tab, "")

    # UI Helpers

    def _label(self, text: str, style: str) -> QLabel:
        """Create a styled label."""
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    def _create_btn(self, text: str, primary: bool = True, callback=None) -> QPushButton:
        """Create a styled action button (DRY)."""
        btn = QPushButton(text)
        if primary:
            btn.setStyleSheet("""
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
        else:
            btn.setStyleSheet("""
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
        if callback:
            btn.clicked.connect(callback)
        return btn

    def _create_upload_frame(self, browse_callback, obj_name: str) -> QFrame:
        """Create a file upload frame (DRY - reused in Tab 1 and Tab 3)."""
        from ui.style_manager import StyleManager
        from ui.components.icon import Icon

        frame = QFrame()
        frame.setObjectName(obj_name)
        frame.setCursor(Qt.PointingHandCursor)
        frame.setStyleSheet(StyleManager.file_upload_frame())

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(5)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("border: none;")
        upload_pixmap = Icon.load_pixmap("upload_file", size=24)
        if upload_pixmap and not upload_pixmap.isNull():
            icon_lbl.setPixmap(upload_pixmap)
        else:
            icon_lbl.setText("📁")
            icon_lbl.setStyleSheet("border: none; font-size: 20px;")
        layout.addWidget(icon_lbl)

        upload_btn = QPushButton(tr("wizard.person_dialog.upload_documents"))
        upload_btn.setStyleSheet(StyleManager.file_upload_button())
        upload_btn.clicked.connect(browse_callback)
        layout.addWidget(upload_btn)

        # Store reference to the button for updating text
        frame._upload_btn = upload_btn
        return frame

    @staticmethod
    def _get_governorate_options():
        """Return Syrian governorate options for birth place dropdown."""
        return [
            ("damascus", "دمشق"),
            ("rural_damascus", "ريف دمشق"),
            ("aleppo", "حلب"),
            ("homs", "حمص"),
            ("hama", "حماة"),
            ("latakia", "اللاذقية"),
            ("tartus", "طرطوس"),
            ("deir_ez_zor", "دير الزور"),
            ("raqqa", "الرقة"),
            ("hasakah", "الحسكة"),
            ("daraa", "درعا"),
            ("suwayda", "السويداء"),
            ("quneitra", "القنيطرة"),
            ("idlib", "إدلب"),
        ]

    def _input_style(self) -> str:
        from ui.style_manager import StyleManager
        return StyleManager.form_input()

    def _date_input_style(self) -> str:
        from ui.style_manager import StyleManager
        return StyleManager.date_input()

    # Tab Navigation

    def _go_to_tab2(self):
        """Tab 1 → Tab 2: Validate personal info then switch."""
        if not self.first_name.text().strip():
            Toast.show_toast(self, tr("wizard.person_dialog.enter_first_name"), Toast.WARNING)
            return
        if not self.last_name.text().strip():
            Toast.show_toast(self, tr("wizard.person_dialog.enter_last_name"), Toast.WARNING)
            return
        if self.national_id.text().strip() and not self._validate_national_id():
            return
        self.tab_widget.setCurrentIndex(1)

    def _go_to_tab3(self):
        """Tab 2 → Tab 3."""
        self.tab_widget.setCurrentIndex(2)

    def _go_to_tab1(self):
        """Tab 2 → Tab 1."""
        self.tab_widget.setCurrentIndex(0)

    def _go_to_tab2_back(self):
        """Tab 3 → Tab 2."""
        self.tab_widget.setCurrentIndex(1)

    # Keep legacy method name for backward compatibility
    def _save_person_and_switch_tab(self):
        """Legacy: validate and go to next tab."""
        self._go_to_tab2()

    # File Browsing

    def _browse_files(self):
        """Browse for ID photo files."""
        from PyQt5.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            self.uploaded_files = file_paths
            # Update button text on the upload frame in Tab 1
            tab1_widget = self.tab_widget.widget(0)
            upload_frame = tab1_widget.findChild(QFrame, "id_upload")
            if upload_frame and hasattr(upload_frame, '_upload_btn'):
                upload_frame._upload_btn.setText(
                    tr("wizard.person_dialog.files_selected", count=len(file_paths))
                )

    def _browse_relation_files(self):
        """Browse for relation evidence files."""
        from PyQt5.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            self.relation_uploaded_files = file_paths
            if self._rel_upload_frame and hasattr(self._rel_upload_frame, '_upload_btn'):
                self._rel_upload_frame._upload_btn.setText(
                    tr("wizard.person_dialog.files_selected", count=len(file_paths))
                )

    # Validation

    def _validate_national_id(self):
        """Validate national ID."""
        nid = self.national_id.text().strip()
        if not nid:
            self.national_id_status.setText("")
            return True

        if len(nid) != 11 or not nid.isdigit():
            self.national_id_status.setText(f"⚠️ {tr('wizard.person_dialog.nid_must_be_11')}")
            self.national_id_status.setStyleSheet(f"color: {Config.WARNING_COLOR};")
            return False

        for person in self.existing_persons:
            if person.get('national_id') == nid:
                if self.editing_mode and self.person_data and person.get('person_id') == self.person_data.get('person_id'):
                    continue
                self.national_id_status.setText(f"❌ {tr('wizard.person_dialog.nid_exists')}")
                self.national_id_status.setStyleSheet(f"color: {Config.ERROR_COLOR};")
                return False

        self.national_id_status.setText(f"✅ {tr('wizard.person_dialog.nid_available')}")
        self.national_id_status.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")
        return True

    # Load / Save Data

    def _load_person_data(self, data: Dict):
        """Load person data into form fields."""
        # Tab 1
        self.first_name.setText(data.get('first_name', ''))
        self.father_name.setText(data.get('father_name', ''))
        self.mother_name.setText(data.get('mother_name', ''))
        self.last_name.setText(data.get('last_name', ''))
        self.national_id.setText(data.get('national_id', ''))

        # Birth place
        bp = data.get('birth_place')
        if bp:
            idx = self.birth_place.findData(bp)
            if idx >= 0:
                self.birth_place.setCurrentIndex(idx)

        # Birth date
        if data.get('birth_date'):
            bd = QDate.fromString(data['birth_date'], 'yyyy-MM-dd')
            if bd.isValid():
                self.birth_date.setDate(bd)

        # Gender
        gender_val = data.get('gender')
        if gender_val:
            idx = self.gender.findData(gender_val)
            if idx >= 0:
                self.gender.setCurrentIndex(idx)

        # Nationality
        nat = data.get('nationality')
        if nat:
            idx = self.nationality.findData(nat)
            if idx >= 0:
                self.nationality.setCurrentIndex(idx)

        # Tab 2
        self.phone.setText(data.get('phone', ''))
        self.email.setText(data.get('email', ''))
        self.landline.setText(data.get('landline', ''))

        # Person role
        role = data.get('person_role') or data.get('relationship_type')
        if role:
            idx = self.person_role.findData(role)
            if idx >= 0:
                self.person_role.setCurrentIndex(idx)

        # Tab 3 - relation data
        rel = data.get('relation_data', {})
        if rel.get('contract_type'):
            idx = self.contract_type.findText(rel['contract_type'])
            if idx < 0:
                idx = self.contract_type.findData(rel['contract_type'])
            if idx >= 0:
                self.contract_type.setCurrentIndex(idx)

        rel_type = rel.get('rel_type')
        if rel_type:
            for i in range(self.rel_type_combo.count()):
                if self.rel_type_combo.itemData(i) == rel_type:
                    self.rel_type_combo.setCurrentIndex(i)
                    break

        if rel.get('start_date'):
            d = QDate.fromString(rel['start_date'], 'yyyy-MM-dd')
            if d.isValid():
                self.start_date.setDate(d)

        if rel.get('ownership_share') is not None:
            self.ownership_share.setValue(float(rel['ownership_share']))

        if rel.get('evidence_type'):
            idx = self.evidence_type.findText(rel['evidence_type'])
            if idx < 0:
                idx = self.evidence_type.findData(rel['evidence_type'])
            if idx >= 0:
                self.evidence_type.setCurrentIndex(idx)

        if rel.get('evidence_desc'):
            self.evidence_desc.setText(rel['evidence_desc'])

        if rel.get('notes'):
            self.notes.setPlainText(rel['notes'])

    def get_person_data(self) -> Dict[str, Any]:
        """Get all person data from all 3 tabs."""
        return {
            'person_id': self.person_data.get('person_id') if self.person_data else str(uuid.uuid4()),
            # Tab 1
            'first_name': self.first_name.text().strip(),
            'father_name': self.father_name.text().strip(),
            'mother_name': self.mother_name.text().strip(),
            'last_name': self.last_name.text().strip(),
            'national_id': self.national_id.text().strip() or None,
            'birth_place': self.birth_place.currentData(),
            'gender': self.gender.currentData(),
            'nationality': self.nationality.currentData(),
            'birth_date': self.birth_date.date().toString('yyyy-MM-dd'),
            # Tab 2
            'person_role': self.person_role.currentData(),
            'relationship_type': self.person_role.currentData(),  # backward compat
            'phone': self.phone.text().strip() or None,
            'email': self.email.text().strip() or None,
            'landline': self.landline.text().strip() or None,
            'is_contact_person': False,
            # Tab 3
            'relation_data': {
                'contract_type': self.contract_type.currentData() if self.contract_type.currentIndex() > 0 else None,
                'rel_type': self.rel_type_combo.currentData(),
                'start_date': self.start_date.date().toString('yyyy-MM-dd'),
                'ownership_share': self.ownership_share.value(),
                'evidence_type': self.evidence_type.currentData() if self.evidence_type.currentIndex() > 0 else None,
                'evidence_desc': self.evidence_desc.text().strip() or None,
                'notes': self.notes.toPlainText().strip() or None,
                'has_documents': self.rb_has_docs.isChecked(),
            }
        }

    def _save_person(self):
        """Validate and save person data."""
        if not self.first_name.text().strip():
            Toast.show_toast(self, tr("wizard.person_dialog.enter_first_name"), Toast.WARNING)
            return
        if not self.last_name.text().strip():
            Toast.show_toast(self, tr("wizard.person_dialog.enter_last_name"), Toast.WARNING)
            return
        if self.national_id.text().strip() and not self._validate_national_id():
            return
        self.accept()

    # API Integration

    def _on_final_save(self):
        """Handle final save (from Tab 3) - create person via API, then link to unit, then accept."""
        import json
        from ui.error_handler import ErrorHandler

        if self._use_api and not self.editing_mode:
            person_data = self.get_person_data()
            logger.info(f"Creating person via API: {person_data.get('first_name')} {person_data.get('last_name')}")

            # Step 1: Create person in household
            try:
                response = self._api_service.create_person_in_household(
                    person_data, self._survey_id, self._household_id
                )

                response_text = json.dumps(response, indent=2, ensure_ascii=False, default=str)
                print(f"\n[PERSON API RESPONSE]\n{response_text}")
                ErrorHandler.show_success(
                    self,
                    f"POST /api/v1/Surveys/{self._survey_id}/households/{self._household_id}/persons\n\n{response_text[:1000]}",
                    "Create Person API Response"
                )

                logger.info("Person created successfully via API")
                self._created_person_data = response

                person_id = (
                    response.get("id") or response.get("personId") or
                    response.get("Id") or response.get("PersonId") or ""
                )

                if not person_id:
                    logger.error(f"Could not find person ID in response. Keys: {list(response.keys())}")
                    ErrorHandler.show_error(self, tr("wizard.person_dialog.created_no_id"), tr("common.error"))
                    return

            except Exception as e:
                logger.error(f"Failed to create person via API: {e}")
                ErrorHandler.show_error(
                    self, tr("wizard.person_dialog.create_failed", error_msg=map_exception(e)), tr("common.error")
                )
                return

            # Step 1.5: Upload identification files
            if self.uploaded_files and self._survey_id and person_id:
                self._upload_identification_files(person_id)

            # Step 2: Link person to property unit with relation
            if self._survey_id and self._unit_id and person_id:
                relation_data = person_data.get('relation_data', {})
                relation_data['person_id'] = person_id
                if not relation_data.get('rel_type'):
                    relation_data['rel_type'] = person_data.get('relationship_type')

                try:
                    relation_response = self._api_service.link_person_to_unit(
                        self._survey_id, self._unit_id, relation_data
                    )

                    relation_response_text = json.dumps(relation_response, indent=2, ensure_ascii=False, default=str)
                    print(f"\n[RELATION API RESPONSE]\n{relation_response_text}")
                    ErrorHandler.show_success(
                        self,
                        f"POST /api/v1/Surveys/{self._survey_id}/units/{self._unit_id}/relations\n\n{relation_response_text[:1000]}",
                        "Link Person to Unit API Response"
                    )
                    logger.info(f"Person {person_id} linked to unit {self._unit_id}")

                    relation_id = (
                        relation_response.get("id") or relation_response.get("relationId") or
                        relation_response.get("Id") or relation_response.get("RelationId") or
                        relation_response.get("personPropertyRelationId") or
                        relation_response.get("PersonPropertyRelationId") or ""
                    )

                    if relation_id and self.relation_uploaded_files:
                        self._upload_tenure_files(relation_id)

                except Exception as e:
                    logger.error(f"Failed to link person to unit: {e}")
                    Toast.show_toast(self, tr("wizard.person_dialog.link_failed", error_msg=map_exception(e)), Toast.WARNING)

        self.accept()

    def _upload_identification_files(self, person_id: str):
        """Upload identification files for the created person."""
        if not self.uploaded_files:
            return
        logger.warning(f"File upload skipped: {len(self.uploaded_files)} identification file(s) for person {person_id}")

    def _upload_tenure_files(self, relation_id: str):
        """Upload tenure evidence files for the created relation."""
        if not self.relation_uploaded_files:
            return
        logger.warning(f"File upload skipped: {len(self.relation_uploaded_files)} tenure file(s) for relation {relation_id}")
