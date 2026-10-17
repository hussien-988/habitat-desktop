# -*- coding: utf-8 -*-
"""
Paint a claim application onto a QPrinter (print preview, printer or PDF).

The form is laid out by QTextDocument at 96 dpi and painted page by page with
the painter scaled to the printer resolution (the same approach as
QTextDocument.print), followed by one page per attachment. Every page gets a
"page X of N" footer and, for drafts, a diagonal draft watermark.
"""

import io
from dataclasses import dataclass
from typing import List, Optional

from PyQt5.QtCore import QRectF, QSizeF, Qt, QUrl
from PyQt5.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QImageReader, QPageLayout, QPageSize,
    QPainter, QTextDocument, QTextOption,
)
from PyQt5.QtPrintSupport import QPrinter

from app.config import Config
from services.printing.application_html import LOGO_RESOURCE, TITLE_COLOR, build_application_html
from services.printing.application_print_model import ApplicationPrintModel
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)

_LAYOUT_DPI = 96
_FOOTER_HEIGHT = 22
_CAPTION_HEIGHT = 34
_PDF_RENDER_DPI = 150
_FONT_FILES = ("NotoKufiArabic-Regular.ttf", "NotoKufiArabic-SemiBold.ttf", "NotoKufiArabic-Bold.ttf")

_font_family: Optional[str] = None


@dataclass
class AttachmentPage:
    """One printed attachment page: an image (file path or encoded bytes) or a note."""
    caption: str
    image_path: Optional[str] = None
    image_bytes: Optional[bytes] = None
    note: str = ""


def configure_printer(printer: QPrinter, doc_name: str) -> None:
    printer.setPageSize(QPageSize(QPageSize.A4))
    printer.setPageOrientation(QPageLayout.Portrait)
    printer.setPageMargins(12, 12, 12, 12, QPrinter.Millimeter)
    printer.setFullPage(False)
    printer.setDocName(doc_name)


def prepare_attachment_pages(model: ApplicationPrintModel) -> List[AttachmentPage]:
    """Turn downloaded attachments into printable pages (safe off the GUI thread)."""
    pages: List[AttachmentPage] = []
    for item in model.attachments:
        caption = " — ".join(filter(None, [item.doc_type, item.person, item.file_name]))
        path = item.local_path
        if not path:
            pages.append(AttachmentPage(caption, note=tr("print.attachment_download_failed")))
        elif _is_pdf(path):
            pages.extend(_pdf_pages(path, caption))
        elif QImageReader(path).canRead():
            pages.append(AttachmentPage(caption, image_path=path))
        else:
            pages.append(AttachmentPage(caption, note=tr("print.attachment_not_printable")))
    return pages


def render_application(printer: QPrinter, model: ApplicationPrintModel,
                       include_attachments: bool,
                       attachment_pages: Optional[List[AttachmentPage]] = None) -> None:
    """Paint the whole application; called for preview, printing and PDF export."""
    attachment_pages = attachment_pages if include_attachments else []
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Could not start printing")
    try:
        scale = printer.logicalDpiX() / _LAYOUT_DPI
        painter.scale(scale, scale)
        page_w = printer.width() / scale
        page_h = printer.height() / scale
        body_h = page_h - _FOOTER_HEIGHT

        doc = _build_document(model, include_attachments, QSizeF(page_w, body_h))
        form_pages = doc.pageCount()
        total = form_pages + len(attachment_pages)
        align = Qt.AlignRight if model.rtl else Qt.AlignLeft

        for index in range(total):
            if index:
                printer.newPage()
            if index < form_pages:
                painter.save()
                painter.translate(0, -index * body_h)
                doc.drawContents(painter, QRectF(0, index * body_h, page_w, body_h))
                painter.restore()
            else:
                _draw_attachment(painter, attachment_pages[index - form_pages],
                                 QRectF(0, 0, page_w, body_h), align)
            if model.is_draft:
                _draw_watermark(painter, page_w, page_h)
            _draw_footer(painter, QRectF(0, body_h, page_w, _FOOTER_HEIGHT), index + 1, total)
    finally:
        painter.end()


