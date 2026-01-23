# -*- coding: utf-8 -*-
"""
Building Selection Step - Step 1 of Office Survey Wizard.

Allows user to:
- Search for existing buildings
- View building on map
- Select a building to proceed
"""

from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QFrame, QListWidget, QListWidgetItem, QToolButton,
    QSizePolicy, QLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from controllers.building_controller import BuildingController
from models.building import Building
from utils.logger import get_logger
from ui.font_utils import FontManager

logger = get_logger(__name__)

# Check for WebEngine availability (for map dialog)
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBENGINE = False
    HAS_WEBCHANNEL = False


class BuildingSelectionStep(BaseStep):
    """
    Step 1: Building Selection.

    User can search for buildings by ID or address and select one.
    UI copied from office_survey_wizard.py _create_building_step() - exact match.
    """

    def __init__(self, context: SurveyContext, parent=None):
        """Initialize the step."""
        super().__init__(context, parent)
        self.building_controller = BuildingController(self.context.db)
        self.selected_building: Optional[Building] = None

    def setup_ui(self):
        """
        Setup the step's UI.

        IMPORTANT: No horizontal padding here - the wizard handles it (131px).
        Only vertical spacing for step content.
        """
        widget = self  # Use self as the widget since BaseStep already has main_layout
        widget.setLayoutDirection(Qt.RightToLeft)

        layout = self.main_layout
        # No horizontal padding - wizard applies 131px (DRY principle)
        # Only vertical spacing between elements
        layout.setContentsMargins(0, 16, 0, 16)  # Top: 16px, Bottom: 16px
        layout.setSpacing(16)

        # ===== Card: Building Data =====
        card = QFrame()
        card.setObjectName("buildingCard")
        card.setStyleSheet("""
            QFrame#buildingCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card_layout.setSizeConstraint(QLayout.SetMinimumSize)

        # Header (title + subtitle)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(1)
        title = QLabel("بيانات البناء")
        title.setStyleSheet("background: transparent;font-family:'IBM Plex Sans Arabic'; font-size: 8pt; font-weight: 900; color:#1F2D3D;")
        subtitle = QLabel("ابحث عن معلومات البناء والموقع الجغرافي")
        subtitle.setStyleSheet("background: transparent;font-family:'IBM Plex Sans Arabic'; font-size: 8pt; color:#7F8C9B;")

        header_text_col.addWidget(title)
        header_text_col.addWidget(subtitle)

        icon_lbl = QLabel("📄")
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
                font-size: 16px;
            }
        """)

        header_row.addWidget(icon_lbl)
        header_row.addLayout(header_text_col)
        header_row.addStretch(1)

        card_layout.addLayout(header_row)

        # Label: building code
        code_label = QLabel("رمز البناء")
        code_label.setStyleSheet("background: transparent;font-family:'IBM Plex Sans Arabic'; font-size: 8pt; color:#1F2D3D; font-weight:800;")
        card_layout.addWidget(code_label)

        # Search bar (one row)
        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setStyleSheet("""
            QFrame#searchBar {
                background-color: #F0F7FF;
                border: 1px solid #E6EEF8;
                border-radius: 18px;
            }
        """)
        search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(10, 4, 10, 4)
        sb.setSpacing(8)

        # Search icon button
        search_icon_btn = QToolButton()
        search_icon_btn.setText("🔍")
        search_icon_btn.setCursor(Qt.PointingHandCursor)
        search_icon_btn.setFixedSize(30, 30)
        search_icon_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #EEF6FF;
                border-radius: 8px;
            }
        """)
        search_icon_btn.clicked.connect(self._search_buildings)

        # Input
        self.building_search = QLineEdit()
        self.building_search.setPlaceholderText("ابحث عن رمز البناء ...")
        self.building_search.setLayoutDirection(Qt.RightToLeft)

        self.building_search.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                padding: 0px 6px;
                min-height: 28px;
                color: #2C3E50;
            }
        """)
        self.building_search.textChanged.connect(self._on_building_code_changed)
        self.building_search.returnPressed.connect(self._search_buildings)

        # Left links (map search buttons)
        left_links_layout = QHBoxLayout()
        left_links_layout.setSpacing(8)

        self.search_on_map_btn = QPushButton("بحث على الخريطة")
        self.search_on_map_btn.setCursor(Qt.PointingHandCursor)
        self.search_on_map_btn.setFlat(True)
        self.search_on_map_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #3890DF;
                font-family: 'IBM Plex Sans Arabic';
                font-weight: 600;
                font-size: 7pt;
                text-decoration: underline;
                padding: 0;
                margin-top: 1px;
            }
        """)
        self.search_on_map_btn.clicked.connect(self._open_map_search_dialog)

        # فقط زر البحث على الخريطة - تم إزالة زر "تحديد منطقة" كما طلب المستخدم
        # الوظيفة الآن مدمجة في الخريطة نفسها
        left_links_layout.addWidget(self.search_on_map_btn)

        # Assemble search bar
        sb.addLayout(left_links_layout)   # left
        sb.addWidget(self.building_search)  # middle (stretch)
        sb.addWidget(search_icon_btn, 1)

        # Add bar to card
        card_layout.addWidget(search_bar)

        # Suggestions list (dropdown look)
        self.buildings_list = QListWidget()
        self.buildings_list.setVisible(False)
        self.buildings_list.setMaximumHeight(170)
        self.buildings_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                background-color: #FFFFFF;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #F1F5F9;
                color: #2C3E50;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #EFF6FF;
            }
        """)
        self.buildings_list.itemClicked.connect(self._on_building_selected)
        self.buildings_list.itemDoubleClicked.connect(self._on_building_confirmed)
        card_layout.addWidget(self.buildings_list)

        layout.addWidget(card)
        layout.addStretch(1)

        # ===== Selected building details (New UI blocks) =====
        self.selected_building_frame = QFrame()
        self.selected_building_frame.setObjectName("selectedBuildingFrame")
        self.selected_building_frame.setStyleSheet("""
            QFrame#selectedBuildingFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        self.selected_building_frame.hide()

        sb = QVBoxLayout(self.selected_building_frame)
        sb.setContentsMargins(14, 6, 14, 6)
        sb.setSpacing(12)

        # 1) General info line
        info_bar = QFrame()
        info_bar.setStyleSheet("""
            QFrame {
                background-color: #F5FAFF;
                border: 1px solid #DCE7F5;
                border-radius: 10px;
            }
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(12, 10, 12, 10)

        self.selected_building_label = QLabel("")
        self.selected_building_label.setStyleSheet("color: #2C3E50; font-weight: 600;")
        self.selected_building_label.setWordWrap(True)

        info_icon = QLabel("🏢")
        info_icon.setStyleSheet("font-size: 16px; color: #3890DF;")
        info_layout.addWidget(info_icon)
        info_layout.addWidget(self.selected_building_label, stretch=1)

        sb.addWidget(info_bar)

        # 2) Stats row
        stats = QFrame()
        stats.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(12)

        def _stat_block(title_text, value_text="-"):
            box = QFrame()
            box.setStyleSheet("QFrame { background: transparent; }")
            v = QVBoxLayout(box)
            v.setSpacing(4)
            t = QLabel(title_text)
            t.setStyleSheet("font-size: 12px; color: #7F8C9B; font-weight: 600;")
            val = QLabel(value_text)
            val.setStyleSheet("font-size: 13px; color: #2C3E50; font-weight: 700;")
            v.addWidget(t, alignment=Qt.AlignHCenter)
            v.addWidget(val, alignment=Qt.AlignHCenter)
            return box, val

        box_status, self.ui_building_status = _stat_block("حالة البناء")
        box_type, self.ui_building_type = _stat_block("نوع البناء")
        box_units, self.ui_units_count = _stat_block("عدد الوحدات")
        box_parcels, self.ui_parcels_count = _stat_block("عدد المقاسم")
        box_shops, self.ui_shops_count = _stat_block("عدد المحلات")

        for b in [box_status, box_type, box_units, box_parcels, box_shops]:
            stats_layout.addWidget(b, stretch=1)

        sb.addWidget(stats)

        # 3) Location card with thumbnail
        loc = QFrame()
        loc.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)
        loc_layout = QHBoxLayout(loc)
        loc_layout.setContentsMargins(12, 12, 12, 12)
        loc_layout.setSpacing(12)

        loc_text_col = QVBoxLayout()
        loc_title = QLabel("موقع البناء")
        loc_title.setStyleSheet("font-size: 12px; color: #2C3E50; font-weight: 700;")
        loc_desc = QLabel("وصف الموقع")
        loc_desc.setStyleSheet("font-size: 12px; color: #7F8C9B;")
        loc_text_col.addWidget(loc_title)
        loc_text_col.addWidget(loc_desc)
        loc_text_col.addStretch()

        loc_layout.addLayout(loc_text_col, stretch=1)

        thumb_col = QVBoxLayout()
        self.map_thumbnail = QLabel("خريطة مصغّرة")
        self.map_thumbnail.setAlignment(Qt.AlignCenter)
        self.map_thumbnail.setFixedSize(280, 120)
        self.map_thumbnail.setStyleSheet("""
            QLabel {
                background-color: #F8FAFC;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                color: #7F8C9B;
            }
        """)

        self.open_map_btn = QPushButton("قم بفتح الخريطة")
        self.open_map_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #DCE7F5;
                border-radius: 10px;
                padding: 8px 10px;
                color: #3890DF;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #EEF6FF; }
        """)
        self.open_map_btn.setEnabled(False)

        thumb_col.addWidget(self.map_thumbnail)
        thumb_col.addWidget(self.open_map_btn, alignment=Qt.AlignLeft)
        loc_layout.addLayout(thumb_col)

        sb.addWidget(loc)

        layout.addWidget(self.selected_building_frame)

        # Load initial buildings
        self._load_buildings()

    def _on_building_code_changed(self):
        """UI behavior: filter + show/hide suggestions."""
        text = self.building_search.text().strip()
        # Filter same as old
        self._filter_buildings()
        # Show suggestions only when there's text
        self.buildings_list.setVisible(bool(text))

    def _open_map_search_dialog(self):
        """Open map search dialog using shared BuildingMapWidget component (DRY principle)."""
        from ui.components.building_map_widget import BuildingMapWidget

        # Use shared component instead of duplicating code
        map_widget = BuildingMapWidget(self.context.db, self)

        # Show dialog and get selected building
        selected_building = map_widget.show_dialog()

        if selected_building:
            # Update context and UI
            self.context.building = selected_building
            self.selected_building = selected_building

            self.selected_building_label.setText(
                f"✅ المبنى المحدد: {selected_building.building_id}\n"
                f"النوع: {selected_building.building_type_display} | "
                f"الحالة: {selected_building.building_status_display}"
            )
            self.selected_building_frame.show()

            # Hide suggestions list
            self.buildings_list.setVisible(False)

            # Emit validation changed
            self.emit_validation_changed(True)

    def _load_buildings(self):
        """Load buildings into the list."""
        result = self.building_controller.load_buildings()
        self.buildings_list.clear()

        if not result.success:
            logger.error(f"Failed to load buildings: {result.message}")
            return

        buildings = result.data
        for building in buildings:
            item = QListWidgetItem(
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display} | "
                f"الحالة: {building.building_status_display}"
            )
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _filter_buildings(self):
        """Filter buildings list based on search text."""
        search_text = self.building_search.text().lower()
        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            item.setHidden(search_text not in item.text().lower())

    def _search_buildings(self):
        """Search buildings from database."""
        search = self.building_search.text().strip()

        if search:
            result = self.building_controller.search_buildings(search)
        else:
            result = self.building_controller.load_buildings()

        self.buildings_list.clear()

        if not result.success:
            logger.error(f"Failed to search buildings: {result.message}")
            return

        buildings = result.data
        for building in buildings:
            item = QListWidgetItem(
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display}"
            )
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _on_building_selected(self, item):
        """Handle building selection."""
        building = item.data(Qt.UserRole)
        self.context.building = building
        self.selected_building = building

        self.selected_building_label.setText(
            f"✅ المبنى المحدد: {building.building_id}\n"
            f"النوع: {building.building_type_display} | "
            f"الحالة: {building.building_status_display}"
        )
        self.selected_building_frame.show()

        # Hide suggestions list after selection - exact copy from old wizard
        self.buildings_list.setVisible(False)

        # Emit validation changed
        self.emit_validation_changed(True)

        logger.info(f"Building selected: {building.building_id}")

    def _on_building_confirmed(self, item):
        """Double-click to confirm and proceed."""
        self._on_building_selected(item)
        # Note: The old wizard calls self._on_next() here, but we don't have that in the step
        # The wizard controller will handle navigation

    def _open_polygon_selector_dialog(self):
        """
        تم إزالة هذه الوظيفة - الآن يتم استخدام الخريطة الموحدة

        DEPRECATED: This functionality has been removed as per user request.
        Polygon selection is now integrated into the unified map view.
        Use _open_map_search_dialog() instead which provides the same functionality.
        """
        QMessageBox.information(
            self,
            "معلومة - Info",
            "استخدم زر 'البحث على الخريطة' لتحديد المباني.\n"
            "Please use 'Search on Map' button to select buildings."
        )
        return
        try:
            from ui.components.polygon_building_selector_dialog import PolygonBuildingSelectorDialog

            # Open dialog
            dialog = PolygonBuildingSelectorDialog(self.context.db, self)
            buildings = dialog.exec_and_get_buildings()

            if not buildings:
                logger.info("No buildings selected from polygon")
                return

            # If only one building, select it automatically
            if len(buildings) == 1:
                building = buildings[0]
                self.context.building = building
                self.selected_building = building

                self.selected_building_label.setText(
                    f"✅ المبنى المحدد: {building.building_id}\n"
                    f"النوع: {building.building_type_display} | "
                    f"الحالة: {building.building_status_display}"
                )
                self.selected_building_frame.show()
                self.buildings_list.setVisible(False)
                self.emit_validation_changed(True)

                logger.info(f"Building auto-selected from polygon: {building.building_id}")

            else:
                # Multiple buildings - show selection dialog
                self._show_building_selection_dialog(buildings)

        except Exception as e:
            logger.error(f"Error opening polygon selector: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "خطأ - Error",
                f"حدث خطأ أثناء فتح محدد المنطقة:\n{str(e)}"
            )

    def _show_building_selection_dialog(self, buildings):
        """
        Show dialog to select one building from multiple candidates.

        Args:
            buildings: List of Building objects
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle(f"اختر مبنى - Select Building ({len(buildings)} found)")
        dialog.setMinimumWidth(500)
        dialog.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # Instructions
        info_label = QLabel(f"تم العثور على {len(buildings)} مبنى في المنطقة المحددة. اختر واحداً:")
        info_label.setStyleSheet("""
            QLabel {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                color: #2C3E50;
                padding: 8px;
            }
        """)
        layout.addWidget(info_label)

        # Buildings list
        buildings_list = QListWidget()
        buildings_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #EFF6FF;
            }
        """)

        for building in buildings:
            item_text = (
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display} | "
                f"الحالة: {building.building_status_display}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, building)
            buildings_list.addItem(item)

        layout.addWidget(buildings_list)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        select_btn = QPushButton("✓ تحديد - Select")
        select_btn.setMinimumHeight(36)
        select_btn.setStyleSheet("""
            QPushButton {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                font-weight: 600;
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2E7BC6;
            }
            QPushButton:disabled {
                background-color: #D1E8FF;
            }
        """)
        select_btn.setEnabled(False)

        cancel_btn = QPushButton("✕ إلغاء - Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                background-color: #F1F5F9;
                color: #64748B;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E8EFF6;
            }
        """)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(select_btn)
        layout.addLayout(buttons_layout)

        # Connect signals
        def on_selection_changed():
            select_btn.setEnabled(buildings_list.currentItem() is not None)

        def on_select():
            current_item = buildings_list.currentItem()
            if current_item:
                dialog.accept()

        buildings_list.itemSelectionChanged.connect(on_selection_changed)
        buildings_list.itemDoubleClicked.connect(lambda: on_select())
        select_btn.clicked.connect(on_select)
        cancel_btn.clicked.connect(dialog.reject)

        # Show dialog
        result = dialog.exec_()

        if result == QDialog.Accepted:
            current_item = buildings_list.currentItem()
            if current_item:
                building = current_item.data(Qt.UserRole)
                self.context.building = building
                self.selected_building = building

                self.selected_building_label.setText(
                    f"✅ المبنى المحدد: {building.building_id}\n"
                    f"النوع: {building.building_type_display} | "
                    f"الحالة: {building.building_status_display}"
                )
                self.selected_building_frame.show()
                self.buildings_list.setVisible(False)
                self.emit_validation_changed(True)

                logger.info(f"Building selected from polygon list: {building.building_id}")

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        if not self.selected_building:
            result.add_error("يجب اختيار مبنى للمتابعة")

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        return {
            "building_id": self.selected_building.building_id if self.selected_building else None,
            "building_uuid": self.selected_building.building_uuid if self.selected_building else None
        }

    def populate_data(self):
        """Populate the step with data from context."""
        if self.context.building:
            self.selected_building = self.context.building
            # Set search text and trigger search
            self.building_search.setText(self.context.building.building_id)
            self._search_buildings()
            # Show selected building frame
            self.selected_building_label.setText(
                f"✅ المبنى المحدد: {self.context.building.building_id}\n"
                f"النوع: {self.context.building.building_type_display} | "
                f"الحالة: {self.context.building.building_status_display}"
            )
            self.selected_building_frame.show()
            # Emit validation
            self.emit_validation_changed(True)

    def get_step_title(self) -> str:
        """Get step title."""
        return "اختيار المبنى"

    def get_step_description(self) -> str:
        """Get step description."""
        return "ابحث عن المبنى المراد مسحه واختره"
