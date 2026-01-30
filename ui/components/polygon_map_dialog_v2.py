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
from PyQt5.QtWidgets import QMessageBox, QPushButton, QHBoxLayout, QWidget
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
        self._building_id_to_building = {b.building_id: b for b in buildings}  # Quick lookup

        # Initialize base dialog with multi-select UI and confirm button
        super().__init__(
            title="اختيار المباني - رسم مضلع أو نقر مباشر",
            show_search=False,  # Polygon mode doesn't need search
            show_multiselect_ui=True,  # Enable multi-select UI
            show_confirm_button=False,  # We'll add custom confirm button
            parent=parent
        )

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
            QMessageBox.warning(
                self,
                "لا توجد مباني محددة",
                "الرجاء تحديد مباني أولاً (رسم مضلع أو نقر مباشر)"
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
            # Enable both polygon drawing AND multi-select clicking
            html = generate_leaflet_html(
                tile_server_url=tile_server_url.rstrip('/'),
                buildings_geojson=buildings_geojson,
                center_lat=36.2021,
                center_lon=37.1343,
                zoom=13,
                show_legend=True,
                show_layer_control=False,
                enable_selection=False,  # No popup selection button
                enable_multiselect=True,  # Enable multi-select clicking mode
                enable_drawing=True,  # Enable polygon drawing
                drawing_mode='polygon'  # Only polygon drawing (not point markers)
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

                # Enable confirm button
                if hasattr(self, 'confirm_selection_btn'):
                    self.confirm_selection_btn.setEnabled(True)

                # Don't auto-close - let user confirm
                QMessageBox.information(
                    self,
                    "تم العثور على مباني",
                    f"تم العثور على {count} مبنى في المضلع\n\nاضغط 'تأكيد الاختيار' لإتمام العملية"
                )
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

            buildings_in_polygon = []

            for building in self.buildings:
                # Skip buildings without coordinates
                if not building.latitude or not building.longitude:
                    continue

                try:
                    # Check if building point is within polygon
                    point = GeoPoint(latitude=building.latitude, longitude=building.longitude)
                    is_inside = map_service._point_in_polygon(point, polygon)

                    if is_inside:
                        buildings_in_polygon.append(building)

                except Exception as e:
                    logger.warning(f"Error checking building {building.building_id}: {e}")
                    continue

            return buildings_in_polygon

        except Exception as e:
            logger.error(f"Error in _query_buildings_in_polygon: {e}", exc_info=True)
            return []

    def _on_buildings_clicked(self, building_ids: List[str]):
        """
        Handle buildings selected by clicking directly on map.

        Args:
            building_ids: List of building IDs selected by clicking
        """
        logger.info(f"Buildings clicked: {building_ids}")

        # Convert building IDs to Building objects
        selected_buildings = []
        for building_id in building_ids:
            building = self._building_id_to_building.get(building_id)
            if building:
                selected_buildings.append(building)
            else:
                logger.warning(f"Building ID {building_id} not found in buildings list")

        # Update selected buildings
        self._selected_buildings = selected_buildings

        # Enable/disable confirm button based on selection
        if hasattr(self, 'confirm_selection_btn'):
            self.confirm_selection_btn.setEnabled(len(self._selected_buildings) > 0)

        logger.info(f"Selected {len(self._selected_buildings)} buildings via clicking")

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
