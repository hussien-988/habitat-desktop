# -*- coding: utf-8 -*-
"""
Field Work Preparation - Step 3: Assignment Summary
UC-012: Assign Buildings to Field Teams

Shows a summary of selected buildings with property units and researcher
before final submission. Supports marking buildings for revisit (S03-S05).
"""

from collections import Counter
from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt

from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Unit type Arabic names (fallback if model not available)
_UNIT_TYPE_AR = {
    1: "شقة سكنية", 2: "محل تجاري", 3: "مكتب", 4: "مستودع", 5: "أخرى",
    "apartment": "شقة سكنية", "shop": "محل تجاري", "office": "مكتب",
    "warehouse": "مستودع", "garage": "كراج", "other": "أخرى",
}


class FieldWorkPreparationStep3(QWidget):
    """
    Step 3: Assignment Summary and Confirmation.

    Displays:
    - Selected buildings list with property unit counts (S03)
    - Revisit checkbox per building (S04/S05)
    - Assigned researcher name
    - Assignment date (today)
    """

    def __init__(self, buildings: list, researcher: dict, parent=None):
        super().__init__(parent)
        self.buildings = buildings or []
        self.researcher = researcher or {}
        self._revisit_checkboxes = {}  # building_id → QCheckBox
        self._revisit_reason_inputs = {}  # building_id → QLineEdit
        self._building_units = {}  # building_id → list of unit dicts
        self._fetch_units()
        self._setup_ui()

    def _fetch_units(self):
        """Fetch property units for each building (S03)."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            for building in self.buildings:
                building_uuid = getattr(building, 'building_uuid', None) or getattr(building, 'id', None)
                if not building_uuid:
                    continue
                try:
                    units = api.get_property_units_by_building(building_uuid)
                    bid = getattr(building, 'building_id', '') or str(building)
                    self._building_units[bid] = units if isinstance(units, list) else []
                except Exception as e:
                    logger.debug(f"Could not fetch units for {building_uuid}: {e}")
        except Exception as e:
            logger.warning(f"Could not fetch property units: {e}")

    def _get_unit_summary(self, building_id: str) -> str:
        """Get Arabic summary of unit types for a building."""
        units = self._building_units.get(building_id, [])
        if not units:
            return ""

        type_counts = Counter()
        for u in units:
            unit_type = u.get('unitType') or u.get('unit_type') or 'other'
            try:
                unit_type = int(unit_type)
            except (ValueError, TypeError):
                pass
            ar_name = _UNIT_TYPE_AR.get(unit_type, str(unit_type))
            type_counts[ar_name] += 1

        parts = [f"{count} {name}" for name, count in type_counts.items()]
        total = len(units)
        return f"{total} وحدات: {', '.join(parts)}" if parts else f"{total} وحدات"

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(20)

        # Summary card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(16)

        title = QLabel("ملخص التعيين")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        researcher_name = (
            self.researcher.get('name')
            or self.researcher.get('display_name')
            or self.researcher.get('id', '')
        )
        assignment_date = date.today().strftime("%Y-%m-%d")

        for label_text, value_text in [
            ("عدد المباني المحددة:", str(len(self.buildings))),
            ("الباحث الميداني:", researcher_name),
            ("تاريخ التعيين:", assignment_date),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #637381; background: transparent;")
            lbl.setFixedWidth(200)
            row.addWidget(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
            val.setStyleSheet("color: #212B36; background: transparent;")
            row.addWidget(val)
            row.addStretch()

            card_layout.addLayout(row)

        layout.addWidget(card)

        # Buildings + units card (S03-S05)
        list_card = QFrame()
        list_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(24, 16, 24, 16)
        list_card_layout.setSpacing(8)

        list_title = QLabel("المباني والوحدات العقارية")
        list_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        list_title.setStyleSheet("color: #212B36; background: transparent;")
        list_card_layout.addWidget(list_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setMaximumHeight(400)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_inner = QVBoxLayout(scroll_content)
        scroll_inner.setContentsMargins(0, 0, 0, 0)
        scroll_inner.setSpacing(4)

        for i, building in enumerate(self.buildings, start=1):
            building_id = (
                getattr(building, 'building_id', None)
                or getattr(building, 'id', None)
                or str(building)
            )
            building_row = self._create_building_row(i, building, building_id)
            scroll_inner.addWidget(building_row)

        scroll_inner.addStretch()
        scroll.setWidget(scroll_content)
        list_card_layout.addWidget(scroll)
        layout.addWidget(list_card)

        layout.addStretch()

    def _create_building_row(self, index: int, building, building_id: str) -> QFrame:
        """Create a building row with unit info and revisit checkbox."""
        row_frame = QFrame()
        row_frame.setStyleSheet("""
            QFrame {
                background: transparent;
                border-bottom: 1px solid #F4F6F8;
                border-radius: 0;
            }
        """)

        row_layout = QVBoxLayout(row_frame)
        row_layout.setContentsMargins(4, 8, 4, 8)
        row_layout.setSpacing(4)

        # Building ID line
        display_id = getattr(building, 'building_id_display', building_id) or building_id
        id_label = QLabel(f"{index}. {display_id}")
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        id_label.setStyleSheet("color: #212B36; background: transparent; border: none;")
        row_layout.addWidget(id_label)

        # Unit summary line (S03)
        unit_summary = self._get_unit_summary(building_id)
        if unit_summary:
            unit_label = QLabel(f"    {unit_summary}")
            unit_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            unit_label.setStyleSheet("color: #637381; background: transparent; border: none;")
            row_layout.addWidget(unit_label)
        else:
            num_units = getattr(building, 'number_of_units', 0) or 0
            if num_units > 0:
                unit_label = QLabel(f"    {num_units} وحدات")
                unit_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
                unit_label.setStyleSheet("color: #637381; background: transparent; border: none;")
                row_layout.addWidget(unit_label)

        # Revisit checkbox (S04/S05)
        revisit_row = QHBoxLayout()
        revisit_row.setContentsMargins(4, 2, 0, 0)
        revisit_row.setSpacing(8)

        cb = QCheckBox("يحتاج إعادة زيارة")
        cb.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        cb.setStyleSheet("""
            QCheckBox {
                color: #637381;
                background: transparent;
                border: none;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #C4CDD5;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #3890DF;
                border-color: #3890DF;
            }
        """)
        self._revisit_checkboxes[building_id] = cb
        revisit_row.addWidget(cb)

        reason_input = QLineEdit()
        reason_input.setPlaceholderText("سبب إعادة الزيارة...")
        reason_input.setFixedHeight(28)
        reason_input.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        reason_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFF;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 0 8px;
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

        cb.toggled.connect(lambda checked, ri=reason_input: ri.setVisible(checked))

        revisit_row.addWidget(reason_input, 1)
        revisit_row.addStretch()
        row_layout.addLayout(revisit_row)

        return row_frame

    def get_summary(self) -> dict:
        """Return buildings, researcher, and revisit data for final submission."""
        revisit_buildings = []
        for building_id, cb in self._revisit_checkboxes.items():
            if cb.isChecked():
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
