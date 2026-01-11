# -*- coding: utf-8 -*-
"""
Login Page - Based on Figma Design Reference
Exact implementation matching the provided screenshot
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,QGraphicsOpacityEffect,QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QColor, QPainter, QPaintEvent, QFont, QFontDatabase, QPixmap
from PyQt5.QtGui import QCursor, QIcon
import os
import re
from app.config import Config
from repositories.database import Database
from services.auth_service import AuthService
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

class DraggableTitleBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
            if not self.window().isMaximized():
                self.window().move(event.globalPos() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self.window()
            w.showNormal() if w.isMaximized() else w.showMaximized()
            event.accept()
        super().mouseDoubleClickEvent(event)


class LoginPage(QWidget):
    """Login page exactly matching the reference screenshot."""

    login_successful = pyqtSignal(object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.auth_service = AuthService(db)
        self.password_visible = False
        self._arabic_re = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

        # Load custom fonts
        self._load_fonts()
        self._setup_ui()
        self._setup_login_watermark()
        self._position_login_watermark()
        self._setup_login_window_controls()

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

        # شفافية خفيفة (متل التصميم)
        eff = QGraphicsOpacityEffect(self.bg_logo)
        eff.setOpacity(0.8)  # جرّب 0.06 إذا بدك أخف
        self.bg_logo.setGraphicsEffect(eff)

        # خليه ورا الكارد
        self.bg_logo.lower()
        if hasattr(self, "login_card"):
            self.login_card.raise_()
    def _position_login_watermark(self):
        if not hasattr(self, "bg_logo") or not hasattr(self, "_bg_logo_src"):
            return

        w = self.width()
        h = self.height()
        mid = h // 2  # نفس تقسيم الأزرق بالنص

        # حجم الشعار (كبره حسب عرض النافذة)
        target_w = int(w *0.55)
        target_w = max(320, min(target_w, 900))

        pix = self._bg_logo_src.scaled(
            target_w, target_w,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.bg_logo.setPixmap(pix)
        self.bg_logo.resize(pix.size())

        # حطه بمنتصف منطقة الأزرق (فوق)
        x = (w - self.bg_logo.width()) // 2
        y = (mid - self.bg_logo.height()) // 2
        self.bg_logo.move(x, y)

        # ترتيب الطبقات: الشعار تحت، الكارد فوق، وبعدين أزرار اللوجين إذا عندك titlebar
        self.bg_logo.lower()
        if hasattr(self, "login_card"):
            self.login_card.raise_()
        if hasattr(self, "titlebar"):
            self.titlebar.raise_()



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

        # ===== Login Card Top Logo (NEW) =====
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedHeight(90)
        logo_label.setStyleSheet("""
            background:transparent ;
            
        """)

        current_dir = os.path.dirname(os.path.abspath(__file__))

        # غيّر اسم الصورة هون إذا اسمها غير هيك
        logo_path = os.path.join(current_dir, "..", "..", "assets", "images", "Layer_1.png")
        logo_path = os.path.normpath(logo_path)

        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo_label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("UN-HABITAT")
            logo_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent;")


        card_layout.addWidget(logo_label)
        card_layout.addSpacing(25)
        # =====================================
        # Title
        title = QLabel("تسجيل الدخول إلى الحساب")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Noto Kufi Arabic", 10, QFont.Bold))
        title.setStyleSheet("color: #2C3E50; background: transparent;")
        card_layout.addWidget(title)

        card_layout.addSpacing(2)

        # Subtitle
        subtitle = QLabel("يرجى إدخال بيانات الدخول للمتابعة واستخدام النظام")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont("Noto Kufi Arabic", 8, QFont.Bold))
        subtitle.setStyleSheet("color: #7F8C9B; background: transparent;")
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(20)

        # Username label
        username_label = QLabel("اسم المستخدم")
        username_label.setFont(QFont("Noto Kufi Arabic", 9, QFont.DemiBold))
        username_label.setStyleSheet("color: #2C3E50; background: transparent;")
        card_layout.addWidget(username_label)

        card_layout.addSpacing(4)

        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("أدخل اسم المستخدم")
        self.username_input.setLayoutDirection(Qt.RightToLeft)
        self.username_input.setFixedHeight(40)
        self.username_input.setFont(QFont("Noto Kufi Arabic", 8))
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: #f0f7ff;
                border: 1px solid #D5DBDB;
                border-radius: 12px;
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
        password_label.setFont(QFont("Noto Kufi Arabic", 9, QFont.DemiBold))
        password_label.setStyleSheet("color: #2C3E50; background: transparent;")
        card_layout.addWidget(password_label)

        card_layout.addSpacing(6)

        # Password input 
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("أدخل كلمة المرور")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(40)
        self.password_input.setFont(QFont("Noto Kufi Arabic", 8))


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
        self.login_btn.setFont(QFont("Noto Kufi Arabic", 9, QFont.Bold))
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 12px;
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

        card_layout.addSpacing(16)

        # Version
        version_label = QLabel("v 1.4")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #BDC3C7; font-size: 10px; background: transparent;")
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
    def _setup_login_window_controls(self):
        self.titlebar = DraggableTitleBar(self)
        self.titlebar.setLayoutDirection(Qt.LeftToRight)

        self.titlebar.setFixedHeight(40)
        self.titlebar.setObjectName("login_titlebar")
        self.titlebar.setStyleSheet("""
            QFrame#login_titlebar { background: transparent; }

            QPushButton#win_btn, QPushButton#win_close {
                color: white;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton#win_btn:hover {
                background: rgba(255,255,255,0.14);
            }
            QPushButton#win_btn:pressed {
                background: rgba(255,255,255,0.22);
            }
            QPushButton#win_close:hover {
                background: rgba(255, 59, 48, 0.90);
            }
            QPushButton#win_close:pressed {
                background: rgba(255, 59, 48, 0.75);
            }
        """)

        lay = QHBoxLayout(self.titlebar)
        lay.setContentsMargins(12, 8, 12, 0)
        lay.setSpacing(6)
        lay.addStretch(1)

        btn_min = QPushButton("–")
        btn_max = QPushButton("□")
        btn_close = QPushButton("✕")

        btn_min.setObjectName("win_btn")
        btn_max.setObjectName("win_btn")
        btn_close.setObjectName("win_close")

        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(40, 28)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setFocusPolicy(Qt.NoFocus)

        btn_min.clicked.connect(lambda: self.window().showMinimized())
        btn_max.clicked.connect(lambda: self.window().showNormal() if self.window().isMaximized() else self.window().showMaximized())
        btn_close.clicked.connect(lambda: self.window().close())

        lay.addWidget(btn_min)
        lay.addWidget(btn_max)
        lay.addWidget(btn_close)
        
        # خليه فوق كل شي
        self.titlebar.raise_()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "titlebar") and self.titlebar:
            self.titlebar.setGeometry(0, 0, self.width(), 40)
            self.titlebar.raise_()
        self._position_login_watermark()

    def _apply_password_style(self, icon_on_left: bool):
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #f0f7ff;
                border: 1px solid #D5DBDB;
                border-radius: 12px;
                padding: 8px 12px;
                
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


