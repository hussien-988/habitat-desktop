#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UN-Habitat Syria - Tenure Rights Registration & Claims Management System
Main application entry point.
"""

import sys
import traceback
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# IMPORTANT: Import QtWebEngineWidgets BEFORE creating QApplication
# This is required by Qt for proper WebEngine initialization
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView  # noqa: F401
except ImportError:
    pass  # WebEngine not available, map will use fallback

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QLocale
from PyQt5.QtGui import QFont, QFontDatabase

from app.config import Config
from app.main_window import MainWindow
from app.styles import get_stylesheet
from repositories.database import Database
from repositories.seed import seed_database
from utils.logger import setup_logger, get_logger
from utils.i18n import I18n


def exception_hook(exc_type, exc_value, exc_tb):
    """Global exception handler to catch crashes."""
    logger = get_logger(__name__)
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical(f"Unhandled exception:\n{error_msg}")
    print(f"CRITICAL ERROR:\n{error_msg}", file=sys.stderr)

    # Show error dialog if app is running
    try:
        QMessageBox.critical(
            None,
            "خطأ في التطبيق",
            f"حدث خطأ غير متوقع:\n\n{exc_value}\n\nراجع ملف السجل للتفاصيل."
        )
    except:
        pass

    sys.__excepthook__(exc_type, exc_value, exc_tb)


def setup_fonts(app: QApplication) -> None:
    """Load custom fonts for Arabic support."""
    fonts_dir = PROJECT_ROOT / "assets" / "fonts"

    # Try to load Noto Sans Arabic if available
    noto_arabic = fonts_dir / "NotoSansArabic-Regular.ttf"
    if noto_arabic.exists():
        font_id = QFontDatabase.addApplicationFont(str(noto_arabic))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                Config.ARABIC_FONT_FAMILY = families[0]

    # Set default application font
    font = QFont(Config.FONT_FAMILY, Config.FONT_SIZE)
    app.setFont(font)


def main() -> int:
    """Main application entry point."""
    # Install global exception handler
    sys.excepthook = exception_hook

    # Setup logging first
    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("UN-Habitat Syria Application Starting")
    logger.info("=" * 60)

    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName(Config.APP_NAME)
    app.setApplicationVersion(Config.VERSION)
    app.setOrganizationName(Config.ORGANIZATION)

    # Set locale for proper number/date formatting
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))

    # Setup fonts
    setup_fonts(app)

    # Initialize translations
    i18n = I18n()

    # Apply UN-Habitat branding stylesheet
    app.setStyleSheet(get_stylesheet())

    # Initialize database
    logger.info("Initializing database...")
    db = Database()
    db.initialize()

    # Seed demo data if database is empty
    logger.info("Checking for demo data...")
    seed_database(db)

    # Create and show main window
    logger.info("Creating main window...")
    window = MainWindow(db, i18n)
    window.show()

    logger.info("Application ready")

    # Run event loop
    exit_code = app.exec_()

    # Cleanup
    logger.info("Application shutting down")
    db.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
