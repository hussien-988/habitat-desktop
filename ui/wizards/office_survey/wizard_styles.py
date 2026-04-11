# -*- coding: utf-8 -*-
"""Shared QSS constants and helpers for the Office Survey Wizard UI."""

from PyQt5.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout, QLabel,
    QWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from ui.design_system import ScreenScale


# -- Step card (white rounded container with blue accent left border) --
STEP_CARD_STYLE = """
    QFrame#StepCard {
        background-color: #FFFFFF;
        border-radius: 14px;
        border: 1px solid #E2EAF2;
        border-left: 3px solid #3890DF;
    }
    QFrame#StepCard QLabel { background: transparent; border: none; }
    QFrame#StepCard QCheckBox { background: transparent; }
"""

# -- Step container background --
STEP_CONTAINER_STYLE = """
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F0F4FA, stop:1 #E8EEF6);
"""

# -- Form inputs (enhanced) --
FORM_FIELD_STYLE = """
    QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox, QTextEdit {
        border: 1.5px solid #D0D7E2;
        border-radius: 10px;
        padding: 8px 14px;
        background-color: #FFFFFF;
        color: #2C3E50;
        font-size: 10pt;
        min-height: 30px;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {
        border: 1.5px solid #3890DF;
        background-color: #FAFCFF;
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
        border-radius: 10px;
        padding: 4px 14px;
        color: #606266;
    }
"""

# -- Table --
WIZARD_TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        border: 1px solid #E2EAF2;
        border-radius: 10px;
        gridline-color: #F1F5F9;
        selection-background-color: #EBF5FF;
        selection-color: #2C3E50;
    }
    QHeaderView::section {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #F5F8FC, stop:1 #EDF1F7);
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
    QTableWidget::item:selected {
        background-color: #EBF5FF;
    }
"""

# -- Section header text --
SECTION_HEADER_STYLE = "color: #1A2B3D; font-weight: 600; background: transparent; border: none;"

# -- Section subtitle text --
SECTION_SUBTITLE_STYLE = "color: #8896A6; background: transparent; border: none;"

# -- Card title text --
CARD_TITLE_STYLE = "color: #212B36; font-weight: bold; background: transparent; border: none;"

# -- In-card action button (gradient blue) --
IN_CARD_ACTION_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
        color: white;
        border: 1px solid rgba(120, 190, 255, 0.35);
        border-radius: 10px;
        padding: 10px 22px;
        font-weight: 600;
        font-size: 10pt;
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
        border: 1.5px solid #E1E8ED;
        border-radius: 10px;
        padding: 10px 22px;
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
        border-radius: 10px;
        font-size: 12pt;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.45);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #3890DF, stop:0.5 #2E7BD6, stop:1 #266FC0);
    }
    QPushButton:disabled {
        background: #C8D0D8;
        border: none;
        color: #8A9AAC;
    }
"""

# -- Footer previous button (visible state) --
FOOTER_SECONDARY_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #414D5A;
        border: 1.5px solid #E1E8ED;
        border-radius: 10px;
        font-size: 12pt;
    }
    QPushButton:hover {
        background-color: #F0F5FF;
        border-color: #3890DF;
        color: #3890DF;
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
        border-radius: 10px;
        padding: 12px 24px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
            stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
        border: 1px solid rgba(140, 210, 255, 0.55);
    }
