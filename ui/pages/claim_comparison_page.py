# -*- coding: utf-8 -*-
"""
Claim Comparison Page — تفاصيل المطالبات
Shows claim details side-by-side for comparison and merge.
Navigated from DuplicatesPage via "عرض" button.
Implements UC-007: Resolve Duplicate Properties
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QScrollArea,
    QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon

from repositories.database import Database
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, Typography
from ui.components.claim_list_card import ClaimListCard
from ui.components.icon import Icon
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

# Mock data for claims (same as duplicates page)
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
        "claim_id": "CL-2025-000002",
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

# Mock data for comparison cards
MOCK_COMPARISON = [
    {
        "building_code": "رمز البناء",
        "building_code_17": "01-0101-001-0001-01",
        "address": "حلب - الحميدية - اسم الناحية - اسم التجمع - اسم الحي",
        "residential_units": "6",
        "commercial_units": "2",
        "total_units": "8",
        "building_type": "سكني",
        "building_status": "سليم",
        "general_description": "مبنى سكني من 4 طوابق في حالة جيدة",
        "location_description": "شارع الحمدانية الرئيسي بالقرب من المسجد",
        "lat": 36.2021,
        "lng": 37.1343,
        "unit_status": "مشغول",
        "unit_type": "شقة سكنية",
        "area_sqm": "120",
        "rooms": "3",
        "floor": "2",
        "unit_number": "12",
        "unit_description": "شقة سكنية بحالة جيدة مع إطلالة",
    },
    {
        "building_code": "رمز البناء",
        "building_code_17": "01-0101-002-0003-02",
        "address": "حلب - الحميدية - اسم الناحية - اسم التجمع - اسم الحي",
        "residential_units": "4",
        "commercial_units": "1",
        "total_units": "5",
        "building_type": "سكني",
        "building_status": "أضرار طفيفة",
        "general_description": "مبنى يحتاج ترميم",
        "location_description": "حي الحميدية الشرقي",
        "lat": 36.2025,
        "lng": 37.1350,
        "unit_status": "شاغر",
        "unit_type": "شقة سكنية",
        "area_sqm": "95",
        "rooms": "2",
        "floor": "1",
        "unit_number": "5",
        "unit_description": "شقة سكنية تحتاج ترميم",
    },
]


class ClaimComparisonPage(QWidget):
    """Claim comparison page — shows two claims side by side for merge."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claim_radio_group = QButtonGroup(self)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        # Outer layout — no margins, scroll area fills the page
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
            + StyleManager.scrollbar()
        )
        self._scroll_area = scroll

        # Scrollable content
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(30)

        # Header: Title + breadcrumb + merge button
        header = self._build_header()
        layout.addLayout(header)

        # Claims card
        claims_card = self._build_claims_section()
        layout.addWidget(claims_card)

        # Comparison section
        comparison = self._build_comparison_section()
        layout.addWidget(comparison)

        layout.addStretch()
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ────────────────────────────────────────────
    # Header
    # ────────────────────────────────────────────
    def _build_header(self) -> QVBoxLayout:
        header = QVBoxLayout()
        header.setSpacing(4)
        header.setContentsMargins(0, 0, 0, 0)

        # Top row: Title + merge button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel("تفاصيل المطالبات")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

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

        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(merge_btn)
        header.addLayout(top_row)

        # Breadcrumb
        breadcrumb = QLabel("التكرارات  •  اختيار السجل الأساسي")
        breadcrumb.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        breadcrumb.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;")
        header.addWidget(breadcrumb)

        return header

    # ────────────────────────────────────────────
    # Claims Section
    # ────────────────────────────────────────────
    def _build_claims_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("claimsCompCard")
        card.setStyleSheet("""
            QFrame#claimsCompCard {
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

            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.claim_radio_group.addButton(radio, idx)
            row.addWidget(radio)

            claim_card = ClaimListCard(claim_data, icon_name="yelow")
            claim_card.setFixedHeight(112)
            row.addWidget(claim_card, 1)

            card_layout.addLayout(row)

        return card

    # ────────────────────────────────────────────
    # Comparison Section
    # ────────────────────────────────────────────
    def _build_comparison_section(self) -> QFrame:
        wrapper = QFrame()
        wrapper.setObjectName("comparisonWrapper")
        wrapper.setStyleSheet("QFrame#comparisonWrapper { background: transparent; border: none; }")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setSpacing(16)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        # Section title
        comp_title = QLabel("المقارنة")
        comp_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        comp_title.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        wrapper_layout.addWidget(comp_title)

        # Two outer cards side by side
        cards_row = QHBoxLayout()
        cards_row.setSpacing(30)

        for data in MOCK_COMPARISON:
            outer_card = self._build_outer_comparison_card(data)
            cards_row.addWidget(outer_card, 1)

        wrapper_layout.addLayout(cards_row)
        return wrapper

    # ────────────────────────────────────────────
    # Outer comparison card (contains 3 inner cards)
    # ────────────────────────────────────────────
    def _build_outer_comparison_card(self, data: dict) -> QFrame:
        outer = QFrame()
        outer.setObjectName("outerCompCard")
        outer.setStyleSheet(f"""
            QFrame#outerCompCard {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        outer.setGraphicsEffect(shadow)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(16)

        # Inner Card 1: Building Info (170h)
        card1 = self._build_building_info_card(data)
        card1.setFixedHeight(170)
        outer_layout.addWidget(card1)

        # Inner Card 2: Building Details — stats + map (614h)
        card2 = self._build_building_details_card(data)
        card2.setFixedHeight(614)
        outer_layout.addWidget(card2)

        # Inner Card 3: Unit Info (527h)
        card3 = self._build_unit_info_card(data)
        card3.setFixedHeight(527)
        outer_layout.addWidget(card3)

        return outer

    # ────────────────────────────────────────────
    # Shared: card frame + shadow
    # ────────────────────────────────────────────
    def _create_inner_card_frame(self) -> QFrame:
        """Create a white inner card with shadow — same style as review step."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        card.setGraphicsEffect(shadow)
        return card

    def _create_card_header(self, icon_name: str, title_text: str, subtitle_text: str) -> QWidget:
        """Create card header: icon (28x28) + title + subtitle — same as review step."""
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Icon container (28x28, white bg, light blue border)
        icon_label = QLabel()
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 7px;
            }
        """)
        icon_pixmap = Icon.load_pixmap(icon_name, size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        # Title + subtitle
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title_label = QLabel(title_text)
        title_label.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        subtitle_label = QLabel(subtitle_text)
        subtitle_label.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_container)
        header_layout.addStretch()

        return header_container

    def _create_field_vertical(self, label_text: str, value_text: str) -> QWidget:
        """Create a vertical field: label on top, value below."""
        field = QWidget()
        field.setStyleSheet("background: transparent; border: none;")
        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)

        value = QLabel(value_text)
        value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        value.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        value.setWordWrap(True)

        field_layout.addWidget(label)
        field_layout.addWidget(value)
        return field

    # ────────────────────────────────────────────
    # Inner Card 1: Building Info (header + code + address pill)
    # ────────────────────────────────────────────
    def _build_building_info_card(self, data: dict) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header
        header = self._create_card_header("blue", "بيانات البناء", "البناء والموقع الجغرافي")
        card_layout.addWidget(header)

        # Building code label
        code_label = QLabel(data.get("building_code", "رمز البناء"))
        code_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        code_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        code_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(code_label)

        # 17-digit building code
        code_17_label = QLabel(data.get("building_code_17", "-"))
        code_17_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        code_17_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        code_17_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(code_17_label)

        # Address pill
        address = data.get("address", "-")
        addr_bar = QFrame()
        addr_bar.setFixedHeight(28)
        addr_bar.setStyleSheet("QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }")

        addr_row = QHBoxLayout(addr_bar)
        addr_row.setContentsMargins(12, 0, 12, 0)
        addr_row.setSpacing(8)

        addr_row.addStretch()

        addr_icon = QLabel()
        addr_icon.setStyleSheet("background: transparent; border: none;")
        addr_icon_pixmap = Icon.load_pixmap("dec", size=16)
        if addr_icon_pixmap and not addr_icon_pixmap.isNull():
            addr_icon.setPixmap(addr_icon_pixmap)
        addr_row.addWidget(addr_icon)

        addr_text = QLabel(address)
        addr_text.setAlignment(Qt.AlignCenter)
        addr_text.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        addr_text.setStyleSheet("color: #0F5B95; background: transparent; border: none;")
        addr_row.addWidget(addr_text)

        addr_row.addStretch()
        card_layout.addWidget(addr_bar)

        return card

    # ────────────────────────────────────────────
    # Inner Card 2: Building Details (stats + map)
    # ────────────────────────────────────────────
    def _build_building_details_card(self, data: dict) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        stat_items = [
            ("عدد المقاسم غير السكنية", data.get("commercial_units", "-")),
            ("عدد المقاسم السكنية", data.get("residential_units", "-")),
            ("العدد الكلي للمقاسم", data.get("total_units", "-")),
            ("نوع البناء", data.get("building_type", "-")),
            ("حالة البناء", data.get("building_status", "-")),
            ("الوصف العام", data.get("general_description", "-")),
            ("وصف الموقع", data.get("location_description", "-")),
        ]

        for label_text, value_text in stat_items:
            field = self._create_field_vertical(label_text, value_text)
            card_layout.addWidget(field)

        # Map section
        map_label = QLabel("موقع البناء")
        map_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        map_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        map_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(map_label)

        # Map placeholder (full width, 130h)
        map_container = QLabel()
        map_container.setFixedHeight(130)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("compMapContainer")
        map_container.setStyleSheet("QLabel#compMapContainer { background-color: #E8E8E8; border-radius: 8px; border: none; }")

        map_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_pixmap or map_pixmap.isNull():
            map_pixmap = Icon.load_pixmap("map-placeholder", size=None)
        if map_pixmap and not map_pixmap.isNull():
            map_container.setPixmap(map_pixmap.scaled(
                562, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            ))
        else:
            loc_fallback = Icon.load_pixmap("carbon_location-filled", size=48)
            if loc_fallback and not loc_fallback.isNull():
                map_container.setPixmap(loc_fallback)

        # "فتح الخريطة" button on top of map
        map_button = QPushButton(map_container)
        map_button.setFixedSize(94, 20)
        map_button.move(8, 8)
        map_button.setCursor(Qt.PointingHandCursor)
        icon_pixmap = Icon.load_pixmap("pill", size=12)
        if icon_pixmap and not icon_pixmap.isNull():
            map_button.setIcon(QIcon(icon_pixmap))
            map_button.setIconSize(QSize(12, 12))
        map_button.setText("فتح الخريطة")
        map_button.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
            }}
        """)
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(8)
        btn_shadow.setXOffset(0)
        btn_shadow.setYOffset(2)
        btn_shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(btn_shadow)

        # Location icon centered on map
        location_icon = QLabel(map_container)
        loc_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if loc_pixmap and not loc_pixmap.isNull():
            location_icon.setPixmap(loc_pixmap)
            location_icon.setFixedSize(56, 56)
            location_icon.move(253, 37)
            location_icon.setStyleSheet("background: transparent;")

        card_layout.addWidget(map_container)
        card_layout.addStretch()

        return card

    # ────────────────────────────────────────────
    # Inner Card 3: Unit Info (header + unit fields)
    # ────────────────────────────────────────────
    def _build_unit_info_card(self, data: dict) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header
        header = self._create_card_header("move", "المقاسم", "معلومات المقسم")
        card_layout.addWidget(header)

        unit_items = [
            ("حالة المقسم", data.get("unit_status", "-")),
            ("نوع المقسم", data.get("unit_type", "-")),
            ("مساحة المقسم", data.get("area_sqm", "-")),
            ("عدد الغرف", data.get("rooms", "-")),
            ("رقم الطابق", data.get("floor", "-")),
            ("رقم المقسم", data.get("unit_number", "-")),
            ("وصف المقسم", data.get("unit_description", "-")),
        ]

        for label_text, value_text in unit_items:
            field = self._create_field_vertical(label_text, value_text)
            card_layout.addWidget(field)

        card_layout.addStretch()
        return card

    # ────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────
    def _on_merge_clicked(self):
        selected_claim = self.claim_radio_group.checkedId()
        logger.info(f"Merge clicked — claim: {selected_claim}")
        Toast.show_toast(self, "سيتم تنفيذ عملية الدمج لاحقاً", Toast.INFO)

    def refresh(self, data=None):
        logger.debug("Refreshing claim comparison page")

    def update_language(self, is_arabic: bool):
        pass
