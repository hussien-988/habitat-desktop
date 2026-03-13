# -*- coding: utf-8 -*-
"""
Import Wizard - Step 6: Final Commit Report
UC-003: Import Pipeline

Displays the final commit report with success/error summary.
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


class ImportStep6Report(QWidget):
    """Step 6: Final commit report."""

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._report_data = None
        self._is_success = True
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Result header card (success or error)
        self._result_card = QFrame()
        self._result_card_layout = QVBoxLayout(self._result_card)
        self._result_card_layout.setContentsMargins(32, 24, 32, 24)
        self._result_card_layout.setSpacing(8)

        self._result_title = QLabel("تم الإدخال بنجاح")
        self._result_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        self._result_card_layout.addWidget(self._result_title)

        self._result_subtitle = QLabel("")
        self._result_subtitle.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._result_card_layout.addWidget(self._result_subtitle)

        # Set default success style
        self._set_result_style(True)

        main_layout.addWidget(self._result_card)

        # Stats card
        stats_card = QFrame()
        stats_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        stats_card_layout = QVBoxLayout(stats_card)
        stats_card_layout.setContentsMargins(32, 24, 32, 24)
        stats_card_layout.setSpacing(16)

        stats_title = QLabel("ملخص النتائج")
        stats_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        stats_title.setStyleSheet("color: #212B36; background: transparent;")
        stats_card_layout.addWidget(stats_title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        stats_card_layout.addWidget(sep)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)

        # Imported count
        self._imported_count = self._create_stat_box(
            "تم الإدخال", "0", "#10B981", "#ECFDF5"
        )
        stats_row.addWidget(self._imported_count)

        # Failed count
        self._failed_count = self._create_stat_box(
            "فشل الإدخال", "0", "#EF4444", "#FEF2F2"
        )
        stats_row.addWidget(self._failed_count)

        # Skipped count
        self._skipped_count = self._create_stat_box(
            "تم التخطي", "0", "#F59E0B", "#FFFBEB"
        )
        stats_row.addWidget(self._skipped_count)

        stats_row.addStretch()
        stats_card_layout.addLayout(stats_row)

        main_layout.addWidget(stats_card)

        # Details card (scrollable)
        details_card = QFrame()
        details_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        details_card_layout = QVBoxLayout(details_card)
        details_card_layout.setContentsMargins(32, 24, 32, 24)
        details_card_layout.setSpacing(12)

        details_title = QLabel("التفاصيل")
        details_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        details_title.setStyleSheet("color: #212B36; background: transparent;")
        details_card_layout.addWidget(details_title)

        self._details_scroll = QScrollArea()
        self._details_scroll.setWidgetResizable(True)
        self._details_scroll.setFrameShape(QFrame.NoFrame)
        self._details_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._details_scroll.setMaximumHeight(300)

        self._details_container = QWidget()
        self._details_container.setStyleSheet("background: transparent;")
        self._details_layout = QVBoxLayout(self._details_container)
        self._details_layout.setContentsMargins(0, 0, 0, 0)
        self._details_layout.setSpacing(6)

        empty_label = QLabel("لا توجد تفاصيل بعد")
        empty_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        empty_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        empty_label.setAlignment(Qt.AlignCenter)
        self._details_layout.addWidget(empty_label)
        self._details_layout.addStretch()

        self._details_scroll.setWidget(self._details_container)
        details_card_layout.addWidget(self._details_scroll)

        main_layout.addWidget(details_card)
        main_layout.addStretch()

    def _create_stat_box(self, label_text: str, value_text: str,
                         color: str, bg: str) -> QFrame:
        """Create a stat box with value and label."""
        box = QFrame()
        box.setFixedHeight(70)
        box.setMinimumWidth(150)
        box.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border-radius: 12px;
                border: none;
            }}
            QFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(16, 8, 16, 8)
        box_layout.setSpacing(4)
        box_layout.setAlignment(Qt.AlignCenter)

        value = QLabel(value_text)
        value.setObjectName("stat_value")
        value.setFont(create_font(size=18, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {color};")
        value.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(value)

        label = QLabel(label_text)
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet("color: #637381;")
        label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(label)

        return box

    def _set_result_style(self, success: bool):
        """Apply success or error styling to the result card."""
        self._is_success = success

        if success:
            self._result_card.setStyleSheet("""
                QFrame {
                    background-color: #ECFDF5;
                    border-radius: 16px;
                    border: 1px solid #A7F3D0;
                }
            """)
            self._result_title.setStyleSheet("color: #065F46; background: transparent;")
            self._result_subtitle.setStyleSheet("color: #047857; background: transparent;")
        else:
            self._result_card.setStyleSheet("""
                QFrame {
                    background-color: #FEF2F2;
                    border-radius: 16px;
                    border: 1px solid #FECACA;
                }
            """)
            self._result_title.setStyleSheet("color: #991B1B; background: transparent;")
            self._result_subtitle.setStyleSheet("color: #B91C1C; background: transparent;")

    def load_report(self, package_id: str):
        """Load the commit report from the controller."""
        logger.info(f"Loading commit report for package {package_id}")

        result = self.import_controller.get_commit_report(package_id)

        if not result.success:
            self._set_result_style(False)
            self._result_title.setText("فشل تحميل التقرير")
            self._result_subtitle.setText(result.message_ar or result.message)
            return

        self._report_data = result.data or {}
        self._update_ui()

    def _update_ui(self):
        """Update UI with report data."""
        if not self._report_data:
            return

        imported = self._report_data.get("importedCount", 0)
        failed = self._report_data.get("failedCount", 0)
        skipped = self._report_data.get("skippedCount", 0)

        # Determine success state
        has_failures = failed > 0
        if imported == 0 and failed > 0:
            self._set_result_style(False)
            self._result_title.setText("فشل الإدخال")
            self._result_subtitle.setText(f"فشل إدخال {failed} سجل")
        elif has_failures:
            self._set_result_style(True)
            self._result_title.setText("تم الإدخال مع بعض الأخطاء")
            self._result_subtitle.setText(
                f"تم إدخال {imported} سجل بنجاح، فشل {failed} سجل"
            )
        else:
            self._set_result_style(True)
            self._result_title.setText("تم الإدخال بنجاح")
            self._result_subtitle.setText(f"تم إدخال {imported} سجل بنجاح")

        # Update stat boxes
        self._update_stat_value(self._imported_count, str(imported))
        self._update_stat_value(self._failed_count, str(failed))
        self._update_stat_value(self._skipped_count, str(skipped))

        # Update details
        self._clear_details()
        details = self._report_data.get("details", [])
        if details:
            for detail in details:
                row = self._create_detail_row(detail)
                self._details_layout.addWidget(row)
        else:
            empty = QLabel("لا توجد تفاصيل إضافية")
            empty.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            empty.setStyleSheet("color: #9CA3AF; background: transparent;")
            empty.setAlignment(Qt.AlignCenter)
            self._details_layout.addWidget(empty)

        self._details_layout.addStretch()

    def _update_stat_value(self, stat_box: QFrame, value: str):
        """Update the value label inside a stat box."""
        value_label = stat_box.findChild(QLabel, "stat_value")
        if value_label:
            value_label.setText(value)

    def _create_detail_row(self, detail: dict) -> QFrame:
        """Create a row for a detail entry."""
        row = QFrame()
        row.setFixedHeight(40)
        row.setStyleSheet("""
            QFrame {
                background-color: #FAFBFC;
                border: 1px solid #F4F6F8;
                border-radius: 6px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(12)

        # Detail message
        message = detail.get("message", "") or str(detail)
        msg_label = QLabel(message)
        msg_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        msg_label.setStyleSheet("color: #212B36;")
        msg_label.setWordWrap(True)
        row_layout.addWidget(msg_label, 1)

        # Status indicator
        status = detail.get("status", "")
        if status:
            is_ok = status.lower() in ("success", "ok", "imported")
            color = "#10B981" if is_ok else "#EF4444"
            status_label = QLabel(status)
            status_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            status_label.setStyleSheet(f"color: {color};")
            row_layout.addWidget(status_label)

        return row

    def _clear_details(self):
        """Remove all detail widgets from the layout."""
        while self._details_layout.count():
            item = self._details_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_error(self, error_message: str):
        """Set the report to error state with a message."""
        self._set_result_style(False)
        self._result_title.setText("فشل الإدخال")
        self._result_subtitle.setText(error_message)

    def get_report_data(self) -> dict:
        """Return the loaded report data."""
        return self._report_data or {}
