# -*- coding: utf-8 -*-
"""
Language Dialog — ديالوغ تغيير اللغة
Follows PasswordDialog/ConfirmationDialog container pattern (DRY).
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ui.design_system import Colors
from ui.font_utils import create_font, FontManager


class _LanguageOption(QWidget):
    """Radio-style language option: text + circle indicator."""

    def __init__(self, label: str, lang_code: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.lang_code = lang_code
        self._selected = selected

        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Text label
        self._text_label = QLabel(label)
        self._text_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        self._text_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        layout.addWidget(self._text_label)

        layout.addStretch()

        # Radio circle indicator
        self._indicator = QLabel()
        self._indicator.setFixedSize(20, 20)
        self._indicator.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._indicator)

        self._apply_style()

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self._indicator.setStyleSheet(f"""
                QLabel {{
                    background-color: {Colors.PRIMARY_BLUE};
                    border-radius: 10px;
                    border: 2px solid {Colors.PRIMARY_BLUE};
                }}
            """)
            # White inner dot via nested label
            self._indicator.setText("●")
            self._indicator.setStyleSheet(f"""
                QLabel {{
                    background-color: {Colors.PRIMARY_BLUE};
                    border-radius: 10px;
                    color: white;
                    font-size: 8px;
                }}
            """)
        else:
            self._indicator.setText("")
            self._indicator.setStyleSheet("""
                QLabel {
                    background-color: white;
                    border-radius: 10px;
                    border: 2px solid #D1D5DB;
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected = True
        super().mousePressEvent(event)


class LanguageDialog(QDialog):
    """Dialog for selecting application language."""

    def __init__(self, current_lang: str = "ar", parent=None):
        super().__init__(parent)
        self.selected_language = current_lang
        self._current_lang = current_lang

        self.setModal(True)
        self.setFixedSize(586, 237)  # 562+24 shadow margin
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
        container.setObjectName("langContainer")
        container.setLayoutDirection(Qt.RightToLeft)
        container.setStyleSheet("""
            QFrame#langContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#langContainer QLabel {
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
        layout.setSpacing(12)

        # Title
        title = QLabel("تغيير اللغة")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # Language options
        self._en_option = _LanguageOption(
            "English", "en", selected=(self._current_lang == "en")
        )
        self._ar_option = _LanguageOption(
            "العربية", "ar", selected=(self._current_lang == "ar")
        )

        self._en_option.mousePressEvent = lambda e: self._select("en")
        self._ar_option.mousePressEvent = lambda e: self._select("ar")

        layout.addWidget(self._en_option)
        layout.addWidget(self._ar_option)

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

    def _select(self, lang_code: str):
        """Select a language option."""
        self.selected_language = lang_code
        self._en_option.selected = (lang_code == "en")
        self._ar_option.selected = (lang_code == "ar")

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
        self.accept()

    @staticmethod
    def get_language(parent=None, current_lang="ar") -> Optional[str]:
        """Show language dialog and return selected language, or None if cancelled."""
        dialog = LanguageDialog(current_lang=current_lang, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.selected_language
        return None
