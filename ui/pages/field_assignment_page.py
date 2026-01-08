# -*- coding: utf-8 -*-
"""
Field assignment page for assigning buildings to field teams.
Implements UC-012: Assign Buildings to Field Teams
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableView, QTableWidget, QTableWidgetItem,
    QFrame, QSplitter, QAbstractItemView, QHeaderView,
    QDialog, QFormLayout, QLineEdit, QCheckBox, QTextEdit,
    QMessageBox, QGroupBox, QListWidget, QListWidgetItem,
    QProgressDialog
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

from app.config import Config, AleppoDivisions
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.unit_repository import UnitRepository
from services.assignment_service import AssignmentService, BuildingAssignment
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingsTableModel(QAbstractTableModel):
    """Table model for buildings available for assignment."""

    def __init__(self):
        super().__init__()
        self._buildings = []
        self._headers = ["رقم المبنى", "الحي", "النوع", "عدد الوحدات", "الحالة"]

    def rowCount(self, parent=None):
        return len(self._buildings)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._buildings):
            return None

        building = self._buildings[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return building.building_id
            elif col == 1:
                return building.neighborhood_name_ar or building.neighborhood_name
            elif col == 2:
                return building.building_type or "-"
            elif col == 3:
                return str(building.number_of_units or 0)
            elif col == 4:
                return building.building_status or "-"
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.UserRole:
            return building

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section] if section < len(self._headers) else ""
        return None

    def set_buildings(self, buildings: list):
        self.beginResetModel()
        self._buildings = buildings
        self.endResetModel()

    def get_building(self, row: int):
        if 0 <= row < len(self._buildings):
            return self._buildings[row]
        return None


class AssignmentQueueWidget(QWidget):
    """Widget showing buildings queued for assignment."""

    assignment_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buildings = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("قائمة التعيين:"))
        header.addStretch()

        clear_btn = QPushButton("مسح الكل")
        clear_btn.setStyleSheet(f"color: {Config.ERROR_COLOR}; background: transparent; border: none;")
        clear_btn.clicked.connect(self.clear)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # List
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F1F5F9;
            }
            QListWidget::item:selected {
                background-color: #EBF5FF;
            }
        """)
        layout.addWidget(self.list_widget)

        # Count label
        self.count_label = QLabel("0 مبنى في القائمة")
        self.count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        layout.addWidget(self.count_label)

    def add_building(self, building):
        """Add building to queue."""
        # Check if already in queue
        for b in self._buildings:
            if b.building_id == building.building_id:
                return False

        self._buildings.append(building)
        item = QListWidgetItem(f"{building.building_id} - {building.neighborhood_name_ar or building.neighborhood_name}")
        item.setData(Qt.UserRole, building)
        self.list_widget.addItem(item)
        self._update_count()
        self.assignment_changed.emit()
        return True

    def remove_selected(self):
        """Remove selected building from queue."""
        current = self.list_widget.currentRow()
        if current >= 0:
            self.list_widget.takeItem(current)
            del self._buildings[current]
            self._update_count()
            self.assignment_changed.emit()

    def clear(self):
        """Clear all buildings from queue."""
        self._buildings = []
        self.list_widget.clear()
        self._update_count()
        self.assignment_changed.emit()

    def get_buildings(self):
        """Get all buildings in queue."""
        return self._buildings.copy()

    def get_building_ids(self):
        """Get list of building IDs in queue."""
        return [b.building_id for b in self._buildings]

    def _update_count(self):
        count = len(self._buildings)
        self.count_label.setText(f"{count} مبنى في القائمة")


