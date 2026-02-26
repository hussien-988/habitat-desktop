# -*- coding: utf-8 -*-
"""
Main application window with navbar navigation (NEW DESIGN)
Based on Figma design pages 1-31
Replaces sidebar with top navbar and tabs
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QShortcut,
    QFrame, QGraphicsDropShadowEffect, QSizeGrip
)

from PyQt5.QtCore import Qt, pyqtSignal, QPoint

from PyQt5.QtGui import QKeySequence, QColor, QMouseEvent

from .config import Config, Pages
from repositories.database import Database
from services.translation_manager import set_language as tm_set_language
from utils.i18n import I18n
from utils.logger import get_logger
from ui.error_handler import ErrorHandler

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with navbar navigation (NEW DESIGN)."""

    language_changed = pyqtSignal(bool)  # True for Arabic, False for English

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.WINDOW_RADIUS = 12
        self.db = db
        self.i18n = i18n
        self.current_user = None
        self._is_arabic = True  # افتراضياً عربي

        # For window dragging
        self._drag_position = QPoint()

        self._setup_window()
        self._setup_shortcuts()
        self._create_widgets()
        self._setup_layout()
        self._connect_signals()

        # تعيين اتجاه الواجهة للعربية
        self.setLayoutDirection(Qt.RightToLeft)
        self.i18n.set_language("ar")

        # Start with login page
        self._show_login()

    def _setup_window(self):
        """Configure window properties."""
        # Set window title to match Figma design
        self.setWindowTitle("UN-HABITAT")

        # Set exact dimensions from Figma: 1512 x 982
        window_width = 1512
        window_height = 982
        self.setMinimumSize(window_width, window_height)

        # Center on screen
        screen = self.screen().geometry()
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
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Language toggle: Ctrl+L
        self.lang_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self.lang_shortcut.activated.connect(self.toggle_language)

        # Logout: Ctrl+Q
        self.logout_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.logout_shortcut.activated.connect(self._handle_logout)

        # Developer reset tool: Ctrl+Shift+R (DEV_MODE only)
        if Config.DEV_MODE:
            self.dev_reset_shortcut = QShortcut(QKeySequence("Ctrl+Shift+R"), self)
            self.dev_reset_shortcut.activated.connect(self._open_dev_reset_dialog)

    def _open_dev_reset_dialog(self):
        """Open developer data reset dialog (DEV_MODE only)."""
        from ui.components.dialogs.dev_reset_dialog import DevResetDialog
        dialog = DevResetDialog(self, db=self.db)
        dialog.exec_()

    def _create_widgets(self):
        """Create main UI components with new design."""
        # Import here to avoid circular imports
        from ui.components.navbar import Navbar
        from ui.pages.login_page import LoginPage
        from ui.pages.splash_page import SplashPage
        from ui.pages.dashboard_page import DashboardPage
        from ui.pages.buildings_page import BuildingsPage
        from ui.pages.building_details_page import BuildingDetailsPage
        from ui.pages.units_page import UnitsPage
        from ui.pages.unit_details_page import UnitDetailsPage
        from ui.pages.persons_page import PersonsPage
        from ui.pages.relations_page import RelationsPage
        from ui.pages.households_page import HouseholdsPage
        from ui.pages.completed_claims_page import CompletedClaimsPage
        from ui.pages.draft_claims_page import DraftClaimsPage
        from ui.pages.search_page import SearchPage
        from ui.pages.reports_page import ReportsPage
        from ui.pages.admin_page import AdminPage
        from ui.pages.map_page import MapPage
        from ui.pages.duplicates_page import DuplicatesPage
        from ui.pages.claim_comparison_page import ClaimComparisonPage
        from ui.pages.field_work_preparation_page import FieldWorkPreparationPage
        from controllers.building_controller import BuildingController
        from ui.pages.case_details_page import CaseDetailsPage
        from ui.pages.user_management_page import UserManagementPage
        from ui.pages.add_user_page import AddUserPage
        from controllers.user_controller import UserController
        from ui.wizards.office_survey import OfficeSurveyWizard

        self._user_controller = UserController(parent=self)


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

        # Splash page (mode chooser)
        self.splash_page = SplashPage(self)
        self.stack.addWidget(self.splash_page)

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

        # Units page (UC-002)
        self.pages[Pages.UNITS] = UnitsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.UNITS])

        # Unit details page
        self.pages[Pages.UNIT_DETAILS] = UnitDetailsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.UNIT_DETAILS])

        # Persons page (UC-003)
        self.pages[Pages.PERSONS] = PersonsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.PERSONS])

        # Relations page (Person-Unit Relations)
        self.pages[Pages.RELATIONS] = RelationsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.RELATIONS])

        # Households page (FSD 6.1.6)
        self.pages[Pages.HOUSEHOLDS] = HouseholdsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.HOUSEHOLDS])

        # Completed Claims page (UC-007, UC-008)
        self.pages[Pages.CLAIMS] = CompletedClaimsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CLAIMS])

        # Draft Claims page
        self.pages[Pages.DRAFT_CLAIMS] = DraftClaimsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.DRAFT_CLAIMS])

        # Search page (UC-011)
        self.pages[Pages.SEARCH] = SearchPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.SEARCH])

        # Reports page (UC-012, UC-013)
        self.pages[Pages.REPORTS] = ReportsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.REPORTS])

        # Admin page (UC-015)
        self.pages[Pages.ADMIN] = AdminPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.ADMIN])

        # Map view page (UC-014)
        self.pages[Pages.MAP_VIEW] = MapPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.MAP_VIEW])

        # Duplicates page (UC-007, UC-008)
        self.pages[Pages.DUPLICATES] = DuplicatesPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.DUPLICATES])

        # Claim Comparison page (UC-007)
        self.pages[Pages.CLAIM_COMPARISON] = ClaimComparisonPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CLAIM_COMPARISON])

        # Field Work Preparation wizard (UC-012)
        field_bc = BuildingController(self.db)
        self.pages[Pages.FIELD_ASSIGNMENT] = FieldWorkPreparationPage(field_bc, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.FIELD_ASSIGNMENT])
        self.pages[Pages.FIELD_ASSIGNMENT].completed.connect(self._on_field_work_completed)

        # Case Details page — read-only view of survey/claim
        self.pages[Pages.CASE_DETAILS] = CaseDetailsPage(self)
        self.stack.addWidget(self.pages[Pages.CASE_DETAILS])

        # User Management page
        self.pages[Pages.USER_MANAGEMENT] = UserManagementPage(
            self.db, self.i18n, user_controller=self._user_controller, parent=self
        )
        self.stack.addWidget(self.pages[Pages.USER_MANAGEMENT])

        # Add User page
        self.pages[Pages.ADD_USER] = AddUserPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.ADD_USER])

        # Sync & Data page
        from ui.pages.sync_data_page import SyncDataPage
        self.pages[Pages.SYNC_DATA] = SyncDataPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.SYNC_DATA])

        # Data Management page
        from ui.pages.data_management_page import DataManagementPage
        self.pages[Pages.DATA_MANAGEMENT] = DataManagementPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.DATA_MANAGEMENT])

        # Office Survey Wizard (UC-004, UC-005) - NEW wizard framework
        self.office_survey_wizard = OfficeSurveyWizard(self.db, self)
        self.stack.addWidget(self.office_survey_wizard)

        # Map tabs to pages (based on Figma design)
        # Tab 0: المطالبات المكتملة (Completed Claims)
        # Tab 1: المسودة (Draft Claims)
        # Tab 2: المبانى (Buildings)
        # Tab 3: الوحدات السكنية (Units)
        # Tab 4: التكرارات (Duplicates)
        self.tab_page_mapping = {
            0: Pages.CLAIMS,
            1: Pages.DRAFT_CLAIMS,
            2: Pages.BUILDINGS,
            3: Pages.UNITS,
            4: Pages.DUPLICATES,
            5: Pages.USER_MANAGEMENT,
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
        # Splash page signal
        self.splash_page.mode_selected.connect(self._on_data_mode_selected)

        # Login page signals
        self.pages[Pages.LOGIN].login_successful.connect(self._on_login_success)

        # Navbar signals
        self.navbar.tab_changed.connect(self._on_tab_changed)
        self.navbar.search_requested.connect(self._on_search_requested)
        self.navbar.filter_applied.connect(self._on_filter_applied)
        self.navbar.logout_requested.connect(self._handle_logout)  # ✅ Connect logout
        self.navbar.language_change_requested.connect(self.toggle_language)  # ✅ Connect language toggle
        self.navbar.sync_requested.connect(self._on_sync_requested)
        self.navbar.password_change_requested.connect(self._on_password_change_requested)
        self.navbar.security_settings_requested.connect(self._on_security_settings_requested)
        self.navbar.data_management_requested.connect(self._on_data_management_requested)

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

        # Case Details - back to drafts
        self.pages[Pages.CASE_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.DRAFT_CLAIMS)
        )

        # Draft Claims - view/edit draft claim
        self.pages[Pages.DRAFT_CLAIMS].claim_selected.connect(self._on_draft_claim_selected)

        # Completed Claims - view claim details
        self.pages[Pages.CLAIMS].claim_selected.connect(self._on_completed_claim_selected)

        # Add Claim buttons - start new office survey (UC-004 S01)
        self.pages[Pages.DRAFT_CLAIMS].add_claim_clicked.connect(self._start_new_office_survey)
        self.pages[Pages.CLAIMS].add_claim_clicked.connect(self._start_new_office_survey)

        # Office Survey Wizard signals
        self.office_survey_wizard.survey_completed.connect(self._on_survey_completed)
        self.office_survey_wizard.survey_cancelled.connect(self._on_survey_cancelled)
        self.office_survey_wizard.survey_saved_draft.connect(self._on_survey_saved_draft)

        # Duplicates page - view comparison
        self.pages[Pages.DUPLICATES].view_comparison_requested.connect(
            lambda group: self.navigate_to(Pages.CLAIM_COMPARISON, group)
        )

        # Claim Comparison - back to duplicates
        self.pages[Pages.CLAIM_COMPARISON].back_requested.connect(
            lambda: self.navigate_to(Pages.DUPLICATES)
        )

        # User Management - add new user
        self.pages[Pages.USER_MANAGEMENT].add_user_requested.connect(
            lambda: self.navigate_to(Pages.ADD_USER)
        )

        # Add User - back to user management
        self.pages[Pages.ADD_USER].back_requested.connect(
            lambda: self.navigate_to(Pages.USER_MANAGEMENT)
        )

        # User Management - view user details
        self.pages[Pages.USER_MANAGEMENT].view_user.connect(
            lambda user: self._navigate_to_user(user, 'view')
        )

        # User Management - edit user
        self.pages[Pages.USER_MANAGEMENT].edit_user_signal.connect(
            lambda user: self._navigate_to_user(user, 'edit')
        )

        # Add User - save new user to database
        self.pages[Pages.ADD_USER].save_requested.connect(self._on_save_new_user)

        # Language change signal
        self.language_changed.connect(self._on_language_changed)

    def _show_login(self):
        """Show login or splash page depending on DATA_MODE."""
        self.navbar.setVisible(False)
        if Config.DATA_MODE:
            self.pages[Pages.LOGIN].set_data_mode(Config.DATA_MODE, self.db)
            self.stack.setCurrentWidget(self.pages[Pages.LOGIN])
            logger.info("Showing login page (mode pre-set)")
        else:
            self.stack.setCurrentWidget(self.splash_page)
            logger.info("Showing splash/mode chooser")

    def _on_data_mode_selected(self, mode: str):
        """Handle data mode selection from splash page."""
        Config.DATA_MODE = "api"
        logger.info("Data mode: API (Docker backend)")

        self.pages[Pages.LOGIN].set_data_mode("api", self.db)
        self.stack.setCurrentWidget(self.pages[Pages.LOGIN])

    def _on_login_success(self, user):
        """Handle successful login."""
        self.current_user = user
        logger.info(f"User logged in: {user.username} ({user.role})")

        # Pass API token to BuildingController if using API backend
        token = getattr(user, '_api_token', None)
        logger.info(f"User API token available: {bool(token)}")
        if token:
            self._set_api_token_for_controllers(token)
        else:
            logger.warning("No API token found in user object - API calls may fail with 401")

        # Show navbar
        self.navbar.setVisible(True)

        # Update navbar with user info
        self.navbar.set_user_id(str(user.user_id))

        # Configure tabs based on user role (RBAC)
        self.navbar.configure_for_role(user.role)

    def _set_api_token_for_controllers(self, token: str):
        """Pass API token to all controllers that use API backend."""
        logger.info(f"Setting API token for controllers (token length: {len(token)})")

        # Store token for later use (e.g., when wizard is reset)
        self._api_token = token

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
                self._show_login()

    def _navigate_to_user(self, user_data: dict, mode: str):
        """Navigate to AddUserPage in view or edit mode."""
        user_data['_mode'] = mode
        self.navigate_to(Pages.ADD_USER, user_data)

    def _on_save_new_user(self, data: dict):
        """Handle saving a new or updated user from AddUserPage via backend API."""
        from ui.components.toast import Toast

        if not hasattr(self, '_user_controller') or not self._user_controller:
            Toast.show_toast(self, "خطأ: UserController غير مهيأ", Toast.ERROR)
            return

        is_edit = data.get("_mode") == "edit"
        permissions = data.get("permissions", {})

        if is_edit:
            user_id = data.get("_editing_user_id", "")
            api_data = {
                "role": data.get("role", ""),
                "permissions": permissions,
            }
            result = self._user_controller.update_user(user_id, api_data)
            success_msg = "تم تحديث المستخدم بنجاح"
            fail_prefix = "فشل تحديث المستخدم"
        else:
            api_data = {
                "username": data.get("user_id", ""),
                "password": data.get("password", ""),
                "role": data.get("role", "analyst"),
                "permissions": permissions,
            }
            result = self._user_controller.create_user(api_data)
            success_msg = "تم حفظ المستخدم بنجاح"
            fail_prefix = "فشل حفظ المستخدم"

        if result.success:
            logger.info(f"User {'updated' if is_edit else 'created'}: {data.get('user_id')}")
            Toast.show_toast(self, success_msg, Toast.SUCCESS)
            self.navigate_to(Pages.USER_MANAGEMENT)
            if Pages.USER_MANAGEMENT in self.pages:
                self.pages[Pages.USER_MANAGEMENT].refresh()
        else:
            logger.error(f"Save user failed: {result.message}")
            Toast.show_toast(self, f"{fail_prefix}: {result.message}", Toast.ERROR)

    def _on_field_work_completed(self, workflow_data):
        """Handle field work wizard completion - save assignment and navigate to sync page."""
        try:
            logger.info(f"_on_field_work_completed received: {type(workflow_data)}")
            buildings = workflow_data.get('buildings', [])
            researcher = workflow_data.get('researcher', {})
            researcher_name = researcher.get('name', 'N/A')
            building_count = len(buildings)
            logger.info(f"Field work assigned: {building_count} buildings to {researcher_name}")

            # Save assignment to sync_log for tracking
            from datetime import datetime
            sync_date = datetime.now().strftime("%Y-%m-%d %H:%M")

            self.db.execute(
                """INSERT INTO sync_log (device_id, action, details, sync_date, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    researcher_name,
                    f"تمت مزامنة {building_count} مبنى من قبل {researcher_name}",
                    "",
                    sync_date,
                    "success"
                )
            )
            logger.info("Saved to sync_log successfully")

            # Show success toast
            from ui.components.toast import Toast
            Toast.show_toast(
                self,
                f"تم إسناد {building_count} مبنى إلى {researcher_name}",
                Toast.SUCCESS
            )

            # Navigate to sync page so user can verify
            self.navigate_to(Pages.SYNC_DATA)
        except Exception as e:
            logger.error(f"Error in _on_field_work_completed: {e}", exc_info=True)

    def _on_sync_requested(self):
        """Handle sync data request from navbar menu."""
        self.navigate_to(Pages.SYNC_DATA)

    def _on_password_change_requested(self):
        """Handle password change request from navbar menu (admin only)."""
        from ui.components.dialogs.password_dialog import PasswordDialog
        from ui.components.toast import Toast
        from services.api_client import get_api_client
        result = PasswordDialog.change_password(parent=self)
        if not result:
            return
        current_pwd, new_pwd = result
        try:
            get_api_client().change_password(current_pwd, new_pwd)
            Toast.show_toast(self, "تم تغيير كلمة المرور بنجاح", Toast.SUCCESS)
            logger.info("Password changed successfully via API")
        except Exception as e:
            logger.error(f"Password change failed: {e}")
            from ui.components.error_handler import ErrorHandler
            ErrorHandler.show_error(self, str(e))

    def _on_security_settings_requested(self):
        """Handle security settings request from navbar menu."""
        from ui.components.dialogs.security_dialog import SecurityDialog
        result = SecurityDialog.show_settings(parent=self)
        if result:
            session_days, max_attempts = result
            logger.info(f"Security settings updated: session={session_days}d, attempts={max_attempts}")

    def _on_data_management_requested(self):
        """Handle data management request from navbar menu."""
        self.navigate_to(Pages.DATA_MANAGEMENT)

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
        if current_page == self.pages.get(Pages.DRAFT_CLAIMS):
            search_mode = getattr(self.navbar, 'search_mode', 'name')
            current_page.search_claims(search_text, search_mode)
            return
        # Otherwise navigate to search page
        self.navigate_to(Pages.SEARCH, search_text)

    def _on_filter_applied(self, filters: dict):
        """Handle filter applied from navbar filter popup."""
        current_page = self.stack.currentWidget()
        if current_page == self.pages.get(Pages.DRAFT_CLAIMS):
            current_page.apply_filters(filters)

    def navigate_to(self, page_id: str, data=None):
        """
        Navigate to a specific page.

        Best Practice: Prevents data loss by showing save confirmation dialog
        when leaving wizard with unsaved data.
        """
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
                        if Pages.DRAFT_CLAIMS in self.pages:
                            self.pages[Pages.DRAFT_CLAIMS].refresh()
                    else:
                        # Save failed - stay in wizard
                        logger.warning("Failed to save draft")
                        return

                elif result == ConfirmationDialog.DISCARD:
                    # User chose to discard - continue navigation
                    logger.info("User discarded wizard changes")

                else:
                    # User cancelled - stay in wizard
                    logger.debug("User cancelled navigation")
                    return

            # Reset wizard for next time (after finalization or unsaved data handling)
            self._reset_wizard()

        # Check if leaving Add User page with unsaved changes
        if current_widget == self.pages.get(Pages.ADD_USER) and page_id != Pages.ADD_USER:
            add_user_page = self.pages[Pages.ADD_USER]
            if hasattr(add_user_page, 'has_unsaved_changes') and add_user_page.has_unsaved_changes():
                from ui.components.dialogs.confirmation_dialog import ConfirmationDialog, DialogResult
                result = ConfirmationDialog.confirm(
                    parent=self,
                    title="تغييرات غير محفوظة",
                    message="لديك تغييرات غير محفوظة.\nهل تريد المغادرة بدون حفظ؟"
                )
                if result != DialogResult.YES:
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

        # Refresh page data if method exists
        if hasattr(page, 'refresh'):
            page.refresh(data)

        # Show page
        self.stack.setCurrentWidget(page)
        logger.debug(f"Navigated to: {page_id}")

    def _has_unsaved_wizard_data(self) -> bool:
        """
        Check if wizard has unsaved data.

        Best Practice: Only warn if user has progressed beyond first step
        or selected a building.
        """
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

    def _reset_wizard(self):
        """Reset wizard to clean state (Best Practice: DRY)."""
        new_context = self.office_survey_wizard.create_context()
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

        # Find survey data from DraftClaimsPage list
        claims_page = self.pages[Pages.DRAFT_CLAIMS]
        claim_data = None
        for c in claims_page.claims_data:
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
            except Exception as e:
                logger.warning(f"Survey context fetch failed: {e}")

        logger.warning(f"Could not load survey details for: {claim_id}")

    def _on_completed_claim_selected(self, claim_id: str):
        """Navigate to case details for a completed claim."""
        logger.info(f"Completed claim selected: {claim_id}")

        claims_page = self.pages[Pages.CLAIMS]
        claim_data = None
        for c in claims_page.claims_data:
            if c.get('claim_id') == claim_id:
                claim_data = c
                break

        if not claim_data:
            logger.warning(f"Claim data not found for: {claim_id}")
            return

        # Try loading via survey_uuid (if available from survey-based claims)
        survey_uuid = claim_data.get('claim_uuid') or claim_data.get('survey_id')
        if survey_uuid:
            try:
                from controllers.survey_controller import SurveyController
                ctrl = SurveyController(self.db)
                result = ctrl.get_survey_full_context(survey_uuid)
                if result.success and result.data:
                    self.navigate_to(Pages.CASE_DETAILS, result.data)
                    return
            except Exception as e:
                logger.warning(f"Survey context fetch failed: {e}")

        # Fallback: navigate with claim_data directly (for claims without survey context)
        if claim_data:
            self.navigate_to(Pages.CASE_DETAILS, claim_data)
            return

        logger.warning(f"Could not load claim details for: {claim_id}")

    def _start_new_office_survey(self):
        """
        Start a new office survey (UC-004 S01).
        Resets the wizard to initial state and opens it.
        """
        logger.info("Starting new office survey")

        # Reset wizard (DRY: use centralized method)
        self._reset_wizard()

        # Navigate to wizard
        self.stack.setCurrentWidget(self.office_survey_wizard)

        logger.debug("New office survey wizard opened")

    def _on_survey_completed(self, survey_id: str):
        """Handle survey completion from wizard."""
        from ui.components.toast import Toast
        logger.info(f"Survey completed: {survey_id}")

        Toast.show_toast(
            self,
            "✅ تم إنهاء المسح بنجاح!",
            Toast.SUCCESS
        )

        self.pages[Pages.DRAFT_CLAIMS].refresh()
        self.navbar.set_current_tab(1)
        self._on_tab_changed(1)

    def _on_survey_cancelled(self):
        """Handle survey cancellation from wizard."""
        logger.info("Survey cancelled")
        self.navbar.set_current_tab(1)
        self._on_tab_changed(1)

    def _on_survey_saved_draft(self, survey_id: str):
        """Handle survey saved as draft."""
        logger.info(f"Survey saved as draft: {survey_id}")
        # Refresh the draft list
        if hasattr(self.pages.get(Pages.DRAFT_CLAIMS), 'refresh'):
            self.pages[Pages.DRAFT_CLAIMS].refresh()

    def toggle_language(self):
        """Show language dialog and apply selection."""
        from ui.components.dialogs.language_dialog import LanguageDialog

        current = "ar" if self._is_arabic else "en"
        selected = LanguageDialog.get_language(parent=self, current_lang=current)
        if selected is None or selected == current:
            return

        self._is_arabic = (selected == "ar")
        self.i18n.set_language(selected)
        tm_set_language(selected)

        if self._is_arabic:
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

        self.language_changed.emit(self._is_arabic)
        logger.info(f"Language changed to: {'Arabic' if self._is_arabic else 'English'}")

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

    # =========================================================================
    # Mouse Events - Window Dragging
    # =========================================================================

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


