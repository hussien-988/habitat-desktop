# -*- coding: utf-8 -*-
"""Slide-up bottom sheet replacing all confirmation and choice dialogs."""

from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QSizePolicy,
    QGraphicsOpacityEffect, QApplication
)
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal, pyqtProperty, QTimer
)
from PyQt5.QtGui import QColor, QPainter

from ui.design_system import (
    BottomSheetDimensions as BSD, Colors, BorderRadius,
    Typography, AnimationTimings, Spacing, ScreenScale
)
from ui.font_utils import create_font, FontManager
from services.translation_manager import get_layout_direction, tr


class _Overlay(QWidget):
    """Semi-transparent overlay behind the sheet."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def set_opacity(self, val):
        self._opacity = val
        self.update()

    def get_opacity(self):
        return self._opacity

    opacity_val = pyqtProperty(float, get_opacity, set_opacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(15, 23, 42)
        color.setAlphaF(0.6 * self._opacity)
        painter.fillRect(self.rect(), color)
        painter.end()

    def mousePressEvent(self, event):
        self.clicked.emit()


class BottomSheet(QWidget):
    """Slide-up bottom sheet container."""

    confirmed = pyqtSignal()
    cancelled = pyqtSignal()
    choice_made = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay = _Overlay(self)
        self._overlay.clicked.connect(self._on_cancel)
        self._panel = QFrame(self)
        self._panel.setObjectName("bottom_sheet_panel")
        self._anim_panel = None
        self._anim_overlay = None
        self._result = None
        self._form_fields = {}
        self._setup_panel()
        self.hide()

    def _setup_panel(self):
        self._panel.setStyleSheet(f"""
            QFrame#bottom_sheet_panel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F0F5FB, stop:1 #E8EFF8
                );
                border-top-left-radius: {BSD.BORDER_RADIUS}px;
                border-top-right-radius: {BSD.BORDER_RADIUS}px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top: 1px solid rgba(56, 144, 223, 0.20);
            }}
        """)
        self._panel_layout = QVBoxLayout(self._panel)
        self._panel_layout.setContentsMargins(
            BSD.PADDING_H, BSD.HANDLE_MARGIN_TOP + BSD.HANDLE_HEIGHT + 8,
            BSD.PADDING_H, BSD.PADDING_V
        )
        self._panel_layout.setSpacing(Spacing.MD)

        self._handle = QFrame(self._panel)
        self._handle.setFixedSize(BSD.HANDLE_WIDTH, BSD.HANDLE_HEIGHT)
        self._handle.setStyleSheet(f"""
            background-color: {BSD.HANDLE_COLOR};
            border-radius: {BSD.HANDLE_HEIGHT // 2}px;
        """)

        self._title_lbl = QLabel()
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setFont(
            create_font(size=FontManager.SIZE_HEADING,
                        weight=FontManager.WEIGHT_SEMIBOLD)
        )
        self._title_lbl.setStyleSheet("color: #1A365D;")
        self._panel_layout.addWidget(self._title_lbl)

        self._message_lbl = QLabel()
        self._message_lbl.setWordWrap(True)
        self._message_lbl.setAlignment(Qt.AlignCenter)
        self._message_lbl.setFont(
            create_font(size=FontManager.SIZE_BODY,
                        weight=FontManager.WEIGHT_REGULAR)
        )
        self._message_lbl.setStyleSheet("color: #4A6FA5;")
        self._panel_layout.addWidget(self._message_lbl)

        self._choices_container = QVBoxLayout()
        self._choices_container.setSpacing(Spacing.SM)
        self._panel_layout.addLayout(self._choices_container)

        self._form_container = QVBoxLayout()
        self._form_container.setSpacing(Spacing.MD)
        self._panel_layout.addLayout(self._form_container)

        self._buttons_layout = QHBoxLayout()
        self._buttons_layout.setSpacing(BSD.BUTTON_GAP)
        self._panel_layout.addLayout(self._buttons_layout)

    def _clear_dynamic(self):
        while self._choices_container.count():
            item = self._choices_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        while self._form_container.count():
            item = self._form_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        while self._buttons_layout.count():
            item = self._buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._form_fields.clear()
        self._message_lbl.setVisible(False)

    def show_confirm(self, title: str, message: str,
                     confirm_text: str = "", cancel_text: str = "",
                     confirm_danger: bool = False):
        self._clear_dynamic()
        self.setLayoutDirection(get_layout_direction())

        self._title_lbl.setText(title)
        self._message_lbl.setText(message)
        self._message_lbl.setVisible(True)

        if not confirm_text:
            confirm_text = tr("button.confirm")
        if not cancel_text:
            cancel_text = tr("button.cancel")

        cancel_btn = self._make_button(cancel_text, "secondary")
        cancel_btn.clicked.connect(self._on_cancel)
        self._buttons_layout.addWidget(cancel_btn)

        confirm_btn = self._make_button(
            confirm_text, "danger" if confirm_danger else "primary"
        )
        confirm_btn.clicked.connect(self._on_confirm)
        self._buttons_layout.addWidget(confirm_btn)

        self._animate_open()

    def show_choices(self, title: str, choices: list):
        self._clear_dynamic()
        self.setLayoutDirection(get_layout_direction())

        self._title_lbl.setText(title)

        for choice_id, choice_text in choices:
            btn = QPushButton(choice_text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ScreenScale.h(48))
            btn.setFont(
                create_font(size=FontManager.SIZE_BODY,
                            weight=FontManager.WEIGHT_MEDIUM)
            )
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(56, 144, 223, 0.06);
                    color: #1A365D;
                    border: 1px solid rgba(56, 144, 223, 0.25);
                    border-radius: {BSD.BUTTON_RADIUS}px;
                    padding: 0 {Spacing.MD}px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: rgba(56, 144, 223, 0.12);
                    border-color: rgba(56, 144, 223, 0.50);
                    color: #1A365D;
                }}
            """)
            btn.clicked.connect(lambda checked, cid=choice_id: self._on_choice(cid))
            self._choices_container.addWidget(btn)

        self._animate_open()

    def show_form(self, title: str, fields: list,
                  submit_text: str = "", cancel_text: str = ""):
        self._clear_dynamic()
        self.setLayoutDirection(get_layout_direction())

        self._title_lbl.setText(title)

        if not submit_text:
            submit_text = "\u0625\u0631\u0633\u0627\u0644"
        if not cancel_text:
            cancel_text = "\u0625\u0644\u063A\u0627\u0621"

        for field_id, field_label, field_type in fields:
            row = QVBoxLayout()
            row.setSpacing(4)

            lbl = QLabel(field_label)
            lbl.setFont(
                create_font(size=FontManager.SIZE_BODY,
                            weight=FontManager.WEIGHT_MEDIUM)
            )
            lbl.setStyleSheet("color: #2C5282;")
            row.addWidget(lbl)

            if field_type == "multiline":
                widget = QTextEdit()
                widget.setFixedHeight(ScreenScale.h(80))
            else:
                widget = QLineEdit()
                widget.setFixedHeight(ScreenScale.h(42))

            widget.setStyleSheet(f"""
                background: #FFFFFF;
                border: 1px solid rgba(56, 144, 223, 0.30);
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                font-size: {Typography.SIZE_BODY}px;
                color: #1A365D;
            """)
            row.addWidget(widget)
            self._form_container.addLayout(row)
            self._form_fields[field_id] = widget

        cancel_btn = self._make_button(cancel_text, "secondary")
        cancel_btn.clicked.connect(self._on_cancel)
        self._buttons_layout.addWidget(cancel_btn)

        submit_btn = self._make_button(submit_text, "primary")
        submit_btn.clicked.connect(self._on_confirm)
        self._buttons_layout.addWidget(submit_btn)

        self._animate_open()

    def get_form_data(self) -> dict:
        data = {}
        for fid, widget in self._form_fields.items():
            if isinstance(widget, QTextEdit):
                data[fid] = widget.toPlainText()
            else:
                data[fid] = widget.text()
        return data

    def _make_button(self, text: str, variant: str = "primary") -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(BSD.BUTTON_HEIGHT)
        btn.setFont(
            create_font(size=FontManager.SIZE_BODY,
                        weight=FontManager.WEIGHT_SEMIBOLD)
        )
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if variant == "primary":
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white;
                    border: none;
                    border-radius: {BSD.BUTTON_RADIUS}px;
                }}
                QPushButton:hover {{
                    background-color: #2A7BC9;
                }}
            """)
        elif variant == "danger":
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.ERROR};
                    color: white;
                    border: none;
                    border-radius: {BSD.BUTTON_RADIUS}px;
                }}
                QPushButton:hover {{
                    background-color: #C0392B;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(56, 144, 223, 0.06);
                    color: #2C5282;
                    border: 1px solid rgba(56, 144, 223, 0.25);
                    border-radius: {BSD.BUTTON_RADIUS}px;
                }}
                QPushButton:hover {{
                    background-color: rgba(56, 144, 223, 0.12);
                    border-color: rgba(56, 144, 223, 0.45);
                }}
            """)
        return btn

    def _animate_open(self):
        if self.parent():
            self.resize(self.parent().size())
        self._overlay.resize(self.size())
        self._overlay.set_opacity(0.0)

        panel_w = min(self.width() - 32, BSD.MAX_WIDTH)
        self._panel.setFixedWidth(panel_w)
        self._panel.adjustSize()
        panel_h = self._panel.sizeHint().height()
        self._panel.setFixedHeight(panel_h)

        x = (self.width() - panel_w) // 2
        self._panel_target_y = self.height() - panel_h
        self._panel.move(x, self.height())

        self._handle.move(
            (panel_w - BSD.HANDLE_WIDTH) // 2,
            BSD.HANDLE_MARGIN_TOP
        )

        self.show()
        self.raise_()

        self._anim_overlay = QPropertyAnimation(self._overlay, b"opacity_val", self)
        self._anim_overlay.setDuration(AnimationTimings.SLIDE_UP)
        self._anim_overlay.setStartValue(0.0)
        self._anim_overlay.setEndValue(1.0)
        self._anim_overlay.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_panel = QPropertyAnimation(self._panel, b"pos", self)
        self._anim_panel.setDuration(AnimationTimings.SLIDE_UP)
        self._anim_panel.setStartValue(QPoint(x, self.height()))
        self._anim_panel.setEndValue(QPoint(x, self._panel_target_y))
        self._anim_panel.setEasingCurve(QEasingCurve.OutQuart)

        self._anim_overlay.start()
        self._anim_panel.start()

    def _animate_close(self, callback=None):
        x = self._panel.x()

        self._anim_overlay = QPropertyAnimation(self._overlay, b"opacity_val", self)
        self._anim_overlay.setDuration(AnimationTimings.FADE_OUT)
        self._anim_overlay.setStartValue(self._overlay.get_opacity())
        self._anim_overlay.setEndValue(0.0)

        self._anim_panel = QPropertyAnimation(self._panel, b"pos", self)
        self._anim_panel.setDuration(AnimationTimings.FADE_OUT + 50)
        self._anim_panel.setStartValue(self._panel.pos())
        self._anim_panel.setEndValue(QPoint(x, self.height()))
        self._anim_panel.setEasingCurve(QEasingCurve.InCubic)

        if callback:
            self._anim_panel.finished.connect(callback)
        self._anim_panel.finished.connect(self.hide)

        self._anim_overlay.start()
        self._anim_panel.start()

    def _on_confirm(self):
        self._result = "confirmed"
        self._animate_close(lambda: self.confirmed.emit())

    def _on_cancel(self):
        self._result = "cancelled"
        self._animate_close(lambda: self.cancelled.emit())

    def _on_choice(self, choice_id: str):
        self._result = choice_id
        self._animate_close(lambda: self.choice_made.emit(choice_id))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.resize(self.size())

    @staticmethod
    def confirm(parent: QWidget, title: str, message: str,
                confirm_text: str = "", cancel_text: str = "",
                confirm_danger: bool = False) -> 'BottomSheet':
        sheet = BottomSheet(parent)
        sheet.show_confirm(title, message, confirm_text, cancel_text,
                          confirm_danger)
        return sheet

    @staticmethod
    def choose(parent: QWidget, title: str,
               choices: list) -> 'BottomSheet':
        sheet = BottomSheet(parent)
        sheet.show_choices(title, choices)
        return sheet

    def show_custom(self, title: str, content_widget: QWidget,
                    submit_text: str = "", cancel_text: str = "",
                    no_buttons: bool = False):
        """Show bottom sheet with a custom widget as content.

        If no_buttons=True, no cancel/submit buttons are added — the caller
        is responsible for providing buttons inside content_widget and
        calling close() or _animate_close() directly.
        """
        self._clear_dynamic()
        self.setLayoutDirection(get_layout_direction())

        self._title_lbl.setText(title)

        self._form_container.addWidget(content_widget)

        if not no_buttons:
            if not submit_text:
                submit_text = "\u0625\u0631\u0633\u0627\u0644"
            if not cancel_text:
                cancel_text = "\u0625\u0644\u063A\u0627\u0621"

            cancel_btn = self._make_button(cancel_text, "secondary")
            cancel_btn.clicked.connect(self._on_cancel)
            self._buttons_layout.addWidget(cancel_btn)

            submit_btn = self._make_button(submit_text, "primary")
            submit_btn.clicked.connect(self._on_confirm)
            self._buttons_layout.addWidget(submit_btn)

        self._animate_open()

    def close_sheet(self, callback=None):
        """Public method to close the sheet with animation."""
        self._animate_close(callback)

    @staticmethod
    def form(parent: QWidget, title: str, fields: list,
             submit_text: str = "", cancel_text: str = "") -> 'BottomSheet':
        sheet = BottomSheet(parent)
        sheet.show_form(title, fields, submit_text, cancel_text)
        return sheet

    @staticmethod
    def custom(parent: QWidget, title: str, content_widget: QWidget,
               submit_text: str = "", cancel_text: str = "",
               no_buttons: bool = False) -> 'BottomSheet':
        sheet = BottomSheet(parent)
        sheet.show_custom(title, content_widget, submit_text, cancel_text,
                          no_buttons)
        return sheet
