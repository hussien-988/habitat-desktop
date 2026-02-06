# -*- coding: utf-8 -*-
"""
Field Work Confirmation Dialog
Shows confirmation before assigning buildings to researcher.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor

from ui.components.icon import Icon
from ui.font_utils import create_font, FontManager


class FieldWorkConfirmationDialog(QDialog):
    """Confirmation dialog for field work assignment."""

    def __init__(self, building_count: int, researcher_id: str, parent=None):
        super().__init__(parent)
        self.building_count = building_count
        self.researcher_id = researcher_id
        self.confirmed = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        # Remove window frame and title bar
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Fixed size: 400×267
        self.setFixedSize(400, 267)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container with rounded corners
        container = QLabel()
        container.setStyleSheet("""
            QLabel {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
        """)
        container.setFixedSize(400, 267)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))  # Black with 60 alpha (transparency)
        container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(container)
        # Padding: top 32px, other sides 24px
        container_layout.setContentsMargins(24, 32, 24, 24)
        container_layout.setSpacing(16)

        # Row 1: Warning icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)

        # Try to load warning.png from assets/images
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        icon_path = base_path / "assets" / "images" / "warning.png"

        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                # Scale to appropriate size (e.g., 48×48)
                scaled_pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(scaled_pixmap)
        else:
            # Fallback: use warning emoji
            icon_label.setText("⚠️")
            icon_label.setFont(create_font(size=24, weight=FontManager.WEIGHT_REGULAR))

        container_layout.addWidget(icon_label)

        # Row 2: Title
        title_text = f"هل انت متاكد من اسناد {self.building_count} مهمة"
        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet("color: #212B36; background: transparent;")
        title_label.setWordWrap(True)
        container_layout.addWidget(title_label)

        # Row 3: Subtitle
        subtitle_text = f"{self.building_count} مهمة سيتم اسنادها ل {self.researcher_id}"
        subtitle_label = QLabel(subtitle_text)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet("color: #637381; background: transparent;")
        subtitle_label.setWordWrap(True)
        container_layout.addWidget(subtitle_label)

        container_layout.addStretch()

        # Row 4: Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        # Cancel button (white)
        btn_cancel = QPushButton("الغاء")
        btn_cancel.setFixedSize(170, 50)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #414D5A;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #F8F9FA;
            }
        """)
        btn_cancel.clicked.connect(self._on_cancel)
        buttons_layout.addWidget(btn_cancel)

        # Assign button (yellow from warning icon)
        btn_assign = QPushButton("اسناد")
        btn_assign.setFixedSize(170, 50)
        btn_assign.setCursor(Qt.PointingHandCursor)
        btn_assign.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        btn_assign.setStyleSheet("""
            QPushButton {
                background-color: #FFC107;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #FFB300;
            }
        """)
        btn_assign.clicked.connect(self._on_assign)
        buttons_layout.addWidget(btn_assign)

        container_layout.addLayout(buttons_layout)

        main_layout.addWidget(container)

    def _on_assign(self):
        """Handle assign button click."""
        self.confirmed = True
        self.accept()

    def _on_cancel(self):
        """Handle cancel button click."""
        self.confirmed = False
        self.reject()

    @staticmethod
    def show_confirmation(building_count: int, researcher_id: str, parent=None) -> bool:
        """
        Show confirmation dialog and return True if user confirmed.

        Args:
            building_count: Number of buildings to assign
            researcher_id: Researcher ID
            parent: Parent widget

        Returns:
            True if user clicked assign, False otherwise
        """
        dialog = FieldWorkConfirmationDialog(building_count, researcher_id, parent)
        dialog.exec_()
        return dialog.confirmed
