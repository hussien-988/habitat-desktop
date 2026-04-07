# -*- coding: utf-8 -*-
"""
    Buildings page with modern UI design - QStackedWidget implementation.
"""

import json
from pathlib import Path
from typing import Optional, Tuple
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QHeaderView,
    QFrame, QFileDialog, QAbstractItemView, QGraphicsDropShadowEffect,
    QDoubleSpinBox, QSpinBox, QScrollArea,
    QMenu, QAction, QTabWidget, QStackedWidget, QStyleOptionHeader, QStyle,
    QStylePainter, QStyleOptionComboBox, QSizePolicy
    )
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize, QLocale, QTimer
from PyQt5.QtGui import QColor, QCursor, QPainter, QFont, QIcon, QPixmap

# Try to import WebEngine for map
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage, QWebEngineProfile
    from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from app.config import Config
from services.vocab_service import get_options as vocab_get_options, get_label as vocab_get_label
from services.display_mappings import (
    get_building_type_display, get_building_status_display,
    get_building_type_options, get_building_status_options
    )
from services.divisions_service import DivisionsService
from services.api_client import get_api_client
from models.building import Building
from repositories.database import Database
from controllers.building_controller import BuildingController
from services.export_service import ExportService
from services.validation_service import ValidationService
from ui.components.rtl_combo import RtlCombo
from ui.components.toast import Toast
from ui.error_handler import ErrorHandler
from ui.components.custom_button import CustomButton
from ui.components.primary_button import PrimaryButton
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.design_system import PageDimensions, Colors, ButtonDimensions, ScreenScale
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from services.api_worker import ApiWorker
from utils.i18n import I18n
from utils.logger import get_logger
from services.translation_manager import tr, get_layout_direction
from ui.components.animated_card import AnimatedCard, EmptyStateAnimated, animate_card_entrance

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


