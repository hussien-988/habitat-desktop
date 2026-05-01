# -*- coding: utf-8 -*-
"""
Leaflet HTML Generator - Unified Map Display.

Generates Leaflet HTML with support for both Point and Polygon geometries,
including clustering, drawing tools, and viewport-based loading.
"""

import json
from pathlib import Path
from typing import Dict, Optional

from utils.logger import get_logger
from ui.constants.map_constants import MapConstants

logger = get_logger(__name__)


class LeafletHTMLGenerator:
    """Generates Leaflet HTML for unified building visualization."""

    # Import status colors from MapConstants
    STATUS_COLORS = MapConstants.STATUS_COLORS
    STATUS_LABELS_AR = MapConstants.STATUS_LABELS_AR

    _assets_cache: Dict[str, str] = {}

    @staticmethod
    def _js_escape(encoded: str) -> str:
        """Escape sequences that would break out of an HTML <script> block.

        ``</script>`` and HTML comment markers terminate the surrounding tag
        regardless of where they appear inside the script body — including
        inside string literals — because the HTML parser runs before the JS
        parser. Escaping the slashes here keeps the value semantically
        identical to JS (a backslash-slash is just an escaped slash) while
        making the payload inert at the HTML layer.
        """
        return (
            encoded
            .replace("</", "<\\/")
            .replace("<!--", "<\\!--")
            .replace("-->", "--\\>")
        )

    @staticmethod
    def _safe_js_json(value, fallback: str = '{}') -> str:
        """Encode JSON-like data for safe embedding in an HTML <script> block.

        Accepts a Python container (dict/list/etc.) or a *JSON-encoded* string
        — for the latter we parse and re-emit so we can canonicalize and
        catch malformed payloads up front. Plain (non-JSON) strings should
        use :py:meth:`_safe_js_string` instead, otherwise they round-trip
        through the fallback.
        """
        if value is None:
            return fallback
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return fallback
        try:
            encoded = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return fallback
        return LeafletHTMLGenerator._js_escape(encoded)

    @staticmethod
    def _safe_js_string(value, fallback: str = '""') -> str:
        """Encode an arbitrary string as a JS string literal, safely.

        Use for values that are *not* JSON — tile URL templates, path
        fragments, hostnames, etc. — where we want the JS source to contain
        ``"http://..."`` not the parsed structure.
        """
        if value is None:
            return fallback
        try:
            encoded = json.dumps(str(value), ensure_ascii=False)
        except (TypeError, ValueError):
            return fallback
        return LeafletHTMLGenerator._js_escape(encoded)

    @classmethod
    def _load_asset(cls, filename: str) -> str:
        """Read a leaflet asset file and cache it. Returns empty string on failure."""
        if filename not in cls._assets_cache:
            asset_path = Path(__file__).parent.parent / "assets" / "leaflet" / filename
            try:
                cls._assets_cache[filename] = asset_path.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Failed to load asset {filename}: {e}")
                cls._assets_cache[filename] = ""
        return cls._assets_cache[filename]

    @classmethod
    def _get_qwebchannel_content(cls) -> str:
        """Read qwebchannel.js from Qt resources and cache it."""
        cache_key = '_qwebchannel'
        if cache_key not in cls._assets_cache:
            try:
                from PyQt5.QtCore import QFile, QIODevice
                f = QFile(":/qtwebchannel/qwebchannel.js")
                if f.open(QIODevice.ReadOnly):
                    cls._assets_cache[cache_key] = bytes(f.readAll()).decode('utf-8')
                    f.close()
                else:
                    cls._assets_cache[cache_key] = ""
                    logger.warning("Could not open qrc:///qtwebchannel/qwebchannel.js")
            except Exception as e:
                cls._assets_cache[cache_key] = ""
                logger.warning(f"Failed to load qwebchannel.js: {e}")
        return cls._assets_cache[cache_key]

    @staticmethod
    def generate(
        tile_server_url: str,
        buildings_geojson: str,
        center_lat: float = MapConstants.DEFAULT_CENTER_LAT,
        center_lon: float = MapConstants.DEFAULT_CENTER_LON,
        zoom: int = MapConstants.DEFAULT_ZOOM,
        min_zoom: int = None,
        max_zoom: int = MapConstants.MAX_ZOOM,
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
        skip_fit_bounds: bool = False,  # Skip auto fitBounds (respect zoom param exactly)
        tile_layer_url: str = None,  # Separate URL for map tiles (defaults to tile_server_url)
        boundaries_geojson: str = None,  # GeoJSON for administrative boundary polygons
        boundary_level: str = None,  # Level name: 'governorates'|'subdistricts'|etc.
        places_json: str = None,  # JSON array of populated places for map labels
        landmarks_json: str = None,  # JSON array of landmarks for map overlay
        streets_json: str = None,  # JSON array of streets for map overlay
        max_selection: Optional[int] = None,  # None=unlimited; 1=single-select replace mode
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
        from services.tile_server_manager import get_local_server_url
        from services.translation_manager import tr as _tr
        local_assets_url = get_local_server_url()
        _loading_text = _tr('page.map.loading_map')

        # [SIMPLIFY] Force-disable features the app no longer needs:
        # drawing tools, boundary overlays, existing polygons, neighborhoods overlay, places labels.
        # Buildings are always rendered as markers/clusters (not polygons).
        enable_drawing = False
        drawing_mode = 'point'
        existing_polygons_geojson = None
        neighborhoods_geojson = None
        selected_neighborhood_code = None
        boundaries_geojson = None
        boundary_level = None
        places_json = None

        drawing_css = ''
        drawing_js = ''
        clustering_css = f'''
    <style>{LeafletHTMLGenerator._load_asset("MarkerCluster.css")}</style>
    <style>{LeafletHTMLGenerator._load_asset("MarkerCluster.Default.css")}</style>'''
        clustering_js = f'<script>{LeafletHTMLGenerator._load_asset("leaflet.markercluster.js")}</script>'
        qwebchannel_content = LeafletHTMLGenerator._get_qwebchannel_content()
        qwebchannel_tag = (
            f'<script>{qwebchannel_content}</script>'
            if qwebchannel_content else
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
        )

        html = f'''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="utf-8">
    <script>
        // [MAP_PERF_JS] Embedded perf timing — fires before any other script.
        // Captured by _PerfWebEnginePage.javaScriptConsoleMessage on the Python side.
        window._mp = function(name, extra) {{
            try {{
                var msg = '[MAP_PERF_JS] phase=' + name + ' t=' + Math.round(performance.now());
                if (extra) msg += ' ' + extra;
                console.log(msg);
            }} catch(e) {{}}
        }};
        window._mp('html_parsed_start');
        document.addEventListener('DOMContentLoaded', function() {{ window._mp('dom_ready'); }});
        window.addEventListener('load', function() {{ window._mp('window_load'); }});
    </script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>خريطة حلب - UN-Habitat</title>
    <style>{LeafletHTMLGenerator._load_asset("leaflet.css")}</style>
    <script>window._mp('css_main_loaded');</script>
    {clustering_css}
    {drawing_css}
    <script>{LeafletHTMLGenerator._load_asset("leaflet.js")}</script>
    <script>window._mp('leaflet_loaded');</script>
    {clustering_js}
    <script>window._mp('clustering_loaded');</script>
    {drawing_js}
    {qwebchannel_tag}
    <script>window._mp('qwebchannel_loaded');</script>
    {LeafletHTMLGenerator._get_styles(enable_selection, enable_drawing, enable_multiselect)}
</head>
<body>
    <div id="map"></div>
    <div id="map-loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">{_loading_text}</div>
    </div>
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
        skip_fit_bounds,
        tile_layer_url,
        boundaries_geojson,
        boundary_level,
        places_json,
        landmarks_json,
        streets_json,
        local_assets_url=local_assets_url,
        max_selection=max_selection,
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

        /* General toolbar links */
        .leaflet-draw-toolbar a {
            background-image: none !important;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }

        /* Polygon draw button — labeled blue chip */
        .leaflet-draw-draw-polygon {
            width: auto !important;
            padding: 0 10px 0 8px !important;
            background: linear-gradient(135deg, #0072BC, #005fa3) !important;
            border: none !important;
            border-radius: 6px !important;
            box-shadow: 0 2px 6px rgba(0, 114, 188, 0.3) !important;
            transition: all 0.2s ease !important;
            color: white !important;
            gap: 6px !important;
        }
        .leaflet-draw-draw-polygon::before {
            content: "⬡";
            font-size: 18px;
            color: white;
        }
        .leaflet-draw-draw-polygon:hover {
            background: linear-gradient(135deg, #005fa3, #004c82) !important;
            box-shadow: 0 3px 10px rgba(0, 114, 188, 0.45) !important;
        }
        .leaflet-draw-draw-polygon.leaflet-draw-toolbar-button-enabled {
            background: linear-gradient(135deg, #004c82, #003d6b) !important;
        }

        /* Injected text label inside polygon button */
        .draw-btn-label {
            font-size: 12px;
            font-family: 'Segoe UI', 'Tahoma', Arial, sans-serif;
            color: white;
            white-space: nowrap;
            font-weight: 500;
            vertical-align: middle;
            margin-right: 4px;
        }

        /* Marker icon */
        .leaflet-draw-draw-marker::before {
            content: "📍";
            font-size: 18px;
        }

        /* Edit icon */
        .leaflet-draw-edit-edit::before {
            content: "✏️";
            font-size: 16px;
        }

        /* Delete icon */
        .leaflet-draw-edit-remove::before {
            content: "🗑️";
            font-size: 16px;
        }

        /* Standard buttons (marker, edit, delete) */
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

        /* Modern circular vertex handles (replaces white squares) */
        .leaflet-editing-icon {
            border-radius: 50% !important;
            background: #0072BC !important;
            border: 2px solid white !important;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.35) !important;
            width: 10px !important;
            height: 10px !important;
            margin-left: -5px !important;
            margin-top: -5px !important;
        }
        .leaflet-editing-icon:hover {
            background: #004c82 !important;
            transform: scale(1.3);
        }

        /* Guide dots during active drawing */
        .leaflet-draw-guide-dot {
            width: 6px !important;
            height: 6px !important;
            border-radius: 50% !important;
            background: rgba(0, 114, 188, 0.55) !important;
            border: 2px solid rgba(0, 114, 188, 0.8) !important;
        }

        /* Draw tooltip — dark pill shape */
        .leaflet-draw-tooltip {
            background: rgba(20, 20, 20, 0.78) !important;
            color: white !important;
            border: none !important;
            border-radius: 4px !important;
            padding: 4px 8px !important;
            font-size: 11px !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
        }
        .leaflet-draw-tooltip::before {
            border-right-color: rgba(20, 20, 20, 0.78) !important;
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

        /* Dark background - replaces default gray (#ddd) for areas without tiles */
        .leaflet-container {{ background: {MapConstants.TILE_PANE_BACKGROUND} !important; }}
        .leaflet-tile-pane {{ background: {MapConstants.TILE_PANE_BACKGROUND}; }}

        /* GPU-accelerate tile compositing */
        .leaflet-tile-pane {{ will-change: transform; }}
        .leaflet-tile {{
            will-change: transform;
            backface-visibility: hidden;
        }}

        /* Loading overlay - hides map until all viewport tiles are ready */
        #map-loading-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: {MapConstants.TILE_PANE_BACKGROUND};
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: opacity 0.4s ease-out;
        }}
        #map-loading-overlay.fade-out {{
            opacity: 0;
            pointer-events: none;
        }}
        .loading-spinner {{
            width: 48px;
            height: 48px;
            border: 4px solid rgba(255,255,255,0.15);
            border-top: 4px solid #0072BC;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        .loading-text {{
            color: rgba(255,255,255,0.7);
            font-family: 'Segoe UI', Tahoma, sans-serif;
            font-size: 13px;
            margin-top: 16px;
            direction: rtl;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}

        /* RTL Support */
        .leaflet-popup-content-wrapper {{
            direction: rtl;
            text-align: right;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}

        /* Building Popup */
        .building-popup {{
            min-width: 200px;
            text-align: right;
        }}
        .building-popup[dir="auto"] {{
            text-align: right;
            direction: rtl;
        }}
        .building-popup h4 {{
            margin: 0 0 8px 0;
            color: #0072BC;
            font-size: 14px;
            font-weight: 600;
            text-align: right;
        }}
        .building-popup p {{
            margin: 4px 0;
            font-size: 12px;
            color: #333;
            text-align: right;
        }}
        .building-popup .label {{
            font-weight: 600;
            color: #666;
            display: inline-block;
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

        /* SVG Pin Icon Styling */
        .building-pin-icon {{
            background: transparent !important;
            border: none !important;
        }}

        .building-pin-icon svg {{
            transition: transform 0.15s ease-in-out;
        }}

        .building-pin-icon:hover svg {{
            transform: scale(1.1);
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

        /* [UNIFIED-DIALOG] Building ID tooltip (shown on pin hover) */
        .building-id-tooltip {{
            background: rgba(30, 41, 59, 0.92) !important;
            color: #F9FAFB !important;
            border: none !important;
            border-radius: 6px !important;
            padding: 4px 10px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            direction: rtl !important;
            font-family: 'Segoe UI', Tahoma, sans-serif !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.25) !important;
            white-space: nowrap !important;
        }}
        .building-id-tooltip::before {{
            border-top-color: rgba(30, 41, 59, 0.92) !important;
        }}

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
            margin-top: -6px !important;
            pointer-events: none !important;
        }}
        .neighborhood-tooltip::before {{
            border-top-color: #0072BC !important;
        }}
        .map-status-overlay {{
            background: rgba(255,255,255,0.85);
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 11px;
            direction: rtl;
            min-width: 120px;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}

        /* Landmark Pin Marker */
        .landmark-pin-icon {{
            background: transparent !important;
            border: none !important;
        }}

        /* Landmark Layer Styles */
        .landmark-tooltip {{
            background: rgba(255, 255, 255, 0.95) !important;
            border: 1px solid #7C3AED !important;
            border-radius: 6px !important;
            padding: 3px 8px !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            color: #333 !important;
            direction: rtl !important;
            font-family: 'Segoe UI', Tahoma, sans-serif !important;
            box-shadow: 0 1px 4px rgba(0,0,0,0.15) !important;
            white-space: nowrap !important;
        }}
        .landmark-popup {{
            min-width: 160px;
            direction: rtl;
            text-align: right;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}
        .landmark-popup h4 {{
            margin: 0 0 6px 0;
            color: #7C3AED;
            font-size: 13px;
            font-weight: 600;
        }}
        .landmark-popup p {{
            margin: 3px 0;
            font-size: 11px;
            color: #333;
        }}
        .landmark-popup .type-badge {{
            display: inline-block;
            padding: 1px 8px;
            border-radius: 10px;
            font-size: 10px;
            color: white;
            font-weight: 600;
        }}

        /* Street Layer Styles */
        .street-tooltip {{
            background: rgba(255, 255, 255, 0.95) !important;
            border: 1px solid #3B82F6 !important;
            border-radius: 4px !important;
            padding: 2px 8px !important;
            font-size: 11px !important;
            color: #1E40AF !important;
            direction: rtl !important;
            font-family: 'Segoe UI', Tahoma, sans-serif !important;
            white-space: nowrap !important;
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
        skip_fit_bounds: bool = False,
        tile_layer_url: str = None,
        boundaries_geojson: str = None,
        boundary_level: str = None,
        places_json: str = None,
        landmarks_json: str = None,
        streets_json: str = None,
        local_assets_url: str = '',
        max_selection: Optional[int] = None,
    ) -> str:
        """Get JavaScript code for map initialization."""
        import json
        from app.config import Config as _Cfg
        from services.tile_server_manager import get_tile_metadata

        effective_tile_url = tile_layer_url or tile_server_url

        # Auto-detect zoom levels from tile server / MBTiles
        tile_meta = get_tile_metadata()
        effective_min_zoom = min_zoom if min_zoom is not None else tile_meta.get('minzoom', MapConstants.MIN_ZOOM)
        effective_max_zoom = max_zoom if max_zoom != MapConstants.MAX_ZOOM else tile_meta.get('maxzoom', MapConstants.MAX_ZOOM)

        # Determine actual tile URL template — Docker TileServer GL returns its own URL in tiles[0]
        tile_template_from_meta = tile_meta.get('tile_template')
        if tile_template_from_meta:
            tile_layer_url_js = LeafletHTMLGenerator._safe_js_string(tile_template_from_meta)
            tile_status_label = "Docker (" + tile_template_from_meta.split('/')[2] + ")"
        else:
            from urllib.parse import urlparse as _urlparse
            import ipaddress as _ipaddress
            _parsed = _urlparse(effective_tile_url)
            _hostname = _parsed.hostname or ''
            _is_docker_server = _hostname in ('localhost', '127.0.0.1')
            if not _is_docker_server:
                try:
                    _is_docker_server = _ipaddress.ip_address(_hostname).is_private
                except ValueError:
                    pass
            if _is_docker_server:
                fallback_tile_url = effective_tile_url + "/tiles/{z}/{x}/{y}.png"
                tile_status_label = "Docker (" + (_hostname or tile_server_url.split(':')[-1]) + ")"
            else:
                fallback_tile_url = effective_tile_url + "/{z}/{x}/{y}.png"
                tile_status_label = _hostname or effective_tile_url
            tile_layer_url_js = LeafletHTMLGenerator._safe_js_string(fallback_tile_url)

        # GeoServer WMS (optional, from .env)
        geoserver_wms_url = ""
        geoserver_workspace = _Cfg.GEOSERVER_WORKSPACE
        if _Cfg.GEOSERVER_ENABLED and _Cfg.GEOSERVER_URL:
            geoserver_wms_url = f"{_Cfg.GEOSERVER_URL}/{_Cfg.GEOSERVER_WORKSPACE}/wms"

        status_colors = LeafletHTMLGenerator.STATUS_COLORS
        status_labels = LeafletHTMLGenerator.STATUS_LABELS_AR

        # Encode for safe embedding inside <script> tags. _safe_js_json escapes
        # the few sequences (e.g. </script>, <!--, -->) that an HTML parser
        # would otherwise treat as tag boundaries even inside JSON string
        # literals — defending against XSS via attacker-controlled feature
        # properties (building name, address, etc.) round-tripping from the API.
        status_colors_json = LeafletHTMLGenerator._safe_js_json(status_colors)
        status_labels_json = LeafletHTMLGenerator._safe_js_json(status_labels)

        empty_fc = '{"type":"FeatureCollection","features":[]}'
        buildings_json = LeafletHTMLGenerator._safe_js_json(buildings_geojson, fallback=empty_fc)

        if existing_polygons_geojson:
            existing_polygons_json = LeafletHTMLGenerator._safe_js_json(existing_polygons_geojson, fallback="")
            if not existing_polygons_json:
                logger.warning("Failed to parse existing polygons GeoJSON")
                existing_polygons_json = None
        else:
            existing_polygons_json = None

        initial_bounds_js = LeafletHTMLGenerator._safe_js_json(initial_bounds, fallback='null') if initial_bounds else 'null'

        # i18n labels — resolved at HTML generation time from current app language
        from services.translation_manager import tr as _tr
        _lbl_neighborhood = _tr('page.map.popup_neighborhood_label')
        _lbl_status       = _tr('page.map.popup_status_label')
        _lbl_units        = _tr('page.map.popup_units_label')
        _lbl_type         = _tr('page.map.popup_type_label')
        _lbl_select       = _tr('page.map.popup_select_building')
        _lbl_not_found    = _tr('mapping.not_specified')
        _lbl_assigned     = _tr('page.map.popup_previously_assigned')
        _lbl_locked       = _tr('page.map.popup_locked_building')
        _lbl_map_status   = _tr('page.map.status_title')
        _lbl_buildings    = _tr('page.map.status_buildings')
        _lbl_tile_server  = _tr('page.map.status_tile_server')

        # Build popup JS block - skip popups in multi-select mode (clicking toggles selection)
        if enable_multiselect:
            popup_js_block = '// Multi-select mode: no popups, clicking toggles selection'
        else:
            selection_btn_js = (
                'if (buildingIdForApi) { popup += "<button class=\\"select-building-btn\\" '
                f'onclick=\\"selectBuilding(&apos;" + buildingIdForApi + "&apos;)\\">'
                f'<span style=\\"font-size:16px\\">✓</span> {_lbl_select}</button>"; }}'
            ) if enable_selection else '// Selection disabled'

            popup_js_block = (
                "var popup = '<div class=\"building-popup\" dir=\"auto\">' +\n"
                "                    '<h4>' + buildingIdDisplay + ' ' +\n"
                "                    '<span class=\"geometry-badge\">' + geomType + '</span></h4>' +\n"
                f"                    '<p><span class=\"label\">{_lbl_neighborhood}</span> ' + (props.neighborhood || '{_lbl_not_found}') + '</p>' +\n"
                f"                    '<p><span class=\"label\">{_lbl_status}</span> ' +\n"
                "                    '<span class=\"status-badge ' + statusClass + '\">' + statusLabel + '</span></p>' +\n"
                f"                    '<p><span class=\"label\">{_lbl_units}</span> ' + (props.units || 0) + '</p>';\n"
                "\n"
                "                if (props.type) {\n"
                f"                    popup += '<p><span class=\"label\">{_lbl_type}</span> ' + props.type + '</p>';\n"
                "                }\n"
                "\n"
                "                if (props.is_assigned) {\n"
                f"                    popup += '<p><span style=\"background:#FEF3C7;color:#92400E;padding:2px 8px;border-radius:4px;font-size:12px;\">\\u2713 {_lbl_assigned}</span></p>';\n"
                "                }\n"
                "                if (props.is_locked) {\n"
                f"                    popup += '<p><span style=\"background:#F3F4F6;color:#6B7280;padding:2px 8px;border-radius:4px;font-size:12px;\">\\uD83D\\uDD12 {_lbl_locked}</span></p>';\n"
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
                "                        if(buildingsLayer) buildingsLayer.resetStyle(this);\n"
                "                    });\n"
                "                }"
            )

        _max_selection_js = 'null' if max_selection is None else str(int(max_selection))
        return f'''
    <script>
        // [PERF] First line of the main map-init script.
        if (typeof window._mp === 'function') window._mp('main_script_start');

        // [UNIFIED-DIALOG] Max selection count: null=unlimited, 1=single-select replace mode.
        window.maxSelection = {_max_selection_js};

        L.Icon.Default.imagePath = '{local_assets_url}/images/';

        // Initialize map. Leaflet 1.x vector canvas not used (no polygons drawn);
        // buildings render as DOM divIcons via pointToLayer.
        var map = L.map('map', {{
            maxZoom: {effective_max_zoom},
            minZoom: {effective_min_zoom},
            fadeAnimation: {'true' if MapConstants.MAP_FADE_ANIMATION else 'false'},
            zoomAnimation: {'true' if MapConstants.MAP_ZOOM_ANIMATION else 'false'},
            zoomAnimationThreshold: {MapConstants.MAP_ZOOM_ANIMATION_THRESHOLD},
            maxBounds: [[{MapConstants.MIN_LAT}, {MapConstants.MIN_LON}], [{MapConstants.MAX_LAT}, {MapConstants.MAX_LON}]],
            maxBoundsViscosity: 1.0
        }}).setView([{center_lat}, {center_lon}], {zoom});
        if (typeof window._mp === 'function') window._mp('map_created');

        var initialBounds = {initial_bounds_js};
        if (initialBounds) {{
            map.fitBounds(initialBounds, {{padding: [50, 50]}});
        }}

        // Add tile layer
        var tileLayer = L.tileLayer({tile_layer_url_js}, {{
            maxZoom: {effective_max_zoom},
            minZoom: {effective_min_zoom},
            attribution: 'Map data &copy; OpenStreetMap | UN-Habitat Syria',
            keepBuffer: {MapConstants.TILE_KEEP_BUFFER},
            updateWhenZooming: {'true' if MapConstants.TILE_UPDATE_WHEN_ZOOMING else 'false'},
            updateWhenIdle: {'true' if MapConstants.TILE_UPDATE_WHEN_IDLE else 'false'},
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
        }});
        tileLayer.addTo(map);
        if (typeof window._mp === 'function') window._mp('tile_layer_added');
        tileLayer.on('load', function() {{ if (typeof window._mp === 'function') window._mp('tile_layer_loaded'); }});
        // GeoServer WMS overlay (optional, configured via .env)
        var geoserverWmsUrl = '{geoserver_wms_url}';
        if (geoserverWmsUrl && geoserverWmsUrl !== '' && geoserverWmsUrl !== 'None') {{
            var gsBuildingsLayer = L.tileLayer.wms(geoserverWmsUrl, {{
                layers: '{geoserver_workspace}:buildings',
                format: 'image/png',
                transparent: true,
                version: '1.1.1',
                attribution: 'GeoServer - UN-Habitat'
            }});
            var gsOverlays = {{"Buildings (GeoServer)": gsBuildingsLayer}};
            L.control.layers(null, gsOverlays).addTo(map);
        }}

        // Loading overlay: keep visible until ALL viewport tiles are loaded so the user
        // never sees dark/empty tile areas. 'load' fires when every tile in the current
        // viewport has loaded (or returned an error tile), so the map is fully drawn.
        (function() {{
            var overlay = document.getElementById('map-loading-overlay');
            if (!overlay) return;
            var removed = false;

            function removeOverlay() {{
                if (removed) return;
                removed = true;
                overlay.classList.add('fade-out');
                setTimeout(function() {{ overlay.style.display = 'none'; }}, 450);
            }}

            // Remove only when ALL viewport tiles are painted.
            tileLayer.on('load', removeOverlay);
            // Safety fallback: remove after 8 seconds regardless (slow/offline tile server).
            setTimeout(removeOverlay, 8000);
        }})();

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

        // [SIMPLIFY] Normalize every feature's geometry to a Point (centroid of polygon rings).
        // Buildings are always rendered as markers — never as polygons — so L.geoJSON's
        // pointToLayer callback fires for ALL features, regardless of what the API returned.
        (function _toPoints() {{
            if (!buildingsData || !buildingsData.features) return;
            function _centroidOfRing(ring) {{
                if (!ring || ring.length === 0) return null;
                var sumLng = 0, sumLat = 0, n = 0;
                // Skip the last point if it's a dup of the first (GeoJSON closed ring).
                var lim = (ring.length > 1 && ring[0][0] === ring[ring.length-1][0] && ring[0][1] === ring[ring.length-1][1])
                          ? ring.length - 1 : ring.length;
                for (var i = 0; i < lim; i++) {{
                    sumLng += ring[i][0];
                    sumLat += ring[i][1];
                    n++;
                }}
                return n > 0 ? [sumLng / n, sumLat / n] : null;
            }}
            for (var i = 0; i < buildingsData.features.length; i++) {{
                var f = buildingsData.features[i];
                if (!f || !f.geometry) continue;
                var g = f.geometry;
                if (g.type === 'Point') continue;
                var pt = null;
                if (g.type === 'Polygon' && g.coordinates && g.coordinates[0]) {{
                    pt = _centroidOfRing(g.coordinates[0]);
                }} else if (g.type === 'MultiPolygon' && g.coordinates && g.coordinates[0] && g.coordinates[0][0]) {{
                    pt = _centroidOfRing(g.coordinates[0][0]);
                }}
                if (pt) {{
                    f.geometry = {{ type: 'Point', coordinates: pt }};
                }}
            }}
        }})();

        // Summary counts
        var _ptCount = buildingsData.features.length;

        // Marker Clustering Configuration
        var markers;
        if (typeof L.markerClusterGroup === 'function') {{
            markers = L.markerClusterGroup({{
                maxClusterRadius: function(zoom) {{
                    if (zoom <= 15) return 80;
                    if (zoom <= 16) return 50;
                    return 30;
                }},
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false,
                zoomToBoundsOnClick: true,
                disableClusteringAtZoom: {MapConstants.DISABLE_CLUSTERING_AT_ZOOM},
                spiderfyDistanceMultiplier: 1.5,
                chunkedLoading: true,
                chunkInterval: {MapConstants.CHUNK_INTERVAL},
                chunkDelay: {MapConstants.CHUNK_DELAY},
                removeOutsideVisibleBounds: true,
                animate: true,
                animateAddingMarkers: false
            }});
        }} else {{
            console.warn('MarkerCluster not available, using featureGroup fallback');
            markers = L.featureGroup();
        }}

        // Points layer for all buildings
        var pointsLayer = L.featureGroup();

        // Batch collection for addLayers (faster than per-marker addLayer)
        var _initialMarkerList = [];

        var buildingsLayer = L.geoJSON(buildingsData, {{
            pointToLayer: function(feature, latlng) {{
                var status = getStatusKey(feature.properties.status || 1);
                var color = statusColors[status] || '#0072BC';
                // [VISUAL] Pre-assigned buildings are distinguished by color only (amber).
                // They remain fully selectable — no special tooltip, no click block.
                if (feature.properties.is_assigned === true) {{
                    color = '#F59E0B';
                }}
                var innerSvg = '<circle cx="12" cy="12" r="4" fill="#fff"/>';
                var pinIcon = L.divIcon({{
                    className: 'building-pin-icon',
                    html: '<div style="position:relative;width:24px;height:36px;">' +
                          '<svg width="24" height="36" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                          '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                          'fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
                          innerSvg + '</svg></div>',
                    iconSize: [24, 36],
                    iconAnchor: [12, 36],
                    popupAnchor: [0, -36]
                }});
                var _marker = L.marker(latlng, {{icon: pinIcon}});
                // [UNIFIED-DIALOG] Show building ID on hover
                var _idLabel = feature.properties.building_id_display || feature.properties.building_id;
                if (_idLabel) {{
                    _marker.bindTooltip(String(_idLabel), {{
                        permanent: false,
                        direction: 'top',
                        offset: [0, -36],
                        className: 'building-id-tooltip'
                    }});
                }}
                return _marker;
            }},

            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var status = props.status || 'intact';
                var statusLabel = statusLabels[status] || status;
                var statusClass = 'status-' + status;
                var geomType = props.geometry_type || 'Point';
                var actualGeomType = feature.geometry.type;

                var buildingIdDisplay = props.building_id_display || props.building_id || 'مبنى';
                var buildingIdForApi = props.building_id;

                {popup_js_block}

                pointsLayer.addLayer(layer);
                _initialMarkerList.push(layer);

                {hover_js_block}
            }}
        }});

        markers.addLayers(_initialMarkerList);
        map.addLayer(markers);

        // Add existing polygons layer (displayed in blue)
        {LeafletHTMLGenerator._get_existing_polygons_js(existing_polygons_geojson) if existing_polygons_geojson else '// No existing polygons'}

        // Neighborhoods overlay layer (zoom-based visibility)
        {LeafletHTMLGenerator._get_neighborhoods_layer_js(neighborhoods_geojson, selected_neighborhood_code, enable_drawing) if neighborhoods_geojson else '// No neighborhoods overlay'}

        // Administrative boundary layer (polygons from Shapefiles)
        {LeafletHTMLGenerator._get_boundaries_layer_js(boundaries_geojson, boundary_level) if boundaries_geojson else '// No boundary layer'}

        // Streets layer (line features — below landmarks)
        {LeafletHTMLGenerator._get_streets_layer_js(streets_json) if streets_json else '// No streets layer'}

        // Landmarks layer (point features — above streets)
        {LeafletHTMLGenerator._get_landmarks_layer_js(landmarks_json) if landmarks_json else '// No landmarks layer'}

        // Populated places layer (city/town labels at low zoom)
        {LeafletHTMLGenerator._get_places_layer_js(places_json) if places_json else '// No places layer'}

        // Fit to buildings if any (skip when initial_bounds or skip_fit_bounds set)
        var skipFitBounds = {'true' if skip_fit_bounds else 'false'};
        if (!skipFitBounds && !initialBounds && buildingsData.features && buildingsData.features.length > 0) {{
            try {{
                var bounds = buildingsLayer.getBounds();
                map.fitBounds(bounds, {{ padding: [50, 50] }});
            }} catch(e) {{
                console.log('Using default center (fitBounds failed)');
            }}
        }}

        {LeafletHTMLGenerator._get_status_legend_js() if (show_legend and not enable_multiselect) else ''}

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

                    if (layer.feature.geometry.type === 'Point') {{
                        // Temporarily replace pin with larger blue icon
                        var _origIcon = layer.getIcon ? layer.getIcon() : null;
                        layer.setIcon(L.divIcon({{
                            className: 'building-pin-icon',
                            html: '<div style="position:relative;width:36px;height:52px;' +
                                  'filter:drop-shadow(0 4px 8px rgba(33,150,243,0.5));">' +
                                  '<svg width="36" height="52" viewBox="0 0 32 48" xmlns="http://www.w3.org/2000/svg">' +
                                  '<path d="M16 0C9.4 0 4 5.4 4 12c0 10 12 32 12 32s12-22 12-32c0-6.6-5.4-12-12-12z" ' +
                                  'fill="#1976D2" stroke="#64B5F6" stroke-width="3"/>' +
                                  '<circle cx="16" cy="12" r="6" fill="#64B5F6"/>' +
                                  '</svg></div>',
                            iconSize: [36, 52],
                            iconAnchor: [18, 52],
                            popupAnchor: [0, -52]
                        }}));
                        if (_origIcon) {{
                            setTimeout(function() {{ layer.setIcon(_origIcon); }}, 2000);
                        }}
                    }} else {{
                        // Highlight polygon temporarily
                        layer.setStyle({{
                            fillOpacity: 1.0,
                            weight: 4,
                            color: '#1976D2'
                        }});

                        setTimeout(function() {{
                            if(buildingsLayer) buildingsLayer.resetStyle(layer);
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

        window.updateBuildingCount = function(count) {{
            var el = document.querySelector('.map-status-overlay');
            if (el) {{
                var parts = el.innerHTML.split('<br>');
                parts[1] = '{_lbl_buildings}: ' + count;
                el.innerHTML = parts.join('<br>');
            }}
        }};

        // Unified zoom handler for all visibility layers
        map.on('zoomend', function() {{
            if(typeof updateNeighborhoodVisibility !== 'undefined') updateNeighborhoodVisibility();
            if(typeof updateBoundaryVisibility !== 'undefined') updateBoundaryVisibility();
            if(typeof updatePlacesVisibility !== 'undefined') updatePlacesVisibility();
            if(typeof updateLandmarksVisibility !== 'undefined') updateLandmarksVisibility();
            if(typeof updateStreetsVisibility !== 'undefined') updateStreetsVisibility();
        }});

        if (typeof window._mp === 'function') window._mp('main_script_end');
    </script>
'''

    @staticmethod
    def _get_status_legend_js() -> str:
        """Get JavaScript for building status legend control."""
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
    def _get_neighborhoods_layer_js(neighborhoods_geojson: str, selected_neighborhood_code: str = None, enable_drawing: bool = False) -> str:
        """
        Get JavaScript for neighborhood center pins with zoom-based visibility.

        - Zoom 15-16: Neighborhood pins with Arabic name labels, buildings hidden
        - Zoom >= 17: Pins hidden, buildings visible (polygons + pin markers)
        - NO polygon borders — pins only

        Tile range: 15-20 (below 15 = gray, no tiles)
        """
        neighborhoods_json = LeafletHTMLGenerator._safe_js_json(neighborhoods_geojson, fallback="")
        if not neighborhoods_json:
            logger.warning("Failed to parse neighborhoods GeoJSON")
            return '// Invalid neighborhoods GeoJSON'

        selected_code = selected_neighborhood_code or ''

        if enable_drawing:
            zoom_handler_js = "// Drawing mode: pins always visible at all zoom levels"
        else:
            zoom_handler_js = "updateNeighborhoodVisibility();"

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
                    offset: [0, -12]
                }});

                neighborhoodPins.addLayer(pin);
            }});

            neighborhoodPins.addTo(map);

            // Zoom-based visibility:
            // zoom 15-16: neighborhood pins visible, initial buildings hidden
            // zoom >= 17: pins hidden, buildings visible
            // When viewport loading is active, DON'T re-add initial markers
            // (viewport loading handles building display at zoom 17+ via its own layers)
            function updateNeighborhoodVisibility() {{
                var zoom = map.getZoom();
                var hasViewportLoading = (typeof viewportLoadingEnabled !== 'undefined' && viewportLoadingEnabled);

                if (zoom >= 17) {{
                    // Zoomed into neighborhood — hide pins
                    if (map.hasLayer(neighborhoodPins)) map.removeLayer(neighborhoodPins);
                    // Only add initial buildings if viewport loading is NOT active
                    if (!hasViewportLoading) {{
                        if (typeof markers !== 'undefined' && !map.hasLayer(markers)) map.addLayer(markers);
                    }}
                }} else {{
                    // City overview (zoom 15-16) — show pins, hide initial buildings
                    if (!map.hasLayer(neighborhoodPins)) map.addLayer(neighborhoodPins);
                    if (typeof markers !== 'undefined' && map.hasLayer(markers)) map.removeLayer(markers);
                }}
            }}

            {zoom_handler_js}

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
        empty_fc = '{"type":"FeatureCollection","features":[]}'
        existing_polygons_json = LeafletHTMLGenerator._safe_js_json(existing_polygons_geojson, fallback=empty_fc)
        if existing_polygons_json == empty_fc and existing_polygons_geojson:
            logger.warning("Failed to parse existing polygons GeoJSON")

        return f'''
        // Existing polygons layer (light transparent blue - shows current polygon during edit)
        var existingPolygonsData = {existing_polygons_json};
        var existingPolygonsLayer = null;

        if (existingPolygonsData && existingPolygonsData.features && existingPolygonsData.features.length > 0) {{
            existingPolygonsLayer = L.geoJSON(existingPolygonsData, {{
                style: function(feature) {{
                    return {{
                        color: '#42A5F5',
                        weight: 3,
                        fillColor: '#90CAF9',
                        fillOpacity: 0.25
                    }};
                }},
                onEachFeature: function(feature, layer) {{
                    // Tooltip label
                    layer.bindTooltip('المضلع الحالي - ارسم مضلعاً جديداً للاستبدال', {{
                        permanent: false,
                        direction: 'top',
                        className: 'existing-polygon-tooltip'
                    }});

                    // Hover effects
                    layer.on('mouseover', function(e) {{
                        this.setStyle({{
                            fillOpacity: 0.4,
                            weight: 3
                        }});
                    }});

                    layer.on('mouseout', function(e) {{
                        this.setStyle({{
                            fillOpacity: 0.25,
                            weight: 2
                        }});
                    }});
                }}
            }}).addTo(map);

        }}
'''

    @staticmethod
    def _get_boundaries_layer_js(boundaries_geojson: str, level: str = None) -> str:
        """
        Generate JavaScript for administrative boundary polygon layer.

        Features:
        - Zoom-based visibility (hidden below zoom 7 for governorates, 10 for others)
        - Subtle fill with visible border
        - Arabic name tooltip on hover
        - Added to layer control overlay
        """
        boundaries_json = LeafletHTMLGenerator._safe_js_json(boundaries_geojson, fallback="")
        if not boundaries_json:
            return '// Invalid boundaries GeoJSON'

        # Zoom threshold: governorates visible earlier, sub-levels only at higher zoom
        zoom_threshold = 7 if level == 'governorates' else 10

        # Arabic label field depends on the level
        # Governorates: NAME_AR, PCODE
        # Subdistricts: NAME_AR, ADM3_AR (if present)
        # Neighbourhoods: NAME_AR, ADM4_AR (if present)
        layer_label_ar = {
            'governorates':  'حدود المحافظات',
            'districts':     'حدود المناطق',
            'subdistricts':  'حدود النواحي',
            'neighbourhoods':'حدود الأحياء',
            'country':       'حدود الدولة',
        }.get(level or '', 'الحدود الإدارية')

        return f'''
        // Administrative boundary layer — level: {level or 'unknown'}
        var boundaryData = {boundaries_json};
        var boundaryZoomThreshold = {zoom_threshold};

        var boundaryStyle = {{
            color: '#3388ff',
            weight: 1.5,
            opacity: 0.7,
            fillColor: '#3388ff',
            fillOpacity: 0.05
        }};

        var boundaryLayer = L.geoJSON(boundaryData, {{
            style: boundaryStyle,
            interactive: false,
            onEachFeature: function(feature, layer) {{
                var p = feature.properties;
                var nameAr = p.NAME_AR || p.ADM3_AR || p.ADM4_AR || p.name_ar || '';
                var pcode = p.PCODE || p.ADM1_PCODE || p.ADM3_PCODE || '';
                if (nameAr) {{
                    layer.bindTooltip(nameAr, {{
                        sticky: true,
                        direction: 'auto',
                        className: 'boundary-tooltip'
                    }});
                }}
                layer.on('mouseover', function() {{
                    this.setStyle({{ weight: 2.5, fillOpacity: 0.15 }});
                }});
                layer.on('mouseout', function() {{
                    this.setStyle(boundaryStyle);
                }});
            }}
        }});

        function updateBoundaryVisibility() {{
            if (map.getZoom() >= boundaryZoomThreshold) {{
                if (!map.hasLayer(boundaryLayer)) {{
                    boundaryLayer.addTo(map);
                }}
            }} else {{
                if (map.hasLayer(boundaryLayer)) {{
                    map.removeLayer(boundaryLayer);
                }}
            }}
        }}

        updateBoundaryVisibility();

        // Register in overlayMaps for layer control (if it exists)
        if (typeof overlayMaps !== 'undefined') {{
            overlayMaps['{layer_label_ar}'] = boundaryLayer;
        }}

'''

    @staticmethod
    def _get_places_layer_js(places_json: str) -> str:
        """
        Generate JavaScript for populated places layer (city/town name labels).

        Shows circle markers with Arabic name tooltips at zoom 8-12.
        Capitals use a larger, orange marker. Other places use a small grey marker.
        Layer auto-hides when zooming into building level (zoom > 12).
        """
        places_embedded = LeafletHTMLGenerator._safe_js_json(places_json, fallback="")
        if not places_embedded:
            return '// Invalid places JSON'

        return f'''
        // Populated places layer — visible at zoom 8-12
        var placesData = {places_embedded};
        var placesLayer = L.featureGroup();

        if (placesData && placesData.length > 0) {{
            placesData.forEach(function(place) {{
                if (!place.lat || !place.lng) return;
                var isCapital = place.is_capital === true;
                var marker = L.circleMarker([place.lat, place.lng], {{
                    radius:      isCapital ? 5 : 3,
                    color:       isCapital ? '#E65100' : '#757575',
                    fillColor:   isCapital ? '#FF6B35' : '#BDBDBD',
                    fillOpacity: 0.85,
                    weight:      1
                }});
                var label = place.name_ar || place.name_en || '';
                if (label) {{
                    marker.bindTooltip(label, {{
                        permanent: false,
                        sticky: true,
                        direction: 'top',
                        className: 'place-label-tooltip'
                    }});
                }}
                placesLayer.addLayer(marker);
            }});
        }}

        function updatePlacesVisibility() {{
            var zoom = map.getZoom();
            if (zoom >= 8 && zoom <= 12) {{
                if (!map.hasLayer(placesLayer)) placesLayer.addTo(map);
            }} else {{
                if (map.hasLayer(placesLayer)) map.removeLayer(placesLayer);
            }}
        }}

        updatePlacesVisibility();

'''

    @staticmethod
    def _get_landmarks_layer_js(landmarks_json: str) -> str:
        """
        Generate JavaScript for landmarks point layer.

        Shows SVG markers per landmark type (from server) with tooltips and popups.
        Falls back to generic colored pin if no server SVG available.
        Visible at zoom >= 13.
        """
        landmarks_embedded = LeafletHTMLGenerator._safe_js_json(landmarks_json, fallback="")
        if not landmarks_embedded:
            return '// Invalid landmarks JSON'

        # Get server SVG icons if available
        try:
            from services.landmark_icon_service import get_svg_icons_json
            svg_icons_json = LeafletHTMLGenerator._safe_js_json(get_svg_icons_json(), fallback='{}')
        except Exception:
            svg_icons_json = '{}'

        return f'''
        // Landmarks layer — visible at zoom >= 13
        var landmarksData = {landmarks_embedded};
        var landmarksLayer = L.featureGroup();

        var landmarkTypeSvgs = {svg_icons_json};

        var landmarkTypeColors = {{
            'Police station': '#3B82F6', 'PoliceStation': '#3B82F6',
            'Mosque': '#10B981',
            'Square': '#8B5CF6', 'PublicBuilding': '#8B5CF6',
            'Shop': '#F59E0B',
            'School': '#EF4444',
            'Clinic': '#EC4899',
            'Water Tank': '#06B6D4', 'WaterTank': '#06B6D4',
            'Fuel Station': '#F97316', 'FuelStation': '#F97316',
            'Hospital': '#DC2626',
            'Park': '#16A34A'
        }};

        var landmarkTypeLabelsAr = {{
            'Police station': 'مركز شرطة', 'PoliceStation': 'مركز شرطة',
            'Mosque': 'مسجد',
            'Square': 'ساحة', 'PublicBuilding': 'ساحة',
            'Shop': 'محل تجاري',
            'School': 'مدرسة',
            'Clinic': 'عيادة',
            'Water Tank': 'خزان مياه', 'WaterTank': 'خزان مياه',
            'Fuel Station': 'محطة وقود', 'FuelStation': 'محطة وقود',
            'Hospital': 'مستشفى',
            'Park': 'حديقة'
        }};

        function createLandmarkIcon(typeName, color) {{
            var svgHtml = landmarkTypeSvgs[typeName];
            if (svgHtml) {{
                return L.divIcon({{
                    className: 'landmark-pin-icon',
                    html: '<div style="position:relative;width:32px;height:42px;">' + svgHtml + '</div>',
                    iconSize: [32, 42],
                    iconAnchor: [16, 42],
                    popupAnchor: [0, -42],
                    tooltipAnchor: [0, -36]
                }});
            }}
            return L.divIcon({{
                className: 'landmark-pin-icon',
                html: '<div style="position:relative;width:28px;height:36px;">' +
                    '<svg viewBox="0 0 28 36" width="28" height="36">' +
                    '<path d="M14 0C6.3 0 0 6.3 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.3 21.7 0 14 0z" fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
                    '<circle cx="14" cy="13" r="5" fill="#fff"/>' +
                    '</svg></div>',
                iconSize: [28, 36],
                iconAnchor: [14, 36],
                popupAnchor: [0, -36],
                tooltipAnchor: [0, -30]
            }});
        }}

        function addLandmarkMarker(lm) {{
            if (!lm.latitude || !lm.longitude) return;
            var typeName = lm.typeName || '';
            var color = landmarkTypeColors[typeName] || '#6B7280';
            var typeAr = landmarkTypeLabelsAr[typeName] || typeName;

            var icon = createLandmarkIcon(typeName, color);
            var marker = L.marker([lm.latitude, lm.longitude], {{ icon: icon }});

            var label = lm.name || '';
            if (label) {{
                marker.bindTooltip(label, {{
                    permanent: false,
                    direction: 'top',
                    className: 'landmark-tooltip',
                    offset: [0, -5]
                }});
            }}

            var popupHtml = '<div class="landmark-popup">' +
                '<h4>' + (lm.name || '') + '</h4>' +
                '<p><span class="type-badge" style="background:' + color + ';color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">' + typeAr + '</span></p>' +
                '<p style="color:#666;font-size:10px;">ID: ' + (lm.identifier || '') + '</p>' +
                '</div>';
            marker.bindPopup(popupHtml);

            marker.landmarkData = lm;
            landmarksLayer.addLayer(marker);
        }}

        if (landmarksData && landmarksData.length > 0) {{
            landmarksData.forEach(addLandmarkMarker);
        }}

        function updateLandmarksVisibility() {{
            var zoom = map.getZoom();
            if (zoom >= 13) {{
                if (!map.hasLayer(landmarksLayer)) landmarksLayer.addTo(map);
            }} else {{
                if (map.hasLayer(landmarksLayer)) map.removeLayer(landmarksLayer);
            }}
        }}

        updateLandmarksVisibility();

        if (typeof overlayMaps !== 'undefined') {{
            overlayMaps['معالم'] = landmarksLayer;
        }}

        function panToLandmark(landmarkId) {{
            landmarksLayer.eachLayer(function(layer) {{
                if (layer.landmarkData && layer.landmarkData.id === landmarkId) {{
                    map.setView(layer.getLatLng(), 16);
                    layer.openPopup();
                }}
            }});
        }}
        window.panToLandmark = panToLandmark;

        function updateLandmarksOnMap(newData) {{
            landmarksLayer.clearLayers();
            if (!newData || !newData.length) return;
            newData.forEach(addLandmarkMarker);
        }}
        window.updateLandmarksOnMap = updateLandmarksOnMap;
'''

    @staticmethod
    def _get_streets_layer_js(streets_json: str) -> str:
        """
        Generate JavaScript for streets line layer.

        Parses WKT LINESTRING geometry and renders as polylines.
        Visible at zoom >= 13.
        """
        streets_embedded = LeafletHTMLGenerator._safe_js_json(streets_json, fallback="")
        if not streets_embedded:
            return '// Invalid streets JSON'

        return f'''
        // Streets layer — visible at zoom >= 13
        var streetsData = {streets_embedded};
        var streetsLayer = L.featureGroup();

        function wktLineToLatLngs(wkt) {{
            if (!wkt) return null;
            var match = wkt.match(/LINESTRING\\s*\\((.+)\\)/i);
            if (!match) return null;
            var coords = match[1].split(',');
            var latLngs = [];
            for (var i = 0; i < coords.length; i++) {{
                var parts = coords[i].trim().split(/\\s+/);
                if (parts.length >= 2) {{
                    latLngs.push([parseFloat(parts[1]), parseFloat(parts[0])]);
                }}
            }}
            return latLngs.length >= 2 ? latLngs : null;
        }}

        if (streetsData && streetsData.length > 0) {{
            streetsData.forEach(function(street) {{
                var latLngs = wktLineToLatLngs(street.geometryWkt);
                if (!latLngs) return;

                var polyline = L.polyline(latLngs, {{
                    color: '#3B82F6',
                    weight: 3,
                    opacity: 0.7
                }});

                var label = street.name || '';
                if (label) {{
                    polyline.bindTooltip(label, {{
                        sticky: true,
                        direction: 'auto',
                        className: 'street-tooltip'
                    }});
                }}

                polyline.on('mouseover', function() {{
                    this.setStyle({{ weight: 5, opacity: 1.0 }});
                }});
                polyline.on('mouseout', function() {{
                    this.setStyle({{ weight: 3, opacity: 0.7 }});
                }});

                streetsLayer.addLayer(polyline);
            }});
        }}

        function updateStreetsVisibility() {{
            var zoom = map.getZoom();
            if (zoom >= 13) {{
                if (!map.hasLayer(streetsLayer)) streetsLayer.addTo(map);
            }} else {{
                if (map.hasLayer(streetsLayer)) map.removeLayer(streetsLayer);
            }}
        }}

        updateStreetsVisibility();

        if (typeof overlayMaps !== 'undefined') {{
            overlayMaps['شوارع'] = streetsLayer;
        }}

        // Dynamic update from Python viewport change
        function updateStreetsOnMap(newData) {{
            streetsLayer.clearLayers();
            if (!newData || !newData.length) return;
            newData.forEach(function(street) {{
                var latLngs = wktLineToLatLngs(street.geometryWkt);
                if (!latLngs) return;
                var polyline = L.polyline(latLngs, {{ color: '#3B82F6', weight: 3, opacity: 0.7 }});
                var label = street.name || '';
                if (label) {{
                    polyline.bindTooltip(label, {{ sticky: true, direction: 'auto', className: 'street-tooltip' }});
                }}
                polyline.on('mouseover', function() {{ this.setStyle({{ weight: 5, opacity: 1.0 }}); }});
                polyline.on('mouseout', function() {{ this.setStyle({{ weight: 3, opacity: 0.7 }}); }});
                streetsLayer.addLayer(polyline);
            }});
        }}
        window.updateStreetsOnMap = updateStreetsOnMap;
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

        // Wait for qt.webChannelTransport to be ready (prevents timing issues)
        function initializeQWebChannel() {{
            initAttempts++;

            // Check for max attempts
            if (initAttempts > maxInitAttempts) {{
                console.error('QWebChannel initialization failed after ' + (maxInitAttempts * 50) + 'ms');
                console.error('   typeof QWebChannel:', typeof QWebChannel);
                console.error('   typeof qt:', typeof qt);
                console.error('   qt.webChannelTransport:', typeof qt !== 'undefined' ? qt.webChannelTransport : 'N/A');
                return;
            }}

            if (typeof QWebChannel === 'undefined') {{
                setTimeout(initializeQWebChannel, 50);
                return;
            }}

            if (typeof qt === 'undefined' || !qt.webChannelTransport) {{
                setTimeout(initializeQWebChannel, 50);
                return;
            }}

            try {{
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    bridge = channel.objects.buildingBridge || channel.objects.bridge;
                    if (!bridge) {{
                        console.error('Bridge object not found in channel!');
                        console.error('   Available objects:', Object.keys(channel.objects));
                        return;
                    }}

                    window.bridge = bridge;  // Make bridge globally accessible
                    bridgeReady = true;
                    window.bridgeReady = true;  // Make bridgeReady globally accessible

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
                console.error('Failed to initialize QWebChannel:', error);
                console.error('   Error details:', error.message, error.stack);
            }}
        }}

        // qwebchannel.js is inlined — start bridge init immediately
        initializeQWebChannel();

        // Function to select building (called from popup button)
        // Wait for bridge or retry with timeout
        function selectBuilding(buildingId) {{
            // Check if bridge is ready
            if (bridgeReady && bridge && (bridge.selectBuilding || bridge.buildingSelected)) {{
                // Bridge ready - select immediately
                if (bridge.selectBuilding) {{
                    bridge.selectBuilding(buildingId);
                }} else {{
                    bridge.buildingSelected(buildingId);
                }}
                map.closePopup();
            }} else if (!bridgeReady) {{
                // Bridge not ready yet - wait 500ms and retry
                console.warn('Bridge not ready, waiting 500ms...');
                setTimeout(function() {{
                    if (bridgeReady && bridge && (bridge.selectBuilding || bridge.buildingSelected)) {{
                        if (bridge.selectBuilding) {{
                            bridge.selectBuilding(buildingId);
                        }} else {{
                            bridge.buildingSelected(buildingId);
                        }}
                        map.closePopup();
                    }} else {{
                        console.error('Bridge still not ready after 500ms');
                        // Don't show alert - just log error (user can try again)
                    }}
                }}, 500);
            }} else {{
                console.error('Bridge initialized but methods not found');
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
    def _get_assignment_legend_js() -> str:
        """Get JavaScript for the color legend control on the assignment map."""
        return """
        // Color legend for field assignment map
        var legend = L.control({position: 'bottomright'});
        legend.onAdd = function(map) {
            var div = L.DomUtil.create('div', 'map-legend');
            div.style.cssText = 'background:white;padding:10px 14px;border-radius:10px;' +
                'box-shadow:0 2px 10px rgba(0,0,0,0.15);font-size:12px;direction:rtl;line-height:2;' +
                'border:1px solid rgba(0,0,0,0.08);';
            var dot = 'display:inline-block;width:12px;height:12px;border-radius:50%;margin-left:6px;vertical-align:middle;';
            div.innerHTML =
                '<div style="font-weight:bold;margin-bottom:2px;font-size:13px;">\\u062f\\u0644\\u064a\\u0644 \\u0627\\u0644\\u0623\\u0644\\u0648\\u0627\\u0646</div>' +
                '<div><span style="' + dot + 'background:#28a745;"></span> \\u0633\\u0644\\u064a\\u0645</div>' +
                '<div><span style="' + dot + 'background:#ffc107;"></span> \\u0645\\u062a\\u0636\\u0631\\u0631 \\u062c\\u0632\\u0626\\u064a\\u0627\\u064b</div>' +
                '<div><span style="' + dot + 'background:#dc3545;"></span> \\u0645\\u062a\\u0636\\u0631\\u0631 / \\u0645\\u062f\\u0645\\u0631</div>' +
                '<div style="border-top:1px solid #eee;margin:4px 0;"></div>' +
                '<div><span style="' + dot + 'background:#F59E0B;"></span> \\u0645\\u0639\\u064a\\u0651\\u0646 \\u0645\\u0633\\u0628\\u0642\\u0627\\u064b</div>' +
                '<div><span style="' + dot + 'background:#9CA3AF;"></span> \\u0645\\u0642\\u0641\\u0644</div>' +
                '<div style="border-top:1px solid #eee;margin:4px 0;"></div>' +
                '<div><span style="' + dot + 'background:#1976D2;border:2px solid #64B5F6;width:10px;height:10px;"></span> \\u0645\\u062d\\u062f\\u062f \\u062d\\u0627\\u0644\\u064a\\u0627\\u064b</div>';
            return div;
        };
        legend.addTo(map);
        """

    @staticmethod
    def _get_viewport_loading_js() -> str:
        """
        Get JavaScript for viewport-based loading.

        Handles viewport-based loading for large building datasets:
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
