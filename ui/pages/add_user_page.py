# -*- coding: utf-8 -*-
"""
Add User Page — إضافة مستخدم جديد
Form page with user info fields + collapsible CRUD permissions.
Same detail-page pattern as unit_details_page.py (DRY).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QCheckBox, QGraphicsDropShadowEffect,
    QScrollArea, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor

from repositories.database import Database
from ui.components.input_field import InputField
from ui.components.rtl_combo import RtlCombo
from ui.components.toast import Toast
from ui.components.dialogs.password_dialog import PasswordDialog
from ui.components.icon import Icon
from ui.design_system import Colors, PageDimensions, ButtonDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

# Permission sections and actions
PERMISSION_SECTIONS = [
    ("claims", "المطالبات"),
    ("buildings", "المباني"),
    ("units", "الوحدات السكنية"),
    ("duplicates", "التكرارات"),
    ("user_management", "إدارة المستخدمين"),
]

PERMISSION_ACTIONS = [
    ("view", "عرض"),
    ("add", "اضافة"),
    ("edit", "تعديل"),
    ("delete", "حذف"),
]

ROLES = [
    ("-", "-"),
    ("admin", "مدير النظام"),
    ("data_manager", "مدير البيانات"),
    ("office_clerk", "موظف المكتب"),
    ("field_supervisor", "مشرف ميداني"),
    ("field_researcher", "باحث ميداني"),
    ("data_collector", "جامع بيانات"),
    ("analyst", "محلل"),
]

ROLE_PERMISSIONS = {
    "admin": {
        "claims": {"view": True, "add": True, "edit": True, "delete": True},
        "buildings": {"view": True, "add": True, "edit": True, "delete": True},
        "units": {"view": True, "add": True, "edit": True, "delete": True},
        "duplicates": {"view": True, "add": True, "edit": True, "delete": True},
        "user_management": {"view": True, "add": True, "edit": True, "delete": True},
    },
    "data_manager": {
        "claims": {"view": True, "add": True, "edit": True, "delete": True},
        "buildings": {"view": True, "add": True, "edit": True, "delete": True},
        "units": {"view": True, "add": True, "edit": True, "delete": True},
        "duplicates": {"view": True, "add": True, "edit": True, "delete": True},
        "user_management": {"view": True, "add": False, "edit": False, "delete": False},
    },
    "office_clerk": {
        "claims": {"view": True, "add": True, "edit": True, "delete": False},
        "buildings": {"view": True, "add": True, "edit": True, "delete": False},
        "units": {"view": True, "add": True, "edit": True, "delete": False},
        "duplicates": {"view": True, "add": False, "edit": False, "delete": False},
        "user_management": {"view": False, "add": False, "edit": False, "delete": False},
    },
    "field_supervisor": {
        "claims": {"view": True, "add": False, "edit": False, "delete": False},
        "buildings": {"view": True, "add": False, "edit": False, "delete": False},
        "units": {"view": True, "add": False, "edit": False, "delete": False},
        "duplicates": {"view": True, "add": False, "edit": False, "delete": False},
        "user_management": {"view": False, "add": False, "edit": False, "delete": False},
    },
    "field_researcher": {
        "claims": {"view": True, "add": True, "edit": True, "delete": False},
        "buildings": {"view": True, "add": True, "edit": True, "delete": False},
        "units": {"view": True, "add": True, "edit": True, "delete": False},
        "duplicates": {"view": True, "add": False, "edit": False, "delete": False},
        "user_management": {"view": False, "add": False, "edit": False, "delete": False},
    },
    "data_collector": {
        "claims": {"view": True, "add": True, "edit": False, "delete": False},
        "buildings": {"view": True, "add": True, "edit": False, "delete": False},
        "units": {"view": True, "add": True, "edit": False, "delete": False},
        "duplicates": {"view": False, "add": False, "edit": False, "delete": False},
        "user_management": {"view": False, "add": False, "edit": False, "delete": False},
    },
    "analyst": {
        "claims": {"view": True, "add": False, "edit": False, "delete": False},
        "buildings": {"view": True, "add": False, "edit": False, "delete": False},
        "units": {"view": True, "add": False, "edit": False, "delete": False},
        "duplicates": {"view": True, "add": False, "edit": False, "delete": False},
        "user_management": {"view": False, "add": False, "edit": False, "delete": False},
    },
}


class AddUserPage(QWidget):
    """Add new user form page with permissions accordion."""

    back_requested = pyqtSignal()
    save_requested = pyqtSignal(dict)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n

        self._permission_checkboxes = {}
        self._section_contents = {}
        self._section_arrows = {}

        self._mode = 'add'  # 'add', 'edit', 'view'
        self._editing_user = None

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(15)

        # Header row: title area (right) + save button (left)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # Title area
        title_area = QVBoxLayout()
        title_area.setSpacing(4)

        self.title_label = QLabel("إضافة مستخدم جديد")
        self.title_label.setFont(create_font(
            size=FontManager.SIZE_TITLE,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self.title_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        title_area.addWidget(self.title_label)

        self.breadcrumb_label = QLabel("إدارة المستخدمين  •  إضافة مستخدم جديد")
        self.breadcrumb_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        self.breadcrumb_label.setStyleSheet(
            f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;"
        )
        title_area.addWidget(self.breadcrumb_label)

        header_layout.addLayout(title_area)
        header_layout.addStretch()

        # Save button (DRY — same as wizard save button, 114×48)
        self.save_btn = QPushButton(" حفظ")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedSize(ButtonDimensions.SAVE_WIDTH, ButtonDimensions.SAVE_HEIGHT)

        save_icon = Icon.load_qicon("save")
        if save_icon:
            self.save_btn.setIcon(save_icon)
            self.save_btn.setIconSize(QSize(
                ButtonDimensions.SAVE_ICON_SIZE, ButtonDimensions.SAVE_ICON_SIZE
            ))

        self.save_btn.setFont(create_font(
            size=ButtonDimensions.SAVE_FONT_SIZE,
            weight=FontManager.WEIGHT_REGULAR,
        ))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                padding: {ButtonDimensions.SAVE_PADDING_V}px {ButtonDimensions.SAVE_PADDING_H}px;
                border-radius: {ButtonDimensions.SAVE_BORDER_RADIUS}px;
                font-family: 'IBM Plex Sans Arabic';
            }}
            QPushButton:hover {{
                background-color: {ButtonDimensions.PRIMARY_HOVER_BG};
            }}
        """)
        self.save_btn.clicked.connect(self._on_save)
        header_layout.addWidget(self.save_btn)

        layout.addLayout(header_layout)

        # Scroll area for form content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # White card containing form + permissions
        card = QFrame()
        card.setObjectName("addUserCard")
        card.setStyleSheet("""
            QFrame#addUserCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(20)

        # Form fields row
        fields_layout = QHBoxLayout()
        fields_layout.setSpacing(20)

        # Right field: المستخدم ID
        id_group = QVBoxLayout()
        id_group.setSpacing(6)
        id_label = QLabel("المستخدم ID")
        id_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        id_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent;")
        id_group.addWidget(id_label)

        self.user_id_input = InputField(placeholder="00000")
        self.user_id_input.setAlignment(Qt.AlignRight)
        self.user_id_input.setStyleSheet("""
            QLineEdit {
                background-color: #f0f7ff;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 10px 14px;
                min-height: 22px;
                color: #2C3E50;
            }
            QLineEdit:focus {
                border: 2px solid #3890DF;
                padding: 9px 13px;
            }
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)
        id_group.addWidget(self.user_id_input)
        fields_layout.addLayout(id_group, 1)

        # Left field: اسم الدور
        role_group = QVBoxLayout()
        role_group.setSpacing(6)
        role_label = QLabel("اسم الدور")
        role_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        role_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent;")
        role_group.addWidget(role_label)

        self.role_combo = RtlCombo()
        for role_id, role_label in ROLES:
            self.role_combo.addItem(role_label, role_id)
        self.role_combo.setFixedHeight(42)
        self.role_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 12px;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                background-color: #f0f7ff;
                font-size: 14px;
                font-weight: 600;
                color: #9CA3AF;
            }
            QComboBox:focus {
                border-color: #3890DF;
                border-width: 2px;
            }
            QComboBox::drop-down {
                subcontrol-origin: border;
                subcontrol-position: center right;
                width: 35px;
                border: none;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                font-size: 14px;
                background-color: white;
                selection-background-color: #3890DF;
                selection-color: white;
            }
        """)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        role_group.addWidget(self.role_combo)
        fields_layout.addLayout(role_group, 1)

        card_layout.addLayout(fields_layout)

        # Permissions section title
        perm_title = QLabel("الصلاحيات")
        perm_title.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        perm_title.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent;"
        )
        perm_title.setAlignment(Qt.AlignLeft)
        card_layout.addWidget(perm_title)

        # Permission sections (accordion)
        for i, (key, title) in enumerate(PERMISSION_SECTIONS):
            expanded = (i == 0)
            section = self._create_permission_section(key, title, expanded)
            card_layout.addWidget(section)

        card_layout.addStretch()
        content_layout.addWidget(card)
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _create_permission_section(self, key: str, title: str, expanded: bool = False) -> QFrame:
        """Create a collapsible permission section with 4 CRUD checkboxes."""
        section = QFrame()
        section.setObjectName(f"section_{key}")
        section.setStyleSheet(f"""
            QFrame#section_{key} {{
                background: transparent;
                border: none;
            }}
        """)
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Header (clickable)
        header = QFrame()
        header.setObjectName(f"sectionHeader_{key}")
        header.setCursor(Qt.PointingHandCursor)
        header.setFixedHeight(48)
        header.setStyleSheet(f"""
            QFrame#sectionHeader_{key} {{
                background-color: #f0f7ff;
                border: 1px solid #E1E8ED;
                border-radius: 20px;
            }}
            QFrame#sectionHeader_{key}:hover {{
                background-color: #E3EEF9;
            }}
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        # Title (first in RTL → goes right)
        title_label = QLabel(title)
        title_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        title_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Arrow (last in RTL → goes left)
        arrow_label = QLabel("∨" if expanded else "‹")
        arrow_label.setFont(create_font(
            size=FontManager.SIZE_SMALL,
            weight=FontManager.WEIGHT_SEMIBOLD,
        ))
        arrow_label.setStyleSheet("color: #637381; background: transparent; border: none;")
        arrow_label.setFixedWidth(20)
        arrow_label.setAlignment(Qt.AlignCenter)
        self._section_arrows[key] = arrow_label
        header_layout.addWidget(arrow_label)

        header.mousePressEvent = lambda e, k=key: self._toggle_section(k)
        section_layout.addWidget(header)

        # Content (4 checkboxes)
        content = QWidget()
        content.setObjectName(f"sectionContent_{key}")
        content.setStyleSheet(f"""
            QWidget#sectionContent_{key} {{
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }}
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 4, 16, 12)
        content_layout.setSpacing(6)

        self._permission_checkboxes[key] = {}

        for action_key, action_label in PERMISSION_ACTIONS:
            cb = QCheckBox(action_label)
            cb.setLayoutDirection(Qt.RightToLeft)
            cb.setFont(create_font(
                size=FontManager.SIZE_BODY,
                weight=FontManager.WEIGHT_REGULAR,
            ))
            cb.setStyleSheet(f"""
                QCheckBox {{
                    spacing: 10px;
                    color: {Colors.PAGE_TITLE};
                    background: transparent;
                    padding: 4px 0;
                }}
                QCheckBox::indicator {{
                    width: 20px;
                    height: 20px;
                    border-radius: 4px;
                    border: 2px solid #D1D5DB;
                    background-color: white;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {Colors.PRIMARY_BLUE};
                    border-color: {Colors.PRIMARY_BLUE};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {Colors.PRIMARY_BLUE};
                }}
            """)
            self._permission_checkboxes[key][action_key] = cb
            content_layout.addWidget(cb)

        content.setVisible(expanded)
        self._section_contents[key] = content
        section_layout.addWidget(content)

        return section

    def _on_role_changed(self, index):
        """Update permission checkboxes when role changes (RBAC)."""
        if self._mode == 'view':
            return
        role_key = self.role_combo.currentData() or ""
        role_perms = ROLE_PERMISSIONS.get(role_key, {})
        for key in self._permission_checkboxes:
            section_perms = role_perms.get(key, {})
            for action_key in self._permission_checkboxes[key]:
                cb = self._permission_checkboxes[key][action_key]
                cb.setChecked(section_perms.get(action_key, False))

    def _toggle_section(self, key: str):
        """Toggle permission section visibility."""
        content = self._section_contents.get(key)
        arrow = self._section_arrows.get(key)
        if not content or not arrow:
            return

        is_visible = content.isVisible()
        content.setVisible(not is_visible)
        arrow.setText("‹" if is_visible else "∨")

    def _collect_data(self) -> dict:
        """Collect form data."""
        permissions = {}
        for key, _ in PERMISSION_SECTIONS:
            section_perms = {}
            for action_key, _ in PERMISSION_ACTIONS:
                cb = self._permission_checkboxes.get(key, {}).get(action_key)
                section_perms[action_key] = cb.isChecked() if cb else False
            permissions[key] = section_perms

        return {
            "user_id": self.user_id_input.text().strip(),
            "role": self.role_combo.currentData() or "-",
            "permissions": permissions,
        }

    def _on_save(self):
        """Handle save button click."""
        data = self._collect_data()

        if not data["user_id"]:
            Toast.show_toast(self, "يرجى إدخال المستخدم ID", Toast.WARNING)
            return

        if data["role"] == "-":
            Toast.show_toast(self, "يرجى اختيار اسم الدور", Toast.WARNING)
            return

        if self._mode == 'edit':
            data["_editing_user_id"] = self._editing_user.get("user_id")
            data["_mode"] = "edit"
            logger.info(f"Update user requested: {data.get('user_id')}, role={data.get('role')}")
            self.save_requested.emit(data)
        else:
            password = PasswordDialog.get_password(self)
            if password is None:
                return
            data["password"] = password
            data["_mode"] = "add"
            logger.info(f"Save user requested: {data.get('user_id')}, role={data.get('role')}")
            self.save_requested.emit(data)

    def set_user_data(self, user_data: dict, mode: str = 'edit'):
        """Pre-fill form with existing user data for view/edit mode."""
        self._mode = mode
        self._editing_user = user_data

        if mode == 'view':
            self.title_label.setText("عرض بيانات المستخدم")
            self.breadcrumb_label.setText("إدارة المستخدمين  •  عرض بيانات المستخدم")
            self.save_btn.setVisible(False)
        elif mode == 'edit':
            self.title_label.setText("تعديل بيانات المستخدم")
            self.breadcrumb_label.setText("إدارة المستخدمين  •  تعديل بيانات المستخدم")
            self.save_btn.setVisible(True)

        self.user_id_input.setText(user_data.get("display_id", user_data.get("username", "")))
        self.user_id_input.setEnabled(False)

        role_key = user_data.get("role_key", user_data.get("role", ""))
        idx = self.role_combo.findData(role_key)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)
        self.role_combo.setEnabled(mode != 'view')

        role_perms = ROLE_PERMISSIONS.get(role_key, {})
        for key in self._permission_checkboxes:
            section_perms = role_perms.get(key, {})
            for action_key in self._permission_checkboxes[key]:
                cb = self._permission_checkboxes[key][action_key]
                cb.setChecked(section_perms.get(action_key, False))
                cb.setEnabled(mode != 'view')

    def refresh(self, data=None):
        """Reset form or load user data for view/edit."""
        if data and isinstance(data, dict) and data.get('_mode'):
            self.set_user_data(data, data['_mode'])
            return

        self._mode = 'add'
        self._editing_user = None
        self.title_label.setText("إضافة مستخدم جديد")
        self.breadcrumb_label.setText("إدارة المستخدمين  •  إضافة مستخدم جديد")
        self.save_btn.setVisible(True)
        self.user_id_input.setEnabled(True)
        self.user_id_input.clear()
        self.role_combo.setEnabled(True)
        self.role_combo.setCurrentIndex(0)

        for key, _ in PERMISSION_SECTIONS:
            for action_key, _ in PERMISSION_ACTIONS:
                cb = self._permission_checkboxes.get(key, {}).get(action_key)
                if cb:
                    cb.setChecked(False)
                    cb.setEnabled(True)

            content = self._section_contents.get(key)
            arrow = self._section_arrows.get(key)
            if content:
                content.setVisible(False)
            if arrow:
                arrow.setText("‹")

        first_key = PERMISSION_SECTIONS[0][0]
        first_content = self._section_contents.get(first_key)
        first_arrow = self._section_arrows.get(first_key)
        if first_content:
            first_content.setVisible(True)
        if first_arrow:
            first_arrow.setText("∨")

    def update_language(self, is_arabic: bool):
        pass
