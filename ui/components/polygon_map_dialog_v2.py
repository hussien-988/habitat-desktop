# -*- coding: utf-8 -*-
"""
Polygon Map Dialog V2 - Unified Design for Polygon Selection.

Matches BuildingMapWidget design exactly - DRY principle.

Uses:
- BaseMapDialog for consistent UI
- LeafletHTMLGenerator for map rendering
- Leaflet.draw for polygon drawing tools
- PostGIS-compatible WKT output

Best Practices (DRY + SOLID):
- Extends BaseMapDialog (no duplication)
- Single Responsibility: Select buildings in polygon
- Open/Closed: Extended BaseMapDialog, not modified
"""

from typing import List, Optional
from PyQt5.QtWidgets import QMessageBox

from repositories.database import Database
from models.building import Building
from ui.components.base_map_dialog import BaseMapDialog
from services.leaflet_html_generator import generate_leaflet_html
from services.geojson_converter import GeoJSONConverter
from utils.logger import get_logger

logger = get_logger(__name__)


class PolygonMapDialog(BaseMapDialog):
    """
    Dialog for selecting multiple buildings by drawing polygon.

    Design matches BuildingMapWidget exactly.

    Returns:
        List[Building]: Buildings within drawn polygon
    """

    def __init__(self, db: Database, buildings: List[Building], parent=None):
        """
        Initialize polygon map dialog.

        Args:
            db: Database instance
            buildings: All buildings to display on map
            parent: Parent widget
        """
        self.db = db
        self.buildings = buildings
        self._selected_buildings = []

        # Initialize base dialog
        # No search bar for polygon selection (different from building selection)
        super().__init__(
            title="اختيار المباني - رسم مضلع",
            show_search=False,  # Polygon mode doesn't need search
            parent=parent
        )

        # Connect geometry signal
        self.geometry_selected.connect(self._on_geometry_selected)

        # Load map
        self._load_map()

    def _load_map(self):
        """Load map with buildings and polygon drawing tools."""
        from services.tile_server_manager import get_tile_server_url

        try:
            # Get tile server URL
            tile_server_url = get_tile_server_url()

            # Convert buildings to GeoJSON
            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                self.buildings,
                prefer_polygons=True
            )

            # Generate map HTML using LeafletHTMLGenerator
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=36.2021,
                center_lon=37.1343,
                zoom=13,
                show_legend=True,
                show_layer_control=False,
                enable_selection=False,  # No building selection popup
                enable_drawing=True  # Enable polygon drawing
            )

            # Load into web view
            self.load_map_html(html)

            logger.info(f"Loaded {len(self.buildings)} buildings into polygon map")

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء تحميل الخريطة:\n{str(e)}"
            )

    def _on_geometry_selected(self, geom_type: str, wkt: str):
        """
        Handle polygon drawn - query buildings within polygon.

        Args:
            geom_type: Geometry type ('Polygon')
            wkt: WKT string (PostGIS-compatible)
        """
        logger.info(f"Polygon drawn: {wkt[:100]}...")

        try:
            # Query buildings within polygon
            self._selected_buildings = self._query_buildings_in_polygon(wkt)

            if self._selected_buildings:
                count = len(self._selected_buildings)
                logger.info(f"Found {count} buildings in polygon")

                # Close dialog and add buildings (no confirmation message needed)
                self.accept()
            else:
                logger.warning("No buildings found in polygon")
                QMessageBox.warning(
                    self,
                    "لا توجد مباني",
                    "المضلع المرسوم لا يحتوي على أي مباني\n"
                    "The drawn polygon contains no buildings\n\n"
                    "الرجاء رسم مضلع يحتوي على مباني"
                )
                # Don't close - let user redraw

        except Exception as e:
            logger.error(f"Error querying buildings: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "خطأ",
                f"حدث خطأ أثناء البحث عن المباني:\n{str(e)}"
            )

    def _query_buildings_in_polygon(self, polygon_wkt: str) -> List[Building]:
        """
        Query buildings within polygon using point-in-polygon check.

        Args:
            polygon_wkt: WKT string (PostGIS-compatible)
                        Example: "POLYGON((lon1 lat1, lon2 lat2, ...))"

        Returns:
            List of buildings within polygon
        """
        from services.map_service import MapService

        map_service = MapService()
        buildings_in_polygon = []

        for building in self.buildings:
            # Skip buildings without coordinates
            if not building.latitude or not building.longitude:
                continue

            try:
                # Check if building point is within polygon
                is_inside = map_service.is_point_in_polygon(
                    building.latitude,
                    building.longitude,
                    polygon_wkt
                )

                if is_inside:
                    buildings_in_polygon.append(building)

            except Exception as e:
                logger.warning(f"Error checking building {building.building_id}: {e}")
                continue

        return buildings_in_polygon

    def get_selected_buildings(self) -> List[Building]:
        """
        Get selected buildings.

        Returns:
            List of buildings within drawn polygon
        """
        return self._selected_buildings


def show_polygon_map_dialog(
    db: Database,
    buildings: List[Building],
    parent=None
) -> Optional[List[Building]]:
    """
    Convenience function to show polygon map dialog.

    Args:
        db: Database instance
        buildings: All buildings to display
        parent: Parent widget

    Returns:
        List of selected buildings, or None if cancelled
    """
    dialog = PolygonMapDialog(db, buildings, parent)
    result = dialog.exec_()

    if result == dialog.Accepted:
        return dialog.get_selected_buildings()

    return None
