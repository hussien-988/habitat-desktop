# -*- coding: utf-8 -*-
"""
Global search page for Buildings, Persons, Claims.
Implements UC-011: Search & Filter
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QTabWidget,
    QFrame, QAbstractItemView, QGraphicsDropShadowEffect, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt5.QtGui import QColor

from app.config import Config, Pages
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.person_repository import PersonRepository
from repositories.claim_repository import ClaimRepository
from ui.components.base_table_model import BaseTableModel
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class SearchResultsModel(BaseTableModel):
    """Generic search results model."""

    def __init__(self, headers: list):
        # Initialize with empty columns; will be set dynamically via set_results
        super().__init__(items=[], columns=[])
        self._custom_headers = headers
        self._data_keys = []

    def columnCount(self, parent=None):
        """Override to use custom headers."""
        return len(self._custom_headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Override to use custom headers."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._custom_headers[section] if section < len(self._custom_headers) else ""
        return None

    def get_item_value(self, item, field_name: str):
        """Extract field value dynamically using data_keys."""
        # field_name is the index in this case
        idx = int(field_name) if field_name.isdigit() else 0
        if idx < len(self._data_keys):
            key = self._data_keys[idx]
            return str(getattr(item, key, "-") or "-")
        return "-"

    def set_results(self, results: list, data_keys: list):
        """Set search results and data keys for dynamic column mapping."""
        self._data_keys = data_keys
        # Build columns dynamically based on data_keys indices
        self._columns = [(str(i), "", "") for i in range(len(data_keys))]
        self.set_items(results)


class SearchPage(QWidget):
    """Global search page."""

    navigate_to = pyqtSignal(str, object)  # page_id, data

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.person_repo = PersonRepository(db)
        self.claim_repo = ClaimRepository(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        title = QLabel(self.i18n.t("global_search"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(title)

        # Search bar
        search_frame = QFrame()
        search_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        search_frame.setGraphicsEffect(shadow)

        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(24, 20, 24, 20)
        search_layout.setSpacing(16)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث في المباني، الأشخاص، المطالبات...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 2px solid {Config.INPUT_BORDER};
                border-radius: 10px;
                padding: 12px 16px;
                font-size: {Config.FONT_SIZE + 1}pt;
            }}
            QLineEdit:focus {{
                border-color: {Config.PRIMARY_COLOR};
            }}
        """)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton(self.i18n.t("search"))
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 32px;
                font-size: {Config.FONT_SIZE + 1}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(search_btn)

        layout.addWidget(search_frame)

        # Connect enter key
        self.search_input.returnPressed.connect(self._do_search)

        # Results tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: white;
                border-radius: 12px;
                border: none;
            }}
            QTabBar::tab {{
                background-color: #F1F5F9;
                color: {Config.TEXT_LIGHT};
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: white;
                color: {Config.PRIMARY_COLOR};
                font-weight: 600;
            }}
        """)

        # Buildings tab
        self.buildings_table = self._create_table()
        self.buildings_model = SearchResultsModel(["رقم المبنى", "الحي", "النوع", "الحالة"])
        self.buildings_table.setModel(self.buildings_model)
        self.buildings_table.doubleClicked.connect(lambda idx: self._on_building_click(idx))
        self.tabs.addTab(self.buildings_table, "المباني (0)")

        # Persons tab
        self.persons_table = self._create_table()
        self.persons_model = SearchResultsModel(["الاسم", "الرقم الوطني", "الجنس", "الجوال"])
        self.persons_table.setModel(self.persons_model)
        self.persons_table.doubleClicked.connect(lambda idx: self._on_person_click(idx))
        self.tabs.addTab(self.persons_table, "الأشخاص (0)")

        # Claims tab
        self.claims_table = self._create_table()
        self.claims_model = SearchResultsModel(["رقم المطالبة", "الوحدة", "النوع", "الحالة"])
        self.claims_table.setModel(self.claims_model)
        self.claims_table.doubleClicked.connect(lambda idx: self._on_claim_click(idx))
        self.tabs.addTab(self.claims_table, "المطالبات (0)")

        layout.addWidget(self.tabs)

    def _create_table(self) -> QTableView:
        """Create a styled table view."""
        table = QTableView()
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
            }}
            QTableView::item {{
                padding: 10px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 10px 8px;
                border: none;
            }}
        """)
        return table

    def refresh(self, data=None):
        """Refresh page."""
        pass

    def _do_search(self):
        """Perform search across all entities."""
        query = self.search_input.text().strip()
        if not query:
            return

        logger.debug(f"Searching for: {query}")

        # Search buildings
        buildings = self.building_repo.search(search_text=query, limit=100)
        self.buildings_model.set_results(
            buildings,
            ["building_id", "neighborhood_name_ar", "building_type", "building_status"]
        )
        self.tabs.setTabText(0, f"المباني ({len(buildings)})")

        # Search persons
        persons = self.person_repo.search(name=query, limit=100)
        if not persons:
            persons = self.person_repo.search(national_id=query, limit=100)
        self.persons_model.set_results(
            persons,
            ["full_name_ar", "national_id", "gender_display_ar", "mobile_number"]
        )
        self.tabs.setTabText(1, f"الأشخاص ({len(persons)})")

        # Search claims
        claims = self.claim_repo.search(claim_id=query, limit=100)
        self.claims_model.set_results(
            claims,
            ["claim_id", "unit_id", "claim_type", "case_status_display_ar"]
        )
        self.tabs.setTabText(2, f"المطالبات ({len(claims)})")

    def _on_building_click(self, index):
        building = self.buildings_model.get_item(index.row())
        if building:
            self.navigate_to.emit(Pages.BUILDING_DETAILS, building.building_id)

    def _on_person_click(self, index):
        person = self.persons_model.get_item(index.row())
        if person:
            # Navigate to person details (or show dialog)
            pass

    def _on_claim_click(self, index):
        claim = self.claims_model.get_item(index.row())
        if claim:
            self.navigate_to.emit(Pages.CLAIMS, claim.claim_id)

    def update_language(self, is_arabic: bool):
        pass
