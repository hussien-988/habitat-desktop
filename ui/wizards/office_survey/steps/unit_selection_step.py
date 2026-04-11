# -*- coding: utf-8 -*-
"""
Unit Selection Step - Step 2 of Office Survey Wizard.

Allows user to:
- View existing units in the selected building
- Select an existing unit
- Create a new unit with validation
"""

from typing import Dict, Any, Optional, List
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QWidget,
    QComboBox, QSpinBox, QTextEdit,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QCursor, QIcon, QColor, QDoubleValidator

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.wizard_styles import (
    MINI_CARD_STYLE, MINI_CARD_SELECTED_STYLE,
    make_step_card, make_icon_header, make_divider, DIVIDER_COLOR,
    FORM_FIELD_STYLE, FOOTER_PRIMARY_STYLE, FOOTER_SECONDARY_STYLE,
)
from controllers.unit_controller import UnitController
from models.unit import PropertyUnit as Unit
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from utils.logger import get_logger
from utils.helpers import build_hierarchical_address
from ui.design_system import Colors, ScreenScale
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.action_button import ActionButton
from ui.components.rtl_combo import RtlCombo
from ui.components.toast import Toast
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import get_unit_status_display, get_unit_type_display, get_unit_type_options, get_unit_status_options
from services.error_mapper import map_exception
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.components.bottom_sheet import BottomSheet

logger = get_logger(__name__)