def _build_document(model: ApplicationPrintModel, include_attachments: bool,
                    page_size: QSizeF) -> QTextDocument:
    doc = QTextDocument()
    # Lay out at a fixed 96 dpi whatever the screen is; the painter scales.
    reference = QImage(1, 1, QImage.Format_RGB32)
    dots_per_meter = round(_LAYOUT_DPI / 0.0254)
    reference.setDotsPerMeterX(dots_per_meter)
    reference.setDotsPerMeterY(dots_per_meter)
    doc.documentLayout().setPaintDevice(reference)
    doc._layout_device = reference  # the layout keeps only a raw pointer

    doc.setDefaultFont(QFont(_print_font_family(), 9))
    option = QTextOption()
    option.setTextDirection(Qt.RightToLeft if model.rtl else Qt.LeftToRight)
    doc.setDefaultTextOption(option)

    logo = QImage(str(Config.IMAGES_DIR / "un-logo.jpg"))
    if not logo.isNull():
        doc.addResource(QTextDocument.ImageResource, QUrl(LOGO_RESOURCE), logo)

    doc.setHtml(build_application_html(model, include_attachments))
    doc.setPageSize(page_size)
    return doc


def _draw_attachment(painter: QPainter, page: AttachmentPage, rect: QRectF, align) -> None:
    painter.save()
    painter.setFont(_painter_font(10, QFont.Bold))
    painter.setPen(QColor(TITLE_COLOR))
    caption_rect = QRectF(rect.left(), rect.top(), rect.width(), _CAPTION_HEIGHT)
    painter.drawText(caption_rect, align | Qt.AlignVCenter | Qt.TextWordWrap, page.caption)

    area = QRectF(rect.left(), rect.top() + _CAPTION_HEIGHT + 6,
                  rect.width(), rect.height() - _CAPTION_HEIGHT - 6)
    image = _load_image(page)
    if image is None or image.isNull():
        painter.setFont(_painter_font(11))
        painter.setPen(QColor("#374151"))
        painter.drawText(area, Qt.AlignCenter | Qt.TextWordWrap,
                         page.note or tr("print.attachment_not_printable"))
    else:
        size = QSizeF(image.size())
        size.scale(area.size(), Qt.KeepAspectRatio)
        target = QRectF(area.left() + (area.width() - size.width()) / 2, area.top(),
                        size.width(), size.height())
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(target, image)
    painter.restore()


def _draw_watermark(painter: QPainter, page_w: float, page_h: float) -> None:
    painter.save()
    painter.translate(page_w / 2, page_h / 2)
    painter.rotate(-35)
    painter.setFont(_painter_font(44, QFont.Bold))
    painter.setPen(QColor(185, 28, 28, 45))
    painter.drawText(QRectF(-page_w, -60, page_w * 2, 120), Qt.AlignCenter, tr("print.draft_marker"))
    painter.restore()


def _draw_footer(painter: QPainter, rect: QRectF, page: int, total: int) -> None:
    painter.save()
    painter.setFont(_painter_font(8))
    painter.setPen(QColor("#6B7280"))
    painter.drawText(rect, Qt.AlignCenter, tr("print.page_x_of_n", x=page, n=total))
    painter.restore()


def _painter_font(point_size: float, weight: int = QFont.Normal) -> QFont:
    """Font for text painted directly: sized in 96-dpi pixels, since the
    painter is already scaled to the printer resolution."""
    font = QFont(_print_font_family())
    font.setPixelSize(round(point_size * _LAYOUT_DPI / 72))
    font.setWeight(weight)
    return font


def _load_image(page: AttachmentPage) -> Optional[QImage]:
    if page.image_bytes:
        return QImage.fromData(page.image_bytes)
    if page.image_path:
        reader = QImageReader(page.image_path)
        reader.setAutoTransform(True)  # honour EXIF rotation of phone photos
        return reader.read()
    return None


def _is_pdf(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def _pdf_pages(path: str, caption: str) -> List[AttachmentPage]:
    import pypdfium2 as pdfium

    pages: List[AttachmentPage] = []
    try:
        pdf = pdfium.PdfDocument(path)
    except Exception as e:
        logger.warning(f"Cannot open PDF attachment {path}: {e}")
        return [AttachmentPage(caption, note=tr("print.attachment_not_printable"))]
    try:
        count = len(pdf)
        for i in range(count):
            image = pdf[i].render(scale=_PDF_RENDER_DPI / 72).to_pil().convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=85)
            pages.append(AttachmentPage(f"{caption} ({i + 1}/{count})", image_bytes=buffer.getvalue()))
    except Exception as e:
        logger.warning(f"Cannot render PDF attachment {path}: {e}")
        pages.append(AttachmentPage(caption, note=tr("print.attachment_not_printable")))
    finally:
        pdf.close()
    return pages


def _print_font_family() -> str:
    """Bundled Arabic font, so the printout looks the same on every machine."""
    global _font_family
    if _font_family is None:
        _font_family = "Noto Kufi Arabic"
        for name in _FONT_FILES:
            font_id = QFontDatabase.addApplicationFont(str(Config.FONTS_DIR / "Noto_Kufi_Arabic" / name))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if families:
                _font_family = families[0]
    return _font_family
