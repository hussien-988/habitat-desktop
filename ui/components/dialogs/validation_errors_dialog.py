# -*- coding: utf-8 -*-
"""Validation Errors Dialog — why a package failed validation, record by record."""

from typing import Any, Dict, List

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSizePolicy, QGraphicsDropShadowEffect, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)

from services.api_worker import ApiWorker
from services.import_error_messages import (
    entity_label, parse_import_messages, translate_import_error,
)
from services.translation_manager import tr, get_layout_direction
from ui.components.toast import Toast
from ui.design_system import ScreenScale, Colors
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)

# staged-entities groups (response key, entity type), in display order
_GROUPS = (
    ("surveys", "Survey"),
    ("buildings", "Building"),
    ("propertyUnits", "PropertyUnit"),
    ("persons", "Person"),
    ("households", "Household"),
    ("personPropertyRelations", "PersonPropertyRelation"),
    ("evidences", "Evidence"),
    ("claims", "Claim"),
)

# LTR embedding keeps codes / national IDs / "1-3" in order inside RTL text
_LTR = "‪{}‬"

# Workers outlive a dialog closed mid-load; keep them referenced until they finish
_ACTIVE_WORKERS: List[ApiWorker] = []


def _release_worker(worker: ApiWorker) -> None:
    if worker in _ACTIVE_WORKERS:
        _ACTIVE_WORKERS.remove(worker)


def _display_identifier(entity_type: str, e: Dict[str, Any]) -> str:
    """Something the user recognises; internal ids / enum names are left out."""
    raw = str(e.get("identifier") or "").strip()
    ident = raw if raw and raw != "N/A" else ""
    if entity_type == "Person":
        name = str(e.get("displayInfo") or "").strip()
        parts = [name] if name else []
        if ident:
            parts.append(_LTR.format(ident))
        return " · ".join(parts) or "—"
    if entity_type == "PropertyUnit":
        return tr("validation_errors_dialog.unit", unit=_LTR.format(ident)) if ident else "—"
    if entity_type in ("Survey", "Building", "Evidence"):
        return _LTR.format(ident) if ident else "—"
    return "—"


