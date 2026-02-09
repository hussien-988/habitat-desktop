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
        initial_zoom: int = 13,
        allow_polygon: bool = True,
        db = None,
        parent=None
    ):
        """
        Initialize map picker dialog.

        Args:
            initial_lat: Initial map center latitude
            initial_lon: Initial map center longitude
            initial_zoom: Initial map zoom level (default: 13)
            allow_polygon: Allow polygon drawing (not just point)
            db: Database instance (optional, for loading buildings)
            parent: Parent widget
        """
        self.initial_lat = initial_lat
        self.initial_lon = initial_lon
        self.initial_zoom = initial_zoom
        self.allow_polygon = allow_polygon
        self.db = db
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
        from services.tile_server_manager import get_tile_server_url

        try:
            # Get tile server URL
            tile_server_url = get_tile_server_url()

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

                # ✅ OPTIMIZED: 200 is sufficient for initial load with viewport loading
                buildings_geojson = self.load_buildings_geojson(self.db, limit=200, auth_token=auth_token)
            else:
                logger.warning("No database provided - map will not show existing buildings")

            # Determine drawing mode
            drawing_mode = 'both' if self.allow_polygon else 'point'

            # Generate map HTML using LeafletHTMLGenerator
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,  # Now with buildings!
                center_lat=self.initial_lat,
                center_lon=self.initial_lon,
                zoom=self.initial_zoom,  # ✅ Smart zoom on neighborhood
                min_zoom=self.initial_zoom,  # ✅ "اجبرو بلا مايحس" - prevent zoom out!
                max_zoom=20,  #
                show_legend=True,  # Show legend for building status
                show_layer_control=False,
                enable_selection=False,  # Don't allow selecting buildings
                enable_drawing=True,  # Enable drawing tools
                drawing_mode=drawing_mode
            )

            # Load into web view
            self.load_map_html(html)

            logger.info(f"Map picker loaded (mode: {drawing_mode})")

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء تحميل الخريطة:\n{str(e)}"
            )

    def _on_geometry_selected(self, geom_type: str, wkt: str):
        """
        Handle geometry drawn (point or polygon).
        Store result but don't close - wait for user to click confirm.

        Args:
            geom_type: 'Point' or 'Polygon'
            wkt: WKT string (PostGIS-compatible)
        """
        logger.info(f"Geometry selected: {geom_type} - {wkt[:100]}...")

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
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء معالجة الإحداثيات:\n{str(e)}"
            )

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
    dialog = MapPickerDialog(initial_lat, initial_lon, allow_polygon, db, parent)
    result = dialog.exec_()

    if result == dialog.Accepted:
        return dialog.get_result()

    return None
