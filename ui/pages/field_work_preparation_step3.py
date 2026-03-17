# -*- coding: utf-8 -*-
"""Field work preparation step 3: review assignment before submission."""

from collections import Counter
from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QRadioButton, QLineEdit, QButtonGroup
)
from PyQt5.QtCore import Qt

from ui.components.icon import Icon
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)

_UNIT_TYPE_AR = {
    1: "شقة سكنية", 2: "محل تجاري", 3: "مكتب", 4: "مستودع", 5: "أخرى",
    "apartment": "شقة سكنية", "shop": "محل تجاري", "office": "مكتب",
    "warehouse": "مستودع", "garage": "كراج", "other": "أخرى",
}


class FieldWorkPreparationStep3(QWidget):
    """Review assignment with buildings, units, and visit type selection."""

    def __init__(self, buildings: list, researcher: dict, parent=None):
        super().__init__(parent)
        self.buildings = buildings or []
        self.researcher = researcher or {}
        self._building_units = {}  # building_id → list of unit dicts
        self._visit_type_groups = {}  # building_id → QButtonGroup
        self._revisit_reason_inputs = {}  # building_id → QLineEdit
        self._accordion_bodies = {}  # building_id → QWidget (body)
        self._accordion_arrows = {}  # building_id → QLabel (arrow)
        self._fetch_units()
        self._setup_ui()

    def _fetch_units(self):
        """Fetch property units for each building."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            for building in self.buildings:
                building_uuid = (
                    getattr(building, 'building_uuid', None)
                    or getattr(building, 'id', None)
                )
                if not building_uuid:
                    continue
                try:
                    units = api.get_assignment_property_units(building_uuid)
                    bid = getattr(building, 'building_id', '') or str(building)
                    self._building_units[bid] = units if isinstance(units, list) else []
                except Exception as e:
                    logger.debug(f"Could not fetch units for {building_uuid}: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch property units: {e}")

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
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
        info_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(24, 20, 24, 20)
        info_layout.setSpacing(12)

        title = QLabel("معلومات التعيين")
        title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent; border: none;")
        info_layout.addWidget(title)

        researcher_name = (
            self.researcher.get('name')
            or self.researcher.get('display_name')
            or self.researcher.get('id', '')
        )
        available = self.researcher.get('available', True)
        avail_text = "متوفر" if available else "غير متوفر"
        avail_color = "#10B981" if available else "#EF4444"
        assignment_date = date.today().strftime("%Y-%m-%d")

        for label_text, value_text, value_color in [
            ("الباحث الميداني:", f"{researcher_name}  —  {avail_text}", avail_color if not available else "#212B36"),
            ("عدد المباني:", str(len(self.buildings)), "#3890DF"),
            ("تاريخ التعيين:", assignment_date, "#212B36"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #637381; background: transparent; border: none;")
            lbl.setFixedWidth(160)
            row.addWidget(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            val.setStyleSheet(f"color: {value_color}; background: transparent; border: none;")
            row.addWidget(val)

            if label_text == "الباحث الميداني:":
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

            row.addStretch()
            info_layout.addLayout(row)

        layout.addWidget(info_card)
        buildings_card = QFrame()
        buildings_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        buildings_card_layout = QVBoxLayout(buildings_card)
        buildings_card_layout.setContentsMargins(24, 16, 24, 16)
        buildings_card_layout.setSpacing(6)

        list_title = QLabel("المباني والمقاسم")
        list_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        list_title.setStyleSheet("color: #212B36; background: transparent; border: none;")
        buildings_card_layout.addWidget(list_title)
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
        layout.addStretch()

        scroll.setWidget(scroll_content)
        outer.addWidget(scroll)

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
        header.setFixedHeight(52)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(12)

        # Arrow
        arrow = QLabel("\u25B6")
        arrow.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        arrow.setStyleSheet("color: #637381; background: transparent; border: none;")
        arrow.setFixedWidth(16)
        self._accordion_arrows[building_id] = arrow
        header_layout.addWidget(arrow)

        # Building icon
        icon_container = QLabel()
        icon_container.setFixedSize(28, 28)
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
        id_label.setStyleSheet("color: #212B36; background: transparent; border: none;")
        header_layout.addWidget(id_label)

        header_layout.addStretch()

        # Units count badge
        units = self._building_units.get(building_id, [])
        units_count = len(units)
        if units_count > 0:
            badge = QLabel(f"{units_count} مقاسم")
            badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            badge.setStyleSheet("""
                color: #3890DF;
                background-color: #EBF5FF;
                padding: 2px 10px;
                border-radius: 10px;
                border: none;
            """)
            header_layout.addWidget(badge)
        else:
            num_units = getattr(building, 'number_of_units', 0) or 0
            if num_units > 0:
                badge = QLabel(f"{num_units} مقاسم")
                badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
                badge.setStyleSheet("""
                    color: #3890DF;
                    background-color: #EBF5FF;
                    padding: 2px 10px;
                    border-radius: 10px;
                    border: none;
                """)
                header_layout.addWidget(badge)

        container_layout.addWidget(header)
        body = QWidget()
        body.setStyleSheet("background: transparent; border: none;")
        body.setVisible(False)
        self._accordion_bodies[building_id] = body

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(44, 8, 16, 12)
        body_layout.setSpacing(10)

        # Visit type radio buttons
        visit_frame = QFrame()
        visit_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: 1px solid #E8EDF2;
                border-radius: 8px;
            }
        """)
        visit_layout = QVBoxLayout(visit_frame)
        visit_layout.setContentsMargins(12, 10, 12, 10)
        visit_layout.setSpacing(8)

        visit_label = QLabel("نوع الزيارة:")
        visit_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        visit_label.setStyleSheet("color: #637381; background: transparent; border: none;")
        visit_layout.addWidget(visit_label)

        radio_row = QHBoxLayout()
        radio_row.setSpacing(24)

        radio_style = """
            QRadioButton {
                color: #212B36;
                font-size: 10pt;
                spacing: 6px;
                background: transparent;
                border: none;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #C4CDD5;
                border-radius: 8px;
                background: white;
            }
            QRadioButton::indicator:hover {
                border-color: #3890DF;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #3890DF;
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.35,
                    fx:0.5, fy:0.5,
                    stop:0 #3890DF, stop:0.6 #3890DF, stop:0.7 white
                );
            }
        """

        btn_group = QButtonGroup(self)
        self._visit_type_groups[building_id] = btn_group

        first_visit_radio = QRadioButton("زيارة أولى")
        first_visit_radio.setStyleSheet(radio_style)
        first_visit_radio.setChecked(True)
        btn_group.addButton(first_visit_radio, 0)
        radio_row.addWidget(first_visit_radio)

        revisit_radio = QRadioButton("إعادة زيارة")
        revisit_radio.setStyleSheet(radio_style)
        btn_group.addButton(revisit_radio, 1)
        radio_row.addWidget(revisit_radio)

        radio_row.addStretch()
        visit_layout.addLayout(radio_row)

        # Reason input (visible only when revisit is selected)
        reason_input = QLineEdit()
        reason_input.setPlaceholderText("سبب إعادة الزيارة...")
        reason_input.setFixedHeight(32)
        reason_input.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        reason_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 0 10px;
                color: #2C3E50;
            }
            QLineEdit:focus {
                border: 1px solid #3890DF;
            }
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)
        reason_input.setVisible(False)
        self._revisit_reason_inputs[building_id] = reason_input

        revisit_radio.toggled.connect(
            lambda checked, ri=reason_input: ri.setVisible(checked)
        )

        visit_layout.addWidget(reason_input)
        body_layout.addWidget(visit_frame)

        # Property units cards
        if units:
            units_label = QLabel("المقاسم:")
            units_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            units_label.setStyleSheet("color: #637381; background: transparent; border: none;")
            body_layout.addWidget(units_label)

            for u in units:
                unit_card = self._create_unit_card(u)
                body_layout.addWidget(unit_card)

        container_layout.addWidget(body)

        # Click handler for header
        header.mousePressEvent = lambda event, bid=building_id: self._toggle_accordion(bid)

        return container

    def _create_unit_card(self, unit_data: dict) -> QFrame:
        """Create a compact unit card displaying key property unit data."""
        unit_type = unit_data.get('unitType') or unit_data.get('unit_type') or 'other'
        try:
            unit_type = int(unit_type)
        except (ValueError, TypeError):
            pass
        lookup_key = unit_type if isinstance(unit_type, int) else str(unit_type).lower()
        ar_type = _UNIT_TYPE_AR.get(lookup_key, str(unit_type))

        unit_code = unit_data.get('unitCode') or unit_data.get('unit_code') or '-'
        floor = unit_data.get('floorNumber')
        floor_str = str(floor) if floor is not None else '-'
        description = unit_data.get('description') or ''
        has_survey = unit_data.get('hasCompletedSurvey', False)
        person_count = unit_data.get('personCount') or 0
        household_count = unit_data.get('householdCount') or 0
        claim_count = unit_data.get('claimCount') or 0

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
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        # Top row: data grid
        grid = QHBoxLayout()
        grid.setSpacing(0)

        data_points = [
            ("رمز الوحدة", unit_code),
            ("الطابق", floor_str),
            ("النوع", ar_type),
            ("الأفراد", str(person_count)),
            ("الأسر", str(household_count)),
            ("المطالبات", str(claim_count)),
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
            val.setStyleSheet("color: #212B36;")
            val.setAlignment(Qt.AlignCenter)
            col.addWidget(val)

            grid.addLayout(col, stretch=1)

            # Vertical separator between columns (except last)
            if i < len(data_points) - 1:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setFixedHeight(28)
                sep.setStyleSheet("background-color: #F0F0F0; border: none;")
                grid.addWidget(sep)

        card_layout.addLayout(grid)

        # Bottom row: description + survey badge
        if description or has_survey is not None:
            bottom = QHBoxLayout()
            bottom.setSpacing(8)

            if description:
                desc = QLabel(description)
                desc.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
                desc.setStyleSheet("color: #637381;")
                desc.setWordWrap(True)
                bottom.addWidget(desc)

            bottom.addStretch()

            if has_survey:
                survey_badge = QLabel("تم المسح")
                survey_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
                survey_badge.setStyleSheet("""
                    color: #10B981;
                    background-color: #ECFDF5;
                    padding: 1px 8px;
                    border-radius: 8px;
                """)
                bottom.addWidget(survey_badge)
            else:
                survey_badge = QLabel("لم يتم المسح")
                survey_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
                survey_badge.setStyleSheet("""
                    color: #9CA3AF;
                    background-color: #F3F4F6;
                    padding: 1px 8px;
                    border-radius: 8px;
                """)
                bottom.addWidget(survey_badge)

            card_layout.addLayout(bottom)

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

    def get_summary(self) -> dict:
        """Return buildings, researcher, and revisit data for final submission."""
        revisit_buildings = []
        for building_id, btn_group in self._visit_type_groups.items():
            if btn_group.checkedId() == 1:  # revisit
                reason = self._revisit_reason_inputs.get(building_id)
                revisit_buildings.append({
                    'building_id': building_id,
                    'reason': reason.text().strip() if reason else '',
                })

        return {
            'buildings': self.buildings,
            'researcher': self.researcher,
            'revisit_buildings': revisit_buildings,
        }
