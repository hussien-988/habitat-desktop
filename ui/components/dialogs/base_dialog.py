# -*- coding: utf-8 -*-
"""
BaseDialog - Unified dialog component with overlay

Provides a consistent, Figma-spec dialog with:
- Modal overlay (dark transparent background)
- Icon with colored background
- Title and message
- Customizable buttons
- Centered positioning
- Clean animations

Based on Figma design specifications.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsOpacityEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor

from ui.design_system import Colors, ButtonDimensions, DialogColors
from ui.font_utils import create_font
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)


class DialogType:
    """Dialog type constants."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    QUESTION = "question"


class BaseDialog(QWidget):
    """
    Base dialog component with overlay.

    Features:
    - Modal overlay that blocks interaction with parent
    - Centered dialog card
    - Icon with colored background based on type
    - Title and message
    - Customizable buttons
    - Follows Figma design specifications

    Usage:
        dialog = BaseDialog(
            parent=self,
            dialog_type=DialogType.SUCCESS,
            title="نجح",
            message="تم حفظ البيانات بنجاح",
            buttons=[("حسناً", self.on_ok)]
        )
        dialog.show()
    """

    # Signals
    closed = pyqtSignal()  # Emitted when dialog is closed

    def __init__(
        self,
        parent: QWidget,
        dialog_type: str,
        title: str,
        message: str,
        buttons: list = None,
        icon_path: str = None,
        use_overlay: bool = False
    ):
        """
        Initialize base dialog.

        Args:
            parent: Parent widget
            dialog_type: Dialog type (success, error, warning, info, question)
            title: Dialog title
            message: Dialog message
            buttons: List of tuples [(label, callback), ...]
            icon_path: Optional custom icon path (48x48px PNG)
            use_overlay: If True, show dark overlay behind dialog (for input/map dialogs).
                         If False, show dialog card with shadow only (default).
        """
        super().__init__(parent)

        self.dialog_type = dialog_type
        self.title_text = title
        self.message_text = message
        self.buttons_config = buttons or []
        self.icon_path = icon_path
        self.use_overlay = use_overlay
        self.result = None  # Store button result

        if self.use_overlay:
            # Overlay mode: cover entire parent window with dark background
            self.setWindowFlags(
                Qt.Dialog |
                Qt.FramelessWindowHint |
                Qt.CustomizeWindowHint
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_DeleteOnClose)

            if parent:
                main_window = parent.window()
                if main_window:
                    self.setGeometry(main_window.geometry())
                else:
                    self.setGeometry(parent.geometry())
        else:
            # Shadow mode: floating card centered on parent with elegant shadow
            self.setWindowFlags(
                Qt.Dialog |
                Qt.FramelessWindowHint |
                Qt.CustomizeWindowHint |
                Qt.WindowStaysOnTopHint  # Prevent disappearing on window switch
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_DeleteOnClose)
            # Size will be set after UI setup

        # Modal behavior - blocks interaction with parent
        self.setWindowModality(Qt.ApplicationModal)

        # Setup UI
        self._setup_ui()

        # Center on parent for shadow mode (after UI setup so size is known)
        if not self.use_overlay and parent:
            self._center_on_parent()

        # Apply fade-in animation (only in overlay mode)
        # In shadow mode, QGraphicsDropShadowEffect on card conflicts with
        # QGraphicsOpacityEffect on parent → causes QPainter errors
        if self.use_overlay:
            self._animate_show()
        else:
            self.opacity_effect = None  # No opacity effect in shadow mode

    def _setup_ui(self):
        """Setup dialog UI with overlay or shadow mode."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        if self.use_overlay:
            # ========== OVERLAY MODE (Dark Background) ==========
            overlay = QFrame()
            overlay.setObjectName("DialogOverlay")
            overlay.setStyleSheet(f"""
                QFrame#DialogOverlay {{
                    background-color: rgba(45, 45, 45, 0.95);
                }}
            """)
            overlay.mousePressEvent = lambda e: self._handle_overlay_click()

            overlay_layout = QVBoxLayout(overlay)
            overlay_layout.setAlignment(Qt.AlignCenter)

            # Dialog card inside overlay
            self.dialog_card = QFrame()
            self.dialog_card.setObjectName("DialogCard")
            self.dialog_card.setFixedWidth(400)
            self.dialog_card.setStyleSheet(f"""
                QFrame#DialogCard {{
                    background-color: #FFFFFF;
                    border: 1px solid #E1E8ED;
                    border-radius: 12px;
                }}
            """)
            self.dialog_card.mousePressEvent = lambda e: e.accept()
        else:
            # ========== SHADOW MODE (No overlay, elegant shadow) ==========
            # Add padding around card for shadow to render
            main_layout.setContentsMargins(24, 24, 24, 24)

            # Dialog card with shadow - centered as standalone widget
            self.dialog_card = QFrame()
            self.dialog_card.setObjectName("DialogCard")
            self.dialog_card.setFixedWidth(400)
            self.dialog_card.setStyleSheet(f"""
                QFrame#DialogCard {{
                    background-color: #FFFFFF;
                    border: 1px solid #E1E8ED;
                    border-radius: 12px;
                }}
            """)

            # Elegant drop shadow
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            card_shadow = QGraphicsDropShadowEffect()
            card_shadow.setBlurRadius(32)
            card_shadow.setXOffset(0)
            card_shadow.setYOffset(8)
            card_shadow.setColor(QColor(0, 0, 0, 60))
            self.dialog_card.setGraphicsEffect(card_shadow)

        card_layout = QVBoxLayout(self.dialog_card)
        card_layout.setContentsMargins(24, 24, 24, 24)  # 24px padding
        card_layout.setSpacing(0)

        # ========== ICON ==========
        icon_container = self._create_icon()
        card_layout.addWidget(icon_container, alignment=Qt.AlignCenter)

        # Gap after icon
        card_layout.addSpacing(16)  # 16px

        # ========== TITLE ==========
        title_label = QLabel(self.title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)

        # Title font: Bold, 16pt
        title_font = create_font(
            size=16,  # 16pt
            weight=QFont.Bold,
            letter_spacing=0
        )
        title_label.setFont(title_font)
        # Title: Near black color (#1A1A1A)
        title_label.setStyleSheet("color: #1A1A1A; background: transparent;")
        card_layout.addWidget(title_label)

        # Gap after title
        card_layout.addSpacing(8)  # 8px

        # ========== MESSAGE ==========
        message_label = QLabel(self.message_text)
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)

        # Message font: Light weight (300), 11pt (Figma: 14px)
        message_font = create_font(
            size=11,  # 11pt (~14px in Figma)
            weight=QFont.Light,  # Weight 300
            letter_spacing=0
        )
        message_label.setFont(message_font)
        # Details: Gray color
        message_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        card_layout.addWidget(message_label)

        # Gap before buttons
        card_layout.addSpacing(24)  # 24px (from Figma requirement)

        # ========== BUTTONS ==========
        if self.buttons_config:
            buttons_row = self._create_buttons()
            card_layout.addLayout(buttons_row)

        # Add card to appropriate container
        if self.use_overlay:
            overlay_layout.addWidget(self.dialog_card)
            main_layout.addWidget(overlay)
        else:
            main_layout.addWidget(self.dialog_card, alignment=Qt.AlignCenter)

    def _create_icon(self) -> QWidget:
        """
        Create icon with colored circular background.

        Returns:
            QWidget containing the icon
        """
        # Icon container
        icon_widget = QWidget()
        icon_widget.setFixedSize(48, 48)  # 48px from Figma

        # Get colors based on dialog type
        bg_color, icon_color = self._get_icon_colors()

        # Set circular background
        icon_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 24px;
            }}
        """)

        # Icon label
        icon_layout = QVBoxLayout(icon_widget)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)

        # Load icon if provided, otherwise use default symbol
        if self.icon_path:
            pixmap = QPixmap(self.icon_path).scaled(
                32, 32,  # Icon size inside the circle
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
        else:
            # Use text symbol as fallback
            symbol = self._get_icon_symbol()
            icon_label.setText(symbol)
            icon_label.setStyleSheet(f"""
                color: {icon_color};
                font-size: 24pt;
                font-weight: bold;
                background: transparent;
            """)

        icon_layout.addWidget(icon_label)

        return icon_widget

    def _get_icon_colors(self) -> tuple:
        """
        Get background and icon colors based on dialog type.

        Returns:
            Tuple of (background_color, icon_color)
        """
        type_colors = {
            DialogType.SUCCESS: ("#E7F7EF", "#43A047"),  # Light green bg, green icon
            DialogType.ERROR: ("#FFE7E7", "#E53935"),    # Light red bg, red icon
            DialogType.WARNING: ("#FFF4E5", "#FFC72C"),  # Light orange bg, YELLOW icon from Figma
            DialogType.INFO: ("#E3F2FD", "#1E88E5"),     # Light blue bg, blue icon
            DialogType.QUESTION: ("#E3F2FD", "#1E88E5"), # Light blue bg, blue icon
        }

        return type_colors.get(self.dialog_type, ("#E3F2FD", "#1E88E5"))

    def _get_icon_symbol(self) -> str:
        """
        Get default icon symbol based on dialog type.

        Returns:
            Icon symbol string
        """
        symbols = {
            DialogType.SUCCESS: "✓",
            DialogType.ERROR: "✕",
            DialogType.WARNING: "!",
            DialogType.INFO: "i",
            DialogType.QUESTION: "?",
        }

        return symbols.get(self.dialog_type, "i")

    def _get_button_style(self) -> str:
        """
        Get button stylesheet based on dialog type.

        Returns:
            Button stylesheet string
        """
        # Type-specific button colors
        # WARNING: Yellow (#FFC72C) - from Figma
        # ERROR: Red
        # SUCCESS: Green
        # INFO/QUESTION: Blue
        type_button_colors = {
            DialogType.WARNING: ("#FFC72C", "#FFD454"),  # Yellow + lighter yellow hover
            DialogType.ERROR: ("#E53935", "#EF5350"),    # Red + lighter red hover
            DialogType.SUCCESS: ("#43A047", "#66BB6A"),  # Green + lighter green hover
            DialogType.INFO: ("#3890DF", "#2A7BC9"),     # Blue + darker blue hover
            DialogType.QUESTION: ("#3890DF", "#2A7BC9"), # Blue + darker blue hover
        }

        bg_color, hover_color = type_button_colors.get(
            self.dialog_type,
            ("#3890DF", "#2A7BC9")  # Default to blue
        )

        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                font-weight: 300;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
            }}
        """

    def _create_buttons(self) -> QHBoxLayout:
        """
        Create button row (centered).

        Returns:
            QHBoxLayout containing buttons
        """
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)  # 16px gap
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        # Center buttons
        buttons_layout.addStretch()

        for label, callback in self.buttons_config:
            btn = self._create_button(label, callback)
            buttons_layout.addWidget(btn)

        buttons_layout.addStretch()

        return buttons_layout

    def _create_button(self, label: str, callback) -> QPushButton:
        """
        Create styled button.

        Args:
            label: Button text
            callback: Click callback function

        Returns:
            QPushButton with styling
        """
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)

        # Button dimensions
        btn.setFixedHeight(48)  # 48px from Figma
        btn.setMinimumWidth(120)  # 120px minimum from Figma
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        # Button font (weight 300 for consistency)
        btn_font = create_font(
            size=10,  # 10pt (14px Figma)
            weight=QFont.Light,  # Weight 300
            letter_spacing=0
        )
        btn.setFont(btn_font)

        # Apply type-specific button style
        btn.setStyleSheet(self._get_button_style())

        # Connect callback
        def on_click():
            self.result = label  # Store which button was clicked
            if callback:
                callback()
            self.close_dialog()

        btn.clicked.connect(on_click)

        return btn

    def _animate_show(self):
        """Animate dialog appearance with fade-in effect."""
        # Start transparent
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0)

        # Animate to opaque
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(200)  # 200ms
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()

    def _center_on_parent(self):
        """Center dialog on parent window (for shadow mode)."""
        parent = self.parent()
        if not parent:
            return
        main_window = parent.window()
        target = main_window if main_window else parent

        # Ensure dialog has computed its size
        self.adjustSize()

        # Map parent center to global coordinates
        parent_rect = target.geometry()
        cx = parent_rect.x() + (parent_rect.width() - self.width()) // 2
        cy = parent_rect.y() + (parent_rect.height() - self.height()) // 2
        self.move(cx, cy)

    def showEvent(self, event):
        """Handle show event - update geometry for correct positioning."""
        super().showEvent(event)
        if self.parent():
            if self.use_overlay:
                main_window = self.parent().window()
                if main_window:
                    self.setGeometry(main_window.geometry())
                else:
                    self.setGeometry(self.parent().geometry())
            else:
                self._center_on_parent()

    def _handle_overlay_click(self):
        """Handle click on overlay (outside dialog card)."""
        # Optional: Close dialog when clicking outside
        # Uncomment the following line if you want this behavior:
        # self.close_dialog()
        pass

    def close_dialog(self):
        """Close dialog with fade-out animation (overlay) or immediate close (shadow)."""
        if self.opacity_effect:
            # Overlay mode: animate fade-out
            self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.animation.setDuration(150)  # 150ms
            self.animation.setStartValue(1)
            self.animation.setEndValue(0)
            self.animation.setEasingCurve(QEasingCurve.InCubic)
            self.animation.finished.connect(self.close)
            self.animation.start()
        else:
            # Shadow mode: close immediately (no opacity effect)
            self.close()

        # Emit closed signal
        self.closed.emit()

    def closeEvent(self, event):
        """Handle close event."""
        self.closed.emit()
        super().closeEvent(event)
