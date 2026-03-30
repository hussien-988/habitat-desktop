"""UN-Habitat TRRCMS Design System."""

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtCore import Qt


class ScreenScale:
    """Screen-aware scaling utility.

    Call ScreenScale.initialize(screen_geometry) once from the main window
    before any UI is built. On screens smaller than 1512x982, dimensions
    scale down proportionally. On larger screens, no scaling (1.0).
    """
    _ref_width = 1512
    _ref_height = 982
    _scale_x = 1.0
    _scale_y = 1.0

    @classmethod
    def initialize(cls, screen_geometry):
        avail_w = screen_geometry.width()
        avail_h = screen_geometry.height()
        cls._scale_x = min(avail_w / cls._ref_width, 1.0)
        cls._scale_y = min(avail_h / cls._ref_height, 1.0)

    @classmethod
    def w(cls, px):
        """Scale a horizontal pixel value."""
        return max(1, int(px * cls._scale_x))

    @classmethod
    def h(cls, px):
        """Scale a vertical pixel value."""
        return max(1, int(px * cls._scale_y))

    @classmethod
    def scale(cls):
        """Overall scale factor (min of x, y)."""
        return min(cls._scale_x, cls._scale_y)


class Colors:
    """Color palette."""
    # Primary Colors
    PRIMARY_BLUE = "#3890DF"  # UN-Habitat primary blue
    PRIMARY_BLUE_LIGHT = "#00B2E3"  # Light blue accent (original UN-Habitat)
    PRIMARY_BLACK = "#000000"
    PRIMARY_WHITE = "#FFFFFF"

    # UI Colors
    BACKGROUND = "#f0f7ff"  # Light gray background (main app background)
    BACKGROUND_LIGHT = "#F0F4F8"  # Very light blue-gray (login page)
    SURFACE = "#FFFFFF"  # White surface/cards
    LIGHT_GRAY_BG = "#FAFBFC"  # Very light gray for alternating rows

    # Navbar colors
    NAVBAR_BG = "#122C49"  # Dark navy blue navbar background
    NAVBAR_BG_HOVER = "#1A3A5C"  # Slightly lighter on hover
    NAVBAR_BORDER = "#0F2338"  # Darker border below navbar
    NAVBAR_TAB_ACTIVE = "#9BC2FF"  # Active tab indicator color

    # Search bar background
    SEARCH_BG = "#1A3A5C"  # Search bar background in navbar (slightly lighter than navbar)

    # Old dark theme colors (DEPRECATED - keeping for backward compatibility)
    DARK_BG_PRIMARY = "#122C49"  # Now same as NAVBAR_BG
    DARK_BG_SECONDARY = "#1A3A5C"  # Now same as NAVBAR_BG_HOVER
    DARK_SURFACE = "#34495E"  # Dark surface for cards (rarely used)

    # Text Colors
    TEXT_PRIMARY = "#2C3E50"  # Dark gray for main text
    TEXT_SECONDARY = "#7F8C9B"  # Medium gray for secondary text
    TEXT_DISABLED = "#BDC3C7"  # Light gray for disabled state
    TEXT_ON_DARK = "#FFFFFF"  # White text on dark backgrounds
    TEXT_ON_PRIMARY = "#FFFFFF"  # White text on primary blue

    # Page Title Colors (Unified across all pages)
    PAGE_TITLE = "#212B36"  # Unified color for all page titles (24px/18pt, SemiBold)
    PAGE_SUBTITLE = "#7F8C9B"  # Unified color for all page subtitles (14px/10pt, SemiBold)

    # Wizard-specific text colors
    WIZARD_TITLE = "#1A1F1D"  # Card titles, labels (14px, weight:600)
    WIZARD_SUBTITLE = "#86909B"  # Card subtitles (14px, weight:400)

    # Border & Divider Colors
    BORDER_DEFAULT = "#E1E8ED"  # Light border
    BORDER_FOCUS = "#00B2E3"  # Primary blue for focused inputs
    DIVIDER = "#ECF0F1"  # Very light gray for dividers

    # Status Colors
    SUCCESS = "#27AE60"  # Green for success
    WARNING = "#F39C12"  # Orange for warnings
    ERROR = "#E74C3C"  # Red for errors
    INFO = "#3498DB"  # Blue for info

    # Button States
    BUTTON_PRIMARY = "#00B2E3"
    BUTTON_PRIMARY_HOVER = "#0099C7"
    BUTTON_PRIMARY_PRESSED = "#0080AB"
    BUTTON_SECONDARY = "#ECF0F1"
    BUTTON_SECONDARY_HOVER = "#D5DBDB"
    BUTTON_DISABLED = "#BDC3C7"

    # Input Field States
    INPUT_BG = "#FFFFFF"
    INPUT_BORDER = "#E1E8ED"
    INPUT_BORDER_FOCUS = "#00B2E3"
    INPUT_BORDER_ERROR = "#E74C3C"
    INPUT_PLACEHOLDER = "#95A5A6"

    # Wizard Search Bar
    SEARCH_BAR_BG = "#F8FAFF"  # Search bar background
    SEARCH_BAR_BORDER = "#E5EAF6"  # Search bar border

    # Table Colors
    TABLE_HEADER_BG = "#F8F9FA"
    TABLE_ROW_ODD = "#FFFFFF"
    TABLE_ROW_EVEN = "#FAFBFC"
    TABLE_ROW_HOVER = "#F0F8FF"
    TABLE_ROW_SELECTED = "#E3F2FD"

    # Badge/Chip Colors
    BADGE_DRAFT = "#F39C12"  # Orange
    BADGE_FINALIZED = "#27AE60"  # Green
    BADGE_PENDING = "#3498DB"  # Blue
    BADGE_REJECTED = "#E74C3C"  # Red

    # Shadow Colors
    SHADOW_SM = "rgba(0, 0, 0, 0.05)"
    SHADOW_MD = "rgba(0, 0, 0, 0.1)"
    SHADOW_LG = "rgba(0, 0, 0, 0.15)"
    SHADOW_XL = "rgba(0, 0, 0, 0.2)"


