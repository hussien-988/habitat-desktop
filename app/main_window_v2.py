# -*- coding: utf-8 -*-
"""
Main application window with navbar navigation (NEW DESIGN)
Based on Figma design pages 1-31
Replaces sidebar with top navbar and tabs
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QShortcut, QMessageBox,
    QFrame, QGraphicsDropShadowEffect, QSizeGrip
)

from PyQt5.QtCore import Qt, pyqtSignal, QPoint

from PyQt5.QtGui import QKeySequence, QColor, QMouseEvent

from .config import Config, Pages
from repositories.database import Database
from utils.i18n import I18n
from utils.logger import get_logger

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

    def _create_widgets(self):
        """Create main UI components with new design."""
        # Import here to avoid circular imports
        from ui.components.navbar import Navbar
        from ui.pages.login_page import LoginPage
        from ui.pages.dashboard_page import DashboardPage
        from ui.pages.buildings_page import BuildingsPage
        from ui.pages.building_details_page import BuildingDetailsPage
        from ui.pages.units_page import UnitsPage
        from ui.pages.persons_page import PersonsPage
        from ui.pages.relations_page import RelationsPage
        from ui.pages.households_page import HouseholdsPage
        from ui.pages.completed_claims_page import CompletedClaimsPage
        from ui.pages.draft_claims_page import DraftClaimsPage
        from ui.pages.search_page import SearchPage
        from ui.pages.reports_page import ReportsPage
        from ui.pages.admin_page import AdminPage
        from ui.pages.import_wizard_page import ImportWizardPage
        from ui.pages.map_page import MapPage
        from ui.pages.duplicates_page import DuplicatesPage
        from ui.pages.field_assignment_page import FieldAssignmentPage
        from ui.pages.draft_office_surveys_page_v2 import DraftOfficeSurveysPage
        from ui.wizards.office_survey import OfficeSurveyWizard


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
        self.pages[Pages.LOGIN] = LoginPage(self.i18n, self)
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

        # Draft Office Surveys page (UC-005) - NEW DESIGN V2
        self.pages[Pages.DRAFT_OFFICE_SURVEYS] = DraftOfficeSurveysPage(self.db, self)
        self.stack.addWidget(self.pages[Pages.DRAFT_OFFICE_SURVEYS])

        # Office Survey Wizard (UC-004, UC-005) - NEW wizard framework
        self.office_survey_wizard = OfficeSurveyWizard(self.db, self)
        self.stack.addWidget(self.office_survey_wizard)

        # Map tabs to pages (based on Figma design)
        # Tab 0: المطالبات المكتملة (Completed Claims)
        # Tab 1: المسودة (Draft Claims)
        # Tab 2: المبانى (Buildings)
        # Tab 3: الوحدات السكنية (Units)
        # Tab 4: التكرارات (Duplicates)
        # Tab 5: استيراد البيانات (Import Data - UC-003)
        self.tab_page_mapping = {
            0: Pages.CLAIMS,            # المطالبات المكتملة
            1: Pages.DRAFT_CLAIMS,      # المسودة (Draft Claims)
            2: Pages.BUILDINGS,         # المبانى
            3: Pages.UNITS,             # الوحدات السكنية
            4: Pages.DUPLICATES,        # التكرارات
            5: Pages.IMPORT_WIZARD,     # استيراد البيانات (UC-003)
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
        self.navbar.search_requested.connect(self._on_search_requested)

        # Buildings page - view details
        self.pages[Pages.BUILDINGS].view_building.connect(self._on_view_building)

        # Building details - back to list
        self.pages[Pages.BUILDING_DETAILS].back_requested.connect(
            lambda: self.navigate_to(Pages.BUILDINGS)
        )

        # Import wizard completion
        self.pages[Pages.IMPORT_WIZARD].import_completed.connect(self._on_import_completed)

        # Draft Office Surveys - resume draft (UC-005 S03)
        if Pages.DRAFT_OFFICE_SURVEYS in self.pages:
            self.pages[Pages.DRAFT_OFFICE_SURVEYS].draft_selected.connect(self._on_draft_selected)

        # Draft Claims - view/edit draft claim
        self.pages[Pages.DRAFT_CLAIMS].claim_selected.connect(self._on_draft_claim_selected)

        # Add Claim buttons - start new office survey (UC-004 S01)
        self.pages[Pages.DRAFT_CLAIMS].add_claim_clicked.connect(self._start_new_office_survey)
        self.pages[Pages.CLAIMS].add_claim_clicked.connect(self._start_new_office_survey)

        # Office Survey Wizard signals
        self.office_survey_wizard.survey_completed.connect(self._on_survey_completed)
        self.office_survey_wizard.survey_cancelled.connect(self._on_survey_cancelled)
        self.office_survey_wizard.survey_saved_draft.connect(self._on_survey_saved_draft)

        # Language change signal
        self.language_changed.connect(self._on_language_changed)

    def _show_login(self):
        """Show the login page."""
        self.navbar.setVisible(False)
        self.stack.setCurrentWidget(self.pages[Pages.LOGIN])
        logger.info("Showing login page")

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

        # Navigate to first tab (Completed Claims / Dashboard)
        self.navbar.set_current_tab(0)
        self._on_tab_changed(0)

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

        # Pass token to OfficeSurveyWizard controller
        if hasattr(self, 'office_survey_wizard') and self.office_survey_wizard:
            self.office_survey_wizard.set_auth_token(token)
            logger.info("API token set for OfficeSurveyWizard")

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
        # Navigate to search page with query
        self.navigate_to(Pages.SEARCH, search_text)

    def navigate_to(self, page_id: str, data=None):
        """
        Navigate to a specific page.

        Best Practice: Prevents data loss by showing save confirmation dialog
        when leaving wizard with unsaved data.
        """
        # Check if currently in wizard with unsaved data
        current_widget = self.stack.currentWidget()
        if current_widget == self.office_survey_wizard and page_id != "office_survey_wizard":
            # User is trying to leave wizard - check for unsaved data
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
                        if Pages.DRAFT_OFFICE_SURVEYS in self.pages:
                            self.pages[Pages.DRAFT_OFFICE_SURVEYS].refresh()
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

                # Reset wizard for next time
                self._reset_wizard()

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

        # Re-set API token after reset (steps may have new controllers)
        if hasattr(self, '_api_token') and self._api_token:
            self.office_survey_wizard.set_auth_token(self._api_token)

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

    def _on_draft_claim_selected(self, claim_id: str):
        """Handle draft claim selection."""
        logger.info(f"Draft claim selected: {claim_id}")
        from ui.components.toast import Toast
        Toast.show_toast(
            self,
            f"تم اختيار المسودة: {claim_id}",
            Toast.INFO
        )

    def _on_draft_selected(self, draft_context: dict):
        """
        Handle draft survey selection from draft list (UC-005 S03).
        Load the draft into the office survey wizard.
        """
        logger.info(f"Loading draft survey into wizard")

        # Restore context from draft (SurveyContext imported in wizard creation)
        from ui.wizards.office_survey.survey_context import SurveyContext
        self.office_survey_wizard.context = SurveyContext.from_dict(draft_context)

        # Navigate to saved step
        saved_step = self.office_survey_wizard.context.current_step_index or 0
        self.office_survey_wizard.navigator.goto_step(saved_step, skip_validation=True)

        # Navigate to wizard
        self.stack.setCurrentWidget(self.office_survey_wizard)
        logger.debug("Draft loaded into office survey wizard")

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

        self.pages[Pages.DRAFT_OFFICE_SURVEYS].refresh()
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

        # Update navbar
        if hasattr(self.navbar, 'update_language'):
            self.navbar.update_language(is_arabic)

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


