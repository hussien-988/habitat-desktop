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
from PyQt5.QtWidgets import QMessageBox
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

    def __init__(self, db: Database, selected_building_id: Optional[str] = None, parent=None):
        """
        Initialize building map dialog.

        Args:
            db: Database instance
            selected_building_id: Optional building ID to show (view-only mode)
            parent: Parent widget
        """
        self.db = db
        self.building_controller = BuildingController(db)
        self._selected_building = None
        self._selected_building_id = selected_building_id
        self._is_view_only = bool(selected_building_id)
        self._buildings_cache = []  # Cache loaded buildings for quick lookup

        # Get auth token from parent window if available
        self._auth_token = None
        try:
            if parent:
                main_window = parent
                while main_window and not hasattr(main_window, 'current_user'):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                    self._auth_token = getattr(main_window.current_user, '_api_token', None)
                    # Set auth token for BuildingController
                    if self._auth_token and self.building_controller.is_using_api:
                        self.building_controller.set_auth_token(self._auth_token)
                        logger.debug("Auth token set for BuildingController")
        except Exception as e:
            logger.warning(f"Could not get auth token from parent: {e}")

        # Determine mode based on whether we're viewing or selecting
        if self._is_view_only:
            # View-only mode: just show the map, no selection controls
            title = "عرض المبنى على الخريطة"
            show_search = False
        else:
            # Selection mode: allow building selection
            title = "بحث على الخريطة"
            show_search = True

        # Initialize base dialog (clean design)
        # SIMPLIFIED: No viewport loading - load once like un-1 (more reliable!)
        super().__init__(
            title=title,
            show_search=show_search,
            enable_viewport_loading=False,  # Disabled for reliability (like un-1)
            parent=parent
        )

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

            # Get auth token from parent window if available
            auth_token = None
            try:
                if self.parent():
                    main_window = self.parent()
                    while main_window and not hasattr(main_window, 'current_user'):
                        main_window = main_window.parent()
                    if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                        auth_token = getattr(main_window.current_user, '_api_token', None)
                        logger.debug(f"Got auth token from MainWindow: {bool(auth_token)}")
            except Exception as e:
                logger.warning(f"Could not get auth token from parent: {e}")

            # Load buildings using shared method (DRY principle)
            # SIMPLIFIED: Load more buildings initially like un-1 (200 buildings)
            # No viewport loading - single load for reliability
            buildings_geojson = self.load_buildings_geojson(self.db, limit=200, auth_token=auth_token)

            # DEBUG: Check if buildings were loaded
            import json
            geojson_data = json.loads(buildings_geojson) if isinstance(buildings_geojson, str) else buildings_geojson
            num_features = len(geojson_data.get('features', []))
            logger.info(f"📊 Loaded {num_features} buildings into GeoJSON")

            if num_features == 0:
                logger.error("❌ NO BUILDINGS LOADED! GeoJSON is empty!")
            else:
                # Check if buildings have coordinates
                features_with_coords = sum(
                    1 for f in geojson_data['features']
                    if f.get('geometry') and f['geometry'].get('coordinates')
                )
                logger.info(f"📍 Buildings with coordinates: {features_with_coords}/{num_features}")

            # Only load buildings if in view-only mode (for focusing on specific building)
            buildings = []
            if self._is_view_only and self._selected_building_id:
                building_filter = BuildingFilter(search_text=self._selected_building_id)
                result = self.building_controller.load_buildings(building_filter)
                buildings = result.data if result.success else []

            # Determine center and zoom
            # CLOSER zoom - avoid gray tiles!
            center_lat = 36.2021
            center_lon = 37.1343
            zoom = 16  # Closer zoom - shows buildings clearly, no gray areas!
            focus_building_id = None

            # If view-only mode, focus on the selected building
            if self._is_view_only and self._selected_building_id:
                focus_building = next(
                    (b for b in buildings if b.building_id == self._selected_building_id),
                    None
                )
                if focus_building and focus_building.latitude and focus_building.longitude:
                    center_lat = focus_building.latitude
                    center_lon = focus_building.longitude
                    zoom = 17  # Close zoom for single building
                    focus_building_id = self._selected_building_id
                    logger.info(f"View-only mode: Focusing on building {focus_building_id}")

            # Generate map HTML using LeafletHTMLGenerator
            # SIMPLIFIED: No viewport loading like un-1 (more reliable for selection!)
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,  # Full load (200 buildings)
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=zoom,
                max_zoom=17,  # CRITICAL: Limit max zoom to available tiles (prevents gray areas)
                show_legend=True,
                show_layer_control=False,
                enable_selection=(not self._is_view_only),  # Enable selection in selection mode
                enable_viewport_loading=False,  # Disabled for reliability (like un-1)
                enable_drawing=False  # No drawing for building selection
            )

            # Load into web view
            self.load_map_html(html)

            # If view-only mode, open popup for focused building
            if self._is_view_only and focus_building_id:
                self._open_building_popup(focus_building_id, center_lat, center_lon)

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء تحميل الخريطة:\n{str(e)}"
            )

    def _open_building_popup(self, building_id: str, lat: float, lon: float):
        """
        Open popup for focused building in view-only mode.

        Args:
            building_id: Building ID to focus on
            lat: Latitude
            lon: Longitude
        """
        def center_and_open():
            js = f"""
            console.log('🎯 Centering on building {building_id} at [{lat}, {lon}]');

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
                                var status = layer.feature.properties.status || 'intact';
                                var statusColors = {{
                                    'intact': '#28a745',
                                    'minor_damage': '#ffc107',
                                    'major_damage': '#fd7e14',
                                    'destroyed': '#dc3545'
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
                                console.log('✅ Popup opened');
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

        Args:
            building_id: Building ID clicked (17-digit code, NOT UUID!)
        """
        logger.info(f"Building selected from map: {building_id}")

        try:
            # CRITICAL FIX: Use BuildingFilter to search by building_id (17-digit code)
            # NOT get_building_by_id() which expects UUID!
            building_filter = BuildingFilter(search_text=building_id)
            result = self.building_controller.load_buildings(building_filter)

            if result.success and result.data:
                building = result.data[0]  # Get first match
                self._selected_building = building

                # Close dialog and proceed to next step (no confirmation message needed)
                logger.info(f"✅ Building {building.building_id} selected, closing dialog")
                self.accept()
            else:
                logger.error(f"Building not found: {building_id}")
                QMessageBox.warning(
                    self,
                    "خطأ",
                    f"لم يتم العثور على المبنى: {building_id}"
                )

        except Exception as e:
            logger.error(f"Error getting building: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء جلب بيانات المبنى:\n{str(e)}"
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
            self.search_input.setPlaceholderText("⏳ جاري البحث...")

        try:
            from app.config import AleppoDivisions

            logger.info(f"🔍 Searching for: '{search_text}'")

            # PROFESSIONAL FIX: Convert neighborhood name → code (API requires code!)
            # API search_buildings() accepts neighborhood_code, NOT name
            neighborhood_code = None
            matched_name = None

            for code, name_en, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
                if (search_text.lower() in name_ar.lower() or
                    search_text.lower() in name_en.lower()):
                    neighborhood_code = code
                    matched_name = name_ar
                    logger.info(f"✅ Matched '{search_text}' → code: {code} ({name_ar})")
                    break

            if not neighborhood_code:
                logger.warning(f"⚠️ No neighborhood match for: '{search_text}'")
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
                logger.warning(f"⚠️ No buildings found for neighborhood code: {neighborhood_code}")
                from ui.components.toast import Toast
                Toast.show_toast(self, f"لا توجد مباني في: {matched_name}", "info")
                return

            # Convert API data to Building objects
            buildings = []
            for b_data in buildings_data:
                building = Building.from_dict(b_data)
                buildings.append(building)

            logger.info(f"✅ Found {len(buildings)} buildings in {matched_name}")

            # Calculate center from buildings with coordinates
            lats = []
            lons = []

            for building in buildings:
                if building.latitude and building.longitude:
                    lats.append(building.latitude)
                    lons.append(building.longitude)

            logger.info(f"📍 Buildings with coordinates: {len(lats)}/{len(buildings)}")

            if lats and lons:
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)

                # Dynamic zoom based on number of buildings (Best Practice)
                # CLOSER ZOOM - avoid gray tiles, show buildings clearly
                if len(lats) <= 5:
                    safe_zoom = 17  # Very few buildings - very close zoom
                elif len(lats) <= 15:
                    safe_zoom = 16  # Small area - close zoom
                else:
                    safe_zoom = 16  # Large area - still close! (avoid gray tiles)

                logger.info(f"🎯 Navigating to: ({center_lat:.6f}, {center_lon:.6f}) with zoom {safe_zoom}")

                # PROFESSIONAL FIX: Smooth navigation without "jitter"
                # Problem: viewport loading adds buildings during flyTo causing jitter
                # Solution: Disable viewport loading events during flyTo
                js_code = f"""
                console.log('🔍 SEARCH: Flying to [{center_lat}, {center_lon}], zoom {safe_zoom}');

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
                        console.log('✅ FlyTo completed - viewport events re-enabled');
                    }}, 2200);

                    console.log('✅ FlyTo started smoothly');
                }}
                """

                self.web_view.page().runJavaScript(js_code)
            else:
                logger.error(f"❌ No buildings with coordinates in '{search_text}'!")
                from ui.components.toast import Toast
                Toast.show_toast(self, f"المباني في {search_text} ليس لديها إحداثيات", "warning")

        except Exception as e:
            logger.error(f"❌ Error searching: {e}", exc_info=True)

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
    parent=None
) -> Optional[Building]:
    """
    Convenience function to show building map dialog.

    Args:
        db: Database instance
        selected_building_id: Optional building ID to show (view-only mode)
        parent: Parent widget

    Returns:
        Selected building, or None if cancelled
    """
    dialog = BuildingMapDialog(db, selected_building_id, parent)
    result = dialog.exec_()

    if result == dialog.Accepted:
        return dialog.get_selected_building()

    return None
