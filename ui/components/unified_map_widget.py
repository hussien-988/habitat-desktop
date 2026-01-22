# -*- coding: utf-8 -*-
"""
Unified Map Widget - خريطة موحدة قابلة لإعادة الاستخدام

توحيد جميع وظائف الخريطة في مكون واحد:
- عرض المباني كنقاط أو مضلعات
- رسم مضلعات جديدة لتحديد نطاق
- التبديل بين نقطة/مضلع
- الضغط على مضلع لجلب المباني داخله
- عرض المضلعات الموجودة مسبقاً باللون الأزرق

SOLID Principles:
- Single Responsibility: يتعامل فقط مع عرض الخريطة والتفاعل معها
- Open/Closed: قابل للتوسع بدون تعديل
- Dependency Inversion: يعتمد على abstractions (Database, services)

DRY Principle:
- استخدام الخدمات المركزية (GeoJSONConverter, LeafletHTMLGenerator)
- لا تكرار في كود JavaScript أو HTML

Best Practices:
- استخدام Leaflet.js + Leaflet.draw
- QWebChannel للتواصل بين Python و JavaScript
- معالجة أخطاء شاملة
"""

import json
from typing import List, Optional, Dict, Any
from enum import Enum

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QButtonGroup, QRadioButton, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from models.building import Building
from services.geojson_converter import GeoJSONConverter
from services.geometry_validation_service import GeometryValidationService
from services.postgis_service import PostGISService, SQLiteSpatialService
from utils.logger import get_logger

logger = get_logger(__name__)


class MapMode(Enum):
    """أوضاع الخريطة"""
    VIEW_ONLY = "view"  # عرض فقط
    DRAW_POINT = "point"  # رسم نقطة
    DRAW_POLYGON = "polygon"  # رسم مضلع


class MapBridge(QObject):
    """
    Bridge للتواصل بين JavaScript و Python

    SOLID: Interface Segregation - واجهة واضحة للتواصل
    """

    # Signals
    polygon_drawn = pyqtSignal(str)  # GeoJSON
    polygon_clicked = pyqtSignal(str)  # Polygon ID or GeoJSON
    point_selected = pyqtSignal(float, float)  # lat, lon
    building_clicked = pyqtSignal(str)  # building_id

    @pyqtSlot(str)
    def on_polygon_drawn(self, geojson_str: str):
        """عند رسم مضلع جديد"""
        logger.debug(f"Polygon drawn: {geojson_str[:100]}...")
        self.polygon_drawn.emit(geojson_str)

    @pyqtSlot(str)
    def on_polygon_clicked(self, polygon_data: str):
        """عند الضغط على مضلع موجود"""
        logger.debug(f"Polygon clicked: {polygon_data[:100]}...")
        self.polygon_clicked.emit(polygon_data)

    @pyqtSlot(float, float)
    def on_point_selected(self, lat: float, lon: float):
        """عند اختيار نقطة"""
        logger.debug(f"Point selected: {lat}, {lon}")
        self.point_selected.emit(lat, lon)

    @pyqtSlot(str)
    def on_building_clicked(self, building_id: str):
        """عند الضغط على مبنى"""
        logger.debug(f"Building clicked: {building_id}")
        self.building_clicked.emit(building_id)


