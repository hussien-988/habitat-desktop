# -*- coding: utf-8 -*-
"""
Building Details Page — عرض تفاصيل المبنى
Card-based view matching review_step.py pattern (DRY).
3 cards: building info, stats, location + units table toggle.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea,
    QGraphicsDropShadowEffect,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon

from models.building import Building
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from controllers.unit_controller import UnitController
from services.display_mappings import get_unit_type_display, get_unit_status_display
from ui.components.icon import Icon
from ui.design_system import Colors, PageDimensions, ButtonDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.helpers import format_date, build_hierarchical_address
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingDetailsPage(QWidget):
    """Building details page — 3 cards + units table toggle."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.unit_controller = UnitController(db)
        self.current_building = None

        self._units_view_active = False
        self._units_list = []
        self._units_page = 1
        self._units_per_page = 11

        self._setup_ui()

    # =========================================================================
    # UI Setup
    # =========================================================================

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(15)

        # Header: [title+breadcrumb right] <stretch> [button left]
        header_row = QHBoxLayout()
        header_row.setSpacing(15)

        title_area = QVBoxLayout()
        title_area.setSpacing(2)

        self.title_label = QLabel("")
        self.title_label.setFont(create_font(
            size=FontManager.SIZE_TITLE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self.title_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        title_area.addWidget(self.title_label)

        self.breadcrumb_label = QLabel("المباني  •  عرض")
        self.breadcrumb_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self.breadcrumb_label.setStyleSheet(
            f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;"
        )
        title_area.addWidget(self.breadcrumb_label)

        header_row.addLayout(title_area)
        header_row.addStretch()

        # "عرض" button (same style as save button)
        self.view_units_btn = QPushButton(" عرض")
        self.view_units_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)
        self.view_units_btn.setCursor(Qt.PointingHandCursor)
        self.view_units_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        self.view_units_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                padding: {ButtonDimensions.SAVE_PADDING_V}px {ButtonDimensions.SAVE_PADDING_H}px;
                border-radius: {ButtonDimensions.SAVE_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
            }}
            QPushButton:hover {{
                background-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
        """)
        self.view_units_btn.clicked.connect(self._toggle_units_view)
        header_row.addWidget(self.view_units_btn)

        layout.addLayout(header_row)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(20)

        # Card 1: Building info (header + code + address)
        self.info_card, self.info_content = self._create_card_base(
            "blue", "بيانات البناء", "معلومات البناء والموقع الجغرافي"
        )
        self._scroll_layout.addWidget(self.info_card)

        # Card 2: Stats row
        self.stats_card, self.stats_content = self._create_simple_card()
        self._scroll_layout.addWidget(self.stats_card)

        # Card 3: Location
        self.location_card, self.location_content = self._create_simple_card()
        self._scroll_layout.addWidget(self.location_card)

        # Units table card (initially hidden)
        self.units_table_card = self._create_units_table_card()
        self.units_table_card.setVisible(False)
        self._scroll_layout.addWidget(self.units_table_card)

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    # =========================================================================
    # Card Builders (DRY — same pattern as review_step.py)
    # =========================================================================

    def _create_card_base(self, icon_name: str, title: str, subtitle: str) -> tuple:
        """Create card with header (icon + title + subtitle). Returns (card, content_layout)."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
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

        # Icon (28x28, rounded)
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

        # Content container
        content_widget = QWidget()
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)

        return card, content_layout

    def _create_simple_card(self) -> tuple:
        """Create a simple card (no header). Returns (card, content_layout)."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
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

    def _add_shadow(self, widget: QWidget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        widget.setGraphicsEffect(shadow)

    # =========================================================================
    # Units Table Card
    # =========================================================================

    def _create_units_table_card(self) -> QFrame:
        """Create card containing the units table for this building."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setObjectName("unitsTableCard")
        card.setStyleSheet(f"""
            QFrame#unitsTableCard {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Table widget
        self.units_table = QTableWidget()
        self.units_table.setColumnCount(5)
        self.units_table.setRowCount(self._units_per_page)
        self.units_table.setLayoutDirection(Qt.RightToLeft)
        self.units_table.setShowGrid(False)
        self.units_table.setFocusPolicy(Qt.NoFocus)
        self.units_table.setSelectionMode(QTableWidget.NoSelection)
        self.units_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.units_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.units_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Headers
        headers = ["رقم المقسم", "المساحة", "نوع المقسم", "حالة المقسم", "وصف المقسم"]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            self.units_table.setHorizontalHeaderItem(i, item)

        # Styling (same as units_page.py)
        self.units_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
                font-size: 10.5pt;
                font-weight: 400;
                color: #212B36;
            }
            QTableWidget::item {
                padding: 8px 15px;
                border-bottom: 1px solid #F0F0F0;
                color: #212B36;
                font-size: 10.5pt;
                font-weight: 400;
            }
            QTableWidget::item:hover {
                background-color: #FAFBFC;
            }
            QHeaderView {
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                padding: 12px;
                padding-left: 30px;
                border: none;
                color: #637381;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }
            QHeaderView::section:hover {
                background-color: #EBEEF2;
            }
        """ + StyleManager.scrollbar())

        # Header config
        h = self.units_table.horizontalHeader()
        h.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.setFixedHeight(56)
        h.setStretchLastSection(True)

        # Column widths
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.resizeSection(0, 200)
        h.setSectionResizeMode(1, QHeaderView.Fixed)
        h.resizeSection(1, 150)
        h.setSectionResizeMode(2, QHeaderView.Fixed)
        h.resizeSection(2, 220)
        h.setSectionResizeMode(3, QHeaderView.Fixed)
        h.resizeSection(3, 220)
        h.setSectionResizeMode(4, QHeaderView.Stretch)

        # Row heights
        v_header = self.units_table.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(52)

        card_layout.addWidget(self.units_table)

        # Footer with pagination
        footer = QFrame()
        footer.setObjectName("unitsFooter")
        footer.setStyleSheet("""
            QFrame#unitsFooter {
                background-color: #F8F9FA;
                border-top: 1px solid #E1E8ED;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        footer.setFixedHeight(58)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)

        # Navigation buttons
        nav_btn_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #EBEEF2; }
            QPushButton:disabled { color: #C1C7CD; border-color: #E8EBED; }
        """

        self.units_prev_btn = QPushButton(">")
        self.units_prev_btn.setFixedSize(32, 32)
        self.units_prev_btn.setCursor(Qt.PointingHandCursor)
        self.units_prev_btn.setStyleSheet(nav_btn_style)
        self.units_prev_btn.clicked.connect(self._on_units_prev_page)
        footer_layout.addWidget(self.units_prev_btn)

        self.units_next_btn = QPushButton("<")
        self.units_next_btn.setFixedSize(32, 32)
        self.units_next_btn.setCursor(Qt.PointingHandCursor)
        self.units_next_btn.setStyleSheet(nav_btn_style)
        self.units_next_btn.clicked.connect(self._on_units_next_page)
        footer_layout.addWidget(self.units_next_btn)

        self.units_page_label = QLabel("0-0 of 0")
        self.units_page_label.setStyleSheet(
            "color: #637381; font-size: 10pt; font-weight: 400; background: transparent;"
        )
        footer_layout.addWidget(self.units_page_label)
        footer_layout.addStretch()

        card_layout.addWidget(footer)

        return card

    # =========================================================================
    # Data Loading
    # =========================================================================

    def refresh(self, data=None):
        """Load building and populate cards.

        Args:
            data: Building object or building_id string
        """
        if not data:
            return

        if isinstance(data, Building):
            building = data
        else:
            building = self.building_repo.get_by_id(str(data))
            if not building:
                logger.error(f"Building not found: {data}")
                return

        self.current_building = building

        # Reset to cards view
        if self._units_view_active:
            self.info_card.setVisible(True)
            self.stats_card.setVisible(True)
            self.location_card.setVisible(True)
            self.units_table_card.setVisible(False)
            self.view_units_btn.setText(" عرض")
            self._units_view_active = False

        display_id = building.building_id_formatted or building.building_id or "-"
        self.title_label.setText(display_id)

        self._populate_cards(building)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _populate_cards(self, building: Building):
        """Populate all 3 cards with building data."""
        self._clear_layout(self.info_content)
        self._clear_layout(self.stats_content)
        self._clear_layout(self.location_content)

        building_code = str(building.building_id) if building.building_id else "-"
        status = building.building_status_display if hasattr(building, 'building_status_display') else "-"
        building_type = building.building_type_display if hasattr(building, 'building_type_display') else "-"
        units_count = str(getattr(building, 'number_of_units', 0))
        apartments_count = str(getattr(building, 'number_of_apartments', 0))
        shops_count = str(getattr(building, 'number_of_shops', 0))
        entry_date = format_date(getattr(building, 'created_at', None)) or "-"
        location_desc = getattr(building, 'location_description', '-') or '-'
        general_desc = getattr(building, 'general_description', '-') or '-'

        # ===== Card 1: Building number + address bar =====
        num_label = QLabel(building_code)
        num_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        num_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        num_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        self.info_content.addWidget(num_label)

        address = build_hierarchical_address(building_obj=building, unit_obj=None, include_unit=False)
        addr_bar = QFrame()
        addr_bar.setLayoutDirection(Qt.RightToLeft)
        addr_bar.setFixedHeight(28)
        addr_bar.setStyleSheet("QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }")
        addr_row = QHBoxLayout(addr_bar)
        addr_row.setContentsMargins(12, 0, 12, 0)
        addr_row.setSpacing(8)

        addr_row.addStretch()
        addr_icon = QLabel()
        addr_icon.setStyleSheet("background: transparent; border: none;")
        addr_pixmap = Icon.load_pixmap("dec", size=16)
        if addr_pixmap and not addr_pixmap.isNull():
            addr_icon.setPixmap(addr_pixmap)
        addr_row.addWidget(addr_icon)

        addr_text = QLabel(address if address else "-")
        addr_text.setAlignment(Qt.AlignCenter)
        addr_text.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        addr_text.setStyleSheet("color: #0F5B95; background: transparent; border: none;")
        addr_row.addWidget(addr_text)
        addr_row.addStretch()
        self.info_content.addWidget(addr_bar)

        # ===== Card 2: Stats row (6 columns) =====
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(0)

        stat_items = [
            ("حالة البناء", status),
            ("نوع البناء", building_type),
            ("العدد الكلي للمقاسم", units_count),
            ("عدد المقاسم السكنية", apartments_count),
            ("عدد المقاسم غير السكنية", shops_count),
            ("تاريخ الادخال", entry_date),
        ]

        for label_text, value_text in stat_items:
            section = QWidget()
            section.setStyleSheet("background: transparent;")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)
            section_layout.setAlignment(Qt.AlignCenter)

            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

            val = QLabel(str(value_text))
            val.setAlignment(Qt.AlignCenter)
            val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
            val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

            section_layout.addWidget(lbl)
            section_layout.addWidget(val)
            stats_row.addWidget(section, stretch=1)

        self.stats_content.addLayout(stats_row)

        # ===== Card 3: Location (map + descriptions) =====
        loc_header = QLabel("موقع البناء")
        loc_header.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        loc_header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        self.location_content.addWidget(loc_header)

        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        # Map placeholder
        map_container = QLabel()
        map_container.setFixedSize(400, 130)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("detailsMapContainer")
        map_container.setStyleSheet("QLabel#detailsMapContainer { background-color: #E8E8E8; border-radius: 8px; }")
        map_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_pixmap or map_pixmap.isNull():
            map_pixmap = Icon.load_pixmap("map-placeholder", size=None)
        if map_pixmap and not map_pixmap.isNull():
            map_container.setPixmap(map_pixmap.scaled(400, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        else:
            loc_fallback = Icon.load_pixmap("carbon_location-filled", size=48)
            if loc_fallback and not loc_fallback.isNull():
                map_container.setPixmap(loc_fallback)

        # "فتح الخريطة" button
        map_button = QPushButton(map_container)
        map_button.setFixedSize(94, 20)
        map_button.move(8, 8)
        map_button.setCursor(Qt.PointingHandCursor)
        pill_pixmap = Icon.load_pixmap("pill", size=12)
        if pill_pixmap and not pill_pixmap.isNull():
            map_button.setIcon(QIcon(pill_pixmap))
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
        map_button.clicked.connect(self._open_map_dialog)

        # Location pin icon
        location_icon = QLabel(map_container)
        loc_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if loc_pixmap and not loc_pixmap.isNull():
            location_icon.setPixmap(loc_pixmap)
            location_icon.setFixedSize(56, 56)
            location_icon.move(172, 37)
            location_icon.setStyleSheet("background: transparent;")

        content_row.addWidget(map_container)

        # Location description
        loc_desc_section = QVBoxLayout()
        loc_desc_section.setSpacing(4)
        loc_desc_lbl = QLabel("وصف الموقع")
        loc_desc_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        loc_desc_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        loc_desc_val = QLabel(location_desc)
        loc_desc_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        loc_desc_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        loc_desc_val.setWordWrap(True)
        loc_desc_section.addWidget(loc_desc_lbl)
        loc_desc_section.addWidget(loc_desc_val)
        loc_desc_section.addStretch(1)
        content_row.addLayout(loc_desc_section, stretch=1)

        # General description
        gen_desc_section = QVBoxLayout()
        gen_desc_section.setSpacing(4)
        gen_desc_lbl = QLabel("الوصف العام")
        gen_desc_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        gen_desc_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        gen_desc_val = QLabel(general_desc)
        gen_desc_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        gen_desc_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        gen_desc_val.setWordWrap(True)
        gen_desc_section.addWidget(gen_desc_lbl)
        gen_desc_section.addWidget(gen_desc_val)
        gen_desc_section.addStretch(1)
        content_row.addLayout(gen_desc_section, stretch=1)

        self.location_content.addLayout(content_row)

    # =========================================================================
    # Units View Toggle
    # =========================================================================

    def _toggle_units_view(self):
        """Toggle between cards view and units table view."""
        if self._units_view_active:
            self.info_card.setVisible(True)
            self.stats_card.setVisible(True)
            self.location_card.setVisible(True)
            self.units_table_card.setVisible(False)
            self.view_units_btn.setText(" عرض")
            self._units_view_active = False
        else:
            self.info_card.setVisible(False)
            self.stats_card.setVisible(False)
            self.location_card.setVisible(False)
            self.units_table_card.setVisible(True)
            self.view_units_btn.setText(" رجوع")
            self._units_view_active = True
            self._load_units()

    def _load_units(self):
        """Load units for the current building."""
        if not self.current_building:
            return

        try:
            main_window = self.window()
            if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
                self.unit_controller.set_auth_token(main_window._api_token)
        except Exception as e:
            logger.warning(f"Could not set auth token: {e}")

        building_uuid = self.current_building.building_uuid or self.current_building.building_id
        result = self.unit_controller.get_units_for_building(building_uuid)

        if result.success:
            self._units_list = result.data or []
        else:
            logger.error(f"Failed to load units: {result.message}")
            self._units_list = []

        self._units_page = 1
        self._update_units_table()

    def _update_units_table(self):
        """Populate the units table with current page data."""
        total = len(self._units_list)
        total_pages = max(1, (total + self._units_per_page - 1) // self._units_per_page)
        self._units_page = min(self._units_page, total_pages)

        start_idx = (self._units_page - 1) * self._units_per_page
        end_idx = min(start_idx + self._units_per_page, total)
        page_units = self._units_list[start_idx:end_idx]

        self.units_table.clearSpans()
        self.units_table.setRowCount(self._units_per_page)

        # Clear all cells
        for row in range(self._units_per_page):
            for col in range(5):
                self.units_table.setItem(row, col, QTableWidgetItem(""))

        if total == 0:
            self.units_table.setSpan(0, 0, self._units_per_page, 5)
            empty_item = QTableWidgetItem("لا توجد مقاسم لهذا المبنى")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setForeground(QColor("#9CA3AF"))
            self.units_table.setItem(0, 0, empty_item)
            self.units_page_label.setText("0-0 of 0")
            self.units_prev_btn.setEnabled(False)
            self.units_next_btn.setEnabled(False)
            return

        for row, unit in enumerate(page_units):
            # col 0: unit number
            try:
                num = str(int(unit.unit_number))
            except (ValueError, TypeError):
                num = unit.unit_number or ""
            self.units_table.setItem(row, 0, QTableWidgetItem(num))

            # col 1: area
            area = str(unit.area_sqm) if unit.area_sqm else "-"
            self.units_table.setItem(row, 1, QTableWidgetItem(area))

            # col 2: unit type
            self.units_table.setItem(row, 2, QTableWidgetItem(
                get_unit_type_display(unit.unit_type)
            ))

            # col 3: unit status
            self.units_table.setItem(row, 3, QTableWidgetItem(
                get_unit_status_display(unit.apartment_status)
            ))

            # col 4: description (truncated)
            desc = unit.property_description or ""
            desc_display = desc[:40] + "..." if len(desc) > 40 else desc
            self.units_table.setItem(row, 4, QTableWidgetItem(desc_display))

        self.units_page_label.setText(f"{start_idx + 1}-{end_idx} of {total}")
        self.units_prev_btn.setEnabled(self._units_page > 1)
        self.units_next_btn.setEnabled(self._units_page < total_pages)

    def _on_units_prev_page(self):
        if self._units_page > 1:
            self._units_page -= 1
            self._update_units_table()

    def _on_units_next_page(self):
        total = len(self._units_list)
        total_pages = max(1, (total + self._units_per_page - 1) // self._units_per_page)
        if self._units_page < total_pages:
            self._units_page += 1
            self._update_units_table()

    # =========================================================================
    # Map Dialog
    # =========================================================================

    def _open_map_dialog(self):
        """Open map dialog in read-only mode."""
        from ui.components.building_map_dialog_v2 import show_building_map_dialog

        if not self.current_building:
            return

        auth_token = None
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, '_api_token'):
                auth_token = main_window._api_token
        except Exception as e:
            logger.warning(f"Could not get auth token: {e}")

        show_building_map_dialog(
            db=self.db,
            selected_building_id=self.current_building.building_uuid or self.current_building.building_id,
            auth_token=auth_token,
            read_only=True,
            selected_building=self.current_building,
            parent=self
        )

    def update_language(self, is_arabic: bool):
        pass
