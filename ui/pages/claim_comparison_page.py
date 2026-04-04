# -*- coding: utf-8 -*-
"""Claim comparison page for side-by-side record comparison and merge."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QScrollArea,
    QSizePolicy, QGraphicsDropShadowEffect, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt5.QtGui import QColor, QIcon

from repositories.database import Database
from services.duplicate_service import DuplicateService
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions
from ui.components.claim_list_card import ClaimListCard
from ui.components.icon import Icon
from ui.components.toast import Toast
from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

RADIO_STYLE = StyleManager.radio_button()


class ClaimComparisonPage(QWidget):
    """Claim comparison page — shows two persons side by side for merge."""

    back_requested = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db)
        self.claim_radio_group = QButtonGroup(self)
        self._current_group = None
        self._comparison_data = []
        self._user_id = None
        self._current_conflict_type = ""
        self._setup_ui()

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def set_user_id(self, user_id: str):
        """Set current user ID for audit trail."""
        self._user_id = user_id

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
            + StyleManager.scrollbar()
        )
        self._scroll_area = scroll

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(
            PageDimensions.content_padding_h(),
            PageDimensions.content_padding_v_top(),
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        self._content_layout.setSpacing(20)

        # Header
        header = self._build_header()
        self._content_layout.addLayout(header)

        # Claims card
        self._claims_card = self._build_claims_container()
        self._content_layout.addWidget(self._claims_card)

        # Comparison section
        self._comparison_wrapper = self._build_comparison_container()
        self._content_layout.addWidget(self._comparison_wrapper)

        # Document comparison section
        self._doc_comparison_card = self._build_document_comparison()
        self._content_layout.addWidget(self._doc_comparison_card)

        # Resolution section
        self._resolution_card = self._build_resolution_section()
        self._content_layout.addWidget(self._resolution_card)

        self._content_layout.addStretch()
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ────────────────────────────────────────────
    # Header
    # ────────────────────────────────────────────
    def _build_header(self) -> QVBoxLayout:
        header = QVBoxLayout()
        header.setSpacing(4)
        header.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self._header_title = QLabel(tr("page.comparison.title"))
        self._header_title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        self._header_title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        self.action_btn = QPushButton(tr("page.comparison.execute"))
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self.action_btn.setFixedSize(90, 48)
        self.action_btn.setStyleSheet(StyleManager.nav_button_primary())
        self.action_btn.clicked.connect(self._on_action_clicked)

        top_row.addWidget(self._header_title)
        top_row.addStretch()
        top_row.addWidget(self.action_btn)
        header.addLayout(top_row)

        # Breadcrumb
        self._breadcrumb = QLabel(tr("page.comparison.breadcrumb"))
        self._breadcrumb.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self._breadcrumb.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent; border: none;")
        header.addWidget(self._breadcrumb)

        return header

    # ────────────────────────────────────────────
    # Claims Container
    # ────────────────────────────────────────────
    def _build_claims_container(self) -> QFrame:
        card = QFrame()
        card.setObjectName("claimsCompCard")
        card.setStyleSheet(StyleManager.form_card())

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(16, 16, 16, 16)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(tr("page.comparison.persons"))
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")

        title_row.addWidget(title_label)
        title_row.addStretch()
        card_layout.addLayout(title_row)

        subtitle = QLabel(tr("page.comparison.select_primary_record"))
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        self._claims_rows_layout = QVBoxLayout()
        self._claims_rows_layout.setSpacing(8)
        card_layout.addLayout(self._claims_rows_layout)

        return card

    # ────────────────────────────────────────────
    # Comparison Container
    # ────────────────────────────────────────────
    def _build_comparison_container(self) -> QFrame:
        wrapper = QFrame()
        wrapper.setObjectName("comparisonWrapper")
        wrapper.setStyleSheet("QFrame#comparisonWrapper { background: transparent; border: none; }")

        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setSpacing(16)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)

        comp_title = QLabel(tr("page.comparison.comparison"))
        comp_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        comp_title.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        wrapper_layout.addWidget(comp_title)

        self._comparison_cards_layout = QHBoxLayout()
        self._comparison_cards_layout.setSpacing(30)
        wrapper_layout.addLayout(self._comparison_cards_layout)

        return wrapper

    # ────────────────────────────────────────────
    # Document Comparison Section
    # ────────────────────────────────────────────
    def _build_document_comparison(self) -> QFrame:
        card = QFrame()
        card.setObjectName("docCompCard")
        card.setStyleSheet(StyleManager.form_card())

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(16, 16, 16, 16)

        title_row = QHBoxLayout()
        title_label = QLabel(tr("page.comparison.document_comparison"))
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        self._doc_load_btn = QPushButton(tr("page.comparison.load_comparison"))
        self._doc_load_btn.setCursor(Qt.PointingHandCursor)
        self._doc_load_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._doc_load_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.PRIMARY_BLUE};
                background: {Colors.PRIMARY_BLUE}0D;
                border: 1px solid {Colors.PRIMARY_BLUE}33;
                border-radius: 8px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background: {Colors.PRIMARY_BLUE}1A;
                border-color: {Colors.PRIMARY_BLUE}66;
            }}
        """)
        self._doc_load_btn.clicked.connect(self._load_document_comparison)

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(self._doc_load_btn)
        card_layout.addLayout(title_row)

        subtitle = QLabel(tr("page.comparison.documents_linked_to_records"))
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        subtitle.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(subtitle)

        # Two-column layout for documents
        self._doc_columns_layout = QHBoxLayout()
        self._doc_columns_layout.setSpacing(20)

        # First entity docs
        self._doc_first_frame = self._build_doc_entity_column(tr("page.comparison.first_record_docs"))
        self._doc_columns_layout.addWidget(self._doc_first_frame, 1)

        # VS divider
        vs = QLabel("VS")
        vs.setAlignment(Qt.AlignCenter)
        vs.setFixedWidth(40)
        vs.setFont(create_font(size=11, weight=FontManager.WEIGHT_BOLD))
        vs.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: {Colors.PRIMARY_BLUE}10; border-radius: 20px; padding: 8px; border: none;")
        self._doc_columns_layout.addWidget(vs)

        # Second entity docs
        self._doc_second_frame = self._build_doc_entity_column(tr("page.comparison.second_record_docs"))
        self._doc_columns_layout.addWidget(self._doc_second_frame, 1)

        card_layout.addLayout(self._doc_columns_layout)

        # Empty state
        self._doc_empty_label = QLabel(tr("page.comparison.click_load_comparison"))
        self._doc_empty_label.setAlignment(Qt.AlignCenter)
        self._doc_empty_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._doc_empty_label.setStyleSheet("color: #9CA3AF; background: transparent; padding: 30px;")
        card_layout.addWidget(self._doc_empty_label)

        # Initially hide columns, show empty state
        self._doc_first_frame.setVisible(False)
        self._doc_second_frame.setVisible(False)

        return card

    def _build_doc_entity_column(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #F8FAFC; border-radius: 12px; border: 1px solid #E5E7EB; }")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        count_lbl = QLabel(f"0 {tr('page.comparison.documents')}")
        count_lbl.setObjectName("doc_count")
        count_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        count_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        layout.addWidget(count_lbl)

        # Container for evidence cards
        docs_container = QVBoxLayout()
        docs_container.setSpacing(6)
        docs_container.setObjectName("docs_list")
        layout.addLayout(docs_container)

        layout.addStretch()
        return frame

    def _build_evidence_card(self, evidence: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 10px;
                border: 1px solid #E5E7EB;
            }
            QFrame:hover {
                border-color: #93C5FD;
                background: #F0F9FF;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # File name row
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        file_name = evidence.get("originalFileName", "")
        mime = evidence.get("mimeType", "")
        icon_text = self._get_file_icon(mime)

        icon_lbl = QLabel(icon_text)
        icon_lbl.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_lbl.setFixedWidth(20)
        name_row.addWidget(icon_lbl)

        name_lbl = QLabel(file_name or "-")
        name_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        name_lbl.setWordWrap(True)
        name_row.addWidget(name_lbl, 1)

        # Version badge
        version = evidence.get("versionNumber", 1)
        ver_lbl = QLabel(f"v{version}")
        ver_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_BOLD))
        ver_lbl.setFixedWidth(28)
        ver_lbl.setAlignment(Qt.AlignCenter)
        is_current = evidence.get("isCurrentVersion", True)
        ver_color = "#10B981" if is_current else "#9CA3AF"
        ver_lbl.setStyleSheet(f"color: {ver_color}; background: {ver_color}15; border-radius: 4px; padding: 2px; border: none;")
        name_row.addWidget(ver_lbl)

        layout.addLayout(name_row)

        # Details row
        details_parts = []
        desc = evidence.get("description", "")
        if desc:
            details_parts.append(desc)
        authority = evidence.get("issuingAuthority", "")
        if authority:
            details_parts.append(authority)
        ref = evidence.get("documentReferenceNumber", "")
        if ref:
            details_parts.append(f"#{ref}")

        if details_parts:
            details_lbl = QLabel(" | ".join(details_parts))
            details_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            details_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            details_lbl.setWordWrap(True)
            layout.addWidget(details_lbl)

        # Date + size row
        meta_parts = []
        issued = evidence.get("documentIssuedDate", "")
        if issued and "T" in str(issued):
            meta_parts.append(str(issued).split("T")[0])
        size_bytes = evidence.get("fileSizeBytes", 0)
        if size_bytes:
            if size_bytes > 1048576:
                meta_parts.append(f"{size_bytes / 1048576:.1f} MB")
            elif size_bytes > 1024:
                meta_parts.append(f"{size_bytes / 1024:.0f} KB")
            else:
                meta_parts.append(f"{size_bytes} B")

        is_expired = evidence.get("isExpired", False)
        if is_expired:
            meta_parts.append(tr("page.comparison.expired"))

        if meta_parts:
            meta_lbl = QLabel(" | ".join(meta_parts))
            meta_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
            expired_color = "#EF4444" if is_expired else "#9CA3AF"
            meta_lbl.setStyleSheet(f"color: {expired_color}; background: transparent; border: none;")
            layout.addWidget(meta_lbl)

        return card

    @staticmethod
    def _get_file_icon(mime_type: str) -> str:
        if not mime_type:
            return "📄"
        if "pdf" in mime_type:
            return "📕"
        if "image" in mime_type:
            return "🖼"
        if "word" in mime_type or "document" in mime_type:
            return "📘"
        if "excel" in mime_type or "spreadsheet" in mime_type:
            return "📗"
        return "📄"

    def _populate_doc_column(self, frame: QFrame, evidences: list):
        layout = frame.layout()
        # Find docs_list container
        docs_layout = None
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.layout() and item.layout().objectName() == "docs_list":
                docs_layout = item.layout()
                break

        if not docs_layout:
            return

        # Clear existing
        while docs_layout.count():
            child = docs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Update count
        count_lbl = frame.findChild(QLabel, "doc_count")
        if count_lbl:
            count_lbl.setText(f"{len(evidences)} {tr('page.comparison.document_singular')}" if len(evidences) != 0 else tr("page.comparison.no_documents"))

        # Add evidence cards
        for ev in evidences:
            ev_card = self._build_evidence_card(ev)
            docs_layout.addWidget(ev_card)

    def _load_document_comparison(self):
        if not self._current_group:
            return

        conflict_id = self._current_group.get("id", "")
        if not conflict_id:
            Toast.show_toast(self, tr("page.comparison.conflict_id_unavailable"), Toast.WARNING)
            return

        self._doc_load_btn.setEnabled(False)

        entity_ids = [
            self._current_group.get("firstEntityId", ""),
            self._current_group.get("secondEntityId", ""),
        ]
        is_person = self._current_conflict_type == "PersonDuplicate"

        self._doc_comparison_worker = ApiWorker(
            self._fetch_document_comparison, conflict_id, entity_ids, is_person
        )
        self._doc_comparison_worker.finished.connect(self._on_doc_comparison_loaded)
        self._doc_comparison_worker.error.connect(self._on_doc_comparison_error)
        self._spinner.show_loading(tr("component.loading.default"))
        self._doc_comparison_worker.start()

    def _fetch_document_comparison(self, conflict_id, entity_ids, is_person):
        """Fetch document comparison data (runs in worker thread)."""
        first_evidences = []
        second_evidences = []

        # Try document-comparison endpoint first
        try:
            doc_data = self.duplicate_service.get_document_comparison(conflict_id)
            logger.info(f"Document comparison response: {str(doc_data)[:500]}")

            if isinstance(doc_data, dict):
                first_entity = doc_data.get("firstEntity") or doc_data.get("firstRecord") or {}
                second_entity = doc_data.get("secondEntity") or doc_data.get("secondRecord") or {}

                first_evidences = (
                    first_entity.get("evidences", [])
                    or first_entity.get("documents", [])
                    or first_entity.get("attachments", [])
                )
                second_evidences = (
                    second_entity.get("evidences", [])
                    or second_entity.get("documents", [])
                    or second_entity.get("attachments", [])
                )

                if not first_evidences and not second_evidences:
                    entities_list = doc_data.get("entities", doc_data.get("records", []))
                    if isinstance(entities_list, list) and len(entities_list) >= 2:
                        first_evidences = entities_list[0].get("evidences", entities_list[0].get("documents", []))
                        second_evidences = entities_list[1].get("evidences", entities_list[1].get("documents", []))

                if not first_evidences and not second_evidences:
                    root_docs = doc_data.get("evidences", doc_data.get("documents", []))
                    if isinstance(root_docs, list) and len(root_docs) >= 2:
                        mid = len(root_docs) // 2
                        first_evidences = root_docs[:mid]
                        second_evidences = root_docs[mid:]

            elif isinstance(doc_data, list):
                if len(doc_data) >= 2 and isinstance(doc_data[0], dict):
                    if "evidences" in doc_data[0] or "documents" in doc_data[0]:
                        first_evidences = doc_data[0].get("evidences", doc_data[0].get("documents", []))
                        second_evidences = doc_data[1].get("evidences", doc_data[1].get("documents", []))
                    else:
                        mid = len(doc_data) // 2
                        first_evidences = doc_data[:mid]
                        second_evidences = doc_data[mid:]

        except Exception as e:
            logger.warning(f"Document comparison endpoint failed: {e}")

        # Fallback: fetch building documents directly from each entity
        if not first_evidences and not second_evidences:
            if not is_person:
                try:
                    from services.api_client import get_api_client
                    api = get_api_client()
                    if api:
                        for idx, eid in enumerate(entity_ids):
                            if not eid:
                                continue
                            try:
                                unit_dto = api.get_property_unit_by_id(eid)
                                building_id = ""
                                if unit_dto:
                                    building_id = unit_dto.get("buildingId", unit_dto.get("building_id", ""))
                                if building_id:
                                    docs = api.get_building_documents(building_id)
                                    if docs:
                                        if idx == 0:
                                            first_evidences = docs
                                        else:
                                            second_evidences = docs
                                        logger.info(f"Fetched {len(docs)} building docs for entity {idx}")
                            except Exception as be:
                                logger.warning(f"Failed to fetch building docs for {eid}: {be}")
                except Exception as e:
                    logger.warning(f"Building documents fallback failed: {e}")

        return {"first": first_evidences, "second": second_evidences}

    def _on_doc_comparison_loaded(self, result):
        """Handle document comparison result on main thread."""
        self._spinner.hide_loading()
        self._doc_load_btn.setEnabled(True)
        first_evidences = result.get("first", [])
        second_evidences = result.get("second", [])

        if not first_evidences and not second_evidences:
            Toast.show_toast(self, tr("page.comparison.no_linked_documents"), Toast.WARNING)
            return

        self._doc_empty_label.setVisible(False)
        self._doc_first_frame.setVisible(True)
        self._doc_second_frame.setVisible(True)

        self._populate_doc_column(self._doc_first_frame, first_evidences)
        self._populate_doc_column(self._doc_second_frame, second_evidences)

    def _on_doc_comparison_error(self, error_msg):
        """Handle document comparison error."""
        self._spinner.hide_loading()
        self._doc_load_btn.setEnabled(True)
        logger.warning(f"Document comparison failed: {error_msg}")
        Toast.show_toast(self, tr("page.comparison.failed_loading_documents"), Toast.ERROR)

    # ────────────────────────────────────────────
    # Resolution Section
    # ────────────────────────────────────────────
    def _build_resolution_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("resolutionCompCard")
        card.setStyleSheet(StyleManager.form_card())

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(16, 16, 16, 16)

        title_label = QLabel(tr("page.comparison.resolution_action"))
        title_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet("color: #E74C3C; background: transparent; border: none;")
        card_layout.addWidget(title_label)

        self._resolution_group = QButtonGroup(self)
        resolution_options = [
            (tr("page.comparison.merge_records"), "merge"),
            (tr("page.comparison.keep_separate"), "keep_separate"),
        ]

        options_layout = QHBoxLayout()
        options_layout.setSpacing(24)
        for idx, (label, value) in enumerate(resolution_options):
            radio = QRadioButton(label)
            radio.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            radio.setStyleSheet(RADIO_STYLE + " QRadioButton { padding: 6px 12px; }")
            radio.setProperty("resolution_type", value)
            self._resolution_group.addButton(radio, idx)
            options_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)
        options_layout.addStretch()
        card_layout.addLayout(options_layout)

        just_label = QLabel(tr("page.comparison.justification_required"))
        just_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        just_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        card_layout.addWidget(just_label)

        self._justification_edit = QTextEdit()
        self._justification_edit.setPlaceholderText(tr("page.comparison.enter_justification"))
        self._justification_edit.setFixedHeight(80)
        self._justification_edit.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._justification_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px;
                background: #FAFBFC;
                color: #333;
            }}
            QTextEdit:focus {{
                border-color: {Colors.PRIMARY_BLUE};
            }}
        """)
        card_layout.addWidget(self._justification_edit)

        return card

    # ────────────────────────────────────────────
    # Shared widget builders
    # ────────────────────────────────────────────
    def _create_inner_card_frame(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(StyleManager.form_card())
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        card.setGraphicsEffect(shadow)
        return card

    def _create_card_header(self, icon_name: str, title_text: str, subtitle_text: str) -> QWidget:
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 7px;
            }
        """)
        icon_pixmap = Icon.load_pixmap(icon_name, size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title_label = QLabel(title_text)
        title_label.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        subtitle_label = QLabel(subtitle_text)
        subtitle_label.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_container)
        header_layout.addStretch()

        return header_container

    def _create_field_vertical(self, label_text: str, value_text: str, is_diff: bool = False) -> QWidget:
        field = QWidget()
        field.setStyleSheet("background: transparent; border: none;")
        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)

        value = QLabel(value_text)
        value.setWordWrap(True)
        value.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)

        if is_diff:
            value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_BOLD))
            value.setStyleSheet("color: #E74C3C; background: #FFF3CD; border: none; padding: 2px 4px; border-radius: 4px;")
        else:
            value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
            value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        field_layout.addWidget(label)
        field_layout.addWidget(value)
        return field

    # ────────────────────────────────────────────
    # Inner Cards with diff highlighting
    # ────────────────────────────────────────────
    def _build_building_info_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        header = self._create_card_header("blue", tr("page.comparison.building_data"), tr("page.comparison.building_location"))
        card_layout.addWidget(header)

        code_label = QLabel(data.get("building_code", "-"))
        code_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        code_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        code_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(code_label)

        # Address pill
        address = data.get("address", "-")
        addr_bar = QFrame()
        addr_bar.setFixedHeight(28)
        addr_bar.setStyleSheet("QFrame { background-color: #F8FAFF; border: none; border-radius: 8px; }")

        addr_row = QHBoxLayout(addr_bar)
        addr_row.setContentsMargins(12, 0, 12, 0)
        addr_row.setSpacing(8)
        addr_row.addStretch()

        addr_icon = QLabel()
        addr_icon.setStyleSheet("background: transparent; border: none;")
        addr_icon_pixmap = Icon.load_pixmap("dec", size=16)
        if addr_icon_pixmap and not addr_icon_pixmap.isNull():
            addr_icon.setPixmap(addr_icon_pixmap)
        addr_row.addWidget(addr_icon)

        addr_text = QLabel(address)
        addr_text.setAlignment(Qt.AlignCenter)
        addr_text.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        addr_text.setStyleSheet("color: #0F5B95; background: transparent; border: none;")
        addr_row.addWidget(addr_text)
        addr_row.addStretch()

        card_layout.addWidget(addr_bar)
        return card

    def _build_building_details_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        stat_items = [
            ("commercial_units", tr("page.comparison.commercial_units"), data.get("commercial_units", "-")),
            ("residential_units", tr("page.comparison.residential_units"), data.get("residential_units", "-")),
            ("total_units", tr("page.comparison.total_units"), data.get("total_units", "-")),
            ("building_type", tr("page.comparison.building_type"), data.get("building_type", "-")),
            ("building_status", tr("page.comparison.building_status"), data.get("building_status", "-")),
            ("general_description", tr("page.comparison.building_description"), data.get("general_description", "-")),
        ]

        for field_key, label_text, value_text in stat_items:
            field = self._create_field_vertical(
                label_text, str(value_text),
                is_diff=(field_key in diff_fields)
            )
            card_layout.addWidget(field)

        # Map placeholder
        map_label = QLabel(tr("page.comparison.building_location_map"))
        map_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        map_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        map_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        card_layout.addWidget(map_label)

        map_container = QLabel()
        map_container.setFixedHeight(130)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("compMapContainer")
        map_container.setStyleSheet("QLabel#compMapContainer { background-color: #E8E8E8; border-radius: 8px; border: none; }")

        loc_fallback = Icon.load_pixmap("carbon_location-filled", size=48)
        if loc_fallback and not loc_fallback.isNull():
            map_container.setPixmap(loc_fallback)

        card_layout.addWidget(map_container)
        card_layout.addStretch()
        return card

    def _build_unit_info_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        header = self._create_card_header("move", tr("page.comparison.units"), tr("page.comparison.unit_info"))
        card_layout.addWidget(header)

        unit_items = [
            ("unit_status", tr("page.comparison.unit_status"), data.get("unit_status", "-")),
            ("unit_type", tr("page.comparison.unit_type"), data.get("unit_type", "-")),
            ("area_sqm", tr("page.comparison.unit_area"), data.get("area_sqm", "-")),
            ("rooms", tr("page.comparison.num_rooms"), data.get("rooms", "-")),
            ("floor", tr("page.comparison.floor_number"), data.get("floor", "-")),
            ("unit_number", tr("page.comparison.unit_number"), data.get("unit_number", "-")),
        ]

        for field_key, label_text, value_text in unit_items:
            field = self._create_field_vertical(
                label_text, str(value_text),
                is_diff=(field_key in diff_fields)
            )
            card_layout.addWidget(field)

        card_layout.addStretch()
        return card

    def _build_person_comparison_card(self, data: dict, diff_fields: set) -> QFrame:
        card = self._create_inner_card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        header = self._create_card_header("yelow", tr("page.comparison.person_data"), tr("page.comparison.duplicate_person_info"))
        card_layout.addWidget(header)

        person_items = [
            ("full_name_ar", tr("page.comparison.full_name"), data.get("full_name_ar", "-")),
            ("mother_name", tr("page.comparison.mother_name"), data.get("mother_name", "-")),
            ("national_id", tr("page.comparison.national_id"), data.get("national_id", "-")),
            ("date_of_birth", tr("page.comparison.date_of_birth"), data.get("date_of_birth", "-")),
            ("gender", tr("page.comparison.gender"), data.get("gender", "-")),
            ("nationality", tr("page.comparison.nationality"), data.get("nationality", "-")),
            ("phone_number", tr("page.comparison.phone_number"), data.get("phone_number", "-")),
        ]

        for field_key, label_text, value_text in person_items:
            field = self._create_field_vertical(
                label_text, str(value_text),
                is_diff=(field_key in diff_fields)
            )
            card_layout.addWidget(field)

        card_layout.addStretch()
        return card

    def _map_person_to_comparison_dict(self, record: dict) -> dict:
        from services.vocab_service import get_label

        full_name_ar = record.get("fullNameArabic") or ""
        if not full_name_ar:
            parts = filter(None, [
                record.get("firstNameArabic", ""),
                record.get("fatherNameArabic", ""),
                record.get("familyNameArabic", ""),
            ])
            full_name_ar = " ".join(parts) or "-"

        dob = record.get("dateOfBirth") or ""
        if dob and "T" in str(dob):
            dob = str(dob).split("T")[0]

        gender_raw = record.get("gender")
        gender_label = get_label("Gender", gender_raw, lang="ar") if gender_raw else "-"

        nationality_raw = record.get("nationality")
        nationality_label = get_label("Nationality", nationality_raw, lang="ar") if nationality_raw else "-"

        return {
            "full_name_ar": str(full_name_ar),
            "mother_name": str(record.get("motherNameArabic") or "-"),
            "national_id": str(record.get("nationalId") or "-"),
            "date_of_birth": dob or "-",
            "gender": gender_label,
            "nationality": nationality_label,
            "phone_number": str(record.get("mobileNumber") or "-"),
        }

    def _compute_person_diff_fields(self, comparison_dicts: list) -> set:
        if len(comparison_dicts) < 2:
            return set()
        diff_fields = set()
        all_keys = [
            "full_name_ar", "mother_name", "national_id",
            "date_of_birth", "gender", "nationality", "phone_number",
        ]
        for key in all_keys:
            values = {str(d.get(key, "")) for d in comparison_dicts}
            if len(values) > 1:
                diff_fields.add(key)
        return diff_fields

    def _build_outer_comparison_card(self, data: dict, diff_fields: set) -> QFrame:
        outer = QFrame()
        outer.setObjectName("outerCompCard")
        outer.setStyleSheet(StyleManager.form_card())
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        outer.setGraphicsEffect(shadow)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(16)

        if self._current_conflict_type == "PersonDuplicate":
            person_card = self._build_person_comparison_card(data, diff_fields)
            outer_layout.addWidget(person_card, 1)
        else:
            card1 = self._build_building_info_card(data, diff_fields)
            card1.setFixedHeight(170)
            outer_layout.addWidget(card1)

            card3 = self._build_unit_info_card(data, diff_fields)
            outer_layout.addWidget(card3, 1)

        return outer

    # ────────────────────────────────────────────
    # Layout helpers
    # ────────────────────────────────────────────
    def _clear_layout(self, layout):
        """Remove all items from a layout recursively."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _map_to_comparison_dict(self, building: dict, unit: dict) -> dict:
        """Map API records to the format expected by comparison cards.

        When data comes from dataComparison (flat dict), pass the same dict
        as both building and unit so all fields are found.
        """
        from services.display_mappings import (
            get_building_type_display, get_building_status_display,
            get_unit_type_display, get_unit_status_display,
        )

        # Handle both camelCase (API) and snake_case (legacy) field names
        address_parts = filter(None, [
            building.get("governorateName", building.get("governorate_name_ar", "")),
            building.get("districtName", building.get("district_name_ar", "")),
            building.get("subDistrictName", building.get("subdistrict_name_ar", "")),
            building.get("address", ""),
        ])

        # Building type/status with vocab resolution
        raw_btype = building.get("buildingType", building.get("building_type", ""))
        raw_bstatus = building.get("buildingStatus", building.get("building_status",
                       building.get("status", "")))
        building_type_label = get_building_type_display(raw_btype) if raw_btype else "-"
        building_status_label = get_building_status_display(raw_bstatus) if raw_bstatus else "-"

        # Unit fields: look in unit dict first, then building dict (for flat dicts)
        def _get_unit(key1, key2="", key3=""):
            val = unit.get(key1, "")
            if not val and key2:
                val = unit.get(key2, "")
            if not val and key3:
                val = unit.get(key3, "")
            if not val:
                val = building.get(key1, "")
            if not val and key2:
                val = building.get(key2, "")
            if not val and key3:
                val = building.get(key3, "")
            return val

        raw_ustatus = _get_unit("unitStatus", "status", "apartment_status")
        raw_utype = _get_unit("unitType", "unit_type")
        unit_status_label = get_unit_status_display(raw_ustatus) if raw_ustatus else "-"
        unit_type_label = get_unit_type_display(raw_utype) if raw_utype else "-"

        raw_area = _get_unit("areaSquareMeters", "area_sqm", "areaSqm")
        raw_rooms = _get_unit("numberOfRooms", "number_of_rooms", "roomCount")
        raw_floor = _get_unit("floorNumber", "floor_number")
        raw_unit_num = _get_unit("unitIdentifier", "unit_number", "unitNumber")

        return {
            "building_code": building.get("buildingId", building.get("building_id",
                             building.get("buildingCode", "-"))),
            "address": " - ".join(address_parts) or "-",
            "residential_units": str(building.get("residentialUnitsCount",
                                    building.get("numberOfApartments",
                                    building.get("number_of_apartments", "-")))),
            "commercial_units": str(building.get("commercialUnitsCount",
                                   building.get("numberOfShops",
                                   building.get("number_of_shops", "-")))),
            "total_units": str(building.get("totalUnitsCount",
                              building.get("numberOfPropertyUnits",
                              building.get("number_of_units", "-")))),
            "building_type": building_type_label,
            "building_status": building_status_label,
            "general_description": building.get("description",
                                   building.get("notes",
                                   building.get("general_description", "-"))),
            "lat": building.get("latitude", 0),
            "lng": building.get("longitude", 0),
            "unit_status": unit_status_label,
            "unit_type": unit_type_label,
            "area_sqm": str(raw_area) if raw_area else "-",
            "rooms": str(raw_rooms) if raw_rooms else "-",
            "floor": str(raw_floor) if raw_floor else "-",
            "unit_number": str(raw_unit_num) if raw_unit_num else "-",
        }

    def _compute_comparison_diff_fields(self, comparison_dicts: list) -> set:
        """Find which fields differ across comparison cards."""
        if len(comparison_dicts) < 2:
            return set()
        diff_fields = set()
        all_keys = ["building_code", "address", "residential_units", "commercial_units",
                     "total_units", "building_type", "building_status", "general_description",
                     "unit_status", "unit_type", "area_sqm", "rooms", "floor", "unit_number"]
        for key in all_keys:
            values = {str(d.get(key, "")) for d in comparison_dicts}
            if len(values) > 1:
                diff_fields.add(key)
        return diff_fields

    # ────────────────────────────────────────────
    # Actions
    # ────────────────────────────────────────────
    def _on_action_clicked(self):
        """Handle resolution action using Conflicts API."""
        justification = self._justification_edit.toPlainText().strip()
        if not justification:
            Toast.show_toast(self, tr("page.comparison.enter_justification_required"), Toast.WARNING)
            return

        selected_radio = self._resolution_group.checkedButton()
        if not selected_radio:
            return

        resolution_type = selected_radio.property("resolution_type")

        if not self._current_group or not self.duplicate_service:
            Toast.show_toast(self, tr("page.comparison.no_data_to_process"), Toast.WARNING)
            return

        conflict_id = self._current_group.get("id", "")
        if not conflict_id:
            Toast.show_toast(self, tr("page.comparison.conflict_id_unavailable"), Toast.WARNING)
            return

        action_labels = {
            "merge": tr("page.comparison.merge_records"),
            "keep_separate": tr("page.comparison.keep_records_separate"),
        }
        action_label = action_labels.get(resolution_type, tr("page.comparison.execute_action"))

        from ui.error_handler import ErrorHandler
        if not ErrorHandler.confirm(
            self,
            f"{tr('page.comparison.confirm_action_message')} {action_label}?\n{tr('page.comparison.cannot_undo')}",
            tr("page.comparison.confirm_action"),
        ):
            return

        master_id = ""
        if resolution_type == "merge":
            selected_idx = self.claim_radio_group.checkedId()
            entity_ids = [
                self._current_group.get("firstEntityId", ""),
                self._current_group.get("secondEntityId", ""),
            ]
            if selected_idx < 0 or selected_idx >= len(entity_ids):
                Toast.show_toast(self, tr("page.comparison.select_primary_record"), Toast.WARNING)
                return
            master_id = entity_ids[selected_idx]
            if not master_id:
                Toast.show_toast(self, tr("page.comparison.record_id_not_found"), Toast.WARNING)
                return

        self.action_btn.setEnabled(False)
        from ui.pages.duplicates_page import _ResolutionWorker
        self._resolution_worker = _ResolutionWorker(
            self.duplicate_service, resolution_type,
            conflict_id, justification, master_id
        )
        self._resolution_worker.finished.connect(self._on_resolution_done)
        self._resolution_worker.error.connect(self._on_resolution_err)
        self._spinner.show_loading(tr("component.loading.default"))
        self._resolution_worker.start()

    def _on_resolution_done(self, success: bool):
        self._spinner.hide_loading()
        self.action_btn.setEnabled(True)
        if success:
            self._justification_edit.clear()
            Toast.show_toast(self, tr("page.comparison.action_success"), Toast.SUCCESS)
            self.back_requested.emit()
        else:
            Toast.show_toast(self, tr("page.comparison.action_failed"), Toast.WARNING)

    def _on_resolution_err(self, error_msg: str):
        self._spinner.hide_loading()
        self.action_btn.setEnabled(True)
        Toast.show_toast(self, f"{tr('page.comparison.action_failed')}: {error_msg}", Toast.ERROR)

    # ────────────────────────────────────────────
    # Refresh — populate with real data from API
    # ────────────────────────────────────────────
    def refresh(self, data=None):
        """Refresh page with conflict data from API.

        Args:
            data: Conflict dict from API (has id, firstEntityId, secondEntityId, etc.)
        """
        logger.debug("Refreshing claim comparison page")
        if data is None:
            return

        if not isinstance(data, dict):
            return

        self._current_group = data
        self._current_conflict_type = data.get("conflictType", "")
        is_person = self._current_conflict_type == "PersonDuplicate"

        # Show spinner during data fetch
        self._spinner.show_loading(tr("component.loading.default"))

        conflict_id = data.get("id", "")
        entity_ids = [data.get("firstEntityId", ""), data.get("secondEntityId", "")]

        def _fetch_comparison_data():
            details = {}
            fetched_persons = {}
            if conflict_id:
                try:
                    details = self.duplicate_service.get_conflict_details(conflict_id)
                except Exception as e:
                    logger.error(f"Failed to fetch conflict details: {e}")
            if is_person:
                for eid in entity_ids:
                    if eid:
                        try:
                            person = self.duplicate_service.get_person_data(eid)
                            if person:
                                fetched_persons[eid] = person
                        except Exception as pe:
                            logger.warning(f"Failed to fetch person {eid}: {pe}")
            return {"details": details, "fetched_persons": fetched_persons}

        self._comparison_fetch_worker = ApiWorker(_fetch_comparison_data)
        self._comparison_fetch_worker.finished.connect(
            lambda result: self._on_comparison_data_loaded(data, result)
        )
        self._comparison_fetch_worker.error.connect(self._on_comparison_data_error)
        self._comparison_fetch_worker.start()

    def _on_comparison_data_error(self, error_msg):
        """Handle comparison data fetch failure."""
        self._spinner.hide_loading()
        logger.error(f"Failed to fetch comparison data: {error_msg}")
        from ui.components.toast import Toast
        Toast.show_toast(self, str(error_msg), Toast.ERROR)

    def _on_comparison_data_loaded(self, data, result):
        """Populate UI after background fetch completes."""
        self._spinner.hide_loading()

        details = result.get("details", {}) if result else {}
        _fetched_persons = result.get("fetched_persons", {}) if result else {}

        is_person = self._current_conflict_type == "PersonDuplicate"

        if details:
            raw_dc = details.get("dataComparison", "")
            logger.info(f"Conflict details keys: {list(details.keys())}")
            if raw_dc:
                logger.info(f"dataComparison type={type(raw_dc).__name__}, "
                            f"preview={str(raw_dc)[:300]}")

        # --- Populate claims section ---
        self._clear_layout(self._claims_rows_layout)

        for btn in self.claim_radio_group.buttons():
            self.claim_radio_group.removeButton(btn)

        # Build two record entries from the conflict data
        records = []
        first_id = data.get("firstEntityIdentifier", data.get("firstEntityId", "-"))
        second_id = data.get("secondEntityIdentifier", data.get("secondEntityId", "-"))

        # dataComparison from API may be a JSON string or a list
        raw_comparison = details.get("dataComparison", "")
        data_comparison = []
        if raw_comparison:
            if isinstance(raw_comparison, list):
                data_comparison = raw_comparison
            elif isinstance(raw_comparison, str):
                import json as _json
                try:
                    parsed = _json.loads(raw_comparison)
                    if isinstance(parsed, list):
                        data_comparison = parsed
                except (ValueError, TypeError):
                    pass

        entity_ids = [data.get("firstEntityId", ""), data.get("secondEntityId", "")]
        records.append({
            "id": entity_ids[0],
            "identifier": first_id,
            "label": tr("page.comparison.first_record"),
        })
        records.append({
            "id": entity_ids[1],
            "identifier": second_id,
            "label": tr("page.comparison.second_record"),
        })

        # Extract national IDs for person duplicates
        person_national_ids = []
        if is_person:
            if data_comparison:
                for dc in data_comparison[:2]:
                    comp = dc if isinstance(dc, dict) else {}
                    if isinstance(dc, list):
                        comp = {}
                        for fi in dc:
                            if isinstance(fi, dict):
                                comp[fi.get("fieldName", "")] = fi.get("value", "")
                    nid = comp.get("nationalId", comp.get("nationalID", ""))
                    person_national_ids.append(str(nid) if nid else "")
            else:
                for eid in entity_ids:
                    p = _fetched_persons.get(eid, {})
                    nid = p.get("nationalId", "") if p else ""
                    person_national_ids.append(str(nid) if nid else "")

        for idx, record in enumerate(records):
            row = QHBoxLayout()
            row.setSpacing(16)
            row.setContentsMargins(0, 0, 0, 0)

            radio = QRadioButton()
            radio.setStyleSheet(RADIO_STYLE)
            self.claim_radio_group.addButton(radio, idx)
            if idx == 0:
                radio.setChecked(True)
            row.addWidget(radio)

            icon_name = "blue" if not is_person else "yelow"

            # For person duplicates: show national ID as subtitle
            subtitle = ""
            if is_person and idx < len(person_national_ids) and person_national_ids[idx]:
                subtitle = person_national_ids[idx]

            claim_card_data = {
                "claim_id": record["identifier"],
                "claimant_name": record["label"],
                "date": data.get("detectedDate", "").split("T")[0] if "T" in str(data.get("detectedDate", "")) else "",
                "governorate_name_ar": subtitle if is_person else self._current_conflict_type,
                "district_name_ar": "",
                "subdistrict_name_ar": "",
                "neighborhood_name_ar": "",
                "building_id": record["id"],
                "unit_number": "",
            }

            claim_card = ClaimListCard(claim_card_data, icon_name=icon_name)
            claim_card.setFixedHeight(112)
            row.addWidget(claim_card, 1)

            self._claims_rows_layout.addLayout(row)

        # --- Populate comparison section ---
        self._clear_layout(self._comparison_cards_layout)

        if is_person:
            # Person duplicates: use already-fetched data (no additional blocking)
            comparison_dicts = []
            for idx, record in enumerate(records):
                person_dto = _fetched_persons.get(record["id"])
                if person_dto:
                    comparison_dicts.append(self._map_person_to_comparison_dict(person_dto))
                elif data_comparison and idx < len(data_comparison):
                    dc = data_comparison[idx]
                    comp_dict = {}
                    if isinstance(dc, dict):
                        if "fieldName" in dc:
                            comp_dict[dc.get("fieldName", "")] = str(dc.get("value", "-"))
                        else:
                            comp_dict = dc
                    elif isinstance(dc, list):
                        for field_item in dc:
                            if isinstance(field_item, dict):
                                key = field_item.get("fieldName", "")
                                val = field_item.get("value", "-")
                                comp_dict[key] = str(val) if val else "-"
                    comparison_dicts.append(self._map_person_to_comparison_dict(comp_dict))
                else:
                    logger.warning(f"Person {record['id']} not available")
                    comparison_dicts.append(self._map_person_to_comparison_dict({}))

            diff_fields = self._compute_person_diff_fields(comparison_dicts)

            for comp_dict in comparison_dicts:
                outer_card = self._build_outer_comparison_card(comp_dict, diff_fields)
                self._comparison_cards_layout.addWidget(outer_card, 1)
        else:
            # Property duplicates: fetch units asynchronously
            record_ids = [r["id"] for r in records]
            self._pending_data_comparison = data_comparison
            self._property_units_worker = ApiWorker(
                self._fetch_all_property_units, record_ids
            )
            self._property_units_worker.finished.connect(self._on_property_units_loaded)
            self._property_units_worker.error.connect(self._on_property_units_error)
            self._spinner.show_loading(tr("component.loading.default"))
            self._property_units_worker.start()

    def _fetch_all_property_units(self, record_ids):
        """Fetch all property unit data for comparison (runs in worker thread)."""
        from services.api_client import get_api_client
        api = get_api_client()
        results = []
        for entity_id in record_ids:
            if not entity_id:
                results.append({})
                continue
            try:
                unit_dto = api.get_property_unit_by_id(entity_id)
                if not unit_dto:
                    results.append({})
                    continue
                building_id = unit_dto.get("buildingId", unit_dto.get("building_id", ""))
                if building_id:
                    try:
                        building_dto = api.get_building_by_id(building_id)
                        if building_dto:
                            unit_dto["_building"] = building_dto
                    except Exception as be:
                        logger.warning(f"Failed to fetch building {building_id}: {be}")
                results.append(unit_dto)
            except Exception as e:
                logger.error(f"Failed to fetch property unit {entity_id}: {e}")
                results.append({})
        return results

    def _on_property_units_loaded(self, unit_dtos):
        """Handle property unit data loaded from API."""
        self._spinner.hide_loading()
        data_comparison = getattr(self, '_pending_data_comparison', [])
        comparison_dicts = []

        for idx, unit_dto in enumerate(unit_dtos):
            if unit_dto:
                building_data = unit_dto.get("_building", {})
                comparison_dicts.append(self._map_to_comparison_dict(
                    building_data or unit_dto, unit_dto
                ))
            elif data_comparison and idx < len(data_comparison):
                dc = data_comparison[idx]
                comp_dict = dc if isinstance(dc, dict) else {}
                if isinstance(dc, list):
                    comp_dict = {}
                    for fi in dc:
                        if isinstance(fi, dict):
                            comp_dict[fi.get("fieldName", "")] = str(fi.get("value", "-"))
                comparison_dicts.append(self._map_to_comparison_dict(comp_dict, comp_dict))
            else:
                logger.warning(f"Property unit at index {idx} not available")
                comparison_dicts.append(self._map_to_comparison_dict({}, {}))

        diff_fields = self._compute_comparison_diff_fields(comparison_dicts)

        self._clear_layout(self._comparison_cards_layout)
        for comp_dict in comparison_dicts:
            outer_card = self._build_outer_comparison_card(comp_dict, diff_fields)
            self._comparison_cards_layout.addWidget(outer_card, 1)

    def _on_property_units_error(self, error_msg):
        """Handle property unit fetch error."""
        self._spinner.hide_loading()
        logger.error(f"Failed to fetch property units: {error_msg}")

    def update_language(self, is_arabic: bool):
        self._header_title.setText(tr("page.comparison.title"))
        self._breadcrumb.setText(tr("page.comparison.breadcrumb"))
        self.action_btn.setText(tr("page.comparison.execute"))
        self._doc_load_btn.setText(tr("page.comparison.load_comparison"))
        self._doc_empty_label.setText(tr("page.comparison.click_load_comparison"))
