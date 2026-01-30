# -*- coding: utf-8 -*-
"""
Field Work Preparation Page - UC-012: Assign Buildings to Field Teams
Step 1: Filter and search buildings

REUSES design from BuildingSelectionStep (office_survey wizard)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QToolButton, QSizePolicy,
    QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon

from controllers.building_controller import BuildingController
from ui.components.icon import Icon
from ui.components.wizard_header import WizardHeader
from ui.components.wizard_footer import WizardFooter
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingCheckboxItem(QWidget):
    """Custom checkbox item for building list."""

    def __init__(self, building, parent=None):
        super().__init__(parent)
        self.building = building

        # Set minimum height to match BuildingSelectionStep items
        self.setMinimumHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)  # Same as BuildingSelectionStep padding
        layout.setSpacing(8)

        # Checkbox with checkmark (✓) instead of blue fill
        self.checkbox = QCheckBox()
        self.checkbox.setFixedSize(18, 18)

        # Try to load check icon (best practice: DRY)
        check_icon_path = self._get_check_icon_path_static()

        if check_icon_path:
            self.checkbox.setStyleSheet(f"""
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid #DCDFE6;
                    border-radius: 4px;
                    background: white;
                }}
                QCheckBox::indicator:checked {{
                    background: white;
                    border-color: #3890DF;
                    image: url({check_icon_path});
                }}
            """)
        else:
            # Fallback: Use Unicode checkmark ✓ character
            self.checkbox.setText("")
            self.checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 2px solid #DCDFE6;
                    border-radius: 4px;
                    background: white;
                    color: #3890DF;
                    font-size: 12px;
                    font-weight: bold;
                }
                QCheckBox::indicator:checked {
                    background: white;
                    border-color: #3890DF;
                    content: "✓";
                }
            """)
        layout.addWidget(self.checkbox)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_pixmap = Icon.load_pixmap("blue", size=24)  # Same size as BuildingSelectionStep
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("🏢")
        layout.addWidget(icon_label)

        # Text
        item_text = (
            f"{building.building_id} | "
            f"النوع: {building.building_type_display} | "
            f"الحالة: {building.building_status_display}"
        )
        text_label = QLabel(item_text)
        text_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        text_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        layout.addWidget(text_label, 1)

    @staticmethod
    def _get_check_icon_path_static() -> str:
        """Get absolute path to check.png icon (DRY helper - static version)."""
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        # Try multiple locations
        search_paths = [
            base_path / "assets" / "images" / "check.png",
            base_path / "assets" / "icons" / "check.png",
            base_path / "assets" / "images" / "checkmark.png",
            base_path / "assets" / "icons" / "checkmark.png",
        ]

        for path in search_paths:
            if path.exists():
                return str(path).replace("\\", "/")

        return ""


