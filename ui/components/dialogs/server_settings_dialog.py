# -*- coding: utf-8 -*-
"""
Server Settings Dialog - إعدادات سيرفر الخريطة
Allows user to configure tile server port from the UI.
"""

import socket
from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QLineEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QIntValidator

from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from app.config import load_local_settings, save_local_settings, get_tile_server_port


class ServerSettingsDialog(QDialog):
    """Dialog for configuring tile server port."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_port = get_tile_server_port()

        self.setModal(True)
        self.setFixedSize(440, 280)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        container = QFrame()
        container.setObjectName("settingsContainer")
        container.setLayoutDirection(Qt.RightToLeft)
        container.setStyleSheet("""
            QFrame#settingsContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#settingsContainer QLabel {
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

        # Title
        title = QLabel("إعدادات سيرفر الخريطة")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # Port input row
        port_row = QHBoxLayout()
        port_row.setSpacing(10)

        port_label = QLabel("رقم البورت:")
        port_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        port_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        port_row.addWidget(port_label)

        self._port_input = QLineEdit(str(self._current_port))
        self._port_input.setFixedSize(120, 36)
        self._port_input.setAlignment(Qt.AlignCenter)
        self._port_input.setValidator(QIntValidator(1, 65535))
        self._port_input.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._port_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFF;
                border: 1px solid #E5EAF6;
                border-radius: 8px;
                padding: 0 8px;
                color: #2C3E50;
            }
            QLineEdit:focus {
                border: 1px solid #3890DF;
            }
        """)
        port_row.addWidget(self._port_input)
        port_row.addStretch()

        layout.addLayout(port_row)

        # Test connection button + status
        test_row = QHBoxLayout()
        test_row.setSpacing(10)

        test_btn = self._create_button("اختبار الاتصال", primary=False)
        test_btn.setFixedSize(140, 40)
        test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(test_btn)

        self._status_label = QLabel("")
        self._status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        test_row.addWidget(self._status_label)
        test_row.addStretch()

        layout.addLayout(test_row)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        cancel_btn = self._create_button("إلغاء", primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = self._create_button("حفظ", primary=True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _test_connection(self):
        """Test TCP connection to the specified port."""
        port_text = self._port_input.text().strip()
        if not port_text:
            self._status_label.setText("أدخل رقم البورت")
            self._status_label.setStyleSheet(f"color: {Colors.ERROR};")
            return

        port = int(port_text)
        try:
            with socket.create_connection(("localhost", port), timeout=3):
                self._status_label.setText("متصل ✓")
                self._status_label.setStyleSheet(f"color: {Colors.SUCCESS};")
        except (socket.timeout, socket.error, OSError):
            self._status_label.setText("غير متصل ✗")
            self._status_label.setStyleSheet(f"color: {Colors.ERROR};")

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(140, 44)
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
                    border: 1px solid #E5E7EB;
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

        return btn

    def _on_save(self):
        """Save port to settings.json."""
        port_text = self._port_input.text().strip()
        if not port_text:
            return

        port = int(port_text)
        settings = load_local_settings()
        settings["tile_server_port"] = port
        save_local_settings(settings)
        self.accept()

    @staticmethod
    def show_settings(parent=None) -> Optional[int]:
        """Show dialog and return new port if saved, None if cancelled."""
        dialog = ServerSettingsDialog(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return get_tile_server_port()
        return None
