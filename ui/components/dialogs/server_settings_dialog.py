# -*- coding: utf-8 -*-
"""
Server Settings Dialog
Configure tile server and API backend URLs with non-blocking connection testing.
"""

import socket
from typing import Optional
from urllib.parse import urlparse

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from ui.design_system import Colors, Spacing, ButtonDimensions
from ui.font_utils import create_font, FontManager
from app.config import (
    load_local_settings, save_local_settings,
    get_tile_server_url, get_api_server_url
)
from services.translation_manager import tr, get_layout_direction

_DEFAULT_TILE_URL = "http://localhost:5000"
_DEFAULT_API_SERVER_URL = "http://localhost:8080"


class _ConnectionWorker(QThread):
    """Non-blocking worker for testing server connectivity."""
    finished = pyqtSignal(bool, str)

    def __init__(self, url: str, is_api: bool):
        super().__init__()
        self._url = url
        self._is_api = is_api

    def run(self):
        try:
            parsed = urlparse(self._url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            with socket.create_connection((host, port), timeout=5):
                pass
            if self._is_api:
                import requests
                requests.get(
                    self._url.rstrip("/") + "/v1/Health",
                    timeout=5, verify=False
                )
            self.finished.emit(True, tr("dialog.server_settings.connected"))
        except Exception:
            self.finished.emit(False, tr("dialog.server_settings.disconnected"))


class ServerSettingsDialog(QDialog):
    """Dialog for configuring tile server and API backend URLs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tile_ok = False
        self._api_ok = False
        self._workers = []

        self.setModal(True)
        self.setFixedSize(520, 420)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        container = QFrame()
        container.setObjectName("settingsContainer")
        container.setLayoutDirection(get_layout_direction())
        container.setStyleSheet(f"""
            QFrame#settingsContainer {{
                background-color: #FFFFFF;
                border-radius: {ButtonDimensions.DIALOG_BORDER_RADIUS}px;
            }}
            QFrame#settingsContainer QLabel {{
                background-color: transparent;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            ButtonDimensions.DIALOG_PADDING,
            ButtonDimensions.DIALOG_PADDING,
            ButtonDimensions.DIALOG_PADDING,
            ButtonDimensions.DIALOG_PADDING,
        )
        layout.setSpacing(Spacing.SM)

        # ── Title ──
        title = QLabel(tr("dialog.server_settings.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)
        layout.addSpacing(Spacing.XS)

        # ── Tile server section ──
        self._tile_url_input, self._tile_test_btn, self._tile_status = \
            self._build_section(
                layout,
                header=tr("dialog.server_settings.tile_header"),
                description=tr("dialog.server_settings.tile_description"),
                value=get_tile_server_url(),
                placeholder=_DEFAULT_TILE_URL,
                on_test=lambda: self._start_test(is_tile=True),
            )
        self._tile_url_input.textChanged.connect(lambda: self._on_url_changed(True))

        layout.addSpacing(Spacing.SM)

        # ── API backend section ──
        self._api_url_input, self._api_test_btn, self._api_status = \
            self._build_section(
                layout,
                header=tr("dialog.server_settings.api_header"),
                description=tr("dialog.server_settings.api_description"),
                value=get_api_server_url(),
                placeholder=_DEFAULT_API_SERVER_URL,
                on_test=lambda: self._start_test(is_tile=False),
            )
        self._api_url_input.textChanged.connect(lambda: self._on_url_changed(False))

        layout.addStretch()

        # ── Buttons row ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.SM)

        reset_btn = self._make_btn(tr("dialog.server_settings.restore_defaults"), "secondary", width=140)
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        cancel_btn = self._make_btn(tr("button.cancel"), "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._save_btn = self._make_btn(tr("button.save"), "primary")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)

        layout.addLayout(btn_layout)
        outer.addWidget(container)

    def _build_section(self, parent_layout, header, description, value, placeholder, on_test):
        """Build one server section (header + description + URL input + test btn + status)."""
        header_lbl = QLabel(header)
        header_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        header_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        header_lbl.setAlignment(Qt.AlignRight)
        parent_layout.addWidget(header_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        desc_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        desc_lbl.setAlignment(Qt.AlignRight)
        parent_layout.addWidget(desc_lbl)

        row = QHBoxLayout()
        row.setSpacing(Spacing.SM)

        url_input = QLineEdit(value)
        url_input.setFixedHeight(38)
        url_input.setAlignment(Qt.AlignLeft)
        url_input.setLayoutDirection(Qt.LeftToRight)
        url_input.setPlaceholderText(placeholder)
        url_input.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        url_input.setStyleSheet(self._input_style())
        row.addWidget(url_input, 1)

        test_btn = self._make_btn(tr("dialog.server_settings.test"), "secondary", width=80, height=38)
        test_btn.clicked.connect(on_test)
        row.addWidget(test_btn)

        status_lbl = QLabel("")
        status_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        status_lbl.setFixedWidth(90)
        status_lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(status_lbl)

        parent_layout.addLayout(row)
        return url_input, test_btn, status_lbl

    # ── Connection testing ──────────────────────────────────────────

    def _start_test(self, is_tile: bool):
        url_input = self._tile_url_input if is_tile else self._api_url_input
        test_btn = self._tile_test_btn if is_tile else self._api_test_btn
        status_lbl = self._tile_status if is_tile else self._api_status

        url = url_input.text().strip()
        if not url:
            status_lbl.setText(tr("dialog.server_settings.enter_url"))
            status_lbl.setStyleSheet(f"color: {Colors.ERROR};")
            return

        parsed = urlparse(url)
        if not parsed.hostname:
            status_lbl.setText(tr("dialog.server_settings.invalid_url"))
            status_lbl.setStyleSheet(f"color: {Colors.ERROR};")
            return

        test_btn.setEnabled(False)
        test_btn.setText(tr("dialog.server_settings.testing"))
        status_lbl.setText("")
        url_input.setStyleSheet(self._input_style())

        worker = _ConnectionWorker(url, is_api=not is_tile)
        worker.finished.connect(lambda ok, msg: self._on_test_done(ok, msg, is_tile))
        self._workers.append(worker)
        worker.start()

    def _on_test_done(self, success: bool, message: str, is_tile: bool):
        test_btn = self._tile_test_btn if is_tile else self._api_test_btn
        status_lbl = self._tile_status if is_tile else self._api_status
        url_input = self._tile_url_input if is_tile else self._api_url_input

        test_btn.setEnabled(True)
        test_btn.setText(tr("dialog.server_settings.test"))

        if success:
            status_lbl.setText(tr("dialog.server_settings.connected_ok"))
            status_lbl.setStyleSheet(f"color: {Colors.SUCCESS};")
            url_input.setStyleSheet(self._input_style(border_color=Colors.SUCCESS))
            if is_tile:
                self._tile_ok = True
            else:
                self._api_ok = True
        else:
            status_lbl.setText(tr("dialog.server_settings.disconnected_fail"))
            status_lbl.setStyleSheet(f"color: {Colors.ERROR};")
            url_input.setStyleSheet(self._input_style(border_color=Colors.ERROR))
            if is_tile:
                self._tile_ok = False
            else:
                self._api_ok = False

        self._update_save_btn()

    def _on_url_changed(self, is_tile: bool):
        """Reset test result when user edits the URL."""
        status_lbl = self._tile_status if is_tile else self._api_status
        url_input = self._tile_url_input if is_tile else self._api_url_input

        status_lbl.setText("")
        url_input.setStyleSheet(self._input_style())

        if is_tile:
            self._tile_ok = False
        else:
            self._api_ok = False
        self._update_save_btn()

    def _update_save_btn(self):
        self._save_btn.setEnabled(self._tile_ok or self._api_ok)

    # ── Actions ─────────────────────────────────────────────────────

    def _on_save(self):
        settings = load_local_settings()
        settings.pop("tile_server_port", None)
        settings.pop("api_port", None)
        settings.pop("api_base_url", None)

        if self._tile_ok:
            tile_url = self._tile_url_input.text().strip()
            if tile_url:
                settings["tile_server_url"] = tile_url
                from services.tile_server_manager import TileServerManager
                TileServerManager.reset()

        if self._api_ok:
            api_url = self._api_url_input.text().strip()
            if api_url:
                settings["api_server_url"] = api_url
                from services.api_client import reset_api_client
                reset_api_client()

        save_local_settings(settings)
        self.accept()

    def _on_reset(self):
        self._tile_url_input.setText(_DEFAULT_TILE_URL)
        self._api_url_input.setText(_DEFAULT_API_SERVER_URL)

    # ── Styles ──────────────────────────────────────────────────────

    @staticmethod
    def _input_style(border_color=None) -> str:
        bc = border_color or Colors.INPUT_BORDER
        return f"""
            QLineEdit {{
                background-color: {Colors.INPUT_BG};
                border: 1.5px solid {bc};
                border-radius: 8px;
                padding: 0 10px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {Colors.INPUT_BORDER_FOCUS};
            }}
            QLineEdit::placeholder {{
                color: {Colors.INPUT_PLACEHOLDER};
            }}
        """

    @staticmethod
    def _make_btn(text: str, style: str, width: int = 110, height: int = 44) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(width, height)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=QFont.Medium))

        if style == "primary":
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white;
                    border: none;
                    border-radius: {ButtonDimensions.DIALOG_BUTTON_BORDER_RADIUS}px;
                }}
                QPushButton:hover {{
                    background-color: #2D7BC9;
                }}
                QPushButton:pressed {{
                    background-color: #2468B0;
                }}
                QPushButton:disabled {{
                    background-color: #B0C4DE;
                    color: #E8EDF2;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: white;
                    color: {Colors.TEXT_SECONDARY};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {ButtonDimensions.DIALOG_BUTTON_BORDER_RADIUS}px;
                }}
                QPushButton:hover {{
                    background-color: #F9FAFB;
                }}
                QPushButton:pressed {{
                    background-color: #F3F4F6;
                }}
                QPushButton:disabled {{
                    background-color: #F5F5F5;
                    color: #C0C0C0;
                    border-color: #E8E8E8;
                }}
            """)
        return btn

    # ── Public API ──────────────────────────────────────────────────

    @staticmethod
    def show_settings(parent=None) -> Optional[bool]:
        """Show dialog. Returns True if saved, None if cancelled."""
        dialog = ServerSettingsDialog(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return True
        return None
