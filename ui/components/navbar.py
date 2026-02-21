# -*- coding: utf-8 -*-
"""
Navbar Component - UN-HABITAT TRRCMS
المكون المشترك للشريط العلوي مع التبويبات

Exact Figma Specifications (المطالبات المكتملة page):
- Container: W=1512, H=109
- Top Bar: H=60
- Tabs Bar: H=48
- Logo: 142.77×21.77 (scaled to 22px height for PyQt5)
- ID Badge: 110.69×40, border-radius=10px, padding=8px
- Background: #122C49 (NAVBAR_BG)
- Font: IBM Plex Sans Arabic, Letter spacing: 0px

Architecture:
- DRY: Reusable components (LogoWidget, IDBadgeWidget)
- SOLID: Single responsibility, dependency injection
- Clean Code: Clear naming, proper separation of concerns
"""

from pathlib import Path
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QWidget, QPushButton,
    QVBoxLayout, QSpacerItem, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QFont, QCursor, QIcon

from ..design_system import Colors, NavbarDimensions, Typography, Spacing
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from .logo import LogoWidget
from .id_badge import IDBadgeWidget
from services.translation_manager import tr


class DraggableFrame(QFrame):
    """
    Draggable frame for window movement
    فريم قابل للسحب لتحريك النافذة

    Allows dragging the window when frameless
    Double-click to maximize/restore
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
            if not self.window().isMaximized():
                self.window().move(event.globalPos() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self.window()
            if w.isMaximized():
                w.showNormal()
            else:
                w.showMaximized()
            event.accept()
        super().mouseDoubleClickEvent(event)


class Navbar(QFrame):
    """
    Main Navbar Component with Tabs
    المكون الرئيسي للشريط العلوي مع التبويبات

    Figma Specifications:
    - Total Height: 109px (60px top + 48px tabs + 1px adjustment)
    - Background: #122C49
    - Logo: Reusable LogoWidget
    - ID Badge: Reusable IDBadgeWidget
    - Search Bar: 450×32px
    - Tabs: المطالبات المكتملة (active), المسودة, المباني, الوحدات السكنية, التكرارات, استيراد

    Signals:
        tab_changed(int): Emitted when tab is changed
        search_requested(str): Emitted when search is performed
    """

    # Signals
    tab_changed = pyqtSignal(int)
    search_requested = pyqtSignal(str)
    logout_requested = pyqtSignal()
    language_change_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    password_change_requested = pyqtSignal()
    security_settings_requested = pyqtSignal()
    data_management_requested = pyqtSignal()

    def __init__(self, user_id=None, parent=None):
        super().__init__(parent)

        self.user_id = user_id or "12345"
        self.setObjectName("navbar")
        self.current_tab_index = 0
        self.tab_buttons = []
        self.search_mode = "name"  # Default search mode

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup navbar UI structure"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar - 60px height
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        # Tabs bar - 48px height
        tabs_bar = self._create_tabs_bar()
        main_layout.addWidget(tabs_bar)

        # Figma: Total height 109px
        self.setFixedHeight(NavbarDimensions.CONTAINER_HEIGHT)

    def _create_top_bar(self):
        """
        Create top bar with logo, ID badge, search, and window controls

        Figma: H=60px, Padding=24px horizontal
        Layout (RTL): [Window Controls] [Spacer] [Search] [Spacer] [ID Badge] [Logo]
        """
        top_bar = DraggableFrame()
        top_bar.setObjectName("navbar_top")
        top_bar.setAttribute(Qt.WA_StyledBackground, True)
        top_bar.setFixedHeight(NavbarDimensions.TOP_BAR_HEIGHT)
        # Keep top bar position fixed regardless of language direction
        top_bar.setLayoutDirection(Qt.RightToLeft)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(
            Spacing.NAVBAR_HORIZONTAL_PADDING, 10,  # Left: 24px, Top: 10px (52-32)/2
            0, 10  # Right: 0px (logo flush to edge), Bottom: 10px
        )
        layout.setSpacing(16)

        # Window controls (minimize, maximize, close) - leftmost
        win_controls = self._create_window_controls()
        layout.addWidget(win_controls)

        # Spacer before search
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Search bar (centered)
        self.search_bar = self._create_search_bar()
        layout.addWidget(self.search_bar)

        # Spacer after search
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # ID Badge - Reusable dropdown component
        self.id_badge = IDBadgeWidget(user_id=self.user_id)
        self.id_badge.logout_requested.connect(self._on_logout_requested)
        self.id_badge.language_change_requested.connect(self._on_language_change_requested)
        self.id_badge.sync_requested.connect(self._on_sync_requested)
        self.id_badge.password_change_requested.connect(self._on_password_change_requested)
        self.id_badge.security_settings_requested.connect(self._on_security_settings_requested)
        self.id_badge.data_management_requested.connect(self._on_data_management_requested)
        layout.addWidget(self.id_badge)

        # Divider line between ID and Logo (Figma spec)
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedHeight(24)  # Visual height of divider
        divider.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.2);
                max-width: 1px;
            }
        """)
        layout.addWidget(divider)

        # Logo - Reusable component (rightmost)
        self.logo = LogoWidget(height=NavbarDimensions.LOGO_SCALED_HEIGHT)
        layout.addWidget(self.logo)

        return top_bar

    def _create_window_controls(self):
        """
        Create window control buttons (minimize, maximize, close)

        Figma: Size 46×32px each (matching login page)
        """
        box = QWidget()
        box.setObjectName("window_controls")
        box.setLayoutDirection(Qt.LeftToRight)

        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Buttons
        btn_min = QPushButton("–")
        btn_max = QPushButton("□")
        btn_close = QPushButton("✕")

        # Make maximize button icon 2x larger (matching login page)
        btn_max.setStyleSheet("""
            QPushButton {
                font-size: 28px;
                margin-bottom: 4px;
            }
        """)

        btn_min.setObjectName("win_btn")
        btn_max.setObjectName("win_btn")
        btn_close.setObjectName("win_close")

        # Figma dimensions: 46×32px (matching login page)
        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(46, 32)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(QCursor(Qt.PointingHandCursor))

        # Connect signals
        btn_min.clicked.connect(lambda: self.window().showMinimized())
        # btn_max.clicked.connect(self._toggle_max_restore)  # Disabled per requirements
        btn_close.clicked.connect(lambda: self.window().close())

        lay.addWidget(btn_min)
        lay.addWidget(btn_max)
        lay.addWidget(btn_close)

        return box

    def _toggle_max_restore(self):
        """Toggle window maximize/restore"""
        w = self.window()
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()

    def _create_search_bar(self):
        """
        Create search bar with menu and icon

        Figma: W=450px, H=32px, Border-radius=4px
        Background: #1A3A5C (SEARCH_BG)
        Layout: [Search Icon] [Input] [Menu Dropdown]
        """
        search_container = QWidget()
        search_container.setFixedWidth(NavbarDimensions.SEARCH_BAR_WIDTH)
        search_container.setFixedHeight(NavbarDimensions.SEARCH_BAR_HEIGHT)
        search_container.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.SEARCH_BG};
                border-radius: 4px;
            }}
        """)

        layout = QHBoxLayout(search_container)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # Search icon button (right side in RTL) - using search.png
        search_icon_btn = QPushButton()
        search_icon_btn.setFixedSize(24, 24)
        search_icon_btn.setCursor(QCursor(Qt.PointingHandCursor))

        # Load search icon
        search_icon_path = Path(__file__).parent.parent.parent / "assets" / "images" / "search.png"
        if search_icon_path.exists():
            icon = QIcon(str(search_icon_path))
            search_icon_btn.setIcon(icon)
            search_icon_btn.setIconSize(QSize(16, 16))
        else:
            search_icon_btn.setText("🔍")
            fallback_font = create_font(size=9, weight=QFont.Normal)  # 12px × 0.75 = 9pt
            search_icon_btn.setFont(fallback_font)

        search_icon_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        search_icon_btn.clicked.connect(self._on_search)

        # Search input field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("navbar.search.default"))

        # Figma: IBM Plex Sans Arabic, 10px, Letter spacing 0
        # Font conversion: 10px × 0.75 = 7.5pt ≈ 8pt
        search_font = create_font(size=8, weight=QFont.Normal, letter_spacing=0)
        self.search_input.setFont(search_font)

        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: white;
                border: none;
                padding: 0px;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)

        # Menu dropdown button (left side in RTL) - using list.png
        menu_btn = QPushButton()
        menu_btn.setFixedSize(20, 20)
        menu_btn.setCursor(QCursor(Qt.PointingHandCursor))

        # Load list.png dropdown menu icon
        list_icon_path = Path(__file__).parent.parent.parent / "assets" / "images" / "list.png"
        if list_icon_path.exists():
            list_icon = QIcon(str(list_icon_path))
            menu_btn.setIcon(list_icon)
            menu_btn.setIconSize(QSize(16, 16))
        else:
            menu_btn.setText("☰")
            fallback_font = create_font(size=9, weight=QFont.Normal)  # 12px × 0.75 = 9pt
            menu_btn.setFont(fallback_font)

        menu_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        menu_btn.clicked.connect(self._on_search_menu_clicked)
        self.search_menu_btn = menu_btn

        # Add widgets (RTL layout)
        layout.addWidget(search_icon_btn)
        layout.addWidget(self.search_input)
        layout.addWidget(menu_btn)

        return search_container

    def _create_tabs_bar(self):
        """
        Create tabs bar with navigation tabs

        Figma Specs:
        - Height: 48px
        - Padding: 24px horizontal
        - Gap between tabs: 24px
        - Font: 14px (11pt) SemiBold, Line height 22px
        - Active tab: Background=#DEEBFF, Text=#3B86FF, Border-radius=8px
        """
        tabs_container = QFrame()
        tabs_container.setObjectName("tabs_bar")
        tabs_container.setFixedHeight(NavbarDimensions.TABS_BAR_HEIGHT)  # 48px

        layout = QHBoxLayout(tabs_container)
        # Vertical centering: (48 - 32) / 2 = 8px top/bottom
        layout.setContentsMargins(
            Spacing.NAVBAR_HORIZONTAL_PADDING, 8,  # 24px left, 8px top
            Spacing.NAVBAR_HORIZONTAL_PADDING, 8   # 24px right, 8px bottom
        )
        layout.setSpacing(NavbarDimensions.TAB_GAP)  # 24px gap between tabs (Figma)

        # Tab titles (translatable)
        self._tab_keys = [
            "navbar.tab.completed_claims",
            "navbar.tab.drafts",
            "navbar.tab.buildings",
            "navbar.tab.residential_units",
            "navbar.tab.duplicates",
            "navbar.tab.user_management",
        ]
        tab_titles = [tr(key) for key in self._tab_keys]

        self.tab_buttons = []
        for index, title in enumerate(tab_titles):
            tab_btn = self._create_tab_button(title, index)
            self.tab_buttons.append(tab_btn)
            layout.addWidget(tab_btn)

        # Spacer to push tabs to the right
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Set first tab as active
        self._set_active_tab(0)

        return tabs_container

    def _create_tab_button(self, title: str, index: int) -> QPushButton:
        """
        Create a single tab button

        Figma Specs:
        - Height: 32px (Hug)
        - Font: IBM Plex Sans Arabic, 14px (11pt in PyQt5), SemiBold (600)
        - Line Height: 22px
        - Padding: 5px (V) × 12px (H)
        - Gap: 24px between tabs
        - Border-radius: 8px
        - Letter spacing: 0
        """
        tab_btn = QPushButton(title)
        tab_btn.setFixedHeight(NavbarDimensions.TAB_HEIGHT)  # 32px
        tab_btn.setCursor(QCursor(Qt.PointingHandCursor))

        # Use centralized font utility (DRY + eliminates conflicts)
        # Figma: 14px SemiBold, Line height 22px, Letter spacing 0
        tab_font = create_font(
            size=NavbarDimensions.TAB_FONT_SIZE,  # 11pt (14px × 0.75)
            weight=NavbarDimensions.TAB_FONT_WEIGHT,  # SemiBold (600)
            letter_spacing=0
        )
        tab_btn.setFont(tab_font)

        tab_btn.setProperty("tab_index", index)
        tab_btn.setProperty("active", False)
        tab_btn.clicked.connect(lambda: self._on_tab_clicked(index))

        return tab_btn

    def _set_active_tab(self, index: int):
        """
        Set active tab with Figma styling

        Figma Specs:
        - Active: bg=#DEEBFF, text=#3B86FF, border-radius=8px, padding=5px 12px
        - Inactive: bg=transparent, text=rgba(255,255,255,0.7), padding=5px 12px
        - Font: 14px (11pt) SemiBold (600), Line height 22px
        - Gap: 24px between tabs
        """
        self.current_tab_index = index

        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                # Active tab - #DEEBFF background, #3B86FF text
                btn.setProperty("active", True)
                btn.setStyleSheet(f"""
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
                """)
            else:
                # Inactive tab - Transparent background, white text with opacity
                btn.setProperty("active", False)
                btn.setStyleSheet(f"""
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
                """)

    def _on_tab_clicked(self, index: int):
        """Handle tab click event"""
        self._set_active_tab(index)
        self.tab_changed.emit(index)

    def _on_search(self):
        """Handle search request (Enter pressed or icon clicked)"""
        self.search_requested.emit(self.search_input.text())

    def _on_search_menu_clicked(self):
        """Show search mode selection menu"""
        from PyQt5.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                color: #2C3E50;
                font-family: '{Typography.FONT_FAMILY_ARABIC}';
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border-radius: 3px;
            }}
        """)

        # Search mode options
        name_action = menu.addAction(tr("navbar.search_menu.by_name"))
        id_action = menu.addAction(tr("navbar.search_menu.by_claim_id"))
        building_action = menu.addAction(tr("navbar.search_menu.by_building"))

        # Show menu
        action = menu.exec_(
            self.search_menu_btn.mapToGlobal(
                self.search_menu_btn.rect().bottomLeft()
            )
        )

        # Update search mode
        if action == name_action:
            self.search_mode = "name"
            self.search_input.setPlaceholderText(tr("navbar.search.by_name"))
        elif action == id_action:
            self.search_mode = "claim_id"
            self.search_input.setPlaceholderText(tr("navbar.search.by_claim_id"))
        elif action == building_action:
            self.search_mode = "building"
            self.search_input.setPlaceholderText(tr("navbar.search.by_building"))

    def _apply_styles(self):
        """Apply navbar background and component styles"""
        self.setStyleSheet(f"""
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
        """)

    # Role-based tab visibility
    TAB_PERMISSIONS = {
        "admin": [0, 1, 2, 3, 4, 5],
        "data_manager": [0, 1, 2, 3, 4, 5],
        "office_clerk": [0, 1, 2, 3],
        "field_supervisor": [0, 1, 2, 3],
        "field_researcher": [1, 2],
        "analyst": [0, 2, 3, 4],
    }

    def configure_for_role(self, role: str):
        """Show/hide tabs based on user role."""
        allowed = self.TAB_PERMISSIONS.get(role, [0, 1, 2, 3, 4, 5])
        for i, btn in enumerate(self.tab_buttons):
            btn.setVisible(i in allowed)
        # Select the first visible tab
        for idx in sorted(allowed):
            if idx < len(self.tab_buttons):
                self._set_active_tab(idx)
                self.tab_changed.emit(idx)
                break

    # Public API methods

    def set_current_tab(self, index: int):
        """Set active tab programmatically"""
        if 0 <= index < len(self.tab_buttons):
            self._set_active_tab(index)

    def get_current_tab(self) -> int:
        """Get current active tab index"""
        return self.current_tab_index

    def set_user_id(self, user_id: str):
        """Update user ID display"""
        self.user_id = user_id
        if hasattr(self, 'id_badge'):
            self.id_badge.set_user_id(user_id)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts when language changes."""
        # Update tab titles
        for i, key in enumerate(self._tab_keys):
            if i < len(self.tab_buttons):
                self.tab_buttons[i].setText(tr(key))

        # Update search placeholder based on current search mode
        mode = getattr(self, 'search_mode', 'default')
        placeholder_map = {
            'default': "navbar.search.default",
            'name': "navbar.search.by_name",
            'claim_id': "navbar.search.by_claim_id",
            'building': "navbar.search.by_building",
        }
        self.search_input.setPlaceholderText(tr(placeholder_map.get(mode, "navbar.search.default")))

        # Update ID badge menu
        if hasattr(self, 'id_badge'):
            self.id_badge.update_language(is_arabic)

    def _on_logout_requested(self):
        """Handle logout request from ID badge dropdown"""
        self.logout_requested.emit()

    def _on_language_change_requested(self):
        """Handle language change request from ID badge dropdown"""
        self.language_change_requested.emit()

    def _on_sync_requested(self):
        """Handle sync data request from ID badge dropdown"""
        self.sync_requested.emit()

    def _on_password_change_requested(self):
        """Handle password change request from ID badge dropdown"""
        self.password_change_requested.emit()

    def _on_security_settings_requested(self):
        """Handle security settings request from ID badge dropdown"""
        self.security_settings_requested.emit()

    def _on_data_management_requested(self):
        """Handle data management request from ID badge dropdown"""
        self.data_management_requested.emit()


class SimpleNavbar(QFrame):
    """
    Simplified Navbar without tabs
    For pages that don't need tab navigation

    Usage:
        navbar = SimpleNavbar(title="تفاصيل المطالبة", user_id="12345")
    """

    search_requested = pyqtSignal(str)
    back_clicked = pyqtSignal()

    def __init__(self, title="", user_id="12345", show_search=True, show_back=False, parent=None):
        super().__init__(parent)

        self.setObjectName("simple_navbar")
        self.user_id = user_id
        self.title = title
        self.show_search = show_search
        self.show_back = show_back

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup simple navbar UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        # Back button
        if self.show_back:
            back_btn = QPushButton("←")
            back_btn.setFixedSize(40, 40)
            back_font = create_font(size=15, weight=QFont.Normal)  # 20px × 0.75 = 15pt
            back_btn.setFont(back_font)
            back_btn.setCursor(QCursor(Qt.PointingHandCursor))
            back_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                }
            """)
            back_btn.clicked.connect(self.back_clicked.emit)
            layout.addWidget(back_btn)

        # Logo
        logo = LogoWidget(height=20)
        layout.addWidget(logo)

        # ID Badge
        id_badge = IDBadgeWidget(user_id=self.user_id, font_size=13)
        layout.addWidget(id_badge)

        # Title
        if self.title:
            title_label = QLabel(self.title)
            # 16px × 0.75 = 12pt
            title_font = create_font(size=12, weight=QFont.DemiBold, letter_spacing=0)
            title_label.setFont(title_font)
            title_label.setStyleSheet("color: white; background: transparent;")
            layout.addWidget(title_label)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Search bar
        if self.show_search:
            search_widget = QWidget()
            search_widget.setFixedWidth(320)
            search_layout = QHBoxLayout(search_widget)
            search_layout.setContentsMargins(0, 0, 0, 0)

            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText(tr("navbar.search.simple"))

            # 13px × 0.75 = 9.75pt ≈ 10pt
            simple_search_font = create_font(size=10, weight=QFont.Normal, letter_spacing=0)
            self.search_input.setFont(simple_search_font)

            self.search_input.setFixedHeight(36)
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Colors.SEARCH_BG};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }}
                QLineEdit::placeholder {{
                    color: rgba(255, 255, 255, 0.5);
                }}
            """)
            self.search_input.returnPressed.connect(self._on_search)
            search_layout.addWidget(self.search_input)
            layout.addWidget(search_widget)

        self.setFixedHeight(60)

    def _apply_styles(self):
        """Apply simple navbar styles"""
        self.setStyleSheet(f"""
            QFrame#simple_navbar {{
                background-color: {Colors.NAVBAR_BG};
                border: none;
            }}
        """)

    def _on_search(self):
        """Handle search event"""
        if self.show_search and hasattr(self, 'search_input'):
            search_text = self.search_input.text().strip()
            if search_text:
                self.search_requested.emit(search_text)
