# -*- coding: utf-8 -*-
"""Building Map Dialog V2 - dialog for building selection via interactive map."""

import json
from typing import Optional, List
from ui.error_handler import ErrorHandler
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

from repositories.database import Database
from controllers.building_controller import BuildingController, BuildingFilter
from models.building import Building
from ui.components.base_map_dialog import BaseMapDialog
from services.leaflet_html_generator import generate_leaflet_html
from services.geojson_converter import GeoJSONConverter
from utils.logger import get_logger
from services.translation_manager import tr

logger = get_logger(__name__)


class _BuildingsWorker(QThread):
    """Background worker for loading buildings data."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, auth_token, selected_building_id, is_view_only,
                 fallback_building, center_lat, center_lon, data_provider=None):
        super().__init__()
        self._auth_token = auth_token
        self._selected_building_id = selected_building_id
        self._is_view_only = is_view_only
        self._fallback_building = fallback_building
        self._center_lat = center_lat
        self._center_lon = center_lon
        self._data_provider = data_provider

    def run(self):
        try:
            result = {}
            from services.map_service_api import MapServiceAPI

            map_service = MapServiceAPI(data_provider=self._data_provider)
            if self._auth_token:
                map_service.set_auth_token(self._auth_token)

            buildings = []
            if self._is_view_only and self._selected_building_id:
                result['buildings_geojson'] = '{"type": "FeatureCollection", "features": []}'
                building = map_service.get_building_with_polygon(self._selected_building_id)
                result['view_buildings'] = [building] if building else []
                if not result['view_buildings'] and self._fallback_building:
                    result['view_buildings'] = [self._fallback_building]
            else:
                try:
                    delta_lat, delta_lng = 0.015, 0.02
                    buildings = map_service.get_buildings_in_bbox(
                        north_east_lat=self._center_lat + delta_lat,
                        north_east_lng=self._center_lon + delta_lng,
                        south_west_lat=self._center_lat - delta_lat,
                        south_west_lng=self._center_lon - delta_lng,
                        page_size=200
                    )
                except Exception as e:
                    logger.warning(f"API map loading failed: {e}")
                result['buildings_list'] = buildings
                result['buildings_geojson'] = GeoJSONConverter.buildings_to_geojson(
                    buildings, force_points=True
                )

            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Buildings worker error: {e}", exc_info=True)
            self.error.emit(str(e))


class _LayersWorker(QThread):
    """Background worker for loading neighborhoods, boundaries, landmarks and streets."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, auth_token):
        super().__init__()
        self._auth_token = auth_token

    def run(self):
        try:
            from concurrent.futures import ThreadPoolExecutor

            result = {}

            def _load_neighborhoods():
                nh_geojson = None
                bd_geojson = None
                try:
                    from services.api_client import get_api_client
                    api = get_api_client()
                    if api and self._auth_token:
                        from app.config import Config
                        neighborhoods = api.get_neighborhoods_by_bounds(
                            sw_lat=Config.MAP_BOUNDS_MIN_LAT,
                            sw_lng=Config.MAP_BOUNDS_MIN_LNG,
                            ne_lat=Config.MAP_BOUNDS_MAX_LAT,
                            ne_lng=Config.MAP_BOUNDS_MAX_LNG,
                        )
                        if neighborhoods:
                            import re
                            features = []
                            for n in neighborhoods:
                                wkt = n.get('boundaries') or n.get('boundary') or n.get('boundaryWkt') or ''
                                coords = re.findall(r'([-\d.]+)\s+([-\d.]+)', wkt)
                                if coords:
                                    lngs = [float(c[0]) for c in coords]
                                    lats = [float(c[1]) for c in coords]
                                    center = (sum(lats)/len(lats), sum(lngs)/len(lngs))
                                    features.append({
                                        "type": "Feature",
                                        "properties": {
                                            "code": n.get('neighborhoodCode') or n.get('code', ''),
                                            "center_lat": center[0], "center_lng": center[1],
                                            "name_ar": n.get('nameArabic') or n.get('name_ar', '')
                                        },
                                        "geometry": None
                                    })
                            nh_geojson = json.dumps(
                                {"type": "FeatureCollection", "features": features}
                            )
                except Exception as e:
                    logger.warning(f"Could not load neighborhoods: {e}")

                try:
                    from services import boundary_service
                    if boundary_service.is_available('neighbourhoods'):
                        raw = boundary_service.get('neighbourhoods')
                        if raw:
                            boundary_data = json.loads(raw)
                            boundary_data['features'] = [
                                f for f in boundary_data['features']
                                if f.get('properties', {}).get('ADM1_PCODE') == 'SY02'
                            ]
                            bd_geojson = json.dumps(boundary_data, ensure_ascii=False)
                except Exception as e:
                    logger.warning(f"Failed to load boundaries: {e}")

                return nh_geojson, bd_geojson

            def _load_landmarks_streets():
                lm_json = None
                st_json = None
                try:
                    from services.api_client import get_api_client
                    from services.map_utils import normalize_landmark, normalize_street
                    from app.config import Config
                    api = get_api_client()
                    sw_lat = Config.MAP_BOUNDS_MIN_LAT
                    sw_lng = Config.MAP_BOUNDS_MIN_LNG
                    ne_lat = Config.MAP_BOUNDS_MAX_LAT
                    ne_lng = Config.MAP_BOUNDS_MAX_LNG

                    landmarks = api.get_landmarks_for_map(
                        south_west_lat=sw_lat, south_west_lng=sw_lng,
                        north_east_lat=ne_lat, north_east_lng=ne_lng
                    )
                    if landmarks and isinstance(landmarks, list):
                        landmarks = [normalize_landmark(lm) for lm in landmarks]
                        lm_json = json.dumps(landmarks, ensure_ascii=False)
                        logger.info(f"Loaded {len(landmarks)} landmarks for map")

                    streets = api.get_streets_for_map(
                        south_west_lat=sw_lat, south_west_lng=sw_lng,
                        north_east_lat=ne_lat, north_east_lng=ne_lng
                    )
                    if streets and isinstance(streets, list):
                        streets = [normalize_street(s) for s in streets]
                        st_json = json.dumps(streets, ensure_ascii=False)
                        logger.info(f"Loaded {len(streets)} streets for map")
                except Exception as e:
                    logger.warning(f"Failed to load landmarks/streets: {e}")

                return lm_json, st_json

            with ThreadPoolExecutor(max_workers=2) as executor:
                f_nh = executor.submit(_load_neighborhoods)
                f_ls = executor.submit(_load_landmarks_streets)

                nh_geojson, bd_geojson = f_nh.result()
                lm_json, st_json = f_ls.result()

            result['neighborhoods_geojson'] = nh_geojson
            result['boundaries_geojson'] = bd_geojson
            result['landmarks_json'] = lm_json
            result['streets_json'] = st_json

            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Layers worker error: {e}", exc_info=True)
            self.error.emit(str(e))