class FieldWorkPreparationStep1(QWidget):
    """
    Step 1: Filter and search buildings.

    REUSES exact card design from BuildingSelectionStep.
    """

    next_clicked = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, building_controller: BuildingController, i18n: I18n, parent=None):
        super().__init__(parent)
        self.building_controller = building_controller
        self.i18n = i18n
        self._selected_building_ids = set()

        # Cache for filter data
        self._governorates = []
        self._subdistricts = []
        self._building_statuses = []

        self._setup_ui()
        self._load_filter_data()
        self._load_buildings()

    def _setup_ui(self):
        """Setup UI - REUSES wizard design (DRY principle)."""
        self.setLayoutDirection(Qt.RightToLeft)

        # Background color (same as wizard)
        from ui.style_manager import StyleManager
        self.setStyleSheet(StyleManager.page_background())

        # === OUTER LAYOUT (NO PADDING) ===
        # This contains content widget + footer (footer extends full width)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # === CONTENT WIDGET (WITH PADDING) ===
        # Contains header + cards with 131px horizontal padding
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")

        content_layout = QVBoxLayout(content_widget)
        # Padding: 131px horizontal (from wizard), 20px top (reduced for consistency), 0px bottom
        from ui.design_system import PageDimensions
        content_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            20,                                       # Top: 20px (reduced from 32px)
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            0                                         # Bottom: 0px
        )
        content_layout.setSpacing(20)  # 20px gap after header (reduced from 30px for consistency)

        # === HEADER (INSIDE content widget to get 131px padding) ===
        self.header = WizardHeader(
            title="تجهيز العمل الميداني",
            subtitle="المباني  •  تجهيز العمل الميداني"
        )
        content_layout.addWidget(self.header)

        # === CARDS CONTAINER ===
        cards_container = QWidget()
        cards_container.setStyleSheet("background-color: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        # Same margins as BuildingSelectionStep: 0 horizontal, 15 top, 16 bottom
        cards_layout.setContentsMargins(0, 15, 0, 16)
        cards_layout.setSpacing(15)  # 15px between cards

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

        # Filter 3: حالة البناء (Building Status)
        filter3_container = self._create_filter_field("حالة البناء")
        self.building_status_combo = QComboBox()
        self.building_status_combo.setPlaceholderText("حالة البناء")
        self._style_combo(self.building_status_combo, "حالة البناء")
        self.building_status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter3_container.layout().addWidget(self.building_status_combo)
        filters_layout.addWidget(filter3_container, 1)

        card_layout.addLayout(filters_layout)

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
        self.buildings_list.setFixedHeight(179)
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

        # Stretch to push footer down
        cards_layout.addStretch(1)

        # Add cards container to content layout
        content_layout.addWidget(cards_container)

        # ===== Selected Buildings Card (Table) - 15px gap from filter card =====
        # This card shows selected buildings in a table format (from Figma)
        content_layout.addSpacing(15)  # Gap: 15px between filter card and selected buildings card

        self.selected_buildings_card = QFrame()
        self.selected_buildings_card.setObjectName("selectedBuildingsCard")
        self.selected_buildings_card.setVisible(False)  # Hidden initially
        self.selected_buildings_card.setStyleSheet("""
            QFrame#selectedBuildingsCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        self.selected_buildings_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        selected_card_layout = QVBoxLayout(self.selected_buildings_card)
        selected_card_layout.setContentsMargins(12, 12, 12, 12)  # Same padding as filter card
        selected_card_layout.setSpacing(12)

        # Header: "العناصر المحددة + (count)" (from Figma)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.selected_header_title = QLabel("العناصر المحددة + (0)")
        self.selected_header_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.selected_header_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        header_row.addWidget(self.selected_header_title)
        header_row.addStretch()

        selected_card_layout.addLayout(header_row)

        # Table container with scrollable area (scrollbar hidden as per Figma)
        from PyQt5.QtWidgets import QScrollArea, QVBoxLayout as QVBox
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        # Table widget container
        table_widget = QWidget()
        table_widget.setStyleSheet("background: transparent;")
        self.selected_table_layout = QVBoxLayout(table_widget)
        self.selected_table_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_table_layout.setSpacing(8)  # Gap between rows

        scroll_area.setWidget(table_widget)
        scroll_area.setMaximumHeight(285)  # Max height from Figma

        selected_card_layout.addWidget(scroll_area)

        content_layout.addWidget(self.selected_buildings_card)

        # Stretch to push footer down
        content_layout.addStretch(1)

        # Add content widget to outer layout
        outer_layout.addWidget(content_widget)

        # === FOOTER (FULL WIDTH - added to outer layout) ===
        self.footer = WizardFooter(
            show_cancel=False,
            show_save_draft=False,
            show_info_label=True,
            next_text="التالي",
            previous_text="السابق"
        )

        # Connect signals
        self.footer.previous_clicked.connect(self.cancelled.emit)
        self.footer.next_clicked.connect(self._on_next)

        # Set initial state
        self.footer.set_next_enabled(False)

        outer_layout.addWidget(self.footer)

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

    def _get_check_icon_path(self) -> str:
        """Get absolute path to check.png icon (DRY helper)."""
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        # Try multiple locations
        search_paths = [
            base_path / "assets" / "images" / "check.png",
            base_path / "assets" / "icons" / "check.png",
            base_path / "assets" / "images" / "checkmark.png",
            base_path / "assets" / "icons" / "checkmark.png",
        ]

        for path in search_paths:
            if path.exists():
                return str(path).replace("\\", "/")

        return ""

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

            # Building statuses from Building model (SOLID - using model as single source of truth)
            self._building_statuses = [
                ("intact", "سليم"),
                ("standing", "سليم"),
                ("minor_damage", "ضرر طفيف"),
                ("damaged", "متضرر"),
                ("partially_damaged", "متضرر جزئياً"),
                ("major_damage", "ضرر كبير"),
                ("severely_damaged", "متضرر بشدة"),
                ("destroyed", "مدمر"),
                ("demolished", "مهدم"),
                ("rubble", "ركام"),
                ("under_construction", "قيد البناء"),
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

        # Populate building statuses
        for status_code, status_name_ar in self._building_statuses:
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
        """Handle checkbox state change."""
        if state == Qt.Checked:
            self._selected_building_ids.add(building.building_id)
            self._add_building_to_table(building)
        else:
            self._selected_building_ids.discard(building.building_id)
            self._remove_building_from_table(building.building_id)

        self._update_selection_count()
        self._update_selected_card_visibility()

        # Clear search field after selection (multi-select best practice)
        self.building_search.clear()

    def _update_selection_count(self):
        """Update selection count and button state."""
        count = len(self._selected_building_ids)
        self.footer.set_next_enabled(count > 0)

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

        # Update header count
        count = len(self._selected_building_ids)
        self.selected_header_title.setText(f"العناصر المحددة + ({count})")

    def _add_building_to_table(self, building):
        """
        Add building row to selected buildings table.

        Row format (from Figma):
        - Building icon
        - Building ID
        - Building type
        - Building status
        - Remove button (X icon)
        """
        # Create row container
        row = QWidget()
        row.setObjectName(f"row_{building.building_id}")
        row.setStyleSheet("""
            QWidget {
                background: #F8F9FA;
                border-radius: 8px;
            }
            QWidget:hover {
                background: #EFF6FF;
            }
        """)
        row.setMinimumHeight(44)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(12)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_pixmap = Icon.load_pixmap("blue", size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("🏢")
        row_layout.addWidget(icon_label)

        # Building ID
        id_label = QLabel(building.building_id)
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        id_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        row_layout.addWidget(id_label)

        # Building Type
        type_label = QLabel(f"النوع: {building.building_type_display}")
        type_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        type_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        row_layout.addWidget(type_label)

        # Building Status
        status_label = QLabel(f"الحالة: {building.building_status_display}")
        status_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        status_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        row_layout.addWidget(status_label)

        row_layout.addStretch()

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background: #FEE2E2;
                color: #DC2626;
                border: none;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #FCA5A5;
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_building_selection(building.building_id))
        row_layout.addWidget(remove_btn)

        # Add row to table
        self.selected_table_layout.addWidget(row)

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
        Remove building from selection (triggered by remove button).

        Updates:
        - Selection set
        - Checkbox in list
        - Table row
        - Card visibility
        """
        # Remove from selection set
        self._selected_building_ids.discard(building_id)

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
        self.buildings_list.setVisible(should_show)
        self._filter_buildings()

        # Update selected card visibility (depends on suggestions visibility)
        self._update_selected_card_visibility()

    def _filter_buildings(self):
        """Filter buildings list based on search text and filters (DRY principle)."""
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
        Handle filter change - apply filters to buildings list.

        Rules:
        - Show suggestions if: filters applied OR search text
        - Hide suggestions if: no filters AND no search text
        - Update selected card visibility
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
            self.buildings_list.setVisible(True)
            self._filter_buildings()
        else:
            self.buildings_list.setVisible(False)

        # Update selected card visibility
        self._update_selected_card_visibility()

    def _on_search(self):
        """Handle search action."""
        search_text = self.building_search.text().strip()
        logger.debug(f"Searching for: {search_text}")
        self._filter_buildings()

    def _on_open_map(self):
        """
        Open offline map dialog with polygon drawing for multi-building selection.

        Uses PolygonMapDialog (DRY principle - unified design with BuildingMapWidget):
        - نفس التصميم الموحد (1100×700px، border-radius 32px)
        - Overlay رمادي شفاف
        - نفس شريط العنوان وزر الإغلاق
        - Offline map with local tiles
        - Draw polygon to select multiple buildings
        - Add selected buildings to current selection
        """
        try:
            from ui.components.polygon_map_dialog_v2 import show_polygon_map_dialog

            # Load buildings first (DRY - reuse existing data if available)
            buildings = getattr(self, '_all_buildings', [])
            if not buildings:
                result = self.building_controller.load_buildings()
                if result.success:
                    buildings = result.data
                else:
                    logger.error(f"Failed to load buildings: {result.message}")
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        "خطأ - Error",
                        f"فشل تحميل المباني:\n{result.message}"
                    )
                    return

            # Show professional map dialog (clean, unified design)
            selected_buildings = show_polygon_map_dialog(
                db=self.building_controller.db,
                buildings=buildings,
                parent=self
            )

            # User cancelled or no buildings selected
            if not selected_buildings:
                logger.info("No buildings selected from polygon")
                return

            # Add selected buildings to current selection (multi-select)
            added_count = 0
            for building in selected_buildings:
                # Skip if already selected
                if building.building_id in self._selected_building_ids:
                    continue

                self._selected_building_ids.add(building.building_id)
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

            # Show success message
            if added_count > 0:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "تم الإضافة",
                    f"تم إضافة {added_count} مبنى جديد للاختيار\n"
                    f"{added_count} new buildings added to selection"
                )

            logger.info(f"Added {added_count} buildings from polygon to selection")

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
                    self.buildings_list.setVisible(False)
                    self._update_selected_card_visibility()

        super().mousePressEvent(event)
