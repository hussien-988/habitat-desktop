# -*- coding: utf-8 -*-
"""
Review Step - Step 7 of Office Survey Wizard.

Final review and submission step - displays summary cards from all previous steps.
"""

from typing import Dict, Any
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
    QHBoxLayout, QGridLayout
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.design_system import Colors
from ui.font_utils import FontManager, create_font
from ui.components.icon import Icon
from utils.logger import get_logger

logger = get_logger(__name__)


class ReviewStep(BaseStep):
    """Step 7: Review & Submit."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)

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
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {Colors.BACKGROUND};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_DEFAULT};
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {Colors.TEXT_SECONDARY};
            }}
        """)

        # Scroll content container
        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Create summary cards for each step
        self.building_card = self._create_building_card()
        scroll_layout.addWidget(self.building_card)

        self.unit_card = self._create_unit_card()
        scroll_layout.addWidget(self.unit_card)

        self.household_card = self._create_household_card()
        scroll_layout.addWidget(self.household_card)

        self.relations_card = self._create_relations_card()
        scroll_layout.addWidget(self.relations_card)

        self.claim_card = self._create_claim_card()
        scroll_layout.addWidget(self.claim_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _create_card_base(self, icon_name: str, title: str, subtitle: str) -> tuple:
        """Create base card with header (icon, title, subtitle) and return card and content layout."""
        card = QFrame()
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 12px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        # Header with icon, title, subtitle
        header_container = QWidget()
        header_container.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
            }}
        """)

        icon_pixmap = Icon.load_pixmap(icon_name, size=24)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        # Title and subtitle
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        title_label.setAlignment(Qt.AlignRight)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        subtitle_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        subtitle_label.setAlignment(Qt.AlignRight)

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        header_layout.addStretch()
        header_layout.addWidget(title_container)
        header_layout.addWidget(icon_label)

        card_layout.addWidget(header_container)

        # Content grid
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_layout = QGridLayout(content_widget)
        content_layout.setHorizontalSpacing(12)
        content_layout.setVerticalSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)

        card_layout.addWidget(content_widget)

        return card, content_layout

    def _create_field(self, label: str, value: str) -> QWidget:
        """Create a labeled field widget for displaying data."""
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Label
        label_widget = QLabel(label)
        label_widget.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label_widget.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        label_widget.setAlignment(Qt.AlignRight)

        # Value
        value_widget = QLabel(value)
        value_widget.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        value_widget.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.INPUT_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
            }}
        """)
        value_widget.setAlignment(Qt.AlignRight)
        value_widget.setWordWrap(True)

        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        return container

    def _create_building_card(self) -> QFrame:
        """Create building information summary card (Step 1)."""
        card, grid = self._create_card_base("blue", "معلومات البناء", "بيانات البناء المختار")
        self.building_grid = grid
        return card

    def _create_unit_card(self) -> QFrame:
        """Create unit information summary card (Step 2)."""
        card, grid = self._create_card_base("property", "معلومات الوحدة", "بيانات الوحدة العقارية")
        self.unit_grid = grid
        return card

    def _create_household_card(self) -> QFrame:
        """Create household information summary card (Step 3)."""
        card, grid = self._create_card_base("person-group", "معلومات الأسرة", "بيانات الأسرة والإشغال")
        self.household_grid = grid
        return card

    def _create_relations_card(self) -> QFrame:
        """Create relations information summary card (Step 5)."""
        card, grid = self._create_card_base("user-account", "العلاقات والأدلة", "علاقات الأشخاص بالوحدة")
        self.relations_grid = grid
        return card

    def _create_claim_card(self) -> QFrame:
        """Create claim information summary card (Step 6)."""
        card, grid = self._create_card_base("elements", "تسجيل الحالة", "بيانات الحالة والمطالبة")
        self.claim_grid = grid
        return card

    def _clear_grid(self, grid_layout):
        """Clear all widgets from a grid layout."""
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _populate_review(self):
        """Populate all summary cards with data from context."""
        self._populate_building_card()
        self._populate_unit_card()
        self._populate_household_card()
        self._populate_relations_card()
        self._populate_claim_card()

    def _populate_building_card(self):
        """Populate building information card."""
        self._clear_grid(self.building_grid)

        if self.context.building:
            building = self.context.building
            building_id = str(building.building_id) if hasattr(building, 'building_id') else "-"
            building_type = building.building_type_display if hasattr(building, 'building_type_display') else "-"
            address = building.address_path if hasattr(building, 'address_path') else "-"
            status = building.status_display if hasattr(building, 'status_display') else "-"

            # RTL order: rightmost field first (col 0), leftmost field last (col 3)
            self.building_grid.addWidget(self._create_field("رمز البناء", building_id), 0, 0)
            self.building_grid.addWidget(self._create_field("نوع البناء", building_type), 0, 1)
            self.building_grid.addWidget(self._create_field("العنوان", address), 0, 2)
            self.building_grid.addWidget(self._create_field("الحالة", status), 0, 3)
        else:
            self.building_grid.addWidget(self._create_field("البيانات", "لم يتم اختيار مبنى"), 0, 0)

    def _populate_unit_card(self):
        """Populate unit information card."""
        self._clear_grid(self.unit_grid)

        if self.context.unit:
            unit = self.context.unit
            unit_id = str(unit.unit_id) if hasattr(unit, 'unit_id') and unit.unit_id else "-"
            unit_type = unit.unit_type_display if hasattr(unit, 'unit_type_display') else "-"
            floor = str(unit.floor_number) if hasattr(unit, 'floor_number') and unit.floor_number else "-"
            apartment = str(unit.apartment_number) if hasattr(unit, 'apartment_number') and unit.apartment_number else "-"
        elif self.context.is_new_unit and self.context.new_unit_data:
            unit_id = "جديد"
            unit_type = self.context.new_unit_data.get('unit_type', '-')
            floor = str(self.context.new_unit_data.get('floor_number', '-'))
            apartment = str(self.context.new_unit_data.get('apartment_number', '-'))
        else:
            self.unit_grid.addWidget(self._create_field("البيانات", "لم يتم اختيار وحدة"), 0, 0)
            return

        # RTL order: rightmost field first (col 0), leftmost field last (col 3)
        self.unit_grid.addWidget(self._create_field("رقم الوحدة", unit_id), 0, 0)
        self.unit_grid.addWidget(self._create_field("نوع الوحدة", unit_type), 0, 1)
        self.unit_grid.addWidget(self._create_field("الطابق", floor), 0, 2)
        self.unit_grid.addWidget(self._create_field("رقم الشقة", apartment), 0, 3)

    def _populate_household_card(self):
        """Populate household information card."""
        self._clear_grid(self.household_grid)

        if not self.context.households:
            self.household_grid.addWidget(self._create_field("البيانات", "لم يتم تسجيل أي أسرة"), 0, 0)
            return

        num_households = str(len(self.context.households))
        total_persons = str(sum(h.get('size', 0) for h in self.context.households))
        total_adults = str(sum(h.get('adults', 0) for h in self.context.households))
        total_minors = str(sum(h.get('minors', 0) for h in self.context.households))
        head_name = self.context.households[0].get('head_name', '-') if self.context.households else "-"

        # RTL order: rightmost field first (col 0), leftmost field last (col 3)
        self.household_grid.addWidget(self._create_field("عدد الأسر", num_households), 0, 0)
        self.household_grid.addWidget(self._create_field("إجمالي الأفراد", total_persons), 0, 1)
        self.household_grid.addWidget(self._create_field("البالغين", total_adults), 0, 2)
        self.household_grid.addWidget(self._create_field("القاصرين", total_minors), 0, 3)
        self.household_grid.addWidget(self._create_field("رب الأسرة", head_name), 1, 0, 1, 2)

    def _populate_relations_card(self):
        """Populate relations information card."""
        self._clear_grid(self.relations_grid)

        if not self.context.relations:
            self.relations_grid.addWidget(self._create_field("البيانات", "لم يتم تسجيل أي علاقات"), 0, 0)
            return

        rel_type_map = {
            "owner": "مالك",
            "co_owner": "شريك",
            "tenant": "مستأجر",
            "occupant": "شاغل",
            "heir": "وارث"
        }

        num_relations = str(len(self.context.relations))
        total_evidences = str(sum(len(r.get('evidences', [])) for r in self.context.relations))
        owners = len([r for r in self.context.relations if r.get('relation_type') in ('owner', 'co_owner')])
        tenants = len([r for r in self.context.relations if r.get('relation_type') == 'tenant'])

        # RTL order: rightmost field first (col 0), leftmost field last (col 3)
        self.relations_grid.addWidget(self._create_field("عدد العلاقات", num_relations), 0, 0)
        self.relations_grid.addWidget(self._create_field("إجمالي الوثائق", total_evidences), 0, 1)
        self.relations_grid.addWidget(self._create_field("الملاك/الشركاء", str(owners)), 0, 2)
        self.relations_grid.addWidget(self._create_field("المستأجرين", str(tenants)), 0, 3)

        # Show first relation details
        if self.context.relations:
            r = self.context.relations[0]
            person_name = r.get('person_name', '-')
            relation_type = rel_type_map.get(r.get('relation_type', ''), '-')
            self.relations_grid.addWidget(self._create_field("أول شخص", person_name), 1, 0, 1, 2)
            self.relations_grid.addWidget(self._create_field("نوع العلاقة", relation_type), 1, 2, 1, 2)

    def _populate_claim_card(self):
        """Populate claim information card."""
        self._clear_grid(self.claim_grid)

        if not self.context.claim_data:
            self.claim_grid.addWidget(self._create_field("البيانات", "لم يتم إنشاء مطالبة"), 0, 0)
            return

        claim_types = {
            "ownership": "ملكية",
            "occupancy": "إشغال",
            "tenancy": "إيجار"
        }
        priorities = {
            "low": "منخفض",
            "normal": "عادي",
            "high": "عالي",
            "urgent": "عاجل"
        }
        business_types = {
            "residential": "سكني",
            "commercial": "تجاري",
            "agricultural": "زراعي"
        }
        sources = {
            "field_survey": "مسح ميداني",
            "direct_request": "طلب مباشر",
            "referral": "إحالة",
            "OFFICE_SUBMISSION": "تقديم مكتبي"
        }
        statuses = {
            "new": "جديد",
            "under_review": "قيد المراجعة",
            "completed": "مكتمل",
            "pending": "معلق"
        }

        claim_type = claim_types.get(self.context.claim_data.get('claim_type'), '-')
        priority = priorities.get(self.context.claim_data.get('priority'), '-')
        business = business_types.get(self.context.claim_data.get('business_nature'), '-')
        source = sources.get(self.context.claim_data.get('source'), '-')
        status = statuses.get(self.context.claim_data.get('case_status'), '-')
        survey_date = str(self.context.claim_data.get('survey_date', '-') or '-')
        next_date = str(self.context.claim_data.get('next_action_date', '-') or '-')

        # RTL order: rightmost field first (col 0), leftmost field last (col 3)
        self.claim_grid.addWidget(self._create_field("نوع الحالة", claim_type), 0, 0)
        self.claim_grid.addWidget(self._create_field("طبيعة الأعمال", business), 0, 1)
        self.claim_grid.addWidget(self._create_field("الأولوية", priority), 0, 2)
        self.claim_grid.addWidget(self._create_field("المصدر", source), 0, 3)
        self.claim_grid.addWidget(self._create_field("الحالة", status), 1, 0)
        self.claim_grid.addWidget(self._create_field("تاريخ المسح", survey_date), 1, 1)
        self.claim_grid.addWidget(self._create_field("تاريخ الإجراء التالي", next_date), 1, 2, 1, 2)

    def validate(self) -> StepValidationResult:
        """Validate that all required data is present."""
        result = self.create_validation_result()

        if not self.context.building:
            result.add_error("لا يوجد مبنى مختار")
        if not self.context.unit and not self.context.is_new_unit:
            result.add_error("لا يوجد وحدة مختارة")
        if len(self.context.persons) == 0:
            result.add_error("لا يوجد أشخاص مسجلين")

        return result

    def collect_data(self) -> Dict[str, Any]:
        return self.context.get_summary()

    def on_show(self):
        """Refresh summary when step is shown."""
        super().on_show()
        self._populate_review()

    def get_step_title(self) -> str:
        return "المراجعة النهائية"

    def get_step_description(self) -> str:
        return "راجع جميع البيانات المدخلة قبل الإرسال"
