# -*- coding: utf-8 -*-
"""
Review Step - Step 7 of Office Survey Wizard.

Final review and submission step - displays summary cards from all previous steps.
"""

from typing import Dict, Any
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
    QHBoxLayout, QGridLayout, QMessageBox, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.design_system import Colors
from ui.font_utils import FontManager, create_font
from ui.components.icon import Icon
from utils.logger import get_logger
from app.config import Config
from services.survey_api_service import SurveyApiService

logger = get_logger(__name__)


class ReviewStep(BaseStep):
    """Step 7: Review & Submit."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

        # Initialize API service for finalizing survey
        self._api_service = SurveyApiService()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

    def setup_ui(self):
        """Setup the step's UI with scrollable summary cards."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BACKGROUND};
            }}
        """)

        layout = self.main_layout
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(16)

        # --- Main Scroll Area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {Colors.BACKGROUND};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_DEFAULT};
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.TEXT_SECONDARY};
            }}
        """)

        # Scroll content container
        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Create summary cards for each step
        self.building_card = self._create_building_card()
        scroll_layout.addWidget(self.building_card)

        self.unit_card = self._create_unit_card()
        scroll_layout.addWidget(self.unit_card)

        self.household_card = self._create_household_card()
        scroll_layout.addWidget(self.household_card)

        self.persons_card = self._create_persons_card()
        scroll_layout.addWidget(self.persons_card)

        self.relations_card = self._create_relations_card()
        scroll_layout.addWidget(self.relations_card)

        self.claim_card = self._create_claim_card()
        scroll_layout.addWidget(self.claim_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _add_shadow(self, widget: QWidget):
        """Add drop shadow effect to a widget."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        widget.setGraphicsEffect(shadow)

    def _create_card_base(self, icon_name: str, title: str, subtitle: str) -> tuple:
        """Create base card with header (icon, title, subtitle) and return card and content layout."""
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

        # Header with icon, title, subtitle
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 10px;
            }}
        """)

        icon_pixmap = Icon.load_pixmap(icon_name, size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        # Title and subtitle
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        title_label.setAlignment(Qt.AlignRight)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        subtitle_label.setAlignment(Qt.AlignRight)

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        # In RTL mode: first added = rightmost
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_container)
        header_layout.addStretch()

        card_layout.addWidget(header_container)

        # Content container
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)

        return card, content_layout

    def _create_stat_item(self, value: str, label: str, color: str = None, label_on_top: bool = False) -> QWidget:
        """Create a stat item with value and label (like in building_selection_step).

        Args:
            value: The stat value
            label: The stat label
            color: Optional color for value
            label_on_top: If True, label is on top and value below (Step 1 style)
        """
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        if label_on_top:
            # Step 1 style: Label on top (darker), Value below (lighter)
            label_widget = QLabel(label)
            label_widget.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            label_widget.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            label_widget.setAlignment(Qt.AlignCenter)

            value_label = QLabel(str(value))
            value_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            value_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            value_label.setAlignment(Qt.AlignCenter)

            layout.addWidget(label_widget)
            layout.addWidget(value_label)
        else:
            # Default style: Value on top (bold, colored), Label below
            value_label = QLabel(str(value))
            value_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
            value_color = color if color else Colors.TEXT_PRIMARY
            value_label.setStyleSheet(f"color: {value_color}; background: transparent; border: none;")
            value_label.setAlignment(Qt.AlignCenter)

            label_widget = QLabel(label)
            label_widget.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            label_widget.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            label_widget.setAlignment(Qt.AlignCenter)

            layout.addWidget(value_label)
            layout.addWidget(label_widget)

        return container

    def _create_stat_row(self, stats: list, label_on_top: bool = False, with_separators: bool = True) -> QWidget:
        """Create a horizontal row of stat items.

        Args:
            stats: List of stat dicts with 'value', 'label', and optional 'color'
            label_on_top: If True, use Step 1 style (label on top)
            with_separators: If True, add vertical separators between items
        """
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)

        for i, stat in enumerate(stats):
            stat_widget = self._create_stat_item(
                stat.get('value', '-'),
                stat.get('label', ''),
                stat.get('color'),
                label_on_top=label_on_top
            )
            layout.addWidget(stat_widget, stretch=1)
            if with_separators and i < len(stats) - 1:
                # Add separator
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background-color: {Colors.BORDER_DEFAULT}; border: none;")
                layout.addWidget(sep)

        return container

    def _create_field(self, label: str, value: str) -> QWidget:
        """Create a labeled field widget for displaying data."""
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Label
        label_widget = QLabel(label)
        label_widget.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label_widget.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        label_widget.setAlignment(Qt.AlignRight)

        # Value
        value_widget = QLabel(value)
        value_widget.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        value_widget.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.INPUT_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        value_widget.setAlignment(Qt.AlignRight)
        value_widget.setWordWrap(True)

        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        return container

    def _create_person_row(self, name: str, role: str, icon_name: str = "user-account") -> QWidget:
        """Create a person row with icon, name and role (like in person_step)."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Role on left (RTL)
        role_label = QLabel(role)
        role_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        role_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px 8px;
            }}
        """)

        # Name
        name_label = QLabel(name)
        name_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        name_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        name_label.setAlignment(Qt.AlignRight)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 16px;
            }}
        """)
        icon_pixmap = Icon.load_pixmap(icon_name, size=20)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        layout.addWidget(role_label)
        layout.addStretch()
        layout.addWidget(name_label)
        layout.addWidget(icon_label)

        return row

    def _create_demographics_grid(self, data: dict) -> QWidget:
        """Create demographics grid with male/female breakdown (like in household_step)."""
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        grid = QGridLayout(container)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setSpacing(8)

        # Header row
        headers = ["الفئة", "ذكور", "إناث", "المجموع"]
        for col, header in enumerate(headers):
            lbl = QLabel(header)
            lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, 0, col)

        # Data rows
        rows = [
            ("البالغين", data.get('adult_male', 0), data.get('adult_female', 0)),
            ("القاصرين", data.get('minor_male', 0), data.get('minor_female', 0)),
            ("المسنين", data.get('elderly_male', 0), data.get('elderly_female', 0)),
            ("ذوي الاحتياجات", data.get('disabled_male', 0), data.get('disabled_female', 0)),
        ]

        for row_idx, (category, male, female) in enumerate(rows, start=1):
            total = male + female

            cat_lbl = QLabel(category)
            cat_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            cat_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
            cat_lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(cat_lbl, row_idx, 0)

            male_lbl = QLabel(str(male))
            male_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
            male_lbl.setStyleSheet(f"color: #3B82F6; background: transparent; border: none;")
            male_lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(male_lbl, row_idx, 1)

            female_lbl = QLabel(str(female))
            female_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
            female_lbl.setStyleSheet(f"color: #EC4899; background: transparent; border: none;")
            female_lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(female_lbl, row_idx, 2)

            total_lbl = QLabel(str(total))
            total_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_BOLD))
            total_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
            total_lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(total_lbl, row_idx, 3)

        return container

    def _create_status_bar(self, status: str, status_display: str) -> QWidget:
        """Create a status bar with colored indicator."""
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Status colors
        status_colors = {
            "new": "#22C55E",  # Green
            "under_review": "#F59E0B",  # Orange
            "completed": "#3B82F6",  # Blue
            "pending": "#EF4444",  # Red
            "draft": "#6B7280",  # Gray
        }

        color = status_colors.get(status, "#6B7280")

        # Status indicator
        indicator = QLabel()
        indicator.setFixedSize(12, 12)
        indicator.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
                border: none;
            }}
        """)

        # Status text
        status_label = QLabel(status_display)
        status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        status_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")

        layout.addStretch()
        layout.addWidget(status_label)
        layout.addWidget(indicator)

        return container

    # =========================================================================
    # Card Creation Methods
    # =========================================================================

    def _create_building_card(self) -> QFrame:
        """Create building information summary card (Step 1)."""
        card, content_layout = self._create_card_base("blue", "بيانات البناء", "معلومات البناء المختار")
        self.building_content = content_layout
        return card

    def _create_unit_card(self) -> QFrame:
        """Create unit information summary card (Step 2) - matching step 2 header."""
        card, content_layout = self._create_card_base("move", "اختر الوحدة العقارية", "اختر أو أضف معلومات الوحدة العقارية")
        self.unit_content = content_layout
        return card

    def _create_household_card(self) -> QFrame:
        """Create household information summary card (Step 3)."""
        card, content_layout = self._create_card_base("person-group", "تسجيل الأسرة", "بيانات الأسرة والتركيبة السكانية")
        self.household_content = content_layout
        return card

    def _create_persons_card(self) -> QFrame:
        """Create persons list summary card (Step 4)."""
        card, content_layout = self._create_card_base("user-account", "الأشخاص المسجلين", "قائمة الأشخاص في الوحدة")
        self.persons_content = content_layout
        return card

    def _create_relations_card(self) -> QFrame:
        """Create relations information summary card (Step 5)."""
        card, content_layout = self._create_card_base("elements", "العلاقات والأدلة", "علاقات الأشخاص بالوحدة")
        self.relations_content = content_layout
        return card

    def _create_claim_card(self) -> QFrame:
        """Create claim information summary card (Step 6)."""
        card, content_layout = self._create_card_base("clipboard-list", "حالة التسجيل", "بيانات الحالة والمطالبة")
        self.claim_content = content_layout
        return card

    def _clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _populate_review(self):
        """Populate all summary cards with data from context."""
        self._populate_building_card()
        self._populate_unit_card()
        self._populate_household_card()
        self._populate_persons_card()
        self._populate_relations_card()
        self._populate_claim_card()

    def _populate_building_card(self):
        """Populate building information card - matching Step 1 layout after selection."""
        self._clear_layout(self.building_content)

        if self.context.building:
            building = self.context.building
            building_code = str(building.building_id) if hasattr(building, 'building_id') else "-"
            address = building.address_path if hasattr(building, 'address_path') else "-"
            building_type = building.building_type_display if hasattr(building, 'building_type_display') else "-"
            status = building.status_display if hasattr(building, 'status_display') else "-"
            units_count = str(building.number_of_units) if hasattr(building, 'number_of_units') else "0"
            parcels_count = str(getattr(building, 'number_of_apartments', 0))
            shops_count = str(building.number_of_shops) if hasattr(building, 'number_of_shops') else "0"
            location_desc = getattr(building, 'location_description', 'وصف الموقع')
            general_desc = getattr(building, 'general_description', 'الوصف العام للموقع')

            # Row 1: Building code field
            code_field = self._create_field("رمز البناء", building_code)
            self.building_content.addWidget(code_field)

            # Row 2: Full address path with icon
            addr_container = QWidget()
            addr_container.setStyleSheet("background: transparent; border: none;")
            addr_layout = QHBoxLayout(addr_container)
            addr_layout.setContentsMargins(0, 0, 0, 0)
            addr_layout.setSpacing(8)

            # Address icon
            addr_icon = QLabel()
            addr_icon.setFixedSize(20, 20)
            addr_pixmap = Icon.load_pixmap("blue", size=16)
            if addr_pixmap and not addr_pixmap.isNull():
                addr_icon.setPixmap(addr_pixmap)
            addr_icon.setStyleSheet("background: transparent; border: none;")

            # Address text
            addr_label = QLabel(address)
            addr_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            addr_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
            addr_label.setAlignment(Qt.AlignRight)
            addr_label.setWordWrap(True)

            addr_layout.addStretch()
            addr_layout.addWidget(addr_label)
            addr_layout.addWidget(addr_icon)

            self.building_content.addWidget(addr_container)

            # Row 3: Stats row (5 sections like Step 1 - label on top, value below)
            stats = [
                {'value': status, 'label': 'حالة البناء'},
                {'value': building_type, 'label': 'نوع البناء'},
                {'value': units_count, 'label': 'عدد الوحدات'},
                {'value': parcels_count, 'label': 'عدد المقاسم'},
                {'value': shops_count, 'label': 'عدد المحلات'},
            ]
            stats_row = self._create_stat_row(stats, label_on_top=True, with_separators=False)
            self.building_content.addWidget(stats_row)

            # Row 4: Location section with header (like Step 1)
            location_container = QWidget()
            location_container.setStyleSheet(f"""
                QWidget {{
                    background-color: {Colors.INPUT_BG};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 8px;
                }}
            """)
            location_main_layout = QVBoxLayout(location_container)
            location_main_layout.setContentsMargins(12, 12, 12, 12)
            location_main_layout.setSpacing(12)

            # Header: "موقع البناء" (like Step 1)
            location_header = QLabel("موقع البناء")
            location_header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            location_header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            location_main_layout.addWidget(location_header)

            # Content row: Map + descriptions
            content_row = QHBoxLayout()
            content_row.setSpacing(24)

            # Map section
            map_container = QLabel()
            map_container.setFixedSize(200, 130)
            map_container.setAlignment(Qt.AlignCenter)
            map_container.setStyleSheet(f"""
                QLabel {{
                    background-color: #E8E8E8;
                    border-radius: 8px;
                    border: none;
                }}
            """)
            # Try to load map image
            map_pixmap = Icon.load_pixmap("image-40", size=None)
            if not map_pixmap or map_pixmap.isNull():
                map_pixmap = Icon.load_pixmap("map-placeholder", size=None)
            if map_pixmap and not map_pixmap.isNull():
                scaled_map = map_pixmap.scaled(200, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                map_container.setPixmap(scaled_map)
            else:
                # Fallback: location icon
                loc_pixmap = Icon.load_pixmap("carbon_location-filled", size=48)
                if loc_pixmap and not loc_pixmap.isNull():
                    map_container.setPixmap(loc_pixmap)

            content_row.addWidget(map_container)

            # Location description section
            loc_section = QVBoxLayout()
            loc_section.setSpacing(4)
            loc_label = QLabel("وصف الموقع")
            loc_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            loc_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            loc_value = QLabel(location_desc)
            loc_value.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            loc_value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            loc_value.setWordWrap(True)
            loc_section.addWidget(loc_label)
            loc_section.addWidget(loc_value)
            loc_section.addStretch()
            content_row.addLayout(loc_section, stretch=1)

            # General description section
            gen_section = QVBoxLayout()
            gen_section.setSpacing(4)
            gen_label = QLabel("الوصف العام")
            gen_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            gen_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            gen_value = QLabel(general_desc)
            gen_value.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            gen_value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            gen_value.setWordWrap(True)
            gen_section.addWidget(gen_label)
            gen_section.addWidget(gen_value)
            gen_section.addStretch()
            content_row.addLayout(gen_section, stretch=1)

            location_main_layout.addLayout(content_row)

            self.building_content.addWidget(location_container)
        else:
            no_data = QLabel("لم يتم اختيار مبنى")
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.building_content.addWidget(no_data)

    def _create_unit_stat_section(self, label_text: str, value_text: str = "-"):
        """Create a stat section matching step 3 unit card style (label top, value below, both centered)."""
        section = QWidget()
        section.setStyleSheet("background: transparent;")

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 0, 8, 0)
        section_layout.setSpacing(4)
        section_layout.setAlignment(Qt.AlignCenter)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        value = QLabel(value_text)
        value.setAlignment(Qt.AlignCenter)
        value.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        section_layout.addWidget(label)
        section_layout.addWidget(value)

        return section, value

    def _populate_unit_card(self):
        """Populate unit information card - same layout as step 3 unit info row."""
        self._clear_layout(self.unit_content)

        unit = self.context.unit
        new_unit_data = self.context.new_unit_data if self.context.is_new_unit else None

        if unit or new_unit_data:
            # Extract values
            if unit:
                unit_num = str(unit.unit_number or unit.apartment_number or "-")
                floor = str(unit.floor_number) if unit.floor_number is not None else "-"
                rooms = str(unit.apartment_number) if unit.apartment_number else "-"
                if unit.area_sqm:
                    try:
                        area = f"{float(unit.area_sqm):.2f} م²"
                    except (ValueError, TypeError):
                        area = "-"
                else:
                    area = "-"
                unit_type = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else "-"
                status_mappings = {
                    "occupied": "مشغولة", "vacant": "شاغرة", "unknown": "غير معروف"
                }
                status = status_mappings.get(getattr(unit, 'apartment_status', ''), getattr(unit, 'apartment_status', '-'))
            else:
                unit_num = str(new_unit_data.get('unit_number', 'جديد'))
                floor = str(new_unit_data.get('floor_number', '-'))
                rooms = str(new_unit_data.get('number_of_rooms', '-'))
                area_raw = new_unit_data.get('area_sqm')
                area = f"{float(area_raw):.2f} م²" if area_raw else "-"
                unit_type = new_unit_data.get('unit_type', '-')
                status = "جديد"

            # Build unit info container matching step 3 style
            unit_info_container = QFrame()
            unit_info_container.setFixedHeight(73)
            unit_info_container.setStyleSheet(f"""
                QFrame {{
                    background-color: #F8FAFF;
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 8px;
                }}
            """)

            unit_info_row = QHBoxLayout(unit_info_container)
            unit_info_row.setSpacing(0)
            unit_info_row.setContentsMargins(8, 8, 8, 8)

            # 6 sections in same order as step 2/3
            data_points = [
                ("رقم الوحدة", unit_num),
                ("رقم الطابق", floor),
                ("عدد الغرف", rooms),
                ("مساحة القسم", area),
                ("نوع الوحدة", unit_type),
                ("حالة الوحدة", status),
            ]

            for label_text, value_text in data_points:
                section, _ = self._create_unit_stat_section(label_text, value_text)
                unit_info_row.addWidget(section, stretch=1)

            self.unit_content.addWidget(unit_info_container)

            # وصف العقار section (matching step 2 unit card)
            desc_layout = QVBoxLayout()
            desc_layout.setContentsMargins(0, 0, 0, 0)
            desc_layout.setSpacing(2)

            desc_title = QLabel("وصف العقار")
            desc_title.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            desc_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
           # desc_title.setAlignment(Qt.AlignRight)

            desc_text_content = ""
            if unit and hasattr(unit, 'property_description') and unit.property_description:
                desc_text_content = unit.property_description
            elif new_unit_data and new_unit_data.get('property_description'):
                desc_text_content = new_unit_data.get('property_description')
            else:
                desc_text_content = "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة."

            desc_text = QLabel(desc_text_content)
            desc_text.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            desc_text.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
           # desc_text.setAlignment(Qt.AlignRight)
            desc_text.setWordWrap(True)
            desc_text.setMaximumHeight(40)

            desc_layout.addWidget(desc_title)
            desc_layout.addWidget(desc_text)

            desc_widget = QWidget()
            desc_widget.setStyleSheet("background: transparent; border: none;")
            desc_widget.setLayout(desc_layout)
            self.unit_content.addWidget(desc_widget)
        else:
            no_data = QLabel("لم يتم اختيار وحدة")
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.unit_content.addWidget(no_data)

    def _populate_household_card(self):
        """Populate household information card."""
        self._clear_layout(self.household_content)

        if not self.context.households:
            no_data = QLabel("لم يتم تسجيل أي أسرة")
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.household_content.addWidget(no_data)
            return

        # Aggregate data from all households
        total_size = sum(h.get('size', 0) for h in self.context.households)
        head_name = self.context.households[0].get('head_name', '-') if self.context.households else "-"

        # Header info row
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        # Family count stat
        count_stat = self._create_stat_item(str(len(self.context.households)), "عدد الأسر", "#3B82F6")
        size_stat = self._create_stat_item(str(total_size), "إجمالي الأفراد", "#22C55E")

        # Head name
        head_container = QWidget()
        head_container.setStyleSheet("background: transparent; border: none;")
        head_layout = QVBoxLayout(head_container)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(4)

        head_label = QLabel("رب الأسرة")
        head_label.setFont(create_font(size=9))
        head_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        head_label.setAlignment(Qt.AlignRight)

        head_value = QLabel(head_name)
        head_value.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        head_value.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        head_value.setAlignment(Qt.AlignRight)

        head_layout.addWidget(head_label)
        head_layout.addWidget(head_value)

        header_layout.addWidget(count_stat)
        header_layout.addWidget(size_stat)
        header_layout.addStretch()
        header_layout.addWidget(head_container)

        self.household_content.addWidget(header_container)

        # Demographics grid
        demographics = {}
        for h in self.context.households:
            for key in ['adult_male', 'adult_female', 'minor_male', 'minor_female',
                        'elderly_male', 'elderly_female', 'disabled_male', 'disabled_female']:
                demographics[key] = demographics.get(key, 0) + h.get(key, 0)

        demographics_grid = self._create_demographics_grid(demographics)
        self.household_content.addWidget(demographics_grid)

    def _populate_persons_card(self):
        """Populate persons list card."""
        self._clear_layout(self.persons_content)

        if not self.context.persons:
            no_data = QLabel("لم يتم تسجيل أي أشخاص")
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.persons_content.addWidget(no_data)
            return

        # Persons count header
        count_label = QLabel(f"عدد الأشخاص: {len(self.context.persons)}")
        count_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        count_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        count_label.setAlignment(Qt.AlignRight)
        self.persons_content.addWidget(count_label)

        # Person rows
        role_map = {
            "head": "رب الأسرة",
            "spouse": "الزوج/ة",
            "child": "ابن/ابنة",
            "relative": "قريب",
            "tenant": "مستأجر",
            "worker": "عامل",
            "other": "آخر"
        }

        for person in self.context.persons:
            name = person.get('full_name', person.get('name', '-'))
            role = role_map.get(person.get('role', ''), person.get('role', '-'))
            row = self._create_person_row(name, role)
            self.persons_content.addWidget(row)

    def _populate_relations_card(self):
        """Populate relations information card."""
        self._clear_layout(self.relations_content)

        if not self.context.relations:
            no_data = QLabel("لم يتم تسجيل أي علاقات")
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.relations_content.addWidget(no_data)
            return

        rel_type_map = {
            "owner": "مالك",
            "co_owner": "شريك",
            "tenant": "مستأجر",
            "occupant": "شاغل",
            "heir": "وارث"
        }

        # Stats row
        num_relations = len(self.context.relations)
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)
        owners = len([r for r in self.context.relations if r.get('relation_type') in ('owner', 'co_owner')])
        tenants = len([r for r in self.context.relations if r.get('relation_type') == 'tenant'])

        stats = [
            {'value': str(num_relations), 'label': 'عدد العلاقات', 'color': '#3B82F6'},
            {'value': str(total_evidences), 'label': 'الوثائق'},
            {'value': str(owners), 'label': 'الملاك'},
            {'value': str(tenants), 'label': 'المستأجرين'},
        ]
        stats_row = self._create_stat_row(stats)
        self.relations_content.addWidget(stats_row)

        # Relations list
        for relation in self.context.relations:
            person_name = relation.get('person_name', '-')
            relation_type = rel_type_map.get(relation.get('relation_type', ''), '-')
            row = self._create_person_row(person_name, relation_type, "elements")
            self.relations_content.addWidget(row)

    def _populate_claim_card(self):
        """Populate claim information card."""
        self._clear_layout(self.claim_content)

        if not self.context.claim_data:
            no_data = QLabel("لم يتم إنشاء مطالبة")
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.claim_content.addWidget(no_data)
            return

        claim_types = {
            "ownership": "ملكية",
            "occupancy": "إشغال",
            "tenancy": "إيجار"
        }
        priorities = {
            "low": "منخفض",
            "normal": "عادي",
            "high": "عالي",
            "urgent": "عاجل"
        }
        business_types = {
            "residential": "سكني",
            "commercial": "تجاري",
            "agricultural": "زراعي"
        }
        sources = {
            "field_survey": "مسح ميداني",
            "direct_request": "طلب مباشر",
            "referral": "إحالة",
            "OFFICE_SUBMISSION": "تقديم مكتبي"
        }
        statuses = {
            "new": "جديد",
            "under_review": "قيد المراجعة",
            "completed": "مكتمل",
            "pending": "معلق",
            "draft": "مسودة"
        }

        claim_data = self.context.claim_data
        status_key = claim_data.get('case_status', 'new')
        status_display = statuses.get(status_key, status_key)

        # Status bar at top
        status_bar = self._create_status_bar(status_key, status_display)
        self.claim_content.addWidget(status_bar)

        # Fields grid
        fields_container = QWidget()
        fields_container.setStyleSheet("background: transparent; border: none;")
        fields_grid = QGridLayout(fields_container)
        fields_grid.setContentsMargins(0, 0, 0, 0)
        fields_grid.setHorizontalSpacing(12)
        fields_grid.setVerticalSpacing(12)

        claim_type = claim_types.get(claim_data.get('claim_type'), '-')
        priority = priorities.get(claim_data.get('priority'), '-')
        business = business_types.get(claim_data.get('business_nature'), '-')
        source = sources.get(claim_data.get('source'), '-')
        survey_date = str(claim_data.get('survey_date', '-') or '-')

        # Row 1
        fields_grid.addWidget(self._create_field("نوع الحالة", claim_type), 0, 0)
        fields_grid.addWidget(self._create_field("طبيعة الأعمال", business), 0, 1)
        fields_grid.addWidget(self._create_field("الأولوية", priority), 0, 2)
        fields_grid.addWidget(self._create_field("المصدر", source), 0, 3)

        # Row 2
        fields_grid.addWidget(self._create_field("تاريخ المسح", survey_date), 1, 0, 1, 2)

        self.claim_content.addWidget(fields_container)

    def validate(self) -> StepValidationResult:
        """Validate that all required data is present."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error("لا يوجد مبنى مختار")
        if not self.context.unit and not self.context.is_new_unit:
            result.add_error("لا يوجد وحدة مختارة")
        if len(self.context.persons) == 0:
            result.add_error("لا يوجد أشخاص مسجلين")

        return result

    def collect_data(self) -> Dict[str, Any]:
        return self.context.get_summary()

    def on_next(self):
        """Called when user clicks Next/Submit button. Finalize the survey via API if not already done."""
        # Skip finalize if already done in Step 5 (RelationStep)
        if hasattr(self.context, 'finalize_response') and self.context.finalize_response:
            logger.info("Survey already finalized in Step 5, skipping duplicate finalize")
            return

        if self._use_api:
            self._finalize_survey_via_api()

    def _finalize_survey_via_api(self):
        """Finalize the survey by calling the API."""
        # Set auth token
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._api_service.set_auth_token(main_window._api_token)

        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            logger.error("No survey_id found in context. Cannot finalize.")
            QMessageBox.critical(
                self,
                "خطأ",
                "لم يتم العثور على معرف المسح. لا يمكن إنهاء المسح."
            )
            return

        logger.info(f"Finalizing survey {survey_id}")

        # Prepare finalization options
        finalize_options = {
            "finalNotes": "Survey completed successfully",
            "durationMinutes": 0,  # Could calculate from survey start time
            "autoCreateClaim": True
        }

        # Call the finalize API
        response = self._api_service.finalize_office_survey(survey_id, finalize_options)

        if response.get("success"):
            logger.info(f"Survey {survey_id} finalized successfully")
            QMessageBox.information(
                self,
                "نجح",
                "تم إنهاء المسح بنجاح!"
            )
        else:
            error_msg = response.get("error", "Unknown error")
            error_details = response.get("details", "")
            logger.error(f"Failed to finalize survey: {error_msg}")
            logger.error(f"Error details: {error_details}")

            full_error = f"فشل في إنهاء المسح:\n\n{error_msg}"
            if error_details:
                # Truncate long error messages
                if len(error_details) > 300:
                    error_details = error_details[:300] + "..."
                full_error += f"\n\nتفاصيل: {error_details}"

            QMessageBox.critical(
                self,
                "خطأ",
                full_error
            )

    def on_show(self):
        """Refresh summary when step is shown."""
        super().on_show()
        self._populate_review()

    def get_step_title(self) -> str:
        return "المراجعة النهائية"

    def get_step_description(self) -> str:
        return "راجع جميع البيانات المدخلة قبل الإرسال"
