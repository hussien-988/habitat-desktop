# -*- coding: utf-8 -*-


from pathlib import Path
from PyQt5.QtWidgets import QWidget, QMenu, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QCursor, QIcon

from ..design_system import NavbarDimensions, Colors, Typography
from services.translation_manager import tr


class IDBadgeWidget(QWidget):

    # Signals for dropdown menu actions
    language_change_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    password_change_requested = pyqtSignal()
    security_settings_requested = pyqtSignal()
    data_management_requested = pyqtSignal()
    logout_requested = pyqtSignal()

    def __init__(self, user_id="12345", parent=None):
        super().__init__(parent)

        self.user_id = user_id
        self._setup_ui()
        self._setup_menu()
        self._apply_styling()

    def _format_user_id(self, user_id):
        user_id_str = str(user_id)

        # If ID is long (UUID-like), show only last 5 digits
        if len(user_id_str) > 10:
            if '-' in user_id_str:
                return user_id_str.split('-')[-1][:5]
            else:
                return user_id_str[-5:]

        return user_id_str

    def _create_user_icon(self):
        from PyQt5.QtGui import QPixmap

        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        icon_label.setAlignment(Qt.AlignCenter)

        # Try to load Vector.png
        vector_path = Path(__file__).parent.parent.parent / "assets" / "images" / "Vector.png"

        if vector_path.exists():
            pixmap = QPixmap(str(vector_path))
            # Scale to fit inside circle with some padding
            scaled = pixmap.scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(scaled)

        # Style: Blue circle background (Figma: border-radius 500px for perfect circle)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.PRIMARY_BLUE};
                border-radius: 10px;
            }}
        """)

        return icon_label

    def _create_id_text_label(self, display_id):
        id_label = QLabel(f"ID {display_id}")

        # Figma: IBM Plex Sans Arabic, 14px, Letter spacing 0
        font = QFont(Typography.FONT_FAMILY_ARABIC)
        font.setPixelSize(16)  # Exact pixel size for Figma match
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0)

        id_label.setFont(font)
        id_label.setStyleSheet(f"color: {Colors.TEXT_ON_DARK}; background: transparent;")
        id_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        return id_label

    def _create_dropdown_arrow(self):
        arrow_label = QLabel()
        arrow_label.setFixedSize(10, 10)
        arrow_label.setAlignment(Qt.AlignCenter)

        # Try to load primary-shape.png
        arrow_path = Path(__file__).parent.parent.parent / "assets" / "images" / "primary-shape.png"

        if arrow_path.exists():
            arrow_label.setPixmap(
                QIcon(str(arrow_path)).pixmap(QSize(8, 8))
            )
        else:
            # Fallback to text arrow
            arrow_label.setText("▼")
            arrow_label.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.TEXT_ON_DARK};
                    font-size: 8px;
                    background: transparent;
                }}
            """)

        arrow_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
            }}
        """)

        return arrow_label

    def _setup_ui(self):
        display_id = self._format_user_id(self.user_id)

        # Create main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # No padding for Hug
        layout.setSpacing(4)  # 4px gap from Figma

        # Create and add components in correct order: icon → id → arrow
        self.icon_label = self._create_user_icon()
        self.id_label = self._create_id_text_label(display_id)
        self.arrow_label = self._create_dropdown_arrow()



        
        layout.addWidget(self.arrow_label)
        layout.addWidget(self.id_label)
        layout.addWidget(self.icon_label)
        
        

        # Widget behavior
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(22)  # 22px from Figma

    def _apply_styling(self):
        self.setStyleSheet(f"""
            IDBadgeWidget {{
                background: transparent;
                border-radius: {NavbarDimensions.ID_BADGE_BORDER_RADIUS}px;
            }}
            IDBadgeWidget:hover {{
                background: rgba(255, 255, 255, 0.1);
            }}
        """)

    def _setup_menu(self):
        self.menu = QMenu(self)
        self.menu.setLayoutDirection(Qt.RightToLeft)  # RTL for Arabic

        # Professional menu styling
        self.menu.setStyleSheet(f"""
            QMenu {{
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 0px;
                min-width: 250px;
            }}
            QMenu::item {{
                padding: 12px 20px;
                color: {Colors.TEXT_PRIMARY};
                font-family: '{Typography.FONT_FAMILY_ARABIC}';
                font-size: 14px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.BACKGROUND};
                color: {Colors.PRIMARY_BLUE};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: #E5E7EB;
                margin: 4px 0px;
            }}
        """)

        # Add menu items (translatable)
        self._lang_action = self.menu.addAction(tr("navbar.menu.change_language"))
        self._sync_action = self.menu.addAction(tr("navbar.menu.sync_data"))
        self._password_action = self.menu.addAction(tr("navbar.menu.change_password"))
        self._security_action = self.menu.addAction(tr("navbar.menu.security_policies"))
        self._data_action = self.menu.addAction(tr("navbar.menu.data_management"))

        self.menu.addSeparator()

        self._logout_action = self.menu.addAction(tr("navbar.menu.logout"))

        # Connect signals (Coming Soon for unfinished features)
        from ui.components.coming_soon_popup import ComingSoonPopup
        _coming_soon = lambda: ComingSoonPopup.popup(self)
        self._lang_action.triggered.connect(_coming_soon)
        self._sync_action.triggered.connect(_coming_soon)
        self._password_action.triggered.connect(_coming_soon)
        self._security_action.triggered.connect(_coming_soon)
        self._data_action.triggered.connect(_coming_soon)
        self._logout_action.triggered.connect(self.logout_requested.emit)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_menu()
        super().mousePressEvent(event)

    def _show_menu(self):
        """
        Show dropdown menu positioned below the widget
        """
        widget_rect = self.rect()
        menu_pos = self.mapToGlobal(widget_rect.bottomRight())
        self.menu.exec_(menu_pos)

    def update_language(self, is_arabic: bool):
        """Update menu item texts when language changes."""
        self._lang_action.setText(tr("navbar.menu.change_language"))
        self._sync_action.setText(tr("navbar.menu.sync_data"))
        self._password_action.setText(tr("navbar.menu.change_password"))
        self._security_action.setText(tr("navbar.menu.security_policies"))
        self._data_action.setText(tr("navbar.menu.data_management"))
        self._logout_action.setText(tr("navbar.menu.logout"))

    def set_user_id(self, user_id):
        """
        Update user ID dynamically

        Args:
            user_id (str): New user ID to display
        """
        self.user_id = user_id
        display_id = self._format_user_id(user_id)

        # Update ID label text
        if hasattr(self, 'id_label'):
            self.id_label.setText(f"ID {display_id}")
