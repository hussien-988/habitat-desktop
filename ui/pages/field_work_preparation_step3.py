# -*- coding: utf-8 -*-
"""Field work preparation step 3: review assignment before submission."""

from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea
)
from PyQt5.QtCore import Qt

from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.animation_utils import stagger_fade_in
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)

def _get_unit_type_labels():
    return {
        1: tr("wizard.step3.unit_apartment"), 2: tr("wizard.step3.unit_shop"),
        3: tr("wizard.step3.unit_office"), 4: tr("wizard.step3.unit_warehouse"),
        5: tr("wizard.step3.unit_other"),
        "apartment": tr("wizard.step3.unit_apartment"), "shop": tr("wizard.step3.unit_shop"),
        "office": tr("wizard.step3.unit_office"), "warehouse": tr("wizard.step3.unit_warehouse"),
        "garage": tr("wizard.step3.unit_garage"), "other": tr("wizard.step3.unit_other"),
    }


class FieldWorkPreparationStep3(QWidget):
    """Review assignment with buildings, units, and visit type selection."""

    def __init__(self, buildings: list, researcher: dict,
                 revisit_unit_id=None, revisit_building_id=None,
                 parent=None):
        super().__init__(parent)
        self.buildings = buildings or []
        self.researcher = researcher or {}
        self._building_units = {}  # building_id -> list of unit dicts
        self._unit_count_badges = {}  # building_id -> QLabel (units badge in header)
        self._accordion_bodies = {}  # building_id -> QWidget (body)
        self._accordion_arrows = {}  # building_id -> QLabel (arrow)
        self._units_labels = {}  # building_id -> QLabel (units section label)
        self._revisit_unit_id = revisit_unit_id
        self._revisit_building_id = revisit_building_id
        self._revisit_reason_input = None

        # Show a temporary loading layout, fetch units in background
        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._spinner = LoadingSpinnerOverlay(self)
        self._spinner.show_loading(tr("wizard.step3.loading_units"))

        self._units_worker = ApiWorker(self._fetch_units_data, self.buildings)
        self._units_worker.finished.connect(self._on_units_loaded)
        self._units_worker.error.connect(self._on_units_load_error)
        self._units_worker.start()

    def _on_units_loaded(self, building_units):
        """Handle successful unit fetch, then build UI."""
        self._building_units = building_units or {}
        self._spinner.hide_loading()
        self._setup_ui()

    def _on_units_load_error(self, error_msg):
        """Handle failed unit fetch, build UI with empty units."""
        logger.warning(f"Could not fetch property units: {error_msg}")
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("wizard.step3.err_load_summary"), Toast.ERROR)
        self._setup_ui()

    @staticmethod
    def _fetch_units_data(buildings):
        """Fetch property units for each building. Runs in background thread."""
        building_units = {}
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            for building in buildings:
                building_uuid = (
                    getattr(building, 'building_uuid', None)
                    or getattr(building, 'id', None)
                )
                if not building_uuid:
                    continue
                try:
                    units = api.get_assignment_property_units(building_uuid)
                    bid = getattr(building, 'building_id', '') or str(building)
                    building_units[bid] = units if isinstance(units, list) else []
                except Exception as e:
                    logger.debug(f"Could not fetch units for {building_uuid}: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch property units: {e}")
        return building_units

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = self._outer_layout
        outer.setSpacing(0)

        # Page-level scroll — the whole step scrolls, not individual cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(16)
        info_card = QFrame()
        info_card.setStyleSheet(StyleManager.data_card())
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(24, 20, 24, 20)
        info_layout.setSpacing(12)

        self._info_title_label = QLabel(tr("wizard.step3.assignment_info"))
        self._info_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._info_title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        info_layout.addWidget(self._info_title_label)

        researcher_name = (
            self.researcher.get('name')
            or self.researcher.get('display_name')
            or self.researcher.get('id', '')
        )
        available = self.researcher.get('available', True)
        avail_text = tr("wizard.step3.available") if available else tr("wizard.step3.unavailable")
        avail_color = "#10B981" if available else "#EF4444"
        assignment_date = date.today().strftime("%Y-%m-%d")

        self._info_row_labels = []
        self._info_row_values = []
        self._avail_badge = None

        for label_text, value_text, value_color in [
            (tr("wizard.step3.field_researcher"), f"{researcher_name}  \u2014  {avail_text}", avail_color if not available else Colors.PAGE_TITLE),
            (tr("wizard.step3.building_count"), str(len(self.buildings)), Colors.PRIMARY_BLUE),
            (tr("wizard.step3.assignment_date"), assignment_date, Colors.PAGE_TITLE),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #637381; background: transparent; border: none;")
            lbl.setFixedWidth(ScreenScale.w(160))
            row.addWidget(lbl)
            self._info_row_labels.append(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            val.setStyleSheet(f"color: {value_color}; background: transparent; border: none;")
            row.addWidget(val)
            self._info_row_values.append(val)

            if label_text == tr("wizard.step3.field_researcher"):
                badge = QLabel(avail_text)
                badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                badge.setStyleSheet(f"""
                    color: {avail_color};
                    background-color: {'#ECFDF5' if available else '#FEF2F2'};
                    padding: 2px 10px;
                    border-radius: 10px;
                    border: none;
                """)
                row.addWidget(badge)
                self._avail_badge = badge

            row.addStretch()
            info_layout.addLayout(row)

        layout.addWidget(info_card)
        buildings_card = QFrame()
        buildings_card.setStyleSheet(StyleManager.data_card())
        buildings_card_layout = QVBoxLayout(buildings_card)
        buildings_card_layout.setContentsMargins(24, 16, 24, 16)
        buildings_card_layout.setSpacing(6)

        self._buildings_title_label = QLabel(tr("wizard.step3.buildings_and_units"))
        self._buildings_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._buildings_title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        buildings_card_layout.addWidget(self._buildings_title_label)
        buildings_card_layout.addSpacing(6)

        for i, building in enumerate(self.buildings):
            building_id = (
                getattr(building, 'building_id', None)
                or getattr(building, 'id', None)
                or str(building)
            )
            accordion = self._create_accordion_item(i + 1, building, building_id)
            buildings_card_layout.addWidget(accordion)

        layout.addWidget(buildings_card)

        if self._revisit_unit_id:
            reason_card = self._create_revisit_reason_card()
            layout.addWidget(reason_card)

        layout.addStretch()

        scroll.setWidget(scroll_content)
        outer.addWidget(scroll)

        stagger_fade_in([info_card, buildings_card])

    def _create_accordion_item(self, index, building, building_id):
        """Create an accordion item for a building."""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #FAFBFC;
                border: none;
                border-radius: 8px;
            }
            QFrame:hover {
                background-color: #F0F4F8;
            }
        """)
        header.setCursor(Qt.PointingHandCursor)
        header.setFixedHeight(ScreenScale.h(52))

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(12)

        # Arrow
        arrow = QLabel("\u25B6")
        arrow.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        arrow.setStyleSheet("color: #637381; background: transparent; border: none;")
        arrow.setFixedWidth(ScreenScale.w(16))
        self._accordion_arrows[building_id] = arrow
        header_layout.addWidget(arrow)

        # Building icon
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        icon_container.setStyleSheet(
            "QLabel { background-color: #f0f7ff; border-radius: 6px; border: none; }"
        )
        icon_container.setAlignment(Qt.AlignCenter)
        icon_pixmap = Icon.load_pixmap("building-03", size=16)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            icon_container.setText("B")
        header_layout.addWidget(icon_container)

        # Building ID
        display_id = self._format_building_id(building_id)
        id_label = QLabel(f"{index}. {display_id}")
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        id_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        header_layout.addWidget(id_label)

        header_layout.addStretch()

        # All units for this building
        units = self._building_units.get(building_id, [])
        total_count = len(units)

        # Units count badge
        if total_count > 0:
            badge = QLabel(tr("wizard.step3.units_count", count=total_count))
        else:
            num_units = getattr(building, 'number_of_units', 0) or 0
            badge = QLabel(tr("wizard.step3.units_count", count=num_units) if num_units > 0 else "")
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setStyleSheet(f"""
            color: {Colors.PRIMARY_BLUE};
            background-color: #EBF5FF;
            padding: 2px 10px;
            border-radius: 10px;
            border: none;
        """)
        if badge.text():
            header_layout.addWidget(badge)
        self._unit_count_badges[building_id] = badge

        container_layout.addWidget(header)
        body = QWidget()
        body.setStyleSheet("background: transparent; border: none;")
        body.setVisible(False)
        self._accordion_bodies[building_id] = body

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(44, 8, 16, 12)
        body_layout.setSpacing(10)

        # Property units — show all units (read-only)
        if units:
            units_label = QLabel(tr("wizard.step3.units_label"))
            units_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            units_label.setStyleSheet("color: #637381; background: transparent; border: none;")
            body_layout.addWidget(units_label)
            self._units_labels[building_id] = units_label

            for u in units:
                unit_card = self._create_unit_card(u)
                body_layout.addWidget(unit_card)

        container_layout.addWidget(body)

        # Click handler for header
        header.mousePressEvent = lambda event, bid=building_id: self._toggle_accordion(bid)

        return container

    def _create_unit_card(self, unit_data: dict) -> QFrame:
        """Create a read-only unit card with survey status badge."""
        unit_type = unit_data.get('unitType') or unit_data.get('unit_type') or 'other'
        try:
            unit_type = int(unit_type)
        except (ValueError, TypeError):
            pass
        lookup_key = unit_type if isinstance(unit_type, int) else str(unit_type).lower()
        ar_type = _get_unit_type_labels().get(lookup_key, str(unit_type))

        unit_code = unit_data.get('unitCode') or unit_data.get('unit_code') or '-'
        floor = unit_data.get('floorNumber')
        floor_str = str(floor) if floor is not None else '-'
        description = unit_data.get('description') or ''
        person_count = unit_data.get('personCount') or 0
        household_count = unit_data.get('householdCount') or 0
        claim_count = unit_data.get('claimCount') or 0
        has_survey = unit_data.get('hasCompletedSurvey', False)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E8EDF2;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(6)

        # Survey status badge row
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        if has_survey:
            status_badge = QLabel(tr("wizard.step3.survey_done"))
            status_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            status_badge.setStyleSheet("""
                color: #10B981;
                background-color: #ECFDF5;
                padding: 2px 8px;
                border-radius: 8px;
            """)
        else:
            status_badge = QLabel(tr("wizard.step3.survey_not_done"))
            status_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            status_badge.setStyleSheet("""
                color: #F59E0B;
                background-color: #FFFBEB;
                padding: 2px 8px;
                border-radius: 8px;
            """)
        status_row.addWidget(status_badge)
        status_row.addStretch()
        card_layout.addLayout(status_row)

        # Data grid
        grid = QHBoxLayout()
        grid.setSpacing(0)

        data_points = [
            (tr("wizard.step3.unit_code"), unit_code),
            (tr("wizard.step3.floor"), floor_str),
            (tr("wizard.step3.type"), ar_type),
            (tr("wizard.step3.persons"), str(person_count)),
            (tr("wizard.step3.households"), str(household_count)),
            (tr("wizard.step3.claims"), str(claim_count)),
        ]

        for i, (label_text, value_text) in enumerate(data_points):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.setContentsMargins(6, 0, 6, 0)
            col.setAlignment(Qt.AlignCenter)

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            lbl.setStyleSheet("color: #9CA3AF;")
            lbl.setAlignment(Qt.AlignCenter)
            col.addWidget(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            val.setStyleSheet(f"color: {Colors.PAGE_TITLE};")
            val.setAlignment(Qt.AlignCenter)
            col.addWidget(val)

            grid.addLayout(col, stretch=1)

            if i < len(data_points) - 1:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setFixedHeight(ScreenScale.h(28))
                sep.setStyleSheet("background-color: #F0F0F0; border: none;")
                grid.addWidget(sep)

        card_layout.addLayout(grid)

        if description:
            desc = QLabel(description)
            desc.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            desc.setStyleSheet("color: #637381;")
            desc.setWordWrap(True)
            card_layout.addWidget(desc)

        return card

    def _toggle_accordion(self, building_id):
        """Toggle accordion expand/collapse."""
        body = self._accordion_bodies.get(building_id)
        arrow = self._accordion_arrows.get(building_id)
        if body is None:
            return

        is_visible = body.isVisible()
        body.setVisible(not is_visible)

        if arrow:
            arrow.setText("\u25BC" if not is_visible else "\u25B6")

    def _format_building_id(self, building_id: str) -> str:
        """Format building ID with dashes."""
        if not building_id:
            return ""
        if len(building_id) == 17:
            parts = [
                building_id[0:2], building_id[2:4], building_id[4:6],
                building_id[6:8], building_id[8:10], building_id[10:12],
                building_id[12:14], building_id[14:16], building_id[16:17]
            ]
            return "-".join(parts)
        return building_id

    def _create_revisit_reason_card(self) -> QFrame:
        """Create a card with a required reason input for revisit mode."""
        from PyQt5.QtWidgets import QLineEdit
        reason_card = QFrame()
        reason_card.setStyleSheet(StyleManager.data_card())
        reason_layout = QVBoxLayout(reason_card)
        reason_layout.setContentsMargins(24, 16, 24, 16)
        reason_layout.setSpacing(8)

        label = QLabel(tr("wizard.step3.revisit_reason_label") + " *")
        label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        reason_layout.addWidget(label)
        self._revisit_reason_label = label

        self._revisit_reason_input = QLineEdit()
        self._revisit_reason_input.setFont(create_font(size=11))
        self._revisit_reason_input.setFixedHeight(ScreenScale.h(38))
        self._revisit_reason_input.setPlaceholderText(
            tr("wizard.step3.revisit_reason_placeholder")
        )
        self._revisit_reason_input.setStyleSheet("""
            QLineEdit {
                background: #F8FAFC;
                border: 1.5px solid #E2E8F0;
                border-radius: 10px;
                padding: 0 12px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border-color: #3890DF;
            }
        """)
        reason_layout.addWidget(self._revisit_reason_input)
        return reason_card

    def update_language(self, is_arabic: bool = True):
        """Update UI text after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Update info card title
        if hasattr(self, '_info_title_label'):
            self._info_title_label.setText(tr("wizard.step3.assignment_info"))

        # Update info row labels (researcher, building count, date)
        if hasattr(self, '_info_row_labels') and len(self._info_row_labels) >= 3:
            self._info_row_labels[0].setText(tr("wizard.step3.field_researcher"))
            self._info_row_labels[1].setText(tr("wizard.step3.building_count"))
            self._info_row_labels[2].setText(tr("wizard.step3.assignment_date"))

        # Update researcher availability text in value and badge
        if hasattr(self, '_info_row_values') and self._info_row_values:
            available = self.researcher.get('available', True)
            avail_text = tr("wizard.step3.available") if available else tr("wizard.step3.unavailable")
            researcher_name = (
                self.researcher.get('name')
                or self.researcher.get('display_name')
                or self.researcher.get('id', '')
            )
            self._info_row_values[0].setText(f"{researcher_name}  \u2014  {avail_text}")
            if hasattr(self, '_avail_badge') and self._avail_badge:
                self._avail_badge.setText(avail_text)

        # Update buildings card title
        if hasattr(self, '_buildings_title_label'):
            self._buildings_title_label.setText(tr("wizard.step3.buildings_and_units"))

        for building_id in self._units_labels:
            self._units_labels[building_id].setText(tr("wizard.step3.units_label"))

        if hasattr(self, '_revisit_reason_label') and self._revisit_reason_label:
            self._revisit_reason_label.setText(tr("wizard.step3.revisit_reason_label") + " *")
        if hasattr(self, '_revisit_reason_input') and self._revisit_reason_input:
            self._revisit_reason_input.setPlaceholderText(tr("wizard.step3.revisit_reason_placeholder"))

    def validate(self) -> bool:
        if self._revisit_unit_id and self._revisit_reason_input is not None:
            if not self._revisit_reason_input.text().strip():
                Toast.show_toast(self, tr("wizard.step3.revisit_reason_required"), Toast.WARNING)
                return False
        return True

    def get_summary(self) -> dict:
        summary = {
            'buildings': self.buildings,
            'researcher': self.researcher,
        }
        if (self._revisit_unit_id and self._revisit_building_id
                and self._revisit_reason_input is not None):
            reason = self._revisit_reason_input.text().strip()
            if reason:
                summary['revisit_reasons'] = {self._revisit_building_id: reason}
        return summary
