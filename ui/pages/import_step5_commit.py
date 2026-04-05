# -*- coding: utf-8 -*-
"""Import wizard commit confirmation step."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger

logger = get_logger(__name__)

# Entity sections matching API response keys
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


class ImportStep5Commit(QWidget):
    """Step 4 (Commit): Confirmation view (display-only, orchestrator handles API calls)."""

    def __init__(self, import_controller, package_id, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id
        self._data = {}
        self._dots_count = 0
        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()
        self.load_summary(package_id)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Commit confirmation card
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
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(16)

        # Title
        title = QLabel(tr("wizard.import.step5.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Total count
        self._total_label = QLabel(tr("wizard.import.step5.total_entities", count=0))
        self._total_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._total_label.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(self._total_label)

        # Summary counts by entity type
        self._counts_layout = QVBoxLayout()
        self._counts_layout.setSpacing(8)

        self._count_labels = {}
        for key, ar_name in _get_entity_sections():
            row_frame = QFrame()
            row_frame.setFixedHeight(40)
            row_frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #FAFCFF, stop:1 transparent);
                    border-radius: 8px;
                    border: none;
                }
                QFrame QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(12, 4, 12, 4)
            row.setSpacing(12)

            name_label = QLabel(f"{ar_name}:")
            name_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
            name_label.setStyleSheet("color: #637381;")
            name_label.setFixedWidth(200)
            row.addWidget(name_label)

            count_label = QLabel("0")
            count_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
            count_label.setStyleSheet("color: #212B36;")
            row.addWidget(count_label)
            row.addStretch()

            self._count_labels[key] = count_label
            self._counts_layout.addWidget(row_frame)

        card_layout.addLayout(self._counts_layout)

        # Warning message
        warning_frame = QFrame()
        warning_frame.setStyleSheet("""
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
        warning_layout = QHBoxLayout(warning_frame)
        warning_layout.setContentsMargins(16, 12, 16, 12)
        warning_layout.setSpacing(10)

        warning_icon = QLabel("!")
        warning_icon.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        warning_icon.setFixedSize(28, 28)
        warning_icon.setAlignment(Qt.AlignCenter)
        warning_icon.setStyleSheet("""
            color: #F59E0B;
            background-color: #FEF3C7;
            border-radius: 14px;
        """)
        warning_layout.addWidget(warning_icon)

        warning_text = QLabel(tr("wizard.import.step5.irreversible_warning"))
        warning_text.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        warning_text.setStyleSheet("color: #92400E;")
        warning_layout.addWidget(warning_text)
        warning_layout.addStretch()

        card_layout.addWidget(warning_frame)

        # Progress bar (hidden initially, shown by orchestrator during commit)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E5E7EB;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4DA0EF, stop:0.5 #3890DF, stop:1 #2E7BD6);
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self._progress_bar)

        # Status label (hidden initially, shown during commit)
        self._status_label = QLabel("")
        self._status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._status_label.setStyleSheet("color: #637381; background: transparent;")
        self._status_label.setVisible(False)
        card_layout.addWidget(self._status_label)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def _create_loading_overlay(self):
        overlay = QWidget(self)
        overlay.setStyleSheet("background-color: rgba(255,255,255,200);")
        overlay.setVisible(False)

        ol = QVBoxLayout(overlay)
        ol.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(240, 90)
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

        self._ld_label = QLabel(tr("wizard.import.step5.loading"))
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
        self._ld_label.setText(msg or tr("wizard.import.step5.loading"))
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

    def load_summary(self, package_id: str, staged_data: dict = None):
        """Load commit summary from staged entities (grouped response)."""
        self._package_id = package_id

        if staged_data:
            self._data = staged_data
            self._update_counts()
            return

        self._show_loading(tr("wizard.import.step5.loading_summary"))

        result = self.import_controller.get_staged_entities(package_id)
        self._hide_loading()

        if result.success:
            self._data = result.data or {}
        else:
            self._data = {}
            logger.error(f"Failed to load entities for summary: {result.message}")
            from ui.components.message_dialog import MessageDialog
            MessageDialog.error(
                self, tr("wizard.import.step5.error"),
                result.message_ar or tr("wizard.import.step5.summary_load_failed")
            )

        self._update_counts()

    def _update_counts(self):
        """Update entity count labels from grouped data."""
        d = self._data
        total = d.get("totalCount", 0)
        self._total_label.setText(tr("wizard.import.step5.total_entities", count=total))

        for key, _ in _ENTITY_SECTION_KEYS:
            section_items = d.get(key, [])
            count = len(section_items) if isinstance(section_items, list) else 0
            if key in self._count_labels:
                self._count_labels[key].setText(str(count))

    def set_committing(self, committing: bool):
        """Toggle committing state (called by orchestrator)."""
        self._progress_bar.setVisible(committing)

        if committing:
            self._status_label.setText(tr("wizard.import.step5.committing"))
            self._status_label.setStyleSheet("color: #3890DF; background: transparent;")
            self._status_label.setVisible(True)
        else:
            self._status_label.setVisible(False)

    def reset(self):
        """Reset the step to initial state."""
        self._data = {}
        self._package_id = None
        self._total_label.setText(tr("wizard.import.step5.total_entities", count=0))
        self._progress_bar.setVisible(False)
        self._status_label.setText("")
        self._status_label.setVisible(False)
        for label in self._count_labels.values():
            label.setText("0")

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Total label
        total = self._data.get("totalCount", 0) if self._data else 0
        self._total_label.setText(tr("wizard.import.step5.total_entities", count=total))

        # Loading label
        self._ld_label.setText(tr("wizard.import.step5.loading"))

        # Re-populate entity name labels in counts section
        # (name labels are not stored as instance vars, so re-update counts)
        self._update_counts()
