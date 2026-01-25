# -*- coding: utf-8 -*-
"""
Claim List Card Component - بطاقة المطالبة في القائمة
Individual claim card with shadow, displayed in grid layout.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

from ..design_system import PageDimensions, Typography
from ..style_manager import StyleManager
from .icon import Icon, IconSize


class ClaimListCard(QFrame):
    """Claim card component for grid display."""

    clicked = pyqtSignal(str)

    def __init__(self, claim_data: dict, icon_name: str = "blue", parent=None):
        """
        Initialize claim card.

        Args:
            claim_data: Dictionary containing claim information
            icon_name: Icon name to display (default: "blue" for completed, "yellow" for drafts)
            parent: Parent widget
        """
        super().__init__(parent)
        self.claim_data = claim_data
        self.icon_name = icon_name
        self._setup_ui()

    def _setup_ui(self):
        """
        Setup card UI with shadow and content layout.

        Figma Specs:
        - Size: 616.5×112px
        - Padding: 12px (all sides)
        - Corner radius: 8px
        - Gap (internal): 12px
        - Fill: #FFFFFF
        - Drop shadow: present
        """
        self.setObjectName("ClaimCard")  # Match StyleManager selector exactly

        # Apply Figma styling via StyleManager (Single Source of Truth)
        self.setStyleSheet(StyleManager.card())

        # Figma: Card dimensions (112px height from Figma)
        self.setFixedHeight(PageDimensions.CARD_HEIGHT)  # 112px
        self.setCursor(Qt.PointingHandCursor)

        # Drop shadow (from Figma Effects - exact values)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(PageDimensions.CARD_SHADOW_BLUR)  # 8px from Figma
        shadow.setXOffset(PageDimensions.CARD_SHADOW_X)        # 0 from Figma
        shadow.setYOffset(PageDimensions.CARD_SHADOW_Y)        # 4px from Figma

        # Color: #919EAB with 16% opacity (Figma)
        shadow_color = QColor(PageDimensions.CARD_SHADOW_COLOR)
        shadow_color.setAlpha(int(255 * PageDimensions.CARD_SHADOW_OPACITY / 100))  # 16% = 41/255
        shadow.setColor(shadow_color)

        self.setGraphicsEffect(shadow)

        # Card layout with Figma padding: 12px all sides
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(
            PageDimensions.CARD_PADDING,  # Left: 12px
            PageDimensions.CARD_PADDING,  # Top: 12px
            PageDimensions.CARD_PADDING,  # Right: 12px
            PageDimensions.CARD_PADDING   # Bottom: 12px
        )
        # Internal gap between elements: 12px (Figma)
        card_layout.setSpacing(PageDimensions.CARD_GAP_INTERNAL)

        top_row = QHBoxLayout()
        top_row.setSpacing(PageDimensions.CARD_GAP_INTERNAL)  # 12px from Figma

        # Icon button using reusable Icon component (DRY + SOLID)
        # Icon varies by claim type: "blue" for completed, "yellow" for drafts
        icon_btn = QPushButton()
        icon_btn.setCursor(Qt.PointingHandCursor)
        icon_btn.setFixedSize(32, 32)

        # Load icon using Icon component static method
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

        name = self.claim_data.get('claimant_name', 'غير محدد')
        name_label = QLabel(name)
        # DRY: Use Typography constants for font family
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
        # DRY: Use Typography constants for font family
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
        # DRY: Use Typography constants for font family
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

        # Details container with Figma styling (pill-shaped box)
        details_container = QFrame()
        details_container.setObjectName("detailsFrame")

        # CRITICAL: Enable styled frame (required for border-radius to work)
        details_container.setFrameShape(QFrame.NoFrame)  # NoFrame allows full stylesheet control
        details_container.setAttribute(Qt.WA_StyledBackground, True)  # Enable custom stylesheet painting

        # Apply Figma styling via StyleManager (DRY + Single Source of Truth)
        details_container.setStyleSheet(StyleManager.card_details_container())

        details_layout = QHBoxLayout(details_container)
        # Padding: 8px horizontal, 6px vertical (Figma)
        # Applied via layout margins for best rendering compatibility
        details_layout.setContentsMargins(
            PageDimensions.CARD_DETAILS_PADDING_H,  # Left: 8px
            PageDimensions.CARD_DETAILS_PADDING_V,  # Top: 6px
            PageDimensions.CARD_DETAILS_PADDING_H,  # Right: 8px
            PageDimensions.CARD_DETAILS_PADDING_V   # Bottom: 6px
        )
        # Gap between elements: 8px (Figma)
        details_layout.setSpacing(PageDimensions.CARD_DETAILS_GAP)

        # Details icon using reusable Icon component (DRY + SOLID)
        # Use "dec" icon (same as unit selection step - DRY principle)
        folder_icon = Icon("dec", size=14, fallback_text="▣")
        details_layout.addWidget(folder_icon)

        # Build hierarchical address using DRY helper function
        # Format: "حلب - المنطقة - الناحية - الحي - رقم البناء - رقم الوحدة"
        # SOLID: Single Responsibility - helper function builds address
        from utils.helpers import build_hierarchical_address

        # Get building and unit objects from claim_data (if available)
        building_obj = self.claim_data.get('building')  # Building model object
        unit_obj = self.claim_data.get('unit')          # Unit model object

        # If objects not available, create simple namespace with available data
        if not building_obj:
            # Create a simple object-like structure from dict data
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

        # Use DRY helper to build address (Single Source of Truth)
        details_text = build_hierarchical_address(
            building_obj=building_obj,
            unit_obj=unit_obj,
            separator=" - ",
            include_unit=True
        )

        # Apply Figma styling with constants (DRY principle)
        details_label = QLabel(details_text)

        # Set font with Typography constants (DRY + SOLID)
        # IBM Plex Sans Arabic only (no Noto Kufi Arabic)
        details_font = QFont(
            Typography.FONT_FAMILY_ARABIC,  # IBM Plex Sans Arabic
            PageDimensions.CARD_DETAILS_TEXT_SIZE,  # 6pt
            PageDimensions.CARD_DETAILS_TEXT_WEIGHT  # Light (300)
        )
        # Set fallback font family chain (matches login_page.py):
        # IBM Plex Sans Arabic → Noto Kufi Arabic → Calibri
        details_font.setFamilies([
            "IBM Plex Sans Arabic",  # System font (same as login)
            "Noto Kufi Arabic",      # Bundled fallback
            "Calibri"                # System fallback
        ])
        details_font.setLetterSpacing(
            QFont.AbsoluteSpacing,
            PageDimensions.CARD_DETAILS_TEXT_LETTER_SPACING  # 0
        )
        details_label.setFont(details_font)

        # Set colors and styling via QSS
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
