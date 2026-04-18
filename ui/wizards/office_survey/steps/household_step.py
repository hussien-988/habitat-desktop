# -*- coding: utf-8 -*-
"""
Household Step - Step 3 of Office Survey Wizard.

Allows user to:
- Enter household information
- Record family composition (adults, children, elderly, disabled)
- Add notes about the household
"""

from typing import Dict, Any, Optional
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QScrollArea, QWidget, QGroupBox, QSizePolicy,
    QSpinBox, QTextEdit, QGridLayout, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QLocale, QDate
from PyQt5.QtGui import QColor

from ui.components.rtl_combo import RtlCombo
from ui.style_manager import StyleManager
from ui.components.centered_text_edit import CenteredTextEdit
from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.wizard_styles import (
    STEP_CARD_STYLE, FORM_FIELD_STYLE,
    make_step_card, make_icon_header, make_divider, get_step_card_style,
    make_editable_date_combo, read_int_from_combo,
)
from app.config import Config
from services.api_client import get_api_client
from utils.logger import get_logger
from ui.components.toast import Toast
from ui.design_system import Colors, ScreenScale
from ui.components.icon import Icon
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction, get_language
from services.display_mappings import get_unit_type_display, get_unit_status_display, get_occupancy_nature_options
from services.error_mapper import map_exception
from ui.components.loading_spinner import LoadingSpinnerOverlay

logger = get_logger(__name__)


