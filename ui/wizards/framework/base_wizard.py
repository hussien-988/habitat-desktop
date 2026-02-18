# -*- coding: utf-8 -*-
"""
Base Wizard - Abstract base class for all wizards.

Provides unified wizard UI with:
- Header with title and progress
- Step container
- Navigation buttons (Previous, Next, Cancel, Save Draft)
- Validation handling
- Draft persistence
"""

from typing import List, Optional, Callable
from abc import ABCMeta, abstractmethod

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from .base_step import BaseStep, StepValidationResult
from .wizard_context import WizardContext
from .step_navigator import StepNavigator
from ui.components.action_button import ActionButton
from ui.error_handler import ErrorHandler
from services.translation_manager import tr


# Combine PyQt5 metaclass with ABC metaclass
class ABCQWidgetMeta(type(QWidget), ABCMeta):
    """Metaclass that combines PyQt5's metaclass with ABC."""
    pass


class BaseWizard(QWidget, metaclass=ABCQWidgetMeta):
    """
    Abstract base class for wizards.

    Subclasses must implement:
    - create_steps(): Create and return list of wizard steps
    - create_context(): Create and return wizard context
    - on_submit(): Handle final submission
    """

    # Signals
    wizard_completed = pyqtSignal(dict)  # Emitted when wizard is submitted
    wizard_cancelled = pyqtSignal()
    draft_saved = pyqtSignal(str)  # Emitted with draft ID

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the wizard."""
        super().__init__(parent)

        # Initialize context and steps
        self.context = self.create_context()
        self.steps = self.create_steps()

        # Create navigator
        self.navigator = StepNavigator(self.context, self.steps)

        # Connect navigator signals
        self.navigator.step_changed.connect(self._on_step_changed)
        self.navigator.can_go_next_changed.connect(self._update_navigation_buttons)
        self.navigator.can_go_previous_changed.connect(self._update_navigation_buttons)
        self.navigator.validation_failed.connect(self._on_validation_failed)

        # Setup UI
        self._setup_ui()

        # Show first step
        self.navigator.goto_step(0, skip_validation=True)

    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    def create_steps(self) -> List[BaseStep]:
        """
        Create and return list of wizard steps.

        Returns:
            List of BaseStep instances
        """
        pass

    @abstractmethod
    def create_context(self) -> WizardContext:
        """
        Create and return wizard context.

        Returns:
            WizardContext instance
        """
        pass

    @abstractmethod
    def on_submit(self) -> bool:
        """
        Handle wizard submission.

        This method is called when the user clicks the Finish button
        and all steps are validated.

        Returns:
            True if submission was successful, False otherwise
        """
        pass

    # =========================================================================
    # Optional Methods - Can be overridden by subclasses
    # =========================================================================

    def get_wizard_title(self) -> str:
        """Get wizard title. Override to customize."""
        return "معالج"

    def get_submit_button_text(self) -> str:
        """Get submit button text. Override to customize."""
        return "إنهاء"

    def on_cancel(self) -> bool:
        """
        Handle wizard cancellation.

        Override to customize cancellation behavior.

        Returns:
            True if cancellation should proceed, False to prevent
        """
        return True

    def on_save_draft(self) -> Optional[str]:
        """
        Handle draft saving.

        Override to implement custom draft saving logic.

        Returns:
            Draft ID if successful, None otherwise
        """
        return None

    # =========================================================================
    # UI Setup
    # =========================================================================

    def _setup_ui(self):
        """Setup the wizard UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #ddd;")
        separator.setFixedHeight(1)
        main_layout.addWidget(separator)

        # Step container
        self.step_container = QStackedWidget()
        for step in self.steps:
            self.step_container.addWidget(step)
        main_layout.addWidget(self.step_container, 1)

        # Footer with navigation buttons
        footer = self._create_footer()
        main_layout.addWidget(footer)

    def _create_header(self) -> QWidget:
        """Create wizard header with title and progress."""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)

        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        self.title_label = QLabel(self.get_wizard_title())
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        # Progress bar
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(8)

        self.progress_label = QLabel("الخطوة 1 من {}".format(len(self.steps)))
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e9ecef;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #0d6efd;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar, 1)

        layout.addLayout(progress_layout)

        return header

    def _create_footer(self) -> QWidget:
        """Create wizard footer with navigation buttons."""
        footer = QWidget()
        footer.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # DRY: Use ActionButton component for all footer buttons
        # Left buttons (Cancel, Save Draft)
        self.btn_cancel = ActionButton("إلغاء", variant="secondary", width=114, height=44)
        self.btn_cancel.clicked.connect(self._handle_cancel)
        layout.addWidget(self.btn_cancel)

        self.btn_save_draft = ActionButton(
            text="حفظ كمسودة",
            variant="secondary",
            icon_name="save",
            width=140,  # Wider to accommodate text
            height=44
        )
        self.btn_save_draft.clicked.connect(self._handle_save_draft)
        layout.addWidget(self.btn_save_draft)

        layout.addStretch()

        # Right buttons (Previous, Next/Finish)
        self.btn_previous = ActionButton("السابق", variant="secondary", width=114, height=44)
        self.btn_previous.clicked.connect(self._handle_previous)
        layout.addWidget(self.btn_previous)

        self.btn_next = ActionButton(
            text="التالي",
            variant="primary",
            icon_name="icon",
            width=114,
            height=44
        )
        self.btn_next.clicked.connect(self._handle_next)
        layout.addWidget(self.btn_next)

        return footer

    # =========================================================================
    # Navigation Handlers
    # =========================================================================

    def _handle_previous(self):
        """Handle previous button click."""
        self.navigator.previous_step()

    def _handle_next(self):
        """Handle next button click."""
        # Check if we're on the last step
        if self.navigator.current_index == len(self.steps) - 1:
            self._handle_submit()
        else:
            self.navigator.next_step()

    def _handle_cancel(self):
        """Handle cancel button click."""
        if self.on_cancel():
            self.wizard_cancelled.emit()
            self.close()

    def _handle_save_draft(self):
        """Handle save draft button click."""
        draft_id = self.on_save_draft()
        if draft_id:
            self.draft_saved.emit(draft_id)
            ErrorHandler.show_success(
                self,
                f"{tr('success.draft_saved')}\n{tr('info.draft_id')}: {draft_id}",
                tr("dialog.success")
            )

    def _handle_submit(self):
        """Handle wizard submission."""
        # Validate last step
        current_step = self.navigator.get_current_step()
        if current_step:
            validation_result = current_step.validate()
            if not validation_result.is_valid:
                self._on_validation_failed(validation_result)
                return

        # Call subclass submission handler
        if self.on_submit():
            try:
                data = self.context.to_dict()
            except Exception:
                data = {}
            self.wizard_completed.emit(data)
            self.close()

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_step_changed(self, old_index: int, new_index: int):
        """Handle step change."""
        # Update step container
        self.step_container.setCurrentIndex(new_index)

        # Update progress
        self._update_progress()

        # Update navigation buttons
        self._update_navigation_buttons()

    def _update_progress(self):
        """Update progress indicator."""
        current = self.navigator.current_index + 1
        total = len(self.steps)
        percentage = self.navigator.get_progress_percentage()

        self.progress_label.setText(f"الخطوة {current} من {total}")
        self.progress_bar.setValue(int(percentage))

    def _update_navigation_buttons(self):
        """Update navigation button states."""
        # Previous button
        self.btn_previous.setEnabled(self.navigator.can_go_previous())

        # Next/Finish button
        if self.navigator.current_index == len(self.steps) - 1:
            self.btn_next.setText(self.get_submit_button_text())
        else:
            self.btn_next.setText("التالي")

    def _on_validation_failed(self, result: StepValidationResult):
        """Handle validation failure."""
        errors = "\n".join(f"• {error}" for error in result.errors)
        warnings = "\n".join(f"• {warning}" for warning in result.warnings)

        message = ""
        if errors:
            message += errors
        if warnings:
            if message:
                message += "\n"
            message += warnings

        ErrorHandler.show_warning(
            self,
            message or tr("validation.check_data"),
            tr("dialog.warning")
        )
