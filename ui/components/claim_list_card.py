# -*- coding: utf-8 -*-
"""
Claim List Card Component - بطاقة المطالبة في القائمة
Individual claim card with shadow, displayed in grid layout.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

from ..design_system import PageDimensions, Typography, ScreenScale
from ..style_manager import StyleManager
from .icon import Icon, IconSize
from services.translation_manager import tr


class ClaimListCard(QFrame):
    """Claim card component for grid display."""

    clicked = pyqtSignal(str)

    def __init__(self, claim_data: dict, icon_name: str = "blue", parent=None):
        """Initialize claim card."""
        super().__init__(parent)
        self.claim_data = claim_data
        self.icon_name = icon_name
        self._setup_ui()

    def _setup_ui(self):
        """Setup card UI with shadow and content layout."""
        self.setObjectName("ClaimCard")  # Match StyleManager selector exactly

        self.setStyleSheet(StyleManager.card())

        self.setFixedHeight(PageDimensions.CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(PageDimensions.CARD_SHADOW_BLUR)
        shadow.setXOffset(PageDimensions.CARD_SHADOW_X)
        shadow.setYOffset(PageDimensions.CARD_SHADOW_Y)

        shadow_color = QColor(PageDimensions.CARD_SHADOW_COLOR)
        shadow_color.setAlpha(int(255 * PageDimensions.CARD_SHADOW_OPACITY / 100))
        shadow.setColor(shadow_color)

        self.setGraphicsEffect(shadow)

        # Card layout
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(
            PageDimensions.CARD_PADDING,  # Left: 12px
            PageDimensions.CARD_PADDING,  # Top: 12px
            PageDimensions.CARD_PADDING,  # Right: 12px
            PageDimensions.CARD_PADDING   # Bottom: 12px
        )
        card_layout.setSpacing(PageDimensions.CARD_GAP_INTERNAL)

        top_row = QHBoxLayout()
        top_row.setSpacing(PageDimensions.CARD_GAP_INTERNAL)

        # Icon button
        icon_btn = QPushButton()
        icon_btn.setCursor(Qt.PointingHandCursor)
        icon_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))

        q_icon = Icon.load_qicon(self.icon_name)
        if q_icon:
            icon_btn.setIcon(q_icon)
            icon_btn.setIconSize(QSize(20, 20))
        else:
            # Fallback to text icon if image not found
            icon_btn.setText("📋")

        icon_btn.setStyleSheet(StyleManager.button_icon())
        icon_btn.clicked.connect(lambda: self.clicked.emit(self.claim_data.get('claim_id', '')))
        top_row.addWidget(icon_btn)

        name_container = QWidget()
        name_container.setStyleSheet("background: transparent; border: none;")
        name_layout = QVBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(2)

        name = self.claim_data.get('claimant_name', tr("component.claim_list_card.unspecified"))
        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            QLabel {{
                color: #212121;
                font-size: 13px;
                font-weight: 600;
                font-family: 'IBM Plex Sans Arabic', 'Noto Kufi Arabic', 'Calibri';
                background: transparent;
                border: none;
            }}
        """)
        name_label.setTextFormat(Qt.PlainText)
        name_layout.addWidget(name_label)

        claim_id = self.claim_data.get('claim_id', 'CL-2025-000001')
        id_label = QLabel(claim_id)
        id_label.setStyleSheet(f"""
            QLabel {{
                color: #9e9e9e;
                font-size: 11px;
                font-family: 'IBM Plex Sans Arabic', 'Noto Kufi Arabic', 'Calibri';
                background: transparent;
                border: none;
            }}
        """)
        id_label.setTextFormat(Qt.PlainText)
        name_layout.addWidget(id_label)

        top_row.addWidget(name_container)
        top_row.addStretch()

        date = self.claim_data.get('date', '2024-12-01')
        date_label = QLabel(date)
        date_label.setStyleSheet(f"""
            QLabel {{
                color: #9e9e9e;
                font-size: 12px;
                font-family: 'IBM Plex Sans Arabic', 'Noto Kufi Arabic', 'Calibri';
                background: transparent;
                border: none;
            }}
        """)
        date_label.setTextFormat(Qt.PlainText)
        top_row.addWidget(date_label)

        card_layout.addLayout(top_row)

        # Details container
        details_container = QFrame()
        details_container.setObjectName("detailsFrame")

        details_container.setFrameShape(QFrame.NoFrame)
        details_container.setAttribute(Qt.WA_StyledBackground, True)
        details_container.setStyleSheet(StyleManager.card_details_container())

        details_layout = QHBoxLayout(details_container)
        details_layout.setContentsMargins(
            PageDimensions.CARD_DETAILS_PADDING_H,
            PageDimensions.CARD_DETAILS_PADDING_V,
            PageDimensions.CARD_DETAILS_PADDING_H,
            PageDimensions.CARD_DETAILS_PADDING_V
        )
        details_layout.setSpacing(PageDimensions.CARD_DETAILS_GAP)

        folder_icon = Icon("dec", size=14, fallback_text="▣")
        details_layout.addWidget(folder_icon)

        # Build hierarchical address
        from utils.helpers import build_hierarchical_address

        building_obj = self.claim_data.get('building')
        unit_obj = self.claim_data.get('unit')

        # If objects not available, create simple namespace with available data
        if not building_obj:
            class SimpleNamespace:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            building_obj = SimpleNamespace(
                governorate_name_ar=self.claim_data.get('governorate_name_ar', 'حلب'),
                district_name_ar=self.claim_data.get('district_name_ar'),
                subdistrict_name_ar=self.claim_data.get('subdistrict_name_ar'),
                neighborhood_name_ar=self.claim_data.get('neighborhood_name_ar'),
                building_id=self.claim_data.get('building_id')
            )

        if not unit_obj and self.claim_data.get('unit_number'):
            class SimpleNamespace:
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)

            unit_obj = SimpleNamespace(
                unit_number=self.claim_data.get('unit_number')
            )

        details_text = build_hierarchical_address(
            building_obj=building_obj,
            unit_obj=unit_obj,
            separator=" - ",
            include_unit=True
        )

        details_label = QLabel(details_text)

        details_font = QFont(
            Typography.FONT_FAMILY_ARABIC,
            PageDimensions.CARD_DETAILS_TEXT_SIZE,
            PageDimensions.CARD_DETAILS_TEXT_WEIGHT
        )
        details_font.setFamilies([
            "IBM Plex Sans Arabic",
            "Noto Kufi Arabic",
            "Calibri"
        ])
        details_font.setLetterSpacing(
            QFont.AbsoluteSpacing,
            PageDimensions.CARD_DETAILS_TEXT_LETTER_SPACING
        )
        details_label.setFont(details_font)

        details_label.setStyleSheet(f"""
            QLabel {{
                color: {PageDimensions.CARD_DETAILS_TEXT_COLOR};
                background: transparent;
                border: none;
            }}
        """)
        details_label.setTextFormat(Qt.PlainText)
        details_layout.addWidget(details_label)

        details_layout.addStretch()

        card_layout.addWidget(details_container)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.claim_data.get('claim_id', ''))
        super().mousePressEvent(event)
