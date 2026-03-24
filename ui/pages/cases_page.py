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
from services.api_worker import ApiWorker

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
        self._user_role = None
        self._user_id = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._load_surveys)
        self._setup_ui()

    def configure_for_user(self, role: str, user_id: str):
        """Set user context for filtering surveys by ownership."""
        self._user_role = role
        self._user_id = user_id
        self._all_data = []
        self._buildings_cache = {}
        self._clear_content()

        if role in ("data_manager", "admin"):
            self._tab_bar.setVisible(False)
            self._active_tab = "finalized"
            self._type_filter.setVisible(True)
            self._add_btn.setVisible(False)
        else:
            self._add_btn.setVisible(True)

        if role == "office_clerk":
            self._type_filter.setVisible(False)

    # UI Setup

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
        self.content_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.content_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Colors.BACKGROUND};
                border: none;
            }}
        """ + StyleManager.scrollbar())

        self.content_widget = QWidget()
        self.content_layout = QGridLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setVerticalSpacing(PageDimensions.CARD_GAP_VERTICAL)
        self.content_layout.setHorizontalSpacing(PageDimensions.CARD_GAP_HORIZONTAL)
        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area)

        self._show_empty_state()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

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

        self._add_btn = PrimaryButton(tr("wizard.button.add_case"), icon_name="icon")
        self._add_btn.clicked.connect(self.add_claim_clicked.emit)
        layout.addWidget(self._add_btn)

        return header

    def _create_filter_bar(self) -> QWidget:
        form_style = StyleManager.form_input()

        bar = QWidget()
        bar.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Search by contact person name (API: contactPersonName)
        self._name_filter = QLineEdit()
        self._name_filter.setLayoutDirection(Qt.RightToLeft)
        self._name_filter.setPlaceholderText("بحث باسم الشخص...")
        self._name_filter.setFixedWidth(280)
        self._name_filter.setStyleSheet(form_style)
        self._name_filter.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._name_filter)

        # Survey type filter (local: 1=Field, 2=Office)
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
    # Filter handling

    def _on_search_changed(self):
        """Debounced search — sends to API after 500ms pause."""
        self._search_timer.start(500)

    def _on_type_changed(self):
        """Survey type dropdown changed — re-filter locally."""
        self._apply_type_filter()

    # Tab handling

    def _on_tab_changed(self, index: int):
        self._active_tab = "draft" if index == 0 else "finalized"
        self._load_surveys()
    # Data loading

    def refresh(self, data=None):
        """Refresh surveys from API."""
        import time
        self._last_refresh_ms = int(time.time() * 1000)
        self._load_surveys()

    def _load_surveys(self):
        """Load surveys from API based on active tab and filters."""
        self._spinner.show_loading("جاري تحميل المسوحات...")

        status = "Draft" if self._active_tab == "draft" else "Finalized"
        name = self._name_filter.text().strip() or None
        clerk_id = self._user_id if self._user_role == "office_clerk" else None

        self._load_surveys_worker = ApiWorker(
            self._fetch_surveys_data, status, name, clerk_id
        )
        self._load_surveys_worker.finished.connect(self._on_surveys_loaded)
        self._load_surveys_worker.error.connect(self._on_surveys_load_error)
        self._load_surveys_worker.start()

    def _fetch_surveys_data(self, status, name, clerk_id):
        """Fetch surveys and enrich buildings cache (runs in worker thread)."""
        from controllers.survey_controller import SurveyController
        from services.api_client import get_api_client
        from controllers.building_controller import BuildingController

        ctrl = SurveyController(self.db)
        result = ctrl.load_office_surveys(
            status=status,
            page=1,
            page_size=30,
            sort_by="SurveyDate",
            sort_direction="desc",
            contact_person_name=name,
            clerk_id=clerk_id,
        )

        new_buildings = {}
        surveys = []
        if result.success and result.data:
            surveys = result.data
            building_ids = {s.get("buildingId", "") for s in surveys if s.get("buildingId")}

            if building_ids:
                try:
                    api = get_api_client()
                    bc = BuildingController(self.db)
                    for bid in building_ids:
                        if not bid or bid in self._buildings_cache:
                            continue
                        try:
                            dto = api.get_building_by_id(bid)
                            new_buildings[bid] = bc._api_dto_to_building(dto)
                        except Exception:
                            pass
                except Exception:
                    pass

        return {"surveys": surveys, "new_buildings": new_buildings, "status": status}

    def _on_surveys_loaded(self, result):
        """Handle surveys loaded from API."""
        self._spinner.hide_loading()

        self._buildings_cache.update(result.get("new_buildings", {}))
        surveys = result.get("surveys", [])

        self._all_data = []
        for s in surveys:
            self._all_data.append(self._map_survey(s))

        logger.info(f"Loaded {len(self._all_data)} surveys (status={result.get('status')})")
        self._apply_type_filter()

    def _on_surveys_load_error(self, error_msg):
        """Handle surveys loading error."""
        self._spinner.hide_loading()
        logger.warning(f"Error loading surveys: {error_msg}")
        self._all_data = []
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
            "claimant_name": s.get("contactPersonFullName") or s.get("intervieweeName") or "غير محدد",
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
    # Display

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
    # Public interface (backward compatibility)

    def search_claims(self, query: str, mode: str = "name"):
        pass

    def apply_filters(self, filters: dict):
        pass

    def update_language(self, is_arabic=True):
        self.title_label.setText(tr("cases.page.title"))
        if self._all_data:
            self._show_cards(self._all_data)
