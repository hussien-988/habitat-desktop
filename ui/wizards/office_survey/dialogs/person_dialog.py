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
    QGridLayout, QTextEdit, QTabWidget,
    QRadioButton, QButtonGroup, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate, QUrl
from PyQt5.QtGui import QColor, QPixmap, QRegExpValidator, QDoubleValidator
from PyQt5.QtCore import QRegExp as QtRegExp

from app.config import Config
from services.validation_service import ValidationService
from services.api_client import get_api_client
from services.translation_manager import tr
from services.error_mapper import map_exception
from services.display_mappings import (
    get_relation_type_options, get_contract_type_options, get_evidence_type_options,
    get_gender_options, get_nationality_options
)
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDialog(QDialog):
    """Dialog for creating or editing a person - 3 tabs."""

    def __init__(self, person_data: Optional[Dict] = None, existing_persons: List[Dict] = None, parent=None,
                 auth_token: Optional[str] = None, survey_id: Optional[str] = None,
                 household_id: Optional[str] = None, unit_id: Optional[str] = None,
                 read_only: bool = False):
        super().__init__(parent)
        self.person_data = person_data
        self.existing_persons = existing_persons or []
        self.editing_mode = person_data is not None
        self.read_only = read_only
        self.validation_service = ValidationService()
        self.uploaded_files = []
        self.relation_uploaded_files = []  # List[Dict]: {path, issue_date, hash}

        # API integration
        self._survey_id = survey_id
        self._household_id = household_id
        self._unit_id = unit_id
        self._api_service = get_api_client()
        if auth_token:
            self._api_service.set_access_token(auth_token)
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'
        self._api_person_id = None
        self._api_relation_id = None
        self._evidence_ids = {}       # {normalized_path: evidence_id} for ID files
        self._server_evidences = []   # List[EvidenceDto] from server on edit

        self.setModal(True)
        self.setFixedSize(589, 674)  # 565+24 width, 650+24 height (12px shadow margin each side)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

        if self.editing_mode and person_data:
            self._load_person_data(person_data)

        if self.read_only:
            self._apply_read_only_mode()

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
            QFrame#ContentFrame QLabel,
            QFrame#ContentFrame QRadioButton {
                background-color: transparent;
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
        if self.read_only:
            title_text = tr("wizard.person_dialog.title_view")
        elif self.editing_mode:
            title_text = tr("wizard.person_dialog.title_edit")
        else:
            title_text = tr("wizard.person_dialog.title_add")
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

    def _apply_read_only_mode(self):
        """Disable all input fields and change buttons for read-only viewing."""
        from PyQt5.QtWidgets import QLineEdit, QComboBox, QDateEdit, QTextEdit, QDoubleSpinBox, QRadioButton

        # Disable all input widgets
        for widget in self.findChildren(QLineEdit):
            widget.setReadOnly(True)
        for widget in self.findChildren(QComboBox):
            widget.setEnabled(False)
        for widget in self.findChildren(QDateEdit):
            widget.setReadOnly(True)
        for widget in self.findChildren(QTextEdit):
            widget.setReadOnly(True)
        for widget in self.findChildren(QDoubleSpinBox):
            widget.setReadOnly(True)
        for widget in self.findChildren(QRadioButton):
            widget.setEnabled(False)

        # Replace all buttons with navigation-only buttons per tab
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            tab_layout = tab.layout()
            if not tab_layout:
                continue
            # Find and remove button layouts (last item in each tab)
            last_item = tab_layout.itemAt(tab_layout.count() - 1)
            if last_item and last_item.layout():
                btn_layout = last_item.layout()
                # Immediately remove old buttons (hide + reparent, not deleteLater)
                widgets_to_remove = []
                for j in range(btn_layout.count()):
                    item = btn_layout.itemAt(j)
                    if item and item.widget():
                        widgets_to_remove.append(item.widget())
                for w in widgets_to_remove:
                    w.hide()
                    btn_layout.removeWidget(w)
                    w.setParent(None)
                # Add navigation buttons for read-only
                if i == 0:
                    btn_layout.addWidget(self._create_btn(tr("common.cancel"), primary=False, callback=self.reject))
                    btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab2))
                elif i == 1:
                    btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab1))
                    btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab3))
                else:
                    btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab2_back))
                    btn_layout.addWidget(self._create_btn(tr("common.cancel"), primary=True, callback=self.reject))

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
        self.ownership_share.textChanged.connect(self._update_all_progress)
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
                bool(self.ownership_share.text().strip()),
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
        # Name validator: Arabic + Latin letters + spaces + hyphens + dots
        # Note: non-raw string so Python converts \u0600-\u06FF to actual Arabic characters
        _name_validator = QRegExpValidator(QtRegExp("[\u0600-\u06FFa-zA-Z\\s.\\-']+"))

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText(tr("wizard.person_dialog.first_name_placeholder"))
        self.first_name.setValidator(_name_validator)
        self.first_name.setStyleSheet(self._input_style())
        grid.addWidget(self.first_name, row, 0)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText(tr("wizard.person_dialog.last_name_placeholder"))
        self.last_name.setValidator(_name_validator)
        self.last_name.setStyleSheet(self._input_style())
        grid.addWidget(self.last_name, row, 1)
        row += 1

        # Row: Father Name | Mother Name
        grid.addWidget(self._label(tr("wizard.person_dialog.father_name"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.mother_name"), label_style), row, 1)
        row += 1
        self.father_name = QLineEdit()
        self.father_name.setPlaceholderText(tr("wizard.person_dialog.father_name_placeholder"))
        self.father_name.setValidator(_name_validator)
        self.father_name.setStyleSheet(self._input_style())
        grid.addWidget(self.father_name, row, 0)

        self.mother_name = QLineEdit()
        self.mother_name.setPlaceholderText(tr("wizard.person_dialog.mother_name_placeholder"))
        self.mother_name.setValidator(_name_validator)
        self.mother_name.setStyleSheet(self._input_style())
        grid.addWidget(self.mother_name, row, 1)
        row += 1

        # Row: Birth Date
        grid.addWidget(self._label(tr("wizard.person_dialog.birth_date"), label_style), row, 0)
        row += 1
        self.birth_date = QDateEdit()
        self.birth_date.setCalendarPopup(True)
        self.birth_date.setDate(QDate(1980, 1, 1))
        self.birth_date.setMinimumDate(QDate(1900, 1, 1))
        self.birth_date.setMaximumDate(QDate.currentDate())
        self.birth_date.setDisplayFormat("yyyy-MM-dd")
        self.birth_date.setStyleSheet(self._date_input_style())
        grid.addWidget(self.birth_date, row, 0)
        row += 1

        # Row: Gender | Nationality
        grid.addWidget(self._label(tr("wizard.person_dialog.gender"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.nationality"), label_style), row, 1)
        row += 1
        self.gender = QComboBox()
        self.gender.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_gender_options():
            self.gender.addItem(display_name, code)
        self.gender.setStyleSheet(self._input_style())
        grid.addWidget(self.gender, row, 0)

        self.nationality = QComboBox()
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_nationality_options():
            self.nationality.addItem(display_name, code)
        self.nationality.setStyleSheet(self._input_style())
        grid.addWidget(self.nationality, row, 1)
        row += 1

        # Row: National ID (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.national_id"), label_style), row, 0, 1, 2)
        row += 1
        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("0000000000")
        self.national_id.setValidator(QRegExpValidator(QtRegExp(r"\d{0,11}")))
        self.national_id.setStyleSheet(self._input_style())
        grid.addWidget(self.national_id, row, 0, 1, 2)
        row += 1

        # ID Photos upload
        grid.addWidget(self._label(tr("wizard.person_dialog.attach_id_photos"), label_style), row, 0, 1, 2)
        row += 1
        upload_frame = self._create_upload_frame(self._browse_files, "id_upload", button_text=tr("wizard.person_dialog.attach_id_photos"))
        grid.addWidget(upload_frame, row, 0, 1, 2)

        tab_layout.addLayout(grid)
        tab_layout.addStretch()

        # Buttons: Next | Cancel
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addWidget(self._create_btn(tr("common.cancel"), primary=False, callback=self.reject))
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab2))
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
        self.email.setValidator(QRegExpValidator(QtRegExp(r"[a-zA-Z0-9@._\-+]+")))
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
        self.phone.setValidator(QRegExpValidator(QtRegExp(r"\d{0,8}")))
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
        self.landline.setValidator(QRegExpValidator(QtRegExp(r"\d{0,7}")))
        self.landline.setStyleSheet(self._input_style())
        grid.addWidget(self.landline, row, 0, 1, 2)

        tab_layout.addLayout(grid)
        tab_layout.addStretch()

        # Buttons: Next | Previous
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab1))
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab3))
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

        self.ownership_share = QLineEdit()
        self.ownership_share.setPlaceholderText("%")
        self.ownership_share.setValidator(QDoubleValidator(0, 100, 2, self))
        self.ownership_share.editingFinished.connect(self._clamp_ownership_share)
        self.ownership_share.setStyleSheet(self._input_style())
        grid.addWidget(self.ownership_share, row, 1)
        row += 1

        # Row: Supporting Docs | Description
        grid.addWidget(self._label(tr("wizard.person_dialog.evidence_type"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.evidence_description"), label_style), row, 1)
        row += 1
        self.evidence_type = QComboBox()
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
                font-size: 14px;
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
        self._rel_upload_frame = self._create_upload_frame(self._browse_relation_files, "rel_upload", button_text=tr("wizard.person_dialog.attach_document"))
        grid.addWidget(self._rel_upload_frame, row, 0, 1, 2)

        # Toggle upload frame visibility based on radio
        self.rb_no_docs.toggled.connect(lambda checked: self._rel_upload_frame.setVisible(not checked))

        tab_layout.addLayout(grid)
        tab_layout.addStretch()

        # Buttons: Save | Previous
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab2_back))
        btn_layout.addWidget(self._create_btn(tr("common.save"), primary=True, callback=self._on_final_save))
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
        btn.setFixedHeight(44)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    color: white;
                    border: 1px solid #4a90e2;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
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
                    font-weight: bold;
                    font-size: 14px;
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

    def _create_upload_frame(self, browse_callback, obj_name: str, button_text: str = None) -> QFrame:
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
        text_btn = QPushButton(button_text or tr("wizard.person_dialog.attach_id_photos"))
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
        """Remove an ID photo file and refresh thumbnails. Deletes from server if previously uploaded."""
        import os
        norm = os.path.normpath(file_path)
        # Delete from server if evidence was uploaded
        if self._use_api and norm in self._evidence_ids and self._survey_id:
            evidence_id = self._evidence_ids[norm]
            try:
                self._api_service.delete_evidence(self._survey_id, evidence_id)
                logger.info(f"Evidence deleted from server: {evidence_id}")
                del self._evidence_ids[norm]
            except Exception as e:
                logger.error(f"Failed to delete evidence {evidence_id}: {e}")
        if file_path in self.uploaded_files:
            self.uploaded_files.remove(file_path)
        self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _remove_relation_file(self, file_path: str):
        """Remove a relation evidence file and refresh thumbnails. Deletes from server if previously uploaded."""
        entry = next((f for f in self.relation_uploaded_files if f["path"] == file_path), None)
        # Delete from server if evidence was uploaded
        if self._use_api and entry and entry.get("evidence_id") and self._survey_id:
            try:
                self._api_service.delete_evidence(self._survey_id, entry["evidence_id"])
                logger.info(f"Tenure evidence deleted from server: {entry['evidence_id']}")
            except Exception as e:
                logger.error(f"Failed to delete tenure evidence: {e}")
        self.relation_uploaded_files = [f for f in self.relation_uploaded_files if f["path"] != file_path]
        file_paths_for_thumbs = [f["path"] for f in self.relation_uploaded_files]
        self._update_upload_thumbnails("rel_upload", file_paths_for_thumbs)

    def _input_style(self) -> str:
        """Custom input style with light blue background."""
        down_img = str(Config.IMAGES_DIR / "down.png").replace("\\", "/")
        return f"""
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {{
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: #f0f7ff;
                color: #333;
                font-size: 14px;
                min-height: 20px;
                max-height: 20px;
            }}
            QComboBox {{
                padding-left: 35px;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {{
                border: 1px solid #E0E6ED;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                image: url({down_img});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #FFFFFF;
                border: 1px solid #E0E6ED;
                border-radius: 0px;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                padding: 4px;
                selection-background-color: #e8f0fe;
                selection-color: #333;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 32px;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #f0f7ff;
            }}
            QComboBox QAbstractItemView QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 4px 0px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView QScrollBar::handle:vertical {{
                background: #C4CDD5;
                min-height: 30px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {{
                background: #919EAB;
            }}
            QComboBox QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QComboBox QAbstractItemView QScrollBar::add-page:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """

    def _date_input_style(self) -> str:
        """Custom date input style with light blue background."""
        cal_img = str(Config.IMAGES_DIR / "calender.png").replace("\\", "/")
        return """
            QDateEdit {
                background-color: #f0f7ff;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                color: #333;
                font-size: 14px;
                min-height: 20px;
                max-height: 20px;
            }
            QDateEdit:focus {
                border: 1px solid #E0E6ED;
            }
            QDateEdit::drop-down {
                border: none;
                width: 25px;
                subcontrol-position: right center;
            }
            QDateEdit::down-arrow {
                image: url(""" + cal_img + """);
                width: 16px;
                height: 16px;
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
        import re
        if self.read_only:
            self.tab_widget.setCurrentIndex(1)
            return
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        if not first:
            Toast.show_toast(self, tr("wizard.person_dialog.enter_first_name"), Toast.WARNING)
            return
        if not last:
            Toast.show_toast(self, tr("wizard.person_dialog.enter_last_name"), Toast.WARNING)
            return
        # Validate names contain actual letters (not just symbols/numbers)
        name_pattern = re.compile(r'^[\u0600-\u06FFa-zA-Z\s.\-\']{2,}$')
        if not name_pattern.match(first):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_first_name"), Toast.WARNING)
            return
        if not name_pattern.match(last):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_last_name"), Toast.WARNING)
            return
        if self.national_id.text().strip() and not self._validate_national_id():
            Toast.show_toast(self, tr("wizard.person_dialog.nid_invalid"), Toast.WARNING)
            return
        if not self.uploaded_files:
            Toast.show_toast(self, tr("wizard.person_dialog.id_photo_required"), Toast.WARNING)
            return
        self.tab_widget.setCurrentIndex(1)

    def _go_to_tab3(self):
        """Tab 2 → Tab 3: Validate contact info then switch."""
        import re
        if self.read_only:
            self.tab_widget.setCurrentIndex(2)
            return
        # Validate phone (optional but if filled must be valid)
        if not self._validate_mobile(self.phone.text().strip()):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_mobile"), Toast.WARNING)
            return
        if not self._validate_landline(self.landline.text().strip()):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_landline"), Toast.WARNING)
            return
        # Validate email (optional but if filled must be Latin + valid format)
        email_text = self.email.text().strip()
        if email_text and not re.match(r'^[a-zA-Z0-9@._\-+]+$', email_text):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_email_chars"), Toast.WARNING)
            return
        if email_text and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email_text):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_email"), Toast.WARNING)
            return
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
        """Browse for ID photo files with duplicate detection."""
        from PyQt5.QtWidgets import QFileDialog
        import os
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            existing_names = {os.path.normpath(f) for f in self.uploaded_files}
            duplicates = []
            new_files = []
            for fp in file_paths:
                norm = os.path.normpath(fp)
                if norm in existing_names:
                    duplicates.append(fp)
                else:
                    new_files.append(fp)
                    existing_names.add(norm)
            if duplicates:
                dup_names = [os.path.basename(f) for f in duplicates]
                replace = self._show_duplicate_file_dialog(dup_names)
                if replace:
                    # Replace: add new files only (duplicates already exist)
                    self.uploaded_files.extend(new_files)
                # else: Cancel - don't add anything
            else:
                self.uploaded_files.extend(new_files)
            self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _browse_relation_files(self):
        """Browse for relation evidence files with dual-level duplicate detection."""
        from PyQt5.QtWidgets import QFileDialog
        import os
        import hashlib

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if not file_paths:
            return

        existing_paths = {os.path.normpath(f["path"]) for f in self.relation_uploaded_files}
        existing_hashes = {f["hash"] for f in self.relation_uploaded_files if f.get("hash")}

        duplicates = []
        new_files = []

        for fp in file_paths:
            norm = os.path.normpath(fp)
            # Level 1: Same path already added
            if norm in existing_paths:
                duplicates.append(fp)
                continue
            # Level 2: Same content (different path, same hash)
            file_hash = self._compute_file_hash(fp)
            if file_hash and file_hash in existing_hashes:
                duplicates.append(fp)
                continue
            new_files.append({"path": fp, "hash": file_hash})
            existing_paths.add(norm)
            if file_hash:
                existing_hashes.add(file_hash)

        if duplicates:
            dup_names = [os.path.basename(f) for f in duplicates]
            replace = self._show_duplicate_file_dialog(dup_names)
            if not replace:
                return

        if not new_files:
            return

        # Issue date: single file → direct dialog, multiple → ask same or separate
        if len(new_files) == 1:
            issue_date = self._show_issue_date_dialog(os.path.basename(new_files[0]["path"]))
            if issue_date is None:
                return
            new_files[0]["issue_date"] = issue_date
        elif len(new_files) > 1:
            use_same = self._ask_same_or_separate_dates(len(new_files))
            if use_same is None:
                return
            if use_same:
                issue_date = self._show_issue_date_dialog()
                if issue_date is None:
                    return
                for f in new_files:
                    f["issue_date"] = issue_date
            else:
                for f in new_files:
                    fname = os.path.basename(f["path"])
                    issue_date = self._show_issue_date_dialog(fname)
                    if issue_date is None:
                        continue
                    f["issue_date"] = issue_date
                new_files = [f for f in new_files if f.get("issue_date")]
                if not new_files:
                    return

        self.relation_uploaded_files.extend(new_files)
        file_paths_for_thumbs = [f["path"] for f in self.relation_uploaded_files]
        self._update_upload_thumbnails("rel_upload", file_paths_for_thumbs)

    def _show_duplicate_file_dialog(self, file_names: list) -> bool:
        """Show a small floating dialog for duplicate files. Returns True to replace, False to cancel."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QFont, QColor
        from ui.font_utils import create_font, FontManager

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(300)

        # Container with white background + rounded corners
        container = QWidget(dlg)
        container.setObjectName("dup_container")
        container.setStyleSheet("""
            QWidget#dup_container {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(20, 20, 20, 16)
        c_layout.setSpacing(10)

        # Warning icon (small circle)
        icon_lbl = QLabel("⚠")
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            background-color: #FEF3C7;
            border-radius: 20px;
            font-size: 18px;
        """)
        c_layout.addWidget(icon_lbl, 0, Qt.AlignCenter)

        # Title
        title_lbl = QLabel(tr("wizard.person_dialog.duplicate_files_title"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet("color: #1F2937; background: transparent;")
        c_layout.addWidget(title_lbl)

        # File names
        names_text = "\n".join(file_names[:3])
        if len(file_names) > 3:
            names_text += f"\n+{len(file_names) - 3} ..."
        msg_lbl = QLabel(names_text)
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        msg_lbl.setStyleSheet("color: #6B7280; background: transparent;")
        c_layout.addWidget(msg_lbl)

        c_layout.addSpacing(4)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedHeight(34)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        cancel_btn.clicked.connect(dlg.reject)

        replace_btn = QPushButton(tr("wizard.person_dialog.replace_file"))
        replace_btn.setFixedHeight(34)
        replace_btn.setCursor(Qt.PointingHandCursor)
        replace_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        replace_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        replace_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(replace_btn, 1)
        c_layout.addLayout(btn_row)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        return dlg.exec_() == QDialog.Accepted

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA-256 hash of a file for duplicate detection."""
        import hashlib
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (IOError, OSError) as e:
            logger.warning(f"Could not compute hash for {file_path}: {e}")
            return ""

    def _show_issue_date_dialog(self, filename: str = None) -> str:
        """Show a mini popup to enter document issue date. Returns ISO date string or None if cancelled."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QFont, QColor
        from ui.font_utils import create_font, FontManager

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(320)

        container = QWidget(dlg)
        container.setObjectName("date_container")
        container.setStyleSheet("""
            QWidget#date_container {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(20, 20, 20, 16)
        c_layout.setSpacing(12)

        # Title
        title_lbl = QLabel(tr("wizard.person_dialog.issue_date_title"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet("color: #1F2937; background: transparent;")
        c_layout.addWidget(title_lbl)

        # Filename subtitle (when per-file mode)
        if filename:
            file_lbl = QLabel(filename)
            file_lbl.setAlignment(Qt.AlignCenter)
            file_lbl.setFont(create_font(size=9))
            file_lbl.setStyleSheet("color: #6B7280; background: transparent;")
            file_lbl.setWordWrap(True)
            c_layout.addWidget(file_lbl)

        # Date picker
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate())
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setLayoutDirection(Qt.LeftToRight)
        date_edit.setStyleSheet("""
            QDateEdit {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 8px 12px;
                background-color: #F9FAFB;
                font-size: 14px;
                min-height: 20px;
            }
            QDateEdit:focus { border-color: #3B82F6; }
        """)
        c_layout.addWidget(date_edit)

        c_layout.addSpacing(4)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedHeight(34)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        cancel_btn.clicked.connect(dlg.reject)

        confirm_btn = QPushButton(tr("common.confirm"))
        confirm_btn.setFixedHeight(34)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        confirm_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(confirm_btn, 1)
        c_layout.addLayout(btn_row)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        if dlg.exec_() == QDialog.Accepted:
            return date_edit.date().toPyDate().isoformat()
        return None

    def _ask_same_or_separate_dates(self, file_count: int):
        """Ask user: same date for all files or separate? Returns True=same, False=separate, None=cancelled."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor
        from ui.font_utils import create_font, FontManager

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(340)
        result = [None]

        container = QWidget(dlg)
        container.setObjectName("date_ask_container")
        container.setStyleSheet("""
            QWidget#date_ask_container {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(20, 20, 20, 16)
        c_layout.setSpacing(12)

        title = QLabel(tr("wizard.person_dialog.date_question_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #1F2937; background: transparent;")
        c_layout.addWidget(title)

        subtitle = QLabel(tr("wizard.person_dialog.date_question_subtitle", count=file_count))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(create_font(size=9))
        subtitle.setStyleSheet("color: #6B7280; background: transparent;")
        subtitle.setWordWrap(True)
        c_layout.addWidget(subtitle)

        c_layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        same_btn = QPushButton(tr("wizard.person_dialog.same_date"))
        same_btn.setFixedHeight(34)
        same_btn.setCursor(Qt.PointingHandCursor)
        same_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        same_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        same_btn.clicked.connect(lambda: (result.__setitem__(0, True), dlg.accept()))

        sep_btn = QPushButton(tr("wizard.person_dialog.separate_dates"))
        sep_btn.setFixedHeight(34)
        sep_btn.setCursor(Qt.PointingHandCursor)
        sep_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        sep_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        sep_btn.clicked.connect(lambda: (result.__setitem__(0, False), dlg.accept()))

        btn_row.addWidget(same_btn, 1)
        btn_row.addWidget(sep_btn, 1)
        c_layout.addLayout(btn_row)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        if dlg.exec_() == QDialog.Accepted:
            return result[0]
        return None

    # Validation

    def _clamp_ownership_share(self):
        """Clamp ownership share to 0-100 range on focus out."""
        try:
            val = float(self.ownership_share.text() or 0)
            if val > 100:
                self.ownership_share.setText("100")
            elif val < 0:
                self.ownership_share.setText("0")
        except ValueError:
            self.ownership_share.setText("")

    def _validate_mobile(self, value: str) -> bool:
        """Validate mobile number: exactly 8 digits (prefix 09 is fixed in UI)."""
        if not value:
            return True
        digits = ''.join(c for c in value if c.isdigit())
        return len(digits) == 8

    def _validate_landline(self, value: str) -> bool:
        """Validate landline number: exactly 7 digits (area code excluded)."""
        if not value:
            return True
        digits = ''.join(c for c in value if c.isdigit())
        return len(digits) == 7

    def _validate_national_id(self):
        """Validate national ID. Returns True if valid or empty."""
        nid = self.national_id.text().strip()
        if not nid:
            return True
        if len(nid) != 11 or not nid.isdigit():
            return False
        for person in self.existing_persons:
            if person.get('national_id') == nid:
                if self.editing_mode and self.person_data and person.get('person_id') == self.person_data.get('person_id'):
                    continue
                return False
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
        if rel.get('contract_type') is not None:
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
            self.ownership_share.setText(str(rel['ownership_share']))

        if rel.get('evidence_type') is not None:
            idx = self.evidence_type.findData(rel['evidence_type'])
            if idx >= 0:
                self.evidence_type.setCurrentIndex(idx)

        if rel.get('evidence_desc'):
            self.evidence_desc.setText(rel['evidence_desc'])

        if rel.get('notes'):
            self.notes.setPlainText(rel['notes'])

        # Restore document files from context (same wizard session)
        import os
        if data.get('_uploaded_files'):
            self.uploaded_files = [f for f in data['_uploaded_files'] if os.path.exists(f)]
            self._update_upload_thumbnails("id_upload", self.uploaded_files)

        if data.get('_evidence_ids'):
            self._evidence_ids = data['_evidence_ids']

        if data.get('_relation_uploaded_files'):
            self.relation_uploaded_files = [
                f for f in data['_relation_uploaded_files']
                if os.path.exists(f.get("path", ""))
            ]
            file_paths = [f["path"] for f in self.relation_uploaded_files]
            self._update_upload_thumbnails("rel_upload", file_paths)

        if data.get('_relation_id'):
            self._api_relation_id = data['_relation_id']

        # Fetch evidence count from server for logging
        if self._use_api and self._survey_id:
            try:
                evidences = self._api_service.get_survey_evidences(self._survey_id)
                person_id = data.get('person_id')
                id_count = sum(1 for e in evidences
                               if e.get('personId') == person_id
                               and not e.get('personPropertyRelationId'))
                rel_count = sum(1 for e in evidences
                                if e.get('personPropertyRelationId'))
                if id_count > 0 or rel_count > 0:
                    logger.info(f"Server evidences: {id_count} identification + {rel_count} tenure")
                self._server_evidences = evidences
            except Exception as e:
                logger.warning(f"Could not fetch evidences from server: {e}")

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
            'gender': self.gender.currentData(),
            'nationality': self.nationality.currentData(),
            'birth_date': self.birth_date.date().toPyDate().isoformat(),
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
                'start_date': self.start_date.date().toPyDate().isoformat(),
                'ownership_share': float(self.ownership_share.text() or 0),
                'evidence_type': self.evidence_type.currentData() if self.evidence_type.currentIndex() > 0 else None,
                'evidence_desc': self.evidence_desc.text().strip() or None,
                'notes': self.notes.toPlainText().strip() or None,
                'has_documents': self.rb_has_docs.isChecked(),
            },
            # Document files (internal, for same-session persistence)
            '_uploaded_files': list(self.uploaded_files),
            '_evidence_ids': dict(self._evidence_ids),
            '_relation_uploaded_files': [dict(f) for f in self.relation_uploaded_files],
            '_relation_id': self._api_relation_id or (
                self.person_data.get('_relation_id') if self.person_data else None
            ),
        }

    def get_api_person_id(self) -> Optional[str]:
        """Return the API-generated person ID after creation, or None."""
        return self._api_person_id

    def get_api_relation_id(self) -> Optional[str]:
        """Return the API-generated relation ID after linking, or None."""
        return self._api_relation_id

    def _save_person(self):
        """Validate and save person data."""
        if not self.first_name.text().strip():
            Toast.show_toast(self, tr("wizard.person_dialog.enter_first_name"), Toast.WARNING)
            return
        if not self.last_name.text().strip():
            Toast.show_toast(self, tr("wizard.person_dialog.enter_last_name"), Toast.WARNING)
            return
        if self.national_id.text().strip() and not self._validate_national_id():
            Toast.show_toast(self, tr("wizard.person_dialog.nid_invalid"), Toast.WARNING)
            return
        if not self._validate_mobile(self.phone.text().strip()):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_mobile"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(1)
            return
        if not self._validate_landline(self.landline.text().strip()):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_landline"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(1)
            return
        self.accept()

    # API Integration

    def _on_final_save(self):
        """Handle final save (from Tab 3) - create person via API, then link to unit, then accept."""
        import re
        from ui.error_handler import ErrorHandler

        # Validate phone numbers before saving
        if not self._validate_mobile(self.phone.text().strip()):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_mobile"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(1)
            return
        if not self._validate_landline(self.landline.text().strip()):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_landline"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(1)
            return

        # Validate email format before saving
        email_text = self.email.text().strip()
        if email_text and not re.match(r'^[a-zA-Z0-9@._\-+]+$', email_text):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_email_chars"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(1)
            return
        if email_text and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email_text):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_email"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(1)
            return

        # Validate names contain actual letters (not just symbols)
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        name_pattern = re.compile(r'^[\u0600-\u06FFa-zA-Z\s.\-\']{2,}$')
        if first and not name_pattern.match(first):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_first_name"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(0)
            return
        if last and not name_pattern.match(last):
            Toast.show_toast(self, tr("wizard.person_dialog.invalid_last_name"), Toast.WARNING)
            self.tab_widget.setCurrentIndex(0)
            return

        # Validate ownership share range
        ownership_text = self.ownership_share.text().strip()
        if ownership_text:
            try:
                ownership_val = float(ownership_text)
                if ownership_val < 0 or ownership_val > 100:
                    Toast.show_toast(self, tr("wizard.person_dialog.invalid_ownership_share"), Toast.WARNING)
                    self.tab_widget.setCurrentIndex(2)
                    return
            except ValueError:
                pass

        if self._use_api and not self.editing_mode:
            person_data = self.get_person_data()
            logger.info(f"Creating person via API: {person_data.get('first_name')} {person_data.get('last_name')}")

            # Step 1: Create person in household
            try:
                response = self._api_service.create_person_in_household(
                    person_data, self._survey_id, self._household_id
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

                self._api_person_id = person_id

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
            link_success = True
            if self._survey_id and self._unit_id and person_id:
                relation_data = person_data.get('relation_data', {})
                relation_data['person_id'] = person_id
                if not relation_data.get('rel_type'):
                    relation_data['rel_type'] = person_data.get('relationship_type')

                try:
                    relation_response = self._api_service.link_person_to_unit(
                        self._survey_id, self._unit_id, relation_data
                    )

                    logger.info(f"Person {person_id} linked to unit {self._unit_id}")

                    relation_id = (
                        relation_response.get("id") or relation_response.get("relationId") or
                        relation_response.get("Id") or relation_response.get("RelationId") or
                        relation_response.get("personPropertyRelationId") or
                        relation_response.get("PersonPropertyRelationId") or ""
                    )

                    if relation_id:
                        self._api_relation_id = relation_id

                    if relation_id and self.relation_uploaded_files:
                        self._upload_tenure_files(relation_id)

                except Exception as e:
                    link_success = False
                    logger.error(f"Failed to link person to unit: {e}")
                    ErrorHandler.show_error(
                        self, tr("wizard.person_dialog.link_failed", error_msg=map_exception(e)), tr("common.error")
                    )
            else:
                logger.warning(f"Skipping relation link: survey_id={self._survey_id}, unit_id={self._unit_id}, person_id={person_id}")

            if not link_success:
                ErrorHandler.show_warning(
                    self,
                    tr("wizard.person_dialog.link_failed_person_saved"),
                    tr("common.warning")
                )

        # Upload new files added during edit mode
        if self._use_api and self.editing_mode:
            import os
            person_id = self.person_data.get('person_id')

            # Upload NEW identification files only (not already in _evidence_ids)
            new_id_files = [f for f in self.uploaded_files
                            if os.path.normpath(f) not in self._evidence_ids]
            if new_id_files and self._survey_id and person_id:
                saved = self.uploaded_files
                self.uploaded_files = new_id_files
                self._upload_identification_files(person_id)
                self.uploaded_files = saved

            # Upload NEW tenure files only (without evidence_id)
            relation_id = self._api_relation_id
            new_rel_files = [f for f in self.relation_uploaded_files
                             if not f.get("evidence_id")]
            if new_rel_files and self._survey_id and relation_id:
                saved = self.relation_uploaded_files
                self.relation_uploaded_files = new_rel_files
                self._upload_tenure_files(relation_id)
                self.relation_uploaded_files = saved

        self.accept()

    def _upload_identification_files(self, person_id: str):
        """Upload identification files for the created person."""
        import os
        if not self.uploaded_files:
            return

        from services.exceptions import ApiException

        for file_path in self.uploaded_files:
            try:
                response = self._api_service.upload_identification_document(
                    self._survey_id, person_id, file_path
                )
                evidence_id = (
                    response.get("id") or response.get("evidenceId") or
                    response.get("Id") or response.get("EvidenceId") or ""
                )
                if evidence_id:
                    self._evidence_ids[os.path.normpath(file_path)] = evidence_id
                logger.info(f"Identification uploaded: {file_path} (evidence_id={evidence_id})")
            except Exception as e:
                logger.error(f"Failed to upload identification file {file_path}: {e}")

    def _upload_tenure_files(self, relation_id: str):
        """Upload tenure evidence files for the created relation."""
        if not self.relation_uploaded_files:
            return

        from services.error_mapper import map_exception as _map_exc
        from services.exceptions import ApiException

        success_count = 0
        fail_count = 0

        for file_entry in self.relation_uploaded_files:
            file_path = file_entry["path"]
            issue_date = file_entry.get("issue_date", "")
            file_hash = file_entry.get("hash", "")

            try:
                response = self._api_service.upload_relation_document(
                    survey_id=self._survey_id,
                    relation_id=relation_id,
                    file_path=file_path,
                    issue_date=issue_date,
                    file_hash=file_hash
                )
                evidence_id = (
                    response.get("id") or response.get("evidenceId") or
                    response.get("Id") or response.get("EvidenceId") or ""
                )
                if evidence_id:
                    file_entry["evidence_id"] = evidence_id
                success_count += 1
            except ApiException as e:
                if e.status_code == 409:
                    logger.info(f"Document already exists (duplicate hash): {file_path}")
                    success_count += 1
                else:
                    fail_count += 1
                    logger.error(f"Failed to upload {file_path}: {_map_exc(e)}")
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to upload {file_path}: {e}")

        if fail_count > 0:
            logger.warning(f"Document upload: {success_count} succeeded, {fail_count} failed")
            Toast.show_toast(
                self,
                tr("wizard.person_dialog.upload_partial", success=success_count, failed=fail_count),
                Toast.WARNING
            )
        elif success_count > 0:
            logger.info(f"All {success_count} document(s) uploaded successfully")
