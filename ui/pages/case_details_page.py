# -*- coding: utf-8 -*-
"""Case details page using ReviewStep in read-only mode."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpacerItem, QSizePolicy,
    QDialog, QTextEdit, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from ui.wizards.office_survey.steps.review_step import ReviewStep
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from ui.design_system import Colors, PageDimensions
from ui.style_manager import StyleManager
from ui.font_utils import FontManager, create_font
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger

logger = get_logger(__name__)


class CaseDetailsPage(QWidget):
    """Standalone page that displays case/survey details in read-only mode."""

    back_requested = pyqtSignal()
    resume_requested = pyqtSignal(str)  # survey_id
    cancel_requested = pyqtSignal(str, str)  # survey_id, reason

    def __init__(self, parent=None):
        super().__init__(parent)

        self._context = SurveyContext()
        self._review = ReviewStep(self._context, read_only=True)
        self._review.initialize()

        self._setup_ui()
    # UI Setup

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.content_padding_h(),
            PageDimensions.content_padding_v_top(),
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)

        self.setStyleSheet(StyleManager.page_background())

        main_layout.addWidget(self._create_header())
        main_layout.addWidget(self._review, 1)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Title + breadcrumb
        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        self._title_label = QLabel(tr("page.case_details.title"))
        self._title_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
            border: none;
        """)

        self._breadcrumb_label = QLabel(self._build_breadcrumb())
        self._breadcrumb_label.setFont(create_font(
            size=FontManager.SIZE_SMALL,
            weight=FontManager.WEIGHT_REGULAR
        ))
        self._breadcrumb_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; border: none;")

        text_box.addWidget(self._title_label)
        text_box.addWidget(self._breadcrumb_label)
        layout.addLayout(text_box)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Resume button (draft only)
        self._resume_btn = QPushButton(tr("page.case_details.resume"))
        self._resume_btn.setFixedSize(160, 40)
        self._resume_btn.setCursor(Qt.PointingHandCursor)
        self._resume_btn.setVisible(False)
        self._resume_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #2A7BC8; }}
        """)
        self._resume_btn.clicked.connect(self._on_resume_clicked)
        layout.addWidget(self._resume_btn)

        # Cancel survey button (draft only)
        self._cancel_btn = QPushButton(tr("page.case_details.cancel_survey"))
        self._cancel_btn.setFixedSize(140, 40)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FECACA;
                border-color: #F87171;
            }
        """)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self._cancel_btn)

        # Back button
        self._back_btn = QPushButton(tr("action.back"))
        self._back_btn.setFixedSize(100, 40)
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)
        self._back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self._back_btn)

        return header
    # Data

    def _build_breadcrumb(self) -> str:
        return f"{tr('page.case_details.breadcrumb')}  ·  {tr('page.case_details.title')}"

    def _on_resume_clicked(self):
        survey_id = None
        if self._context:
            survey_id = self._context.get_data("survey_id")
            if not survey_id:
                survey_id = getattr(self._context, 'wizard_id', None)
        if survey_id:
            logger.info(f"Resume requested for survey: {survey_id}")
            self.resume_requested.emit(survey_id)
        else:
            logger.warning("No survey_id in context for resume")

    def _on_cancel_clicked(self):
        survey_id = None
        if self._context:
            survey_id = self._context.get_data("survey_id")
            if not survey_id:
                survey_id = getattr(self._context, 'wizard_id', None)
        if not survey_id:
            logger.warning("No survey_id in context for cancel")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("page.case_details.cancel_survey"))
        dialog.setModal(True)
        dialog.setFixedWidth(400)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setAttribute(Qt.WA_TranslucentBackground)

        # Outer layout with margin for shadow rendering
        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(24, 24, 24, 24)

        # White container card
        container = QWidget()
        container.setObjectName("cancelDialogContainer")
        container.setStyleSheet("""
            QWidget#cancelDialogContainer {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E5E7EB;
            }
            QWidget#cancelDialogContainer QLabel {
                border: none;
                background: transparent;
            }
        """)

        # Shadow on container
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 80))
        container.setGraphicsEffect(shadow)

        outer_layout.addWidget(container)

        # Card content layout
        card_layout = QVBoxLayout(container)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(0)

        # Icon (red circle with X)
        icon_widget = QWidget()
        icon_widget.setFixedSize(48, 48)
        icon_widget.setStyleSheet("""
            QWidget {
                background-color: #FFE7E7;
                border-radius: 24px;
            }
        """)
        icon_inner = QVBoxLayout(icon_widget)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        icon_inner.setAlignment(Qt.AlignCenter)
        icon_label = QLabel("✕")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("color: #E53935; font-size: 24pt; font-weight: bold; background: transparent;")
        icon_inner.addWidget(icon_label)

        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(icon_widget)
        icon_row.addStretch()
        card_layout.addLayout(icon_row)

        card_layout.addSpacing(16)

        # Title
        title_label = QLabel(tr("page.case_details.cancel_survey"))
        title_label.setFont(create_font(size=16, weight=QFont.Bold))
        title_label.setStyleSheet("color: #1A1A1A;")
        title_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)

        card_layout.addSpacing(8)

        # Subtitle
        subtitle = QLabel(tr("page.case_details.cancel_confirm"))
        subtitle.setFont(create_font(size=10, weight=QFont.Normal))
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(16)

        # Reason text edit
        reason_edit = QTextEdit()
        reason_edit.setPlaceholderText(tr("page.case_details.cancel_reason_placeholder"))
        reason_edit.setFixedHeight(80)
        reason_edit.setFont(create_font(size=10, weight=QFont.Normal))
        reason_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px;
                background-color: #F9FAFB;
                color: #1A1A1A;
            }
            QTextEdit:focus { border-color: #E53935; }
        """)
        card_layout.addWidget(reason_edit)

        card_layout.addSpacing(24)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        # Secondary: dismiss
        dismiss_btn = QPushButton(tr("action.dismiss"))
        dismiss_btn.setFixedSize(150, 48)
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.setFont(create_font(size=10, weight=QFont.Medium))
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #6B7280;
                border: none;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #F9FAFB; }
            QPushButton:pressed { background-color: #F3F4F6; }
        """)
        dismiss_shadow = QGraphicsDropShadowEffect()
        dismiss_shadow.setBlurRadius(8)
        dismiss_shadow.setXOffset(0)
        dismiss_shadow.setYOffset(2)
        dismiss_shadow.setColor(QColor(0, 0, 0, 25))
        dismiss_btn.setGraphicsEffect(dismiss_shadow)
        dismiss_btn.clicked.connect(dialog.reject)

        # Primary: confirm cancel (red)
        confirm_btn = QPushButton(tr("page.case_details.confirm_cancel"))
        confirm_btn.setFixedSize(150, 48)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setFont(create_font(size=10, weight=QFont.Medium))
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53935;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #EF5350; }
            QPushButton:pressed { background-color: #C62828; }
        """)
        confirm_btn.clicked.connect(dialog.accept)

        btn_layout.addWidget(dismiss_btn)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)

        if dialog.exec_() == QDialog.Accepted:
            reason = reason_edit.toPlainText().strip()
            if not reason:
                from ui.components.toast import Toast
                Toast.show_toast(self, tr("page.case_details.reason_required"), Toast.WARNING)
                return
            logger.info(f"Cancel requested for survey: {survey_id}")
            self.cancel_requested.emit(survey_id, reason)

    def _update_button_visibility(self):
        """Show resume/cancel buttons only for draft surveys."""
        status = ""
        if self._context:
            status = getattr(self._context, 'status', '') or self._context.get_data("status") or ""
        is_draft = str(status).lower() in ("draft", "1")
        self._resume_btn.setVisible(is_draft)
        self._cancel_btn.setVisible(is_draft)

    def refresh(self, survey_data=None):
        """Called by main_window.navigate_to() — loads survey data into ReviewStep."""
        if survey_data is None:
            return

        try:
            if isinstance(survey_data, SurveyContext):
                self._context = survey_data
            elif isinstance(survey_data, dict):
                self._context = SurveyContext.from_dict(survey_data)
            else:
                logger.warning(f"Unexpected survey_data type: {type(survey_data)}")
                return

            self._review.context = self._context
            self._review._populate_review()
            self._update_button_visibility()
            logger.info("Case details page refreshed successfully")
        except Exception as e:
            logger.error(f"Error refreshing case details: {e}", exc_info=True)

    def update_language(self, is_arabic=True):
        self.setLayoutDirection(get_layout_direction())
        self._title_label.setText(tr("page.case_details.title"))
        self._breadcrumb_label.setText(self._build_breadcrumb())
        self._resume_btn.setText(tr("page.case_details.resume"))
        self._cancel_btn.setText(tr("page.case_details.cancel_survey"))
        self._back_btn.setText(tr("action.back"))
        self._review._populate_review()
