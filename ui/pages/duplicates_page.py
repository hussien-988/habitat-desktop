# -*- coding: utf-8 -*-
"""
Duplicate resolution page.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QTabWidget, QSplitter, QTextEdit,
    QGraphicsDropShadowEffect, QDialog, QFormLayout,
    QRadioButton, QButtonGroup, QScrollArea, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from app.config import Config
from repositories.database import Database
from services.duplicate_service import DuplicateService, DuplicateGroup
from ui.components.toast import Toast
from ui.error_handler import ErrorHandler
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class DuplicatesPage(QWidget):
    """
    Page for reviewing and resolving duplicate records.
    Implements UC-007 (Property Duplicates) and UC-008 (Person Duplicates).
    """

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.dup_service = DuplicateService(db)
        self.current_groups = []
        self.selected_group_index = -1

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("إدارة التكرارات")
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("تحديث")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Stats cards
        self.stats_layout = QHBoxLayout()
        self._create_stat_cards()
        layout.addLayout(self.stats_layout)

        # Tabs for different entity types
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background-color: white; border-radius: 8px; }}
            QTabBar::tab {{ padding: 10px 20px; }}
            QTabBar::tab:selected {{ background-color: {Config.PRIMARY_COLOR}; color: white; }}
        """)

        # Property duplicates tab (UC-007)
        self.property_tab = self._create_duplicates_tab("property")
        self.tabs.addTab(self.property_tab, "تكرارات العقارات")

        # Person duplicates tab (UC-008)
        self.person_tab = self._create_duplicates_tab("person")
        self.tabs.addTab(self.person_tab, "تكرارات الأشخاص")

        layout.addWidget(self.tabs)

    def _create_stat_cards(self):
        """Create statistics cards."""
        self.stat_cards = {}

        card_data = [
            ("building", "المباني المكررة", Config.WARNING_COLOR),
            ("unit", "الوحدات المكررة", Config.WARNING_COLOR),
            ("person", "الأشخاص المكررين", Config.ERROR_COLOR),
            ("total", "إجمالي التكرارات", Config.INFO_COLOR),
        ]

        for key, label, color in card_data:
            card = self._create_stat_card(label, "0", color)
            self.stat_cards[key] = card
            self.stats_layout.addWidget(card)

    def _create_stat_card(self, label: str, value: str, color: str) -> QFrame:
        """Create a statistics card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 12px;
                border-left: 4px solid {color};
            }}
        """)
        card.setMinimumHeight(80)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 3)
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setObjectName("value")
        value_widget.setStyleSheet(f"color: {color}; font-size: {Config.FONT_SIZE_H1}pt; font-weight: 700;")
        layout.addWidget(value_widget)

        return card

    def _create_duplicates_tab(self, entity_type: str) -> QWidget:
        """Create a tab for viewing and resolving duplicates."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Left panel: Groups list
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #F8FAFC; border-radius: 8px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)

        list_label = QLabel("مجموعات التكرار:")
        list_label.setStyleSheet("font-weight: 600;")
        left_layout.addWidget(list_label)

        # Groups table
        groups_table = QTableWidget()
        groups_table.setObjectName(f"{entity_type}_groups")
        groups_table.setColumnCount(3)
        groups_table.setHorizontalHeaderLabels(["المفتاح", "العدد", "الحالة"])
        groups_table.horizontalHeader().setStretchLastSection(True)
        groups_table.setSelectionBehavior(QTableWidget.SelectRows)
        groups_table.setSelectionMode(QTableWidget.SingleSelection)
        groups_table.verticalHeader().setVisible(False)
        groups_table.setStyleSheet("""
            QTableWidget { border: 1px solid #E5E7EB; border-radius: 6px; }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #EBF5FF; }
        """)
        groups_table.itemSelectionChanged.connect(
            lambda: self._on_group_selected(entity_type)
        )
        left_layout.addWidget(groups_table)

        layout.addWidget(left_panel, 1)

        # Right panel: Details and actions
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: white; border-radius: 8px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)

        details_label = QLabel("تفاصيل التكرار:")
        details_label.setStyleSheet("font-weight: 600; font-size: 11pt;")
        right_layout.addWidget(details_label)

        # Details scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        details_content = QWidget()
        details_content.setObjectName(f"{entity_type}_details")
        details_content_layout = QVBoxLayout(details_content)
        details_content_layout.setAlignment(Qt.AlignTop)

        placeholder = QLabel("اختر مجموعة تكرار لعرض التفاصيل")
        placeholder.setObjectName(f"{entity_type}_placeholder")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(f"color: {Config.TEXT_LIGHT}; padding: 40px;")
        details_content_layout.addWidget(placeholder)

        scroll.setWidget(details_content)
        right_layout.addWidget(scroll)

        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()

        merge_btn = QPushButton("دمج السجلات")
        merge_btn.setObjectName(f"{entity_type}_merge_btn")
        merge_btn.setEnabled(False)
        merge_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:disabled {{ background-color: #ccc; }}
        """)
        merge_btn.clicked.connect(lambda: self._on_merge_clicked(entity_type))
        actions_layout.addWidget(merge_btn)

        separate_btn = QPushButton("إبقاء منفصلة")
        separate_btn.setObjectName(f"{entity_type}_separate_btn")
        separate_btn.setEnabled(False)
        separate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.WARNING_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:disabled {{ background-color: #ccc; }}
        """)
        separate_btn.clicked.connect(lambda: self._on_keep_separate_clicked(entity_type))
        actions_layout.addWidget(separate_btn)

        escalate_btn = QPushButton("تصعيد للمراجعة")
        escalate_btn.setObjectName(f"{entity_type}_escalate_btn")
        escalate_btn.setEnabled(False)
        escalate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:disabled {{ background-color: #ccc; }}
        """)
        escalate_btn.clicked.connect(lambda: self._on_escalate_clicked(entity_type))
        actions_layout.addWidget(escalate_btn)

        right_layout.addLayout(actions_layout)

        layout.addWidget(right_panel, 2)

        return widget

    def refresh(self, data=None):
        """Refresh duplicate data."""
        logger.debug("Refreshing duplicates page")

        # Update stats
        counts = self.dup_service.get_pending_count()
        for key, count in counts.items():
            if key in self.stat_cards:
                value_label = self.stat_cards[key].findChild(QLabel, "value")
                if value_label:
                    value_label.setText(str(count))

        # Load property duplicates
        self._load_property_duplicates()

        # Load person duplicates
        self._load_person_duplicates()

    def _load_property_duplicates(self):
        """Load property (building + unit) duplicates."""
        groups = self.dup_service.get_all_property_duplicates()
        self.property_groups = groups

        table = self.property_tab.findChild(QTableWidget, "property_groups")
        if table:
            table.setRowCount(len(groups))
            for i, group in enumerate(groups):
                table.setItem(i, 0, QTableWidgetItem(group.group_key))
                table.setItem(i, 1, QTableWidgetItem(str(len(group.records))))
                status_text = "مبنى" if group.entity_type == "building" else "وحدة"
                table.setItem(i, 2, QTableWidgetItem(status_text))

    def _load_person_duplicates(self):
        """Load person duplicates."""
        groups = self.dup_service.detect_person_duplicates()
        self.person_groups = groups

        table = self.person_tab.findChild(QTableWidget, "person_groups")
        if table:
            table.setRowCount(len(groups))
            for i, group in enumerate(groups):
                table.setItem(i, 0, QTableWidgetItem(group.group_key))
                table.setItem(i, 1, QTableWidgetItem(str(len(group.records))))
                table.setItem(i, 2, QTableWidgetItem("شخص"))

    def _on_group_selected(self, entity_type: str):
        """Handle group selection."""
        if entity_type == "property":
            table = self.property_tab.findChild(QTableWidget, "property_groups")
            groups = getattr(self, "property_groups", [])
            details_widget = self.property_tab.findChild(QWidget, "property_details")
        else:
            table = self.person_tab.findChild(QTableWidget, "person_groups")
            groups = getattr(self, "person_groups", [])
            details_widget = self.person_tab.findChild(QWidget, "person_details")

        if not table or not groups:
            return

        selected = table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if row < 0 or row >= len(groups):
            return

        self.selected_group_index = row
        group = groups[row]

        # Enable action buttons
        tab = self.property_tab if entity_type == "property" else self.person_tab
        for btn_name in [f"{entity_type}_merge_btn", f"{entity_type}_separate_btn", f"{entity_type}_escalate_btn"]:
            btn = tab.findChild(QPushButton, btn_name)
            if btn:
                btn.setEnabled(True)

        # Display details side-by-side
        self._display_group_details(entity_type, group)

    def _display_group_details(self, entity_type: str, group: DuplicateGroup):
        """Display detailed comparison of duplicate records."""
        if entity_type == "property":
            details_widget = self.property_tab.findChild(QWidget, "property_details")
        else:
            details_widget = self.person_tab.findChild(QWidget, "person_details")

        if not details_widget:
            return

        # Clear existing content
        layout = details_widget.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Create side-by-side comparison
        comparison_layout = QHBoxLayout()

        for i, record in enumerate(group.records):
            card = self._create_record_card(entity_type, record, i + 1)
            comparison_layout.addWidget(card)

        comparison_widget = QWidget()
        comparison_widget.setLayout(comparison_layout)
        layout.addWidget(comparison_widget)

    def _create_record_card(self, entity_type: str, record: dict, index: int) -> QGroupBox:
        """Create a card displaying record details."""
        card = QGroupBox(f"سجل {index}")
        card.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QFormLayout(card)
        layout.setSpacing(8)

        if entity_type == "property" or entity_type == "building" or entity_type == "unit":
            # Property record fields
            fields = [
                ("معرف المبنى", record.get("building_id", "-")),
                ("رمز الوحدة", record.get("unit_code", "-")),
                ("نوع الوحدة", record.get("unit_type", "-")),
                ("الطابق", str(record.get("floor_number", "-"))),
                ("العنوان", record.get("address_text", "-")),
                ("الإحداثيات", record.get("geo_location", "-")),
            ]
        else:
            # Person record fields
            fields = [
                ("الاسم الأول", record.get("first_name", "-")),
                ("اسم الأب", record.get("father_name", "-")),
                ("اسم العائلة", record.get("family_name", "-")),
                ("الرقم الوطني", record.get("national_id", "-")),
                ("الجنس", record.get("sex", "-")),
                ("سنة الميلاد", str(record.get("birth_year", "-"))),
                ("الهاتف", record.get("phone_primary", "-")),
            ]

        for label, value in fields:
            label_widget = QLabel(label + ":")
            label_widget.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            value_widget = QLabel(str(value) if value else "-")
            value_widget.setWordWrap(True)
            layout.addRow(label_widget, value_widget)

        # Store UUID for selection
        uuid_key = "building_uuid" if entity_type == "building" else (
            "unit_uuid" if entity_type == "unit" else "person_uuid"
        )
        card.setProperty("record_uuid", record.get(uuid_key, ""))

        return card

    def _on_merge_clicked(self, entity_type: str):
        """Handle merge action."""
        if entity_type == "property":
            groups = getattr(self, "property_groups", [])
        else:
            groups = getattr(self, "person_groups", [])

        if self.selected_group_index < 0 or self.selected_group_index >= len(groups):
            return

        group = groups[self.selected_group_index]

        # Show merge dialog
        dialog = MergeDialog(group, self)
        if dialog.exec_() == QDialog.Accepted:
            master_uuid = dialog.get_master_uuid()
            justification = dialog.get_justification()

            if master_uuid and justification:
                success = self.dup_service.resolve_as_merge(
                    group, master_uuid, justification
                )
                if success:
                    Toast.show_toast(self, "تم دمج السجلات بنجاح", Toast.SUCCESS)
                    self.refresh()
                else:
                    Toast.show_toast(self, "فشل في دمج السجلات", Toast.ERROR)

    def _on_keep_separate_clicked(self, entity_type: str):
        """Handle keep separate action."""
        if entity_type == "property":
            groups = getattr(self, "property_groups", [])
        else:
            groups = getattr(self, "person_groups", [])

        if self.selected_group_index < 0 or self.selected_group_index >= len(groups):
            return

        group = groups[self.selected_group_index]

        # Get justification
        from PyQt5.QtWidgets import QInputDialog
        justification, ok = QInputDialog.getMultiLineText(
            self,
            "سبب الإبقاء منفصلة",
            "يرجى إدخال سبب اعتبار هذه السجلات منفصلة:"
        )

        if ok and justification.strip():
            success = self.dup_service.resolve_as_separate(
                group, justification.strip()
            )
            if success:
                Toast.show_toast(self, "تم تسجيل القرار بنجاح", Toast.SUCCESS)
                self.refresh()
            else:
                Toast.show_toast(self, "فشل في تسجيل القرار", Toast.ERROR)

    def _on_escalate_clicked(self, entity_type: str):
        """Handle escalate action."""
        if entity_type == "property":
            groups = getattr(self, "property_groups", [])
        else:
            groups = getattr(self, "person_groups", [])

        if self.selected_group_index < 0 or self.selected_group_index >= len(groups):
            return

        group = groups[self.selected_group_index]

        # Get justification
        from PyQt5.QtWidgets import QInputDialog
        justification, ok = QInputDialog.getMultiLineText(
            self,
            "سبب التصعيد",
            "يرجى إدخال سبب تصعيد هذه الحالة للمراجعة:"
        )

        if ok and justification.strip():
            success = self.dup_service.escalate_for_review(
                group, justification.strip()
            )
            if success:
                Toast.show_toast(self, "تم تصعيد الحالة للمراجعة", Toast.SUCCESS)
                self.refresh()
            else:
                Toast.show_toast(self, "فشل في تصعيد الحالة", Toast.ERROR)

    def update_language(self, is_arabic: bool):
        """Update UI language."""
        pass  # UI is Arabic by default


class MergeDialog(QDialog):
    """Dialog for selecting master record during merge."""

    def __init__(self, group: DuplicateGroup, parent=None):
        super().__init__(parent)
        self.group = group
        self.selected_uuid = None

        self.setWindowTitle("دمج السجلات")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Instructions
        instructions = QLabel("اختر السجل الرئيسي الذي سيتم الاحتفاظ به:")
        instructions.setStyleSheet("font-weight: 600;")
        layout.addWidget(instructions)

        # Radio buttons for each record
        self.button_group = QButtonGroup(self)

        for i, record in enumerate(self.group.records):
            uuid_key = self._get_uuid_key()
            uuid_val = record.get(uuid_key, "")

            # Create descriptive label
            if self.group.entity_type in ["building", "unit"]:
                label = f"سجل {i+1}: {record.get('building_id', '-')}"
                if record.get("unit_code"):
                    label += f" / {record.get('unit_code')}"
            else:
                label = f"سجل {i+1}: {record.get('first_name', '')} {record.get('family_name', '')}"
                if record.get("national_id"):
                    label += f" ({record.get('national_id')})"

            radio = QRadioButton(label)
            radio.setProperty("uuid", uuid_val)
            self.button_group.addButton(radio, i)
            layout.addWidget(radio)

        # First record selected by default
        if self.button_group.buttons():
            self.button_group.buttons()[0].setChecked(True)

        # Justification
        layout.addWidget(QLabel("سبب الدمج (مطلوب):"))
        self.justification_edit = QTextEdit()
        self.justification_edit.setMaximumHeight(100)
        self.justification_edit.setPlaceholderText("أدخل سبب دمج هذه السجلات...")
        layout.addWidget(self.justification_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        merge_btn = QPushButton("دمج")
        merge_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
        """)
        merge_btn.clicked.connect(self._on_merge)
        btn_layout.addWidget(merge_btn)

        layout.addLayout(btn_layout)

    def _get_uuid_key(self) -> str:
        if self.group.entity_type == "building":
            return "building_uuid"
        elif self.group.entity_type == "unit":
            return "unit_uuid"
        else:
            return "person_uuid"

    def _on_merge(self):
        justification = self.justification_edit.toPlainText().strip()
        if not justification:
            ErrorHandler.show_warning(self, "يجب إدخال سبب الدمج", "خطأ")
            return

        selected = self.button_group.checkedButton()
        if selected:
            self.selected_uuid = selected.property("uuid")
            self.accept()

    def get_master_uuid(self) -> str:
        return self.selected_uuid

    def get_justification(self) -> str:
        return self.justification_edit.toPlainText().strip()