class Typography:
    """Typography system."""

    # Font Families
    FONT_FAMILY_PRIMARY = "IBM Plex Sans Arabic"  # Main font for the entire application
    FONT_FAMILY_ARABIC = "IBM Plex Sans Arabic"   # Arabic text font (same as primary)
    FONT_FAMILY_LATIN = "Roboto"                  # Latin text font (for English text if needed)
    FONT_FAMILY_FALLBACK = "Calibri"              # System fallback only

    # Font Weights
    WEIGHT_LIGHT = 300
    WEIGHT_REGULAR = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_SEMIBOLD = 600  # SemiBold / DemiBold weight
    WEIGHT_BOLD = 700
    WEIGHT_BLACK = 900  # Extra Bold / Black weight

    # Font Sizes (in pixels)
    SIZE_CAPTION = 12  # Small text, captions
    SIZE_BODY = 14  # Default body text
    SIZE_SUBHEADING = 16  # Subheadings, section labels
    SIZE_H3 = 18  # Third-level headings
    SIZE_H2 = 20  # Second-level headings
    SIZE_H1 = 24  # Page titles
    SIZE_DISPLAY = 32  # Large display text

    # Line Heights (relative to font size)
    LINE_HEIGHT_TIGHT = 1.2
    LINE_HEIGHT_NORMAL = 1.5
    LINE_HEIGHT_LOOSE = 1.8

    @staticmethod
    def get_font(size=14, weight=400, family=None):
        """
        Get a QFont with specified properties

        Args:
            size: Font size in pixels
            weight: Font weight (300-700)
            family: Font family (None for default)
        """
        font = QFont()

        if family:
            font.setFamily(family)
        else:
            # Default font family based on system
            font.setFamily(Typography.FONT_FAMILY_ARABIC)
            font.setStyleHint(QFont.SansSerif)

        font.setPointSize(size)

        # Map weight to QFont weight
        if weight >= 700:
            font.setWeight(QFont.Bold)
        elif weight >= 600:
            font.setWeight(QFont.DemiBold)
        elif weight >= 500:
            font.setWeight(QFont.Medium)
        elif weight >= 300:
            font.setWeight(QFont.Light)
        else:
            font.setWeight(QFont.Normal)

        return font

    @staticmethod
    def get_heading_font(level=1):
        """Get font for heading levels H1-H3"""
        sizes = {
            1: Typography.SIZE_H1,
            2: Typography.SIZE_H2,
            3: Typography.SIZE_H3
        }
        return Typography.get_font(
            size=sizes.get(level, Typography.SIZE_H1),
            weight=Typography.WEIGHT_BOLD
        )

    @staticmethod
    def get_body_font(bold=False):
        """Get font for body text"""
        weight = Typography.WEIGHT_BOLD if bold else Typography.WEIGHT_REGULAR
        return Typography.get_font(size=Typography.SIZE_BODY, weight=weight)


