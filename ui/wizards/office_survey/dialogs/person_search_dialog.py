# -*- coding: utf-8 -*-
"""
PersonSearchDialog - Search and select an existing registered person.

Shows the current survey applicant at the top (from context.applicant),
then a searchable list of all persons from the API.
"""

from typing import Optional, Dict, Any, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QWidget,
    QGraphicsDropShadowEffect, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from services.translation_manager import tr
from utils.logger import get_logger

logger = get_logger(__name__)

_SECTION_LABEL_STYLE = (
    "font-size: 11px; font-weight: 700; color: #94A3B8; "
    "background: transparent; letter-spacing: 0.5px;"
)
_NAME_STYLE = "font-size: 13px; font-weight: 600; color: #1E293B; background: transparent;"
_ID_STYLE = "font-size: 11px; color: #64748B; background: transparent;"


class PersonSearchDialog(QDialog):
    """Search and select an existing person — contacts applicant shown at top."""

    def __init__(
        self,
        api_client,
        contact_person: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._api_client = api_client
        self._contact_person = contact_person
        self._auth_token = auth_token
        self._all_persons: List[Dict[str, Any]] = []
        self._selected_person: Optional[Dict[str, Any]] = None

        self.setModal(True)
        self.setFixedSize(544, 600)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()

        # Defer API load so dialog renders first
        QTimer.singleShot(100, self._load_persons)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("SearchCard")
        card.setStyleSheet("""
            QFrame#SearchCard {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#SearchCard QLabel,
            QFrame#SearchCard QCheckBox {
                background-color: transparent;
            }
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        main = QVBoxLayout(card)
        main.setContentsMargins(24, 24, 24, 24)
        main.setSpacing(14)

        # Title
        title = QLabel(tr("person_search.title"))
        title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #2c3e50; background: transparent;"
        )
        main.addWidget(title)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet("border: none; background-color: #E8ECF0;")
        main.addWidget(div)

        # Search field
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText(tr("person_search.search_placeholder"))
        self._search_field.setStyleSheet("""
            QLineEdit {
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px 12px;
                background-color: #F0F7FF;
                color: #333;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #4A90E2; }
        """)
        self._search_field.textChanged.connect(self._on_search_changed)
        main.addWidget(self._search_field)

        # Scroll area for results
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        main.addWidget(scroll, 1)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton(tr("common.cancel") if self._tr_exists("common.cancel") else "إلغاء")
        cancel_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px 20px;
                background: #F8FAFC;
                color: #64748B;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #F1F5F9; }
        """)
        cancel_btn.clicked.connect(self.reject)

        self._confirm_btn = QPushButton(tr("person_search.confirm"))
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                background: #4A90E2;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #357ABD; }
            QPushButton:disabled { background: #B0C4DE; color: #FFFFFF; }
        """)
        self._confirm_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._confirm_btn)
        main.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_persons(self):
        """Load persons from API. Shows applicant at top, then all persons."""
        self._clear_list()

        # Contact person section (from context.applicant)
        if self._contact_person:
            self._add_section_label(tr("person_search.current_applicant"))
            self._add_person_card(self._contact_person, is_applicant=True)

        # All persons section
        self._add_section_label(tr("person_search.registered_persons"))

        loading = QLabel(tr("wizard.person_dialog.loading_docs"))
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet("color: #94A3B8; font-size: 12px; background: transparent; padding: 16px;")
        self._list_layout.insertWidget(self._list_layout.count() - 1, loading)

        try:
            if self._api_client and self._auth_token:
                self._api_client.set_access_token(self._auth_token)
            response = self._api_client.get_persons(page=1, page_size=100) if self._api_client else {}
            items = response.get("items", []) if isinstance(response, dict) else []
            self._all_persons = items
        except Exception as e:
            logger.error(f"Failed to load persons: {e}")
            self._all_persons = []

        loading.deleteLater()
        self._render_persons(self._all_persons)

    def _render_persons(self, persons: List[Dict[str, Any]]):
        """Clear and re-render the persons list."""
        # Remove all non-section, non-stretch items after contact card section
        # Simply clear and rebuild from scratch each time search changes
        self._clear_list(keep_applicant=True)

        if not persons:
            no_result = QLabel(tr("person_search.no_results"))
            no_result.setAlignment(Qt.AlignCenter)
            no_result.setStyleSheet(
                "color: #94A3B8; font-size: 12px; background: transparent; padding: 16px;"
            )
            self._list_layout.insertWidget(self._list_layout.count() - 1, no_result)
            return

        for p in persons:
            self._add_person_card(p, is_applicant=False)

    # ------------------------------------------------------------------
    # List helpers
    # ------------------------------------------------------------------

    def _clear_list(self, keep_applicant: bool = False):
        """Remove all widgets from the list layout."""
        while self._list_layout.count() > 1:  # keep stretch at end
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not keep_applicant and self._contact_person:
            # Re-add applicant section
            self._add_section_label(tr("person_search.current_applicant"))
            self._add_person_card(self._contact_person, is_applicant=True)
        self._add_section_label(tr("person_search.registered_persons"))

    def _add_section_label(self, text: str):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(_SECTION_LABEL_STYLE)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._list_layout.insertWidget(self._list_layout.count() - 1, lbl)

    def _add_person_card(self, person: Dict[str, Any], is_applicant: bool):
        """Create a clickable card for one person."""
        card = QFrame()
        card.setObjectName("PersonCard")
        card.setCursor(Qt.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        base_style = """
            QFrame#PersonCard {
                border-radius: 10px;
                padding: 2px;
            }
        """
        applicant_style = "background-color: #EFF6FF; border: 1px solid #BFDBFE;"
        default_style = "background-color: #F8FAFC; border: 1px solid #E2E8F0;"
        selected_style = "background-color: #DBEAFE; border: 2px solid #3B82F6;"

        card.setStyleSheet(base_style + (applicant_style if is_applicant else default_style))
        card._person_data = person
        card._is_selected = False
        card._base_style = base_style + (applicant_style if is_applicant else default_style)
        card._selected_style = base_style + selected_style

        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name = self._build_full_name(person)
        name_lbl = QLabel(name or "—")
        name_lbl.setStyleSheet(_NAME_STYLE)
        name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        nid = person.get("nationalId") or person.get("national_id", "")
        nid_lbl = QLabel(f"رقم وطني: {nid}" if nid else "بدون رقم وطني")
        nid_lbl.setStyleSheet(_ID_STYLE)
        nid_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        text_col.addWidget(name_lbl)
        text_col.addWidget(nid_lbl)
        layout.addLayout(text_col)
        layout.addStretch()

        if is_applicant:
            tag = QLabel("مقدم الطلب")
            tag.setStyleSheet("""
                QLabel {
                    background-color: #3B82F6; color: white;
                    border-radius: 4px; padding: 2px 8px;
                    font-size: 10px; font-weight: 600;
                }
            """)
            layout.addWidget(tag)

        card.mousePressEvent = lambda e, c=card: self._on_card_clicked(c)
        self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _on_card_clicked(self, clicked_card: QFrame):
        """Deselect all cards, select the clicked one."""
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QFrame):
                w = item.widget()
                if hasattr(w, '_is_selected'):
                    w._is_selected = False
                    w.setStyleSheet(w._base_style)

        clicked_card._is_selected = True
        clicked_card.setStyleSheet(clicked_card._selected_style)
        self._selected_person = clicked_card._person_data
        self._confirm_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str):
        text = text.strip().lower()
        if not text:
            self._render_persons(self._all_persons)
            return

        filtered = [
            p for p in self._all_persons
            if text in self._build_full_name(p).lower()
            or text in (p.get("nationalId") or p.get("national_id", "")).lower()
        ]
        self._render_persons(filtered)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_full_name(person: Dict[str, Any]) -> str:
        parts = [
            person.get("firstNameArabic") or person.get("first_name_ar", ""),
            person.get("fatherNameArabic") or person.get("father_name_ar", ""),
            person.get("familyNameArabic") or person.get("last_name_ar", ""),
        ]
        return " ".join(p for p in parts if p)

    @staticmethod
    def _tr_exists(key: str) -> bool:
        try:
            from services.translation_manager import tr
            val = tr(key)
            return val != key
        except Exception:
            return False

    def get_selected_person(self) -> Optional[Dict[str, Any]]:
        """Return the selected person dict, or None."""
        return self._selected_person
