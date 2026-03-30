# -*- coding: utf-8 -*-
"""Login page."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QColor, QPainter, QPaintEvent, QFont, QFontDatabase, QPixmap
from PyQt5.QtGui import QCursor, QIcon
import os
import re
from app.config import Config
from services.api_auth_service import ApiAuthService
from services.translation_manager import tr, get_layout_direction, set_language as tm_set_language, get_language as tm_get_language
from app.config import save_language
from utils.i18n import I18n
from utils.logger import get_logger
from ui.font_utils import create_font, FontManager
from ui.design_system import Colors

logger = get_logger(__name__)


class LoginPage(QWidget):
    """Login page exactly matching the reference screenshot."""

    login_successful = pyqtSignal(object)

    def __init__(self, i18n: I18n, db=None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.db = db
        self.auth_service = ApiAuthService()
        self.password_visible = False
        self._arabic_re = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

        # Login lockout tracking
        self._failed_attempts = 0
        self._lockout_until = None

        # Load custom fonts
        self._load_fonts()
        self._setup_ui()
        self._setup_login_watermark()
        self._position_login_watermark()
        self._setup_login_navbar()


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
        """Paint background with blue section."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Blue section height (~55% of window)
        blue_height = int(height * 0.55)

        # Top section - Primary blue
        painter.fillRect(0, 33, width, blue_height, QColor(Colors.PRIMARY_BLUE))

        # Bottom section - Background color #F0F7FF
        painter.fillRect(0, 33 + blue_height, width, height - (33 + blue_height), QColor(Colors.BACKGROUND))

    def _setup_ui(self):
        """Setup the login UI."""
        # Set background color for the entire page
        self.setStyleSheet(f"""
            QWidget#LoginPage {{
                background-color: {Colors.BACKGROUND};
            }}
        """)
        self.setObjectName("LoginPage")

        # Main layout with NO margins (full screen)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Stack layers from bottom to top:
        # 1. Background is set via stylesheet above
        # 2. Blue section (will be created by paintEvent)
        # 3. Login card (centered)

        # Create container for login card (centered)
        card_container = QWidget()
        card_container.setStyleSheet("background: transparent;")
        card_container_layout = QVBoxLayout(card_container)
        card_container_layout.setAlignment(Qt.AlignCenter)
        card_container_layout.setContentsMargins(0, 0, 0, 0)

        # Create login card
        self.login_card = self._create_login_card()
        card_container_layout.addWidget(self.login_card)

        # Add card container to main layout
        main_layout.addWidget(card_container)
    def _setup_login_watermark(self):
        self.bg_logo = QLabel(self)
        self.bg_logo.setObjectName("login_bg_logo")
        self.bg_logo.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.bg_logo.setStyleSheet("background: transparent;")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, "..", "..", "assets", "images", "login-watermark.png")
        logo_path = os.path.normpath(logo_path)

        pix = QPixmap(logo_path)
        if pix.isNull():
            return

        self._bg_logo_src = pix

        # شفافية خفيفة
        eff = QGraphicsOpacityEffect(self.bg_logo)
        eff.setOpacity(0.8)
        self.bg_logo.setGraphicsEffect(eff)

        # خليه ورا الكارد
        self.bg_logo.lower()
        if hasattr(self, "login_card"):
            self.login_card.raise_()
    def _position_login_watermark(self):
        if not hasattr(self, "bg_logo") or not hasattr(self, "_bg_logo_src"):
            return

        target_w = 657
        target_h = 515

        pix = self._bg_logo_src.scaled(
            target_w, target_h,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )

        self.bg_logo.setPixmap(pix)
        self.bg_logo.resize(pix.size())

        # Position watermark
        x = 427
        y = 65
        self.bg_logo.move(x, y)

        # ترتيب الطبقات: الشعار تحت، الكارد فوق، وبعدين أزرار اللوجين إذا عندك titlebar
        self.bg_logo.lower()
        if hasattr(self, "login_card"):
            self.login_card.raise_()
        if hasattr(self, "titlebar"):
            self.titlebar.raise_()


    def _create_login_card(self) -> QFrame:
        """Create the white login card."""
        card = QFrame()
        card.setObjectName("login_card")
        # Card size
        card.setFixedWidth(475)
        card.setFixedHeight(538)
        card.setStyleSheet("""
            QFrame#login_card {
                background-color: white;
                border-radius: 24px;
                
            }
        """)

        # Subtle shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(150, 150, 150, 40))
        shadow.setOffset(0, 3)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(24)
        card_layout.setContentsMargins(32, 32, 32, 32)

        # Login Card Top Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(92, 90)
        logo_label.setStyleSheet("background: transparent;")

        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Try to load Layer_1.png logo
        logo_path = os.path.join(current_dir, "..", "..", "assets", "images", "Layer_1.png")
        logo_path = os.path.normpath(logo_path)

        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            # Scale logo
            logo_label.setPixmap(pixmap.scaled(95, 90, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("UN-HABITAT")
            logo_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent;")

        card_layout.addWidget(logo_label, 0, Qt.AlignCenter)

        # Title
        self._title_label = QLabel(tr("page.login.title"))
        title = self._title_label
        title.setAlignment(Qt.AlignCenter)
        title.setMaximumWidth(315)
        title_font = create_font(size=FontManager.SIZE_HEADING, weight=QFont.Bold, letter_spacing=0)
        title.setFont(title_font)
        title.setStyleSheet("color: #172A47; background: transparent;")
        card_layout.addWidget(title,0, Qt.AlignCenter)

        card_layout.addSpacing(-20)

        # Subtitle
        self._subtitle_label = QLabel(tr("page.login.subtitle"))
        subtitle = self._subtitle_label
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(False)  # Single line only
        subtitle.setMinimumWidth(315)  # Ensure minimum width for single line
        subtitle_font = create_font(size=FontManager.SIZE_BODY, weight=QFont.DemiBold, letter_spacing=0)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #86909B; background: transparent;")
        card_layout.addWidget(subtitle,0, Qt.AlignCenter)

        # Reduce gap before form fields
        card_layout.addSpacing(16)

        # Username label
        self._username_label = QLabel(tr("page.login.username"))
        username_label = self._username_label
        username_label_font = create_font(size=10, weight=QFont.DemiBold, letter_spacing=0)
        username_label.setFont(username_label_font)
        username_label.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(username_label)
        card_layout.addSpacing(-20)  # Reduce gap between label and input (tighter)


        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(tr("page.login.username_placeholder"))
        self.username_input.setLayoutDirection(get_layout_direction())
        self.username_input.setFixedHeight(40)
        username_input_font = create_font(size=10, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0)
        self.username_input.setFont(username_input_font)
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFF;
                border: 1px solid #E5EAF6;
                border-radius: 8px;
                padding: 0 4px;
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

        # Reduce gap between username input and password label
        card_layout.addSpacing(-12)

        # Password label
        self._password_label = QLabel(tr("page.login.password"))
        password_label = self._password_label
        password_label_font = create_font(size=10, weight=QFont.DemiBold, letter_spacing=0)
        password_label.setFont(password_label_font)
        password_label.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(password_label)
        card_layout.addSpacing(-20)  # Reduce gap between label and input (tighter)

        # Password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(tr("page.login.password_placeholder"))
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)
        password_input_font = create_font(size=10, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0)
        self.password_input.setFont(password_input_font)


        '''self.password_input.setLayoutDirection(Qt.RightToLeft)
        self.password_input.setAlignment(Qt.AlignRight)'''

 
        current_dir = os.path.dirname(os.path.abspath(__file__))
        eye_path = os.path.join(current_dir, "..", "..", "assets", "images", "Eye.png")
        eye_path = os.path.normpath(eye_path)

        eye_icon = QIcon(eye_path)
        self.eye_action = self.password_input.addAction(eye_icon, QLineEdit.TrailingPosition)
        
        self.eye_action.triggered.connect(self._toggle_password_visibility)


        self._apply_password_style(icon_on_left=True)
        self.password_input.textChanged.connect(self._on_password_text_changed)
        self.password_input.returnPressed.connect(self._on_login)

        card_layout.addWidget(self.password_input)


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
        card_layout.addSpacing(16)
        # Login button
        self.login_btn = QPushButton(tr("page.login.sign_in"))
        self.login_btn.setFixedHeight(48)
        self.login_btn.setFixedWidth(411)  # Card width (475) - Padding (32×2) = 411
        self.login_btn.setCursor(Qt.PointingHandCursor)
        button_font = create_font(size=12, weight=QFont.Bold, letter_spacing=0)
        self.login_btn.setFont(button_font)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 8px;
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


        return card

    def set_data_mode(self, mode: str, db=None):
        """Set auth service (always API)."""
        self.auth_service = ApiAuthService()
        logger.info("Login: using API auth")

    def _toggle_password_visibility(self):
        """Toggle password visibility"""
        self.password_visible = not self.password_visible
        if self.password_visible:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def _on_login(self):
        """Handle login attempt with lockout enforcement."""
        from datetime import datetime, timedelta

        # Check lockout
        if self._lockout_until and datetime.now() < self._lockout_until:
            remaining = int((self._lockout_until - datetime.now()).total_seconds()) // 60 + 1
            self._show_error(tr("page.login.account_locked", minutes=remaining))
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error(tr("page.login.fields_required"))
            return

        self._set_login_loading(True)

        from services.api_worker import ApiWorker
        worker = ApiWorker(self.auth_service.authenticate, username, password)
        worker.finished.connect(lambda result: self._on_login_result(result, username))
        worker.start()
        self._login_worker = worker

    def _on_login_result(self, result, username):
        """Handle login result from async worker."""
        from datetime import datetime, timedelta
        self._set_login_loading(False)

        if isinstance(result, Exception):
            self._show_error(tr("page.login.connection_error"))
            return

        user, error = result

        if user:
            from app.config import Roles
            if user.role in Roles.NON_LOGIN_ROLES:
                self._show_error(tr("page.login.not_authorized"))
                return

            self._failed_attempts = 0
            self._lockout_until = None
            logger.info(f"Login successful: {username}")
            self.error_label.hide()
            self.login_successful.emit(user)
        else:
            self._failed_attempts += 1
            logger.warning(f"Login failed: {username} (attempt {self._failed_attempts})")

            max_attempts, lockout_minutes = self._get_lockout_settings()
            if max_attempts > 0 and self._failed_attempts >= max_attempts:
                self._lockout_until = datetime.now() + timedelta(minutes=lockout_minutes)
                self._show_error(tr("page.login.lockout_exceeded", minutes=lockout_minutes))
                logger.warning(f"Account locked for {lockout_minutes} min after {self._failed_attempts} failed attempts")
            else:
                remaining = max_attempts - self._failed_attempts
                if max_attempts > 0 and remaining <= 3:
                    self._show_error(tr("page.login.invalid_credentials_remaining", remaining=remaining))
                else:
                    self._show_error(tr("page.login.invalid_credentials"))

    def _set_login_loading(self, loading: bool):
        """Toggle login button loading state."""
        self.login_btn.setEnabled(not loading)
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)
        if loading:
            self._original_btn_text = self.login_btn.text()
            self.login_btn.setText(tr("page.login.signing_in"))
        else:
            self.login_btn.setText(getattr(self, '_original_btn_text', tr("page.login.sign_in")))

    def _get_lockout_settings(self) -> tuple:
        """Get lockout settings from SecurityService. Returns (max_attempts, lockout_minutes)."""
        try:
            from services.security_service import SecurityService
            if self.db:
                svc = SecurityService(self.db)
            else:
                from repositories.database import Database
                svc = SecurityService(Database())
            settings = svc.get_settings()
            return settings.max_failed_login_attempts, settings.account_lockout_duration_minutes
        except Exception as e:
            logger.warning(f"Could not load lockout settings: {e}")
            return 5, 15

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
        """Update language."""
        self.setLayoutDirection(get_layout_direction())
        self._title_label.setText(tr("page.login.title"))
        self._subtitle_label.setText(tr("page.login.subtitle"))
        self._username_label.setText(tr("page.login.username"))
        self.username_input.setPlaceholderText(tr("page.login.username_placeholder"))
        self._password_label.setText(tr("page.login.password"))
        self.password_input.setPlaceholderText(tr("page.login.password_placeholder"))
        self.login_btn.setText(tr("page.login.sign_in"))
        if hasattr(self, "_lang_btn"):
            self._update_lang_button()

    def _setup_login_navbar(self):
        """Setup navbar title bar for login page."""
        from ui.components.navbar import DraggableFrame

        # Create title bar
        self.titlebar = DraggableFrame(self)
        self.titlebar.setLayoutDirection(Qt.LeftToRight)
        self.titlebar.setFixedHeight(33)
        self.titlebar.setObjectName("login_titlebar")
        self.titlebar.setStyleSheet("""
            QFrame#login_titlebar {
                background: white;
                border-bottom: 1px solid #E5E7EB;
            }
            QPushButton#win_btn, QPushButton#win_close {
                color: #374151;
                background: transparent;
                border: none;
                font-family: 'Segoe Fluent Icons', 'Segoe MDL2 Assets';
                font-size: 14px;
                font-weight: 400;
                line-height: 16px;
                border-radius: 6px;
            }
            QPushButton#win_btn:hover {
                background: rgba(0,0,0,0.05);
            }
            QPushButton#win_btn:pressed {
                background: rgba(0,0,0,0.1);
            }
            QPushButton#win_close:hover {
                background: rgba(255, 59, 48, 0.90);
                color: white;
            }
            QPushButton#win_close:pressed {
                background: rgba(255, 59, 48, 0.75);
                color: white;
            }
        """)

        lay = QHBoxLayout(self.titlebar)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(0)

        # Logo image
        logo_label = QLabel()
        logo_label.setStyleSheet("background: transparent;")
        logo_label.setFixedSize(143, 22)

        logo_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "assets", "images", "header.png"
        )
        logo_path = os.path.normpath(logo_path)

        logo_pixmap = QPixmap(logo_path)
        if not logo_pixmap.isNull():
            # Scale logo
            scaled_logo = logo_pixmap.scaled(
                143, 22, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(scaled_logo)
        else:
            # Fallback to text if image not found
            logo_label.setText("UN-HABITAT")
            logo_label.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            logo_label.setStyleSheet("color: #0072BC; background: transparent;")

        lay.addWidget(logo_label)

        lay.addStretch(1)

        # Window control buttons
        btn_min = QPushButton("\u2013")
        btn_max = QPushButton("□")
        btn_close = QPushButton("✕")

        # Make maximize button icon 2x larger
        btn_max.setStyleSheet("""
            QPushButton {
                font-size: 28px;
                margin-bottom: 4px;
            }
        """)

        btn_min.setObjectName("win_btn")
        btn_max.setObjectName("win_btn")
        btn_close.setObjectName("win_close")

        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(46, 32)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setFocusPolicy(Qt.NoFocus)

        btn_min.clicked.connect(lambda: self.window().showMinimized())
        # Maximize button DISABLED (not functional)
        # btn_max.clicked.connect(...)  # Intentionally disabled
        btn_close.clicked.connect(lambda: self.window().close())

        lay.addWidget(btn_min)
        lay.addWidget(btn_max)
        lay.addWidget(btn_close)

        # Keep on top
        self.titlebar.raise_()

        # Settings button — floating on the blue area (top-left)
        self._btn_settings = QPushButton("\u2699", self)
        self._btn_settings.setFixedSize(42, 42)
        self._btn_settings.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_settings.setFocusPolicy(Qt.NoFocus)
        self._btn_settings.setToolTip(tr("page.login.settings_tooltip"))
        self._btn_settings.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                color: rgba(255, 255, 255, 0.55);
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                color: rgba(255, 255, 255, 0.85);
            }
            QPushButton:pressed {
                color: white;
            }
        """)
        self._btn_settings.clicked.connect(self._open_server_settings)
        self._btn_settings.move(20, 45)
        self._btn_settings.raise_()

        # Language toggle button — floating on the blue area
        self._lang_btn = QPushButton(self)
        self._lang_btn.setFixedSize(80, 32)
        self._lang_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._lang_btn.setFocusPolicy(Qt.NoFocus)
        self._lang_btn.setStyleSheet("""
            QPushButton {
                color: white;
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 16px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.25);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)
        self._lang_btn.clicked.connect(self._toggle_language)
        self._update_lang_button()
        self._lang_btn.move(70, 50)
        self._lang_btn.raise_()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "titlebar") and self.titlebar:
            self.titlebar.setGeometry(0, 0, self.width(), 33)
            self.titlebar.raise_()
        if hasattr(self, "_btn_settings"):
            self._btn_settings.raise_()
        if hasattr(self, "_lang_btn"):
            self._lang_btn.raise_()
        self._position_login_watermark()

    def _open_server_settings(self):
        """Open the server settings dialog."""
        from ui.components.dialogs.server_settings_dialog import ServerSettingsDialog
        ServerSettingsDialog.show_settings(parent=self)

    def _toggle_language(self):
        """Toggle between Arabic and English."""
        current = tm_get_language()
        new_lang = "en" if current == "ar" else "ar"
        tm_set_language(new_lang)
        save_language(new_lang)
        is_arabic = (new_lang == "ar")
        self.update_language(is_arabic)

    def _update_lang_button(self):
        """Update language button text based on current language."""
        current = tm_get_language()
        self._lang_btn.setText("English" if current == "ar" else "عربي")

    def _apply_password_style(self, icon_on_left: bool):
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFF;
                border: 1px solid #E5EAF6;
                border-radius: 8px;
                padding: 0 4px;
                color: #2C3E50;
            }}
            QLineEdit:focus {{
                border: 1px solid #3890DF;
                outline: none;
            }}
            QLineEdit::placeholder {{
                color: #BDC3C7;
            }}
            QLineEdit QToolButton {{
                border: none;
                background: transparent;
                padding: 0px 6px;
            }}
            QLineEdit QToolButton:hover {{
                background: rgba(56,144,223,0.12);
                border-radius: 8px;
            }}
        """)

    def _on_password_text_changed(self, text):
    # فاضي أو فيه عربي => RTL (placeholder يمين) + مسافة لليسار بسبب العين
        if (not text.strip()) or self._arabic_re.search(text):
            self.password_input.setLayoutDirection(Qt.RightToLeft)
            self.password_input.setAlignment(Qt.AlignRight)
            self.password_input.setTextMargins(44, 0, 12, 0)  # مساحة للأيقونة

    # غير هيك (إنجليزي/أرقام) => LTR + مسافة لليمين بسبب العين
        else:
            self.password_input.setLayoutDirection(Qt.LeftToRight)
            self.password_input.setAlignment(Qt.AlignLeft)
            self.password_input.setTextMargins(12, 0, 44, 0)