class Spacing:
    """Spacing system based on 8px grid."""
    XS = 4   # Extra small spacing
    SM = 8   # Small spacing
    MD = 16  # Medium spacing (base unit)
    LG = 24  # Large spacing
    XL = 32  # Extra large spacing
    XXL = 48 # Double extra large spacing

    # Component-specific spacing
    CARD_PADDING = MD  # 16px padding inside cards
    SECTION_MARGIN = LG  # 24px margin between sections
    PAGE_MARGIN = XL  # 32px page margins

    # Form spacing
    FORM_FIELD_SPACING = MD  # Space between form fields
    FORM_GROUP_SPACING = LG  # Space between form groups
    LABEL_SPACING = XS  # Space between label and input

    # Button spacing
    BUTTON_PADDING_H = MD  # Horizontal padding in buttons
    BUTTON_PADDING_V = SM  # Vertical padding in buttons
    BUTTON_SPACING = SM  # Space between adjacent buttons

    # Navbar spacing
    NAVBAR_HORIZONTAL_PADDING = LG  # 24px horizontal padding in navbar
    NAVBAR_TOP_HEIGHT = 52  # Top bar height (updated for 56px tabs)
    NAVBAR_TABS_HEIGHT = 56  # Tabs bar height
    NAVBAR_TOTAL_HEIGHT = 109  # Total navbar height (52 + 56 + 1)

    # ID Badge spacing
    ID_BADGE_PADDING_V = 8  # Vertical padding in ID badge
    ID_BADGE_PADDING_H = 8  # Horizontal padding in ID badge
    ID_BADGE_GAP = 8  # Gap between ID badge elements
    ID_BADGE_RADIUS = 10  # Border radius for ID badge


class BorderRadius:
    """Border radius values for components"""
    NONE = 0
    SM = 4   # Small radius (inputs, badges)
    MD = 8   # Medium radius (buttons, cards)
    LG = 12  # Large radius (modals, dialogs)
    FULL = 9999  # Full circle/pill shape


class Shadows:
    """Box shadow definitions."""
    NONE = "none"
    SM = f"0 1px 2px 0 {Colors.SHADOW_SM}"
    MD = f"0 4px 6px -1px {Colors.SHADOW_MD}"
    LG = f"0 10px 15px -3px {Colors.SHADOW_LG}"
    XL = f"0 20px 25px -5px {Colors.SHADOW_XL}"

    # Component-specific shadows
    CARD = MD
    DROPDOWN = LG
    MODAL = XL
    BUTTON = SM


class Icons:
    """Icon specifications"""
    SIZE_SM = 16
    SIZE_MD = 24
    SIZE_LG = 32
    SIZE_XL = 48


