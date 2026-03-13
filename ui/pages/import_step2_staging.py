# -*- coding: utf-8 -*-
"""
Import Wizard - Step 2: Staging Results and Validation Report
UC-003: Import Pipeline

Displays the validation report after staging a package.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Validation issue type configuration
_ISSUE_TYPE_CONFIG = {
    'error': {
        'label': 'خطأ',
        'color': '#EF4444',
        'bg': '#FEF2F2',
    },
    'warning': {
        'label': 'تحذير',
        'color': '#F59E0B',
        'bg': '#FFFBEB',
    },
    'info': {
        'label': 'معلومة',
        'color': '#3B82F6',
        'bg': '#EFF6FF',
    },
}


class ImportStep2Staging(QWidget):
    """Step 2: Staging results and validation report."""

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._report_data = None
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Validation report card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(16)

        # Title
        title = QLabel("تقرير التحقق")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Summary stats row
        self._stats_layout = QHBoxLayout()
        self._stats_layout.setSpacing(24)

        self._total_label = self._create_stat_widget("إجمالي السجلات", "0")
        self._errors_label = self._create_stat_widget("أخطاء", "0", "#EF4444")
        self._warnings_label = self._create_stat_widget("تحذيرات", "0", "#F59E0B")

        self._stats_layout.addStretch()
        card_layout.addLayout(self._stats_layout)

        # Issues list (scrollable)
        self._issues_scroll = QScrollArea()
        self._issues_scroll.setWidgetResizable(True)
        self._issues_scroll.setFrameShape(QFrame.NoFrame)
        self._issues_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._issues_scroll.setMaximumHeight(420)

        self._issues_container = QWidget()
        self._issues_container.setStyleSheet("background: transparent;")
        self._issues_layout = QVBoxLayout(self._issues_container)
        self._issues_layout.setContentsMargins(0, 0, 0, 0)
        self._issues_layout.setSpacing(8)

        # Initial empty state
        empty_label = QLabel("لا توجد بيانات بعد")
        empty_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        empty_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        empty_label.setAlignment(Qt.AlignCenter)
        self._issues_layout.addWidget(empty_label)
        self._issues_layout.addStretch()

        self._issues_scroll.setWidget(self._issues_container)
        card_layout.addWidget(self._issues_scroll)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def _create_stat_widget(self, label_text: str, value_text: str,
                            value_color: str = "#212B36") -> QLabel:
        """Create a stat display with label and value."""
        container = QVBoxLayout()
        container.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet("color: #637381; background: transparent;")
        container.addWidget(label)

        value = QLabel(value_text)
        value.setFont(create_font(size=16, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {value_color}; background: transparent;")
        container.addWidget(value)

        self._stats_layout.addLayout(container)
        return value

    def load_report(self, package_id: str):
        """Load validation report from the controller."""
        logger.info(f"Loading validation report for package {package_id}")

        result = self.import_controller.get_validation_report(package_id)

        if not result.success:
            self._show_error(result.message_ar or "فشل تحميل تقرير التحقق")
            return

        self._report_data = result.data or {}
        self._update_ui()

    def _update_ui(self):
        """Update UI with report data."""
        if not self._report_data:
            return

        total = self._report_data.get("totalRecords", 0)
        errors = self._report_data.get("errorCount", 0)
        warnings = self._report_data.get("warningCount", 0)

        self._total_label.setText(str(total))
        self._errors_label.setText(str(errors))
        self._warnings_label.setText(str(warnings))

        # Clear existing issues
        self._clear_issues()

        issues = self._report_data.get("issues", [])
        if not issues:
            empty_label = QLabel("لا توجد مشكلات في البيانات")
            empty_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
            empty_label.setStyleSheet("color: #10B981; background: transparent;")
            empty_label.setAlignment(Qt.AlignCenter)
            self._issues_layout.addWidget(empty_label)
        else:
            for issue in issues:
                row = self._create_issue_row(issue)
                self._issues_layout.addWidget(row)

        self._issues_layout.addStretch()

    def _create_issue_row(self, issue: dict) -> QFrame:
        """Create a row for a single validation issue."""
        row = QFrame()
        row.setFixedHeight(48)
        row.setStyleSheet("""
            QFrame {
                background-color: #FAFBFC;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(12)

        # Issue type badge
        issue_type = issue.get("type", "info").lower()
        config = _ISSUE_TYPE_CONFIG.get(issue_type, _ISSUE_TYPE_CONFIG['info'])

        badge = QLabel(config['label'])
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(26)
        badge.setFixedWidth(70)
        badge.setStyleSheet(f"""
            padding: 2px 12px;
            border-radius: 13px;
            color: {config['color']};
            background-color: {config['bg']};
        """)
        row_layout.addWidget(badge)

        # Issue message
        message = issue.get("message", "")
        msg_label = QLabel(message)
        msg_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        msg_label.setStyleSheet("color: #212B36;")
        msg_label.setWordWrap(True)
        row_layout.addWidget(msg_label, 1)

        # Entity reference (if present)
        entity_ref = issue.get("entityRef", "") or issue.get("sourceId", "")
        if entity_ref:
            ref_label = QLabel(entity_ref)
            ref_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            ref_label.setStyleSheet("color: #9CA3AF;")
            row_layout.addWidget(ref_label)

        return row

    def _clear_issues(self):
        """Remove all issue widgets from the layout."""
        while self._issues_layout.count():
            item = self._issues_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_error(self, message: str):
        """Display an error message in the issues area."""
        self._clear_issues()
        error_label = QLabel(message)
        error_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        error_label.setStyleSheet("color: #EF4444; background: transparent;")
        error_label.setAlignment(Qt.AlignCenter)
        self._issues_layout.addWidget(error_label)
        self._issues_layout.addStretch()

    def get_report_data(self) -> dict:
        """Return the loaded report data."""
        return self._report_data or {}