class HouseholdStep(BaseStep):
    """
    Step 3: Household Information.

    Collects household demographic information including:
    - Head of household
    - Total members
    - Family composition (adults, children, elderly, disabled)
    - Notes
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)

        # Initialize API client for creating households
        self._api_client = get_api_client()

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        widget = self
        layout = self.main_layout
        layout.setContentsMargins(0, 8, 0, 16)
        layout.setSpacing(10)

        # ── Three-column horizontal layout (no scroll) ──
        three_col = QHBoxLayout()
        three_col.setSpacing(ScreenScale.w(14))
        three_col.setContentsMargins(0, 0, 0, 0)

        # ═══ COL 1: Building/Unit summary sidebar ═══
        self.household_building_frame = make_step_card()
        self.household_building_frame.setFixedWidth(ScreenScale.w(290))
        self.household_building_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(self.household_building_frame)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(ScreenScale.h(6))

        # Address row
        self._address_container = QFrame()
        self._address_container.setFixedHeight(ScreenScale.h(32))
        self._address_container.setStyleSheet("""
            QFrame {
                background-color: #F0F4FA;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        address_row = QHBoxLayout(self._address_container)
        address_row.setContentsMargins(10, 0, 10, 0)
        address_row.setSpacing(6)

        address_icon = QLabel()
        address_icon_pixmap = Icon.load_pixmap("dec", size=14)
        if address_icon_pixmap and not address_icon_pixmap.isNull():
            address_icon.setPixmap(address_icon_pixmap)
        else:
            address_icon.setText("📍")
        address_icon.setStyleSheet("background: transparent; border: none;")
        address_row.addWidget(address_icon)

        self.household_building_address = QLabel(tr("wizard.unit.address_label"))
        self.household_building_address.setAlignment(Qt.AlignCenter)
        self.household_building_address.setWordWrap(False)
        self.household_building_address.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        self.household_building_address.setStyleSheet("""
            QLabel { border: none; background-color: transparent; color: #667281; }
        """)
        address_row.addWidget(self.household_building_address, 1)

        card_layout.addWidget(self._address_container)
        card_layout.addSpacing(ScreenScale.h(6))

        # Building stats (vertical)
        self._building_stats_container = QWidget()
        self._building_stats_container.setStyleSheet("background: transparent;")
        _bs_layout = QVBoxLayout(self._building_stats_container)
        _bs_layout.setContentsMargins(0, 0, 0, 0)
        _bs_layout.setSpacing(0)

        _row_type,    self.ui_building_type,   self._lbl_building_type   = self._create_stat_row(tr("wizard.building.type"))
        _row_status,  self.ui_building_status, self._lbl_building_status = self._create_stat_row(tr("wizard.building.status"))
        _row_units,   self.ui_units_count,     self._lbl_units_count     = self._create_stat_row(tr("wizard.building.units_count"))
        _row_parcels, self.ui_parcels_count,   self._lbl_parcels_count   = self._create_stat_row(tr("wizard.building.parcels_count"))
        _row_shops,   self.ui_shops_count,     self._lbl_shops_count     = self._create_stat_row(tr("wizard.building.shops_count"))
        for _w in (_row_type, _row_status, _row_units, _row_parcels, _row_shops):
            _bs_layout.addWidget(_w, 1)
            _bs_layout.addWidget(self._thin_separator())
        card_layout.addWidget(self._building_stats_container, 1)

        card_layout.addSpacing(ScreenScale.h(4))

        # Unit stats (vertical)
        self._unit_info_container = QFrame()
        self._unit_info_container.setStyleSheet("""
            QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }
        """)
        _ui_layout = QVBoxLayout(self._unit_info_container)
        _ui_layout.setContentsMargins(10, 8, 10, 8)
        _ui_layout.setSpacing(0)

        _row_unit_num,   self.ui_unit_number,  self._lbl_unit_number  = self._create_stat_row(tr("wizard.household.unit_number"))
        _row_floor,      self.ui_floor_number, self._lbl_floor_number = self._create_stat_row(tr("wizard.household.floor_number"))
        _row_rooms,      self.ui_rooms_count,  self._lbl_rooms_count  = self._create_stat_row(tr("wizard.household.rooms_count"))
        _row_area,       self.ui_area,         self._lbl_area         = self._create_stat_row(tr("wizard.household.unit_area"))
        _row_unit_type,  self.ui_unit_type,    self._lbl_unit_type    = self._create_stat_row(tr("wizard.household.unit_type_label"))
        _row_unit_stat,  self.ui_unit_status,  self._lbl_unit_status  = self._create_stat_row(tr("wizard.household.unit_status_label"))
        _unit_rows = [_row_unit_num, _row_floor, _row_rooms, _row_area, _row_unit_type, _row_unit_stat]
        for _i, _w in enumerate(_unit_rows):
            _ui_layout.addWidget(_w, 1)
            if _i < len(_unit_rows) - 1:
                _ui_layout.addWidget(self._thin_separator())
        card_layout.addWidget(self._unit_info_container, 1)

        three_col.addWidget(self.household_building_frame, 0)

        # ═══ COL 2: Family Information ═══
        self._family_info_frame = make_step_card()
        self._family_info_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        family_info_layout = QVBoxLayout(self._family_info_frame)
        family_info_layout.setSpacing(12)
        family_info_layout.setContentsMargins(16, 16, 16, 16)

        # Icon header
        header_layout, self._occupants_header_title, self._occupants_header_subtitle = make_icon_header(
            title=tr("wizard.household.occupants_title"),
            subtitle=tr("wizard.household.subtitle"),
            icon_name="user-group",
        )
        
        family_info_layout.addLayout(header_layout)

        # Divider
        family_info_layout.addWidget(make_divider())

        down_img = str(Config.IMAGES_DIR / "down.png").replace("\\", "/")
        combo_style = FORM_FIELD_STYLE + f"""
            QComboBox::down-arrow {{ image: url({down_img}); width: 12px; height: 12px; }}
        """

        # -- Row 1: Occupancy Nature (left) + Total Members (right) --
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        nature_col = QVBoxLayout()
        nature_col.setSpacing(4)
        self._occupancy_nature_label = QLabel(tr("wizard.household.occupancy_nature"))
        self._occupancy_nature_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._occupancy_nature_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        nature_col.addWidget(self._occupancy_nature_label)
        self.hh_occupancy_nature = RtlCombo()
        self.hh_occupancy_nature.addItem(tr("wizard.household.select"), None)
        for code, display_name in get_occupancy_nature_options():
            if code == 0:
                continue
            self.hh_occupancy_nature.addItem(display_name, code)
        self.hh_occupancy_nature.setStyleSheet(combo_style)
        self.hh_occupancy_nature.setMinimumHeight(ScreenScale.h(38))
        nature_col.addWidget(self.hh_occupancy_nature)
        row1.addLayout(nature_col, 1)

        total_members_col = QVBoxLayout()
        total_members_col.setSpacing(4)
        self._total_members_label = QLabel(tr("wizard.household.total_members"))
        self._total_members_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._total_members_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        total_members_col.addWidget(self._total_members_label)
        self.hh_total_members = QSpinBox()
        self.hh_total_members.setRange(0, 50)
        self.hh_total_members.setValue(0)
        self.hh_total_members.setAlignment(Qt.AlignCenter)
        self.hh_total_members.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.hh_total_members.setButtonSymbols(QSpinBox.NoButtons)
        members_widget = self._create_spinbox_with_arrows(self.hh_total_members)
        members_widget.setFixedHeight(ScreenScale.h(45))
        total_members_col.addWidget(members_widget)
        row1.addLayout(total_members_col, 1)

        family_info_layout.addLayout(row1)
        family_info_layout.addSpacing(8)

        # -- Row 2: Occupancy Start Date: day | month | year (editable combos) --
        start_date_col = QVBoxLayout()
        start_date_col.setSpacing(6)
        self._start_date_label = QLabel(tr("wizard.household.occupancy_start_date"))
        self._start_date_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._start_date_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        start_date_col.addWidget(self._start_date_label)

        date_row = QHBoxLayout()
        date_row.setSpacing(6)

        self.hh_start_day = make_editable_date_combo(
            items=[(str(d), d) for d in range(1, 32)],
            max_digits=2, placeholder=tr("wizard.person_dialog.day_placeholder"),
        )
        self.hh_start_month = make_editable_date_combo(
            items=[(str(m), m) for m in range(1, 13)],
            max_digits=2, placeholder=tr("wizard.person_dialog.month_placeholder"),
        )
        self.hh_start_year = make_editable_date_combo(
            items=[(str(y), y) for y in range(QDate.currentDate().year(), 1939, -1)],
            max_digits=4, placeholder=tr("wizard.person_dialog.year_placeholder"),
        )
        date_row.addWidget(self.hh_start_day, 1)
        date_row.addWidget(self.hh_start_month, 1)
        date_row.addWidget(self.hh_start_year, 2)
        start_date_col.addLayout(date_row)
        family_info_layout.addLayout(start_date_col)
        family_info_layout.addSpacing(8)

        notes_field_layout = QVBoxLayout()
        notes_field_layout.setSpacing(4)

        self._notes_label = QLabel(tr("wizard.household.notes_label"))
        self._notes_label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        self._notes_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        notes_field_layout.addWidget(self._notes_label)

        self.hh_notes = CenteredTextEdit()
        self.hh_notes.setPlaceholderText(tr("wizard.household.notes_placeholder"))
        self.hh_notes.setPlaceholderStyleSheet(
            f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; font-size: 10pt;"
        )
        self.hh_notes.setMaximumHeight(ScreenScale.h(80))
        self.hh_notes.setLayoutDirection(get_layout_direction())
        self.hh_notes.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px 12px;
                border: 1.5px solid #D0D7E2;
                border-radius: 8px;
                background-color: #FFFFFF;
                font-size: 10pt;
                color: {Colors.WIZARD_TITLE};
            }}
            QTextEdit:focus {{
                border: 1.5px solid {Colors.PRIMARY_BLUE};
            }}
        """)
        notes_field_layout.addWidget(self.hh_notes)

        family_info_layout.addLayout(notes_field_layout)
        family_info_layout.addStretch(1)

        three_col.addWidget(self._family_info_frame, 1)

        # ═══ COL 3: Composition ═══
        self._composition_frame = make_step_card()
        self._composition_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        composition_layout = QVBoxLayout(self._composition_frame)
        composition_layout.setSpacing(12)
        composition_layout.setContentsMargins(16, 16, 16, 16)

        # Icon header
        comp_header_layout, comp_header_title, comp_header_subtitle = make_icon_header(
            title=tr("wizard.household.composition_title"),
            subtitle=tr("wizard.household.composition_subtitle"),
            icon_name="elements",
        )

        composition_layout.addLayout(comp_header_layout)


        self.hh_composition_header_title = comp_header_title
        self.hh_composition_header_subtitle = comp_header_subtitle
        # Divider
        composition_layout.addWidget(make_divider())

        comp_grid = QGridLayout()
        comp_grid.setHorizontalSpacing(12)
        comp_grid.setVerticalSpacing(8)
        comp_grid.setColumnStretch(0, 1)
        comp_grid.setColumnStretch(1, 1)

        _demo_fields = [
            (0, 0, "wizard.household.males",    "hh_male_count"),
            (0, 1, "wizard.household.females",  "hh_female_count"),
            (1, 0, "wizard.household.adults",   "hh_adult_count"),
            (1, 1, "wizard.household.children", "hh_child_count"),
            (2, 0, "wizard.household.elderly",  "hh_elderly_count"),
            (2, 1, "wizard.household.disabled", "hh_disabled_count"),
        ]
        self._demo_labels = {}

        for _row, _col, _lkey, _attr in _demo_fields:
            _lbl = QLabel(tr(_lkey))
            _lbl.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            _lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
            self._demo_labels[_attr] = (_lbl, _lkey)
            _spin = QSpinBox()
            _spin.setRange(0, 50)
            _spin.setValue(0)
            _spin.setAlignment(Qt.AlignRight)
            _spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
            _spin.setButtonSymbols(QSpinBox.NoButtons)
            setattr(self, _attr, _spin)
            _cell_w = QFrame()
            _cell_w.setStyleSheet("""
                QFrame {
                    background-color: #F8FAFF;
                    border: 1px solid #E8EFF6;
                    border-radius: 10px;
                }
            """)
            _cell_layout = QVBoxLayout(_cell_w)
            _cell_layout.setContentsMargins(10, 8, 10, 8)
            _cell_layout.setSpacing(4)
            _cell_layout.addWidget(_lbl)
            _cell_layout.addWidget(self._create_composition_spinbox(_spin))
            comp_grid.addWidget(_cell_w, _row, _col)

        composition_layout.addLayout(comp_grid)
        composition_layout.addStretch(1)

        three_col.addWidget(self._composition_frame, 1)

        # Apply deeper shadows to cards
        for card in (self.household_building_frame, self._family_info_frame, self._composition_frame):
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(30)
            shadow.setOffset(0, 6)
            shadow.setColor(QColor(0, 0, 0, 28))
            card.setGraphicsEffect(shadow)

        layout.addLayout(three_col, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_stat_row(self, label_text: str, value_text: str = "-"):
        """
        Compact one-line stat row: label on leading edge, value on trailing edge.
        Used inside the narrow sidebar of the three-column household layout.
        """
        row = QWidget()
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hl = QHBoxLayout(row)
        hl.setContentsMargins(2, 4, 2, 4)
        hl.setSpacing(6)

        _is_rtl = get_layout_direction() == Qt.RightToLeft
        _align = (
            Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter
            if _is_rtl else
            Qt.AlignLeft | Qt.AlignAbsolute | Qt.AlignVCenter
        )

        label = QLabel(label_text)
        label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        label.setAlignment(_align)

        value = QLabel(value_text)
        value.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        value.setAlignment(_align)

        hl.addWidget(label, 0, Qt.AlignVCenter)
        hl.addStretch(1)
        hl.addWidget(value, 0, Qt.AlignVCenter)

        return row, value, label

    def _thin_separator(self) -> QFrame:
        s = QFrame()
        s.setFixedHeight(1)
        s.setStyleSheet("background-color: #EDF1F6; border: none;")
        return s

    def _create_stat_section(self, label_text: str, value_text: str = "-"):
        """
        Create a stat section with label on top and value below.

        Same design as unit_selection_step for consistency.

        Args:
            label_text: Label text (e.g., "نوع البناء")
            value_text: Value text (default: "-")

        Returns:
            Tuple of (section_widget, value_label)
        """
        section = QWidget()
        section.setStyleSheet("background: transparent;")

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 0, 8, 0)
        section_layout.setSpacing(4)
        section_layout.setAlignment(Qt.AlignCenter)

        # Label (top)
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Value (bottom) - centered under label
        value = QLabel(value_text)
        value.setAlignment(Qt.AlignCenter)
        value.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        section_layout.addWidget(label)
        section_layout.addWidget(value)

        return section, value, label

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox, bg_color: str = "#F8FAFF") -> QFrame:
        """
        Create a spinbox widget with icon arrows (matching unit_dialog style).

        Args:
            spinbox: QSpinBox to wrap with custom arrows
            bg_color: Background color for the container

        Returns:
            QFrame container with spinbox and arrows
        """
        container = QFrame()
        container.setFixedHeight(ScreenScale.h(45))
        container.setStyleSheet(f"""
            QFrame {{
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: {bg_color};
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Spinbox (no border since container has border)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                padding-right: 35px;
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #606266;
                selection-background-color: transparent;
                selection-color: #606266;
            }
            QSpinBox:focus {
                border: none;
                outline: 0;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)
        layout.addWidget(spinbox, 1)

        # Arrow column (RIGHT side) with left border separator
        arrow_container = QFrame()
        arrow_container.setFixedWidth(ScreenScale.w(30))
        arrow_container.setStyleSheet("""
            QFrame {
                border: none;
                border-left: 1px solid #E1E8ED;
                background: transparent;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)

        # Up arrow icon (^.png)
        up_label = QLabel()
        up_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(22))
        up_label.setAlignment(Qt.AlignCenter)
        up_pixmap = Icon.load_pixmap("^", size=10)
        if up_pixmap and not up_pixmap.isNull():
            up_label.setPixmap(up_pixmap)
        else:
            up_label.setText("^")
            up_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        up_label.setCursor(Qt.PointingHandCursor)
        up_label.mousePressEvent = lambda _: spinbox.stepUp()
        arrow_layout.addWidget(up_label)

        # Down arrow icon (v.png)
        down_label = QLabel()
        down_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(22))
        down_label.setAlignment(Qt.AlignCenter)
        down_pixmap = Icon.load_pixmap("v", size=10)
        if down_pixmap and not down_pixmap.isNull():
            down_label.setPixmap(down_pixmap)
        else:
            down_label.setText("v")
            down_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda _: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        layout.addWidget(arrow_container)

        return container

    def _create_gender_card(self, title: str, fields: list) -> QFrame:
        """
        Create a gender-specific card (Male/Female) with demographic fields.

        Args:
            title: Card title (e.g., "ذكور" or "إناث")
            fields: List of tuples [(label, attribute_name), ...]

        Returns:
            QFrame containing the gender card
        - Height: 340px (fixed)
        - Width: Auto (fill available space with equal stretch)
        - Border-radius: 12px
        - Gap between fields: 12px
        - Background: White
        """
        card = QFrame()
        card.setObjectName(f"{title}Card")
        card.setMinimumHeight(ScreenScale.h(280))
        card.setStyleSheet(f"""
            QFrame#{title}Card {{
                background-color: #F8FAFF;
                border: 1px solid #E2EAF2;
                border-radius: 12px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)  # Gap between fields: 12px
        card_layout.setContentsMargins(12, 12, 12, 12)  # Padding: 12px

        # Card title
        card_title = QLabel(title)
        card_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        card_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(card_title)

        # Create fields using the same spinbox with arrows pattern
        for label_text, attr_name in fields:
            field_layout = QVBoxLayout()
            field_layout.setSpacing(4)

            # Label
            label = QLabel(label_text)
            label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
            field_layout.addWidget(label)

            # SpinBox with custom arrows (white background)
            spinbox = QSpinBox()
            spinbox.setRange(0, 50)
            spinbox.setValue(0)
            spinbox.setAlignment(Qt.AlignRight)
            spinbox.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
            spinbox.setButtonSymbols(QSpinBox.NoButtons)

            # Create container with arrows (white background for inner cards)
            spinbox_widget = self._create_composition_spinbox(spinbox)

            field_layout.addWidget(spinbox_widget)
            card_layout.addLayout(field_layout)

            # Store reference to spinbox for data collection
            setattr(self, attr_name, spinbox)

        return card

    def _create_composition_spinbox(self, spinbox: QSpinBox) -> QFrame:
        """
        Create a spinbox widget with arrows for composition fields.

        Reuses _create_spinbox_with_arrows with WHITE background.
        """
        return self._create_spinbox_with_arrows(spinbox, bg_color="#FFFFFF")

    # _make_icon_header is now shared via wizard_styles.make_icon_header

    def update_language(self, is_arabic: bool):
        """Update layout direction and all labels when language changes."""
        _dir = get_layout_direction()
        self.setLayoutDirection(_dir)

        # Flip direction on all containers
        self.household_building_frame.setLayoutDirection(_dir)
        self._address_container.setLayoutDirection(_dir)
        self._building_stats_container.setLayoutDirection(_dir)
        self._unit_info_container.setLayoutDirection(_dir)
        self._family_info_frame.setLayoutDirection(_dir)
        self._composition_frame.setLayoutDirection(_dir)
        self.hh_notes.setLayoutDirection(_dir)

        # Re-apply step card styles (accent border side depends on RTL)
        self.household_building_frame.setStyleSheet(get_step_card_style())
        self._family_info_frame.setStyleSheet(get_step_card_style())
        self._composition_frame.setStyleSheet(get_step_card_style())

        # Building card stat titles
        self._lbl_building_type.setText(tr("wizard.building.type"))
        self._lbl_building_status.setText(tr("wizard.building.status"))
        self._lbl_units_count.setText(tr("wizard.building.units_count"))
        self._lbl_parcels_count.setText(tr("wizard.building.parcels_count"))
        self._lbl_shops_count.setText(tr("wizard.building.shops_count"))

        # Unit info stat titles
        self._lbl_unit_number.setText(tr("wizard.household.unit_number"))
        self._lbl_floor_number.setText(tr("wizard.household.floor_number"))
        self._lbl_rooms_count.setText(tr("wizard.household.rooms_count"))
        self._lbl_area.setText(tr("wizard.household.unit_area"))
        self._lbl_unit_type.setText(tr("wizard.household.unit_type_label"))
        self._lbl_unit_status.setText(tr("wizard.household.unit_status_label"))

        # Re-apply direction-aware alignment to sidebar stat rows
        _align = (
            Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter
            if _dir == Qt.RightToLeft else
            Qt.AlignLeft | Qt.AlignAbsolute | Qt.AlignVCenter
        )
        for _pair in (
            (self._lbl_building_type, self.ui_building_type),
            (self._lbl_building_status, self.ui_building_status),
            (self._lbl_units_count, self.ui_units_count),
            (self._lbl_parcels_count, self.ui_parcels_count),
            (self._lbl_shops_count, self.ui_shops_count),
            (self._lbl_unit_number, self.ui_unit_number),
            (self._lbl_floor_number, self.ui_floor_number),
            (self._lbl_rooms_count, self.ui_rooms_count),
            (self._lbl_area, self.ui_area),
            (self._lbl_unit_type, self.ui_unit_type),
            (self._lbl_unit_status, self.ui_unit_status),
        ):
            for _w in _pair:
                _w.setAlignment(_align)

        self._occupants_header_title.setText(tr("wizard.household.occupants_title"))
        self._occupants_header_subtitle.setText(tr("wizard.household.subtitle"))
        self.hh_composition_header_title.setText(tr("wizard.household.composition_title"))
        self.hh_composition_header_subtitle.setText(tr("wizard.household.composition_subtitle"))
        self._occupancy_nature_label.setText(tr("wizard.household.occupancy_nature"))
        self._total_members_label.setText(tr("wizard.household.total_members"))
        self._start_date_label.setText(tr("wizard.household.occupancy_start_date"))
        self._notes_label.setText(tr("wizard.household.notes_label"))
        self.hh_notes.setPlaceholderText(tr("wizard.household.notes_placeholder"))

        for _attr, (_lbl, _key) in self._demo_labels.items():
            _lbl.setText(tr(_key))

        _cur_nature = self.hh_occupancy_nature.currentData()
        self.hh_occupancy_nature.clear()
        self.hh_occupancy_nature.addItem(tr("wizard.household.select"), None)
        for code, display_name in get_occupancy_nature_options():
            if code == 0:
                continue
            self.hh_occupancy_nature.addItem(display_name, code)
        if _cur_nature is not None:
            _idx = self.hh_occupancy_nature.findData(_cur_nature)
            if _idx >= 0:
                self.hh_occupancy_nature.setCurrentIndex(_idx)

        # Refresh placeholders for editable date combos after language change
        for _combo, _ph_key in (
            (self.hh_start_day,   "wizard.person_dialog.day_placeholder"),
            (self.hh_start_month, "wizard.person_dialog.month_placeholder"),
            (self.hh_start_year,  "wizard.person_dialog.year_placeholder"),
        ):
            _le = _combo.lineEdit()
            if _le:
                _le.setPlaceholderText(tr(_ph_key))

    def validate(self) -> StepValidationResult:
        """Validate the step and save household data automatically."""
        result = self.create_validation_result()

        # Auto-save household data when clicking "Next"
        property_unit_id = None
        if self.context.unit:
            property_unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            property_unit_id = self.context.new_unit_data.get('unit_uuid')

        # Validate: total members must be > 0
        total_entered = self.hh_total_members.value()
        if total_entered <= 0:
            result.add_error(tr("wizard.household.members_required"))
            return result

        # Validate: gender sum <= householdSize
        gender_sum = self.hh_male_count.value() + self.hh_female_count.value()
        if gender_sum > total_entered:
            result.add_error(tr("wizard.household.gender_exceeds_total"))
            return result

        # Validate: age sum <= householdSize
        age_sum = self.hh_adult_count.value() + self.hh_child_count.value() + self.hh_elderly_count.value()
        if age_sum > total_entered:
            result.add_error(tr("wizard.household.age_exceeds_total"))
            return result

        # Validate: disabled count must not exceed total members
        if self.hh_disabled_count.value() > total_entered:
            result.add_error(tr("wizard.household.disability_exceeds_total"))
            return result

        _y = read_int_from_combo(self.hh_start_year)
        _m = read_int_from_combo(self.hh_start_month)
        _d = read_int_from_combo(self.hh_start_day)
        occupancy_start_date = None
        if _y and _m and _d:
            occupancy_start_date = f"{_y:04d}-{_m:02d}-{_d:02d}"
        elif _y and _m:
            occupancy_start_date = f"{_y:04d}-{_m:02d}-01"
        elif _y:
            occupancy_start_date = f"{_y:04d}-01-01"

        household = {
            "household_id": str(uuid.uuid4()),
            "property_unit_id": property_unit_id,
            "unit_uuid": property_unit_id,
            "occupancy_nature": self.hh_occupancy_nature.currentData(),
            "occupancy_start_date": occupancy_start_date,
            "size": self.hh_total_members.value(),
            "male_count": self.hh_male_count.value(),
            "female_count": self.hh_female_count.value(),
            "adult_count": self.hh_adult_count.value(),
            "child_count": self.hh_child_count.value(),
            "elderly_count": self.hh_elderly_count.value(),
            "disabled_count": self.hh_disabled_count.value(),
            "notes": self.hh_notes.toPlainText().strip()
        }

        # Save household data
        existing_household_id = self.context.get_data("household_id")
        survey_id = self.context.get_data("survey_id")
        saved = False

        self._set_auth_token()
        self._spinner.show_loading(tr("component.loading.default"))

        try:
            if existing_household_id:
                stored = self.context.households[0] if self.context.households else {}
                if self._household_data_changed(household, stored):
                    try:
                        self._api_client.update_household(existing_household_id, household, survey_id=survey_id)
                        logger.info(f"Household {existing_household_id} updated via API")
                        saved = True
                    except Exception as e:
                        logger.error(f"Failed to update household via API: {e}")
                        Toast.show_toast(self, tr("wizard.household.load_failed"), Toast.ERROR)
                        result.add_error(tr("wizard.household.update_failed"))
                        return result
                else:
                    logger.info(f"Household unchanged ({existing_household_id}), skipping")
                    saved = True
                household["api_id"] = existing_household_id
            else:
                logger.info(f"Creating household via API: property_unit_id={property_unit_id}, survey_id={survey_id}, size={household['size']}")
                try:
                    api_response = self._api_client.create_household(household, survey_id=survey_id)
                    logger.info("Household created successfully via API")
                    household_id = api_response.get("id") or api_response.get("householdId", "")
                    household["api_id"] = household_id
                    self.context.update_data("household_id", household_id)
                    saved = True
                except Exception as e:
                    logger.error(f"Failed to create household via API: {e}")
                    Toast.show_toast(self, tr("wizard.household.load_failed"), Toast.ERROR)
                    result.add_error(tr("wizard.household.save_failed"))
                    return result
        finally:
            self._spinner.hide_loading()

        if self.context.households:
            self.context.households[0] = household
        else:
            self.context.households.append(household)

        return result

    def _household_data_changed(self, current: Dict, stored: Dict) -> bool:
        """Compare current form data with stored household to detect changes."""
        compare_keys = [
            "property_unit_id",
            "size", "occupancy_nature", "occupancy_start_date",
            "male_count", "female_count",
            "adult_count", "child_count", "elderly_count",
            "disabled_count", "notes"
        ]
        for key in compare_keys:
            if current.get(key) != stored.get(key):
                return True
        return False

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "households": self.context.households,
            "households_count": len(self.context.households)
        }

    def reset(self):
        """Clear all household form fields for a new wizard session."""
        if not self._is_initialized:
            return
        for spin in [self.hh_total_members, self.hh_male_count, self.hh_female_count,
                     self.hh_adult_count, self.hh_child_count,
                     self.hh_elderly_count, self.hh_disabled_count]:
            spin.setValue(0)
        self.hh_occupancy_nature.setCurrentIndex(0)
        for _combo in (self.hh_start_day, self.hh_start_month, self.hh_start_year):
            _combo.setCurrentIndex(-1)
            _combo.clearEditText()
        self.hh_notes.clear()

    def populate_data(self):
        """Populate the step with data from context."""
        # Update building address and stats
        if self.context.building:
            from utils.helpers import build_hierarchical_address
            address = build_hierarchical_address(self.context.building)
            self.household_building_address.setText(address)

            # Update building stats - same as unit_selection_step
            building = self.context.building

            # Use display properties directly (they return Arabic text)
            self.ui_building_type.setText(building.building_type_display or "-")
            self.ui_building_status.setText(building.building_status_display or "-")
            self.ui_units_count.setText(str(getattr(building, 'number_of_apartments', 0) + (building.number_of_shops or 0)))
            self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
            self.ui_shops_count.setText(str(building.number_of_shops or 0))

        # Update unit information (Row 3) - use centralized display_mappings
        # Get unit data from context
        if self.context.unit:
            unit = self.context.unit
            unit_type_display = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else get_unit_type_display(getattr(unit, 'unit_type', None))
            unit_status_raw = getattr(unit, 'apartment_status', None)
            unit_status_display = get_unit_status_display(unit_status_raw) if unit_status_raw else "-"

            floor_number = getattr(unit, 'floor_number', None)
            unit_number = getattr(unit, 'unit_number', None) or getattr(unit, 'apartment_number', None)
            rooms_count = getattr(unit, 'apartment_number', None)
            area = getattr(unit, 'area_sqm', None)
        elif self.context.new_unit_data:
            unit_type_raw = self.context.new_unit_data.get('unit_type')
            unit_type_display = get_unit_type_display(unit_type_raw) if unit_type_raw else "-"

            unit_status_raw = self.context.new_unit_data.get('apartment_status')
            unit_status_display = get_unit_status_display(unit_status_raw) if unit_status_raw else "-"

            floor_number = self.context.new_unit_data.get('floor_number')
            unit_number = self.context.new_unit_data.get('unit_number')
            rooms_count = self.context.new_unit_data.get('number_of_rooms')
            area = self.context.new_unit_data.get('area_sqm')
        else:
            unit_type_display = unit_status_display = "-"
            floor_number = unit_number = rooms_count = area = None

        # Update unit info labels
        self.ui_unit_type.setText(unit_type_display)
        self.ui_unit_status.setText(unit_status_display)
        self.ui_floor_number.setText(str(floor_number) if floor_number is not None else "-")
        self.ui_unit_number.setText(str(unit_number) if unit_number else "-")
        self.ui_rooms_count.setText(str(rooms_count) if rooms_count is not None else "-")
        # Format area with 2 decimal places
        if area:
            try:
                area_formatted = f"{float(area):.2f} m²"
                self.ui_area.setText(area_formatted)
            except (ValueError, TypeError):
                self.ui_area.setText("-")
        else:
            self.ui_area.setText("-")

        # Load existing household data if available
        if len(self.context.households) > 0:
            household = self.context.households[0]
            # Head of household name
            # Restore occupancy combos
            if household.get('occupancy_nature') is not None:
                idx = self.hh_occupancy_nature.findData(household['occupancy_nature'])
                if idx >= 0:
                    self.hh_occupancy_nature.setCurrentIndex(idx)

            saved_date = household.get('occupancy_start_date')
            if saved_date:
                _parts = str(saved_date)[:10].split('-')
                if len(_parts) >= 1 and _parts[0].isdigit():
                    _idx = self.hh_start_year.findData(int(_parts[0]))
                    if _idx >= 0:
                        self.hh_start_year.setCurrentIndex(_idx)
                    else:
                        self.hh_start_year.setCurrentText(_parts[0])
                if len(_parts) >= 2 and _parts[1].isdigit():
                    _idx = self.hh_start_month.findData(int(_parts[1]))
                    if _idx >= 0:
                        self.hh_start_month.setCurrentIndex(_idx)
                    else:
                        self.hh_start_month.setCurrentText(_parts[1].lstrip('0') or '0')
                if len(_parts) >= 3 and _parts[2].isdigit():
                    _idx = self.hh_start_day.findData(int(_parts[2]))
                    if _idx >= 0:
                        self.hh_start_day.setCurrentIndex(_idx)
                    else:
                        self.hh_start_day.setCurrentText(_parts[2].lstrip('0') or '0')

            self.hh_total_members.setValue(int(household.get("size") or 0))
            self.hh_male_count.setValue(int(household.get("male_count") or 0))
            self.hh_female_count.setValue(int(household.get("female_count") or 0))
            self.hh_adult_count.setValue(int(household.get("adult_count") or 0))
            self.hh_child_count.setValue(int(household.get("child_count") or 0))
            self.hh_elderly_count.setValue(int(household.get("elderly_count") or 0))
            self.hh_disabled_count.setValue(int(household.get("disabled_count") or 0))
            self.hh_notes.setPlainText(household.get("notes", ""))
        else:
            self.hh_total_members.setValue(0)
            self.hh_male_count.setValue(0)
            self.hh_female_count.setValue(0)
            self.hh_adult_count.setValue(0)
            self.hh_child_count.setValue(0)
            self.hh_elderly_count.setValue(0)
            self.hh_disabled_count.setValue(0)
            self.hh_notes.clear()

    def get_step_title(self) -> str:
        """Get step title."""
        return tr("wizard.household.step_title")

    def get_step_description(self) -> str:
        """Get step description."""
        return tr("wizard.household.step_description")
