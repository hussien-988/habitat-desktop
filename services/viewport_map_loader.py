# -*- coding: utf-8 -*-
"""
    Viewport-Based Map Loader Service
    ==================================

    Loads buildings for the visible map area through a fixed grid of cells.

    Features:
    - Only requests the cells that are not cached yet
    - Pan-back and small moves are served from memory
    - Failed requests are never cached, so an area can't stay empty after an error
    - Views with too many buildings for pins use per-cell building counts instead

    Usage:
    loader = ViewportMapLoader(map_service_api)
    buildings = loader.load_buildings_for_viewport(
        north_east_lat=36.5,
        north_east_lng=37.5,
        south_west_lat=36.0,
        south_west_lng=36.8
    )
"""

import math
from threading import Lock
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from models.building import Building
from services.map_data_provider import MapBounds
from services.map_service_api import MapServiceAPI
from utils.logger import get_logger

logger = get_logger(__name__)

Cell = Tuple[int, int]

# ~550m x ~450m at Aleppo's latitude: small enough that a dense area stays close to the view
CELL_SIZE_DEGREES = 0.005
# Backend limit for one Buildings/map request
MAX_BUILDINGS_PER_REQUEST = 50000
# Screen size of one count bubble
GRID_CELL_PIXELS = 80
# Most pins one view may hold; stays smooth in map rendering measurements
MAX_PINS_PER_VIEW = 3000
# From this zoom a view is small enough to always show pins
ALWAYS_PINS_ZOOM = 18
# Backend bounds for map requests (Syria)
MIN_LAT, MAX_LAT = 32.0, 37.5
MIN_LNG, MAX_LNG = 36.0, 42.5


@dataclass
class CachedCell:
    """Buildings of one grid cell, keyed by building ID."""
    loaded_at: datetime
    buildings: Dict[str, Building] = field(default_factory=dict)

    def is_expired(self, max_age_minutes: int) -> bool:
        return datetime.now() - self.loaded_at > timedelta(minutes=max_age_minutes)


