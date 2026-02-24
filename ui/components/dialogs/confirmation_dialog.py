# -*- coding: utf-8 -*-
"""
Confirmation Dialog Component - مكون حوار التأكيد

Reusable confirmation dialog following DRY and SOLID principles.

Features:
- Warning/Info/Question icons
- Customizable title and message
- Multiple button configurations
- RTL support for Arabic
- Follows Figma design system

Usage:
    # Simple yes/no confirmation
    result = ConfirmationDialog.confirm(
        parent=self,
        title="تأكيد",
        message="هل أنت متأكد؟"
    )
    if result == ConfirmationDialog.YES:
        # User clicked yes
        pass

    # Save draft confirmation
    result = ConfirmationDialog.save_draft_confirmation(
        parent=self,
        title="هل تريد الحفظ؟",
        message="لديك تغييرات غير محفوظة. هل تريد حفظها كمسودة؟"
    )
    if result == ConfirmationDialog.SAVE:
        # Save as draft
        pass
    elif result == ConfirmationDialog.DISCARD:
        # Discard changes
        pass
    # else: Cancel (do nothing)
"""

from enum import IntEnum
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QSpacerItem, QSizePolicy,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap, QColor

from ..icon import Icon
from ...design_system import Colors, ButtonDimensions
from ...font_utils import create_font, FontManager
from typing import Optional


class DialogResult(IntEnum):
    """Dialog result codes."""
    CANCEL = 0
    YES = 1
    NO = 2
    SAVE = 3
    DISCARD = 4


