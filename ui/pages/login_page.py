# -*- coding: utf-8 -*-
"""
Login Page - Based on Figma Design Reference
Exact implementation matching the provided screenshot
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPaintEvent, QFont, QFontDatabase, QPixmap
import os

from app.config import Config
from repositories.database import Database
from services.auth_service import AuthService
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class LoginPage(QWidget):
    """Login page exactly matching the reference screenshot."""

    login_successful = pyqtSignal(object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.auth_service = AuthService(db)
        self.password_visible = False

        # Load custom fonts
        self._load_fonts()
        self._setup_ui()

    def _load_fonts(self):
        """Load Noto Kufi Arabic fonts"""
        fonts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts", "Noto_Kufi_Arabic")
        font_files = [
            "NotoKufiArabic-Regular.ttf",
            "NotoKufiArabic-Bold.ttf",
            "NotoKufiArabic-SemiBold.ttf",
            "NotoKufiArabic-Medium.ttf"
        ]

        for font_file in font_files:
            font_path = os.path.join(fonts_dir, font_file)
            if os.path.exists(font_path):
                QFontDatabase.addApplicationFont(font_path)

    def paintEvent(self, event: QPaintEvent):
        """Paint two-tone background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        mid_height = height // 2

        # Top half - blue (#3890DF based on reference)
        painter.fillRect(0, 0, width, mid_height, QColor("#3890DF"))

        # Bottom half - very light blue-gray (#F0F4F8 based on reference)
        painter.fillRect(0, mid_height, width, height - mid_height, QColor("#F0F4F8"))

    def _setup_ui(self):
        """Setup the login UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create login card
        card = self._create_login_card()
        main_layout.addWidget(card)

    def _create_login_card(self) -> QFrame:
        """Create the white login card matching reference design"""
        card = QFrame()
        card.setObjectName("login_card")
        card.setFixedSize(420, 520)  # Adjusted card size
        card.setStyleSheet("""
            QFrame#login_card {
                background-color: white;
                border-radius: 12px;
            }
        """)

        # Subtle shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(150, 150, 150, 40))
        shadow.setOffset(0, 3)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(32, 32, 32, 32)

        # Logo area with UN-HABITAT image
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedHeight(80)

        # Try to load the logo image
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, "..", "..", "assets", "images", "un-logo.jpg")
        logo_path = os.path.normpath(logo_path)

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)

        # If no image, show text
        if logo_label.pixmap() is None or logo_label.pixmap().isNull():
            logo_label.setText("UN-HABITAT")
            logo_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent;")

        card_layout.addWidget(logo_label)
        card_layout.addSpacing(20)

        # Title
        title = QLabel("تسجيل الدخول إلى الحساب")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Noto Kufi Arabic", 11, QFont.Bold))
        title.setStyleSheet("color: #2C3E50; background: transparent;")
        card_layout.addWidget(title)

        card_layout.addSpacing(6)

        # Subtitle
        subtitle = QLabel("يرجى إدخال بيانات الدخول للمتابعة واستخدام النظام")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont("Noto Kufi Arabic", 8))
        subtitle.setStyleSheet("color: #7F8C9B; background: transparent;")
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(24)

        # Username label
        username_label = QLabel("اسم المستخدم")
        username_label.setFont(QFont("Noto Kufi Arabic", 11, QFont.DemiBold))
        username_label.setStyleSheet("color: #2C3E50; background: transparent;")
        card_layout.addWidget(username_label)

        card_layout.addSpacing(6)

        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("أدخل اسم المستخدم")
        self.username_input.setLayoutDirection(Qt.RightToLeft)
        self.username_input.setFixedHeight(42)
        self.username_input.setFont(QFont("Noto Kufi Arabic", 11))
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #D5DBDB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #2C3E50;
            }
            QLineEdit:focus {
                border: 1px solid #3890DF;
                outline: none;
            }
            QLineEdit::placeholder {
                color: #BDC3C7;
            }
        """)
        self.username_input.textChanged.connect(self._hide_error)
        card_layout.addWidget(self.username_input)

        card_layout.addSpacing(14)

        # Password label
        password_label = QLabel("كلمة المرور")
        password_label.setFont(QFont("Noto Kufi Arabic", 11, QFont.DemiBold))
        password_label.setStyleSheet("color: #2C3E50; background: transparent;")
        card_layout.addWidget(password_label)

        card_layout.addSpacing(6)

        # Password input with eye icon
        password_container = QFrame()
        password_container.setFixedHeight(42)
        password_container.setStyleSheet("background: transparent; border: none;")

        self.password_input = QLineEdit(password_container)
        self.password_input.setPlaceholderText("أدخل كلمة المرور")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setLayoutDirection(Qt.RightToLeft)
        self.password_input.setFixedHeight(42)
        self.password_input.setFont(QFont("Noto Kufi Arabic", 11))

        # Calculate width to match username input (full width)
        card_width = 420 - 64  # card width minus left/right margins (32 each)
        self.password_input.setGeometry(0, 0, card_width, 42)

        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #D5DBDB;
                border-radius: 6px;
                padding-right: 40px;
                padding-left: 12px;
                padding-top: 8px;
                padding-bottom: 8px;
                color: #2C3E50;
            }
            QLineEdit:focus {
                border: 1px solid #3890DF;
                outline: none;
            }
            QLineEdit::placeholder {
                color: #BDC3C7;
            }
        """)
        self.password_input.textChanged.connect(self._hide_error)
        self.password_input.returnPressed.connect(self._on_login)

        # Eye icon positioned on the left for RTL
        self.toggle_password_btn = QPushButton("👁", password_container)
        self.toggle_password_btn.setGeometry(8, 7, 28, 28)
        self.toggle_password_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_password_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                color: #95A5A6;
            }
            QPushButton:hover {
                color: #3890DF;
            }
        """)
        self.toggle_password_btn.clicked.connect(self._toggle_password_visibility)

        card_layout.addWidget(password_container)

        card_layout.addSpacing(20)

        # Error message
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("""
            background-color: #FADBD8;
            color: #E74C3C;
            font-size: 10px;
            padding: 8px 10px;
            border-radius: 4px;
            border: 1px solid #E74C3C;
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        # Login button
        self.login_btn = QPushButton("تسجيل دخول")
        self.login_btn.setFixedHeight(40)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setFont(QFont("Noto Kufi Arabic", 12, QFont.Bold))
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2A7BC9;
            }
            QPushButton:pressed {
                background-color: #1F68B3;
            }
        """)
        self.login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self.login_btn)

        card_layout.addSpacing(12)

        # Version
        version_label = QLabel("v 1.4")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #BDC3C7; font-size: 9px; background: transparent;")
        card_layout.addWidget(version_label)

        return card

    def _toggle_password_visibility(self):
        """Toggle password visibility"""
        self.password_visible = not self.password_visible
        if self.password_visible:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def _on_login(self):
        """Handle login attempt"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error("يرجى إدخال اسم المستخدم وكلمة المرور")
            return

        user, error = self.auth_service.authenticate(username, password)

        if user:
            logger.info(f"Login successful: {username}")
            self.error_label.hide()
            self._clear_form()
            self.login_successful.emit(user)
        else:
            logger.warning(f"Login failed: {username}")
            self._show_error("اسم المستخدم أو كلمة المرور غير صحيحة")

    def _show_error(self, message: str):
        """Show error message"""
        self.error_label.setText(message)
        self.error_label.show()

    def _hide_error(self):
        """Hide error message"""
        if self.error_label.isVisible():
            self.error_label.hide()

    def _clear_form(self):
        """Clear form fields"""
        self.username_input.clear()
        self.password_input.clear()
        self.error_label.hide()

    def refresh(self, data=None):
        """Refresh the page"""
        self._clear_form()
        self.username_input.setFocus()

    def update_language(self, is_arabic: bool):
        """Update language"""
        pass
