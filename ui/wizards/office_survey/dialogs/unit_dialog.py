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
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QDoubleValidator

from app.config import Config, Vocabularies
from models.building import Building
from controllers.unit_controller import UnitController
from services.validation_service import ValidationService
from services.api_client import get_api_client
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitDialog(QDialog):
    """Dialog for creating or editing a property unit."""

    def __init__(self, building: Building, db, unit_data: Optional[Dict] = None, parent=None, auth_token: Optional[str] = None, survey_id: Optional[str] = None):
        """
        Initialize the dialog.

        Args:
            building: The building this unit belongs to
            db: Database instance
            unit_data: Optional existing unit data for editing
            parent: Parent widget
            auth_token: Optional JWT token for API calls
            survey_id: Survey UUID for creating units under a survey
        """
        super().__init__(parent)
        self.building = building
        self.unit_data = unit_data
        self._survey_id = survey_id
        self.unit_controller = UnitController(db)
        self.validation_service = ValidationService()

        # Initialize API client for creating units
        self._api_service = get_api_client()
        if auth_token:
            self._api_service.set_access_token(auth_token)
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

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
        layout.setSpacing(0)  # نضبط المسافات يدوياً
        layout.setContentsMargins(24, 16, 24, 16)  # تخفيف البادينغ العلوي والسفلي

        # العنوان (Header) - RTL ياخذ يمين تلقائياً
        header_label = QLabel("أضف معلومات الوحدة العقارية" if not self.unit_data else "تعديل معلومات الوحدة العقارية")
        header_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #1A1F1D; background: transparent;")
        layout.addWidget(header_label)

        # مسافة بين العنوان والحقول الأولى: 32 (ضعف المسافة)
        layout.addSpacing(32)

        # Row 1: Unit Type and Unit Status
        row1 = QHBoxLayout()
        row1.setSpacing(16)  # مسافات متساوية بين الحقول

        # Unit Type - Using API integer codes from Vocabularies
        # API: 1=Apartment, 2=Shop, 3=Office, 4=Warehouse, 5=Other
        self.unit_type_combo = QComboBox()
        self.unit_type_combo.setStyleSheet(self._combo_style())
        self.unit_type_combo.addItem("اختر", 0)  # Default selection
        for code, name_en, name_ar in Vocabularies.UNIT_TYPES:
            self.unit_type_combo.addItem(name_ar, code)
        row1.addLayout(self._create_field_container("نوع الوحدة", self.unit_type_combo), 1)

        # Unit Status - Using API integer codes from Vocabularies
        # API: 1=Occupied, 2=Vacant, 3=Damaged, 4=UnderRenovation, 5=Uninhabitable, 6=Locked, 99=Unknown
        self.unit_status_combo = QComboBox()
        self.unit_status_combo.setStyleSheet(self._combo_style())
        self.unit_status_combo.addItem("اختر", 0)  # Default selection
        for code, name_en, name_ar in Vocabularies.UNIT_STATUS:
            self.unit_status_combo.addItem(name_ar, code)
        row1.addLayout(self._create_field_container("حالة الوحدة", self.unit_status_combo), 1)

        layout.addLayout(row1)

        # مسافة بين الصفوف: 16
        layout.addSpacing(16)

        # Row 2: Floor Number and Unit Number
        row2 = QHBoxLayout()
        row2.setSpacing(16)  # مسافات متساوية بين الحقول

        # Floor Number with custom arrows
        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 100)
        self.floor_spin.setValue(0)
        self.floor_spin.setAlignment(Qt.AlignRight)
        self.floor_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.floor_spin.setButtonSymbols(QSpinBox.NoButtons)
        floor_widget = self._create_spinbox_with_arrows(self.floor_spin)
        row2.addLayout(self._create_field_container("رقم الطابق", floor_widget), 1)

        # Unit Number with custom arrows
        self.unit_number_spin = QSpinBox()
        self.unit_number_spin.setRange(0, 9999)
        self.unit_number_spin.setValue(0)
        self.unit_number_spin.setAlignment(Qt.AlignRight)
        self.unit_number_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.unit_number_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.unit_number_spin.valueChanged.connect(self._check_uniqueness)
        unit_widget = self._create_spinbox_with_arrows(self.unit_number_spin)
        row2.addLayout(self._create_field_container("رقم الوحدة", unit_widget), 1)

        layout.addLayout(row2)

        # Uniqueness validation label
        self.uniqueness_label = QLabel("")
        self.uniqueness_label.setStyleSheet("font-size: 11px; margin-top: -8px;")
        layout.addWidget(self.uniqueness_label)

        # مسافة بين الصفوف: 16
        layout.addSpacing(16)

        # Row 3: Number of Rooms and Area
        row3 = QHBoxLayout()
        row3.setSpacing(16)  # مسافات متساوية بين الحقول

        # Number of Rooms with custom arrows
        self.rooms_spin = QSpinBox()
        self.rooms_spin.setRange(0, 20)
        self.rooms_spin.setValue(0)
        self.rooms_spin.setAlignment(Qt.AlignRight)
        self.rooms_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.rooms_spin.setButtonSymbols(QSpinBox.NoButtons)
        rooms_widget = self._create_spinbox_with_arrows(self.rooms_spin)
        row3.addLayout(self._create_field_container("عدد الغرف", rooms_widget), 1)

        # Area - with numeric validator and inline error
        self.area_input = QLineEdit()
        self.area_input.setPlaceholderText("المساحة التقريبية أو المقاسة (م²)")
        self.area_input.setStyleSheet(self._input_style())

        # Allow only numbers (with decimal point)
        area_validator = QDoubleValidator(0.0, 999999.99, 2, self.area_input)
        area_validator.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        area_validator.setNotation(QDoubleValidator.StandardNotation)
        self.area_input.setValidator(area_validator)

        # Inline error label
        self.area_error_label = QLabel("")
        self.area_error_label.setStyleSheet("color: #e74c3c; font-size: 11px; background: transparent;")
        self.area_error_label.setVisible(False)
        self.area_input.textChanged.connect(self._validate_area_input)

        row3.addLayout(self._create_field_container_with_validation("مساحة الوحدة", self.area_input, self.area_error_label), 1)

        layout.addLayout(row3)

        # مسافة بين الصفوف: 16
        layout.addSpacing(16)

        # Description - DRY
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(131)
        self.description_edit.setMaximumHeight(131)
        self.description_edit.setPlaceholderText(
            "وصف تفصيلي يشمل: عدد الغرف وأنواعها، المساحة التقريبية، الاتجاهات والحدود، وأي ميزات مميزة."
        )
        self.description_edit.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 12px;
                color: #6B7280;
            }
            QTextEdit:focus {
                border-color: #3890DF;
                border-width: 2px;
            }
        """)
        layout.addLayout(self._create_field_container("وصف العقار", self.description_edit))

        # مسافة قبل الأزرار: 40
        layout.addSpacing(40)

        # Buttons - DRY with helper method
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)

        # إنشاء الأزرار بترتيب معكوس بسبب RTL
        self.save_btn = self._create_save_button()
        cancel_btn = self._create_cancel_button()

        # إضافة الأزرار (الترتيب سيعكس تلقائياً مع RTL)
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        # إضافة الـ frame الأبيض للـ layout الرئيسي
        main_layout.addWidget(content_frame)

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """Create a spinbox widget with text arrows on the side."""
        # Container frame
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
            }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Arrow column (left side)
        arrow_container = QFrame()
        arrow_container.setStyleSheet("QFrame { border: none; background: transparent; }")
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(5, 2, 5, 2)
        arrow_layout.setSpacing(-5)

        # Up arrow
        up_label = QLabel("^")
        up_label.setStyleSheet("""
            QLabel {
                color: #9CA3AF;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                background: #E1E8ED;
                border-radius: 3px;
            }
        """)
        up_label.setFixedSize(24, 18)
        up_label.setAlignment(Qt.AlignCenter)
        up_label.setCursor(Qt.PointingHandCursor)
        up_label.mousePressEvent = lambda e: spinbox.stepUp()
        arrow_layout.addWidget(up_label)

        # Down arrow
        down_label = QLabel("v")
        down_label.setStyleSheet("""
            QLabel {
                color: #9CA3AF;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                background: #E1E8ED;
                border-radius: 3px;
            }
        """)
        down_label.setFixedSize(24, 18)
        down_label.setAlignment(Qt.AlignCenter)
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda e: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        layout.addWidget(arrow_container)

        # Spinbox (no border since container has border)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                border: none;
                background: transparent;
                font-size: 14px;
                min-height: 40px;
                max-height: 40px;
            }
        """)
        layout.addWidget(spinbox, 1)

        return container

    def _create_field_container(self, label_text: str, widget) -> QVBoxLayout:
        """
        Create a field container with label and widget.

        DRY: Single method for all field containers.

        Args:
            label_text: Text for the label
            widget: The input widget (QComboBox, QLineEdit, etc.)

        Returns:
            QVBoxLayout with label and widget
        """
        container = QVBoxLayout()
        container.setSpacing(4)  # مسافة شبه معدومة بين label والحقل

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 14px; font-weight: 600; color: #374151;")

        container.addWidget(label)
        container.addWidget(widget)

        return container

    def _create_field_container_with_validation(self, label_text: str, widget, validation_label: QLabel) -> QVBoxLayout:
        """
        Create a field container with label, widget, and validation message.

        DRY: Single method for field containers that need validation feedback.

        Args:
            label_text: Text for the label
            widget: The input widget
            validation_label: QLabel for validation messages

        Returns:
            QVBoxLayout with label, widget, and validation label
        """
        container = QVBoxLayout()
        container.setSpacing(4)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 14px; font-weight: 600; color: #374151;")

        container.addWidget(label)
        container.addWidget(widget)
        container.addWidget(validation_label)

        return container

    def _create_save_button(self) -> QPushButton:
        """
        Create save button with consistent styling.

        DRY: Single method for save button creation.

        Returns:
            QPushButton configured as save button
        """
        btn = QPushButton("حفظ")
        btn.setFixedSize(264, 44)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                color: white;
                box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
            }
            QPushButton:hover {
                background-color: #2A7BC9;
            }
            QPushButton:pressed {
                background-color: #1E6BB8;
            }
            QPushButton:disabled {
                background-color: #9CA3AF;
            }
        """)
        btn.clicked.connect(self._on_save)
        return btn

    def _create_cancel_button(self) -> QPushButton:
        """
        Create cancel button with consistent styling.

        DRY: Single method for cancel button creation.

        Returns:
            QPushButton configured as cancel button
        """
        btn = QPushButton("إلغاء")
        btn.setFixedSize(264, 44)
        btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #A9B2BC;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                color: #374151;
                box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
            }
            QPushButton:hover {
                background-color: #F8FAFF;
            }
            QPushButton:pressed {
                background-color: #E8ECEF;
            }
        """)
        btn.clicked.connect(self.reject)
        return btn

    def _combo_style(self) -> str:
        """Get combobox stylesheet with custom dropdown arrow."""
        return """
            QComboBox {
                padding: 6px 40px 6px 12px;
                padding-right: 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 14px;
                font-weight: 600;
                color: #9CA3AF;
                min-height: 40px;
                max-height: 40px;
            }
            QComboBox:focus {
                border-color: #3890DF;
                border-width: 2px;
            }
            QComboBox::drop-down {
                subcontrol-origin: border;
                subcontrol-position: center left;
                width: 35px;
                border: none;
                margin-left: 5px;
            }
            QComboBox::down-arrow {
                image: url(assets/images/v.png);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                font-size: 14px;
            }
        """


    def _input_style(self) -> str:
        """Get input stylesheet with consistent dimensions."""
        return """
            QLineEdit {
                padding: 6px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 13px;
                min-height: 40px;
                max-height: 40px;
            }
            QLineEdit:focus {
                border-color: #3890DF;
                border-width: 2px;
            }
        """

    def _input_error_style(self) -> str:
        """Get input stylesheet for error state (red border)."""
        return """
            QLineEdit {
                padding: 6px 12px;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                background-color: #FFF5F5;
                font-size: 13px;
                min-height: 40px;
                max-height: 40px;
            }
            QLineEdit:focus {
                border-color: #e74c3c;
                border-width: 2px;
            }
        """

    def _show_styled_message(self, title: str, message: str, is_error: bool = False):
        """Show a styled message box with white background (avoids transparent parent issue)."""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Critical if is_error else QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #FFFFFF;
            }
            QMessageBox QLabel {
                color: #374151;
                font-size: 13px;
                min-width: 250px;
            }
            QMessageBox QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #2A7BC9;
            }
        """)
        msg.exec_()

    def _validate_area_input(self, text: str):
        """Real-time validation for area field - numbers only."""
        if not text.strip():
            # Empty is OK (field is optional)
            self.area_error_label.setVisible(False)
            self.area_input.setStyleSheet(self._input_style())
            return

        try:
            float(text.strip())
            self.area_error_label.setVisible(False)
            self.area_input.setStyleSheet(self._input_style())
        except ValueError:
            self.area_error_label.setText("المساحة يجب أن تكون أرقام فقط")
            self.area_error_label.setVisible(True)
            self.area_input.setStyleSheet(self._input_error_style())

    def _check_uniqueness(self):
        """Check if unit number is unique within the building."""
        unit_number = str(self.unit_number_spin.value())
        floor = self.floor_spin.value()

        if self.unit_number_spin.value() == 0:
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
            self._show_styled_message("تحذير", "يرجى اختيار نوع الوحدة")
            return False

        # Unit number is required
        if self.unit_number_spin.value() == 0:
            self._show_styled_message("تحذير", "يرجى إدخال رقم الوحدة")
            return False

        # Area should be numeric if provided
        area_text = self.area_input.text().strip()
        if area_text:
            try:
                float(area_text)
                self.area_error_label.setVisible(False)
                self.area_input.setStyleSheet(self._input_style())
            except ValueError:
                self.area_error_label.setText("المساحة يجب أن تكون أرقام فقط")
                self.area_error_label.setVisible(True)
                self.area_input.setStyleSheet(self._input_error_style())
                self.area_input.setFocus()
                return False

        return True

    def _on_save(self):
        """Handle save button click."""
        if not self._validate():
            return

        # If using API and creating new unit, call API first
        if self._use_api and not self.unit_data:
            unit_data = self.get_unit_data()
            if self._survey_id:
                unit_data['survey_id'] = self._survey_id
            logger.info(f"Creating property unit via API: {unit_data}")

            try:
                response = self._api_service.create_property_unit(unit_data)
                logger.info("Property unit created successfully via API")
                self._created_unit_data = response
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to create unit via API: {error_msg}")
                self._show_styled_message("خطأ", f"فشل في إنشاء الوحدة:\n{error_msg}", is_error=True)
                return

        self.accept()

    def _load_unit_data(self, unit_data: Dict):
        """Load existing unit data into form."""
        # Unit type - handle both integer codes and string values
        unit_type = unit_data.get('unit_type')
        if unit_type is not None:
            # If it's a string, try to find matching integer code
            if isinstance(unit_type, str):
                type_map = {"apartment": 1, "shop": 2, "office": 3, "warehouse": 4, "other": 5}
                unit_type = type_map.get(unit_type.lower(), 0)
            idx = self.unit_type_combo.findData(unit_type)
            if idx >= 0:
                self.unit_type_combo.setCurrentIndex(idx)

        # Unit status - handle both integer codes and string values
        status = unit_data.get('apartment_status') or unit_data.get('status')
        if status is not None:
            # If it's a string, try to find matching integer code
            if isinstance(status, str):
                status_map = {
                    "occupied": 1, "vacant": 2, "damaged": 3,
                    "underrenovation": 4, "uninhabitable": 5, "locked": 6, "unknown": 99,
                    "intact": 1, "destroyed": 3  # Legacy mappings
                }
                status = status_map.get(status.lower().replace("_", ""), 0)
            idx = self.unit_status_combo.findData(status)
            if idx >= 0:
                self.unit_status_combo.setCurrentIndex(idx)

        # Floor number
        if 'floor_number' in unit_data and unit_data['floor_number'] is not None:
            self.floor_spin.setValue(unit_data['floor_number'])

        # Unit number
        unit_num = unit_data.get('unit_number') or unit_data.get('apartment_number')
        if unit_num:
            try:
                self.unit_number_spin.setValue(int(unit_num))
            except (ValueError, TypeError):
                pass

        # Number of rooms
        if 'number_of_rooms' in unit_data:
            self.rooms_spin.setValue(unit_data['number_of_rooms'] or 0)

        # Area
        if 'area_sqm' in unit_data and unit_data['area_sqm']:
            self.area_input.setText(str(unit_data['area_sqm']))

        # Description
        if 'property_description' in unit_data and unit_data['property_description']:
            self.description_edit.setPlainText(unit_data['property_description'])

    def get_unit_data(self) -> Dict[str, Any]:
        """Get unit data from form with integer codes for API."""
        # Parse area
        area_value = None
        area_text = self.area_input.text().strip()
        if area_text:
            try:
                area_value = float(area_text)
            except ValueError:
                pass

        # Get integer codes from dropdowns (API expects integers)
        unit_type_code = self.unit_type_combo.currentData() or 1  # Default to Apartment
        status_code = self.unit_status_combo.currentData() or 1  # Default to Occupied

        unit_data = {
            'unit_uuid': self.unit_data.get('unit_uuid') if self.unit_data else str(uuid.uuid4()),
            'building_id': self.building.building_id,
            'building_uuid': self.building.building_uuid,
            'unit_type': unit_type_code,  # Integer code for API
            'status': status_code,  # Integer code for API
            'apartment_status': status_code,  # Compatibility
            'floor_number': self.floor_spin.value(),
            'unit_number': str(self.unit_number_spin.value()),
            'apartment_number': str(self.unit_number_spin.value()),  # Compatibility
            'number_of_rooms': self.rooms_spin.value(),
            'area_sqm': area_value,
            'property_description': self.description_edit.toPlainText().strip() or None
        }

        return unit_data

    def set_auth_token(self, token: str):
        """Set authentication token for API calls."""
        if self._api_service:
            self._api_service.set_access_token(token)
