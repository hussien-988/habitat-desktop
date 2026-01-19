# -*- coding: utf-8 -*-
"""
Shared Navbar Component - Figma Design (Pages 1-31)
المكون المشترك للشريط العلوي مع التبويبات

This is the shared navigation bar that appears across all pages.
Specifications extracted from Figma screenshot:
- Background: #122C49 (dark navy blue)
- Height: 60px (top bar) + 48px (tabs) = 108px total
- Active tab indicator: #9BC2FF (3px bottom border)
- Tab text: white with 0.7 opacity when inactive
"""

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QWidget, QPushButton,
    QVBoxLayout, QSpacerItem, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QFont, QCursor

from ..design_system import Colors

class DraggableFrame(QFrame):
    """فريم بيتسحب منه التطبيق لما نشيل إطار الويندوز"""

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
    Shared Navbar Component - المكون المشترك للشريط العلوي

    Exact specifications from Figma screenshot:
    - Background: #122C49
    - Total height: 108px (60px top + 48px tabs)
    - Active tab indicator: #9BC2FF, 3px bottom border
    - Inactive tabs: white text with 0.7 opacity
    - Active tab: white text with 1.0 opacity
    """

    # Signals
    tab_changed = pyqtSignal(int)  # Emitted when tab changes
    search_requested = pyqtSignal(str)  # Emitted when search is performed

    def __init__(self, user_id=None, parent=None):
        super().__init__(parent)
        # Default to placeholder if no user_id provided (for testing)
        self.user_id = user_id or "00000"
        self.setObjectName("shared_navbar")
        self.current_tab_index = 0
        self.tab_buttons = []

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup navbar UI matching Figma screenshot exactly"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar (logo, ID badge, search, menu) - 60px height
        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        # Tab bar - 48px height
        tabs_bar = self._create_tabs_bar()
        main_layout.addWidget(tabs_bar)

        self.setFixedHeight(108)  # 60 + 48 = 108px total

    def _create_top_bar(self):
        """Create the top bar - 60px height with logo, ID, search, menu"""
        top_bar = DraggableFrame()
        top_bar.setObjectName("navbar_top")
        top_bar.setAttribute(Qt.WA_StyledBackground, True)
        top_bar.setFixedHeight(60)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(24, 0, 24, 0)  # 24px horizontal padding
        layout.setSpacing(16)
        #الازرار 
        win_controls = self._create_window_controls()
        layout.addWidget(win_controls)
        # Spacer before search (to center it)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Search bar - 400px width (centered)
        self.search_bar = self._create_search_bar()
        layout.addWidget(self.search_bar)

        # Spacer after search (to center it)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # ID Badge - far left in RTL (right side visually)
        id_badge = self._create_id_badge()
        layout.addWidget(id_badge)

        # UN-HABITAT Logo - leftmost in RTL (rightmost visually)
        logo_widget = self._create_logo()
        layout.addWidget(logo_widget)
        


        return top_bar

    def _create_logo(self):
        """Create UN-HABITAT logo from image file"""
        from pathlib import Path
        from PyQt5.QtGui import QPixmap

        logo = QLabel()

        # Load logo image from assets
        logo_path = Path(__file__).parent.parent.parent / "assets" / "images" / "header.png"

        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            # Scale to smaller size - 28px height
            scaled_pixmap = pixmap.scaledToHeight(20, Qt.SmoothTransformation)
            logo.setPixmap(scaled_pixmap)
        else:
            # Fallback to text if image not found
            logo.setText("UN-HABITAT")
            logo.setFont(QFont("Noto Kufi Arabic", 10, QFont.Bold))

        logo.setStyleSheet("""
            QLabel {
                background: transparent;
            }
        """)
        return logo
    def _create_window_controls(self):
        box = QWidget()
        box.setObjectName("window_controls")

        box.setLayoutDirection(Qt.LeftToRight)

        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        btn_min = QPushButton("–")
        btn_max = QPushButton("□")
        btn_close = QPushButton("✕")

        btn_min.setObjectName("win_btn")
        btn_max.setObjectName("win_btn")
        btn_close.setObjectName("win_close")

        # الحجم الأساسي (بدون تغيير)
        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(40, 28)
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(QCursor(Qt.PointingHandCursor))

        btn_min.clicked.connect(lambda: self.window().showMinimized())
        # زر التكبير متوقف - لا يفعل شيء
        # btn_max.clicked.connect(self._toggle_max_restore)
        btn_close.clicked.connect(lambda: self.window().close())

    
        lay.addWidget(btn_min)
        lay.addWidget(btn_max)
        lay.addWidget(btn_close)
        return box



    def _toggle_max_restore(self):
        w = self.window()
        if w.isMaximized():
            w.showNormal()  
        else:
            w.showMaximized()


    def _create_id_badge(self):
        """Create ID badge with border"""
        # If user_id is a UUID (long), show only last 5 characters
        # Otherwise show the full ID
        display_id = self.user_id
        if len(str(self.user_id)) > 10:
            # Extract last segment after last dash, or last 5 chars
            if '-' in str(self.user_id):
                display_id = str(self.user_id).split('-')[-1][:5]
            else:
                display_id = str(self.user_id)[-5:]

        id_badge = QLabel(f"ID {display_id}")
        id_badge.setFont(QFont("Noto Kufi Arabic", 9))
        id_badge.setStyleSheet(f"""
            QLabel {{
                color: white;
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 3px;
                padding: 3px 8px;
            }}
        """)
        self._id_badge_widget = id_badge  # Store reference for updates
        return id_badge

    def _create_search_bar(self):
        """Create search bar with menu icon inside - matching Figma reference exactly"""
        search_container = QWidget()
        search_container.setFixedWidth(450)
        search_container.setFixedHeight(32)
        search_container.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.SEARCH_BG};
                border-radius: 4px;
            }}
        """)

        # Layout inside search container
        layout = QHBoxLayout(search_container)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # Search icon button on the RIGHT (🔍) - clickable to trigger search
        search_icon_btn = QPushButton("🔍")
        search_icon_btn.setFixedSize(24, 24)
        search_icon_btn.setCursor(QCursor(Qt.PointingHandCursor))
        search_icon_btn.setFont(QFont("Arial", 12))
        search_icon_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.6);
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                color: white;
            }
            QPushButton:pressed {
                color: rgba(255, 255, 255, 0.8);
            }
        """)
        search_icon_btn.clicked.connect(self._on_search)

        # Search input
        search_input = QLineEdit()
        search_input.setPlaceholderText("ابحث عنالرمزأوالاسم...")
        search_input.setFont(QFont("Noto Kufi Arabic", 10))
        search_input.setStyleSheet("""
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
        search_input.returnPressed.connect(self._on_search)
        search_input.textChanged.connect(self._on_search_text_changed)

        # Dropdown menu button (▼) on the LEFT inside search field
        menu_btn = QPushButton("▼")
        menu_btn.setFixedSize(20, 20)
        menu_btn.setCursor(QCursor(Qt.PointingHandCursor))
        menu_btn.setFont(QFont("Arial", 10))
        menu_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        menu_btn.clicked.connect(self._on_search_menu_clicked)

        # Add widgets to layout (RIGHT to LEFT in RTL)
        layout.addWidget(search_icon_btn)
        layout.addWidget(search_input)
        layout.addWidget(menu_btn)

        self.search_input = search_input
        self.search_menu_btn = menu_btn
        self.search_mode = "name"  # Default: search by name
        return search_container

    def _create_tabs_bar(self):
        """Create tabs bar - 48px height with custom tab buttons"""
        tabs_container = QFrame()
        tabs_container.setObjectName("tabs_bar")
        tabs_container.setFixedHeight(48)

        layout = QHBoxLayout(tabs_container)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(0)

        # Tab titles from Figma screenshot (RIGHT to LEFT as they appear visually)
        # Starting with "المطالبات المكتملة" on the right
        tab_titles = [
            "المطالبات المكتملة",  # Completed Claims (rightmost) - ACTIVE by default
            "المسودة",             # Drafts
            "المباني",             # Buildings
            "الوحدات السكنية",     # Residential Units
            "التكرارات",           # Duplicates
            "استيراد"     # Import Data (UC-003)
        ]

        self.tab_buttons = []
        for index, title in enumerate(tab_titles):
            tab_btn = self._create_tab_button(title, index)
            self.tab_buttons.append(tab_btn)
            layout.addWidget(tab_btn)

        # Spacer to push tabs to the right (in RTL mode, this appears on the left)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Set first tab as active
        self._set_active_tab(0)

        return tabs_container

    def _create_tab_button(self, title: str, index: int) -> QPushButton:
        """Create a single tab button with exact Figma styling"""
        tab_btn = QPushButton(title)
        tab_btn.setFixedHeight(48)
        tab_btn.setCursor(QCursor(Qt.PointingHandCursor))
        tab_btn.setFont(QFont("Noto Kufi Arabic", 9))
        tab_btn.setProperty("tab_index", index)
        tab_btn.setProperty("active", False)

        # Initial style (inactive)
        tab_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                padding: 0px 16px;
                text-align: center;
            }
            QPushButton:hover {
                color: rgba(255, 255, 255, 0.9);
                background: rgba(255, 255, 255, 0.05);
            }
        """)

        tab_btn.clicked.connect(lambda: self._on_tab_clicked(index))
        return tab_btn

    def _set_active_tab(self, index: int):
        """Set the active tab with background color from Figma"""
        self.current_tab_index = index

        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                # Active tab style - background color #9BC2FF, text color #122C49
                btn.setProperty("active", True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Colors.BACKGROUND};
                        color: #3890fd;
                        border: none;
                        border-radius: 8px;
                        padding: 6px 12px;
                        text-align: center;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        border: 1px solid #F0F7FF;
                    }}
                """)
            else:
                # Inactive tab style - transparent background, white text with opacity
                btn.setProperty("active", False)
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: rgba(255, 255, 255, 0.7);
                        border: none;
                        padding: 6px 12px;
                        text-align: center;
                    }
                    QPushButton:hover {
                        color: rgba(255, 255, 255, 0.9);
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 4px;
                    }
                """)

    def _on_tab_clicked(self, index: int):
        """Handle tab click"""
        self._set_active_tab(index)
        self.tab_changed.emit(index)

    def _apply_styles(self):
        """Apply navbar background color"""
        self.setStyleSheet(f"""
            QFrame#shared_navbar {{
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
                font-size: 13px;
                font-weight: 600;
                border-radius: 8px;
            }}
            QPushButton#win_btn:hover {{
                background: rgba(255,255,255,0.14);
            }}
            QPushButton#win_btn:pressed {{
                background: rgba(255,255,255,0.22);
            }}
            QPushButton#win_close:hover {{
                background: rgba(255,59,48,0.9);
            }}
            QPushButton#win_close:pressed {{
                background: rgba(255, 59, 48, 0.75);
            }}

        """)

    def _on_search(self):
        """Handle search request when user presses Enter"""
        if hasattr(self, 'search_input'):
            search_text = self.search_input.text()
            if search_text.strip():
                # Emit search with mode: (query, mode)
                self.search_requested.emit(f"{self.search_mode}:{search_text}")

    def _on_search_text_changed(self, text):
        """Handle real-time search as user types"""
        # يمكن استخدامها للبحث الفوري
        pass

    def _on_search_menu_clicked(self):
        """Show menu to select search mode"""
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
                font-family: 'Noto Kufi Arabic';
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border-radius: 3px;
            }}
        """)

        # إضافة خيارات البحث
        name_action = menu.addAction("🔍 بحث بالاسم")
        id_action = menu.addAction("🔢 بحث برقم المطالبة")
        building_action = menu.addAction("🏢 بحث بالمبنى")

        # عرض القائمة
        action = menu.exec_(self.search_menu_btn.mapToGlobal(
            self.search_menu_btn.rect().bottomLeft()
        ))

        # تحديد طريقة البحث بناءً على الاختيار
        if action == name_action:
            self.search_mode = "name"
            self.search_input.setPlaceholderText("ابحث عن اسم المستلم...")
        elif action == id_action:
            self.search_mode = "claim_id"
            self.search_input.setPlaceholderText("ابحث برقم المطالبة...")
        elif action == building_action:
            self.search_mode = "building"
            self.search_input.setPlaceholderText("ابحث عن المبنى...")

    def set_current_tab(self, index: int):
        """Set the active tab programmatically"""
        if 0 <= index < len(self.tab_buttons):
            self._set_active_tab(index)

    def get_current_tab(self) -> int:
        """Get current active tab index"""
        return self.current_tab_index

    def set_user_id(self, user_id: str):
        """Update user ID display"""
        self.user_id = user_id
        # Find and update ID badge
        for child in self.findChildren(QLabel):
            if "ID" in child.text():
                child.setText(f"ID {user_id}")
                break


