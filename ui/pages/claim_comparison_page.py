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
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, ButtonDimensions
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.accent_line import AccentLine
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.animation_utils import stagger_fade_in
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

RADIO_STYLE = StyleManager.radio_button()

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

_TABLE_DIFF_INDICATOR = f"""
    QLabel {{
        color: {Colors.PRIMARY_BLUE};
        background: #EBF5FF;
        border-left: 3px solid {Colors.PRIMARY_BLUE};
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
        self.setFixedHeight(72)
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
        self._radio.setFixedSize(20, 20)
        layout.addWidget(self._radio)

        # Icon
        icon_name = data.get("icon", "blue")
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
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

        # Action button in header
        self.action_btn = QPushButton(tr("page.comparison.execute"))
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self.action_btn.setFixedSize(100, ButtonDimensions.SAVE_HEIGHT)
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
        self._back_btn.setFixedSize(100, ButtonDimensions.SAVE_HEIGHT)
        self._back_btn.setStyleSheet(StyleManager.dark_action_button())
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._back_btn)

        outer_layout.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        outer_layout.addWidget(self._accent_line)

        # Resolved status banner (hidden by default)
        self._resolved_banner = QFrame()
        self._resolved_banner.setFixedHeight(40)
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
        resolved_icon.setFixedSize(20, 20)
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
        self._doc_load_btn.setFixedHeight(32)
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

        just_label = QLabel(tr("page.comparison.justification_required"))
        just_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        just_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        res_layout.addWidget(just_label)

        self._justification_edit = QTextEdit()
        self._justification_edit.setPlaceholderText(tr("page.comparison.enter_justification"))
        self._justification_edit.setFixedHeight(80)
        self._justification_edit.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._justification_edit.setStyleSheet(StyleManager.form_input_light())
        res_layout.addWidget(self._justification_edit)

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
        icon_label.setFixedSize(28, 28)
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

        # Determine fields based on conflict type
        if self._current_conflict_type == "PersonDuplicate":
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

        row_offset = 1
        for idx, (field_key, label_text) in enumerate(fields):
            row = row_offset + idx
            is_diff = field_key in diff_fields
            is_alt = idx % 2 == 0
            alt_bg = "#F8FBFF" if is_alt else "transparent"

            # Field label column
            field_lbl = QLabel(label_text)
            field_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            field_lbl.setStyleSheet(_TABLE_ROW_FIELD.replace("transparent", alt_bg))
            self._table_grid.addWidget(field_lbl, row, 0)

            # Thin separator between field and record A
            sep1 = QFrame()
            sep1.setFixedWidth(1)
            sep1.setStyleSheet(f"QFrame {{ background: #E2EAF2; }}")
            self._table_grid.addWidget(sep1, row, 1)

            # Record A value
            val_a = str(comparison_dicts[0].get(field_key, "-"))
            lbl_a = QLabel(val_a)
            lbl_a.setWordWrap(True)
            if is_diff:
                lbl_a.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
                lbl_a.setStyleSheet(_TABLE_DIFF_INDICATOR.replace("#EBF5FF", "#E8F2FF"))
            else:
                lbl_a.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                lbl_a.setStyleSheet(_TABLE_ROW_VALUE_A.replace("#F0F7FF", "#EDF4FF" if is_alt else "#F0F7FF"))
            self._table_grid.addWidget(lbl_a, row, 2)

            # Thin separator between record A and B
            sep2 = QFrame()
            sep2.setFixedWidth(1)
            sep2.setStyleSheet(f"QFrame {{ background: #E2EAF2; }}")
            self._table_grid.addWidget(sep2, row, 3)

            # Record B value
            val_b = str(comparison_dicts[1].get(field_key, "-"))
            lbl_b = QLabel(val_b)
            lbl_b.setWordWrap(True)
            if is_diff:
                lbl_b.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
                lbl_b.setStyleSheet(_TABLE_DIFF_INDICATOR.replace("#EBF5FF", "#FFF8EB"))
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
        icon_lbl.setFixedWidth(20)
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
        ver_lbl.setFixedWidth(28)
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
        is_person = self._current_conflict_type == "PersonDuplicate"

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

    def _map_person_to_comparison_dict(self, record: dict) -> dict:
        from services.vocab_service import get_label

        full_name_ar = record.get("fullNameArabic") or ""
        if not full_name_ar:
            parts = filter(None, [
                record.get("firstNameArabic", ""),
                record.get("fatherNameArabic", ""),
                record.get("familyNameArabic", ""),
            ])
            full_name_ar = " ".join(parts) or "-"

        dob = record.get("dateOfBirth") or ""
        if dob and "T" in str(dob):
            dob = str(dob).split("T")[0]

        gender_raw = record.get("gender")
        gender_label = get_label("Gender", gender_raw, lang="ar") if gender_raw else "-"

        nationality_raw = record.get("nationality")
        nationality_label = get_label("Nationality", nationality_raw, lang="ar") if nationality_raw else "-"

        return {
            "full_name_ar": str(full_name_ar),
            "mother_name": str(record.get("motherNameArabic") or "-"),
            "national_id": str(record.get("nationalId") or "-"),
            "date_of_birth": dob or "-",
            "gender": gender_label,
            "nationality": nationality_label,
            "phone_number": str(record.get("mobileNumber") or "-"),
        }

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
        is_person = self._current_conflict_type == "PersonDuplicate"

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

        def _fetch_comparison_data():
            details = {}
            fetched_persons = {}
            if conflict_id:
                try:
                    details = self.duplicate_service.get_conflict_details(conflict_id)
                except Exception as e:
                    logger.error(f"Failed to fetch conflict details: {e}")
            if is_person:
                for eid in entity_ids:
                    if eid:
                        try:
                            person = self.duplicate_service.get_person_data(eid)
                            if person:
                                fetched_persons[eid] = person
                        except Exception as pe:
                            logger.warning(f"Failed to fetch person {eid}: {pe}")
            return {"details": details, "fetched_persons": fetched_persons}

        self._comparison_fetch_worker = ApiWorker(_fetch_comparison_data)
        self._comparison_fetch_worker.finished.connect(
            lambda result: self._on_comparison_data_loaded(data, result)
        )
        self._comparison_fetch_worker.error.connect(self._on_comparison_data_error)
        self._comparison_fetch_worker.start()

    def _on_comparison_data_error(self, error_msg):
        """Handle comparison data fetch failure."""
        self._spinner.hide_loading()
        logger.error(f"Failed to fetch comparison data: {error_msg}")
        Toast.show_toast(self, str(error_msg), Toast.ERROR)

    def _on_comparison_data_loaded(self, data, result):
        """Populate UI after background fetch completes."""
        self._spinner.hide_loading()

        details = result.get("details", {}) if result else {}
        _fetched_persons = result.get("fetched_persons", {}) if result else {}

        is_person = self._current_conflict_type == "PersonDuplicate"

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

        records = []
        first_id = data.get("firstEntityIdentifier", data.get("firstEntityId", "-"))
        second_id = data.get("secondEntityIdentifier", data.get("secondEntityId", "-"))

        raw_comparison = details.get("dataComparison", "")
        data_comparison = []
        if raw_comparison:
            if isinstance(raw_comparison, list):
                data_comparison = raw_comparison
            elif isinstance(raw_comparison, str):
                import json as _json
                try:
                    parsed = _json.loads(raw_comparison)
                    if isinstance(parsed, list):
                        data_comparison = parsed
                except (ValueError, TypeError):
                    pass

        entity_ids = [data.get("firstEntityId", ""), data.get("secondEntityId", "")]
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
                person_dto = _fetched_persons.get(record["id"])
                if person_dto:
                    comparison_dicts.append(self._map_person_to_comparison_dict(person_dto))
                elif data_comparison and idx < len(data_comparison):
                    dc = data_comparison[idx]
                    comp_dict = {}
                    if isinstance(dc, dict):
                        if "fieldName" in dc:
                            comp_dict[dc.get("fieldName", "")] = str(dc.get("value", "-"))
                        else:
                            comp_dict = dc
                    elif isinstance(dc, list):
                        for field_item in dc:
                            if isinstance(field_item, dict):
                                key = field_item.get("fieldName", "")
                                val = field_item.get("value", "-")
                                comp_dict[key] = str(val) if val else "-"
                    comparison_dicts.append(self._map_person_to_comparison_dict(comp_dict))
                else:
                    logger.warning(f"Person {record['id']} not available")
                    comparison_dicts.append(self._map_person_to_comparison_dict({}))

            diff_fields = self._compute_person_diff_fields(comparison_dicts)
            self._populate_comparison_table(comparison_dicts, diff_fields)
        else:
            # Property duplicates: fetch units asynchronously
            record_ids = [r["id"] for r in records]
            self._pending_data_comparison = data_comparison
            self._property_units_worker = ApiWorker(
                self._fetch_all_property_units, record_ids
            )
            self._property_units_worker.finished.connect(self._on_property_units_loaded)
            self._property_units_worker.error.connect(self._on_property_units_error)
            self._spinner.show_loading(tr("component.loading.default"))
            self._property_units_worker.start()

    def _fetch_all_property_units(self, record_ids):
        """Fetch all property unit data for comparison (runs in worker thread)."""
        from services.api_client import get_api_client
        api = get_api_client()
        results = []
        for entity_id in record_ids:
            if not entity_id:
                results.append({})
                continue
            try:
                unit_dto = api.get_property_unit_by_id(entity_id)
                if not unit_dto:
                    results.append({})
                    continue
                building_id = unit_dto.get("buildingId", unit_dto.get("building_id", ""))
                if building_id:
                    try:
                        building_dto = api.get_building_by_id(building_id)
                        if building_dto:
                            unit_dto["_building"] = building_dto
                    except Exception as be:
                        logger.warning(f"Failed to fetch building {building_id}: {be}")
                results.append(unit_dto)
            except Exception as e:
                logger.error(f"Failed to fetch property unit {entity_id}: {e}")
                results.append({})
        return results

    def _on_property_units_loaded(self, unit_dtos):
        """Handle property unit data loaded from API."""
        self._spinner.hide_loading()
        data_comparison = getattr(self, '_pending_data_comparison', [])
        comparison_dicts = []

        for idx, unit_dto in enumerate(unit_dtos):
            if unit_dto:
                building_data = unit_dto.get("_building", {})
                comparison_dicts.append(self._map_to_comparison_dict(
                    building_data or unit_dto, unit_dto
                ))
            elif data_comparison and idx < len(data_comparison):
                dc = data_comparison[idx]
                comp_dict = dc if isinstance(dc, dict) else {}
                if isinstance(dc, list):
                    comp_dict = {}
                    for fi in dc:
                        if isinstance(fi, dict):
                            comp_dict[fi.get("fieldName", "")] = str(fi.get("value", "-"))
                comparison_dicts.append(self._map_to_comparison_dict(comp_dict, comp_dict))
            else:
                logger.warning(f"Property unit at index {idx} not available")
                comparison_dicts.append(self._map_to_comparison_dict({}, {}))

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

        # Justification
        self._justification_edit.setPlaceholderText(tr("page.comparison.enter_justification"))

        # Re-render if data is loaded
        if self._current_group:
            self.refresh(self._current_group)
