# -*- coding: utf-8 -*-
"""
Claim Search Page — UC-006 S01-S02: Search and display existing claims.

Design: Matches project design system (PageDimensions, StyleManager).
Pattern: Follows CompletedClaimsPage conventions (grid + cards + search).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame, QGridLayout,
    QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ui.design_system import Colors, PageDimensions
from ui.components.empty_state import EmptyState
from ui.components.claim_list_card import ClaimListCard
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)

# Status filter options: (API int value, Arabic label)
_STATUS_OPTIONS = [
    (None, "الكل"),
    (1, "مسودة"),
    (2, "مقدمة"),
    (3, "قيد المراجعة"),
    (4, "تم التحقق"),
    (5, "معتمدة"),
    (6, "مرفوضة"),
    (7, "مؤرشفة"),
]

# Source filter options
_SOURCE_OPTIONS = [
    (None, "الكل"),
    (1, "ميداني"),
    (2, "مكتبي"),
]


class ClaimSearchPage(QWidget):
    """UC-006 S01-S02: Search existing claims and display results."""

    claim_selected = pyqtSignal(str)  # claim_id for edit
    back_requested = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._all_data = []
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)
        self.setStyleSheet(StyleManager.page_background())

        # Header
        main_layout.addWidget(self._create_header())

        # Filter bar
        main_layout.addWidget(self._create_filter_bar())

        # Content area (scrollable grid)
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_area.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}"
        )

        self.content_widget = QWidget()
        self.content_layout = QGridLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
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

        self.title_label = QLabel("البحث عن مطالبة")
        title_font = create_font(
            size=FontManager.SIZE_TITLE,
            weight=QFont.Bold,
            letter_spacing=0,
        )
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self.title_label)

        layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        back_btn = QPushButton("رجوع")
        back_btn.setFixedSize(100, 40)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Bold,
        ))
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_btn)

        return header

    def _create_filter_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        form_style = StyleManager.form_input()

        # Status filter
        status_label = QLabel("الحالة:")
        status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; font-size: 12px;")
        layout.addWidget(status_label)

        self._status_combo = QComboBox()
        for val, label in _STATUS_OPTIONS:
            self._status_combo.addItem(label, val)
        self._status_combo.setStyleSheet(form_style)
        self._status_combo.setMinimumWidth(120)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._status_combo)

        # Source filter
        source_label = QLabel("المصدر:")
        source_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; font-size: 12px;")
        layout.addWidget(source_label)

        self._source_combo = QComboBox()
        for val, label in _SOURCE_OPTIONS:
            self._source_combo.addItem(label, val)
        self._source_combo.setStyleSheet(form_style)
        self._source_combo.setMinimumWidth(120)
        self._source_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._source_combo)

        # Text search
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("بحث بالاسم أو رقم المطالبة...")
        self._search_input.setStyleSheet(form_style)
        self._search_input.setMinimumWidth(200)
        self._search_input.textChanged.connect(self._on_text_search)
        layout.addWidget(self._search_input)

        layout.addStretch()
        return bar

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self, data=None):
        """Load claims from API using current filters."""
        self._spinner.show_loading("جاري البحث عن المطالبات...")
        try:
            self._all_data = []
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController()

            status_val = self._status_combo.currentData()
            source_val = self._source_combo.currentData()

            result = ctrl.search_claims_from_api(
                case_status=status_val,
                claim_source=source_val,
            )
            if result.success and result.data:
                for dto in result.data:
                    self._all_data.append(self._map_summary_to_card(dto))

            self._apply_text_filter()
        except Exception as e:
            logger.warning(f"Error loading claims: {e}")
            self._apply_text_filter()
        finally:
            self._spinner.hide_loading()

    @staticmethod
    def _map_summary_to_card(dto: dict) -> dict:
        """Map API ClaimSummaryDto to ClaimListCard data format."""
        return {
            "claim_id": dto.get("claimId") or dto.get("id", ""),
            "claim_uuid": dto.get("claimId") or dto.get("id", ""),
            "claimant_name": dto.get("primaryClaimantName") or "غير محدد",
            "date": (dto.get("createdAtUtc") or dto.get("surveyDate") or "")[:10],
            "status": str(dto.get("claimStatus") or dto.get("status") or ""),
            "building_id": dto.get("buildingId") or "",
            "unit_number": dto.get("propertyUnitCode") or "",
            "unit_id": dto.get("propertyUnitId") or "",
            "governorate_name_ar": dto.get("governorateNameArabic") or "",
            "district_name_ar": dto.get("districtNameArabic") or "",
            "subdistrict_name_ar": dto.get("subDistrictNameArabic") or "",
            "neighborhood_name_ar": dto.get("neighborhoodNameArabic") or "",
            "building": None,
            "unit": None,
        }

    def _on_filter_changed(self):
        self.refresh()

    def _on_text_search(self, text: str):
        self._apply_text_filter()

    def _apply_text_filter(self):
        query = self._search_input.text().strip().lower()
        if not query:
            filtered = self._all_data
        else:
            filtered = [
                item for item in self._all_data
                if query in (item.get("claimant_name") or "").lower()
                or query in (item.get("claim_id") or "").lower()
            ]

        self.title_label.setText(
            f"البحث عن مطالبة ({len(filtered)})" if self._all_data else "البحث عن مطالبة"
        )

        if filtered:
            self._show_cards(filtered)
        else:
            self._show_empty_state()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _show_cards(self, data):
        self._clear_content()
        self.content_layout.setColumnStretch(0, 1)
        self.content_layout.setColumnStretch(1, 1)

        for index, item in enumerate(data):
            row = index // PageDimensions.CARD_COLUMNS
            col = index % PageDimensions.CARD_COLUMNS

            card = ClaimListCard(item, icon_name="blue")
            card.clicked.connect(self._on_card_clicked)
            self.content_layout.addWidget(card, row, col)

        final_row = (len(data) + PageDimensions.CARD_COLUMNS - 1) // PageDimensions.CARD_COLUMNS
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding),
            final_row, 0, 1, PageDimensions.CARD_COLUMNS,
        )

    def _show_empty_state(self):
        self._clear_content()
        empty = EmptyState(
            icon_text="🔍",
            title="لا توجد مطالبات",
            description="استخدم الفلاتر للبحث عن المطالبات",
        )
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 0, 0, 1, 2
        )
        self.content_layout.addWidget(empty, 1, 0, 1, 2, Qt.AlignCenter)
        self.content_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), 2, 0, 1, 2
        )

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_card_clicked(self, claim_id: str):
        self.claim_selected.emit(claim_id)

    def update_language(self, is_arabic=True):
        self.title_label.setText("البحث عن مطالبة" if is_arabic else "Search Claims")
