"""Lightweight phase-timing trace for the map-open pipeline.

A trace is created at the entry point of a flow (Claims, Field Work,
Buildings Mgmt), passed into the map dialog, and `mark()` is called at each
phase boundary. All marks log a single grep-able line:

    [MAP_PERF] dialog=<id> flow=<name> phase=<name> elapsed_ms=<n> since_prev_ms=<n> <k=v ...>

When the map is fully ready, `summary()` emits one final line:

    [MAP_PERF_SUMMARY] dialog=<id> flow=<name> total_ms=<n> phases={phase=ms,...}

The trace object is thread-safe: marks called from QThread workers are fine.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class MapPerfTrace:
    """Per-dialog phase-timing trace. Construct at flow entry, pass into the dialog."""

    def __init__(self, flow_name: str, dialog_id: Optional[str] = None):
        self.flow_name = flow_name
        self.dialog_id = dialog_id or uuid.uuid4().hex[:8]
        self._t0 = time.perf_counter()
        self._last = self._t0
        self._lock = threading.Lock()
        self._phases: Dict[str, float] = {}
        self._summarized = False

    def mark(self, phase: str, **fields: Any) -> None:
        now = time.perf_counter()
        with self._lock:
            elapsed_ms = (now - self._t0) * 1000.0
            since_prev_ms = (now - self._last) * 1000.0
            self._last = now
            self._phases[phase] = elapsed_ms
        extras = " ".join(f"{k}={v}" for k, v in fields.items())
        # WARNING level so the marks appear in the terminal during this
        # diagnostic pass; the project's console handler is WARNING+ only.
        logger.warning(
            "[MAP_PERF] dialog=%s flow=%s phase=%s elapsed_ms=%.1f since_prev_ms=%.1f%s",
            self.dialog_id,
            self.flow_name,
            phase,
            elapsed_ms,
            since_prev_ms,
            (" " + extras) if extras else "",
        )

    def summary(self) -> None:
        with self._lock:
            if self._summarized:
                return
            self._summarized = True
            now = time.perf_counter()
            total_ms = (now - self._t0) * 1000.0
            phases_str = ",".join(f"{k}={v:.0f}" for k, v in self._phases.items())
        logger.warning(
            "[MAP_PERF_SUMMARY] dialog=%s flow=%s total_ms=%.1f phases={%s}",
            self.dialog_id,
            self.flow_name,
            total_ms,
            phases_str,
        )


# Module-level pointer to the trace currently in the synchronous critical
# section (HTML generation + tile-metadata fetch). Used by tile_server_manager
# so it can record marks without changing its public API. Always set/cleared
# from the main thread by BuildingMapDialog._start_map_load.
_active_trace: Optional[MapPerfTrace] = None


def set_active_trace(trace: Optional[MapPerfTrace]) -> None:
    global _active_trace
    _active_trace = trace


def get_active_trace() -> Optional[MapPerfTrace]:
    return _active_trace


def snapshot_active_timers() -> str:
    """Return a one-line string describing currently active QTimers in the app.

    Walks every top-level widget tree (most QTimers in PyQt5 apps are children
    of widgets, not of QApplication, so a plain `app.findChildren(QTimer)`
    misses them). Format: 'OwnerClass@<intervalms> xN' grouped, semicolon-
    separated. Returns 'none' or 'n/a' on empty/no-app.
    """
    try:
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return "n/a"

        seen_ids = set()
        timers = []
        # Top-level widgets — these own most timers.
        for w in app.topLevelWidgets():
            try:
                for t in w.findChildren(QTimer):
                    if id(t) in seen_ids:
                        continue
                    seen_ids.add(id(t))
                    timers.append(t)
            except Exception:
                continue
        # QApplication-owned (rare).
        try:
            for t in app.findChildren(QTimer):
                if id(t) in seen_ids:
                    continue
                seen_ids.add(id(t))
                timers.append(t)
        except Exception:
            pass

        active_descriptors = []
        for t in timers:
            try:
                if not t.isActive():
                    continue
                owner = t.parent()
                cls = type(owner).__name__ if owner is not None else "None"
                active_descriptors.append(f"{cls}@{t.interval()}ms")
            except Exception:
                continue

        if not active_descriptors:
            return "none"

        from collections import Counter
        counts = Counter(active_descriptors)
        parts = [f"{k} x{v}" if v > 1 else k for k, v in counts.most_common()]
        if len(parts) > 30:
            return ";".join(parts[:30]) + f";...(+{len(parts) - 30})"
        return ";".join(parts)
    except Exception as e:
        return f"err:{type(e).__name__}"


class MainThreadHeartbeat:
    """Direct probe of Qt main-thread responsiveness.

    Schedules a QTimer that should fire every `interval_ms` for `duration_ms`
    in total. Each fire records the actual gap to the previous fire; if the
    main thread is starved (event loop blocked), the gap is much larger than
    `interval_ms`. On stop, logs a summary mark with max_stall_ms and the
    histogram of stalls that exceeded a threshold.
    """

    def __init__(self, trace: "MapPerfTrace", parent, interval_ms: int = 50,
                 duration_ms: int = 5000, stall_threshold_ms: float = 100.0):
        from PyQt5.QtCore import QTimer

        self._trace = trace
        self._interval = interval_ms / 1000.0
        self._stall_threshold = stall_threshold_ms / 1000.0
        self._duration_ms = duration_ms
        self._max_stall = 0.0
        self._sum_stall = 0.0
        self._stall_count = 0
        self._fires = 0
        self._last = time.perf_counter()
        self._started_at = self._last
        self._stalls: list = []
        self._timer = QTimer(parent)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        self._last = time.perf_counter()
        self._started_at = self._last
        self._timer.start()

    def _on_tick(self) -> None:
        now = time.perf_counter()
        gap = now - self._last
        self._last = now
        self._fires += 1
        stall = max(0.0, gap - self._interval)
        if stall > 0:
            self._sum_stall += stall
            self._stall_count += 1
        if stall > self._max_stall:
            self._max_stall = stall
        if stall * 1000.0 >= self._stall_threshold * 1000.0:
            self._stalls.append(round(stall * 1000.0))
        if (now - self._started_at) * 1000.0 >= self._duration_ms:
            self.stop()

    def stop(self) -> None:
        if not self._timer.isActive():
            return
        self._timer.stop()
        avg = (self._sum_stall / self._stall_count) if self._stall_count else 0.0
        # Show top 5 worst stalls inline.
        worst = sorted(self._stalls, reverse=True)[:5]
        worst_str = ",".join(str(x) for x in worst) or "-"
        if self._trace:
            self._trace.mark(
                'heartbeat_summary',
                fires=self._fires,
                max_stall_ms=round(self._max_stall * 1000.0, 1),
                avg_stall_ms=round(avg * 1000.0, 1),
                stalls_over_threshold=len(self._stalls),
                worst_stalls_ms=worst_str,
            )


def count_web_engine_views() -> int:
    """Count alive QWebEngineView instances in the application.

    Uses `QApplication.allWidgets()` which lists every QWidget (visible or not,
    parented or not) — so it picks up zombie views from previous closed dialogs
    that haven't been garbage-collected yet. Returns -1 on error.
    """
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return 0
        return sum(1 for w in app.allWidgets() if isinstance(w, QWebEngineView))
    except Exception:
        return -1


def snapshot_running_threads() -> str:
    """Return a one-line string describing currently alive Python/Qt threads.

    Uses `threading.enumerate()` — sees all live Python threads, which includes
    unparented QThread instances (e.g. _BuildingsWorker created with no parent).
    Filters out the main thread. Format: 'name xN' grouped, semicolon-separated.
    """
    try:
        import threading
        try:
            main_id = threading.main_thread().ident
        except Exception:
            main_id = None
        names = []
        for th in threading.enumerate():
            try:
                if not th.is_alive():
                    continue
                if main_id is not None and th.ident == main_id:
                    continue
                # Prefer thread.name; fall back to type if it's a generic 'Thread-N'.
                name = getattr(th, 'name', None) or 'Thread'
                if name.startswith('Thread-') or name.startswith('Dummy-'):
                    name = type(th).__name__
                names.append(name)
            except Exception:
                continue
        if not names:
            return "none"
        from collections import Counter
        counts = Counter(names)
        parts = [f"{k} x{v}" if v > 1 else k for k, v in counts.most_common()]
        if len(parts) > 30:
            return ";".join(parts[:30]) + f";...(+{len(parts) - 30})"
        return ";".join(parts)
    except Exception as e:
        return f"err:{type(e).__name__}"
