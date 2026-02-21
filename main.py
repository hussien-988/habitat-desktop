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
from repositories.seed import seed_database, seed_users_only  # type: ignore
from utils.i18n import I18n  # type: ignore
from utils.logger import setup_logger  # type: ignore
from ui.font_utils import set_application_default_font  # type: ignore


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

        # CRITICAL: Set application-wide default font BEFORE creating any widgets
        # This eliminates stylesheet font conflicts (Best Practice)
        set_application_default_font()

        # Log startup
        logger.info("=" * 80)
        logger.info("Starting TRRCMS Application")
        logger.info("=" * 80)

        # Persistent database — keep existing data between runs
        sqlite_db_path = Config.DB_PATH
        if sqlite_db_path.exists():
            logger.info(f"Using existing database: {sqlite_db_path}")
        else:
            logger.info("No database found, will create fresh one")

        # Initialize database (CREATE IF NOT EXISTS — safe for existing DB)
        logger.info("Initializing database...")
        db = Database()
        db.initialize()
        logger.info(">> Database initialized successfully")

        # Seed only users if DB is empty (no mock buildings/units/claims)
        user_count = db.fetch_one("SELECT COUNT(*) as count FROM users")
        if user_count and user_count['count'] == 0:
            from repositories.seed import seed_users_only
            seed_users_only(db)
            logger.info(">> Seeded initial users (clean start)")
        else:
            logger.info(f">> Database has {user_count['count']} users, skipping seed")

        # Initialize i18n
        logger.info("Initializing internationalization...")
        i18n = I18n()
        i18n.set_language("ar")  # Default to Arabic
        logger.info(">> Internationalization initialized (Arabic)")

        # Fetch and cache vocabularies from backend API (skip in local mode)
        if Config.DATA_MODE != "local":
            logger.info("Fetching vocabularies from API...")
            try:
                from services.vocab_service import initialize_vocabularies  # type: ignore
                initialize_vocabularies()
                logger.info(">> Vocabularies initialized")
            except Exception as e:
                logger.warning(f">> Vocabulary fetch failed (will use defaults): {e}")
        else:
            logger.info(">> Local mode: skipping API vocabulary fetch")

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