def build_error_rows(staged: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Records with blocking validation errors (warnings are not shown)."""
    rows = []
    for key, entity_type in _GROUPS:
        for e in (staged or {}).get(key) or []:
            raw = parse_import_messages(e.get("validationErrors"))
            if not raw:
                continue
            rows.append({
                "entity_type": entity_type,
                "identifier": _display_identifier(entity_type, e),
                "raw": raw,
                "raw_identifier": " | ".join(
                    str(v) for v in (e.get("identifier"), e.get("displayInfo"), e.get("originalEntityId")) if v
                ),
            })
    return rows


class ValidationErrorsDialog(QDialog):
    """Record type + identifier + translated reason, with a copy-for-support action."""

    def __init__(self, package_id: str, import_controller, package_number: str = "", parent=None):
        super().__init__(parent)
        self._package_id = package_id
        self._package_number = package_number or package_id
        self._import_controller = import_controller
        self._rows: List[Dict[str, Any]] = []
        self._state = "loading"  # loading | failed | ready
        self._worker = None

        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.CustomizeWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(True)
        self.setLayoutDirection(get_layout_direction())

        self._setup_ui()
        self._populate_values()
        self._center_on_parent()
        self._animate_in()
        self._load()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(24),
            ScreenScale.w(24), ScreenScale.h(24),
        )

        self._card = QFrame()
        self._card.setObjectName("ValidationErrorsCard")
        self._card.setStyleSheet(
            "QFrame#ValidationErrorsCard {"
            " background-color: #FFFFFF;"
            " border: 1px solid #E1E8ED;"
            " border-radius: 12px;"
            "}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 60))
        self._card.setGraphicsEffect(shadow)
        self._card.setMinimumWidth(ScreenScale.w(640))
        self._card.setMaximumWidth(ScreenScale.w(900))

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(22),
            ScreenScale.w(24), ScreenScale.h(22),
        )
        card_layout.setSpacing(ScreenScale.h(12))

        self._title_lbl = QLabel()
        self._title_lbl.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._title_lbl.setStyleSheet("color: #111827; background: transparent;")
        card_layout.addWidget(self._title_lbl)

        self._summary_lbl = QLabel()
        self._summary_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._summary_lbl.setStyleSheet(
            "color: #991B1B; background: #FEF2F2;"
            " border: 1px solid #FECACA; border-radius: 8px; padding: 8px 12px;"
        )
        card_layout.addWidget(self._summary_lbl)

        self._status_lbl = QLabel()
        self._status_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._status_lbl.setWordWrap(True)
        card_layout.addWidget(self._status_lbl)

        self._table = QTableWidget(0, 3)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setWordWrap(True)
        self._table.setTextElideMode(Qt.ElideNone)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        # Rows follow their wrapped reasons whatever the final column widths are
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.setStyleSheet(
            "QTableWidget { border: 1px solid #E2E8F0; border-radius: 8px; background: #FFFFFF; }"
            "QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #F1F5F9; color: #1F2937; }"
            "QHeaderView::section { background: #F8FAFC; color: #475569; border: none;"
            " border-bottom: 1px solid #E2E8F0; padding: 8px; }"
        )
        self._table.setMinimumHeight(ScreenScale.h(220))
        self._table.setMaximumHeight(ScreenScale.h(440))
        card_layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, ScreenScale.h(4), 0, 0)
        self._copy_btn = QPushButton()
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._copy_btn.setMinimumHeight(ScreenScale.h(36))
        self._copy_btn.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1;"
            " border-radius: 8px; padding: 0 16px; }"
            "QPushButton:hover { background: #F8FAFC; }"
        )
        self._copy_btn.clicked.connect(self._copy_for_support)
        btn_row.addWidget(self._copy_btn)
        btn_row.addStretch()

        self._close_btn = QPushButton()
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._close_btn.setMinimumHeight(ScreenScale.h(36))
        self._close_btn.setMinimumWidth(ScreenScale.w(110))
        self._close_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._close_btn.setStyleSheet(
            "QPushButton {"
            f" background-color: {Colors.PRIMARY_BLUE};"
            " color: white;"
            " border: none;"
            " border-radius: 8px;"
            " padding: 0 22px;"
            "}"
            "QPushButton:hover { background-color: #2D7BC9; }"
            "QPushButton:pressed { background-color: #1F66A8; }"
        )
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        card_layout.addLayout(btn_row)

        outer.addWidget(self._card, alignment=Qt.AlignCenter)

    # -- data ---------------------------------------------------------------

    def _load(self):
        worker = ApiWorker(self._import_controller.get_staged_entities, self._package_id)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._on_load_error)
        _ACTIVE_WORKERS.append(worker)
        worker.finished.connect(lambda *_: _release_worker(worker))
        worker.error.connect(lambda *_: _release_worker(worker))
        self._worker = worker
        worker.start()

    def done(self, result):
        # Closed while loading: the reply must not reach a deleted dialog
        if self._worker is not None:
            for signal, slot in ((self._worker.finished, self._on_loaded),
                                 (self._worker.error, self._on_load_error)):
                try:
                    signal.disconnect(slot)
                except TypeError:
                    pass
        super().done(result)

    def _on_loaded(self, result):
        if not getattr(result, "success", False):
            self._on_load_error(getattr(result, "message", ""))
            return
        self._rows = build_error_rows(result.data or {})
        self._state = "ready"
        self._populate_values()

    def _on_load_error(self, message: str = ""):
        logger.warning(f"Validation errors for package {self._package_id} not loaded: {message}")
        self._state = "failed"
        self._populate_values()

    # -- view ---------------------------------------------------------------

    def _populate_values(self):
        self._title_lbl.setText(tr("validation_errors_dialog.title"))
        self._copy_btn.setText(tr("import_errors.copy_for_support"))
        self._close_btn.setText(tr("quarantine_dialog.close"))
        self._table.setHorizontalHeaderLabels([
            tr("validation_errors_dialog.col_type"),
            tr("validation_errors_dialog.col_identifier"),
            tr("validation_errors_dialog.col_reason"),
        ])

        ready_with_rows = self._state == "ready" and bool(self._rows)
        self._summary_lbl.setVisible(ready_with_rows)
        self._table.setVisible(ready_with_rows)
        self._copy_btn.setVisible(ready_with_rows)
        self._status_lbl.setVisible(not ready_with_rows)

        if self._state == "loading":
            self._set_status(tr("validation_errors_dialog.loading"), "#64748B")
        elif self._state == "failed":
            self._set_status(tr("validation_errors_dialog.load_failed"), "#991B1B")
        elif not self._rows:
            self._set_status(tr("validation_errors_dialog.empty"), "#64748B")
        else:
            self._summary_lbl.setText(tr("validation_errors_dialog.summary", count=len(self._rows)))
            self._fill_table()

        self._copy_btn.adjustSize()
        self._close_btn.adjustSize()
        self.adjustSize()

    def _set_status(self, text: str, color: str):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"color: {color}; background: transparent;")

    def _fill_table(self):
        self._table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            # Same reason twice on one record (e.g. two validators) reads as one line
            reasons = list(dict.fromkeys(translate_import_error(m) for m in row["raw"]))
            cells = (entity_label(row["entity_type"]), row["identifier"], "\n".join(reasons))
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignLeading | Qt.AlignVCenter)
                self._table.setItem(i, col, item)
        self._table.resizeRowsToContents()

    def _copy_for_support(self):
        """Raw (technical) details to paste to support — not shown on screen."""
        lines = [f"Package {self._package_number} — validation errors"]
        for row in self._rows:
            for msg in row["raw"]:
                lines.append(f"{row['entity_type']} | {row['raw_identifier']} | {msg}")
        QApplication.clipboard().setText("\n".join(lines))
        Toast.show_toast(self, tr("import_errors.copied"), Toast.SUCCESS)

    def update_language(self, is_arabic: bool = True):
        self.setLayoutDirection(get_layout_direction())
        self._populate_values()

    def _center_on_parent(self):
        parent = self.parent()
        if not parent:
            return
        main_window = parent.window() if hasattr(parent, "window") else parent
        self.adjustSize()
        rect = main_window.geometry()
        cx = rect.x() + (rect.width() - self.width()) // 2
        cy = rect.y() + (rect.height() - self.height()) // 2
        self.move(cx, cy)

    def _animate_in(self):
        try:
            self.setWindowOpacity(0.0)
            self._anim = QPropertyAnimation(self, b"windowOpacity")
            self._anim.setDuration(160)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._center_on_parent()

    @classmethod
    def show_for(cls, package_id: str, import_controller, package_number: str = "", parent=None) -> None:
        dlg = cls(package_id, import_controller, package_number=package_number, parent=parent)
        dlg.exec_()
