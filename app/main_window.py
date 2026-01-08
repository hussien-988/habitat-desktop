# -*- coding: utf-8 -*-
"""
Main application window with sidebar navigation and QStackedWidget routing.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QShortcut, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence

from .config import Config, Pages
from repositories.database import Database
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with navigation shell."""

    language_changed = pyqtSignal(bool)  # True for Arabic, False for English

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.current_user = None
        self._is_arabic = True  # افتراضياً عربي

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
        self.setWindowTitle(f"{Config.APP_NAME} - {Config.APP_TITLE}")
        self.setMinimumSize(Config.WINDOW_MIN_WIDTH, Config.WINDOW_MIN_HEIGHT)

        # Center on screen
        screen = self.screen().geometry()
        x = (screen.width() - Config.WINDOW_MIN_WIDTH) // 2
        y = (screen.height() - Config.WINDOW_MIN_HEIGHT) // 2
        self.setGeometry(x, y, Config.WINDOW_MIN_WIDTH, Config.WINDOW_MIN_HEIGHT)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Language toggle: Ctrl+L
        self.lang_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self.lang_shortcut.activated.connect(self.toggle_language)

        # Logout: Ctrl+Q
        self.logout_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.logout_shortcut.activated.connect(self._handle_logout)

    def _create_widgets(self):
        """Create main UI components."""
        # Import here to avoid circular imports
        from ui.components.sidebar import Sidebar
        from ui.components.topbar import TopBar
        from ui.pages.login_page import LoginPage
        from ui.pages.dashboard_page import DashboardPage
        from ui.pages.buildings_page import BuildingsPage
        from ui.pages.building_details_page import BuildingDetailsPage
        from ui.pages.units_page import UnitsPage
        from ui.pages.persons_page import PersonsPage
        from ui.pages.relations_page import RelationsPage
        from ui.pages.households_page import HouseholdsPage
        from ui.pages.claims_page import ClaimsPage
        from ui.pages.search_page import SearchPage
        from ui.pages.reports_page import ReportsPage
        from ui.pages.admin_page import AdminPage
        from ui.pages.import_wizard_page import ImportWizardPage
        from ui.pages.map_page import MapPage
        from ui.pages.duplicates_page import DuplicatesPage
        from ui.pages.field_assignment_page import FieldAssignmentPage
        from ui.pages.draft_office_surveys_page import DraftOfficeSurveysPage
        from ui.pages.office_survey_wizard import OfficeSurveyWizard

        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Sidebar (hidden initially)
        self.sidebar = Sidebar(self.i18n, self)
        self.sidebar.setVisible(False)

        # Top bar (hidden initially)
        self.topbar = TopBar(self.i18n, self)
        self.topbar.setVisible(False)

        # Stacked widget for pages
        self.stack = QStackedWidget()

        # Create pages
        self.pages = {}

        # Login page
        self.pages[Pages.LOGIN] = LoginPage(self.db, self.i18n, self)
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

        # Persons page (UC-003)
        self.pages[Pages.PERSONS] = PersonsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.PERSONS])

        # Relations page (Person-Unit Relations)
        self.pages[Pages.RELATIONS] = RelationsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.RELATIONS])

        # Households page (FSD 6.1.6)
        self.pages[Pages.HOUSEHOLDS] = HouseholdsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.HOUSEHOLDS])

        # Claims page (UC-007, UC-008)
        self.pages[Pages.CLAIMS] = ClaimsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.CLAIMS])

        # Search page (UC-011)
        self.pages[Pages.SEARCH] = SearchPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.SEARCH])

        # Reports page (UC-012, UC-013)
        self.pages[Pages.REPORTS] = ReportsPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.REPORTS])

        # Admin page (UC-015)
        self.pages[Pages.ADMIN] = AdminPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.ADMIN])

        # Import wizard page (UC-009)
        self.pages[Pages.IMPORT_WIZARD] = ImportWizardPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.IMPORT_WIZARD])

        # Map view page (UC-014)
        self.pages[Pages.MAP_VIEW] = MapPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.MAP_VIEW])

        # Duplicates page (UC-007, UC-008)
        self.pages[Pages.DUPLICATES] = DuplicatesPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.DUPLICATES])

        # Field Assignment page (UC-012)
        self.pages[Pages.FIELD_ASSIGNMENT] = FieldAssignmentPage(self.db, self.i18n, self)
        self.stack.addWidget(self.pages[Pages.FIELD_ASSIGNMENT])

        # Draft Office Surveys page (UC-005)
        self.pages[Pages.DRAFT_OFFICE_SURVEYS] = DraftOfficeSurveysPage(self.db, self)
        self.stack.addWidget(self.pages[Pages.DRAFT_OFFICE_SURVEYS])

        # Office Survey Wizard (UC-004, UC-005)
        self.office_survey_wizard = OfficeSurveyWizard(self.db, self.i18n, self)
        self.stack.addWidget(self.office_survey_wizard)

    def _setup_layout(self):
        """Setup the main layout."""
        # Main horizontal layout
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add sidebar (no stretch - fixed width area)
        main_layout.addWidget(self.sidebar, 0)

        # Content area (topbar + stack)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self.topbar, 0)  # No stretch for topbar
        content_layout.addWidget(self.stack, 1)   # Stack takes all remaining space

        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget, 1)  # Content expands to fill space

    def _connect_signals(self):
        """Connect widget signals to slots."""
        # Login page signals
        self.pages[Pages.LOGIN].login_successful.connect(self._on_login_success)

        # Sidebar navigation
        self.sidebar.navigate.connect(self.navigate_to)

        # Top bar signals
        self.topbar.logout_requested.connect(self._handle_logout)
        self.topbar.language_toggled.connect(self.toggle_language)

        # Buildings page - view details
        self.pages[Pages.BUILDINGS].view_building.connect(self._on_view_building)

        # Building details - back to list
        self.pages[Pages.BUILDING_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.BUILDINGS)
        )

        # Import wizard completion
        self.pages[Pages.IMPORT_WIZARD].import_completed.connect(self._on_import_completed)

        # Draft Office Surveys - resume draft (UC-005 S03)
        self.pages[Pages.DRAFT_OFFICE_SURVEYS].draft_selected.connect(self._on_draft_selected)

        # Office Survey Wizard signals
        self.office_survey_wizard.survey_completed.connect(self._on_survey_completed)
        self.office_survey_wizard.survey_cancelled.connect(self._on_survey_cancelled)
        self.office_survey_wizard.survey_saved_draft.connect(self._on_survey_saved_draft)

        # Language change signal
        self.language_changed.connect(self._on_language_changed)

    def _show_login(self):
        """Show the login page."""
        self.sidebar.setVisible(False)
        self.topbar.setVisible(False)
        self.stack.setCurrentWidget(self.pages[Pages.LOGIN])
        logger.info("Showing login page")

    def _on_login_success(self, user):
        """Handle successful login."""
        self.current_user = user
        logger.info(f"User logged in: {user.username} ({user.role})")

        # Show navigation
        self.sidebar.setVisible(True)
        self.topbar.setVisible(True)

        # Update UI with user info
        self.topbar.set_user(user)
        self.sidebar.set_user(user)

        # Navigate to dashboard
        self.navigate_to(Pages.DASHBOARD)

    def _handle_logout(self):
        """Handle logout request."""
        if self.current_user:
            reply = QMessageBox.question(
                self,
                self.i18n.t("logout_confirm_title"),
                self.i18n.t("logout_confirm_message"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                logger.info(f"User logged out: {self.current_user.username}")
                self.current_user = None
                self._show_login()

    def navigate_to(self, page_id: str, data=None):
        """Navigate to a specific page."""
        if page_id not in self.pages:
            logger.error(f"Page not found: {page_id}")
            return

        page = self.pages[page_id]

        # Refresh page data if method exists
        if hasattr(page, 'refresh'):
            page.refresh(data)

        # Update sidebar selection
        self.sidebar.set_selected(page_id)

        # Update topbar title
        self.topbar.set_title(page_id)

        # Show page
        self.stack.setCurrentWidget(page)
        logger.debug(f"Navigated to: {page_id}")

    def _on_view_building(self, building_id: str):
        """Handle view building request from buildings list."""
        logger.debug(f"Viewing building: {building_id}")
        self.navigate_to(Pages.BUILDING_DETAILS, building_id)

    def _on_import_completed(self, stats: dict):
        """Handle import wizard completion."""
        from ui.components.toast import Toast
        Toast.show_toast(
            self,
            self.i18n.t("import_success").format(count=stats.get("imported", 0)),
            Toast.SUCCESS
        )
        # Refresh dashboard
        self.navigate_to(Pages.DASHBOARD)

    def _on_draft_selected(self, draft_context: dict):
        """
        Handle draft survey selection from draft list (UC-005 S03).
        Load the draft into the office survey wizard.
        """
        logger.info(f"Loading draft survey into wizard")

        # Load draft data into wizard
        self.office_survey_wizard.load_draft(draft_context)

        # Navigate to wizard
        self.stack.setCurrentWidget(self.office_survey_wizard)
        logger.debug("Draft loaded into office survey wizard")

    def _on_survey_completed(self, survey_id: str):
        """Handle survey completion from wizard."""
        from ui.components.toast import Toast
        logger.info(f"Survey completed: {survey_id}")

        Toast.show_toast(
            self,
            "✅ تم إنهاء المسح بنجاح!",
            Toast.SUCCESS
        )

        # Refresh draft list and return to it
        self.pages[Pages.DRAFT_OFFICE_SURVEYS].refresh()
        self.navigate_to(Pages.DASHBOARD)

    def _on_survey_cancelled(self):
        """Handle survey cancellation from wizard."""
        logger.info("Survey cancelled")
        # Return to draft list or dashboard
        self.navigate_to(Pages.DRAFT_OFFICE_SURVEYS)

    def _on_survey_saved_draft(self, survey_id: str):
        """Handle survey saved as draft."""
        logger.info(f"Survey saved as draft: {survey_id}")
        # Refresh the draft list
        if hasattr(self.pages.get(Pages.DRAFT_OFFICE_SURVEYS), 'refresh'):
            self.pages[Pages.DRAFT_OFFICE_SURVEYS].refresh()

    def toggle_language(self):
        """Toggle between English and Arabic."""
        self._is_arabic = not self._is_arabic
        self.i18n.set_language("ar" if self._is_arabic else "en")

        # Update layout direction
        if self._is_arabic:
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

        # Emit signal for components to update
        self.language_changed.emit(self._is_arabic)
        logger.info(f"Language changed to: {'Arabic' if self._is_arabic else 'English'}")

    def _on_language_changed(self, is_arabic: bool):
        """Handle language change across all components."""
        # Update all pages
        for page in self.pages.values():
            if hasattr(page, 'update_language'):
                page.update_language(is_arabic)

        # Update sidebar and topbar
        self.sidebar.update_language(is_arabic)
        self.topbar.update_language(is_arabic)

        # Update window title
        title = Config.APP_TITLE_AR if is_arabic else Config.APP_TITLE
        self.setWindowTitle(f"{Config.APP_NAME} - {title}")

    def closeEvent(self, event):
        """Handle window close event."""
        if self.current_user:
            reply = QMessageBox.question(
                self,
                self.i18n.t("exit_confirm_title"),
                self.i18n.t("exit_confirm_message"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

        logger.info("Application closing")
        event.accept()
