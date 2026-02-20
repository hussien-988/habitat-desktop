# -*- coding: utf-8 -*-
"""
Unit Details View Page — displays unit information card.
DRY: Replicates the unit card section from unit_selection_step.py wizard
but with a single unit, no selection state, no "add unit" button.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from repositories.database import Database
from repositories.unit_repository import UnitRepository
from models.unit import PropertyUnit
from services.display_mappings import get_unit_status_display
from services.translation_manager import tr
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions
from ui.components.icon import Icon
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitDetailsPage(QWidget):
    """Unit details view page — mirrors wizard unit card section."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.current_unit = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(15)

        # Title — unit number (e.g. "12"), right-aligned, same font as other pages
        self.title_label = QLabel("")
        self.title_label.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        self.title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        self.title_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.title_label)

        # Breadcrumb — "الوحدات السكنية  •  عرض"
        self.breadcrumb = QLabel("الوحدات السكنية  •  عرض")
        self.breadcrumb.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self.breadcrumb.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;")
        layout.addWidget(self.breadcrumb)

        # Card container — populated in refresh()
        self._card_container = QVBoxLayout()
        self._card_container.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._card_container)

        layout.addStretch()

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

        # Update title with unit number
        display_num = str(unit.unit_number or unit.apartment_number or "?")
        self.title_label.setText(display_num)

        # Clear old card and rebuild
        self._rebuild_card(unit)

    def _rebuild_card(self, unit):
        """Clear and rebuild the entire card section."""
        while self._card_container.count():
            item = self._card_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # White outer frame (same as units_main_frame in wizard)
        frame = QFrame()
        frame.setObjectName("unitDetailFrame")
        frame.setStyleSheet("""
            QFrame#unitDetailFrame {
                background-color: white;
                border-radius: 10px;
                border: none;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(12)
        frame_layout.setContentsMargins(11, 11, 11, 11)

        # Section header: icon + "المقاسم" / "معلومات المقاسم" (no add button)
        header = self._build_section_header()
        frame_layout.addLayout(header)

        # Unit card (DRY — same as _create_unit_card but without selection)
        card = self._build_unit_card(unit)
        frame_layout.addWidget(card)

        self._card_container.addWidget(frame)

    def _build_section_header(self) -> QHBoxLayout:
        """Build section header — mirrors wizard unit_selection_step lines 241-315."""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Right side: Icon container + Title/Subtitle
        right_header = QHBoxLayout()
        right_header.setSpacing(8)

        # Icon container 48×48, background #F0F7FF, border-radius 6px
        icon_container = QFrame()
        icon_container.setFixedSize(48, 48)
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
        else:
            icon_label.setText("🏘️")
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_container_layout.addWidget(icon_label)

        right_header.addWidget(icon_container)

        # Title + Subtitle
        title_subtitle_layout = QVBoxLayout()
        title_subtitle_layout.setSpacing(2)
        title_subtitle_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("المقاسم")
        title.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #1A1F1D; border: none; background: transparent;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_subtitle_layout.addWidget(title)

        subtitle = QLabel("معلومات المقاسم")
        subtitle.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle.setStyleSheet("color: #86909B; border: none; background: transparent;")
        subtitle.setAlignment(Qt.AlignRight)
        title_subtitle_layout.addWidget(subtitle)

        right_header.addLayout(title_subtitle_layout)

        header_layout.addLayout(right_header)
        header_layout.addStretch()

        return header_layout

    def _build_unit_card(self, unit) -> QFrame:
        """
        Build unit info card — exact copy of _create_unit_card() from
        unit_selection_step.py lines 587-760, but without:
        - selection state / checkmark
        - hover border change
        - click handler / cursor
        - setFixedSize (uses fill-width instead)
        """
        card = QFrame()
        card.setObjectName("unitCard")
        card.setStyleSheet("""
            QFrame#unitCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
            }
            QFrame#unitCard QLabel {
                border: none;
                background: transparent;
            }
        """)

        # Shadow — same as wizard
        card_shadow = QGraphicsDropShadowEffect()
        card_shadow.setBlurRadius(8)
        card_shadow.setXOffset(0)
        card_shadow.setYOffset(2)
        card_shadow.setColor(QColor(0, 0, 0, 30))
        card.setGraphicsEffect(card_shadow)

        card.setLayoutDirection(Qt.RightToLeft)

        # Main layout — Figma: padding 12px all sides
        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # --- Data preparation (same as wizard) ---
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
                area_val = f"{float(unit.area_sqm):.2f} م²"
            except (ValueError, TypeError):
                area_val = "-"
        else:
            area_val = "-"

        # --- Top Row: 6-column grid ---
        data_points = [
            ("رقم المقسم", unit_display_num),
            ("رقم الطابق", floor_val),
            ("عدد الغرف", rooms_val),
            ("مساحة المقسم", area_val),
            ("نوع المقسم", unit_type_val),
            ("حالة المقسم", status_val),
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

        # --- Dotted divider ---
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

        # --- Description section ---
        desc_layout = QVBoxLayout()
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(2)
        desc_layout.setDirection(QVBoxLayout.TopToBottom)

        desc_title = QLabel("وصف المقسم")
        desc_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        desc_title.setStyleSheet("color: #1A1F1D;")
        desc_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        desc_text_content = unit.property_description if unit.property_description else tr("wizard.unit.property_description_placeholder")
        desc_text = QLabel(desc_text_content)
        desc_text.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        desc_text.setStyleSheet("color: #86909B;")
        desc_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        desc_text.setWordWrap(True)
        desc_text.setMaximumHeight(40)

        desc_layout.addWidget(desc_title)
        desc_layout.addWidget(desc_text)
        main_layout.addLayout(desc_layout)

        return card
