# -*- coding: utf-8 -*-
"""
Unit Dialog - Dialog for creating/editing property units.

Allows user to input:
- Unit type and status
- Floor and unit number
- Number of rooms and area
- Property description
"""

from typing import Dict, Any, Optional
import uuid

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QTextEdit, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from app.config import Config
from models.building import Building
from controllers.unit_controller import UnitController
from services.validation_service import ValidationService
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitDialog(QDialog):
    """Dialog for creating or editing a property unit."""

    def __init__(self, building: Building, db, unit_data: Optional[Dict] = None, parent=None):
        """
        Initialize the dialog.

        Args:
            building: The building this unit belongs to
            db: Database instance
            unit_data: Optional existing unit data for editing
            parent: Parent widget
        """
        super().__init__(parent)
        self.building = building
        self.unit_data = unit_data
        self.unit_controller = UnitController(db)
        self.validation_service = ValidationService()

        # إزالة الشريط العلوي (title bar)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)

        # CRITICAL: جعل الخلفية شفافة حتى تظهر فقط الزوايا المنحنية
        self.setAttribute(Qt.WA_TranslucentBackground)

        # الأبعاد حسب Figma: 574×589
        self.setFixedSize(574, 589)

        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
        """)

        self._setup_ui()
        if unit_data:
            self._load_unit_data(unit_data)

    def _setup_ui(self):
        """Setup the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # إنشاء frame أبيض مع زوايا منحنية
        content_frame = QFrame()
        content_frame.setObjectName("ContentFrame")
        content_frame.setStyleSheet("""
            QFrame#ContentFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 24px;
            }
        """)

        layout = QVBoxLayout(content_frame)
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)

        # العنوان (Header)
        header_label = QLabel("إضافة وحدة عقارية" if not self.unit_data else "تعديل وحدة عقارية")
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1A1F1D; background: transparent;")
        layout.addWidget(header_label)

        # Row 1: Unit Type and Unit Status
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # Unit Type
        type_container = QVBoxLayout()
        type_label = QLabel("نوع الوحدة")
        type_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        self.unit_type_combo = QComboBox()
        self.unit_type_combo.setStyleSheet(self._combo_style())
        unit_types = [
            ("", "اختر نوع الوحدة"),
            ("apartment", "شقة"),
            ("shop", "محل تجاري"),
            ("office", "مكتب"),
            ("warehouse", "مستودع"),
            ("garage", "مرآب"),
            ("other", "أخرى")
        ]
        for code, ar in unit_types:
            self.unit_type_combo.addItem(ar, code)
        type_container.addWidget(type_label)
        type_container.addWidget(self.unit_type_combo)
        row1.addLayout(type_container, 1)

        # Unit Status
        status_container = QVBoxLayout()
        status_label = QLabel("حالة الوحدة")
        status_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        self.unit_status_combo = QComboBox()
        self.unit_status_combo.setStyleSheet(self._combo_style())
        unit_statuses = [
            ("", "اختر الحالة"),
            ("intact", "جيدة"),
            ("damaged", "متضررة"),
            ("destroyed", "مدمرة")
        ]
        for code, ar in unit_statuses:
            self.unit_status_combo.addItem(ar, code)
        status_container.addWidget(status_label)
        status_container.addWidget(self.unit_status_combo)
        row1.addLayout(status_container, 1)

        layout.addLayout(row1)

        # Row 2: Floor Number and Unit Number
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # Floor Number - Custom spinbox with stacked arrows
        from ui.style_manager import StyleManager
        from ui.components.icon import Icon

        floor_container = QVBoxLayout()
        floor_label = QLabel("رقم الطابق")
        floor_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")

        # Create custom spinbox frame
        floor_frame = QFrame()
        floor_frame.setStyleSheet(StyleManager.spinbox_input_container())
        floor_frame.setFixedHeight(40)

        floor_layout = QHBoxLayout(floor_frame)
        floor_layout.setContentsMargins(5, 0, 10, 0)
        floor_layout.setSpacing(0)

        # Stacked arrows layout
        floor_arrows_layout = QVBoxLayout()
        floor_arrows_layout.setContentsMargins(0, 0, 0, 0)
        floor_arrows_layout.setSpacing(0)

        # Up arrow button
        self.floor_up_btn = QPushButton()
        self.floor_up_btn.setFixedSize(20, 15)
        self.floor_up_btn.setStyleSheet(StyleManager.spinbox_arrow_button())
        floor_up_pixmap = Icon.load_pixmap("^", size=16)
        if floor_up_pixmap and not floor_up_pixmap.isNull():
            self.floor_up_btn.setIcon(QIcon(floor_up_pixmap))

        # Down arrow button
        self.floor_down_btn = QPushButton()
        self.floor_down_btn.setFixedSize(20, 15)
        self.floor_down_btn.setStyleSheet(StyleManager.spinbox_arrow_button())
        floor_down_pixmap = Icon.load_pixmap("down", size=16)
        if floor_down_pixmap and not floor_down_pixmap.isNull():
            self.floor_down_btn.setIcon(QIcon(floor_down_pixmap))

        floor_arrows_layout.addWidget(self.floor_up_btn)
        floor_arrows_layout.addWidget(self.floor_down_btn)

        # Value input field
        self.floor_input = QLineEdit()
        self.floor_input.setText("0")
        self.floor_input.setAlignment(Qt.AlignCenter)
        self.floor_input.setStyleSheet(StyleManager.spinbox_input_field())

        # Connect button clicks
        self.floor_up_btn.clicked.connect(lambda: self._increment_floor())
        self.floor_down_btn.clicked.connect(lambda: self._decrement_floor())

        floor_layout.addLayout(floor_arrows_layout)
        floor_layout.addStretch()
        floor_layout.addWidget(self.floor_input)
        floor_layout.addStretch()

        floor_container.addWidget(floor_label)
        floor_container.addWidget(floor_frame)
        row2.addLayout(floor_container, 1)

        # Unit Number
        unit_num_container = QVBoxLayout()
        unit_num_label = QLabel("رقم الوحدة")
        unit_num_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        self.unit_number_input = QLineEdit()
        self.unit_number_input.setPlaceholderText("مثال: 101")
        self.unit_number_input.setStyleSheet(self._input_style())
        self.unit_number_input.textChanged.connect(self._check_uniqueness)
        unit_num_container.addWidget(unit_num_label)
        unit_num_container.addWidget(self.unit_number_input)
        row2.addLayout(unit_num_container, 1)

        layout.addLayout(row2)

        # Uniqueness validation label
        self.uniqueness_label = QLabel("")
        self.uniqueness_label.setStyleSheet("font-size: 11px; margin-top: -8px;")
        layout.addWidget(self.uniqueness_label)

        # Row 3: Number of Rooms and Area
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        # Number of Rooms - Custom spinbox with stacked arrows
        rooms_container = QVBoxLayout()
        rooms_label = QLabel("عدد الغرف")
        rooms_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")

        # Create custom spinbox frame
        rooms_frame = QFrame()
        rooms_frame.setStyleSheet(StyleManager.spinbox_input_container())
        rooms_frame.setFixedHeight(40)

        rooms_layout = QHBoxLayout(rooms_frame)
        rooms_layout.setContentsMargins(5, 0, 10, 0)
        rooms_layout.setSpacing(0)

        # Stacked arrows layout
        rooms_arrows_layout = QVBoxLayout()
        rooms_arrows_layout.setContentsMargins(0, 0, 0, 0)
        rooms_arrows_layout.setSpacing(0)

        # Up arrow button
        self.rooms_up_btn = QPushButton()
        self.rooms_up_btn.setFixedSize(20, 15)
        self.rooms_up_btn.setStyleSheet(StyleManager.spinbox_arrow_button())
        rooms_up_pixmap = Icon.load_pixmap("^", size=16)
        if rooms_up_pixmap and not rooms_up_pixmap.isNull():
            self.rooms_up_btn.setIcon(QIcon(rooms_up_pixmap))

        # Down arrow button
        self.rooms_down_btn = QPushButton()
        self.rooms_down_btn.setFixedSize(20, 15)
        self.rooms_down_btn.setStyleSheet(StyleManager.spinbox_arrow_button())
        rooms_down_pixmap = Icon.load_pixmap("down", size=16)
        if rooms_down_pixmap and not rooms_down_pixmap.isNull():
            self.rooms_down_btn.setIcon(QIcon(rooms_down_pixmap))

        rooms_arrows_layout.addWidget(self.rooms_up_btn)
        rooms_arrows_layout.addWidget(self.rooms_down_btn)

        # Value input field
        self.rooms_input = QLineEdit()
        self.rooms_input.setText("0")
        self.rooms_input.setAlignment(Qt.AlignCenter)
        self.rooms_input.setStyleSheet(StyleManager.spinbox_input_field())

        # Connect button clicks
        self.rooms_up_btn.clicked.connect(lambda: self._increment_rooms())
        self.rooms_down_btn.clicked.connect(lambda: self._decrement_rooms())

        rooms_layout.addLayout(rooms_arrows_layout)
        rooms_layout.addStretch()
        rooms_layout.addWidget(self.rooms_input)
        rooms_layout.addStretch()

        rooms_container.addWidget(rooms_label)
        rooms_container.addWidget(rooms_frame)
        row3.addLayout(rooms_container, 1)

        # Area
        area_container = QVBoxLayout()
        area_label = QLabel("مساحة الوحدة (م²)")
        area_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        self.area_input = QLineEdit()
        self.area_input.setPlaceholderText("المساحة التقريبية أو المقاسة")
        self.area_input.setStyleSheet(self._input_style())
        area_container.addWidget(area_label)
        area_container.addWidget(self.area_input)
        row3.addLayout(area_container, 1)

        layout.addLayout(row3)

        # Description
        desc_label = QLabel("وصف العقار")
        desc_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #374151;")
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText(
            "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة."
        )
        self.description_edit.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 12px;
                color: #6B7280;
            }
        """)
        layout.addWidget(desc_label)
        layout.addWidget(self.description_edit)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("حفظ")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
                color: white;
            }}
            QPushButton:hover {{
                background-color: #005A9C;
            }}
            QPushButton:disabled {{
                background-color: #9CA3AF;
            }}
        """)
        self.save_btn.clicked.connect(self._on_save)

        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.save_btn)
        layout.addLayout(buttons_layout)

        # إضافة الـ frame الأبيض للـ layout الرئيسي
        main_layout.addWidget(content_frame)

    def _combo_style(self) -> str:
        """Get combobox stylesheet."""
        return """
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
        """

    def _spinbox_style(self) -> str:
        """Get spinbox stylesheet."""
        return """
            QSpinBox {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
            QSpinBox:focus {
                border-color: #3498db;
            }
        """

    def _input_style(self) -> str:
        """Get input stylesheet."""
        return """
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F9FAFB;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """

    def _increment_floor(self):
        """Increment floor value when up arrow is clicked."""
        try:
            current = int(self.floor_input.text())
            if current < 100:  # Max value
                self.floor_input.setText(str(current + 1))
        except ValueError:
            self.floor_input.setText("0")

    def _decrement_floor(self):
        """Decrement floor value when down arrow is clicked."""
        try:
            current = int(self.floor_input.text())
            if current > -3:  # Min value
                self.floor_input.setText(str(current - 1))
        except ValueError:
            self.floor_input.setText("0")

    def _increment_rooms(self):
        """Increment rooms value when up arrow is clicked."""
        try:
            current = int(self.rooms_input.text())
            if current < 20:  # Max value
                self.rooms_input.setText(str(current + 1))
        except ValueError:
            self.rooms_input.setText("0")

    def _decrement_rooms(self):
        """Decrement rooms value when down arrow is clicked."""
        try:
            current = int(self.rooms_input.text())
            if current > 0:  # Min value
                self.rooms_input.setText(str(current - 1))
        except ValueError:
            self.rooms_input.setText("0")

    def _check_uniqueness(self):
        """Check if unit number is unique within the building."""
        unit_number = self.unit_number_input.text().strip()
        try:
            floor = int(self.floor_input.text())
        except ValueError:
            floor = 0

        if not unit_number:
            self.uniqueness_label.setText("")
            self.save_btn.setEnabled(True)
            return

        # Check existing units
        try:
            result = self.unit_controller.get_units_for_building(self.building.building_uuid)
            is_unique = True

            if not result.success:
                logger.error(f"Failed to check unit uniqueness: {result.message}")
                self.uniqueness_label.setText("⚠️ خطأ في التحقق من التفرد")
                self.uniqueness_label.setStyleSheet("color: #e67e22; font-size: 11px;")
                return

            existing_units = result.data
            for unit in existing_units:
                # Skip if editing the same unit
                if self.unit_data and hasattr(unit, 'unit_id') and unit.unit_id == self.unit_data.get('unit_id'):
                    continue

                # Check for duplicate
                if (hasattr(unit, 'apartment_number') and unit.apartment_number == unit_number and
                    hasattr(unit, 'floor_number') and unit.floor_number == floor):
                    is_unique = False
                    break
                elif (hasattr(unit, 'unit_number') and unit.unit_number == unit_number and
                      hasattr(unit, 'floor_number') and unit.floor_number == floor):
                    is_unique = False
                    break

            if is_unique:
                self.uniqueness_label.setText("✅ رقم الوحدة متاح")
                self.uniqueness_label.setStyleSheet("color: #27ae60; font-size: 11px;")
                self.save_btn.setEnabled(True)
            else:
                self.uniqueness_label.setText("❌ يوجد وحدة بنفس الرقم والطابق")
                self.uniqueness_label.setStyleSheet("color: #e74c3c; font-size: 11px;")
                self.save_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"Error checking uniqueness: {e}", exc_info=True)
            self.uniqueness_label.setText("")
            self.save_btn.setEnabled(True)

    def _validate(self) -> bool:
        """Validate form data."""
        # Unit type is required
        if not self.unit_type_combo.currentData():
            QMessageBox.warning(self, "تحذير", "يرجى اختيار نوع الوحدة")
            return False

        # Unit number is required
        if not self.unit_number_input.text().strip():
            QMessageBox.warning(self, "تحذير", "يرجى إدخال رقم الوحدة")
            return False

        # Area should be numeric if provided
        area_text = self.area_input.text().strip()
        if area_text:
            try:
                float(area_text)
            except ValueError:
                QMessageBox.warning(self, "تحذير", "المساحة يجب أن تكون رقماً")
                return False

        return True

    def _on_save(self):
        """Handle save button click."""
        if self._validate():
            self.accept()

    def _load_unit_data(self, unit_data: Dict):
        """Load existing unit data into form."""
        # Unit type
        unit_type = unit_data.get('unit_type')
        if unit_type:
            idx = self.unit_type_combo.findData(unit_type)
            if idx >= 0:
                self.unit_type_combo.setCurrentIndex(idx)

        # Unit status
        status = unit_data.get('apartment_status')
        if status:
            idx = self.unit_status_combo.findData(status)
            if idx >= 0:
                self.unit_status_combo.setCurrentIndex(idx)

        # Floor number
        if 'floor_number' in unit_data and unit_data['floor_number'] is not None:
            self.floor_input.setText(str(unit_data['floor_number']))

        # Unit number
        unit_num = unit_data.get('unit_number') or unit_data.get('apartment_number')
        if unit_num:
            self.unit_number_input.setText(str(unit_num))

        # Number of rooms
        if 'number_of_rooms' in unit_data:
            self.rooms_input.setText(str(unit_data['number_of_rooms'] or 0))

        # Area
        if 'area_sqm' in unit_data and unit_data['area_sqm']:
            self.area_input.setText(str(unit_data['area_sqm']))

        # Description
        if 'property_description' in unit_data and unit_data['property_description']:
            self.description_edit.setPlainText(unit_data['property_description'])

    def get_unit_data(self) -> Dict[str, Any]:
        """Get unit data from form."""
        # Parse area
        area_value = None
        area_text = self.area_input.text().strip()
        if area_text:
            try:
                area_value = float(area_text)
            except ValueError:
                pass

        # Parse floor and rooms values
        try:
            floor_value = int(self.floor_input.text())
        except ValueError:
            floor_value = 0

        try:
            rooms_value = int(self.rooms_input.text())
        except ValueError:
            rooms_value = 0

        unit_data = {
            'unit_uuid': self.unit_data.get('unit_uuid') if self.unit_data else str(uuid.uuid4()),
            'building_id': self.building.building_id,
            'building_uuid': self.building.building_uuid,
            'unit_type': self.unit_type_combo.currentData(),
            'apartment_status': self.unit_status_combo.currentData() or 'intact',
            'floor_number': floor_value,
            'unit_number': self.unit_number_input.text().strip(),
            'apartment_number': self.unit_number_input.text().strip(),  # Compatibility
            'number_of_rooms': rooms_value,
            'area_sqm': area_value,
            'property_description': self.description_edit.toPlainText().strip() or None
        }

        return unit_data
