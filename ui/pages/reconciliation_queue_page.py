# -*- coding: utf-8 -*-
"""Reconciliation queue page — records committed via Keep-Separate that need review.

Persons whose National ID was cleared and property units whose identifier was
suffixed land here so a reviewer can verify/repair them later. Read-only list
(the actual edit happens through the normal entity pages).
"""

import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QScrollArea, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QColor

from repositories.database import Database
from controllers.import_controller import ImportController
from app.config import Pages
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.components.empty_state import EmptyState
from ui.components.toast import Toast
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, ScreenScale
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

_PAGINATION_BTN_STYLE = """
    QPushButton {
        background: #FFFFFF; color: #37474F;
        border: 1px solid #CFD8DC; border-radius: 8px; padding: 0 16px;
    }
    QPushButton:hover { background: #ECEFF1; }
    QPushButton:disabled { color: #B0BEC5; background: #F5F7FA; }
"""


class _ReconciliationWorker(QThread):
    finished = Signal(dict)
    error = Signal(str, str)

    def __init__(self, controller: ImportController, entity_type, page, page_size):
        super().__init__()
        self.controller = controller
        self.entity_type = entity_type
        self.page = page
        self.page_size = page_size

    def run(self):
        result = self.controller.get_reconciliation_queue(
            self.entity_type, self.page, self.page_size
        )
        if result.success:
            self.finished.emit(result.data or {})
        else:
            trace = getattr(result.error, "trace_id", "") or ""
            self.error.emit(result.message_ar or result.message, trace)


