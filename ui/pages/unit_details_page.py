# -*- coding: utf-8 -*-
"""Unit details view page with DarkHeaderZone."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from repositories.database import Database
from repositories.unit_repository import UnitRepository
from models.unit import PropertyUnit
from services.display_mappings import get_unit_status_display
from services.translation_manager import tr, get_layout_direction
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.components.icon import Icon
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.accent_line import AccentLine
from ui.animation_utils import stagger_fade_in
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitDetailsPage(QWidget):
    """Unit details view page with dark header."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.current_unit = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title("")

        self._back_btn = QPushButton(tr("action.back"))
        self._back_btn.setFixedSize(ScreenScale.w(100), ScreenScale.h(40))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self._back_btn.setStyleSheet(StyleManager.dark_action_button())
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._back_btn)

        layout.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        layout.addWidget(self._accent_line)

        # Light content wrapper
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(StyleManager.page_background())
        content_inner = QVBoxLayout(content_wrapper)
        content_inner.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        content_inner.setSpacing(15)

        # Card container
        self._card_container = QVBoxLayout()
        self._card_container.setContentsMargins(0, 0, 0, 0)
        content_inner.addLayout(self._card_container)
        content_inner.addStretch()

        layout.addWidget(content_wrapper)

    def refresh(self, data=None):
        """Load unit and display card. Accepts PropertyUnit object or string ID."""
        if data is None:
            return

        if isinstance(data, PropertyUnit):
            unit = data
        elif isinstance(data, str):
            unit = self.unit_repo.get_by_uuid(data) or self.unit_repo.get_by_id(data)
        else:
            return

        if not unit:
            logger.error(f"Unit not found: {data}")
            return

        self.current_unit = unit

        display_num = str(unit.unit_number or unit.apartment_number or "?")
        self._header.set_title(display_num)

        self._rebuild_card(unit)

    def _rebuild_card(self, unit):
        """Clear and rebuild the entire card section."""
        while self._card_container.count():
            item = self._card_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Outer frame with gradient bg
        frame = QFrame()
        frame.setObjectName("unitDetailFrame")
        frame.setStyleSheet(StyleManager.data_card())
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 22))
        frame.setGraphicsEffect(shadow)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(12)
        frame_layout.setContentsMargins(11, 11, 11, 11)

        # Section header
        header = self._build_section_header()
        frame_layout.addLayout(header)

        # Unit card
        card = self._build_unit_card(unit)
        frame_layout.addWidget(card)

        self._card_container.addWidget(frame)

        stagger_fade_in([frame])

    def _build_section_header(self) -> QHBoxLayout:
        """Build section header with icon + title/subtitle."""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)

        right_header = QHBoxLayout()
        right_header.setSpacing(8)

        icon_container = QFrame()
        icon_container.setFixedSize(ScreenScale.w(48), ScreenScale.h(48))
        icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: none;
                border-radius: 6px;
            }}
        """)
        icon_container_layout = QHBoxLayout(icon_container)
        icon_container_layout.setContentsMargins(0, 0, 0, 0)
        icon_container_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel()
        icon_pixmap = Icon.load_pixmap("move", size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_container_layout.addWidget(icon_label)

        right_header.addWidget(icon_container)

        title_subtitle_layout = QVBoxLayout()
        title_subtitle_layout.setSpacing(2)
        title_subtitle_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel(tr("page.unit_details.units_title"))
        title.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #1A1F1D; border: none; background: transparent;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_subtitle_layout.addWidget(title)

        subtitle = QLabel(tr("page.unit_details.units_info"))
        subtitle.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle.setStyleSheet("color: #86909B; border: none; background: transparent;")
        subtitle.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(subtitle)

        right_header.addLayout(title_subtitle_layout)
        header_layout.addLayout(right_header)
        header_layout.addStretch()

        return header_layout

    def _build_unit_card(self, unit) -> QFrame:
        """Build unit info card with gradient background."""
        card = QFrame()
        card.setObjectName("unitCard")
        card.setStyleSheet(StyleManager.data_card())

        card_shadow = QGraphicsDropShadowEffect()
        card_shadow.setBlurRadius(8)
        card_shadow.setXOffset(0)
        card_shadow.setYOffset(2)
        card_shadow.setColor(QColor(0, 0, 0, 30))
        card.setGraphicsEffect(card_shadow)

        card.setLayoutDirection(get_layout_direction())

        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Data preparation
        unit_display_num = str(unit.unit_number or unit.apartment_number or "?")
        unit_type_val = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else (unit.unit_type or "-")

        if hasattr(unit, 'apartment_status') and unit.apartment_status is not None:
            status_val = get_unit_status_display(unit.apartment_status)
        else:
            status_val = "-"

        floor_val = str(unit.floor_number) if unit.floor_number is not None else "-"
        rooms_val = str(unit.apartment_number) if unit.apartment_number else "-"

        if unit.area_sqm:
            try:
                area_val = f"{float(unit.area_sqm):.2f} {tr('unit.sqm')}"
            except (ValueError, TypeError):
                area_val = "-"
        else:
            area_val = "-"

        # 6-column grid
        data_points = [
            (tr("page.unit_details.unit_number"), unit_display_num),
            (tr("page.unit_details.floor_number"), floor_val),
            (tr("page.unit_details.rooms_count"), rooms_val),
            (tr("page.unit_details.unit_area"), area_val),
            (tr("page.unit_details.unit_type"), unit_type_val),
            (tr("page.unit_details.unit_status"), status_val),
        ]

        grid_layout = QHBoxLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        for label_text, value_text in data_points:
            col = QVBoxLayout()
            col.setSpacing(2)
            col.setContentsMargins(8, 0, 8, 0)
            col.setAlignment(Qt.AlignCenter)

            lbl_title = QLabel(label_text)
            lbl_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl_title.setStyleSheet("color: #1A1F1D;")
            lbl_title.setAlignment(Qt.AlignCenter)

            lbl_val = QLabel(str(value_text))
            lbl_val.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            lbl_val.setStyleSheet("color: #86909B;")
            lbl_val.setAlignment(Qt.AlignCenter)

            col.addWidget(lbl_title)
            col.addWidget(lbl_val)
            grid_layout.addLayout(col, stretch=1)

        main_layout.addLayout(grid_layout)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("""
            QFrame {
                border: none;
                border-top: 1px dotted #D1D5DB;
                background: transparent;
            }
        """)
        main_layout.addWidget(divider)

        # Description
        desc_layout = QVBoxLayout()
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(2)
        desc_layout.setDirection(QVBoxLayout.TopToBottom)

        desc_title = QLabel(tr("page.unit_details.unit_description"))
        desc_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        desc_title.setStyleSheet("color: #1A1F1D;")
        desc_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        desc_text_content = unit.property_description if unit.property_description else tr("wizard.unit.property_description_placeholder")
        desc_text = QLabel(desc_text_content)
        desc_text.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        desc_text.setStyleSheet("color: #86909B;")
        desc_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        desc_text.setWordWrap(True)
        desc_text.setMaximumHeight(ScreenScale.h(40))

        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(desc_text)
        main_layout.addLayout(desc_layout)

        return card

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        self.setLayoutDirection(get_layout_direction())
        self._back_btn.setText(tr("action.back"))
        if self.current_unit:
            self._rebuild_card(self.current_unit)
