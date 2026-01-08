# -*- coding: utf-8 -*-
"""
Households/Occupancy management page with search, CRUD, and validation.
Implements Household data entry tied to Units.
"""

from decimal import Decimal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFrame, QDialog, QFormLayout, QSpinBox, QTextEdit,
    QAbstractItemView, QGraphicsDropShadowEffect, QMessageBox,
    QDateEdit, QGroupBox, QDoubleSpinBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex, QDate
from PyQt5.QtGui import QColor

from app.config import Config
from repositories.database import Database
from repositories.household_repository import HouseholdRepository
from repositories.unit_repository import UnitRepository
from repositories.person_repository import PersonRepository
from models.household import Household
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class HouseholdsTableModel(QAbstractTableModel):
    """Table model for households list."""

    def __init__(self, is_arabic: bool = True):
        super().__init__()
        self._households = []
        self._units_cache = {}
        self._is_arabic = is_arabic
        self._headers_en = ["Unit", "Main Occupant", "Size", "M/F", "Age Groups", "Type", "Nature"]
        self._headers_ar = ["الوحدة", "الشاغل الرئيسي", "الحجم", "ذ/أ", "الفئات العمرية", "النوع", "الطبيعة"]

    def set_cache(self, units_cache: dict):
        """Set the cache for units lookups."""
        self._units_cache = units_cache

    def rowCount(self, parent=None):
        return len(self._households)

    def columnCount(self, parent=None):
        return len(self._headers_en)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._households):
            return None

        household = self._households[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                # Unit ID
                unit = self._units_cache.get(household.unit_id)
                return unit.unit_id if unit else household.unit_id[:15]
            elif col == 1:
                # Main occupant
                return household.main_occupant_name or "-"
            elif col == 2:
                # Occupancy size
                return str(household.occupancy_size)
            elif col == 3:
                # Gender distribution (Male/Female)
                return f"{household.male_count}/{household.female_count}"
            elif col == 4:
                # Age groups (Minors/Adults/Elderly)
                return f"{household.minors_count}/{household.adults_count}/{household.elderly_count}"
            elif col == 5:
                # Occupancy type
                return household.occupancy_type_display_ar if self._is_arabic else household.occupancy_type_display
            elif col == 6:
                # Occupancy nature
                return household.occupancy_nature_display_ar if self._is_arabic else household.occupancy_nature_display
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.ToolTipRole:
            if col == 3:
                return f"ذكور: {household.male_count}, إناث: {household.female_count}"
            elif col == 4:
                return f"قاصرين: {household.minors_count}, بالغين: {household.adults_count}, كبار السن: {household.elderly_count}"

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = self._headers_ar if self._is_arabic else self._headers_en
            return headers[section] if section < len(headers) else ""
        return None

    def set_households(self, households: list):
        self.beginResetModel()
        self._households = households
        self.endResetModel()

    def get_household(self, row: int):
        if 0 <= row < len(self._households):
            return self._households[row]
        return None

    def set_language(self, is_arabic: bool):
        self._is_arabic = is_arabic
        self.layoutChanged.emit()


class HouseholdDialog(QDialog):
    """Dialog for creating/editing a household."""

    OCCUPANCY_TYPES = [
        ("owner", "مالك", "Owner"),
        ("tenant", "مستأجر", "Tenant"),
        ("guest", "ضيف", "Guest"),
        ("caretaker", "حارس", "Caretaker"),
        ("relative", "قريب", "Relative"),
        ("other", "آخر", "Other"),
    ]

    OCCUPANCY_NATURES = [
        ("permanent", "دائم", "Permanent"),
        ("temporary", "مؤقت", "Temporary"),
        ("seasonal", "موسمي", "Seasonal"),
    ]

    def __init__(self, db: Database, i18n: I18n, household: Household = None,
                 preselected_unit_id: str = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.household = household
        self.preselected_unit_id = preselected_unit_id
        self.unit_repo = UnitRepository(db)
        self.person_repo = PersonRepository(db)
        self._is_edit_mode = household is not None

        self.setWindowTitle(i18n.t("edit_household") if household else i18n.t("add_household"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(650)
        self._setup_ui()

        if household:
            self._populate_data()
        elif preselected_unit_id:
            self._set_preselected_unit()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # === Unit Selection Group ===
        unit_group = QGroupBox("الوحدة")
        unit_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: {Config.FONT_SIZE}pt;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top right;
                padding: 0 8px;
            }}
        """)
        unit_form = QFormLayout(unit_group)
        unit_form.setSpacing(10)

        self.unit_combo = QComboBox()
        self.unit_combo.setMinimumWidth(350)
        units = self.unit_repo.get_all(limit=500)
        self.unit_combo.addItem("-- اختر الوحدة --", "")
        for u in units:
            display = f"{u.unit_id} ({u.unit_type_display_ar})"
            self.unit_combo.addItem(display, u.unit_id)
        unit_form.addRow("الوحدة *:", self.unit_combo)

        layout.addWidget(unit_group)

        # === Main Occupant Group ===
        occupant_group = QGroupBox("الشاغل الرئيسي")
        occupant_group.setStyleSheet(unit_group.styleSheet())
        occupant_form = QFormLayout(occupant_group)
        occupant_form.setSpacing(10)

        # Person selection (optional)
        self.person_combo = QComboBox()
        self.person_combo.setMinimumWidth(350)
        persons = self.person_repo.get_all(limit=500)
        self.person_combo.addItem("-- اختر شخص (اختياري) --", "")
        for p in persons:
            display = f"{p.full_name_ar} ({p.national_id or 'بدون رقم وطني'})"
            self.person_combo.addItem(display, p.person_id)
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        occupant_form.addRow("الشخص:", self.person_combo)

        # Manual name entry (fallback)
        self.occupant_name = QLineEdit()
        self.occupant_name.setPlaceholderText("أو أدخل الاسم يدوياً...")
        occupant_form.addRow("الاسم:", self.occupant_name)

        layout.addWidget(occupant_group)

        # === Occupancy Counts Group ===
        counts_group = QGroupBox("بيانات الإشغال")
        counts_group.setStyleSheet(unit_group.styleSheet())
        counts_form = QFormLayout(counts_group)
        counts_form.setSpacing(10)

        # Occupancy size
        size_container = QWidget()
        size_layout = QVBoxLayout(size_container)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(4)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 50)
        self.size_spin.setValue(1)
        self.size_spin.valueChanged.connect(self._validate_counts)
        size_layout.addWidget(self.size_spin)
        counts_form.addRow("حجم الأسرة *:", size_container)

        # Gender distribution header
        gender_label = QLabel("التوزيع حسب الجنس:")
        gender_label.setStyleSheet(f"font-weight: 600; color: {Config.TEXT_COLOR}; margin-top: 8px;")
        counts_form.addRow(gender_label)

        # Male count
        self.male_spin = QSpinBox()
        self.male_spin.setRange(0, 50)
        self.male_spin.valueChanged.connect(self._validate_counts)
        counts_form.addRow("الذكور:", self.male_spin)

        # Female count
        self.female_spin = QSpinBox()
        self.female_spin.setRange(0, 50)
        self.female_spin.valueChanged.connect(self._validate_counts)
        counts_form.addRow("الإناث:", self.female_spin)

        # Age distribution header
        age_label = QLabel("التوزيع حسب العمر:")
        age_label.setStyleSheet(f"font-weight: 600; color: {Config.TEXT_COLOR}; margin-top: 8px;")
        counts_form.addRow(age_label)

        # Minors count
        self.minors_spin = QSpinBox()
        self.minors_spin.setRange(0, 50)
        self.minors_spin.valueChanged.connect(self._validate_counts)
        counts_form.addRow("القاصرين (< 18):", self.minors_spin)

        # Adults count
        self.adults_spin = QSpinBox()
        self.adults_spin.setRange(0, 50)
        self.adults_spin.valueChanged.connect(self._validate_counts)
        counts_form.addRow("البالغين (18-59):", self.adults_spin)

        # Elderly count
        self.elderly_spin = QSpinBox()
        self.elderly_spin.setRange(0, 50)
        self.elderly_spin.valueChanged.connect(self._validate_counts)
        counts_form.addRow("كبار السن (60+):", self.elderly_spin)

        # With disability count
        self.disability_spin = QSpinBox()
        self.disability_spin.setRange(0, 50)
        self.disability_spin.valueChanged.connect(self._validate_counts)
        counts_form.addRow("ذوي الإعاقة:", self.disability_spin)

        # Validation hint
        self.count_hint = QLabel("")
        self.count_hint.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: 10px;")
        counts_form.addRow("", self.count_hint)

        layout.addWidget(counts_group)

        # === Occupancy Details Group ===
        details_group = QGroupBox("تفاصيل الإشغال")
        details_group.setStyleSheet(unit_group.styleSheet())
        details_form = QFormLayout(details_group)
        details_form.setSpacing(10)

        # Occupancy type
        self.type_combo = QComboBox()
        self.type_combo.addItem("-- اختر --", "")
        for code, ar, en in self.OCCUPANCY_TYPES:
            self.type_combo.addItem(ar, code)
        details_form.addRow("نوع الإشغال:", self.type_combo)

        # Occupancy nature
        self.nature_combo = QComboBox()
        self.nature_combo.addItem("-- اختر --", "")
        for code, ar, en in self.OCCUPANCY_NATURES:
            self.nature_combo.addItem(ar, code)
        details_form.addRow("طبيعة الإشغال:", self.nature_combo)

        # Start date
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setSpecialValueText("غير محدد")
        self.start_date.setDate(QDate.currentDate())
        details_form.addRow("تاريخ بدء الإشغال:", self.start_date)

        # Monthly rent
        self.rent_spin = QDoubleSpinBox()
        self.rent_spin.setRange(0, 10000000)
        self.rent_spin.setDecimals(2)
        self.rent_spin.setSuffix(" ل.س")
        self.rent_spin.setSpecialValueText("غير محدد")
        details_form.addRow("الإيجار الشهري:", self.rent_spin)

        layout.addWidget(details_group)

        # === Notes ===
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        self.notes.setPlaceholderText("ملاحظات إضافية...")
        layout.addWidget(QLabel("ملاحظات:"))
        layout.addWidget(self.notes)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"""
            color: {Config.ERROR_COLOR};
            font-size: {Config.FONT_SIZE_SMALL}pt;
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 6px;
            padding: 8px;
        """)
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
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

    def _on_person_changed(self):
        """Auto-fill name when person is selected."""
        person_id = self.person_combo.currentData()
        if person_id:
            persons = self.person_repo.get_all(limit=500)
            for p in persons:
                if p.person_id == person_id:
                    self.occupant_name.setText(p.full_name_ar)
                    break

    def _validate_counts(self):
        """Live validation of counts."""
        size = self.size_spin.value()
        male = self.male_spin.value()
        female = self.female_spin.value()
        minors = self.minors_spin.value()
        adults = self.adults_spin.value()
        elderly = self.elderly_spin.value()
        disability = self.disability_spin.value()

        errors = []
        gender_sum = male + female
        age_sum = minors + adults + elderly

        if gender_sum > size:
            errors.append(f"مجموع الذكور والإناث ({gender_sum}) > حجم الأسرة ({size})")
        if age_sum > size:
            errors.append(f"مجموع الفئات العمرية ({age_sum}) > حجم الأسرة ({size})")
        if disability > size:
            errors.append(f"عدد ذوي الإعاقة ({disability}) > حجم الأسرة ({size})")

        if errors:
            self.count_hint.setText(" | ".join(errors))
            self.count_hint.setStyleSheet(f"color: {Config.ERROR_COLOR}; font-size: 10px;")
        else:
            remaining_gender = size - gender_sum
            remaining_age = size - age_sum
            hints = []
            if remaining_gender > 0:
                hints.append(f"متبقي للجنس: {remaining_gender}")
            if remaining_age > 0:
                hints.append(f"متبقي للعمر: {remaining_age}")
            self.count_hint.setText(" | ".join(hints) if hints else "✓ البيانات متسقة")
            self.count_hint.setStyleSheet(f"color: {Config.SUCCESS_COLOR}; font-size: 10px;")

        return len(errors) == 0

    def _set_preselected_unit(self):
        """Set the preselected unit."""
        if self.preselected_unit_id:
            idx = self.unit_combo.findData(self.preselected_unit_id)
            if idx >= 0:
                self.unit_combo.setCurrentIndex(idx)

    def _populate_data(self):
        """Populate form with existing household data."""
        if not self.household:
            return

        # Unit
        idx = self.unit_combo.findData(self.household.unit_id)
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)

        # Main occupant
        if self.household.main_occupant_id:
            idx = self.person_combo.findData(self.household.main_occupant_id)
            if idx >= 0:
                self.person_combo.setCurrentIndex(idx)

        if self.household.main_occupant_name:
            self.occupant_name.setText(self.household.main_occupant_name)

        # Counts
        self.size_spin.setValue(self.household.occupancy_size)
        self.male_spin.setValue(self.household.male_count)
        self.female_spin.setValue(self.household.female_count)
        self.minors_spin.setValue(self.household.minors_count)
        self.adults_spin.setValue(self.household.adults_count)
        self.elderly_spin.setValue(self.household.elderly_count)
        self.disability_spin.setValue(self.household.with_disability_count)

        # Occupancy type
        if self.household.occupancy_type:
            idx = self.type_combo.findData(self.household.occupancy_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)

        # Occupancy nature
        if self.household.occupancy_nature:
            idx = self.nature_combo.findData(self.household.occupancy_nature)
            if idx >= 0:
                self.nature_combo.setCurrentIndex(idx)

        # Start date
        if self.household.occupancy_start_date:
            self.start_date.setDate(QDate(
                self.household.occupancy_start_date.year,
                self.household.occupancy_start_date.month,
                self.household.occupancy_start_date.day
            ))

        # Monthly rent
        if self.household.monthly_rent:
            self.rent_spin.setValue(float(self.household.monthly_rent))

        # Notes
        if self.household.notes:
            self.notes.setPlainText(self.household.notes)

    def _on_save(self):
        """Validate and save."""
        errors = []

        # Required fields
        unit_id = self.unit_combo.currentData()
        if not unit_id:
            errors.append("يجب اختيار الوحدة")

        # Validate counts
        if not self._validate_counts():
            errors.append("البيانات غير متسقة - راجع الأرقام")

        if errors:
            self.error_label.setText(" • ".join(errors))
            self.error_label.setVisible(True)
            return

        self.error_label.setVisible(False)
        self.accept()

    def get_data(self) -> dict:
        """Get form data as dictionary."""
        start_date = self.start_date.date().toPyDate() if self.start_date.date().isValid() else None
        rent = self.rent_spin.value() if self.rent_spin.value() > 0 else None

        return {
            "unit_id": self.unit_combo.currentData(),
            "main_occupant_id": self.person_combo.currentData() or None,
            "main_occupant_name": self.occupant_name.text().strip() or None,
            "occupancy_size": self.size_spin.value(),
            "male_count": self.male_spin.value(),
            "female_count": self.female_spin.value(),
            "minors_count": self.minors_spin.value(),
            "adults_count": self.adults_spin.value(),
            "elderly_count": self.elderly_spin.value(),
            "with_disability_count": self.disability_spin.value(),
            "occupancy_type": self.type_combo.currentData() or None,
            "occupancy_nature": self.nature_combo.currentData() or None,
            "occupancy_start_date": start_date,
            "monthly_rent": Decimal(str(rent)) if rent else None,
            "notes": self.notes.toPlainText().strip() or None,
        }


class HouseholdsPage(QWidget):
    """Households management page."""

    view_household = pyqtSignal(str)

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.household_repo = HouseholdRepository(db)
        self.unit_repo = UnitRepository(db)
        self._units_cache = {}

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel(self.i18n.t("households"))
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Add household button
        add_btn = QPushButton("+ " + self.i18n.t("add_household"))
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
        add_btn.clicked.connect(self._on_add_household)
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

        # Unit filter
        filters_layout.addWidget(QLabel("الوحدة:"))
        self.unit_filter = QComboBox()
        self.unit_filter.setMinimumWidth(200)
        self.unit_filter.addItem(self.i18n.t("all"), "")
        self.unit_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.unit_filter)

        # Occupancy type filter
        filters_layout.addWidget(QLabel("نوع الإشغال:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem(self.i18n.t("all"), "")
        for code, ar, en in HouseholdDialog.OCCUPANCY_TYPES:
            self.type_filter.addItem(ar, code)
        self.type_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.type_filter)

        # Occupancy nature filter
        filters_layout.addWidget(QLabel("طبيعة الإشغال:"))
        self.nature_filter = QComboBox()
        self.nature_filter.addItem(self.i18n.t("all"), "")
        for code, ar, en in HouseholdDialog.OCCUPANCY_NATURES:
            self.nature_filter.addItem(ar, code)
        self.nature_filter.currentIndexChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.nature_filter)

        filters_layout.addStretch()
        layout.addWidget(filters_frame)

        # Results count and stats
        stats_layout = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        stats_layout.addWidget(self.count_label)

        stats_layout.addStretch()

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        stats_layout.addWidget(self.stats_label)

        layout.addLayout(stats_layout)

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

        self.table_model = HouseholdsTableModel(is_arabic=self.i18n.is_arabic())
        self.table.setModel(self.table_model)

        # Context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        table_layout.addWidget(self.table)
        layout.addWidget(table_frame)

    def _show_context_menu(self, pos):
        """Show context menu for table actions."""
        from PyQt5.QtWidgets import QMenu, QAction

        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)

        edit_action = QAction("تعديل", self)
        edit_action.triggered.connect(lambda: self._on_row_double_click(index))
        menu.addAction(edit_action)

        delete_action = QAction("حذف", self)
        delete_action.triggered.connect(lambda: self._delete_household(index))
        menu.addAction(delete_action)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _delete_household(self, index):
        """Delete a household."""
        household = self.table_model.get_household(index.row())
        if not household:
            return

        reply = QMessageBox.question(
            self,
            "تأكيد الحذف",
            "هل أنت متأكد من حذف هذه الأسرة؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.household_repo.delete(household.household_id)
                Toast.show_toast(self, self.i18n.t("household_deleted"), Toast.SUCCESS)
                self._load_households()
            except Exception as e:
                logger.error(f"Failed to delete household: {e}")
                Toast.show_toast(self, f"فشل في حذف الأسرة: {str(e)}", Toast.ERROR)

    def refresh(self, data=None):
        """Refresh the households list."""
        logger.debug("Refreshing households page")
        self._load_filters()
        self._load_households()

    def _load_filters(self):
        """Load filter dropdowns."""
        # Cache units
        units = self.unit_repo.get_all(limit=500)
        self._units_cache = {u.unit_id: u for u in units}

        # Update table model cache
        self.table_model.set_cache(self._units_cache)

        # Unit filter
        current_unit = self.unit_filter.currentData()
        self.unit_filter.clear()
        self.unit_filter.addItem(self.i18n.t("all"), "")
        for u in units:
            self.unit_filter.addItem(u.unit_id, u.unit_id)
        if current_unit:
            idx = self.unit_filter.findData(current_unit)
            if idx >= 0:
                self.unit_filter.setCurrentIndex(idx)

    def _load_households(self):
        """Load households with filters."""
        unit_id = self.unit_filter.currentData()
        occupancy_type = self.type_filter.currentData()
        occupancy_nature = self.nature_filter.currentData()

        households = self.household_repo.search(
            unit_id=unit_id or None,
            occupancy_type=occupancy_type or None,
            occupancy_nature=occupancy_nature or None,
            limit=500
        )

        self.table_model.set_households(households)
        self.count_label.setText(f"تم العثور على {len(households)} أسرة")

        # Calculate stats
        total_occupants = sum(h.occupancy_size for h in households)
        total_males = sum(h.male_count for h in households)
        total_females = sum(h.female_count for h in households)
        self.stats_label.setText(f"إجمالي الشاغلين: {total_occupants} (ذ: {total_males}, أ: {total_females})")

    def _on_filter_changed(self):
        self._load_households()

    def _on_row_double_click(self, index):
        """Handle double-click to edit household."""
        household = self.table_model.get_household(index.row())
        if household:
            self._edit_household(household)

    def _on_add_household(self):
        """Add new household."""
        dialog = HouseholdDialog(self.db, self.i18n, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            household = Household(**data)

            # Validate
            validation_errors = household.validate()
            if validation_errors:
                Toast.show_toast(self, " • ".join(validation_errors), Toast.ERROR)
                return

            try:
                self.household_repo.create(household)
                Toast.show_toast(self, self.i18n.t("household_added"), Toast.SUCCESS)
                self._load_households()
            except Exception as e:
                logger.error(f"Failed to create household: {e}")
                Toast.show_toast(self, f"فشل في إضافة الأسرة: {str(e)}", Toast.ERROR)

    def _edit_household(self, household: Household):
        """Edit existing household."""
        dialog = HouseholdDialog(self.db, self.i18n, household=household, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            for key, value in data.items():
                setattr(household, key, value)

            # Validate
            validation_errors = household.validate()
            if validation_errors:
                Toast.show_toast(self, " • ".join(validation_errors), Toast.ERROR)
                return

            try:
                self.household_repo.update(household)
                Toast.show_toast(self, self.i18n.t("household_updated"), Toast.SUCCESS)
                self._load_households()
            except Exception as e:
                logger.error(f"Failed to update household: {e}")
                Toast.show_toast(self, f"فشل في تحديث الأسرة: {str(e)}", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update language."""
        self.table_model.set_language(is_arabic)
