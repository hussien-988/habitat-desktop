# -*- coding: utf-8 -*-
"""
Duplicates Page — التكرارات
Displays duplicate units and persons for review and merge.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates

Features:
- Queue navigation (next/prev) between duplicate groups
- Field difference highlighting
- Resolution options: merge, keep separate, request field verification
- Required justification notes
- Loading indicator for API fetch
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QRadioButton, QButtonGroup, QAbstractItemView,
    QSizePolicy, QTextEdit, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QColor

from repositories.database import Database
from services.duplicate_service import DuplicateService, DuplicateGroup
from services.display_mappings import get_unit_type_display, get_unit_status_display
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions
from ui.components.claim_list_card import ClaimListCard
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

RADIO_STYLE = f"""
    QRadioButton {{
        background: transparent;
        border: none;
        spacing: 0px;
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 2px solid #C4CDD5;
        background: {Colors.BACKGROUND};
    }}
    QRadioButton::indicator:hover {{
        border-color: {Colors.PRIMARY_BLUE};
    }}
    QRadioButton::indicator:checked {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 4px solid {Colors.PRIMARY_BLUE};
        background: {Colors.PRIMARY_BLUE};
    }}
"""


class _DetectionWorker(QThread):
    """Background worker for duplicate detection (API calls)."""
    finished = Signal(list, list)
    error = Signal(str)

    def __init__(self, service: DuplicateService):
        super().__init__()
        self.service = service

    def run(self):
        try:
            unit_groups = self.service.detect_unit_duplicates()
            person_groups = self.service.detect_person_duplicates()
            self.finished.emit(unit_groups, person_groups)
        except Exception as e:
            self.error.emit(str(e))


class DuplicatesPage(QWidget):
    """Duplicates resolution page with queue navigation and resolution options."""

    view_comparison_requested = pyqtSignal(object)  # Emits DuplicateGroup

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db)
        self.unit_radio_group = QButtonGroup(self)
        self.claim_radio_group = QButtonGroup(self)
        self._unit_groups = []
        self._person_groups = []
        self._current_unit_idx = 0
        self._current_person_idx = 0
        self._worker = None
        self._user_id = None
        self._setup_ui()

    def set_user_id(self, user_id: str):
        """Set current user ID for audit trail."""
        self._user_id = user_id

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(20)

        # Header: Title + action buttons
        header = self._build_header()
        layout.addLayout(header)

        # Loading label (shown during API fetch)
        self._loading_label = QLabel("جاري تحميل البيانات من الخادم...")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #6B7280; background: transparent; padding: 40px;")
        self._loading_label.setVisible(False)
        layout.addWidget(self._loading_label)

        # Units card
        self._units_card = self._build_units_section()
        layout.addWidget(self._units_card)

        # Persons/Claims card
        self._claims_card = self._build_claims_section()
        layout.addWidget(self._claims_card)

        # Resolution section
        self._resolution_card = self._build_resolution_section()
        layout.addWidget(self._resolution_card)

        layout.addStretch()

    # ────────────────────────────────────────────
    # Header
    # ────────────────────────────────────────────
    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("التكرارات")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        # Action button
        self.action_btn = QPushButton("تنفيذ")
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self.action_btn.setFixedSize(90, 48)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #2E7BC8;
            }}
            QPushButton:pressed {{
                background-color: #2568A8;
            }}
            QPushButton:disabled {{
                background-color: #B0BEC5;
            }}
        """)
        self.action_btn.clicked.connect(self._on_action_clicked)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.action_btn)

        return header

    # ────────────────────────────────────────────
    # Units Section with Queue Navigation
    # ────────────────────────────────────────────
    def _build_units_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("unitsCard")
        card.setStyleSheet("""
            QFrame#unitsCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(16, 16, 16, 16)

        # Title row with navigation
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("الوحدات")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")

        # Queue navigation
        self._unit_nav_label = QLabel("")
        self._unit_nav_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._unit_nav_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        nav_btn_style = f"""
            QPushButton {{
                background-color: #F4F6F8;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #E8EDF2; }}
            QPushButton:disabled {{ color: #B0BEC5; background-color: #F4F6F8; }}
        """

        self._unit_prev_btn = QPushButton("السابق")
        self._unit_prev_btn.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        self._unit_prev_btn.setCursor(Qt.PointingHandCursor)
        self._unit_prev_btn.setFixedHeight(28)
        self._unit_prev_btn.setStyleSheet(nav_btn_style)
        self._unit_prev_btn.clicked.connect(lambda: self._navigate_units(-1))

        self._unit_next_btn = QPushButton("التالي")
        self._unit_next_btn.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        self._unit_next_btn.setCursor(Qt.PointingHandCursor)
        self._unit_next_btn.setFixedHeight(28)
        self._unit_next_btn.setStyleSheet(nav_btn_style)
        self._unit_next_btn.clicked.connect(lambda: self._navigate_units(1))

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(self._unit_nav_label)
        title_row.addWidget(self._unit_prev_btn)
        title_row.addWidget(self._unit_next_btn)
        card_layout.addLayout(title_row)

        # Subtitle
        subtitle = QLabel("اختر الوحدة الصحيحة")
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        # Table
        self.units_table = QTableWidget()
        self.units_table.setColumnCount(8)
        self.units_table.setHorizontalHeaderLabels([
            "",
            "رقم المقسم",
            "المنطقة",
            "نوع المقسم",
            "حالة المقسم",
            "رقم الطابق",
            "الغرف",
            "مساحة المقسم",
        ])
        self.units_table.verticalHeader().setVisible(False)
        self.units_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.units_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.units_table.setShowGrid(False)
        self.units_table.setFocusPolicy(Qt.NoFocus)
        self.units_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.units_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = self.units_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.units_table.setColumnWidth(0, 50)

        self.units_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: none;
                outline: none;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #F0F0F0;
                color: #4A5568;
            }
            QHeaderView::section {
                background-color: #F4F6F8;
                color: #6B7280;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 10px 8px;
            }
        """ + RADIO_STYLE)

        card_layout.addWidget(self.units_table)
        return card

    # ────────────────────────────────────────────
    # Claims/Persons Section with Queue Navigation
    # ────────────────────────────────────────────
    def _build_claims_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("claimsCard")
        card.setStyleSheet("""
            QFrame#claimsCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(16, 16, 16, 16)

        # Title row with navigation
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("الأشخاص")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")

        view_btn = QPushButton("عرض المقارنة")
        view_btn.setCursor(Qt.PointingHandCursor)
        view_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        view_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.PRIMARY_BLUE};
                background: transparent;
                border: none;
                padding: 0;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        view_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        view_btn.clicked.connect(self._on_view_comparison_clicked)

        # Person queue nav
        self._person_nav_label = QLabel("")
        self._person_nav_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._person_nav_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        nav_btn_style = f"""
            QPushButton {{
                background-color: #F4F6F8;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #E8EDF2; }}
            QPushButton:disabled {{ color: #B0BEC5; background-color: #F4F6F8; }}
        """

        self._person_prev_btn = QPushButton("السابق")
        self._person_prev_btn.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        self._person_prev_btn.setCursor(Qt.PointingHandCursor)
        self._person_prev_btn.setFixedHeight(28)
        self._person_prev_btn.setStyleSheet(nav_btn_style)
        self._person_prev_btn.clicked.connect(lambda: self._navigate_persons(-1))

        self._person_next_btn = QPushButton("التالي")
        self._person_next_btn.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        self._person_next_btn.setCursor(Qt.PointingHandCursor)
        self._person_next_btn.setFixedHeight(28)
        self._person_next_btn.setStyleSheet(nav_btn_style)
        self._person_next_btn.clicked.connect(lambda: self._navigate_persons(1))

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(self._person_nav_label)
        title_row.addWidget(self._person_prev_btn)
        title_row.addWidget(self._person_next_btn)
        title_row.addWidget(view_btn)
        card_layout.addLayout(title_row)

        # Subtitle
        subtitle = QLabel("اختيار السجل الأساسي")
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        # Rows container
        self._claims_container = QVBoxLayout()
        self._claims_container.setSpacing(8)
        card_layout.addLayout(self._claims_container)

        return card

    # ────────────────────────────────────────────
    # Resolution Section
    # ────────────────────────────────────────────
    def _build_resolution_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("resolutionCard")
        card.setStyleSheet("""
            QFrame#resolutionCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title_label = QLabel("إجراء الحل")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        card_layout.addWidget(title_label)

        # Resolution options as radio buttons
        self._resolution_group = QButtonGroup(self)

        resolution_options = [
            ("دمج السجلات", "merge"),
            ("إبقاء منفصل", "keep_separate"),
            ("طلب تحقق ميداني", "field_verification"),
        ]

        options_layout = QHBoxLayout()
        options_layout.setSpacing(24)

        for idx, (label, value) in enumerate(resolution_options):
            radio = QRadioButton(label)
            radio.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            radio.setStyleSheet(RADIO_STYLE + """
                QRadioButton { padding: 6px 12px; }
            """)
            radio.setProperty("resolution_type", value)
            self._resolution_group.addButton(radio, idx)
            options_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

        options_layout.addStretch()
        card_layout.addLayout(options_layout)

        # Justification text area
        just_label = QLabel("مبرر القرار (مطلوب)")
        just_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        just_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        card_layout.addWidget(just_label)

        self._justification_edit = QTextEdit()
        self._justification_edit.setPlaceholderText("أدخل سبب قرار الحل...")
        self._justification_edit.setFixedHeight(80)
        self._justification_edit.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._justification_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px;
                background: #FAFBFC;
                color: #333;
            }}
            QTextEdit:focus {{
                border-color: {Colors.PRIMARY_BLUE};
            }}
        """)
        card_layout.addWidget(self._justification_edit)

        return card

    # ────────────────────────────────────────────
    # Queue Navigation
    # ────────────────────────────────────────────
    def _navigate_units(self, direction: int):
        """Navigate to next/prev unit duplicate group."""
        if not self._unit_groups:
            return
        new_idx = self._current_unit_idx + direction
        if 0 <= new_idx < len(self._unit_groups):
            self._current_unit_idx = new_idx
            self._display_unit_group()

    def _navigate_persons(self, direction: int):
        """Navigate to next/prev person duplicate group."""
        if not self._person_groups:
            return
        new_idx = self._current_person_idx + direction
        if 0 <= new_idx < len(self._person_groups):
            self._current_person_idx = new_idx
            self._display_person_group()

    def _update_unit_nav(self):
        """Update unit navigation controls."""
        total = len(self._unit_groups)
        if total == 0:
            self._unit_nav_label.setText("")
            self._unit_prev_btn.setEnabled(False)
            self._unit_next_btn.setEnabled(False)
            return
        current = self._current_unit_idx + 1
        self._unit_nav_label.setText(f"{current} من {total}")
        self._unit_prev_btn.setEnabled(self._current_unit_idx > 0)
        self._unit_next_btn.setEnabled(self._current_unit_idx < total - 1)

    def _update_person_nav(self):
        """Update person navigation controls."""
        total = len(self._person_groups)
        if total == 0:
            self._person_nav_label.setText("")
            self._person_prev_btn.setEnabled(False)
            self._person_next_btn.setEnabled(False)
            return
        current = self._current_person_idx + 1
        self._person_nav_label.setText(f"{current} من {total}")
        self._person_prev_btn.setEnabled(self._current_person_idx > 0)
        self._person_next_btn.setEnabled(self._current_person_idx < total - 1)

    # ────────────────────────────────────────────
    # Data Loading
    # ────────────────────────────────────────────
    def _start_detection(self):
        """Start duplicate detection in background thread."""
        if self._worker and self._worker.isRunning():
            return

        self._loading_label.setVisible(True)
        self._units_card.setVisible(False)
        self._claims_card.setVisible(False)
        self._resolution_card.setVisible(False)

        self._worker = _DetectionWorker(self.duplicate_service)
        self._worker.finished.connect(self._on_detection_finished)
        self._worker.error.connect(self._on_detection_error)
        self._worker.start()

    def _on_detection_finished(self, unit_groups, person_groups):
        """Handle detection results."""
        self._loading_label.setVisible(False)
        self._units_card.setVisible(True)
        self._claims_card.setVisible(True)
        self._resolution_card.setVisible(True)

        self._unit_groups = unit_groups
        self._person_groups = person_groups
        self._current_unit_idx = 0
        self._current_person_idx = 0

        self._display_unit_group()
        self._display_person_group()

    def _on_detection_error(self, error_msg):
        """Handle detection error."""
        self._loading_label.setText(f"فشل تحميل البيانات: {error_msg}")
        logger.error(f"Duplicate detection error: {error_msg}")

    def _display_unit_group(self):
        """Display the current unit duplicate group in the table."""
        # Clear radio buttons
        for btn in self.unit_radio_group.buttons():
            self.unit_radio_group.removeButton(btn)

        self._update_unit_nav()

        if not self._unit_groups:
            self._show_no_duplicates_message(self.units_table)
            self._adjust_table_height()
            return

        group = self._unit_groups[self._current_unit_idx]
        records = group.records
        self._populate_units_table(records)
        self._adjust_table_height()

    def _display_person_group(self):
        """Display the current person duplicate group as claim cards."""
        # Clear existing
        while self._claims_container.count():
            item = self._claims_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

        # Clear radio buttons
        for btn in self.claim_radio_group.buttons():
            self.claim_radio_group.removeButton(btn)

        self._update_person_nav()

        if not self._person_groups:
            no_dup = QLabel("لا توجد تكرارات في الأشخاص - جميع السجلات فريدة")
            no_dup.setAlignment(Qt.AlignCenter)
            no_dup.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            no_dup.setStyleSheet("color: #27AE60; background: transparent; padding: 20px;")
            self._claims_container.addWidget(no_dup)
            return

        group = self._person_groups[self._current_person_idx]
        # Collect field values to detect differences
        field_keys = ["nationalId", "firstNameArabic", "fatherNameArabic",
                      "familyNameArabic", "motherNameArabic", "gender", "dateOfBirth"]
        diff_fields = self._find_differing_fields(group.records, field_keys)

        for idx, person in enumerate(group.records):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(16)
            row_layout.setContentsMargins(0, 0, 0, 0)

            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.claim_radio_group.addButton(radio, idx)
            if idx == 0:
                radio.setChecked(True)
            row_layout.addWidget(radio)

            # Build person info card
            name = f"{person.get('firstNameArabic', '')} {person.get('fatherNameArabic', '')} {person.get('familyNameArabic', '')}".strip()
            claim_data = {
                "claim_id": person.get("nationalId", ""),
                "claimant_name": name or "-",
                "date": str(person.get("dateOfBirth", "")),
                "governorate_name_ar": person.get("motherNameArabic", ""),
                "district_name_ar": person.get("gender", ""),
                "subdistrict_name_ar": f"مواليد: {person.get('dateOfBirth', '')}",
                "neighborhood_name_ar": "",
                "building_id": "",
                "unit_number": "",
            }
            claim_card = ClaimListCard(claim_data, icon_name="yelow")
            claim_card.setFixedHeight(112)

            # Highlight if person has differing fields
            if diff_fields:
                claim_card.setStyleSheet(claim_card.styleSheet() + """
                    QFrame { border-left: 3px solid #F39C12; }
                """)

            row_layout.addWidget(claim_card, 1)
            self._claims_container.addLayout(row_layout)

    def _show_no_duplicates_message(self, table):
        """Show a 'no duplicates found' message in a table."""
        table.setRowCount(1)
        table.setSpan(0, 0, 1, table.columnCount())
        msg = QTableWidgetItem("لا توجد تكرارات - جميع السجلات فريدة")
        msg.setTextAlignment(Qt.AlignCenter)
        msg.setForeground(QColor("#27AE60"))
        msg.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        table.setItem(0, 0, msg)

    def _populate_units_table(self, units_data):
        """Populate units table with field difference highlighting."""
        self.units_table.setRowCount(len(units_data))

        # Detect which fields differ
        field_keys = ["unitIdentifier", "buildingId", "unitType", "status",
                      "floorNumber", "numberOfRooms", "areaSquareMeters"]
        diff_fields = self._find_differing_fields(units_data, field_keys)

        for row_idx, unit in enumerate(units_data):
            # Radio button in column 0
            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.unit_radio_group.addButton(radio, row_idx)

            radio_container = QWidget()
            radio_container.setStyleSheet("background: transparent; border: none;")
            radio_layout = QHBoxLayout(radio_container)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            radio_layout.setAlignment(Qt.AlignCenter)
            radio_layout.addWidget(radio)
            self.units_table.setCellWidget(row_idx, 0, radio_container)

            if row_idx == 0:
                radio.setChecked(True)

            # Data columns mapped from API camelCase fields
            col_mapping = [
                ("unitIdentifier", str(unit.get("unitIdentifier", ""))),
                ("buildingId", unit.get("buildingId", "")),
                ("unitType", get_unit_type_display(unit.get("unitType", unit.get("type", "")))),
                ("status", get_unit_status_display(unit.get("status", ""))),
                ("floorNumber", str(unit.get("floorNumber", ""))),
                ("numberOfRooms", str(unit.get("numberOfRooms", ""))),
                ("areaSquareMeters", f"{unit.get('areaSquareMeters', 0):.0f} (م²)" if unit.get("areaSquareMeters") else ""),
            ]

            for col_idx, (field_key, value) in enumerate(col_mapping):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))

                # Highlight fields that differ between records
                if field_key in diff_fields:
                    item.setBackground(QColor("#FFF3CD"))
                    item.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))

                self.units_table.setItem(row_idx, col_idx + 1, item)

    def _adjust_table_height(self):
        """Adjust table height based on row count."""
        row_height = 48
        header_height = 40
        row_count = max(self.units_table.rowCount(), 1)
        table_height = header_height + (row_height * row_count) + 4
        self.units_table.setFixedHeight(table_height)
        self.units_table.verticalHeader().setDefaultSectionSize(row_height)

    @staticmethod
    def _find_differing_fields(records: list, field_keys: list) -> set:
        """Find which fields have different values across records."""
        if len(records) < 2:
            return set()

        diff_fields = set()
        for key in field_keys:
            values = {str(r.get(key, "")) for r in records}
            if len(values) > 1:
                diff_fields.add(key)
        return diff_fields

    # ────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────
    def _on_view_comparison_clicked(self):
        """Emit view comparison with the current person duplicate group."""
        if self._person_groups and self._current_person_idx < len(self._person_groups):
            self.view_comparison_requested.emit(self._person_groups[self._current_person_idx])
        else:
            Toast.show_toast(self, "لا توجد تكرارات للمقارنة", Toast.WARNING)

    def _on_action_clicked(self):
        """Handle resolution action based on selected option."""
        justification = self._justification_edit.toPlainText().strip()
        if not justification:
            Toast.show_toast(self, "يرجى إدخال مبرر القرار", Toast.WARNING)
            return

        # Get resolution type
        selected_radio = self._resolution_group.checkedButton()
        if not selected_radio:
            Toast.show_toast(self, "يرجى اختيار نوع الإجراء", Toast.WARNING)
            return

        resolution_type = selected_radio.property("resolution_type")

        success = False

        if resolution_type == "merge":
            success = self._execute_merge(justification)
        elif resolution_type == "keep_separate":
            success = self._execute_keep_separate(justification)
        elif resolution_type == "field_verification":
            success = self._execute_field_verification(justification)

        if success:
            self._justification_edit.clear()
            Toast.show_toast(self, "تم تنفيذ الإجراء بنجاح", Toast.SUCCESS)

    def _execute_merge(self, justification: str) -> bool:
        """Execute merge for both unit and person selections."""
        merged = False

        # Merge unit group
        if self._unit_groups and self._current_unit_idx < len(self._unit_groups):
            selected_unit = self.unit_radio_group.checkedId()
            if selected_unit >= 0:
                group = self._unit_groups[self._current_unit_idx]
                master_id = group.records[selected_unit].get("id", "")
                if master_id:
                    if self.duplicate_service.resolve_as_merge(group, master_id, justification, self._user_id):
                        self._unit_groups.pop(self._current_unit_idx)
                        if self._current_unit_idx >= len(self._unit_groups):
                            self._current_unit_idx = max(0, len(self._unit_groups) - 1)
                        self._display_unit_group()
                        merged = True

        # Merge person group
        if self._person_groups and self._current_person_idx < len(self._person_groups):
            selected_claim = self.claim_radio_group.checkedId()
            if selected_claim >= 0:
                group = self._person_groups[self._current_person_idx]
                master_id = group.records[selected_claim].get("id", "")
                if master_id:
                    if self.duplicate_service.resolve_as_merge(group, master_id, justification, self._user_id):
                        self._person_groups.pop(self._current_person_idx)
                        if self._current_person_idx >= len(self._person_groups):
                            self._current_person_idx = max(0, len(self._person_groups) - 1)
                        self._display_person_group()
                        merged = True

        if not merged:
            Toast.show_toast(self, "يرجى اختيار السجلات المراد دمجها", Toast.WARNING)

        return merged

    def _execute_keep_separate(self, justification: str) -> bool:
        """Mark current groups as intentionally separate."""
        success = False

        if self._unit_groups and self._current_unit_idx < len(self._unit_groups):
            group = self._unit_groups[self._current_unit_idx]
            if self.duplicate_service.resolve_as_separate(group, justification, self._user_id):
                self._unit_groups.pop(self._current_unit_idx)
                if self._current_unit_idx >= len(self._unit_groups):
                    self._current_unit_idx = max(0, len(self._unit_groups) - 1)
                self._display_unit_group()
                success = True

        if self._person_groups and self._current_person_idx < len(self._person_groups):
            group = self._person_groups[self._current_person_idx]
            if self.duplicate_service.resolve_as_separate(group, justification, self._user_id):
                self._person_groups.pop(self._current_person_idx)
                if self._current_person_idx >= len(self._person_groups):
                    self._current_person_idx = max(0, len(self._person_groups) - 1)
                self._display_person_group()
                success = True

        return success

    def _execute_field_verification(self, justification: str) -> bool:
        """Request field verification for current groups."""
        success = False

        if self._unit_groups and self._current_unit_idx < len(self._unit_groups):
            group = self._unit_groups[self._current_unit_idx]
            if self.duplicate_service.request_field_verification(group, justification, self._user_id):
                self._unit_groups.pop(self._current_unit_idx)
                if self._current_unit_idx >= len(self._unit_groups):
                    self._current_unit_idx = max(0, len(self._unit_groups) - 1)
                self._display_unit_group()
                success = True

        if self._person_groups and self._current_person_idx < len(self._person_groups):
            group = self._person_groups[self._current_person_idx]
            if self.duplicate_service.request_field_verification(group, justification, self._user_id):
                self._person_groups.pop(self._current_person_idx)
                if self._current_person_idx >= len(self._person_groups):
                    self._current_person_idx = max(0, len(self._person_groups) - 1)
                self._display_person_group()
                success = True

        return success

    def refresh(self, data=None):
        """Refresh page data by starting detection."""
        logger.debug("Refreshing duplicates page")
        self._start_detection()

    def update_language(self, is_arabic: bool):
        """Update UI language — placeholder."""
        pass