"""

# -- Info chip --
CHIP_STYLE = """
    QLabel {{
        background-color: {bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 2px 8px;
    }}
"""

# -- Slide panel form section divider --
SECTION_DIVIDER_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #E2EAF2, stop:0.5 #D0D7E2, stop:1 #E2EAF2);
        max-height: 1px;
        border: none;
    }
"""

# -- Tab underline indicator --
TAB_UNDERLINE_STYLE = """
    QPushButton {{
        background: transparent;
        color: {inactive_fg};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        color: {active_fg};
        border-bottom-color: rgba(56, 144, 223, 0.3);
    }}
"""

TAB_UNDERLINE_ACTIVE = """
    QPushButton {{
        background: transparent;
        color: {active_fg};
        border: none;
        border-bottom: 2px solid #3890DF;
        padding: 8px 16px;
        font-weight: 600;
    }}
"""


# -- Shared colors used across step cards --
ICON_HEADER_BG = "#EBF5FF"
ICON_HEADER_BORDER = "#DBEAFE"
DIVIDER_COLOR = "#E2EAF2"
READONLY_BG = "#F8FAFF"
ADDRESS_TEXT_COLOR = "#667281"

# -- Evidence status pill --
EVIDENCE_AVAILABLE_STYLE = """
    QLabel {
        background-color: #e1f7ef;
        color: #10b981;
        border-radius: 18px;
    }
"""
EVIDENCE_WAITING_STYLE = """
    QLabel {
        background-color: #fef3c7;
        color: #f59e0b;
        border-radius: 18px;
    }
"""

# -- Case category field styles --
CASE_CLOSED_FIELD_STYLE = """
    QLineEdit {
        border: 1px solid #D0D7E2;
        border-radius: 8px;
        padding: 10px;
        background-color: #e8f5e9;
        color: #2e7d32;
        font-size: 14px;
        font-weight: bold;
        min-height: 23px;
        max-height: 23px;
    }
"""
CASE_OPEN_FIELD_STYLE = """
    QLineEdit {
        border: 1px solid #D0D7E2;
        border-radius: 8px;
        padding: 10px;
        background-color: #fff3e0;
        color: #e65100;
        font-size: 14px;
        font-weight: bold;
        min-height: 23px;
        max-height: 23px;
    }
"""

# -- Mini card style (for person/unit list items) --
MINI_CARD_STYLE = """
    QFrame {
        background-color: #F8FAFF;
        border: 1px solid #E5EAF6;
        border-radius: 10px;
    }
    QFrame:hover {
        background-color: #EBF5FF;
        border-color: rgba(56, 144, 223, 0.5);
    }
    QLabel {
        border: none;
        background: transparent;
    }
"""

# -- Selected mini card (active/chosen item) --
MINI_CARD_SELECTED_STYLE = """
    QFrame {
        background-color: #EBF5FF;
        border: 2px solid #3890DF;
        border-radius: 10px;
    }
    QLabel {
        border: none;
        background: transparent;
    }
"""

# -- Person card in lists (enhanced) --
PERSON_CARD_STYLE = """
    QFrame {
        background-color: #F8FAFF;
        border: 1px solid #E2EAF2;
        border-radius: 12px;
    }
    QFrame:hover {
        background-color: #EBF5FF;
        border-color: rgba(56, 144, 223, 0.5);
    }
    QLabel {
        border: none;
        background: transparent;
    }
"""

# -- Context menu --
CONTEXT_MENU_STYLE = """
    QMenu {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
        padding: 4px;
    }
    QMenu::item {
        padding: 8px 16px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #F3F4F6;
    }
"""

# -- Menu dots button --
MENU_DOTS_STYLE = """
    QPushButton {
        border: none;
        color: #475569;
        font-size: 24px;
        font-weight: 900;
        background: transparent;
        border-radius: 18px;
    }
    QPushButton:hover {
        color: #1e293b;
        background-color: #F1F5F9;
    }
"""

# -- Empty state icon circle --
EMPTY_STATE_ICON_STYLE = """
    background-color: #EBF5FF;
    border-radius: 40px;
    border: 1px solid #DBEAFE;
"""

# -- Sub-section header label --
SUB_SECTION_STYLE = """
    QLabel {
        color: #3890DF;
        font-weight: 600;
        background: transparent;
        border: none;
        padding: 4px 0px;
    }
"""

# -- Badge/pill variants --
BADGE_BLUE = "background-color: #DBEAFE; color: #1E40AF; border-radius: 12px; padding: 3px 12px; border: none;"
BADGE_GREEN = "background-color: #D1FAE5; color: #065F46; border-radius: 12px; padding: 3px 12px; border: none;"
BADGE_AMBER = "background-color: #FEF3C7; color: #92400E; border-radius: 12px; padding: 3px 12px; border: none;"
BADGE_RED = "background-color: #FEE2E2; color: #991B1B; border-radius: 12px; padding: 3px 12px; border: none;"
BADGE_GRAY = "background-color: #F1F5F9; color: #475569; border-radius: 12px; padding: 3px 12px; border: none;"


def make_step_card(object_name: str = "StepCard") -> QFrame:
    """Create a white rounded card frame with drop shadow and blue left accent."""
    card = QFrame()
    card.setObjectName(object_name)
    card.setStyleSheet(STEP_CARD_STYLE)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 18))
    card.setGraphicsEffect(shadow)
    return card


