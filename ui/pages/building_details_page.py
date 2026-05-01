# -*- coding: utf-8 -*-
"""
Building Details Page — عرض تفاصيل المبنى
Card-based view matching review_step.py pattern.
3 cards: building info, stats, location.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon

from models.building import Building
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from controllers.building_controller import BuildingController
from controllers.unit_controller import UnitController
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.design_system import Colors, PageDimensions, ButtonDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.helpers import format_date, build_hierarchical_address
from utils.i18n import I18n
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction, get_text_alignment
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingDetailsPage(QWidget):
    """Building details page — 3 cards (info, stats, location)."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.unit_controller = UnitController(db)
        self.building_controller = BuildingController(db)
        self.current_building = None
        self._user_role = None

        self._setup_ui()

    def configure_for_role(self, role: str):
        """Store user role for lock permission checks."""
        self._user_role = role

    # UI Setup

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self.title_label = self._header.get_title_label()

        self._stat_units = StatPill(tr("page.building_details.units_count"))
        self._header.add_stat_pill(self._stat_units)

        # Action buttons in dark header
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(ScreenScale.w(40), ButtonDimensions.SAVE_HEIGHT)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        self._close_btn.setStyleSheet(StyleManager.dark_action_button())
        self._close_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._close_btn)

        self._lock_btn = QPushButton("")
        self._lock_btn.setFixedHeight(ButtonDimensions.SAVE_HEIGHT)
        self._lock_btn.setMinimumWidth(ButtonDimensions.SAVE_WIDTH)
        self._lock_btn.setCursor(Qt.PointingHandCursor)
        self._lock_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        self._lock_btn.setStyleSheet(StyleManager.dark_action_button())
        self._lock_btn.clicked.connect(self._on_toggle_lock)
        self._lock_btn.setVisible(False)
        self._header.add_action_widget(self._lock_btn)

        self._back_btn = QPushButton(tr("action.back"))
        self._back_btn.setFixedSize(ScreenScale.w(100), ButtonDimensions.SAVE_HEIGHT)
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self._back_btn.setStyleSheet(StyleManager.dark_action_button())
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._header.add_action_widget(self._back_btn)

        layout.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        layout.addWidget(self._accent_line)

        # Light content wrapper
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(StyleManager.page_background())
        content_inner = QVBoxLayout(content_wrapper)
        content_inner.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        content_inner.setSpacing(15)
        layout.addWidget(content_wrapper)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(get_layout_direction())
        scroll_content.setStyleSheet("background: transparent;")
        self._scroll_content = scroll_content
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(20)

        # Card 1: Building info (header + code + address)
        self.info_card, self.info_content, self._info_title_lbl, self._info_subtitle_lbl = self._create_card_base(
            "blue", tr("page.building_details.card_title"), tr("page.building_details.card_subtitle")
        )
        self._scroll_layout.addWidget(self.info_card)

        # Card 2: Stats row
        self.stats_card, self.stats_content = self._create_simple_card()
        self._scroll_layout.addWidget(self.stats_card)

        # Card 3: Location
        self.location_card, self.location_content = self._create_simple_card()
        self._scroll_layout.addWidget(self.location_card)

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        self._scroll = scroll
        content_inner.addWidget(scroll)

        from ui.components.skeleton_loader import DetailSkeleton
        self._skeleton = DetailSkeleton(groups=3, fields_per_group=4, message=tr("page.building_details.loading"))
        content_inner.addWidget(self._skeleton)
        self._skeleton.hide()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)
    # Card Builders (same pattern as review_step.py)

    def _create_card_base(self, icon_name: str, title: str, subtitle: str) -> tuple:
        """Create card with header (icon + title + subtitle). Returns (card, content_layout)."""
        card = QFrame()
        card.setLayoutDirection(get_layout_direction())
        card.setStyleSheet(StyleManager.data_card())
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header row
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Icon (28x28, rounded)
        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 7px;
            }
        """)
        icon_pixmap = Icon.load_pixmap(icon_name, size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        # Title + subtitle
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        title_layout.addWidget(title_lbl)
        title_layout.addWidget(subtitle_lbl)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_container)
        header_layout.addStretch()

        card_layout.addWidget(header)

        # Content container (inherits direction from card parent)
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)

        return card, content_layout, title_lbl, subtitle_lbl

    def _create_simple_card(self) -> tuple:
        """Create a simple card (no header). Returns (card, content_layout)."""
        card = QFrame()
        card.setLayoutDirection(get_layout_direction())
        card.setStyleSheet(StyleManager.data_card())
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)

        return card, content_layout

    def _add_shadow(self, widget: QWidget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        widget.setGraphicsEffect(shadow)
    # Data Loading

    def refresh(self, data=None):
        """Load building and populate cards.

        Args:
            data: Building object or building_id string
        """
        if not data:
            return
        self._scroll.hide()
        self._skeleton.show()
        self._skeleton.start()

        if isinstance(data, Building):
            building = data
        else:
            building = self.building_repo.get_by_id(str(data))
            if not building:
                logger.error(f"Building not found: {data}")
                self._skeleton.stop()
                self._skeleton.hide()
                self._scroll.show()
                return

        self.current_building = building

        # Update lock button (only admin/data_manager can lock)
        is_locked = getattr(building, 'is_locked', False)
        self._lock_btn.setText(
            tr("building.action.unlock") if is_locked else tr("building.action.lock")
        )
        can_lock = self._user_role in ('admin', 'data_manager')
        self._lock_btn.setVisible(can_lock)

        display_id = building.building_id_formatted or building.building_id or "-"
        self._header.set_title(display_id)

        # Show cards immediately with available data
        self._skeleton.stop()
        self._skeleton.hide()
        self._scroll.show()
        self._populate_cards(building)

        # Progressive reveal animation for cards
        from ui.animation_utils import stagger_fade_in
        stagger_fade_in([self.info_card, self.stats_card, self.location_card])

        # Fetch full details + unit counts in background
        building_id_for_api = building.building_uuid or building.building_id
        if building_id_for_api:
            self._spinner.show_loading(tr("page.building_details.loading"))
            auth_token = None
            try:
                main_window = self.window()
                if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
                    auth_token = main_window._api_token
            except Exception:
                pass

            self._refresh_details_worker = ApiWorker(
                self._fetch_building_details_bg,
                building, building_id_for_api, auth_token
            )
            self._refresh_details_worker.finished.connect(self._on_refresh_details_finished)
            self._refresh_details_worker.error.connect(self._on_refresh_details_error)
            self._refresh_details_worker.start()

    def _fetch_building_details_bg(self, building, building_id_for_api, auth_token):
        """Background: re-fetch building from API and recalculate unit counts."""
        from services.map_service_api import MapServiceAPI

        result_building = building
        units_data = None

        # Re-fetch full details from API
        try:
            map_api = MapServiceAPI()
            if auth_token:
                map_api.set_auth_token(auth_token)
            full_building = map_api.get_building_with_polygon(building_id_for_api)
            if full_building:
                result_building = full_building
        except Exception as e:
            logger.warning(f"Could not re-fetch building details from API: {e}")

        # Recalculate unit counts from actual PropertyUnits API data
        building_uuid = result_building.building_uuid
        if building_uuid:
            try:
                if auth_token:
                    self.unit_controller.set_auth_token(auth_token)
                units_result = self.unit_controller.get_units_for_building(building_uuid)
                if units_result.success and units_result.data is not None:
                    units_data = units_result.data
            except Exception as e:
                logger.warning(f"Could not recalculate unit counts: {e}")

        return {"building": result_building, "units_data": units_data}

    def _on_refresh_details_finished(self, result):
        """Callback: update UI with full building details from API."""
        self._spinner.hide_loading()
        if not result or not result.get("building"):
            logger.warning("Refresh details returned empty result")
            return
        building = result["building"]
        units_data = result["units_data"]

        if units_data is not None:
            total = len(units_data)
            residential = sum(
                1 for u in units_data
                if str(getattr(u, 'unit_type', '')).strip() in ('1', 'apartment')
            )
            building.number_of_units = total
            building.number_of_apartments = residential
            building.number_of_shops = total - residential

        self.current_building = building
        display_id = building.building_id_formatted or building.building_id or "-"
        self._header.set_title(display_id)
        self._populate_cards(building)

        # Sync lock button with refreshed API data
        is_locked = getattr(building, 'is_locked', False)
        self._lock_btn.setText(
            tr("building.action.unlock") if is_locked else tr("building.action.lock")
        )

    def _on_refresh_details_error(self, error_msg):
        """Callback: API fetch failed, keep existing data."""
        self._spinner.hide_loading()
        logger.warning(f"Background building details fetch failed: {error_msg}")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _populate_cards(self, building: Building):
        """Populate all 3 cards with building data."""
        self._clear_layout(self.info_content)
        self._clear_layout(self.stats_content)
        self._clear_layout(self.location_content)

        building_code = building.building_id_formatted or building.building_id_display or building.building_id or "-"
        status = building.building_status_display if hasattr(building, 'building_status_display') else "-"
        building_type = building.building_type_display if hasattr(building, 'building_type_display') else "-"
        units_count = str(getattr(building, 'number_of_units', 0))
        apartments_count = str(getattr(building, 'number_of_apartments', 0))
        shops_count = str(getattr(building, 'number_of_shops', 0))
        try:
            self._stat_units.set_count(int(units_count))
        except (ValueError, TypeError):
            self._stat_units.set_count(0)
        entry_date = format_date(getattr(building, 'created_at', None)) or "-"
        location_desc = getattr(building, 'location_description', '-') or '-'
        general_desc = getattr(building, 'general_description', '-') or '-'
        num_label = QLabel(building_code)
        num_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        num_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        num_label.setAlignment(get_text_alignment())
        self.info_content.addWidget(num_label)

        address = build_hierarchical_address(building_obj=building, unit_obj=None, include_unit=False)
        addr_bar = QFrame()
        addr_bar.setFixedHeight(ScreenScale.h(28))
        addr_bar.setStyleSheet("QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }")
        addr_row = QHBoxLayout(addr_bar)
        addr_row.setContentsMargins(12, 0, 12, 0)
        addr_row.setSpacing(8)

        addr_row.addStretch()
        addr_icon = QLabel()
        addr_icon.setStyleSheet("background: transparent; border: none;")
        addr_pixmap = Icon.load_pixmap("dec", size=16)
        if addr_pixmap and not addr_pixmap.isNull():
            addr_icon.setPixmap(addr_pixmap)
        addr_row.addWidget(addr_icon)

        addr_text = QLabel(address if address else "-")
        addr_text.setAlignment(Qt.AlignCenter)
        addr_text.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        addr_text.setStyleSheet("color: #0F5B95; background: transparent; border: none;")
        addr_row.addWidget(addr_text)
        addr_row.addStretch()
        self.info_content.addWidget(addr_bar)
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(0)

        stat_items = [
            (tr("page.building_details.building_status"), status),
            (tr("page.building_details.building_type"), building_type),
            (tr("page.building_details.total_units"), units_count),
            (tr("page.building_details.residential_units"), apartments_count),
            (tr("page.building_details.non_residential_units"), shops_count),
            (tr("page.building_details.entry_date"), entry_date),
        ]

        for label_text, value_text in stat_items:
            section = QWidget()
            section.setStyleSheet("background: transparent;")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)
            section_layout.setAlignment(Qt.AlignCenter)

            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

            val = QLabel(str(value_text))
            val.setAlignment(Qt.AlignCenter)
            val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
            val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

            section_layout.addWidget(lbl)
            section_layout.addWidget(val)
            stats_row.addWidget(section, stretch=1)

        self.stats_content.addLayout(stats_row)
        loc_header = QLabel(tr("page.building_details.location"))
        loc_header.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        loc_header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        self.location_content.addWidget(loc_header)

        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        # Map placeholder
        map_container = QLabel()
        map_container.setFixedSize(ScreenScale.w(400), ScreenScale.h(130))
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("detailsMapContainer")
        map_container.setStyleSheet("QLabel#detailsMapContainer { background-color: #E8E8E8; border-radius: 8px; }")
        map_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_pixmap or map_pixmap.isNull():
            map_pixmap = Icon.load_pixmap("map-placeholder", size=None)
        if map_pixmap and not map_pixmap.isNull():
            map_container.setPixmap(map_pixmap.scaled(400, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        else:
            loc_fallback = Icon.load_pixmap("carbon_location-filled", size=48)
            if loc_fallback and not loc_fallback.isNull():
                map_container.setPixmap(loc_fallback)

        # "فتح الخريطة" button
        map_button = QPushButton(map_container)
        map_button.setFixedSize(ScreenScale.w(94), ScreenScale.h(20))
        map_button.move(8, 8)
        map_button.setCursor(Qt.PointingHandCursor)
        pill_pixmap = Icon.load_pixmap("pill", size=12)
        if pill_pixmap and not pill_pixmap.isNull():
            map_button.setIcon(QIcon(pill_pixmap))
            map_button.setIconSize(QSize(12, 12))
        map_button.setText(tr("page.building_details.open_map"))
        map_button.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_REGULAR))
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
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(8)
        btn_shadow.setXOffset(0)
        btn_shadow.setYOffset(2)
        btn_shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(btn_shadow)
        map_button.clicked.connect(self._open_map_dialog)

        # Location pin icon
        location_icon = QLabel(map_container)
        loc_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if loc_pixmap and not loc_pixmap.isNull():
            location_icon.setPixmap(loc_pixmap)
            location_icon.setFixedSize(ScreenScale.w(56), ScreenScale.h(56))
            location_icon.move(172, 37)
            location_icon.setStyleSheet("background: transparent;")

        content_row.addWidget(map_container)

        # General description
        gen_desc_section = QVBoxLayout()
        gen_desc_section.setSpacing(4)
        gen_desc_lbl = QLabel(tr("page.building_details.description"))
        gen_desc_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        gen_desc_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        gen_desc_val = QLabel(general_desc)
        gen_desc_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        gen_desc_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        gen_desc_val.setWordWrap(True)
        gen_desc_section.addWidget(gen_desc_lbl)
        gen_desc_section.addWidget(gen_desc_val)
        gen_desc_section.addStretch(1)
        content_row.addLayout(gen_desc_section, stretch=1)

        self.location_content.addLayout(content_row)
    def _on_toggle_lock(self):
        """Toggle building lock state with confirmation."""
        if not self.current_building:
            return
        if self._user_role not in ('admin', 'data_manager'):
            return
        from ui.error_handler import ErrorHandler
        is_locked = getattr(self.current_building, 'is_locked', False)
        msg_key = "page.buildings.confirm_unlock" if is_locked else "page.buildings.confirm_lock"
        title_key = "building.action.unlock" if is_locked else "building.action.lock"
        if not ErrorHandler.confirm(self, tr(msg_key), tr(title_key)):
            return
        new_lock_state = not is_locked
        op_result = self.building_controller.toggle_building_lock(
            self.current_building.building_uuid or self.current_building.building_id,
            new_lock_state
        )
        if op_result.success:
            self.current_building.is_locked = new_lock_state
            self._lock_btn.setText(
                tr("building.action.unlock") if new_lock_state else tr("building.action.lock")
            )
            Toast.show_toast(self, tr("building.lock_success"), Toast.SUCCESS)
        else:
            Toast.show_toast(self, tr("building.lock_failed"), Toast.ERROR)

    # Map Dialog

    def _open_map_dialog(self):
        """Open map dialog in read-only mode."""
        from ui.components.building_map_dialog_v2 import show_building_map_dialog

        if not self.current_building:
            return

        auth_token = None
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, '_api_token'):
                auth_token = main_window._api_token
        except Exception as e:
            logger.warning(f"Could not get auth token: {e}")

        show_building_map_dialog(
            db=self.db,
            selected_building_id=self.current_building.building_uuid or self.current_building.building_id,
            auth_token=auth_token,
            read_only=True,
            selected_building=self.current_building,
            parent=self
        )

    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)
        for card in [self.info_card, self.stats_card, self.location_card]:
            card.setLayoutDirection(direction)
        self._back_btn.setText(tr("action.back"))
        self._stat_units.set_label(tr("page.building_details.units_count"))
        self._info_title_lbl.setText(tr("page.building_details.card_title"))
        self._info_subtitle_lbl.setText(tr("page.building_details.card_subtitle"))
        if self.current_building:
            is_locked = getattr(self.current_building, 'is_locked', False)
            self._lock_btn.setText(
                tr("building.action.unlock") if is_locked else tr("building.action.lock")
            )
            self._populate_cards(self.current_building)
