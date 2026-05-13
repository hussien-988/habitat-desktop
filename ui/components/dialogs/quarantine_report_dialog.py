# -*- coding: utf-8 -*-
"""Quarantine Report Dialog — minimal layout matching the app's dialog system."""

from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSizePolicy, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)

from services.translation_manager import tr, get_layout_direction
from ui.design_system import ScreenScale, Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class QuarantineReportDialog(QDialog):
    """Compact dialog: title + package number + file name + reason + close."""

    def __init__(self, report: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._report = report or {}

        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.CustomizeWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(True)
        self.setLayoutDirection(get_layout_direction())

        self._card = None
        self._title_lbl = None
        self._pkg_num_label_lbl = None
        self._pkg_num_value_lbl = None
        self._file_name_label_lbl = None
        self._file_name_value_lbl = None
        self._reason_label_lbl = None
        self._reason_value_lbl = None
        self._close_btn = None

        self._setup_ui()
        self._populate_values()
        self._center_on_parent()
        self._animate_in()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(24),
            ScreenScale.w(24), ScreenScale.h(24),
        )
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("QuarantineCard")
        self._card.setStyleSheet(
            "QFrame#QuarantineCard {"
            " background-color: #FFFFFF;"
            " border: 1px solid #E1E8ED;"
            " border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 60))
        self._card.setGraphicsEffect(shadow)
        self._card.setMinimumWidth(ScreenScale.w(420))
        self._card.setMaximumWidth(ScreenScale.w(640))
        self._card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(22),
            ScreenScale.w(24), ScreenScale.h(22),
        )
        card_layout.setSpacing(ScreenScale.h(14))

        self._title_lbl = QLabel()
        self._title_lbl.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._title_lbl.setStyleSheet("color: #111827; background: transparent;")
        self._title_lbl.setWordWrap(True)
        card_layout.addWidget(self._title_lbl)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #F1F5F9; border: none;")
        card_layout.addWidget(sep)

        self._pkg_num_label_lbl, self._pkg_num_value_lbl = self._build_field_row()
        card_layout.addLayout(self._row_layout(self._pkg_num_label_lbl, self._pkg_num_value_lbl))

        self._file_name_label_lbl, self._file_name_value_lbl = self._build_field_row()
        card_layout.addLayout(self._row_layout(self._file_name_label_lbl, self._file_name_value_lbl))

        self._reason_label_lbl = QLabel()
        self._reason_label_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._reason_label_lbl.setStyleSheet("color: #6B7280; background: transparent;")
        card_layout.addWidget(self._reason_label_lbl)

        self._reason_value_lbl = QLabel()
        self._reason_value_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._reason_value_lbl.setStyleSheet(
            "color: #1F2937;"
            " background: #F8FAFC;"
            " border: 1px solid #E2E8F0;"
            " border-radius: 8px;"
            " padding: 10px 12px;"
        )
        self._reason_value_lbl.setWordWrap(True)
        self._reason_value_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._reason_value_lbl.setMinimumHeight(ScreenScale.h(60))
        self._reason_value_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card_layout.addWidget(self._reason_value_lbl)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, ScreenScale.h(4), 0, 0)
        btn_row.addStretch()
        self._close_btn = QPushButton()
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._close_btn.setMinimumHeight(ScreenScale.h(36))
        self._close_btn.setMinimumWidth(ScreenScale.w(110))
        self._close_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._close_btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {Colors.PRIMARY_BLUE};"
            " color: white;"
            " border: none;"
            " border-radius: 8px;"
            " padding: 0 22px;"
            "}"
            "QPushButton:hover { background-color: #2D7BC9; }"
            "QPushButton:pressed { background-color: #1F66A8; }"
        )
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        card_layout.addLayout(btn_row)

        outer.addWidget(self._card, alignment=Qt.AlignCenter)

    def _build_field_row(self):
        label_lbl = QLabel()
        label_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        label_lbl.setStyleSheet("color: #6B7280; background: transparent;")
        label_lbl.setMinimumWidth(ScreenScale.w(140))
        label_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        value_lbl = QLabel()
        value_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        value_lbl.setStyleSheet("color: #111827; background: transparent;")
        value_lbl.setWordWrap(True)
        value_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return label_lbl, value_lbl

    @staticmethod
    def _row_layout(label_lbl, value_lbl):
        row = QHBoxLayout()
        row.setSpacing(ScreenScale.w(12))
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label_lbl, 0, Qt.AlignTop)
        row.addWidget(value_lbl, 1)
        return row

    def _populate_values(self):
        r = self._report
        self._title_lbl.setText(tr("quarantine_dialog.title"))
        self._pkg_num_label_lbl.setText(tr("quarantine_dialog.package_number"))
        self._pkg_num_value_lbl.setText(str(r.get("packageNumber") or "-"))
        self._file_name_label_lbl.setText(tr("quarantine_dialog.file_name"))
        self._file_name_value_lbl.setText(str(r.get("fileName") or "-"))
        self._reason_label_lbl.setText(tr("quarantine_dialog.reason_label"))
        self._reason_value_lbl.setText(str(r.get("quarantineReason") or "-"))
        self._close_btn.setText(tr("quarantine_dialog.close"))
        self._close_btn.adjustSize()

    def update_language(self, is_arabic: bool = True):
        self.setLayoutDirection(get_layout_direction())
        self._populate_values()

    def _center_on_parent(self):
        parent = self.parent()
        if not parent:
            return
        main_window = parent.window() if hasattr(parent, "window") else parent
        self.adjustSize()
        rect = main_window.geometry()
        cx = rect.x() + (rect.width() - self.width()) // 2
        cy = rect.y() + (rect.height() - self.height()) // 2
        self.move(cx, cy)

    def _animate_in(self):
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(None)
        self._card.setGraphicsEffect(self._card.graphicsEffect())
        try:
            self.setWindowOpacity(0.0)
            self._anim = QPropertyAnimation(self, b"windowOpacity")
            self._anim.setDuration(160)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_parent()

    @classmethod
    def show_for(cls, report: Dict[str, Any], parent=None) -> None:
        dlg = cls(report, parent=parent)
        dlg.exec_()
