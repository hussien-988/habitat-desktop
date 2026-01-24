"""
UN-Habitat TRRCMS Design System
Based on Figma Design (Desktop Version) + Brand Manual

This module contains all design tokens, colors, typography, spacing,
and component specifications extracted from the official design files.
"""

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtCore import Qt


class Colors:
    """
    Color palette extracted from UN-Habitat Brand Manual and Figma Design
    """
    # Primary Colors (from Figma PDF - extracted from pages 1-31)
    PRIMARY_BLUE = "#3890DF"  # UN-Habitat primary blue (updated from Figma)
    PRIMARY_BLUE_LIGHT = "#00B2E3"  # Light blue accent (original UN-Habitat)
    PRIMARY_BLACK = "#000000"
    PRIMARY_WHITE = "#FFFFFF"

    # UI Colors (from Figma Design - Pages 1-31)
    BACKGROUND = "#f0f7ff"  # Light gray background (main app background)
    BACKGROUND_LIGHT = "#F0F4F8"  # Very light blue-gray (login page)
    SURFACE = "#FFFFFF"  # White surface/cards
    LIGHT_GRAY_BG = "#FAFBFC"  # Very light gray for alternating rows

    # Navbar colors (from Figma pages 1, 3-5, 26-31) - UPDATED
    NAVBAR_BG = "#122C49"  # Dark navy blue navbar background (exact from Figma)
    NAVBAR_BG_HOVER = "#1A3A5C"  # Slightly lighter on hover
    NAVBAR_BORDER = "#0F2338"  # Darker border below navbar
    NAVBAR_TAB_ACTIVE = "#9BC2FF"  # Active tab indicator color

    # Search bar background (from Figma pages 1-5, 26-27)
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

    # Wizard-specific text colors (from Figma)
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

    # Wizard Search Bar (from Figma)
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
    """
    Typography system based on Brand Manual requirements
    Primary Arabic Font: IBM Plex Sans Arabic (main font for the application)
    Primary Latin Font: Roboto
    System Fallback: Calibri

    Note: Noto Kufi Arabic removed - IBM Plex Sans Arabic is now the only Arabic font
    """

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

        font.setPixelSize(size)

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
    """
    Spacing system for consistent layout
    Based on 8px grid system
    """
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

    # Navbar spacing (from Figma specs)
    NAVBAR_HORIZONTAL_PADDING = LG  # 24px horizontal padding in navbar
    NAVBAR_TOP_HEIGHT = 52  # Top bar height (updated for 56px tabs)
    NAVBAR_TABS_HEIGHT = 56  # Tabs bar height (Figma: 56 Hug)
    NAVBAR_TOTAL_HEIGHT = 109  # Total navbar height (52 + 56 + 1)

    # ID Badge spacing (from Figma specs)
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
    """
    Box shadow definitions
    Format: offset-x, offset-y, blur-radius, spread-radius, color
    """
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
    """
    Navbar dimensions from Figma specifications
    Exact measurements for navbar components
    """
    # Container dimensions
    CONTAINER_WIDTH = 1512  # Total navbar width from Figma
    CONTAINER_HEIGHT = 109  # Total navbar height from Figma (60 + 48 + 1)

    # Top bar dimensions
    TOP_BAR_HEIGHT = 60  # Top bar section height (Figma: 60px)

    # Logo dimensions (from Figma: 142.77×21.77)
    LOGO_WIDTH = 142.77
    LOGO_HEIGHT = 21.77
    # Scaled for PyQt5 visual balance
    LOGO_SCALED_HEIGHT = 22  # Rounded for PyQt5

    # ID Badge dimensions (from Figma: 110.69×40)
    ID_BADGE_WIDTH = 110.69
    ID_BADGE_HEIGHT = 40
    ID_BADGE_BORDER_RADIUS = 10  # From Figma
    ID_BADGE_PADDING_V = 8  # Vertical padding
    ID_BADGE_PADDING_H = 8  # Horizontal padding
    ID_BADGE_GAP = 8  # Gap between elements

    # Tabs bar dimensions (من Figma)
    TABS_BAR_HEIGHT = 48  # Tabs section height (Figma: 48px)
    TAB_HEIGHT = 32  # Individual tab height (Figma: 32px Hug)
    TAB_PADDING_H = 12  # Horizontal padding in each tab (Figma: calculated from layout)
    TAB_PADDING_V = 5  # Vertical padding in each tab (for 22px line-height)
    TAB_GAP = 24  # Gap between tabs (Figma: 24px)
    TAB_BORDER_RADIUS = 8  # Border radius for active tab (Figma: 8px)
    TAB_FONT_SIZE = 11  # Tab text font size (Figma: 14px × 0.75 = 10.5pt ≈ 11pt)
    TAB_FONT_WEIGHT = Typography.WEIGHT_SEMIBOLD  # SemiBold (600)
    TAB_LINE_HEIGHT = 22  # Line height from Figma (22px)

    # Search bar dimensions
    SEARCH_BAR_WIDTH = 450
    SEARCH_BAR_HEIGHT = 32