class ViewportMapLoader:
    """Loads and caches buildings per grid cell for the visible map area."""

    def __init__(
        self,
        map_service: Optional[MapServiceAPI] = None,
        cache_max_size: int = 20000,
        cache_max_age_minutes: int = 5,
        db=None
    ):
        """
        Initialize viewport loader.

        Args:
            map_service: MapServiceAPI instance (creates if not provided)
            cache_max_size: Maximum cached cells
            cache_max_age_minutes: Cell lifetime
            db: Database instance
        """
        self.map_service = map_service or MapServiceAPI()
        self.db = db
        self.cache_max_size = cache_max_size
        self.cache_max_age_minutes = cache_max_age_minutes
        self._cells: Dict[Cell, CachedCell] = {}
        self._lock = Lock()

    @staticmethod
    def _cell_of(lat: float, lng: float) -> Cell:
        return (math.floor(lat / CELL_SIZE_DEGREES), math.floor(lng / CELL_SIZE_DEGREES))

    def _cells_in_bounds(self, north_east_lat, north_east_lng, south_west_lat, south_west_lng) -> Set[Cell]:
        min_row, min_col = self._cell_of(south_west_lat, south_west_lng)
        max_row, max_col = self._cell_of(north_east_lat, north_east_lng)
        return {
            (row, col)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        }

    def load_viewport(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        zoom_level: int,
        auth_token: Optional[str] = None
    ) -> Tuple[List[Building], Optional[List[Dict]]]:
        """
        Load the map content for a viewport.

        Returns (buildings, None) for pins, or ([], cells) when the view holds too
        many buildings and should show per-cell counts. Raises on API failure, so
        the caller can report it and the area stays uncached.
        """
        if auth_token:
            self.map_service.set_auth_token(auth_token)

        wanted = self._cells_in_bounds(north_east_lat, north_east_lng, south_west_lat, south_west_lng)

        with self._lock:
            missing = {
                cell for cell in wanted
                if cell not in self._cells
                or self._cells[cell].is_expired(self.cache_max_age_minutes)
            }

        if missing and zoom_level < ALWAYS_PINS_ZOOM:
            cells = self._load_grid(
                north_east_lat, north_east_lng, south_west_lat, south_west_lng, zoom_level
            )
            if sum(cell.get("count", 0) for cell in cells) > MAX_PINS_PER_VIEW:
                return [], cells

        fetched: List[Building] = self._fetch_cells(missing) if missing else []

        result = {b.building_id: b for b in fetched}
        with self._lock:
            for cell in wanted:
                cached = self._cells.get(cell)
                if cached:
                    result.update(cached.buildings)

        logger.debug(
            f"Viewport: {len(wanted)} cells, {len(missing)} fetched, {len(result)} buildings"
        )
        return list(result.values()), None

    def _fetch_cells(self, cells: Set[Cell]) -> List[Building]:
        """Fetch the area covering `cells` once and store its buildings per cell."""
        rows = [row for row, _ in cells]
        cols = [col for _, col in cells]
        min_row, max_row, min_col, max_col = min(rows), max(rows), min(cols), max(cols)

        bounds = MapBounds(
            min_lat=min_row * CELL_SIZE_DEGREES,
            max_lat=(max_row + 1) * CELL_SIZE_DEGREES,
            min_lng=min_col * CELL_SIZE_DEGREES,
            max_lng=(max_col + 1) * CELL_SIZE_DEGREES,
        )
        buildings = self.map_service.load_viewport_buildings(bounds, MAX_BUILDINGS_PER_REQUEST)
        if len(buildings) >= MAX_BUILDINGS_PER_REQUEST:
            logger.warning(f"Map request reached the {MAX_BUILDINGS_PER_REQUEST} building limit")

        now = datetime.now()
        covered = {
            (row, col)
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        }
        with self._lock:
            for cell in covered:
                self._cells[cell] = CachedCell(loaded_at=now)
            for building in buildings:
                if building.latitude is None or building.longitude is None:
                    continue
                cached = self._cells.get(self._cell_of(float(building.latitude), float(building.longitude)))
                if cached:
                    cached.buildings[building.building_id] = building
            self._evict_oldest()
        return buildings

    def _evict_oldest(self):
        """Keep the cache within its size limit. Caller holds the lock."""
        excess = len(self._cells) - self.cache_max_size
        if excess <= 0:
            return
        oldest = sorted(self._cells, key=lambda cell: self._cells[cell].loaded_at)[:excess]
        for cell in oldest:
            del self._cells[cell]

    def _load_grid(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        zoom_level: int
    ) -> List[Dict]:
        """
        Return building counts per grid cell for a view.

        The area is snapped to whole cells, so a cell at the screen edge is counted in full.
        """
        cell_size = GRID_CELL_PIXELS * 360 / (256 * 2 ** zoom_level)
        bounds = MapBounds(
            min_lat=max(MIN_LAT, math.floor(south_west_lat / cell_size) * cell_size),
            max_lat=min(MAX_LAT, math.ceil(north_east_lat / cell_size) * cell_size),
            min_lng=max(MIN_LNG, math.floor(south_west_lng / cell_size) * cell_size),
            max_lng=min(MAX_LNG, math.ceil(north_east_lng / cell_size) * cell_size),
        )
        if bounds.min_lat >= bounds.max_lat or bounds.min_lng >= bounds.max_lng:
            return []
        return self.map_service.load_building_grid(bounds, cell_size)

    def clear_cache(self):
        """Clear all cached cells."""
        with self._lock:
            self._cells.clear()
        logger.info("Viewport cache cleared")


# ─── Session-level singleton registry (persists for the entire app session) ───
_viewport_loaders: Dict[str, 'ViewportMapLoader'] = {}


def get_shared_viewport_loader(
    provider_key: str,
    map_service=None,
) -> 'ViewportMapLoader':
    """
    Return a shared ViewportMapLoader for the given provider type.

    Args:
        provider_key: Unique key per data provider type (e.g. class name).
        map_service: MapServiceAPI instance with updated auth token.
    """
    global _viewport_loaders
    if provider_key not in _viewport_loaders:
        _viewport_loaders[provider_key] = ViewportMapLoader(map_service=map_service)
        logger.info(f"Session ViewportMapLoader created for provider: {provider_key}")
    else:
        if map_service:
            _viewport_loaders[provider_key].map_service = map_service
    return _viewport_loaders[provider_key]


def clear_all_shared_viewport_loaders() -> None:
    """Clear viewport caches across every shared loader. Used on server switch
    so the previous server's buildings cannot surface in the new server's UI.
    """
    global _viewport_loaders
    for key, loader in list(_viewport_loaders.items()):
        try:
            loader.clear_cache()
        except Exception:
            pass
    logger.info(f"Cleared viewport caches across {len(_viewport_loaders)} shared loader(s)")
