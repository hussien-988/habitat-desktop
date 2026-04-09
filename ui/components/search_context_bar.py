# -*- coding: utf-8 -*-
"""
SearchContextBar — Reusable search mode context widget for DarkHeaderZone.
Manages tabs visibility and provides search result count display.
"""

from typing import List, Dict, Optional

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor

from ui.design_system import ScreenScale
from ui.font_utils import create_font
from ui.components.icon import Icon
from services.translation_manager import tr


class SearchContextBar(QWidget):
    """Search context bar for DarkHeaderZone.

    Displays a back button and search result count when search mode is active.
    Internally manages tab visibility during search mode.
    """

    back_clicked = pyqtSignal()

    def __init__(self, tabs: List[QWidget] = None, parent=None):
        """
        Initialize SearchContextBar.

        Args:
            tabs: List of tab widgets to manage visibility for
            parent: Parent widget
        """
        super().__init__(parent)
        self._tabs = tabs or []
        self._tab_visibility: Dict[QWidget, bool] = {}
        self._clear_action = None

        self._build_ui()

    def _build_ui(self):
        """Build the UI layout."""
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Back button
        self._back_btn = QPushButton(tr("common.back"))
        back_icon = Icon.load_qicon("arrow-right", 14)
        if back_icon:
            self._back_btn.setIcon(back_icon)
        self._back_btn.setFixedHeight(ScreenScale.h(28))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                color: white;
                font-size: 12px;
                padding: 0 10px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.2); }
        """)
        self._back_btn.clicked.connect(self.back_clicked.emit)

        # Count label
        self._count_label = QLabel(tr("search.results"))
        self._count_label.setStyleSheet(
            "color: rgba(200, 220, 255, 200); font-size: 13px; background: transparent;"
        )

        layout.addWidget(self._back_btn)
        layout.addWidget(self._count_label)
        layout.addStretch()

    def attach_clear_action(self, search_field: QLineEdit):
        """Attach X button (clear action) to a search field.

        Args:
            search_field: QLineEdit to attach the action to
        """
        clear_icon = Icon.load_qicon("x-close", 12)
        if clear_icon:
            self._clear_action = search_field.addAction(
                clear_icon,
                QLineEdit.TrailingPosition
            )
            if self._clear_action:
                self._clear_action.setVisible(False)
                self._clear_action.triggered.connect(self.back_clicked.emit)

    def enter_search_mode(self):
        """Enter search mode: hide tabs, show this widget, show X button."""
        # Save current visibility state of all tabs
        self._tab_visibility.clear()
        for tab in self._tabs:
            self._tab_visibility[tab] = tab.isVisible()

        # Hide all tabs
        for tab in self._tabs:
            tab.hide()

        # Show this widget and X button
        self.show()
        if self._clear_action:
            self._clear_action.setVisible(True)

    def exit_search_mode(self):
        """Exit search mode: restore tabs, hide this widget, hide X button."""
        # Restore tab visibility from saved state
        for tab in self._tabs:
            if tab in self._tab_visibility:
                tab.setVisible(self._tab_visibility[tab])

        # Hide this widget and X button
        self.hide()
        if self._clear_action:
            self._clear_action.setVisible(False)

    def update_count(self, term: str, count: int):
        """Update the result count display.

        Args:
            term: Search term (e.g., "SRV-001")
            count: Number of results
        """
        plural = "نتيجة" if count == 1 else "نتائج"
        self._count_label.setText(f'"{term}" — {count} {plural}')

    def update_language(self):
        """Update all text when language changes."""
        self._back_btn.setText(tr("common.back"))
        if not self._count_label.text():
            self._count_label.setText(tr("search.results"))