class _SearchWorker(QThread):
    """Background worker for search operations without blocking UI."""
    found = pyqtSignal(str, float, float, int)  # name, lat, lng, zoom
    not_found = pyqtSignal(str)  # search_text
    error = pyqtSignal(str)

    def __init__(self, search_text, auth_token, neighborhoods_cache):
        super().__init__()
        self._search_text = search_text
        self._auth_token = auth_token
        self.neighborhoods_cache = neighborhoods_cache

    def run(self):
        try:
            from services.api_client import get_api_client
            search_text = self._search_text

            # Step 1: load neighborhoods if not cached
            if self.neighborhoods_cache is None:
                try:
                    api = get_api_client()
                    if self._auth_token:
                        api.set_access_token(self._auth_token)
                    self.neighborhoods_cache = api.get_neighborhoods() or []
                    logger.info(f"Loaded {len(self.neighborhoods_cache)} neighborhoods from API")
                except Exception as e:
                    logger.warning(f"Failed to load neighborhoods: {e}")
                    self.neighborhoods_cache = []

            # Step 2: match neighborhood
            match = self._match_neighborhood(search_text)
            if match and match["lat"] and match["lng"]:
                try:
                    self.found.emit(match["name"], float(match["lat"]), float(match["lng"]), 17)
                    return
                except (ValueError, TypeError):
                    logger.warning(f"Invalid coords for {match['name']}")

            if not match:
                # Step 3: places fallback (local file, fast)
                try:
                    from services import boundary_service
                    places = boundary_service.get_places_list()
                    for p in places:
                        if search_text in p.get('name_ar', '') or \
                           search_text.lower() in p.get('name_en', '').lower():
                            label = p.get('name_ar') or p.get('name_en') or search_text
                            self.found.emit(label, float(p['lat']), float(p['lng']), 13)
                            return
                except Exception as e:
                    logger.warning(f"Places search error: {e}")

                # Step 4: landmarks API
                try:
                    from services.map_utils import normalize_landmark
                    api = get_api_client()
                    landmarks = api.search_landmarks(search_text, max_results=5)
                    if landmarks and isinstance(landmarks, list):
                        lm = normalize_landmark(landmarks[0])
                        lat, lng = lm.get("latitude"), lm.get("longitude")
                        if lat and lng:
                            self.found.emit(
                                lm.get("name", search_text),
                                float(lat), float(lng), 17
                            )
                            return
                except Exception as e:
                    logger.warning(f"Landmark search error: {e}")

                self.not_found.emit(search_text)
                return

            # Step 5: neighborhood matched but no coords - search buildings
            if match and match.get("code"):
                try:
                    api = get_api_client()
                    if self._auth_token:
                        api.set_access_token(self._auth_token)
                    response = api.search_buildings(
                        neighborhood_code=match["code"], page_size=200
                    )
                    buildings_data = response.get('buildings', response.get('data', []))
                    lats, lons = [], []
                    for b_data in buildings_data:
                        b = Building.from_dict(b_data)
                        if b.latitude and b.longitude:
                            lats.append(b.latitude)
                            lons.append(b.longitude)
                    if lats:
                        zoom = 19 if len(lats) <= 5 else 18 if len(lats) <= 15 else 17
                        self.found.emit(
                            match["name"],
                            sum(lats) / len(lats),
                            sum(lons) / len(lons),
                            zoom
                        )
                        return
                except Exception as e:
                    logger.warning(f"Building search error: {e}")

            self.not_found.emit(search_text)

        except Exception as e:
            logger.error(f"Search worker error: {e}", exc_info=True)
            self.error.emit(str(e))

    def _match_neighborhood(self, search_text):
        """Match search text against cached neighborhoods."""
        search_lower = search_text.lower().strip()
        best_match = None
        for n in (self.neighborhoods_cache or []):
            name_ar = n.get("nameArabic", "") or ""
            name_en = n.get("nameEnglish", "") or n.get("name", "") or ""
            if search_lower == name_ar.lower() or search_lower == name_en.lower():
                best_match = n
                break
            if not best_match:
                if search_lower in name_ar.lower() or search_lower in name_en.lower():
                    best_match = n
        if not best_match:
            return None
        code = (
            best_match.get("neighborhoodCode") or best_match.get("code")
            or best_match.get("fullCode") or ""
        )
        name = best_match.get("nameArabic") or best_match.get("nameEnglish") or ""
        lat = best_match.get("centerLatitude") or best_match.get("latitude") or best_match.get("centroidLat")
        lng = best_match.get("centerLongitude") or best_match.get("longitude") or best_match.get("centroidLng")
        return {"code": code, "name": name, "lat": lat, "lng": lng}


