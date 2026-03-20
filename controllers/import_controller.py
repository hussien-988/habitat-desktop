# -*- coding: utf-8 -*-
"""
Import Controller.
"""

import time
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from services.api_client import get_api_client
from services.exceptions import NetworkException, ApiException
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

    @staticmethod
    def _api_error_msg(e: Exception, default_msg: str) -> str:
        """Return user-facing Arabic message based on API status code."""
        if not hasattr(e, "status_code"):
            return default_msg
        code = e.status_code
        detail = ""
        if hasattr(e, "response_data") and e.response_data:
            detail = (
                e.response_data.get("detail", "")
                or e.response_data.get("message", "")
                or ""
            )
        if code == 403:
            return "غير مخوّل: لا تملك صلاحية تنفيذ هذا الإجراء"
        if code == 409:
            if detail:
                return f"تعارض في حالة الحزمة: {detail}"
            return "تعارض في حالة الحزمة"
        if code == 400:
            return "طلب غير صالح — يرجى المحاولة لاحقاً"
        if code == 404:
            return "الحزمة غير موجودة"
        if code == 500:
            return "خطأ في الخادم — يرجى إبلاغ الدعم الفني"
        return default_msg

    @staticmethod
    def _with_retry(fn, max_retries=2, backoff_base=1.0):
        """Retry on NetworkException with exponential backoff."""
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except NetworkException:
                if attempt == max_retries:
                    raise
                wait = backoff_base * (2 ** attempt)
                logger.info(f"Network error, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)

    def upload_package(self, file_path: str) -> OperationResult[Dict]:
        """Upload a .uhc package."""
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.import_upload(file_path))
            pkg_id = result.get("id") or result.get("packageId") or ""
            self.package_uploaded.emit(pkg_id)
            return OperationResult.ok(data=result, message_ar="تم رفع الملف بنجاح")
        except ApiException as e:
            logger.error(f"Upload API error: {e}")
            if e.status_code == 409:
                msg_ar = "هذه الحزمة مرفوعة مسبقاً ولا يمكن رفعها مرة أخرى"
            else:
                msg_ar = f"فشل رفع الملف: خطأ من الخادم ({e.status_code})"
            return OperationResult.fail(str(e), message_ar=msg_ar)
        except NetworkException as e:
            logger.error(f"Upload network error: {e}")
            return OperationResult.fail(str(e), message_ar="فشل رفع الملف: خطأ في الاتصال بالخادم")
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
        except ApiException as e:
            logger.error(f"Get packages API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل تحميل قائمة الحزم"))
        except NetworkException as e:
            logger.error(f"Get packages network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Get packages failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل قائمة الحزم")

    def get_package(self, package_id: str) -> OperationResult[Dict]:
        """Get package details."""
        try:
            api = get_api_client()
            result = api.get_import_package(package_id)
            return OperationResult.ok(data=result)
        except ApiException as e:
            logger.error(f"Get package API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل تحميل تفاصيل الحزمة"))
        except NetworkException as e:
            logger.error(f"Get package network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Get package failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل تفاصيل الحزمة")

    def stage_package(self, package_id: str) -> OperationResult[Dict]:
        """Stage a package (unpack + validate)."""
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.stage_import_package(package_id))
            self.package_staged.emit(package_id)
            return OperationResult.ok(data=result, message_ar="تم تدريج الحزمة بنجاح")
        except ApiException as e:
            logger.error(f"Stage package API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل تدريج الحزمة"))
        except NetworkException as e:
            logger.error(f"Stage package network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Staging failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تدريج الحزمة")

    def get_validation_report(self, package_id: str) -> OperationResult[Dict]:
        """Get validation report."""
        try:
            api = get_api_client()
            result = api.get_validation_report(package_id)
            return OperationResult.ok(data=result)
        except ApiException as e:
            logger.error(f"Get validation report API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل تحميل تقرير التحقق"))
        except NetworkException as e:
            logger.error(f"Get validation report network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Get validation report failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل تقرير التحقق")

    def get_staged_entities(self, package_id: str) -> OperationResult[Dict]:
        """Get staged entities (grouped by type).

        Returns the raw API response dict with keys:
        buildings, propertyUnits, persons, households,
        personPropertyRelations, claims, surveys, evidences, totalCount.
        """
        try:
            api = get_api_client()
            result = api.get_staged_entities(package_id)
            if not isinstance(result, dict):
                result = {}
            return OperationResult.ok(data=result)
        except ApiException as e:
            logger.error(f"Get staged entities API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل تحميل الكيانات المرحلية"))
        except NetworkException as e:
            logger.error(f"Get staged entities network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Get staged entities failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل الكيانات المرحلية")

    def detect_duplicates(self, package_id: str) -> OperationResult[Dict]:
        """Run duplicate detection."""
        try:
            api = get_api_client()
            result = api.detect_duplicates(package_id)
            return OperationResult.ok(data=result, message_ar="تم كشف التكرارات")
        except ApiException as e:
            logger.error(f"Detect duplicates API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل كشف التكرارات"))
        except NetworkException as e:
            logger.error(f"Detect duplicates network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل كشف التكرارات")

    def approve_package(self, package_id: str) -> OperationResult[Dict]:
        """Approve package for commit."""
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.approve_import_package(package_id))
            return OperationResult.ok(data=result, message_ar="تمت الموافقة على الحزمة")
        except ApiException as e:
            logger.error(f"Approve package API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل الموافقة على الحزمة"))
        except NetworkException as e:
            logger.error(f"Approve package network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Approve failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل الموافقة على الحزمة")

    def commit_package(self, package_id: str) -> OperationResult[Dict]:
        """Commit package to production."""
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.commit_import_package(package_id))
            self.package_committed.emit(package_id)
            return OperationResult.ok(data=result, message_ar="تم إدخال البيانات في الإنتاج")
        except ApiException as e:
            logger.error(f"Commit package API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل إدخال البيانات"))
        except NetworkException as e:
            logger.error(f"Commit package network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل إدخال البيانات")

    def get_commit_report(self, package_id: str) -> OperationResult[Dict]:
        """Get commit report."""
        try:
            api = get_api_client()
            result = api.get_commit_report(package_id)
            return OperationResult.ok(data=result)
        except ApiException as e:
            logger.error(f"Get commit report API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل تحميل تقرير الإدخال"))
        except NetworkException as e:
            logger.error(f"Get commit report network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Get commit report failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل تحميل تقرير الإدخال")

    def reset_commit(self, package_id: str) -> OperationResult[Dict]:
        """Reset a stuck commit."""
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.reset_commit(package_id))
            return OperationResult.ok(data=result, message_ar="تم إعادة تعيين حالة الإدخال")
        except ApiException as e:
            logger.error(f"Reset commit API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل إعادة التعيين"))
        except NetworkException as e:
            logger.error(f"Reset commit network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
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
        except ApiException as e:
            logger.error(f"Cancel package API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل إلغاء الحزمة"))
        except NetworkException as e:
            logger.error(f"Cancel package network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل إلغاء الحزمة")

    def quarantine_package(self, package_id: str) -> OperationResult[Dict]:
        """Quarantine a suspicious package."""
        try:
            api = get_api_client()
            result = api.quarantine_import_package(package_id)
            return OperationResult.ok(data=result, message_ar="تم حجر الحزمة")
        except ApiException as e:
            logger.error(f"Quarantine package API error: {e}")
            return OperationResult.fail(str(e), message_ar=self._api_error_msg(e, "فشل حجر الحزمة"))
        except NetworkException as e:
            logger.error(f"Quarantine package network error: {e}")
            return OperationResult.fail(str(e), message_ar="خطأ في الاتصال بالخادم")
        except Exception as e:
            logger.error(f"Quarantine failed: {e}")
            return OperationResult.fail(str(e), message_ar="فشل حجر الحزمة")
