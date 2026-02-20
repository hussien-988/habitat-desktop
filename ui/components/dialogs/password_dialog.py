# -*- coding: utf-8 -*-
"""
Password Dialog — ديالوغ كلمة المرور
Two modes:
  - SET: Single field (new user) — "حفظ المستخدم"
  - CHANGE: Two fields with confirmation — "تغيير كلمة المرور"
Follows PersonDialog/ConfirmationDialog container pattern (DRY).
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ui.components.icon import Icon
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager


# Input field stylesheet (DRY — shared across both fields)
_INPUT_STYLE = """
    QLineEdit {
        background-color: #f0f7ff;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        padding: 0 14px;
        color: #2C3E50;
    }
    QLineEdit:focus {
        border: 2px solid #3890DF;
        padding: 0 13px;
    }
    QLineEdit::placeholder {
        color: #9CA3AF;
    }
"""


class PasswordDialog(QDialog):
    """Dialog for setting or changing user password."""

    # Mode constants
    SET = "set"
    CHANGE = "change"

    def __init__(self, mode: str = SET, parent=None):
        super().__init__(parent)
        self.password = None
        self._mode = mode
        self._visibility = {}  # field_name → bool

        self.setModal(True)
        # Figma: SET=589×234, CHANGE=589×320, +24 for shadow margin
        height = 344 if mode == self.CHANGE else 258
        self.setFixedSize(613, height)
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
        container.setObjectName("pwdContainer")
        container.setStyleSheet("""
            QFrame#pwdContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#pwdContainer QLabel {
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
        layout.setSpacing(16)

        if self._mode == self.SET:
            self._build_set_mode(layout)
        else:
            self._build_change_mode(layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        save_btn = self._create_button("حفظ", primary=True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        cancel_btn = self._create_button("الغاء", primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _build_set_mode(self, layout: QVBoxLayout):
        """Single password field — new user."""
        title = self._create_title("حفظ المستخدم")
        layout.addWidget(title)

        subtitle = self._create_subtitle("ضع كلمة المرور للمستخدم")
        layout.addWidget(subtitle)

        self.password_input = self._create_password_field("أدخل كلمة المرور", "password")
        layout.addWidget(self.password_input)

    def _build_change_mode(self, layout: QVBoxLayout):
        """Two password fields with confirmation — change password."""
        title = self._create_title("تغيير كلمة المرور")
        layout.addWidget(title)

        subtitle = self._create_subtitle("ضع كلمة المرور الجديدة")
        layout.addWidget(subtitle)

        self.password_input = self._create_password_field("أدخل كلمة المرور", "password")
        layout.addWidget(self.password_input)

        confirm_label = self._create_subtitle("اعد ادخال كلمة المرور الجديدة")
        layout.addWidget(confirm_label)

        self.confirm_input = self._create_password_field("أدخل كلمة المرور", "confirm")
        layout.addWidget(self.confirm_input)

    # --- Reusable widget builders (DRY) ---

    def _create_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _create_subtitle(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _create_password_field(self, placeholder: str, name: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.Password)
        field.setFixedHeight(42)
        field.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        field.setStyleSheet(_INPUT_STYLE)

        self._visibility[name] = False
        eye_icon = Icon.load_qicon("Eye")
        if eye_icon:
            action = field.addAction(eye_icon, QLineEdit.TrailingPosition)
            action.triggered.connect(lambda _, n=name, f=field: self._toggle_visibility(n, f))

        return field

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(170, 50)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=QFont.Medium))

        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: #2D7BC9;
                }}
                QPushButton:pressed {{
                    background-color: #2468B0;
                }}
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

    def _toggle_visibility(self, name: str, field: QLineEdit):
        self._visibility[name] = not self._visibility[name]
        field.setEchoMode(
            QLineEdit.Normal if self._visibility[name] else QLineEdit.Password
        )

    def _on_save(self):
        pwd = self.password_input.text().strip()
        if not pwd:
            return

        if self._mode == self.CHANGE:
            confirm = self.confirm_input.text().strip()
            if pwd != confirm:
                self.confirm_input.setStyleSheet("""
                    QLineEdit {
                        background-color: #f0f7ff;
                        border: 2px solid #E74C3C;
                        border-radius: 8px;
                        padding: 0 13px;
                        color: #2C3E50;
                    }
                    QLineEdit::placeholder { color: #9CA3AF; }
                """)
                return

        self.password = pwd
        self.accept()

    @staticmethod
    def get_password(parent=None) -> Optional[str]:
        """Show SET dialog and return password, or None if cancelled."""
        dialog = PasswordDialog(mode=PasswordDialog.SET, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.password
        return None

    @staticmethod
    def change_password(parent=None) -> Optional[str]:
        """Show CHANGE dialog and return new password, or None if cancelled."""
        dialog = PasswordDialog(mode=PasswordDialog.CHANGE, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.password
        return None
