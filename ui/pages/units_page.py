# -*- coding: utf-8 -*-
"""Property Units list page with animated card-based layout and dark header."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QDialog, QAbstractItemView, QSizePolicy,
    QScrollArea, QStackedWidget, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QIcon, QCursor, QFont

from app.config import Config
from repositories.database import Database
from repositories.unit_repository import UnitRepository
from repositories.building_repository import BuildingRepository
from models.unit import PropertyUnit
from controllers.unit_controller import UnitController
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from services.display_mappings import (
    get_unit_type_display, get_unit_status_display,
    get_unit_type_options, get_unit_status_options
)
from ui.wizards.office_survey.dialogs.unit_dialog import UnitDialog as WizardUnitDialog
from ui.components.building_picker_dialog import BuildingPickerDialog
from ui.components.toast import Toast
from ui.components.primary_button import PrimaryButton
from ui.error_handler import ErrorHandler
from utils.i18n import I18n
from utils.logger import get_logger
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction
from ui.components.animated_card import AnimatedCard, EmptyStateAnimated, animate_card_entrance
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager

logger = get_logger(__name__)


class _UnitCard(AnimatedCard):
    """Unit card showing unit number, floor, type, area, status."""

    _STATUS_COLORS = {
        "occupied": "#10B981",
        "vacant": "#F59E0B",
        "under_maintenance": "#EF4444",
    }
    _STATUS_STYLES = {
        "occupied": {"bg": "#ECFDF5", "fg": "#065F46", "border": "#6EE7B7"},
        "vacant": {"bg": "#FFFBEB", "fg": "#92400E", "border": "#FCD34D"},
        "under_maintenance": {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
    }

    def __init__(self, unit, parent=None):
        self._unit = unit
        status_key = self._get_status_key(unit)
        color = self._STATUS_COLORS.get(status_key, "#3890DF")
        super().__init__(parent, card_height=100, status_color=color)

    def _get_status_key(self, unit):
        status = getattr(unit, 'apartment_status', None)
        if status is None:
            return "vacant"
        s = str(status).strip().lower()
        if s in ("occupied", "\u0645\u0623\u0647\u0648\u0644\u0629", "1"):
            return "occupied"
        elif s in ("vacant", "\u0634\u0627\u063a\u0631\u0629", "2"):
            return "vacant"
        return "under_maintenance"

    def _build_content(self, layout):
        from PyQt5.QtWidgets import QHBoxLayout, QLabel
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        from ui.font_utils import create_font, FontManager
        from ui.design_system import Colors
        from services.translation_manager import tr
        from services.display_mappings import get_unit_type_display, get_unit_status_display

        u = self._unit

        # Row 1: Unit number + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        display_num = str(u.unit_number or u.apartment_number or "?")
        num_label = QLabel(f"{tr('page.unit_details.unit_number')}: {display_num}")
        num_label.setFont(create_font(size=13, weight=QFont.Bold))
        num_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        row1.addWidget(num_label)
        row1.addStretch()

        status_key = self._get_status_key(u)
        style = self._STATUS_STYLES.get(status_key, self._STATUS_STYLES["vacant"])
        status_text = get_unit_status_display(getattr(u, 'apartment_status', None)) if hasattr(u, 'apartment_status') else "-"
        badge = QLabel(status_text)
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(22)
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 11px; "
            f"padding: 0 10px; }}"
        )
        row1.addWidget(badge)
        layout.addLayout(row1)

        # Row 2: Floor + Type + Area
        parts = []
        if u.floor_number is not None:
            parts.append(f"{tr('page.unit_details.floor_number')}: {u.floor_number}")
        unit_type = getattr(u, 'unit_type_display_ar', None) or get_unit_type_display(getattr(u, 'unit_type', None))
        if unit_type and unit_type != "-":
            parts.append(unit_type)
        if u.area_sqm:
            try:
                parts.append(f"{float(u.area_sqm):.1f} {tr('unit.sqm')}")
            except (ValueError, TypeError):
                pass
        details = QLabel(" \u2009\u00b7\u2009 ".join(parts) if parts else "-")
        details.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        details.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(details)

        # Row 3: Description
        desc = u.property_description or ""
        if desc:
            desc_label = QLabel(desc[:80] + ("..." if len(desc) > 80 else ""))
            desc_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            desc_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none; opacity: 0.7;")
            layout.addWidget(desc_label)


class UnitsPage(QWidget):
    """Property Units management page -- grouped by building, API-backed."""

    view_unit = pyqtSignal(object)
    edit_unit_signal = pyqtSignal(object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.building_repo = BuildingRepository(db)

        self._api_service = get_api_client()
        self.unit_controller = UnitController(db)

        # Grouped data: list of BuildingWithUnitsDto dicts
        self._groups = []
        # Flat list of row descriptors
        self._rows = []
        self._total_units = 0
        self._total_buildings = 0

        self._current_page = 1
        self._rows_per_page = 20
        self._total_pages = 1

        # API-side filters (sent as query params)
        self._active_filters = {
            'building_id': None,
            'unit_type': None,
            'unit_status': None,
        }
        self._buildings_cache = {}

        self._card_widgets = []

        # Shared timer for card shimmer animation
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.units.title"))

        self._stat_units = StatPill(tr("page.units.stat_units"))
        self._header.add_stat_pill(self._stat_units)

        self._stat_buildings = StatPill(tr("page.units.stat_buildings"))
        self._header.add_stat_pill(self._stat_buildings)

        # Add button in header
        self.add_btn = PrimaryButton(tr("page.units.add_new"), icon_name="icon")
        self.add_btn.clicked.connect(self._on_add_unit)
        self._header.add_action_widget(self.add_btn)

        main.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        main.addWidget(self._accent_line)

        # Light content area
        self._content_wrapper = QWidget()
        self._content_wrapper.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        content_layout = QVBoxLayout(self._content_wrapper)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        content_layout.setSpacing(0)

        # Stacked widget: cards scroll vs empty state
        self._stack = QStackedWidget()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)

        self._empty_state = EmptyStateAnimated(
            title=tr("page.units.no_units"),
            description=tr("page.units.empty_description") if hasattr(tr, '__call__') else "",
        )
        self._stack.addWidget(self._empty_state)

        content_layout.addWidget(self._stack, 1)

        # Pagination bar
        self._pagination = self._create_pagination()
        content_layout.addWidget(self._pagination)

        main.addWidget(self._content_wrapper, 1)

        # Loading spinner overlay
        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_pagination(self):
        bar = QFrame()
        bar.setFixedHeight(40)
        bar.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 6, 4, 0)
        layout.addStretch()

        _NAV_BTN = """
            QPushButton {
                background: rgba(56, 144, 223, 0.08);
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 6px; color: #3890DF;
                padding: 0 10px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(56, 144, 223, 0.18); }
            QPushButton:disabled { color: #B0BEC5; background: transparent; border-color: #E0E0E0; }
        """
        self.prev_btn = QPushButton("\u276E")
        self.prev_btn.setFixedSize(32, 28)
        self.prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.prev_btn.setStyleSheet(_NAV_BTN)
        self.prev_btn.clicked.connect(self._on_prev_page)
        layout.addWidget(self.prev_btn)

        self._page_info = QLabel("")
        self._page_info.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._page_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._page_info.setAlignment(Qt.AlignCenter)
        self._page_info.setMinimumWidth(80)
        layout.addWidget(self._page_info)

        self.next_btn = QPushButton("\u276F")
        self.next_btn.setFixedSize(32, 28)
        self.next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.next_btn.setStyleSheet(_NAV_BTN)
        self.next_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self.next_btn)

        return bar

    # -- Data loading --

    def refresh(self, data=None):
        logger.debug("Refreshing units page")
        self._load_units()

    def configure_for_role(self, role: str):
        """Enable/disable CRUD buttons based on user role."""
        self._user_role = role
        can_create = role in {"admin", "data_manager", "office_clerk", "field_researcher"}
        if hasattr(self, 'add_btn'):
            self.add_btn.setEnabled(can_create)

    def _set_auth_token(self):
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._api_service.set_access_token(main_window._api_token)
            self.unit_controller.set_auth_token(main_window._api_token)

    def _dto_to_unit(self, dto: dict, building_uuid: str = None) -> PropertyUnit:
        return PropertyUnit(
            unit_uuid=dto.get("id") or dto.get("unitUuid") or "",
            unit_id=dto.get("unitId") or "",
            building_id=building_uuid or dto.get("buildingId") or "",
            unit_type=dto.get("unitType") or 1,
            unit_number=dto.get("unitIdentifier") or dto.get("unitNumber") or "",
            floor_number=dto.get("floorNumber") if dto.get("floorNumber") is not None else 0,
            apartment_number=dto.get("unitIdentifier") or "",
            apartment_status=dto.get("status") or 1,
            property_description=dto.get("description") or "",
            area_sqm=dto.get("areaSquareMeters"),
        )

    def _load_units(self):
        self._spinner.show_loading(tr("page.units.loading"))
        self._set_auth_token()
        self._load_units_worker = ApiWorker(
            self.unit_controller.get_units_grouped,
            building_id=self._active_filters.get('building_id'),
            unit_type=self._active_filters.get('unit_type'),
            status=self._active_filters.get('unit_status'),
        )
        self._load_units_worker.finished.connect(self._on_load_units_finished)
        self._load_units_worker.error.connect(self._on_load_units_error)
        self._load_units_worker.start()

    def _on_load_units_finished(self, result):
        self._spinner.hide_loading()
        if result.success:
            self._groups = result.data or []
        else:
            logger.warning(f"Failed to load grouped units: {result.message}")
            self._groups = []
        self._total_units = sum(g.get('unitCount', 0) for g in self._groups)
        self._total_buildings = len(self._groups)
        self._rebuild_rows()
        self._current_page = 1
        self._populate_cards()

    def _on_load_units_error(self, error_msg):
        self._spinner.hide_loading()
        logger.warning(f"API grouped load failed: {error_msg}")
        Toast.show_toast(self, tr("page.units.load_error") if tr("page.units.load_error") != "page.units.load_error" else str(error_msg), Toast.ERROR)
        self._groups = []
        self._total_units = 0
        self._total_buildings = 0
        self._rebuild_rows()
        self._current_page = 1
        self._populate_cards()

    def _rebuild_rows(self):
        self._rows = []
        for group in self._groups:
            building = self._get_building_for_group(group)
            for dto in group.get('propertyUnits', []):
                unit = self._dto_to_unit(dto, group.get('buildingId'))
                self._rows.append({'type': 'unit', 'group': group, 'unit': unit, 'building': building})

    # -- Card population --

    def _populate_cards(self):
        try:
            self._clear_cards()

            # Update stat pills
            self._stat_units.set_count(self._total_units)
            self._stat_buildings.set_count(self._total_buildings)

            total_rows = len(self._rows)
            self._total_pages = max(1, (total_rows + self._rows_per_page - 1) // self._rows_per_page)
            self._current_page = min(self._current_page, self._total_pages)

            if total_rows == 0:
                self._stack.setCurrentIndex(1)
                self._empty_state.set_title(tr("page.units.no_units"))
                self._update_pagination_info()
                return

            self._stack.setCurrentIndex(0)

            start_idx = (self._current_page - 1) * self._rows_per_page
            end_idx = min(start_idx + self._rows_per_page, total_rows)
            page_rows = self._rows[start_idx:end_idx]

            for row_data in page_rows:
                unit = row_data['unit']
                group = row_data['group']
                card = _UnitCard(unit)
                card.clicked.connect(lambda u=unit, g=group: self._on_card_clicked(u, g))
                self._cards_layout.insertWidget(
                    self._cards_layout.count() - 1, card
                )
                self._card_widgets.append(card)

            self._update_pagination_info()
            self._animate_card_entrance()

            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()
        except Exception as e:
            logger.error(f"Error populating unit cards: {e}")
            self._stack.setCurrentIndex(1)

    def _animate_card_entrance(self):
        count = len(self._card_widgets)
        if count > 30 or count == 0:
            return

        for i, card in enumerate(self._card_widgets):
            opacity_eff = QGraphicsOpacityEffect(card)
            opacity_eff.setOpacity(0.0)
            card.setGraphicsEffect(opacity_eff)

            anim = QPropertyAnimation(opacity_eff, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _restore_shadow(c=card):
                try:
                    s = QGraphicsDropShadowEffect(c)
                    s.setBlurRadius(20)
                    s.setOffset(0, 4)
                    s.setColor(QColor(0, 0, 0, 22))
                    c.setGraphicsEffect(s)
                except RuntimeError:
                    pass

            anim.finished.connect(_restore_shadow)
            QTimer.singleShot(i * 40, anim.start)

            card._entrance_anim = anim
            card._entrance_effect = opacity_eff

    def _clear_cards(self):
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            if hasattr(card, '_entrance_anim') and card._entrance_anim:
                try:
                    card._entrance_anim.stop()
                except RuntimeError:
                    pass
            try:
                card.clicked.disconnect()
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_card_shimmer(self):
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    def _update_pagination_info(self):
        total = len(self._rows)
        ps = self._rows_per_page
        total_pages = max(1, (total + ps - 1) // ps)
        page = self._current_page
        start = (page - 1) * ps + 1
        end = min(page * ps, total)
        if total > 0:
            self._page_info.setText(f"{start}-{end}  /  {total}")
        else:
            self._page_info.setText("")
        self.prev_btn.setEnabled(page > 1)
        self.next_btn.setEnabled(page < total_pages)

    # -- Card interactions --

    def _on_card_clicked(self, unit, group):
        self.view_unit.emit(unit)

    def _on_card_right_click(self, unit, group, pos):
        self._show_card_actions_menu(unit, group, pos)

    def _show_card_actions_menu(self, unit: PropertyUnit, group: dict, global_pos=None):
        from PyQt5.QtWidgets import QMenu, QAction
        from ui.components.icon import Icon

        menu = QMenu(self)
        menu.setFixedSize(200, 149)

        view_icon = Icon.load_qicon("eye-open", size=18)
        view_action = QAction("  " + tr("action.view"), self)
        if view_icon:
            view_action.setIcon(view_icon)
        view_action.triggered.connect(lambda: self.view_unit.emit(unit))
        menu.addAction(view_action)

        _role = getattr(self, '_user_role', 'admin')
        edit_icon = Icon.load_qicon("edit-01", size=18)
        edit_action = QAction("  " + tr("action.edit"), self)
        if edit_icon:
            edit_action.setIcon(edit_icon)
        edit_action.triggered.connect(lambda: self._edit_unit(unit, group))
        edit_action.setEnabled(_role in {"admin", "data_manager", "office_clerk", "field_researcher"})
        menu.addAction(edit_action)

        delete_icon = Icon.load_qicon("delete", size=18)
        delete_action = QAction("  " + tr("action.delete"), self)
        if delete_icon:
            delete_action.setIcon(delete_icon)
        delete_action.triggered.connect(lambda: self._delete_unit(unit))
        delete_action.setEnabled(_role in {"admin", "data_manager"})
        menu.addAction(delete_action)

        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 10px;
                border-radius: 4px;
                color: #212B36;
                font-size: 11pt;
                font-weight: 400;
            }
            QMenu::item:selected {
                background-color: #F6F6F7;
            }
        """)
        if global_pos:
            menu.exec_(global_pos)
        else:
            menu.exec_(QCursor.pos())

    # -- Pagination --

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._populate_cards()

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._populate_cards()

    def _go_to_page(self, page_num):
        if 1 <= page_num <= self._total_pages:
            self._current_page = page_num
            self._populate_cards()

    # -- Filter system --

    def _apply_filter(self, filter_key: str, filter_value):
        """Apply API-side filter and reload from server."""
        value = filter_value
        if filter_key in ('unit_type', 'unit_status') and value is not None:
            try:
                value = int(value)
            except (ValueError, TypeError):
                pass
        self._active_filters[filter_key] = value
        self._current_page = 1
        self._load_units()

    # -- Building helper --

    def _get_building_for_group(self, group: dict):
        """Return a Building object for a group dict using API only."""
        building_id = group.get('buildingId')
        if not building_id:
            return None

        if building_id in self._buildings_cache:
            return self._buildings_cache[building_id]

        building = None
        try:
            if self._api_service:
                dto = self._api_service.get_building_by_id(building_id)
                if dto and isinstance(dto, dict):
                    from models.building import Building
                    b = Building()
                    b.building_uuid = building_id
                    b.building_id = dto.get('buildingCode') or dto.get('buildingId', '')
                    b.building_id_formatted = (dto.get('buildingCodeFormatted') or
                                               b.building_id)
                    building = b
        except Exception:
            pass

        if building:
            self._buildings_cache[building_id] = building
            return building

        # Fallback: minimal object with short buildingNumber from group
        from models.building import Building
        b = Building()
        b.building_uuid = building_id
        b.building_id = group.get('buildingNumber') or building_id
        self._buildings_cache[building_id] = b
        return b

    # -- CRUD operations --

    def _on_add_unit(self):
        """Open building picker then add unit dialog."""
        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None

        picker = BuildingPickerDialog(
            db=self.db,
            api_service=self._api_service,
            auth_token=auth_token,
            parent=self
        )
        if picker.exec_() != QDialog.Accepted:
            return

        building = picker.get_selected_building()
        if not building:
            return

        # Cache the selected building for future _edit_unit lookups
        bid = building.building_uuid or building.building_id
        if bid:
            self._buildings_cache[bid] = building

        dialog = WizardUnitDialog(building, self.db, parent=self, auth_token=auth_token)
        if dialog.exec_() == QDialog.Accepted:
            Toast.show_toast(self, tr("success.unit.added"), Toast.SUCCESS)
            self._load_units()

    def _on_add_unit_for_building(self, group: dict):
        """Add a unit for a specific building (from header add button)."""
        building = self._get_building_for_group(group)
        if not building:
            Toast.show_toast(self, tr("page.units.building_not_found"), Toast.ERROR)
            return
        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None
        dialog = WizardUnitDialog(building, self.db, parent=self, auth_token=auth_token)
        if dialog.exec_() == QDialog.Accepted:
            Toast.show_toast(self, tr("success.unit.added"), Toast.SUCCESS)
            self._load_units()

    def _edit_unit(self, unit: PropertyUnit, group: dict):
        building = self._get_building_for_group(group)
        if not building:
            Toast.show_toast(self, tr("page.units.building_not_found"), Toast.ERROR)
            return

        unit_data = unit.to_dict()
        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None

        dialog = WizardUnitDialog(building, self.db, unit_data=unit_data, parent=self, auth_token=auth_token)
        if dialog.exec_() == QDialog.Accepted:
            updated_data = dialog.get_unit_data()
            try:
                self._set_auth_token()
                self._api_service.update_property_unit(unit.unit_uuid, updated_data)
                Toast.show_toast(self, tr("success.unit.updated"), Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"API unit update failed: {e}")
                Toast.show_toast(self, tr("error.unit.update_failed_with_reason", error=str(e)), Toast.ERROR)

    def _delete_unit(self, unit: PropertyUnit):
        unit_label = unit.unit_number or unit.unit_uuid or ""
        if ErrorHandler.confirm(
            self,
            tr("page.units.delete_confirm", unit_label=unit_label),
            tr("confirm.delete.title")
        ):
            self._set_auth_token()
            success = self._api_service.delete_property_unit(unit.unit_uuid)
            if success:
                Toast.show_toast(self, tr("success.unit.deleted"), Toast.SUCCESS)
                self._load_units()
            else:
                logger.error(f"Failed to delete unit {unit.unit_uuid}")
                Toast.show_toast(self, tr("error.unit.delete_failed"), Toast.ERROR)

    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        self._header.set_title(tr("page.units.title"))
        self.add_btn.setText(tr("page.units.add_new"))
        self._stat_units.set_label(tr("page.units.stat_units"))
        self._stat_buildings.set_label(tr("page.units.stat_buildings"))

        self._scroll.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)

        if self._rows:
            self._populate_cards()
        else:
            self._empty_state.set_title(tr("page.units.no_units"))
