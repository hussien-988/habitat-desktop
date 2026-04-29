# -*- coding: utf-8 -*-
"""Global registry for live ApiWorker (QThread) instances.

The registry exists for one reason: when the user closes the app, every
background thread we started must be told to stop and given a brief moment
to wind down. Without this, PyQt prints
``QThread: Destroyed while thread is still running`` and the OS may keep
the process alive briefly with half-finished network requests in flight.

Pages do not need to talk to this module directly — ``ApiWorker.__init__``
registers itself automatically. Wiring lives at the application boundary
(``main.py`` connects ``QApplication.aboutToQuit`` to ``stop_all_workers``).
"""

from typing import Set
from utils.logger import get_logger

logger = get_logger(__name__)


# Strong references keep workers alive until they finish naturally or until
# stop_all_workers() is called. Without strong refs, a page that drops its
# attribute (e.g. self._search_worker = ApiWorker(...) replaced by a new
# instance) would let the previous QThread be garbage-collected mid-run,
# which crashes Python.
_LIVE_WORKERS: Set = set()


def register(worker) -> None:
    """Add ``worker`` to the live set and auto-remove it on finish/error.

    Safe to call from any thread; ``set.add`` is GIL-protected and the
    finished/error signals fire on the worker's own thread but mutate the
    set under the same GIL.
    """
    if worker is None:
        return
    _LIVE_WORKERS.add(worker)
    try:
        worker.finished.connect(lambda *_: _LIVE_WORKERS.discard(worker))
        worker.error.connect(lambda *_: _LIVE_WORKERS.discard(worker))
    except Exception as e:
        logger.debug(f"Could not attach worker auto-cleanup signal: {e}")


def stop_all_workers(timeout_ms: int = 2000) -> int:
    """Politely stop every still-running worker; returns count stopped.

    ``QThread.quit()`` only ends a thread that runs an event loop — our
    ApiWorker subclass returns from ``run()`` on its own once the wrapped
    callable finishes, so quit() is largely advisory. The real safety
    comes from ``wait(timeout_ms)``, which blocks the caller (the GUI
    thread, during shutdown) until the worker exits or the timeout
    expires. Workers that do not respect the timeout are abandoned —
    we do not call ``terminate()`` because that can leave Python objects
    in inconsistent states.
    """
    snapshot = list(_LIVE_WORKERS)
    stopped = 0
    for worker in snapshot:
        try:
            if worker.isRunning():
                worker.quit()
                worker.wait(timeout_ms)
                stopped += 1
        except Exception as e:
            logger.debug(f"Error stopping worker: {e}")
    _LIVE_WORKERS.clear()
    if stopped:
        logger.info(f"Stopped {stopped} background worker(s) on shutdown")
    return stopped


def live_count() -> int:
    """Return the number of currently-tracked workers (for diagnostics)."""
    return len(_LIVE_WORKERS)
