# -*- coding: utf-8 -*-
"""
Print Application Dialog — طباعة طلب تسجيل ادعاء

Lets the desk officer print the claim application with or without its
attachments, through the print preview (print or the Windows PDF printer)
or straight to a PDF file.
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
from services.api_worker import ApiWorker
from services.printing.application_renderer import configure_printer, render_application
from services.translation_manager import get_layout_direction, tr
from ui.components.dialogs.language_dialog import _LanguageOption
from ui.components.toast import Toast
from ui.design_system import Colors, ScreenScale
from ui.font_utils import FontManager, create_font
from utils.helpers import sanitize_filename
from utils.logger import get_logger

logger = get_logger(__name__)

_FORM_ONLY = "form"
_WITH_ATTACHMENTS = "attachments"


def open_print_dialog(context, parent=None) -> None:
    """Show the print dialog for the survey held by `context`."""
    PrintApplicationDialog(context, parent).exec_()


class PrintApplicationDialog(QDialog):
    """Choose with/without attachments, then preview-and-print or save a PDF."""

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._context = context
        self._controller = ApplicationPrintController(self)
        self._model = None
        self._attachment_pages = None
        self._worker = None
        self._choice = _FORM_ONLY
        self._closed = False

        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self.setMinimumWidth(ScreenScale.w(520))
        self._setup_ui()
        self._set_busy(True)
        self._run(self._controller.build_model, self._context, on_done=self._on_model_ready)

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

        title = QLabel(tr("print.dialog_title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        self._form_option = _LanguageOption(tr("print.option_form_only"), _FORM_ONLY, selected=True)
        self._attachments_option = _LanguageOption(tr("print.option_with_attachments"), _WITH_ATTACHMENTS)
        self._form_option.mousePressEvent = lambda e: self._select(_FORM_ONLY)
        self._attachments_option.mousePressEvent = lambda e: self._select(_WITH_ATTACHMENTS)
        layout.addWidget(self._form_option)
        layout.addWidget(self._attachments_option)

        self._counts = QLabel()
        self._counts.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self._counts.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 0 12px;")
        self._counts.hide()
        layout.addWidget(self._counts)

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
        self._form_option.selected = choice == _FORM_ONLY
        self._attachments_option.selected = choice == _WITH_ATTACHMENTS

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
        logger.warning(f"Application print failed: {message}")
        self._set_busy(False)
        Toast.show_toast(self.parentWidget() or self, tr("print.failed"), Toast.ERROR)
        if self._model is None:
            self.reject()

    def _on_model_ready(self, model):
        self._model = model
        self._counts.setText(tr(
            "print.option_counts", id_docs=model.id_documents_count, evidence=model.evidence_count,
        ))
        self._counts.show()
        self._set_busy(False)

    def _with_attachment_pages(self, then):
        """Run `then` once the attachment pages needed by the choice are ready."""
        if self._choice == _FORM_ONLY or self._attachment_pages is not None:
            then()
            return
        self._set_busy(True)

        def _ready(pages):
            self._attachment_pages = pages
            self._set_busy(False)
            then()

        self._run(self._controller.prepare_attachments, self._model, on_done=_ready)

    def _render(self, printer: QPrinter):
        render_application(printer, self._model, self._choice == _WITH_ATTACHMENTS,
                           self._attachment_pages)

    def _new_printer(self) -> QPrinter:
        printer = QPrinter(QPrinter.HighResolution)
        configure_printer(printer, self._file_stem())
        return printer

    def _file_stem(self) -> str:
        return sanitize_filename(self._model.reference_code or tr("print.title"))

    def _on_preview(self):
        def _show():
            # Keep the printer referenced: the preview only stores a raw pointer.
            self._printer = self._new_printer()
            preview = QPrintPreviewDialog(self._printer, self)
            preview.setWindowTitle(tr("print.dialog_title"))
            preview.paintRequested.connect(self._render)
            preview.exec_()
            self.accept()

        self._with_attachment_pages(_show)

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

        self._with_attachment_pages(_save)
