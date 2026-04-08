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
- Each style is defined once
- Each method handles one component type
- Clear naming, comprehensive documentation

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
from pathlib import Path
from .design_system import (
    Colors,
    ButtonDimensions,
    NavbarDimensions,
    PageDimensions,
    BorderRadius,
    Typography,
    Spacing
)

# Absolute path to images directory for stylesheet url() references
_IMAGES_DIR = str(Path(__file__).parent.parent / "assets" / "images").replace("\\", "/")


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
    - No duplicate style definitions
    - Each method has single responsibility
    - Maintainable: Easy to update styles application-wide
    """

    @staticmethod
    def button_primary() -> str:
        """
        Get primary button stylesheet (PrimaryButton component).

        Usage: Main action buttons (e.g., "إضافة حالة جديدة")
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
                background-color: {Colors.NAVBAR_GRADIENT_TOP};
                border: none;
            }}
            QFrame#navbar_top {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #061222,
                    stop:0.4 {Colors.NAVBAR_GRADIENT_MID},
                    stop:1.0 {Colors.NAVBAR_GRADIENT_BOT}
                );
                border-radius: 16px;
                border: none;
            }}
            QWidget#window_controls {{
                background: transparent;
            }}
            QPushButton#win_btn, QPushButton#win_close {{
                color: rgba(180, 210, 245, 190);
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: 400;
                line-height: 16px;
                border-radius: 6px;
            }}
            QPushButton#win_btn:hover {{
                background: rgba(56, 144, 223, 0.18);
                color: white;
            }}
            QPushButton#win_btn:pressed {{
                background: rgba(56, 144, 223, 0.30);
                color: white;
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

    @staticmethod
    def card() -> str:
        """
        Get card container stylesheet.

        Usage: Claim cards, data cards
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

    @staticmethod
    def page_background() -> str:
        """
        Get page background stylesheet.

        Usage: Main content pages
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
                width: 16px;
                border-radius: 8px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #c0c0c0;
                border-radius: 8px;
                min-height: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {Colors.PRIMARY_BLUE};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background-color: {Colors.BACKGROUND};
                height: 16px;
                border-radius: 8px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: #c0c0c0;
                border-radius: 8px;
                min-width: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {Colors.PRIMARY_BLUE};
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """

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

    @staticmethod
    def form_input() -> str:
        """
        Unified search/filter input stylesheet.

        Used for QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox across
        all pages — filter bars, search inputs, combo filters.

        Design:
        - Background: white (#FFFFFF) for clear contrast on page bg
        - Border: 1.5px solid #D0D7E2 (visible but not heavy)
        - Border-radius: 8px
        - Focus border: Colors.PRIMARY_BLUE
        - Placeholder: Colors.INPUT_PLACEHOLDER

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {{
                border: 1.5px solid #D0D7E2;
                border-radius: 8px;
                padding: 6px 12px;
                background-color: {Colors.SURFACE};
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                min-height: 28px;
                max-height: 28px;
            }}
            QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QDoubleSpinBox:hover {{
                border-color: #93C5FD;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {{
                border-color: {Colors.PRIMARY_BLUE};
                background-color: {Colors.SURFACE};
            }}
            QLineEdit::placeholder {{
                color: {Colors.INPUT_PLACEHOLDER};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                image: url({_IMAGES_DIR}/down.png);
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.SURFACE};
                border: 1px solid #D0D7E2;
                selection-background-color: rgba(56, 144, 223, 0.1);
                selection-color: {Colors.PRIMARY_BLUE};
            }}
        """

    @staticmethod
    def date_input() -> str:
        """
        Get date input stylesheet with calendar icon on the left.

        Usage: QDateEdit in forms
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
                selection-background-color: transparent;
                selection-color: #333;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #2D9CDB;
                background-color: white;
                outline: 0;
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

    @staticmethod
    def wizard_footer() -> str:
        """
        Get wizard footer card stylesheet.

        Usage: Footer card in wizard with navigation buttons
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

    @staticmethod
    def dialog_overlay() -> str:
        """
        Get dialog overlay stylesheet (semi-transparent dark background).

        Usage: Fullscreen overlay that covers the page when dialog is shown
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
    def stats_card(accent_color: str) -> str:
        """
        Get stats card stylesheet with colored left accent border.

        Args:
            accent_color: Left border accent color hex string

        Returns:
            Complete QSS stylesheet string
        """
        return f"""
            QFrame#StatsCard {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-left: 4px solid {accent_color};
                border-radius: 8px;
            }}
        """

    @staticmethod
    def dialog_button_secondary() -> str:
        """
        Get secondary button stylesheet for dialogs.

        Usage: Secondary buttons inside dialogs (Cancel, No, etc.)
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


    # -- New shared styles for cohesive redesign --

    @staticmethod
    def dark_search_input() -> str:
        """Frosted glass search input for use inside DarkHeaderZone."""
        return """
            QLineEdit {
                background: rgba(10, 22, 40, 140);
                color: white;
                border: 1px solid rgba(56, 144, 223, 35);
                border-radius: 8px;
                padding: 0 12px 0 34px;
            }
            QLineEdit:focus {
                border: 1.5px solid rgba(56, 144, 223, 140);
                background: rgba(10, 22, 40, 180);
            }
            QLineEdit::placeholder {
                color: rgba(139, 172, 200, 130);
            }
        """

    @staticmethod
    def dark_combo_box() -> str:
        """Dark-themed combo box for use inside DarkHeaderZone."""
        return """
            QComboBox {
                background: rgba(10, 22, 40, 140);
                color: white;
                border: 1px solid rgba(56, 144, 223, 35);
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 10pt;
                min-width: 140px;
            }
            QComboBox:hover { border-color: rgba(56, 144, 223, 80); }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255, 255, 255, 0.5);
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #0F1E36;
                color: white;
                border: 1px solid rgba(56, 144, 223, 40);
                border-radius: 6px;
                selection-background-color: rgba(56, 144, 223, 50);
                outline: none;
                padding: 4px;
            }
        """

    @staticmethod
    def dark_action_button() -> str:
        """Gradient blue action button for dark header zones."""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                    stop:0 #4DA0EF, stop:0.45 #3890DF, stop:1 #2E7BD6);
                color: white;
                border: 1px solid rgba(120, 190, 255, 0.35);
                border-radius: 10px;
                padding: 0 24px;
                font-weight: 700;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                    stop:0 #5AACFF, stop:0.45 #4DA0EF, stop:1 #3890DF);
                border: 1px solid rgba(140, 210, 255, 0.55);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                    stop:0 #3890DF, stop:0.5 #2E7BD6, stop:1 #266FC0);
                border: 1px solid rgba(100, 170, 240, 0.25);
            }
            QPushButton:disabled {
                background: rgba(56, 144, 223, 0.25);
                color: rgba(255, 255, 255, 0.4);
                border: 1px solid rgba(56, 144, 223, 0.15);
            }
        """

    @staticmethod
    def data_card() -> str:
        """Blue-tinted card with subtle gradient for data list items."""
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border-radius: 14px;
                border: 1px solid #E2EAF2;
            }
        """

    @staticmethod
    def data_card_hover() -> str:
        """Hover state for data cards."""
        return """
            QFrame {
                background: #F0F5FF;
                border-radius: 14px;
                border: 1px solid rgba(56, 144, 223, 0.3);
            }
        """

    @staticmethod
    def form_card() -> str:
        """White form card with shadow and rounded corners."""
        return f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: 1px solid #E2EAF2;
                border-radius: 14px;
            }}
        """

    @staticmethod
    def form_input_light() -> str:
        """Light-themed form input for use inside white cards."""
        return """
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #F8FAFF;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                padding: 8px 12px;
                color: #606266;
                font-size: 10pt;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #3890DF;
            }
            QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
                background-color: #F1F5F9;
                color: #94A3B8;
            }
        """

    @staticmethod
    def form_combo_light() -> str:
        """Light-themed combo box for use inside white form cards."""
        return f"""
            QComboBox {{
                padding: 6px 12px 6px 12px;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
                background-color: #F8FAFF;
                font-size: 10pt;
                color: #606266;
            }}
            QComboBox:focus {{
                border: 1px solid #3890DF;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 35px;
                border: none;
                margin-right: 5px;
            }}
            QComboBox::down-arrow {{
                image: url({_IMAGES_DIR}/v.png);
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                font-size: 10pt;
                background-color: white;
                selection-background-color: #3890DF;
                selection-color: white;
            }}
        """

    @staticmethod
    def wizard_step_pill(active: bool = False, completed: bool = False) -> str:
        """Step indicator pill for wizard progress inside dark header."""
        if completed:
            return """
                QLabel {
                    background: rgba(16, 185, 129, 0.2);
                    color: #6EE7B7;
                    border: 1px solid rgba(16, 185, 129, 0.4);
                    border-radius: 14px;
                    padding: 4px 16px;
                    font-weight: 600;
                }
            """
        elif active:
            return """
                QLabel {
                    background: rgba(56, 144, 223, 0.25);
                    color: white;
                    border: 1px solid rgba(120, 190, 255, 0.6);
                    border-radius: 14px;
                    padding: 4px 16px;
                    font-weight: 700;
                }
            """
        else:
            return """
                QLabel {
                    background: rgba(15, 31, 61, 0.5);
                    color: rgba(139, 172, 200, 160);
                    border: 1px solid rgba(56, 144, 223, 20);
                    border-radius: 14px;
                    padding: 4px 16px;
                    font-weight: 400;
                }
            """

    @staticmethod
    def step_connector(active: bool = False) -> str:
        """Connector line between wizard steps."""
        color = "rgba(56, 144, 223, 0.6)" if active else "rgba(56, 144, 223, 0.15)"
        return f"""
            QFrame {{
                background-color: {color};
                max-height: 2px;
                min-height: 2px;
            }}
        """

    @staticmethod
    def nav_footer() -> str:
        """Elevated wizard/page footer with shadow border."""
        return f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border-top: 1px solid #E2EAF2;
            }}
        """

    @staticmethod
    def nav_button_primary() -> str:
        """Primary navigation button (Next, Confirm) for wizard footers."""
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4DA0EF, stop:0.5 #3890DF, stop:1 #2E7BD6);
                color: white;
                border: 1px solid rgba(120, 190, 255, 0.3);
                border-radius: 10px;
                padding: 8px 32px;
                font-weight: 700;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5AACFF, stop:0.5 #4DA0EF, stop:1 #3890DF);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3890DF, stop:0.5 #2E7BD6, stop:1 #266FC0);
            }}
            QPushButton:disabled {{
                background: #E8EDF2;
                color: #B0BEC5;
                border-color: #DDE3EA;
            }}
        """

    @staticmethod
    def nav_button_secondary() -> str:
        """Secondary navigation button (Back, Cancel) for wizard footers."""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FAFBFF, stop:1 #F0F4FA);
                border: 1px solid rgba(56, 144, 223, 0.20);
                border-radius: 10px;
                color: #3890DF;
                padding: 8px 32px;
                font-weight: 600;
                font-size: 12pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #EBF5FF, stop:1 #E0EDFA);
                border-color: rgba(56, 144, 223, 0.40);
            }
            QPushButton:pressed {
                background: #E0EDFA;
            }
            QPushButton:disabled {
                color: #C0C8D0;
                background: #F5F7FA;
                border-color: #E8ECF0;
            }
        """

    @staticmethod
    def accordion_header() -> str:
        """Accordion header card style for expandable sections."""
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border: 1px solid #E2EAF2;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: rgba(56, 144, 223, 0.35);
                background: #F0F5FF;
            }
        """

    @staticmethod
    def accordion_body() -> str:
        """Accordion body content area."""
        return f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: 1px solid #E8EDF2;
                border-top: none;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
        """

    @staticmethod
    def status_badge(color: str, bg: str, border: str = "") -> str:
        """Colored status badge/pill."""
        border_css = f"border: 1px solid {border};" if border else f"border: 1px solid {color}33;"
        return f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                {border_css}
                border-radius: 11px;
                padding: 2px 10px;
                font-weight: 600;
            }}
        """

    @staticmethod
    def modern_table() -> str:
        """Modern table styling with blue-tinted headers and hover effects."""
        return """
            QTableWidget {
                border: none;
                background-color: white;
                font-size: 10.5pt;
                font-weight: 400;
                color: #212B36;
            }
            QTableWidget::item {
                padding: 8px 15px;
                border-bottom: 1px solid #F0F0F0;
                color: #212B36;
                font-size: 10.5pt;
                font-weight: 400;
            }
            QTableWidget::item:hover {
                background-color: #F5F9FF;
            }
            QHeaderView {
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QHeaderView::section {
                background-color: #F0F7FF;
                padding: 12px;
                padding-left: 30px;
                border: none;
                border-bottom: 2px solid #E0EFFF;
                color: #3890DF;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }
            QHeaderView::section:hover {
                background-color: #E0EFFF;
            }
            QTableView {
                border: none;
                background-color: white;
            }
            QTableView::item {
                padding: 12px 8px;
                border-bottom: 1px solid #F0F4F8;
            }
            QTableView::item:selected {
                background-color: #EBF5FF;
                color: #212B36;
            }
            QTableView::item:hover {
                background-color: #F5F9FF;
            }
        """

    @staticmethod
    def table_card() -> str:
        """White card container for tables with rounded corners."""
        return """
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 1px solid #E8EDF2;
            }
        """

    @staticmethod
    def pagination_button(active: bool = False) -> str:
        """Pagination page number button."""
        if active:
            return f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    min-width: 32px;
                    min-height: 32px;
                    max-width: 32px;
                    max-height: 32px;
                    font-weight: 600;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid #E8EDF2;
                border-radius: 8px;
                min-width: 32px;
                min-height: 32px;
                max-width: 32px;
                max-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #F0F5FF;
                border-color: rgba(56, 144, 223, 0.3);
                color: {Colors.PRIMARY_BLUE};
            }}
        """

    @staticmethod
    def refresh_button_dark() -> str:
        """Refresh/action button styled for dark header zone."""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2E7BD6, stop:1 #3890DF);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 7px 18px;
                font-size: 10pt;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3688E3, stop:1 #4A9EED);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2568B8, stop:1 #2E7BD6);
            }
        """

    @staticmethod
    def back_button_light() -> str:
        """Light-themed back button for content areas."""
        return """
            QPushButton {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
        """

    @staticmethod
    def empty_state_dark() -> str:
        """Dark constellation-themed empty state background."""
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0E2035, stop:0.5 #132D50, stop:1 #1A3860);
                border-radius: 16px;
                border: 1px solid rgba(56, 144, 223, 0.15);
            }
        """

    @staticmethod
    def radio_button() -> str:
        """Styled radio button."""
        return f"""
            QRadioButton {{
                background: transparent;
                border: none;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #C4CDD5;
                background: {Colors.BACKGROUND};
            }}
            QRadioButton::indicator:hover {{
                border-color: {Colors.PRIMARY_BLUE};
            }}
            QRadioButton::indicator:checked {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 4px solid {Colors.PRIMARY_BLUE};
                background: {Colors.PRIMARY_BLUE};
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


def mark_field_error(widget, error_label=None, message: str = "") -> None:
    """Apply error visual state to an input widget.

    Args:
        widget: QLineEdit, QComboBox, or similar input widget.
        error_label: Optional QLabel to show the error message below the field.
        message: Error text to display in the error_label.
    """
    widget.setStyleSheet(StyleManager.input_field(InputVariant.ERROR))
    if error_label is not None:
        error_label.setText(message)
        error_label.setVisible(bool(message))


def mark_field_valid(widget, error_label=None) -> None:
    """Apply success/valid visual state to an input widget."""
    widget.setStyleSheet(StyleManager.input_field(InputVariant.SUCCESS))
    if error_label is not None:
        error_label.setVisible(False)


def clear_field_state(widget, error_label=None) -> None:
    """Reset an input widget to its default (neutral) visual state."""
    widget.setStyleSheet(StyleManager.input_field(InputVariant.DEFAULT))
    if error_label is not None:
        error_label.setVisible(False)


def required_label_html(text: str) -> str:
    """Return an HTML label string with a red asterisk for required fields.

    Usage::

        label.setText(required_label_html(tr("field.name")))

    Args:
        text: The field label text (plain string).
    Returns:
        HTML string with a red asterisk appended.
    """
    return f"{text} <span style='color:{Colors.ERROR};'>*</span>"
