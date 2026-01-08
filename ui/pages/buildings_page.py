# -*- coding: utf-8 -*-
"""
Buildings list page with filters and table - Professional design.
"""

import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QFileDialog, QAbstractItemView, QGraphicsDropShadowEffect,
    QDialog, QFormLayout, QDoubleSpinBox, QSpinBox, QMessageBox, QScrollArea,
    QMenu, QAction, QToolButton, QSizePolicy, QTabWidget, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QCursor

# Try to import WebEngine for map
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from app.config import Config, Vocabularies, AleppoDivisions
from models.building import Building
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from services.export_service import ExportService
from services.validation_service import ValidationService
from ui.components.table_models import BuildingsTableModel
from ui.components.toast import Toast
from ui.components.dialogs import ExportDialog
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingDialog(QDialog):
    """
    Dialog for creating/editing a building (UC-000 S02, S02a, S03, S04, S06).
    """

    def __init__(self, i18n: I18n, building: Building = None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.building = building
        self.validation_service = ValidationService()

        self.setWindowTitle("تعديل مبنى" if building else "إضافة مبنى جديد")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        self._setup_ui()

        if building:
            self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        form = QFormLayout(content)
        form.setSpacing(12)

        # Administrative Hierarchy Section (UC-000 S03)
        section_label = QLabel("التسلسل الإداري:")
        section_label.setStyleSheet("font-weight: 700; font-size: 11pt; margin-top: 10px;")
        form.addRow(section_label)

        # Governorate
        self.governorate_combo = QComboBox()
        self.governorate_combo.addItem("حلب", "01")  # Default for Aleppo
        form.addRow("المحافظة:", self.governorate_combo)

        # District
        self.district_combo = QComboBox()
        for code, name, name_ar in AleppoDivisions.DISTRICTS:
            self.district_combo.addItem(name_ar, code)
        self.district_combo.currentIndexChanged.connect(self._update_building_id)
        form.addRow("المنطقة:", self.district_combo)

        # Neighborhood
        self.neighborhood_combo = QComboBox()
        for code, name, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
            self.neighborhood_combo.addItem(name_ar, code)
        self.neighborhood_combo.currentIndexChanged.connect(self._update_building_id)
        form.addRow("الحي:", self.neighborhood_combo)

        # Building Number (used to construct building_id)
        self.building_number = QLineEdit()
        self.building_number.setPlaceholderText("رقم المبنى (مثال: 00001)")
        self.building_number.setMaxLength(5)
        self.building_number.textChanged.connect(self._update_building_id)
        form.addRow("رقم المبنى:", self.building_number)

        # Generated Building ID (readonly display)
        self.building_id_label = QLabel("-")
        self.building_id_label.setStyleSheet(f"color: {Config.PRIMARY_COLOR}; font-weight: 600;")
        form.addRow("رمز المبنى:", self.building_id_label)

        # Building Properties Section
        section_label2 = QLabel("خصائص المبنى:")
        section_label2.setStyleSheet("font-weight: 700; font-size: 11pt; margin-top: 10px;")
        form.addRow(section_label2)

        # Building Type
        self.type_combo = QComboBox()
        for code, en, ar in Vocabularies.BUILDING_TYPES:
            self.type_combo.addItem(ar, code)
        form.addRow("نوع المبنى:", self.type_combo)

        # Building Status
        self.status_combo = QComboBox()
        for code, en, ar in Vocabularies.BUILDING_STATUS:
            self.status_combo.addItem(ar, code)
        form.addRow("حالة المبنى:", self.status_combo)

        # Number of Floors
        self.floors_spin = QSpinBox()
        self.floors_spin.setRange(1, 50)
        self.floors_spin.setValue(1)
        form.addRow("عدد الطوابق:", self.floors_spin)

        # Number of Apartments
        self.apartments_spin = QSpinBox()
        self.apartments_spin.setRange(0, 200)
        form.addRow("عدد الشقق:", self.apartments_spin)

        # Number of Shops
        self.shops_spin = QSpinBox()
        self.shops_spin.setRange(0, 50)
        form.addRow("عدد المحلات:", self.shops_spin)

        # Geo Location Section (UC-000 S04)
        section_label3 = QLabel("الموقع الجغرافي:")
        section_label3.setStyleSheet("font-weight: 700; font-size: 11pt; margin-top: 10px;")
        form.addRow(section_label3)

        # Map selection button (UC-000 S04 - Pick from map)
        map_btn_container = QWidget()
        map_btn_layout = QHBoxLayout(map_btn_container)
        map_btn_layout.setContentsMargins(0, 0, 0, 0)
        map_btn_layout.setSpacing(8)

        self.pick_from_map_btn = QPushButton("📍 اختر من الخريطة")
        self.pick_from_map_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        self.pick_from_map_btn.setCursor(Qt.PointingHandCursor)
        self.pick_from_map_btn.clicked.connect(self._on_pick_from_map)
        map_btn_layout.addWidget(self.pick_from_map_btn)

        self.location_status_label = QLabel("")
        self.location_status_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 9pt;")
        map_btn_layout.addWidget(self.location_status_label)
        map_btn_layout.addStretch()

        form.addRow("", map_btn_container)

        # Latitude (Read-only - UC-000 Comment 3: Manual entry isn't practical)
        self.latitude_spin = QDoubleSpinBox()
        self.latitude_spin.setRange(35.0, 38.0)  # Aleppo region
        self.latitude_spin.setDecimals(6)
        self.latitude_spin.setSingleStep(0.0001)
        self.latitude_spin.setSpecialValueText("لم يتم التحديد - اختر من الخريطة")
        self.latitude_spin.setValue(0)  # Default to 0 = not set
        self.latitude_spin.setReadOnly(True)  # Read-only per UC-000 Comment 3
        self.latitude_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)  # Hide spinbox arrows
        self.latitude_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_LIGHT};
                border: 1px dashed {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        form.addRow("خط العرض:", self.latitude_spin)

        # Longitude (Read-only - UC-000 Comment 3: Manual entry isn't practical)
        self.longitude_spin = QDoubleSpinBox()
        self.longitude_spin.setRange(36.0, 39.0)  # Aleppo region
        self.longitude_spin.setDecimals(6)
        self.longitude_spin.setSingleStep(0.0001)
        self.longitude_spin.setSpecialValueText("لم يتم التحديد - اختر من الخريطة")
        self.longitude_spin.setValue(0)  # Default to 0 = not set
        self.longitude_spin.setReadOnly(True)  # Read-only per UC-000 Comment 3
        self.longitude_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)  # Hide spinbox arrows
        self.longitude_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {Config.BACKGROUND_COLOR};
                color: {Config.TEXT_LIGHT};
                border: 1px dashed {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        form.addRow("خط الطول:", self.longitude_spin)

        # Geometry type indicator
        self.geometry_type_label = QLabel("نوع الإحداثيات: نقطة")
        self.geometry_type_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 9pt;")
        form.addRow("", self.geometry_type_label)

        # Store polygon data if selected from map
        self._polygon_wkt = None

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {Config.ERROR_COLOR};")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("حفظ")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _update_building_id(self):
        """Generate building ID based on administrative codes (UC-000 S03)."""
        gov = self.governorate_combo.currentData() or "01"
        dist = self.district_combo.currentData() or "01"
        # Subdistrict and community default to 01
        subdist = "01"
        comm = "001"
        neigh = self.neighborhood_combo.currentData() or "001"
        bldg_num = self.building_number.text().strip().zfill(5)

        # Format: GG-DD-SS-CCC-NNN-BBBBB (17 chars with dashes)
        building_id = f"{gov}-{dist}-{subdist}-{comm}-{neigh}-{bldg_num}"
        self.building_id_label.setText(building_id)

    def _on_pick_from_map(self):
        """Open map picker dialog (UC-000 S04)."""
        try:
            from ui.components.map_picker_dialog import MapPickerDialog

            current_lat = self.latitude_spin.value()
            current_lon = self.longitude_spin.value()

            dialog = MapPickerDialog(
                initial_lat=current_lat,
                initial_lon=current_lon,
                parent=self
            )

            if dialog.exec_() == QDialog.Accepted:
                result = dialog.get_result()
                if result:
                    self.latitude_spin.setValue(result["latitude"])
                    self.longitude_spin.setValue(result["longitude"])

                    if result.get("polygon_wkt"):
                        self._polygon_wkt = result["polygon_wkt"]
                        self.geometry_type_label.setText("نوع الإحداثيات: مضلع (Polygon)")
                        self.location_status_label.setText("✓ تم تحديد الموقع من الخريطة")
                    else:
                        self._polygon_wkt = None
                        self.geometry_type_label.setText("نوع الإحداثيات: نقطة")
                        self.location_status_label.setText("✓ تم تحديد الموقع")

                    self.location_status_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR}; font-size: 9pt;")

        except ImportError:
            # Fallback if map picker not available
            QMessageBox.information(
                self,
                "اختيار الموقع",
                "يرجى إدخال الإحداثيات يدوياً.\n\n"
                "ملاحظة: يمكنك الحصول على الإحداثيات من Google Maps\n"
                "بالنقر بزر الماوس الأيمن على الموقع واختيار 'إحداثيات'"
            )

    def _populate_data(self):
        """Populate form with existing building data."""
        if not self.building:
            return

        # Set combos by data
        idx = self.district_combo.findData(self.building.district_code)
        if idx >= 0:
            self.district_combo.setCurrentIndex(idx)

        idx = self.neighborhood_combo.findData(self.building.neighborhood_code)
        if idx >= 0:
            self.neighborhood_combo.setCurrentIndex(idx)

        # Extract building number from building_id (last 5 digits)
        if self.building.building_id and len(self.building.building_id) >= 5:
            bldg_num = self.building.building_id[-5:]
            self.building_number.setText(bldg_num)

        idx = self.type_combo.findData(self.building.building_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        idx = self.status_combo.findData(self.building.building_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        self.floors_spin.setValue(self.building.number_of_floors or 1)
        self.apartments_spin.setValue(self.building.number_of_apartments or 0)
        self.shops_spin.setValue(self.building.number_of_shops or 0)

        if self.building.latitude:
            self.latitude_spin.setValue(self.building.latitude)
            self.location_status_label.setText("✓ تم تحديد الموقع")
            self.location_status_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR}; font-size: 9pt;")
        if self.building.longitude:
            self.longitude_spin.setValue(self.building.longitude)

    def _on_save(self):
        """Validate and save (UC-000 S06)."""
        # Build data dict for validation
        data = self.get_data()

        # Validate
        result = self.validation_service.validate_building(data)

        if not result.is_valid:
            self.error_label.setText(" | ".join(result.errors))
            return

        if result.warnings:
            reply = QMessageBox.warning(
                self,
                "تحذيرات",
                "\n".join(result.warnings) + "\n\nهل تريد المتابعة؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self.accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        dist_idx = self.district_combo.currentIndex()
        neigh_idx = self.neighborhood_combo.currentIndex()

        data = {
            "building_id": self.building_id_label.text(),
            "governorate_code": self.governorate_combo.currentData(),
            "governorate_name": "Aleppo",
            "governorate_name_ar": "حلب",
            "district_code": self.district_combo.currentData(),
            "district_name": AleppoDivisions.DISTRICTS[dist_idx][1] if dist_idx >= 0 else "",
            "district_name_ar": AleppoDivisions.DISTRICTS[dist_idx][2] if dist_idx >= 0 else "",
            "subdistrict_code": "01",
            "subdistrict_name": "",
            "subdistrict_name_ar": "",
            "community_code": "001",
            "community_name": "",
            "community_name_ar": "",
            "neighborhood_code": self.neighborhood_combo.currentData(),
            "neighborhood_name": AleppoDivisions.NEIGHBORHOODS_ALEPPO[neigh_idx][1] if neigh_idx >= 0 else "",
            "neighborhood_name_ar": AleppoDivisions.NEIGHBORHOODS_ALEPPO[neigh_idx][2] if neigh_idx >= 0 else "",
            "building_number": self.building_number.text().strip(),
            "building_type": self.type_combo.currentData(),
            "building_status": self.status_combo.currentData(),
            "number_of_floors": self.floors_spin.value(),
            "number_of_apartments": self.apartments_spin.value(),
            "number_of_shops": self.shops_spin.value(),
            "number_of_units": self.apartments_spin.value() + self.shops_spin.value(),
            "latitude": self.latitude_spin.value() if self.latitude_spin.value() != 0 else None,
            "longitude": self.longitude_spin.value() if self.longitude_spin.value() != 0 else None,
        }

        # Add polygon geometry if selected from map (UC-000 S04)
        if self._polygon_wkt:
            data["polygon_wkt"] = self._polygon_wkt
            data["geometry_type"] = "polygon"
        else:
            data["geometry_type"] = "point"

        return data


class BuildingsPage(QWidget):
    """Buildings list page with professional styling."""

    view_building = pyqtSignal(str)  # Emits building_id

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.export_service = ExportService(db)
        self.map_view = None  # Initialize before _setup_ui

        self._setup_ui()

        # Set up URL handler for map clicks (UC-000 S02a - map selection)
        if HAS_WEBENGINE and self.map_view:
            self.map_view.page().urlChanged.connect(self._handle_map_url)

    def _setup_ui(self):
        """Setup buildings page UI."""
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header row
        header_layout = QHBoxLayout()

        title_label = QLabel(self.i18n.t("building_list"))
        title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Add Building button (UC-000 S01)
        self.add_btn = QPushButton("+ إضافة مبنى")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #16A34A;
            }}
        """)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self._on_add_building)
        header_layout.addWidget(self.add_btn)

        # Export button
        self.export_btn = QPushButton(self.i18n.t('export'))
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self._on_export)
        header_layout.addWidget(self.export_btn)

        layout.addLayout(header_layout)

        # Filters card
        filters_frame = QFrame()
        filters_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        # Add shadow to filters
        filters_shadow = QGraphicsDropShadowEffect()
        filters_shadow.setBlurRadius(20)
        filters_shadow.setColor(QColor(0, 0, 0, 20))
        filters_shadow.setOffset(0, 4)
        filters_frame.setGraphicsEffect(filters_shadow)

        filters_layout = QHBoxLayout(filters_frame)
        filters_layout.setContentsMargins(24, 20, 24, 20)
        filters_layout.setSpacing(20)

        # Search input
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)

        search_label = QLabel(self.i18n.t('search'))
        search_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt; font-weight: 600;")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("رقم المبنى، الحي...")
        self.search_input.setMinimumWidth(220)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: {Config.FONT_SIZE}pt;
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
                background-color: white;
            }}
        """)
        self.search_input.textChanged.connect(self._on_filter_changed)
        search_layout.addWidget(self.search_input)
        filters_layout.addWidget(search_container)

        # Neighborhood filter
        neighborhood_container = QWidget()
        neighborhood_layout = QVBoxLayout(neighborhood_container)
        neighborhood_layout.setContentsMargins(0, 0, 0, 0)
        neighborhood_layout.setSpacing(6)

        neighborhood_label = QLabel(self.i18n.t('neighborhood'))
        neighborhood_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt; font-weight: 600;")
        neighborhood_layout.addWidget(neighborhood_label)

        self.neighborhood_combo = QComboBox()
        self.neighborhood_combo.setMinimumWidth(160)
        self.neighborhood_combo.setStyleSheet(self._get_combo_style())
        self.neighborhood_combo.addItem(self.i18n.t("all"), "")
        self.neighborhood_combo.currentIndexChanged.connect(self._on_filter_changed)
        neighborhood_layout.addWidget(self.neighborhood_combo)
        filters_layout.addWidget(neighborhood_container)

        # Type filter
        type_container = QWidget()
        type_layout = QVBoxLayout(type_container)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.setSpacing(6)

        type_label = QLabel(self.i18n.t('building_type'))
        type_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt; font-weight: 600;")
        type_layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.setMinimumWidth(140)
        self.type_combo.setStyleSheet(self._get_combo_style())
        self.type_combo.addItem(self.i18n.t("all"), "")
        for code, en, ar in Vocabularies.BUILDING_TYPES:
            self.type_combo.addItem(en, code)
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        type_layout.addWidget(self.type_combo)
        filters_layout.addWidget(type_container)

        # Status filter
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)

        status_label = QLabel(self.i18n.t('status'))
        status_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt; font-weight: 600;")
        status_layout.addWidget(status_label)

        self.status_combo = QComboBox()
        self.status_combo.setMinimumWidth(140)
        self.status_combo.setStyleSheet(self._get_combo_style())
        self.status_combo.addItem(self.i18n.t("all"), "")
        for code, en, ar in Vocabularies.BUILDING_STATUS:
            self.status_combo.addItem(en, code)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        status_layout.addWidget(self.status_combo)
        filters_layout.addWidget(status_container)

        filters_layout.addStretch()

        # Clear filters button
        clear_btn = QPushButton(self.i18n.t("refresh"))
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Config.PRIMARY_COLOR};
                border: 1px solid {Config.PRIMARY_COLOR};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_LIGHT};
                color: white;
                border-color: {Config.PRIMARY_LIGHT};
            }}
        """)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_filters)
        filters_layout.addWidget(clear_btn, 0, Qt.AlignBottom)

        layout.addWidget(filters_frame)

        # Results count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        layout.addWidget(self.count_label)

        # Tabs for List and Map views (UC-000 S02a - list and/or map)
        self.view_tabs = QTabWidget()
        self.view_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: white;
                border-radius: 12px;
            }}
            QTabBar::tab {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                border: none;
                border-radius: 8px 8px 0 0;
                padding: 12px 24px;
                margin-right: 4px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: white;
                color: {Config.PRIMARY_COLOR};
                border-bottom: 3px solid {Config.PRIMARY_COLOR};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {Config.BACKGROUND_COLOR};
            }}
        """)

        # Table container (Tab 1)
        table_container = QFrame()
        table_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        table_shadow = QGraphicsDropShadowEffect()
        table_shadow.setBlurRadius(20)
        table_shadow.setColor(QColor(0, 0, 0, 20))
        table_shadow.setOffset(0, 4)
        table_container.setGraphicsEffect(table_shadow)

        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # Table
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
                border-radius: 12px;
                gridline-color: transparent;
            }}
            QTableView::item {{
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QTableView::item:hover {{
                background-color: #F8FAFC;
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                font-size: {Config.FONT_SIZE_LABEL}pt;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)
        self.table.doubleClicked.connect(self._on_row_double_click)

        # Enable context menu (UC-000 S02a - Edit/Delete/View)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Setup model
        self.table_model = BuildingsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        table_layout.addWidget(self.table)

        # Add table to first tab
        self.view_tabs.addTab(table_container, "📋 قائمة")

        # Map container (Tab 2 - UC-000 S02a - map selection)
        map_container = QFrame()
        map_container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        map_shadow = QGraphicsDropShadowEffect()
        map_shadow.setBlurRadius(20)
        map_shadow.setColor(QColor(0, 0, 0, 20))
        map_shadow.setOffset(0, 4)
        map_container.setGraphicsEffect(map_shadow)

        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE:
            self.map_view = QWebEngineView()
            self.map_view.setMinimumHeight(500)
            map_layout.addWidget(self.map_view)
        else:
            # Fallback message
            fallback_label = QLabel(
                "🗺️ الخريطة غير متاحة\n\n"
                "PyQtWebEngine غير مثبت\n"
                "استخدم تبويب 'قائمة' لعرض المباني"
            )
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setStyleSheet(f"""
                font-size: {Config.FONT_SIZE}pt;
                color: {Config.TEXT_LIGHT};
                padding: 80px;
            """)
            map_layout.addWidget(fallback_label)
            self.map_view = None

        self.view_tabs.addTab(map_container, "🗺️ خريطة")

        # Connect tab change to refresh map
        self.view_tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.view_tabs)

    def _get_combo_style(self):
        """Get consistent combobox styling."""
        return f"""
            QComboBox {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: {Config.FONT_SIZE}pt;
                min-height: 18px;
            }}
            QComboBox:hover {{
                border-color: {Config.PRIMARY_COLOR};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                selection-background-color: {Config.PRIMARY_LIGHT};
                selection-color: white;
            }}
        """

    def refresh(self, data=None):
        """Refresh the buildings list."""
        logger.debug("Refreshing buildings page")
        self._load_neighborhoods()
        self._load_buildings()

    def _load_neighborhoods(self):
        """Load neighborhoods into filter combo."""
        current = self.neighborhood_combo.currentData()

        self.neighborhood_combo.clear()
        self.neighborhood_combo.addItem(self.i18n.t("all"), "")

        neighborhoods = self.building_repo.get_neighborhoods()
        for n in neighborhoods:
            display = n["name_ar"] if self.i18n.is_arabic() else n["name"]
            self.neighborhood_combo.addItem(display, n["code"])

        if current:
            idx = self.neighborhood_combo.findData(current)
            if idx >= 0:
                self.neighborhood_combo.setCurrentIndex(idx)

    def _load_buildings(self):
        """Load buildings with current filters."""
        search = self.search_input.text().strip()
        neighborhood = self.neighborhood_combo.currentData()
        building_type = self.type_combo.currentData()
        status = self.status_combo.currentData()

        buildings = self.building_repo.search(
            neighborhood_code=neighborhood or None,
            building_type=building_type or None,
            building_status=status or None,
            search_text=search or None,
            limit=500
        )

        self.table_model.set_buildings(buildings)
        self.count_label.setText(f"تم العثور على {len(buildings)} مبنى")

        # Refresh map if on map tab
        if hasattr(self, 'view_tabs') and self.view_tabs.currentIndex() == 1:
            self._load_map()

    def _on_filter_changed(self):
        """Handle filter change."""
        self._load_buildings()

    def _on_tab_changed(self, index):
        """Handle tab change - load map when switching to map tab (UC-000 S02a)."""
        if index == 1:  # Map tab
            self._load_map()

    def _load_map(self):
        """Load buildings on interactive map (UC-000 S02a - map selection)."""
        if not HAS_WEBENGINE or not self.map_view:
            return

        # Get current filtered buildings
        buildings = self.table_model.get_all_buildings()
        geo_buildings = [b for b in buildings if b.latitude and b.longitude]

        # Generate GeoJSON
        features = []
        for b in geo_buildings:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [b.longitude, b.latitude]
                },
                "properties": {
                    "building_id": b.building_id,
                    "building_uuid": str(b.building_uuid) if b.building_uuid else "",
                    "neighborhood": b.neighborhood_name_ar or b.neighborhood_name or "",
                    "status": b.building_status or "intact",
                    "units": b.number_of_units or 0,
                    "type": b.building_type or ""
                }
            })

        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": features
        }, ensure_ascii=False)

        # Generate HTML
        html = self._get_map_html(geojson)
        self.map_view.setHtml(html)

    def _get_map_html(self, buildings_geojson: str) -> str:
        """Generate HTML for interactive buildings map with click-to-edit (UC-000 S02a)."""
        return f'''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة المباني</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ height: 100%; width: 100%; }}
        #map {{ height: 100%; width: 100%; }}
        .leaflet-popup-content-wrapper {{
            direction: rtl;
            text-align: right;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}
        .building-popup {{
            min-width: 220px;
        }}
        .building-popup h4 {{
            margin: 0 0 10px 0;
            color: #0072BC;
            font-size: 15px;
            font-weight: 700;
        }}
        .building-popup p {{
            margin: 6px 0;
            font-size: 13px;
            color: #333;
        }}
        .building-popup button {{
            background-color: #0072BC;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 8px;
            width: 100%;
        }}
        .building-popup button:hover {{
            background-color: #005a94;
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            color: white;
            font-weight: 600;
        }}
        .status-intact {{ background-color: #28a745; }}
        .status-minor_damage {{ background-color: #ffc107; color: #333; }}
        .status-major_damage {{ background-color: #fd7e14; }}
        .status-destroyed {{ background-color: #dc3545; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        // Initialize map centered on Aleppo
        var map = L.map('map').setView([36.2021, 37.1343], 13);

        // Add tile layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 18,
            attribution: '© OpenStreetMap | UN-Habitat'
        }}).addTo(map);

        // Status colors
        var statusColors = {{
            'intact': '#28a745',
            'minor_damage': '#ffc107',
            'major_damage': '#fd7e14',
            'destroyed': '#dc3545'
        }};

        var statusLabels = {{
            'intact': 'سليم',
            'minor_damage': 'ضرر طفيف',
            'major_damage': 'ضرر كبير',
            'destroyed': 'مدمر'
        }};

        // Buildings GeoJSON
        var buildingsData = {buildings_geojson};

        // Add buildings layer with click-to-edit (UC-000 S02a)
        var buildingsLayer = L.geoJSON(buildingsData, {{
            pointToLayer: function(feature, latlng) {{
                var status = feature.properties.status || 'intact';
                var color = statusColors[status] || '#0072BC';

                return L.circleMarker(latlng, {{
                    radius: 8,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.9
                }});
            }},
            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var status = props.status || 'intact';
                var statusLabel = statusLabels[status] || status;
                var statusClass = 'status-' + status;

                var popup = '<div class="building-popup">' +
                    '<h4>' + (props.building_id || 'مبنى') + '</h4>' +
                    '<p><strong>الحي:</strong> ' + (props.neighborhood || 'غير محدد') + '</p>' +
                    '<p><strong>الحالة:</strong> <span class="status-badge ' + statusClass + '">' + statusLabel + '</span></p>' +
                    '<p><strong>عدد الوحدات:</strong> ' + (props.units || 0) + '</p>' +
                    '<button onclick="editBuilding(\\'' + (props.building_uuid || '') + '\\')">✏️ تعديل المبنى</button>' +
                    '</div>';

                layer.bindPopup(popup);
            }}
        }}).addTo(map);

        // Fit to buildings if any
        if (buildingsData.features && buildingsData.features.length > 0) {{
            map.fitBounds(buildingsLayer.getBounds(), {{ padding: [50, 50] }});
        }}

        // Function to edit building (called from popup button - UC-000 S02a map selection)
        function editBuilding(buildingUuid) {{
            if (buildingUuid) {{
                // Send message to Python
                window.location.href = 'edit-building://' + buildingUuid;
            }}
        }}
    </script>
</body>
</html>
'''

    def _handle_map_url(self, url):
        """Handle URL clicks from map (UC-000 S02a - map selection to edit)."""
        url_str = url.toString()

        # Check for edit-building:// protocol
        if url_str.startswith('edit-building://'):
            building_uuid = url_str.replace('edit-building://', '')
            if building_uuid:
                # Find building by UUID
                building = self.building_repo.get_by_uuid(building_uuid)
                if building:
                    self._on_edit_building(building)
                else:
                    Toast.show_toast(self, "لم يتم العثور على المبنى", Toast.WARNING)

    def _clear_filters(self):
        """Clear all filters."""
        self.search_input.clear()
        self.neighborhood_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self._load_buildings()

    def _on_row_double_click(self, index):
        """Handle row double-click to edit building (UC-000 S02a)."""
        building = self.table_model.get_building(index.row())
        if building:
            self._on_edit_building(building)

    def _show_context_menu(self, position: QPoint):
        """Show context menu for table row (UC-000 S02a)."""
        index = self.table.indexAt(position)
        if not index.isValid():
            return

        building = self.table_model.get_building(index.row())
        if not building:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Config.PRIMARY_LIGHT};
                color: white;
            }}
        """)

        # View action
        view_action = QAction("👁 عرض التفاصيل", self)
        view_action.triggered.connect(lambda: self.view_building.emit(building.building_id))
        menu.addAction(view_action)

        # Edit action (UC-000 S02a)
        edit_action = QAction("✏️ تعديل", self)
        edit_action.triggered.connect(lambda: self._on_edit_building(building))
        menu.addAction(edit_action)

        menu.addSeparator()

        # Show on map action
        map_action = QAction("🗺️ عرض على الخريطة", self)
        map_action.triggered.connect(lambda: self._show_on_map(building))
        menu.addAction(map_action)

        menu.addSeparator()

        # Delete action
        delete_action = QAction("🗑️ حذف", self)
        delete_action.setStyleSheet("color: red;")
        delete_action.triggered.connect(lambda: self._on_delete_building(building))
        menu.addAction(delete_action)

        menu.exec_(self.table.viewport().mapToGlobal(position))

    def _show_on_map(self, building: Building):
        """Show building location on map."""
        if building.latitude and building.longitude:
            try:
                from ui.components.map_viewer_dialog import MapViewerDialog
                dialog = MapViewerDialog(
                    latitude=building.latitude,
                    longitude=building.longitude,
                    title=f"موقع المبنى: {building.building_id}",
                    parent=self
                )
                dialog.exec_()
            except ImportError:
                # Open in browser as fallback
                import webbrowser
                url = f"https://www.google.com/maps?q={building.latitude},{building.longitude}"
                webbrowser.open(url)
        else:
            Toast.show_toast(self, "لا تتوفر إحداثيات لهذا المبنى", Toast.WARNING)

    def _on_delete_building(self, building: Building):
        """Handle delete building with confirmation."""
        reply = QMessageBox.warning(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف المبنى {building.building_id}؟\n\n"
            "تحذير: سيتم حذف جميع الوحدات والمطالبات المرتبطة بهذا المبنى.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # Check for related claims
            from repositories.claim_repository import ClaimRepository
            claim_repo = ClaimRepository(self.db)
            related_claims = claim_repo.get_claims_for_building(building.building_uuid)

            if related_claims:
                reply2 = QMessageBox.warning(
                    self,
                    "تحذير: توجد مطالبات مرتبطة",
                    f"يوجد {len(related_claims)} مطالبة مرتبطة بهذا المبنى.\n\n"
                    "هل تريد المتابعة في الحذف؟",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply2 != QMessageBox.Yes:
                    return

            self.building_repo.delete(building.building_uuid)
            Toast.show_toast(self, f"تم حذف المبنى {building.building_id} بنجاح", Toast.SUCCESS)
            self._load_buildings()

        except Exception as e:
            logger.error(f"Failed to delete building: {e}")
            Toast.show_toast(self, f"فشل في حذف المبنى: {str(e)}", Toast.ERROR)

    def _on_export(self):
        """Handle export button click."""
        fmt = ExportDialog.get_format(self, self.i18n)
        if not fmt:
            return

        extension = "csv" if fmt == "csv" else "xlsx"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("export"),
            f"buildings_export.{extension}",
            f"{extension.upper()} Files (*.{extension})"
        )

        if not filename:
            return

        try:
            filters = {
                "neighborhood_code": self.neighborhood_combo.currentData() or None,
                "building_type": self.type_combo.currentData() or None,
                "building_status": self.status_combo.currentData() or None,
            }

            file_path = Path(filename)
            if fmt == "csv":
                result = self.export_service.export_buildings_csv(file_path, filters)
            else:
                result = self.export_service.export_buildings_excel(file_path, filters)

            Toast.show_toast(
                self,
                f"Exported {result['record_count']} buildings to {file_path.name}",
                Toast.SUCCESS
            )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            Toast.show_toast(self, f"Export failed: {str(e)}", Toast.ERROR)

    def _on_add_building(self):
        """Handle add building button (UC-000 S01, S02)."""
        dialog = BuildingDialog(self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            # Check for duplicate building_id
            existing = self.building_repo.get_by_id(data["building_id"])
            if existing:
                Toast.show_toast(self, f"المبنى برقم {data['building_id']} موجود مسبقاً", Toast.ERROR)
                return

            try:
                building = Building(**data)
                self.building_repo.create(building)
                Toast.show_toast(self, f"تم إضافة المبنى {building.building_id} بنجاح", Toast.SUCCESS)
                self._load_buildings()
            except Exception as e:
                logger.error(f"Failed to create building: {e}")
                Toast.show_toast(self, f"فشل في إضافة المبنى: {str(e)}", Toast.ERROR)

    def _on_edit_building(self, building: Building):
        """Handle edit building (UC-000 S02a)."""
        dialog = BuildingDialog(self.i18n, building=building, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                # Update building with new data
                for key, value in data.items():
                    if hasattr(building, key):
                        setattr(building, key, value)

                self.building_repo.update(building)
                Toast.show_toast(self, f"تم تحديث المبنى {building.building_id} بنجاح", Toast.SUCCESS)
                self._load_buildings()
            except Exception as e:
                logger.error(f"Failed to update building: {e}")
                Toast.show_toast(self, f"فشل في تحديث المبنى: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        self.table_model.set_language(is_arabic)
        self._load_neighborhoods()
