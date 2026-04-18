# -*- coding: utf-8 -*-
"""Field work preparation step 2: select field researcher."""

from pathlib import Path
import sys

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QToolButton, QSizePolicy, QScrollArea,
    QMenu, QAction,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPoint, QTimer
from PyQt5.QtGui import QIcon, QColor

from ui.components.animated_card import AnimatedCard
from ui.components.empty_state import EmptyState
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.animation_utils import stagger_fade_in
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.i18n import I18n
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from utils.logger import get_logger

logger = get_logger(__name__)


class _ResearcherCard(AnimatedCard):
    """Card-based researcher item with selectable radio-like state."""

    card_selected = pyqtSignal(object)  # Emits researcher dict

    def __init__(self, researcher_data: dict, parent=None):
        self.researcher_data = researcher_data
        self._selected = False

        # Green strip for available, red for unavailable
        is_available = researcher_data.get('is_available', True)
        status_color = "#10B981" if is_available else "#EF4444"

        super().__init__(
            parent,
            card_height=90,
            border_radius=10,
            show_chevron=False,
            show_strip=False,
            status_color=status_color,
            strip_width=4,
            clickable=True,
            lift_target=2.0,
        )

    def _build_content(self, layout):
        """Populate card with researcher info."""
        # Top row: name (bold) + role badge
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(self.researcher_data.get('display_name', ''))
        name_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        name_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent;")
        apply_label_alignment(name_label)
        top_row.addWidget(name_label)

        # Availability badge
        is_available = self.researcher_data.get('is_available', True)
        avail_text = tr("wizard.step2.available") if is_available else tr("wizard.step2.unavailable")
        avail_color = "#10B981" if is_available else "#EF4444"
        avail_bg = "#ECFDF5" if is_available else "#FEF2F2"

        avail_badge = QLabel(avail_text)
        avail_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        avail_badge.setStyleSheet(
            f"color: {avail_color}; background-color: {avail_bg}; "
            "padding: 2px 10px; border-radius: 9px;"
        )
        top_row.addWidget(avail_badge)

        # Team badge
        team = self.researcher_data.get('team_name')
        if team:
            team_badge = QLabel(team)
            team_badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
            team_badge.setStyleSheet(
                f"color: {Colors.PRIMARY_BLUE}; background-color: #EBF5FF; "
                "padding: 2px 10px; border-radius: 9px;"
            )
            top_row.addWidget(team_badge)

        top_row.addStretch()
        layout.addLayout(top_row)

        # Bottom row: username + assignment count
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        bottom_row.setContentsMargins(0, 0, 0, 0)

        username = self.researcher_data.get('username', '')
        if username:
            user_label = QLabel(f"@{username}")
            user_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            user_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
            apply_label_alignment(user_label)
            bottom_row.addWidget(user_label)

        active = self.researcher_data.get('active_assignments', 0)
        count_label = QLabel(f"{tr('wizard.step2.col_active_tasks')}: {active}")
        count_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        count_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
        apply_label_alignment(count_label)
        bottom_row.addWidget(count_label)

        bottom_row.addStretch()
        layout.addLayout(bottom_row)

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
            super()._apply_base_style()

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
            super()._apply_hover_style()

    @property
    def is_selected(self):
        return self._selected

    @is_selected.setter
    def is_selected(self, value):
        if self._selected != value:
            self._selected = value
            self._apply_base_style()
            self.update()

    def mousePressEvent(self, event):
        """Emit card_selected on click (radio-style, only one can be active)."""
        if event.button() == Qt.LeftButton:
            self.card_selected.emit(self.researcher_data)
        super().mousePressEvent(event)


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
        }

        self._all_researchers = []
        self._researchers = []

        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

        # Load researchers from API (non-blocking)
        self._spinner.show_loading(tr("wizard.step2.loading_researchers"))
        self._researchers_worker = ApiWorker(self._fetch_researchers_from_db)
        self._researchers_worker.finished.connect(self._on_researchers_loaded)
        self._researchers_worker.error.connect(self._on_researchers_load_error)
        self._researchers_worker.start()

    def _on_researchers_loaded(self, researchers):
        """Handle successful researcher fetch."""
        self._all_researchers = researchers or []
        self._researchers = list(self._all_researchers)
        self._update_cards()
        self._spinner.hide_loading()

    def _on_researchers_load_error(self, error_msg):
        """Handle failed researcher fetch."""
        logger.warning(f"Failed to load researchers: {error_msg}")
        self._all_researchers = []
        self._researchers = []
        self._update_cards()
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("wizard.step2.err_load_researchers"), Toast.ERROR)

    @staticmethod
    def _fetch_researchers_from_db():
        """Fetch field collectors from BuildingAssignments API.

        Returns list of dicts with full API data for each collector.
        Runs in a background thread via ApiWorker.
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

        return []

    def _setup_ui(self):
        """Setup UI - search card + table + selected card."""
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        pad_h = PageDimensions.content_padding_h()
        main_layout.setContentsMargins(pad_h, 0, pad_h, 0)
        main_layout.setSpacing(0)

        cards_container = QWidget()
        cards_container.setStyleSheet("background-color: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 15, 0, 16)
        cards_layout.setSpacing(15)
        search_card = QFrame()
        search_card.setObjectName("researcherCard")
        search_card.setStyleSheet(f"""
            QFrame#researcherCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        search_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        search_card_layout = QVBoxLayout(search_card)
        search_card_layout.setContentsMargins(12, 12, 12, 12)
        search_card_layout.setSpacing(6)

        self._select_label = QLabel(tr("wizard.step2.select_researcher"))
        self._select_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._select_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        search_card_layout.addWidget(self._select_label)

        # Search bar
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
            search_icon_btn.setText("S")

        search_icon_btn.clicked.connect(self._filter_and_update)

        self.researcher_search = QLineEdit()
        self.researcher_search.setPlaceholderText(tr("wizard.step2.search_placeholder"))
        self.researcher_search.setLayoutDirection(get_layout_direction())
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

        # Filter buttons row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._filter_avail_btn = QToolButton()
        self._filter_avail_btn.setText(tr("wizard.step2.col_availability") + " \u25BE")
        self._filter_avail_btn.setCursor(Qt.PointingHandCursor)
        self._filter_avail_btn.setStyleSheet(f"""
            QToolButton {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 9pt;
                color: #637381;
                background: #F8F9FA;
            }}
            QToolButton:hover {{
                background: #EFF6FF;
                border-color: {Colors.PRIMARY_BLUE};
                color: {Colors.PRIMARY_BLUE};
            }}
        """)
        self._filter_avail_btn.clicked.connect(lambda: self._show_filter_menu(2))
        filter_row.addWidget(self._filter_avail_btn)

        filter_row.addStretch()
        search_card_layout.addLayout(filter_row)

        cards_layout.addWidget(search_card)

        # Scroll area for researcher cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()

        scroll.setWidget(self._scroll_content)
        cards_layout.addWidget(scroll, 1)

        # Empty state label
        self._empty_label = EmptyState(
            icon_name="user-group",
            title=tr("wizard.step2.no_matching_collectors"),
        )
        self._empty_label.setMinimumHeight(ScreenScale.h(150))
        self._empty_label.setVisible(False)
        cards_layout.addWidget(self._empty_label)

        # Footer with count
        self.count_label = QLabel(tr("wizard.step2.result_count", count=0))
        self.count_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.count_label.setStyleSheet("color: #637381; background: transparent;")
        cards_layout.addWidget(self.count_label)

        # Card state
        self._card_widgets: list = []
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        # Initial populate
        self._update_cards()

        main_layout.addWidget(cards_container, 1)

    # ── Cards ──

    def _update_cards(self):
        """Populate cards with filtered researchers."""
        self._clear_cards()

        researchers = self._researchers
        total = len(researchers)

        if total == 0:
            self._empty_label.setVisible(True)
            self.count_label.setText(tr("wizard.step2.result_count", count=0))
            return

        self._empty_label.setVisible(False)

        for researcher in researchers:
            card = _ResearcherCard(researcher, parent=self._scroll_content)
            card.card_selected.connect(self._on_card_selected)

            # Restore selection state
            if self._selected_researcher and researcher['id'] == self._selected_researcher['id']:
                card.is_selected = True

            self._card_widgets.append(card)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        self.count_label.setText(tr("wizard.step2.result_count", count=total))

        # Animate entrance
        if self._card_widgets:
            stagger_fade_in(self._card_widgets)
            self._shimmer_timer.start()

        # Verify selection still exists
        if self._selected_researcher:
            selected_id = self._selected_researcher['id']
            if not any(r['id'] == selected_id for r in researchers):
                self._selected_researcher = None

    def _clear_cards(self):
        """Remove all researcher cards."""
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            try:
                card.card_selected.disconnect()
            except (TypeError, RuntimeError):
                pass
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_card_shimmer(self):
        """Drive shimmer animation on all visible cards."""
        for card in self._card_widgets:
            card.update()

    # ── Selection ──

    def _on_card_selected(self, researcher_data):
        """Handle researcher card click (radio-style: only one selected)."""
        # Deselect all cards
        for card in self._card_widgets:
            card.is_selected = (card.researcher_data['id'] == researcher_data['id'])

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
        """Apply search text + filters and refresh cards."""
        search_text = self.researcher_search.text().strip().lower()

        filtered = list(self._all_researchers)

        # Text search (by name or username)
        if search_text:
            filtered = [
                r for r in filtered
                if search_text in r['display_name'].lower()
                or search_text in (r.get('username') or '').lower()
            ]

        # Availability filter
        avail_filter = self._active_filters.get('availability')
        if avail_filter == "available":
            filtered = [r for r in filtered if r['is_available']]
        elif avail_filter == "unavailable":
            filtered = [r for r in filtered if not r['is_available']]

        self._researchers = filtered
        self._update_cards()

    def _show_filter_menu(self, column_index):
        """Build and display filter menu for availability."""
        unique_values = set()
        filter_key = None

        if column_index == 2:
            filter_key = 'availability'
            unique_values = {"available", "unavailable"}

        if not unique_values:
            return

        menu = QMenu(self)
        menu.setLayoutDirection(get_layout_direction())
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: white;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px;
            }}
            QMenu::item {{
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 10pt;
                color: #637381;
            }}
            QMenu::item:selected {{
                background-color: #EFF6FF;
                color: {Colors.PRIMARY_BLUE};
            }}
        """)

        clear_action = QAction(tr("wizard.step2.show_all"), self)
        clear_action.triggered.connect(lambda: self._apply_filter(filter_key, None))
        menu.addAction(clear_action)
        menu.addSeparator()

        _availability_labels = {
            "available": tr("wizard.step2.available"),
            "unavailable": tr("wizard.step2.unavailable"),
        }
        for value in sorted(unique_values):
            display_text = _availability_labels.get(value, value)
            action = QAction(display_text, self)
            action.triggered.connect(lambda checked, v=value: self._apply_filter(filter_key, v))
            if self._active_filters.get(filter_key) == value:
                action.setCheckable(True)
                action.setChecked(True)
            menu.addAction(action)

        # Show below the filter button
        if hasattr(self, '_filter_avail_btn'):
            pos = self._filter_avail_btn.mapToGlobal(
                QPoint(0, self._filter_avail_btn.height())
            )
        else:
            pos = self.mapToGlobal(QPoint(0, 0))
        menu.exec_(pos)

    def _apply_filter(self, filter_key, filter_value):
        """Apply a filter and refresh."""
        self._active_filters[filter_key] = filter_value
        self._filter_and_update()

    def get_selected_researcher(self):
        """Get selected researcher info."""
        return self._selected_researcher

    def update_language(self, is_arabic: bool = True):
        """Update UI text after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Card title
        self._select_label.setText(tr("wizard.step2.select_researcher"))

        # Search placeholder
        self.researcher_search.setPlaceholderText(tr("wizard.step2.search_placeholder"))
        self.researcher_search.setLayoutDirection(get_layout_direction())

        # Filter button
        if hasattr(self, '_filter_avail_btn'):
            self._filter_avail_btn.setText(tr("wizard.step2.col_availability") + " \u25BE")

        # Empty state
        self._empty_label.set_title(tr("wizard.step2.no_matching_collectors"))

        # Footer count label
        count = len(self._researchers)
        self.count_label.setText(tr("wizard.step2.result_count", count=count))

        # Re-populate cards to update text
        self._update_cards()
