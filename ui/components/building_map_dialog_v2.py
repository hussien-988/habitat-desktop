# -*- coding: utf-8 -*-
"""
Building Map Dialog V2 - Unified Design for Building Selection.

Matches BuildingMapWidget design exactly - DRY principle.

Uses:
- BaseMapDialog for consistent UI
- LeafletHTMLGenerator for map rendering
- PostGIS-compatible WKT output
- Single building selection

Best Practices (DRY + SOLID):
- Extends BaseMapDialog (no duplication)
- Single Responsibility: Select single building by clicking
- Open/Closed: Extended BaseMapDialog, not modified
"""

from typing import Optional
from ui.error_handler import ErrorHandler
from PyQt5.QtCore import QTimer

from repositories.database import Database
from controllers.building_controller import BuildingController, BuildingFilter
from models.building import Building
from ui.components.base_map_dialog import BaseMapDialog
from services.leaflet_html_generator import generate_leaflet_html
from services.geojson_converter import GeoJSONConverter
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingMapDialog(BaseMapDialog):
    """
    Dialog for selecting a single building by clicking on map.

    Design matches BuildingMapWidget exactly.

    Returns:
        Building: Selected building
    """

    def __init__(
        self,
        db: Database,
        selected_building_id: Optional[str] = None,
        auth_token: Optional[str] = None,
        read_only: bool = False,
        selected_building: Optional[Building] = None,
        parent=None
    ):
        """
        Initialize building map dialog.

        Args:
            db: Database instance
            selected_building_id: Optional building ID to show (view-only mode)
            auth_token: Optional API authentication token
            read_only: If True, map is read-only (no selection allowed)
            selected_building: Optional Building object (fallback for coordinates if API fails)
            parent: Parent widget
        """
        self.db = db
        self.building_controller = BuildingController(db)
        self._fallback_building = selected_building
        self._selected_building = None
        self._selected_building_id = selected_building_id
        self._is_view_only = read_only or bool(selected_building_id)  # Support explicit read_only
        self._buildings_cache = []  # Cache loaded buildings for quick lookup

        # FIX: Use provided auth token first, fallback to parent window
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
            title = "عرض المبنى على الخريطة"
            show_search = False
        else:
            # Selection mode: allow building selection
            title = "بحث على الخريطة"
            show_search = True

        # FIX: Store auth token temporarily (BaseMapDialog.__init__ will overwrite it)
        temp_auth_token = self._auth_token

        # Initialize base dialog (clean design)
        # PHASE 2: Enable viewport loading for 9000+ buildings (dynamic loading)
        super().__init__(
            title=title,
            show_search=show_search,
            enable_viewport_loading=True,  # Enabled: Load buildings dynamically as user pans/zooms
            parent=parent
        )

        # FIX: Restore auth token (BaseMapDialog.__init__ sets _auth_token = None)
        # Now self._auth_token exists (from BaseMapDialog) - set it to our stored token
        self._auth_token = temp_auth_token
        logger.debug(f"Auth token set in BaseMapDialog: {bool(self._auth_token)}")

        # FIX: Set token in viewport loader to prevent 401 errors
        if hasattr(self, '_viewport_loader') and self._viewport_loader and self._viewport_loader.map_service and self._auth_token:
            self._viewport_loader.map_service.set_auth_token(self._auth_token)
            logger.info(f"Auth token set in viewport loader")

        # Connect building selection signal (from map clicks)
        self.building_selected.connect(self._on_building_selected_from_map)

        # SIMPLE: Load map with buildings directly (like old working version!)
        self._load_map()

    def _load_map(self):
        """Load map with buildings."""
        from services.tile_server_manager import get_tile_server_url

        try:
            # Get tile server URL
            tile_server_url = get_tile_server_url()

            # Use self._auth_token (already set in __init__)
            logger.debug(f"Using auth token for loading buildings: {bool(self._auth_token)}")

            # Load buildings using shared method (DRY principle)
            # VIEW-ONLY MODE: Load ONLY the selected building (no others!)
            # SELECTION MODE: 200 buildings for initial load
            if self._is_view_only and self._selected_building_id:
                # View-only: Empty initial load (will add selected building below)
                buildings_geojson = '{"type": "FeatureCollection", "features": []}'
                logger.info("View-only mode: Loading ONLY selected building (no initial 200)")
            else:
                # Selection mode: Load 200 buildings for browsing
                # IMPORTANT: Load buildings AND cache them for selection!
                from services.map_service_api import MapServiceAPI
                from services.geojson_converter import GeoJSONConverter

                map_service = MapServiceAPI()
                if self._auth_token:
                    map_service.set_auth_token(self._auth_token)

                # Load buildings from BuildingAssignments API
                buildings = map_service.get_buildings_in_bbox(
                    north_east_lat=36.5,
                    north_east_lng=37.5,
                    south_west_lat=36.0,
                    south_west_lng=36.8,
                    page_size=200
                )

                # CRITICAL: Cache buildings for selection lookup!
                self._buildings_cache = buildings
                logger.info(f"Cached {len(buildings)} buildings for selection")

                # Convert to GeoJSON
                buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                    buildings,
                    prefer_polygons=True
                )

            # DEBUG: Check if buildings were loaded
            import json
            geojson_data = json.loads(buildings_geojson) if isinstance(buildings_geojson, str) else buildings_geojson
            num_features = len(geojson_data.get('features', []))
            logger.info(f"Loaded {num_features} buildings into GeoJSON")

            if num_features == 0:
                logger.error("NO BUILDINGS LOADED! GeoJSON is empty!")
            else:
                # Check if buildings have coordinates
                features_with_coords = sum(
                    1 for f in geojson_data['features']
                    if f.get('geometry') and f['geometry'].get('coordinates')
                )
                logger.info(f"Buildings with coordinates: {features_with_coords}/{num_features}")

            # Only load buildings if in view-only mode (for focusing on specific building)
            buildings = []
            if self._is_view_only and self._selected_building_id:
                logger.info(f"Focus mode: Looking for building_id = {self._selected_building_id}")

                from services.map_service_api import MapServiceAPI
                map_service = MapServiceAPI()
                if self._auth_token:
                    map_service.set_auth_token(self._auth_token)

                building = map_service.get_building_with_polygon(self._selected_building_id)
                buildings = [building] if building else []
                logger.info(f"Retrieved building with polygon: found {len(buildings)} buildings")

                # Fallback: if API didn't find the building, use the passed-in building object
                if not buildings and self._fallback_building:
                    buildings = [self._fallback_building]
                    logger.info(f"Using fallback building object for GeoJSON (lat={self._fallback_building.latitude}, lon={self._fallback_building.longitude})")

                # FIX: Add selected building to GeoJSON if not already present
                if buildings and len(buildings) > 0:
                    from services.geojson_converter import GeoJSONConverter
                    selected_building_geojson = GeoJSONConverter.buildings_to_geojson(
                        buildings,
                        prefer_polygons=True
                    )

                    # Merge selected building into buildings_geojson
                    selected_data = json.loads(selected_building_geojson)
                    if selected_data.get('features'):
                        # Check if building already exists in geojson_data
                        existing_ids = {
                            f.get('properties', {}).get('building_id')
                            for f in geojson_data.get('features', [])
                        }

                        # Add selected building if not present
                        for feature in selected_data['features']:
                            building_id = feature.get('properties', {}).get('building_id')
                            if building_id not in existing_ids:
                                geojson_data['features'].append(feature)
                                logger.info(f"Added selected building {building_id} to GeoJSON")

                        # Update buildings_geojson with merged data
                        buildings_geojson = json.dumps(geojson_data)

            # DEBUG: Check if buildings were loaded
            import json
            geojson_data = json.loads(buildings_geojson) if isinstance(buildings_geojson, str) else buildings_geojson
            num_features = len(geojson_data.get('features', []))
            logger.info(f"Loaded {num_features} buildings into GeoJSON")

            if num_features == 0:
                logger.error("NO BUILDINGS LOADED! GeoJSON is empty!")
            else:
                # Check if buildings have coordinates
                features_with_coords = sum(
                    1 for f in geojson_data['features']
                    if f.get('geometry') and f['geometry'].get('coordinates')
                )
                logger.info(f"Buildings with coordinates: {features_with_coords}/{num_features}")

            # Determine center and zoom
            #
            center_lat = 36.2021
            center_lon = 37.1343
            zoom = 15  #
            focus_building_id = None

            # If view-only mode, focus on the selected building
            if self._is_view_only and self._selected_building_id:
                logger.info(f"Focus mode: self._selected_building_id = {self._selected_building_id}")
                logger.info(f"Focus mode: buildings list has {len(buildings)} buildings")
                if buildings:
                    logger.info(f"Buildings IDs in list: {[b.building_id for b in buildings]}")

                focus_building = next(
                    (b for b in buildings
                     if b.building_id == self._selected_building_id
                     or b.building_uuid == self._selected_building_id),
                    None
                )

                if focus_building:
                    logger.info(f"Found focus_building: {focus_building.building_id}")
                else:
                    logger.warning(f"Could NOT find focus_building with ID {self._selected_building_id} in buildings list")

                if not focus_building and self._fallback_building:
                    # Use fallback building coordinates when API lookup fails
                    logger.info(f"Using fallback building coordinates for {self._selected_building_id}")
                    focus_building = self._fallback_building

                if focus_building:
                    # Calculate center from polygon geometry if available
                    if focus_building.geo_location and 'POLYGON' in focus_building.geo_location.upper():
                        from services.geojson_converter import GeoJSONConverter
                        geometry, _ = GeoJSONConverter._parse_geo_location(focus_building.geo_location)
                        if geometry and geometry.get('type') == 'Polygon':
                            coords = geometry['coordinates'][0]
                            center_lon = sum(c[0] for c in coords) / len(coords)
                            center_lat = sum(c[1] for c in coords) / len(coords)
                        elif focus_building.latitude and focus_building.longitude:
                            center_lat = focus_building.latitude
                            center_lon = focus_building.longitude
                        else:
                            center_lat = 36.2021
                            center_lon = 37.1343
                    elif focus_building.latitude and focus_building.longitude:
                        center_lat = focus_building.latitude
                        center_lon = focus_building.longitude
                    else:
                        center_lat = 36.2021
                        center_lon = 37.1343

                    zoom = 20
                    focus_building_id = self._selected_building_id
                    logger.info(f"Focusing on building {focus_building_id} at ({center_lat}, {center_lon}) with max zoom {zoom}")

            # Load neighborhoods for map overlay (DRY - shared helper from BaseMapDialog)
            neighborhoods_geojson = self.load_neighborhoods_geojson(auth_token=self._auth_token)

            # Generate map HTML using LeafletHTMLGenerator
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=zoom,
                max_zoom=20,
                show_legend=True,
                show_layer_control=False,
                enable_selection=(not self._is_view_only),
                enable_viewport_loading=(not self._is_view_only),
                enable_drawing=False,
                neighborhoods_geojson=neighborhoods_geojson,
                skip_fit_bounds=self._is_view_only
            )

            # Load into web view
            self.load_map_html(html)

            # If view-only mode, open popup for focused building immediately (no delay)
            if self._is_view_only and focus_building_id:
                logger.info(f"Opening popup for building {focus_building_id}")
                self._open_building_popup_immediate(focus_building_id, center_lat, center_lon)

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"حدث خطأ أثناء تحميل الخريطة:\n{str(e)}",
                "خطأ"
            )

    def _open_building_popup_immediate(self, building_id: str, lat: float, lon: float):
        """
        Open popup for focused building IMMEDIATELY when map loads (no flicker).

        FIX: Uses map.whenReady() to open popup as soon as map is ready.
        No gray screen, no center transition - direct focus on building!

        Args:
            building_id: Building ID to focus on
            lat: Latitude
            lon: Longitude
        """
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
        """
        Open popup for focused building in view-only mode (legacy method).

        Args:
            building_id: Building ID to focus on
            lat: Latitude
            lon: Longitude
        """
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
        """
        Handle building selection from map click.

        FIX: Use cached buildings from map (loaded from BuildingAssignments API)
        instead of searching in Buildings API (which has different data)!

        Args:
            building_id: Building ID clicked (17-digit code from BuildingAssignments API)
        """
        logger.info(f"Building selected from map: {building_id}")

        try:
            # BEST PRACTICE: Use cached buildings from dialog (loaded from BuildingAssignments API)
            # These are the SAME buildings shown on the map!
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
                self._selected_building = matching_building
                # Close dialog and proceed to next step (no confirmation message needed)
                logger.info(f"Building {matching_building.building_id} selected, closing dialog")
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

    def _show_building_not_found_error(self, building_id: str):
        """Show error message when building is not found."""
        ErrorHandler.show_warning(
            self,
            f"رمز المبنى: {building_id}\n"
            f"لم يتم العثور على هذا المبنى في قاعدة البيانات.\n"
            f"قد يكون المبنى محذوفاً أو غير مسجّل.",
            "لم يتم العثور على المبنى"
        )

    def _on_search_submitted(self):
        """Handle search submission - search using backend API."""
        if not self.show_search or not hasattr(self, 'search_input'):
            return

        search_text = self.search_input.text().strip()

        if not search_text:
            return

        # Show loading indicator
        if hasattr(self, 'search_input'):
            self.search_input.setEnabled(False)
            self.search_input.setPlaceholderText("جاري البحث...")

        try:
            from app.config import AleppoDivisions

            logger.info(f"Searching for: '{search_text}'")

            # PROFESSIONAL FIX: Convert neighborhood name → code (API requires code!)
            # API search_buildings() accepts neighborhood_code, NOT name
            neighborhood_code = None
            matched_name = None

            for code, name_en, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
                if (search_text.lower() in name_ar.lower() or
                    search_text.lower() in name_en.lower()):
                    neighborhood_code = code
                    matched_name = name_ar
                    logger.info(f"Matched '{search_text}' → code: {code} ({name_ar})")
                    break

            if not neighborhood_code:
                logger.warning(f"No neighborhood match for: '{search_text}'")
                from ui.components.toast import Toast
                Toast.show_toast(self, f"لم يتم العثور على الحي: {search_text}", "warning")
                return

            # Get buildings from API using neighborhood_code (CORRECT!)
            from services.api_client import get_api_client
            api_client = get_api_client()

            # PROFESSIONAL FIX: Update auth token before API call (prevent 401!)
            if self._auth_token:
                api_client.set_access_token(self._auth_token)
                logger.debug("Auth token synchronized before search")

            response = api_client.search_buildings(
                neighborhood_code=neighborhood_code,
                page_size=200  # Get all buildings in neighborhood
            )

            # Extract buildings from paginated response
            buildings_data = response.get('buildings', response.get('data', []))

            if not buildings_data:
                logger.warning(f"No buildings found for neighborhood code: {neighborhood_code}")
                from ui.components.toast import Toast
                Toast.show_toast(self, f"لا توجد مباني في: {matched_name}", "info")
                return

            # Convert API data to Building objects
            buildings = []
            for b_data in buildings_data:
                building = Building.from_dict(b_data)
                buildings.append(building)

            logger.info(f"Found {len(buildings)} buildings in {matched_name}")

            # Calculate center from buildings with coordinates
            lats = []
            lons = []

            for building in buildings:
                if building.latitude and building.longitude:
                    lats.append(building.latitude)
                    lons.append(building.longitude)

            logger.info(f"Buildings with coordinates: {len(lats)}/{len(buildings)}")

            if lats and lons:
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)

                # Dynamic zoom based on number of buildings (Best Practice)
                #
                if len(lats) <= 5:
                    safe_zoom = 19  # Very few buildings - very close zoom
                elif len(lats) <= 15:
                    safe_zoom = 18  # Small area - close zoom
                else:
                    safe_zoom = 17  # Large area - moderate zoom

                logger.info(f"Navigating to: ({center_lat:.6f}, {center_lon:.6f}) with zoom {safe_zoom}")

                # PROFESSIONAL FIX: Smooth navigation without "jitter"
                # Problem: viewport loading adds buildings during flyTo causing jitter
                # Solution: Disable viewport loading events during flyTo
                js_code = f"""
                console.log('SEARCH: Flying to [{center_lat}, {center_lon}], zoom {safe_zoom}');

                // Disable viewport loading events during flyTo (prevents jitter!)
                if (typeof window._isFlying === 'undefined') {{
                    window._isFlying = false;
                }}

                if (typeof map !== 'undefined') {{
                    window._isFlying = true;  // Set flag to skip viewport events

                    map.flyTo([{center_lat}, {center_lon}], {safe_zoom}, {{
                        duration: 2.0,      // Smooth & professional (2 seconds)
                        easeLinearity: 0.25 // Smooth easing
                    }});

                    // Re-enable viewport events after flyTo completes (2.2s = 2.0s + buffer)
                    setTimeout(function() {{
                        window._isFlying = false;
                        console.log('FlyTo completed - viewport events re-enabled');
                    }}, 2200);

                    console.log('FlyTo started smoothly');
                }}
                """

                self.web_view.page().runJavaScript(js_code)
            else:
                logger.error(f"No buildings with coordinates in '{search_text}'!")
                from ui.components.toast import Toast
                Toast.show_toast(self, f"المباني في {search_text} ليس لديها إحداثيات", "warning")

        except Exception as e:
            logger.error(f"Error searching: {e}", exc_info=True)

        finally:
            # Re-enable search input
            if hasattr(self, 'search_input'):
                self.search_input.setEnabled(True)
                self.search_input.setPlaceholderText("البحث عن منطقة (مثال: الجميلية)")

    def get_selected_building(self) -> Optional[Building]:
        """
        Get selected building.

        Returns:
            Selected building or None
        """
        return self._selected_building


def show_building_map_dialog(
    db: Database,
    selected_building_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    read_only: bool = False,
    selected_building: Optional[Building] = None,
    parent=None
) -> Optional[Building]:
    """
    Convenience function to show building map dialog.

    Args:
        db: Database instance
        selected_building_id: Optional building ID to show (view-only mode)
        auth_token: Optional API authentication token
        read_only: If True, map is read-only (no selection allowed)
        selected_building: Optional Building object (fallback for coordinates if API fails)
        parent: Parent widget

    Returns:
        Selected building, or None if cancelled
    """
    dialog = BuildingMapDialog(db, selected_building_id, auth_token, read_only, selected_building, parent)
    result = dialog.exec_()

    if result == dialog.Accepted:
        return dialog.get_selected_building()

    return None
