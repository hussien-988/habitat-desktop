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

        # Cache for filter data
        self._governorates = []
        self._subdistricts = []
        self._building_statuses = []

        self._setup_ui()
        self._load_filter_data()
        self._load_buildings()

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

        # Filter 1: الناحية (Subdistrict)
        filter1_container = self._create_filter_field("الناحية")
        self.subdistrict_combo = QComboBox()
        self.subdistrict_combo.setPlaceholderText("اسم الناحية")
        self._style_combo(self.subdistrict_combo, "اسم الناحية")
        self.subdistrict_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter1_container.layout().addWidget(self.subdistrict_combo)
        filters_layout.addWidget(filter1_container, 1)

        # Filter 2: المحافظة (Governorate)
        filter2_container = self._create_filter_field("المحافظة")
        self.governorate_combo = QComboBox()
        self.governorate_combo.setPlaceholderText("اسم المحافظة")
        self._style_combo(self.governorate_combo, "اسم المحافظة")
        self.governorate_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter2_container.layout().addWidget(self.governorate_combo)
        filters_layout.addWidget(filter2_container, 1)

        # Filter 3: حالة المسح (Survey Status)
        filter3_container = self._create_filter_field("حالة المسح")
        self.building_status_combo = QComboBox()
        self.building_status_combo.setPlaceholderText("حالة المسح")
        self._style_combo(self.building_status_combo, "حالة المسح")
        self.building_status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter3_container.layout().addWidget(self.building_status_combo)
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
        self.building_search.returnPressed.connect(self._on_search)

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

        # Center the list horizontally
        list_container = QHBoxLayout()
        list_container.addStretch(1)
        list_container.addWidget(self.buildings_list)
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
        """Load filter data from database (DRY - best practice)."""
        try:
            # Load all buildings to extract unique values
            result = self.building_controller.load_buildings()
            if not result.success:
                logger.error(f"Failed to load buildings for filter data: {result.message}")
                return

            buildings = result.data

            # Extract unique governorates (DRY - using set comprehension)
            governorates_set = {
                (b.governorate_code, b.governorate_name_ar)
                for b in buildings
                if b.governorate_code and b.governorate_name_ar
            }
            self._governorates = sorted(governorates_set, key=lambda x: x[1])

            # Extract unique subdistricts
            subdistricts_set = {
                (b.subdistrict_code, b.subdistrict_name_ar)
                for b in buildings
                if b.subdistrict_code and b.subdistrict_name_ar
            }
            self._subdistricts = sorted(subdistricts_set, key=lambda x: x[1])

            # ✅ Survey Status (حالة المسح الميداني) - from Backend API
            # Used for BuildingAssignment API filtering (UC-012)
            self._survey_statuses = [
                ("not_surveyed", "لم يتم المسح"),
                ("in_progress", "جاري المسح"),
                ("completed", "تم المسح"),
                ("verified", "تم التحقق"),
            ]

            # Populate combo boxes
            self._populate_filter_combos()

        except Exception as e:
            logger.error(f"Error loading filter data: {e}", exc_info=True)

    def _populate_filter_combos(self):
        """Populate filter combo boxes with data (DRY)."""
        # Populate governorates
        for code, name_ar in self._governorates:
            self.governorate_combo.addItem(name_ar, code)

        # Populate subdistricts
        for code, name_ar in self._subdistricts:
            self.subdistrict_combo.addItem(name_ar, code)

        # ✅ Populate survey statuses (حالة المسح)
        for status_code, status_name_ar in self._survey_statuses:
            self.building_status_combo.addItem(status_name_ar, status_code)

    def _load_buildings(self):
        """Load buildings into the list."""
        result = self.building_controller.load_buildings()
        self.buildings_list.clear()

        if not result.success:
            logger.error(f"Failed to load buildings: {result.message}")
            return

        self._all_buildings = result.data

        for building in self._all_buildings:
            item = QListWidgetItem(self.buildings_list)

            # Create custom widget with checkbox
            widget = BuildingCheckboxItem(building, self)
            widget.checkbox.stateChanged.connect(
                lambda state, b=building: self._on_checkbox_changed(b, state)
            )

            # Set item size
            item.setSizeHint(widget.sizeHint())

            self.buildings_list.addItem(item)
            self.buildings_list.setItemWidget(item, widget)

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

        # NOTE: Do NOT clear search field - keep suggestions visible for multi-select
        # User can select multiple buildings from same search results

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
        Show/hide selected buildings card based on selection count and suggestions visibility.

        Rules (from Figma behavior):
        - Show card only when: has selections AND suggestions list is hidden
        - Update header count
        """
        has_selection = len(self._selected_building_ids) > 0
        suggestions_hidden = not self.buildings_list.isVisible()

        # Show card only if has selections AND suggestions are hidden
        should_show = has_selection and suggestions_hidden
        self.selected_buildings_card.setVisible(should_show)

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

        # ✅ No remove button - checkbox is enough for unselecting

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

    def _on_search_text_changed(self, text):
        """
        Show/hide suggestions on text change.

        Rules:
        - Show suggestions if: search text OR active filters
        - Hide suggestions if: no search text AND no active filters
        - Update selected card visibility based on suggestions visibility
        """
        filters = self.get_filters()
        has_active_filter = any([
            filters['subdistrict'],
            filters['governorate'],
            filters['building_status']
        ])

        # Show suggestions only if there's search text OR active filters
        should_show = bool(text.strip()) or has_active_filter
        self._set_suggestions_visible(should_show)
        self._filter_buildings()

        # Update selected card visibility (depends on suggestions visibility)
        self._update_selected_card_visibility()

    def _load_buildings_from_api(self):
        """
        ✅ Load buildings from Backend API with filters (Best Practice).

        Reduces load on local database by fetching directly from Backend.
        Implements UC-012 field assignment workflow.
        """
        filters = self.get_filters()

        try:
            # ✅ Call Backend API with filters (no polygon needed!)
            result = self.building_controller.search_for_assignment_by_filters(
                governorate_code=filters['governorate'],
                subdistrict_code=filters['subdistrict'],
                survey_status=filters['building_status'],  # This is survey_status in API
                has_active_assignment=False,  # Only show unassigned buildings
                page=1,
                page_size=500
            )

            if not result.success:
                logger.error(f"Failed to load buildings from API: {result.message}")
                # Fallback to local filtering if API fails
                self._filter_buildings()
                return

            # ✅ Clear and repopulate list with API results
            self.buildings_list.clear()
            buildings = result.data

            # Apply search text filter locally (if any)
            search_text = self.building_search.text().lower()
            if search_text:
                buildings = [
                    b for b in buildings
                    if search_text in (b.building_id.lower() if b.building_id else "")
                ]

            logger.info(f"✅ Loaded {len(buildings)} buildings from API with filters")

            # Add buildings to list
            for building in buildings:
                item = QListWidgetItem(self.buildings_list)
                widget = BuildingCheckboxItem(building, self)

                # Connect checkbox
                widget.checkbox.stateChanged.connect(
                    lambda state, b=building: self._on_checkbox_changed(b, state)
                )

                # Check if already selected
                if building.building_id in self._selected_building_ids:
                    widget.checkbox.setChecked(True)

                item.setSizeHint(widget.sizeHint())
                self.buildings_list.addItem(item)
                self.buildings_list.setItemWidget(item, widget)

        except Exception as e:
            logger.error(f"Error loading buildings from API: {e}", exc_info=True)
            # Fallback to local filtering
            self._filter_buildings()

    def _filter_buildings(self):
        """
        Filter buildings list based on search text and filters (DRY principle).

        NOTE: This is the FALLBACK method for local filtering.
        Prefer _load_buildings_from_api() for better performance.
        """
        search_text = self.building_search.text().lower()
        filters = self.get_filters()

        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            widget = self.buildings_list.itemWidget(item)

            if widget and hasattr(widget, 'building'):
                building = widget.building

                # Search text match
                text_match = (
                    search_text in building.building_id.lower() if building.building_id else False
                ) if search_text else True

                # Filter matches
                governorate_match = (
                    building.governorate_code == filters['governorate']
                ) if filters['governorate'] else True

                subdistrict_match = (
                    building.subdistrict_code == filters['subdistrict']
                ) if filters['subdistrict'] else True

                building_status_match = (
                    building.building_status == filters['building_status']
                ) if filters['building_status'] else True

                # Show only if ALL filters match
                match = text_match and governorate_match and subdistrict_match and building_status_match
                item.setHidden(not match)

    def _on_filter_changed(self):
        """
        ✅ Handle filter change - uses Backend API for efficient search (Best Practice).

        Rules:
        - Show suggestions if: filters applied OR search text
        - Hide suggestions if: no filters AND no search text
        - Update selected card visibility
        - ✅ NEW: Calls Backend API instead of local filtering
        """
        filters = self.get_filters()
        logger.debug(f"Filters changed: {filters}")

        # Show buildings list if filters are applied OR search text exists
        has_active_filter = any([
            filters['subdistrict'],
            filters['governorate'],
            filters['building_status']
        ])

        if has_active_filter or filters['search_text']:
            self._set_suggestions_visible(True)
            # ✅ BEST PRACTICE: Load from Backend API with filters
            self._load_buildings_from_api()
        else:
            self._set_suggestions_visible(False)
            self.buildings_list.clear()  # Clear list when no filters

        # Update selected card visibility
        self._update_selected_card_visibility()

    def _on_search(self):
        """
        ✅ Handle search action - uses Backend API with filters (Best Practice).

        If filters are applied, loads from API. Otherwise uses local search.
        """
        search_text = self.building_search.text().strip()
        logger.debug(f"Searching for: {search_text}")

        filters = self.get_filters()
        has_active_filter = any([
            filters['subdistrict'],
            filters['governorate'],
            filters['building_status']
        ])

        if has_active_filter:
            # ✅ Use API if filters are active
            self._load_buildings_from_api()
        else:
            # Fallback to local search if no filters
            self._filter_buildings()

    def _on_open_map(self):
        """
        Open map dialog with polygon drawing for multi-building selection.

        ✅ BEST PRACTICE: Same as wizard - NO pre-loading of buildings!
        - Dialog loads buildings dynamically with viewport loading
        - Fast instant opening (no 6+ second wait)
        - DRY principle: unified with BuildingMapDialog
        """
        try:
            from ui.components.polygon_map_dialog_v2 import show_polygon_map_dialog

            # ✅ BEST PRACTICE: Get auth token only (like wizard - NO building loading!)
            auth_token = None
            try:
                main_window = self
                while main_window and not hasattr(main_window, 'current_user'):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                    auth_token = getattr(main_window.current_user, '_api_token', None)
                    logger.debug(f"✅ Auth token available for PolygonMapDialog")
            except Exception as e:
                logger.warning(f"Could not get auth token: {e}")

            # ✅ FAST: Open dialog immediately (like wizard)
            # Dialog handles building loading internally with viewport loading
            selected_buildings = show_polygon_map_dialog(
                db=self.building_controller.db,
                auth_token=auth_token,
                parent=self
            )

            # User cancelled or no buildings selected
            logger.info(f"📥 Received from polygon map dialog: {type(selected_buildings)}")
            logger.info(f"   Buildings count: {len(selected_buildings) if selected_buildings else 0}")

            if not selected_buildings:
                logger.info("❌ No buildings selected from polygon")
                return

            # ✅ SOLID: Log received buildings for debugging
            logger.info(f"✅ Received {len(selected_buildings)} buildings from polygon")
            for i, bldg in enumerate(selected_buildings[:3]):
                logger.info(f"   Building {i+1}: ID={bldg.building_id}")

            # Add selected buildings to current selection (multi-select)
            added_count = 0
            for building in selected_buildings:
                # Skip if already selected
                if building.building_id in self._selected_building_ids:
                    continue

                # ✅ CRITICAL FIX: Add to BOTH sets!
                # _selected_building_ids: buildings in table
                # _confirmed_building_ids: buildings ready for transfer (checked)
                self._selected_building_ids.add(building.building_id)
                self._confirmed_building_ids.add(building.building_id)  # ← Add to confirmed too!
                self._add_building_to_table(building)
                added_count += 1

                # Find the corresponding widget and check its checkbox
                for i in range(self.buildings_list.count()):
                    item = self.buildings_list.item(i)
                    widget = self.buildings_list.itemWidget(item)

                    if widget and hasattr(widget, 'building'):
                        if widget.building.building_id == building.building_id:
                            # Check the checkbox
                            widget.checkbox.setChecked(True)
                            break

            # Update UI
            self._update_selection_count()
            self._update_selected_card_visibility()

            # ✅ NO MESSAGE: Buildings are added directly to the list (silent operation)
            # User can see them in "العناصر المحفوظة" section
            logger.info(f"✅ Added {added_count} buildings from polygon to selection (silent)")

        except Exception as e:
            logger.error(f"Error opening map selector: {e}", exc_info=True)
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "خطأ - Error",
                f"حدث خطأ أثناء فتح الخريطة:\n{str(e)}"
            )

    def _on_next(self):
        """Handle next button click."""
        if self._selected_building_ids:
            self.next_clicked.emit()

    def get_filters(self) -> dict:
        """Get current filter values (SOLID - consistent interface)."""
        # Get values only if index > -1 (item selected, not placeholder)
        return {
            'subdistrict': self.subdistrict_combo.currentData() if self.subdistrict_combo.currentIndex() >= 0 else None,
            'governorate': self.governorate_combo.currentData() if self.governorate_combo.currentIndex() >= 0 else None,
            'building_status': self.building_status_combo.currentData() if self.building_status_combo.currentIndex() >= 0 else None,
            'search_text': self.building_search.text().strip()
        }

    def get_selected_building_ids(self):
        """Get list of selected building IDs."""
        return list(self._selected_building_ids)

    def get_selected_buildings(self):
        """Get list of selected building objects."""
        if not hasattr(self, '_all_buildings'):
            return []

        # Return building objects that match selected IDs
        return [
            building for building in self._all_buildings
            if building.building_id in self._selected_building_ids
        ]

    def mousePressEvent(self, event):
        """
        Handle mouse press to detect clicks outside suggestions list.

        When user clicks outside the suggestions list (and not on filter combos or search bar),
        hide the suggestions by clearing search and show the selected buildings card.
        """
        # Check if suggestions list is visible
        if self.buildings_list.isVisible():
            # Get widgets to check
            widgets_to_exclude = [
                self.buildings_list,
                self.building_search,
                self.subdistrict_combo,
                self.governorate_combo,
                self.building_status_combo
            ]

            # Check if click is on any of the excluded widgets
            click_on_widget = False
            for widget in widgets_to_exclude:
                if widget.underMouse():
                    click_on_widget = True
                    break

            # If click is outside all excluded widgets, hide suggestions
            if not click_on_widget:
                # Clear filters and search to hide suggestions
                filters = self.get_filters()
                has_active_filter = any([
                    filters['subdistrict'],
                    filters['governorate'],
                    filters['building_status']
                ])

                # Only clear search if no active filters
                if not has_active_filter:
                    self.building_search.clear()
                    self._set_suggestions_visible(False)
                    self._update_selected_card_visibility()

        super().mousePressEvent(event)

    def _on_search_enter(self):
        """
        Handle Enter key press in search field (Best Practice).

        Hide suggestions and show selected buildings card.
        """
        # Clear search field and hide suggestions
        self.building_search.clear()
        self._set_suggestions_visible(False)
        self._update_selected_card_visibility()