class SimpleNavbar(QFrame):
    """
    Simplified Navbar without tabs
    For pages that don't need tab navigation (e.g., detail pages, forms)
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

        # Back button (if needed)
        if self.show_back:
            back_btn = QPushButton("←")
            back_btn.setFixedSize(40, 40)
            back_btn.setFont(QFont("Arial", 20))
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
        logo = QLabel("UN-HABITAT")
        logo.setFont(QFont("Noto Kufi Arabic", 14, QFont.Bold))
        logo.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(logo)

        # User badge
        user_badge = QLabel(f"ID {self.user_id}")
        user_badge.setFont(QFont("Noto Kufi Arabic", 13))
        user_badge.setStyleSheet("""
            QLabel {
                color: white;
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 4px;
                padding: 4px 12px;
            }
        """)
        layout.addWidget(user_badge)

        # Title (if provided)
        if self.title:
            title_label = QLabel(self.title)
            title_label.setFont(QFont("Noto Kufi Arabic", 16, QFont.DemiBold))
            title_label.setStyleSheet("color: white; background: transparent;")
            layout.addWidget(title_label)

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Search bar (if needed)
        if self.show_search:
            search_widget = QWidget()
            search_widget.setFixedWidth(320)
            search_layout = QHBoxLayout(search_widget)
            search_layout.setContentsMargins(0, 0, 0, 0)

            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("بحث...")
            self.search_input.setFont(QFont("Noto Kufi Arabic", 13))
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
        """Apply styles"""
        self.setStyleSheet(f"""
            QFrame#simple_navbar {{
                background-color: {Colors.NAVBAR_BG};
                border: none;
            }}
        """)

    def _on_search(self):
        """Handle search"""
        if self.show_search and hasattr(self, 'search_input'):
            search_text = self.search_input.text()
            if search_text.strip():
                self.search_requested.emit(search_text)
