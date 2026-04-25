# -*- coding: utf-8 -*-
"""Claim comparison page — full-page comparison and merge resolution."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QScrollArea,
    QSizePolicy, QGraphicsDropShadowEffect, QTextEdit,
    QGridLayout,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon, QCursor

from repositories.database import Database
from services.duplicate_service import DuplicateService
from services.conflict_classifier import get_conflict_display_category, PERSON
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, ButtonDimensions, ScreenScale
from ui.components.dark_header_zone import DarkHeaderZone
from app.config import Pages
from ui.components.accent_line import AccentLine
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.animation_utils import stagger_fade_in
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction, get_text_alignment
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

RADIO_STYLE = StyleManager.radio_button()

# Field keys whose values are always Latin (digits / Latin punctuation).
# Cells for these fields render with LayoutDirection=LeftToRight so the
# digits and separators don't get bidi-reordered inside an Arabic UI.
_LTR_FIELD_KEYS = {
    "national_id",
    "date_of_birth",
    "phone_number",
    "building_code",
    "area_sqm",
    "rooms",
    "floor",
    "unit_number",
    "residential_units",
    "commercial_units",
    "total_units",
}


def _find_in_staged_persons(staged_snapshot, entity_id):
    """Search the staged-entities payload for a person record by id.

    staged_snapshot shape (from api.get_staged_entities):
      { "persons": [...], "buildings": [...], "propertyUnits": [...], ... }
    Each list contains staged entity dicts with various id fields.
    """
    return _find_in_staged_collection(staged_snapshot, "persons", entity_id)


def _find_in_staged_property_units(staged_snapshot, entity_id):
    """Search the staged-entities payload for a property unit by id."""
    return _find_in_staged_collection(staged_snapshot, "propertyUnits", entity_id)


def _find_in_staged_buildings(staged_snapshot, building_id):
    """Search the staged-entities payload for a building by id."""
    return _find_in_staged_collection(staged_snapshot, "buildings", building_id)


def _find_in_staged_collection(staged_snapshot, collection_key, entity_id):
    """Generic id-lookup across one of the staged-entities lists.

    Returns the unwrapped staging payload (`stagingData` / `entityData` /
    the item itself) so callers can read it like a regular DTO.
    """
    if not staged_snapshot or not entity_id:
        return None
    items = (
        staged_snapshot.get(collection_key)
        if isinstance(staged_snapshot, dict) else None
    )
    if not isinstance(items, list):
        return None
    target = str(entity_id)
    id_keys = (
        "id", "originalEntityId", "stagedEntityId",
        "personId", "buildingId", "propertyUnitId", "entityId",
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in id_keys:
            val = item.get(key)
            if val and str(val) == target:
                payload = item.get("stagingData") or item.get("entityData") or item
                if isinstance(payload, str):
                    try:
                        import json as _json
                        payload = _json.loads(payload)
                    except (ValueError, TypeError):
                        payload = item
                return payload if isinstance(payload, dict) else item
    return None


# ─── Embedded snapshot helpers (ConflictDetailDto.firstEntity / secondEntity) ──
#
# Backend now embeds the full Person/PropertyUnit/Building DTOs directly in the
# `/conflicts/{id}/details` response, eliminating the need for secondary calls
# to /persons/{id}, /propertyunits/{id}, /buildings/{id}, or
# /import/packages/{id}/staged-entities. These helpers extract the inner DTO
# while preserving graceful fallback when snapshots are absent (older backend).

def _match_snapshot_to_id(details, entity_id):
    """Locate the snapshot wrapper that matches a given conflict entity id.

    Per backend contract:
      - `firstEntity` corresponds to `firstEntityId` (always the staging row)
      - `secondEntity` corresponds to `secondEntityId` (Production or Staging)

    Returns (snapshot_dict, source_str) or (None, None) when not found.
    `source_str` is the raw `source` field ("Staging"/"Production") or "" if
    the wrapper exists but has no source.
    """
    if not isinstance(details, dict) or not entity_id:
        return None, None
    target = str(entity_id)
    for snap_key, id_key in (
        ("firstEntity", "firstEntityId"),
        ("secondEntity", "secondEntityId"),
    ):
        if str(details.get(id_key, "")) != target:
            continue
        snap = details.get(snap_key)
        if isinstance(snap, dict):
            return snap, str(snap.get("source", ""))
    return None, None


def _extract_dto_from_snapshot(snapshot):
    """Extract the inner Person/PropertyUnit/Building DTO from a snapshot.

    The wrapper carries `entityType` selecting exactly one payload field.
    Returns None when:
      - the wrapper itself is missing/non-dict
      - the targeted payload field is null (entity deleted/missing per
        backend doc edge cases)

    The returned dict is a shallow copy so callers can mutate it (e.g. attach
    `_building`) without affecting the original details object.
    """
    if not isinstance(snapshot, dict):
        return None
    entity_type = snapshot.get("entityType")
    payload_key = {
        "Person": "person",
        "PropertyUnit": "propertyUnit",
        "Building": "building",
    }.get(entity_type)
    if not payload_key:
        return None
    payload = snapshot.get(payload_key)
    return dict(payload) if isinstance(payload, dict) else None

# ─── Styles ───────────────────────────────────────────────────────────
_RECORD_CARD_NORMAL = f"""
    QFrame#recordCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 #F7FAFF, stop:1 #F0F5FF);
        border: 1.5px solid #E2EAF2;
        border-radius: 12px;
    }}
"""

_RECORD_CARD_SELECTED = f"""
    QFrame#recordCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 #EBF5FF, stop:1 #E0EFFF);
        border: 2px solid {Colors.PRIMARY_BLUE};
        border-radius: 12px;
    }}
"""

_SECTION_CARD_STYLE = f"""
    QFrame#sectionCard {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 #F7FAFF, stop:1 #F0F5FF);
        border: 1px solid #E2EAF2;
        border-radius: 14px;
    }}
"""

_TABLE_HEADER_STYLE = f"""
    QFrame {{
        background: #0E2035;
        border: none;
    }}
"""

_TABLE_HEADER_LABEL = """
    QLabel {
        color: #FFFFFF;
        background: transparent;
        border: none;
        padding: 12px 16px;
    }
"""

_TABLE_ROW_FIELD = f"""
    QLabel {{
        color: {Colors.PAGE_TITLE};
        background: transparent;
        border: none;
        padding: 11px 16px;
        font-weight: 600;
    }}
"""

_TABLE_ROW_VALUE_A = f"""
    QLabel {{
        color: {Colors.WIZARD_TITLE};
        background: #F0F7FF;
        border: none;
        padding: 11px 16px;
    }}
"""

_TABLE_ROW_VALUE_B = f"""
    QLabel {{
        color: {Colors.WIZARD_TITLE};
        background: #FAFBFF;
        border: none;
        padding: 11px 16px;
    }}
"""

def _get_diff_indicator_style(bg_color="#EBF5FF"):
    border_side = "border-right" if get_layout_direction() == Qt.RightToLeft else "border-left"
    return f"""
        QLabel {{
            color: {Colors.PRIMARY_BLUE};
            background: {bg_color};
            {border_side}: 3px solid {Colors.PRIMARY_BLUE};
            padding: 11px 16px;
            font-weight: 700;
        }}
    """

_DOC_COLUMN_STYLE = """
    QFrame {
        background: #F8FAFC;
        border-radius: 12px;
        border: 1px solid #E5E7EB;
    }
