# -*- coding: utf-8 -*-
"""
Server Settings Dialog — Layered Dark design
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
from PyQt5.QtGui import QColor, QFont, QCursor

from ui.design_system import Colors, Spacing, ButtonDimensions, ScreenScale
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
        from PyQt5.QtWidgets import QApplication
        _scr = QApplication.primaryScreen().availableGeometry()
        self.resize(min(540, int(_scr.width() * 0.45)), min(480, int(_scr.height() * 0.55)))
        self.setMinimumSize(400, 360)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    # -- UI --

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        container = QFrame()
        container.setObjectName("settingsContainer")
        container.setLayoutDirection(get_layout_direction())
        container.setStyleSheet("""
            QFrame#settingsContainer {
                background-color: rgba(10, 20, 40, 245);
                border: 1px solid rgba(56, 144, 223, 25);
                border-radius: 16px;
            }
            QFrame#settingsContainer QLabel {
                background-color: transparent;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 80))
        container.setGraphicsEffect(shadow)

        main_lay = QVBoxLayout(container)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # -- Blue gradient header banner --
        header = QFrame()
        header.setObjectName("headerBanner")
        header.setFixedHeight(ScreenScale.h(54))
        header.setStyleSheet("""
            QFrame#headerBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1A3A6B, stop:0.5 #2A5A9B, stop:1 #1A3A6B);
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(24, 0, 12, 0)
        header_lay.setSpacing(0)

        title = QLabel(tr("dialog.server_settings.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet("color: white; background: transparent;")
        header_lay.addWidget(title)

        header_lay.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(200, 220, 255, 150);
                background: transparent;
                border: none;
                font-size: 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: white;
                background: rgba(255, 59, 48, 0.60);
            }
        """)
        close_btn.clicked.connect(self.reject)
        header_lay.addWidget(close_btn)

        main_lay.addWidget(header)

        # -- Content area --
        content = QFrame()
        content.setObjectName("contentArea")
        content.setStyleSheet("QFrame#contentArea { background: transparent; }")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # -- Tile server section --
        self._tile_url_input, self._tile_test_btn, self._tile_status = \
            self._build_section(
                layout,
                icon="\u2295",
                header=tr("dialog.server_settings.tile_header"),
                description=tr("dialog.server_settings.tile_description"),
                value=get_tile_server_url(),
                placeholder=_DEFAULT_TILE_URL,
                on_test=lambda: self._start_test(is_tile=True),
            )
        self._tile_url_input.textChanged.connect(lambda: self._on_url_changed(True))

        # -- API backend section --
        self._api_url_input, self._api_test_btn, self._api_status = \
            self._build_section(
                layout,
                icon="\u25C6",
                header=tr("dialog.server_settings.api_header"),
                description=tr("dialog.server_settings.api_description"),
                value=get_api_server_url(),
                placeholder=_DEFAULT_API_SERVER_URL,
                on_test=lambda: self._start_test(is_tile=False),
            )
        self._api_url_input.textChanged.connect(lambda: self._on_url_changed(False))

        layout.addStretch()

        # -- Buttons row --
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        reset_btn = self._make_btn(tr("dialog.server_settings.restore_defaults"), "secondary", width=170)
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
        main_lay.addWidget(content, 1)
        outer.addWidget(container)

    def _build_section(self, parent_layout, icon, header, description, value, placeholder, on_test):
        """Build one server section inside a raised card with left accent border."""
        section = QFrame()
        section.setObjectName("sectionCard")
        section.setStyleSheet("""
            QFrame#sectionCard {
                background-color: rgba(20, 40, 75, 180);
                border: 1px solid rgba(56, 144, 223, 20);
                border-left: 3px solid rgba(56, 144, 223, 100);
                border-radius: 10px;
            }
            QFrame#sectionCard QLabel {
                background: transparent;
            }
        """)

        card_lay = QVBoxLayout(section)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(6)

        header_lbl = QLabel(f"{icon}  {header}")
        header_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        header_lbl.setStyleSheet("color: white;")
        card_lay.addWidget(header_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        desc_lbl.setStyleSheet("color: #8BACC8;")
        card_lay.addWidget(desc_lbl)

        card_lay.addSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(8)

        url_input = QLineEdit(value)
        url_input.setFixedHeight(ScreenScale.h(40))
        url_input.setAlignment(Qt.AlignLeft)
        url_input.setLayoutDirection(Qt.LeftToRight)
        url_input.setPlaceholderText(placeholder)
        url_input.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        url_input.setStyleSheet(self._input_style())
        row.addWidget(url_input, 1)

        test_btn = self._make_btn(tr("dialog.server_settings.test"), "secondary", width=80, height=40)
        test_btn.clicked.connect(on_test)
        row.addWidget(test_btn)

        card_lay.addLayout(row)

        status_lbl = QLabel("")
        status_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        status_lbl.setStyleSheet("color: #8BACC8;")
        card_lay.addWidget(status_lbl)

        parent_layout.addWidget(section)
        return url_input, test_btn, status_lbl

    # -- Connection testing --

    def _start_test(self, is_tile: bool):
        url_input = self._tile_url_input if is_tile else self._api_url_input
        test_btn = self._tile_test_btn if is_tile else self._api_test_btn
        status_lbl = self._tile_status if is_tile else self._api_status

        url = url_input.text().strip()
        if not url:
            status_lbl.setText(tr("dialog.server_settings.enter_url"))
            status_lbl.setStyleSheet("color: #E53935;")
            return

        parsed = urlparse(url)
        if not parsed.hostname:
            status_lbl.setText(tr("dialog.server_settings.invalid_url"))
            status_lbl.setStyleSheet("color: #E53935;")
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
            status_lbl.setText("\u25CF " + tr("dialog.server_settings.connected_ok"))
            status_lbl.setStyleSheet("color: #66BB6A;")
            url_input.setStyleSheet(self._input_style(border_color="rgba(102, 187, 106, 150)"))
            if is_tile:
                self._tile_ok = True
            else:
                self._api_ok = True
        else:
            status_lbl.setText("\u25CF " + tr("dialog.server_settings.disconnected_fail"))
            status_lbl.setStyleSheet("color: #EF5350;")
            url_input.setStyleSheet(self._input_style(border_color="rgba(239, 83, 80, 150)"))
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

    # -- Actions --

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

    # -- Styles --

    @staticmethod
    def _input_style(border_color=None) -> str:
        bc = border_color or "rgba(56, 144, 223, 80)"
        return f"""
            QLineEdit {{
                background-color: rgba(230, 240, 255, 15);
                border: 1.5px solid {bc};
                border-radius: 8px;
                padding: 0 12px;
                color: white;
                selection-background-color: rgba(56, 144, 223, 100);
            }}
            QLineEdit:focus {{
                border: 1.5px solid rgba(56, 144, 223, 180);
                background-color: rgba(230, 240, 255, 25);
            }}
            QLineEdit::placeholder {{
                color: rgba(139, 172, 200, 130);
            }}
        """

    @staticmethod
    def _make_btn(text: str, style: str, width: int = 110, height: int = 44) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumWidth(width)
        btn.setFixedHeight(height)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFont(create_font(size=10, weight=QFont.Medium))

        if style == "primary":
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
                QPushButton:disabled {
                    background: rgba(56, 144, 223, 40);
                    color: rgba(255, 255, 255, 80);
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(30, 50, 85, 200);
                    color: rgba(180, 200, 230, 220);
                    border: 1px solid rgba(56, 144, 223, 60);
                    border-radius: 10px;
                }
                QPushButton:hover {
                    background: rgba(40, 65, 110, 220);
                    color: white;
                    border-color: rgba(56, 144, 223, 120);
                }
                QPushButton:pressed {
                    background: rgba(25, 45, 75, 230);
                }
                QPushButton:disabled {
                    background: rgba(20, 35, 60, 180);
                    color: rgba(139, 172, 200, 60);
                    border-color: rgba(56, 144, 223, 15);
                }
            """)
        return btn

    # -- Public API --

    @staticmethod
    def show_settings(parent=None) -> Optional[bool]:
        """Show dialog. Returns True if saved, None if cancelled."""
        dialog = ServerSettingsDialog(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return True
        return None
