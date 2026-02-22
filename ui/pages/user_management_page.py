# -*- coding: utf-8 -*-
"""
User Management Page — إدارة المستخدمين
Table-based user management with CRUD and filters.
Same pattern as units_page.py (DRY).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QAbstractItemView, QMenu, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QIcon, QFont, QPixmap

from app.config import Roles
from repositories.database import Database
from repositories.user_repository import UserRepository
from models.user import User
from ui.components.page_header import PageHeader
from ui.components.toggle_switch import ToggleSwitch
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.components.dialogs.password_dialog import PasswordDialog
from ui.style_manager import StyleManager, PageDimensions
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class UserManagementPage(QWidget):
    """User management page — table with CRUD, filters, pagination."""

    view_user = pyqtSignal(object)
    edit_user_signal = pyqtSignal(object)
    add_user_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.user_repo = UserRepository(db) if db else None

        self._all_users = []
        self._users = []
        self._current_page = 1
        self._rows_per_page = 11
        self._total_pages = 1
        self._active_filters = {
            'role': None,
            'status': None,
        }

        self._setup_ui()

    def _setup_ui(self):
        from ui.design_system import Colors
        from ui.font_utils import create_font, FontManager
        from pathlib import Path
        import sys

        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(15)

        # Header (DRY — PageHeader component)
        header = PageHeader(
            title="إدارة المستخدمين",
            show_add_button=True,
            button_text="إضافة مستخدم جديد",
            button_icon="icon",
        )
        header.add_clicked.connect(self._on_add_user)
        layout.addWidget(header)

        # Table card
        table_card = QFrame()
        table_card.setFixedHeight(708)
        table_card.setStyleSheet("background-color: white; border-radius: 16px;")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(0)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setRowCount(11)
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Filterable column icon
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent
        icon_path = base_path / "assets" / "images" / "down.png"

        headers = ["المستخدم ID", "الدور", "الصلاحية", ""]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            if i in (1, 2) and icon_path.exists():
                item.setIcon(QIcon(str(icon_path)))
            self.table.setHorizontalHeaderItem(i, item)

        # Styling (DRY — same as units_page)
        self.table.setStyleSheet("""
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
                background-color: #FAFBFC;
            }
            QHeaderView {
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                padding: 12px;
                padding-left: 30px;
                border: none;
                color: #637381;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }
            QHeaderView::section:hover {
                background-color: #EBEEF2;
            }
        """ + StyleManager.scrollbar())

        # Header config
        h_header = self.table.horizontalHeader()
        h_header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h_header.setFixedHeight(56)
        h_header.setStretchLastSection(True)
        h_header.setMouseTracking(True)
        h_header.sectionEntered.connect(self._on_header_hover)
        h_header.sectionClicked.connect(self._on_header_clicked)

        # Column widths
        h_header.setSectionResizeMode(0, QHeaderView.Fixed)
        h_header.resizeSection(0, 298)
        h_header.setSectionResizeMode(1, QHeaderView.Fixed)
        h_header.resizeSection(1, 298)
        h_header.setSectionResizeMode(2, QHeaderView.Fixed)
        h_header.resizeSection(2, 298)
        h_header.setSectionResizeMode(3, QHeaderView.Stretch)

        # Row heights
        v_header = self.table.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(52)

        # Events
        self.table.cellClicked.connect(self._on_cell_clicked)

        card_layout.addWidget(self.table)

        # Footer
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E1E8ED;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)
        footer_frame.setFixedHeight(58)

        footer = QHBoxLayout(footer_frame)
        footer.setContentsMargins(10, 10, 10, 10)

        # Navigation arrows
        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        nav_btn_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #EBEEF2; }
            QPushButton:disabled { color: #C1C7CD; }
        """
        self.prev_btn = QPushButton(">")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet(nav_btn_style)
        self.prev_btn.clicked.connect(self._on_prev_page)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("<")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet(nav_btn_style)
        self.next_btn.clicked.connect(self._on_next_page)
        nav_layout.addWidget(self.next_btn)

        footer.addWidget(nav_container)

        # Page counter
        self.page_label = QLabel("0-0 of 0")
        self.page_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent;")
        footer.addWidget(self.page_label)

        # Rows per page selector
        rows_container = QFrame()
        rows_container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QFrame:hover { background-color: #EBEEF2; }
        """)
        rows_container.setCursor(Qt.PointingHandCursor)
        rows_layout = QHBoxLayout(rows_container)
        rows_layout.setContentsMargins(4, 2, 4, 2)
        rows_layout.setSpacing(4)

        down_icon_label = QLabel()
        if icon_path.exists():
            down_pixmap = QPixmap(str(icon_path))
            if not down_pixmap.isNull():
                down_pixmap = down_pixmap.scaled(10, 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                down_icon_label.setPixmap(down_pixmap)
        down_icon_label.setStyleSheet("background: transparent; border: none;")
        rows_layout.addWidget(down_icon_label)

        self.rows_number = QLabel(str(self._rows_per_page))
        self.rows_number.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent; border: none;")
        rows_layout.addWidget(self.rows_number)

        rows_container.mousePressEvent = lambda e: self._show_page_selection_menu(rows_container)
        footer.addWidget(rows_container)

        rows_label = QLabel("Rows per page:")
        rows_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400; background: transparent;")
        footer.addWidget(rows_label)

        footer.addStretch()

        self.dense_toggle = ToggleSwitch("Dense", checked=True)
        self.dense_toggle.toggled.connect(self._on_dense_toggle)
        footer.addWidget(self.dense_toggle)

        card_layout.addWidget(footer_frame)
        layout.addWidget(table_card)

    # ── Data ──

    def refresh(self, data=None):
        logger.debug("Refreshing user management page")
        self._load_users()

    def _load_users(self):
        if self.user_repo:
            users = self.user_repo.get_all(limit=1000)
            self._all_users = [
                {
                    "user_id": u.user_id,
                    "username": u.username,
                    "display_id": str(int(u.user_id.replace('-', '')[:8], 16) % 900000 + 100000),
                    "full_name": u.full_name_ar or u.full_name or u.username,
                    "role": Roles.get_display_name(u.role, arabic=True),
                    "role_key": u.role,
                    "is_active": u.is_active,
                    "email": u.email or "",
                    "_user_obj": u,
                }
                for u in users
            ]
        else:
            self._all_users = []
        self._users = self._apply_filters(self._all_users)
        self._current_page = 1
        self._update_table()

    def _update_table(self):
        total = len(self._users)
        self._total_pages = max(1, (total + self._rows_per_page - 1) // self._rows_per_page)
        self._current_page = min(self._current_page, self._total_pages)

        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + self._rows_per_page, total)
        page_users = self._users[start_idx:end_idx]

        # Clear
        self.table.clearSpans()
        for row in range(self._rows_per_page):
            for col in range(4):
                self.table.setItem(row, col, QTableWidgetItem(""))

        if total == 0:
            self.table.setSpan(0, 0, self._rows_per_page, 4)
            empty_item = QTableWidgetItem("لا توجد بيانات مطابقة للفلتر المحدد")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setForeground(QColor("#9CA3AF"))
            self.table.setItem(0, 0, empty_item)
            self.page_label.setText("0-0 of 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        for row, user in enumerate(page_users):
            # col 0: المستخدم ID (6-digit display ID from UUID)
            self.table.setItem(row, 0, QTableWidgetItem(user.get("display_id", "")))

            # col 1: الدور
            self.table.setItem(row, 1, QTableWidgetItem(user.get("role", "")))

            # col 2: الحالة
            status = "نشط" if user.get("is_active", True) else "معطل"
            status_item = QTableWidgetItem(status)
            if user.get("is_active", True):
                status_item.setForeground(QColor("#27AE60"))
            else:
                status_item.setForeground(QColor("#E74C3C"))
            self.table.setItem(row, 2, status_item)

            # col 3: ⋮
            dots_item = QTableWidgetItem("⋮")
            dots_item.setTextAlignment(Qt.AlignCenter)
            dots_font = QFont()
            dots_font.setPointSize(18)
            dots_font.setWeight(QFont.Bold)
            dots_item.setFont(dots_font)
            dots_item.setForeground(QColor("#637381"))
            self.table.setItem(row, 3, dots_item)

        # Update pagination
        if total > 0:
            self.page_label.setText(f"{start_idx + 1}-{end_idx} of {total}")
        else:
            self.page_label.setText("0-0 of 0")
        self.rows_number.setText(str(self._rows_per_page))
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

    # ── Pagination ──

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._update_table()

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._update_table()

    def _show_page_selection_menu(self, parent_widget):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                color: #637381;
                font-size: 10pt;
            }
            QMenu::item:selected {
                background-color: #E3F2FD;
                color: #3498db;
            }
        """)
        for size in [5, 10, 15, 25]:
            action = menu.addAction(str(size))
            if size == self._rows_per_page:
                action.setEnabled(False)
            else:
                action.triggered.connect(lambda checked, s=size: self._set_rows_per_page(s))
        menu.exec_(parent_widget.mapToGlobal(parent_widget.rect().bottomLeft()))

    def _set_rows_per_page(self, size):
        self._rows_per_page = size
        self.table.setRowCount(size)
        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(52 if self.dense_toggle.isChecked() else 68)
        self._current_page = 1
        self._update_table()

    def _on_dense_toggle(self, checked):
        row_height = 52 if checked else 68
        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(row_height)
        if checked:
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    # ── Row interactions ──

    def _on_cell_clicked(self, row: int, col: int):
        if col != 3:
            return
        item = self.table.item(row, 0)
        if not item or not item.text().strip():
            return
        start_idx = (self._current_page - 1) * self._rows_per_page
        user_idx = start_idx + row
        if user_idx >= len(self._users):
            return
        self._show_actions_menu(row, col, self._users[user_idx])

    def _show_actions_menu(self, row: int, col: int, user: dict):
        rect = self.table.visualItemRect(self.table.item(row, col))
        position = QPoint(rect.right() - 10, rect.bottom())

        menu = QMenu(self)
        menu.setFixedSize(200, 189)

        # عرض
        view_icon = Icon.load_qicon("eye-open", size=18)
        view_action = QAction("  عرض", self)
        if view_icon:
            view_action.setIcon(view_icon)
        view_action.triggered.connect(lambda: self._on_view_user(user))
        menu.addAction(view_action)

        # تعديل
        edit_icon = Icon.load_qicon("edit-01", size=18)
        edit_action = QAction("  تعديل", self)
        if edit_icon:
            edit_action.setIcon(edit_icon)
        edit_action.triggered.connect(lambda: self._on_edit_user(user))
        menu.addAction(edit_action)

        # تغيير كلمة المرور
        password_icon = Icon.load_qicon("lock", size=18)
        password_action = QAction("  تغيير كلمة المرور", self)
        if password_icon:
            password_action.setIcon(password_icon)
        password_action.triggered.connect(lambda: self._on_change_password(user))
        menu.addAction(password_action)

        # حذف
        delete_icon = Icon.load_qicon("delete", size=18)
        delete_action = QAction("  حذف", self)
        if delete_icon:
            delete_action.setIcon(delete_icon)
        delete_action.triggered.connect(lambda: self._on_delete_user(user))
        menu.addAction(delete_action)

        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 10px;
                border-radius: 4px;
                color: #212B36;
                font-size: 11pt;
                font-weight: 400;
            }
            QMenu::item:selected {
                background-color: #F6F6F7;
            }
        """)
        menu.exec_(self.table.viewport().mapToGlobal(position))

    # ── Header filter system ──

    def _on_header_hover(self, logical_index: int):
        header = self.table.horizontalHeader()
        if logical_index in (1, 2):
            header.setCursor(Qt.PointingHandCursor)
        else:
            header.setCursor(Qt.ArrowCursor)

    def _on_header_clicked(self, logical_index: int):
        if logical_index not in (1, 2):
            return
        self._show_filter_menu(logical_index)

    def _show_filter_menu(self, column_index: int):
        unique_values = set()
        filter_key = None

        if column_index == 1:
            filter_key = 'role'
            for u in self._all_users:
                role = u.get("role", "").strip()
                if role:
                    unique_values.add(role)
        elif column_index == 2:
            filter_key = 'status'
            unique_values = {"نشط", "معطل"}

        if not unique_values:
            return

        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 8px;
            }
            QMenu::item {
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 10pt;
                color: #637381;
            }
            QMenu::item:selected {
                background-color: #EFF6FF;
                color: #3890DF;
            }
        """)

        clear_action = QAction("عرض الكل", self)
        clear_action.triggered.connect(lambda: self._apply_filter(filter_key, None))
        menu.addAction(clear_action)
        menu.addSeparator()

        for value in sorted(unique_values):
            action = QAction(value, self)
            action.triggered.connect(lambda checked, v=value: self._apply_filter(filter_key, v))
            if self._active_filters.get(filter_key) == value:
                action.setCheckable(True)
                action.setChecked(True)
            menu.addAction(action)

        header = self.table.horizontalHeader()
        x_pos = header.sectionViewportPosition(column_index)
        y_pos = header.height()
        pos = self.table.mapToGlobal(QPoint(x_pos, y_pos))
        menu.exec_(pos)

    def _apply_filter(self, filter_key: str, filter_value):
        self._active_filters[filter_key] = filter_value
        self._current_page = 1
        self._users = self._apply_filters(self._all_users)
        self._update_table()

    def _apply_filters(self, users: list) -> list:
        filtered = users

        if self._active_filters.get('role'):
            target = self._active_filters['role']
            filtered = [u for u in filtered if u.get("role", "").strip() == target]

        if self._active_filters.get('status'):
            target = self._active_filters['status']
            if target == "نشط":
                filtered = [u for u in filtered if u.get("is_active", True)]
            elif target == "معطل":
                filtered = [u for u in filtered if not u.get("is_active", True)]

        return filtered

    # ── Actions ──

    def _on_add_user(self):
        self.add_user_requested.emit()

    def _on_view_user(self, user: dict):
        logger.info(f"View user: {user.get('user_id')}")
        self.view_user.emit(user)

    def _on_edit_user(self, user: dict):
        logger.info(f"Edit user: {user.get('user_id')}")
        self.edit_user_signal.emit(user)

    def _on_change_password(self, user: dict):
        logger.info(f"Change password for user: {user.get('user_id')}")
        new_password = PasswordDialog.get_password(self)
        if new_password and self.user_repo:
            user_obj = user.get("_user_obj")
            if user_obj:
                user_obj.set_password(new_password)
                self.user_repo.update(user_obj)
                logger.info(f"Password changed for user: {user.get('username')}")
                Toast.show_toast(self, "تم تغيير كلمة المرور بنجاح", Toast.SUCCESS)

    def _on_delete_user(self, user: dict):
        from PyQt5.QtWidgets import QMessageBox
        username = user.get("username", "")
        reply = QMessageBox.question(
            self, "تأكيد الحذف",
            f"هل أنت متأكد من حذف المستخدم: {user.get('full_name', username)}؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes and self.user_repo:
            self.user_repo.delete(user.get("user_id"))
            logger.info(f"Deleted user: {username}")
            Toast.show_toast(self, "تم حذف المستخدم بنجاح", Toast.SUCCESS)
            self._load_users()

    def update_language(self, is_arabic: bool):
        pass
