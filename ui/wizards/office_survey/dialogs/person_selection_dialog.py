# -*- coding: utf-8 -*-
"""
PersonSelectionDialog - Select a person to add: applicant, existing unit person, or new.

Shows the applicant at the top (if not already added), then existing persons
linked to this unit from the API with their relation type, and finally
a "new person" option.
"""

from typing import Optional, Dict, Any, List

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QWidget,
    QGraphicsDropShadowEffect, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from services.display_mappings import get_relation_type_display
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger

logger = get_logger(__name__)

_NAME_STYLE = "font-size: 13px; font-weight: 600; color: #1E293B; background: transparent;"
_ID_STYLE = "font-size: 11px; color: #64748B; background: transparent;"
_SECTION_LABEL_STYLE = (
    "font-size: 11px; font-weight: 700; color: #94A3B8; "
    "background: transparent; letter-spacing: 0.5px;"
)


class PersonSelectionDialog(QDialog):
    """Dialog to choose between applicant, existing unit persons, or new person."""

    def __init__(
        self,
        applicant: Optional[Dict[str, Any]] = None,
        existing_persons: Optional[List[Dict[str, Any]]] = None,
        already_added_ids: Optional[List[str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._applicant = applicant
        self._existing_persons = existing_persons or []
        self._already_added_ids = set(already_added_ids or [])
        self._selection: Optional[Dict[str, Any]] = None

        self.setModal(True)
        self.setFixedSize(544, 520)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")
        self.setLayoutDirection(get_layout_direction())

        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("SelectionCard")
        card.setStyleSheet("""
            QFrame#SelectionCard {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#SelectionCard QLabel {
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
        title = QLabel(tr("person_selection.title"))
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

        # Scroll area
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

        self._populate_choices()

        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        main.addWidget(scroll, 1)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton(tr("common.cancel"))
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

        self._confirm_btn = QPushButton(tr("common.confirm"))
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

    def _populate_choices(self):
        """Build the list of selectable person cards."""
        base_card_style = """
            QFrame#PersonCard {
                border-radius: 10px;
                padding: 2px;
            }
        """
        selected_style = base_card_style + "background-color: #DBEAFE; border: 2px solid #3B82F6;"

        # Applicant card
        if self._applicant:
            self._add_section_label(tr("person_selection.applicant"))
            applicant_style = base_card_style + "background-color: #EFF6FF; border: 1px solid #BFDBFE;"
            name = " ".join(filter(None, [
                self._applicant.get('first_name_ar', ''),
                self._applicant.get('father_name_ar', ''),
                self._applicant.get('last_name_ar', ''),
            ]))
            nid = self._applicant.get('national_id', '')
            card = self._create_card(
                name=name or "—",
                subtitle=tr("person_selection.national_id_label", nid=nid) if nid else "",
                badge_text=tr("person_selection.applicant"),
                badge_bg="#3B82F6",
                style=applicant_style,
                selected_style=selected_style,
                selection_data={'type': 'applicant', 'person_data': None, 'relation_data': None},
            )
            self._list_layout.addWidget(card)

        # Existing persons linked to the unit
        available = [
            p for p in self._existing_persons
            if p.get('person_id') not in self._already_added_ids
        ]
        if available:
            self._add_section_label(tr("person_selection.linked_persons"))
            default_style = base_card_style + "background-color: #F8FAFC; border: 1px solid #E2E8F0;"
            for p in available:
                name = " ".join(filter(None, [
                    p.get('first_name', ''),
                    p.get('father_name', ''),
                    p.get('last_name', ''),
                ]))
                rel_type = p.get('person_role') or p.get('relationship_type') or p.get('relation_type')
                rel_display = get_relation_type_display(rel_type) if rel_type else ""
                badge_bg = "#10B981" if rel_type in (1, 5) else "#F59E0B" if rel_type == 3 else "#6B7280"
                card = self._create_card(
                    name=name or "—",
                    subtitle=tr("person_selection.national_id_label", nid=p.get('national_id', '')) if p.get('national_id') else "",
                    badge_text=rel_display,
                    badge_bg=badge_bg,
                    style=default_style,
                    selected_style=selected_style,
                    selection_data={'type': 'existing', 'person_data': p, 'relation_data': None},
                )
                self._list_layout.addWidget(card)

        # "New person" option
        self._add_section_label("")
        new_style = base_card_style + "background-color: #F0FDF4; border: 1px dashed #86EFAC;"
        new_card = self._create_card(
            name=tr("person_selection.add_new_person"),
            subtitle=tr("person_selection.add_new_person_subtitle"),
            badge_text=None,
            badge_bg=None,
            style=new_style,
            selected_style=selected_style,
            selection_data={'type': 'new', 'person_data': None, 'relation_data': None},
        )
        self._list_layout.addWidget(new_card)

    def _create_card(
        self,
        name: str,
        subtitle: str,
        badge_text: Optional[str],
        badge_bg: Optional[str],
        style: str,
        selected_style: str,
        selection_data: Dict[str, Any],
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("PersonCard")
        card.setCursor(Qt.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setStyleSheet(style)
        card._is_selected = False
        card._base_style = style
        card._selected_style = selected_style
        card._selection_data = selection_data

        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(_NAME_STYLE)
        name_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        text_col.addWidget(name_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(_ID_STYLE)
            sub_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            text_col.addWidget(sub_lbl)

        layout.addLayout(text_col)
        layout.addStretch()

        if badge_text:
            tag = QLabel(badge_text)
            tag.setStyleSheet(f"""
                QLabel {{
                    background-color: {badge_bg}; color: white;
                    border-radius: 4px; padding: 2px 8px;
                    font-size: 10px; font-weight: 600;
                }}
            """)
            layout.addWidget(tag)

        card.mousePressEvent = lambda e, c=card: self._on_card_clicked(c)
        return card

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
        self._selection = clicked_card._selection_data
        self._confirm_btn.setEnabled(True)

    def _add_section_label(self, text: str):
        if not text:
            return
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(_SECTION_LABEL_STYLE)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._list_layout.addWidget(lbl)

    def get_selection(self) -> Optional[Dict[str, Any]]:
        """Return the selection dict: {type, person_data, relation_data}."""
        return self._selection
