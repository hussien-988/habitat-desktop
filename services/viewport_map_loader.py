    # -*- coding: utf-8 -*-
"""
    Viewport-Based Map Loader Service
    ==================================

    Professional service for loading buildings based on map viewport.
    Optimized for performance with millions of buildings.

    Features:
    - Smart caching + debouncing
    - Reusable across all map components
    - Works with millions of buildings

    Usage:
    loader = ViewportMapLoader(map_service_api)
    buildings = loader.load_buildings_for_viewport(
        north_east_lat=36.5,
        north_east_lng=37.5,
        south_west_lat=36.0,
        south_west_lng=36.8
    )
"""

from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib

from models.building import Building
from services.map_service_api import MapServiceAPI
from services.building_cache_service import BuildingCacheService, get_building_cache
from services.spatial_sampler import SpatialSampler
from services.api_client import get_api_client
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ViewportBounds:
    """Viewport bounding box."""
    north_east_lat: float
    north_east_lng: float
    south_west_lat: float
    south_west_lng: float

    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to tuple for easy comparison."""
        return (
            self.north_east_lat,
            self.north_east_lng,
            self.south_west_lat,
            self.south_west_lng
        )

    def get_cache_key(self) -> str:
        """Generate cache key (2 decimals ~1.1km — allows small pans to hit cache)."""
        rounded = tuple(round(x, 2) for x in self.to_tuple())
        key_str = f"{rounded[0]}_{rounded[1]}_{rounded[2]}_{rounded[3]}"
        # MD5 is fine here: the digest is only used as a viewport-cache key,
        # never a security primitive. ``usedforsecurity=False`` documents the
        # intent and silences static analysers (e.g. bandit B324).
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def area_size(self) -> float:
        """Calculate approximate area size (for cache expiry logic)."""
        lat_diff = abs(self.north_east_lat - self.south_west_lat)
        lng_diff = abs(self.north_east_lng - self.south_west_lng)
        return lat_diff * lng_diff


@dataclass
class CachedViewportData:
    """Cached viewport data with metadata."""
    bounds: ViewportBounds
    buildings: List[Building]
    loaded_at: datetime
    hit_count: int = 0

    def is_expired(self, max_age_minutes: int = 10) -> bool:
        """Check if cache is expired."""
        age = datetime.now() - self.loaded_at
        return age > timedelta(minutes=max_age_minutes)


class ViewportMapLoader:
    """
    Service for loading buildings based on map viewport.

    Features:
    - Smart caching (LRU with expiry)
    - Debouncing support
    - Performance optimized for millions of buildings
    """

    def __init__(
        self,
        map_service: Optional[MapServiceAPI] = None,
        cache_enabled: bool = True,
        cache_max_size: int = 50,
        cache_max_age_minutes: int = 10,
        building_cache_service: Optional[BuildingCacheService] = None,
        use_spatial_sampling: bool = True,
        db=None
    ):
        """
        Initialize viewport loader.

        Args:
            map_service: MapServiceAPI instance (creates if not provided)
            cache_enabled: Enable smart caching
            cache_max_size: Maximum cache entries (LRU)
            cache_max_age_minutes: Cache expiry time
            building_cache_service: Optional BuildingCacheService (uses singleton if not provided)
            use_spatial_sampling: Enable grid-based spatial sampling
            db: Database instance for local fallback when API unavailable
        """
        self.map_service = map_service or MapServiceAPI()
        self.db = db
        self.cache_enabled = cache_enabled
        self.cache_max_size = cache_max_size
        self.cache_max_age_minutes = cache_max_age_minutes
        self.use_spatial_sampling = use_spatial_sampling

        # Use application-wide cache service (singleton)
        self.building_cache = building_cache_service

        # Fallback to local cache if building_cache not available
        self._cache: Dict[str, CachedViewportData] = {}

        logger.info(
            f"ViewportMapLoader initialized "
            f"(cache: {cache_enabled}, spatial_sampling: {use_spatial_sampling})"
        )

    def load_buildings_for_viewport(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        zoom_level: Optional[int] = None,
        status_filter: Optional[str] = None,
        force_refresh: bool = False,
        min_zoom_threshold: int = 15,
        max_markers: int = 1000,
        auth_token: Optional[str] = None
    ) -> List[Building]:
        """
        Load buildings for viewport with professional optimizations.

        Optimizations:
            - Application-wide cache (Singleton BuildingCacheService)
            - Spatial sampling (grid-based even distribution)
            - Zoom-adaptive density (20-100 buildings based on zoom)
            - Min zoom threshold (prevent loading at low zoom)
            - Priority-based sampling (prefer damaged buildings)

        Args:
            north_east_lat: NE latitude
            north_east_lng: NE longitude
            south_west_lat: SW latitude
            south_west_lng: SW longitude
            zoom_level: Current map zoom level
            status_filter: Optional building status filter
            force_refresh: Bypass cache and force API call
            min_zoom_threshold: Minimum zoom level to load buildings (default: 12)
            max_markers: Maximum markers per viewport (default: 1000)
            auth_token: Optional authentication token for API

        Returns:
            List of buildings (spatially sampled for optimal performance)
        """
        # Min zoom check: prevent loading buildings when zoomed out too far
        if zoom_level is not None and zoom_level < min_zoom_threshold:
            logger.debug(f"Zoom {zoom_level} < {min_zoom_threshold}, skipping building load")
            return []

        try:
            # PROFESSIONAL FIX: Update auth token BEFORE any API calls (prevent 401!)
            # Must be done BEFORE cache check, because cache miss will trigger API call
            if auth_token:
                self.map_service.set_auth_token(auth_token)
                logger.debug("Auth token synchronized with MapServiceAPI (before cache check)")

            buildings = []

            bounds = ViewportBounds(
                north_east_lat=north_east_lat,
                north_east_lng=north_east_lng,
                south_west_lat=south_west_lat,
                south_west_lng=south_west_lng
            )

            if self.cache_enabled and not force_refresh:
                cached = self._get_from_cache(bounds)
                if cached:
                    buildings = cached.buildings
                    logger.debug(f"Loaded {len(buildings)} buildings from viewport cache")
                else:
                    buildings = self.map_service.get_buildings_in_bbox(
                        north_east_lat=north_east_lat,
                        north_east_lng=north_east_lng,
                        south_west_lat=south_west_lat,
                        south_west_lng=south_west_lng,
                        page_size=max_markers
                    )
                    self._store_in_cache(bounds, buildings)
                    logger.debug(f"Loaded {len(buildings)} buildings for viewport")
            else:
                buildings = self.map_service.get_buildings_in_bbox(
                    north_east_lat=north_east_lat,
                    north_east_lng=north_east_lng,
                    south_west_lat=south_west_lat,
                    south_west_lng=south_west_lng,
                    page_size=max_markers
                )
                logger.debug(f"Loaded {len(buildings)} buildings for viewport (no cache)")

            # Spatial Sampling — only when buildings exceed the display limit.
            # SpatialSampler._create_grid skips buildings with no direct lat/lng
            # (only geo_location WKT), so bypassing it for small datasets prevents
            # silently dropping most buildings.
            if self.use_spatial_sampling and zoom_level is not None and len(buildings) > max_markers:
                sampled_buildings = SpatialSampler.sample_buildings(
                    buildings=buildings,
                    north_east_lat=north_east_lat,
                    north_east_lng=north_east_lng,
                    south_west_lat=south_west_lat,
                    south_west_lng=south_west_lng,
                    zoom_level=zoom_level,
                    use_priority=True
                )
                return sampled_buildings
            else:
                return buildings[:max_markers]

        except Exception as e:
            logger.error(f"Error loading buildings for viewport: {e}", exc_info=True)
            return []

    def _get_from_cache(self, bounds: ViewportBounds) -> Optional[CachedViewportData]:
        """Get cached data for viewport (with expiry check)."""
        cache_key = bounds.get_cache_key()

        if cache_key not in self._cache:
            return None

        cached = self._cache[cache_key]

        # Check expiry
        if cached.is_expired(self.cache_max_age_minutes):
            del self._cache[cache_key]
            return None

        # Increment hit count
        cached.hit_count += 1
        return cached

    def _store_in_cache(self, bounds: ViewportBounds, buildings: List[Building]):
        """Store viewport data in cache (with LRU eviction)."""
        cache_key = bounds.get_cache_key()

        # LRU eviction: remove oldest/least-used entries if cache full
        if len(self._cache) >= self.cache_max_size:
            self._evict_lru()

        # Store new entry
        self._cache[cache_key] = CachedViewportData(
            bounds=bounds,
            buildings=buildings,
            loaded_at=datetime.now(),
            hit_count=0
        )

    def _evict_lru(self):
        """Evict least recently used cache entry."""
        if not self._cache:
            return

        # Find entry with lowest hit count (LRU)
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)
        del self._cache[lru_key]

    def clear_cache(self):
        """Clear all cached viewport data."""
        self._cache.clear()
        logger.info("Viewport cache cleared")

    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics."""
        return {
            "enabled": self.cache_enabled,
            "entries": len(self._cache),
            "max_size": self.cache_max_size,
            "max_age_minutes": self.cache_max_age_minutes,
            "total_buildings_cached": sum(len(c.buildings) for c in self._cache.values())
        }

    def _dto_to_building(self, dto: dict) -> Building:
        """Convert BuildingAssignments API DTO to Building for map display."""
        building = Building(
            building_id=dto.get("buildingCode", ""),
            building_uuid=dto.get("id", ""),
            building_type=dto.get("buildingType"),
            building_status=dto.get("buildingStatus") or dto.get("status", 1),
            latitude=dto.get("latitude"),
            longitude=dto.get("longitude"),
            number_of_units=dto.get("numberOfPropertyUnits", 0),
            is_assigned=dto.get("hasActiveAssignment", False),
            is_locked=dto.get("isLocked", False),
        )
        building.has_active_assignment = dto.get("hasActiveAssignment", False)
        return building


# ─── Session-level singleton registry (persists for the entire app session) ───
_viewport_loaders: Dict[str, 'ViewportMapLoader'] = {}


def get_shared_viewport_loader(
    provider_key: str,
    map_service=None,
    cache_max_age_minutes: int = 30,
) -> 'ViewportMapLoader':
    """
    Return a shared ViewportMapLoader for the given provider type.
    The cache persists for the entire app session — reopening the map dialog
    reuses the same loader and serves cached viewport data instantly.

    Args:
        provider_key: Unique key per data provider type (e.g. class name).
        map_service: MapServiceAPI instance with updated auth token.
        cache_max_age_minutes: Cache TTL (default 30 min for session cache).
    """
    global _viewport_loaders
    if provider_key not in _viewport_loaders:
        _viewport_loaders[provider_key] = ViewportMapLoader(
            map_service=map_service,
            cache_enabled=True,
            cache_max_size=100,
            cache_max_age_minutes=cache_max_age_minutes,
            use_spatial_sampling=False,
        )
        logger.info(f"Session ViewportMapLoader created for provider: {provider_key}")
    else:
        if map_service:
            _viewport_loaders[provider_key].map_service = map_service
    return _viewport_loaders[provider_key]
