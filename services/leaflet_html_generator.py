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
        zoom: int = 15,  #
        min_zoom: int = None,  # Minimum zoom level (prevents zooming out)
        max_zoom: int = 20,  #
        show_legend: bool = True,
        show_layer_control: bool = True,
        enable_drawing: bool = False,
        enable_selection: bool = False,
        enable_multiselect: bool = False,  # NEW: Enable multi-select clicking mode
        enable_viewport_loading: bool = False,  # NEW: Enable viewport-based loading
        drawing_mode: str = 'both',  # 'point', 'polygon', 'both'
        existing_polygons_geojson: str = None,  # GeoJSON for existing polygons (blue)
        initial_bounds: list = None,  # [[south_lat, west_lng], [north_lat, east_lng]]
        neighborhoods_geojson: str = None,  # GeoJSON for neighborhood boundaries overlay
        selected_neighborhood_code: str = None,  # Highlight this neighborhood
        skip_fit_bounds: bool = False  # Skip auto fitBounds (respect zoom param exactly)
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
            initial_bounds: Bounds to fitBounds on load [[south_lat, west_lng], [north_lat, east_lng]]

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
        existing_polygons_geojson,
        initial_bounds,
        neighborhoods_geojson,
        selected_neighborhood_code,
        skip_fit_bounds
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
            filter: drop-shadow(0 4px 8px rgba(33, 150, 243, 0.5));
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

        /* Neighborhood Layer Styles */
        .neighborhood-tooltip {{
            background: rgba(255, 255, 255, 0.92) !important;
            border: 1px solid #0072BC !important;
            border-radius: 6px !important;
            padding: 4px 10px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            color: #333 !important;
            direction: rtl !important;
            font-family: 'Segoe UI', Tahoma, sans-serif !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
            white-space: nowrap !important;
        }}
        .neighborhood-tooltip::before {{
            border-top-color: #0072BC !important;
        }}
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
        existing_polygons_geojson: str = None,
        initial_bounds: list = None,
        neighborhoods_geojson: str = None,
        selected_neighborhood_code: str = None,
        skip_fit_bounds: bool = False
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

        initial_bounds_js = json.dumps(initial_bounds) if initial_bounds else 'null'

        # Build popup JS block - skip popups in multi-select mode (clicking toggles selection)
        if enable_multiselect:
            popup_js_block = '// Multi-select mode: no popups, clicking toggles selection'
        else:
            selection_btn_js = (
                'if (buildingIdForApi) { popup += "<button class=\\"select-building-btn\\" '
                'onclick=\\"selectBuilding(&apos;" + buildingIdForApi + "&apos;)\\">'
                '<span style=\\"font-size:16px\\">✓</span> اختيار هذا المبنى</button>"; }'
            ) if enable_selection else '// Selection disabled'

            popup_js_block = (
                "var popup = '<div class=\"building-popup\">' +\n"
                "                    '<h4>' + buildingIdDisplay + ' ' +\n"
                "                    '<span class=\"geometry-badge\">' + geomType + '</span></h4>' +\n"
                "                    '<p><span class=\"label\">الحي:</span> ' + (props.neighborhood || 'غير محدد') + '</p>' +\n"
                "                    '<p><span class=\"label\">الحالة:</span> ' +\n"
                "                    '<span class=\"status-badge ' + statusClass + '\">' + statusLabel + '</span></p>' +\n"
                "                    '<p><span class=\"label\">الوحدات:</span> ' + (props.units || 0) + '</p>';\n"
                "\n"
                "                if (props.type) {\n"
                "                    popup += '<p><span class=\"label\">النوع:</span> ' + props.type + '</p>';\n"
                "                }\n"
                "\n"
                "                " + selection_btn_js + "\n"
                "\n"
                "                popup += '</div>';\n"
                "\n"
                "                layer.bindPopup(popup);"
            )

        # Build hover JS block - skip in multi-select mode (multiselect template adds its own)
        if enable_multiselect:
            hover_js_block = '// Hover handled by multi-select handler'
        else:
            hover_js_block = (
                "// Highlight on hover (polygons only)\n"
                "                if (geomType !== 'Point') {\n"
                "                    layer.on('mouseover', function(e) {\n"
                "                        this.setStyle({\n"
                "                            fillOpacity: 0.8,\n"
                "                            weight: 3\n"
                "                        });\n"
                "                    });\n"
                "\n"
                "                    layer.on('mouseout', function(e) {\n"
                "                        buildingsLayer.resetStyle(this);\n"
                "                    });\n"
                "                }"
            )

        return f'''
    <script>
        // Fix Leaflet icon paths for local serving
        L.Icon.Default.imagePath = '{tile_server_url}/images/';

        // Initialize map centered on Aleppo with zoom constraints
        // PERFORMANCE: preferCanvas for 10x faster rendering (Canvas vs SVG/DOM)
        // Reference: https://leafletjs.com/reference.html#map-prefercanvas
        var map = L.map('map', {{
            preferCanvas: true,   // CRITICAL: Use Canvas renderer (10x faster!)
            maxZoom: {max_zoom},  //
            minZoom: {min_zoom if min_zoom is not None else 15}  // Min zoom where tiles exist (15-20)
        }}).setView([{center_lat}, {center_lon}], {zoom});

        var initialBounds = {initial_bounds_js};
        if (initialBounds) {{
            map.fitBounds(initialBounds, {{padding: [50, 50]}});
        }}

        // Add tile layer from local server
        var tileLayer = L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: {max_zoom},  //
            minZoom: 15,  // Min zoom where tiles exist (15-20)
            attribution: 'Map data &copy; OpenStreetMap | UN-Habitat Syria',
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
        }});

        tileLayer.addTo(map);

        // Status colors and labels
        var statusColors = {status_colors_json};
        var statusLabels = {status_labels_json};

        var statusMapping = {{
            1: 'intact', 2: 'minor_damage', 3: 'major_damage',
            4: 'major_damage', 5: 'severely_damaged', 6: 'destroyed',
            7: 'under_construction', 8: 'demolished', 99: 'intact'
        }};

        var statusStringMapping = {{
            'intact': 'intact', 'standing': 'standing',
            'minordamage': 'minor_damage', 'minor_damage': 'minor_damage', 'damaged': 'damaged',
            'moderatedamage': 'major_damage', 'majordamage': 'major_damage', 'major_damage': 'major_damage',
            'partiallydamaged': 'partially_damaged', 'partially_damaged': 'partially_damaged',
            'severelydamaged': 'severely_damaged', 'severely_damaged': 'severely_damaged',
            'destroyed': 'destroyed', 'demolished': 'demolished', 'rubble': 'rubble',
            'underconstruction': 'under_construction', 'under_construction': 'under_construction',
            'abandoned': 'demolished'
        }};

        function getStatusKey(status) {{
            if (typeof status === 'number') return statusMapping[status] || 'intact';
            var key = String(status).toLowerCase().replace(/_/g, '');
            return statusStringMapping[key] || statusStringMapping[String(status).toLowerCase()] || 'intact';
        }}

        // Buildings GeoJSON - Direct embedding (Simple & Works)
        var buildingsData = {buildings_json};

        // Diagnostic: Log GeoJSON structure
        console.log('========================================');
        console.log('GeoJSON Loaded - Total Features:', buildingsData.features.length);
        if (buildingsData.features.length > 0) {{
            var sample = buildingsData.features[0];
            console.log('Sample Feature:');
            console.log('  - ID:', sample.id);
            console.log('  - Geometry Type:', sample.geometry.type);
            console.log('  - Properties geometry_type:', sample.properties.geometry_type);
            console.log('  - Has coordinates:', sample.geometry.coordinates ? 'Yes' : 'No');

            // Count by geometry type
            var polygonCount = buildingsData.features.filter(f => f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon').length;
            var pointCount = buildingsData.features.filter(f => f.geometry.type === 'Point').length;
            console.log('Feature Types:');
            console.log('  - Polygons:', polygonCount);
            console.log('  - Points:', pointCount);
        }}
        console.log('========================================');

        // =========================================================
        // Professional Marker Clustering Configuration
        // =========================================================
        // Best Practice: Use marker clustering for handling thousands of buildings
        // Reference: https://github.com/Leaflet/Leaflet.markercluster

        //
        var markers = L.markerClusterGroup({{
            maxClusterRadius: 60,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            disableClusteringAtZoom: 18,
            spiderfyDistanceMultiplier: 1.5,
            chunkedLoading: true,
            chunkInterval: 100,
            chunkDelay: 25,
            removeOutsideVisibleBounds: true,
            animate: true,
            animateAddingMarkers: false
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
            //
            // Reference: https://leafletjs.com/reference.html#marker
            pointToLayer: function(feature, latlng) {{
                var status = getStatusKey(feature.properties.status || 1);
                var color = statusColors[status] || '#0072BC';

                // SVG Pin Marker
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
                var actualGeomType = feature.geometry.type;

                // Diagnostic: Print detailed info about each building
                console.log('🏢 Adding building:', props.building_id);
                console.log('   - Actual Geometry Type (from GeoJSON):', actualGeomType);
                console.log('   - Property geometry_type:', geomType);
                console.log('   - MISMATCH:', actualGeomType !== geomType ? 'YES ⚠️' : 'No');

                // ✅ Use building_id_display (with dashes) for UI, building_id (no dashes) for API
                var buildingIdDisplay = props.building_id_display || props.building_id || 'مبنى';
                var buildingIdForApi = props.building_id;  // ✅ NO dashes for API

                {popup_js_block}

                // Add to appropriate layer group
                // IMPORTANT: We should use actualGeomType (from geometry) not geomType (from properties)
                // to ensure correct rendering
                if (actualGeomType === 'Point') {{
                    pointsLayer.addLayer(layer);
                    markers.addLayer(layer);  // Add point markers to cluster
                    console.log('   → Added to POINTS layer (marker)');
                }} else {{
                    polygonsLayer.addLayer(layer);
                    console.log('   → Added to POLYGONS layer');
                }}

                {hover_js_block}
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

        // Neighborhoods overlay layer (zoom-based visibility)
        {LeafletHTMLGenerator._get_neighborhoods_layer_js(neighborhoods_geojson, selected_neighborhood_code) if neighborhoods_geojson else '// No neighborhoods overlay'}

        // Fit to buildings if any (skip when initial_bounds or skip_fit_bounds set)
        var skipFitBounds = {'true' if skip_fit_bounds else 'false'};
        if (!skipFitBounds && !initialBounds && buildingsData.features && buildingsData.features.length > 0) {{
            try {{
                var bounds = buildingsLayer.getBounds();
                map.fitBounds(bounds, {{ padding: [50, 50] }});
                console.log('Map fitted to buildings bounds');
            }} catch(e) {{
                console.log('Using default center (fitBounds failed)');
            }}
        }} else if (skipFitBounds) {{
            console.log('fitBounds skipped - using exact zoom:', {zoom});
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
    def _get_neighborhoods_layer_js(neighborhoods_geojson: str, selected_neighborhood_code: str = None) -> str:
        """
        Get JavaScript for neighborhood center pins with zoom-based visibility.

        - Zoom 15-16: Neighborhood pins with Arabic name labels, buildings hidden
        - Zoom >= 17: Pins hidden, buildings visible (polygons + pin markers)
        - NO polygon borders — pins only

        Tile range: 15-20 (below 15 = gray, no tiles)
        """
        try:
            neighborhoods_dict = json.loads(neighborhoods_geojson)
            neighborhoods_json = json.dumps(neighborhoods_dict)
        except:
            return '// Invalid neighborhoods GeoJSON'

        selected_code = selected_neighborhood_code or ''

        return f'''
        // =========================================================
        // Neighborhood Center Pins (zoom-based visibility)
        // Tiles exist: zoom 15-20
        // Pins: zoom 15-16 (city overview with neighborhood labels)
        // Buildings: zoom 17+ (zoomed into a neighborhood)
        // =========================================================
        var neighborhoodsData = {neighborhoods_json};
        var selectedNeighborhoodCode = '{selected_code}';
        var neighborhoodPins = L.featureGroup();

        if (neighborhoodsData && neighborhoodsData.features && neighborhoodsData.features.length > 0) {{

            neighborhoodsData.features.forEach(function(feature) {{
                var props = feature.properties;
                var isSelected = props.code === selectedNeighborhoodCode;

                var pin = L.circleMarker(
                    [props.center_lat, props.center_lng],
                    {{
                        radius: isSelected ? 7 : 5,
                        fillColor: isSelected ? '#0072BC' : '#555',
                        color: '#fff',
                        weight: 2,
                        fillOpacity: 0.9
                    }}
                );

                pin.bindTooltip(props.name_ar, {{
                    permanent: true,
                    direction: 'top',
                    className: 'neighborhood-tooltip',
                    offset: [0, -8]
                }});

                neighborhoodPins.addLayer(pin);
            }});

            neighborhoodPins.addTo(map);

            // Zoom-based visibility:
            // zoom 15-16: neighborhood pins visible, buildings hidden
            // zoom >= 17: pins hidden, buildings visible
            function updateNeighborhoodVisibility() {{
                var zoom = map.getZoom();
                if (zoom >= 17) {{
                    // Zoomed into neighborhood — show buildings, hide pins
                    if (map.hasLayer(neighborhoodPins)) map.removeLayer(neighborhoodPins);
                    if (!map.hasLayer(markers)) map.addLayer(markers);
                    if (!map.hasLayer(polygonsLayer)) map.addLayer(polygonsLayer);
                }} else {{
                    // City overview (zoom 15-16) — show pins, hide buildings
                    if (!map.hasLayer(neighborhoodPins)) map.addLayer(neighborhoodPins);
                    if (map.hasLayer(markers)) map.removeLayer(markers);
                    if (map.hasLayer(polygonsLayer)) map.removeLayer(polygonsLayer);
                }}
            }}

            map.on('zoomend', updateNeighborhoodVisibility);
            updateNeighborhoodVisibility();

            console.log('Neighborhood pins loaded:', neighborhoodsData.features.length);
        }}
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

                    // ✅ Use building_id_display for UI, building_id for API
                    var buildingIdDisplay = props.building_id_display || props.building_id || 'مبنى موجود';
                    var buildingIdForApi = props.building_id;

                    // Build popup content
                    var popup = '<div class="building-popup">' +
                        '<h4>' + buildingIdDisplay + '</h4>' +
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
                            console.log('Existing polygon clicked:', buildingIdForApi);
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
