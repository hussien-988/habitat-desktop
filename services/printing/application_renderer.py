# -*- coding: utf-8 -*-
"""
Paint a printed document (claim application, case report) onto a QPrinter
(print preview, printer or PDF).

The form is laid out by QTextDocument at 96 dpi with design metrics (exact,
unhinted glyph advances) and painted page by page with the painter scaled to
the printer resolution, as QTextDocument.print does. Captions, the footer and
the draft watermark are painted in printer coordinates with point-size fonts.
Every page gets a "page X of N" footer and, for drafts, a diagonal watermark.
"""

import io
from dataclasses import dataclass
from typing import List, Optional

from PyQt5.QtCore import QRectF, QSizeF, Qt, QUrl
from PyQt5.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QImageReader, QPageLayout, QPageSize,
    QPainter, QTextCursor, QTextDocument, QTextOption,
)
from PyQt5.QtPrintSupport import QPrinter

from app.config import Config
from services.printing.application_html import build_application_html
from services.printing.html_parts import LOGO_RESOURCE, TITLE_COLOR
from services.printing.application_print_model import ApplicationPrintModel
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)

_LAYOUT_DPI = 96
# Heights in 96-dpi layout units, scaled to the printer resolution when drawn
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
    render_document(printer, build_application_html(model, include_attachments), model.rtl,
                    model.is_draft, attachment_pages if include_attachments else None)


def render_document(printer: QPrinter, html: str, rtl: bool, is_draft: bool = False,
                    attachment_pages: Optional[List[AttachmentPage]] = None) -> None:
    """Paint `html` page by page, then one page per attachment."""
    attachment_pages = attachment_pages or []
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Could not start printing")
    try:
        direction = Qt.RightToLeft if rtl else Qt.LeftToRight
        painter.setLayoutDirection(direction)
        scale = printer.logicalDpiX() / _LAYOUT_DPI
        page = QRectF(0, 0, printer.width(), printer.height())
        body = QRectF(0, 0, page.width(), page.height() - _FOOTER_HEIGHT * scale)

        # The text document works in 96-dpi layout units
        doc_w, doc_h = body.width() / scale, body.height() / scale
        doc = _build_document(html, QSizeF(doc_w, doc_h), direction)
        form_pages = doc.pageCount()
        total = form_pages + len(attachment_pages)

        for index in range(total):
            if index:
                printer.newPage()
            if index < form_pages:
                painter.save()
                painter.scale(scale, scale)
                painter.translate(0, -index * doc_h)
                doc.drawContents(painter, QRectF(0, index * doc_h, doc_w, doc_h))
                painter.restore()
            else:
                _draw_attachment(painter, attachment_pages[index - form_pages], body, scale, rtl)
            if is_draft:
                _draw_watermark(painter, page)
            _draw_footer(painter, QRectF(0, body.bottom(), page.width(), page.height() - body.height()),
                         index + 1, total)
    finally:
        painter.end()


def _build_document(html: str, page_size: QSizeF, direction) -> QTextDocument:
    doc = QTextDocument()
    # Lay out at a fixed 96 dpi whatever the screen is; the painter scales.
    reference = QImage(1, 1, QImage.Format_RGB32)
    dots_per_meter = round(_LAYOUT_DPI / 0.0254)
    reference.setDotsPerMeterX(dots_per_meter)
    reference.setDotsPerMeterY(dots_per_meter)
    doc.documentLayout().setPaintDevice(reference)
    doc._layout_device = reference  # the layout keeps only a raw pointer
    # Unhinted advances: hinted ones are rounded to whole 96-dpi pixels and
    # drift once scaled, which opens gaps between joined Arabic letters.
    doc.setUseDesignMetrics(True)

    doc.setDefaultFont(QFont(_print_font_family(), 9))
    option = QTextOption()
    option.setTextDirection(direction)
    doc.setDefaultTextOption(option)

    logo = QImage(str(Config.IMAGES_DIR / "un-logo.jpg"))
    if not logo.isNull():
        doc.addResource(QTextDocument.ImageResource, QUrl(LOGO_RESOURCE), logo)

    doc.setHtml(html)
    _apply_direction(doc, direction)
    doc.setPageSize(page_size)
    return doc


def _apply_direction(doc: QTextDocument, direction) -> None:
    """Set the direction of every paragraph, including those in table cells
    (QTextDocument applies the HTML `dir` attribute only partially): text is
    then aligned to the right in RTL and mixed Arabic/Latin text ordered right."""
    block = doc.begin()
    while block.isValid():
        block_format = block.blockFormat()
        block_format.setLayoutDirection(direction)
        QTextCursor(block).setBlockFormat(block_format)
        block = block.next()


def _draw_attachment(painter: QPainter, page: AttachmentPage, rect: QRectF,
                     scale: float, rtl: bool) -> None:
    painter.save()
    caption_h = _CAPTION_HEIGHT * scale
    align = (Qt.AlignRight if rtl else Qt.AlignLeft) | Qt.AlignAbsolute
    painter.setFont(_font(10, QFont.Bold))
    painter.setPen(QColor(TITLE_COLOR))
    painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), caption_h),
                     align | Qt.AlignVCenter | Qt.TextWordWrap, page.caption)

    gap = 6 * scale
    area = QRectF(rect.left(), rect.top() + caption_h + gap,
                  rect.width(), rect.height() - caption_h - gap)
    image = _load_image(page)
    if image is None or image.isNull():
        painter.setFont(_font(11))
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


def _draw_watermark(painter: QPainter, page: QRectF) -> None:
    painter.save()
    painter.translate(page.center())
    painter.rotate(-35)
    painter.setFont(_font(44, QFont.Bold))
    painter.setPen(QColor(185, 28, 28, 45))
    painter.drawText(QRectF(-page.width(), -page.height() / 8, page.width() * 2, page.height() / 4),
                     Qt.AlignCenter, tr("print.draft_marker"))
    painter.restore()


def _draw_footer(painter: QPainter, rect: QRectF, page: int, total: int) -> None:
    painter.save()
    painter.setFont(_font(8))
    painter.setPen(QColor("#6B7280"))
    painter.drawText(rect, Qt.AlignCenter, tr("print.page_x_of_n", x=page, n=total))
    painter.restore()


def _font(point_size: float, weight: int = QFont.Normal) -> QFont:
    """Print font for text painted in printer coordinates."""
    font = QFont(_print_font_family(), -1, weight)
    font.setPointSizeF(point_size)
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
