# -*- coding: utf-8 -*-
"""
Field Work Preparation - Step 3: Assignment Summary
UC-012: Assign Buildings to Field Teams

Shows a summary of selected buildings and researcher before final submission.
"""

from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt

from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class FieldWorkPreparationStep3(QWidget):
    """
    Step 3: Assignment Summary and Confirmation.

    Displays:
    - Selected buildings list (building_id / address)
    - Assigned researcher name
    - Assignment date (today)
    """

    def __init__(self, buildings: list, researcher: dict, parent=None):
        super().__init__(parent)
        self.buildings = buildings or []
        self.researcher = researcher or {}
        self._setup_ui()

    def _setup_ui(self):
        from ui.design_system import Colors

        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(20)

        # ── Summary card ──────────────────────────────────────────────
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

        # Title
        title = QLabel("ملخص التعيين")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Info rows
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

        # ── Buildings list ────────────────────────────────────────────
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

        list_title = QLabel("المباني المحددة")
        list_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        list_title.setStyleSheet("color: #212B36; background: transparent;")
        list_card_layout.addWidget(list_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.setMaximumHeight(300)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                font-size: 10pt;
                color: #212B36;
            }
            QListWidget::item {
                padding: 6px 4px;
                border-bottom: 1px solid #F4F6F8;
            }
        """)
        list_widget.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))

        for i, building in enumerate(self.buildings, start=1):
            building_id = (
                getattr(building, 'building_id', None)
                or getattr(building, 'id', None)
                or str(building)
            )
            address = getattr(building, 'address', '') or ''
            display = f"{i}. {building_id}"
            if address:
                display += f"  —  {address}"
            list_widget.addItem(display)

        scroll.setWidget(list_widget)
        list_card_layout.addWidget(scroll)
        layout.addWidget(list_card)

        layout.addStretch()

    def get_summary(self) -> dict:
        """Return buildings and researcher for final submission."""
        return {
            'buildings': self.buildings,
            'researcher': self.researcher,
        }
