# -*- coding: utf-8 -*-
"""
Server Settings Dialog - إعدادات الاتصال
Allows user to configure tile server and API backend ports from the UI.
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
from app.config import (
    load_local_settings, save_local_settings,
    get_tile_server_port, get_api_port
)


class ServerSettingsDialog(QDialog):
    """Dialog for configuring tile server and API backend ports."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_tile_port = get_tile_server_port()
        self._current_api_port = get_api_port()

        self.setModal(True)
        self.setFixedSize(440, 400)
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
        layout.setSpacing(14)

        # Title
        title = QLabel("إعدادات الاتصال")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # --- Tile server section ---
        tile_header = QLabel("سيرفر الخريطة")
        tile_header.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        tile_header.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        tile_header.setAlignment(Qt.AlignRight)
        layout.addWidget(tile_header)

        tile_row = QHBoxLayout()
        tile_row.setSpacing(10)

        tile_label = QLabel("رقم البورت:")
        tile_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        tile_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        tile_row.addWidget(tile_label)

        self._tile_port_input = QLineEdit(str(self._current_tile_port))
        self._tile_port_input.setFixedSize(120, 36)
        self._tile_port_input.setAlignment(Qt.AlignCenter)
        self._tile_port_input.setValidator(QIntValidator(1, 65535))
        self._tile_port_input.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._tile_port_input.setStyleSheet(self._input_style())
        tile_row.addWidget(self._tile_port_input)

        tile_test_btn = self._create_button("اختبار", primary=False)
        tile_test_btn.setFixedSize(80, 36)
        tile_test_btn.clicked.connect(lambda: self._test_connection(self._tile_port_input, self._tile_status))
        tile_row.addWidget(tile_test_btn)

        self._tile_status = QLabel("")
        self._tile_status.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._tile_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        tile_row.addWidget(self._tile_status)
        tile_row.addStretch()

        layout.addLayout(tile_row)

        # --- API backend section ---
        api_header = QLabel("سيرفر البيانات (Backend)")
        api_header.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        api_header.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        api_header.setAlignment(Qt.AlignRight)
        layout.addWidget(api_header)

        api_row = QHBoxLayout()
        api_row.setSpacing(10)

        api_label = QLabel("رقم البورت:")
        api_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        api_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        api_row.addWidget(api_label)

        self._api_port_input = QLineEdit(str(self._current_api_port))
        self._api_port_input.setFixedSize(120, 36)
        self._api_port_input.setAlignment(Qt.AlignCenter)
        self._api_port_input.setValidator(QIntValidator(1, 65535))
        self._api_port_input.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._api_port_input.setStyleSheet(self._input_style())
        api_row.addWidget(self._api_port_input)

        api_test_btn = self._create_button("اختبار", primary=False)
        api_test_btn.setFixedSize(80, 36)
        api_test_btn.clicked.connect(lambda: self._test_connection(self._api_port_input, self._api_status))
        api_row.addWidget(api_test_btn)

        self._api_status = QLabel("")
        self._api_status.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._api_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        api_row.addWidget(self._api_status)
        api_row.addStretch()

        layout.addLayout(api_row)

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

    @staticmethod
    def _input_style() -> str:
        return """
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
        """

    def _test_connection(self, port_input: QLineEdit, status_label: QLabel):
        """Test TCP connection to the specified port."""
        port_text = port_input.text().strip()
        if not port_text:
            status_label.setText("أدخل رقم البورت")
            status_label.setStyleSheet(f"color: {Colors.ERROR};")
            return

        port = int(port_text)
        try:
            with socket.create_connection(("localhost", port), timeout=3):
                status_label.setText("متصل ✓")
                status_label.setStyleSheet(f"color: {Colors.SUCCESS};")
        except (socket.timeout, socket.error, OSError):
            status_label.setText("غير متصل ✗")
            status_label.setStyleSheet(f"color: {Colors.ERROR};")

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
        """Save both ports to settings.json."""
        tile_text = self._tile_port_input.text().strip()
        api_text = self._api_port_input.text().strip()
        if not tile_text or not api_text:
            return

        settings = load_local_settings()
        settings["tile_server_port"] = int(tile_text)
        settings["api_port"] = int(api_text)
        save_local_settings(settings)
        self.accept()

    @staticmethod
    def show_settings(parent=None) -> Optional[int]:
        """Show dialog and return new tile port if saved, None if cancelled."""
        dialog = ServerSettingsDialog(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return get_tile_server_port()
        return None
