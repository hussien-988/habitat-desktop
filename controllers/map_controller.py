# -*- coding: utf-8 -*-
"""
Map Controller
==============
Controller for map and GIS operations.

Handles:
- Map layer management
- Spatial queries
- Geometry operations
- GPS integration
- GeoJSON export/import
- Coordinate validation
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from repositories.database import Database
from services.map_service import MapService, GeoPoint, GeoPolygon, BuildingGeoData
from services.map_service_api import MapServiceAPI
from services.gps_service import GPSService, GPSPosition, GPSConfig, GPSStatus
from utils.logger import get_logger
from app.config import Config

logger = get_logger(__name__)


@dataclass
class MapFilter:
    """Filter for map queries."""
    bbox_min_lat: Optional[float] = None
    bbox_min_lng: Optional[float] = None
    bbox_max_lat: Optional[float] = None
    bbox_max_lng: Optional[float] = None
    neighborhood_code: Optional[str] = None
    building_status: Optional[str] = None
    has_claims: Optional[bool] = None
    layer: str = "buildings"


@dataclass
class MapState:
    """Current state of the map."""
    center_lat: float = 36.2
    center_lng: float = 37.15
    zoom: int = 15  #
    active_layers: List[str] = None
    selected_feature_id: Optional[str] = None
    drawing_mode: Optional[str] = None  # None, 'point', 'polygon'

    def __post_init__(self):
        if self.active_layers is None:
            self.active_layers = ["buildings"]


class MapController(BaseController):
    """
    Controller for map and GIS operations.

    Provides a clean interface for map-related functionality.
    """

    # Signals
    map_loaded = pyqtSignal()
    layer_toggled = pyqtSignal(str, bool)  # layer_name, visible
    feature_selected = pyqtSignal(str, str)  # layer, feature_id
    feature_deselected = pyqtSignal()
    coordinate_picked = pyqtSignal(float, float)  # lat, lng
    polygon_drawn = pyqtSignal(list)  # list of [lat, lng]
    gps_position_updated = pyqtSignal(object)  # GPSPosition
    gps_status_changed = pyqtSignal(str)  # status
    buildings_in_view = pyqtSignal(list)  # list of BuildingGeoData

    # Map bounds for Iraq/Syria (Aleppo region)
    DEFAULT_BOUNDS = {
        "min_lat": 36.0,
        "max_lat": 36.5,
        "min_lng": 36.8,
        "max_lng": 37.5
    }

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

        # Initialize map service based on configuration (API or local)
        if Config.DATA_PROVIDER == "http":  # API mode
            try:
                self.map_service = MapServiceAPI()
                logger.info("✅ MapController initialized in API mode")
            except Exception as e:
                logger.error(f"❌ Failed to initialize MapServiceAPI: {e}")
                logger.warning("Falling back to local database mode")
                self.map_service = MapService(db)
        else:
            self.map_service = MapService(db)
            logger.info("MapController initialized in local database mode")

        self.gps_service: Optional[GPSService] = None

        self._state = MapState()
        self._cached_features: Dict[str, List[BuildingGeoData]] = {}

    # ==================== Properties ====================

    @property
    def state(self) -> MapState:
        """Get current map state."""
        return self._state

    @property
    def center(self) -> Tuple[float, float]:
        """Get map center (lat, lng)."""
        return (self._state.center_lat, self._state.center_lng)

    @property
    def zoom(self) -> int:
        """Get map zoom level."""
        return self._state.zoom

    @property
    def active_layers(self) -> List[str]:
        """Get active layer names."""
        return self._state.active_layers

    @property
    def is_gps_connected(self) -> bool:
        """Check if GPS is connected."""
        return self.gps_service is not None and self.gps_service.is_connected()

    @property
    def current_gps_position(self) -> Optional[GPSPosition]:
        """Get current GPS position."""
        return self.gps_service.get_current_position() if self.gps_service else None

    # ==================== Map State ====================

    def set_center(self, lat: float, lng: float, zoom: Optional[int] = None) -> OperationResult:
        """
        Set map center.

        Args:
            lat: Latitude
            lng: Longitude
            zoom: Optional zoom level

        Returns:
            OperationResult
        """
        # Validate coordinates
        if not self._validate_coordinates(lat, lng):
            return OperationResult.fail(
                message="Invalid coordinates",
                message_ar="إحداثيات غير صالحة"
            )

        self._state.center_lat = lat
        self._state.center_lng = lng
        if zoom is not None:
            self._state.zoom = zoom

        self._trigger_callbacks("on_center_changed", lat, lng, zoom)
        return OperationResult.ok()

    def set_zoom(self, zoom: int) -> OperationResult:
        """
        Set map zoom level.

        Args:
            zoom: Zoom level (1-20)

        Returns:
            OperationResult
        """
        if not 1 <= zoom <= 20:
            return OperationResult.fail(message="Invalid zoom level")

        self._state.zoom = zoom
        self._trigger_callbacks("on_zoom_changed", zoom)
        return OperationResult.ok()

    def pan_to_building(self, building_uuid: str) -> OperationResult:
        """
        Pan map to a building.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult
        """
        try:
            building = self.map_service.get_building_location(building_uuid)

            if not building:
                return OperationResult.fail(
                    message="Building not found",
                    message_ar="المبنى غير موجود"
                )

            # Get center point
            if building.point:
                lat, lng = building.point.latitude, building.point.longitude
            elif building.polygon:
                centroid = building.polygon.get_centroid()
                lat, lng = centroid.latitude, centroid.longitude
            else:
                return OperationResult.fail(
                    message="Building has no geometry",
                    message_ar="المبنى ليس له إحداثيات"
                )

            return self.set_center(lat, lng, zoom=17)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Layer Management ====================

    def toggle_layer(self, layer_name: str, visible: bool) -> OperationResult:
        """
        Toggle layer visibility.

        Args:
            layer_name: Name of layer
            visible: Whether layer should be visible

        Returns:
            OperationResult
        """
        if visible:
            if layer_name not in self._state.active_layers:
                self._state.active_layers.append(layer_name)
        else:
            if layer_name in self._state.active_layers:
                self._state.active_layers.remove(layer_name)

        self.layer_toggled.emit(layer_name, visible)
        self._trigger_callbacks("on_layer_toggled", layer_name, visible)
        return OperationResult.ok()

    def get_available_layers(self) -> List[Dict[str, Any]]:
        """Get list of available map layers."""
        return [
            {
                "name": "buildings",
                "title": "Buildings",
                "title_ar": "المباني",
                "type": "polygon",
                "default_visible": True
            },
            {
                "name": "claims",
                "title": "Claims",
                "title_ar": "المطالبات",
                "type": "point",
                "default_visible": False
            },
            {
                "name": "damage",
                "title": "Damage Assessment",
                "title_ar": "تقييم الأضرار",
                "type": "point",
                "default_visible": False
            },
            {
                "name": "heatmap",
                "title": "Density Heatmap",
                "title_ar": "خريطة الكثافة",
                "type": "heatmap",
                "default_visible": False
            }
        ]

    # ==================== Feature Selection ====================

    def select_feature(self, layer: str, feature_id: str) -> OperationResult:
        """
        Select a feature on the map.

        Args:
            layer: Layer name
            feature_id: Feature ID (UUID)

        Returns:
            OperationResult with feature data
        """
        self._state.selected_feature_id = feature_id

        self.feature_selected.emit(layer, feature_id)
        self._trigger_callbacks("on_feature_selected", layer, feature_id)

        # Get feature details
        if layer == "buildings":
            building = self.map_service.get_building_location(feature_id)
            return OperationResult.ok(data=building)

        return OperationResult.ok()

    def deselect_feature(self):
        """Clear feature selection."""
        self._state.selected_feature_id = None
        self.feature_deselected.emit()
        self._trigger_callbacks("on_feature_deselected")

    # ==================== Spatial Queries ====================

    def get_buildings_in_view(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        page_size: int = 2000,
        zoom_level: Optional[int] = None
    ) -> OperationResult[List[BuildingGeoData]]:
        """
        Get buildings visible in current map view.

        Args:
            bbox: Optional bounding box (min_lat, min_lng, max_lat, max_lng)
            page_size: Maximum buildings to load (default: 2000) ✅ محسّن للأداء
            zoom_level: Optional zoom level for optimization

        Returns:
            OperationResult with list of BuildingGeoData
        """
        try:
            self._emit_started("get_buildings_in_view")

            if bbox:
                min_lat, min_lng, max_lat, max_lng = bbox
            else:
                # Calculate bbox from current view
                lat_range = 0.01 * (20 - self._state.zoom)
                lng_range = 0.01 * (20 - self._state.zoom)
                min_lat = self._state.center_lat - lat_range
                max_lat = self._state.center_lat + lat_range
                min_lng = self._state.center_lng - lng_range
                max_lng = self._state.center_lng + lng_range

            zoom = zoom_level if zoom_level is not None else self._state.zoom

            # Query buildings with optimized parameters
            # ✅ استخدام MapServiceAPI إذا كان مُفعّل (يدعم page_size)
            if isinstance(self.map_service, MapServiceAPI):
                # Use API optimized method with page_size
                buildings = self.map_service.get_buildings_in_bbox_optimized(
                    north_east_lat=max_lat,
                    north_east_lng=max_lng,
                    south_west_lat=min_lat,
                    south_west_lng=min_lng,
                    page_size=page_size,
                    zoom_level=zoom
                )
                # Convert Building to BuildingGeoData
                buildings_geodata = [self._building_to_geodata(b) for b in buildings]
            else:
                # Fallback: Use local MapService
                polygon = GeoPolygon(coordinates=[[
                    (min_lng, min_lat),
                    (max_lng, min_lat),
                    (max_lng, max_lat),
                    (min_lng, max_lat),
                    (min_lng, min_lat)
                ]])
                buildings_geodata = self.map_service.search_buildings_in_polygon(polygon)

            self._cached_features["buildings"] = buildings_geodata
            self._emit_completed("get_buildings_in_view", True)
            self.buildings_in_view.emit(buildings_geodata)

            logger.info(f"✅ Loaded {len(buildings_geodata)} buildings (page_size={page_size}, zoom={zoom})")
            return OperationResult.ok(data=buildings_geodata)

        except Exception as e:
            logger.error(f"❌ Error getting buildings in view: {e}")
            self._emit_error("get_buildings_in_view", str(e))
            return OperationResult.fail(message=str(e))

    def _building_to_geodata(self, building) -> BuildingGeoData:
        """Convert Building model to BuildingGeoData."""
        point = None
        polygon = None

        if building.latitude and building.longitude:
            point = GeoPoint(
                latitude=building.latitude,
                longitude=building.longitude
            )

        if building.geo_location and 'POLYGON' in building.geo_location.upper():
            try:
                polygon = GeoPolygon.from_wkt(building.geo_location)
            except:
                pass

        return BuildingGeoData(
            building_uuid=building.building_uuid,
            building_id=building.building_id,
            geometry_type="polygon" if polygon else "point",
            point=point,
            polygon=polygon,
            neighborhood_code=getattr(building, 'neighborhood_code', ''),
            status=building.building_status or '',
            building_type=building.building_type or '',
            properties={
                "number_of_units": building.number_of_units or 0
            }
        )

    def search_buildings_by_radius(
        self,
        center_lat: float,
        center_lng: float,
        radius_meters: float
    ) -> OperationResult[List[BuildingGeoData]]:
        """
        Search buildings within radius of a point.

        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            radius_meters: Search radius in meters

        Returns:
            OperationResult with list of BuildingGeoData
        """
        try:
            center = GeoPoint(latitude=center_lat, longitude=center_lng)
            buildings = self.map_service.search_buildings_by_location(center, radius_meters)
            return OperationResult.ok(data=buildings)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def search_buildings_in_polygon(
        self,
        polygon_points: List[Tuple[float, float]]
    ) -> OperationResult[List[BuildingGeoData]]:
        """
        Search buildings within a polygon.

        Args:
            polygon_points: List of (lng, lat) tuples

        Returns:
            OperationResult with list of BuildingGeoData
        """
        try:
            polygon = GeoPolygon(coordinates=[polygon_points])
            buildings = self.map_service.search_buildings_in_polygon(polygon)
            return OperationResult.ok(data=buildings)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def check_proximity(
        self,
        building1_uuid: str,
        building2_uuid: str
    ) -> OperationResult[Dict[str, Any]]:
        """
        Check proximity between two buildings.

        Args:
            building1_uuid: First building UUID
            building2_uuid: Second building UUID

        Returns:
            OperationResult with proximity data
        """
        try:
            result = self.map_service.check_proximity_overlap(building1_uuid, building2_uuid)
            return OperationResult.ok(data=result)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Coordinate Picking ====================

    def set_drawing_mode(self, mode: Optional[str]) -> OperationResult:
        """
        Set drawing mode.

        Args:
            mode: 'point', 'polygon', or None to disable

        Returns:
            OperationResult
        """
        if mode not in [None, "point", "polygon"]:
            return OperationResult.fail(message="Invalid drawing mode")

        self._state.drawing_mode = mode
        self._trigger_callbacks("on_drawing_mode_changed", mode)
        return OperationResult.ok()

    def handle_coordinate_picked(self, lat: float, lng: float):
        """
        Handle coordinate picked from map.

        Args:
            lat: Latitude
            lng: Longitude
        """
        if not self._validate_coordinates(lat, lng):
            logger.warning(f"Invalid coordinates picked: {lat}, {lng}")
            return

        self.coordinate_picked.emit(lat, lng)
        self._trigger_callbacks("on_coordinate_picked", lat, lng)

    def handle_polygon_drawn(self, points: List[List[float]]):
        """
        Handle polygon drawn on map.

        Args:
            points: List of [lat, lng] pairs
        """
        self.polygon_drawn.emit(points)
        self._trigger_callbacks("on_polygon_drawn", points)

    # ==================== Geometry Operations ====================

    def update_building_geometry(
        self,
        building_uuid: str,
        point: Optional[GeoPoint] = None,
        polygon: Optional[GeoPolygon] = None,
        user_id: Optional[str] = None
    ) -> OperationResult[bool]:
        """
        Update building geometry.

        Args:
            building_uuid: Building UUID
            point: Optional point geometry
            polygon: Optional polygon geometry
            user_id: User making the change

        Returns:
            OperationResult with success status
        """
        try:
            self._emit_started("update_building_geometry")

            success = self.map_service.update_building_geometry(
                building_uuid, point, polygon, user_id
            )

            if success:
                self._emit_completed("update_building_geometry", True)
                self._trigger_callbacks("on_geometry_updated", building_uuid)
                return OperationResult.ok(
                    data=True,
                    message="Geometry updated successfully",
                    message_ar="تم تحديث الموقع بنجاح"
                )
            else:
                self._emit_error("update_building_geometry", "Failed to update geometry")
                return OperationResult.fail(message="Failed to update geometry")

        except Exception as e:
            self._emit_error("update_building_geometry", str(e))
            return OperationResult.fail(message=str(e))

    def validate_coordinates(
        self,
        lat: float,
        lng: float
    ) -> OperationResult[Tuple[bool, str]]:
        """
        Validate coordinates.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            OperationResult with (is_valid, message)
        """
        is_valid, message = self.map_service.validate_coordinates(lat, lng)
        return OperationResult.ok(data=(is_valid, message))

    def _validate_coordinates(self, lat: float, lng: float) -> bool:
        """Internal coordinate validation."""
        return -90 <= lat <= 90 and -180 <= lng <= 180

    # ==================== GPS Integration ====================

    def connect_gps(self, config: Optional[GPSConfig] = None) -> OperationResult[bool]:
        """
        Connect to GPS device.

        Args:
            config: Optional GPS configuration

        Returns:
            OperationResult with success status
        """
        try:
            self._emit_started("connect_gps")

            self.gps_service = GPSService(config)

            # Register callbacks
            self.gps_service.add_position_callback(self._on_gps_position)
            self.gps_service.add_status_callback(self._on_gps_status)

            success = self.gps_service.connect()

            if success:
                self._emit_completed("connect_gps", True)
                return OperationResult.ok(
                    data=True,
                    message="GPS connected",
                    message_ar="تم الاتصال بـ GPS"
                )
            else:
                self._emit_error("connect_gps", "Failed to connect GPS")
                return OperationResult.fail(message="Failed to connect GPS")

        except Exception as e:
            self._emit_error("connect_gps", str(e))
            return OperationResult.fail(message=str(e))

    def disconnect_gps(self):
        """Disconnect from GPS device."""
        if self.gps_service:
            self.gps_service.disconnect()
            self.gps_service = None
            self.gps_status_changed.emit("disconnected")

    def get_gps_position(self) -> OperationResult[GPSPosition]:
        """
        Get current GPS position.

        Returns:
            OperationResult with GPSPosition
        """
        if not self.gps_service:
            return OperationResult.fail(
                message="GPS not connected",
                message_ar="GPS غير متصل"
            )

        position = self.gps_service.get_current_position()

        if position:
            return OperationResult.ok(data=position)
        else:
            return OperationResult.fail(
                message="No GPS fix",
                message_ar="لا يوجد إشارة GPS"
            )

    def pan_to_gps_location(self) -> OperationResult:
        """Pan map to current GPS location."""
        result = self.get_gps_position()

        if result.success:
            position = result.data
            return self.set_center(position.latitude, position.longitude, zoom=17)

        return result

    def _on_gps_position(self, position: GPSPosition):
        """Handle GPS position update."""
        self.gps_position_updated.emit(position)
        self._trigger_callbacks("on_gps_position", position)

    def _on_gps_status(self, status: GPSStatus):
        """Handle GPS status change."""
        self.gps_status_changed.emit(status.value)
        self._trigger_callbacks("on_gps_status", status)

    # ==================== Export ====================

    def export_to_geojson(
        self,
        filter_: Optional[MapFilter] = None,
        file_path: Optional[str] = None
    ) -> OperationResult[Dict]:
        """
        Export map data to GeoJSON.

        Args:
            filter_: Optional filter
            file_path: Optional file path to save

        Returns:
            OperationResult with GeoJSON data
        """
        try:
            buildings = self._cached_features.get("buildings", [])

            if not buildings:
                # Load buildings if not cached
                result = self.get_buildings_in_view()
                if result.success:
                    buildings = result.data

            geojson = self.map_service.export_to_geojson(buildings)

            if file_path:
                import json
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(geojson, f, ensure_ascii=False, indent=2)

            return OperationResult.ok(data=geojson)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_claims_geojson(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> OperationResult[Dict]:
        """
        Get claims as GeoJSON.

        Args:
            filters: Optional filters

        Returns:
            OperationResult with GeoJSON data
        """
        try:
            geojson = self.map_service.get_claims_geojson(filters)
            return OperationResult.ok(data=geojson)

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_heatmap_data(self) -> OperationResult[List[Dict]]:
        """
        Get heatmap data.

        Returns:
            OperationResult with heatmap points
        """
        try:
            data = self.map_service.get_density_heatmap_data()
            return OperationResult.ok(data=data)

        except Exception as e:
            return OperationResult.fail(message=str(e))
