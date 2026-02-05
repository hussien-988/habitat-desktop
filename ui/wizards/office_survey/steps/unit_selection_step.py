# -*- coding: utf-8 -*-
"""
Unit Selection Step - Step 2 of Office Survey Wizard.

Allows user to:
- View existing units in the selected building
- Select an existing unit
- Create a new unit with validation
"""

from typing import Dict, Any, Optional, List

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QWidget, QMessageBox, QGroupBox,
    QComboBox, QSpinBox, QTextEdit, QDialog, QFormLayout,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor, QIcon, QColor

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from controllers.unit_controller import UnitController
from models.unit import PropertyUnit as Unit
from app.config import Config
from utils.logger import get_logger
from utils.helpers import build_hierarchical_address
from ui.design_system import Colors
from ui.components.icon import Icon
from ui.components.action_button import ActionButton
from ui.font_utils import create_font, FontManager

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
        # No horizontal padding - wizard applies 131px (DRY principle)
        # Only vertical spacing between elements
        # Best Practice: Adjusted top margin to match visual spacing of building_selection_step
        layout.setContentsMargins(0, 8, 0, 16)  # Top: 8px (reduced for visual consistency), Bottom: 16px
        layout.setSpacing(10)  # Reduced spacing: 10px between cards (was 15px)

        # Selected building info card - same design as building_selection_step stats card
        # Height: 113px, includes address row + stats sections
        self.unit_building_frame = QFrame()
        self.unit_building_frame.setObjectName("unitBuildingInfoCard")
        self.unit_building_frame.setFixedHeight(113)  # Height: 113px total
        self.unit_building_frame.setStyleSheet(f"""
            QFrame#unitBuildingInfoCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)

        # Apply subtle shadow effect for visual separation from tabs
        # Best Practice: Consistent shadow across all wizard steps
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)  # Soft blur
        shadow.setXOffset(0)  # Centered shadow
        shadow.setYOffset(2)  # Slight offset downward
        shadow.setColor(QColor(0, 0, 0, 30))  # Lighter shadow (alpha: 30 - reduced from 60)
        self.unit_building_frame.setGraphicsEffect(shadow)

        # Main card layout
        card_layout = QVBoxLayout(self.unit_building_frame)
        card_layout.setContentsMargins(12, 12, 12, 12)  # Padding: 12px all sides
        card_layout.setSpacing(12)  # Gap between rows

        # ===== ROW 1: Building Address =====
        # Height: 28px, full width, border-radius 8px (suitable for 28px height), background #F8FAFF
        # Best Practice: border-radius should be proportional to height (28/3.5 ≈ 8px)
        address_container = QFrame()
        address_container.setFixedHeight(28)
        address_container.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: none;
                border-radius: 8px;
            }
        """)

        # DRY: Centered layout with icon + text
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
        # SOLID: Single Responsibility - displays building address only
        self.unit_building_address = QLabel("عنوان البناء")
        self.unit_building_address.setAlignment(Qt.AlignCenter)
        self.unit_building_address.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
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

        # ===== ROW 2: Building Stats (5 sections) =====
        # Same design as building_selection_step stats sections
        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)  # Equal distribution

        # Helper function to create stat section (label on top, value below)
        def _create_stat_section(label_text, value_text="-"):
            """Create a stat section with label on top and value below."""
            section = QWidget()
            section.setStyleSheet("background: transparent;")

            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(8, 0, 8, 0)  # Padding for better spacing
            section_layout.setSpacing(4)
            section_layout.setAlignment(Qt.AlignLeft)  # Start from same point (right in RTL)

            # Label (top text) - smaller font, left aligned (starts from right in RTL)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignLeft)  # Start from same point
            label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))  # Smaller: 9pt
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

            # Value (bottom text) - smaller font, RIGHT aligned
            value = QLabel(value_text)
            value.setAlignment(Qt.AlignRight)  # Right alignment for values
            value.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))  # Smaller: 9pt
            value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

            section_layout.addWidget(label)
            section_layout.addWidget(value)

            return section, value

        # Create 5 stat sections
        section_type, self.ui_building_type = _create_stat_section("نوع البناء")
        section_status, self.ui_building_status = _create_stat_section("حالة البناء")
        section_units, self.ui_units_count = _create_stat_section("عدد الوحدات")
        section_parcels, self.ui_parcels_count = _create_stat_section("عدد المقاسم")
        section_shops, self.ui_shops_count = _create_stat_section("عدد المحلات")

        # Add sections with equal spacing
        sections = [section_type, section_status, section_units, section_parcels, section_shops]
        for section in sections:
            stats_row.addWidget(section, stretch=1)

        card_layout.addLayout(stats_row)

        layout.addWidget(self.unit_building_frame)

        # Figma: Units Container Card (Card 2)
        # Dimensions: 1249×372 (width×height), border-radius: 8px, padding: 12px
        # Gap from Card 1: 15px (handled by layout.setSpacing(15))
        units_main_frame = QFrame()
        units_main_frame.setObjectName("unitsContainerCard")
        # DRY: Fixed dimensions from Figma (width × height)
        units_main_frame.setFixedSize(1249, 372)
        # SOLID: Separation of concerns - styling in stylesheet, spacing in layout
        units_main_frame.setStyleSheet("""
            QFrame#unitsContainerCard {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)

        # Apply subtle shadow effect for visual depth
        # Best Practice: Consistent shadow across all cards
        shadow2 = QGraphicsDropShadowEffect()
        shadow2.setBlurRadius(8)
        shadow2.setXOffset(0)
        shadow2.setYOffset(2)
        shadow2.setColor(QColor(0, 0, 0, 30))  # Lighter shadow (alpha: 30 - reduced from 60)
        units_main_frame.setGraphicsEffect(shadow2)

        # Best Practice: Use layout margins instead of CSS padding (more predictable)
        units_main_layout = QVBoxLayout(units_main_frame)
        units_main_layout.setSpacing(12)
        # Adjusted: Internal padding 11px all sides (reduced to prevent card clipping)
        units_main_layout.setContentsMargins(11, 11, 11, 11)

        # Figma: Header with title/subtitle on right and button on left
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)  # No spacing, manual control
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Right side: Icon container + Title and subtitle
        right_header = QHBoxLayout()
        right_header.setSpacing(8)  # Gap between icon container and text

        # DRY: Icon container (48×48, background #F0F7FF, small border-radius)
        # Best Practice: Reusable pattern for icon containers
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

        # Load move.png icon
        icon_label = QLabel()
        icon_pixmap = Icon.load_pixmap("move", size=24)  # Reasonable size for 48×48 container
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("🏘️")  # Fallback emoji
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_container_layout.addWidget(icon_label)

        right_header.addWidget(icon_container)

        # Title and subtitle (Figma: 14px → 10.5pt)
        title_subtitle_layout = QVBoxLayout()
        title_subtitle_layout.setSpacing(2)
        title_subtitle_layout.setContentsMargins(0, 0, 0, 0)

        # DRY: Use FontManager for consistent font sizing
        # Figma: 14px × 0.75 = 10.5pt (rounded to 10pt for cleaner rendering)
        # Increased weight to emphasize title (SemiBold instead of Regular)
        # RTL: Text ends at the same point as subtitle, but starts further right
        title_label = QLabel("اختر الوحدة العقارية")
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet("""
            QLabel {
                color: #1A1F1D;
                border: none;
                background: transparent;
            }
        """)
        # Fix RTL alignment: AlignLeft makes RTL text end at the same point as subtitle
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_subtitle_layout.addWidget(title_label)

        # Subtitle with same font size, different color
        subtitle_label = QLabel("اختر أو أضف معلومات الوحدة العقارية")
        subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #86909B;
                border: none;
                background: transparent;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(subtitle_label)

        right_header.addLayout(title_subtitle_layout)
        header_layout.addLayout(right_header)
        header_layout.addStretch()

        # Left side: Add unit button (Figma: 125×44, outline variant)
        # DRY: Use ActionButton component (Single Source of Truth)
        # Figma specs: background #F0F7FF, border #3890DF, border-radius 8px
        self.add_unit_btn = ActionButton(
            text="أضف وحدة",
            variant="outline",
            icon_name="icon",
            width=125,
            height=44
        )
        self.add_unit_btn.clicked.connect(self._show_add_unit_dialog)
        header_layout.addWidget(self.add_unit_btn)

        units_main_layout.addLayout(header_layout)

        # Units list container (inside white frame)
        self.units_container = QWidget()
        self.units_layout = QVBoxLayout(self.units_container)
        self.units_layout.setSpacing(10)
        self.units_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for units (hidden scrollbar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.units_container)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)
        units_main_layout.addWidget(scroll, 1)

        layout.addWidget(units_main_frame, 1)

    def _load_units(self):
        """Load units for the selected building and display as cards."""
        if not self.context.building:
            # Clear all units when no building is selected (new wizard)
            self.unit_building_frame.setVisible(False)
            # Clear existing unit cards
            while self.units_layout.count():
                child = self.units_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            # Clear selected unit
            self.selected_unit = None
            self.emit_validation_changed(False)
            return

        # Populate building info card
        # SOLID: Single Responsibility - each field displays one piece of data
        # DRY: Reuse building object instead of repeating property access
        building = self.context.building

        # Update address using DRY helper function (Single Source of Truth)
        # Format: "حلب - المنطقة - الناحية - الحي - رقم البناء"
        # Best Practice: Use centralized helper instead of duplicating logic
        address = build_hierarchical_address(
            building_obj=building,
            unit_obj=None,  # Don't include unit number in building info card
            separator=" - ",
            include_unit=False
        )
        self.unit_building_address.setText(address)

        # Update stats - DRY: consistent pattern for all fields
        self.ui_building_type.setText(building.building_type_display or "-")
        self.ui_building_status.setText(building.building_status_display or "-")
        self.ui_units_count.setText(str(building.number_of_units or 0))
        self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
        self.ui_shops_count.setText(str(building.number_of_shops or 0))

        # Show the card after populating data
        self.unit_building_frame.setVisible(True)

        # Clear existing unit cards
        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Load units from database
        result = self.unit_controller.get_units_for_building(self.context.building.building_uuid)

        if not result.success:
            logger.error(f"Failed to load units: {result.message}")
            # Show empty state
            empty_label = QLabel("⚠️ خطأ في تحميل الوحدات")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #EF4444; font-size: 14px; padding: 40px;")
            self.units_layout.addWidget(empty_label)
            self.units_layout.addStretch()
            return

        units = result.data

        if units:
            for unit in units:
                unit_card = self._create_unit_card(unit)
                self.units_layout.addWidget(unit_card)
        else:
            # Empty state message
            empty_label = QLabel("📭 لا توجد وحدات مسجلة. انقر على 'أضف وحدة' لإضافة وحدة جديدة")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("""
                color: #9CA3AF;
                font-size: 14px;
                padding: 40px;
            """)
            self.units_layout.addWidget(empty_label)

        self.units_layout.addStretch()

    def _to_arabic_numerals(self, text: str) -> str:
        """
        DRY: Convert English/Latin numerals to Arabic-Indic numerals.

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
        DRY: Create a label with consistent styling.

        Args:
            text: Label text
            is_title: True for title style (like "اختر الوحدة العقارية"),
                     False for value style (like subtitle)

        Returns:
            Configured QLabel
        """
        label = QLabel(text)

        if is_title:
            # Title style - smaller font, left aligned (appears right in RTL)
            label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))  # Smaller: 9pt
            label.setStyleSheet("color: #1A1F1D;")
            label.setAlignment(Qt.AlignLeft)  # Left in RTL = Right visually
        else:
            # Value style - smaller font, left aligned (appears right in RTL)
            label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))  # Smaller: 9pt
            label.setStyleSheet("color: #86909B;")
            label.setAlignment(Qt.AlignLeft)  # Left in RTL = Right visually

        return label

    def _create_unit_card(self, unit) -> QFrame:
        """
        Create a unit card widget with Figma specifications.

        Figma specs:
        - Dimensions: 1225×138 (width×height)
        - Padding: 12px all sides
        - Border-radius: 10px
        - Gap between top and bottom sections: 8px
        """
        # Determine unit display number (from unit_number or apartment_number)
        unit_display_num = unit.unit_number or unit.apartment_number or "?"

        # Check if this is the selected unit
        is_selected = self.context.unit and self.context.unit.unit_id == unit.unit_id

        # Create card frame - Figma: 1225×138
        card = QFrame()
        card.setObjectName("unitCard")
        card.setFixedSize(1225, 138)

        # Different styles for selected and normal cards
        if is_selected:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #f0f7ff;
                    border: 2px solid #3498db;
                    border-radius: 10px;
                }
                QFrame#unitCard QLabel {
                    border: none;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 10px;
                }
                QFrame#unitCard:hover {
                    border-color: #3498db;
                    background-color: #f9fbfd;
                }
                QFrame#unitCard QLabel {
                    border: none;
                }
            """)

        # Apply subtle shadow effect for depth
        # Best Practice: Consistent shadow like other cards
        card_shadow = QGraphicsDropShadowEffect()
        card_shadow.setBlurRadius(8)
        card_shadow.setXOffset(0)
        card_shadow.setYOffset(2)
        card_shadow.setColor(QColor(0, 0, 0, 30))  # Subtle shadow
        card.setGraphicsEffect(card_shadow)

        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda _: self._on_unit_card_clicked(unit)
        card.setLayoutDirection(Qt.RightToLeft)

        # Main layout - Figma: padding 12px all sides
        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(8)  # Gap between top and bottom: 8px
        main_layout.setContentsMargins(12, 12, 12, 12)  # Padding: 12px

        # Get unit data with Arabic text
        # DRY: Use Arabic display properties from model
        unit_type_val = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else (unit.unit_type or "-")

        # Get Arabic status (use property if exists, otherwise translate manually)
        if hasattr(unit, 'apartment_status'):
            status_mappings = {
                "occupied": "مشغولة",
                "vacant": "شاغرة",
                "unknown": "غير معروف"
            }
            status_val = status_mappings.get(unit.apartment_status, unit.apartment_status)
        else:
            status_val = "جيدة"

        # Keep numerals in English (0-9) for consistency with the app
        floor_val = str(unit.floor_number) if unit.floor_number is not None else "-"
        rooms_val = str(getattr(unit, 'number_of_rooms', 0)) if hasattr(unit, 'number_of_rooms') else "-"
        unit_display_num = str(unit_display_num)

        # Format area with 2 decimal places in English numerals
        if unit.area_sqm:
            try:
                area_val = f"{float(unit.area_sqm):.2f} م²"
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
            ("رقم الوحدة", unit_display_num),
            ("رقم الطابق", floor_val),
            ("عدد الغرف", rooms_val),
            ("مساحة القسم", area_val),
            ("نوع الوحدة", unit_type_val),
            ("حالة الوحدة", status_val),
        ]

        # DRY: Use helper method for consistent label styling
        for label_text, value_text in data_points:
            col = QVBoxLayout()
            col.setSpacing(2)  # Small gap between title and value
            col.setContentsMargins(8, 0, 8, 0)  # Padding for better spacing

            # DRY: Create labels using helper method
            lbl_title = self._create_field_label(label_text, is_title=True)
            lbl_val = self._create_field_label(str(value_text), is_title=False)

            col.addWidget(lbl_title)
            col.addWidget(lbl_val)
            grid_layout.addLayout(col, stretch=1)  # Evenly distribute columns

        main_layout.addLayout(grid_layout)

        # Dotted divider line - subtle separator
        # Best Practice: Use dotted style for visual separation without being intrusive
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

        # Title: وصف العقار
        desc_title = QLabel("وصف العقار")
        desc_title.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))  # Smaller: 9pt
        desc_title.setStyleSheet("color: #1A1F1D;")
        desc_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Left in RTL = Right visually


        # Description text (user-entered OR placeholder)
        desc_text_content = unit.property_description if unit.property_description else "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة."
        desc_text = QLabel(desc_text_content)
        desc_text.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))  # Smaller: 9pt
        desc_text.setStyleSheet("color: #86909B;")
        desc_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # Left in RTL = Right visually
        
        desc_text.setWordWrap(True)
        desc_text.setMaximumHeight(40)

        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(desc_text)
        main_layout.addLayout(desc_layout)

        # Checkmark for selected item
        if is_selected:
            check_label = QLabel("✓")
            check_label.setStyleSheet("color: #3498db; font-size: 18px; font-weight: bold; border: none;")
            check_label.setAlignment(Qt.AlignLeft)
            main_layout.addWidget(check_label)

        return card

    def _on_unit_card_clicked(self, unit):
        """Handle unit card click with toggle functionality."""
        # Toggle functionality: if clicking on already selected unit, deselect it
        if self.context.unit and self.context.unit.unit_id == unit.unit_id:
            # Deselect the unit
            self.context.unit = None
            self.context.is_new_unit = False
            self.selected_unit = None
            # Refresh cards to remove selection highlight
            self._load_units()
            # Emit validation changed (no unit selected = invalid)
            self.emit_validation_changed(False)
            logger.info(f"Unit deselected: {unit.unit_id}")
        else:
            # Select the unit
            self.context.unit = unit
            self.context.is_new_unit = False
            self.selected_unit = unit
            # Refresh cards to show selection
            self._load_units()
            # Emit validation changed (unit selected = valid)
            self.emit_validation_changed(True)
            logger.info(f"Unit selected: {unit.unit_id}")

    def _show_add_unit_dialog(self):
        """Show dialog to add a new unit - uses API to create unit."""
        from ui.wizards.office_survey.dialogs.unit_dialog import UnitDialog

        # Get auth token from main window if available
        auth_token = None
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            auth_token = main_window._api_token

        # Get survey_id from context (created in step 1)
        survey_id = self.context.get_data("survey_id")

        dialog = UnitDialog(
            self.context.building,
            self.context.db,
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id
        )

        if dialog.exec_() == QDialog.Accepted:
            # Unit was created via API (if using API mode)
            # Store the unit data in context
            self.context.is_new_unit = True
            self.context.new_unit_data = dialog.get_unit_data()

            # Mark as having a selected unit (even though it's new)
            # This allows validation to pass
            self.selected_unit = "new_unit"  # Placeholder to indicate new unit

            # Enable next button by emitting validation changed
            self.emit_validation_changed(True)

            # Refresh units list to show the newly created unit
            self._load_units()

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error("لا يوجد مبنى مختار! يرجى العودة للخطوة السابقة")

        # Check if unit is selected OR new unit is being created
        if not self.selected_unit and not self.context.is_new_unit:
            result.add_error("يجب اختيار وحدة أو إنشاء وحدة جديدة للمتابعة")

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
        super().on_show()

        # Set auth token for API calls if available (may not be set in __init__)
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self.unit_controller.set_auth_token(main_window._api_token)

        # Reload units when step is shown
        self._load_units()

    def get_step_title(self) -> str:
        """Get step title."""
        return "اختيار الوحدة العقارية"

    def get_step_description(self) -> str:
        """Get step description."""
        return "اختر وحدة موجودة أو أنشئ وحدة جديدة في المبنى المختار"
