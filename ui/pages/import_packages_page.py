# -*- coding: utf-8 -*-
"""
Import Packages Page — UC-003 import pipeline list view.
Two classes: ImportPackagesPage (container) and ImportPackagesListPage (table).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMenu, QAction, QStackedWidget, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QColor, QFont

from ui.components.custom_button import CustomButton
from ui.components.primary_button import PrimaryButton
from ui.components.toast import Toast
from ui.design_system import PageDimensions, Colors, ButtonDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from controllers.import_controller import ImportController
from utils.logger import get_logger

logger = get_logger(__name__)

# Status display mapping: API status -> (Arabic label, color)
_STATUS_DISPLAY = {
    "Uploaded": ("\u062a\u0645 \u0627\u0644\u0631\u0641\u0639", "#3890DF"),
    "Staged": ("\u062a\u0645 \u0627\u0644\u062a\u062f\u0631\u064a\u062c", "#F59E0B"),
    "Validated": ("\u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642", "#10B981"),
    "Approved": ("\u062a\u0645\u062a \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629", "#059669"),
    "Committed": ("\u062a\u0645 \u0627\u0644\u0625\u062f\u062e\u0627\u0644", "#10B981"),
    "Failed": ("\u0641\u0634\u0644", "#EF4444"),
    "Cancelled": ("\u0645\u0644\u063a\u0627\u0629", "#9CA3AF"),
    "Quarantined": ("\u0645\u062d\u062c\u0648\u0631\u0629", "#DC2626"),
}


class ImportPackagesListPage(QWidget):
    """Import Packages list with table, filters, and pagination."""

    open_wizard = pyqtSignal()
    view_package = pyqtSignal(str)

    def __init__(self, import_controller, i18n, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self.i18n = i18n
        self._packages = []
        self._current_page = 1
        self._rows_per_page = 11
        self._total_count = 0
        self._total_pages = 1
        self._status_filter = ""
        self._user_role = "admin"

        self._setup_ui()

    def _setup_ui(self):
        """Setup list UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        layout.setSpacing(15)

        # Header row: title + upload button
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        title = QLabel("\u062d\u0632\u0645 \u0627\u0644\u0627\u0633\u062a\u064a\u0631\u0627\u062f")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        top_row.addWidget(title)

        top_row.addStretch()

        self.upload_btn = PrimaryButton("\u0631\u0641\u0639 \u0645\u0644\u0641 \u062c\u062f\u064a\u062f", icon_name="icon")
        self.upload_btn.clicked.connect(self.open_wizard.emit)
        top_row.addWidget(self.upload_btn)

        layout.addLayout(top_row)

        # White table card
        table_card = QFrame()
        table_card.setFixedHeight(708)
        table_card.setStyleSheet("background-color: white; border-radius: 16px;")
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(10, 10, 10, 10)

        # Filter bar inside card
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(5, 0, 5, 5)
        filter_row.setSpacing(10)

        self._status_combo = QComboBox()
        self._status_combo.setFont(create_font(size=FontManager.SIZE_BODY))
        self._status_combo.setMinimumWidth(200)
        self._status_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #f0f7ff;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)
        self._status_combo.addItem("\u062c\u0645\u064a\u0639 \u0627\u0644\u062d\u0627\u0644\u0627\u062a", "")
        self._status_combo.addItem("\u062a\u0645 \u0627\u0644\u0631\u0641\u0639", "Uploaded")
        self._status_combo.addItem("\u062a\u0645 \u0627\u0644\u062a\u062f\u0631\u064a\u062c", "Staged")
        self._status_combo.addItem("\u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642", "Validated")
        self._status_combo.addItem("\u062a\u0645\u062a \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629", "Approved")
        self._status_combo.addItem("\u062a\u0645 \u0627\u0644\u0625\u062f\u062e\u0627\u0644", "Committed")
        self._status_combo.addItem("\u0641\u0634\u0644", "Failed")
        self._status_combo.addItem("\u0645\u0644\u063a\u0627\u0629", "Cancelled")
        self._status_combo.addItem("\u0645\u062d\u062c\u0648\u0631\u0629", "Quarantined")
        self._status_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        filter_row.addWidget(self._status_combo)

        filter_row.addStretch()
        card_layout.addLayout(filter_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setRowCount(11)
        self.table.setLayoutDirection(Qt.RightToLeft)

        headers = [
            "\u0627\u0633\u0645 \u0627\u0644\u0645\u0644\u0641",
            "\u0627\u0644\u062d\u0627\u0644\u0629",
            "\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0631\u0641\u0639",
            "\u0639\u062f\u062f \u0627\u0644\u0633\u062c\u0644\u0627\u062a",
            "\u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645",
            "",
        ]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            self.table.setHorizontalHeaderItem(i, item)

        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                background-color: white;
                font-size: 10.5pt;
                font-weight: 400;
                color: #212B36;
            }}
            QTableWidget::item {{
                padding: 8px 15px;
                border-bottom: 1px solid #F0F0F0;
                color: #212B36;
                font-size: 10.5pt;
                font-weight: 400;
            }}
            QTableWidget::item:hover {{
                background-color: #FAFBFC;
            }}
            QHeaderView {{
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }}
            QHeaderView::section {{
                background-color: #F8F9FA;
                padding: 12px;
                padding-left: 30px;
                border: none;
                color: #637381;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }}
            QHeaderView::section:hover {{
                background-color: #EBEEF2;
            }}
        """ + StyleManager.scrollbar())

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setFixedHeight(56)
        header.setStretchLastSection(True)

        # Column widths
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 280)

        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 140)

        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 160)

        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(3, 120)

        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.resizeSection(4, 180)

        header.setSectionResizeMode(5, QHeaderView.Stretch)

        # Row height
        vertical_header = self.table.verticalHeader()
        vertical_header.setVisible(False)
        vertical_header.setDefaultSectionSize(52)

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

        self.prev_btn = QPushButton(">")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBEEF2;
            }
            QPushButton:disabled {
                color: #C1C7CD;
            }
        """)
        self.prev_btn.clicked.connect(self._go_to_previous_page)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("<")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 14pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBEEF2;
            }
            QPushButton:disabled {
                color: #C1C7CD;
            }
        """)
        self.next_btn.clicked.connect(self._go_to_next_page)
        nav_layout.addWidget(self.next_btn)

        footer.addWidget(nav_container)

        # Counter label
        self.page_label = QLabel("1-11 of 0")
        self.page_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400;")
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
            QFrame:hover {
                background-color: #EBEEF2;
            }
        """)
        rows_container.setCursor(Qt.PointingHandCursor)
        rows_layout = QHBoxLayout(rows_container)
        rows_layout.setContentsMargins(4, 2, 4, 2)
        rows_layout.setSpacing(4)

        self.rows_number = QLabel("11")
        self.rows_number.setStyleSheet(
            "color: #637381; font-size: 10pt; font-weight: 400; "
            "background: transparent; border: none;"
        )
        rows_layout.addWidget(self.rows_number)

        rows_container.mousePressEvent = lambda e: self._show_page_selection_menu(rows_container)
        footer.addWidget(rows_container)

        rows_label = QLabel("Rows per page:")
        rows_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400;")
        footer.addWidget(rows_label)

        footer.addStretch()

        card_layout.addWidget(footer_frame)

        layout.addWidget(table_card)

    # -- Data loading --

    def _on_status_filter_changed(self, index):
        """Handle status filter combo change."""
        self._status_filter = self._status_combo.currentData() or ""
        self._current_page = 1
        self._load_packages()

    def _load_packages(self):
        """Fetch packages from API and populate table."""
        result = self.import_controller.get_packages(
            page=self._current_page,
            page_size=self._rows_per_page,
            status_filter=self._status_filter or None,
        )

        items = []
        total_count = 0

        if result.success:
            data = result.data or {}
            if isinstance(data, dict):
                items = data.get("items", [])
                total_count = data.get("totalCount", len(items))
            elif isinstance(data, list):
                items = data
                total_count = len(items)
        else:
            logger.error(f"Failed to load packages: {result.message}")

        self._packages = items
        self._total_count = total_count
        self._total_pages = max(1, (total_count + self._rows_per_page - 1) // self._rows_per_page)

        self._populate_table(items, total_count)

    def _populate_table(self, items, total_count):
        """Fill the table with package data."""
        # Clear all cells
        self.table.clearSpans()
        for row in range(11):
            for col in range(6):
                self.table.setItem(row, col, QTableWidgetItem(""))

        if not items:
            self.table.setSpan(0, 0, 11, 6)
            empty_item = QTableWidgetItem("\u0644\u0627 \u062a\u0648\u062c\u062f \u062d\u0632\u0645 \u0645\u0637\u0627\u0628\u0642\u0629")
            empty_item.setTextAlignment(Qt.AlignCenter)
            empty_item.setForeground(QColor("#9CA3AF"))
            self.table.setItem(0, 0, empty_item)
            self.page_label.setText("0-0 of 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        for idx, pkg in enumerate(items):
            if idx >= 11:
                break

            # File name
            file_name = pkg.get("fileName") or pkg.get("file_name") or ""
            self.table.setItem(idx, 0, QTableWidgetItem(file_name))

            # Status with color
            status_raw = pkg.get("status") or ""
            display_text, color = _STATUS_DISPLAY.get(status_raw, (status_raw, "#637381"))
            status_item = QTableWidgetItem(display_text)
            status_item.setForeground(QColor(color))
            status_item.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
            self.table.setItem(idx, 1, status_item)

            # Upload date
            upload_date = pkg.get("uploadDate") or pkg.get("createdAt") or pkg.get("created_at") or ""
            date_str = str(upload_date)[:10] if upload_date else ""
            self.table.setItem(idx, 2, QTableWidgetItem(date_str))

            # Record count
            record_count = pkg.get("recordCount") or pkg.get("record_count") or ""
            self.table.setItem(idx, 3, QTableWidgetItem(str(record_count)))

            # User
            user_name = pkg.get("uploadedBy") or pkg.get("uploaded_by") or pkg.get("userName") or ""
            self.table.setItem(idx, 4, QTableWidgetItem(user_name))

            # Actions column
            actions_item = QTableWidgetItem("\u22ee")
            actions_item.setTextAlignment(Qt.AlignCenter)
            dots_font = create_font(size=14, weight=FontManager.WEIGHT_BOLD)
            actions_item.setFont(dots_font)
            actions_item.setForeground(QColor("#637381"))
            self.table.setItem(idx, 5, actions_item)

        # Update pagination
        start_idx = (self._current_page - 1) * self._rows_per_page
        end_idx = min(start_idx + len(items), total_count)
        if total_count > 0:
            self.page_label.setText(f"{start_idx + 1}-{end_idx} of {total_count}")
        else:
            self.page_label.setText("0-0 of 0")

        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)

    # -- Cell click / context menu --

    def _on_cell_clicked(self, row, col):
        """Handle cell click on actions column."""
        if col != 5:
            return

        item = self.table.item(row, 0)
        if not item or not item.text().strip():
            return

        if row >= len(self._packages):
            return

        pkg = self._packages[row]
        self._show_actions_menu(row, col, pkg)

    def _show_actions_menu(self, row, col, pkg):
        """Show context menu for a package row."""
        item = self.table.item(row, col)
        if not item:
            return

        rect = self.table.visualItemRect(item)
        position = QPoint(rect.right() - 10, rect.bottom())

        pkg_id = str(pkg.get("id") or pkg.get("packageId") or "")

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

        # View
        view_action = QAction("\u0639\u0631\u0636", self)
        view_action.triggered.connect(lambda: self.view_package.emit(pkg_id))
        menu.addAction(view_action)

        # Cancel
        cancel_action = QAction("\u0625\u0644\u063a\u0627\u0621", self)
        cancel_action.triggered.connect(lambda: self._cancel_package(pkg_id))
        menu.addAction(cancel_action)

        # Quarantine
        quarantine_action = QAction("\u062d\u062c\u0631", self)
        quarantine_action.triggered.connect(lambda: self._quarantine_package(pkg_id))
        menu.addAction(quarantine_action)

        # Reset commit (admin only)
        if self._user_role == "admin":
            reset_action = QAction("\u0625\u0639\u0627\u062f\u0629 \u062a\u0639\u064a\u064a\u0646", self)
            reset_action.triggered.connect(lambda: self._reset_commit(pkg_id))
            menu.addAction(reset_action)

        menu.exec_(self.table.viewport().mapToGlobal(position))

    # -- Package actions --

    def _cancel_package(self, package_id):
        """Cancel a package."""
        result = self.import_controller.cancel_package(package_id)
        if result.success:
            Toast.show_toast(self, result.message_ar or "\u062a\u0645 \u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062d\u0632\u0645\u0629", Toast.SUCCESS)
            self._load_packages()
        else:
            Toast.show_toast(self, result.message_ar or "\u0641\u0634\u0644 \u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u062d\u0632\u0645\u0629", Toast.ERROR)

    def _quarantine_package(self, package_id):
        """Quarantine a package."""
        result = self.import_controller.quarantine_package(package_id)
        if result.success:
            Toast.show_toast(self, result.message_ar or "\u062a\u0645 \u062d\u062c\u0631 \u0627\u0644\u062d\u0632\u0645\u0629", Toast.SUCCESS)
            self._load_packages()
        else:
            Toast.show_toast(self, result.message_ar or "\u0641\u0634\u0644 \u062d\u062c\u0631 \u0627\u0644\u062d\u0632\u0645\u0629", Toast.ERROR)

    def _reset_commit(self, package_id):
        """Reset a stuck commit (admin only)."""
        result = self.import_controller.reset_commit(package_id)
        if result.success:
            Toast.show_toast(self, result.message_ar or "\u062a\u0645 \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0639\u064a\u064a\u0646", Toast.SUCCESS)
            self._load_packages()
        else:
            Toast.show_toast(self, result.message_ar or "\u0641\u0634\u0644 \u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0639\u064a\u064a\u0646", Toast.ERROR)

    # -- Pagination --

    def _go_to_previous_page(self):
        """Go to previous page."""
        if self._current_page > 1:
            self._current_page -= 1
            self._load_packages()

    def _go_to_next_page(self):
        """Go to next page."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_packages()

    def _show_page_selection_menu(self, parent_widget):
        """Show dropdown to select page number."""
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

        for page_num in range(1, self._total_pages + 1):
            action = menu.addAction(f"Page {page_num}")
            if page_num == self._current_page:
                action.setEnabled(False)
            else:
                action.triggered.connect(lambda checked, p=page_num: self._go_to_page(p))

        menu.exec_(parent_widget.mapToGlobal(parent_widget.rect().bottomLeft()))

    def _go_to_page(self, page_num):
        """Go to specific page."""
        if 1 <= page_num <= self._total_pages:
            self._current_page = page_num
            self._load_packages()

    # -- Public API --

    def refresh(self):
        """Refresh list from API."""
        self._load_packages()

    def configure_for_role(self, role):
        """Enable/disable actions based on user role."""
        self._user_role = role
        can_upload = role in {"admin", "data_manager"}
        self.upload_btn.setVisible(can_upload)
        self.upload_btn.setEnabled(can_upload)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()


class ImportPackagesPage(QWidget):
    """Main container with QStackedWidget for import packages."""

    open_wizard = pyqtSignal()
    view_package = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None, **kwargs):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_controller = ImportController(db)

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        self.setStyleSheet(StyleManager.page_background())
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stacked = QStackedWidget()

        # Page 0: List
        self.list_page = ImportPackagesListPage(
            self.import_controller,
            self.i18n,
            self,
        )
        self.list_page.open_wizard.connect(self.open_wizard.emit)
        self.list_page.view_package.connect(self.view_package.emit)
        self.stacked.addWidget(self.list_page)

        layout.addWidget(self.stacked)

    def refresh(self, data=None):
        """Refresh."""
        self.list_page.refresh()
        self.stacked.setCurrentIndex(0)

    def configure_for_role(self, role):
        """Delegate role configuration to inner list page."""
        self.list_page.configure_for_role(role)
