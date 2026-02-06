# -*- coding: utf-8 -*-
"""
Property Units list page with filters and CRUD operations.
Implements UC-002: Property Unit Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QTextEdit,
    QAbstractItemView, QGraphicsDropShadowEffect, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QCursor

from app.config import Config, Vocabularies
from repositories.database import Database
from repositories.unit_repository import UnitRepository
from repositories.building_repository import BuildingRepository
from models.unit import PropertyUnit
from ui.components.toast import Toast
from ui.components.primary_button import PrimaryButton
from utils.i18n import I18n
from utils.logger import get_logger
from ui.style_manager import StyleManager, PageDimensions

logger = get_logger(__name__)


class UnitDialog(QDialog):
    """Dialog for creating/editing a property unit."""

    def __init__(self, db: Database, i18n: I18n, unit: PropertyUnit = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit = unit
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self._is_edit_mode = unit is not None

        self.setWindowTitle(i18n.t("edit_unit") if unit else i18n.t("add_unit"))
        self.setMinimumWidth(500)
        self._setup_ui()

        if unit:
            self._populate_data()
        else:
            # Auto-suggest first unit number for selected building
            self._on_building_changed()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        # Building selection
        self.building_combo = QComboBox()
        buildings = self.building_repo.get_all(limit=500)
        for b in buildings:
            display = f"{b.building_id} - {b.neighborhood_name_ar}"
            self.building_combo.addItem(display, b.building_id)
        self.building_combo.currentIndexChanged.connect(self._on_building_changed)
        form.addRow(self.i18n.t("building") + ":", self.building_combo)

        # Unit number (3-digit suffix)
        unit_number_container = QWidget()
        unit_number_layout = QVBoxLayout(unit_number_container)
        unit_number_layout.setContentsMargins(0, 0, 0, 0)
        unit_number_layout.setSpacing(4)

        self.unit_number_input = QLineEdit()
        self.unit_number_input.setPlaceholderText("001")
        self.unit_number_input.setMaxLength(3)
        self.unit_number_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
            }}
        """)
        self.unit_number_input.textChanged.connect(self._validate_unit_number)
        unit_number_layout.addWidget(self.unit_number_input)

        self.unit_number_hint = QLabel("رقم الوحدة: 3 أرقام (001-999)")
        self.unit_number_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 11px;")
        unit_number_layout.addWidget(self.unit_number_hint)

        self.unit_number_error = QLabel("")
        self.unit_number_error.setStyleSheet("color: #DC2626; font-size: 11px;")
        self.unit_number_error.setVisible(False)
        unit_number_layout.addWidget(self.unit_number_error)

        form.addRow("رقم الوحدة:", unit_number_container)

        # Unit type
        self.type_combo = QComboBox()
        for code, en, ar in Vocabularies.UNIT_TYPES:
            self.type_combo.addItem(ar, code)
        form.addRow(self.i18n.t("unit_type") + ":", self.type_combo)

        # Floor number
        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 50)
        self.floor_spin.setValue(0)
        form.addRow(self.i18n.t("floor") + ":", self.floor_spin)

        # Apartment number
        self.apt_number = QLineEdit()
        self.apt_number.setPlaceholderText("مثال: 101")
        form.addRow(self.i18n.t("apartment_number") + ":", self.apt_number)

        # Status
        self.status_combo = QComboBox()
        statuses = [("occupied", "مشغول"), ("vacant", "شاغر"), ("unknown", "غير معروف")]
        for code, ar in statuses:
            self.status_combo.addItem(ar, code)
        form.addRow(self.i18n.t("status") + ":", self.status_combo)

        # Area
        self.area_spin = QSpinBox()
        self.area_spin.setRange(0, 10000)
        self.area_spin.setSuffix(" م²")
        form.addRow(self.i18n.t("area") + ":", self.area_spin)

        # Description
        self.description = QTextEdit()
        self.description.setMaximumHeight(80)
        self.description.setPlaceholderText("وصف الوحدة...")
        form.addRow(self.i18n.t("description") + ":", self.description)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate_data(self):
        """Populate form with existing unit data."""
        if not self.unit:
            return

        # Find and select building (block signal to avoid auto-suggest overwriting)
        self.building_combo.blockSignals(True)
        idx = self.building_combo.findData(self.unit.building_id)
        if idx >= 0:
            self.building_combo.setCurrentIndex(idx)
        self.building_combo.blockSignals(False)

        # Unit number
        self.unit_number_input.setText(self.unit.unit_number or "001")

        # Unit type
        idx = self.type_combo.findData(self.unit.unit_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.floor_spin.setValue(self.unit.floor_number)
        self.apt_number.setText(self.unit.apartment_number)

        idx = self.status_combo.findData(self.unit.apartment_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        if self.unit.area_sqm:
            self.area_spin.setValue(int(self.unit.area_sqm))

        self.description.setPlainText(self.unit.property_description or "")

    def _on_building_changed(self):
        """Handle building selection change - auto-suggest next unit number."""
        if self._is_edit_mode:
            return  # Don't auto-suggest in edit mode

        building_id = self.building_combo.currentData()
        if building_id:
            next_number = self.unit_repo.get_next_unit_number(building_id)
            self.unit_number_input.setText(next_number)
            self.unit_number_hint.setText(f"رقم الوحدة التالي المتاح: {next_number}")

    def _validate_unit_number(self):
        """Validate unit number format and uniqueness."""
        text = self.unit_number_input.text().strip()

        # Check if empty
        if not text:
            self._show_unit_number_error("رقم الوحدة مطلوب")
            return False

        # Check if numeric
        if not text.isdigit():
            self._show_unit_number_error("يجب أن يكون رقم الوحدة أرقاماً فقط")
            return False

        # Check range (001-999)
        num = int(text)
        if num < 1 or num > 999:
            self._show_unit_number_error("يجب أن يكون الرقم بين 001 و 999")
            return False

        # Check uniqueness
        building_id = self.building_combo.currentData()
        padded_number = text.zfill(3)
        exclude_uuid = self.unit.unit_uuid if self.unit else None

        if self.unit_repo.unit_number_exists(building_id, padded_number, exclude_uuid):
            self._show_unit_number_error("رقم الوحدة موجود مسبقاً في هذا المبنى")
            return False

        # Valid
        self._hide_unit_number_error()
        return True

    def _show_unit_number_error(self, message: str):
        """Show unit number validation error."""
        self.unit_number_error.setText(message)
        self.unit_number_error.setVisible(True)
        self.unit_number_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #FEF2F2;
                border: 2px solid #DC2626;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
        """)

    def _hide_unit_number_error(self):
        """Hide unit number validation error."""
        self.unit_number_error.setVisible(False)
        self.unit_number_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
            }}
        """)

    def _get_padded_unit_number(self) -> str:
        """Get unit number padded to 3 digits."""
        text = self.unit_number_input.text().strip()
        if text.isdigit():
            return text.zfill(3)
        return "001"

    def accept(self):
        """Override accept to validate before closing."""
        if not self._validate_unit_number():
            QMessageBox.warning(
                self,
                "خطأ في البيانات",
                "الرجاء تصحيح رقم الوحدة قبل الحفظ"
            )
            return
        super().accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        unit_number = self._get_padded_unit_number()
        building_id = self.building_combo.currentData()
        # Generate unit_id from building_id + unit_number
        unit_id = f"{building_id}-{unit_number}"

        return {
            "building_id": building_id,
            "unit_number": unit_number,
            "unit_id": unit_id,
            "unit_type": self.type_combo.currentData(),
            "floor_number": self.floor_spin.value(),
            "apartment_number": self.apt_number.text().strip(),
            "apartment_status": self.status_combo.currentData(),
            "area_sqm": float(self.area_spin.value()) if self.area_spin.value() > 0 else None,
            "property_description": self.description.toPlainText().strip(),
        }


class UnitsPage(QWidget):
    """Property Units management page with card-based table layout matching buildings page."""

    view_unit = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit_repo = UnitRepository(db)
        self.building_repo = BuildingRepository(db)

        # Pagination
        self._all_units = []
        self._units = []
        self._current_page = 1
        self._page_size = 11  # Fixed 11 rows like buildings page

        self._setup_ui()

    def _setup_ui(self):
        # Background color from StyleManager
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        # Apply unified padding from PageDimensions
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 32px
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            PageDimensions.CONTENT_PADDING_V_BOTTOM  # Bottom: 0px
        )
        layout.setSpacing(15)  # 15px gap between header and table card

        # Header row - Title on left, buttons on right
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # Title
        title = QLabel("الوحدات العقارية")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #333;")
        top_row.addWidget(title)

        top_row.addStretch()

        # Add unit button - using PrimaryButton component like buildings page
        add_btn = PrimaryButton("إضافة وحدة جديدة", icon_name="icon")
        add_btn.clicked.connect(self._on_add_unit)
        top_row.addWidget(add_btn)

        layout.addLayout(top_row)

        # Table card
        table_card = QFrame()
        table_card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
            }
        """)

        table_shadow = QGraphicsDropShadowEffect()
        table_shadow.setBlurRadius(10)
        table_shadow.setColor(QColor(0, 0, 0, 15))
        table_shadow.setOffset(0, 2)
        table_card.setGraphicsEffect(table_shadow)

        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setRowCount(11)  # Fixed 11 rows
        self.table.setLayoutDirection(Qt.RightToLeft)

        # Get down.png icon path
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        icon_path = base_path / "assets" / "images" / "down.png"

        # Set headers
        headers = ["رقم الوحدة", "رقم المبنى", "النوع", "الطابق", "رقم الشقة", "الحالة", ""]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            # Add icon to filterable columns (2, 5)
            if i in [2, 5] and icon_path.exists():
                icon = QIcon(str(icon_path))
                item.setIcon(icon)
            self.table.setHorizontalHeaderItem(i, item)

        # Disable scroll bars
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Table styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: none;
                gridline-color: #F1F5F9;
            }
            QTableWidget::item {
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }
            QTableWidget::item:selected {
                background-color: #EBF5FF;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                color: #6B7280;
                font-weight: 600;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid #E1E8ED;
            }
        """)

        # Configure header
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Unit ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Building ID
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Floor
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Apt Number
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(6, QHeaderView.Fixed)  # Actions
        header.resizeSection(6, 50)  # Fixed width for actions column

        # Set row height
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(50)

        # Selection behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Double click to edit
        self.table.cellDoubleClicked.connect(self._on_row_double_click)

        card_layout.addWidget(self.table)

        # Footer with pagination
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

        # Previous button
        self.prev_btn = QPushButton(">")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #6B7280;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
            }
            QPushButton:disabled {
                color: #D1D5DB;
                border-color: #F3F4F6;
            }
        """)
        self.prev_btn.clicked.connect(self._on_prev_page)
        nav_layout.addWidget(self.prev_btn)

        # Next button
        self.next_btn = QPushButton("<")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #6B7280;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
            }
            QPushButton:disabled {
                color: #D1D5DB;
                border-color: #F3F4F6;
            }
        """)
        self.next_btn.clicked.connect(self._on_next_page)
        nav_layout.addWidget(self.next_btn)

        footer.addWidget(nav_container)

        # Page info label
        self.page_label = QLabel("صفحة 1 من 1")
        self.page_label.setStyleSheet("color: #6B7280; background: transparent;")
        footer.addWidget(self.page_label)

        footer.addStretch()

        # Results count
        self.count_label = QLabel("0 وحدة")
        self.count_label.setStyleSheet("color: #6B7280; background: transparent;")
        footer.addWidget(self.count_label)

        card_layout.addWidget(footer_frame)

        layout.addWidget(table_card)

    def refresh(self, data=None):
        """Refresh the units list."""
        logger.debug("Refreshing units page")
        self._load_units()

    def _load_units(self):
        """Load all units without filters."""
        units = self.unit_repo.get_all(limit=1000)

        self._all_units = units
        self._units = units
        self._current_page = 1
        self._update_table()

    def _update_table(self):
        """Update table with current page of units."""
        # Calculate pagination
        total_units = len(self._units)
        total_pages = max(1, (total_units + self._page_size - 1) // self._page_size)
        self._current_page = min(self._current_page, total_pages)

        start_idx = (self._current_page - 1) * self._page_size
        end_idx = min(start_idx + self._page_size, total_units)
        page_units = self._units[start_idx:end_idx]

        # Clear table
        for row in range(self._page_size):
            for col in range(7):
                self.table.setItem(row, col, QTableWidgetItem(""))

        # Populate table
        for row, unit in enumerate(page_units):
            # Unit ID
            self.table.setItem(row, 0, QTableWidgetItem(unit.unit_id))

            # Building ID (truncated)
            building_id_display = unit.building_id[:20] + "..." if len(unit.building_id) > 20 else unit.building_id
            self.table.setItem(row, 1, QTableWidgetItem(building_id_display))

            # Type
            type_display = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else unit.unit_type
            self.table.setItem(row, 2, QTableWidgetItem(type_display))

            # Floor
            self.table.setItem(row, 3, QTableWidgetItem(str(unit.floor_number)))

            # Apartment number
            self.table.setItem(row, 4, QTableWidgetItem(unit.apartment_number or "-"))

            # Status
            status_display = unit.status_display if hasattr(unit, 'status_display') else unit.apartment_status
            self.table.setItem(row, 5, QTableWidgetItem(status_display))

            # Actions button
            action_btn = QPushButton("⋮")
            action_btn.setFixedSize(30, 30)
            action_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #6B7280;
                    font-size: 18px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #F3F4F6;
                    border-radius: 4px;
                }
            """)
            action_btn.setCursor(Qt.PointingHandCursor)
            action_btn.clicked.connect(lambda checked, u=unit: self._show_unit_menu(u))
            self.table.setCellWidget(row, 6, action_btn)

        # Update pagination controls
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < total_pages)
        self.page_label.setText(f"صفحة {self._current_page} من {total_pages}")
        self.count_label.setText(f"{total_units} وحدة")

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._update_table()

    def _on_next_page(self):
        total_pages = max(1, (len(self._units) + self._page_size - 1) // self._page_size)
        if self._current_page < total_pages:
            self._current_page += 1
            self._update_table()

    def _on_row_double_click(self, row, col):
        """Handle double-click to edit unit."""
        start_idx = (self._current_page - 1) * self._page_size
        unit_idx = start_idx + row
        if unit_idx < len(self._units):
            unit = self._units[unit_idx]
            self._edit_unit(unit)

    def _show_unit_menu(self, unit: PropertyUnit):
        """Show context menu for unit actions."""
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F3F4F6;
            }
        """)

        edit_action = menu.addAction("تعديل")
        edit_action.triggered.connect(lambda: self._edit_unit(unit))

        delete_action = menu.addAction("حذف")
        delete_action.triggered.connect(lambda: self._delete_unit(unit))

        menu.exec_(QCursor.pos())

    def _on_add_unit(self):
        """Add new unit."""
        dialog = UnitDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            unit = PropertyUnit(**data)

            try:
                self.unit_repo.create(unit)
                Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"Failed to create unit: {e}")
                Toast.show_toast(self, f"فشل في إضافة الوحدة: {str(e)}", Toast.ERROR)

    def _edit_unit(self, unit: PropertyUnit):
        """Edit existing unit."""
        dialog = UnitDialog(self.db, self.i18n, unit=unit, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(unit, key, value)

            try:
                self.unit_repo.update(unit)
                Toast.show_toast(self, "تم تحديث الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"Failed to update unit: {e}")
                Toast.show_toast(self, f"فشل في تحديث الوحدة: {str(e)}", Toast.ERROR)

    def _delete_unit(self, unit: PropertyUnit):
        """Delete unit with confirmation."""
        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الوحدة {unit.unit_id}؟",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.unit_repo.delete(unit.unit_uuid)
                Toast.show_toast(self, "تم حذف الوحدة بنجاح", Toast.SUCCESS)
                self._load_units()
            except Exception as e:
                logger.error(f"Failed to delete unit: {e}")
                Toast.show_toast(self, f"فشل في حذف الوحدة: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update language."""
        # Reload headers and data
        self._update_table()
