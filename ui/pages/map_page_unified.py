# -*- coding: utf-8 -*-
"""
صفحة عرض الخريطة الموحدة - Unified Map Page

استخدام UnifiedMapWidget لعرض خريطة شاملة مع:
- عرض المباني (نقاط + مضلعات)
- رسم مضلعات لتحديد نطاق
- التبديل بين نقطة/مضلع
- الضغط على مضلع موجود لجلب المباني
- عرض المضلعات الموجودة مسبقاً باللون الأزرق

SOLID Principles:
- Single Responsibility: الصفحة فقط تنظم الواجهة
- Dependency Inversion: تعتمد على UnifiedMapWidget abstraction

DRY Principle:
- لا تكرار - كل المنطق في UnifiedMapWidget

Best Practices:
- فصل المخاوف (Separation of Concerns)
- قابلية إعادة الاستخدام
- معالجة أخطاء شاملة
"""

from typing import List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QLineEdit, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from app.config import Config
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from models.building import Building
from ui.components.unified_map_widget import UnifiedMapWidget, MapMode
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingListPanel(QFrame):
    """
    لوحة قائمة المباني الجانبية

    SOLID: Single Responsibility - فقط عرض وتصفية المباني
    """

    building_selected = pyqtSignal(object)
    filter_changed = pyqtSignal()

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.buildings: List[Building] = []

        self.setFixedWidth(280)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # العنوان
        title = QLabel("قائمة المباني")
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H2}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(title)

        # حقل البحث
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("بحث...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 10px;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                font-size: {Config.FONT_SIZE}pt;
            }}
            QLineEdit:focus {{
                border-color: {Config.PRIMARY_COLOR};
            }}
        """)
        self.search_input.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.search_input)

        # فلتر الحالة
        filter_layout = QHBoxLayout()
        filter_label = QLabel("الحالة:")
        filter_label.setStyleSheet(f"font-size: {Config.FONT_SIZE_SMALL}pt;")
        filter_layout.addWidget(filter_label)

        self.status_filter = QComboBox()
        self.status_filter.addItem("الكل", "")
        self.status_filter.addItem("سليم", "intact")
        self.status_filter.addItem("ضرر طفيف", "minor_damage")
        self.status_filter.addItem("ضرر كبير", "major_damage")
        self.status_filter.addItem("مدمر", "destroyed")
        self.status_filter.setStyleSheet(f"""
            QComboBox {{
                padding: 6px;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 4px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
            }}
        """)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.status_filter, 1)

        layout.addLayout(filter_layout)

        # القائمة
        self.building_list = QListWidget()
        self.building_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 4px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
                margin: 2px 0;
            }}
            QListWidget::item:hover {{
                background-color: #f8f9fa;
            }}
            QListWidget::item:selected {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
            }}
        """)
        self.building_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.building_list, 1)

        # عداد المباني
        self.count_label = QLabel("0 مبنى")
        self.count_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE_LABEL}pt;
        """)
        layout.addWidget(self.count_label)

        # إطار التفاصيل
        self.detail_frame = QFrame()
        self.detail_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #f8f9fa;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        self.detail_frame.hide()

        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(8, 8, 8, 8)
        detail_layout.setSpacing(4)

        self.detail_id = QLabel()
        self.detail_neighborhood = QLabel()
        self.detail_status = QLabel()
        self.detail_coords = QLabel()

        for label in [self.detail_id, self.detail_neighborhood, self.detail_status, self.detail_coords]:
            label.setStyleSheet(f"font-size: {Config.FONT_SIZE_LABEL}pt; color: {Config.TEXT_COLOR};")
            label.setWordWrap(True)
            detail_layout.addWidget(label)

        layout.addWidget(self.detail_frame)

    def set_buildings(self, buildings: List[Building]):
        """تعيين قائمة المباني"""
        self.buildings = buildings
        self._update_list()

    def _update_list(self):
        """تحديث القائمة"""
        self.building_list.clear()

        # الفلترة
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentData()

        filtered_buildings = self.buildings

        if status_filter:
            filtered_buildings = [b for b in filtered_buildings if b.building_status == status_filter]

        if search_text:
            filtered_buildings = [
                b for b in filtered_buildings if
                search_text in (b.building_id or '').lower() or
                search_text in (b.neighborhood_name_ar or '').lower() or
                search_text in (b.neighborhood_name or '').lower()
            ]

        # فقط المباني بإحداثيات
        geo_buildings = [b for b in filtered_buildings if b.latitude and b.longitude]

        # الألوان
        colors = {
            "intact": "#28a745",
            "minor_damage": "#b8860b",
            "major_damage": "#fd7e14",
            "destroyed": "#dc3545",
        }

        for building in geo_buildings[:100]:
            neighborhood = building.neighborhood_name_ar or building.neighborhood_name or ""
            item_text = f"{building.building_id}"
            if neighborhood:
                item_text += f" - {neighborhood}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, building)
            item.setForeground(QColor(colors.get(building.building_status, Config.TEXT_COLOR)))

            self.building_list.addItem(item)

        self.count_label.setText(f"{self.building_list.count()} من {len(geo_buildings)} مبنى")

    def _on_filter_changed(self):
        """معالجة تغيير الفلتر"""
        self._update_list()
        self.filter_changed.emit()

    def _on_item_clicked(self, item):
        """معالجة اختيار مبنى"""
        building = item.data(Qt.UserRole)
        if building:
            self.show_building_details(building)
            self.building_selected.emit(building)

    def show_building_details(self, building: Building):
        """عرض تفاصيل المبنى"""
        self.detail_frame.show()
        self.detail_id.setText(f"المبنى: {building.building_id}")
        self.detail_neighborhood.setText(
            f"الحي: {building.neighborhood_name_ar or building.neighborhood_name or 'غير محدد'}"
        )

        status_ar = {
            "intact": "سليم",
            "minor_damage": "ضرر طفيف",
            "major_damage": "ضرر كبير",
            "destroyed": "مدمر"
        }.get(building.building_status, building.building_status or "غير محدد")
        self.detail_status.setText(f"الحالة: {status_ar}")

        if building.latitude and building.longitude:
            self.detail_coords.setText(f"{building.latitude:.5f}, {building.longitude:.5f}")
        else:
            self.detail_coords.setText("الإحداثيات: غير متوفرة")


class MapPageUnified(QWidget):
    """
    صفحة الخريطة الموحدة - استخدام UnifiedMapWidget

    Best Practice: استخدام مكون موحد قابل لإعادة الاستخدام
    """

    navigate_to = pyqtSignal(object, object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.buildings: List[Building] = []

        self._setup_ui()

    def _setup_ui(self):
        """إعداد واجهة الخريطة"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # الترويسة
        header = self._create_header()
        layout.addWidget(header)

        # المحتوى الرئيسي
        splitter = QSplitter(Qt.Horizontal)

        # الخريطة الموحدة
        map_container = QFrame()
        map_container.setStyleSheet(f"""
            background-color: white;
            border: 1px solid {Config.BORDER_COLOR};
            border-radius: 8px;
        """)
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)

        # استخدام UnifiedMapWidget
        self.map_widget = UnifiedMapWidget(
            db=self.db,
            parent=self,
            initial_mode=MapMode.VIEW_ONLY,
            show_mode_switcher=True,  # عرض أدوات التبديل
            show_existing_polygons=True  # عرض المضلعات الموجودة
        )

        # الاتصال بالـ signals
        self.map_widget.polygon_selected.connect(self._on_polygon_selected)
        self.map_widget.point_selected.connect(self._on_point_selected)
        self.map_widget.buildings_in_polygon.connect(self._on_buildings_in_polygon)

        map_layout.addWidget(self.map_widget)
        splitter.addWidget(map_container)

        # اللوحة الجانبية
        self.side_panel = BuildingListPanel(self.i18n)
        self.side_panel.building_selected.connect(self._on_building_selected)
        self.side_panel.filter_changed.connect(self._on_filter_changed)
        splitter.addWidget(self.side_panel)

        splitter.setSizes([700, 280])
        layout.addWidget(splitter, 1)

        # شريط المعلومات
        info_bar = self._create_info_bar()
        layout.addWidget(info_bar)

    def _create_header(self) -> QFrame:
        """إنشاء الترويسة"""
        header = QFrame()
        header.setStyleSheet(f"""
            background-color: white;
            border: 1px solid {Config.BORDER_COLOR};
            border-radius: 8px;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)

        title_label = QLabel("🗺️ خريطة المباني الموحدة")
        title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title_label)

        # حالة الوضع
        self.status_label = QLabel("جارٍ التحميل...")
        self.status_label.setStyleSheet(f"""
            color: white;
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 4px 12px;
            background-color: {Config.SUCCESS_COLOR};
            border-radius: 12px;
        """)
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        # زر تحديث
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: {Config.FONT_SIZE}pt;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        return header

    def _create_info_bar(self) -> QFrame:
        """إنشاء شريط المعلومات"""
        info_bar = QFrame()
        info_bar.setStyleSheet(f"""
            background-color: white;
            border: 1px solid {Config.BORDER_COLOR};
            border-radius: 6px;
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(16, 8, 16, 8)

        self.info_label = QLabel("جارٍ تحميل البيانات...")
        self.info_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        info_layout.addWidget(self.info_label)

        info_layout.addStretch()

        tips_label = QLabel("💡 يمكنك التبديل بين عرض فقط، تحديد نقطة، أو رسم مضلع")
        tips_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt;")
        info_layout.addWidget(tips_label)

        return info_bar

    def refresh(self, data=None):
        """تحديث بيانات الخريطة"""
        logger.debug("Refreshing unified map page")

        try:
            # تحميل المباني
            self.buildings = self.building_repo.get_all(limit=500)
            geo_buildings = [b for b in self.buildings if b.latitude and b.longitude]

            # تحديث اللوحة الجانبية
            self.side_panel.set_buildings(self.buildings)

            # تحميل في الخريطة الموحدة
            self.map_widget.load_buildings(self.buildings, limit=500)

            # تحديث المعلومات
            polygon_count = len([b for b in self.buildings if b.geo_location and 'POLYGON' in b.geo_location.upper()])

            self.info_label.setText(
                f"📊 عرض {len(geo_buildings)} مبنى بإحداثيات من أصل {len(self.buildings)} مبنى • "
                f"{polygon_count} مضلع موجود"
            )

            self.status_label.setText("✅ جاهز")
            self.status_label.setStyleSheet(f"""
                color: white;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 12px;
                background-color: {Config.SUCCESS_COLOR};
                border-radius: 12px;
            """)

        except Exception as e:
            logger.error(f"Error refreshing map: {e}", exc_info=True)
            self.info_label.setText(f"❌ خطأ في تحميل البيانات: {str(e)}")
            self.status_label.setText("❌ خطأ")
            self.status_label.setStyleSheet(f"""
                color: white;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 12px;
                background-color: {Config.ERROR_COLOR};
                border-radius: 12px;
            """)

    def _on_building_selected(self, building: Building):
        """معالجة اختيار مبنى من القائمة"""
        logger.info(f"Building selected from list: {building.building_id}")
        # يمكن إضافة تكبير الخريطة على المبنى هنا

    def _on_polygon_selected(self, geojson: str, buildings: List[Building]):
        """معالجة اختيار مضلع"""
        logger.info(f"Polygon selected, {len(buildings)} buildings inside")

        # تحديث القائمة الجانبية بالمباني داخل المضلع
        self.side_panel.set_buildings(buildings)

        # عرض رسالة
        self.info_label.setText(
            f"🎯 مضلع محدد: تم العثور على {len(buildings)} مبنى داخل النطاق"
        )

    def _on_point_selected(self, lat: float, lon: float):
        """معالجة اختيار نقطة"""
        logger.info(f"Point selected: {lat}, {lon}")
        self.info_label.setText(f"📍 نقطة محددة: {lat:.5f}, {lon:.5f}")

    def _on_buildings_in_polygon(self, buildings: List[Building]):
        """معالجة جلب مباني داخل مضلع"""
        logger.info(f"Buildings in polygon: {len(buildings)}")

        if buildings:
            # تحديث القائمة الجانبية
            self.side_panel.set_buildings(buildings)
        else:
            QMessageBox.information(
                self,
                "لا توجد مباني",
                "لم يتم العثور على مباني داخل المضلع المحدد"
            )

    def _on_filter_changed(self):
        """معالجة تغيير الفلتر في القائمة الجانبية"""
        # يمكن إضافة تحديث الخريطة بناءً على الفلتر
        pass

    def update_language(self, is_arabic: bool):
        """تحديث اللغة"""
        pass

    def closeEvent(self, event):
        """Clean up on close"""
        super().closeEvent(event)
