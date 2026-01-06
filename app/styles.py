# -*- coding: utf-8 -*-
"""
UN-Habitat branding stylesheet for PyQt5.
"""

from .config import Config


def get_stylesheet() -> str:
    """Generate the main application stylesheet with UN-Habitat branding."""
    return f"""
    /* ===== Global Styles ===== */
    QWidget {{
        font-family: "{Config.FONT_FAMILY}", "{Config.ARABIC_FONT_FAMILY}", sans-serif;
        font-size: {Config.FONT_SIZE}pt;
        color: {Config.TEXT_COLOR};
        background-color: {Config.BACKGROUND_COLOR};
    }}

    /* ===== Main Window ===== */
    QMainWindow {{
        background-color: {Config.BACKGROUND_COLOR};
    }}

    /* ===== Sidebar ===== */
    #sidebar {{
        background-color: {Config.SIDEBAR_BG};
        border: none;
    }}

    #sidebar QLabel {{
        color: white;
    }}

    #sidebar QPushButton {{
        background-color: transparent;
        color: rgba(255, 255, 255, 0.85);
        border: none;
        text-align: left;
        padding: 14px 20px;
        font-size: {Config.FONT_SIZE}pt;
        font-weight: 500;
        border-radius: 0;
        margin: 0;
        border-left: 3px solid transparent;
    }}

    #sidebar QPushButton:hover {{
        background-color: {Config.SIDEBAR_HOVER};
        color: white;
    }}

    #sidebar QPushButton:checked,
    #sidebar QPushButton[selected="true"] {{
        background-color: {Config.SIDEBAR_ACTIVE};
        border-left: 3px solid {Config.ACCENT_COLOR};
        color: white;
    }}

    #sidebar #logo-container {{
        padding: 24px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }}

    #sidebar #app-title {{
        color: white;
        font-size: 16pt;
        font-weight: 600;
        letter-spacing: 1px;
    }}

    /* ===== Top Bar ===== */
    #topbar {{
        background-color: {Config.CARD_BACKGROUND};
        border-bottom: 1px solid {Config.BORDER_COLOR};
        min-height: {Config.TOPBAR_HEIGHT}px;
    }}

    #topbar QLabel {{
        color: {Config.TEXT_COLOR};
        font-size: {Config.FONT_SIZE_HEADING}pt;
        font-weight: bold;
    }}

    #topbar QPushButton {{
        background-color: transparent;
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 4px;
        padding: 6px 12px;
        min-width: 32px;
    }}

    #topbar QPushButton:hover {{
        background-color: {Config.BACKGROUND_COLOR};
        border-color: {Config.PRIMARY_COLOR};
    }}

    /* ===== Cards ===== */
    .card {{
        background-color: {Config.CARD_BACKGROUND};
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 8px;
        padding: 16px;
    }}

    QFrame[class="card"] {{
        background-color: {Config.CARD_BACKGROUND};
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 8px;
    }}

    /* ===== Buttons ===== */
    QPushButton {{
        background-color: {Config.PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: 500;
        min-height: 32px;
    }}

    QPushButton:hover {{
        background-color: {Config.PRIMARY_DARK};
    }}

    QPushButton:pressed {{
        background-color: {Config.PRIMARY_DARK};
    }}

    QPushButton:disabled {{
        background-color: #cccccc;
        color: #666666;
    }}

    QPushButton[class="secondary"] {{
        background-color: transparent;
        color: {Config.PRIMARY_COLOR};
        border: 1px solid {Config.PRIMARY_COLOR};
    }}

    QPushButton[class="secondary"]:hover {{
        background-color: {Config.PRIMARY_LIGHT};
        color: white;
    }}

    QPushButton[class="success"] {{
        background-color: {Config.SUCCESS_COLOR};
    }}

    QPushButton[class="success"]:hover {{
        background-color: #218838;
    }}

    QPushButton[class="danger"] {{
        background-color: {Config.ERROR_COLOR};
    }}

    QPushButton[class="danger"]:hover {{
        background-color: #c82333;
    }}

    QPushButton[class="warning"] {{
        background-color: {Config.WARNING_COLOR};
        color: {Config.TEXT_COLOR};
    }}

    /* ===== Input Fields ===== */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
        background-color: {Config.INPUT_BG};
        border: 1px solid {Config.INPUT_BORDER};
        border-radius: 6px;
        padding: 10px 14px;
        min-height: 22px;
        font-size: {Config.FONT_SIZE}pt;
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {Config.INPUT_FOCUS};
        padding: 9px 13px;
        outline: none;
    }}

    QLineEdit:disabled {{
        background-color: #F1F5F9;
        color: #94A3B8;
        border-color: #E2E8F0;
    }}

    /* ===== ComboBox ===== */
    QComboBox {{
        background-color: white;
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 4px;
        padding: 8px 12px;
        min-height: 20px;
        min-width: 100px;
    }}

    QComboBox:hover {{
        border-color: {Config.PRIMARY_COLOR};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {Config.TEXT_COLOR};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: white;
        border: 1px solid {Config.BORDER_COLOR};
        selection-background-color: {Config.PRIMARY_LIGHT};
        selection-color: white;
    }}

    /* ===== Tables ===== */
    QTableView, QTableWidget {{
        background-color: white;
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 8px;
        gridline-color: #F1F5F9;
        selection-background-color: #EBF5FF;
        selection-color: {Config.TEXT_COLOR};
        alternate-background-color: {Config.TABLE_ROW_ALT};
    }}

    QTableView::item, QTableWidget::item {{
        padding: 12px 8px;
        border-bottom: 1px solid #F1F5F9;
    }}

    QTableView::item:selected, QTableWidget::item:selected {{
        background-color: #EBF5FF;
        color: {Config.TEXT_COLOR};
    }}

    QTableView::item:hover {{
        background-color: #F8FAFC;
    }}

    QHeaderView::section {{
        background-color: {Config.TABLE_HEADER_BG};
        color: {Config.TEXT_LIGHT};
        font-weight: 600;
        font-size: 9pt;
        text-transform: uppercase;
        padding: 12px 8px;
        border: none;
        border-bottom: 1px solid {Config.BORDER_COLOR};
        border-right: none;
    }}

    QHeaderView::section:last {{
        border-right: none;
    }}

    /* ===== Tab Widget ===== */
    QTabWidget::pane {{
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 4px;
        background-color: {Config.CARD_BACKGROUND};
        margin-top: -1px;
    }}

    QTabBar::tab {{
        background-color: {Config.BACKGROUND_COLOR};
        color: {Config.TEXT_COLOR};
        border: 1px solid {Config.BORDER_COLOR};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 10px 20px;
        margin-right: 2px;
    }}

    QTabBar::tab:selected {{
        background-color: {Config.CARD_BACKGROUND};
        color: {Config.PRIMARY_COLOR};
        font-weight: bold;
        border-bottom: 2px solid {Config.PRIMARY_COLOR};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: white;
    }}

    /* ===== ScrollBar ===== */
    QScrollBar:vertical {{
        background-color: {Config.BACKGROUND_COLOR};
        width: 12px;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical {{
        background-color: #c0c0c0;
        border-radius: 6px;
        min-height: 30px;
        margin: 2px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {Config.PRIMARY_COLOR};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: {Config.BACKGROUND_COLOR};
        height: 12px;
        border-radius: 6px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: #c0c0c0;
        border-radius: 6px;
        min-width: 30px;
        margin: 2px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {Config.PRIMARY_COLOR};
    }}

    /* ===== Progress Bar ===== */
    QProgressBar {{
        background-color: {Config.BACKGROUND_COLOR};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {Config.PRIMARY_COLOR};
        border-radius: 4px;
    }}

    /* ===== Group Box ===== */
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 12px;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        color: {Config.PRIMARY_COLOR};
    }}

    /* ===== Labels ===== */
    QLabel {{
        color: {Config.TEXT_COLOR};
        background-color: transparent;
    }}

    QLabel[class="title"] {{
        font-size: {Config.FONT_SIZE_TITLE}pt;
        font-weight: bold;
        color: {Config.PRIMARY_COLOR};
    }}

    QLabel[class="heading"] {{
        font-size: {Config.FONT_SIZE_HEADING}pt;
        font-weight: bold;
    }}

    QLabel[class="subtitle"] {{
        font-size: {Config.FONT_SIZE}pt;
        color: {Config.TEXT_LIGHT};
    }}

    QLabel[class="error"] {{
        color: {Config.ERROR_COLOR};
    }}

    QLabel[class="success"] {{
        color: {Config.SUCCESS_COLOR};
    }}

    QLabel[class="warning"] {{
        color: {Config.WARNING_COLOR};
    }}

    /* ===== Tooltip ===== */
    QToolTip {{
        background-color: {Config.TEXT_COLOR};
        color: white;
        border: none;
        padding: 6px 10px;
        border-radius: 4px;
    }}

    /* ===== Splitter ===== */
    QSplitter::handle {{
        background-color: {Config.BORDER_COLOR};
    }}

    QSplitter::handle:horizontal {{
        width: 2px;
    }}

    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* ===== Menu ===== */
    QMenu {{
        background-color: white;
        border: 1px solid {Config.BORDER_COLOR};
        border-radius: 4px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 8px 32px 8px 16px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {Config.PRIMARY_LIGHT};
        color: white;
    }}

    /* ===== Status Bar ===== */
    QStatusBar {{
        background-color: {Config.CARD_BACKGROUND};
        border-top: 1px solid {Config.BORDER_COLOR};
    }}

    /* ===== Login Page ===== */
    #login-container {{
        background-color: {Config.PRIMARY_COLOR};
    }}

    #login-card {{
        background-color: white;
        border-radius: 8px;
        padding: 32px;
    }}

    #login-logo {{
        margin-bottom: 24px;
    }}

    #login-title {{
        font-size: 20pt;
        font-weight: bold;
        color: {Config.PRIMARY_COLOR};
        margin-bottom: 8px;
    }}

    /* ===== Dashboard ===== */
    .stat-card {{
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        border: 1px solid {Config.BORDER_COLOR};
    }}

    .stat-value {{
        font-size: 28pt;
        font-weight: bold;
        color: {Config.PRIMARY_COLOR};
    }}

    .stat-label {{
        font-size: {Config.FONT_SIZE}pt;
        color: {Config.TEXT_LIGHT};
    }}

    /* ===== Toast Notifications ===== */
    #toast {{
        background-color: {Config.TEXT_COLOR};
        color: white;
        border-radius: 4px;
        padding: 12px 20px;
    }}

    #toast[type="success"] {{
        background-color: {Config.SUCCESS_COLOR};
    }}

    #toast[type="error"] {{
        background-color: {Config.ERROR_COLOR};
    }}

    #toast[type="warning"] {{
        background-color: {Config.WARNING_COLOR};
        color: {Config.TEXT_COLOR};
    }}

    #toast[type="info"] {{
        background-color: {Config.INFO_COLOR};
    }}

    /* ===== Import Wizard ===== */
    #wizard-step {{
        font-weight: bold;
        padding: 12px 24px;
        border-radius: 20px;
        margin: 0 4px;
    }}

    #wizard-step[active="true"] {{
        background-color: {Config.PRIMARY_COLOR};
        color: white;
    }}

    #wizard-step[completed="true"] {{
        background-color: {Config.SUCCESS_COLOR};
        color: white;
    }}

    #wizard-step[pending="true"] {{
        background-color: {Config.BACKGROUND_COLOR};
        color: {Config.TEXT_LIGHT};
    }}
    """


def get_rtl_stylesheet() -> str:
    """Get additional RTL-specific styles for Arabic."""
    return """
    /* RTL Adjustments */
    #sidebar QPushButton {
        text-align: right;
        padding: 12px 16px;
    }

    #sidebar QPushButton:checked,
    #sidebar QPushButton[selected="true"] {
        border-left: none;
        border-right: 3px solid #FDB714;
    }

    QTableView, QTableWidget {
        /* RTL text alignment handled programmatically */
    }
    """