class PageDimensions:
    """
    Page layout dimensions from Figma specifications
    For content areas and common page elements

    Calculations:
    - Window: 1512×982px
    - Navbar: 109px
    - Available: 1512×873px
    - Content: 1249×830px (from Figma)
    - Horizontal padding: (1512-1249)/2 = 131.5px each side
    - Vertical remaining: 873-830 = 43px (for header + bottom margin)
    """
    # Content container dimensions (from Figma: Completed Claims Page)
    CONTENT_WIDTH = 1249  # Content area width (Figma: 1249 Hug)
    CONTENT_HEIGHT = 830  # Content area height (Figma: 830 Hug)

    # Page positioning (from Figma - exact position values)
    CONTENT_POSITION_X = 131  # X position from left (Figma: 131px)
    CONTENT_POSITION_Y = 141  # Y position from top of window (Figma: 141px)

    # Calculated padding (for PyQt5 layout)
    CONTENT_PADDING_H = 131  # Horizontal: 131px each side (Figma exact value)
    CONTENT_PADDING_V_TOP = 32  # Top: gap between navbar and content (Figma: 32px)
    CONTENT_PADDING_V_BOTTOM = 0  # Bottom: no padding

    # Spacing and gaps
    CARD_GAP_VERTICAL = 16    # Gap between card rows (Figma: 16px)
    CARD_GAP_HORIZONTAL = 16  # Gap between card columns (Figma: 16px)
    HEADER_GAP = 30           # Gap between header and first card (Figma: 30px)

    # Header dimensions
    PAGE_HEADER_HEIGHT = 48  # Page header height with button and title (Figma: 48px)

    # Card dimensions
    CARD_HEIGHT = 112           # Individual card height (Figma: 112px Hug)
    CARD_WIDTH = 616            # Individual card width (Figma: 616.5px Fill, rounded to 616)
    CARD_COLUMNS = 2            # Number of columns in grid (Figma shows 2-column layout)

    # Card styling (from Figma)
    CARD_PADDING = 12           # Card internal padding (Figma: 12px all sides)
    CARD_BORDER_RADIUS = 8      # Card corner radius (Figma: 8px)
    CARD_GAP_INTERNAL = 12      # Gap between elements inside card (Figma: 12px)

    # Card shadow (from Figma Drop shadow)
    CARD_SHADOW_X = 0           # Shadow X offset (Figma: 0)
    CARD_SHADOW_Y = 4           # Shadow Y offset (Figma: 4)
    CARD_SHADOW_BLUR = 8        # Shadow blur radius (Figma: 8)
    CARD_SHADOW_SPREAD = 0      # Shadow spread (Figma: 0)
    CARD_SHADOW_COLOR = "#919EAB"  # Shadow color (Figma: #919EAB)
    CARD_SHADOW_OPACITY = 16    # Shadow opacity percentage (Figma: 16%)

    # Card details container (inner box in card - from Figma)
    CARD_DETAILS_HEIGHT = 28         # Details container height (Figma: 28px Hug)
    CARD_DETAILS_PADDING_H = 8       # Horizontal padding (Figma: 8px)
    CARD_DETAILS_PADDING_V = 6       # Vertical padding (Figma: 6px)
    CARD_DETAILS_GAP = 8             # Gap between elements (Figma: 8px)
    CARD_DETAILS_RADIUS = 32         # Corner radius (Figma: 32px - stored for reference)
                                      # Note: StyleManager uses 999px for perfect pill shape
                                      # CSS limits radius to height/2 when value exceeds it
    CARD_DETAILS_BG = "#F8FAFF"      # Background color (Figma: #F8FAFF)
    CARD_DETAILS_BORDER = "#E5EAF6"  # Border color (Figma: #E5EAF6)
    CARD_DETAILS_BORDER_WIDTH = 1    # Border width (Figma: 1px, Inside)

    # Card details text styling (text inside details container - from Figma)
    CARD_DETAILS_TEXT_COLOR = "#757575"                          # Text color (Figma: #757575)
    CARD_DETAILS_TEXT_SIZE = 6                                   # Font size (PyQt5: 6pt - adjusted for smaller display)
    # DRY: Use primary Arabic font (IBM Plex Sans Arabic) from Typography
    # Fallback: Calibri (system fallback only)
    CARD_DETAILS_TEXT_WEIGHT = Typography.WEIGHT_LIGHT           # Font weight: Light (300)
    CARD_DETAILS_TEXT_LETTER_SPACING = 0                         # Letter spacing (Figma: 0)


