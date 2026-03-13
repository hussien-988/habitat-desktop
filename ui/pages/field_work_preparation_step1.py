# -*- coding: utf-8 -*-
"""
    Field Work Preparation - Step 1: Select Buildings
    UC-012: Assign Buildings to Field Teams

    Filter and search buildings for field work assignment.
    REUSES design from BuildingSelectionStep (office_survey wizard)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QToolButton, QSizePolicy,
    QListWidget, QListWidgetItem, QCheckBox, QGraphicsDropShadowEffect,
    QScrollArea
    )
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QColor

from controllers.building_controller import BuildingController
from services.api_client import get_api_client
from ui.components.icon import Icon
from ui.components.wizard_header import WizardHeader
from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingCheckboxItem(QWidget):
    """Custom checkbox item for building list."""

    def __init__(self, building, parent=None):
        super().__init__(parent)
        self.building = building
        self.setCursor(Qt.PointingHandCursor)  # Make entire row clickable

        # Set minimum height
        self.setMinimumHeight(56)  # Unified height

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)  # Unified padding
        layout.setSpacing(16)  # Unified spacing

        # === Checkbox with checkmark overlay (like wizard) ===
        checkbox_container = QWidget()
        checkbox_container.setFixedSize(20, 20)

        # Checkbox - border only (no content) - positioned at (0,0)
        self.checkbox = QCheckBox(checkbox_container)
        self.checkbox.setGeometry(0, 0, 20, 20)
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #3890DF;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: white;
                border-color: #3890DF;
            }
            QCheckBox::indicator:hover {
                border-color: #3890DF;
            }
        """)

        # Checkmark overlay (only visible when checked) - overlaid on top at (0,0)
        self.check_label = QLabel("✓", checkbox_container)
        self.check_label.setGeometry(0, 0, 20, 20)
        self.check_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        self.check_label.setAlignment(Qt.AlignCenter)
        self.check_label.setVisible(False)  # Hidden by default
        # Make checkmark transparent to mouse clicks (so checkbox underneath can be clicked)
        self.check_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Update checkmark visibility when checkbox state changes
        self.checkbox.stateChanged.connect(lambda state: self.check_label.setVisible(state == Qt.Checked))

        layout.addWidget(checkbox_container)

        # Icon container - Unified: 32×32px with #f0f7ff background (using building-03)
        icon_container = QLabel()
        icon_container.setFixedSize(32, 32)
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet("""
            QLabel {
                background-color: #f0f7ff;
                border-radius: 6px;
            }
        """)
        icon_pixmap = Icon.load_pixmap("building-03", size=20)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            icon_container.setText("🏢")
        layout.addWidget(icon_container)

        # Text with formatted building ID - using PAGE_SUBTITLE color
        formatted_id = self._format_building_id_static(building.building_id)
        item_text = (
            f"{formatted_id} | "
            f"النوع: {building.building_type_display} | "
            f"الحالة: {building.building_status_display}"
        )
        text_label = QLabel(item_text)
        text_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        text_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
        layout.addWidget(text_label, 1)

    def mousePressEvent(self, event):
        """Handle click on entire row - toggle checkbox."""
        self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)

    @staticmethod
    def _format_building_id_static(building_id: str) -> str:
        """
        Format building ID with dashes (17 digits: XX-XX-XX-XX-XX-XX-XX-XX-X).
        Static version for BuildingCheckboxItem.
        """
        if not building_id:
            return ""

        # Remove any existing dashes
        clean_id = building_id.replace("-", "")

        # Format: 2-2-2-2-2-2-2-2-1 (17 digits total)
        if len(clean_id) >= 17:
            formatted = f"{clean_id[0:2]}-{clean_id[2:4]}-{clean_id[4:6]}-{clean_id[6:8]}-{clean_id[8:10]}-{clean_id[10:12]}-{clean_id[12:14]}-{clean_id[14:16]}-{clean_id[16]}"
            return formatted

        # Return as-is if not 17 digits
        return building_id