class CodeDisplayCombo(RtlCombo):
    """QComboBox that shows full text in dropdown but only the code in the selected field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.currentIndexChanged.connect(self._update_code_display)

    def _update_code_display(self):
        code = self.currentData()
        if code and self.lineEdit():
            self.lineEdit().setText(str(code))


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
        self._neighborhoods_cache = []
        self._has_map_coordinates = False

        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

        if building:
            self._populate_data()

    def _setup_ui(self):
        """Setup the add/edit building UI with 3 cards."""
        # Wrap content in scroll area to show all cards
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.buildings.building_info"))

        # Close button in header
        close_btn = QPushButton("✕")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(ButtonDimensions.CLOSE_WIDTH, ButtonDimensions.CLOSE_HEIGHT)
        close_btn_font = create_font(
            size=ButtonDimensions.CLOSE_FONT_SIZE,
            weight=QFont.Normal,
            letter_spacing=0
        )
        close_btn.setFont(close_btn_font)
        close_btn.setStyleSheet(StyleManager.refresh_button_dark())
        close_btn.clicked.connect(self.cancelled.emit)
        self._header.add_action_widget(close_btn)

        # Save button in header
        self._save_btn = QPushButton(" " + tr("button.save"))
        save_btn = self._save_btn
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)
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
        save_btn.setStyleSheet(StyleManager.refresh_button_dark())
        save_btn.clicked.connect(self._on_save)
        save_btn.setVisible(False)  # Read-only mode: no save button
        self._header.add_action_widget(save_btn)

        main_layout.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        main_layout.addWidget(self._accent_line)

        # Create scroll area for the form content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        # Container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            PageDimensions.content_padding_h(),
            14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        layout.setSpacing(12)

        container.setStyleSheet(StyleManager.page_background())
        # Same card style as wizard (building_selection_step.py)
        card1 = QFrame()
        card1.setObjectName("buildingCard")
        card1.setStyleSheet(StyleManager.form_card())

        card1_layout = QVBoxLayout(card1)
        # Padding: 12px from all sides (matching wizard)
        card1_layout.setContentsMargins(12, 12, 12, 12)
        # No default spacing - we'll control gaps manually for precision
        card1_layout.setSpacing(0)

        # Header (title + subtitle) - same structure as wizard
        card_header = QHBoxLayout()
        card_header.setSpacing(8)

        # Icon FIRST (left side in RTL)
        from ui.components.icon import Icon
        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(40), ScreenScale.h(40))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        # Load blue.png icon
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

        # Title: "بيانات البناء"
        info_title = QLabel(tr("page.buildings.building_data"))
        # Title
        info_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        info_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Subtitle: "ادخل معلومات البناء والموقع الجغرافي"
        # Changed from "ابحث عن" to "ادخل" as requested
        info_sub = QLabel(tr("page.buildings.enter_building_info"))
        # Subtitle
        info_sub.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        info_sub.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        header_text_col.addWidget(info_title)
        header_text_col.addWidget(info_sub)

        card_header.addLayout(header_text_col)
        card_header.addStretch(1)

        card1_layout.addLayout(card_header)

        # Gap: 12px between header and fields (matching wizard)
        card1_layout.addSpacing(12)

        # شبكة الحقول - 6 في صف واحد (بدون containers)
        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        # Shared label font (same as card title)
        label_font = create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD)

        # Shared input style for QLineEdit fields
        input_style = StyleManager.form_input_light()

        # Shared combo style for dropdown fields
        code_combo_style = StyleManager.form_combo_light()

        # DivisionsService for cascading dropdowns
        self._divisions = DivisionsService()

        # Field 1: رمز المحافظة (Governorate) - Dropdown
        gov_container = QVBoxLayout()
        gov_container.setSpacing(6)
        gov_label = QLabel(tr("page.buildings.governorate_code"))
        gov_label.setFont(label_font)
        gov_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.governorate_combo = CodeDisplayCombo()
        self.governorate_combo.addItem(tr("page.buildings.select_governorate"), "")
        for code, en, ar in self._divisions.get_governorates():
            self.governorate_combo.addItem(f"{code} - {ar}", code)
        self.governorate_combo.setCurrentIndex(1)  # Default: Aleppo
        self.governorate_combo.setStyleSheet(code_combo_style)
        self.governorate_combo.setFixedHeight(ScreenScale.h(45))
        self.governorate_combo.setLayoutDirection(get_layout_direction())
        self.governorate_combo.currentIndexChanged.connect(self._on_governorate_changed)
        gov_container.addWidget(gov_label)
        gov_container.addWidget(self.governorate_combo)
        fields_row.addLayout(gov_container, 1)

        # Field 2: رمز المنطقة (District) - Dropdown from DivisionsService
        dist_container = QVBoxLayout()
        dist_container.setSpacing(6)
        dist_label = QLabel(tr("page.buildings.district_code"))
        dist_label.setFont(label_font)
        dist_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.district_combo = CodeDisplayCombo()
        self.district_combo.setStyleSheet(code_combo_style)
        self.district_combo.setFixedHeight(ScreenScale.h(45))
        self.district_combo.setLayoutDirection(get_layout_direction())
        self.district_combo.currentIndexChanged.connect(self._on_district_changed)
        dist_container.addWidget(dist_label)
        dist_container.addWidget(self.district_combo)
        fields_row.addLayout(dist_container, 1)

        # Field 3: رمز البلدة (Subdistrict) - Dropdown from DivisionsService
        sub_container = QVBoxLayout()
        sub_container.setSpacing(6)
        sub_label = QLabel(tr("page.buildings.subdistrict_code"))
        sub_label.setFont(label_font)
        sub_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.subdistrict_combo = CodeDisplayCombo()
        self.subdistrict_combo.setStyleSheet(code_combo_style)
        self.subdistrict_combo.setFixedHeight(ScreenScale.h(45))
        self.subdistrict_combo.setLayoutDirection(get_layout_direction())
        self.subdistrict_combo.currentIndexChanged.connect(self._on_subdistrict_changed)
        sub_container.addWidget(sub_label)
        sub_container.addWidget(self.subdistrict_combo)
        fields_row.addLayout(sub_container, 1)

        # Field 4: رمز القرية (Community) - Dropdown from DivisionsService
        comm_container = QVBoxLayout()
        comm_container.setSpacing(6)
        comm_label = QLabel(tr("page.buildings.community_code"))
        comm_label.setFont(label_font)
        comm_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.community_combo = CodeDisplayCombo()
        self.community_combo.setStyleSheet(code_combo_style)
        self.community_combo.setFixedHeight(ScreenScale.h(45))
        self.community_combo.setLayoutDirection(get_layout_direction())
        self.community_combo.currentIndexChanged.connect(self._update_building_id)
        self.community_combo.currentIndexChanged.connect(self._validate_building_id_realtime)
        comm_container.addWidget(comm_label)
        comm_container.addWidget(self.community_combo)
        fields_row.addLayout(comm_container, 1)

        # Field 5: رمز الحي (Neighborhood) - Loaded from API
        neigh_container = QVBoxLayout()
        neigh_container.setSpacing(6)
        neigh_label = QLabel(tr("page.buildings.neighborhood_code"))
        neigh_label.setFont(label_font)
        neigh_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        self.neighborhood_combo = CodeDisplayCombo()
        self.neighborhood_combo.addItem(tr("page.buildings.select_neighborhood"), "")
        self.neighborhood_combo.setStyleSheet(code_combo_style)
        self.neighborhood_combo.setFixedHeight(ScreenScale.h(45))
        self.neighborhood_combo.setLayoutDirection(get_layout_direction())

        self.neighborhood_combo.currentIndexChanged.connect(self._update_building_id)
        self.neighborhood_combo.currentIndexChanged.connect(self._validate_building_id_realtime)
        self.neighborhood_combo.currentIndexChanged.connect(self._on_neighborhood_changed_by_user)

        neigh_container.addWidget(neigh_label)
        neigh_container.addWidget(self.neighborhood_combo)
        fields_row.addLayout(neigh_container, 1)

        # Field 6: رمز البناء (Building Number) - QLineEdit (unique number)
        build_container = QVBoxLayout()
        build_container.setSpacing(6)
        build_label = QLabel(tr("page.buildings.building_number"))
        build_label.setFont(label_font)
        build_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.building_number = QLineEdit()
        self.building_number.setPlaceholderText("00001")
        self.building_number.setMaxLength(5)
        self.building_number.setStyleSheet(input_style)
        self.building_number.setFixedHeight(ScreenScale.h(45))
        self.building_number.setAlignment(Qt.AlignRight)
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
        self.building_id_label = QLabel(tr("page.buildings.building_code") + ": 01-001-002-003-0001-01-01")
        self.building_id_label.setAlignment(Qt.AlignCenter)
        self.building_id_label.setFixedHeight(ScreenScale.h(32))
        self.building_id_label.setStyleSheet("""
            background-color: #f0f7ff; color: #409eff;
            border: 1px solid #d9ecff; border-radius: 4px;
            font-weight: bold; margin-top: 8px; font-size: 13px;
        """)
        card1_layout.addWidget(self.building_id_label)

        # Trigger initial cascade to fill district → subdistrict → community
        self._on_governorate_changed()

        layout.addWidget(card1)
        card2 = QFrame()
        card2.setStyleSheet(StyleManager.form_card())
        card2_layout = QHBoxLayout(card2)
        card2_layout.setContentsMargins(12, 12, 12, 12)
        card2_layout.setSpacing(15)

        # Shared label font for card 2 (same as card 1)
        card2_label_font = create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD)

        # Shared combobox style
        combo_style = StyleManager.form_combo_light()

        # حالة البناء
        vbox_status = QVBoxLayout()
        vbox_status.setSpacing(6)
        lbl_status = QLabel(tr("page.buildings.filter_status"))
        lbl_status.setFont(card2_label_font)
        lbl_status.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_status.addWidget(lbl_status)
        self.status_combo = RtlCombo()
        self.status_combo.addItem(tr("page.buildings.select"))
        for code, label in vocab_get_options("BuildingStatus"):
            self.status_combo.addItem(label, code)
        self.status_combo.setStyleSheet(combo_style)
        self.status_combo.setFixedHeight(ScreenScale.h(45))
        self.status_combo.setLayoutDirection(get_layout_direction())
        vbox_status.addWidget(self.status_combo)
        card2_layout.addLayout(vbox_status, 1)  # توحيد العرض - stretch factor

        # نوع البناء
        vbox_type = QVBoxLayout()
        vbox_type.setSpacing(6)
        lbl_type = QLabel(tr("page.buildings.filter_type"))
        lbl_type.setFont(card2_label_font)
        lbl_type.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_type.addWidget(lbl_type)
        self.type_combo = RtlCombo()
        self.type_combo.addItem(tr("page.buildings.select"))
        for code, label in vocab_get_options("BuildingType"):
            self.type_combo.addItem(label, code)
        self.type_combo.setStyleSheet(combo_style)
        self.type_combo.setFixedHeight(ScreenScale.h(45))
        self.type_combo.setLayoutDirection(get_layout_direction())
        self.type_combo.currentIndexChanged.connect(self._on_building_type_changed)
        vbox_type.addWidget(self.type_combo)
        card2_layout.addLayout(vbox_type, 1)  # توحيد العرض - stretch factor

        # عدد المقاسم السكنية
        vbox_residential = QVBoxLayout()
        vbox_residential.setSpacing(6)
        lbl_residential = QLabel(tr("page.buildings.residential_units"))
        lbl_residential.setFont(card2_label_font)
        lbl_residential.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_residential.addWidget(lbl_residential)
        self.residential_spin = QSpinBox()
        self.residential_spin.setRange(0, 200)
        self.residential_spin.setValue(0)
        self.residential_spin.setAlignment(Qt.AlignRight)
        self.residential_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.residential_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.residential_spin.valueChanged.connect(self._update_total_units)
        residential_widget = self._create_spinbox_with_arrows(self.residential_spin)
        vbox_residential.addWidget(residential_widget)
        card2_layout.addLayout(vbox_residential, 1)

        # عدد المقاسم غير السكنية
        vbox_non_residential = QVBoxLayout()
        vbox_non_residential.setSpacing(6)
        lbl_non_residential = QLabel(tr("page.buildings.non_residential_units"))
        lbl_non_residential.setFont(card2_label_font)
        lbl_non_residential.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_non_residential.addWidget(lbl_non_residential)
        self.non_residential_spin = QSpinBox()
        self.non_residential_spin.setRange(0, 200)
        self.non_residential_spin.setValue(0)
        self.non_residential_spin.setAlignment(Qt.AlignRight)
        self.non_residential_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.non_residential_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.non_residential_spin.valueChanged.connect(self._update_total_units)
        non_residential_widget = self._create_spinbox_with_arrows(self.non_residential_spin)
        vbox_non_residential.addWidget(non_residential_widget)
        card2_layout.addLayout(vbox_non_residential, 1)

        # عدد الطوابق
        vbox_floors = QVBoxLayout()
        vbox_floors.setSpacing(6)
        lbl_floors = QLabel(tr("page.buildings.floors_count"))
        lbl_floors.setFont(card2_label_font)
        lbl_floors.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_floors.addWidget(lbl_floors)
        self.floors_spin = QSpinBox()
        self.floors_spin.setRange(0, 50)
        self.floors_spin.setValue(1)
        self.floors_spin.setAlignment(Qt.AlignRight)
        self.floors_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.floors_spin.setButtonSymbols(QSpinBox.NoButtons)
        floors_widget = self._create_spinbox_with_arrows(self.floors_spin)
        vbox_floors.addWidget(floors_widget)
        card2_layout.addLayout(vbox_floors, 1)

        # العدد الكلي للمقاسم (read-only, auto-calculated)
        vbox_total = QVBoxLayout()
        vbox_total.setSpacing(6)
        lbl_total = QLabel(tr("page.add_building.total_units"))
        lbl_total.setFont(card2_label_font)
        lbl_total.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox_total.addWidget(lbl_total)
        self.total_units_label = QLabel("0")
        self.total_units_label.setAlignment(Qt.AlignCenter)
        self.total_units_label.setFixedHeight(ScreenScale.h(45))
        self.total_units_label.setStyleSheet("""
            QLabel {
                padding: 6px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #EEF2F7;
                font-size: 16px;
                font-weight: 700;
                color: #374151;
            }
        """)
        vbox_total.addWidget(self.total_units_label)
        card2_layout.addLayout(vbox_total, 1)

        layout.addWidget(card2)

        # === CARD 3: موقع البناء ===
        card3 = QFrame()
        card3.setStyleSheet(StyleManager.form_card())
        card3_layout = QVBoxLayout(card3)
        card3_layout.setContentsMargins(12, 12, 12, 12)
        card3_layout.setSpacing(0)  # Manual spacing control

        # Row 1: Header only - "موقع البناء"
        header = QLabel(tr("page.add_building.building_location"))
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
        map_label.setFixedHeight(ScreenScale.h(16))  # Same as label height
        map_section.addWidget(map_label)

        # Map container (QLabel to support QPixmap)
        map_container = QLabel()
        map_container.setFixedSize(ScreenScale.w(400), ScreenScale.h(130))
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
        map_button.setFixedSize(ScreenScale.w(94), ScreenScale.h(20))
        map_button.move(8, 8)  # Position in top-left corner with small margin
        map_button.setCursor(Qt.PointingHandCursor)

        # Icon: pill.png
        icon_pixmap = Icon.load_pixmap("pill", size=12)
        if icon_pixmap and not icon_pixmap.isNull():
            map_button.setIcon(QIcon(icon_pixmap))
            map_button.setIconSize(QSize(12, 12))

        # Text: "فتح الخريطة"
        map_button.setText(tr("page.add_building.open_map"))
        map_button.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))

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
        map_button.setVisible(False)  # Read-only mode: no map picking

        # Location icon in center of map
        location_icon = QLabel(map_container)
        location_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if location_pixmap and not location_pixmap.isNull():
            location_icon.setPixmap(location_pixmap)
            location_icon.setFixedSize(ScreenScale.w(56), ScreenScale.h(56))
            # Position in center: (400-56)/2 = 172, (130-56)/2 = 37
            location_icon.move(172, 37)
            location_icon.setStyleSheet("background: transparent;")
        else:
            # Fallback: use text emoji
            location_icon.setText("📍")
            location_icon.setFont(create_font(size=32, weight=FontManager.WEIGHT_REGULAR))
            location_icon.setStyleSheet("background: transparent;")
            location_icon.setAlignment(Qt.AlignCenter)
            location_icon.setFixedSize(ScreenScale.w(56), ScreenScale.h(56))
            location_icon.move(172, 37)

        map_section.addWidget(map_container)

        # Polygon-only mode
        geometry_type_row = QHBoxLayout()
        geometry_type_row.setSpacing(12)
        geometry_type_row.setContentsMargins(0, 8, 0, 0)

        geometry_label = QLabel(tr("page.add_building.location_type"))
        geometry_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        geometry_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        geometry_type_row.addWidget(geometry_label)

        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.geometry_button_group = QButtonGroup(self)

        # Point radio hidden
        self.point_radio = QRadioButton(tr("page.add_building.point_gps"))
        self.point_radio.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.point_radio.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.point_radio.setChecked(False)
        self.point_radio.setVisible(False)
        self.geometry_button_group.addButton(self.point_radio, 1)

        self.polygon_radio = QRadioButton(tr("page.add_building.polygon"))
        self.polygon_radio.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.polygon_radio.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        self.polygon_radio.setChecked(True)
        self.geometry_button_group.addButton(self.polygon_radio, 2)
        geometry_type_row.addWidget(self.polygon_radio)

        geometry_type_row.addStretch()
        map_section.addLayout(geometry_type_row)

        map_section.addStretch(1)  # Push content to top

        content_row.addLayout(map_section, stretch=1)

        # Section 2: وثائق المبنى - Document thumbnails (replaces وصف الموقع)
        docs_section = QVBoxLayout()
        docs_section.setSpacing(4)

        lbl_docs = QLabel(tr("page.add_building.building_documents"))
        lbl_docs.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl_docs.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        docs_section.addWidget(lbl_docs)

        self.docs_scroll = QScrollArea()
        self.docs_scroll.setFixedHeight(ScreenScale.h(130))
        self.docs_scroll.setWidgetResizable(True)
        self.docs_scroll.setFrameShape(QFrame.NoFrame)
        self.docs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.docs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.docs_scroll.setStyleSheet(
            "QScrollArea { background-color: #F8FAFF; border: 1px solid #dcdfe6; border-radius: 8px; }"
            + StyleManager.scrollbar()
        )

        self.docs_container = QWidget()
        self.docs_container.setStyleSheet("background: transparent;")
        self.docs_layout = QHBoxLayout(self.docs_container)
        self.docs_layout.setContentsMargins(8, 8, 8, 8)
        self.docs_layout.setSpacing(8)
        self.docs_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.docs_empty_label = QLabel(tr("page.add_building.no_documents"))
        self.docs_empty_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self.docs_empty_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.docs_empty_label.setAlignment(Qt.AlignCenter)
        self.docs_layout.addWidget(self.docs_empty_label)
        self.docs_layout.addStretch()

        self.docs_scroll.setWidget(self.docs_container)
        docs_section.addWidget(self.docs_scroll)
        docs_section.addStretch(1)

        content_row.addLayout(docs_section, stretch=1)

        # Section 3: وصف البناء (read-only text)
        section_general = QVBoxLayout()
        section_general.setSpacing(4)

        lbl_general = QLabel(tr("page.add_building.building_description"))
        lbl_general.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl_general.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        self.general_desc = QTextEdit()
        self.general_desc.setPlaceholderText(tr("page.add_building.no_description"))
        self.general_desc.setReadOnly(True)
        self.general_desc.setFixedHeight(ScreenScale.h(130))
        self.general_desc.setStyleSheet(StyleManager.form_input_light())

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

        # Set container in scroll area and add to main layout
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Apply read-only mode to all form fields
        self._apply_read_only_mode()

    def _apply_read_only_mode(self):
        """Make all form inputs read-only (page is informational only)."""
        for combo in (
            self.governorate_combo, self.district_combo,
            self.subdistrict_combo, self.community_combo,
            self.neighborhood_combo, self.status_combo, self.type_combo
        ):
            combo.setEnabled(False)

        self.building_number.setReadOnly(True)

        for spin in (self.residential_spin, self.non_residential_spin, self.floors_spin):
            spin.setEnabled(False)

        self.polygon_radio.setEnabled(False)

    def _load_building_documents(self, building_uuid: str):
        """Fetch and display document thumbnails for the building (non-blocking)."""
        # Clear existing docs
        while self.docs_layout.count() > 0:
            item = self.docs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._docs_worker = ApiWorker(self._fetch_building_documents_bg, building_uuid)
        self._docs_worker.finished.connect(self._on_building_documents_loaded)
        self._docs_worker.error.connect(self._on_building_documents_error)
        self._spinner.show_loading(tr("component.loading.default"))
        self._docs_worker.start()

    def _fetch_building_documents_bg(self, building_uuid):
        """Background: fetch building documents from API."""
        from services.api_client import get_api_client
        api = get_api_client()
        if not api:
            return None
        return api.get_building_documents(building_uuid)

    def _on_building_documents_loaded(self, docs):
        """Callback: display fetched document thumbnails."""
        self._spinner.hide_loading()
        if not docs:
            self._show_no_docs()
            return

        for doc in docs:
            card = self._create_doc_card(doc)
            self.docs_layout.addWidget(card)

        self.docs_layout.addStretch()

    def _on_building_documents_error(self, error_msg):
        """Callback: document fetch failed."""
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.buildings.load_error"), Toast.ERROR)
        logger.warning(f"Failed to load building documents: {error_msg}")
        self._show_no_docs()

    def _show_no_docs(self):
        """Display 'no documents' placeholder in the docs area."""
        label = QLabel(tr("page.add_building.no_documents"))
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label.setAlignment(Qt.AlignCenter)
        self.docs_layout.addWidget(label)
        self.docs_layout.addStretch()

    def _create_doc_card(self, doc: dict) -> QWidget:
        """Create a clickable document thumbnail card (70x90px)."""
        from PyQt5.QtWidgets import QSizePolicy
        card = QFrame()
        card.setFixedSize(ScreenScale.w(70), ScreenScale.h(100))
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
            }
            QFrame:hover { border-color: #3890DF; }
        """)
        card.setCursor(Qt.PointingHandCursor)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        mime_type = doc.get("mimeType", "")
        file_path = doc.get("filePath", "")
        file_name = doc.get("originalFileName", "")

        thumb = QLabel()
        thumb.setFixedSize(ScreenScale.w(60), ScreenScale.h(60))
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")

        if mime_type.startswith("image/") and file_path:
            px = QPixmap(file_path)
            if not px.isNull():
                thumb.setPixmap(px.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                thumb.setText("🖼")
                thumb.setFont(create_font(size=20, weight=FontManager.WEIGHT_REGULAR))
        else:
            thumb.setText("📄")
            thumb.setFont(create_font(size=20, weight=FontManager.WEIGHT_REGULAR))

        card_layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_label = QLabel(file_name[:10] + "..." if len(file_name) > 10 else file_name)
        name_label.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        card_layout.addWidget(name_label)

        card.mousePressEvent = lambda event, fp=file_path: self._on_doc_clicked(fp)

        return card

    def _on_doc_clicked(self, file_path: str):
        """Open a document file using the system default application."""
        if not file_path:
            return
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

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
            widget.setFixedHeight(ScreenScale.h(36))
            widget.setAlignment(Qt.AlignCenter)
        elif isinstance(widget, QComboBox):
            widget.setFixedHeight(ScreenScale.h(36))

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

    def _get_gov_code(self) -> str:
        """Get governorate code from combo or fallback."""
        return self.governorate_combo.currentData() or "01"

    def _get_district_code(self) -> str:
        """Get district code from combo or fallback."""
        return self.district_combo.currentData() or "01"

    def _get_subdistrict_code(self) -> str:
        """Get subdistrict code from combo or fallback."""
        return self.subdistrict_combo.currentData() or "01"

    def _get_community_code(self) -> str:
        """Get community code from combo or fallback."""
        return self.community_combo.currentData() or "001"

    def _get_neighborhood_code(self) -> str:
        """Get neighborhood code from combo (empty string if none selected)."""
        return self.neighborhood_combo.currentData() or ""

    def _update_building_id(self):
        """Generate building ID in format: GG-DD-SS-CCC-NNN-BBBBB"""
        gov = self._get_gov_code()
        dist = self._get_district_code()
        subdist = self._get_subdistrict_code()
        comm = self._get_community_code()
        neigh = self._get_neighborhood_code() or "___"
        bldg_num = self.building_number.text().strip().zfill(5)

        building_id = f"{gov}-{dist}-{subdist}-{comm}-{neigh}-{bldg_num}"
        self.building_id_label.setText(tr("page.add_building.building_code_value", code=building_id))

    def _validate_building_number_on_enter(self):
        """Validate building number when user presses Enter."""
        building_num = self.building_number.text().strip()

        if len(building_num) < 5:
            ErrorHandler.show_warning(self, tr("dialog.buildings.building_number_5_digits"))
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
        gov = self._get_gov_code()
        dist = self._get_district_code()
        subdist = self._get_subdistrict_code()
        comm = self._get_community_code()
        neigh = self._get_neighborhood_code()
        bldg_num = building_num.zfill(5)

        building_id = f"{gov}-{dist}-{subdist}-{comm}-{neigh}-{bldg_num}"
        building_id_plain = building_id.replace("-", "")

        # Check if this building ID already exists in the database
        # Skip check if we're editing an existing building with this ID
        if self.building and self.building.building_id == building_id_plain:
            self.building_id_warning.hide()
            return

        # Use controller to check existence (dashless for DB lookup)
        result = self.building_controller.get_building_by_id(building_id_plain)

        if result.success and result.data:
            self.building_id_warning.setText(tr("dialog.buildings.building_already_exists"))
            self.building_id_warning.show()
        else:
            self.building_id_warning.hide()

    def _update_total_units(self):
        """Update total units label (residential + non-residential)."""
        total = self.residential_spin.value() + self.non_residential_spin.value()
        self.total_units_label.setText(str(total))

    def _on_building_type_changed(self):
        """Enable/disable residential and non-residential spins based on building type."""
        building_type = self.type_combo.currentData()

        # Vocab integer codes: 1=Residential, 2=Commercial, 3=MixedUse, 4=Industrial
        if building_type == 1:
            self.residential_spin.setEnabled(True)
            self.non_residential_spin.setEnabled(False)
            self.non_residential_spin.setValue(0)
        elif building_type in (2, 4):
            self.residential_spin.setEnabled(False)
            self.residential_spin.setValue(0)
            self.non_residential_spin.setEnabled(True)
        elif building_type == 3:
            self.residential_spin.setEnabled(True)
            self.non_residential_spin.setEnabled(True)
        else:
            self.residential_spin.setEnabled(True)
            self.non_residential_spin.setEnabled(True)

        self._update_total_units()

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

                    # Heuristic zoom calculation (tiles exist 15-20)
                    if lat_diff < 0.01 or lon_diff < 0.01:
                        zoom = 17  # Small area (neighborhood)
                    elif lat_diff < 0.05 or lon_diff < 0.05:
                        zoom = 16  # Medium area (district)
                    else:
                        zoom = 15  # Large area (city overview)

                    logger.info(f"Area center calculated: ({center_lat:.6f}, {center_lon:.6f}) zoom={zoom}")
                    logger.info(f"   Based on {len(buildings)} buildings in area")
                    return center_lat, center_lon, zoom

            # Fallback: No buildings found in area
            logger.warning(f"No buildings found in specified area, using default center")
            return 36.2021, 37.1343, 15

        except Exception as e:
            logger.error(f"Failed to calculate area center: {e}")
            # Fallback to default
            return 36.2021, 37.1343, 15

    def _on_pick_from_map(self):
        """
        Open map picker to select building location.

        No validation required - user can open map at any time.
        Uses existing coordinates or defaults to Aleppo center.
        Buildings are saved to Backend Database (PostgreSQL).
        """
        try:
            from ui.components.map_picker_dialog_v2 import MapPickerDialog  # noqa: F401
        except ImportError:
            ErrorHandler.show_success(
                self,
                tr("dialog.buildings.enter_coordinates_manually"),
                tr("dialog.buildings.select_location")
            )
            return

        # Compute synchronous map params
        initial_bounds = None
        selected_neighborhood_code = self._get_neighborhood_code()

        if self._has_map_coordinates:
            initial_lat = self.latitude_spin.value()
            initial_lon = self.longitude_spin.value()
            initial_zoom = 20
        elif selected_neighborhood_code:
            center = self._get_neighborhood_center(selected_neighborhood_code)
            if center:
                initial_lat, initial_lon = center
                initial_zoom = 18
                initial_bounds = self._get_neighborhood_bounds(selected_neighborhood_code)
            else:
                initial_lat = 36.2021
                initial_lon = 37.1343
                initial_zoom = 15
        else:
            initial_lat = 36.2021
            initial_lon = 37.1343
            initial_zoom = 15

        allow_polygon = self.polygon_radio.isChecked()

        # Store map params for use in callback
        self._map_picker_params = {
            "initial_lat": initial_lat,
            "initial_lon": initial_lon,
            "initial_zoom": initial_zoom,
            "allow_polygon": allow_polygon,
            "initial_bounds": initial_bounds,
            "selected_neighborhood_code": selected_neighborhood_code,
        }

        # Fetch neighborhoods GeoJSON in background, then open dialog
        self._neighborhoods_geojson_worker = ApiWorker(self._build_neighborhoods_geojson)
        self._neighborhoods_geojson_worker.finished.connect(self._on_neighborhoods_geojson_loaded)
        self._neighborhoods_geojson_worker.error.connect(self._on_neighborhoods_geojson_error)
        self._spinner.show_loading(tr("component.loading.default"))
        self._neighborhoods_geojson_worker.start()

    def _on_neighborhoods_geojson_loaded(self, neighborhoods_geojson):
        """Callback: open map picker dialog with fetched neighborhoods GeoJSON."""
        self._spinner.hide_loading()
        self._open_map_picker_dialog(neighborhoods_geojson)

    def _on_neighborhoods_geojson_error(self, error_msg):
        """Callback: neighborhoods fetch failed, open dialog with empty GeoJSON."""
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.buildings.load_error"), Toast.ERROR)
        logger.warning(f"Failed to load neighborhoods for map: {error_msg}")
        self._open_map_picker_dialog('{"type":"FeatureCollection","features":[]}')

    def _open_map_picker_dialog(self, neighborhoods_geojson):
        """Open the map picker dialog with precomputed params and neighborhoods data."""
        from ui.components.map_picker_dialog_v2 import MapPickerDialog

        params = self._map_picker_params

        dialog = MapPickerDialog(
            initial_lat=params["initial_lat"],
            initial_lon=params["initial_lon"],
            initial_zoom=params["initial_zoom"],
            allow_polygon=params["allow_polygon"],
            initial_bounds=params["initial_bounds"],
            neighborhoods_geojson=neighborhoods_geojson,
            selected_neighborhood_code=params["selected_neighborhood_code"],
            db=self.building_controller.db,
            skip_fit_bounds=self._has_map_coordinates,
            existing_polygon_wkt=self._polygon_wkt,
            parent=self
        )

        if dialog.exec_():
            result = dialog.get_result()

            # Handle Polygon geometry FIRST (before checking point)
            if result and 'polygon_wkt' in result and result['polygon_wkt']:
                polygon_wkt = result['polygon_wkt']
                self._polygon_wkt = polygon_wkt
                self._has_map_coordinates = True

                centroid_lat = result.get('latitude', 36.2)
                centroid_lon = result.get('longitude', 37.15)
                self.latitude_spin.setValue(centroid_lat)
                self.longitude_spin.setValue(centroid_lon)

                self._detect_and_update_neighborhood(polygon_wkt)

                # Show success message
                self.location_status_label.setText(
                tr("page.add_building.polygon_drawn").format(lat=f"{centroid_lat:.6f}", lon=f"{centroid_lon:.6f}")
                )
                self.location_status_label.setStyleSheet(
                    f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;"
                )
                self.geometry_type_label.setText(tr("page.add_building.type_polygon"))
                logger.info(f"Polygon drawn and saved: {polygon_wkt[:100]}...")

            # Handle Point geometry (only if NOT polygon)
            elif result and 'latitude' in result and 'longitude' in result:
                lat = result['latitude']
                lon = result['longitude']

                self.latitude_spin.setValue(lat)
                self.longitude_spin.setValue(lon)
                self._polygon_wkt = None
                self._has_map_coordinates = True

                geometry_wkt = f"POINT({lon} {lat})"
                self._detect_and_update_neighborhood(geometry_wkt)

                self.location_status_label.setText(
                    tr("page.add_building.location_set_coords").format(lat=f"{lat:.6f}", lon=f"{lon:.6f}")
                )
                self.location_status_label.setStyleSheet(
                    f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;"
                )
                self.geometry_type_label.setText(tr("page.add_building.type_point"))

    def _populate_data(self):
        """Populate form with existing building data."""
        if not self.building:
            return

        # GG: تحميل رمز المحافظة (Governorate) - select in combo by data
        if hasattr(self.building, 'governorate_code') and self.building.governorate_code:
            idx = self.governorate_combo.findData(self.building.governorate_code)
            if idx >= 0:
                self.governorate_combo.setCurrentIndex(idx)

        # DD: تحميل رمز المنطقة (District) - select in combo by data
        if hasattr(self.building, 'district_code') and self.building.district_code:
            idx = self.district_combo.findData(self.building.district_code)
            if idx >= 0:
                self.district_combo.setCurrentIndex(idx)

        # SS: تحميل المنطقة الفرعية (Subdistrict) - select in combo by data
        if hasattr(self.building, 'subdistrict_code') and self.building.subdistrict_code:
            idx = self.subdistrict_combo.findData(self.building.subdistrict_code)
            if idx >= 0:
                self.subdistrict_combo.setCurrentIndex(idx)

        # CCC: تحميل رمز المجتمع/المدينة (Community) - select in combo by data
        if hasattr(self.building, 'community_code') and self.building.community_code:
            idx = self.community_combo.findData(self.building.community_code)
            if idx >= 0:
                self.community_combo.setCurrentIndex(idx)

        # NNN: Load neighborhood — must reload neighborhoods for correct community first
        # (cascading handlers load neighborhoods for community[index=1], not the actual community)
        self._load_neighborhoods_from_api()
        if hasattr(self.building, 'neighborhood_code') and self.building.neighborhood_code:
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
        self.residential_spin.setValue(self.building.number_of_apartments or 0)
        self.non_residential_spin.setValue(self.building.number_of_shops or 0)
        if hasattr(self, 'floors_spin'):
            self.floors_spin.setValue(self.building.number_of_floors or 1)
        self._update_total_units()

        # تحميل الأوصاف
        if getattr(self.building, 'general_description', None):
            self.general_desc.setText(self.building.general_description)

        if self.building.latitude:
            self.latitude_spin.setValue(self.building.latitude)
            self.location_status_label.setText(tr("page.add_building.location_set"))
            self.location_status_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR}; font-size: 10pt;")
        if self.building.longitude:
            self.longitude_spin.setValue(self.building.longitude)
        if self.building.latitude and self.building.longitude:
            self._has_map_coordinates = True

        if hasattr(self.building, 'geo_location') and self.building.geo_location:
            self._polygon_wkt = self.building.geo_location
            self.geometry_type_label.setText(tr("page.add_building.coordinates_type_polygon"))

        # تحديث رمز البناء
        self._update_building_id()

        # Load document thumbnails if building has a UUID
        building_uuid = getattr(self.building, 'building_uuid', None)
        if building_uuid:
            self._load_building_documents(building_uuid)

    def _show_validation_error_dialog(self, errors):
        """Display validation errors via notification bar."""
        message = " | ".join(errors) if len(errors) <= 3 else "\n".join(errors)
        ErrorHandler.show_error(self, message)

    def _show_duplicate_error_dialog(self, building_id):
        """Display duplicate building error via BottomSheet with review option."""
        from ui.components.bottom_sheet import BottomSheet
        msg = tr('dialog.buildings.duplicate_msg_exists', building_id=building_id)
        sheet = BottomSheet(self)
        sheet.choice_made.connect(lambda choice: self._on_duplicate_choice(choice))
        sheet.show_choices(
            tr("dialog.buildings.duplicate_number"),
            [
                (tr("dialog.buildings.review_existing"), tr("dialog.buildings.review_existing")),
                (tr("button.ok"), tr("button.ok")),
            ]
        )
        ErrorHandler.show_warning(self, msg)

    def _on_duplicate_choice(self, choice):
        """Handle duplicate building dialog choice."""
        if choice == tr("dialog.buildings.review_existing"):
            self.cancelled.emit()
        # يمكن إضافة منطق للبحث عن البناء وعرضه

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """
        Create a spinbox widget with icon arrows on the RIGHT side.
        Same pattern as unit_dialog.py.

        Args:
            spinbox: The QSpinBox to wrap with custom arrows

        Returns:
            QFrame containing the spinbox with custom arrow controls
        """
        # Container frame - توحيد الحجم 45px height
        container = QFrame()
        container.setFixedHeight(ScreenScale.h(45))
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
        arrow_container.setFixedWidth(ScreenScale.w(30))
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
        up_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(22))
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
        down_label.setFixedSize(ScreenScale.w(30), ScreenScale.h(22))
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

    def _set_save_loading(self, loading, text=""):
        """Set save button loading state."""
        btn = self._save_btn
        if loading:
            btn._original_text = btn.text()
            btn.setText(text or tr("component.loading.default"))
            btn.setEnabled(False)
            btn.setCursor(Qt.WaitCursor)
        else:
            btn.setText(getattr(btn, '_original_text', " " + tr("button.save")))
            btn.setEnabled(True)
            btn.setCursor(Qt.PointingHandCursor)

    def _on_save(self):
        """Validate and save."""
        data = self.get_data()

        result = self.validation_service.validate_building(data)

        if not result.is_valid:
            self._show_validation_error_dialog(result.errors)
            return

        if result.warnings:
            if not ErrorHandler.confirm(
                self,
                "\n".join(result.warnings) + "\n\n" + tr("dialog.buildings.continue_question"),
                tr("dialog.buildings.warnings")
            ):
                return

        self._set_save_loading(True, tr("page.add_building.saving"))
        try:
            if self.building:
                result = self.building_controller.update_building(
                    self.building.building_uuid,
                    data,
                    existing_building=self.building
                )

                if result.success:
                    Toast.show_toast(self.window(), tr("dialog.buildings.building_updated", building_id=self.building.building_id), Toast.SUCCESS)
                    self.saved.emit()
                else:
                    error_msg = result.message
                    if hasattr(result, 'validation_errors') and result.validation_errors:
                        error_msg += "\n" + "\n".join(result.validation_errors)
                    self._show_validation_error_dialog([error_msg])
            else:
                result = self.building_controller.create_building(data)

                if result.success:
                    building = result.data
                    Toast.show_toast(self.window(), tr("dialog.buildings.building_added", building_id=building.building_id), Toast.SUCCESS)
                    self.saved.emit()
                else:
                    error_msg = result.message
                    if hasattr(result, 'validation_errors') and result.validation_errors:
                        error_msg += "\n" + "\n".join(result.validation_errors)

                    if "already exists" in error_msg or "موجود" in error_msg:
                        self._show_duplicate_error_dialog(data['building_id'])
                    else:
                        self._show_validation_error_dialog([error_msg])

        except Exception as e:
            logger.error(f"Failed to save building: {e}")
            self._show_validation_error_dialog([tr("dialog.buildings.save_failed", error=str(e))])
        finally:
            self._set_save_loading(False)

    def get_data(self):
        """Get form data."""
        # استخراج building_id من الـ label (بعد "رمز البناء: ")
        building_id_text = self.building_id_label.text()
        if ":" in building_id_text:
            building_id = building_id_text.split(":", 1)[1].strip()
        else:
            building_id = building_id_text.strip()

        # Lookup names from selected codes via DivisionsService
        gov_code = self._get_gov_code()
        dist_code = self._get_district_code()
        subdist_code = self._get_subdistrict_code()
        comm_code = self._get_community_code()
        neigh_code = self._get_neighborhood_code()

        gov_en, gov_ar = self._divisions.get_governorate_name(gov_code)
        dist_en, dist_ar = self._divisions.get_district_name(gov_code, dist_code)
        subdist_en, subdist_ar = self._divisions.get_subdistrict_name(gov_code, dist_code, subdist_code)
        comm_en, comm_ar = self._divisions.get_community_name(gov_code, dist_code, subdist_code, comm_code)

        neigh_name_en = self._get_neighborhood_name_en()
        neigh_name_ar = self._get_neighborhood_name_ar()

        data = {
            "building_id": building_id,
            # GG: Governorate
            "governorate_code": gov_code,
            "governorate_name": gov_en,
            "governorate_name_ar": gov_ar,
            # DD: District
            "district_code": dist_code,
            "district_name": dist_en,
            "district_name_ar": dist_ar,
            # SS: Subdistrict
            "subdistrict_code": subdist_code,
            "subdistrict_name": subdist_en,
            "subdistrict_name_ar": subdist_ar,
            # CCC: Community
            "community_code": comm_code,
            "community_name": comm_en,
            "community_name_ar": comm_ar,
            # NNN: Neighborhood
            "neighborhood_code": neigh_code,
            "neighborhood_name": neigh_name_en,
            "neighborhood_name_ar": neigh_name_ar,
            # BBBBB: Building Number
            "building_number": self.building_number.text().strip(),
            # Building Details
            "building_type": self.type_combo.currentData(),
            "building_status": self.status_combo.currentData(),
            "number_of_apartments": self.residential_spin.value(),
            "number_of_shops": self.non_residential_spin.value(),
            "number_of_units": self.residential_spin.value() + self.non_residential_spin.value(),
            "number_of_floors": self.floors_spin.value() if hasattr(self, 'floors_spin') else 1,
            # Coordinates
            "latitude": self.latitude_spin.value() if self.latitude_spin.value() != 0 else None,
            "longitude": self.longitude_spin.value() if self.longitude_spin.value() != 0 else None,
            # Location descriptions (QTextEdit uses toPlainText())
            "general_description": self.general_desc.toPlainText().strip(),
            "location_description": "",
        }

        if self._polygon_wkt:
            data["geo_location"] = self._polygon_wkt

        return data

    def _set_neighborhood_by_code(self, code: str):
        """Set neighborhood combo selection by code."""
        self.neighborhood_combo.blockSignals(True)
        idx = self.neighborhood_combo.findData(code)
        if idx >= 0:
            self.neighborhood_combo.setCurrentIndex(idx)
        self.neighborhood_combo.blockSignals(False)

    def _on_neighborhood_changed_by_user(self):
        """Warn if map coordinates already set and don't match new neighborhood."""
        if not self._has_map_coordinates:
            return

        new_code = self._get_neighborhood_code()
        if not new_code:
            return

        try:
            from services.neighborhood_geocoder import NeighborhoodGeocoder
            geocoder = NeighborhoodGeocoder()
            lon = self.longitude_spin.value()
            lat = self.latitude_spin.value()
            detected = geocoder.find_neighborhood(f"POINT({lon} {lat})")

            if detected and detected.code != new_code:
                ErrorHandler.show_warning(
                    self,
                    tr("dialog.buildings.location_neighborhood_mismatch",
                       neighborhood=detected.name_ar, code=detected.code),
                    tr("dialog.buildings.alert")
                )
        except Exception:
            pass

    def _on_governorate_changed(self):
        """Cascading: governorate → fill districts."""
        gov_code = self._get_gov_code()
        self.district_combo.blockSignals(True)
        self.district_combo.clear()
        self.district_combo.addItem(tr("page.add_building.select_district"), "")
        if gov_code:
            for code, en, ar in self._divisions.get_districts(gov_code):
                self.district_combo.addItem(f"{code} - {ar}", code)
            if self.district_combo.count() > 1:
                self.district_combo.setCurrentIndex(1)
        self.district_combo.blockSignals(False)
        self._on_district_changed()

    def _on_district_changed(self):
        """Cascading: district → fill subdistricts."""
        gov_code = self._get_gov_code()
        dist_code = self._get_district_code()
        self.subdistrict_combo.blockSignals(True)
        self.subdistrict_combo.clear()
        self.subdistrict_combo.addItem(tr("page.add_building.select_subdistrict"), "")
        if gov_code and dist_code:
            for code, en, ar in self._divisions.get_subdistricts(gov_code, dist_code):
                self.subdistrict_combo.addItem(f"{code} - {ar}", code)
            if self.subdistrict_combo.count() > 1:
                self.subdistrict_combo.setCurrentIndex(1)
        self.subdistrict_combo.blockSignals(False)
        self._on_subdistrict_changed()

    def _on_subdistrict_changed(self):
        """Cascading: subdistrict → fill communities."""
        gov_code = self._get_gov_code()
        dist_code = self._get_district_code()
        subdist_code = self._get_subdistrict_code()
        self.community_combo.blockSignals(True)
        self.community_combo.clear()
        self.community_combo.addItem(tr("page.add_building.select_community"), "")
        if gov_code and dist_code and subdist_code:
            for code, en, ar in self._divisions.get_communities(gov_code, dist_code, subdist_code):
                self.community_combo.addItem(f"{code} - {ar}", code)
            if self.community_combo.count() > 1:
                self.community_combo.setCurrentIndex(1)
        self.community_combo.blockSignals(False)
        self._load_neighborhoods_from_api()
        self._update_building_id()
        self._validate_building_id_realtime()

    def _load_neighborhoods_from_api(self):
        """Load neighborhoods from backend API (non-blocking)."""
        gov_code = self._get_gov_code()
        dist_code = self._get_district_code()
        subdist_code = self._get_subdistrict_code()
        comm_code = self._get_community_code()

        self.neighborhood_combo.blockSignals(True)
        self.neighborhood_combo.clear()
        self.neighborhood_combo.addItem(tr("page.add_building.select_neighborhood"), "")
        self.neighborhood_combo.blockSignals(False)

        if gov_code and dist_code and subdist_code and comm_code:
            self._spinner.show_loading(tr("component.loading.default"))
            self._neighborhoods_api_worker = ApiWorker(
                self._fetch_neighborhoods_bg, gov_code, dist_code, subdist_code, comm_code
            )
            self._neighborhoods_api_worker.finished.connect(self._on_neighborhoods_api_loaded)
            self._neighborhoods_api_worker.error.connect(self._on_neighborhoods_api_error)
            self._neighborhoods_api_worker.start()

    def _fetch_neighborhoods_bg(self, gov_code, dist_code, subdist_code, comm_code):
        """Background: fetch neighborhoods from API."""
        api_client = get_api_client()
        if api_client is not None:
            return api_client.get_neighborhoods(
                governorate_code=gov_code,
                district_code=dist_code,
                subdistrict_code=subdist_code,
                community_code=comm_code
            )
        return []

    def _on_neighborhoods_api_loaded(self, neighborhoods):
        """Callback: populate neighborhood combo with API results."""
        self._spinner.hide_loading()
        if not neighborhoods:
            neighborhoods = []
        self._neighborhoods_cache = neighborhoods
        self.neighborhood_combo.blockSignals(True)
        for n in neighborhoods:
            code = n.get("neighborhoodCode", n.get("code", ""))
            name_ar = n.get("nameArabic", n.get("name_ar", ""))
            self.neighborhood_combo.addItem(f"{code} - {name_ar}", code)
        if self.neighborhood_combo.count() > 1:
            self.neighborhood_combo.setCurrentIndex(1)
        self.neighborhood_combo.blockSignals(False)

    def _on_neighborhoods_api_error(self, error_msg):
        """Callback: neighborhoods fetch failed."""
        self._spinner.hide_loading()
        logger.warning(f"Failed to load neighborhoods from API: {error_msg}")

    def _get_neighborhood_name_ar(self) -> str:
        """Get Arabic name from cached API neighborhoods."""
        code = self._get_neighborhood_code()
        for n in getattr(self, '_neighborhoods_cache', []):
            if n.get("neighborhoodCode") == code:
                return n.get("nameArabic", "")
        return ""

    def _get_neighborhood_name_en(self) -> str:
        """Get English name from cached API neighborhoods."""
        code = self._get_neighborhood_code()
        for n in getattr(self, '_neighborhoods_cache', []):
            if n.get("neighborhoodCode") == code:
                return n.get("nameEnglish", "")
        return ""

    def _detect_and_update_neighborhood(self, geometry_wkt: str):
        """
        Detect neighborhood from geometry and update form field.

        Behavior:
        - No neighborhood selected: silently set detected neighborhood
        - Same neighborhood: no action
        - Different neighborhood: confirm dialog before overriding
        """
        try:
            from services.neighborhood_geocoder import NeighborhoodGeocoder

            geocoder = NeighborhoodGeocoder()
            detected = geocoder.find_neighborhood(geometry_wkt)

            if not detected:
                logger.debug("No neighborhood detected from geometry")
                return

            current_code = self._get_neighborhood_code()

            if not current_code:
                self._set_neighborhood_by_code(detected.code)
                self._update_building_id()
                Toast.show_toast(
                    self,
                    tr("dialog.buildings.neighborhood_auto_detected",
                       neighborhood=detected.name_ar, code=detected.code),
                    Toast.INFO
                )
            elif current_code != detected.code:
                current_neighborhood = geocoder.get_neighborhood_by_code(current_code)
                current_name = current_neighborhood.name_ar if current_neighborhood else current_code

                if ErrorHandler.confirm(
                    self,
                    tr("dialog.buildings.neighborhood_mismatch_confirm",
                       current_name=current_name, current_code=current_code,
                       detected_name=detected.name_ar, detected_code=detected.code),
                    tr("dialog.buildings.different_neighborhood")
                ):
                    self._set_neighborhood_by_code(detected.code)
                    self._update_building_id()

        except Exception as e:
            logger.error(f"Failed to detect neighborhood: {e}", exc_info=True)

    def _parse_wkt_bounds(self, wkt: str):
        """Extract [[min_lat, min_lng], [max_lat, max_lng]] from any WKT geometry."""
        import re
        if not wkt:
            return None
        try:
            coords = re.findall(r'([-\d.]+)\s+([-\d.]+)', wkt)
            if coords:
                lngs = [float(c[0]) for c in coords]
                lats = [float(c[1]) for c in coords]
                return [[min(lats), min(lngs)], [max(lats), max(lngs)]]
        except Exception:
            pass
        return None

    def _get_neighborhood_center(self, neighborhood_code: str) -> Optional[Tuple[float, float]]:
        """Get center coordinates of neighborhood from _neighborhoods_cache."""
        for n in getattr(self, '_neighborhoods_cache', []):
            if n.get('neighborhoodCode') == neighborhood_code:
                wkt = n.get('boundaries') or n.get('boundary') or n.get('boundaryWkt', '')
                result = self._parse_wkt_centroid(wkt)
                if result:
                    logger.info(f"Neighborhood center from cache: {neighborhood_code} -> {result}")
                    return result
        logger.warning(f"Neighborhood not found in cache: {neighborhood_code}")
        return None

    def _get_neighborhood_bounds(self, neighborhood_code: str):
        """Get Leaflet bounds [[s,w],[n,e]] from _neighborhoods_cache."""
        for n in getattr(self, '_neighborhoods_cache', []):
            if n.get('neighborhoodCode') == neighborhood_code:
                wkt = n.get('boundaries') or n.get('boundary') or n.get('boundaryWkt', '')
                result = self._parse_wkt_bounds(wkt)
                if result:
                    logger.info(f"Neighborhood bounds from cache: {neighborhood_code} -> {result}")
                    return result
        logger.warning(f"Neighborhood bounds not found in cache: {neighborhood_code}")
        return None

    def _build_neighborhoods_geojson(self) -> str:
        """Load neighborhoods from Backend API using Config map bounds."""
        try:
            from services.api_client import get_api_client
            from app.config import Config
            api = get_api_client()

            neighborhoods = api.get_neighborhoods_by_bounds(
                sw_lat=Config.MAP_BOUNDS_MIN_LAT,
                sw_lng=Config.MAP_BOUNDS_MIN_LNG,
                ne_lat=Config.MAP_BOUNDS_MAX_LAT,
                ne_lng=Config.MAP_BOUNDS_MAX_LNG
            )

            if neighborhoods:
                geojson = self._neighborhoods_api_to_geojson(neighborhoods)
                if geojson:
                    logger.info(f"Loaded {len(neighborhoods)} neighborhoods from API")
                    return geojson
        except Exception as e:
            logger.warning(f"API neighborhoods failed: {e}")

        return '{"type":"FeatureCollection","features":[]}'

    def _neighborhoods_api_to_geojson(self, neighborhoods: list) -> str:
        """Convert API neighborhood response (with WKT boundaries) to GeoJSON."""
        import json
        features = []
        for n in neighborhoods:
            name_ar = n.get('nameArabic', n.get('name_ar', ''))
            name_en = n.get('nameEnglish', n.get('name_en', ''))
            code = n.get('neighborhoodCode', n.get('fullCode', n.get('code', '')))

            # Use API-provided center if available (more accurate than computing from WKT)
            center_lat = n.get('centerLatitude') or n.get('center_lat')
            center_lng = n.get('centerLongitude') or n.get('center_lng')

            if not center_lat or not center_lng:
                wkt = n.get('boundaryWkt', n.get('boundaries', n.get('boundary', '')))
                if not wkt:
                    continue
                centroid = self._parse_wkt_centroid(wkt)
                if not centroid:
                    continue
                center_lat, center_lng = centroid

            features.append({
                "type": "Feature",
                "properties": {
                    "code": code,
                    "name_ar": name_ar,
                    "name_en": name_en,
                    "center_lat": center_lat,
                    "center_lng": center_lng
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [center_lng, center_lat]
                }
            })

        if not features:
            return None
        return json.dumps({"type": "FeatureCollection", "features": features})

    def _parse_wkt_centroid(self, wkt: str):
        """Extract centroid from any WKT geometry string."""
        import re
        if not wkt:
            return None
        try:
            coords = re.findall(r'([-\d.]+)\s+([-\d.]+)', wkt)
            if coords:
                lngs = [float(c[0]) for c in coords]
                lats = [float(c[1]) for c in coords]
                return sum(lats) / len(lats), sum(lngs) / len(lngs)
        except Exception:
            pass
        return None

