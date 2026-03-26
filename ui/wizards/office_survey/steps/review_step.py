# -*- coding: utf-8 -*-
"""
Review Step - Step 6 of Office Survey Wizard.

Final review and submission step - displays summary cards from all previous steps.
"""

from typing import Dict, Any
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
    QHBoxLayout, QGridLayout, QGraphicsDropShadowEffect,
    QPushButton, QMenu
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.error_handler import ErrorHandler
from ui.design_system import Colors
from ui.style_manager import StyleManager
from ui.font_utils import FontManager, create_font
from ui.components.icon import Icon
from ui.components.toast import Toast
from utils.logger import get_logger
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from services.translation_manager import tr
from services.error_mapper import map_exception
from ui.wizards.office_survey.steps.occupancy_claims_step import _is_owner_relation
from services.display_mappings import (
    get_relation_type_display, get_relationship_to_head_display,
    get_unit_status_display,
    get_claim_type_display, get_priority_display,
    get_business_type_display, get_source_display,
    get_claim_status_display,
)
from utils.helpers import build_hierarchical_address

logger = get_logger(__name__)


class ReviewStep(BaseStep):
    """Step 6: Review & Submit."""

    edit_requested = pyqtSignal(int)  # Emits step index to edit

    def __init__(self, context: SurveyContext, parent=None, read_only=False):
        self._read_only = read_only
        super().__init__(context, parent)

        # Initialize API service for finalizing survey
        self._api_service = get_api_client()

    def setup_ui(self):
        """Setup the step's UI with scrollable summary cards."""
        widget = self
        widget.setLayoutDirection(Qt.RightToLeft)
        widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BACKGROUND};
            }}
        """)

        layout = self.main_layout
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(16)

        # --- Main Scroll Area ---
        scroll = QScrollArea()
        scroll.setLayoutDirection(Qt.RightToLeft)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
            + StyleManager.scrollbar()
        )

        # Scroll content container
        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)  # Increased spacing for clear card separation

        # Case status banner (hidden — not shown in final review)
        self.case_status_banner = self._create_case_status_banner()
        self.case_status_banner.hide()

        # Applicant info card (hidden in case details / read-only mode)
        self.applicant_card = self._create_applicant_card()
        scroll_layout.addWidget(self.applicant_card)
        if self._read_only:
            self.applicant_card.hide()

        # Create summary cards — building split into 3 separate cards
        # Building Card 1: Header + code + address
        self.building_info_card = self._create_building_info_card()
        scroll_layout.addWidget(self.building_info_card)

        # Building Card 2: Stats row
        self.building_stats_card, self.building_stats_content = self._create_simple_card()
        scroll_layout.addWidget(self.building_stats_card)

        # Building Card 3: Location section
        self.building_location_card, self.building_location_content = self._create_simple_card()
        scroll_layout.addWidget(self.building_location_card)

        self.unit_card = self._create_unit_card()
        scroll_layout.addWidget(self.unit_card)

        self.household_card = self._create_household_card()
        scroll_layout.addWidget(self.household_card)

        self.persons_card = self._create_persons_card()
        scroll_layout.addWidget(self.persons_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
    # Shared Styles & Helpers

    def _create_section_label(self, text: str) -> QLabel:
        """Create section label with WIZARD_TITLE style (reused across all cards)."""
        lbl = QLabel(text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        return lbl

    def _create_case_status_banner(self) -> QFrame:
        """Create a banner showing whether the case is open or closed."""
        banner = QFrame()
        banner.setObjectName("caseStatusBanner")
        banner.setFixedHeight(48)
        banner.setStyleSheet("""
            QFrame#caseStatusBanner {
                background-color: #FFF7ED;
                border: 1px solid #FED7AA;
                border-radius: 8px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(16, 0, 16, 0)

        self._case_status_label = QLabel(tr("review.case.open"))
        self._case_status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._case_status_label.setStyleSheet("color: #C2410C; background: transparent; border: none;")
        self._case_status_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        b_layout.addWidget(self._case_status_label)
        return banner

    def _create_applicant_card(self) -> QFrame:
        """Create a summary card for applicant (visitor) information."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        header_row = QHBoxLayout()
        title_lbl = QLabel(tr("review.applicant.title"))
        title_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        header_row.addWidget(title_lbl)
        header_row.addStretch()
        card_layout.addLayout(header_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #E2E8F0; border: none;")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        self._applicant_grid = QGridLayout()
        self._applicant_grid.setSpacing(8)
        card_layout.addLayout(self._applicant_grid)

        return card

    def _add_shadow(self, widget: QWidget):
        """Add drop shadow effect to a widget."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 25))
        widget.setGraphicsEffect(shadow)

    def _request_edit(self, step_index: int):
        """Emit signal requesting wizard to enter edit mode for a step."""
        self.edit_requested.emit(step_index)

    def _create_edit_menu_button(self, callback) -> QPushButton:
        """Create a menu button with a single 'تعديل' action."""
        menu_btn = QPushButton("⋮")
        menu_btn.setFixedSize(36, 36)
        menu_btn.setStyleSheet("""
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
        menu_btn.setCursor(Qt.PointingHandCursor)

        menu = QMenu(menu_btn)
        menu.setLayoutDirection(Qt.RightToLeft)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F3F4F6;
            }
        """)

        edit_action = menu.addAction(tr("wizard.review.edit"))
        edit_action.triggered.connect(callback)

        menu_btn.clicked.connect(
            lambda: menu.exec_(menu_btn.mapToGlobal(menu_btn.rect().bottomRight()))
        )

        return menu_btn

    def _create_card_base(self, icon_name: str, title: str, subtitle: str, edit_callback=None) -> tuple:
        """Create base card with header (icon, title, subtitle) and return card and content layout."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header with icon, title, subtitle
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Icon container (compact: 28×28, radius 7px)
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

        # Title and subtitle
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        # In RTL mode: first added = rightmost
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_container)
        header_layout.addStretch()

        # Edit menu button (appears on left side in RTL)
        if edit_callback:
            edit_btn = self._create_edit_menu_button(edit_callback)
            header_layout.addWidget(edit_btn)

        card_layout.addWidget(header_container)

        # Content container
        content_widget = QWidget()
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)

        return card, content_layout

    def _create_simple_card(self) -> tuple:
        """Create a simple card (no header) with shadow and return card and content layout."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        self._add_shadow(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)

        # Content container
        content_widget = QWidget()
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        card_layout.addWidget(content_widget)

        return card, content_layout

    def _create_person_row(self, person: dict) -> QWidget:
        """Create a person row card with blue left border accent."""
        row = QFrame()
        row.setLayoutDirection(Qt.RightToLeft)
        row.setFixedHeight(80)
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
                border-right: 3px solid #3B82F6;
            }}
            QLabel {{
                border: none;
            }}
        """)

        card_layout = QHBoxLayout(row)
        card_layout.setContentsMargins(15, 0, 15, 0)

        # Right side: Icon + Text
        right_group = QHBoxLayout()
        right_group.setSpacing(12)

        # Circular icon
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #F4F8FF;
                color: #3182CE;
                border-radius: 18px;
                border: none;
            }
        """)
        user_pixmap = Icon.load_pixmap("user", size=20)
        if user_pixmap and not user_pixmap.isNull():
            icon_lbl.setPixmap(user_pixmap)

        # Name and role
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)

        full_name = f"{person.get('first_name', '')} {person.get('father_name', '')} {person.get('last_name', '')}".strip()
        if not full_name:
            full_name = person.get('full_name', person.get('name', '-'))
        name_lbl = QLabel(full_name)
        name_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        name_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        role_key = person.get('person_role') or person.get('relationship_type')
        role_text = get_relationship_to_head_display(role_key) if role_key else ""
        role_lbl = QLabel(role_text)
        role_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        role_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        text_vbox.addWidget(name_lbl)
        text_vbox.addWidget(role_lbl)

        right_group.addWidget(icon_lbl)
        right_group.addLayout(text_vbox)

        card_layout.addLayout(right_group)
        card_layout.addStretch()

        # Left side: "عرض المعلومات الشخصية" link (hidden in read_only mode)
        if not self._read_only:
            view_lbl = QLabel(tr("wizard.review.view_personal_info"))
            view_lbl.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_MEDIUM))
            view_lbl.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
            view_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            view_lbl.setCursor(Qt.PointingHandCursor)
            view_lbl.mousePressEvent = lambda e, p=person: self._view_person_editable(p)
            card_layout.addWidget(view_lbl)

        return row

    def _create_building_info_card(self) -> QFrame:
        """Create building info card (Step 1) — header + code + address."""
        card, content_layout = self._create_card_base("blue", tr("wizard.review.building_card_title"), tr("wizard.review.building_card_subtitle"))
        self.building_info_content = content_layout
        return card

    def _create_unit_card(self) -> QFrame:
        """Create unit information summary card (Step 2) - matching step 2 header."""
        card, content_layout = self._create_card_base("move", tr("wizard.review.unit_card_title"), tr("wizard.review.unit_card_subtitle"),
                                                       edit_callback=None if self._read_only else lambda: self._request_edit(2))
        self.unit_content = content_layout
        return card

    def _create_household_card(self) -> QFrame:
        """Create household information summary card (Step 3)."""
        card, content_layout = self._create_card_base("user-group", tr("wizard.review.household_card_title"), tr("wizard.review.household_card_subtitle"),
                                                       edit_callback=None if self._read_only else lambda: self._request_edit(3))
        self.household_content = content_layout
        return card

    def _create_persons_card(self) -> QFrame:
        """Create persons list summary card (Step 4)."""
        card, content_layout = self._create_card_base("user-account", tr("wizard.review.persons_card_title"), tr("wizard.review.persons_card_subtitle"),
                                                       edit_callback=None if self._read_only else lambda: self._request_edit(4))
        self.persons_content = content_layout
        return card

    def _create_claim_card(self) -> QFrame:
        """Create claim information summary card (Step 6)."""
        card, content_layout = self._create_card_base("elements", tr("wizard.review.claim_card_title"), tr("wizard.review.claim_card_subtitle"))
        self.claim_content = content_layout
        return card

    def _open_map_dialog(self):
        """Open map dialog in read-only mode to view the building location."""
        from ui.components.building_map_dialog_v2 import show_building_map_dialog

        auth_token = None
        try:
            main_window = self
            while main_window and not hasattr(main_window, 'current_user'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'current_user') and main_window.current_user:
                auth_token = getattr(main_window.current_user, '_api_token', None)
        except Exception as e:
            logger.warning(f"Could not get auth token: {e}")
            Toast.show_toast(self, "تعذر تحميل بيانات المراجعة", Toast.ERROR)

        building = self.context.building
        if building:
            show_building_map_dialog(
                db=self.context.db,
                selected_building_id=building.building_uuid or building.building_id,
                auth_token=auth_token,
                read_only=True,
                selected_building=building,
                parent=self
            )

    def _clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _populate_review(self):
        """Populate all summary cards with data from context."""
        self._populate_case_status_banner()
        self._populate_applicant_card()
        self._populate_building_card()
        self._populate_unit_card()
        self._populate_household_card()
        self._populate_persons_card()

    def _populate_case_status_banner(self):
        """Update case status banner based on claim/owner/evidence state.

        Three states:
          - Closed:           owner exists AND has uploaded evidence
          - Pending evidence: owner exists BUT no evidence uploaded
          - Open:             no owner relation — no claim created
        """
        has_owner = False
        owner_has_evidence = False

        for p in (self.context.persons or []):
            role = p.get('person_role') or p.get('relationship_type')
            if _is_owner_relation(role):
                has_owner = True
                rel_files = p.get('_relation_uploaded_files') or []
                has_docs_flag = p.get('relation_data', {}).get('has_documents', False)
                if rel_files or has_docs_flag:
                    owner_has_evidence = True
                break

        if has_owner and owner_has_evidence:
            text = tr("review.case.closed")
            text_color = "#15803D"
            bg_color, border_color = "#F0FDF4", "#BBF7D0"
        elif has_owner:
            text = tr("review.case.pending_evidence")
            text_color = "#92400E"
            bg_color, border_color = "#FFFBEB", "#FDE68A"
        else:
            text = tr("review.case.open")
            text_color = "#C2410C"
            bg_color, border_color = "#FFF7ED", "#FED7AA"

        self._case_status_label.setText(text)
        self._case_status_label.setStyleSheet(
            f"color: {text_color}; background: transparent; border: none;"
        )
        self.case_status_banner.setStyleSheet(f"""
            QFrame#caseStatusBanner {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """)

    def _populate_applicant_card(self):
        """Populate the applicant summary card from context.applicant."""
        self._clear_layout(self._applicant_grid)

        applicant = getattr(self.context, 'applicant', None)
        if not applicant:
            no_data = QLabel("-")
            no_data.setFont(create_font(size=FontManager.SIZE_BODY))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            self._applicant_grid.addWidget(no_data, 0, 0)
            return

        full_name_display = " ".join(filter(None, [
            applicant.get("first_name_ar"),
            applicant.get("father_name_ar"),
            applicant.get("last_name_ar"),
        ])) or applicant.get("full_name", "-")

        fields = [
            (tr("wizard.applicant.full_name"), full_name_display),
            (tr("wizard.applicant.national_id"), applicant.get("national_id", "")),
            (tr("wizard.applicant.phone"), applicant.get("phone", "")),
            (tr("wizard.applicant.email"), applicant.get("email", "")),
        ]

        idx = 0
        for label_text, value_text in fields:
            if not value_text or value_text == "-":
                continue
            lbl = QLabel(label_text + ":")
            lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            lbl.setAlignment(Qt.AlignCenter)
            val = QLabel(value_text)
            val.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
            val.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            val.setAlignment(Qt.AlignCenter)
            self._applicant_grid.addWidget(lbl, idx // 2, (idx % 2) * 2)
            self._applicant_grid.addWidget(val, idx // 2, (idx % 2) * 2 + 1)
            idx += 1

    def _populate_building_card(self):
        """Populate 3 separate building cards matching BuildingSelectionStep."""
        self._clear_layout(self.building_info_content)
        self._clear_layout(self.building_stats_content)
        self._clear_layout(self.building_location_content)

        if not self.context.building:
            no_data = QLabel(tr("wizard.building.not_selected"))
            no_data.setFont(create_font(size=FontManager.SIZE_BODY))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.building_info_content.addWidget(no_data)
            self.building_stats_card.hide()
            self.building_location_card.hide()
            return

        self.building_stats_card.show()
        self.building_location_card.show()

        building = self.context.building
        building_code = str(building.building_id) if hasattr(building, 'building_id') else "-"
        building_type = building.building_type_display if hasattr(building, 'building_type_display') else "-"
        status = building.building_status_display if hasattr(building, 'building_status_display') else "-"
        units_count = str(building.number_of_units) if hasattr(building, 'number_of_units') else "0"
        parcels_count = str(getattr(building, 'number_of_apartments', 0))
        shops_count = str(building.number_of_shops) if hasattr(building, 'number_of_shops') else "0"
        location_desc = getattr(building, 'location_description', '-')
        general_desc = getattr(building, 'general_description', '-')
        building_num_label = QLabel(building_code)
        building_num_label.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        building_num_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        building_num_label.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        self.building_info_content.addWidget(building_num_label)

        address = build_hierarchical_address(building_obj=building, unit_obj=None, include_unit=False)
        addr_bar = QFrame()
        addr_bar.setLayoutDirection(Qt.RightToLeft)
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
        else:
            addr_icon.setText("\U0001f4cd")
        addr_row.addWidget(addr_icon)

        addr_text = QLabel(address if address else "-")
        addr_text.setAlignment(Qt.AlignCenter)
        addr_text.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        addr_text.setStyleSheet("color: #0F5B95; background: transparent; border: none;")
        addr_row.addWidget(addr_text)
        addr_row.addStretch()
        self.building_info_content.addWidget(addr_bar)
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(0)

        stat_items = [
            (tr("wizard.building.status"), status),
            (tr("wizard.building.type"), building_type),
            (tr("wizard.building.units_count"), units_count),
            (tr("wizard.building.parcels_count"), parcels_count),
            (tr("wizard.building.shops_count"), shops_count),
        ]

        for label_text, value_text in stat_items:
            section = QWidget()
            section.setStyleSheet("background: transparent;")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(4)
            section_layout.setAlignment(Qt.AlignCenter)

            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

            val = QLabel(str(value_text))
            val.setAlignment(Qt.AlignCenter)
            val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
            val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

            section_layout.addWidget(lbl)
            section_layout.addWidget(val)
            stats_row.addWidget(section, stretch=1)

        self.building_stats_content.addLayout(stats_row)
        loc_header = QLabel(tr("wizard.building.location_title"))
        loc_header.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        loc_header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        self.building_location_content.addWidget(loc_header)

        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        map_container = QLabel()
        map_container.setFixedSize(400, 130)
        map_container.setAlignment(Qt.AlignCenter)
        map_container.setObjectName("reviewMapContainer")
        map_container.setStyleSheet("QLabel#reviewMapContainer { background-color: #E8E8E8; border-radius: 8px; }")
        map_pixmap = Icon.load_pixmap("image-40", size=None)
        if not map_pixmap or map_pixmap.isNull():
            map_pixmap = Icon.load_pixmap("map-placeholder", size=None)
        if map_pixmap and not map_pixmap.isNull():
            map_container.setPixmap(map_pixmap.scaled(400, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        else:
            loc_fallback = Icon.load_pixmap("carbon_location-filled", size=48)
            if loc_fallback and not loc_fallback.isNull():
                map_container.setPixmap(loc_fallback)

        # "فتح الخريطة" button (top-left, same as building_selection_step)
        map_button = QPushButton(map_container)
        map_button.setFixedSize(94, 20)
        map_button.move(8, 8)
        map_button.setCursor(Qt.PointingHandCursor)
        icon_pixmap = Icon.load_pixmap("pill", size=12)
        if icon_pixmap and not icon_pixmap.isNull():
            map_button.setIcon(QIcon(icon_pixmap))
            map_button.setIconSize(QSize(12, 12))
        map_button.setText(tr("wizard.building.open_map"))
        map_button.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: #F5F5F5;
            }}
        """)
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(8)
        btn_shadow.setXOffset(0)
        btn_shadow.setYOffset(2)
        btn_shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(btn_shadow)
        map_button.clicked.connect(self._open_map_dialog)

        # Location icon (center of map)
        location_icon = QLabel(map_container)
        loc_pixmap = Icon.load_pixmap("carbon_location-filled", size=56)
        if loc_pixmap and not loc_pixmap.isNull():
            location_icon.setPixmap(loc_pixmap)
            location_icon.setFixedSize(56, 56)
            location_icon.move(172, 37)
            location_icon.setStyleSheet("background: transparent;")
        else:
            location_icon.setText("\U0001f4cd")
            location_icon.setFont(create_font(size=32, weight=FontManager.WEIGHT_REGULAR))
            location_icon.setStyleSheet("background: transparent;")
            location_icon.setAlignment(Qt.AlignCenter)
            location_icon.setFixedSize(56, 56)
            location_icon.move(172, 37)

        content_row.addWidget(map_container)

        loc_desc_section = QVBoxLayout()
        loc_desc_section.setSpacing(4)
        loc_desc_label = QLabel(tr("wizard.building.location_description"))
        loc_desc_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        loc_desc_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        loc_desc_value = QLabel(location_desc if location_desc else "-")
        loc_desc_value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        loc_desc_value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        loc_desc_value.setWordWrap(True)
        loc_desc_section.addWidget(loc_desc_label)
        loc_desc_section.addWidget(loc_desc_value)
        loc_desc_section.addStretch(1)
        content_row.addLayout(loc_desc_section, stretch=1)

        gen_desc_section = QVBoxLayout()
        gen_desc_section.setSpacing(4)
        gen_desc_label = QLabel(tr("wizard.building.general_description"))
        gen_desc_label.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        gen_desc_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        gen_desc_value = QLabel(general_desc if general_desc else "-")
        gen_desc_value.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        gen_desc_value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        gen_desc_value.setWordWrap(True)
        gen_desc_section.addWidget(gen_desc_label)
        gen_desc_section.addWidget(gen_desc_value)
        gen_desc_section.addStretch(1)
        content_row.addLayout(gen_desc_section, stretch=1)

        self.building_location_content.addLayout(content_row)

    def _create_unit_stat_section(self, label_text: str, value_text: str = "-"):
        """Create a stat section matching step 3 unit card style (label top, value below, both centered)."""
        section = QWidget()
        section.setStyleSheet("background: transparent;")

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(8, 0, 8, 0)
        section_layout.setSpacing(4)
        section_layout.setAlignment(Qt.AlignCenter)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

        value = QLabel(value_text)
        value.setAlignment(Qt.AlignCenter)
        value.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_SEMIBOLD))
        value.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        section_layout.addWidget(label)
        section_layout.addWidget(value)

        return section, value

    def _populate_unit_card(self):
        """Populate unit information card - same layout as step 3 unit info row."""
        self._clear_layout(self.unit_content)

        unit = self.context.unit
        new_unit_data = self.context.new_unit_data if self.context.is_new_unit else None

        if unit or new_unit_data:
            # Extract values
            if unit:
                unit_num = str(unit.unit_number or unit.apartment_number or "-")
                floor = str(unit.floor_number) if unit.floor_number is not None else "-"
                rooms = str(unit.apartment_number) if unit.apartment_number and str(unit.apartment_number) != "0" else "-"
                if unit.area_sqm:
                    try:
                        area = tr("wizard.unit.area_format", value=f"{float(unit.area_sqm):.2f}")
                    except (ValueError, TypeError):
                        area = "-"
                else:
                    area = "-"
                unit_type = unit.unit_type_display_ar if hasattr(unit, 'unit_type_display_ar') else "-"
                status_raw = getattr(unit, 'apartment_status', None)
                if status_raw is not None:
                    status = get_unit_status_display(status_raw)
                else:
                    status = "-"
            else:
                unit_num = str(new_unit_data.get('unit_number', tr("wizard.review.new_unit")))
                floor = str(new_unit_data.get('floor_number', '-'))
                rooms = str(new_unit_data.get('number_of_rooms', '-'))
                area_raw = new_unit_data.get('area_sqm')
                area = tr("wizard.unit.area_format", value=f"{float(area_raw):.2f}") if area_raw else "-"
                unit_type = new_unit_data.get('unit_type', '-')
                status = tr("wizard.review.new_unit")

            # Build unit info container matching step 3 style
            unit_info_container = QFrame()
            unit_info_container.setLayoutDirection(Qt.RightToLeft)
            unit_info_container.setFixedHeight(73)
            unit_info_container.setStyleSheet(f"""
                QFrame {{
                    background-color: #F8FAFF;
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 8px;
                }}
            """)

            unit_info_row = QHBoxLayout(unit_info_container)
            unit_info_row.setSpacing(0)
            unit_info_row.setContentsMargins(8, 8, 8, 8)

            # 6 sections in same order as step 2/3
            data_points = [
                (tr("wizard.unit.number"), unit_num),
                (tr("wizard.unit.floor_number"), floor),
                (tr("wizard.unit.rooms_count"), rooms),
                (tr("wizard.unit.area"), area),
                (tr("wizard.unit.type"), unit_type),
                (tr("wizard.unit.status"), status),
            ]

            for label_text, value_text in data_points:
                section, _ = self._create_unit_stat_section(label_text, value_text)
                unit_info_row.addWidget(section, stretch=1)

            self.unit_content.addWidget(unit_info_container)

            # Dotted separator line
            dotted_sep = QFrame()
            dotted_sep.setFixedHeight(1)
            dotted_sep.setStyleSheet("background: transparent; border-top: 1px dashed #E0E6ED;")
            self.unit_content.addWidget(dotted_sep)

            desc_layout = QVBoxLayout()
            desc_layout.setContentsMargins(0, 0, 0, 0)
            desc_layout.setSpacing(2)

            desc_title = QLabel(tr("wizard.unit.property_description"))
            desc_title.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            desc_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")

            desc_text_content = ""
            if unit and hasattr(unit, 'property_description') and unit.property_description:
                desc_text_content = unit.property_description
            elif new_unit_data and new_unit_data.get('property_description'):
                desc_text_content = new_unit_data.get('property_description')
            else:
                desc_text_content = tr("wizard.unit.property_description_placeholder")

            desc_text = QLabel(desc_text_content)
            desc_text.setFont(create_font(size=FontManager.WIZARD_FIELD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            desc_text.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            desc_text.setWordWrap(True)
            desc_text.setMaximumHeight(40)

            desc_layout.addWidget(desc_title)
            desc_layout.addWidget(desc_text)

            desc_widget = QWidget()
            desc_widget.setLayoutDirection(Qt.RightToLeft)
            desc_widget.setStyleSheet("background: transparent; border: none;")
            desc_widget.setLayout(desc_layout)
            self.unit_content.addWidget(desc_widget)
        else:
            no_data = QLabel(tr("wizard.unit.not_selected"))
            no_data.setFont(create_font(size=FontManager.SIZE_BODY))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.unit_content.addWidget(no_data)

    def _create_demographic_card(self, items: list) -> QFrame:
        """Create a demographic data card with label/value rows and separators."""
        frame = QFrame()
        frame.setLayoutDirection(Qt.RightToLeft)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(18)

        ALIGN_ABS_RIGHT = Qt.AlignRight | Qt.AlignAbsolute

        for i, (text, value) in enumerate(items):
            item_block = QVBoxLayout()
            item_block.setSpacing(4)

            txt_lbl = QLabel(text)
            txt_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            txt_lbl.setStyleSheet(f"color: #1e293b; background: transparent; border: none;")
            txt_lbl.setAlignment(ALIGN_ABS_RIGHT)

            val_lbl = QLabel(str(value))
            val_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            val_lbl.setStyleSheet(f"color: #94a3b8; background: transparent; border: none;")
            val_lbl.setAlignment(ALIGN_ABS_RIGHT)

            item_block.addWidget(txt_lbl)
            item_block.addWidget(val_lbl)
            card_layout.addLayout(item_block)

            if i < len(items) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet(f"background-color: #f1f5f9; border: none;")
                card_layout.addWidget(separator)

        return frame

    def _populate_household_card(self):
        """Populate household information card - matching screenshot layout."""
        self._clear_layout(self.household_content)

        if not self.context.households:
            no_data = QLabel(tr("wizard.household.no_data"))
            no_data.setFont(create_font(size=FontManager.SIZE_BODY))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.household_content.addWidget(no_data)
            return

        total_size = sum(h.get('size', 0) for h in self.context.households)

        # Get main occupant name (first person in context)
        main_occupant_name = "-"
        if self.context.persons:
            p = self.context.persons[0]
            main_occupant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
            if not main_occupant_name:
                main_occupant_name = p.get('full_name', p.get('name', '-'))

        # Summary row: main occupant info (right) + total count (left)
        summary_container = QWidget()
        summary_container.setLayoutDirection(Qt.RightToLeft)
        summary_container.setStyleSheet("background: transparent; border: none;")
        summary_layout = QHBoxLayout(summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)

        occupant_block = QVBoxLayout()
        occupant_block.setSpacing(4)
        occupant_title = self._create_section_label(tr("wizard.review.main_occupant_info"))
        occupant_val = QLabel(main_occupant_name)
        occupant_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        occupant_val.setStyleSheet(f"color: #94a3b8; background: transparent; border: none;")
        occupant_block.addWidget(occupant_title)
        occupant_block.addWidget(occupant_val)

        count_block = QVBoxLayout()
        count_block.setSpacing(4)
        count_title = self._create_section_label(tr("wizard.household.family_size"))
        count_title.setAlignment(Qt.AlignCenter)
        count_val = QLabel(str(total_size))
        count_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        count_val.setStyleSheet(f"color: #94a3b8; background: transparent; border: none;")
        count_val.setAlignment(Qt.AlignCenter)
        count_block.addWidget(count_title)
        count_block.addWidget(count_val)

        summary_layout.addLayout(occupant_block)
        summary_layout.addStretch()
        summary_layout.addLayout(count_block)
        summary_layout.addStretch()

        self.household_content.addWidget(summary_container)

        # --- Aggregate demographics ---
        demographics = {}
        for h in self.context.households:
            for key in ['adult_males', 'adult_females', 'male_children_under18', 'female_children_under18',
                        'male_elderly_over65', 'female_elderly_over65', 'disabled_males', 'disabled_females']:
                demographics[key] = demographics.get(key, 0) + h.get(key, 0)

        # --- Two cards side by side: Males (right) + Females (left) ---
        male_items = [
            (tr("wizard.household.adult_males"), demographics.get('adult_males', 0)),
            (tr("wizard.household.male_children"), demographics.get('male_children_under18', 0)),
            (tr("wizard.household.male_elderly"), demographics.get('male_elderly_over65', 0)),
            (tr("wizard.household.disabled_males"), demographics.get('disabled_males', 0)),
        ]

        female_items = [
            (tr("wizard.household.adult_females"), demographics.get('adult_females', 0)),
            (tr("wizard.household.female_children"), demographics.get('female_children_under18', 0)),
            (tr("wizard.household.female_elderly"), demographics.get('female_elderly_over65', 0)),
            (tr("wizard.household.disabled_females"), demographics.get('disabled_females', 0)),
        ]

        cards_container = QWidget()
        cards_container.setLayoutDirection(Qt.RightToLeft)
        cards_container.setStyleSheet("background: transparent; border: none;")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(20)

        cards_layout.addWidget(self._create_demographic_card(male_items))
        cards_layout.addWidget(self._create_demographic_card(female_items))

        self.household_content.addWidget(cards_container)

    def _populate_persons_card(self):
        """Populate persons list card matching step 4 layout."""
        self._clear_layout(self.persons_content)

        if not self.context.persons:
            no_data = QLabel(tr("wizard.person.no_persons"))
            no_data.setFont(create_font(size=FontManager.SIZE_BODY))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.persons_content.addWidget(no_data)
            return

        self.persons_content.setSpacing(10)

        for person in self.context.persons:
            row = self._create_person_row(person)
            self.persons_content.addWidget(row)

    def _view_person_editable(self, person: dict):
        """Open PersonDialog in editable mode to view/edit person details from review."""
        from ui.wizards.office_survey.dialogs.person_dialog import PersonDialog
        from PyQt5.QtWidgets import QDialog

        # Get API context IDs
        auth_token = None
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            auth_token = main_window._api_token

        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")
        unit_id = None
        if self.context.unit:
            unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            unit_id = self.context.new_unit_data.get('unit_uuid')

        is_finalized = self._read_only or self.context.status == "finalized"

        dialog = PersonDialog(
            person_data=person,
            existing_persons=self.context.persons,
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id,
            household_id=household_id,
            unit_id=unit_id,
            read_only=is_finalized
        )

        if dialog.exec_() == QDialog.Accepted and not is_finalized:
            updated_data = dialog.get_person_data()
            person_id = person.get('person_id')
            updated_data['person_id'] = person_id

            # Detect applicant (contact person - not a household member)
            is_applicant = person.get('_is_applicant', False) or person.get('_is_contact_person', False)
            if not is_applicant:
                contact_person_id = self.context.get_data('contact_person_id')
                if contact_person_id and person_id == contact_person_id:
                    is_applicant = True

            if person_id:
                try:
                    self._set_auth_token()
                    if is_applicant and survey_id:
                        self._api_service.update_contact_person(
                            survey_id, person_id, updated_data)
                    elif survey_id and household_id:
                        self._api_service.update_person_in_survey(
                            survey_id, household_id, person_id, updated_data)
                    else:
                        logger.warning(f"Missing survey_id or household_id for person {person_id}")
                        Toast.show_toast(self, "تعذر تحميل بيانات المراجعة", Toast.ERROR)
                    logger.info(f"Person {person_id} updated via API from review step")

                    relation_id = updated_data.get('_relation_id') or person.get('_relation_id')
                    if relation_id and survey_id:
                        try:
                            self._api_service.update_relation(survey_id, relation_id, updated_data)
                            logger.info(f"Relation {relation_id} updated via API")
                        except Exception as e:
                            logger.warning(f"Failed to update relation {relation_id}: {e}")
                            Toast.show_toast(self, "تعذر تحميل بيانات المراجعة", Toast.ERROR)
                except Exception as e:
                    from services.error_mapper import is_duplicate_nid_error, build_duplicate_person_message
                    if is_duplicate_nid_error(e):
                        ErrorHandler.show_warning(self, build_duplicate_person_message(getattr(e, 'response_data', {})), tr("common.warning"))
                    else:
                        logger.error(f"Failed to update person via API: {e}")
                        from services.error_mapper import map_exception
                        ErrorHandler.show_error(self, map_exception(e), tr("common.error"))
                    return

            # Update context
            for i, p in enumerate(self.context.persons):
                if p.get('person_id') == person_id:
                    self.context.persons[i] = updated_data
                    break

            # Refresh persons card
            self._populate_persons_card()
            logger.info(f"Person updated from review: {updated_data.get('first_name', '')} {updated_data.get('last_name', '')}")

    def _create_claim_data_card(self, claim_data: dict) -> QFrame:
        """Create a single read-only claim card matching ClaimStep styling exactly."""
        ro_bg = "#f0f7ff"

        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 15, 20, 15)
        card_layout.setSpacing(12)

        ro_field_style = f"""
            QLabel {{
                background-color: {ro_bg};
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                color: #333;
                font-size: 14px;
                min-height: 23px;
                max-height: 23px;
            }}
        """

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for i in range(3):
            grid.setColumnStretch(i, 1)

        def add_field(label_text, value_text, row, col):
            v = QVBoxLayout()
            v.setSpacing(4)
            lbl = self._create_section_label(label_text)
            v.addWidget(lbl)
            val = QLabel(str(value_text) if value_text else "-")
            val.setStyleSheet(ro_field_style)
            v.addWidget(val)
            grid.addLayout(v, row, col)

        # Claimant name
        claimant_name = claim_data.get('person_name', '').strip()
        if not claimant_name:
            claimant_ids = claim_data.get('claimant_person_ids', [])
            if claimant_ids and self.context.persons:
                for p in self.context.persons:
                    if p.get('person_id') in claimant_ids:
                        claimant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
                        break
            if not claimant_name and self.context.persons:
                p = self.context.persons[0]
                claimant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
        if not claimant_name:
            claimant_name = "-"

        # Unit display ID
        unit_display = claim_data.get('unit_display_id', '').strip()
        if not unit_display:
            unit_display = claim_data.get('unit_id', '-') or "-"

        # Row 0: claimant, unit, claim type
        add_field(tr("wizard.review.claimant_id"), claimant_name, 0, 0)
        add_field(tr("wizard.review.unit_claim_id"), unit_display, 0, 1)
        add_field(tr("wizard.review.claim_type"), get_claim_type_display(claim_data.get('claim_type', '')), 0, 2)

        # Row 1: case status, source, survey date
        add_field(tr("wizard.review.case_status"), get_claim_status_display(claim_data.get('case_status', 'new')), 1, 0)
        add_field(tr("wizard.review.source"), get_source_display(claim_data.get('source', '')), 1, 1)
        add_field(tr("wizard.review.survey_date"), str(claim_data.get('survey_date', '-') or '-'), 1, 2)

        card_layout.addLayout(grid)
        card_layout.addSpacing(4)

        # Notes
        notes_text = claim_data.get('notes', '')
        notes_title = self._create_section_label(tr("wizard.review.review_notes"))
        card_layout.addWidget(notes_title)

        notes_val = QLabel(notes_text if notes_text else tr("wizard.review.review_notes_placeholder"))
        notes_val.setAlignment(Qt.AlignTop)
        notes_val.setWordWrap(True)
        notes_val.setMinimumHeight(80)
        notes_val.setMaximumHeight(100)
        notes_val.setStyleSheet(f"""
            QLabel {{
                background-color: {ro_bg};
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 8px;
                color: {Colors.TEXT_SECONDARY if not notes_text else '#333'};
                font-size: 13px;
            }}
        """)
        card_layout.addWidget(notes_val)
        card_layout.addSpacing(4)

        # Evidence status bar (pill shape matching ClaimStep)
        evidence_count = claim_data.get('evidence_count', 0)
        if not evidence_count:
            evidence_ids = claim_data.get('evidence_ids', [])
            evidence_count = len(evidence_ids) if evidence_ids else 0

        eval_label = QLabel()
        eval_label.setAlignment(Qt.AlignCenter)
        eval_label.setFixedHeight(36)
        eval_label.setFont(create_font(size=FontManager.WIZARD_BADGE, weight=FontManager.WEIGHT_SEMIBOLD))

        if evidence_count > 0:
            self._set_evidence_label(eval_label, evidence_count)
        else:
            # Set initial state then fetch asynchronously
            eval_label.setText(tr("wizard.review.waiting_documents"))
            eval_label.setStyleSheet("""
                QLabel {
                    background-color: #fef3c7;
                    color: #f59e0b;
                    border-radius: 18px;
                }
            """)
            survey_id = self.context.get_data("survey_id")
            if survey_id:
                self._fetch_evidence_count_async(survey_id, eval_label)

        card_layout.addWidget(eval_label)

        return card

    def _set_evidence_label(self, label, count):
        """Set evidence label with count."""
        count_text = f" ({count})" if count else ""
        label.setText(f"\u2713  {tr('wizard.review.evidence_available')}{count_text}")
        label.setStyleSheet("""
            QLabel {
                background-color: #e1f7ef;
                color: #10b981;
                border-radius: 18px;
            }
        """)

    def _fetch_evidence_count_async(self, survey_id, label):
        """Fetch evidence count in background and update the label."""
        api = get_api_client()

        def _do_fetch():
            return api.get_survey_evidences(survey_id)

        def _on_fetched(evidences):
            count = len(evidences) if evidences else 0
            if count > 0:
                self._set_evidence_label(label, count)

        self._review_evidence_worker = ApiWorker(_do_fetch)
        self._review_evidence_worker.finished.connect(_on_fetched)
        self._review_evidence_worker.error.connect(
            lambda msg: (logger.warning(f"Failed to fetch evidence count: {msg}"),
                         Toast.show_toast(self, "تعذر تحميل بيانات المراجعة", Toast.ERROR))
        )
        self._review_evidence_worker.start()

    def _populate_claim_card(self):
        """Populate claim information card."""
        self._clear_layout(self.claim_content)

        # Prefer full claim_data over sparse claims list
        if self.context.claim_data:
            self.claim_content.setSpacing(10)
            claim_card = self._create_claim_data_card(self.context.claim_data)
            self.claim_content.addWidget(claim_card)
            return

        claims = getattr(self.context, 'claims', [])
        if not claims:
            no_data = QLabel(tr("wizard.review.no_claim"))
            no_data.setFont(create_font(size=FontManager.SIZE_BODY))
            no_data.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            no_data.setAlignment(Qt.AlignCenter)
            self.claim_content.addWidget(no_data)
            return

        self.claim_content.setSpacing(10)
        for claim_data in claims:
            claim_card = self._create_claim_data_card(claim_data)
            self.claim_content.addWidget(claim_card)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts by rebuilding review content."""
        self._populate_review()

    def validate(self) -> StepValidationResult:
        """Validate that all required data is present."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error(tr("wizard.review.no_building"))
        if not self.context.unit and not self.context.is_new_unit:
            result.add_error(tr("wizard.review.no_unit"))
        if len(self.context.persons) == 0:
            result.add_error(tr("wizard.review.no_persons"))

        return result

    def collect_data(self) -> Dict[str, Any]:
        return self.context.get_summary()

    def on_next(self):
        """Called when user clicks Next/Submit button. Finalize the survey via API."""
        self._set_auth_token()
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            logger.error("No survey_id found in context. Cannot finalize.")
            ErrorHandler.show_error(self, tr("wizard.review.no_survey_id"), tr("common.error"))
            return

        # Save intervieweeName before finalizing (draft endpoint only works while Draft)
        try:
            a = self.context.applicant or {}
            parts = [a.get("first_name_ar", ""), a.get("father_name_ar", ""), a.get("last_name_ar", "")]
            name = " ".join(p for p in parts if p) or a.get("full_name")
            if name:
                self._api_service.save_draft_to_backend(survey_id, {"interviewee_name": name})
        except Exception as e:
            logger.warning(f"Could not save interviewee name: {e}")
            Toast.show_toast(self, "تعذر تحميل بيانات المراجعة", Toast.ERROR)

        # Step 1: process-claims if not already done in OccupancyClaimsStep
        if not (hasattr(self.context, 'finalize_response') and self.context.finalize_response):
            self._finalize_survey_via_api(survey_id)
            if not (hasattr(self.context, 'finalize_response') and self.context.finalize_response):
                return  # process-claims failed, stop

        # Step 2: finalize the survey (S19-S21: transition to FINALIZED state)
        self._call_finalize_endpoint(survey_id)

    def _finalize_survey_via_api(self, survey_id: str):
        """Call process-claims endpoint (S17-S18)."""
        finalize_options = {
            "finalNotes": "Survey completed successfully",
            "durationMinutes": 10,
            "autoCreateClaim": True
        }
        try:
            response = self._api_service.finalize_office_survey(survey_id, finalize_options)
            logger.info(f"Survey {survey_id} process-claims succeeded")
            self.context.finalize_response = response
        except Exception as e:
            logger.error(f"Failed to process claims for survey {survey_id}: {e}")
            from services.error_mapper import map_exception
            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))

    def _call_finalize_endpoint(self, survey_id: str):
        """Call finalize endpoint to transition survey to FINALIZED state (S19-S21)."""
        try:
            self._api_service.finalize_survey_status(survey_id)
            logger.info(f"Survey {survey_id} finalized successfully")
            self.context.status = "finalized"
        except Exception as e:
            logger.error(f"Failed to finalize survey status {survey_id}: {e}")
            from services.error_mapper import map_exception
            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))

    def on_show(self):
        """Refresh summary when step is shown."""
        super().on_show()
        self._populate_review()

    def get_step_title(self) -> str:
        return tr("wizard.review.step_title")

    def get_step_description(self) -> str:
        return tr("wizard.review.step_description")
