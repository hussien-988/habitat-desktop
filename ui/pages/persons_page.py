# -*- coding: utf-8 -*-
"""
Persons management page with search, CRUD, and validation.
Implements UC-003: Person Management
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox,
    QAbstractItemView, QGraphicsDropShadowEffect, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex
from PyQt5.QtGui import QColor

from app.config import Config, Vocabularies
from repositories.database import Database
from repositories.person_repository import PersonRepository
from models.person import Person
from services.validation_service import ValidationService
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonsTableModel(QAbstractTableModel):
    """Table model for persons."""

    def __init__(self, is_arabic: bool = True):
        super().__init__()
        self._persons = []
        self._is_arabic = is_arabic
        self._headers_en = ["Name", "Father Name", "National ID", "Gender", "Year of Birth", "Mobile"]
        self._headers_ar = ["الاسم", "اسم الأب", "الرقم الوطني", "الجنس", "سنة الميلاد", "الجوال"]

    def rowCount(self, parent=None):
        return len(self._persons)

    def columnCount(self, parent=None):
        return len(self._headers_en)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._persons):
            return None

        person = self._persons[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return person.full_name_ar if self._is_arabic else person.full_name
            elif col == 1:
                return person.father_name_ar if self._is_arabic else person.father_name
            elif col == 2:
                return person.national_id or "-"
            elif col == 3:
                return person.gender_display_ar if self._is_arabic else person.gender_display
            elif col == 4:
                return str(person.year_of_birth) if person.year_of_birth else "-"
            elif col == 5:
                return person.mobile_number or "-"
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = self._headers_ar if self._is_arabic else self._headers_en
            return headers[section] if section < len(headers) else ""
        return None

    def set_persons(self, persons: list):
        self.beginResetModel()
        self._persons = persons
        self.endResetModel()

    def get_person(self, row: int):
        if 0 <= row < len(self._persons):
            return self._persons[row]
        return None

    def set_language(self, is_arabic: bool):
        self._is_arabic = is_arabic
        self.layoutChanged.emit()


class PersonDialog(QDialog):
    """Dialog for creating/editing a person."""

    def __init__(self, db: Database, i18n: I18n, person: Person = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.person = person
        self.validation = ValidationService()

        self.setWindowTitle(i18n.t("edit_person") if person else i18n.t("add_person"))
        self.setMinimumWidth(550)
        self._setup_ui()

        if person:
            self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        # Arabic names
        self.first_name_ar = QLineEdit()
        self.first_name_ar.setPlaceholderText("الاسم الأول بالعربية")
        form.addRow("الاسم الأول:", self.first_name_ar)

        self.father_name_ar = QLineEdit()
        self.father_name_ar.setPlaceholderText("اسم الأب بالعربية")
        form.addRow("اسم الأب:", self.father_name_ar)

        self.mother_name_ar = QLineEdit()
        self.mother_name_ar.setPlaceholderText("اسم الأم بالعربية")
        form.addRow("اسم الأم:", self.mother_name_ar)

        self.last_name_ar = QLineEdit()
        self.last_name_ar.setPlaceholderText("اسم العائلة بالعربية")
        form.addRow("اسم العائلة:", self.last_name_ar)

        # Gender
        self.gender_combo = QComboBox()
        for code, en, ar in Vocabularies.GENDERS:
            self.gender_combo.addItem(ar, code)
        form.addRow("الجنس:", self.gender_combo)

        # Year of birth
        self.year_birth = QSpinBox()
        self.year_birth.setRange(1900, 2025)
        self.year_birth.setValue(1980)
        form.addRow("سنة الميلاد:", self.year_birth)

        # National ID (11 digits)
        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("11 رقم")
        self.national_id.setMaxLength(11)
        form.addRow("الرقم الوطني:", self.national_id)

        # Mobile
        self.mobile = QLineEdit()
        self.mobile.setPlaceholderText("+963 9XXXXXXXX")
        form.addRow("رقم الجوال:", self.mobile)

        # Contact person flag
        self.is_contact = QCheckBox("شخص الاتصال")
        form.addRow("", self.is_contact)

        layout.addLayout(form)

        # Validation error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {Config.ERROR_COLOR}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(self.i18n.t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.i18n.t("save"))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _populate_data(self):
        """Populate form with existing person data."""
        if not self.person:
            return

        self.first_name_ar.setText(self.person.first_name_ar)
        self.father_name_ar.setText(self.person.father_name_ar)
        self.mother_name_ar.setText(self.person.mother_name_ar)
        self.last_name_ar.setText(self.person.last_name_ar)

        idx = self.gender_combo.findData(self.person.gender)
        if idx >= 0:
            self.gender_combo.setCurrentIndex(idx)

        if self.person.year_of_birth:
            self.year_birth.setValue(self.person.year_of_birth)

        self.national_id.setText(self.person.national_id or "")
        self.mobile.setText(self.person.mobile_number or "")
        self.is_contact.setChecked(self.person.is_contact_person)

    def _on_save(self):
        """Validate and save."""
        errors = []

        # Validate required Arabic names
        if not self.first_name_ar.text().strip():
            errors.append("الاسم الأول مطلوب")
        if not self.father_name_ar.text().strip():
            errors.append("اسم الأب مطلوب")
        if not self.last_name_ar.text().strip():
            errors.append("اسم العائلة مطلوب")

        # Validate national ID (11 digits)
        nid = self.national_id.text().strip()
        if nid and (not nid.isdigit() or len(nid) != 11):
            errors.append("الرقم الوطني يجب أن يكون 11 رقم")

        if errors:
            self.error_label.setText(" | ".join(errors))
            return

        self.accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        return {
            "first_name_ar": self.first_name_ar.text().strip(),
            "first_name": self.first_name_ar.text().strip(),  # Fallback
            "father_name_ar": self.father_name_ar.text().strip(),
            "father_name": self.father_name_ar.text().strip(),
            "mother_name_ar": self.mother_name_ar.text().strip(),
            "mother_name": self.mother_name_ar.text().strip(),
            "last_name_ar": self.last_name_ar.text().strip(),
            "last_name": self.last_name_ar.text().strip(),
            "gender": self.gender_combo.currentData(),
            "year_of_birth": self.year_birth.value(),
            "national_id": self.national_id.text().strip() or None,
            "mobile_number": self.mobile.text().strip() or None,
            "is_contact_person": self.is_contact.isChecked(),
        }


class PersonsPage(QWidget):
    """Persons management page."""

    view_person = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.person_repo = PersonRepository(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel(self.i18n.t("persons"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Add person button
        add_btn = QPushButton("+ " + self.i18n.t("add_person"))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: {Config.FONT_SIZE}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #219A52;
            }}
        """)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_person)
        header_layout.addWidget(add_btn)

        layout.addLayout(header_layout)

        # Filters
        filters_frame = QFrame()
        filters_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        filters_frame.setGraphicsEffect(shadow)

        filters_layout = QHBoxLayout(filters_frame)
        filters_layout.setContentsMargins(24, 20, 24, 20)
        filters_layout.setSpacing(20)

        # Name search
        self.name_search = QLineEdit()
        self.name_search.setPlaceholderText("بحث بالاسم...")
        self.name_search.setMinimumWidth(200)
        self.name_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        self.name_search.textChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.name_search)

        # National ID search
        self.nid_search = QLineEdit()
        self.nid_search.setPlaceholderText("الرقم الوطني...")
        self.nid_search.setMaximumWidth(150)
        self.nid_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: #F8FAFC;
                border: 1px solid {Config.INPUT_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
            }}
        """)
        self.nid_search.textChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.nid_search)

        # Gender filter
        self.gender_combo = QComboBox()
        self.gender_combo.addItem(self.i18n.t("all"), "")
        for code, en, ar in Vocabularies.GENDERS:
            self.gender_combo.addItem(ar, code)
        self.gender_combo.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.gender_combo)

        filters_layout.addStretch()
        layout.addWidget(filters_frame)

        # Results count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.count_label)

        # Table
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 12px;")

        table_shadow = QGraphicsDropShadowEffect()
        table_shadow.setBlurRadius(20)
        table_shadow.setColor(QColor(0, 0, 0, 20))
        table_shadow.setOffset(0, 4)
        table_frame.setGraphicsEffect(table_shadow)

        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: none;
                border-radius: 12px;
            }}
            QTableView::item {{
                padding: 12px 8px;
                border-bottom: 1px solid #F1F5F9;
            }}
            QTableView::item:selected {{
                background-color: #EBF5FF;
                color: {Config.TEXT_COLOR};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)
        self.table.doubleClicked.connect(self._on_row_double_click)

        self.table_model = PersonsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        table_layout.addWidget(self.table)
        layout.addWidget(table_frame)

    def refresh(self, data=None):
        """Refresh the persons list."""
        logger.debug("Refreshing persons page")
        self._load_persons()

    def _load_persons(self):
        """Load persons with filters."""
        name = self.name_search.text().strip()
        nid = self.nid_search.text().strip()
        gender = self.gender_combo.currentData()

        persons = self.person_repo.search(
            name=name or None,
            national_id=nid or None,
            gender=gender or None,
            limit=500
        )

        self.table_model.set_persons(persons)
        self.count_label.setText(f"تم العثور على {len(persons)} شخص")

    def _on_filter_changed(self):
        self._load_persons()

    def _on_row_double_click(self, index):
        person = self.table_model.get_person(index.row())
        if person:
            self._edit_person(person)

    def _on_add_person(self):
        """Add new person."""
        dialog = PersonDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            person = Person(**data)

            try:
                self.person_repo.create(person)
                Toast.show(self, "تم إضافة الشخص بنجاح", Toast.SUCCESS)
                self._load_persons()
            except Exception as e:
                logger.error(f"Failed to create person: {e}")
                Toast.show(self, f"فشل في إضافة الشخص: {str(e)}", Toast.ERROR)

    def _edit_person(self, person: Person):
        """Edit existing person."""
        dialog = PersonDialog(self.db, self.i18n, person=person, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(person, key, value)

            try:
                self.person_repo.update(person)
                Toast.show(self, "تم تحديث بيانات الشخص بنجاح", Toast.SUCCESS)
                self._load_persons()
            except Exception as e:
                logger.error(f"Failed to update person: {e}")
                Toast.show(self, f"فشل في تحديث البيانات: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        self.table_model.set_language(is_arabic)
