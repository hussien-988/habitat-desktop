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

# ── Mock data (will be replaced with real data binding later) ──
MOCK_UNITS = [
    {
        "unit_number": "12",
        "area": "حلب - الحميدية",
        "type": "سكنية",
        "status": "جيدة",
        "floor": "3",
        "rooms": "1",
        "area_sqm": "120 (م²)",
    },
    {
        "unit_number": "12",
        "area": "حلب - الحميدية",
        "type": "سكنية",
        "status": "جيدة",
        "floor": "3",
        "rooms": "1",
        "area_sqm": "120 (م²)",
    },
]

MOCK_CLAIMS = [
    {
        "claim_id": "CL-2025-000001",
        "claimant_name": "دار عربي الخاص محمود حسن",
        "date": "2024-12-01",
        "governorate_name_ar": "حلب",
        "district_name_ar": "الحميدية",
        "subdistrict_name_ar": "اسم الناحية",
        "neighborhood_name_ar": "اسم التجمع - اسم الحي",
        "building_id": "رقم البناء",
        "unit_number": "رقم المقسم العقارية",
    },
    {
        "claim_id": "CL-2025-000001",
        "claimant_name": "دار عربي الخاص محمود حسن",
        "date": "2024-12-01",
        "governorate_name_ar": "حلب",
        "district_name_ar": "الحميدية",
        "subdistrict_name_ar": "اسم الناحية",
        "neighborhood_name_ar": "اسم التجمع - اسم الحي",
        "building_id": "رقم البناء",
        "unit_number": "رقم المقسم العقارية",
    },
]


class DuplicatesPage(QWidget):
    """Duplicates resolution page — matches Figma design."""

    view_comparison_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_radio_group = QButtonGroup(self)
        self.claim_radio_group = QButtonGroup(self)
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

        # Populate mock data
        self._populate_units_table(MOCK_UNITS)

        # Adjust table height to fit content
        row_height = 48
        header_height = 40
        table_height = header_height + (row_height * len(MOCK_UNITS)) + 4
        self.units_table.setFixedHeight(table_height)
        self.units_table.verticalHeader().setDefaultSectionSize(row_height)

        card_layout.addWidget(self.units_table)
        return card

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

            # Select first row by default
            if row_idx == 0:
                radio.setChecked(True)

            # Data columns
            columns = [
                unit["unit_number"],
                unit["area"],
                unit["type"],
                unit["status"],
                unit["floor"],
                unit["rooms"],
                unit["area_sqm"],
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
        view_btn.clicked.connect(self.view_comparison_requested.emit)

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(view_btn)
        card_layout.addLayout(title_row)

        # Subtitle
        subtitle = QLabel("اختيار السجل الأساسي")
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        # Claim rows: Radio + gap + ClaimListCard
        for idx, claim_data in enumerate(MOCK_CLAIMS):
            row = QHBoxLayout()
            row.setSpacing(16)
            row.setContentsMargins(0, 0, 0, 0)

            # Radio button
            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.claim_radio_group.addButton(radio, idx)
            row.addWidget(radio)

            # ClaimListCard — same design as drafts page
            claim_card = ClaimListCard(claim_data, icon_name="yelow")
            claim_card.setFixedHeight(112)
            row.addWidget(claim_card, 1)

            card_layout.addLayout(row)

        return card

    # ────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────
    def _on_merge_clicked(self):
        """Handle merge button click — placeholder for real logic."""
        selected_unit = self.unit_radio_group.checkedId()
        selected_claim = self.claim_radio_group.checkedId()
        logger.info(f"Merge clicked — unit: {selected_unit}, claim: {selected_claim}")
        Toast.show_toast(self, "سيتم تنفيذ عملية الدمج لاحقاً", Toast.INFO)

    def refresh(self, data=None):
        """Refresh page data — placeholder for real data binding."""
        logger.debug("Refreshing duplicates page")

    def update_language(self, is_arabic: bool):
        """Update UI language — placeholder."""
        pass
