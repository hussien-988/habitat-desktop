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
from services.translation_manager import tr, get_layout_direction


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
        self.setLayoutDirection(get_layout_direction())
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

        # Language toggle button
        self._lang_btn = QPushButton()
        self._update_lang_display()
        self._lang_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Config.TEXT_COLOR};
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #F3F4F6;
            }}
        """)
        self._lang_btn.setCursor(Qt.PointingHandCursor)
        self._lang_btn.clicked.connect(self.language_toggled.emit)
        layout.addWidget(self._lang_btn)

        # زر تسجيل الخروج
        self.logout_btn = QPushButton(tr("component.topbar.logout"))
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
            Pages.DASHBOARD: tr("component.topbar.page_dashboard"),
            Pages.BUILDINGS: tr("component.topbar.page_buildings"),
            Pages.BUILDING_DETAILS: tr("component.topbar.page_building_details"),
            Pages.IMPORT_WIZARD: tr("component.topbar.page_import_wizard"),
            Pages.MAP_VIEW: tr("component.topbar.page_map_view"),
        }

        self.title_label.setText(titles.get(page_id, page_id))

    def set_user(self, user):
        """تحديث معلومات المستخدم."""
        self.current_user = user
        if user:
            self.user_label.setText(user.full_name_ar or user.full_name or user.username)

    def _update_lang_display(self):
        """Update language button text."""
        from services.translation_manager import get_language
        current = get_language()
        self._lang_btn.setText("English" if current == "ar" else "عربي")

    def update_language(self, is_arabic: bool):
        """تحديث اللغة."""
        self.setLayoutDirection(get_layout_direction())
        self.logout_btn.setText(tr("component.topbar.logout"))
        self._update_lang_display()
        if self._current_page:
            self.set_title(self._current_page)
        if self.current_user:
            self.user_label.setText(self.current_user.full_name_ar or self.current_user.full_name or self.current_user.username)
