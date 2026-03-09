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
from services.translation_manager import tr


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
        # Apply unified padding (DRY - using PageDimensions constants):
        # - Horizontal: 131px each side
        # - Top: 32px (gap between navbar and content - unified across all pages)
        # - Bottom: 0px
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 32px (unified)
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            PageDimensions.CONTENT_PADDING_V_BOTTOM  # Bottom: 0px
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)  # 30px gap after header

        # Background color from Figma via StyleManager
        self.setStyleSheet(StyleManager.page_background())

        # Header with title and add button
        self.header = self._create_header()
        main_layout.addWidget(self.header)

        # Content area (scrollable with hidden scrollbar)
        # Best Practice: Hide scrollbar for cleaner UI while maintaining scroll functionality
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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

    def showEvent(self, event):
        """تحديث البيانات عند عرض الصفحة"""
        super().showEvent(event)
        # تحديث البيانات تلقائياً عند فتح الصفحة
        self.refresh()

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

        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self.title_label)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Add button - Using reusable PrimaryButton component (DRY + SOLID)
        # Figma: 199×48px, padding 24×12, font 16px, icon instead of "+"
        add_btn = PrimaryButton(tr("wizard.button.add_case"), icon_name="icon")
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
        """Refresh the claims list from the backend API (Approved and Rejected statuses)."""
        self.claims_data = []
        if not self.db:
            self._show_empty_state()
            return
        try:
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController(self.db)
            summaries = []
            for status_int in (5, 6):   # 5=Approved, 6=Rejected
                result = ctrl.load_claims_from_api(status=status_int)
                if result.success and result.data:
                    summaries.extend(result.data)
            for s in summaries:
                status_int = s.get("caseStatus") or 0
                status_str = "approved" if status_int == 5 else "rejected"
                date_raw = s.get("createdAt", s.get("surveyDate", ""))
                date_str = date_raw.split("T")[0] if "T" in date_raw else date_raw
                cid = s.get("claimId", "N/A")
                self.claims_data.append({
                    "claim_id": cid,
                    "claim_uuid": cid,
                    "survey_id": s.get("surveyId", ""),
                    "claimant_name": s.get("fullNameArabic") or s.get("primaryClaimantName") or "غير محدد",
                    "date": date_str,
                    "status": status_str,
                    "building": None,
                    "unit": None,
                    "unit_id": "",
                    "building_id": "",
                })
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error loading claims from API: {e}")
        if self.claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()
