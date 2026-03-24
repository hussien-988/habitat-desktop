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
from PyQt5.QtGui import QPixmap, QColor, QPainter, QFont

from app.config import Config
from app import MainWindow
from repositories.database import Database
from utils.i18n import I18n
from utils.logger import setup_logger
from ui.font_utils import set_application_default_font


def _create_splash():
    """Create a splash screen pixmap with logo and loading text."""
    width, height = 420, 280
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#1B2B4D"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    logo_path = str(Path(__file__).parent / "assets" / "images" / "app.ico")
    text_y = 40
    if Path(logo_path).exists():
        logo = QPixmap(logo_path)
        if not logo.isNull():
            logo = logo.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap((width - logo.width()) // 2, 30, logo)
            text_y = 125

    painter.setPen(QColor("white"))
    painter.setFont(QFont("Arial", 16, QFont.Bold))
    painter.drawText(0, text_y, width, 40, Qt.AlignHCenter, "TRRCMS")

    painter.setFont(QFont("Arial", 11))
    painter.setPen(QColor(255, 255, 255, 180))
    painter.drawText(0, text_y + 40, width, 30, Qt.AlignHCenter,
                     "Tenure Rights Registration & Claims")

    painter.setFont(QFont("Arial", 10))
    painter.setPen(QColor(255, 255, 255, 140))
    painter.drawText(0, text_y + 70, width, 30, Qt.AlignHCenter,
                     "جاري تحميل التطبيق...")

    painter.end()
    return pixmap


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

        # Show splash screen immediately
        splash = QSplashScreen(_create_splash(), Qt.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()

        # Set application-wide default font
        set_application_default_font()

        # Initialize database
        splash.showMessage("  تهيئة قاعدة البيانات...",
                          Qt.AlignBottom | Qt.AlignHCenter, QColor("white"))
        app.processEvents()
        print("[STARTUP] Initializing database...")
        db = Database()
        db.initialize()

        # Initialize i18n
        i18n = I18n()
        i18n.set_language("ar")

        # Create main window
        splash.showMessage("  تحميل الواجهة...",
                          Qt.AlignBottom | Qt.AlignHCenter, QColor("white"))
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
