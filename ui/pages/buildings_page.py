# -*- coding: utf-8 -*-
"""
Buildings page with modern UI design - QStackedWidget implementation.
"""

import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QFileDialog, QAbstractItemView, QGraphicsDropShadowEffect,
    QDialog, QDoubleSpinBox, QSpinBox, QMessageBox, QScrollArea,
    QMenu, QAction, QTabWidget, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QCursor

# Try to import WebEngine for map
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage, QWebEngineProfile
    from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from app.config import Config, Vocabularies, AleppoDivisions
from models.building import Building
from repositories.database import Database
from controllers.building_controller import BuildingController
from services.export_service import ExportService
from services.validation_service import ValidationService
from ui.components.toast import Toast
from ui.components.dialogs import ExportDialog
from ui.components.message_dialog import MessageDialog
from ui.components.custom_button import CustomButton
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


# Custom WebPage for console logging
if HAS_WEBENGINE:
    class DebugWebPage(QWebEnginePage):
        """Custom QWebEnginePage that logs console messages."""

        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
            """Log JavaScript console messages."""
            logger.info(f"JS [{level}]: {message} (line {lineNumber})")


# Tile request interceptor
if HAS_WEBENGINE:
    class BuildingsPageTileInterceptor(QWebEngineUrlRequestInterceptor):
        """Interceptor to add required headers for tile loading."""

        def interceptRequest(self, info):
            """Add required headers to tile requests."""
            info.setHttpHeader(b"Accept-Language", b"en-US,en;q=0.9,ar;q=0.8")
            info.setHttpHeader(b"User-Agent", b"UN-Habitat TRRCMS/1.0")


