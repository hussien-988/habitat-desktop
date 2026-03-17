# -*- coding: utf-8 -*-
"""Field work preparation step 2: select field researcher."""

from pathlib import Path
import sys

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QToolButton, QSizePolicy, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt5.QtGui import QIcon, QColor, QPixmap

from ui.components.icon import Icon
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class FieldWorkPreparationStep2(QWidget):
    """Select field researcher via table with search and filters."""

    researcher_selected = pyqtSignal(str)  # Emits researcher id

    def __init__(self, selected_buildings, i18n: I18n, parent=None):
        super().__init__(parent)
        self.selected_buildings = selected_buildings
        self.i18n = i18n
        self.page = parent
        self._selected_researcher = None
        self._selected_radio = None  # Track currently selected radio button

        # Filters
        self._active_filters = {
            'availability': None,
            'team': None,
        }

        self._all_researchers = []
        self._researchers = []

        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

        # Load researchers from API
        self._spinner.show_loading("جاري تحميل الباحثين...")
        try:
            self._all_researchers = self._fetch_researchers_from_db()
            self._researchers = list(self._all_researchers)
            self._update_table()
        finally:
            self._spinner.hide_loading()

    def _fetch_researchers_from_db(self):
        """Fetch field collectors from BuildingAssignments API.

        Returns list of dicts with full API data for each collector.
        """
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            collectors = api.get_field_collectors()
            items = collectors if isinstance(collectors, list) else collectors.get("items", []) if isinstance(collectors, dict) else []
            researchers = []
            for user in items:
                user_id = user.get("id") or user.get("userId") or ""
                display_name = (
                    user.get("fullNameArabic")
                    or user.get("fullNameEnglish")
                    or user.get("fullName")
                    or user.get("username")
                    or user.get("userName")
                    or user_id
                )
                if user_id:
                    researchers.append({
                        'id': user_id,
                        'display_name': display_name,
                        'username': user.get("username", ""),
                        'is_available': user.get("isAvailable", True),
                        'active_assignments': user.get("activeAssignments", 0),
                        'pending_transfers': user.get("pendingTransferCount", 0),
                        'total_units': user.get("totalPropertyUnitsAssigned", 0),
                        'tablet_id': user.get("assignedTabletId"),
                        'team_name': user.get("teamName"),
                    })
            if researchers:
                researchers.sort(key=lambda r: (not r['is_available'], r['active_assignments']))
                return researchers
        except Exception as e:
            logger.warning(f"Failed to load field collectors from API: {e}")
            try:
                from services.api_client import get_api_client
                api = get_api_client()
                researchers = []
                for role in ("field_researcher", "data_collector"):
                    result = api.get_all_users(role=role, is_active=True)
                    items = result.get("items", []) if isinstance(result, dict) else []
                    for user in items:
                        user_id = user.get("id") or user.get("userId") or ""
                        display_name = (
                            user.get("fullNameArabic")
                            or user.get("fullName")
                            or user.get("userName")
                            or user_id
                        )
                        if user_id:
                            researchers.append({
                                'id': user_id,
                                'display_name': display_name,
                                'username': "",
                                'is_available': True,
                                'active_assignments': 0,
                                'pending_transfers': 0,
                                'total_units': 0,
                                'tablet_id': None,
                                'team_name': None,
                            })
                if researchers:
                    return researchers
            except Exception as fallback_err:
                logger.warning(f"Fallback to Users API also failed: {fallback_err}")

        # Last resort: load from local database
        try:
            from repositories.database import Database
            db = Database()
            rows = db.fetch_all(
                "SELECT user_id, username, full_name, full_name_ar "
                "FROM users WHERE role IN ('field_researcher', 'data_collector') AND is_active = 1"
            )
            researchers = []
            for row in rows:
                uid = row.get('user_id') or row.get('username') or ''
                display = row.get('full_name_ar') or row.get('full_name') or row.get('username') or uid
                if uid:
                    researchers.append({
                        'id': uid,
                        'display_name': display,
                        'username': row.get('username', ''),
                        'is_available': True,
                        'active_assignments': 0,
                        'pending_transfers': 0,
                        'total_units': 0,
                        'tablet_id': None,
                        'team_name': None,
                    })
            if researchers:
                logger.info(f"Loaded {len(researchers)} researchers from local DB")
                return researchers
        except Exception as db_err:
            logger.warning(f"Local DB fallback also failed: {db_err}")

        return []

    def _setup_ui(self):
        """Setup UI - search card + table + selected card."""
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        cards_container = QWidget()
        cards_container.setStyleSheet("background-color: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 15, 0, 16)
        cards_layout.setSpacing(15)
        search_card = QFrame()
        search_card.setObjectName("researcherCard")
        search_card.setStyleSheet("""
            QFrame#researcherCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)
        search_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        search_card_layout = QVBoxLayout(search_card)
        search_card_layout.setContentsMargins(12, 12, 12, 12)
        search_card_layout.setSpacing(6)

        label = QLabel("اختر الباحث الميداني")
        label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        search_card_layout.addWidget(label)

        # Search bar
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
            search_icon_btn.setText("S")

        search_icon_btn.clicked.connect(self._filter_and_update)

        self.researcher_search = QLineEdit()
        self.researcher_search.setPlaceholderText("ابحث عن اسم جامع البيانات")
        self.researcher_search.setLayoutDirection(Qt.RightToLeft)
        self.researcher_search.setStyleSheet("""
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
        self.researcher_search.textChanged.connect(self._filter_and_update)

        sb.addWidget(self.researcher_search)
        sb.addWidget(search_icon_btn, 1)

        search_card_layout.addWidget(search_bar)
        cards_layout.addWidget(search_card)
        table_card = QFrame()
        table_card.setStyleSheet("background-color: white; border-radius: 16px;")
        table_card_layout = QVBoxLayout(table_card)
        table_card_layout.setContentsMargins(10, 10, 10, 10)
        table_card_layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Filter icon for headers
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent
        self._icon_path = base_path / "assets" / "images" / "down.png"

        headers = ["", "اسم جامع البيانات", "حالة التوفر", "المهام النشطة", "الفريق"]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            if i in (2, 4) and self._icon_path.exists():
                item.setIcon(QIcon(str(self._icon_path)))
            self.table.setHorizontalHeaderItem(i, item)

        self.table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
                font-size: 10.5pt;
                font-weight: 400;
                color: #212B36;
            }
            QTableWidget::item {
                padding: 8px 15px;
                border-bottom: 1px solid #F0F0F0;
                color: #212B36;
                font-size: 10.5pt;
                font-weight: 400;
            }
            QTableWidget::item:hover {
                background-color: #FAFBFC;
            }
            QHeaderView {
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                padding: 12px;
                padding-left: 30px;
                border: none;
                color: #637381;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }
            QHeaderView::section:hover {
                background-color: #EBEEF2;
            }
        """ + StyleManager.scrollbar())

        # Header config
        h_header = self.table.horizontalHeader()
        h_header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h_header.setFixedHeight(56)
        h_header.setStretchLastSection(False)
        h_header.setMouseTracking(True)
        h_header.sectionEntered.connect(self._on_header_hover)
        h_header.sectionClicked.connect(self._on_header_clicked)

        # Column widths
        h_header.setSectionResizeMode(0, QHeaderView.Fixed)
        h_header.resizeSection(0, 50)
        h_header.setSectionResizeMode(1, QHeaderView.Stretch)
        h_header.setSectionResizeMode(2, QHeaderView.Fixed)
        h_header.resizeSection(2, 150)
        h_header.setSectionResizeMode(3, QHeaderView.Fixed)
        h_header.resizeSection(3, 140)
        h_header.setSectionResizeMode(4, QHeaderView.Fixed)
        h_header.resizeSection(4, 170)

        # Row heights
        v_header = self.table.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(52)

        # Row click
        self.table.cellClicked.connect(self._on_cell_clicked)

        table_card_layout.addWidget(self.table)

        # Table footer with count
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E1E8ED;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)
        footer_frame.setFixedHeight(42)

        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(16, 8, 16, 8)

        self.count_label = QLabel("0 نتيجة")
        self.count_label.setStyleSheet("color: #637381; font-size: 10pt; background: transparent;")
        footer_layout.addWidget(self.count_label)
        footer_layout.addStretch()

        table_card_layout.addWidget(footer_frame)
        cards_layout.addWidget(table_card)

        # Load table
        self._update_table()

        main_layout.addWidget(cards_container)
        main_layout.addStretch(1)

    # ── Table ──

    def _update_table(self):
        """Populate table with filtered researchers."""
        researchers = self._researchers
        total = len(researchers)

        self.table.setRowCount(max(total, 1))
        self.table.clearSpans()

        if total == 0:
            self.table.setSpan(0, 0, 1, 5)
            empty_item = QTableWidgetItem("لا يوجد جامعي بيانات مطابقين")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setForeground(QColor("#9CA3AF"))
            self.table.setItem(0, 0, empty_item)
            self.count_label.setText("0 نتيجة")
            return

        for row, researcher in enumerate(researchers):
            # Col 0: Radio button
            radio_container = QWidget()
            radio_container.setStyleSheet("background: transparent;")
            radio_layout = QHBoxLayout(radio_container)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            radio_layout.setAlignment(Qt.AlignCenter)

            radio = QRadioButton()
            radio.setFixedSize(20, 20)
            radio.setStyleSheet("""
                QRadioButton::indicator {
                    width: 18px;
                    height: 18px;
                    border: 2px solid #C4CDD5;
                    border-radius: 9px;
                    background: white;
                }
                QRadioButton::indicator:hover {
                    border-color: #3890DF;
                }
                QRadioButton::indicator:checked {
                    border: 2px solid #3890DF;
                    background: qradialgradient(
                        cx:0.5, cy:0.5, radius:0.4,
                        fx:0.5, fy:0.5,
                        stop:0 #3890DF, stop:0.6 #3890DF, stop:0.7 white
                    );
                }
            """)

            # Check if this was the previously selected researcher
            if self._selected_researcher and researcher['id'] == self._selected_researcher['id']:
                radio.setChecked(True)
                self._selected_radio = radio

            radio.toggled.connect(
                lambda checked, rdata=researcher, r=radio:
                self._on_researcher_selected(rdata, checked, r)
            )

            radio_layout.addWidget(radio)
            self.table.setCellWidget(row, 0, radio_container)

            # Col 1: Name
            name_item = QTableWidgetItem(researcher['display_name'])
            self.table.setItem(row, 1, name_item)

            # Col 2: Availability (colored)
            is_available = researcher['is_available']
            avail_text = "متوفر" if is_available else "غير متوفر"
            avail_item = QTableWidgetItem(avail_text)
            avail_item.setForeground(QColor("#10B981") if is_available else QColor("#EF4444"))
            self.table.setItem(row, 2, avail_item)

            # Col 3: Active assignments
            count = researcher.get('active_assignments', 0)
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, count_item)

            # Col 4: Team name
            team = researcher.get('team_name') or "—"
            team_item = QTableWidgetItem(team)
            self.table.setItem(row, 4, team_item)

        self.count_label.setText(f"{total} نتيجة")

    def _on_cell_clicked(self, row, col):
        """Handle clicking on a table row — select the radio in that row."""
        if col == 0:
            return  # Radio button handles itself
        radio_widget = self.table.cellWidget(row, 0)
        if radio_widget:
            radio = radio_widget.findChild(QRadioButton)
            if radio:
                radio.setChecked(True)

    # ── Selection ──

    def _on_researcher_selected(self, researcher_data, checked, radio):
        """Handle researcher selection via radio button."""
        if not checked:
            return

        # Uncheck previous radio if different
        if self._selected_radio and self._selected_radio is not radio:
            self._selected_radio.setChecked(False)
        self._selected_radio = radio

        self._selected_researcher = {
            'id': researcher_data['id'],
            'name': researcher_data['display_name'],
            'available': researcher_data['is_available'],
            'username': researcher_data.get('username', ''),
            'active_assignments': researcher_data.get('active_assignments', 0),
            'pending_transfers': researcher_data.get('pending_transfers', 0),
            'total_units': researcher_data.get('total_units', 0),
            'tablet_id': researcher_data.get('tablet_id'),
            'team_name': researcher_data.get('team_name'),
        }
        logger.info(f"Researcher selected: {researcher_data['display_name']} ({researcher_data['id']})")

        if self.page and hasattr(self.page, 'enable_next_button'):
            self.page.enable_next_button(True)

        self.researcher_selected.emit(researcher_data['id'])

    # ── Search & Filter ──

    def _filter_and_update(self):
        """Apply search text + header filters and refresh table."""
        search_text = self.researcher_search.text().strip().lower()

        filtered = list(self._all_researchers)

        # Text search (by name)
        if search_text:
            filtered = [
                r for r in filtered
                if search_text in r['display_name'].lower()
                or search_text in (r.get('username') or '').lower()
            ]

        # Availability filter
        avail_filter = self._active_filters.get('availability')
        if avail_filter == "متوفر":
            filtered = [r for r in filtered if r['is_available']]
        elif avail_filter == "غير متوفر":
            filtered = [r for r in filtered if not r['is_available']]

        # Team filter
        team_filter = self._active_filters.get('team')
        if team_filter:
            filtered = [r for r in filtered if (r.get('team_name') or "—") == team_filter]

        self._researchers = filtered
        self._update_table()

    def _on_header_hover(self, logical_index):
        """Change cursor for filterable columns."""
        header = self.table.horizontalHeader()
        if logical_index in (2, 4):
            header.setCursor(Qt.PointingHandCursor)
        else:
            header.setCursor(Qt.ArrowCursor)

    def _on_header_clicked(self, logical_index):
        """Show filter menu for filterable columns."""
        if logical_index not in (2, 4):
            return
        self._show_filter_menu(logical_index)

    def _show_filter_menu(self, column_index):
        """Build and display filter menu for a column."""
        unique_values = set()
        filter_key = None

        if column_index == 2:
            filter_key = 'availability'
            unique_values = {"متوفر", "غير متوفر"}
        elif column_index == 4:
            filter_key = 'team'
            for r in self._all_researchers:
                team = r.get('team_name') or "—"
                unique_values.add(team)

        if not unique_values:
            return

        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 10pt;
                color: #637381;
            }
            QMenu::item:selected {
                background-color: #EFF6FF;
                color: #3890DF;
            }
        """)

        clear_action = QAction("عرض الكل", self)
        clear_action.triggered.connect(lambda: self._apply_filter(filter_key, None))
        menu.addAction(clear_action)
        menu.addSeparator()

        for value in sorted(unique_values):
            action = QAction(value, self)
            action.triggered.connect(lambda checked, v=value: self._apply_filter(filter_key, v))
            if self._active_filters.get(filter_key) == value:
                action.setCheckable(True)
                action.setChecked(True)
            menu.addAction(action)

        header = self.table.horizontalHeader()
        x_pos = header.sectionViewportPosition(column_index)
        y_pos = header.height()
        pos = self.table.mapToGlobal(QPoint(x_pos, y_pos))
        menu.exec_(pos)

    def _apply_filter(self, filter_key, filter_value):
        """Apply a header filter and refresh."""
        self._active_filters[filter_key] = filter_value
        self._filter_and_update()

    def get_selected_researcher(self):
        """Get selected researcher info."""
        return self._selected_researcher
