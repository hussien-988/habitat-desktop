# -*- coding: utf-8 -*-
"""
Building Selection Step - Step 1 of Office Survey Wizard.

Allows user to:
- Search for existing buildings
- View building on map
- Select a building to proceed
"""

from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFrame, QListWidget, QListWidgetItem, QToolButton,
    QSizePolicy, QLayout, QWidget
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPixmap, QIcon

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from controllers.building_controller import BuildingController, BuildingFilter
from models.building import Building
from app.config import Config
from services.api_client import get_api_client
from services.error_mapper import map_exception
from ui.error_handler import ErrorHandler
from utils.logger import get_logger
from ui.font_utils import FontManager, create_font
from ui.design_system import Colors
from services.translation_manager import tr

logger = get_logger(__name__)

# Check for WebEngine availability (for map dialog)
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBENGINE = False
    HAS_WEBCHANNEL = False


class BuildingSelectionStep(BaseStep):
    """
    Step 1: Building Selection.

    User can search for buildings by ID or address and select one.
    UI copied from office_survey_wizard.py _create_building_step() - exact match.
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)
        self.building_controller = BuildingController(self.context.db)
        self.selected_building: Optional[Building] = None

        # Initialize survey API service
        self._survey_api_service = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        widget = self  # Use self as the widget since BaseStep already has main_layout
        widget.setLayoutDirection(Qt.RightToLeft)

        layout = self.main_layout
        # No horizontal padding - wizard applies 131px (DRY principle)
        # Only vertical spacing between elements
        # Top gap: 15px (reduced to accommodate multiple cards)
        layout.setContentsMargins(0, 15, 0, 16)  # Top: 15px, Bottom: 16px
        layout.setSpacing(15)  # Unified spacing: 15px between cards

        # ===== Card: Building Data =====
        card = QFrame()
        card.setObjectName("buildingCard")
        card.setStyleSheet("""
            QFrame#buildingCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)

        # Card dimensions: Fixed height 151px (from Figma)
        card.setFixedHeight(151)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        card_layout = QVBoxLayout(card)
        # Padding: 12px from all sides (from Figma)
        card_layout.setContentsMargins(12, 12, 12, 12)
        # No default spacing - we'll control gaps manually for precision
        card_layout.setSpacing(0)

        # Header (title + subtitle)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(1)
        title = QLabel(tr("wizard.building.card_title"))
        # Title: 14px from Figma = 10pt, weight 600, color WIZARD_TITLE
        title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        subtitle = QLabel(tr("wizard.building.card_subtitle"))
        # Subtitle: 14px from Figma = 10pt, weight 400, color WIZARD_SUBTITLE
        subtitle.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        header_text_col.addWidget(title)
        header_text_col.addWidget(subtitle)

        # Icon: blue.png
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        # Load blue.png icon using Icon.load_pixmap for absolute path resolution
        from ui.components.icon import Icon
        icon_pixmap = Icon.load_pixmap("blue", size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_lbl.setPixmap(icon_pixmap)
        else:
            # Fallback if image not found
            icon_lbl.setText("📄")
            icon_lbl.setStyleSheet(icon_lbl.styleSheet() + "font-size: 16px;")

        header_row.addWidget(icon_lbl)
        header_row.addLayout(header_text_col)
        header_row.addStretch(1)

        card_layout.addLayout(header_row)

        # Gap: 12px between header and code label (from Figma)
        card_layout.addSpacing(12)

        # Label: building code (same as title - 14px = 10pt, weight 600, color WIZARD_TITLE)
        code_label = QLabel(tr("wizard.building.code_label"))
        code_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        code_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(code_label)

        # Gap: 8px between code label and search bar
        card_layout.addSpacing(8)

        # Search bar (one row) - Figma specs:
        # Height: 42px, padding: 14px left/right & 8px top/bottom
        # Border-radius: 8px, Background & Border from design system
        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setFixedHeight(42)  # Height from Figma
        search_bar.setStyleSheet(f"""
            QFrame#searchBar {{
                background-color: {Colors.SEARCH_BAR_BG};
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
            }}
        """)
        search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(search_bar)
        # Padding: 14px left/right, 8px top/bottom (from Figma)
        sb.setContentsMargins(14, 8, 14, 8)
        sb.setSpacing(8)

        # Search icon button
        search_icon_btn = QToolButton()
        search_icon_btn.setCursor(Qt.PointingHandCursor)
        search_icon_btn.setFixedSize(30, 30)
        search_icon_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
            }
            QToolButton:hover {
                background-color: #EEF6FF;
                border-radius: 8px;
            }
        """)
        # Load search.png icon using Icon.load_pixmap for absolute path resolution
        from ui.components.icon import Icon
        search_pixmap = Icon.load_pixmap("search", size=20)
        if search_pixmap and not search_pixmap.isNull():
            search_icon_btn.setIcon(QIcon(search_pixmap))
            search_icon_btn.setIconSize(QSize(20, 20))
        else:
            # Fallback if image not found
            search_icon_btn.setText("🔍")
            search_icon_btn.setStyleSheet(search_icon_btn.styleSheet() + "font-size: 14px;")

        search_icon_btn.clicked.connect(self._search_buildings)

        # Input
        self.building_search = QLineEdit()
        self.building_search.setPlaceholderText(tr("wizard.building.search_placeholder"))
        self.building_search.setLayoutDirection(Qt.RightToLeft)

        self.building_search.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                padding: 0px 6px;
                min-height: 28px;
                color: #2C3E50;
            }
        """)
        self.building_search.textChanged.connect(self._on_building_code_changed)
        self.building_search.returnPressed.connect(self._search_buildings)

        # Left links (map search buttons)
        left_links_layout = QHBoxLayout()
        left_links_layout.setSpacing(8)

        self.search_on_map_btn = QPushButton(tr("wizard.building.search_on_map"))
        self.search_on_map_btn.setCursor(Qt.PointingHandCursor)
        self.search_on_map_btn.setFlat(True)
        self.search_on_map_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #3890DF;
                font-family: 'IBM Plex Sans Arabic';
                font-weight: 600;
                font-size: 7pt;
                text-decoration: underline;
                padding: 0;
                margin-top: 1px;
            }
        """)
        self.search_on_map_btn.clicked.connect(self._open_map_search_dialog)

        # فقط زر البحث على الخريطة - تم إزالة زر "تحديد منطقة" كما طلب المستخدم
        # الوظيفة الآن مدمجة في الخريطة نفسها
        left_links_layout.addWidget(self.search_on_map_btn)

        # Assemble search bar
        sb.addLayout(left_links_layout)   # left
        sb.addWidget(self.building_search)  # middle (stretch)
        sb.addWidget(search_icon_btn, 1)

        # Add bar to card
        card_layout.addWidget(search_bar)

        # Add card to main layout
        layout.addWidget(card)

        # Suggestions list (dropdown look) - Flows from search bar, centered, overlaps card
        # Figma specs: width 1225px, height 179px, border-radius 8px, no scrollbar
        # Floats above card by 12px (overlaps with card's bottom padding)
        self.buildings_list = QListWidget()
        self.buildings_list.setVisible(False)
        self.buildings_list.setFixedHeight(179)  # Height from Figma
        self.buildings_list.setFixedWidth(1225)  # Width from Figma

        # Hide scrollbar but keep scrolling enabled with mouse wheel
        self.buildings_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.buildings_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # DRY: Using Colors constants and removing border-bottom separator
        # Border-radius only on bottom corners (flows from search bar)
        self.buildings_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                background-color: {Colors.SURFACE};
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-bottom: none;
            }}
            QListWidget::item:selected {{
                background-color: #EFF6FF;
            }}
        """)
        self.buildings_list.itemClicked.connect(self._on_building_selected)
        self.buildings_list.itemDoubleClicked.connect(self._on_building_confirmed)

        # Position list: overlaps with card's bottom padding (12px) and centered horizontally
        # Calculation: -(layout spacing 15px + card bottom padding 12px) = -27px
        layout.addSpacing(-27)  # Negative spacing: overlaps card by 12px (cancels 15px spacing + 12px padding)

        # Center the list horizontally using a container layout
        list_container = QHBoxLayout()
        list_container.addStretch(1)  # Left stretch
        list_container.addWidget(self.buildings_list)
        list_container.addStretch(1)  # Right stretch

        layout.addLayout(list_container)

        # Correct spacing before stats card (professional calculation):
        # - Cancel the negative spacing effect: +27px
        # - Add desired spacing between cards: +15px
        # - Total: +42px
        layout.addSpacing(42)  # Restores normal flow + adds 15px spacing

        # ===== Selected building stats card (Separate card) =====
        # Figma specs: height 73px, padding 12px all sides, 5 sections without dividers
        self.stats_card = QFrame()
        self.stats_card.setObjectName("statsCard")
        self.stats_card.setVisible(False)  # Hidden initially
        self.stats_card.setFixedHeight(73)  # Height from Figma

        # DRY: Using Colors constants
        self.stats_card.setStyleSheet(f"""
            QFrame#statsCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)

        stats_layout = QHBoxLayout(self.stats_card)
        # Padding: 12px from all sides (from Figma)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(0)  # No spacing - sections will be separated by stretch

        # Helper function to create stat section (label on top, value below)
        def _create_stat_section(label_text, value_text="-"):
            """Create a stat section with label on top and value below."""
            section = QWidget()
            section.setStyleSheet("background: transparent;")

            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)  # Small gap between label and value
            section_layout.setAlignment(Qt.AlignCenter)

            # Label (top text) - darker color (swapped)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignCenter)
            # DRY: Using create_font + Colors (swapped to WIZARD_TITLE)
            label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

            # Value (bottom text/number) - lighter color (swapped)
            value = QLabel(value_text)
            value.setAlignment(Qt.AlignCenter)
            # DRY: Using create_font + Colors (swapped to WIZARD_SUBTITLE)
            value.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

            section_layout.addWidget(label)
            section_layout.addWidget(value)

            return section, value

        # Create 5 stat sections (from Figma order)
        section_type, self.ui_building_type = _create_stat_section(tr("wizard.building.type"))
        section_status, self.ui_building_status = _create_stat_section(tr("wizard.building.status"))
        section_units, self.ui_units_count = _create_stat_section(tr("wizard.building.units_count"))
        section_parcels, self.ui_parcels_count = _create_stat_section(tr("wizard.building.parcels_count"))
        section_shops, self.ui_shops_count = _create_stat_section(tr("wizard.building.shops_count"))

        # Add sections with equal spacing (no dividers)
        sections = [section_type, section_status, section_units, section_parcels, section_shops]
        for i, section in enumerate(sections):
            stats_layout.addWidget(section, stretch=1)
            # No separator lines - just equal distribution

        layout.addWidget(self.stats_card)

        # Spacing between stats card and location card: 15px
        layout.addSpacing(15)

        # ===== Location card (Third section) =====
        # Figma specs: height 187px, padding 12px all sides, gap 12px, border-radius 8px
        self.location_card = QFrame()
        self.location_card.setObjectName("locationCard")
        self.location_card.setVisible(False)  # Hidden initially
        self.location_card.setFixedHeight(187)  # Height from Figma

        # DRY: Using Colors constants
        self.location_card.setStyleSheet(f"""
            QFrame#locationCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)

        location_layout = QVBoxLayout(self.location_card)
        # Padding: 12px from all sides (from Figma)
        location_layout.setContentsMargins(12, 12, 12, 12)
        location_layout.setSpacing(0)  # Manual spacing control

        # Row 1: Header only - "موقع البناء"
        header = QLabel(tr("wizard.building.location_title"))
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        location_layout.addWidget(header)

        # Gap: 12px between header and content
        location_layout.addSpacing(12)

        # Row 2: Three equal sections with 24px gap between them
        content_row = QHBoxLayout()
        content_row.setSpacing(24)  # Gap: 24px between sections

        # Helper function for info section (DRY)
        def _create_info_section(label_text, value_text="-"):
            """Create info section with label and value."""
            section = QVBoxLayout()
            section.setSpacing(4)  # Small gap between label and value

            # Label (top)
            label = QLabel(label_text)
            label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

            # Value (bottom)
            value = QLabel(value_text)
            value.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
            value.setWordWrap(True)

            section.addWidget(label)
            section.addWidget(value)
            section.addStretch(1)  # Push content to top

            return section, value

        # Section 1: Map (left)
        map_section = QVBoxLayout()
        map_section.setSpacing(0)  # No spacing - manual control

        # Map container (QLabel to support QPixmap)
        map_container = QLabel()
        map_container.setFixedSize(400, 130)  # Width: 400px, Height: 130px (from Figma)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("mapContainer")

        # Load background map image using Icon component (absolute paths)
        from ui.components.icon import Icon

        # Try to load map image (image-40.png or map-placeholder.png)
        map_bg_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_bg_pixmap or map_bg_pixmap.isNull():
            # Fallback to map-placeholder
            map_bg_pixmap = Icon.load_pixmap("map-placeholder", size=None)

        if map_bg_pixmap and not map_bg_pixmap.isNull():
            # Scale to exact size while maintaining quality
            scaled_bg = map_bg_pixmap.scaled(400, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            map_container.setPixmap(scaled_bg)

        # Styling with border-radius (works with QLabel)
        map_container.setStyleSheet(f"""
            QLabel#mapContainer {{
                background-color: #E8E8E8;
                border-radius: 8px;
            }}
        """)

        # Layout for map container (no automatic layout - manual positioning)
        # We'll use absolute positioning for button and icon

        # White button in top-left corner (opposite to title)
        # Dimensions: 94×20px, border-radius: 5px, padding: 4px
        map_button = QPushButton(map_container)
        map_button.setFixedSize(94, 20)  # Width: 94px, Height: 20px (from Figma)
        map_button.move(8, 8)  # Position in top-left corner with small margin
        map_button.setCursor(Qt.PointingHandCursor)

        # Icon: pill.png with PRIMARY_BLUE color using Icon.load_pixmap
        from ui.components.icon import Icon
        icon_pixmap = Icon.load_pixmap("pill", size=12)
        if icon_pixmap and not icon_pixmap.isNull():
            map_button.setIcon(QIcon(icon_pixmap))
            map_button.setIconSize(QSize(12, 12))

        # Text: "فتح الخريطة" - 12px Figma = 9pt PyQt5, PRIMARY_BLUE color
        map_button.setText(tr("wizard.building.open_map"))
        map_button.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))

        # DRY: Using Colors.PRIMARY_BLUE
        # Professional shadow effect for floating appearance
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
            }}
        """)

        # Apply shadow effect using QGraphicsDropShadowEffect for professional floating look
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)  # Soft blur
        shadow.setXOffset(0)  # Centered shadow
        shadow.setYOffset(2)  # Slight offset downward
        shadow.setColor(QColor(0, 0, 0, 60))  # Semi-transparent black (alpha: 60/255)
        map_button.setGraphicsEffect(shadow)

        map_button.clicked.connect(self._open_map_dialog)

        # Location icon in center of map
        # carbon_location-filled.png - larger size for better visibility
        location_icon = QLabel(map_container)
        from ui.components.icon import Icon
        location_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if location_pixmap and not location_pixmap.isNull():
            location_icon.setPixmap(location_pixmap)
            location_icon.setFixedSize(56, 56)
            # Position in center: (400-56)/2 = 172, (130-56)/2 = 37
            location_icon.move(172, 37)

            # Professional design: transparent background
            # Note: Qt doesn't support CSS filter property, removed to prevent warnings
            location_icon.setStyleSheet("""
                background: transparent;
            """)
        else:
            # Fallback: use text emoji with larger size
            location_icon.setText("📍")
            location_icon.setFont(create_font(size=32, weight=FontManager.WEIGHT_REGULAR))
            location_icon.setStyleSheet("background: transparent;")
            location_icon.setAlignment(Qt.AlignCenter)
            location_icon.setFixedSize(56, 56)
            location_icon.move(172, 37)

        map_section.addWidget(map_container)
        map_section.addStretch(1)  # Push content to top

        content_row.addLayout(map_section, stretch=1)

        # Section 2: وصف الموقع (center)
        section_location, self.ui_location_desc = _create_info_section(tr("wizard.building.location_desc"), tr("wizard.building.location_desc"))
        content_row.addLayout(section_location, stretch=1)

        # Section 3: الوصف العام (right)
        section_general, self.ui_general_desc = _create_info_section(tr("wizard.building.general_desc"), tr("wizard.building.general_desc_placeholder"))
        content_row.addLayout(section_general, stretch=1)

        location_layout.addLayout(content_row)

        layout.addWidget(self.location_card)

        # Add stretch after location card to push remaining content down
        layout.addStretch(1)

        # Lazy loading: Don't load buildings until needed (when user searches or opens map)
        # This speeds up wizard initialization significantly
        # self._load_buildings()  # Removed - will load on first search

    def _on_building_code_changed(self):
        """UI behavior: filter + show/hide suggestions."""
        text = self.building_search.text().strip()
        # Filter same as old
        self._filter_buildings()
        # Show suggestions only when there's text
        self.buildings_list.setVisible(bool(text))

    def _open_map_search_dialog(self):
        """
        Open professional map search dialog for building selection.

        Uses BuildingMapDialog V2 (DRY principle) - unified component with:
        - Clean design (no clutter, matches screenshot 2)
        - Live coordinate updates
        - PostGIS-compatible WKT output
        - Always in selection mode (user can search again)
        """
        from ui.components.building_map_dialog_v2 import show_building_map_dialog

        # ✅ FIX: Get auth token from parent window (MainWindow has current_user with token)
        auth_token = None
        try:
            main_window = self
            while main_window and not hasattr(main_window, 'current_user'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                auth_token = getattr(main_window.current_user, '_api_token', None)
                logger.debug(f"✅ Got auth token from MainWindow.current_user: {bool(auth_token)}")
        except Exception as e:
            logger.warning(f"Could not get auth token from parent: {e}")

        # Always open in selection mode (not view-only)
        # User can search and select building even if already selected
        selected_building = show_building_map_dialog(
            db=self.context.db,
            selected_building_id=None,  # Always selection mode
            auth_token=auth_token,  # ✅ Pass auth token
            parent=self
        )

        if selected_building:
            # Update context and UI
            self.context.building = selected_building
            self.selected_building = selected_building

            # Update stats card with building data
            self.ui_building_type.setText(selected_building.building_type_display or "-")
            self.ui_building_status.setText(selected_building.building_status_display or "-")
            self.ui_units_count.setText(str(selected_building.number_of_units))
            self.ui_parcels_count.setText(str(getattr(selected_building, 'number_of_apartments', 0)))
            self.ui_shops_count.setText(str(selected_building.number_of_shops))

            # Show stats card
            self.stats_card.setVisible(True)

            # Update location card with building data
            self.ui_general_desc.setText(getattr(selected_building, 'general_description', tr("wizard.building.general_description_fallback")))
            self.ui_location_desc.setText(getattr(selected_building, 'location_description', tr("wizard.building.location_description")))

            # Show location card
            self.location_card.setVisible(True)

            # Hide suggestions list
            self.buildings_list.setVisible(False)

            # UX Enhancement: Clear search field to allow searching again
            self.building_search.clear()

            # Emit validation changed
            self.emit_validation_changed(True)

    def _open_map_dialog(self):
        """
        Open map dialog to VIEW the currently selected building.

        ✅ DRY: Uses show_building_map_dialog helper (unified across app)
        ✅ View-only mode: Shows selected building with focus (no re-selection)
        """
        from ui.components.building_map_dialog_v2 import show_building_map_dialog

        # Get auth token
        auth_token = None
        try:
            main_window = self
            while main_window and not hasattr(main_window, 'current_user'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                auth_token = getattr(main_window.current_user, '_api_token', None)
        except Exception as e:
            logger.warning(f"Could not get auth token: {e}")

        # If we already have a selected building, open in VIEW-ONLY mode
        if hasattr(self, 'selected_building') and self.selected_building:
            # ✅ VIEW-ONLY MODE: Just show the building, don't allow re-selection
            show_building_map_dialog(
                db=self.context.db,
                selected_building_id=self.selected_building.building_id,
                auth_token=auth_token,
                read_only=True,  # ✅ View-only: focus on building
                parent=self
            )
            return  # ✅ Don't process result (view-only, not selection)

        # If no building selected yet, open in SELECTION mode
        selected_building = show_building_map_dialog(
            db=self.context.db,
            selected_building_id=None,
            auth_token=auth_token,
            read_only=False,  # Selection mode
            parent=self
        )

        if selected_building:
            # Update context and UI
            self.context.building = selected_building
            self.selected_building = selected_building

            # Update stats card
            self.ui_building_type.setText(selected_building.building_type_display or "-")
            self.ui_building_status.setText(selected_building.building_status_display or "-")
            self.ui_units_count.setText(str(selected_building.number_of_units))
            self.ui_parcels_count.setText(str(getattr(selected_building, 'number_of_apartments', 0)))
            self.ui_shops_count.setText(str(selected_building.number_of_shops))

            # Update location card
            self.ui_general_desc.setText(getattr(selected_building, 'general_description', tr("wizard.building.general_description_fallback")))
            self.ui_location_desc.setText(getattr(selected_building, 'location_description', tr("wizard.building.location_description")))

            # Show cards
            self.stats_card.setVisible(True)
            self.location_card.setVisible(True)

            # Hide suggestions list after selection
            self.buildings_list.setVisible(False)

            # UX Enhancement: Clear search field to allow searching again
            self.building_search.clear()

            # Emit validation changed
            self.emit_validation_changed(True)

    def _load_buildings(self):
        """Load buildings into the list."""
        # Load first 100 buildings only for performance (use search for specific buildings)
        building_filter = BuildingFilter(limit=100)
        result = self.building_controller.load_buildings(building_filter)
        self.buildings_list.clear()

        if not result.success:
            logger.error(f"Failed to load buildings: {result.message}")
            return

        buildings = result.data
        for building in buildings:
            # Create item with building info
            item_text = (
                f"{building.building_id} | "
                f"{tr('wizard.building.type_prefix', value=building.building_type_display)} | "
                f"{tr('wizard.building.status_prefix', value=building.building_status_display)}"
            )
            item = QListWidgetItem(item_text)

            # Add blue.png icon (DRY: same icon as card header)
            from ui.components.icon import Icon
            icon_pixmap = Icon.load_pixmap("blue", size=24)
            if icon_pixmap and not icon_pixmap.isNull():
                item.setIcon(QIcon(icon_pixmap))

            # Apply font: same as subtitle (DRY: create_font + Colors.WIZARD_SUBTITLE)
            font = create_font(size=10, weight=FontManager.WEIGHT_REGULAR)
            item.setFont(font)
            item.setForeground(QColor(Colors.WIZARD_SUBTITLE))

            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _filter_buildings(self):
        """Filter buildings list based on search text (with lazy loading)."""
        # Lazy load: Load buildings on first search if not already loaded
        if self.buildings_list.count() == 0:
            self._load_buildings()

        search_text = self.building_search.text().lower()
        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            item.setHidden(search_text not in item.text().lower())

    def _search_buildings(self):
        """Search buildings via API or local database."""
        # Ensure auth token is set on building controller
        self._set_building_controller_auth()

        search = self.building_search.text().strip()

        if search:
            result = self.building_controller.search_buildings(search)
        else:
            # Load first 100 buildings only
            building_filter = BuildingFilter(limit=100)
            result = self.building_controller.load_buildings(building_filter)

        self.buildings_list.clear()

        if not result.success:
            logger.error(f"Failed to search buildings: {result.message}")
            return

        buildings = result.data
        for building in buildings:
            # Create item with building info
            item_text = (
                f"{building.building_id} | "
                f"{tr('wizard.building.type_prefix', value=building.building_type_display)}"
            )
            item = QListWidgetItem(item_text)

            # Add blue.png icon (DRY: same icon as card header)
            from ui.components.icon import Icon
            icon_pixmap = Icon.load_pixmap("blue", size=24)
            if icon_pixmap and not icon_pixmap.isNull():
                item.setIcon(QIcon(icon_pixmap))

            # Apply font: same as subtitle (DRY: create_font + Colors.WIZARD_SUBTITLE)
            font = create_font(size=10, weight=FontManager.WEIGHT_REGULAR)
            item.setFont(font)
            item.setForeground(QColor(Colors.WIZARD_SUBTITLE))

            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _on_building_selected(self, item):
        """Handle building selection."""
        building = item.data(Qt.UserRole)
        self.context.building = building
        self.selected_building = building

        # Update stats card with building data
        self.ui_building_type.setText(building.building_type_display or "-")
        self.ui_building_status.setText(building.building_status_display or "-")
        # TODO: Get actual counts from building object
        self.ui_units_count.setText(str(building.number_of_units))
        self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
        self.ui_shops_count.setText(str(building.number_of_shops))

        # Show stats card
        self.stats_card.setVisible(True)

        # Update location card with building data
        self.ui_general_desc.setText(getattr(building, 'general_description', tr("wizard.building.general_description_fallback")))
        self.ui_location_desc.setText(getattr(building, 'location_description', tr("wizard.building.location_description")))

        # Update map thumbnail if coordinates are available
        if hasattr(building, 'latitude') and hasattr(building, 'longitude'):
            # TODO: Load actual map thumbnail from coordinates
            pass

        # Show location card
        self.location_card.setVisible(True)

        # Hide suggestions list after selection
        self.buildings_list.setVisible(False)

        # UX Enhancement: Clear search field to allow searching again
        # This allows user to easily search for a different building if they made a mistake
        self.building_search.clear()

        # Emit validation changed
        self.emit_validation_changed(True)

        logger.info(f"Building selected: {building.building_id}")

    def _on_building_confirmed(self, item):
        """Double-click to confirm and proceed."""
        self._on_building_selected(item)
        # Note: The old wizard calls self._on_next() here, but we don't have that in the step
        # The wizard controller will handle navigation

    def _open_polygon_selector_dialog(self):
        """
        تم إزالة هذه الوظيفة - الآن يتم استخدام الخريطة الموحدة

        DEPRECATED: This functionality has been removed as per user request.
        Polygon selection is now integrated into the unified map view.
        Use _open_map_search_dialog() instead which provides the same functionality.
        """
        ErrorHandler.show_warning(
            self,
            tr("wizard.building.use_map_search"),
            tr("wizard.building.info_title")
        )
        return
        try:
            from ui.components.polygon_building_selector_dialog import PolygonBuildingSelectorDialog

            # Open dialog
            dialog = PolygonBuildingSelectorDialog(self.context.db, self)
            buildings = dialog.exec_and_get_buildings()

            if not buildings:
                logger.info("No buildings selected from polygon")
                return

            # If only one building, select it automatically
            if len(buildings) == 1:
                building = buildings[0]
                self.context.building = building
                self.selected_building = building

                # Update stats card
                self.ui_building_type.setText(building.building_type_display or "-")
                self.ui_building_status.setText(building.building_status_display or "-")
                self.ui_units_count.setText(str(building.number_of_units))
                self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
                self.ui_shops_count.setText(str(building.number_of_shops))
                self.stats_card.setVisible(True)

                # Update location card
                self.ui_general_desc.setText(getattr(building, 'general_description', tr("wizard.building.general_description_fallback")))
                self.ui_location_desc.setText(getattr(building, 'location_description', tr("wizard.building.location_description")))
                self.location_card.setVisible(True)

                self.buildings_list.setVisible(False)

                # UX Enhancement: Clear search field to allow searching again
                self.building_search.clear()

                self.emit_validation_changed(True)

                logger.info(f"Building auto-selected from polygon: {building.building_id}")

            else:
                # Multiple buildings - show selection dialog
                self._show_building_selection_dialog(buildings)

        except Exception as e:
            logger.error(f"Error opening polygon selector: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                tr("wizard.building.polygon_error", details=str(e)),
                tr("wizard.building.polygon_error_title")
            )

    def _show_building_selection_dialog(self, buildings):
        """
        Show dialog to select one building from multiple candidates.

        Args:
            buildings: List of Building objects
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("wizard.building.select_dialog_title", count=len(buildings)))
        dialog.setMinimumWidth(500)
        dialog.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # Instructions
        info_label = QLabel(tr("wizard.building.select_dialog_instructions", count=len(buildings)))
        info_label.setStyleSheet("""
            QLabel {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                color: #2C3E50;
                padding: 8px;
            }
        """)
        layout.addWidget(info_label)

        # Buildings list
        buildings_list = QListWidget()
        buildings_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #EFF6FF;
            }
        """)

        for building in buildings:
            item_text = (
                f"🏢 {building.building_id} | "
                f"{tr('wizard.building.type_prefix', value=building.building_type_display)} | "
                f"{tr('wizard.building.status_prefix', value=building.building_status_display)}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, building)
            buildings_list.addItem(item)

        layout.addWidget(buildings_list)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        select_btn = QPushButton(f"✓ {tr('wizard.building.select_button')}")
        select_btn.setMinimumHeight(36)
        select_btn.setStyleSheet("""
            QPushButton {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                font-weight: 600;
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2E7BC6;
            }
            QPushButton:disabled {
                background-color: #D1E8FF;
            }
        """)
        select_btn.setEnabled(False)

        cancel_btn = QPushButton(f"✕ {tr('wizard.building.cancel_button')}")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                background-color: #F1F5F9;
                color: #64748B;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E8EFF6;
            }
        """)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(select_btn)
        layout.addLayout(buttons_layout)

        # Connect signals
        def on_selection_changed():
            select_btn.setEnabled(buildings_list.currentItem() is not None)

        def on_select():
            current_item = buildings_list.currentItem()
            if current_item:
                dialog.accept()

        buildings_list.itemSelectionChanged.connect(on_selection_changed)
        buildings_list.itemDoubleClicked.connect(lambda: on_select())
        select_btn.clicked.connect(on_select)
        cancel_btn.clicked.connect(dialog.reject)

        # Show dialog
        result = dialog.exec_()

        if result == QDialog.Accepted:
            current_item = buildings_list.currentItem()
            if current_item:
                building = current_item.data(Qt.UserRole)
                self.context.building = building
                self.selected_building = building

                # Update stats card
                self.ui_building_type.setText(building.building_type_display or "-")
                self.ui_building_status.setText(building.building_status_display or "-")
                self.ui_units_count.setText(str(building.number_of_units))
                self.ui_parcels_count.setText(str(getattr(building, 'number_of_apartments', 0)))
                self.ui_shops_count.setText(str(building.number_of_shops))
                self.stats_card.setVisible(True)

                # Update location card
                self.ui_general_desc.setText(getattr(building, 'general_description', tr("wizard.building.general_description_fallback")))
                self.ui_location_desc.setText(getattr(building, 'location_description', tr("wizard.building.location_description")))
                self.location_card.setVisible(True)

                self.buildings_list.setVisible(False)

                # UX Enhancement: Clear search field to allow searching again
                self.building_search.clear()

                self.emit_validation_changed(True)

                logger.info(f"Building selected from polygon list: {building.building_id}")

    def validate(self) -> StepValidationResult:
        """Validate the step and create survey via API."""
        result = self.create_validation_result()

        if not self.selected_building:
            result.add_error(tr("wizard.building.must_select"))
            return result

        # Create survey via API when clicking Next
        if self._use_api:
            # Set auth token
            self._set_auth_token()

            building_uuid = getattr(self.selected_building, 'building_uuid', '') or ''
            survey_data = {"building_uuid": building_uuid}

            logger.info(f"Creating office survey for building: {building_uuid}")

            try:
                survey_response = self._survey_api_service.create_office_survey(survey_data)

                survey_id = survey_response.get("id") or survey_response.get("surveyId", "")
                self.context.update_data("survey_id", survey_id)
                self.context.update_data("survey_data", survey_response)
                print(f"[SURVEY] Survey created successfully, survey_id: {survey_id}")
                print(f"[SURVEY] Full API response: {survey_response}")
                logger.info(f"Survey created successfully, survey_id: {survey_id}")

            except Exception as e:
                logger.error(f"Failed to create survey: {e}", exc_info=True)
                user_msg = map_exception(e, context="survey")
                result.add_error(user_msg)
                return result

        return result

    def _set_auth_token(self):
        """Set auth token for survey API service from main window."""
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._survey_api_service.set_access_token(main_window._api_token)

    def _set_building_controller_auth(self):
        """Set auth token for building controller API service."""
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self.building_controller.set_auth_token(main_window._api_token)

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "building_id": self.selected_building.building_id if self.selected_building else None,
            "building_uuid": self.selected_building.building_uuid if self.selected_building else None
        }

    def populate_data(self):
        """Populate the step with data from context."""
        if self.context.building:
            self.selected_building = self.context.building
            # Set search text and trigger search
            self.building_search.setText(self.context.building.building_id)
            self._search_buildings()

            # Update stats card
            self.ui_building_type.setText(self.context.building.building_type_display or "-")
            self.ui_building_status.setText(self.context.building.building_status_display or "-")
            self.ui_units_count.setText(str(self.context.building.number_of_units))
            self.ui_parcels_count.setText(str(getattr(self.context.building, 'number_of_apartments', 0)))
            self.ui_shops_count.setText(str(self.context.building.number_of_shops))
            self.stats_card.setVisible(True)

            # Update location card
            self.ui_general_desc.setText(getattr(self.context.building, 'general_description', tr("wizard.building.general_description_fallback")))
            self.ui_location_desc.setText(getattr(self.context.building, 'location_description', tr("wizard.building.location_description")))
            self.location_card.setVisible(True)

            # Emit validation
            self.emit_validation_changed(True)
        else:
            # Clear all UI when no building selected (new survey)
            self.selected_building = None
            self.stats_card.setVisible(False)
            self.location_card.setVisible(False)
            self.emit_validation_changed(False)

    def get_step_title(self) -> str:
        """Get step title."""
        return tr("wizard.building.step_title")

    def get_step_description(self) -> str:
        """Get step description."""
        return tr("wizard.building.step_description")
