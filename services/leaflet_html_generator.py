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

import json
from typing import Dict, Optional
from utils.logger import get_logger
from ui.constants.map_constants import MapConstants

logger = get_logger(__name__)


class LeafletHTMLGenerator:
    """
    Generates Leaflet HTML for unified building visualization.

    Design Pattern: Builder Pattern
    - Builds complex HTML structure step by step
    - Allows customization while maintaining consistency

    Best Practices:
    - DRY: Uses MapConstants for colors (Single Source of Truth)
    - Professional clustering for handling thousands of buildings
    - Optimized for performance and scalability
    """

    # Import status colors from MapConstants (DRY principle)
    STATUS_COLORS = MapConstants.STATUS_COLORS
    STATUS_LABELS_AR = MapConstants.STATUS_LABELS_AR

    @staticmethod
    def generate(
        tile_server_url: str,
        buildings_geojson: str,
        center_lat: float = 36.2021,
        center_lon: float = 37.1343,
        zoom: int = 16,  # ✅ محسّن: زوم أعلى (16 بدلاً من 14) للوضوح الأفضل
        min_zoom: int = None,  # NEW: Minimum zoom level (prevents zooming out)
        max_zoom: int = 17,  # NEW: Maximum zoom level (based on available tiles)
        show_legend: bool = True,
        show_layer_control: bool = True,
        enable_drawing: bool = False,
        enable_selection: bool = False,
        enable_multiselect: bool = False,  # NEW: Enable multi-select clicking mode
        enable_viewport_loading: bool = False,  # NEW: Enable viewport-based loading
        drawing_mode: str = 'both',  # 'point', 'polygon', 'both'
        existing_polygons_geojson: str = None  # GeoJSON for existing polygons (blue)
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
            enable_multiselect: Enable multi-select clicking mode (select multiple buildings by clicking)
            enable_viewport_loading: Enable viewport-based loading for millions of buildings
            drawing_mode: Drawing mode ('point', 'polygon', 'both')
            existing_polygons_geojson: GeoJSON for existing polygons (displayed in blue)

        Returns:
            Complete HTML string ready for QWebEngineView
        """
        # إضافة Leaflet.draw إذا كان الرسم مفعلاً
        drawing_css = f'<link rel="stylesheet" href="{tile_server_url}/leaflet-draw.css" />' if enable_drawing else ''
        drawing_js = f'<script src="{tile_server_url}/leaflet-draw.js"></script>' if enable_drawing else ''

        # إضافة Leaflet.markercluster للـ clustering (best practice for thousands of buildings)
        clustering_css = '''
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />'''
        clustering_js = '<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>'

        html = f'''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة حلب - UN-Habitat</title>
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    {clustering_css}
    {drawing_css}
    <script src="{tile_server_url}/leaflet.js"></script>
    {clustering_js}
    {drawing_js}
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    {LeafletHTMLGenerator._get_styles(enable_selection, enable_drawing, enable_multiselect)}
</head>
<body>
    <div id="map"></div>
    {LeafletHTMLGenerator._get_javascript(
        tile_server_url,
        buildings_geojson,
        center_lat,
        center_lon,
        zoom,
        min_zoom,
        max_zoom,
        show_legend,
        show_layer_control,
        enable_drawing,
        enable_selection,
        enable_multiselect,
        enable_viewport_loading,
        drawing_mode,
        existing_polygons_geojson
    )}
</body>
</html>
'''

        return html

    @staticmethod
    def _get_styles(enable_selection: bool = False, enable_drawing: bool = False, enable_multiselect: bool = False) -> str:
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

        /* إصلاح أيقونات أدوات الرسم - استخدام SVG مضمنة بدلاً من الصور */
        .leaflet-draw-toolbar a {
            background-image: none !important;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }

        /* أيقونة رسم المضلع */
        .leaflet-draw-draw-polygon::before {
            content: "⬡";
            font-size: 20px;
        }

        /* أيقونة رسم النقطة/العلامة */
        .leaflet-draw-draw-marker::before {
            content: "📍";
            font-size: 18px;
        }

        /* أيقونة التعديل */
        .leaflet-draw-edit-edit::before {
            content: "✏️";
            font-size: 16px;
        }

        /* أيقونة الحذف */
        .leaflet-draw-edit-remove::before {
            content: "🗑️";
            font-size: 16px;
        }

        /* تحسين مظهر أزرار الأدوات */
        .leaflet-draw-toolbar .leaflet-draw-draw-polygon,
        .leaflet-draw-toolbar .leaflet-draw-draw-marker,
        .leaflet-draw-toolbar .leaflet-draw-edit-edit,
        .leaflet-draw-toolbar .leaflet-draw-edit-remove {
            background-color: white !important;
            border: 2px solid #ccc !important;
            border-radius: 4px;
        }

        .leaflet-draw-toolbar a:hover {
            background-color: #f0f0f0 !important;
        }

        .leaflet-draw-toolbar .leaflet-draw-toolbar-button-enabled {
            background-color: #0072BC !important;
        }
        ''' if enable_drawing else ''

        multiselect_styles = '''
        /* Multi-Select Mode Styles */
        .selected-building {
            cursor: pointer !important;
        }

        .selected-pin {
            filter: drop-shadow(0 4px 8px rgba(255, 107, 0, 0.6));
            animation: pulse-selection 1.5s ease-in-out infinite;
        }

        @keyframes pulse-selection {
            0%, 100% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.1);
            }
        }

        /* Hover effect for selectable buildings */
        .building-polygon:hover,
        .building-point:hover {
            cursor: pointer;
            opacity: 0.9;
        }
        ''' if enable_multiselect else ''

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

        /* ✅ SVG Pin Icon Styling */
        .building-pin-icon {{
            background: transparent !important;
            border: none !important;
        }}

        .building-pin-icon svg {{
            transition: transform 0.2s ease-in-out;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }}

        .building-pin-icon:hover svg {{
            transform: scale(1.1);
            filter: drop-shadow(0 3px 6px rgba(0,0,0,0.4));
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
        {multiselect_styles}
    </style>
'''

    @staticmethod
    def _get_javascript(
        tile_server_url: str,
        buildings_geojson: str,
        center_lat: float,
        center_lon: float,
        zoom: int,
        min_zoom: int,
        max_zoom: int,
        show_legend: bool,
        show_layer_control: bool,
        enable_drawing: bool = False,
        enable_selection: bool = False,
        enable_multiselect: bool = False,
        enable_viewport_loading: bool = False,
        drawing_mode: str = 'both',
        existing_polygons_geojson: str = None
    ) -> str:
        """Get JavaScript code for map initialization."""
        import json

        status_colors = LeafletHTMLGenerator.STATUS_COLORS
        status_labels = LeafletHTMLGenerator.STATUS_LABELS_AR

        # Convert Python dicts to JSON strings for JavaScript
        status_colors_json = json.dumps(status_colors)
        status_labels_json = json.dumps(status_labels)

        # Parse buildings GeoJSON string to dict, then embed directly in JavaScript
        try:
            buildings_dict = json.loads(buildings_geojson)
            buildings_json = json.dumps(buildings_dict)
        except:
            buildings_json = '{"type":"FeatureCollection","features":[]}'

        # Parse existing polygons if provided
        if existing_polygons_geojson:
            try:
                existing_polygons_dict = json.loads(existing_polygons_geojson)
                existing_polygons_json = json.dumps(existing_polygons_dict)
            except:
                existing_polygons_json = None
        else:
            existing_polygons_json = None

        return f'''
    <script>
        // Fix Leaflet icon paths for local serving
        L.Icon.Default.imagePath = '{tile_server_url}/images/';

        // Initialize map centered on Aleppo with zoom constraints
        // PERFORMANCE: preferCanvas for 10x faster rendering (Canvas vs SVG/DOM)
        // Reference: https://leafletjs.com/reference.html#map-prefercanvas
        var map = L.map('map', {{
            preferCanvas: true,   // CRITICAL: Use Canvas renderer (10x faster!)
            maxZoom: {max_zoom},  // Prevent zooming beyond available tiles
            minZoom: {min_zoom if min_zoom is not None else 13}  // ✅ Smart constraint: prevent zoom out beyond neighborhood!
        }}).setView([{center_lat}, {center_lon}], {zoom});

        // Add tile layer from local server
        var tileLayer = L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: {max_zoom},  // Maximum zoom (prevents gray tiles beyond available zoom levels)
            minZoom: 10,  // Allow zooming out to see full city
            attribution: 'Map data &copy; OpenStreetMap | UN-Habitat Syria',
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
        }});

        tileLayer.addTo(map);

        // Status colors and labels
        var statusColors = {status_colors_json};
        var statusLabels = {status_labels_json};

        // Status mapping from numeric codes to string keys
        // API returns: 1=Intact, 2=MinorDamage, 3=ModerateDamage, 4=MajorDamage, 5=SeverelyDamaged, 6=Destroyed, 7=UnderConstruction, 8=Abandoned
        var statusMapping = {{
            1: 'intact',
            2: 'minor_damage',
            3: 'major_damage',
            4: 'major_damage',
            5: 'severely_damaged',
            6: 'destroyed',
            7: 'under_construction',
            8: 'demolished',
            99: 'intact'  // Unknown -> default to intact
        }};

        // Helper function to get status string from numeric code
        function getStatusKey(status) {{
            return typeof status === 'number' ? (statusMapping[status] || 'intact') : status;
        }}

        // Buildings GeoJSON - Direct embedding (Simple & Works)
        var buildingsData = {buildings_json};

        // =========================================================
        // Professional Marker Clustering Configuration
        // =========================================================
        // Best Practice: Use marker clustering for handling thousands of buildings
        // Reference: https://github.com/Leaflet/Leaflet.markercluster

        // ✅ إعدادات Clustering محسّنة للأداء العالي (10,000+ مبنى)
        var markers = L.markerClusterGroup({{
            maxClusterRadius: 60,              // ✅ تقليل من 80 إلى 60 (أقل تداخل)
            spiderfyOnMaxZoom: true,          // Expand clusters at max zoom
            showCoverageOnHover: false,       // Don't show cluster area on hover
            zoomToBoundsOnClick: true,        // Zoom to cluster bounds on click
            disableClusteringAtZoom: 15,      // ✅ تغيير من 17 إلى 15 (تفاصيل أبكر)
            spiderfyDistanceMultiplier: 1.5,  // Space between spiderfied markers
            chunkedLoading: true,             // Load markers in chunks for performance
            chunkInterval: 100,                // ✅ تقليل من 200 إلى 100ms (أسرع)
            chunkDelay: 25,                    // ✅ تقليل من 50 إلى 25ms (أسرع)
            removeOutsideVisibleBounds: true,  // ✅ جديد: إزالة markers خارج viewport
            animate: true,                     // Smooth animations
            animateAddingMarkers: false        // ✅ جديد: تعطيل animation عند الإضافة (أسرع)
        }});

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
                var status = getStatusKey(feature.properties.status || 1);
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

            // pointToLayer for Point features - استخدام Pin Markers (أجمل وأوضح)
            // ✅ محسّن: SVG Pin marker بدلاً من Circle (أكثر وضوحاً وأداء أفضل)
            // Reference: https://leafletjs.com/reference.html#marker
            pointToLayer: function(feature, latlng) {{
                var status = getStatusKey(feature.properties.status || 1);
                var color = statusColors[status] || '#0072BC';

                // ✅ استخدام SVG Pin Marker (Professional + Fast Rendering)
                var pinIcon = L.divIcon({{
                    className: 'building-pin-icon',
                    html: '<div style="position: relative; width: 24px; height: 36px;">' +
                          '<svg width="24" height="36" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                          '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                          'fill="' + color + '" stroke="#fff" stroke-width="2"/>' +  // ✅ Color from status
                          '<circle cx="12" cy="12" r="4" fill="#fff"/>' +
                          '</svg></div>',
                    iconSize: [24, 36],
                    iconAnchor: [12, 36],      // نقطة الارتكاز (طرف الدبوس)
                    popupAnchor: [0, -36]      // موقع الـpopup فوق الدبوس
                }});

                return L.marker(latlng, {{icon: pinIcon}});
            }},

            // onEachFeature for popups and events
            // Reference: https://leafletjs.com/reference.html#geojson-oneachfeature
            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var status = props.status || 'intact';
                var statusLabel = statusLabels[status] || status;
                var statusClass = 'status-' + status;
                var geomType = props.geometry_type || 'Point';

                // تشخيص: طباعة معلومات عن كل مبنى يتم إضافته
                console.log('🏢 Adding building:', props.building_id, '(Type:', geomType + ')');

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
                {'if (props.building_id) { popup += "<button class=\\"select-building-btn\\" onclick=\\"selectBuilding(&apos;" + props.building_id + "&apos;)\\\"><span style=\\"font-size:16px\\">✓</span> اختيار هذا المبنى</button>"; }' if enable_selection else '// Selection disabled'}

                popup += '</div>';

                layer.bindPopup(popup);

                // Add to appropriate layer group
                // Points go to marker cluster, polygons go directly to map
                if (geomType === 'Point') {{
                    pointsLayer.addLayer(layer);
                    markers.addLayer(layer);  // Add point markers to cluster
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
        }});

        // Add marker cluster group to map (contains all point markers)
        map.addLayer(markers);

        // Add polygons layer to map (bypasses clustering)
        polygonsLayer.addTo(map);

        console.log('✅ Buildings layer created with clustering support');
        console.log('   - Markers in cluster:', markers.getLayers().length);
        console.log('   - Polygons on map:', polygonsLayer.getLayers().length);

        // Add existing polygons layer (displayed in blue)
        {LeafletHTMLGenerator._get_existing_polygons_js(existing_polygons_geojson) if existing_polygons_geojson else '// No existing polygons'}

        // Fit to buildings if any
        if (buildingsData.features && buildingsData.features.length > 0) {{
            try {{
                var bounds = buildingsLayer.getBounds();
                console.log('📍 Buildings bounds:', bounds);
                console.log('   - SouthWest:', bounds.getSouthWest());
                console.log('   - NorthEast:', bounds.getNorthEast());
                map.fitBounds(bounds, {{ padding: [50, 50] }});
                console.log('✅ Map fitted to buildings bounds');
            }} catch(e) {{
                console.error('❌ Could not fit bounds:', e);
                console.log('   Using default center instead');
            }}
        }} else {{
            console.warn('⚠️ No buildings to fit bounds to');
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

        {LeafletHTMLGenerator._get_selection_js() if (enable_selection or enable_viewport_loading or enable_drawing or enable_multiselect) else '// Selection disabled'}

        {LeafletHTMLGenerator._get_drawing_js(drawing_mode) if enable_drawing else '// Drawing disabled'}

        {LeafletHTMLGenerator._get_multiselect_js() if enable_multiselect else '// Multi-select disabled'}

        {LeafletHTMLGenerator._get_viewport_loading_js() if enable_viewport_loading else '// Viewport loading disabled'}
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
    def _get_existing_polygons_js(existing_polygons_geojson: str) -> str:
        """
        Get JavaScript for displaying existing polygons in blue.

        Args:
            existing_polygons_geojson: GeoJSON string containing existing building polygons

        Returns:
            JavaScript code to add existing polygons layer
        """
        # Parse and embed directly
        try:
            existing_polygons_dict = json.loads(existing_polygons_geojson)
            existing_polygons_json = json.dumps(existing_polygons_dict)
        except:
            existing_polygons_json = '{"type":"FeatureCollection","features":[]}'

        return f'''
        // Existing polygons layer (displayed in blue)
        var existingPolygonsData = {existing_polygons_json};

        if (existingPolygonsData && existingPolygonsData.features && existingPolygonsData.features.length > 0) {{
            var existingPolygonsLayer = L.geoJSON(existingPolygonsData, {{
                style: function(feature) {{
                    return {{
                        color: '#0056A3',        // Border: dark blue
                        weight: 2,
                        fillColor: '#0072BC',    // Fill: blue
                        fillOpacity: 0.3,
                        className: 'existing-polygon'
                    }};
                }},
                onEachFeature: function(feature, layer) {{
                    var props = feature.properties;

                    // Build popup content
                    var popup = '<div class="building-popup">' +
                        '<h4>' + (props.building_id || 'مبنى موجود') + '</h4>' +
                        '<p><span class="label">الحالة:</span> ' + (props.status || 'غير محدد') + '</p>' +
                        '<p class="note">مضلع موجود مسبقاً</p>' +
                        '</div>';

                    layer.bindPopup(popup);

                    // Hover effects
                    layer.on('mouseover', function(e) {{
                        this.setStyle({{
                            fillOpacity: 0.5,
                            weight: 3
                        }});
                    }});

                    layer.on('mouseout', function(e) {{
                        this.setStyle({{
                            fillOpacity: 0.3,
                            weight: 2
                        }});
                    }});

                    // Click event - emit to Python via QWebChannel
                    layer.on('click', function(e) {{
                        if (typeof qt !== 'undefined' && qt.webChannelTransport) {{
                            // Emit polygon clicked event to Python
                            console.log('Existing polygon clicked:', props.building_id);
                        }}
                    }});
                }}
            }}).addTo(map);

            console.log('Loaded', existingPolygonsData.features.length, 'existing polygons');
        }}
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
        var bridgeReady = false;
        var initAttempts = 0;
        var maxInitAttempts = 100;  // 5 seconds max (100 × 50ms)

        // ✅ FIX: Wait for qt.webChannelTransport to be ready (prevents timing issues)
        function initializeQWebChannel() {{
            initAttempts++;

            // Check for max attempts
            if (initAttempts > maxInitAttempts) {{
                console.error('❌ QWebChannel initialization failed after ' + (maxInitAttempts * 50) + 'ms');
                console.error('   typeof QWebChannel:', typeof QWebChannel);
                console.error('   typeof qt:', typeof qt);
                console.error('   qt.webChannelTransport:', typeof qt !== 'undefined' ? qt.webChannelTransport : 'N/A');
                return;
            }}

            if (typeof QWebChannel === 'undefined') {{
                console.log('⏳ QWebChannel not loaded yet (attempt ' + initAttempts + '), waiting...');
                setTimeout(initializeQWebChannel, 50);
                return;
            }}

            if (typeof qt === 'undefined' || !qt.webChannelTransport) {{
                if (initAttempts % 20 === 0) {{  // Log every second
                    console.log('⏳ Waiting for qt.webChannelTransport (attempt ' + initAttempts + ')...');
                }}
                setTimeout(initializeQWebChannel, 50);  // Retry in 50ms
                return;
            }}

            try {{
                console.log('🔄 Initializing QWebChannel (attempt ' + initAttempts + ')...');
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    bridge = channel.objects.buildingBridge || channel.objects.bridge;
                    if (!bridge) {{
                        console.error('❌ Bridge object not found in channel!');
                        console.error('   Available objects:', Object.keys(channel.objects));
                        return;
                    }}

                    window.bridge = bridge;  // Make bridge globally accessible
                    bridgeReady = true;
                    window.bridgeReady = true;  // Make bridgeReady globally accessible
                    console.log('✅ QWebChannel bridge ready for selection (attempt ' + initAttempts + ')');
                    console.log('   Bridge methods:', Object.keys(bridge));

                    // Notify Python that bridge is ready
                    if (bridge && bridge.onBridgeReady) {{
                        bridge.onBridgeReady();
                    }}

                    // Notify any waiting code that bridge is ready
                    if (typeof window.onBridgeReady === 'function') {{
                        window.onBridgeReady();
                    }}
                }});
            }} catch (error) {{
                console.error('❌ Failed to initialize QWebChannel:', error);
                console.error('   Error details:', error.message, error.stack);
            }}
        }}

        // Start initialization after a small delay to ensure DOM is ready
        setTimeout(initializeQWebChannel, 100);

        // Function to select building (called from popup button)
        // ✅ FIX: Wait for bridge or retry with timeout
        function selectBuilding(buildingId) {{
            console.log('🏢 Selecting building:', buildingId);

            // ✅ Check if bridge is ready
            if (bridgeReady && bridge && (bridge.selectBuilding || bridge.buildingSelected)) {{
                // Bridge ready - select immediately
                if (bridge.selectBuilding) {{
                    bridge.selectBuilding(buildingId);
                }} else {{
                    bridge.buildingSelected(buildingId);
                }}
                map.closePopup();
                console.log('✅ Building selected via bridge');
            }} else if (!bridgeReady) {{
                // Bridge not ready yet - wait 500ms and retry
                console.warn('⏳ Bridge not ready, waiting 500ms...');
                setTimeout(function() {{
                    if (bridgeReady && bridge && (bridge.selectBuilding || bridge.buildingSelected)) {{
                        if (bridge.selectBuilding) {{
                            bridge.selectBuilding(buildingId);
                        }} else {{
                            bridge.buildingSelected(buildingId);
                        }}
                        map.closePopup();
                        console.log('✅ Building selected after retry');
                    }} else {{
                        console.error('❌ Bridge still not ready after 500ms');
                        // Don't show alert - just log error (user can try again)
                    }}
                }}, 500);
            }} else {{
                console.error('❌ Bridge initialized but methods not found');
            }}
        }}

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

    @staticmethod
    def _get_multiselect_js() -> str:
        """
        Get JavaScript for multi-select clicking mode.

        Allows users to click on buildings to select/deselect them.
        """
        from services.leaflet_multiselect_template import MULTISELECT_JS_TEMPLATE
        return MULTISELECT_JS_TEMPLATE

    @staticmethod
    def _get_viewport_loading_js() -> str:
        """
        Get JavaScript for viewport-based loading.

        Implements industry best practices for handling millions of buildings:
        - Only loads buildings in current viewport
        - Debounces requests during rapid pan/zoom
        - Updates markers dynamically without page reload
        """
        from services.leaflet_viewport_template import VIEWPORT_LOADING_JS_TEMPLATE
        return VIEWPORT_LOADING_JS_TEMPLATE
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
