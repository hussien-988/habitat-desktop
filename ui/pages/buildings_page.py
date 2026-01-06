# -*- coding: utf-8 -*-
"""
Buildings list page with filters and table - Professional design.
"""

from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QFileDialog, QAbstractItemView, QGraphicsDropShadowEffect,
    QDialog, QFormLayout, QDoubleSpinBox, QSpinBox, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

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

        # Latitude
        self.latitude_spin = QDoubleSpinBox()
        self.latitude_spin.setRange(35.0, 38.0)  # Aleppo region
        self.latitude_spin.setDecimals(6)
        self.latitude_spin.setSingleStep(0.0001)
        self.latitude_spin.setSpecialValueText("غير محدد")
        self.latitude_spin.setValue(36.2)  # Aleppo default
        form.addRow("خط العرض:", self.latitude_spin)

        # Longitude
        self.longitude_spin = QDoubleSpinBox()
        self.longitude_spin.setRange(36.0, 39.0)  # Aleppo region
        self.longitude_spin.setDecimals(6)
        self.longitude_spin.setSingleStep(0.0001)
        self.longitude_spin.setSpecialValueText("غير محدد")
        self.longitude_spin.setValue(37.15)  # Aleppo default
        form.addRow("خط الطول:", self.longitude_spin)

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

        return {
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
            "latitude": self.latitude_spin.value(),
            "longitude": self.longitude_spin.value(),
        }


class BuildingsPage(QWidget):
    """Buildings list page with professional styling."""

    view_building = pyqtSignal(str)  # Emits building_id

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.export_service = ExportService(db)

        self._setup_ui()

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

        # Table container
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

        # Setup model
        self.table_model = BuildingsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        table_layout.addWidget(self.table)
        layout.addWidget(table_container)

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

    def _on_filter_changed(self):
        """Handle filter change."""
        self._load_buildings()

    def _clear_filters(self):
        """Clear all filters."""
        self.search_input.clear()
        self.neighborhood_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self._load_buildings()

    def _on_row_double_click(self, index):
        """Handle row double-click to view details."""
        building = self.table_model.get_building(index.row())
        if building:
            self.view_building.emit(building.building_id)

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

            Toast.show(
                self,
                f"Exported {result['record_count']} buildings to {file_path.name}",
                Toast.SUCCESS
            )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            Toast.show(self, f"Export failed: {str(e)}", Toast.ERROR)

    def _on_add_building(self):
        """Handle add building button (UC-000 S01, S02)."""
        dialog = BuildingDialog(self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            # Check for duplicate building_id
            existing = self.building_repo.get_by_id(data["building_id"])
            if existing:
                Toast.show(self, f"المبنى برقم {data['building_id']} موجود مسبقاً", Toast.ERROR)
                return

            try:
                building = Building(**data)
                self.building_repo.create(building)
                Toast.show(self, f"تم إضافة المبنى {building.building_id} بنجاح", Toast.SUCCESS)
                self._load_buildings()
            except Exception as e:
                logger.error(f"Failed to create building: {e}")
                Toast.show(self, f"فشل في إضافة المبنى: {str(e)}", Toast.ERROR)

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
                Toast.show(self, f"تم تحديث المبنى {building.building_id} بنجاح", Toast.SUCCESS)
                self._load_buildings()
            except Exception as e:
                logger.error(f"Failed to update building: {e}")
                Toast.show(self, f"فشل في تحديث المبنى: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        self.table_model.set_language(is_arabic)
        self._load_neighborhoods()