class WizardDimensions:
    """
    Wizard-specific dimensions from Figma specifications.

    Note: Wizard uses same page padding as claims pages (DRY principle).
    Reuses PageDimensions.CONTENT_PADDING_H, CONTENT_PADDING_V_TOP, etc.

    Figma Specs (Office Survey Wizard):
    - Header section: Title + Buttons (height: 48px)
    - Save button: 114×48px, padding 24×12, border-radius 8px
    - Close button: 52×48px, padding 20×12, border-radius 8px
    - Buttons gap: 16px
    - Tabs bar: 1249×66px (Fill × Hug), gap 8px
    - Spacing: Header→Tabs: 30px, Tabs→Content: 16px
    """
    # Header dimensions (from Figma images)
    HEADER_HEIGHT = 48                    # Header height (same as button height)
    HEADER_TITLE_FONT_SIZE = 18           # Title: 24px Figma = 18pt (×0.75)

    # Save button (from Figma: 114×48px)
    SAVE_BTN_WIDTH = 114                  # Width: 114px (Hug)
    SAVE_BTN_HEIGHT = 48                  # Height: 48px
    SAVE_BTN_PADDING_H = 24               # Horizontal padding: 24px
    SAVE_BTN_PADDING_V = 12               # Vertical padding: 12px
    SAVE_BTN_RADIUS = 8                   # Border-radius: 8px

    # Close button (from Figma: 52×48px)
    CLOSE_BTN_WIDTH = 52                  # Width: 52px (Hug)
    CLOSE_BTN_HEIGHT = 48                 # Height: 48px
    CLOSE_BTN_PADDING_H = 20              # Horizontal padding: 20px
    CLOSE_BTN_PADDING_V = 12              # Vertical padding: 12px
    CLOSE_BTN_RADIUS = 8                  # Border-radius: 8px

    # Spacing (from Figma)
    BUTTONS_GAP = 16                      # Gap between buttons (Figma: 16px)
    HEADER_TO_TABS_GAP = 30               # Gap from header to tabs (30px)
    TABS_TO_CONTENT_GAP = 16              # Gap from tabs to content (16px)

    # Tabs bar dimensions (from Figma)
    TABS_BAR_HEIGHT = 66                  # Tabs bar height (Figma: 66px Hug)
    TABS_GAP = 8                          # Gap between tab items (Figma: 8px)

    # DRY: Reuse page padding from PageDimensions
    # No need to duplicate - use PageDimensions.CONTENT_PADDING_H, etc.


