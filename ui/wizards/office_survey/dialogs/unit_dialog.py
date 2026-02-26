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
    QPushButton, QSpinBox, QTextEdit, QFrame, QGraphicsDropShadowEffect,
    QWidget
)
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QDoubleValidator, QColor

from app.config import Config
from ui.components.rtl_combo import RtlCombo
from models.building import Building
from controllers.unit_controller import UnitController
from ui.error_handler import ErrorHandler
from services.validation_service import ValidationService
from services.api_client import get_api_client
from services.translation_manager import tr
from services.display_mappings import get_unit_type_options, get_unit_status_options
from services.error_mapper import map_exception
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
        if self._api_service and auth_token:
            self._api_service.set_access_token(auth_token)
            self.unit_controller.set_auth_token(auth_token)
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

        # إزالة الشريط العلوي (title bar)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)

        # CRITICAL: ضبط RTL صراحةً - الـ Dialog نافذة مستقلة لا ترث RTL من التطبيق
        self.setLayoutDirection(Qt.RightToLeft)

        # CRITICAL: جعل الخلفية شفافة حتى تظهر فقط الزوايا المنحنية
        self.setAttribute(Qt.WA_TranslucentBackground)

        # الأبعاد حسب Figma: 574×589 + shadow margin (20+20=40 W, 12+28=40 H)
        self.setFixedSize(614, 629)

        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
        """)

        self._overlay = None

        self._setup_ui()
        if unit_data:
            self._load_unit_data(unit_data)

    def _setup_ui(self):
        """Setup the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 12, 20, 28)  # Margin for shadow to render
        main_layout.setSpacing(0)

        # إنشاء frame أبيض مع زوايا منحنية (يرث RTL من التطبيق تلقائياً)
        content_frame = QFrame()
        content_frame.setObjectName("ContentFrame")
        content_frame.setStyleSheet("""
            QFrame#ContentFrame {
                background-color: #FFFFFF;
                border: none;
                border-radius: 24px;
            }
        """)

        # Shadow effect — makes dialog float above the page
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 80))
        content_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(content_frame)
        layout.setSpacing(0)
        layout.setContentsMargins(24, 16, 24, 16)

        # العنوان (RTL يحاذيه يميناً تلقائياً)
        header_label = QLabel("اضف معلومات المقسم" if not self.unit_data else "تعديل معلومات المقسم")
        header_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #1A1F1D; background: transparent;")
        layout.addWidget(header_label)

        layout.addSpacing(32)

        # Row 1: رقم الطابق (يمين) | رقم المقسم (يسار)
        # في RTL: أول عنصر يُضاف → يظهر يميناً
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # رقم الطابق (يمين في RTL = أول عنصر)
        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 100)
        self.floor_spin.setValue(0)
        self.floor_spin.setAlignment(Qt.AlignRight)
        self.floor_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.floor_spin.setButtonSymbols(QSpinBox.NoButtons)
        floor_widget = self._create_spinbox_with_arrows(self.floor_spin)
        row1.addLayout(self._create_field_container("رقم الطابق", floor_widget), 1)

        # رقم المقسم (يسار في RTL = ثاني عنصر)
        self.unit_number_spin = QSpinBox()
        self.unit_number_spin.setRange(0, 9999)
        self.unit_number_spin.setValue(0)
        self.unit_number_spin.setAlignment(Qt.AlignRight)
        self.unit_number_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.unit_number_spin.setButtonSymbols(QSpinBox.NoButtons)
        unit_widget = self._create_spinbox_with_arrows(self.unit_number_spin)
        row1.addLayout(self._create_field_container("رقم المقسم", unit_widget), 1)

        layout.addLayout(row1)

        layout.addSpacing(16)

        # Row 2: نوع المقسم (يمين) | حالة المقسم (يسار)
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # نوع المقسم (يمين في RTL = أول عنصر)
        self.unit_type_combo = RtlCombo()
        self.unit_type_combo.setStyleSheet(self._combo_style())
        self.unit_type_combo.setFixedHeight(40)
        self.unit_type_combo.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_type_options():
            self.unit_type_combo.addItem(label, code)
        row2.addLayout(self._create_field_container("نوع المقسم", self.unit_type_combo), 1)

        # حالة المقسم (يسار في RTL = ثاني عنصر)
        self.unit_status_combo = RtlCombo()
        self.unit_status_combo.setStyleSheet(self._combo_style())
        self.unit_status_combo.setFixedHeight(40)
        self.unit_status_combo.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_status_options():
            self.unit_status_combo.addItem(label, code)
        row2.addLayout(self._create_field_container("حالة المقسم", self.unit_status_combo), 1)

        layout.addLayout(row2)

        layout.addSpacing(16)

        # Row 3: عدد الغرف (يمين) | مساحة المقسم (يسار)
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        # عدد الغرف (يمين في RTL = أول عنصر)
        self.rooms_spin = QSpinBox()
        self.rooms_spin.setRange(0, 20)
        self.rooms_spin.setValue(0)
        self.rooms_spin.setAlignment(Qt.AlignRight)
        self.rooms_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.rooms_spin.setButtonSymbols(QSpinBox.NoButtons)
        rooms_widget = self._create_spinbox_with_arrows(self.rooms_spin)
        row3.addLayout(self._create_field_container("عدد الغرف", rooms_widget), 1)

        # مساحة المقسم (يسار في RTL = ثاني عنصر)
        self.area_input = QLineEdit()
        self.area_input.setFixedHeight(40)
        self.area_input.setPlaceholderText(tr("wizard.unit_dialog.area_placeholder"))
        self.area_input.setStyleSheet(self._input_style())

        area_validator = QDoubleValidator(0.0, 999999.99, 2, self.area_input)
        area_validator.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        area_validator.setNotation(QDoubleValidator.StandardNotation)
        self.area_input.setValidator(area_validator)

        self.area_error_label = QLabel("")
        self.area_error_label.setStyleSheet("color: #e74c3c; font-size: 11px; background: transparent;")
        self.area_error_label.setVisible(False)
        self.area_input.textChanged.connect(self._validate_area_input)

        row3.addLayout(self._create_field_container_with_validation("مساحة المقسم", self.area_input, self.area_error_label), 1)

        layout.addLayout(row3)

        layout.addSpacing(16)

        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(131)
        self.description_edit.setMaximumHeight(131)
        self.description_edit.setPlaceholderText(
            tr("wizard.unit_dialog.description_placeholder")
        )
        self.description_edit.setStyleSheet("""
            QTextEdit {
                padding: 8px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 14px;
                color: #6B7280;
            }
            QTextEdit:focus {
                border-color: #3890DF;
                border-width: 2px;
            }
        """)
        # Center-align placeholder and text
        from PyQt5.QtGui import QTextCursor, QTextBlockFormat
        self.description_edit.setAlignment(Qt.AlignCenter)
        layout.addLayout(self._create_field_container("وصف المقسم", self.description_edit))

        layout.addSpacing(40)

        # Buttons: في RTL أول عنصر → يمين
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)

        self.save_btn = self._create_save_button()
        cancel_btn = self._create_cancel_button()

        # الغاء يمين (أول) | حفظ يسار (ثاني) - تناسب اتجاه القراءة العربية
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.save_btn)

        layout.addLayout(buttons_layout)

        main_layout.addWidget(content_frame)

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """Create a spinbox widget with icon arrows (same as buildings_page)."""
        from ui.components.icon import Icon

        # Container frame - يرث RTL من التطبيق (مطابق لـ buildings_page)
        container = QFrame()
        container.setFixedHeight(40)
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

        # Spinbox (no border since container has border)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                padding-right: 35px;
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #606266;
                selection-background-color: transparent;
                selection-color: #606266;
            }
            QSpinBox:focus {
                border: none;
                outline: 0;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)
        layout.addWidget(spinbox, 1)

        # Arrow column (RIGHT side) with left border separator
        arrow_container = QFrame()
        arrow_container.setFixedWidth(30)
        arrow_container.setStyleSheet("""
            QFrame {
                border: none;
                border-left: 1px solid #E1E8ED;
                background: transparent;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)

        # Up arrow icon (^.png)
        up_label = QLabel()
        up_label.setFixedSize(30, 22)
        up_label.setAlignment(Qt.AlignCenter)
        up_pixmap = Icon.load_pixmap("^", size=10)
        if up_pixmap and not up_pixmap.isNull():
            up_label.setPixmap(up_pixmap)
        else:
            up_label.setText("^")
            up_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        up_label.setCursor(Qt.PointingHandCursor)
        up_label.mousePressEvent = lambda _: spinbox.stepUp()
        arrow_layout.addWidget(up_label)

        # Down arrow icon (v.png)
        down_label = QLabel()
        down_label.setFixedSize(30, 22)
        down_label.setAlignment(Qt.AlignCenter)
        down_pixmap = Icon.load_pixmap("v", size=10)
        if down_pixmap and not down_pixmap.isNull():
            down_label.setPixmap(down_pixmap)
        else:
            down_label.setText("v")
            down_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda _: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        layout.addWidget(arrow_container)

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
        container.setSpacing(4)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 14px; font-weight: 600; color: #374151; background: transparent;")

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
        label.setStyleSheet("font-size: 14px; font-weight: 600; color: #374151; background: transparent;")

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
        btn = QPushButton(tr("common.save"))
        btn.setFixedSize(264, 44)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                color: white;
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
        btn = QPushButton(tr("common.cancel"))
        btn.setFixedSize(264, 44)
        btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #A9B2BC;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
                color: #374151;
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
        """Get combobox stylesheet - same pattern as buildings_page."""
        arrow_img = str(Config.IMAGES_DIR / "v.png").replace("\\", "/")
        return f"""
            QComboBox {{
                padding: 6px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 14px;
                font-weight: 600;
                color: #9CA3AF;
            }}
            QComboBox:focus {{
                border-color: #3890DF;
                border-width: 2px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: center right;
                width: 35px;
                border: none;
                margin-right: 5px;
            }}
            QComboBox::down-arrow {{
                image: url({arrow_img});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                font-size: 14px;
                background-color: white;
                selection-background-color: #3890DF;
                selection-color: white;
            }}
        """


    def _input_style(self) -> str:
        """Get input stylesheet with consistent dimensions."""
        return """
            QLineEdit {
                padding: 6px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 14px;
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
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #e74c3c;
                border-width: 2px;
            }
        """

    def _show_styled_message(self, title: str, message: str, is_error: bool = False):
        """Show a styled message box."""
        if is_error:
            ErrorHandler.show_error(self, message, title)
        else:
            ErrorHandler.show_warning(self, message, title)

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
            self.area_error_label.setText(tr("wizard.unit_dialog.area_numbers_only"))
            self.area_error_label.setVisible(True)
            self.area_input.setStyleSheet(self._input_error_style())

    def _validate(self) -> bool:
        """Validate form data on save."""
        # Unit type is required
        if not self.unit_type_combo.currentData():
            self._show_styled_message(tr("common.warning"), tr("wizard.unit_dialog.select_type_warning"))
            return False

        # Unit number is required
        if self.unit_number_spin.value() == 0:
            self._show_styled_message(tr("common.warning"), tr("wizard.unit_dialog.enter_number_warning"))
            return False

        # Check uniqueness on save
        if not self._is_unit_unique():
            self._show_styled_message(tr("common.warning"), tr("wizard.unit_dialog.number_taken"))
            return False

        # Area should be numeric if provided
        area_text = self.area_input.text().strip()
        if area_text:
            try:
                float(area_text)
                self.area_error_label.setVisible(False)
                self.area_input.setStyleSheet(self._input_style())
            except ValueError:
                self.area_error_label.setText(tr("wizard.unit_dialog.area_numbers_only"))
                self.area_error_label.setVisible(True)
                self.area_input.setStyleSheet(self._input_error_style())
                self.area_input.setFocus()
                return False

        return True

    def _is_unit_unique(self) -> bool:
        """Check if unit number + floor combination is unique within the building."""
        unit_number = str(self.unit_number_spin.value())
        floor = self.floor_spin.value()

        try:
            result = self.unit_controller.get_units_for_building(self.building.building_uuid)
            if not result.success:
                return True  # Allow save if check fails

            for unit in result.data:
                # Skip if editing the same unit
                if self.unit_data and hasattr(unit, 'unit_id') and unit.unit_id == self.unit_data.get('unit_id'):
                    continue
                # Check for duplicate
                u_num = getattr(unit, 'apartment_number', None) or getattr(unit, 'unit_number', None)
                u_floor = getattr(unit, 'floor_number', None)
                if u_num == unit_number and u_floor == floor:
                    return False

            return True
        except Exception as e:
            logger.error(f"Error checking uniqueness: {e}", exc_info=True)
            return True  # Allow save if check fails

    def _on_save(self):
        """Handle save button click."""
        if not self._validate():
            return

        if not self.unit_data:
            unit_data = self.get_unit_data()
            if self._survey_id:
                unit_data['survey_id'] = self._survey_id

            logger.info(f"Creating property unit via API: {unit_data}")
            try:
                response = self._api_service.create_property_unit(unit_data)
                logger.info("Property unit created successfully via API")
                self._created_unit_data = response
            except Exception as e:
                logger.error(f"API unit creation failed: {e}")
                if "409" in str(e):
                    self._show_styled_message(
                        tr("common.error"),
                        "هذا المقسم مسجّل مسبقاً في النظام. يرجى اختياره من القائمة أو تغيير رقم المقسم.",
                        is_error=True
                    )
                    return
                self._show_styled_message(tr("common.error"), str(e), is_error=True)
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

    # ── Overlay for floating appearance ──

    def showEvent(self, event):
        """Show dark overlay behind dialog when it opens."""
        super().showEvent(event)
        if self.parent():
            top_window = self.parent().window()
            self._overlay = QWidget(top_window)
            self._overlay.setGeometry(0, 0, top_window.width(), top_window.height())
            self._overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.4);")
            self._overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self._overlay.show()
            self._overlay.raise_()
            self.raise_()  # Keep dialog above overlay

    def _cleanup_overlay(self):
        """Remove the dark overlay."""
        if self._overlay:
            try:
                self._overlay.hide()
                self._overlay.setParent(None)
                self._overlay.deleteLater()
            except RuntimeError:
                pass
            self._overlay = None

    def closeEvent(self, event):
        self._cleanup_overlay()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_overlay()
        super().reject()

    def accept(self):
        self._cleanup_overlay()
        super().accept()
