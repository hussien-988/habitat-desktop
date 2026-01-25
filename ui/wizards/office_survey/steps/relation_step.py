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
        """Setup the step's UI - matching person_step styling."""
        from ui.font_utils import FontManager, create_font
        from ui.design_system import Colors
        from ui.components.icon import Icon

        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        # Set main window background color
        widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        # Match person_step margins: No horizontal padding - wizard handles it
        # Only vertical spacing for step content
        layout.setContentsMargins(0, 15, 0, 16)  # Top: 15px, Bottom: 16px
        layout.setSpacing(15)  # Unified spacing: 15px between cards

        # --- The Main Card (QFrame) - matching person_step card styling ---
        main_card = QFrame()
        main_card.setObjectName("relationsCard")
        main_card.setLayoutDirection(Qt.RightToLeft)
        main_card.setStyleSheet(f"""
            QFrame#relationsCard {{
                background-color: {Colors.SURFACE};
                border-radius: 12px;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        main_card_layout = QVBoxLayout(main_card)
        main_card_layout.setContentsMargins(12, 12, 12, 12)  # Match person_step: 12px padding
        main_card_layout.setSpacing(12)  # Match person_step: 12px spacing

        # --- Header with Title and Icon (inside the card) ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Title text container
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)  # Match person_step spacing
        title_label = QLabel("العلاقة والأدلة")
        # Title: 14px from Figma = 10pt, weight 600, color WIZARD_TITLE
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        subtitle_label = QLabel("تسجيل تفاصيل ملكية شخص للوحدة عقارية")
        # Subtitle: 14px from Figma = 10pt, weight 400, color WIZARD_SUBTITLE
        subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        subtitle_label.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(subtitle_label)

        # Icon for title
        title_icon = QLabel()
        title_icon.setFixedSize(40, 40)
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        # Load user-account.png icon using Icon.load_pixmap
        relation_icon_pixmap = Icon.load_pixmap("user-account", size=24)
        if relation_icon_pixmap and not relation_icon_pixmap.isNull():
            title_icon.setPixmap(relation_icon_pixmap)
        else:
            # Fallback if image not found
            title_icon.setText("👥")
            title_icon.setStyleSheet(title_icon.styleSheet() + "font-size: 16px;")

        # Assemble title group (icon first in code = rightmost visually in RTL)
        header_layout.addWidget(title_icon)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        main_card_layout.addLayout(header_layout)
        # Gap: 12px between header and content
        main_card_layout.addSpacing(12)

        # Scroll Area for person cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
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
        scroll_widget.setLayoutDirection(Qt.RightToLeft)
        scroll_widget.setStyleSheet("background-color: transparent;")
        self.cards_layout = QVBoxLayout(scroll_widget)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(scroll_widget)
        main_card_layout.addWidget(scroll_area)

        layout.addWidget(main_card)
        layout.addStretch()

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
        from ui.design_system import Colors

        # Main card container - matching person_step card background
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(12)

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

        # Import StyleManager for shared styles
        from ui.style_manager import StyleManager

        label_style = "color: #333; font-size: 12px; font-weight: 600;"

        # Row 1 - Labels
        grid.addWidget(self._create_label("نوع العقد", label_style), 0, 0)
        grid.addWidget(self._create_label("نوع العلاقة", label_style), 0, 1)
        grid.addWidget(self._create_label("تاريخ بدء العلاقة", label_style), 0, 2)

        # Row 1 - Inputs - Using StyleManager for consistent styling
        contract_type = QComboBox()
        contract_type.addItems(["اختر", "عقد إيجار", "عقد بيع", "عقد شراكة"])
        contract_type.setStyleSheet(StyleManager.form_input())
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
        relation_type.setStyleSheet(StyleManager.form_input())
        grid.addWidget(relation_type, 1, 1)

        start_date = QDateEdit()
        start_date.setCalendarPopup(True)
        start_date.setDate(QDate.currentDate())
        start_date.setDisplayFormat("yyyy-MM-dd")
        start_date.setStyleSheet(StyleManager.date_input())
        grid.addWidget(start_date, 1, 2)

        # Row 2 - Labels
        grid.addWidget(self._create_label("حصة الملكية", label_style), 2, 0)
        grid.addWidget(self._create_label("نوع الدليل", label_style), 2, 1)
        grid.addWidget(self._create_label("وصف الدليل", label_style), 2, 2)

        # Row 2 - Inputs - Using StyleManager for consistent styling
        ownership_share = QLineEdit("0")
        ownership_share.setStyleSheet(StyleManager.form_input())
        grid.addWidget(ownership_share, 3, 0)

        evidence_type = QComboBox()
        evidence_type.addItems(["اختر", "صك", "عقد", "وكالة", "إقرار"])
        evidence_type.setStyleSheet(StyleManager.form_input())
        grid.addWidget(evidence_type, 3, 1)

        evidence_desc = QLineEdit("-")
        evidence_desc.setStyleSheet(StyleManager.form_input())
        grid.addWidget(evidence_desc, 3, 2)

        card_layout.addLayout(grid)

        # Pre-fill form fields with relation data from person dialog Tab 2
        relation_data = person.get('relation_data', {})

        # Pre-fill contract type
        if relation_data.get('contract_type'):
            idx = contract_type.findText(relation_data['contract_type'])
            if idx >= 0:
                contract_type.setCurrentIndex(idx)

        # Pre-fill relation type from relation_data (priority) or relationship_type
        rel_type_value = relation_data.get('rel_type') or person.get('relationship_type')
        if rel_type_value:
            for i in range(relation_type.count()):
                if relation_type.itemData(i) == rel_type_value:
                    relation_type.setCurrentIndex(i)
                    break

        # Pre-fill start date
        if relation_data.get('start_date'):
            date = QDate.fromString(relation_data['start_date'], 'yyyy-MM-dd')
            if date.isValid():
                start_date.setDate(date)

        # Pre-fill ownership share
        if relation_data.get('ownership_share') is not None:
            ownership_share.setText(str(relation_data['ownership_share']))

        # Pre-fill evidence type
        if relation_data.get('evidence_type'):
            idx = evidence_type.findText(relation_data['evidence_type'])
            if idx >= 0:
                evidence_type.setCurrentIndex(idx)

        # Pre-fill evidence description
        if relation_data.get('evidence_desc'):
            evidence_desc.setText(relation_data['evidence_desc'])

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

        # Pre-fill notes
        if relation_data.get('notes'):
            notes.setPlainText(relation_data['notes'])

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

        # Upload box - Using StyleManager for consistent styling
        upload_box = QFrame()
        upload_box.setCursor(Qt.PointingHandCursor)
        upload_box.setStyleSheet(StyleManager.file_upload_frame())

        upload_layout = QVBoxLayout(upload_box)
        upload_layout.setContentsMargins(20, 15, 20, 15)
        upload_layout.setAlignment(Qt.AlignCenter)
        upload_layout.setSpacing(5)

        # Upload icon
        from ui.components.icon import Icon
        upload_icon = QLabel()
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("border: none;")
        upload_pixmap = Icon.load_pixmap("upload_file", size=24)
        if upload_pixmap and not upload_pixmap.isNull():
            upload_icon.setPixmap(upload_pixmap)
        else:
            upload_icon.setText("📁")
            upload_icon.setStyleSheet("border: none; font-size: 20px;")
        upload_layout.addWidget(upload_icon)

        # Upload button
        upload_btn = QPushButton("ارفع صور المستندات")
        upload_btn.setStyleSheet(StyleManager.file_upload_button())
        upload_layout.addWidget(upload_btn)

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
