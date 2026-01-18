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
from PyQt5.QtGui import QCursor

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from repositories.unit_repository import UnitRepository
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
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)
        self.unit_repo = UnitRepository(self.context.db)
        self.selected_unit: Optional[Unit] = None

    def setup_ui(self):
        """Setup the step's UI."""
        # Header
        header = QLabel("الخطوة 2: اختيار أو إنشاء الوحدة العقارية")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        # Description
        desc = QLabel("اختر وحدة موجودة أو أنشئ وحدة جديدة")
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 16px;")
        self.main_layout.addWidget(desc)

        # Building info card
        building_info = self._create_building_info_card()
        self.main_layout.addWidget(building_info)

        # Units section
        units_section = self._create_units_section()
        self.main_layout.addWidget(units_section, 1)

        # Selected unit info
        self.selected_info = QLabel("لم يتم اختيار وحدة")
        self.selected_info.setStyleSheet("""
            background-color: #ecf0f1;
            padding: 12px;
            border-radius: 4px;
            color: #7f8c8d;
        """)
        self.main_layout.addWidget(self.selected_info)

    def _create_building_info_card(self) -> QGroupBox:
        """Create building information card."""
        group = QGroupBox("معلومات المبنى المختار")
        layout = QVBoxLayout(group)

        if self.context.building:
            # Building ID
            building_id_label = QLabel(f"🏢 رمز المبنى: {self.context.building.building_id}")
            building_id_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(building_id_label)

            # Address
            address = self.context.building.address or "غير محدد"
            address_label = QLabel(f"📍 العنوان: {address}")
            layout.addWidget(address_label)

            # Type and Status
            info_layout = QHBoxLayout()
            type_label = QLabel(f"النوع: {self.context.building.building_type_display or 'غير محدد'}")
            status_label = QLabel(f"الحالة: {self.context.building.building_status_display or 'غير محدد'}")
            info_layout.addWidget(type_label)
            info_layout.addWidget(status_label)
            info_layout.addStretch()
            layout.addLayout(info_layout)
        else:
            error_label = QLabel("⚠️ لم يتم اختيار مبنى!")
            error_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            layout.addWidget(error_label)

        return group

    def _create_units_section(self) -> QWidget:
        """Create units list section."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with add button
        header_layout = QHBoxLayout()

        units_label = QLabel("الوحدات الموجودة")
        units_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(units_label)

        header_layout.addStretch()

        # Add unit button
        self.add_unit_btn = QPushButton("+ أضف وحدة جديدة")
        self.add_unit_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.add_unit_btn.clicked.connect(self._show_add_unit_dialog)
        header_layout.addWidget(self.add_unit_btn)

        layout.addLayout(header_layout)

        # Scroll area for units
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
        """)

        # Units container
        self.units_container = QWidget()
        self.units_layout = QVBoxLayout(self.units_container)
        self.units_layout.setSpacing(10)
        self.units_layout.setContentsMargins(10, 10, 10, 10)

        scroll.setWidget(self.units_container)
        layout.addWidget(scroll, 1)

        return container

    def _load_units(self):
        """Load units for the selected building."""
        # Clear existing units
        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.context.building:
            empty_label = QLabel("⚠️ لا يوجد مبنى مختار")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #7f8c8d; padding: 40px;")
            self.units_layout.addWidget(empty_label)
            return

        # Load units from repository
        try:
            units = self.unit_repo.get_by_building(self.context.building.building_id)

            if units:
                for unit in units:
                    unit_card = self._create_unit_card(unit)
                    self.units_layout.addWidget(unit_card)
            else:
                # Empty state
                empty_label = QLabel("📭 لا توجد وحدات مسجلة.\nانقر على 'أضف وحدة جديدة' لإضافة وحدة.")
                empty_label.setAlignment(Qt.AlignCenter)
                empty_label.setStyleSheet("""
                    color: #9CA3AF;
                    font-size: 14px;
                    padding: 40px;
                """)
                self.units_layout.addWidget(empty_label)

            self.units_layout.addStretch()

        except Exception as e:
            logger.error(f"Error loading units: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء تحميل الوحدات: {str(e)}"
            )

    def _create_unit_card(self, unit: Unit) -> QFrame:
        """Create a unit card widget."""
        # Check if selected
        is_selected = self.selected_unit and self.selected_unit.unit_id == unit.unit_id

        # Create card
        card = QFrame()
        card.setObjectName("unitCard")

        # Style based on selection
        if is_selected:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #d5f4e6;
                    border: 2px solid #27ae60;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 12px;
                }
                QFrame#unitCard:hover {
                    border-color: #3498db;
                    background-color: #f9fbfd;
                }
            """)

        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.mousePressEvent = lambda _: self._on_unit_card_clicked(unit)

        # Card layout
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # Unit number and type
        header_layout = QHBoxLayout()
        unit_num = unit.unit_number or unit.apartment_number or "غير محدد"
        unit_label = QLabel(f"🏠 وحدة رقم: {unit_num}")
        unit_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(unit_label)

        header_layout.addStretch()

        if is_selected:
            check_label = QLabel("✓")
            check_label.setStyleSheet("color: #27ae60; font-size: 18px; font-weight: bold;")
            header_layout.addWidget(check_label)

        layout.addLayout(header_layout)

        # Details grid
        details_layout = QHBoxLayout()
        details_layout.setSpacing(16)

        # Column 1
        col1 = QVBoxLayout()
        col1.addWidget(self._create_detail_item("النوع", unit.unit_type_display or unit.unit_type or "غير محدد"))
        col1.addWidget(self._create_detail_item("الطابق", str(unit.floor_number) if unit.floor_number is not None else "-"))
        details_layout.addLayout(col1)

        # Column 2
        col2 = QVBoxLayout()
        col2.addWidget(self._create_detail_item("الحالة", unit.apartment_status_display or unit.apartment_status or "جيدة"))
        col2.addWidget(self._create_detail_item("المساحة", f"{unit.area_sqm} م²" if unit.area_sqm else "-"))
        details_layout.addLayout(col2)

        # Column 3
        col3 = QVBoxLayout()
        rooms = str(getattr(unit, 'number_of_rooms', '-'))
        col3.addWidget(self._create_detail_item("عدد الغرف", rooms))
        details_layout.addLayout(col3)

        details_layout.addStretch()
        layout.addLayout(details_layout)

        # Description (if available)
        if unit.property_description:
            desc_label = QLabel(unit.property_description)
            desc_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            desc_label.setWordWrap(True)
            desc_label.setMaximumHeight(40)
            layout.addWidget(desc_label)

        return card

    def _create_detail_item(self, label: str, value: str) -> QWidget:
        """Create a detail label-value pair."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-size: 11px; color: #9CA3AF;")
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("font-size: 12px; color: #2c3e50; font-weight: 600;")
        layout.addWidget(value_widget)

        return container

    def _on_unit_card_clicked(self, unit: Unit):
        """Handle unit card click."""
        self.selected_unit = unit

        # Update context
        self.context.set_unit(unit, is_new=False)

        # Refresh cards to show selection
        self._load_units()

        # Update selected info
        self.selected_info.setText(
            f"✓ تم اختيار الوحدة: {unit.unit_number or unit.apartment_number}\n"
            f"النوع: {unit.unit_type_display or unit.unit_type}"
        )
        self.selected_info.setStyleSheet("""
            background-color: #d5f4e6;
            padding: 12px;
            border-radius: 4px;
            color: #27ae60;
            font-weight: bold;
        """)

        # Emit validation changed
        self.emit_validation_changed(True)

        logger.info(f"Unit selected: {unit.unit_id}")

    def _show_add_unit_dialog(self):
        """Show dialog to add a new unit."""
        from ui.wizards.office_survey.dialogs.unit_dialog import UnitDialog

        dialog = UnitDialog(self.context.building, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            unit_data = dialog.get_unit_data()

            try:
                # Create unit in database
                new_unit = self.unit_repo.create(unit_data)

                # Update context
                self.context.set_unit(new_unit, is_new=True)
                self.context.new_unit_data = unit_data
                self.selected_unit = new_unit

                # Reload units
                self._load_units()

                # Update selected info
                self.selected_info.setText(
                    f"✓ تم إنشاء واختيار الوحدة الجديدة: {new_unit.unit_number or new_unit.apartment_number}"
                )
                self.selected_info.setStyleSheet("""
                    background-color: #d5f4e6;
                    padding: 12px;
                    border-radius: 4px;
                    color: #27ae60;
                    font-weight: bold;
                """)

                # Emit validation changed
                self.emit_validation_changed(True)

                logger.info(f"New unit created: {new_unit.unit_id}")

            except Exception as e:
                logger.error(f"Error creating unit: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "خطأ",
                    f"حدث خطأ أثناء إنشاء الوحدة: {str(e)}"
                )

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error("لا يوجد مبنى مختار! يرجى العودة للخطوة السابقة")

        if not self.selected_unit:
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
            # Update UI to show selection
            self.selected_info.setText(
                f"✓ الوحدة المختارة: {self.context.unit.unit_number or self.context.unit.apartment_number}"
            )
            self.selected_info.setStyleSheet("""
                background-color: #d5f4e6;
                padding: 12px;
                border-radius: 4px;
                color: #27ae60;
                font-weight: bold;
            """)

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
