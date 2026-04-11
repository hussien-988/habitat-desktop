# -*- coding: utf-8 -*-
"""
Password Dialog — ديالوغ كلمة المرور
Three modes:
  - SET: Two fields (new user) — white theme — "حفظ المستخدم"
  - CHANGE: Three fields — dark theme — "تغيير كلمة المرور"
  - FORCED: Three fields + welcome + reason — dark theme — first login
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

from ui.components.icon import Icon
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger
from services.translation_manager import tr, get_layout_direction

logger = get_logger(__name__)


# Light theme input style (SET mode only)
_INPUT_STYLE_LIGHT = """
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

# Dark theme input style (CHANGE / FORCED modes — matches login page)
_INPUT_STYLE_DARK = """
    QLineEdit {
        background-color: rgba(10, 22, 40, 153);
        border: 1px solid rgba(56, 144, 223, 51);
        border-radius: 10px;
        padding: 0 12px;
        color: white;
    }
    QLineEdit:focus {
        border: 1px solid rgba(56, 144, 223, 153);
        outline: none;
    }
    QLineEdit::placeholder {
        color: rgba(139, 172, 200, 102);
    }
"""

# Dark theme error input style
_INPUT_ERROR_DARK = """
    QLineEdit {
        background-color: rgba(10, 22, 40, 153);
        border: 2px solid rgba(231, 76, 60, 180);
        border-radius: 10px;
        padding: 0 11px;
        color: white;
    }
    QLineEdit::placeholder { color: rgba(139, 172, 200, 102); }
"""


