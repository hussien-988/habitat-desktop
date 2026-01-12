# -*- coding: utf-8 -*-
"""
Claim List Card Component - بطاقة المطالبة في القائمة
Individual claim card with shadow, displayed in grid layout.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

from ..design_system import Colors


class ClaimListCard(QFrame):
    """Claim card component for grid display."""

    clicked = pyqtSignal(str)

    def __init__(self, claim_data: dict, parent=None):
        super().__init__(parent)
        self.claim_data = claim_data
        self._setup_ui()

    def _setup_ui(self):
        """Setup card UI with shadow and content layout."""
        self.setObjectName("claimCard")

        self.setStyleSheet("""
            QFrame#claimCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
            QFrame#claimCard:hover {
                background-color: #FAFBFC;
            }
        """)

        self.setMinimumHeight(120)
        self.setCursor(Qt.PointingHandCursor)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        icon_btn = QPushButton("📋")
        icon_btn.setCursor(Qt.PointingHandCursor)
        icon_btn.setFixedSize(32, 32)
        icon_btn.setStyleSheet("""
            QPushButton {
                background-color: #e3f2fd;
                color: #3890df;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #bbdefb;
            }
        """)
        icon_btn.clicked.connect(lambda: self.clicked.emit(self.claim_data.get('claim_id', '')))
        top_row.addWidget(icon_btn)

        name_container = QWidget()
        name_container.setStyleSheet("background: transparent; border: none;")
        name_layout = QVBoxLayout(name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(2)

        name = self.claim_data.get('claimant_name', 'غير محدد')
        name_label = QLabel(name)
        name_label.setStyleSheet("""
            QLabel {
                color: #212121;
                font-size: 13px;
                font-weight: 600;
                font-family: 'Noto Kufi Arabic';
                background: transparent;
                border: none;
            }
        """)
        name_label.setTextFormat(Qt.PlainText)
        name_layout.addWidget(name_label)

        claim_id = self.claim_data.get('claim_id', 'CL-2025-000001')
        id_label = QLabel(claim_id)
        id_label.setStyleSheet("""
            QLabel {
                color: #9e9e9e;
                font-size: 11px;
                font-family: 'Noto Kufi Arabic';
                background: transparent;
                border: none;
            }
        """)
        id_label.setTextFormat(Qt.PlainText)
        name_layout.addWidget(id_label)

        top_row.addWidget(name_container)
        top_row.addStretch()

        date = self.claim_data.get('date', '2024-12-01')
        date_label = QLabel(date)
        date_label.setStyleSheet("""
            QLabel {
                color: #9e9e9e;
                font-size: 12px;
                font-family: 'Noto Kufi Arabic';
                background: transparent;
                border: none;
            }
        """)
        date_label.setTextFormat(Qt.PlainText)
        top_row.addWidget(date_label)

        card_layout.addLayout(top_row)

        details_container = QFrame()
        details_container.setObjectName("detailsFrame")
        details_container.setStyleSheet("""
            QFrame#detailsFrame {
                background-color: #f0f7ff;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
        """)

        details_layout = QHBoxLayout(details_container)
        details_layout.setContentsMargins(10, 6, 10, 6)
        details_layout.setSpacing(6)

        folder_icon = QLabel("▣")
        folder_icon.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #3890df;
                background: transparent;
                border: none;
            }
        """)
        details_layout.addWidget(folder_icon)

        location = self.claim_data.get('location', 'غير محدد')
        unit_id = self.claim_data.get('unit_id', '')
        building_id = self.claim_data.get('building_id', '')

        details_parts = []
        if location and location != 'غير محدد':
            details_parts.append(location)
        if building_id:
            details_parts.append(f"رقم البناء: {building_id}")
        if unit_id:
            details_parts.append(f"رقم الوحدة: {unit_id}")

        details_text = " - ".join(details_parts) if details_parts else "لا توجد تفاصيل إضافية"

        details_label = QLabel(details_text)
        details_label.setStyleSheet("""
            QLabel {
                color: #757575;
                font-size: 11px;
                font-family: 'Noto Kufi Arabic';
                background: transparent;
                border: none;
            }
        """)
        details_label.setTextFormat(Qt.PlainText)
        details_layout.addWidget(details_label)

        details_layout.addStretch()

        card_layout.addWidget(details_container)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.claim_data.get('claim_id', ''))
        super().mousePressEvent(event)
