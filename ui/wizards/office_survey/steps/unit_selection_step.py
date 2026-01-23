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
    QComboBox, QSpinBox, QTextEdit, QDialog, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor, QIcon

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from controllers.unit_controller import UnitController
from models.unit import PropertyUnit as Unit
from app.config import Config
from utils.logger import get_logger

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

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        layout = self.main_layout
        # No horizontal padding - wizard applies 131px (DRY principle)
        # Only vertical spacing between elements
        layout.setContentsMargins(0, 16, 0, 16)  # Top: 16px, Bottom: 16px
        layout.setSpacing(16)

        # Selected building info card (search + metrics layout)
        self.unit_building_frame = QFrame()
        self.unit_building_frame.setObjectName("unitBuildingInfoCard")
        self.unit_building_frame.setStyleSheet("""
            QFrame#unitBuildingInfoCard {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)

        # Card layout
        self.unit_building_layout = QVBoxLayout(self.unit_building_frame)
        self.unit_building_layout.setSpacing(14)
        self.unit_building_layout.setContentsMargins(14, 14, 14, 14)

        # Building address row with icon (centered with border)
        address_container = QFrame()
        address_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)

        address_row = QHBoxLayout(address_container)
        address_row.setSpacing(8)
        address_row.setContentsMargins(8, 8, 8, 8)

        # Add stretch to center the content
        address_row.addStretch()

        # Building icon
        building_icon = QLabel("🏢")
        building_icon.setStyleSheet("""
            QLabel {
                font-size: 16px;
                border: none;
                background-color: transparent;
            }
        """)
        building_icon.setAlignment(Qt.AlignCenter)
        address_row.addWidget(building_icon)

        # Building address label
        self.unit_building_address = QLabel("حلب الحميدية")
        self.unit_building_address.setAlignment(Qt.AlignCenter)
        self.unit_building_address.setStyleSheet("""
            QLabel {
                border: none;
                background-color: transparent;
                font-size: 12px;
                color: #6B7280;
                font-weight: 500;
            }
        """)
        address_row.addWidget(self.unit_building_address)

        # Add stretch to center the content
        address_row.addStretch()

        self.unit_building_layout.addWidget(address_container)

        # Metrics row container
        self.unit_building_metrics_layout = QHBoxLayout()
        self.unit_building_metrics_layout.setSpacing(22)
        self.unit_building_layout.addLayout(self.unit_building_metrics_layout)

        layout.addWidget(self.unit_building_frame)

        # White container frame for all units
        units_main_frame = QFrame()
        units_main_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        units_main_layout = QVBoxLayout(units_main_frame)
        units_main_layout.setSpacing(12)
        units_main_layout.setContentsMargins(16, 16, 16, 16)

        # Header with title/subtitle on right and button on left
        header_layout = QHBoxLayout()

        # Right side: Icon + Title and subtitle
        right_header = QHBoxLayout()
        right_header.setSpacing(8)

        # Icon
        icon_label = QLabel("🏘️")
        icon_label.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        right_header.addWidget(icon_label)

        # Title and subtitle
        title_subtitle_layout = QVBoxLayout()
        title_subtitle_layout.setSpacing(2)

        title_label = QLabel("اختر الوحدة العقارية")
        title_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 200;
            color: #111827;
            border: none;
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(title_label)

        subtitle_label = QLabel("اختر أو أضف معلومات الوحدة العقارية")
        subtitle_label.setStyleSheet("""
            font-size: 9px;
            font-weight: 100;
            color: #6B7280;
            border: none;
            background: transparent;
        """)
        subtitle_label.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(subtitle_label)

        right_header.addLayout(title_subtitle_layout)
        header_layout.addLayout(right_header)
        header_layout.addStretch()

        # Left side: Add unit button
        self.add_unit_btn = QPushButton("أضف وحدة")
        self.add_unit_btn.setIcon(QIcon.fromTheme("list-add"))
        self.add_unit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #005A9C;
            }}
        """)
        self.add_unit_btn.clicked.connect(self._show_add_unit_dialog)
        header_layout.addWidget(self.add_unit_btn)

        units_main_layout.addLayout(header_layout)

        # Units list container (inside white frame)
        self.units_container = QWidget()
        self.units_layout = QVBoxLayout(self.units_container)
        self.units_layout.setSpacing(10)
        self.units_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for units
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.units_container)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)
        units_main_layout.addWidget(scroll, 1)

        layout.addWidget(units_main_frame, 1)

    def _load_units(self):
        """Load units for the selected building and display as cards - exact copy from old wizard."""
        if not self.context.building:
            return

        # Populate building info (simple text display)
        if hasattr(self, 'unit_building_label'):
            self.unit_building_label.setText(
                f"🏢 المبنى المحدد: {self.context.building.building_id}"
            )

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

    def _create_unit_card(self, unit) -> QFrame:
        """Create a unit card widget matching the exact photo layout - exact copy from old wizard."""
        # Determine unit display number (from unit_number or apartment_number)
        unit_display_num = unit.unit_number or unit.apartment_number or "?"

        # Check if this is the selected unit
        is_selected = self.context.unit and self.context.unit.unit_id == unit.unit_id

        # Create card frame
        card = QFrame()
        card.setObjectName("unitCard")

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
                    color: #2c3e50;
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
                    color: #2c3e50;
                }
            """)

        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda _: self._on_unit_card_clicked(unit)
        card.setLayoutDirection(Qt.RightToLeft)

        # Main layout
        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Get unit data
        unit_type_val = unit.unit_type_display if hasattr(unit, 'unit_type_display') else unit.unit_type
        status_val = unit.apartment_status_display if hasattr(unit, 'apartment_status_display') else unit.apartment_status or "جيدة"
        floor_val = str(unit.floor_number) if unit.floor_number is not None else "-"
        rooms_val = str(getattr(unit, 'number_of_rooms', 0)) if hasattr(unit, 'number_of_rooms') else "-"
        area_val = f"{unit.area_sqm}" if unit.area_sqm else "120"

        # Top Row (Data Grid)
        grid_layout = QHBoxLayout()
        grid_layout.setContentsMargins(20, 15, 20, 15)
        grid_layout.setSpacing(10)

        # Column Data (In order for RTL)
        data_points = [
            ("حالة الوحدة", status_val),
            ("نوع الوحدة", unit_type_val),
            ("مساحة القسم", f"{area_val} (م²)"),
            ("عدد الغرف", rooms_val),
            ("رقم الطابق", floor_val),
            ("رقم الوحدة", str(unit_display_num)),
        ]

        for label_text, value_text in data_points:
            col = QVBoxLayout()
            col.setSpacing(4)

            lbl_title = QLabel(label_text)
            lbl_title.setStyleSheet("font-weight: bold; color: #333; font-size: 11px;")
            lbl_title.setAlignment(Qt.AlignCenter)

            lbl_val = QLabel(str(value_text))
            lbl_val.setStyleSheet("color: #666; font-size: 11px;")
            lbl_val.setAlignment(Qt.AlignCenter)

            col.addWidget(lbl_title)
            col.addWidget(lbl_val)
            grid_layout.addLayout(col)

        main_layout.addLayout(grid_layout)

        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #eeeeee; border: none; max-height: 1px;")
        main_layout.addWidget(line)

        # Bottom Section (Description)
        desc_layout = QVBoxLayout()
        desc_layout.setContentsMargins(20, 12, 20, 15)
        desc_layout.setSpacing(6)

        desc_title = QLabel("وصف العقار")
        desc_title.setStyleSheet("font-weight: bold; color: #333; font-size: 11px;")

        desc_text_content = unit.property_description if unit.property_description else "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة."
        desc_text = QLabel(desc_text_content)
        desc_text.setStyleSheet("color: #7f8c8d; font-size: 10px;")
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
        """Handle unit card click - exact copy from old wizard."""
        self.context.unit = unit
        self.context.is_new_unit = False
        self.selected_unit = unit
        # Refresh cards to show selection
        self._load_units()

        # Emit validation changed
        self.emit_validation_changed(True)

        logger.info(f"Unit selected: {unit.unit_id}")

    def _show_add_unit_dialog(self):
        """Show dialog to add a new unit - exact copy from old wizard."""
        from ui.wizards.office_survey.dialogs.unit_dialog import UnitDialog

        dialog = UnitDialog(self.context.building, self.context.db, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            # Create new unit (will be saved when moving forward)
            self.context.is_new_unit = True
            self.context.new_unit_data = dialog.get_unit_data()

            # Mark as having a selected unit (even though it's new)
            # This allows validation to pass
            self.selected_unit = "new_unit"  # Placeholder to indicate new unit

            # Enable next button by emitting validation changed
            self.emit_validation_changed(True)

            QMessageBox.information(self, "تم", "سيتم إضافة الوحدة عند إتمام الاستمارة")

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
        # Reload units when step is shown
        self._load_units()

    def get_step_title(self) -> str:
        """Get step title."""
        return "اختيار الوحدة العقارية"

    def get_step_description(self) -> str:
        """Get step description."""
        return "اختر وحدة موجودة أو أنشئ وحدة جديدة في المبنى المختار"
