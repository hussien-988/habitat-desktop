# -*- coding: utf-8 -*-
"""Import wizard final commit report step."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction, get_text_alignment
from utils.logger import get_logger
from ui.design_system import Colors, ScreenScale

logger = get_logger(__name__)

# Entity sections in commit-report (9 types)
_ENTITY_SECTION_KEYS = [
    ('surveys', 'wizard.import.entity.surveys'),
    ('buildings', 'wizard.import.entity.buildings'),
    ('buildingDocuments', 'wizard.import.entity.building_documents'),
    ('propertyUnits', 'wizard.import.entity.property_units'),
    ('persons', 'wizard.import.entity.persons'),
    ('households', 'wizard.import.entity.households'),
    ('personPropertyRelations', 'wizard.import.entity.person_property_relations'),
    ('identificationDocuments', 'wizard.import.entity.identification_documents'),
    ('evidences', 'wizard.import.entity.evidences'),
    ('claims', 'wizard.import.entity.claims'),
]


def _get_entity_sections():
    return [(k, tr(tr_key)) for k, tr_key in _ENTITY_SECTION_KEYS]


class ImportStep6Report(QWidget):
    """Step 5 (Report): Final commit report."""

    def __init__(self, import_controller, package_id, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id
        self._report_data = None
        self._dots_count = 0
        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()
        self.load_report(package_id)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        # No outer scroll — the report fits within the available height by
        # using a 2-card horizontal layout (stats + breakdown) instead of
        # stacking. The errors card has its own internal scroll for long
        # error lists, but the page itself never scrolls.
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 16, 0, 16)
        main_layout.setSpacing(16)

        # --- Card 1: Result header (success/partial/fail) ---
        self._result_card = QFrame()
        self._result_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._result_card_layout = QVBoxLayout(self._result_card)
        self._result_card_layout.setContentsMargins(28, 16, 28, 16)
        self._result_card_layout.setSpacing(6)

        self._result_title = QLabel(tr("wizard.import.step6.commit_success"))
        self._result_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        self._result_card_layout.addWidget(self._result_title)

        self._result_subtitle = QLabel("")
        self._result_subtitle.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._result_card_layout.addWidget(self._result_subtitle)

        # Meta info row (duration, date, package number)
        self._meta_layout = QHBoxLayout()
        self._meta_layout.setSpacing(24)

        self._duration_label = QLabel("")
        self._duration_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._meta_layout.addWidget(self._duration_label)

        self._date_label = QLabel("")
        self._date_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._meta_layout.addWidget(self._date_label)

        self._pkg_number_label = QLabel("")
        self._pkg_number_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._meta_layout.addWidget(self._pkg_number_label)

        self._meta_layout.addStretch()
        self._result_card_layout.addLayout(self._meta_layout)

        result_shadow = QGraphicsDropShadowEffect()
        result_shadow.setBlurRadius(20)
        result_shadow.setXOffset(0)
        result_shadow.setYOffset(4)
        result_shadow.setColor(QColor(0, 0, 0, 22))
        self._result_card.setGraphicsEffect(result_shadow)
        self._set_result_style("success")
        main_layout.addWidget(self._result_card)

        # --- Cards 2 + 3 side-by-side: Summary stats | Per-entity breakdown ---
        # Wide screens have more horizontal space than vertical; use it.
        # Stats card on the left (40%), breakdown table on the right (60%).
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)

        stats_card = self._create_card()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(24, 20, 24, 20)
        stats_layout.setSpacing(14)

        self._stats_title = QLabel(tr("wizard.import.step6.results_summary"))
        self._stats_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._stats_title.setStyleSheet("color: #212B36; background: transparent;")
        stats_layout.addWidget(self._stats_title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        stats_layout.addWidget(sep)

        # Stat boxes in a 2-column grid (3 rows: approved+committed,
        # failed+skipped, rate spanning both columns).
        stats_grid = QGridLayout()
        stats_grid.setSpacing(12)

        self._approved_box, self._approved_label = self._create_stat_box(
            tr("wizard.import.step6.stat_approved"), "0", "#3B82F6", "#EFF6FF"
        )
        self._committed_box, self._committed_label = self._create_stat_box(
            tr("wizard.import.step6.stat_committed"), "0", "#10B981", "#ECFDF5"
        )
        self._failed_box, self._failed_label = self._create_stat_box(
            tr("wizard.import.step6.stat_failed"), "0", "#EF4444", "#FEF2F2"
        )
        self._skipped_box, self._skipped_label = self._create_stat_box(
            tr("wizard.import.step6.stat_skipped"), "0", "#F59E0B", "#FFFBEB"
        )
        self._rate_box, self._rate_label = self._create_stat_box(
            tr("wizard.import.step6.stat_success_rate"), "0%", "#8B5CF6", "#F5F3FF"
        )

        stats_grid.addWidget(self._approved_box, 0, 0)
        stats_grid.addWidget(self._committed_box, 0, 1)
        stats_grid.addWidget(self._failed_box, 1, 0)
        stats_grid.addWidget(self._skipped_box, 1, 1)
        stats_grid.addWidget(self._rate_box, 2, 0, 1, 2)

        stats_layout.addLayout(stats_grid)
        stats_layout.addStretch()

        # --- Card 3: Per-entity breakdown table ---
        breakdown_card = self._create_card()
        breakdown_layout = QVBoxLayout(breakdown_card)
        breakdown_layout.setContentsMargins(24, 20, 24, 20)
        breakdown_layout.setSpacing(14)

        self._breakdown_title = QLabel(tr("wizard.import.step6.breakdown_title"))
        self._breakdown_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._breakdown_title.setStyleSheet("color: #212B36; background: transparent;")
        breakdown_layout.addWidget(self._breakdown_title)

        self._breakdown_table = QTableWidget()
        self._breakdown_table.setColumnCount(5)
        self._breakdown_table.setHorizontalHeaderLabels([
            tr("wizard.import.step6.col_entity_type"),
            tr("wizard.import.step6.col_approved"),
            tr("wizard.import.step6.col_committed"),
            tr("wizard.import.step6.col_failed"),
            tr("wizard.import.step6.col_skipped"),
        ])
        self._breakdown_table.setLayoutDirection(get_layout_direction())
        self._breakdown_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._breakdown_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._breakdown_table.verticalHeader().setVisible(False)
        self._breakdown_table.setAlternatingRowColors(True)

        header = self._breakdown_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self._breakdown_table.setColumnWidth(0, ScreenScale.w(140))
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.Stretch)

        self._breakdown_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                gridline-color: #F4F6F8;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border: none;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                color: #637381;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid #E1E8ED;
                font-weight: 600;
            }
        """)
        self._breakdown_table.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        # Let the table expand vertically to fill the card — no fixed
        # min/max height, so it grows when the window has spare space and
        # the inner scrollbar disappears.
        self._breakdown_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        breakdown_layout.addWidget(self._breakdown_table, 1)

        # Place stats (left, 4/10 width) and breakdown (right, 6/10 width)
        # side by side. Use stretch factors so they scale with the window.
        cards_row.addWidget(stats_card, 4)
        cards_row.addWidget(breakdown_card, 6)
        # Stretch factor 1 on the cards row so it consumes the empty
        # space below the result header, instead of leaving a wide gap
        # above the footer button.
        main_layout.addLayout(cards_row, 1)

        # The legacy "معلومات إضافية" card was removed per UX feedback —
        # the per-entity breakdown above already covers what the user
        # needs to see. Backwards-compat stubs are kept below so older
        # call sites (_update_extra_info, update_language) don't crash.
        self._extra_card = None
        self._extra_title = None
        self._extra_rows_layout = None
        self._extra_labels = {}
        self._extra_name_labels = {}
        self._extra_keys_tr = []

        # --- Card 5: Errors (hidden if none) ---
        self._errors_card = self._create_card()
        errors_card_layout = QVBoxLayout(self._errors_card)
        errors_card_layout.setContentsMargins(32, 24, 32, 24)
        errors_card_layout.setSpacing(12)

        errors_title_row = QHBoxLayout()
        self._errors_title_label = QLabel(tr("wizard.import.step6.errors_title"))
        self._errors_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._errors_title_label.setStyleSheet(f"color: {Colors.ERROR}; background: transparent;")
        errors_title_row.addWidget(self._errors_title_label)

        self._errors_count_label = QLabel("")
        self._errors_count_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._errors_count_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        errors_title_row.addWidget(self._errors_count_label)
        errors_title_row.addStretch()
        errors_card_layout.addLayout(errors_title_row)

        self._errors_scroll = QScrollArea()
        self._errors_scroll.setWidgetResizable(True)
        self._errors_scroll.setFrameShape(QFrame.NoFrame)
        self._errors_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )
        # Constrain the errors card so the page itself never scrolls;
        # only the inner errors list scrolls when many errors are present.
        self._errors_scroll.setMaximumHeight(ScreenScale.h(140))

        self._errors_container = QWidget()
        self._errors_container.setStyleSheet("background: transparent;")
        self._errors_layout = QVBoxLayout(self._errors_container)
        self._errors_layout.setContentsMargins(0, 0, 0, 0)
        self._errors_layout.setSpacing(6)

        self._errors_scroll.setWidget(self._errors_container)
        errors_card_layout.addWidget(self._errors_scroll)

        self._errors_card.setVisible(False)
        main_layout.addWidget(self._errors_card)

        # No trailing stretch — cards_row already absorbs the available
        # vertical space via its stretch factor, so the cards reach the
        # bottom of the page instead of leaving a gap.

    def _create_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border-radius: 16px;
                border: 1px solid #E2EAF2;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 22))
        card.setGraphicsEffect(shadow)
        return card

    def _create_stat_box(self, label_text: str, value_text: str,
                         color: str, bg: str):
        """Create a stat box with value and label. Returns (box, label)."""
        box = QFrame()
        box.setFixedHeight(ScreenScale.h(70))
        box.setMinimumWidth(ScreenScale.w(120))
        box.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg}, stop:1 #FFFFFF);
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
        value.setLayoutDirection(Qt.LeftToRight)
        box_layout.addWidget(value)

        label = QLabel(label_text)
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet("color: #637381;")
        label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(label)

        return box, label

    def _set_result_style(self, status: str = "success"):
        """Apply styling to the result card. status: 'success', 'partial', 'error'."""
        if status == "success":
            self._result_card.setStyleSheet("""
                QFrame {
                    background-color: #ECFDF5;
                    border-radius: 16px;
                    border: 1px solid #A7F3D0;
                }
                QFrame QLabel { border: none; background: transparent; }
            """)
            self._result_title.setStyleSheet("color: #065F46; background: transparent;")
            self._result_subtitle.setStyleSheet("color: #047857; background: transparent;")
            meta_color = "#047857"
        elif status == "partial":
            self._result_card.setStyleSheet("""
                QFrame {
                    background-color: #FFFBEB;
                    border-radius: 16px;
                    border: 1px solid #FDE68A;
                }
                QFrame QLabel { border: none; background: transparent; }
            """)
            self._result_title.setStyleSheet("color: #92400E; background: transparent;")
            self._result_subtitle.setStyleSheet("color: #B45309; background: transparent;")
            meta_color = "#B45309"
        else:
            self._result_card.setStyleSheet("""
                QFrame {
                    background-color: #FEF2F2;
                    border-radius: 16px;
                    border: 1px solid #FECACA;
                }
                QFrame QLabel { border: none; background: transparent; }
            """)
            self._result_title.setStyleSheet("color: #991B1B; background: transparent;")
            self._result_subtitle.setStyleSheet("color: #B91C1C; background: transparent;")
            meta_color = "#B91C1C"

        for lbl in (self._duration_label, self._date_label, self._pkg_number_label):
            lbl.setStyleSheet(f"color: {meta_color}; background: transparent;")

    def _create_loading_overlay(self):
        overlay = QWidget(self)
        overlay.setStyleSheet("background-color: rgba(255,255,255,200);")
        overlay.setVisible(False)

        ol = QVBoxLayout(overlay)
        ol.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(ScreenScale.w(240), ScreenScale.h(90))
        card.setStyleSheet(
            "QFrame { background: white; border-radius: 16px; }"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 4)
        card.setGraphicsEffect(shadow)

        cl = QVBoxLayout(card)
        cl.setAlignment(Qt.AlignCenter)
        cl.setSpacing(6)

        self._ld_label = QLabel(tr("wizard.import.step6.loading"))
        self._ld_label.setAlignment(Qt.AlignCenter)
        self._ld_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._ld_label.setStyleSheet("color: #3890DF; background: transparent;")
        cl.addWidget(self._ld_label)

        self._ld_dots = QLabel("")
        self._ld_dots.setAlignment(Qt.AlignCenter)
        self._ld_dots.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        self._ld_dots.setStyleSheet("color: #3890DF; background: transparent;")
        cl.addWidget(self._ld_dots)

        ol.addWidget(card)
        return overlay

    def _show_loading(self, msg=None):
        self._ld_label.setText(msg or tr("wizard.import.step6.loading"))
        self._dots_count = 0
        self._loading_overlay.setVisible(True)
        self._loading_overlay.raise_()
        self._loading_overlay.setGeometry(self.rect())
        if not hasattr(self, '_dots_timer'):
            self._dots_timer = QTimer(self)
            self._dots_timer.timeout.connect(self._animate_dots)
        self._dots_timer.start(400)

    def _hide_loading(self):
        self._loading_overlay.setVisible(False)
        if hasattr(self, '_dots_timer'):
            self._dots_timer.stop()

    def _animate_dots(self):
        self._dots_count = (self._dots_count % 3) + 1
        self._ld_dots.setText("." * self._dots_count)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.setGeometry(self.rect())

    def load_report(self, package_id: str):
        """Load the commit report from the controller."""
        logger.info(f"Loading commit report for package {package_id}")

        self._show_loading(tr("wizard.import.step6.loading_report"))

        result = self.import_controller.get_commit_report(package_id)
        self._hide_loading()

        if not result.success:
            self._set_result_style("error")
            self._result_title.setText(tr("wizard.import.step6.report_load_failed"))
            self._result_subtitle.setText(result.message_ar or result.message)
            from ui.components.message_dialog import MessageDialog
            MessageDialog.error(
                self, tr("wizard.import.step6.error"),
                result.message_ar or tr("wizard.import.step6.commit_report_load_failed")
            )
            return

        self._report_data = result.data or {}
        self._update_ui()

    def _update_ui(self):
        """Update UI with report data."""
        d = self._report_data
        if not d:
            return

        total_approved = d.get("totalRecordsApproved", 0)
        total_committed = d.get("totalRecordsCommitted", 0)
        total_failed = d.get("totalRecordsFailed", 0)
        total_skipped = d.get("totalRecordsSkipped", 0)
        success_rate = d.get("successRate", 0)
        is_fully_ok = d.get("isFullySuccessful", False)

        # Result header
        if is_fully_ok and total_failed == 0:
            self._set_result_style("success")
            self._result_title.setText(tr("wizard.import.step6.commit_success"))
            self._result_subtitle.setText(
                tr("wizard.import.step6.commit_success_detail", count=total_committed)
            )
        elif total_committed > 0 and total_failed > 0:
            self._set_result_style("partial")
            self._result_title.setText(tr("wizard.import.step6.commit_partial"))
            self._result_subtitle.setText(
                tr("wizard.import.step6.commit_partial_detail", committed=total_committed, failed=total_failed)
            )
        else:
            self._set_result_style("error")
            self._result_title.setText(tr("wizard.import.step6.commit_failed"))
            self._result_subtitle.setText(tr("wizard.import.step6.commit_failed_detail", count=total_failed))

        # Meta info
        duration = d.get("duration", "")
        committed_at = d.get("committedAtUtc", "")
        pkg_number = d.get("packageNumber", "")

        if duration:
            self._duration_label.setText(tr("wizard.import.step6.meta_duration", value=duration))
        if committed_at:
            date_part = committed_at[:10] if len(committed_at) >= 10 else committed_at
            self._date_label.setText(tr("wizard.import.step6.meta_date", value=date_part))
        if pkg_number:
            self._pkg_number_label.setText(tr("wizard.import.step6.meta_package_number", value=pkg_number))

        # Summary stat boxes
        self._update_stat_value(self._approved_box, str(total_approved))
        self._update_stat_value(self._committed_box, str(total_committed))
        self._update_stat_value(self._failed_box, str(total_failed))
        self._update_stat_value(self._skipped_box, str(total_skipped))
        rate_str = f"{success_rate}%" if isinstance(success_rate, int) else f"{success_rate:.1f}%"
        self._update_stat_value(self._rate_box, rate_str)

        # Per-entity breakdown table
        self._populate_breakdown_table(d)

        # Extra info
        self._update_extra_info(d)

        # Errors
        errors = d.get("errors", [])
        self._populate_errors(errors)

    def _update_stat_value(self, stat_box: QFrame, value: str):
        value_label = stat_box.findChild(QLabel, "stat_value")
        if value_label:
            value_label.setText(value)

    def _populate_breakdown_table(self, d: dict):
        """Fill the per-entity breakdown table."""
        rows = []
        for key, ar_name in _get_entity_sections():
            section = d.get(key)
            if not isinstance(section, dict):
                continue
            approved = section.get("approved", 0)
            committed = section.get("committed", 0)
            failed = section.get("failed", 0)
            skipped = section.get("skipped", 0)
            if approved or committed or failed or skipped:
                rows.append((ar_name, approved, committed, failed, skipped))

        self._breakdown_table.setRowCount(len(rows))
        for row_idx, (name, approved, committed, failed, skipped) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(get_text_alignment() | Qt.AlignVCenter)
            self._breakdown_table.setItem(row_idx, 0, name_item)

            for col, val in enumerate([approved, committed, failed, skipped], start=1):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 3 and val > 0:
                    item.setForeground(Qt.red)
                self._breakdown_table.setItem(row_idx, col, item)

            self._breakdown_table.setRowHeight(row_idx, 40)

    def _update_extra_info(self, d: dict):
        """No-op stub. The "extra info" card was removed per UX feedback;
        this method is kept so older call sites don't crash."""
        return

    def _populate_errors(self, errors: list):
        """Populate the errors section."""
        # Clear existing
        while self._errors_layout.count():
            item = self._errors_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not errors:
            self._errors_card.setVisible(False)
            return

        self._errors_card.setVisible(True)
        self._errors_count_label.setText(tr("wizard.import.step6.error_count", count=len(errors)))

        entity_names = {k: v for k, v in _get_entity_sections()}

        for err in errors:
            row = QFrame()
            row.setFixedHeight(ScreenScale.h(48))
            row.setStyleSheet("""
                QFrame {
                    background-color: #FEF2F2;
                    border: 1px solid #FECACA;
                    border-radius: 6px;
                }
                QFrame QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 4, 12, 4)
            row_layout.setSpacing(12)

            entity_type = err.get("entityType", "")
            entity_label = QLabel(entity_names.get(entity_type, entity_type))
            entity_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            entity_label.setStyleSheet("color: #991B1B;")
            entity_label.setMinimumWidth(ScreenScale.w(160))
            row_layout.addWidget(entity_label)

            original_id = err.get("originalEntityId", "")
            if original_id:
                id_label = QLabel(str(original_id)[:12])
                id_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
                id_label.setStyleSheet("color: #B91C1C;")
                id_label.setFixedWidth(ScreenScale.w(100))
                row_layout.addWidget(id_label)

            msg = err.get("errorMessage", "")
            msg_label = QLabel(msg)
            msg_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            msg_label.setStyleSheet("color: #7F1D1D;")
            msg_label.setWordWrap(True)
            row_layout.addWidget(msg_label, 1)

            self._errors_layout.addWidget(row)

        self._errors_layout.addStretch()

    def set_error(self, error_message: str):
        """Set the report to error state with a message."""
        self._set_result_style("error")
        self._result_title.setText(tr("wizard.import.step6.commit_failed"))
        self._result_subtitle.setText(error_message)

    def get_report_data(self) -> dict:
        """Return the loaded report data."""
        return self._report_data or {}

    def reset(self):
        """Reset the step to initial state."""
        self._report_data = None
        self._set_result_style("success")
        self._result_title.setText(tr("wizard.import.step6.commit_success"))
        self._result_subtitle.setText("")
        self._duration_label.setText("")
        self._date_label.setText("")
        self._pkg_number_label.setText("")
        self._update_stat_value(self._approved_box, "0")
        self._update_stat_value(self._committed_box, "0")
        self._update_stat_value(self._failed_box, "0")
        self._update_stat_value(self._skipped_box, "0")
        self._update_stat_value(self._rate_box, "0%")
        self._breakdown_table.setRowCount(0)
        for label in self._extra_labels.values():
            label.setText("-")
        self._errors_card.setVisible(False)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Result title — reset to default when no report data loaded yet
        if not self._report_data:
            self._result_title.setText(tr("wizard.import.step6.commit_success"))
            self._result_subtitle.setText("")

        # Loading label
        self._ld_label.setText(tr("wizard.import.step6.loading"))

        # Section titles
        self._stats_title.setText(tr("wizard.import.step6.results_summary"))
        self._breakdown_title.setText(tr("wizard.import.step6.breakdown_title"))
        # _extra_title was removed with the legacy "Additional info" card.
        if self._extra_title is not None:
            self._extra_title.setText(tr("wizard.import.step6.extra_info_title"))
        self._errors_title_label.setText(tr("wizard.import.step6.errors_title"))

        # Stat box labels
        self._approved_label.setText(tr("wizard.import.step6.stat_approved"))
        self._committed_label.setText(tr("wizard.import.step6.stat_committed"))
        self._failed_label.setText(tr("wizard.import.step6.stat_failed"))
        self._skipped_label.setText(tr("wizard.import.step6.stat_skipped"))
        self._rate_label.setText(tr("wizard.import.step6.stat_success_rate"))

        # Extra info name labels
        for key, tr_key in self._extra_keys_tr:
            if key in self._extra_name_labels:
                self._extra_name_labels[key].setText(f"{tr(tr_key)}:")

        # Breakdown table header labels
        self._breakdown_table.setHorizontalHeaderLabels([
            tr("wizard.import.step6.col_entity_type"),
            tr("wizard.import.step6.col_approved"),
            tr("wizard.import.step6.col_committed"),
            tr("wizard.import.step6.col_failed"),
            tr("wizard.import.step6.col_skipped"),
        ])
        self._breakdown_table.setLayoutDirection(get_layout_direction())

        # Re-populate all dynamic content with updated translations
        if self._report_data:
            self._update_ui()
