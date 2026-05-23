# -*- coding: utf-8 -*-
"""Import Controller.

All import-related backend calls go through this controller. Each method
returns an OperationResult whose .error field is the normalized
ApiException (or NetworkException) that failed the call — UI layers use
it to render inline error panels with traceId / technical details, while
the message_ar field provides the user-facing headline.
"""

import time
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from services.api_client import get_api_client
from services.translation_manager import tr
from services.exceptions import (
    ApiException,
    NetworkException,
    humanize_exception,
    log_exception,
    CTX_LOAD_PACKAGE,
    CTX_LOAD_REPORT,
    CTX_STAGE,
    CTX_DETECT,
    CTX_APPROVE,
    CTX_COMMIT,
    CTX_RESET_COMMIT,
    CTX_CANCEL,
    CTX_QUARANTINE,
    CTX_UNCANCEL,
    CTX_QUARANTINE_REPORT,
    CTX_RECONCILIATION_QUEUE,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def _fail_from_exception(exc: BaseException, context: str) -> OperationResult:
    """Backwards-compatible wrapper around BaseController.fail_from_exception."""
    return BaseController.fail_from_exception(exc, context, log=logger)


def _is_stage_already_advanced(exc: ApiException) -> bool:
    """True when a 409 from /stage indicates the package already moved past Validating."""
    parts = [exc.message or ""]
    rd = getattr(exc, "response_data", {}) or {}
    if isinstance(rd, dict):
        parts.append(str(rd.get("detail") or ""))
        parts.append(str(rd.get("message") or ""))
    haystack = " ".join(parts).lower()
    return "cannot stage" in haystack


class ImportController(BaseController):
    """Controller for the import pipeline."""

    package_uploaded = pyqtSignal(str)  # package_id
    package_staged = pyqtSignal(str)
    package_committed = pyqtSignal(str)
    package_cancelled = pyqtSignal(str)
    package_restored = pyqtSignal(str, int)  # package_id, new_status

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db

    # Backwards-compat: kept so existing callers that still reference
    # ImportController._api_error_msg don't break. Prefer humanize_exception.
    @staticmethod
    def _api_error_msg(exc: Exception, default_msg: str) -> str:
        return humanize_exception(exc)

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
                logger.info(
                    f"Network error, retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)

    # -----------------------------------------------------------------------
    # Upload (dev/test only — production packages arrive via field workflow)
    # -----------------------------------------------------------------------

    def upload_package(self, file_path: str) -> OperationResult[Dict]:
        context = "upload"
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.import_upload(file_path))
            pkg_id = result.get("id") or result.get("packageId") or ""
            print(
                f"[UPLOAD-DEBUG] Package uploaded — backend returned: id={pkg_id}, "
                f"status={result.get('status')}, fileName={result.get('fileName', 'N/A')}",
                flush=True,
            )
            self.package_uploaded.emit(pkg_id)
            return OperationResult.ok(data=result, message_ar=tr("import.success.uploaded"))
        except ApiException as e:
            # Upload has some legacy-specific domain messages (duplicate upload).
            # Keep that for users while the unified humanize layer takes over
            # general cases.
            if e.status_code == 409:
                e.context = context
                log_exception(e, logger, context=context)
                fail = OperationResult.fail(
                    message=str(e),
                    message_ar=tr("import.error.duplicate_package"),
                    error=e,
                )
                # Pass the backend body through so the UI can link to the
                # already-imported package (isDuplicatePackage + package).
                if isinstance(getattr(e, "response_data", None), dict):
                    fail.data = e.response_data
                return fail
            return _fail_from_exception(e, context)
        except NetworkException as e:
            return _fail_from_exception(e, context)
        except Exception as e:
            return _fail_from_exception(e, context)

    # -----------------------------------------------------------------------
    # Packages list / details
    # -----------------------------------------------------------------------

    def get_packages(
        self, page: int = 1, page_size: int = 20, status_filter: str = None
    ) -> OperationResult[Dict]:
        try:
            api = get_api_client()
            return OperationResult.ok(
                data=api.get_import_packages(page, page_size, status_filter)
            )
        except (ApiException, NetworkException) as e:
            return _fail_from_exception(e, CTX_LOAD_PACKAGE)
        except Exception as e:
            return _fail_from_exception(e, CTX_LOAD_PACKAGE)

    def get_package(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        try:
            api = get_api_client()
            data = api.get_import_package(package_id)
            latency = int((time.monotonic() - t) * 1000)
            status = data.get("status") if isinstance(data, dict) else None
            logger.info(
                f"[import-flow] api GET /packages/{package_id} → status={status} latency={latency}ms"
            )
            return OperationResult.ok(data=data)
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api GET /packages/{package_id} FAILED type={type(e).__name__} "
                f"latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_LOAD_PACKAGE)
        except Exception as e:
            return _fail_from_exception(e, CTX_LOAD_PACKAGE)

    def get_package_with_meta(self, package_id: str) -> OperationResult[Dict]:
        """Fetch a package and enrich the dict with UI metadata."""
        from services.import_status_map import status_meta
        result = self.get_package(package_id)
        if result.success and isinstance(result.data, dict):
            status = result.data.get("status", 0)
            if isinstance(status, str) and status.isdigit():
                status = int(status)
            result.data["_statusMeta"] = status_meta(status)
        return result

    def get_conflict_count_for_package(
        self, package_id: str, only_pending: bool = True
    ) -> OperationResult[int]:
        """Return the count of conflicts on a package.

        By default counts only PendingReview conflicts — this is what the
        backend's AreAllResolvedForPackageAsync uses to decide whether the
        package can transition from ReviewingConflicts to ReadyToCommit.
        Counting all conflicts (including Resolved/AutoResolved) gives a
        misleading number that prevents the wizard's rescue path from
        firing when a package is actually fully resolved.

        Pass `only_pending=False` for the global "any-status" count.
        """
        t = time.monotonic()
        try:
            api = get_api_client()
            kwargs = {"page": 1, "page_size": 1, "import_package_id": package_id}
            if only_pending:
                kwargs["status"] = "PendingReview"
            result = api.get_conflicts(**kwargs)
            total = int(result.get("totalCount", 0) or 0) if isinstance(result, dict) else 0
            latency = int((time.monotonic() - t) * 1000)
            logger.info(
                f"[import-flow] api GET /conflicts pkg={package_id} only_pending={only_pending} "
                f"→ count={total} latency={latency}ms"
            )
            return OperationResult.ok(data=total)
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api GET /conflicts pkg={package_id} FAILED "
                f"type={type(e).__name__} latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, "load_conflict_count")
        except Exception as e:
            return _fail_from_exception(e, "load_conflict_count")

    # -----------------------------------------------------------------------
    # Pipeline steps
    # -----------------------------------------------------------------------

    def stage_package(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        logger.info(f"[import-flow] api POST /stage/{package_id} started")
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.stage_import_package(package_id))
            latency = int((time.monotonic() - t) * 1000)
            logger.info(
                f"[import-flow] api POST /stage/{package_id} OK latency={latency}ms"
            )
            self.package_staged.emit(package_id)
            return OperationResult.ok(data=result, message_ar=tr("import.success.staged"))
        except ApiException as e:
            latency = int((time.monotonic() - t) * 1000)
            if e.status_code == 409 and _is_stage_already_advanced(e):
                logger.info(
                    f"[import-flow] api POST /stage/{package_id} 409-idempotent "
                    f"latency={latency}ms (backend already advanced)"
                )
                self.package_staged.emit(package_id)
                return OperationResult.ok(
                    data={"alreadyAdvanced": True},
                    message_ar=tr("import.success.stage_already_advanced"),
                )
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api POST /stage/{package_id} FAILED type={type(e).__name__} "
                f"latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_STAGE)
        except NetworkException as e:
            latency = int((time.monotonic() - t) * 1000)
            logger.warning(
                f"[import-flow] api POST /stage/{package_id} FAILED type={type(e).__name__} "
                f"latency={latency}ms"
            )
            return _fail_from_exception(e, CTX_STAGE)
        except Exception as e:
            return _fail_from_exception(e, CTX_STAGE)

    def get_validation_report(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        try:
            api = get_api_client()
            data = api.get_validation_report(package_id)
            latency = int((time.monotonic() - t) * 1000)
            logger.info(
                f"[import-flow] api GET /validation-report/{package_id} OK latency={latency}ms"
            )
            return OperationResult.ok(data=data)
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api GET /validation-report/{package_id} FAILED "
                f"type={type(e).__name__} latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_LOAD_REPORT)
        except Exception as e:
            return _fail_from_exception(e, CTX_LOAD_REPORT)

    def get_staged_entities(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        try:
            api = get_api_client()
            result = api.get_staged_entities(package_id)
            if not isinstance(result, dict):
                result = {}
            latency = int((time.monotonic() - t) * 1000)
            logger.info(
                f"[import-flow] api GET /staged-entities/{package_id} received latency={latency}ms"
            )
            return OperationResult.ok(data=result)
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api GET /staged-entities/{package_id} FAILED "
                f"type={type(e).__name__} latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_LOAD_REPORT)
        except Exception as e:
            return _fail_from_exception(e, CTX_LOAD_REPORT)

    def detect_duplicates(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        logger.info(f"[import-flow] api POST /detect-duplicates/{package_id} started")
        try:
            api = get_api_client()
            data = api.detect_duplicates(package_id)
            latency = int((time.monotonic() - t) * 1000)
            logger.info(
                f"[import-flow] api POST /detect-duplicates/{package_id} OK latency={latency}ms"
            )
            return OperationResult.ok(data=data, message_ar=tr("import.success.duplicates_detected"))
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api POST /detect-duplicates/{package_id} FAILED "
                f"type={type(e).__name__} latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_DETECT)
        except Exception as e:
            return _fail_from_exception(e, CTX_DETECT)

    def stage_and_detect_if_pending(
        self, package_id: str, current_status: int
    ) -> OperationResult[Dict]:
        """Stage then detect-duplicates — but only when the package is still
        PENDING. If stage fails, do NOT call detect-duplicates."""
        from services.import_status_map import PkgStatus
        if current_status != PkgStatus.PENDING:
            return OperationResult.ok(data={"skipped": True, "reason": "status_not_pending"})

        stage_result = self.stage_package(package_id)
        if not stage_result.success:
            # Critical: stop the chain here. Propagate the typed error to the UI.
            return stage_result

        detect_result = self.detect_duplicates(package_id)
        if not detect_result.success:
            logger.warning(f"Duplicate detection failed after stage: {detect_result.message}")
            # Stage succeeded — surface partial success but attach the detect error
            return OperationResult.ok(
                data={"stage": stage_result.data, "detect": None},
                message_ar=stage_result.message_ar,
            )
        return OperationResult.ok(
            data={"stage": stage_result.data, "detect": detect_result.data},
            message_ar=stage_result.message_ar,
        )

    def approve_package(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        logger.info(f"[import-flow] api POST /approve/{package_id} started")
        try:
            api = get_api_client()
            data = self._with_retry(lambda: api.approve_import_package(package_id))
            latency = int((time.monotonic() - t) * 1000)
            logger.info(f"[import-flow] api POST /approve/{package_id} OK latency={latency}ms")
            return OperationResult.ok(data=data, message_ar=tr("import.success.approved"))
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api POST /approve/{package_id} FAILED type={type(e).__name__} "
                f"latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_APPROVE)
        except Exception as e:
            return _fail_from_exception(e, CTX_APPROVE)

    def commit_package(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        logger.info(f"[import-flow] api POST /commit/{package_id} started")
        try:
            api = get_api_client()
            result = self._with_retry(lambda: api.commit_import_package(package_id))
            latency = int((time.monotonic() - t) * 1000)
            logger.info(f"[import-flow] api POST /commit/{package_id} OK latency={latency}ms")
            self.package_committed.emit(package_id)
            return OperationResult.ok(data=result, message_ar=tr("import.success.committed"))
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api POST /commit/{package_id} FAILED type={type(e).__name__} "
                f"latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_COMMIT)
        except Exception as e:
            return _fail_from_exception(e, CTX_COMMIT)

    def get_commit_report(self, package_id: str) -> OperationResult[Dict]:
        t = time.monotonic()
        try:
            api = get_api_client()
            data = api.get_commit_report(package_id)
            latency = int((time.monotonic() - t) * 1000)
            if isinstance(data, dict):
                approved = data.get("totalRecordsApproved", "?")
                committed = data.get("totalRecordsCommitted", "?")
                failed = data.get("totalRecordsFailed", "?")
                skipped = data.get("totalRecordsSkipped", "?")
                rate = data.get("successRate", "?")
                logger.info(
                    f"[import-flow] api GET /commit-report/{package_id} → "
                    f"approved={approved} committed={committed} failed={failed} "
                    f"skipped={skipped} rate={rate} latency={latency}ms"
                )
            else:
                logger.info(
                    f"[import-flow] api GET /commit-report/{package_id} → non-dict latency={latency}ms"
                )
            return OperationResult.ok(data=data)
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api GET /commit-report/{package_id} FAILED "
                f"type={type(e).__name__} latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_LOAD_REPORT)
        except Exception as e:
            return _fail_from_exception(e, CTX_LOAD_REPORT)

    def reset_commit(self, package_id: str, reason: str = "") -> OperationResult[Dict]:
        """Reset a stuck commit. Never called implicitly — only in response to
        an explicit user request after confirmation. Backend requires a
        non-empty reason for the audit trail."""
        try:
            api = get_api_client()
            return OperationResult.ok(
                data=self._with_retry(lambda: api.reset_commit(package_id, reason=reason)),
                message_ar=tr("import.success.reset"),
            )
        except (ApiException, NetworkException) as e:
            return _fail_from_exception(e, CTX_RESET_COMMIT)
        except Exception as e:
            return _fail_from_exception(e, CTX_RESET_COMMIT)

    def cancel_package(self, package_id: str, reason: str = "") -> OperationResult[Dict]:
        t = time.monotonic()
        logger.info(f"[import-flow] api POST /cancel/{package_id} started reason={reason!r}")
        try:
            api = get_api_client()
            if reason:
                result = api.cancel_import_package(package_id, reason=reason)
            else:
                result = api.cancel_import_package(package_id)
            latency = int((time.monotonic() - t) * 1000)
            logger.info(f"[import-flow] api POST /cancel/{package_id} OK latency={latency}ms")
            self.package_cancelled.emit(package_id)
            return OperationResult.ok(data=result, message_ar=tr("import.success.cancelled"))
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api POST /cancel/{package_id} FAILED type={type(e).__name__} "
                f"latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_CANCEL)
        except Exception as e:
            return _fail_from_exception(e, CTX_CANCEL)

    def quarantine_package(self, package_id: str, reason: str = "") -> OperationResult[Dict]:
        try:
            api = get_api_client()
            return OperationResult.ok(
                data=api.quarantine_import_package(package_id, reason=reason),
                message_ar=tr("import.success.quarantined"),
            )
        except (ApiException, NetworkException) as e:
            return _fail_from_exception(e, CTX_QUARANTINE)
        except Exception as e:
            return _fail_from_exception(e, CTX_QUARANTINE)

    def uncancel_package(
        self, package_id: str, reason: str = ""
    ) -> OperationResult[Dict]:
        """Restore a Cancelled package; UI should route by returned status."""
        t = time.monotonic()
        logger.info(f"[import-flow] api POST /uncancel/{package_id} started reason={reason!r}")
        try:
            api = get_api_client()
            result = api.uncancel_import_package(package_id, reason or None)
            latency = int((time.monotonic() - t) * 1000)
            new_status = 0
            if isinstance(result, dict):
                new_status = int(result.get("status") or 0)
            logger.info(
                f"[import-flow] api POST /uncancel/{package_id} OK "
                f"latency={latency}ms new_status={new_status}"
            )
            self.package_restored.emit(package_id, new_status)
            return OperationResult.ok(
                data=result, message_ar=tr("import.success.restored")
            )
        except (ApiException, NetworkException) as e:
            latency = int((time.monotonic() - t) * 1000)
            trace = getattr(e, "trace_id", "") or ""
            logger.warning(
                f"[import-flow] api POST /uncancel/{package_id} FAILED "
                f"type={type(e).__name__} latency={latency}ms trace={trace}"
            )
            return _fail_from_exception(e, CTX_UNCANCEL)
        except Exception as e:
            return _fail_from_exception(e, CTX_UNCANCEL)

    def get_quarantine_report(self, package_id: str) -> OperationResult[Dict]:
        """Fetch the structured quarantine report for a package."""
        try:
            api = get_api_client()
            return OperationResult.ok(data=api.get_quarantine_report(package_id))
        except (ApiException, NetworkException) as e:
            return _fail_from_exception(e, CTX_QUARANTINE_REPORT)
        except Exception as e:
            return _fail_from_exception(e, CTX_QUARANTINE_REPORT)

    def get_reconciliation_queue(
        self,
        entity_type: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> OperationResult[Dict]:
        """Fetch the Keep-Separate reconciliation queue (persons + units)."""
        try:
            api = get_api_client()
            return OperationResult.ok(
                data=api.get_reconciliation_queue(entity_type, page, page_size)
            )
        except (ApiException, NetworkException) as e:
            return _fail_from_exception(e, CTX_RECONCILIATION_QUEUE)
        except Exception as e:
            return _fail_from_exception(e, CTX_RECONCILIATION_QUEUE)
