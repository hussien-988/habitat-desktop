# -*- coding: utf-8 -*-
"""
Success Popup Dialog - Shows success message after survey finalization.
Supports displaying multiple claims with claimant names.
"""

from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QGraphicsDropShadowEffect,
    QFrame, QHBoxLayout, QPushButton, QWidget
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPixmap
import os

from ui.design_system import Colors, ButtonDimensions
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction


class SuccessPopup(QDialog):
    """Success popup dialog shown after survey finalization."""

    _CARD_W = 320
    _BASE_HEIGHT = 390
    _CLAIM_ROW_HEIGHT = 64

    def __init__(self,
                 claim_number: str = "",
                 claims: Optional[List[Dict]] = None,
                 title: str = None,
                 description: str = None,
                 auto_close_ms: int = 0,
                 parent=None):
        super().__init__(parent)
        self.claim_number = claim_number
        self.claims = claims or []
        self.title_text = title if title is not None else tr("component.success_popup.default_title")
        self.description_text = description if description is not None else tr("component.success_popup.default_description")
        self.auto_close_ms = auto_close_ms
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(get_layout_direction())

        extra_claims = max(0, len(self.claims) - 1) if self.claims else 0
        card_h = self._BASE_HEIGHT + (extra_claims * self._CLAIM_ROW_HEIGHT)
        total_w = self._CARD_W + 60   # 30px margin each side
        total_h = card_h + 60         # 30px margin each side

        self.setFixedSize(total_w, total_h)

        # Card
        self._card = QFrame(self)
        self._card.setObjectName("SuccessCard")
        self._card.setFixedSize(self._CARD_W, card_h)
        self._card.move(30, 30)
        self._card.setStyleSheet("""
            QFrame#SuccessCard {
                background-color: #FFFFFF;
                border-radius: 20px;
                border: 1px solid #E8F0FA;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(30, 80, 160, 50))
        shadow.setOffset(0, 8)
        self._card.setGraphicsEffect(shadow)

        # Layout — no top padding (accent bar handles it)
        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(0, 0, 0, 28)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)

        # Green accent bar at top
        accent = QFrame()
        accent.setFixedHeight(6)
        accent.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        layout.addWidget(accent)
        layout.addSpacing(24)

        # Icon circle
        icon_wrap = QLabel()
        icon_wrap.setFixedSize(76, 76)
        icon_wrap.setAlignment(Qt.AlignCenter)
        icon_wrap.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #34d399, stop:1 #10b981);
                border-radius: 38px;
                border: none;
            }
        """)

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "images", "like.png"
        )
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_wrap.setPixmap(pixmap)
        else:
            icon_wrap.setText("✓")
            icon_wrap.setFont(create_font(size=30, weight=FontManager.WEIGHT_BOLD))
            icon_wrap.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #34d399, stop:1 #10b981);
                border-radius: 38px;
                color: white;
            """)

        layout.addWidget(icon_wrap, 0, Qt.AlignCenter)
        layout.addSpacing(18)

        # Title
        title_lbl = QLabel(self.title_text)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setFont(create_font(size=20, weight=FontManager.WEIGHT_BOLD))
        title_lbl.setStyleSheet("color: #1A2B3C; background: transparent; border: none;")
        layout.addWidget(title_lbl)
        layout.addSpacing(14)

        # Claims or single claim number
        if self.claims:
            layout.addWidget(self._build_claims_list())
        elif self.claim_number:
            pill = QFrame()
            pill.setMinimumHeight(34)
            pill.setStyleSheet("""
                QFrame {
                    background: rgba(56, 144, 223, 0.10);
                    border-radius: 17px;
                    border: 1px solid rgba(56, 144, 223, 0.20);
                }
            """)
            pill_layout = QHBoxLayout(pill)
            pill_layout.setContentsMargins(20, 0, 20, 0)
            num_lbl = QLabel(self.claim_number)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
            num_lbl.setStyleSheet("color: #3890DF; background: transparent; border: none;")
            pill_layout.addWidget(num_lbl, 0, Qt.AlignCenter)

            pill_wrap = QHBoxLayout()
            pill_wrap.setContentsMargins(24, 0, 24, 0)
            pill_wrap.addStretch()
            pill_wrap.addWidget(pill)
            pill_wrap.addStretch()
            pill_widget = QWidget()
            pill_widget.setStyleSheet("background: transparent; border: none;")
            pill_widget.setLayout(pill_wrap)
            layout.addWidget(pill_widget)

        layout.addSpacing(10)

        # Description
        desc_lbl = QLabel(self.description_text)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setFont(create_font(size=FontManager.SIZE_BODY))
        desc_lbl.setStyleSheet("color: #94a3b8; background: transparent; border: none;")
        desc_lbl.setContentsMargins(24, 0, 24, 0)
        layout.addWidget(desc_lbl)

        layout.addSpacing(20)

        # Done button — blue gradient
        done_btn = QPushButton(tr("component.success_popup.done_button"))
        done_btn.setFixedSize(140, 44)
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        done_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3890DF, stop:1 #5BA8F0);
                color: white;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2A7BC9, stop:1 #4A98E0);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1E6AB0, stop:1 #3A88D0);
            }
        """)
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn, 0, Qt.AlignCenter)

        if self.auto_close_ms > 0:
            QTimer.singleShot(self.auto_close_ms, self.close)

    def showEvent(self, event):
        super().showEvent(event)
        # Fade-in animation on the whole window
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(220)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _build_claims_list(self) -> QFrame:
        container = QFrame()
        container.setStyleSheet("background: transparent; border: none;")
        v_layout = QVBoxLayout(container)
        v_layout.setContentsMargins(20, 0, 20, 0)
        v_layout.setSpacing(6)

        for claim in self.claims:
            name = claim.get("fullNameArabic", "") or claim.get("primaryClaimantName", "")
            number = claim.get("claimNumber", "")

            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background: rgba(56, 144, 223, 0.06);
                    border-radius: 10px;
                    border: none;
                }
            """)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(2)

            if name:
                name_lbl = QLabel(name)
                name_lbl.setAlignment(Qt.AlignCenter)
                name_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
                name_lbl.setStyleSheet("color: #1A2B3C; background: transparent; border: none;")
                row_layout.addWidget(name_lbl)

            if number:
                num_lbl = QLabel(number)
                num_lbl.setAlignment(Qt.AlignCenter)
                num_lbl.setFont(create_font(size=11))
                num_lbl.setStyleSheet("color: #3890DF; background: transparent; border: none;")
                row_layout.addWidget(num_lbl)

            v_layout.addWidget(row)

        return container

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def show_success(claim_number: str = "",
                     claims: Optional[List[Dict]] = None,
                     title: str = None,
                     description: str = None,
                     auto_close_ms: int = 0,
                     parent=None) -> int:
        popup = SuccessPopup(
            claim_number=claim_number,
            claims=claims,
            title=title,
            description=description,
            auto_close_ms=auto_close_ms,
            parent=parent
        )

        if parent:
            top_window = parent.window()
            target = top_window if top_window else parent
            target_rect = target.geometry()
            popup_x = target_rect.x() + (target_rect.width() - popup.width()) // 2
            popup_y = target_rect.y() + (target_rect.height() - popup.height()) // 2
            popup_x = max(0, popup_x)
            popup_y = max(0, popup_y)
            popup.move(popup_x, popup_y)
        else:
            from PyQt5.QtWidgets import QDesktopWidget
            screen = QDesktopWidget().availableGeometry()
            popup_x = (screen.width() - popup.width()) // 2
            popup_y = (screen.height() - popup.height()) // 2
            popup.move(popup_x, popup_y)

        return popup.exec_()
