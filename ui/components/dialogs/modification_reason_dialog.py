# -*- coding: utf-8 -*-
"""
Modification Reason Dialog — ديالوغ سبب التعديل
Mandatory reason input (min 10 chars) before saving claim modifications.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

_MIN_REASON_LENGTH = 10


class ModificationReasonDialog(QDialog):
    """S08: Requires a mandatory reason (min 10 chars) before saving claim modifications."""

    def __init__(self, changes_summary: list = None, parent=None):
        super().__init__(parent)
        self._changes_summary = changes_summary or []
        self._reason = ""

        self.setModal(True)
        self.setFixedSize(540, 440)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        # White container with shadow
        container = QFrame()
        container.setObjectName("reasonContainer")
        container.setStyleSheet("""
            QFrame#reasonContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#reasonContainer QLabel {
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
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(16)

        # Title (centered)
        title = QLabel("سبب التعديل")
        title.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Changes summary
        if self._changes_summary:
            summary_frame = QFrame()
            summary_frame.setObjectName("summaryFrame")
            summary_frame.setStyleSheet(f"""
                QFrame#summaryFrame {{
                    background-color: #F8FAFC;
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 10px;
                }}
                QFrame#summaryFrame QLabel {{
                    background-color: transparent;
                    border: none;
                }}
            """)
            summary_layout = QVBoxLayout(summary_frame)
            summary_layout.setContentsMargins(14, 10, 14, 10)
            summary_layout.setSpacing(4)

            summary_title = QLabel("التغييرات التي تمت:")
            summary_title.setFont(create_font(
                size=FontManager.SIZE_SMALL, weight=FontManager.WEIGHT_SEMIBOLD))
            summary_title.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            summary_layout.addWidget(summary_title)

            for change in self._changes_summary:
                item = QLabel(f"  \u2022 {change}")
                item.setFont(create_font(size=FontManager.SIZE_SMALL))
                item.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
                item.setWordWrap(True)
                summary_layout.addWidget(item)

            layout.addWidget(summary_frame)

        # Reason label
        reason_label = QLabel(f"سبب التعديل (إلزامي — {_MIN_REASON_LENGTH} أحرف على الأقل):")
        reason_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        reason_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(reason_label)

        # Reason input
        self._reason_input = QTextEdit()
        self._reason_input.setLayoutDirection(Qt.RightToLeft)
        self._reason_input.setPlaceholderText("أدخل سبب التعديل هنا...")
        self._reason_input.setMinimumHeight(90)
        self._reason_input.setMaximumHeight(120)
        self._reason_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: #f0f7ff;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
                font-family: 'IBM Plex Sans Arabic', 'Calibri';
            }}
            QTextEdit:focus {{
                border: 2px solid {Colors.PRIMARY_BLUE};
            }}
        """)
        layout.addWidget(self._reason_input)

        # Error label (hidden initially)
        self._error_label = QLabel()
        self._error_label.setFont(create_font(size=9))
        self._error_label.setStyleSheet("color: #EF4444;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Buttons (centered like LogoutDialog)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        confirm_btn = self._create_button("تأكيد وحفظ", primary=True)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        cancel_btn = self._create_button("إلغاء", primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(170, 50)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))

        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white;
                    border: none;
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    background-color: #2A7BC8;
                }}
                QPushButton:pressed {{
                    background-color: #1E6CB3;
                }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #6B7280;
                    border: none;
                    border-radius: 8px;
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

    def _on_confirm(self):
        reason = self._reason_input.toPlainText().strip()
        if not reason:
            self._show_error("سبب التعديل مطلوب")
            return
        if len(reason) < _MIN_REASON_LENGTH:
            self._show_error(
                f"سبب التعديل يجب أن يكون {_MIN_REASON_LENGTH} أحرف على الأقل"
                f" (الحالي: {len(reason)})"
            )
            return
        self._reason = reason
        self.accept()

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.show()
        self._reason_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: #f0f7ff;
                border: 2px solid #EF4444;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
                font-family: 'IBM Plex Sans Arabic', 'Calibri';
            }}
            QTextEdit:focus {{
                border: 2px solid #EF4444;
            }}
        """)

    def get_reason(self) -> str:
        return self._reason