class ReconciliationQueuePage(QWidget):
    """Lists Keep-Separate records (persons + units) awaiting reconciliation."""

    open_person = pyqtSignal(str)   # personId
    open_unit = pyqtSignal(str)     # propertyUnitId
    back_requested = pyqtSignal()   # return to the import packages page

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_controller = ImportController(db)
        self._worker = None
        self._loading = False
        self._user_role = None
        self._current_page = 1
        self._page_size = 20
        self._total_pages = 1
        self._cards = []
        self._setup_ui()

    # -- UI Setup ----------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet("background-color: #f0f7ff;")
        self.setLayoutDirection(get_layout_direction())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.reconciliation.title"))

        self._stat_persons = StatPill(tr("page.reconciliation.stat_persons"))
        self._stat_persons.set_count(0)
        self._header.add_stat_pill(self._stat_persons)

        self._stat_units = StatPill(tr("page.reconciliation.stat_units"))
        self._stat_units.set_count(0)
        self._header.add_stat_pill(self._stat_units)

        self._back_btn = QPushButton(tr("action.back"))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setStyleSheet(StyleManager.dark_action_button())
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._back_btn)

        self._refresh_btn = QPushButton(tr("page.reconciliation.refresh"))
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setStyleSheet(StyleManager.refresh_button_dark())
        self._refresh_btn.clicked.connect(lambda: self.refresh())
        self._header.add_action_widget(self._refresh_btn)

        self._type_filter = QComboBox()
        self._type_filter.setLayoutDirection(get_layout_direction())
        self._type_filter.setStyleSheet(StyleManager.dark_combo_box())
        self._type_filter.addItem(tr("page.reconciliation.all_types"), "")
        self._type_filter.addItem(tr("page.reconciliation.stat_persons"), "person")
        self._type_filter.addItem(tr("page.reconciliation.stat_units"), "propertyunit")
        self._type_filter.currentIndexChanged.connect(self._on_filter_changed)
        self._header.add_row2_widget(self._type_filter)

        root.addWidget(self._header)

        self._accent = AccentLine()
        root.addWidget(self._accent)

        content_area = QWidget()
        content_area.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(), 14,
        )
        content_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        scroll.setWidget(scroll_content)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._content_layout.addWidget(self._cards_container)

        self._pagination_footer = self._build_pagination_footer()
        self._content_layout.addWidget(self._pagination_footer)
        self._pagination_footer.setVisible(False)

        self._empty_state = EmptyState(
            icon_name="tdesign_no-result",
            title=tr("page.reconciliation.empty_title"),
            description=tr("page.reconciliation.empty_hint"),
        )
        self._empty_state.setMinimumHeight(ScreenScale.h(280))
        self._content_layout.addWidget(self._empty_state)
        self._empty_state.setVisible(False)

        self._content_layout.addStretch()

        content_layout.addWidget(scroll, 1)
        root.addWidget(content_area, 1)

        self._spinner = LoadingSpinnerOverlay(self)

    def _build_pagination_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(ScreenScale.h(54))
        footer.setStyleSheet(
            "QFrame { background: #FAFCFF; border: 1px solid #E2EAF2; border-radius: 12px; }"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 0, 16, 0)
        fl.setSpacing(10)

        self._prev_btn = QPushButton(tr("page.reconciliation.previous"))
        self._prev_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setFixedHeight(ScreenScale.h(34))
        self._prev_btn.setStyleSheet(_PAGINATION_BTN_STYLE)
        self._prev_btn.clicked.connect(lambda: self._go_to_page(self._current_page - 1))
        fl.addWidget(self._prev_btn)

        self._page_label = QLabel("1 / 1")
        self._page_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setStyleSheet("color: #546E7A; background: transparent; border: none;")
        fl.addWidget(self._page_label)

        self._next_btn = QPushButton(tr("page.reconciliation.next"))
        self._next_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setFixedHeight(ScreenScale.h(34))
        self._next_btn.setStyleSheet(_PAGINATION_BTN_STYLE)
        self._next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))
        fl.addWidget(self._next_btn)

        fl.addStretch()
        return footer

    # -- Cards -------------------------------------------------------------

    def _clear_cards(self):
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet("color: #1F3A5F; background: transparent; border: none;")
        apply_label_alignment(lbl)
        return lbl

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("reconCard")
        card.setStyleSheet("""
            QFrame#reconCard {
                background: #FFFFFF;
                border: 1px solid #E2EAF2;
                border-radius: 12px;
            }
            QFrame#reconCard QLabel { background: transparent; border: none; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 18))
        card.setGraphicsEffect(shadow)
        return card

    def _info_label(self, text: str, color: str = "#546E7A", size: int = 9) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(create_font(size=size, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet(f"color: {color};")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return lbl

    def _open_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        btn.setFixedHeight(ScreenScale.h(32))
        btn.setMinimumWidth(ScreenScale.w(110))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE}; color: white;
                border: none; border-radius: 8px; padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #1A56DB; }}
        """)
        return btn

    @staticmethod
    def _short_date(value) -> str:
        s = str(value or "")
        return s[:10] if len(s) >= 10 else s

    def _build_person_card(self, item: dict) -> QFrame:
        card = self._make_card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(4)

        name = QLabel(str(item.get("fullNameArabic") or "-"))
        name.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        name.setStyleSheet("color: #16243B;")
        apply_label_alignment(name)
        info.addWidget(name)

        nid_chip = QLabel(
            f"{tr('page.reconciliation.person_preserved_nid')}: "
            f"{item.get('preservedNationalId') or '-'}"
        )
        nid_chip.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        nid_chip.setStyleSheet(
            "color: #92400E; background: #FEF3C7;"
            " border: 1px solid #FDE68A; border-radius: 8px; padding: 3px 10px;"
        )
        nid_row = QHBoxLayout()
        nid_row.setContentsMargins(0, 0, 0, 0)
        nid_row.addWidget(nid_chip)
        nid_row.addStretch()
        info.addLayout(nid_row)

        meta = QHBoxLayout()
        meta.setSpacing(18)
        meta.addWidget(self._info_label(
            f"{tr('page.reconciliation.person_mobile')}: {item.get('mobileNumber') or '-'}"
        ))
        meta.addWidget(self._info_label(
            f"{tr('page.reconciliation.last_modified')}: "
            f"{self._short_date(item.get('lastModifiedAtUtc'))}"
        ))
        meta.addStretch()
        info.addLayout(meta)

        layout.addLayout(info, 1)

        person_id = str(item.get("personId") or "")
        btn = self._open_button(tr("page.reconciliation.open_person"))
        btn.clicked.connect(lambda _=False, pid=person_id: self._on_open_person(pid))
        layout.addWidget(btn, 0, Qt.AlignVCenter)
        return card

    def _build_unit_card(self, item: dict) -> QFrame:
        card = self._make_card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(4)

        building = QLabel(
            f"{tr('page.reconciliation.unit_building')}: "
            f"{item.get('buildingCode') or '-'}"
        )
        building.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        building.setStyleSheet("color: #16243B;")
        apply_label_alignment(building)
        info.addWidget(building)

        # current ← original (LTR so the arrow/identifiers read correctly)
        change = QLabel(
            f"{item.get('currentUnitIdentifier') or '-'}  ←  "
            f"{item.get('originalUnitIdentifier') or '-'}"
        )
        change.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        change.setLayoutDirection(Qt.LeftToRight)
        change.setStyleSheet(
            "color: #1E40AF; background: #EFF6FF;"
            " border: 1px solid #BFDBFE; border-radius: 8px; padding: 3px 10px;"
        )
        change_row = QHBoxLayout()
        change_row.setContentsMargins(0, 0, 0, 0)
        change_row.addWidget(change)
        change_row.addStretch()
        info.addLayout(change_row)

        info.addWidget(self._info_label(
            f"{tr('page.reconciliation.last_modified')}: "
            f"{self._short_date(item.get('lastModifiedAtUtc'))}"
        ))

        layout.addLayout(info, 1)

        unit_id = str(item.get("propertyUnitId") or "")
        btn = self._open_button(tr("page.reconciliation.open_unit"))
        btn.clicked.connect(lambda _=False, uid=unit_id: self._on_open_unit(uid))
        layout.addWidget(btn, 0, Qt.AlignVCenter)
        return card

    def _on_open_person(self, person_id: str):
        if person_id:
            self.open_person.emit(person_id)

    def _on_open_unit(self, unit_id: str):
        if unit_id:
            self.open_unit.emit(unit_id)

    # -- Data loading ------------------------------------------------------

    def _on_filter_changed(self):
        self._current_page = 1
        self._load()

    def _go_to_page(self, page: int):
        if page < 1 or page > self._total_pages or page == self._current_page:
            return
        self._current_page = page
        self._load()

    def refresh(self, data=None):
        self._current_page = 1
        self._load()

    def _load(self):
        if self._loading:
            return
        self._loading = True

        if self._worker and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except Exception:
                pass
            self._worker.quit()
            self._worker.wait(500)

        entity_type = self._type_filter.currentData() or None
        self._spinner.show_loading(tr("page.reconciliation.loading"))
        self._worker = _ReconciliationWorker(
            self.import_controller, entity_type,
            self._current_page, self._page_size,
        )
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, data: dict):
        self._loading = False
        self._spinner.hide_loading()

        persons = data.get("persons") or []
        units = data.get("propertyUnits") or []
        persons_total = int(data.get("personsTotalCount", 0) or 0)
        units_total = int(data.get("propertyUnitsTotalCount", 0) or 0)

        self._stat_persons.set_count(persons_total)
        self._stat_units.set_count(units_total)

        self._clear_cards()

        entity_type = self._type_filter.currentData() or ""
        show_persons = entity_type in ("", "person")
        show_units = entity_type in ("", "propertyunit")

        if show_persons and persons:
            title = self._section_title(tr("page.reconciliation.section_persons"))
            self._cards_layout.addWidget(title)
            self._cards.append(title)
            for item in persons:
                card = self._build_person_card(item)
                self._cards_layout.addWidget(card)
                self._cards.append(card)

        if show_units and units:
            title = self._section_title(tr("page.reconciliation.section_units"))
            self._cards_layout.addWidget(title)
            self._cards.append(title)
            for item in units:
                card = self._build_unit_card(item)
                self._cards_layout.addWidget(card)
                self._cards.append(card)

        # Pagination: pageSize applies per entity type, so size pages off the
        # larger of the two scoped totals.
        if entity_type == "person":
            scoped_total = persons_total
        elif entity_type == "propertyunit":
            scoped_total = units_total
        else:
            scoped_total = max(persons_total, units_total)
        self._total_pages = max(1, math.ceil(scoped_total / self._page_size))

        has_rows = bool(self._cards)
        self._empty_state.setVisible(not has_rows)
        self._cards_container.setVisible(has_rows)
        self._update_pagination()

    def _update_pagination(self):
        show = self._total_pages > 1
        self._pagination_footer.setVisible(show)
        if show:
            self._page_label.setText(f"{self._current_page} / {self._total_pages}")
            self._prev_btn.setEnabled(self._current_page > 1)
            self._next_btn.setEnabled(self._current_page < self._total_pages)

    def _on_error(self, message: str, trace_id: str):
        self._loading = False
        self._spinner.hide_loading()
        self._clear_cards()
        self._cards_container.setVisible(False)
        self._pagination_footer.setVisible(False)
        self._empty_state.setVisible(True)
        Toast.show_toast(self, message or tr("import.error.reconciliation_queue_failed"), Toast.ERROR)

    # -- Role / language ---------------------------------------------------

    def configure_for_role(self, role: str):
        self._user_role = role

    def update_language(self, is_arabic: bool = True):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.reconciliation.title"))
        self._stat_persons.set_label(tr("page.reconciliation.stat_persons"))
        self._stat_units.set_label(tr("page.reconciliation.stat_units"))
        self._back_btn.setText(tr("action.back"))
        self._refresh_btn.setText(tr("page.reconciliation.refresh"))
        self._prev_btn.setText(tr("page.reconciliation.previous"))
        self._next_btn.setText(tr("page.reconciliation.next"))
