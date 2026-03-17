# -*- coding: utf-8 -*-
"""
Claim Details Page — displays claim details from Claims API.

Sections:
  1. Claim header (number, type, status, source, date) — badges
  2. Claimant info (person data — read-only)
  3. Property unit (building + unit — read-only)
  4. Relation type & evidence (editable for open claims)
  5. Claim status summary

Data source: ClaimController.get_claim_full_detail()
"""

from utils.logger import get_logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea,
    QSpacerItem, QSizePolicy, QGridLayout,
    QGraphicsDropShadowEffect, QComboBox, QFileDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.toast import Toast
from services.translation_manager import tr
from services.display_mappings import (
    get_unit_type_display, get_unit_status_display,
    get_claim_type_display, get_source_display, get_claim_status_display,
)

logger = get_logger(__name__)

# Case status labels (not in vocab — hardcoded)
_CASE_STATUS_LABELS = {
    1: "مفتوحة",
    2: "مغلقة",
}

# Gender labels
_GENDER_LABELS = {
    1: "ذكر",
    2: "أنثى",
    0: "غير محدد",
}


class ClaimDetailsPage(QWidget):
    """Claim details page with 4 sections from Claims API."""

    back_requested = pyqtSignal()
    edit_requested = pyqtSignal(str)  # claim_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._claim_data = {}
        self._person_data = {}
        self._unit_data = {}
        self._building_data = {}
        self._survey_id = None
        self._evidences = []
        self._claim_id = None
        # Edit mode state
        self._is_editing = False
        self._original_claim_type = None
        self._relation_id = None
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []  # evidence dicts to link (existing docs)
        self._claim_type_combo = None
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(StyleManager.page_background())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        main_layout.setSpacing(16)

        # Header
        main_layout.addWidget(self._create_header())

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 40)
        self._scroll_layout.setSpacing(20)

        # Section 1: Claim header card
        self._header_card, self._header_content = self._create_simple_card()
        self._scroll_layout.addWidget(self._header_card)

        # Section 2: Claimant info
        self._person_card, self._person_content = self._create_card_base(
            "blue", "بيانات المُطالِب", "المعلومات الشخصية لمقدم المطالبة"
        )
        self._scroll_layout.addWidget(self._person_card)

        # Section 3: Property unit
        self._property_card, self._property_content = self._create_card_base(
            "blue", "الوحدة العقارية", "بيانات المبنى والوحدة المُطالَب بها"
        )
        self._scroll_layout.addWidget(self._property_card)

        # Section 4: Relation & Evidence
        self._relation_card, self._relation_content = self._create_card_base(
            "blue", "نوع المطالبة والمستندات", "نوع العلاقة والأدلة المرفقة"
        )
        self._scroll_layout.addWidget(self._relation_card)

        # Section 5: Claim status summary
        self._status_card, self._status_content = self._create_simple_card()
        self._scroll_layout.addWidget(self._status_card)

        self._scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    # =========================================================================
    # Header
    # =========================================================================

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Title + breadcrumb
        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        self._title_label = QLabel("تفاصيل المطالبة")
        self._title_label.setFont(create_font(
            size=FontManager.SIZE_TITLE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self._title_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )

        self._breadcrumb_label = QLabel("المطالبات  ·  تفاصيل المطالبة")
        self._breadcrumb_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self._breadcrumb_label.setStyleSheet(
            f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;"
        )

        text_box.addWidget(self._title_label)
        text_box.addWidget(self._breadcrumb_label)
        layout.addLayout(text_box)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Cancel edit button (hidden by default, shown during editing)
        self._cancel_edit_btn = QPushButton("إلغاء")
        self._cancel_edit_btn.setFixedSize(80, 40)
        self._cancel_edit_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_edit_btn.setVisible(False)
        self._cancel_edit_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #475569;
                border: 1px solid #E2E8F0; border-radius: 8px;
                font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background-color: #F1F5F9; }
        """)
        self._cancel_edit_btn.clicked.connect(self._on_cancel_edit)
        layout.addWidget(self._cancel_edit_btn)

        # Edit/Save button (visible for open claims + admin/data_manager)
        self._edit_btn = QPushButton("تعديل المطالبة")
        self._edit_btn.setFixedSize(160, 40)
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.setVisible(False)
        self._edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #2A7BC8; }}
        """)
        self._edit_btn.clicked.connect(self._on_edit_or_save_clicked)
        layout.addWidget(self._edit_btn)

        # Back button
        back_btn = QPushButton("✕")
        back_btn.setFixedSize(36, 36)
        back_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #E2E8F0; color: #475569; font-size: 16px;
                font-weight: 600; background: white; border-radius: 8px;
            }
            QPushButton:hover { color: #1e293b; background-color: #F1F5F9; }
        """)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_btn)

        return header

    # =========================================================================
    # Card builders (same pattern as BuildingDetailsPage)
    # =========================================================================

    def _create_card_base(self, icon_name, title, subtitle):
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.SURFACE}; border: none; border-radius: 12px; }}
        """)
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header row
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel { background-color: #ffffff; border: 1px solid #DBEAFE; border-radius: 7px; }
        """)
        icon_pixmap = Icon.load_pixmap(icon_name, size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        title_layout.addWidget(title_lbl)
        title_layout.addWidget(subtitle_lbl)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_container)
        header_layout.addStretch()

        card_layout.addWidget(header)

        # Content
        content_widget = QWidget()
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)
        return card, content_layout

    def _create_simple_card(self):
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{ background-color: {Colors.SURFACE}; border: none; border-radius: 12px; }}
        """)
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        content_widget = QWidget()
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)
        return card, content_layout

    @staticmethod
    def _add_shadow(widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        widget.setGraphicsEffect(shadow)

    # =========================================================================
    # Field helpers
    # =========================================================================

    def _create_field_pair(self, label_text, value_text):
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        lbl.setAlignment(Qt.AlignCenter)

        val = QLabel(str(value_text) if value_text else "-")
        val.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        val.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        val.setAlignment(Qt.AlignCenter)
        val.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addWidget(val)
        return container

    def _create_badge(self, text, bg_color, text_color):
        badge = QLabel(str(text))
        badge.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(26)
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 13px;
                padding: 2px 14px;
            }}
        """)
        return badge

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # =========================================================================
    # Data loading
    # =========================================================================

    def refresh(self, data=None):
        """Load claim data from ClaimController.get_claim_full_detail() result."""
        if data is None:
            return

        self._claim_data = data.get("claim") or {}
        self._person_data = data.get("person") or {}
        self._unit_data = data.get("unit") or {}
        self._building_data = data.get("building") or {}
        self._survey_id = data.get("survey_id")
        self._evidences = data.get("evidences") or []
        self._claim_id = self._claim_data.get("id") or self._claim_data.get("claimId", "")

        self._populate_header_card()
        self._populate_person_card()
        self._populate_property_card()
        self._populate_relation_card()
        self._populate_status_card()
        self._update_edit_visibility()

        logger.info(f"Claim details loaded: {self._claim_data.get('claimNumber', 'N/A')}")

    # =========================================================================
    # Populate sections
    # =========================================================================

    def _populate_header_card(self):
        self._clear_layout(self._header_content)

        claim = self._claim_data
        claim_number = str(claim.get("claimNumber", "N/A"))
        claim_type = get_claim_type_display(claim.get("claimType", ""))
        case_status = claim.get("caseStatus") or claim.get("status", 1)
        status_label = _CASE_STATUS_LABELS.get(case_status, "غير محدد")
        source = get_source_display(claim.get("claimSource", 0))
        date_str = (str(claim.get("createdAtUtc") or ""))[:10]

        # Claim number
        num_label = QLabel(claim_number)
        num_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        num_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        num_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        self._header_content.addWidget(num_label)

        # Badges row
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        badges_row.setContentsMargins(0, 0, 0, 0)

        # Type badge
        badges_row.addWidget(self._create_badge(claim_type, "#EFF6FF", "#1E40AF"))

        # Status badge
        if case_status == 2:
            badges_row.addWidget(self._create_badge(status_label, "#F0FDF4", "#15803D"))
        else:
            badges_row.addWidget(self._create_badge(status_label, "#FFF7ED", "#C2410C"))

        # Source badge
        badges_row.addWidget(self._create_badge(source, "#F5F3FF", "#5B21B6"))

        # Date
        if date_str and not date_str.startswith("0001"):
            date_label = QLabel(date_str)
            date_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR))
            date_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            badges_row.addWidget(date_label)

        badges_row.addStretch()

        badges_widget = QWidget()
        badges_widget.setStyleSheet("background: transparent; border: none;")
        badges_widget.setLayout(badges_row)
        self._header_content.addWidget(badges_widget)

    def _populate_person_card(self):
        self._clear_layout(self._person_content)

        person = self._person_data
        if not person:
            name = self._claim_data.get("primaryClaimantName") or self._claim_data.get("fullNameArabic", "-")
            no_lbl = QLabel(f"المُطالِب: {name}")
            no_lbl.setFont(create_font(size=FontManager.SIZE_BODY))
            no_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            self._person_content.addWidget(no_lbl)
            return

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        for c in range(4):
            grid.setColumnStretch(c, 1)

        gender_raw = person.get("gender", 0)
        gender_label = _GENDER_LABELS.get(gender_raw, str(gender_raw) if gender_raw else "-")
        dob = person.get("dateOfBirth")
        dob_display = str(dob)[:10] if dob and not str(dob).startswith("0001") else "-"

        fields = [
            ("الاسم", person.get("firstNameArabic", "-")),
            ("اسم الأب", person.get("fatherNameArabic", "-")),
            ("العائلة", person.get("familyNameArabic", "-")),
            ("اسم الأم", person.get("motherNameArabic", "-")),
            ("الرقم الوطني", str(person.get("nationalId", "-"))),
            ("الجنس", gender_label),
            ("تاريخ الميلاد", dob_display),
        ]

        for i, (label, value) in enumerate(fields):
            row = i // 4
            col = i % 4
            grid.addWidget(self._create_field_pair(label, value), row, col)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent; border: none;")
        grid_widget.setLayout(grid)
        self._person_content.addWidget(grid_widget)

    def _populate_property_card(self):
        self._clear_layout(self._property_content)

        building = self._building_data
        unit = self._unit_data

        if not building and not unit:
            building_code = str(self._claim_data.get("buildingCode") or "-")
            no_lbl = QLabel(f"رقم البناء: {building_code}")
            no_lbl.setFont(create_font(size=FontManager.SIZE_BODY))
            no_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            self._property_content.addWidget(no_lbl)
            return

        # Address bar
        gov = building.get("governorateNameArabic", "")
        dist = building.get("districtNameArabic", "")
        sub = building.get("subDistrictNameArabic", "")
        neigh = building.get("neighborhoodNameArabic", "")
        address_parts = [p for p in [gov, dist, sub, neigh] if p]
        address = " > ".join(address_parts) if address_parts else "-"

        addr_bar = QFrame()
        addr_bar.setLayoutDirection(Qt.RightToLeft)
        addr_bar.setFixedHeight(28)
        addr_bar.setStyleSheet("QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }")
        addr_layout = QHBoxLayout(addr_bar)
        addr_layout.setContentsMargins(12, 0, 12, 0)
        addr_lbl = QLabel(address)
        addr_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        addr_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        addr_layout.addWidget(addr_lbl)
        addr_layout.addStretch()
        self._property_content.addWidget(addr_bar)

        # Building & unit fields
        building_code = str(building.get("buildingCode") or building.get("buildingNumber") or "-")
        unit_number = str(unit.get("unitIdentifier") or unit.get("unitNumber") or "-")
        floor_raw = unit.get("floorNumber")
        floor = str(floor_raw) if floor_raw is not None else "-"
        unit_type_raw = unit.get("unitType", 0)
        unit_type = get_unit_type_display(unit_type_raw) if unit_type_raw else "-"
        area = unit.get("areaSquareMeters") or unit.get("areaSqm", 0)
        area_display = f"{area:.2f} م²" if area else "-"
        rooms_raw = unit.get("numberOfRooms")
        rooms = str(rooms_raw) if rooms_raw is not None else "-"
        unit_status_raw = unit.get("status") or unit.get("unitStatus", 0)
        unit_status = get_unit_status_display(unit_status_raw) if unit_status_raw else "-"

        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setContentsMargins(0, 4, 0, 0)
        for c in range(4):
            grid.setColumnStretch(c, 1)

        props = [
            ("رقم البناء", building_code),
            ("رقم الوحدة", unit_number),
            ("رقم الطابق", floor),
            ("نوع الوحدة", unit_type),
            ("المساحة", area_display),
            ("عدد الغرف", rooms),
            ("حالة الوحدة", unit_status),
        ]

        for i, (label, value) in enumerate(props):
            row = i // 4
            col = i % 4
            grid.addWidget(self._create_field_pair(label, value), row, col)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent; border: none;")
        grid_widget.setLayout(grid)
        self._property_content.addWidget(grid_widget)

    def _populate_relation_card(self):
        self._clear_layout(self._relation_content)

        claim = self._claim_data
        current_type = claim.get("claimType", "")

        # Claim type row
        type_row = QHBoxLayout()
        type_row.setContentsMargins(0, 0, 0, 0)
        type_row.setSpacing(8)

        type_label = QLabel("نوع المطالبة:")
        type_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        type_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        type_row.addWidget(type_label)

        if self._is_editing:
            self._claim_type_combo = QComboBox()
            self._claim_type_combo.setFixedHeight(36)
            self._claim_type_combo.setMinimumWidth(160)
            self._claim_type_combo.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid #E0E6ED; border-radius: 8px;
                    padding: 6px 10px; background-color: #f0f7ff;
                    color: #333; font-size: 13px;
                }}
                QComboBox:focus {{ border-color: {Colors.PRIMARY_BLUE}; }}
                QComboBox::drop-down {{ border: none; width: 28px; }}
            """)
            # Use display_mappings labels (consistent with view mode)
            _CLAIM_TYPE_OPTIONS = [
                (1, get_claim_type_display(1)),
                (2, get_claim_type_display(2)),
                (3, get_claim_type_display(3)),
            ]
            logger.info(f"[EDIT] ClaimType options: {_CLAIM_TYPE_OPTIONS}")
            logger.info(f"[EDIT] current claimType value: {current_type!r} (type={type(current_type).__name__})")
            for code, label in _CLAIM_TYPE_OPTIONS:
                self._claim_type_combo.addItem(label, code)
            # Set current value — handle both int and string types
            idx = self._claim_type_combo.findData(current_type)
            if idx < 0 and isinstance(current_type, str):
                # Try matching by string-to-int conversion
                try:
                    idx = self._claim_type_combo.findData(int(current_type))
                except (ValueError, TypeError):
                    pass
            if idx < 0 and isinstance(current_type, int):
                # Try matching by int-to-string
                idx = self._claim_type_combo.findData(str(current_type))
            logger.info(f"[EDIT] ComboBox findData result: idx={idx}")
            if idx >= 0:
                self._claim_type_combo.setCurrentIndex(idx)
            type_row.addWidget(self._claim_type_combo)
        else:
            type_value = QLabel(get_claim_type_display(current_type))
            type_value.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
            type_value.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            type_row.addWidget(type_value)

        type_row.addStretch()
        type_widget = QWidget()
        type_widget.setStyleSheet("background: transparent; border: none;")
        type_widget.setLayout(type_row)
        self._relation_content.addWidget(type_widget)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #E2E8F0; border: none;")
        self._relation_content.addWidget(divider)

        # Evidence header row (title + upload button in edit mode)
        ev_header = QHBoxLayout()
        ev_header.setContentsMargins(0, 0, 0, 0)
        ev_title = QLabel("المستندات المرفقة")
        ev_title.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        ev_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        ev_header.addWidget(ev_title)
        ev_header.addStretch()

        if self._is_editing:
            upload_btn = QPushButton("+ رفع مستند")
            upload_btn.setFixedHeight(32)
            upload_btn.setCursor(Qt.PointingHandCursor)
            upload_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE}; color: white;
                    border: none; border-radius: 6px; padding: 0 16px;
                    font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background-color: #2A7BC8; }}
            """)
            upload_btn.clicked.connect(self._on_upload_evidence)
            ev_header.addWidget(upload_btn)

            pick_btn = QPushButton("اختيار مستند")
            pick_btn.setFixedHeight(32)
            pick_btn.setCursor(Qt.PointingHandCursor)
            pick_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: {Colors.PRIMARY_BLUE};
                    border: 1.5px solid {Colors.PRIMARY_BLUE}; border-radius: 6px;
                    padding: 0 16px; font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background-color: #EFF6FF; }}
            """)
            pick_btn.clicked.connect(self._on_pick_existing_evidence)
            ev_header.addWidget(pick_btn)

        ev_header_widget = QWidget()
        ev_header_widget.setStyleSheet("background: transparent; border: none;")
        ev_header_widget.setLayout(ev_header)
        self._relation_content.addWidget(ev_header_widget)

        # Evidence thumbnails
        active_evidences = [ev for ev in self._evidences
                           if str(ev.get("id") or ev.get("evidenceId") or "") not in self._pending_deletes]

        if active_evidences or self._pending_uploads or self._pending_links:
            thumbs_container = QWidget()
            thumbs_container.setStyleSheet("background: transparent; border: none;")
            thumbs_layout = QHBoxLayout(thumbs_container)
            thumbs_layout.setContentsMargins(0, 0, 0, 0)
            thumbs_layout.setSpacing(10)

            for ev in active_evidences:
                card = self._create_evidence_thumbnail(ev)
                thumbs_layout.addWidget(card)

            # Pending uploads (local files not yet saved)
            for fp in self._pending_uploads:
                card = self._create_pending_upload_card(fp)
                thumbs_layout.addWidget(card)

            # Pending links (existing docs selected for linking)
            for ev_data in self._pending_links:
                card = self._create_pending_link_card(ev_data)
                thumbs_layout.addWidget(card)

            thumbs_layout.addStretch()
            self._relation_content.addWidget(thumbs_container)
        else:
            no_ev = QLabel("لا توجد مستندات مرفقة")
            no_ev.setFont(create_font(size=FontManager.SIZE_BODY))
            no_ev.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_ev.setAlignment(Qt.AlignCenter)
            self._relation_content.addWidget(no_ev)

        # Save/Cancel buttons moved to header (edit_btn + cancel_edit_btn)

    def _create_evidence_thumbnail(self, evidence):
        """Create a clickable thumbnail card for an evidence document."""
        from PyQt5.QtGui import QPixmap

        ev_id = str(evidence.get("id") or evidence.get("evidenceId") or "")
        file_name = str(evidence.get("fileName") or evidence.get("originalFileName") or "مستند")

        card = QFrame()
        card.setFixedSize(80, 105)
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
            }
            QFrame:hover { border-color: #3890DF; }
        """)
        card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb = QLabel()
        thumb.setFixedSize(70, 70)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")

        local_path = self._download_evidence_file(ev_id, file_name)
        if local_path:
            px = QPixmap(local_path)
            if not px.isNull():
                thumb.setPixmap(px.scaled(66, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._set_file_type_icon(thumb, file_name)
        else:
            self._set_file_type_icon(thumb, file_name)

        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_short = file_name[:12] + "..." if len(file_name) > 12 else file_name
        name_lbl = QLabel(name_short)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        if self._is_editing and ev_id:
            # Delete button overlay
            del_btn = QPushButton("✕", card)
            del_btn.setFixedSize(18, 18)
            del_btn.move(60, 2)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E53E3E; color: white; border: none;
                    border-radius: 9px; font-size: 10px; font-weight: bold;
                }
                QPushButton:hover { background-color: #C53030; }
            """)
            del_btn.clicked.connect(lambda _, eid=ev_id: self._on_delete_evidence(eid))
        elif local_path:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            card.mousePressEvent = lambda e, fp=local_path: QDesktopServices.openUrl(QUrl.fromLocalFile(fp))
        else:
            def _on_click_unavailable(event, page=self):
                Toast.show_toast(page, "لا يمكن تحميل المستند حالياً", Toast.WARNING)
            card.mousePressEvent = _on_click_unavailable

        return card

    def _set_file_type_icon(self, label, file_name):
        """Set a file-type-appropriate icon on a QLabel."""
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext == "pdf":
            icon_text = "PDF"
            bg_color = "#E53E3E"
        elif ext in ("jpg", "jpeg", "png", "bmp", "gif", "webp"):
            icon_text = "IMG"
            bg_color = "#3182CE"
        else:
            icon_text = "DOC"
            bg_color = "#718096"
        label.setText(icon_text)
        label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        label.setStyleSheet(
            f"color: white; background-color: {bg_color}; border-radius: 8px; border: none;"
        )

    def _download_evidence_file(self, evidence_id, file_name):
        """Download evidence file to temp dir using multiple strategies, return local path or None."""
        if not evidence_id:
            return None
        import os, tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), "trrcms_evidence")
        os.makedirs(cache_dir, exist_ok=True)
        save_path = os.path.join(cache_dir, f"{evidence_id}_{file_name}")

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return save_path

        from services.api_client import get_api_client
        api = get_api_client()

        # Strategy 1: Try direct download endpoint
        try:
            api.download_evidence(evidence_id, save_path)
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                return save_path
        except Exception as e:
            logger.debug(f"Direct download failed for {evidence_id}: {e}")

        # Strategy 2: Get evidence metadata — try filePath/fileUrl
        try:
            meta = api.get_evidence_by_id(evidence_id)
            if meta:
                logger.info(f"Evidence metadata keys: {list(meta.keys())}")
                file_url = (meta.get("fileUrl") or meta.get("blobUrl")
                            or meta.get("url") or meta.get("downloadUrl"))
                file_path_val = meta.get("filePath")

                import requests as _requests
                auth_headers = {
                    "Authorization": f"Bearer {api.access_token}",
                    "Accept": "*/*"
                }

                # Try direct URL first
                if file_url and file_url.startswith("http"):
                    try:
                        resp = _requests.get(file_url, headers=auth_headers, timeout=30, verify=False)
                        resp.raise_for_status()
                        with open(save_path, 'wb') as f:
                            f.write(resp.content)
                        if os.path.getsize(save_path) > 0:
                            return save_path
                    except Exception:
                        pass

                # Try filePath with base URL variations
                if file_path_val:
                    base = api.base_url.rstrip("/")
                    # Remove /api suffix to get server root
                    server_root = base.rsplit("/api", 1)[0] if base.endswith("/api") else base
                    urls_to_try = [
                        f"{base}/{file_path_val}",
                        f"{server_root}/{file_path_val}",
                    ]
                    for url in urls_to_try:
                        try:
                            logger.info(f"Trying evidence URL: {url}")
                            resp = _requests.get(url, headers=auth_headers, timeout=30, verify=False)
                            resp.raise_for_status()
                            with open(save_path, 'wb') as f:
                                f.write(resp.content)
                            if os.path.getsize(save_path) > 0:
                                logger.info(f"Evidence downloaded from: {url}")
                                return save_path
                        except Exception as url_err:
                            logger.info(f"URL failed ({url}): {url_err}")
                            continue
        except Exception as e:
            logger.warning(f"Metadata download failed for {evidence_id}: {e}")

        return None

    def _populate_status_card(self):
        self._clear_layout(self._status_content)

        claim = self._claim_data
        case_status = claim.get("caseStatus") or claim.get("status", 1)
        status_label = _CASE_STATUS_LABELS.get(case_status, "غير محدد")
        has_conflict = claim.get("hasConflict") or claim.get("hasConflicts", False)
        evidence_count = claim.get("evidenceCount") or len(self._evidences)

        # Status banner — 3 states: closed, pending evidence, open
        if case_status == 2:
            banner_bg, banner_border, banner_color = "#F0FDF4", "#BBF7D0", "#15803D"
            banner_text = "المطالبة مغلقة"
        elif case_status == 1 and evidence_count == 0:
            banner_bg, banner_border, banner_color = "#FFFBEB", "#FDE68A", "#92400E"
            banner_text = "بانتظار الأدلة — تم تسجيل المُطالِب دون مستندات"
        else:
            banner_bg, banner_border, banner_color = "#FFF7ED", "#FED7AA", "#C2410C"
            banner_text = "المطالبة مفتوحة"

        banner = QFrame()
        banner.setStyleSheet(f"""
            QFrame {{ background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; }}
        """)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(16, 10, 16, 10)

        banner_lbl = QLabel(banner_text)
        banner_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
        banner_lbl.setStyleSheet(f"color: {banner_color}; background: transparent; border: none;")
        banner_layout.addWidget(banner_lbl)
        banner_layout.addStretch()
        self._status_content.addWidget(banner)

        # Stats grid — distributed evenly
        stats_grid = QGridLayout()
        stats_grid.setSpacing(16)
        stats_grid.setContentsMargins(0, 4, 0, 0)
        for c in range(3):
            stats_grid.setColumnStretch(c, 1)

        stats_grid.addWidget(self._create_field_pair("الحالة", status_label), 0, 0)
        stats_grid.addWidget(self._create_field_pair("التعارض", "نعم" if has_conflict else "لا يوجد"), 0, 1)
        stats_grid.addWidget(self._create_field_pair("عدد المستندات", str(evidence_count)), 0, 2)

        stats_widget = QWidget()
        stats_widget.setStyleSheet("background: transparent; border: none;")
        stats_widget.setLayout(stats_grid)
        self._status_content.addWidget(stats_widget)

    # =========================================================================
    # Actions
    # =========================================================================

    def _on_edit_or_save_clicked(self):
        if self._is_editing:
            logger.info("[EDIT] Save button clicked — calling _on_save_edit()")
            self._on_save_edit()
            return
        if not self._claim_id:
            logger.warning("[EDIT] No claim_id, cannot enter edit mode")
            return
        logger.info(f"[EDIT] Entering edit mode for claim {self._claim_id}")
        self._is_editing = True
        self._original_claim_type = self._claim_data.get("claimType")
        logger.info(f"[EDIT] Original claimType: {self._original_claim_type!r}")
        logger.info(f"[EDIT] survey_id: {self._survey_id}")
        logger.info(f"[EDIT] evidences count: {len(self._evidences)}")
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._extract_relation_id()
        logger.info(f"[EDIT] Extracted relation_id: {self._relation_id}")
        self._populate_relation_card()
        self._edit_btn.setText("حفظ التعديلات")
        self._cancel_edit_btn.setVisible(True)
        logger.info("[EDIT] Edit mode activated")

    def _update_edit_visibility(self):
        main_window = self.window()
        can_edit = False
        if hasattr(main_window, 'current_user') and main_window.current_user:
            role = getattr(main_window.current_user, 'role', '')
            case_status = self._claim_data.get("caseStatus") or self._claim_data.get("status", 1)
            can_edit = role in ("admin", "data_manager") and case_status == 1
        self._edit_btn.setVisible(can_edit)
        self._cancel_edit_btn.setVisible(False)

    # =========================================================================
    # Edit mode handlers
    # =========================================================================

    def _extract_relation_id(self):
        """Extract relation_id from claim data or evidence relations."""
        # Primary: from claim's sourceRelationId
        rel_id = self._claim_data.get("sourceRelationId")
        if rel_id:
            self._relation_id = rel_id
            return
        # Fallback: from evidence relations
        for ev in self._evidences:
            for rel in (ev.get("evidenceRelations") or []):
                rel_id = rel.get("personPropertyRelationId")
                if rel_id:
                    self._relation_id = rel_id
                    return

    def _on_cancel_edit(self):
        logger.info("[EDIT] Cancel edit — returning to view mode")
        self._is_editing = False
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._claim_type_combo = None
        self._populate_relation_card()
        self._edit_btn.setText("تعديل المطالبة")
        self._cancel_edit_btn.setVisible(False)
        self._update_edit_visibility()

    def _on_upload_evidence(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "اختيار مستندات", "",
            "Images & PDF (*.png *.jpg *.jpeg *.pdf)")
        if not file_paths:
            return
        self._pending_uploads.extend(file_paths)
        self._populate_relation_card()

    def _on_delete_evidence(self, evidence_id):
        if evidence_id not in self._pending_deletes:
            self._pending_deletes.append(evidence_id)
        self._populate_relation_card()

    def _on_remove_pending_upload(self, file_path):
        if file_path in self._pending_uploads:
            self._pending_uploads.remove(file_path)
        self._populate_relation_card()

    def _on_pick_existing_evidence(self):
        """Open dialog to pick existing evidence documents from survey."""
        logger.info(f"[PICK] Opening evidence picker, survey_id={self._survey_id}")
        if not self._survey_id:
            Toast.show_toast(self, "لا يمكن تحميل المستندات — survey_id غير متوفر", Toast.WARNING)
            return

        from services.api_client import get_api_client
        api = get_api_client()

        all_evidences = api.get_survey_evidences(self._survey_id)
        logger.info(f"[PICK] Got {len(all_evidences)} evidences from survey")

        # Exclude already-linked evidences and pending deletes
        linked_ids = {str(ev.get("id") or ev.get("evidenceId") or "") for ev in self._evidences}
        linked_ids -= set(self._pending_deletes)
        # Also exclude already-pending-link IDs
        for ev_data in self._pending_links:
            linked_ids.add(str(ev_data.get("id") or ev_data.get("evidenceId") or ""))

        from ui.components.dialogs.evidence_picker_dialog import EvidencePickerDialog
        dialog = EvidencePickerDialog(all_evidences, linked_ids, parent=self)
        if dialog.exec_() == EvidencePickerDialog.Accepted:
            selected_data = dialog.get_selected_data()
            self._pending_links.extend(selected_data)
            self._populate_relation_card()

    def _on_remove_pending_link(self, evidence_id):
        """Remove an evidence from the pending links list."""
        self._pending_links = [
            ev for ev in self._pending_links
            if str(ev.get("id") or ev.get("evidenceId") or "") != evidence_id
        ]
        self._populate_relation_card()

    def _create_pending_link_card(self, ev_data):
        """Create a thumbnail card for an existing evidence selected for linking (blue border)."""
        file_name = str(ev_data.get("originalFileName") or ev_data.get("fileName") or "مستند")
        ev_id = str(ev_data.get("id") or ev_data.get("evidenceId") or "")

        card = QFrame()
        card.setFixedSize(80, 105)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1.5px solid {Colors.PRIMARY_BLUE};
                border-radius: 6px;
            }}
            QFrame:hover {{ border-color: #2A7BC8; }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb = QLabel()
        thumb.setFixedSize(70, 70)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")
        self._set_file_type_icon(thumb, file_name)
        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_short = file_name[:12] + "..." if len(file_name) > 12 else file_name
        name_lbl = QLabel(name_short)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; border: none; background: transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        # Remove button
        del_btn = QPushButton("\u2715", card)
        del_btn.setFixedSize(18, 18)
        del_btn.move(60, 2)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53E3E; color: white; border: none;
                border-radius: 9px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #C53030; }
        """)
        del_btn.clicked.connect(lambda _, eid=ev_id: self._on_remove_pending_link(eid))

        return card

    def _create_pending_upload_card(self, file_path):
        """Create a thumbnail card for a pending (not yet uploaded) file."""
        import os
        from PyQt5.QtGui import QPixmap
        file_name = os.path.basename(file_path)

        card = QFrame()
        card.setFixedSize(80, 105)
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #68D391;
                border-radius: 6px;
            }
            QFrame:hover { border-color: #38A169; }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        thumb = QLabel()
        thumb.setFixedSize(70, 70)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")

        px = QPixmap(file_path)
        if not px.isNull():
            thumb.setPixmap(px.scaled(66, 66, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self._set_file_type_icon(thumb, file_name)

        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_short = file_name[:12] + "..." if len(file_name) > 12 else file_name
        name_lbl = QLabel(name_short)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet(f"color: #38A169; border: none; background: transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        card_layout.addWidget(name_lbl)

        # Remove button
        del_btn = QPushButton("✕", card)
        del_btn.setFixedSize(18, 18)
        del_btn.move(60, 2)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53E3E; color: white; border: none;
                border-radius: 9px; font-size: 10px; font-weight: bold;
            }
            QPushButton:hover { background-color: #C53030; }
        """)
        del_btn.clicked.connect(lambda _, fp=file_path: self._on_remove_pending_upload(fp))

        return card

    def _on_save_edit(self):
        """Save all pending changes via single PUT /api/v1/Claims/{id}."""
        import os
        import hashlib
        from controllers.claim_controller import ClaimController

        ctrl = ClaimController()

        # Check claim type change
        new_type = self._claim_type_combo.currentData() if self._claim_type_combo else None
        type_changed = new_type is not None and new_type != self._original_claim_type
        logger.info(f"[SAVE] new_type={new_type!r}, original={self._original_claim_type!r}, changed={type_changed}")
        logger.info(f"[SAVE] pending_uploads={len(self._pending_uploads)}, pending_deletes={len(self._pending_deletes)}, pending_links={len(self._pending_links)}")

        has_changes = type_changed or self._pending_uploads or self._pending_deletes or self._pending_links
        if not has_changes:
            Toast.show_toast(self, "لا توجد تعديلات للحفظ", Toast.INFO)
            self._on_cancel_edit()
            return

        # Modification reason dialog (required by backend for all changes)
        from ui.components.dialogs.modification_reason_dialog import ModificationReasonDialog
        summary = []
        if type_changed:
            old_label = get_claim_type_display(self._original_claim_type)
            new_label = get_claim_type_display(new_type)
            summary.append(f"تغيير نوع المطالبة: {old_label} → {new_label}")
        if self._pending_uploads:
            summary.append(f"رفع {len(self._pending_uploads)} مستند جديد")
        if self._pending_links:
            summary.append(f"ربط {len(self._pending_links)} مستند موجود")
        if self._pending_deletes:
            summary.append(f"إزالة {len(self._pending_deletes)} مستند")
        dialog = ModificationReasonDialog(summary, parent=self)
        if dialog.exec_() != ModificationReasonDialog.Accepted:
            return
        reason = dialog.get_reason()

        # Build single update command for PUT /api/v1/Claims/{id}
        update_data = {}

        if type_changed:
            update_data["relationType"] = new_type

        # New evidence from uploaded files
        if self._pending_uploads:
            new_evidence = []
            for fp in self._pending_uploads:
                try:
                    file_size = os.path.getsize(fp)
                    file_name = os.path.basename(fp)
                    ext = os.path.splitext(file_name)[1].lower()
                    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                                ".png": "image/png", ".pdf": "application/pdf"}
                    mime_type = mime_map.get(ext, "application/octet-stream")
                    with open(fp, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    new_evidence.append({
                        "evidenceType": 2,
                        "description": file_name,
                        "originalFileName": file_name,
                        "filePath": fp,
                        "fileSizeBytes": file_size,
                        "mimeType": mime_type,
                        "fileHash": file_hash,
                    })
                except Exception as e:
                    logger.error(f"[SAVE] Failed to read file {fp}: {e}")
            if new_evidence:
                update_data["newEvidence"] = new_evidence

        # Link existing evidence
        if self._pending_links:
            link_ids = []
            for ev_data in self._pending_links:
                ev_id = str(ev_data.get("id") or ev_data.get("evidenceId") or "")
                if ev_id:
                    link_ids.append(ev_id)
            if link_ids:
                update_data["linkExistingEvidenceIds"] = link_ids

        # Unlink evidence
        if self._pending_deletes:
            update_data["unlinkEvidenceRelationIds"] = list(self._pending_deletes)

        if reason:
            update_data["reasonForModification"] = reason

        logger.info(f"[SAVE] Update command: {update_data}")
        result = ctrl.update_claim(self._claim_id, update_data)
        logger.info(f"[SAVE] Result: success={result.success}, msg={result.message}")

        if not result.success:
            Toast.show_toast(self, f"فشل حفظ التعديلات: {result.message}", Toast.ERROR)
        else:
            Toast.show_toast(self, "تم حفظ التعديلات بنجاح", Toast.SUCCESS)

        # Reload data and switch back to view mode
        self._is_editing = False
        self._pending_uploads = []
        self._pending_deletes = []
        self._pending_links = []
        self._claim_type_combo = None
        self._edit_btn.setText("تعديل المطالبة")
        self._cancel_edit_btn.setVisible(False)
        self._reload_claim_data()

    def _reload_claim_data(self):
        """Reload claim data from API and refresh the page."""
        from controllers.claim_controller import ClaimController
        ctrl = ClaimController()
        result = ctrl.get_claim_full_detail(self._claim_id, hint_survey_id=self._survey_id)
        if result.success:
            self.refresh(result.data)
        else:
            logger.warning(f"Failed to reload claim data: {result.message}")
