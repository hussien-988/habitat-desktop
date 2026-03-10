# -*- coding: utf-8 -*-
"""
Cases Page — grid of Draft and Open cases with colored top-border cards.

Shows only:
  drafts — Draft surveys  (GET /api/v1/Surveys/office?status=Draft)
  open   — Open claims    (GET /api/Claims?CaseStatus=1)

Completed claims have their own dedicated navbar tab.
"""

import logging
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout,
    QPushButton, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from ..design_system import Colors, PageDimensions
from ..components.empty_state import EmptyState
from ..components.claim_list_card import ClaimListCard
from ..components.primary_button import PrimaryButton
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from services.translation_manager import tr

logger = logging.getLogger(__name__)

_STATUS_CONFIG = {
    "draft": {"color": "#94A3B8", "badge_key": "cases.badge.draft", "icon": "yelow"},
    "open":  {"color": "#F97316", "badge_key": "cases.badge.open",  "icon": "blue"},
}


class CasesPage(QWidget):
    """
    Cases page: card grid with colored top-border per status.

    Signals:
        claim_selected(str): emitted when a survey/claim card is clicked
        add_claim_clicked():  emitted when the add-case button is clicked
        survey_finalized(str): emitted after a draft survey is finalized
        resume_survey(str):    emitted when resume button clicked on draft card
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

        self.header = self._create_header()
        main_layout.addWidget(self.header)

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

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.title_label = QLabel(tr("cases.page.title"))
        self.title_label.setFont(create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold, letter_spacing=0))
        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self.title_label)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        add_btn = PrimaryButton(tr("wizard.button.add_case"), icon_name="icon")
        add_btn.clicked.connect(self.add_claim_clicked.emit)
        layout.addWidget(add_btn)

        return header

    # -------------------------------------------------------------------------
    # Data loading
    # -------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self, data=None):
        self._all_data = []
        self._all_data.extend(self._fetch_surveys(status="Draft"))

        if self._all_data:
            self._show_cards(self._all_data)
        else:
            self._show_empty_state()

    def _fetch_surveys(self, status: str) -> List[Dict]:
        surveys = []
        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            result = ctrl.load_office_surveys(status=status)
            if result.success and result.data:
                surveys = result.data
        except Exception as e:
            logger.warning(f"Failed to fetch surveys (status={status}): {e}")
            return []

        if not surveys:
            return []

        building_ids = {s.get("buildingId", "") for s in surveys if s.get("buildingId")}
        buildings_cache = self._fetch_buildings_by_ids(building_ids)

        items = []
        for s in surveys:
            building_obj = buildings_cache.get(s.get("buildingId"))
            unit_num = s.get("unitIdentifier", "")
            unit_obj = None
            if unit_num:
                class _NS:
                    def __init__(self, **kw): self.__dict__.update(kw)
                unit_obj = _NS(unit_number=unit_num)
            items.append({
                "claim_id":      s.get("referenceCode") or s.get("id", "N/A"),
                "claim_uuid":    s.get("id", ""),
                "claimant_name": s.get("intervieweeName") or "غير محدد",
                "date":          (s.get("surveyDate") or "")[:10],
                "status":        "draft",
                "building":      building_obj,
                "unit":          unit_obj,
                "unit_id":       s.get("propertyUnitId", ""),
                "unit_number":   unit_num,
                "building_id":   s.get("buildingNumber") or (building_obj.building_id if building_obj else ""),
            })

        # Enrich missing names from survey detail
        self._enrich_missing_names(items)

        return items

    def _enrich_missing_names(self, items: List[Dict]):
        """For items with no intervieweeName, fetch name from survey detail/persons."""
        missing = [item for item in items if item.get("claimant_name") == "غير محدد"]
        if not missing:
            return
        try:
            from services.api_client import get_api_client
            api = get_api_client()
        except Exception:
            return
        for item in missing:
            try:
                detail = api.get_office_survey_detail(item["claim_uuid"])
                if detail.get("intervieweeName"):
                    item["claimant_name"] = detail["intervieweeName"]
                    continue
                for rel in (detail.get("relations") or []):
                    pid = rel.get("personId")
                    if pid:
                        person = api._request("GET", f"/v1/Persons/{pid}")
                        parts = [
                            person.get("firstNameArabic", ""),
                            person.get("fatherNameArabic", ""),
                            person.get("familyNameArabic", ""),
                        ]
                        name = " ".join(p for p in parts if p)
                        if name:
                            item["claimant_name"] = name
                            break
            except Exception:
                pass

    def _fetch_claims(self, case_status: int) -> List[Dict]:
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            result = api.get_claims(status=case_status)
            raw = result if isinstance(result, list) else result.get("items", [])
            items = []
            for c in raw:
                items.append({
                    "claim_id":      c.get("claimNumber", ""),
                    "claim_uuid":    c.get("id", ""),
                    "claimant_name": c.get("primaryClaimantName") or "غير محدد",
                    "date":          (c.get("createdAtUtc") or "")[:10],
                    "status":        "open",
                    "unit_number":   c.get("propertyUnitCode", ""),
                })
            return items
        except Exception as e:
            logger.warning(f"Failed to fetch claims (caseStatus={case_status}): {e}")
            return []

    def _fetch_buildings_by_ids(self, building_ids) -> dict:
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

    def _make_card_wrapper(self, item: Dict, color: str, badge_text: str, icon: str) -> QFrame:
        outer = QFrame()
        outer.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        sc = QColor("#919EAB")
        sc.setAlpha(41)
        shadow.setColor(sc)
        outer.setGraphicsEffect(shadow)

        layout = QVBoxLayout(outer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        card = ClaimListCard(item, icon_name=icon)
        card.setGraphicsEffect(None)
        card.setStyleSheet("QFrame#ClaimCard { background: transparent; border: none; }")
        card.clicked.connect(self._on_card_clicked)
        layout.addWidget(card)

        return outer

    def _show_cards(self, data: List[Dict]):
        self._clear_content()
        self.content_layout.setColumnStretch(0, 1)
        self.content_layout.setColumnStretch(1, 1)

        for index, item in enumerate(data):
            row = index // PageDimensions.CARD_COLUMNS
            col = index % PageDimensions.CARD_COLUMNS
            status = item.get("status", "draft")
            cfg = _STATUS_CONFIG.get(status, _STATUS_CONFIG["draft"])
            badge_text = tr(cfg["badge_key"])

            wrapper = self._make_card_wrapper(item, cfg["color"], badge_text, cfg["icon"])
            self.content_layout.addWidget(wrapper, row, col)

        final_row = (len(data) + PageDimensions.CARD_COLUMNS - 1) // PageDimensions.CARD_COLUMNS
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding),
            final_row, 0, 1, PageDimensions.CARD_COLUMNS
        )

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

    # -------------------------------------------------------------------------
    # Search / Filter (called from main window toolbar)
    # -------------------------------------------------------------------------

    def search_claims(self, query: str, mode: str = "name"):
        if not query.strip():
            self.title_label.setText(tr("cases.page.title"))
            self.refresh()
            return
        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            result = ctrl.load_office_surveys(status="Draft")
            all_surveys = result.data if (result.success and result.data) else []
            q = query.strip().lower()
            filtered = []
            for s in all_surveys:
                if mode == "name":
                    if q in (s.get("intervieweeName") or "").lower():
                        filtered.append(s)
                elif mode == "claim_id":
                    if q in (s.get("referenceCode") or "").lower() or q in (s.get("id") or "").lower():
                        filtered.append(s)
                elif mode == "building":
                    if q in (s.get("buildingNumber") or "").lower() or q in (s.get("buildingId") or "").lower():
                        filtered.append(s)
            self._display_search_results(filtered)
        except Exception as e:
            logger.warning(f"Search failed: {e}")

    def apply_filters(self, filters: dict):
        has_filter = any(v for v in filters.values() if v)
        if not has_filter:
            self.title_label.setText(tr("cases.page.title"))
            self.refresh()
            return
        try:
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            result = ctrl.load_office_surveys(status="Draft")
            if not result.success or not result.data:
                self._display_search_results([])
                return
            surveys = result.data
            building_code = filters.get("building_code", "").strip()
            gov_code = filters.get("governorate_code", "").strip()
            filter_date = filters.get("date", "").strip()
            filtered = []
            for s in surveys:
                if building_code:
                    bid = s.get("buildingNumber", "") or ""
                    buid = s.get("buildingId", "") or ""
                    if building_code not in bid and building_code not in buid:
                        continue
                if gov_code:
                    bid = s.get("buildingNumber", "") or ""
                    if not bid.startswith(gov_code):
                        continue
                if filter_date:
                    if (s.get("surveyDate") or "")[:10] != filter_date:
                        continue
                filtered.append(s)
            self._display_search_results(filtered)
        except Exception as e:
            logger.warning(f"Filter failed: {e}")

    def _display_search_results(self, surveys):
        building_ids = {s.get("buildingId", "") for s in surveys if s.get("buildingId")}
        buildings_cache = self._fetch_buildings_by_ids(building_ids)
        items = []
        for s in surveys:
            building_obj = buildings_cache.get(s.get("buildingId"))
            unit_num = s.get("unitIdentifier", "")
            unit_obj = None
            if unit_num:
                class _NS:
                    def __init__(self, **kw): self.__dict__.update(kw)
                unit_obj = _NS(unit_number=unit_num)
            items.append({
                "claim_id":      s.get("referenceCode") or s.get("id", "N/A"),
                "claim_uuid":    s.get("id", ""),
                "claimant_name": s.get("intervieweeName") or "غير محدد",
                "date":          (s.get("surveyDate") or "")[:10],
                "status":        "draft",
                "building":      building_obj,
                "unit":          unit_obj,
                "unit_id":       s.get("propertyUnitId", ""),
                "unit_number":   unit_num,
                "building_id":   s.get("buildingNumber") or (building_obj.building_id if building_obj else ""),
            })
        self.title_label.setText(f"نتائج البحث ({len(items)})")
        if items:
            self._show_cards(items)
        else:
            self._show_empty_state()

    # -------------------------------------------------------------------------
    # Language
    # -------------------------------------------------------------------------

    def update_language(self, is_arabic=True):
        self.title_label.setText(tr("cases.page.title"))
        if self._all_data:
            self._show_cards(self._all_data)
