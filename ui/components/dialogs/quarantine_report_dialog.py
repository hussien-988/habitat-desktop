# -*- coding: utf-8 -*-
"""Quarantine Report Dialog.

Displays a structured diagnosis explaining why an import package is quarantined.
Backed by GET /api/v1/import/packages/{id}/quarantine-report.
"""

from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QWidget, QSizePolicy
)

from services.translation_manager import tr, get_layout_direction
from ui.design_system import ScreenScale
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


# Maps backend QuarantineCategory string → (title_key, action_key, accent_color)
_CATEGORY_META = {
    "ChecksumFailure": (
        "quarantine_dialog.cat.checksum",
        "quarantine_dialog.cat.checksum_action",
        "#EF4444",
    ),
    "SignatureFailure": (
        "quarantine_dialog.cat.signature",
        "quarantine_dialog.cat.signature_action",
        "#DC2626",
    ),
    "VocabularyVersionMismatch": (
        "quarantine_dialog.cat.vocab",
        "quarantine_dialog.cat.vocab_action",
        "#F59E0B",
    ),
    "SchemaInvalid": (
        "quarantine_dialog.cat.schema",
        "quarantine_dialog.cat.schema_action",
        "#8B5CF6",
    ),
    "ManualQuarantine": (
        "quarantine_dialog.cat.manual",
        "quarantine_dialog.cat.manual_action",
        "#6B7280",
    ),
}