def _create_shield_icon(size: int = 56) -> QPixmap:
    """Draw a modern shield icon with QPainter."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)

    # Circle background
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(56, 144, 223, 30))
    p.drawEllipse(0, 0, size, size)

    # Shield path
    cx, cy = size / 2, size / 2
    s = size * 0.36
    path = QPainterPath()
    path.moveTo(cx, cy - s)
    path.lineTo(cx + s * 0.75, cy - s * 0.55)
    path.lineTo(cx + s * 0.75, cy + s * 0.1)
    path.quadTo(cx + s * 0.5, cy + s * 0.8, cx, cy + s)
    path.quadTo(cx - s * 0.5, cy + s * 0.8, cx - s * 0.75, cy + s * 0.1)
    path.lineTo(cx - s * 0.75, cy - s * 0.55)
    path.closeSubpath()

    pen = QPen(QColor(56, 144, 223), 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(QColor(56, 144, 223, 25))
    p.drawPath(path)

    # Checkmark inside
    check = QPainterPath()
    check.moveTo(cx - s * 0.28, cy + s * 0.05)
    check.lineTo(cx - s * 0.05, cy + s * 0.30)
    check.lineTo(cx + s * 0.30, cy - s * 0.20)
    pen2 = QPen(QColor(56, 144, 223), 2.0)
    pen2.setCapStyle(Qt.RoundCap)
    pen2.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen2)
    p.setBrush(Qt.NoBrush)
    p.drawPath(check)

    p.end()
    return pixmap


class PasswordDialog(QDialog):
    """Dialog for setting or changing user password."""

    # Mode constants
    SET = "set"
    CHANGE = "change"
    FORCED = "forced"

    def __init__(self, mode: str = SET, parent=None, username: str = "", username_en: str = ""):
        super().__init__(parent)
        self.password = None
        self.current_password = None
        self._mode = mode
        self._username = username
        self._username_en = username_en
        self._visibility = {}
        self._is_dark = mode in (self.CHANGE, self.FORCED)

        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        from PyQt5.QtWidgets import QApplication
        _scr = QApplication.primaryScreen().availableGeometry()
        if self._is_dark:
            h = 600 if mode == self.FORCED else 530
            self.resize(min(500, int(_scr.width() * 0.40)), min(h, int(_scr.height() * 0.65)))
            self.setMinimumSize(400, 420)
        else:
            self.resize(min(613, int(_scr.width() * 0.48)), min(384, int(_scr.height() * 0.45)))
            self.setMinimumSize(450, 320)

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        if self._is_dark:
            self._setup_dark_ui()
        else:
            self._setup_light_ui()

    # ------------------------------------------------------------------ #
    #  DARK THEME UI (CHANGE / FORCED)
    # ------------------------------------------------------------------ #

    def _setup_dark_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)

        outer.addStretch(1)

        card_wrapper = QHBoxLayout()
        card_wrapper.addStretch(1)

        # Frosted glass card
        card = QFrame()
        card.setObjectName("pwdCard")
        card.setFixedWidth(ScreenScale.w(440))
        card.setStyleSheet("""
            QFrame#pwdCard {
                background-color: rgba(15, 31, 61, 160);
                border: 1px solid rgba(56, 144, 223, 30);
                border-radius: 16px;
            }
            QFrame#pwdCard QLabel {
                background-color: transparent;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 76))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(14)

        # Shield icon
        shield_label = QLabel()
        shield_label.setAlignment(Qt.AlignCenter)
        shield_pixmap = _create_shield_icon(56)
        shield_label.setPixmap(shield_pixmap)
        layout.addWidget(shield_label)

        layout.addSpacing(4)

        if self._mode == self.FORCED:
            self._build_forced_header(layout)
        else:
            self._build_change_header(layout)

        layout.addSpacing(4)

        self._build_dark_fields(layout)

        # Error label
        self._policy_error_label = QLabel("")
        self._policy_error_label.setWordWrap(True)
        self._policy_error_label.setAlignment(Qt.AlignCenter)
        self._policy_error_label.setStyleSheet("""
            background-color: rgba(231, 76, 60, 38);
            color: #E74C3C;
            font-size: 10px;
            padding: 8px 10px;
            border-radius: 8px;
            border: 1px solid rgba(231, 76, 60, 102);
        """)
        self._policy_error_label.setFont(create_font(size=9))
        self._policy_error_label.hide()
        layout.addWidget(self._policy_error_label)

        layout.addSpacing(6)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        save_btn = self._create_dark_button(tr("button.save"), primary=True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        cancel_btn = self._create_dark_button(tr("button.cancel"), primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        card_wrapper.addWidget(card)
        card_wrapper.addStretch(1)
        outer.addLayout(card_wrapper)
        outer.addStretch(1)

    def _build_forced_header(self, layout: QVBoxLayout):
        """Welcome message + reason for forced password change."""
        from services.translation_manager import get_language
        if get_language() == 'ar':
            name = self._username or self._username_en or ""
        else:
            name = self._username_en or self._username or ""
        welcome_text = tr("dialog.password.forced_welcome").replace("{name}", name)
        title = QLabel(welcome_text)
        title.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        reason = QLabel(tr("dialog.password.forced_reason"))
        reason.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        reason.setStyleSheet("color: #8BACC8;")
        reason.setAlignment(Qt.AlignCenter)
        reason.setWordWrap(True)
        layout.addWidget(reason)

    def _build_change_header(self, layout: QVBoxLayout):
        """Simple title for voluntary password change."""
        title = QLabel(tr("dialog.password.change_password"))
        title.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

    def _build_dark_fields(self, layout: QVBoxLayout):
        """Three dark-themed password fields: current + new + confirm."""
        lbl_font = create_font(size=10, weight=QFont.DemiBold)
        lbl_style = "color: #8BACC8;"

        # Current password
        current_lbl = QLabel(tr("dialog.password.enter_current"))
        current_lbl.setFont(lbl_font)
        current_lbl.setStyleSheet(lbl_style)
        layout.addWidget(current_lbl)

        self.current_input = self._create_dark_password_field(
            tr("dialog.password.enter_password"), "current"
        )
        layout.addWidget(self.current_input)

        layout.addSpacing(4)

        # New password
        new_lbl = QLabel(tr("dialog.password.enter_new"))
        new_lbl.setFont(lbl_font)
        new_lbl.setStyleSheet(lbl_style)
        layout.addWidget(new_lbl)

        self.password_input = self._create_dark_password_field(
            tr("dialog.password.enter_password"), "password"
        )
        layout.addWidget(self.password_input)

        layout.addSpacing(4)

        # Confirm password
        confirm_lbl = QLabel(tr("dialog.password.reenter_new"))
        confirm_lbl.setFont(lbl_font)
        confirm_lbl.setStyleSheet(lbl_style)
        layout.addWidget(confirm_lbl)

        self.confirm_input = self._create_dark_password_field(
            tr("dialog.password.enter_password"), "confirm"
        )
        layout.addWidget(self.confirm_input)

    def _create_dark_password_field(self, placeholder: str, name: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.Password)
        field.setFixedHeight(ScreenScale.h(48))
        field.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        field.setStyleSheet(_INPUT_STYLE_DARK)

        self._visibility[name] = False
        eye_icon = Icon.load_qicon("Eye")
        if eye_icon:
            action = field.addAction(eye_icon, QLineEdit.TrailingPosition)
            action.triggered.connect(
                lambda _, n=name, f=field: self._toggle_visibility(n, f)
            )

        return field

    def _create_dark_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(ScreenScale.h(48))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=11, weight=QFont.Bold))

        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3890DF, stop:1 #5BA8F0);
                    color: white;
                    border: none;
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4DA0EF, stop:1 #6DB8FF);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2A7BC9, stop:1 #4A98E0);
                }
            """)
            btn_shadow = QGraphicsDropShadowEffect()
            btn_shadow.setBlurRadius(20)
            btn_shadow.setColor(QColor(56, 144, 223, 76))
            btn_shadow.setOffset(0, 4)
            btn.setGraphicsEffect(btn_shadow)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8BACC8;
                    border: 1px solid rgba(56, 144, 223, 51);
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background: rgba(56, 144, 223, 20);
                    color: white;
                }
                QPushButton:pressed {
                    background: rgba(56, 144, 223, 40);
                }
            """)

        return btn

    # ------------------------------------------------------------------ #
    #  LIGHT THEME UI (SET mode — unchanged)
    # ------------------------------------------------------------------ #

    def _setup_light_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

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

        self._build_set_mode(layout)

        # Policy error label
        self._policy_error_label = QLabel("")
        self._policy_error_label.setWordWrap(True)
        self._policy_error_label.setAlignment(Qt.AlignRight)
        self._policy_error_label.setStyleSheet(
            "color: #E74C3C; font-size: 11px; background: transparent; padding: 0 4px;"
        )
        self._policy_error_label.hide()
        layout.addWidget(self._policy_error_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        save_btn = self._create_light_button(tr("button.save"), primary=True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        cancel_btn = self._create_light_button(tr("button.cancel"), primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        outer.addWidget(container)

    def _build_set_mode(self, layout: QVBoxLayout):
        """Two password fields with confirmation — new user (light theme)."""
        title = self._create_light_title(tr("dialog.password.save_user"))
        layout.addWidget(title)

        subtitle = self._create_light_subtitle(tr("dialog.password.set_password"))
        layout.addWidget(subtitle)

        self.password_input = self._create_light_password_field(
            tr("dialog.password.enter_password"), "password"
        )
        layout.addWidget(self.password_input)

        confirm_label = self._create_light_subtitle(tr("dialog.password.reenter_password"))
        layout.addWidget(confirm_label)

        self.confirm_input = self._create_light_password_field(
            tr("dialog.password.enter_password"), "confirm"
        )
        layout.addWidget(self.confirm_input)

    def _create_light_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _create_light_subtitle(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _create_light_password_field(self, placeholder: str, name: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.Password)
        field.setFixedHeight(ScreenScale.h(42))
        field.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        field.setStyleSheet(_INPUT_STYLE_LIGHT)

        self._visibility[name] = False
        eye_icon = Icon.load_qicon("Eye")
        if eye_icon:
            action = field.addAction(eye_icon, QLineEdit.TrailingPosition)
            action.triggered.connect(
                lambda _, n=name, f=field: self._toggle_visibility(n, f)
            )

        return field

    def _create_light_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(ScreenScale.w(170), ScreenScale.h(50))
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

    # ------------------------------------------------------------------ #
    #  Shared logic
    # ------------------------------------------------------------------ #

    def _toggle_visibility(self, name: str, field: QLineEdit):
        self._visibility[name] = not self._visibility[name]
        field.setEchoMode(
            QLineEdit.Normal if self._visibility[name] else QLineEdit.Password
        )

    def _on_save(self):
        pwd = self.password_input.text().strip()
        if not pwd:
            return

        confirm = self.confirm_input.text().strip()
        if pwd != confirm:
            self._highlight_error(self.confirm_input)
            self._policy_error_label.setText(tr("dialog.password.mismatch"))
            self._policy_error_label.show()
            return

        if self._mode in (self.CHANGE, self.FORCED):
            current = self.current_input.text().strip()
            if not current:
                self._highlight_error(self.current_input)
                return
            self.current_password = current

        is_valid, errors = self._validate_against_policy(pwd)
        if not is_valid:
            self._highlight_error(self.password_input)
            self._policy_error_label.setText("\n".join(errors))
            self._policy_error_label.show()
            return

        self._policy_error_label.hide()
        self.password = pwd
        self.accept()

    def _validate_against_policy(self, password: str) -> tuple:
        """Validate password against SecurityService policy."""
        try:
            from repositories.database import Database
            from services.security_service import SecurityService
            db = Database()
            svc = SecurityService(db)
            return svc.validate_password(password)
        except Exception as e:
            logger.warning(f"Could not validate password policy: {e}")
            return True, []

    def _highlight_error(self, field: QLineEdit):
        if self._is_dark:
            field.setStyleSheet(_INPUT_ERROR_DARK)
        else:
            field.setStyleSheet("""
                QLineEdit {
                    background-color: #f0f7ff;
                    border: 2px solid #E74C3C;
                    border-radius: 8px;
                    padding: 0 13px;
                    color: #2C3E50;
                }
                QLineEdit::placeholder { color: #9CA3AF; }
            """)

    # ------------------------------------------------------------------ #
    #  Static convenience methods
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_password(parent=None) -> Optional[str]:
        """Show SET dialog and return password, or None if cancelled."""
        dialog = PasswordDialog(mode=PasswordDialog.SET, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.password
        return None

    @staticmethod
    def change_password(parent=None) -> Optional[tuple]:
        """Show CHANGE dialog (dark theme) — voluntary from settings."""
        dialog = PasswordDialog(mode=PasswordDialog.CHANGE, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return (dialog.current_password, dialog.password)
        return None

    @staticmethod
    def forced_change_password(parent=None, username: str = "", username_en: str = "") -> Optional[tuple]:
        """Show FORCED dialog (dark theme + welcome) — first login."""
        dialog = PasswordDialog(
            mode=PasswordDialog.FORCED, parent=parent,
            username=username, username_en=username_en
        )
        if dialog.exec_() == QDialog.Accepted:
            return (dialog.current_password, dialog.password)
        return None
