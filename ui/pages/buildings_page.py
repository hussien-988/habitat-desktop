# -*- coding: utf-8 -*-
"""
Buildings page with modern UI design - QStackedWidget implementation.
"""

import json
from pathlib import Path
from typing import Optional, Tuple
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QTableView, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QFileDialog, QAbstractItemView, QGraphicsDropShadowEffect,
    QDialog, QDoubleSpinBox, QSpinBox, QMessageBox, QScrollArea,
    QMenu, QAction, QTabWidget, QStackedWidget, QStyleOptionHeader, QStyle
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize, QLocale
from PyQt5.QtGui import QColor, QCursor, QPainter, QFont, QIcon, QPixmap

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
from ui.components.primary_button import PrimaryButton
from ui.design_system import PageDimensions, Colors, ButtonDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
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
        # ✅ FIX: Wrap content in scroll area to show all cards including radio buttons
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create scroll area for the form content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # Container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        # Apply unified padding from PageDimensions (DRY principle)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 32px
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            PageDimensions.CONTENT_PADDING_V_BOTTOM  # Bottom: 0px
        )
        layout.setSpacing(12)

        # Background color from Figma via StyleManager (DRY principle)
        container.setStyleSheet(StyleManager.page_background())

        # Header - matching wizard style (DRY: Using design system constants)
        title_row = QHBoxLayout()
        title_row.setSpacing(16)
        title_row.setContentsMargins(0, 0, 0, 0)

        # Title/Subtitle container (vertical) - RIGHT SIDE
        title_subtitle_container = QVBoxLayout()
        title_subtitle_container.setSpacing(4)

        # Title: "إضافة بناء جديد" or "تعديل بناء"
        # Figma: Desktop/H4 24px = 18pt Bold (DRY: Using FontManager)
        title_label = QLabel("إضافة بناء جديد" if not self.building else "تعديل بناء")
        title_font = create_font(
            size=FontManager.SIZE_TITLE,  # 18pt (24px Figma)
            weight=QFont.Bold,
            letter_spacing=0
        )
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none; background: transparent;")
        title_subtitle_container.addWidget(title_label)

        # Subtitle: "المباني  •  إضافة بناء جديد"
        # Desktop/Body2 (DRY: Using FontManager)
        subtitle_layout = QHBoxLayout()
        subtitle_layout.setSpacing(8)
        subtitle_layout.setContentsMargins(0, 0, 0, 0)

        subtitle_part1 = QLabel("المباني")
        subtitle_font = create_font(
            size=FontManager.SIZE_BODY,  # 9pt (12px Figma)
            weight=QFont.Normal,
            letter_spacing=0
        )
        subtitle_part1.setFont(subtitle_font)
        subtitle_part1.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        subtitle_layout.addWidget(subtitle_part1)

        # Dot separator
        dot_label = QLabel("•")
        dot_label.setFont(subtitle_font)
        dot_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        subtitle_layout.addWidget(dot_label)

        # Part 2
        subtitle_part2 = QLabel("إضافة بناء جديد" if not self.building else "تعديل بناء")
        subtitle_part2.setFont(subtitle_font)
        subtitle_part2.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        subtitle_layout.addWidget(subtitle_part2)

        subtitle_layout.addStretch()
        title_subtitle_container.addLayout(subtitle_layout)

        title_row.addLayout(title_subtitle_container)
        title_row.addStretch()

        # Close button (X) - LEFT SIDE FIRST (DRY: Using ButtonDimensions and Colors)
        # Figma specs: 52×48px, White background
        close_btn = QPushButton("✕")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(ButtonDimensions.CLOSE_WIDTH, ButtonDimensions.CLOSE_HEIGHT)

        close_btn_font = create_font(
            size=ButtonDimensions.CLOSE_FONT_SIZE,
            weight=QFont.Normal,
            letter_spacing=0
        )
        close_btn.setFont(close_btn_font)

        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {ButtonDimensions.CLOSE_BORDER_RADIUS}px;
                padding: {ButtonDimensions.CLOSE_PADDING_V}px {ButtonDimensions.CLOSE_PADDING_H}px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BACKGROUND_LIGHT};
            }}
        """)
        close_btn.clicked.connect(self.cancelled.emit)
        title_row.addWidget(close_btn)

        # Save button with icon - LEFT SIDE SECOND (DRY: Using ButtonDimensions)
        # Figma specs: 114×48px
        save_btn = QPushButton(" حفظ")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)

        # Load save icon
        import os
        save_icon_path = os.path.join("assets", "images", "save.png")
        if os.path.exists(save_icon_path):
            save_btn.setIcon(QIcon(save_icon_path))
            save_btn.setIconSize(QSize(ButtonDimensions.SAVE_ICON_SIZE, ButtonDimensions.SAVE_ICON_SIZE))

        save_btn_font = create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=QFont.Normal,
            letter_spacing=0
        )
        save_btn.setFont(save_btn_font)

        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                padding: {ButtonDimensions.SAVE_PADDING_V}px {ButtonDimensions.SAVE_PADDING_H}px;
                border-radius: {ButtonDimensions.SAVE_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
                icon-size: {ButtonDimensions.SAVE_ICON_SIZE}px;
            }}
            QPushButton:hover {{
                background-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        title_row.addWidget(save_btn)

        layout.addLayout(title_row)

        # مسافة بعد الهيدر قبل الكاردات
        layout.addSpacing(24)

        # === CARD 1: بيانات البناء ===
        # DRY: Using same card style as wizard (building_selection_step.py)
        card1 = QFrame()
        card1.setObjectName("buildingCard")
        card1.setStyleSheet("""
            QFrame#buildingCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)

        card1_layout = QVBoxLayout(card1)
        # Padding: 12px from all sides (matching wizard - DRY principle)
        card1_layout.setContentsMargins(12, 12, 12, 12)
        # No default spacing - we'll control gaps manually for precision
        card1_layout.setSpacing(0)

        # Header (title + subtitle) - DRY: Same structure as wizard
        card_header = QHBoxLayout()
        card_header.setSpacing(8)

        # Icon FIRST (left side in RTL) - DRY: Using Icon.load_pixmap
        from ui.components.icon import Icon
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)  # Wizard spec: 40×40px
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        # Load blue.png icon (DRY: reusing wizard's icon loading pattern)
        icon_pixmap = Icon.load_pixmap("blue", size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        else:
            # Fallback if image not found
            icon_label.setText("🏢")
            icon_label.setStyleSheet(icon_label.styleSheet() + "font-size: 16px;")

        card_header.addWidget(icon_label)

        # Text column (title + subtitle) SECOND (right side in RTL)
        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(1)

        # Title: "بيانات البناء" - DRY: Using create_font and Colors
        info_title = QLabel("بيانات البناء")
        # Title: 14px from Figma = 10pt, weight 600, color WIZARD_TITLE (matching wizard)
        info_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        info_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Subtitle: "ادخل معلومات البناء والموقع الجغرافي"
        # Changed from "ابحث عن" to "ادخل" as requested
        info_sub = QLabel("ادخل معلومات البناء والموقع الجغرافي")
        # Subtitle: 14px from Figma = 10pt, weight 400, color WIZARD_SUBTITLE (matching wizard)
        info_sub.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        info_sub.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        header_text_col.addWidget(info_title)
        header_text_col.addWidget(info_sub)

        card_header.addLayout(header_text_col)
        card_header.addStretch(1)

        card1_layout.addLayout(card_header)

        # Gap: 12px between header and fields (matching wizard - DRY principle)
        card1_layout.addSpacing(12)

        # شبكة الحقول - 6 في صف واحد (بدون containers)
        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        # Shared label font (DRY: same as card title)
        label_font = create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD)

        # Shared input style (DRY: background #F8FAFF, border-radius 8px, height 45px)
        input_style = """
            QLineEdit {
                background-color: #F8FAFF;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                padding: 8px 12px;
                color: #606266;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #3890DF;
            }
        """

        # Field 1: رمز المحافظة (Governorate)
        gov_container = QVBoxLayout()
        gov_container.setSpacing(6)
        gov_label = QLabel("رمز المحافظة")
        gov_label.setFont(label_font)
        gov_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.governorate_combo = QLineEdit()
        self.governorate_combo.setText("01")
        self.governorate_combo.setMaxLength(2)
        self.governorate_combo.setStyleSheet(input_style)
        self.governorate_combo.setFixedHeight(45)  # توحيد الارتفاع
        self.governorate_combo.setAlignment(Qt.AlignRight)  # محاذاة لليمين
        self.governorate_combo.textChanged.connect(self._update_building_id)
        self.governorate_combo.textChanged.connect(self._validate_building_id_realtime)
        gov_container.addWidget(gov_label)
        gov_container.addWidget(self.governorate_combo)
        fields_row.addLayout(gov_container, 1)

        # Field 2: رمز المنطقة (District)
        dist_container = QVBoxLayout()
        dist_container.setSpacing(6)
        dist_label = QLabel("رمز المنطقة")
        dist_label.setFont(label_font)
        dist_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.district_combo = QLineEdit()
        self.district_combo.setText("01")
        self.district_combo.setMaxLength(2)
        self.district_combo.setStyleSheet(input_style)
        self.district_combo.setFixedHeight(45)  # توحيد الارتفاع
        self.district_combo.setAlignment(Qt.AlignRight)  # محاذاة لليمين
        self.district_combo.textChanged.connect(self._update_building_id)
        self.district_combo.textChanged.connect(self._validate_building_id_realtime)
        dist_container.addWidget(dist_label)
        dist_container.addWidget(self.district_combo)
        fields_row.addLayout(dist_container, 1)

        # Field 3: رمز البلدة (Subdistrict)
        sub_container = QVBoxLayout()
        sub_container.setSpacing(6)
        sub_label = QLabel("رمز البلدة")
        sub_label.setFont(label_font)
        sub_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.subdistrict_code = QLineEdit()
        self.subdistrict_code.setText("01")
        self.subdistrict_code.setMaxLength(2)
        self.subdistrict_code.setStyleSheet(input_style)
        self.subdistrict_code.setFixedHeight(45)  # توحيد الارتفاع
        self.subdistrict_code.setAlignment(Qt.AlignRight)  # محاذاة لليمين
        self.subdistrict_code.textChanged.connect(self._update_building_id)
        self.subdistrict_code.textChanged.connect(self._validate_building_id_realtime)
        sub_container.addWidget(sub_label)
        sub_container.addWidget(self.subdistrict_code)
        fields_row.addLayout(sub_container, 1)

        # Field 4: رمز القرية (Community)
        comm_container = QVBoxLayout()
        comm_container.setSpacing(6)
        comm_label = QLabel("رمز القرية")
        comm_label.setFont(label_font)
        comm_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.community_code = QLineEdit()
        self.community_code.setPlaceholderText("001")
        self.community_code.setMaxLength(3)
        self.community_code.setStyleSheet(input_style)
        self.community_code.setFixedHeight(45)  # توحيد الارتفاع
        self.community_code.setAlignment(Qt.AlignRight)  # محاذاة لليمين
        self.community_code.textChanged.connect(self._update_building_id)
        self.community_code.textChanged.connect(self._validate_building_id_realtime)
        comm_container.addWidget(comm_label)
        comm_container.addWidget(self.community_code)
        fields_row.addLayout(comm_container, 1)

        # Field 5: رمز الحي (Neighborhood)
        neigh_container = QVBoxLayout()
        neigh_container.setSpacing(6)
        neigh_label = QLabel("رمز الحي")
        neigh_label.setFont(label_font)
        neigh_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        self.neighborhood_code_input = QLineEdit()
        self.neighborhood_code_input.setPlaceholderText("001")
        self.neighborhood_code_input.setMaxLength(3)
        self.neighborhood_code_input.setStyleSheet(input_style)
        self.neighborhood_code_input.setFixedHeight(45)
        self.neighborhood_code_input.setAlignment(Qt.AlignRight)

        self.neighborhood_code_input.textChanged.connect(self._update_building_id)
        self.neighborhood_code_input.textChanged.connect(self._validate_building_id_realtime)

        neigh_container.addWidget(neigh_label)
        neigh_container.addWidget(self.neighborhood_code_input)
        fields_row.addLayout(neigh_container, 1)

        # Field 6: رمز البناء (Building Number)
        build_container = QVBoxLayout()
        build_container.setSpacing(6)
        build_label = QLabel("رمز البناء")
        build_label.setFont(label_font)
        build_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.building_number = QLineEdit()
        self.building_number.setPlaceholderText("00001")
        self.building_number.setMaxLength(5)
        self.building_number.setStyleSheet(input_style)
        self.building_number.setFixedHeight(45)  # توحيد الارتفاع
        self.building_number.setAlignment(Qt.AlignRight)  # محاذاة لليمين
        self.building_number.textChanged.connect(self._update_building_id)
        self.building_number.textChanged.connect(self._validate_building_id_realtime)
        self.building_number.returnPressed.connect(self._validate_building_number_on_enter)
        build_container.addWidget(build_label)
        build_container.addWidget(self.building_number)
        fields_row.addLayout(build_container, 1)

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
        card2_layout.setContentsMargins(12, 12, 12, 12)  # توحيد padding مع الكاردات الأخرى
        card2_layout.setSpacing(15)

        # Shared label font for card 2 (DRY: same as card 1)
        card2_label_font = create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD)

        # Shared combobox style (نسخة طبق الأصل 100% من unit_dialog.py - فقط الارتفاع 45px)
        combo_style = """
            QComboBox {
                padding: 6px 40px 6px 12px;
                padding-right: 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 14px;
                font-weight: 600;
                color: #9CA3AF;
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
                border-left-width: 0px;
                margin-left: 5px;
            }
            QComboBox::down-arrow {
                image: url(assets/images/v.png);
                width: 12px;
                height: 12px;
                border: none;
                border-width: 0px;
            }
            QComboBox QAbstractItemView {
                font-size: 14px;
            }
        """

        # حالة البناء
        vbox_status = QVBoxLayout()
        vbox_status.setSpacing(6)
        lbl_status = QLabel("حالة البناء")
        lbl_status.setFont(card2_label_font)
        lbl_status.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_status.addWidget(lbl_status)
        self.status_combo = QComboBox()
        self.status_combo.addItem("اختر")
        for code, en, ar in Vocabularies.BUILDING_STATUS:
            self.status_combo.addItem(ar, code)
        self.status_combo.setStyleSheet(combo_style)
        self.status_combo.setFixedHeight(45)  # توحيد الارتفاع مع باقي الحقول
        self.status_combo.setLayoutDirection(Qt.RightToLeft)  # محاذاة لليمين
        vbox_status.addWidget(self.status_combo)
        card2_layout.addLayout(vbox_status, 1)  # توحيد العرض - stretch factor

        # نوع البناء
        vbox_type = QVBoxLayout()
        vbox_type.setSpacing(6)
        lbl_type = QLabel("نوع البناء")
        lbl_type.setFont(card2_label_font)
        lbl_type.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_type.addWidget(lbl_type)
        self.type_combo = QComboBox()
        self.type_combo.addItem("اختر")
        for code, en, ar in Vocabularies.BUILDING_TYPES:
            self.type_combo.addItem(ar, code)
        self.type_combo.setStyleSheet(combo_style)
        self.type_combo.setFixedHeight(45)  # توحيد الارتفاع مع باقي الحقول
        self.type_combo.setLayoutDirection(Qt.RightToLeft)  # محاذاة لليمين
        vbox_type.addWidget(self.type_combo)
        card2_layout.addLayout(vbox_type, 1)  # توحيد العرض - stretch factor

        # عدد الوحدات (DRY: using _create_spinbox_with_arrows)
        vbox_units = QVBoxLayout()
        vbox_units.setSpacing(6)
        lbl_units = QLabel("عدد الوحدات")
        lbl_units.setFont(card2_label_font)
        lbl_units.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_units.addWidget(lbl_units)
        self.apartments_spin = QSpinBox()
        self.apartments_spin.setRange(0, 200)
        self.apartments_spin.setValue(0)
        self.apartments_spin.setAlignment(Qt.AlignRight)
        self.apartments_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.apartments_spin.setButtonSymbols(QSpinBox.NoButtons)
        apartments_widget = self._create_spinbox_with_arrows(self.apartments_spin)
        vbox_units.addWidget(apartments_widget)
        card2_layout.addLayout(vbox_units, 1)  # توحيد العرض - stretch factor

        # عدد المقاسم (DRY: using _create_spinbox_with_arrows)
        vbox_floors = QVBoxLayout()
        vbox_floors.setSpacing(6)
        lbl_floors = QLabel("عدد المقاسم")
        lbl_floors.setFont(card2_label_font)
        lbl_floors.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_floors.addWidget(lbl_floors)
        self.floors_spin = QSpinBox()
        self.floors_spin.setRange(1, 50)
        self.floors_spin.setValue(1)
        self.floors_spin.setAlignment(Qt.AlignRight)
        self.floors_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.floors_spin.setButtonSymbols(QSpinBox.NoButtons)
        floors_widget = self._create_spinbox_with_arrows(self.floors_spin)
        vbox_floors.addWidget(floors_widget)
        card2_layout.addLayout(vbox_floors, 1)  # توحيد العرض - stretch factor

        # عدد المحلات (DRY: using _create_spinbox_with_arrows)
        vbox_shops = QVBoxLayout()
        vbox_shops.setSpacing(6)
        lbl_shops = QLabel("عدد المحلات")
        lbl_shops.setFont(card2_label_font)
        lbl_shops.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_shops.addWidget(lbl_shops)
        self.shops_spin = QSpinBox()
        self.shops_spin.setRange(0, 50)
        self.shops_spin.setValue(0)
        self.shops_spin.setAlignment(Qt.AlignRight)
        self.shops_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.shops_spin.setButtonSymbols(QSpinBox.NoButtons)
        shops_widget = self._create_spinbox_with_arrows(self.shops_spin)
        vbox_shops.addWidget(shops_widget)
        card2_layout.addLayout(vbox_shops, 1)  # توحيد العرض - stretch factor

        layout.addWidget(card2)

        # === CARD 3: موقع البناء === (DRY: نفس تنسيق building_selection_step.py بالضبط)
        card3 = QFrame()
        card3.setStyleSheet(self._get_card_style())
        card3_layout = QVBoxLayout(card3)
        card3_layout.setContentsMargins(12, 12, 12, 12)
        card3_layout.setSpacing(0)  # Manual spacing control

        # Row 1: Header only - "موقع البناء"
        header = QLabel("موقع البناء")
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card3_layout.addWidget(header)

        # Gap: 12px between header and content
        card3_layout.addSpacing(12)

        # Row 2: Three equal sections with 24px gap between them
        content_row = QHBoxLayout()
        content_row.setSpacing(24)  # Gap: 24px between sections

        # Section 1: Map (left)
        map_section = QVBoxLayout()
        map_section.setSpacing(4)  # Same spacing as other sections

        # Empty label for alignment (same height as other sections' labels)
        map_label = QLabel("")  # Empty to maintain alignment
        map_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        map_label.setFixedHeight(16)  # Same as label height
        map_section.addWidget(map_label)

        # Map container (QLabel to support QPixmap)
        map_container = QLabel()
        map_container.setFixedSize(400, 130)  # Width: 400px, Height: 130px (from Figma)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("mapContainer")

        # Load background map image using Icon component (absolute paths)
        from ui.components.icon import Icon

        # Try to load map image (image-40.png or map-placeholder.png)
        map_bg_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_bg_pixmap or map_bg_pixmap.isNull():
            # Fallback to map-placeholder
            map_bg_pixmap = Icon.load_pixmap("map-placeholder", size=None)

        if map_bg_pixmap and not map_bg_pixmap.isNull():
            # Scale to exact size while maintaining quality
            scaled_bg = map_bg_pixmap.scaled(400, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            map_container.setPixmap(scaled_bg)

        # Styling with border-radius (works with QLabel)
        map_container.setStyleSheet(f"""
            QLabel#mapContainer {{
                background-color: #E8E8E8;
                border-radius: 8px;
            }}
        """)

        # White button in top-left corner
        map_button = QPushButton(map_container)
        map_button.setFixedSize(94, 20)  # Width: 94px, Height: 20px (from Figma)
        map_button.move(8, 8)  # Position in top-left corner with small margin
        map_button.setCursor(Qt.PointingHandCursor)

        # Icon: pill.png
        icon_pixmap = Icon.load_pixmap("pill", size=12)
        if icon_pixmap and not icon_pixmap.isNull():
            map_button.setIcon(QIcon(icon_pixmap))
            map_button.setIconSize(QSize(12, 12))

        # Text: "فتح الخريطة" - 12px Figma = 9pt PyQt5
        map_button.setText("فتح الخريطة")
        map_button.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))

        # DRY: Using Colors.PRIMARY_BLUE
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
            }}
        """)

        # Apply shadow effect
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(shadow)

        map_button.clicked.connect(self._on_pick_from_map)

        # Location icon in center of map
        location_icon = QLabel(map_container)
        location_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if location_pixmap and not location_pixmap.isNull():
            location_icon.setPixmap(location_pixmap)
            location_icon.setFixedSize(56, 56)
            # Position in center: (400-56)/2 = 172, (130-56)/2 = 37
            location_icon.move(172, 37)
            location_icon.setStyleSheet("background: transparent;")
        else:
            # Fallback: use text emoji
            location_icon.setText("📍")
            location_icon.setFont(create_font(size=32, weight=FontManager.WEIGHT_REGULAR))
            location_icon.setStyleSheet("background: transparent;")
            location_icon.setAlignment(Qt.AlignCenter)
            location_icon.setFixedSize(56, 56)
            location_icon.move(172, 37)

        map_section.addWidget(map_container)

        # Polygon-only mode
        geometry_type_row = QHBoxLayout()
        geometry_type_row.setSpacing(12)
        geometry_type_row.setContentsMargins(0, 8, 0, 0)

        geometry_label = QLabel("نوع الموقع:")
        geometry_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        geometry_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        geometry_type_row.addWidget(geometry_label)

        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.geometry_button_group = QButtonGroup(self)

        # Point radio hidden
        self.point_radio = QRadioButton("نقطة (GPS)")
        self.point_radio.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.point_radio.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.point_radio.setChecked(False)
        self.point_radio.setVisible(False)
        self.geometry_button_group.addButton(self.point_radio, 1)

        self.polygon_radio = QRadioButton("مضلع (Polygon)")
        self.polygon_radio.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.polygon_radio.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.polygon_radio.setChecked(True)
        self.geometry_button_group.addButton(self.polygon_radio, 2)
        geometry_type_row.addWidget(self.polygon_radio)

        geometry_type_row.addStretch()
        map_section.addLayout(geometry_type_row)

        map_section.addStretch(1)  # Push content to top

        content_row.addLayout(map_section, stretch=1)

        # Section 2: وصف الموقع (center) - QLineEdit for input
        section_location = QVBoxLayout()
        section_location.setSpacing(4)

        lbl_location = QLabel("وصف الموقع")
        lbl_location.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl_location.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        self.site_desc = QTextEdit()
        self.site_desc.setPlaceholderText("ادخل وصفاً تفصيلياً...")
        self.site_desc.setFixedHeight(130)  # نفس ارتفاع الخريطة
        self.site_desc.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFF;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                padding: 8px 12px;
                color: #606266;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 1px solid #3890DF;
            }
        """)

        section_location.addWidget(lbl_location)
        section_location.addWidget(self.site_desc)
        section_location.addStretch(1)  # Push content to top

        content_row.addLayout(section_location, stretch=1)

        # Section 3: الوصف العام (right) - QLineEdit for input
        section_general = QVBoxLayout()
        section_general.setSpacing(4)

        lbl_general = QLabel("الوصف العام")
        lbl_general.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl_general.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        self.general_desc = QTextEdit()
        self.general_desc.setPlaceholderText("ادخل وصفاً عاماً...")
        self.general_desc.setFixedHeight(130)  # نفس ارتفاع الخريطة
        self.general_desc.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFF;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                padding: 8px 12px;
                color: #606266;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 1px solid #3890DF;
            }
        """)

        section_general.addWidget(lbl_general)
        section_general.addWidget(self.general_desc)
        section_general.addStretch(1)  # Push content to top

        content_row.addLayout(section_general, stretch=1)

        card3_layout.addLayout(content_row)

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

        layout.addWidget(card3)
        layout.addStretch()

        # ✅ FIX: Set container in scroll area and add to main layout
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

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
        gov = self.governorate_combo.text().strip() or "01"

        # DD: District (منطقة) - 2 digits
        dist = self.district_combo.text().strip() or "01"

        # SS: Subdistrict (منطقة فرعية) - 2 digits
        subdist = self.subdistrict_code.text().strip() or "01"

        # CCC: Community (مجتمع/مدينة) - 3 digits
        comm = self.community_code.text().strip() or "001"

        # NNN: Neighborhood - 3 digits
        neigh = self.neighborhood_code_input.text().strip() or "001"

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
        gov = self.governorate_combo.text().strip() or "01"
        dist = self.district_combo.text().strip() or "01"
        subdist = self.subdistrict_code.text().strip() or "01"
        comm = self.community_code.text().strip() or "001"
        neigh = self.neighborhood_code_input.text().strip() or "001"
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

    def _get_auth_token(self) -> Optional[str]:
        """
        Get auth token from main window.

        Helper method for auth token retrieval.

        Returns:
            Auth token string or None
        """
        try:
            main_window = self.window()
            if hasattr(main_window, 'current_user') and main_window.current_user:
                return getattr(main_window.current_user, '_api_token', None)
        except Exception as e:
            logger.warning(f"Could not get auth token: {e}")
        return None

    def _get_status_color(self, status: str) -> str:
        """
        Get marker color based on building status.

        Args:
            status: Building status key (intact, minor_damage, etc.)

        Returns:
            Hex color code for the status
        """
        status_colors = {
            'intact': '#28a745',           # Green
            'minor_damage': '#ffc107',     # Yellow
            'major_damage': '#fd7e14',     # Orange
            'severely_damaged': '#dc3545', # Red
            'destroyed': '#dc3545',        # Red
            'under_construction': '#17a2b8', # Cyan
            'demolished': '#6c757d'        # Gray
        }
        return status_colors.get(status, '#0072BC')  # Default: Blue

    def _calculate_area_center(self, district_code: str = None, neighborhood_code: str = None):
        """
        Calculate map center and zoom based on district/neighborhood code.

        Smart focus: Uses building data to calculate bbox for the specified area.

        Args:
            district_code: District code (e.g., "01")
            neighborhood_code: Neighborhood code (e.g., "001")

        Returns:
            Tuple[float, float, int]: (center_lat, center_lon, zoom)
        """
        try:
            # Build filter for area
            from controllers.building_controller import BuildingFilter

            filter_params = BuildingFilter(limit=100)  # Sample size for bbox calculation

            # Filter by district/neighborhood if provided
            if neighborhood_code and neighborhood_code.strip():
                filter_params.neighborhood_code = neighborhood_code.strip()
                logger.info(f"Calculating center for neighborhood: {neighborhood_code}")
            elif district_code and district_code.strip():
                filter_params.district_code = district_code.strip()
                logger.info(f"Calculating center for district: {district_code}")
            else:
                # No filter - use default
                logger.info("No area specified, using default center (Aleppo)")
                return 36.2021, 37.1343, 13

            # Fetch buildings in area
            result = self.building_controller.load_buildings(filter_params)

            if result.success and result.data and len(result.data) > 0:
                buildings = result.data

                # Calculate bbox from buildings
                lats = [b.latitude for b in buildings if b.latitude]
                lons = [b.longitude for b in buildings if b.longitude]

                if lats and lons:
                    min_lat, max_lat = min(lats), max(lats)
                    min_lon, max_lon = min(lons), max(lons)

                    # Center of bbox
                    center_lat = (min_lat + max_lat) / 2
                    center_lon = (min_lon + max_lon) / 2

                    # Calculate zoom based on bbox size
                    lat_diff = max_lat - min_lat
                    lon_diff = max_lon - max_lon

                    # Heuristic zoom calculation
                    if lat_diff < 0.01 or lon_diff < 0.01:
                        zoom = 15  # Small area (neighborhood)
                    elif lat_diff < 0.05 or lon_diff < 0.05:
                        zoom = 14  # Medium area (district)
                    else:
                        zoom = 13  # Large area

                    logger.info(f"Area center calculated: ({center_lat:.6f}, {center_lon:.6f}) zoom={zoom}")
                    logger.info(f"   Based on {len(buildings)} buildings in area")
                    return center_lat, center_lon, zoom

            # Fallback: No buildings found in area
            logger.warning(f"No buildings found in specified area, using default center")
            return 36.2021, 37.1343, 13

        except Exception as e:
            logger.error(f"Failed to calculate area center: {e}")
            # Fallback to default
            return 36.2021, 37.1343, 13

    def _on_pick_from_map(self):
        """
        Open map picker to select building location.

        No validation required - user can open map at any time.
        Uses existing coordinates or defaults to Aleppo center.
        Buildings are saved to Backend Database (PostgreSQL).
        """
        try:
            from ui.components.map_picker_dialog_v2 import MapPickerDialog

            if self.latitude_spin.value() != 0 and self.longitude_spin.value() != 0:
                initial_lat = self.latitude_spin.value()
                initial_lon = self.longitude_spin.value()
                initial_zoom = 16
                logger.info(f"Using existing coordinates: ({initial_lat}, {initial_lon})")
            else:
                neighborhood_code = self.neighborhood_code_input.text().strip()
                if neighborhood_code and len(neighborhood_code) == 3:
                    center = self._get_neighborhood_center(neighborhood_code)
                    if center:
                        initial_lat, initial_lon = center
                        initial_zoom = 17  # ✅ Changed from 19 to 17 for better context
                        logger.info(f"✅ Focusing map on neighborhood {neighborhood_code}: ({initial_lat:.6f}, {initial_lon:.6f}) zoom={initial_zoom}")
                    else:
                        logger.warning(f"⚠️ Neighborhood {neighborhood_code} not found in neighborhoods.json, using default Aleppo center")
                        initial_lat = 36.2021
                        initial_lon = 37.1343
                        initial_zoom = 13
                else:
                    logger.info("No neighborhood code specified, using default Aleppo center")
                    initial_lat = 36.2021
                    initial_lon = 37.1343
                    initial_zoom = 13

            allow_polygon = self.polygon_radio.isChecked()

            dialog = MapPickerDialog(
                initial_lat=initial_lat,
                initial_lon=initial_lon,
                initial_zoom=initial_zoom,
                allow_polygon=allow_polygon,
                db=self.building_controller.db,
                parent=self
            )

            if dialog.exec_():
                result = dialog.get_result()

                # Handle Polygon geometry FIRST (before checking point)
                if result and 'polygon_wkt' in result and result['polygon_wkt']:
                    polygon_wkt = result['polygon_wkt']
                    self._polygon_wkt = polygon_wkt

                    # Get centroid for lat/lon
                    centroid_lat = result.get('latitude', 36.2)
                    centroid_lon = result.get('longitude', 37.15)
                    self.latitude_spin.setValue(centroid_lat)
                    self.longitude_spin.setValue(centroid_lon)

                    # ✅ Verify neighborhood and warn if different
                    self._verify_and_update_neighborhood_from_polygon(polygon_wkt)

                    # Show success message
                    self.location_status_label.setText(
                        f"✓ تم رسم المضلع (مركزه: {centroid_lat:.6f}, {centroid_lon:.6f})"
                    )
                    self.location_status_label.setStyleSheet(
                        f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;"
                    )
                    self.geometry_type_label.setText("🔷 مضلع")
                    logger.info(f"✅ Polygon drawn and saved: {polygon_wkt[:100]}...")

                # Handle Point geometry (only if NOT polygon)
                elif result and 'latitude' in result and 'longitude' in result:
                    lat = result['latitude']
                    lon = result['longitude']

                    self.latitude_spin.setValue(lat)
                    self.longitude_spin.setValue(lon)
                    self._polygon_wkt = None  # Clear polygon data

                    geometry_wkt = result.get('wkt') or f"POINT({lon} {lat})"
                    self._auto_detect_neighborhood(geometry_wkt)

                    self.location_status_label.setText(
                        f"تم تحديد الموقع ({lat:.6f}, {lon:.6f})"
                    )
                    self.location_status_label.setStyleSheet(
                        f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;"
                    )
                    self.geometry_type_label.setText("📍 نقطة")

        except ImportError:
            QMessageBox.information(
                self,
                "اختيار الموقع",
                "يرجى إدخال الإحداثيات يدوياً."
            )

    def _populate_data(self):
        """Populate form with existing building data."""
        if not self.building:
            return

        # GG: تحميل رمز المحافظة (Governorate)
        if hasattr(self.building, 'governorate_code') and self.building.governorate_code:
            self.governorate_combo.setText(self.building.governorate_code)

        # DD: تحميل رمز المنطقة (District)
        if hasattr(self.building, 'district_code') and self.building.district_code:
            self.district_combo.setText(self.building.district_code)

        # SS: تحميل المنطقة الفرعية (Subdistrict)
        if hasattr(self.building, 'subdistrict_code') and self.building.subdistrict_code:
            self.subdistrict_code.setText(self.building.subdistrict_code)

        # CCC: تحميل رمز المجتمع/المدينة (Community)
        if hasattr(self.building, 'community_code') and self.building.community_code:
            self.community_code.setText(self.building.community_code)

        # NNN: Load neighborhood code
        if hasattr(self.building, 'neighborhood_code') and self.building.neighborhood_code:
            self.neighborhood_code_input.setText(self.building.neighborhood_code)

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

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """
        Create a spinbox widget with icon arrows on the RIGHT side.
        DRY: Same pattern as unit_dialog.py

        Args:
            spinbox: The QSpinBox to wrap with custom arrows

        Returns:
            QFrame containing the spinbox with custom arrow controls
        """
        # Container frame - توحيد الحجم 45px height
        container = QFrame()
        container.setFixedHeight(45)
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

        # Spinbox styling - يسار
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                padding-right: 35px;
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #606266;
            }
        """)
        layout.addWidget(spinbox, 1)

        # Arrow column (RIGHT side) - يمين
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
        arrow_layout.setSpacing(0)  # صفر تماماً

        # Load arrow icons
        from ui.components.icon import Icon

        # Up arrow icon (^.png)
        up_label = QLabel()
        up_label.setFixedSize(30, 22)
        up_label.setAlignment(Qt.AlignCenter)
        up_pixmap = Icon.load_pixmap("^", size=10)
        if up_pixmap and not up_pixmap.isNull():
            up_label.setPixmap(up_pixmap)
        else:
            # Fallback to text if icon not found
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
            # Fallback to text if icon not found
            down_label.setText("v")
            down_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda _: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        layout.addWidget(arrow_container)

        return container

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
        """Get form data (DRY: adapted for manual entry fields)."""
        # استخراج building_id من الـ label (بعد "رمز البناء: ")
        building_id_text = self.building_id_label.text()
        if ":" in building_id_text:
            building_id = building_id_text.split(":", 1)[1].strip()
        else:
            building_id = building_id_text.strip()

        data = {
            "building_id": building_id,
            # GG: Governorate (manual entry now)
            "governorate_code": self.governorate_combo.text().strip() or "01",
            "governorate_name": "Aleppo",
            "governorate_name_ar": "حلب",
            # DD: District (manual entry now)
            "district_code": self.district_combo.text().strip() or "01",
            "district_name": "",  # Manual entry - no lookup
            "district_name_ar": "",
            # SS: Subdistrict
            "subdistrict_code": self.subdistrict_code.text().strip() or "01",
            "subdistrict_name": "",
            "subdistrict_name_ar": "",
            # CCC: Community
            "community_code": self.community_code.text().strip() or "001",
            "community_name": "",
            "community_name_ar": "",
            # NNN: Neighborhood code
            "neighborhood_code": self.neighborhood_code_input.text().strip() or "001",
            "neighborhood_name": self._get_neighborhood_name_en(),
            "neighborhood_name_ar": self._get_neighborhood_name_ar(),
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
            # Location descriptions (QTextEdit uses toPlainText())
            "general_description": self.general_desc.toPlainText().strip(),
            "location_description": self.site_desc.toPlainText().strip(),
        }

        if self._polygon_wkt:
            data["geo_location"] = self._polygon_wkt

        return data

    def _get_neighborhood_name_ar(self) -> str:
        """Get Arabic name from neighborhood code."""
        from app.config import AleppoDivisions
        code = self.neighborhood_code_input.text().strip()
        if code:
            for c, name_en, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
                if c == code:
                    return name_ar
        return ""

    def _get_neighborhood_name_en(self) -> str:
        """Get English name from neighborhood code."""
        from app.config import AleppoDivisions
        code = self.neighborhood_code_input.text().strip()
        if code:
            for c, name_en, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
                if c == code:
                    return name_en
        return ""

    def _auto_detect_neighborhood(self, geometry_wkt: str):
        """
        Auto-detect neighborhood from geometry (Point or Polygon).

        Uses NeighborhoodGeocoder service for reverse geocoding.
        Updates neighborhood code field if found.

        Args:
            geometry_wkt: WKT geometry string
        """
        try:
            from services.neighborhood_geocoder import NeighborhoodGeocoderFactory

            geocoder = NeighborhoodGeocoderFactory.create(provider="local")

            neighborhood = geocoder.find_neighborhood(geometry_wkt)

            if neighborhood:
                current_code = self.neighborhood_code_input.text().strip()

                if current_code and current_code != neighborhood.code:
                    reply = QMessageBox.question(
                        self,
                        "تغيير المنطقة",
                        f"المنطقة المدخلة: {current_code}\n"
                        f"المنطقة المكتشفة: {neighborhood.name_ar} ({neighborhood.code})\n\n"
                        f"هل تريد التحديث إلى المنطقة المكتشفة؟",
                        QMessageBox.Yes | QMessageBox.No
                    )

                    if reply == QMessageBox.Yes:
                        self.neighborhood_code_input.setText(neighborhood.code)

                elif not current_code:
                    self.neighborhood_code_input.setText(neighborhood.code)
                    Toast.show_success(
                        self,
                        f"تم تحديد المنطقة تلقائياً: {neighborhood.name_ar}"
                    )

            else:
                logger.debug("No neighborhood detected from geometry")

        except Exception as e:
            logger.error(f"Failed to auto-detect neighborhood: {e}")

    def _get_neighborhood_center(self, neighborhood_code: str) -> Optional[Tuple[float, float]]:
        """
        Get center coordinates of neighborhood from polygon.

        Args:
            neighborhood_code: Neighborhood code (e.g., "002")

        Returns:
            (latitude, longitude) tuple or None
        """
        try:
            from services.neighborhood_geocoder import NeighborhoodGeocoderFactory

            geocoder = NeighborhoodGeocoderFactory.create(provider="local")
            neighborhood = geocoder.get_neighborhood_by_code(neighborhood_code)

            if neighborhood:
                logger.info(f"Found neighborhood: {neighborhood.name_ar} ({neighborhood.code})")
                import json
                data_file = geocoder._data_file
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for n in data.get('neighborhoods', []):
                    if n['code'] == neighborhood_code:
                        polygon = n.get('polygon', [])
                        if polygon:
                            lng_sum = sum(p[0] for p in polygon)
                            lat_sum = sum(p[1] for p in polygon)
                            count = len(polygon)
                            center_lng = lng_sum / count
                            center_lat = lat_sum / count
                            logger.info(f"Calculated center: lat={center_lat}, lng={center_lng}")
                            return center_lat, center_lng

            logger.warning(f"Neighborhood not found: {neighborhood_code}")
            return None

        except Exception as e:
            logger.error(f"Failed to get neighborhood center: {e}", exc_info=True)
            return None

    def _verify_and_update_neighborhood_from_polygon(self, polygon_wkt: str):
        """
        Verify if drawn polygon is in the specified neighborhood.

        If different, show warning and update neighborhood code field.

        Args:
            polygon_wkt: WKT format polygon string
        """
        try:
            from services.neighborhood_geocoder import NeighborhoodGeocoderFactory

            # Get current neighborhood code from form
            current_neighborhood_code = self.neighborhood_code_input.text().strip()

            if not current_neighborhood_code:
                logger.info("No neighborhood code specified, skipping verification")
                return

            # Detect actual neighborhood from polygon
            geocoder = NeighborhoodGeocoderFactory.create(provider="local")
            detected = geocoder.find_neighborhood(polygon_wkt)

            if not detected:
                logger.warning("Could not detect neighborhood from polygon")
                QMessageBox.warning(
                    self,
                    "تحذير",
                    "⚠️ لم يتم التعرف على الحي من الموقع المحدد على الخريطة.\n"
                    "يرجى التأكد من رسم المضلع داخل حدود الحي الصحيح."
                )
                return

            # Compare with form value
            if detected.code != current_neighborhood_code:
                # Get current neighborhood name for display
                current_neighborhood = geocoder.get_neighborhood_by_code(current_neighborhood_code)
                current_name = current_neighborhood.name_ar if current_neighborhood else current_neighborhood_code

                # Show warning dialog
                reply = QMessageBox.warning(
                    self,
                    "تحذير - حي مختلف",
                    f"⚠️ البوليغون المرسوم يقع في حي مختلف!\n\n"
                    f"الحي المدخل في الحقل: {current_name} ({current_neighborhood_code})\n"
                    f"الحي المكتشف من الخريطة: {detected.name_ar} ({detected.code})\n\n"
                    f"هل تريد تحديث حقل الحي إلى '{detected.name_ar}' ({detected.code})؟",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Yes:
                    # Update neighborhood code field
                    self.neighborhood_code_input.setText(detected.code)
                    self._update_building_id()  # Update building ID
                    logger.info(f"✅ Updated neighborhood code from {current_neighborhood_code} to {detected.code}")

                    Toast.show_toast(
                        self,
                        f"تم تحديث رمز الحي إلى: {detected.name_ar} ({detected.code})",
                        Toast.INFO
                    )
                else:
                    logger.info(f"User kept original neighborhood code: {current_neighborhood_code}")
                    Toast.show_toast(
                        self,
                        "⚠️ تحذير: البوليغون في حي مختلف عن الحقل المدخل",
                        Toast.WARNING
                    )
            else:
                logger.info(f"✅ Polygon is correctly within neighborhood {detected.code}")

        except Exception as e:
            logger.error(f"Failed to verify neighborhood: {e}", exc_info=True)


class FilterableHeaderView(QHeaderView):
    """
    Custom header view that displays down.png icon AFTER text (RTL-compatible).

    DRY Principle: Reusable header for any table with filterable columns.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._down_pixmap = None
        self._filterable_columns = []  # Columns that show down icon
        self._load_down_icon()

    def _load_down_icon(self):
        """Load down.png icon."""
        from pathlib import Path
        import sys
        from PyQt5.QtGui import QPixmap

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        search_paths = [
            base_path / "assets" / "images" / "down.png",
            base_path / "assets" / "icons" / "down.png",
            base_path / "assets" / "down.png",
        ]

        for path in search_paths:
            if path.exists():
                self._down_pixmap = QPixmap(str(path))
                if not self._down_pixmap.isNull():
                    self._down_pixmap = self._down_pixmap.scaled(
                        10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    return

        self._down_pixmap = None

    def set_filterable_columns(self, columns: list):
        """Set which columns should show the down icon."""
        self._filterable_columns = columns

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int):
        """Simple paintSection - draw default then add icon at fixed position."""
        # Draw default header (background, border, text)
        super().paintSection(painter, rect, logical_index)

        # Add icon for filterable columns
        if logical_index in self._filterable_columns and self._down_pixmap and not self._down_pixmap.isNull():
            painter.save()

            # Simple fixed position: left side of the section (after text in RTL)
            # This works because text is right-aligned in RTL
            icon_x = rect.left() + 15
            icon_y = rect.center().y() - self._down_pixmap.height() // 2

            painter.drawPixmap(icon_x, icon_y, self._down_pixmap)
            painter.restore()


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
        self._all_buildings = []  # Store unfiltered buildings (DRY principle)
        self._current_page = 1
        self._rows_per_page = 11
        self._total_pages = 1

        # Active filters (DRY - same as field_work_preparation_page)
        self._active_filters = {
            'area': None,           # المنطقة (column 2)
            'building_type': None,  # نوع البناء (column 3)
            'building_status': None # حالة البناء (column 4)
        }

        self._setup_ui()

    def _setup_ui(self):
        """Setup buildings list UI."""
        layout = QVBoxLayout(self)
        # Apply unified padding from PageDimensions (DRY principle)
        # Same as completed_claims_page.py and draft_claims_page.py
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,        # Left: 131px
            PageDimensions.CONTENT_PADDING_V_TOP,    # Top: 32px
            PageDimensions.CONTENT_PADDING_H,        # Right: 131px
            PageDimensions.CONTENT_PADDING_V_BOTTOM  # Bottom: 0px
        )
        layout.setSpacing(15)  # 15px gap between header and table card

        # سطر العنوان والأزرار - المباني على اليسار والأزرار على اليمين
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        # العنوان - DRY: Using unified page title styling (18pt, PAGE_TITLE color)
        title = QLabel("المباني")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        top_row.addWidget(title)

        top_row.addStretch()

        # الأزرار
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        # زر تجهيز العمل الميداني (شفاف مع بوردر أزرق)
        # DRY: Apply unified button dimensions from Figma (199×48px, border-radius 8px)
        btn_field = CustomButton.secondary("تجهيز العمل الميداني", self, width=199, height=48)
        btn_field.clicked.connect(self.prepare_field_work.emit)

        # زر إضافة بناء جديد (أزرق solid)
        # DRY: Exact copy of "Add New Case" button from claims pages (PrimaryButton component)
        add_btn = PrimaryButton("إضافة بناء جديد", icon_name="icon")
        add_btn.clicked.connect(self.add_building.emit)

        btn_layout.addWidget(btn_field)
        btn_layout.addWidget(add_btn)

        top_row.addLayout(btn_layout)

        layout.addLayout(top_row)

        # البطاقة البيضاء للجدول
        table_card = QFrame()
        table_card.setFixedHeight(708)  # Figma spec: 708px height
        table_card.setStyleSheet("background-color: white; border-radius: 16px;")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setRowCount(11)  # Fixed 11 rows
        self.table.setLayoutDirection(Qt.RightToLeft)

        # Get down.png icon path
        from pathlib import Path
        import sys
        from PyQt5.QtGui import QIcon

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        icon_path = base_path / "assets" / "images" / "down.png"

        # Set headers with icons for filterable columns
        headers = ["رمز البناء", "تاريخ الادخال", "المنطقة", "نوع البناء", "حالة البناء", ""]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            # Add icon to filterable columns (2, 3, 4)
            if i in [2, 3, 4] and icon_path.exists():
                icon = QIcon(str(icon_path))
                item.setIcon(icon)
            self.table.setHorizontalHeaderItem(i, item)

        # Disable scroll bars
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ستايل الجدول الاحترافي
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                background-color: white;
                font-size: 10.5pt;
                font-weight: 400;
                color: #212B36;
            }}
            QTableWidget::item {{
                padding: 8px 15px;
                border-bottom: 1px solid #F0F0F0;
                color: #212B36;
                font-size: 10.5pt;
                font-weight: 400;
            }}
            QTableWidget::item:hover {{
                background-color: #FAFBFC;
            }}
            QHeaderView {{
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }}
            QHeaderView::section {{
                background-color: #F8F9FA;
                padding: 12px;
                padding-left: 30px;
                border: none;
                color: #637381;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }}
            QHeaderView::section:hover {{
                background-color: #EBEEF2;
            }}
        """)

        # ضبط المحاذاة والعرض
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setFixedHeight(56)  # Figma spec: 56px header height
        header.setStretchLastSection(True)  # آخر عمود يأخذ المساحة المتبقية
        header.setMouseTracking(True)  # Enable mouse tracking for cursor change

        # Connect hover event for cursor change on filterable columns
        header.sectionEntered.connect(self._on_header_hover)

        # تحديد عرض الأعمدة حسب Figma
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # رمز البناء
        header.resizeSection(0, 298)

        header.setSectionResizeMode(1, QHeaderView.Fixed)  # تاريخ الإدخال
        header.resizeSection(1, 220)

        header.setSectionResizeMode(2, QHeaderView.Fixed)  # المنطقة
        header.resizeSection(2, 206)

        header.setSectionResizeMode(3, QHeaderView.Fixed)  # نوع البناء
        header.resizeSection(3, 195)

        header.setSectionResizeMode(4, QHeaderView.Fixed)  # حالة البناء
        header.resizeSection(4, 195)

        header.setSectionResizeMode(5, QHeaderView.Stretch)  # أيقونة الثلاث نقاط (الباقي)

        # ضبط ارتفاع الصفوف بالتساوي
        # الارتفاع المتاح: 708 (card) - 10 (top) - 10 (bottom) - 56 (header) - 58 (footer) = 574px
        # لكل صف: 574 / 11 = 52px تقريباً
        vertical_header = self.table.verticalHeader()
        vertical_header.setVisible(False)
        vertical_header.setDefaultSectionSize(52)  # ارتفاع موحد لكل الصفوف

        # Enable cell click for actions button
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_click)

        # Connect header click for filtering (DRY - same pattern as field_work_preparation)
        header.sectionClicked.connect(self._on_header_clicked)

        card_layout.addWidget(self.table)

        # التذييل - Footer with gray background like header
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E1E8ED;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)
        footer_frame.setFixedHeight(58)  # Footer height: 58px

        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(10, 10, 10, 10)  # Padding 10px from all sides

        # Navigation arrows > < (أول شي من اليمين)
        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        # Previous button (>) - للصفحة السابقة
        self.prev_btn = QPushButton(">")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBEEF2;
            }
            QPushButton:disabled {
                color: #C1C7CD;
            }
        """)
        self.prev_btn.clicked.connect(self._go_to_previous_page)
        nav_layout.addWidget(self.prev_btn)

        # Next button (<) - للصفحة التالية
        self.next_btn = QPushButton("<")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBEEF2;
            }
            QPushButton:disabled {
                color: #C1C7CD;
            }
        """)
        self.next_btn.clicked.connect(self._go_to_next_page)
        nav_layout.addWidget(self.next_btn)

        footer.addWidget(nav_container)

        # Counter label "1-11 of 50" (ثاني شي)
        self.page_label = QLabel("1-11 of 11")
        self.page_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400;")
        footer.addWidget(self.page_label)

        # Rows number with down icon (ثالث شي) - Clickable page selector
        from PyQt5.QtGui import QPixmap
        rows_container = QFrame()
        rows_container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QFrame:hover {
                background-color: #EBEEF2;
            }
        """)
        rows_container.setCursor(Qt.PointingHandCursor)
        rows_layout = QHBoxLayout(rows_container)
        rows_layout.setContentsMargins(4, 2, 4, 2)
        rows_layout.setSpacing(4)

        # Down icon - أولاً (نجرب نبدل المكان)
        down_icon_label = QLabel()
        if icon_path.exists():
            down_pixmap = QPixmap(str(icon_path))
            if not down_pixmap.isNull():
                down_pixmap = down_pixmap.scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                down_icon_label.setPixmap(down_pixmap)
        down_icon_label.setStyleSheet("background: transparent; border: none;")
        rows_layout.addWidget(down_icon_label)

        # Number (11) - ثانياً
        self.rows_number = QLabel("11")
        self.rows_number.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent; border: none;")
        rows_layout.addWidget(self.rows_number)

        # Make clickable to show page selection menu
        rows_container.mousePressEvent = lambda e: self._show_page_selection_menu(rows_container)

        footer.addWidget(rows_container)

        # "Rows per page:" label (رابع شي)
        rows_label = QLabel("Rows per page:")
        rows_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400;")
        footer.addWidget(rows_label)

        footer.addStretch()

        card_layout.addWidget(footer_frame)

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

    def _load_buildings(self):
        """Load buildings from repository and populate table."""
        # Load buildings using controller
        result = self.building_controller.load_buildings()

        if result.success:
            all_buildings = result.data
        else:
            logger.error(f"Failed to load buildings: {result.message}")
            all_buildings = []

        self._all_buildings = all_buildings  # Store unfiltered buildings (DRY)

        # Apply filters (CRITICAL: Filter BEFORE pagination)
        self._buildings = self._apply_filters(all_buildings)

        # Calculate pagination from FILTERED buildings (not all_buildings)
        total = len(self._buildings)
        self._total_pages = (total + self._rows_per_page - 1) // self._rows_per_page if total > 0 else 1

        # Get buildings for current page from FILTERED buildings
        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + self._rows_per_page, total)
        page_buildings = self._buildings[start_idx:end_idx]

        # Clear all table cells
        for row in range(11):
            for col in range(6):
                self.table.setItem(row, col, QTableWidgetItem(""))

        # Populate table with current page data
        for idx, building in enumerate(page_buildings):
            # رمز البناء (use formatted ID if available, fallback to building_id)
            display_id = building.building_id_formatted or building.building_id or ""
            self.table.setItem(idx, 0, QTableWidgetItem(display_id))

            # تاريخ الادخال
            date_str = building.created_at.strftime("%d/%m/%Y") if building.created_at else ""
            self.table.setItem(idx, 1, QTableWidgetItem(date_str))

            # المنطقة (neighborhood only - no district prefix)
            area = (building.neighborhood_name_ar or building.neighborhood_name or '').strip()
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

            # زر الثلاث نقاط - أكبر وأغمق
            actions_item = QTableWidgetItem("⋮")
            actions_item.setTextAlignment(Qt.AlignCenter)

            # خط أكبر وأغمق للثلاث نقاط
            from PyQt5.QtGui import QFont, QColor
            dots_font = QFont()
            dots_font.setPointSize(18)  # أكبر من النص العادي (10.5pt)
            dots_font.setWeight(QFont.Bold)
            actions_item.setFont(dots_font)
            actions_item.setForeground(QColor("#637381"))  # لون أغمق

            self.table.setItem(idx, 5, actions_item)

        # Update pagination info (counter only: "1-11 of 50")
        if total > 0:
            self.page_label.setText(f"{start_idx + 1}-{end_idx} of {total}")
        else:
            self.page_label.setText("0-0 of 0")

        # Update navigation buttons state
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

    def _get_down_icon_path(self) -> str:
        """
        Get absolute path to down.png icon (DRY - reused from field_work_preparation_page).

        Single source of truth for icon paths.
        """
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        # Try multiple locations
        search_paths = [
            base_path / "assets" / "images" / "down.png",
            base_path / "assets" / "icons" / "down.png",
            base_path / "assets" / "down.png",
        ]

        for path in search_paths:
            if path.exists():
                return str(path).replace("\\", "/")

        return ""

    def _on_header_hover(self, logical_index: int):
        """
        Change cursor to pointer only on filterable columns (DRY principle).

        Args:
            logical_index: Column index being hovered
        """
        header = self.table.horizontalHeader()

        # Pointer cursor only for filterable columns (2, 3, 4)
        if logical_index in [2, 3, 4]:
            header.setCursor(Qt.PointingHandCursor)
        else:
            header.setCursor(Qt.ArrowCursor)

    def _on_header_clicked(self, logical_index: int):
        """
        Handle header click to show filter menu (DRY - same pattern as field_work_preparation).

        Filterable columns:
        - Column 2: المنطقة (Area)
        - Column 3: نوع البناء (Building Type)
        - Column 4: حالة البناء (Building Status)
        """
        # Only columns 2, 3, 4 are filterable
        if logical_index not in [2, 3, 4]:
            return

        self._show_filter_menu(logical_index)

    def _show_filter_menu(self, column_index: int):
        """
        Show filter menu for the clicked column (DRY principle).

        Args:
            column_index: Index of the column (2=Area, 3=Type, 4=Status)
        """
        # Get unique values for this column from all buildings
        unique_values = set()
        filter_key = None

        if column_index == 2:  # المنطقة (neighborhood only, no district)
            filter_key = 'area'
            for building in self._all_buildings:
                area = (building.neighborhood_name_ar or building.neighborhood_name or '').strip()
                if area:
                    unique_values.add(area)
        elif column_index == 3:  # نوع البناء
            filter_key = 'building_type'
            for building in self._all_buildings:
                for code, en, ar in Vocabularies.BUILDING_TYPES:
                    if code == building.building_type:
                        unique_values.add((code, ar))
                        break
        elif column_index == 4:  # حالة البناء
            filter_key = 'building_status'
            for building in self._all_buildings:
                for code, en, ar in Vocabularies.BUILDING_STATUS:
                    if code == building.building_status:
                        unique_values.add((code, ar))
                        break

        if not unique_values:
            return

        # Create menu
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

        # Add "عرض الكل" (Show All) option
        clear_action = QAction("عرض الكل", self)
        clear_action.triggered.connect(lambda: self._apply_filter(filter_key, None))
        menu.addAction(clear_action)

        menu.addSeparator()

        # Add filter options
        sorted_values = sorted(unique_values, key=lambda x: x[1] if isinstance(x, tuple) else x)
        for value in sorted_values:
            if isinstance(value, tuple):
                code, display = value
                action = QAction(display, self)
                action.triggered.connect(lambda checked, c=code: self._apply_filter(filter_key, c))
            else:
                action = QAction(value, self)
                action.triggered.connect(lambda checked, v=value: self._apply_filter(filter_key, v))

            # Mark active filter
            if column_index == 2 and self._active_filters['area'] == value:
                action.setCheckable(True)
                action.setChecked(True)
            elif column_index == 3 and self._active_filters['building_type'] == (value if isinstance(value, str) else value[0]):
                action.setCheckable(True)
                action.setChecked(True)
            elif column_index == 4 and self._active_filters['building_status'] == (value if isinstance(value, str) else value[0]):
                action.setCheckable(True)
                action.setChecked(True)

            menu.addAction(action)

        # Show menu below the specific column header (RTL-compatible positioning)
        header = self.table.horizontalHeader()

        # Get the visual position of the column (works correctly in RTL)
        x_pos = header.sectionViewportPosition(column_index)

        # Y position: below the header
        y_pos = header.height()

        # Map to global coordinates (relative to table widget, not header)
        pos = self.table.mapToGlobal(QPoint(x_pos, y_pos))
        menu.exec_(pos)

    def _apply_filter(self, filter_key: str, filter_value):
        """
        Apply filter and reload table (DRY principle).

        Args:
            filter_key: Key in _active_filters dict
            filter_value: Value to filter by (None to clear filter)
        """
        self._active_filters[filter_key] = filter_value
        self._current_page = 1  # Reset to first page
        self._load_buildings()

    def _apply_filters(self, buildings: list) -> list:
        """
        Apply active filters to buildings list (DRY principle).

        Returns:
            Filtered list of buildings
        """
        filtered = buildings

        # Apply area filter
        if self._active_filters['area']:
            filtered = [
                b for b in filtered
                if self._get_building_area(b) == self._active_filters['area']
            ]

        # Apply building type filter
        if self._active_filters['building_type']:
            filtered = [
                b for b in filtered
                if b.building_type == self._active_filters['building_type']
            ]

        # Apply building status filter
        if self._active_filters['building_status']:
            filtered = [
                b for b in filtered
                if b.building_status == self._active_filters['building_status']
            ]

        return filtered

    def _get_building_area(self, building) -> str:
        """Get formatted area string for building (DRY helper) - neighborhood name only."""
        # Return neighborhood name only (not district + neighborhood)
        return (building.neighborhood_name_ar or building.neighborhood_name or '').strip()

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

        # إنشاء القائمة - 3 صفوف فقط
        menu = QMenu(self)
        menu.setFixedSize(200, 149)  # Figma: 200×149

        # Load icons
        from ui.components.icon import Icon

        # 1. عرض - لون #212B36
        view_icon = Icon.load_qicon("eye-open", size=18)
        view_action = QAction("  عرض", self)
        if view_icon:
            view_action.setIcon(view_icon)
        menu.addAction(view_action)

        # 2. تعديل - لون #212B36
        edit_icon = Icon.load_qicon("edit-01", size=18)
        edit_action = QAction("  تعديل", self)
        if edit_icon:
            edit_action.setIcon(edit_icon)
        edit_action.triggered.connect(lambda: self.edit_building.emit(building))
        menu.addAction(edit_action)

        # 3. حذف - لون #FF4842
        delete_icon = Icon.load_qicon("delete", size=18)
        delete_action = QAction("  حذف", self)
        if delete_icon:
            delete_action.setIcon(delete_icon)
        delete_action.triggered.connect(lambda: self._on_delete_building(building))
        menu.addAction(delete_action)

        # Apply styles
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
            QMenu::item:nth-child(3) {
                color: #FF4842;
            }
            QMenu::item:nth-child(3):selected {
                color: #FF4842;
            }
        """)

        # عرض القائمة تحت زر الثلاث نقاط
        menu.exec_(self.table.viewport().mapToGlobal(position))

    def _show_on_map(self, building: Building):
        """
        Show building location on map (read-only view).

        Uses building_map_dialog_v2 with read_only mode.
        """
        if building.latitude and building.longitude:
            from ui.components.building_map_dialog_v2 import show_building_map_dialog

            auth_token = self._get_auth_token()

            show_building_map_dialog(
                db=self.building_controller.db,
                selected_building_id=building.building_id,
                auth_token=auth_token,
                read_only=True,
                parent=self
            )
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

    def _go_to_previous_page(self):
        """Go to previous page."""
        if self._current_page > 1:
            self._current_page -= 1
            self._load_buildings()

    def _go_to_next_page(self):
        """Go to next page."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_buildings()

    def _show_page_selection_menu(self, parent_widget):
        """Show dropdown menu to select page number."""
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

        # Add page numbers to menu
        for page_num in range(1, self._total_pages + 1):
            action = menu.addAction(f"Page {page_num}")
            if page_num == self._current_page:
                action.setEnabled(False)  # Disable current page
            else:
                action.triggered.connect(lambda checked, p=page_num: self._go_to_page(p))

        # Show menu below the widget
        menu.exec_(parent_widget.mapToGlobal(parent_widget.rect().bottomLeft()))

    def _go_to_page(self, page_num):
        """Go to specific page."""
        if 1 <= page_num <= self._total_pages:
            self._current_page = page_num
            self._load_buildings()

    def update_language(self, is_arabic: bool):
        """Update language."""
        # Reload buildings to update language
        self._load_buildings()


class BuildingsPage(QWidget):
    """
    Main Buildings Page - QStackedWidget container

    Supports both API and local database backends based on Config.DATA_PROVIDER.
    Set DATA_PROVIDER = "http" in config to use API backend.
    """

    view_building = pyqtSignal(str)

    def __init__(self, db: Database = None, i18n: I18n = None, parent=None, use_api: bool = None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_controller = BuildingController(db, use_api=use_api)
        self.export_service = ExportService(db) if db else None

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        # Background color from Figma via StyleManager (DRY principle)
        self.setStyleSheet(StyleManager.page_background())

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

        from ui.pages.field_work_preparation_page import FieldWorkPreparationPage
        self.field_work_page = FieldWorkPreparationPage(
            self.building_controller,
            self.i18n,
            parent=self
        )
        self.field_work_page.completed.connect(self._on_field_work_completed)
        self.field_work_page.cancelled.connect(self._on_field_work_cancelled)
        self.stacked.addWidget(self.field_work_page)
        self.stacked.setCurrentWidget(self.field_work_page)

    def _on_field_work_completed(self, workflow_data):
        """Handle field work workflow completion."""
        buildings = workflow_data.get('buildings', [])
        researcher = workflow_data.get('researcher', {})
        logger.debug(
            f"Field work assignment complete: {len(buildings)} buildings "
            f"assigned to {researcher.get('name', 'N/A')}"
        )
        # Return to list page
        self.list_page.refresh()
        self.stacked.setCurrentWidget(self.list_page)

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
