# -*- coding: utf-8 -*-
"""
Modification Reason Dialog — UC-006 S08.
Mandatory reason input before saving claim modifications.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class ModificationReasonDialog(QDialog):
    """S08: Requires a mandatory reason before saving claim modifications."""

    def __init__(self, changes_summary: list = None, parent=None):
        """
        Args:
            changes_summary: List of strings describing what was changed.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._changes_summary = changes_summary or []
        self._reason = ""
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("سبب التعديل")
        self.setMinimumSize(480, 360)
        self.setMaximumSize(600, 500)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: white;
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("سبب التعديل")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none;")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # Changes summary
        if self._changes_summary:
            summary_frame = QFrame()
            summary_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #F8FAFC;
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            summary_layout = QVBoxLayout(summary_frame)
            summary_layout.setContentsMargins(12, 8, 12, 8)
            summary_layout.setSpacing(4)

            summary_title = QLabel("التغييرات التي تمت:")
            summary_title.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.DemiBold))
            summary_title.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none;")
            summary_layout.addWidget(summary_title)

            for change in self._changes_summary:
                item = QLabel(f"  • {change}")
                item.setFont(create_font(size=FontManager.SIZE_SMALL))
                item.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none;")
                item.setWordWrap(True)
                summary_layout.addWidget(item)

            layout.addWidget(summary_frame)

        # Reason input
        reason_label = QLabel("يرجى إدخال سبب التعديل (إلزامي):")
        reason_label.setFont(create_font(size=FontManager.SIZE_BODY))
        reason_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none;")
        reason_label.setAlignment(Qt.AlignRight)
        layout.addWidget(reason_label)

        self._reason_input = QTextEdit()
        self._reason_input.setPlaceholderText("أدخل سبب التعديل هنا...")
        self._reason_input.setMinimumHeight(80)
        self._reason_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: white;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                font-family: 'IBM Plex Sans Arabic', 'Calibri';
            }}
            QTextEdit:focus {{
                border-color: {Colors.PRIMARY_BLUE};
            }}
        """)
        layout.addWidget(self._reason_input)

        # Error label (hidden initially)
        self._error_label = QLabel("سبب التعديل مطلوب")
        self._error_label.setStyleSheet("color: #EF4444; font-size: 11px; border: none;")
        self._error_label.setAlignment(Qt.AlignRight)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #F8FAFC;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("تأكيد وحفظ")
        confirm_btn.setFixedHeight(40)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #2A7BC8;
            }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def _on_confirm(self):
        reason = self._reason_input.toPlainText().strip()
        if not reason:
            self._error_label.show()
            self._reason_input.setStyleSheet(self._reason_input.styleSheet().replace(
                f"border: 1px solid {Colors.BORDER_DEFAULT}",
                "border: 1px solid #EF4444"
            ))
            return
        self._reason = reason
        self.accept()

    def get_reason(self) -> str:
        return self._reason
