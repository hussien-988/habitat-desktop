# -*- coding: utf-8 -*-
"""
Cache Initializer - Application Startup Helper
===============================================

Initialize BuildingCacheService during application startup.

Usage in main.py:
    from utils.cache_initializer import initialize_application_cache

    # After database initialization
    initialize_application_cache(db, auth_token)
"""

from typing import Optional
from repositories.database import Database
from services.building_cache_service import get_building_cache
from utils.logger import get_logger

logger = get_logger(__name__)


def initialize_application_cache(
    db: Database,
    auth_token: Optional[str] = None,
    initial_size: int = 150
) -> bool:
    """
    Initialize application-wide building cache on startup.

    Professional Best Practice:
    - Loads small initial set of buildings (150) during startup
    - Provides instant responsiveness for map operations
    - Reduces API calls and database queries
    - Improves overall application performance

    Args:
        db: Database instance
        auth_token: Optional authentication token for API
        initial_size: Number of buildings to load initially (default: 150)

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("🚀 Initializing application cache...")

        # Get singleton cache instance
        cache = get_building_cache(db)

        # Set initial cache size if different from default
        if initial_size != 150:
            cache.INITIAL_CACHE_SIZE = initial_size

        # Initialize cache with buildings
        success = cache.initialize_cache(auth_token=auth_token)

        if success:
            stats = cache.get_cache_stats()
            logger.info(
                f"✅ Cache initialized successfully!\n"
                f"   - Buildings cached: {stats['cache_size']}\n"
                f"   - Spatial index size: {stats['spatial_index_size']}\n"
                f"   - Max cache size: {stats['max_cache_size']}\n"
                f"   - Ready for high-performance map operations!"
            )
        else:
            logger.warning("⚠️ Cache initialization failed (will use API/DB fallback)")

        return success

    except Exception as e:
        logger.error(f"Error initializing cache: {e}", exc_info=True)
        return False


def get_cache_stats_summary() -> str:
    """
    Get human-readable cache statistics summary.

    Returns:
        Formatted cache stats string
    """
    try:
        cache = get_building_cache()
        stats = cache.get_cache_stats()

        return (
            f"📊 Cache Statistics:\n"
            f"  Buildings: {stats['cache_size']}/{stats['max_cache_size']}\n"
            f"  Hit Rate: {stats['hit_rate']}\n"
            f"  Cache Age: {stats['cache_age_hours']:.1f} hours\n"
            f"  Spatial Index: {stats['spatial_index_size']} cells"
        )
    except Exception as e:
        return f"Cache stats unavailable: {e}"
