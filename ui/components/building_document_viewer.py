# -*- coding: utf-8 -*-
"""Shared helper to download and open a building document.

Building documents are served through an authenticated download endpoint
(GET /v1/building-documents/{id}/download), so the stored ``filePath`` is an
internal server path and cannot be opened directly. This centralises the
download-then-open behavior: "downloading" toast -> background download ->
open with the system app, or an error toast if the download/open fails.
"""

import os
import threading
from typing import Optional

from PyQt5.QtCore import QObject, Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget

from ui.components.toast import Toast
from services.translation_manager import tr
from utils.helpers import download_building_document_file
from utils.logger import get_logger

logger = get_logger(__name__)


class _BuildingDocOpener(QObject):
    """Per-call helper. Downloads on a worker thread, opens on the UI thread."""

    _completed = pyqtSignal(object)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent_widget = parent
        self._completed.connect(self._on_completed, Qt.QueuedConnection)

    def start(self, document_id: str, file_name: str) -> None:
        Toast.show_toast(
            self._parent_widget, tr("building_documents.downloading"), Toast.INFO
        )

        def _worker():
            try:
                local = download_building_document_file(document_id, file_name or document_id)
            except Exception as exc:
                logger.error(f"Building document download error for {document_id}: {exc}")
                local = None
            self._completed.emit(local)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_completed(self, local_path: Optional[str]) -> None:
        try:
            if not local_path or not os.path.exists(local_path):
                self._show_error()
                return
            try:
                os.startfile(local_path)
            except Exception as exc:
                logger.warning(f"os.startfile failed for {local_path}: {exc}")
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(local_path)):
                    self._show_error()
        finally:
            self.deleteLater()

    def _show_error(self) -> None:
        try:
            Toast.show_toast(
                self._parent_widget,
                tr("building_documents.cannot_open"),
                Toast.ERROR,
                duration=6000,
            )
        except Exception:
            pass


def download_and_open_building_document(
    parent: QWidget, document_id: str, file_name: str
) -> None:
    """Download a building document in the background and open it on success.

    Shows a "downloading" toast immediately and an error toast if the file
    cannot be downloaded or opened. Safe to call from the UI thread.
    """
    if not document_id:
        Toast.show_toast(
            parent, tr("building_documents.cannot_open"),
            Toast.ERROR, duration=6000,
        )
        return
    _BuildingDocOpener(parent).start(document_id, file_name)


def show_building_documents_dialog(parent: QWidget, docs: list) -> None:
    """Show a building's documents in a simple frameless dialog.

    Each row downloads and opens its document on click via the download
    endpoint (never the stored filePath). Mirrors the survey step dialog.
    """
    from PyQt5.QtWidgets import (
        QDialog, QScrollArea, QPushButton, QVBoxLayout, QHBoxLayout,
        QLabel, QFrame, QWidget as _QWidget,
    )
    from PyQt5.QtGui import QCursor
    from ui.design_system import Colors, ScreenScale
    from ui.font_utils import create_font, FontManager

    dlg = QDialog(parent)
    dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    dlg.setFixedSize(ScreenScale.w(500), ScreenScale.h(400))
    dlg.setStyleSheet("""
        QDialog {
            background-color: white;
            border: 1px solid #dcdfe6;
            border-radius: 12px;
        }
    """)

    main_lay = QVBoxLayout(dlg)
    main_lay.setContentsMargins(20, 16, 20, 16)
    main_lay.setSpacing(12)

    header = QHBoxLayout()
    title = QLabel(f"{tr('building_documents.dialog_title')} ({len(docs)})")
    title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
    title.setStyleSheet(f"color: {Colors.WIZARD_TITLE};")
    header.addWidget(title)
    header.addStretch()

    close_btn = QPushButton("X")
    close_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
    close_btn.setCursor(QCursor(Qt.PointingHandCursor))
    close_btn.setStyleSheet("""
        QPushButton {
            background: #f0f0f0; border: none; border-radius: 16px;
            font-size: 14px; font-weight: bold; color: #666;
        }
        QPushButton:hover { background: #e0e0e0; }
    """)
    close_btn.clicked.connect(dlg.close)
    header.addWidget(close_btn)
    main_lay.addLayout(header)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    container = _QWidget()
    container.setStyleSheet("background: transparent;")
    list_lay = QVBoxLayout(container)
    list_lay.setContentsMargins(0, 0, 0, 0)
    list_lay.setSpacing(8)

    for doc in docs:
        list_lay.addWidget(_make_doc_row(parent, doc))

    list_lay.addStretch()
    scroll.setWidget(container)
    main_lay.addWidget(scroll)

    dlg.exec_()


def _make_doc_row(parent: QWidget, doc: dict):
    """Create a clickable document row (type icon + name) for the dialog."""
    from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel
    from ui.design_system import ScreenScale
    from ui.font_utils import create_font, FontManager

    row = QFrame()
    row.setFixedHeight(ScreenScale.h(50))
    row.setStyleSheet("""
        QFrame {
            background-color: #F8FAFF;
            border: 1px solid #E1E8ED;
            border-radius: 8px;
        }
        QFrame:hover { border-color: #3890DF; background-color: #EBF5FF; }
    """)
    row.setCursor(Qt.PointingHandCursor)

    lay = QHBoxLayout(row)
    lay.setContentsMargins(12, 4, 12, 4)
    lay.setSpacing(10)

    mime_type = doc.get("mimeType", "") or doc.get("contentType", "") or ""
    display_name = (
        doc.get("originalFileName") or doc.get("fileName") or ""
    ).strip() or tr("building_documents.document_fallback")
    doc_id = doc.get("id") or doc.get("documentId") or ""

    is_image = mime_type.startswith("image/")
    icon_text = "IMG" if is_image else "PDF" if "pdf" in mime_type else "DOC"
    icon_bg = "#DBEAFE" if is_image else "#FEE2E2" if "pdf" in mime_type else "#E5E7EB"
    icon_fg = "#1D4ED8" if is_image else "#DC2626" if "pdf" in mime_type else "#374151"

    icon_lbl = QLabel(icon_text)
    icon_lbl.setFixedSize(ScreenScale.w(36), ScreenScale.h(36))
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
    icon_lbl.setStyleSheet(
        f"background: {icon_bg}; color: {icon_fg}; border-radius: 6px; border: none;"
    )
    lay.addWidget(icon_lbl)

    name_lbl = QLabel(display_name)
    name_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
    name_lbl.setStyleSheet("color: #303133; border: none; background: transparent;")
    lay.addWidget(name_lbl, stretch=1)

    row.mousePressEvent = lambda event, did=doc_id, fn=display_name: download_and_open_building_document(parent, did, fn)
    return row
