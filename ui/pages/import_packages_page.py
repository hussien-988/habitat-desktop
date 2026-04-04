# -*- coding: utf-8 -*-
"""Import packages page — dark header design system, table layout, spinner overlay."""

import math
import random
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMenu, QAction, QStackedWidget, QPushButton,
    QGraphicsDropShadowEffect, QApplication, QAbstractItemView,
    QSizePolicy, QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath,
)

from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.nav_style_tab import NavStyleTab
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.error_handler import ErrorHandler
from ui.design_system import PageDimensions, Colors
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from controllers.import_controller import ImportController
from services.vocab_service import get_label as vocab_get_label, get_options as vocab_get_options
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger

logger = get_logger(__name__)

# Status code -> color
_STATUS_COLORS = {
    1:  "#6B7280",   # Pending
    2:  "#3890DF",   # Validating
    3:  "#F59E0B",   # Staging
    4:  "#EF4444",   # Validation Failed
    5:  "#DC2626",   # Quarantined
    6:  "#8B5CF6",   # Reviewing Conflicts
    7:  "#059669",   # Ready To Commit
    8:  "#3890DF",   # Committing
    9:  "#10B981",   # Completed
    10: "#EF4444",   # Failed
    11: "#F59E0B",   # Partially Completed
    12: "#9CA3AF",   # Cancelled
}

# Status code -> bg color for pill badges
_STATUS_BG = {
    1:  "rgba(107,114,128,0.12)",
    2:  "rgba(56,144,223,0.12)",
    3:  "rgba(245,158,11,0.12)",
    4:  "rgba(239,68,68,0.12)",
    5:  "rgba(220,38,38,0.12)",
    6:  "rgba(139,92,246,0.12)",
    7:  "rgba(5,150,105,0.12)",
    8:  "rgba(56,144,223,0.12)",
    9:  "rgba(16,185,129,0.12)",
    10: "rgba(239,68,68,0.12)",
    11: "rgba(245,158,11,0.12)",
    12: "rgba(156,163,175,0.12)",
}

_DARK_COMBO_STYLE = """
    QComboBox {
        background: rgba(10, 22, 40, 140);
        color: white;
        border: 1px solid rgba(56, 144, 223, 35);
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 10pt;
        min-width: 200px;
    }
    QComboBox:hover { border-color: rgba(56, 144, 223, 80); }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid rgba(255, 255, 255, 0.5);
        margin-right: 8px;
    }
    QComboBox QAbstractItemView {
        background: #0F1E36;
        color: white;
        border: 1px solid rgba(56, 144, 223, 40);
        border-radius: 6px;
        selection-background-color: rgba(56, 144, 223, 50);
        outline: none;
        padding: 4px;
    }
"""

_ADD_BTN_STYLE = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #2E7BD6, stop:1 #3890DF);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 7px 18px;
        font-size: 10pt;
        font-weight: 600;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #3688E3, stop:1 #4A9EED);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #2568B8, stop:1 #2E7BD6);
    }
"""

_NAV_BTN_STYLE = """
    QPushButton {{
        background: {bg};
        border: 1px solid rgba(56, 144, 223, 30);
        border-radius: 6px;
        color: {fg};
        font-size: 13pt;
        font-weight: bold;
    }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:disabled {{
        background: #E8EDF2;
        color: #B0BEC5;
        border-color: #DDE3EA;
    }}
"""

_TABLE_CARD_STYLE = """
    QFrame#tableCard {
        background-color: white;
        border-radius: 16px;
        border: 1px solid #E8EDF2;
    }
