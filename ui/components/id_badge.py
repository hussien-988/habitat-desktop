# -*- coding: utf-8 -*-
"""
ID Badge Widget — شارة المستخدم مع قائمة منسدلة
Custom popup dropdown with cloud/bubble shape and PNG icons.
"""

from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout,
    QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt5.QtGui import (
    QFont, QCursor, QIcon, QColor, QPainter,
    QPainterPath, QBrush, QPen
)

from ui.components.icon import Icon
from ui.design_system import NavbarDimensions, Colors, Typography
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr


# =========================================================================
# Menu Item
# =========================================================================

class _MenuItem(QWidget):
    """Single clickable menu item: icon + text."""

    clicked = pyqtSignal()

    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._text = text
        self._hovered = False

        self.setFixedHeight(36)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Icon
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(18, 18)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setStyleSheet("background: transparent;")
        pixmap = Icon.load_pixmap(icon_name, size=18)
        if pixmap and not pixmap.isNull():
            self._icon_label.setPixmap(pixmap)
        layout.addWidget(self._icon_label)

        # Text
        self._text_label = QLabel(text)
        self._text_label.setFont(create_font(
            size=FontManager.SIZE_SMALL,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        self._text_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(self._text_label, stretch=1)

        self._apply_style()

    def set_text(self, text: str):
        self._text_label.setText(text)

    def _apply_style(self):
        if self._hovered:
            self.setStyleSheet(f"background-color: #f0f7ff; border-radius: 6px;")
            self._text_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent;")
        else:
            self.setStyleSheet("background: transparent;")
            self._text_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")

    def enterEvent(self, event):
        self._hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# =========================================================================
# Dropdown Popup (Cloud/Bubble shape)
# =========================================================================

ARROW_HEIGHT = 10
ARROW_WIDTH = 16
POPUP_WIDTH = 191
POPUP_BODY_HEIGHT = 245
POPUP_RADIUS = 12
SHADOW_MARGIN = 12


class _DropdownPopup(QWidget):
    """Custom popup widget with bubble arrow pointing to the badge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        total_w = POPUP_WIDTH + SHADOW_MARGIN * 2
        total_h = ARROW_HEIGHT + POPUP_BODY_HEIGHT + SHADOW_MARGIN * 2
        self.setFixedSize(total_w, total_h)

        # Arrow X offset from right edge (centers on badge)
        self._arrow_x = total_w // 2

        # Container for menu items (inside the body area)
        self._container = QWidget(self)
        self._container.setGeometry(
            SHADOW_MARGIN,
            SHADOW_MARGIN + ARROW_HEIGHT,
            POPUP_WIDTH,
            POPUP_BODY_HEIGHT
        )
        self._container.setStyleSheet("background: transparent;")

        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(6, 8, 6, 8)
        self._layout.setSpacing(2)

        self._items = []

    def add_item(self, item: _MenuItem):
        self._items.append(item)
        self._layout.addWidget(item)
        item.clicked.connect(self.close)

    def add_separator(self):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #E5E7EB;")
        self._layout.addWidget(sep)

    def set_arrow_x(self, x: int):
        """Set X position of arrow tip relative to popup left edge."""
        self._arrow_x = x

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Body rect (below arrow, inside shadow margin)
        body_x = SHADOW_MARGIN
        body_y = SHADOW_MARGIN + ARROW_HEIGHT
        body_w = POPUP_WIDTH
        body_h = POPUP_BODY_HEIGHT

        # Draw shadow
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(
            body_x, body_y, body_w, body_h,
            POPUP_RADIUS, POPUP_RADIUS
        )
        for i in range(SHADOW_MARGIN):
            alpha = 8 - int(8 * i / SHADOW_MARGIN)
            painter.setPen(QPen(QColor(0, 0, 0, alpha), 1))
            painter.setBrush(Qt.NoBrush)
            offset = i * 0.5
            shadow = QPainterPath()
            shadow.addRoundedRect(
                body_x - offset, body_y - offset + 2,
                body_w + offset * 2, body_h + offset * 2,
                POPUP_RADIUS + offset, POPUP_RADIUS + offset
            )
            painter.drawPath(shadow)

        # Main body path
        path = QPainterPath()
        path.addRoundedRect(
            body_x, body_y, body_w, body_h,
            POPUP_RADIUS, POPUP_RADIUS
        )

        # Arrow triangle (pointing up)
        arrow_cx = self._arrow_x
        arrow_top = SHADOW_MARGIN
        arrow_base = body_y

        arrow_path = QPainterPath()
        arrow_path.moveTo(arrow_cx, arrow_top)
        arrow_path.lineTo(arrow_cx + ARROW_WIDTH // 2, arrow_base)
        arrow_path.lineTo(arrow_cx - ARROW_WIDTH // 2, arrow_base)
        arrow_path.closeSubpath()

        # Unite body + arrow
        combined = path.united(arrow_path)

        # Fill white
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        painter.setBrush(QBrush(QColor("white")))
        painter.drawPath(combined)

        painter.end()


# =========================================================================
# ID Badge Widget
# =========================================================================

class IDBadgeWidget(QWidget):

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

        vector_pixmap = Icon.load_pixmap("Vector", size=10)
        if vector_pixmap and not vector_pixmap.isNull():
            icon_label.setPixmap(vector_pixmap)

        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.PRIMARY_BLUE};
                border-radius: 10px;
            }}
        """)
        return icon_label

    def _create_id_text_label(self, display_id):
        id_label = QLabel(f"ID {display_id}")
        font = QFont(Typography.FONT_FAMILY_ARABIC)
        font.setPixelSize(16)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
        id_label.setFont(font)
        id_label.setStyleSheet(f"color: {Colors.TEXT_ON_DARK}; background: transparent;")
        id_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        return id_label

    def _create_dropdown_arrow(self):
        arrow_label = QLabel()
        arrow_label.setFixedSize(10, 10)
        arrow_label.setAlignment(Qt.AlignCenter)

        arrow_pixmap = Icon.load_pixmap("primary-shape", size=8)
        if arrow_pixmap and not arrow_pixmap.isNull():
            arrow_label.setPixmap(arrow_pixmap)
        else:
            arrow_label.setText("▼")
            arrow_label.setStyleSheet(f"color: {Colors.TEXT_ON_DARK}; font-size: 8px; background: transparent;")

        arrow_label.setStyleSheet("background: transparent;")
        return arrow_label

    def _setup_ui(self):
        display_id = self._format_user_id(self.user_id)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.icon_label = self._create_user_icon()
        self.id_label = self._create_id_text_label(display_id)
        self.arrow_label = self._create_dropdown_arrow()

        layout.addWidget(self.arrow_label)
        layout.addWidget(self.id_label)
        layout.addWidget(self.icon_label)

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(22)

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
        self._popup = _DropdownPopup()

        # Menu items: (icon_name, translation_key, signal)
        self._menu_items_config = [
            ("language", "navbar.menu.change_language", self.language_change_requested),
            ("fluent", "navbar.menu.sync_data", self.sync_requested),
            ("lock", "navbar.menu.change_password", self.password_change_requested),
            ("safe", "navbar.menu.security_policies", self.security_settings_requested),
            ("data", "navbar.menu.data_management", self.data_management_requested),
        ]

        self._menu_item_widgets = []

        # Features disabled for client build
        _disabled_keys = {
            "navbar.menu.change_language",
            "navbar.menu.change_password",
            "navbar.menu.security_policies",
        }

        for icon_name, tr_key, signal in self._menu_items_config:
            item = _MenuItem(icon_name, tr(tr_key))
            if tr_key in _disabled_keys:
                item.setCursor(Qt.ForbiddenCursor)
                item.setToolTip("هذه الميزة غير متاحة حالياً")
                from PyQt5.QtWidgets import QGraphicsOpacityEffect
                opacity_effect = QGraphicsOpacityEffect()
                opacity_effect.setOpacity(0.5)
                item.setGraphicsEffect(opacity_effect)
            else:
                item.clicked.connect(signal.emit)
            self._popup.add_item(item)
            self._menu_item_widgets.append((item, tr_key))

        self._popup.add_separator()

        # Logout (after separator)
        self._logout_item = _MenuItem("logout", tr("navbar.menu.logout"))
        self._logout_item.clicked.connect(self.logout_requested.emit)
        self._popup.add_item(self._logout_item)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._show_menu()
        super().mousePressEvent(event)

    def _show_menu(self):
        """Show dropdown popup below the badge with arrow pointing to center."""
        badge_center = self.mapToGlobal(QPoint(self.width() // 2, self.height()))
        popup_w = self._popup.width()

        # Position popup so arrow points to badge center
        popup_x = badge_center.x() - popup_w // 2
        popup_y = badge_center.y() + 2

        # Arrow should be at center of popup
        self._popup.set_arrow_x(popup_w // 2)
        self._popup.move(popup_x, popup_y)
        self._popup.show()

    def update_language(self, is_arabic: bool):
        """Update menu item texts when language changes."""
        for item, tr_key in self._menu_item_widgets:
            item.set_text(tr(tr_key))
        self._logout_item.set_text(tr("navbar.menu.logout"))

    def set_user_id(self, user_id):
        self.user_id = user_id
        display_id = self._format_user_id(user_id)
        if hasattr(self, 'id_label'):
            self.id_label.setText(f"ID {display_id}")
