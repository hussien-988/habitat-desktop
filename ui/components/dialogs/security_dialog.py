# -*- coding: utf-8 -*-
"""
Security Policies Dialog — ديالوغ سياسات الأمان
Follows PasswordDialog/LanguageDialog container pattern (DRY).
Custom spinbox arrows match unit_dialog / household_step pattern.
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSpinBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ui.components.icon import Icon
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager


class SecurityDialog(QDialog):
    """Dialog for configuring security policies."""

    def __init__(self, parent=None, session_days: int = 1, max_attempts: int = 12):
        super().__init__(parent)
        self.session_days = session_days
        self.max_attempts = max_attempts

        self.setModal(True)
        self.setFixedSize(613, 344)
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
        container.setObjectName("secContainer")
        container.setLayoutDirection(Qt.RightToLeft)
        container.setStyleSheet("""
            QFrame#secContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#secContainer QLabel {
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
        title = QLabel("سياسات الأمان")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # Field 1: Session duration
        field1 = self._create_field("مدة الجلسة", self.session_days, 1, 30, " Day")
        self._session_spin = field1["spin"]
        layout.addLayout(field1["layout"])

        # Field 2: Max login attempts
        field2 = self._create_field("عدد محاولات الدخول", self.max_attempts, 1, 99, "")
        self._attempts_spin = field2["spin"]
        layout.addLayout(field2["layout"])

        layout.addStretch()

        # Buttons (RTL: cancel first in code → appears left, save second → appears right)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        cancel_btn = self._create_button("الغاء", primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = self._create_button("حفظ", primary=True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _create_field(self, label_text: str, default: int, min_val: int, max_val: int, suffix: str) -> dict:
        col = QVBoxLayout()
        col.setSpacing(6)

        # Label above the field
        label = QLabel(label_text)
        label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        label.setAlignment(Qt.AlignRight)
        col.addWidget(label)

        # Spinbox
        spin = QSpinBox()
        spin.setMinimum(min_val)
        spin.setMaximum(max_val)
        spin.setValue(default)
        if suffix:
            spin.setSuffix(suffix)
        spin.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        spin.setAlignment(Qt.AlignCenter)

        # Wrap spinbox in styled container with custom arrows
        field_container = self._create_spinbox_with_arrows(spin)
        col.addWidget(field_container)

        return {"layout": col, "spin": spin}

    def _create_spinbox_with_arrows(self, spinbox: QSpinBox) -> QFrame:
        """Custom spinbox container with icon arrows (DRY: matches unit_dialog pattern)."""
        container = QFrame()
        container.setFixedHeight(42)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        container.setStyleSheet("""
            QFrame {
                border: 1px solid #E1E8ED;
                border-radius: 12px;
                background-color: #F0F7FF;
            }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Spinbox (no border, transparent bg — container provides styling)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 6px 12px;
                border: none;
                background: transparent;
                color: #2C3E50;
            }
            QSpinBox:focus {
                border: none;
                outline: 0;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
                border: none;
            }
        """)
        layout.addWidget(spinbox, 1)

        # Arrow column with border separator (right border in RTL since arrows appear on left)
        arrow_container = QFrame()
        arrow_container.setFixedWidth(30)
        arrow_container.setStyleSheet("""
            QFrame {
                border: none;
                border-right: 1px solid #E1E8ED;
                background: transparent;
                border-top-left-radius: 12px;
                border-bottom-left-radius: 12px;
            }
        """)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)

        # Up arrow
        up_label = QLabel()
        up_label.setFixedSize(30, 21)
        up_label.setAlignment(Qt.AlignCenter)
        up_pixmap = Icon.load_pixmap("^", size=10)
        if up_pixmap and not up_pixmap.isNull():
            up_label.setPixmap(up_pixmap)
        else:
            up_label.setText("^")
            up_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        up_label.setCursor(Qt.PointingHandCursor)
        up_label.mousePressEvent = lambda _: spinbox.stepUp()
        arrow_layout.addWidget(up_label)

        # Down arrow
        down_label = QLabel()
        down_label.setFixedSize(30, 21)
        down_label.setAlignment(Qt.AlignCenter)
        down_pixmap = Icon.load_pixmap("v", size=10)
        if down_pixmap and not down_pixmap.isNull():
            down_label.setPixmap(down_pixmap)
        else:
            down_label.setText("v")
            down_label.setStyleSheet("color: #9CA3AF; font-size: 10px; font-weight: bold; background: transparent;")
        down_label.setCursor(Qt.PointingHandCursor)
        down_label.mousePressEvent = lambda _: spinbox.stepDown()
        arrow_layout.addWidget(down_label)

        layout.addWidget(arrow_container)

        return container

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

    def _on_save(self):
        self.session_days = self._session_spin.value()
        self.max_attempts = self._attempts_spin.value()
        self.accept()

    @staticmethod
    def show_settings(parent=None, session_days: int = 1, max_attempts: int = 12) -> Optional[tuple]:
        """Show security policies dialog. Returns (session_days, max_attempts) or None."""
        dialog = SecurityDialog(parent=parent, session_days=session_days, max_attempts=max_attempts)
        if dialog.exec_() == QDialog.Accepted:
            return (dialog.session_days, dialog.max_attempts)
        return None