class UnitSelectionStep(BaseStep):
    """
    Step 2: Unit Selection/Creation.

    User can:
    - View existing units in the selected building
    - Select an existing unit
    - Create a new unit with uniqueness validation
    UI copied from office_survey_wizard.py _create_unit_step() - exact match.
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)
        self.unit_controller = UnitController(self.context.db)
        self.selected_unit: Optional[Unit] = None

        # Initialize API client for linking units to survey
        self._api_service = get_api_client()
        self._loaded_building_uuid = None  # Track which building's units are loaded

        # Set auth token for API calls if available
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self.unit_controller.set_auth_token(main_window._api_token)

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        layout = self.main_layout
        # No horizontal padding - wizard applies 131px
        # Adjusted top margin to match visual spacing of building_selection_step
        layout.setContentsMargins(0, 8, 0, 16)  # Top: 8px (reduced for visual consistency), Bottom: 16px
        layout.setSpacing(10)  # Reduced spacing: 10px between cards (was 15px)

        # Selected building info card - same design as building_selection_step stats card
        # Height: 113px, includes address row + stats sections
        self.unit_building_frame = make_step_card()

        # Main card layout
        card_layout = QVBoxLayout(self.unit_building_frame)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        address_container = QFrame()
        address_container.setFixedHeight(ScreenScale.h(32))
        address_container.setStyleSheet("""
            QFrame {
                background-color: #F0F4FA;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)

        # Centered layout with icon + text
        address_row = QHBoxLayout(address_container)
        address_row.setContentsMargins(12, 0, 12, 0)
        address_row.setSpacing(8)

        # Center the content
        address_row.addStretch()

        # Icon: dec.png
        from ui.components.icon import Icon
        address_icon = QLabel()
        address_icon_pixmap = Icon.load_pixmap("dec", size=16)
        if address_icon_pixmap and not address_icon_pixmap.isNull():
            address_icon.setPixmap(address_icon_pixmap)
        else:
            address_icon.setText("📍")  # Fallback emoji
        address_icon.setStyleSheet("background: transparent; border: none;")
        address_row.addWidget(address_icon)

        # Building address text - centered, color #667281
        # Displays building address only
        self.unit_building_address = QLabel(tr("wizard.unit.address_label"))
        self.unit_building_address.setAlignment(Qt.AlignCenter)
        self.unit_building_address.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        self.unit_building_address.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
                color: #667281;
            }
        """)
        address_row.addWidget(self.unit_building_address)

        # Center the content
        address_row.addStretch()

        card_layout.addWidget(address_container)
        # Same design as building_selection_step stats sections
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)  # Equal distribution

        # Helper function to create stat section (label on top, value below)
        def _create_stat_section(label_text, value_text="-"):
            """Create a stat section with label on top and value below."""
            section = QWidget()
            section.setStyleSheet("background: transparent;")

            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(8, 0, 8, 0)
            section_layout.setSpacing(4)
            section_layout.setAlignment(Qt.AlignCenter)

            # Label (top)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignCenter)
            label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

            # Value (bottom) - centered under label
            value = QLabel(value_text)
            value.setAlignment(Qt.AlignCenter)
            value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
            value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

            section_layout.addWidget(label)
            section_layout.addWidget(value)

            return section, value, label

        # Create 5 stat sections - hardcoded Arabic matching Step 1
        section_status, self.ui_building_status, self._lbl_status = _create_stat_section(tr("wizard.building.status"))
        section_type, self.ui_building_type, self._lbl_type = _create_stat_section(tr("wizard.building.type"))
        section_units, self.ui_units_count, self._lbl_units = _create_stat_section(tr("wizard.building.units_count"))
        section_parcels, self.ui_parcels_count, self._lbl_parcels = _create_stat_section(tr("wizard.building.parcels_count"))
        section_shops, self.ui_shops_count, self._lbl_shops = _create_stat_section(tr("wizard.building.shops_count"))

        # Add sections with equal spacing - status first, then type (matching Step 1 order)
        sections = [section_status, section_type, section_units, section_parcels, section_shops]
        for section in sections:
            stats_row.addWidget(section, stretch=1)

        card_layout.addLayout(stats_row)

        layout.addWidget(self.unit_building_frame)

        # Units Container Card
        # Dimensions: 1249×372 (width×height), border-radius: 8px, padding: 12px
        # Gap from Card 1: 15px (handled by layout.setSpacing(15))
        units_main_frame = make_step_card()

        units_main_layout = QVBoxLayout(units_main_frame)
        units_main_layout.setSpacing(14)
        units_main_layout.setContentsMargins(16, 16, 16, 16)

        # Header: icon + title/subtitle + add-unit button
        header_layout, header_title, header_subtitle = make_icon_header(
            tr("wizard.unit.select_title"),
            tr("wizard.unit.select_subtitle"),
            "move"
        )

        # إعادة تطبيق الترجمة (مهم جداً)
        header_title.setText(tr("wizard.unit.select_title"))
        header_subtitle.setText(tr("wizard.unit.select_subtitle"))
        self._units_header_title = header_title
        self._units_header_subtitle = header_subtitle

        self.add_unit_btn = ActionButton(
            text=tr("wizard.unit.add_button"),
            variant="outline",
            icon_name="icon",
            width=125,
            height=44
        )
        self.add_unit_btn.clicked.connect(self._show_add_unit_form)
        header_layout.addWidget(self.add_unit_btn)

        units_main_layout.addLayout(header_layout)

        # BottomSheet reference for unit creation (created on demand)
        self._unit_sheet = None
        self._pending_auto_select_uuid = None  # UUID to auto-select after async load

        # Empty state widget (shown when no units)
        self._empty_state = self._create_empty_state()
        units_main_layout.addWidget(self._empty_state)

        # Units list container (inside white frame)
        self.units_container = QWidget()
        self.units_layout = QVBoxLayout(self.units_container)
        self.units_layout.setSpacing(10)
        self.units_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for units
        scroll = QScrollArea()
        scroll.setLayoutDirection(get_layout_direction())
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.units_container)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: white; }"
            + StyleManager.scrollbar()
        )
        self._scroll_area = scroll
        units_main_layout.addWidget(scroll, 1)

        layout.addWidget(units_main_frame, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_empty_state(self) -> QWidget:
        """Create empty state widget shown when no units exist."""
        import os
        from PyQt5.QtGui import QPixmap

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 40, 0, 40)

        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(15)

        # Icon with orange circle background
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(70), ScreenScale.h(70))
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet("""
            background-color: #EBF5FF;
            border: 1px solid #DBEAFE;
            border-radius: 35px;
        """)

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "assets", "images", "tdesign_no-result.png"
        )
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_container.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            no_result_pixmap = Icon.load_pixmap("tdesign_no-result", size=40)
            if no_result_pixmap and not no_result_pixmap.isNull():
                icon_container.setPixmap(no_result_pixmap)
            else:
                icon_container.setText("!")
                icon_container.setStyleSheet(icon_container.styleSheet() + "font-size: 28px; color: #1a1a1a;")

        # Title
        title_label = QLabel(tr("wizard.unit.empty_title"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Description
        desc_label = QLabel(tr("wizard.unit.empty_desc"))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_DESC, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        center_layout.addWidget(icon_container, alignment=Qt.AlignCenter)
        center_layout.addWidget(title_label)
        center_layout.addWidget(desc_label)

        main_layout.addWidget(center_widget)

        return container

    def _load_units(self):
        """Load units for the selected building and display as cards (non-blocking)."""
        if not self.context.building:
            self._loaded_building_uuid = None
            self.unit_building_frame.setVisible(False)
            while self.units_layout.count():
                child = self.units_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self._empty_state.setVisible(True)
            self._scroll_area.setVisible(False)
            self.selected_unit = None
            self.emit_validation_changed(False)
            return

        building_uuid = self.context.building.building_uuid

        if building_uuid and self._loaded_building_uuid == building_uuid:
            logger.info(f"Units already loaded for building {building_uuid}, skipping fetch")
            return

        building = self.context.building

        address = build_hierarchical_address(
            building_obj=building,
            unit_obj=None,
            separator=" - ",
            include_unit=False
        )
        self.unit_building_address.setText(address)

        self.ui_building_type.setText(building.building_type_display or "-")
        self.ui_building_status.setText(building.building_status_display or "-")
        self.ui_units_count.setText(str(getattr(building, 'number_of_apartments', 0) + (building.number_of_shops or 0)))
        self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
        self.ui_shops_count.setText(str(building.number_of_shops or 0))

        self.unit_building_frame.setVisible(True)

        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        survey_id = self.context.get_data("survey_id")
        logger.info(f"Loading units for building: {building_uuid}, survey: {survey_id}")

        def _do_load():
            if survey_id:
                return self.unit_controller.get_units_for_survey(survey_id)
            else:
                return self.unit_controller.get_units_for_building(building_uuid)

        self._spinner.show_loading(tr("component.loading.default"))
        self._load_units_worker = ApiWorker(_do_load)
        self._load_units_worker.finished.connect(
            lambda result: (self._spinner.hide_loading(), self._on_units_loaded(result, building_uuid))
        )
        self._load_units_worker.error.connect(
            lambda msg: (self._spinner.hide_loading(), self._on_units_load_error(msg))
        )
        self._load_units_worker.start()

    def _on_units_loaded(self, result, building_uuid):
        """Handle units loaded from API."""
        if not result.success:
            logger.error(f"Failed to load units: {result.message}")
            self._empty_state.setVisible(True)
            self._scroll_area.setVisible(False)
            return

        all_units = result.data or []
        units = []
        for u in all_units:
            u_building = getattr(u, 'building_id', None)
            if not u_building or u_building == building_uuid or u_building == self.context.building.building_id:
                units.append(u)
            else:
                logger.warning(f"Filtered out unit {u.unit_id} - belongs to building {u_building}, not {building_uuid}")

        logger.info(f"Showing {len(units)} units (of {len(all_units)} returned by API) for building {building_uuid}")

        has_units = len(units) > 0
        self._empty_state.setVisible(not has_units)
        self._scroll_area.setVisible(has_units)

        if units:
            for unit in units:
                unit_card = self._create_unit_card(unit)
                self.units_layout.addWidget(unit_card)

        # Auto-select newly created unit if pending
        if self._pending_auto_select_uuid and units:
            for unit in units:
                if getattr(unit, 'unit_uuid', None) == self._pending_auto_select_uuid:
                    self.context.unit = unit
                    self.context.is_new_unit = False
                    self.selected_unit = unit
                    logger.info(f"Auto-selected newly created unit: {unit.unit_uuid}")
                    self._refresh_unit_card_styles()
                    self.emit_validation_changed(True)
                    break
            self._pending_auto_select_uuid = None

        self.units_layout.addStretch()
        self._loaded_building_uuid = building_uuid

    def _on_units_load_error(self, msg):
        """Handle units loading error."""
        logger.error(f"Failed to load units: {msg}")
        self._empty_state.setVisible(True)
        self._scroll_area.setVisible(False)

    def _to_arabic_numerals(self, text: str) -> str:
        """
        Convert English/Latin numerals to Arabic-Indic numerals.

        Args:
            text: Text containing numerals

        Returns:
            Text with Arabic numerals
        """
        arabic_digits = '٠١٢٣٤٥٦٧٨٩'
        english_digits = '0123456789'
        translation_table = str.maketrans(english_digits, arabic_digits)
        return str(text).translate(translation_table)

    def _create_field_label(self, text: str, is_title: bool = True) -> QLabel:
        """
        Create a label with consistent styling.

        Args:
            text: Label text
            is_title: True for title style (like "اختر مقسماً"),
                     False for value style (like subtitle)

        Returns:
            Configured QLabel
        """
        label = QLabel(text)

        if is_title:
            # Title style - center-aligned
            label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE};")
            label.setAlignment(Qt.AlignCenter)
        else:
            # Value style - center-aligned (directly under label)
            label.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE};")
            label.setAlignment(Qt.AlignCenter)

        return label

    def _create_unit_card(self, unit) -> QFrame:
        """
        Create a unit card widget.
        - Dimensions: 1225×138 (width×height)
        - Padding: 12px all sides
        - Border-radius: 10px
        - Gap between top and bottom sections: 8px
        """
        # Determine unit display number (from unit_number or apartment_number)
        unit_display_num = unit.unit_number or unit.apartment_number or "?"

        # Check if this is the selected unit
        is_selected = bool(self.context.unit and self.context.unit.unit_uuid == unit.unit_uuid)
        card = QFrame()
        card.setObjectName("unitCard")

        if is_selected:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #EBF5FF;
                    border: 2px solid #3890DF;
                    border-left: 4px solid #3890DF;
                    border-radius: 12px;
                }
                QFrame#unitCard QLabel { border: none; background: transparent; }
            """)
        else:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #F8FAFF;
                    border: 1px solid #E5EAF6;
                    border-radius: 12px;
                }
                QFrame#unitCard:hover {
                    border-color: rgba(56, 144, 223, 0.5);
                    background-color: #EBF5FF;
                }
                QFrame#unitCard QLabel { border: none; background: transparent; }
            """)

        card_shadow = QGraphicsDropShadowEffect()
        card_shadow.setBlurRadius(16)
        card_shadow.setXOffset(0)
        card_shadow.setYOffset(3)
        card_shadow.setColor(QColor(0, 0, 0, 18))
        card.setGraphicsEffect(card_shadow)

        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda _: self._on_unit_card_clicked(unit)
        card.setProperty("unit_id", unit.unit_uuid)
        card.setLayoutDirection(get_layout_direction())
        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(8)  # Gap between top and bottom: 8px
        main_layout.setContentsMargins(12, 12, 12, 12)  # Padding: 12px

        # Get unit type using centralized display mapping (language-aware)
        unit_type_val = get_unit_type_display(unit.unit_type) if unit.unit_type else "-"

        # Get status display using centralized mapping
        if hasattr(unit, 'apartment_status') and unit.apartment_status is not None:
            status_val = get_unit_status_display(unit.apartment_status)
        else:
            status_val = "-"

        # Keep numerals in English (0-9) for consistency with the app
        floor_val = str(unit.floor_number) if unit.floor_number is not None else "-"
        rooms_val = str(unit.apartment_number) if unit.apartment_number else "-"
        unit_display_num = str(unit_display_num)

        # Format area with 2 decimal places in English numerals
        if unit.area_sqm:
            try:
                area_val = f"{float(unit.area_sqm):.2f} {tr('wizard.unit.area_unit')}"
            except (ValueError, TypeError):
                area_val = "-"
        else:
            area_val = "-"

        # Top Row (Data Grid) - reversed order and evenly distributed
        grid_layout = QHBoxLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Column Data - REVERSED ORDER (was right-to-left, now left-to-right in code)
        # All values converted to Arabic
        data_points = [
            (tr("wizard.unit.unit_number"), unit_display_num),
            (tr("wizard.unit.floor_number"), floor_val),
            (tr("wizard.unit.rooms_count"), rooms_val),
            (tr("wizard.unit.unit_area"), area_val),
            (tr("wizard.unit.unit_type"), unit_type_val),
            (tr("wizard.unit.unit_status"), status_val),
        ]

        # Use helper method for consistent label styling
        for label_text, value_text in data_points:
            col = QVBoxLayout()
            col.setSpacing(2)  # Small gap between title and value
            col.setContentsMargins(8, 0, 8, 0)  # Padding for better spacing
            col.setAlignment(Qt.AlignCenter)  # Center labels and values in column

            # Create labels using helper method
            lbl_title = self._create_field_label(label_text, is_title=True)
            lbl_val = self._create_field_label(str(value_text), is_title=False)

            col.addWidget(lbl_title)
            col.addWidget(lbl_val)
            grid_layout.addLayout(col, stretch=1)  # Evenly distribute columns

        main_layout.addLayout(grid_layout)

        # Dotted divider line - subtle separator
        # Use dotted style for visual separation without being intrusive
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("""
            QFrame {
                border: none;
                border-top: 1px dotted #D1D5DB;
                background: transparent;
            }
        """)
        main_layout.addWidget(divider)

        # Bottom Section (Description)
        desc_layout = QVBoxLayout()
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(2)
        desc_layout.setDirection(QVBoxLayout.TopToBottom)  # Ensure top-to-bottom flow

        # Title: وصف المقسم
        desc_title = QLabel(tr("wizard.unit.unit_description"))
        desc_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        desc_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE};")
        desc_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Left in RTL = Right visually


        # Description text (user-entered OR placeholder)
        desc_text_content = unit.property_description if unit.property_description else tr("wizard.unit.property_description_placeholder")
        desc_text = QLabel(desc_text_content)
        desc_text.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        desc_text.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE};")
        desc_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # Left in RTL = Right visually
        
        desc_text.setWordWrap(True)
        desc_text.setMaximumHeight(ScreenScale.h(40))

        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(desc_text)
        main_layout.addLayout(desc_layout)

        # Checkmark for selected item (always created, visibility toggled)
        check_label = QLabel("✓")
        check_label.setObjectName("checkLabel")
        check_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; font-size: 18px; font-weight: bold; border: none;")
        check_label.setAlignment(Qt.AlignLeft)
        check_label.setVisible(is_selected)
        main_layout.addWidget(check_label)

        return card

    def _refresh_unit_card_styles(self):
        """Update selection highlight and checkmark on existing cards without API re-fetch."""
        selected_id = self.context.unit.unit_uuid if self.context.unit else None
        for i in range(self.units_layout.count()):
            item = self.units_layout.itemAt(i)
            if not item:
                continue
            card = item.widget()
            if not card or not isinstance(card, QFrame) or card.objectName() != "unitCard":
                continue
            unit_id = card.property("unit_id")
            is_selected = (unit_id == selected_id)
            if is_selected:
                card.setStyleSheet("""
                    QFrame#unitCard {
                        background-color: #EBF5FF;
                        border: 2px solid #3890DF;
                        border-radius: 12px;
                    }
                    QFrame#unitCard QLabel { border: none; }
                """)
            else:
                card.setStyleSheet("""
                    QFrame#unitCard {
                        background-color: #FFFFFF;
                        border: 1px solid #E2EAF2;
                        border-radius: 12px;
                    }
                    QFrame#unitCard:hover {
                        border-color: #3890DF;
                        background-color: #F8FAFF;
                    }
                    QFrame#unitCard QLabel { border: none; }
                """)
            # Toggle checkmark visibility
            check_label = card.findChild(QLabel, "checkLabel")
            if check_label:
                check_label.setVisible(is_selected)

    def _on_unit_card_clicked(self, unit):
        """Handle unit card click with toggle functionality."""
        # Toggle functionality: if clicking on already selected unit, deselect it
        if self.context.unit and self.context.unit.unit_uuid == unit.unit_uuid:
            # Deselect the unit
            self.context.unit = None
            self.context.is_new_unit = False
            self.selected_unit = None
            # Update card styles without re-fetching from API
            self._refresh_unit_card_styles()
            # Emit validation changed (no unit selected = invalid)
            self.emit_validation_changed(False)
            logger.info(f"Unit deselected: {unit.unit_id}")
        else:
            # Select the unit
            self.context.unit = unit
            self.context.is_new_unit = False
            self.selected_unit = unit
            # Update card styles without re-fetching from API
            self._refresh_unit_card_styles()
            # Emit validation changed (unit selected = valid)
            self.emit_validation_changed(True)
            logger.info(f"Unit selected: {unit.unit_id}")

    # ── Inline Unit Form ──

    def _show_add_unit_form(self):
        """Show unit creation form in a BottomSheet overlay."""
        form_widget = self._build_unit_form_widget()

        parent = self.window()
        self._unit_sheet = BottomSheet.custom(
            parent,
            tr("wizard.unit_dialog.title_add"),
            form_widget,
            no_buttons=True
        )

    def _cancel_inline_unit(self):
        """Close the BottomSheet."""
        if self._unit_sheet:
            self._unit_sheet.close_sheet()

    def _build_unit_form_widget(self) -> QWidget:
        """Build the unit form fields widget for BottomSheet."""
        form = QWidget()
        form.setStyleSheet("background: transparent; QLabel { background: transparent; border: none; }")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        label_style = "color: #64748B; background: transparent; border: none;"

        # Row 1: Floor number | Unit number
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        self._if_floor = QSpinBox()
        self._if_floor.setRange(-3, 100)
        self._if_floor.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._if_floor.setButtonSymbols(QSpinBox.NoButtons)
        self._if_floor.setFixedHeight(ScreenScale.h(40))
        self._if_floor.setStyleSheet(FORM_FIELD_STYLE)
        row1.addLayout(self._make_bs_field(tr("wizard.unit_dialog.floor_number"), self._if_floor, label_style), 1)

        self._if_unit_num = QSpinBox()
        self._if_unit_num.setRange(0, 9999)
        self._if_unit_num.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._if_unit_num.setButtonSymbols(QSpinBox.NoButtons)
        self._if_unit_num.setFixedHeight(ScreenScale.h(40))
        self._if_unit_num.setStyleSheet(FORM_FIELD_STYLE)
        row1.addLayout(self._make_bs_field(tr("wizard.unit_dialog.unit_number"), self._if_unit_num, label_style), 1)
        form_layout.addLayout(row1)

        # Row 2: Unit type | Unit status
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        self._if_type = RtlCombo()
        self._if_type.setStyleSheet(FORM_FIELD_STYLE)
        self._if_type.setFixedHeight(ScreenScale.h(40))
        self._if_type.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_type_options():
            self._if_type.addItem(label, code)
        row2.addLayout(self._make_bs_field(tr("wizard.unit_dialog.unit_type"), self._if_type, label_style), 1)

        self._if_status = RtlCombo()
        self._if_status.setStyleSheet(FORM_FIELD_STYLE)
        self._if_status.setFixedHeight(ScreenScale.h(40))
        self._if_status.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_status_options():
            self._if_status.addItem(label, code)
        row2.addLayout(self._make_bs_field(tr("wizard.unit_dialog.unit_status"), self._if_status, label_style), 1)
        form_layout.addLayout(row2)

        # Row 3: Rooms | Area
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        self._if_rooms = QSpinBox()
        self._if_rooms.setRange(0, 20)
        self._if_rooms.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._if_rooms.setButtonSymbols(QSpinBox.NoButtons)
        self._if_rooms.setFixedHeight(ScreenScale.h(40))
        self._if_rooms.setStyleSheet(FORM_FIELD_STYLE)
        row3.addLayout(self._make_bs_field(tr("wizard.unit_dialog.rooms"), self._if_rooms, label_style), 1)

        self._if_area = QLineEdit()
        self._if_area.setPlaceholderText(tr("wizard.unit_dialog.area_placeholder"))
        self._if_area.setFixedHeight(ScreenScale.h(40))
        self._if_area.setStyleSheet(FORM_FIELD_STYLE)
        area_validator = QDoubleValidator(0.0, 999999.99, 2, self._if_area)
        area_validator.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        area_validator.setNotation(QDoubleValidator.StandardNotation)
        self._if_area.setValidator(area_validator)
        row3.addLayout(self._make_bs_field(tr("wizard.unit_dialog.area"), self._if_area, label_style), 1)
        form_layout.addLayout(row3)

        # Description (full width)
        self._if_desc = QTextEdit()
        self._if_desc.setMinimumHeight(ScreenScale.h(90))
        self._if_desc.setMaximumHeight(ScreenScale.h(110))
        self._if_desc.setPlaceholderText(tr("wizard.unit_dialog.description_placeholder"))
        self._if_desc.setStyleSheet(FORM_FIELD_STYLE)
        form_layout.addLayout(self._make_bs_field(tr("wizard.unit_dialog.description"), self._if_desc, label_style))

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(ScreenScale.h(44))
        cancel_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        cancel_btn.setStyleSheet(FOOTER_SECONDARY_STYLE)
        cancel_btn.clicked.connect(self._cancel_inline_unit)
        btn_row.addWidget(cancel_btn, 1)

        save_btn = QPushButton(tr("common.save"))
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedHeight(ScreenScale.h(44))
        save_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        save_btn.setStyleSheet(FOOTER_PRIMARY_STYLE)
        save_btn.clicked.connect(self._save_inline_unit)
        btn_row.addWidget(save_btn, 1)

        form_layout.addLayout(btn_row)

        return form

    def _make_bs_field(self, label_text: str, widget, label_style: str = "") -> QVBoxLayout:
        """Create a labeled form field for the BottomSheet form."""
        col = QVBoxLayout()
        col.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(label_style or "color: #64748B; background: transparent; border: none;")
        col.addWidget(lbl)
        col.addWidget(widget)
        return col

    def _save_inline_unit(self):
        """Validate and save the inline unit form via API."""
        target = self._unit_sheet or self.window() or self
        # Basic validation (mirrors UnitDialog._validate_basic)
        if not self._if_type.currentData():
            Toast.show_toast(target, tr("wizard.unit_dialog.select_type_warning"), Toast.WARNING)
            return
        if self._if_unit_num.value() == 0:
            Toast.show_toast(target, tr("wizard.unit_dialog.enter_number_warning"), Toast.WARNING)
            return
        area_text = self._if_area.text().strip()
        if area_text:
            try:
                float(area_text)
            except ValueError:
                Toast.show_toast(target, tr("wizard.unit_dialog.area_numbers_only"), Toast.WARNING)
                return

        # Set auth token
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._api_service.set_access_token(main_window._api_token)
            self.unit_controller.set_auth_token(main_window._api_token)

        # Check uniqueness then create
        def _do_fetch():
            return self.unit_controller.get_units_for_building(self.context.building.building_uuid)

        def _on_fetched(result):
            self._spinner.hide_loading()
            if result.success and result.data:
                unit_number = str(self._if_unit_num.value())
                floor = self._if_floor.value()
                for u in result.data:
                    u_num = getattr(u, 'apartment_number', None) or getattr(u, 'unit_number', None)
                    u_floor = getattr(u, 'floor_number', None)
                    if u_num == unit_number and u_floor == floor:
                        Toast.show_toast(self._unit_sheet or self, tr("wizard.unit_dialog.number_taken"), Toast.WARNING)
                        return
            self._do_create_unit()

        def _on_fetch_error(msg):
            self._spinner.hide_loading()
            logger.error(f"Error checking uniqueness: {msg}")
            self._do_create_unit()

        self._spinner.show_loading(tr("component.loading.default"))
        self._save_worker = ApiWorker(_do_fetch)
        self._save_worker.finished.connect(_on_fetched)
        self._save_worker.error.connect(_on_fetch_error)
        self._save_worker.start()

    def _do_create_unit(self):
        """Create the unit via API after uniqueness check passes."""
        area_text = self._if_area.text().strip()
        area_value = float(area_text) if area_text else None
        unit_data = {
            'unit_uuid': str(uuid.uuid4()),
            'building_id': self.context.building.building_id,
            'building_uuid': self.context.building.building_uuid,
            'unit_type': self._if_type.currentData() or 1,
            'status': self._if_status.currentData() or 1,
            'apartment_status': self._if_status.currentData() or 1,
            'floor_number': self._if_floor.value(),
            'unit_number': str(self._if_unit_num.value()),
            'apartment_number': str(self._if_unit_num.value()),
            'number_of_rooms': self._if_rooms.value(),
            'area_sqm': area_value,
            'property_description': self._if_desc.toPlainText().strip() or None,
        }

        survey_id = self.context.get_data("survey_id")
        if survey_id:
            unit_data['survey_id'] = survey_id

        # Show spinner on BottomSheet so it's visible above the form
        spinner_target = self._unit_sheet or self
        if hasattr(spinner_target, '_spinner'):
            spinner_target._spinner.show_loading(tr("component.loading.default"))
        else:
            self._spinner.show_loading(tr("component.loading.default"))
        try:
            response = self._api_service.create_property_unit(unit_data)
            logger.info("Property unit created successfully via inline form")

            self.context.is_new_unit = True
            self.context.new_unit_data = unit_data

            api_uuid = None
            if response:
                api_uuid = response.get('id') or response.get('unitUuid')
            if api_uuid:
                logger.info(f"Using API-generated unit UUID: {api_uuid}")
                self.context.new_unit_data['unit_uuid'] = api_uuid

            # Close BottomSheet and refresh units list
            if self._unit_sheet:
                self._unit_sheet.close_sheet()

            # Store UUID for auto-selection after async load completes
            self._pending_auto_select_uuid = api_uuid
            self._loaded_building_uuid = None
            self._load_units()

        except Exception as e:
            logger.error(f"API unit creation failed: {e}")
            target = self._unit_sheet or self.window() or self
            if "409" in str(e):
                Toast.show_toast(target, tr("wizard.unit_dialog.duplicate_unit"), Toast.ERROR)
            else:
                Toast.show_toast(target, str(e), Toast.ERROR)
        finally:
            if hasattr(spinner_target, '_spinner'):
                spinner_target._spinner.hide_loading()
            else:
                self._spinner.hide_loading()

    # _make_icon_header is now shared via wizard_styles.make_icon_header

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        self.setLayoutDirection(get_layout_direction())
        if hasattr(self, 'add_unit_btn'):
            self.add_unit_btn.setText(tr("wizard.unit.add_button"))
        if hasattr(self, '_units_header_title'):
            self._units_header_title.setText(tr("wizard.unit.select_title"))
            self._units_header_subtitle.setText(tr("wizard.unit.select_subtitle"))
        if hasattr(self, '_lbl_status'):
            self._lbl_status.setText(tr("wizard.building.status"))
            self._lbl_type.setText(tr("wizard.building.type"))
            self._lbl_units.setText(tr("wizard.building.units_count"))
            self._lbl_parcels.setText(tr("wizard.building.parcels_count"))
            self._lbl_shops.setText(tr("wizard.building.shops_count"))
        # Reload unit cards with new language
        if self.context.building:
            self._loaded_building_uuid = None  # Force re-render with new language
            self._load_units()

    def validate(self) -> StepValidationResult:
        """Validate the step. Linking is performed asynchronously via on_next."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error(tr("wizard.unit.no_building_error"))
            return result

        if not self.selected_unit and not self.context.is_new_unit:
            result.add_error(tr("wizard.unit.select_or_create_error"))
            return result

        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            result.add_error(tr("wizard.unit.no_survey_error"))
            return result

        current_unit_id = None
        if self.selected_unit and self.selected_unit != "new_unit":
            current_unit_id = getattr(self.selected_unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            current_unit_id = self.context.new_unit_data.get('unit_uuid')

        if not survey_id or not current_unit_id:
            result.add_error(tr("wizard.unit.no_survey_or_unit_error"))
            return result

        # Guard: skip if same unit already linked
        if self.context.get_data("unit_linked"):
            previous_unit_id = self.context.get_data("linked_unit_uuid")
            if previous_unit_id == current_unit_id:
                logger.info(f"Unit already linked ({current_unit_id}), skipping")
                return result
            else:
                logger.info(f"Unit changed ({previous_unit_id} -> {current_unit_id}), patching relations")
                cleaned = False
                try:
                    self.context.cleanup_on_unit_change(self._api_service, new_unit_id=current_unit_id)
                    cleaned = True
                except Exception as e:
                    logger.warning(f"API cleanup failed, doing local cleanup: {e}")

                if not cleaned:
                    for person in self.context.persons:
                        person['_relation_id'] = None
                    self.context.relations = []
                    self.context.claims = []
                    self.context.finalize_response = None
                    for key in ("unit_linked", "linked_unit_uuid",
                                "claims_count", "created_claims"):
                        self.context.update_data(key, None)

        # Link unit synchronously — block progression if it fails
        if not self.context.get_data("unit_linked"):
            self._set_auth_token()
            self._spinner.show_loading(tr("component.loading.default"))
            try:
                self._api_service.link_unit_to_survey(survey_id, current_unit_id)
                logger.info(f"Unit {current_unit_id} linked to survey {survey_id}")
                self.context.update_data("unit_linked", True)
                self.context.update_data("linked_unit_uuid", current_unit_id)
            except Exception as e:
                logger.error(f"API link failed: {e}")
                result.add_error(tr("wizard.unit.link_failed"))
                return result
            finally:
                self._spinner.hide_loading()

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "unit_id": self.selected_unit.unit_id if self.selected_unit else None,
            "unit_uuid": self.selected_unit.unit_uuid if self.selected_unit else None,
            "is_new_unit": self.context.is_new_unit,
            "new_unit_data": self.context.new_unit_data
        }

    def populate_data(self):
        """Populate the step with data from context."""
        # Load units for the building
        self._load_units()

        # Restore selected unit if exists
        if self.context.unit:
            self.selected_unit = self.context.unit
            # Emit validation - unit is already selected
            self.emit_validation_changed(True)

    def on_show(self):
        """Called when step is shown."""
        # Set auth token before populate_data (called by super) loads units
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self.unit_controller.set_auth_token(main_window._api_token)

        super().on_show()

    def get_step_title(self) -> str:
        """Get step title."""
        return tr("wizard.unit.step_title")

    def get_step_description(self) -> str:
        """Get step description."""
        return tr("wizard.unit.step_description")
