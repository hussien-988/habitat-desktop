# -*- coding: utf-8 -*-
"""Reusable animated card base — shimmer sweep, hover lift, shadow transitions,
status strip, directional chevron.  Extracted from _ClaimCard / _SurveyCard."""

import math
import random
import time

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, pyqtSignal, pyqtProperty, QTimer
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QCursor, QLinearGradient, QPainterPath,
    QFont,
)

from PyQt5.QtCore import QRectF, QPropertyAnimation, QEasingCurve, QPoint
from PyQt5.QtWidgets import QGraphicsOpacityEffect

from services.translation_manager import get_layout_direction


class AnimatedCard(QFrame):
    """Base card with shimmer sweep, hover lift, shadow transitions,
    status color strip, and directional chevron.

    Subclasses must override ``_build_content(layout)`` to populate the
    card interior with their own labels / rows.

    Parameters (all optional kwargs in __init__):
        card_height   – fixed height in px (default 110)
        border_radius – corner radius (default 12)
        shimmer_speed – sine multiplier (default 0.7)
        shimmer_width – half-width of shimmer gradient (default 120)
        lift_target   – hover lift in px (default 4.0)
        show_chevron  – draw directional chevron (default True)
        show_strip    – draw left status color strip (default True)
        status_color  – strip colour hex (default "#3890DF")
        strip_width   – status strip width (default 5)
        clickable     – emit clicked / show pointer cursor (default True)
    """

    clicked = pyqtSignal()

    _CARD_BG = "#F7FAFF"
    _CARD_BG_HOVER = "#F0F5FF"

    # -- lift property --------------------------------------------------------
    def _get_lift(self):
        return self._lift_value

    def _set_lift(self, v):
        self._lift_value = v
        lv = int(v)
        self.setContentsMargins(0, max(0, -lv), 0, max(0, lv))
        self.update()

    lift = pyqtProperty(float, _get_lift, _set_lift)

    # -- init -----------------------------------------------------------------
    def __init__(self, parent=None, **kw):
        super().__init__(parent)
        self._card_height = kw.get("card_height", 110)
        self._border_radius = kw.get("border_radius", 12)
        self._shimmer_speed = kw.get("shimmer_speed", 0.7)
        self._shimmer_width = kw.get("shimmer_width", 120)
        self._lift_target = kw.get("lift_target", 4.0)
        self._show_chevron = kw.get("show_chevron", True)
        self._show_strip = kw.get("show_strip", True)
        self._status_color = kw.get("status_color", "#3890DF")
        self._strip_width = kw.get("strip_width", 5)
        self._clickable = kw.get("clickable", True)

        self._hovered = False
        self._pressed = False
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None
        self._entrance_anim = None
        self._entrance_effect = None

        if self._clickable:
            self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(self._card_height)
        self.setMouseTracking(True)

        self._apply_base_style()
        self._apply_shadow_rest()
        self._init_layout()

    # -- styling helpers ------------------------------------------------------
    def _class_name(self):
        return type(self).__name__

    def _apply_base_style(self):
        r = self._border_radius
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(
            f"{self._class_name()} {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"    stop:0 {self._CARD_BG}, stop:1 #F0F5FF);"
            f"  border-radius: {r}px;"
            f"  border: 1px solid #E2EAF2;"
            f"}}"
        )

    def _apply_hover_style(self):
        r = self._border_radius
        self.setStyleSheet(
            f"{self._class_name()} {{"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"    stop:0 {self._CARD_BG_HOVER}, stop:1 #E8F0FE);"
            f"  border-radius: {r}px;"
            f"  border: 1.5px solid rgba(56,144,223,0.30);"
            f"}}"
        )

    def _apply_shadow_rest(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 22))
        self.setGraphicsEffect(shadow)

    # -- layout ---------------------------------------------------------------
    def _init_layout(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 20, 0)
        outer.setSpacing(0)

        # Status strip
        if self._show_strip:
            strip = QFrame()
            strip.setFixedWidth(self._strip_width)
            is_rtl = get_layout_direction() == Qt.RightToLeft
            tl = self._border_radius if not is_rtl else 0
            bl = self._border_radius if not is_rtl else 0
            tr_ = self._border_radius if is_rtl else 0
            br = self._border_radius if is_rtl else 0
            strip.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                f"  stop:0 {self._status_color}, stop:0.5 {self._status_color}80,"
                f"  stop:1 {self._status_color});"
                f"border-top-left-radius: {tl}px;"
                f"border-bottom-left-radius: {bl}px;"
                f"border-top-right-radius: {tr_}px;"
                f"border-bottom-right-radius: {br}px;"
            )
            self._strip_widget = strip
            outer.addWidget(strip)

        # Content area
        content = QVBoxLayout()
        content.setContentsMargins(18, 12, 0, 12)
        content.setSpacing(4)
        self._build_content(content)
        outer.addLayout(content, 1)

    def _build_content(self, layout: QVBoxLayout):
        """Override in subclasses to populate the card interior."""
        pass

    # -- public helpers -------------------------------------------------------
    def set_status_color(self, color: str):
        """Change the strip colour after construction."""
        self._status_color = color
        if hasattr(self, "_strip_widget"):
            is_rtl = get_layout_direction() == Qt.RightToLeft
            tl = self._border_radius if not is_rtl else 0
            bl = self._border_radius if not is_rtl else 0
            tr_ = self._border_radius if is_rtl else 0
            br = self._border_radius if is_rtl else 0
            self._strip_widget.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                f"  stop:0 {color}, stop:0.5 {color}80, stop:1 {color});"
                f"border-top-left-radius: {tl}px;"
                f"border-bottom-left-radius: {bl}px;"
                f"border-top-right-radius: {tr_}px;"
                f"border-bottom-right-radius: {br}px;"
            )

    # -- painting (shimmer + top accent + chevron) ----------------------------
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time()
        r = self._border_radius

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), r - 1, r - 1)
        painter.setClipPath(clip)

        # Subtle cartographic grid
        painter.setPen(QPen(QColor(56, 144, 223, 5), 0.5))
        for gx in range(0, w + 60, 60):
            painter.drawLine(gx, 0, gx, h)
        for gy in range(0, h + 60, 60):
            painter.drawLine(0, gy, w, gy)

        # Animated shimmer sweep
        sweep_pos = (math.sin(t * self._shimmer_speed + self._shimmer_offset) + 1) / 2
        sweep_x = int(sweep_pos * w)
        sw = self._shimmer_width
        shimmer = QLinearGradient(sweep_x - sw, 0, sweep_x + sw, 0)
        shimmer.setColorAt(0, QColor(56, 144, 223, 0))
        shimmer.setColorAt(0.5, QColor(120, 190, 255, 10))
        shimmer.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.fillRect(QRectF(0, 0, w, h), shimmer)

        # Top edge accent on hover
        if self._hovered:
            top = QLinearGradient(0, 0, w, 0)
            top.setColorAt(0, QColor(56, 144, 223, 0))
            top.setColorAt(0.2, QColor(56, 144, 223, 40))
            top.setColorAt(0.5, QColor(91, 168, 240, 65))
            top.setColorAt(0.8, QColor(56, 144, 223, 40))
            top.setColorAt(1, QColor(56, 144, 223, 0))
            painter.fillRect(QRectF(0, 0, w, 2.5), top)

        painter.setClipping(False)

        # Directional chevron
        if self._show_chevron:
            is_rtl = self.layoutDirection() == Qt.RightToLeft
            cx = 16 if is_rtl else w - 24
            alpha = 160 if self._hovered else 40
            painter.setPen(QPen(
                QColor(56, 144, 223, alpha), 1.8,
                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin,
            ))
            cy = h / 2
            if is_rtl:
                painter.drawLine(int(cx + 6), int(cy - 5), int(cx), int(cy))
                painter.drawLine(int(cx), int(cy), int(cx + 6), int(cy + 5))
            else:
                painter.drawLine(int(cx), int(cy - 5), int(cx + 6), int(cy))
                painter.drawLine(int(cx + 6), int(cy), int(cx), int(cy + 5))

        painter.end()

    # -- hover / lift ---------------------------------------------------------
    def _animate_lift(self, target):
        if self._lift_anim and self._lift_anim.state() == QPropertyAnimation.Running:
            self._lift_anim.stop()
        self._lift_anim = QPropertyAnimation(self, b"lift")
        self._lift_anim.setDuration(180)
        self._lift_anim.setStartValue(self._lift_value)
        self._lift_anim.setEndValue(target)
        self._lift_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._lift_anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self._apply_hover_style()
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(36)
            eff.setOffset(0, 8)
            eff.setColor(QColor(56, 144, 223, 40))
        self._animate_lift(self._lift_target)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self._apply_base_style()
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(20)
            eff.setOffset(0, 4)
            eff.setColor(QColor(0, 0, 0, 22))
        self._animate_lift(0.0)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            eff = self.graphicsEffect()
            if isinstance(eff, QGraphicsDropShadowEffect):
                eff.setBlurRadius(8)
                eff.setOffset(0, 1)
                eff.setColor(QColor(0, 0, 0, 18))
            if self._clickable:
                self.clicked.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            eff = self.graphicsEffect()
            if isinstance(eff, QGraphicsDropShadowEffect):
                if self._hovered:
                    eff.setBlurRadius(36)
                    eff.setOffset(0, 8)
                    eff.setColor(QColor(56, 144, 223, 40))
                else:
                    eff.setBlurRadius(20)
                    eff.setOffset(0, 4)
                    eff.setColor(QColor(0, 0, 0, 22))
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
#  _EmptyStateAnimated — Dark navy cartographic empty state (reusable)
# ---------------------------------------------------------------------------

