# -*- coding: utf-8 -*-
"""
Property Units list page with filters and CRUD operations.
Implements UC-002: Property Unit Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QDialog,
    QAbstractItemView, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QIcon, QCursor, QFont

from app.config import Config
from repositories.database import Database
from repositories.unit_repository import UnitRepository
from repositories.building_repository import BuildingRepository
from models.unit import PropertyUnit
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


class BuildingSelectDialog(QDialog):
    """Simple dialog to select a building before adding a unit."""

    def __init__(self, building_repo, parent=None):
        super().__init__(parent)
        self.building_repo = building_repo
        self._selected_building = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedSize(420, 200)

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
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("اختر المبنى")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1A1F1D;")
        layout.addWidget(title)

        self.building_combo = QComboBox()
        self.building_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #F8FAFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                min-height: 20px;
            }}
            QComboBox:focus {{ border: 2px solid {Config.PRIMARY_COLOR}; }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #6B7280;
                margin-right: 10px;
            }}
        """)
        buildings = self.building_repo.get_all(limit=500)
        self._buildings = buildings
        for b in buildings:
            name = b.neighborhood_name_ar or b.neighborhood_name or ""
            display = f"{b.building_id} - {name}".strip(" -")
            self.building_combo.addItem(display, b.building_id)
        layout.addWidget(self.building_combo)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

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
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("تأكيد")
        ok_btn.setFixedHeight(40)
        ok_btn.setCursor(Qt.PointingHandCursor)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR}; color: white;
                border: none; border-radius: 8px;
                padding: 8px 24px; font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {Config.PRIMARY_DARK}; }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)
        main_layout.addWidget(card)

    def get_selected_building(self):
        building_id = self.building_combo.currentData()
        if not building_id:
            return None
        for b in self._buildings:
            if b.building_id == building_id:
                return b
        return None


