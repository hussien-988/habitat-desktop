# -*- coding: utf-8 -*-
"""
Forgot Password Dialog — نسيت كلمة المرور

Sends POST /v1/auth/forgot-password {username, note} so an administrator
resets the password. The server answers with the same localized message
whether or not the user exists; that message is shown as is.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from services.translation_manager import get_layout_direction, tr
from ui.design_system import Colors, ScreenScale
from ui.font_utils import FontManager, create_font
from utils.logger import get_logger

logger = get_logger(__name__)


_INPUT_STYLE = """
    QLineEdit, QPlainTextEdit {
        background-color: #f0f7ff;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        padding: 0 14px;
        color: #2C3E50;
    }
    QPlainTextEdit { padding: 8px 10px; }
    QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #3890DF; }
"""


class ForgotPasswordDialog(QDialog):
    """Username + optional note → request a password reset from an administrator."""

    def __init__(self, username: str = "", parent=None):
        super().__init__(parent)
        self._worker = None
        self._sent = False

        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self._setup_ui()
        self.username_input.setText(username)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setObjectName("forgotPwdCard")
        card.setFixedWidth(ScreenScale.w(440))
        card.setStyleSheet("""
            QFrame#forgotPwdCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 16px;
            }
            QFrame#forgotPwdCard QLabel { background-color: transparent; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 76))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(12)

        title = QLabel(tr("forgot_password.title"))
        title.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        hint = QLabel(tr("forgot_password.hint"))
        hint.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addSpacing(4)

        lbl_font = create_font(size=10, weight=QFont.DemiBold)
        lbl_style = f"color: {Colors.TEXT_PRIMARY};"

        username_lbl = QLabel(
            f"{tr('page.login.username')} <span style='color:#E74C3C;'>*</span>"
        )
        username_lbl.setFont(lbl_font)
        username_lbl.setStyleSheet(lbl_style)
        layout.addWidget(username_lbl)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(tr("page.login.username_placeholder"))
        self.username_input.setFixedHeight(ScreenScale.h(48))
        self.username_input.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self.username_input.setStyleSheet(_INPUT_STYLE)
        self.username_input.textChanged.connect(self._hide_status)
        layout.addWidget(self.username_input)

        note_lbl = QLabel(tr("forgot_password.note"))
        note_lbl.setFont(lbl_font)
        note_lbl.setStyleSheet(lbl_style)
        layout.addWidget(note_lbl)

        self.note_input = QPlainTextEdit()
        self.note_input.setPlaceholderText(tr("forgot_password.note_placeholder"))
        self.note_input.setFixedHeight(ScreenScale.h(90))
        self.note_input.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self.note_input.setStyleSheet(_INPUT_STYLE)
        layout.addWidget(self.note_input)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setFont(create_font(size=9))
        self._status.hide()
        layout.addWidget(self._status)

        layout.addSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self._send_btn = self._create_button(tr("forgot_password.send"), primary=True)
        self._send_btn.clicked.connect(self._on_send)
        buttons.addWidget(self._send_btn)
        self._cancel_btn = self._create_button(tr("button.cancel"), primary=False)
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._cancel_btn)
        layout.addLayout(buttons)

        outer.addWidget(card)

    def _create_button(self, text: str, primary: bool) -> QPushButton:
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
                QPushButton:disabled { background: rgba(56, 144, 223, 90); }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: #F8FAFF;
                    color: #606266;
                    border: 1px solid #E1E8ED;
                    border-radius: 10px;
                }
                QPushButton:hover { background: #EFF6FF; color: #2C3E50; }
            """)
        return btn

    # ------------------------------------------------------------------ #

    def _on_send(self):
        username = self.username_input.text().strip()
        if not username:
            self._show_status(tr("forgot_password.username_required"), success=False)
            return

        from services.api_client import get_api_client
        from services.api_worker import ApiWorker

        api = get_api_client()
        if not api:
            self._show_status(tr("page.login.connection_error"), success=False)
            return

        self._set_sending(True)
        self._worker = ApiWorker(
            api.forgot_password, username, self.note_input.toPlainText().strip()
        )
        self._worker.finished.connect(self._on_send_finished)
        self._worker.error.connect(self._on_send_failed)
        self._worker.start()

    def _on_send_finished(self, result):
        self._set_sending(False)
        result = result if isinstance(result, dict) else {}
        if result.get("accepted"):
            self._sent = True
            self._show_status(result.get("message") or tr("forgot_password.sent"), success=True)
            # Request done: only closing is left
            self._send_btn.hide()
            self._cancel_btn.setText(tr("button.close"))
            self.username_input.setReadOnly(True)
            self.note_input.setReadOnly(True)
        else:
            self._show_status(result.get("message") or tr("forgot_password.too_many"), success=False)

    def _on_send_failed(self, message):
        logger.warning(f"Forgot password request failed: {message}")
        self._set_sending(False)
        self._show_status(tr("page.login.connection_error"), success=False)

    def _set_sending(self, sending: bool):
        self._send_btn.setEnabled(not sending)
        self._cancel_btn.setEnabled(not sending)
        self._send_btn.setText(tr("forgot_password.sending") if sending else tr("forgot_password.send"))

    def _show_status(self, text: str, success: bool):
        if success:
            style = """
                background-color: rgba(39, 174, 96, 30);
                color: #1E8449;
                padding: 8px 10px;
                border-radius: 8px;
                border: 1px solid rgba(39, 174, 96, 90);
            """
        else:
            style = """
                background-color: rgba(231, 76, 60, 38);
                color: #E74C3C;
                padding: 8px 10px;
                border-radius: 8px;
                border: 1px solid rgba(231, 76, 60, 102);
            """
        self._status.setStyleSheet(style)
        self._status.setText(text)
        self._status.show()

    def _hide_status(self):
        if not self._sent:
            self._status.hide()

    def reject(self):
        # Keep the dialog while the request is in flight
        if self._worker is not None and self._worker.isRunning():
            return
        super().reject()
