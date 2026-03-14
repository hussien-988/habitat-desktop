# -*- coding: utf-8 -*-
"""
Import Wizard Page - 5-Step Wizard Pattern
UC-003: Bulk Data Import

Structure (SAME as FieldWorkPreparationPage):
- Header (fixed) + Step Indicator
- QStackedWidget (content changes between steps)
- Footer (fixed)

Steps:
  1. Packages — select incoming package (uploaded by tablet via /sync/upload)
  2. Staging — staging + validation report + duplicate detection (merged)
  3. Review — staged entities review
  4. Commit — approve + commit confirmation
  5. Report — commit report
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QFrame, QPushButton,
    QHBoxLayout, QLabel, QGraphicsDropShadowEffect, QApplication,
    QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

from ui.components.wizard_header import WizardHeader
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

TOTAL_STEPS = 5

_STEP_NAMES = [
    "اختيار الحزمة",
    "التدريج والتحقق",
    "المراجعة",
    "التأكيد",
    "التقرير",
]


class ImportWizardPage(QWidget):
    """
    Import Wizard - 5-Step Wizard Structure.

    Same structure as FieldWorkPreparationPage:
    1. Fixed header + step indicator
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

        # Step indicator
        self._step_indicator = self._create_step_indicator()
        content_layout.addWidget(self._step_indicator)

        # Step container (QStackedWidget)
        self.step_container = QStackedWidget()
        content_layout.addWidget(self.step_container, 1)

        outer_layout.addWidget(content_container, 1)

        # Loading overlay (hidden)
        self._loading_overlay = self._create_loading_overlay()

        # Footer (fixed, full width)
        footer = self._create_footer()
        outer_layout.addWidget(footer)

    # -- Step Indicator -------------------------------------------------------

    def _create_step_indicator(self) -> QFrame:
        """Create step progress indicator bar."""
        container = QFrame()
        container.setFixedHeight(64)
        container.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-bottom: 1px solid #E1E8ED;
            }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(40, 8, 40, 8)
        layout.setSpacing(0)

        self._step_circles = []
        self._step_labels = []
        self._step_lines = []

        for i in range(TOTAL_STEPS):
            # Circle
            circle = QLabel(str(i + 1))
            circle.setFixedSize(32, 32)
            circle.setAlignment(Qt.AlignCenter)
            circle.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            self._step_circles.append(circle)

            # Label
            name_label = QLabel(_STEP_NAMES[i])
            name_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet("background: transparent; border: none;")
            self._step_labels.append(name_label)

            # Circle + label vertical group
            step_group = QVBoxLayout()
            step_group.setSpacing(2)
            step_group.setAlignment(Qt.AlignCenter)
            step_group.addWidget(circle, 0, Qt.AlignCenter)
            step_group.addWidget(name_label, 0, Qt.AlignCenter)

            step_widget = QWidget()
            step_widget.setStyleSheet("background: transparent; border: none;")
            step_widget.setLayout(step_group)
            step_widget.setFixedWidth(100)

            layout.addWidget(step_widget)

            # Connecting line (not after last step)
            if i < TOTAL_STEPS - 1:
                line = QFrame()
                line.setFixedHeight(2)
                line.setStyleSheet("background: transparent; border: none;")
                self._step_lines.append(line)

                line_container = QWidget()
                line_container.setStyleSheet("background: transparent; border: none;")
                line_layout = QVBoxLayout(line_container)
                line_layout.setContentsMargins(0, 12, 0, 18)
                line_layout.addWidget(line)

                layout.addWidget(line_container, 1)

        self._update_step_indicator(0)
        return container

    def _update_step_indicator(self, current: int):
        """Update step indicator styling for the current step."""
        for i in range(TOTAL_STEPS):
            circle = self._step_circles[i]
            label = self._step_labels[i]

            if i < current:
                # Completed
                circle.setStyleSheet("""
                    background-color: #10B981; color: #FFFFFF;
                    border-radius: 16px; border: none;
                """)
                circle.setText("\u2713")
                label.setStyleSheet("color: #10B981; background: transparent; border: none;")
            elif i == current:
                # Active
                circle.setStyleSheet("""
                    background-color: #3890DF; color: #FFFFFF;
                    border-radius: 16px; border: none;
                """)
                circle.setText(str(i + 1))
                label.setStyleSheet("color: #3890DF; background: transparent; border: none; font-weight: 600;")
            else:
                # Upcoming
                circle.setStyleSheet("""
                    background-color: #F3F4F6; color: #9CA3AF;
                    border-radius: 16px; border: none;
                """)
                circle.setText(str(i + 1))
                label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")

        for i, line in enumerate(self._step_lines):
            if i < current:
                line.setStyleSheet("background-color: #10B981; border: none;")
            else:
                line.setStyleSheet("background-color: #E5E7EB; border: none;")

    # -- Loading Overlay ------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        """Create a loading overlay shown during blocking API calls."""
        overlay = QFrame(self)
        overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 200);
            }
        """)
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        # Spinner card
        card = QFrame()
        card.setFixedSize(280, 100)
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(8)

        self._loading_label = QLabel("جاري المعالجة...")
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_label)

        # Simple animated dots indicator
        self._loading_dots = QLabel("")
        self._loading_dots.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._loading_dots.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_dots.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_dots)

        overlay_layout.addWidget(card)

        # Dots animation timer
        self._dots_count = 0
        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)

        return overlay

    def _show_loading(self, message: str):
        """Show loading overlay with a message."""
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)
        QApplication.processEvents()

    def _hide_loading(self):
        """Hide loading overlay."""
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

    def _animate_dots(self):
        """Animate loading dots."""
        self._dots_count = (self._dots_count + 1) % 4
        self._loading_dots.setText("." * self._dots_count)

    def resizeEvent(self, event):
        """Resize overlay with the widget."""
        super().resizeEvent(event)
        if self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Footer ---------------------------------------------------------------

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

        # Cancel package button (shown on steps 2-4)
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
        # Step 1: Incoming packages (select a package to process)
        from ui.pages.import_step1_packages import ImportStep1Packages
        self.step1 = ImportStep1Packages(
            self.import_controller,
            parent=self
        )
        self.step1.package_selected.connect(self._on_package_selected)
        self.step_container.addWidget(self.step1)

        # Steps 2-5: created lazily when needed
        self.step2 = None        # staging + validation + duplicates
        self.step_review = None   # review (uses import_step4_review.py)
        self.step_commit = None   # commit (uses import_step5_commit.py)
        self.step_report = None   # report (uses import_step6_report.py)

        self.current_step = 0

    # -- Navigation ----------------------------------------------------------

    def _on_back(self):
        """Handle back button."""
        if self.current_step > 0 and self.current_step < 3:
            self.current_step -= 1
            self.step_container.setCurrentIndex(self.current_step)
            self._update_navigation()

    def _on_next(self):
        """Handle next button — step transitions with controller calls."""
        if self.current_step == 0:
            self._transition_step1_to_step2()

        elif self.current_step == 1:
            self._transition_step2_to_review()

        elif self.current_step == 2:
            self._transition_review_to_commit()

        elif self.current_step == 3:
            self._transition_commit_to_report()

        elif self.current_step == 4:
            self.refresh()

    def _on_package_selected(self, package_id: str):
        """Handle package selection from Step 1."""
        self.btn_next.setEnabled(bool(package_id))

    def _transition_step1_to_step2(self):
        """Step 1 -> 2: stage the package + detect duplicates, then show results."""
        package_id = self.step1.get_selected_package_id()
        if not package_id:
            return

        self._current_package_id = package_id
        self.step1._stop_polling()

        self.btn_next.setEnabled(False)
        self._show_loading("جاري تدريج الحزمة...")

        # Stage (package already uploaded by tablet via /sync/upload)
        stage_result = self.import_controller.stage_package(self._current_package_id)
        if not stage_result.success:
            logger.error(f"Staging failed: {stage_result.message}")
            self._hide_loading()
            self.btn_next.setEnabled(True)
            self._show_error(stage_result.message_ar or "فشل تدريج الحزمة")
            self.step1._start_polling()
            return

        # Detect duplicates
        self._loading_label.setText("جاري كشف التكرارات...")
        QApplication.processEvents()
        dup_result = self.import_controller.detect_duplicates(self._current_package_id)
        duplicates_data = None
        if dup_result.success:
            duplicates_data = dup_result.data
        else:
            logger.warning(f"Duplicate detection failed: {dup_result.message}")

        self._hide_loading()

        # Create Step 2 (staging + validation + duplicates)
        self._ensure_step2(duplicates_data)
        self.current_step = 1
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_step2_to_review(self):
        """Step 2 -> Review: show staged entities for review."""
        self._ensure_step_review()
        self.current_step = 2
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_review_to_commit(self):
        """Review -> Commit: approve the package, then show commit confirmation."""
        self.btn_next.setEnabled(False)
        self._show_loading("جاري الموافقة على الحزمة...")

        approve_result = self.import_controller.approve_package(self._current_package_id)

        self._hide_loading()

        if not approve_result.success:
            logger.error(f"Approve failed: {approve_result.message}")
            self.btn_next.setEnabled(True)
            self._show_error(approve_result.message_ar or "فشل الموافقة على الحزمة")
            return

        self._ensure_step_commit()
        self.current_step = 3
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()

    def _transition_commit_to_report(self):
        """Commit -> Report: commit the package, then show report."""
        self.btn_next.setEnabled(False)
        self._show_loading("جاري إدخال البيانات...")

        # Show progress on commit step
        if self.step_commit and hasattr(self.step_commit, 'set_committing'):
            self.step_commit.set_committing(True)

        commit_result = self.import_controller.commit_package(self._current_package_id)

        if self.step_commit and hasattr(self.step_commit, 'set_committing'):
            self.step_commit.set_committing(False)

        self._hide_loading()

        if not commit_result.success:
            logger.error(f"Commit failed: {commit_result.message}")
            self.btn_next.setEnabled(True)
            self._show_error(commit_result.message_ar or "فشل إدخال البيانات")
            return

        self._ensure_step_report()
        self.current_step = 4
        self.step_container.setCurrentIndex(self.current_step)
        self._update_navigation()
        self.completed.emit({"package_id": self._current_package_id})

    # -- Lazy step creation ---------------------------------------------------

    def _ensure_step2(self, duplicates_data=None):
        """Create or rebuild Step 2: Staging + Validation + Duplicates."""
        if self.step2 is not None:
            self.step_container.removeWidget(self.step2)
            self.step2.deleteLater()

        from ui.pages.import_step2_staging import ImportStep2Staging
        self.step2 = ImportStep2Staging(
            self.import_controller,
            self._current_package_id,
            duplicates_data=duplicates_data,
            parent=self
        )
        self.step_container.addWidget(self.step2)

    def _ensure_step_review(self):
        """Create or rebuild Review step (uses import_step4_review)."""
        if self.step_review is not None:
            self.step_container.removeWidget(self.step_review)
            self.step_review.deleteLater()

        from ui.pages.import_step4_review import ImportStep4Review
        self.step_review = ImportStep4Review(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step_review)

    def _ensure_step_commit(self):
        """Create or rebuild Commit step (uses import_step5_commit)."""
        if self.step_commit is not None:
            self.step_container.removeWidget(self.step_commit)
            self.step_commit.deleteLater()

        from ui.pages.import_step5_commit import ImportStep5Commit
        self.step_commit = ImportStep5Commit(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step_commit)

    def _ensure_step_report(self):
        """Create or rebuild Report step (uses import_step6_report)."""
        if self.step_report is not None:
            self.step_container.removeWidget(self.step_report)
            self.step_report.deleteLater()

        from ui.pages.import_step6_report import ImportStep6Report
        self.step_report = ImportStep6Report(
            self.import_controller,
            self._current_package_id,
            parent=self
        )
        self.step_container.addWidget(self.step_report)

    # -- Navigation state -----------------------------------------------------

    def _update_navigation(self):
        """Update navigation buttons and step indicator based on current step."""
        self._update_step_indicator(self.current_step)

        # Cancel button visible on steps 2-4 (index 1-3)
        self.btn_cancel.setVisible(1 <= self.current_step <= 3)

        if self.current_step == 0:
            self.btn_back.setEnabled(False)
            self.btn_next.setText("بدء المعالجة   >")
            has_selection = (
                hasattr(self, 'step1')
                and hasattr(self.step1, 'get_selected_package_id')
                and bool(self.step1.get_selected_package_id())
            )
            self.btn_next.setEnabled(has_selection)

        elif self.current_step == 1:
            self.btn_back.setEnabled(True)
            self.btn_next.setText("التالي   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 2:
            self.btn_back.setEnabled(True)
            self.btn_next.setText("موافقة وإدخال   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 3:
            self.btn_back.setEnabled(False)
            self.btn_next.setText("إدخال البيانات   >")
            self.btn_next.setEnabled(True)

        elif self.current_step == 4:
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

        msg_box = QMessageBox(self)
        msg_box.setLayoutDirection(Qt.RightToLeft)
        msg_box.setWindowTitle("تأكيد الإلغاء")
        msg_box.setText("هل أنت متأكد من إلغاء هذه الحزمة؟")
        msg_box.setInformativeText("لا يمكن التراجع عن هذا الإجراء.")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        msg_box.button(QMessageBox.Yes).setText("نعم، إلغاء")
        msg_box.button(QMessageBox.No).setText("لا، تراجع")

        if msg_box.exec_() != QMessageBox.Yes:
            return

        logger.info(f"Cancelling package: {self._current_package_id}")
        self._show_loading("جاري إلغاء الحزمة...")
        cancel_result = self.import_controller.cancel_package(self._current_package_id)
        self._hide_loading()

        if not cancel_result.success:
            logger.error(f"Cancel failed: {cancel_result.message}")
            self._show_error(cancel_result.message_ar or "فشل إلغاء الحزمة")
            return

        self._show_success("تم إلغاء الحزمة بنجاح")
        self.cancelled.emit()
        self.refresh()

    # -- Error/Success display ------------------------------------------------

    def _show_error(self, message: str):
        """Show error message via dialog."""
        from ui.components.message_dialog import MessageDialog
        MessageDialog.error(self, "خطأ", message)

    def _show_success(self, message: str):
        """Show success message via dialog."""
        from ui.components.message_dialog import MessageDialog
        MessageDialog.success(self, "نجاح", message)

    # -- Public interface -----------------------------------------------------

    def refresh(self, data=None):
        """Reset wizard to step 1 for a new import."""
        for step_attr in ('step_report', 'step_commit', 'step_review', 'step2'):
            step = getattr(self, step_attr, None)
            if step is not None:
                self.step_container.removeWidget(step)
                step.deleteLater()
                setattr(self, step_attr, None)

        self._current_package_id = None
        self.current_step = 0
        self.step_container.setCurrentIndex(0)
        self._update_navigation()

        if hasattr(self.step1, 'reset'):
            self.step1.reset()
        if hasattr(self.step1, '_start_polling'):
            self.step1._start_polling()

    def configure_for_role(self, role: str):
        """Store user role for RBAC and propagate to steps."""
        self._user_role = role
        for step_attr in ('step1', 'step2', 'step_review', 'step_commit', 'step_report'):
            step = getattr(self, step_attr, None)
            if step is not None and hasattr(step, 'configure_for_role'):
                step.configure_for_role(role)
