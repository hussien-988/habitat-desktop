# -*- coding: utf-8 -*-
"""
Map Picker Dialog V2 - Unified Design for Location/Polygon Selection.

Matches BuildingMapWidget design exactly - DRY principle.

Uses:
- BaseMapDialog for consistent UI
- LeafletHTMLGenerator for map rendering
- Leaflet.draw for point/polygon drawing
- PostGIS-compatible WKT output

Returns both point coordinates AND polygon WKT.
"""

from typing import Optional, Dict
from PyQt5.QtCore import pyqtSlot

from ui.components.base_map_dialog import BaseMapDialog
from services.leaflet_html_generator import generate_leaflet_html
from utils.logger import get_logger

logger = get_logger(__name__)


class MapPickerDialog(BaseMapDialog):
    """
    Dialog for picking location or drawing polygon.

    Design matches BuildingMapWidget exactly.

    Returns:
        Dict with 'latitude', 'longitude', and optional 'polygon_wkt'
    """

    def __init__(
        self,
        initial_lat: float = 36.2021,
        initial_lon: float = 37.1343,
        initial_zoom: int = 15,
        allow_polygon: bool = True,
        initial_bounds: list = None,
        neighborhoods_geojson: str = None,
        selected_neighborhood_code: str = None,
        db = None,
        skip_fit_bounds: bool = False,
        existing_polygon_wkt: str = None,
        parent=None
    ):
        """
        Initialize map picker dialog.

        Args:
            initial_lat: Initial map center latitude
            initial_lon: Initial map center longitude
            initial_zoom: Initial map zoom level (default: 15)
            allow_polygon: Allow polygon drawing (not just point)
            initial_bounds: Bounds to fit on load [[south_lat, west_lng], [north_lat, east_lng]]
            neighborhoods_geojson: GeoJSON FeatureCollection of neighborhood polygons
            selected_neighborhood_code: Currently selected neighborhood code for highlighting
            db: Database instance (optional, for loading buildings)
            skip_fit_bounds: Skip auto fitBounds (respect initial_zoom exactly)
            existing_polygon_wkt: Existing polygon WKT to display on map (for edit mode)
            parent: Parent widget
        """
        self.initial_lat = initial_lat
        self.initial_lon = initial_lon
        self.initial_zoom = initial_zoom
        self.allow_polygon = allow_polygon
        self.initial_bounds = initial_bounds
        self.neighborhoods_geojson = neighborhoods_geojson
        self.selected_neighborhood_code = selected_neighborhood_code
        self.db = db
        self._skip_fit_bounds = skip_fit_bounds
        self._existing_polygon_wkt = existing_polygon_wkt
        self._result = None

        # Initialize base dialog (no search bar, but show confirm button)
        super().__init__(
            title="تحديد الموقع على الخريطة",
            show_search=False,
            show_confirm_button=True,  # Show confirm button and coordinates
            parent=parent
        )

        # Connect geometry signal (but don't auto-close anymore)
        self.geometry_selected.connect(self._on_geometry_selected)

        # Load map
        self._load_map()

    def _load_map(self):
        """Load map with drawing tools AND existing buildings."""
        from services.tile_server_manager import get_local_server_url, get_tile_server_url

        try:
            # Local server for assets (leaflet.js, leaflet.css) — always local Python server
            tile_server_url = get_local_server_url()
            # Tile URL may be Docker when available, or local as fallback
            docker_url = get_tile_server_url()

            # Load buildings using shared method (DRY principle) - BEST PRACTICE!
            buildings_geojson = '{"type":"FeatureCollection","features":[]}'  # Default empty
            if self.db:
                logger.info("Loading buildings for map picker...")

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

                # 200 is sufficient for initial load with viewport loading
                buildings_geojson = self.load_buildings_geojson(self.db, limit=200, auth_token=auth_token)
            else:
                logger.warning("No database provided - map will not show existing buildings")

            # Always use polygon drawing mode (no points/pins)
            drawing_mode = 'polygon'

            # Convert existing polygon WKT to GeoJSON for display on map
            existing_polygons_geojson = self._wkt_to_geojson(self._existing_polygon_wkt)
            if self._existing_polygon_wkt:
                logger.info(f"Existing polygon WKT: {self._existing_polygon_wkt[:80]}...")
                logger.info(f"Converted to GeoJSON: {'YES' if existing_polygons_geojson else 'FAILED'}")
            else:
                logger.info("No existing polygon (new building)")

            # Generate map HTML using LeafletHTMLGenerator
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=self.initial_lat,
                center_lon=self.initial_lon,
                zoom=self.initial_zoom,
                min_zoom=15,
                max_zoom=20,
                show_legend=True,
                show_layer_control=False,
                enable_selection=False,
                enable_drawing=True,
                drawing_mode=drawing_mode,
                existing_polygons_geojson=existing_polygons_geojson,
                initial_bounds=self.initial_bounds,
                neighborhoods_geojson=self.neighborhoods_geojson,
                selected_neighborhood_code=self.selected_neighborhood_code,
                skip_fit_bounds=self._skip_fit_bounds,
                tile_layer_url=docker_url
            )

            # Load into web view
            self.load_map_html(html)

            logger.info(f"Map picker loaded (mode: {drawing_mode})")

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            from ui.error_handler import ErrorHandler
            ErrorHandler.show_error(
                self,
                f"حدث خطأ أثناء تحميل الخريطة:\n{str(e)}",
                "خطأ"
            )

    def _on_geometry_selected(self, geom_type: str, wkt: str):
        """
        Handle geometry drawn (point or polygon).
        Store result but don't close - wait for user to click confirm.

        Args:
            geom_type: 'Point' or 'Polygon'
            wkt: WKT string (PostGIS-compatible)
        """
        logger.info(f"Geometry selected: {geom_type} - {wkt[:100] if wkt else 'None'}...")

        # Handle deletion (null/empty from JS)
        if not geom_type or not wkt:
            self._result = None
            logger.info("Geometry cleared (deleted by user)")
            return

        try:
            if geom_type == 'Point':
                # Parse point coordinates
                # Format: POINT(lon lat)
                coords = wkt.replace('POINT(', '').replace(')', '').strip()
                lon_str, lat_str = coords.split()
                lat = float(lat_str)
                lon = float(lon_str)

                self._result = {
                    'latitude': lat,
                    'longitude': lon,
                    'polygon_wkt': None
                }

                logger.info(f"Point selected: ({lat}, {lon}) - waiting for confirmation")
                # Don't auto-close - user must click confirm button

            elif geom_type == 'Polygon':
                # Parse polygon to get centroid for lat/lon
                # Format: POLYGON((lon1 lat1, lon2 lat2, ...))
                coords_str = wkt.replace('POLYGON((', '').replace('))', '').strip()
                pairs = coords_str.split(',')

                lats = []
                lons = []
                for pair in pairs:
                    parts = pair.strip().split()
                    if len(parts) == 2:
                        lons.append(float(parts[0]))
                        lats.append(float(parts[1]))

                # Calculate centroid
                if lats and lons:
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)

                    self._result = {
                        'latitude': center_lat,
                        'longitude': center_lon,
                        'polygon_wkt': wkt
                    }

                    logger.info(f"Polygon selected: centroid=({center_lat}, {center_lon}) - waiting for confirmation")
                    # Don't auto-close - user must click confirm button

        except Exception as e:
            logger.error(f"Error parsing geometry: {e}", exc_info=True)
            from ui.error_handler import ErrorHandler
            ErrorHandler.show_error(
                self,
                f"حدث خطأ أثناء معالجة الإحداثيات:\n{str(e)}",
                "خطأ"
            )

    @staticmethod
    def _wkt_to_geojson(geo_location: str) -> Optional[str]:
        """Convert geo_location (WKT or GeoJSON) to GeoJSON FeatureCollection for map display."""
        if not geo_location:
            return None

        try:
            import json
            import re

            geometry = None

            # Strategy 1: If it's already GeoJSON (starts with '{')
            if geo_location.strip().startswith('{'):
                parsed = json.loads(geo_location)
                if parsed.get('type') == 'Polygon':
                    geometry = parsed
                elif parsed.get('type') == 'Feature':
                    geometry = parsed.get('geometry')
                elif parsed.get('type') == 'FeatureCollection':
                    # Already a FeatureCollection - return as-is
                    logger.info("Existing polygon is already GeoJSON FeatureCollection")
                    return geo_location

            # Strategy 2: WKT format - use regex (same as GeoJSONConverter)
            if not geometry and 'POLYGON' in geo_location.upper():
                match = re.search(r'POLYGON\s*\(\s*\((.*?)\)\s*\)', geo_location, re.IGNORECASE)
                if match:
                    coords_str = match.group(1)
                    coordinates = []
                    for pair in coords_str.split(','):
                        parts = pair.strip().split()
                        if len(parts) >= 2:
                            coordinates.append([float(parts[0]), float(parts[1])])

                    if len(coordinates) >= 3:
                        geometry = {
                            "type": "Polygon",
                            "coordinates": [coordinates]
                        }

            if not geometry:
                logger.warning(f"Could not parse geo_location: {geo_location[:80]}...")
                return None

            # Wrap in FeatureCollection
            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {
                        "building_id": "existing",
                        "building_id_display": "المضلع الحالي",
                        "status": "existing"
                    },
                    "geometry": geometry
                }]
            }
            coords_count = len(geometry.get('coordinates', [[]])[0])
            result = json.dumps(geojson)
            logger.info(f"Converted existing polygon to GeoJSON ({coords_count} points)")
            return result

        except Exception as e:
            logger.warning(f"Failed to convert geo_location to GeoJSON: {e}")
            return None

    def get_result(self) -> Optional[Dict]:
        """
        Get selected location/polygon result.

        Returns:
            Dict with 'latitude', 'longitude', and optional 'polygon_wkt'
            or None if cancelled
        """
        return self._result


def show_map_picker_dialog(
    initial_lat: float = 36.2021,
    initial_lon: float = 37.1343,
    allow_polygon: bool = True,
    db = None,
    parent=None
) -> Optional[Dict]:
    """
    Convenience function to show map picker dialog.

    Args:
        initial_lat: Initial map center latitude
        initial_lon: Initial map center longitude
        allow_polygon: Allow polygon drawing
        db: Database instance (REQUIRED for showing buildings - BEST PRACTICE!)
        parent: Parent widget

    Returns:
        Dict with location/polygon, or None if cancelled
    """
    dialog = MapPickerDialog(
        initial_lat=initial_lat,
        initial_lon=initial_lon,
        allow_polygon=allow_polygon,
        db=db,
        parent=parent
    )
    result = dialog.exec_()

    if result == dialog.Accepted:
        return dialog.get_result()

    return None
