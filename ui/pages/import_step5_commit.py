# -*- coding: utf-8 -*-
"""
Import Wizard - Step 5: Approve and Commit Confirmation
UC-003: Import Pipeline

Confirmation view before committing staged entities to production.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Entity type Arabic labels
_ENTITY_TYPE_AR = {
    'building': 'مبنى',
    'person': 'شخص',
    'property_unit': 'وحدة عقارية',
    'claim': 'مطالبة',
    'survey': 'مسح',
}


class ImportStep5Commit(QWidget):
    """Step 5: Approve and commit confirmation."""

    commit_completed = pyqtSignal(str)  # package_id
    commit_failed = pyqtSignal(str)  # error message

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._entities = []
        self._package_id = None
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Commit confirmation card
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
        title = QLabel("تأكيد الإدخال")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Summary counts
        self._counts_layout = QVBoxLayout()
        self._counts_layout.setSpacing(8)

        self._count_labels = {}
        for key, ar_name in _ENTITY_TYPE_AR.items():
            row = QHBoxLayout()
            row.setSpacing(12)

            name_label = QLabel(f"{ar_name}:")
            name_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
            name_label.setStyleSheet("color: #637381; background: transparent;")
            name_label.setFixedWidth(140)
            row.addWidget(name_label)

            count_label = QLabel("0")
            count_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
            count_label.setStyleSheet("color: #212B36; background: transparent;")
            row.addWidget(count_label)
            row.addStretch()

            self._count_labels[key] = count_label
            self._counts_layout.addLayout(row)

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

        warning_text = QLabel("هذا الإجراء نهائي ولا يمكن التراجع عنه")
        warning_text.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        warning_text.setStyleSheet("color: #92400E;")
        warning_layout.addWidget(warning_text)
        warning_layout.addStretch()

        card_layout.addWidget(warning_frame)

        # Progress bar (hidden initially)
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
                background-color: #10B981;
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._status_label.setStyleSheet("color: #637381; background: transparent;")
        self._status_label.setVisible(False)
        card_layout.addWidget(self._status_label)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def load_summary(self, package_id: str, entities: list = None):
        """Load commit summary from staged entities."""
        self._package_id = package_id

        if entities:
            self._entities = entities
        else:
            result = self.import_controller.get_staged_entities(package_id)
            if result.success:
                self._entities = result.data or []
            else:
                self._entities = []
                logger.error(f"Failed to load entities for summary: {result.message}")

        self._update_counts()

    def _update_counts(self):
        """Update entity count labels."""
        counts = {}
        for entity in self._entities:
            entity_type = entity.get("entityType", "unknown")
            counts[entity_type] = counts.get(entity_type, 0) + 1

        for key, label in self._count_labels.items():
            label.setText(str(counts.get(key, 0)))

    def start_commit(self, package_id: str = None):
        """Approve and then commit the package."""
        pkg_id = package_id or self._package_id
        if not pkg_id:
            logger.error("No package_id provided for commit")
            return

        self._set_committing(True)

        # Step 1: Approve
        approve_result = self.import_controller.approve_package(pkg_id)
        if not approve_result.success:
            self._set_committing(False)
            self._status_label.setText(approve_result.message_ar or "فشل الموافقة على الحزمة")
            self._status_label.setStyleSheet("color: #EF4444; background: transparent;")
            self._status_label.setVisible(True)
            self.commit_failed.emit(approve_result.message)
            return

        # Step 2: Commit
        self._status_label.setText("جاري إدخال البيانات...")
        self._status_label.setStyleSheet("color: #3890DF; background: transparent;")
        self._status_label.setVisible(True)

        commit_result = self.import_controller.commit_package(pkg_id)

        self._set_committing(False)

        if commit_result.success:
            self._status_label.setText(commit_result.message_ar or "تم إدخال البيانات بنجاح")
            self._status_label.setStyleSheet("color: #10B981; background: transparent;")
            self._status_label.setVisible(True)
            logger.info(f"Commit succeeded for package {pkg_id}")
            self.commit_completed.emit(pkg_id)
        else:
            self._status_label.setText(commit_result.message_ar or "فشل إدخال البيانات")
            self._status_label.setStyleSheet("color: #EF4444; background: transparent;")
            self._status_label.setVisible(True)
            logger.error(f"Commit failed: {commit_result.message}")
            self.commit_failed.emit(commit_result.message)

    def _set_committing(self, committing: bool):
        """Toggle committing state."""
        self._progress_bar.setVisible(committing)

        if committing:
            self._status_label.setText("جاري الموافقة والإدخال...")
            self._status_label.setStyleSheet("color: #3890DF; background: transparent;")
            self._status_label.setVisible(True)

    def reset(self):
        """Reset the step to initial state."""
        self._entities = []
        self._package_id = None
        self._progress_bar.setVisible(False)
        self._status_label.setText("")
        self._status_label.setVisible(False)
        for label in self._count_labels.values():
            label.setText("0")
