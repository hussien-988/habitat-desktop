# -*- coding: utf-8 -*-
"""Import wizard step 2: staging results and validation report."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QGraphicsDropShadowEffect,
    QPushButton,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor

from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction, get_text_alignment
from utils.logger import get_logger

logger = get_logger(__name__)

# Entity type labels (key in API)
_ENTITY_SECTION_KEYS = [
    ('surveys', 'wizard.import.entity.surveys'),
    ('buildings', 'wizard.import.entity.buildings'),
    ('propertyUnits', 'wizard.import.entity.property_units'),
    ('persons', 'wizard.import.entity.persons'),
    ('households', 'wizard.import.entity.households'),
    ('personPropertyRelations', 'wizard.import.entity.person_property_relations'),
    ('evidences', 'wizard.import.entity.evidences'),
    ('claims', 'wizard.import.entity.claims'),
]


def _get_entity_sections():
    return [(k, tr(tr_key)) for k, tr_key in _ENTITY_SECTION_KEYS]


class ImportStep2Staging(QWidget):
    """Step 2: Staging results, validation report, and duplicate detection."""

    resolve_duplicates_requested = pyqtSignal()

    def __init__(self, import_controller, package_id, duplicates_data=None, skip_load=False, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id
        self._report_data = None
        self._duplicates_data = duplicates_data
        self._dots_count = 0
        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()
        if not skip_load:
            self.load_report(package_id)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(0)

        # Main scroll area
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        main_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # ── Card 1: Summary Stats ──
        summary_card = self._build_summary_card()
        self._apply_card_shadow(summary_card)
        scroll_layout.addWidget(summary_card)

        # ── Card 2: Entity Breakdown Table ──
        entity_card = self._build_entity_table_card()
        self._apply_card_shadow(entity_card)
        scroll_layout.addWidget(entity_card)

        # ── Card 3: Duplicates / Conflicts ──
        dup_card = self._build_duplicates_card()
        self._apply_card_shadow(dup_card)
        scroll_layout.addWidget(dup_card)

        # ── Card 4: Validator Level Results ──
        self._level_card = self._build_level_results_card()
        self._apply_card_shadow(self._level_card)
        self._level_card.setVisible(False)
        scroll_layout.addWidget(self._level_card)

        scroll_layout.addStretch()
        main_scroll.setWidget(scroll_content)
        main_layout.addWidget(main_scroll, 1)

    # ── Card builders ────────────────────────────────────────────────

    def _build_summary_card(self) -> QFrame:
        """Card with total summary stats."""
        card = QFrame()
        card.setStyleSheet(self._card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self._summary_title_label = QLabel(tr("wizard.import.step2.title"))
        self._summary_title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        self._summary_title_label.setStyleSheet("color: #212B36; background: transparent;")
        layout.addWidget(self._summary_title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        layout.addWidget(sep)

        # Status badge (isClean)
        self._clean_badge = QLabel("")
        self._clean_badge.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._clean_badge.setAlignment(Qt.AlignCenter)
        self._clean_badge.setFixedHeight(ScreenScale.h(32))
        self._clean_badge.setMinimumWidth(ScreenScale.w(200))
        self._clean_badge.setVisible(False)
        layout.addWidget(self._clean_badge, alignment=get_text_alignment())

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        self._stat_total = self._create_stat_box(tr("wizard.import.step2.total_records"), "0", "#3890DF", "#EBF5FF")
        stats_row.addWidget(self._stat_total)
        self._stat_valid = self._create_stat_box(tr("wizard.import.step2.valid"), "0", "#10B981", "#ECFDF5")
        stats_row.addWidget(self._stat_valid)
        self._stat_invalid = self._create_stat_box(tr("wizard.import.step2.invalid"), "0", "#EF4444", "#FEF2F2")
        stats_row.addWidget(self._stat_invalid)
        self._stat_warning = self._create_stat_box(tr("wizard.import.step2.warnings"), "0", "#F59E0B", "#FFFBEB")
        stats_row.addWidget(self._stat_warning)
        self._stat_skipped = self._create_stat_box(tr("wizard.import.step2.skipped"), "0", "#9CA3AF", "#F3F4F6")
        stats_row.addWidget(self._stat_skipped)
        self._stat_pending = self._create_stat_box(tr("wizard.import.step2.pending"), "0", "#8B5CF6", "#F5F3FF")
        stats_row.addWidget(self._stat_pending)

        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Attachments info
        self._attachments_label = QLabel("")
        self._attachments_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._attachments_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        self._attachments_label.setVisible(False)
        layout.addWidget(self._attachments_label)

        return card

    def _build_entity_table_card(self) -> QFrame:
        """Card with per-entity breakdown table."""
        card = QFrame()
        card.setStyleSheet(self._card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._entity_title_label = QLabel(tr("wizard.import.step2.entity_breakdown"))
        self._entity_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._entity_title_label.setStyleSheet("color: #212B36; background: transparent;")
        layout.addWidget(self._entity_title_label)

        entity_sections = _get_entity_sections()

        # Table: entity type | total | valid | invalid | warning | skipped | pending
        self._entity_table = QTableWidget()
        self._entity_table.setColumnCount(7)
        self._entity_table.setHorizontalHeaderLabels([
            tr("wizard.import.step2.col_entity"),
            tr("wizard.import.step2.col_total"),
            tr("wizard.import.step2.col_valid"),
            tr("wizard.import.step2.col_invalid"),
            tr("wizard.import.step2.col_warning"),
            tr("wizard.import.step2.col_skipped"),
            tr("wizard.import.step2.col_pending"),
        ])
        self._entity_table.setRowCount(len(entity_sections))
        self._entity_table.setLayoutDirection(get_layout_direction())
        self._entity_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._entity_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._entity_table.verticalHeader().setVisible(False)
        self._entity_table.setFixedHeight(ScreenScale.h(44) * len(_ENTITY_SECTION_KEYS) + ScreenScale.h(36))

        header = self._entity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self._entity_table.setColumnWidth(0, ScreenScale.w(160))
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.Stretch)

        self._entity_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                gridline-color: #F4F6F8;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border: none;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                color: #637381;
                padding: 8px 8px;
                border: none;
                border-bottom: 2px solid #E1E8ED;
                font-weight: 600;
            }
        """)
        self._entity_table.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        header.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))

        # Pre-populate with entity names
        for row_idx, (key, ar_name) in enumerate(entity_sections):
            name_item = QTableWidgetItem(ar_name)
            name_item.setTextAlignment(get_text_alignment() | Qt.AlignVCenter)
            self._entity_table.setItem(row_idx, 0, name_item)
            for col in range(1, 7):
                item = QTableWidgetItem("0")
                item.setTextAlignment(Qt.AlignCenter)
                self._entity_table.setItem(row_idx, col, item)
            self._entity_table.setRowHeight(row_idx, 40)

        layout.addWidget(self._entity_table)
        return card

    def _build_duplicates_card(self) -> QFrame:
        """Card with duplicate/conflict detection results."""
        card = QFrame()
        card.setStyleSheet(self._card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self._dup_title_label = QLabel(tr("wizard.import.step2.duplicates_title"))
        self._dup_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._dup_title_label.setStyleSheet("color: #212B36; background: transparent;")
        layout.addWidget(self._dup_title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        layout.addWidget(sep)

        # Stats row
        dup_stats = QHBoxLayout()
        dup_stats.setSpacing(16)

        self._dup_persons = self._create_stat_box(tr("wizard.import.step2.dup_persons"), "0", "#F59E0B", "#FFFBEB")
        dup_stats.addWidget(self._dup_persons)
        self._dup_properties = self._create_stat_box(tr("wizard.import.step2.dup_properties"), "0", "#F59E0B", "#FFFBEB")
        dup_stats.addWidget(self._dup_properties)
        self._dup_total = self._create_stat_box(tr("wizard.import.step2.dup_total"), "0", "#EF4444", "#FEF2F2")
        dup_stats.addWidget(self._dup_total)

        dup_stats.addStretch()
        layout.addLayout(dup_stats)

        # Status label
        self._dup_status = QLabel("")
        self._dup_status.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._dup_status.setAlignment(Qt.AlignCenter)
        self._dup_status.setStyleSheet("color: #10B981; background: transparent;")
        layout.addWidget(self._dup_status)

        # Warning banner (shown only when duplicates exist)
        self._dup_warning = QFrame()
        self._dup_warning.setStyleSheet("""
            QFrame {
                background-color: #FFFBEB;
                border: 1px solid #FDE68A;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        warning_layout = QHBoxLayout(self._dup_warning)
        warning_layout.setContentsMargins(16, 12, 16, 12)
        warning_layout.setSpacing(10)

        warning_icon = QLabel("!")
        warning_icon.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        warning_icon.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        warning_icon.setAlignment(Qt.AlignCenter)
        warning_icon.setStyleSheet("""
            color: #F59E0B;
            background-color: #FEF3C7;
            border-radius: 14px;
        """)
        warning_layout.addWidget(warning_icon)

        self._dup_warning_text = QLabel(
            tr("wizard.import.step2.dup_warning_text")
        )
        self._dup_warning_text.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._dup_warning_text.setStyleSheet("color: #92400E;")
        self._dup_warning_text.setWordWrap(True)
        warning_layout.addWidget(self._dup_warning_text, 1)

        layout.addWidget(self._dup_warning)
        self._dup_warning.setVisible(False)

        # "Resolve duplicates" button
        self._resolve_dups_btn = QPushButton(tr("wizard.import.step2.resolve_duplicates"))
        self._resolve_dups_btn.setCursor(Qt.PointingHandCursor)
        self._resolve_dups_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._resolve_dups_btn.setMinimumWidth(ScreenScale.w(180))
        self._resolve_dups_btn.setFixedHeight(ScreenScale.h(40))
        self._resolve_dups_btn.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #D97706; }
        """)
        self._resolve_dups_btn.clicked.connect(self.resolve_duplicates_requested.emit)
        self._resolve_dups_btn.setVisible(False)
        layout.addWidget(self._resolve_dups_btn, alignment=Qt.AlignCenter)

        return card

    def _build_level_results_card(self) -> QFrame:
        """Card with validator level results."""
        card = QFrame()
        card.setStyleSheet(self._card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self._level_title_label = QLabel(tr("wizard.import.step2.level_results_title"))
        self._level_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._level_title_label.setStyleSheet("color: #212B36; background: transparent;")
        layout.addWidget(self._level_title_label)

        # Container for level rows
        self._levels_container = QVBoxLayout()
        self._levels_container.setSpacing(8)

        empty = QLabel(tr("wizard.import.step2.no_data_yet"))
        empty.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        empty.setStyleSheet("color: #9CA3AF; background: transparent;")
        empty.setAlignment(Qt.AlignCenter)
        self._levels_container.addWidget(empty)

        layout.addLayout(self._levels_container)
        return card

    # ── Reusable widgets ─────────────────────────────────────────────

    def _create_stat_box(self, label_text: str, value_text: str,
                         color: str, bg: str) -> QFrame:
        """Create a stat box with value and label."""
        box = QFrame()
        box.setFixedHeight(ScreenScale.h(64))
        box.setMinimumWidth(ScreenScale.w(120))
        box.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg}, stop:1 #FFFFFF);
                border-radius: 10px;
                border: none;
            }}
            QFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 6, 12, 6)
        box_layout.setSpacing(2)
        box_layout.setAlignment(Qt.AlignCenter)

        value = QLabel(value_text)
        value.setObjectName("stat_value")
        value.setFont(create_font(size=16, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {color};")
        value.setAlignment(Qt.AlignCenter)
        value.setLayoutDirection(Qt.LeftToRight)
        box_layout.addWidget(value)

        label = QLabel(label_text)
        label.setObjectName("stat_label")
        label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet("color: #637381;")
        label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(label)

        return box

    def _update_stat_value(self, box: QFrame, value: str):
        """Update the value label inside a stat box."""
        label = box.findChild(QLabel, "stat_value")
        if label:
            label.setText(value)

    def _apply_card_shadow(self, card: QFrame):
        """Apply consistent drop shadow to a card widget."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 22))
        card.setGraphicsEffect(shadow)

    def _card_style(self) -> str:
        return """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border-radius: 16px;
                border: 1px solid rgba(226, 234, 242, 0.4);
            }
        """

    # ── Data loading ─────────────────────────────────────────────────

    # -- Loading overlay -------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 200); }")
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(ScreenScale.w(240), ScreenScale.h(90))
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

        self._ld_label = QLabel(tr("wizard.import.step2.loading"))
        self._ld_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._ld_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._ld_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._ld_label)

        self._ld_dots = QLabel("")
        self._ld_dots.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._ld_dots.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._ld_dots.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._ld_dots)

        overlay_layout.addWidget(card)

        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)
        return overlay

    def _show_loading(self, message: str):
        self._ld_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)

    def _hide_loading(self):
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

    def _animate_dots(self):
        self._dots_count = (self._dots_count + 1) % 4
        self._ld_dots.setText("." * self._dots_count)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Data loading ----------------------------------------------------------

    def load_report(self, package_id: str):
        """Load validation report from the controller."""
        logger.info(f"Loading validation report for package {package_id}")

        self._show_loading(tr("wizard.import.step2.loading_report"))
        result = self.import_controller.get_validation_report(package_id)
        self._hide_loading()

        if not result.success:
            self._show_error(result.message_ar or tr("wizard.import.step2.report_load_failed"))
            from ui.components.message_dialog import MessageDialog
            MessageDialog.error(self, tr("wizard.import.step2.error"), result.message_ar or tr("wizard.import.step2.report_load_failed"))
            return

        self._report_data = result.data or {}
        self._update_summary()
        self._update_entity_table()
        self._update_duplicates()
        self._update_level_results()

    def _update_summary(self):
        """Update summary stats from report data."""
        d = self._report_data

        self._update_stat_value(self._stat_total, str(d.get("totalRecords", 0)))
        self._update_stat_value(self._stat_valid, str(d.get("totalValid", 0)))
        self._update_stat_value(self._stat_invalid, str(d.get("totalInvalid", 0)))
        self._update_stat_value(self._stat_warning, str(d.get("totalWarning", 0)))
        self._update_stat_value(self._stat_skipped, str(d.get("totalSkipped", 0)))
        self._update_stat_value(self._stat_pending, str(d.get("totalPending", 0)))

        # isClean badge
        is_clean = d.get("isClean", False)
        if is_clean:
            self._clean_badge.setText(tr("wizard.import.step2.data_clean"))
            self._clean_badge.setStyleSheet("""
                color: #065F46;
                background-color: #ECFDF5;
                border: 1px solid #A7F3D0;
                border-radius: 16px;
                padding: 4px 20px;
            """)
        else:
            self._clean_badge.setText(tr("wizard.import.step2.has_issues"))
            self._clean_badge.setStyleSheet("""
                color: #991B1B;
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 16px;
                padding: 4px 20px;
            """)
        self._clean_badge.setVisible(True)

        # Attachments
        files = d.get("attachmentFilesExtracted", 0)
        bytes_val = d.get("attachmentBytesExtracted", 0)
        if files > 0:
            size_mb = bytes_val / (1024 * 1024)
            self._attachments_label.setText(
                tr("wizard.import.step2.attachments_info", files=files, size=f"{size_mb:.1f}")
            )
            self._attachments_label.setVisible(True)

    def _update_entity_table(self):
        """Update per-entity breakdown table."""
        d = self._report_data
        for row_idx, (key, _) in enumerate(_ENTITY_SECTION_KEYS):
            section = d.get(key, {})
            if not isinstance(section, dict):
                continue

            values = [
                section.get("total", 0),
                section.get("valid", 0),
                section.get("invalid", 0),
                section.get("warning", 0),
                section.get("skipped", 0),
                section.get("pending", 0),
            ]

            for col, val in enumerate(values, start=1):
                item = self._entity_table.item(row_idx, col)
                if item:
                    item.setText(str(val))
                    # Color invalid/warning cells
                    if col == 3 and val > 0:  # invalid
                        item.setForeground(Qt.red)
                    elif col == 4 and val > 0:  # warning
                        from PyQt5.QtGui import QColor
                        item.setForeground(QColor("#F59E0B"))

    def _update_duplicates(self):
        """Update duplicates section from report data."""
        d = self._report_data

        person_dups = d.get("personDuplicatesFound", 0)
        property_dups = d.get("propertyDuplicatesFound", 0)
        total_conflicts = d.get("totalConflictsFound", 0)
        dup_ran = d.get("duplicateDetectionRan", False)

        self._update_stat_value(self._dup_persons, str(person_dups))
        self._update_stat_value(self._dup_properties, str(property_dups))
        self._update_stat_value(self._dup_total, str(total_conflicts))

        if not dup_ran:
            self._dup_status.setText(tr("wizard.import.step2.dup_not_run"))
            self._dup_status.setStyleSheet("color: #9CA3AF; background: transparent;")
            self._dup_warning.setVisible(False)
            self._resolve_dups_btn.setVisible(False)
        elif total_conflicts == 0:
            self._dup_status.setText(tr("wizard.import.step2.no_duplicates"))
            self._dup_status.setStyleSheet("color: #10B981; background: transparent;")
            self._dup_warning.setVisible(False)
            self._resolve_dups_btn.setVisible(False)
        else:
            self._dup_status.setText(
                tr("wizard.import.step2.conflicts_found",
                   total=total_conflicts, persons=person_dups, properties=property_dups)
            )
            self._dup_status.setStyleSheet("color: #F59E0B; background: transparent;")
            self._dup_warning.setVisible(True)
            self._resolve_dups_btn.setVisible(True)

    def _update_level_results(self):
        """Update validator level results."""
        # Clear existing
        while self._levels_container.count():
            item = self._levels_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        levels = self._report_data.get("levelResults", [])

        if not levels:
            self._level_card.setVisible(False)
            return

        self._level_card.setVisible(True)
        for level_data in levels:
            row = self._create_level_row(level_data)
            self._levels_container.addWidget(row)

    def _create_level_row(self, level_data: dict) -> QFrame:
        """Create a row for a single validator level result."""
        row = QFrame()
        errors = level_data.get("errorCount", 0)
        warnings = level_data.get("warningCount", 0)

        if errors > 0:
            border_color = "#FECACA"
            bg_color = "#FEF2F2"
        elif warnings > 0:
            border_color = "#FDE68A"
            bg_color = "#FFFBEB"
        else:
            border_color = "#D1FAE5"
            bg_color = "#ECFDF5"

        row.setFixedHeight(ScreenScale.h(48))
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(16, 0, 16, 0)
        row_layout.setSpacing(16)

        # Level number
        level_num = level_data.get("level", 0)
        level_label = QLabel(tr("wizard.import.step2.level_num", num=level_num))
        level_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        level_label.setStyleSheet("color: #212B36;")
        level_label.setFixedWidth(ScreenScale.w(80))
        row_layout.addWidget(level_label)

        # Validator name
        name = level_data.get("validatorName", "")
        name_label = QLabel(name)
        name_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        name_label.setStyleSheet("color: #637381;")
        row_layout.addWidget(name_label, 1)

        # Records checked
        checked = level_data.get("recordsChecked", 0)
        checked_label = QLabel(tr("wizard.import.step2.records_checked", count=checked))
        checked_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        checked_label.setStyleSheet("color: #9CA3AF;")
        row_layout.addWidget(checked_label)

        # Errors
        if errors > 0:
            err_label = QLabel(tr("wizard.import.step2.error_count", count=errors))
            err_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            err_label.setStyleSheet(f"color: {Colors.ERROR};")
            row_layout.addWidget(err_label)

        # Warnings
        if warnings > 0:
            warn_label = QLabel(tr("wizard.import.step2.warning_count", count=warnings))
            warn_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            warn_label.setStyleSheet("color: #F59E0B;")
            row_layout.addWidget(warn_label)

        # Duration
        duration = level_data.get("durationMs", 0)
        if duration > 0:
            dur_label = QLabel(f"{duration}ms")
            dur_label.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            dur_label.setStyleSheet("color: #D1D5DB;")
            row_layout.addWidget(dur_label)

        return row

    def _show_error(self, message: str):
        """Display an error message."""
        self._clean_badge.setText(message)
        self._clean_badge.setStyleSheet("""
            color: #991B1B;
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 16px;
            padding: 4px 20px;
        """)
        self._clean_badge.setVisible(True)

    @staticmethod
    def _refresh_stat_label(box, text: str):
        """Update the title label inside a stat box (uses objectName='stat_label')."""
        from PyQt5.QtWidgets import QLabel
        lbl = box.findChild(QLabel, "stat_label")
        if lbl:
            lbl.setText(text)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Section titles
        self._summary_title_label.setText(tr("wizard.import.step2.title"))
        self._entity_title_label.setText(tr("wizard.import.step2.entity_breakdown"))
        self._dup_title_label.setText(tr("wizard.import.step2.duplicates_title"))
        self._level_title_label.setText(tr("wizard.import.step2.level_results_title"))

        # Stat box labels — summary
        self._refresh_stat_label(self._stat_total,   tr("wizard.import.step2.total_records"))
        self._refresh_stat_label(self._stat_valid,   tr("wizard.import.step2.valid"))
        self._refresh_stat_label(self._stat_invalid, tr("wizard.import.step2.invalid"))
        self._refresh_stat_label(self._stat_warning, tr("wizard.import.step2.warnings"))
        self._refresh_stat_label(self._stat_skipped, tr("wizard.import.step2.skipped"))
        self._refresh_stat_label(self._stat_pending, tr("wizard.import.step2.pending"))

        # Stat box labels — duplicates
        self._refresh_stat_label(self._dup_persons,    tr("wizard.import.step2.dup_persons"))
        self._refresh_stat_label(self._dup_properties, tr("wizard.import.step2.dup_properties"))
        self._refresh_stat_label(self._dup_total,      tr("wizard.import.step2.dup_total"))

        # Duplicate warning text
        self._dup_warning_text.setText(tr("wizard.import.step2.dup_warning_text"))

        # Entity breakdown table headers
        self._entity_table.setHorizontalHeaderLabels([
            tr("wizard.import.step2.col_entity"),
            tr("wizard.import.step2.col_total"),
            tr("wizard.import.step2.col_valid"),
            tr("wizard.import.step2.col_invalid"),
            tr("wizard.import.step2.col_warning"),
            tr("wizard.import.step2.col_skipped"),
            tr("wizard.import.step2.col_pending"),
        ])
        self._entity_table.setLayoutDirection(get_layout_direction())

        # Entity row names
        entity_sections = _get_entity_sections()
        for row_idx, (key, ar_name) in enumerate(entity_sections):
            item = self._entity_table.item(row_idx, 0)
            if item:
                item.setText(ar_name)

        # Resolve duplicates button
        self._resolve_dups_btn.setText(tr("wizard.import.step2.resolve_duplicates"))

        # Loading label
        self._ld_label.setText(tr("wizard.import.step2.loading"))

        # Re-apply duplicate status text if report data loaded
        if self._report_data:
            self._update_duplicates()

    def get_report_data(self) -> dict:
        """Return the loaded report data."""
        return self._report_data or {}
