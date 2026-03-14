# -*- coding: utf-8 -*-
"""
Import Packages Page — UC-003 import pipeline list view.
Two classes: ImportPackagesPage (container) and ImportPackagesListPage (table).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMenu, QAction, QStackedWidget, QPushButton,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import QColor, QFont

from ui.components.custom_button import CustomButton
from ui.components.primary_button import PrimaryButton
from ui.design_system import PageDimensions, Colors, ButtonDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from controllers.import_controller import ImportController
from services.vocab_service import get_label as vocab_get_label, get_options as vocab_get_options
from utils.logger import get_logger

logger = get_logger(__name__)

# Colors per status code (UI-specific — labels come from vocab_service)
_STATUS_COLORS = {
    1:  "#6B7280",   # Pending — gray
    2:  "#3890DF",   # Validating — blue
    3:  "#F59E0B",   # Staging — amber
    4:  "#EF4444",   # Validation Failed — red
    5:  "#DC2626",   # Quarantined — dark red
    6:  "#8B5CF6",   # Reviewing Conflicts — purple
    7:  "#059669",   # Ready To Commit — dark green
    8:  "#3890DF",   # Committing — blue
    9:  "#10B981",   # Completed — green
    10: "#EF4444",   # Failed — red
    11: "#F59E0B",   # Partially Completed — amber
    12: "#9CA3AF",   # Cancelled — gray
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
        self._dots_count = 0

        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()

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

        self.upload_btn = PrimaryButton("معالجة حزمة جديدة", icon_name="icon")
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
        self._status_combo.setEditable(True)
        self._status_combo.lineEdit().setReadOnly(True)
        self._status_combo.lineEdit().setAlignment(Qt.AlignRight)
        self._status_combo.setFixedHeight(42)
        self._status_combo.setMinimumWidth(220)

        import os
        arrow_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "images", "down.png"
        )
        arrow_css = (
            f"image: url({arrow_path.replace(os.sep, '/')}); width: 12px; height: 12px;"
            if os.path.exists(arrow_path)
            else "border-left: none;"
        )
        self._status_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #f0f7ff;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                padding: 8px 14px;
                padding-left: 35px;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                color: #212B36;
            }}
            QComboBox:hover {{
                border-color: #93C5FD;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                {arrow_css}
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                background-color: white;
                selection-background-color: #EFF6FF;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 32px;
            }}
            QScrollBar:vertical {{
                width: 0px;
            }}
            QScrollBar:horizontal {{
                height: 0px;
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                padding: 0px;
                color: #212B36;
            }}
        """)

        self._status_combo.addItem("جميع الحالات", "")
        for code, label in vocab_get_options("import_status"):
            self._status_combo.addItem(label, str(code))
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
            "اسم الملف",
            "الحالة",
            "التاريخ",
            "المحتوى",
            "الجهاز",
            "",
        ]
        for i, text in enumerate(headers):
            item = QTableWidgetItem(text)
            self.table.setHorizontalHeaderItem(i, item)

        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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
        header.setStretchLastSection(False)

        # Column widths: col 0 stretches, rest fixed
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 150)

        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 150)

        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(3, 240)

        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.resizeSection(4, 120)

        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.resizeSection(5, 50)

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

        rows_label = QLabel("عدد الصفوف:")
        rows_label.setStyleSheet("color: #637381; font-size: 10pt; font-weight: 400;")
        footer.addWidget(rows_label)

        footer.addStretch()

        card_layout.addWidget(footer_frame)

        layout.addWidget(table_card)

    # -- Loading overlay -------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 200); }")
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(240, 90)
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(6)

        self._loading_label = QLabel("جاري التحميل...")
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_label)

        self._loading_dots_label = QLabel("")
        self._loading_dots_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._loading_dots_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_dots_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_dots_label)

        overlay_layout.addWidget(card)

        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)

        return overlay

    def _show_loading(self, message: str = "جاري التحميل..."):
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)
        QApplication.processEvents()

    def _hide_loading(self):
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

    def _animate_dots(self):
        self._dots_count = (self._dots_count + 1) % 4
        self._loading_dots_label.setText("." * self._dots_count)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Data loading --

    def _on_status_filter_changed(self, index):
        """Handle status filter combo change."""
        self._status_filter = self._status_combo.currentData() or ""
        self._current_page = 1
        self._load_packages()

    def _load_packages(self):
        """Fetch packages from API and populate table."""
        self._show_loading("جاري تحميل الحزم...")

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
            from ui.components.message_dialog import MessageDialog
            MessageDialog.error(self, "خطأ", result.message_ar or "فشل تحميل الحزم")

        self._packages = items
        self._total_count = total_count
        self._total_pages = max(1, (total_count + self._rows_per_page - 1) // self._rows_per_page)

        self._populate_table(items, total_count)
        self._hide_loading()

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

            # Col 0: File name
            file_name = pkg.get("fileName") or ""
            self.table.setItem(idx, 0, QTableWidgetItem(file_name))

            # Col 1: Status (int -> Arabic label from vocab + color)
            status_raw = pkg.get("status", 0)
            if isinstance(status_raw, str) and status_raw.isdigit():
                status_raw = int(status_raw)
            display_text = vocab_get_label("import_status", status_raw)
            color = _STATUS_COLORS.get(status_raw, "#637381")
            status_item = QTableWidgetItem(display_text)
            status_item.setForeground(QColor(color))
            status_item.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
            self.table.setItem(idx, 1, status_item)

            # Col 2: Date
            date_raw = pkg.get("packageCreatedDate") or pkg.get("createdAtUtc") or ""
            date_str = str(date_raw)[:10] if date_raw else ""
            self.table.setItem(idx, 2, QTableWidgetItem(date_str))

            # Col 3: Content summary
            buildings = pkg.get("buildingCount", 0) or 0
            units = pkg.get("propertyUnitCount", 0) or 0
            persons = pkg.get("personCount", 0) or 0
            content = f"{buildings} \u0645\u0628\u0627\u0646\u064a \u2022 {units} \u0648\u062d\u062f\u0629 \u2022 {persons} \u0623\u0634\u062e\u0627\u0635"
            self.table.setItem(idx, 3, QTableWidgetItem(content))

            # Col 4: Device ID
            device_id = pkg.get("deviceId") or ""
            device_str = str(device_id)[:20] if device_id else ""
            self.table.setItem(idx, 4, QTableWidgetItem(device_str))

            # Col 5: Actions
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
        from ui.components.message_dialog import MessageDialog
        if result.success:
            MessageDialog.success(self, "تم الإلغاء", result.message_ar or "تم إلغاء الحزمة")
            self._load_packages()
        else:
            MessageDialog.error(self, "خطأ", result.message_ar or "فشل إلغاء الحزمة")

    def _quarantine_package(self, package_id):
        """Quarantine a package."""
        result = self.import_controller.quarantine_package(package_id)
        from ui.components.message_dialog import MessageDialog
        if result.success:
            MessageDialog.success(self, "تم الحجر", result.message_ar or "تم حجر الحزمة")
            self._load_packages()
        else:
            MessageDialog.error(self, "خطأ", result.message_ar or "فشل حجر الحزمة")

    def _reset_commit(self, package_id):
        """Reset a stuck commit (admin only)."""
        result = self.import_controller.reset_commit(package_id)
        from ui.components.message_dialog import MessageDialog
        if result.success:
            MessageDialog.success(self, "تم إعادة التعيين", result.message_ar or "تم إعادة التعيين")
            self._load_packages()
        else:
            MessageDialog.error(self, "خطأ", result.message_ar or "فشل إعادة التعيين")

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
