# -*- coding: utf-8 -*-
"""
الشريط العلوي.
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.config import Config, Pages
from utils.i18n import I18n


class TopBar(QWidget):
    """الشريط العلوي مع العنوان والإجراءات."""

    logout_requested = pyqtSignal()
    language_toggled = pyqtSignal()

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.current_user = None
        self._current_page = None

        self._setup_ui()

    def _setup_ui(self):
        """إعداد الواجهة."""
        self.setObjectName("topbar")
        self.setFixedHeight(60)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(f"""
            #topbar {{
                background-color: white;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        # عنوان الصفحة
        self.title_label = QLabel("")
        self.title_label.setObjectName("page-title")
        self.title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H2}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(self.title_label)

        # مساحة فارغة
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # فاصل
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setFixedHeight(24)
        separator.setStyleSheet(f"background-color: {Config.BORDER_COLOR};")
        layout.addWidget(separator)

        # اسم المستخدم
        self.user_label = QLabel("")
        self.user_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE}pt;
        """)
        layout.addWidget(self.user_label)

        # زر تسجيل الخروج
        self.logout_btn = QPushButton("تسجيل الخروج")
        self.logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Config.ERROR_COLOR};
                border: 1px solid {Config.ERROR_COLOR};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Config.ERROR_COLOR};
                color: white;
            }}
        """)
        self.logout_btn.setCursor(Qt.PointingHandCursor)
        self.logout_btn.clicked.connect(self.logout_requested.emit)
        layout.addWidget(self.logout_btn)

    def set_title(self, page_id: str):
        """تحديد عنوان الصفحة."""
        self._current_page = page_id

        titles = {
            Pages.DASHBOARD: "لوحة التحكم",
            Pages.BUILDINGS: "المباني",
            Pages.BUILDING_DETAILS: "تفاصيل المبنى",
            Pages.IMPORT_WIZARD: "معالج الاستيراد",
            Pages.MAP_VIEW: "عرض الخريطة",
        }

        self.title_label.setText(titles.get(page_id, page_id))

    def set_user(self, user):
        """تحديث معلومات المستخدم."""
        self.current_user = user
        if user:
            self.user_label.setText(user.full_name_ar or user.full_name or user.username)

    def update_language(self, is_arabic: bool):
        """تحديث اللغة."""
        if self._current_page:
            self.set_title(self._current_page)
        if self.current_user:
            self.user_label.setText(self.current_user.full_name_ar or self.current_user.full_name or self.current_user.username)
