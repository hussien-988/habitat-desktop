# -*- coding: utf-8 -*-
"""
Building Cache Service - Application-Wide Singleton Cache
==========================================================

Professional caching solution for building data across the entire application.

Best Practices Applied:
- Singleton Pattern (one instance per application)
- LRU Cache (Least Recently Used eviction)
- Spatial Indexing (fast viewport queries)
- Thread-Safe operations
- Progressive loading strategy

References:
- https://realpython.com/lru-cache-python/
- https://dev.to/mustafaelghrib/how-to-implement-a-cache-manager-with-the-singleton-pattern-using-python-5635
- https://github.com/jazzycamel/PyQt5Singleton

Architecture:
    Application Startup:
        ↓
    Load 150 buildings (initial cache)
        ↓
    Store in LRU Cache (maxsize=1000)
        ↓
    Map requests buildings for viewport
        ↓
    Cache hit? → Return from cache (FAST!)
    Cache miss? → Load from API/DB → Cache it
"""

from typing import List, Optional, Dict, Tuple
from functools import lru_cache
from threading import Lock
from datetime import datetime, timedelta

from models.building import Building
from repositories.database import Database
from controllers.building_controller import BuildingController, BuildingFilter
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingCacheServiceMeta(type):
    """
    Thread-safe Singleton metaclass for BuildingCacheService.

    Ensures only one instance exists across the entire application.
    Professional Best Practice for PyQt5 applications.
    """
    _instances: Dict[type, 'BuildingCacheService'] = {}
    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        """Thread-safe singleton instantiation."""
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class BuildingCacheService(metaclass=BuildingCacheServiceMeta):
    """
    Application-wide building cache service (Singleton).

    Features:
    - LRU Cache with configurable size (default: 1000 buildings)
    - Spatial indexing for fast viewport queries
    - Progressive loading (load small set on startup, more on demand)
    - Thread-safe operations
    - Cache invalidation support

    Usage:
        # Get singleton instance
        cache = BuildingCacheService.get_instance(db)

        # Get buildings for viewport
        buildings = cache.get_buildings_for_viewport(
            north_east_lat=36.25,
            north_east_lng=37.18,
            south_west_lat=36.20,
            south_west_lng=37.13
        )
    """

    # Configuration (Best Practices)
    INITIAL_CACHE_SIZE = 150      # Load on startup (fast startup!)
    MAX_CACHE_SIZE = 1000         # LRU eviction beyond this
    CACHE_TTL_HOURS = 24          # Cache invalidation time

    _instance: Optional['BuildingCacheService'] = None

    def __init__(self, db: Database):
        """
        Initialize cache service (called only once - Singleton).

        Args:
            db: Database instance
        """
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.db = db
        self.building_controller = BuildingController(db)

        # Cache storage
        self._cache: Dict[str, Building] = {}  # building_id -> Building
        self._spatial_index: Dict[Tuple[int, int], List[str]] = {}  # (lat_grid, lon_grid) -> [building_ids]
        self._cache_timestamp = datetime.now()
        self._lock = Lock()

        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0

        # Mark as initialized
        self._initialized = True

        logger.info("BuildingCacheService initialized (Singleton)")

    @classmethod
    def get_instance(cls, db: Database = None) -> 'BuildingCacheService':
        """
        Get singleton instance of BuildingCacheService.

        Args:
            db: Database instance (required on first call)

        Returns:
            Singleton instance
        """
        if cls._instance is None:
            if db is None:
                raise ValueError("Database instance required for first initialization")
            cls._instance = cls(db)
        return cls._instance

    def initialize_cache(self, auth_token: Optional[str] = None) -> bool:
        """
        Initialize cache with initial building set.

        Loads INITIAL_CACHE_SIZE buildings to warm up the cache.
        Called during application startup.

        Args:
            auth_token: Optional authentication token for API

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Initializing cache with {self.INITIAL_CACHE_SIZE} buildings...")

            # Set auth token if provided
            if auth_token and self.building_controller.is_using_api:
                self.building_controller.set_auth_token(auth_token)

            # Load initial buildings
            building_filter = BuildingFilter(limit=self.INITIAL_CACHE_SIZE)
            result = self.building_controller.load_buildings(building_filter)

            if not result.success:
                logger.error(f"Failed to initialize cache: {result.message}")
                return False

            buildings = result.data

            # Populate cache
            with self._lock:
                for building in buildings:
                    self._add_to_cache(building)

            logger.info(f"✅ Cache initialized with {len(buildings)} buildings")
            logger.info(f"   Cache stats: {self.get_cache_stats()}")
            return True

        except Exception as e:
            logger.error(f"Error initializing cache: {e}", exc_info=True)
            return False

    def _add_to_cache(self, building: Building):
        """
        Add building to cache and spatial index.

        Thread-safe internal method.

        Args:
            building: Building object to cache
        """
        # Add to main cache
        self._cache[building.building_id] = building

        # Add to spatial index (grid-based)
        if building.latitude and building.longitude:
            grid_key = self._get_grid_key(building.latitude, building.longitude)
            if grid_key not in self._spatial_index:
                self._spatial_index[grid_key] = []
            if building.building_id not in self._spatial_index[grid_key]:
                self._spatial_index[grid_key].append(building.building_id)

        # LRU eviction if cache too large
        if len(self._cache) > self.MAX_CACHE_SIZE:
            self._evict_lru()

    def _get_grid_key(self, lat: float, lon: float, precision: int = 2) -> Tuple[int, int]:
        """
        Get grid key for spatial indexing.

        Divides the map into grid cells for fast spatial queries.

        Args:
            lat: Latitude
            lon: Longitude
            precision: Grid precision (2 = ~1km cells)

        Returns:
            (lat_grid, lon_grid) tuple
        """
        lat_grid = int(lat * (10 ** precision))
        lon_grid = int(lon * (10 ** precision))
        return (lat_grid, lon_grid)

    def _evict_lru(self):
        """
        Evict least recently used building from cache.

        Professional LRU implementation for memory management.
        """
        # Simple LRU: remove oldest 10% of cache
        evict_count = len(self._cache) // 10
        building_ids_to_evict = list(self._cache.keys())[:evict_count]

        for building_id in building_ids_to_evict:
            building = self._cache.pop(building_id, None)
            if building and building.latitude and building.longitude:
                # Remove from spatial index
                grid_key = self._get_grid_key(building.latitude, building.longitude)
                if grid_key in self._spatial_index:
                    try:
                        self._spatial_index[grid_key].remove(building_id)
                    except ValueError:
                        pass

        logger.debug(f"LRU eviction: removed {evict_count} buildings")

    def get_buildings_for_viewport(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        max_count: Optional[int] = None,
        auth_token: Optional[str] = None
    ) -> List[Building]:
        """
        Get buildings within viewport bounds (cache-first strategy).

        Professional Best Practice:
        1. Check cache first (FAST!)
        2. If cache miss, load from API/DB
        3. Update cache for future requests

        Args:
            north_east_lat: Viewport NE latitude
            north_east_lng: Viewport NE longitude
            south_west_lat: Viewport SW latitude
            south_west_lng: Viewport SW longitude
            max_count: Maximum buildings to return (for performance)
            auth_token: Optional auth token for API calls

        Returns:
            List of buildings in viewport
        """
        try:
            # Check if cache needs refresh
            if self._should_refresh_cache():
                logger.info("Cache expired, refreshing...")
                self.invalidate_cache()

            # Get grid cells for viewport
            grid_keys = self._get_viewport_grid_keys(
                north_east_lat, north_east_lng,
                south_west_lat, south_west_lng
            )

            # Collect buildings from cache
            cached_buildings = []
            with self._lock:
                for grid_key in grid_keys:
                    if grid_key in self._spatial_index:
                        for building_id in self._spatial_index[grid_key]:
                            if building_id in self._cache:
                                building = self._cache[building_id]
                                # Verify building is actually in viewport
                                if self._is_in_viewport(
                                    building,
                                    north_east_lat, north_east_lng,
                                    south_west_lat, south_west_lng
                                ):
                                    cached_buildings.append(building)

            # Cache hit statistics
            if cached_buildings:
                self._cache_hits += 1
                logger.debug(f"Cache HIT: {len(cached_buildings)} buildings in viewport")
            else:
                self._cache_misses += 1
                logger.debug("Cache MISS: loading from API/DB...")

                # Load from API/DB
                cached_buildings = self._load_buildings_from_source(
                    north_east_lat, north_east_lng,
                    south_west_lat, south_west_lng,
                    auth_token
                )

            # Apply max_count limit if specified
            if max_count and len(cached_buildings) > max_count:
                cached_buildings = cached_buildings[:max_count]

            return cached_buildings

        except Exception as e:
            logger.error(f"Error getting buildings for viewport: {e}", exc_info=True)
            return []

    def _get_viewport_grid_keys(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float
    ) -> List[Tuple[int, int]]:
        """
        Get all grid keys that overlap with viewport.

        Args:
            north_east_lat: NE latitude
            north_east_lng: NE longitude
            south_west_lat: SW latitude
            south_west_lng: SW longitude

        Returns:
            List of grid keys
        """
        grid_keys = []

        # Get min/max grid coordinates
        min_lat_grid = int(south_west_lat * 100)
        max_lat_grid = int(north_east_lat * 100)
        min_lon_grid = int(south_west_lng * 100)
        max_lon_grid = int(north_east_lng * 100)

        # Collect all grid cells in viewport
        for lat_grid in range(min_lat_grid, max_lat_grid + 1):
            for lon_grid in range(min_lon_grid, max_lon_grid + 1):
                grid_keys.append((lat_grid, lon_grid))

        return grid_keys

    def _is_in_viewport(
        self,
        building: Building,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float
    ) -> bool:
        """Check if building is within viewport bounds."""
        if not building.latitude or not building.longitude:
            return False

        return (
            south_west_lat <= building.latitude <= north_east_lat and
            south_west_lng <= building.longitude <= north_east_lng
        )

    def _load_buildings_from_source(
        self,
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        auth_token: Optional[str] = None
    ) -> List[Building]:
        """
        Load buildings from API/DB and update cache.

        Args:
            north_east_lat: NE latitude
            north_east_lng: NE longitude
            south_west_lat: SW latitude
            south_west_lng: SW longitude
            auth_token: Optional auth token

        Returns:
            List of buildings
        """
        try:
            # Set auth token if provided
            if auth_token and self.building_controller.is_using_api:
                self.building_controller.set_auth_token(auth_token)

            # Load buildings (large set for better caching)
            building_filter = BuildingFilter(limit=500)
            result = self.building_controller.load_buildings(building_filter)

            if not result.success:
                logger.error(f"Failed to load buildings: {result.message}")
                return []

            all_buildings = result.data

            # Filter to viewport and update cache
            viewport_buildings = []
            with self._lock:
                for building in all_buildings:
                    # Add to cache
                    self._add_to_cache(building)

                    # Check if in viewport
                    if self._is_in_viewport(
                        building,
                        north_east_lat, north_east_lng,
                        south_west_lat, south_west_lng
                    ):
                        viewport_buildings.append(building)

            logger.debug(f"Loaded {len(all_buildings)} buildings, {len(viewport_buildings)} in viewport")
            return viewport_buildings

        except Exception as e:
            logger.error(f"Error loading buildings from source: {e}", exc_info=True)
            return []

    def get_building_by_id(self, building_id: str) -> Optional[Building]:
        """
        Get building by ID from cache.

        Args:
            building_id: Building ID

        Returns:
            Building or None if not in cache
        """
        with self._lock:
            return self._cache.get(building_id)

    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed based on TTL."""
        elapsed = datetime.now() - self._cache_timestamp
        return elapsed > timedelta(hours=self.CACHE_TTL_HOURS)

    def invalidate_cache(self):
        """Clear cache (for testing or when data changes)."""
        with self._lock:
            self._cache.clear()
            self._spatial_index.clear()
            self._cache_timestamp = datetime.now()
        logger.info("Cache invalidated")

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'cache_size': len(self._cache),
            'max_cache_size': self.MAX_CACHE_SIZE,
            'spatial_index_size': len(self._spatial_index),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'cache_age_hours': (datetime.now() - self._cache_timestamp).total_seconds() / 3600
        }


# Convenience function
def get_building_cache(db: Database = None) -> BuildingCacheService:
    """
    Get singleton instance of BuildingCacheService.

    Args:
        db: Database instance (required on first call)

    Returns:
        BuildingCacheService singleton
    """
    return BuildingCacheService.get_instance(db)