class NavbarDimensions:
    """Navbar dimension constants."""
    # Container dimensions
    CONTAINER_WIDTH = 1512
    CONTAINER_HEIGHT = 109

    # Top bar dimensions
    TOP_BAR_HEIGHT = 60

    # Logo dimensions
    LOGO_WIDTH = 142.77
    LOGO_HEIGHT = 21.77
    LOGO_SCALED_HEIGHT = 22

    # ID Badge dimensions
    ID_BADGE_WIDTH = 110.69
    ID_BADGE_HEIGHT = 40
    ID_BADGE_BORDER_RADIUS = 10
    ID_BADGE_PADDING_V = 8
    ID_BADGE_PADDING_H = 8
    ID_BADGE_GAP = 8

    # Tabs bar dimensions
    TABS_BAR_HEIGHT = 48
    TAB_HEIGHT = 32
    TAB_PADDING_H = 12
    TAB_PADDING_V = 5
    TAB_GAP = 24
    TAB_BORDER_RADIUS = 8
    TAB_FONT_SIZE = 11
    TAB_FONT_WEIGHT = Typography.WEIGHT_SEMIBOLD
    TAB_LINE_HEIGHT = 22

    # Search bar dimensions
    SEARCH_BAR_WIDTH = 450
    SEARCH_BAR_HEIGHT = 32


class PageDimensions:
    """Page layout dimension constants."""
    # Content container dimensions
    CONTENT_WIDTH = 1249
    CONTENT_HEIGHT = 830

    # Page positioning
    CONTENT_POSITION_X = 131
    CONTENT_POSITION_Y = 141

    # Content padding (static fallbacks)
    CONTENT_PADDING_H = 131
    CONTENT_PADDING_V_TOP = 32
    CONTENT_PADDING_V_BOTTOM = 0

    @classmethod
    def content_padding_h(cls):
        """Dynamic horizontal padding — scales on small screens."""
        return ScreenScale.w(131)

    @classmethod
    def content_padding_v_top(cls):
        """Dynamic vertical top padding."""
        return ScreenScale.h(32)

    # Spacing and gaps
    CARD_GAP_VERTICAL = 16
    CARD_GAP_HORIZONTAL = 16
    HEADER_GAP = 30

    # Header dimensions
    PAGE_HEADER_HEIGHT = 48

    # Card dimensions
    CARD_HEIGHT = 112
    CARD_WIDTH = 616
    CARD_COLUMNS = 2

    # Card styling
    CARD_PADDING = 12
    CARD_BORDER_RADIUS = 8
    CARD_GAP_INTERNAL = 12

    # Card shadow
    CARD_SHADOW_X = 0
    CARD_SHADOW_Y = 4
    CARD_SHADOW_BLUR = 8
    CARD_SHADOW_SPREAD = 0
    CARD_SHADOW_COLOR = "#919EAB"
    CARD_SHADOW_OPACITY = 16

    # Card details container
    CARD_DETAILS_HEIGHT = 28
    CARD_DETAILS_PADDING_H = 8
    CARD_DETAILS_PADDING_V = 6
    CARD_DETAILS_GAP = 8
    CARD_DETAILS_RADIUS = 32
    CARD_DETAILS_BG = "#F8FAFF"
    CARD_DETAILS_BORDER = "#E5EAF6"
    CARD_DETAILS_BORDER_WIDTH = 1

    # Card details text styling
    CARD_DETAILS_TEXT_COLOR = "#667281"
    CARD_DETAILS_TEXT_SIZE = 6
    CARD_DETAILS_TEXT_WEIGHT = Typography.WEIGHT_LIGHT
    CARD_DETAILS_TEXT_LETTER_SPACING = 0


class WizardDimensions:
    """Wizard-specific dimension constants."""
    # Header dimensions
    HEADER_HEIGHT = 48
    HEADER_TITLE_FONT_SIZE = 18

    # Save button
    SAVE_BTN_WIDTH = 114
    SAVE_BTN_HEIGHT = 48
    SAVE_BTN_PADDING_H = 24
    SAVE_BTN_PADDING_V = 12
    SAVE_BTN_RADIUS = 8

    # Close button
    CLOSE_BTN_WIDTH = 52
    CLOSE_BTN_HEIGHT = 48
    CLOSE_BTN_PADDING_H = 20
    CLOSE_BTN_PADDING_V = 12
    CLOSE_BTN_RADIUS = 8

    # Spacing
    BUTTONS_GAP = 16
    HEADER_TO_TABS_GAP = 30
    TABS_TO_CONTENT_GAP = 16

    # Tabs bar dimensions
    TABS_BAR_HEIGHT = 66
    TABS_GAP = 8