class TransferDialog(QDialog):
    """Dialog for transferring buildings to tablet."""

    def __init__(self, assignment_service: AssignmentService, building_count: int, parent=None):
        super().__init__(parent)
        self.assignment_service = assignment_service
        self.building_count = building_count
        self.selected_team = None
        self.selected_tablet = None

        self.setWindowTitle("نقل المباني إلى الجهاز اللوحي")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Info
        info = QLabel(f"سيتم نقل {self.building_count} مبنى إلى الجهاز اللوحي")
        info.setStyleSheet(f"font-weight: 600; color: {Config.PRIMARY_COLOR};")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(12)

        # Team selector
        self.team_combo = QComboBox()
        teams = self.assignment_service.get_field_teams()
        for team in teams:
            self.team_combo.addItem(team["team_name"], team["team_id"])
        form.addRow("الفريق الميداني:", self.team_combo)

        # Tablet selector
        self.tablet_combo = QComboBox()
        tablets = self.assignment_service.get_available_tablets()
        for tablet in tablets:
            status = "✓" if tablet["status"] == "connected" else "✗"
            self.tablet_combo.addItem(f"{status} {tablet['device_name']}", tablet["device_id"])
        form.addRow("الجهاز اللوحي:", self.tablet_combo)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("ملاحظات إضافية...")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("ملاحظات:", self.notes_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        transfer_btn = QPushButton("نقل الآن")
        transfer_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
        """)
        transfer_btn.clicked.connect(self._on_transfer)
        btn_layout.addWidget(transfer_btn)

        layout.addLayout(btn_layout)

    def _on_transfer(self):
        self.selected_team = self.team_combo.currentText()
        self.selected_tablet = self.tablet_combo.currentData()
        self.notes = self.notes_edit.toPlainText()
        self.accept()


class FieldAssignmentPage(QWidget):
    """Field assignment page for UC-012."""

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self.assignment_service = AssignmentService(db)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()

        title = QLabel("تعيين المباني للفرق الميدانية")
        title.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header.addWidget(title)

        header.addStretch()

        # Statistics
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        header.addWidget(self.stats_label)

        layout.addLayout(header)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: Building search and selection
        left_widget = self._create_building_selection_widget()
        splitter.addWidget(left_widget)

        # Right: Assignment queue and actions
        right_widget = self._create_assignment_widget()
        splitter.addWidget(right_widget)

        splitter.setSizes([600, 400])
        layout.addWidget(splitter)

    def _create_building_selection_widget(self) -> QWidget:
        """Create building search and selection panel (UC-012 S01-S03)."""
        widget = QGroupBox("اختيار المباني")
        widget.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filters (UC-012 S02)
        filter_layout = QHBoxLayout()

        # Neighborhood filter
        filter_layout.addWidget(QLabel("الحي:"))
        self.neighborhood_combo = QComboBox()
        self.neighborhood_combo.addItem("جميع الأحياء", None)
        for code, name, name_ar in AleppoDivisions.NEIGHBORHOODS_ALEPPO:
            self.neighborhood_combo.addItem(name_ar, code)
        self.neighborhood_combo.setMinimumWidth(150)
        self.neighborhood_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.neighborhood_combo)

        # Status filter
        filter_layout.addWidget(QLabel("الحالة:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("جميع الحالات", None)
        self.status_combo.addItem("غير معين", "unassigned")
        self.status_combo.addItem("معين", "assigned")
        self.status_combo.addItem("تم النقل", "transferred")
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.status_combo)

        filter_layout.addStretch()

        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("البحث برقم المبنى...")
        self.search_edit.textChanged.connect(self._on_search)
        filter_layout.addWidget(self.search_edit)

        layout.addLayout(filter_layout)

        # Buildings table (UC-012 S01)
        self.buildings_table = QTableView()
        self.buildings_table.setAlternatingRowColors(True)
        self.buildings_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.buildings_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.buildings_table.setShowGrid(False)
        self.buildings_table.verticalHeader().setVisible(False)
        self.buildings_table.horizontalHeader().setStretchLastSection(True)
        self.buildings_table.setStyleSheet(f"""
            QTableView {{
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }}
            QTableView::item {{
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
        self.buildings_table.doubleClicked.connect(self._on_building_double_click)

        self.buildings_model = BuildingsTableModel()
        self.buildings_table.setModel(self.buildings_model)

        layout.addWidget(self.buildings_table)

        # Actions
        actions = QHBoxLayout()

        add_selected_btn = QPushButton("← إضافة المحدد")
        add_selected_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
        """)
        add_selected_btn.clicked.connect(self._on_add_selected)
        actions.addWidget(add_selected_btn)

        add_all_btn = QPushButton("← إضافة الكل")
        add_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
        """)
        add_all_btn.clicked.connect(self._on_add_all)
        actions.addWidget(add_all_btn)

        actions.addStretch()

        self.building_count_label = QLabel("0 مبنى")
        self.building_count_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        actions.addWidget(self.building_count_label)

        layout.addLayout(actions)

        return widget

    def _create_assignment_widget(self) -> QWidget:
        """Create assignment queue and actions panel (UC-012 S06-S12)."""
        widget = QGroupBox("قائمة التعيين والنقل")
        widget.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Assignment queue
        self.queue_widget = AssignmentQueueWidget()
        self.queue_widget.assignment_changed.connect(self._on_queue_changed)
        layout.addWidget(self.queue_widget)

        # Remove button
        remove_btn = QPushButton("إزالة المحدد من القائمة")
        remove_btn.clicked.connect(self.queue_widget.remove_selected)
        layout.addWidget(remove_btn)

        # Team selector
        team_layout = QHBoxLayout()
        team_layout.addWidget(QLabel("الفريق:"))

        self.team_combo = QComboBox()
        teams = self.assignment_service.get_field_teams()
        for team in teams:
            self.team_combo.addItem(team["team_name"], team["team_id"])
        team_layout.addWidget(self.team_combo)

        layout.addLayout(team_layout)

        # Action buttons
        actions = QVBoxLayout()

        # Assign button (UC-012 S06)
        self.assign_btn = QPushButton("تعيين المباني للفريق")
        self.assign_btn.setEnabled(False)
        self.assign_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
            }}
            QPushButton:disabled {{
                background-color: #CBD5E0;
            }}
        """)
        self.assign_btn.clicked.connect(self._on_assign)
        actions.addWidget(self.assign_btn)

        # Transfer button (UC-012 S08)
        self.transfer_btn = QPushButton("نقل إلى الجهاز اللوحي")
        self.transfer_btn.setEnabled(False)
        self.transfer_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 600;
            }}
            QPushButton:disabled {{
                background-color: #CBD5E0;
            }}
        """)
        self.transfer_btn.clicked.connect(self._on_transfer)
        actions.addWidget(self.transfer_btn)

        layout.addLayout(actions)

        # Recent assignments
        layout.addWidget(QLabel("التعيينات الأخيرة:"))

        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(["المبنى", "الفريق", "الحالة", "النقل"])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setMaximumHeight(200)
        self.recent_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 8px;
                border: none;
            }}
        """)
        layout.addWidget(self.recent_table)

        return widget

    def _on_filter_changed(self, index):
        """Handle filter change."""
        self._load_buildings()

    def _on_search(self, text):
        """Handle search text change."""
        self._load_buildings()

    def _load_buildings(self):
        """Load buildings based on current filters."""
        neighborhood = self.neighborhood_combo.currentData()
        search_text = self.search_edit.text().strip()

        buildings = self.building_repo.search(
            neighborhood_code=neighborhood,
            search_text=search_text if search_text else None,
            limit=200
        )

        # Filter by assignment status if selected
        status_filter = self.status_combo.currentData()
        if status_filter:
            filtered = []
            for building in buildings:
                assignment = self.assignment_service.get_assignment_for_building(building.building_id)
                if status_filter == "unassigned" and not assignment:
                    filtered.append(building)
                elif status_filter == "assigned" and assignment and assignment.transfer_status != "transferred":
                    filtered.append(building)
                elif status_filter == "transferred" and assignment and assignment.transfer_status == "transferred":
                    filtered.append(building)
            buildings = filtered

        self.buildings_model.set_buildings(buildings)
        self.building_count_label.setText(f"{len(buildings)} مبنى")

    def _on_building_double_click(self, index):
        """Add double-clicked building to queue."""
        building = self.buildings_model.get_building(index.row())
        if building:
            if self.queue_widget.add_building(building):
                Toast.show_toast(self, f"تم إضافة المبنى {building.building_id}", Toast.SUCCESS)
            else:
                Toast.show_toast(self, "المبنى موجود في القائمة", Toast.WARNING)

    def _on_add_selected(self):
        """Add selected buildings to queue."""
        indexes = self.buildings_table.selectionModel().selectedRows()
        added = 0
        for index in indexes:
            building = self.buildings_model.get_building(index.row())
            if building and self.queue_widget.add_building(building):
                added += 1

        if added > 0:
            Toast.show_toast(self, f"تم إضافة {added} مبنى للقائمة", Toast.SUCCESS)

    def _on_add_all(self):
        """Add all visible buildings to queue."""
        buildings = [self.buildings_model.get_building(i) for i in range(self.buildings_model.rowCount())]
        added = 0
        for building in buildings:
            if building and self.queue_widget.add_building(building):
                added += 1

        if added > 0:
            Toast.show_toast(self, f"تم إضافة {added} مبنى للقائمة", Toast.SUCCESS)

    def _on_queue_changed(self):
        """Handle queue content change."""
        has_buildings = len(self.queue_widget.get_buildings()) > 0
        self.assign_btn.setEnabled(has_buildings)
        self.transfer_btn.setEnabled(has_buildings)

    def _on_assign(self):
        """Assign buildings to team (UC-012 S06)."""
        buildings = self.queue_widget.get_buildings()
        if not buildings:
            return

        team_name = self.team_combo.currentText()

        reply = QMessageBox.question(
            self,
            "تأكيد التعيين",
            f"هل تريد تعيين {len(buildings)} مبنى للفريق: {team_name}؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            assignments = self.assignment_service.create_batch_assignments(
                building_ids=[b.building_id for b in buildings],
                field_team_name=team_name
            )

            Toast.show_toast(self, f"تم تعيين {len(assignments)} مبنى للفريق {team_name}", Toast.SUCCESS)
            self.queue_widget.clear()
            self._load_recent_assignments()
            self._update_stats()

        except Exception as e:
            logger.error(f"Assignment failed: {e}")
            Toast.show_toast(self, f"فشل في التعيين: {str(e)}", Toast.ERROR)

    def _on_transfer(self):
        """Transfer buildings to tablet (UC-012 S08-S12)."""
        buildings = self.queue_widget.get_buildings()
        if not buildings:
            return

        dialog = TransferDialog(self.assignment_service, len(buildings), self)
        if dialog.exec_() != QDialog.Accepted:
            return

        team_name = dialog.selected_team
        tablet_id = dialog.selected_tablet
        notes = dialog.notes

        # First create assignments if not already assigned
        try:
            assignments = []
            for building in buildings:
                existing = self.assignment_service.get_assignment_for_building(building.building_id)
                if existing and existing.assignment_status not in ("completed", "cancelled"):
                    assignments.append(existing)
                else:
                    assignment = self.assignment_service.create_assignment(
                        building_id=building.building_id,
                        field_team_name=team_name,
                        notes=notes
                    )
                    assignments.append(assignment)

            # Initiate transfer
            assignment_ids = [a.assignment_id for a in assignments]
            result = self.assignment_service.initiate_transfer(assignment_ids, tablet_id)

            # Simulate transfer completion
            progress = QProgressDialog("جاري نقل البيانات...", "إلغاء", 0, len(assignment_ids), self)
            progress.setWindowTitle("نقل البيانات")
            progress.setWindowModality(Qt.WindowModal)

            for i, assignment_id in enumerate(result["success"]):
                progress.setValue(i)
                if progress.wasCanceled():
                    break

                # Simulate network delay
                QTimer.singleShot(100, lambda: None)

                # Complete the transfer
                self.assignment_service.complete_transfer(assignment_id)

            progress.setValue(len(assignment_ids))

            Toast.show_toast(self, f"تم نقل {len(result['success'])} مبنى بنجاح", Toast.SUCCESS)
            self.queue_widget.clear()
            self._load_recent_assignments()
            self._update_stats()

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            Toast.show_toast(self, f"فشل في النقل: {str(e)}", Toast.ERROR)

    def _load_recent_assignments(self):
        """Load recent assignments into table."""
        assignments = self.assignment_service.get_assignments(limit=10)

        self.recent_table.setRowCount(len(assignments))
        for i, a in enumerate(assignments):
            self.recent_table.setItem(i, 0, QTableWidgetItem(a.building_id))
            self.recent_table.setItem(i, 1, QTableWidgetItem(a.field_team_name or "-"))

            status_text = {
                "pending": "معلق",
                "assigned": "معين",
                "completed": "مكتمل",
                "cancelled": "ملغى"
            }.get(a.assignment_status, a.assignment_status)
            self.recent_table.setItem(i, 2, QTableWidgetItem(status_text))

            transfer_text = {
                "not_transferred": "غير منقول",
                "transferring": "جاري النقل",
                "transferred": "تم النقل",
                "failed": "فشل"
            }.get(a.transfer_status, a.transfer_status)
            transfer_item = QTableWidgetItem(transfer_text)
            if a.transfer_status == "transferred":
                transfer_item.setBackground(QColor("#D1FAE5"))
            elif a.transfer_status == "failed":
                transfer_item.setBackground(QColor("#FEE2E2"))
            self.recent_table.setItem(i, 3, transfer_item)

    def _update_stats(self):
        """Update statistics display."""
        stats = self.assignment_service.get_assignment_statistics()
        total = stats.get("total", 0)
        pending = stats.get("pending_transfers", 0)
        transferred = stats.get("by_transfer", {}).get("transferred", 0)

        self.stats_label.setText(
            f"إجمالي التعيينات: {total} | في الانتظار: {pending} | تم النقل: {transferred}"
        )

    def refresh(self, data=None):
        """Refresh the page."""
        self._load_buildings()
        self._load_recent_assignments()
        self._update_stats()

    def update_language(self, is_arabic: bool):
        """Update UI language."""
        pass