class AddBuildingPage(QWidget):
    """
    Add/Edit Building Form Page - 3 Cards Design
    """

    saved = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, building_controller, i18n, building=None, parent=None):
        super().__init__(parent)
        self.building_controller = building_controller
        self.i18n = i18n
        self.building = building
        self.validation_service = ValidationService()
        self._polygon_wkt = None

        self._setup_ui()

        if building:
            self._populate_data()

    def _setup_ui(self):
        """Setup the add/edit building UI with 3 cards."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(12)

        # الخلفية العامة
        self.setStyleSheet("background-color: #f4f7f9;")

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        # زر الرجوع (سهم بدون عنوان)
        back_btn = QPushButton("←")
        back_btn.setFixedSize(42, 42)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: none;
                border-radius: 6px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.cancelled.emit)
        back_btn.setToolTip("رجوع إلى قائمة المباني")
        header_layout.addWidget(back_btn)

        # معلومات العنوان (يمين)
        title_vbox = QVBoxLayout()
        title = QLabel("إضافة بناء جديد" if not self.building else "تعديل بناء")
        title.setStyleSheet("font-size: 26px; font-weight: bold; color: #1a2b3c; border: none;")

        breadcrumb = QLabel("المباني  •  إضافة بناء جديد")
        breadcrumb.setStyleSheet("color: #909399; font-size: 13px; border: none;")

        title_vbox.addWidget(title)
        title_vbox.addWidget(breadcrumb)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()

        # زر الحفظ (يسار)
        save_btn = CustomButton.success("حفظ", self, width=110, height=42, icon="✓")
        save_btn.clicked.connect(self._on_save)
        header_layout.addWidget(save_btn)

        layout.addLayout(header_layout)

        # === CARD 1: بيانات البناء ===
        card1 = QFrame()
        card1.setStyleSheet(self._get_card_style())
        card1_layout = QVBoxLayout(card1)
        card1_layout.setContentsMargins(20, 15, 20, 15)
        card1_layout.setSpacing(12)

        # رأس البطاقة
        card_header = QHBoxLayout()
        info_vbox = QVBoxLayout()
        info_title = QLabel("بيانات البناء")
        info_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #303133; border: none;")
        info_sub = QLabel("أدخل معلومات البناء والموقع الجغرافي")
        info_sub.setStyleSheet("color: #909399; font-size: 12px; border: none;")
        info_vbox.addWidget(info_title)
        info_vbox.addWidget(info_sub)

        icon_label = QLabel("🏢")
        icon_label.setFixedSize(45, 45)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background-color: #ecf5ff; border-radius: 22px; font-size: 20px; border: none;")

        card_header.addLayout(info_vbox)
        card_header.addStretch()
        card_header.addWidget(icon_label)
        card1_layout.addLayout(card_header)

        # شبكة الحقول - 5 في صف واحد
        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        # GG: رمز المحافظة (Governorate)
        self.governorate_combo = self._create_simple_field("محافظة", QComboBox(), "01")
        self.governorate_combo.addItem("حلب", "01")
        self.governorate_combo.currentIndexChanged.connect(self._update_building_id)
        self.governorate_combo.currentIndexChanged.connect(self._validate_building_id_realtime)
        fields_row.addWidget(self.governorate_combo._parent_container, 1)

        # DD: رمز المنطقة (District)
        self.district_combo = self._create_simple_field("مدينة", QComboBox(), "01")
        for code, name, name_ar in AleppoDivisions.DISTRICTS:
            self.district_combo.addItem(code, code)
        self.district_combo.currentIndexChanged.connect(self._update_building_id)
        self.district_combo.currentIndexChanged.connect(self._validate_building_id_realtime)
        fields_row.addWidget(self.district_combo._parent_container, 1)

        # SS: منطقة فرعية (Subdistrict) - ثابت 01
        self.subdistrict_code = self._create_simple_field("بلدة", QLineEdit(), "01")
        self.subdistrict_code.setText("01")
        self.subdistrict_code.setMaxLength(2)
        self.subdistrict_code.textChanged.connect(self._update_building_id)
        self.subdistrict_code.textChanged.connect(self._validate_building_id_realtime)
        fields_row.addWidget(self.subdistrict_code._parent_container, 1)

        # CCC: رمز المجتمع/المدينة (Community)
        self.community_code = self._create_simple_field("قرية", QLineEdit(), "001")
        self.community_code.setPlaceholderText("001")
        self.community_code.setMaxLength(3)
        self.community_code.textChanged.connect(self._update_building_id)
        self.community_code.textChanged.connect(self._validate_building_id_realtime)
        fields_row.addWidget(self.community_code._parent_container, 1)

        # NNN: رمز الحي/القرية (Neighborhood)
        self.neighborhood_combo = self._create_simple_field("حي", QComboBox(), "001")
        for code, name, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
            self.neighborhood_combo.addItem(code, code)
        self.neighborhood_combo.currentIndexChanged.connect(self._update_building_id)
        self.neighborhood_combo.currentIndexChanged.connect(self._validate_building_id_realtime)
        fields_row.addWidget(self.neighborhood_combo._parent_container, 1)

        # BBBBB: رقم البناء (Building Number)
        self.building_number = self._create_simple_field("رقم البناء", QLineEdit(), "00001")
        self.building_number.setPlaceholderText("00001")
        self.building_number.setMaxLength(5)
        self.building_number.textChanged.connect(self._update_building_id)
        self.building_number.textChanged.connect(self._validate_building_id_realtime)
        self.building_number.returnPressed.connect(self._validate_building_number_on_enter)
        fields_row.addWidget(self.building_number._parent_container, 1)

        card1_layout.addLayout(fields_row)

        # Warning label for duplicate building ID
        self.building_id_warning = QLabel("")
        self.building_id_warning.setAlignment(Qt.AlignCenter)
        self.building_id_warning.setStyleSheet("""
            color: #e74c3c;
            font-size: 12px;
            font-weight: bold;
            padding: 6px;
            background-color: #fee;
            border: 1px solid #fcc;
            border-radius: 4px;
            margin-top: 4px;
        """)
        self.building_id_warning.setWordWrap(True)
        self.building_id_warning.hide()
        card1_layout.addWidget(self.building_id_warning)

        # شريط الرمز النهائي
        self.building_id_label = QLabel("رمز البناء: 01-001-002-003-0001-01-01")
        self.building_id_label.setAlignment(Qt.AlignCenter)
        self.building_id_label.setFixedHeight(32)
        self.building_id_label.setStyleSheet("""
            background-color: #f0f7ff; color: #409eff;
            border: 1px solid #d9ecff; border-radius: 4px;
            font-weight: bold; margin-top: 8px; font-size: 13px;
        """)
        card1_layout.addWidget(self.building_id_label)

        layout.addWidget(card1)

        # === CARD 2: حالة البناء ===
        card2 = QFrame()
        card2.setStyleSheet(self._get_card_style())
        card2_layout = QHBoxLayout(card2)
        card2_layout.setContentsMargins(20, 12, 20, 12)
        card2_layout.setSpacing(15)

        # حالة البناء
        vbox_status = QVBoxLayout()
        vbox_status.setSpacing(6)
        lbl_status = QLabel("حالة البناء")
        lbl_status.setStyleSheet("font-size: 12px; color: #606266;")
        vbox_status.addWidget(lbl_status)
        self.status_combo = QComboBox()
        self.status_combo.addItem("اختر")
        for code, en, ar in Vocabularies.BUILDING_STATUS:
            self.status_combo.addItem(ar, code)
        self.status_combo.setFixedHeight(36)
        vbox_status.addWidget(self.status_combo)
        card2_layout.addLayout(vbox_status)

        # نوع البناء
        vbox_type = QVBoxLayout()
        vbox_type.setSpacing(6)
        lbl_type = QLabel("نوع البناء")
        lbl_type.setStyleSheet("font-size: 12px; color: #606266;")
        vbox_type.addWidget(lbl_type)
        self.type_combo = QComboBox()
        self.type_combo.addItem("اختر")
        for code, en, ar in Vocabularies.BUILDING_TYPES:
            self.type_combo.addItem(ar, code)
        self.type_combo.setFixedHeight(36)
        vbox_type.addWidget(self.type_combo)
        card2_layout.addLayout(vbox_type)

        # عدد الوحدات
        vbox_units = QVBoxLayout()
        vbox_units.setSpacing(6)
        lbl_units = QLabel("عدد الوحدات")
        lbl_units.setStyleSheet("font-size: 12px; color: #606266;")
        vbox_units.addWidget(lbl_units)
        self.apartments_spin = QSpinBox()
        self.apartments_spin.setFixedHeight(40)
        self.apartments_spin.setAlignment(Qt.AlignCenter)
        self.apartments_spin.setRange(0, 200)
        self.apartments_spin.setButtonSymbols(QSpinBox.PlusMinus)
        self.apartments_spin.setReadOnly(True)
        self.apartments_spin.setFocusPolicy(Qt.StrongFocus)
        self.apartments_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 14px;
                background: white;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: border;
                width: 32px;
                border-left: 1px solid #ddd;
                background: #3498db;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #2980b9;
            }
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background: #1f6ca0;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
                border-top-right-radius: 5px;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
                border-bottom-right-radius: 5px;
            }
            QSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 6px solid white;
            }
            QSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid white;
            }
        """)
        vbox_units.addWidget(self.apartments_spin)
        card2_layout.addLayout(vbox_units)

        # عدد المقاسم
        vbox_floors = QVBoxLayout()
        vbox_floors.setSpacing(6)
        lbl_floors = QLabel("عدد المقاسم")
        lbl_floors.setStyleSheet("font-size: 12px; color: #606266;")
        vbox_floors.addWidget(lbl_floors)
        self.floors_spin = QSpinBox()
        self.floors_spin.setFixedHeight(40)
        self.floors_spin.setAlignment(Qt.AlignCenter)
        self.floors_spin.setRange(1, 50)
        self.floors_spin.setValue(1)
        self.floors_spin.setButtonSymbols(QSpinBox.PlusMinus)
        self.floors_spin.setReadOnly(True)
        self.floors_spin.setFocusPolicy(Qt.StrongFocus)
        self.floors_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 14px;
                background: white;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: border;
                width: 32px;
                border-left: 1px solid #ddd;
                background: #3498db;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #2980b9;
            }
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background: #1f6ca0;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
                border-top-right-radius: 5px;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
                border-bottom-right-radius: 5px;
            }
            QSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 6px solid white;
            }
            QSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid white;
            }
        """)
        vbox_floors.addWidget(self.floors_spin)
        card2_layout.addLayout(vbox_floors)

        # عدد المحلات
        vbox_shops = QVBoxLayout()
        vbox_shops.setSpacing(6)
        lbl_shops = QLabel("عدد المحلات")
        lbl_shops.setStyleSheet("font-size: 12px; color: #606266;")
        vbox_shops.addWidget(lbl_shops)
        self.shops_spin = QSpinBox()
        self.shops_spin.setFixedHeight(40)
        self.shops_spin.setAlignment(Qt.AlignCenter)
        self.shops_spin.setRange(0, 50)
        self.shops_spin.setButtonSymbols(QSpinBox.PlusMinus)
        self.shops_spin.setReadOnly(True)
        self.shops_spin.setFocusPolicy(Qt.StrongFocus)
        self.shops_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 14px;
                background: white;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: border;
                width: 32px;
                border-left: 1px solid #ddd;
                background: #3498db;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #2980b9;
            }
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
                background: #1f6ca0;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
                border-top-right-radius: 5px;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
                border-bottom-right-radius: 5px;
            }
            QSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 6px solid white;
            }
            QSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid white;
            }
        """)
        vbox_shops.addWidget(self.shops_spin)
        card2_layout.addLayout(vbox_shops)

        layout.addWidget(card2)

        # === CARD 3: موقع البناء ===
        card3 = QFrame()
        card3.setStyleSheet(self._get_card_style())
        card3_layout = QVBoxLayout(card3)
        card3_layout.setContentsMargins(20, 15, 20, 15)
        card3_layout.setSpacing(12)

        title = QLabel("موقع البناء")
        title.setStyleSheet("font-weight: bold; margin-bottom: 10px; border: none;")
        card3_layout.addWidget(title)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        # الوصف العام
        vbox_gen = QVBoxLayout()
        lbl_gen = QLabel("الوصف العام")
        self.general_desc = QLineEdit()
        self.general_desc.setPlaceholderText("ادخل وصفاً عاماً...")
        self.general_desc.setFixedHeight(40)
        vbox_gen.addWidget(lbl_gen)
        vbox_gen.addWidget(self.general_desc)

        # وصف الموقع
        vbox_desc = QVBoxLayout()
        lbl_site = QLabel("وصف الموقع")
        self.site_desc = QLineEdit()
        self.site_desc.setPlaceholderText("ادخل وصفاً تفصيلياً...")
        self.site_desc.setFixedHeight(40)
        vbox_desc.addWidget(lbl_site)
        vbox_desc.addWidget(self.site_desc)

        # الخريطة - Container with coordinates above
        map_container = QWidget()
        map_container_layout = QVBoxLayout(map_container)
        map_container_layout.setContentsMargins(0, 0, 0, 0)
        map_container_layout.setSpacing(8)

        # Coordinates label (shows after selecting location) - ABOVE the map
        self.coordinates_label = QLabel("")
        self.coordinates_label.setStyleSheet("""
            color: #27ae60;
            font-size: 11px;
            font-weight: 600;
            padding: 2px;
        """)
        self.coordinates_label.setAlignment(Qt.AlignCenter)
        self.coordinates_label.setWordWrap(True)
        self.coordinates_label.hide()
        map_container_layout.addWidget(self.coordinates_label)

        # Map preview frame with actual Leaflet mini-map
        map_frame = QFrame()
        map_frame.setFixedSize(320, 100)
        map_frame.setStyleSheet("""
            QFrame {
                border-radius: 8px;
                border: 2px solid #3498db;
                background: white;
            }
        """)

        map_inner = QVBoxLayout(map_frame)
        map_inner.setContentsMargins(0, 0, 0, 0)
        map_inner.setSpacing(0)

        # Create mini Leaflet map preview
        if HAS_WEBENGINE:
            self.mini_map = QWebEngineView()
            self.mini_map.setFixedSize(316, 96)

            # Simple Leaflet HTML
            mini_map_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <style>
                    body { margin: 0; padding: 0; }
                    #map { width: 100%; height: 96px; }
                </style>
            </head>
            <body>
                <div id="map"></div>
                <script>
                    var map = L.map('map', {
                        zoomControl: false,
                        attributionControl: false,
                        dragging: false,
                        scrollWheelZoom: false,
                        doubleClickZoom: false,
                        boxZoom: false,
                        keyboard: false,
                        tap: false,
                        touchZoom: false
                    }).setView([36.2, 37.15], 13);

                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
                </script>
            </body>
            </html>
            """
            self.mini_map.setHtml(mini_map_html)
            map_inner.addWidget(self.mini_map)
        else:
            # Fallback: simple label
            fallback_label = QLabel("🗺️ خريطة")
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setStyleSheet("color: #3498db; font-size: 24px;")
            map_inner.addWidget(fallback_label)

        map_container_layout.addWidget(map_frame)

        # Map link button (below the map preview)
        map_btn = QPushButton("فتح الخريطة")
        map_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #3498db;
                text-decoration: underline;
                font-size: 13px;
                font-weight: 600;
                padding: 4px;
            }
            QPushButton:hover {
                color: #2980b9;
            }
        """)
        map_btn.setCursor(Qt.PointingHandCursor)
        map_btn.clicked.connect(self._on_pick_from_map)
        map_container_layout.addWidget(map_btn, alignment=Qt.AlignCenter)

        # Store lat/lon (hidden)
        self.latitude_spin = QDoubleSpinBox()
        self.latitude_spin.setRange(35.0, 38.0)
        self.latitude_spin.setDecimals(6)
        self.latitude_spin.setValue(36.2)
        self.latitude_spin.setVisible(False)

        self.longitude_spin = QDoubleSpinBox()
        self.longitude_spin.setRange(36.0, 39.0)
        self.longitude_spin.setDecimals(6)
        self.longitude_spin.setValue(37.15)
        self.longitude_spin.setVisible(False)

        self.location_status_label = QLabel("")
        self.geometry_type_label = QLabel("")

        body_layout.addLayout(vbox_gen)
        body_layout.addLayout(vbox_desc)
        body_layout.addWidget(map_container)

        card3_layout.addLayout(body_layout)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f56c6c; font-weight: 600; font-size: 10pt; border: none;")
        self.error_label.setWordWrap(True)
        card3_layout.addWidget(self.error_label)

        layout.addWidget(card3)
        layout.addStretch()

    def _get_card_style(self):
        """Get card stylesheet."""
        return """
            QFrame {
                background-color: white;
                border: 1px solid #e1e8ee;
                border-radius: 8px;
            }
            QLabel { border: none; color: #444; }
            QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 8px;
                background-color: #ffffff;
                color: #606266;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #606266;
                width: 0;
                height: 0;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
            }
        """

    def _create_simple_field(self, label_text, widget, placeholder=""):
        """Create a simple labeled field for grid layout."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 12px; color: #606266; border: none;")
        layout.addWidget(label)

        if isinstance(widget, QLineEdit):
            widget.setPlaceholderText(placeholder)
            widget.setFixedHeight(36)
            widget.setAlignment(Qt.AlignCenter)
        elif isinstance(widget, QComboBox):
            widget.setFixedHeight(36)

        layout.addWidget(widget)
        widget._parent_container = container
        return widget

    def _create_field_container(self, label_text, widget):
        """Create field container with label."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: 10pt;
            font-weight: 600;
        """)
        layout.addWidget(label)
        layout.addWidget(widget)

        return container

    def _create_field(self, label_text, widget):
        """Create a labeled field and return the widget (stores parent in widget)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: 10pt;
            font-weight: 600;
        """)
        layout.addWidget(label)

        # Style the widget
        if isinstance(widget, (QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox)):
            widget.setStyleSheet(f"""
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                    background-color: white;
                    border: 2px solid {Config.INPUT_BORDER};
                    border-radius: 6px;
                    padding: 10px 14px;
                    font-size: 10pt;
                }}
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                    border-color: {Config.PRIMARY_COLOR};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 30px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: white;
                    border: 1px solid {Config.BORDER_COLOR};
                    selection-background-color: {Config.PRIMARY_LIGHT};
                    selection-color: white;
                }}
            """)

        layout.addWidget(widget)
        widget._parent_container = container
        return widget

    def _update_building_id(self):
        """Generate building ID in format: GG-DD-SS-CCC-NNN-BBBBB"""
        # GG: Governorate (محافظة) - 2 digits
        gov = self.governorate_combo.currentData() or "01"

        # DD: District (منطقة) - 2 digits
        dist = self.district_combo.currentData() or "01"

        # SS: Subdistrict (منطقة فرعية) - 2 digits
        subdist = self.subdistrict_code.text().strip() or "01"

        # CCC: Community (مجتمع/مدينة) - 3 digits
        comm = self.community_code.text().strip() or "001"

        # NNN: Neighborhood (حي/قرية) - 3 digits
        neigh = self.neighborhood_combo.currentData() or "001"

        # BBBBB: Building Number - 5 digits
        bldg_num = self.building_number.text().strip().zfill(5)

        # Format: GG-DD-SS-CCC-NNN-BBBBB
        building_id = f"{gov}-{dist}-{subdist}-{comm}-{neigh}-{bldg_num}"
        self.building_id_label.setText(f"رمز البناء: {building_id}")

    def _validate_building_number_on_enter(self):
        """Validate building number when user presses Enter."""
        building_num = self.building_number.text().strip()

        if len(building_num) < 5:
            from ui.components.message_dialog import MessageDialog
            MessageDialog.warning(self, "خطأ في الإدخال", "رقم البناء يجب أن يتكون من 5 خانات")
            self.building_number.setFocus()
            return

        # If valid length, move to next field
        self.building_number.clearFocus()

    def _validate_building_id_realtime(self):
        """Validate building ID in real-time as user types the building number."""
        # Only validate if user has entered 5 digits (complete building number)
        building_num = self.building_number.text().strip()

        if len(building_num) != 5:
            self.building_id_warning.hide()
            return

        # Generate the complete building ID
        gov = self.governorate_combo.currentData() or "01"
        dist = self.district_combo.currentData() or "01"
        subdist = self.subdistrict_code.text().strip() or "01"
        comm = self.community_code.text().strip() or "001"
        neigh = self.neighborhood_combo.currentData() or "001"
        bldg_num = building_num.zfill(5)

        building_id = f"{gov}-{dist}-{subdist}-{comm}-{neigh}-{bldg_num}"

        # Check if this building ID already exists in the database
        # Skip check if we're editing an existing building with this ID
        if self.building and self.building.building_id == building_id:
            self.building_id_warning.hide()
            return

        # Use controller to check existence
        result = self.building_controller.get_building(building_id)

        if result.success and result.data:
            self.building_id_warning.setText("⚠️ هذا البناء موجود بالفعل")
            self.building_id_warning.show()
        else:
            self.building_id_warning.hide()

    def _update_total_units(self):
        """Update total units."""
        total = self.apartments_spin.value() + self.shops_spin.value()
        self.units_label.setText(str(total))

    def _on_pick_from_map(self):
        """Open map picker - V2 unified design (matches BuildingMapWidget)."""
        try:
            from ui.components.map_picker_dialog_v2 import show_map_picker_dialog

            # Use unified map picker with consistent design (DRY BEST PRACTICE!)
            result = show_map_picker_dialog(
                initial_lat=self.latitude_spin.value(),
                initial_lon=self.longitude_spin.value(),
                allow_polygon=True,
                db=self.building_controller.db,  # Pass DB to show buildings!
                parent=self
            )

            if result:
                self.latitude_spin.setValue(result["latitude"])
                self.longitude_spin.setValue(result["longitude"])

                # Show coordinates in the label above the map button
                lat = result["latitude"]
                lon = result["longitude"]
                self.coordinates_label.setText(f"✓ الإحداثيات: {lat:.6f}, {lon:.6f}")
                self.coordinates_label.show()

                if result.get("polygon_wkt"):
                    self._polygon_wkt = result["polygon_wkt"]
                    self.geometry_type_label.setText("نوع الإحداثيات: مضلع")
                    self.location_status_label.setText("✓ تم تحديد الموقع من الخريطة")
                else:
                    self._polygon_wkt = None
                    self.geometry_type_label.setText("نوع الإحداثيات: نقطة")
                    self.location_status_label.setText("✓ تم تحديد الموقع")

                self.location_status_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;")

        except ImportError:
            QMessageBox.information(self, "اختيار الموقع", "يرجى إدخال الإحداثيات يدوياً.")

    def _populate_data(self):
        """Populate form with existing building data."""
        if not self.building:
            return

        # GG: تحميل رمز المحافظة (Governorate)
        if hasattr(self.building, 'governorate_code') and self.building.governorate_code:
            idx = self.governorate_combo.findData(self.building.governorate_code)
            if idx >= 0:
                self.governorate_combo.setCurrentIndex(idx)

        # DD: تحميل رمز المنطقة (District)
        idx = self.district_combo.findData(self.building.district_code)
        if idx >= 0:
            self.district_combo.setCurrentIndex(idx)

        # SS: تحميل المنطقة الفرعية (Subdistrict)
        if hasattr(self.building, 'subdistrict_code') and self.building.subdistrict_code:
            self.subdistrict_code.setText(self.building.subdistrict_code)

        # CCC: تحميل رمز المجتمع/المدينة (Community)
        if hasattr(self.building, 'community_code') and self.building.community_code:
            self.community_code.setText(self.building.community_code)

        # NNN: تحميل رمز الحي/القرية (Neighborhood)
        idx = self.neighborhood_combo.findData(self.building.neighborhood_code)
        if idx >= 0:
            self.neighborhood_combo.setCurrentIndex(idx)

        # BBBBB: تحميل رقم البناء (Building Number - آخر 5 أرقام من building_id)
        if self.building.building_id and len(self.building.building_id) >= 5:
            bldg_num = self.building.building_id[-5:]
            self.building_number.setText(bldg_num)

        # تحميل نوع البناء
        idx = self.type_combo.findData(self.building.building_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        # تحميل حالة البناء
        idx = self.status_combo.findData(self.building.building_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        # تحميل الأعداد
        self.floors_spin.setValue(self.building.number_of_floors or 1)
        self.apartments_spin.setValue(self.building.number_of_apartments or 0)
        self.shops_spin.setValue(self.building.number_of_shops or 0)

        # تحميل الأوصاف
        if hasattr(self.building, 'general_description') and self.building.general_description:
            self.general_desc.setText(self.building.general_description)
        if hasattr(self.building, 'site_description') and self.building.site_description:
            self.site_desc.setText(self.building.site_description)

        # تحميل الإحداثيات
        if self.building.latitude:
            self.latitude_spin.setValue(self.building.latitude)
            self.location_status_label.setText("✓ تم تحديد الموقع")
            self.location_status_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;")
        if self.building.longitude:
            self.longitude_spin.setValue(self.building.longitude)

        # تحميل المضلع إذا كان موجود
        if hasattr(self.building, 'geo_location') and self.building.geo_location:
            self._polygon_wkt = self.building.geo_location
            self.geometry_type_label.setText("نوع الإحداثيات: مضلع")

        # تحديث رمز البناء
        self._update_building_id()

    def _show_validation_error_dialog(self, errors):
        """عرض نافذة خطأ واضحة للتحقق من البيانات."""
        dialog = QDialog(self)
        dialog.setWindowTitle("خطأ في البيانات")
        dialog.setFixedSize(500, 280)
        dialog.setStyleSheet("""
            QDialog {
                background-color: white;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # أيقونة الخطأ
        icon_label = QLabel("❌")
        icon_label.setStyleSheet("font-size: 52px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # العنوان
        title = QLabel("بيانات غير صحيحة")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e74c3c;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # قائمة الأخطاء
        errors_text = "\n".join([f"• {error}" for error in errors])
        message = QLabel(errors_text)
        message.setStyleSheet("font-size: 14px; color: #555; line-height: 1.6;")
        message.setAlignment(Qt.AlignRight)
        message.setWordWrap(True)
        layout.addWidget(message)

        layout.addStretch()

        # زر موافق
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("موافق")
        ok_btn.setFixedSize(120, 42)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

        dialog.exec_()

    def _show_duplicate_error_dialog(self, building_id):
        """عرض نافذة خطأ واضحة لرقم البناء المكرر - حسب مواصفات FSD."""
        dialog = QDialog(self)
        dialog.setWindowTitle("رقم مكرر")
        dialog.setFixedSize(520, 300)
        dialog.setStyleSheet("""
            QDialog {
                background-color: white;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        # أيقونة الخطأ
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 52px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # العنوان - حسب FSD: E003 Duplicate
        title = QLabel("رقم مكرر")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e67e22;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # الرسالة - واضحة ومحددة
        message = QLabel(
            f"<div style='text-align: right; line-height: 1.8;'>"
            f"<p style='font-size: 15px; margin-bottom: 10px;'>"
            f"المبنى برقم <b style='color: #e67e22; font-size: 16px;'>{building_id}</b> موجود مسبقاً في النظام."
            f"</p>"
            f"<p style='font-size: 13px; color: #7f8c8d;'>"
            f"<b>الحل:</b> راجع السجل الموجود أو قم بتعديل رمز البناء."
            f"</p>"
            f"<p style='font-size: 12px; color: #95a5a6; margin-top: 8px;'>"
            f"رمز الخطأ: E003 - Duplicate Building ID"
            f"</p>"
            f"</div>"
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        layout.addStretch()

        # الأزرار
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # زر مراجعة السجل
        review_btn = QPushButton("مراجعة السجل الموجود")
        review_btn.setFixedSize(170, 42)
        review_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        review_btn.clicked.connect(lambda: self._review_existing_building(building_id, dialog))
        btn_layout.addWidget(review_btn)

        btn_layout.addSpacing(10)

        # زر موافق
        ok_btn = QPushButton("موافق")
        ok_btn.setFixedSize(100, 42)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

        dialog.exec_()

    def _review_existing_building(self, building_id, dialog):
        """فتح السجل الموجود للمراجعة."""
        dialog.accept()
        # إغلاق نافذة الإضافة والعودة للقائمة
        self.cancelled.emit()
        # يمكن إضافة منطق للبحث عن البناء وعرضه

    def _on_save(self):
        """Validate and save."""
        data = self.get_data()

        result = self.validation_service.validate_building(data)

        if not result.is_valid:
            # عرض رسائل الخطأ في نافذة واضحة
            self._show_validation_error_dialog(result.errors)
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

        try:
            if self.building:
                # Update - use controller
                result = self.building_controller.update_building(
                    self.building.building_uuid,
                    data
                )

                if result.success:
                    Toast.show_toast(self.window(), f"تم تحديث المبنى {self.building.building_id} بنجاح", Toast.SUCCESS)
                    self.saved.emit()
                else:
                    error_msg = result.message
                    if hasattr(result, 'validation_errors') and result.validation_errors:
                        error_msg += "\n" + "\n".join(result.validation_errors)
                    self._show_validation_error_dialog([error_msg])
            else:
                # Create - use controller
                result = self.building_controller.create_building(data)

                if result.success:
                    building = result.data
                    Toast.show_toast(self.window(), f"تم إضافة المبنى {building.building_id} بنجاح", Toast.SUCCESS)
                    self.saved.emit()
                else:
                    error_msg = result.message
                    if hasattr(result, 'validation_errors') and result.validation_errors:
                        error_msg += "\n" + "\n".join(result.validation_errors)

                    # Check if it's duplicate error
                    if "already exists" in error_msg or "موجود" in error_msg:
                        self._show_duplicate_error_dialog(data['building_id'])
                    else:
                        self._show_validation_error_dialog([error_msg])

        except Exception as e:
            logger.error(f"Failed to save building: {e}")
            self._show_validation_error_dialog([f"فشل في حفظ المبنى: {str(e)}"])

    def get_data(self):
        """Get form data."""
        dist_idx = self.district_combo.currentIndex()
        neigh_idx = self.neighborhood_combo.currentIndex()

        # استخراج building_id من الـ label (بعد "رمز البناء: ")
        building_id_text = self.building_id_label.text()
        if ":" in building_id_text:
            building_id = building_id_text.split(":", 1)[1].strip()
        else:
            building_id = building_id_text.strip()

        data = {
            "building_id": building_id,
            # GG: Governorate
            "governorate_code": self.governorate_combo.currentData(),
            "governorate_name": "Aleppo",
            "governorate_name_ar": "حلب",
            # DD: District
            "district_code": self.district_combo.currentData(),
            "district_name": AleppoDivisions.DISTRICTS[dist_idx][1] if dist_idx >= 0 else "",
            "district_name_ar": AleppoDivisions.DISTRICTS[dist_idx][2] if dist_idx >= 0 else "",
            # SS: Subdistrict
            "subdistrict_code": self.subdistrict_code.text().strip() or "01",
            "subdistrict_name": "",
            "subdistrict_name_ar": "",
            # CCC: Community
            "community_code": self.community_code.text().strip() or "001",
            "community_name": "",
            "community_name_ar": "",
            # NNN: Neighborhood
            "neighborhood_code": self.neighborhood_combo.currentData(),
            "neighborhood_name": AleppoDivisions.NEIGHBORHOODS_ALEPPO[neigh_idx][1] if neigh_idx >= 0 else "",
            "neighborhood_name_ar": AleppoDivisions.NEIGHBORHOODS_ALEPPO[neigh_idx][2] if neigh_idx >= 0 else "",
            # BBBBB: Building Number
            "building_number": self.building_number.text().strip(),
            # Building Details
            "building_type": self.type_combo.currentData(),
            "building_status": self.status_combo.currentData(),
            "number_of_floors": self.floors_spin.value(),
            "number_of_apartments": self.apartments_spin.value(),
            "number_of_shops": self.shops_spin.value(),
            "number_of_units": self.apartments_spin.value() + self.shops_spin.value(),
            # Coordinates
            "latitude": self.latitude_spin.value() if self.latitude_spin.value() != 0 else None,
            "longitude": self.longitude_spin.value() if self.longitude_spin.value() != 0 else None,
            # Note: general_description and site_description are UI-only fields, not saved to Building model
        }

        if self._polygon_wkt:
            data["geo_location"] = self._polygon_wkt

        return data


class BuildingsListPage(QWidget):
    """
    Buildings List Page with Table
    """

    view_building = pyqtSignal(str)
    edit_building = pyqtSignal(object)
    add_building = pyqtSignal()
    prepare_field_work = pyqtSignal()

    def __init__(self, building_controller, export_service, i18n, parent=None):
        super().__init__(parent)
        self.building_controller = building_controller
        self.export_service = export_service
        self.i18n = i18n
        self.map_view = None
        self._buildings = []  # Store buildings list
        self._current_page = 1
        self._rows_per_page = 11
        self._total_pages = 1

        self._setup_ui()

    def _setup_ui(self):
        """Setup buildings list UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # سطر العنوان والأزرار - المباني على اليسار والأزرار على اليمين
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # العنوان + حقل البحث
        title_search_layout = QHBoxLayout()
        title_search_layout.setSpacing(25)

        title = QLabel("المباني")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #333;")
        title_search_layout.addWidget(title)

        # حقل البحث الناعم (بدون بوردر - فقط خط سفلي)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 البحث في المباني...")
        self.search_input.setFixedWidth(280)
        self.search_input.setFixedHeight(40)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                border-bottom: 2px solid #ddd;
                background: transparent;
                padding: 8px 12px;
                font-size: 14px;
                color: #333;
            }
            QLineEdit:focus {
                border-bottom: 2px solid #3498db;
                outline: none;
            }
            QLineEdit::placeholder {
                color: #999;
            }
        """)
        title_search_layout.addWidget(self.search_input)

        # ربط البحث بالتغييرات الفورية
        self.search_input.textChanged.connect(self._on_search_text_changed)

        # الأزرار
        btn_layout = QHBoxLayout()

        # زر تجهيز العمل الميداني (شفاف مع بوردر أزرق)
        btn_field = CustomButton.secondary("تجهيز العمل الميداني", self, width=180, height=45)
        btn_field.clicked.connect(self.prepare_field_work.emit)

        # زر إضافة بناء جديد (أزرق solid)
        btn_add = CustomButton.primary("إضافة بناء جديد", self, width=160, height=45, icon="+")
        btn_add.clicked.connect(self.add_building.emit)

        btn_layout.addWidget(btn_field)
        btn_layout.addWidget(btn_add)

        top_row.addLayout(title_search_layout)
        top_row.addStretch()
        top_row.addLayout(btn_layout)

        layout.addLayout(top_row)

        # البطاقة البيضاء للجدول
        table_card = QFrame()
        table_card.setStyleSheet("background-color: white; border-radius: 12px;")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setRowCount(11)  # Fixed 11 rows
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setHorizontalHeaderLabels(["رمز البناء", "تاريخ الادخال", "المنطقة", "نوع البناء", "حالة البناء", ""])

        # Disable scroll bars
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ستايل الجدول الاحترافي
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setStyleSheet("""
            QTableWidget { border: none; background-color: white; }
            QTableWidget::item { padding: 15px; border-bottom: 1px solid #f0f0f0; color: #555; }
            QHeaderView::section {
                background-color: white; padding: 12px; border: none;
                border-bottom: 2px solid #f0f0f0; color: #888; font-weight: bold; font-size: 13px;
            }
        """)

        # ضبط المحاذاة والعرض
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.verticalHeader().setVisible(False)

        # Enable cell click for actions button
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_click)

        card_layout.addWidget(self.table)

        # التذييل
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 10, 20, 10)
        dense_label = QLabel("Dense")
        self.page_label = QLabel("Rows per page: 11  |  1-11 of 11")
        self.page_label.setStyleSheet("color: #666;")

        footer.addWidget(dense_label)
        footer.addStretch()
        footer.addWidget(self.page_label)

        # أزرار التنقل بين الصفحات
        self.pagination_container = QWidget()
        pagination_layout = QHBoxLayout(self.pagination_container)
        pagination_layout.setContentsMargins(0, 0, 0, 0)
        pagination_layout.setSpacing(5)

        # سيتم إنشاء الأزرار ديناميكياً في _update_pagination()
        self.page_buttons = []

        footer.addWidget(self.pagination_container)

        card_layout.addLayout(footer)

        layout.addWidget(table_card)

    def showEvent(self, event):
        """تحميل البيانات تلقائياً عند عرض الصفحة"""
        super().showEvent(event)
        # تحميل البيانات تلقائياً عند فتح الصفحة
        self.refresh()

    def refresh(self):
        """Refresh list."""
        logger.debug("Refreshing buildings list")
        self._load_buildings()

    def _load_buildings(self, search_text: str = ""):
        """Load buildings from repository and populate table.

        Args:
            search_text: Optional search text to filter buildings
        """
        # Load buildings with search filter using controller
        if search_text:
            result = self.building_controller.search_buildings(search_text)
        else:
            result = self.building_controller.load_buildings()

        if result.success:
            all_buildings = result.data
        else:
            logger.error(f"Failed to load buildings: {result.message}")
            all_buildings = []

        self._buildings = all_buildings  # Store for later access

        # Calculate pagination
        total = len(all_buildings)
        self._total_pages = (total + self._rows_per_page - 1) // self._rows_per_page if total > 0 else 1

        # Get buildings for current page
        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + self._rows_per_page, total)
        page_buildings = all_buildings[start_idx:end_idx]

        # Clear all table cells
        for row in range(11):
            for col in range(6):
                self.table.setItem(row, col, QTableWidgetItem(""))

        # Populate table with current page data
        for idx, building in enumerate(page_buildings):
            # رمز البناء
            self.table.setItem(idx, 0, QTableWidgetItem(building.building_id or ""))

            # تاريخ الادخال
            date_str = building.created_at.strftime("%d/%m/%Y") if building.created_at else ""
            self.table.setItem(idx, 1, QTableWidgetItem(date_str))

            # المنطقة
            area = f"{building.neighborhood_name_ar or building.neighborhood_name or ''}"
            if building.district_name_ar:
                area = f"{building.district_name_ar} - {area}"
            self.table.setItem(idx, 2, QTableWidgetItem(area))

            # نوع البناء
            building_type = ""
            for code, en, ar in Vocabularies.BUILDING_TYPES:
                if code == building.building_type:
                    building_type = ar
                    break
            self.table.setItem(idx, 3, QTableWidgetItem(building_type))

            # حالة البناء
            building_status = ""
            for code, en, ar in Vocabularies.BUILDING_STATUS:
                if code == building.building_status:
                    building_status = ar
                    break
            self.table.setItem(idx, 4, QTableWidgetItem(building_status))

            # زر الثلاث نقاط
            actions_item = QTableWidgetItem("⋮")
            actions_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 5, actions_item)

        # Update pagination info
        if total > 0:
            self.page_label.setText(f"Rows per page: 11  |  {start_idx + 1}-{end_idx} of {total}")
        else:
            self.page_label.setText("Rows per page: 11  |  0-0 of 0")

        # Update pagination buttons
        self._update_pagination()

    def _on_search_text_changed(self, text: str):
        """Handle search input changes with smart filtering."""
        search_query = text.strip()

        # Reset to first page when searching
        self._current_page = 1

        # Reload buildings with search filter
        self._load_buildings(search_text=search_query)

        logger.debug(f"Search: '{search_query}' -> {len(self._buildings)} results")

    def _update_pagination(self):
        """Update pagination buttons."""
        # Clear existing buttons
        layout = self.pagination_container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.page_buttons = []

        # Create page buttons (1, 2, 3, 4...)
        for page_num in range(1, self._total_pages + 1):
            btn = QPushButton(str(page_num))
            btn.setFixedSize(35, 35)

            if page_num == self._current_page:
                # Current page - highlighted
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                """)
            else:
                # Other pages
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: white;
                        color: #666;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        font-weight: normal;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #f0f0f0;
                    }
                """)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, p=page_num: self._go_to_page(p))

            layout.addWidget(btn)
            self.page_buttons.append(btn)

    def _go_to_page(self, page_num):
        """Go to specific page."""
        if 1 <= page_num <= self._total_pages:
            self._current_page = page_num
            self._load_buildings()

    def _on_cell_double_click(self, row, col):
        """Handle cell double click."""
        # Calculate actual building index
        start_idx = (self._current_page - 1) * self._rows_per_page
        building_idx = start_idx + row

        if building_idx < len(self._buildings):
            building = self._buildings[building_idx]
            self.edit_building.emit(building)

    def _on_cell_clicked(self, row: int, col: int):
        """فتح القائمة المنسدلة عند الضغط على زر الثلاث نقاط."""
        # التحقق من أن المستخدم ضغط على عمود الإجراءات (آخر عمود)
        if col != 5:
            return

        # التحقق من وجود محتوى في السطر
        building_id_item = self.table.item(row, 0)
        if not building_id_item or not building_id_item.text().strip():
            return

        # حساب index البناء الفعلي
        start_idx = (self._current_page - 1) * self._rows_per_page
        building_idx = start_idx + row

        if building_idx >= len(self._buildings):
            return

        building = self._buildings[building_idx]

        # إظهار القائمة المنسدلة
        self._show_actions_menu(row, col, building)

    def _show_actions_menu(self, row: int, col: int, building: Building):
        """عرض القائمة المنسدلة تحت زر الثلاث نقاط."""
        # الحصول على موقع الخلية
        item = self.table.item(row, col)
        if not item:
            return

        rect = self.table.visualItemRect(item)
        position = QPoint(rect.right() - 10, rect.bottom())

        # إنشاء القائمة
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 10px 30px 10px 20px;
                border-radius: 4px;
                font-size: 13px;
                color: #333;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e0e0e0;
                margin: 4px 8px;
            }
        """)

        # عرض التفاصيل
        view_action = QAction("👁  عرض التفاصيل", self)
        view_action.triggered.connect(lambda: self.view_building.emit(building.building_id))
        menu.addAction(view_action)

        # تعديل
        edit_action = QAction("✏️  تعديل البناء", self)
        edit_action.triggered.connect(lambda: self.edit_building.emit(building))
        menu.addAction(edit_action)

        menu.addSeparator()

        # عرض على الخريطة
        map_action = QAction("🗺️  عرض على الخريطة", self)
        map_action.triggered.connect(lambda: self._show_on_map(building))
        menu.addAction(map_action)

        menu.addSeparator()

        # حذف
        delete_action = QAction("🗑️  حذف البناء", self)
        delete_action.triggered.connect(lambda: self._on_delete_building(building))
        menu.addAction(delete_action)

        # عرض القائمة تحت زر الثلاث نقاط
        menu.exec_(self.table.viewport().mapToGlobal(position))

    def _show_on_map(self, building: Building):
        """Show on map."""
        if building.latitude and building.longitude:
            from ui.components.map_picker_dialog import MapPickerDialog
            dialog = MapPickerDialog.get_instance(
                initial_lat=building.latitude,
                initial_lon=building.longitude,
                allow_polygon=False,
                read_only=True,
                highlight_location=True,
                parent=self
            )
            dialog.setWindowTitle(f"موقع المبنى: {building.building_id}")
            dialog.exec_()
        else:
            Toast.show_toast(self, "لا تتوفر إحداثيات لهذا المبنى", Toast.WARNING)

    def _on_delete_building(self, building: Building):
        """Delete building with confirmation dialog."""
        # تأكيد الحذف
        if not MessageDialog.confirm(
            self,
            "تأكيد الحذف",
            f"سيتم حذف المبنى <b>{building.building_id}</b><br>"
            "هذا الإجراء لا يمكن التراجع عنه.",
            ok_text="حذف",
            cancel_text="إلغاء"
        ):
            return

        try:
            # التحقق من وجود مطالبات مرتبطة
            from repositories.claim_repository import ClaimRepository
            from repositories.database import Database
            db = Database.get_instance()
            claim_repo = ClaimRepository(db)
            related_claims = claim_repo.get_claims_for_building(building.building_uuid)

            if related_claims:
                if not MessageDialog.confirm(
                    self,
                    "تحذير: توجد مطالبات مرتبطة",
                    f"يوجد <b>{len(related_claims)}</b> مطالبة مرتبطة بهذا المبنى.<br><br>"
                    "هل تريد المتابعة في الحذف؟",
                    ok_text="متابعة الحذف",
                    cancel_text="إلغاء"
                ):
                    return

            # حذف المبنى باستخدام controller
            result = self.building_controller.delete_building(building.building_uuid)

            if result.success:
                Toast.show_toast(self, f"تم حذف المبنى {building.building_id} بنجاح", Toast.SUCCESS)
                self._load_buildings()
            else:
                raise Exception(result.message)

        except Exception as e:
            logger.error(f"Failed to delete building: {e}")
            error_msg = str(e).lower()

            # رسالة واضحة حسب نوع الخطأ
            if "foreign key constraint failed" in error_msg or "constraint" in error_msg:
                MessageDialog.error(
                    self,
                    "لا يمكن حذف المبنى",
                    f"المبنى <b>{building.building_id}</b> مرتبط ببيانات أخرى<br>"
                    "(وحدات، مطالبات، أو وثائق)<br><br>"
                    "يجب حذف البيانات المرتبطة أولاً"
                )
            else:
                MessageDialog.error(
                    self,
                    "خطأ في الحذف",
                    f"حدث خطأ أثناء حذف المبنى:<br>{str(e)}"
                )

    def update_language(self, is_arabic: bool):
        """Update language."""
        # Reload buildings to update language
        self._load_buildings()


