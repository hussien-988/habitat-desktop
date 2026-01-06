# -*- coding: utf-8 -*-
"""
صفحة تسجيل الدخول بتصميم احترافي.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from app.config import Config
from repositories.database import Database
from services.auth_service import AuthService
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class LoginPage(QWidget):
    """صفحة تسجيل الدخول."""

    login_successful = pyqtSignal(object)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.auth_service = AuthService(db)

        self._setup_ui()

    def _setup_ui(self):
        """إعداد واجهة تسجيل الدخول."""
        self.setObjectName("login-container")

        # التخطيط الرئيسي
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # الجانب الأيسر - منطقة الشعار مع خلفية الصورة
        left_panel = QFrame()
        left_panel.setFixedWidth(420)
        left_panel.setObjectName("left-panel")

        # تحديد خلفية الشعار مع تأثير overlay
        logo_path = str(Config.LOGO_PATH).replace("\\", "/")
        left_panel.setStyleSheet(f"""
            QFrame#left-panel {{
                background-image: url("{logo_path}");
                background-repeat: no-repeat;
                background-position: center;
                border: none;
            }}
        """)

        # طبقة overlay شفافة فوق الصورة
        overlay = QFrame(left_panel)
        overlay.setObjectName("overlay")
        overlay.setStyleSheet(f"""
            QFrame#overlay {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 114, 188, 0.85),
                    stop:0.5 rgba(0, 90, 156, 0.88),
                    stop:1 rgba(0, 60, 120, 0.92)
                );
            }}
        """)

        # تخطيط الـ overlay ليملأ كامل المساحة
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(0)
        left_panel_layout.addWidget(overlay)

        # محتوى الـ overlay
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        overlay_layout.setContentsMargins(40, 80, 40, 80)
        overlay_layout.setSpacing(0)

        overlay_layout.addStretch(2)

        # اسم النظام - السطر الأول
        system_name1 = QLabel("نظام تسجيل حقوق الحيازة")
        system_name1.setStyleSheet(f"""
            color: white;
            font-size: 15pt;
            font-weight: 600;
            letter-spacing: 1px;
            background: transparent;
        """)
        system_name1.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(system_name1)

        overlay_layout.addSpacing(8)

        # اسم النظام - السطر الثاني
        system_name2 = QLabel("وإدارة المطالبات")
        system_name2.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.9);
            font-size: 14pt;
            font-weight: 500;
            letter-spacing: 1px;
            background: transparent;
        """)
        system_name2.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(system_name2)

        overlay_layout.addStretch(3)

        main_layout.addWidget(left_panel)

        # الجانب الأيمن - نموذج تسجيل الدخول
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignCenter)
        right_layout.setContentsMargins(80, 60, 80, 60)

        # كارد تسجيل الدخول
        card = QFrame()
        card.setObjectName("login-card")
        card.setFixedWidth(420)
        card.setStyleSheet("""
            QFrame#login-card {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        # إضافة ظل
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 8)
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(44, 44, 44, 44)

        # عنوان الترحيب
        welcome_label = QLabel("مرحباً بك")
        welcome_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1 + 4}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
            background: transparent;
            padding: 0;
            margin: 0;
        """)
        welcome_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(welcome_label)

        card_layout.addSpacing(10)

        # العنوان الفرعي
        subtitle = QLabel("قم بتسجيل الدخول للمتابعة")
        subtitle.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_BODY + 1}pt;
            color: {Config.TEXT_LIGHT};
            background: transparent;
            padding: 0;
            margin: 0;
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(38)

        # حقل اسم المستخدم
        username_label = QLabel("اسم المستخدم")
        username_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE + 2}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
            background: transparent;
            padding: 0;
            margin: 0;
        """)
        card_layout.addWidget(username_label)

        card_layout.addSpacing(6)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("أدخل اسم المستخدم")
        self.username_input.setLayoutDirection(Qt.RightToLeft)
        self.username_input.setFixedHeight(52)
        self.username_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 2px solid #E2E8F0;
                border-radius: 10px;
                padding: 0 16px;
                font-size: {Config.FONT_SIZE + 2}pt;
                color: {Config.TEXT_COLOR};
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
                background-color: white;
            }}
        """)
        card_layout.addWidget(self.username_input)

        card_layout.addSpacing(28)

        # حقل كلمة المرور
        password_label = QLabel("كلمة المرور")
        password_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE + 2}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
            background: transparent;
            padding: 0;
            margin: 0;
        """)
        card_layout.addWidget(password_label)

        card_layout.addSpacing(6)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("أدخل كلمة المرور")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setLayoutDirection(Qt.RightToLeft)
        self.password_input.setFixedHeight(52)
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 2px solid #E2E8F0;
                border-radius: 10px;
                padding: 0 16px;
                font-size: {Config.FONT_SIZE + 2}pt;
                color: {Config.TEXT_COLOR};
            }}
            QLineEdit:focus {{
                border: 2px solid {Config.PRIMARY_COLOR};
                background-color: white;
            }}
        """)
        self.password_input.returnPressed.connect(self._on_login)
        card_layout.addWidget(self.password_input)

        card_layout.addSpacing(32)

        # رسالة الخطأ
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"""
            color: {Config.ERROR_COLOR};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            padding: 10px;
            background-color: #FEE2E2;
            border-radius: 6px;
        """)
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        # زر تسجيل الدخول
        self.login_btn = QPushButton("تسجيل الدخول")
        self.login_btn.setFixedHeight(54)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: {Config.FONT_SIZE_H2 + 1}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
            QPushButton:pressed {{
                background-color: #004A7C;
            }}
        """)
        self.login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self.login_btn)

        card_layout.addSpacing(28)

        # بيانات تجريبية
        hint_container = QFrame()
        hint_container.setStyleSheet("""
            background-color: transparent;
            border: none;
        """)
        hint_layout = QVBoxLayout(hint_container)
        hint_layout.setContentsMargins(0, 8, 0, 0)
        hint_layout.setSpacing(2)

        hint_title = QLabel("بيانات الدخول التجريبية")
        hint_title.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-weight: 500;
            font-size: {Config.FONT_SIZE}pt;
            background: transparent;
        """)
        hint_title.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(hint_title)

        hint_text = QLabel("admin / admin123")
        hint_text.setStyleSheet(f"""
            color: {Config.PRIMARY_COLOR};
            font-size: {Config.FONT_SIZE}pt;
            font-weight: 600;
            background: transparent;
        """)
        hint_text.setAlignment(Qt.AlignCenter)
        hint_layout.addWidget(hint_text)

        card_layout.addWidget(hint_container)

        right_layout.addWidget(card)

        main_layout.addWidget(right_panel, 1)

    def _on_login(self):
        """معالجة تسجيل الدخول."""
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
        """عرض رسالة الخطأ."""
        self.error_label.setText(message)
        self.error_label.show()

    def _clear_form(self):
        """مسح النموذج."""
        self.username_input.clear()
        self.password_input.clear()
        self.error_label.hide()

    def refresh(self, data=None):
        """تحديث الصفحة."""
        self._clear_form()
        self.username_input.setFocus()

    def update_language(self, is_arabic: bool):
        """تحديث اللغة."""
        pass
