# -*- coding: utf-8 -*-
"""
Success Popup Dialog - Shows success message after survey finalization.
Supports displaying multiple claims with claimant names.
"""

from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QGraphicsDropShadowEffect,
    QFrame, QHBoxLayout, QPushButton
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPixmap
import os

from ui.design_system import Colors, ButtonDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager


class SuccessPopup(QDialog):
    """Success popup dialog shown after survey finalization."""

    # Card base dimensions
    _BASE_WIDTH = 350
    _BASE_CARD_WIDTH = 300
    _BASE_HEIGHT = 350
    _CLAIM_ROW_HEIGHT = 60

    def __init__(self,
                 claim_number: str = "",
                 claims: Optional[List[Dict]] = None,
                 title: str = "تمت الإضافة بنجاح",
                 description: str = "تم حفظ جميع المعلومات،\nويمكنك الآن المتابعة أو إضافة عنصر جديد",
                 auto_close_ms: int = 0,
                 parent=None):
        super().__init__(parent)
        self.claim_number = claim_number
        self.claims = claims or []
        self.title_text = title
        self.description_text = description
        self.auto_close_ms = auto_close_ms
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.RightToLeft)

        # Dynamic height based on number of claims
        extra_claims = max(0, len(self.claims) - 1) if self.claims else 0
        total_height = self._BASE_HEIGHT + (extra_claims * self._CLAIM_ROW_HEIGHT)
        card_height = total_height - 50  # 25px margin each side

        self.setFixedSize(self._BASE_WIDTH, total_height)

        # Main card container
        card = QFrame(self)
        card.setFixedSize(self._BASE_CARD_WIDTH, card_height)
        card.move(25, 25)
        card.setObjectName("MainCard")
        card.setStyleSheet("""
            #MainCard {
                background-color: white;
                border-radius: 30px;
                border: 1px solid #e0e0e0;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 5)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 25, 20, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "images", "like.png"
        )
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_label.setPixmap(pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_label.setText("\u2713")
            icon_label.setFont(create_font(size=28, weight=FontManager.WEIGHT_BOLD))
            icon_label.setStyleSheet("""
                background: #10b981; color: white;
                border-radius: 30px;
                min-width: 60px; max-width: 60px;
                min-height: 60px; max-height: 60px;
            """)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(self.title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=18, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        layout.addWidget(title_label)

        # Claims list or single claim number
        if self.claims:
            claims_container = self._build_claims_list()
            layout.addWidget(claims_container)
        elif self.claim_number:
            id_label = QLabel(self.claim_number)
            id_label.setAlignment(Qt.AlignCenter)
            id_label.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
            id_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
            layout.addWidget(id_label)

        # Description
        desc_label = QLabel(self.description_text)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setFont(create_font(size=FontManager.SIZE_BODY))
        desc_label.setStyleSheet("color: #94a3b8; background: transparent; border: none;")
        layout.addWidget(desc_label)

        # "تم" button
        done_btn = QPushButton("تم")
        done_btn.setFixedHeight(ButtonDimensions.PRIMARY_HEIGHT)
        done_btn.setFixedWidth(120)
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_BOLD))
        done_btn.setStyleSheet(StyleManager.button_primary())
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn, 0, Qt.AlignCenter)

        if self.auto_close_ms > 0:
            QTimer.singleShot(self.auto_close_ms, self.close)

    def _build_claims_list(self) -> QFrame:
        container = QFrame()
        container.setStyleSheet("background: transparent; border: none;")
        v_layout = QVBoxLayout(container)
        v_layout.setContentsMargins(0, 4, 0, 4)
        v_layout.setSpacing(6)

        for claim in self.claims:
            name = claim.get("fullNameArabic", "") or claim.get("primaryClaimantName", "")
            number = claim.get("claimNumber", "")

            row = QFrame()
            row.setStyleSheet("QFrame { background: transparent; border: none; }")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 4, 0, 4)
            row_layout.setSpacing(2)

            if name:
                name_lbl = QLabel(name)
                name_lbl.setAlignment(Qt.AlignCenter)
                name_lbl.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
                name_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
                row_layout.addWidget(name_lbl)

            if number:
                num_lbl = QLabel(number)
                num_lbl.setAlignment(Qt.AlignCenter)
                num_lbl.setFont(create_font(size=11))
                num_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
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
                     title: str = "تمت الإضافة بنجاح",
                     description: str = "تم حفظ جميع المعلومات،\nويمكنك الآن المتابعة أو إضافة عنصر جديد",
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
