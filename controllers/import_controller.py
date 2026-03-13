# -*- coding: utf-8 -*-
"""
Import Controller — orchestrates the import pipeline (UC-003).
"""

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from services.api_client import get_api_client
from utils.logger import get_logger

logger = get_logger(__name__)


class ImportController(BaseController):
    """Controller for the import pipeline."""

    package_uploaded = pyqtSignal(str)  # package_id
    package_staged = pyqtSignal(str)
    package_committed = pyqtSignal(str)
    package_cancelled = pyqtSignal(str)

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db

    def upload_package(self, file_path: str) -> OperationResult[Dict]:
        """Upload a .uhc package."""
        try:
            api = get_api_client()
            result = api.import_upload(file_path)
            pkg_id = result.get("id") or result.get("packageId") or ""
            self.package_uploaded.emit(pkg_id)
            return OperationResult.ok(data=result, message_ar="تم رفع الملف بنجاح")
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل رفع الملف")

    def get_packages(
        self, page: int = 1, page_size: int = 20, status_filter: str = None
    ) -> OperationResult[Dict]:
        """List import packages."""
        try:
            api = get_api_client()
            result = api.get_import_packages(page, page_size, status_filter)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Get packages failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل قائمة الحزم")

    def get_package(self, package_id: str) -> OperationResult[Dict]:
        """Get package details."""
        try:
            api = get_api_client()
            result = api.get_import_package(package_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Get package failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل تفاصيل الحزمة")

    def stage_package(self, package_id: str) -> OperationResult[Dict]:
        """Stage a package (unpack + validate)."""
        try:
            api = get_api_client()
            result = api.stage_import_package(package_id)
            self.package_staged.emit(package_id)
            return OperationResult.ok(data=result, message_ar="تم تدريج الحزمة بنجاح")
        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تدريج الحزمة")

    def get_validation_report(self, package_id: str) -> OperationResult[Dict]:
        """Get validation report."""
        try:
            api = get_api_client()
            result = api.get_validation_report(package_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Get validation report failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل تقرير التحقق")

    def get_staged_entities(self, package_id: str) -> OperationResult[List]:
        """Get staged entities."""
        try:
            api = get_api_client()
            result = api.get_staged_entities(package_id)
            items = result if isinstance(result, list) else result.get("items", []) if isinstance(result, dict) else []
            return OperationResult.ok(data=items)
        except Exception as e:
            logger.error(f"Get staged entities failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل الكيانات المرحلية")

    def detect_duplicates(self, package_id: str) -> OperationResult[Dict]:
        """Run duplicate detection."""
        try:
            api = get_api_client()
            result = api.detect_duplicates(package_id)
            return OperationResult.ok(data=result, message_ar="تم كشف التكرارات")
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل كشف التكرارات")

    def approve_package(self, package_id: str) -> OperationResult[Dict]:
        """Approve package for commit."""
        try:
            api = get_api_client()
            result = api.approve_import_package(package_id)
            return OperationResult.ok(data=result, message_ar="تمت الموافقة على الحزمة")
        except Exception as e:
            logger.error(f"Approve failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل الموافقة على الحزمة")

    def commit_package(self, package_id: str) -> OperationResult[Dict]:
        """Commit package to production."""
        try:
            api = get_api_client()
            result = api.commit_import_package(package_id)
            self.package_committed.emit(package_id)
            return OperationResult.ok(data=result, message_ar="تم إدخال البيانات في الإنتاج")
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل إدخال البيانات")

    def get_commit_report(self, package_id: str) -> OperationResult[Dict]:
        """Get commit report."""
        try:
            api = get_api_client()
            result = api.get_commit_report(package_id)
            return OperationResult.ok(data=result)
        except Exception as e:
            logger.error(f"Get commit report failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل تقرير الإدخال")

    def reset_commit(self, package_id: str) -> OperationResult[Dict]:
        """Reset a stuck commit."""
        try:
            api = get_api_client()
            result = api.reset_commit(package_id)
            return OperationResult.ok(data=result, message_ar="تم إعادة تعيين حالة الإدخال")
        except Exception as e:
            logger.error(f"Reset commit failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل إعادة التعيين")

    def cancel_package(self, package_id: str) -> OperationResult[Dict]:
        """Cancel an active package."""
        try:
            api = get_api_client()
            result = api.cancel_import_package(package_id)
            self.package_cancelled.emit(package_id)
            return OperationResult.ok(data=result, message_ar="تم إلغاء الحزمة")
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل إلغاء الحزمة")

    def quarantine_package(self, package_id: str) -> OperationResult[Dict]:
        """Quarantine a suspicious package."""
        try:
            api = get_api_client()
            result = api.quarantine_import_package(package_id)
            return OperationResult.ok(data=result, message_ar="تم حجر الحزمة")
        except Exception as e:
            logger.error(f"Quarantine failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل حجر الحزمة")