class ButtonDimensions:
    """Button dimension constants."""
    # Primary Button
    PRIMARY_WIDTH = 199
    PRIMARY_HEIGHT = 48
    PRIMARY_BORDER_RADIUS = 8
    PRIMARY_PADDING_H = 24
    PRIMARY_PADDING_V = 12
    PRIMARY_FONT_SIZE = 10

    # Primary Button Colors
    PRIMARY_HOVER_BG = "#2A7BC9"
    PRIMARY_PRESSED_BG = "#1F68B3"
    PRIMARY_DISABLED_BG = "#BDC3C7"
    PRIMARY_DISABLED_TEXT = "#7F8C9B"

    # Save Button
    SAVE_WIDTH = 114
    SAVE_HEIGHT = 48
    SAVE_BORDER_RADIUS = 8
    SAVE_PADDING_H = 24
    SAVE_PADDING_V = 12
    SAVE_FONT_SIZE = 12
    SAVE_ICON_SIZE = 14
    SAVE_ICON_SPACING = 10

    # Close Button
    CLOSE_WIDTH = 52
    CLOSE_HEIGHT = 48
    CLOSE_BORDER_RADIUS = 8
    CLOSE_PADDING_H = 16
    CLOSE_PADDING_V = 12
    CLOSE_FONT_SIZE = 12

    # Step Tab/Indicator
    STEP_TAB_WIDTH = 111
    STEP_TAB_HEIGHT = 35
    STEP_TAB_BORDER_RADIUS = 14
    STEP_TAB_PADDING_H = 16
    STEP_TAB_PADDING_V = 10
    STEP_TAB_GAP = 20
    STEP_TAB_FONT_SIZE = 9

    # Footer Card
    FOOTER_WIDTH = 1512
    FOOTER_HEIGHT = 74
    FOOTER_PADDING_H = 130
    FOOTER_PADDING_V = 12

    # Footer Navigation Buttons
    NAV_BUTTON_WIDTH = 252
    NAV_BUTTON_HEIGHT = 50
    NAV_BUTTON_GAP = 748
    NAV_BUTTON_BORDER_RADIUS = 8
    NAV_BUTTON_FONT_SIZE = 12

    # Dialog Dimensions
    DIALOG_WIDTH = 400
    DIALOG_MIN_HEIGHT = 294
    DIALOG_BORDER_RADIUS = 12
    DIALOG_PADDING = 24

    # Dialog Icon
    DIALOG_ICON_SIZE = 48
    DIALOG_ICON_BORDER_RADIUS = 24

    # Dialog Buttons
    DIALOG_BUTTON_HEIGHT = 48
    DIALOG_BUTTON_MIN_WIDTH = 120
    DIALOG_BUTTON_GAP = 16
    DIALOG_BUTTON_BORDER_RADIUS = 8
    DIALOG_BUTTON_FONT_SIZE = 10

    # Dialog Spacing
    DIALOG_TITLE_GAP = 16
    DIALOG_MESSAGE_GAP = 8
    DIALOG_BUTTON_TOP_GAP = 24


class DialogColors:
    """Dialog type-specific colors."""

    # Icon Background Colors (light backgrounds for icons)
    WARNING_BG = "#FFF4E5"                 # Warning icon background (light orange)
    ERROR_BG = "#FFE7E7"                   # Error icon background (light red)
    SUCCESS_BG = "#E7F7EF"                 # Success icon background (light green)
    INFO_BG = "#E3F2FD"                    # Info icon background (light blue)

    # Icon Colors (main colors)
    WARNING_ICON = "#FFC72C"               # Warning icon color (yellow)
    ERROR_ICON = "#E53935"                 # Error icon color (red)
    SUCCESS_ICON = "#43A047"               # Success icon color (green)
    INFO_ICON = "#1E88E5"                  # Info icon color (blue)

    # Button Colors
    WARNING_BUTTON_BG = "#FFC72C"          # Warning button background (yellow)
    WARNING_BUTTON_HOVER = "#FFD454"       # Warning button hover (lighter yellow)

    # Overlay
    OVERLAY_BG = "rgba(45, 45, 45, 0.95)"  # Very dark gray overlay (95% opacity)


