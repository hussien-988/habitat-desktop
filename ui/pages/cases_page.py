# -*- coding: utf-8 -*-
"""
Cases Page — displays office surveys grouped in 3 internal sub-tabs.

Sub-tabs:
  0. مسودات  (Draft)    — unprocessed surveys, includes finalize button
  1. فاينالايز (Finalized) — surveys where process-claims has been run
  2. مكتمل   (Completed) — surveys in Submitted / UnderReview / Verified state
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout,
    QPushButton
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


_TABS = [
    {"label_key": "cases.tab.drafts",    "statuses": ["Draft"],                             "show_finalize": True},
    {"label_key": "cases.tab.finalized", "statuses": ["Finalized"],                         "show_finalize": False},
    {"label_key": "cases.tab.completed", "statuses": ["Submitted", "UnderReview", "Verified"], "show_finalize": False},
]

_TAB_BTN_ACTIVE = """
    QPushButton {
        background-color: #1E3A8A;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 5px 20px;
        font-size: 11pt;
        font-weight: 600;
    }
"""

_TAB_BTN_INACTIVE = """
    QPushButton {
        background: transparent;
        color: #475569;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 5px 20px;
        font-size: 11pt;
        font-weight: 400;
    }
    QPushButton:hover {
        background-color: #F1F5F9;
    }