"""


class _EmptyStatePackages(QWidget):
    """Dark constellation-themed empty state for import packages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(340)
        self._anim_start = time.time()

        random.seed(77)
        self._particles = []
        for _ in range(8):
            self._particles.append({
                "x": random.uniform(0.1, 0.9),
                "y": random.uniform(0.1, 0.9),
                "speed": random.uniform(0.3, 0.7),
                "phase": random.uniform(0, math.tau),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setFixedSize(72, 72)
        self._icon.setStyleSheet(
            "background: rgba(56,144,223,0.08); border-radius: 36px;"
        )
        self._icon.setText("\U0001F4E6")
        self._icon.setFont(create_font(size=28))
        layout.addWidget(self._icon, 0, Qt.AlignCenter)

        self._title = QLabel(tr("page.import_packages.no_packages"))
        self._title.setFont(create_font(size=14, weight=QFont.Bold))
        self._title.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        self._subtitle = QLabel(tr("page.import_packages.no_packages_hint"))
        self._subtitle.setFont(create_font(size=10))
        self._subtitle.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent;")
        self._subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._subtitle)

    def set_title(self, text: str):
        self._title.setText(text)

    def set_subtitle(self, text: str):
        self._subtitle.setText(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self._anim_start

        path = QPainterPath()
        r = 16.0
        path.addRoundedRect(0, 0, w, h, r, r)

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#0E2035"))
        grad.setColorAt(0.5, QColor("#132D50"))
        grad.setColorAt(1.0, QColor("#1A3860"))
        painter.fillPath(path, grad)
        painter.setClipPath(path)

        # Grid
        painter.setPen(QPen(QColor(56, 144, 223, 12), 1))
        for x in range(60, w, 60):
            painter.drawLine(x, 0, x, h)
        for y in range(60, h, 60):
            painter.drawLine(0, y, w, y)

        # Particles
        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.01 * math.sin(t * p["speed"] + p["phase"])) * w)
            py = int((p["y"] + 0.008 * math.cos(t * p["speed"] * 0.7 + p["phase"])) * h)
            px = max(4, min(w - 4, px))
            py = max(4, min(h - 4, py))
            positions.append((px, py))
            alpha = 30 + int(15 * math.sin(t * 1.2 + p["phase"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 180:
                    alpha = int(12 * (1 - dist / 180))
                    painter.setPen(QPen(QColor(139, 172, 200, alpha), 1))
                    painter.drawLine(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1],
                    )

        painter.setClipping(False)
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()


class ImportPackagesPage(QWidget):
    """Import Packages page with dark header, table, pagination, spinner overlay."""

    open_wizard = pyqtSignal()
    view_package = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None, **kwargs):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_controller = ImportController(db)

        self._packages = []
        self._current_page = 1
        self._rows_per_page = 20
        self._total_count = 0
        self._total_pages = 1
        self._status_filter = ""
        self._user_role = "admin"
        self._loading = False

        self._setup_ui()

    # -- UI Setup ----------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet("background-color: #f0f7ff;")
        self.setLayoutDirection(get_layout_direction())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Dark header
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.import_packages.title"))

        self._stat_total = StatPill(tr("page.import_packages.stat_total"))
        self._stat_total.set_count(0)
        self._header.add_stat_pill(self._stat_total)

        # Upload button
        self._upload_btn = QPushButton(tr("page.import_packages.process_new"))
        self._upload_btn.setCursor(Qt.PointingHandCursor)
        self._upload_btn.setStyleSheet(_ADD_BTN_STYLE)
        self._upload_btn.clicked.connect(self._on_upload_clicked)
        self._header.add_action_widget(self._upload_btn)

        # Status filter combo in row2
        self._status_combo = QComboBox()
        self._status_combo.setLayoutDirection(get_layout_direction())
        self._status_combo.setStyleSheet(_DARK_COMBO_STYLE)
        self._status_combo.addItem(tr("page.import_packages.all_statuses"), "")
        for code, label in vocab_get_options("import_status"):
            self._status_combo.addItem(label, str(code))
        self._status_combo.currentIndexChanged.connect(self._on_status_filter_changed)
        self._header.add_row2_widget(self._status_combo)

        root.addWidget(self._header)

        # Accent line
        self._accent = AccentLine()
        root.addWidget(self._accent)

        # Content area
        content_area = QWidget()
        content_area.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 16,
            PageDimensions.content_padding_h(), 16,
        )
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Page 0: table card
        self._table_card = self._build_table_card()
        self._stack.addWidget(self._table_card)

        # Page 1: empty state
        self._empty_state = _EmptyStatePackages()
        self._stack.addWidget(self._empty_state)

        content_layout.addWidget(self._stack)
        root.addWidget(content_area, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _build_table_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("tableCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setStyleSheet(_TABLE_CARD_STYLE)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 18))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setRowCount(0)
        self.table.setLayoutDirection(get_layout_direction())
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setStyleSheet(self._table_stylesheet())

        headers = self._header_labels()
        for i, text in enumerate(headers):
            self.table.setHorizontalHeaderItem(i, QTableWidgetItem(text))

        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.setFixedHeight(52)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.resizeSection(5, 50)

        vh = self.table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(50)

        self.table.cellClicked.connect(self._on_cell_clicked)
        card_layout.addWidget(self.table)

        # Footer / pagination
        footer = self._build_footer()
        card_layout.addWidget(footer)

        return card

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(54)
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-top: 1px solid #E8EDF2;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Prev button
        self._prev_btn = QPushButton("\u25B7")
        self._prev_btn.setFixedSize(34, 34)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setStyleSheet(
            _NAV_BTN_STYLE.format(bg="#F0F7FF", fg="#3890DF", hover="#E0EFFF")
        )
        self._prev_btn.clicked.connect(self._go_prev)
        layout.addWidget(self._prev_btn)

        # Page info
        self._page_label = QLabel("0")
        self._page_label.setFont(create_font(size=10))
        self._page_label.setStyleSheet("color: #546E7A; background: transparent;")
        layout.addWidget(self._page_label)

        # Next button
        self._next_btn = QPushButton("\u25C1")
        self._next_btn.setFixedSize(34, 34)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setStyleSheet(
            _NAV_BTN_STYLE.format(bg="#F0F7FF", fg="#3890DF", hover="#E0EFFF")
        )
        self._next_btn.clicked.connect(self._go_next)
        layout.addWidget(self._next_btn)

        layout.addStretch()

        # Rows per page
        self._rows_label = QLabel(tr("page.import_packages.rows_per_page"))
        self._rows_label.setFont(create_font(size=9))
        self._rows_label.setStyleSheet("color: #78909C; background: transparent;")
        layout.addWidget(self._rows_label)

        self._rows_btn = QPushButton(str(self._rows_per_page))
        self._rows_btn.setFixedSize(44, 30)
        self._rows_btn.setCursor(Qt.PointingHandCursor)
        self._rows_btn.setStyleSheet("""
            QPushButton {
                background: #F0F7FF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                color: #546E7A;
                font-size: 10pt;
            }
            QPushButton:hover { background: #E0EFFF; }
        """)
        self._rows_btn.clicked.connect(self._show_rows_menu)
        layout.addWidget(self._rows_btn)

        return footer

    @staticmethod
    def _header_labels():
        return [
            tr("page.import_packages.col_filename"),
            tr("page.import_packages.col_status"),
            tr("page.import_packages.col_date"),
            tr("page.import_packages.col_content"),
            tr("page.import_packages.col_device"),
            "",
        ]

    @staticmethod
    def _table_stylesheet():
        return """
            QTableWidget {
                border: none;
                background-color: white;
                font-size: 10.5pt;
                color: #212B36;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QTableWidget::item {
                padding: 8px 15px;
                border-bottom: 1px solid #F0F4F8;
                color: #212B36;
                font-size: 10.5pt;
            }
            QTableWidget::item:hover {
                background-color: #F5F9FF;
            }
            QHeaderView {
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            QHeaderView::section {
                background-color: #F0F7FF;
                padding: 10px 15px;
                border: none;
                border-bottom: 2px solid #E0EFFF;
                color: #3890DF;
                font-weight: 600;
                font-size: 10pt;
            }
            QHeaderView::section:hover {
                background-color: #E0EFFF;
            }
        """ + StyleManager.scrollbar()

    # -- Data loading ------------------------------------------------------

    def _on_status_filter_changed(self, _index):
        self._status_filter = self._status_combo.currentData() or ""
        self._current_page = 1
        self._load_packages()

    def _load_packages(self):
        if self._loading:
            return
        self._loading = True
        self._spinner.show_loading(tr("page.import_packages.loading_packages"))

        try:
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
                logger.error("Failed to load packages: %s", result.message)
                ErrorHandler.show_error(
                    self,
                    result.message_ar or tr("page.import_packages.load_failed"),
                )

            self._packages = items
            self._total_count = total_count
            self._total_pages = max(1, (total_count + self._rows_per_page - 1) // self._rows_per_page)

            self._stat_total.set_count(total_count)

            if items:
                self._populate_table(items, total_count)
                self._stack.setCurrentIndex(0)
            else:
                self._stack.setCurrentIndex(1)

            self._update_pagination()
        except Exception as exc:
            logger.error("Load packages exception: %s", exc)
        finally:
            self._loading = False
            self._spinner.hide_loading()

    def _populate_table(self, items, total_count):
        self.table.setRowCount(len(items))

        for idx, pkg in enumerate(items):
            # Col 0: File name
            file_name = pkg.get("fileName") or ""
            name_item = QTableWidgetItem(file_name)
            name_item.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            self.table.setItem(idx, 0, name_item)

            # Col 1: Status badge
            status_raw = pkg.get("status", 0)
            if isinstance(status_raw, str) and status_raw.isdigit():
                status_raw = int(status_raw)
            display_text = vocab_get_label("import_status", status_raw)
            color = _STATUS_COLORS.get(status_raw, "#637381")
            bg = _STATUS_BG.get(status_raw, "rgba(107,114,128,0.10)")

            status_widget = QWidget()
            status_widget.setStyleSheet("background: transparent;")
            sl = QHBoxLayout(status_widget)
            sl.setContentsMargins(4, 4, 4, 4)
            sl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            badge = QLabel(display_text)
            badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            badge.setStyleSheet(
                f"color: {color}; background: {bg}; "
                f"border-radius: 10px; padding: 3px 10px;"
            )
            badge.setAlignment(Qt.AlignCenter)
            sl.addWidget(badge)

            self.table.setCellWidget(idx, 1, status_widget)

            # Col 2: Date
            date_raw = pkg.get("packageCreatedDate") or pkg.get("createdAtUtc") or ""
            date_str = str(date_raw)[:10] if date_raw else ""
            date_item = QTableWidgetItem(date_str)
            date_item.setForeground(QColor("#78909C"))
            self.table.setItem(idx, 2, date_item)

            # Col 3: Content summary
            buildings = pkg.get("buildingCount", 0) or 0
            units = pkg.get("propertyUnitCount", 0) or 0
            persons = pkg.get("personCount", 0) or 0
            content = tr(
                "page.import_packages.content_summary",
                buildings=buildings, units=units, persons=persons,
            )
            content_item = QTableWidgetItem(content)
            content_item.setForeground(QColor("#546E7A"))
            self.table.setItem(idx, 3, content_item)

            # Col 4: Device ID
            device_id = pkg.get("deviceId") or ""
            device_str = str(device_id)[:20] if device_id else ""
            device_item = QTableWidgetItem(device_str)
            device_item.setForeground(QColor("#90A4AE"))
            device_item.setFont(create_font(size=9))
            self.table.setItem(idx, 4, device_item)

            # Col 5: Actions menu trigger
            actions_item = QTableWidgetItem("\u22EE")
            actions_item.setTextAlignment(Qt.AlignCenter)
            actions_item.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
            actions_item.setForeground(QColor("#90A4AE"))
            self.table.setItem(idx, 5, actions_item)

    # -- Pagination --------------------------------------------------------

    def _update_pagination(self):
        if self._total_count == 0:
            self._page_label.setText("0")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return

        start = (self._current_page - 1) * self._rows_per_page + 1
        end = min(start + self._rows_per_page - 1, self._total_count)
        self._page_label.setText(f"{start}-{end} / {self._total_count}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    def _go_prev(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_packages()

    def _go_next(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_packages()

    def _show_rows_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #546E7A;
                font-size: 10pt;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F0F7FF;
                color: #3890DF;
            }
        """)

        for size in (10, 20, 50):
            action = menu.addAction(str(size))
            if size == self._rows_per_page:
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda checked, s=size: self._set_rows_per_page(s)
                )

        menu.exec_(self._rows_btn.mapToGlobal(self._rows_btn.rect().bottomLeft()))

    def _set_rows_per_page(self, size):
        self._rows_per_page = size
        self._rows_btn.setText(str(size))
        self._current_page = 1
        self._load_packages()

    # -- Cell click / context menu -----------------------------------------

    def _on_cell_clicked(self, row, col):
        if col != 5:
            return
        if row >= len(self._packages):
            return
        pkg = self._packages[row]
        self._show_actions_menu(row, col, pkg)

    def _show_actions_menu(self, row, col, pkg):
        item = self.table.item(row, col)
        if not item:
            return

        rect = self.table.visualItemRect(item)
        position = QPoint(rect.right() - 10, rect.bottom())

        pkg_id = str(pkg.get("id") or pkg.get("packageId") or "")
        status = pkg.get("status", 0)
        if isinstance(status, str) and status.isdigit():
            status = int(status)

        menu = QMenu(self)
        menu.setLayoutDirection(get_layout_direction())
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 10px 16px;
                border-radius: 4px;
                color: #212B36;
                font-size: 10.5pt;
            }
            QMenu::item:selected {
                background-color: #F0F7FF;
            }
        """)

        # View
        view_action = QAction(tr("action.view"), self)
        view_action.triggered.connect(lambda: self._on_view_package(pkg_id))
        menu.addAction(view_action)

        # Cancel (only if not already cancelled/completed)
        if status not in (9, 12):
            cancel_action = QAction(tr("action.cancel"), self)
            cancel_action.triggered.connect(lambda: self._cancel_package(pkg_id))
            menu.addAction(cancel_action)

        # Quarantine (only if not completed/cancelled/quarantined)
        if status not in (5, 9, 12):
            quarantine_action = QAction(tr("action.quarantine"), self)
            quarantine_action.triggered.connect(lambda: self._quarantine_package(pkg_id))
            menu.addAction(quarantine_action)

        # Reset commit (admin only, only for stuck committing status=8)
        if self._user_role == "admin" and status == 8:
            reset_action = QAction(tr("page.import_packages.reset_commit"), self)
            reset_action.triggered.connect(lambda: self._reset_commit(pkg_id))
            menu.addAction(reset_action)

        menu.exec_(self.table.viewport().mapToGlobal(position))

    def _on_view_package(self, pkg_id):
        self._spinner.show_loading()
        self.view_package.emit(pkg_id)

    def _on_upload_clicked(self):
        self._spinner.show_loading()
        self.open_wizard.emit()

    # -- Package actions ---------------------------------------------------

    def _cancel_package(self, package_id):
        self._spinner.show_loading(tr("page.import_packages.cancelling"))
        try:
            result = self.import_controller.cancel_package(package_id)
            if result.success:
                ErrorHandler.show_success(self, result.message_ar or tr("page.import_packages.package_cancelled"))
                self._load_packages()
            else:
                ErrorHandler.show_error(self, result.message_ar or tr("page.import_packages.cancel_failed"))
        except Exception as e:
            ErrorHandler.show_error(self, tr("page.import_packages.cancel_failed_detail", error=str(e)))
        finally:
            self._spinner.hide_loading()

    def _quarantine_package(self, package_id):
        self._spinner.show_loading(tr("page.import_packages.quarantining"))
        try:
            result = self.import_controller.quarantine_package(package_id)
            if result.success:
                ErrorHandler.show_success(self, result.message_ar or tr("page.import_packages.package_quarantined"))
                self._load_packages()
            else:
                ErrorHandler.show_error(self, result.message_ar or tr("page.import_packages.quarantine_failed"))
        except Exception as e:
            ErrorHandler.show_error(self, tr("page.import_packages.quarantine_failed_detail", error=str(e)))
        finally:
            self._spinner.hide_loading()

    def _reset_commit(self, package_id):
        self._spinner.show_loading()
        try:
            result = self.import_controller.reset_commit(package_id)
            if result.success:
                ErrorHandler.show_success(self, result.message_ar or tr("page.import_packages.reset_done"))
                self._load_packages()
            else:
                ErrorHandler.show_error(self, result.message_ar or tr("page.import_packages.reset_failed"))
        except Exception as e:
            ErrorHandler.show_error(self, tr("page.import_packages.reset_failed_detail", error=str(e)))
        finally:
            self._spinner.hide_loading()

    # -- Public API --------------------------------------------------------

    def refresh(self, data=None):
        self._current_page = 1
        self._spinner.hide_loading()
        self._load_packages()

    def configure_for_role(self, role):
        self._user_role = role
        can_upload = role in {"admin", "data_manager"}
        self._upload_btn.setVisible(can_upload)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.import_packages.title"))
        self._stat_total.set_label(tr("page.import_packages.stat_total"))
        self._upload_btn.setText(tr("page.import_packages.process_new"))

        # Status combo first item
        self._status_combo.setItemText(0, tr("page.import_packages.all_statuses"))

        # Table headers
        labels = self._header_labels()
        for i, text in enumerate(labels):
            item = self.table.horizontalHeaderItem(i)
            if item:
                item.setText(text)

        self._rows_label.setText(tr("page.import_packages.rows_per_page"))

        # Empty state
        self._empty_state.set_title(tr("page.import_packages.no_packages"))
        self._empty_state.set_subtitle(tr("page.import_packages.no_packages_hint"))

        if self._packages:
            self._populate_table(self._packages, self._total_count)
