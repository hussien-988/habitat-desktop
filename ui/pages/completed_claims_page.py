# -*- coding: utf-8 -*-
"""
صفحة المطالبات المكتملة - Completed Claims Page
Displays completed/approved claims in a 2-column grid layout.

Figma Specifications Applied:
- Background: #F0F7FF (BACKGROUND color)
- Typography: IBM Plex Sans Arabic, Letter spacing: 0px
- Layout: Clean, professional spacing

Note: Navbar is managed by MainWindow, not by individual pages
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ..design_system import Colors, PageDimensions
from ..components.empty_state import EmptyState
from ..components.claim_list_card import ClaimListCard
from ..components.primary_button import PrimaryButton
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager


class CompletedClaimsPage(QWidget):
    """
    Completed claims page with grid layout.

    Signals:
        claim_selected(str): Emitted when a claim card is clicked
        add_claim_clicked(): Emitted when add button is clicked

    Note: Navbar is managed by MainWindow, not by this page
    """

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
        """
        Setup page UI.

        Structure:
        - Header (80px height with title and add button)
        - Content area (scrollable grid of claim cards)

        Note: Navbar is managed by MainWindow
        """
        main_layout = QVBoxLayout(self)
        # Apply padding from Figma:
        # - Horizontal: 131px each side
        # - Top: 43px (gap between navbar and content: 982-109-830=43px)
        # - Bottom: 0px
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 43px
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            PageDimensions.CONTENT_PADDING_V_BOTTOM  # Bottom: 0px
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)  # 30px gap after header

        # Background color from Figma via StyleManager
        self.setStyleSheet(StyleManager.page_background())

        # Header with title and add button
        self.header = self._create_header()
        main_layout.addWidget(self.header)

        # Content area (scrollable)
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Colors.BACKGROUND};
                border: none;
            }}
        """)

        # Content widget with Grid Layout (Figma: 2 columns, 16px gaps)
        self.content_widget = QWidget()
        self.content_layout = QGridLayout(self.content_widget)
        # No additional padding inside content (padding applied to main_layout)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        # Using Figma values: 16px gap both vertical and horizontal
        self.content_layout.setVerticalSpacing(PageDimensions.CARD_GAP_VERTICAL)      # 16px
        self.content_layout.setHorizontalSpacing(PageDimensions.CARD_GAP_HORIZONTAL)  # 16px

        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area)

        # Show empty state by default
        self._show_empty_state()

    def _create_header(self):
        """
        Create page header with dynamic title and add button.

        Figma Specs:
        - Height: 48px (button + title height)
        - Gap after header: 30px (handled by main_layout spacing)
        - Font: IBM Plex Sans Arabic, 16px Bold, Letter spacing 0
        - Button: Border-radius 8px, Height 40px
        """
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)  # 48px
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)  # No extra padding
        layout.setSpacing(16)

        # Page title (dynamic based on tab)
        self.title_label = QLabel(self.current_tab_title)

        # Use centralized font utility (DRY + eliminates stylesheet conflicts)
        # Figma: IBM Plex Sans Arabic, 24px Bold, Letter spacing 0
        # Font conversion: 24px × 0.75 = 18pt
        title_font = create_font(
            size=FontManager.SIZE_TITLE,  # 18pt
            weight=QFont.Bold,             # 700
            letter_spacing=0
        )
        self.title_label.setFont(title_font)

        self.title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none;")
        layout.addWidget(self.title_label)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Add button - Using reusable PrimaryButton component (DRY + SOLID)
        # Figma: 199×48px, padding 24×12, font 16px, icon instead of "+"
        add_btn = PrimaryButton("إضافة حالة جديدة", icon_name="icon")
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

        # Center the empty state in grid layout
        # Add top spacer (row 0, spans 2 columns)
        self.content_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 0, 0, 1, 2)
        # Add empty state widget (row 1, spans 2 columns, centered)
        self.content_layout.addWidget(empty_state, 1, 0, 1, 2, Qt.AlignCenter)
        # Add bottom spacer (row 2, spans 2 columns)
        self.content_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 0, 1, 2)

    def _show_claims_list(self):
        """Show claims in 2-column grid layout with Figma spacing"""
        # Clear existing content
        self._clear_content()

        if not self.claims_data:
            self._show_empty_state()
            return

        # Add cards directly to content_layout (which is already QGridLayout)
        # Grid layout was set up in _setup_ui with 16px gaps
        for index, claim in enumerate(self.claims_data):
            row = index // PageDimensions.CARD_COLUMNS  # Integer division for row
            col = index % PageDimensions.CARD_COLUMNS   # Modulo for column (0 or 1)

            card = ClaimListCard(claim)
            card.clicked.connect(self._on_card_clicked)
            self.content_layout.addWidget(card, row, col)

        # Add spacer at the bottom to push content up
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        final_row = (len(self.claims_data) + PageDimensions.CARD_COLUMNS - 1) // PageDimensions.CARD_COLUMNS
        self.content_layout.addItem(spacer, final_row, 0, 1, PageDimensions.CARD_COLUMNS)

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
