# -*- coding: utf-8 -*-
"""
صفحة المسودات - Draft Claims Page
Displays draft claims in a 2-column grid layout.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ..design_system import Colors
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from ..components.empty_state import EmptyState
from ..components.claim_list_card import ClaimListCard


class DraftClaimsPage(QWidget):
    """Draft claims page with grid layout."""

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claims_data = []
        self.current_tab_title = "المسودة"
        self._setup_ui()

    def _setup_ui(self):
        """Setup page UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setStyleSheet(StyleManager.page_background())

        self.header = self._create_header()
        main_layout.addWidget(self.header)
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Colors.BACKGROUND};
                border: none;
            }}
        """)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(32, 32, 32, 32)
        self.content_layout.setSpacing(16)

        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area)

        self._show_empty_state()

    def _create_header(self):
        """Create page header with title and add button."""
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(32, 0, 32, 0)
        layout.setSpacing(16)

        self.title_label = QLabel(self.current_tab_title)
        # Use centralized font utility: 18pt Bold (24px × 0.75 = 18pt)
        title_font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold, letter_spacing=0)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(StyleManager.label_title())
        layout.addWidget(self.title_label)

        layout.addStretch()

        add_btn = QPushButton("⊕ إضافة حالة جديدة")
        add_btn.setFixedHeight(40)
        add_btn.setCursor(Qt.PointingHandCursor)
        # Use centralized font: 12pt DemiBold (16px × 0.75 = 12pt)
        btn_font = create_font(size=12, weight=QFont.DemiBold, letter_spacing=0)
        add_btn.setFont(btn_font)
        add_btn.setStyleSheet(StyleManager.button_primary())
        add_btn.clicked.connect(self.add_claim_clicked.emit)
        layout.addWidget(add_btn)

        return header

    def _show_empty_state(self):
        """Show empty state when no claims exist."""
        self._clear_content()

        empty_state = EmptyState(
            icon_text="📝",
            title="لا توجد مسودات",
            description="ابدأ بإضافة حالات جديدة أو احفظها كمسودة"
        )

        self.content_layout.addStretch()
        self.content_layout.addWidget(empty_state, alignment=Qt.AlignCenter)
        self.content_layout.addStretch()

    def _show_claims_list(self):
        """Show claims in 2-column grid layout."""
        self._clear_content()

        if not self.claims_data:
            self._show_empty_state()
            return

        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(20)
        grid_layout.setVerticalSpacing(20)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

        for index, claim in enumerate(self.claims_data):
            row = index // 2
            col = index % 2

            card = ClaimListCard(claim)
            card.clicked.connect(self._on_card_clicked)
            grid_layout.addWidget(card, row, col)

        grid_layout.setRowStretch(len(self.claims_data) // 2 + 1, 1)

        self.content_layout.addWidget(grid_container)

    def _on_card_clicked(self, claim_id: str):
        """Handle card click."""
        self.claim_selected.emit(claim_id)

    def _clear_content(self):
        """Clear all content from layout."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass

    def load_claims(self, claims_data):
        """
        Load claims data and display.

        Args:
            claims_data: List of claim dictionaries
        """
        self.claims_data = claims_data

        if claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()

    def set_tab_title(self, title: str):
        """Update page title."""
        self.current_tab_title = title
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)

    def refresh(self, data=None):
        """Refresh the claims list."""
        if self.db:
            try:
                from repositories.claim_repository import ClaimRepository
                claim_repo = ClaimRepository(self.db)

                all_claims = claim_repo.get_all(limit=100)
                claims = [c for c in all_claims if c.case_status == 'draft']

                self.claims_data = []
                for claim in claims:
                    claimant_name = 'غير محدد'
                    if claim.person_ids:
                        try:
                            from repositories.person_repository import PersonRepository
                            person_repo = PersonRepository(self.db)
                            person = person_repo.find_by_id(claim.person_ids.split(',')[0])
                            if person:
                                claimant_name = person.full_name_ar or person.full_name or 'غير محدد'
                        except:
                            pass

                    location = 'غير محدد'
                    building_id = ''
                    if claim.unit_id:
                        try:
                            from repositories.unit_repository import UnitRepository
                            from repositories.building_repository import BuildingRepository
                            unit_repo = UnitRepository(self.db)
                            building_repo = BuildingRepository(self.db)

                            unit = unit_repo.find_by_id(claim.unit_id)
                            if unit and unit.building_id:
                                building_id = unit.building_id
                                building = building_repo.find_by_id(unit.building_id)
                                if building:
                                    location = building.neighborhood_name_ar or building.neighborhood_name or 'غير محدد'
                        except:
                            pass

                    date_str = '2025-01-01'
                    if claim.submission_date:
                        if isinstance(claim.submission_date, str):
                            date_str = claim.submission_date.split('T')[0] if 'T' in claim.submission_date else claim.submission_date
                        else:
                            date_str = claim.submission_date.strftime('%Y-%m-%d')

                    self.claims_data.append({
                        'claim_id': claim.claim_id or claim.case_number or 'N/A',
                        'claimant_name': claimant_name,
                        'date': date_str,
                        'status': claim.case_status or 'draft',
                        'location': location,
                        'unit_id': claim.unit_id or '',
                        'building_id': building_id if claim.unit_id else ''
                    })
            except Exception as e:
                self.claims_data = []

        if self.claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()
