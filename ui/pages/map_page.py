# -*- coding: utf-8 -*-
"""
    صفحة عرض الخريطة - Offline باستخدام Leaflet.js + MBTiles.
    يعمل بدون اتصال بالإنترنت باستخدام خرائط tiles مخزنة محلياً.
"""

import json
import re
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QComboBox,
    QLineEdit, QSplitter
    )
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QTimer, QThread
from PyQt5.QtGui import QColor

# Try to import WebEngine
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    from ui.components.viewport_bridge import ViewportBridge
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from app.config import Config
from repositories.database import Database
from controllers.map_controller import MapController
from services.translation_manager import tr
from services.display_mappings import get_building_status_display
from utils.i18n import I18n
from services.api_worker import ApiWorker
from ui.components.toast import Toast
from utils.logger import get_logger

logger = get_logger(__name__)

# Note: This page uses the centralized tile server from services/tile_server_manager.py


class _MapPageWorker(QThread):
    """Background worker for loading map page data without blocking the UI."""
    finished = pyqtSignal(dict)

    def run(self):
        result = {}
        try:
            from services.tile_server_manager import get_tile_metadata, get_tile_server_url, get_local_server_url

            result['tile_meta'] = get_tile_metadata()
            result['tile_url'] = get_tile_server_url()
            result['local_asset_url'] = get_local_server_url()

            tile_bounds = result['tile_meta'].get('bounds')
            if tile_bounds and len(tile_bounds) == 4:
                bbox = (tile_bounds[1], tile_bounds[0], tile_bounds[3], tile_bounds[2])
            else:
                bbox = (Config.MAP_BOUNDS_MIN_LAT, Config.MAP_BOUNDS_MIN_LNG,
                        Config.MAP_BOUNDS_MAX_LAT, Config.MAP_BOUNDS_MAX_LNG)
            result['bbox'] = bbox

            # Get buildings
            from controllers.map_controller import MapController
            map_ctrl = MapController(None)
            buildings_result = map_ctrl.get_buildings_in_view(bbox=bbox, page_size=2000, zoom_level=15)
            result['buildings_result'] = buildings_result

            # Get neighborhoods
            result['neighborhoods'] = None
            try:
                from services.api_client import get_api_client
                api = get_api_client()
                result['neighborhoods'] = api.get_neighborhoods_by_bounds(
                    sw_lat=Config.MAP_BOUNDS_MIN_LAT, sw_lng=Config.MAP_BOUNDS_MIN_LNG,
                    ne_lat=Config.MAP_BOUNDS_MAX_LAT, ne_lng=Config.MAP_BOUNDS_MAX_LNG
                )
            except Exception as e:
                logger.warning(f"Could not load neighborhoods: {e}")

            # Get landmarks
            result['landmarks'] = None
            try:
                from services.api_client import get_api_client
                from services.map_utils import normalize_landmark, normalize_street
                api = get_api_client()
                lm = api.get_landmarks_for_map(
                    north_east_lat=bbox[2], north_east_lng=bbox[3],
                    south_west_lat=bbox[0], south_west_lng=bbox[1]
                )
                if lm:
                    result['landmarks'] = [normalize_landmark(l) for l in lm]
            except Exception as e:
                logger.warning(f"Could not load landmarks: {e}")

            # Get streets
            result['streets'] = None
            try:
                st = api.get_streets_for_map(
                    north_east_lat=bbox[2], north_east_lng=bbox[3],
                    south_west_lat=bbox[0], south_west_lng=bbox[1]
                )
                if st:
                    result['streets'] = [normalize_street(s) for s in st]
            except Exception as e:
                logger.warning(f"Could not load streets: {e}")

        except Exception as e:
            logger.error(f"Map page worker error: {e}", exc_info=True)

        self.finished.emit(result)


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
        title = QLabel(tr("page.map.buildings_list"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H2}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(title)

        # حقل البحث
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("page.map.search"))
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
        filter_label = QLabel(tr("page.map.status_label"))
        filter_label.setStyleSheet(f"font-size: {Config.FONT_SIZE_SMALL}pt;")
        filter_layout.addWidget(filter_label)

        self.status_filter = QComboBox()
        self.status_filter.addItem(tr("page.map.all"), "")
        self.status_filter.addItem(get_building_status_display("intact"), "intact")
        self.status_filter.addItem(get_building_status_display("minor_damage"), "minor_damage")
        self.status_filter.addItem(get_building_status_display("major_damage"), "major_damage")
        self.status_filter.addItem(get_building_status_display("destroyed"), "destroyed")
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
        self.count_label.setText(tr("page.map.count_label", count=self.building_list.count(), total=total_geo))

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
        self.detail_id.setText(tr("page.map.building_label", building_id=building.building_id))
        self.detail_neighborhood.setText(tr("page.map.neighborhood_label", value=building.neighborhood_name_ar or building.neighborhood_name or tr("mapping.not_specified")))

        status_display = get_building_status_display(building.building_status)
        self.detail_status.setText(tr("page.map.status_display", status=status_display))

        if building.latitude and building.longitude:
            self.detail_coords.setText(f"{building.latitude:.5f}, {building.longitude:.5f}")
        else:
            self.detail_coords.setText(tr("page.map.coords_unavailable"))


