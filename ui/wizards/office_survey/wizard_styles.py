# -*- coding: utf-8 -*-
"""Shared QSS constants and helpers for the Office Survey Wizard UI."""

from PyQt5.QtWidgets import QFrame, QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor


# -- Step card (white rounded container with shadow) --
STEP_CARD_STYLE = """
    QFrame#StepCard {
        background-color: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E2EAF2;
    }
    QFrame#StepCard QLabel { background: transparent; border: none; }
    QFrame#StepCard QCheckBox { background: transparent; }
"""

# -- Form inputs --
FORM_FIELD_STYLE = """
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {
        border: 1.5px solid #D0D7E2;
        border-radius: 8px;
        padding: 8px 12px;
        background-color: #FFFFFF;
        color: #2C3E50;
        font-size: 10pt;
        min-height: 26px;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {
        border-color: #3890DF;
    }
    QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {
        background-color: #F1F5F9;
        color: #94A3B8;
        border-color: #E2E8F0;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox QAbstractItemView {
        border: 1px solid #D0D7E2;
        border-radius: 4px;
        background-color: #FFFFFF;
        selection-background-color: #EBF5FF;
        selection-color: #2C3E50;
    }
"""

# -- Read-only fields --
READONLY_FIELD_STYLE = """
    QLineEdit {
        background-color: #F8FAFF;
        border: 1px solid #dcdfe6;
        border-radius: 8px;
        padding: 8px 12px;
        color: #606266;
    }
"""

# -- Table --
WIZARD_TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        border: 1px solid #E2EAF2;
        border-radius: 8px;
        gridline-color: #F1F5F9;
        selection-background-color: #EBF5FF;
        selection-color: #2C3E50;
    }
    QHeaderView::section {
        background-color: #F0F4FA;
        color: #2C3E50;
        font-weight: 600;
        padding: 10px 8px;
        border: none;
        border-bottom: 2px solid #E2EAF2;
    }
    QTableWidget::item {
        padding: 8px;
        border-bottom: 1px solid #F1F5F9;
    }
    QTableWidget::item:hover {
        background-color: #F8FAFF;
    }
"""

# -- Section header text --
SECTION_HEADER_STYLE = "color: #1A1F1D; font-weight: 600; background: transparent; border: none;"

# -- Section subtitle text --
SECTION_SUBTITLE_STYLE = "color: #86909B; background: transparent; border: none;"

# -- Card title text --
CARD_TITLE_STYLE = "color: #212B36; font-weight: bold; background: transparent; border: none;"

# -- In-card action button (gradient blue) --
IN_CARD_ACTION_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
        color: white;
        border: 1px solid rgba(120, 190, 255, 0.35);
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.55);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #3890DF, stop:0.5 #2E7BD6, stop:1 #266FC0);
    }
    QPushButton:disabled {
        background: #BDC3C7;
        border: none;
        color: #7F8C9B;
    }
"""

# -- Outline (secondary) button --
OUTLINE_BUTTON_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #414D5A;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #F0F4F8;
        border-color: #3890DF;
        color: #3890DF;
    }
    QPushButton:disabled {
        background-color: #FFFFFF;
        border: 1px solid #E1E8ED;
        color: #BDC3C7;
    }
"""

# -- Footer next/save button (gradient blue, larger) --
FOOTER_PRIMARY_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
        color: white;
        border: 1px solid rgba(120, 190, 255, 0.25);
        border-radius: 8px;
        font-size: 12pt;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.45);
    }
    QPushButton:disabled {
        background: #BDC3C7;
        border: none;
        color: #7F8C9B;
    }
"""

# -- Footer previous button (visible state) --
FOOTER_SECONDARY_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #414D5A;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        font-size: 12pt;
    }
    QPushButton:hover {
        background-color: #F0F4F8;
        border-color: #3890DF;
    }
    QPushButton:disabled {
        background-color: #FFFFFF;
        border: 1px solid #E1E8ED;
        color: #BDC3C7;
    }
"""

# -- Footer previous button (hidden/transparent state) --
FOOTER_HIDDEN_STYLE = """
    QPushButton {
        background-color: transparent;
        color: transparent;
        border: none;
    }
"""

# -- Header save button (in dark zone) --
HEADER_SAVE_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
        color: white;
        border: 1px solid rgba(120, 190, 255, 0.35);
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.55);
    }
"""


def make_step_card(object_name: str = "StepCard") -> QFrame:
    """Create a white rounded card frame with drop shadow."""
    card = QFrame()
    card.setObjectName(object_name)
    card.setStyleSheet(STEP_CARD_STYLE)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(20)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 20))
    card.setGraphicsEffect(shadow)
    return card