class UnifiedMapWidget(QWidget):
    """
    خريطة موحدة لجميع الاحتياجات

    Features:
    - عرض المباني (نقاط + مضلعات)
    - رسم مضلعات جديدة
    - اختيار نقاط
    - الضغط على مضلع لجلب المباني
    """

    # Signals
    polygon_selected = pyqtSignal(str, list)  # GeoJSON, List[Building]
    point_selected = pyqtSignal(float, float)  # lat, lon
    buildings_in_polygon = pyqtSignal(list)  # List[Building]

    def __init__(
        self,
        db: Database,
        parent=None,
        initial_mode: MapMode = MapMode.VIEW_ONLY,
        show_mode_switcher: bool = True,
        show_existing_polygons: bool = True
    ):
        """
        Args:
            db: Database connection
            parent: Parent widget
            initial_mode: وضع الخريطة الأولي
            show_mode_switcher: عرض أزرار التبديل بين الأوضاع
            show_existing_polygons: عرض المضلعات الموجودة مسبقاً
        """
        super().__init__(parent)

        self.db = db
        self.building_repo = BuildingRepository(db)
        self.geometry_service = GeometryValidationService()

        # Determine spatial service
        if db.db_type == "postgresql":
            self.spatial_service = PostGISService(db.get_connection())
        else:
            self.spatial_service = SQLiteSpatialService(db.get_connection())

        self.current_mode = initial_mode
        self.show_mode_switcher = show_mode_switcher
        self.show_existing_polygons = show_existing_polygons

        self.buildings: List[Building] = []
        self.existing_polygons: List[Dict[str, Any]] = []
        self.current_polygon_geojson: Optional[str] = None

        # Bridge for JS-Python communication
        self.bridge = MapBridge()
        self.bridge.polygon_drawn.connect(self._on_polygon_drawn)
        self.bridge.polygon_clicked.connect(self._on_polygon_clicked)
        self.bridge.point_selected.connect(self._on_point_selected)
        self.bridge.building_clicked.connect(self._on_building_clicked)

        self._setup_ui()

    def _setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # شريط الأدوات
        if self.show_mode_switcher:
            toolbar = self._create_toolbar()
            layout.addWidget(toolbar)

        # الخريطة
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)

        # Setup QWebChannel
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        layout.addWidget(self.web_view, 1)

        # شريط المعلومات
        self.info_label = QLabel("جارٍ تحميل الخريطة...")
        self.info_label.setStyleSheet("""
            QLabel {
                padding: 8px 12px;
                background-color: #f8f9fa;
                border-radius: 4px;
                color: #6c757d;
                font-size: 11pt;
            }
        """)
        layout.addWidget(self.info_label)

    def _create_toolbar(self) -> QFrame:
        """إنشاء شريط الأدوات"""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px;
            }
        """)

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(12)

        # Label
        mode_label = QLabel("الوضع:")
        mode_label.setStyleSheet("font-weight: bold; color: #495057;")
        toolbar_layout.addWidget(mode_label)

        # Radio buttons للأوضاع
        self.mode_group = QButtonGroup(self)

        self.view_radio = QRadioButton("عرض فقط")
        self.point_radio = QRadioButton("تحديد نقطة")
        self.polygon_radio = QRadioButton("رسم مضلع")

        for i, (radio, mode) in enumerate([
            (self.view_radio, MapMode.VIEW_ONLY),
            (self.point_radio, MapMode.DRAW_POINT),
            (self.polygon_radio, MapMode.DRAW_POLYGON)
        ]):
            self.mode_group.addButton(radio, i)
            radio.setProperty("mode", mode)
            radio.toggled.connect(self._on_mode_changed)
            toolbar_layout.addWidget(radio)

            if mode == self.current_mode:
                radio.setChecked(True)

        toolbar_layout.addStretch()

        # زر مسح
        clear_btn = QPushButton("مسح الرسم")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        clear_btn.clicked.connect(self._clear_drawing)
        toolbar_layout.addWidget(clear_btn)

        return toolbar

    def load_buildings(self, buildings: Optional[List[Building]] = None, limit: int = 500):
        """
        تحميل المباني على الخريطة

        Args:
            buildings: قائمة مباني محددة، أو None لتحميل الكل
            limit: الحد الأقصى للمباني
        """
        if buildings is None:
            self.buildings = self.building_repo.get_all(limit=limit)
        else:
            self.buildings = buildings

        # تحميل المضلعات الموجودة إذا مطلوب
        if self.show_existing_polygons:
            self._load_existing_polygons()

        self._refresh_map()

    def _load_existing_polygons(self):
        """تحميل المضلعات الموجودة مسبقاً من قاعدة البيانات"""
        try:
            # جلب المباني التي لها مضلعات
            polygons = []

            for building in self.buildings:
                if building.geo_location and ('POLYGON' in building.geo_location.upper()):
                    polygons.append({
                        'building_id': building.building_id,
                        'geo_location': building.geo_location,
                        'status': building.building_status or 'intact'
                    })

            self.existing_polygons = polygons
            logger.info(f"Loaded {len(polygons)} existing polygons")

        except Exception as e:
            logger.error(f"Error loading existing polygons: {e}")
            self.existing_polygons = []

    def _refresh_map(self):
        """تحديث الخريطة"""
        try:
            # تحويل المباني إلى GeoJSON
            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                self.buildings,
                prefer_polygons=True
            )

            # تحويل المضلعات الموجودة إلى GeoJSON
            existing_polygons_geojson = self._existing_polygons_to_geojson()

            # توليد HTML
            html = self._generate_map_html(buildings_geojson, existing_polygons_geojson)

            # تحميل في WebView
            self.web_view.setHtml(html)

            # تحديث المعلومات
            geo_count = len([b for b in self.buildings if b.latitude and b.longitude])
            polygon_count = len(self.existing_polygons)
            self.info_label.setText(
                f"عرض {geo_count} مبنى • {polygon_count} مضلع موجود • "
                f"الوضع: {self._get_mode_name()}"
            )

        except Exception as e:
            logger.error(f"Error refreshing map: {e}", exc_info=True)
            self.info_label.setText(f"خطأ في تحميل الخريطة: {str(e)}")

    def _existing_polygons_to_geojson(self) -> str:
        """تحويل المضلعات الموجودة إلى GeoJSON"""
        if not self.existing_polygons:
            return json.dumps({"type": "FeatureCollection", "features": []})

        features = []

        for poly_data in self.existing_polygons:
            try:
                from services.geojson_converter import GeoJSONConverter as GC
                geom, geom_type = GC._parse_geo_location(poly_data['geo_location'])

                if geom:
                    features.append({
                        "type": "Feature",
                        "id": poly_data['building_id'],
                        "geometry": geom,
                        "properties": {
                            "building_id": poly_data['building_id'],
                            "status": poly_data.get('status', 'intact'),
                            "type": "existing_polygon"
                        }
                    })
            except Exception as e:
                logger.warning(f"Failed to parse polygon for {poly_data.get('building_id')}: {e}")

        return json.dumps({
            "type": "FeatureCollection",
            "features": features
        }, ensure_ascii=False)

    def _generate_map_html(self, buildings_geojson: str, existing_polygons_geojson: str) -> str:
        """
        توليد HTML للخريطة

        Best Practice: استخدام Leaflet.js مع Leaflet.draw
        """
        from services.tile_server_manager import get_tile_server_url

        tile_url = get_tile_server_url()
        mode_js = self.current_mode.value

        return f'''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة موحدة</title>

    <link rel="stylesheet" href="{tile_url}/leaflet.css" />
    <link rel="stylesheet" href="{tile_url}/leaflet.draw.css" />
    <script src="{tile_url}/leaflet.js"></script>
    <script src="{tile_url}/leaflet.draw.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ height: 100%; width: 100%; }}
        #map {{ height: 100%; width: 100%; }}

        .leaflet-popup-content-wrapper {{
            direction: rtl;
            text-align: right;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}

        /* Styling لمضلعات موجودة - لون أزرق */
        .existing-polygon {{
            fill: #0072BC !important;
            fill-opacity: 0.3 !important;
            stroke: #0056A3 !important;
            stroke-width: 2 !important;
        }}

        .existing-polygon:hover {{
            fill-opacity: 0.5 !important;
            stroke-width: 3 !important;
            cursor: pointer !important;
        }}

        /* Styling للمضلع الجديد المرسوم */
        .drawn-polygon {{
            fill: #28a745 !important;
            fill-opacity: 0.4 !important;
            stroke: #1e7e34 !important;
            stroke-width: 3 !important;
        }}
    </style>
</head>
<body>
    <div id="map"></div>

    <script>
        var bridge;
        var map;
        var drawnItems;
        var drawControl;
        var currentMode = '{mode_js}';

        // Initialize QWebChannel
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            bridge = channel.objects.bridge;
            initMap();
        }});

        function initMap() {{
            // إنشاء الخريطة
            map = L.map('map', {{
                center: [36.2021, 37.1343],  // Aleppo
                zoom: 13,
                zoomControl: true
            }});

            // Offline tiles
            L.tileLayer('{tile_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
                attribution: 'UN-Habitat',
                maxZoom: 18,
                minZoom: 10
            }}).addTo(map);

            // طبقة للرسومات الجديدة
            drawnItems = new L.FeatureGroup();
            map.addLayer(drawnItems);

            // إضافة أدوات الرسم
            setupDrawControls();

            // تحميل المباني
            loadBuildings();

            // تحميل المضلعات الموجودة
            loadExistingPolygons();

            // تفعيل الوضع الحالي
            setMode(currentMode);
        }}

        function setupDrawControls() {{
            drawControl = new L.Control.Draw({{
                position: 'topright',
                draw: {{
                    polygon: {{
                        allowIntersection: false,
                        showArea: true,
                        drawError: {{
                            color: '#e74c3c',
                            message: 'لا يمكن رسم مضلع متقاطع!'
                        }},
                        shapeOptions: {{
                            color: '#28a745',
                            weight: 3,
                            fillOpacity: 0.4
                        }}
                    }},
                    polyline: false,
                    circle: false,
                    rectangle: false,
                    marker: false,
                    circlemarker: false
                }},
                edit: {{
                    featureGroup: drawnItems,
                    remove: true
                }}
            }});

            map.addControl(drawControl);

            // Event: رسم مكتمل
            map.on(L.Draw.Event.CREATED, function(e) {{
                var layer = e.layer;
                drawnItems.clearLayers();  // مسح الرسومات السابقة
                drawnItems.addLayer(layer);

                // إضافة class للتمييز
                if (layer instanceof L.Polygon) {{
                    layer.options.className = 'drawn-polygon';
                    layer.setStyle({{
                        color: '#28a745',
                        fillColor: '#28a745',
                        fillOpacity: 0.4,
                        weight: 3
                    }});
                }}

                // إرسال إلى Python
                var geojson = layer.toGeoJSON();
                bridge.on_polygon_drawn(JSON.stringify(geojson));
            }});

            // Event: تعديل
            map.on(L.Draw.Event.EDITED, function(e) {{
                var layers = e.layers;
                layers.eachLayer(function(layer) {{
                    var geojson = layer.toGeoJSON();
                    bridge.on_polygon_drawn(JSON.stringify(geojson));
                }});
            }});

            // Event: حذف
            map.on(L.Draw.Event.DELETED, function(e) {{
                bridge.on_polygon_drawn(JSON.stringify({{}}));
            }});
        }}

        function loadBuildings() {{
            var buildingsData = {buildings_geojson};

            if (!buildingsData || !buildingsData.features) return;

            var statusColors = {{
                'intact': '#28a745',
                'minor_damage': '#ffc107',
                'major_damage': '#fd7e14',
                'destroyed': '#dc3545'
            }};

            L.geoJSON(buildingsData, {{
                // Styling للمضلعات
                style: function(feature) {{
                    var status = feature.properties.status || 'intact';
                    return {{
                        fillColor: statusColors[status] || '#0072BC',
                        color: '#fff',
                        weight: 2,
                        fillOpacity: 0.6,
                        opacity: 1
                    }};
                }},

                // Styling للنقاط
                pointToLayer: function(feature, latlng) {{
                    var status = feature.properties.status || 'intact';
                    return L.circleMarker(latlng, {{
                        radius: 8,
                        fillColor: statusColors[status] || '#0072BC',
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9
                    }});
                }},

                // Popup لكل feature
                onEachFeature: function(feature, layer) {{
                    var props = feature.properties;
                    var popup = '<div style="min-width: 180px;">' +
                        '<h4 style="margin: 0 0 8px 0; color: #0072BC;">' + props.building_id + '</h4>' +
                        '<p style="margin: 4px 0;"><strong>الحي:</strong> ' + (props.neighborhood || 'غير محدد') + '</p>' +
                        '<p style="margin: 4px 0;"><strong>الحالة:</strong> ' + (props.status || 'intact') + '</p>' +
                        '<p style="margin: 4px 0;"><strong>النوع:</strong> ' + (props.geometry_type || 'Point') + '</p>' +
                        '</div>';

                    layer.bindPopup(popup);

                    // Event: الضغط على مبنى
                    layer.on('click', function() {{
                        bridge.on_building_clicked(props.building_id);
                    }});
                }}
            }}).addTo(map);
        }}

        function loadExistingPolygons() {{
            var polygonsData = {existing_polygons_geojson};

            if (!polygonsData || !polygonsData.features || polygonsData.features.length === 0) return;

            L.geoJSON(polygonsData, {{
                style: function(feature) {{
                    return {{
                        fillColor: '#0072BC',
                        color: '#0056A3',
                        weight: 2,
                        fillOpacity: 0.3,
                        opacity: 1,
                        className: 'existing-polygon'
                    }};
                }},

                onEachFeature: function(feature, layer) {{
                    var props = feature.properties;
                    var popup = '<div style="min-width: 180px;">' +
                        '<h4 style="margin: 0 0 8px 0; color: #0072BC;">مضلع موجود</h4>' +
                        '<p style="margin: 4px 0;"><strong>المبنى:</strong> ' + props.building_id + '</p>' +
                        '<p style="margin: 4px 0;"><strong>الحالة:</strong> ' + props.status + '</p>' +
                        '<button onclick="selectPolygon(\'' + props.building_id + '\')" ' +
                        'style="margin-top: 8px; padding: 6px 12px; background: #0072BC; color: white; ' +
                        'border: none; border-radius: 4px; cursor: pointer;">جلب المباني في هذا النطاق</button>' +
                        '</div>';

                    layer.bindPopup(popup);

                    // تمييز عند hover
                    layer.on('mouseover', function() {{
                        this.setStyle({{fillOpacity: 0.5, weight: 3}});
                    }});

                    layer.on('mouseout', function() {{
                        this.setStyle({{fillOpacity: 0.3, weight: 2}});
                    }});
                }}
            }}).addTo(map);
        }}

        function selectPolygon(buildingId) {{
            // إرسال إلى Python لجلب المباني
            bridge.on_polygon_clicked(buildingId);
        }}

        function setMode(mode) {{
            currentMode = mode;

            // إخفاء/إظهار أدوات الرسم
            if (mode === 'polygon') {{
                document.querySelector('.leaflet-draw-toolbar').style.display = 'block';
            }} else {{
                document.querySelector('.leaflet-draw-toolbar').style.display = 'none';
            }}

            // تفعيل/تعطيل الرسم
            if (mode === 'point') {{
                map.on('click', onMapClick);
            }} else {{
                map.off('click', onMapClick);
            }}
        }}

        function onMapClick(e) {{
            if (currentMode === 'point') {{
                bridge.on_point_selected(e.latlng.lat, e.latlng.lng);

                // إضافة marker مؤقت
                drawnItems.clearLayers();
                var marker = L.marker(e.latlng);
                drawnItems.addLayer(marker);
            }}
        }}

        function clearDrawing() {{
            drawnItems.clearLayers();
        }}
    </script>
</body>
</html>
'''

    def _get_mode_name(self) -> str:
        """الحصول على اسم الوضع الحالي"""
        return {
            MapMode.VIEW_ONLY: "عرض فقط",
            MapMode.DRAW_POINT: "تحديد نقطة",
            MapMode.DRAW_POLYGON: "رسم مضلع"
        }.get(self.current_mode, "غير معروف")

    def _on_mode_changed(self):
        """معالجة تغيير الوضع"""
        checked_button = self.mode_group.checkedButton()
        if checked_button:
            self.current_mode = checked_button.property("mode")
            logger.info(f"Map mode changed to: {self.current_mode}")

            # إرسال أمر JavaScript لتغيير الوضع
            js = f"setMode('{self.current_mode.value}')"
            self.web_view.page().runJavaScript(js)

            self.info_label.setText(f"الوضع: {self._get_mode_name()}")

    def _clear_drawing(self):
        """مسح الرسم الحالي"""
        self.current_polygon_geojson = None
        self.web_view.page().runJavaScript("clearDrawing()")
        logger.info("Drawing cleared")

    @pyqtSlot(str)
    def _on_polygon_drawn(self, geojson_str: str):
        """معالجة رسم مضلع جديد"""
        if not geojson_str or geojson_str == "{}":
            self.current_polygon_geojson = None
            return

        try:
            self.current_polygon_geojson = geojson_str
            geojson = json.loads(geojson_str)

            # التحقق من صحة المضلع
            if geojson.get('geometry', {}).get('type') == 'Polygon':
                coords = geojson['geometry']['coordinates'][0]

                # تحويل إلى WKT للاستعلام
                wkt_coords = ', '.join([f"{lon} {lat}" for lon, lat in coords])
                wkt = f"POLYGON(({wkt_coords}))"

                # جلب المباني داخل المضلع
                buildings_in_poly = self._query_buildings_in_polygon(wkt)

                logger.info(f"Polygon drawn, found {len(buildings_in_poly)} buildings inside")

                # إصدار signal
                self.polygon_selected.emit(geojson_str, buildings_in_poly)
                self.buildings_in_polygon.emit(buildings_in_poly)

                # تحديث المعلومات
                self.info_label.setText(
                    f"مضلع محدد: {len(buildings_in_poly)} مبنى داخل النطاق"
                )

        except Exception as e:
            logger.error(f"Error processing drawn polygon: {e}", exc_info=True)
            QMessageBox.warning(self, "خطأ", f"خطأ في معالجة المضلع: {str(e)}")

    @pyqtSlot(str)
    def _on_polygon_clicked(self, building_id: str):
        """معالجة الضغط على مضلع موجود"""
        try:
            # البحث عن المبنى
            building = next((b for b in self.buildings if b.building_id == building_id), None)

            if not building or not building.geo_location:
                QMessageBox.warning(self, "خطأ", "لم يتم العثور على المضلع")
                return

            # جلب المباني داخل هذا المضلع
            buildings_in_poly = self._query_buildings_in_polygon(building.geo_location)

            logger.info(f"Clicked polygon {building_id}, found {len(buildings_in_poly)} buildings")

            # إصدار signal
            self.polygon_selected.emit(building.geo_location, buildings_in_poly)
            self.buildings_in_polygon.emit(buildings_in_poly)

            # عرض رسالة
            QMessageBox.information(
                self,
                "المباني في النطاق",
                f"تم العثور على {len(buildings_in_poly)} مبنى داخل هذا النطاق"
            )

        except Exception as e:
            logger.error(f"Error handling polygon click: {e}", exc_info=True)
            QMessageBox.warning(self, "خطأ", f"خطأ في جلب المباني: {str(e)}")

    @pyqtSlot(float, float)
    def _on_point_selected(self, lat: float, lon: float):
        """معالجة اختيار نقطة"""
        logger.info(f"Point selected: {lat}, {lon}")
        self.point_selected.emit(lat, lon)
        self.info_label.setText(f"نقطة محددة: {lat:.5f}, {lon:.5f}")

    @pyqtSlot(str)
    def _on_building_clicked(self, building_id: str):
        """معالجة الضغط على مبنى"""
        logger.info(f"Building clicked: {building_id}")

        building = next((b for b in self.buildings if b.building_id == building_id), None)
        if building:
            # يمكن إضافة عرض تفاصيل المبنى هنا
            pass

    def _query_buildings_in_polygon(self, polygon_wkt: str) -> List[Building]:
        """
        جلب المباني داخل مضلع معين

        Args:
            polygon_wkt: المضلع بصيغة WKT

        Returns:
            قائمة المباني داخل المضلع
        """
        try:
            # تحويل المضلع إلى نقاط
            polygon_points = self._wkt_to_points(polygon_wkt)

            if not polygon_points:
                return []

            # استعلام مكاني
            buildings = self.spatial_service.get_buildings_in_polygon(polygon_points)

            # تحويل النتائج إلى Building objects
            result_buildings = []
            for b_data in buildings:
                building = self.building_repo.get_by_id(b_data['building_id'])
                if building:
                    result_buildings.append(building)

            return result_buildings

        except Exception as e:
            logger.error(f"Error querying buildings in polygon: {e}", exc_info=True)
            return []

    def _wkt_to_points(self, wkt: str) -> List[tuple]:
        """تحويل WKT إلى قائمة نقاط"""
        try:
            import re

            # دعم POLYGON و MULTIPOLYGON
            if wkt.upper().startswith('POLYGON'):
                match = re.search(r'POLYGON\s*\(\s*\((.*?)\)\s*\)', wkt, re.IGNORECASE)
                if match:
                    coords_str = match.group(1)
                    points = []
                    for point_str in coords_str.split(','):
                        parts = point_str.strip().split()
                        if len(parts) >= 2:
                            points.append((float(parts[0]), float(parts[1])))
                    return points

            return []

        except Exception as e:
            logger.error(f"Error parsing WKT: {e}")
            return []

    def set_mode(self, mode: MapMode):
        """
        تغيير وضع الخريطة برمجياً

        Args:
            mode: الوضع الجديد
        """
        self.current_mode = mode

        if self.show_mode_switcher:
            # تحديث UI
            for button in self.mode_group.buttons():
                if button.property("mode") == mode:
                    button.setChecked(True)
                    break

        # تحديث JavaScript
        js = f"setMode('{mode.value}')"
        self.web_view.page().runJavaScript(js)

    def get_current_polygon(self) -> Optional[str]:
        """الحصول على المضلع المرسوم حالياً (GeoJSON)"""
        return self.current_polygon_geojson