class QuarantineReportDialog(QDialog):
    """Modal dialog showing the quarantine report for a single package."""

    def __init__(self, report: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._report = report or {}
        self._details_visible = False

        self.setWindowTitle(tr("quarantine_dialog.title"))
        self.setLayoutDirection(get_layout_direction())
        self.setModal(True)
        self.setMinimumSize(ScreenScale.w(560), ScreenScale.h(560))
        self.setStyleSheet("QDialog { background-color: #F9FAFB; }")

        self._setup_ui()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addWidget(self._build_header())
        root.addWidget(self._build_action_card())
        root.addWidget(self._build_checks_card())

        self._details_card = self._build_details_card()
        root.addWidget(self._details_card)
        self._details_card.setVisible(False)

        root.addStretch()
        root.addLayout(self._build_footer())

    def _build_header(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; }
            QFrame QLabel { background: transparent; border: none; }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        title = QLabel(tr("quarantine_dialog.title"))
        title.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #111827;")
        lay.addWidget(title)

        pkg_number = str(self._report.get("packageNumber") or "-")
        file_name = str(self._report.get("fileName") or "-")
        lay.addLayout(self._info_row(tr("quarantine_dialog.package_number"), pkg_number))
        lay.addLayout(self._info_row(tr("quarantine_dialog.file_name"), file_name))

        return card

    def _build_action_card(self) -> QFrame:
        category = str(self._report.get("quarantineCategory") or "")
        title_key, action_key, accent = _CATEGORY_META.get(
            category,
            ("quarantine_dialog.cat.unknown",
             "quarantine_dialog.cat.unknown_action",
             "#6B7280"),
        )

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #FFFFFF;
                border: 1px solid {accent}44;
                border-left: 4px solid {accent};
                border-radius: 10px;
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        cat_label_row = QHBoxLayout()
        cat_label_row.setSpacing(8)
        small = QLabel(tr("quarantine_dialog.category_label") + ":")
        small.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        small.setStyleSheet("color: #6B7280;")
        cat_label_row.addWidget(small)

        cat_value = QLabel(tr(title_key))
        cat_value.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        cat_value.setStyleSheet(f"color: {accent};")
        cat_label_row.addWidget(cat_value)
        cat_label_row.addStretch()
        lay.addLayout(cat_label_row)

        action_label = QLabel(tr("quarantine_dialog.action_label") + ":")
        action_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        action_label.setStyleSheet("color: #6B7280;")
        lay.addWidget(action_label)

        action_value = QLabel(tr(action_key))
        action_value.setFont(create_font(size=11, weight=FontManager.WEIGHT_MEDIUM))
        action_value.setStyleSheet("color: #111827;")
        action_value.setWordWrap(True)
        lay.addWidget(action_value)

        reason = self._report.get("quarantineReason")
        if reason:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background: #F3F4F6; border: none;")
            lay.addWidget(sep)

            reason_label = QLabel(tr("quarantine_dialog.reason_label") + ":")
            reason_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            reason_label.setStyleSheet("color: #6B7280;")
            lay.addWidget(reason_label)

            reason_value = QLabel(str(reason))
            reason_value.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
            reason_value.setStyleSheet("color: #374151;")
            reason_value.setWordWrap(True)
            lay.addWidget(reason_value)

        return card

    def _build_checks_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; }
            QFrame QLabel { background: transparent; border: none; }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        title = QLabel(tr("quarantine_dialog.checks_label"))
        title.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #111827;")
        lay.addWidget(title)

        for label_key, value_key in (
            ("quarantine_dialog.check_checksum", "isChecksumValid"),
            ("quarantine_dialog.check_signature", "isSignatureValid"),
            ("quarantine_dialog.check_vocabulary", "isVocabularyCompatible"),
            ("quarantine_dialog.check_schema", "isSchemaValid"),
        ):
            lay.addWidget(self._check_row(tr(label_key), self._report.get(value_key)))

        return card

    def _build_details_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; }
            QFrame QLabel { background: transparent; border: none; }
        """)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        # Wrap long error log in a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setMaximumHeight(ScreenScale.h(200))

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(6)

        schema_version = self._report.get("schemaVersion")
        if schema_version:
            content_lay.addLayout(
                self._info_row(tr("quarantine_dialog.schema_version"), str(schema_version))
            )

        vocab_issues = self._report.get("vocabularyCompatibilityIssues")
        if vocab_issues:
            content_lay.addWidget(
                self._labeled_block(
                    tr("quarantine_dialog.vocab_issues"), str(vocab_issues)
                )
            )

        error_log = self._report.get("errorLog")
        if error_log:
            content_lay.addWidget(
                self._labeled_block(
                    tr("quarantine_dialog.error_log"), str(error_log)
                )
            )

        content_lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return card

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        has_technical = any(
            self._report.get(k)
            for k in ("schemaVersion", "vocabularyCompatibilityIssues", "errorLog")
        )
        if has_technical:
            self._toggle_btn = QPushButton(tr("quarantine_dialog.show_details"))
            self._toggle_btn.setCursor(Qt.PointingHandCursor)
            self._toggle_btn.setFixedHeight(ScreenScale.h(36))
            self._toggle_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
            self._toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #F3F4F6; color: #374151;
                    border: 1px solid #E5E7EB; border-radius: 8px;
                    padding: 0 16px;
                }
                QPushButton:hover { background-color: #E5E7EB; }
            """)
            self._toggle_btn.clicked.connect(self._toggle_details)
            row.addWidget(self._toggle_btn)
        else:
            self._toggle_btn = None

        row.addStretch()

        close_btn = QPushButton(tr("quarantine_dialog.close"))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(ScreenScale.h(36))
        close_btn.setMinimumWidth(ScreenScale.w(100))
        close_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF; color: white;
                border: none; border-radius: 8px; padding: 0 20px;
            }
            QPushButton:hover { background-color: #2A7BC9; }
        """)
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        return row

    # ----------------------------------------------------------- helpers

    def _info_row(self, label: str, value: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel(label + ":")
        lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet("color: #6B7280;")
        lbl.setFixedWidth(ScreenScale.w(140))
        row.addWidget(lbl)

        val = QLabel(value)
        val.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        val.setStyleSheet("color: #111827;")
        val.setWordWrap(True)
        val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(val, 1)
        return row

    def _check_row(self, label: str, ok: Optional[bool]) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet("color: #374151;")
        row.addWidget(lbl)
        row.addStretch()

        is_ok = bool(ok)
        badge_text = ("✓ " + tr("quarantine_dialog.check_ok")) if is_ok else \
            ("✗ " + tr("quarantine_dialog.check_fail"))
        color = "#10B981" if is_ok else "#EF4444"
        bg = "#ECFDF5" if is_ok else "#FEF2F2"
        border = "#A7F3D0" if is_ok else "#FECACA"

        badge = QLabel(badge_text)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setStyleSheet(f"""
            color: {color};
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 10px;
            padding: 2px 10px;
        """)
        row.addWidget(badge)
        return wrap

    def _labeled_block(self, label: str, text: str) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)

        lbl = QLabel(label)
        lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet("color: #6B7280;")
        col.addWidget(lbl)

        val = QLabel(text)
        val.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        val.setStyleSheet("""
            color: #374151;
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 6px;
            padding: 6px 8px;
        """)
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(val)
        return wrap

    def _toggle_details(self):
        self._details_visible = not self._details_visible
        self._details_card.setVisible(self._details_visible)
        if self._toggle_btn:
            self._toggle_btn.setText(
                tr("quarantine_dialog.hide_details") if self._details_visible
                else tr("quarantine_dialog.show_details")
            )

    # ----------------------------------------------------------- API

    @classmethod
    def show_for(cls, report: Dict[str, Any], parent=None) -> None:
        """Convenience: build, show modally, and clean up."""
        dlg = cls(report, parent=parent)
        dlg.exec_()
