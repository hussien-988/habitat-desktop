# -*- coding: utf-8 -*-
"""
Case Details Page — displays survey/claim details using ReviewStep in read-only mode.

Design: Matches project design system (PageDimensions, StyleManager).
Architecture: Reuses ReviewStep via Composition (DRY) — no code duplication.
Data: refresh() receives SurveyContext from API via main_window navigation.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.wizards.office_survey.steps.review_step import ReviewStep
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from ui.design_system import Colors, PageDimensions
from ui.style_manager import StyleManager
from ui.font_utils import FontManager, create_font
from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)


class CaseDetailsPage(QWidget):
    """Standalone page that displays case/survey details in read-only mode."""

    back_requested = pyqtSignal()
    resume_requested = pyqtSignal(str)  # survey_id

    def __init__(self, parent=None):
        super().__init__(parent)

        self._context = SurveyContext()
        self._review = ReviewStep(self._context, read_only=True)
        self._review.initialize()

        self._setup_ui()

    # =========================================================================
    # UI Setup
    # =========================================================================

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
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
        self._resume_btn = QPushButton("استئناف التعديل")
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

        # Back button
        self._back_btn = QPushButton("رجوع")
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

    # =========================================================================
    # Data
    # =========================================================================

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

    def _update_button_visibility(self):
        """Show resume button only for draft surveys."""
        status = ""
        if self._context:
            status = getattr(self._context, 'status', '') or self._context.get_data("status") or ""
        is_draft = str(status).lower() in ("draft", "1")
        self._resume_btn.setVisible(is_draft)

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
        self._title_label.setText(tr("page.case_details.title"))
        self._breadcrumb_label.setText(self._build_breadcrumb())
        self._review._populate_review()