"""


# ─── RecordCard ───────────────────────────────────────────────────────
class _RecordCard(QFrame):
    """Selectable record card for primary record selection."""

    card_clicked = pyqtSignal()

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("recordCard")
        self.setFixedHeight(ScreenScale.h(72))
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._selected = False
        self.setStyleSheet(_RECORD_CARD_NORMAL)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 18))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)

        # Radio indicator
        self._radio = QRadioButton()
        self._radio.setStyleSheet(RADIO_STYLE)
        self._radio.setFixedSize(ScreenScale.w(20), ScreenScale.h(20))
        layout.addWidget(self._radio)

        # Icon
        icon_name = data.get("icon", "blue")
        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #DBEAFE; border-radius: 8px; }"
        )
        pixmap = Icon.load_pixmap(icon_name, size=16)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        # Text block
        text_block = QWidget()
        text_block.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(text_block)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._label = QLabel(data.get("label", ""))
        self._label.setFont(create_font(size=11, weight=FontManager.WEIGHT_BOLD))
        self._label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        detail_parts = []
        identifier = data.get("identifier", "")
        if identifier:
            detail_parts.append(identifier)
        date_str = data.get("date", "")
        if date_str:
            detail_parts.append(date_str)
        subtitle = data.get("subtitle", "")
        if subtitle:
            detail_parts.append(subtitle)

        self._detail = QLabel("  \u00B7  ".join(detail_parts) if detail_parts else "")
        self._detail.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._detail.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        text_layout.addWidget(self._label)
        text_layout.addWidget(self._detail)

        layout.addWidget(text_block, 1)

    @property
    def radio(self) -> QRadioButton:
        return self._radio

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(_RECORD_CARD_SELECTED)
            shadow = self.graphicsEffect()
            if isinstance(shadow, QGraphicsDropShadowEffect):
                shadow.setColor(QColor(56, 144, 223, 40))
                shadow.setBlurRadius(20)
        else:
            self.setStyleSheet(_RECORD_CARD_NORMAL)
            shadow = self.graphicsEffect()
            if isinstance(shadow, QGraphicsDropShadowEffect):
                shadow.setColor(QColor(0, 0, 0, 18))
                shadow.setBlurRadius(16)

    def mousePressEvent(self, event):
        self._radio.setChecked(True)
        self.card_clicked.emit()
        super().mousePressEvent(event)


# ─── Main Page ────────────────────────────────────────────────────────
class ClaimComparisonPage(QWidget):
    """Claim comparison page — tabular comparison and merge resolution."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db)
        self.claim_radio_group = QButtonGroup(self)
        self._current_group = None
        self._comparison_data = []
        self._user_id = None
        self._current_conflict_type = ""
        self._record_cards = []
        self._is_resolved = False
        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def set_user_id(self, user_id: str):
        """Set current user ID for audit trail."""
        self._user_id = user_id

    # ────────────────────────────────────────────
    # UI Setup
    # ────────────────────────────────────────────
    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.comparison.title"))
        self._header.set_help(Pages.CLAIM_COMPARISON)

        # Action button in header
        self.action_btn = QPushButton(tr("page.comparison.execute"))
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self.action_btn.setFixedSize(ScreenScale.w(100), ButtonDimensions.SAVE_HEIGHT)
        self.action_btn.setStyleSheet(StyleManager.dark_action_button())
        self.action_btn.clicked.connect(self._on_action_clicked)
        self._header.add_action_widget(self.action_btn)

        # Back button in header
        self._back_btn = QPushButton(tr("action.back"))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self._back_btn.setFixedSize(ScreenScale.w(100), ButtonDimensions.SAVE_HEIGHT)
        self._back_btn.setStyleSheet(StyleManager.dark_action_button())
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._back_btn)

        outer_layout.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        outer_layout.addWidget(self._accent_line)

        # Resolved status banner (hidden by default)
        self._resolved_banner = QFrame()
        self._resolved_banner.setFixedHeight(ScreenScale.h(40))
        self._resolved_banner.setStyleSheet(
            "QFrame { background: #D1FAE5; border-bottom: 1px solid #A7F3D0; }"
        )
        banner_layout = QHBoxLayout(self._resolved_banner)
        banner_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 0,
            PageDimensions.content_padding_h(), 0,
        )
        banner_layout.setSpacing(8)

        resolved_icon = QLabel()
        resolved_icon.setFixedSize(ScreenScale.w(20), ScreenScale.h(20))
        resolved_icon.setAlignment(Qt.AlignCenter)
        resolved_icon.setStyleSheet(
            "QLabel { background: #10B981; border-radius: 10px; color: #FFFFFF;"
            " font-weight: 700; font-size: 12px; border: none; }"
        )
        resolved_icon.setText("\u2713")
        banner_layout.addWidget(resolved_icon)

        self._resolved_label = QLabel(tr("page.comparison.resolved_status"))
        self._resolved_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._resolved_label.setStyleSheet("color: #065F46; background: transparent; border: none;")
        banner_layout.addWidget(self._resolved_label)
        banner_layout.addStretch()

        self._resolved_banner.setVisible(False)
        outer_layout.addWidget(self._resolved_banner)

        # Light content wrapper
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(StyleManager.page_background())
        content_inner = QVBoxLayout(content_wrapper)
        content_inner.setContentsMargins(0, 0, 0, 0)
        content_inner.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
            + StyleManager.scrollbar()
        )
        self._scroll_area = scroll

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        self._content_layout.setSpacing(16)

        # Section 1: Record Selection
        self._records_title = self._build_section_title(
            "blue",
            tr("page.comparison.records_section"),
            tr("page.comparison.records_section_subtitle"),
        )
        self._content_layout.addWidget(self._records_title)

        self._records_card = QFrame()
        self._records_card.setObjectName("sectionCard")
        self._records_card.setStyleSheet(_SECTION_CARD_STYLE)
        records_card_layout = QVBoxLayout(self._records_card)
        records_card_layout.setContentsMargins(16, 16, 16, 16)
        records_card_layout.setSpacing(10)
        self._records_layout = QVBoxLayout()
        self._records_layout.setSpacing(10)
        records_card_layout.addLayout(self._records_layout)
        self._content_layout.addWidget(self._records_card)

        # Section 2: Comparison Table
        self._comparison_title = self._build_section_title(
            "move",
            tr("page.comparison.comparison"),
            tr("page.comparison.comparison_section_subtitle"),
        )
        self._content_layout.addWidget(self._comparison_title)

        self._comparison_card = QFrame()
        self._comparison_card.setObjectName("sectionCard")
        self._comparison_card.setStyleSheet(_SECTION_CARD_STYLE)
        comp_card_layout = QVBoxLayout(self._comparison_card)
        comp_card_layout.setContentsMargins(0, 0, 0, 0)
        comp_card_layout.setSpacing(0)
        self._table_container = QWidget()
        self._table_container.setStyleSheet("background: transparent;")
        self._table_grid = QGridLayout(self._table_container)
        self._table_grid.setContentsMargins(0, 0, 0, 0)
        self._table_grid.setSpacing(0)
        self._table_grid.setColumnStretch(0, 30)
        self._table_grid.setColumnStretch(1, 0)
        self._table_grid.setColumnStretch(2, 35)
        self._table_grid.setColumnStretch(3, 0)
        self._table_grid.setColumnStretch(4, 35)
        comp_card_layout.addWidget(self._table_container)
        self._content_layout.addWidget(self._comparison_card)

        # Section 3: Document Comparison
        doc_title_row = QHBoxLayout()
        doc_title_row.setSpacing(12)
        self._doc_title = self._build_section_title(
            "dec",
            tr("page.comparison.document_comparison"),
            tr("page.comparison.doc_section_subtitle"),
        )
        doc_title_row.addWidget(self._doc_title, 1)

        self._doc_load_btn = QPushButton(tr("page.comparison.load_comparison"))
        self._doc_load_btn.setCursor(Qt.PointingHandCursor)
        self._doc_load_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._doc_load_btn.setFixedHeight(ScreenScale.h(32))
        self._doc_load_btn.setStyleSheet(f"""
            QPushButton {{
                color: #FFFFFF;
                background: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 8px;
                padding: 6px 20px;
            }}
            QPushButton:hover {{
                background: #2D7BC9;
            }}
            QPushButton:disabled {{
                background: #A0C4E8;
                color: #D0E4F5;
            }}
        """)
        self._doc_load_btn.clicked.connect(self._load_document_comparison)
        doc_title_row.addWidget(self._doc_load_btn, 0, Qt.AlignBottom)

        doc_title_widget = QWidget()
        doc_title_widget.setStyleSheet("background: transparent;")
        doc_title_widget.setLayout(doc_title_row)
        self._content_layout.addWidget(doc_title_widget)

        self._doc_card = QFrame()
        self._doc_card.setObjectName("sectionCard")
        self._doc_card.setStyleSheet(_SECTION_CARD_STYLE)
        doc_card_layout = QVBoxLayout(self._doc_card)
        doc_card_layout.setContentsMargins(16, 16, 16, 16)
        doc_card_layout.setSpacing(12)

        # Doc columns container
        self._doc_columns_layout = QHBoxLayout()
        self._doc_columns_layout.setSpacing(0)

        self._doc_first_frame = self._build_doc_column(tr("page.comparison.first_record_docs"))
        self._doc_columns_layout.addWidget(self._doc_first_frame, 1)

        # Thin vertical separator
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet("QFrame { background: #E2EAF2; }")
        self._doc_columns_layout.addWidget(separator)

        self._doc_second_frame = self._build_doc_column(tr("page.comparison.second_record_docs"))
        self._doc_columns_layout.addWidget(self._doc_second_frame, 1)

        doc_card_layout.addLayout(self._doc_columns_layout)

        # Doc empty state
        self._doc_empty_label = QLabel(tr("page.comparison.click_load_comparison"))
        self._doc_empty_label.setAlignment(Qt.AlignCenter)
        self._doc_empty_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._doc_empty_label.setStyleSheet("color: #9CA3AF; background: transparent; padding: 30px;")
        doc_card_layout.addWidget(self._doc_empty_label)

        self._doc_first_frame.setVisible(False)
        self._doc_second_frame.setVisible(False)

        self._content_layout.addWidget(self._doc_card)

        # Section 4: Resolution
        self._resolution_title = self._build_section_title(
            "yelow",
            tr("page.comparison.resolution_action"),
            tr("page.comparison.resolution_subtitle"),
        )
        self._content_layout.addWidget(self._resolution_title)

        self._resolution_card = QFrame()
        self._resolution_card.setObjectName("sectionCard")
        self._resolution_card.setStyleSheet(_SECTION_CARD_STYLE)
        res_layout = QVBoxLayout(self._resolution_card)
        res_layout.setContentsMargins(20, 20, 20, 20)
        res_layout.setSpacing(14)

        self._resolution_group = QButtonGroup(self)
        resolution_options = [
            (tr("page.comparison.merge_records"), "merge"),
            (tr("page.comparison.keep_separate"), "keep_separate"),
        ]

        options_layout = QHBoxLayout()
        options_layout.setSpacing(24)
        for idx, (label, value) in enumerate(resolution_options):
            radio = QRadioButton(label)
            radio.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            radio.setStyleSheet(RADIO_STYLE + " QRadioButton { padding: 6px 12px; }")
            radio.setProperty("resolution_type", value)
            self._resolution_group.addButton(radio, idx)
            options_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)
        options_layout.addStretch()
        res_layout.addLayout(options_layout)

        # Justification — required input. Larger label with red asterisk so
        # the user immediately sees this is mandatory. The placeholder is
        # multiline with a concrete example. A hint below clarifies that
        # the text is persisted in the audit trail and cannot be edited.
        self._justification_label = QLabel()
        self._justification_label.setText(
            f"{tr('page.comparison.justification_required')} "
            f"<span style='color:#DC2626;'>*</span>"
        )
        self._justification_label.setTextFormat(Qt.RichText)
        self._justification_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_BOLD))
        self._justification_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        res_layout.addWidget(self._justification_label)

        self._justification_edit = QTextEdit()
        self._justification_edit.setPlaceholderText(tr("page.comparison.enter_justification"))
        self._justification_edit.setFixedHeight(ScreenScale.h(110))
        self._justification_edit.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._justification_edit.setStyleSheet(
            "QTextEdit {"
            " background: #FFFFFF;"
            " border: 1.5px solid #CBD5E1;"
            " border-radius: 8px;"
            " padding: 10px 12px;"
            " color: #1F2937;"
            " selection-background-color: #93C5FD;"
            " }"
            " QTextEdit:focus { border-color: #3890DF; }"
        )
        res_layout.addWidget(self._justification_edit)

        self._justification_hint = QLabel(tr("page.comparison.justification_audit_hint"))
        self._justification_hint.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._justification_hint.setStyleSheet(
            "color: #6B7280; background: transparent; border: none; padding-top: 4px;"
        )
        self._justification_hint.setWordWrap(True)
        res_layout.addWidget(self._justification_hint)

        self._content_layout.addWidget(self._resolution_card)

        self._content_layout.addStretch()
        scroll.setWidget(content)
        content_inner.addWidget(scroll)
        outer_layout.addWidget(content_wrapper, 1)

    # ────────────────────────────────────────────
    # Section Title Builder
    # ────────────────────────────────────────────
    def _build_section_title(self, icon_name: str, title: str, subtitle: str) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #DBEAFE; border-radius: 7px; }"
        )
        pixmap = Icon.load_pixmap(icon_name, size=14)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)

        text_container = QWidget()
        text_container.setStyleSheet("background: transparent; border: none;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        text_layout.addWidget(title_label)
        text_layout.addWidget(subtitle_label)

        layout.addWidget(icon_label)
        layout.addWidget(text_container)
        layout.addStretch()

        # Store references for update_language
        container._title_label = title_label
        container._subtitle_label = subtitle_label

        return container

    # ────────────────────────────────────────────
    # Document Column Builder
    # ────────────────────────────────────────────
    def _build_doc_column(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_DOC_COLUMN_STYLE)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        layout.addWidget(title_lbl)
        frame._title_label = title_lbl

        count_lbl = QLabel(f"0 {tr('page.comparison.documents')}")
        count_lbl.setObjectName("doc_count")
        count_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        count_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        layout.addWidget(count_lbl)

        docs_container = QVBoxLayout()
        docs_container.setSpacing(6)
        docs_container.setObjectName("docs_list")
        layout.addLayout(docs_container)

        layout.addStretch()
        return frame

    # ────────────────────────────────────────────
    # Comparison Table Population
    # ────────────────────────────────────────────
    def _populate_comparison_table(self, comparison_dicts: list, diff_fields: set):
        """Fill the comparison table grid with field rows."""
        self._clear_grid(self._table_grid)

        if len(comparison_dicts) < 2:
            return

        # Dark header row
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame { background: #0E2035; border-top-left-radius: 14px;"
            " border-top-right-radius: 14px; }"
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        headers = [
            (tr("page.comparison.field_name"), 30),
            (tr("page.comparison.record_a"), 35),
            (tr("page.comparison.record_b"), 35),
        ]
        for col, (text, stretch) in enumerate(headers):
            lbl = QLabel(text)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_BOLD))
            lbl.setStyleSheet(_TABLE_HEADER_LABEL)
            header_layout.addWidget(lbl, stretch)
            if col < 2:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setStyleSheet("QFrame { background: rgba(255,255,255,0.15); }")
                header_layout.addWidget(sep)

        self._table_grid.addWidget(header_frame, 0, 0, 1, 5)

        # Unavailable placeholder row — shown when a record's details couldn't be loaded
        notice_offset = 0
        if any(d.get("_unavailable") for d in comparison_dicts):
            notice = QLabel()
            a_unavail = comparison_dicts[0].get("_unavailable")
            b_unavail = comparison_dicts[1].get("_unavailable")
            if a_unavail and b_unavail:
                notice.setText(tr("page.comparison.record_unavailable"))
            elif a_unavail:
                notice.setText(f"{tr('page.comparison.record_a')}: {tr('page.comparison.record_unavailable')}")
            else:
                notice.setText(f"{tr('page.comparison.record_b')}: {tr('page.comparison.record_unavailable')}")
            notice.setAlignment(Qt.AlignCenter)
            notice.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            notice.setStyleSheet(
                "QLabel { background: #FFF7ED; color: #B45309;"
                " border: 1px solid #FCD34D; border-radius: 8px;"
                " padding: 10px 16px; margin: 6px 0; }"
            )
            self._table_grid.addWidget(notice, 1, 0, 1, 5)
            notice_offset = 1

        # Determine fields based on robust category (preferred) or legacy conflictType
        category = getattr(self, "_current_category", "")
        if category == PERSON or self._current_conflict_type == "PersonDuplicate":
            fields = [
                ("full_name_ar", tr("page.comparison.full_name")),
                ("mother_name", tr("page.comparison.mother_name")),
                ("national_id", tr("page.comparison.national_id")),
                ("date_of_birth", tr("page.comparison.date_of_birth")),
                ("gender", tr("page.comparison.gender")),
                ("nationality", tr("page.comparison.nationality")),
                ("phone_number", tr("page.comparison.phone_number")),
            ]
        else:
            fields = [
                ("building_code", tr("page.comparison.building_data")),
                ("address", tr("page.comparison.building_location")),
                ("residential_units", tr("page.comparison.residential_units")),
                ("commercial_units", tr("page.comparison.commercial_units")),
                ("total_units", tr("page.comparison.total_units")),
                ("building_type", tr("page.comparison.building_type")),
                ("building_status", tr("page.comparison.building_status")),
                ("general_description", tr("page.comparison.building_description")),
                ("unit_status", tr("page.comparison.unit_status")),
                ("unit_type", tr("page.comparison.unit_type")),
                ("area_sqm", tr("page.comparison.unit_area")),
                ("rooms", tr("page.comparison.num_rooms")),
                ("floor", tr("page.comparison.floor_number")),
                ("unit_number", tr("page.comparison.unit_number")),
            ]

        row_offset = 1 + notice_offset
        for idx, (field_key, label_text) in enumerate(fields):
            row = row_offset + idx
            is_diff = field_key in diff_fields
            is_alt = idx % 2 == 0
            alt_bg = "#F8FBFF" if is_alt else "transparent"

            # Field label column — keep default Qt alignment (no override)
            # so the original look is preserved.
            field_lbl = QLabel(label_text)
            field_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            field_lbl.setStyleSheet(_TABLE_ROW_FIELD.replace("transparent", alt_bg))
            self._table_grid.addWidget(field_lbl, row, 0)

            # Thin separator between field and record A
            sep1 = QFrame()
            sep1.setFixedWidth(1)
            sep1.setStyleSheet(f"QFrame {{ background: #E2EAF2; }}")
            self._table_grid.addWidget(sep1, row, 1)

            # Record A value — alignment kept at Qt default for Arabic
            # text values (matches the previous look). For known Latin-
            # only fields (NID, date, phone) we explicitly:
            #   • set layout direction to LTR so digits/dashes/`+` don't
            #     get bidi-reordered, and
            #   • align them to the trailing edge of the cell so they
            #     visually match the rest of the column in Arabic UI.
            val_a = str(comparison_dicts[0].get(field_key, "-"))
            lbl_a = QLabel(val_a)
            lbl_a.setWordWrap(True)
            if field_key in _LTR_FIELD_KEYS:
                lbl_a.setLayoutDirection(Qt.LeftToRight)
                lbl_a.setAlignment(get_text_alignment() | Qt.AlignVCenter)
            if is_diff:
                lbl_a.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
                lbl_a.setStyleSheet(_get_diff_indicator_style("#E8F2FF"))
            else:
                lbl_a.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                lbl_a.setStyleSheet(_TABLE_ROW_VALUE_A.replace("#F0F7FF", "#EDF4FF" if is_alt else "#F0F7FF"))
            self._table_grid.addWidget(lbl_a, row, 2)

            # Thin separator between record A and B
            sep2 = QFrame()
            sep2.setFixedWidth(1)
            sep2.setStyleSheet(f"QFrame {{ background: #E2EAF2; }}")
            self._table_grid.addWidget(sep2, row, 3)

            # Record B value — same LTR + trailing-edge alignment for Latin.
            val_b = str(comparison_dicts[1].get(field_key, "-"))
            lbl_b = QLabel(val_b)
            lbl_b.setWordWrap(True)
            if field_key in _LTR_FIELD_KEYS:
                lbl_b.setLayoutDirection(Qt.LeftToRight)
                lbl_b.setAlignment(get_text_alignment() | Qt.AlignVCenter)
            if is_diff:
                lbl_b.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
                lbl_b.setStyleSheet(_get_diff_indicator_style("#FFF8EB"))
            else:
                lbl_b.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                lbl_b.setStyleSheet(_TABLE_ROW_VALUE_B.replace("#FAFBFF", "#F5F7FF" if is_alt else "#FAFBFF"))
            self._table_grid.addWidget(lbl_b, row, 4)

        # Bottom border row
        bottom_frame = QFrame()
        bottom_frame.setFixedHeight(2)
        bottom_frame.setStyleSheet("QFrame { background: #E2EAF2; }")
        self._table_grid.addWidget(bottom_frame, row_offset + len(fields), 0, 1, 5)

    def _clear_grid(self, grid: QGridLayout):
        """Remove all widgets from a grid layout."""
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ────────────────────────────────────────────
    # Record Selection UI Update
    # ────────────────────────────────────────────
    def _update_record_selection(self):
        """Update record card visual states based on radio selection."""
        checked_id = self.claim_radio_group.checkedId()
        for idx, card in enumerate(self._record_cards):
            card.set_selected(idx == checked_id)

    # ────────────────────────────────────────────
    # Evidence Card Builder
    # ────────────────────────────────────────────
    def _build_evidence_card(self, evidence: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 10px;
                border: 1px solid #E5E7EB;
            }
            QFrame:hover {
                border-color: #93C5FD;
                background: #F0F9FF;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # File name row
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        file_name = evidence.get("originalFileName", "")
        mime = evidence.get("mimeType", "")
        icon_text = self._get_file_icon(mime)

        icon_lbl = QLabel(icon_text)
        icon_lbl.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_lbl.setFixedWidth(ScreenScale.w(20))
        name_row.addWidget(icon_lbl)

        name_lbl = QLabel(file_name or "-")
        name_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        name_lbl.setWordWrap(True)
        name_row.addWidget(name_lbl, 1)

        # Version badge
        version = evidence.get("versionNumber", 1)
        ver_lbl = QLabel(f"v{version}")
        ver_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_BOLD))
        ver_lbl.setFixedWidth(ScreenScale.w(28))
        ver_lbl.setAlignment(Qt.AlignCenter)
        is_current = evidence.get("isCurrentVersion", True)
        ver_color = "#10B981" if is_current else "#9CA3AF"
        ver_lbl.setStyleSheet(
            f"color: {ver_color}; background: {ver_color}15; "
            f"border-radius: 4px; padding: 2px; border: none;"
        )
        name_row.addWidget(ver_lbl)

        layout.addLayout(name_row)

        # Details row
        details_parts = []
        desc = evidence.get("description", "")
        if desc:
            details_parts.append(desc)
        authority = evidence.get("issuingAuthority", "")
        if authority:
            details_parts.append(authority)
        ref = evidence.get("documentReferenceNumber", "")
        if ref:
            details_parts.append(f"#{ref}")

        if details_parts:
            details_lbl = QLabel(" | ".join(details_parts))
            details_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            details_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            details_lbl.setWordWrap(True)
            layout.addWidget(details_lbl)

        # Date + size row
        meta_parts = []
        issued = evidence.get("documentIssuedDate", "")
        if issued and "T" in str(issued):
            meta_parts.append(str(issued).split("T")[0])
        size_bytes = evidence.get("fileSizeBytes", 0)
        if size_bytes:
            if size_bytes > 1048576:
                meta_parts.append(f"{size_bytes / 1048576:.1f} MB")
            elif size_bytes > 1024:
                meta_parts.append(f"{size_bytes / 1024:.0f} KB")
            else:
                meta_parts.append(f"{size_bytes} B")

        is_expired = evidence.get("isExpired", False)
        if is_expired:
            meta_parts.append(tr("page.comparison.expired"))

        if meta_parts:
            meta_lbl = QLabel(" | ".join(meta_parts))
            meta_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
            expired_color = "#EF4444" if is_expired else "#9CA3AF"
            meta_lbl.setStyleSheet(f"color: {expired_color}; background: transparent; border: none;")
            layout.addWidget(meta_lbl)

        return card

    @staticmethod
    def _get_file_icon(mime_type: str) -> str:
        if not mime_type:
            return "F"
        if "pdf" in mime_type:
            return "PDF"
        if "image" in mime_type:
            return "IMG"
        if "word" in mime_type or "document" in mime_type:
            return "DOC"
        if "excel" in mime_type or "spreadsheet" in mime_type:
            return "XLS"
        return "F"

    def _populate_doc_column(self, frame: QFrame, evidences: list):
        layout = frame.layout()
        docs_layout = None
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.layout() and item.layout().objectName() == "docs_list":
                docs_layout = item.layout()
                break

        if not docs_layout:
            return

        while docs_layout.count():
            child = docs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        count_lbl = frame.findChild(QLabel, "doc_count")
        if count_lbl:
            count_lbl.setText(
                f"{len(evidences)} {tr('page.comparison.document_singular')}"
                if len(evidences) != 0
                else tr("page.comparison.no_documents")
            )

        for ev in evidences:
            ev_card = self._build_evidence_card(ev)
            docs_layout.addWidget(ev_card)

    # ────────────────────────────────────────────
    # Document Comparison Fetch
    # ────────────────────────────────────────────
    def _load_document_comparison(self):
        if not self._current_group:
            return

        conflict_id = self._current_group.get("id", "")
        if not conflict_id:
            Toast.show_toast(self, tr("page.comparison.conflict_id_unavailable"), Toast.WARNING)
            return

        self._doc_load_btn.setEnabled(False)

        entity_ids = [
            self._current_group.get("firstEntityId", ""),
            self._current_group.get("secondEntityId", ""),
        ]
        is_person = getattr(self, "_current_category", "") == PERSON

        self._doc_comparison_worker = ApiWorker(
            self._fetch_document_comparison, conflict_id, entity_ids, is_person
        )
        self._doc_comparison_worker.finished.connect(self._on_doc_comparison_loaded)
        self._doc_comparison_worker.error.connect(self._on_doc_comparison_error)
        self._spinner.show_loading(tr("component.loading.default"))
        self._doc_comparison_worker.start()

    def _fetch_document_comparison(self, conflict_id, entity_ids, is_person):
        """Fetch document comparison data (runs in worker thread)."""
        first_evidences = []
        second_evidences = []

        try:
            doc_data = self.duplicate_service.get_document_comparison(conflict_id)
            logger.info(f"Document comparison response: {str(doc_data)[:500]}")

            if isinstance(doc_data, dict):
                first_entity = doc_data.get("firstEntity") or doc_data.get("firstRecord") or {}
                second_entity = doc_data.get("secondEntity") or doc_data.get("secondRecord") or {}

                first_evidences = (
                    first_entity.get("evidences", [])
                    or first_entity.get("documents", [])
                    or first_entity.get("attachments", [])
                )
                second_evidences = (
                    second_entity.get("evidences", [])
                    or second_entity.get("documents", [])
                    or second_entity.get("attachments", [])
                )

                if not first_evidences and not second_evidences:
                    entities_list = doc_data.get("entities", doc_data.get("records", []))
                    if isinstance(entities_list, list) and len(entities_list) >= 2:
                        first_evidences = entities_list[0].get("evidences", entities_list[0].get("documents", []))
                        second_evidences = entities_list[1].get("evidences", entities_list[1].get("documents", []))

                if not first_evidences and not second_evidences:
                    root_docs = doc_data.get("evidences", doc_data.get("documents", []))
                    if isinstance(root_docs, list) and len(root_docs) >= 2:
                        mid = len(root_docs) // 2
                        first_evidences = root_docs[:mid]
                        second_evidences = root_docs[mid:]

            elif isinstance(doc_data, list):
                if len(doc_data) >= 2 and isinstance(doc_data[0], dict):
                    if "evidences" in doc_data[0] or "documents" in doc_data[0]:
                        first_evidences = doc_data[0].get("evidences", doc_data[0].get("documents", []))
                        second_evidences = doc_data[1].get("evidences", doc_data[1].get("documents", []))
                    else:
                        mid = len(doc_data) // 2
                        first_evidences = doc_data[:mid]
                        second_evidences = doc_data[mid:]

        except Exception as e:
            logger.warning(f"Document comparison endpoint failed: {e}")

        if not first_evidences and not second_evidences:
            if not is_person:
                try:
                    from services.api_client import get_api_client
                    api = get_api_client()
                    if api:
                        for idx, eid in enumerate(entity_ids):
                            if not eid:
                                continue
                            try:
                                unit_dto = api.get_property_unit_by_id(eid)
                                building_id = ""
                                if unit_dto:
                                    building_id = unit_dto.get("buildingId", unit_dto.get("building_id", ""))
                                if building_id:
                                    docs = api.get_building_documents(building_id)
                                    if docs:
                                        if idx == 0:
                                            first_evidences = docs
                                        else:
                                            second_evidences = docs
                                        logger.info(f"Fetched {len(docs)} building docs for entity {idx}")
                            except Exception as be:
                                logger.warning(f"Failed to fetch building docs for {eid}: {be}")
                except Exception as e:
                    logger.warning(f"Building documents fallback failed: {e}")

        return {"first": first_evidences, "second": second_evidences}

    def _on_doc_comparison_loaded(self, result):
        """Handle document comparison result on main thread."""
        self._spinner.hide_loading()
        self._doc_load_btn.setEnabled(True)
        first_evidences = result.get("first", [])
        second_evidences = result.get("second", [])

        if not first_evidences and not second_evidences:
            Toast.show_toast(self, tr("page.comparison.no_linked_documents"), Toast.WARNING)
            return

        self._doc_empty_label.setVisible(False)
        self._doc_first_frame.setVisible(True)
        self._doc_second_frame.setVisible(True)

        self._populate_doc_column(self._doc_first_frame, first_evidences)
        self._populate_doc_column(self._doc_second_frame, second_evidences)

    def _on_doc_comparison_error(self, error_msg):
        """Handle document comparison error."""
        self._spinner.hide_loading()
        self._doc_load_btn.setEnabled(True)
        logger.warning(f"Document comparison failed: {error_msg}")
        Toast.show_toast(self, tr("page.comparison.failed_loading_documents"), Toast.ERROR)

    # ────────────────────────────────────────────
    # Layout helpers
    # ────────────────────────────────────────────
    def _clear_layout(self, layout):
        """Remove all items from a layout recursively."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ────────────────────────────────────────────
    # Data Mapping (preserved as-is)
    # ────────────────────────────────────────────
    def _map_to_comparison_dict(self, building: dict, unit: dict) -> dict:
        """Map API records to the format expected by comparison table."""
        from services.display_mappings import (
            get_building_type_display, get_building_status_display,
            get_unit_type_display, get_unit_status_display,
        )

        address_parts = filter(None, [
            building.get("governorateName", building.get("governorate_name_ar", "")),
            building.get("districtName", building.get("district_name_ar", "")),
            building.get("subDistrictName", building.get("subdistrict_name_ar", "")),
            building.get("address", ""),
        ])

        raw_btype = building.get("buildingType", building.get("building_type", ""))
        raw_bstatus = building.get("buildingStatus", building.get("building_status",
                       building.get("status", "")))
        building_type_label = get_building_type_display(raw_btype) if raw_btype else "-"
        building_status_label = get_building_status_display(raw_bstatus) if raw_bstatus else "-"

        def _get_unit(key1, key2="", key3=""):
            val = unit.get(key1, "")
            if not val and key2:
                val = unit.get(key2, "")
            if not val and key3:
                val = unit.get(key3, "")
            if not val:
                val = building.get(key1, "")
            if not val and key2:
                val = building.get(key2, "")
            if not val and key3:
                val = building.get(key3, "")
            return val

        raw_ustatus = _get_unit("unitStatus", "status", "apartment_status")
        raw_utype = _get_unit("unitType", "unit_type")
        unit_status_label = get_unit_status_display(raw_ustatus) if raw_ustatus else "-"
        unit_type_label = get_unit_type_display(raw_utype) if raw_utype else "-"

        raw_area = _get_unit("areaSquareMeters", "area_sqm", "areaSqm")
        raw_rooms = _get_unit("numberOfRooms", "number_of_rooms", "roomCount")
        raw_floor = _get_unit("floorNumber", "floor_number")
        raw_unit_num = _get_unit("unitIdentifier", "unit_number", "unitNumber")

        return {
            "building_code": building.get("buildingId", building.get("building_id",
                             building.get("buildingCode", "-"))),
            "address": " - ".join(address_parts) or "-",
            "residential_units": str(building.get("residentialUnitsCount",
                                    building.get("numberOfApartments",
                                    building.get("number_of_apartments", "-")))),
            "commercial_units": str(building.get("commercialUnitsCount",
                                   building.get("numberOfShops",
                                   building.get("number_of_shops", "-")))),
            "total_units": str(building.get("totalUnitsCount",
                              building.get("numberOfPropertyUnits",
                              building.get("number_of_units", "-")))),
            "building_type": building_type_label,
            "building_status": building_status_label,
            "general_description": building.get("description",
                                   building.get("notes",
                                   building.get("general_description", "-"))),
            "lat": building.get("latitude", 0),
            "lng": building.get("longitude", 0),
            "unit_status": unit_status_label,
            "unit_type": unit_type_label,
            "area_sqm": str(raw_area) if raw_area else "-",
            "rooms": str(raw_rooms) if raw_rooms else "-",
            "floor": str(raw_floor) if raw_floor else "-",
            "unit_number": str(raw_unit_num) if raw_unit_num else "-",
        }

    def _compute_comparison_diff_fields(self, comparison_dicts: list) -> set:
        """Find which fields differ across comparison records."""
        if len(comparison_dicts) < 2:
            return set()
        diff_fields = set()
        all_keys = ["building_code", "address", "residential_units", "commercial_units",
                     "total_units", "building_type", "building_status", "general_description",
                     "unit_status", "unit_type", "area_sqm", "rooms", "floor", "unit_number"]
        for key in all_keys:
            values = {str(d.get(key, "")) for d in comparison_dicts}
            if len(values) > 1:
                diff_fields.add(key)
        return diff_fields

    # Map of backend field names (in DataComparison.fields[].field) to our
    # internal canonical comparison-field keys.
    _DC_FIELD_ALIASES = {
        "fullname": "full_name_ar",
        "fullnamearabic": "full_name_ar",
        "name": "full_name_ar",
        "mothername": "mother_name",
        "mothernamearabic": "mother_name",
        "nationalid": "national_id",
        "national_id": "national_id",
        "nid": "national_id",
        "dateofbirth": "date_of_birth",
        "date_of_birth": "date_of_birth",
        "dob": "date_of_birth",
        "gender": "gender",
        "nationality": "nationality",
        "phone": "phone_number",
        "phonenumber": "phone_number",
        "mobilenumber": "phone_number",
    }

    @classmethod
    def _parse_data_comparison(cls, raw):
        """Normalise backend `dataComparison` into [record_a_dict, record_b_dict].

        Handles three observed shapes:
          1. {"fields": [{"field": ..., "first": ..., "second": ...,
                          "match": bool}, ...]}    (canonical backend)
          2. [{...record_a...}, {...record_b...}]   (already flattened)
          3. [[{fieldName, value}, ...], [...]]     (legacy list-of-lists)

        Returns a 2-element list — index 0 is record A, index 1 is record B.
        Empty dicts when the input is missing/unparseable.
        """
        import json as _json

        if not raw:
            return [{}, {}]

        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
            except (ValueError, TypeError):
                return [{}, {}]

        # Shape 1: dict with "fields" array.
        if isinstance(raw, dict):
            fields = raw.get("fields")
            if isinstance(fields, list):
                rec_a, rec_b = {}, {}
                for entry in fields:
                    if not isinstance(entry, dict):
                        continue
                    field_name = str(
                        entry.get("field") or entry.get("fieldName") or ""
                    ).strip()
                    if not field_name:
                        continue
                    canonical = cls._DC_FIELD_ALIASES.get(
                        field_name.lower().replace("_", ""), field_name
                    )
                    first = entry.get("first", entry.get("firstValue", ""))
                    second = entry.get("second", entry.get("secondValue", ""))
                    if first not in ("", None):
                        # Store under BOTH canonical (snake_case) and the
                        # original field name so legacy lookups (cards,
                        # NID extraction) that read camelCase keep working.
                        rec_a[canonical] = str(first)
                        if field_name != canonical:
                            rec_a[field_name] = str(first)
                    if second not in ("", None):
                        rec_b[canonical] = str(second)
                        if field_name != canonical:
                            rec_b[field_name] = str(second)
                return [rec_a, rec_b]
            # Single-record dict — treat as record A only.
            return [raw, {}]

        # Shape 2 / 3: list.
        if isinstance(raw, list):
            out = []
            for item in raw[:2]:
                if isinstance(item, dict):
                    out.append(item)
                elif isinstance(item, list):
                    flat = {}
                    for fi in item:
                        if isinstance(fi, dict):
                            key = (
                                fi.get("field")
                                or fi.get("fieldName")
                                or ""
                            )
                            val = fi.get("value", fi.get("first", ""))
                            if key:
                                canonical = cls._DC_FIELD_ALIASES.get(
                                    str(key).lower().replace("_", ""), key
                                )
                                flat[canonical] = str(val)
                    out.append(flat)
                else:
                    out.append({})
            while len(out) < 2:
                out.append({})
            return out

        return [{}, {}]

    @staticmethod
    def _is_meaningful_person(person_dto: dict) -> bool:
        """Return True if the person dict has at least one identifying field.

        Some endpoints return a thin `{"id": "..."}` for missing/staged
        records. Treating that as a real hit overwrites the identifier
        skeleton with empty data, so we filter it out here.
        """
        if not isinstance(person_dto, dict):
            return False
        for key in (
            "fullNameArabic", "firstNameArabic", "fatherNameArabic",
            "familyNameArabic", "fullName", "nationalId", "mobileNumber",
            "phoneNumber", "dateOfBirth", "motherNameArabic",
        ):
            v = person_dto.get(key)
            if v not in (None, ""):
                return True
        return False

    @staticmethod
    def _build_identifier_fallback(conflict_data: dict, idx: int,
                                   data_comparison: list) -> dict:
        """Last-resort fallback when neither production nor dataComparison
        have data for one record.

        The conflict object always carries `firstEntityIdentifier` /
        `secondEntityIdentifier` (the human-readable label, usually the name).
        For person duplicates, the NID is shared by definition with the OTHER
        record — pull it from data_comparison's other side if present.
        Returns a dict with at least a name and (when possible) NID.
        """
        if not isinstance(conflict_data, dict):
            return {}
        identifier = conflict_data.get(
            "firstEntityIdentifier" if idx == 0 else "secondEntityIdentifier",
            "",
        )
        # Backend may send an empty/None identifier when one side is staged-only.
        # Fall back to the parsed dataComparison full-name for this index so the
        # skeleton still has SOMETHING to display.
        if not identifier and 0 <= idx < len(data_comparison):
            dc_row = data_comparison[idx] or {}
            if isinstance(dc_row, dict):
                identifier = (
                    dc_row.get("full_name_ar")
                    or dc_row.get("fullNameArabic")
                    or ""
                )
        if not identifier:
            return {}
        result = {"fullNameArabic": str(identifier)}
        # Try to inherit NID from the sibling record's parsed data.
        sibling_idx = 1 - idx
        if 0 <= sibling_idx < len(data_comparison):
            sibling = data_comparison[sibling_idx] or {}
            if isinstance(sibling, dict):
                nid = (
                    sibling.get("national_id")
                    or sibling.get("nationalId")
                    or sibling.get("nationalID")
                )
                if nid:
                    result["nationalId"] = str(nid)
        return result

    def _map_person_to_comparison_dict(self, record: dict) -> dict:
        from services.vocab_service import get_label

        logger.warning(
            f"[CMP-MAP] input keys={list(record.keys()) if isinstance(record, dict) else None}, "
            f"full_name_ar(canonical)={record.get('full_name_ar')!r}, "
            f"fullNameArabic={record.get('fullNameArabic')!r}, "
            f"nationalId={record.get('nationalId')!r}, "
            f"national_id={record.get('national_id')!r}"
        )

        # Accept either a production person DTO (fullNameArabic, mobileNumber,
        # …) or a pre-canonical dict already produced by `_parse_data_comparison`
        # (full_name_ar, phone_number, …) — whichever has data wins.
        canonical_full_name = record.get("full_name_ar")
        full_name_ar = canonical_full_name or record.get("fullNameArabic") or ""
        if not full_name_ar:
            parts = filter(None, [
                record.get("firstNameArabic", ""),
                record.get("fatherNameArabic", ""),
                record.get("familyNameArabic", ""),
            ])
            full_name_ar = " ".join(parts) or "-"

        dob = (
            record.get("date_of_birth")
            or record.get("dateOfBirth")
            or ""
        )
        if dob and "T" in str(dob):
            dob = str(dob).split("T")[0]

        gender_raw = record.get("gender")
        gender_label = (
            get_label("Gender", gender_raw, lang="ar")
            if gender_raw and not isinstance(gender_raw, str)
            else (gender_raw if gender_raw else "-")
        )
        # If gender_raw came as a string label already (e.g. "Male"), pass
        # through; if it's a vocab code, get_label resolves it.
        if isinstance(gender_raw, str) and gender_raw in ("Male", "Female", "ذكر", "أنثى"):
            gender_label = gender_raw if gender_raw in ("ذكر", "أنثى") else (
                "ذكر" if gender_raw == "Male" else "أنثى"
            )
        elif isinstance(gender_raw, (int, str)) and gender_raw not in ("", None):
            try:
                gender_label = get_label("Gender", gender_raw, lang="ar") or str(gender_raw)
            except Exception:
                gender_label = str(gender_raw)
        else:
            gender_label = "-"

        nationality_raw = record.get("nationality")
        if isinstance(nationality_raw, str) and nationality_raw and not nationality_raw.isdigit():
            nationality_label = nationality_raw
        elif nationality_raw not in ("", None):
            try:
                nationality_label = get_label("Nationality", nationality_raw, lang="ar") or str(nationality_raw)
            except Exception:
                nationality_label = str(nationality_raw)
        else:
            nationality_label = "-"

        phone = (
            record.get("phone_number")
            or record.get("mobileNumber")
            or record.get("phoneNumber")
            or record.get("phone")
            or "-"
        )

        out = {
            "full_name_ar": str(full_name_ar),
            "mother_name": str(
                record.get("mother_name")
                or record.get("motherNameArabic")
                or record.get("motherName")
                or "-"
            ),
            "national_id": str(
                record.get("national_id")
                or record.get("nationalId")
                or "-"
            ),
            "date_of_birth": dob or "-",
            "gender": gender_label,
            "nationality": nationality_label,
            "phone_number": str(phone),
        }
        logger.warning(
            f"[CMP-MAP] output: full_name_ar={out.get('full_name_ar')!r}, "
            f"national_id={out.get('national_id')!r}, "
            f"date_of_birth={out.get('date_of_birth')!r}"
        )
        return out

    def _compute_person_diff_fields(self, comparison_dicts: list) -> set:
        if len(comparison_dicts) < 2:
            return set()
        diff_fields = set()
        all_keys = [
            "full_name_ar", "mother_name", "national_id",
            "date_of_birth", "gender", "nationality", "phone_number",
        ]
        for key in all_keys:
            values = {str(d.get(key, "")) for d in comparison_dicts}
            if len(values) > 1:
                diff_fields.add(key)
        return diff_fields

    # ────────────────────────────────────────────
    # Resolution Action
    # ────────────────────────────────────────────
    def _on_action_clicked(self):
        """Handle resolution action using Conflicts API."""
        justification = self._justification_edit.toPlainText().strip()
        if not justification:
            Toast.show_toast(self, tr("page.comparison.enter_justification_required"), Toast.WARNING)
            return

        selected_radio = self._resolution_group.checkedButton()
        if not selected_radio:
            return

        resolution_type = selected_radio.property("resolution_type")

        if not self._current_group or not self.duplicate_service:
            Toast.show_toast(self, tr("page.comparison.no_data_to_process"), Toast.WARNING)
            return

        conflict_id = self._current_group.get("id", "")
        if not conflict_id:
            Toast.show_toast(self, tr("page.comparison.conflict_id_unavailable"), Toast.WARNING)
            return

        action_labels = {
            "merge": tr("page.comparison.merge_records"),
            "keep_separate": tr("page.comparison.keep_records_separate"),
        }
        action_label = action_labels.get(resolution_type, tr("page.comparison.execute_action"))

        from ui.error_handler import ErrorHandler
        if not ErrorHandler.confirm(
            self,
            f"{tr('page.comparison.confirm_action_message')} {action_label}?\n{tr('page.comparison.cannot_undo')}",
            tr("page.comparison.confirm_action"),
        ):
            return

        master_id = ""
        if resolution_type == "merge":
            selected_idx = self.claim_radio_group.checkedId()
            entity_ids = [
                self._current_group.get("firstEntityId", ""),
                self._current_group.get("secondEntityId", ""),
            ]
            if selected_idx < 0 or selected_idx >= len(entity_ids):
                Toast.show_toast(self, tr("page.comparison.select_primary_record"), Toast.WARNING)
                return
            master_id = entity_ids[selected_idx]
            if not master_id:
                Toast.show_toast(self, tr("page.comparison.record_id_not_found"), Toast.WARNING)
                return

        self.action_btn.setEnabled(False)
        from ui.pages.duplicates_page import _ResolutionWorker
        self._resolution_worker = _ResolutionWorker(
            self.duplicate_service, resolution_type,
            conflict_id, justification, master_id
        )
        self._resolution_worker.finished.connect(self._on_resolution_done)
        self._resolution_worker.error.connect(self._on_resolution_err)
        self._spinner.show_loading(tr("component.loading.default"))
        self._resolution_worker.start()

    def _on_resolution_done(self, success: bool):
        self._spinner.hide_loading()
        self.action_btn.setEnabled(True)
        if success:
            self._justification_edit.clear()
            Toast.show_toast(self, tr("page.comparison.action_success"), Toast.SUCCESS)
            # Tell the duplicates page to force-reload its list right after
            # we navigate back. This avoids the 200ms refresh race in
            # main_window.navigate_to and lets the page's
            # "all-resolved-auto-return" check fire immediately.
            try:
                from app.config import Pages as _Pages
                main_win = self.window()
                if main_win is not None and hasattr(main_win, "pages"):
                    dup_page = main_win.pages.get(_Pages.DUPLICATES)
                    if dup_page is not None and hasattr(dup_page, "refresh"):
                        # Synchronous refresh — the worker still runs async,
                        # but the load_conflicts call kicks off NOW so the
                        # auto-return logic isn't delayed by the navigation
                        # timer.
                        dup_page.refresh()
            except Exception as e:
                logger.warning(f"Could not pre-refresh duplicates list: {e}")
            self.back_requested.emit()
        else:
            Toast.show_toast(self, tr("page.comparison.action_failed"), Toast.WARNING)

    def _on_resolution_err(self, error_msg: str):
        self._spinner.hide_loading()
        self.action_btn.setEnabled(True)
        Toast.show_toast(self, f"{tr('page.comparison.action_failed')}: {error_msg}", Toast.ERROR)

    # ────────────────────────────────────────────
    # Refresh — populate with real data from API
    # ────────────────────────────────────────────
    def refresh(self, data=None):
        """Refresh page with conflict data from API."""
        logger.debug("Refreshing claim comparison page")
        if data is None:
            return

        if not isinstance(data, dict):
            return

        self._current_group = data
        self._current_conflict_type = data.get("conflictType", "")
        self._current_category = get_conflict_display_category(data)
        self._current_import_package_id = data.get("_importPackageId") or ""
        is_person = self._current_category == PERSON

        # Resolved / read-only mode
        status = data.get("status", "")
        self._is_resolved = status in ("Resolved", "AutoResolved")

        # Update header title with conflict type (+ resolved tag)
        type_label = tr("page.duplicates.type_person") if is_person else tr("page.duplicates.type_property")
        if self._is_resolved:
            title_text = f"{tr('page.comparison.title')} - {type_label} ({tr('page.comparison.resolved_status')})"
        else:
            title_text = f"{tr('page.comparison.title')} - {type_label}"
        self._header.set_title(title_text)
        self._accent_line.pulse()

        # Toggle resolved banner and resolution section
        self._resolved_banner.setVisible(self._is_resolved)
        self._resolution_title.setVisible(not self._is_resolved)
        self._resolution_card.setVisible(not self._is_resolved)
        self.action_btn.setVisible(not self._is_resolved)

        # Reset doc comparison
        self._doc_empty_label.setVisible(True)
        self._doc_first_frame.setVisible(False)
        self._doc_second_frame.setVisible(False)
        self._doc_load_btn.setEnabled(True)

        # Reset justification
        self._justification_edit.clear()

        # Show spinner during data fetch
        self._spinner.show_loading(tr("component.loading.default"))

        conflict_id = data.get("id", "")
        entity_ids = [data.get("firstEntityId", ""), data.get("secondEntityId", "")]
        package_id = self._current_import_package_id

        def _fetch_comparison_data():
            details = {}
            staged_snapshot = None
            fetched_records = {}
            record_sources = {}  # eid -> "details" | "staged" | "production" | "unavailable"

            if conflict_id:
                try:
                    details = self.duplicate_service.get_conflict_details(conflict_id) or {}
                except Exception as e:
                    logger.error(f"Failed to fetch conflict details: {e}")

            logger.warning(
                f"[CMP] details fetched: keys={list(details.keys())}, "
                f"dataComparison_present={bool(details.get('dataComparison'))}, "
                f"dataComparison_preview={str(details.get('dataComparison',''))[:300]}"
            )

            # Embedded snapshots eliminate the need for secondary calls when
            # both sides are present in details. We only fall back to
            # staged-entities + production lookup when snapshots are missing
            # (older backend deploy or `null` payload edge case).
            if is_person:
                for eid in entity_ids:
                    if not eid:
                        continue

                    # 1) Embedded snapshot path (preferred — single call).
                    snap_wrapper, snap_source = _match_snapshot_to_id(details, eid)
                    snap_dto = _extract_dto_from_snapshot(snap_wrapper) if snap_wrapper else None
                    if snap_dto:
                        fetched_records[eid] = snap_dto
                        record_sources[eid] = (
                            f"snapshot:{snap_source.lower()}" if snap_source else "snapshot"
                        )
                        logger.info(
                            f"Person {eid} resolved from embedded snapshot "
                            f"(source={snap_source!r})"
                        )
                        logger.warning(
                            f"[CMP] eid={eid} source={record_sources[eid]} "
                            f"has_keys={list(snap_dto.keys())[:10]}"
                        )
                        continue

                    # 2) Fallback path — staged-entities then production.
                    if package_id and staged_snapshot is None:
                        try:
                            from services.api_client import get_api_client
                            staged_snapshot = get_api_client().get_staged_entities(package_id)
                        except Exception as se:
                            logger.warning(
                                f"Failed to fetch staged entities for package "
                                f"{package_id}: {se}"
                            )
                            staged_snapshot = {}

                    record = (
                        _find_in_staged_persons(staged_snapshot, eid)
                        if staged_snapshot else None
                    )
                    if record:
                        fetched_records[eid] = record
                        record_sources[eid] = "staged"
                        logger.info(f"Person {eid} resolved from staged entities (fallback)")
                        logger.warning(
                            f"[CMP] eid={eid} source={record_sources[eid]} "
                            f"has_keys={list(fetched_records.get(eid,{}).keys())[:10]}"
                        )
                        continue
                    try:
                        person = self.duplicate_service.get_person_data(eid)
                        if person:
                            fetched_records[eid] = person
                            record_sources[eid] = "production"
                            logger.info(f"Person {eid} resolved from production endpoint (fallback)")
                            logger.warning(
                                f"[CMP] eid={eid} source={record_sources[eid]} "
                                f"has_keys={list(fetched_records.get(eid,{}).keys())[:10]}"
                            )
                            continue
                    except Exception as pe:
                        logger.warning(f"Failed to fetch person {eid} from production: {pe}")
                    record_sources[eid] = "unavailable"
                    logger.warning(f"Person {eid} details unavailable")
                    logger.warning(
                        f"[CMP] eid={eid} source={record_sources[eid]} "
                        f"has_keys={list(fetched_records.get(eid,{}).keys())[:10]}"
                    )
            logger.warning(
                f"[CMP] worker return: fetched_persons keys={list(fetched_records.keys())}, "
                f"sources={record_sources}"
            )
            return {
                "details": details,
                "fetched_persons": fetched_records,
                "record_sources": record_sources,
            }

        self._comparison_fetch_worker = ApiWorker(_fetch_comparison_data)
        self._comparison_fetch_worker.finished.connect(
            lambda result: self._on_comparison_data_loaded(data, result)
        )
        self._comparison_fetch_worker.error.connect(self._on_comparison_data_error)
        self._comparison_fetch_worker.start()

    def _on_comparison_data_error(self, error_msg):
        """Handle comparison data fetch failure.

        We surface the user-facing message via toast AND keep the empty
        comparison area showing the "details unavailable" placeholder so
        the user never sees a silently blank page.
        """
        self._spinner.hide_loading()
        logger.error(f"Failed to fetch comparison data: {error_msg}")
        # Show the central "record details unavailable" message with a
        # toast for visibility — message_ar already humanized upstream.
        safe_msg = str(error_msg) or tr("comparison.error.record_details_unavailable")
        Toast.show_toast(self, safe_msg, Toast.ERROR)
        # Also render the placeholder banner above the comparison area by
        # passing a synthetic "both records unavailable" payload through
        # the normal load handler. This avoids a blank page.
        try:
            self._on_comparison_data_loaded(self._current_group or {}, {
                "details": {},
                "fetched_persons": {},
                "record_sources": {
                    self._current_group.get("firstEntityId", "") if self._current_group else "": "unavailable",
                    self._current_group.get("secondEntityId", "") if self._current_group else "": "unavailable",
                },
            })
        except Exception as inner:
            logger.warning(f"Could not render comparison fallback UI: {inner}")

    def _on_comparison_data_loaded(self, data, result):
        """Populate UI after background fetch completes."""
        self._spinner.hide_loading()

        details = result.get("details", {}) if result else {}
        _fetched_persons = result.get("fetched_persons", {}) if result else {}
        record_sources = result.get("record_sources", {}) if result else {}

        is_person = getattr(self, "_current_category", "") == PERSON

        logger.warning(
            f"[CMP] loaded: details_keys={list(details.keys())}, "
            f"fetched_persons_keys={list(_fetched_persons.keys())}, "
            f"record_sources={record_sources}"
        )

        if details:
            raw_dc = details.get("dataComparison", "")
            logger.info(f"Conflict details keys: {list(details.keys())}")
            if raw_dc:
                logger.info(f"dataComparison type={type(raw_dc).__name__}, "
                            f"preview={str(raw_dc)[:300]}")

        # --- Populate records section ---
        self._clear_layout(self._records_layout)
        self._record_cards.clear()

        for btn in self.claim_radio_group.buttons():
            self.claim_radio_group.removeButton(btn)

        # Parse dataComparison first so identifier fallbacks below can use it.
        # Backend shape (TRRCMS-Backend ConflictDetailDto.DataComparison):
        #   { "fields": [{"field": "...", "first": "...", "second": "...",
        #                 "match": bool}, ...] }
        # Older builds may also send a flat list (legacy). We normalise all
        # variants into a 2-element list of dicts keyed by our internal
        # canonical comparison-field names so the per-record loop below can
        # populate either record reliably without a per-entity production
        # lookup succeeding.
        raw_comparison = details.get("dataComparison", "")
        data_comparison = self._parse_data_comparison(raw_comparison)

        def _identifier_for(idx: int) -> str:
            # `dict.get(key, default)` returns the empty string if the key is
            # PRESENT but blank — which is what the backend sends when the
            # entity is staged-only. Walk a fallback chain that treats "",
            # None, and "-" as missing, ending at the parsed dataComparison
            # full-name field so the card never appears blank when the table
            # row has data.
            key_id = "firstEntityIdentifier" if idx == 0 else "secondEntityIdentifier"
            key_eid = "firstEntityId" if idx == 0 else "secondEntityId"
            for candidate in (
                data.get(key_id),
                (data_comparison[idx] if idx < len(data_comparison) else {}).get("full_name_ar"),
                (data_comparison[idx] if idx < len(data_comparison) else {}).get("fullNameArabic"),
                data.get(key_eid),
            ):
                if candidate not in (None, "", "-"):
                    return str(candidate)
            return "-"

        records = []
        first_id = _identifier_for(0)
        second_id = _identifier_for(1)

        logger.warning(
            f"[CMP] parsed dataComparison: len={len(data_comparison)}, "
            f"rec0_keys={list((data_comparison[0] or {}).keys()) if data_comparison else []}, "
            f"rec1_keys={list((data_comparison[1] or {}).keys()) if len(data_comparison)>1 else []}"
        )
        logger.warning(
            f"[CMP] rec0_sample: "
            f"{dict(list((data_comparison[0] or {}).items())[:8]) if data_comparison else {}}"
        )
        logger.warning(
            f"[CMP] rec1_sample: "
            f"{dict(list((data_comparison[1] or {}).items())[:8]) if len(data_comparison)>1 else {}}"
        )

        entity_ids = [data.get("firstEntityId", ""), data.get("secondEntityId", "")]
        logger.warning(
            f"[CMP] entity_ids={entity_ids}, "
            f"firstEntityIdentifier={data.get('firstEntityIdentifier')!r}, "
            f"secondEntityIdentifier={data.get('secondEntityIdentifier')!r}"
        )
        records.append({
            "id": entity_ids[0],
            "identifier": first_id,
            "label": tr("page.comparison.first_record"),
        })
        records.append({
            "id": entity_ids[1],
            "identifier": second_id,
            "label": tr("page.comparison.second_record"),
        })

        # Extract national IDs for person duplicates
        person_national_ids = []
        if is_person:
            if data_comparison:
                for dc in data_comparison[:2]:
                    comp = dc if isinstance(dc, dict) else {}
                    if isinstance(dc, list):
                        comp = {}
                        for fi in dc:
                            if isinstance(fi, dict):
                                comp[fi.get("fieldName", "")] = fi.get("value", "")
                    nid = comp.get("nationalId", comp.get("nationalID", ""))
                    person_national_ids.append(str(nid) if nid else "")
            else:
                for eid in entity_ids:
                    p = _fetched_persons.get(eid, {})
                    nid = p.get("nationalId", "") if p else ""
                    person_national_ids.append(str(nid) if nid else "")

        # Build record selection cards
        date_str = ""
        raw_date = data.get("detectedDate", "")
        if raw_date and "T" in str(raw_date):
            date_str = str(raw_date).split("T")[0]

        for idx, record in enumerate(records):
            subtitle = ""
            if is_person and idx < len(person_national_ids) and person_national_ids[idx]:
                subtitle = person_national_ids[idx]
            elif not is_person:
                subtitle = self._current_conflict_type

            icon_name = "yelow" if is_person else "blue"
            card_data = {
                "label": record["label"],
                "identifier": record["identifier"],
                "date": date_str,
                "subtitle": subtitle,
                "icon": icon_name,
            }

            record_card = _RecordCard(card_data, parent=self._records_card)
            self.claim_radio_group.addButton(record_card.radio, idx)
            if idx == 0:
                record_card.radio.setChecked(True)
            record_card.card_clicked.connect(self._update_record_selection)
            self._records_layout.addWidget(record_card)
            self._record_cards.append(record_card)

        self._update_record_selection()

        # Disable record selection in resolved mode
        if self._is_resolved:
            for card in self._record_cards:
                card.setEnabled(False)
                card.setCursor(QCursor(Qt.ArrowCursor))

        # --- Populate comparison table ---
        if is_person:
            comparison_dicts = []
            for idx, record in enumerate(records):
                # Build the record by LAYERING three sources from least to
                # most authoritative. This guarantees the comparison cell
                # always has at least name + NID even when the production
                # endpoint returns an unrelated thin payload.
                #
                #   layer 1: identifier skeleton (firstEntityIdentifier +
                #            sibling NID — always works for person dups)
                #   layer 2: parsed dataComparison[idx] (per-record fields)
                #   layer 3: production person DTO (fetched by id) — only
                #            applied when it contains real person data, so
                #            a {"id":"..."} placeholder doesn't blank out
                #            the lower layers.
                logger.warning(f"[CMP] === record idx={idx} eid={record['id']!r} ===")

                merged = self._build_identifier_fallback(data, idx, data_comparison) or {}
                logger.warning(f"[CMP] idx={idx} skeleton_fallback={merged}")

                dc_dict = data_comparison[idx] if idx < len(data_comparison) else {}
                if isinstance(dc_dict, dict) and dc_dict:
                    merged.update({k: v for k, v in dc_dict.items() if v not in ("", None)})
                logger.warning(
                    f"[CMP] idx={idx} "
                    f"dc_dict_keys={list((dc_dict if isinstance(dc_dict,dict) else {}).keys())}, "
                    f"after_dc_merge_keys={list(merged.keys())}"
                )

                person_dto = _fetched_persons.get(record["id"])
                logger.warning(
                    f"[CMP] idx={idx} person_dto_present={isinstance(person_dto, dict)}, "
                    f"meaningful={self._is_meaningful_person(person_dto) if isinstance(person_dto, dict) else False}, "
                    f"person_dto_keys={list(person_dto.keys()) if isinstance(person_dto, dict) else None}"
                )
                if isinstance(person_dto, dict) and self._is_meaningful_person(person_dto):
                    merged.update(
                        {k: v for k, v in person_dto.items() if v not in ("", None)}
                    )

                logger.warning(
                    f"[CMP] idx={idx} merged_final_keys={list(merged.keys())}, "
                    f"merged_sample={dict(list(merged.items())[:8])}"
                )

                if not merged:
                    logger.warning(f"Person {record['id']} not available — placeholder")
                    mapped = self._map_person_to_comparison_dict({})
                    mapped["_source"] = "unavailable"
                    mapped["_unavailable"] = True
                    mapped["_unavailable_text"] = tr("page.comparison.record_unavailable")
                else:
                    mapped = self._map_person_to_comparison_dict(merged)
                    mapped["_source"] = record_sources.get(record["id"], "merged")
                    mapped["_unavailable"] = False
                logger.warning(
                    f"[CMP] idx={idx} mapped_full_name_ar={mapped.get('full_name_ar')!r}, "
                    f"national_id={mapped.get('national_id')!r}, "
                    f"unavailable={mapped.get('_unavailable')}, "
                    f"source={mapped.get('_source')}"
                )
                comparison_dicts.append(mapped)

            diff_fields = self._compute_person_diff_fields(comparison_dicts)
            self._populate_comparison_table(comparison_dicts, diff_fields)
        else:
            # Property duplicates: fetch units asynchronously
            record_ids = [r["id"] for r in records]
            self._pending_data_comparison = data_comparison
            self._property_units_worker = ApiWorker(
                self._fetch_all_property_units, record_ids, details
            )
            self._property_units_worker.finished.connect(self._on_property_units_loaded)
            self._property_units_worker.error.connect(self._on_property_units_error)
            self._spinner.show_loading(tr("component.loading.default"))
            self._property_units_worker.start()

    def _fetch_all_property_units(self, record_ids, details=None):
        """Fetch all property unit data for comparison (runs in worker thread).

        Resolution order per entity:
          1. Embedded snapshot from `details.firstEntity` / `details.secondEntity`
             — preferred: zero extra API calls.
          2. Staged-entities snapshot (only fetched lazily when needed).
          3. Production lookup via /propertyunits/{id}.

        The staged side of a duplicate isn't in production yet, so falling
        back to a pure production lookup would 404 and blank the column.
        """
        from services.api_client import get_api_client
        api = get_api_client()

        staged_snapshot = None  # Lazily fetched only when snapshot path fails.
        package_id = self._current_import_package_id
        logger.warning(
            f"[CMP-PROP] worker start: package_id={package_id!r}, "
            f"record_ids={record_ids}, has_details={bool(details)}"
        )

        def _ensure_staged_snapshot():
            nonlocal staged_snapshot
            if staged_snapshot is not None or not package_id:
                return
            try:
                staged_snapshot = api.get_staged_entities(package_id) or {}
            except Exception as se:
                logger.warning(
                    f"[CMP-PROP] Failed to fetch staged entities for package "
                    f"{package_id}: {se}"
                )
                staged_snapshot = {}

        results = []
        for entity_id in record_ids:
            if not entity_id:
                results.append({})
                continue

            unit_dto = None
            from_snapshot = False
            from_staged = False

            # 1) Embedded snapshot path.
            snap_wrapper, snap_source = _match_snapshot_to_id(details, entity_id)
            snap_dto = _extract_dto_from_snapshot(snap_wrapper) if snap_wrapper else None
            if snap_dto:
                unit_dto = snap_dto
                from_snapshot = True
                from_staged = (snap_source.lower() == "staging")
                logger.warning(
                    f"[CMP-PROP] eid={entity_id} resolved from embedded snapshot "
                    f"(source={snap_source!r}), keys={list(unit_dto.keys())[:15]}"
                )

            # 2) Staged-entities fallback.
            if unit_dto is None:
                _ensure_staged_snapshot()
                if staged_snapshot:
                    staged_unit = _find_in_staged_property_units(
                        staged_snapshot, entity_id
                    )
                    if staged_unit:
                        unit_dto = dict(staged_unit)
                        from_staged = True
                        logger.warning(
                            f"[CMP-PROP] eid={entity_id} resolved from staged "
                            f"(fallback), keys={list(unit_dto.keys())[:15]}"
                        )

            # 3) Production fallback.
            if unit_dto is None:
                try:
                    unit_dto = api.get_property_unit_by_id(entity_id)
                    logger.warning(
                        f"[CMP-PROP] eid={entity_id} production lookup "
                        f"{'succeeded' if unit_dto else 'returned empty'} (fallback)"
                    )
                except Exception as e:
                    logger.error(f"[CMP-PROP] eid={entity_id} production failed: {e}")
                    unit_dto = None

            if not unit_dto:
                results.append({})
                continue

            # Attach the parent building. The propertyUnit DTO (whether from
            # snapshot or production) carries `buildingId` only — the building
            # object itself must come from staged-entities (when staging) or
            # production (when production).
            building_id = (
                unit_dto.get("buildingId")
                or unit_dto.get("building_id")
                or ""
            )
            if building_id:
                building_dto = None
                if from_staged:
                    _ensure_staged_snapshot()
                    if staged_snapshot:
                        staged_building = _find_in_staged_buildings(
                            staged_snapshot, building_id
                        )
                        if staged_building:
                            building_dto = dict(staged_building)
                else:
                    try:
                        building_dto = api.get_building_by_id(building_id)
                    except Exception as be:
                        logger.warning(
                            f"Failed to fetch building {building_id}: {be}"
                        )
                if building_dto:
                    unit_dto["_building"] = building_dto

            logger.warning(
                f"[CMP-PROP] eid={entity_id} final: from_snapshot={from_snapshot}, "
                f"from_staged={from_staged}, has_building={'_building' in unit_dto}"
            )
            results.append(unit_dto)

        return results

    def _on_property_units_loaded(self, unit_dtos):
        """Handle property unit data loaded from API."""
        self._spinner.hide_loading()
        data_comparison = getattr(self, '_pending_data_comparison', [])
        conflict_data = self._current_group or {}
        comparison_dicts = []

        for idx, unit_dto in enumerate(unit_dtos):
            logger.warning(
                f"[CMP-PROP] === record idx={idx} dto_present={bool(unit_dto)} "
                f"dc_present={bool(data_comparison and idx < len(data_comparison) and data_comparison[idx])}"
            )
            if unit_dto:
                building_data = unit_dto.get("_building", {})
                mapped = self._map_to_comparison_dict(
                    building_data or unit_dto, unit_dto
                )
                comparison_dicts.append(mapped)
                continue

            # Build a property-skeleton fallback so the column never blanks
            # out when production 404s and dataComparison is null. Order:
            #   1. dataComparison row (richest when backend supplies it)
            #   2. firstEntityIdentifier / secondEntityIdentifier from the
            #      conflict (always present — usually "<building_id>|<unit>")
            comp_dict = {}
            if data_comparison and idx < len(data_comparison):
                dc = data_comparison[idx]
                if isinstance(dc, dict):
                    comp_dict = {k: v for k, v in dc.items() if v not in ("", None)}
                elif isinstance(dc, list):
                    for fi in dc:
                        if isinstance(fi, dict):
                            key = fi.get("fieldName", "") or fi.get("field", "")
                            val = fi.get("value", fi.get("first", ""))
                            if key and val not in ("", None):
                                comp_dict[key] = str(val)

            if not comp_dict:
                ident = conflict_data.get(
                    "firstEntityIdentifier" if idx == 0 else "secondEntityIdentifier",
                    "",
                )
                if ident:
                    # Identifier shape observed: "<buildingId>|<unit>" — split
                    # so the table at least shows the building code and unit
                    # number rather than two columns of dashes.
                    parts = str(ident).split("|", 1)
                    comp_dict["buildingId"] = parts[0] if parts else str(ident)
                    if len(parts) > 1 and parts[1]:
                        comp_dict["unitIdentifier"] = parts[1]

            logger.warning(
                f"[CMP-PROP] idx={idx} skeleton_keys={list(comp_dict.keys())}, "
                f"sample={dict(list(comp_dict.items())[:6])}"
            )
            comparison_dicts.append(self._map_to_comparison_dict(comp_dict, comp_dict))

        diff_fields = self._compute_comparison_diff_fields(comparison_dicts)
        self._populate_comparison_table(comparison_dicts, diff_fields)

    def _on_property_units_error(self, error_msg):
        """Handle property unit fetch error."""
        self._spinner.hide_loading()
        logger.error(f"Failed to fetch property units: {error_msg}")

    # ────────────────────────────────────────────
    # Language Update
    # ────────────────────────────────────────────
    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        # Header
        self._header.set_title(tr("page.comparison.title"))
        self._back_btn.setText(tr("action.back"))
        self.action_btn.setText(tr("page.comparison.execute"))

        # Section titles
        self._records_title._title_label.setText(tr("page.comparison.records_section"))
        self._records_title._subtitle_label.setText(tr("page.comparison.records_section_subtitle"))

        self._comparison_title._title_label.setText(tr("page.comparison.comparison"))
        self._comparison_title._subtitle_label.setText(tr("page.comparison.comparison_section_subtitle"))

        self._doc_title._title_label.setText(tr("page.comparison.document_comparison"))
        self._doc_title._subtitle_label.setText(tr("page.comparison.doc_section_subtitle"))

        self._resolution_title._title_label.setText(tr("page.comparison.resolution_action"))
        self._resolution_title._subtitle_label.setText(tr("page.comparison.resolution_subtitle"))

        # Resolved banner
        self._resolved_label.setText(tr("page.comparison.resolved_status"))

        # Doc load button & empty state
        self._doc_load_btn.setText(tr("page.comparison.load_comparison"))
        self._doc_empty_label.setText(tr("page.comparison.click_load_comparison"))

        # Resolution radio buttons
        resolution_labels = [
            tr("page.comparison.merge_records"),
            tr("page.comparison.keep_separate"),
        ]
        for idx, btn in enumerate(self._resolution_group.buttons()):
            if idx < len(resolution_labels):
                btn.setText(resolution_labels[idx])

        # Justification — keep the rich-text label with the red asterisk in
        # sync with the language change.
        self._justification_label.setText(
            f"{tr('page.comparison.justification_required')} "
            f"<span style='color:#DC2626;'>*</span>"
        )
        self._justification_edit.setPlaceholderText(tr("page.comparison.enter_justification"))
        if hasattr(self, "_justification_hint"):
            self._justification_hint.setText(tr("page.comparison.justification_audit_hint"))

        # Document column titles
        self._doc_first_frame._title_label.setText(tr("page.comparison.first_record_docs"))
        self._doc_second_frame._title_label.setText(tr("page.comparison.second_record_docs"))

        # Re-render if data is loaded
        if self._current_group:
            self.refresh(self._current_group)
