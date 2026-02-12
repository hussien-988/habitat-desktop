# -*- coding: utf-8 -*-
"""
Login Page - Based on Figma Design Reference
Exact implementation matching the provided screenshot
"""

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
from utils.i18n import I18n
from utils.logger import get_logger
from ui.font_utils import create_font, FontManager
from ui.design_system import Colors

logger = get_logger(__name__)


class LoginPage(QWidget):
    """Login page exactly matching the reference screenshot."""

    login_successful = pyqtSignal(object)

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.auth_service = ApiAuthService()
        self.password_visible = False
        self._arabic_re = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

        # Load custom fonts
        self._load_fonts()
        self._setup_ui()
        self._setup_login_watermark()
        self._position_login_watermark()
        self._setup_login_navbar()

        # Apply development mode settings (auto-fill credentials)
        self._apply_dev_mode_settings()

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
        """Paint background with blue section (Professional Stack)"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Blue section height from Figma (approximately 547px in 982px window = ~55%)
        blue_height = int(height * 0.55)

        # Top section - Primary blue
        painter.fillRect(0, 33, width, blue_height, QColor(Colors.PRIMARY_BLUE))

        # Bottom section - Background color #F0F7FF
        painter.fillRect(0, 33 + blue_height, width, height - (33 + blue_height), QColor(Colors.BACKGROUND))

    def _setup_ui(self):
        """Setup the login UI - Professional Stack Layout"""
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

        # شفافية خفيفة (متل التصميم) - Figma: Opacity 4% → PyQt5 needs higher value
        eff = QGraphicsOpacityEffect(self.bg_logo)
        eff.setOpacity(0.8)  # PyQt5: 15% for visible watermark (Figma 4% too low)
        self.bg_logo.setGraphicsEffect(eff)

        # خليه ورا الكارد
        self.bg_logo.lower()
        if hasattr(self, "login_card"):
            self.login_card.raise_()
    def _position_login_watermark(self):
        if not hasattr(self, "bg_logo") or not hasattr(self, "_bg_logo_src"):
            return

        # Figma exact dimensions: W=657.04, H=515
        target_w = 657
        target_h = 515

        pix = self._bg_logo_src.scaled(
            target_w, target_h,
            Qt.IgnoreAspectRatio,  # Use exact dimensions from Figma
            Qt.SmoothTransformation
        )

        self.bg_logo.setPixmap(pix)
        self.bg_logo.resize(pix.size())

        # Figma exact position: X=427, Y=65
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
        """Create the white login card matching Figma specs"""
        card = QFrame()
        card.setObjectName("login_card")
        # Figma: W=475, H=538 Hug (content-based)
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
        card_layout.setSpacing(24)  # Figma: Gap=32px → PyQt5 24px spacing

        card_layout.setContentsMargins(32, 32, 32, 32)  # Figma: Padding=32px (exact)

        # ===== Login Card Top Logo (Figma: W=122.54, H=120) =====
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(92, 90)  # Figma: 122.54×120 scaled down ~25% for PyQt5
        logo_label.setStyleSheet("background: transparent;")

        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Try to load Layer_1.png logo
        logo_path = os.path.join(current_dir, "..", "..", "assets", "images", "Layer_1.png")
        logo_path = os.path.normpath(logo_path)

        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            # Scale to PyQt5 appropriate size (Figma 122.54×120 → PyQt5 92×90)
            logo_label.setPixmap(pixmap.scaled(95, 90, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("UN-HABITAT")
            logo_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent;")

        card_layout.addWidget(logo_label, 0, Qt.AlignCenter)
        # =====================================
        # Title - Figma: Body/Body 2 -18px, W=315 Fill, H=21 Hug
        title = QLabel("تسجيل الدخول إلى الحساب")
        title.setAlignment(Qt.AlignCenter)
        title.setMaximumWidth(315)  # Figma: W=315 Fill
        title_font = create_font(size=FontManager.SIZE_HEADING, weight=QFont.Bold, letter_spacing=0)
        title.setFont(title_font)
        title.setStyleSheet("color: #172A47; background: transparent;")  # Grey/Dark - 900 (s-text)
        card_layout.addWidget(title,0, Qt.AlignCenter)

        # Figma: Gap between Title and Subtitle = 4px
        card_layout.addSpacing(-20)  # Negative spacing: 24px (default) - 20 = 4px gap

        # Subtitle - Figma: Body/Body 4 -14px, W=315 Fill, H=56 Hug (Single line, DemiBold weight)
        subtitle = QLabel("يرجى إدخال بيانات الدخول للمتابعة واستخدام النظام")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(False)  # Single line only
        subtitle.setMinimumWidth(315)  # Ensure minimum width for single line
        subtitle_font = create_font(size=FontManager.SIZE_BODY, weight=QFont.DemiBold, letter_spacing=0)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #86909B; background: transparent;")  # Grey/Dark - 500 (s-text)-(nav)
        card_layout.addWidget(subtitle,0, Qt.AlignCenter)

        # Reduce gap before form fields
        card_layout.addSpacing(16)

        # Username label
        username_label = QLabel("اسم المستخدم")
        username_label_font = create_font(size=10, weight=QFont.DemiBold, letter_spacing=0)
        username_label.setFont(username_label_font)
        username_label.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(username_label)
        card_layout.addSpacing(-20)  # Reduce gap between label and input (tighter)


        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("أدخل اسم المستخدم")
        self.username_input.setLayoutDirection(Qt.RightToLeft)
        self.username_input.setFixedHeight(40)  # Figma appropriate height
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
        password_label = QLabel("كلمة المرور")
        password_label_font = create_font(size=10, weight=QFont.DemiBold, letter_spacing=0)
        password_label.setFont(password_label_font)
        password_label.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(password_label)
        card_layout.addSpacing(-20)  # Reduce gap between label and input (tighter)

        # Password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("أدخل كلمة المرور")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)  # Figma appropriate height
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
        self.login_btn = QPushButton("تسجيل دخول")
        self.login_btn.setFixedHeight(48)  # Figma: ~50px button height
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

    def _apply_dev_mode_settings(self):
        """
        Apply development mode settings for easier testing.

        Best Practice:
        - Only enabled when Config.DEV_MODE = True
        - Auto-fills login credentials to skip manual entry during development
        - MUST be disabled in production (set Config.DEV_MODE = False)

        Security Note:
        This feature is ONLY for development/testing environments.
        Never enable DEV_MODE in production deployments.
        """
        if not Config.DEV_MODE or not Config.DEV_AUTO_LOGIN:
            return

        # Auto-fill credentials from Config
        self.username_input.setText(Config.DEV_USERNAME)
        self.password_input.setText(Config.DEV_PASSWORD)

        logger.info("DEV MODE: Auto-filled login credentials")

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

    def _setup_login_navbar(self):
        """Setup navbar title bar for login page - reusing Navbar components"""
        from ui.components.navbar import DraggableFrame

        # Create title bar using DraggableFrame (from Navbar)
        self.titlebar = DraggableFrame(self)
        self.titlebar.setLayoutDirection(Qt.LeftToRight)
        self.titlebar.setFixedHeight(33)  # Figma: 33px
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
        # Figma: Left padding = 12px for logo position
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(0)

        # Logo image from assets (header.png)
        # Figma specs: X=12, Y=5.62, Width=142.77, Height=21.77
        logo_label = QLabel()
        logo_label.setStyleSheet("background: transparent;")
        logo_label.setFixedSize(143, 22)  # Figma: 142.77 × 21.77

        logo_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "assets", "images", "header.png"
        )
        logo_path = os.path.normpath(logo_path)

        logo_pixmap = QPixmap(logo_path)
        if not logo_pixmap.isNull():
            # Scale to exact Figma dimensions
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

        # Window control buttons - Figma specs: 46×32px each
        btn_min = QPushButton("–")
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

        # Figma dimensions: 46 × 32 px
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


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "titlebar") and self.titlebar:
            self.titlebar.setGeometry(0, 0, self.width(), 33)  # Figma: 33px height
            self.titlebar.raise_()
        self._position_login_watermark()

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


