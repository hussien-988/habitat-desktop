# -*- coding: utf-8 -*-
"""Modern unified table component inspired by Linear/Notion/Figma."""

from typing import List, Dict, Any, Optional, Callable

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QHeaderView, QTableWidget, QTableWidgetItem,
    QSizePolicy, QAbstractItemView, QGraphicsOpacityEffect,
    QStyledItemDelegate, QStyle
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve,
    QSize, QRect
)
from PyQt5.QtGui import QColor, QPainter, QFont, QIcon, QCursor

from ui.design_system import (
    ModernTableDimensions as MTD, Colors, BorderRadius,
    Typography, Spacing, AnimationTimings, SkeletonColors, ScreenScale
)
from ui.font_utils import create_font, FontManager
from services.translation_manager import get_layout_direction, tr


class _StatusBadge(QLabel):
    """Rounded status badge with colored background."""

    _STATUS_COLORS = {
        "success": (Colors.SUCCESS, "#F0FDF4"),
        "error": (Colors.ERROR, "#FEF2F2"),
        "warning": (Colors.WARNING, "#FFFBEB"),
        "info": (Colors.INFO, "#EFF6FF"),
        "draft": (Colors.BADGE_DRAFT, "#FFF8E1"),
        "finalized": (Colors.BADGE_FINALIZED, "#E8F5E9"),
        "pending": (Colors.BADGE_PENDING, "#E3F2FD"),
        "rejected": (Colors.BADGE_REJECTED, "#FFEBEE"),
        "default": (Colors.TEXT_SECONDARY, Colors.BACKGROUND),
    }

    def __init__(self, text: str, status: str = "default", parent=None):
        super().__init__(text, parent)
        fg, bg = self._STATUS_COLORS.get(status, self._STATUS_COLORS["default"])
        self.setAlignment(Qt.AlignCenter)
        self.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        self.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border-radius: {MTD.STATUS_BADGE_RADIUS}px;
            padding: {MTD.STATUS_BADGE_PADDING_V}px {MTD.STATUS_BADGE_PADDING_H}px;
        """)
        self.setFixedHeight(ScreenScale.h(24))


class _ActionBar(QWidget):
    """Row action icons container, visible on hover."""

    def __init__(self, actions: list, row_data: dict, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        for icon_text, tooltip, callback in actions:
            btn = QPushButton(icon_text)
            btn.setToolTip(tooltip)
            btn.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {Colors.TEXT_SECONDARY};
                    border: none;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background: rgba(56, 144, 223, 0.1);
                    color: {Colors.PRIMARY_BLUE};
                }}
            """)
            btn.clicked.connect(lambda checked, cb=callback, rd=row_data: cb(rd))
            layout.addWidget(btn)


class _RowDelegate(QStyledItemDelegate):
    """Custom delegate for hover accent bar on rows."""

    def __init__(self, table, parent=None):
        super().__init__(parent)
        self._table = table
        self._hover_row = -1

    def set_hover_row(self, row):
        self._hover_row = row

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        if index.row() == self._hover_row and index.column() == 0:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(Colors.PRIMARY_BLUE))
            painter.setPen(Qt.NoPen)
            is_rtl = get_layout_direction() == Qt.RightToLeft
            if is_rtl:
                x = option.rect.right() - MTD.ROW_HOVER_ACCENT_WIDTH
            else:
                x = option.rect.left()
            painter.drawRect(
                x, option.rect.top() + 4,
                MTD.ROW_HOVER_ACCENT_WIDTH,
                option.rect.height() - 8
            )
            painter.restore()


