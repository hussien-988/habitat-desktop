# -*- coding: utf-8 -*-
"""
Building details page with tabbed view.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableView, QFrame, QFormLayout, QHeaderView,
    QAbstractItemView, QScrollArea, QGridLayout, QDialog
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.config import Config
from ui.components.toast import Toast
from models.building import Building
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.unit_repository import UnitRepository
from repositories.person_repository import PersonRepository
from repositories.claim_repository import ClaimRepository
from ui.components.table_models import UnitsTableModel, PersonsTableModel
from utils.i18n import I18n
from utils.helpers import format_date
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingDetailsPage(QWidget):
    """Building details page with tabs."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self.person_repo = PersonRepository(db)
        self.claim_repo = ClaimRepository(db)

        self.current_building = None
        self._setup_ui()

    def _setup_ui(self):
        """Setup building details UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with back button
        header_layout = QHBoxLayout()

        self.back_btn = QPushButton(f"← {self.i18n.t('back_to_list')}")
        self.back_btn.setProperty("class", "secondary")
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.back_btn)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Edit button (UC-000 S02a)
        self.edit_btn = QPushButton("تعديل المبنى")
        self.edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        self.edit_btn.clicked.connect(self._on_edit_building)
        header_layout.addWidget(self.edit_btn)

        layout.addLayout(header_layout)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Overview tab
        self.overview_tab = self._create_overview_tab()
        self.tabs.addTab(self.overview_tab, self.i18n.t("overview_tab"))

        # Units tab
        self.units_tab = self._create_units_tab()
        self.tabs.addTab(self.units_tab, self.i18n.t("units_tab"))

        # Persons tab
        self.persons_tab = self._create_persons_tab()
        self.tabs.addTab(self.persons_tab, self.i18n.t("persons_tab"))

        # Evidence tab
        self.evidence_tab = self._create_evidence_tab()
        self.tabs.addTab(self.evidence_tab, self.i18n.t("evidence_tab"))

        # History tab
        self.history_tab = self._create_history_tab()
        self.tabs.addTab(self.history_tab, self.i18n.t("history_tab"))

    def _create_overview_tab(self) -> QWidget:
        """Create the overview tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(24)

        # Building info card
        info_card = QFrame()
        info_card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 8px;
                border: 1px solid {Config.BORDER_COLOR};
                padding: 16px;
            }}
        """)
        info_layout = QGridLayout(info_card)
        info_layout.setSpacing(16)

        # Create field labels
        self.field_labels = {}
        fields = [
            ("building_id", self.i18n.t("building_id"), 0, 0),
            ("neighborhood", self.i18n.t("neighborhood"), 0, 2),
            ("building_type", self.i18n.t("building_type"), 1, 0),
            ("building_status", self.i18n.t("building_status"), 1, 2),
            ("governorate", self.i18n.t("governorate"), 2, 0),
            ("district", self.i18n.t("district"), 2, 2),
            ("floors", self.i18n.t("floors"), 3, 0),
            ("apartments", self.i18n.t("apartments"), 3, 2),
            ("shops", self.i18n.t("shops"), 4, 0),
            ("coordinates", self.i18n.t("coordinates"), 4, 2),
        ]

        for field_id, label_text, row, col in fields:
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-weight: bold; color: #666;")
            info_layout.addWidget(label, row, col)

            value_label = QLabel("-")
            self.field_labels[field_id] = value_label
            info_layout.addWidget(value_label, row, col + 1)

        layout.addWidget(info_card)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _create_units_tab(self) -> QWidget:
        """Create the units tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # Units table
        self.units_table = QTableView()
        self.units_table.setAlternatingRowColors(True)
        self.units_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.units_table.verticalHeader().setVisible(False)
        self.units_table.horizontalHeader().setStretchLastSection(True)

        self.units_model = UnitsTableModel(is_arabic=self.i18n.is_arabic())
        self.units_table.setModel(self.units_model)

        layout.addWidget(self.units_table)

        return widget

    def _create_persons_tab(self) -> QWidget:
        """Create the persons tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # Note
        note_label = QLabel("Persons with relations to units in this building:")
        note_label.setStyleSheet("color: #666; margin-bottom: 8px;")
        layout.addWidget(note_label)

        # Persons table
        self.persons_table = QTableView()
        self.persons_table.setAlternatingRowColors(True)
        self.persons_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.persons_table.verticalHeader().setVisible(False)
        self.persons_table.horizontalHeader().setStretchLastSection(True)

        self.persons_model = PersonsTableModel(is_arabic=self.i18n.is_arabic())
        self.persons_table.setModel(self.persons_model)

        layout.addWidget(self.persons_table)

        return widget

    def _create_evidence_tab(self) -> QWidget:
        """Create the evidence tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # Placeholder
        placeholder = QLabel("📎 Evidence documents for this building will be displayed here.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #999; font-size: 12pt; padding: 40px;")
        layout.addWidget(placeholder)

        layout.addStretch()
        return widget

    def _create_history_tab(self) -> QWidget:
        """Create the history/audit tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # Placeholder
        placeholder = QLabel("📜 Modification history and audit trail will be displayed here.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #999; font-size: 12pt; padding: 40px;")
        layout.addWidget(placeholder)

        layout.addStretch()
        return widget

    def refresh(self, building_id: str = None):
        """Refresh building details."""
        if not building_id:
            return

        logger.debug(f"Loading building details: {building_id}")

        # Load building
        building = self.building_repo.get_by_id(building_id)
        if not building:
            logger.error(f"Building not found: {building_id}")
            return

        self.current_building = building
        self._update_overview(building)
        self._load_units(building_id)
        self._load_persons(building_id)

        # Update title
        if self.i18n.is_arabic():
            self.title_label.setText(f"{building.neighborhood_name_ar} - {building.building_id}")
        else:
            self.title_label.setText(f"{building.neighborhood_name} - {building.building_id}")

    def _update_overview(self, building: Building):
        """Update overview tab with building data."""
        is_arabic = self.i18n.is_arabic()

        self.field_labels["building_id"].setText(building.building_id)
        self.field_labels["neighborhood"].setText(
            building.neighborhood_name_ar if is_arabic else building.neighborhood_name
        )
        self.field_labels["building_type"].setText(building.building_type_display)
        self.field_labels["building_status"].setText(building.building_status_display)
        self.field_labels["governorate"].setText(
            building.governorate_name_ar if is_arabic else building.governorate_name
        )
        self.field_labels["district"].setText(
            building.district_name_ar if is_arabic else building.district_name
        )
        self.field_labels["floors"].setText(str(building.number_of_floors))
        self.field_labels["apartments"].setText(str(building.number_of_apartments))
        self.field_labels["shops"].setText(str(building.number_of_shops))

        if building.latitude and building.longitude:
            self.field_labels["coordinates"].setText(
                f"{building.latitude:.6f}, {building.longitude:.6f}"
            )
        else:
            self.field_labels["coordinates"].setText("-")

    def _load_units(self, building_id: str):
        """Load units for the building."""
        units = self.unit_repo.get_by_building(building_id)
        self.units_model.set_units(units)

    def _load_persons(self, building_id: str):
        """Load persons related to the building's units."""
        # Get all units for the building
        units = self.unit_repo.get_by_building(building_id)

        # Get persons for each unit
        all_persons = []
        seen_ids = set()

        for unit in units:
            persons = self.person_repo.get_by_unit(unit.unit_id)
            for person in persons:
                if person.person_id not in seen_ids:
                    all_persons.append(person)
                    seen_ids.add(person.person_id)

        self.persons_model.set_persons(all_persons)

    def _on_edit_building(self):
        """Handle edit building button (UC-000 S02a)."""
        if not self.current_building:
            return

        # Import here to avoid circular import
        from ui.pages.buildings_page import BuildingDialog

        dialog = BuildingDialog(self.i18n, building=self.current_building, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                # Update building with new data
                for key, value in data.items():
                    if hasattr(self.current_building, key):
                        setattr(self.current_building, key, value)

                self.building_repo.update(self.current_building)
                Toast.show_toast(self, f"تم تحديث المبنى بنجاح", Toast.SUCCESS)

                # Refresh display
                self.refresh(self.current_building.building_id)
            except Exception as e:
                logger.error(f"Failed to update building: {e}")
                Toast.show_toast(self, f"فشل في تحديث المبنى: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        # Update tab titles
        self.tabs.setTabText(0, self.i18n.t("overview_tab"))
        self.tabs.setTabText(1, self.i18n.t("units_tab"))
        self.tabs.setTabText(2, self.i18n.t("persons_tab"))
        self.tabs.setTabText(3, self.i18n.t("evidence_tab"))
        self.tabs.setTabText(4, self.i18n.t("history_tab"))

        self.back_btn.setText(f"← {self.i18n.t('back_to_list')}")

        # Refresh if we have a building
        if self.current_building:
            self._update_overview(self.current_building)
