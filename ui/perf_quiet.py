# -*- coding: utf-8 -*-
"""App-wide visual quietening: disables decorative shadows and animations.

Apply once at app startup, before any UI is created.
"""

from __future__ import annotations

_APPLIED = False


def apply_global_perf_quietening() -> None:
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    try:
        from PyQt5.QtCore import QPropertyAnimation, QTimer
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGraphicsEffect
    except Exception:
        return

    if not getattr(QPropertyAnimation, "_perf_quiet", False):
        _orig_start = QPropertyAnimation.start

        def _quiet_start(self, *args, **kwargs):
            try:
                self.setDuration(1)
                self.setLoopCount(1)
            except Exception:
                pass
            return _orig_start(self, *args, **kwargs)

        QPropertyAnimation.start = _quiet_start
        QPropertyAnimation._perf_quiet = True

    if not getattr(QGraphicsDropShadowEffect, "_perf_quiet", False):
        _orig_eff_init = QGraphicsDropShadowEffect.__init__

        def _quiet_eff_init(self, *args, **kwargs):
            _orig_eff_init(self, *args, **kwargs)
            try:
                QGraphicsEffect.setEnabled(self, False)
            except Exception:
                pass

        def _quiet_eff_setEnabled(self, _enabled):
            try:
                QGraphicsEffect.setEnabled(self, False)
            except Exception:
                pass

        QGraphicsDropShadowEffect.__init__ = _quiet_eff_init
        QGraphicsDropShadowEffect.setEnabled = _quiet_eff_setEnabled
        QGraphicsDropShadowEffect._perf_quiet = True


def quieten_widget_tree(root) -> None:
    if root is None:
        return
    try:
        from PyQt5.QtCore import QPropertyAnimation, QTimer
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QWidget
    except Exception:
        return

    try:
        widgets = [root] + root.findChildren(QWidget)
    except Exception:
        widgets = [root]
    for w in widgets:
        try:
            eff = w.graphicsEffect()
        except RuntimeError:
            continue
        if isinstance(eff, QGraphicsDropShadowEffect):
            try:
                eff.setEnabled(False)
            except RuntimeError:
                pass

    try:
        anims = root.findChildren(QPropertyAnimation)
    except Exception:
        anims = []
    for a in anims:
        try:
            a.stop()
            a.setLoopCount(1)
            a.setDuration(1)
        except RuntimeError:
            pass

    for w in widgets:
        for attr in ("_shimmer_timer",):
            t = getattr(w, attr, None)
            if isinstance(t, QTimer):
                try:
                    if t.isActive():
                        t.stop()
                    t.blockSignals(True)
                except RuntimeError:
                    pass
