# -*- coding: utf-8 -*-
"""
Duplicates Page — التكرارات
Displays duplicate units and claims for review and merge.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QRadioButton, QButtonGroup, QAbstractItemView,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from repositories.database import Database
from services.duplicate_service import DuplicateService
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



class DuplicatesPage(QWidget):
    """Duplicates resolution page — matches Figma design."""

    view_comparison_requested = pyqtSignal(object)  # Emits DuplicateGroup

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db) if db else None
        self.unit_radio_group = QButtonGroup(self)
        self.claim_radio_group = QButtonGroup(self)
        self._unit_groups = []
        self._person_groups = []
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(30)

        # ── Header: Title + Merge button ──
        header = self._build_header()
        layout.addLayout(header)

        # ── Units card ──
        units_card = self._build_units_section()
        layout.addWidget(units_card)

        # ── Claims card ──
        claims_card = self._build_claims_section()
        layout.addWidget(claims_card)

        layout.addStretch()

    # ────────────────────────────────────────────
    # Header
    # ────────────────────────────────────────────
    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        # Title — right side
        title = QLabel("التكرارات")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        # Merge button — left side
        merge_btn = QPushButton("دمج")
        merge_btn.setCursor(Qt.PointingHandCursor)
        merge_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        merge_btn.setFixedSize(75, 48)
        merge_btn.setStyleSheet(f"""
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
        """)
        merge_btn.clicked.connect(self._on_merge_clicked)
        self.merge_btn = merge_btn

        header.addWidget(title)
        header.addStretch()
        header.addWidget(merge_btn)

        return header

    # ────────────────────────────────────────────
    # Units Section
    # ────────────────────────────────────────────
    def _build_units_section(self) -> QFrame:
        # ── White card container ──
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

        # Section title + subtitle (red color)
        title_label = QLabel("الوحدات")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        card_layout.addWidget(title_label)

        subtitle = QLabel("اختر الوحدة الصحيحة")
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        # Table
        self.units_table = QTableWidget()
        self.units_table.setColumnCount(8)  # 7 data + 1 radio
        self.units_table.setHorizontalHeaderLabels([
            "",  # radio column
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

        # Header styling
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
            QRadioButton {
                background: transparent;
                border: none;
                spacing: 0px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #C4CDD5;
                background: #f0f7ff;
            }
            QRadioButton::indicator:hover {
                border-color: #3890DF;
            }
            QRadioButton::indicator:checked {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 4px solid #3890DF;
                background: #3890DF;
            }
        """)

        # Load real duplicate data
        self._load_unit_duplicates()

        # Adjust table height
        row_height = 48
        header_height = 40
        row_count = max(self.units_table.rowCount(), 1)
        table_height = header_height + (row_height * row_count) + 4
        self.units_table.setFixedHeight(table_height)
        self.units_table.verticalHeader().setDefaultSectionSize(row_height)

        card_layout.addWidget(self.units_table)
        return card

    def _load_unit_duplicates(self):
        """Load real duplicate unit data from DuplicateService."""
        if not self.duplicate_service:
            self._show_no_duplicates_message(self.units_table)
            return

        try:
            self._unit_groups = self.duplicate_service.detect_unit_duplicates()
            if self._unit_groups:
                records = self._unit_groups[0].records
                self._populate_units_table(records)
            else:
                self._show_no_duplicates_message(self.units_table)
        except Exception as e:
            logger.warning(f"Failed to detect unit duplicates: {e}")
            self._show_no_duplicates_message(self.units_table)

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
        self.units_table.setRowCount(len(units_data))

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

            # Data columns (from real DB records)
            columns = [
                str(unit.get("unit_number", "")),
                unit.get("neighborhood_name_ar", unit.get("area", "")),
                unit.get("unit_type", unit.get("type", "")),
                unit.get("apartment_status", unit.get("status", "")),
                str(unit.get("floor_number", unit.get("floor", ""))),
                str(unit.get("number_of_rooms", unit.get("rooms", ""))),
                f"{unit.get('area_sqm', 0):.0f} (م²)" if unit.get("area_sqm") else "",
            ]
            for col_idx, value in enumerate(columns):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
                self.units_table.setItem(row_idx, col_idx + 1, item)

    # ────────────────────────────────────────────
    # Claims Section (white card container)
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

        # Title row: "المطالبات" (red) + stretch + "عرض" (blue)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("المطالبات")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")

        view_btn = QPushButton("عرض")
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

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(view_btn)
        card_layout.addLayout(title_row)

        # Subtitle
        subtitle = QLabel("اختيار السجل الأساسي")
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        # Load real person duplicates
        self._claims_container = QVBoxLayout()
        self._claims_container.setSpacing(8)
        card_layout.addLayout(self._claims_container)
        self._load_person_duplicates()

        return card

    def _load_person_duplicates(self):
        """Load real person duplicate data."""
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

        if not self.duplicate_service:
            no_dup = QLabel("لا توجد تكرارات في الأشخاص")
            no_dup.setAlignment(Qt.AlignCenter)
            no_dup.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            no_dup.setStyleSheet("color: #27AE60; background: transparent; padding: 20px;")
            self._claims_container.addWidget(no_dup)
            return

        try:
            self._person_groups = self.duplicate_service.detect_person_duplicates()
        except Exception as e:
            logger.warning(f"Failed to detect person duplicates: {e}")
            self._person_groups = []

        if not self._person_groups:
            no_dup = QLabel("لا توجد تكرارات في الأشخاص - جميع السجلات فريدة")
            no_dup.setAlignment(Qt.AlignCenter)
            no_dup.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            no_dup.setStyleSheet("color: #27AE60; background: transparent; padding: 20px;")
            self._claims_container.addWidget(no_dup)
            return

        # Show first duplicate group
        group = self._person_groups[0]
        for idx, person in enumerate(group.records):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(16)
            row_layout.setContentsMargins(0, 0, 0, 0)

            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.claim_radio_group.addButton(radio, idx)
            row_layout.addWidget(radio)

            # Build a claim-like card from person data
            claim_data = {
                "claim_id": person.get("national_id", ""),
                "claimant_name": f"{person.get('first_name_ar', '')} {person.get('last_name_ar', '')}",
                "date": str(person.get("created_at", "")),
                "governorate_name_ar": person.get("nationality", ""),
                "district_name_ar": person.get("gender", ""),
                "subdistrict_name_ar": f"مواليد: {person.get('year_of_birth', '')}",
                "neighborhood_name_ar": person.get("mobile_number", ""),
                "building_id": "",
                "unit_number": "",
            }
            claim_card = ClaimListCard(claim_data, icon_name="yelow")
            claim_card.setFixedHeight(112)
            row_layout.addWidget(claim_card, 1)

            self._claims_container.addLayout(row_layout)

    # ────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────
    def _on_view_comparison_clicked(self):
        """Emit view comparison with the current person duplicate group."""
        if self._person_groups:
            self.view_comparison_requested.emit(self._person_groups[0])
        else:
            Toast.show_toast(self, "لا توجد تكرارات للمقارنة", Toast.WARNING)

    def _on_merge_clicked(self):
        """Handle merge button click."""
        selected_unit = self.unit_radio_group.checkedId()
        selected_claim = self.claim_radio_group.checkedId()
        logger.info(f"Merge clicked - unit: {selected_unit}, claim: {selected_claim}")

        if not self.duplicate_service:
            Toast.show_toast(self, "خدمة كشف التكرارات غير متوفرة", Toast.WARNING)
            return

        merged = False
        if self._unit_groups and selected_unit >= 0:
            group = self._unit_groups[0]
            master_id = group.records[selected_unit].get("unit_id", "")
            if master_id:
                self.duplicate_service.resolve_as_merge(group, master_id, "User selected master")
                merged = True

        if self._person_groups and selected_claim >= 0:
            group = self._person_groups[0]
            master_id = group.records[selected_claim].get("person_id", "")
            if master_id:
                self.duplicate_service.resolve_as_merge(group, master_id, "User selected master")
                merged = True

        if merged:
            Toast.show_toast(self, "تم الدمج بنجاح", Toast.SUCCESS)
            self.refresh()
        else:
            Toast.show_toast(self, "يرجى اختيار السجلات المراد دمجها", Toast.WARNING)

    def refresh(self, data=None):
        """Refresh page data."""
        logger.debug("Refreshing duplicates page")
        self._load_unit_duplicates()
        self._load_person_duplicates()

    def update_language(self, is_arabic: bool):
        """Update UI language — placeholder."""
        pass
