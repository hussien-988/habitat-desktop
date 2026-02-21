# -*- coding: utf-8 -*-
"""
Logout Dialog — ديالوغ تأكيد تسجيل الخروج / إغلاق التطبيق
Follows LanguageDialog/PasswordDialog container pattern (DRY).
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ui.components.icon import Icon
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager


class LogoutDialog(QDialog):
    """Dialog for confirming logout or application exit."""

    def __init__(self, parent=None, is_exit: bool = False):
        super().__init__(parent)
        self._is_exit = is_exit

        self.setModal(True)
        self.setFixedSize(586, 307)  # 562+24 shadow margin
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        # White container
        container = QFrame()
        container.setObjectName("logoutContainer")
        container.setStyleSheet("""
            QFrame#logoutContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#logoutContainer QLabel {
                background-color: transparent;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Icon (centered)
        icon_label = QLabel()
        icon_label.setFixedSize(64, 64)
        icon_label.setAlignment(Qt.AlignCenter)
        pixmap = Icon.load_pixmap("logout-01", size=64)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)

        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        icon_layout.addWidget(icon_label)
        icon_layout.addStretch()
        layout.addLayout(icon_layout)

        # Title (centered)
        title_text = "إغلاق التطبيق" if self._is_exit else "تسجيل خروج"
        title = QLabel(title_text)
        title.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Subtitle (centered)
        if self._is_exit:
            subtitle_text = "هل انت متأكد انك تريد إغلاق التطبيق؟"
        else:
            subtitle_text = "هل انت متأكد انك تريد تسجيل الخروج"
        subtitle = QLabel(subtitle_text)
        subtitle.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        action_text = "إغلاق" if self._is_exit else "خروج"
        action_btn = self._create_button(action_text, primary=True)
        action_btn.clicked.connect(self.accept)
        btn_layout.addWidget(action_btn)

        back_btn = self._create_button("رجوع", primary=False)
        back_btn.clicked.connect(self.reject)
        btn_layout.addWidget(back_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(170, 50)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=QFont.Medium))

        if primary:
            # Red button for logout/exit
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #EF4444;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #DC2626;
                }
                QPushButton:pressed {
                    background-color: #B91C1C;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #6B7280;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #F9FAFB;
                }
                QPushButton:pressed {
                    background-color: #F3F4F6;
                }
            """)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(8)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 25))
            btn.setGraphicsEffect(shadow)

        return btn

    @staticmethod
    def confirm_logout(parent=None) -> bool:
        """Show logout confirmation dialog. Returns True if user confirmed."""
        dialog = LogoutDialog(parent=parent, is_exit=False)
        return dialog.exec_() == QDialog.Accepted

    @staticmethod
    def confirm_exit(parent=None) -> bool:
        """Show exit confirmation dialog. Returns True if user confirmed."""
        dialog = LogoutDialog(parent=parent, is_exit=True)
        return dialog.exec_() == QDialog.Accepted
