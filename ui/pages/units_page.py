# -*- coding: utf-8 -*-
"""
Property Units list page with filters and CRUD operations.
Implements UC-002: Property Unit Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QTextEdit,
    QAbstractItemView, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QCursor

from app.config import Config, Vocabularies
from repositories.database import Database
from repositories.unit_repository import UnitRepository
from repositories.building_repository import BuildingRepository
from models.unit import PropertyUnit
from services.api_client import get_api_client
from ui.components.toast import Toast
from ui.components.primary_button import PrimaryButton
from ui.error_handler import ErrorHandler
from utils.i18n import I18n
from utils.logger import get_logger
from ui.style_manager import StyleManager, PageDimensions

logger = get_logger(__name__)


class UnitDialog(QDialog):
    """Dialog for creating/editing a property unit - modern card-based style."""

    def __init__(self, db: Database, i18n: I18n, unit: PropertyUnit = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.unit = unit
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self._is_edit_mode = unit is not None

        # Remove title bar for modern look
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)

        # Make background transparent for rounded corners
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Fixed size matching the design from step 2
        self.setFixedSize(560, 580)

        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
        """)

        self._setup_ui()

        if unit:
            self._populate_data()
        else:
            # Auto-suggest first unit number for selected building
            self._on_building_changed()

    def _create_field_widget(self, label_text: str, widget, placeholder: str = None) -> QWidget:
        """Create a field container with label above the input."""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Label
        label = QLabel(label_text)
        label.setStyleSheet("color: #6B7280; font-size: 13px; font-weight: 500; border: none; background: transparent;")
        label.setAlignment(Qt.AlignRight)
        layout.addWidget(label)

        # Style the widget
        if isinstance(widget, QComboBox):
            widget.setStyleSheet(f"""
                QComboBox {{
                    background-color: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 10px 12px;
                    font-size: 14px;
                    min-height: 20px;
                }}
                QComboBox:focus {{
                    border: 2px solid {Config.PRIMARY_COLOR};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 30px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid #6B7280;
                    margin-right: 10px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: white;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    selection-background-color: #EBF5FF;
                }}
            """)
            if placeholder:
                widget.setPlaceholderText(placeholder)
        elif isinstance(widget, QSpinBox):
            # Style spinbox with stacked up/down buttons on left side like in step 2 photo
            widget.setStyleSheet(f"""
                QSpinBox {{
                    background-color: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 8px 12px 8px 32px;
                    font-size: 14px;
                    min-height: 24px;
                }}
                QSpinBox:focus {{
                    border: 1px solid {Config.PRIMARY_COLOR};
                }}
                QSpinBox::up-button {{
                    subcontrol-origin: border;
                    subcontrol-position: center left;
                    width: 24px;
                    height: 12px;
                    border: none;
                    border-right: 1px solid #E5E7EB;
                    border-top-left-radius: 7px;
                    background: transparent;
                    margin-bottom: 0px;
                }}
                QSpinBox::up-button:hover {{
                    background: #F3F4F6;
                }}
                QSpinBox::up-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-bottom: 5px solid #9CA3AF;
                    width: 0;
                    height: 0;
                }}
                QSpinBox::down-button {{
                    subcontrol-origin: border;
                    subcontrol-position: center left;
                    width: 24px;
                    height: 12px;
                    border: none;
                    border-right: 1px solid #E5E7EB;
                    border-bottom-left-radius: 7px;
                    background: transparent;
                    margin-top: 12px;
                }}
                QSpinBox::down-button:hover {{
                    background: #F3F4F6;
                }}
                QSpinBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #9CA3AF;
                    width: 0;
                    height: 0;
                }}
            """)
        elif isinstance(widget, QLineEdit):
            widget.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 10px 12px;
                    font-size: 14px;
                    min-height: 20px;
                }}
                QLineEdit:focus {{
                    border: 2px solid {Config.PRIMARY_COLOR};
                }}
            """)
            if placeholder:
                widget.setPlaceholderText(placeholder)
        elif isinstance(widget, QTextEdit):
            widget.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #FFFFFF;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 10px 12px;
                    font-size: 14px;
                }}
                QTextEdit:focus {{
                    border: 2px solid {Config.PRIMARY_COLOR};
                }}
            """)
            if placeholder:
                widget.setPlaceholderText(placeholder)

        layout.addWidget(widget)
        return container

    def _setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Card container with white background and rounded corners
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        # Add shadow to card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(20)

        # Title header - right aligned like in photo
        title_label = QLabel("أضف معلومات المقسم" if not self._is_edit_mode else "تعديل معلومات المقسم")
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #1F2937;
            background: transparent;
            border: none;
            padding: 0px;
        """)
        title_label.setAlignment(Qt.AlignRight)
        card_layout.addWidget(title_label)

        # Form content
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(16)

        # Row 1: حالة الوحدة (Status - left) | نوع الوحدة (Type - right) - RTL order
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # Unit Type (right side visually in RTL - added first)
        self.type_combo = QComboBox()
        self.type_combo.addItem("اختر", "")
        for code, en, ar in Vocabularies.UNIT_TYPES:
            self.type_combo.addItem(ar, code)
        row1.addWidget(self._create_field_widget("نوع الوحدة", self.type_combo, "اختر"))

        # Status (left side visually in RTL - added second)
        self.status_combo = QComboBox()
        self.status_combo.addItem("اختر", "")
        statuses = [("occupied", "مشغول"), ("vacant", "شاغر"), ("unknown", "غير معروف")]
        for code, ar in statuses:
            self.status_combo.addItem(ar, code)
        row1.addWidget(self._create_field_widget("حالة الوحدة", self.status_combo, "اختر"))

        form_layout.addLayout(row1)

        # Row 2: رقم الوحدة (Unit Number - left) | رقم الطابق (Floor - right) - RTL order
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # Floor number (right side visually in RTL - added first)
        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 50)
        self.floor_spin.setValue(0)
        self.floor_spin.setAlignment(Qt.AlignCenter)
        row2.addWidget(self._create_field_widget("رقم الطابق", self.floor_spin))

        # Unit number (left side visually in RTL - added second)
        self.unit_number_input = QSpinBox()
        self.unit_number_input.setRange(0, 999)
        self.unit_number_input.setValue(0)
        self.unit_number_input.setAlignment(Qt.AlignCenter)
        row2.addWidget(self._create_field_widget("رقم الوحدة", self.unit_number_input))

        form_layout.addLayout(row2)

        # Error label for unit number (hidden by default)
        self.unit_number_error = QLabel("")
        self.unit_number_error.setStyleSheet("color: #DC2626; font-size: 11px;")
        self.unit_number_error.setVisible(False)
        self.unit_number_error.setAlignment(Qt.AlignRight)
        form_layout.addWidget(self.unit_number_error)

        # Row 3: مساحة الوحدة (Area - left) | عدد الغرف (Rooms - right) - RTL order
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        # Rooms count (right side visually in RTL - added first)
        self.apt_number = QSpinBox()
        self.apt_number.setRange(0, 20)
        self.apt_number.setValue(0)
        self.apt_number.setAlignment(Qt.AlignCenter)
        row3.addWidget(self._create_field_widget("عدد الغرف", self.apt_number))

        # Area (left side visually in RTL - added second)
        self.area_input = QLineEdit()
        self.area_input.setAlignment(Qt.AlignRight)
        self.area_input.setPlaceholderText("المساحة التقريبية أو المقاسة (م²)")
        row3.addWidget(self._create_field_widget("مساحة الوحدة", self.area_input))

        form_layout.addLayout(row3)

        # Row 4: وصف العقار (Description) - full width
        self.description = QTextEdit()
        self.description.setFixedHeight(80)
        desc_widget = self._create_field_widget("وصف العقار", self.description,
            "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة")
        form_layout.addWidget(desc_widget)

        card_layout.addWidget(form_container)

        # Building combo
        self.building_combo = QComboBox()
        buildings = self.building_repo.get_all(limit=500)
        for b in buildings:
            display = f"{b.building_id} - {b.neighborhood_name_ar}"
            self.building_combo.addItem(display, b.building_id)
        self.building_combo.currentIndexChanged.connect(self._on_building_changed)
        card_layout.addWidget(self.building_combo)

        # Hint label
        self.unit_number_hint = QLabel("")
        self.unit_number_hint.setStyleSheet("color: #6B7280; font-size: 12px; margin-top: 4px;")
        card_layout.addWidget(self.unit_number_hint)

        # Spacer
        card_layout.addStretch()

        # Buttons row - حفظ (Save - blue, left) | إلغاء (Cancel - outline, right)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # Save button (primary - blue) - appears on LEFT in RTL
        save_btn = QPushButton("حفظ")
        save_btn.setFixedHeight(45)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        # Cancel button (secondary - outline) - appears on RIGHT in RTL
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setFixedHeight(45)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #6B7280;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #D1D5DB;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

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

        # Unit number (now a QSpinBox)
        if self.unit.unit_number:
            try:
                self.unit_number_input.setValue(int(self.unit.unit_number))
            except (ValueError, TypeError):
                self.unit_number_input.setValue(0)

        # Unit type
        idx = self.type_combo.findData(self.unit.unit_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.floor_spin.setValue(self.unit.floor_number)

        # Apartment number / rooms count (QSpinBox)
        if self.unit.apartment_number:
            try:
                self.apt_number.setValue(int(self.unit.apartment_number))
            except (ValueError, TypeError):
                self.apt_number.setValue(0)

        idx = self.status_combo.findData(self.unit.apartment_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        # Area (now a QLineEdit)
        if self.unit.area_sqm:
            self.area_input.setText(str(int(self.unit.area_sqm)))

        self.description.setPlainText(self.unit.property_description or "")

    def _on_building_changed(self):
        """Handle building selection change - auto-suggest next unit number."""
        if self._is_edit_mode:
            return  # Don't auto-suggest in edit mode

        building_id = self.building_combo.currentData()
        if building_id:
            next_number = self.unit_repo.get_next_unit_number(building_id)
            try:
                self.unit_number_input.setValue(int(next_number))
            except (ValueError, TypeError):
                self.unit_number_input.setValue(1)
            self.unit_number_hint.setText(f"رقم الوحدة التالي المتاح: {next_number}")

    def _validate_unit_number(self):
        """Validate unit number format and uniqueness."""
        num = self.unit_number_input.value()

        # Check range (1-999)
        if num < 1 or num > 999:
            self._show_unit_number_error("يجب أن يكون الرقم بين 001 و 999")
            return False

        # Check uniqueness
        building_id = self.building_combo.currentData()
        padded_number = str(num).zfill(3)
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
        self.unit_number_input.setStyleSheet("""
            QSpinBox {
                background-color: #FEF2F2;
                border: 2px solid #DC2626;
                border-radius: 8px;
                padding: 8px 12px 8px 32px;
                font-size: 14px;
                min-height: 24px;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 24px;
                height: 12px;
                border: none;
                border-right: 1px solid #DC2626;
                border-top-left-radius: 7px;
                background: transparent;
            }
            QSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #DC2626;
                width: 0;
                height: 0;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 24px;
                height: 12px;
                border: none;
                border-right: 1px solid #DC2626;
                border-bottom-left-radius: 7px;
                background: transparent;
                margin-top: 12px;
            }
            QSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #DC2626;
                width: 0;
                height: 0;
            }
        """)

    def _hide_unit_number_error(self):
        """Hide unit number validation error."""
        self.unit_number_error.setVisible(False)
        self.unit_number_input.setStyleSheet(f"""
            QSpinBox {{
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 12px 8px 32px;
                font-size: 14px;
                min-height: 24px;
            }}
            QSpinBox:focus {{
                border: 1px solid {Config.PRIMARY_COLOR};
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 24px;
                height: 12px;
                border: none;
                border-right: 1px solid #E5E7EB;
                border-top-left-radius: 7px;
                background: transparent;
            }}
            QSpinBox::up-button:hover {{
                background: #F3F4F6;
            }}
            QSpinBox::up-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #9CA3AF;
                width: 0;
                height: 0;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 24px;
                height: 12px;
                border: none;
                border-right: 1px solid #E5E7EB;
                border-bottom-left-radius: 7px;
                background: transparent;
                margin-top: 12px;
            }}
            QSpinBox::down-button:hover {{
                background: #F3F4F6;
            }}
            QSpinBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9CA3AF;
                width: 0;
                height: 0;
            }}
        """)

    def _get_padded_unit_number(self) -> str:
        """Get unit number padded to 3 digits."""
        num = self.unit_number_input.value()
        if num > 0:
            return str(num).zfill(3)
        return "001"

    def accept(self):
        """Override accept to validate before closing."""
        if not self._validate_unit_number():
            ErrorHandler.show_warning(
                self,
                "الرجاء تصحيح رقم الوحدة قبل الحفظ",
                "خطأ في البيانات"
            )
            return
        super().accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        unit_number = self._get_padded_unit_number()
        building_id = self.building_combo.currentData()
        # Generate unit_id from building_id + unit_number
        unit_id = f"{building_id}-{unit_number}"

        # Parse area from text input
        area_text = self.area_input.text().strip()
        area_sqm = None
        if area_text:
            try:
                area_sqm = float(area_text)
            except ValueError:
                area_sqm = None

        return {
            "building_id": building_id,
            "unit_number": unit_number,
            "unit_id": unit_id,
            "unit_type": self.type_combo.currentData() or None,
            "floor_number": self.floor_spin.value(),
            "apartment_number": str(self.apt_number.value()) if self.apt_number.value() > 0 else "",
            "apartment_status": self.status_combo.currentData() or None,
            "area_sqm": area_sqm,
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

        # API service for fetching units
        self._api_service = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

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

        # Mapping for unit type to Arabic
        type_ar_map = {
            "apartment": "شقة",
            "shop": "محل تجاري",
            "office": "مكتب",
            "warehouse": "مستودع",
            "other": "أخرى",
        }

        # Mapping for status to Arabic
        status_ar_map = {
            "occupied": "مشغول",
            "vacant": "شاغر",
            "damaged": "متضرر",
            "under_renovation": "قيد التجديد",
            "uninhabitable": "غير صالح للسكن",
            "locked": "مغلق",
            "unknown": "غير معروف",
        }

        # Populate table
        for row, unit in enumerate(page_units):
            # Unit ID
            self.table.setItem(row, 0, QTableWidgetItem(unit.unit_id or ""))

            # Building ID (truncated)
            building_id = unit.building_id or ""
            building_id_display = building_id[:20] + "..." if len(building_id) > 20 else building_id
            self.table.setItem(row, 1, QTableWidgetItem(building_id_display))

            # Type - map to Arabic
            unit_type = unit.unit_type or "other"
            type_display = type_ar_map.get(unit_type.lower(), unit_type)
            self.table.setItem(row, 2, QTableWidgetItem(type_display))

            # Floor
            self.table.setItem(row, 3, QTableWidgetItem(str(unit.floor_number or 0)))

            # Apartment number (shows number of rooms from API)
            self.table.setItem(row, 4, QTableWidgetItem(unit.apartment_number or "-"))

            # Status - map to Arabic
            status = unit.apartment_status or "unknown"
            status_display = status_ar_map.get(status.lower(), status)
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

            try:
                if self._use_api:
                    # Create via API: POST /api/v1/PropertyUnits
                    logger.info("Creating unit via API")

                    # Set auth token if available
                    main_window = self.window()
                    if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
                        self._api_service.set_access_token(main_window._api_token)

                    # Prepare API data format
                    api_data = {
                        "buildingId": data.get("building_id", ""),
                        "unitIdentifier": data.get("unit_number", ""),
                        "floorNumber": data.get("floor_number", 0),
                        "unitType": self._get_unit_type_code(data.get("unit_type")),
                        "status": self._get_status_code(data.get("apartment_status")),
                        "areaSquareMeters": data.get("area_sqm") or 0,
                        "numberOfRooms": int(data.get("apartment_number") or 0) if data.get("apartment_number") else 0,
                        "description": data.get("property_description", "")
                    }

                    try:
                        response = self._api_service.create_property_unit(api_data)
                        Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
                        self._load_units()
                    except Exception as api_error:
                        error_msg = str(api_error)
                        logger.error(f"Failed to create unit via API: {error_msg}")
                        Toast.show_toast(self, f"فشل في إضافة الوحدة: {error_msg}", Toast.ERROR)
                else:
                    # Create via local repository
                    unit = PropertyUnit(**data)
                    self.unit_repo.create(unit)
                    Toast.show_toast(self, "تم إضافة الوحدة بنجاح", Toast.SUCCESS)
                    self._load_units()
            except Exception as e:
                logger.error(f"Failed to create unit: {e}")
                Toast.show_toast(self, f"فشل في إضافة الوحدة: {str(e)}", Toast.ERROR)

    def _get_unit_type_code(self, unit_type: str) -> int:
        """Convert unit type string to API code."""
        type_map = {
            "apartment": 0,
            "shop": 1,
            "office": 2,
            "warehouse": 3,
            "other": 4,
        }
        if unit_type:
            return type_map.get(unit_type.lower(), 0)
        return 0

    def _get_status_code(self, status: str) -> int:
        """Convert status string to API code."""
        status_map = {
            "occupied": 0,
            "vacant": 1,
            "damaged": 2,
            "under_renovation": 3,
            "uninhabitable": 4,
            "locked": 5,
            "unknown": 6,
        }
        if status:
            return status_map.get(status.lower(), 0)
        return 0

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
        # Reload headers and data
        self._update_table()