def make_icon_header(
    title: str,
    subtitle: str,
    icon_name: str,
    icon_size: int = 40,
    icon_radius: int = 10,
) :
    from ui.components.icon import Icon
    from ui.font_utils import create_font, FontManager

    row = QHBoxLayout()
    row.setSpacing(12)
    row.setContentsMargins(0, 0, 0, 0)

    icon_lbl = QLabel()
    icon_lbl.setFixedSize(icon_size, icon_size)
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_lbl.setStyleSheet(
        f"QLabel {{ background-color: {ICON_HEADER_BG}; "
        f"border: 1px solid {ICON_HEADER_BORDER}; "
        f"border-radius: {icon_radius}px; }}"
    )
    px = Icon.load_pixmap(icon_name, size=int(icon_size * 0.55))
    if px and not px.isNull():
        icon_lbl.setPixmap(px)

    row.addWidget(icon_lbl)

    col = QVBoxLayout()
    col.setSpacing(2)

    t = QLabel(title)
    t.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
    t.setStyleSheet(SECTION_HEADER_STYLE)

    s = QLabel(subtitle)
    s.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
    s.setStyleSheet(SECTION_SUBTITLE_STYLE)

    col.addWidget(t)
    col.addWidget(s)
    row.addLayout(col)
    row.addStretch()
    return row , t , s


def make_divider() -> QFrame:
    """Create a gradient horizontal divider line for step cards."""
    divider = QFrame()
    divider.setFrameShape(QFrame.HLine)
    divider.setFixedHeight(2)
    divider.setStyleSheet("""
        QFrame {
            border: none;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 transparent, stop:0.15 #DBEAFE,
                stop:0.5 #3890DF, stop:0.85 #DBEAFE, stop:1 transparent);
        }
    """)
    return divider


def make_sub_section_header(text: str) -> QLabel:
    """Create a styled sub-section header label."""
    from ui.font_utils import create_font, FontManager

    lbl = QLabel(text)
    lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
    lbl.setStyleSheet(SUB_SECTION_STYLE)
    return lbl


def make_badge(text: str, variant: str = "blue") -> QLabel:
    """Create a pill-shaped badge label.

    Args:
        text: Badge text.
        variant: One of 'blue', 'green', 'amber', 'red', 'gray'.
    """
    from ui.font_utils import create_font, FontManager

    styles = {
        "blue": BADGE_BLUE, "green": BADGE_GREEN, "amber": BADGE_AMBER,
        "red": BADGE_RED, "gray": BADGE_GRAY,
    }
    lbl = QLabel(text)
    lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
    lbl.setStyleSheet(styles.get(variant, BADGE_BLUE))
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(ScreenScale.h(24))
    return lbl


def make_mini_card(object_name: str = "MiniCard") -> QFrame:
    """Create a styled mini card frame for list items (persons, units)."""
    card = QFrame()
    card.setObjectName(object_name)
    card.setStyleSheet(MINI_CARD_STYLE)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(8)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 10))
    card.setGraphicsEffect(shadow)
    return card


def make_field_group(label_text: str, widget, label_style: str = None) -> QVBoxLayout:
    """Create a vertical label + widget group for forms.

    Args:
        label_text: Label text above the widget.
        widget: The input widget.
        label_style: Optional custom style for the label.
    """
    from ui.font_utils import create_font, FontManager

    box = QVBoxLayout()
    box.setSpacing(4)
    box.setContentsMargins(0, 0, 0, 0)

    lbl = QLabel(label_text)
    lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
    lbl.setStyleSheet(label_style or "color: #64748B; background: transparent; border: none;")
    box.addWidget(lbl)
    box.addWidget(widget)
    return box


def make_empty_state(icon_name: str, title: str, subtitle: str = "") -> QWidget:
    """Create a centered empty state widget with icon circle + text."""
    from ui.components.icon import Icon
    from ui.font_utils import create_font, FontManager

    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignCenter)
    layout.setSpacing(12)

    # Icon circle
    icon_circle = QLabel()
    icon_circle.setFixedSize(ScreenScale.w(80), ScreenScale.h(80))
    icon_circle.setAlignment(Qt.AlignCenter)
    icon_circle.setStyleSheet(EMPTY_STATE_ICON_STYLE)
    px = Icon.load_pixmap(icon_name, size=40)
    if px and not px.isNull():
        icon_circle.setPixmap(px)
    layout.addWidget(icon_circle, alignment=Qt.AlignCenter)

    # Title
    t = QLabel(title)
    t.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
    t.setStyleSheet("color: #475569; background: transparent; border: none;")
    t.setAlignment(Qt.AlignCenter)
    layout.addWidget(t)

    # Subtitle
    if subtitle:
        s = QLabel(subtitle)
        s.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        s.setStyleSheet("color: #94A3B8; background: transparent; border: none;")
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        s.setMaximumWidth(ScreenScale.w(320))
        layout.addWidget(s, alignment=Qt.AlignCenter)

    return container
