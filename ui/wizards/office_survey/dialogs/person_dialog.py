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
from PyQt5.QtCore import Qt, QDate, QUrl
from PyQt5.QtGui import QColor, QPixmap

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
        self.setFixedSize(589, 674)  # 565+24 width, 650+24 height (12px shadow margin each side)
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
        outer_layout.setContentsMargins(12, 12, 12, 12)  # Margin for shadow visibility
        outer_layout.setSpacing(0)

        # White rounded content frame
        content_frame = QFrame()
        content_frame.setObjectName("ContentFrame")
        content_frame.setStyleSheet("""
            QFrame#ContentFrame {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#ContentFrame QWidget {
                background-color: transparent;
            }
            QFrame#ContentFrame QLineEdit,
            QFrame#ContentFrame QComboBox,
            QFrame#ContentFrame QDateEdit,
            QFrame#ContentFrame QDoubleSpinBox,
            QFrame#ContentFrame QTextEdit {
                background-color: #f0f7ff;
            }
            QFrame#ContentFrame QLineEdit:focus,
            QFrame#ContentFrame QComboBox:focus,
            QFrame#ContentFrame QDateEdit:focus,
            QFrame#ContentFrame QDoubleSpinBox:focus,
            QFrame#ContentFrame QTextEdit:focus {
                border: 1px solid #E0E6ED;
            }
        """)

        # Drop shadow for floating effect
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(content_frame)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        content_frame.setGraphicsEffect(shadow)

        outer_layout.addWidget(content_frame)

        main_layout = QVBoxLayout(content_frame)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # Dialog title (right-aligned for RTL)
        title_text = tr("wizard.person_dialog.title_edit") if self.editing_mode else tr("wizard.person_dialog.title_add")
        self._dialog_title = QLabel(title_text)
        self._dialog_title.setAlignment(Qt.AlignAbsolute | Qt.AlignRight)
        self._dialog_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(self._dialog_title)

        # Progress indicator (3 bars)
        self._setup_progress_indicator(main_layout)

        # Tab widget with hidden tab bar
        self.tab_widget = QTabWidget()
        self.tab_widget.tabBar().setVisible(False)
        self.tab_widget.setAutoFillBackground(False)
        self.tab_widget.setStyleSheet("""
            QTabWidget {
                background-color: transparent;
                border: none;
            }
            QTabWidget::pane {
                border: none;
                background-color: transparent;
                padding: 0px;
            }
            QTabWidget > QWidget {
                background-color: transparent;
            }
        """)

        self._setup_tab1_personal()
        self._setup_tab2_contact()
        self._setup_tab3_relation()

        # Ensure all tab pages and internal stacked widget are transparent
        from PyQt5.QtWidgets import QStackedWidget
        stacked = self.tab_widget.findChild(QStackedWidget)
        if stacked:
            stacked.setAutoFillBackground(False)
            stacked.setStyleSheet("background-color: transparent;")
        for i in range(self.tab_widget.count()):
            page = self.tab_widget.widget(i)
            page.setAutoFillBackground(False)

        # Connect field signals for live progress tracking
        self._connect_progress_signals()

        self.tab_widget.currentChanged.connect(self._update_progress)
        main_layout.addWidget(self.tab_widget)

    def _setup_progress_indicator(self, layout):
        """Create 3-bar progress indicator with gradient fill."""
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)
        self._progress_bars = []
        for _ in range(3):
            bar = QFrame()
            bar.setFixedHeight(5)
            bar.setLayoutDirection(Qt.LeftToRight)  # Prevent RTL from flipping gradient
            bar.setStyleSheet("QFrame { background-color: #e0e6ed; border-radius: 2px; }")
            self._progress_bars.append(bar)
            progress_layout.addWidget(bar)
        layout.addLayout(progress_layout)

    def _connect_progress_signals(self):
        """Connect all form field signals to update progress bars live."""
        # Tab 1 fields
        self.first_name.textChanged.connect(self._update_all_progress)
        self.last_name.textChanged.connect(self._update_all_progress)
        self.father_name.textChanged.connect(self._update_all_progress)
        self.mother_name.textChanged.connect(self._update_all_progress)
        self.birth_place.currentIndexChanged.connect(self._update_all_progress)
        self.gender.currentIndexChanged.connect(self._update_all_progress)
        self.nationality.currentIndexChanged.connect(self._update_all_progress)
        self.national_id.textChanged.connect(self._update_all_progress)

        # Tab 2 fields
        self.person_role.currentIndexChanged.connect(self._update_all_progress)
        self.email.textChanged.connect(self._update_all_progress)
        self.phone.textChanged.connect(self._update_all_progress)
        self.landline.textChanged.connect(self._update_all_progress)

        # Tab 3 fields
        self.contract_type.currentIndexChanged.connect(self._update_all_progress)
        self.rel_type_combo.currentIndexChanged.connect(self._update_all_progress)
        self.ownership_share.valueChanged.connect(self._update_all_progress)
        self.evidence_type.currentIndexChanged.connect(self._update_all_progress)
        self.evidence_desc.textChanged.connect(self._update_all_progress)
        self.notes.textChanged.connect(self._update_all_progress)

    def _calculate_tab_fill(self, tab_index: int) -> float:
        """Calculate fill percentage (0.0 to 1.0) for a given tab."""
        if tab_index == 0:
            fields = [
                bool(self.first_name.text().strip()),
                bool(self.last_name.text().strip()),
                bool(self.father_name.text().strip()),
                bool(self.mother_name.text().strip()),
                self.birth_place.currentIndex() > 0,
                self.gender.currentIndex() > 0,
                self.nationality.currentIndex() > 0,
                bool(self.national_id.text().strip()),
            ]
        elif tab_index == 1:
            fields = [
                self.person_role.currentIndex() > 0,
                bool(self.email.text().strip()),
                bool(self.phone.text().strip()),
                bool(self.landline.text().strip()),
            ]
        else:
            fields = [
                self.contract_type.currentIndex() > 0,
                self.rel_type_combo.currentIndex() > 0,
                self.ownership_share.value() > 0,
                self.evidence_type.currentIndex() > 0,
                bool(self.evidence_desc.text().strip()),
                bool(self.notes.toPlainText().strip()),
            ]
        filled = sum(fields)
        return filled / len(fields) if fields else 0.0

    def _update_bar_style(self, bar: QFrame, fill_pct: float):
        """Update a single progress bar with gradient fill."""
        if fill_pct <= 0:
            bar.setStyleSheet("QFrame { background-color: #e0e6ed; border-radius: 2px; }")
        elif fill_pct >= 1.0:
            bar.setStyleSheet("QFrame { background-color: #4a90e2; border-radius: 2px; }")
        else:
            # Gradient: blue up to fill_pct, then gray
            stop = round(fill_pct, 3)
            stop2 = round(fill_pct + 0.001, 3)
            bar.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:1, y1:0, x2:0, y2:0,
                        stop:0 #4a90e2, stop:{stop} #4a90e2,
                        stop:{stop2} #e0e6ed, stop:1 #e0e6ed);
                    border-radius: 2px;
                }}
            """)

    def _update_all_progress(self, *args):
        """Update all 3 progress bars based on field completion."""
        for i, bar in enumerate(self._progress_bars):
            pct = self._calculate_tab_fill(i)
            self._update_bar_style(bar, pct)

    def _update_progress(self, current_tab: int):
        """Update progress when tab changes (also recalc fill)."""
        self._update_all_progress()

    # Tab 1: Personal Information

    def _setup_tab1_personal(self):
        """Tab 1: Names, birth place, birth date, gender, nationality, national ID, ID photos."""
        tab = QWidget()
        tab.setLayoutDirection(Qt.RightToLeft)
        tab.setStyleSheet("background-color: transparent;")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(10)

        label_style = "color: #555; font-weight: 600; font-size: 11pt; background: transparent;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
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
        btn_layout.setSpacing(3)
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
        tab.setStyleSheet("background-color: transparent;")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(10)

        label_style = "color: #555; font-weight: 600; font-size: 11pt; background: transparent;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
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
        btn_layout.setSpacing(3)
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
        tab.setStyleSheet("background-color: transparent;")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(10)

        label_style = "color: #555; font-weight: 600; font-size: 11pt; background: transparent;"
        from ui.style_manager import StyleManager

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
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
                background-color: #f0f7ff;
                color: #333;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #E0E6ED;
            }
        """)
        # RTL text direction for Arabic
        self.notes.setLayoutDirection(Qt.RightToLeft)
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
        radio_widget.setStyleSheet("background-color: transparent;")
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
        btn_layout.setSpacing(3)
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
                    border: 1px solid #4a90e2;
                    border-radius: 8px;
                    padding: 9px 40px;
                    font-weight: bold;
                    font-size: 14px;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background-color: #357ABD;
                    border-color: #357ABD;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #4a90e2;
                    border: 1.5px solid #b0b8c4;
                    border-radius: 8px;
                    padding: 9px 40px;
                    font-weight: bold;
                    font-size: 14px;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background-color: #f5f7fa;
                    border-color: #8e99a8;
                }
            """)
            # Light shadow so white button floats above the card
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            btn_shadow = QGraphicsDropShadowEffect(btn)
            btn_shadow.setBlurRadius(12)
            btn_shadow.setOffset(0, 2)
            btn_shadow.setColor(QColor(0, 0, 0, 30))
            btn.setGraphicsEffect(btn_shadow)
        if callback:
            btn.clicked.connect(callback)
        return btn

    def _create_upload_frame(self, browse_callback, obj_name: str) -> QFrame:
        """Create a file upload frame with icon + blue text + thumbnail previews."""
        from ui.components.icon import Icon

        frame = QFrame()
        frame.setObjectName(obj_name)
        frame.setMinimumHeight(55)
        frame.setStyleSheet(f"""
            QFrame#{obj_name} {{
                border: 2px dashed #B0C4DE;
                border-radius: 8px;
                background-color: transparent;
            }}
        """)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(6)

        # Row: centered icon + text, thumbnails on the side
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        # Thumbnails container (left side in RTL = trailing end)
        thumbnails_container = QWidget()
        thumbnails_container.setStyleSheet("border: none; background: transparent;")
        thumbnails_layout = QHBoxLayout(thumbnails_container)
        thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        thumbnails_layout.setSpacing(6)
        row_layout.addWidget(thumbnails_container)

        row_layout.addStretch()

        # Upload icon (centered)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        upload_pixmap = Icon.load_pixmap("upload_file", size=20)
        if upload_pixmap and not upload_pixmap.isNull():
            icon_lbl.setPixmap(upload_pixmap)
        else:
            icon_lbl.setText("📎")
            icon_lbl.setStyleSheet("border: none; font-size: 16px; background: transparent;")
        icon_lbl.setCursor(Qt.PointingHandCursor)
        icon_lbl.mousePressEvent = lambda e: browse_callback()
        row_layout.addWidget(icon_lbl)

        # Blue underlined text (centered, next to icon)
        text_btn = QPushButton(tr("wizard.person_dialog.attach_id_photos"))
        text_btn.setStyleSheet("""
            QPushButton {
                color: #4a90e2;
                text-decoration: underline;
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 500;
                padding: 0px;
            }
            QPushButton:hover { color: #357ABD; }
        """)
        text_btn.setCursor(Qt.PointingHandCursor)
        text_btn.clicked.connect(browse_callback)
        row_layout.addWidget(text_btn)

        row_layout.addStretch()

        frame_layout.addLayout(row_layout)

        # Store references
        frame._thumbnails_container = thumbnails_container
        frame._thumbnails_layout = thumbnails_layout
        frame._text_btn = text_btn
        return frame

    def _create_thumbnail_widget(self, file_path: str, remove_callback) -> QWidget:
        """Create a single thumbnail widget with image preview and X remove button."""
        container = QWidget()
        container.setFixedSize(48, 48)
        container.setStyleSheet("border: none; background: transparent;")

        # Thumbnail image
        thumb = QLabel(container)
        thumb.setFixedSize(44, 44)
        thumb.move(4, 4)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            QLabel {
                border: 1px solid #E0E6ED;
                border-radius: 6px;
                background-color: #FFFFFF;
            }
        """)
        thumb.setCursor(Qt.PointingHandCursor)

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            thumb.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            thumb.setText("📄")

        # Click to open image in system viewer
        from PyQt5.QtGui import QDesktopServices
        def _open_file(e, fp=file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(fp))
        thumb.mousePressEvent = _open_file

        # X remove button (small dark circle, top-left corner)
        x_btn = QLabel(container)
        x_btn.setFixedSize(18, 18)
        x_btn.move(0, 0)
        x_btn.setText("✕")
        x_btn.setAlignment(Qt.AlignCenter)
        x_btn.setStyleSheet("""
            QLabel {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border-radius: 9px;
                font-size: 10px;
                font-weight: bold;
                border: none;
            }
        """)
        x_btn.setCursor(Qt.PointingHandCursor)
        def _remove_file(e, fp=file_path):
            remove_callback(fp)
        x_btn.mousePressEvent = _remove_file

        return container

    def _update_upload_thumbnails(self, obj_name: str, file_paths: list):
        """Refresh thumbnail display in the specified upload frame."""
        frame = self.findChild(QFrame, obj_name)
        if not frame or not hasattr(frame, '_thumbnails_layout'):
            return

        layout = frame._thumbnails_layout
        # Clear existing thumbnails
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new thumbnails
        if obj_name == "id_upload":
            remove_fn = self._remove_uploaded_file
        else:
            remove_fn = self._remove_relation_file

        for fp in file_paths:
            thumb_widget = self._create_thumbnail_widget(fp, remove_fn)
            layout.addWidget(thumb_widget)

    def _remove_uploaded_file(self, file_path: str):
        """Remove an ID photo file and refresh thumbnails."""
        if file_path in self.uploaded_files:
            self.uploaded_files.remove(file_path)
        self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _remove_relation_file(self, file_path: str):
        """Remove a relation evidence file and refresh thumbnails."""
        if file_path in self.relation_uploaded_files:
            self.relation_uploaded_files.remove(file_path)
        self._update_upload_thumbnails("rel_upload", self.relation_uploaded_files)

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
        """Custom input style with light blue background."""
        return """
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: #f0f7ff;
                color: #333;
                font-size: 13px;
                min-height: 20px;
                max-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
                border: 1px solid #E0E6ED;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                background-image: url(assets/images/down.png);
                background-repeat: no-repeat;
                background-position: center;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #E0E6ED;
                border-radius: 0px;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                padding: 4px;
                selection-background-color: #e8f0fe;
                selection-color: #333;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #f0f7ff;
            }
            QComboBox QAbstractItemView QScrollBar:vertical {
                background: transparent;
                width: 5px;
                margin: 4px 0px;
                border-radius: 2px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical {
                background: #C4CDD5;
                min-height: 30px;
                border-radius: 2px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {
                background: #919EAB;
            }
            QComboBox QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QComboBox QAbstractItemView QScrollBar::add-page:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-page:vertical {
                background: none;
            }
        """

    def _date_input_style(self) -> str:
        """Custom date input style with light blue background."""
        return """
            QDateEdit {
                background-color: #f0f7ff;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                color: #333;
                font-size: 13px;
                min-height: 20px;
                max-height: 20px;
            }
            QDateEdit:focus {
                border: 1px solid #E0E6ED;
            }
            QDateEdit::drop-down {
                border: none;
                width: 25px;
                subcontrol-position: left center;
                background-image: url(assets/images/calender.png);
                background-repeat: no-repeat;
                background-position: center;
            }
            QDateEdit::down-arrow {
                width: 0px;
                height: 0px;
            }
            /* Calendar popup styling */
            QCalendarWidget {
                background-color: #FFFFFF;
                border: 1px solid #E0E6ED;
                border-radius: 10px;
            }
            QCalendarWidget QToolButton {
                color: #333;
                background-color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #f0f7ff;
            }
            QCalendarWidget QToolButton::menu-indicator {
                image: none;
            }
            QCalendarWidget QToolButton#qt_calendar_prevmonth {
                qproperty-icon: none;
                qproperty-text: "<";
                color: #4a90e2;
                font-weight: bold;
                font-size: 16px;
            }
            QCalendarWidget QToolButton#qt_calendar_nextmonth {
                qproperty-icon: none;
                qproperty-text: ">";
                color: #4a90e2;
                font-weight: bold;
                font-size: 16px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E0E6ED;
                padding: 4px;
            }
            QCalendarWidget QAbstractItemView {
                background-color: #FFFFFF;
                color: #333;
                selection-background-color: #4a90e2;
                selection-color: white;
                font-size: 12px;
                outline: none;
                border: none;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #333;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #B0BEC5;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #f8faff;
            }
            QCalendarWidget QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                color: #333;
            }
            QCalendarWidget QMenu::item:selected {
                background-color: #e8f0fe;
                color: #333;
            }
            QCalendarWidget QSpinBox {
                background-color: #FFFFFF;
                color: #333;
                border: 1px solid #E0E6ED;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 13px;
            }
        """

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
            self.uploaded_files.extend(file_paths)
            self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _browse_relation_files(self):
        """Browse for relation evidence files."""
        from PyQt5.QtWidgets import QFileDialog
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            self.relation_uploaded_files.extend(file_paths)
            self._update_upload_thumbnails("rel_upload", self.relation_uploaded_files)

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
