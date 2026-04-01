# -*- coding: utf-8 -*-
"""
Claim Detail Dialog — Modal overlay showing full claim details.
Navy header with frosted glass aesthetic, matching login page/navbar identity.
"""

import logging
from typing import Dict, Optional

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QGridLayout, QPushButton,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QApplication,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QPoint, QRect, QTimer,
)
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QPen, QBrush, QPaintEvent, QFont,
)

from ui.font_utils import create_font, FontManager
from ui.design_system import Colors, Typography
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import (
    get_claim_type_display, get_source_display,
    get_unit_type_display, get_claim_status_display,
)
from services.api_worker import ApiWorker
from ui.components.toast import Toast

logger = logging.getLogger(__name__)

_STATUS_STYLES = {
    "open":         {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74"},
    "draft":        {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74"},
    "submitted":    {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "under_review": {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "screening":    {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "awaiting_docs":{"bg": "#FFFBEB", "fg": "#92400E", "border": "#FCD34D"},
    "conflict":     {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
    "approved":     {"bg": "#F0FDF4", "fg": "#15803D", "border": "#86EFAC"},
    "closed":       {"bg": "#F0FDF4", "fg": "#15803D", "border": "#86EFAC"},
    "rejected":     {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
}


def _get_case_status_label(status):
    _keys = {1: "status.claim.open", 2: "status.claim.closed"}
    key = _keys.get(status)
    return tr(key) if key else str(status) if status else "-"


def _get_gender_label(gender):
    _map = {
        1: "page.claim_details.gender_male",
        2: "page.claim_details.gender_female",
        0: "page.claim_details.gender_unspecified",
    }
    key = _map.get(gender)
    return tr(key) if key else str(gender) if gender else "-"


class _DialogNavyHeader(QFrame):
    """Navy gradient header for the dialog with claim number and status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setStyleSheet("border: none; background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 16, 0)
        layout.setSpacing(12)

        self._claim_label = QLabel("")
        self._claim_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._claim_label.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(self._claim_label)

        layout.addStretch()

        self._status_badge = QLabel("")
        self._status_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._status_badge.setFixedHeight(26)
        self._status_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_badge)

        self._close_btn = QPushButton("\u2715")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(200, 220, 255, 180);
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.18);
                color: white;
            }
        """)
        layout.addWidget(self._close_btn)

    def set_data(self, claim_number: str, status_int: int):
        self._claim_label.setText(claim_number)
        status_str = "open" if status_int == 1 else "closed"
        text = _get_case_status_label(status_int)
        style = _STATUS_STYLES.get(status_str, _STATUS_STYLES["open"])
        self._status_badge.setText(f"  {text}  ")
        self._status_badge.setStyleSheet(f"""
            QLabel {{
                background: {style['bg']};
                color: {style['fg']};
                border: 1px solid {style['border']};
                border-radius: 13px;
                padding: 0px 12px;
            }}
        """)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#0D1B30"))
        grad.setColorAt(1.0, QColor("#1A3358"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 12, 12)
        # Square off bottom corners
        painter.fillRect(0, h - 12, w, 12, QBrush(grad))

        # Subtle grid
        painter.setPen(QPen(QColor(56, 144, 223, 12), 1))
        x = 40
        while x < w:
            painter.drawLine(x, 0, x, h)
            x += 40

        painter.end()
        super().paintEvent(event)


class ClaimDetailDialog(QDialog):
    """Modal dialog showing full claim details with navy header."""

    edit_requested = pyqtSignal(str)

    def __init__(self, claim_id: str, db=None, parent=None):
        super().__init__(parent)
        self._claim_id = claim_id
        self._db = db
        self._claim_data = {}
        self._person_data = {}
        self._unit_data = {}
        self._building_data = {}
        self._evidences = []
        self._case_status = 0

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        if parent:
            self.setFixedSize(parent.size())
        else:
            self.setFixedSize(1200, 800)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        direction = get_layout_direction()

        # Full overlay layout
        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(0, 0, 0, 0)

        # Center container
        center = QHBoxLayout()
        center.addStretch()
        card_col = QVBoxLayout()
        card_col.addStretch()

        # Card
        self._card = QFrame()
        self._card.setFixedWidth(680)
        self._card.setMaximumHeight(int(self.height() * 0.85))
        self._card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Navy header
        self._navy_header = _DialogNavyHeader()
        self._navy_header._close_btn.clicked.connect(self.close)
        card_layout.addWidget(self._navy_header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: white; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(direction)
        scroll_content.setStyleSheet("background: white;")
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(24, 20, 24, 20)
        self._content_layout.setSpacing(24)

        # Placeholder loading text
        self._loading_label = QLabel(tr("dialog.claim_detail.loading"))
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._loading_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(self._loading_label)
        self._content_layout.addStretch()

        scroll.setWidget(scroll_content)
        card_layout.addWidget(scroll, 1)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("""
            QFrame {
                background: #FAFBFC;
                border-top: 1px solid #E8EDF2;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 0, 24, 0)
        footer_layout.setSpacing(12)

        footer_layout.addStretch()

        self._close_btn = QPushButton(tr("dialog.claim_detail.btn_close"))
        self._close_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._close_btn.setFixedSize(120, 36)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet(StyleManager.button_secondary())
        self._close_btn.clicked.connect(self.close)
        footer_layout.addWidget(self._close_btn)

        self._edit_btn = QPushButton(tr("dialog.claim_detail.btn_edit"))
        self._edit_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._edit_btn.setFixedSize(120, 36)
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.setStyleSheet(StyleManager.button_primary())
        self._edit_btn.clicked.connect(self._on_edit)
        footer_layout.addWidget(self._edit_btn)

        card_layout.addWidget(footer)

        card_col.addWidget(self._card, 0, Qt.AlignCenter)
        card_col.addStretch()
        center.addLayout(card_col)
        center.addStretch()
        overlay_layout.addLayout(center)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()

    def _load_data(self):
        self._worker = ApiWorker(self._fetch_detail, self._claim_id)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_data_error)
        self._worker.start()

    def _fetch_detail(self, claim_id):
        from controllers.claim_controller import ClaimController
        controller = ClaimController(self._db)
        result = controller.get_claim_full_detail(claim_id)
        if result and result.success:
            return result.data
        return None

    def _on_data_loaded(self, data):
        if not data:
            self._loading_label.setText(tr("dialog.claim_detail.error_loading"))
            return

        self._claim_data = data.get("claim", {}) or {}
        self._person_data = data.get("person", {}) or {}
        self._unit_data = data.get("unit", {}) or {}
        self._building_data = data.get("building", {}) or {}
        self._evidences = data.get("evidences", []) or []
        self._case_status = self._claim_data.get("caseStatus", 0)

        relation = data.get("relation")
        self._ownership_share = relation if isinstance(relation, (int, float)) else None

        # Update header
        claim_number = (
            self._claim_data.get("claimNumber", "")
            or self._claim_data.get("claimId", "")
            or self._claim_id
        )
        self._navy_header.set_data(claim_number, self._case_status)

        # Show/hide edit button based on status
        self._edit_btn.setVisible(self._case_status == 1)

        self._populate_content()

    def _on_data_error(self, error_msg):
        self._loading_label.setText(tr("dialog.claim_detail.error_loading"))
        logger.warning(f"Error loading claim detail: {error_msg}")

    def _populate_content(self):
        # Clear loading text
        self._loading_label.hide()

        direction = get_layout_direction()
        no_data = tr("dialog.claim_detail.no_data")

        # Section 1: Claimant
        person = self._person_data
        claimant_name = (
            person.get("fullNameArabic")
            or person.get("fullNameEnglish")
            or self._claim_data.get("primaryClaimantName")
            or no_data
        )
        id_number = person.get("idNumber") or person.get("nationalId") or no_data
        gender = _get_gender_label(person.get("gender"))

        self._add_section(
            tr("dialog.claim_detail.section_claimant"),
            [
                (tr("dialog.claim_detail.field_name"), claimant_name),
                (tr("dialog.claim_detail.field_id_number"), id_number),
                (tr("dialog.claim_detail.field_gender"), gender),
            ],
        )

        # Section 2: Property Unit
        building = self._building_data
        unit = self._unit_data
        building_code = (
            building.get("buildingCode")
            or building.get("buildingNumber")
            or self._claim_data.get("buildingCode")
            or no_data
        )
        unit_code = (
            unit.get("unitNumber")
            or unit.get("propertyUnitCode")
            or self._claim_data.get("propertyUnitCode")
            or no_data
        )
        unit_type_raw = unit.get("unitType") or unit.get("propertyUnitType") or ""
        try:
            unit_type = get_unit_type_display(unit_type_raw) or unit_type_raw or no_data
        except Exception:
            unit_type = unit_type_raw or no_data

        self._add_section(
            tr("dialog.claim_detail.section_property"),
            [
                (tr("dialog.claim_detail.field_building"), building_code),
                (tr("dialog.claim_detail.field_unit"), unit_code),
                (tr("dialog.claim_detail.field_unit_type"), unit_type),
            ],
        )

        # Section 3: Relation & Evidence
        claim = self._claim_data
        claim_type_raw = claim.get("claimType") or ""
        try:
            claim_type_text = get_claim_type_display(claim_type_raw) or claim_type_raw or no_data
        except Exception:
            claim_type_text = claim_type_raw or no_data

        share_text = f"{self._ownership_share}%" if self._ownership_share is not None else no_data

        source_raw = claim.get("claimSource", 0)
        source_text = get_source_display(source_raw) if source_raw else no_data

        evidence_texts = []
        for ev in self._evidences:
            doc_type = ev.get("documentType") or ev.get("type") or ""
            evidence_texts.append(doc_type)
        evidence_str = " | ".join(evidence_texts) if evidence_texts else no_data

        fields = [
            (tr("dialog.claim_detail.field_claim_type"), claim_type_text),
            (tr("dialog.claim_detail.field_ownership_share"), share_text),
            (tr("dialog.claim_detail.field_source"), source_text),
            (tr("dialog.claim_detail.field_evidence"), evidence_str),
        ]

        date_str = claim.get("createdAtUtc") or claim.get("submissionDate") or ""
        if date_str and not date_str.startswith("0001"):
            fields.append((tr("dialog.claim_detail.field_date"), date_str[:10]))

        self._add_section(tr("dialog.claim_detail.section_relation"), fields)

        # Section 4: Notes (if any)
        notes = claim.get("notes") or claim.get("claimDescription") or ""
        resolution = claim.get("resolutionNotes") or claim.get("processingNotes") or ""
        if notes or resolution:
            note_fields = []
            if notes:
                note_fields.append((tr("dialog.claim_detail.field_notes"), notes))
            if resolution:
                note_fields.append((tr("dialog.claim_detail.field_resolution"), resolution))
            self._add_section(tr("dialog.claim_detail.section_notes"), note_fields)

        self._content_layout.addStretch()

    def _add_section(self, title: str, fields: list):
        # Section title with line
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: #1A3358; background: transparent;")
        title_row.addWidget(title_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background: #E8EDF2; border: none;")
        title_row.addWidget(line, 1)

        self._content_layout.addLayout(title_row)

        # Fields grid
        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(16)
        grid.setColumnStretch(1, 1)

        for row_idx, (label, value) in enumerate(fields):
            lbl = QLabel(label)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
            lbl.setAlignment(Qt.AlignTop)
            grid.addWidget(lbl, row_idx, 0)

            val = QLabel(str(value))
            val.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            val.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
            val.setWordWrap(True)
            grid.addWidget(val, row_idx, 1)

        self._content_layout.addLayout(grid)

    def _on_edit(self):
        self.edit_requested.emit(self._claim_id)
        self.close()

    def mousePressEvent(self, event):
        # Close if clicking the overlay (outside card)
        if event.button() == Qt.LeftButton:
            card_rect = self._card.geometry()
            # Map to dialog coordinates
            card_global = self._card.mapTo(self, QPoint(0, 0))
            full_rect = QRect(card_global, self._card.size())
            if not full_rect.contains(event.pos()):
                self.close()
        super().mousePressEvent(event)
