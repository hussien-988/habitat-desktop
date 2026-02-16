# -*- coding: utf-8 -*-
"""
Household Step - Step 3 of Office Survey Wizard.

Allows user to:
- Enter household information
- Record family composition (adults, children, elderly, disabled)
- Add notes about the household
"""

from typing import Dict, Any, Optional
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QWidget, QGroupBox,
    QSpinBox, QTextEdit, QGridLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QColor

from ui.components.rtl_combo import RtlCombo
from ui.components.centered_text_edit import CenteredTextEdit
from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from services.api_client import get_api_client
from utils.logger import get_logger
from ui.design_system import Colors
from ui.components.icon import Icon
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr
from services.display_mappings import get_unit_type_display, get_unit_status_display, get_occupancy_type_options, get_occupancy_nature_options
from services.error_mapper import map_exception

logger = get_logger(__name__)


class HouseholdStep(BaseStep):
    """
    Step 3: Household Information.

    Collects household demographic information including:
    - Head of household
    - Total members
    - Family composition (adults, children, elderly, disabled)
    - Notes
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)

        # Initialize API client for creating households
        self._api_client = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        widget = self
        layout = self.main_layout
        # No horizontal padding - wizard applies 131px (DRY principle)
        # Only vertical spacing between elements
        layout.setContentsMargins(0, 16, 0, 16)  # Top: 16px, Bottom: 16px
        layout.setSpacing(8)

        # Selected building info card - same design as unit_selection_step
        # Height: 198px (changed from 113px)
        self.household_building_frame = QFrame()
        self.household_building_frame.setObjectName("householdBuildingInfoCard")
        self.household_building_frame.setFixedHeight(198)  # Fixed height as requested
        self.household_building_frame.setStyleSheet(f"""
            QFrame#householdBuildingInfoCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)

        # Apply subtle shadow effect for visual separation
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.household_building_frame.setGraphicsEffect(shadow)

        # Main card layout
        card_layout = QVBoxLayout(self.household_building_frame)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        # ===== ROW 1: Building Address =====
        address_container = QFrame()
        address_container.setFixedHeight(28)
        address_container.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: none;
                border-radius: 8px;
            }
        """)

        address_row = QHBoxLayout(address_container)
        address_row.setContentsMargins(12, 0, 12, 0)
        address_row.setSpacing(8)

        # Center the content
        address_row.addStretch()

        # Icon: dec.png
        address_icon = QLabel()
        address_icon_pixmap = Icon.load_pixmap("dec", size=16)
        if address_icon_pixmap and not address_icon_pixmap.isNull():
            address_icon.setPixmap(address_icon_pixmap)
        else:
            address_icon.setText("📍")  # Fallback emoji
        address_icon.setStyleSheet("background: transparent; border: none;")
        address_row.addWidget(address_icon)

        # Building address text
        self.household_building_address = QLabel(tr("wizard.unit.address_label"))
        self.household_building_address.setAlignment(Qt.AlignCenter)
        self.household_building_address.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        self.household_building_address.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
                color: #667281;
            }
        """)
        address_row.addWidget(self.household_building_address)

        # Center the content
        address_row.addStretch()

        card_layout.addWidget(address_container)

        # ===== ROW 2: Building Stats (5 sections) =====
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)

        # Create 5 stat sections (DRY: using helper method)
        section_type, self.ui_building_type = self._create_stat_section(tr("wizard.building.type"))
        section_status, self.ui_building_status = self._create_stat_section(tr("wizard.building.status"))
        section_units, self.ui_units_count = self._create_stat_section(tr("wizard.building.units_count"))
        section_parcels, self.ui_parcels_count = self._create_stat_section(tr("wizard.building.parcels_count"))
        section_shops, self.ui_shops_count = self._create_stat_section(tr("wizard.building.shops_count"))

        # Add sections with equal spacing
        sections = [section_type, section_status, section_units, section_parcels, section_shops]
        for section in sections:
            stats_row.addWidget(section, stretch=1)

        card_layout.addLayout(stats_row)

        # ===== ROW 3: Unit Information (6 sections) =====
        # Same order as unit_selection_step unit cards
        unit_info_container = QFrame()
        unit_info_container.setFixedHeight(73)
        unit_info_container.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: none;
                border-radius: 8px;
            }
        """)

        unit_info_row = QHBoxLayout(unit_info_container)
        unit_info_row.setSpacing(0)
        unit_info_row.setContentsMargins(8, 8, 8, 8)  # Add padding inside container

        # Create 6 unit info sections - SAME labels as unit_selection_step cards
        section_unit_num, self.ui_unit_number = self._create_stat_section(tr("wizard.household.unit_number"))
        section_floor, self.ui_floor_number = self._create_stat_section(tr("wizard.household.floor_number"))
        section_rooms, self.ui_rooms_count = self._create_stat_section(tr("wizard.household.rooms_count"))
        section_area, self.ui_area = self._create_stat_section(tr("wizard.household.unit_area"))
        section_unit_type, self.ui_unit_type = self._create_stat_section(tr("wizard.household.unit_type_label"))
        section_unit_status, self.ui_unit_status = self._create_stat_section(tr("wizard.household.unit_status_label"))

        # Add sections with equal spacing
        unit_sections = [section_unit_num, section_floor, section_rooms, section_area, section_unit_type, section_unit_status]
        for section in unit_sections:
            unit_info_row.addWidget(section, stretch=1)

        card_layout.addWidget(unit_info_container)

        # Create scroll area for ALL cards (modern thin scrollbar)
        scroll_area = QScrollArea()
        scroll_area.setLayoutDirection(Qt.RightToLeft)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 4px 0px 4px 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #C4CDD5;
                min-height: 40px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #919EAB;
            }
            QScrollBar::handle:vertical:pressed {
                background: #637381;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Container widget for scroll area content
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        # Add Card 1 (Building info) to scroll area
        scroll_layout.addWidget(self.household_building_frame)

        # معلومات الاسرة (Family Information) Section - same design as units card
        family_info_frame = QFrame()
        family_info_frame.setObjectName("familyInfoCard")
        family_info_frame.setFixedHeight(330)  # Header + head_name + total_members + notes
        family_info_frame.setStyleSheet("""
            QFrame#familyInfoCard {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)

        # Apply subtle shadow effect
        family_shadow = QGraphicsDropShadowEffect()
        family_shadow.setBlurRadius(8)
        family_shadow.setXOffset(0)
        family_shadow.setYOffset(2)
        family_shadow.setColor(QColor(0, 0, 0, 30))
        family_info_frame.setGraphicsEffect(family_shadow)

        family_info_layout = QVBoxLayout(family_info_frame)
        family_info_layout.setSpacing(12)
        family_info_layout.setContentsMargins(12, 12, 12, 12)  # Padding 12px

        # ===== HEADER: Icon + Title/Subtitle =====
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Right side: Icon container + Title and subtitle
        right_header = QHBoxLayout()
        right_header.setSpacing(8)

        # Icon container (48×48, background #F0F7FF)
        icon_container = QFrame()
        icon_container.setFixedSize(48, 48)
        icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: none;
                border-radius: 6px;
            }}
        """)

        # Center icon inside container
        icon_container_layout = QHBoxLayout(icon_container)
        icon_container_layout.setContentsMargins(0, 0, 0, 0)
        icon_container_layout.setAlignment(Qt.AlignCenter)

        # Load user-group.png icon
        icon_label = QLabel()
        icon_pixmap = Icon.load_pixmap("user-group", size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("👥")  # Fallback emoji
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_container_layout.addWidget(icon_label)

        right_header.addWidget(icon_container)

        # Title and subtitle
        title_subtitle_layout = QVBoxLayout()
        title_subtitle_layout.setSpacing(2)
        title_subtitle_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        self._title_label = QLabel(tr("wizard.household.occupants_title"))
        self._title_label.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        self._title_label.setStyleSheet("""
            QLabel {
                color: #1A1F1D;
                border: none;
                background: transparent;
            }
        """)
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_subtitle_layout.addWidget(self._title_label)

        # Subtitle
        self._subtitle_label = QLabel(tr("wizard.household.subtitle"))
        self._subtitle_label.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        self._subtitle_label.setStyleSheet("""
            QLabel {
                color: #86909B;
                border: none;
                background: transparent;
            }
        """)
        self._subtitle_label.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(self._subtitle_label)

        right_header.addLayout(title_subtitle_layout)
        header_layout.addLayout(right_header)
        header_layout.addStretch()

        family_info_layout.addLayout(header_layout)

        # ===== ROW 1.5: Occupancy Type + Occupancy Nature (side by side) =====
        family_info_layout.addSpacing(8)

        occupancy_row = QHBoxLayout()
        occupancy_row.setSpacing(12)

        arrow_img = str(Config.IMAGES_DIR / "v.png").replace("\\", "/")
        combo_style = f"""
            QComboBox {{
                padding: 6px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 14px;
                color: #1A1A1A;
                min-height: 43px;
                max-height: 43px;
            }}
            QComboBox:focus {{
                border: 1px solid #E1E8ED;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center right;
                width: 35px;
                border: none;
                margin-right: 5px;
            }}
            QComboBox::down-arrow {{
                image: url({arrow_img});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                font-size: 14px;
                background-color: white;
                selection-background-color: #3890DF;
                selection-color: white;
            }}
        """
        label_style = "color: #374151; background: transparent;"

        # -- Left field: Occupancy Nature (ownership/other) --
        nature_col = QVBoxLayout()
        nature_col.setSpacing(4)

        self._occupancy_nature_label = QLabel(tr("wizard.household.occupancy_nature"))
        self._occupancy_nature_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._occupancy_nature_label.setStyleSheet(label_style)
        nature_col.addWidget(self._occupancy_nature_label)

        self.hh_occupancy_nature = RtlCombo()
        self.hh_occupancy_nature.addItem(tr("wizard.household.select"), None)
        for code, display_name in get_occupancy_nature_options():
            if code == 0:
                continue
            self.hh_occupancy_nature.addItem(display_name, code)
        self.hh_occupancy_nature.setStyleSheet(combo_style)
        self.hh_occupancy_nature.setFixedHeight(45)
        nature_col.addWidget(self.hh_occupancy_nature)

        occupancy_row.addLayout(nature_col, 1)

        # -- Right field: Occupancy Type (residential/non-residential) --
        type_col = QVBoxLayout()
        type_col.setSpacing(4)

        self._occupancy_type_label = QLabel(tr("wizard.household.occupancy_type"))
        self._occupancy_type_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._occupancy_type_label.setStyleSheet(label_style)
        type_col.addWidget(self._occupancy_type_label)

        self.hh_occupancy_type = RtlCombo()
        self.hh_occupancy_type.addItem(tr("wizard.household.select"), None)
        for code, display_name in get_occupancy_type_options():
            if code == 0:
                continue
            self.hh_occupancy_type.addItem(display_name, code)
        self.hh_occupancy_type.setStyleSheet(combo_style)
        self.hh_occupancy_type.setFixedHeight(45)
        type_col.addWidget(self.hh_occupancy_type)

        occupancy_row.addLayout(type_col, 1)

        family_info_layout.addLayout(occupancy_row)

        # ===== ROW 2: Total Members (full width) =====
        family_info_layout.addSpacing(8)

        total_members_layout = QVBoxLayout()
        total_members_layout.setSpacing(4)

        self._total_members_label = QLabel(tr("wizard.household.total_members"))
        self._total_members_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._total_members_label.setStyleSheet("color: #374151; background: transparent;")
        total_members_layout.addWidget(self._total_members_label)

        self.hh_total_members = QSpinBox()
        self.hh_total_members.setRange(0, 50)
        self.hh_total_members.setValue(0)
        self.hh_total_members.setAlignment(Qt.AlignCenter)
        self.hh_total_members.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.hh_total_members.setButtonSymbols(QSpinBox.NoButtons)

        members_widget = self._create_spinbox_with_arrows(self.hh_total_members)
        members_widget.setFixedHeight(45)
        total_members_layout.addWidget(members_widget)

        family_info_layout.addLayout(total_members_layout)

        # ===== ROW 3: Notes field =====
        # Gap before row 3: 8px
        family_info_layout.addSpacing(8)

        notes_field_layout = QVBoxLayout()
        notes_field_layout.setSpacing(4)

        self._notes_label = QLabel(tr("wizard.household.notes_label"))
        self._notes_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._notes_label.setStyleSheet("color: #374151; background: transparent;")
        notes_field_layout.addWidget(self._notes_label)

        self.hh_notes = CenteredTextEdit()
        self.hh_notes.setPlaceholderText(tr("wizard.household.notes_placeholder"))
        self.hh_notes.setPlaceholderStyleSheet(
            "color: #9CA3AF; background: transparent; font-size: 16px; font-weight: 400;"
        )
        self.hh_notes.setMaximumHeight(80)
        self.hh_notes.setLayoutDirection(Qt.RightToLeft)
        self.hh_notes.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F0F7FF;
                font-size: 16px;
                font-weight: 600;
                color: #1A1A1A;
            }
            QTextEdit:focus {
                border-color: #3890DF;
                border-width: 2px;
            }
        """)
        notes_field_layout.addWidget(self.hh_notes)

        family_info_layout.addLayout(notes_field_layout)

        scroll_layout.addWidget(family_info_frame)

        # ========== CARD 3: تكوين الأسرة (Family Composition) ==========
        composition_frame = QFrame()
        composition_frame.setObjectName("compositionCard")
        composition_frame.setFixedHeight(400)  # Figma spec
        composition_frame.setStyleSheet("""
            QFrame#compositionCard {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)

        # Apply subtle shadow effect
        composition_shadow = QGraphicsDropShadowEffect()
        composition_shadow.setBlurRadius(8)
        composition_shadow.setXOffset(0)
        composition_shadow.setYOffset(2)
        composition_shadow.setColor(QColor(0, 0, 0, 30))
        composition_frame.setGraphicsEffect(composition_shadow)

        composition_layout = QVBoxLayout(composition_frame)
        composition_layout.setSpacing(12)  # Gap: 12px
        composition_layout.setContentsMargins(12, 12, 12, 12)  # Padding: 12px

        # ===== ROW 1: Title (no icon) =====
        title_label = QLabel(tr("wizard.household.composition_title"))
        title_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet("color: #1A1F1D; background: transparent;")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        composition_layout.addWidget(title_label)

        # ===== ROW 2: Two inner cards (Male + Female) =====
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)  # Gap between cards: 12px

        # Create Male card (LEFT in RTL)
        male_card = self._create_gender_card(tr("wizard.household.males"), [
            (tr("wizard.household.adult_males"), "hh_adult_males"),
            (tr("wizard.household.male_children"), "hh_male_children_under18"),
            (tr("wizard.household.male_elderly"), "hh_male_elderly_over65"),
            (tr("wizard.household.disabled_males"), "hh_disabled_males")
        ])
        cards_row.addWidget(male_card, 1)

        # Create Female card (RIGHT in RTL)
        female_card = self._create_gender_card(tr("wizard.household.females"), [
            (tr("wizard.household.adult_females"), "hh_adult_females"),
            (tr("wizard.household.female_children"), "hh_female_children_under18"),
            (tr("wizard.household.female_elderly"), "hh_female_elderly_over65"),
            (tr("wizard.household.disabled_females"), "hh_disabled_females")
        ])
        cards_row.addWidget(female_card, 1)

        composition_layout.addLayout(cards_row)
        scroll_layout.addWidget(composition_frame)

        # Set scroll content and add to main layout
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

    def _create_stat_section(self, label_text: str, value_text: str = "-"):
        """
        DRY: Create a stat section with label on top and value below.

        Same design as unit_selection_step for consistency.

        Args:
            label_text: Label text (e.g., "نوع البناء")
            value_text: Value text (default: "-")

        Returns:
            Tuple of (section_widget, value_label)
        """
        section = QWidget()
        section.setStyleSheet("background: transparent;")

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 0, 8, 0)
        section_layout.setSpacing(4)
        section_layout.setAlignment(Qt.AlignCenter)

        # Label (top)
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Value (bottom) - centered under label
        value = QLabel(value_text)
        value.setAlignment(Qt.AlignCenter)
        value.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        section_layout.addWidget(label)
        section_layout.addWidget(value)

        return section, value

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox, bg_color: str = "#F8FAFF") -> QFrame:
        """
        Create a spinbox widget with icon arrows (matching unit_dialog style).

        Args:
            spinbox: QSpinBox to wrap with custom arrows
            bg_color: Background color for the container

        Returns:
            QFrame container with spinbox and arrows
        """
        container = QFrame()
        container.setFixedHeight(45)
        container.setStyleSheet(f"""
            QFrame {{
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: {bg_color};
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Spinbox (no border since container has border)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                padding-right: 35px;
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #606266;
                selection-background-color: transparent;
                selection-color: #606266;
            }
            QSpinBox:focus {
                border: none;
                outline: 0;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)
        layout.addWidget(spinbox, 1)

        # Arrow column (RIGHT side) with left border separator
        arrow_container = QFrame()
        arrow_container.setFixedWidth(30)
        arrow_container.setStyleSheet("""
            QFrame {
                border: none;
                border-left: 1px solid #E1E8ED;
                background: transparent;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)

        # Up arrow icon (^.png)
        up_label = QLabel()
        up_label.setFixedSize(30, 22)
        up_label.setAlignment(Qt.AlignCenter)
        up_pixmap = Icon.load_pixmap("^", size=10)
        if up_pixmap and not up_pixmap.isNull():
            up_label.setPixmap(up_pixmap)
        else:
            up_label.setText("^")
            up_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        up_label.setCursor(Qt.PointingHandCursor)
        up_label.mousePressEvent = lambda _: spinbox.stepUp()
        arrow_layout.addWidget(up_label)

        # Down arrow icon (v.png)
        down_label = QLabel()
        down_label.setFixedSize(30, 22)
        down_label.setAlignment(Qt.AlignCenter)
        down_pixmap = Icon.load_pixmap("v", size=10)
        if down_pixmap and not down_pixmap.isNull():
            down_label.setPixmap(down_pixmap)
        else:
            down_label.setText("v")
            down_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda _: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        layout.addWidget(arrow_container)

        return container

    def _create_gender_card(self, title: str, fields: list) -> QFrame:
        """
        DRY: Create a gender-specific card (Male/Female) with demographic fields.

        Args:
            title: Card title (e.g., "ذكور" or "إناث")
            fields: List of tuples [(label, attribute_name), ...]

        Returns:
            QFrame containing the gender card

        Figma specs:
        - Height: 340px (fixed)
        - Width: Auto (fill available space with equal stretch)
        - Border-radius: 12px
        - Gap between fields: 12px
        - Background: White
        """
        card = QFrame()
        card.setObjectName(f"{title}Card")
        card.setFixedHeight(340)  # Figma spec
        card.setStyleSheet(f"""
            QFrame#{title}Card {{
                background-color: #F0F7FF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)  # Gap between fields: 12px
        card_layout.setContentsMargins(12, 12, 12, 12)  # Padding: 12px

        # Card title
        card_title = QLabel(title)
        card_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        card_title.setStyleSheet("color: #374151; background: transparent;")
        card_title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(card_title)

        # Create fields using the same spinbox with arrows pattern
        for label_text, attr_name in fields:
            field_layout = QVBoxLayout()
            field_layout.setSpacing(4)

            # Label
            label = QLabel(label_text)
            label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet("color: #374151; background: transparent;")
            field_layout.addWidget(label)

            # SpinBox with custom arrows (white background)
            spinbox = QSpinBox()
            spinbox.setRange(0, 50)
            spinbox.setValue(0)
            spinbox.setAlignment(Qt.AlignRight)
            spinbox.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
            spinbox.setButtonSymbols(QSpinBox.NoButtons)

            # Create container with arrows (white background for inner cards)
            spinbox_widget = self._create_composition_spinbox(spinbox)

            field_layout.addWidget(spinbox_widget)
            card_layout.addLayout(field_layout)

            # Store reference to spinbox for data collection
            setattr(self, attr_name, spinbox)

        return card

    def _create_composition_spinbox(self, spinbox: QSpinBox) -> QFrame:
        """
        Create a spinbox widget with arrows for composition fields.

        Reuses _create_spinbox_with_arrows with WHITE background.
        """
        return self._create_spinbox_with_arrows(spinbox, bg_color="#FFFFFF")

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        self._title_label.setText(tr("wizard.household.occupants_title"))
        self._subtitle_label.setText(tr("wizard.household.subtitle"))
        self._occupancy_type_label.setText(tr("wizard.household.occupancy_type"))
        self._occupancy_nature_label.setText(tr("wizard.household.occupancy_nature"))
        self._total_members_label.setText(tr("wizard.household.total_members"))
        self._notes_label.setText(tr("wizard.household.notes_label"))
        self.hh_notes.setPlaceholderText(tr("wizard.household.notes_placeholder"))

    def validate(self) -> StepValidationResult:
        """Validate the step and save household data automatically."""
        result = self.create_validation_result()

        # Auto-save household data when clicking "Next"
        property_unit_id = None
        if self.context.unit:
            property_unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            property_unit_id = self.context.new_unit_data.get('unit_uuid')

        # Validate: total members must be > 0
        total_entered = self.hh_total_members.value()
        if total_entered <= 0:
            result.add_error(tr("wizard.household.members_required"))
            return result

        # Validate: total members == sum of all male + female fields
        sum_details = (
            self.hh_adult_males.value() + self.hh_adult_females.value()
            + self.hh_male_children_under18.value() + self.hh_female_children_under18.value()
            + self.hh_male_elderly_over65.value() + self.hh_female_elderly_over65.value()
            + self.hh_disabled_males.value() + self.hh_disabled_females.value()
        )
        if total_entered != sum_details:
            result.add_error(tr("wizard.household.members_mismatch"))
            return result

        household = {
            "household_id": str(uuid.uuid4()),
            "property_unit_id": property_unit_id,
            "unit_uuid": property_unit_id,
            "occupancy_type": self.hh_occupancy_type.currentData(),
            "occupancy_nature": self.hh_occupancy_nature.currentData(),
            "size": self.hh_total_members.value(),
            "adult_males": self.hh_adult_males.value(),
            "adult_females": self.hh_adult_females.value(),
            "male_children_under18": self.hh_male_children_under18.value(),
            "female_children_under18": self.hh_female_children_under18.value(),
            "male_elderly_over65": self.hh_male_elderly_over65.value(),
            "female_elderly_over65": self.hh_female_elderly_over65.value(),
            "disabled_males": self.hh_disabled_males.value(),
            "disabled_females": self.hh_disabled_females.value(),
            "notes": self.hh_notes.toPlainText().strip()
        }

        # Save via API if using API mode
        if self._use_api:
            existing_household_id = self.context.get_data("household_id")
            survey_id = self.context.get_data("survey_id")
            self._set_auth_token()

            if existing_household_id:
                stored = self.context.households[0] if self.context.households else {}
                if self._household_data_changed(household, stored):
                    try:
                        self._api_client.update_household(existing_household_id, household, survey_id=survey_id)
                        logger.info(f"Household {existing_household_id} updated via API")
                    except Exception as e:
                        logger.error(f"Failed to update household: {e}")
                        result.add_error(tr("wizard.household.save_failed", error_msg=map_exception(e)))
                        return result
                else:
                    logger.info(f"Household unchanged ({existing_household_id}), skipping")
                household["api_id"] = existing_household_id
            else:
                logger.info(f"Creating household via API: property_unit_id={property_unit_id}, survey_id={survey_id}, size={household['size']}")
                try:
                    api_response = self._api_client.create_household(household, survey_id=survey_id)
                    logger.info("Household created successfully via API")
                    household_id = api_response.get("id") or api_response.get("householdId", "")
                    household["api_id"] = household_id
                    self.context.update_data("household_id", household_id)
                except Exception as e:
                    logger.error(f"Failed to create household via API: {e}")
                    result.add_error(tr("wizard.household.save_failed", error_msg=map_exception(e)))
                    return result

        # Update or add household data
        if self.context.households:
            self.context.households[0] = household
        else:
            self.context.households.append(household)

        # Validate that household data exists
        if len(self.context.households) == 0:
            result.add_error(tr("wizard.household.required_error"))

        return result

    def _household_data_changed(self, current: Dict, stored: Dict) -> bool:
        """Compare current form data with stored household to detect changes."""
        compare_keys = [
            "property_unit_id",
            "size", "occupancy_type", "occupancy_nature",
            "adult_males", "adult_females",
            "male_children_under18", "female_children_under18",
            "male_elderly_over65", "female_elderly_over65",
            "disabled_males", "disabled_females", "notes"
        ]
        for key in compare_keys:
            if current.get(key) != stored.get(key):
                return True
        return False

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "households": self.context.households,
            "households_count": len(self.context.households)
        }

    def populate_data(self):
        """Populate the step with data from context."""
        # Update building address and stats
        if self.context.building:
            from utils.helpers import build_hierarchical_address
            address = build_hierarchical_address(self.context.building)
            self.household_building_address.setText(address)

            # Update building stats - same as unit_selection_step
            building = self.context.building

            # Use display properties directly (they return Arabic text)
            self.ui_building_type.setText(building.building_type_display or "-")
            self.ui_building_status.setText(building.building_status_display or "-")
            self.ui_units_count.setText(str(getattr(building, 'number_of_apartments', 0) + (building.number_of_shops or 0)))
            self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
            self.ui_shops_count.setText(str(building.number_of_shops or 0))

        # Update unit information (Row 3) - DRY: use centralized display_mappings
        # Get unit data from context
        if self.context.unit:
            unit = self.context.unit
            unit_type_display = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else get_unit_type_display(getattr(unit, 'unit_type', None))
            unit_status_raw = getattr(unit, 'apartment_status', None)
            unit_status_display = get_unit_status_display(unit_status_raw) if unit_status_raw else "-"

            floor_number = getattr(unit, 'floor_number', None)
            unit_number = getattr(unit, 'unit_number', None) or getattr(unit, 'apartment_number', None)
            rooms_count = getattr(unit, 'apartment_number', None)
            area = getattr(unit, 'area_sqm', None)
        elif self.context.new_unit_data:
            unit_type_raw = self.context.new_unit_data.get('unit_type')
            unit_type_display = get_unit_type_display(unit_type_raw) if unit_type_raw else "-"

            unit_status_raw = self.context.new_unit_data.get('apartment_status')
            unit_status_display = get_unit_status_display(unit_status_raw) if unit_status_raw else "-"

            floor_number = self.context.new_unit_data.get('floor_number')
            unit_number = self.context.new_unit_data.get('unit_number')
            rooms_count = self.context.new_unit_data.get('number_of_rooms')
            area = self.context.new_unit_data.get('area_sqm')
        else:
            unit_type_display = unit_status_display = "-"
            floor_number = unit_number = rooms_count = area = None

        # Update unit info labels
        self.ui_unit_type.setText(unit_type_display)
        self.ui_unit_status.setText(unit_status_display)
        self.ui_floor_number.setText(str(floor_number) if floor_number is not None else "-")
        self.ui_unit_number.setText(str(unit_number) if unit_number else "-")
        self.ui_rooms_count.setText(str(rooms_count) if rooms_count is not None else "-")
        # Format area with 2 decimal places
        if area:
            try:
                area_formatted = f"{float(area):.2f} m²"
                self.ui_area.setText(area_formatted)
            except (ValueError, TypeError):
                self.ui_area.setText("-")
        else:
            self.ui_area.setText("-")

        # Load existing household data if available
        if len(self.context.households) > 0:
            household = self.context.households[0]
            # Head of household name
            # Restore occupancy combos
            if household.get('occupancy_nature') is not None:
                idx = self.hh_occupancy_nature.findData(household['occupancy_nature'])
                if idx >= 0:
                    self.hh_occupancy_nature.setCurrentIndex(idx)
            if household.get('occupancy_type') is not None:
                idx = self.hh_occupancy_type.findData(household['occupancy_type'])
                if idx >= 0:
                    self.hh_occupancy_type.setCurrentIndex(idx)

            self.hh_total_members.setValue(household.get("size", 0))
            self.hh_adult_males.setValue(household.get("adult_males", 0))
            self.hh_adult_females.setValue(household.get("adult_females", 0))
            self.hh_male_children_under18.setValue(household.get("male_children_under18", 0))
            self.hh_female_children_under18.setValue(household.get("female_children_under18", 0))
            self.hh_male_elderly_over65.setValue(household.get("male_elderly_over65", 0))
            self.hh_female_elderly_over65.setValue(household.get("female_elderly_over65", 0))
            self.hh_disabled_males.setValue(household.get("disabled_males", 0))
            self.hh_disabled_females.setValue(household.get("disabled_females", 0))
            self.hh_notes.setPlainText(household.get("notes", ""))
        else:
            self.hh_total_members.setValue(0)
            self.hh_adult_males.setValue(0)
            self.hh_adult_females.setValue(0)
            self.hh_male_children_under18.setValue(0)
            self.hh_female_children_under18.setValue(0)
            self.hh_male_elderly_over65.setValue(0)
            self.hh_female_elderly_over65.setValue(0)
            self.hh_disabled_males.setValue(0)
            self.hh_disabled_females.setValue(0)
            self.hh_notes.clear()

    def get_step_title(self) -> str:
        """Get step title."""
        return tr("wizard.household.step_title")

    def get_step_description(self) -> str:
        """Get step description."""
        return tr("wizard.household.step_description")
