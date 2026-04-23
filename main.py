#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TRRCMS - Tenure Rights Registration & Claims Management System
Main entry point for the application
"""

import math
import os
import random
import sys
import time
from pathlib import Path

# Enable Chromium WebEngine in Wine/CrossOver environments on macOS
if sys.platform == 'darwin':
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--no-sandbox')

# Add trrcms directory to Python path
trrcms_path = Path(__file__).parent / "trrcms"
sys.path.insert(0, str(trrcms_path))


from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import (
    QPixmap, QColor, QPainter, QFont, QFontDatabase,
    QLinearGradient, QRadialGradient, QPen, QPainterPath,
)

from app.config import Config, get_saved_language
from app import MainWindow
from repositories.database import Database
from utils.logger import setup_logger
from ui.font_utils import set_application_default_font


class AnimatedSplash(QSplashScreen):
    """Refined institutional splash with constellation, orbital ring,
    and progress bar."""

    WIDTH, HEIGHT = 560, 400
    _FONT = "Noto Kufi Arabic"
    _RADIUS = 14

    # Vertical layout positions (generous spacing to prevent overlap)
    _LOGO_Y = 30
    _LOGO_SIZE = 80
    _LOGO_CENTER_Y = _LOGO_Y + _LOGO_SIZE // 2          # 70
    _TITLE_Y = _LOGO_Y + _LOGO_SIZE + 20                 # 130
    _TITLE_H = 40
    _SUB_EN_Y = _TITLE_Y + _TITLE_H + 4                  # 174
    _SUB_EN_H = 28
    _SUB_AR_Y = _SUB_EN_Y + _SUB_EN_H + 4                # 206
    _SUB_AR_H = 28
    _SEP_Y = _SUB_AR_Y + _SUB_AR_H + 14                  # 248
    _BAR_Y = _SEP_Y + 22                                  # 270
    _STATUS_Y = HEIGHT - 35                                # 365

    def __init__(self):
        self._logo_pixmap = None
        self._load_fonts()

        logo_path = Path(__file__).parent / "assets" / "images" / "Layer_1.png"
        if logo_path.exists():
            px = QPixmap(str(logo_path))
            if not px.isNull():
                self._logo_pixmap = px.scaled(
                    self._LOGO_SIZE, self._LOGO_SIZE,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )

        bg = self._create_background()
        super().__init__(bg)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self._start_time = None
        self._glow_phase = 0.0
        self._fade_in = 0.0
        self._status_msg = ""
        self._progress = 0.0

        # Constellation particles (deterministic seed for consistency)
        random.seed(42)
        self._particles = []
        for _ in range(14):
            self._particles.append((
                random.uniform(30, self.WIDTH - 30),
                random.uniform(30, self.HEIGHT - 30),
                random.uniform(8, 22),
                random.uniform(0.3, 0.7),
                random.uniform(0, math.tau),
            ))

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)

    def _load_fonts(self):
        fonts_dir = Path(__file__).parent / "assets" / "fonts" / "Noto_Kufi_Arabic"
        for name in ("NotoKufiArabic-Regular.ttf", "NotoKufiArabic-Bold.ttf",
                     "NotoKufiArabic-SemiBold.ttf", "NotoKufiArabic-Medium.ttf"):
            fp = fonts_dir / name
            if fp.exists():
                QFontDatabase.addApplicationFont(str(fp))

    def show(self):
        super().show()
        self._start_time = time.time()
        self._pulse_timer.start(33)

    def set_progress(self, value: float):
        self._progress = max(0.0, min(1.0, value))
        self.repaint()

    def _create_background(self):
        w, h = self.WIDTH, self.HEIGHT
        r = self._RADIUS
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        # Clip to rounded rect
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, r, r)
        p.setClipPath(clip)

        # Deep navy gradient
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor("#0A1628"))
        bg.setColorAt(0.45, QColor("#0F1F3D"))
        bg.setColorAt(1.0, QColor("#162B4D"))
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRect(0, 0, w, h)

        # Geometric grid overlay
        grid_pen = QPen(QColor(26, 50, 88, 15), 0.5)
        p.setPen(grid_pen)
        spacing = 50
        for x in range(0, w + 1, spacing):
            p.drawLine(x, 0, x, h)
        for y in range(0, h + 1, spacing):
            p.drawLine(0, y, w, y)

        # Diamond accents at intersections
        p.setPen(QPen(QColor(56, 144, 223, 12), 0.5))
        p.setBrush(Qt.NoBrush)
        for x in range(0, w + 1, spacing):
            for y in range(0, h + 1, spacing):
                dp = QPainterPath()
                dp.moveTo(x, y - 3)
                dp.lineTo(x + 3, y)
                dp.lineTo(x, y + 3)
                dp.lineTo(x - 3, y)
                dp.closeSubpath()
                p.drawPath(dp)

        # Inner vignette
        vig = QRadialGradient(w / 2, h / 2, max(w, h) * 0.7)
        vig.setColorAt(0.0, QColor(0, 0, 0, 0))
        vig.setColorAt(0.7, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 45))
        p.setPen(Qt.NoPen)
        p.setBrush(vig)
        p.drawRect(0, 0, w, h)

        p.setClipping(False)

        # Accent border
        bg2 = QLinearGradient(0, 0, w, h)
        bg2.setColorAt(0.0, QColor(56, 144, 223, 80))
        bg2.setColorAt(0.25, QColor(56, 144, 223, 20))
        bg2.setColorAt(0.5, QColor(56, 144, 223, 80))
        bg2.setColorAt(0.75, QColor(56, 144, 223, 20))
        bg2.setColorAt(1.0, QColor(56, 144, 223, 80))
        p.setPen(QPen(bg2, 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, r, r)

        p.end()
        return pixmap

    def _pulse_tick(self):
        if not self._start_time:
            return
        t = time.time() - self._start_time
        self._fade_in = min(1.0, t / 0.6)
        self._glow_phase = 0.8 + 0.2 * math.sin(t * 1.6)
        self.repaint()

    def showMessage(self, message, alignment=0, color=QColor()):
        self._status_msg = message.strip()
        self.repaint()

    def paintEvent(self, event):
        super().paintEvent(event)

        w, h = self.WIDTH, self.HEIGHT
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        t = time.time() - self._start_time if self._start_time else 0
        p.setOpacity(self._fade_in)

        logo_cy = self._LOGO_CENTER_Y

        # --- Constellation particles ---
        positions = []
        for bx, by, radius, speed, phase in self._particles:
            px = bx + radius * math.sin(t * speed + phase)
            py = by + radius * math.cos(t * speed * 0.7 + phase)
            positions.append((px, py))
            alpha = int(22 + 16 * math.sin(t * speed * 0.5 + phase))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(56, 144, 223, alpha))
            p.drawEllipse(int(px) - 1, int(py) - 1, 3, 3)

        # Connecting lines between nearby particles
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 90:
                    la = int(8 * (1.0 - dist / 90))
                    p.setPen(QPen(QColor(56, 144, 223, la), 0.5))
                    p.drawLine(
                        int(positions[i][0]), int(positions[i][1]),
                        int(positions[j][0]), int(positions[j][1]),
                    )

        # --- Breathing glow behind logo ---
        ga = int(30 * self._glow_phase)
        glow = QRadialGradient(w / 2, logo_cy, 100)
        glow.setColorAt(0.0, QColor(56, 144, 223, ga))
        glow.setColorAt(0.5, QColor(56, 144, 223, int(ga * 0.25)))
        glow.setColorAt(1.0, QColor(56, 144, 223, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(int(w / 2 - 100), logo_cy - 100, 200, 200)

        # --- Traveling shimmer ---
        sx = w * 0.5 + w * 0.4 * math.sin(t * 0.5)
        sy = h * 0.35 + h * 0.1 * math.cos(t * 0.9)
        sa = int(18 * self._glow_phase)
        shimmer = QRadialGradient(sx, sy, w * 0.35)
        shimmer.setColorAt(0.0, QColor(100, 180, 255, sa))
        shimmer.setColorAt(0.5, QColor(56, 144, 223, int(sa * 0.25)))
        shimmer.setColorAt(1.0, QColor(56, 144, 223, 0))
        p.setBrush(shimmer)
        p.drawRect(0, 0, w, h)

        # --- Orbital ring ---
        ring_cx, ring_cy = w / 2, logo_cy
        ring_rx, ring_ry = 52, 46

        p.setPen(QPen(QColor(56, 144, 223, 15), 0.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(
            int(ring_cx - ring_rx), int(ring_cy - ring_ry),
            ring_rx * 2, ring_ry * 2,
        )

        for orbit_phase, alpha_base in [(0.0, 55), (2.094, 40), (4.189, 48)]:
            angle = t * 0.75 + orbit_phase
            dx = ring_rx * math.cos(angle)
            dy = ring_ry * math.sin(angle)
            da = int(alpha_base + 20 * math.sin(t * 1.8 + orbit_phase))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(91, 168, 240, da))
            p.drawEllipse(int(ring_cx + dx) - 2, int(ring_cy + dy) - 2, 5, 5)

        # --- Logo ---
        if self._logo_pixmap:
            lx = (w - self._logo_pixmap.width()) // 2
            ly = self._LOGO_Y
            p.drawPixmap(lx, ly, self._logo_pixmap)

        # --- Title "TRRCMS" ---
        title_font = QFont(self._FONT, 16, QFont.DemiBold)
        title_font.setLetterSpacing(QFont.AbsoluteSpacing, 3.0)
        p.setFont(title_font)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(0, self._TITLE_Y, w, self._TITLE_H,
                   Qt.AlignHCenter | Qt.AlignVCenter, "TRRCMS")

        # --- English subtitle ---
        sub_font = QFont(self._FONT, 9)
        sub_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.3)
        p.setFont(sub_font)
        p.setPen(QColor(139, 172, 200, 180))
        p.drawText(0, self._SUB_EN_Y, w, self._SUB_EN_H,
                   Qt.AlignHCenter | Qt.AlignVCenter,
                   "Tenure Rights Registration & Claims Management")

        # --- Arabic subtitle ---
        ar_font = QFont(self._FONT, 9)
        p.setFont(ar_font)
        p.setPen(QColor(139, 172, 200, 130))
        p.drawText(0, self._SUB_AR_Y, w, self._SUB_AR_H,
                   Qt.AlignHCenter | Qt.AlignVCenter,
                   "\u0646\u0638\u0627\u0645 \u062a\u0633\u062c\u064a\u0644 "
                   "\u062d\u0642\u0648\u0642 \u0627\u0644\u062d\u064a\u0627\u0632\u0629 "
                   "\u0648\u0625\u062f\u0627\u0631\u0629 \u0627\u0644\u0645\u0637\u0627\u0644\u0628\u0627\u062a")

        # --- Animated separator ---
        sep_y = self._SEP_Y

        # Faint flanking rules
        p.setPen(QPen(QColor(56, 144, 223, 12), 0.5))
        p.drawLine(100, sep_y - 6, w - 100, sep_y - 6)
        p.drawLine(100, sep_y + 6, w - 100, sep_y + 6)

        # Main sweep
        sweep = (t * 0.3) % 1.0
        sg = QLinearGradient(100, 0, w - 100, 0)
        sg.setColorAt(0.0, QColor(255, 255, 255, 0))
        pre = max(0.05, sweep - 0.15)
        post = min(0.95, sweep + 0.15)
        if pre < post:
            sg.setColorAt(pre, QColor(255, 255, 255, 20))
            sg.setColorAt(sweep, QColor(56, 144, 223, 180))
            sg.setColorAt(post, QColor(255, 255, 255, 20))
        sg.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(sg, 1.0))
        p.drawLine(100, sep_y, w - 100, sep_y)

        # --- Progress bar ---
        bar_y = self._BAR_Y
        bar_x = 110
        bar_w = w - 220
        bar_h = 3

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1A2E4A"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 1.5, 1.5)

        if self._progress > 0:
            fill_w = max(4, int(bar_w * self._progress))
            fg = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            fg.setColorAt(0.0, QColor(56, 144, 223, 200))
            fg.setColorAt(1.0, QColor(91, 168, 240, 255))
            p.setBrush(fg)
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 1.5, 1.5)

            if fill_w > 8:
                eg = QRadialGradient(bar_x + fill_w, bar_y + 1.5, 14)
                eg.setColorAt(0.0, QColor(91, 168, 240, 65))
                eg.setColorAt(1.0, QColor(56, 144, 223, 0))
                p.setBrush(eg)
                p.drawEllipse(int(bar_x + fill_w - 14), bar_y - 12, 28, 28)
        else:
            seg_w = bar_w * 0.25
            seg_pos = (math.sin(t * 2.0) * 0.5 + 0.5) * (bar_w - seg_w)
            ig = QLinearGradient(bar_x + seg_pos, 0, bar_x + seg_pos + seg_w, 0)
            ig.setColorAt(0.0, QColor(56, 144, 223, 0))
            ig.setColorAt(0.3, QColor(56, 144, 223, 140))
            ig.setColorAt(0.7, QColor(91, 168, 240, 140))
            ig.setColorAt(1.0, QColor(56, 144, 223, 0))
            p.setBrush(ig)
            p.drawRoundedRect(
                int(bar_x + seg_pos), bar_y,
                int(seg_w), bar_h, 1.5, 1.5,
            )

        # --- Status message ---
        if self._status_msg:
            p.setPen(QColor(139, 172, 200, 120))
            p.setFont(QFont(self._FONT, 8))
            p.drawText(0, self._STATUS_Y, w, 24, Qt.AlignHCenter, self._status_msg)

        p.setOpacity(1.0)
        p.end()


def main():
    """Main application entry point."""

    # Enable GPU acceleration for QWebEngineView (must be set before QApplication)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--ignore-gpu-blacklist "
        "--enable-gpu-rasterization "
        "--enable-zero-copy"
    )

    # Set Qt attributes BEFORE creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough  # type: ignore
        )
    except AttributeError:
        pass  # Qt5 versions prior to 5.14 don't have this
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)  # type: ignore

    # Initialize logging
    logger = setup_logger()

    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName(Config.APP_NAME)
        app.setOrganizationName("UN-Habitat")
        app.setOrganizationDomain("unhabitat.org")

        # Initialize language from saved preference (before splash text)
        from services.translation_manager import (
            set_language as tm_set_language, tr, get_layout_direction
        )
        saved_lang = get_saved_language()
        tm_set_language(saved_lang)
        app.setLayoutDirection(get_layout_direction())

        # Show animated splash screen
        splash = AnimatedSplash()
        splash.show()
        app.processEvents()

        # Set application-wide default font
        set_application_default_font()

        # Initialize database in background thread so splash can animate
        splash.set_progress(0.1)
        splash.showMessage(tr("splash.initializing_db"),
                           Qt.AlignBottom | Qt.AlignHCenter,
                           QColor(255, 255, 255, 120))
        app.processEvents()
        print("[STARTUP] Initializing database...")

        from PyQt5.QtCore import QThread, pyqtSignal

        class _DbWorker(QThread):
            done = pyqtSignal(object)
            def run(self):
                db = Database()
                db.initialize()
                self.done.emit(db)

        db_result = [None]
        worker = _DbWorker()
        worker.done.connect(lambda db: db_result.__setitem__(0, db))
        worker.start()

        while worker.isRunning():
            app.processEvents()
            QThread.msleep(16)

        db = db_result[0]

        # Create main window
        splash.set_progress(0.7)
        splash.showMessage(tr("splash.loading_ui"),
                           Qt.AlignBottom | Qt.AlignHCenter,
                           QColor(255, 255, 255, 120))
        app.processEvents()
        window = MainWindow(db, saved_lang)
        splash.set_progress(1.0)
        app.processEvents()
        window.show()
        splash.finish(window)
        print("[STARTUP] Application started successfully!")

        # Defer API data loading so window appears immediately
        def _init_deferred():
            print("[STARTUP] Fetching vocabularies from API...")
            try:
                from services.vocab_service import initialize_vocabularies  # type: ignore
                initialize_vocabularies()
                print("[STARTUP] Vocabularies initialized successfully")
            except Exception as e:
                print(f"[STARTUP] Vocabularies initialization failed: {e}")

        from PyQt5.QtCore import QTimer  # type: ignore
        QTimer.singleShot(0, _init_deferred)

        # Run application event loop
        exit_code = app.exec_()
        logger.info(f"Application closed with exit code: {exit_code}")
        sys.exit(exit_code)

    except ImportError as e:
        error_msg = f"Import Error: {e}"
        print(f"\n[ERROR] {error_msg}")
        print("\nPossible causes:")
        print("1. Missing dependencies - Run: pip install -r requirements.txt")
        print("2. Python path issue - Make sure you're in the correct directory")
        print("\nDetails:", str(e))
        if 'logger' in locals():
            logger.exception(error_msg)
        sys.exit(1)

    except Exception as e:
        error_msg = f"Fatal error during application startup: {e}"
        print(f"\n[ERROR] {error_msg}")
        print("\nPlease check trrcms/logs/app.log for details")
        if 'logger' in locals():
            logger.exception(error_msg)
        else:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