class ComponentStyles:
    """Pre-defined QSS component styles."""

    @staticmethod
    def get_button_style(variant="primary", size="medium"):
        """
        Get button stylesheet

        Args:
            variant: primary, secondary, text, danger
            size: small, medium, large
        """
        # Size mappings
        size_map = {
            "small": (f"{Spacing.SM}px {Spacing.MD}px", Typography.SIZE_CAPTION),
            "medium": (f"{Spacing.SM}px {Spacing.BUTTON_PADDING_H}px", Typography.SIZE_BODY),
            "large": (f"{Spacing.MD}px {Spacing.LG}px", Typography.SIZE_SUBHEADING)
        }

        padding, font_size = size_map.get(size, size_map["medium"])

        # Variant styles
        if variant == "primary":
            return f"""
                QPushButton {{
                    background-color: {Colors.BUTTON_PRIMARY};
                    color: {Colors.TEXT_ON_PRIMARY};
                    border: none;
                    border-radius: {BorderRadius.MD}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: {Typography.WEIGHT_MEDIUM};
                }}
                QPushButton:hover {{
                    background-color: {Colors.BUTTON_PRIMARY_HOVER};
                }}
                QPushButton:pressed {{
                    background-color: {Colors.BUTTON_PRIMARY_PRESSED};
                }}
                QPushButton:disabled {{
                    background-color: {Colors.BUTTON_DISABLED};
                    color: {Colors.TEXT_DISABLED};
                }}
            """
        elif variant == "secondary":
            return f"""
                QPushButton {{
                    background-color: {Colors.BUTTON_SECONDARY};
                    color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: {BorderRadius.MD}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: {Typography.WEIGHT_MEDIUM};
                }}
                QPushButton:hover {{
                    background-color: {Colors.BUTTON_SECONDARY_HOVER};
                    border-color: {Colors.PRIMARY_BLUE};
                }}
                QPushButton:disabled {{
                    background-color: {Colors.BUTTON_SECONDARY};
                    color: {Colors.TEXT_DISABLED};
                    border-color: {Colors.BORDER_DEFAULT};
                }}
            """
        elif variant == "danger":
            return f"""
                QPushButton {{
                    background-color: {Colors.ERROR};
                    color: {Colors.PRIMARY_WHITE};
                    border: none;
                    border-radius: {BorderRadius.MD}px;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: {Typography.WEIGHT_MEDIUM};
                }}
                QPushButton:hover {{
                    background-color: #C0392B;
                }}
                QPushButton:disabled {{
                    background-color: {Colors.BUTTON_DISABLED};
                    color: {Colors.TEXT_DISABLED};
                }}
            """
        else:  # text variant
            return f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.PRIMARY_BLUE};
                    border: none;
                    padding: {padding};
                    font-size: {font_size}px;
                    font-weight: {Typography.WEIGHT_MEDIUM};
                }}
                QPushButton:hover {{
                    background-color: rgba(0, 178, 227, 0.1);
                }}
                QPushButton:disabled {{
                    color: {Colors.TEXT_DISABLED};
                }}
            """

    @staticmethod
    def get_input_style():
        """Get input field stylesheet"""
        return f"""
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.INPUT_BORDER};
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                font-size: {Typography.SIZE_BODY}px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border-color: {Colors.INPUT_BORDER_FOCUS};
                outline: none;
            }}
            QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
                background-color: {Colors.BUTTON_SECONDARY};
                color: {Colors.TEXT_DISABLED};
                border-color: {Colors.BORDER_DEFAULT};
            }}
            QLineEdit::placeholder, QTextEdit::placeholder {{
                color: {Colors.INPUT_PLACEHOLDER};
            }}
        """

    @staticmethod
    def get_card_style():
        """Get card container stylesheet"""
        return f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD}px;
                padding: {Spacing.CARD_PADDING}px;
            }}
        """

    @staticmethod
    def get_table_style():
        """Get table/list stylesheet"""
        return f"""
            QTableWidget, QTableView {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.MD}px;
                gridline-color: {Colors.DIVIDER};
            }}
            QTableWidget::item, QTableView::item {{
                padding: {Spacing.SM}px {Spacing.MD}px;
                border: none;
            }}
            QTableWidget::item:hover, QTableView::item:hover {{
                background-color: {Colors.TABLE_ROW_HOVER};
            }}
            QTableWidget::item:selected, QTableView::item:selected {{
                background-color: {Colors.TABLE_ROW_SELECTED};
                color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Colors.TABLE_HEADER_BG};
                color: {Colors.TEXT_PRIMARY};
                padding: {Spacing.SM}px {Spacing.MD}px;
                border: none;
                border-bottom: 2px solid {Colors.BORDER_DEFAULT};
                font-weight: {Typography.WEIGHT_BOLD};
            }}
        """

    @staticmethod
    def get_dialog_style():
        """Get modal/dialog stylesheet"""
        return f"""
            QDialog {{
                background-color: {Colors.SURFACE};
                border-radius: {BorderRadius.LG}px;
            }}
        """

    @staticmethod
    def get_navbar_style():
        """Get top navigation bar stylesheet."""
        return f"""
            QFrame#navbar {{
                background-color: {Colors.NAVBAR_BG};
                border: none;
                border-bottom: 2px solid {Colors.NAVBAR_BORDER};
                padding: {Spacing.MD}px {Spacing.LG}px;
                min-height: 60px;
            }}
            QLabel#logo {{
                color: {Colors.TEXT_ON_DARK};
                font-size: {Typography.SIZE_H3}px;
                font-weight: {Typography.WEIGHT_BOLD};
            }}
            QLabel#user_id {{
                color: {Colors.TEXT_ON_DARK};
                font-size: {Typography.SIZE_BODY}px;
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: {BorderRadius.FULL}px;
                padding: {Spacing.XS}px {Spacing.MD}px;
            }}
        """

    @staticmethod
    def get_tab_bar_style():
        """Get tab navigation stylesheet."""
        return f"""
            QTabBar {{
                background-color: transparent;
                border: none;
            }}
            QTabBar::tab {{
                background-color: transparent;
                color: rgba(255, 255, 255, 0.7);
                padding: {Spacing.MD}px {Spacing.LG}px;
                border: none;
                border-bottom: 3px solid transparent;
                font-size: {Typography.SIZE_BODY}px;
                font-weight: {Typography.WEIGHT_REGULAR};
                min-width: 120px;
            }}
            QTabBar::tab:hover {{
                background-color: {Colors.NAVBAR_BG_HOVER};
                color: {Colors.PRIMARY_WHITE};
            }}
            QTabBar::tab:selected {{
                color: {Colors.PRIMARY_WHITE};
                font-weight: {Typography.WEIGHT_BOLD};
                border-bottom: 3px solid {Colors.PRIMARY_BLUE};
                background-color: transparent;
            }}
            QTabWidget::pane {{
                border: none;
                background-color: {Colors.BACKGROUND};
            }}
        """

    @staticmethod
    def get_search_bar_style():
        """Get search bar stylesheet."""
        return f"""
            QLineEdit#search_bar {{
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: {BorderRadius.FULL}px;
                padding: {Spacing.SM}px {Spacing.LG}px;
                padding-right: {Spacing.XL}px;
                color: {Colors.TEXT_ON_DARK};
                font-size: {Typography.SIZE_BODY}px;
            }}
            QLineEdit#search_bar:focus {{
                border-color: {Colors.PRIMARY_BLUE};
                background-color: rgba(255, 255, 255, 0.15);
            }}
            QLineEdit#search_bar::placeholder {{
                color: rgba(255, 255, 255, 0.5);
            }}
        """


class DesignTokens:
    """
    Complete design tokens bundle
    Use this class to access all design system values
    """
    colors = Colors
    typography = Typography
    spacing = Spacing
    radius = BorderRadius
    shadows = Shadows
    icons = Icons
    navbar = NavbarDimensions
    page = PageDimensions
    components = ComponentStyles
