# -*- coding: utf-8 -*-
"""
Claim Step - Step 6 of Office Survey Wizard.

Simplified step for creating claims.
Note: This is a simplified implementation.
"""

from typing import Dict, Any
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QGroupBox, QFormLayout,
    QLineEdit, QDateEdit, QGridLayout, QFrame, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt, QDate

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from services.translation_manager import tr
from services.vocab_service import get_options
from utils.logger import get_logger

logger = get_logger(__name__)


def _find_combo_code_by_english(vocab_name: str, english_key: str) -> int:
    """Find the integer code for a vocabulary item by its English label."""
    from services.vocab_service import get_options
    english_key_lower = english_key.lower()
    for code, label in get_options(vocab_name, lang="en"):
        if label.lower() == english_key_lower:
            return code
    return 0


class ClaimStep(BaseStep):
    """Step 6: Claim Creation (Simplified)."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._claim_cards = []  # Store references to claim card widgets

    def setup_ui(self):
        """Setup the step's UI - scrollable claim cards."""
        from ui.style_manager import StyleManager
        from ui.font_utils import FontManager, create_font
        from ui.design_system import Colors
        from ui.components.icon import Icon

        # Store references for later use
        self._StyleManager = StyleManager
        self._FontManager = FontManager
        self._create_font = create_font
        self._Colors = Colors
        self._Icon = Icon

        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        layout.setContentsMargins(0, 15, 0, 16)
        layout.setSpacing(15)

        # Create scroll area for claim cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setLayoutDirection(Qt.RightToLeft)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Colors.BACKGROUND};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {Colors.BACKGROUND};
            }}
        """)

        # Container widget for scroll area
        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_content.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        self.cards_layout = QVBoxLayout(scroll_content)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(15)

        # Create the first (default) claim card
        first_card = self._create_claim_card_widget()
        self.cards_layout.addWidget(first_card)
        self._claim_cards.append(first_card)

        self.cards_layout.addStretch()

        self.scroll_area.setWidget(scroll_content)
        layout.addWidget(self.scroll_area)

        # Create empty state widget (hidden by default)
        self.empty_state_widget = self._create_empty_state_widget()
        self.empty_state_widget.hide()
        layout.addWidget(self.empty_state_widget)

    def _create_empty_state_widget(self) -> QWidget:
        """Create empty state widget shown when no claims are created."""
        from ui.font_utils import FontManager, create_font
        from ui.design_system import Colors
        from ui.components.icon import Icon
        from PyQt5.QtGui import QPixmap

        container = QWidget()
        container.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        # Main layout to center everything
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Center container
        center_container = QWidget()
        center_container.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_container)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(15)

        # 1. Icon with orange circle background
        icon_container = QLabel()
        icon_container.setFixedSize(70, 70)
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet("""
            background-color: #ffcc33;
            border-radius: 35px;
        """)

        # Load icon from assets
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                                  "assets", "images", "tdesign_no-result.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_container.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback: try Icon loader
            no_result_pixmap = Icon.load_pixmap("tdesign_no-result", size=40)
            if no_result_pixmap and not no_result_pixmap.isNull():
                icon_container.setPixmap(no_result_pixmap)
            else:
                icon_container.setText("⚠")
                icon_container.setStyleSheet(icon_container.styleSheet() + "font-size: 28px; color: #1a1a1a;")

        # 2. Main Title (Arabic Text)
        title_label = QLabel("لا توجد مطالبة ملكية على هذا المقسم")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"""
            color: {Colors.WIZARD_TITLE};
            background: transparent;
        """)

        # 3. Description (Arabic Text)
        desc_label = QLabel(
            "لم يتم العثور على أي علاقة ملكية، لذلك لن يتم إنشاء\n"
            "مطالبة، وسيُعتبر العقار بدون أي مطالبات معلّقة"
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_DESC, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet(f"""
            color: {Colors.WIZARD_SUBTITLE};
            background: transparent;
            line-height: 1.5;
        """)

        # Add widgets to the center layout
        center_layout.addWidget(icon_container, alignment=Qt.AlignCenter)
        center_layout.addWidget(title_label)
        center_layout.addWidget(desc_label)

        # Add the center container to the main layout
        main_layout.addWidget(center_container)

        return container

    def _create_claim_card_widget(self, claim_data: Dict[str, Any] = None) -> QFrame:
        """Create a single claim card widget matching the main card design."""
        from ui.style_manager import StyleManager
        from ui.font_utils import FontManager, create_font
        from ui.design_system import Colors
        from ui.components.icon import Icon

        card = QFrame()
        card.setObjectName("ClaimCard")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame#ClaimCard {{
                background-color: {Colors.SURFACE};
                border-radius: 12px;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(12)

        # --- Header with Title and Icon ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        title_label = QLabel("تسجيل الحالة")
        title_label.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        subtitle_label = QLabel("ربط المطالبين بالوحدات العقارية وتتبع مطالبات تسجيل حقوق الحيازة")
        subtitle_label.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        subtitle_label.setAlignment(Qt.AlignRight)
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(subtitle_label)

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
        claim_icon_pixmap = Icon.load_pixmap("elements", size=24)
        if claim_icon_pixmap and not claim_icon_pixmap.isNull():
            title_icon.setPixmap(claim_icon_pixmap)
        else:
            title_icon.setText("📋")
            title_icon.setStyleSheet(title_icon.styleSheet() + "font-size: 16px;")

        header_layout.addWidget(title_icon)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        card_layout.addLayout(header_layout)
        card_layout.addSpacing(12)

        # --- Grid Layout for fields ---
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for i in range(4):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, field_widget, row, col):
            v = QVBoxLayout()
            v.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
            v.addWidget(lbl)
            v.addWidget(field_widget)
            grid.addLayout(v, row, col)

        # Field styles
        from app.config import Config
        ro_bg = "#f0f7ff"
        edit_bg = "#ffffff"
        down_img = str(Config.IMAGES_DIR / "down.png").replace("\\", "/")

        ro_input_style = f"""
            QLineEdit {{
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: {ro_bg};
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
        """
        edit_combo_style = f"""
            QComboBox {{
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: {edit_bg};
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                image: url({down_img});
                width: 12px;
                height: 12px;
            }}
        """
        ro_date_style = f"""
            QDateEdit {{
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: {ro_bg};
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
        """
        edit_date_style = f"""
            QDateEdit {{
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                background-color: {edit_bg};
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
        """

        # Row 1: معرف المطالب | معرف الوحدة المطالب بها | نوع الحالة | طبيعة الأعمال
        claim_person_search = QLineEdit()
        claim_person_search.setPlaceholderText("اسم الشخص")
        claim_person_search.setStyleSheet(ro_input_style)
        claim_person_search.setReadOnly(True)
        add_field("معرف المطالب", claim_person_search, 0, 0)

        claim_unit_search = QLineEdit()
        claim_unit_search.setPlaceholderText("رقم المقسم")
        claim_unit_search.setStyleSheet(ro_input_style)
        claim_unit_search.setReadOnly(True)
        add_field("معرف المقسم المطالب به", claim_unit_search, 0, 1)

        claim_type_combo = QComboBox()
        claim_type_combo.addItem(tr("mapping.select"), 0)
        for code, label in get_options("ClaimType"):
            claim_type_combo.addItem(label, code)
        claim_type_combo.setStyleSheet(edit_combo_style)
        add_field("نوع الحالة", claim_type_combo, 0, 2)

        claim_business_nature = QComboBox()
        claim_business_nature.addItem(tr("mapping.select"), 0)
        for code, label in get_options("BusinessNature"):
            claim_business_nature.addItem(label, code)
        claim_business_nature.setStyleSheet(edit_combo_style)
        add_field("طبيعة الأعمال", claim_business_nature, 0, 3)

        # Row 2: حالة الحالة | المصدر | تاريخ المسح | الأولوية
        claim_status_combo = QComboBox()
        claim_status_combo.addItem(tr("mapping.select"), 0)
        for code, label in get_options("ClaimStatus"):
            claim_status_combo.addItem(label, code)
        claim_status_combo.setStyleSheet(edit_combo_style)
        add_field("حالة الحالة", claim_status_combo, 1, 0)

        claim_source_combo = QComboBox()
        claim_source_combo.addItem(tr("mapping.select"), 0)
        for code, label in get_options("ClaimSource"):
            claim_source_combo.addItem(label, code)
        claim_source_combo.setStyleSheet(edit_combo_style)
        add_field("المصدر", claim_source_combo, 1, 1)

        claim_survey_date = QDateEdit()
        claim_survey_date.setCalendarPopup(False)
        claim_survey_date.setButtonSymbols(QDateEdit.NoButtons)
        claim_survey_date.setDisplayFormat("yyyy-MM-dd")
        claim_survey_date.setDate(QDate.currentDate())
        claim_survey_date.setReadOnly(True)
        claim_survey_date.setStyleSheet(ro_date_style)
        add_field("تاريخ المسح", claim_survey_date, 1, 2)

        claim_priority_combo = QComboBox()
        claim_priority_combo.addItem(tr("mapping.select"), 0)
        for code, label in get_options("CasePriority"):
            claim_priority_combo.addItem(label, code)
        claim_priority_combo.setCurrentIndex(2)
        claim_priority_combo.setStyleSheet(edit_combo_style)
        add_field("الأولوية", claim_priority_combo, 1, 3)

        card_layout.addLayout(grid)
        card_layout.addSpacing(8)

        # Notes Section
        notes_label = QLabel("ملاحظات المراجعة")
        notes_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        notes_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(notes_label)

        claim_notes = QTextEdit()
        claim_notes.setPlaceholderText("ملاحظات إضافية")
        claim_notes.setMinimumHeight(100)
        claim_notes.setMaximumHeight(120)
        claim_notes.setStyleSheet(f"""
            QTextEdit {{
                background-color: {edit_bg};
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 8px;
                color: #333;
                font-size: 14px;
            }}
        """)
        card_layout.addWidget(claim_notes)
        card_layout.addSpacing(8)

        # Next Action Date Section
        next_date_label = QLabel("تاريخ الإجراء التالي")
        next_date_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        next_date_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(next_date_label)

        claim_next_action_date = QDateEdit()
        claim_next_action_date.setCalendarPopup(True)
        claim_next_action_date.setDisplayFormat("yyyy-MM-dd")
        claim_next_action_date.setStyleSheet(edit_date_style)
        card_layout.addWidget(claim_next_action_date)
        card_layout.addSpacing(8)

        # Status Bar - Evidence available indicator (pill shape)
        claim_eval_label = QLabel("✓  الأدلة متوفرة")
        claim_eval_label.setAlignment(Qt.AlignCenter)
        claim_eval_label.setFixedHeight(36)
        claim_eval_label.setFont(create_font(size=FontManager.WIZARD_BADGE, weight=FontManager.WEIGHT_SEMIBOLD))
        claim_eval_label.setStyleSheet("""
            QLabel {
                background-color: #e1f7ef;
                color: #10b981;
                border-radius: 18px;
            }
        """)
        card_layout.addWidget(claim_eval_label)

        # Store widget references in card for later access
        card.claim_person_search = claim_person_search
        card.claim_unit_search = claim_unit_search
        card.claim_type_combo = claim_type_combo
        card.claim_business_nature = claim_business_nature
        card.claim_status_combo = claim_status_combo
        card.claim_source_combo = claim_source_combo
        card.claim_survey_date = claim_survey_date
        card.claim_priority_combo = claim_priority_combo
        card.claim_notes = claim_notes
        card.claim_next_action_date = claim_next_action_date
        card.claim_eval_label = claim_eval_label

        # Populate with claim data if provided
        if claim_data:
            self._populate_card_with_data(card, claim_data)

        return card

    def _populate_card_with_data(self, card: QFrame, claim_data: Dict[str, Any]):
        """Populate a claim card with data from API response."""
        # Claimant name
        claimant_name = claim_data.get('fullNameArabic', '')
        if claimant_name:
            card.claim_person_search.setText(claimant_name)

        # Unit ID
        unit_id = claim_data.get('propertyUnitIdNumber', '')
        if unit_id:
            card.claim_unit_search.setText(unit_id)

        # Relation type -> claim type
        relation_type = claim_data.get('relationType', '').lower()
        if relation_type in ('owner', 'co_owner', 'heir'):
            for i in range(card.claim_type_combo.count()):
                if card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Ownership"):
                    card.claim_type_combo.setCurrentIndex(i)
                    break
        elif relation_type == 'tenant':
            for i in range(card.claim_type_combo.count()):
                if card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Tenancy"):
                    card.claim_type_combo.setCurrentIndex(i)
                    break
        elif relation_type == 'occupant':
            for i in range(card.claim_type_combo.count()):
                if card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Occupancy"):
                    card.claim_type_combo.setCurrentIndex(i)
                    break

        # Survey date
        survey_date_str = claim_data.get('surveyDate', '')
        if survey_date_str:
            try:
                from datetime import datetime
                survey_date = datetime.fromisoformat(survey_date_str.replace('Z', '+00:00'))
                card.claim_survey_date.setDate(QDate(survey_date.year, survey_date.month, survey_date.day))
            except Exception as e:
                logger.warning(f"Failed to parse survey date: {e}")

        # Claim number in status label
        claim_number = claim_data.get('claimNumber', '')
        has_evidence = claim_data.get('hasEvidence', False)

        #if claim_number:
           # card.claim_eval_label.setText(f"تم إنشاء المطالبة: {claim_number}")
          #  card.claim_eval_label.setStyleSheet("""
            #    QLabel {
             #       background-color: #e1f7ef;
             #       color: #10b981;
            #  3      border-radius: 8px;
              #  }
           # """)
        if has_evidence:
            card.claim_eval_label.setText("✓  الأدلة متوفرة")
            card.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #e1f7ef;
                    color: #10b981;
                    border-radius: 18px;
                }
            """)
        else:
            card.claim_eval_label.setText("في انتظار المستندات")
            card.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #fef3c7;
                    color: #f59e0b;
                    border-radius: 18px;
                }
            """)

    def _evaluate_for_claim(self):
        """Evaluate relations for claim creation and populate from API response if available."""
        if hasattr(self.context, 'finalize_response') and self.context.finalize_response:
            self._populate_from_api_response(self.context.finalize_response)
            return

        self._populate_from_context()

    def _populate_from_api_response(self, response: Dict[str, Any]):
        """Populate claim cards from process-claims API response."""
        logger.info("Populating claim cards from API response")

        # Extract data from response
        survey_data = response.get('survey', {})
        claims_count = response.get('claimsCreatedCount', 0)
        created_claims = response.get('createdClaims', [])
        data_summary = response.get('dataSummary', {})
        claim_created = response.get('claimCreated', False)

        # Clear existing cards except the first one
        while len(self._claim_cards) > 1:
            card = self._claim_cards.pop()
            self.cards_layout.removeWidget(card)
            card.deleteLater()

        # Check if claimCreated is false - show empty state
        if not claim_created:
            logger.info("No claims created - showing empty state")
            self.scroll_area.hide()
            self.empty_state_widget.show()
            return

        # Claims were created - show claim cards
        self.empty_state_widget.hide()
        self.scroll_area.show()

        # If we have created claims, populate cards
        if created_claims and len(created_claims) > 0:
            # Populate first card with first claim
            first_claim = created_claims[0]
            self._populate_card_with_data(self._claim_cards[0], first_claim)

            # Add additional survey data to first card
            survey_date_str = survey_data.get('surveyDate', '')
            if survey_date_str:
                try:
                    from datetime import datetime
                    survey_date = datetime.fromisoformat(survey_date_str.replace('Z', '+00:00'))
                    self._claim_cards[0].claim_survey_date.setDate(QDate(survey_date.year, survey_date.month, survey_date.day))
                except Exception as e:
                    logger.warning(f"Failed to parse survey date: {e}")

            # Create additional cards for remaining claims
            for i in range(1, len(created_claims)):
                claim = created_claims[i]
                new_card = self._create_claim_card_widget(claim)
                # Insert before the stretch
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, new_card)
                self._claim_cards.append(new_card)

            # Store claim info in context
            self.context.update_data("claims_count", claims_count)
            self.context.update_data("created_claims", created_claims)
        else:
            # No claims created - populate first card with context data
            self._populate_first_card_from_context(survey_data, data_summary, response)

    def _populate_first_card_from_context(self, survey_data: Dict, data_summary: Dict, response: Dict):
        """Populate the first card from context when no claims were created."""
        first_card = self._claim_cards[0]

        # Populate unit subdivision number from survey
        unit_identifier = survey_data.get('unitIdentifier', '')
        if unit_identifier:
            first_card.claim_unit_search.setText(unit_identifier)
        elif self.context.unit:
            first_card.claim_unit_search.setText(str(self.context.unit.unit_number or ""))

        # Populate claimant name from first person in context
        if self.context.persons:
            first_person = self.context.persons[0]
            full_name = f"{first_person.get('first_name', '')} {first_person.get('last_name', '')}"
            first_card.claim_person_search.setText(full_name.strip())

        # Set survey date from API response
        survey_date_str = survey_data.get('surveyDate', '')
        if survey_date_str:
            try:
                from datetime import datetime
                survey_date = datetime.fromisoformat(survey_date_str.replace('Z', '+00:00'))
                first_card.claim_survey_date.setDate(QDate(survey_date.year, survey_date.month, survey_date.day))
            except Exception as e:
                logger.warning(f"Failed to parse survey date: {e}")

        # Auto-select claim type based on relations
        # relation_type can be integer (1=owner,2=occupant,3=tenant,4=guest,5=heir,99=other) or string
        owners = [r for r in self.context.relations if r.get('relation_type') in ('owner', 'co_owner', 1)]
        tenants = [r for r in self.context.relations if r.get('relation_type') in ('tenant', 3)]
        occupants = [r for r in self.context.relations if r.get('relation_type') in ('occupant', 2)]
        heirs = [r for r in self.context.relations if r.get('relation_type') in ('heir', 5)]

        if owners or heirs:
            for i in range(first_card.claim_type_combo.count()):
                if first_card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Ownership"):
                    first_card.claim_type_combo.setCurrentIndex(i)
                    break
        elif tenants:
            for i in range(first_card.claim_type_combo.count()):
                if first_card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Tenancy"):
                    first_card.claim_type_combo.setCurrentIndex(i)
                    break
        elif occupants:
            for i in range(first_card.claim_type_combo.count()):
                if first_card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Occupancy"):
                    first_card.claim_type_combo.setCurrentIndex(i)
                    break

        # Update status bar
        evidence_count = data_summary.get('evidenceCount', 0)
        reason = response.get('claimNotCreatedReason', '')

        if evidence_count > 0:
            first_card.claim_eval_label.setText(f"✓  الأدلة متوفرة ({evidence_count})")
            first_card.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #e1f7ef;
                    color: #10b981;
                    border-radius: 18px;
                }
            """)
        else:
            first_card.claim_eval_label.setText(reason if reason else "في انتظار المستندات")
            first_card.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #fef3c7;
                    color: #f59e0b;
                    border-radius: 18px;
                }
            """)

    def _populate_from_context(self):
        """Original logic to populate from context when no API response is available."""
        # Ensure scroll area is visible and empty state is hidden
        self.empty_state_widget.hide()
        self.scroll_area.show()

        first_card = self._claim_cards[0]

        # relation_type can be integer (1=owner,2=occupant,3=tenant,4=guest,5=heir,99=other) or string
        owners = [r for r in self.context.relations if r.get('relation_type') in ('owner', 'co_owner', 1)]
        tenants = [r for r in self.context.relations if r.get('relation_type') in ('tenant', 3)]
        occupants = [r for r in self.context.relations if r.get('relation_type') in ('occupant', 2)]
        heirs = [r for r in self.context.relations if r.get('relation_type') in ('heir', 5)]

        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)
        # Also check person data for uploaded tenure documents (not reflected in relations)
        if total_evidences == 0:
            for person in self.context.persons:
                total_evidences += len(person.get('_relation_uploaded_files', []))

        if self.context.unit:
            unit = self.context.unit
            unit_num = unit.unit_number or unit.apartment_number or "?"
            first_card.claim_unit_search.setText(str(unit_num))

        if self.context.persons:
            first_person = self.context.persons[0]
            full_name = f"{first_person.get('first_name', '')} {first_person.get('last_name', '')}"
            first_card.claim_person_search.setText(full_name.strip())

        if owners or heirs:
            for i in range(first_card.claim_type_combo.count()):
                if first_card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Ownership"):
                    first_card.claim_type_combo.setCurrentIndex(i)
                    break
        elif tenants:
            for i in range(first_card.claim_type_combo.count()):
                if first_card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Tenancy"):
                    first_card.claim_type_combo.setCurrentIndex(i)
                    break
        elif occupants:
            for i in range(first_card.claim_type_combo.count()):
                if first_card.claim_type_combo.itemData(i) == _find_combo_code_by_english("ClaimType", "Occupancy"):
                    first_card.claim_type_combo.setCurrentIndex(i)
                    break

        if total_evidences > 0:
            first_card.claim_eval_label.setText(f"✓  الأدلة متوفرة ({total_evidences})")
            first_card.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #e1f7ef;
                    color: #10b981;
                    border-radius: 18px;
                }
            """)
        else:
            first_card.claim_eval_label.setText("في انتظار المستندات")
            first_card.claim_eval_label.setStyleSheet("""
                QLabel {
                    background-color: #fef3c7;
                    color: #f59e0b;
                    border-radius: 18px;
                }
            """)

    def on_show(self):
        """Called when step is shown."""
        super().on_show()
        self._evaluate_for_claim()

    def validate(self) -> StepValidationResult:
        result = self.create_validation_result()

        # Skip validation if empty state is shown (no claims created)
        if hasattr(self, 'empty_state_widget') and self.empty_state_widget.isVisible():
            return result

        # Validate at least the first card has claim type selected
        if self._claim_cards:
            first_card = self._claim_cards[0]
            claim_type = first_card.claim_type_combo.currentData()
            if not claim_type:
                result.add_error(tr("wizard.claim.type_required"))

        # Store claims data to context during validation
        # (collect_data() is never called by the framework during navigation)
        if result.is_valid and self._claim_cards:
            self.collect_data()

        return result

    def collect_data(self) -> Dict[str, Any]:
        """Collect claim data from all cards."""
        # Return empty data if empty state is shown (no claims created)
        if hasattr(self, 'empty_state_widget') and self.empty_state_widget.isVisible():
            return {"claims": [], "claim_data": None, "no_claims_created": True}

        claims_data = []

        for card in self._claim_cards:
            # Collect claimant person IDs
            claimant_ids = [r['person_id'] for r in self.context.relations
                            if r.get('relation_type') in ('owner', 'co_owner', 'heir', 1, 5)]
            if not claimant_ids:
                claimant_ids = [r['person_id'] for r in self.context.relations]

            # Collect all evidences from relations
            all_evidences = []
            for rel in self.context.relations:
                all_evidences.extend(rel.get('evidences', []))

            # Also count uploaded tenure documents from person data
            evidence_count = len(all_evidences)
            if evidence_count == 0:
                for person in self.context.persons:
                    evidence_count += len(person.get('_relation_uploaded_files', []))

            claim_data = {
                "claim_type": card.claim_type_combo.currentData(),
                "priority": card.claim_priority_combo.currentData(),
                "business_nature": card.claim_business_nature.currentData(),
                "source": card.claim_source_combo.currentData() or _find_combo_code_by_english("ClaimSource", "Office Submission"),
                "case_status": card.claim_status_combo.currentData() or _find_combo_code_by_english("ClaimStatus", "New"),
                "survey_date": card.claim_survey_date.date().toPyDate().isoformat(),
                "next_action_date": card.claim_next_action_date.date().toPyDate().isoformat(),
                "notes": card.claim_notes.toPlainText().strip(),
                "status": "draft",
                "person_name": card.claim_person_search.text().strip(),
                "unit_display_id": card.claim_unit_search.text().strip(),
                "claimant_person_ids": claimant_ids,
                "evidence_ids": [e['evidence_id'] for e in all_evidences],
                "evidence_count": evidence_count,
                "unit_id": self.context.unit.unit_id if self.context.unit else None,
                "building_id": self.context.building.building_id if self.context.building else None
            }
            claims_data.append(claim_data)

        # Store all claims in context
        self.context.claims = claims_data
        # Store first claim as the main claim_data for backward compatibility
        if claims_data:
            self.context.claim_data = claims_data[0]

        return {"claims": claims_data, "claim_data": claims_data[0] if claims_data else None}

    def get_step_title(self) -> str:
        return "تسجيل الحالة"

    def get_step_description(self) -> str:
        return "ربط المطالبين بالوحدات العقارية وتتبع مطالبات تسجيل حقوق الحيازة"
