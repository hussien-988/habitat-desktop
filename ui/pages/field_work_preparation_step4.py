# -*- coding: utf-8 -*-
"""Field work preparation step 4: completion confirmation and transfer status."""

from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton
)
from PyQt5.QtCore import Qt, QTimer

from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Transfer status display configuration
_STATUS_CONFIG = {
    'not_transferred': {
        'label': 'في الانتظار',
        'color': '#9CA3AF',
        'bg': '#F3F4F6',
    },
    'transferring': {
        'label': 'قيد المزامنة',
        'color': '#3890DF',
        'bg': '#EBF5FF',
    },
    'transferred': {
        'label': 'تمت المزامنة',
        'color': '#10B981',
        'bg': '#ECFDF5',
    },
    'failed': {
        'label': 'فشلت المزامنة',
        'color': '#EF4444',
        'bg': '#FEF2F2',
    },
}


class FieldWorkPreparationStep4(QWidget):
    """Completion confirmation with transfer status monitoring."""

    def __init__(self, buildings: list, researcher_name: str,
                 assignment_ids: list, db=None, parent=None):
        super().__init__(parent)
        self.buildings = buildings or []
        self.researcher_name = researcher_name
        self.assignment_ids = assignment_ids or []
        self.db = db
        self._status_rows = {}  # assignment_id → (badge_label, retry_btn)

        self._setup_ui()
        self._load_transfer_status()

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._load_transfer_status)
        self._refresh_timer.start(10000)

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(20)

        # Success header card
        success_card = QFrame()
        success_card.setStyleSheet("""
            QFrame {
                background-color: #ECFDF5;
                border-radius: 16px;
                border: 1px solid #A7F3D0;
            }
        """)
        success_layout = QVBoxLayout(success_card)
        success_layout.setContentsMargins(32, 24, 32, 24)
        success_layout.setSpacing(8)

        success_title = QLabel("تم إنشاء التعيين بنجاح")
        success_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        success_title.setStyleSheet("color: #065F46; background: transparent;")
        success_layout.addWidget(success_title)

        summary_text = f"تم إسناد {len(self.buildings)} مبنى إلى {self.researcher_name}"
        summary_label = QLabel(summary_text)
        summary_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        summary_label.setStyleSheet("color: #047857; background: transparent;")
        success_layout.addWidget(summary_label)

        date_label = QLabel(date.today().strftime("%Y-%m-%d"))
        date_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        date_label.setStyleSheet("color: #6EE7B7; background: transparent;")
        success_layout.addWidget(date_label)

        layout.addWidget(success_card)

        # Transfer status card
        status_card = QFrame()
        status_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        status_card_layout = QVBoxLayout(status_card)
        status_card_layout.setContentsMargins(24, 16, 24, 16)
        status_card_layout.setSpacing(8)

        status_title = QLabel("حالة النقل")
        status_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        status_title.setStyleSheet("color: #212B36; background: transparent;")
        status_card_layout.addWidget(status_title)

        # Scroll area for building status rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setMaximumHeight(350)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(scroll_content)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)

        # Create a row per building/assignment
        for i, building in enumerate(self.buildings):
            building_id = (
                getattr(building, 'building_id', None)
                or getattr(building, 'id', None)
                or str(building)
            )
            display_id = getattr(building, 'building_id_display', building_id) or building_id
            assignment_id = self.assignment_ids[i] if i < len(self.assignment_ids) else None

            row = self._create_status_row(display_id, assignment_id)
            self._rows_layout.addWidget(row)

        self._rows_layout.addStretch()
        scroll.setWidget(scroll_content)
        status_card_layout.addWidget(scroll)
        layout.addWidget(status_card)

        layout.addStretch()

    def _create_status_row(self, display_id: str, assignment_id: str) -> QFrame:
        """Create a transfer status row for a building."""
        row = QFrame()
        row.setFixedHeight(48)
        row.setStyleSheet("""
            QFrame {
                background-color: white;
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

        # Building ID
        id_label = QLabel(display_id)
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        id_label.setStyleSheet("color: #212B36;")
        row_layout.addWidget(id_label)

        row_layout.addStretch()

        # Status badge
        badge = QLabel("في الانتظار")
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(26)
        badge.setMinimumWidth(90)
        badge.setStyleSheet("""
            padding: 2px 12px;
            border-radius: 13px;
            color: #9CA3AF;
            background-color: #F3F4F6;
        """)
        row_layout.addWidget(badge)

        # Retry button (hidden by default)
        retry_btn = QPushButton("إعادة المحاولة")
        retry_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        retry_btn.setFixedSize(110, 28)
        retry_btn.setCursor(Qt.PointingHandCursor)
        retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                color: #EF4444;
                border: 1px solid #FECACA;
                border-radius: 6px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
            }
        """)
        retry_btn.setVisible(False)
        if assignment_id:
            retry_btn.clicked.connect(lambda _, aid=assignment_id: self._on_retry(aid))
        row_layout.addWidget(retry_btn)

        if assignment_id:
            self._status_rows[assignment_id] = (badge, retry_btn)

        return row

    def _load_transfer_status(self):
        """Load transfer status from API, fallback to local DB."""
        if not self.assignment_ids:
            return

        try:
            from services.api_client import get_api_client
            api = get_api_client()

            # Check for timed-out transfers
            try:
                api.check_transfer_timeout()
            except Exception:
                pass

            for assignment_id in self.assignment_ids:
                try:
                    assignment = api.get_assignment(assignment_id)
                except Exception:
                    assignment = None

                if not assignment:
                    # Fallback to local DB
                    if self.db:
                        try:
                            from services.assignment_service import AssignmentService
                            svc = AssignmentService(db=self.db)
                            local = svc.get_assignment(assignment_id)
                            if local:
                                assignment = {
                                    "transferStatus": local.transfer_status or "not_transferred"
                                }
                        except Exception:
                            pass
                    if not assignment:
                        continue

                status = assignment.get("transferStatus") or "not_transferred"
                config = _STATUS_CONFIG.get(status, _STATUS_CONFIG['not_transferred'])

                if assignment_id in self._status_rows:
                    badge, retry_btn = self._status_rows[assignment_id]
                    badge.setText(config['label'])
                    badge.setStyleSheet(f"""
                        padding: 2px 12px;
                        border-radius: 13px;
                        color: {config['color']};
                        background-color: {config['bg']};
                    """)
                    retry_btn.setVisible(status == 'failed')

        except Exception as e:
            logger.warning(f"Could not load transfer status: {e}")

    def _on_retry(self, assignment_id: str):
        """Retry a failed transfer via API."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            api.retry_transfer([assignment_id])
            logger.info(f"Retried transfer for assignment {assignment_id}")
            self._load_transfer_status()
        except Exception as e:
            logger.warning(f"API retry failed for {assignment_id}: {e}")
            # Fallback to local DB
            if self.db:
                try:
                    from services.assignment_service import AssignmentService
                    svc = AssignmentService(db=self.db)
                    svc.retry_transfer(assignment_id)
                    self._load_transfer_status()
                except Exception as fallback_err:
                    logger.warning(f"Local retry also failed: {fallback_err}")

    def stop_refresh(self):
        """Stop the auto-refresh timer."""
        if self._refresh_timer.isActive():
            self._refresh_timer.stop()
