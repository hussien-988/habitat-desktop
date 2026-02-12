# -*- coding: utf-8 -*-
"""
Review Step - Step 7 of Office Survey Wizard.

Final review and submission step - displays summary cards from all previous steps.
"""

from typing import Dict, Any
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
    QHBoxLayout, QGridLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.error_handler import ErrorHandler
from ui.design_system import Colors
from ui.font_utils import FontManager, create_font
from ui.components.icon import Icon
from utils.logger import get_logger
from app.config import Config
from services.api_client import get_api_client
from services.translation_manager import tr
from services.error_mapper import map_exception
from services.display_mappings import (
    get_relation_type_display, get_unit_status_display,
    get_claim_type_display, get_priority_display,
    get_business_type_display, get_source_display,
    get_claim_status_display
)

logger = get_logger(__name__)


class ReviewStep(BaseStep):
    """Step 7: Review & Submit."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

        # Initialize API service for finalizing survey
        self._api_service = get_api_client()
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

        # Icon container (circular, light blue background)
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #e8f4fd;
                border: 1px solid #d0e8f7;
                border-radius: 24px;
            }
        """)

        icon_pixmap = Icon.load_pixmap(icon_name, size=28)
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

    def _create_person_row(self, person: dict) -> QWidget:
        """Create a person row card matching step 4 layout."""
        row = QFrame()
        row.setLayoutDirection(Qt.RightToLeft)
        row.setFixedHeight(80)
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
            }}
        """)

        card_layout = QHBoxLayout(row)
        card_layout.setContentsMargins(15, 0, 15, 0)

        # Right side: Icon + Text
        right_group = QHBoxLayout()
        right_group.setSpacing(12)

        # Circular icon
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #F4F8FF;
                color: #3182CE;
                border-radius: 18px;
                border: none;
            }
        """)
        user_pixmap = Icon.load_pixmap("user", size=20)
        if user_pixmap and not user_pixmap.isNull():
            icon_lbl.setPixmap(user_pixmap)

        # Name and role
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        full_name = f"{person.get('first_name', '')} {person.get('father_name', '')} {person.get('last_name', '')}".strip()
        if not full_name:
            full_name = person.get('full_name', person.get('name', '-'))
        name_lbl = QLabel(full_name)
        name_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        name_lbl.setAlignment(Qt.AlignRight)

        role_key = person.get('relationship_type', person.get('role', ''))
        role_text = get_relation_type_display(role_key) if role_key else get_relation_type_display('occupant')
        role_lbl = QLabel(role_text)
        role_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        role_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        text_vbox.addWidget(name_lbl)
        text_vbox.addWidget(role_lbl)

        right_group.addWidget(icon_lbl)
        right_group.addLayout(text_vbox)

        # Left side: "عرض المعلومات الشخصية" link
        view_lbl = QLabel(tr("wizard.review.view_personal_info"))
        view_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        view_lbl.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
        view_lbl.setCursor(Qt.PointingHandCursor)

        card_layout.addLayout(right_group)
        card_layout.addStretch()
        card_layout.addWidget(view_lbl)

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
        headers = [tr("wizard.review.demographics_category"), tr("wizard.review.demographics_male"), tr("wizard.review.demographics_female"), tr("wizard.review.demographics_total")]
        for col, header in enumerate(headers):
            lbl = QLabel(header)
            lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, 0, col)

        # Data rows
        rows = [
            (tr("wizard.review.demographics_adults"), data.get('adult_male', 0), data.get('adult_female', 0)),
            (tr("wizard.review.demographics_children"), data.get('minor_male', 0), data.get('minor_female', 0)),
            (tr("wizard.review.demographics_elderly"), data.get('elderly_male', 0), data.get('elderly_female', 0)),
            (tr("wizard.review.demographics_disabled"), data.get('disabled_male', 0), data.get('disabled_female', 0)),
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
        card, content_layout = self._create_card_base("blue", tr("wizard.review.building_card_title"), tr("wizard.review.building_card_subtitle"))
        self.building_content = content_layout
        return card

    def _create_unit_card(self) -> QFrame:
        """Create unit information summary card (Step 2) - matching step 2 header."""
        card, content_layout = self._create_card_base("move", tr("wizard.review.unit_card_title"), tr("wizard.review.unit_card_subtitle"))
        self.unit_content = content_layout
        return card

    def _create_household_card(self) -> QFrame:
        """Create household information summary card (Step 3)."""
        card, content_layout = self._create_card_base("user-group", tr("wizard.review.household_card_title"), tr("wizard.review.household_card_subtitle"))
        self.household_content = content_layout
        return card

    def _create_persons_card(self) -> QFrame:
        """Create persons list summary card (Step 4)."""
        card, content_layout = self._create_card_base("user-account", tr("wizard.review.persons_card_title"), tr("wizard.review.persons_card_subtitle"))
        self.persons_content = content_layout
        return card

    def _create_relations_card(self) -> QFrame:
        """Create relations information summary card (Step 5)."""
        card, content_layout = self._create_card_base("user-account", tr("wizard.review.relations_card_title"), tr("wizard.review.relations_card_subtitle"))
        self.relations_content = content_layout
        return card

    def _create_claim_card(self) -> QFrame:
        """Create claim information summary card (Step 6)."""
        card, content_layout = self._create_card_base("elements", tr("wizard.review.claim_card_title"), tr("wizard.review.claim_card_subtitle"))
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
            location_desc = getattr(building, 'location_description', tr("wizard.building.location_description"))
            general_desc = getattr(building, 'general_description', tr("wizard.building.general_description_fallback"))

            # Row 1: Building code field
            code_field = self._create_field(tr("wizard.review.building_code"), building_code)
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
                {'value': status, 'label': tr("wizard.building.status")},
                {'value': building_type, 'label': tr("wizard.building.type")},
                {'value': units_count, 'label': tr("wizard.building.units_count")},
                {'value': parcels_count, 'label': tr("wizard.building.parcels_count")},
                {'value': shops_count, 'label': tr("wizard.building.shops_count")},
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
            location_header = QLabel(tr("wizard.building.location"))
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
            loc_label = QLabel(tr("wizard.building.location_description"))
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
            gen_label = QLabel(tr("wizard.building.general_description"))
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
            no_data = QLabel(tr("wizard.building.not_selected"))
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
                        area = tr("wizard.unit.area_format", value=f"{float(unit.area_sqm):.2f}")
                    except (ValueError, TypeError):
                        area = "-"
                else:
                    area = "-"
                unit_type = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else "-"
                status_raw = getattr(unit, 'apartment_status', None)
                if status_raw is not None:
                    status = get_unit_status_display(status_raw)
                else:
                    status = "-"
            else:
                unit_num = str(new_unit_data.get('unit_number', tr("wizard.review.new_unit")))
                floor = str(new_unit_data.get('floor_number', '-'))
                rooms = str(new_unit_data.get('number_of_rooms', '-'))
                area_raw = new_unit_data.get('area_sqm')
                area = tr("wizard.unit.area_format", value=f"{float(area_raw):.2f}") if area_raw else "-"
                unit_type = new_unit_data.get('unit_type', '-')
                status = tr("wizard.review.new_unit")

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
                (tr("wizard.unit.number"), unit_num),
                (tr("wizard.unit.floor_number"), floor),
                (tr("wizard.unit.rooms_count"), rooms),
                (tr("wizard.unit.area"), area),
                (tr("wizard.unit.type"), unit_type),
                (tr("wizard.unit.status"), status),
            ]

            for label_text, value_text in data_points:
                section, _ = self._create_unit_stat_section(label_text, value_text)
                unit_info_row.addWidget(section, stretch=1)

            self.unit_content.addWidget(unit_info_container)

            # وصف العقار section (matching step 2 unit card)
            desc_layout = QVBoxLayout()
            desc_layout.setContentsMargins(0, 0, 0, 0)
            desc_layout.setSpacing(2)

            desc_title = QLabel(tr("wizard.unit.property_description"))
            desc_title.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            desc_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
           # desc_title.setAlignment(Qt.AlignRight)

            desc_text_content = ""
            if unit and hasattr(unit, 'property_description') and unit.property_description:
                desc_text_content = unit.property_description
            elif new_unit_data and new_unit_data.get('property_description'):
                desc_text_content = new_unit_data.get('property_description')
            else:
                desc_text_content = tr("wizard.unit.property_description_placeholder")

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
            no_data = QLabel(tr("wizard.unit.not_selected"))
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.unit_content.addWidget(no_data)

    def _create_demographic_card(self, items: list) -> QFrame:
        """Create a demographic data card with label/value rows and separators."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(18)

        ALIGN_ABS_RIGHT = Qt.AlignRight | Qt.AlignAbsolute

        for i, (text, value) in enumerate(items):
            item_block = QVBoxLayout()
            item_block.setSpacing(4)

            txt_lbl = QLabel(text)
            txt_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            txt_lbl.setStyleSheet(f"color: #1e293b; background: transparent; border: none;")
            txt_lbl.setAlignment(ALIGN_ABS_RIGHT)

            val_lbl = QLabel(str(value))
            val_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            val_lbl.setStyleSheet(f"color: #94a3b8; background: transparent; border: none;")
            val_lbl.setAlignment(ALIGN_ABS_RIGHT)

            item_block.addWidget(txt_lbl)
            item_block.addWidget(val_lbl)
            card_layout.addLayout(item_block)

            if i < len(items) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet(f"background-color: #f1f5f9; border: none;")
                card_layout.addWidget(separator)

        return frame

    def _populate_household_card(self):
        """Populate household information card - matching screenshot layout."""
        self._clear_layout(self.household_content)

        if not self.context.households:
            no_data = QLabel(tr("wizard.household.no_data"))
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.household_content.addWidget(no_data)
            return

        # Aggregate data from all households
        total_size = sum(h.get('size', 0) for h in self.context.households)
        head_name = self.context.households[0].get('head_name', '-') if self.context.households else "-"

        # --- Summary Row: Head name (right) + Member count (center) ---
        summary_container = QWidget()
        summary_container.setStyleSheet("background: transparent; border: none;")
        summary_layout = QHBoxLayout(summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)

        # Right block: head of household name
        name_block = QVBoxLayout()
        name_block.setSpacing(4)
        name_title = QLabel(tr("wizard.household.head_name"))
        name_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        name_title.setStyleSheet(f"color: #1e293b; background: transparent; border: none;")
        name_title.setAlignment(Qt.AlignRight)
        name_val = QLabel(head_name)
        name_val.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        name_val.setStyleSheet(f"color: #94a3b8; background: transparent; border: none;")
        name_val.setAlignment(Qt.AlignRight)
        name_block.addWidget(name_title)
        name_block.addWidget(name_val)

        # Center block: member count
        count_block = QVBoxLayout()
        count_block.setSpacing(4)
        count_title = QLabel(tr("wizard.household.family_size"))
        count_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        count_title.setStyleSheet(f"color: #1e293b; background: transparent; border: none;")
        count_title.setAlignment(Qt.AlignCenter)
        count_val = QLabel(str(total_size))
        count_val.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        count_val.setStyleSheet(f"color: #94a3b8; background: transparent; border: none;")
        count_val.setAlignment(Qt.AlignCenter)
        count_block.addWidget(count_title)
        count_block.addWidget(count_val)

        summary_layout.addLayout(name_block)
        summary_layout.addStretch()
        summary_layout.addLayout(count_block)
        summary_layout.addStretch()

        self.household_content.addWidget(summary_container)

        # --- Aggregate demographics ---
        demographics = {}
        for h in self.context.households:
            for key in ['adult_male', 'adult_female', 'minor_male', 'minor_female',
                        'elderly_male', 'elderly_female', 'disabled_male', 'disabled_female']:
                demographics[key] = demographics.get(key, 0) + h.get(key, 0)

        # --- Two cards side by side: Males (right) + Females (left) ---
        male_items = [
            (tr("wizard.household.adult_males"), demographics.get('adult_male', 0)),
            (tr("wizard.household.male_children"), demographics.get('minor_male', 0)),
            (tr("wizard.household.male_elderly"), demographics.get('elderly_male', 0)),
            (tr("wizard.household.disabled_males"), demographics.get('disabled_male', 0)),
        ]

        female_items = [
            (tr("wizard.household.adult_females"), demographics.get('adult_female', 0)),
            (tr("wizard.household.female_children"), demographics.get('minor_female', 0)),
            (tr("wizard.household.female_elderly"), demographics.get('elderly_female', 0)),
            (tr("wizard.household.disabled_females"), demographics.get('disabled_female', 0)),
        ]

        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent; border: none;")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(20)

        cards_layout.addWidget(self._create_demographic_card(male_items))
        cards_layout.addWidget(self._create_demographic_card(female_items))

        self.household_content.addWidget(cards_container)

    def _populate_persons_card(self):
        """Populate persons list card matching step 4 layout."""
        self._clear_layout(self.persons_content)

        if not self.context.persons:
            no_data = QLabel(tr("wizard.person.no_persons"))
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.persons_content.addWidget(no_data)
            return

        self.persons_content.setSpacing(10)

        for person in self.context.persons:
            row = self._create_person_row(person)
            self.persons_content.addWidget(row)

    def _create_relation_person_card(self, relation: dict) -> QFrame:
        """Create a read-only relation card for a person, matching step 5 layout."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(12)

        # --- Person header: icon + name + role ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #F4F8FF;
                border-radius: 19px;
                border: 1px solid #d1e3f8;
            }
        """)
        person_icon = Icon.load_pixmap("user", size=20)
        if person_icon and not person_icon.isNull():
            icon_label.setPixmap(person_icon)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(0)

        person_name = relation.get('person_name', '-')
        name_label = QLabel(person_name)
        name_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        name_label.setStyleSheet(f"color: #2c3e50; background: transparent;")

        role_text = get_relation_type_display(relation.get('relation_type', '')) if relation.get('relation_type') else '-'
        role_label = QLabel(role_text)
        role_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        role_label.setStyleSheet("color: #7f8c8d; background: transparent;")

        text_vbox.addWidget(name_label)
        text_vbox.addWidget(role_label)

        header_layout.addWidget(icon_label)
        header_layout.addLayout(text_vbox)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # --- Form fields (read-only) in grid ---
        label_style = "color: #333; font-size: 12px; font-weight: 600; background: transparent;"
        value_style = f"""
            QLabel {{
                background-color: #ffffff;
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                padding: 8px 12px;
                color: #2d3436;
                font-size: 12px;
            }}
        """

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        # Row 0 - Labels
        lbl_contract = QLabel(tr("wizard.relation.contract_type"))
        lbl_contract.setStyleSheet(label_style)
        grid.addWidget(lbl_contract, 0, 0)

        lbl_date = QLabel(tr("wizard.relation.start_date"))
        lbl_date.setStyleSheet(label_style)
        grid.addWidget(lbl_date, 0, 1)

        lbl_share = QLabel(tr("wizard.relation.ownership_share"))
        lbl_share.setStyleSheet(label_style)
        grid.addWidget(lbl_share, 0, 2)

        # Row 1 - Values
        contract_val = QLabel(relation.get('contract_type') or "-")
        contract_val.setStyleSheet(value_style)
        grid.addWidget(contract_val, 1, 0)

        date_val = QLabel(relation.get('start_date') or "-")
        date_val.setStyleSheet(value_style)
        grid.addWidget(date_val, 1, 1)

        share = relation.get('ownership_share', 0)
        share_val = QLabel(f"{share} %")
        share_val.setStyleSheet(value_style)
        grid.addWidget(share_val, 1, 2)

        card_layout.addLayout(grid)

        # --- Notes ---
        notes_text = relation.get('notes')
        if notes_text:
            notes_title = QLabel(tr("wizard.relation.notes_label"))
            notes_title.setStyleSheet(label_style)
            card_layout.addWidget(notes_title)

            notes_val = QLabel(notes_text)
            notes_val.setWordWrap(True)
            notes_val.setStyleSheet(value_style)
            card_layout.addWidget(notes_val)

        # --- Evidence ---
        evidence_type = relation.get('evidence_type')
        evidence_desc = relation.get('evidence_description')
        if evidence_type or evidence_desc:
            docs_title = QLabel(tr("wizard.relation.documents_label"))
            docs_title.setStyleSheet(label_style)
            card_layout.addWidget(docs_title)

            doc_text = evidence_type or ""
            if evidence_desc:
                doc_text += f" - {evidence_desc}" if doc_text else evidence_desc
            docs_val = QLabel(doc_text)
            docs_val.setStyleSheet(value_style)
            card_layout.addWidget(docs_val)

        return card

    def _populate_relations_card(self):
        """Populate relations card matching step 5 layout - one card per person."""
        self._clear_layout(self.relations_content)

        if not self.context.relations:
            no_data = QLabel(tr("wizard.relation.no_relations"))
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.relations_content.addWidget(no_data)
            return

        self.relations_content.setSpacing(10)

        for relation in self.context.relations:
            card = self._create_relation_person_card(relation)
            self.relations_content.addWidget(card)

    def _create_claim_data_card(self, claim_data: dict) -> QFrame:
        """Create a single read-only claim card matching step 6 layout."""
        # Use display_mappings for DRY translations

        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(12)

        label_style = f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;"
        value_style = f"""
            QLabel {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 12px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """

        # --- Grid: Row 1 & 2 ---
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for i in range(4):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, value_text, row, col):
            v = QVBoxLayout()
            v.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            lbl.setStyleSheet(label_style)
            v.addWidget(lbl)
            val = QLabel(str(value_text) if value_text else "-")
            val.setStyleSheet(value_style)
            v.addWidget(val)
            grid.addLayout(v, row, col)

        # Claimant name - use per-card person_name first
        claimant_name = claim_data.get('person_name', '').strip()
        if not claimant_name:
            claimant_ids = claim_data.get('claimant_person_ids', [])
            if claimant_ids and self.context.persons:
                for p in self.context.persons:
                    if p.get('person_id') in claimant_ids:
                        claimant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
                        break
            if not claimant_name and self.context.persons:
                p = self.context.persons[0]
                claimant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
        if not claimant_name:
            claimant_name = "-"

        # Unit display ID - use per-card value first
        unit_display = claim_data.get('unit_display_id', '').strip()
        if not unit_display:
            unit_display = claim_data.get('unit_id', '-') or "-"

        add_field(tr("wizard.review.claimant_id"), claimant_name, 0, 0)
        add_field(tr("wizard.review.unit_claim_id"), unit_display, 0, 1)
        add_field(tr("wizard.review.claim_type"), get_claim_type_display(claim_data.get('claim_type', '')), 0, 2)
        add_field(tr("wizard.review.business_nature"), get_business_type_display(claim_data.get('business_nature', '')), 0, 3)

        add_field(tr("wizard.review.case_status"), get_claim_status_display(claim_data.get('case_status', 'new')), 1, 0)
        add_field(tr("wizard.review.source"), get_source_display(claim_data.get('source', '')), 1, 1)
        add_field(tr("wizard.review.survey_date"), str(claim_data.get('survey_date', '-') or '-'), 1, 2)
        add_field(tr("wizard.review.priority"), get_priority_display(claim_data.get('priority', '')), 1, 3)

        card_layout.addLayout(grid)

        # --- Notes ---
        notes_text = claim_data.get('notes', '')
        notes_title = QLabel(tr("wizard.review.review_notes"))
        notes_title.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        notes_title.setStyleSheet(label_style)
        card_layout.addWidget(notes_title)

        notes_val = QLabel(notes_text if notes_text else tr("wizard.review.review_notes_placeholder"))
        notes_val.setWordWrap(True)
        notes_val.setMinimumHeight(60)
        notes_val.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 12px;
                color: {Colors.TEXT_SECONDARY if not notes_text else Colors.TEXT_PRIMARY};
                font-size: 13px;
            }}
        """)
        card_layout.addWidget(notes_val)

        # --- Next Action Date ---
        next_date_title = QLabel(tr("wizard.review.next_action_date"))
        next_date_title.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        next_date_title.setStyleSheet(label_style)
        card_layout.addWidget(next_date_title)

        next_date = claim_data.get('next_action_date', '00-00-0000') or '00-00-0000'
        next_date_val = QLabel(next_date)
        next_date_val.setStyleSheet(value_style)
        card_layout.addWidget(next_date_val)

        # --- Evidence Status Bar ---
        eval_label = QLabel()
        eval_label.setAlignment(Qt.AlignCenter)
        eval_label.setFixedHeight(50)
        eval_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        eval_label.setText(f"  \u2714  {tr('wizard.review.evidence_available')}")
        eval_label.setStyleSheet("""
            QLabel {
                background-color: #e1f7ef;
                color: #10b981;
                border-radius: 8px;
            }
        """)
        card_layout.addWidget(eval_label)

        return card

    def _populate_claim_card(self):
        """Populate claim information card - show all claims from step 6."""
        self._clear_layout(self.claim_content)

        # Use claims list (all claims), fallback to single claim_data
        claims = getattr(self.context, 'claims', [])
        if not claims and self.context.claim_data:
            claims = [self.context.claim_data]

        if not claims:
            no_data = QLabel(tr("wizard.review.no_claim"))
            no_data.setFont(create_font(size=10))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.claim_content.addWidget(no_data)
            return

        self.claim_content.setSpacing(10)

        for claim_data in claims:
            claim_card = self._create_claim_data_card(claim_data)
            self.claim_content.addWidget(claim_card)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts by rebuilding review content."""
        self._populate_review()

    def validate(self) -> StepValidationResult:
        """Validate that all required data is present."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error(tr("wizard.review.no_building"))
        if not self.context.unit and not self.context.is_new_unit:
            result.add_error(tr("wizard.review.no_unit"))
        if len(self.context.persons) == 0:
            result.add_error(tr("wizard.review.no_persons"))

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
            self._api_service.set_access_token(main_window._api_token)

        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            logger.error("No survey_id found in context. Cannot finalize.")
            ErrorHandler.show_error(
                self,
                tr("wizard.review.no_survey_id"),
                tr("common.error")
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
        try:
            response = self._api_service.finalize_office_survey(survey_id, finalize_options)

            logger.info(f"Survey {survey_id} finalized successfully")
            ErrorHandler.show_success(
                self,
                tr("wizard.review.finalize_success"),
                tr("common.success")
            )

        except Exception as e:
            logger.error(f"Failed to finalize survey: {e}")

            ErrorHandler.show_error(
                self,
                tr("wizard.review.finalize_error", error_msg=map_exception(e)),
                tr("common.error")
            )

    def on_show(self):
        """Refresh summary when step is shown."""
        super().on_show()
        self._populate_review()

    def get_step_title(self) -> str:
        return tr("wizard.review.step_title")

    def get_step_description(self) -> str:
        return tr("wizard.review.step_description")
