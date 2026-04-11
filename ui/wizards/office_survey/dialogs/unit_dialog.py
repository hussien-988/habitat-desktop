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
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import get_unit_type_options, get_unit_status_options
from services.error_mapper import map_exception
from ui.components.toast import Toast
from ui.components.loading_spinner import LoadingSpinnerOverlay
from utils.logger import get_logger
from ui.design_system import ScreenScale
from ui.wizards.office_survey.wizard_styles import FORM_FIELD_STYLE, FOOTER_PRIMARY_STYLE, FOOTER_SECONDARY_STYLE

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

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setLayoutDirection(get_layout_direction())
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Dynamic side-panel sizing
        parent_rect = parent.window().geometry() if parent else None
        if parent_rect:
            panel_w = min(560, parent_rect.width() - 40)
            panel_h = min(660, parent_rect.height() - 20)
        else:
            panel_w = 560
            panel_h = 660
        self.setFixedSize(panel_w, panel_h)

        self.setStyleSheet("QDialog { background-color: transparent; }")
        self._overlay = None
        self._slide_anim = None

        self._setup_ui()
        if unit_data:
            self._load_unit_data(unit_data)

    def _do_slide_in(self):
        """Position as side panel with slide-in animation."""
        parent = self.parent()
        if not parent:
            return
        try:
            from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint
            parent_rect = parent.window().geometry()
            is_rtl = get_layout_direction() == Qt.RightToLeft
            pw = self.width()
            parent_global = parent.window().mapToGlobal(parent.window().rect().topLeft())
            if is_rtl:
                target_x = parent_global.x() + 10
            else:
                target_x = parent_global.x() + parent_rect.width() - pw - 10
            target_y = parent_global.y() + (parent_rect.height() - self.height()) // 2
            start_x = target_x + ((-pw) if is_rtl else pw)
            self.move(start_x, target_y)
            self._slide_anim = QPropertyAnimation(self, b"pos", self)
            self._slide_anim.setDuration(250)
            self._slide_anim.setStartValue(QPoint(start_x, target_y))
            self._slide_anim.setEndValue(QPoint(target_x, target_y))
            self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._slide_anim.start()
        except Exception:
            pass

    def _setup_ui(self):
        """Setup the dialog UI as side panel."""
        from ui.font_utils import create_font, FontManager
        from PyQt5.QtWidgets import QScrollArea

        self.setLayoutDirection(get_layout_direction())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        content_frame = QFrame()
        content_frame.setObjectName("ContentFrame")
        content_frame.setStyleSheet("""
            QFrame#ContentFrame {
                background-color: #FFFFFF;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top: 1px solid rgba(56, 144, 223, 0.20);
            }
            QFrame#ContentFrame QLabel,
            QFrame#ContentFrame QRadioButton {
                background-color: transparent;
            }
        """)

        shadow = QGraphicsDropShadowEffect(content_frame)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, -6)
        shadow.setColor(QColor(0, 0, 0, 100))
        content_frame.setGraphicsEffect(shadow)

        main_layout.addWidget(content_frame)

        frame_layout = QVBoxLayout(content_frame)
        frame_layout.setSpacing(0)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        # Header bar
        header_bar = QFrame()
        header_bar.setFixedHeight(ScreenScale.h(50))
        header_bar.setObjectName("PanelHeader")
        header_bar.setStyleSheet("""
            QFrame#PanelHeader {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #EBF5FF, stop:0.5 #E0EEFB, stop:1 #D6E8F7);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        hdr_layout = QHBoxLayout(header_bar)
        hdr_layout.setContentsMargins(20, 0, 20, 0)
        hdr_layout.setSpacing(10)

        close_btn = QPushButton("\u2715")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(ScreenScale.w(30), ScreenScale.h(30))
        close_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 64, 100, 0.08);
                color: #3B82F6;
                border: 1px solid rgba(56, 144, 223, 0.15);
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(30, 64, 100, 0.15);
                color: #1E40AF;
            }
        """)
        close_btn.clicked.connect(self.reject)
        hdr_layout.addWidget(close_btn)

        header_title = tr("wizard.unit_dialog.title_add") if not self.unit_data else tr("wizard.unit_dialog.title_edit")
        hdr_lbl = QLabel(header_title)
        hdr_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
        hdr_lbl.setStyleSheet("color: #1A365D; background: transparent; border: none;")
        hdr_layout.addWidget(hdr_lbl, 1)

        frame_layout.addWidget(header_bar)

        # Accent line
        accent = QFrame()
        accent.setFixedHeight(2)
        accent.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(56, 144, 223, 0),
                    stop:0.2 rgba(56, 144, 223, 120),
                    stop:0.5 rgba(91, 168, 240, 180),
                    stop:0.8 rgba(56, 144, 223, 120),
                    stop:1 rgba(56, 144, 223, 0));
            }
        """)
        frame_layout.addWidget(accent)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(56, 144, 223, 0.30);
                border-radius: 3px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(56, 144, 223, 0.50);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content_inner = QWidget()
        content_inner.setStyleSheet("background-color: #FFFFFF;")
        layout = QVBoxLayout(content_inner)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 12, 20, 14)

        scroll.setWidget(content_inner)
        frame_layout.addWidget(scroll, 1)

        # Row 1: رقم الطابق | رقم المقسم
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 100)
        self.floor_spin.setValue(0)
        self.floor_spin.setAlignment(Qt.AlignRight)
        self.floor_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.floor_spin.setButtonSymbols(QSpinBox.NoButtons)
        floor_widget = self._create_spinbox_with_arrows(self.floor_spin)
        row1.addLayout(self._create_field_container(tr("wizard.unit_dialog.floor_number"), floor_widget), 1)

        self.unit_number_spin = QSpinBox()
        self.unit_number_spin.setRange(0, 9999)
        self.unit_number_spin.setValue(0)
        self.unit_number_spin.setAlignment(Qt.AlignRight)
        self.unit_number_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.unit_number_spin.setButtonSymbols(QSpinBox.NoButtons)
        unit_widget = self._create_spinbox_with_arrows(self.unit_number_spin)
        row1.addLayout(self._create_field_container(tr("wizard.unit_dialog.unit_number"), unit_widget), 1)

        layout.addLayout(row1)

        # Row 2: نوع المقسم | حالة المقسم
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        self.unit_type_combo = RtlCombo()
        self.unit_type_combo.setStyleSheet(self._combo_style())
        self.unit_type_combo.setFixedHeight(ScreenScale.h(40))
        self.unit_type_combo.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_type_options():
            self.unit_type_combo.addItem(label, code)
        row2.addLayout(self._create_field_container(tr("wizard.unit_dialog.unit_type"), self.unit_type_combo), 1)

        self.unit_status_combo = RtlCombo()
        self.unit_status_combo.setStyleSheet(self._combo_style())
        self.unit_status_combo.setFixedHeight(ScreenScale.h(40))
        self.unit_status_combo.addItem(tr("wizard.unit_dialog.select"), 0)
        for code, label in get_unit_status_options():
            self.unit_status_combo.addItem(label, code)
        row2.addLayout(self._create_field_container(tr("wizard.unit_dialog.unit_status"), self.unit_status_combo), 1)

        layout.addLayout(row2)

        # Row 3: عدد الغرف | مساحة المقسم
        row3 = QHBoxLayout()
        row3.setSpacing(16)

        self.rooms_spin = QSpinBox()
        self.rooms_spin.setRange(0, 20)
        self.rooms_spin.setValue(0)
        self.rooms_spin.setAlignment(Qt.AlignRight)
        self.rooms_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.rooms_spin.setButtonSymbols(QSpinBox.NoButtons)
        rooms_widget = self._create_spinbox_with_arrows(self.rooms_spin)
        row3.addLayout(self._create_field_container(tr("wizard.unit_dialog.rooms"), rooms_widget), 1)

        self.area_input = QLineEdit()
        self.area_input.setFixedHeight(ScreenScale.h(40))
        self.area_input.setPlaceholderText(tr("wizard.unit_dialog.area_placeholder"))
        self.area_input.setStyleSheet(self._input_style())

        area_validator = QDoubleValidator(0.0, 999999.99, 2, self.area_input)
        area_validator.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        area_validator.setNotation(QDoubleValidator.StandardNotation)
        self.area_input.setValidator(area_validator)

        self.area_error_label = QLabel("")
        self.area_error_label.setStyleSheet("color: #e74c3c; font-size: 9pt; background: transparent;")
        self.area_error_label.setVisible(False)
        self.area_input.textChanged.connect(self._validate_area_input)

        row3.addLayout(self._create_field_container_with_validation(tr("wizard.unit_dialog.area"), self.area_input, self.area_error_label), 1)

        layout.addLayout(row3)

        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(ScreenScale.h(110))
        self.description_edit.setMaximumHeight(ScreenScale.h(110))
        self.description_edit.setPlaceholderText(tr("wizard.unit_dialog.description_placeholder"))
        self.description_edit.setStyleSheet(FORM_FIELD_STYLE)
        layout.addLayout(self._create_field_container(tr("wizard.unit_dialog.description"), self.description_edit))

        layout.addStretch(1)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)

        self.save_btn = self._create_save_button()
        cancel_btn = self._create_cancel_button()

        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.save_btn)

        layout.addLayout(buttons_layout)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """Create a spinbox widget with icon arrows (same as buildings_page)."""
        from ui.components.icon import Icon

        # Container frame - يرث RTL من التطبيق (مطابق لـ buildings_page)
        container = QFrame()
        container.setFixedHeight(ScreenScale.h(40))
        container.setStyleSheet("""
            QFrame {
                border: 1.5px solid #D0D7E2;
                border-radius: 10px;
                background-color: #FFFFFF;
            }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Spinbox (no border since container has border)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 8px 14px;
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #2C3E50;
                min-height: 30px;
                selection-background-color: transparent;
                selection-color: #2C3E50;
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
        arrow_container.setFixedWidth(ScreenScale.w(30))
        arrow_container.setStyleSheet("""
            QFrame {
                border: none;
                border-left: 1.5px solid #D0D7E2;
                background: transparent;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }
        """)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)

        # Up arrow icon (^.png)
        up_label = QLabel()
        up_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(22))
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
        down_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(22))
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

        Args:
            label_text: Text for the label
            widget: The input widget (QComboBox, QLineEdit, etc.)

        Returns:
            QVBoxLayout with label and widget
        """
        from ui.font_utils import create_font, FontManager
        container = QVBoxLayout()
        container.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet("color: #64748B; background: transparent; border: none;")

        container.addWidget(label)
        container.addWidget(widget)

        return container

    def _create_field_container_with_validation(self, label_text: str, widget, validation_label: QLabel) -> QVBoxLayout:
        """
        Create a field container with label, widget, and validation message.

        Args:
            label_text: Text for the label
            widget: The input widget
            validation_label: QLabel for validation messages

        Returns:
            QVBoxLayout with label, widget, and validation label
        """
        from ui.font_utils import create_font, FontManager
        container = QVBoxLayout()
        container.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet("color: #64748B; background: transparent; border: none;")

        container.addWidget(label)
        container.addWidget(widget)
        container.addWidget(validation_label)

        return container

    def _create_save_button(self) -> QPushButton:
        """
        Create save button with consistent styling.

        Returns:
            QPushButton configured as save button
        """
        btn = QPushButton(tr("common.save"))
        btn.setFixedHeight(ScreenScale.h(44))
        btn.setStyleSheet(FOOTER_PRIMARY_STYLE)
        btn.clicked.connect(self._on_save)
        return btn

    def _create_cancel_button(self) -> QPushButton:
        """
        Create cancel button with consistent styling.

        Returns:
            QPushButton configured as cancel button
        """
        btn = QPushButton(tr("common.cancel"))
        btn.setFixedHeight(ScreenScale.h(44))
        btn.setStyleSheet(FOOTER_SECONDARY_STYLE)
        btn.clicked.connect(self.reject)
        return btn

    def _combo_style(self) -> str:
        """Get combobox stylesheet - matches person_dialog (FORM_FIELD_STYLE)."""
        return FORM_FIELD_STYLE

    def _input_style(self) -> str:
        """Get input stylesheet - matches person_dialog (FORM_FIELD_STYLE)."""
        return FORM_FIELD_STYLE

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

    def _validate_basic(self) -> bool:
        """Validate form data (without uniqueness check)."""
        if not self.unit_type_combo.currentData():
            self._show_styled_message(tr("common.warning"), tr("wizard.unit_dialog.select_type_warning"))
            return False

        if self.unit_number_spin.value() == 0:
            self._show_styled_message(tr("common.warning"), tr("wizard.unit_dialog.enter_number_warning"))
            return False

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

    def _is_unit_unique_local(self, units_data, unit_number, floor) -> bool:
        """Check uniqueness locally against already-fetched unit list."""
        for unit in units_data:
            if self.unit_data and hasattr(unit, 'unit_id') and unit.unit_id == self.unit_data.get('unit_id'):
                continue
            u_num = getattr(unit, 'apartment_number', None) or getattr(unit, 'unit_number', None)
            u_floor = getattr(unit, 'floor_number', None)
            if u_num == unit_number and u_floor == floor:
                return False
        return True

    def _on_save(self):
        """Handle save button click - validates then saves."""
        # Run basic validation (without uniqueness check)
        if not self._validate_basic():
            return

        # Disable save button while checking uniqueness
        self.save_btn.setEnabled(False)

        unit_number = str(self.unit_number_spin.value())
        floor = self.floor_spin.value()

        def _do_fetch():
            return self.unit_controller.get_units_for_building(self.building.building_uuid)

        def _on_units_fetched(result):
            self._spinner.hide_loading()
            self.save_btn.setEnabled(True)
            if result.success and result.data:
                if not self._is_unit_unique_local(result.data, unit_number, floor):
                    self._show_styled_message(tr("common.warning"), tr("wizard.unit_dialog.number_taken"))
                    return
            self._do_save()

        def _on_fetch_error(msg):
            self._spinner.hide_loading()
            self.save_btn.setEnabled(True)
            logger.error(f"Error checking uniqueness: {msg}")
            # Allow save if check fails
            self._do_save()

        self._spinner.show_loading(tr("component.loading.default"))
        self._uniqueness_worker = ApiWorker(_do_fetch)
        self._uniqueness_worker.finished.connect(_on_units_fetched)
        self._uniqueness_worker.error.connect(_on_fetch_error)
        self._uniqueness_worker.start()

    def _do_save(self):
        """Proceed with the actual save after validation passes."""
        if not self.unit_data:
            unit_data = self.get_unit_data()
            if self._survey_id:
                unit_data['survey_id'] = self._survey_id

            logger.info(f"Creating property unit via API: {unit_data}")
            self._spinner.show_loading(tr("component.loading.default"))
            try:
                response = self._api_service.create_property_unit(unit_data)
                logger.info("Property unit created successfully via API")
                self._created_unit_data = response
            except Exception as e:
                logger.error(f"API unit creation failed: {e}")
                if "409" in str(e):
                    self._show_styled_message(
                        tr("common.error"),
                        tr("wizard.unit_dialog.duplicate_unit"),
                        is_error=True
                    )
                    return
                self._show_styled_message(tr("common.error"), str(e), is_error=True)
                return
            finally:
                self._spinner.hide_loading()

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
        """Show dark overlay and slide-in animation."""
        super().showEvent(event)
        if self.parent():
            top_window = self.parent().window()
            self._overlay = QWidget(top_window)
            self._overlay.setGeometry(0, 0, top_window.width(), top_window.height())
            self._overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.25);")
            self._overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self._overlay.show()
            self._overlay.raise_()
            self.raise_()  # Keep dialog above overlay
        self._do_slide_in()

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
