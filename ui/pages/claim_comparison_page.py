# -*- coding: utf-8 -*-
"""
Claim Comparison Page — تفاصيل المطالبات
Shows person records side-by-side for comparison and merge.
Navigated from DuplicatesPage via "عرض المقارنة" button.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates

Data source: REST API via DuplicateService.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QScrollArea,
    QSizePolicy, QGraphicsDropShadowEffect, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon

from repositories.database import Database
from services.duplicate_service import DuplicateService, DuplicateGroup
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions
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


class ClaimComparisonPage(QWidget):
    """Claim comparison page — shows two persons side by side for merge."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db)
        self.claim_radio_group = QButtonGroup(self)
        self._current_group = None
        self._comparison_data = []
        self._user_id = None
        self._setup_ui()

    def set_user_id(self, user_id: str):
        """Set current user ID for audit trail."""
        self._user_id = user_id

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
            + StyleManager.scrollbar()
        )
        self._scroll_area = scroll

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        self._content_layout.setSpacing(20)

        # Header
        header = self._build_header()
        self._content_layout.addLayout(header)

        # Claims card
        self._claims_card = self._build_claims_container()
        self._content_layout.addWidget(self._claims_card)

        # Comparison section
        self._comparison_wrapper = self._build_comparison_container()
        self._content_layout.addWidget(self._comparison_wrapper)

        # Resolution section
        self._resolution_card = self._build_resolution_section()
        self._content_layout.addWidget(self._resolution_card)

        self._content_layout.addStretch()
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ────────────────────────────────────────────
    # Header
    # ────────────────────────────────────────────
    def _build_header(self) -> QVBoxLayout:
        header = QVBoxLayout()
        header.setSpacing(4)
        header.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel("تفاصيل المطالبات")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

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
        """)
        self.action_btn.clicked.connect(self._on_action_clicked)

        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(self.action_btn)
        header.addLayout(top_row)

        # Breadcrumb
        breadcrumb = QLabel("التكرارات  •  اختيار السجل الأساسي")
        breadcrumb.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        breadcrumb.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;")
        header.addWidget(breadcrumb)

        return header

    # ────────────────────────────────────────────
    # Claims Container
    # ────────────────────────────────────────────
    def _build_claims_container(self) -> QFrame:
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

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("الأشخاص")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")

        title_row.addWidget(title_label)
        title_row.addStretch()
        card_layout.addLayout(title_row)

        subtitle = QLabel("اختيار السجل الأساسي")
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        self._claims_rows_layout = QVBoxLayout()
        self._claims_rows_layout.setSpacing(8)
        card_layout.addLayout(self._claims_rows_layout)

        return card

    # ────────────────────────────────────────────
    # Comparison Container
    # ────────────────────────────────────────────
    def _build_comparison_container(self) -> QFrame:
        wrapper = QFrame()
        wrapper.setObjectName("comparisonWrapper")
        wrapper.setStyleSheet("QFrame#comparisonWrapper { background: transparent; border: none; }")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setSpacing(16)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        comp_title = QLabel("المقارنة")
        comp_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        comp_title.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        wrapper_layout.addWidget(comp_title)

        self._comparison_cards_layout = QHBoxLayout()
        self._comparison_cards_layout.setSpacing(30)
        wrapper_layout.addLayout(self._comparison_cards_layout)

        return wrapper

    # ────────────────────────────────────────────
    # Resolution Section
    # ────────────────────────────────────────────
    def _build_resolution_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("resolutionCompCard")
        card.setStyleSheet("""
            QFrame#resolutionCompCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(16, 16, 16, 16)

        title_label = QLabel("إجراء الحل")
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        card_layout.addWidget(title_label)

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
            radio.setStyleSheet(RADIO_STYLE + " QRadioButton { padding: 6px 12px; }")
            radio.setProperty("resolution_type", value)
            self._resolution_group.addButton(radio, idx)
            options_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)
        options_layout.addStretch()
        card_layout.addLayout(options_layout)

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
    # Shared widget builders
    # ────────────────────────────────────────────
    def _create_inner_card_frame(self) -> QFrame:
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
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

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

    def _create_field_vertical(self, label_text: str, value_text: str, is_diff: bool = False) -> QWidget:
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
        value.setWordWrap(True)
        value.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)

        if is_diff:
            value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_BOLD))
            value.setStyleSheet("color: #E74C3C; background: #FFF3CD; border: none; padding: 2px 4px; border-radius: 4px;")
        else:
            value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
            value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        field_layout.addWidget(label)
        field_layout.addWidget(value)
        return field

    # ────────────────────────────────────────────
    # Inner Cards with diff highlighting
    # ────────────────────────────────────────────
    def _build_building_info_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        header = self._create_card_header("blue", "بيانات البناء", "البناء والموقع الجغرافي")
        card_layout.addWidget(header)

        code_label = QLabel(data.get("building_code", "-"))
        code_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        code_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        code_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(code_label)

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

    def _build_building_details_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        stat_items = [
            ("commercial_units", "عدد المقاسم غير السكنية", data.get("commercial_units", "-")),
            ("residential_units", "عدد المقاسم السكنية", data.get("residential_units", "-")),
            ("total_units", "العدد الكلي للمقاسم", data.get("total_units", "-")),
            ("building_type", "نوع البناء", data.get("building_type", "-")),
            ("building_status", "حالة البناء", data.get("building_status", "-")),
            ("general_description", "وصف البناء", data.get("general_description", "-")),
        ]

        for field_key, label_text, value_text in stat_items:
            field = self._create_field_vertical(
                label_text, str(value_text),
                is_diff=(field_key in diff_fields)
            )
            card_layout.addWidget(field)

        # Map placeholder
        map_label = QLabel("موقع البناء")
        map_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        map_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        map_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(map_label)

        map_container = QLabel()
        map_container.setFixedHeight(130)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("compMapContainer")
        map_container.setStyleSheet("QLabel#compMapContainer { background-color: #E8E8E8; border-radius: 8px; border: none; }")

        loc_fallback = Icon.load_pixmap("carbon_location-filled", size=48)
        if loc_fallback and not loc_fallback.isNull():
            map_container.setPixmap(loc_fallback)

        card_layout.addWidget(map_container)
        card_layout.addStretch()
        return card

    def _build_unit_info_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        header = self._create_card_header("move", "المقاسم", "معلومات المقسم")
        card_layout.addWidget(header)

        unit_items = [
            ("unit_status", "حالة المقسم", data.get("unit_status", "-")),
            ("unit_type", "نوع المقسم", data.get("unit_type", "-")),
            ("area_sqm", "مساحة المقسم", data.get("area_sqm", "-")),
            ("rooms", "عدد الغرف", data.get("rooms", "-")),
            ("floor", "رقم الطابق", data.get("floor", "-")),
            ("unit_number", "رقم المقسم", data.get("unit_number", "-")),
        ]

        for field_key, label_text, value_text in unit_items:
            field = self._create_field_vertical(
                label_text, str(value_text),
                is_diff=(field_key in diff_fields)
            )
            card_layout.addWidget(field)

        card_layout.addStretch()
        return card

    def _build_outer_comparison_card(self, data: dict, diff_fields: set) -> QFrame:
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

        card1 = self._build_building_info_card(data, diff_fields)
        card1.setFixedHeight(170)
        outer_layout.addWidget(card1)

        card2 = self._build_building_details_card(data, diff_fields)
        card2.setFixedHeight(614)
        outer_layout.addWidget(card2)

        card3 = self._build_unit_info_card(data, diff_fields)
        card3.setFixedHeight(527)
        outer_layout.addWidget(card3)

        return outer

    # ────────────────────────────────────────────
    # Layout helpers
    # ────────────────────────────────────────────
    def _clear_layout(self, layout):
        """Remove all items from a layout recursively."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _map_to_comparison_dict(self, building: dict, unit: dict) -> dict:
        """Map API records to the format expected by comparison cards."""
        # Handle both camelCase (API) and snake_case (legacy) field names
        address_parts = filter(None, [
            building.get("governorateName", building.get("governorate_name_ar", "")),
            building.get("districtName", building.get("district_name_ar", "")),
            building.get("subDistrictName", building.get("subdistrict_name_ar", "")),
            building.get("address", ""),
        ])

        return {
            "building_code": building.get("buildingId", building.get("building_id", "-")),
            "address": " - ".join(address_parts) or "-",
            "residential_units": str(building.get("residentialUnitsCount", building.get("number_of_apartments", "-"))),
            "commercial_units": str(building.get("commercialUnitsCount", building.get("number_of_shops", "-"))),
            "total_units": str(building.get("totalUnitsCount", building.get("number_of_units", "-"))),
            "building_type": str(building.get("buildingType", building.get("building_type", "-"))),
            "building_status": str(building.get("status", building.get("building_status", "-"))),
            "general_description": building.get("description", building.get("general_description", "-")),
            "lat": building.get("latitude", 0),
            "lng": building.get("longitude", 0),
            "unit_status": str(unit.get("status", unit.get("apartment_status", "-"))),
            "unit_type": str(unit.get("unitType", unit.get("unit_type", "-"))),
            "area_sqm": str(unit.get("areaSquareMeters", unit.get("area_sqm", "-"))),
            "rooms": str(unit.get("numberOfRooms", unit.get("number_of_rooms", "-"))),
            "floor": str(unit.get("floorNumber", unit.get("floor_number", "-"))),
            "unit_number": str(unit.get("unitIdentifier", unit.get("unit_number", "-"))),
        }

    def _compute_comparison_diff_fields(self, comparison_dicts: list) -> set:
        """Find which fields differ across comparison cards."""
        if len(comparison_dicts) < 2:
            return set()
        diff_fields = set()
        all_keys = ["building_code", "address", "residential_units", "commercial_units",
                     "total_units", "building_type", "building_status", "general_description",
                     "unit_status", "unit_type", "area_sqm", "rooms", "floor", "unit_number"]
        for key in all_keys:
            values = {str(d.get(key, "")) for d in comparison_dicts}
            if len(values) > 1:
                diff_fields.add(key)
        return diff_fields

    # ────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────
    def _on_action_clicked(self):
        """Handle resolution action."""
        justification = self._justification_edit.toPlainText().strip()
        if not justification:
            Toast.show_toast(self, "يرجى إدخال مبرر القرار", Toast.WARNING)
            return

        selected_radio = self._resolution_group.checkedButton()
        if not selected_radio:
            return

        resolution_type = selected_radio.property("resolution_type")

        if not self._current_group or not self.duplicate_service:
            Toast.show_toast(self, "لا توجد بيانات للمعالجة", Toast.WARNING)
            return

        success = False

        if resolution_type == "merge":
            selected_idx = self.claim_radio_group.checkedId()
            if selected_idx < 0 or selected_idx >= len(self._current_group.records):
                Toast.show_toast(self, "يرجى اختيار السجل الأساسي", Toast.WARNING)
                return
            master_id = self._current_group.records[selected_idx].get("id", "")
            if not master_id:
                Toast.show_toast(self, "لم يتم العثور على معرف السجل", Toast.WARNING)
                return
            success = self.duplicate_service.resolve_as_merge(
                self._current_group, master_id, justification, self._user_id
            )
        elif resolution_type == "keep_separate":
            success = self.duplicate_service.resolve_as_separate(
                self._current_group, justification, self._user_id
            )
        elif resolution_type == "field_verification":
            success = self.duplicate_service.request_field_verification(
                self._current_group, justification, self._user_id
            )

        if success:
            self._justification_edit.clear()
            Toast.show_toast(self, "تم تنفيذ الإجراء بنجاح", Toast.SUCCESS)
            self.back_requested.emit()
        else:
            Toast.show_toast(self, "فشلت عملية المعالجة", Toast.WARNING)

    # ────────────────────────────────────────────
    # Refresh — populate with real data from API
    # ────────────────────────────────────────────
    def refresh(self, data=None):
        """Refresh page with duplicate group data from API."""
        logger.debug("Refreshing claim comparison page")
        if data is None:
            return

        if not isinstance(data, DuplicateGroup):
            return

        self._current_group = data

        try:
            self._comparison_data = self.duplicate_service.get_person_comparison_data(data)
        except Exception as e:
            logger.error(f"Failed to fetch comparison data: {e}")
            return

        # --- Populate claims section ---
        self._clear_layout(self._claims_rows_layout)

        for btn in self.claim_radio_group.buttons():
            self.claim_radio_group.removeButton(btn)

        for idx, person_data in enumerate(self._comparison_data):
            person = person_data["person"]
            claims = person_data["claims"]
            buildings = person_data["buildings"]
            units = person_data["units"]

            row = QHBoxLayout()
            row.setSpacing(16)
            row.setContentsMargins(0, 0, 0, 0)

            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.claim_radio_group.addButton(radio, idx)
            if idx == 0:
                radio.setChecked(True)
            row.addWidget(radio)

            first_claim = claims[0] if claims else {}
            first_building = buildings[0] if buildings else {}

            name = f"{person.get('firstNameArabic', '')} {person.get('fatherNameArabic', '')} {person.get('familyNameArabic', '')}".strip()

            claim_card_data = {
                "claim_id": first_claim.get("claimNumber", person.get("nationalId", "")),
                "claimant_name": name or "-",
                "date": str(first_claim.get("createdAt", person.get("dateOfBirth", ""))),
                "governorate_name_ar": first_building.get("governorateName", ""),
                "district_name_ar": first_building.get("districtName", ""),
                "subdistrict_name_ar": first_building.get("subDistrictName", ""),
                "neighborhood_name_ar": "",
                "building_id": first_building.get("buildingId", ""),
                "unit_number": "",
            }

            claim_card = ClaimListCard(claim_card_data, icon_name="yelow")
            claim_card.setFixedHeight(112)
            row.addWidget(claim_card, 1)

            self._claims_rows_layout.addLayout(row)

        # --- Populate comparison section ---
        self._clear_layout(self._comparison_cards_layout)

        # Build comparison dicts and compute diffs
        comparison_dicts = []
        for person_data in self._comparison_data:
            building = person_data["buildings"][0] if person_data["buildings"] else {}
            unit = person_data["units"][0] if person_data["units"] else {}
            comparison_dicts.append(self._map_to_comparison_dict(building, unit))

        diff_fields = self._compute_comparison_diff_fields(comparison_dicts)

        for comp_dict in comparison_dicts:
            outer_card = self._build_outer_comparison_card(comp_dict, diff_fields)
            self._comparison_cards_layout.addWidget(outer_card, 1)

    def update_language(self, is_arabic: bool):
        pass
