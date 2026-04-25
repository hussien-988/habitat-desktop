# -*- coding: utf-8 -*-
"""Shared helper to download and open an evidence document.

Centralises the download-then-open behavior used by claim details, the
evidence picker dialog and the person dialog so they share the same UX:
"downloading" toast → background download → open with system app, or an
error toast if the download/open fails.
"""

import os
import threading
from typing import Optional

from PyQt5.QtCore import QObject, Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget

from ui.components.toast import Toast
from services.translation_manager import tr
from utils.helpers import download_evidence_file
from utils.logger import get_logger

logger = get_logger(__name__)


class _EvidenceOpener(QObject):
    """Per-call helper. Downloads on a worker thread, opens on the UI thread."""

    _completed = pyqtSignal(object)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent_widget = parent
        self._completed.connect(self._on_completed, Qt.QueuedConnection)

    def start(self, evidence_id: str, file_name: str) -> None:
        Toast.show_toast(
            self._parent_widget, tr("page.claim_details.downloading"), Toast.INFO
        )

        def _worker():
            try:
                local = download_evidence_file(evidence_id, file_name or evidence_id)
            except Exception as exc:
                logger.error(f"Evidence download error for {evidence_id}: {exc}")
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
                tr("page.claim_details.cannot_download"),
                Toast.ERROR,
                duration=6000,
            )
        except Exception:
            pass


def download_and_open_evidence(
    parent: QWidget, evidence_id: str, file_name: str
) -> None:
    """Download an evidence file in the background and open it on success.

    Shows a "downloading" toast immediately and an error toast if the file
    cannot be downloaded or opened. Safe to call from the UI thread.
    """
    if not evidence_id:
        Toast.show_toast(
            parent, tr("page.claim_details.cannot_download"),
            Toast.ERROR, duration=6000,
        )
        return
    _EvidenceOpener(parent).start(evidence_id, file_name)
