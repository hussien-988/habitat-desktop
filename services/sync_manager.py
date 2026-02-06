# -*- coding: utf-8 -*-
"""
Sync Manager - لإدارة تشغيل Sync Server.
"""

from typing import Optional
from services.sync_server_service import SyncServerService
from utils.logger import get_logger

logger = get_logger(__name__)

_sync_server_instance: Optional[SyncServerService] = None


def start_sync_server(db, uhc_service, port=8443) -> bool:
    """
    تشغيل Sync Server عند بدء التطبيق.

    Args:
        db: Database connection
        uhc_service: UHC service instance
        port: Port number (default: 8443)

    Returns:
        True إذا نجح التشغيل
    """
    global _sync_server_instance

    try:
        if _sync_server_instance and _sync_server_instance.server:
            logger.warning("Sync server already running")
            return True

        _sync_server_instance = SyncServerService(db, uhc_service, port=port)
        success = _sync_server_instance.start()

        if success:
            logger.info(f"✅ Sync Server started on port {port}")
            logger.info(f"   Tablets can connect to: {_sync_server_instance.local_ip}:{port}")
        else:
            logger.error("❌ Failed to start Sync Server")

        return success

    except Exception as e:
        logger.error(f"Failed to start Sync Server: {e}", exc_info=True)
        return False


def stop_sync_server():
    """إيقاف Sync Server."""
    global _sync_server_instance

    if _sync_server_instance:
        try:
            _sync_server_instance.stop()
            logger.info("✅ Sync Server stopped")
        except Exception as e:
            logger.error(f"Error stopping Sync Server: {e}")
        finally:
            _sync_server_instance = None


def get_sync_server() -> Optional[SyncServerService]:
    """الحصول على Sync Server instance."""
    return _sync_server_instance
