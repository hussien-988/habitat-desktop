# -*- coding: utf-8 -*-
"""
صفحة المطالبات المكتملة - Completed Claims Page
Displays completed/approved claims in a 2-column grid layout.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ..design_system import Colors
from ..components.empty_state import EmptyState
from ..components.claim_list_card import ClaimListCard


class CompletedClaimsPage(QWidget):
    """Completed claims page with grid layout."""

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claims_data = []
        self.current_tab_title = "المطالبات المكتملة"
        self._setup_ui()

    def _setup_ui(self):
        """Setup page UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

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

        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(32, 32, 32, 32)
        self.content_layout.setSpacing(16)

        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area)

        # Show empty state by default
        self._show_empty_state()

    def _create_header(self):
        """Create page header with dynamic title and add button"""
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(32, 0, 32, 0)
        layout.setSpacing(16)

        # Page title (dynamic based on tab)
        self.title_label = QLabel(self.current_tab_title)
        self.title_label.setFont(QFont("Noto Kufi Arabic", 10, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none;")
        layout.addWidget(self.title_label)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Add button
        add_btn = QPushButton("إضافة حالة جديدة +")
        add_btn.setFixedHeight(40)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFont(QFont("Noto Kufi Arabic", 9, QFont.Bold))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0px 20px;
            }}
            QPushButton:hover {{
                background-color: #2A7BC9;
            }}
            QPushButton:pressed {{
                background-color: #1F68B3;
            }}
        """)
        add_btn.clicked.connect(self.add_claim_clicked.emit)
        layout.addWidget(add_btn)

        return header

    def _show_empty_state(self):
        """Show empty state when no claims exist"""
        # Clear existing content
        self._clear_content()

        # Create empty state
        empty_state = EmptyState(
            icon_text="+",
            title="لا توجد بيانات بعد",
            description="ابدأ بإضافة الحالات للظهور هنا"
        )

        # Center the empty state
        self.content_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.content_layout.addWidget(empty_state, alignment=Qt.AlignCenter)
        self.content_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def _show_claims_list(self):
        """Show claims in 2-column grid layout with spacing between cards"""
        # Clear existing content
        self._clear_content()

        if not self.claims_data:
            self._show_empty_state()
            return

        # Create grid container
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(20)  # 20px horizontal spacing (reference design)
        grid_layout.setVerticalSpacing(20)    # 20px vertical spacing (reference design)
        grid_layout.setColumnStretch(0, 1)    # Equal column widths
        grid_layout.setColumnStretch(1, 1)

        # Add cards in 2-column grid (row, col)
        for index, claim in enumerate(self.claims_data):
            row = index // 2  # Integer division for row
            col = index % 2   # Modulo for column (0 or 1)

            card = ClaimListCard(claim)
            card.clicked.connect(self._on_card_clicked)
            grid_layout.addWidget(card, row, col)

        # Add spacer at the bottom
        grid_layout.setRowStretch(len(self.claims_data) // 2 + 1, 1)

        # Add grid container to content layout
        self.content_layout.addWidget(grid_container)

    def _on_card_clicked(self, claim_id: str):
        """Handle card click"""
        self.claim_selected.emit(claim_id)

    def _clear_content(self):
        """Clear all content from layout"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass

    def load_claims(self, claims_data):
        """
        Load claims data and display

        Args:
            claims_data: List of claim dictionaries with keys:
                - claim_id: str
                - claimant_name: str
                - date: str
                - metadata: list of strings
        """
        self.claims_data = claims_data

        if claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()

    def search_claims(self, query: str, mode: str = "name"):
        """
        Search claims based on query and mode.

        Args:
            query: Search query string
            mode: Search mode (name, claim_id, building)
        """
        pass

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
                claims = [c for c in all_claims if c.case_status in ['completed', 'approved', 'verified', 'closed']]

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
                import traceback
                print(f"Error loading claims: {e}")
                print(f"Traceback:\n{traceback.format_exc()}")
                self.claims_data = []

        # Display based on data availability
        if self.claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()
