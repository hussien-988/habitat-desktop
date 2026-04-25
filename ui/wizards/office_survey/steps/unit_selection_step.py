# -*- coding: utf-8 -*-
"""
Unit Selection Step - Step 2 of Office Survey Wizard.

Allows user to:
- View existing units in the selected building
- Select an existing unit
- Create a new unit with validation
"""

from typing import Dict, Any, Optional, List
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QWidget,
    QComboBox, QSpinBox, QTextEdit,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtWidgets import QSizePolicy, QSpacerItem
from PyQt5.QtGui import QCursor, QIcon, QColor, QDoubleValidator

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.wizard_styles import (
    MINI_CARD_STYLE, MINI_CARD_SELECTED_STYLE,
    make_step_card, make_icon_header, make_divider, DIVIDER_COLOR,
    FORM_FIELD_STYLE, FOOTER_PRIMARY_STYLE, FOOTER_SECONDARY_STYLE,
)
from controllers.unit_controller import UnitController
from models.unit import PropertyUnit as Unit
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from utils.logger import get_logger
from utils.helpers import build_hierarchical_address
from ui.design_system import Colors, ScreenScale
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.action_button import ActionButton
from ui.components.rtl_combo import RtlCombo
from ui.components.toast import Toast
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import get_unit_status_display, get_unit_type_display, get_unit_type_options, get_unit_status_options
from services.error_mapper import map_exception
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.components.bottom_sheet import BottomSheet
from app.config import Config

logger = get_logger(__name__)




