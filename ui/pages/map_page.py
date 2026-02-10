# -*- coding: utf-8 -*-
"""
صفحة عرض الخريطة - Offline باستخدام Leaflet.js + MBTiles.
يعمل بدون اتصال بالإنترنت باستخدام خرائط tiles مخزنة محلياً.
"""

import json
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QComboBox,
    QLineEdit, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QColor

# Try to import WebEngine
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    from ui.components.viewport_bridge import ViewportBridge  # ✅ جديد
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from app.config import Config
from repositories.database import Database
from controllers.map_controller import MapController
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

# Note: This page uses the centralized tile server from services/tile_server_manager.py


class BuildingListPanel(QFrame):
    """لوحة قائمة المباني الجانبية."""

    building_selected = pyqtSignal(object)

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.buildings = []

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
        """إعداد الواجهة."""
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
        self.search_input.textChanged.connect(self._filter_list)
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
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 8px;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 4px;
            }}
        """)
        self.status_filter.currentIndexChanged.connect(self._filter_list)
        filter_layout.addWidget(self.status_filter, 1)
        layout.addLayout(filter_layout)

        # قائمة المباني
        self.building_list = QListWidget()
        self.building_list.setAlternatingRowColors(True)
        self.building_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }}
            QListWidget::item:selected {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: {Config.BACKGROUND_COLOR};
            }}
        """)
        self.building_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.building_list, 1)

        # معلومات المبنى المحدد
        self.detail_frame = QFrame()
        self.detail_frame.setStyleSheet(f"""
            background-color: {Config.PRIMARY_COLOR};
            border-radius: 6px;
        """)
        self.detail_frame.hide()

        detail_layout = QVBoxLayout(self.detail_frame)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(3)

        self.detail_id = QLabel()
        self.detail_id.setStyleSheet("font-weight: 600; font-size: 11pt; color: white;")
        detail_layout.addWidget(self.detail_id)

        self.detail_neighborhood = QLabel()
        self.detail_neighborhood.setStyleSheet("font-size: 9pt; color: rgba(255,255,255,0.9);")
        detail_layout.addWidget(self.detail_neighborhood)

        self.detail_status = QLabel()
        self.detail_status.setStyleSheet("font-size: 9pt; color: rgba(255,255,255,0.9);")
        detail_layout.addWidget(self.detail_status)

        self.detail_coords = QLabel()
        self.detail_coords.setStyleSheet("font-size: 8pt; color: rgba(255,255,255,0.7);")
        detail_layout.addWidget(self.detail_coords)

        layout.addWidget(self.detail_frame)

        # عداد المباني
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_LABEL}pt;
            color: {Config.TEXT_LIGHT};
            padding: 6px;
            background-color: {Config.BACKGROUND_COLOR};
            border-radius: 4px;
        """)
        self.count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.count_label)

    def set_buildings(self, buildings):
        """تعيين قائمة المباني."""
        self.buildings = buildings
        self._update_list()

    def _update_list(self):
        """تحديث قائمة المباني."""
        self.building_list.clear()

        geo_buildings = [b for b in self.buildings if b.latitude and b.longitude]

        # تطبيق الفلتر
        status_filter = self.status_filter.currentData()
        if status_filter:
            geo_buildings = [b for b in geo_buildings if b.building_status == status_filter]

        # تطبيق البحث
        search_text = self.search_input.text().strip().lower()
        if search_text:
            geo_buildings = [b for b in geo_buildings if
                search_text in (b.building_id or '').lower() or
                search_text in (b.neighborhood_name_ar or '').lower() or
                search_text in (b.neighborhood_name or '').lower()
            ]

        status_ar = {
            "intact": "سليم",
            "minor_damage": "ضرر طفيف",
            "major_damage": "ضرر كبير",
            "destroyed": "مدمر"
        }

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

        total_geo = len([b for b in self.buildings if b.latitude and b.longitude])
        self.count_label.setText(f"{self.building_list.count()} من {total_geo} مبنى")

    def _filter_list(self):
        """تصفية القائمة."""
        self._update_list()

    def _on_item_clicked(self, item):
        """معالجة اختيار مبنى."""
        building = item.data(Qt.UserRole)
        if building:
            self.show_building_details(building)
            self.building_selected.emit(building)

    def show_building_details(self, building):
        """عرض تفاصيل المبنى."""
        self.detail_frame.show()
        self.detail_id.setText(f"المبنى: {building.building_id}")
        self.detail_neighborhood.setText(f"الحي: {building.neighborhood_name_ar or building.neighborhood_name or 'غير محدد'}")

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


def get_leaflet_html(tile_server_url: str, buildings_geojson: str) -> str:
    """
    Generate Leaflet HTML with offline tiles and local Leaflet library.

    DEPRECATED: Use LeafletHTMLGenerator.generate() instead for better maintainability.
    This function is kept for backward compatibility.

    Best Practice (DRY): Delegates to centralized HTML generator
    """
    from services.leaflet_html_generator import generate_leaflet_html
    return generate_leaflet_html(tile_server_url, buildings_geojson)

    # Original implementation (deprecated, keeping as fallback):
    return f'''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة حلب - UN-Habitat</title>
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <script src="{tile_server_url}/leaflet.js"></script>
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
            min-width: 200px;
        }}
        .building-popup h4 {{
            margin: 0 0 8px 0;
            color: #0072BC;
            font-size: 14px;
        }}
        .building-popup p {{
            margin: 4px 0;
            font-size: 12px;
            color: #333;
        }}
        .status-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            color: white;
        }}
        .status-intact {{ background-color: #28a745; }}
        .status-minor_damage {{ background-color: #ffc107; color: #333; }}
        .status-major_damage {{ background-color: #fd7e14; }}
        .status-destroyed {{ background-color: #dc3545; }}
        .legend {{
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            font-size: 12px;
            direction: rtl;
        }}
        .legend h4 {{
            margin: 0 0 8px 0;
            font-size: 13px;
            color: #333;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 4px 0;
        }}
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-left: 8px;
            border: 2px solid white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}
        .offline-badge {{
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 1000;
            background: #28a745;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
    </style>
</head>
<body>
    <div class="offline-badge">وضع Offline</div>
    <div id="map"></div>
    <script>
        // Fix Leaflet icon paths for local serving
        L.Icon.Default.imagePath = '{tile_server_url}/images/';

        // Initialize map centered on Aleppo
        var map = L.map('map').setView([36.2021, 37.1343], 14);

        // Add tile layer from local server
        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 16,
            minZoom: 10,
            attribution: 'Map data &copy; OpenStreetMap | UN-Habitat Syria'
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

        // Add buildings layer
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
            style: function(feature) {{
                // تخصيص أسلوب المضلعات - ظهور باللون الأزرق
                if (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon') {{
                    return {{
                        color: '#0072BC',        // لون الحدود
                        fillColor: '#0072BC',    // لون التعبئة
                        weight: 2,
                        opacity: 0.8,
                        fillOpacity: 0.3
                    }};
                }}
                return {{}};
            }},
            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var status = props.status || 'intact';
                var statusLabel = statusLabels[status] || status;
                var statusClass = 'status-' + status;

                var geomType = feature.properties.geometry_type || feature.geometry.type;
                var geomLabel = geomType === 'Polygon' || geomType === 'MultiPolygon' ? 'مضلع' : 'نقطة';

                var popup = '<div class="building-popup">' +
                    '<h4>' + (props.building_id || 'مبنى') + '</h4>' +
                    '<p><strong>الحي:</strong> ' + (props.neighborhood || 'غير محدد') + '</p>' +
                    '<p><strong>الحالة:</strong> <span class="status-badge ' + statusClass + '">' + statusLabel + '</span></p>' +
                    '<p><strong>الوحدات:</strong> ' + (props.units || 0) + '</p>' +
                    '<p><strong>النوع:</strong> ' + geomLabel + '</p>' +
                    '</div>';

                layer.bindPopup(popup);

                // تسليط الضوء عند hover للمضلعات
                if (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon') {{
                    layer.on({{
                        mouseover: function(e) {{
                            e.target.setStyle({{
                                fillOpacity: 0.5,
                                weight: 3
                            }});
                        }},
                        mouseout: function(e) {{
                            e.target.setStyle({{
                                fillOpacity: 0.3,
                                weight: 2
                            }});
                        }}
                    }});
                }}
            }}
        }}).addTo(map);

        // Fit to buildings if any
        if (buildingsData.features && buildingsData.features.length > 0) {{
            map.fitBounds(buildingsLayer.getBounds(), {{ padding: [50, 50] }});
        }}

        // Add legend
        var legend = L.control({{ position: 'bottomright' }});
        legend.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<h4>دليل الحالات</h4>' +
                '<div class="legend-item"><div class="legend-color" style="background:#28a745"></div>سليم</div>' +
                '<div class="legend-item"><div class="legend-color" style="background:#ffc107"></div>ضرر طفيف</div>' +
                '<div class="legend-item"><div class="legend-color" style="background:#fd7e14"></div>ضرر كبير</div>' +
                '<div class="legend-item"><div class="legend-color" style="background:#dc3545"></div>مدمر</div>';
            return div;
        }};
        legend.addTo(map);

        // Function to highlight building (called from Python)
        function highlightBuilding(buildingId) {{
            buildingsLayer.eachLayer(function(layer) {{
                if (layer.feature.properties.building_id === buildingId) {{
                    map.setView(layer.getLatLng(), 16);
                    layer.openPopup();
                    layer.setStyle({{ radius: 12, weight: 3 }});
                }} else {{
                    layer.setStyle({{ radius: 8, weight: 2 }});
                }}
            }});
        }}
    </script>
</body>
</html>
'''


class MapPage(QWidget):
    """صفحة عرض الخريطة - تعمل Offline باستخدام Leaflet + MBTiles."""

    navigate_to = pyqtSignal(object, object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        # DRY + SOLID: Use MapController (single source of truth for map data)
        # MapController automatically selects API or local DB based on configuration
        self.map_controller = MapController(db)
        self.buildings = []

        # ✅ جديد: Viewport-based loading (المرحلة 2)
        self.viewport_bridge: Optional['ViewportBridge'] = None
        self.web_channel: Optional['QWebChannel'] = None

        self._setup_ui()

    def _setup_ui(self):
        """إعداد واجهة الخريطة."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # الترويسة
        header = QFrame()
        header.setStyleSheet(f"""
            background-color: white;
            border: 1px solid {Config.BORDER_COLOR};
            border-radius: 8px;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)

        title_label = QLabel("عرض الخريطة")
        title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title_label)

        # حالة الوضع
        self.status_label = QLabel("جارٍ التحميل...")
        self.status_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 4px 12px;
            background-color: #f0f0f0;
            border-radius: 12px;
        """)
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        # زر تحديث
        refresh_btn = QPushButton("تحديث")
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
        refresh_btn.clicked.connect(lambda: self.refresh())
        header_layout.addWidget(refresh_btn)

        layout.addWidget(header)

        # المحتوى الرئيسي
        splitter = QSplitter(Qt.Horizontal)

        # الخريطة
        map_container = QFrame()
        map_container.setStyleSheet(f"""
            background-color: white;
            border: 1px solid {Config.BORDER_COLOR};
            border-radius: 8px;
        """)
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setMinimumSize(600, 400)
            map_layout.addWidget(self.web_view)

            # ✅ جديد: Setup ViewportBridge for dynamic loading
            self._setup_viewport_bridge()
        else:
            # Fallback message
            fallback_label = QLabel(
                "PyQtWebEngine غير متوفر\n\n"
                "قم بتثبيته باستخدام:\n"
                "pip install PyQtWebEngine"
            )
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setStyleSheet(f"""
                font-size: {Config.FONT_SIZE}pt;
                color: {Config.TEXT_LIGHT};
                padding: 40px;
            """)
            map_layout.addWidget(fallback_label)
            self.web_view = None

        splitter.addWidget(map_container)

        # اللوحة الجانبية
        self.side_panel = BuildingListPanel(self.i18n)
        self.side_panel.building_selected.connect(self._on_building_selected)
        splitter.addWidget(self.side_panel)

        splitter.setSizes([700, 280])
        layout.addWidget(splitter, 1)

        # شريط المعلومات
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

        tips_label = QLabel("انقر على مبنى للتفاصيل")
        tips_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt;")
        info_layout.addWidget(tips_label)

        layout.addWidget(info_bar)

    def _start_tile_server(self):
        """Get tile server URL from centralized manager."""
        from services.tile_server_manager import get_tile_server_url

        tile_url = get_tile_server_url()
        # Extract port from URL for backward compatibility
        self.tile_server_port = tile_url.split(':')[-1]
        logger.info(f"Using tile server: {tile_url}")
        return True

    def _buildings_to_geojson(self, buildings) -> str:
        """
        Convert buildings to GeoJSON format - polygons only.

        Uses GeoJSONConverter for unified conversion logic.
        """
        from services.geojson_converter import GeoJSONConverter
        return GeoJSONConverter.buildings_to_geojson(
            buildings,
            prefer_polygons=True
        )

    def _parse_wkt_to_geojson(self, wkt: str) -> dict:
        """تحليل WKT (POLYGON/MULTIPOLYGON) إلى GeoJSON"""
        try:
            wkt = wkt.strip()

            # معالجة MULTIPOLYGON
            if wkt.upper().startswith('MULTIPOLYGON'):
                # استخراج المحتوى بين الأقواس
                content = wkt[wkt.index('(')+1:wkt.rindex(')')]

                polygons = []
                depth = 0
                current_polygon = []
                current_pos = 0

                for i, char in enumerate(content):
                    if char == '(':
                        depth += 1
                        if depth == 2:
                            current_pos = i + 1
                    elif char == ')':
                        if depth == 2:
                            polygon_str = content[current_pos:i]
                            coords = self._parse_polygon_coords(polygon_str)
                            if coords:
                                polygons.append(coords)
                        depth -= 1

                if polygons:
                    return {
                        "type": "MultiPolygon",
                        "coordinates": polygons
                    }

            # معالجة POLYGON عادي
            elif wkt.upper().startswith('POLYGON'):
                content = wkt[wkt.index('(')+1:wkt.rindex(')')]
                coords = self._parse_polygon_coords(content)

                if coords:
                    return {
                        "type": "Polygon",
                        "coordinates": coords
                    }

        except Exception as e:
            logger.warning(f"Failed to parse WKT: {e}")

        return None

    def _parse_polygon_coords(self, polygon_str: str) -> list:
        """تحليل إحداثيات المضلع"""
        rings = []

        # تقسيم الحلقات (خارجية + ثقوب)
        depth = 0
        ring_parts = []
        current_start = 0

        for i, char in enumerate(polygon_str):
            if char == '(':
                if depth == 0:
                    current_start = i + 1
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    ring_parts.append(polygon_str[current_start:i])

        # إذا لم تكن هناك أقواس داخلية، استخدم النص كله
        if not ring_parts:
            ring_parts = [polygon_str.strip('()')]

        for ring_str in ring_parts:
            ring = []
            for point_str in ring_str.split(','):
                point_str = point_str.strip()
                if point_str:
                    parts = point_str.split()
                    if len(parts) >= 2:
                        lon = float(parts[0])
                        lat = float(parts[1])
                        ring.append([lon, lat])

            if ring:
                rings.append(ring)

        return rings if rings else None

    def refresh(self, data=None):
        """تحديث بيانات الخريطة بأداء محسّن."""
        logger.debug("Refreshing map page with optimized performance")

        # Load buildings using MapController (DRY + SOLID)
        # Aleppo bounding box (same as MapServiceAPI)
        bbox = (36.0, 36.8, 36.5, 37.5)  # min_lat, min_lon, max_lat, max_lon

        # ✅ استخدام page_size محسّن = 2000 (زيادة من 1000)
        # ✅ تمرير zoom_level للتحسينات المستقبلية
        logger.info(f"[MAP_PAGE] Requesting buildings with bbox: {bbox} | page_size=2000")
        result = self.map_controller.get_buildings_in_view(
            bbox=bbox,
            page_size=2000,  # ⚡ محسّن: 2000 بدلاً من الافتراضي
            zoom_level=15    # ⚡ للتحسينات المستقبلية (polygon simplification)
        )
        logger.info(f"[MAP_PAGE] Result success: {result.success}, data count: {len(result.data) if result.success else 0}")

        if result.success:
            from models.building import Building
            self.buildings = []
            polygon_count = 0
            point_count = 0
            for geo_data in result.data:
                building = Building()
                building.building_uuid = geo_data.building_id
                building.building_id = geo_data.building_id
                building.latitude = geo_data.point.latitude if geo_data.point else None
                building.longitude = geo_data.point.longitude if geo_data.point else None
                building.building_status = geo_data.status
                building.building_type = geo_data.building_type

                if geo_data.polygon:
                    building.geo_location = geo_data.polygon.to_wkt()
                    polygon_count += 1
                    logger.debug(f"Building {building.building_id}: Has polygon WKT (length={len(building.geo_location)})")
                elif geo_data.point:
                    point_count += 1

                self.buildings.append(building)

            logger.info(f"Buildings summary: {polygon_count} with polygons, {point_count} with points only")

            buildings_with_geometry = [b for b in self.buildings if b.geo_location or (b.latitude and b.longitude)]
            logger.info(f"✅ Loaded {len(buildings_with_geometry)} buildings with geometry from MapController")
            geo_buildings = buildings_with_geometry
        else:
            logger.error(f"❌ Failed to load buildings: {result.message}")
            self.buildings = []
            geo_buildings = []

        self.side_panel.set_buildings(self.buildings)

        self.info_label.setText(
            f"عرض {len(geo_buildings)} مبنى بإحداثيات من أصل {len(self.buildings)} مبنى"
        )

        if not HAS_WEBENGINE:
            self.status_label.setText("WebEngine غير متوفر")
            self.status_label.setStyleSheet(f"""
                color: white;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 12px;
                background-color: {Config.WARNING_COLOR};
                border-radius: 12px;
            """)
            return

        # Start tile server
        if self._start_tile_server():
            self.status_label.setText("وضع Offline")
            self.status_label.setStyleSheet(f"""
                color: white;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 12px;
                background-color: {Config.SUCCESS_COLOR};
                border-radius: 12px;
            """)

            # Generate and load HTML
            tile_url = f"http://127.0.0.1:{self.tile_server_port}"
            geojson = self._buildings_to_geojson(geo_buildings)

            # Log GeoJSON summary
            import json
            try:
                geojson_data = json.loads(geojson)
                features = geojson_data.get('features', [])
                polygon_features = [f for f in features if f.get('geometry', {}).get('type') in ['Polygon', 'MultiPolygon']]
                point_features = [f for f in features if f.get('geometry', {}).get('type') == 'Point']
                logger.info(f"GeoJSON summary: {len(polygon_features)} Polygon features, {len(point_features)} Point features, {len(features)} total")
                if polygon_features:
                    sample = polygon_features[0]
                    logger.debug(f"Sample polygon feature: building_id={sample.get('properties', {}).get('building_id')}, geometry_type={sample.get('properties', {}).get('geometry_type')}")
            except:
                pass

            html = get_leaflet_html(tile_url, geojson)

            self.web_view.setHtml(html)
        else:
            self.status_label.setText("خطأ في تحميل الخريطة")
            self.status_label.setStyleSheet(f"""
                color: white;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 12px;
                background-color: {Config.ERROR_COLOR};
                border-radius: 12px;
            """)

    def _on_building_selected(self, building):
        """معالجة اختيار مبنى من القائمة."""
        if self.web_view and building.building_id:
            # Call JavaScript to highlight building
            js = f"highlightBuilding('{building.building_id}')"
            self.web_view.page().runJavaScript(js)

    def _setup_viewport_bridge(self):
        """
        ✅ المرحلة 2: إعداد ViewportBridge للتحميل الديناميكي.

        Professional Best Practice:
        - QWebChannel للتواصل بين JavaScript و Python
        - Debouncing في ViewportBridge (300ms)
        - Dynamic loading عند تغيير viewport
        """
        if not HAS_WEBENGINE or not self.web_view:
            logger.warning("⚠️ WebEngine not available, viewport loading disabled")
            return

        try:
            # إنشاء ViewportBridge
            self.viewport_bridge = ViewportBridge(debounce_ms=300, parent=self)
            self.viewport_bridge.viewportChanged.connect(self._on_viewport_changed)

            # إنشاء QWebChannel
            self.web_channel = QWebChannel(self.web_view.page())
            self.web_channel.registerObject('viewportBridge', self.viewport_bridge)

            # ربط channel مع web page
            self.web_view.page().setWebChannel(self.web_channel)

            logger.info("✅ ViewportBridge setup complete (debounce=300ms)")

        except Exception as e:
            logger.error(f"❌ Failed to setup ViewportBridge: {e}")
            self.viewport_bridge = None
            self.web_channel = None

    def _on_viewport_changed(self, viewport_data: dict):
        """
        معالجة تغيير viewport - تحميل المباني في المنطقة الجديدة.

        Professional Best Practice:
        - يُستدعى بعد debouncing (300ms)
        - يُحمّل فقط المباني في viewport الحالي
        - يُحدّث الخريطة ديناميكياً بدون reload

        Args:
            viewport_data: dict with keys:
                - ne_lat, ne_lng: North-East corner
                - sw_lat, sw_lng: South-West corner
                - zoom: Current zoom level
                - center_lat, center_lng: Map center
        """
        try:
            logger.info(f"🗺️ Loading buildings for viewport (zoom={viewport_data['zoom']})")

            # تحويل viewport إلى bbox
            bbox = (
                viewport_data['sw_lat'],
                viewport_data['sw_lng'],
                viewport_data['ne_lat'],
                viewport_data['ne_lng']
            )

            # تحميل المباني في viewport
            result = self.map_controller.get_buildings_in_view(
                bbox=bbox,
                page_size=2000,  # ⚡ محسّن من المرحلة 1
                zoom_level=viewport_data['zoom']
            )

            if result.success and result.data:
                # تحويل BuildingGeoData إلى GeoJSON
                from services.geojson_converter import buildings_to_geojson
                geojson_data = buildings_to_geojson(result.data)
                geojson_str = json.dumps(geojson_data, ensure_ascii=False)

                # إرسال للخريطة عبر JavaScript
                if self.web_view:
                    js_code = f"if (typeof updateBuildingsOnMap === 'function') {{ updateBuildingsOnMap({geojson_str}); }}"
                    self.web_view.page().runJavaScript(js_code)

                    logger.info(f"✅ Updated map with {len(result.data)} buildings")

                # تحديث الـ status
                self.info_label.setText(f"تم تحميل {len(result.data)} مبنى في المنطقة الحالية")
            else:
                logger.warning(f"⚠️ No buildings found in viewport")
                self.info_label.setText("لا توجد مبانٍ في المنطقة الحالية")

        except Exception as e:
            logger.error(f"❌ Error loading viewport buildings: {e}", exc_info=True)
            self.info_label.setText("خطأ في تحميل البيانات")

    def update_language(self, is_arabic: bool):
        """تحديث اللغة."""
        pass

    def closeEvent(self, event):
        """Clean up on close (shared tile server remains active)."""
        # Note: We don't shutdown the shared tile server as it may be used by other components
        super().closeEvent(event)
