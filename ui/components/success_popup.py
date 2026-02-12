# -*- coding: utf-8 -*-
"""
Success Popup Dialog - Shows success message after survey finalization.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPixmap
import os


class SuccessPopup(QDialog):
    """
    Success popup dialog shown after survey finalization.

    Displays a clean popup with:
    - Success icon
    - Title message
    - Claim/Reference number
    - Description text
    """

    def __init__(self,
                 claim_number: str = "",
                 title: str = "تمت الإضافة بنجاح",
                 description: str = "تم حفظ جميع المعلومات،\nويمكنك الآن المتابعة أو إضافة عنصر جديد",
                 auto_close_ms: int = 0,
                 parent=None):
        """
        Initialize the success popup.

        Args:
            claim_number: The claim or reference number to display
            title: The success title text
            description: The description text
            auto_close_ms: Auto-close after this many milliseconds (0 = no auto-close)
            parent: Parent widget
        """
        super().__init__(parent)
        self.claim_number = claim_number
        self.title_text = title
        self.description_text = description
        self.auto_close_ms = auto_close_ms
        self._init_ui()

    def _init_ui(self):
        """Initialize the popup UI."""
        # Window Setup - frameless, translucent, stays on top
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(350, 350)
        self.setLayoutDirection(Qt.RightToLeft)

        # The Main Card Container - white rounded box
        card = QLabel(self)
        card.setFixedSize(300, 300)
        card.move(25, 25)  # Centering within the shadow area
        card.setObjectName("MainCard")
        card.setStyleSheet("""
            #MainCard {
                background-color: white;
                border-radius: 30px;
                border: 1px solid #e0e0e0;
            }
        """)

        # Add shadow for a "popup" feel
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 5)
        card.setGraphicsEffect(shadow)

        # Content Layout
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")

        # Load icon from assets
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                  "assets", "images", "like.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_label.setPixmap(pixmap.scaled(70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback: show checkmark emoji
            icon_label.setText("✓")
            icon_label.setStyleSheet("""
                background: #10b981;
                color: white;
                font-size: 36px;
                border-radius: 35px;
                min-width: 70px;
                max-width: 70px;
                min-height: 70px;
                max-height: 70px;
            """)

        # Success Title (Arabic)
        title_label = QLabel(self.title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: #1e293b;
            background: transparent;
            border: none;
        """)

        # ID/Claim Reference Label
        id_label = QLabel(self.claim_number if self.claim_number else "")
        id_label.setAlignment(Qt.AlignCenter)
        id_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1e293b;
            background: transparent;
            border: none;
        """)

        # Description (Arabic)
        desc_label = QLabel(self.description_text)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            font-size: 14px;
            color: #94a3b8;
            line-height: 140%;
            background: transparent;
            border: none;
        """)

        # Add widgets to layout
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        if self.claim_number:
            layout.addWidget(id_label)
        layout.addWidget(desc_label)

        # Auto-close timer if specified
        if self.auto_close_ms > 0:
            QTimer.singleShot(self.auto_close_ms, self.close)

    def mousePressEvent(self, event):
        """Close the popup when clicking on it."""
        self.accept()

    def keyPressEvent(self, event):
        """Close on Escape or Enter key."""
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.accept()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def show_success(claim_number: str = "",
                     title: str = "تمت الإضافة بنجاح",
                     description: str = "تم حفظ جميع المعلومات،\nويمكنك الآن المتابعة أو إضافة عنصر جديد",
                     auto_close_ms: int = 0,
                     parent=None) -> int:
        """
        Static method to show the success popup.

        Args:
            claim_number: The claim or reference number to display
            title: The success title text
            description: The description text
            auto_close_ms: Auto-close after this many milliseconds (0 = no auto-close)
            parent: Parent widget

        Returns:
            QDialog result code
        """
        popup = SuccessPopup(
            claim_number=claim_number,
            title=title,
            description=description,
            auto_close_ms=auto_close_ms,
            parent=parent
        )

        # Center on parent window if available
        if parent:
            top_window = parent.window()
            target = top_window if top_window else parent
            # Use geometry() for reliable screen coordinates
            target_rect = target.geometry()
            popup_x = target_rect.x() + (target_rect.width() - popup.width()) // 2
            popup_y = target_rect.y() + (target_rect.height() - popup.height()) // 2
            # Ensure popup stays within screen bounds
            popup_x = max(0, popup_x)
            popup_y = max(0, popup_y)
            popup.move(popup_x, popup_y)
        else:
            # Center on screen if no parent
            from PyQt5.QtWidgets import QDesktopWidget
            screen = QDesktopWidget().availableGeometry()
            popup_x = (screen.width() - popup.width()) // 2
            popup_y = (screen.height() - popup.height()) // 2
            popup.move(popup_x, popup_y)

        return popup.exec_()
