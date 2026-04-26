# -*- coding: utf-8 -*-
"""Field work preparation step 1: select buildings for assignment."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QToolButton, QStackedWidget,
    QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QIcon

from controllers.building_controller import BuildingController
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from ui.components.animated_card import AnimatedCard
from ui.components.empty_state import EmptyState
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.animation_utils import stagger_fade_in
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


def _connect_auto_direction(field):
    """Connect textChanged on a QLineEdit to auto-detect direction from first character."""
    def _detect(text):
        if text and '\u0600' <= text[0] <= '\u06FF':
            field.setLayoutDirection(Qt.RightToLeft)
            field.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        elif text:
            field.setLayoutDirection(Qt.LeftToRight)
            field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    field.textChanged.connect(_detect)


class _SelectableBuildingCard(AnimatedCard):
    """Search result building card - lighter style, clicking adds to selection."""

    selection_changed = pyqtSignal(object, bool)

    _STATUS_COLORS = {
        "intact": "#10B981",
        "damaged": "#F59E0B",
        "destroyed": "#EF4444",
        "سليم": "#10B981",
        "متضرر": "#F59E0B",
        "مدمر": "#EF4444",
    }

    def __init__(self, building, parent=None):
        self.building = building
        self._selected = False
        self._assigned_badge = None
        self._locked_badge = None

        status_display = getattr(building, 'building_status_display', '') or ''
        status_color = self._STATUS_COLORS.get(status_display.lower(), "#CBD5E1")

        super().__init__(
            parent,
            card_height=72,
            border_radius=8,
            show_chevron=False,
            show_strip=True,
            status_color=status_color,
            strip_width=3,
            clickable=True,
            lift_target=1.5,
        )

    def _build_content(self, layout):
        """Populate card with building info."""
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.setContentsMargins(0, 0, 0, 0)

        self._code_label = QLabel(self.building.building_id or "")
        self._code_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._code_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent;")
        apply_label_alignment(self._code_label)
        top_row.addWidget(self._code_label, 1)

        self._add_indicator = QLabel("+")
        self._add_indicator.setFixedSize(22, 22)
        self._add_indicator.setAlignment(Qt.AlignCenter)
        self._add_indicator.setStyleSheet(
            "color: #2563EB; background: #EFF6FF; border-radius: 11px;"
            " font-size: 14px; font-weight: bold;"
        )
        top_row.addWidget(self._add_indicator)
        layout.addLayout(top_row)

        info_row = QHBoxLayout()
        info_row.setSpacing(10)
        info_row.setContentsMargins(0, 0, 0, 0)

        type_display = getattr(self.building, 'building_type_display', '') or ''
        status_display = getattr(self.building, 'building_status_display', '') or ''
        secondary_text = f"{tr('wizard.step1.type_label')}: {type_display}"
        if status_display:
            secondary_text += f"  |  {tr('wizard.step1.status_label')}: {status_display}"

        secondary_label = QLabel(secondary_text)
        secondary_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        secondary_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
        apply_label_alignment(secondary_label)
        self._secondary_label = secondary_label
        info_row.addWidget(secondary_label, 1)

        if getattr(self.building, 'is_assigned', False) or getattr(self.building, 'has_active_assignment', False):
            assigned_badge = QLabel(tr("building.assigned"))
            assigned_badge.setFont(create_font(size=7, weight=FontManager.WEIGHT_SEMIBOLD))
            assigned_badge.setStyleSheet(
                f"color: white; background: {Colors.PRIMARY_BLUE};"
                " border-radius: 8px; padding: 2px 7px;"
            )
            self._assigned_badge = assigned_badge
            info_row.addWidget(assigned_badge)

        if getattr(self.building, 'is_locked', False):
            locked_badge = QLabel(tr("building.locked"))
            locked_badge.setFont(create_font(size=7, weight=FontManager.WEIGHT_SEMIBOLD))
            locked_badge.setStyleSheet(
                "color: white; background: #6c757d;"
                " border-radius: 8px; padding: 2px 7px;"
            )
            self._locked_badge = locked_badge
            info_row.addWidget(locked_badge)

        layout.addLayout(info_row)

    def _apply_base_style(self):
        """Override base style to show selection state."""
        r = self._border_radius
        cn = self._class_name()
        if self._selected:
            self.setStyleSheet(
                f"{cn} {{"
                f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"    stop:0 #EBF5FF, stop:1 #DBEAFE);"
                f"  border-radius: {r}px;"
                f"  border: 2px solid {Colors.PRIMARY_BLUE};"
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"{cn} {{"
                f"  background: white;"
                f"  border-radius: {r}px;"
                f"  border: 1px solid #E2E8F0;"
                f"}}"
            )

    def _apply_hover_style(self):
        """Override hover style to show selection state."""
        r = self._border_radius
        cn = self._class_name()
        if self._selected:
            self.setStyleSheet(
                f"{cn} {{"
                f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"    stop:0 #DBEAFE, stop:1 #BFDBFE);"
                f"  border-radius: {r}px;"
                f"  border: 2px solid {Colors.PRIMARY_BLUE};"
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"{cn} {{"
                f"  background: #F8FAFF;"
                f"  border-radius: {r}px;"
                f"  border: 1px solid #93C5FD;"
                f"}}"
            )

    @property
    def is_selected(self):
        return self._selected

    @is_selected.setter
    def is_selected(self, value):
        if self._selected != value:
            self._selected = value
            if hasattr(self, '_add_indicator'):
                if value:
                    self._add_indicator.setText("✓")
                    self._add_indicator.setStyleSheet(
                        "color: white; background: #2563EB; border-radius: 11px;"
                        " font-size: 12px; font-weight: bold;"
                    )
                else:
                    self._add_indicator.setText("+")
                    self._add_indicator.setStyleSheet(
                        "color: #2563EB; background: #EFF6FF; border-radius: 11px;"
                        " font-size: 14px; font-weight: bold;"
                    )
            self._apply_base_style()
            self.update()

    def mousePressEvent(self, event):
        """Emit selection signal on click without toggling internally."""
        if event.button() == Qt.LeftButton:
            self.selection_changed.emit(self.building, not self._selected)
        super().mousePressEvent(event)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        type_display = getattr(self.building, 'building_type_display', '') or ''
        status_display = getattr(self.building, 'building_status_display', '') or ''
        secondary_text = f"{tr('wizard.step1.type_label')}: {type_display}"
        if status_display:
            secondary_text += f"  |  {tr('wizard.step1.status_label')}: {status_display}"
        if hasattr(self, '_secondary_label') and self._secondary_label:
            self._secondary_label.setText(secondary_text)
        if self._assigned_badge:
            self._assigned_badge.setText(tr("building.assigned"))
        if self._locked_badge:
            self._locked_badge.setText(tr("building.locked"))
        self.update()


class _SelectedBuildingRow(QFrame):
    """Row widget for the selected buildings view - distinct from search result cards."""

    removal_requested = pyqtSignal(object)

    def __init__(self, building, parent=None):
        super().__init__(parent)
        self.building = building
        self._sub_label = None
        self._setup()

    def _setup(self):
        self.setLayoutDirection(get_layout_direction())
        self.setFixedHeight(ScreenScale.h(60))
        self.setStyleSheet("""
            _SelectedBuildingRow {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #EFF6FF, stop:1 #E0F2FE);
                border-radius: 8px;
                border: 1px solid #BFDBFE;
                border-right: 3px solid #2563EB;
            }
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                color: #64748B;
                background: #E2E8F0;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                color: white;
                background: #EF4444;
            }
        """)
        remove_btn.clicked.connect(lambda: self.removal_requested.emit(self.building))
        row.addWidget(remove_btn)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setContentsMargins(0, 0, 0, 0)

        code_label = QLabel(self.building.building_id or "")
        code_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        code_label.setStyleSheet("color: #1E3A8A; background: transparent;")
        code_label.setLayoutDirection(Qt.LeftToRight)
        if get_layout_direction() == Qt.RightToLeft:
            code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            code_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        info_col.addWidget(code_label)

        type_display = getattr(self.building, 'building_type_display', '') or ''
        if type_display:
            sub_label = QLabel(f"{tr('wizard.step1.type_label')}: {type_display}")
            sub_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            sub_label.setStyleSheet("color: #64748B; background: transparent;")
            self._sub_label = sub_label
            info_col.addWidget(sub_label)

        row.addLayout(info_col, 1)

        check_circle = QLabel("✓")
        check_circle.setFixedSize(28, 28)
        check_circle.setAlignment(Qt.AlignCenter)
        check_circle.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        check_circle.setStyleSheet(
            "color: white; background: #2563EB; border-radius: 14px;"
        )
        row.addWidget(check_circle)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        if self._sub_label:
            type_display = getattr(self.building, 'building_type_display', '') or ''
            self._sub_label.setText(f"{tr('wizard.step1.type_label')}: {type_display}")
        self.update()


class FieldWorkPreparationStep1(QWidget):
    """Filter and search buildings for field assignment."""

    next_clicked = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, building_controller: BuildingController, i18n: I18n, parent=None):
        super().__init__(parent)
        self.building_controller = building_controller
        self.i18n = i18n
        self.page = parent  # Store reference to parent page
        self._selected_building_ids = set()
        self._confirmed_building_ids = set()
        self._selected_buildings = {}  # {building_id: building_object}
        self._showing_selected_view = False

        # Cache for filter data (from API)
        self._all_communities = []  # [(code, name_ar, name_en), ...]
        self._all_neighborhoods = []  # [(code, name_ar, name_en, community_code), ...]
        self._all_neighborhoods_raw = []

        self._setup_ui()

        # Install event filter to detect clicks outside suggestions
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def load_data(self):
        """Load filter data from API (call after login)."""
        self._load_filter_data_async()

    def _load_filter_data_async(self):
        """Load filter data from API in background thread (non-blocking)."""
        api = get_api_client()

        def _fetch():
            communities = api.get_communities(
                governorate_code="01", district_code="01", sub_district_code="01"
            )
            neighborhoods = api.get_neighborhoods(
                governorate_code="01", district_code="01", subdistrict_code="01"
            )
            return communities, neighborhoods

        def _on_done(result):
            from services.translation_manager import get_language
            communities, neighborhoods = result
            self._all_communities = []
            self._all_neighborhoods = []

            for c in communities:
                if c.get("isActive", True):
                    code = c.get("code", "")
                    name_ar = c.get("nameArabic", "")
                    name_en = c.get("nameEnglish", "") or name_ar
                    if code and (name_ar or name_en):
                        self._all_communities.append((code, name_ar, name_en))
            self._all_communities.sort(key=lambda x: x[1])

            lang = get_language()
            self.community_combo.blockSignals(True)
            self.community_combo.clear()
            self.community_combo.addItem(tr("wizard.step1.all"), None)
            for code, name_ar, name_en in self._all_communities:
                display = name_ar if lang == "ar" else (name_en or name_ar)
                self.community_combo.addItem(display, code)
            self.community_combo.blockSignals(False)

            self._all_neighborhoods_raw = neighborhoods
            for n in neighborhoods:
                code = n.get("neighborhoodCode") or n.get("code", "")
                name_ar = n.get("nameArabic", "")
                name_en = n.get("nameEnglish", "") or name_ar
                comm_code = n.get("communityCode", "")
                if code and (name_ar or name_en):
                    self._all_neighborhoods.append((code, name_ar, name_en, comm_code))
            self._all_neighborhoods.sort(key=lambda x: x[1])

            self.neighborhood_combo.clear()
            self.neighborhood_combo.addItem(tr("wizard.step1.all"), None)
            for code, name_ar, name_en, _ in self._all_neighborhoods:
                display = name_ar if lang == "ar" else (name_en or name_ar)
                self.neighborhood_combo.addItem(display, code)

            logger.info(
                f"Loaded {len(self._all_communities)} communities, "
                f"{len(self._all_neighborhoods)} neighborhoods from API (async)"
            )

        def _on_error(msg):
            logger.error(f"Error loading filter data from API (async): {msg}")

        self._filter_data_worker = ApiWorker(_fetch)
        self._filter_data_worker.finished.connect(_on_done)
        self._filter_data_worker.error.connect(_on_error)
        self._filter_data_worker.start()

    def _setup_ui(self):
        """Setup UI - inline filters, search, chips row, and results area."""
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 16,
            PageDimensions.content_padding_h(), 0
        )
        main_layout.setSpacing(16)

        # -- Filter Row (3 combos, inline -- no card wrapper) --
        filters_layout = QHBoxLayout()
        filters_layout.setSpacing(16)

        # Filter 1: City
        filter1_container, self._filter1_label = self._create_filter_field(tr("filter.step1.city"))
        self.community_combo = QComboBox()
        self.community_combo.setPlaceholderText(tr("filter.step1.select_city"))
        self._style_combo(self.community_combo)
        self.community_combo.currentIndexChanged.connect(self._on_community_changed)
        filter1_container.layout().addWidget(self.community_combo)
        filters_layout.addWidget(filter1_container, 1)

        # Filter 2: Neighborhood -- cascading from community
        filter2_container, self._filter2_label = self._create_filter_field(tr("filter.step1.neighborhood"))
        self.neighborhood_combo = QComboBox()
        self.neighborhood_combo.setPlaceholderText(tr("filter.step1.select_neighborhood"))
        self._style_combo(self.neighborhood_combo)
        self.neighborhood_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter2_container.layout().addWidget(self.neighborhood_combo)
        filters_layout.addWidget(filter2_container, 1)

        # Filter 3: Assignment Status
        filter3_container, self._filter3_label = self._create_filter_field(tr("filter.step1.assignment_status"))
        self.assignment_status_combo = QComboBox()
        self.assignment_status_combo.setPlaceholderText(tr("filter.step1.assignment_status"))
        self._style_combo(self.assignment_status_combo)
        self.assignment_status_combo.addItem(tr("filter.step1.all"), None)
        self.assignment_status_combo.addItem(tr("filter.step1.unassigned"), "false")
        self.assignment_status_combo.addItem(tr("filter.step1.assigned"), "true")
        self.assignment_status_combo.setCurrentIndex(0)
        self.assignment_status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter3_container.layout().addWidget(self.assignment_status_combo)
        filters_layout.addWidget(filter3_container, 1)

        main_layout.addLayout(filters_layout)

        # -- Search Row --
        self._search_label = QLabel(tr("wizard.step1.building_code_label"))
        self._search_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._search_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        main_layout.addWidget(self._search_label)

        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setFixedHeight(ScreenScale.h(42))
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
        search_icon_btn.setFixedSize(ScreenScale.w(30), ScreenScale.h(30))
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
            search_icon_btn.setText("?")
        search_icon_btn.clicked.connect(self._on_search)

        # Input
        self.building_search = QLineEdit()
        self.building_search.setPlaceholderText(tr("wizard.step1.search_building_code"))
        self.building_search.setLayoutDirection(get_layout_direction())
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
        _connect_auto_direction(self.building_search)

        # Map link button
        self._map_link_btn = QPushButton(tr("wizard.step1.search_on_map"))
        self._map_link_btn.setCursor(Qt.PointingHandCursor)
        self._map_link_btn.setFlat(True)
        self._map_link_btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                color: {Colors.PRIMARY_BLUE};
                font-family: 'IBM Plex Sans Arabic';
                font-weight: 600;
                font-size: 7pt;
                text-decoration: underline;
                padding: 0;
                margin-top: 1px;
            }}
        """)
        self._map_link_btn.clicked.connect(self._on_open_map)

        # Assemble search bar
        sb.addWidget(self._map_link_btn)
        sb.addWidget(self.building_search)
        sb.addWidget(search_icon_btn, 1)

        main_layout.addWidget(search_bar)

        # -- Selection Count Label (shown when buildings selected) --
        self._selection_count_label = QLabel()
        self._selection_count_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._selection_count_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent;")
        self._selection_count_label.setVisible(False)
        main_layout.addWidget(self._selection_count_label)

        # -- Results Area (fills remaining space) --
        self._suggestions_scroll = QScrollArea()
        self._suggestions_scroll.setWidgetResizable(True)
        self._suggestions_scroll.setFrameShape(QFrame.NoFrame)
        self._suggestions_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        self._suggestions_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._suggestions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._suggestions_content = QWidget()
        self._suggestions_content.setStyleSheet("background: transparent;")
        self._suggestions_layout = QVBoxLayout(self._suggestions_content)
        self._suggestions_layout.setContentsMargins(4, 4, 4, 4)
        self._suggestions_layout.setSpacing(6)
        self._suggestions_layout.addStretch()
        self._suggestions_scroll.setWidget(self._suggestions_content)

        # Track suggestion card widgets
        self._suggestion_cards = []

        # Shimmer timer for animated cards
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(50)
        self._shimmer_timer.timeout.connect(self._update_shimmer)

        # Debounce timer for search field (prevents API call on every keystroke)
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(350)
        self._search_debounce_timer.timeout.connect(self._load_buildings_from_api)

        # Empty state (shown initially with hint)
        self.empty_label = EmptyState(
            icon_name="carbon_location-filled",
            title=tr("wizard.step1.select_filters_hint"),
        )
        self.empty_label.setMinimumHeight(ScreenScale.h(179))

        # Stacked results: page 0 = empty state, page 1 = results scroll
        empty_page = QWidget()
        empty_page.setStyleSheet("background: transparent;")
        ep_layout = QHBoxLayout(empty_page)
        ep_layout.setContentsMargins(0, 0, 0, 0)
        ep_layout.addStretch(1)
        ep_layout.addWidget(self.empty_label)
        ep_layout.addStretch(1)

        self._results_stack = QStackedWidget()
        self._results_stack.setStyleSheet("background: transparent;")
        self._results_stack.addWidget(empty_page)  # index 0
        self._results_stack.addWidget(self._suggestions_scroll)  # index 1
        self._results_stack.setCurrentIndex(0)

        main_layout.addWidget(self._results_stack, 1)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_filter_field(self, label_text: str):
        """Create filter field container with label. Returns (container, label)."""
        container = QFrame()
        container.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        layout.addWidget(label)

        return container, label

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

    def _style_combo(self, combo: QComboBox):
        """Apply consistent styling to combo boxes (full-field clickable)."""
        combo.setFixedHeight(ScreenScale.h(42))

        down_icon_path = self._get_down_icon_path()

        if down_icon_path:
            down_arrow_css = f"image: url({down_icon_path}); width: 12px; height: 12px;"
        else:
            down_arrow_css = (
                "border-left: 4px solid transparent; "
                "border-right: 4px solid transparent; "
                "border-top: 5px solid #606266; width: 0; height: 0;"
            )

        combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
                padding: 8px 35px 8px 14px;
                background-color: {Colors.SEARCH_BAR_BG};
                color: #374151;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                {down_arrow_css}
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                background-color: white;
                selection-background-color: #EFF6FF;
                selection-color: #374151;
                color: #374151;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                color: #374151;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #EFF6FF;
                color: #1d4ed8;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #EFF6FF;
                color: #1d4ed8;
            }}
            QScrollBar:vertical {{
                width: 0px;
            }}
            QScrollBar:horizontal {{
                height: 0px;
            }}
        """)

    def _load_filter_data(self):
        """Load communities and neighborhoods from API."""
        try:
            from services.translation_manager import get_language
            api = get_api_client()

            self._all_communities = []
            self._all_neighborhoods = []

            communities = api.get_communities(
                governorate_code="01", district_code="01", sub_district_code="01"
            )
            for c in communities:
                if c.get("isActive", True):
                    code = c.get("code", "")
                    name_ar = c.get("nameArabic", "")
                    name_en = c.get("nameEnglish", "") or name_ar
                    if code and (name_ar or name_en):
                        self._all_communities.append((code, name_ar, name_en))
            self._all_communities.sort(key=lambda x: x[1])

            lang = get_language()
            self.community_combo.blockSignals(True)
            self.community_combo.clear()
            self.community_combo.addItem(tr("wizard.step1.all"), None)
            for code, name_ar, name_en in self._all_communities:
                display = name_ar if lang == "ar" else (name_en or name_ar)
                self.community_combo.addItem(display, code)
            self.community_combo.blockSignals(False)

            neighborhoods = api.get_neighborhoods(
                governorate_code="01", district_code="01", subdistrict_code="01"
            )
            self._all_neighborhoods_raw = neighborhoods
            for n in neighborhoods:
                code = n.get("neighborhoodCode") or n.get("code", "")
                name_ar = n.get("nameArabic", "")
                name_en = n.get("nameEnglish", "") or name_ar
                comm_code = n.get("communityCode", "")
                if code and (name_ar or name_en):
                    self._all_neighborhoods.append((code, name_ar, name_en, comm_code))
            self._all_neighborhoods.sort(key=lambda x: x[1])

            self.neighborhood_combo.clear()
            self.neighborhood_combo.addItem(tr("wizard.step1.all"), None)
            for code, name_ar, name_en, _ in self._all_neighborhoods:
                display = name_ar if lang == "ar" else (name_en or name_ar)
                self.neighborhood_combo.addItem(display, code)

            logger.info(
                f"Loaded {len(self._all_communities)} communities, "
                f"{len(self._all_neighborhoods)} neighborhoods from API"
            )

        except Exception as e:
            logger.error(f"Error loading filter data from API: {e}", exc_info=True)
            Toast.show_toast(self, tr("wizard.step1.buildings_load_failed"), Toast.ERROR)

    def _on_community_changed(self, index):
        """Cascade: update neighborhoods based on selected community."""
        from services.translation_manager import get_language
        community_code = self.community_combo.currentData()
        lang = get_language()

        self.neighborhood_combo.blockSignals(True)
        self.neighborhood_combo.clear()
        self.neighborhood_combo.addItem(tr("wizard.step1.all"), None)

        if community_code:
            for code, name_ar, name_en, comm_code in self._all_neighborhoods:
                if comm_code == community_code:
                    display = name_ar if lang == "ar" else (name_en or name_ar)
                    self.neighborhood_combo.addItem(display, code)
        else:
            for code, name_ar, name_en, _ in self._all_neighborhoods:
                display = name_ar if lang == "ar" else (name_en or name_ar)
                self.neighborhood_combo.addItem(display, code)

        self.neighborhood_combo.blockSignals(False)
        self._on_filter_changed()

    def _on_checkbox_changed(self, building, state):
        """Handle selection state change from suggestion cards."""
        if state == Qt.Checked:
            self._selected_building_ids.add(building.building_id)
            self._confirmed_building_ids.add(building.building_id)
            self._selected_buildings[building.building_id] = building
        else:
            self._selected_building_ids.discard(building.building_id)
            self._confirmed_building_ids.discard(building.building_id)
            self._selected_buildings.pop(building.building_id, None)

        self._update_selection_count()
        self._update_selected_card_visibility()

    def _update_selection_count(self):
        """Update selection count and button state (based on confirmed buildings)."""
        count = len(self._confirmed_building_ids)
        # Enable/disable next button via parent page
        if self.page and hasattr(self.page, 'enable_next_button'):
            self.page.enable_next_button(count > 0)

    def _update_selected_card_visibility(self):
        """Show/hide selection count label."""
        count = len(self._selected_building_ids)
        has_selection = count > 0
        self._selection_count_label.setVisible(has_selection)
        if has_selection:
            self._selection_count_label.setText(
                f"{tr('wizard.step1.selected_items')} ({count} {tr('wizard.step1.building_unit')})"
            )

    def clear_all_selections(self):
        """Clear all selections (used by parent page on refresh)."""
        self._selected_building_ids.clear()
        self._confirmed_building_ids.clear()
        self._selected_buildings.clear()
        self._clear_suggestion_cards()
        self._set_suggestions_visible(False)
        self._update_selection_count()
        self._update_selected_card_visibility()

    def _remove_building_selection(self, building_id):
        """Remove building from selection and update UI."""
        self._selected_building_ids.discard(building_id)
        self._confirmed_building_ids.discard(building_id)
        self._selected_buildings.pop(building_id, None)

        # Remove card from view
        if self._showing_selected_view:
            for card in self._suggestion_cards[:]:
                if card.building.building_id == building_id:
                    self._suggestions_layout.removeWidget(card)
                    self._suggestion_cards.remove(card)
                    card.deleteLater()
                    break
            if not self._suggestion_cards:
                self._showing_selected_view = False
                self.empty_label.set_title(tr("wizard.step1.select_filters_hint"))
                self._results_stack.setCurrentIndex(0)
        else:
            # Uncheck card in search results
            for card in self._suggestion_cards:
                if card.building.building_id == building_id:
                    card.is_selected = False
                    break

        self._update_selection_count()
        self._update_selected_card_visibility()

    def _update_shimmer(self):
        """Repaint suggestion cards for shimmer animation."""
        for card in self._suggestion_cards:
            if card and not card.isHidden():
                card.update()

    def _set_suggestions_visible(self, visible: bool):
        """Show/hide results area via stacked widget."""
        if visible:
            self._showing_selected_view = False
            self._results_stack.setCurrentIndex(1)
            self._shimmer_timer.start()
        else:
            self._shimmer_timer.stop()
            if self._selected_building_ids:
                self._show_selected_buildings_view()
            else:
                self._showing_selected_view = False
                self.empty_label.set_title(tr("wizard.step1.select_filters_hint"))
                self._results_stack.setCurrentIndex(0)

    def _show_selected_buildings_view(self):
        """Show selected buildings as rows in the results area."""
        self._clear_suggestion_cards()
        self._showing_selected_view = True

        for bid, building in self._selected_buildings.items():
            row = _SelectedBuildingRow(building, self._suggestions_content)
            row.removal_requested.connect(lambda b: self._remove_building_selection(b.building_id))
            self._suggestions_layout.insertWidget(
                self._suggestions_layout.count() - 1, row
            )
            self._suggestion_cards.append(row)

        if self._suggestion_cards:
            stagger_fade_in(self._suggestion_cards, stagger_ms=40, duration=250)

        self._results_stack.setCurrentIndex(1)

    def _on_search_text_changed(self, text):
        """Update UI state on text change; actual search happens only on Enter or icon click."""
        filters = self.get_filters()
        has_active_filter = any([
            filters['community'],
            filters['neighborhood'],
            filters['assignment_status'] is not None
        ])
        should_show = bool(text.strip()) or has_active_filter
        self._set_suggestions_visible(should_show)
        self._update_selected_card_visibility()

    def _load_buildings_from_api(self):
        """Load buildings from Backend API with current filters (non-blocking)."""
        self._spinner.show_loading(tr("page.field_step1.searching_buildings"))

        filters = self.get_filters()
        has_active = None
        assignment_val = filters.get('assignment_status')
        if assignment_val == "false":
            has_active = False
        elif assignment_val == "true":
            has_active = True

        api = get_api_client()
        self._buildings_worker = ApiWorker(
            api.get_buildings_for_assignment,
            community_code=filters['community'],
            neighborhood_code=filters['neighborhood'],
            has_active_assignment=has_active,
            page=1,
            page_size=500
        )
        self._buildings_worker.finished.connect(self._on_buildings_loaded)
        self._buildings_worker.error.connect(self._on_buildings_load_error)
        self._buildings_worker.start()

    def _on_buildings_loaded(self, response):
        """Handle API response for building search."""
        try:
            items = response.get("items", [])
            buildings = [self._api_dto_to_building(item) for item in items]

            search_text = self.building_search.text().lower().strip()
            if search_text:
                buildings = [
                    b for b in buildings
                    if search_text in (b.building_id.lower() if b.building_id else "")
                ]

            logger.info(f"Loaded {len(buildings)} buildings from API")
            self._clear_suggestion_cards()

            if buildings:
                self._results_stack.setCurrentIndex(1)
                self._shimmer_timer.start()
                self._populate_buildings_list(buildings)
            else:
                self._shimmer_timer.stop()
                self.empty_label.set_title(tr("wizard.step1.no_buildings"))
                self._results_stack.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Failed to process buildings response: {e}", exc_info=True)
            self._clear_suggestion_cards()
            Toast.show_toast(self, tr("wizard.step1.buildings_load_failed"), Toast.ERROR)
        finally:
            self._spinner.hide_loading()

    def _on_buildings_load_error(self, error_msg):
        """Handle API error for building search."""
        logger.error(f"Failed to load buildings from API: {error_msg}")
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("wizard.step1.buildings_load_failed"), Toast.ERROR)

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

    def _clear_suggestion_cards(self):
        """Remove all suggestion cards from the scroll area."""
        self._suggestion_cards.clear()
        while self._suggestions_layout.count() > 1:  # Keep trailing stretch
            item = self._suggestions_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _populate_buildings_list(self, buildings):
        """Populate the results area with _SelectableBuildingCard widgets."""
        self._clear_suggestion_cards()

        for building in buildings:
            card = _SelectableBuildingCard(building, self._suggestions_content)
            card.selection_changed.connect(self._on_card_selection_changed)

            # Restore selection state if already selected
            if building.building_id in self._selected_building_ids:
                card.is_selected = True

            self._suggestions_layout.insertWidget(
                self._suggestions_layout.count() - 1, card
            )
            self._suggestion_cards.append(card)

        # Stagger fade-in entrance animation for the new cards
        if self._suggestion_cards:
            stagger_fade_in(self._suggestion_cards, stagger_ms=40, duration=250)

    def _on_card_selection_changed(self, building, is_selected):
        """Handle card selection toggle from _SelectableBuildingCard."""
        if is_selected:
            if building.building_id in self._selected_building_ids:
                Toast.show_toast(self, tr("wizard.step1.already_selected"), Toast.WARNING)
                for card in self._suggestion_cards:
                    if hasattr(card, 'is_selected') and card.building.building_id == building.building_id:
                        card.is_selected = True
                        break
                return
            if getattr(building, 'has_active_assignment', False):
                Toast.show_toast(self, tr("wizard.step1.building_already_assigned"), Toast.WARNING)
                for card in self._suggestion_cards:
                    if hasattr(card, 'is_selected') and card.building.building_id == building.building_id:
                        card.is_selected = False
                        break
                return
            self._on_checkbox_changed(building, Qt.Checked)
            for card in self._suggestion_cards:
                if hasattr(card, 'is_selected') and card.building.building_id == building.building_id:
                    card.is_selected = True
                    break
        else:
            self._on_checkbox_changed(building, Qt.Unchecked)
            if self._showing_selected_view:
                for card in self._suggestion_cards[:]:
                    if card.building.building_id == building.building_id:
                        self._suggestions_layout.removeWidget(card)
                        self._suggestion_cards.remove(card)
                        card.deleteLater()
                        break
                if not self._suggestion_cards:
                    self._showing_selected_view = False
                    self.empty_label.set_title(tr("wizard.step1.select_filters_hint"))
                    self._results_stack.setCurrentIndex(0)
            else:
                for card in self._suggestion_cards:
                    if hasattr(card, 'is_selected') and card.building.building_id == building.building_id:
                        card.is_selected = False
                        break

    def _on_filter_changed(self):
        """Handle filter change -- auto-load when a geographic filter is active."""
        self._clear_suggestion_cards()
        filters = self.get_filters()
        has_geo_filter = bool(filters['community'] or filters['neighborhood'])
        if has_geo_filter:
            self._load_buildings_from_api()
            self._set_suggestions_visible(True)
        else:
            self._set_suggestions_visible(False)

    def _on_search(self):
        """Handle search icon click - show suggestions with filtered results."""
        search_text = self.building_search.text().strip()
        logger.debug(f"Searching for: {search_text}")

        self._load_buildings_from_api()

        self._set_suggestions_visible(True)
        self._update_selected_card_visibility()

    def _on_open_map(self):
        """Open map dialog for multi-building selection.

        Uses the exact same entry point as Office Survey
        (show_multiselect_map_dialog). The only behavioural difference is that
        no max_selection is passed (defaults to None = unlimited multi-select).
        Auth token is auto-discovered by the dialog from the parent.
        """
        try:
            from ui.components.building_map_dialog_v2 import show_multiselect_map_dialog
            from services.map_perf_logger import (
                MapPerfTrace, snapshot_active_timers, snapshot_running_threads,
                count_web_engine_views,
            )

            perf_trace = MapPerfTrace(flow_name="field_work")
            perf_trace.mark(
                'flow_start',
                active_timers=snapshot_active_timers(),
                running_threads=snapshot_running_threads(),
                web_views=count_web_engine_views(),
            )

            # Pass neighborhood center if a neighborhood filter is selected
            filters = self.get_filters()
            center_lat, center_lon = None, None
            neighborhood_code = filters.get('neighborhood')
            if neighborhood_code:
                center_lat, center_lon = self._get_neighborhood_center(neighborhood_code)

            selected_buildings = show_multiselect_map_dialog(
                db=self.building_controller.db,
                parent=self,
                center_lat=center_lat,
                center_lon=center_lon,
                initial_zoom=17 if neighborhood_code else None,
                already_selected_ids=list(self._selected_building_ids),
                perf_trace=perf_trace,
            )

            # User cancelled or no buildings selected
            logger.info(f"Received from polygon map dialog: {type(selected_buildings)}")
            logger.info(f"   Buildings count: {len(selected_buildings) if selected_buildings else 0}")

            if not selected_buildings:
                logger.info("No buildings selected from polygon")
                return

            # Log received buildings for debugging
            logger.info(f"Received {len(selected_buildings)} buildings from polygon")
            for i, bldg in enumerate(selected_buildings[:3]):
                logger.info(f"   Building {i+1}: ID={bldg.building_id}")

            # Add selected buildings to current selection (multi-select)
            added_count = 0
            for building in selected_buildings:
                # Skip if already selected
                if building.building_id in self._selected_building_ids:
                    continue

                # Check if building exists in suggestion cards
                found_in_suggestions = False
                for card in self._suggestion_cards:
                    if card.building.building_id == building.building_id:
                        card.is_selected = True
                        card.selection_changed.emit(card.building, True)
                        found_in_suggestions = True
                        break

                # Only add directly if NOT in suggestions (avoid double-add)
                if not found_in_suggestions:
                    self._selected_building_ids.add(building.building_id)
                    self._confirmed_building_ids.add(building.building_id)
                    self._selected_buildings[building.building_id] = building

                added_count += 1

            showing_search_results = (
                self._results_stack.currentIndex() == 1 and not self._showing_selected_view
            )

            self._update_selection_count()
            self._update_selected_card_visibility()

            if showing_search_results:
                for card in self._suggestion_cards:
                    if hasattr(card, 'is_selected'):
                        card.is_selected = card.building.building_id in self._selected_building_ids
            elif self._selected_building_ids:
                self._show_selected_buildings_view()

            logger.info(f"Added {added_count} buildings from map to selection")

        except Exception as e:
            logger.error(f"Error opening map selector: {e}", exc_info=True)
            from ui.error_handler import ErrorHandler
            ErrorHandler.show_warning(
                self,
                tr("wizard.step1.map_open_error", error=str(e)),
                tr("dialog.error")
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

    def _get_neighborhood_center(self, neighborhood_code):
        """Get center coordinates for a neighborhood from cached API data."""
        try:
            for n in self._all_neighborhoods_raw:
                code = n.get("neighborhoodCode") or n.get("code", "")
                if code == neighborhood_code:
                    lat = n.get("centerLatitude")
                    lng = n.get("centerLongitude")
                    if lat and lng:
                        return float(lat), float(lng)
        except Exception as e:
            logger.debug(f"Could not get neighborhood center: {e}")
        return None, None

    def get_selected_building_ids(self):
        """Get list of selected building IDs."""
        return list(self._selected_building_ids)

    def get_selected_buildings(self):
        """Get list of confirmed (selected) building objects."""
        return [
            b for bid, b in self._selected_buildings.items()
            if bid in self._confirmed_building_ids
        ]

    def eventFilter(self, obj, event):
        """Event filter for dismissing suggestions on outside click."""
        from PyQt5.QtCore import QEvent, QRect

        if event.type() == QEvent.MouseButtonPress and self._results_stack.currentIndex() == 1:
            # Check if click is inside suggestions area or search bar
            click_pos = event.globalPos()
            inside = False

            safe_widgets = [
                self._suggestions_scroll, self.building_search,
                self.community_combo, self.community_combo.view(),
                self.neighborhood_combo, self.neighborhood_combo.view(),
                self.assignment_status_combo, self.assignment_status_combo.view(),
            ]
            for widget in safe_widgets:
                if widget is None:
                    continue
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
        """Handle Enter key press in search field -- execute search immediately."""
        self._search_debounce_timer.stop()
        self._load_buildings_from_api()
        self._set_suggestions_visible(True)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        self.setLayoutDirection(get_layout_direction())

        # Filter labels
        self._filter1_label.setText(tr("filter.step1.city"))
        self._filter2_label.setText(tr("filter.step1.neighborhood"))
        self._filter3_label.setText(tr("filter.step1.assignment_status"))

        # Rebuild community combo with correct language names, preserve selection
        current_community = self.community_combo.currentData()
        self.community_combo.blockSignals(True)
        self.community_combo.clear()
        self.community_combo.addItem(tr("wizard.step1.all"), None)
        for code, name_ar, name_en in self._all_communities:
            display = name_ar if is_arabic else (name_en or name_ar)
            self.community_combo.addItem(display, code)
        if current_community:
            idx = self.community_combo.findData(current_community)
            if idx >= 0:
                self.community_combo.setCurrentIndex(idx)
        self.community_combo.blockSignals(False)
        self.community_combo.setPlaceholderText(tr("filter.step1.select_city"))

        # Rebuild neighborhood combo with correct language names, preserve selection
        current_neighborhood = self.neighborhood_combo.currentData()
        current_community_code = self.community_combo.currentData()
        self.neighborhood_combo.blockSignals(True)
        self.neighborhood_combo.clear()
        self.neighborhood_combo.addItem(tr("wizard.step1.all"), None)
        for code, name_ar, name_en, comm_code in self._all_neighborhoods:
            if not current_community_code or comm_code == current_community_code:
                display = name_ar if is_arabic else (name_en or name_ar)
                self.neighborhood_combo.addItem(display, code)
        if current_neighborhood:
            idx = self.neighborhood_combo.findData(current_neighborhood)
            if idx >= 0:
                self.neighborhood_combo.setCurrentIndex(idx)
        self.neighborhood_combo.blockSignals(False)
        self.neighborhood_combo.setPlaceholderText(tr("filter.step1.select_neighborhood"))

        # Assignment status combo
        self.assignment_status_combo.setPlaceholderText(tr("filter.step1.assignment_status"))
        self.assignment_status_combo.setItemText(0, tr("filter.step1.all"))
        self.assignment_status_combo.setItemText(1, tr("filter.step1.unassigned"))
        self.assignment_status_combo.setItemText(2, tr("filter.step1.assigned"))

        # Search area
        self._search_label.setText(tr("wizard.step1.building_code_label"))
        self.building_search.setPlaceholderText(tr("wizard.step1.search_building_code"))
        self._map_link_btn.setText(tr("wizard.step1.search_on_map"))

        # Empty state
        if self._results_stack.currentIndex() == 0:
            self.empty_label.set_title(tr("wizard.step1.select_filters_hint"))

        # Selection count
        self._update_selected_card_visibility()

        # Refresh visible suggestion cards and selected rows
        for card in self._suggestion_cards:
            if hasattr(card, 'update_language'):
                card.update_language(is_arabic)
