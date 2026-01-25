# -*- coding: utf-8 -*-
"""
Centralized Style Manager - مدير الأنماط المركزي
Single source of truth for ALL application styles.

This module provides a centralized way to generate QSS (Qt Style Sheets)
for all UI components in the application. It eliminates:
- Duplicate QSS code in components
- Inconsistent styling across the application
- Hard-to-maintain inline stylesheets

Architecture:
- DRY: Each style is defined once
- SOLID: Single Responsibility - each method handles one component type
- Clean Code: Clear naming, comprehensive documentation

Usage:
    from ui.style_manager import StyleManager

    # Apply button style
    button.setStyleSheet(StyleManager.button_primary())

    # Apply page background
    page.setStyleSheet(StyleManager.page_background())

    # Apply navbar style
    navbar.setStyleSheet(StyleManager.navbar())

Author: UN-Habitat TRRCMS Team
Created: 2025
"""

from enum import Enum
from typing import Optional
from .design_system import (
    Colors,
    ButtonDimensions,
    NavbarDimensions,
    PageDimensions,
    BorderRadius,
    Typography,
    Spacing
)


class ButtonVariant(Enum):
    """Button style variants"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    TEXT = "text"


class InputVariant(Enum):
    """Input field style variants"""
    DEFAULT = "default"
    ERROR = "error"
    SUCCESS = "success"


class StyleManager:
    """
    Centralized stylesheet generator.

    All QSS styles are generated here - NO styles should be defined in components!
    This ensures consistency and makes maintenance easier.

    Principles:
    - Single Source of Truth: All styles defined here
    - DRY: No duplicate style definitions
    - SOLID: Each method has single responsibility
    - Maintainable: Easy to update styles application-wide
    """

    # ==================== BUTTONS ====================

    @staticmethod
    def button_primary() -> str:
        """
        Get primary button stylesheet (PrimaryButton component).

        Usage: Main action buttons (e.g., "إضافة حالة جديدة")

        Figma Specs:
        - Size: 199×48px
        - Border-radius: 8px
        - Padding: 24×12px
        - Background: #3890DF (PRIMARY_BLUE)
        - Text: White

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QPushButton#PrimaryButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: {Colors.PRIMARY_WHITE};
                border: none;
                border-radius: {ButtonDimensions.PRIMARY_BORDER_RADIUS}px;
                padding: {ButtonDimensions.PRIMARY_PADDING_V}px {ButtonDimensions.PRIMARY_PADDING_H}px;
                text-align: center;
            }}
            QPushButton#PrimaryButton:hover {{
                background-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
            QPushButton#PrimaryButton:pressed {{
                background-color: {ButtonDimensions.PRIMARY_PRESSED_BG};
            }}
            QPushButton#PrimaryButton:disabled {{
                background-color: {ButtonDimensions.PRIMARY_DISABLED_BG};
                color: {ButtonDimensions.PRIMARY_DISABLED_TEXT};
            }}
        """

    @staticmethod
    def button_secondary() -> str:
        """
        Get secondary button stylesheet.

        Usage: Secondary actions (e.g., "إلغاء", "رجوع")

        Figma Specs:
        - Border: 1px solid PRIMARY_BLUE
        - Background: Transparent/White
        - Text: PRIMARY_BLUE

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QPushButton#SecondaryButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.PRIMARY_BLUE};
                border-radius: {BorderRadius.MD}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                text-align: center;
                min-height: 32px;
            }}
            QPushButton#SecondaryButton:hover {{
                background-color: rgba(56, 144, 223, 0.1);
                border-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
            QPushButton#SecondaryButton:pressed {{
                background-color: rgba(56, 144, 223, 0.2);
            }}
            QPushButton#SecondaryButton:disabled {{
                background-color: {Colors.BUTTON_DISABLED};
                color: {Colors.TEXT_DISABLED};
                border-color: {Colors.BORDER_DEFAULT};
            }}
        """

    @staticmethod
    def button_text() -> str:
        """
        Get text button stylesheet (no background, just text).

        Usage: Tertiary actions (e.g., "تخطي", "إلغاء")

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QPushButton#TextButton {{
                background-color: transparent;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                padding: {Spacing.SM}px {Spacing.MD}px;
                text-align: center;
            }}
            QPushButton#TextButton:hover {{
                background-color: rgba(56, 144, 223, 0.1);
                border-radius: {BorderRadius.SM}px;
            }}
            QPushButton#TextButton:pressed {{
                background-color: rgba(56, 144, 223, 0.2);
            }}
            QPushButton#TextButton:disabled {{
                color: {Colors.TEXT_DISABLED};
            }}
        """

    @staticmethod
    def button_danger() -> str:
        """
        Get danger button stylesheet (for destructive actions).

        Usage: Destructive actions (e.g., "حذف", "إزالة")

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QPushButton#DangerButton {{
                background-color: {Colors.ERROR};
                color: {Colors.PRIMARY_WHITE};
                border: none;
                border-radius: {BorderRadius.MD}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                text-align: center;
                min-height: 32px;
            }}
            QPushButton#DangerButton:hover {{
                background-color: #C0392B;
            }}
            QPushButton#DangerButton:pressed {{
                background-color: #A93226;
            }}
            QPushButton#DangerButton:disabled {{
                background-color: {Colors.BUTTON_DISABLED};
                color: {Colors.TEXT_DISABLED};
            }}
        """

    @staticmethod
    def button_icon() -> str:
        """
        Get icon button stylesheet (for cards, small actions).

        Usage: Icon-only buttons in cards

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #e3f2fd;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #bbdefb;
            }
            QPushButton:pressed {
                background-color: #90caf9;
            }
        """

    # ==================== INPUTS ====================

    @staticmethod
    def input_field(variant: InputVariant = InputVariant.DEFAULT) -> str:
        """
        Get input field stylesheet.

        Args:
            variant: Input variant (DEFAULT, ERROR, SUCCESS)

        Usage: Text inputs, text areas

        Returns:
            Complete QSS stylesheet string
        """
        border_color = Colors.INPUT_BORDER
        focus_color = Colors.INPUT_BORDER_FOCUS

        if variant == InputVariant.ERROR:
            border_color = Colors.INPUT_BORDER_ERROR
            focus_color = Colors.INPUT_BORDER_ERROR
        elif variant == InputVariant.SUCCESS:
            border_color = Colors.SUCCESS
            focus_color = Colors.SUCCESS

        return f"""
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 10px 14px;
                min-height: 22px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border: 2px solid {focus_color};
                padding: 9px 13px;
                outline: none;
            }}
            QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
                background-color: #F1F5F9;
                color: #94A3B8;
                border-color: #E2E8F0;
            }}
            QLineEdit::placeholder, QTextEdit::placeholder {{
                color: {Colors.INPUT_PLACEHOLDER};
            }}
        """

    @staticmethod
    def search_bar() -> str:
        """
        Get search bar stylesheet (for navbar search).

        Usage: Search bars in navbar

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QWidget {{
                background-color: {Colors.SEARCH_BG};
                border-radius: 4px;
            }}
        """

    # ==================== NAVBAR ====================

    @staticmethod
    def navbar() -> str:
        """
        Get complete navbar stylesheet.

        Usage: Main navbar component

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QFrame#navbar {{
                background-color: {Colors.NAVBAR_BG};
                border: none;
            }}
            QFrame#navbar_top {{
                background-color: {Colors.NAVBAR_BG};
                border-radius: 16px;
                border: none;
            }}
            QFrame#tabs_bar {{
                background-color: {Colors.NAVBAR_BG};
                border: none;
            }}
            QWidget#window_controls {{
                background: transparent;
            }}
            QPushButton#win_btn, QPushButton#win_close {{
                color: white;
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: 400;
                line-height: 16px;
                border-radius: 6px;
            }}
            QPushButton#win_btn:hover {{
                background: rgba(255, 255, 255, 0.1);
            }}
            QPushButton#win_btn:pressed {{
                background: rgba(255, 255, 255, 0.15);
            }}
            QPushButton#win_close:hover {{
                background: rgba(255, 59, 48, 0.90);
                color: white;
            }}
            QPushButton#win_close:pressed {{
                background: rgba(255, 59, 48, 0.75);
                color: white;
            }}
        """

    @staticmethod
    def tab_active() -> str:
        """
        Get active tab stylesheet.

        Usage: Active/selected tab in navbar

        Figma Specs:
        - Background: #DEEBFF
        - Text: #3B86FF
        - Border-radius: 8px
        - Padding: 5×12px

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QPushButton {{
                background-color: #DEEBFF;
                color: #3B86FF;
                border: none;
                border-radius: {NavbarDimensions.TAB_BORDER_RADIUS}px;
                padding: {NavbarDimensions.TAB_PADDING_V}px {NavbarDimensions.TAB_PADDING_H}px;
                text-align: center;
                line-height: {NavbarDimensions.TAB_LINE_HEIGHT}px;
            }}
            QPushButton:hover {{
                background-color: #CDE0FF;
            }}
        """

    @staticmethod
    def tab_inactive() -> str:
        """
        Get inactive tab stylesheet.

        Usage: Inactive/unselected tabs in navbar

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QPushButton {{
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                padding: {NavbarDimensions.TAB_PADDING_V}px {NavbarDimensions.TAB_PADDING_H}px;
                text-align: center;
                line-height: {NavbarDimensions.TAB_LINE_HEIGHT}px;
            }}
            QPushButton:hover {{
                color: rgba(255, 255, 255, 0.9);
                background: rgba(255, 255, 255, 0.05);
                border-radius: {NavbarDimensions.TAB_BORDER_RADIUS}px;
            }}
        """

    # ==================== CARDS ====================

    @staticmethod
    def card() -> str:
        """
        Get card container stylesheet.

        Usage: Claim cards, data cards

        Figma Specs:
        - Background: White (#FFFFFF)
        - Border: 1px solid #E1E8ED
        - Border-radius: 8px
        - Shadow: 0 4px 8px rgba(145, 158, 171, 0.16)

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QFrame#ClaimCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {PageDimensions.CARD_BORDER_RADIUS}px;
            }}
        """

    @staticmethod
    def card_details_container() -> str:
        """
        Get card details container stylesheet (inner pill-shaped box).

        Usage: Details section inside claim cards

        Figma Specs:
        - Background: #F8FAFF
        - Border: 1px solid #E5EAF6
        - Border-radius: 14px (pill shape - maximum for 28px height)
        - Padding: Applied via layout margins (not stylesheet)

        Note: Border-radius is set to 14px (height/2) for perfect pill shape.
        Padding is controlled by layout margins to avoid rendering conflicts.

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QFrame#detailsFrame {{
                background-color: {PageDimensions.CARD_DETAILS_BG};
                border: {PageDimensions.CARD_DETAILS_BORDER_WIDTH}px solid {PageDimensions.CARD_DETAILS_BORDER};
                border-radius: 14px;
            }}
        """

    # ==================== PAGES ====================

    @staticmethod
    def page_background() -> str:
        """
        Get page background stylesheet.

        Usage: Main content pages

        Figma Specs:
        - Background: #F0F7FF (BACKGROUND color)

        Returns:
            Complete QSS stylesheet string
        """
        return f"background-color: {Colors.BACKGROUND};"

    @staticmethod
    def page_header() -> str:
        """
        Get page header stylesheet.

        Usage: Page title headers

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QWidget {{
                background-color: {Colors.BACKGROUND};
                border: none;
            }}
        """

    # ==================== TABLES ====================

    @staticmethod
    def table() -> str:
        """
        Get data table stylesheet.

        Usage: QTableView, QTableWidget

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QTableView, QTableWidget {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD}px;
                gridline-color: #F1F5F9;
                selection-background-color: #EBF5FF;
                selection-color: {Colors.TEXT_PRIMARY};
                alternate-background-color: {Colors.TABLE_ROW_EVEN};
            }}
            QTableView::item, QTableWidget::item {{
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected, QTableWidget::item:selected {{
                background-color: #EBF5FF;
                color: {Colors.TEXT_PRIMARY};
            }}
            QTableView::item:hover {{
                background-color: #F8FAFC;
            }}
            QHeaderView::section {{
                background-color: {Colors.TABLE_HEADER_BG};
                color: {Colors.TEXT_PRIMARY};
                font-weight: 600;
                font-size: 9pt;
                text-transform: uppercase;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
                border-right: none;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
        """

    # ==================== DIALOGS ====================

    @staticmethod
    def dialog() -> str:
        """
        Get dialog/modal stylesheet.

        Usage: QDialog, modal windows

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QDialog {{
                background-color: {Colors.SURFACE};
                border-radius: {BorderRadius.LG}px;
            }}
        """

    # ==================== SCROLLBARS ====================

    @staticmethod
    def scrollbar() -> str:
        """
        Get scrollbar stylesheet.

        Usage: QScrollBar (vertical and horizontal)

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QScrollBar:vertical {{
                background-color: {Colors.BACKGROUND};
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
                background-color: {Colors.PRIMARY_BLUE};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background-color: {Colors.BACKGROUND};
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
                background-color: {Colors.PRIMARY_BLUE};
            }}
        """

    # ==================== LABELS ====================

    @staticmethod
    def label_title() -> str:
        """
        Get title label stylesheet.

        Usage: Page titles, section titles

        Returns:
            Complete QSS stylesheet string
        """
        return f"color: {Colors.TEXT_PRIMARY}; border: none;"

    @staticmethod
    def label_subtitle() -> str:
        """
        Get subtitle label stylesheet.

        Usage: Secondary text, descriptions

        Returns:
            Complete QSS stylesheet string
        """
        return f"color: {Colors.TEXT_SECONDARY}; border: none;"

    @staticmethod
    def label_error() -> str:
        """
        Get error label stylesheet.

        Usage: Error messages, validation errors

        Returns:
            Complete QSS stylesheet string
        """
        return f"color: {Colors.ERROR}; border: none;"

    @staticmethod
    def label_success() -> str:
        """
        Get success label stylesheet.

        Usage: Success messages, confirmations

        Returns:
            Complete QSS stylesheet string
        """
        return f"color: {Colors.SUCCESS}; border: none;"

    # ==================== EMPTY STATE ====================

    @staticmethod
    def empty_state() -> str:
        """
        Get empty state container stylesheet.

        Usage: Empty state widgets

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QWidget {{
                background-color: transparent;
            }}
        """

    # ==================== COMBO BOX ====================

    @staticmethod
    def combo_box() -> str:
        """
        Get combo box stylesheet.

        Usage: QComboBox dropdowns

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QComboBox {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM}px;
                padding: 8px 12px;
                min-height: 20px;
                min-width: 100px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QComboBox:hover {{
                border-color: {Colors.PRIMARY_BLUE};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {Colors.TEXT_PRIMARY};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                selection-background-color: rgba(56, 144, 223, 0.1);
                selection-color: {Colors.PRIMARY_BLUE};
            }}
        """

    # ==================== FORM INPUTS ====================

    @staticmethod
    def form_input() -> str:
        """
        Get standard form input stylesheet (matching person dialog design).

        Usage: QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox in forms

        Figma Specs:
        - Background: #F8FAFC
        - Border: 1px solid #E0E6ED
        - Border-radius: 8px
        - Height: 23px (min/max)
        - Focus border: #2D9CDB

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: #F8FAFC;
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
                border: 1px solid #2D9CDB;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                background-image: url(assets/images/down.png);
                background-repeat: no-repeat;
                background-position: center;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
            }
        """

    @staticmethod
    def date_input() -> str:
        """
        Get date input stylesheet with calendar icon on the left.

        Usage: QDateEdit in forms

        Figma Specs:
        - Background: #F8FAFC
        - Border: 1px solid #E0E6ED
        - Calendar icon: Left side, 25px width
        - Icon: assets/images/calender.png

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QDateEdit {
                background-color: #F8FAFC;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }
            QDateEdit:focus {
                border: 1px solid #2D9CDB;
                background-color: white;
            }
            QDateEdit::drop-down {
                image: url(assets/images/calender.png);
                width: 25px;
                border: none;
                padding-left: 10px;
            }
        """

    @staticmethod
    def mobile_input_container() -> str:
        """
        Get mobile number input container stylesheet.

        Usage: QFrame wrapping mobile input with prefix

        Figma Specs:
        - Background: #F8FAFC
        - Border: 1px solid #E0E6ED
        - Border-radius: 8px
        - Contains: prefix label + input field

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
            }
        """

    @staticmethod
    def mobile_input_prefix() -> str:
        """
        Get mobile number prefix label stylesheet.

        Usage: QLabel showing "+963 | 09"

        Figma Specs:
        - Color: #4A5568 (bold)
        - Width: 90px
        - No border

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QLabel {
                color: #4A5568;
                font-weight: bold;
                border: none;
                padding-left: 10px;
            }
        """

    @staticmethod
    def mobile_input_field() -> str:
        """
        Get mobile number input field stylesheet.

        Usage: QLineEdit for phone number (inside container)

        Figma Specs:
        - Background: transparent
        - No border
        - Padding: 10px

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QLineEdit {
                background: transparent;
                border: none;
                padding: 10px;
                color: #333;
            }
        """

    @staticmethod
    def file_upload_frame() -> str:
        """
        Get file upload frame stylesheet.

        Usage: QFrame for file upload area

        Figma Specs:
        - Background: #F0F7FF
        - Border: 2px dashed #BEE3F8
        - Border-radius: 10px
        - Min-height: 100px
        - Hover: #E6F2FF

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QFrame {
                background-color: #F0F7FF;
                border: 2px dashed #BEE3F8;
                border-radius: 10px;
                min-height: 100px;
            }
            QFrame:hover {
                background-color: #E6F2FF;
            }
        """

    @staticmethod
    def file_upload_button() -> str:
        """
        Get file upload button stylesheet.

        Usage: QPushButton for "ارفع صور المستندات"

        Figma Specs:
        - Color: #2D9CDB (blue)
        - Font-weight: bold
        - Background: transparent
        - Text-decoration: underline
        - Hover: #1E7BB0

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QPushButton {
                color: #2D9CDB;
                font-weight: bold;
                border: none;
                background: transparent;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #1E7BB0;
            }
        """

    @staticmethod
    def numeric_input() -> str:
        """
        Get numeric input stylesheet with percentage icon.

        Usage: QDoubleSpinBox for ownership share (حصة الملكية)

        Figma Specs:
        - Background: #F8FAFC
        - Border: 1px solid #E0E6ED
        - Border-radius: 8px
        - Height: 23px (min/max)
        - Icon: assets/images/percent.png on the left

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QDoubleSpinBox {
                background-color: #F8FAFC;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                padding-left: 35px;
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #2D9CDB;
                background-color: white;
            }
            QDoubleSpinBox::up-button {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 0px;
                border: none;
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: padding;
                subcontrol-position: left center;
                width: 25px;
                border: none;
                image: url(assets/images/percent.png);
                padding-left: 10px;
            }
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
                width: 0px;
                height: 0px;
            }
        """

    @staticmethod
    def spinbox_input_container() -> str:
        """
        Get spinbox input container stylesheet with stacked arrows.

        Usage: QFrame wrapping QLineEdit + stacked up/down arrow buttons

        Figma Specs:
        - Background: #F8FAFC
        - Border: 1px solid #E0E6ED
        - Border-radius: 8px
        - Height: 40px
        - Contains: stacked arrows (left) + value input (center)

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
            }
        """

    @staticmethod
    def spinbox_input_field() -> str:
        """
        Get spinbox input field stylesheet.

        Usage: QLineEdit for numeric value (inside spinbox container)

        Figma Specs:
        - Background: transparent
        - No border
        - Color: #999
        - Font-size: 16px
        - Alignment: Center

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QLineEdit {
                background: transparent;
                border: none;
                color: #999;
                font-size: 16px;
            }
        """

    @staticmethod
    def spinbox_arrow_button() -> str:
        """
        Get spinbox arrow button stylesheet.

        Usage: QPushButton for up/down arrows (inside spinbox container)

        Figma Specs:
        - Background: transparent
        - No border
        - Size: 20x15 each
        - Icons: assets/images/^.png and assets/images/down.png

        Returns:
            Complete QSS stylesheet string
        """
        return """
            QPushButton {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """

    # ==================== FOOTER ====================

    @staticmethod
    def wizard_footer() -> str:
        """
        Get wizard footer card stylesheet.

        Usage: Footer card in wizard with navigation buttons

        Figma Specs:
        - Size: 1512×74px
        - Background: White (#FFFFFF)
        - Border: 1px solid #E1E8ED
        - Internal padding: 130px left/right, 12px top/bottom
        - Shadow: Applied via QGraphicsDropShadowEffect (not stylesheet)

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QFrame#WizardFooter {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 0px;
            }}
        """

    # ==================== DIALOGS ====================

    @staticmethod
    def dialog_overlay() -> str:
        """
        Get dialog overlay stylesheet (semi-transparent dark background).

        Usage: Fullscreen overlay that covers the page when dialog is shown

        Figma Specs:
        - Background: rgba(0, 0, 0, 0.5) - 50% opacity black
        - Full screen coverage
        - Blocks interaction with underlying content

        Returns:
            Complete QSS stylesheet string
        """
        from ui.design_system import DialogColors

        return f"""
            QFrame#DialogOverlay {{
                background-color: {DialogColors.OVERLAY_BG};
            }}
        """

    @staticmethod
    def dialog_card() -> str:
        """
        Get dialog card stylesheet (white card containing dialog content).

        Usage: The white card that contains icon, title, message, and buttons

        Figma Specs:
        - Width: 480px (fixed)
        - Background: White (#FFFFFF)
        - Border-radius: 12px
        - Shadow: 0px 8px 16px rgba(0, 0, 0, 0.15)
        - Padding: 32px (all sides)

        Returns:
            Complete QSS stylesheet string
        """
        from ui.design_system import ButtonDimensions

        return f"""
            QFrame#DialogCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {ButtonDimensions.DIALOG_BORDER_RADIUS}px;
            }}
        """

    @staticmethod
    def dialog_button_primary() -> str:
        """
        Get primary button stylesheet for dialogs.

        Usage: Buttons inside dialogs (OK, Yes, Confirm, etc.)

        Figma Specs:
        - Height: 48px
        - Min-width: 120px
        - Background: Primary Blue (#3890DF)
        - Text: White
        - Border-radius: 8px
        - Font: 16px (12pt Qt), Normal weight

        Returns:
            Complete QSS stylesheet string
        """
        from ui.design_system import ButtonDimensions

        return f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: {ButtonDimensions.DIALOG_BUTTON_BORDER_RADIUS}px;
                padding: 12px 24px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: {ButtonDimensions.DIALOG_BUTTON_FONT_SIZE}pt;
            }}
            QPushButton:hover {{
                background-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
            QPushButton:pressed {{
                background-color: {Colors.PRIMARY_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_DISABLED};
            }}
        """

    @staticmethod
    def dialog_button_secondary() -> str:
        """
        Get secondary button stylesheet for dialogs.

        Usage: Secondary buttons inside dialogs (Cancel, No, etc.)

        Figma Specs:
        - Height: 48px
        - Min-width: 120px
        - Background: Transparent/White
        - Text: Primary Blue
        - Border: 1px solid Border color
        - Border-radius: 8px

        Returns:
            Complete QSS stylesheet string
        """
        from ui.design_system import ButtonDimensions

        return f"""
            QPushButton {{
                background-color: {Colors.SURFACE};
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {ButtonDimensions.DIALOG_BUTTON_BORDER_RADIUS}px;
                padding: 12px 24px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: {ButtonDimensions.DIALOG_BUTTON_FONT_SIZE}pt;
            }}
            QPushButton:hover {{
                background-color: {Colors.BACKGROUND_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {Colors.BORDER_DEFAULT};
            }}
            QPushButton:disabled {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                color: {Colors.TEXT_DISABLED};
            }}
        """


# Convenience functions for backward compatibility
def get_button_style(variant: str = "primary") -> str:
    """
    Convenience function to get button style by variant name.

    Args:
        variant: Button variant ("primary", "secondary", "text", "danger")

    Returns:
        QSS stylesheet string
    """
    if variant == "primary":
        return StyleManager.button_primary()
    elif variant == "secondary":
        return StyleManager.button_secondary()
    elif variant == "text":
        return StyleManager.button_text()
    elif variant == "danger":
        return StyleManager.button_danger()
    else:
        return StyleManager.button_primary()


def get_input_style(variant: str = "default") -> str:
    """
    Convenience function to get input style by variant name.

    Args:
        variant: Input variant ("default", "error", "success")

    Returns:
        QSS stylesheet string
    """
    if variant == "error":
        return StyleManager.input_field(InputVariant.ERROR)
    elif variant == "success":
        return StyleManager.input_field(InputVariant.SUCCESS)
    else:
        return StyleManager.input_field(InputVariant.DEFAULT)