class ModernTable(QFrame):
    """Premium table widget with built-in pagination, sorting, skeleton, and empty state."""

    row_clicked = pyqtSignal(int, dict)
    row_double_clicked = pyqtSignal(int, dict)
    page_changed = pyqtSignal(int)
    sort_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("modern_table")
        self._columns = []
        self._data = []
        self._actions = []
        self._page = 1
        self._page_size = 10
        self._total_count = 0
        self._sort_col = ""
        self._sort_dir = "asc"
        self._hover_row = -1
        self._skeleton = None
        self._empty_widget = None

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            QFrame#modern_table {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {MTD.BORDER_RADIUS}px;
            }}
        """)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._table = QTableWidget()
        self._table.setObjectName("modern_table_inner")
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setMouseTracking(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setSectionsClickable(True)
        self._table.horizontalHeader().sectionClicked.connect(self._on_header_click)
        self._table.cellClicked.connect(self._on_cell_click)
        self._table.cellDoubleClicked.connect(self._on_cell_double_click)
        self._table.cellEntered.connect(self._on_cell_hover)

        self._delegate = _RowDelegate(self._table, self._table)
        self._table.setItemDelegate(self._delegate)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                border: none;
                outline: none;
            }}
            QTableWidget::item {{
                padding: {MTD.CELL_PADDING_V}px {MTD.CELL_PADDING_H}px;
                border: none;
                border-bottom: 1px solid {MTD.ROW_BORDER};
                color: {Colors.TEXT_PRIMARY};
            }}
            QTableWidget::item:hover {{
                background-color: {MTD.ROW_HOVER_BG};
            }}
            QTableWidget::item:selected {{
                background-color: {MTD.ROW_SELECTED_BG};
                color: {Colors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: transparent;
                color: {MTD.HEADER_TEXT_COLOR};
                font-size: {MTD.HEADER_FONT_SIZE}px;
                font-weight: {MTD.HEADER_FONT_WEIGHT};
                text-transform: uppercase;
                padding: {MTD.CELL_PADDING_V}px {MTD.CELL_PADDING_H}px;
                border: none;
                border-bottom: 1px solid {MTD.ROW_BORDER};
            }}
            QHeaderView::section:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)

        self._main_layout.addWidget(self._table, 1)

        self._footer = QFrame()
        self._footer.setFixedHeight(MTD.PAGINATION_HEIGHT)
        self._footer.setStyleSheet("background: transparent; border: none;")
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(MTD.CELL_PADDING_H, 0,
                                         MTD.CELL_PADDING_H, 0)

        self._count_lbl = QLabel()
        self._count_lbl.setFont(
            create_font(size=11, weight=FontManager.WEIGHT_REGULAR)
        )
        self._count_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        footer_layout.addWidget(self._count_lbl)

        footer_layout.addStretch()

        self._pagination = QHBoxLayout()
        self._pagination.setSpacing(4)
        footer_layout.addLayout(self._pagination)

        self._main_layout.addWidget(self._footer)

        from ui.components.skeleton_loader import TableSkeleton
        self._skeleton_widget = TableSkeleton(columns=4, rows=5, parent=self)
        self._skeleton_widget.hide()
        self._main_layout.addWidget(self._skeleton_widget)

        self._empty_frame = QFrame()
        self._empty_frame.hide()
        empty_layout = QVBoxLayout(self._empty_frame)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(Spacing.SM)
        self._empty_icon = QLabel()
        self._empty_icon.setAlignment(Qt.AlignCenter)
        self._empty_icon.setFont(create_font(size=32))
        self._empty_icon.setStyleSheet(f"color: {Colors.TEXT_DISABLED};")
        empty_layout.addWidget(self._empty_icon)
        self._empty_text = QLabel()
        self._empty_text.setAlignment(Qt.AlignCenter)
        self._empty_text.setFont(
            create_font(size=FontManager.SIZE_BODY,
                        weight=FontManager.WEIGHT_MEDIUM)
        )
        self._empty_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        empty_layout.addWidget(self._empty_text)
        self._main_layout.addWidget(self._empty_frame)

    def set_columns(self, columns: list):
        self._columns = columns
        has_actions = bool(self._actions)
        total = len(columns) + (1 if has_actions else 0)

        self._table.setColumnCount(total)
        headers = [col.get("label", "") for col in columns]
        if has_actions:
            headers.append("")
        self._table.setHorizontalHeaderLabels(headers)

        header = self._table.horizontalHeader()
        for i, col in enumerate(columns):
            mode = col.get("resize", "stretch")
            if mode == "fixed":
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, col.get("width", 100))
            elif mode == "contents":
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.Stretch)

        if has_actions:
            header.setSectionResizeMode(total - 1, QHeaderView.Fixed)
            self._table.setColumnWidth(total - 1, 80)

    def set_actions(self, actions: list):
        self._actions = actions

    def set_data(self, data: list, total_count: int = None):
        self._data = data
        if total_count is not None:
            self._total_count = total_count
        else:
            self._total_count = len(data)

        self._skeleton_widget.stop()
        self._skeleton_widget.hide()

        if not data:
            self._table.hide()
            self._footer.hide()
            self._empty_frame.show()
            return

        self._empty_frame.hide()
        self._table.show()
        self._footer.show()
        self._populate_rows(data)
        self._update_footer()

    def _populate_rows(self, data: list):
        self._table.setRowCount(len(data))

        for row_idx, row_data in enumerate(data):
            self._table.setRowHeight(row_idx, MTD.ROW_HEIGHT)

            for col_idx, col_def in enumerate(self._columns):
                key = col_def.get("key", "")
                cell_type = col_def.get("type", "text")
                value = row_data.get(key, "")

                if cell_type == "status":
                    status_map = col_def.get("status_map", {})
                    status_key = status_map.get(str(value), "default")
                    display = col_def.get("display_map", {}).get(str(value), str(value))
                    badge = _StatusBadge(display, status_key)
                    self._table.setCellWidget(row_idx, col_idx, badge)
                elif cell_type == "id":
                    item = QTableWidgetItem(str(value))
                    item.setFont(create_font(
                        size=11, weight=FontManager.WEIGHT_MEDIUM,
                        families=["Roboto Mono"]
                    ))
                    item.setForeground(QColor(Colors.PRIMARY_BLUE))
                    self._table.setItem(row_idx, col_idx, item)
                else:
                    item = QTableWidgetItem(str(value))
                    item.setFont(create_font(
                        size=FontManager.SIZE_BODY,
                        weight=FontManager.WEIGHT_REGULAR
                    ))
                    self._table.setItem(row_idx, col_idx, item)

            if self._actions:
                action_bar = _ActionBar(self._actions, row_data)
                action_bar.setVisible(False)
                self._table.setCellWidget(
                    row_idx, len(self._columns), action_bar
                )

    def _update_footer(self):
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        start = (self._page - 1) * self._page_size + 1
        end = min(self._page * self._page_size, self._total_count)

        self._count_lbl.setText(f"{start}-{end} / {self._total_count}")

        while self._pagination.count():
            item = self._pagination.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if total_pages <= 1:
            return

        for p in range(1, total_pages + 1):
            if total_pages > 7:
                if p > 3 and p < total_pages - 2 and abs(p - self._page) > 1:
                    if p == 4 or p == total_pages - 3:
                        dots = QLabel("...")
                        dots.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
                        self._pagination.addWidget(dots)
                    continue

            btn = QPushButton(str(p))
            btn.setFixedSize(MTD.PAGE_BUTTON_SIZE, MTD.PAGE_BUTTON_SIZE)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))

            if p == self._page:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Colors.PRIMARY_BLUE};
                        color: white;
                        border: none;
                        border-radius: {MTD.PAGE_BUTTON_RADIUS}px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {Colors.TEXT_SECONDARY};
                        border: none;
                        border-radius: {MTD.PAGE_BUTTON_RADIUS}px;
                    }}
                    QPushButton:hover {{
                        background-color: {Colors.BACKGROUND};
                        color: {Colors.TEXT_PRIMARY};
                    }}
                """)
            btn.clicked.connect(lambda checked, pg=p: self._go_to_page(pg))
            self._pagination.addWidget(btn)

    def _go_to_page(self, page: int):
        self._page = page
        self._update_footer()
        self.page_changed.emit(page)

    def set_page(self, page: int):
        self._page = page

    def set_page_size(self, size: int):
        self._page_size = size

    def set_empty_state(self, text: str, icon: str = ""):
        self._empty_text.setText(text)
        self._empty_icon.setText(icon)

    def show_loading(self, message: str = ""):
        self._table.hide()
        self._footer.hide()
        self._empty_frame.hide()
        if message and hasattr(self._skeleton_widget, '_build'):
            pass
        self._skeleton_widget.show()
        self._skeleton_widget.start()

    def _on_header_click(self, col_idx):
        if col_idx >= len(self._columns):
            return
        col = self._columns[col_idx]
        key = col.get("key", "")
        sortable = col.get("sortable", True)
        if not sortable:
            return

        if self._sort_col == key:
            self._sort_dir = "desc" if self._sort_dir == "asc" else "asc"
        else:
            self._sort_col = key
            self._sort_dir = "asc"

        arrow = " \u25B2" if self._sort_dir == "asc" else " \u25BC"
        headers = []
        for i, c in enumerate(self._columns):
            label = c.get("label", "")
            if c.get("key") == key:
                label += arrow
            headers.append(label)
        if self._actions:
            headers.append("")
        self._table.setHorizontalHeaderLabels(headers)

        self.sort_changed.emit(key, self._sort_dir)

    def _on_cell_click(self, row, col):
        if row < len(self._data):
            self.row_clicked.emit(row, self._data[row])

    def _on_cell_double_click(self, row, col):
        if row < len(self._data):
            self.row_double_clicked.emit(row, self._data[row])

    def _on_cell_hover(self, row, col):
        if row == self._hover_row:
            return

        if self._actions:
            action_col = len(self._columns)
            if 0 <= self._hover_row < self._table.rowCount():
                old_widget = self._table.cellWidget(self._hover_row, action_col)
                if old_widget:
                    old_widget.setVisible(False)

            self._hover_row = row
            new_widget = self._table.cellWidget(row, action_col)
            if new_widget:
                new_widget.setVisible(True)
        else:
            self._hover_row = row

        self._delegate.set_hover_row(row)
        self._table.viewport().update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._actions and 0 <= self._hover_row < self._table.rowCount():
            action_col = len(self._columns)
            widget = self._table.cellWidget(self._hover_row, action_col)
            if widget:
                widget.setVisible(False)
        self._hover_row = -1
        self._delegate.set_hover_row(-1)
        self._table.viewport().update()

    def get_selected_row(self) -> Optional[dict]:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            idx = rows[0].row()
            if idx < len(self._data):
                return self._data[idx]
        return None

    def clear(self):
        self._data = []
        self._table.setRowCount(0)
        self._total_count = 0
        self._page = 1