"""


class CasesPage(QWidget):
    """
    Cases page: one tab-bar with 3 sub-tabs for survey states.

    Signals:
        claim_selected(str): emitted when a survey card is clicked
        add_claim_clicked(): emitted when the add-case button is clicked
        survey_finalized(str): emitted after a draft survey is finalized
    """

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()
    survey_finalized = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claims_data = []          # data of the currently visible tab
        self._active_tab = 0
        self._tab_data = {0: [], 1: [], 2: []}
        self._tab_buttons = []
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
        main_layout.setSpacing(PageDimensions.HEADER_GAP)
        self.setStyleSheet(StyleManager.page_background())

        # Header
        self.header = self._create_header()
        main_layout.addWidget(self.header)

        # Sub-tab bar
        self.tab_bar = self._create_tab_bar()
        main_layout.addWidget(self.tab_bar)

        # Scrollable content
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
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setVerticalSpacing(PageDimensions.CARD_GAP_VERTICAL)
        self.content_layout.setHorizontalSpacing(PageDimensions.CARD_GAP_HORIZONTAL)
        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area)

        self._show_empty_state()

    def _create_header(self):
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.title_label = QLabel(tr("navbar.tab.cases"))
        self.title_label.setFont(create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold, letter_spacing=0))
        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self.title_label)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        add_btn = PrimaryButton(tr("wizard.button.add_case") if tr("wizard.button.add_case") != "wizard.button.add_case" else "إضافة حالة جديدة", icon_name="icon")
        add_btn.clicked.connect(self.add_claim_clicked.emit)
        layout.addWidget(add_btn)

        return header

    def _create_tab_bar(self):
        bar = QWidget()
        bar.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._tab_buttons = []
        for i, tab in enumerate(_TABS):
            btn = QPushButton(tr(tab["label_key"]))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_TAB_BTN_ACTIVE if i == 0 else _TAB_BTN_INACTIVE)
            idx = i
            btn.clicked.connect(lambda checked, x=idx: self._on_tab_clicked(x))
            self._tab_buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        return bar

    # -------------------------------------------------------------------------
    # Tab switching
    # -------------------------------------------------------------------------

    def _on_tab_clicked(self, index: int):
        if self._active_tab == index:
            return
        self._active_tab = index
        self._update_tab_styles()
        self._load_and_show_tab(index, force=False)

    def _update_tab_styles(self):
        for i, btn in enumerate(self._tab_buttons):
            btn.setStyleSheet(_TAB_BTN_ACTIVE if i == self._active_tab else _TAB_BTN_INACTIVE)

    def _load_and_show_tab(self, index: int, force: bool = True):
        """Load data for tab `index` if not cached (or if force=True) then display."""
        if force or not self._tab_data.get(index):
            self._tab_data[index] = self._fetch_tab_surveys(index)
        self.claims_data = self._tab_data[index]
        if self.claims_data:
            self._show_cards(index)
        else:
            self._show_empty_state()

    def _fetch_tab_surveys(self, index: int):
        """Fetch surveys from API for the given tab index."""
        tab = _TABS[index]
        surveys = []
        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            for status in tab["statuses"]:
                result = ctrl.load_office_surveys(status=status)
                if result.success and result.data:
                    surveys.extend(result.data)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Tab {index} load failed: {e}")

        if not surveys:
            return []

        # Enrich with building objects (for Draft tab especially)
        building_ids = {s.get('buildingId', '') for s in surveys if s.get('buildingId')}
        buildings_cache = self._fetch_buildings_by_ids(building_ids)

        items = []
        for s in surveys:
            building_obj = buildings_cache.get(s.get('buildingId'))
            unit_num = s.get('unitIdentifier', '')
            unit_obj = None
            if unit_num:
                class _NS:
                    def __init__(self, **kw): self.__dict__.update(kw)
                unit_obj = _NS(unit_number=unit_num)

            items.append({
                'claim_id': s.get('referenceCode') or s.get('id', 'N/A'),
                'claim_uuid': s.get('id', ''),
                'claimant_name': s.get('intervieweeName') or 'غير محدد',
                'date': (s.get('surveyDate') or '')[:10],
                'status': tab["statuses"][0].lower(),
                'building': building_obj,
                'unit': unit_obj,
                'unit_id': s.get('propertyUnitId', ''),
                'unit_number': unit_num,
                'building_id': s.get('buildingNumber') or (building_obj.building_id if building_obj else ''),
            })
        return items

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------

    def _show_empty_state(self):
        self._clear_content()
        empty_state = EmptyState(
            icon_text="+",
            title="لا توجد بيانات بعد",
            description="لا يوجد سجلات لهذه الحالة"
        )
        self.content_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 0, 0, 1, 2)
        self.content_layout.addWidget(empty_state, 1, 0, 1, 2, Qt.AlignCenter)
        self.content_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 0, 1, 2)

    def _show_cards(self, tab_index: int):
        self._clear_content()
        self.content_layout.setColumnStretch(0, 1)
        self.content_layout.setColumnStretch(1, 1)

        show_finalize = _TABS[tab_index]["show_finalize"]
        icon = "yelow" if show_finalize else "green"

        for index, claim in enumerate(self.claims_data):
            row = index // PageDimensions.CARD_COLUMNS
            col = index % PageDimensions.CARD_COLUMNS

            if show_finalize:
                # Draft tab: card + finalize button
                container = QFrame()
                container.setStyleSheet("background: transparent; border: none;")
                c_layout = QVBoxLayout(container)
                c_layout.setContentsMargins(0, 0, 0, 0)
                c_layout.setSpacing(6)

                card = ClaimListCard(claim, icon_name=icon)
                card.clicked.connect(self._on_card_clicked)
                c_layout.addWidget(card)

                finalize_btn = QPushButton("إتمام المطالبة")
                finalize_btn.setCursor(Qt.PointingHandCursor)
                finalize_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1E3A8A;
                        color: #FFFFFF;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-size: 11px;
                        font-weight: 600;
                    }
                    QPushButton:hover { background-color: #1E40AF; }
                """)
                uid = claim.get('claim_uuid', '')
                finalize_btn.clicked.connect(
                    lambda checked, u=uid: self._on_finalize_clicked(u)
                )
                c_layout.addWidget(finalize_btn)
                self.content_layout.addWidget(container, row, col)
            else:
                # Finalized / Completed tabs: card only
                card = ClaimListCard(claim, icon_name=icon)
                card.clicked.connect(self._on_card_clicked)
                self.content_layout.addWidget(card, row, col)

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        final_row = (len(self.claims_data) + PageDimensions.CARD_COLUMNS - 1) // PageDimensions.CARD_COLUMNS
        self.content_layout.addItem(spacer, final_row, 0, 1, PageDimensions.CARD_COLUMNS)

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    def _on_card_clicked(self, claim_id: str):
        self.claim_selected.emit(claim_id)

    def _on_finalize_clicked(self, claim_uuid: str):
        if not claim_uuid:
            return
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            api.finalize_office_survey(claim_uuid, {
                "autoCreateClaim": True,
                "finalNotes": "",
                "durationMinutes": 1
            })
            api.finalize_survey_status(claim_uuid)
            from ui.components.toast import Toast
            Toast.show_toast(self, "تم إتمام المطالبة بنجاح", Toast.SUCCESS)
            self.survey_finalized.emit(claim_uuid)
            # Invalidate cache for draft and finalized tabs, then switch to finalized
            self._tab_data[0] = []
            self._tab_data[1] = []
            self._active_tab = 1
            self._update_tab_styles()
            self._load_and_show_tab(1, force=True)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Finalize failed: {e}")
            from ui.error_handler import ErrorHandler
            ErrorHandler.show_error(self, f"فشل إتمام المطالبة:\n{e}", "خطأ")

    # -------------------------------------------------------------------------
    # Data lifecycle
    # -------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self, data=None):
        """Reload all cached tab data and redisplay active tab."""
        self._tab_data = {0: [], 1: [], 2: []}
        self._load_and_show_tab(self._active_tab, force=True)

    def _fetch_buildings_by_ids(self, building_ids):
        """Fetch Building objects by UUID from API with local DB fallback."""
        cache = {}
        if not building_ids:
            return cache
        try:
            from services.api_client import get_api_client
            from controllers.building_controller import BuildingController
            api = get_api_client()
            bc = BuildingController(self.db)
            for bid in building_ids:
                if not bid:
                    continue
                try:
                    dto = api.get_building_by_id(bid)
                    cache[bid] = bc._api_dto_to_building(dto)
                except Exception:
                    pass
        except Exception:
            pass
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

    # -------------------------------------------------------------------------
    # Search / Filter (only active on Draft tab)
    # -------------------------------------------------------------------------

    def search_claims(self, query: str, mode: str = "name"):
        """Search within current tab's surveys (API filter)."""
        if not query.strip():
            self.title_label.setText(tr("navbar.tab.cases"))
            self.refresh()
            return
        try:
            ctrl_module = __import__('controllers.survey_controller', fromlist=['SurveyController'])
            ctrl = ctrl_module.SurveyController(self.db)
            tab = _TABS[self._active_tab]
            all_surveys = []
            for status in tab["statuses"]:
                result = ctrl.load_office_surveys(status=status)
                if result.success and result.data:
                    all_surveys.extend(result.data)
            q = query.strip().lower()
            filtered = []
            for s in all_surveys:
                if mode == "name":
                    if q in (s.get('intervieweeName') or '').lower():
                        filtered.append(s)
                elif mode == "claim_id":
                    if q in (s.get('referenceCode') or '').lower() or q in (s.get('id') or '').lower():
                        filtered.append(s)
                elif mode == "building":
                    if q in (s.get('buildingNumber') or '').lower() or q in (s.get('buildingId') or '').lower():
                        filtered.append(s)
            self._display_search_results(filtered)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Search failed: {e}")

    def apply_filters(self, filters: dict):
        """Apply filters on Draft tab surveys."""
        has_filter = any(v for v in filters.values() if v)
        if not has_filter:
            self.title_label.setText(tr("navbar.tab.cases"))
            self.refresh()
            return
        try:
            ctrl_module = __import__('controllers.survey_controller', fromlist=['SurveyController'])
            ctrl = ctrl_module.SurveyController(self.db)
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
                if building_code:
                    bid = s.get('buildingNumber', '') or ''
                    buid = s.get('buildingId', '') or ''
                    if building_code not in bid and building_code not in buid:
                        continue
                if gov_code:
                    bid = s.get('buildingNumber', '') or ''
                    if not bid.startswith(gov_code):
                        continue
                if filter_date:
                    if (s.get('surveyDate') or '')[:10] != filter_date:
                        continue
                filtered.append(s)
            self._display_search_results(filtered)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Filter failed: {e}")

    def _display_search_results(self, surveys):
        building_ids = {s.get('buildingId', '') for s in surveys if s.get('buildingId')}
        buildings_cache = self._fetch_buildings_by_ids(building_ids)
        self.claims_data = []
        tab = _TABS[self._active_tab]
        for s in surveys:
            building_obj = buildings_cache.get(s.get('buildingId'))
            unit_num = s.get('unitIdentifier', '')
            unit_obj = None
            if unit_num:
                class _NS:
                    def __init__(self, **kw): self.__dict__.update(kw)
                unit_obj = _NS(unit_number=unit_num)
            self.claims_data.append({
                'claim_id': s.get('referenceCode') or s.get('id', 'N/A'),
                'claim_uuid': s.get('id', ''),
                'claimant_name': s.get('intervieweeName') or 'غير محدد',
                'date': (s.get('surveyDate') or '')[:10],
                'status': tab["statuses"][0].lower(),
                'building': building_obj,
                'unit': unit_obj,
                'unit_id': s.get('propertyUnitId', ''),
                'unit_number': unit_num,
                'building_id': s.get('buildingNumber') or (building_obj.building_id if building_obj else ''),
            })
        self.title_label.setText(f"نتائج البحث ({len(self.claims_data)})")
        if self.claims_data:
            self._show_cards(self._active_tab)
        else:
            self._show_empty_state()

    # -------------------------------------------------------------------------
    # Language
    # -------------------------------------------------------------------------

    def update_language(self, is_arabic=True):
        self.title_label.setText(tr("navbar.tab.cases"))
        for i, btn in enumerate(self._tab_buttons):
            btn.setText(tr(_TABS[i]["label_key"]))
        self._load_and_show_tab(self._active_tab, force=False)
