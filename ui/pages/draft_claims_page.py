# -*- coding: utf-8 -*-
"""
صفحة المسودات - Draft Claims Page
Displays draft claims in a 2-column grid layout.

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


class DraftClaimsPage(QWidget):
    """
    Draft claims page with grid layout.

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
        self.current_tab_title = "المسودات"
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

        # Force equal column widths even when one column is empty
        self.content_layout.setColumnStretch(0, 1)
        self.content_layout.setColumnStretch(1, 1)

        if not self.claims_data:
            self._show_empty_state()
            return

        # Add cards directly to content_layout (which is already QGridLayout)
        # Grid layout was set up in _setup_ui with 16px gaps
        for index, claim in enumerate(self.claims_data):
            row = index // PageDimensions.CARD_COLUMNS  # Integer division for row
            col = index % PageDimensions.CARD_COLUMNS   # Modulo for column (0 or 1)

            # DRY: Use ClaimListCard with yelow icon for drafts
            card = ClaimListCard(claim, icon_name="yelow")
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
        if not query.strip():
            self.title_label.setText(self.current_tab_title)
            self.refresh()
            return

        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)

            # Try API search first
            kwargs = {}
            if mode == "name":
                kwargs['person_name'] = query
            elif mode == "claim_id":
                kwargs['reference_code'] = query
            elif mode == "building":
                kwargs['building_id'] = query

            result = self._search_via_api(ctrl, query, mode)
            if result is not None:
                self._display_search_results(result)
                return

            # Fallback: local DB search
            from repositories.survey_repository import SurveyRepository
            repo = SurveyRepository(self.db)
            rows = repo.search_drafts(source='office', **kwargs)
            surveys = self._map_local_rows_to_surveys(rows, ctrl)
            self._display_search_results(surveys)

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Search failed: {e}")
            self.claims_data = []
            self._show_empty_state()

    def apply_filters(self, filters: dict):
        """
        Apply advanced filters from the filter dialog.

        Args:
            filters: Dict with keys: building_code, governorate_code, date
        """
        has_filter = any(v for v in filters.values() if v)
        if not has_filter:
            self.title_label.setText(self.current_tab_title)
            self.refresh()
            return

        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)

            # Load all drafts then filter by building_code, governorate, date
            result = ctrl.load_office_surveys(status="Draft")
            if not result.success or not result.data:
                self._display_search_results([])
                return

            surveys = result.data
            building_code = filters.get('building_code', '').strip()
            gov_code = filters.get('governorate_code', '').strip()
            filter_date = filters.get('date', '').strip()

            filtered = []
            for s in surveys:
                # Filter by building code
                if building_code:
                    bid = s.get('buildingNumber', '') or ''
                    buid = s.get('buildingId', '') or ''
                    if building_code not in bid and building_code not in buid:
                        continue

                # Filter by governorate (building_id starts with gov code)
                if gov_code:
                    bid = s.get('buildingNumber', '') or ''
                    if not bid.startswith(gov_code):
                        continue

                # Filter by date
                if filter_date:
                    survey_date = (s.get('surveyDate') or '')[:10]
                    if survey_date != filter_date:
                        continue

                filtered.append(s)

            self._display_search_results(filtered)

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Filter failed: {e}")
            self.claims_data = []
            self._show_empty_state()

    def _search_via_api(self, ctrl, query, mode):
        """Try searching via API. Returns list of survey dicts or None."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            if api is None:
                return None
            # API does not have a dedicated search endpoint for drafts,
            # so we load all drafts and filter client-side
            result = ctrl.load_office_surveys(status="Draft")
            if not result.success or not result.data:
                return []

            surveys = result.data
            filtered = []
            q = query.strip().lower()
            for s in surveys:
                if mode == "name":
                    name = (s.get('intervieweeName') or '').lower()
                    if q in name:
                        filtered.append(s)
                elif mode == "claim_id":
                    ref = (s.get('referenceCode') or '').lower()
                    sid = (s.get('id') or '').lower()
                    if q in ref or q in sid:
                        filtered.append(s)
                elif mode == "building":
                    bid = (s.get('buildingNumber') or '').lower()
                    buid = (s.get('buildingId') or '').lower()
                    if q in bid or q in buid:
                        filtered.append(s)
            return filtered
        except Exception:
            return None

    def _map_local_rows_to_surveys(self, rows, ctrl):
        """Convert local DB rows to API-format survey dicts."""
        surveys = []
        for row in rows:
            context = row.get("context", {})
            surveys.append({
                "id": row.get("survey_id", ""),
                "buildingId": row.get("building_id") or context.get("building_uuid") or "",
                "propertyUnitId": row.get("unit_id", ""),
                "unitIdentifier": context.get("unit", {}).get("unit_number", "") if isinstance(context.get("unit"), dict) else "",
                "referenceCode": row.get("reference_code", ""),
                "intervieweeName": ctrl._extract_interviewee_name(context),
                "surveyDate": str(row.get("survey_date", "")),
                "status": row.get("status", "draft"),
                "buildingNumber": context.get("building", {}).get("building_id", "") if isinstance(context.get("building"), dict) else "",
            })
        return surveys

    def _display_search_results(self, surveys):
        """Display search/filter results using the same card format as refresh()."""
        building_ids = {s.get('buildingId', '') for s in surveys if s.get('buildingId')}
        buildings_cache = self._fetch_buildings_by_ids(building_ids)

        self.claims_data = []
        for s in surveys:
            building_obj = buildings_cache.get(s.get('buildingId'))

            unit_obj = None
            unit_num = s.get('unitIdentifier', '')
            if unit_num:
                class _NS:
                    def __init__(self, **kw): self.__dict__.update(kw)
                unit_obj = _NS(unit_number=unit_num)

            self.claims_data.append({
                'claim_id': s.get('referenceCode') or s.get('id', 'N/A'),
                'claim_uuid': s.get('id', ''),
                'claimant_name': s.get('intervieweeName') or 'غير محدد',
                'date': (s.get('surveyDate') or '')[:10],
                'status': 'draft',
                'building': building_obj,
                'unit': unit_obj,
                'unit_id': s.get('propertyUnitId', ''),
                'unit_number': unit_num,
                'building_id': s.get('buildingNumber') or (building_obj.building_id if building_obj else ''),
            })

        self.title_label.setText(f"نتائج البحث ({len(self.claims_data)})")

        if self.claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()

    def set_tab_title(self, title: str):
        """Update page title."""
        self.current_tab_title = title
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)

    def refresh(self, data=None):
        """Refresh survey drafts list from Surveys/office API."""
        self.title_label.setText(self.current_tab_title)
        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            result = ctrl.load_office_surveys(status="Draft")

            if not result.success or not result.data:
                self.claims_data = []
                self._show_empty_state()
                return

            surveys = result.data

            # Fetch Building objects by UUID for full address display
            building_ids = {s.get('buildingId', '') for s in surveys if s.get('buildingId')}
            buildings_cache = self._fetch_buildings_by_ids(building_ids)

            self.claims_data = []
            for s in surveys:
                building_obj = buildings_cache.get(s.get('buildingId'))

                # Create unit namespace if unit data available
                unit_obj = None
                unit_num = s.get('unitIdentifier', '')
                if unit_num:
                    class _NS:
                        def __init__(self, **kw): self.__dict__.update(kw)
                    unit_obj = _NS(unit_number=unit_num)

                self.claims_data.append({
                    'claim_id': s.get('referenceCode') or s.get('id', 'N/A'),
                    'claim_uuid': s.get('id', ''),
                    'claimant_name': s.get('intervieweeName') or 'غير محدد',
                    'date': (s.get('surveyDate') or '')[:10],
                    'status': 'draft',
                    'building': building_obj,
                    'unit': unit_obj,
                    'unit_id': s.get('propertyUnitId', ''),
                    'unit_number': unit_num,
                    'building_id': s.get('buildingNumber') or (building_obj.building_id if building_obj else ''),
                })

            if self.claims_data:
                self._show_claims_list()
            else:
                self._show_empty_state()

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"API load failed: {e}")
            self.claims_data = []
            self._show_empty_state()

    def _fetch_buildings_by_ids(self, building_ids):
        """Fetch Building objects by UUID from API with local DB fallback."""
        from models.building import Building
        cache = {}
        if not building_ids:
            return cache

        # Try API first
        try:
            from services.api_client import get_api_client
            from controllers.claim_controller import ClaimController
            api = get_api_client()
            for bid in building_ids:
                if not bid:
                    continue
                try:
                    dto = api.get_building_by_id(bid)
                    mapped = ClaimController._map_building_dto(dto)
                    cache[bid] = Building.from_dict(mapped)
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: load missing buildings from local DB
        missing = [b for b in building_ids if b and b not in cache]
        if missing:
            try:
                from repositories.building_repository import BuildingRepository
                repo = BuildingRepository(self.db)
                for bid in missing:
                    building = repo.get_by_uuid(bid) or repo.get_by_id(bid)
                    if building:
                        cache[bid] = building
            except Exception:
                pass

        return cache
