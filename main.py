#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TRRCMS - Tenure Rights Registration & Claims Management System
Main entry point for the application
"""

import sys
import time
from pathlib import Path

# Add trrcms directory to Python path
trrcms_path = Path(__file__).parent / "trrcms"
sys.path.insert(0, str(trrcms_path))


from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import (
    QPixmap, QColor, QPainter, QFont,
    QLinearGradient, QRadialGradient, QPen,
)

from app.config import Config, get_saved_language
from app import MainWindow
from repositories.database import Database
from utils.logger import setup_logger
from ui.font_utils import set_application_default_font


class AnimatedSplash(QSplashScreen):
    """Splash screen with glow breathing effect and animated loading dots."""

    WIDTH, HEIGHT = 460, 320

    def __init__(self):
        self._logo_pixmap = None
        self._text_y = 50

        # Load logo
        logo_path = Path(__file__).parent / "assets" / "images" / "Layer_1.png"
        if logo_path.exists():
            px = QPixmap(str(logo_path))
            if not px.isNull():
                self._logo_pixmap = px.scaled(
                    88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self._text_y = 130

        # Create background-only pixmap
        bg = self._create_background()
        super().__init__(bg)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # Effect state
        self._start_time = None
        self._glow_phase = 0.0
        self._dots_frame = 0
        self._status_msg = ""

        # Glow breathing timer (~30fps is enough for subtle pulse)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)

        # Dots animation timer (every 400ms)
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._advance_dots)

    def show(self):
        super().show()
        self._start_time = time.time()
        self._pulse_timer.start(33)
        self._dots_timer.start(400)

    def _create_background(self):
        """Create the static background pixmap (gradient + border)."""
        w, h = self.WIDTH, self.HEIGHT
        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background gradient
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor("#0F1B33"))
        bg.setColorAt(0.5, QColor("#162544"))
        bg.setColorAt(1.0, QColor("#1A3055"))
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 12, 12)

        # Accent border
        border_grad = QLinearGradient(0, 0, w, h)
        border_grad.setColorAt(0.0, QColor(100, 180, 255, 100))
        border_grad.setColorAt(0.25, QColor(100, 180, 255, 40))
        border_grad.setColorAt(0.5, QColor(100, 180, 255, 100))
        border_grad.setColorAt(0.75, QColor(100, 180, 255, 40))
        border_grad.setColorAt(1.0, QColor(100, 180, 255, 100))
        painter.setPen(QPen(border_grad, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

        painter.end()
        return pixmap

    def _pulse_tick(self):
        """Update glow breathing phase."""
        if not self._start_time:
            return
        import math
        t = time.time() - self._start_time
        # Slow sine wave: period ~3s, range 0.6-1.0
        self._glow_phase = 0.8 + 0.2 * math.sin(t * 2.1)
        self.repaint()

    def _advance_dots(self):
        """Cycle through loading dots frames."""
        self._dots_frame = (self._dots_frame + 1) % 4
        if self._status_msg:
            self.repaint()

    def showMessage(self, message, alignment=0, color=QColor()):
        """Override to store status message for custom rendering."""
        self._status_msg = message.strip()
        self.repaint()

    def paintEvent(self, event):
        """Draw all elements with breathing glow effect."""
        super().paintEvent(event)

        w, h = self.WIDTH, self.HEIGHT
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Breathing glow behind logo
        glow_alpha = int(35 * self._glow_phase)
        glow = QRadialGradient(w / 2, 95, 120)
        glow.setColorAt(0.0, QColor(56, 144, 223, glow_alpha))
        glow.setColorAt(0.6, QColor(56, 144, 223, int(glow_alpha * 0.3)))
        glow.setColorAt(1.0, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(int(w / 2 - 120), -25, 240, 240)

        text_y = self._text_y

        # Logo
        if self._logo_pixmap:
            lx = (w - self._logo_pixmap.width()) // 2
            ly = 30
            painter.setOpacity(0.15)
            painter.drawPixmap(lx + 2, ly + 2, self._logo_pixmap)
            painter.setOpacity(1.0)
            painter.drawPixmap(lx, ly, self._logo_pixmap)

        # Title
        painter.setPen(QColor(255, 255, 255, 240))
        painter.setFont(QFont("Arial", 17, QFont.Bold))
        painter.drawText(0, text_y, w, 36, Qt.AlignHCenter, "TRRCMS")

        # Subtitle
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QColor(255, 255, 255, 160))
        painter.drawText(0, text_y + 36, w, 24, Qt.AlignHCenter,
                         "Tenure Rights Registration & Claims")

        # Separator line
        sep_y = text_y + 68
        sep_grad = QLinearGradient(0, 0, w, 0)
        sep_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        sep_grad.setColorAt(0.3, QColor(255, 255, 255, 40))
        sep_grad.setColorAt(0.7, QColor(255, 255, 255, 40))
        sep_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(sep_grad, 1))
        painter.drawLine(80, sep_y, w - 80, sep_y)

        # Status message with animated dots
        if self._status_msg:
            painter.setPen(QColor(255, 255, 255, 120))
            painter.setFont(QFont("Arial", 9))
            dots = "." * self._dots_frame
            display_msg = self._status_msg.rstrip(".") + dots
            painter.drawText(0, h - 40, w, 30, Qt.AlignHCenter, display_msg)

        painter.end()


def main():
    """Main application entry point."""

    # Set Qt attributes BEFORE creating QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # type: ignore
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)  # type: ignore
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
            set_language as tm_set_language, tr
        )
        saved_lang = get_saved_language()
        tm_set_language(saved_lang)

        # Show animated splash screen
        splash = AnimatedSplash()
        splash.show()
        app.processEvents()

        # Set application-wide default font
        set_application_default_font()

        # Initialize database
        splash.showMessage(tr("splash.initializing_db"),
                           Qt.AlignBottom | Qt.AlignHCenter,
                           QColor(255, 255, 255, 120))
        app.processEvents()
        print("[STARTUP] Initializing database...")
        db = Database()
        db.initialize()

        # Create main window
        splash.showMessage(tr("splash.loading_ui"),
                           Qt.AlignBottom | Qt.AlignHCenter,
                           QColor(255, 255, 255, 120))
        app.processEvents()
        window = MainWindow(db, saved_lang)
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

            try:
                from services.landmark_icon_service import load_landmark_types
                load_landmark_types()
                print("[STARTUP] Landmark types loaded")
            except Exception as e:
                print(f"[STARTUP] Landmark types loading failed: {e}")

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
