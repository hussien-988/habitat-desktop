# -*- coding: utf-8 -*-
"""
Property Units list page with filters and CRUD operations.
Implements UC-002: Property Unit Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QDialog, QLineEdit, QListWidget, QListWidgetItem,
    QAbstractItemView, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import QColor, QIcon, QCursor, QFont

from app.config import Config
from repositories.database import Database
from repositories.unit_repository import UnitRepository
from repositories.building_repository import BuildingRepository
from models.unit import PropertyUnit
from controllers.unit_controller import UnitController
from services.api_client import get_api_client
from services.display_mappings import (
    get_unit_type_display, get_unit_status_display,
    get_unit_type_options, get_unit_status_options
)
from ui.wizards.office_survey.dialogs.unit_dialog import UnitDialog as WizardUnitDialog
from ui.components.toast import Toast
from ui.components.primary_button import PrimaryButton
from ui.error_handler import ErrorHandler
from utils.i18n import I18n
from utils.logger import get_logger
from ui.style_manager import StyleManager, PageDimensions

logger = get_logger(__name__)


class BuildingPickerDialog(QDialog):
    """Dialog to search and select a building before adding a unit.

    Shows a search field; results appear as a dropdown when typing >= 2 chars.
    Clicking a result item immediately accepts the dialog.
    """

    def __init__(self, db, api_service, groups=None, auth_token=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._api_service = api_service
        self._groups = groups or []
        self._auth_token = auth_token
        self._selected_building = None

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_api_search)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(520)
        self.setMaximumWidth(520)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 45))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("اختر المبنى")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1A1F1D;")
        layout.addWidget(title)

        # Search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث برمز المبنى أو القسيمة ...")
        self.search_input.setLayoutDirection(Qt.RightToLeft)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 9px 12px;
                font-size: 13px;
                color: #212B36;
            }}
            QLineEdit:focus {{ border: 2px solid {Config.PRIMARY_COLOR}; }}
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.search_input)

        map_btn = QPushButton("الخريطة")
        map_btn.setFixedHeight(38)
        map_btn.setFixedWidth(95)
        map_btn.setCursor(Qt.PointingHandCursor)
        map_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Config.PRIMARY_COLOR};
                border: 1px solid {Config.PRIMARY_COLOR};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: #EEF4FF; }}
        """)
        map_btn.clicked.connect(self._on_map_btn_clicked)
        search_row.addWidget(map_btn)

        layout.addLayout(search_row)

        # Status label — shows search state (hidden when empty)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "color: #637381; font-size: 10pt; background: transparent; border: none;"
        )
        layout.addWidget(self.status_label)

        # Results list — hidden initially, appears as dropdown on search
        self.results_list = QListWidget()
        self.results_list.setLayoutDirection(Qt.RightToLeft)
        self.results_list.setFixedHeight(195)
        self.results_list.setVisible(False)
        self.results_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #FAFBFC;
                font-size: 13px;
                color: #212B36;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 14px;
                border-bottom: 1px solid #F0F0F0;
                cursor: pointer;
            }
            QListWidget::item:hover {
                background-color: #EEF4FF;
                color: #1E3A8A;
            }
        """)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.results_list)

        # Cancel button
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #6B7280;
                border: 1px solid #E5E7EB; border-radius: 8px;
                padding: 8px 24px; font-size: 14px;
            }
            QPushButton:hover { background-color: #F9FAFB; }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        main_layout.addWidget(card)

    def _on_search_text_changed(self, text: str):
        self._search_timer.stop()
        if len(text.strip()) < 2:
            self.results_list.clear()
            self.results_list.setVisible(False)
            self.status_label.setText("")
            self.adjustSize()
            return
        self.status_label.setText("جاري البحث ...")
        self._search_timer.start(300)

    def _do_api_search(self):
        text = self.search_input.text().strip()
        if len(text) < 2:
            return
        try:
            response = self._api_service.search_buildings(building_id=text, page_size=20)
            items = []
            if isinstance(response, dict):
                items = response.get("items", []) or response.get("data", []) or []
            elif isinstance(response, list):
                items = response

            from models.building import Building
            buildings = []
            for dto in items:
                b = Building()
                b.building_uuid = dto.get("id") or dto.get("buildingUuid") or ""
                b.building_id = (
                    dto.get("buildingCode") or dto.get("buildingNumber") or
                    dto.get("buildingId") or ""
                )
                b.neighborhood_name_ar = (
                    dto.get("neighborhoodName") or dto.get("neighborhoodNameAr") or ""
                )
                buildings.append(b)

            self._populate_list(buildings)

            if buildings:
                self.results_list.setVisible(True)
                self.status_label.setText(f"{len(buildings)} نتيجة — انقر للاختيار")
            else:
                self.results_list.setVisible(False)
                self.status_label.setText("لا توجد نتائج")
            self.adjustSize()
        except Exception as e:
            logger.warning(f"Building search failed: {e}")
            self.status_label.setText("فشل البحث — تأكد من الاتصال بالخادم")

    def _populate_list(self, buildings):
        self.results_list.clear()
        for b in buildings:
            neighborhood = (b.neighborhood_name_ar or "").strip()
            display = b.building_id or b.building_uuid or ""
            if neighborhood:
                display = f"{display}  —  {neighborhood}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, b)
            self.results_list.addItem(item)

    def _on_item_clicked(self, item):
        """Single click on a result item — select and accept immediately."""
        self._selected_building = item.data(Qt.UserRole)
        self.accept()

    def _on_map_btn_clicked(self):
        try:
            from ui.components.building_map_dialog_v2 import BuildingMapDialog
            dlg = BuildingMapDialog(
                db=self.db,
                auth_token=self._auth_token,
                read_only=False,
                parent=self
            )
            if dlg.exec_() == QDialog.Accepted:
                building = dlg.get_selected_building()
                if building:
                    self._selected_building = building
                    self.accept()
        except Exception as e:
            logger.warning(f"Failed to open map dialog: {e}")

    def get_selected_building(self):
        return self._selected_building


class UnitsPage(QWidget):
    """Property Units management page — grouped by building, API-backed."""

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
        # Flat list of row descriptors: {'type': 'unit', 'group': dict, 'unit': PropertyUnit}
        self._rows = []
        self._total_units = 0
        self._total_buildings = 0

        self._current_page = 1
        self._rows_per_page = 11
        self._total_pages = 1

        # API-side filters (sent as query params)
        self._active_filters = {
            'building_id': None,
            'unit_type': None,
            'unit_status': None,
        }
        self._buildings_cache = {}

        self._setup_ui()

    def _setup_ui(self):
        from ui.design_system import Colors
        from ui.font_utils import create_font, FontManager
        from pathlib import Path
        import sys

        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(15)

        # Header row
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        title = QLabel("الوحدات السكنية")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        top_row.addWidget(title)

        top_row.addStretch()

        add_btn = PrimaryButton("إضافة وحدة جديدة", icon_name="icon")
        add_btn.clicked.connect(self._on_add_unit)
        top_row.addWidget(add_btn)

        layout.addLayout(top_row)

        # Table card
        table_card = QFrame()
        table_card.setFixedHeight(708)
        table_card.setStyleSheet("background-color: white; border-radius: 16px;")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setRowCount(11)
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent
        icon_path = base_path / "assets" / "images" / "down.png"

        # Filterable cols are 2 (unit type) and 3 (unit status)
        headers = ["رقم المقسم", "رمز المبنى", "نوع المقسم", "حالة المقسم", "وصف المقسم", ""]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            if i in (2, 3) and icon_path.exists():
                item.setIcon(QIcon(str(icon_path)))
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

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setFixedHeight(56)
        header.setStretchLastSection(False)
        header.setMouseTracking(True)
        header.sectionEntered.connect(self._on_header_hover)
        header.sectionClicked.connect(self._on_header_clicked)

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 130)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 240)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 140)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(3, 140)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.resizeSection(5, 44)

        v_header = self.table.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(52)

        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_double_click)

        card_layout.addWidget(self.table)

        # Footer (pagination)
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E1E8ED;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)
        footer_frame.setFixedHeight(58)

        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(10, 10, 10, 10)

        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        nav_btn_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #EBEEF2; }
            QPushButton:disabled { color: #C1C7CD; }
        """
        self.prev_btn = QPushButton(">")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet(nav_btn_style)
        self.prev_btn.clicked.connect(self._on_prev_page)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("<")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet(nav_btn_style)
        self.next_btn.clicked.connect(self._on_next_page)
        nav_layout.addWidget(self.next_btn)

        footer.addWidget(nav_container)

        self.page_label = QLabel("0-0 of 0")
        self.page_label.setStyleSheet(
            "color: #637381; font-size: 10pt; font-weight: 400; background: transparent;"
        )
        footer.addWidget(self.page_label)

        from PyQt5.QtGui import QPixmap
        rows_container = QFrame()
        rows_container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QFrame:hover { background-color: #EBEEF2; }
        """)
        rows_container.setCursor(Qt.PointingHandCursor)
        rows_layout = QHBoxLayout(rows_container)
        rows_layout.setContentsMargins(4, 2, 4, 2)
        rows_layout.setSpacing(4)

        down_icon_label = QLabel()
        if icon_path.exists():
            down_pixmap = QPixmap(str(icon_path))
            if not down_pixmap.isNull():
                down_pixmap = down_pixmap.scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                down_icon_label.setPixmap(down_pixmap)
        down_icon_label.setStyleSheet("background: transparent; border: none;")
        rows_layout.addWidget(down_icon_label)

        self.rows_number = QLabel(str(self._rows_per_page))
        self.rows_number.setStyleSheet(
            "color: #637381; font-size: 10pt; font-weight: 400; background: transparent; border: none;"
        )
        rows_layout.addWidget(self.rows_number)

        rows_container.mousePressEvent = lambda e: self._show_page_selection_menu(rows_container)
        footer.addWidget(rows_container)

        rows_label = QLabel("Rows per page:")
        rows_label.setStyleSheet(
            "color: #637381; font-size: 10pt; font-weight: 400; background: transparent;"
        )
        footer.addWidget(rows_label)

        from ui.components.toggle_switch import ToggleSwitch
        self.dense_toggle = ToggleSwitch("Dense", checked=True)
        self.dense_toggle.toggled.connect(self._on_dense_toggle)

        footer.addStretch()
        footer.addWidget(self.dense_toggle)

        card_layout.addWidget(footer_frame)
        layout.addWidget(table_card)

    # ── Data loading ──

    def refresh(self, data=None):
        logger.debug("Refreshing units page")
        self._load_units()

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
        self._set_auth_token()
        try:
            result = self.unit_controller.get_units_grouped(
                building_id=self._active_filters.get('building_id'),
                unit_type=self._active_filters.get('unit_type'),
                status=self._active_filters.get('unit_status'),
            )
            if result.success:
                self._groups = result.data or []
            else:
                logger.warning(f"Failed to load grouped units: {result.message}")
                self._groups = []
        except Exception as e:
            logger.warning(f"API grouped load failed: {e}")
            self._groups = []

        self._total_units = sum(g.get('unitCount', 0) for g in self._groups)
        self._total_buildings = len(self._groups)

        self._rebuild_rows()
        self._current_page = 1
        self._update_table()

    def _rebuild_rows(self):
        self._rows = []
        for group in self._groups:
            building = self._get_building_for_group(group)
            for dto in group.get('propertyUnits', []):
                unit = self._dto_to_unit(dto, group.get('buildingId'))
                self._rows.append({'type': 'unit', 'group': group, 'unit': unit, 'building': building})

    # ── Table rendering ──

    def _update_table(self):
        total_rows = len(self._rows)
        self._total_pages = max(1, (total_rows + self._rows_per_page - 1) // self._rows_per_page)
        self._current_page = min(self._current_page, self._total_pages)

        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + self._rows_per_page, total_rows)
        page_rows = self._rows[start_idx:end_idx]

        # Clear all rows
        self.table.clearSpans()
        for row in range(self.table.rowCount()):
            for col in range(6):
                self.table.setItem(row, col, QTableWidgetItem(""))
            self.table.setCellWidget(row, 5, None)

        if total_rows == 0:
            self.table.setSpan(0, 0, self.table.rowCount(), 6)
            empty_item = QTableWidgetItem("لا توجد وحدات سكنية")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setForeground(QColor("#9CA3AF"))
            self.table.setItem(0, 0, empty_item)
            self.page_label.setText("0-0 of 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        for row_idx, row_data in enumerate(page_rows):
            self._render_unit_row(row_idx, row_data['unit'], row_data['group'], row_data.get('building'))

        self.page_label.setText(f"{start_idx + 1}-{end_idx} of {total_rows}")
        self.rows_number.setText(str(self._rows_per_page))
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

    def _render_unit_row(self, row: int, unit: PropertyUnit, group: dict, building=None):
        self.table.setItem(row, 0, QTableWidgetItem(str(unit.unit_number or "")))

        if building and building.building_id:
            building_code = building.building_id_formatted or building.building_id
        else:
            building_code = group.get('buildingNumber') or group.get('buildingId', '')
        self.table.setItem(row, 1, QTableWidgetItem(building_code))

        self.table.setItem(row, 2, QTableWidgetItem(get_unit_type_display(unit.unit_type)))
        self.table.setItem(row, 3, QTableWidgetItem(get_unit_status_display(unit.apartment_status)))

        desc = unit.property_description or ""
        desc_display = desc[:40] + "..." if len(desc) > 40 else desc
        self.table.setItem(row, 4, QTableWidgetItem(desc_display))

        dots_item = QTableWidgetItem("⋮")
        dots_item.setTextAlignment(Qt.AlignCenter)
        dots_font = QFont()
        dots_font.setPointSize(18)
        dots_font.setWeight(QFont.Bold)
        dots_item.setFont(dots_font)
        dots_item.setForeground(QColor("#637381"))
        self.table.setItem(row, 5, dots_item)

    # ── Pagination ──

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._update_table()

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._update_table()

    def _go_to_page(self, page_num):
        if 1 <= page_num <= self._total_pages:
            self._current_page = page_num
            self._update_table()

    def _show_page_selection_menu(self, parent_widget):
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                color: #637381;
                font-size: 10pt;
            }
            QMenu::item:selected {
                background-color: #E3F2FD;
                color: #3498db;
            }
        """)
        for size in [5, 10, 15, 25]:
            action = menu.addAction(str(size))
            if size == self._rows_per_page:
                action.setEnabled(False)
            else:
                action.triggered.connect(lambda checked, s=size: self._set_rows_per_page(s))
        menu.exec_(parent_widget.mapToGlobal(parent_widget.rect().bottomLeft()))

    def _set_rows_per_page(self, size):
        self._rows_per_page = size
        self.table.setRowCount(size)
        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(76)
        self._current_page = 1
        self._update_table()

    def _on_dense_toggle(self, checked):
        row_height = 52 if checked else 68
        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(row_height)
        if checked:
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    # ── Row interactions ──

    def _on_row_double_click(self, row, col):
        start_idx = (self._current_page - 1) * self._rows_per_page
        row_idx = start_idx + row
        if row_idx >= len(self._rows):
            return
        self.view_unit.emit(self._rows[row_idx]['unit'])

    def _on_cell_clicked(self, row: int, col: int):
        if col != 5:
            return
        start_idx = (self._current_page - 1) * self._rows_per_page
        row_idx = start_idx + row
        if row_idx >= len(self._rows):
            return
        row_data = self._rows[row_idx]
        item = self.table.item(row, 0)
        if not item or not item.text().strip():
            return
        self._show_actions_menu(row, col, row_data['unit'], row_data['group'])

    def _show_actions_menu(self, row: int, col: int, unit: PropertyUnit, group: dict):
        from PyQt5.QtWidgets import QMenu, QAction
        from ui.components.icon import Icon

        rect = self.table.visualItemRect(self.table.item(row, col))
        position = QPoint(rect.right() - 10, rect.bottom())

        menu = QMenu(self)
        menu.setFixedSize(200, 149)

        view_icon = Icon.load_qicon("eye-open", size=18)
        view_action = QAction("  عرض", self)
        if view_icon:
            view_action.setIcon(view_icon)
        view_action.triggered.connect(lambda: self.view_unit.emit(unit))
        menu.addAction(view_action)

        edit_icon = Icon.load_qicon("edit-01", size=18)
        edit_action = QAction("  تعديل", self)
        if edit_icon:
            edit_action.setIcon(edit_icon)
        edit_action.triggered.connect(lambda: self._edit_unit(unit, group))
        menu.addAction(edit_action)

        delete_icon = Icon.load_qicon("delete", size=18)
        delete_action = QAction("  حذف", self)
        if delete_icon:
            delete_action.setIcon(delete_icon)
        delete_action.triggered.connect(lambda: self._delete_unit(unit))
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
        menu.exec_(self.table.viewport().mapToGlobal(position))

    # ── Header filter system ──

    def _on_header_hover(self, logical_index: int):
        header = self.table.horizontalHeader()
        if logical_index in (2, 3):
            header.setCursor(Qt.PointingHandCursor)
        else:
            header.setCursor(Qt.ArrowCursor)

    def _on_header_clicked(self, logical_index: int):
        if logical_index not in (2, 3):
            return
        self._show_filter_menu(logical_index)

    def _show_filter_menu(self, column_index: int):
        filter_key = None
        unique_values = set()

        if column_index == 2:
            filter_key = 'unit_type'
            for code, label in get_unit_type_options():
                if code is not None and code != "":
                    unique_values.add((code, label))
        elif column_index == 3:
            filter_key = 'unit_status'
            for code, label in get_unit_status_options():
                if code is not None and code != "":
                    unique_values.add((code, label))

        if not unique_values:
            return

        from PyQt5.QtWidgets import QMenu, QAction
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

        sorted_values = sorted(unique_values, key=lambda x: str(x[1]))
        current_val = self._active_filters.get(filter_key)
        for code, display in sorted_values:
            action = QAction(display, self)
            action.triggered.connect(lambda checked, c=code: self._apply_filter(filter_key, c))
            if current_val is not None and str(current_val) == str(code):
                action.setCheckable(True)
                action.setChecked(True)
            menu.addAction(action)

        header = self.table.horizontalHeader()
        x_pos = header.sectionViewportPosition(column_index)
        y_pos = header.height()
        pos = self.table.mapToGlobal(QPoint(x_pos, y_pos))
        menu.exec_(pos)

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

    # ── Building helper ──

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

    # ── CRUD operations ──

    def _on_add_unit(self):
        """Open building picker then add unit dialog."""
        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None

        picker = BuildingPickerDialog(
            db=self.db,
            api_service=self._api_service,
            groups=self._groups,
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
            Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
            self._load_units()

    def _on_add_unit_for_building(self, group: dict):
        """Add a unit for a specific building (from header add button)."""
        building = self._get_building_for_group(group)
        if not building:
            Toast.show_toast(self, "لم يتم العثور على المبنى", Toast.ERROR)
            return
        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None
        dialog = WizardUnitDialog(building, self.db, parent=self, auth_token=auth_token)
        if dialog.exec_() == QDialog.Accepted:
            Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
            self._load_units()

    def _edit_unit(self, unit: PropertyUnit, group: dict):
        building = self._get_building_for_group(group)
        if not building:
            Toast.show_toast(self, "لم يتم العثور على المبنى", Toast.ERROR)
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
                Toast.show_toast(self, "تم تحديث الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"API unit update failed: {e}")
                Toast.show_toast(self, f"فشل تحديث الوحدة: {e}", Toast.ERROR)

    def _delete_unit(self, unit: PropertyUnit):
        unit_label = unit.unit_number or unit.unit_uuid or ""
        if ErrorHandler.confirm(
            self,
            f"هل أنت متأكد من حذف الوحدة {unit_label}؟",
            "تأكيد الحذف"
        ):
            self._set_auth_token()
            success = self._api_service.delete_property_unit(unit.unit_uuid)
            if success:
                Toast.show_toast(self, "تم حذف الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            else:
                logger.error(f"Failed to delete unit {unit.unit_uuid}")
                Toast.show_toast(self, "فشل في حذف الوحدة", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        self._update_table()
