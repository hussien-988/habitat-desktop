# -*- coding: utf-8 -*-
"""
Empty State Component - Figma Design (Page 3)
Component shown when there is no data to display
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPainter, QColor


class EmptyState(QWidget):
    """
    Empty state component with icon, title, and description.
    Matches Figma design specifications exactly.

    From Figma Page 3:
    - Centered circular blue icon (120px)
    - Title below icon
    - Description text
    """

    def __init__(self,
                 icon_text: str = "+",
                 title: str = "لا توجد بيانات بعد",
                 description: str = "ابدأ بإضافة الحالات لإظهارها هنا",
                 parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.title_text = title
        self.description_text = description
        self._setup_ui()

    def _setup_ui(self):
        """Setup the empty state UI matching Figma Page 3 exactly."""
        # Main layout - centered
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        # Icon circle (120px × 120px, blue background)
        icon_container = QWidget()
        icon_container.setFixedSize(120, 120)
        icon_container.setStyleSheet("""
            QWidget {
                background-color: #3890DF;
                border-radius: 60px;
            }
        """)

        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignCenter)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        # Icon label (+ symbol or custom icon)
        icon_label = QLabel(self.icon_text)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFont(QFont("Noto Kufi Arabic", 36, QFont.Bold))
        icon_label.setStyleSheet("""
            QLabel {
                color: white;
                background: transparent;
            }
        """)
        icon_layout.addWidget(icon_label)

        layout.addWidget(icon_container, 0, Qt.AlignCenter)

        # Spacing after icon (24px from Figma)
        layout.addSpacing(24)

        # Title
        title_label = QLabel(self.title_text)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Noto Kufi Arabic", 18, QFont.DemiBold))
        title_label.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                background: transparent;
            }
        """)
        layout.addWidget(title_label)

        # Spacing between title and description (8px from Figma)
        layout.addSpacing(8)

        # Description
        description_label = QLabel(self.description_text)
        description_label.setAlignment(Qt.AlignCenter)
        description_label.setWordWrap(True)
        description_label.setMaximumWidth(400)
        description_label.setFont(QFont("Noto Kufi Arabic", 14))
        description_label.setStyleSheet("""
            QLabel {
                color: #7F8C9B;
                background: transparent;
            }
        """)
        layout.addWidget(description_label)

    def set_icon(self, icon_text: str):
        """Update the icon text."""
        self.icon_text = icon_text
        # Update will be handled by finding the label
        for widget in self.findChildren(QLabel):
            if widget.font().pointSize() == 36:
                widget.setText(icon_text)
                break

    def set_title(self, title: str):
        """Update the title text."""
        self.title_text = title
        for widget in self.findChildren(QLabel):
            if widget.font().pointSize() == 18:
                widget.setText(title)
                break

    def set_description(self, description: str):
        """Update the description text."""
        self.description_text = description
        for widget in self.findChildren(QLabel):
            if widget.font().pointSize() == 14 and widget.wordWrap():
                widget.setText(description)
                break
