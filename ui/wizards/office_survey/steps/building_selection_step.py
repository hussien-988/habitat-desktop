# -*- coding: utf-8 -*-
"""
Building Selection Step - Step 1 of Office Survey Wizard.

Allows user to:
- Search for existing buildings
- View building on map
- Select a building to proceed
"""

from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from repositories.building_repository import BuildingRepository
from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingSelectionStep(BaseStep):
    """
    Step 1: Building Selection.

    User can search for buildings by ID or address and select one.
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)
        self.building_repo = BuildingRepository(self.context.db)
        self.selected_building: Optional[Building] = None

    def setup_ui(self):
        """Setup the step's UI."""
        # Header
        header = QLabel("الخطوة 1: اختيار المبنى")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        self.main_layout.addWidget(header)

        # Description
        desc = QLabel("ابحث عن المبنى واختره للمتابعة")
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 16px;")
        self.main_layout.addWidget(desc)

        # Search section
        search_group = self._create_search_section()
        self.main_layout.addWidget(search_group)

        # Results table
        results_group = self._create_results_section()
        self.main_layout.addWidget(results_group, 1)

        # Selected building info
        self.selected_info = QLabel("لم يتم اختيار مبنى")
        self.selected_info.setStyleSheet("""
            background-color: #ecf0f1;
            padding: 12px;
            border-radius: 4px;
            color: #7f8c8d;
        """)
        self.main_layout.addWidget(self.selected_info)

    def _create_search_section(self) -> QGroupBox:
        """Create search section."""
        group = QGroupBox("البحث عن مبنى")
        layout = QVBoxLayout(group)

        # Search by ID
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("رمز المبنى:"))
        self.building_id_input = QLineEdit()
        self.building_id_input.setPlaceholderText("مثال: 01-01-01-001-001-00001")
        self.building_id_input.returnPressed.connect(self._search_buildings)
        id_layout.addWidget(self.building_id_input, 1)
        layout.addLayout(id_layout)

        # Search by address
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("العنوان:"))
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("ابحث بالعنوان...")
        self.address_input.returnPressed.connect(self._search_buildings)
        addr_layout.addWidget(self.address_input, 1)
        layout.addLayout(addr_layout)

        # Search button
        btn_search = QPushButton("بحث")
        btn_search.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        btn_search.clicked.connect(self._search_buildings)
        layout.addWidget(btn_search, alignment=Qt.AlignRight)

        return group

    def _create_results_section(self) -> QGroupBox:
        """Create results section."""
        group = QGroupBox("النتائج")
        layout = QVBoxLayout(group)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "رمز المبنى",
            "العنوان",
            "المحافظة",
            "الحي",
            "الإجراء"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.results_table)

        return group

    def _search_buildings(self):
        """Search for buildings."""
        building_id = self.building_id_input.text().strip()
        address = self.address_input.text().strip()

        if not building_id and not address:
            QMessageBox.warning(
                self,
                "تحذير",
                "الرجاء إدخال رمز المبنى أو العنوان للبحث"
            )
            return

        try:
            # Search in repository
            buildings = []

            if building_id:
                building = self.building_repo.get_by_building_id(building_id)
                if building:
                    buildings = [building]
            elif address:
                # Search by address (simplified - actual implementation may vary)
                all_buildings = self.building_repo.get_all()
                buildings = [
                    b for b in all_buildings
                    if address.lower() in (b.address or "").lower()
                ]

            # Display results
            self._display_results(buildings)

        except Exception as e:
            logger.error(f"Error searching buildings: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء البحث: {str(e)}"
            )

    def _display_results(self, buildings: list):
        """Display search results in table."""
        self.results_table.setRowCount(len(buildings))

        for row, building in enumerate(buildings):
            # Building ID
            self.results_table.setItem(row, 0, QTableWidgetItem(building.building_id or ""))

            # Address
            self.results_table.setItem(row, 1, QTableWidgetItem(building.address or ""))

            # Governorate
            self.results_table.setItem(row, 2, QTableWidgetItem(building.governorate_code or ""))

            # Neighborhood
            self.results_table.setItem(row, 3, QTableWidgetItem(building.neighborhood_code or ""))

            # Select button
            btn_select = QPushButton("اختيار")
            btn_select.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
            """)
            btn_select.clicked.connect(lambda checked, b=building: self._select_building(b))
            self.results_table.setCellWidget(row, 4, btn_select)

    def _select_building(self, building: Building):
        """Select a building."""
        self.selected_building = building

        # Update context
        self.context.set_building(building)

        # Update UI
        self.selected_info.setText(
            f"✓ تم اختيار المبنى: {building.building_id}\n"
            f"العنوان: {building.address or 'غير محدد'}"
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

        logger.info(f"Building selected: {building.building_id}")

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        if not self.selected_building:
            result.add_error("يجب اختيار مبنى للمتابعة")

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "building_id": self.selected_building.building_id if self.selected_building else None,
            "building_uuid": self.selected_building.building_uuid if self.selected_building else None
        }

    def populate_data(self):
        """Populate the step with data from context."""
        if self.context.building:
            self.selected_building = self.context.building
            self.building_id_input.setText(self.context.building.building_id)
            self._search_buildings()

    def get_step_title(self) -> str:
        """Get step title."""
        return "اختيار المبنى"

    def get_step_description(self) -> str:
        """Get step description."""
        return "ابحث عن المبنى المراد مسحه واختره"
