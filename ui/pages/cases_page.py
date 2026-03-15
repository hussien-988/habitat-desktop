# -*- coding: utf-8 -*-
"""
Surveys Page — displays all surveys (Draft & Finalized) using Surveys/office API.
Features Underline Tab Bar for switching between draft/finalized surveys,
plus filter bar with reference code, person name, and building number search.
"""

import logging
from typing import List, Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout,
    QLineEdit, QComboBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from ..design_system import Colors, PageDimensions
from ..components.empty_state import EmptyState
from ..components.claim_list_card import ClaimListCard
from ..components.primary_button import PrimaryButton
from ..components.underline_tab_bar import UnderlineTabBar
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from services.translation_manager import tr
from services.display_mappings import get_survey_type_display

logger = logging.getLogger(__name__)

_STATUS_CONFIG = {
    "draft":     {"icon": "yelow"},
    "finalized": {"icon": "blue"},
}


class CasesPage(QWidget):
    """
    Surveys page with Underline Tab Bar (Draft / Finalized).

    Signals:
        claim_selected(str): emitted when a finalized survey card is clicked
        add_claim_clicked():  emitted when the add-case button is clicked
        survey_finalized(str): emitted after a draft survey is finalized
        resume_survey(str):    emitted when a draft survey card is clicked
    """

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()
    survey_finalized = pyqtSignal(str)
    resume_survey = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._all_data: List[Dict] = []
        self._active_tab = "draft"  # "draft" or "finalized"
        self._buildings_cache: Dict[str, object] = {}
        self._last_refresh_ms = 0
        self._search_timer = None
        self._setup_ui()

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

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
        self._tab_bar = UnderlineTabBar(["مسودة", "منتهية"], self)
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

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.title_label = QLabel(tr("cases.page.title"))
        self.title_label.setFont(create_font(
            size=FontManager.SIZE_TITLE, weight=QFont.Bold, letter_spacing=0
        ))
        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self.title_label)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        add_btn = PrimaryButton(tr("wizard.button.add_case"), icon_name="icon")
        add_btn.clicked.connect(self.add_claim_clicked.emit)
        layout.addWidget(add_btn)

        return header

    def _create_filter_bar(self) -> QWidget:
        form_style = StyleManager.form_input()

        bar = QWidget()
        bar.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 1. Search by reference code (API: referenceCode)
        self._ref_search = QLineEdit()
        self._ref_search.setLayoutDirection(Qt.RightToLeft)
        self._ref_search.setPlaceholderText("بحث بالرمز المرجعي...")
        self._ref_search.setFixedWidth(220)
        self._ref_search.setStyleSheet(form_style)
        self._ref_search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._ref_search)

        # 2. Search by person name (API: intervieweeName)
        self._name_filter = QLineEdit()
        self._name_filter.setLayoutDirection(Qt.RightToLeft)
        self._name_filter.setPlaceholderText("بحث باسم الشخص...")
        self._name_filter.setFixedWidth(200)
        self._name_filter.setStyleSheet(form_style)
        self._name_filter.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._name_filter)

        # 3. Search by building number (API: buildingId)
        self._building_filter = QLineEdit()
        self._building_filter.setLayoutDirection(Qt.RightToLeft)
        self._building_filter.setPlaceholderText("رقم المبنى...")
        self._building_filter.setFixedWidth(160)
        self._building_filter.setStyleSheet(form_style)
        self._building_filter.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._building_filter)

        # 4. Survey type filter (local: 1=Field, 2=Office)
        self._type_filter = QComboBox()
        self._type_filter.setLayoutDirection(Qt.RightToLeft)
        self._type_filter.setFixedWidth(170)
        self._type_filter.setStyleSheet(form_style)
        self._type_filter.addItem("الكل", None)
        self._type_filter.addItem(get_survey_type_display(1), 1)
        self._type_filter.addItem(get_survey_type_display(2), 2)
        self._type_filter.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self._type_filter)

        layout.addStretch()
        return bar

    # -------------------------------------------------------------------------
    # Filter handling
    # -------------------------------------------------------------------------

    def _on_search_changed(self):
        """Debounced search — sends to API after 500ms pause."""
        if self._search_timer and self._search_timer.isActive():
            self._search_timer.stop()
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._load_surveys)
        self._search_timer.start(500)

    def _on_type_changed(self):
        """Survey type dropdown changed — re-filter locally."""
        self._apply_type_filter()

    # -------------------------------------------------------------------------
    # Tab handling
    # -------------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        self._active_tab = "draft" if index == 0 else "finalized"
        self._load_surveys()

    # -------------------------------------------------------------------------
    # Data loading
    # -------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        import time
        now = int(time.time() * 1000)
        if now - self._last_refresh_ms > 500:
            self.refresh()

    def refresh(self, data=None):
        """Refresh surveys from API."""
        import time
        self._last_refresh_ms = int(time.time() * 1000)
        self._load_surveys()

    def _load_surveys(self):
        """Load surveys from API based on active tab and filters."""
        self._all_data = []
        status = "Draft" if self._active_tab == "draft" else "Finalized"
        ref_code = self._ref_search.text().strip() or None
        name = self._name_filter.text().strip() or None
        building = self._building_filter.text().strip() or None

        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            result = ctrl.load_office_surveys(
                status=status,
                page=1,
                page_size=30,
                sort_by="SurveyDate",
                sort_direction="desc",
                reference_code=ref_code,
                interviewee_name=name,
                building_id=building,
            )
            if result.success and result.data:
                building_ids = {s.get("buildingId", "") for s in result.data if s.get("buildingId")}
                self._enrich_buildings_cache(building_ids)

                for s in result.data:
                    self._all_data.append(self._map_survey(s))

            logger.info(f"Loaded {len(self._all_data)} surveys (status={status})")
        except Exception as e:
            logger.warning(f"Error loading surveys (status={status}): {e}")

        self._apply_type_filter()

    def _apply_type_filter(self):
        """Filter displayed cards by survey type (local filter)."""
        type_val = self._type_filter.currentData()
        if type_val is not None:
            filtered = [c for c in self._all_data if c.get("survey_type") == type_val]
        else:
            filtered = self._all_data

        if filtered:
            self._show_cards(filtered)
        else:
            self._show_empty_state()

    def _enrich_buildings_cache(self, building_ids):
        """Fetch building details for IDs not yet cached."""
        if not building_ids:
            return
        try:
            from services.api_client import get_api_client
            from controllers.building_controller import BuildingController
            api = get_api_client()
            bc = BuildingController(self.db)
            for bid in building_ids:
                if not bid or bid in self._buildings_cache:
                    continue
                try:
                    dto = api.get_building_by_id(bid)
                    self._buildings_cache[bid] = bc._api_dto_to_building(dto)
                except Exception:
                    pass
        except Exception:
            pass

    def _map_survey(self, s: Dict) -> Dict:
        """Map Surveys API summary to card data format."""
        building_id = s.get("buildingId", "")
        building_obj = self._buildings_cache.get(building_id)

        unit_num = s.get("unitIdentifier", "")
        unit_obj = None
        if unit_num:
            class _NS:
                def __init__(self, **kw): self.__dict__.update(kw)
            unit_obj = _NS(unit_number=unit_num)

        return {
            "claim_id": s.get("referenceCode") or s.get("id", "N/A"),
            "claim_uuid": s.get("id", ""),
            "claimant_name": s.get("intervieweeName") or "غير محدد",
            "date": (s.get("surveyDate") or "")[:10],
            "status": self._active_tab,
            "building_id": s.get("buildingNumber") or (building_obj.building_id if building_obj else ""),
            "unit_number": unit_num,
            "source_label": get_survey_type_display(s.get("surveyType", 0)),
            "survey_type": s.get("surveyType"),
            "building": building_obj,
            "unit": unit_obj,
            "unit_id": s.get("propertyUnitId", ""),
        }

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------

    def _show_cards(self, data: List[Dict]):
        self._clear_content()

        cfg = _STATUS_CONFIG.get(self._active_tab, _STATUS_CONFIG["draft"])
        icon = cfg["icon"]

        for index, item in enumerate(data):
            row = index // PageDimensions.CARD_COLUMNS
            col = index % PageDimensions.CARD_COLUMNS

            card = ClaimListCard(item, icon_name=icon)
            card.clicked.connect(self._on_card_clicked)
            self.content_layout.addWidget(card, row, col)

        final_row = (len(data) + PageDimensions.CARD_COLUMNS - 1) // PageDimensions.CARD_COLUMNS
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding),
            final_row, 0, 1, PageDimensions.CARD_COLUMNS
        )

    def _show_empty_state(self):
        self._clear_content()

        msg = "لا توجد مسودات حالياً" if self._active_tab == "draft" else "لا توجد مسوحات منتهية بعد"
        empty_state = EmptyState(
            icon_text="+",
            title=msg,
            description="ابدأ بإضافة المسوحات للظهور هنا"
        )

        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 0, 0, 1, 2
        )
        self.content_layout.addWidget(empty_state, 1, 0, 1, 2, Qt.AlignCenter)
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 0, 1, 2
        )

    def _on_card_clicked(self, claim_id: str):
        """Navigate to CaseDetailsPage for both draft and finalized surveys."""
        self.claim_selected.emit(claim_id)

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # -------------------------------------------------------------------------
    # Public interface (backward compatibility)
    # -------------------------------------------------------------------------

    def search_claims(self, query: str, mode: str = "name"):
        pass

    def apply_filters(self, filters: dict):
        pass

    def update_language(self, is_arabic=True):
        self.title_label.setText(tr("cases.page.title"))
        if self._all_data:
            self._show_cards(self._all_data)
