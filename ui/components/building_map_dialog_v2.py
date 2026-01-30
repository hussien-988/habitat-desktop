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
from repositories.building_repository import BuildingRepository
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
        self.building_repo = BuildingRepository(db)
        self._selected_building = None
        self._selected_building_id = selected_building_id
        self._is_view_only = bool(selected_building_id)

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
        super().__init__(
            title=title,
            show_search=show_search,
            parent=parent
        )

        # Connect building selection signal (from map clicks)
        self.building_selected.connect(self._on_building_selected_from_map)

        # Load map
        self._load_map()

    def _load_map(self):
        """Load map with buildings."""
        from services.tile_server_manager import get_tile_server_url

        try:
            # Get tile server URL
            tile_server_url = get_tile_server_url()

            # Get all buildings
            buildings = self.building_repo.get_all(limit=200)

            # Convert buildings to GeoJSON
            buildings_geojson = GeoJSONConverter.buildings_to_geojson(
                buildings,
                prefer_polygons=True
            )

            # Determine center and zoom
            center_lat = 36.2021
            center_lon = 37.1343
            zoom = 13
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
                    zoom = 16  # Closer zoom for single building
                    focus_building_id = self._selected_building_id
                    logger.info(f"View-only mode: Focusing on building {focus_building_id}")

            # Generate map HTML using LeafletHTMLGenerator
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=center_lat,
                center_lon=center_lon,
                zoom=zoom,
                show_legend=True,
                show_layer_control=False,
                enable_selection=(not self._is_view_only),  # Enable selection in selection mode
                enable_drawing=False  # No drawing for building selection
            )

            # Load into web view
            self.load_map_html(html)

            logger.info(f"Loaded {len(buildings)} buildings into map (mode: {'view' if self._is_view_only else 'select'})")

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
            building_id: Building ID clicked
        """
        logger.info(f"Building selected from map: {building_id}")

        try:
            # Find building in database
            building = self.building_repo.get_by_id(building_id)

            if building:
                self._selected_building = building

                # Close dialog and proceed to next step (no confirmation message needed)
                logger.info(f"Building {building.building_id} selected, closing dialog")
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
        """Handle search submission - search for neighborhood."""
        if not self.show_search or not hasattr(self, 'search_input'):
            return

        search_text = self.search_input.text().strip()

        if not search_text:
            logger.info("Search submitted but text is empty - ignoring")
            return

        logger.info(f"🔍 SEARCH TRIGGERED: '{search_text}'")

        try:
            buildings = self.building_repo.get_all(limit=500)
            logger.info(f"Loaded {len(buildings)} buildings for search")

            # Find buildings in matching neighborhoods
            matching_buildings = []

            for building in buildings:
                neighborhood_ar = (building.neighborhood_name_ar or "").lower()
                neighborhood_en = (building.neighborhood_name or "").lower()
                search_lower = search_text.lower()

                if search_lower in neighborhood_ar or search_lower in neighborhood_en:
                    matching_buildings.append(building)

            logger.info(f"Found {len(matching_buildings)} matching buildings")

            if matching_buildings:
                # Get center point of matching buildings
                lats = [b.latitude for b in matching_buildings if b.latitude]
                lons = [b.longitude for b in matching_buildings if b.longitude]

                if lats and lons:
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)

                    logger.info(f"Flying to center: ({center_lat}, {center_lon})")

                    # Fly to location on map
                    js_code = f"""
                    console.log('🔍 SEARCH: Flying to [{center_lat}, {center_lon}]');
                    if (typeof map !== 'undefined') {{
                        map.flyTo([{center_lat}, {center_lon}], 16, {{
                            duration: 2.0,
                            easeLinearity: 0.25
                        }});
                        console.log('✅ Map flyTo executed successfully');
                    }}
                    """
                    self.web_view.page().runJavaScript(js_code)

                    logger.info(f"✅ Search successful: {len(matching_buildings)} buildings")
            else:
                logger.warning(f"❌ No buildings found for neighborhood: '{search_text}'")

        except Exception as e:
            logger.error(f"❌ Error searching for neighborhood: {e}", exc_info=True)

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
