# -*- coding: utf-8 -*-
"""Main application window with navbar navigation."""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QShortcut, QApplication,
    QFrame, QGraphicsDropShadowEffect, QSizeGrip
)

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QEvent

from PyQt5.QtGui import QKeySequence, QColor, QMouseEvent, QPixmap, QPainter

from .config import Config, Pages, save_language, get_saved_language
from repositories.database import Database
from services.translation_manager import tr, set_language as tm_set_language
from utils.i18n import I18n
from utils.logger import get_logger
from ui.error_handler import ErrorHandler
from ui.design_system import ScreenScale

logger = get_logger(__name__)


class _WatermarkOverlay(QWidget):
    """Transparent overlay that draws a pulsing UN-Habitat watermark on top of all pages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        import math
        self._math = math

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")

        # Load watermark image
        self._watermark = QPixmap()
        from pathlib import Path
        import sys
        base = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(__file__).parent.parent
        wm_path = base / "assets" / "images" / "login-watermark.png"
        if wm_path.exists():
            self._watermark.load(str(wm_path))

        # Animation state
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._t += 0.05
        self.update()

    def paintEvent(self, event):
        if self._watermark.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        wm_size = int(min(self.width(), self.height()) * 0.30)
        if wm_size < 10:
            painter.end()
            return

        scaled = self._watermark.scaled(
            wm_size, wm_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2

        # Breathing opacity: 0.06 - 0.14
        opacity = 0.06 + 0.08 * (self._math.sin(self._t * 0.8) + 1) / 2
        painter.setOpacity(opacity)
        painter.drawPixmap(x, y, scaled)
        painter.end()


class _WatermarkBackground(QWidget):
    """Container that holds the page stack and positions a watermark overlay on top."""

    def __init__(self, child_widget: QWidget, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(child_widget, 1)

        self._overlay = _WatermarkOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._overlay.raise_()


class MainWindow(QMainWindow):
    """Main application window with navbar navigation."""

    language_changed = pyqtSignal(bool)  # True for Arabic, False for English

    # Pages restricted to specific roles
    _PAGE_ROLE_ACCESS = {
        Pages.FIELD_ASSIGNMENT: {"admin", "data_manager", "field_supervisor"},
        Pages.SYNC_DATA: {"admin", "data_manager", "field_supervisor"},
        Pages.CASE_MANAGEMENT: {"admin", "data_manager"},
        Pages.CASE_ENTITY_DETAILS: {"admin", "data_manager"},
        Pages.CLAIM_EDIT: {"admin", "data_manager"},
        Pages.DUPLICATES: {"admin", "data_manager"},
        Pages.CLAIM_COMPARISON: {"admin", "data_manager"},
        Pages.IMPORT_WIZARD: {"admin", "data_manager"},
        Pages.IMPORT_PACKAGES: {"admin", "data_manager"},
        Pages.BUILDINGS: {"admin", "data_manager"},
    }

    def __init__(self, db: Database, lang: str = "ar", parent=None):
        super().__init__(parent)
        self.WINDOW_RADIUS = 12
        self.db = db
        self.i18n = I18n(lang)
        self.current_user = None
        self._is_arabic = (lang == "ar")

        # For window dragging
        self._drag_position = QPoint()

        # Contextual back navigation (case entity details → survey/claim details → back)
        self._back_to_case_entity = False
        self._case_entity_case_id = None

        # Session timeout tracking
        self._session_timer = None
        self._last_activity = None
        self._session_timeout_ms = 0

        # Proactive token refresh timer
        self._token_refresh_timer = None

        self._setup_window()
        self._setup_shortcuts()
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()
        self._setup_tile_interceptor()

        # Set layout direction based on saved language
        if self._is_arabic:
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

        # Start with login page
        self._show_login()

    def _setup_window(self):
        """Configure window properties — adapts to screen size."""
        self.setWindowTitle("UN-HABITAT")

        screen = self.screen().availableGeometry()

        # Window = 95% of available screen, capped at reference size
        window_width = min(1512, int(screen.width() * 0.95))
        window_height = min(982, int(screen.height() * 0.95))

        # Initialize scaling from actual window size (not screen size)
        ScreenScale.initialize_from_size(window_width, window_height)
        self.setMinimumSize(min(1024, window_width), min(680, window_height))

        # Center on screen (use screen.x/y to handle multi-monitor and top taskbar)
        x = screen.x() + (screen.width() - window_width) // 2
        y = screen.y() + (screen.height() - window_height) // 2
        self.setGeometry(x, y, window_width, window_height)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)


        # Add rounded corners to window (Windows 11 style)
        # Note: This uses Windows-specific API through Qt
        '''try:
            import ctypes
            from ctypes import wintypes

            # DWM (Desktop Window Manager) API for rounded corners
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2  # Round corners

            hwnd = int(self.winId())
            preference = wintypes.DWORD(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference),
                ctypes.sizeof(preference)
            )
        except Exception as e:
            # If Windows API fails, continue without rounded corners
            logger.debug(f"Could not set rounded corners: {e}")
        '''
    def _setup_tile_interceptor(self):
        """Add User-Agent/Referer headers for external tile server requests."""
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineProfile
            from services.tile_request_interceptor import TileRequestInterceptor

            self._tile_interceptor = TileRequestInterceptor(self)
            QWebEngineProfile.defaultProfile().setUrlRequestInterceptor(self._tile_interceptor)
        except ImportError:
            pass

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Language toggle: Ctrl+L
        self.lang_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self.lang_shortcut.activated.connect(self.toggle_language)

        # Logout: Ctrl+Q
        self.logout_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.logout_shortcut.activated.connect(self._handle_logout)


    def _create_widgets(self):
        """Create main UI components with new design."""
        # Import here to avoid circular imports
        from ui.components.navbar import Navbar
        from ui.pages.login_page import LoginPage
        from ui.pages.buildings_page import BuildingsPage
        from ui.pages.building_details_page import BuildingDetailsPage
        from ui.pages.units_page import UnitsPage
        from ui.pages.unit_details_page import UnitDetailsPage
        from ui.pages.persons_page import PersonsPage
        from ui.pages.relations_page import RelationsPage
        from ui.pages.households_page import HouseholdsPage
        from ui.pages.completed_claims_page import CompletedClaimsPage
        from ui.pages.cases_page import CasesPage
        from ui.pages.duplicates_page import DuplicatesPage
        from ui.pages.claim_comparison_page import ClaimComparisonPage
        from ui.pages.field_work_preparation_page import FieldWorkPreparationPage
        from controllers.building_controller import BuildingController
        from ui.pages.case_details_page import CaseDetailsPage
        from ui.pages.claim_details_page import ClaimDetailsPage
        from ui.wizards.office_survey import OfficeSurveyWizard
        from ui.pages.import_wizard_page import ImportWizardPage
        from ui.pages.claim_edit_page import ClaimEditPage


        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet("background: transparent;")
        # إطار داخلي هو اللي رح يبين التطبيق + يعطي زوايا + ظل
        self.window_frame = QFrame(self.central_widget)
        self.window_frame.setObjectName("window_frame")
        self.window_frame.setAttribute(Qt.WA_StyledBackground, True)
        self.window_frame.setStyleSheet(f"""
            QFrame#window_frame {{
                background-color: {Config.BACKGROUND_COLOR};
                border-radius: 12px;
            }}
        """)


        # مقبض تغيير الحجم (resize) خليّه جوّا الإطار
        self._size_grip = QSizeGrip(self.window_frame)
        self._size_grip.setFixedSize(ScreenScale.w(16), ScreenScale.h(16))
        self._size_grip.setStyleSheet("background: transparent;")


        # Navbar (hidden initially - shown after login)
        self.navbar = Navbar(user_id="12345", parent=self)
        self.navbar.setVisible(False)

        # Stacked widget for pages
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        # Create pages
        self.pages = {}

        # Login page
        self.pages[Pages.LOGIN] = LoginPage(self.i18n, db=self.db, parent=self)
        self.stack.addWidget(self.pages[Pages.LOGIN])

        # Buildings list page
        self.pages[Pages.BUILDINGS] = BuildingsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.BUILDINGS])

        # Building details page
        self.pages[Pages.BUILDING_DETAILS] = BuildingDetailsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.BUILDING_DETAILS])

        # Units page
        self.pages[Pages.UNITS] = UnitsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.UNITS])

        # Unit details page
        self.pages[Pages.UNIT_DETAILS] = UnitDetailsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.UNIT_DETAILS])

        # Persons page
        self.pages[Pages.PERSONS] = PersonsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.PERSONS])

        # Relations page (Person-Unit Relations)
        self.pages[Pages.RELATIONS] = RelationsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.RELATIONS])

        # Households page
        self.pages[Pages.HOUSEHOLDS] = HouseholdsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.HOUSEHOLDS])

        # Completed Claims page
        self.pages[Pages.CLAIMS] = CompletedClaimsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CLAIMS])

        # Cases page (3 sub-tabs: Draft / Finalized / Completed)
        self.pages[Pages.SURVEYS] = CasesPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.SURVEYS])

        # Case Management page (Case entity: Open / Closed)
        from ui.pages.case_management_page import CaseManagementPage
        self.pages[Pages.CASE_MANAGEMENT] = CaseManagementPage(self)
        self.stack.addWidget(self.pages[Pages.CASE_MANAGEMENT])

        # Case Entity Details page
        from ui.pages.case_entity_details_page import CaseEntityDetailsPage
        self.pages[Pages.CASE_ENTITY_DETAILS] = CaseEntityDetailsPage(self)
        self.stack.addWidget(self.pages[Pages.CASE_ENTITY_DETAILS])

        # Duplicates page
        self.pages[Pages.DUPLICATES] = DuplicatesPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.DUPLICATES])

        # Claim Comparison page
        self.pages[Pages.CLAIM_COMPARISON] = ClaimComparisonPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CLAIM_COMPARISON])

        # Field Work Preparation wizard
        field_bc = BuildingController(self.db)
        self.pages[Pages.FIELD_ASSIGNMENT] = FieldWorkPreparationPage(field_bc, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.FIELD_ASSIGNMENT])
        self.pages[Pages.FIELD_ASSIGNMENT].completed.connect(self._on_field_work_completed)

        # Case Details page — read-only view of survey/claim
        self.pages[Pages.SURVEY_DETAILS] = CaseDetailsPage(self)
        self.stack.addWidget(self.pages[Pages.SURVEY_DETAILS])

        # Claim Details page — dedicated view for claims from Claims API
        self.pages[Pages.CLAIM_DETAILS] = ClaimDetailsPage(self)
        self.stack.addWidget(self.pages[Pages.CLAIM_DETAILS])

        # Sync & Data page
        from ui.pages.sync_data_page import SyncDataPage
        self.pages[Pages.SYNC_DATA] = SyncDataPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.SYNC_DATA])

        # Import Wizard page
        from controllers.import_controller import ImportController
        self._import_controller = ImportController(self.db)
        self.pages[Pages.IMPORT_WIZARD] = ImportWizardPage(
            import_controller=self._import_controller, db=self.db, i18n=self.i18n, parent=self
        )
        self.stack.addWidget(self.pages[Pages.IMPORT_WIZARD])

        # Import <-> Duplicates navigation signals
        self.pages[Pages.IMPORT_WIZARD].navigate_to_duplicates.connect(
            self._on_import_navigate_to_duplicates
        )
        self.pages[Pages.DUPLICATES].return_to_import.connect(
            self._on_duplicates_return_to_import
        )

        # Import Packages list page
        from ui.pages.import_packages_page import ImportPackagesPage
        self.pages[Pages.IMPORT_PACKAGES] = ImportPackagesPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.IMPORT_PACKAGES])

        # Claim Edit page
        self.pages[Pages.CLAIM_EDIT] = ClaimEditPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CLAIM_EDIT])

        # Office Survey Wizard
        self.office_survey_wizard = OfficeSurveyWizard(self.db, self)
        self.stack.addWidget(self.office_survey_wizard)

        # Map tabs to pages
        # Tab 0: المطالبات المكتملة (Completed Claims)
        # Tab 1: الادعاءات (Cases/Claims)
        # Tab 2: إدارة الحالات (Case Management)
        # Tab 3: الاستيراد (Import)
        # Tab 4: التكرارات (Duplicates)
        # Tab 5: تجهيز العمل الميداني (Field Work Preparation)
        # Tab 6: المباني (Buildings)
        self.tab_page_mapping = {
            0: Pages.CLAIMS,
            1: Pages.SURVEYS,
            2: Pages.CASE_MANAGEMENT,
            3: Pages.IMPORT_PACKAGES,
            4: Pages.DUPLICATES,
            5: Pages.FIELD_ASSIGNMENT,
            6: Pages.BUILDINGS,
        }

    def _setup_layout(self):
    # لاي اوت خارجي: بدون فراغ شفاف (حسب طلب المستخدم)
        outer = QVBoxLayout(self.central_widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.window_frame)

    # لاي اوت داخلي: جوّا الإطار
        inner = QVBoxLayout(self.window_frame)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        inner.addWidget(self.navbar, 0)
        self._watermark_bg = _WatermarkBackground(self.stack, self)
        inner.addWidget(self._watermark_bg, 1)


    def _connect_signals(self):
        """Connect widget signals to slots."""
        # Login page signals
        self.pages[Pages.LOGIN].login_successful.connect(self._on_login_success)

        # Navbar signals
        self.navbar.tab_changed.connect(self._on_tab_changed)
        # Search/filter removed from navbar — each page has its own filters
        self.navbar.logout_requested.connect(self._handle_logout)
        self.navbar.language_change_requested.connect(self.toggle_language)
        self.navbar.sync_requested.connect(self._on_sync_requested)
        self.navbar.password_change_requested.connect(self._on_voluntary_password_change)
        self.pages[Pages.SYNC_DATA].sync_notification.connect(self._on_sync_notification)
        self.navbar.import_requested.connect(self._on_import_requested)

        # Import pages signals. The wizard is always entered with a specific
        # package id via `view_package`; there is no package-less entry point.
        # Upload flows emit `view_package` with the new id after success.
        self.pages[Pages.IMPORT_PACKAGES].view_package.connect(
            self._on_view_import_package
        )
        self.pages[Pages.IMPORT_WIZARD].completed.connect(
            self._on_import_completed_silent_refresh
        )
        self.pages[Pages.IMPORT_WIZARD].cancelled.connect(
            lambda: self.navigate_to(Pages.IMPORT_PACKAGES)
        )
        self.pages[Pages.IMPORT_WIZARD].terminal_state_message.connect(
            self._on_import_terminal_state_message
        )

        # Buildings page - view details
        self.pages[Pages.BUILDINGS].view_building.connect(self._on_view_building)

        # Building details - back to list
        self.pages[Pages.BUILDING_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.BUILDINGS)
        )

        # Units page - view details
        self.pages[Pages.UNITS].view_unit.connect(self._on_view_unit)

        # Unit details - back to list
        self.pages[Pages.UNIT_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.UNITS)
        )

        # Case Details - back to source page (draft or finalized)
        self.pages[Pages.SURVEY_DETAILS].back_requested.connect(self._on_case_details_back)

        # Case Management - view case details
        self.pages[Pages.CASE_MANAGEMENT].case_selected.connect(self._on_case_entity_selected)

        # Case Entity Details - back to case management
        self.pages[Pages.CASE_ENTITY_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.CASE_MANAGEMENT)
        )

        # Case Entity Details - view survey (contextual navigation)
        self.pages[Pages.CASE_ENTITY_DETAILS].survey_clicked.connect(
            self._on_case_entity_survey_clicked
        )

        # Case Entity Details - view claim (contextual navigation)
        self.pages[Pages.CASE_ENTITY_DETAILS].claim_clicked.connect(
            self._on_case_entity_claim_clicked
        )

        # Case Entity Details - toggle editable
        self.pages[Pages.CASE_ENTITY_DETAILS].toggle_editable_requested.connect(
            self._on_toggle_case_editable
        )

        # Case Entity Details - revisit
        self.pages[Pages.CASE_ENTITY_DETAILS].revisit_requested.connect(
            self._on_case_revisit_requested
        )

        # Cases - view survey details (works for all 3 sub-tabs)
        self.pages[Pages.SURVEYS].claim_selected.connect(self._on_draft_claim_selected)

        # Cases - resume draft survey in wizard for editing
        self.pages[Pages.SURVEYS].resume_survey.connect(self._on_resume_draft_survey)

        # Cases - finalize survey → stay on cases page (switch to finalized sub-tab)
        self.pages[Pages.SURVEYS].survey_finalized.connect(
            lambda _: self.navigate_to(Pages.SURVEYS)
        )

        # Completed Claims - view claim details
        self.pages[Pages.CLAIMS].claim_selected.connect(self._on_completed_claim_selected)

        # Add Claim button - start new office survey
        self.pages[Pages.SURVEYS].add_claim_clicked.connect(self._start_new_office_survey)

        # Office Survey Wizard signals
        self.office_survey_wizard.survey_completed.connect(self._on_survey_completed)
        self.office_survey_wizard.survey_cancelled.connect(self._on_survey_cancelled)
        self.office_survey_wizard.survey_saved_draft.connect(self._on_survey_saved_draft)

        # Resume draft survey from CaseDetailsPage
        self.pages[Pages.SURVEY_DETAILS].resume_requested.connect(
            self._on_resume_draft_survey
        )

        # Cancel draft survey from CaseDetailsPage
        self.pages[Pages.SURVEY_DETAILS].cancel_requested.connect(
            self._on_cancel_draft_survey
        )

        # Resume obstructed survey from CaseDetailsPage
        self.pages[Pages.SURVEY_DETAILS].resume_obstructed_requested.connect(
            self._on_resume_obstructed_survey
        )

        # Revert finalized survey to draft from CaseDetailsPage
        self.pages[Pages.SURVEY_DETAILS].revert_requested.connect(
            self._on_revert_survey_to_draft
        )

        # Claim Details page signals
        self.pages[Pages.CLAIM_DETAILS].back_requested.connect(
            self._on_claim_details_back
        )
        self.pages[Pages.CLAIM_DETAILS].edit_requested.connect(
            self._on_edit_claim_requested
        )

        # Claim Edit - back to case details / save completed
        self.pages[Pages.CLAIM_EDIT].back_requested.connect(
            lambda: self.navigate_to(Pages.SURVEYS)
        )
        self.pages[Pages.CLAIM_EDIT].save_completed.connect(
            lambda: self.navigate_to(Pages.SURVEYS)
        )

        # Duplicates page - view comparison
        self.pages[Pages.DUPLICATES].view_comparison_requested.connect(
            lambda group: self.navigate_to(Pages.CLAIM_COMPARISON, group)
        )

        # Claim Comparison - back to duplicates
        self.pages[Pages.CLAIM_COMPARISON].back_requested.connect(
            lambda: self.navigate_to(Pages.DUPLICATES)
        )

        # Sync Data - back to field assignment
        self.pages[Pages.SYNC_DATA].back_requested.connect(
            lambda: self.navigate_to(Pages.FIELD_ASSIGNMENT)
        )

        # Claim Search - back to claims
        if Pages.CLAIM_SEARCH in self.pages:
            self.pages[Pages.CLAIM_SEARCH].back_requested.connect(
                lambda: self.navigate_to(Pages.CLAIMS)
            )

        # Language change signal
        self.language_changed.connect(self._on_language_changed)

    def _show_login(self):
        """Show the login page."""
        self.navbar.setVisible(False)
        self.pages[Pages.LOGIN].set_data_mode(Config.DATA_MODE, self.db)
        self.stack.setCurrentWidget(self.pages[Pages.LOGIN])
        logger.info("Showing login page")

    def _on_login_success(self, user):
        """Handle successful login."""
        self.current_user = user
        logger.info(f"User logged in: {user.username} ({user.role})")

        # Check if password change is required before proceeding
        if getattr(user, 'must_change_password', False):
            logger.info("Password change required for user: %s", user.username)
            self._start_forced_password_change(user)
            return

        self._complete_login(user)

    def _complete_login(self, user):
        """Finalize login: set token, configure UI, load data (non-blocking)."""
        self.current_user = user

        token = getattr(user, '_api_token', None)
        logger.info(f"User API token available: {bool(token)}")
        if token:
            self._set_api_token_for_controllers(token)
        else:
            logger.warning("No API token found in user object - API calls may fail with 401")

        self._start_token_refresh_timer()
        self._show_login_loading()

        # Configure UI immediately (no blocking on vocab refresh)
        # Use a short delay so the loading overlay has time to render
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._finish_login_ui(user))

        # Refresh vocabularies in background (fire-and-forget)
        from services.api_worker import ApiWorker

        def _background_vocab_refresh():
            try:
                from services.vocab_service import refresh_vocabularies
                refresh_vocabularies()
                logger.info("Vocabularies refreshed after login")
            except Exception as e:
                logger.warning(f"Vocab refresh failed (non-critical): {e}")

        self._vocab_worker = ApiWorker(_background_vocab_refresh)
        self._vocab_worker.start()

        # Fetch admin-managed security policy from backend (fire-and-forget)
        def _background_security_policy_refresh():
            from services.security_service import SecurityService
            if not SecurityService.fetch_from_api():
                logger.warning("Security policy fetch returned no data — using local fallback")

        self._security_policy_worker = ApiWorker(_background_security_policy_refresh)
        self._security_policy_worker.start()

        # Pre-initialize map services in background (tile server + landmark icons)
        import threading
        threading.Thread(target=self._prewarm_map_services, daemon=True).start()

    def _prewarm_map_services(self):
        """Pre-initialize map services in background to avoid delays on first map open."""
        try:
            from services.tile_server_manager import TileServerManager
            mgr = TileServerManager.get_instance()
            mgr.get_tile_metadata()
            from services.landmark_icon_service import load_landmark_types
            load_landmark_types()
            logger.debug("Map services pre-warmed successfully")
        except Exception as e:
            logger.debug(f"Map prewarm (non-critical): {e}")

    def _finish_login_ui(self, user):
        """Configure UI after background data loads (runs on main thread)."""
        try:
            # Sync language if it was changed on the login page
            saved_lang = get_saved_language()
            saved_is_arabic = (saved_lang == "ar")
            if saved_is_arabic != self._is_arabic:
                self._is_arabic = saved_is_arabic
                self.i18n.set_language(saved_lang)
                if self._is_arabic:
                    self.setLayoutDirection(Qt.RightToLeft)
                else:
                    self.setLayoutDirection(Qt.LeftToRight)
                self.language_changed.emit(self._is_arabic)

            # Show navbar
            self.navbar.setVisible(True)

            # Update navbar with user info
            self.navbar.set_user_id(str(user.user_id))
            name_ar = getattr(user, 'full_name_ar', '') or ''
            name_en = getattr(user, 'full_name', '') or getattr(user, 'username', '')
            self.navbar.set_username_bilingual(name_ar, name_en)

            # Set user context on CasesPage BEFORE configure_for_role,
            # because configure_for_role emits tab_changed which triggers refresh()
            cases_page = self.pages.get(Pages.SURVEYS)
            if cases_page and hasattr(cases_page, 'configure_for_user'):
                cases_page.configure_for_user(user.role, str(user.user_id))

            # Set user context on CaseManagementPage
            cm_page = self.pages.get(Pages.CASE_MANAGEMENT)
            if cm_page and hasattr(cm_page, 'configure_for_user'):
                cm_page.configure_for_user(user.role)

            # Configure tabs based on user role (RBAC)
            self.navbar.configure_for_role(user.role)

            # Apply role-based button visibility to content pages
            for page_id in (Pages.BUILDINGS, Pages.BUILDING_DETAILS, Pages.UNITS,
                            Pages.PERSONS, Pages.IMPORT_WIZARD, Pages.IMPORT_PACKAGES,
                            Pages.SURVEY_DETAILS, Pages.CASE_ENTITY_DETAILS):
                page = self.pages.get(page_id)
                if page and hasattr(page, 'configure_for_role'):
                    page.configure_for_role(user.role)
        except Exception as e:
            logger.error(f"Error during login UI setup: {e}", exc_info=True)
        finally:
            self._hide_login_loading()
            QApplication.processEvents()

        # Start session timeout timer
        self._start_session_timer()

        # Load field assignment filter data async (requires valid API token)
        if Pages.FIELD_ASSIGNMENT in self.pages:
            field_page = self.pages[Pages.FIELD_ASSIGNMENT]
            if hasattr(field_page, '_load_filter_data_async'):
                field_page._load_filter_data_async()
            elif hasattr(field_page, 'load_data'):
                field_page.load_data()

    # -- Forced Password Change (async UX flow) --

    def _start_forced_password_change(self, user):
        """Step 1: Show password change dialog."""
        from ui.components.dialogs.password_dialog import PasswordDialog
        from ui.components.toast import Toast

        name_ar = getattr(user, 'full_name_ar', '') or ''
        name_en = getattr(user, 'full_name', '') or getattr(user, 'username', '')
        result = PasswordDialog.forced_change_password(
            parent=self, username=name_ar, username_en=name_en
        )
        if result is None:
            Toast.show_toast(self, tr("dialog.password.change_cancelled"), Toast.WARNING)
            self._show_login()
            return

        current_password, new_password = result
        self._pwd_change_user = user
        self._pwd_change_new_password = new_password

        # Step 2: Show loader and call API async
        self._show_login_loading_msg(tr("dialog.password.changing"))

        from services.api_client import get_api_client
        api_client = get_api_client()
        token = getattr(user, '_api_token', None)
        if token:
            api_client.set_access_token(token)

        def _call_change_password(cur_pwd, new_pwd, uid):
            try:
                return api_client.change_password(cur_pwd, new_pwd, user_id=uid)
            except Exception as e:
                detail = ""
                if hasattr(e, 'response_data') and e.response_data:
                    detail = e.response_data.get('message') or ""
                raise Exception(detail) if detail else e

        from services.api_worker import ApiWorker
        self._pwd_worker = ApiWorker(
            _call_change_password,
            current_password, new_password,
            getattr(user, 'user_id', None)
        )
        self._pwd_worker.finished.connect(self._on_password_changed)
        self._pwd_worker.error.connect(self._on_password_change_failed)
        self._pwd_worker.start()

    def _on_password_changed(self, result):
        """Step 3: Password changed — show success dialog, then re-auth."""
        self._hide_login_loading()
        logger.info("Password changed successfully for user: %s",
                     self._pwd_change_user.username)

        from ui.components.dialogs.message_dialog import MessageDialog
        MessageDialog.show_success(
            self,
            tr("dialog.password.change_success_title"),
            tr("dialog.password.change_success_message"),
        )

        # Step 4: Re-authenticate with new password
        self._show_login_loading_msg(tr("dialog.password.logging_in"))

        from services.api_worker import ApiWorker
        from services.api_auth_service import ApiAuthService
        auth_service = ApiAuthService()
        self._reauth_worker = ApiWorker(
            auth_service.authenticate,
            self._pwd_change_user.username,
            self._pwd_change_new_password
        )
        self._reauth_worker.finished.connect(self._on_reauth_finished)
        self._reauth_worker.error.connect(self._on_reauth_failed)
        self._reauth_worker.start()

    def _on_password_change_failed(self, error_msg):
        """Password change API failed — show specific error and retry."""
        self._hide_login_loading()
        logger.error("Password change failed: %s", error_msg)

        from ui.components.dialogs.message_dialog import MessageDialog
        MessageDialog.show_error(
            self,
            tr("page.user_mgmt.password_change_failed_title"),
            error_msg or tr("page.user_mgmt.password_change_failed"),
        )
        self._start_forced_password_change(self._pwd_change_user)

    def _on_reauth_finished(self, result):
        """Step 5: Re-auth done — continue to main app."""
        self._hide_login_loading()

        new_user, error = result if isinstance(result, tuple) else (result, None)
        if new_user and not isinstance(new_user, str):
            self._complete_login(new_user)
        else:
            logger.error("Re-authentication failed: %s", error)
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("page.user_mgmt.password_change_failed"), Toast.ERROR)
            self._show_login()

    def _on_reauth_failed(self, error_msg):
        """Re-authentication failed."""
        self._hide_login_loading()
        logger.error("Re-authentication failed: %s", error_msg)
        from ui.components.toast import Toast
        Toast.show_toast(self, tr("page.user_mgmt.password_change_failed"), Toast.ERROR)
        self._show_login()

    # -- Voluntary Password Change (from navbar settings) --

    def _on_voluntary_password_change(self):
        """User requested password change from settings pill."""
        from ui.components.dialogs.password_dialog import PasswordDialog

        result = PasswordDialog.change_password(parent=self)
        if result is None:
            return

        current_password, new_password = result

        self._show_login_loading_msg(tr("dialog.password.changing"))

        from services.api_client import get_api_client
        api_client = get_api_client()

        user_id = getattr(self.current_user, 'user_id', None)

        def _call_change(cur_pwd, new_pwd, uid):
            try:
                return api_client.change_password(cur_pwd, new_pwd, user_id=uid)
            except Exception as e:
                detail = ""
                if hasattr(e, 'response_data') and e.response_data:
                    detail = e.response_data.get('message') or ""
                raise Exception(detail) if detail else e

        from services.api_worker import ApiWorker
        self._vol_pwd_worker = ApiWorker(
            _call_change, current_password, new_password, user_id
        )
        self._vol_pwd_worker.finished.connect(self._on_voluntary_pwd_success)
        self._vol_pwd_worker.error.connect(self._on_voluntary_pwd_error)
        self._vol_pwd_worker.start()

    def _on_voluntary_pwd_success(self, result):
        self._hide_login_loading()
        from ui.components.dialogs.message_dialog import MessageDialog
        MessageDialog.show_success(
            self,
            tr("dialog.password.change_success_title"),
            tr("dialog.password.change_success_message"),
        )

    def _on_voluntary_pwd_error(self, error_msg):
        self._hide_login_loading()
        logger.error("Voluntary password change failed: %s", error_msg)
        from ui.components.dialogs.message_dialog import MessageDialog
        MessageDialog.show_error(
            self,
            tr("page.user_mgmt.password_change_failed_title"),
            error_msg or tr("page.user_mgmt.password_change_failed"),
        )

    def _show_login_loading_msg(self, message):
        """Show loading spinner with a custom message."""
        from ui.components.loading_spinner import LoadingSpinnerOverlay
        if not hasattr(self, '_login_spinner') or self._login_spinner is None:
            self._login_spinner = LoadingSpinnerOverlay(self, timeout_ms=30_000)
        self._login_spinner.show_loading(message)

    def _show_login_loading(self):
        """Show a loading spinner overlay during post-login data preparation."""
        from ui.components.loading_spinner import LoadingSpinnerOverlay
        if not hasattr(self, '_login_spinner') or self._login_spinner is None:
            self._login_spinner = LoadingSpinnerOverlay(self, timeout_ms=30_000)
        self._login_spinner.show_loading(tr("page.login.loading_data"))

    def _hide_login_loading(self):
        """Hide the loading spinner overlay."""
        if hasattr(self, '_login_spinner') and self._login_spinner:
            self._login_spinner.hide_loading()

    def _start_session_timer(self):
        """Start session inactivity timer based on security settings."""
        from datetime import datetime
        timeout_minutes = 30
        if self.db:
            try:
                from services.security_service import SecurityService
                svc = SecurityService(self.db)
                settings = svc.get_settings()
                timeout_minutes = settings.session_timeout_minutes
            except Exception as e:
                logger.warning(f"Could not load session timeout setting: {e}")

        self._session_timeout_ms = timeout_minutes * 60 * 1000
        self._last_activity = datetime.now()

        # Install app-wide event filter for activity tracking
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

        # Check every 60 seconds
        if self._session_timer is None:
            self._session_timer = QTimer(self)
            self._session_timer.timeout.connect(self._check_session_timeout)
        self._session_timer.start(60000)
        logger.info(f"Session timeout set to {timeout_minutes} minutes")

    def _stop_session_timer(self):
        """Stop session inactivity timer."""
        if self._session_timer:
            self._session_timer.stop()
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)

    def _start_token_refresh_timer(self):
        """Start proactive token refresh every 15 minutes."""
        self._stop_token_refresh_timer()
        self._token_refresh_timer = QTimer(self)
        self._token_refresh_timer.timeout.connect(self._proactive_token_refresh)
        self._token_refresh_timer.start(15 * 60 * 1000)  # 15 minutes
        logger.info("Token refresh timer started (every 15 min)")

    def _stop_token_refresh_timer(self):
        """Stop the proactive token refresh timer."""
        if self._token_refresh_timer:
            self._token_refresh_timer.stop()
            self._token_refresh_timer = None

    def _proactive_token_refresh(self):
        """Proactively refresh the API token before it expires."""
        if not self.current_user:
            self._stop_token_refresh_timer()
            return
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            if api and api.access_token:
                if api.refresh_access_token():
                    logger.info("Proactive token refresh succeeded")
                else:
                    logger.warning("Proactive token refresh failed")
        except Exception as e:
            logger.warning(f"Proactive token refresh error: {e}")

    def eventFilter(self, obj, event):
        """Track user activity for session timeout."""
        from datetime import datetime
        etype = event.type()
        if etype in (QEvent.MouseMove, QEvent.KeyPress,
                     QEvent.MouseButtonPress, QEvent.Wheel):
            self._last_activity = datetime.now()
        return super().eventFilter(obj, event)

    def _check_session_timeout(self):
        """Check if session has timed out due to inactivity."""
        from datetime import datetime
        if not self.current_user or not self._last_activity:
            return
        elapsed_ms = (datetime.now() - self._last_activity).total_seconds() * 1000
        if elapsed_ms >= self._session_timeout_ms:
            self._session_timer.stop()
            logger.warning("Session timed out due to inactivity")
            from ui.components.dialogs.message_dialog import MessageDialog
            MessageDialog.show_warning(
                self,
                "انتهاء الجلسة",
                "انتهت مهلة الجلسة بسبب عدم النشاط. سيتم تسجيل الخروج تلقائياً."
            )
            self._force_logout()

    def _force_logout(self):
        """Force logout without confirmation dialog (session timeout)."""
        if self.current_user:
            logger.info(f"Force logout (session timeout): {self.current_user.username}")
            try:
                from services.api_client import get_api_client
                get_api_client().logout()
            except Exception as e:
                logger.warning(f"API logout failed: {e}")
            from services.security_service import SecurityService
            SecurityService.clear_cache()
            self.current_user = None
            self._stop_session_timer()
            self._stop_token_refresh_timer()
            self._show_login()

    def _set_api_token_for_controllers(self, token: str):
        """Pass API token to all controllers that use API backend."""
        logger.info(f"Setting API token for controllers (token length: {len(token)})")

        # Store token for later use (e.g., when wizard is reset)
        self._api_token = token

        # Set token directly on the API client singleton
        from services.api_client import get_api_client
        api = get_api_client()
        if api:
            api.set_access_token(token)
            refresh = getattr(self.current_user, '_api_refresh_token', None)
            if refresh:
                api.refresh_token = refresh
            api.set_session_expired_callback(self._on_session_expired)
            api.set_password_change_required_callback(self._on_password_change_required)
            api.set_network_error_callback(self._on_network_error)
            logger.info("API token set on singleton")

        # Pass token to BuildingsPage controller
        if Pages.BUILDINGS in self.pages:
            buildings_page = self.pages[Pages.BUILDINGS]
            if hasattr(buildings_page, 'building_controller'):
                buildings_page.building_controller.set_auth_token(token)
                logger.info("API token set for BuildingController")

        # Pass token to Field Work Preparation wizard controller
        if Pages.FIELD_ASSIGNMENT in self.pages:
            field_page = self.pages[Pages.FIELD_ASSIGNMENT]
            if hasattr(field_page, 'building_controller'):
                field_page.building_controller.set_auth_token(token)
                logger.info("API token set for Field Work BuildingController")

        # Pass token to OfficeSurveyWizard controller
        if hasattr(self, 'office_survey_wizard') and self.office_survey_wizard:
            self.office_survey_wizard.set_auth_token(token)
            logger.info("API token set for OfficeSurveyWizard")

        # Pass token to UserController
        if hasattr(self, '_user_controller') and self._user_controller:
            self._user_controller.set_auth_token(token)
            logger.info("API token set for UserController")

    def _on_network_error(self, error_type: str):
        """Handle network/server errors from any API call (called from background thread)."""
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._do_network_error(error_type))

    def _do_network_error(self, error_type: str):
        """Show network error toast (runs on main thread)."""
        from ui.components.toast import Toast
        if error_type == "network":
            msg = "تعذّر الاتصال بالخادم — تحقق من الاتصال بالإنترنت"
        else:
            msg = "خطأ في الخادم — يرجى المحاولة لاحقاً"
        Toast.show_toast(self, msg, Toast.ERROR, 6000)

    def _on_session_expired(self):
        """Handle session expiry (called from background thread)."""
        if not self.current_user:
            return
        if getattr(self, '_session_expiry_pending', False):
            return
        self._session_expiry_pending = True
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self._do_session_expired)

    def _do_session_expired(self):
        """Show expiry toast and redirect to login (runs on main thread)."""
        self._session_expiry_pending = False
        if not self.current_user:
            return
        logger.warning(f"Session expired for user: {self.current_user.username}")
        from ui.components.toast import Toast
        Toast.show_toast(
            self,
            "انتهت صلاحية الجلسة، يرجى تسجيل الدخول مجدداً",
            Toast.WARNING,
            5000
        )
        from services.security_service import SecurityService
        SecurityService.clear_cache()
        self.current_user = None
        self._stop_session_timer()
        self._stop_token_refresh_timer()
        self._show_login()

    def _on_password_change_required(self):
        """Handle password change required from API 403 (called from background thread)."""
        if not self.current_user:
            return
        if getattr(self, '_password_change_pending', False):
            return
        self._password_change_pending = True
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self._do_password_change_required)

    def _do_password_change_required(self):
        """Show password change dialog (runs on main thread)."""
        self._password_change_pending = False
        if not self.current_user:
            return
        logger.warning(f"Password change required for user: {self.current_user.username}")
        from ui.components.toast import Toast
        Toast.show_toast(
            self,
            tr("dialog.password.change_required_message"),
            Toast.WARNING,
            5000
        )
        self._start_forced_password_change(self.current_user)

    def _handle_logout(self):
        """Handle logout request."""
        if self.current_user:
            from ui.components.dialogs.logout_dialog import LogoutDialog
            if LogoutDialog.confirm_logout(parent=self):
                logger.info(f"User logged out: {self.current_user.username}")
                try:
                    from services.api_client import get_api_client
                    get_api_client().logout()
                except Exception as e:
                    logger.warning(f"API logout failed (proceeding with local logout): {e}")
                from services.security_service import SecurityService
                SecurityService.clear_cache()
                self.current_user = None
                self._stop_session_timer()
                self._stop_token_refresh_timer()
                # Clear login fields for security
                login_page = self.pages.get(Pages.LOGIN)
                if login_page:
                    if hasattr(login_page, 'username_input'):
                        login_page.username_input.clear()
                    if hasattr(login_page, 'password_input'):
                        login_page.password_input.clear()
                self._show_login()

    def _on_field_work_completed(self, workflow_data):
        """Handle field work wizard completion - create assignment via API."""
        try:
            from ui.components.toast import Toast
            from services.api_client import get_api_client

            logger.info(f"_on_field_work_completed received: {type(workflow_data)}")
            buildings = workflow_data.get('buildings', [])
            researcher = workflow_data.get('researcher', {})
            revisit_reasons = workflow_data.get('revisit_reasons', {})
            researcher_name = researcher.get('name', 'N/A')
            researcher_id = researcher.get('id', '')
            building_count = len(buildings)

            if not buildings or not researcher_id:
                logger.error("Missing buildings or researcher ID for assignment")
                Toast.show_toast(self, "\u0628\u064a\u0627\u0646\u0627\u062a \u063a\u064a\u0631 \u0645\u0643\u062a\u0645\u0644\u0629 \u0644\u0644\u062a\u0639\u064a\u064a\u0646", Toast.ERROR)
                return

            # Build buildings payload (assignment is at building level)
            buildings_payload = []
            for b in buildings:
                b_uuid = getattr(b, 'building_uuid', None) or (
                    b.get('building_uuid') if isinstance(b, dict) else None
                )
                b_id = getattr(b, 'building_id', None) or (
                    b.get('building_id') if isinstance(b, dict) else None
                )
                item = {"buildingId": b_uuid}
                reason = revisit_reasons.get(b_id)
                if reason:
                    item["revisitReason"] = reason
                buildings_payload.append(item)

            logger.info(f"Creating API assignment: {building_count} buildings -> {researcher_name} ({researcher_id})")

            try:
                api = get_api_client()
                api_response = api.create_assignment(
                    buildings=buildings_payload,
                    field_collector_id=researcher_id,
                )
                logger.info("Assignment created on backend API successfully")

                # Extract assignment IDs from response
                api_assignment_ids = []
                if isinstance(api_response, dict):
                    api_assignment_ids = api_response.get("createdAssignmentIds", [])
                    if not api_assignment_ids:
                        for a in api_response.get("assignments", []):
                            aid = a.get("id") or a.get("assignmentId")
                            if aid:
                                api_assignment_ids.append(aid)

            except Exception as api_err:
                logger.error(f"API assignment creation failed: {api_err}")
                Toast.show_toast(
                    self,
                    f"فشل إنشاء التعيين في الخادم: {str(api_err)}",
                    Toast.ERROR
                )
                return

            Toast.show_toast(
                self,
                f"تم إسناد {building_count} مبنى إلى {researcher_name}",
                Toast.SUCCESS
            )

            # Invalidate building cache so map reflects new assignment status
            try:
                from services.building_cache_service import BuildingCacheService
                BuildingCacheService.get_instance().invalidate_cache()
            except Exception:
                pass

            effective_ids = api_assignment_ids

            # Reset wizard and navigate to sync data page
            if Pages.FIELD_ASSIGNMENT in self.pages:
                field_page = self.pages[Pages.FIELD_ASSIGNMENT]
                if hasattr(field_page, 'refresh'):
                    field_page.refresh()

            self.navigate_to(Pages.SYNC_DATA)

        except Exception as e:
            logger.error(f"Error in _on_field_work_completed: {e}", exc_info=True)

    def _on_import_requested(self):
        """Handle import data request from navbar menu."""
        self.navigate_to(Pages.IMPORT_PACKAGES)

    def _on_view_import_package(self, pkg_id: str):
        """Open the import wizard on a specific package id.

        We pass the id through navigate_to's `data` so the wizard's delayed
        refresh(data=pkg_id) routes by backend status atomically. Calling
        set_package_id eagerly here would race the navigate_to refresh.
        """
        self.navigate_to(Pages.IMPORT_WIZARD, str(pkg_id) if pkg_id else None)

    def _on_import_completed_silent_refresh(self, _data):
        """Refresh the packages list in the background without leaving the report.

        Connected to ImportWizard.completed. The wizard already switched
        to its Final Report step internally; we only need to make sure
        the IMPORT_PACKAGES page reflects the new Completed status for
        when the user eventually presses "العودة إلى قائمة الحزم". Do
        NOT call navigate_to here — that would yank the user off the
        report they're trying to read.
        """
        pkg_page = self.pages.get(Pages.IMPORT_PACKAGES)
        if pkg_page is None:
            return
        for method_name in ("_load_packages", "refresh"):
            fn = getattr(pkg_page, method_name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
                break

    def _on_import_terminal_state_message(self, severity: str, message_ar: str):
        """Show a Toast on the packages page after a wizard bounce.

        Without this, silent bounces (Quarantined / Failed / etc.) made
        users believe their package had completed successfully. The Toast
        is shown with a longer duration (6s) so the user has time to read
        the reason before it dismisses.
        """
        from ui.components.toast import Toast
        if not message_ar:
            return
        sev = (severity or "info").lower()
        kind = (
            Toast.ERROR if sev == "error"
            else Toast.WARNING if sev == "warning"
            else Toast.INFO
        )
        target = self.pages.get(Pages.IMPORT_PACKAGES) or self
        try:
            Toast.show_toast(target, message_ar, kind, duration=6000)
        except Exception:
            try:
                Toast.show_toast(target, message_ar, kind)
            except Exception:
                pass

    def _on_import_navigate_to_duplicates(self, package_id: str = ""):
        """Navigate from import wizard to duplicates page, scoped to this package."""
        dup_page = self.pages.get(Pages.DUPLICATES)
        import_page = self.pages.get(Pages.IMPORT_WIZARD)
        if not dup_page:
            return

        pkg_id = str(package_id) if package_id else ""
        pkg_name = ""
        if import_page and hasattr(import_page, "current_package_name"):
            try:
                pkg_name = import_page.current_package_name() or ""
            except Exception:
                pkg_name = ""

        if pkg_id:
            dup_page.set_import_context(pkg_id, pkg_name)
        else:
            dup_page.set_return_to_import(True)
            dup_page.refresh()
        self.navbar.set_current_tab(4)
        self.stack.setCurrentWidget(dup_page)

    def _on_duplicates_return_to_import(self):
        """Return from duplicates page to the import wizard.

        Steps in order:
          1. Capture the package id from the duplicates page (or wizard) so
             we can re-route even if the wizard had been torn down.
          2. Hide the duplicates banner. We do NOT call clear_import_context()
             here — that triggers a wasted /conflicts reload BEFORE we
             switch pages. The next time the user opens duplicates with a
             different context (or no context) the import-context state will
             be reset by set_import_context / set_return_to_import.
          3. Switch the visible widget to the wizard FIRST, then refresh.
          4. Force the wizard to re-fetch the package status and route to
             the right step. Even if the wizard previously had no
             _current_package_id, we re-seed it from the duplicates page's
             import context.
        """
        dup_page = self.pages.get(Pages.DUPLICATES)
        import_page = self.pages.get(Pages.IMPORT_WIZARD)

        # Recover the package id — duplicates page knows it via import-context.
        pkg_id = ""
        if dup_page is not None and hasattr(dup_page, "_import_package_id"):
            pkg_id = str(getattr(dup_page, "_import_package_id", "") or "")
        if not pkg_id and import_page is not None:
            pkg_id = str(getattr(import_page, "_current_package_id", "") or "")

        if dup_page is not None:
            try:
                dup_page.set_return_to_import(False)
            except Exception:
                pass

        if import_page is None:
            return

        # Tab 3 maps to IMPORT_PACKAGES, not the wizard, so we don't change
        # the navbar tab here — switching the stack widget is enough and
        # avoids a flicker through the packages list.
        self.stack.setCurrentWidget(import_page)

        # Re-route the wizard. Prefer the package id we captured above —
        # set_package_id tears down stale step widgets, fetches the latest
        # status, and routes to the right step (ReadyToCommit → Step 2,
        # ReviewingConflicts → back to duplicates, etc.).
        if pkg_id and hasattr(import_page, "set_package_id"):
            import_page.set_package_id(pkg_id)
        elif hasattr(import_page, "refresh_current_package"):
            import_page.refresh_current_package()

        # Now that the wizard owns the navigation, the duplicates page can
        # safely drop its import context (no longer needs to be in import
        # mode). This is async-safe because the dup_page is no longer the
        # visible widget.
        if dup_page is not None and hasattr(dup_page, "_import_package_id"):
            try:
                dup_page._import_package_id = None
                dup_page._import_package_name = ""
                if hasattr(dup_page, "_import_banner"):
                    dup_page._import_banner.setVisible(False)
            except Exception:
                pass

    def _on_sync_requested(self):
        """Handle sync data request from navbar menu."""
        self.navbar.hide_sync_notification()
        sync_page = self.pages.get(Pages.SYNC_DATA)
        if sync_page:
            sync_page.clear_notifications()
        self.navigate_to(Pages.SYNC_DATA)

    def _on_sync_notification(self, count: int):
        if count > 0:
            self.navbar.show_sync_notification(count)
        else:
            self.navbar.hide_sync_notification()

    def _on_tab_changed(self, tab_index: int):
        """Handle navbar tab change."""
        if tab_index in self.tab_page_mapping:
            page_id = self.tab_page_mapping[tab_index]
            self.navigate_to(page_id)
            logger.debug(f"Tab {tab_index} selected -> navigating to {page_id}")
        else:
            logger.warning(f"No page mapped to tab index: {tab_index}")

    def _on_search_requested(self, search_text: str):
        """Handle search request from navbar."""
        logger.info(f"Search requested: {search_text}")
        # If on draft claims page, search within drafts
        current_page = self.stack.currentWidget()
        if current_page == self.pages.get(Pages.SURVEYS):
            search_mode = getattr(self.navbar, 'search_mode', 'name')
            current_page.search_claims(search_text, search_mode)
            return

    def _on_filter_applied(self, filters: dict):
        """Handle filter applied from navbar filter popup."""
        current_page = self.stack.currentWidget()
        if current_page == self.pages.get(Pages.SURVEYS):
            current_page.apply_filters(filters)

    def navigate_to(self, page_id: str, data=None):
        """Navigate to a specific page."""
        # Check if currently in wizard with unsaved data
        current_widget = self.stack.currentWidget()
        if current_widget == self.office_survey_wizard and page_id != "office_survey_wizard":
            if self._has_unsaved_wizard_data():
                from ui.components.bottom_sheet import BottomSheet
                from PyQt5.QtCore import QEventLoop
                loop = QEventLoop()
                choice_result = [None]

                def on_choice(c):
                    choice_result[0] = c
                    loop.quit()

                def on_cancel():
                    choice_result[0] = "cancel"
                    loop.quit()

                sheet = BottomSheet(self)
                sheet.choice_made.connect(on_choice)
                sheet.cancelled.connect(on_cancel)
                sheet.show_choices(
                    tr("wizard.confirm.save_title"),
                    [
                        ("save", tr("wizard.confirm.save_draft")),
                        ("discard", tr("wizard.confirm.discard")),
                    ]
                )
                loop.exec_()

                if choice_result[0] == "save":
                    draft_id = self.office_survey_wizard.on_save_draft()
                    if draft_id:
                        if Pages.SURVEYS in self.pages:
                            self.pages[Pages.SURVEYS].refresh()
                    else:
                        logger.warning("Failed to save draft")
                        return

                elif choice_result[0] == "discard":
                    survey_id = self.office_survey_wizard.context.get_data("survey_id")
                    if survey_id:
                        reason_loop = QEventLoop()
                        reason_result = [None]

                        def on_reason_confirmed():
                            reason_data = reason_sheet.get_form_data()
                            reason_result[0] = (reason_data.get("reason") or "").strip()
                            reason_loop.quit()

                        def on_reason_cancelled():
                            reason_result[0] = None
                            reason_loop.quit()

                        reason_sheet = BottomSheet(self)
                        reason_sheet.confirmed.connect(on_reason_confirmed)
                        reason_sheet.cancelled.connect(on_reason_cancelled)
                        reason_sheet.show_form(
                            tr("wizard.cancel_reason_title"),
                            [("reason", tr("wizard.cancel_reason_prompt"), "multiline")],
                            submit_text=tr("page.case_details.confirm_cancel"),
                            cancel_text=tr("action.dismiss"),
                        )
                        reason_loop.exec_()

                        if not reason_result[0]:
                            return
                        try:
                            from services.api_client import get_api_client
                            api = get_api_client()
                            if self._api_token:
                                api.set_access_token(self._api_token)
                            api.cancel_survey(survey_id, reason_result[0])
                            logger.info(f"Survey {survey_id} cancelled: {reason_result[0]}")
                        except Exception as e:
                            logger.warning(f"Failed to cancel survey {survey_id}: {e}")
                    logger.info("User discarded wizard changes")

                else:
                    logger.debug("User cancelled navigation")
                    return

            # Reset wizard for next time (after finalization or unsaved data handling)
            self._reset_wizard()

        # Block restricted pages for unauthorized roles
        if page_id in self._PAGE_ROLE_ACCESS and self.current_user:
            role = getattr(self.current_user, 'role', None)
            if role not in self._PAGE_ROLE_ACCESS[page_id]:
                from ui.components.toast import Toast
                Toast.show_toast(self, "غير مخوّل: لا تملك صلاحية الوصول إلى هذه الصفحة", Toast.ERROR)
                logger.warning(f"Access denied: {self.current_user.username} ({role}) -> {page_id}")
                return

        # Proceed with navigation
        if page_id not in self.pages:
            # Handle special case: office survey wizard
            if page_id == "office_survey_wizard":
                self._fade_to_widget(self.office_survey_wizard)
                return
            logger.error(f"Page not found: {page_id}")
            return

        page = self.pages[page_id]

        # Clear sync notification badge when navigating to sync page
        if page_id == Pages.SYNC_DATA:
            self.navbar.hide_sync_notification()
            if hasattr(page, 'clear_notifications'):
                page.clear_notifications()

        # Sync navbar active tab to match the navigated page
        page_to_tab = {v: k for k, v in self.tab_page_mapping.items()}
        if page_id in page_to_tab:
            self.navbar.set_current_tab(page_to_tab[page_id])

        # Refresh page data if method exists
        # Show page first, then refresh after fade-in completes
        # to avoid QGraphicsOpacityEffect conflicts with child widgets
        self._fade_to_widget(page)

        if hasattr(page, 'refresh'):
            QTimer.singleShot(200, lambda p=page, d=data: p.refresh(d))
        logger.debug(f"Navigated to: {page_id}")

    def _fade_to_widget(self, widget):
        """Switch page with a quick cross-fade animation."""
        from PyQt5.QtWidgets import QGraphicsOpacityEffect
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        effect.setOpacity(0)
        self.stack.setCurrentWidget(widget)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(150)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start()
        self._page_anim = anim

    def _has_unsaved_wizard_data(self) -> bool:
        
        wizard = self.office_survey_wizard

        # If finalization was completed, no need to show save dialog
        if hasattr(wizard, '_finalization_complete') and wizard._finalization_complete:
            return False

        context = wizard.context

        # Once a survey_id exists, there is a real backend survey that can be
        # saved as draft or cancelled, so leaving must show the bottom sheet.
        survey_id = None
        if hasattr(context, "get_data"):
            survey_id = context.get_data("survey_id")

        if survey_id:
            return True

        # If the user moved beyond Step 0, treat the wizard as an active flow.
        # In the normal flow, Step 0 validation creates survey_id before moving on.
        current_index = wizard.navigator.current_index
        if current_index >= 1:
            return True

        # Step 0 + selected building only = no real survey yet.
        # Do not block tab switching and do not show the bottom sheet.
        return False

    def _reset_wizard(self, building=None):
        """Reset wizard to clean state."""
        new_context = self.office_survey_wizard.create_context()
        if building is not None:
            new_context.building = building
        self.office_survey_wizard.context = new_context

        for step in self.office_survey_wizard.steps:
            step.context = new_context

        self.office_survey_wizard.navigator.context = new_context
        self.office_survey_wizard.navigator.reset()

        # Reset finalization flag for next survey
        self.office_survey_wizard._finalization_complete = False

        # Re-set API token after reset (steps may have new controllers)
        if hasattr(self, '_api_token') and self._api_token:
            self.office_survey_wizard.set_auth_token(self._api_token)

    def _on_view_building(self, building):
        """Handle view building request from buildings list."""
        logger.debug(f"Viewing building: {getattr(building, 'building_id', building)}")
        self.navigate_to(Pages.BUILDING_DETAILS, building)

    def _on_view_unit(self, unit):
        """Handle view unit request from units list."""
        logger.debug(f"Viewing unit: {getattr(unit, 'unit_id', unit)}")
        self.navigate_to(Pages.UNIT_DETAILS, unit)

    def _on_draft_claim_selected(self, claim_id: str):
        """Navigate to case details — fetch full survey context from Surveys/office API."""
        logger.info(f"Draft survey selected: {claim_id}")

        claims_page = self.pages[Pages.SURVEYS]
        claim_data = None
        for c in claims_page._all_data:
            if c.get('claim_id') == claim_id:
                claim_data = c
                break

        if not claim_data:
            logger.warning(f"Survey data not found for: {claim_id}")
            return

        survey_uuid = claim_data.get('claim_uuid')
        if not survey_uuid:
            logger.warning(f"Could not load survey details for: {claim_id}")
            return

        self._show_login_loading_msg(tr("component.loading.default"))

        from services.api_worker import ApiWorker

        def _fetch():
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            return ctrl.get_survey_full_context(survey_uuid)

        self._draft_claim_worker = ApiWorker(_fetch)
        self._draft_claim_worker.finished.connect(
            lambda result: self._on_draft_claim_fetched(result, claim_id)
        )
        self._draft_claim_worker.error.connect(
            lambda msg: self._on_draft_claim_fetch_error(msg, claim_id)
        )
        self._draft_claim_worker.start()

    def _on_draft_claim_fetched(self, result, claim_id):
        self._hide_login_loading()
        if result and result.success and result.data:
            self.navigate_to(Pages.SURVEY_DETAILS, result.data)
        else:
            from ui.components.toast import Toast
            msg = getattr(result, 'message', '') if result else ''
            Toast.show_toast(self, msg or "فشل تحميل بيانات المسح", Toast.ERROR)

    def _on_draft_claim_fetch_error(self, error_msg, claim_id):
        self._hide_login_loading()
        logger.warning(f"Survey context fetch failed for {claim_id}: {error_msg}")

    def _on_resume_draft_survey(self, survey_uuid: str):
        """Load draft survey into wizard for editing and resumption."""
        if not survey_uuid:
            return

        self._show_login_loading_msg(tr("component.loading.default"))

        from services.api_worker import ApiWorker

        def _fetch():
            from controllers.survey_controller import SurveyController
            return SurveyController(self.db).get_survey_full_context(survey_uuid)

        self._resume_draft_worker = ApiWorker(_fetch)
        self._resume_draft_worker.finished.connect(
            lambda result: self._on_resume_draft_loaded(result, survey_uuid)
        )
        self._resume_draft_worker.error.connect(
            lambda msg: self._on_resume_draft_error(msg, survey_uuid)
        )
        self._resume_draft_worker.start()

    def _on_resume_draft_loaded(self, result, survey_uuid):
        """Handle resume draft data loaded from API."""
        self._hide_login_loading()
        if not result or not result.success or not result.data:
            logger.warning(f"Could not load draft context for: {survey_uuid}")
            from ui.components.toast import Toast
            msg = getattr(result, 'message', '') if result else ''
            Toast.show_toast(self, msg or "فشل تحميل المسودة", Toast.ERROR)
            return

        try:
            from ui.wizards.office_survey.survey_context import SurveyContext
            new_context = SurveyContext.from_dict(result.data)

            self.office_survey_wizard.context = new_context
            for step in self.office_survey_wizard.steps:
                step.context = new_context
            self.office_survey_wizard.navigator.context = new_context
            self.office_survey_wizard._finalization_complete = False

            if hasattr(self, '_api_token') and self._api_token:
                self.office_survey_wizard.set_auth_token(self._api_token)

            resume_step = result.data.get("resume_step", 1)
            self.office_survey_wizard.navigator.goto_step(resume_step, skip_validation=True)

            self.navigate_to("office_survey_wizard")
            logger.info(f"Draft survey {survey_uuid} resumed at step {resume_step}")
        except Exception as e:
            logger.error(f"Failed to resume draft {survey_uuid}: {e}")

    def _on_resume_draft_error(self, error_msg, survey_uuid):
        """Handle resume draft fetch failure."""
        self._hide_login_loading()
        logger.error(f"Failed to resume draft {survey_uuid}: {error_msg}")

    def _on_case_entity_selected(self, case_id: str):
        """Handle case card click from CaseManagementPage — navigate to case entity details."""
        logger.info(f"Case entity selected: {case_id}")
        cm_page = self.pages.get(Pages.CASE_MANAGEMENT)
        if cm_page:
            cm_page._navigating = False
            if hasattr(cm_page, '_spinner'):
                cm_page._spinner.hide_loading()
        self.navigate_to(Pages.CASE_ENTITY_DETAILS, {"case_id": case_id})

    def _fetch_survey_for_case(self, survey_uuid: str):
        """Fetch full survey context by UUID and navigate to CaseDetailsPage."""
        self._show_login_loading_msg(tr("component.loading.default"))

        from services.api_worker import ApiWorker

        def _fetch():
            from controllers.survey_controller import SurveyController
            ctrl = SurveyController(self.db)
            return ctrl.get_survey_full_context(survey_uuid)

        def _on_fetched(result):
            self._hide_login_loading()
            if result and result.success and result.data:
                self.navigate_to(Pages.SURVEY_DETAILS, result.data)
            else:
                from ui.components.toast import Toast
                msg = getattr(result, 'message', '') if result else ''
                Toast.show_toast(self, msg or tr("page.case_management.load_failed"), Toast.ERROR)

        def _on_err(msg):
            self._hide_login_loading()
            logger.error(f"Survey fetch for case failed: {msg}")

        worker = ApiWorker(_fetch)
        worker.finished.connect(_on_fetched)
        worker.error.connect(_on_err)
        self._case_survey_worker = worker
        worker.start()

    def _on_case_details_back(self):
        """Navigate back from CaseDetailsPage (survey details).
        If navigated from case entity details, return there; otherwise go to surveys list."""
        if self._back_to_case_entity and self._case_entity_case_id:
            case_id = self._case_entity_case_id
            self._back_to_case_entity = False
            self._case_entity_case_id = None
            self.navigate_to(Pages.CASE_ENTITY_DETAILS, {"case_id": case_id})
        else:
            self.navigate_to(Pages.SURVEYS)

    def _on_claim_details_back(self):
        """Navigate back from ClaimDetailsPage.
        If navigated from case entity details, return there; otherwise go to claims list."""
        if self._back_to_case_entity and self._case_entity_case_id:
            case_id = self._case_entity_case_id
            self._back_to_case_entity = False
            self._case_entity_case_id = None
            self.navigate_to(Pages.CASE_ENTITY_DETAILS, {"case_id": case_id})
        else:
            self.navigate_to(Pages.CLAIMS)

    def _on_case_entity_survey_clicked(self, survey_id: str):
        """Navigate to survey details from case entity details (contextual)."""
        ce_page = self.pages.get(Pages.CASE_ENTITY_DETAILS)
        if ce_page and ce_page._case:
            self._back_to_case_entity = True
            self._case_entity_case_id = ce_page._case.id
        self._fetch_survey_for_case(survey_id)

    def _on_case_entity_claim_clicked(self, claim_id: str):
        """Navigate to claim details from case entity details (contextual)."""
        ce_page = self.pages.get(Pages.CASE_ENTITY_DETAILS)
        if ce_page and ce_page._case:
            self._back_to_case_entity = True
            self._case_entity_case_id = ce_page._case.id
        self.navigate_to(Pages.CLAIM_DETAILS, {"claim_id": claim_id})

    def _on_toggle_case_editable(self, case_id: str, is_editable: bool):
        """Toggle the editable flag on a case via API."""
        from services.translation_manager import tr
        from ui.error_handler import ErrorHandler

        action_key = "page.case_entity.unlock_editing" if is_editable else "page.case_entity.lock_editing"
        action_text = tr(action_key)
        confirmed = ErrorHandler.confirm(
            self,
            tr("page.case_entity.lock_confirm_msg", action=action_text),
            tr("page.case_entity.lock_confirm_title"),
        )
        if not confirmed:
            return

        from services.api_worker import ApiWorker

        def _toggle():
            from services.api_client import get_api_client
            api = get_api_client()
            api.set_case_editable(case_id, is_editable)
            return is_editable

        def _on_done(new_val):
            ce_page = self.pages.get(Pages.CASE_ENTITY_DETAILS)
            if ce_page and hasattr(ce_page, 'update_after_editable_toggle'):
                ce_page.update_after_editable_toggle(new_val)
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("page.case_entity.editable_updated"), Toast.SUCCESS)

        def _on_err(msg):
            logger.error(f"Toggle editable failed: {msg}")
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("page.case_entity.editable_update_failed"), Toast.ERROR)

        worker = ApiWorker(_toggle)
        worker.finished.connect(_on_done)
        worker.error.connect(_on_err)
        self._toggle_editable_worker = worker
        worker.start()

    def _on_case_revisit_requested(self, revisit_data: dict):
        """Handle revisit request from case entity details — navigate to field work wizard Step 2."""
        from services.api_worker import ApiWorker
        property_unit_id = revisit_data.get("property_unit_id", "")

        def _fetch():
            from services.api_client import get_api_client
            return get_api_client().get_property_unit_by_id(property_unit_id)

        def _on_done(unit_dto):
            from ui.components.toast import Toast
            if not unit_dto:
                Toast.show_toast(self, "\u062a\u0639\u0630\u0651\u0631 \u062a\u062d\u062f\u064a\u062f \u0627\u0644\u0645\u0628\u0646\u0649", Toast.ERROR)
                return
            building_id = unit_dto.get("buildingId") or unit_dto.get("building_id") or ""
            if not building_id:
                Toast.show_toast(self, "\u062a\u0639\u0630\u0651\u0631 \u062a\u062d\u062f\u064a\u062f \u0627\u0644\u0645\u0628\u0646\u0649", Toast.ERROR)
                return
            self.navigate_to(Pages.FIELD_ASSIGNMENT, data={
                'revisit_mode': True,
                'building_id': building_id,
                'unit_id': property_unit_id,
            })

        def _on_err(msg):
            logger.error(f"Revisit unit fetch failed: {msg}")
            from ui.components.toast import Toast
            Toast.show_toast(self, "\u0641\u0634\u0644 \u062a\u062d\u0645\u064a\u0644 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0645\u0642\u0633\u0645", Toast.ERROR)

        worker = ApiWorker(_fetch)
        worker.finished.connect(_on_done)
        worker.error.connect(_on_err)
        self._revisit_fetch_worker = worker
        worker.start()

    def _on_edit_claim_requested(self, claim_id: str):
        """Navigate to ClaimEditPage, passing claim_id + survey_id from current context."""
        case_page = self.pages.get(Pages.SURVEY_DETAILS)
        data = {"claim_id": claim_id}
        if case_page and case_page._context:
            survey_id = case_page._context.get_data("survey_id")
            if survey_id:
                data["survey_id"] = survey_id
        self.navigate_to(Pages.CLAIM_EDIT, data)

    def _on_completed_claim_selected(self, claim_id: str):
        """Navigate to claim details page."""
        logger.info(f"Claim selected: {claim_id}")
        self.navigate_to(Pages.CLAIM_DETAILS, {"claim_id": claim_id})

    def _start_new_office_survey(self):
        """Start a new office survey."""
        from PyQt5.QtWidgets import QDialog
        from ui.components.building_map_dialog_v2 import MultiSelectBuildingMapDialog

        logger.info("Starting new office survey — opening building map dialog")

        # Pause shimmer animation on the surveys page while the map dialog is open.
        # The shimmer timer fires every 80ms on the main thread (card.update() for every
        # survey card), which starves QWebEngineView initialization and makes the map
        # appear slow. Field work preparation has no such background timer, which is why
        # that path opens the same dialog noticeably faster.
        surveys_page = self.pages.get(Pages.SURVEYS)
        shimmer_was_active = (
            surveys_page is not None
            and hasattr(surveys_page, '_shimmer_timer')
            and surveys_page._shimmer_timer.isActive()
        )
        if shimmer_was_active:
            surveys_page._shimmer_timer.stop()

        header_timer_was_active = (
            surveys_page is not None
            and hasattr(surveys_page, '_header')
            and hasattr(surveys_page._header, '_timer')
            and surveys_page._header._timer.isActive()
        )
        if header_timer_was_active:
            surveys_page._header._timer.stop()

        auth_token = getattr(self, '_api_token', None)
        try:
            dialog = MultiSelectBuildingMapDialog(
                db=self.db,
                auth_token=auth_token,
                parent=self,
                max_selection=1,
            )
            result = dialog.exec_()
        finally:
            if shimmer_was_active:
                surveys_page._shimmer_timer.start()
            if header_timer_was_active:
                surveys_page._header._timer.start()

        if result != QDialog.Accepted:
            logger.debug("Building selection cancelled")
            return

        buildings = dialog.get_selected_buildings()
        if not buildings:
            logger.warning("Map dialog accepted but no building selected")
            return
        selected_building = buildings[0]

        logger.info(f"Building selected: {selected_building.building_id}")

        self._reset_wizard(building=selected_building)
        self.stack.setCurrentWidget(self.office_survey_wizard)

    def _on_survey_completed(self, data):
        """Handle survey completion from wizard — navigate to surveys page."""
        logger.info(f"Survey completed: {data}")
        self.pages[Pages.SURVEYS].refresh()
        self.navbar.set_current_tab(1)
        self._on_tab_changed(1)

    def _on_survey_cancelled(self):
        """Handle survey cancellation from wizard."""
        logger.info("Survey cancelled")
        self.navbar.set_current_tab(1)
        self._on_tab_changed(1)

    def _on_cancel_draft_survey(self, survey_id: str, reason: str):
        """Cancel a draft survey via API."""
        from ui.components.toast import Toast
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            if self._api_token:
                api.set_access_token(self._api_token)
            api.cancel_survey(survey_id, reason)
            Toast.show_toast(self, "تم إلغاء المسح بنجاح", Toast.SUCCESS)
            self.navigate_to(Pages.SURVEYS)
            if Pages.SURVEYS in self.pages and hasattr(self.pages[Pages.SURVEYS], 'refresh'):
                self.pages[Pages.SURVEYS].refresh()
        except Exception as e:
            logger.error(f"Failed to cancel survey {survey_id}: {e}", exc_info=True)
            Toast.show_toast(self, f"فشل إلغاء المسح: {e}", Toast.ERROR)

    def _on_resume_obstructed_survey(self, survey_id: str):
        """Resume an obstructed survey via API (Obstructed → Draft)."""
        from ui.components.toast import Toast
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            if self._api_token:
                api.set_access_token(self._api_token)
            api.resume_obstructed_survey(survey_id)
            Toast.show_toast(self, tr("wizard.draft.saved_success"), Toast.SUCCESS)
            self.navigate_to(Pages.SURVEYS)
            if Pages.SURVEYS in self.pages and hasattr(self.pages[Pages.SURVEYS], 'refresh'):
                self.pages[Pages.SURVEYS].refresh()
        except Exception as e:
            logger.error(f"Failed to resume obstructed survey {survey_id}: {e}", exc_info=True)
            Toast.show_toast(self, f"فشل استئناف المسح: {e}", Toast.ERROR)

    def _on_revert_survey_to_draft(self, survey_id: str, reason: str):
        """Revert a finalized survey back to Draft via API."""
        from ui.components.toast import Toast
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            if self._api_token:
                api.set_access_token(self._api_token)
            api.revert_survey_to_draft(survey_id, reason)
            Toast.show_toast(self, tr("wizard.draft.saved_success"), Toast.SUCCESS)
            self.navigate_to(Pages.SURVEYS)
            if Pages.SURVEYS in self.pages and hasattr(self.pages[Pages.SURVEYS], 'refresh'):
                self.pages[Pages.SURVEYS].refresh()
        except Exception as e:
            logger.error(f"Failed to revert survey {survey_id} to draft: {e}", exc_info=True)
            Toast.show_toast(self, f"فشل إعادة المسح للمسودة: {e}", Toast.ERROR)

    def _on_survey_saved_draft(self, survey_id: str):
        """Handle survey saved as draft."""
        logger.info(f"Survey saved as draft: {survey_id}")
        if hasattr(self.pages.get(Pages.SURVEYS), 'refresh'):
            self.pages[Pages.SURVEYS].refresh()
        self.navigate_to(Pages.SURVEYS)

    def toggle_language(self):
        """Toggle language directly between Arabic and English."""
        from ui.components.loading_spinner import LoadingSpinnerOverlay

        if not hasattr(self, '_lang_spinner'):
            self._lang_spinner = LoadingSpinnerOverlay(self, timeout_ms=10_000)
        self._lang_spinner.show_loading(tr("app.changing_language"))

        new_lang = "en" if self._is_arabic else "ar"
        self._is_arabic = (new_lang == "ar")
        self.i18n.set_language(new_lang)
        tm_set_language(new_lang)
        save_language(new_lang)

        from PyQt5.QtWidgets import QApplication as _QApp
        direction = Qt.RightToLeft if self._is_arabic else Qt.LeftToRight
        _QApp.instance().setLayoutDirection(direction)
        self.setLayoutDirection(direction)

        self.language_changed.emit(self._is_arabic)
        logger.info(f"Language changed to: {'Arabic' if self._is_arabic else 'English'}")

        QTimer.singleShot(300, self._lang_spinner.hide_loading)

    def _on_language_changed(self, is_arabic: bool):
        """Handle language change across all components."""
        # Update all pages
        for page in self.pages.values():
            if hasattr(page, 'update_language'):
                page.update_language(is_arabic)

        # Update navbar
        if hasattr(self.navbar, 'update_language'):
            self.navbar.update_language(is_arabic)

        # Update office survey wizard (not in self.pages)
        if hasattr(self, 'office_survey_wizard') and self.office_survey_wizard:
            if hasattr(self.office_survey_wizard, 'update_language'):
                self.office_survey_wizard.update_language(is_arabic)

        # Update window title
        title = Config.APP_TITLE_AR if is_arabic else Config.APP_TITLE
        self.setWindowTitle(f"{Config.APP_NAME} - {title}")

    def closeEvent(self, event):
        """Handle window close event."""
        if self.current_user:
            from ui.components.dialogs.logout_dialog import LogoutDialog
            if not LogoutDialog.confirm_exit(parent=self):
                event.ignore()
                return

        logger.info("Application closing")
        event.accept()
    
    def showEvent(self, event):
        super().showEvent(event)
        self._apply_round_mask()

        # Connect screen change signals (only once)
        if not hasattr(self, '_screen_signals_connected'):
            self._screen_signals_connected = True
            handle = self.windowHandle()
            if handle:
                handle.screenChanged.connect(self._on_window_screen_changed)
            current_screen = self.screen()
            if current_screen:
                current_screen.geometryChanged.connect(
                    self._on_screen_geometry_changed
                )
                current_screen.logicalDotsPerInchChanged.connect(
                    self._on_dpi_changed
                )

    def _on_screen_geometry_changed(self, _new_geo):
        """Screen resolution/size changed."""
        self._adapt_to_screen()

    def _on_dpi_changed(self, _new_dpi):
        """Windows DPI scale changed (125%, 150%, etc.)."""
        self._adapt_to_screen()

    def _on_window_screen_changed(self, new_screen):
        """Window moved to a different monitor."""
        old_screen = getattr(self, '_current_screen', None)
        if old_screen:
            try:
                old_screen.geometryChanged.disconnect(self._on_screen_geometry_changed)
                old_screen.logicalDotsPerInchChanged.disconnect(self._on_dpi_changed)
            except RuntimeError:
                pass
        if new_screen:
            new_screen.geometryChanged.connect(self._on_screen_geometry_changed)
            new_screen.logicalDotsPerInchChanged.connect(self._on_dpi_changed)
            self._current_screen = new_screen
            self._adapt_to_screen()

    def _adapt_to_screen(self):
        """Re-adapt window size and scaling after screen change."""
        screen = self.screen().availableGeometry()
        w = min(1512, int(screen.width() * 0.95))
        h = min(982, int(screen.height() * 0.95))
        ScreenScale.initialize_from_size(w, h)
        self.setMinimumSize(min(1024, w), min(680, h))
        x = screen.x() + (screen.width() - w) // 2
        y = screen.y() + (screen.height() - h) // 2
        self.setGeometry(x, y, w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    # حرّك مقبض تغيير الحجم
        if hasattr(self, "_size_grip") and self._size_grip:
            m = 6
            self._size_grip.move(
                self.window_frame.width() - self._size_grip.width() - m,
                self.window_frame.height() - self._size_grip.height() - m
        )

    # طبّق قصّ الزوايا بعد أي تغيير بالحجم
        if hasattr(self, "window_frame") and self.window_frame and not self.isMaximized():
            self._apply_round_mask()

    def changeEvent(self, event):
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            if hasattr(self, "window_frame") and self.window_frame:
                if self.isMaximized():
                    self.window_frame.setStyleSheet(f"""
                        QFrame#window_frame {{
                            background-color: {Config.BACKGROUND_COLOR};
                            border-radius: 0px;
                        }}
                    """)
                    self.window_frame.clearMask()
                else:
                    self.window_frame.setStyleSheet(f"""
                        QFrame#window_frame {{
                            background-color: {Config.BACKGROUND_COLOR};
                            border-radius: 12px;
                        }}
                    """)
                    self._apply_round_mask()
        super().changeEvent(event)

    def _apply_round_mask(self):
        from PyQt5.QtGui import QPainterPath
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QRegion

        r = getattr(self, "WINDOW_RADIUS", 18)
        path = QPainterPath()
        rect = QRectF(self.window_frame.rect())
        path.addRoundedRect(rect, r, r)

        self.window_frame.setMask(QRegion(path.toFillPolygon().toPolygon()))
    # Mouse Events - Window Dragging

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.LeftButton:
            # Store the position where user clicked
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for window dragging."""
        if event.buttons() == Qt.LeftButton:
            # Move window to new position
            self.move(event.globalPos() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release after dragging."""
        if event.button() == Qt.LeftButton:
            event.accept()