class UnitSelectionStep(BaseStep):
    """
    Step 2: Unit Selection/Creation.

    User can:
    - View existing units in the selected building
    - Select an existing unit
    - Create a new unit with uniqueness validation
    UI copied from office_survey_wizard.py _create_unit_step() - exact match.
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)
        self.unit_controller = UnitController(self.context.db)
        self.selected_unit: Optional[Unit] = None

        # Initialize API client for linking units to survey
        self._api_service = get_api_client()
        self._loaded_building_uuid = None  # Track which building's units are loaded

        # Flat list of all unit card widgets for style refresh
        self._all_unit_cards: List[QFrame] = []

        # Set auth token for API calls if available
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self.unit_controller.set_auth_token(main_window._api_token)

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        layout = self.main_layout
        layout.setContentsMargins(0, 8, 0, 16)
        layout.setSpacing(10)

        # Two-column horizontal split: narrow info card (left) + wide units card (right)
        two_col = QHBoxLayout()
        two_col.setSpacing(ScreenScale.w(14))
        two_col.setContentsMargins(0, 0, 0, 0)

        # ── Card 1: Building Summary (narrow, fills column height) ──────
        self.unit_building_frame = make_step_card()
        self.unit_building_frame.setVisible(False)
        self.unit_building_frame.setFixedWidth(ScreenScale.w(290))
        self.unit_building_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        bld_layout = QVBoxLayout(self.unit_building_frame)
        bld_layout.setContentsMargins(16, 16, 16, 16)
        bld_layout.setSpacing(ScreenScale.h(6))

        # Address row (icon + address)
        addr_row = QHBoxLayout()
        addr_row.setSpacing(ScreenScale.w(6))
        addr_icon = QLabel()
        addr_icon_px = Icon.load_pixmap("dec", size=14)
        if addr_icon_px and not addr_icon_px.isNull():
            addr_icon.setPixmap(addr_icon_px)
        else:
            addr_icon.setText("📍")
        addr_icon.setStyleSheet("background: transparent; border: none;")
        addr_icon.setAlignment(Qt.AlignTop)
        addr_row.addWidget(addr_icon, 0, Qt.AlignTop)

        self.unit_building_address = QLabel(tr("wizard.unit.address_label"))
        self.unit_building_address.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.unit_building_address.setStyleSheet("color: #334155; background: transparent; border: none;")
        self.unit_building_address.setWordWrap(True)
        addr_row.addWidget(self.unit_building_address, 1)
        bld_layout.addLayout(addr_row)

        bld_layout.addWidget(make_divider())

        # 5 stats — each wrapped in an expanding widget with stretch factor 1,
        # so they distribute equally across the card's vertical space.
        _bld_is_rtl = get_layout_direction() == Qt.RightToLeft
        _bld_align = (
            Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter
            if _bld_is_rtl else
            Qt.AlignLeft  | Qt.AlignAbsolute | Qt.AlignVCenter
        )

        def _stat_widget(lbl_key, val="-"):
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            row = QHBoxLayout(wrap)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            lbl = QLabel(tr(lbl_key))
            lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            lbl.setAlignment(_bld_align)
            v = QLabel(val)
            v.setFont(create_font(size=11, weight=FontManager.WEIGHT_BOLD))
            v.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            v.setAlignment(_bld_align)
            row.addWidget(lbl, 0, Qt.AlignVCenter)
            row.addStretch(1)
            row.addWidget(v, 0, Qt.AlignVCenter)
            return wrap, v, lbl

        stats_specs = [
            ("wizard.building.status",        "ui_building_status", "_lbl_status"),
            ("wizard.building.type",          "ui_building_type",   "_lbl_type"),
            ("wizard.building.units_count",   "ui_units_count",     "_lbl_units"),
            ("wizard.building.parcels_count", "ui_parcels_count",   "_lbl_parcels"),
            ("wizard.building.shops_count",   "ui_shops_count",     "_lbl_shops"),
        ]
        for i, (key, val_attr, lbl_attr) in enumerate(stats_specs):
            stat_widget, v, lbl = _stat_widget(key)
            setattr(self, val_attr, v)
            setattr(self, lbl_attr, lbl)
            bld_layout.addWidget(stat_widget, 1)  # stretch factor 1 for even distribution
            if i < len(stats_specs) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet("color: #EEF2F8; background: #EEF2F8; border: none; max-height: 1px;")
                sep.setFixedHeight(1)
                bld_layout.addWidget(sep, 0)

        two_col.addWidget(self.unit_building_frame, 0)

        # ── Card 2: Units Selection (wide) ──────────────────────────────
        units_main_frame = make_step_card()

        units_main_layout = QVBoxLayout(units_main_frame)
        units_main_layout.setSpacing(14)
        units_main_layout.setContentsMargins(16, 16, 16, 16)

        # Header: icon + title/subtitle + add-unit button
        header_layout, header_title, header_subtitle = make_icon_header(
            tr("wizard.unit.select_title"),
            tr("wizard.unit.select_subtitle"),
            "move"
        )

        # إعادة تطبيق الترجمة (مهم جداً)
        header_title.setText(tr("wizard.unit.select_title"))
        header_subtitle.setText(tr("wizard.unit.select_subtitle"))
        self._units_header_title = header_title
        self._units_header_subtitle = header_subtitle

        self.add_unit_btn = ActionButton(
            text=tr("wizard.unit.add_button"),
            variant="outline",
            icon_name="icon",
            width=125,
            height=44
        )
        self.add_unit_btn.clicked.connect(self._show_add_unit_form)
        header_layout.addWidget(self.add_unit_btn)

        units_main_layout.addLayout(header_layout)

        # BottomSheet reference for unit creation (created on demand)
        self._unit_sheet = None
        self._pending_auto_select_uuid = None  # UUID to auto-select after async load

        # Empty state widget (shown when no units)
        self._empty_state = self._create_empty_state()
        units_main_layout.addWidget(self._empty_state)

        # Units list container (inside white frame)
        self.units_container = QWidget()
        self.units_layout = QVBoxLayout(self.units_container)
        self.units_layout.setSpacing(10)
        self.units_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for units
        scroll = QScrollArea()
        scroll.setLayoutDirection(get_layout_direction())
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.units_container)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: white; }"
            + StyleManager.scrollbar()
        )
        self._scroll_area = scroll
        units_main_layout.addWidget(scroll, 1)

        two_col.addWidget(units_main_frame, 1)

        layout.addLayout(two_col, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_empty_state(self) -> QWidget:
        """Create empty state widget shown when no units exist."""
        import os
        from PyQt5.QtGui import QPixmap

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 40, 0, 40)

        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(15)

        # Icon with orange circle background
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(70), ScreenScale.h(70))
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet("""
            background-color: #EBF5FF;
            border: 1px solid #DBEAFE;
            border-radius: 35px;
        """)

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "assets", "images", "tdesign_no-result.png"
        )
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_container.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            no_result_pixmap = Icon.load_pixmap("tdesign_no-result", size=40)
            if no_result_pixmap and not no_result_pixmap.isNull():
                icon_container.setPixmap(no_result_pixmap)
            else:
                icon_container.setText("!")
                icon_container.setStyleSheet(icon_container.styleSheet() + "font-size: 28px; color: #1a1a1a;")

        # Title
        title_label = QLabel(tr("wizard.unit.empty_title"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Description
        desc_label = QLabel(tr("wizard.unit.empty_desc"))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_DESC, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        center_layout.addWidget(icon_container, alignment=Qt.AlignCenter)
        center_layout.addWidget(title_label)
        center_layout.addWidget(desc_label)

        main_layout.addWidget(center_widget)

        return container

    def _load_units(self):
        """Load units for the selected building and display as cards (non-blocking)."""
        if not self.context.building:
            self._loaded_building_uuid = None
            self.unit_building_frame.setVisible(False)
            while self.units_layout.count():
                child = self.units_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self._empty_state.setVisible(True)
            self._scroll_area.setVisible(False)
            self.selected_unit = None
            self.emit_validation_changed(False)
            return

        building_uuid = self.context.building.building_uuid

        if building_uuid and self._loaded_building_uuid == building_uuid:
            logger.info(f"Units already loaded for building {building_uuid}, skipping fetch")
            return

        building = self.context.building

        address = build_hierarchical_address(
            building_obj=building,
            unit_obj=None,
            separator=" - ",
            include_unit=False
        )
        self.unit_building_address.setText(address)

        self.ui_building_type.setText(building.building_type_display or "-")
        self.ui_building_status.setText(building.building_status_display or "-")
        self.ui_units_count.setText(str(getattr(building, 'number_of_apartments', 0) + (building.number_of_shops or 0)))
        self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
        self.ui_shops_count.setText(str(building.number_of_shops or 0))

        self.unit_building_frame.setVisible(True)

        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        survey_id = self.context.get_data("survey_id")
        logger.info(f"Loading units for building: {building_uuid}, survey: {survey_id}")

        def _do_load():
            if survey_id:
                return self.unit_controller.get_units_for_survey(survey_id)
            else:
                return self.unit_controller.get_units_for_building(building_uuid)

        self._spinner.show_loading(tr("component.loading.default"))
        self._load_units_worker = ApiWorker(_do_load)
        self._load_units_worker.finished.connect(
            lambda result: (self._spinner.hide_loading(), self._on_units_loaded(result, building_uuid))
        )
        self._load_units_worker.error.connect(
            lambda msg: (self._spinner.hide_loading(), self._on_units_load_error(msg))
        )
        self._load_units_worker.start()

    def _on_units_loaded(self, result, building_uuid):
        """Handle units loaded from API."""
        if not result.success:
            logger.error(f"Failed to load units: {result.message}")
            self._empty_state.setVisible(True)
            self._scroll_area.setVisible(False)
            return

        all_units = result.data or []
        units = []
        for u in all_units:
            u_building = getattr(u, 'building_id', None)
            if not u_building or u_building == building_uuid or u_building == self.context.building.building_id:
                units.append(u)
            else:
                logger.warning(f"Filtered out unit {u.unit_id} - belongs to building {u_building}, not {building_uuid}")

        logger.info(f"Showing {len(units)} units (of {len(all_units)} returned by API) for building {building_uuid}")

        has_units = len(units) > 0
        self._empty_state.setVisible(not has_units)
        self._scroll_area.setVisible(has_units)

        # Reset card tracking
        self._all_unit_cards = []

        # Auto-select newly created unit BEFORE building grid
        if self._pending_auto_select_uuid and units:
            for unit in units:
                if getattr(unit, 'unit_uuid', None) == self._pending_auto_select_uuid:
                    self.context.unit = unit
                    self.context.is_new_unit = False
                    self.selected_unit = unit
                    logger.info(f"Auto-selected newly created unit: {unit.unit_uuid}")
                    self.emit_validation_changed(True)
                    break
            self._pending_auto_select_uuid = None

        if units:
            # Flat grid — units sorted by floor, then unit number; no floor-group labels.
            # Each card shows its floor_number internally so grouping info isn't lost.
            def _sort_key(u):
                floor = u.floor_number if u.floor_number is not None else 9999
                return (floor, u.unit_number or u.apartment_number or "")

            sorted_units = sorted(units, key=_sort_key)

            cols = 3
            grid_widget = QWidget()
            grid_widget.setStyleSheet("background: transparent;")
            grid = QGridLayout(grid_widget)
            grid.setSpacing(ScreenScale.w(10))
            grid.setContentsMargins(0, 0, 0, 8)
            for col_idx in range(cols):
                grid.setColumnStretch(col_idx, 1)

            for idx, unit in enumerate(sorted_units):
                card = self._create_unit_card(unit)
                self._all_unit_cards.append(card)
                grid.addWidget(card, idx // cols, idx % cols)

            # Only the final row may be partial — fill remaining cells
            remainder = len(sorted_units) % cols
            if remainder > 0:
                last_row = len(sorted_units) // cols
                for col_idx in range(remainder, cols):
                    filler = QWidget()
                    filler.setStyleSheet("background: transparent;")
                    grid.addWidget(filler, last_row, col_idx)

            self.units_layout.addWidget(grid_widget)

        self.units_layout.addStretch()
        self._loaded_building_uuid = building_uuid

    def _on_units_load_error(self, msg):
        """Handle units loading error."""
        logger.error(f"Failed to load units: {msg}")
        self._empty_state.setVisible(True)
        self._scroll_area.setVisible(False)

    def _to_arabic_numerals(self, text: str) -> str:
        """
        Convert English/Latin numerals to Arabic-Indic numerals.

        Args:
            text: Text containing numerals

        Returns:
            Text with Arabic numerals
        """
        arabic_digits = '٠١٢٣٤٥٦٧٨٩'
        english_digits = '0123456789'
        translation_table = str.maketrans(english_digits, arabic_digits)
        return str(text).translate(translation_table)

    def _create_field_label(self, text: str, is_title: bool = True) -> QLabel:
        """
        Create a label with consistent styling.

        Args:
            text: Label text
            is_title: True for title style (like "اختر مقسماً"),
                     False for value style (like subtitle)

        Returns:
            Configured QLabel
        """
        label = QLabel(text)

        if is_title:
            # Title style - center-aligned
            label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE};")
            label.setAlignment(Qt.AlignCenter)
        else:
            # Value style - center-aligned (directly under label)
            label.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE};")
            label.setAlignment(Qt.AlignCenter)

        return label

    # Status → (badge_bg, badge_text_color)
    _STATUS_PALETTE = {
        "vacant":           ("#F0FDF4", "#16A34A"),
        "occupied":         ("#EFF6FF", "#2563EB"),
        "damaged":          ("#FEF2F2", "#DC2626"),
        "under_renovation": ("#FFF7ED", "#EA580C"),
        "uninhabitable":    ("#FEF2F2", "#B91C1C"),
        "locked":           ("#F1F5F9", "#475569"),
    }

    @staticmethod
    def _make_dotted_divider() -> QFrame:
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(
            "QFrame { border: none; border-top: 1px dashed #E2EAF2; background: transparent; }"
        )
        return d

    def _create_unit_card(self, unit) -> QFrame:
        """Uniform labeled tile: each field (رقم المقسم، رقم الطابق، نوع، حالة، مساحة، غرف) as a cell."""
        unit_display_num = unit.unit_number or unit.apartment_number or "?"
        floor_val = str(unit.floor_number) if getattr(unit, 'floor_number', None) is not None else "-"
        is_selected = bool(self.context.unit and self.context.unit.unit_uuid == unit.unit_uuid)

        # ── Card frame ──
        card = QFrame()
        card.setObjectName("unitCard")
        card.setProperty("unit_id", unit.unit_uuid)
        card.setCursor(Qt.PointingHandCursor)
        is_rtl = get_layout_direction() == Qt.RightToLeft
        card.setLayoutDirection(get_layout_direction())
        card.setMinimumHeight(ScreenScale.h(200))
        self._apply_unit_card_style(card, is_selected)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(14)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)

        card.mousePressEvent = lambda ev: (
            self._on_unit_card_clicked(unit)
            if not any(c.underMouse() for c in card.findChildren(QPushButton))
            else None
        )

        layout = QVBoxLayout(card)
        layout.setSpacing(ScreenScale.h(8))
        layout.setContentsMargins(14, 12, 14, 12)

        # ── Values ──
        unit_type_val = get_unit_type_display(unit.unit_type) if unit.unit_type else "-"
        status_key = getattr(unit, 'apartment_status', None)
        status_val = get_unit_status_display(status_key) if status_key is not None else "-"
        rooms_val = str(unit.apartment_number) if unit.apartment_number else "-"
        if unit.area_sqm:
            try:
                area_val = f"{float(unit.area_sqm):.2f} {tr('wizard.unit.area_unit')}"
            except (ValueError, TypeError):
                area_val = "-"
        else:
            area_val = "-"

        # Explicit start-edge alignment using AlignAbsolute so numeric text is
        # never left-stranded in RTL mode (Qt bidi fallback for numbers ignores
        # leading/trailing without AbsoluteAlign).
        cell_align = (
            Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter
            if is_rtl else
            Qt.AlignLeft  | Qt.AlignAbsolute | Qt.AlignVCenter
        )

        def _labeled_cell(label_text: str, value_widget: QWidget) -> QWidget:
            wrap = QWidget()
            wrap.setLayoutDirection(card.layoutDirection())
            wrap.setStyleSheet("background: transparent;")
            vl = QVBoxLayout(wrap)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(3)
            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #94A3B8; background: transparent; border: none;")
            lbl.setAlignment(cell_align)
            if isinstance(value_widget, QLabel):
                value_widget.setAlignment(cell_align)
            vl.addWidget(lbl)
            vl.addWidget(value_widget)
            return wrap

        # ── Top strip: selection checkmark on trailing edge (reserves height so cards stay aligned) ──
        sel_strip = QWidget()
        sel_strip.setLayoutDirection(card.layoutDirection())
        sel_strip.setFixedHeight(ScreenScale.h(18))
        sel_strip.setStyleSheet("background: transparent;")
        strip_layout = QHBoxLayout(sel_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)

        check_label = QLabel("✓")
        check_label.setObjectName("checkLabel")
        check_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_BOLD))
        check_label.setStyleSheet(
            "QLabel { background: #3890DF; color: white;"
            "padding: 1px 7px; border-radius: 9px; border: none; }"
        )
        check_label.setAlignment(Qt.AlignCenter)
        check_label.setVisible(is_selected)

        strip_layout.addStretch(1)
        strip_layout.addWidget(check_label, 0, Qt.AlignVCenter)
        layout.addWidget(sel_strip)

        # ── 3-row × 2-col grid: unit_no/floor — type/status — area/rooms ──
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(ScreenScale.w(10))
        info_grid.setVerticalSpacing(ScreenScale.h(10))
        info_grid.setContentsMargins(0, 0, 0, 0)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)

        # Row 0: Unit number | Floor number
        num_val_lbl = QLabel(str(unit_display_num))
        num_val_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        num_val_lbl.setStyleSheet("color: #0F172A; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.unit.unit_number"), num_val_lbl), 0, 0)

        floor_val_lbl = QLabel(floor_val)
        floor_val_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        floor_val_lbl.setStyleSheet("color: #0F172A; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.unit.floor_number"), floor_val_lbl), 0, 1)

        # Row 1: Type | Status (colored pill)
        type_val_lbl = QLabel(unit_type_val)
        type_val_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        type_val_lbl.setStyleSheet("color: #334155; background: transparent; border: none;")
        type_val_lbl.setWordWrap(True)
        info_grid.addWidget(_labeled_cell(tr("wizard.unit.unit_type"), type_val_lbl), 1, 0)

        badge_bg, badge_fg = self._STATUS_PALETTE.get(
            str(status_key) if status_key is not None else "",
            ("#F1F5F9", "#475569")
        )
        status_badge = QLabel(status_val)
        status_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        status_badge.setStyleSheet(
            f"background-color: {badge_bg}; color: {badge_fg};"
            "padding: 3px 10px; border-radius: 9px; border: none;"
        )
        status_badge.setAlignment(Qt.AlignCenter)
        badge_holder = QWidget()
        badge_holder.setLayoutDirection(card.layoutDirection())
        badge_holder.setStyleSheet("background: transparent;")
        bh = QHBoxLayout(badge_holder)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)
        bh.addWidget(status_badge, 0)
        bh.addStretch(1)
        info_grid.addWidget(_labeled_cell(tr("wizard.unit.unit_status"), badge_holder), 1, 1)

        # Row 2: Area | Rooms
        area_val_lbl = QLabel(area_val)
        area_val_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        area_val_lbl.setStyleSheet("color: #334155; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.unit.unit_area"), area_val_lbl), 2, 0)

        rooms_val_lbl = QLabel(rooms_val)
        rooms_val_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        rooms_val_lbl.setStyleSheet("color: #334155; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.unit.rooms_count"), rooms_val_lbl), 2, 1)

        layout.addLayout(info_grid)

        # ── Description toggle (aligns to leading edge in both RTL and LTR) ──
        desc_text = unit.property_description or ""
        if desc_text.strip():
            layout.addWidget(self._make_dotted_divider())

            desc_body = QLabel(desc_text)
            desc_body.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            desc_body.setStyleSheet("color: #475569; background: transparent; border: none;")
            desc_body.setWordWrap(True)
            desc_body.setAlignment(cell_align)
            desc_body.setVisible(False)

            toggle_btn = QPushButton("▸  " + tr("wizard.unit.unit_description"))
            toggle_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            toggle_text_align = "right" if is_rtl else "left"
            toggle_btn.setStyleSheet(
                "QPushButton { color: #3890DF; background: transparent; border: none;"
                f"text-align: {toggle_text_align}; padding: 0; }}"
                "QPushButton:hover { color: #2563EB; }"
            )
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.clicked.connect(lambda: (
                desc_body.setVisible(not desc_body.isVisible()),
                toggle_btn.setText(
                    ("▾  " if desc_body.isVisible() else "▸  ")
                    + tr("wizard.unit.unit_description")
                ),
            ))

            layout.addWidget(toggle_btn)
            layout.addWidget(desc_body)

        return card

    @staticmethod
    def _apply_unit_card_style(card: QFrame, is_selected: bool):
        if is_selected:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #EBF5FF;
                    border: 2px solid #3890DF;
                    border-radius: 12px;
                }
                QFrame#unitCard QLabel { border: none; background: transparent; }
                QFrame#unitCard QPushButton { background: transparent; border: none; }
            """)
        else:
            card.setStyleSheet("""
                QFrame#unitCard {
                    background-color: #F8FAFF;
                    border: 1px solid #E5EAF6;
                    border-radius: 12px;
                }
                QFrame#unitCard:hover {
                    border-color: rgba(56, 144, 223, 0.55);
                    background-color: #EBF5FF;
                }
                QFrame#unitCard QLabel { border: none; background: transparent; }
                QFrame#unitCard QPushButton { background: transparent; border: none; }
            """)

    def _refresh_unit_card_styles(self):
        """Update selection highlight and checkmark on existing cards without API re-fetch."""
        selected_id = self.context.unit.unit_uuid if self.context.unit else None
        for card in getattr(self, "_all_unit_cards", []):
            if not isinstance(card, QFrame) or card.objectName() != "unitCard":
                continue
            unit_id = card.property("unit_id")
            is_selected = (unit_id == selected_id)
            self._apply_unit_card_style(card, is_selected)
            check_label = card.findChild(QLabel, "checkLabel")
            if check_label:
                check_label.setVisible(is_selected)

    def _on_unit_card_clicked(self, unit):
        """Handle unit card click with toggle functionality."""
        # Toggle functionality: if clicking on already selected unit, deselect it
        if self.context.unit and self.context.unit.unit_uuid == unit.unit_uuid:
            # Deselect the unit
            self.context.unit = None
            self.context.is_new_unit = False
            self.selected_unit = None
            # Update card styles without re-fetching from API
            self._refresh_unit_card_styles()
            # Emit validation changed (no unit selected = invalid)
            self.emit_validation_changed(False)
            logger.info(f"Unit deselected: {unit.unit_id}")
        else:
            # Select the unit
            self.context.unit = unit
            self.context.is_new_unit = False
            self.selected_unit = unit
            # Update card styles without re-fetching from API
            self._refresh_unit_card_styles()
            # Emit validation changed (unit selected = valid)
            self.emit_validation_changed(True)
            logger.info(f"Unit selected: {unit.unit_id}")

    # ── Inline Unit Form ──

    def _show_add_unit_form(self):
        """Show unit creation form in a BottomSheet overlay."""
        form_widget = self._build_unit_form_widget()

        parent = self.window()
        self._unit_sheet = BottomSheet.custom(
            parent,
            tr("wizard.unit_dialog.title_add"),
            form_widget,
            no_buttons=True
        )
        # Hide wizard header save button while the unit form sheet is open
        wizard = self.window()
        if hasattr(wizard, 'save_btn'):
            self._wizard_save_was_visible = wizard.save_btn.isVisible()
            wizard.save_btn.setVisible(False)
        else:
            self._wizard_save_was_visible = False

    def _cancel_inline_unit(self):
        """Close the BottomSheet."""
        if self._unit_sheet:
            self._unit_sheet.close_sheet()
        self._restore_wizard_save_btn()

    def _restore_wizard_save_btn(self):
        """Restore wizard header save button after the unit sheet closes."""
        wizard = self.window()
        if hasattr(wizard, '_sync_header_save_visibility'):
            wizard._sync_header_save_visibility()
        elif hasattr(wizard, 'save_btn') and getattr(self, '_wizard_save_was_visible', False):
            wizard.save_btn.setVisible(True)
        self._wizard_save_was_visible = False

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """Create a spinbox widget with icon arrows."""
        container = QFrame()
        container.setFixedHeight(ScreenScale.h(48))
        container.setStyleSheet("""
            QFrame {
                border: 1.5px solid #D0D7E2;
                border-radius: 10px;
                background-color: #FFFFFF;
            }
        """)
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 8px 14px;
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #2C3E50;
                min-height: 30px;
                selection-background-color: transparent;
                selection-color: #2C3E50;
            }
            QSpinBox:focus { border: none; outline: 0; }
            QSpinBox::up-button, QSpinBox::down-button { width: 0px; border: none; }
        """)
        h.addWidget(spinbox, 1)

        arrow_container = QFrame()
        arrow_container.setFixedWidth(ScreenScale.w(30))
        arrow_container.setStyleSheet("""
            QFrame {
                border: none;
                border-left: 1.5px solid #D0D7E2;
                background: transparent;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }
        """)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)

        up_label = QLabel()
        up_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(20))
        up_label.setAlignment(Qt.AlignCenter)
        up_px = Icon.load_pixmap("^", size=10)
        if up_px and not up_px.isNull():
            up_label.setPixmap(up_px)
        else:
            up_label.setText("^")
            up_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        up_label.setCursor(Qt.PointingHandCursor)
        up_label.mousePressEvent = lambda _: spinbox.stepUp()
        arrow_layout.addWidget(up_label)

        down_label = QLabel()
        down_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(20))
        down_label.setAlignment(Qt.AlignCenter)
        down_px = Icon.load_pixmap("v", size=10)
        if down_px and not down_px.isNull():
            down_label.setPixmap(down_px)
        else:
            down_label.setText("v")
            down_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda _: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        h.addWidget(arrow_container)
        return container

    def _build_unit_form_widget(self) -> QWidget:
        """Build the unit form fields widget for BottomSheet."""
        form = QWidget()
        form.setStyleSheet("background: transparent; QLabel { background: transparent; border: none; }")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        label_style = "color: #64748B; background: transparent; border: none;"
        down_img = str(Config.IMAGES_DIR / "down.png").replace("\\", "/")
        combo_style = FORM_FIELD_STYLE + f"""
            QComboBox::down-arrow {{ image: url({down_img}); width: 12px; height: 12px; }}
        """

        # Row 1: Floor number | Unit number
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        self._if_floor = QSpinBox()
        self._if_floor.setRange(-3, 100)
        self._if_floor.setAlignment(Qt.AlignRight)
        self._if_floor.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._if_floor.setButtonSymbols(QSpinBox.NoButtons)
        floor_widget = self._create_spinbox_with_arrows(self._if_floor)
        row1.addLayout(self._make_bs_field(tr("wizard.unit_dialog.floor_number"), floor_widget, label_style), 1)

        self._if_unit_num = QSpinBox()
        self._if_unit_num.setRange(0, 9999)
        self._if_unit_num.setAlignment(Qt.AlignRight)
        self._if_unit_num.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._if_unit_num.setButtonSymbols(QSpinBox.NoButtons)
        unit_widget = self._create_spinbox_with_arrows(self._if_unit_num)
        row1.addLayout(self._make_bs_field(tr("wizard.unit_dialog.unit_number"), unit_widget, label_style), 1)
        form_layout.addLayout(row1)

        # Row 2: Unit type | Unit status
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        self._if_type = RtlCombo()
        self._if_type.setStyleSheet(combo_style)
        self._if_type.setFixedHeight(ScreenScale.h(48))
        self._if_type.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_type_options():
            self._if_type.addItem(label, code)
        row2.addLayout(self._make_bs_field(tr("wizard.unit_dialog.unit_type"), self._if_type, label_style), 1)

        self._if_status = RtlCombo()
        self._if_status.setStyleSheet(combo_style)
        self._if_status.setFixedHeight(ScreenScale.h(48))
        self._if_status.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_status_options():
            self._if_status.addItem(label, code)
        row2.addLayout(self._make_bs_field(tr("wizard.unit_dialog.unit_status"), self._if_status, label_style), 1)
        form_layout.addLayout(row2)

        # Row 3: Rooms | Area
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        self._if_rooms = QSpinBox()
        self._if_rooms.setRange(0, 20)
        self._if_rooms.setAlignment(Qt.AlignRight)
        self._if_rooms.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self._if_rooms.setButtonSymbols(QSpinBox.NoButtons)
        rooms_widget = self._create_spinbox_with_arrows(self._if_rooms)
        row3.addLayout(self._make_bs_field(tr("wizard.unit_dialog.rooms"), rooms_widget, label_style), 1)

        self._if_area = QLineEdit()
        self._if_area.setPlaceholderText(tr("wizard.unit_dialog.area_placeholder"))
        self._if_area.setFixedHeight(ScreenScale.h(48))
        self._if_area.setStyleSheet(FORM_FIELD_STYLE)
        area_validator = QDoubleValidator(0.0, 999999.99, 2, self._if_area)
        area_validator.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        area_validator.setNotation(QDoubleValidator.StandardNotation)
        self._if_area.setValidator(area_validator)
        row3.addLayout(self._make_bs_field(tr("wizard.unit_dialog.area"), self._if_area, label_style), 1)
        form_layout.addLayout(row3)

        # Description (full width)
        self._if_desc = QTextEdit()
        self._if_desc.setMinimumHeight(ScreenScale.h(90))
        self._if_desc.setMaximumHeight(ScreenScale.h(110))
        self._if_desc.setPlaceholderText(tr("wizard.unit_dialog.description_placeholder"))
        self._if_desc.setStyleSheet(FORM_FIELD_STYLE)
        form_layout.addLayout(self._make_bs_field(tr("wizard.unit_dialog.description"), self._if_desc, label_style))

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(ScreenScale.h(44))
        cancel_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        cancel_btn.setStyleSheet(FOOTER_SECONDARY_STYLE)
        cancel_btn.clicked.connect(self._cancel_inline_unit)
        btn_row.addWidget(cancel_btn, 1)

        save_btn = QPushButton(tr("common.save"))
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedHeight(ScreenScale.h(44))
        save_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        save_btn.setStyleSheet(FOOTER_PRIMARY_STYLE)
        save_btn.clicked.connect(self._save_inline_unit)
        btn_row.addWidget(save_btn, 1)

        form_layout.addLayout(btn_row)

        return form

    def _make_bs_field(self, label_text: str, widget, label_style: str = "") -> QVBoxLayout:
        """Create a labeled form field for the BottomSheet form."""
        col = QVBoxLayout()
        col.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(label_style or "color: #64748B; background: transparent; border: none;")
        col.addWidget(lbl)
        col.addWidget(widget)
        return col

    def _save_inline_unit(self):
        """Validate and save the inline unit form via API."""
        target = self._unit_sheet or self.window() or self
        # Basic validation (mirrors UnitDialog._validate_basic)
        if not self._if_type.currentData():
            Toast.show_toast(target, tr("wizard.unit_dialog.select_type_warning"), Toast.WARNING)
            return
        if self._if_unit_num.value() == 0:
            Toast.show_toast(target, tr("wizard.unit_dialog.enter_number_warning"), Toast.WARNING)
            return
        area_text = self._if_area.text().strip()
        if area_text:
            try:
                float(area_text)
            except ValueError:
                Toast.show_toast(target, tr("wizard.unit_dialog.area_numbers_only"), Toast.WARNING)
                return

        # Set auth token
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._api_service.set_access_token(main_window._api_token)
            self.unit_controller.set_auth_token(main_window._api_token)

        # Check uniqueness then create.
        # Use a single spinner target throughout: the sheet overlay if the
        # sheet is open (so it renders above the backdrop), otherwise the
        # step spinner. The same target is used for the creation call in
        # _do_create_unit so the spinner never appears twice.
        _sheet = self._unit_sheet
        _use_sheet = _sheet is not None and hasattr(_sheet, "show_loading")

        def _hide_check_spinner():
            if _use_sheet and _sheet is not None:
                try:
                    _sheet.hide_loading()
                except Exception:
                    pass
            else:
                self._spinner.hide_loading()

        def _do_fetch():
            return self.unit_controller.get_units_for_building(self.context.building.building_uuid)

        def _on_fetched(result):
            if result.success and result.data:
                unit_number = str(self._if_unit_num.value())
                floor = self._if_floor.value()
                for u in result.data:
                    u_num = getattr(u, 'apartment_number', None) or getattr(u, 'unit_number', None)
                    u_floor = getattr(u, 'floor_number', None)
                    if u_num == unit_number and u_floor == floor:
                        _hide_check_spinner()
                        Toast.show_toast(self._unit_sheet or self, tr("wizard.unit_dialog.number_taken"), Toast.WARNING)
                        return
            self._do_create_unit()

        def _on_fetch_error(msg):
            logger.error(f"Error checking uniqueness: {msg}")
            self._do_create_unit()

        if _use_sheet:
            _sheet.show_loading(tr("component.loading.default"))
        else:
            self._spinner.show_loading(tr("component.loading.default"))
        self._save_worker = ApiWorker(_do_fetch)
        self._save_worker.finished.connect(_on_fetched)
        self._save_worker.error.connect(_on_fetch_error)
        self._save_worker.start()

    def _do_create_unit(self):
        """Create the unit via API after uniqueness check passes."""
        area_text = self._if_area.text().strip()
        area_value = float(area_text) if area_text else None
        unit_data = {
            'unit_uuid': str(uuid.uuid4()),
            'building_id': self.context.building.building_id,
            'building_uuid': self.context.building.building_uuid,
            'unit_type': self._if_type.currentData() or 1,
            'status': self._if_status.currentData() or 1,
            'apartment_status': self._if_status.currentData() or 1,
            'floor_number': self._if_floor.value(),
            'unit_number': str(self._if_unit_num.value()),
            'apartment_number': str(self._if_unit_num.value()),
            'number_of_rooms': self._if_rooms.value(),
            'area_sqm': area_value,
            'property_description': self._if_desc.toPlainText().strip() or None,
        }

        survey_id = self.context.get_data("survey_id")
        if survey_id:
            unit_data['survey_id'] = survey_id

        # Spinner is already shown by _save_inline_unit — do not show again.
        sheet = self._unit_sheet

        try:
            response = self._api_service.create_property_unit(unit_data)
            logger.info("Property unit created successfully via inline form")

            self.context.is_new_unit = True
            self.context.new_unit_data = unit_data

            api_uuid = None
            if response:
                api_uuid = response.get('id') or response.get('unitUuid')
            if api_uuid:
                logger.info(f"Using API-generated unit UUID: {api_uuid}")
                self.context.new_unit_data['unit_uuid'] = api_uuid

            # Close BottomSheet and refresh units list
            if self._unit_sheet:
                self._unit_sheet.close_sheet()
            self._restore_wizard_save_btn()

            # Store UUID for auto-selection after async load completes
            self._pending_auto_select_uuid = api_uuid
            self._loaded_building_uuid = None
            self._load_units()

        except Exception as e:
            logger.error(f"API unit creation failed: {e}")
            target = self._unit_sheet or self.window() or self
            if "409" in str(e):
                Toast.show_toast(target, tr("wizard.unit_dialog.duplicate_unit"), Toast.ERROR)
            else:
                Toast.show_toast(target, str(e), Toast.ERROR)
        finally:
            if sheet is not None and hasattr(sheet, "hide_loading"):
                try:
                    sheet.hide_loading()
                except Exception:
                    pass
            else:
                self._spinner.hide_loading()

    # _make_icon_header is now shared via wizard_styles.make_icon_header

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        self.setLayoutDirection(get_layout_direction())
        if hasattr(self, 'add_unit_btn'):
            self.add_unit_btn.setText(tr("wizard.unit.add_button"))
        if hasattr(self, '_units_header_title'):
            self._units_header_title.setText(tr("wizard.unit.select_title"))
            self._units_header_subtitle.setText(tr("wizard.unit.select_subtitle"))
        if hasattr(self, '_lbl_status'):
            self._lbl_status.setText(tr("wizard.building.status"))
            self._lbl_type.setText(tr("wizard.building.type"))
            self._lbl_units.setText(tr("wizard.building.units_count"))
            self._lbl_parcels.setText(tr("wizard.building.parcels_count"))
            self._lbl_shops.setText(tr("wizard.building.shops_count"))
        # Reload unit cards with new language
        if self.context.building:
            self._loaded_building_uuid = None  # Force re-render with new language
            self._load_units()

    def validate(self) -> StepValidationResult:
        """Validate the step. Linking is performed asynchronously via on_next."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error(tr("wizard.unit.no_building_error"))
            return result

        if not self.selected_unit and not self.context.is_new_unit:
            result.add_error(tr("wizard.unit.select_or_create_error"))
            return result

        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            result.add_error(tr("wizard.unit.no_survey_error"))
            return result

        current_unit_id = None
        if self.selected_unit and self.selected_unit != "new_unit":
            current_unit_id = getattr(self.selected_unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            current_unit_id = self.context.new_unit_data.get('unit_uuid')

        if not survey_id or not current_unit_id:
            result.add_error(tr("wizard.unit.no_survey_or_unit_error"))
            return result

        # Guard: skip if same unit already linked
        if self.context.get_data("unit_linked"):
            previous_unit_id = self.context.get_data("linked_unit_uuid")
            if previous_unit_id == current_unit_id:
                logger.info(f"Unit already linked ({current_unit_id}), skipping")
                return result
            else:
                logger.info(f"Unit changed ({previous_unit_id} -> {current_unit_id}), patching relations")
                cleaned = False
                try:
                    self.context.cleanup_on_unit_change(self._api_service, new_unit_id=current_unit_id)
                    cleaned = True
                except Exception as e:
                    logger.warning(f"API cleanup failed, doing local cleanup: {e}")

                if not cleaned:
                    for person in self.context.persons:
                        person['_relation_id'] = None
                    self.context.relations = []
                    self.context.claims = []
                    self.context.finalize_response = None
                    for key in ("unit_linked", "linked_unit_uuid",
                                "claims_count", "created_claims"):
                        self.context.update_data(key, None)

        # Link unit synchronously — block progression if it fails
        if not self.context.get_data("unit_linked"):
            self._set_auth_token()
            self._spinner.show_loading(tr("component.loading.default"))
            try:
                self._api_service.link_unit_to_survey(survey_id, current_unit_id)
                logger.info(f"Unit {current_unit_id} linked to survey {survey_id}")
                self.context.update_data("unit_linked", True)
                self.context.update_data("linked_unit_uuid", current_unit_id)
            except Exception as e:
                logger.error(f"API link failed: {e}")
                result.add_error(tr("wizard.unit.link_failed"))
                return result
            finally:
                self._spinner.hide_loading()

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "unit_id": self.selected_unit.unit_id if self.selected_unit else None,
            "unit_uuid": self.selected_unit.unit_uuid if self.selected_unit else None,
            "is_new_unit": self.context.is_new_unit,
            "new_unit_data": self.context.new_unit_data
        }

    def populate_data(self):
        """Populate the step with data from context."""
        # Load units for the building
        self._load_units()

        # Restore selected unit if exists
        if self.context.unit:
            self.selected_unit = self.context.unit
            # Emit validation - unit is already selected
            self.emit_validation_changed(True)

    def on_show(self):
        """Called when step is shown."""
        # Set auth token before populate_data (called by super) loads units
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self.unit_controller.set_auth_token(main_window._api_token)

        super().on_show()

    def get_step_title(self) -> str:
        """Get step title."""
        return tr("wizard.unit.step_title")

    def get_step_description(self) -> str:
        """Get step description."""
        return tr("wizard.unit.step_description")
