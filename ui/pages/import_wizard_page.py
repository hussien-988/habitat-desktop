# -*- coding: utf-8 -*-
"""
Import Wizard Page - 6-Step Wizard Pattern
UC-003: Bulk Data Import

Structure (SAME as FieldWorkPreparationPage):
- Header (fixed)
- QStackedWidget (content changes between steps)
- Footer (fixed)

Steps:
  1. Upload — file selection + upload
  2. Staging — staging + validation report
  3. Duplicates — duplicate detection results
  4. Review — staged entities review
  5. Commit — approve + commit
  6. Report — commit report
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QFrame, QPushButton,
    QHBoxLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from ui.components.wizard_header import WizardHeader
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

TOTAL_STEPS = 6


class ImportWizardPage(QWidget):
    """
    Import Wizard - 6-Step Wizard Structure.

    Same structure as FieldWorkPreparationPage:
    1. Fixed header
    2. QStackedWidget for steps
    3. Fixed footer with back/next + cancel button
    """

    completed = pyqtSignal(object)
    cancelled = pyqtSignal()

    def __init__(self, import_controller=None, db=None, i18n=None, parent=None):
        """Initialize import wizard."""
        super().__init__(parent)
        self.import_controller = import_controller
        self.db = db
        self.i18n = i18n
        self._user_role = None
        self._current_package_id = None

        self._setup_ui()
        self._create_steps()

    def _setup_ui(self):
        """Setup UI (SAME structure as FieldWorkPreparationPage)."""
        self.setLayoutDirection(Qt.RightToLeft)

        from ui.style_manager import StyleManager
        self.setStyleSheet(StyleManager.page_background())

        # Outer layout (no padding) for full-width footer
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Content container (with padding)
        content_container = QWidget()
        content_container.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(content_container)
        from ui.design_system import PageDimensions
        content_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            0
        )
        content_layout.setSpacing(0)

        # Header (fixed)
        self.header = WizardHeader(
            title="استيراد البيانات",
            subtitle="إدارة البيانات  •  استيراد البيانات"
        )
        content_layout.addWidget(self.header)

        # Step container (QStackedWidget)
        self.step_container = QStackedWidget()
        content_layout.addWidget(self.step_container, 1)

        outer_layout.addWidget(content_container, 1)

        # Footer (fixed, full width)
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    def _create_footer(self):
        """Create footer with back, cancel, and next buttons."""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-top: 1px solid #E1E8ED;
            }
        """)
        footer.setFixedHeight(74)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(130, 12, 130, 12)
        layout.setSpacing(0)

        # Back button
        self.btn_back = QPushButton("<   السابق")
        self.btn_back.setFixedSize(252, 50)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_back = QGraphicsDropShadowEffect()
        shadow_back.setBlurRadius(8)
        shadow_back.setXOffset(0)
        shadow_back.setYOffset(2)
        shadow_back.setColor(QColor("#E5EAF6"))
        self.btn_back.setGraphicsEffect(shadow_back)

        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #414D5A;
                border: none;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #F8F9FA;
            }
            QPushButton:disabled {
                background-color: transparent;
                color: transparent;
                border: none;
            }
        """)
        self.btn_back.clicked.connect(self._on_back)
        self.btn_back.setEnabled(False)
        layout.addWidget(self.btn_back)

        layout.addStretch()

        # Cancel package button (shown on steps 2-5)
        self.btn_cancel = QPushButton("إلغاء الحزمة")
        self.btn_cancel.setFixedSize(252, 50)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_cancel = QGraphicsDropShadowEffect()
        shadow_cancel.setBlurRadius(8)
        shadow_cancel.setXOffset(0)
        shadow_cancel.setYOffset(2)
        shadow_cancel.setColor(QColor("#F6E5E5"))
        self.btn_cancel.setGraphicsEffect(shadow_cancel)

        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #DC3545;
                border: 1px solid #DC3545;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #FFF5F5;
            }
            QPushButton:disabled {
                background-color: transparent;
                color: transparent;
                border: none;
            }
        """)
        self.btn_cancel.clicked.connect(self._on_cancel_package)
        self.btn_cancel.setVisible(False)
        layout.addWidget(self.btn_cancel)

        # Spacer between cancel and next
        layout.addStretch()

        # Next button
        self.btn_next = QPushButton("التالي   >")
        self.btn_next.setFixedSize(252, 50)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))

        shadow_next = QGraphicsDropShadowEffect()
        shadow_next.setBlurRadius(8)
        shadow_next.setXOffset(0)
        shadow_next.setYOffset(2)
        shadow_next.setColor(QColor("#E5EAF6"))
        self.btn_next.setGraphicsEffect(shadow_next)

        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #f0f7ff;
                color: #3890DF;
                border: 1px solid #3890DF;
                border-radius: 8px;
                font-size: 12pt;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #E3F2FD;
            }
            QPushButton:disabled {
                background-color: #F8F9FA;
                color: #9CA3AF;
                border-color: #E1E8ED;
            }
        """)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_next.setEnabled(False)
        layout.addWidget(self.btn_next)

        return footer

    def _create_steps(self):
        """Create step placeholders. Steps are created lazily."""
        # Step 1: Upload (created eagerly as the initial step)
        from ui.pages.import_step1_upload import ImportStep1Upload
        self.step1 = ImportStep1Upload(
            self.import_controller,
            parent=self
        )
        self.step_container.addWidget(self.step1)

        # Steps 2-6: created lazily when needed
        self.step2 = None
        self.step3 = None
        self.step4 = None
        self.step5 = None
        self.step6 = None

        self.current_step = 0

    # -- Navigation ----------------------------------------------------------

    def _on_back(self):
        """Handle back button."""
        if self.current_step > 0 and self.current_step < 5:
            self.current_step -= 1
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

    def _on_next(self):
        """Handle next button — step transitions with controller calls."""
        if self.current_step == 0:
            self._transition_step1_to_step2()

        elif self.current_step == 1:
            self._transition_step2_to_step3()

        elif self.current_step == 2:
            self._transition_step3_to_step4()

        elif self.current_step == 3:
            self._transition_step4_to_step5()

        elif self.current_step == 4:
            self._transition_step5_to_step6()

        elif self.current_step == 5:
            # Step 6: "New Import" button — restart wizard
            self.refresh()

    def _transition_step1_to_step2(self):
        """Step 1 -> 2: upload_package, then stage_package, then show staging."""
        file_path = self.step1.get_selected_file_path()
        if not file_path:
            return

        self.btn_next.setEnabled(False)
        self.btn_next.setText("جاري الرفع...")

        # Upload
        upload_result = self.import_controller.upload_package(file_path)
        if not upload_result.success:
            logger.error(f"Upload failed: {upload_result.message}")
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)
            self._show_error(upload_result.message_ar or "فشل رفع الملف")
            return

        pkg_data = upload_result.data or {}
        self._current_package_id = (
            pkg_data.get("id") or pkg_data.get("packageId") or ""
        )
        logger.info(f"Package uploaded: {self._current_package_id}")

        # Stage
        self.btn_next.setText("جاري التدريج...")
        stage_result = self.import_controller.stage_package(self._current_package_id)
        if not stage_result.success:
            logger.error(f"Staging failed: {stage_result.message}")
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)
            self._show_error(stage_result.message_ar or "فشل تدريج الحزمة")
            return

        # Create Step 2 (staging + validation)
        self._ensure_step2()
        self.current_step = 1
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_step2_to_step3(self):
        """Step 2 -> 3: detect_duplicates, then show results."""
        self.btn_next.setEnabled(False)
        self.btn_next.setText("جاري كشف التكرارات...")

        dup_result = self.import_controller.detect_duplicates(self._current_package_id)
        if not dup_result.success:
            logger.error(f"Duplicate detection failed: {dup_result.message}")
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)
            self._show_error(dup_result.message_ar or "فشل كشف التكرارات")
            return

        self._ensure_step3(dup_result.data)
        self.current_step = 2
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_step3_to_step4(self):
        """Step 3 -> 4: move to review (no controller call needed)."""
        self._ensure_step4()
        self.current_step = 3
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_step4_to_step5(self):
        """Step 4 -> 5: approve_package, then show commit step."""
        self.btn_next.setEnabled(False)
        self.btn_next.setText("جاري الموافقة...")

        approve_result = self.import_controller.approve_package(self._current_package_id)
        if not approve_result.success:
            logger.error(f"Approve failed: {approve_result.message}")
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)
            self._show_error(approve_result.message_ar or "فشل الموافقة على الحزمة")
            return

        self._ensure_step5()
        self.current_step = 4
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_step5_to_step6(self):
        """Step 5 -> 6: commit_package, then show report."""
        self.btn_next.setEnabled(False)
        self.btn_next.setText("جاري الإدخال...")

        commit_result = self.import_controller.commit_package(self._current_package_id)
        if not commit_result.success:
            logger.error(f"Commit failed: {commit_result.message}")
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)
            self._show_error(commit_result.message_ar or "فشل إدخال البيانات")
            return

        self._ensure_step6()
        self.current_step = 5
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()
        self.completed.emit({"package_id": self._current_package_id})

    # -- Lazy step creation ---------------------------------------------------

    def _ensure_step2(self):
        """Create or rebuild Step 2: Staging + Validation Report."""
        if self.step2 is not None:
            self.step_container.removeWidget(self.step2)
            self.step2.deleteLater()

        from ui.pages.import_step2_staging import ImportStep2Staging
        self.step2 = ImportStep2Staging(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step2)

    def _ensure_step3(self, duplicates_data=None):
        """Create or rebuild Step 3: Duplicate Detection Results."""
        if self.step3 is not None:
            self.step_container.removeWidget(self.step3)
            self.step3.deleteLater()

        from ui.pages.import_step3_duplicates import ImportStep3Duplicates
        self.step3 = ImportStep3Duplicates(
            self.import_controller,
            self._current_package_id,
            duplicates_data=duplicates_data,
            parent=self
        )
        self.step_container.addWidget(self.step3)

    def _ensure_step4(self):
        """Create or rebuild Step 4: Staged Entities Review."""
        if self.step4 is not None:
            self.step_container.removeWidget(self.step4)
            self.step4.deleteLater()

        from ui.pages.import_step4_review import ImportStep4Review
        self.step4 = ImportStep4Review(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step4)

    def _ensure_step5(self):
        """Create or rebuild Step 5: Approve + Commit."""
        if self.step5 is not None:
            self.step_container.removeWidget(self.step5)
            self.step5.deleteLater()

        from ui.pages.import_step5_commit import ImportStep5Commit
        self.step5 = ImportStep5Commit(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step5)

    def _ensure_step6(self):
        """Create or rebuild Step 6: Commit Report."""
        if self.step6 is not None:
            self.step_container.removeWidget(self.step6)
            self.step6.deleteLater()

        from ui.pages.import_step6_report import ImportStep6Report
        self.step6 = ImportStep6Report(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step6)

    # -- Navigation state -----------------------------------------------------

    def _update_navigation(self):
        """Update navigation buttons based on current step."""
        # Cancel button visible on steps 2-5 (index 1-4)
        self.btn_cancel.setVisible(1 <= self.current_step <= 4)

        if self.current_step == 0:
            # Step 1: Upload
            self.btn_back.setEnabled(False)
            self.btn_next.setText("التالي   >")
            has_file = (
                hasattr(self, 'step1')
                and hasattr(self.step1, 'get_selected_file_path')
                and bool(self.step1.get_selected_file_path())
            )
            self.btn_next.setEnabled(has_file)

        elif self.current_step == 1:
            # Step 2: Staging
            self.btn_back.setEnabled(True)
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 2:
            # Step 3: Duplicates
            self.btn_back.setEnabled(True)
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 3:
            # Step 4: Review
            self.btn_back.setEnabled(True)
            self.btn_next.setText("موافقة وإدخال   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 4:
            # Step 5: Commit
            self.btn_back.setEnabled(False)
            self.btn_next.setText("إدخال البيانات   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 5:
            # Step 6: Report — only "New Import" button
            self.btn_back.setEnabled(False)
            self.btn_cancel.setVisible(False)
            self.btn_next.setText("استيراد جديد")
            self.btn_next.setEnabled(True)

    def enable_next_button(self, enabled: bool):
        """Allow steps to enable/disable next button."""
        self.btn_next.setEnabled(enabled)

    # -- Cancel package -------------------------------------------------------

    def _on_cancel_package(self):
        """Cancel the current import package and reset the wizard."""
        if not self._current_package_id:
            return

        logger.info(f"Cancelling package: {self._current_package_id}")
        cancel_result = self.import_controller.cancel_package(self._current_package_id)
        if not cancel_result.success:
            logger.error(f"Cancel failed: {cancel_result.message}")
            self._show_error(cancel_result.message_ar or "فشل إلغاء الحزمة")
            return

        self.cancelled.emit()
        self.refresh()

    # -- Error display --------------------------------------------------------

    def _show_error(self, message: str):
        """Show error message via Toast if available, fallback to log."""
        try:
            main_window = self.window()
            if hasattr(main_window, 'toast'):
                from ui.components.toast import Toast
                main_window.toast.show_message(message, Toast.ERROR)
            else:
                logger.warning(f"Toast unavailable, error: {message}")
        except Exception:
            logger.warning(f"Could not show toast: {message}")

    # -- Public interface -----------------------------------------------------

    def refresh(self, data=None):
        """Reset wizard to step 1 for a new import."""
        # Remove steps 6 down to 2
        for step_attr in ('step6', 'step5', 'step4', 'step3', 'step2'):
            step = getattr(self, step_attr, None)
            if step is not None:
                self.step_container.removeWidget(step)
                step.deleteLater()
                setattr(self, step_attr, None)

        # Reset state
        self._current_package_id = None
        self.current_step = 0
        self.step_container.setCurrentIndex(0)
        self._update_navigation()

        # Reset step 1 if it supports it
        if hasattr(self.step1, 'reset'):
            self.step1.reset()

    def configure_for_role(self, role: str):
        """Store user role for RBAC and propagate to steps."""
        self._user_role = role
        # Propagate to any existing steps
        for step_attr in ('step1', 'step2', 'step3', 'step4', 'step5', 'step6'):
            step = getattr(self, step_attr, None)
            if step is not None and hasattr(step, 'configure_for_role'):
                step.configure_for_role(role)
