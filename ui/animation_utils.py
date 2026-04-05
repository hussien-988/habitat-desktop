# -*- coding: utf-8 -*-
"""Shared animation utilities for consistent motion throughout the app."""

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QWidget

from ui.design_system import AnimationTimings


def _ensure_opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    effect = widget.findChild(QGraphicsOpacityEffect)
    if not effect:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    return effect


def fade_in(widget: QWidget, duration: int = AnimationTimings.FADE_IN,
            callback=None) -> QPropertyAnimation:
    effect = _ensure_opacity_effect(widget)
    effect.setOpacity(0.0)
    widget.show()
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    if callback:
        anim.finished.connect(callback)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def fade_out(widget: QWidget, duration: int = AnimationTimings.FADE_OUT,
             callback=None) -> QPropertyAnimation:
    effect = _ensure_opacity_effect(widget)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.InCubic)
    if callback:
        anim.finished.connect(callback)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def slide_down(widget: QWidget, distance: int = 40,
               duration: int = AnimationTimings.SLIDE_DOWN,
               callback=None) -> QPropertyAnimation:
    target_pos = widget.pos()
    start_pos = target_pos - QPoint(0, distance)
    widget.move(start_pos)
    widget.show()
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    anim.setStartValue(start_pos)
    anim.setEndValue(target_pos)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    if callback:
        anim.finished.connect(callback)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def slide_up(widget: QWidget, distance: int = None,
             duration: int = AnimationTimings.SLIDE_UP,
             callback=None) -> QPropertyAnimation:
    if distance is None:
        distance = widget.height()
    target_pos = widget.pos()
    start_pos = target_pos + QPoint(0, distance)
    widget.move(start_pos)
    widget.show()
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(duration)
    anim.setStartValue(start_pos)
    anim.setEndValue(target_pos)
    anim.setEasingCurve(QEasingCurve.OutQuart)
    if callback:
        anim.finished.connect(callback)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def stagger_fade_in(widgets, stagger_ms: int = AnimationTimings.ROW_STAGGER,
                    duration: int = AnimationTimings.FADE_IN):
    """Fade in a list of widgets one after another with stagger delay."""
    _anims = []
    for i, widget in enumerate(widgets):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        widget.show()

        def _start_anim(w=widget, e=effect):
            try:
                # Guard: widget or effect may have been deleted if page navigated away
                w.isVisible()
                e.opacity()
            except RuntimeError:
                return
            anim = QPropertyAnimation(e, b"opacity", w)
            anim.setDuration(duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda ww=w: ww.setGraphicsEffect(None))
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            _anims.append(anim)

        QTimer.singleShot(i * stagger_ms, _start_anim)
    return _anims