class BuildingMapDialog(BaseMapDialog):
    """Dialog for selecting a single building by clicking on map."""

    def __init__(
        self,
        db: Database,
        selected_building_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        read_only: bool = False,
        selected_building: Optional[Building] = None,
        parent=None,
        show_confirm_button: bool = False,
        show_multiselect_ui: bool = False,
    ):
        """Initialize building map dialog."""
        self.db = db
        self.building_controller = BuildingController(db)
        self._fallback_building = selected_building
        self._selected_building = None
        self._selected_building_id = selected_building_id
        self._is_view_only = read_only or bool(selected_building_id)  # Support explicit read_only
        self._buildings_cache = []  # Cache loaded buildings for quick lookup

        # Use provided auth token first, fallback to parent window
        self._auth_token = auth_token
        if not self._auth_token:
            try:
                if parent:
                    main_window = parent
                    while main_window and not hasattr(main_window, 'current_user'):
                        main_window = main_window.parent()
                    if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                        self._auth_token = getattr(main_window.current_user, '_api_token', None)
            except Exception as e:
                logger.warning(f"Could not get auth token from parent: {e}")

        # Set auth token for BuildingController
        if self._auth_token and self.building_controller.is_using_api:
            self.building_controller.set_auth_token(self._auth_token)
            logger.info("Auth token set for BuildingController in dialog")
        else:
            logger.warning("No auth token available for BuildingMapDialog")

        # Determine mode based on whether we're viewing or selecting
        if self._is_view_only:
            # View-only mode: just show the map, no selection controls
            title = tr("dialog.map.view_building_on_map")
            show_search = False
        else:
            # Selection mode: allow building selection
            title = tr("dialog.map.search_on_map")
            show_search = True

        # Store auth token temporarily (BaseMapDialog.__init__ will overwrite it)
        temp_auth_token = self._auth_token

        # Initialize base dialog (clean design)
        # Enable viewport loading for dynamic building loading
        super().__init__(
            title=title,
            show_search=show_search,
            show_confirm_button=show_confirm_button,
            show_multiselect_ui=show_multiselect_ui,
            enable_viewport_loading=True,
            parent=parent
        )

        # Restore auth token after BaseMapDialog.__init__
        self._auth_token = temp_auth_token
        logger.debug(f"Auth token set in BaseMapDialog: {bool(self._auth_token)}")

        # Set token in viewport loader
        if hasattr(self, '_viewport_loader') and self._viewport_loader:
            if self._viewport_loader.map_service and self._auth_token:
                self._viewport_loader.map_service.set_auth_token(self._auth_token)
                logger.info(f"Auth token set in viewport loader")
            self._viewport_loader.db = self.db

        # Connect building selection signal (from map clicks)
        self.building_selected.connect(self._on_building_selected_from_map)

        # Cache for neighborhoods (loaded from API on first search)
        self._neighborhoods_cache = None
        self._search_worker = None

        self._buildings_worker = None
        self._layers_worker = None
        self._page_loaded = False
        self._pending_layers_data = None
        self._pending_buildings_data = None
        QTimer.singleShot(50, self._start_map_load)

    def _start_map_load(self):
        """Show map immediately with tiles, then load buildings in background."""
        from services.tile_server_manager import get_tile_server_url
        from ui.constants.map_constants import MapConstants

        tile_url = get_tile_server_url()
        logger.info(f"Map tile server URL: {tile_url}")

        center_lat = MapConstants.DEFAULT_CENTER_LAT
        center_lon = MapConstants.DEFAULT_CENTER_LON
        zoom = 15

        # For view-only with fallback building, center on it
        if self._is_view_only and self._fallback_building:
            fb = self._fallback_building
            if fb.latitude and fb.longitude:
                center_lat, center_lon = fb.latitude, fb.longitude
                zoom = 20

        # Show map immediately with empty buildings
        empty_geojson = '{"type":"FeatureCollection","features":[]}'
        try:
            html = generate_leaflet_html(
                tile_server_url=tile_url.rstrip('/'),
                buildings_geojson=empty_geojson,
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=zoom,
                max_zoom=20,
                show_legend=False,
                show_layer_control=False,
                enable_selection=(not self._is_view_only),
                enable_viewport_loading=(not self._is_view_only),
                enable_drawing=False,
                neighborhoods_geojson=None,
                landmarks_json='[]',
                streets_json='[]',
                boundaries_geojson=None,
                boundary_level='neighbourhoods',
            )
            if not html:
                logger.error("generate_leaflet_html returned empty HTML")
                self._show_map_error(tr("dialog.map.map_load_failed"))
                return
            self.load_map_html(html)
        except Exception as e:
            logger.error(f"Failed to generate map HTML: {e}", exc_info=True)
            self._show_map_error(tr("dialog.map.map_load_failed"))
            return

        # Track page load for deferred layers injection
        if self.web_view:
            self.web_view.loadFinished.connect(self._on_page_ready)

        # Show loading overlay on map
        if self.web_view:
            js_overlay = """
            (function() {
                var overlay = document.createElement('div');
                overlay.id = 'loadingOverlay';
                overlay.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);' +
                    'background:rgba(27,43,77,0.85);color:white;padding:8px 20px;border-radius:20px;' +
                    'font-size:13px;font-family:Arial;z-index:9999;direction:rtl;';
                overlay.textContent = '{tr("dialog.map.loading_buildings")}';
                document.body.appendChild(overlay);
            })();
            """
            QTimer.singleShot(300, lambda: self.web_view.page().runJavaScript(js_overlay))

        self._buildings_worker = _BuildingsWorker(
            self._auth_token, self._selected_building_id,
            self._is_view_only, self._fallback_building,
            center_lat, center_lon
        )
        self._buildings_worker.finished.connect(self._on_buildings_ready)
        self._buildings_worker.error.connect(self._on_map_data_error)
        self._buildings_worker.start()

        self._layers_worker = _LayersWorker(self._auth_token)
        self._layers_worker.finished.connect(self._on_layers_ready)
        self._layers_worker.error.connect(lambda e: logger.warning(f"Layers loading failed: {e}"))
        self._layers_worker.start()

    def _on_map_data_error(self, error_msg):
        """Handle map data loading error."""
        logger.error(f"Map data loading failed: {error_msg}")
        ErrorHandler.show_error(self, f"{tr('dialog.map.error_loading_map')}\n{error_msg}", tr("dialog.map.error_title"))

    def _on_buildings_ready(self, data):
        """Inject buildings into the already-visible map, or buffer if page not loaded."""
        if not self._page_loaded:
            self._pending_buildings_data = data
            logger.info("Buildings data buffered, waiting for page load")
            return
        self._inject_buildings(data)

    def _inject_buildings(self, data):
        """Inject buildings GeoJSON into the map page via JavaScript."""
        try:
            buildings_geojson = data.get('buildings_geojson', '{"type":"FeatureCollection","features":[]}')

            if 'buildings_list' in data:
                self._buildings_cache = data['buildings_list']
                logger.info(f"Cached {len(self._buildings_cache)} buildings for selection")

            geojson_data = json.loads(buildings_geojson) if isinstance(buildings_geojson, str) else buildings_geojson

            focus_building_id = None
            center_lat = center_lon = None

            if self._is_view_only and self._selected_building_id:
                buildings = data.get('view_buildings', [])
                if buildings:
                    selected_geojson = GeoJSONConverter.buildings_to_geojson(buildings, force_points=True)
                    selected_data = json.loads(selected_geojson)
                    if selected_data.get('features'):
                        existing_ids = {f.get('properties', {}).get('building_id') for f in geojson_data.get('features', [])}
                        for feature in selected_data['features']:
                            bid = feature.get('properties', {}).get('building_id')
                            if bid not in existing_ids:
                                geojson_data['features'].append(feature)
                        buildings_geojson = json.dumps(geojson_data)

                focus_building = next(
                    (b for b in buildings
                     if b.building_id == self._selected_building_id
                     or b.building_uuid == self._selected_building_id), None
                )
                if not focus_building and self._fallback_building:
                    focus_building = self._fallback_building

                if focus_building:
                    if focus_building.latitude and focus_building.longitude:
                        center_lat, center_lon = focus_building.latitude, focus_building.longitude
                    elif focus_building.geo_location:
                        geometry, _ = GeoJSONConverter._parse_geo_location(focus_building.geo_location)
                        if geometry:
                            centroid = GeoJSONConverter._calculate_centroid(geometry)
                            if centroid:
                                center_lon, center_lat = centroid['coordinates']
                    focus_building_id = self._selected_building_id

            safe_geojson = json.dumps(buildings_geojson) if isinstance(buildings_geojson, str) else json.dumps(json.dumps(buildings_geojson))
            js_inject = f"""
            (function() {{
                var overlay = document.getElementById('loadingOverlay');
                if (overlay) overlay.remove();

                var geojsonStr = {safe_geojson};
                var geojsonData = (typeof geojsonStr === 'string') ? JSON.parse(geojsonStr) : geojsonStr;
                if (typeof buildingsLayer !== 'undefined' && buildingsLayer) {{
                    buildingsLayer.clearLayers();
                    L.geoJSON(geojsonData, buildingsLayer.options).eachLayer(function(layer) {{
                        buildingsLayer.addLayer(layer);
                    }});
                }} else if (typeof L !== 'undefined' && typeof map !== 'undefined') {{
                    window.buildingsLayer = L.geoJSON(geojsonData, {{
                        style: function(feature) {{
                            return {{color: '#1a73e8', weight: 2, fillOpacity: 0.3}};
                        }},
                        onEachFeature: function(feature, layer) {{
                            if (feature.properties && feature.properties.building_id) {{
                                layer.on('click', function() {{
                                    if (typeof bridge !== 'undefined') {{
                                        bridge.onBuildingSelected(feature.properties.building_id);
                                    }}
                                }});
                            }}
                        }}
                    }}).addTo(map);
                }}
                console.log('Buildings injected: ' + (geojsonData.features ? geojsonData.features.length : 0));

                // Attach multiselect handlers to newly injected buildings
                if (window.multiselectMode && typeof window.attachMultiselectHandler === 'function') {{
                    if (typeof buildingsLayer !== 'undefined' && buildingsLayer) {{
                        buildingsLayer.eachLayer(function(layer) {{
                            window.attachMultiselectHandler(layer);
                        }});
                    }}
                    console.log('Multi-select handlers attached to injected buildings');
                }}
            }})();
            """
            if self.web_view:
                self.web_view.page().runJavaScript(js_inject)

                update_count_js = """
                (function() {
                    if (typeof buildingsLayer !== 'undefined' && buildingsLayer) {
                        var count = buildingsLayer.getLayers().length;
                        if (typeof window.updateBuildingCount === 'function') {
                            window.updateBuildingCount(count);
                        }
                    }
                })();
                """
                QTimer.singleShot(500, lambda: self.web_view.page().runJavaScript(update_count_js))

            if self._is_view_only and focus_building_id and center_lat and center_lon:
                self._fly_to(center_lat, center_lon, 20)
                QTimer.singleShot(2500, lambda: self._open_building_popup_immediate(
                    focus_building_id, center_lat, center_lon))

        except Exception as e:
            logger.error(f"Error injecting buildings: {e}", exc_info=True)

    def _on_page_ready(self, success):
        """Called when HTML page finishes loading - inject any buffered data."""
        if success:
            self._page_loaded = True
            if self._pending_buildings_data:
                self._inject_buildings(self._pending_buildings_data)
                self._pending_buildings_data = None
            if self._pending_layers_data:
                self._inject_layers(self._pending_layers_data)
                self._pending_layers_data = None

    def _on_layers_ready(self, data):
        """Inject landmarks and streets, or buffer if page not loaded yet."""
        if self._page_loaded:
            self._inject_layers(data)
        else:
            self._pending_layers_data = data
            logger.info("Layers data buffered, waiting for page load")

    def _inject_layers(self, data):
        """Inject landmarks and streets into the loaded map page."""
        try:
            landmarks_json = data.get('landmarks_json')
            if landmarks_json and self.web_view:
                js_lm = f"if(typeof updateLandmarksOnMap==='function')updateLandmarksOnMap({landmarks_json});"
                self.web_view.page().runJavaScript(js_lm)

            streets_json = data.get('streets_json')
            if streets_json and self.web_view:
                js_st = f"if(typeof updateStreetsOnMap==='function')updateStreetsOnMap({streets_json});"
                self.web_view.page().runJavaScript(js_st)
        except Exception as e:
            logger.error(f"Error injecting layers: {e}", exc_info=True)

    def _open_building_popup_immediate(self, building_id: str, lat: float, lon: float):
        """Open popup for focused building when map loads."""
        js = f"""
        (function() {{
            console.log('Focus mode: Opening building {building_id} immediately');

            // Wait for map to be fully loaded and ready
            if (typeof map !== 'undefined' && map) {{
                map.whenReady(function() {{
                    console.log('Map ready, focusing on building {building_id}');

                    // Find and enhance building marker
                    if (typeof buildingsLayer !== 'undefined' && buildingsLayer) {{
                        buildingsLayer.eachLayer(function(layer) {{
                            if (layer.feature && layer.feature.properties.building_id === '{building_id}') {{
                                console.log('Found building marker');

                                // Enhanced marker for visibility
                                if (layer.setIcon) {{
                                    // FIX: Convert status from int to string key if needed
                                    var rawStatus = layer.feature.properties.status || 1;
                                    var status = (typeof rawStatus === 'number' && typeof getStatusKey === 'function')
                                        ? getStatusKey(rawStatus)
                                        : (typeof rawStatus === 'string' ? rawStatus : 'intact');

                                    var statusColors = {{
                                        'intact': '#28a745',
                                        'minor_damage': '#ffc107',
                                        'major_damage': '#fd7e14',
                                        'severely_damaged': '#dc3545',
                                        'destroyed': '#dc3545',
                                        'under_construction': '#17a2b8',
                                        'demolished': '#6c757d'
                                    }};
                                    var color = statusColors[status] || '#0072BC';

                                    // Large icon: 2x size (72x108)
                                    var largeIcon = L.divIcon({{
                                        className: 'building-pin-icon-huge',
                                        html: '<div style="width: 72px; height: 108px;">' +
                                              '<svg width="72" height="108" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                                              '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                                              'fill="' + color + '" stroke="#fff" stroke-width="3"/>' +
                                              '<circle cx="12" cy="12" r="5" fill="#fff"/>' +
                                              '</svg></div>',
                                        iconSize: [72, 108],
                                        iconAnchor: [36, 108],
                                        popupAnchor: [0, -108]
                                    }});
                                    layer.setIcon(largeIcon);

                                    // Bring marker to front (above all other buildings)
                                    if (layer.setZIndexOffset) {{
                                        layer.setZIndexOffset(10000);  // Very high z-index
                                    }}

                                    console.log('Enhanced icon set with color: ' + color);
                                }}

                                // Bring layer to front
                                if (layer.bringToFront) {{
                                    layer.bringToFront();
                                }}

                                // Open popup immediately (no delay!)
                                setTimeout(function() {{
                                    layer.openPopup();
                                    console.log('Popup opened');
                                }}, 100);  // Minimal delay for rendering
                            }}
                        }});
                    }}
                }});
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def _open_building_popup(self, building_id: str, lat: float, lon: float):
        """Open popup for focused building in view-only mode."""
        def center_and_open():
            js = f"""
            console.log('Centering on building {building_id} at [{lat}, {lon}]');

            if (typeof map !== 'undefined') {{
                // Center map on building
                map.setView([{lat}, {lon}], map.getZoom(), {{
                    animate: true,
                    duration: 0.8
                }});

                // Find and open popup
                if (typeof buildingsLayer !== 'undefined') {{
                    buildingsLayer.eachLayer(function(layer) {{
                        if (layer.feature && layer.feature.properties.building_id === '{building_id}') {{
                            // Enhanced marker for visibility
                            if (layer.setIcon) {{
                                // FIX: Convert status from int to string key if needed
                                var rawStatus = layer.feature.properties.status || 1;
                                var status = (typeof rawStatus === 'number' && typeof getStatusKey === 'function')
                                    ? getStatusKey(rawStatus)
                                    : (typeof rawStatus === 'string' ? rawStatus : 'intact');

                                var statusColors = {{
                                    'intact': '#28a745',
                                    'minor_damage': '#ffc107',
                                    'major_damage': '#fd7e14',
                                    'severely_damaged': '#dc3545',
                                    'destroyed': '#dc3545',
                                    'under_construction': '#17a2b8',
                                    'demolished': '#6c757d'
                                }};
                                var color = statusColors[status] || '#0072BC';

                                var largeIcon = L.divIcon({{
                                    className: 'building-pin-icon-large',
                                    html: '<div style="width: 36px; height: 54px;">' +
                                          '<svg width="36" height="54" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                                          '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                                          'fill="' + color + '" stroke="#fff" stroke-width="3"/>' +
                                          '<circle cx="12" cy="12" r="5" fill="#fff"/>' +
                                          '</svg></div>',
                                    iconSize: [36, 54],
                                    iconAnchor: [18, 54],
                                    popupAnchor: [0, -54]
                                }});
                                layer.setIcon(largeIcon);
                            }}

                            // Open popup
                            setTimeout(function() {{
                                layer.openPopup();
                                console.log('Popup opened');
                            }}, 500);
                        }}
                    }});
                }}
            }}
            """
            self.web_view.page().runJavaScript(js)

        # Execute after map loads
        QTimer.singleShot(2000, center_and_open)

    def _on_building_selected_from_map(self, building_id: str):
        """Handle building selection from map click."""
        logger.info(f"Building selected from map: {building_id}")

        try:
            # Use cached buildings from dialog (same buildings shown on the map)
            cached_buildings = self._buildings_cache or []

            logger.debug(f"Searching in {len(cached_buildings)} cached buildings from dialog")

            # Find exact match by building_id in cached data
            matching_building = None
            for b in cached_buildings:
                if b.building_id == building_id:
                    matching_building = b
                    logger.info(f"Found building in cache: {building_id}")
                    break

            if matching_building:
                # Enrich building with full details (cache may lack address names)
                enriched = self._enrich_building_data(matching_building)
                self._selected_building = enriched or matching_building
                logger.info(f"Building {self._selected_building.building_id} selected, closing dialog")
                self.accept()
            else:
                # Fallback: Try searching in API (in case cache is empty)
                logger.warning(f"Building not in cache, trying API search...")

                from services.map_service_api import MapServiceAPI
                map_service = MapServiceAPI()
                if self._auth_token:
                    map_service.set_auth_token(self._auth_token)

                matching_building = map_service.get_building_with_polygon(building_id)

                if matching_building:
                    self._selected_building = matching_building
                    logger.info(f"Building {matching_building.building_id} selected, closing dialog")
                    self.accept()
                else:
                    logger.warning(f"Building not found in API: {building_id}")
                    self._show_building_not_found_error(building_id)

        except Exception as e:
            logger.error(f"Error selecting building: {e}", exc_info=True)
            self._show_building_not_found_error(building_id)

    def _enrich_building_data(self, cached_building: Building) -> Optional[Building]:
        """Enrich a cached building with full address data from the detail API."""
        try:
            # Use the building UUID to get full details
            building_uuid = cached_building.building_uuid
            if not building_uuid:
                logger.warning("Cannot enrich: no building_uuid")
                return None

            from services.map_service_api import MapServiceAPI
            map_service = MapServiceAPI()
            if self._auth_token:
                map_service.set_auth_token(self._auth_token)

            enriched = map_service.get_building_with_polygon(building_uuid)
            if enriched:
                # Preserve geo_location from cache if enriched doesn't have it
                if not enriched.geo_location and cached_building.geo_location:
                    enriched.geo_location = cached_building.geo_location
                logger.info(f"Enriched building {cached_building.building_id} with full address data")
                return enriched

        except Exception as e:
            logger.warning(f"Could not enrich building data: {e}")

        return None

    def _show_building_not_found_error(self, building_id: str):
        """Show error message when building is not found."""
        ErrorHandler.show_warning(
            self,
            f"{tr('dialog.map.building_code')}: {building_id}\n"
            f"{tr('dialog.map.building_not_found_in_db')}\n"
            f"{tr('dialog.map.building_may_be_deleted')}",
            tr("dialog.map.building_not_found_title")
        )

    def _show_load_warning(self):
        """Show warning toast when initial building load fails."""
        try:
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("dialog.map.buildings_load_failed_try_pan"), Toast.WARNING)
        except Exception:
            pass

    def _load_neighborhoods_cache(self):
        """Load all neighborhoods from API (lazy, called once on first search)."""
        if self._neighborhoods_cache is not None:
            return

        try:
            from services.api_client import get_api_client
            api_client = get_api_client()
            if not api_client:
                raise Exception("No API client available")
            if self._auth_token:
                api_client.set_access_token(self._auth_token)

            self._neighborhoods_cache = api_client.get_neighborhoods() or []
            logger.info(f"Loaded {len(self._neighborhoods_cache)} neighborhoods from API")
        except Exception as e:
            logger.warning(f"Failed to load neighborhoods from API: {e}")
            self._neighborhoods_cache = []

    def _match_neighborhood(self, search_text: str):
        """Match search text against cached neighborhoods. Returns (code, name, lat, lng) or None."""
        search_lower = search_text.lower().strip()

        best_match = None
        for n in self._neighborhoods_cache:
            name_ar = n.get("nameArabic", "") or ""
            name_en = n.get("nameEnglish", "") or n.get("name", "") or ""

            # Exact match gets priority
            if search_lower == name_ar.lower() or search_lower == name_en.lower():
                best_match = n
                break

            # Partial match (contains)
            if not best_match:
                if search_lower in name_ar.lower() or search_lower in name_en.lower():
                    best_match = n

        if not best_match:
            return None

        code = (
            best_match.get("neighborhoodCode") or best_match.get("code")
            or best_match.get("fullCode") or ""
        )
        name = best_match.get("nameArabic") or best_match.get("nameEnglish") or ""
        lat = best_match.get("centerLatitude") or best_match.get("latitude") or best_match.get("centroidLat")
        lng = best_match.get("centerLongitude") or best_match.get("longitude") or best_match.get("centroidLng")

        return {"code": code, "name": name, "lat": lat, "lng": lng}

    def _on_search_submitted(self):
        """Handle search submission - runs in background thread to avoid UI freeze."""
        if not self.show_search or not hasattr(self, 'search_input'):
            return

        search_text = self.search_input.text().strip()
        if not search_text:
            return

        self.search_input.setEnabled(False)
        self.search_input.setPlaceholderText(tr("dialog.map.searching"))
        logger.info(f"Searching for: '{search_text}'")

        self._search_worker = _SearchWorker(
            search_text, self._auth_token, self._neighborhoods_cache
        )
        self._search_worker.found.connect(self._on_search_found)
        self._search_worker.not_found.connect(self._on_search_not_found)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    def _on_search_found(self, name, lat, lng, zoom):
        """Handle successful search result from worker."""
        # Update neighborhoods cache from worker
        if self._search_worker and self._search_worker.neighborhoods_cache:
            self._neighborhoods_cache = self._search_worker.neighborhoods_cache
        self._fly_to(lat, lng, zoom)
        from ui.components.toast import Toast
        Toast.show_toast(self, name, "success")
        self._reset_search_input()

    def _on_search_not_found(self, search_text):
        """Handle search not found - try streets JS layer as last resort."""
        # Update neighborhoods cache from worker
        if self._search_worker and self._search_worker.neighborhoods_cache:
            self._neighborhoods_cache = self._search_worker.neighborhoods_cache
        from ui.components.toast import Toast

        def _on_street_not_found():
            Toast.show_toast(self, f"{tr('dialog.map.not_found')}: {search_text}", "warning")

        self._search_streets_js(search_text, not_found_callback=_on_street_not_found)
        self._reset_search_input()

    def _on_search_error(self, error_msg):
        """Handle search error from worker."""
        logger.error(f"Search error: {error_msg}")
        self._reset_search_input()

    def _reset_search_input(self):
        """Re-enable search input after search completes."""
        if hasattr(self, 'search_input'):
            self.search_input.setEnabled(True)
            self.search_input.setPlaceholderText(tr("dialog.map.search_placeholder"))

    def get_selected_building(self) -> Optional[Building]:
        """Get selected building or None."""
        return self._selected_building


def show_building_map_dialog(
    db: Database,
    selected_building_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    read_only: bool = False,
    selected_building: Optional[Building] = None,
    parent=None
) -> Optional[Building]:
    """Show building map dialog and return selected building, or None if cancelled."""
    dialog = BuildingMapDialog(db, selected_building_id, auth_token, read_only, selected_building, parent)
    result = dialog.exec_()

    if result == dialog.Accepted:
        return dialog.get_selected_building()

    return None


class MultiSelectBuildingMapDialog(BuildingMapDialog):
    """Building map dialog with multi-select support.

    Uses the same fast map, search, landmarks, and streets as BuildingMapDialog
    but enables multi-select mode so users can click multiple buildings.
    """

    def __init__(self, db: Database, auth_token: Optional[str] = None, parent=None,
                 center_lat: Optional[float] = None, center_lon: Optional[float] = None,
                 initial_zoom: Optional[int] = None,
                 already_selected_ids: Optional[list] = None):
        self._multi_selected_buildings: List[Building] = []
        self._already_selected_ids = set(already_selected_ids or [])
        self._initial_center_lat = center_lat
        self._initial_center_lon = center_lon
        self._initial_zoom = initial_zoom

        # Invalidate building cache on open so is_assigned status is fresh from API
        try:
            from services.building_cache_service import BuildingCacheService
            BuildingCacheService.get_instance().invalidate_cache()
        except Exception:
            pass

        super().__init__(
            db=db,
            selected_building_id=None,
            auth_token=auth_token,
            read_only=False,
            selected_building=None,
            parent=parent,
            show_confirm_button=True,
            show_multiselect_ui=True,
        )

        # Use FieldAssignmentMapProvider for assignment data (hasActiveAssignment, isLocked)
        try:
            from services.map_data_provider import FieldAssignmentMapProvider
            from services.api_client import get_api_client
            from services.map_service_api import MapServiceAPI
            fa_provider = FieldAssignmentMapProvider(get_api_client())
            fa_service = MapServiceAPI(data_provider=fa_provider)
            if self._auth_token:
                fa_service.set_auth_token(self._auth_token)
            if self._viewport_loader:
                self._viewport_loader.map_service = fa_service
        except Exception as e:
            logger.warning(f"Could not set FieldAssignmentMapProvider: {e}")

    def _start_map_load(self):
        """Override to enable multiselect in the generated HTML."""
        from services.tile_server_manager import get_tile_server_url
        from ui.constants.map_constants import MapConstants

        tile_url = get_tile_server_url()
        center_lat = getattr(self, '_initial_center_lat', None) or MapConstants.DEFAULT_CENTER_LAT
        center_lon = getattr(self, '_initial_center_lon', None) or MapConstants.DEFAULT_CENTER_LON
        zoom = getattr(self, '_initial_zoom', None) or 15

        empty_geojson = '{"type":"FeatureCollection","features":[]}'
        try:
            html = generate_leaflet_html(
                tile_server_url=tile_url.rstrip('/'),
                buildings_geojson=empty_geojson,
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=zoom,
                max_zoom=20,
                show_legend=False,
                show_layer_control=False,
                enable_selection=True,
                enable_multiselect=True,
                enable_viewport_loading=True,
                enable_drawing=False,
                neighborhoods_geojson=None,
                landmarks_json='[]',
                streets_json='[]',
                boundaries_geojson=None,
                boundary_level='neighbourhoods',
            )
            if not html:
                logger.error("generate_leaflet_html returned empty HTML")
                self._show_map_error(tr("dialog.map.map_load_failed"))
                return
            self.load_map_html(html)
        except Exception as e:
            logger.error(f"Failed to generate map HTML: {e}", exc_info=True)
            self._show_map_error(tr("dialog.map.map_load_failed"))
            return

        if self.web_view:
            self.web_view.loadFinished.connect(self._on_page_ready)

        if self.web_view:
            js_overlay = (
                "(function() {"
                "var overlay = document.createElement('div');"
                "overlay.id = 'loadingOverlay';"
                "overlay.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);' +"
                "'background:rgba(27,43,77,0.85);color:white;padding:8px 20px;border-radius:20px;' +"
                "'font-size:13px;font-family:Arial;z-index:9999;direction:rtl;';"
                f"overlay.textContent = '{tr('dialog.map.loading_buildings')}';"
                "document.body.appendChild(overlay);"
                "})();"
            )
            QTimer.singleShot(300, lambda: self.web_view.page().runJavaScript(js_overlay))

        fa_provider = None
        try:
            from services.map_data_provider import FieldAssignmentMapProvider
            from services.api_client import get_api_client
            fa_provider = FieldAssignmentMapProvider(get_api_client())
        except Exception:
            pass

        self._buildings_worker = _BuildingsWorker(
            self._auth_token, None, False, None,
            center_lat, center_lon,
            data_provider=fa_provider
        )
        self._buildings_worker.finished.connect(self._on_buildings_ready)
        self._buildings_worker.error.connect(self._on_map_data_error)
        self._buildings_worker.start()

        self._layers_worker = _LayersWorker(self._auth_token)
        self._layers_worker.finished.connect(self._on_layers_ready)
        self._layers_worker.error.connect(lambda e: logger.warning(f"Layers loading failed: {e}"))
        self._layers_worker.start()

    def _on_buildings_multiselected(self, building_ids_json: str):
        """Override: process batch building IDs from multiselect JS."""
        import json as _json
        try:
            new_ids = set(_json.loads(building_ids_json))
        except Exception:
            return

        current_ids = {b.building_id for b in self._multi_selected_buildings}
        added = new_ids - current_ids
        removed = current_ids - new_ids

        # Remove deselected
        if removed:
            self._multi_selected_buildings = [
                b for b in self._multi_selected_buildings if b.building_id not in removed
            ]

        # Add newly selected
        for bid in added:
            # Check if already selected in step1
            if bid in self._already_selected_ids:
                if self.web_view:
                    self.web_view.page().runJavaScript(
                        "showMapToast('\u0647\u0630\u0627 \u0627\u0644\u0645\u0628\u0646\u0649 \u0645\u062e\u062a\u0627\u0631 \u0645\u0633\u0628\u0642\u0627\u064b');"
                    )
                continue

            matching = self._find_building_in_cache(bid)
            if matching:
                self._multi_selected_buildings.append(matching)

        self.confirm_btn.setEnabled(len(self._multi_selected_buildings) > 0)
        logger.info(f"Multi-select: {len(self._multi_selected_buildings)} buildings selected")

    def _find_building_in_cache(self, building_id: str) -> Optional[Building]:
        """Find building in caches or fetch from API."""
        # Check initial buildings cache
        for b in (self._buildings_cache or []):
            if b.building_id == building_id:
                return b

        # Check viewport cache (populated by _on_viewport_buildings_cached)
        viewport_cache = getattr(self, '_viewport_buildings_cache', {})
        cached = viewport_cache.get(building_id)
        if cached:
            return cached

        # Check application-wide building cache (always populated by viewport loading)
        try:
            from services.building_cache_service import BuildingCacheService
            cache_service = BuildingCacheService.get_instance()
            global_cached = cache_service.get_building_by_id(building_id)
            if global_cached:
                return global_cached
        except Exception:
            pass

        # Fallback: fetch from API
        try:
            from services.map_service_api import MapServiceAPI
            map_service = MapServiceAPI()
            if self._auth_token:
                map_service.set_auth_token(self._auth_token)
            return map_service.get_building_with_polygon(building_id)
        except Exception as e:
            logger.warning(f"Could not fetch building {building_id}: {e}")
            return None

    def _on_building_selected_from_map(self, building_id: str):
        """Fallback: handle individual building selection signal."""
        pass

    def get_selected_buildings(self) -> List[Building]:
        """Get all selected buildings."""
        return list(self._multi_selected_buildings)


def show_multiselect_map_dialog(
    db: Database,
    auth_token: Optional[str] = None,
    parent=None,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    initial_zoom: Optional[int] = None,
    already_selected_ids: Optional[list] = None,
) -> Optional[List[Building]]:
    """Show multi-select building map dialog. Returns list of buildings or None."""
    dialog = MultiSelectBuildingMapDialog(
        db, auth_token, parent,
        center_lat=center_lat,
        center_lon=center_lon,
        initial_zoom=initial_zoom,
        already_selected_ids=already_selected_ids,
    )
    result = dialog.exec_()

    if result == dialog.Accepted:
        selected = dialog.get_selected_buildings()
        if selected:
            return selected

    return None
