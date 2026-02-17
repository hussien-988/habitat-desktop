# -*- coding: utf-8 -*-
"""
Case Details Page — displays survey/claim details using ReviewStep in read-only mode.

Design: Matches project design system (PageDimensions, StyleManager).
Architecture: Reuses ReviewStep via Composition (DRY) — no code duplication.
Data: refresh() receives SurveyContext from API via main_window navigation.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMenu, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

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

    def __init__(self, parent=None):
        super().__init__(parent)

        # Start empty — real data arrives via refresh()
        self._context = SurveyContext()
        self._review = ReviewStep(self._context, read_only=True)
        self._review.initialize()

        self._setup_ui()

    # =========================================================================
    # UI Setup — matches PageDimensions / StyleManager (DRY with other pages)
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

        # Header (transparent bg — same pattern as CompletedClaimsPage)
        main_layout.addWidget(self._create_header())

        # Body: ReviewStep (has its own internal scroll area)
        main_layout.addWidget(self._review, 1)

    def _create_header(self) -> QWidget:
        """Page header: title + breadcrumb (right) and ⋮ menu (left)."""
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Right side: title + breadcrumb
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

        # Spacer
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Menu button (⋮)
        self._menu_btn = QPushButton("⋮")
        self._menu_btn.setFixedSize(36, 36)
        self._menu_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #475569;
                font-size: 24px;
                font-weight: 700;
                background: transparent;
                border-radius: 18px;
            }
            QPushButton:hover {
                color: #1e293b;
                background-color: #F1F5F9;
            }
        """)
        self._menu_btn.setCursor(Qt.PointingHandCursor)

        menu = QMenu(self._menu_btn)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F1F5F9;
            }
        """)
        back_action = menu.addAction(tr("page.case_details.back_to_list"))
        back_action.triggered.connect(self.back_requested.emit)
        self._menu_btn.setMenu(menu)

        layout.addWidget(self._menu_btn)

        return header

    # =========================================================================
    # Data
    # =========================================================================

    def _build_breadcrumb(self) -> str:
        return f"{tr('page.case_details.breadcrumb')}  ·  {tr('page.case_details.title')}"

    def refresh(self, survey_data=None):
        """
        Called by main_window.navigate_to() — loads survey data into ReviewStep.

        Args:
            survey_data: dict (context_data JSON from API) or SurveyContext.
                         When None, keeps current data.
        """
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
            logger.info("Case details page refreshed successfully")
        except Exception as e:
            logger.error(f"Error refreshing case details: {e}", exc_info=True)

    def update_language(self, is_arabic=True):
        """Support language switching."""
        self._title_label.setText(tr("page.case_details.title"))
        self._breadcrumb_label.setText(self._build_breadcrumb())
        self._review._populate_review()

