# -*- coding: utf-8 -*-
"""
Administration page for users, roles, and vocabularies.
Implements UC-015: User & Role Administration
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableView, QTabWidget, QFrame, QDialog,
    QFormLayout, QLineEdit, QCheckBox, QAbstractItemView,
    QGraphicsDropShadowEffect, QMessageBox, QHeaderView,
    QTableWidget, QTableWidgetItem, QFileDialog, QSpinBox,
    QScrollArea, QGroupBox, QSplitter
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor

from app.config import Config, Roles, Vocabularies
from repositories.database import Database
from repositories.user_repository import UserRepository
from repositories.vocabulary_repository import VocabularyRepository, VocabularyTerm
from services.security_service import SecurityService, SecuritySettings
from models.user import User
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class UsersTableModel(QAbstractTableModel):
    """Table model for users (UC-009 S03)."""

    def __init__(self):
        super().__init__()
        self._users = []
        self._headers = ["اسم المستخدم", "الاسم الكامل", "الدور", "البريد", "الحالة"]

    def rowCount(self, parent=None):
        return len(self._users)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._users):
            return None

        user = self._users[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return user.username
            elif col == 1:
                return user.full_name_ar or user.full_name
            elif col == 2:
                return Roles.get_display_name(user.role, arabic=True)
            elif col == 3:
                return user.email or "-"
            elif col == 4:
                # Show locked/active/disabled status (UC-009 S03)
                if user.is_locked:
                    return "مقفل"
                elif user.is_active:
                    return "نشط"
                else:
                    return "معطل"
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            if col == 4:
                if user.is_locked:
                    return QColor("#FEF3C7")  # Yellow for locked
                elif user.is_active:
                    return QColor("#D1FAE5")  # Green for active
                else:
                    return QColor("#FEE2E2")  # Red for disabled

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section] if section < len(self._headers) else ""
        return None

    def set_users(self, users: list):
        self.beginResetModel()
        self._users = users
        self.endResetModel()

    def get_user(self, row: int):
        if 0 <= row < len(self._users):
            return self._users[row]
        return None


class UserDialog(QDialog):
    """Dialog for creating/editing a user."""

    def __init__(self, i18n: I18n, user: User = None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.user = user

        self.setWindowTitle("تعديل المستخدم" if user else "إضافة مستخدم جديد")
        self.setMinimumWidth(450)
        self._setup_ui()

        if user:
            self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        self.username = QLineEdit()
        self.username.setPlaceholderText("اسم المستخدم")
        if self.user:
            self.username.setEnabled(False)
        form.addRow("اسم المستخدم:", self.username)

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("الاسم الكامل بالعربية")
        form.addRow("الاسم الكامل:", self.full_name)

        self.email = QLineEdit()
        self.email.setPlaceholderText("example@unhabitat.org")
        form.addRow("البريد الإلكتروني:", self.email)

        self.role_combo = QComboBox()
        roles = [
            (Roles.ADMIN, "مدير النظام"),
            (Roles.DATA_MANAGER, "مدير البيانات"),
            (Roles.OFFICE_CLERK, "موظف المكتب"),
            (Roles.FIELD_SUPERVISOR, "مشرف ميداني"),
            (Roles.ANALYST, "محلل"),
        ]
        for code, name in roles:
            self.role_combo.addItem(name, code)
        form.addRow("الدور:", self.role_combo)

        self.is_active = QCheckBox("مستخدم نشط")
        self.is_active.setChecked(True)
        form.addRow("", self.is_active)

        if not self.user:
            self.password = QLineEdit()
            self.password.setEchoMode(QLineEdit.Password)
            self.password.setPlaceholderText("كلمة المرور")
            form.addRow("كلمة المرور:", self.password)

            self.password_confirm = QLineEdit()
            self.password_confirm.setEchoMode(QLineEdit.Password)
            self.password_confirm.setPlaceholderText("تأكيد كلمة المرور")
            form.addRow("تأكيد كلمة المرور:", self.password_confirm)

        layout.addLayout(form)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {Config.ERROR_COLOR};")
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("حفظ")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate_data(self):
        if not self.user:
            return

        self.username.setText(self.user.username)
        self.full_name.setText(self.user.full_name_ar or self.user.full_name)
        self.email.setText(self.user.email or "")

        idx = self.role_combo.findData(self.user.role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)

        self.is_active.setChecked(self.user.is_active)

    def _on_save(self):
        errors = []

        if not self.username.text().strip():
            errors.append("اسم المستخدم مطلوب")

        if not self.full_name.text().strip():
            errors.append("الاسم الكامل مطلوب")

        if not self.user:  # New user - validate password
            if not hasattr(self, 'password') or not self.password.text():
                errors.append("كلمة المرور مطلوبة")
            elif self.password.text() != self.password_confirm.text():
                errors.append("كلمتا المرور غير متطابقتين")
            elif len(self.password.text()) < 6:
                errors.append("كلمة المرور يجب أن تكون 6 أحرف على الأقل")

        if errors:
            self.error_label.setText(" | ".join(errors))
            return

        self.accept()

    def get_data(self) -> dict:
        data = {
            "username": self.username.text().strip(),
            "full_name": self.full_name.text().strip(),
            "full_name_ar": self.full_name.text().strip(),
            "email": self.email.text().strip() or None,
            "role": self.role_combo.currentData(),
            "is_active": self.is_active.isChecked(),
        }

        if not self.user and hasattr(self, 'password'):
            data["password"] = self.password.text()

        return data


class VocabularyTermDialog(QDialog):
    """Dialog for creating/editing a vocabulary term."""

    def __init__(self, vocabulary_name: str, term: VocabularyTerm = None, parent=None):
        super().__init__(parent)
        self.vocabulary_name = vocabulary_name
        self.term = term

        self.setWindowTitle("تعديل المصطلح" if term else "إضافة مصطلح جديد")
        self.setMinimumWidth(450)
        self._setup_ui()

        if term:
            self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("الرمز (مثال: residential)")
        if self.term:
            self.code_edit.setEnabled(False)
        form.addRow("الرمز:", self.code_edit)

        self.label_en_edit = QLineEdit()
        self.label_en_edit.setPlaceholderText("English label")
        form.addRow("التسمية (إنجليزي):", self.label_en_edit)

        self.label_ar_edit = QLineEdit()
        self.label_ar_edit.setPlaceholderText("التسمية بالعربية")
        form.addRow("التسمية (عربي):", self.label_ar_edit)

        self.is_active = QCheckBox("مصطلح نشط")
        self.is_active.setChecked(True)
        form.addRow("", self.is_active)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {Config.ERROR_COLOR};")
        layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("حفظ")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate_data(self):
        if not self.term:
            return
        self.code_edit.setText(self.term.term_code)
        self.label_en_edit.setText(self.term.term_label or "")
        self.label_ar_edit.setText(self.term.term_label_ar or "")
        self.is_active.setChecked(self.term.status == "active")

    def _on_save(self):
        if not self.code_edit.text().strip():
            self.error_label.setText("الرمز مطلوب")
            return
        if not self.label_ar_edit.text().strip():
            self.error_label.setText("التسمية العربية مطلوبة")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "term_code": self.code_edit.text().strip(),
            "term_label": self.label_en_edit.text().strip() or self.code_edit.text().strip(),
            "term_label_ar": self.label_ar_edit.text().strip(),
            "status": "active" if self.is_active.isChecked() else "deprecated",
        }


class AdminPage(QWidget):
    """Administration page."""

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.user_repo = UserRepository(db)
        self.vocab_repo = VocabularyRepository(db)
        self.security_service = SecurityService(db)
        self.current_vocabulary = "building_type"

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        title = QLabel(self.i18n.t("admin"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(title)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: white;
                border-radius: 12px;
                border: none;
            }}
            QTabBar::tab {{
                background-color: #F1F5F9;
                color: {Config.TEXT_LIGHT};
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: white;
                color: {Config.PRIMARY_COLOR};
                font-weight: 600;
            }}
        """)

        # Users tab
        users_widget = self._create_users_tab()
        tabs.addTab(users_widget, "المستخدمون")

        # Vocabularies tab
        vocab_widget = self._create_vocab_tab()
        tabs.addTab(vocab_widget, "القوائم المنسدلة")

        # System tab
        system_widget = self._create_system_tab()
        tabs.addTab(system_widget, "إعدادات النظام")

        layout.addWidget(tabs)

    def _create_users_tab(self) -> QWidget:
        """Create users management tab (UC-009 S02-S05)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with actions
        header = QHBoxLayout()

        # Action buttons for selected user (UC-009 S04, S05)
        self.lock_user_btn = QPushButton("قفل الحساب")
        self.lock_user_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.WARNING_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
        """)
        self.lock_user_btn.clicked.connect(self._on_lock_user)
        self.lock_user_btn.setEnabled(False)
        header.addWidget(self.lock_user_btn)

        self.unlock_user_btn = QPushButton("إلغاء القفل")
        self.unlock_user_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
        """)
        self.unlock_user_btn.clicked.connect(self._on_unlock_user)
        self.unlock_user_btn.setEnabled(False)
        header.addWidget(self.unlock_user_btn)

        self.deactivate_user_btn = QPushButton("تعطيل")
        self.deactivate_user_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.ERROR_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
        """)
        self.deactivate_user_btn.clicked.connect(self._on_deactivate_user)
        self.deactivate_user_btn.setEnabled(False)
        header.addWidget(self.deactivate_user_btn)

        header.addStretch()

        add_btn = QPushButton("+ إضافة مستخدم")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        add_btn.clicked.connect(self._on_add_user)
        header.addWidget(add_btn)

        layout.addLayout(header)

        # Table
        self.users_table = QTableView()
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.users_table.setShowGrid(False)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
            }}
            QTableView::item {{
                padding: 10px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 10px 8px;
                border: none;
            }}
        """)
        self.users_table.doubleClicked.connect(self._on_user_double_click)

        self.users_model = UsersTableModel()
        self.users_table.setModel(self.users_model)

        # Connect selection changed to update action buttons (UC-009 S03)
        selection_model = self.users_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_user_selection_changed)

        layout.addWidget(self.users_table)

        # Roles info section (UC-009 S06 - read-only display)
        roles_group = QGroupBox("الأدوار المتاحة")
        roles_group.setStyleSheet("""
            QGroupBox { font-weight: 600; border: 1px solid #E5E7EB; border-radius: 8px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        roles_layout = QVBoxLayout(roles_group)
        roles_layout.setSpacing(8)

        roles_info = [
            ("مدير النظام", "System Administrator", "صلاحيات كاملة لإدارة النظام والمستخدمين"),
            ("مدير البيانات", "Data Manager", "إدارة المباني والوحدات والمطالبات"),
            ("موظف المكتب", "Office Clerk", "تسجيل المطالبات وإدارة الملفات"),
            ("مشرف ميداني", "Field Supervisor", "الإشراف على فرق الميدان"),
            ("محلل", "Analyst", "عرض التقارير والإحصائيات فقط"),
        ]

        for ar_name, en_name, desc in roles_info:
            role_label = QLabel(f"<b>{ar_name}</b> ({en_name}): {desc}")
            role_label.setWordWrap(True)
            role_label.setStyleSheet("padding: 4px;")
            roles_layout.addWidget(role_label)

        layout.addWidget(roles_group)

        return widget

    def _create_vocab_tab(self) -> QWidget:
        """Create vocabularies management tab with full CRUD (UC-010)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        info = QLabel("إدارة القوائم المنسدلة (أنواع المباني، حالات المطالبات، إلخ)")
        info.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(info)

        # Vocabulary selector and actions
        header_layout = QHBoxLayout()

        self.vocab_combo = QComboBox()
        self.vocab_combo.addItem("أنواع المباني", "building_type")
        self.vocab_combo.addItem("حالات المباني", "building_status")
        self.vocab_combo.addItem("أنواع الوحدات", "unit_type")
        self.vocab_combo.addItem("أنواع العلاقات", "relation_type")
        self.vocab_combo.addItem("حالات المطالبات", "case_status")
        self.vocab_combo.setMinimumWidth(200)
        self.vocab_combo.currentIndexChanged.connect(self._on_vocabulary_changed)
        header_layout.addWidget(self.vocab_combo)

        header_layout.addStretch()

        # Import button (UC-010 S04)
        import_btn = QPushButton("استيراد من ملف")
        import_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
        """)
        import_btn.clicked.connect(self._on_import_vocab)
        header_layout.addWidget(import_btn)

        # Export button (UC-010 S09)
        export_btn = QPushButton("تصدير")
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.WARNING_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
        """)
        export_btn.clicked.connect(self._on_export_vocab)
        header_layout.addWidget(export_btn)

        # Add term button (UC-010 S05)
        add_btn = QPushButton("+ إضافة مصطلح")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        add_btn.clicked.connect(self._on_add_term)
        header_layout.addWidget(add_btn)

        layout.addLayout(header_layout)

        # Vocabulary terms table
        self.vocab_table = QTableWidget()
        self.vocab_table.setColumnCount(5)
        self.vocab_table.setHorizontalHeaderLabels(["الرمز", "التسمية (إنجليزي)", "التسمية (عربي)", "الحالة", "إجراءات"])
        self.vocab_table.horizontalHeader().setStretchLastSection(True)
        self.vocab_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vocab_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.vocab_table.verticalHeader().setVisible(False)
        self.vocab_table.setAlternatingRowColors(True)
        self.vocab_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: none;
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 10px 8px;
                border: none;
            }}
        """)
        layout.addWidget(self.vocab_table)

        # Show deprecated checkbox
        show_deprecated = QCheckBox("إظهار المصطلحات المتقادمة")
        show_deprecated.stateChanged.connect(self._on_show_deprecated_changed)
        self.show_deprecated = show_deprecated
        layout.addWidget(show_deprecated)

        return widget

    def _on_vocabulary_changed(self, index):
        """Handle vocabulary selection change."""
        self.current_vocabulary = self.vocab_combo.currentData()
        self._load_vocab_terms()

    def _load_vocab_terms(self):
        """Load vocabulary terms into table."""
        include_deprecated = self.show_deprecated.isChecked() if hasattr(self, 'show_deprecated') else False
        terms = self.vocab_repo.get_terms(self.current_vocabulary, include_deprecated=include_deprecated)

        self.vocab_table.setRowCount(len(terms))
        for i, term in enumerate(terms):
            self.vocab_table.setItem(i, 0, QTableWidgetItem(term.term_code))
            self.vocab_table.setItem(i, 1, QTableWidgetItem(term.term_label or ""))
            self.vocab_table.setItem(i, 2, QTableWidgetItem(term.term_label_ar or ""))

            status_item = QTableWidgetItem("نشط" if term.status == "active" else "متقادم")
            if term.status != "active":
                status_item.setBackground(QColor("#FEE2E2"))
            self.vocab_table.setItem(i, 3, status_item)

            # Actions cell with buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            actions_layout.setSpacing(4)

            edit_btn = QPushButton("تعديل")
            edit_btn.setStyleSheet(f"background-color: {Config.PRIMARY_COLOR}; color: white; padding: 4px 8px; border-radius: 4px;")
            edit_btn.clicked.connect(lambda checked, t=term: self._on_edit_term(t))
            actions_layout.addWidget(edit_btn)

            if term.status == "active":
                deprecate_btn = QPushButton("إيقاف")
                deprecate_btn.setStyleSheet(f"background-color: {Config.WARNING_COLOR}; color: white; padding: 4px 8px; border-radius: 4px;")
                deprecate_btn.clicked.connect(lambda checked, t=term: self._on_deprecate_term(t))
                actions_layout.addWidget(deprecate_btn)
            else:
                activate_btn = QPushButton("تفعيل")
                activate_btn.setStyleSheet(f"background-color: {Config.SUCCESS_COLOR}; color: white; padding: 4px 8px; border-radius: 4px;")
                activate_btn.clicked.connect(lambda checked, t=term: self._on_activate_term(t))
                actions_layout.addWidget(activate_btn)

            self.vocab_table.setCellWidget(i, 4, actions_widget)

    def _on_show_deprecated_changed(self, state):
        """Handle show deprecated checkbox change."""
        self._load_vocab_terms()

    def _on_add_term(self):
        """Add a new vocabulary term."""
        dialog = VocabularyTermDialog(self.current_vocabulary, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            term = VocabularyTerm(
                vocabulary_name=self.current_vocabulary,
                term_code=data["term_code"],
                term_label=data["term_label"],
                term_label_ar=data["term_label_ar"],
                status=data["status"]
            )
            try:
                self.vocab_repo.create_term(term)
                Toast.show(self, "تم إضافة المصطلح بنجاح", Toast.SUCCESS)
                self._load_vocab_terms()
            except ValueError as e:
                Toast.show(self, str(e), Toast.ERROR)
            except Exception as e:
                logger.error(f"Failed to create term: {e}")
                Toast.show(self, f"فشل في إضافة المصطلح: {str(e)}", Toast.ERROR)

    def _on_edit_term(self, term: VocabularyTerm):
        """Edit an existing vocabulary term."""
        dialog = VocabularyTermDialog(self.current_vocabulary, term=term, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            term.term_label = data["term_label"]
            term.term_label_ar = data["term_label_ar"]
            term.status = data["status"]
            try:
                self.vocab_repo.update_term(term)
                Toast.show(self, "تم تحديث المصطلح بنجاح", Toast.SUCCESS)
                self._load_vocab_terms()
            except Exception as e:
                logger.error(f"Failed to update term: {e}")
                Toast.show(self, f"فشل في تحديث المصطلح: {str(e)}", Toast.ERROR)

    def _on_deprecate_term(self, term: VocabularyTerm):
        """Deprecate a vocabulary term."""
        reply = QMessageBox.question(
            self,
            "تأكيد الإيقاف",
            f"هل تريد إيقاف المصطلح '{term.term_label_ar}'؟\nسيظل المصطلح موجوداً ولكن لن يظهر في القوائم الجديدة.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.vocab_repo.deprecate_term(term.term_id)
            Toast.show(self, "تم إيقاف المصطلح", Toast.SUCCESS)
            self._load_vocab_terms()

    def _on_activate_term(self, term: VocabularyTerm):
        """Activate a deprecated vocabulary term."""
        self.vocab_repo.activate_term(term.term_id)
        Toast.show(self, "تم تفعيل المصطلح", Toast.SUCCESS)
        self._load_vocab_terms()

    def _on_import_vocab(self):
        """Import vocabulary terms from file (UC-010 S04)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "استيراد القائمة المنسدلة",
            "",
            "CSV Files (*.csv);;JSON Files (*.json);;All Files (*)"
        )
        if not file_path:
            return

        try:
            import json
            import csv

            terms = []
            if file_path.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    terms = json.load(f)
            elif file_path.endswith(".csv"):
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    terms = list(reader)
            else:
                Toast.show(self, "نوع الملف غير مدعوم", Toast.ERROR)
                return

            count = self.vocab_repo.import_vocabulary(self.current_vocabulary, terms)
            Toast.show(self, f"تم استيراد {count} مصطلح", Toast.SUCCESS)
            self._load_vocab_terms()

        except Exception as e:
            logger.error(f"Import failed: {e}")
            Toast.show(self, f"فشل في الاستيراد: {str(e)}", Toast.ERROR)

    def _on_export_vocab(self):
        """Export vocabulary terms to file (UC-010 S09)."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "تصدير القائمة المنسدلة",
            f"{self.current_vocabulary}.json",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            import json
            import csv

            terms = self.vocab_repo.export_vocabulary(self.current_vocabulary)

            if file_path.endswith(".json"):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(terms, f, ensure_ascii=False, indent=2)
            elif file_path.endswith(".csv"):
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    if terms:
                        writer = csv.DictWriter(f, fieldnames=terms[0].keys())
                        writer.writeheader()
                        writer.writerows(terms)

            Toast.show(self, f"تم تصدير {len(terms)} مصطلح", Toast.SUCCESS)

        except Exception as e:
            logger.error(f"Export failed: {e}")
            Toast.show(self, f"فشل في التصدير: {str(e)}", Toast.ERROR)

    def _create_system_tab(self) -> QWidget:
        """Create system settings tab with security and audit (UC-011)."""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Splitter for security settings and audit log
        splitter = QSplitter(Qt.Horizontal)

        # Left: Security Settings
        security_widget = self._create_security_settings_widget()
        splitter.addWidget(security_widget)

        # Right: Audit Log
        audit_widget = self._create_audit_log_widget()
        splitter.addWidget(audit_widget)

        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)

        return widget

    def _create_security_settings_widget(self) -> QWidget:
        """Create security settings panel (UC-011 S03-S05)."""
        widget = QGroupBox("إعدادات الأمان")
        widget.setStyleSheet("""
            QGroupBox { font-weight: 600; border: 1px solid #E5E7EB; border-radius: 8px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        layout = QFormLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Password settings (UC-011 S03)
        pwd_label = QLabel("سياسة كلمة المرور:")
        pwd_label.setStyleSheet("font-weight: 600; margin-top: 10px;")
        layout.addRow(pwd_label)

        self.password_min_length = QSpinBox()
        self.password_min_length.setRange(6, 32)
        self.password_min_length.setValue(8)
        layout.addRow("الحد الأدنى للطول:", self.password_min_length)

        self.require_uppercase = QCheckBox("يتطلب حرف كبير")
        self.require_uppercase.setChecked(True)
        layout.addRow("", self.require_uppercase)

        self.require_lowercase = QCheckBox("يتطلب حرف صغير")
        self.require_lowercase.setChecked(True)
        layout.addRow("", self.require_lowercase)

        self.require_digit = QCheckBox("يتطلب رقم")
        self.require_digit.setChecked(True)
        layout.addRow("", self.require_digit)

        self.require_symbol = QCheckBox("يتطلب رمز خاص")
        layout.addRow("", self.require_symbol)

        self.password_expiry = QSpinBox()
        self.password_expiry.setRange(0, 365)
        self.password_expiry.setValue(90)
        self.password_expiry.setSuffix(" يوم")
        layout.addRow("انتهاء كلمة المرور:", self.password_expiry)

        self.password_history = QSpinBox()
        self.password_history.setRange(0, 24)
        self.password_history.setValue(5)
        layout.addRow("سجل كلمات المرور السابقة:", self.password_history)

        # Session settings (UC-011 S04)
        session_label = QLabel("إعدادات الجلسة:")
        session_label.setStyleSheet("font-weight: 600; margin-top: 10px;")
        layout.addRow(session_label)

        self.session_timeout = QSpinBox()
        self.session_timeout.setRange(5, 480)
        self.session_timeout.setValue(30)
        self.session_timeout.setSuffix(" دقيقة")
        layout.addRow("مهلة الجلسة:", self.session_timeout)

        self.max_login_attempts = QSpinBox()
        self.max_login_attempts.setRange(1, 20)
        self.max_login_attempts.setValue(5)
        layout.addRow("المحاولات الفاشلة المسموحة:", self.max_login_attempts)

        self.lockout_duration = QSpinBox()
        self.lockout_duration.setRange(1, 1440)
        self.lockout_duration.setValue(15)
        self.lockout_duration.setSuffix(" دقيقة")
        layout.addRow("مدة قفل الحساب:", self.lockout_duration)

        # Save button
        save_btn = QPushButton("حفظ الإعدادات")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                margin-top: 16px;
            }}
        """)
        save_btn.clicked.connect(self._on_save_security_settings)
        layout.addRow("", save_btn)

        scroll.setWidget(content)

        main_layout = QVBoxLayout(widget)
        main_layout.addWidget(scroll)

        return widget

    def _create_audit_log_widget(self) -> QWidget:
        """Create audit log viewer panel (UC-011 S08)."""
        widget = QGroupBox("سجل المراجعة")
        widget.setStyleSheet("""
            QGroupBox { font-weight: 600; border: 1px solid #E5E7EB; border-radius: 8px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filters
        filter_layout = QHBoxLayout()

        self.audit_action_filter = QComboBox()
        self.audit_action_filter.addItem("كل الإجراءات", None)
        self.audit_action_filter.setMinimumWidth(150)
        filter_layout.addWidget(self.audit_action_filter)

        refresh_btn = QPushButton("تحديث")
        refresh_btn.clicked.connect(self._load_audit_logs)
        filter_layout.addWidget(refresh_btn)

        filter_layout.addStretch()

        export_btn = QPushButton("تصدير السجل")
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.WARNING_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
            }}
        """)
        export_btn.clicked.connect(self._on_export_audit_log)
        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # Audit log table
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(5)
        self.audit_table.setHorizontalHeaderLabels(["التاريخ", "المستخدم", "الإجراء", "الكيان", "التفاصيل"])
        self.audit_table.horizontalHeader().setStretchLastSection(True)
        self.audit_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.audit_table.verticalHeader().setVisible(False)
        self.audit_table.setAlternatingRowColors(True)
        self.audit_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }}
            QTableWidget::item {{
                padding: 6px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 8px;
                border: none;
            }}
        """)
        layout.addWidget(self.audit_table)

        # Count label
        self.audit_count_label = QLabel("إجمالي السجلات: 0")
        self.audit_count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.audit_count_label)

        return widget

    def _load_security_settings(self):
        """Load current security settings."""
        settings = self.security_service.get_settings()

        self.password_min_length.setValue(settings.password_min_length)
        self.require_uppercase.setChecked(settings.password_require_uppercase)
        self.require_lowercase.setChecked(settings.password_require_lowercase)
        self.require_digit.setChecked(settings.password_require_digit)
        self.require_symbol.setChecked(settings.password_require_symbol)
        self.password_expiry.setValue(settings.password_expiry_days)
        self.password_history.setValue(settings.password_reuse_history)
        self.session_timeout.setValue(settings.session_timeout_minutes)
        self.max_login_attempts.setValue(settings.max_failed_login_attempts)
        self.lockout_duration.setValue(settings.account_lockout_duration_minutes)

    def _on_save_security_settings(self):
        """Save security settings (UC-011 S07)."""
        settings = SecuritySettings(
            password_min_length=self.password_min_length.value(),
            password_require_uppercase=self.require_uppercase.isChecked(),
            password_require_lowercase=self.require_lowercase.isChecked(),
            password_require_digit=self.require_digit.isChecked(),
            password_require_symbol=self.require_symbol.isChecked(),
            password_expiry_days=self.password_expiry.value(),
            password_reuse_history=self.password_history.value(),
            session_timeout_minutes=self.session_timeout.value(),
            max_failed_login_attempts=self.max_login_attempts.value(),
            account_lockout_duration_minutes=self.lockout_duration.value()
        )

        success, errors = self.security_service.update_settings(settings)

        if success:
            Toast.show(self, "تم حفظ إعدادات الأمان بنجاح", Toast.SUCCESS)
        else:
            QMessageBox.warning(self, "خطأ في التحقق", "\n".join(errors))

    def _load_audit_logs(self):
        """Load audit log entries."""
        action_filter = self.audit_action_filter.currentData()
        logs = self.security_service.get_audit_logs(limit=100, action=action_filter)

        self.audit_table.setRowCount(len(logs))
        for i, log in enumerate(logs):
            timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else "-"
            self.audit_table.setItem(i, 0, QTableWidgetItem(timestamp))
            self.audit_table.setItem(i, 1, QTableWidgetItem(log.username or log.user_id or "-"))
            self.audit_table.setItem(i, 2, QTableWidgetItem(log.action or "-"))
            entity = f"{log.entity_type}/{log.entity_id}" if log.entity_type else "-"
            self.audit_table.setItem(i, 3, QTableWidgetItem(entity))
            self.audit_table.setItem(i, 4, QTableWidgetItem(log.details or "-"))

        # Update count
        total = self.security_service.get_audit_log_count()
        self.audit_count_label.setText(f"إجمالي السجلات: {total}")

        # Update action filter options
        current = self.audit_action_filter.currentText()
        self.audit_action_filter.clear()
        self.audit_action_filter.addItem("كل الإجراءات", None)
        for action in self.security_service.get_action_types():
            self.audit_action_filter.addItem(action, action)

    def _on_export_audit_log(self):
        """Export audit log to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "تصدير سجل المراجعة",
            "audit_log.csv",
            "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            import csv
            logs = self.security_service.get_audit_logs(limit=10000)

            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "User", "Action", "Entity Type", "Entity ID", "Details"])
                for log in logs:
                    writer.writerow([
                        log.timestamp.isoformat() if log.timestamp else "",
                        log.username or log.user_id or "",
                        log.action or "",
                        log.entity_type or "",
                        log.entity_id or "",
                        log.details or ""
                    ])

            Toast.show(self, f"تم تصدير {len(logs)} سجل", Toast.SUCCESS)

        except Exception as e:
            logger.error(f"Export failed: {e}")
            Toast.show(self, f"فشل في التصدير: {str(e)}", Toast.ERROR)

    def refresh(self, data=None):
        """Refresh the page."""
        self._load_users()
        self._load_vocab_terms()
        self._load_security_settings()
        self._load_audit_logs()

    def _load_users(self):
        """Load users into table."""
        users = self.user_repo.get_all()
        self.users_model.set_users(users)

    def _on_add_user(self):
        """Add new user."""
        dialog = UserDialog(self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            user = User(
                username=data["username"],
                full_name=data["full_name"],
                full_name_ar=data["full_name_ar"],
                email=data["email"],
                role=data["role"],
                is_active=data["is_active"],
            )
            user.set_password(data["password"])

            try:
                self.user_repo.create(user)
                Toast.show(self, "تم إضافة المستخدم بنجاح", Toast.SUCCESS)
                self._load_users()
            except Exception as e:
                logger.error(f"Failed to create user: {e}")
                Toast.show(self, f"فشل في إضافة المستخدم: {str(e)}", Toast.ERROR)

    def _on_user_double_click(self, index):
        """Edit user on double click."""
        user = self.users_model.get_user(index.row())
        if user:
            dialog = UserDialog(self.i18n, user=user, parent=self)
            if dialog.exec_() == QDialog.Accepted:
                data = dialog.get_data()
                user.full_name = data["full_name"]
                user.full_name_ar = data["full_name_ar"]
                user.email = data["email"]
                user.role = data["role"]
                user.is_active = data["is_active"]

                try:
                    self.user_repo.update(user)
                    Toast.show(self, "تم تحديث المستخدم بنجاح", Toast.SUCCESS)
                    self._load_users()
                except Exception as e:
                    logger.error(f"Failed to update user: {e}")
                    Toast.show(self, f"فشل في تحديث المستخدم: {str(e)}", Toast.ERROR)

    def _on_user_selection_changed(self, selected, deselected):
        """Update action buttons based on selected user (UC-009 S03)."""
        indexes = self.users_table.selectionModel().selectedRows()
        if not indexes:
            self.lock_user_btn.setEnabled(False)
            self.unlock_user_btn.setEnabled(False)
            self.deactivate_user_btn.setEnabled(False)
            return

        user = self.users_model.get_user(indexes[0].row())
        if user:
            self.lock_user_btn.setEnabled(not user.is_locked and user.is_active)
            self.unlock_user_btn.setEnabled(user.is_locked)
            self.deactivate_user_btn.setEnabled(user.is_active)

    def _on_lock_user(self):
        """Lock selected user account (UC-009 S04)."""
        indexes = self.users_table.selectionModel().selectedRows()
        if not indexes:
            return

        user = self.users_model.get_user(indexes[0].row())
        if not user:
            return

        reply = QMessageBox.question(
            self,
            "تأكيد قفل الحساب",
            f"هل تريد قفل حساب المستخدم: {user.username}؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self.user_repo.lock_user(user.user_id)
            Toast.show(self, f"تم قفل حساب {user.username}", Toast.SUCCESS)
            self._load_users()
        except Exception as e:
            logger.error(f"Failed to lock user: {e}")
            Toast.show(self, f"فشل في قفل الحساب: {str(e)}", Toast.ERROR)

    def _on_unlock_user(self):
        """Unlock selected user account (UC-009 S04)."""
        indexes = self.users_table.selectionModel().selectedRows()
        if not indexes:
            return

        user = self.users_model.get_user(indexes[0].row())
        if not user:
            return

        try:
            self.user_repo.reset_failed_attempts(user.user_id)
            Toast.show(self, f"تم إلغاء قفل حساب {user.username}", Toast.SUCCESS)
            self._load_users()
        except Exception as e:
            logger.error(f"Failed to unlock user: {e}")
            Toast.show(self, f"فشل في إلغاء القفل: {str(e)}", Toast.ERROR)

    def _on_deactivate_user(self):
        """Deactivate selected user (UC-009 S04)."""
        indexes = self.users_table.selectionModel().selectedRows()
        if not indexes:
            return

        user = self.users_model.get_user(indexes[0].row())
        if not user:
            return

        reply = QMessageBox.question(
            self,
            "تأكيد تعطيل الحساب",
            f"هل تريد تعطيل حساب المستخدم: {user.username}؟\nلن يتمكن من تسجيل الدخول.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            user.is_active = False
            self.user_repo.update(user)
            Toast.show(self, f"تم تعطيل حساب {user.username}", Toast.SUCCESS)
            self._load_users()
        except Exception as e:
            logger.error(f"Failed to deactivate user: {e}")
            Toast.show(self, f"فشل في تعطيل الحساب: {str(e)}", Toast.ERROR)

    def _on_backup(self):
        """Create database backup."""
        Toast.show(self, "جاري إنشاء نسخة احتياطية...", Toast.INFO)
        # In production, this would copy the database file
        Toast.show(self, "تم إنشاء النسخة الاحتياطية بنجاح", Toast.SUCCESS)

    def update_language(self, is_arabic: bool):
        pass
