#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TRRCMS - Tenure Rights Registration & Claims Management System
Main entry point for the application

نظام تسجيل حقوق الحيازة وإدارة المطالبات
نقطة الدخول الرئيسية للتطبيق
"""

import sys
from pathlib import Path

# Add trrcms directory to Python path (MUST be before any trrcms imports)
trrcms_path = Path(__file__).parent / "trrcms"
sys.path.insert(0, str(trrcms_path))

# Now we can import from trrcms
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Import trrcms modules after path is set
# Note: IDE may show warnings, but these imports will work at runtime
from app.config import Config  # type: ignore
from app import MainWindow  # type: ignore
from repositories.database import Database  # type: ignore
from repositories.seed import seed_database  # type: ignore
from utils.i18n import I18n  # type: ignore
from utils.logger import setup_logger  # type: ignore


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

        # Log startup
        logger.info("=" * 80)
        logger.info("Starting TRRCMS Application")
        logger.info("=" * 80)

        # Initialize database
        logger.info("Initializing database...")
        db = Database()
        db.initialize()
        logger.info(">> Database initialized successfully")

        # Seed demo data if database is empty
        logger.info("Checking for demo data...")
        seed_database(db)

        # Initialize i18n
        logger.info("Initializing internationalization...")
        i18n = I18n()
        i18n.set_language("ar")  # Default to Arabic
        logger.info(">> Internationalization initialized (Arabic)")

        # Create main window (now using v2 with Navbar)
        logger.info("Creating main window (NEW DESIGN v2 with Navbar)...")
        window = MainWindow(db, i18n)
        window.show()
        logger.info(">> Main window created and displayed")

        logger.info("=" * 80)
        logger.info(">> Application started successfully!")
        logger.info("=" * 80)

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
