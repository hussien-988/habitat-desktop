# -*- coding: utf-8 -*-
"""
Branded loading spinner overlay with cartographic authority aesthetic.
Features app logo with orbital ring, radial glow, constellation particles,
and expressive loading text.
"""
import math
import random
import time
from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, QTimer, QRectF, QEvent, QPoint, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QPixmap, QRadialGradient,
    QLinearGradient, QIcon,
)

from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction

_DEFAULT_TIMEOUT_MS = 30_000

# Particle seed for deterministic constellation
_PARTICLE_SEED = 42
_PARTICLE_COUNT = 12

# Animation timing
_FRAME_INTERVAL_MS = 30  # ~33fps


class _BrandedSpinnerWidget(QWidget):
    """Animated spinner with app logo, orbital ring, glow, and particles."""

    def __init__(self, logo_size: int = 64, ring_radius: int = 52, parent=None):
        super().__init__(parent)
        self._logo_size = logo_size
        self._ring_radius = ring_radius
        widget_size = ring_radius * 2 + 32
        self.setFixedSize(widget_size, widget_size)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._logo_pixmap = self._load_logo(logo_size)
        self._anim_start = time.time()
        self._particles = self._init_particles()

        # Arc colors
        self._arc_color = QColor(56, 144, 223)  # #3890DF
        self._arc_color_secondary = QColor(100, 180, 240)
        self._glow_color = QColor(56, 144, 223)
        self._particle_color = QColor(139, 172, 200)

        self._timer = QTimer(self)
        self._timer.setInterval(_FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    @staticmethod
    def _load_logo(size: int) -> Optional[QPixmap]:
        """Load app.ico and scale to desired size."""
        import os
        ico_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "assets", "images", "app.ico"
        )
        ico_path = os.path.normpath(ico_path)
        if os.path.exists(ico_path):
            icon = QIcon(ico_path)
            if not icon.isNull():
                return icon.pixmap(QSize(size, size))
        return None

    @staticmethod
    def _init_particles():
        """Create deterministic constellation particles."""
        rng = random.Random(_PARTICLE_SEED)
        particles = []
        for _ in range(_PARTICLE_COUNT):
            particles.append({
                "angle": rng.uniform(0, math.tau),
                "dist": rng.uniform(0.55, 0.95),
                "speed": rng.uniform(0.15, 0.45) * rng.choice([-1, 1]),
                "phase": rng.uniform(0, math.tau),
                "size": rng.uniform(1.2, 2.2),
            })
        return particles

    def start(self):
        self._anim_start = time.time()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _tick(self):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        t = time.time() - self._anim_start
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        # 1. Radial glow behind logo (breathing)
        glow_alpha = 25 + int(18 * math.sin(t * 1.3))
        glow_r = self._ring_radius + 16
        glow_grad = QRadialGradient(cx, cy, glow_r)
        glow_grad.setColorAt(0.0, QColor(56, 144, 223, glow_alpha + 15))
        glow_grad.setColorAt(0.4, QColor(56, 144, 223, glow_alpha))
        glow_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow_grad)
        painter.drawEllipse(QPoint(int(cx), int(cy)), glow_r, glow_r)

        # 2. Constellation particles
        painter.setPen(Qt.NoPen)
        positions = []
        half = w / 2
        for p in self._particles:
            angle = p["angle"] + t * p["speed"]
            dist = p["dist"] * half
            # Gentle oscillation on distance
            dist += 3 * math.sin(t * 0.8 + p["phase"])
            px = cx + dist * math.cos(angle)
            py = cy + dist * math.sin(angle)
            positions.append((int(px), int(py)))
            alpha = 45 + int(25 * math.sin(t * 1.5 + p["phase"]))
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(int(px), int(py)),
                                int(p["size"]), int(p["size"]))

        # Connecting lines between nearby particles
        painter.setPen(QPen(QColor(139, 172, 200, 14), 1))
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 65:
                    painter.drawLine(positions[i][0], positions[i][1],
                                     positions[j][0], positions[j][1])

        # 3. Track ring (faint circle behind the arc)
        track_pen = QPen(QColor(56, 144, 223, 20), 2.5)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.NoBrush)
        ring_rect = QRectF(
            cx - self._ring_radius, cy - self._ring_radius,
            self._ring_radius * 2, self._ring_radius * 2,
        )
        painter.drawEllipse(ring_rect)

        # 4. Primary rotating arc
        arc_pen = QPen(self._arc_color, 3)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        start_angle = int((t * 120) % 360 * 16)
        span_angle = 100 * 16
        painter.drawArc(ring_rect, start_angle, span_angle)

        # 5. Secondary counter-rotating arc (thinner, lighter)
        arc_pen2 = QPen(QColor(100, 180, 240, 90), 1.5)
        arc_pen2.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen2)
        start2 = int((-t * 80 + 180) % 360 * 16)
        span2 = 60 * 16
        painter.drawArc(ring_rect, start2, span2)

        # 6. Outer faint orbital dots
        painter.setPen(Qt.NoPen)
        for i in range(3):
            dot_angle = t * 0.6 + i * (math.tau / 3)
            dot_r = self._ring_radius + 10
            dot_x = cx + dot_r * math.cos(dot_angle)
            dot_y = cy + dot_r * math.sin(dot_angle)
            dot_alpha = 35 + int(20 * math.sin(t * 2 + i))
            painter.setBrush(QColor(56, 144, 223, dot_alpha))
            painter.drawEllipse(QPoint(int(dot_x), int(dot_y)), 2, 2)

        # 7. Logo in center with subtle pulse
        if self._logo_pixmap and not self._logo_pixmap.isNull():
            pulse = 1.0 + 0.04 * math.sin(t * 2.0)
            scaled_size = int(self._logo_size * pulse)
            logo_x = int(cx - scaled_size / 2)
            logo_y = int(cy - scaled_size / 2)
            scaled = self._logo_pixmap.scaled(
                scaled_size, scaled_size,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            painter.drawPixmap(logo_x, logo_y, scaled)
        else:
            # Fallback: draw UN-Habitat text if logo not found
            painter.setPen(QColor(255, 255, 255, 200))
            painter.setFont(create_font(size=10, weight=FontManager.WEIGHT_BOLD))
            painter.drawText(
                QRectF(cx - 30, cy - 10, 60, 20),
                Qt.AlignCenter, "UN"
            )

        painter.end()


class LoadingSpinnerOverlay(QWidget):
    """Branded dark overlay with logo spinner, text, and constellation.

    Features:
    - App logo with orbital ring animation
    - Radial breathing glow effect
    - Constellation particle background
    - Expressive loading text
    - Safety timeout (default 30s) to prevent infinite hang
    - Reentrant guard prevents double-loading
    """

    def __init__(self, parent: Optional[QWidget] = None,
                 timeout_ms: int = _DEFAULT_TIMEOUT_MS) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self._is_loading = False
        self._anim_start = time.time()

        # Background particles (larger set for overlay background)
        rng = random.Random(77)
        self._bg_particles = []
        for _ in range(20):
            self._bg_particles.append({
                "x": rng.uniform(0.05, 0.95),
                "y": rng.uniform(0.05, 0.95),
                "dx": rng.uniform(0.2, 0.6) * rng.choice([-1, 1]),
                "dy": rng.uniform(0.15, 0.5) * rng.choice([-1, 1]),
                "phase": rng.uniform(0, math.tau),
            })

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        # Spinner widget
        self._spinner = _BrandedSpinnerWidget(
            logo_size=64, ring_radius=52, parent=self
        )
        layout.addWidget(self._spinner, 0, Qt.AlignCenter)

        # Primary message label
        self._label = QLabel(tr("component.loading.default"))
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.92); background: transparent;"
            "padding: 0px 20px;"
        )
        self._label.setLayoutDirection(get_layout_direction())
        layout.addWidget(self._label, 0, Qt.AlignCenter)

        # Subtitle label
        self._subtitle = QLabel("")
        self._subtitle.setAlignment(Qt.AlignCenter)
        self._subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._subtitle.setStyleSheet(
            "color: rgba(160, 190, 220, 0.7); background: transparent;"
        )
        self._subtitle.setLayoutDirection(get_layout_direction())
        self._subtitle.hide()
        layout.addWidget(self._subtitle, 0, Qt.AlignCenter)

        # Background animation timer
        self._bg_timer = QTimer(self)
        self._bg_timer.setInterval(_FRAME_INTERVAL_MS)
        self._bg_timer.timeout.connect(self._bg_tick)

        # Safety timeout timer
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self.hide_loading)
        self._timeout_ms = timeout_ms

        if parent:
            parent.installEventFilter(self)

        self.hide()

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    def _bg_tick(self):
        self.update()

    def show_loading(self, message: str = None, subtitle: str = None) -> None:
        """Show overlay with branded spinner and message.

        Args:
            message: Primary message text (or default from translations)
            subtitle: Optional secondary text below primary message
        """
        self._is_loading = True
        self._anim_start = time.time()
        self._label.setText(message or tr("component.loading.default"))
        self._label.setLayoutDirection(get_layout_direction())

        if subtitle:
            self._subtitle.setText(subtitle)
            self._subtitle.setLayoutDirection(get_layout_direction())
            self._subtitle.show()
        else:
            self._subtitle.hide()

        self._resize_to_parent()

        self._spinner.start()
        self._bg_timer.start()
        self.show()
        self.raise_()

        self._timeout_timer.start(self._timeout_ms)
        QApplication.processEvents()
        self._resize_to_parent()
        QTimer.singleShot(0, self._resize_to_parent)

    def _resize_to_parent(self) -> None:
        """Resize overlay to match the visible area of the parent widget.

        Falls back to the top-level window when the parent has not been laid
        out yet (e.g. when show_loading is called before the step becomes the
        current widget in a QStackedWidget).
        """
        parent = self.parent()
        if not (parent and isinstance(parent, QWidget)):
            return
        if parent.layout() is not None:
            parent.layout().activate()
        rect = parent.rect()
        if rect.width() < 100 or rect.height() < 100:
            top = parent.window()
            if top is not None and top is not parent:
                top_rect = top.rect()
                if top_rect.width() >= 100 and top_rect.height() >= 100:
                    top_left = parent.mapFromGlobal(top.mapToGlobal(top_rect.topLeft()))
                    self.setGeometry(top_left.x(), top_left.y(),
                                     top_rect.width(), top_rect.height())
                    return
        self.setGeometry(rect)

    def hide_loading(self) -> None:
        """Hide overlay and stop all animations. Safe to call even if not showing."""
        self._timeout_timer.stop()
        self._bg_timer.stop()
        self._spinner.stop()
        self._is_loading = False
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        t = time.time() - self._anim_start

        # Deep navy gradient overlay
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor(10, 22, 40, 215))
        grad.setColorAt(0.5, QColor(15, 30, 55, 220))
        grad.setColorAt(1.0, QColor(18, 36, 65, 215))
        painter.fillRect(self.rect(), grad)

        # Faint cadastral grid
        grid_spacing = 80
        painter.setPen(QPen(QColor(56, 144, 223, 8), 1))
        x = grid_spacing
        while x < w:
            painter.drawLine(x, 0, x, h)
            x += grid_spacing
        y = grid_spacing
        while y < h:
            painter.drawLine(0, y, w, y)
            y += grid_spacing

        # Background constellation particles
        painter.setPen(Qt.NoPen)
        positions = []
        for p in self._bg_particles:
            px = int((p["x"] + 0.008 * math.sin(t * p["dx"] + p["phase"])) * w)
            py = int((p["y"] + 0.006 * math.cos(t * p["dy"] + p["phase"])) * h)
            px = max(2, min(w - 2, px))
            py = max(2, min(h - 2, py))
            positions.append((px, py))
            alpha = 30 + int(15 * math.sin(t * 1.2 + p["phase"]))
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        # Constellation connecting lines
        painter.setPen(QPen(QColor(139, 172, 200, 10), 1))
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 160:
                    painter.drawLine(positions[i][0], positions[i][1],
                                     positions[j][0], positions[j][1])

        # Ambient center glow
        center_x, center_y = w // 2, h // 2 - 20
        ambient_r = 200
        ambient_alpha = 10 + int(6 * math.sin(t * 0.9))
        ambient_grad = QRadialGradient(center_x, center_y, ambient_r)
        ambient_grad.setColorAt(0.0, QColor(56, 144, 223, ambient_alpha + 8))
        ambient_grad.setColorAt(0.6, QColor(56, 144, 223, ambient_alpha))
        ambient_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(ambient_grad)
        painter.drawEllipse(QPoint(center_x, center_y), ambient_r, ambient_r)

        # Bottom accent line
        line_y = h - 2
        line_grad = QLinearGradient(0, line_y, w, line_y)
        line_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
        line_grad.setColorAt(0.3, QColor(56, 144, 223, 15))
        line_grad.setColorAt(0.5, QColor(56, 144, 223, 30))
        line_grad.setColorAt(0.7, QColor(56, 144, 223, 15))
        line_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(QPen(line_grad, 1))
        painter.drawLine(0, line_y, w, line_y)

        painter.end()
        super().paintEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.parent() and event.type() in (QEvent.Resize, QEvent.Show):
            if self.isVisible():
                self._resize_to_parent()
                self.raise_()
        return super().eventFilter(obj, event)
