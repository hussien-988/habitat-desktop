# -*- coding: utf-8 -*-
"""Generic background worker for non-blocking API calls."""

from PyQt5.QtCore import QThread, pyqtSignal
from utils.logger import get_logger

logger = get_logger(__name__)


class ApiWorker(QThread):
    """Runs any callable in a background thread to avoid blocking the UI."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.warning(f"ApiWorker error: {e}")
            self.error.emit(str(e))