class BuildingsPage(QWidget):
    """
    Main Buildings Page - QStackedWidget container
    """

    view_building = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_controller = BuildingController(db)
        self.export_service = ExportService(db)

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stacked widget
        self.stacked = QStackedWidget()

        # Page 0: List
        self.list_page = BuildingsListPage(
            self.building_controller,
            self.export_service,
            self.i18n,
            self
        )
        self.list_page.view_building.connect(self.view_building.emit)
        self.list_page.edit_building.connect(self._on_edit_building)
        self.list_page.add_building.connect(self._on_add_building)
        self.list_page.prepare_field_work.connect(self._on_prepare_field_work)
        self.stacked.addWidget(self.list_page)

        # Page 1: Add/Edit (created on demand)
        self.form_page = None

        # Page 2: Field Work Preparation (created on demand)
        self.field_work_page = None

        layout.addWidget(self.stacked)

    def refresh(self, data=None):
        """Refresh."""
        logger.debug("Refreshing buildings page")
        self.list_page.refresh()
        self.stacked.setCurrentIndex(0)

    def _on_add_building(self):
        """Add building."""
        if self.form_page:
            self.stacked.removeWidget(self.form_page)
            self.form_page.deleteLater()

        self.form_page = AddBuildingPage(
            self.building_controller,
            self.i18n,
            building=None,
            parent=self
        )
        self.form_page.saved.connect(self._on_form_saved)
        self.form_page.cancelled.connect(self._on_form_cancelled)
        self.stacked.addWidget(self.form_page)
        self.stacked.setCurrentWidget(self.form_page)

    def _on_edit_building(self, building: Building):
        """Edit building."""
        if self.form_page:
            self.stacked.removeWidget(self.form_page)
            self.form_page.deleteLater()

        self.form_page = AddBuildingPage(
            self.building_controller,
            self.i18n,
            building=building,
            parent=self
        )
        self.form_page.saved.connect(self._on_form_saved)
        self.form_page.cancelled.connect(self._on_form_cancelled)
        self.stacked.addWidget(self.form_page)
        self.stacked.setCurrentWidget(self.form_page)

    def _on_prepare_field_work(self):
        """Open field work preparation wizard."""
        if self.field_work_page:
            self.stacked.removeWidget(self.field_work_page)
            self.field_work_page.deleteLater()

        from ui.pages.field_work_preparation_page import FieldWorkPreparationStep1
        self.field_work_page = FieldWorkPreparationStep1(
            self.building_controller,
            self.i18n,
            parent=self
        )
        self.field_work_page.next_clicked.connect(self._on_field_work_next)
        self.field_work_page.cancelled.connect(self._on_field_work_cancelled)
        self.stacked.addWidget(self.field_work_page)
        self.stacked.setCurrentWidget(self.field_work_page)

    def _on_field_work_next(self):
        """Handle field work next step."""
        # TODO: Navigate to next step
        logger.debug("Field work next step")

    def _on_field_work_cancelled(self):
        """Handle field work cancellation."""
        self.stacked.setCurrentWidget(self.list_page)

    def _on_form_saved(self):
        """Form saved."""
        self.list_page.refresh()
        self.stacked.setCurrentWidget(self.list_page)

    def _on_form_cancelled(self):
        """Form cancelled."""
        self.stacked.setCurrentWidget(self.list_page)

    def update_language(self, is_arabic: bool):
        """Update language."""
        self.list_page.update_language(is_arabic)
