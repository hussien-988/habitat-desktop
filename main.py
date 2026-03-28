#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TRRCMS - Tenure Rights Registration & Claims Management System
Main entry point for the application
"""

import sys
from pathlib import Path

# Add trrcms directory to Python path
trrcms_path = Path(__file__).parent / "trrcms"
sys.path.insert(0, str(trrcms_path))


from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QPixmap, QColor, QPainter, QFont,
    QLinearGradient, QRadialGradient, QPen,
)

from app.config import Config
from app import MainWindow
from repositories.database import Database
from utils.i18n import I18n
from utils.logger import setup_logger
from ui.font_utils import set_application_default_font


def _create_splash():
    """Create a styled splash screen with visual polish."""
    width, height = 460, 320
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    # Background gradient
    bg = QLinearGradient(0, 0, 0, height)
    bg.setColorAt(0.0, QColor("#0F1B33"))
    bg.setColorAt(0.5, QColor("#162544"))
    bg.setColorAt(1.0, QColor("#1A3055"))
    painter.setBrush(bg)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(0, 0, width, height, 12, 12)

    # Static accent border
    border_grad = QLinearGradient(0, 0, width, height)
    border_grad.setColorAt(0.0, QColor(100, 180, 255, 100))
    border_grad.setColorAt(0.25, QColor(100, 180, 255, 40))
    border_grad.setColorAt(0.5, QColor(100, 180, 255, 100))
    border_grad.setColorAt(0.75, QColor(100, 180, 255, 40))
    border_grad.setColorAt(1.0, QColor(100, 180, 255, 100))
    painter.setPen(QPen(border_grad, 1.5))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(1, 1, width - 2, height - 2, 12, 12)

    # Subtle radial glow behind logo
    glow = QRadialGradient(width / 2, 95, 120)
    glow.setColorAt(0.0, QColor(56, 144, 223, 35))
    glow.setColorAt(0.6, QColor(56, 144, 223, 10))
    glow.setColorAt(1.0, QColor(56, 144, 223, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(int(width / 2 - 120), -25, 240, 240)

    # Logo
    logo_path = str(Path(__file__).parent / "assets" / "images" / "Layer_1.png")
    text_y = 50
    if Path(logo_path).exists():
        logo = QPixmap(logo_path)
        if not logo.isNull():
            logo = logo.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lx = (width - logo.width()) // 2
            ly = 30
            painter.setOpacity(0.15)
            painter.drawPixmap(lx + 2, ly + 2, logo)
            painter.setOpacity(1.0)
            painter.drawPixmap(lx, ly, logo)
            text_y = 130

    # Title
    painter.setPen(QColor(255, 255, 255, 240))
    painter.setFont(QFont("Arial", 17, QFont.Bold))
    painter.drawText(0, text_y, width, 36, Qt.AlignHCenter, "TRRCMS")

    # Subtitle
    painter.setFont(QFont("Arial", 10))
    painter.setPen(QColor(255, 255, 255, 160))
    painter.drawText(0, text_y + 36, width, 24, Qt.AlignHCenter,
                     "Tenure Rights Registration & Claims")

    # Separator line
    sep_y = text_y + 68
    sep_grad = QLinearGradient(0, 0, width, 0)
    sep_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
    sep_grad.setColorAt(0.3, QColor(255, 255, 255, 40))
    sep_grad.setColorAt(0.7, QColor(255, 255, 255, 40))
    sep_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setPen(QPen(sep_grad, 1))
    painter.drawLine(80, sep_y, width - 80, sep_y)

    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    return splash


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

        # Show splash screen
        splash = _create_splash()
        splash.show()
        app.processEvents()

        # Set application-wide default font
        set_application_default_font()

        # Initialize database
        splash.showMessage("  تهيئة قاعدة البيانات...",
                           Qt.AlignBottom | Qt.AlignHCenter,
                           QColor(255, 255, 255, 120))
        app.processEvents()
        print("[STARTUP] Initializing database...")
        db = Database()
        db.initialize()

        # Initialize i18n
        i18n = I18n()
        i18n.set_language("ar")

        # Create main window
        splash.showMessage("  تحميل الواجهة...",
                           Qt.AlignBottom | Qt.AlignHCenter,
                           QColor(255, 255, 255, 120))
        app.processEvents()
        window = MainWindow(db, i18n)
        window.show()
        splash.finish(window)
        print("[STARTUP] Application started successfully!")

        # Defer vocabulary loading so window appears immediately
        def _init_vocabs():
            print("[STARTUP] Fetching vocabularies from API...")
            try:
                from services.vocab_service import initialize_vocabularies  # type: ignore
                initialize_vocabularies()
                print("[STARTUP] Vocabularies initialized successfully")
            except Exception as e:
                print(f"[STARTUP] Vocabularies initialization failed: {e}")

        from PyQt5.QtCore import QTimer  # type: ignore
        QTimer.singleShot(0, _init_vocabs)

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
