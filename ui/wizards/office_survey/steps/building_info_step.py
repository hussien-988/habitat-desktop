# -*- coding: utf-8 -*-
"""
Building Info Step - Step 0 of Office Survey Wizard.

Displays selected building data in read-only mode before proceeding with survey.
Building is already set in context.building from BuildingMapDialog selection.
"""

from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from services.display_mappings import get_building_type_display, get_building_status_display
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingInfoStep(BaseStep):
    """
    Step 0: Building Information (Read-Only).

    Shows context.building data as label/value pairs.
    No user input — validation always passes if building exists.
    """

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

    def setup_ui(self):
        layout = self.main_layout
        layout.setContentsMargins(0, 8, 0, 16)
        layout.setSpacing(0)

        # Card
        card = QFrame()
        card.setObjectName("buildingInfoCard")
        card.setStyleSheet("""
            QFrame#buildingInfoCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #EFF6FF;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
                font-size: 18px;
            }
        """)
        icon_label.setText("\U0001f3e2")
        header_row.addWidget(icon_label)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title_label = QLabel(tr("wizard.building.card_title"))
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        subtitle_label = QLabel(tr("wizard.building.subtitle"))
        subtitle_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        header_text.addWidget(title_label)
        header_text.addWidget(subtitle_label)

        header_row.addLayout(header_text)
        header_row.addStretch()
        card_layout.addLayout(header_row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #E1E8ED; border: none; background-color: #E1E8ED;")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        # Fields container (populated in populate_data)
        self._fields_layout = QVBoxLayout()
        self._fields_layout.setSpacing(12)
        card_layout.addLayout(self._fields_layout)

        layout.addWidget(card)
        layout.addStretch()

    def _clear_fields(self):
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_field(self, label: str, value: str):
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        lbl = QLabel(label + ":")
        lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        lbl.setFixedWidth(140)

        val = QLabel(value or "\u2014")
        val.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        val.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        val.setWordWrap(True)

        row.addWidget(lbl)
        row.addWidget(val, 1)
        self._fields_layout.addWidget(row_widget)

    def populate_data(self):
        self._clear_fields()
        b = self.context.building
        if not b:
            return

        building_id = (
            getattr(b, 'building_id_display', None)
            or getattr(b, 'building_id', '')
        )
        self._add_field(tr("wizard.building.code_label"), str(building_id))
        self._add_field(
            tr("wizard.building.type"),
            get_building_type_display(getattr(b, 'building_type', None))
        )
        self._add_field(
            tr("wizard.building.status"),
            get_building_status_display(getattr(b, 'building_status', None))
        )
        self._add_field(
            tr("wizard.building.units_count"),
            str(getattr(b, 'number_of_units', 0) or 0)
        )

        gov  = getattr(b, 'governorate_name_ar', '') or getattr(b, 'governorate_code', '')
        dist = getattr(b, 'district_name_ar', '')    or getattr(b, 'district_code', '')
        sub  = getattr(b, 'subdistrict_name_ar', '') or getattr(b, 'subdistrict_code', '')
        city = getattr(b, 'city_name_ar', '')        or getattr(b, 'city_code', '')
        parts = [p for p in [gov, dist, sub, city] if p]
        if parts:
            self._add_field(tr("wizard.building.location"), " / ".join(parts))

        lat = getattr(b, 'latitude', None)
        lon = getattr(b, 'longitude', None)
        if lat and lon:
            self._add_field(tr("wizard.building.coordinates"), f"{lat:.6f}, {lon:.6f}")

    def validate(self) -> StepValidationResult:
        result = StepValidationResult(is_valid=True, errors=[])
        if not self.context.building:
            result.add_error("لم يتم اختيار البناء")
        return result

    def collect_data(self) -> dict:
        return {}

    def get_name(self) -> str:
        return tr("wizard.step.building_info")
