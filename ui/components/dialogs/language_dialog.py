# -*- coding: utf-8 -*-
"""
Language Dialog — ديالوغ تغيير اللغة
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction


class _LanguageOption(QWidget):
    """Radio-style language option: text + circle indicator."""

    def __init__(self, label: str, lang_code: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.lang_code = lang_code
        self._selected = selected

        self.setFixedHeight(ScreenScale.h(40))
        self.setCursor(Qt.PointingHandCursor)
        self.setLayoutDirection(get_layout_direction())

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
        self._indicator.setFixedSize(ScreenScale.h(20), ScreenScale.h(20))
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
        from PyQt5.QtWidgets import QApplication
        _scr = QApplication.primaryScreen().availableGeometry()
        self.resize(min(586, int(_scr.width() * 0.45)), min(237, int(_scr.height() * 0.30)))
        self.setMinimumSize(420, 200)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        # White container
        container = QFrame()
        container.setObjectName("langContainer")
        container.setLayoutDirection(get_layout_direction())
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
        title = QLabel(tr("dialog.language.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # Language options
        self._en_option = _LanguageOption(
            "English", "en", selected=(self._current_lang == "en")
        )
        self._ar_option = _LanguageOption(
            tr("dialog.language.arabic"), "ar", selected=(self._current_lang == "ar")
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

        cancel_btn = self._create_button(tr("button.cancel"), primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = self._create_button(tr("button.save"), primary=True)
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

    def _on_save(self):
        self.accept()

    @staticmethod
    def get_language(parent=None, current_lang="ar") -> Optional[str]:
        """Show language dialog and return selected language, or None if cancelled."""
        dialog = LanguageDialog(current_lang=current_lang, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.selected_language
        return None
