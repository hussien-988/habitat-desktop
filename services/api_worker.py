# -*- coding: utf-8 -*-
"""Generic background worker for non-blocking API calls."""

import threading
import time
import uuid
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import get_logger
from services.worker_registry import register as _register_worker

logger = get_logger(__name__)

# Process-wide guard for run_blocking_async: prevents a second blocking
# helper from starting while one is already pumping the event loop on the
# main thread. Without this, a user click during the first wait can re-enter
# the helper and create nested QEventLoops — a known source of reentrancy
# bugs in PyQt.
_BLOCKING_ASYNC_BUSY = False
_BLOCKING_ASYNC_LOCK = threading.Lock()


class ApiWorker(QThread):
    """Runs any callable in a background thread to avoid blocking the UI."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self.exception: Optional[Exception] = None
        # Auto-register so the registry can stop us at app shutdown without
        # every call site needing to opt in.
        _register_worker(self)

    def run(self):
        from services.exceptions import (
            ApiException, NetworkException, humanize_exception, log_exception,
        )
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except (ApiException, NetworkException) as e:
            # Surface a safe user-facing message; never a stack trace.
            self.exception = e
            log_exception(e, logger, context="api_worker")
            self.error.emit(humanize_exception(e))
        except Exception as e:
            self.exception = e
            logger.warning(f"ApiWorker error: {e}")
            self.error.emit(humanize_exception(e))


def run_blocking_async(func, *args, **kwargs):
    """Run a blocking callable in a background QThread while keeping the Qt
    event loop alive on the caller's thread.

    Use this from synchronous handlers that cannot be restructured easily
    (e.g. a wizard step's `validate()` which must return a result) but where
    the inner call is a slow network operation that would otherwise freeze
    the UI for tens of seconds — typical for POSTs against a remote backend
    over ngrok.

    Returns the callable's return value, or raises RuntimeError with the
    humanized error message on failure.

    Caller responsibility: disable any UI controls that could trigger
    reentrant work (Save / Next buttons, etc.) before invoking this, and
    re-enable them after it returns. The Qt event loop *is* live during
    the wait, which is the whole point — paints, scroll, navbar all work —
    but it also means user input can fire other slots if not guarded.
    """
    from PyQt5.QtCore import QEventLoop, QTimer
    global _BLOCKING_ASYNC_BUSY

    # Reentrancy guard: another run_blocking_async is already pumping the
    # event loop. Refuse to start a second one — the caller must serialize.
    with _BLOCKING_ASYNC_LOCK:
        if _BLOCKING_ASYNC_BUSY:
            fname = getattr(func, "__name__", repr(func))
            logger.warning(
                f"[BLOCKING-ASYNC] REENTRANCY refused for {fname}: another helper is busy"
            )
            raise RuntimeError("Another background operation is already running")
        _BLOCKING_ASYNC_BUSY = True

    op_id = uuid.uuid4().hex[:6]
    fname = getattr(func, "__name__", repr(func))
    caller_tid = threading.get_ident()
    t0 = time.monotonic()
    logger.info(
        f"[BLOCKING-ASYNC {op_id}] start fn={fname} caller_tid={caller_tid}"
    )

    result_box = {"value": None, "error": None, "done": False, "timed_out": False}
    loop = QEventLoop()
    worker = ApiWorker(func, *args, **kwargs)

    def _on_done(v):
        result_box["value"] = v
        result_box["done"] = True
        loop.quit()

    def _on_err(msg):
        result_box["error"] = msg
        result_box["done"] = True
        loop.quit()

    def _on_timeout():
        if not result_box["done"]:
            result_box["timed_out"] = True
            result_box["error"] = "BLOCKING-ASYNC watchdog: 120s elapsed without worker completion"
            logger.error(
                f"[BLOCKING-ASYNC {op_id}] WATCHDOG fired after 120s, fn={fname}"
            )
            loop.quit()

    worker.finished.connect(_on_done)
    worker.error.connect(_on_err)

    # Safety watchdog so a broken worker can never wedge the UI indefinitely.
    QTimer.singleShot(120000, _on_timeout)

    worker.start()
    try:
        loop.exec_()
    finally:
        with _BLOCKING_ASYNC_LOCK:
            _BLOCKING_ASYNC_BUSY = False

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if result_box["timed_out"]:
        logger.error(
            f"[BLOCKING-ASYNC {op_id}] timed_out fn={fname} elapsed_ms={elapsed_ms}"
        )
        raise RuntimeError(result_box["error"])
    if result_box["error"] is not None:
        logger.warning(
            f"[BLOCKING-ASYNC {op_id}] error fn={fname} elapsed_ms={elapsed_ms} msg={result_box['error']}"
        )
        # Preserve original exception type so callers can use isinstance()
        # checks (e.g. ApiException.status_code == 409 for duplicate-NID).
        if worker.exception is not None:
            raise worker.exception
        raise RuntimeError(result_box["error"])
    logger.info(
        f"[BLOCKING-ASYNC {op_id}] done fn={fname} elapsed_ms={elapsed_ms}"
    )
    return result_box["value"]
