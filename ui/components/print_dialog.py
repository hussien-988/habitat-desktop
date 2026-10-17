# -*- coding: utf-8 -*-
"""
Print Dialog — طباعة

One dialog for every printed document: pick the basic or the full version
(claim application with/without attachments, case report with/without claim
details), then print through the print preview (printer or the Windows PDF
printer) or save straight to a PDF file. What is printed comes from a job.
"""

import os

from PyQt5.QtCore import QStandardPaths, Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt5.QtWidgets import (
    QDialog, QFileDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout,
)

from controllers.application_print_controller import ApplicationPrintController
from controllers.case_print_controller import CasePrintController
from services.api_worker import ApiWorker
from services.printing.application_renderer import configure_printer, render_application, render_document
from services.printing.case_html import build_case_html
from services.translation_manager import get_layout_direction, tr
from ui.components.dialogs.language_dialog import _LanguageOption
from ui.components.toast import Toast
from ui.design_system import Colors, ScreenScale
from ui.font_utils import FontManager, create_font
from utils.helpers import sanitize_filename
from utils.logger import get_logger

logger = get_logger(__name__)

_BASIC = "basic"
_FULL = "full"


def open_print_dialog(context, parent=None) -> None:
    """Show the print dialog for the claim application of the survey in `context`."""
    PrintDialog(ApplicationPrintJob(context), parent).exec_()


def open_case_print_dialog(case_data: dict, parent=None) -> None:
    """Show the print dialog for a case report (see CasePrintJob for `case_data`)."""
    PrintDialog(CasePrintJob(case_data), parent).exec_()


class ApplicationPrintJob:
    """Claim application, with or without its attachments."""
    title_key = "print.dialog_title"
    basic_key = "print.option_form_only"
    full_key = "print.option_with_attachments"

    def __init__(self, context):
        self._context = context
        self._controller = ApplicationPrintController()
        self.model = None

    def load(self):
        return self._controller.build_model(self._context)

    def load_full(self):
        return self._controller.prepare_attachments(self.model)

    def summary(self) -> str:
        return tr("print.option_counts", id_docs=self.model.id_documents_count,
                  evidence=self.model.evidence_count)

    def file_stem(self) -> str:
        return self.model.reference_code or tr("print.title")

    def render(self, printer: QPrinter, full: bool, full_data) -> None:
        render_application(printer, self.model, full, full_data)


class CasePrintJob:
    """Case report, with or without the details of its claims.

    `case_data` holds the case page's data: case_number, status, case_rows,
    property_rows, surveys, claims (API dicts) and notes.
    """
    title_key = "print.case.dialog_title"
    basic_key = "print.case.option_case_only"
    full_key = "print.case.option_with_claims"

    def __init__(self, case_data: dict):
        self._case_data = case_data
        self._controller = CasePrintController()
        self.model = None

    def load(self):
        return self._controller.build_model(**self._case_data)

    def load_full(self):
        return self._controller.load_claim_details(self.model)

    def summary(self) -> str:
        return ""

    def file_stem(self) -> str:
        return self.model.case_number or tr("print.case.title")

    def render(self, printer: QPrinter, full: bool, full_data) -> None:
        render_document(printer, build_case_html(self.model, full_data if full else None), self.model.rtl)