class ClickableRowWidget(QWidget):
    """Widget for table row that toggles checkbox when clicked."""

    def __init__(self, checkbox, parent=None):
        super().__init__(parent)
        self.checkbox = checkbox
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle click on entire row - toggle checkbox."""
        self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)


class FieldWorkPreparationStep1(QWidget):
    """
    Step 1: Filter and search buildings.

    Original structure with its own header and footer.
    """

    next_clicked = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, building_controller: BuildingController, i18n: I18n, parent=None):
        super().__init__(parent)
        self.building_controller = building_controller
        self.i18n = i18n
        self.page = parent  # Store reference to parent page
        self._selected_building_ids = set()  # Buildings shown in table (may be unchecked)
        self._confirmed_building_ids = set()  # Buildings confirmed for transfer (checked only)

        # Cache for filter data (from API)
        self._all_communities = []  # [(code, name_ar), ...]
        self._all_neighborhoods = []  # [(code, name_ar, community_code), ...]

        self._setup_ui()
        self._load_filter_data()

        # Install event filter to detect clicks outside suggestions
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def _setup_ui(self):
        """Setup UI - content only (no header/footer)."""
        self.setLayoutDirection(Qt.RightToLeft)

        # Background
        self.setStyleSheet("background: transparent;")

        # === MAIN LAYOUT (No padding - parent has padding) ===
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === CARDS CONTAINER ===
        cards_container = QWidget()
        cards_container.setStyleSheet("background-color: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 15, 0, 16)
        cards_layout.setSpacing(15)

        # ===== Card: تصفية المباني (NO icon, NO title, NO subtitle) =====
        card = QFrame()
        card.setObjectName("filterCard")
        card.setStyleSheet("""
            QFrame#filterCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)

        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        card_layout = QVBoxLayout(card)
        # Padding: 12px all sides
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        # === 3 Filter Fields in ONE ROW ===
        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(12)

        # Filter 1: المجتمع (Community)
        filter1_container = self._create_filter_field("المجتمع")
        self.community_combo = QComboBox()
        self.community_combo.setPlaceholderText("اختر المجتمع")
        self._style_combo(self.community_combo, "اختر المجتمع")
        self.community_combo.currentIndexChanged.connect(self._on_community_changed)
        filter1_container.layout().addWidget(self.community_combo)
        filters_layout.addWidget(filter1_container, 1)

        # Filter 2: الحي (Neighborhood) — cascading from community
        filter2_container = self._create_filter_field("الحي")
        self.neighborhood_combo = QComboBox()
        self.neighborhood_combo.setPlaceholderText("اختر الحي")
        self._style_combo(self.neighborhood_combo, "اختر الحي")
        self.neighborhood_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter2_container.layout().addWidget(self.neighborhood_combo)
        filters_layout.addWidget(filter2_container, 1)

        # Filter 3: حالة التعيين (Assignment Status)
        filter3_container = self._create_filter_field("حالة التعيين")
        self.assignment_status_combo = QComboBox()
        self.assignment_status_combo.setPlaceholderText("حالة التعيين")
        self._style_combo(self.assignment_status_combo, "حالة التعيين")
        self.assignment_status_combo.addItem("الكل", None)
        self.assignment_status_combo.addItem("غير معيّن", "false")
        self.assignment_status_combo.addItem("معيّن", "true")
        self.assignment_status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter3_container.layout().addWidget(self.assignment_status_combo)
        filters_layout.addWidget(filter3_container, 1)

        card_layout.addLayout(filters_layout)

        # === Label: رمز البناء ===
        search_label = QLabel("رمز البناء")
        search_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        search_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(search_label)

        # === Search bar - EXACT COPY from BuildingSelectionStep ===
        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setFixedHeight(42)
        search_bar.setStyleSheet(f"""
            QFrame#searchBar {{
                background-color: {Colors.SEARCH_BAR_BG};
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
            }}
        """)
        search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(search_bar)
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
        search_pixmap = Icon.load_pixmap("search", size=20)
        if search_pixmap and not search_pixmap.isNull():
            search_icon_btn.setIcon(QIcon(search_pixmap))
            search_icon_btn.setIconSize(QSize(20, 20))
        else:
            search_icon_btn.setText("🔍")

        search_icon_btn.clicked.connect(self._on_search)

        # Input
        self.building_search = QLineEdit()
        self.building_search.setPlaceholderText("ابحث عن رمز البناء ...")
        self.building_search.setLayoutDirection(Qt.RightToLeft)
        # Hide suggestions when Enter is pressed (Best Practice)
        self.building_search.returnPressed.connect(self._on_search_enter)
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
        self.building_search.textChanged.connect(self._on_search_text_changed)

        # "بحث على الخريطة" link button
        map_link_btn = QPushButton("بحث على الخريطة")
        map_link_btn.setCursor(Qt.PointingHandCursor)
        map_link_btn.setFlat(True)
        map_link_btn.setStyleSheet("""
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
        map_link_btn.clicked.connect(self._on_open_map)

        # Assemble search bar
        sb.addWidget(map_link_btn)
        sb.addWidget(self.building_search)
        sb.addWidget(search_icon_btn, 1)

        card_layout.addWidget(search_bar)

        cards_layout.addWidget(card)

        # === Suggestions list (SAME as BuildingSelectionStep, but with checkboxes) ===
        self.buildings_list = QListWidget()
        self.buildings_list.setVisible(False)
        self.buildings_list.setFixedHeight(0)  # Start collapsed (will be 179 when visible)
        self.buildings_list.setFixedWidth(1225)

        # Hide scrollbar but keep scrolling
        self.buildings_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.buildings_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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

        # Position list: overlaps with card's bottom padding
        cards_layout.addSpacing(-27)

        # Empty state label (shown when no buildings found)
        self.empty_label = QLabel("لا يوجد مباني")
        self.empty_label.setFixedWidth(1225)
        self.empty_label.setFixedHeight(179)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self.empty_label.setStyleSheet(f"""
            QLabel {{
                color: #9CA3AF;
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        self.empty_label.setVisible(False)

        # Center the list horizontally
        list_container = QHBoxLayout()
        list_container.addStretch(1)
        list_container.addWidget(self.buildings_list)
        list_container.addWidget(self.empty_label)
        list_container.addStretch(1)

        cards_layout.addLayout(list_container)

        # Correct spacing
        cards_layout.addSpacing(42)

        # === Selected Buildings Card ===
        self.selected_buildings_card = QFrame()
        self.selected_buildings_card.setObjectName("selectedBuildingsCard")
        self.selected_buildings_card.setVisible(False)
        self.selected_buildings_card.setFixedWidth(1249)
        self.selected_buildings_card.setStyleSheet("""
            QFrame#selectedBuildingsCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)
        self.selected_buildings_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        selected_card_layout = QVBoxLayout(self.selected_buildings_card)
        selected_card_layout.setContentsMargins(12, 12, 12, 12)
        selected_card_layout.setSpacing(12)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(4)

        label_title = QLabel("العناصر المحددة")
        label_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        label_title.setStyleSheet("color: #212B36; background: transparent;")
        header_row.addWidget(label_title)

        self.selected_count_label = QLabel("0 بناء")
        self.selected_count_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.selected_count_label.setStyleSheet("color: #3890DF; background: transparent;")
        header_row.addWidget(self.selected_count_label)

        header_row.addStretch()

        selected_card_layout.addLayout(header_row)

        # Table layout
        self.selected_table_layout = QVBoxLayout()
        self.selected_table_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_table_layout.setSpacing(0)

        selected_card_layout.addLayout(self.selected_table_layout)

        cards_layout.addWidget(self.selected_buildings_card)

        # Add cards to main layout
        main_layout.addWidget(cards_container)

        # Add stretch to push content to top
        main_layout.addStretch(1)

    def _create_footer(self):
        """Create footer with navigation buttons."""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top: 1px solid #E1E8ED;
            }
        """)
        footer.setFixedHeight(74)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(130, 12, 130, 12)
        layout.setSpacing(0)

        # Back button (disabled for Step 1)
        self.btn_back = QPushButton("<   السابق")
        self.btn_back.setFixedSize(252, 50)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_back = QGraphicsDropShadowEffect()
        shadow_back.setBlurRadius(8)
        shadow_back.setXOffset(0)
        shadow_back.setYOffset(2)
        shadow_back.setColor(QColor("#E5EAF6"))
        self.btn_back.setGraphicsEffect(shadow_back)

        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #414D5A;
                border: none;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #F8F9FA;
            }
            QPushButton:disabled {
                background-color: transparent;
                color: transparent;
                border: none;
            }
        """)
        self.btn_back.clicked.connect(self.cancelled.emit)
        self.btn_back.setEnabled(False)  # Disabled on Step 1
        layout.addWidget(self.btn_back)

        layout.addStretch()

        # Next button
        self.btn_next = QPushButton("التالي   >")
        self.btn_next.setFixedSize(252, 50)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_next = QGraphicsDropShadowEffect()
        shadow_next.setBlurRadius(8)
        shadow_next.setXOffset(0)
        shadow_next.setYOffset(2)
        shadow_next.setColor(QColor("#E5EAF6"))
        self.btn_next.setGraphicsEffect(shadow_next)

        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #f0f7ff;
                color: #3890DF;
                border: 1px solid #3890DF;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #E3F2FD;
            }
            QPushButton:disabled {
                background-color: #F8F9FA;
                color: #9CA3AF;
                border-color: #E1E8ED;
            }
        """)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_next.setEnabled(False)  # Initially disabled
        layout.addWidget(self.btn_next)

        return footer

    def _create_filter_field(self, label_text: str) -> QFrame:
        """Create filter field container with label (DRY)."""
        container = QFrame()
        container.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        layout.addWidget(label)

        return container

    def _get_down_icon_path(self) -> str:
        """Get absolute path to down.png icon."""
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        # Try multiple locations
        search_paths = [
            base_path / "assets" / "images" / "down.png",
            base_path / "assets" / "icons" / "down.png",
            base_path / "assets" / "down.png",
        ]

        for path in search_paths:
            if path.exists():
                return str(path).replace("\\", "/")

        return ""

    def _style_combo(self, combo: QComboBox, placeholder: str = ""):
        """Apply consistent styling to combo boxes (SAME as search bar height)."""
        combo.setFixedHeight(42)
        combo.setEditable(True)
        combo.lineEdit().setReadOnly(True)
        combo.lineEdit().setPlaceholderText(placeholder)
        combo.lineEdit().installEventFilter(self)

        # Load down.png icon
        down_icon_path = self._get_down_icon_path()

        if down_icon_path:
            combo.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid {Colors.SEARCH_BAR_BORDER};
                    border-radius: 8px;
                    padding: 8px 14px;
                    padding-left: 35px;
                    background-color: {Colors.SEARCH_BAR_BG};
                    color: #6c757d;
                    font-family: 'IBM Plex Sans Arabic';
                    font-size: 9pt;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 30px;
                    subcontrol-position: right center;
                }}
                QComboBox::down-arrow {{
                    image: url({down_icon_path});
                    width: 12px;
                    height: 12px;
                }}
                QComboBox QAbstractItemView {{
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    background-color: white;
                    selection-background-color: #EFF6FF;
                    color: #6c757d;
                    font-family: 'IBM Plex Sans Arabic';
                    font-size: 9pt;
                    outline: none;
                }}
                QComboBox QAbstractItemView::item {{
                    padding: 8px 12px;
                    color: #6c757d;
                }}
                QScrollBar:vertical {{
                    width: 0px;
                }}
                QScrollBar:horizontal {{
                    height: 0px;
                }}
                QLineEdit {{
                    border: none;
                    background: transparent;
                    font-family: 'IBM Plex Sans Arabic';
                    font-size: 9pt;
                    padding: 0px;
                    color: #6c757d;
                }}
            """)
        else:
            combo.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid {Colors.SEARCH_BAR_BORDER};
                    border-radius: 8px;
                    padding: 8px 14px;
                    padding-left: 35px;
                    background-color: {Colors.SEARCH_BAR_BG};
                    color: #6c757d;
                    font-family: 'IBM Plex Sans Arabic';
                    font-size: 9pt;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 30px;
                    subcontrol-position: right center;
                }}
                QComboBox::down-arrow {{
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #606266;
                    width: 0;
                    height: 0;
                }}
                QComboBox QAbstractItemView {{
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    background-color: white;
                    selection-background-color: #EFF6FF;
                    color: #6c757d;
                    font-family: 'IBM Plex Sans Arabic';
                    font-size: 9pt;
                    outline: none;
                }}
                QComboBox QAbstractItemView::item {{
                    padding: 8px 12px;
                    color: #6c757d;
                }}
                QScrollBar:vertical {{
                    width: 0px;
                }}
                QScrollBar:horizontal {{
                    height: 0px;
                }}
                QLineEdit {{
                    border: none;
                    background: transparent;
                    font-family: 'IBM Plex Sans Arabic';
                    font-size: 9pt;
                    padding: 0px;
                    color: #6c757d;
                }}
            """)

    def _load_filter_data(self):
        """Load communities and neighborhoods from API."""
        try:
            api = get_api_client()

            # Load communities (Aleppo: gov=01, dist=01, subdist=01)
            communities = api.get_communities(
                governorate_code="01", district_code="01", sub_district_code="01"
            )
            for c in communities:
                if c.get("isActive", True):
                    code = c.get("code", "")
                    name_ar = c.get("nameArabic", "") or c.get("nameEnglish", "")
                    if code and name_ar:
                        self._all_communities.append((code, name_ar))
            self._all_communities.sort(key=lambda x: x[1])

            # Populate community combo
            self.community_combo.addItem("الكل", None)
            for code, name_ar in self._all_communities:
                self.community_combo.addItem(name_ar, code)

            # Load all neighborhoods (Aleppo)
            neighborhoods = api.get_neighborhoods(
                governorate_code="01", district_code="01", subdistrict_code="01"
            )
            for n in neighborhoods:
                code = n.get("neighborhoodCode") or n.get("code", "")
                name_ar = n.get("nameArabic", "") or n.get("nameEnglish", "")
                comm_code = n.get("communityCode", "")
                if code and name_ar:
                    self._all_neighborhoods.append((code, name_ar, comm_code))
            self._all_neighborhoods.sort(key=lambda x: x[1])

            # Populate neighborhood combo (all initially)
            self.neighborhood_combo.addItem("الكل", None)
            for code, name_ar, _ in self._all_neighborhoods:
                self.neighborhood_combo.addItem(name_ar, code)

            logger.info(
                f"Loaded {len(self._all_communities)} communities, "
                f"{len(self._all_neighborhoods)} neighborhoods from API"
            )

        except Exception as e:
            logger.error(f"Error loading filter data from API: {e}", exc_info=True)

    def _on_community_changed(self, index):
        """Cascade: update neighborhoods based on selected community."""
        community_code = self.community_combo.currentData()

        self.neighborhood_combo.blockSignals(True)
        self.neighborhood_combo.clear()
        self.neighborhood_combo.addItem("الكل", None)

        if community_code:
            # Filter neighborhoods by community
            for code, name_ar, comm_code in self._all_neighborhoods:
                if comm_code == community_code:
                    self.neighborhood_combo.addItem(name_ar, code)
        else:
            # Show all neighborhoods
            for code, name_ar, _ in self._all_neighborhoods:
                self.neighborhood_combo.addItem(name_ar, code)

        self.neighborhood_combo.blockSignals(False)
        self._on_filter_changed()

    def _on_checkbox_changed(self, building, state):
        """Handle checkbox state change in suggestions list."""
        if state == Qt.Checked:
            # Add to both sets: selected (in table) and confirmed (for transfer)
            self._selected_building_ids.add(building.building_id)
            self._confirmed_building_ids.add(building.building_id)
            self._add_building_to_table(building)
        else:
            # Remove from both sets and table
            self._selected_building_ids.discard(building.building_id)
            self._confirmed_building_ids.discard(building.building_id)
            self._remove_building_from_table(building.building_id)

        self._update_selection_count()
        self._update_selected_card_visibility()

        # Return focus to search field so Enter key works for dismissing suggestions
        self.building_search.setFocus()

    def _on_table_checkbox_changed(self, building_id: str, state):
        """
        Handle checkbox state change in selected buildings table.

        NOTE: Unlike suggestions list, unchecking here does NOT remove the row.
        It only toggles the "confirmed for transfer" status.
        """
        if state == Qt.Checked:
            # Add to confirmed set (for transfer)
            self._confirmed_building_ids.add(building_id)
        else:
            # Remove from confirmed set (but keep in table)
            self._confirmed_building_ids.discard(building_id)

        # Update count and button state
        self._update_selection_count()

    def _update_selection_count(self):
        """Update selection count and button state (based on CONFIRMED buildings only)."""
        count = len(self._confirmed_building_ids)  # Only confirmed buildings count
        # Enable/disable next button via parent page
        if self.page and hasattr(self.page, 'enable_next_button'):
            self.page.enable_next_button(count > 0)

    def _update_selected_card_visibility(self):
        """
        Show/hide selected buildings card based on selection count.

        Card is visible whenever there are selected buildings, regardless of
        whether the suggestions list is open or closed.
        """
        has_selection = len(self._selected_building_ids) > 0
        self.selected_buildings_card.setVisible(has_selection)

        # Update header count (confirmed buildings only)
        count = len(self._confirmed_building_ids)
        self.selected_count_label.setText(f"{count} بناء")

    def _add_building_to_table(self, building):
        """
        Add building row to selected buildings table.

        Row format (from Figma):
        - Checkbox (to unselect - cleaner UX)
        - Building icon (32×32px with #f0f7ff background)
        - Building ID (formatted: 01-01-01-...)
        """
        # Skip if already in table (prevents duplicates on list rebuild)
        for i in range(self.selected_table_layout.count()):
            widget = self.selected_table_layout.itemAt(i).widget()
            if widget and widget.objectName() == f"row_{building.building_id}":
                return

        # === Checkbox with checkmark overlay (unified with suggestions) ===
        checkbox_container = QWidget()
        checkbox_container.setFixedSize(20, 20)

        # Checkbox - border only - positioned at (0,0)
        checkbox = QCheckBox(checkbox_container)
        checkbox.setGeometry(0, 0, 20, 20)
        checkbox.setChecked(True)  # Already selected and confirmed
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #3890DF;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: white;
                border-color: #3890DF;
            }
            QCheckBox::indicator:hover {
                border-color: #3890DF;
            }
        """)

        # Checkmark overlay (same as suggestions list) - overlaid on top at (0,0)
        check_label = QLabel("✓", checkbox_container)
        check_label.setGeometry(0, 0, 20, 20)
        check_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        check_label.setAlignment(Qt.AlignCenter)
        check_label.setVisible(True)  # Visible by default (checked)
        # Make checkmark transparent to mouse clicks (so checkbox underneath can be clicked)
        check_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Update checkmark visibility when checkbox state changes
        checkbox.stateChanged.connect(lambda state: check_label.setVisible(state == Qt.Checked))

        # Connect to handler
        checkbox.stateChanged.connect(
            lambda state, bid=building.building_id: self._on_table_checkbox_changed(bid, state)
        )

        # Create row container (clickable)
        row = ClickableRowWidget(checkbox)
        row.setObjectName(f"row_{building.building_id}")
        row._building_obj = building
        row.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        row.setMinimumHeight(32)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 3, 0, 0)  # Margin top only (3px)
        row_layout.setSpacing(16)  # Logical spacing between elements

        row_layout.addWidget(checkbox_container)

        # === Icon in 32×32 square with #f0f7ff background ===
        icon_container = QLabel()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet("""
            QLabel {
                background-color: #f0f7ff;
                border-radius: 6px;
            }
        """)
        icon_container.setAlignment(Qt.AlignCenter)

        # Try to load building-03 icon
        icon_pixmap = Icon.load_pixmap("building-03", size=20)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            # Fallback: use emoji
            icon_container.setText("🏢")
            icon_container.setStyleSheet("""
                QLabel {
                    background-color: #f0f7ff;
                    border-radius: 6px;
                    font-size: 16px;
                }
            """)
        row_layout.addWidget(icon_container)

        # === Building ID (formatted with dashes) - unified with suggestions ===
        formatted_id = self._format_building_id(building.building_id)
        id_label = QLabel(formatted_id)
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        id_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
        row_layout.addWidget(id_label)

        row_layout.addStretch()

        # No remove button - checkbox is enough for unselecting

        # Add row to table
        self.selected_table_layout.addWidget(row)

    def _format_building_id(self, building_id: str) -> str:
        """
        Format building ID with dashes (17 digits: XX-XX-XX-XX-XX-XX-XX-XX-X).

        Example: 01010101010101010 → 01-01-01-01-01-01-01-01-0
        """
        if not building_id:
            return ""

        # Remove any existing dashes
        clean_id = building_id.replace("-", "")

        # Format: 2-2-2-2-2-2-2-2-1 (17 digits total)
        if len(clean_id) >= 17:
            formatted = f"{clean_id[0:2]}-{clean_id[2:4]}-{clean_id[4:6]}-{clean_id[6:8]}-{clean_id[8:10]}-{clean_id[10:12]}-{clean_id[12:14]}-{clean_id[14:16]}-{clean_id[16]}"
            return formatted
        else:
            # If less than 17, just return as-is (or format what we have)
            return building_id

    def _remove_building_from_table(self, building_id: str):
        """Remove building row from table (DRY helper)."""
        # Find and remove the widget
        for i in range(self.selected_table_layout.count()):
            widget = self.selected_table_layout.itemAt(i).widget()
            if widget and widget.objectName() == f"row_{building_id}":
                self.selected_table_layout.removeWidget(widget)
                widget.deleteLater()
                break

    def _remove_building_selection(self, building_id: str):
        """
        Remove building from selection (triggered when unchecking from suggestions list).

        Updates:
        - Both selection sets (selected and confirmed)
        - Checkbox in list
        - Table row
        - Card visibility
        """
        # Remove from both sets
        self._selected_building_ids.discard(building_id)
        self._confirmed_building_ids.discard(building_id)

        # Uncheck checkbox in list
        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            widget = self.buildings_list.itemWidget(item)

            if widget and hasattr(widget, 'building'):
                if widget.building.building_id == building_id:
                    widget.checkbox.setChecked(False)
                    break

        # Remove from table
        self._remove_building_from_table(building_id)

        # Update UI
        self._update_selection_count()
        self._update_selected_card_visibility()

    def _set_suggestions_visible(self, visible: bool):
        """
        Show/hide suggestions list with proper height adjustment.

        This prevents spacing gaps when suggestions are hidden by collapsing the widget completely.

        Args:
            visible: True to show suggestions, False to hide
        """
        self.buildings_list.setVisible(visible)
        # Adjust height to prevent spacing gaps when hidden
        self.buildings_list.setFixedHeight(179 if visible else 0)
        if not visible:
            self.empty_label.setVisible(False)

    def _on_search_text_changed(self, text):
        """Show/hide suggestions on text change."""
        filters = self.get_filters()
        has_active_filter = any([
            filters['community'],
            filters['neighborhood'],
            filters['assignment_status'] is not None
        ])

        should_show = bool(text.strip()) or has_active_filter
        self._set_suggestions_visible(should_show)

        if has_active_filter or text.strip():
            self._load_buildings_from_api()

        self._update_selected_card_visibility()

    def _load_buildings_from_api(self):
        """Load buildings from Backend API with current filters."""
        filters = self.get_filters()

        # Parse assignment status
        has_active = None
        assignment_val = filters.get('assignment_status')
        if assignment_val == "false":
            has_active = False
        elif assignment_val == "true":
            has_active = True

        try:
            api = get_api_client()
            response = api.get_buildings_for_assignment(
                community_code=filters['community'],
                neighborhood_code=filters['neighborhood'],
                has_active_assignment=has_active,
                page=1,
                page_size=500
            )

            items = response.get("items", [])
            buildings = [self._api_dto_to_building(item) for item in items]

            # Apply local text search on top of API results
            search_text = self.building_search.text().lower().strip()
            if search_text:
                buildings = [
                    b for b in buildings
                    if search_text in (b.building_id.lower() if b.building_id else "")
                ]

            logger.info(f"Loaded {len(buildings)} buildings from API")
            self.buildings_list.clear()

            if buildings:
                self.empty_label.setVisible(False)
                self.buildings_list.setVisible(True)
                self.buildings_list.setFixedHeight(179)
                self._populate_buildings_list(buildings)
            else:
                self.buildings_list.setVisible(False)
                self.buildings_list.setFixedHeight(0)
                self.empty_label.setVisible(True)

        except Exception as e:
            logger.error(f"Failed to load buildings from API: {e}", exc_info=True)
            self.buildings_list.clear()

    def _api_dto_to_building(self, dto):
        """Convert API BuildingDto to Building object for UI."""
        from models.building import Building

        building = Building(
            building_id=dto.get("buildingCode", ""),
            building_uuid=dto.get("id", ""),
            building_type=dto.get("buildingType", 1),
            building_status=dto.get("buildingStatus", 1),
            latitude=dto.get("latitude"),
            longitude=dto.get("longitude"),
            number_of_units=dto.get("numberOfPropertyUnits", 0),
        )
        building.has_active_assignment = dto.get("hasActiveAssignment", False)
        building.current_assignment_id = dto.get("currentAssignmentId")
        building.current_assignee_name = dto.get("currentAssigneeName")

        return building

    def _populate_buildings_list(self, buildings):
        """Populate the suggestions list with building items."""
        for building in buildings:
            item = QListWidgetItem(self.buildings_list)
            widget = BuildingCheckboxItem(building, self)
            widget.checkbox.stateChanged.connect(
                lambda state, b=building: self._on_checkbox_changed(b, state)
            )
            if building.building_id in self._selected_building_ids:
                widget.checkbox.setChecked(True)
            item.setSizeHint(widget.sizeHint())
            self.buildings_list.addItem(item)
            self.buildings_list.setItemWidget(item, widget)

    def _on_filter_changed(self):
        """Handle filter change — calls API directly."""
        filters = self.get_filters()
        logger.debug(f"Filters changed: {filters}")

        has_active_filter = any([
            filters['community'],
            filters['neighborhood'],
            filters['assignment_status'] is not None
        ])

        if has_active_filter or filters['search_text']:
            self._load_buildings_from_api()
        else:
            self.buildings_list.clear()

    def _on_search(self):
        """Handle search icon click - show suggestions with filtered results."""
        search_text = self.building_search.text().strip()
        logger.debug(f"Searching for: {search_text}")

        self._load_buildings_from_api()

        self._set_suggestions_visible(True)
        self._update_selected_card_visibility()

    def _on_open_map(self):
        """Open map dialog with polygon drawing for multi-building selection."""
        try:
            from ui.components.polygon_map_dialog_v2 import show_polygon_map_dialog

            auth_token = None
            try:
                main_window = self
                while main_window and not hasattr(main_window, 'current_user'):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                    auth_token = getattr(main_window.current_user, '_api_token', None)
            except Exception as e:
                logger.warning(f"Could not get auth token: {e}")

            selected_buildings = show_polygon_map_dialog(
                db=self.building_controller.db,
                auth_token=auth_token,
                parent=self
            )

            # User cancelled or no buildings selected
            logger.info(f"Received from polygon map dialog: {type(selected_buildings)}")
            logger.info(f"   Buildings count: {len(selected_buildings) if selected_buildings else 0}")

            if not selected_buildings:
                logger.info("No buildings selected from polygon")
                return

            # SOLID: Log received buildings for debugging
            logger.info(f"Received {len(selected_buildings)} buildings from polygon")
            for i, bldg in enumerate(selected_buildings[:3]):
                logger.info(f"   Building {i+1}: ID={bldg.building_id}")

            # Add selected buildings to current selection (multi-select)
            added_count = 0
            for building in selected_buildings:
                # Skip if already selected
                if building.building_id in self._selected_building_ids:
                    continue

                # Check if building exists in suggestions list
                # If so, checking the checkbox triggers _on_checkbox_changed which adds to table
                found_in_suggestions = False
                for i in range(self.buildings_list.count()):
                    item = self.buildings_list.item(i)
                    widget = self.buildings_list.itemWidget(item)
                    if widget and hasattr(widget, 'building'):
                        if widget.building.building_id == building.building_id:
                            widget.checkbox.setChecked(True)
                            found_in_suggestions = True
                            break

                # Only add directly if NOT in suggestions (avoid double-add)
                if not found_in_suggestions:
                    self._selected_building_ids.add(building.building_id)
                    self._confirmed_building_ids.add(building.building_id)
                    self._add_building_to_table(building)

                added_count += 1

            # Update UI
            self._update_selection_count()
            self._update_selected_card_visibility()

            # NO MESSAGE: Buildings are added directly to the list (silent operation)
            # User can see them in "العناصر المحفوظة" section
            logger.info(f"Added {added_count} buildings from polygon to selection (silent)")

        except Exception as e:
            logger.error(f"Error opening map selector: {e}", exc_info=True)
            from ui.error_handler import ErrorHandler
            ErrorHandler.show_warning(
                self,
                f"حدث خطأ أثناء فتح الخريطة:\n{str(e)}",
                "خطأ - Error"
            )

    def _on_next(self):
        """Handle next button click."""
        if self._selected_building_ids:
            self.next_clicked.emit()

    def get_filters(self) -> dict:
        """Get current filter values."""
        return {
            'community': self.community_combo.currentData() if self.community_combo.currentIndex() >= 0 else None,
            'neighborhood': self.neighborhood_combo.currentData() if self.neighborhood_combo.currentIndex() >= 0 else None,
            'assignment_status': self.assignment_status_combo.currentData() if self.assignment_status_combo.currentIndex() >= 0 else None,
            'search_text': self.building_search.text().strip()
        }

    def get_selected_building_ids(self):
        """Get list of selected building IDs."""
        return list(self._selected_building_ids)

    def get_selected_buildings(self):
        """Get list of confirmed (checked) building objects from suggestions list."""
        confirmed = []
        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            widget = self.buildings_list.itemWidget(item)
            if widget and hasattr(widget, 'building'):
                if widget.building.building_id in self._confirmed_building_ids:
                    confirmed.append(widget.building)

        # Also include buildings added via polygon map (not in suggestions)
        suggestion_ids = {b.building_id for b in confirmed}
        for bid in self._confirmed_building_ids:
            if bid not in suggestion_ids:
                # Check table rows for buildings added via polygon
                for j in range(self.selected_table_layout.count()):
                    row_widget = self.selected_table_layout.itemAt(j).widget()
                    if row_widget and hasattr(row_widget, '_building_obj'):
                        if row_widget._building_obj.building_id == bid:
                            confirmed.append(row_widget._building_obj)

        return confirmed

    def eventFilter(self, obj, event):
        """
        Event filter for:
        1. Combo box line edits — click anywhere opens dropdown
        2. Clicks outside suggestions list — dismiss suggestions
        """
        from PyQt5.QtCore import QEvent, QRect

        if event.type() == QEvent.MouseButtonPress:
            parent = obj.parent()
            if isinstance(parent, QComboBox):
                parent.showPopup()
                return True

        if event.type() == QEvent.MouseButtonPress and self.buildings_list.isVisible():
            # Check if click is inside suggestions list or search bar
            click_pos = event.globalPos()
            inside = False

            for widget in [self.buildings_list, self.building_search]:
                rect = widget.rect()
                global_tl = widget.mapToGlobal(rect.topLeft())
                global_rect = QRect(global_tl, rect.size())
                if global_rect.contains(click_pos):
                    inside = True
                    break

            if not inside:
                self.building_search.blockSignals(True)
                self.building_search.clear()
                self.building_search.blockSignals(False)
                self._set_suggestions_visible(False)
                self._update_selected_card_visibility()

        return super().eventFilter(obj, event)

    def _on_search_enter(self):
        """
        Handle Enter key press in search field (Best Practice).

        Clears search, hides suggestions, shows selected buildings card.
        """
        # Block signals to prevent textChanged from re-showing suggestions
        self.building_search.blockSignals(True)
        self.building_search.clear()
        self.building_search.blockSignals(False)

        self._set_suggestions_visible(False)
        self._update_selected_card_visibility()