class EmptyStateAnimated(QFrame):
    """Dark-themed empty state with constellation particles, cartographic
    motifs, folder icon, and shimmer sweep.  Set title / description via
    ``set_title()`` / ``set_description()``."""

    def __init__(self, title: str = "", description: str = "", parent=None):
        super().__init__(parent)
        self._title_text = title
        self._desc_text = description
        self._anim_start = time.time()

        self._shimmer_pos = 0.0
        self._shimmer_anim = QPropertyAnimation(self, b"shimmerPos")
        self._shimmer_anim.setDuration(2500)
        self._shimmer_anim.setStartValue(0.0)
        self._shimmer_anim.setEndValue(1.0)
        self._shimmer_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._shimmer_anim.setLoopCount(-1)
        self._shimmer_anim.start()

        random.seed(77)
        self._particles = []
        for _ in range(12):
            self._particles.append({
                "x": random.uniform(0.05, 0.95),
                "y": random.uniform(0.05, 0.95),
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(0.3, 0.8),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    @pyqtProperty(float)
    def shimmerPos(self):
        return self._shimmer_pos

    @shimmerPos.setter
    def shimmerPos(self, val):
        self._shimmer_pos = val
        self.update()

    def set_title(self, text: str):
        self._title_text = text
        self.update()

    def set_description(self, text: str):
        self._desc_text = text
        self.update()

    def paintEvent(self, event):
        from ui.font_utils import create_font, FontManager
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self._anim_start

        # Dark navy gradient
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0.0, QColor("#0E2035"))
        bg.setColorAt(0.5, QColor("#132D50"))
        bg.setColorAt(1.0, QColor("#1A3860"))
        painter.fillRect(0, 0, w, h, bg)

        # Grid
        painter.setPen(QPen(QColor(56, 144, 223, 12), 0.5))
        for x in range(0, w, 60):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 60):
            painter.drawLine(0, y, w, y)

        # Particles
        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.012 * math.sin(t * p["speed"] + p["phase"])) * w)
            py = int((p["y"] + 0.010 * math.cos(t * p["speed"] * 0.7 + p["phase"])) * h)
            px = max(4, min(w - 4, px))
            py = max(4, min(h - 4, py))
            positions.append((px, py))
            alpha = 35 + int(18 * math.sin(t * 1.5 + p["phase"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 150:
                    alpha = int(12 * (1 - dist / 150))
                    painter.setPen(QPen(QColor(139, 172, 200, alpha), 1))
                    painter.drawLine(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1],
                    )

        cx, cy_c = w // 2, int(h * 0.40)
        fw, fh = 110, 80

        # Breathing glow
        from PyQt5.QtGui import QRadialGradient
        glow_alpha = 20 + int(12 * math.sin(t * 0.8))
        glow = QRadialGradient(cx, cy_c, 100)
        glow.setColorAt(0, QColor(56, 144, 223, glow_alpha))
        glow.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(cx - 100, cy_c - 100, 200, 200)

        # Concentric circles
        for i, radius in enumerate([40, 65, 90]):
            alpha = int(15 + 8 * math.sin(t * 0.4 + i * 1.2))
            painter.setPen(QPen(QColor(56, 144, 223, alpha), 0.8))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - radius, cy_c - radius, radius * 2, radius * 2)

        # Crosshairs
        cross_alpha = int(12 + 6 * math.sin(t * 0.3))
        painter.setPen(QPen(QColor(56, 144, 223, cross_alpha), 0.5))
        painter.drawLine(cx - 100, cy_c, cx - 55, cy_c)
        painter.drawLine(cx + 55, cy_c, cx + 100, cy_c)
        painter.drawLine(cx, cy_c - 85, cx, cy_c - 50)
        painter.drawLine(cx, cy_c + 50, cx, cy_c + 85)

        # Folder body
        folder = QPainterPath()
        folder.moveTo(cx - fw // 2, cy_c - fh // 2 + 16)
        folder.lineTo(cx - fw // 2, cy_c + fh // 2)
        folder.lineTo(cx + fw // 2, cy_c + fh // 2)
        folder.lineTo(cx + fw // 2, cy_c - fh // 2 + 16)
        folder.closeSubpath()
        painter.setPen(QPen(QColor(56, 144, 223, 40), 1.5))
        painter.setBrush(QColor(15, 31, 61, 180))
        painter.drawPath(folder)

        # Folder tab
        tab = QPainterPath()
        tab.moveTo(cx - fw // 2, cy_c - fh // 2 + 16)
        tab.lineTo(cx - fw // 2, cy_c - fh // 2 + 4)
        tab.lineTo(cx - fw // 2 + 4, cy_c - fh // 2)
        tab.lineTo(cx - 12, cy_c - fh // 2)
        tab.lineTo(cx - 8, cy_c - fh // 2 + 8)
        tab.lineTo(cx + 8, cy_c - fh // 2 + 8)
        tab.lineTo(cx + 12, cy_c - fh // 2 + 16)
        tab.closeSubpath()
        painter.setPen(QPen(QColor(56, 144, 223, 40), 1.5))
        painter.setBrush(QColor(20, 40, 70, 200))
        painter.drawPath(tab)

        # Documents
        doc_x, doc_y = cx - 18, cy_c - fh // 2 + 24
        for i in range(2):
            dx = doc_x + i * 14
            dy = doc_y + i * 5
            painter.setPen(QPen(QColor(56, 144, 223, 30), 1))
            painter.setBrush(QColor(25, 50, 85))
            painter.drawRoundedRect(QRectF(dx, dy, 30, 38), 3, 3)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(56, 144, 223, 25))
            for line_y in range(3):
                lw = 20 if line_y < 2 else 13
                painter.drawRect(QRectF(dx + 5, dy + 9 + line_y * 8, lw, 2))

        # Ground shadow
        painter.setPen(QPen(QColor(56, 144, 223, 20), 1))
        painter.drawLine(cx - fw // 2 + 8, cy_c + fh // 2 + 3,
                         cx + fw // 2 - 8, cy_c + fh // 2 + 3)

        # Shimmer sweep on folder
        shimmer_x = int((self._shimmer_pos * 2 - 0.5) * fw + cx - fw // 2)
        sg = QLinearGradient(shimmer_x - 30, 0, shimmer_x + 30, 0)
        sg.setColorAt(0, QColor(56, 144, 223, 0))
        sg.setColorAt(0.5, QColor(91, 168, 240, 50))
        sg.setColorAt(1, QColor(56, 144, 223, 0))
        cp = QPainterPath()
        cp.addRect(QRectF(cx - fw // 2, cy_c - fh // 2, fw, fh))
        painter.setClipPath(cp)
        painter.setPen(Qt.NoPen)
        painter.setBrush(sg)
        painter.drawRect(shimmer_x - 30, cy_c - fh // 2, 60, fh)
        painter.setClipping(False)

        # Title
        painter.setFont(create_font(size=FontManager.SIZE_TITLE, weight=QFont.DemiBold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            QRectF(0, cy_c + fh // 2 + 28, w, 30),
            Qt.AlignCenter, self._title_text,
        )

        # Description
        painter.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        painter.setPen(QColor(139, 172, 200, 200))
        painter.drawText(
            QRectF(w * 0.2, cy_c + fh // 2 + 62, w * 0.6, 40),
            Qt.AlignCenter | Qt.TextWordWrap, self._desc_text,
        )

        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()


# ---------------------------------------------------------------------------
#  Utilities for page-level card management
# ---------------------------------------------------------------------------

def animate_card_entrance(cards: list, parent=None):
    """Stagger fade-in entrance for a list of AnimatedCard widgets.
    300ms per card, 40ms stagger, OutCubic.  Restores shadow after."""
    count = len(cards)
    if count > 30 or count == 0:
        return
    for i, card in enumerate(cards):
        opacity_eff = QGraphicsOpacityEffect(card)
        opacity_eff.setOpacity(0.0)
        card.setGraphicsEffect(opacity_eff)

        anim = QPropertyAnimation(opacity_eff, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _restore(c=card):
            s = QGraphicsDropShadowEffect(c)
            s.setBlurRadius(20)
            s.setOffset(0, 4)
            s.setColor(QColor(0, 0, 0, 22))
            c.setGraphicsEffect(s)

        anim.finished.connect(_restore)
        QTimer.singleShot(i * 40, anim.start)

        card._entrance_anim = anim
        card._entrance_effect = opacity_eff
