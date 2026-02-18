# -*- coding: utf-8 -*-
"""
شريط التنقل الجانبي مع شعار UN-Habitat.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpacerItem, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.config import Config, Pages
from utils.i18n import I18n


class Sidebar(QFrame):
    """شريط التنقل الجانبي."""

    navigate = pyqtSignal(str)

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.current_user = None
        self._buttons = {}
        self._selected_page = None

        self._setup_ui()

    def _setup_ui(self):
        """إعداد الواجهة."""
        self.setObjectName("sidebar")
        self.setFixedWidth(Config.SIDEBAR_WIDTH)
        self.setLayoutDirection(Qt.RightToLeft)

        # استخدام الصورة كخلفية عبر StyleSheet - fit بدون تمدد
        logo_path = str(Config.LOGO_PATH).replace("\\", "/")
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background-image: url("{logo_path}");
                background-repeat: no-repeat;
                background-position: center center;
                background-attachment: fixed;
                border: none;
            }}
        """)

        # الـ layout الرئيسي
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # طبقة overlay فوق الخلفية - لون شفاف للسماح بظهور الشعار
        overlay = QFrame()
        overlay.setObjectName("sidebar-overlay")
        overlay.setStyleSheet("""
            QFrame#sidebar-overlay {
                background: rgba(0, 82, 156, 0.80);
                border: none;
                margin: 0;
                padding: 0;
            }
        """)
        main_layout.addWidget(overlay)

        # محتوى الـ overlay
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # مساحة علوية
        layout.addSpacing(32)

        # عناصر التنقل
        nav_items = [
            (Pages.DASHBOARD, "لوحة التحكم"),
            (Pages.BUILDINGS, "المباني"),
            (Pages.UNITS, "الوحدات"),
            (Pages.PERSONS, "الأشخاص"),
            (Pages.CLAIMS, "المطالبات"),
            (Pages.DUPLICATES, "التكرارات"),
            (Pages.FIELD_ASSIGNMENT, "تعيين الفرق"),
            (Pages.SEARCH, "البحث"),
            (Pages.IMPORT_WIZARD, "الاستيراد"),
            (Pages.MAP_VIEW, "الخريطة"),
            (Pages.REPORTS, "التقارير"),
            (Pages.ADMIN, "الإدارة"),
        ]

        for page_id, label in nav_items:
            btn = self._create_nav_button(page_id, label)
            layout.addWidget(btn)
            self._buttons[page_id] = btn

        # مساحة فارغة
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # معلومات المستخدم
        self.user_widget = QFrame()
        self.user_widget.setObjectName("user-widget")
        self.user_widget.setStyleSheet("""
            QFrame#user-widget {
                background: transparent;
                border: none;
            }
        """)
        user_layout = QVBoxLayout(self.user_widget)
        user_layout.setContentsMargins(16, 14, 16, 14)
        user_layout.setSpacing(4)

        self.user_name_label = QLabel("")
        self.user_name_label.setStyleSheet(f"""
            color: white;
            font-weight: 700;
            font-size: {Config.FONT_SIZE}pt;
            background: transparent;
        """)
        self.user_name_label.setAlignment(Qt.AlignRight)
        user_layout.addWidget(self.user_name_label)

        self.user_role_label = QLabel("")
        self.user_role_label.setStyleSheet(f"""
            color: {Config.ACCENT_COLOR};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            font-weight: 500;
            background: transparent;
        """)
        self.user_role_label.setAlignment(Qt.AlignRight)
        user_layout.addWidget(self.user_role_label)

        layout.addWidget(self.user_widget)

    def _create_nav_button(self, page_id: str, label: str) -> QPushButton:
        """إنشاء زر تنقل."""
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setLayoutDirection(Qt.RightToLeft)
        btn.setFocusPolicy(Qt.NoFocus)  # إزالة البوردر المنقط عند الضغط
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: rgba(255, 255, 255, 0.8);
                border: none;
                outline: none;
                text-align: right;
                padding: 14px 18px;
                font-size: {Config.FONT_SIZE + 1}pt;
                font-weight: 500;
                border-right: 3px solid transparent;
                border-radius: 0;
            }}
            QPushButton:focus {{
                outline: none;
                border: none;
            }}
            QPushButton:hover {{
                background-color: rgba(253, 183, 20, 0.15);
                color: {Config.ACCENT_COLOR};
                border-right: 3px solid {Config.ACCENT_COLOR};
                font-size: {Config.FONT_SIZE + 2}pt;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background-color: rgba(253, 183, 20, 0.12);
                border-right: 3px solid {Config.ACCENT_COLOR};
                color: {Config.ACCENT_COLOR};
                font-size: {Config.FONT_SIZE + 2}pt;
                font-weight: 700;
            }}
        """)
        btn.clicked.connect(lambda checked, pid=page_id: self._on_nav_click(pid))
        return btn

    def _on_nav_click(self, page_id: str):
        """معالجة النقر على زر التنقل."""
        self.set_selected(page_id)
        self.navigate.emit(page_id)

    def set_selected(self, page_id: str):
        """تحديد العنصر النشط."""
        self._selected_page = page_id

        for pid, btn in self._buttons.items():
            btn.setChecked(pid == page_id)
            btn.setProperty("selected", pid == page_id)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_user(self, user):
        """تحديث معلومات المستخدم."""
        self.current_user = user
        if user:
            self.user_name_label.setText(user.display_name)
            self.user_role_label.setText(user.role_display_ar)

    def update_language(self, is_arabic: bool):
        """تحديث اللغة."""
        pass
