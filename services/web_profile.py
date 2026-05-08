# -*- coding: utf-8 -*-
"""Shared QWebEngineProfile for all map web views.

Using a single named profile across the preview map and full-screen
map dialog allows the HTTP cache (Leaflet JS/CSS, OSM tiles) to be
reused, avoiding redundant downloads on every dialog open.
"""

from __future__ import annotations

import os
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineProfile
    _HAS_WEBENGINE = True
except ImportError:
    QWebEngineProfile = None
    _HAS_WEBENGINE = False


_PROFILE = None


def get_shared_map_profile():
    """Return a process-wide QWebEngineProfile for map web views.

    Lazy-initialized on first use. Persistent disk cache is enabled so
    Leaflet assets and tile images survive across app restarts.
    """
    global _PROFILE
    if not _HAS_WEBENGINE:
        return None
    if _PROFILE is not None:
        return _PROFILE

    try:
        profile = QWebEngineProfile("trrcms_maps")

        from app.config import Config
        cache_root = getattr(Config, "DATA_DIR", None)
        if cache_root:
            cache_dir = os.path.join(str(cache_root), "web_cache", "maps")
            storage_dir = os.path.join(str(cache_root), "web_storage", "maps")
            os.makedirs(cache_dir, exist_ok=True)
            os.makedirs(storage_dir, exist_ok=True)
            profile.setCachePath(cache_dir)
            profile.setPersistentStoragePath(storage_dir)

        profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
        profile.setHttpCacheMaximumSize(64 * 1024 * 1024)

        _PROFILE = profile
        logger.info("Shared map web profile initialized (DiskHttpCache enabled)")
    except Exception as e:
        logger.warning(f"Could not init shared map profile: {e}")
        _PROFILE = None

    return _PROFILE