class UnitsPage(QWidget):
    """Property Units management page — 6-column table matching Figma design."""

    view_unit = pyqtSignal(object)
    edit_unit_signal = pyqtSignal(object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.building_repo = BuildingRepository(db)

        self._api_service = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

        self._all_units = []
        self._units = []
        self._current_page = 1
        self._rows_per_page = 11
        self._total_pages = 1

        self._active_filters = {
            'neighborhood': None,
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

        # ── Header row ──
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

        # ── Table card ──
        table_card = QFrame()
        table_card.setFixedHeight(708)
        table_card.setStyleSheet("background-color: white; border-radius: 16px;")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(0)

        # Table
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

        # Icon for filterable columns
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent
        icon_path = base_path / "assets" / "images" / "down.png"

        headers = ["رقم المقسم", "المنطقة", "نوع المقسم", "حالة المقسم", "وصف المقسم", ""]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            if i in (1, 2, 3) and icon_path.exists():
                item.setIcon(QIcon(str(icon_path)))
            self.table.setHorizontalHeaderItem(i, item)

        # Styling (DRY — same as buildings page)
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
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setFixedHeight(56)
        header.setStretchLastSection(True)
        header.setMouseTracking(True)
        header.sectionEntered.connect(self._on_header_hover)
        header.sectionClicked.connect(self._on_header_clicked)

        # Column widths
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 298)   # رقم المقسم
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 206)   # المنطقة
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 220)   # نوع المقسم
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(3, 195)   # حالة المقسم
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.resizeSection(4, 195)   # وصف المقسم
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # ⋮

        # Row heights
        v_header = self.table.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(52)

        # Events
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_double_click)

        card_layout.addWidget(self.table)

        # ── Footer ──
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

        # Navigation arrows
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

        # Page counter
        self.page_label = QLabel("0-0 of 0")
        self.page_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent;")
        footer.addWidget(self.page_label)

        # Rows per page selector
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
        self.rows_number.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent; border: none;")
        rows_layout.addWidget(self.rows_number)

        rows_container.mousePressEvent = lambda e: self._show_page_selection_menu(rows_container)
        footer.addWidget(rows_container)

        rows_label = QLabel("Rows per page:")
        rows_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent;")
        footer.addWidget(rows_label)

        from ui.components.toggle_switch import ToggleSwitch
        self.dense_toggle = ToggleSwitch("Dense", checked=True)
        self.dense_toggle.toggled.connect(self._on_dense_toggle)

        footer.addStretch()
        footer.addWidget(self.dense_toggle)

        card_layout.addWidget(footer_frame)
        layout.addWidget(table_card)

    def refresh(self, data=None):
        """Refresh the units list."""
        logger.debug("Refreshing units page")
        self._load_units()

    def _load_units(self):
        """Load all units from API or local repository."""
        # Set auth token if available
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
            self._api_service.set_access_token(main_window._api_token)

        if self._use_api:
            # Load from API: GET /api/v1/PropertyUnits
            logger.info("Loading units from API")
            raw_units = self._api_service.get_all_property_units(limit=1000)
            # Convert API dicts to PropertyUnit objects
            units = []
            for dto in raw_units:
                if isinstance(dto, dict):
                    units.append(PropertyUnit(
                        unit_uuid=dto.get("id") or dto.get("unitUuid") or "",
                        unit_id=dto.get("unitId") or "",
                        building_id=dto.get("buildingId") or "",
                        unit_type=dto.get("unitType") or "apartment",
                        unit_number=dto.get("unitIdentifier") or dto.get("unitNumber") or "001",
                        floor_number=dto.get("floorNumber") or 0,
                        apartment_number=dto.get("apartmentNumber") or dto.get("unitIdentifier") or "",
                        apartment_status=dto.get("status") or dto.get("apartmentStatus") or "occupied",
                        property_description=dto.get("description") or dto.get("propertyDescription") or "",
                        area_sqm=dto.get("areaSquareMeters") or dto.get("areaSqm"),
                    ))
                else:
                    units.append(dto)
        else:
            # Load from local database
            logger.info("Loading units from local database")
            units = self.unit_repo.get_all(limit=1000)

        self._all_units = units

        self._buildings_cache = {}
        all_buildings = self.building_repo.get_all(limit=5000)
        for b in all_buildings:
            self._buildings_cache[b.building_id] = b
            if b.building_uuid:
                self._buildings_cache[b.building_uuid] = b

        self._units = self._apply_filters(units)
        self._current_page = 1
        self._update_table()

    def _update_table(self):
        total = len(self._units)
        self._total_pages = max(1, (total + self._rows_per_page - 1) // self._rows_per_page)
        self._current_page = min(self._current_page, self._total_pages)

        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + self._rows_per_page, total)
        page_units = self._units[start_idx:end_idx]

        # Clear spans and cells
        self.table.clearSpans()
        for row in range(self._rows_per_page):
            for col in range(6):
                self.table.setItem(row, col, QTableWidgetItem(""))

        if total == 0:
            self.table.setSpan(0, 0, self._rows_per_page, 6)
            empty_item = QTableWidgetItem("لا توجد بيانات مطابقة للفلتر المحدد")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setForeground(QColor("#9CA3AF"))
            self.table.setItem(0, 0, empty_item)
            self.page_label.setText("0-0 of 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        # Populate rows
        for row, unit in enumerate(page_units):
            # col 0: رقم المقسم
            try:
                num = str(int(unit.unit_number))
            except (ValueError, TypeError):
                num = unit.unit_number or ""
            self.table.setItem(row, 0, QTableWidgetItem(num))

            # col 1: المنطقة (neighborhood from building)
            area = self._get_unit_area(unit)
            self.table.setItem(row, 1, QTableWidgetItem(area))

            # col 2: نوع المقسم
            self.table.setItem(row, 2, QTableWidgetItem(get_unit_type_display(unit.unit_type)))

            # col 3: حالة المقسم
            self.table.setItem(row, 3, QTableWidgetItem(get_unit_status_display(unit.apartment_status)))

            # col 4: وصف المقسم (truncated)
            desc = unit.property_description or ""
            desc_display = desc[:40] + "..." if len(desc) > 40 else desc
            self.table.setItem(row, 4, QTableWidgetItem(desc_display))

            # col 5: ⋮ (3-dot menu)
            dots_item = QTableWidgetItem("⋮")
            dots_item.setTextAlignment(Qt.AlignCenter)
            dots_font = QFont()
            dots_font.setPointSize(18)
            dots_font.setWeight(QFont.Bold)
            dots_item.setFont(dots_font)
            dots_item.setForeground(QColor("#637381"))
            self.table.setItem(row, 5, dots_item)

        # Update pagination
        if total > 0:
            self.page_label.setText(f"{start_idx + 1}-{end_idx} of {total}")
        else:
            self.page_label.setText("0-0 of 0")
        self.rows_number.setText(str(self._rows_per_page))
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

    def _get_unit_area(self, unit) -> str:
        if not unit.building_id:
            return ""
        building = self._buildings_cache.get(unit.building_id)
        if building:
            return (building.neighborhood_name_ar or building.neighborhood_name or "").strip()
        return ""

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
        """Go to specific page."""
        if 1 <= page_num <= self._total_pages:
            self._current_page = page_num
            self._load_units()

    def _show_page_selection_menu(self, parent_widget):
        """Show dropdown menu to select rows per page."""
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
        """Change rows per page and reload."""
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
        """Handle double-click to view unit details."""
        start_idx = (self._current_page - 1) * self._rows_per_page
        unit_idx = start_idx + row
        if unit_idx < len(self._units):
            self.view_unit.emit(self._units[unit_idx])

    def _on_cell_clicked(self, row: int, col: int):
        """Open action menu when 3-dot column is clicked."""
        if col != 5:
            return
        item = self.table.item(row, 0)
        if not item or not item.text().strip():
            return
        start_idx = (self._current_page - 1) * self._rows_per_page
        unit_idx = start_idx + row
        if unit_idx >= len(self._units):
            return
        self._show_actions_menu(row, col, self._units[unit_idx])

    def _show_actions_menu(self, row: int, col: int, unit: PropertyUnit):
        """Show 3-dot action menu below the cell (same pattern as buildings page)."""
        from PyQt5.QtWidgets import QMenu, QAction
        from ui.components.icon import Icon

        rect = self.table.visualItemRect(self.table.item(row, col))
        position = QPoint(rect.right() - 10, rect.bottom())

        menu = QMenu(self)
        menu.setFixedSize(200, 149)

        # عرض
        view_icon = Icon.load_qicon("eye-open", size=18)
        view_action = QAction("  عرض", self)
        if view_icon:
            view_action.setIcon(view_icon)
        view_action.triggered.connect(lambda: self.view_unit.emit(unit))
        menu.addAction(view_action)

        # تعديل
        edit_icon = Icon.load_qicon("edit-01", size=18)
        edit_action = QAction("  تعديل", self)
        if edit_icon:
            edit_action.setIcon(edit_icon)
        edit_action.triggered.connect(lambda: self._edit_unit(unit))
        menu.addAction(edit_action)

        # حذف
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
        """Pointer cursor on filterable columns only."""
        header = self.table.horizontalHeader()
        if logical_index in (1, 2, 3):
            header.setCursor(Qt.PointingHandCursor)
        else:
            header.setCursor(Qt.ArrowCursor)

    def _on_header_clicked(self, logical_index: int):
        if logical_index not in (1, 2, 3):
            return
        self._show_filter_menu(logical_index)

    def _show_filter_menu(self, column_index: int):
        """Show filter dropdown for the clicked column header."""
        unique_values = set()
        filter_key = None

        if column_index == 1:
            filter_key = 'neighborhood'
            seen = set()
            for b in self._buildings_cache.values():
                if id(b) in seen:
                    continue
                seen.add(id(b))
                area = (b.neighborhood_name_ar or b.neighborhood_name or "").strip()
                if area:
                    unique_values.add((area, area))
        elif column_index == 2:
            filter_key = 'unit_type'
            for code, label in get_unit_type_options():
                if code:
                    unique_values.add((code, label))
        elif column_index == 3:
            filter_key = 'unit_status'
            for code, label in get_unit_status_options():
                if code:
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

        # "عرض الكل" (clear filter)
        clear_action = QAction("عرض الكل", self)
        clear_action.triggered.connect(lambda: self._apply_filter(filter_key, None))
        menu.addAction(clear_action)
        menu.addSeparator()

        sorted_values = sorted(unique_values, key=lambda x: x[1])
        for code, display in sorted_values:
            action = QAction(display, self)
            action.triggered.connect(lambda checked, c=code: self._apply_filter(filter_key, c))
            if self._active_filters.get(filter_key) == code:
                action.setCheckable(True)
                action.setChecked(True)
            menu.addAction(action)

        header = self.table.horizontalHeader()
        x_pos = header.sectionViewportPosition(column_index)
        y_pos = header.height()
        pos = self.table.mapToGlobal(QPoint(x_pos, y_pos))
        menu.exec_(pos)

    def _apply_filter(self, filter_key: str, filter_value):
        """Apply filter and reload table."""
        self._active_filters[filter_key] = filter_value
        self._current_page = 1
        self._units = self._apply_filters(self._all_units)
        self._update_table()

    def _apply_filters(self, units: list) -> list:
        filtered = units

        if self._active_filters.get('neighborhood'):
            target = self._active_filters['neighborhood']
            filtered = [u for u in filtered if self._get_unit_area(u) == target]

        if self._active_filters.get('unit_type'):
            target = self._active_filters['unit_type']
            filtered = [u for u in filtered if self._match_code(u.unit_type, target)]

        if self._active_filters.get('unit_status'):
            target = self._active_filters['unit_status']
            filtered = [u for u in filtered if self._match_code(u.apartment_status, target)]

        return filtered

    @staticmethod
    def _match_code(value, target):
        if value is None:
            return False
        try:
            return int(value) == int(target)
        except (ValueError, TypeError):
            return str(value).strip().lower() == str(target).strip().lower()

    # ── CRUD operations ──

    def _on_add_unit(self):
        select_dlg = BuildingSelectDialog(self.building_repo, parent=self)
        if select_dlg.exec_() != QDialog.Accepted:
            return
        building = select_dlg.get_selected_building()
        if not building:
            return

        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None

        dialog = WizardUnitDialog(building, self.db, parent=self, auth_token=auth_token)
        if dialog.exec_() == QDialog.Accepted:
            Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
            self._load_units()

    def _edit_unit(self, unit: PropertyUnit):
        # Use buildings cache (dual-indexed by ID and UUID) to avoid mismatch
        building = self._buildings_cache.get(unit.building_id)
        if not building:
            building = self.building_repo.get_by_id(unit.building_id)
        if not building:
            Toast.show_toast(self, "لم يتم العثور على المبنى", Toast.ERROR)
            return

        unit_data = unit.to_dict()
        main_window = self.window()
        auth_token = getattr(main_window, '_api_token', None) if main_window else None

        dialog = WizardUnitDialog(building, self.db, unit_data=unit_data, parent=self, auth_token=auth_token)
        if dialog.exec_() == QDialog.Accepted:
            Toast.show_toast(self, "تم تحديث الوحدة بنجاح", Toast.SUCCESS)
            self._load_units()

    def _delete_unit(self, unit: PropertyUnit):
        """Delete unit with confirmation."""
        if ErrorHandler.confirm(
            self,
            f"هل أنت متأكد من حذف الوحدة {unit.unit_id}؟",
            "تأكيد الحذف"
        ):
            try:
                self.unit_repo.delete(unit.unit_uuid)
                Toast.show_toast(self, "تم حذف الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"Failed to delete unit: {e}")
                Toast.show_toast(self, f"فشل في حذف الوحدة: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update language."""
        self._update_table()
