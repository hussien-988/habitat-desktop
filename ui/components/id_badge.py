# -*- coding: utf-8 -*-
"""
ID Badge Widget — كبسولة المستخدم
Frosted glass capsule showing user icon and ID.
"""

from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QCursor

from ui.components.icon import Icon
from ui.design_system import NavbarDimensions, Colors, Typography


class IDBadgeWidget(QWidget):
    """Fixed frosted glass capsule: user icon + ID text."""

    language_change_requested = pyqtSignal()

    def __init__(self, user_id="12345", parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self._setup_ui()
        self._apply_styling()

    def _format_user_id(self, user_id):
        user_id_str = str(user_id)
        if len(user_id_str) > 10:
            if '-' in user_id_str:
                return user_id_str.split('-')[-1][:5]
            else:
                return user_id_str[-5:]
        return user_id_str

    def _create_user_icon(self):
        icon_label = QLabel()
        icon_label.setFixedSize(22, 22)
        icon_label.setAlignment(Qt.AlignCenter)

        vector_pixmap = Icon.load_pixmap("Vector", size=11)
        if vector_pixmap and not vector_pixmap.isNull():
            icon_label.setPixmap(vector_pixmap)

        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.PRIMARY_BLUE};
                border-radius: 11px;
            }}
        """)
        return icon_label

    def _create_id_text_label(self, display_id):
        id_label = QLabel(f"ID {display_id}")
        font = QFont(Typography.FONT_FAMILY_ARABIC)
        font.setPixelSize(14)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        id_label.setFont(font)
        id_label.setStyleSheet("color: rgba(200, 220, 255, 230); background: transparent;")
        id_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        return id_label

    def _setup_ui(self):
        display_id = self._format_user_id(self.user_id)

        self.setLayoutDirection(Qt.LeftToRight)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 10, 3)
        layout.setSpacing(6)

        # User icon (always visually first)
        self.icon_label = self._create_user_icon()
        layout.addWidget(self.icon_label)

        # ID text
        self.id_label = self._create_id_text_label(display_id)
        layout.addWidget(self.id_label)

        self.setFixedHeight(30)

    def _apply_styling(self):
        self.setStyleSheet(f"""
            IDBadgeWidget {{
                background: {Colors.FROSTED_BG};
                border-radius: {NavbarDimensions.ID_BADGE_BORDER_RADIUS}px;
                border: 1px solid {Colors.FROSTED_BORDER};
            }}
            IDBadgeWidget:hover {{
                border: 1px solid {Colors.FROSTED_BORDER_HOVER};
            }}
        """)

    def update_language(self, is_arabic: bool):
        """No-op (language toggle moved to settings pill)."""
        pass

    def set_user_id(self, user_id):
        self.user_id = user_id
        display_id = self._format_user_id(user_id)
        if hasattr(self, 'id_label'):
            self.id_label.setText(f"ID {display_id}")