class ButtonDimensions:
    """
    Button dimensions from Figma specifications (exact measurements).
    User provided exact specs: 199×48px, padding 24×12, font 16px, border-radius 8px.

    Font conversion: Figma uses pixels, PyQt5 QFont uses points.
    Formula: Points = Pixels × 0.75 (because 1pt = 1.333px)
    """
    # Primary Button (e.g., "إضافة حالة جديدة +")
    PRIMARY_WIDTH = 199                    # Button width (Figma: 199px - exact)
    PRIMARY_HEIGHT = 48                    # Button height (Figma: 48px - exact)
    PRIMARY_BORDER_RADIUS = 8              # Corner radius (Figma: 8px)
    PRIMARY_PADDING_H = 24                 # Horizontal padding (Figma: 24px - exact)
    PRIMARY_PADDING_V = 12                 # Vertical padding (Figma: 12px - exact)
    PRIMARY_FONT_SIZE = 10                 # Font size (Figma: 16px → PyQt5: 16×0.75=12pt)

    # Primary Button Colors (from Figma)
    PRIMARY_HOVER_BG = "#2A7BC9"           # Hover state (darker blue)
    PRIMARY_PRESSED_BG = "#1F68B3"         # Pressed state (even darker)
    PRIMARY_DISABLED_BG = "#BDC3C7"        # Disabled background
    PRIMARY_DISABLED_TEXT = "#7F8C9B"      # Disabled text color

    # Save Button (Wizard header - Figma specs)
    SAVE_WIDTH = 114                       # Button width (Figma: 114px)
    SAVE_HEIGHT = 48                       # Button height (Figma: 48px)
    SAVE_BORDER_RADIUS = 8                 # Corner radius (Figma: 8px)
    SAVE_PADDING_H = 24                    # Horizontal padding (Figma: 24px)
    SAVE_PADDING_V = 12                    # Vertical padding (Figma: 12px)
    SAVE_FONT_SIZE = 12                    # Font size (Figma: 16px → PyQt5: 16×0.75=12pt)
    SAVE_ICON_SIZE = 14                    # Icon size (14×14px)
    SAVE_ICON_SPACING = 10                 # Spacing between icon and text (Figma: 10px)

    # Close Button (Wizard header - Figma specs)
    CLOSE_WIDTH = 52                       # Button width (Figma: 52px)
    CLOSE_HEIGHT = 48                      # Button height (Figma: 48px)
    CLOSE_BORDER_RADIUS = 8                # Corner radius (Figma: 8px)
    CLOSE_PADDING_H = 16                   # Horizontal padding (Figma: 16px)
    CLOSE_PADDING_V = 12                   # Vertical padding (Figma: 12px)
    CLOSE_FONT_SIZE = 12                   # Font size (Figma: 16px → PyQt5: 16×0.75=12pt)

    # Step Tab/Indicator (Wizard tabs bar - Figma specs)
    STEP_TAB_WIDTH = 111                   # Tab width (Figma: 111px)
    STEP_TAB_HEIGHT = 35                   # Tab height (Figma: 35px)
    STEP_TAB_BORDER_RADIUS = 14            # Border-radius (same as pill: 14px)
    STEP_TAB_PADDING_H = 16                # Horizontal padding (Figma: 16px - يمين/يسار)
    STEP_TAB_PADDING_V = 10                # Vertical padding (Figma: 10px - فوق/تحت)
    STEP_TAB_GAP = 20                      # Gap between tabs (Figma: 20px)
    STEP_TAB_FONT_SIZE = 9                 # Font size (9pt)

    # Footer Card (Wizard footer - Figma specs)
    FOOTER_WIDTH = 1512                    # Footer width (Figma: 1512px)
    FOOTER_HEIGHT = 74                     # Footer height (Figma: 74px)
    FOOTER_PADDING_H = 130                 # Horizontal internal padding (Figma: 130px - يمين/يسار)
    FOOTER_PADDING_V = 12                  # Vertical internal padding (Figma: 12px - فوق/تحت)

    # Footer Navigation Buttons (Figma specs)
    NAV_BUTTON_WIDTH = 252                 # Navigation button width (Figma: 252px)
    NAV_BUTTON_HEIGHT = 50                 # Navigation button height (Figma: 50px)
    NAV_BUTTON_GAP = 748                   # Gap between navigation buttons (Figma: 1512-130*2-252*2 = 748px)
    NAV_BUTTON_BORDER_RADIUS = 8           # Border radius for navigation buttons (Figma: 8px)
    NAV_BUTTON_FONT_SIZE = 12              # Font size for navigation buttons (Figma: 16px → 12pt Qt)

    # Dialog Dimensions (Figma specs)
    DIALOG_WIDTH = 400                     # Dialog width (Figma screenshot: 400px)
    DIALOG_MIN_HEIGHT = 294                # Dialog minimum height (Figma screenshot: 294px)
    DIALOG_BORDER_RADIUS = 12              # Dialog border-radius (Figma: 12px)
    DIALOG_PADDING = 24                    # Dialog internal padding (Figma: 24px)

    # Dialog Icon
    DIALOG_ICON_SIZE = 48                  # Icon size (Figma: 48px)
    DIALOG_ICON_BORDER_RADIUS = 24         # Icon container border-radius (circular: 48/2 = 24px)

    # Dialog Buttons
    DIALOG_BUTTON_HEIGHT = 48              # Button height (Figma: 48px)
    DIALOG_BUTTON_MIN_WIDTH = 120          # Button minimum width (Figma: 120px)
    DIALOG_BUTTON_GAP = 16                 # Gap between buttons (Figma: 16px)
    DIALOG_BUTTON_BORDER_RADIUS = 8        # Button border-radius (Figma: 8px)
    DIALOG_BUTTON_FONT_SIZE = 10           # Button font size (Figma: 14px → 10pt Qt)

    # Dialog Spacing (from Figma screenshot)
    DIALOG_TITLE_GAP = 16                  # Gap between icon and title (Figma: 16px)
    DIALOG_MESSAGE_GAP = 8                 # Gap between title and details (Figma: 8px)
    DIALOG_BUTTON_TOP_GAP = 24             # Gap between message and buttons (Figma: 24px)