def get_leaflet_html(tile_server_url: str, buildings_geojson: str, **kwargs) -> str:
    """
    Generate Leaflet HTML with offline tiles and local Leaflet library.

    DEPRECATED: Use LeafletHTMLGenerator.generate() instead for better maintainability.
    This function is kept for backward compatibility.

    Delegates to centralized HTML generator.
    """
    from services.leaflet_html_generator import generate_leaflet_html
    return generate_leaflet_html(tile_server_url, buildings_geojson, **kwargs)

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

        // Initialize map (center and zoom from Config/.env)
        var map = L.map('map').setView([{Config.MAP_CENTER_LAT}, {Config.MAP_CENTER_LNG}], {Config.MAP_DEFAULT_ZOOM});

        // Add tile layer from local server
        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: {Config.MAP_MAX_ZOOM},
            minZoom: {Config.MAP_MIN_ZOOM},
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


from services.map_utils import LANDMARK_TYPE_MAP, normalize_landmark as _normalize_landmark, normalize_street as _normalize_street


class MapPage(QWidget):
    """صفحة عرض الخريطة - تعمل Offline باستخدام Leaflet + MBTiles."""

    navigate_to = pyqtSignal(object, object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        # Use MapController (single source of truth for map data)
        # MapController automatically selects API or local DB based on configuration
        self.map_controller = MapController(db)
        self.buildings = []

        # جديد: Viewport-based loading (المرحلة 2)
        self.viewport_bridge: Optional['ViewportBridge'] = None
        self.web_channel: Optional['QWebChannel'] = None
        self._refresh_worker = None
        self._viewport_buildings_worker = None
        self._landmark_search_worker = None
        self._street_search_worker = None
        self._viewport_landmarks_worker = None
        self._viewport_streets_worker = None

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

        title_label = QLabel(tr("page.map.title"))
        title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title_label)

        # حالة الوضع
        self.status_label = QLabel(tr("page.map.loading"))
        self.status_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 4px 12px;
            background-color: #f0f0f0;
            border-radius: 12px;
        """)
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        # Search type selector
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItem("معلم", "landmark")
        self.search_type_combo.addItem("حي", "neighborhood")
        self.search_type_combo.addItem("شارع", "street")
        self.search_type_combo.setFixedWidth(80)
        self.search_type_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 5px 8px;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
            }}
        """)
        self.search_type_combo.currentIndexChanged.connect(self._on_search_type_changed)
        header_layout.addWidget(self.search_type_combo)

        # Search input
        self.landmark_search = QLineEdit()
        self.landmark_search.setPlaceholderText("بحث المعالم...")
        self.landmark_search.setFixedWidth(200)
        self.landmark_search.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
            }}
            QLineEdit:focus {{
                border-color: {Config.PRIMARY_COLOR};
            }}
        """)
        header_layout.addWidget(self.landmark_search)

        # Landmark search results dropdown
        self.landmark_results = QListWidget()
        self.landmark_results.setFixedWidth(280)
        self.landmark_results.setMaximumHeight(200)
        self.landmark_results.setStyleSheet(f"""
            QListWidget {{
                background: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                font-size: {Config.FONT_SIZE_SMALL}pt;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid #f0f0f0;
            }}
            QListWidget::item:selected {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: #F0F7FF;
            }}
        """)
        self.landmark_results.setWindowFlags(Qt.Popup)
        self.landmark_results.hide()
        self.landmark_results.itemClicked.connect(self._on_landmark_result_clicked)

        # Debounce timer for landmark search
        self._landmark_search_timer = QTimer(self)
        self._landmark_search_timer.setSingleShot(True)
        self._landmark_search_timer.setInterval(500)
        self._landmark_search_timer.timeout.connect(self._do_landmark_search)
        self.landmark_search.textChanged.connect(self._on_landmark_search_changed)

        # زر تحديث
        refresh_btn = QPushButton(tr("page.map.refresh"))
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

            # جديد: Setup ViewportBridge for dynamic loading
            self._setup_viewport_bridge()
        else:
            # Fallback message
            fallback_label = QLabel(tr("page.map.webengine_missing"))
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

        self.info_label = QLabel(tr("page.map.loading_data"))
        self.info_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        info_layout.addWidget(self.info_label)

        info_layout.addStretch()

        tips_label = QLabel(tr("page.map.click_building"))
        tips_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_LABEL}pt;")
        info_layout.addWidget(tips_label)

        layout.addWidget(info_bar)

    def _start_tile_server(self):
        """Get tile server URLs from centralized manager."""
        from services.tile_server_manager import get_tile_server_url, get_local_server_url

        # Local server always starts — serves static assets (leaflet.js, leaflet.css, etc.)
        self.local_asset_url = get_local_server_url()
        # Tile URL may be Docker (when available) or local
        self.tile_url = get_tile_server_url()
        # Backward compat: other methods may use tile_server_port
        self.tile_server_port = self.local_asset_url.split(':')[-1]
        logger.info(f"Assets URL: {self.local_asset_url}, Tiles URL: {self.tile_url}")
        return True

    def _parse_wkt_centroid(self, wkt: str):
        """Extract centroid from any WKT POLYGON or MULTIPOLYGON."""
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

    def _neighborhoods_api_to_geojson(self, neighborhoods: list) -> str:
        """Convert API neighborhood list to GeoJSON for map overlay pins."""
        features = []
        for n in neighborhoods:
            wkt = n.get('boundaries') or n.get('boundary') or n.get('boundaryWkt') or ''
            center = self._parse_wkt_centroid(wkt)
            if not center:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "code": n.get('neighborhoodCode') or n.get('code', ''),
                    "center_lat": center[0],
                    "center_lng": center[1],
                    "name_ar": n.get('nameArabic') or n.get('name_ar', '')
                },
                "geometry": None
            })
        return json.dumps({"type": "FeatureCollection", "features": features})

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
        """تحديث بيانات الخريطة بأداء محسّن — يحمّل البيانات في خيط خلفي."""
        logger.debug("Refreshing map page (async)")

        if not HAS_WEBENGINE:
            self.status_label.setText(tr("page.map.webengine_unavailable"))
            self.status_label.setStyleSheet(f"""
                color: white;
                font-size: {Config.FONT_SIZE_SMALL}pt;
                padding: 4px 12px;
                background-color: {Config.WARNING_COLOR};
                border-radius: 12px;
            """)
            return

        # Show loading state
        self.status_label.setText("جاري تحميل البيانات...")
        self.status_label.setStyleSheet(f"""
            color: white;
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 4px 12px;
            background-color: #FF9800;
            border-radius: 12px;
        """)

        loading_html = """
        <html><body style="display:flex;align-items:center;justify-content:center;
        height:100vh;margin:0;font-family:Arial;background:#f0f2f5;direction:rtl;">
        <div style="text-align:center;color:#555;">
        <div style="font-size:32px;margin-bottom:16px;">&#x23F3;</div>
        <div style="font-size:16px;">جاري تحميل الخريطة...</div>
        </div></body></html>
        """
        if hasattr(self, 'web_view') and self.web_view:
            self.web_view.setHtml(loading_html)

        self._refresh_worker = _MapPageWorker()
        self._refresh_worker.finished.connect(self._on_refresh_data_ready)
        self._refresh_worker.start()

    def _on_refresh_data_ready(self, data):
        """Handle map data from background worker."""
        tile_meta = data.get('tile_meta', {})
        tile_bounds = tile_meta.get('bounds')
        bbox = data.get('bbox', (Config.MAP_BOUNDS_MIN_LAT, Config.MAP_BOUNDS_MIN_LNG,
                                  Config.MAP_BOUNDS_MAX_LAT, Config.MAP_BOUNDS_MAX_LNG))

        buildings_result = data.get('buildings_result')

        if buildings_result and buildings_result.success:
            from models.building import Building
            self.buildings = []
            polygon_count = 0
            point_count = 0
            for geo_data in buildings_result.data:
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
                elif geo_data.point:
                    point_count += 1
                self.buildings.append(building)

            logger.info(f"Buildings: {polygon_count} polygons, {point_count} points")
            geo_buildings = [b for b in self.buildings if b.geo_location or (b.latitude and b.longitude)]
        else:
            self.buildings = []
            geo_buildings = []

        self.side_panel.set_buildings(self.buildings)
        self.info_label.setText(
            tr("page.map.showing_buildings", geo_count=len(geo_buildings), total=len(self.buildings))
        )

        # Set tile server URLs
        self.local_asset_url = data.get('local_asset_url', '')
        self.tile_url = data.get('tile_url', '')
        self.tile_server_port = self.local_asset_url.split(':')[-1] if self.local_asset_url else ''

        self.status_label.setText(tr("page.map.offline_mode"))
        self.status_label.setStyleSheet(f"""
            color: white;
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 4px 12px;
            background-color: {Config.SUCCESS_COLOR};
            border-radius: 12px;
        """)

        # Neighborhoods
        neighborhoods_geojson = None
        neighborhoods = data.get('neighborhoods')
        if neighborhoods:
            neighborhoods_geojson = self._neighborhoods_api_to_geojson(neighborhoods)

        # Tile bounds
        initial_bounds = None
        if tile_bounds and len(tile_bounds) == 4:
            initial_bounds = [[tile_bounds[1], tile_bounds[0]], [tile_bounds[3], tile_bounds[2]]]

        # Boundaries (local — fast, no network)
        from services import boundary_service
        boundaries_geojson = None
        boundary_level = 'governorates'
        if boundary_service.is_available(boundary_level):
            boundaries_geojson = boundary_service.get(boundary_level)
        places_json = boundary_service.get_places_json() if boundary_service.is_available('populated_places') else None

        # Landmarks and streets from worker
        landmarks_json = None
        streets_json = None
        if data.get('landmarks'):
            landmarks_json = json.dumps(data['landmarks'], ensure_ascii=False)
        if data.get('streets'):
            streets_json = json.dumps(data['streets'], ensure_ascii=False)

        # Generate and load HTML
        geojson = self._buildings_to_geojson(geo_buildings)
        html = get_leaflet_html(
            self.local_asset_url,
            geojson,
            tile_layer_url=self.tile_url,
            neighborhoods_geojson=neighborhoods_geojson,
            initial_bounds=initial_bounds,
            boundaries_geojson=boundaries_geojson,
            boundary_level=boundary_level,
            places_json=places_json,
            landmarks_json=landmarks_json,
            streets_json=streets_json
        )

        self.web_view.setHtml(html, QUrl(self.local_asset_url))

    # Keep old code path for error display
    def _show_map_error(self):
        if not hasattr(self, 'status_label'):
            return
        self.status_label.setText(tr("page.map.load_error"))
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
        المرحلة 2: إعداد ViewportBridge للتحميل الديناميكي.

        - QWebChannel للتواصل بين JavaScript و Python
        - Debouncing في ViewportBridge (300ms)
        - Dynamic loading عند تغيير viewport
        """
        if not HAS_WEBENGINE or not self.web_view:
            logger.warning("WebEngine not available, viewport loading disabled")
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

            logger.info("ViewportBridge setup complete (debounce=300ms)")

        except Exception as e:
            Toast.show_toast(self, "تعذر تحميل بيانات الخريطة", Toast.ERROR)
            logger.error(f"Failed to setup ViewportBridge: {e}")
            self.viewport_bridge = None
            self.web_channel = None

    def _on_viewport_changed(self, viewport_data: dict):
        """
        معالجة تغيير viewport - تحميل المباني في المنطقة الجديدة.

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
            logger.info(f"Loading buildings for viewport (zoom={viewport_data['zoom']})")

            bbox = (
                viewport_data['sw_lat'],
                viewport_data['sw_lng'],
                viewport_data['ne_lat'],
                viewport_data['ne_lng']
            )

            self._pending_viewport_data = viewport_data

            self._viewport_buildings_worker = ApiWorker(
                self.map_controller.get_buildings_in_view,
                bbox=bbox,
                page_size=2000,
                zoom_level=viewport_data['zoom']
            )
            self._viewport_buildings_worker.finished.connect(self._on_viewport_buildings_ready)
            self._viewport_buildings_worker.error.connect(self._on_viewport_buildings_error)
            self._viewport_buildings_worker.start()

        except Exception as e:
            logger.error(f"Error starting viewport buildings worker: {e}", exc_info=True)
            self.info_label.setText(tr("page.map.viewport_load_error"))

    def _on_viewport_buildings_ready(self, result):
        """Handle viewport buildings loaded in background."""
        try:
            if result and result.success and result.data:
                from services.geojson_converter import buildings_to_geojson
                geojson_data = buildings_to_geojson(result.data)
                geojson_str = json.dumps(geojson_data, ensure_ascii=False)

                if self.web_view:
                    js_code = f"if (typeof updateBuildingsOnMap === 'function') {{ updateBuildingsOnMap({geojson_str}); }}"
                    self.web_view.page().runJavaScript(js_code)

                logger.info(f"Updated map with {len(result.data)} buildings")
                self.info_label.setText(tr("page.map.loaded_in_viewport", count=len(result.data)))
            else:
                logger.warning(f"No buildings found in viewport")
                self.info_label.setText(tr("page.map.no_buildings_viewport"))

            viewport_data = getattr(self, '_pending_viewport_data', None)
            if viewport_data:
                self._update_viewport_landmarks_streets(viewport_data)

        except Exception as e:
            logger.error(f"Error processing viewport buildings: {e}", exc_info=True)
            self.info_label.setText(tr("page.map.viewport_load_error"))

    def _on_viewport_buildings_error(self, error_msg):
        """Handle viewport buildings load error."""
        logger.warning(f"Viewport buildings worker failed: {error_msg}")
        self.info_label.setText(tr("page.map.viewport_load_error"))

    def _on_landmark_search_changed(self, text):
        """Debounce landmark search input."""
        if len(text.strip()) < 2:
            self.landmark_results.hide()
            return
        self._landmark_search_timer.start()

    def _on_search_type_changed(self, index):
        """Update placeholder when search type changes."""
        search_type = self.search_type_combo.currentData()
        placeholders = {
            "neighborhood": "بحث الأحياء...",
            "street": "بحث الشوارع...",
        }
        self.landmark_search.setPlaceholderText(placeholders.get(search_type, "بحث المعالم..."))
        self.landmark_search.clear()
        self.landmark_results.hide()

    def _do_landmark_search(self):
        """Execute search after debounce."""
        query = self.landmark_search.text().strip()
        if len(query) < 2:
            self.landmark_results.hide()
            return

        search_type = self.search_type_combo.currentData()
        if search_type == "neighborhood":
            self._do_neighborhood_search(query)
        elif search_type == "street":
            self._do_street_search(query)
        else:
            self._do_landmark_api_search(query)

    def _do_landmark_api_search(self, query):
        """Search landmarks via API (non-blocking)."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()

            self._landmark_search_worker = ApiWorker(
                api.search_landmarks, query, max_results=10
            )
            self._landmark_search_worker.finished.connect(self._on_landmark_search_ready)
            self._landmark_search_worker.error.connect(self._on_landmark_search_error)
            self._landmark_search_worker.start()

        except Exception as e:
            Toast.show_toast(self, "تعذر تحميل بيانات الخريطة", Toast.ERROR)
            logger.warning(f"Landmark search failed: {e}")
            self.landmark_results.hide()

    def _on_landmark_search_ready(self, results):
        """Handle landmark search results from background worker."""
        self.landmark_results.clear()
        if not results:
            self.landmark_results.hide()
            return

        for lm in results:
            lm = _normalize_landmark(lm)
            name = lm.get('name', '')
            type_name = lm.get('typeName', '')
            display = f"{name} ({type_name})" if type_name else name
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, lm)
            self.landmark_results.addItem(item)

        pos = self.landmark_search.mapToGlobal(self.landmark_search.rect().bottomLeft())
        self.landmark_results.move(pos)
        self.landmark_results.show()

    def _on_landmark_search_error(self, error_msg):
        """Handle landmark search error."""
        Toast.show_toast(self, "تعذر تحميل بيانات الخريطة", Toast.ERROR)
        logger.warning(f"Landmark search worker failed: {error_msg}")
        self.landmark_results.hide()

    def _do_street_search(self, query):
        """Search streets by fetching all streets and filtering by name locally (non-blocking)."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()

            self._street_search_query = query

            self._street_search_worker = ApiWorker(
                api.get_streets_for_map,
                north_east_lat=Config.MAP_BOUNDS_MAX_LAT,
                north_east_lng=Config.MAP_BOUNDS_MAX_LNG,
                south_west_lat=Config.MAP_BOUNDS_MIN_LAT,
                south_west_lng=Config.MAP_BOUNDS_MIN_LNG
            )
            self._street_search_worker.finished.connect(self._on_street_search_ready)
            self._street_search_worker.error.connect(self._on_street_search_error)
            self._street_search_worker.start()

        except Exception as e:
            Toast.show_toast(self, "تعذر تحميل بيانات الخريطة", Toast.ERROR)
            logger.warning(f"Street search failed: {e}")
            self.landmark_results.hide()

    def _on_street_search_ready(self, streets):
        """Handle street search results from background worker."""
        self.landmark_results.clear()
        if not streets:
            self.landmark_results.hide()
            return

        query_lower = getattr(self, '_street_search_query', '').lower()
        matches = []
        for s in streets:
            s = _normalize_street(s)
            name = s.get('name', '')
            if query_lower in (name or '').lower():
                wkt = s.get('geometryWkt', '')
                lat, lng = self._extract_center_from_linestring(wkt)
                if lat and lng:
                    matches.append({
                        'name': name,
                        'latitude': lat,
                        'longitude': lng,
                        '_type': 'street',
                    })
                if len(matches) >= 10:
                    break

        if not matches:
            self.landmark_results.hide()
            return

        for st in matches:
            item = QListWidgetItem(st['name'])
            item.setData(Qt.UserRole, st)
            self.landmark_results.addItem(item)

        pos = self.landmark_search.mapToGlobal(self.landmark_search.rect().bottomLeft())
        self.landmark_results.move(pos)
        self.landmark_results.show()

    def _on_street_search_error(self, error_msg):
        """Handle street search error."""
        Toast.show_toast(self, "تعذر تحميل بيانات الخريطة", Toast.ERROR)
        logger.warning(f"Street search worker failed: {error_msg}")
        self.landmark_results.hide()

    @staticmethod
    def _extract_center_from_linestring(wkt):
        """Extract center point from a WKT LINESTRING."""
        if not wkt:
            return None, None
        match = re.match(r'LINESTRING\s*\((.+)\)', wkt, re.IGNORECASE)
        if not match:
            return None, None
        coords = match.group(1).split(',')
        mid = len(coords) // 2
        parts = coords[mid].strip().split()
        if len(parts) >= 2:
            return float(parts[1]), float(parts[0])
        return None, None

    def _do_neighborhood_search(self, query):
        """Search neighborhoods from local GeoJSON."""
        try:
            from services import boundary_service
            raw = boundary_service.get('neighbourhoods')
            if not raw:
                self.landmark_results.hide()
                return

            data = json.loads(raw)
            features = data.get('features', [])
            query_lower = query.lower()

            matches = []
            for f in features:
                props = f.get('properties', {})
                name_ar = props.get('NAME_AR', '')
                name_en = props.get('NAME_EN', '')
                if query_lower in (name_ar or '').lower() or query_lower in (name_en or '').lower():
                    matches.append({
                        'name_ar': name_ar,
                        'name_en': name_en,
                        'latitude': props.get('LATITUDE'),
                        'longitude': props.get('LONGITUDE'),
                        'adm1_ar': props.get('ADM1_AR', ''),
                        '_type': 'neighborhood',
                    })
                    if len(matches) >= 10:
                        break

            self.landmark_results.clear()
            if not matches:
                self.landmark_results.hide()
                return

            for nb in matches:
                display = f"{nb['name_ar']} - {nb['adm1_ar']}" if nb['adm1_ar'] else nb['name_ar']
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, nb)
                self.landmark_results.addItem(item)

            pos = self.landmark_search.mapToGlobal(self.landmark_search.rect().bottomLeft())
            self.landmark_results.move(pos)
            self.landmark_results.show()

        except Exception as e:
            Toast.show_toast(self, "تعذر تحميل بيانات الخريطة", Toast.ERROR)
            logger.warning(f"Neighborhood search failed: {e}")
            self.landmark_results.hide()

    def _on_landmark_result_clicked(self, item):
        """Handle search result click — pan map to location."""
        data = item.data(Qt.UserRole)
        if not data:
            return

        self.landmark_results.hide()
        self.landmark_search.clear()

        lat = data.get('latitude')
        lng = data.get('longitude')

        if not self.web_view or not lat or not lng:
            return

        result_type = data.get('_type', '')
        if result_type == 'neighborhood':
            js = f"map.setView([{lat}, {lng}], 15);"
            self.web_view.page().runJavaScript(js)
        elif result_type == 'street':
            js = f"map.setView([{lat}, {lng}], 16);"
            self.web_view.page().runJavaScript(js)
        else:
            lm_id = data.get('id', '')
            js = f"if (typeof panToLandmark === 'function') {{ panToLandmark('{lm_id}'); }} else {{ map.setView([{lat}, {lng}], 16); }}"
            self.web_view.page().runJavaScript(js)

    def _update_viewport_landmarks_streets(self, viewport_data: dict):
        """Reload landmarks and streets for the current viewport (non-blocking)."""
        if not self.web_view:
            return

        zoom = viewport_data.get('zoom', 0)

        try:
            from services.api_client import get_api_client
            api = get_api_client()

            ne_lat = viewport_data['ne_lat']
            ne_lng = viewport_data['ne_lng']
            sw_lat = viewport_data['sw_lat']
            sw_lng = viewport_data['sw_lng']

            # Only load landmarks when zoom >= 14 (layer visibility threshold)
            if zoom >= 14:
                self._viewport_landmarks_worker = ApiWorker(
                    api.get_landmarks_for_map,
                    north_east_lat=ne_lat, north_east_lng=ne_lng,
                    south_west_lat=sw_lat, south_west_lng=sw_lng
                )
                self._viewport_landmarks_worker.finished.connect(self._on_viewport_landmarks_ready)
                self._viewport_landmarks_worker.error.connect(
                    lambda msg: logger.warning(f"Viewport landmarks worker failed: {msg}")
                )
                self._viewport_landmarks_worker.start()

            # Only load streets when zoom >= 13 (layer visibility threshold)
            if zoom >= 13:
                self._viewport_streets_worker = ApiWorker(
                    api.get_streets_for_map,
                    north_east_lat=ne_lat, north_east_lng=ne_lng,
                    south_west_lat=sw_lat, south_west_lng=sw_lng
                )
                self._viewport_streets_worker.finished.connect(self._on_viewport_streets_ready)
                self._viewport_streets_worker.error.connect(
                    lambda msg: logger.warning(f"Viewport streets worker failed: {msg}")
                )
                self._viewport_streets_worker.start()

        except Exception as e:
            logger.warning(f"Could not start landmarks/streets workers: {e}")

    def _on_viewport_landmarks_ready(self, landmarks):
        """Handle viewport landmarks loaded in background."""
        if not landmarks or not self.web_view:
            return
        try:
            landmarks = [_normalize_landmark(lm) for lm in landmarks]
            landmarks_str = json.dumps(landmarks, ensure_ascii=False)
            js = f"if (typeof updateLandmarksOnMap === 'function') {{ updateLandmarksOnMap({landmarks_str}); }}"
            self.web_view.page().runJavaScript(js)
        except Exception as e:
            logger.warning(f"Error processing viewport landmarks: {e}")

    def _on_viewport_streets_ready(self, streets):
        """Handle viewport streets loaded in background."""
        if not streets or not self.web_view:
            return
        try:
            streets = [_normalize_street(s) for s in streets]
            streets_str = json.dumps(streets, ensure_ascii=False)
            js = f"if (typeof updateStreetsOnMap === 'function') {{ updateStreetsOnMap({streets_str}); }}"
            self.web_view.page().runJavaScript(js)
        except Exception as e:
            logger.warning(f"Error processing viewport streets: {e}")

    def update_language(self, is_arabic: bool):
        """تحديث اللغة."""
        pass

    def closeEvent(self, event):
        """Clean up on close (shared tile server remains active)."""
        # Note: We don't shutdown the shared tile server as it may be used by other components
        super().closeEvent(event)