class PrintDialog(QDialog):
    """Choose the basic or full version, then preview-and-print or save a PDF."""

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job
        self._full_data = None
        self._worker = None
        self._choice = _BASIC
        self._closed = False

        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self.setMinimumWidth(ScreenScale.w(520))
        self._setup_ui()
        self._set_busy(True)
        self._run(self._job.load, on_done=self._on_model_ready)

    # -- UI --

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("printContainer")
        container.setStyleSheet("""
            QFrame#printContainer { background-color: #FFFFFF; border-radius: 24px; }
            QFrame#printContainer QLabel { background-color: transparent; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel(tr(self._job.title_key))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        self._basic_option = _LanguageOption(tr(self._job.basic_key), _BASIC, selected=True)
        self._full_option = _LanguageOption(tr(self._job.full_key), _FULL)
        self._basic_option.mousePressEvent = lambda e: self._select(_BASIC)
        self._full_option.mousePressEvent = lambda e: self._select(_FULL)
        layout.addWidget(self._basic_option)
        layout.addWidget(self._full_option)

        self._summary = QLabel()
        self._summary.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._summary.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 0 12px;")
        self._summary.hide()
        layout.addWidget(self._summary)

        self._status = QLabel(tr("print.preparing"))
        self._status.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self._status)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()
        self._cancel_btn = self._create_button(tr("button.cancel"), primary=False)
        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn = self._create_button(tr("print.save_pdf"), primary=False)
        self._save_btn.clicked.connect(self._on_save_pdf)
        self._preview_btn = self._create_button(tr("print.preview"), primary=True)
        self._preview_btn.clicked.connect(self._on_preview)
        for btn in (self._cancel_btn, self._save_btn, self._preview_btn):
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        outer.addWidget(container)

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(ScreenScale.w(150), ScreenScale.h(46))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=QFont.Medium))
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {Colors.PRIMARY_BLUE}; color: white;
                               border: none; border-radius: 8px; }}
                QPushButton:hover {{ background-color: #2D7BC9; }}
                QPushButton:pressed {{ background-color: #2468B0; }}
                QPushButton:disabled {{ background-color: #A9C9EC; }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background-color: white; color: #6B7280;
                              border: 1px solid #E5E7EB; border-radius: 8px; }
                QPushButton:hover { background-color: #F9FAFB; }
                QPushButton:disabled { color: #C0C8D0; }
            """)
        return btn

    def _select(self, choice: str):
        if not self._preview_btn.isEnabled():
            return
        self._choice = choice
        self._basic_option.selected = choice == _BASIC
        self._full_option.selected = choice == _FULL

    def _set_busy(self, busy: bool):
        for btn in (self._save_btn, self._preview_btn):
            btn.setEnabled(not busy)
        self._status.setVisible(busy)

    # -- Flow --

    def _run(self, func, *args, on_done):
        self._worker = ApiWorker(func, *args)
        self._worker.finished.connect(lambda result: self._on_result(result, on_done))
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def done(self, result_code: int):
        self._closed = True  # late worker results are ignored
        super().done(result_code)

    def _on_result(self, result, on_done):
        if self._closed:
            return
        if not result or not result.success:
            self._on_error(result.message_ar if result else "")
            return
        on_done(result.data)

    def _on_error(self, message: str):
        if self._closed:
            return
        logger.warning(f"Print failed: {message}")
        self._set_busy(False)
        Toast.show_toast(self.parentWidget() or self, tr("print.failed"), Toast.ERROR)
        if self._job.model is None:
            self.reject()

    def _on_model_ready(self, model):
        self._job.model = model
        summary = self._job.summary()
        if summary:
            self._summary.setText(summary)
            self._summary.show()
        self._set_busy(False)

    def _with_full_data(self, then):
        """Run `then` once the data needed by the full version is ready."""
        if self._choice == _BASIC or self._full_data is not None:
            then()
            return
        self._set_busy(True)

        def _ready(data):
            self._full_data = data
            self._set_busy(False)
            then()

        self._run(self._job.load_full, on_done=_ready)

    def _render(self, printer: QPrinter):
        self._job.render(printer, self._choice == _FULL, self._full_data)

    def _new_printer(self) -> QPrinter:
        printer = QPrinter(QPrinter.HighResolution)
        configure_printer(printer, self._file_stem())
        return printer

    def _file_stem(self) -> str:
        return sanitize_filename(self._job.file_stem())

    def _on_preview(self):
        def _show():
            # Keep the printer referenced: the preview only stores a raw pointer.
            self._printer = self._new_printer()
            preview = QPrintPreviewDialog(self._printer, self)
            preview.setWindowTitle(tr(self._job.title_key))
            preview.paintRequested.connect(self._render)
            preview.exec_()
            self.accept()

        self._with_full_data(_show)

    def _on_save_pdf(self):
        folder = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        path, _ = QFileDialog.getSaveFileName(
            self, tr("print.save_pdf"), os.path.join(folder, f"{self._file_stem()}.pdf"), "PDF (*.pdf)",
        )
        if not path:
            return

        def _save():
            printer = self._new_printer()
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            try:
                self._render(printer)
            except Exception as e:
                self._on_error(str(e))
                return
            Toast.show_toast(self.parentWidget() or self, tr("print.saved"), Toast.SUCCESS)
            self.accept()

        self._with_full_data(_save)
