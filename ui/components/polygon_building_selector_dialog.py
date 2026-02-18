# -*- coding: utf-8 -*-
"""
Polygon Building Selector Dialog.

Allows user to draw a polygon on the map and select buildings within it.
Integrates PolygonEditorWidget with PostGIS spatial queries.

Usage:
    dialog = PolygonBuildingSelectorDialog(db, parent)
    buildings = dialog.exec_and_get_buildings()
    if buildings:
        # User selected buildings within drawn polygon
"""

from typing import List, Optional
import json

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox,
    QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSlot

from ui.components.polygon_editor_widget import PolygonEditorWidget
from services.geometry_validation_service import GeometryValidationService
from services.postgis_service import PostGISService, SQLiteSpatialService
from models.building import Building
from repositories.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class PolygonBuildingSelectorDialog(QDialog):
    """
    Dialog for selecting buildings by drawing a polygon on the map.

    Features:
    - Interactive polygon drawing with Leaflet.draw
    - Real-time building count as polygon is drawn
    - List of buildings within polygon
    - Spatial validation (area, self-intersection)
    - Support for both PostGIS and SQLite spatial queries
    """

    def __init__(self, db: Database, parent=None):
        """
        Initialize the dialog.

        Args:
            db: Database instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.db = db
        self.selected_buildings: List[Building] = []

        # Initialize services
        self.geometry_validator = GeometryValidationService()
        self.spatial_service = self._init_spatial_service()

        self._setup_ui()
        self._connect_signals()

    def _init_spatial_service(self):
        """Initialize spatial service (PostGIS or SQLite fallback)."""
        try:
            # Try PostGIS first
            postgis = PostGISService()
            if postgis.connect():
                logger.info("Using PostGIS for spatial queries")
                return postgis
        except Exception as e:
            logger.warning(f"PostGIS not available: {e}")

        # Fallback to SQLite spatial
        logger.info("Using SQLite spatial fallback")
        return SQLiteSpatialService(self.db.get_connection())

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("تحديد المباني بالمضلع - Polygon Building Selection")
        self.setMinimumSize(1000, 700)
        self.setLayoutDirection(Qt.RightToLeft)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # ===== Instructions =====
        instructions = QLabel(
            "ارسم مضلعاً على الخريطة لتحديد المباني داخل المنطقة\n"
            "Draw a polygon on the map to select buildings within the area"
        )
        instructions.setStyleSheet("""
            QLabel {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                color: #2C3E50;
                padding: 8px;
                background-color: #EEF6FF;
                border: 1px solid #D1E8FF;
                border-radius: 8px;
            }
        """)
        instructions.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(instructions)

        # ===== Polygon Editor =====
        editor_group = QGroupBox("محرر المضلع - Polygon Editor")
        editor_group.setStyleSheet("""
            QGroupBox {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                font-weight: 600;
                color: #1F2D3D;
                border: 2px solid #E1E8ED;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                background-color: white;
            }
        """)

        editor_layout = QVBoxLayout(editor_group)
        editor_layout.setContentsMargins(8, 8, 8, 8)

        # Polygon editor widget
        self.polygon_editor = PolygonEditorWidget(self)
        self.polygon_editor.setMinimumHeight(400)
        editor_layout.addWidget(self.polygon_editor)

        main_layout.addWidget(editor_group)

        # ===== Buildings List =====
        buildings_group = QGroupBox("المباني المحددة - Selected Buildings")
        buildings_group.setStyleSheet("""
            QGroupBox {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                font-weight: 600;
                color: #1F2D3D;
                border: 2px solid #E1E8ED;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                background-color: white;
            }
        """)

        buildings_layout = QVBoxLayout(buildings_group)
        buildings_layout.setContentsMargins(8, 8, 8, 8)

        # Status label
        self.status_label = QLabel("لم يتم رسم مضلع بعد - No polygon drawn yet")
        self.status_label.setStyleSheet("""
            QLabel {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                color: #7F8C9B;
                padding: 6px;
            }
        """)
        buildings_layout.addWidget(self.status_label)

        # Buildings list
        self.buildings_list = QListWidget()
        self.buildings_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                background-color: #FAFBFC;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #EFF6FF;
                color: #2C3E50;
            }
        """)
        self.buildings_list.setMaximumHeight(150)
        buildings_layout.addWidget(self.buildings_list)

        main_layout.addWidget(buildings_group)

        # ===== Buttons =====
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.select_btn = QPushButton("✓ تحديد المباني - Select Buildings")
        self.select_btn.setEnabled(False)
        self.select_btn.setMinimumHeight(40)
        self.select_btn.setStyleSheet("""
            QPushButton {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                font-weight: 600;
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #2E7BC6;
            }
            QPushButton:disabled {
                background-color: #D1E8FF;
                color: #A0B4C6;
            }
        """)
        self.select_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("✕ إلغاء - Cancel")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                font-weight: 600;
                background-color: #F1F5F9;
                color: #64748B;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #E8EFF6;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.select_btn)

        main_layout.addLayout(buttons_layout)

    def _connect_signals(self):
        """Connect widget signals."""
        self.polygon_editor.polygon_changed.connect(self._on_polygon_changed)
        self.polygon_editor.area_changed.connect(self._on_area_changed)

    @pyqtSlot(str)
    def _on_polygon_changed(self, geojson_str: str):
        """
        Handle polygon change event.

        Validates the polygon and queries buildings within it.
        """
        logger.info("Polygon changed, querying buildings...")

        try:
            # Parse GeoJSON
            geojson = json.loads(geojson_str)

            # Convert to WKT for PostGIS
            wkt = self._geojson_to_wkt(geojson)

            if not wkt:
                self._clear_buildings()
                return

            # Validate polygon
            from services.map_service import GeoPolygon
            polygon_coords = geojson['geometry']['coordinates']
            geo_polygon = GeoPolygon(coordinates=polygon_coords)

            validation_result = self.geometry_validator.validate_polygon(
                geo_polygon,
                check_self_intersection=True
            )

            if not validation_result.is_valid:
                error_msg = "\n".join(validation_result.errors)
                self.status_label.setText(f"❌ مضلع غير صالح: {error_msg}")
                self.status_label.setStyleSheet("QLabel { color: #DC2626; }")
                self._clear_buildings()
                return

            # Query buildings
            buildings = self._query_buildings_in_polygon(wkt)

            # Update UI
            self._update_buildings_list(buildings)

        except Exception as e:
            logger.error(f"Error processing polygon: {e}", exc_info=True)
            self.status_label.setText(f"❌ خطأ: {str(e)}")
            self._clear_buildings()

    @pyqtSlot(float)
    def _on_area_changed(self, area_sqm: float):
        """Handle area change event."""
        # Area is shown in the polygon editor status bar
        pass

    def _geojson_to_wkt(self, geojson: dict) -> Optional[str]:
        """
        Convert GeoJSON to WKT format.

        Args:
            geojson: GeoJSON dict

        Returns:
            WKT string or None
        """
        try:
            geometry = geojson.get('geometry', {})
            geom_type = geometry.get('type', '')
            coords = geometry.get('coordinates', [])

            if geom_type == 'Polygon' and coords:
                # coords is list of rings, first ring is exterior
                exterior_ring = coords[0]

                # Format as WKT: POLYGON((lon lat, lon lat, ...))
                points = [f"{lon} {lat}" for lon, lat in exterior_ring]
                wkt = f"POLYGON(({', '.join(points)}))"

                return wkt

            return None

        except Exception as e:
            logger.error(f"Error converting GeoJSON to WKT: {e}")
            return None

    def _query_buildings_in_polygon(self, polygon_wkt: str) -> List[Building]:
        """
        Query buildings within polygon using spatial service.

        Args:
            polygon_wkt: Polygon WKT string

        Returns:
            List of Building objects
        """
        try:
            if isinstance(self.spatial_service, PostGISService):
                # Use PostGIS
                results = self.spatial_service.find_buildings_in_polygon(polygon_wkt)

                # Convert to Building objects
                buildings = []
                for result in results:
                    props = result.properties if hasattr(result, 'properties') else {}
                    building = Building(
                        building_uuid=result.feature_id,
                        building_id=props.get('building_id', ''),
                        governorate_code=props.get('governorate_code', ''),
                        district_code=props.get('district_code', ''),
                        subdistrict_code=props.get('subdistrict_code', ''),
                        community_code=props.get('community_code', ''),
                        neighborhood_code=props.get('neighborhood_code', ''),
                        building_number=props.get('building_number', ''),
                        building_type=props.get('building_type'),
                        building_status=props.get('building_status')
                    )
                    buildings.append(building)

                # Resolve address names from JSON files
                self._resolve_buildings_address_names(buildings)
                return buildings

            else:
                # Use SQLite spatial fallback
                # Parse WKT to polygon points
                import re
                match = re.search(r'POLYGON\(\((.*?)\)\)', polygon_wkt)
                if match:
                    points_str = match.group(1)
                    polygon_points = []
                    for point_str in points_str.split(','):
                        lon, lat = map(float, point_str.strip().split())
                        polygon_points.append((lon, lat))

                    results = self.spatial_service.find_buildings_in_polygon(polygon_points)

                    # Convert to Building objects
                    buildings = []
                    for result in results:
                        building = Building(
                            building_uuid=result['building_uuid'],
                            building_id=result['building_id'],
                            governorate_code=result.get('governorate_code', ''),
                            district_code=result.get('district_code', ''),
                            subdistrict_code=result.get('subdistrict_code', ''),
                            community_code=result.get('community_code', ''),
                            neighborhood_code=result.get('neighborhood_code', ''),
                            building_number=result.get('building_number', ''),
                            building_type=result.get('building_type'),
                            building_status=result.get('building_status')
                        )
                        buildings.append(building)

                    # Resolve address names from JSON files
                    self._resolve_buildings_address_names(buildings)
                    return buildings

            return []

        except Exception as e:
            logger.error(f"Error querying buildings: {e}", exc_info=True)
            return []

    def _resolve_buildings_address_names(self, buildings: List[Building]):
        """
        Resolve address names from codes using local JSON files.

        Extracts codes from building_id (17 digits: GG-DD-SS-CCC-NNN-BBBBB)
        then resolves names from administrative_divisions.json + neighborhoods.json.
        """
        from controllers.building_controller import BuildingController
        for b in buildings:
            # Extract codes from building_id if spatial query didn't return them
            bid = b.building_id or ""
            if len(bid) == 17 and bid.isdigit():
                b.governorate_code = b.governorate_code or bid[0:2]
                b.district_code = b.district_code or bid[2:4]
                b.subdistrict_code = b.subdistrict_code or bid[4:6]
                b.community_code = b.community_code or bid[6:9]
                b.neighborhood_code = b.neighborhood_code or bid[9:12]
                b.building_number = b.building_number or bid[12:17]

            # Always resolve names from JSON (override dataclass defaults)
            if b.governorate_code:
                resolved = BuildingController._resolve_admin_names(
                    b.governorate_code, b.district_code,
                    b.subdistrict_code, b.community_code
                )
                if resolved["governorate_name_ar"]:
                    b.governorate_name_ar = resolved["governorate_name_ar"]
                if resolved["district_name_ar"]:
                    b.district_name_ar = resolved["district_name_ar"]
                if resolved["subdistrict_name_ar"]:
                    b.subdistrict_name_ar = resolved["subdistrict_name_ar"]
                if resolved["community_name_ar"]:
                    b.community_name_ar = resolved["community_name_ar"]

            # Resolve neighborhood name from neighborhoods.json
            if b.neighborhood_code:
                name = BuildingController._get_neighborhood_name(b.neighborhood_code)
                if name and name != b.neighborhood_code:
                    b.neighborhood_name_ar = name

    def _update_buildings_list(self, buildings: List[Building]):
        """
        Update the buildings list widget.

        Args:
            buildings: List of Building objects
        """
        self.buildings_list.clear()
        self.selected_buildings = buildings

        if not buildings:
            self.status_label.setText("⚠️ لا توجد مباني في المنطقة المحددة")
            self.status_label.setStyleSheet("QLabel { color: #F59E0B; }")
            self.select_btn.setEnabled(False)
            return

        # Update status
        count = len(buildings)
        self.status_label.setText(f"✓ تم العثور على {count} مبنى في المنطقة")
        self.status_label.setStyleSheet("QLabel { color: #10B981; }")
        self.select_btn.setEnabled(True)

        # Add buildings to list
        for building in buildings:
            item_text = (
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display} | "
                f"الحالة: {building.building_status_display}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _clear_buildings(self):
        """Clear buildings list."""
        self.buildings_list.clear()
        self.selected_buildings = []
        self.select_btn.setEnabled(False)

    def exec_and_get_buildings(self) -> Optional[List[Building]]:
        """
        Execute dialog and return selected buildings.

        Returns:
            List of Building objects if user clicked Select, None if cancelled
        """
        result = self.exec_()

        if result == QDialog.Accepted and self.selected_buildings:
            return self.selected_buildings

        return None

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Clean up spatial service
        if isinstance(self.spatial_service, PostGISService):
            self.spatial_service.disconnect()

        super().closeEvent(event)
