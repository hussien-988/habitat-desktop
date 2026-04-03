# -*- coding: utf-8 -*-
"""Main application window with navbar navigation."""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QShortcut,
    QFrame, QGraphicsDropShadowEffect, QSizeGrip
)

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QEvent

from PyQt5.QtGui import QKeySequence, QColor, QMouseEvent

from .config import Config, Pages, save_language, get_saved_language
from repositories.database import Database
from services.translation_manager import tr, set_language as tm_set_language
from utils.i18n import I18n
from utils.logger import get_logger
from ui.error_handler import ErrorHandler

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with navbar navigation."""

    language_changed = pyqtSignal(bool)  # True for Arabic, False for English

    # Pages restricted to specific roles
    _PAGE_ROLE_ACCESS = {
        Pages.FIELD_ASSIGNMENT: {"admin", "data_manager", "field_supervisor"},
        Pages.SYNC_DATA: {"admin", "data_manager", "field_supervisor"},
        Pages.REPORTS: {"admin", "data_manager", "field_supervisor"},
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

        # Session timeout tracking
        self._session_timer = None
        self._last_activity = None
        self._session_timeout_ms = 0

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

        # Initialize screen scaling for all UI components
        from ui.design_system import ScreenScale
        ScreenScale.initialize(screen)

        # Window = 95% of available screen, capped at reference size
        window_width = min(1512, int(screen.width() * 0.95))
        window_height = min(982, int(screen.height() * 0.95))
        self.setMinimumSize(1024, 680)

        # Center on screen
        x = (screen.width() - window_width) // 2
        y = (screen.height() - window_height) // 2
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
        from ui.pages.dashboard_page import DashboardPage
        from ui.pages.buildings_page import BuildingsPage
        from ui.pages.building_details_page import BuildingDetailsPage
        from ui.pages.units_page import UnitsPage
        from ui.pages.unit_details_page import UnitDetailsPage
        from ui.pages.persons_page import PersonsPage
        from ui.pages.relations_page import RelationsPage
        from ui.pages.households_page import HouseholdsPage
        from ui.pages.completed_claims_page import CompletedClaimsPage
        from ui.pages.cases_page import CasesPage
        from ui.pages.search_page import SearchPage
        from ui.pages.reports_page import ReportsPage
        from ui.pages.map_page import MapPage
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

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.window_frame.setGraphicsEffect(shadow)

        # مقبض تغيير الحجم (resize) خليّه جوّا الإطار
        self._size_grip = QSizeGrip(self.window_frame)
        self._size_grip.setFixedSize(16, 16)
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

        # Dashboard page
        self.pages[Pages.DASHBOARD] = DashboardPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.DASHBOARD])

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
        self.pages[Pages.CASES] = CasesPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CASES])

        # Search page
        self.pages[Pages.SEARCH] = SearchPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.SEARCH])

        # Reports page
        self.pages[Pages.REPORTS] = ReportsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.REPORTS])

        # Map view page
        self.pages[Pages.MAP_VIEW] = MapPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.MAP_VIEW])

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
        self.pages[Pages.CASE_DETAILS] = CaseDetailsPage(self)
        self.stack.addWidget(self.pages[Pages.CASE_DETAILS])

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
        # Tab 1: الحالات (Cases)
        # Tab 2: الاستيراد (Import)
        # Tab 3: التكرارات (Duplicates)
        # Tab 4: إدارة المستخدمين (User Management)
        # Tab 5: تجهيز العمل الميداني (Field Work Preparation)
        self.tab_page_mapping = {
            0: Pages.CLAIMS,
            1: Pages.CASES,
            2: Pages.IMPORT_PACKAGES,
            3: Pages.DUPLICATES,
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
        inner.addWidget(self.stack, 1)


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
        self.pages[Pages.SYNC_DATA].sync_notification.connect(self._on_sync_notification)
        self.navbar.import_requested.connect(self._on_import_requested)

        # Import pages signals
        self.pages[Pages.IMPORT_PACKAGES].open_wizard.connect(
            lambda: self.navigate_to(Pages.IMPORT_WIZARD)
        )
        self.pages[Pages.IMPORT_PACKAGES].view_package.connect(
            lambda pkg_id: self.navigate_to(Pages.IMPORT_WIZARD)
        )
        self.pages[Pages.IMPORT_WIZARD].completed.connect(
            lambda _: self.navigate_to(Pages.IMPORT_PACKAGES)
        )
        self.pages[Pages.IMPORT_WIZARD].cancelled.connect(
            lambda: self.navigate_to(Pages.IMPORT_PACKAGES)
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
        self.pages[Pages.CASE_DETAILS].back_requested.connect(self._on_case_details_back)

        # Cases - view survey details (works for all 3 sub-tabs)
        self.pages[Pages.CASES].claim_selected.connect(self._on_draft_claim_selected)

        # Cases - resume draft survey in wizard for editing
        self.pages[Pages.CASES].resume_survey.connect(self._on_resume_draft_survey)

        # Cases - finalize survey → stay on cases page (switch to finalized sub-tab)
        self.pages[Pages.CASES].survey_finalized.connect(
            lambda _: self.navigate_to(Pages.CASES)
        )

        # Completed Claims - view claim details
        self.pages[Pages.CLAIMS].claim_selected.connect(self._on_completed_claim_selected)

        # Add Claim button - start new office survey
        self.pages[Pages.CASES].add_claim_clicked.connect(self._start_new_office_survey)

        # Office Survey Wizard signals
        self.office_survey_wizard.survey_completed.connect(self._on_survey_completed)
        self.office_survey_wizard.survey_cancelled.connect(self._on_survey_cancelled)
        self.office_survey_wizard.survey_saved_draft.connect(self._on_survey_saved_draft)

        # Resume draft survey from CaseDetailsPage
        self.pages[Pages.CASE_DETAILS].resume_requested.connect(
            self._on_resume_draft_survey
        )

        # Cancel draft survey from CaseDetailsPage
        self.pages[Pages.CASE_DETAILS].cancel_requested.connect(
            self._on_cancel_draft_survey
        )

        # Claim Details page signals
        self.pages[Pages.CLAIM_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.CLAIMS)
        )
        self.pages[Pages.CLAIM_DETAILS].edit_requested.connect(
            self._on_edit_claim_requested
        )

        # Claim Edit - back to case details / save completed
        self.pages[Pages.CLAIM_EDIT].back_requested.connect(
            lambda: self.navigate_to(Pages.CASES)
        )
        self.pages[Pages.CLAIM_EDIT].save_completed.connect(
            lambda: self.navigate_to(Pages.CASES)
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
            if not self._handle_forced_password_change(user):
                self._show_login()
                return

        # Pass API token to BuildingController if using API backend
        token = getattr(user, '_api_token', None)
        logger.info(f"User API token available: {bool(token)}")
        if token:
            self._set_api_token_for_controllers(token)
        else:
            logger.warning("No API token found in user object - API calls may fail with 401")

        # Show loading overlay while preparing data
        self._show_login_loading()

        try:
            # Refresh vocabularies now that we have a valid API token/port
            try:
                from services.vocab_service import refresh_vocabularies
                refresh_vocabularies()
                logger.info("Vocabularies refreshed after login")
            except Exception as e:
                logger.warning(f"Failed to refresh vocabularies after login: {e}")

            # Freeze repainting to prevent login-to-main transition flicker
            self.setUpdatesEnabled(False)
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

                # Set user context on CasesPage BEFORE configure_for_role,
                # because configure_for_role emits tab_changed which triggers refresh()
                cases_page = self.pages.get(Pages.CASES)
                if cases_page and hasattr(cases_page, 'configure_for_user'):
                    cases_page.configure_for_user(user.role, str(user.user_id))

                # Configure tabs based on user role (RBAC)
                self.navbar.configure_for_role(user.role)

                # Apply role-based button visibility to content pages
                for page_id in (Pages.BUILDINGS, Pages.UNITS, Pages.PERSONS,
                                Pages.IMPORT_WIZARD, Pages.IMPORT_PACKAGES):
                    page = self.pages.get(page_id)
                    if page and hasattr(page, 'configure_for_role'):
                        page.configure_for_role(user.role)

                # Load field assignment filter data (requires valid API token)
                if Pages.FIELD_ASSIGNMENT in self.pages:
                    field_page = self.pages[Pages.FIELD_ASSIGNMENT]
                    if hasattr(field_page, 'load_data'):
                        field_page.load_data()
            finally:
                # Always resume repainting
                self.setUpdatesEnabled(True)
        finally:
            # Always hide loading overlay
            self._hide_login_loading()

        # Start session timeout timer
        self._start_session_timer()

    def _handle_forced_password_change(self, user) -> bool:
        """Show password change dialog when backend requires it.

        Returns True if password was changed successfully, False otherwise.
        """
        from ui.components.dialogs.password_dialog import PasswordDialog
        from services.api_client import get_api_client
        from services.api_auth_service import ApiAuthService
        from ui.components.toast import Toast

        result = PasswordDialog.change_password(parent=self)
        if result is None:
            Toast.show(self, tr("dialog.password.change_cancelled"), Toast.WARNING)
            return False

        current_password, new_password = result

        try:
            api_client = get_api_client()
            token = getattr(user, '_api_token', None)
            if token:
                api_client.set_access_token(token)
            api_client.change_password(current_password, new_password)
            logger.info("Password changed successfully for user: %s", user.username)
        except Exception as e:
            logger.error("Password change failed: %s", e)
            Toast.show(self, tr("page.user_mgmt.password_change_failed"), Toast.ERROR)
            return False

        # Re-authenticate with new password to get unrestricted token
        try:
            auth_service = ApiAuthService()
            new_user, error = auth_service.authenticate(user.username, new_password)
            if new_user:
                self.current_user = new_user
                token = getattr(new_user, '_api_token', None)
                if token:
                    self._set_api_token_for_controllers(token)
                Toast.show(self, tr("page.user_mgmt.password_changed_success"), Toast.SUCCESS)
                return True
            else:
                logger.error("Re-authentication after password change failed: %s", error)
                Toast.show(self, tr("page.user_mgmt.password_change_failed"), Toast.ERROR)
                return False
        except Exception as e:
            logger.error("Re-authentication failed: %s", e)
            Toast.show(self, tr("page.user_mgmt.password_change_failed"), Toast.ERROR)
            return False

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
        try:
            from services.security_service import SecurityService
            svc = SecurityService(self.db)
            settings = svc.get_settings()
            timeout_minutes = settings.session_timeout_minutes
        except Exception as e:
            logger.warning(f"Could not load session timeout setting: {e}")
            timeout_minutes = 30

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
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
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
            self.current_user = None
            self._stop_session_timer()
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
        self.current_user = None
        self._stop_session_timer()
        self._show_login()

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
                self.current_user = None
                self._stop_session_timer()
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
            revisit_buildings = workflow_data.get('revisit_buildings', [])
            researcher_name = researcher.get('name', 'N/A')
            researcher_id = researcher.get('id', '')
            building_count = len(buildings)

            if not buildings or not researcher_id:
                logger.error("Missing buildings or researcher ID for assignment")
                Toast.show_toast(self, "بيانات غير مكتملة للتعيين", Toast.ERROR)
                return

            # Build buildings payload
            revisit_map = {r['building_id']: r for r in revisit_buildings}
            buildings_payload = []
            for b in buildings:
                b_uuid = getattr(b, 'building_uuid', None) or (
                    b.get('building_uuid') if isinstance(b, dict) else None
                )
                b_id = getattr(b, 'building_id', None) or (
                    b.get('building_id') if isinstance(b, dict) else None
                )
                item = {"buildingId": b_uuid}
                revisit_info = revisit_map.get(b_id)
                if revisit_info:
                    item["revisitReason"] = revisit_info.get('reason', '')
                buildings_payload.append(item)

            # Build assignment notes
            assignment_notes = None
            if revisit_buildings:
                info_parts = [
                    f"{r['building_id']}: {r.get('reason', '')}" for r in revisit_buildings
                ]
                assignment_notes = "مباني تحتاج إعادة زيارة: " + " | ".join(info_parts)

            logger.info(f"Creating API assignment: {building_count} buildings -> {researcher_name} ({researcher_id})")

            try:
                api = get_api_client()
                api_response = api.create_assignment(
                    buildings=buildings_payload,
                    field_collector_id=researcher_id,
                    assignment_notes=assignment_notes
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

    def _on_import_navigate_to_duplicates(self):
        """Navigate from import wizard to duplicates page with return banner."""
        dup_page = self.pages.get(Pages.DUPLICATES)
        if dup_page:
            dup_page.set_return_to_import(True)
            dup_page.refresh()
            self.navbar.set_current_tab(3)
            self.stack.setCurrentWidget(dup_page)

    def _on_duplicates_return_to_import(self):
        """Return from duplicates page to import wizard without resetting."""
        dup_page = self.pages.get(Pages.DUPLICATES)
        if dup_page:
            dup_page.set_return_to_import(False)
        import_page = self.pages.get(Pages.IMPORT_WIZARD)
        if import_page:
            self.navbar.set_current_tab(2)
            self.stack.setCurrentWidget(import_page)
            import_page.refresh_from_duplicates()

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
        if current_page == self.pages.get(Pages.CASES):
            search_mode = getattr(self.navbar, 'search_mode', 'name')
            current_page.search_claims(search_text, search_mode)
            return
        # Otherwise navigate to search page
        self.navigate_to(Pages.SEARCH, search_text)

    def _on_filter_applied(self, filters: dict):
        """Handle filter applied from navbar filter popup."""
        current_page = self.stack.currentWidget()
        if current_page == self.pages.get(Pages.CASES):
            current_page.apply_filters(filters)

    def navigate_to(self, page_id: str, data=None):
        """Navigate to a specific page."""
        # Check if currently in wizard with unsaved data
        current_widget = self.stack.currentWidget()
        if current_widget == self.office_survey_wizard and page_id != "office_survey_wizard":
            if self._has_unsaved_wizard_data():
                from ui.components.dialogs.confirmation_dialog import ConfirmationDialog

                # Show save draft confirmation
                result = ConfirmationDialog.save_draft_confirmation(
                    parent=self,
                    title="هل تريد الحفظ؟",
                    message="لديك تغييرات غير محفوظة.\nهل تريد حفظها كمسودة؟"
                )

                if result == ConfirmationDialog.SAVE:
                    # Save as draft
                    draft_id = self.office_survey_wizard.on_save_draft()
                    if draft_id:
                        from ui.components.toast import Toast
                        Toast.show_toast(self, "✅ تم حفظ المسودة بنجاح!", Toast.SUCCESS)
                        # Refresh drafts page
                        if Pages.CASES in self.pages:
                            self.pages[Pages.CASES].refresh()
                    else:
                        # Save failed - stay in wizard
                        logger.warning("Failed to save draft")
                        return

                elif result == ConfirmationDialog.DISCARD:
                    # Cancel survey on server with reason
                    survey_id = self.office_survey_wizard.context.get_data("survey_id")
                    if survey_id:
                        from PyQt5.QtWidgets import QInputDialog
                        reason, ok = QInputDialog.getMultiLineText(
                            self, "سبب الإلغاء",
                            "يرجى إدخال سبب إلغاء المسح:", ""
                        )
                        if not ok or not reason.strip():
                            return
                        try:
                            from services.api_client import get_api_client
                            api = get_api_client()
                            if self._api_token:
                                api.set_access_token(self._api_token)
                            api.cancel_survey(survey_id, reason.strip())
                            logger.info(f"Survey {survey_id} cancelled: {reason.strip()}")
                        except Exception as e:
                            logger.warning(f"Failed to cancel survey {survey_id}: {e}")
                    logger.info("User discarded wizard changes")

                else:
                    # User cancelled - stay in wizard
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
                self.stack.setCurrentWidget(self.office_survey_wizard)
                return
            logger.error(f"Page not found: {page_id}")
            return

        page = self.pages[page_id]

        # Clear sync notification badge when navigating to sync page
        if page_id == Pages.SYNC_DATA:
            self.navbar.hide_sync_notification()
            if hasattr(page, 'clear_notifications'):
                page.clear_notifications()

        # Sync navbar tab when navigating to import pages
        if page_id in (Pages.IMPORT_PACKAGES, Pages.IMPORT_WIZARD):
            self.navbar.set_current_tab(2)

        # Refresh page data if method exists
        if hasattr(page, 'refresh'):
            page.refresh(data)

        # Show page
        self.stack.setCurrentWidget(page)
        logger.debug(f"Navigated to: {page_id}")

    def _has_unsaved_wizard_data(self) -> bool:
        """Check if wizard has unsaved data."""
        # If finalization was completed, no need to show save dialog
        if hasattr(self.office_survey_wizard, '_finalization_complete') and self.office_survey_wizard._finalization_complete:
            return False

        # Check if beyond step 1 (step 2+)
        if self.office_survey_wizard.navigator.current_index >= 1:
            return True

        # Check if building selected in step 1
        if hasattr(self.office_survey_wizard.context, 'building') and self.office_survey_wizard.context.building:
            return True

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

        # Find survey data from CasesPage list
        claims_page = self.pages[Pages.CASES]
        claim_data = None
        for c in claims_page._all_data:
            if c.get('claim_id') == claim_id:
                claim_data = c
                break

        if not claim_data:
            logger.warning(f"Survey data not found for: {claim_id}")
            return

        survey_uuid = claim_data.get('claim_uuid')
        if survey_uuid:
            try:
                from controllers.survey_controller import SurveyController
                ctrl = SurveyController(self.db)
                result = ctrl.get_survey_full_context(survey_uuid)
                if result.success and result.data:
                    self.navigate_to(Pages.CASE_DETAILS, result.data)
                    return
                from ui.components.toast import Toast
                Toast.show_toast(self, result.message or "فشل تحميل بيانات المسح", Toast.ERROR)
            except Exception as e:
                logger.warning(f"Survey context fetch failed: {e}")

        logger.warning(f"Could not load survey details for: {claim_id}")

    def _on_resume_draft_survey(self, survey_uuid: str):
        """Load draft survey into wizard for editing and resumption."""
        if not survey_uuid:
            return
        try:
            from controllers.survey_controller import SurveyController
            result = SurveyController(self.db).get_survey_full_context(survey_uuid)
            if not result.success or not result.data:
                logger.warning(f"Could not load draft context for: {survey_uuid}")
                from ui.components.toast import Toast
                Toast.show_toast(self, result.message or "فشل تحميل المسودة", Toast.ERROR)
                return

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

    def _on_case_details_back(self):
        """Navigate back to the Cases page from CaseDetailsPage."""
        self.navigate_to(Pages.CASES)

    def _on_edit_claim_requested(self, claim_id: str):
        """Navigate to ClaimEditPage, passing claim_id + survey_id from current context."""
        case_page = self.pages.get(Pages.CASE_DETAILS)
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
        from ui.components.building_map_dialog_v2 import BuildingMapDialog

        logger.info("Starting new office survey — opening building map dialog")

        auth_token = getattr(self, '_api_token', None)
        dialog = BuildingMapDialog(
            db=self.db,
            auth_token=auth_token,
            read_only=False,
            parent=self
        )
        if dialog.exec_() != QDialog.Accepted:
            logger.debug("Building selection cancelled")
            return

        selected_building = dialog.get_selected_building()
        if not selected_building:
            logger.warning("Map dialog accepted but no building selected")
            return

        logger.info(f"Building selected: {selected_building.building_id}")

        # Reset wizard with building pre-set so populate_data() runs correctly on Step 0
        self._reset_wizard(building=selected_building)
        self.stack.setCurrentWidget(self.office_survey_wizard)

    def _on_survey_completed(self, data):
        """Handle survey completion from wizard."""
        from ui.components.toast import Toast
        logger.info(f"Survey completed: {data}")

        Toast.show_toast(
            self,
            "✅ تم إنهاء المسح بنجاح!",
            Toast.SUCCESS
        )

        # Navigate to the appropriate tab based on finalization and role access
        is_finalized = (
            isinstance(data, dict) and data.get('status') == 'finalized'
        )

        from ui.components.navbar import Navbar
        user_role = getattr(self.current_user, 'role', '') if self.current_user else ''
        allowed_tabs = Navbar.TAB_PERMISSIONS.get(user_role, [0, 1])

        if is_finalized and 0 in allowed_tabs:
            if hasattr(self.pages.get(Pages.CLAIMS), 'refresh'):
                self.pages[Pages.CLAIMS].refresh()
            self.navbar.set_current_tab(0)
            self._on_tab_changed(0)
        else:
            self.pages[Pages.CASES].refresh()
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
            self.navigate_to(Pages.CASES)
            if Pages.CASES in self.pages and hasattr(self.pages[Pages.CASES], 'refresh'):
                self.pages[Pages.CASES].refresh()
        except Exception as e:
            logger.error(f"Failed to cancel survey {survey_id}: {e}", exc_info=True)
            Toast.show_toast(self, f"فشل إلغاء المسح: {e}", Toast.ERROR)

    def _on_survey_saved_draft(self, survey_id: str):
        """Handle survey saved as draft."""
        logger.info(f"Survey saved as draft: {survey_id}")
        if hasattr(self.pages.get(Pages.CASES), 'refresh'):
            self.pages[Pages.CASES].refresh()
        self.navigate_to(Pages.CASES)

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

        if self._is_arabic:
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

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
        if hasattr(self, "window_frame") and self.window_frame:
            self._apply_round_mask()

    def _apply_round_mask(self):
        from PyQt5.QtGui import QPainterPath
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QRegion

        r = getattr(self, "WINDOW_RADIUS", 18)  # نفس رقم الراديوس اللي مستخدمه
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


