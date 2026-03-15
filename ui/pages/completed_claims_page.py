# -*- coding: utf-8 -*-
"""
Claims Page — displays all claims (Open & Closed) using Claims API.
Features Underline Tab Bar for switching between open/closed claims.
"""

import logging
from typing import List, Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout,
    QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ..design_system import Colors, PageDimensions
from ..components.empty_state import EmptyState
from ..components.claim_list_card import ClaimListCard
from ..components.primary_button import PrimaryButton
from ..components.underline_tab_bar import UnderlineTabBar
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from services.translation_manager import tr
from services.display_mappings import get_source_display

logger = logging.getLogger(__name__)

# CaseStatus enum values from backend
CASE_STATUS_OPEN = 1
CASE_STATUS_CLOSED = 2


class CompletedClaimsPage(QWidget):
    """
    Claims page with Underline Tab Bar (Open / Closed).

    Signals:
        claim_selected(str): Emitted when a claim card is clicked
        add_claim_clicked(): Emitted when add button is clicked
    """

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claims_data: List[Dict] = []
        self._active_tab = "open"  # "open" or "closed"
        self._buildings_cache: Dict[str, object] = {}
        self._last_refresh_ms = 0
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        main_layout.setSpacing(16)

        self.setStyleSheet(StyleManager.page_background())

        # Header
        self.header = self._create_header()
        main_layout.addWidget(self.header)

        # Filter bar
        filter_bar = self._create_filter_bar()
        main_layout.addWidget(filter_bar)

        # Underline Tab Bar
        self._tab_bar = UnderlineTabBar(["مفتوحة", "مغلقة"], self)
        self._tab_bar.tab_changed.connect(self._on_tab_changed)
        main_layout.addWidget(self._tab_bar)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #E8E8E8; border: none;")
        main_layout.addWidget(separator)

        # Content area (scrollable)
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

        self.content_widget = QWidget()
        self.content_layout = QGridLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setVerticalSpacing(PageDimensions.CARD_GAP_VERTICAL)
        self.content_layout.setHorizontalSpacing(PageDimensions.CARD_GAP_HORIZONTAL)
        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area)

        self._show_empty_state()

    def showEvent(self, event):
        super().showEvent(event)
        # Debounce: skip if refresh was called in the last 500ms (navigate_to already called it)
        import time
        now = int(time.time() * 1000)
        if now - self._last_refresh_ms > 500:
            self.refresh()

    def _create_header(self):
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.title_label = QLabel(tr("navbar.tab.claims"))
        title_font = create_font(
            size=FontManager.SIZE_TITLE,
            weight=QFont.Bold,
            letter_spacing=0
        )
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self.title_label)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        return header

    def _create_filter_bar(self):
        form_style = StyleManager.form_input()

        bar = QWidget()
        bar.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 1. Search by claim number
        self._search_input = QLineEdit()
        self._search_input.setLayoutDirection(Qt.RightToLeft)
        self._search_input.setPlaceholderText("بحث برقم المطالبة...")
        self._search_input.setFixedWidth(220)
        self._search_input.setStyleSheet(form_style)
        self._search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_input)

        # 2. Source filter (FieldCollection=1, OfficeSubmission=2 per Swagger)
        self._source_filter = QComboBox()
        self._source_filter.setLayoutDirection(Qt.RightToLeft)
        self._source_filter.setFixedWidth(170)
        self._source_filter.setStyleSheet(form_style)
        self._source_filter.addItem("الكل", None)
        self._source_filter.addItem(get_source_display(1), 1)
        self._source_filter.addItem(get_source_display(2), 2)
        self._source_filter.currentIndexChanged.connect(self._on_source_changed)
        layout.addWidget(self._source_filter)

        # 3. Person name filter
        self._name_filter = QLineEdit()
        self._name_filter.setLayoutDirection(Qt.RightToLeft)
        self._name_filter.setPlaceholderText("بحث باسم المُطالِب...")
        self._name_filter.setFixedWidth(200)
        self._name_filter.setStyleSheet(form_style)
        self._name_filter.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._name_filter)

        layout.addStretch()
        return bar

    def _on_search_changed(self):
        """Local filter — re-display without API call."""
        self._apply_local_filter()

    def _on_source_changed(self):
        """Source dropdown changed — reload from API."""
        self._load_claims()

    def _apply_local_filter(self):
        """Filter displayed cards by claim number, person name, and source."""
        search_text = self._search_input.text().strip()
        name_text = self._name_filter.text().strip()
        source_val = self._source_filter.currentData()

        filtered = self.claims_data
        if search_text:
            filtered = [c for c in filtered
                        if search_text in (c.get("claim_id") or "")]
        if name_text:
            filtered = [c for c in filtered
                        if name_text in (c.get("claimant_name") or "")]
        if source_val is not None:
            filtered = [c for c in filtered
                        if c.get("source") == source_val]

        if filtered:
            self._show_claims_list(filtered)
        else:
            self._show_empty_state()

    # -------------------------------------------------------------------------
    # Tab handling
    # -------------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        self._active_tab = "open" if index == 0 else "closed"
        self._load_claims()

    # -------------------------------------------------------------------------
    # Data loading
    # -------------------------------------------------------------------------

    def refresh(self, data=None):
        """Refresh claims from Claims API."""
        import time
        self._last_refresh_ms = int(time.time() * 1000)
        self._load_claims()

    def _load_claims(self):
        """Load claims from API based on active tab and source filter."""
        self.claims_data = []
        case_status = CASE_STATUS_OPEN if self._active_tab == "open" else CASE_STATUS_CLOSED
        source = self._source_filter.currentData()

        try:
            from services.api_client import get_api_client
            api = get_api_client()
            summaries = api.get_claims_summaries(
                claim_status=case_status,
                claim_source=source,
            )

            # Enrich with building details
            building_codes = {s.get("buildingCode", "") for s in summaries if s.get("buildingCode")}
            self._enrich_buildings_cache(api, building_codes)

            for s in summaries:
                self.claims_data.append(self._map_summary(s))
            logger.info(f"Loaded {len(self.claims_data)} claims (status={case_status}, source={source})")
        except Exception as e:
            logger.warning(f"Error loading claims (status={case_status}): {e}")

        self._apply_local_filter()

    def _enrich_buildings_cache(self, api, building_codes):
        """Fetch building details for codes not yet cached."""
        from controllers.building_controller import BuildingController
        bc = BuildingController(self.db)

        for code in building_codes:
            if not code or code in self._buildings_cache:
                continue
            try:
                result = api.search_buildings(building_id=code, page_size=1)
                buildings = result.get("buildings", [])
                if buildings:
                    self._buildings_cache[code] = bc._api_dto_to_building(buildings[0])
            except Exception as e:
                logger.debug(f"Building lookup failed for {code}: {e}")

    def _map_summary(self, s: Dict) -> Dict:
        """Map Claims API summary DTO to card data format."""
        source = s.get("claimSource", 0)
        source_label = get_source_display(source)

        claimant = (
            s.get("primaryClaimantName")
            or s.get("fullNameArabic")
            or "غير محدد"
        )
        date_str = s.get("createdAtUtc") or s.get("surveyDate") or ""

        building_code = s.get("buildingCode", "")
        building_obj = self._buildings_cache.get(building_code)

        unit_number = s.get("propertyUnitIdNumber", "") or s.get("unitCode", "")
        unit_obj = None
        if unit_number:
            class _NS:
                def __init__(self, **kw): self.__dict__.update(kw)
            unit_obj = _NS(unit_number=unit_number)

        return {
            "claim_id": s.get("claimNumber", "") or s.get("claimId", "N/A"),
            "claim_uuid": s.get("claimId", "") or s.get("id", ""),
            "claimant_name": claimant,
            "date": date_str[:10] if date_str and not date_str.startswith("0001") else "",
            "status": "open" if s.get("caseStatus") == CASE_STATUS_OPEN else "closed",
            "building_code": building_code,
            "unit_number": unit_number,
            "source": source,
            "source_label": source_label,
            "building_id": building_obj.building_id if building_obj else building_code,
            "building": building_obj,
            "unit": unit_obj,
            "survey_id": s.get("surveyId", ""),
        }

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------

    def _show_claims_list(self, data=None):
        self._clear_content()

        display = data if data is not None else self.claims_data
        if not display:
            self._show_empty_state()
            return

        icon = "blue" if self._active_tab == "closed" else "yelow"

        for index, claim in enumerate(display):
            row = index // PageDimensions.CARD_COLUMNS
            col = index % PageDimensions.CARD_COLUMNS

            card = ClaimListCard(claim, icon_name=icon)
            card.clicked.connect(self._on_card_clicked)
            self.content_layout.addWidget(card, row, col)

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        final_row = (len(display) + PageDimensions.CARD_COLUMNS - 1) // PageDimensions.CARD_COLUMNS
        self.content_layout.addItem(spacer, final_row, 0, 1, PageDimensions.CARD_COLUMNS)

    def _show_empty_state(self):
        self._clear_content()

        msg = "لا توجد مطالبات مفتوحة حالياً" if self._active_tab == "open" else "لا توجد مطالبات مغلقة بعد"
        empty_state = EmptyState(
            icon_text="+",
            title=msg,
            description="ابدأ بإضافة الحالات للظهور هنا"
        )

        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 0, 0, 1, 2
        )
        self.content_layout.addWidget(empty_state, 1, 0, 1, 2, Qt.AlignCenter)
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 0, 1, 2
        )

    def _on_card_clicked(self, claim_id: str):
        self.claim_selected.emit(claim_id)

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # -------------------------------------------------------------------------
    # Public interface (kept for backward compatibility)
    # -------------------------------------------------------------------------

    def load_claims(self, claims_data):
        self.claims_data = claims_data
        if claims_data:
            self._show_claims_list()
        else:
            self._show_empty_state()

    def search_claims(self, query: str, mode: str = "name"):
        pass

    def set_tab_title(self, title: str):
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)
