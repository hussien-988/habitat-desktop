# -*- coding: utf-8 -*-
"""
Relation Step - Step 5 of Office Survey Wizard.

Allows user to:
- Link persons to units with relations
- Define relation type and ownership details
- Upload evidence documents
"""

from typing import Dict, Any, List
import uuid
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QDateEdit,
    QDoubleSpinBox, QLineEdit, QTextEdit, QFrame, QGridLayout, QButtonGroup,
    QRadioButton, QFileDialog, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt, QDate

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from app.config import Config
from utils.logger import get_logger
from ui.components.toast import Toast

logger = get_logger(__name__)


class RelationStep(BaseStep):
    """Step 5: Relations & Evidence."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._editing_relation_index = None
        self._current_relation_evidences = []
        self._relation_file_paths = []
        self._person_cards = []  # Store references to person card widgets

    def setup_ui(self):
        """Setup the step's UI with scrollable person cards."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        outer = self.main_layout
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        # Header (title + subtitle)
        title_box = QVBoxLayout()
        title = QLabel("العلاقة والأدلة")
        title.setStyleSheet("color: #111827; font-weight: 700; font-size: 16px;")
        subtitle = QLabel("تسجيل تفاصيل ملكية شخص للوحدة عقارية")
        subtitle.setStyleSheet("color: #6B7280; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout = QHBoxLayout()
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        outer.addLayout(header_layout)

        # Scroll Area for person cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f4f7f9;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)

        # Container widget for cards
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #f4f7f9;")
        self.cards_layout = QVBoxLayout(scroll_widget)
        self.cards_layout.setSpacing(15)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(scroll_widget)
        outer.addWidget(scroll_area)

        # Initially populate with persons from context
        self._populate_person_cards()

    def _populate_person_cards(self):
        """Create a card for each person from step 4."""
        # Clear existing cards
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self._person_cards.clear()

        # Get persons from context
        persons = self.context.persons if hasattr(self.context, 'persons') else []

        if not persons:
            # Show message if no persons
            no_person_label = QLabel("لا توجد أشخاص. الرجاء إضافة أشخاص في الخطوة السابقة.")
            no_person_label.setStyleSheet("color: #6B7280; font-size: 14px; padding: 20px;")
            no_person_label.setAlignment(Qt.AlignCenter)
            self.cards_layout.addWidget(no_person_label)
            return

        # Create a card for each person
        for person in persons:
            card = self._create_person_card(person)
            self.cards_layout.addWidget(card)
            self._person_cards.append(card)

        # Add stretch at the end
        self.cards_layout.addStretch()

    def _create_person_card(self, person: Dict[str, Any]) -> QFrame:
        """Create a single person relation card based on the provided design."""
        # Main card container
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-top: 2px solid #3498db;
                border-radius: 4px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 20, 30, 30)
        card_layout.setSpacing(10)

        # Header with person info and icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # Icon
        icon_label = QLabel("👤")
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #f0f7ff;
                border-radius: 19px;
                border: 1px solid #d1e3f8;
                color: #3498db;
                font-size: 18px;
            }
        """)

        # Person name and status
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(0)

        full_name = f"{person.get('first_name', '')} {person.get('father_name', '')} {person.get('last_name', '')}"
        name_label = QLabel(full_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")

        status = person.get('relationship_type', 'غير محدد')
        status_label = QLabel(status)
        status_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")

        text_vbox.addWidget(name_label)
        text_vbox.addWidget(status_label)

        header_layout.addWidget(icon_label)
        header_layout.addLayout(text_vbox)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)

        # Form grid
        grid = QGridLayout()
        grid.setSpacing(15)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        label_style = "color: #333; font-size: 12px; font-weight: 600;"
        input_style = """
            QLineEdit, QComboBox, QDateEdit {
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                padding: 8px;
                background-color: #ffffff;
                color: #2d3436;
            }
        """

        # Row 1 - Labels
        grid.addWidget(self._create_label("نوع العقد", label_style), 0, 0)
        grid.addWidget(self._create_label("نوع العلاقة", label_style), 0, 1)
        grid.addWidget(self._create_label("تاريخ بدء العلاقة", label_style), 0, 2)

        # Row 1 - Inputs
        contract_type = QComboBox()
        contract_type.addItems(["اختر", "عقد إيجار", "عقد بيع", "عقد شراكة"])
        contract_type.setStyleSheet(input_style)
        grid.addWidget(contract_type, 1, 0)

        relation_type = QComboBox()
        rel_types = [
            ("owner", "مالك"),
            ("co_owner", "شريك في الملكية"),
            ("tenant", "مستأجر"),
            ("occupant", "شاغل"),
            ("heir", "وارث"),
            ("guardian", "ولي/وصي"),
            ("other", "أخرى")
        ]
        relation_type.addItem("اختر", None)
        for code, ar in rel_types:
            relation_type.addItem(ar, code)
        relation_type.setStyleSheet(input_style)
        grid.addWidget(relation_type, 1, 1)

        start_date = QDateEdit()
        start_date.setCalendarPopup(True)
        start_date.setDate(QDate.currentDate())
        start_date.setStyleSheet(input_style)
        grid.addWidget(start_date, 1, 2)

        # Row 2 - Labels
        grid.addWidget(self._create_label("حصة الملكية", label_style), 2, 0)
        grid.addWidget(self._create_label("نوع الدليل", label_style), 2, 1)
        grid.addWidget(self._create_label("وصف الدليل", label_style), 2, 2)

        # Row 2 - Inputs
        ownership_share = QLineEdit("0")
        ownership_share.setStyleSheet(input_style)
        grid.addWidget(ownership_share, 3, 0)

        evidence_type = QComboBox()
        evidence_type.addItems(["اختر", "صك", "عقد", "وكالة", "إقرار"])
        evidence_type.setStyleSheet(input_style)
        grid.addWidget(evidence_type, 3, 1)

        evidence_desc = QLineEdit("-")
        evidence_desc.setStyleSheet(input_style)
        grid.addWidget(evidence_desc, 3, 2)

        card_layout.addLayout(grid)

        # Notes section
        notes_label = self._create_label("ادخل ملاحظاتك", label_style)
        card_layout.addWidget(notes_label)

        notes = QTextEdit("-")
        notes.setMaximumHeight(70)
        notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                padding: 8px;
                background-color: #ffffff;
                color: #2d3436;
            }
        """)
        card_layout.addWidget(notes)

        # Documents section
        docs_label = self._create_label("صور المستندات", label_style)
        card_layout.addWidget(docs_label)

        radio_layout = QHBoxLayout()
        rb_has = QRadioButton("يوجد مستندات")
        rb_none = QRadioButton("لا يوجد مستندات")
        rb_has.setChecked(True)

        radio_layout.addWidget(rb_has)
        radio_layout.addWidget(rb_none)
        radio_layout.addStretch()
        card_layout.addLayout(radio_layout)

        # Upload box
        upload_box = QFrame()
        upload_box.setStyleSheet("""
            QFrame {
                border: 1px dashed #b2bec3;
                border-radius: 6px;
                background-color: #fdfdfd;
                min-height: 60px;
            }
        """)
        upload_layout = QVBoxLayout(upload_box)
        upload_text = QLabel("ارفع صور المستندات")
        upload_text.setAlignment(Qt.AlignCenter)
        upload_text.setStyleSheet("color: #3498db; font-weight: bold; background: transparent;")
        upload_layout.addWidget(upload_text)
        card_layout.addWidget(upload_box)

        # Store references to widgets for data retrieval
        card.person_data = person
        card.contract_type = contract_type
        card.relation_type = relation_type
        card.start_date = start_date
        card.ownership_share = ownership_share
        card.evidence_type = evidence_type
        card.evidence_desc = evidence_desc
        card.notes = notes

        return card

    def _create_label(self, text: str, style: str) -> QLabel:
        """Helper to create styled label."""
        label = QLabel(text)
        label.setStyleSheet(style)
        return label

    def _collect_relations_from_cards(self) -> List[Dict[str, Any]]:
        """Collect relation data from all person cards."""
        relations = []

        for card in self._person_cards:
            person_data = card.person_data

            # Get relationship type
            rel_type_idx = card.relation_type.currentIndex()
            if rel_type_idx <= 0:  # Skip if not selected
                continue

            relation = {
                "relation_id": str(uuid.uuid4()),
                "person_id": person_data.get('person_id'),
                "person_name": f"{person_data.get('first_name', '')} {person_data.get('last_name', '')}",
                "relation_type": card.relation_type.currentData() if hasattr(card.relation_type, 'currentData') else None,
                "ownership_share": float(card.ownership_share.text()) if card.ownership_share.text() and card.ownership_share.text() != "0" else 0.0,
                "start_date": card.start_date.date().toString("yyyy-MM-dd"),
                "contract_type": card.contract_type.currentText() if card.contract_type.currentIndex() > 0 else None,
                "evidence_type": card.evidence_type.currentText() if card.evidence_type.currentIndex() > 0 else None,
                "evidence_description": card.evidence_desc.text().strip() or None,
                "notes": card.notes.toPlainText().strip() or None,
                "evidences": []
            }

            relations.append(relation)

        return relations

    def validate(self) -> StepValidationResult:
        """Validate the step."""
        result = self.create_validation_result()

        # Collect relations from cards
        relations = self._collect_relations_from_cards()

        # Check if at least one relation exists
        if len(relations) == 0:
            result.add_error("يجب تسجيل علاقة واحدة على الأقل")

        # Store in context
        self.context.relations = relations

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect data from the step."""
        # Collect relations from all cards
        relations = self._collect_relations_from_cards()
        self.context.relations = relations

        return {
            "relations": relations,
            "relations_count": len(relations)
        }

    def populate_data(self):
        """Populate the step with data from context."""
        # Refresh person cards when data changes
        self._populate_person_cards()

    def on_show(self):
        """Called when step is shown."""
        super().on_show()
        # Refresh person cards when step is shown
        self._populate_person_cards()

    def get_step_title(self) -> str:
        """Get step title."""
        return "العلاقات والأدلة"

    def get_step_description(self) -> str:
        """Get step description."""
        return "تسجيل تفاصيل ملكية شخص للوحدة عقارية"