class ConfirmationDialog(QDialog):
    """
    Reusable confirmation dialog.

    Single Responsibility: Display confirmation dialogs with icons and buttons
    Open/Closed: Easily extended via static factory methods
    Liskov Substitution: Inherits cleanly from QDialog
    Interface Segregation: Minimal interface (show + result)
    Dependency Inversion: Uses abstract Icon component
    """

    # Result constants for easy access
    CANCEL = DialogResult.CANCEL
    YES = DialogResult.YES
    NO = DialogResult.NO
    SAVE = DialogResult.SAVE
    DISCARD = DialogResult.DISCARD

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "تأكيد",
        message: str = "",
        icon_name: str = "wirning",  # warning icon (typo preserved from assets)
        buttons: list = None,
        default_button: int = 0
    ):
        """
        Initialize confirmation dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: Message to display
            icon_name: Icon file name (yellow warning by default)
            buttons: List of (text, result_code) tuples
            default_button: Index of default button
        """
        super().__init__(parent)

        self.result_code = DialogResult.CANCEL
        self.buttons_config = buttons or [
            ("نعم", DialogResult.YES),
            ("لا", DialogResult.NO)
        ]
        self.default_button_index = default_button

        # Dialog setup (Figma dimensions)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(400)  # Fixed width for consistent appearance

        # Frameless window with transparent background for rounded corners
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Setup UI
        self._setup_ui(title, message, icon_name)

    def _setup_ui(self, title: str, message: str, icon_name: str):
        """
        Setup dialog UI matching Figma design EXACTLY.

        Figma specifications:
        - Row 1: Icon (centered)
        - Row 2: Title (centered)
        - Row 3: Subtitle/Message (centered)
        - Row 4: Buttons (170×50, border-radius 8)
        - Layout: Vertical (not horizontal)
        """
        # Create container widget for white background with rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        container.setStyleSheet("""
            QWidget#dialogContainer {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E5E7EB;
            }
            QWidget#dialogContainer QLabel {
                border: none;
                background: transparent;
            }
        """)

        # Main dialog layout - margins give shadow room to render
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(24, 24, 24, 24)
        dialog_layout.addWidget(container)

        # Container layout (content)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)  # Spacing between rows

        # Row 1: Icon (centered)
        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        icon = Icon(icon_name, size=64, fallback_text="⚠️")  # Larger icon as in Figma
        icon.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon)
        icon_layout.addStretch()
        main_layout.addLayout(icon_layout)

        # Row 2: Title (centered)
        title_label = QLabel(title)
        title_font = create_font(
            size=16,  # 16pt for dialog title
            weight=QFont.Bold
        )
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        main_layout.addWidget(title_label)

        # Row 3: Subtitle/Message (centered)
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        # Figma: 10pt font for subtitle
        message_font = create_font(
            size=10,  # 10pt from Figma
            weight=QFont.Normal
        )
        message_label.setFont(message_font)
        message_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        message_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(message_label)

        # Row 4: Buttons area (centered)
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(16, 0, 16, 0)
        buttons_layout.setSpacing(12)
        buttons_layout.addStretch()

        # Create buttons from configuration (Figma: 170×50)
        self.button_widgets = []
        for index, (button_text, result_code) in enumerate(self.buttons_config):
            btn = self._create_button(
                text=button_text,
                result_code=result_code,
                is_primary=(index == self.default_button_index)
            )
            self.button_widgets.append(btn)
            buttons_layout.addWidget(btn)

        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)

        # Add shadow effect to container for depth
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 80))
        container.setGraphicsEffect(shadow)

    def _create_button(
        self,
        text: str,
        result_code: int,
        is_primary: bool = False
    ) -> QPushButton:
        """
        Create styled button matching Figma design EXACTLY.

        Figma specifications:
        - Size: 170×50 (width × height)
        - Border radius: 8px
        - Primary (Save): Yellow (#F9C74F) + white text
        - Secondary (Discard): White + shadow + gray text
        - Font: 10pt

        Args:
            text: Button text
            result_code: Result code when clicked
            is_primary: Whether this is the primary button

        Returns:
            Styled QPushButton
        """
        btn = QPushButton(text)

        btn.setFixedSize(150, 48)
        btn.setCursor(Qt.PointingHandCursor)

        # Figma: Font 10pt
        btn_font = create_font(
            size=10,  # 10pt from Figma
            weight=QFont.Medium
        )
        btn.setFont(btn_font)

        # Style based on button type
        if is_primary:
            # Primary button: Yellow background + white text (Save as draft)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #F9C74F;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: #F8BD3B;
                }}
                QPushButton:pressed {{
                    background-color: #E6A82D;
                }}
            """)
        else:
            # Secondary button: White + shadow + gray text (Discard)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: white;
                    color: #6B7280;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: #F9FAFB;
                }}
                QPushButton:pressed {{
                    background-color: #F3F4F6;
                }}
            """)

            # Add shadow to secondary button (Figma design)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(8)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 25))  # 10% opacity
            btn.setGraphicsEffect(shadow)

        # Connect click to result
        btn.clicked.connect(lambda: self._handle_button_click(result_code))

        return btn

    def _handle_button_click(self, result_code: int):
        """Handle button click and close dialog with result."""
        self.result_code = result_code
        self.accept() if result_code != DialogResult.CANCEL else self.reject()

    def get_result(self) -> int:
        """Get dialog result code."""
        return self.result_code

    # =========================================================================
    # Static Factory Methods (following Factory Pattern for DRY)
    # =========================================================================

    @staticmethod
    def confirm(
        parent: Optional[QWidget] = None,
        title: str = "تأكيد",
        message: str = "هل أنت متأكد؟",
        icon_name: str = "wirning"
    ) -> int:
        """
        Show simple yes/no confirmation dialog.

        Returns:
            DialogResult.YES or DialogResult.NO or DialogResult.CANCEL
        """
        dialog = ConfirmationDialog(
            parent=parent,
            title=title,
            message=message,
            icon_name=icon_name,
            buttons=[
                ("لا", DialogResult.NO),
                ("نعم", DialogResult.YES)
            ],
            default_button=1  # Yes is default
        )
        dialog.exec_()
        return dialog.get_result()

    @staticmethod
    def save_draft_confirmation(
        parent: Optional[QWidget] = None,
        title: str = "هل تريد الحفظ؟",
        message: str = "لديك تغييرات غير محفوظة.\nهل تريد حفظها كمسودة؟"
    ) -> int:
        """
        Show save draft confirmation dialog (UC-001 S28, UC-004 S22).

        This matches the Figma design shown in the screenshot EXACTLY:
        - Icon: wirning.png (warning icon with yellow)
        - Layout: Icon → Title → Subtitle → Buttons
        - Buttons: "عدم الحفظ" (white) | "حفظ كمسودة" (yellow)
        - Button size: 170×50, border-radius: 8px

        Returns:
            DialogResult.SAVE - Save as draft (yellow button)
            DialogResult.DISCARD - Don't save (white button)
            DialogResult.CANCEL - Cancel (X or Esc)
        """
        dialog = ConfirmationDialog(
            parent=parent,
            title=title,
            message=message,
            icon_name="wirning",  # wirning.png from Figma (typo preserved)
            buttons=[
                ("عدم الحفظ", DialogResult.DISCARD),  # White button (secondary)
                ("حفظ كمسودة", DialogResult.SAVE)      # Yellow button (primary)
            ],
            default_button=1  # Save is default (yellow button)
        )
        dialog.exec_()
        return dialog.get_result()

    @staticmethod
    def warning(
        parent: Optional[QWidget] = None,
        title: str = "تحذير",
        message: str = "",
        icon_name: str = "wirning"
    ) -> int:
        """
        Show warning dialog with OK button.

        Returns:
            DialogResult.YES (OK was clicked)
        """
        dialog = ConfirmationDialog(
            parent=parent,
            title=title,
            message=message,
            icon_name=icon_name,
            buttons=[
                ("حسناً", DialogResult.YES)
            ],
            default_button=0
        )
        dialog.exec_()
        return dialog.get_result()
