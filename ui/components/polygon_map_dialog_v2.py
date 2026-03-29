# -*- coding: utf-8 -*-
"""
Polygon Map Dialog V2 - حوار اختيار المباني عبر الخريطة
Dialog for selecting buildings by polygon or click on map.
"""

import json
from typing import List, Optional
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QWidget, QLabel
from ui.error_handler import ErrorHandler
from PyQt5.QtCore import Qt

from repositories.database import Database
from models.building import Building
from ui.components.base_map_dialog import BaseMapDialog
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from services.leaflet_html_generator import generate_leaflet_html
from services.geojson_converter import GeoJSONConverter
from services.api_worker import ApiWorker
from utils.logger import get_logger
from services.translation_manager import tr

logger = get_logger(__name__)


class PolygonMapDialog(BaseMapDialog):
    """Dialog for selecting multiple buildings on map."""

    def __init__(self, db: Database, auth_token: Optional[str] = None, parent=None):
        """Initialize polygon map dialog."""
        self.db = db
        self._selected_buildings = []
        self._building_id_to_building = {}  # Quick lookup (populated during selection)
        self.buildings = []

        # Store auth_token before super().__init__ (BaseMapDialog resets it)
        _temp_auth_token = auth_token
        if not _temp_auth_token:
            try:
                if parent:
                    main_window = parent
                    while main_window and not hasattr(main_window, 'current_user'):
                        main_window = main_window.parent()
                    if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                        _temp_auth_token = getattr(main_window.current_user, '_api_token', None)
            except Exception as e:
                logger.warning(f"Could not get auth token from parent: {e}")

        super().__init__(
            title=tr("dialog.map.select_buildings_on_map"),
            show_search=False,
            show_multiselect_ui=False,  # No building list panel - clean map
            show_confirm_button=False,  # Custom confirm button below
            enable_viewport_loading=True,
            parent=parent
        )

        # Set auth_token after super().__init__
        self._auth_token = _temp_auth_token
        if hasattr(self, '_viewport_loader') and self._viewport_loader:
            if self._viewport_loader.map_service and self._auth_token:
                self._viewport_loader.map_service.set_auth_token(self._auth_token)
            self._viewport_loader.db = self.db

        self._clicked_building_ids = []
        self.buildings_multiselected.connect(self._on_buildings_clicked)

        self._add_confirm_button()

        # Load map
        self._load_map()

    def _add_confirm_button(self):
        """Add confirm button bar at bottom with selection counter."""
        # Find the main content widget
        if not hasattr(self, 'layout') or self.layout() is None:
            return

        # Create button container
        button_container = QWidget()
        button_container.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(24, 8, 24, 16)
        button_layout.setSpacing(12)

        # Selection counter (left side)
        self._selection_label = QLabel("")
        self._selection_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._selection_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; padding: 4px 8px;")
        button_layout.addWidget(self._selection_label)

        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BACKGROUND};
                border-color: {Colors.TEXT_SECONDARY};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Confirm button
        self.confirm_selection_btn = QPushButton(tr("dialog.map.confirm_selection"))
        self.confirm_selection_btn.setFixedSize(140, 40)
        self.confirm_selection_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_selection_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.confirm_selection_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
            QPushButton:disabled {{
                background-color: {Colors.LIGHT_GRAY_BG};
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        self.confirm_selection_btn.setEnabled(False)
        self.confirm_selection_btn.clicked.connect(self._on_confirm_selection)
        button_layout.addWidget(self.confirm_selection_btn)

        # Add to main layout
        main_widget = self.findChild(QWidget)
        if main_widget and main_widget.layout():
            main_widget.layout().addWidget(button_container)

    def _on_selection_count_updated(self, count: int):
        """Update selection counter label and confirm button state."""
        if hasattr(self, '_selection_label'):
            if count == 0:
                self._selection_label.setText("")
            elif count == 1:
                self._selection_label.setText(tr("dialog.map.one_building_selected"))
            elif count == 2:
                self._selection_label.setText(tr("dialog.map.two_buildings_selected"))
            elif count <= 10:
                self._selection_label.setText(tr("dialog.map.plural_buildings_selected", count=count))
            else:
                self._selection_label.setText(tr("dialog.map.many_buildings_selected", count=count))

        if hasattr(self, 'confirm_selection_btn'):
            self.confirm_selection_btn.setEnabled(count > 0)

    def _on_confirm_selection(self):
        """Handle confirm button click. Resolves Building objects from caches."""
        building_ids = getattr(self, '_clicked_building_ids', [])

        if not building_ids:
            ErrorHandler.show_warning(
                self,
                tr("dialog.map.please_select_buildings_first"),
                tr("dialog.map.no_buildings_selected")
            )
            return

        # Resolve Building objects from caches first
        viewport_cache = getattr(self, '_viewport_buildings_cache', {})
        cached_buildings = []
        uncached_ids = []

        for building_id in building_ids:
            building = (
                self._building_id_to_building.get(building_id)
                or viewport_cache.get(building_id)
            )
            if building:
                self._building_id_to_building[building.building_id] = building
                cached_buildings.append(building)
            else:
                uncached_ids.append(building_id)

        if not uncached_ids:
            # All buildings resolved from cache
            self._finalize_selection(cached_buildings)
            return

        # Fetch uncached buildings in background
        logger.info(f"Fetching {len(uncached_ids)} uncached buildings from API")
        if hasattr(self, 'confirm_selection_btn'):
            self.confirm_selection_btn.setEnabled(False)
            self.confirm_selection_btn.setText(tr("dialog.map.loading"))

        self._pending_cached_buildings = cached_buildings

        self._confirm_fetch_worker = ApiWorker(
            self._fetch_buildings_batch, uncached_ids
        )
        self._confirm_fetch_worker.finished.connect(self._on_confirm_fetch_finished)
        self._confirm_fetch_worker.error.connect(self._on_confirm_fetch_error)
        self._confirm_fetch_worker.start()

    def _fetch_buildings_batch(self, building_ids):
        """Fetch multiple buildings by ID (runs in background thread)."""
        from controllers.building_controller import BuildingController
        controller = BuildingController(self.db)
        if hasattr(self, '_auth_token') and self._auth_token:
            controller.set_auth_token(self._auth_token)

        fetched = []
        for building_id in building_ids:
            try:
                result = controller.get_building_by_id(building_id)
                if result.success and result.data:
                    fetched.append(result.data)
                else:
                    logger.warning(f"Building {building_id} not found: {result.message}")
            except Exception as e:
                logger.error(f"Error fetching building {building_id}: {e}")
        return fetched

    def _on_confirm_fetch_finished(self, fetched_buildings):
        """Handle batch building fetch completion."""
        if hasattr(self, 'confirm_selection_btn'):
            self.confirm_selection_btn.setText(tr("dialog.map.confirm_selection"))
            self.confirm_selection_btn.setEnabled(True)

        cached = getattr(self, '_pending_cached_buildings', [])
        all_buildings = cached + (fetched_buildings or [])

        for b in (fetched_buildings or []):
            if b.building_id:
                self._building_id_to_building[b.building_id] = b

        self._finalize_selection(all_buildings)

    def _on_confirm_fetch_error(self, error_msg):
        """Handle batch building fetch error."""
        logger.error(f"Confirm fetch error: {error_msg}")
        if hasattr(self, 'confirm_selection_btn'):
            self.confirm_selection_btn.setText(tr("dialog.map.confirm_selection"))
            self.confirm_selection_btn.setEnabled(True)

        # Try to finalize with whatever we have cached
        cached = getattr(self, '_pending_cached_buildings', [])
        if cached:
            self._finalize_selection(cached)
        else:
            ErrorHandler.show_warning(
                self,
                tr("dialog.map.building_details_not_found"),
                tr("dialog.map.data_fetch_error")
            )

    def _finalize_selection(self, buildings):
        """Finalize confirmed building selection."""
        if buildings:
            self._selected_buildings = buildings
            logger.info(f"Confirmed selection of {len(buildings)} buildings")
            self._cleanup_overlay()
            self.accept()
        else:
            logger.warning("Could not resolve any buildings")
            ErrorHandler.show_warning(
                self,
                tr("dialog.map.building_details_not_found"),
                tr("dialog.map.data_fetch_error")
            )

    def accept(self):
        """Override to ensure overlay cleanup."""
        try:
            self._cleanup_overlay()
        except Exception as e:
            logger.warning(f"Error cleaning overlay in accept: {e}")
        finally:
            super().accept()

    def reject(self):
        """Override to ensure overlay cleanup."""
        try:
            self._cleanup_overlay()
        except Exception as e:
            logger.warning(f"Error cleaning overlay in reject: {e}")
        finally:
            super().reject()

    def closeEvent(self, event):
        """Override to ensure overlay cleanup."""
        try:
            self._cleanup_overlay()
        except Exception as e:
            logger.warning(f"Error cleaning overlay in closeEvent: {e}")
        finally:
            super().closeEvent(event)

    def _load_map(self):
        """Load map with multi-select mode."""
        from services.tile_server_manager import get_tile_server_url

        try:
            # Get tile server URL
            tile_server_url = get_tile_server_url()

            if self._auth_token:
                logger.info(f"_load_map: Auth token available (length: {len(self._auth_token)})")
            else:
                logger.error(f"_load_map: NO AUTH TOKEN! Viewport loading will fail!")

            # Start with empty buildings; load asynchronously to avoid blocking
            buildings_geojson = '{"type":"FeatureCollection","features":[]}'
            self._load_initial_buildings_async()

            # Load neighborhoods for map overlay (shared helper)
            neighborhoods_geojson = self.load_neighborhoods_geojson(auth_token=self._auth_token)
            logger.info(f"Neighborhoods result: {'loaded' if neighborhoods_geojson else 'None/failed'}")

            boundaries_geojson = None
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
                        boundaries_geojson = json.dumps(boundary_data, ensure_ascii=False)
                        logger.info(f"Loaded {len(boundary_data['features'])} neighbourhood boundaries for Aleppo")
            except Exception as e:
                logger.warning(f"Failed to load neighbourhood boundaries: {e}")

            center_lat, center_lon = 36.2021, 37.1343

            # Load landmarks and streets asynchronously (injected after map loads)
            self._load_landmarks_streets_async(center_lat, center_lon)

            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=15,
                max_zoom=20,
                show_legend=True,
                show_layer_control=False,
                enable_selection=False,
                enable_multiselect=True,
                enable_viewport_loading=True,
                enable_drawing=False,
                neighborhoods_geojson=neighborhoods_geojson,
                landmarks_json='[]',
                streets_json='[]',
                boundaries_geojson=boundaries_geojson,
                boundary_level='neighbourhoods',
            )

            # Load into web view
            self.load_map_html(html)

            logger.info(f"Polygon map loaded with viewport loading enabled (FAST!)")

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"{tr('dialog.map.error_loading_map')}\n{str(e)}",
                tr("dialog.map.error_title")
            )

    def _load_landmarks_streets_async(self, center_lat: float, center_lon: float):
        """Load landmarks and streets in a background thread, inject via JS when ready."""
        def _fetch():
            from services.api_client import get_api_client
            from services.map_utils import normalize_landmark, normalize_street
            api = get_api_client()
            result = {'landmarks': None, 'streets': None}

            landmarks = api.get_landmarks_for_map(
                south_west_lat=center_lat - 0.5, south_west_lng=center_lon - 0.5,
                north_east_lat=center_lat + 0.5, north_east_lng=center_lon + 0.5
            )
            if landmarks and isinstance(landmarks, list):
                result['landmarks'] = [normalize_landmark(lm) for lm in landmarks]

            streets = api.get_streets_for_map(
                south_west_lat=center_lat - 0.5, south_west_lng=center_lon - 0.5,
                north_east_lat=center_lat + 0.5, north_east_lng=center_lon + 0.5
            )
            if streets and isinstance(streets, list):
                result['streets'] = [normalize_street(s) for s in streets]

            return result

        self._landmarks_streets_worker = ApiWorker(_fetch)
        self._landmarks_streets_worker.finished.connect(self._on_landmarks_streets_loaded)
        self._landmarks_streets_worker.error.connect(
            lambda err: logger.warning(f"Failed to load landmarks/streets: {err}")
        )
        self._landmarks_streets_worker.start()

    def _on_landmarks_streets_loaded(self, result):
        """Inject landmarks and streets into the already-loaded map via JavaScript."""
        try:
            if result.get('landmarks'):
                landmarks_js = json.dumps(result['landmarks'], ensure_ascii=False)
                self.web_view.page().runJavaScript(
                    f"if(typeof updateLandmarksOnMap==='function'){{updateLandmarksOnMap({landmarks_js});}}"
                )
                logger.info(f"Injected {len(result['landmarks'])} landmarks into map")
            if result.get('streets'):
                streets_js = json.dumps(result['streets'], ensure_ascii=False)
                self.web_view.page().runJavaScript(
                    f"if(typeof updateStreetsOnMap==='function'){{updateStreetsOnMap({streets_js});}}"
                )
                logger.info(f"Injected {len(result['streets'])} streets into map")
        except Exception as e:
            logger.warning(f"Error injecting landmarks/streets into map: {e}")

    def _load_initial_buildings_async(self):
        """Load initial buildings in a background thread, inject into map when ready."""
        if not hasattr(self, '_viewport_buildings_cache'):
            self._viewport_buildings_cache = {}

        self._buildings_load_worker = ApiWorker(self._load_and_cache_initial_buildings)
        self._buildings_load_worker.finished.connect(self._on_initial_buildings_loaded)
        self._buildings_load_worker.error.connect(
            lambda err: logger.warning(f"Failed to load initial buildings: {err}")
        )
        self._buildings_load_worker.start()

    def _on_initial_buildings_loaded(self, result):
        """Handle initial buildings loaded from background thread."""
        buildings = result.get('buildings', [])
        geojson = result.get('geojson')

        if not buildings:
            logger.info("No initial buildings loaded")
            return

        # Cache buildings
        self.buildings = buildings
        for b in buildings:
            if b.building_id:
                self._viewport_buildings_cache[b.building_id] = b

        # Inject into map via JavaScript
        if geojson:
            try:
                self.web_view.page().runJavaScript(
                    f"""
                    if (typeof buildingsLayer !== 'undefined') {{
                        var newData = {geojson};
                        var newLayer = L.geoJSON(newData, buildingsLayer.options);
                        newLayer.eachLayer(function(layer) {{ buildingsLayer.addLayer(layer); }});
                        console.log('Injected ' + newData.features.length + ' initial buildings');
                    }}
                    """
                )
                logger.info(f"Injected {len(buildings)} initial buildings into map")
            except Exception as e:
                logger.warning(f"Error injecting buildings into map: {e}")

    def _load_and_cache_initial_buildings(self):
        """
        Load initial buildings (runs in background thread).
        Returns dict with 'buildings' list and 'geojson' string.
        """
        from services.geojson_converter import GeoJSONConverter

        # Try API first (only if auth token available)
        if self._auth_token:
            try:
                from services.map_service_api import MapServiceAPI
                map_service = MapServiceAPI()
                map_service.set_auth_token(self._auth_token)

                buildings = map_service.get_buildings_in_bbox(
                    north_east_lat=36.5,
                    north_east_lng=37.5,
                    south_west_lat=36.0,
                    south_west_lng=36.8,
                    page_size=200
                )

                if buildings:
                    logger.info(f"Loaded {len(buildings)} initial buildings from API")
                    geojson = GeoJSONConverter.buildings_to_geojson(buildings, prefer_polygons=True)
                    return {'buildings': buildings, 'geojson': geojson}

            except Exception as e:
                logger.error(f"API unavailable for map buildings: {e}", exc_info=True)

        # Fallback: load via BuildingController
        try:
            from controllers.building_controller import BuildingController
            controller = BuildingController(self.db)
            result = controller.load_buildings()
            if result.success and result.data:
                buildings = result.data
                logger.info(f"Loaded {len(buildings)} buildings via controller for map")
                geojson = GeoJSONConverter.buildings_to_geojson(buildings, prefer_polygons=True)
                return {'buildings': buildings, 'geojson': geojson}
        except Exception as e2:
            logger.error(f"BuildingController fallback also failed: {e2}", exc_info=True)

        return {'buildings': [], 'geojson': None}

    def _on_geometry_selected(self, geom_type: str, wkt: str):
        """Handle polygon drawn - query buildings within polygon."""
        logger.info(f"_on_geometry_selected called!")
        logger.info(f"   geom_type: {geom_type}")
        logger.info(f"   wkt: {wkt[:100] if wkt else 'None'}...")

        try:
            # Query buildings within polygon using BuildingAssignments API
            self._selected_buildings = self._query_buildings_in_polygon(wkt)

            if self._selected_buildings:
                count = len(self._selected_buildings)
                logger.info(f"Found {count} buildings in polygon")

                
                building_ids = [b.building_id for b in self._selected_buildings]

                
                for building in self._selected_buildings:
                    if building.building_id not in self._building_id_to_building:
                        self._building_id_to_building[building.building_id] = building


                if not hasattr(self, '_selected_building_ids'):
                    self._selected_building_ids = []
                self._selected_building_ids = building_ids

                self._update_buildings_list(building_ids)

                #  Update counter display (uses parent class method)
                self._on_selection_count_updated(count)

                # Highlight selected buildings on map
                self._highlight_selected_buildings()

                # Enable confirm button
                if hasattr(self, 'confirm_selection_btn'):
                    self.confirm_selection_btn.setEnabled(True)
                    logger.info(f"Confirm button enabled ({count} buildings selected)")

                logger.info(f"Found {count} buildings in polygon - shown on map")
            else:
                logger.warning("No buildings found in polygon")
                ErrorHandler.show_warning(
                    self,
                    tr("dialog.map.polygon_no_buildings"),
                    tr("dialog.map.no_buildings_title")
                )
                # Don't close - let user redraw

        except Exception as e:
            logger.error(f"Error querying buildings: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"{tr('dialog.map.error_searching_buildings')}\n{str(e)}",
                tr("dialog.map.error_title")
            )

    def _query_buildings_in_polygon(self, polygon_wkt: str) -> List[Building]:
        """Query buildings within polygon using BuildingAssignments API."""
        logger.info(f"_query_buildings_in_polygon called")
        logger.info(f"FULL WKT STRING:")
        logger.info(f"   {polygon_wkt}")
        logger.info(f"   WKT length: {len(polygon_wkt) if polygon_wkt else 0} characters")
        logger.info(f"   Using BuildingAssignments API (PostGIS in Backend)")

        try:
            from services.api_client import get_api_client
            from models.building import Building

            api_client = get_api_client()

            if hasattr(self, '_auth_token') and self._auth_token:
                api_client.set_access_token(self._auth_token)
                logger.debug("Auth token set for BuildingAssignments API")
            else:
                logger.warning("No auth token available - trying anyway")

            
            result = api_client.search_buildings_for_assignment(
                polygon_wkt=polygon_wkt,
                has_active_assignment=None,  # Get all buildings (we'll filter later if needed)
                page=1,
                page_size=10000  # Get all buildings in polygon (up to 10k)
            )

            buildings_data = result.get("items", [])
            total_count = result.get("totalCount", 0)
            polygon_area = result.get("polygonAreaSquareMeters", 0)

            logger.info(f"BuildingAssignments API returned {len(buildings_data)} buildings")
            logger.info(f"   Total count: {total_count}")
            logger.info(f"   Polygon area: {polygon_area:.2f} m²")

            buildings_in_polygon = []
            for i, building_data in enumerate(buildings_data):
                try:
                    # Log first building's raw data
                    if i == 0:
                        logger.info(f"First building raw data from API:")
                        logger.info(f"   Keys: {list(building_data.keys())[:10]}")
                        logger.info(f"   ID field: {building_data.get('id', 'N/A')}")
                        logger.info(f"   buildingCode field: {building_data.get('buildingCode', 'N/A')}")

                    building = Building.from_dict(building_data)
                    buildings_in_polygon.append(building)
                except Exception as e:
                    logger.warning(f"Failed to convert building: {e}")
                    continue

            logger.info(f"Query results:")
            logger.info(f"   Total buildings in polygon: {len(buildings_in_polygon)}")

            return buildings_in_polygon

        except Exception as e:
            logger.error(f"Error querying BuildingAssignments API: {e}", exc_info=True)

            logger.warning("Falling back to local point-in-polygon check...")
            return self._query_buildings_in_polygon_local(polygon_wkt)

    def _query_buildings_in_polygon_local(self, polygon_wkt: str) -> List[Building]:
        """Fallback: query buildings using local point-in-polygon check."""
        logger.info(f"Using fallback local point-in-polygon check")
        logger.info(f"   Total buildings to check: {len(self.buildings)}")

        try:
            from services.map_service import MapService, GeoPoint, GeoPolygon

            # Create MapService with database connection
            if not hasattr(self, 'db') or not self.db:
                logger.error("Database connection not available")
                return []

            map_service = MapService(self.db.connection)
            polygon = GeoPolygon.from_wkt(polygon_wkt)

            if not polygon:
                logger.error(f"Failed to parse polygon WKT: {polygon_wkt}")
                return []

            logger.info(f"Polygon parsed successfully: {len(polygon.coordinates)} coordinates")

            buildings_in_polygon = []
            checked_count = 0
            skipped_count = 0

            for building in self.buildings:
                checked_count += 1

                # Skip buildings without coordinates
                if not building.latitude or not building.longitude:
                    skipped_count += 1
                    continue

                try:
                    # Check if building point is within polygon
                    point = GeoPoint(latitude=building.latitude, longitude=building.longitude)
                    is_inside = map_service._point_in_polygon(point, polygon)

                    if is_inside:
                        buildings_in_polygon.append(building)
                        logger.debug(f"Building {building.building_id} is inside polygon")

                except Exception as e:
                    logger.warning(f"Error checking building {building.building_id}: {e}")
                    continue

            logger.info(f"Fallback query results:")
            logger.info(f"   Total checked: {checked_count}")
            logger.info(f"   Skipped (no coords): {skipped_count}")
            logger.info(f"   Found inside polygon: {len(buildings_in_polygon)}")

            return buildings_in_polygon

        except Exception as e:
            logger.error(f"Error in fallback query: {e}", exc_info=True)
            return []

    def _on_buildings_clicked(self, building_ids: List[str]):
        """Handle buildings selected by clicking on map."""
        logger.info(f"Buildings clicked: {building_ids}")

        # Store IDs for deferred fetch on confirm
        self._clicked_building_ids = list(building_ids)

        # Cache any buildings we already have
        for building_id in building_ids:
            if building_id not in self._building_id_to_building:
                cached = self._building_id_to_building.get(building_id)
                if cached:
                    continue

        # Button state is controlled by _on_selection_count_updated (from JS count signal)
        logger.info(f"Stored {len(building_ids)} building IDs for selection")

    def _highlight_selected_buildings(self):
        """Highlight selected buildings on map with blue color."""
        if not self._selected_buildings:
            return

        # Get building IDs
        building_ids = [b.building_id for b in self._selected_buildings]

        # JavaScript to highlight buildings
        js_code = f"""
        console.log(' Highlighting {len(building_ids)} selected buildings...');

        var selectedIds = {building_ids};
        var highlightedCount = 0;

        // Find and highlight each building marker
        if (typeof buildingsLayer !== 'undefined') {{
            buildingsLayer.eachLayer(function(layer) {{
                if (layer.feature && selectedIds.includes(layer.feature.properties.building_id)) {{
                    // Change marker color to blue
                    if (layer.setIcon) {{
                        var blueIcon = L.divIcon({{
                            className: 'building-pin-icon-selected',
                            html: '<div style="width: 30px; height: 45px;">' +
                                  '<svg width="30" height="45" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">' +
                                  '<path d="M12 0C5.4 0 0 5.4 0 12c0 8 12 24 12 24s12-16 12-24c0-6.6-5.4-12-12-12z" ' +
                                  'fill="#007bff" stroke="#fff" stroke-width="2"/>' +
                                  '<circle cx="12" cy="12" r="4" fill="#fff"/>' +
                                  '</svg></div>',
                            iconSize: [30, 45],
                            iconAnchor: [15, 45],
                            popupAnchor: [0, -45]
                        }});
                        layer.setIcon(blueIcon);
                        highlightedCount++;
                    }}
                }}
            }});
        console.log(' Highlighted ' + highlightedCount + ' buildings in blue');
        }} else {{
        console.warn(' buildingsLayer not found - cannot highlight buildings');
        }}
        """

        try:
            self.web_view.page().runJavaScript(js_code)
            logger.info(f"Highlighted {len(building_ids)} buildings on map")
        except Exception as e:
            logger.warning(f"Failed to highlight buildings: {e}")

    def get_selected_buildings(self) -> List[Building]:
        """Get selected buildings."""
        logger.info(f"get_selected_buildings() called")
        logger.info(f"   Returning {len(self._selected_buildings)} buildings")
        if self._selected_buildings:
            for i, bldg in enumerate(self._selected_buildings[:3]):  # Log first 3
                logger.info(f"   Building {i+1}: ID={bldg.building_id}")
        else:
            logger.warning("No buildings selected!")
        return self._selected_buildings


def show_polygon_map_dialog(
    db: Database,
    auth_token: Optional[str] = None,
    parent=None
    ) -> Optional[List[Building]]:
    """Show polygon map dialog and return selected buildings or None."""
    logger.info("show_polygon_map_dialog() called")
    dialog = PolygonMapDialog(db, auth_token, parent)
    result = dialog.exec_()

    logger.info(f"Dialog result: {'Accepted' if result == dialog.Accepted else 'Rejected/Cancelled'}")

    if result == dialog.Accepted:
        selected = dialog.get_selected_buildings()
        logger.info(f"Returning {len(selected) if selected else 0} buildings to parent")
        return selected
    else:
        logger.info("User cancelled - returning None")

    return None