class DialogColors:
    """
    Dialog type-specific colors
    Based on Figma design specifications
    """

    # Icon Background Colors (light backgrounds for icons)
    WARNING_BG = "#FFF4E5"                 # Warning icon background (light orange)
    ERROR_BG = "#FFE7E7"                   # Error icon background (light red)
    SUCCESS_BG = "#E7F7EF"                 # Success icon background (light green)
    INFO_BG = "#E3F2FD"                    # Info icon background (light blue)

    # Icon Colors (main colors)
    WARNING_ICON = "#FFC72C"               # Warning icon color (yellow from Figma)
    ERROR_ICON = "#E53935"                 # Error icon color (red)
    SUCCESS_ICON = "#43A047"               # Success icon color (green)
    INFO_ICON = "#1E88E5"                  # Info icon color (blue)

    # Button Colors
    WARNING_BUTTON_BG = "#FFC72C"          # Warning button background (yellow)
    WARNING_BUTTON_HOVER = "#FFD454"       # Warning button hover (lighter yellow)

    # Overlay
    OVERLAY_BG = "rgba(45, 45, 45, 0.95)"  # Very dark gray overlay (95% opacity)


class ComponentStyles:
    """
    Pre-defined component style strings for QSS
    Based on Figma design specifications
    """

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
        """Get top navigation bar stylesheet (from Figma pages 1-5) - CORRECTED"""
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
        """Get tab navigation stylesheet (from Figma pages 3-5) - CORRECTED"""
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
        """Get search bar stylesheet (from Figma pages 1-5)"""
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