class FilterableHeaderView(QHeaderView):
    """
    Custom header view that displays down.png icon AFTER text (RTL-compatible).

    Reusable header for any table with filterable columns.
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


class _BuildingCard(AnimatedCard):
    """Building card with code, type, status, neighborhood info."""

    view_building = pyqtSignal(object)

    _STATUS_COLORS = {
        "intact": "#10B981",
        "damaged": "#F59E0B",
        "destroyed": "#EF4444",
    }
    _STATUS_STYLES = {
        "intact": {"bg": "#ECFDF5", "fg": "#065F46", "border": "#6EE7B7"},
        "damaged": {"bg": "#FFFBEB", "fg": "#92400E", "border": "#FCD34D"},
        "destroyed": {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
    }

    def __init__(self, building, parent=None):
        self._building = building
        status_key = self._get_status_key(building.building_status)
        color = self._STATUS_COLORS.get(status_key, "#3890DF")
        super().__init__(parent, card_height=110, status_color=color)

    def _get_status_key(self, status):
        if status is None:
            return "intact"
        s = str(status).strip().lower()
        if s in ("1", "intact", "\u0633\u0644\u064a\u0645"):
            return "intact"
        elif s in ("2", "damaged", "\u0645\u062a\u0636\u0631\u0631"):
            return "damaged"
        elif s in ("3", "destroyed", "\u0645\u062f\u0645\u0631"):
            return "destroyed"
        return "intact"

    def _build_content(self, layout):
        from PyQt5.QtWidgets import QHBoxLayout, QLabel
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        from ui.font_utils import create_font, FontManager
        from ui.design_system import Colors
        from services.translation_manager import tr
        from services.display_mappings import get_building_type_display, get_building_status_display

        b = self._building

        # Row 1: Building code + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        code_label = QLabel(b.building_id_formatted or b.building_id or "N/A")
        code_label.setFont(create_font(size=13, weight=QFont.Bold))
        code_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        code_label.setMaximumWidth(ScreenScale.w(400))
        row1.addWidget(code_label)
        row1.addStretch()

        # Status badge
        status_key = self._get_status_key(b.building_status)
        style = self._STATUS_STYLES.get(status_key, self._STATUS_STYLES["intact"])
        status_text = get_building_status_display(b.building_status)
        badge = QLabel(status_text)
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(22))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 11px; "
            f"padding: 0 10px; }}"
        )
        row1.addWidget(badge)
        layout.addLayout(row1)

        # Row 2: neighborhood + type + area
        parts = []
        neighborhood = (b.neighborhood_name_ar or b.neighborhood_name or "").strip()
        if neighborhood:
            parts.append(neighborhood)
        btype = get_building_type_display(b.building_type)
        if btype and btype != "-":
            parts.append(btype)
        district = (b.district_name_ar or b.district_name or "").strip()
        if district:
            parts.append(district)

        details_text = " \u2009\u00b7\u2009 ".join(parts) if parts else "-"
        details = QLabel(details_text)
        details.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        details.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(details)

        # Row 3: assignment + lock chips
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)

        chip_style = (
            "QLabel {{ background-color: {bg}; color: {fg}; "
            "border: 1px solid {border}; border-radius: 4px; "
            "padding: 2px 8px; }}"
        )

        # Assignment chip
        is_assigned = getattr(b, 'is_assigned', False)
        if is_assigned:
            chip = QLabel(tr("building.assigned"))
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#EEF2FF", fg="#4338CA", border="#E0E7FF"))
            chips_row.addWidget(chip)

        # Lock chip
        is_locked = getattr(b, 'is_locked', False)
        if is_locked:
            chip = QLabel(tr("building.locked"))
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#FEF2F2", fg="#991B1B", border="#FCA5A5"))
            chips_row.addWidget(chip)

        # Date chip
        if b.created_at:
            chip = QLabel(b.created_at.strftime("%d/%m/%Y"))
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#F0FDF4", fg="#15803D", border="#DCFCE7"))
            chips_row.addWidget(chip)

        chips_row.addStretch()
        layout.addLayout(chips_row)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.view_building.emit(self._building)


class BuildingsListPage(QWidget):
    """
    Buildings List Page with Table
    """

    view_building = pyqtSignal(object)
    edit_building = pyqtSignal(object)

    def __init__(self, building_controller, export_service, i18n, parent=None):
        super().__init__(parent)
        self.building_controller = building_controller
        self.export_service = export_service
        self.i18n = i18n
        self.map_view = None
        self._buildings = []  # Store buildings list
        self._all_buildings = []  # Store unfiltered buildings
        self._current_page = 1
        self._rows_per_page = 11
        self._total_pages = 1

        # Active filters (same as field_work_preparation_page)
        self._active_filters = {
            'area': None,           # المنطقة/district (column 2)
            'neighborhood': None,   # الحي/neighborhood (column 3)
            'building_type': None,  # نوع البناء (column 4)
            'building_status': None # حالة البناء (column 5)
        }
        self._neighborhoods_api_cache = []  # cached from API on first filter use
        self._load_worker = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup buildings list UI."""
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.buildings.title"))

        self._stat_total = StatPill(tr("page.buildings.total"))
        self._header.add_stat_pill(self._stat_total)

        layout.addWidget(self._header)

        # Accent line between header and content
        self._accent_line = AccentLine()
        layout.addWidget(self._accent_line)

        # Light content area
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(StyleManager.page_background())
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        content_layout.setSpacing(12)

        # Stacked widget: cards view + empty state
        self._stack = QStackedWidget()

        # Page 0: Scroll area with cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(StyleManager.scrollbar())
        scroll.setFrameShape(QFrame.NoFrame)

        cards_container = QWidget()
        cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()
        scroll.setWidget(cards_container)
        self._stack.addWidget(scroll)

        # Page 1: Empty state
        self._empty_state = EmptyStateAnimated(
            title=tr("page.buildings.no_matching_data"),
            description=tr("page.buildings.empty_description") if hasattr(tr, '__call__') else "",
        )
        self._stack.addWidget(self._empty_state)

        content_layout.addWidget(self._stack)

        # Pagination bar
        self._pagination_bar = QHBoxLayout()
        self._pagination_bar.setContentsMargins(0, 8, 0, 0)
        self._pagination_bar.addStretch()

        self._prev_btn = QPushButton("\u276E")
        self._prev_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._prev_btn.setStyleSheet(StyleManager.pagination_button())
        self._prev_btn.clicked.connect(lambda: self._go_to_page(self._current_page - 1))
        self._pagination_bar.addWidget(self._prev_btn)

        self._page_info = QLabel("1-0 / 0")
        self._page_info.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._page_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self._pagination_bar.addWidget(self._page_info)

        self._next_btn = QPushButton("\u276F")
        self._next_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(28))
        self._next_btn.setStyleSheet(StyleManager.pagination_button())
        self._next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))
        self._pagination_bar.addWidget(self._next_btn)

        content_layout.addLayout(self._pagination_bar)

        # Shimmer timer
        self._card_widgets = []
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        layout.addWidget(content_wrapper)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def refresh(self):
        """Refresh list."""
        logger.debug("Refreshing buildings list")
        self._load_buildings()

    def configure_for_role(self, role: str):
        """Store user role for lock permission checks."""
        self._user_role = role

    def _load_buildings(self):
        """Load buildings asynchronously."""
        self._clear_cards()
        self._spinner.show_loading(tr("page.buildings.loading"))

        self._load_worker = ApiWorker(self._fetch_buildings_bg)
        self._load_worker.finished.connect(self._on_buildings_loaded)
        self._load_worker.error.connect(self._on_buildings_load_error)
        self._load_worker.start()

    def _fetch_buildings_bg(self):
        """Background thread: load from controller."""
        return self.building_controller.load_buildings()

    def _on_buildings_loaded(self, result):
        """Main thread callback after buildings loaded."""
        self._spinner.hide_loading()
        if result.success:
            self._all_buildings = result.data
        else:
            Toast.show_toast(self, tr("page.buildings.load_error"), Toast.ERROR)
            logger.error(f"Failed to load buildings: {result.message}")
            self._all_buildings = []

        self._populate_table_from_buildings()

    def _on_buildings_load_error(self, error_msg):
        """Handle background loading error."""
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.buildings.load_error"), Toast.ERROR)
        logger.error(f"Background load failed: {error_msg}")
        self._all_buildings = []
        self._stat_total.set_count(0)
        self._populate_table_from_buildings()

    def _populate_table_from_buildings(self):
        """Apply filters, paginate, and create building cards."""
        self._buildings = self._apply_filters(self._all_buildings)
        self._stat_total.set_count(len(self._all_buildings))

        total = len(self._buildings)
        self._total_pages = max(1, (total + self._rows_per_page - 1) // self._rows_per_page)

        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + self._rows_per_page, total)
        page_buildings = self._buildings[start_idx:end_idx]

        # Clear old cards
        self._clear_cards()

        if not page_buildings:
            self._stack.setCurrentIndex(1)  # Show empty state
            self._update_pagination_info(0, 0, total)
            return

        self._stack.setCurrentIndex(0)  # Show cards

        for b in page_buildings:
            card = _BuildingCard(b)
            card.view_building.connect(self.view_building.emit)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            self._card_widgets.append(card)

        animate_card_entrance(self._card_widgets)
        if not self._shimmer_timer.isActive():
            self._shimmer_timer.start()

        self._update_pagination_info(start_idx + 1, end_idx, total)

    def _on_header_clicked(self, logical_index: int):
        """
        Handle header click to show filter menu.

        Filterable columns:
        - Column 2: المنطقة (District)
        - Column 3: الحي (Neighborhood)
        - Column 4: نوع البناء (Building Type)
        - Column 5: حالة البناء (Building Status)
        """
        # Only columns 2, 3, 4, 5 are filterable
        if logical_index not in [2, 3, 4, 5]:
            return

        self._show_filter_menu(logical_index)

    def _show_filter_menu(self, column_index: int):
        """
        Show filter menu for the clicked column.

        Args:
            column_index: Index of the column (2=Area, 3=Type, 4=Status)
        """
        # Get unique values for this column from all buildings
        unique_values = set()
        filter_key = None

        if column_index == 2:  # المنطقة (district)
            filter_key = 'area'
            for building in self._all_buildings:
                area = (building.district_name_ar or building.district_name or '').strip()
                if area:
                    unique_values.add(area)
        elif column_index == 3:  # الحي (neighborhood - loaded from API)
            filter_key = 'neighborhood'
            if not self._neighborhoods_api_cache:
                # First call: fetch in background, then show menu
                self._neighborhoods_filter_worker = ApiWorker(
                    self._fetch_neighborhoods_for_filter_bg
                )
                self._neighborhoods_filter_worker.finished.connect(
                    self._on_neighborhoods_for_filter_loaded
                )
                self._neighborhoods_filter_worker.error.connect(
                    self._on_neighborhoods_for_filter_error
                )
                self._neighborhoods_filter_worker.start()
                return
            neighborhoods = self._neighborhoods_api_cache
            for n in neighborhoods:
                code = n.get("neighborhoodCode", n.get("code", ""))
                name_ar = n.get("nameArabic", n.get("name_ar", ""))
                if code and name_ar:
                    unique_values.add((code, name_ar))
        elif column_index == 4:  # نوع البناء
            filter_key = 'building_type'
            for code, label in get_building_type_options():
                if code:
                    unique_values.add((code, label))
        elif column_index == 5:  # حالة البناء
            filter_key = 'building_status'
            for code, label in get_building_status_options():
                if code:
                    unique_values.add((code, label))

        if not unique_values:
            return

        # Create menu
        from PyQt5.QtWidgets import QMenu, QAction
        menu = QMenu(self)
        menu.setLayoutDirection(get_layout_direction())
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
        clear_action = QAction(tr("filter.show_all"), self)
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
            elif column_index == 3 and self._active_filters['neighborhood'] == (value if isinstance(value, str) else value[0]):
                action.setCheckable(True)
                action.setChecked(True)
            elif column_index == 4 and self._active_filters['building_type'] == (value if isinstance(value, str) else value[0]):
                action.setCheckable(True)
                action.setChecked(True)
            elif column_index == 5 and self._active_filters['building_status'] == (value if isinstance(value, str) else value[0]):
                action.setCheckable(True)
                action.setChecked(True)

            menu.addAction(action)

        # Show menu below the specific column header (RTL-compatible positioning)
        inner_table = self._modern_table._table
        header = inner_table.horizontalHeader()

        # Get the visual position of the column (works correctly in RTL)
        x_pos = header.sectionViewportPosition(column_index)

        # Y position: below the header
        y_pos = header.height()

        # Map to global coordinates (relative to table widget, not header)
        pos = inner_table.mapToGlobal(QPoint(x_pos, y_pos))
        menu.exec_(pos)

    def _apply_filter(self, filter_key: str, filter_value):
        """
        Apply filter and reload table.

        Args:
            filter_key: Key in _active_filters dict
            filter_value: Value to filter by (None to clear filter)
        """
        self._active_filters[filter_key] = filter_value
        self._current_page = 1  # Reset to first page
        self._load_buildings()

    def _apply_filters(self, buildings: list) -> list:
        """
        Apply active filters to buildings list.

        Returns:
            Filtered list of buildings
        """
        filtered = buildings

        # Apply area filter (district)
        if self._active_filters['area']:
            filtered = [
                b for b in filtered
                if self._get_building_area(b) == self._active_filters['area']
            ]

        # Apply neighborhood filter
        if self._active_filters['neighborhood']:
            target = self._active_filters['neighborhood']
            filtered = [b for b in filtered if b.neighborhood_code == target]

        # Apply building type filter
        if self._active_filters['building_type']:
            target = self._active_filters['building_type']
            filtered = [
                b for b in filtered
                if self._match_code(b.building_type, target)
            ]

        # Apply building status filter
        if self._active_filters['building_status']:
            target = self._active_filters['building_status']
            filtered = [
                b for b in filtered
                if self._match_code(b.building_status, target)
            ]

        return filtered

    @staticmethod
    def _match_code(value, target):
        if value is None:
            return False
        try:
            return int(value) == int(target)
        except (ValueError, TypeError):
            return str(value).strip().lower() == str(target).strip().lower()

    def _get_building_area(self, building) -> str:
        """Get district name for building (used by area filter)."""
        return (building.district_name_ar or building.district_name or '').strip()

    def _fetch_neighborhoods_for_filter_bg(self):
        """Background: fetch neighborhoods from API for filter menu."""
        from services.api_client import get_api_client
        api = get_api_client()
        if api:
            return api.get_neighborhoods()
        return None

    def _on_neighborhoods_for_filter_loaded(self, result):
        """Callback: neighborhoods fetched, cache and show filter menu."""
        if result:
            self._neighborhoods_api_cache = result
        else:
            self._neighborhoods_api_cache = self._fallback_neighborhoods_from_buildings()
        # Re-trigger the filter menu now that cache is populated
        self._show_filter_menu(3)

    def _on_neighborhoods_for_filter_error(self, error_msg):
        """Callback: neighborhoods fetch failed, use fallback."""
        Toast.show_toast(self, tr("page.buildings.load_error"), Toast.ERROR)
        logger.warning(f"Could not load neighborhoods for filter: {error_msg}")
        self._neighborhoods_api_cache = self._fallback_neighborhoods_from_buildings()
        # Re-trigger the filter menu with fallback data
        self._show_filter_menu(3)

    def _fallback_neighborhoods_from_buildings(self) -> list:
        """Extract unique neighborhoods from already-loaded buildings."""
        seen = {}
        for b in self._all_buildings:
            if b.neighborhood_code and b.neighborhood_name_ar:
                seen[b.neighborhood_code] = b.neighborhood_name_ar
        return [
            {"neighborhoodCode": k, "nameArabic": v} for k, v in seen.items()
        ]

    def _clear_cards(self):
        """Remove all card widgets."""
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            if hasattr(card, '_entrance_anim') and card._entrance_anim:
                try:
                    card._entrance_anim.stop()
                except RuntimeError:
                    pass
            try:
                card.view_building.disconnect()
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_card_shimmer(self):
        """Update shimmer animation on all visible cards."""
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    def _update_pagination_info(self, start, end, total):
        """Update pagination labels and button states."""
        self._page_info.setText(f"{start}-{end} / {total}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    def _go_to_page(self, page):
        """Navigate to a specific page."""
        if 1 <= page <= self._total_pages:
            self._current_page = page
            self._populate_table_from_buildings()

    def _on_page_changed(self, page):
        """Handle page change."""
        self._current_page = page
        self._populate_table_from_buildings()

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
                selected_building=building,
                parent=self
            )
        else:
            Toast.show_toast(self, tr("dialog.buildings.no_coordinates"), Toast.WARNING)

    def _on_toggle_lock(self, building: Building):
        """Toggle building lock state with confirmation."""
        if getattr(self, '_user_role', None) not in ('admin', 'data_manager'):
            return
        is_locked = getattr(building, 'is_locked', False)
        msg_key = "page.buildings.confirm_unlock" if is_locked else "page.buildings.confirm_lock"
        title_key = "building.action.unlock" if is_locked else "building.action.lock"

        if not ErrorHandler.confirm(self, tr(msg_key), tr(title_key)):
            return

        new_lock_state = not is_locked
        op_result = self.building_controller.toggle_building_lock(
            building.building_uuid or building.building_id,
            new_lock_state
        )
        if op_result.success:
            Toast.show_toast(self, tr("building.lock_success"), Toast.SUCCESS)
            self._load_buildings()
        else:
            Toast.show_toast(self, tr("building.lock_failed"), Toast.ERROR)

    def _on_delete_building(self, building: Building):
        """Delete building with confirmation dialog."""
        if not ErrorHandler.confirm(
            self,
            tr("dialog.buildings.delete_message", building_id=building.building_id),
            tr("dialog.buildings.confirm_delete")
        ):
            return

        try:
            result = self.building_controller.delete_building(building.building_uuid)

            if result.success:
                Toast.show_toast(self, tr("dialog.buildings.building_deleted", building_id=building.building_id), Toast.SUCCESS)
                self._load_buildings()
            else:
                raise Exception(result.message or result.message_ar)

        except Exception as e:
            logger.error(f"Failed to delete building: {e}")
            ErrorHandler.show_error(
                self,
                tr("dialog.buildings.delete_error_message", error=str(e))
            )

    def update_language(self, is_arabic: bool):
        """Update language."""
        self._load_buildings()


class BuildingsPage(QWidget):
    """
    Main Buildings Page - QStackedWidget container

    Supports both API and local database backends based on Config.DATA_PROVIDER.
    Set DATA_PROVIDER = "http" in config to use API backend.
    """

    view_building = pyqtSignal(object)

    def __init__(self, db: Database = None, i18n: I18n = None, parent=None, **kwargs):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_controller = BuildingController(db)
        self.export_service = ExportService(db) if db else None

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
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
        self.stacked.addWidget(self.list_page)

        # Page 1: Add/Edit (created on demand)
        self.form_page = None

        layout.addWidget(self.stacked)

    def refresh(self, data=None):
        """Refresh."""
        logger.debug("Refreshing buildings page")
        self.list_page.refresh()
        self.stacked.setCurrentIndex(0)

    def configure_for_role(self, role: str):
        """Delegate role configuration to inner list page."""
        self.list_page.configure_for_role(role)

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
        if self.form_page and hasattr(self.form_page, 'update_language'):
            self.form_page.update_language(is_arabic)
