# -*- coding: utf-8 -*-
"""
Leaflet HTML Generator - Unified Map Display.

Generates Leaflet HTML with support for both Point and Polygon geometries.
Follows best practices from Leaflet.js documentation.

Best Practices Applied:
1. L.geoJSON() with pointToLayer for points (markers/circle markers)
2. style function for polygons
3. FeatureGroup for unified layer management
4. Proper event handling with onEachFeature
5. Layer control for toggling between views

References:
- https://leafletjs.com/examples/geojson/
- https://leafletjs.com/reference.html#geojson
- https://github.com/skylarkdrones/pyqtlet
"""

from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class LeafletHTMLGenerator:
    """
    Generates Leaflet HTML for unified building visualization.

    Design Pattern: Builder Pattern
    - Builds complex HTML structure step by step
    - Allows customization while maintaining consistency
    """

    # Status color mapping (shared across all maps)
    STATUS_COLORS = {
        'intact': '#28a745',
        'minor_damage': '#ffc107',
        'major_damage': '#fd7e14',
        'destroyed': '#dc3545'
    }

    STATUS_LABELS_AR = {
        'intact': 'سليم',
        'minor_damage': 'ضرر طفيف',
        'major_damage': 'ضرر كبير',
        'destroyed': 'مدمر'
    }

    @staticmethod
    def generate(
        tile_server_url: str,
        buildings_geojson: str,
        center_lat: float = 36.2021,
        center_lon: float = 37.1343,
        zoom: int = 14,
        show_legend: bool = True,
        show_layer_control: bool = True,
        enable_drawing: bool = False,
        enable_selection: bool = False,
        drawing_mode: str = 'both'  # 'point', 'polygon', 'both'
    ) -> str:
        """
        Generate Leaflet HTML with unified geometry display.

        Args:
            tile_server_url: URL for tile server
            buildings_geojson: GeoJSON FeatureCollection string
            center_lat: Map center latitude
            center_lon: Map center longitude
            zoom: Initial zoom level
            show_legend: Show status legend
            show_layer_control: Show layer toggle control
            enable_drawing: Enable polygon drawing tools
            enable_selection: Enable building selection button in popup
            drawing_mode: Drawing mode ('point', 'polygon', 'both')

        Returns:
            Complete HTML string ready for QWebEngineView
        """
        # إضافة Leaflet.draw إذا كان الرسم مفعلاً
        drawing_css = f'<link rel="stylesheet" href="{tile_server_url}/leaflet-draw.css" />' if enable_drawing else ''
        drawing_js = f'<script src="{tile_server_url}/leaflet-draw.js"></script>' if enable_drawing else ''

        return f'''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة حلب - UN-Habitat</title>
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    {drawing_css}
    <script src="{tile_server_url}/leaflet.js"></script>
    {drawing_js}
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    {LeafletHTMLGenerator._get_styles(enable_selection, enable_drawing)}
</head>
<body>
    <div class="offline-badge">وضع Offline</div>
    <div id="map"></div>
    {LeafletHTMLGenerator._get_javascript(
        tile_server_url,
        buildings_geojson,
        center_lat,
        center_lon,
        zoom,
        show_legend,
        show_layer_control,
        enable_drawing,
        enable_selection,
        drawing_mode
    )}
</body>
</html>
'''

    @staticmethod
    def _get_styles(enable_selection: bool = False, enable_drawing: bool = False) -> str:
        """Get CSS styles for map."""
        selection_styles = '''
        /* Selection Button */
        .select-building-btn {
            width: 100%;
            padding: 8px 12px;
            margin-top: 12px;
            background: linear-gradient(135deg, #0072BC 0%, #005A94 100%);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            font-size: 13px;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .select-building-btn:hover {
            background: linear-gradient(135deg, #005A94 0%, #004070 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .select-building-btn:active {
            transform: translateY(0);
        }
        ''' if enable_selection else ''

        drawing_styles = '''
        /* Drawing Controls */
        .leaflet-draw-toolbar {
            direction: ltr !important;
        }
        .drawing-mode-indicator {
            position: absolute;
            top: 60px;
            right: 10px;
            z-index: 1000;
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            font-size: 12px;
            font-weight: 600;
            color: #0072BC;
            display: none;
        }
        ''' if enable_drawing else ''

        return f'''
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ height: 100%; width: 100%; }}
        #map {{ height: 100%; width: 100%; }}

        /* RTL Support */
        .leaflet-popup-content-wrapper {{
            direction: rtl;
            text-align: right;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}

        /* Building Popup */
        .building-popup {{
            min-width: 200px;
        }}
        .building-popup h4 {{
            margin: 0 0 8px 0;
            color: #0072BC;
            font-size: 14px;
            font-weight: 600;
        }}
        .building-popup p {{
            margin: 4px 0;
            font-size: 12px;
            color: #333;
        }}
        .building-popup .label {{
            font-weight: 600;
            color: #666;
        }}

        /* Status Badge */
        .status-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            color: white;
            font-weight: 600;
        }}
        .status-intact {{ background-color: #28a745; }}
        .status-minor_damage {{ background-color: #ffc107; color: #333; }}
        .status-major_damage {{ background-color: #fd7e14; }}
        .status-destroyed {{ background-color: #dc3545; }}

        /* Geometry Type Badge */
        .geometry-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 10px;
            background-color: #6c757d;
            color: white;
            margin-left: 4px;
        }}

        /* Legend */
        .legend {{
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            font-size: 12px;
            direction: rtl;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}
        .legend h4 {{
            margin: 0 0 8px 0;
            font-size: 13px;
            color: #333;
            font-weight: 600;
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
            box-shadow: 0 0 2px rgba(0,0,0,0.3);
        }}

        /* Offline Badge */
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
            font-weight: 600;
        }}

        /* Polygon Styles */
        .leaflet-interactive {{
            cursor: pointer;
        }}

        /* Highlight on hover */
        .building-polygon:hover {{
            fill-opacity: 0.7;
        }}

        {selection_styles}
        {drawing_styles}
    </style>
'''

    @staticmethod
    def _get_javascript(
        tile_server_url: str,
        buildings_geojson: str,
        center_lat: float,
        center_lon: float,
        zoom: int,
        show_legend: bool,
        show_layer_control: bool,
        enable_drawing: bool = False,
        enable_selection: bool = False,
        drawing_mode: str = 'both'
    ) -> str:
        """Get JavaScript code for map initialization."""
        status_colors = LeafletHTMLGenerator.STATUS_COLORS
        status_labels = LeafletHTMLGenerator.STATUS_LABELS_AR

        return f'''
    <script>
        // Fix Leaflet icon paths for local serving
        L.Icon.Default.imagePath = '{tile_server_url}/images/';

        // Initialize map centered on Aleppo
        var map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});

        // Add tile layer from local server
        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 16,
            minZoom: 10,
            attribution: 'Map data &copy; OpenStreetMap | UN-Habitat Syria'
        }}).addTo(map);

        // Status colors and labels
        var statusColors = {status_colors};
        var statusLabels = {status_labels};

        // Buildings GeoJSON
        var buildingsData = {buildings_geojson};

        // Create separate layers for points and polygons
        var pointsLayer = L.featureGroup();
        var polygonsLayer = L.featureGroup();

        // Add buildings layer with unified geometry handling
        // Best Practice: Use L.geoJSON with pointToLayer and style
        // Reference: https://leafletjs.com/examples/geojson/
        var buildingsLayer = L.geoJSON(buildingsData, {{
            // Style function for Polygon/MultiPolygon features
            // Reference: https://leafletjs.com/reference.html#geojson-style
            style: function(feature) {{
                var status = feature.properties.status || 'intact';
                var color = statusColors[status] || '#0072BC';

                return {{
                    color: '#fff',
                    weight: 2,
                    fillColor: color,
                    fillOpacity: 0.6,
                    opacity: 1,
                    className: 'building-polygon'
                }};
            }},

            // pointToLayer for Point features
            // Reference: https://leafletjs.com/reference.html#geojson-pointtolayer
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

            // onEachFeature for popups and events
            // Reference: https://leafletjs.com/reference.html#geojson-oneachfeature
            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var status = props.status || 'intact';
                var statusLabel = statusLabels[status] || status;
                var statusClass = 'status-' + status;
                var geomType = props.geometry_type || 'Point';

                // Build popup content
                var popup = '<div class="building-popup">' +
                    '<h4>' + (props.building_id || 'مبنى') + ' ' +
                    '<span class="geometry-badge">' + geomType + '</span></h4>' +
                    '<p><span class="label">الحي:</span> ' + (props.neighborhood || 'غير محدد') + '</p>' +
                    '<p><span class="label">الحالة:</span> ' +
                    '<span class="status-badge ' + statusClass + '">' + statusLabel + '</span></p>' +
                    '<p><span class="label">الوحدات:</span> ' + (props.units || 0) + '</p>';

                if (props.type) {{
                    popup += '<p><span class="label">النوع:</span> ' + props.type + '</p>';
                }}

                // إضافة زر الاختيار إذا كان مفعلاً
                {'if (props.building_id) { popup += \'<button class="select-building-btn" onclick="selectBuilding(\\\'\" + props.building_id + \"\\\')"><span style=\"font-size:16px\">✓</span> اختيار هذا المبنى</button>\'; }' if enable_selection else '// Selection disabled'}

                popup += '</div>';

                layer.bindPopup(popup);

                // Add to appropriate layer group
                if (geomType === 'Point') {{
                    pointsLayer.addLayer(layer);
                }} else {{
                    polygonsLayer.addLayer(layer);
                }}

                // Highlight on hover (polygons only)
                if (geomType !== 'Point') {{
                    layer.on('mouseover', function(e) {{
                        this.setStyle({{
                            fillOpacity: 0.8,
                            weight: 3
                        }});
                    }});

                    layer.on('mouseout', function(e) {{
                        buildingsLayer.resetStyle(this);
                    }});
                }}
            }}
        }}).addTo(map);

        // Fit to buildings if any
        if (buildingsData.features && buildingsData.features.length > 0) {{
            try {{
                map.fitBounds(buildingsLayer.getBounds(), {{ padding: [50, 50] }});
            }} catch(e) {{
                console.log('Could not fit bounds:', e);
            }}
        }}

        {LeafletHTMLGenerator._get_legend_js() if show_legend else ''}

        {LeafletHTMLGenerator._get_layer_control_js() if show_layer_control else ''}

        // Function to highlight building (called from Python)
        function highlightBuilding(buildingId) {{
            buildingsLayer.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties.building_id === buildingId) {{
                    // Open popup
                    layer.openPopup();

                    // Pan to building
                    if (layer.getLatLng) {{
                        map.panTo(layer.getLatLng());
                    }} else if (layer.getBounds) {{
                        map.fitBounds(layer.getBounds(), {{ padding: [100, 100] }});
                    }}

                    // Highlight temporarily
                    if (layer.feature.geometry.type !== 'Point') {{
                        var originalStyle = {{
                            fillOpacity: 0.6,
                            weight: 2
                        }};

                        layer.setStyle({{
                            fillOpacity: 1.0,
                            weight: 4,
                            color: '#FF0000'
                        }});

                        setTimeout(function() {{
                            buildingsLayer.resetStyle(layer);
                        }}, 2000);
                    }}
                }}
            }});
        }}

        // Expose functions to Python
        window.highlightBuilding = highlightBuilding;

        {LeafletHTMLGenerator._get_selection_js() if enable_selection else '// Selection disabled'}

        {LeafletHTMLGenerator._get_drawing_js(drawing_mode) if enable_drawing else '// Drawing disabled'}

        // Log statistics
        var pointCount = pointsLayer.getLayers().length;
        var polygonCount = polygonsLayer.getLayers().length;
        console.log('Map loaded:', pointCount, 'points,', polygonCount, 'polygons');
    </script>
'''

    @staticmethod
    def _get_legend_js() -> str:
        """Get JavaScript for legend control."""
        return '''
        // Add legend
        var legend = L.control({ position: 'bottomright' });
        legend.onAdd = function(map) {
            var div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<h4>دليل الحالات</h4>' +
                '<div class="legend-item">' +
                '<div class="legend-color" style="background:#28a745"></div>سليم</div>' +
                '<div class="legend-item">' +
                '<div class="legend-color" style="background:#ffc107"></div>ضرر طفيف</div>' +
                '<div class="legend-item">' +
                '<div class="legend-color" style="background:#fd7e14"></div>ضرر كبير</div>' +
                '<div class="legend-item">' +
                '<div class="legend-color" style="background:#dc3545"></div>مدمر</div>';
            return div;
        };
        legend.addTo(map);
'''

    @staticmethod
    def _get_layer_control_js() -> str:
        """Get JavaScript for layer control (optional)."""
        return '''
        // Add layer control (optional - for future use)
        // var overlays = {
        //     "نقاط (Points)": pointsLayer,
        //     "مضلعات (Polygons)": polygonsLayer
        // };
        // L.control.layers(null, overlays).addTo(map);
'''

    @staticmethod
    def _get_selection_js() -> str:
        """Get JavaScript for building selection via QWebChannel."""
        return '''
        // QWebChannel setup for building selection
        var bridge = null;

        if (typeof QWebChannel !== 'undefined') {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                bridge = channel.objects.buildingBridge || channel.objects.bridge;
                console.log('QWebChannel initialized for selection');
            });
        }

        // Function to select building (called from popup button)
        function selectBuilding(buildingId) {
            console.log('Selecting building:', buildingId);

            if (bridge && bridge.selectBuilding) {
                bridge.selectBuilding(buildingId);
                map.closePopup();
            } else if (bridge && bridge.buildingSelected) {
                bridge.buildingSelected(buildingId);
                map.closePopup();
            } else {
                console.error('Bridge not initialized or selectBuilding method not found');
                alert('خطأ: لا يمكن اختيار المبنى. جسر الاتصال غير متاح.');
            }
        }

        window.selectBuilding = selectBuilding;
'''

    @staticmethod
    def _get_drawing_js(drawing_mode: str = 'both') -> str:
        """
        Get JavaScript for drawing tools (points and polygons).

        Args:
            drawing_mode: 'point', 'polygon', or 'both'
        """
        from services.leaflet_drawing_template import DRAWING_JS_TEMPLATE

        # تحديد الأدوات المفعلة
        enable_marker = 'true' if drawing_mode in ['point', 'both'] else 'false'
        enable_polygon = 'true' if drawing_mode in ['polygon', 'both'] else 'false'

        # استبدال placeholders في template
        result = (DRAWING_JS_TEMPLATE
                  .replace('__DRAWING_MODE__', drawing_mode)
                  .replace('__ENABLE_MARKER__', enable_marker)
                  .replace('__ENABLE_POLYGON__', enable_polygon))

        return result
# Export convenience function
def generate_leaflet_html(
    tile_server_url: str,
    buildings_geojson: str,
    **kwargs
) -> str:
    """
    Convenience function for generating Leaflet HTML.

    Args:
        tile_server_url: URL for tile server
        buildings_geojson: GeoJSON FeatureCollection string
        **kwargs: Additional options (center_lat, center_lon, zoom, etc.)

    Returns:
        Complete HTML string
    """
    return LeafletHTMLGenerator.generate(
        tile_server_url,
        buildings_geojson,
        **kwargs
    )
