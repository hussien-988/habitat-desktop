# -*- coding: utf-8 -*-
"""
Draft Office Surveys Page - UC-005 Implementation (NEW DESIGN v3)

Based on Figma Pages 3-5 - VERTICAL CARD LIST (NOT table!)
Displays list of draft office surveys as vertical cards
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QDateEdit, QMessageBox,
    QSpacerItem, QSizePolicy, QScrollArea, QDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QColor, QFont

from repositories.database import Database
from repositories.survey_repository import SurveyRepository
from repositories.building_repository import BuildingRepository
from ui.components.toast import Toast
from ui.components.ui_components import (
    Button, Input, Card, Badge, Heading, EmptyState,
    ConfirmDialog
)
from ui.design_system import Colors, Typography, Spacing, BorderRadius
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class DraftCard(QFrame):
    """
    Single draft item card (Figma pages 3-5 design)
    Light gray card with horizontal layout
    """

    clicked = pyqtSignal(dict)  # Emits draft data when clicked
    resume_clicked = pyqtSignal(dict)
    delete_clicked = pyqtSignal(dict)

    def __init__(self, draft_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.draft_data = draft_data
        self._setup_ui()

    def _setup_ui(self):
        """Setup card UI"""
        self.setObjectName("draft_card")
        self.setCursor(Qt.PointingHandCursor)

        # Card style
        self.setStyleSheet(f"""
            QFrame#draft_card {{
                background-color: {Colors.LIGHT_GRAY_BG};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.MD}px;
            }}
            QFrame#draft_card:hover {{
                background-color: {Colors.SURFACE};
                border-color: {Colors.PRIMARY_BLUE};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.MD)

        # Extract data
        context = self.draft_data.get('context', {})
        building = context.get('building', {})
        persons = context.get('persons', [])

        # Find contact person name
        contact_name = "غير محدد"
        for person in persons:
            if person.get('is_contact_person'):
                contact_name = person.get('name', 'غير محدد')
                break
        if contact_name == "غير محدد" and persons:
            contact_name = persons[0].get('name', 'غير محدد')

        # Left section - Date + Status badge
        left_section = QVBoxLayout()
        left_section.setSpacing(Spacing.XS)

        # Date
        created_at = self.draft_data.get('created_at')
        date_str = created_at.strftime('%Y-%m-%d') if created_at else 'N/A'
        date_label = QLabel(date_str)
        date_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_CAPTION}px;
        """)
        left_section.addWidget(date_label)

        # Status badge
        status_badge = QLabel("مسودة")
        status_badge.setStyleSheet(f"""
            background-color: {Colors.BADGE_DRAFT};
            color: white;
            font-size: {Typography.SIZE_CAPTION}px;
            font-weight: {Typography.WEIGHT_BOLD};
            padding: {Spacing.XS}px {Spacing.SM}px;
            border-radius: {BorderRadius.SM}px;
        """)
        status_badge.setAlignment(Qt.AlignCenter)
        status_badge.setFixedWidth(60)
        left_section.addWidget(status_badge)

        layout.addLayout(left_section)

        # Middle section - Main info
        middle_section = QVBoxLayout()
        middle_section.setSpacing(Spacing.XS)

        # Contact name
        name_label = QLabel(contact_name)
        name_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_BODY}px;
            font-weight: {Typography.WEIGHT_BOLD};
        """)
        middle_section.addWidget(name_label)

        # Building ID
        building_id = self.draft_data.get('building_id') or building.get('building_id', 'غير محدد')
        building_label = QLabel(f"المبنى: {building_id}")
        building_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_CAPTION}px;
        """)
        middle_section.addWidget(building_label)

        # Reference code
        ref_code = self.draft_data.get('reference_code', 'N/A')
        ref_label = QLabel(f"الرقم المرجعي: {ref_code}")
        ref_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_CAPTION}px;
        """)
        middle_section.addWidget(ref_label)

        layout.addLayout(middle_section, 1)

        # Right section - Action buttons
        right_section = QHBoxLayout()
        right_section.setSpacing(Spacing.SM)

        # Resume button
        resume_btn = QPushButton("استئناف")
        resume_btn.setCursor(Qt.PointingHandCursor)
        resume_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                font-size: {Typography.SIZE_CAPTION}px;
                font-weight: {Typography.WEIGHT_BOLD};
            }}
            QPushButton:hover {{
                background-color: {Colors.BUTTON_PRIMARY_HOVER};
            }}
        """)
        resume_btn.clicked.connect(lambda: self.resume_clicked.emit(self.draft_data))
        right_section.addWidget(resume_btn)

        # Delete button
        delete_btn = QPushButton("حذف")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ERROR};
                color: white;
                border: none;
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                font-size: {Typography.SIZE_CAPTION}px;
                font-weight: {Typography.WEIGHT_BOLD};
            }}
            QPushButton:hover {{
                background-color: #C0392B;
            }}
        """)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.draft_data))
        right_section.addWidget(delete_btn)

        layout.addLayout(right_section)

    def mousePressEvent(self, event):
        """Handle card click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.draft_data)
        super().mousePressEvent(event)


class DraftOfficeSurveysPage(QWidget):
    """
    Draft Office Surveys List Page - New Design v3
    Based on Figma Pages 3-5 (المسودة tab)
    Uses VERTICAL CARD LIST instead of table
    Implements UC-005 S01-S03
    """

    # Signals
    draft_selected = pyqtSignal(dict)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.survey_repo = SurveyRepository(db)
        self.building_repo = BuildingRepository(db)
        self.i18n = I18n()

        self._draft_data: List[Dict[str, Any]] = []
        self._init_ui()
        self._apply_styles()
        self._load_drafts()

    def _init_ui(self):
        """Initialize UI with new card-based design"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
                                      Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN)
        main_layout.setSpacing(Spacing.SECTION_MARGIN)

        # Header with action button
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)

        # Filter card
        filter_card = self._create_filter_card()
        main_layout.addWidget(filter_card)

        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setFont(Typography.get_body_font())
        self.stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        main_layout.addWidget(self.stats_label)

        # Scrollable card list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        # Container for cards
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(Spacing.SM)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.addStretch()

        scroll_area.setWidget(self.card_container)
        main_layout.addWidget(scroll_area, 1)

        # Empty state (shown when no data)
        self.empty_state = EmptyState(
            icon_text="➕",
            title="لا توجد مسودات بعد",
            message="ابدأ بإضافة مسودات المسوحات المكتبية لإظهارها هنا"
        )
        self.empty_state.setVisible(False)
        main_layout.addWidget(self.empty_state)

    def _create_header(self) -> QHBoxLayout:
        """Create page header"""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(Spacing.MD)

        # Title - DRY: Using unified page title styling (18pt, PAGE_TITLE color)
        from ui.font_utils import create_font, FontManager
        title = QLabel("المسودة")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        header_layout.addWidget(title)

        header_layout.addSpacerItem(
            QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # Add new draft button
        add_btn = Button("+ إضافة حالة جديدة", variant="primary", size="medium")
        header_layout.addWidget(add_btn)

        # Refresh button
        refresh_btn = Button("🔄", variant="secondary", size="medium")
        refresh_btn.clicked.connect(self._load_drafts)
        refresh_btn.setToolTip("تحديث")
        header_layout.addWidget(refresh_btn)

        return header_layout

    def _create_filter_card(self) -> Card:
        """Create filter section in a card"""
        card = Card()
        layout = QVBoxLayout()
        layout.setSpacing(Spacing.MD)

        # Filter title
        filter_label = QLabel("الفلتر")
        filter_label.setFont(Typography.get_body_font(bold=True))
        filter_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(filter_label)

        # First row: Building code + Address
        row1 = QHBoxLayout()
        row1.setSpacing(Spacing.MD)

        # Building code search
        building_col = QVBoxLayout()
        building_col.setSpacing(Spacing.LABEL_SPACING)
        building_label = QLabel("رمز المبنى")
        building_label.setFont(Typography.get_body_font())
        self.building_search = Input("ابحث عن رمز المبنى ...")
        self.building_search.textChanged.connect(self._apply_filters)
        building_col.addWidget(building_label)
        building_col.addWidget(self.building_search)
        row1.addLayout(building_col, 1)

        # Address search
        address_col = QVBoxLayout()
        address_col.setSpacing(Spacing.LABEL_SPACING)
        address_label = QLabel("العنوان")
        address_label.setFont(Typography.get_body_font())
        self.address_search = Input("ابحث عن العنوان ...")
        self.address_search.textChanged.connect(self._apply_filters)
        address_col.addWidget(address_label)
        address_col.addWidget(self.address_search)
        row1.addLayout(address_col, 1)

        layout.addLayout(row1)

        # Second row: Date range
        row2 = QHBoxLayout()
        row2.setSpacing(Spacing.MD)

        # Date from
        date_from_col = QVBoxLayout()
        date_from_col.setSpacing(Spacing.LABEL_SPACING)
        date_from_label = QLabel("من تاريخ")
        date_from_label.setFont(Typography.get_body_font())
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setStyleSheet(f"""
            QDateEdit {{
                background-color: {Colors.INPUT_BG};
                border: 2px solid {Colors.INPUT_BORDER};
                border-radius: {BorderRadius.SM}px;
                padding: 0 {Spacing.MD}px;
                font-size: {Typography.SIZE_BODY}px;
                min-height: 40px;
            }}
        """)
        self.date_from.dateChanged.connect(self._apply_filters)
        date_from_col.addWidget(date_from_label)
        date_from_col.addWidget(self.date_from)
        row2.addLayout(date_from_col, 1)

        # Date to
        date_to_col = QVBoxLayout()
        date_to_col.setSpacing(Spacing.LABEL_SPACING)
        date_to_label = QLabel("إلى تاريخ")
        date_to_label.setFont(Typography.get_body_font())
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setStyleSheet(f"""
            QDateEdit {{
                background-color: {Colors.INPUT_BG};
                border: 2px solid {Colors.INPUT_BORDER};
                border-radius: {BorderRadius.SM}px;
                padding: 0 {Spacing.MD}px;
                font-size: {Typography.SIZE_BODY}px;
                min-height: 40px;
            }}
        """)
        self.date_to.dateChanged.connect(self._apply_filters)
        date_to_col.addWidget(date_to_label)
        date_to_col.addWidget(self.date_to)
        row2.addLayout(date_to_col, 1)

        # Apply button
        apply_col = QVBoxLayout()
        apply_col.addSpacerItem(QSpacerItem(20, 23, QSizePolicy.Minimum, QSizePolicy.Fixed))
        apply_btn = Button("تطبيق", variant="primary", size="medium")
        apply_btn.clicked.connect(self._apply_filters)
        apply_col.addWidget(apply_btn)
        row2.addLayout(apply_col)

        layout.addLayout(row2)

        card.setLayout(layout)
        return card

    def _apply_styles(self):
        """Apply global page styles"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BACKGROUND};
            }}
        """)

    def _load_drafts(self):
        """Load all draft office surveys (UC-005 S01)"""
        try:
            self._draft_data = self.survey_repo.get_drafts_for_office(limit=500)
            self._populate_cards(self._draft_data)
            self._update_statistics()

            # Show/hide empty state
            if len(self._draft_data) == 0:
                self.card_container.setVisible(False)
                self.empty_state.setVisible(True)
            else:
                self.card_container.setVisible(True)
                self.empty_state.setVisible(False)

            logger.info(f"Loaded {len(self._draft_data)} draft office surveys")

        except Exception as e:
            logger.error(f"Error loading drafts: {e}")
            Toast.show_toast(self, f"خطأ في تحميل المسودات: {str(e)}", Toast.ERROR)

    def _populate_cards(self, drafts: List[Dict[str, Any]]):
        """Populate card list with draft data (Figma pages 3-5 design)"""
        # Clear existing cards
        while self.card_layout.count() > 1:  # Keep the stretch at the end
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new cards
        for draft in drafts:
            card = DraftCard(draft)
            card.resume_clicked.connect(self._resume_draft)
            card.delete_clicked.connect(self._delete_draft)
            self.card_layout.insertWidget(self.card_layout.count() - 1, card)

    def _update_statistics(self):
        """Update statistics display"""
        total = len(self._draft_data)
        self.stats_label.setText(f"📊 إجمالي المسودات: {total}")

    def _apply_filters(self):
        """Apply search filters (UC-005 S02)"""
        try:
            building_filter = self.building_search.text().strip()
            address_filter = self.address_search.text().strip()
            date_from = self.date_from.date().toPyDate()
            date_to = self.date_to.date().toPyDate()

            # Filter in memory for now (can be optimized with repo filter later)
            filtered_drafts = []
            for draft in self._draft_data:
                # Check building ID
                if building_filter:
                    building_id = draft.get('building_id', '')
                    if building_filter.lower() not in building_id.lower():
                        continue

                # Check date range
                created_at = draft.get('created_at')
                if created_at:
                    draft_date = created_at.date() if isinstance(created_at, datetime) else created_at
                    if not (date_from <= draft_date <= date_to):
                        continue

                filtered_drafts.append(draft)

            self._populate_cards(filtered_drafts)
            self.stats_label.setText(f"📊 عرض {len(filtered_drafts)} من أصل {len(self._draft_data)} مسودة")

        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            Toast.show_toast(self, f"خطأ في تطبيق الفلاتر: {str(e)}", Toast.ERROR)

    def _resume_draft(self, draft_data: Dict[str, Any]):
        """Resume selected draft (UC-005 S03)"""
        ref_code = draft_data.get('reference_code', 'N/A')

        # Use new design confirmation dialog
        dialog = ConfirmDialog(
            title="تأكيد الاستئناف",
            message=f"هل تريد استئناف المسح المسودة؟\n\nالرقم المرجعي: {ref_code}",
            icon="❓",
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            context_data = draft_data.get('context', {})
            logger.info(f"Resuming draft survey: {draft_data.get('survey_id')}")
            self.draft_selected.emit(context_data)
            Toast.show_toast(self, f"جاري استئناف المسح...\n{ref_code}", Toast.INFO)

    def _delete_draft(self, draft_data: Dict[str, Any]):
        """Delete selected draft"""
        ref_code = draft_data.get('reference_code', 'N/A')

        dialog = ConfirmDialog(
            title="تأكيد الحذف",
            message=f"هل أنت متأكد من حذف هذه المسودة؟\n\nالرقم المرجعي: {ref_code}\n\nهذا الإجراء لا يمكن التراجع عنه.",
            icon="⚠️",
            parent=self
        )

        if dialog.exec_() == QDialog.Accepted:
            try:
                survey_id = draft_data.get('survey_id')
                self.survey_repo.delete_draft(survey_id)
                logger.info(f"Deleted draft survey: {survey_id}")
                Toast.show_toast(self, "تم حذف المسودة بنجاح", Toast.SUCCESS)
                self._load_drafts()  # Reload
            except Exception as e:
                logger.error(f"Error deleting draft: {e}")
                Toast.show_toast(self, f"خطأ في حذف المسودة: {str(e)}", Toast.ERROR)

    def refresh(self, data=None):
        """Refresh the page"""
        self._load_drafts()

    def update_language(self, is_arabic: bool):
        """Update language"""
        pass
