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
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QWidget
from ui.error_handler import ErrorHandler
from PyQt5.QtCore import Qt

from repositories.database import Database
from models.building import Building
from ui.components.base_map_dialog import BaseMapDialog
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
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

    def __init__(self, db: Database, auth_token: Optional[str] = None, parent=None):
        """
        Initialize polygon map dialog.

        ✅ BEST PRACTICE: Same as BuildingMapDialog (wizard) - NO buildings parameter!
        Buildings are loaded dynamically with viewport loading.

        Args:
            db: Database instance
            auth_token: Optional API authentication token (REQUIRED for BuildingAssignments API)
            parent: Parent widget
        """
        self.db = db
        self._selected_buildings = []
        self._building_id_to_building = {}  # Quick lookup (populated during selection)
        self.buildings = []  # ✅ FIX: Initialize buildings list for fallback method

        # ✅ CRITICAL FIX: Store auth_token BEFORE super().__init__ temporarily
        # We'll reassign after super().__init__ because BaseMapDialog.__init__ resets it to None!
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

        # Initialize base dialog with multi-select UI and confirm button
        super().__init__(
            title="اختيار المباني - رسم مضلع أو نقر مباشر",
            show_search=False,  # Polygon mode doesn't need search
            show_multiselect_ui=True,  # Enable multi-select UI
            show_confirm_button=False,  # We'll add custom confirm button
            enable_viewport_loading=True,  # ✅ Enable for proper QWebChannel initialization (like wizard)
            parent=parent
        )

        # ✅ CRITICAL FIX: Set auth_token AFTER super().__init__
        # BaseMapDialog.__init__ sets self._auth_token = None, so we must reassign here!
        self._auth_token = _temp_auth_token

        if self._auth_token:
            logger.info(f"✅ Auth token set for PolygonMapDialog (length: {len(self._auth_token)})")
        else:
            logger.warning("⚠️ No auth token - API calls will fail with 401!")

        # Connect signals
        self.geometry_selected.connect(self._on_geometry_selected)
        self.buildings_multiselected.connect(self._on_buildings_clicked)

        # Add custom confirm button for selected buildings
        self._add_confirm_button()

        # Load map
        self._load_map()

    def _add_confirm_button(self):
        """Add confirm button at the bottom of dialog."""
        from ui.design_system import Colors
        from ui.font_utils import create_font, FontManager

        # Find the main content widget
        if not hasattr(self, 'layout') or self.layout() is None:
            return

        # Create button container
        button_container = QWidget()
        button_container.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(24, 8, 24, 16)
        button_layout.setSpacing(12)
        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("✕ إلغاء")
        cancel_btn.setFixedSize(120, 40)
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
        self.confirm_selection_btn = QPushButton("✓ تأكيد الاختيار")
        self.confirm_selection_btn.setFixedSize(160, 40)
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
        self.confirm_selection_btn.setEnabled(False)  # Disabled until buildings selected
        self.confirm_selection_btn.clicked.connect(self._on_confirm_selection)
        button_layout.addWidget(self.confirm_selection_btn)

        button_layout.addStretch()

        # Add to main layout
        main_widget = self.findChild(QWidget)
        if main_widget and main_widget.layout():
            main_widget.layout().addWidget(button_container)

    def _on_confirm_selection(self):
        """Handle confirm button click."""
        if self._selected_buildings:
            logger.info(f"Confirmed selection of {len(self._selected_buildings)} buildings")
            # Explicitly cleanup overlay before accepting
            self._cleanup_overlay()
            self.accept()
        else:
            ErrorHandler.show_warning(
                self,
                "الرجاء تحديد مباني أولاً (رسم مضلع أو نقر مباشر)",
                "لا توجد مباني محددة"
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
        """
        Load map with polygon drawing tools.

        ✅ BEST PRACTICE: Same as BuildingMapDialog!
        - Start with EMPTY GeoJSON (fast loading!)
        - Buildings loaded dynamically via viewport loading
        - NO pre-loading of buildings
        """
        from services.tile_server_manager import get_tile_server_url

        try:
            # Get tile server URL
            tile_server_url = get_tile_server_url()

            # ✅ CRITICAL: Log auth token status
            if self._auth_token:
                logger.info(f"✅ _load_map: Auth token available (length: {len(self._auth_token)})")
            else:
                logger.error(f"❌ _load_map: NO AUTH TOKEN! Viewport loading will fail!")

            # ✅ FIX: Load 200 buildings initially (SAME AS WIZARD!)
            # This fixes QWebChannel bridge initialization issue
            buildings_geojson = self.load_buildings_geojson(self.db, limit=200, auth_token=self._auth_token)
            logger.info(f"🚀 Loading 200 buildings initially (like wizard) - more will load dynamically")

            # ✅ Generate map HTML using LeafletHTMLGenerator
            # SAME AS BuildingMapDialog but with polygon drawing enabled!
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=36.2021,
                center_lon=37.1343,
                zoom=15,  #
                max_zoom=20,  #
                show_legend=True,
                show_layer_control=False,
                enable_selection=False,  # No popup selection button
                enable_multiselect=True,  # Enable multi-select clicking mode
                enable_viewport_loading=True,  # ✅ CRITICAL: Enable viewport loading (SAME AS BuildingMapDialog!)
                enable_drawing=True,  # Enable polygon drawing
                drawing_mode='polygon'  # Only polygon drawing (not point markers)
            )

            # Load into web view
            self.load_map_html(html)

            logger.info(f"✅ Polygon map loaded with viewport loading enabled (FAST!)")

        except Exception as e:
            logger.error(f"Error loading map: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"حدث خطأ أثناء تحميل الخريطة:\n{str(e)}",
                "خطأ"
            )

    def _on_geometry_selected(self, geom_type: str, wkt: str):
        """
        Handle polygon drawn - query buildings within polygon.

        Args:
            geom_type: Geometry type ('Polygon')
            wkt: WKT string (PostGIS-compatible)
        """
        logger.info(f"🔔 _on_geometry_selected called!")
        logger.info(f"   geom_type: {geom_type}")
        logger.info(f"   wkt: {wkt[:100] if wkt else 'None'}...")

        try:
            # Query buildings within polygon using BuildingAssignments API
            self._selected_buildings = self._query_buildings_in_polygon(wkt)

            if self._selected_buildings:
                count = len(self._selected_buildings)
                logger.info(f"✅ Found {count} buildings in polygon")

                # ✅ SOLID: Single Responsibility - Extract building IDs
                building_ids = [b.building_id for b in self._selected_buildings]

                # ✅ DRY: Store building lookup (cache for fast access)
                for building in self._selected_buildings:
                    if building.building_id not in self._building_id_to_building:
                        self._building_id_to_building[building.building_id] = building

                # ✅ CRITICAL FIX: Update BaseMapDialog's selected_building_ids list
                # This is required for parent class methods to work correctly
                if not hasattr(self, '_selected_building_ids'):
                    self._selected_building_ids = []
                self._selected_building_ids = building_ids

                # ✅ DRY: Use parent class method to update buildings list UI
                # This populates the sidebar with building details
                self._update_buildings_list(building_ids)

                # ✅ Update counter display (uses parent class method)
                self._on_selection_count_updated(count)

                # ✅ Highlight selected buildings on map
                self._highlight_selected_buildings()

                # Enable confirm button
                if hasattr(self, 'confirm_selection_btn'):
                    self.confirm_selection_btn.setEnabled(True)
                    logger.info(f"✅ Confirm button enabled ({count} buildings selected)")

                # ✅ NO MESSAGE: Buildings are shown directly on map and in counter
                # User can see them highlighted on map and count in UI
                logger.info(f"✅ Found {count} buildings in polygon - shown on map")
            else:
                logger.warning("No buildings found in polygon")
                ErrorHandler.show_warning(
                    self,
                    "المضلع المرسوم لا يحتوي على أي مباني\n"
                    "The drawn polygon contains no buildings\n\n"
                    "الرجاء رسم مضلع يحتوي على مباني",
                    "لا توجد مباني"
                )
                # Don't close - let user redraw

        except Exception as e:
            logger.error(f"Error querying buildings: {e}", exc_info=True)
            ErrorHandler.show_error(
                self,
                f"حدث خطأ أثناء البحث عن المباني:\n{str(e)}",
                "خطأ"
            )

    def _query_buildings_in_polygon(self, polygon_wkt: str) -> List[Building]:
        """
        Query buildings within polygon using CORRECT BuildingAssignments API.

        ✅ BEST PRACTICE: Uses Backend PostGIS for fast spatial queries
        ✅ CORRECT API: /api/v1/BuildingAssignments/buildings/search

        Args:
            polygon_wkt: WKT string (PostGIS-compatible)
                        Example: "POLYGON((lon1 lat1, lon2 lat2, ...))"

        Returns:
            List of buildings within polygon
        """
        logger.info(f"🔍 _query_buildings_in_polygon called")
        logger.info(f"📐 FULL WKT STRING:")
        logger.info(f"   {polygon_wkt}")
        logger.info(f"   WKT length: {len(polygon_wkt) if polygon_wkt else 0} characters")
        logger.info(f"   Using BuildingAssignments API (PostGIS in Backend)")

        try:
            from services.api_client import get_api_client
            from models.building import Building

            # Get API client
            api_client = get_api_client()

            # ✅ CRITICAL: Set auth token before API call
            if hasattr(self, '_auth_token') and self._auth_token:
                api_client.set_access_token(self._auth_token)
                logger.debug("✅ Auth token set for BuildingAssignments API")
            else:
                logger.warning("⚠️ No auth token available - trying anyway")

            # ✅ CORRECT API: Search buildings for assignment using polygon
            # has_active_assignment=False means: only buildings without active assignment
            # has_active_assignment=None means: all buildings (assigned + unassigned)
            result = api_client.search_buildings_for_assignment(
                polygon_wkt=polygon_wkt,
                has_active_assignment=None,  # Get all buildings (we'll filter later if needed)
                page=1,
                page_size=10000  # Get all buildings in polygon (up to 10k)
            )

            # Extract buildings from API response
            buildings_data = result.get("items", [])
            total_count = result.get("totalCount", 0)
            polygon_area = result.get("polygonAreaSquareMeters", 0)

            logger.info(f"✅ BuildingAssignments API returned {len(buildings_data)} buildings")
            logger.info(f"   Total count: {total_count}")
            logger.info(f"   Polygon area: {polygon_area:.2f} m²")

            # Convert to Building objects
            buildings_in_polygon = []
            for i, building_data in enumerate(buildings_data):
                try:
                    # ✅ DEBUG: Log first building's raw data
                    if i == 0:
                        logger.info(f"🔍 First building raw data from API:")
                        logger.info(f"   Keys: {list(building_data.keys())[:10]}")
                        logger.info(f"   ID field: {building_data.get('id', 'N/A')}")
                        logger.info(f"   buildingCode field: {building_data.get('buildingCode', 'N/A')}")

                    building = Building.from_dict(building_data)
                    buildings_in_polygon.append(building)
                except Exception as e:
                    logger.warning(f"Failed to convert building: {e}")
                    continue

            logger.info(f"📊 Query results:")
            logger.info(f"   Total buildings in polygon: {len(buildings_in_polygon)}")

            return buildings_in_polygon

        except Exception as e:
            logger.error(f"Error querying BuildingAssignments API: {e}", exc_info=True)

            # ✅ FALLBACK: Use local point-in-polygon check if API fails
            logger.warning("⚠️ Falling back to local point-in-polygon check...")
            return self._query_buildings_in_polygon_local(polygon_wkt)

    def _query_buildings_in_polygon_local(self, polygon_wkt: str) -> List[Building]:
        """
        Fallback: Query buildings using local point-in-polygon check.

        Only used if BuildingAssignments API fails.
        """
        logger.info(f"🔄 Using fallback local point-in-polygon check")
        logger.info(f"   Total buildings to check: {len(self.buildings)}")

        try:
            from services.map_service import MapService, GeoPoint, GeoPolygon

            # Create MapService with database connection
            if not hasattr(self, 'db') or not self.db:
                logger.error("❌ Database connection not available")
                return []

            map_service = MapService(self.db.connection)
            polygon = GeoPolygon.from_wkt(polygon_wkt)

            if not polygon:
                logger.error(f"❌ Failed to parse polygon WKT: {polygon_wkt}")
                return []

            logger.info(f"✅ Polygon parsed successfully: {len(polygon.coordinates)} coordinates")

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
                        logger.debug(f"   ✅ Building {building.building_id} is inside polygon")

                except Exception as e:
                    logger.warning(f"Error checking building {building.building_id}: {e}")
                    continue

            logger.info(f"📊 Fallback query results:")
            logger.info(f"   Total checked: {checked_count}")
            logger.info(f"   Skipped (no coords): {skipped_count}")
            logger.info(f"   Found inside polygon: {len(buildings_in_polygon)}")

            return buildings_in_polygon

        except Exception as e:
            logger.error(f"Error in fallback query: {e}", exc_info=True)
            return []

    def _fetch_building_from_api(self, building_id: str) -> Optional[Building]:
        """
        Fetch single building using BuildingController (SAME AS POLYGON PATTERN).

        ✅ CORRECT: Uses BuildingController.get_building_by_id (API or DB)

        Args:
            building_id: Building ID to fetch (e.g., "01-01-01-001-001-00001")

        Returns:
            Building object if found, None otherwise
        """
        try:
            from controllers.building_controller import BuildingController

            # Create controller (will use API if available)
            controller = BuildingController(self.db)

            # Set auth token if available
            if hasattr(self, '_auth_token') and self._auth_token:
                controller.set_auth_token(self._auth_token)

            # ✅ Use get_building_by_id (searches in API/DB)
            result = controller.get_building_by_id(building_id)

            if result.success and result.data:
                logger.info(f"✅ Found building via controller: {building_id}")
                return result.data
            else:
                logger.warning(f"Building {building_id} not found: {result.message}")
                return None

        except Exception as e:
            logger.error(f"Error fetching building: {e}", exc_info=True)
            return None

    def _on_buildings_clicked(self, building_ids: List[str]):
        """
        Handle buildings selected by clicking directly on map.

        ✅ SAME AS POLYGON: If building not in cache, fetch from BuildingAssignments API!

        Args:
            building_ids: List of building IDs selected by clicking
        """
        logger.info(f"🖱️ Buildings clicked: {building_ids}")

        # Convert building IDs to Building objects
        selected_buildings = []
        for building_id in building_ids:
            building = self._building_id_to_building.get(building_id)

            if not building:
                # ✅ SAME AS POLYGON: Fetch from BuildingAssignments API
                logger.info(f"🔍 Building {building_id} not in cache - fetching from API...")
                building = self._fetch_building_from_api(building_id)

                if building:
                    # ✅ SAME AS POLYGON: Store in dictionary for future use
                    self._building_id_to_building[building.building_id] = building
                    logger.info(f"✅ Fetched and cached building {building_id}")
                else:
                    logger.warning(f"❌ Building {building_id} not found in API")
                    continue

            selected_buildings.append(building)

        # Update selected buildings
        self._selected_buildings = selected_buildings

        # Enable/disable confirm button based on selection
        if hasattr(self, 'confirm_selection_btn'):
            self.confirm_selection_btn.setEnabled(len(self._selected_buildings) > 0)

        logger.info(f"✅ Selected {len(self._selected_buildings)} buildings via clicking")

    def _highlight_selected_buildings(self):
        """
        Highlight selected buildings on map with blue color.

        ✅ Visual Feedback: Shows user which buildings are selected!
        """
        if not self._selected_buildings:
            return

        # Get building IDs
        building_ids = [b.building_id for b in self._selected_buildings]

        # JavaScript to highlight buildings
        js_code = f"""
        console.log('🎨 Highlighting {len(building_ids)} selected buildings...');

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
            console.log('✅ Highlighted ' + highlightedCount + ' buildings in blue');
        }} else {{
            console.warn('⚠️ buildingsLayer not found - cannot highlight buildings');
        }}
        """

        try:
            self.web_view.page().runJavaScript(js_code)
            logger.info(f"✅ Highlighted {len(building_ids)} buildings on map")
        except Exception as e:
            logger.warning(f"Failed to highlight buildings: {e}")

    def get_selected_buildings(self) -> List[Building]:
        """
        Get selected buildings.

        Returns:
            List of buildings within drawn polygon
        """
        logger.info(f"📤 get_selected_buildings() called")
        logger.info(f"   Returning {len(self._selected_buildings)} buildings")
        if self._selected_buildings:
            for i, bldg in enumerate(self._selected_buildings[:3]):  # Log first 3
                logger.info(f"   Building {i+1}: ID={bldg.building_id}")
        else:
            logger.warning("   ⚠️ No buildings selected!")
        return self._selected_buildings


def show_polygon_map_dialog(
    db: Database,
    auth_token: Optional[str] = None,
    parent=None
) -> Optional[List[Building]]:
    """
    Convenience function to show polygon map dialog.

    ✅ BEST PRACTICE: Same signature as wizard - NO buildings parameter!
    Buildings are loaded dynamically with viewport loading for fast performance.

    Args:
        db: Database instance
        auth_token: Optional API authentication token (REQUIRED for BuildingAssignments API)
        parent: Parent widget

    Returns:
        List of selected buildings, or None if cancelled
    """
    logger.info("🗺️ show_polygon_map_dialog() called")
    dialog = PolygonMapDialog(db, auth_token, parent)
    result = dialog.exec_()

    logger.info(f"📋 Dialog result: {'Accepted' if result == dialog.Accepted else 'Rejected/Cancelled'}")

    if result == dialog.Accepted:
        selected = dialog.get_selected_buildings()
        logger.info(f"✅ Returning {len(selected) if selected else 0} buildings to parent")
        return selected
    else:
        logger.info("❌ User cancelled - returning None")

    return None
