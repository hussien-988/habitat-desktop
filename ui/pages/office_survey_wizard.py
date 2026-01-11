# -*- coding: utf-8 -*-
"""
Office Survey Wizard - UC-004 Complete Implementation.

Complete workflow for office-based property surveys including:
- Building identification and selection (with map integration)
- Property unit management (with uniqueness validation)
- Household/occupancy profiling (with adults/minors)
- Person registration (add/edit with validation)
- Relation and evidence capture (linked evidences)
- Claim creation
- Final review and submission
- Full persistence support
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, date
import uuid
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QTableView, QHeaderView,
    QAbstractItemView, QLineEdit, QComboBox, QSpinBox,
    QTextEdit, QListWidget, QListWidgetItem, QFormLayout,
    QGroupBox, QScrollArea, QSplitter, QMessageBox,
    QDialog, QFileDialog, QDateEdit, QCheckBox,
    QGraphicsDropShadowEffect, QRadioButton, QButtonGroup,
    QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QColor

from PyQt5.QtWidgets import QSizePolicy,QLayout
from PyQt5.QtWidgets import QToolButton

from app.config import Config
from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.unit_repository import UnitRepository
from repositories.person_repository import PersonRepository
from repositories.claim_repository import ClaimRepository
from repositories.survey_repository import SurveyRepository
from models.building import Building
from models.unit import PropertyUnit as Unit
from models.person import Person
from models.claim import Claim
from ui.components.toast import Toast
from ui.design_system import Colors
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Survey Context - Central data holder
# ============================================================================

class SurveyContext:
    """Holds all data for the current office survey session."""

    def __init__(self):
        self.survey_id = str(uuid.uuid4())
        self.status = "draft"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.clerk_id = None
        self.reference_number = self._generate_reference_number()

        # Selected entities
        self.building: Optional[Building] = None
        self.unit: Optional[Unit] = None
        self.is_new_unit = False
        self.new_unit_data: Optional[Dict] = None

        # Household data
        self.households: List[Dict] = []

        # Persons and relations
        self.persons: List[Dict] = []
        self.relations: List[Dict] = []

        # Claim
        self.claim_data: Optional[Dict] = None

    def _generate_reference_number(self) -> str:
        """Generate a reference number for the survey (Comment 1 in UC-004)."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        short_id = self.survey_id[:4].upper()
        return f"SRV-{timestamp}-{short_id}"

    def to_dict(self) -> Dict:
        """Serialize context to dictionary for persistence."""
        return {
            "survey_id": self.survey_id,
            "reference_number": self.reference_number,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "clerk_id": self.clerk_id,
            "building_id": self.building.building_id if self.building else None,
            "building_uuid": self.building.building_uuid if self.building else None,
            "unit_id": self.unit.unit_id if self.unit else None,
            "unit_uuid": self.unit.unit_uuid if self.unit else None,
            "is_new_unit": self.is_new_unit,
            "new_unit_data": self.new_unit_data,
            "households": self.households,
            "persons": self.persons,
            "relations": self.relations,
            "claim_data": self.claim_data
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SurveyContext':
        """Restore context from dictionary."""
        ctx = cls()
        ctx.survey_id = data.get("survey_id", ctx.survey_id)
        ctx.reference_number = data.get("reference_number", ctx.reference_number)
        ctx.status = data.get("status", "draft")
        ctx.clerk_id = data.get("clerk_id")
        ctx.is_new_unit = data.get("is_new_unit", False)
        ctx.new_unit_data = data.get("new_unit_data")
        ctx.households = data.get("households", [])
        ctx.persons = data.get("persons", [])
        ctx.relations = data.get("relations", [])
        ctx.claim_data = data.get("claim_data")
        return ctx


# ============================================================================
# Evidence Data Structure
# ============================================================================

class Evidence:
    """Evidence document linked to a relation."""

    def __init__(self, evidence_id: str = None):
        self.evidence_id = evidence_id or str(uuid.uuid4())
        self.document_type: str = "supporting_doc"
        self.document_number: Optional[str] = None
        self.issue_date: Optional[str] = None
        self.issuing_authority: Optional[str] = None
        self.file_path: Optional[str] = None
        self.file_name: Optional[str] = None
        self.notes: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "evidence_id": self.evidence_id,
            "document_type": self.document_type,
            "document_number": self.document_number,
            "issue_date": self.issue_date,
            "issuing_authority": self.issuing_authority,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "notes": self.notes
        }


# ============================================================================
# Add Evidence Dialog
# ============================================================================

class AddEvidenceDialog(QDialog):
    """Dialog for adding evidence with full metadata."""

    DOCUMENT_TYPES = [
        ("TAPU_GREEN", "صك ملكية (طابو أخضر)"),
        ("PROPERTY_REG", "بيان قيد عقاري"),
        ("COURT_RULING", "حكم قضائي"),
        ("SALE_NOTARIZED", "عقد بيع موثق"),
        ("SALE_INFORMAL", "عقد بيع غير موثق"),
        ("RENT_REGISTERED", "عقد إيجار مسجل"),
        ("RENT_INFORMAL", "عقد إيجار غير مسجل"),
        ("UTILITY_BILL", "فاتورة مرافق"),
        ("MUKHTAR_CERT", "شهادة المختار"),
        ("INHERITANCE", "حصر إرث"),
        ("WITNESS_STATEMENT", "إفادة شاهد"),
        ("OTHER", "أخرى"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_file = None
        self.setWindowTitle("إضافة دليل / وثيقة")
        self.setMinimumWidth(500)
        self._setup_ui()
        self.building_map = None


    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        form = QFormLayout()
        form.setSpacing(12)

        # Document type
        self.type_combo = QComboBox()
        for code, ar in self.DOCUMENT_TYPES:
            self.type_combo.addItem(ar, code)
        form.addRow("نوع الوثيقة:", self.type_combo)

        # Document number
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("رقم الوثيقة (اختياري)")
        form.addRow("رقم الوثيقة:", self.number_edit)

        # Issue date
        self.issue_date = QDateEdit()
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDate(QDate.currentDate())
        self.issue_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("تاريخ الإصدار:", self.issue_date)

        # Issuing authority
        self.authority_edit = QLineEdit()
        self.authority_edit.setPlaceholderText("الجهة المصدرة")
        form.addRow("الجهة المصدرة:", self.authority_edit)

        layout.addLayout(form)

        # File selection
        file_frame = QGroupBox("ملف الوثيقة")
        file_layout = QHBoxLayout(file_frame)

        self.file_label = QLabel("لم يتم اختيار ملف")
        self.file_label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
        file_layout.addWidget(self.file_label)

        browse_btn = QPushButton("استعراض...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_frame)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("ملاحظات (اختياري)")
        self.notes_edit.setMaximumHeight(80)
        layout.addWidget(self.notes_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("إضافة")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 600;
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف الوثيقة", "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.doc *.docx);;All Files (*)"
        )
        if file_path:
            self.selected_file = file_path
            from pathlib import Path
            self.file_label.setText(Path(file_path).name)
            self.file_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

    def get_evidence(self) -> Evidence:
        evidence = Evidence()
        evidence.document_type = self.type_combo.currentData()
        evidence.document_number = self.number_edit.text().strip() or None
        evidence.issue_date = self.issue_date.date().toString("yyyy-MM-dd")
        evidence.issuing_authority = self.authority_edit.text().strip() or None
        evidence.file_path = self.selected_file
        if self.selected_file:
            from pathlib import Path
            evidence.file_name = Path(self.selected_file).name
        evidence.notes = self.notes_edit.toPlainText().strip() or None
        return evidence


# ============================================================================
# Main Wizard
# ============================================================================

class OfficeSurveyWizard(QWidget):
    """
    Office Survey Wizard implementing UC-004 at 100%.

    7 Stages:
    1. Building Search & Selection (with map)
    2. Property Unit Selection/Creation (with validation)
    3. Household/Occupancy Profiling (with adults/minors)
    4. Person Registration (add/edit)
    5. Relation & Evidence Capture (linked)
    6. Claim Creation
    7. Final Review & Submit
    """

    survey_completed = pyqtSignal(str)  # Emits survey_id
    survey_cancelled = pyqtSignal()
    survey_saved_draft = pyqtSignal(str)  # Emits survey_id

    STEP_BUILDING = 0
    STEP_UNIT = 1
    STEP_HOUSEHOLD = 2
    STEP_PERSONS = 3
    STEP_RELATIONS = 4
    STEP_CLAIM = 5
    STEP_REVIEW = 6

    STEP_NAMES = [
        ("1", "تسجيل البناء"),
        ("2", "الوحدة العقارية"),
        ("3", "تفاصيل الإشغال"),
        ("4", "الأشخاص"),
        ("5", "العلاقة والأدلة"),
        ("6", "المطالبة"),
        ("7", "المراجعة النهائية"),
    ]

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n

        # Repositories
        self.building_repo = BuildingRepository(db)
        self.unit_repo = UnitRepository(db)
        self.person_repo = PersonRepository(db)
        self.claim_repo = ClaimRepository(db)
        self.survey_repo = SurveyRepository(db)

        # Survey context
        self.context = SurveyContext()
        self.current_step = 0

        # Edit tracking
        self._editing_person_index: Optional[int] = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the wizard UI."""
        CONTENT_WIDTH = 1120
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        # ===== Page header (matches design) =====
        page_header = QFrame()
        page_header.setStyleSheet("QFrame { background: transparent; }")
        #page_header.setLayoutDirection(Qt.LeftToRight)

        ph = QHBoxLayout(page_header)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(12)

        # Left: Save button (must be created BEFORE adding)
        title_widget = QWidget()
        title_widget.setLayoutDirection(Qt.RightToLeft)

        title_col = QVBoxLayout(title_widget)
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)

        page_title = QLabel("إضافة حالة جديدة")
        page_title.setStyleSheet("font-family: Noto Kufi Arabic;font-size: 20px; font-weight: 800; color: #1F2D3D; margin:0; padding:0;")
        #page_title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        breadcrumb = QLabel("المطالبات المكتملة  •  إضافة حالة جديدة")
        breadcrumb.setStyleSheet("font-family: Noto Kufi Arabic;font-size: 14px; color: #7F8C9B;font-weight: 600; padding:0; margin-top: 4px;")
        #breadcrumb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # اجعلهم نفس العرض حتى يبدأوا من نفس النقطة
        w = max(page_title.sizeHint().width(), breadcrumb.sizeHint().width())
        page_title.setFixedWidth(w)
        breadcrumb.setFixedWidth(w)

        title_col.addWidget(page_title)
        title_col.addWidget(breadcrumb)

        ph.addWidget(title_widget, 0, Qt.AlignRight)
        ph.addStretch(1)
        # Right
        self.save_btn = QPushButton("حفظ 💾")
        self.save_btn.setFixedSize(110, 44)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: 600;
                font-size: 10pt;
                font-family: Noto Kufi Arabic;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: #2A7BC9;
            }}
            QPushButton:pressed {{
                background-color: #1F68B3;
            }}
        """)
        self.save_btn.clicked.connect(self._save_as_draft)
        ph.addWidget(self.save_btn, 0, Qt.AlignLeft)

        SIDE_PAD = 90  # جرّب 120، إذا بدك أوسع خليها 140، إذا أضيق 100

        header_row = QHBoxLayout()
        header_row.setContentsMargins(SIDE_PAD, 0, SIDE_PAD, 0)
        header_row.addWidget(page_header)
        layout.addLayout(header_row)

        
        # Step indicators
        # ===== Step tabs (Navbar style) - matches design =====
        steps_frame = QFrame()
        steps_frame.setLayoutDirection(Qt.RightToLeft)
        steps_frame.setStyleSheet("QFrame { background: transparent; border: none; }")

        steps_layout = QHBoxLayout(steps_frame)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(10)

        # لتكون التبويبات على اليمين مثل التصميم

        self.step_labels = []
        for _, name in self.STEP_NAMES:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumHeight(34)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #FFFFFF;
                    border: 1px solid #F0F7FF;
                    border-radius: 17px;
                    padding: 7px 12px;
                    color: #2C3E50;
                    font-weight: 800;
                    font-size: 9pt;
                    font-family: 'Noto Kufi Arabic';
                }
            """)
            self.step_labels.append(lbl)
            steps_layout.addWidget(lbl)

        steps_layout.addStretch(1)

        steps_row = QHBoxLayout()
        steps_row.setContentsMargins(SIDE_PAD, 0, SIDE_PAD, 0)
        steps_row.addWidget(steps_frame)
        layout.addLayout(steps_row)


        # Content area
        self.content_stack = QStackedWidget()

        # Create all step widgets
        self.content_stack.addWidget(self._create_building_step())  # 0
        self.content_stack.addWidget(self._create_unit_step())      # 1
        self.content_stack.addWidget(self._create_household_step()) # 2
        self.content_stack.addWidget(self._create_persons_step())   # 3
        self.content_stack.addWidget(self._create_relations_step()) # 4
        self.content_stack.addWidget(self._create_claim_step())     # 5
        self.content_stack.addWidget(self._create_review_step())    # 6

        content_row = QHBoxLayout()
        content_row.setContentsMargins(SIDE_PAD, 0, SIDE_PAD, 0)
        content_row.addWidget(self.content_stack)
        layout.addLayout(content_row)


        # Navigation buttons
        # ===================== Footer (design card) =====================
        self.footer_frame = QFrame()
        self.footer_frame.setObjectName("wizardFooter")
        self.footer_frame.setStyleSheet("""
        QFrame#wizardFooter {
            background-color: #FFFFFF;
            border: 1px solid #E1E8ED;
            border-radius: 82px;
        }
        """)

        self.footer_frame.setLayoutDirection(Qt.LeftToRight)

        nav_layout = QHBoxLayout(self.footer_frame)
        nav_layout.setContentsMargins(16, 12, 16, 12)
        nav_layout.setSpacing(12)

        # زر السابق
        self.prev_btn = QPushButton("→ السابق")
        self.prev_btn.clicked.connect(self._on_previous)
        self.prev_btn.setEnabled(False)
        self.prev_btn.setStyleSheet("""
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #3890fd;
            border-radius: 10px;
            padding: 10px 22px;
            color: #3890fd;
            font-weight: 800;
        }
        QPushButton:disabled { color: #A0AEC0; }
        """)

        # زر التالي
        self.next_btn = QPushButton("التالي ←")
        self.next_btn.clicked.connect(self._on_next)
        self.next_btn.setEnabled(False)
        self.next_btn.setStyleSheet("""
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #3890fd;
            color: #3890fd;
            border-radius: 10px;
            padding: 12px 60px;
            font-weight: 800;
        }
        QPushButton:disabled { background-color: #; }
        """)

        # حسب التصميم: "التالي" يسار و "السابق" يمين
        nav_layout.addWidget(self.next_btn)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.prev_btn)

        layout.addWidget(self.footer_frame)

        # Update display
        self._update_step_display()

    # ==================== Step 1: Building Selection (S01-S03) ====================

    def _create_building_step(self) -> QWidget:
        """Create Step 1: Building Search and Selection (New UI)"""
        widget = QWidget()
        widget.setLayoutDirection(Qt.RightToLeft)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

    # ===== Card: Building Data =====
        card = QFrame()
        card.setObjectName("buildingCard")
        card.setStyleSheet("""
            QFrame#buildingCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card_layout.setSizeConstraint(QLayout.SetMinimumSize)
        # Header (title + subtitle)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(1)
        title = QLabel("بيانات البناء")
        title.setStyleSheet("background: transparent;font-family:'Noto Kufi Arabic'; font-size: 8pt; font-weight: 900; color:#1F2D3D;")
        subtitle = QLabel("ابحث عن معلومات البناء والموقع الجغرافي")
        subtitle.setStyleSheet("background: transparent;font-family:'Noto Kufi Arabic'; font-size: 8pt; color:#7F8C9B;")

        header_text_col.addWidget(title)
        header_text_col.addWidget(subtitle)

        icon_lbl = QLabel("📄")
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
                font-size: 16px;
            }
        """)

        header_row.addWidget(icon_lbl)
        header_row.addLayout(header_text_col)
        header_row.addStretch(1)

        card_layout.addLayout(header_row)


        # Label: building code
        code_label = QLabel("رمز البناء")
        code_label.setStyleSheet("background: transparent;font-family:'Noto Kufi Arabic'; font-size: 8pt; color:#1F2D3D; font-weight:800;")
        card_layout.addWidget(code_label)

        # One long input bar (search icon right + link left) - matches design
        # --- Search bar (one row) ---
        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setStyleSheet("""
            QFrame#searchBar {
                background-color: #F0F7FF;
                border: 1px solid #E6EEF8;
                border-radius: 18px;
            }
        """)
        search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(10,4, 10, 4)
        sb.setSpacing(8)
        # ✅ زر العدسة (يظهر داخل الحقل لأن الشريط نفسه هو الحقل)
        search_icon_btn = QToolButton()
        search_icon_btn.setText("🔍")
        search_icon_btn.setCursor(Qt.PointingHandCursor)
        search_icon_btn.setFixedSize(30, 30)
        search_icon_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #EEF6FF;
                border-radius: 8px;
            }
        """)
        search_icon_btn.clicked.connect(self._search_buildings)
                # Input
        self.building_search = QLineEdit()
        self.building_search.setPlaceholderText("ابحث عن رمز البناء ...")
        self.building_search.setLayoutDirection(Qt.RightToLeft)
        
        self.building_search.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-family: 'Noto Kufi Arabic';
                font-size: 10pt;
                padding: 0px 6px;
                min-height: 28px;
                color: #2C3E50;
                    }
        """)
        self.building_search.textChanged.connect(self._on_building_code_changed)
        self.building_search.returnPressed.connect(self._search_buildings)

        # Left link
        self.search_on_map_btn = QPushButton("بحث على الخريطة")
        self.search_on_map_btn.setCursor(Qt.PointingHandCursor)
        self.search_on_map_btn.setFlat(True)
        self.search_on_map_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #3890DF;
                font-family: 'Noto Kufi Arabic';
                font-weight: 600;
                font-size: 7pt;
                text-decoration: underline;
                padding: 0;
                margin-top: 1px;
            }
        """)
        self.search_on_map_btn.clicked.connect(self._open_map_search_dialog)



        # Search icon inside input (Action)
        sb.addWidget(self.search_on_map_btn)   # left
        sb.addWidget(self.building_search)  # middle (stretch)
        sb.addWidget(search_icon_btn,1)
        
        # Add bar to card 
        card_layout.addWidget(search_bar)


        # Suggestions list (dropdown look)
        self.buildings_list = QListWidget()
        self.buildings_list.setVisible(False)
        self.buildings_list.setMaximumHeight(170)
        self.buildings_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                background-color: #FFFFFF;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #F1F5F9;
                color: #2C3E50;
                font-family: 'Noto Kufi Arabic';
                font-size: 9pt;
            }
            QListWidget::item:selected {
                background-color: #EFF6FF;
            }
        """)
        self.buildings_list.itemClicked.connect(self._on_building_selected)
        self.buildings_list.itemDoubleClicked.connect(self._on_building_confirmed)
        card_layout.addWidget(self.buildings_list)
    

        layout.addWidget(card)
        layout.addStretch(1)


    # ===== Selected building details (New UI blocks) =====
        self.selected_building_frame = QFrame()
        self.selected_building_frame.setObjectName("selectedBuildingFrame")
        self.selected_building_frame.setStyleSheet("""
            QFrame#selectedBuildingFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 12px;
            }
        """)
        self.selected_building_frame.hide()

        sb = QVBoxLayout(self.selected_building_frame)
        sb.setContentsMargins(14, 6, 14, 6)
        sb.setSpacing(12)

        # 1) General info line (arrow 1)
        info_bar = QFrame()
        info_bar.setStyleSheet("""
            QFrame {
                background-color: #F5FAFF;
                border: 1px solid #DCE7F5;
                border-radius: 10px;
            }
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(12, 10, 12, 10)

    
        self.selected_building_label = QLabel("")
        self.selected_building_label.setStyleSheet("color: #2C3E50; font-weight: 600;")
        self.selected_building_label.setWordWrap(True)

        info_icon = QLabel("🏢")
        info_icon.setStyleSheet("font-size: 16px; color: #3890DF;")
        info_layout.addWidget(info_icon)
        info_layout.addWidget(self.selected_building_label, stretch=1)

        sb.addWidget(info_bar)

        # 2) Stats row (arrow 2) - placeholders for now (نعبّيها بالخطوة الجاية)
        stats = QFrame()
        stats.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(12)

        def _stat_block(title_text, value_text="-"):
            box = QFrame()
            box.setStyleSheet("QFrame { background: transparent; }")
            v = QVBoxLayout(box)
            v.setSpacing(4)
            t = QLabel(title_text)
            t.setStyleSheet("font-size: 12px; color: #7F8C9B; font-weight: 600;")
            val = QLabel(value_text)
            val.setStyleSheet("font-size: 13px; color: #2C3E50; font-weight: 700;")
            v.addWidget(t, alignment=Qt.AlignHCenter)
            v.addWidget(val, alignment=Qt.AlignHCenter)
            return box, val

        box_status, self.ui_building_status = _stat_block("حالة البناء")
        box_type, self.ui_building_type = _stat_block("نوع البناء")
        box_units, self.ui_units_count = _stat_block("عدد الوحدات")
        box_parcels, self.ui_parcels_count = _stat_block("عدد المقاسم")
        box_shops, self.ui_shops_count = _stat_block("عدد المحلات")

        for b in [box_status, box_type, box_units, box_parcels, box_shops]:
            stats_layout.addWidget(b, stretch=1)

        sb.addWidget(stats)

        # 3) Location card with thumbnail (arrow 3) - UI فقط الآن
        loc = QFrame()
        loc.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)
        loc_layout = QHBoxLayout(loc)
        loc_layout.setContentsMargins(12, 12, 12, 12)
        loc_layout.setSpacing(12)

        loc_text_col = QVBoxLayout()
        loc_title = QLabel("موقع البناء")
        loc_title.setStyleSheet("font-size: 12px; color: #2C3E50; font-weight: 700;")
        loc_desc = QLabel("وصف الموقع")
        loc_desc.setStyleSheet("font-size: 12px; color: #7F8C9B;")
        loc_text_col.addWidget(loc_title)
        loc_text_col.addWidget(loc_desc)
        loc_text_col.addStretch()

        loc_layout.addLayout(loc_text_col, stretch=1)

        thumb_col = QVBoxLayout()
        self.map_thumbnail = QLabel("خريطة مصغّرة")
        self.map_thumbnail.setAlignment(Qt.AlignCenter)
        self.map_thumbnail.setFixedSize(280, 120)
        self.map_thumbnail.setStyleSheet("""
            QLabel {
                background-color: #F8FAFC;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                color: #7F8C9B;
            }
        """)

        self.open_map_btn = QPushButton("قم بفتح الخريطة")
        self.open_map_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #DCE7F5;
                border-radius: 10px;
                padding: 8px 10px;
                color: #3890DF;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #EEF6FF; }
        """)
    # منربطه بالخطوة الجاية (منطق)
        self.open_map_btn.setEnabled(False)

        thumb_col.addWidget(self.map_thumbnail)
        thumb_col.addWidget(self.open_map_btn, alignment=Qt.AlignLeft)
        loc_layout.addLayout(thumb_col)

        sb.addWidget(loc)

        layout.addWidget(self.selected_building_frame)

        # Load initial buildings (نفس القديم)
        self._load_buildings()
        return widget
    def _on_building_code_changed(self):
        """UI behavior: filter + show/hide suggestions"""
        text = self.building_search.text().strip()
    # فلترة نفس القديم
        self._filter_buildings()
    # إظهار الاقتراحات فقط وقت في نص
        self.buildings_list.setVisible(bool(text))

    def _open_map_search_dialog(self):
        """Open modal dialog like the design (UI only for now)."""
        dlg = QDialog(self)
        dlg.setModal(True)
        dlg.setWindowTitle("بحث على الخريطة")
        dlg.setFixedSize(820, 420)

        dlg.setStyleSheet("""
            QDialog {
                background-color: rgba(0,0,0,120);
            }
        """)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(24, 24, 24, 24)

        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 60))
        panel.setGraphicsEffect(shadow)

        p = QVBoxLayout(panel)
        p.setContentsMargins(18, 18, 18, 18)
        p.setSpacing(12)

        title = QLabel("بحث على الخريطة")
        title.setStyleSheet("font-size: 14px; font-weight: 800; color: #2C3E50;")
        p.addWidget(title, alignment=Qt.AlignRight)

        # Search row (UI only)
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_input = QLineEdit()
        search_input.setPlaceholderText("ابحث عن اسم المنطقة ...")
        search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                padding: 10px 12px;
            }
        """)
        search_btn = QPushButton("🔍")
        search_btn.setFixedWidth(44)
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #F8FAFC; }
        """)
        search_row.addWidget(search_btn)
        search_row.addWidget(search_input, stretch=1)
        p.addLayout(search_row)

    # Map view (reuse existing loader)
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            self.building_map = QWebEngineView()
            self.building_map.setMinimumHeight(260)
            p.addWidget(self.building_map)
            self._load_buildings_map()
        except ImportError:
            placeholder = QLabel("🗺️ الخريطة غير متاحة (QtWebEngine غير مثبت)")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("""
                QLabel {
                    background-color: #F8FAFC;
                    border: 1px solid #E1E8ED;
                    border-radius: 10px;
                    padding: 40px;
                    color: #7F8C9B;
                }
            """)
            p.addWidget(placeholder)

        outer.addWidget(panel)
        dlg.exec_()


    def _load_buildings_map(self):
        """Load interactive map for building selection (S02) - OFFLINE VERSION."""
        if not hasattr(self, "building_map") or self.building_map is None:
            # Map view is created inside the dialog, so nothing to load yet.
            return

        # Use the shared tile server from MapPickerDialog
        from ui.components.map_picker_dialog import MapPickerDialog

        # Ensure tile server is started
        if MapPickerDialog._tile_server_port is None:
            temp_dialog = MapPickerDialog.__new__(MapPickerDialog)
            temp_dialog._start_tile_server()

        tile_server_url = f"http://127.0.0.1:{MapPickerDialog._tile_server_port}"

        # Get buildings with coordinates
        buildings = self.building_repo.get_all(limit=200)
        markers_js = ""

        for b in buildings:
            if hasattr(b, 'latitude') and b.latitude and hasattr(b, 'longitude') and b.longitude:
                # Use building_type_display if available
                building_type = getattr(b, 'building_type_display', getattr(b, 'building_type', 'مبنى'))
                markers_js += f"""
                    var marker_{b.building_id.replace('-', '_')} = L.marker([{b.latitude}, {b.longitude}])
                        .addTo(map)
                        .bindPopup('<b>{b.building_id}</b><br>{building_type}');
                    marker_{b.building_id.replace('-', '_')}.on('click', function() {{
                        selectBuilding('{b.building_id}');
                    }});
                """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="{tile_server_url}/leaflet.js"></script>
    <script>
        var map = L.map('map', {{
            preferCanvas: true,
            zoomAnimation: true,
            fadeAnimation: false
        }}).setView([36.2, 37.15], 13);

        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 18,
            minZoom: 12,
            attribution: 'UN-Habitat Syria - يعمل بدون اتصال بالإنترنت',
            updateWhenIdle: true,
            keepBuffer: 2,
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        }}).addTo(map);

        {markers_js}

        function selectBuilding(buildingId) {{
            // Would communicate with Python via QWebChannel
            console.log('Selected building: ' + buildingId);
        }}
    </script>
</body>
</html>
"""
        self.building_map.setHtml(html)

    def _load_buildings(self):
        """Load buildings into the list."""
        buildings = self.building_repo.get_all(limit=100)
        self.buildings_list.clear()

        for building in buildings:
            item = QListWidgetItem(
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display} | "
                f"الحالة: {building.building_status_display}"
            )
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _filter_buildings(self):
        """Filter buildings list based on search text."""
        search_text = self.building_search.text().lower()
        for i in range(self.buildings_list.count()):
            item = self.buildings_list.item(i)
            item.setHidden(search_text not in item.text().lower())

    def _search_buildings(self):
        """Search buildings from database."""
        search = self.building_search.text().strip()
        

        if search:
            buildings = self.building_repo.search(building_id=search, limit=50)
        else:
            buildings = self.building_repo.get_all(limit=100)

        self.buildings_list.clear()
        for building in buildings:
            item = QListWidgetItem(
                f"🏢 {building.building_id} | "
                f"النوع: {building.building_type_display}"
            )
            item.setData(Qt.UserRole, building)
            self.buildings_list.addItem(item)

    def _on_building_selected(self, item):
        """Handle building selection."""
        building = item.data(Qt.UserRole)
        self.context.building = building

        self.selected_building_label.setText(
            f"✅ المبنى المحدد: {building.building_id}\n"
            f"النوع: {building.building_type_display} | "
            f"الحالة: {building.building_status_display}"
        )
        self.selected_building_frame.show()
        self.next_btn.setEnabled(True)

    def _on_building_confirmed(self, item):
        """Double-click to confirm and proceed."""
        self._on_building_selected(item)
        self._on_next()

    # ==================== Step 2: Unit Selection (S04-S06) ====================

    def _create_unit_step(self) -> QWidget:
        """Create Step 2: Property Unit Selection with uniqueness validation (S04-S06)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Selected building reminder
        self.unit_building_label = QLabel("")
        self.unit_building_label.setStyleSheet(f"""
            background-color: #F0F9FF;
            padding: 10px;
            border-radius: 6px;
            color: {Config.INFO_COLOR};
            font-weight: bold;
        """)
        layout.addWidget(self.unit_building_label)

        # Options: Select existing or create new
        options_group = QGroupBox("اختيار الوحدة العقارية")
        options_layout = QVBoxLayout(options_group)

        self.unit_existing_radio = QRadioButton("اختيار وحدة موجودة")
        self.unit_existing_radio.setChecked(True)
        self.unit_existing_radio.toggled.connect(self._on_unit_option_changed)
        options_layout.addWidget(self.unit_existing_radio)

        self.unit_new_radio = QRadioButton("إنشاء وحدة جديدة")
        self.unit_new_radio.toggled.connect(self._on_unit_option_changed)
        options_layout.addWidget(self.unit_new_radio)

        layout.addWidget(options_group)

        # Existing units list
        self.existing_units_frame = QFrame()
        eu_layout = QVBoxLayout(self.existing_units_frame)

        eu_label = QLabel("الوحدات الموجودة في المبنى:")
        eu_label.setStyleSheet("font-weight: bold;")
        eu_layout.addWidget(eu_label)

        self.units_list = QListWidget()
        self.units_list.setStyleSheet("""
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background-color: #DBEAFE; }
        """)
        self.units_list.itemClicked.connect(self._on_unit_selected)
        eu_layout.addWidget(self.units_list)

        layout.addWidget(self.existing_units_frame)

        # New unit form with validation
        self.new_unit_frame = QFrame()
        self.new_unit_frame.hide()
        self.new_unit_frame.setStyleSheet("""
            QFrame { background-color: #F8FAFC; border-radius: 8px; padding: 12px; }
        """)
        nu_layout = QFormLayout(self.new_unit_frame)
        nu_layout.setSpacing(12)

        self.unit_type_combo = QComboBox()
        unit_types = [
            ("apartment", "شقة"), ("shop", "محل تجاري"), ("office", "مكتب"),
            ("warehouse", "مستودع"), ("garage", "مرآب"), ("basement", "قبو"),
            ("roof", "سطح"), ("other", "أخرى")
        ]
        for code, ar in unit_types:
            self.unit_type_combo.addItem(ar, code)
        nu_layout.addRow("نوع الوحدة:", self.unit_type_combo)

        self.floor_spin = QSpinBox()
        self.floor_spin.setRange(-3, 100)
        nu_layout.addRow("رقم الطابق:", self.floor_spin)

        self.apt_number = QLineEdit()
        self.apt_number.setPlaceholderText("مثال: 101")
        self.apt_number.textChanged.connect(self._check_unit_uniqueness)
        nu_layout.addRow("رقم الوحدة:", self.apt_number)

        # Uniqueness indicator
        self.unit_uniqueness_label = QLabel("")
        nu_layout.addRow("", self.unit_uniqueness_label)

        self.unit_area = QSpinBox()
        self.unit_area.setRange(0, 10000)
        self.unit_area.setSuffix(" م²")
        nu_layout.addRow("المساحة:", self.unit_area)

        self.unit_rooms = QSpinBox()
        self.unit_rooms.setRange(0, 20)
        nu_layout.addRow("عدد الغرف:", self.unit_rooms)

        self.unit_desc = QTextEdit()
        self.unit_desc.setMaximumHeight(60)
        self.unit_desc.setPlaceholderText("وصف إضافي للوحدة...")
        nu_layout.addRow("الوصف:", self.unit_desc)

        layout.addWidget(self.new_unit_frame)
        layout.addStretch()

        return widget

    def _check_unit_uniqueness(self):
        """Check if unit number is unique within building (S06 validation)."""
        if not self.context.building or not self.apt_number.text().strip():
            self.unit_uniqueness_label.setText("")
            return

        unit_number = self.apt_number.text().strip()
        floor = self.floor_spin.value()

        # Check existing units
        existing_units = self.unit_repo.get_by_building(self.context.building.building_id)
        is_unique = True

        for unit in existing_units:
            if (hasattr(unit, 'apartment_number') and unit.apartment_number == unit_number and
                hasattr(unit, 'floor_number') and unit.floor_number == floor):
                is_unique = False
                break

        if is_unique:
            self.unit_uniqueness_label.setText("✅ رقم الوحدة متاح")
            self.unit_uniqueness_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")
            self.next_btn.setEnabled(True)
        else:
            self.unit_uniqueness_label.setText("❌ يوجد وحدة بنفس الرقم والطابق")
            self.unit_uniqueness_label.setStyleSheet(f"color: {Config.ERROR_COLOR};")
            self.next_btn.setEnabled(False)

    def _on_unit_option_changed(self):
        """Handle unit option radio change."""
        if self.unit_existing_radio.isChecked():
            self.existing_units_frame.show()
            self.new_unit_frame.hide()
            self.context.is_new_unit = False
            self.next_btn.setEnabled(self.context.unit is not None)
        else:
            self.existing_units_frame.hide()
            self.new_unit_frame.show()
            self.context.is_new_unit = True
            self._check_unit_uniqueness()

    def _load_units_for_building(self):
        """Load units for the selected building."""
        if not self.context.building:
            return

        self.unit_building_label.setText(
            f"🏢 المبنى المحدد: {self.context.building.building_id}"
        )

        units = self.unit_repo.get_by_building(self.context.building.building_id)
        self.units_list.clear()

        if units:
            for unit in units:
                item = QListWidgetItem(
                    f"🏠 {unit.unit_id} | "
                    f"النوع: {unit.unit_type_display} | "
                    f"الطابق: {unit.floor_number or '-'}"
                )
                item.setData(Qt.UserRole, unit)
                self.units_list.addItem(item)
        else:
            item = QListWidgetItem("📭 لا توجد وحدات مسجلة - اختر 'إنشاء وحدة جديدة'")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor(Config.TEXT_LIGHT))
            self.units_list.addItem(item)

    def _on_unit_selected(self, item):
        """Handle unit selection."""
        unit = item.data(Qt.UserRole)
        if unit:
            self.context.unit = unit
            self.next_btn.setEnabled(True)

    def _save_new_unit_data(self):
        """Save new unit data to context."""
        if self.context.is_new_unit:
            self.context.new_unit_data = {
                "unit_type": self.unit_type_combo.currentData(),
                "floor_number": self.floor_spin.value(),
                "apartment_number": self.apt_number.text().strip(),
                "area": self.unit_area.value(),
                "rooms": self.unit_rooms.value(),
                "description": self.unit_desc.toPlainText().strip(),
                "building_id": self.context.building.building_id if self.context.building else None
            }

    # ==================== Step 3: Household (S07-S10) ====================

    def _create_household_step(self) -> QWidget:
        """Create Step 3: Household/Occupancy with adults/minors (S07-S10)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Unit info
        self.household_unit_label = QLabel("")
        self.household_unit_label.setStyleSheet(f"""
            background-color: #F0F9FF;
            padding: 10px;
            border-radius: 6px;
        """)
        layout.addWidget(self.household_unit_label)

        # Splitter for list and form
        splitter = QSplitter(Qt.Horizontal)

        # Left: Households list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)

        hh_header = QHBoxLayout()
        hh_label = QLabel("الأسر المقيمة:")
        hh_label.setStyleSheet("font-weight: bold;")
        hh_header.addWidget(hh_label)
        hh_header.addStretch()

        add_hh_btn = QPushButton("+ إضافة أسرة")
        add_hh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
        """)
        add_hh_btn.clicked.connect(self._add_household)
        hh_header.addWidget(add_hh_btn)

        list_layout.addLayout(hh_header)

        self.households_list = QListWidget()
        self.households_list.setStyleSheet("QListWidget::item { padding: 10px; }")
        self.households_list.itemClicked.connect(self._on_household_selected)
        list_layout.addWidget(self.households_list)

        # Delete household button
        del_hh_btn = QPushButton("🗑️ حذف الأسرة المحددة")
        del_hh_btn.clicked.connect(self._delete_household)
        list_layout.addWidget(del_hh_btn)

        splitter.addWidget(list_frame)

        # Right: Household form
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #F8FAFC; border-radius: 8px; padding: 12px;")
        form_layout = QVBoxLayout(form_frame)

        form_title = QLabel("بيانات الأسرة")
        form_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        form_layout.addWidget(form_title)

        hh_form = QFormLayout()
        hh_form.setSpacing(10)

        self.hh_head_name = QLineEdit()
        self.hh_head_name.setPlaceholderText("اسم رب الأسرة")
        hh_form.addRow("رب الأسرة:", self.hh_head_name)

        # Adults/Minors breakdown (Medium priority gap)
        age_group = QGroupBox("التوزيع العمري")
        age_layout = QFormLayout(age_group)

        self.hh_adults = QSpinBox()
        self.hh_adults.setRange(0, 50)
        self.hh_adults.setValue(1)
        self.hh_adults.valueChanged.connect(self._update_household_size)
        age_layout.addRow("بالغون (18+):", self.hh_adults)

        self.hh_minors = QSpinBox()
        self.hh_minors.setRange(0, 50)
        self.hh_minors.valueChanged.connect(self._update_household_size)
        age_layout.addRow("قاصرون (<18):", self.hh_minors)

        hh_form.addRow(age_group)

        # Gender breakdown
        gender_group = QGroupBox("التوزيع حسب الجنس")
        gender_layout = QFormLayout(gender_group)

        self.hh_males = QSpinBox()
        self.hh_males.setRange(0, 50)
        self.hh_males.valueChanged.connect(self._update_household_size)
        gender_layout.addRow("ذكور:", self.hh_males)

        self.hh_females = QSpinBox()
        self.hh_females.setRange(0, 50)
        self.hh_females.valueChanged.connect(self._update_household_size)
        gender_layout.addRow("إناث:", self.hh_females)

        hh_form.addRow(gender_group)

        # Auto-computed size (Low priority gap)
        self.hh_size_label = QLabel("الحجم الإجمالي: 1")
        self.hh_size_label.setStyleSheet(f"font-weight: bold; color: {Config.PRIMARY_COLOR};")
        hh_form.addRow("", self.hh_size_label)

        self.hh_vulnerable = QSpinBox()
        self.hh_vulnerable.setRange(0, 20)
        hh_form.addRow("الفئات الهشة:", self.hh_vulnerable)

        form_layout.addLayout(hh_form)

        # Save button
        save_hh_btn = QPushButton("💾 حفظ بيانات الأسرة")
        save_hh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }}
        """)
        save_hh_btn.clicked.connect(self._save_household)
        form_layout.addWidget(save_hh_btn)

        form_layout.addStretch()
        splitter.addWidget(form_frame)

        splitter.setSizes([300, 400])
        layout.addWidget(splitter)

        return widget

    def _update_household_size(self):
        """Auto-compute household size (Low priority gap)."""
        total = self.hh_adults.value() + self.hh_minors.value()
        self.hh_size_label.setText(f"الحجم الإجمالي: {total}")

        # Validate gender matches total
        gender_total = self.hh_males.value() + self.hh_females.value()
        if gender_total > 0 and gender_total != total:
            self.hh_size_label.setStyleSheet(f"font-weight: bold; color: {Config.WARNING_COLOR};")
            self.hh_size_label.setText(f"الحجم الإجمالي: {total} ⚠️ (الجنس: {gender_total})")
        else:
            self.hh_size_label.setStyleSheet(f"font-weight: bold; color: {Config.PRIMARY_COLOR};")

    def _add_household(self):
        """Add a new household entry."""
        self._editing_household_index = None
        self.hh_head_name.clear()
        self.hh_adults.setValue(1)
        self.hh_minors.setValue(0)
        self.hh_males.setValue(0)
        self.hh_females.setValue(0)
        self.hh_vulnerable.setValue(0)
        self._update_household_size()
        Toast.show_toast(self, "أدخل بيانات الأسرة الجديدة", Toast.INFO)

    def _on_household_selected(self, item):
        """Load household data for editing."""
        hh_id = item.data(Qt.UserRole)
        for i, hh in enumerate(self.context.households):
            if hh['household_id'] == hh_id:
                self._editing_household_index = i
                self.hh_head_name.setText(hh['head_name'])
                self.hh_adults.setValue(hh.get('adults', hh.get('size', 1)))
                self.hh_minors.setValue(hh.get('minors', 0))
                self.hh_males.setValue(hh.get('male_count', 0))
                self.hh_females.setValue(hh.get('female_count', 0))
                self.hh_vulnerable.setValue(hh.get('vulnerable_count', 0))
                self._update_household_size()
                break

    def _save_household(self):
        """Save current household data."""
        if not self.hh_head_name.text().strip():
            QMessageBox.warning(self, "خطأ", "يجب إدخال اسم رب الأسرة")
            return

        household = {
            "household_id": str(uuid.uuid4()) if not hasattr(self, '_editing_household_index') or self._editing_household_index is None else self.context.households[self._editing_household_index]['household_id'],
            "head_name": self.hh_head_name.text().strip(),
            "size": self.hh_adults.value() + self.hh_minors.value(),
            "adults": self.hh_adults.value(),
            "minors": self.hh_minors.value(),
            "male_count": self.hh_males.value(),
            "female_count": self.hh_females.value(),
            "vulnerable_count": self.hh_vulnerable.value()
        }

        if hasattr(self, '_editing_household_index') and self._editing_household_index is not None:
            self.context.households[self._editing_household_index] = household
            Toast.show_toast(self, "تم تحديث بيانات الأسرة", Toast.SUCCESS)
        else:
            self.context.households.append(household)
            Toast.show_toast(self, "تم إضافة الأسرة", Toast.SUCCESS)

        self._refresh_households_list()
        self._add_household()  # Clear form
        self.next_btn.setEnabled(True)

    def _delete_household(self):
        """Delete selected household."""
        current = self.households_list.currentItem()
        if not current:
            return

        hh_id = current.data(Qt.UserRole)
        self.context.households = [h for h in self.context.households if h['household_id'] != hh_id]
        self._refresh_households_list()
        self._add_household()
        Toast.show_toast(self, "تم حذف الأسرة", Toast.INFO)

    def _refresh_households_list(self):
        """Refresh the households display list."""
        self.households_list.clear()
        for hh in self.context.households:
            item = QListWidgetItem(
                f"👨‍👩‍👧‍👦 {hh['head_name']}\n"
                f"   الحجم: {hh['size']} (بالغون: {hh.get('adults', '-')}, قاصرون: {hh.get('minors', '-')})"
            )
            item.setData(Qt.UserRole, hh['household_id'])
            self.households_list.addItem(item)

    # ==================== Step 4: Persons (S11-S13) ====================

    def _create_persons_step(self) -> QWidget:
        """Create Step 4: Person Registration with Edit support (S11-S13)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Splitter for list and form
        splitter = QSplitter(Qt.Horizontal)

        # Left: Persons list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)

        persons_header = QHBoxLayout()
        persons_label = QLabel("الأشخاص المسجلون:")
        persons_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        persons_header.addWidget(persons_label)
        persons_header.addStretch()

        add_person_btn = QPushButton("+ إضافة شخص")
        add_person_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }}
        """)
        add_person_btn.clicked.connect(self._add_person)
        persons_header.addWidget(add_person_btn)

        list_layout.addLayout(persons_header)

        self.persons_list = QListWidget()
        self.persons_list.setStyleSheet("""
            QListWidget::item { padding: 12px; }
            QListWidget::item:selected { background-color: #DBEAFE; }
        """)
        self.persons_list.itemClicked.connect(self._on_person_selected)
        list_layout.addWidget(self.persons_list)

        # Delete person button
        del_person_btn = QPushButton("🗑️ حذف الشخص المحدد")
        del_person_btn.clicked.connect(self._delete_person)
        list_layout.addWidget(del_person_btn)

        splitter.addWidget(list_frame)

        # Right: Person form
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #F8FAFC; border-radius: 8px; padding: 12px;")
        form_layout = QVBoxLayout(form_frame)

        self.person_form_title = QLabel("إضافة شخص جديد")
        self.person_form_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        form_layout.addWidget(self.person_form_title)

        pf_layout = QFormLayout()
        pf_layout.setSpacing(10)

        self.person_first_name = QLineEdit()
        self.person_first_name.setPlaceholderText("الاسم الأول *")
        pf_layout.addRow("الاسم الأول:", self.person_first_name)

        self.person_father_name = QLineEdit()
        self.person_father_name.setPlaceholderText("اسم الأب")
        pf_layout.addRow("اسم الأب:", self.person_father_name)

        self.person_last_name = QLineEdit()
        self.person_last_name.setPlaceholderText("اسم العائلة *")
        pf_layout.addRow("اسم العائلة:", self.person_last_name)

        self.person_national_id = QLineEdit()
        self.person_national_id.setPlaceholderText("11 رقم")
        self.person_national_id.setMaxLength(11)
        self.person_national_id.textChanged.connect(self._validate_national_id)
        pf_layout.addRow("الرقم الوطني:", self.person_national_id)

        # National ID validation indicator (Medium priority gap)
        self.national_id_status = QLabel("")
        pf_layout.addRow("", self.national_id_status)

        self.person_gender = QComboBox()
        self.person_gender.addItem("ذكر", "male")
        self.person_gender.addItem("أنثى", "female")
        pf_layout.addRow("الجنس:", self.person_gender)

        self.person_birth_date = QDateEdit()
        self.person_birth_date.setCalendarPopup(True)
        self.person_birth_date.setDate(QDate(1980, 1, 1))
        self.person_birth_date.setDisplayFormat("yyyy-MM-dd")
        pf_layout.addRow("تاريخ الميلاد:", self.person_birth_date)

        self.person_phone = QLineEdit()
        self.person_phone.setPlaceholderText("رقم الهاتف")
        pf_layout.addRow("الهاتف:", self.person_phone)

        # Link to household
        self.person_household_combo = QComboBox()
        self.person_household_combo.addItem("-- غير مرتبط --", None)
        pf_layout.addRow("الأسرة:", self.person_household_combo)

        self.person_is_contact = QCheckBox("شخص التواصل الرئيسي")
        pf_layout.addRow("", self.person_is_contact)

        form_layout.addLayout(pf_layout)

        # Save button
        save_person_btn = QPushButton("💾 حفظ بيانات الشخص")
        save_person_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }}
        """)
        save_person_btn.clicked.connect(self._save_person)
        form_layout.addWidget(save_person_btn)

        form_layout.addStretch()
        splitter.addWidget(form_frame)

        splitter.setSizes([350, 400])
        layout.addWidget(splitter)

        return widget

    def _validate_national_id(self):
        """Validate national ID uniqueness (Medium priority gap)."""
        nid = self.person_national_id.text().strip()

        if not nid:
            self.national_id_status.setText("")
            return

        if len(nid) != 11 or not nid.isdigit():
            self.national_id_status.setText("⚠️ يجب أن يكون 11 رقم")
            self.national_id_status.setStyleSheet(f"color: {Config.WARNING_COLOR};")
            return

        # Check in current context
        for i, p in enumerate(self.context.persons):
            if p.get('national_id') == nid:
                if self._editing_person_index is not None and i == self._editing_person_index:
                    continue
                self.national_id_status.setText("❌ الرقم موجود مسبقاً")
                self.national_id_status.setStyleSheet(f"color: {Config.ERROR_COLOR};")
                return

        # Check in database
        existing = self.person_repo.get_by_national_id(nid)
        if existing:
            self.national_id_status.setText("⚠️ موجود في قاعدة البيانات")
            self.national_id_status.setStyleSheet(f"color: {Config.WARNING_COLOR};")
        else:
            self.national_id_status.setText("✅ الرقم متاح")
            self.national_id_status.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

    def _populate_household_combo(self):
        """Populate household combo for person linking."""
        self.person_household_combo.clear()
        self.person_household_combo.addItem("-- غير مرتبط --", None)
        for hh in self.context.households:
            self.person_household_combo.addItem(f"👨‍👩‍👧‍👦 {hh['head_name']}", hh['household_id'])

    def _add_person(self):
        """Clear form for adding new person."""
        self._editing_person_index = None
        self.person_form_title.setText("إضافة شخص جديد")
        self.person_first_name.clear()
        self.person_father_name.clear()
        self.person_last_name.clear()
        self.person_national_id.clear()
        self.person_phone.clear()
        self.person_is_contact.setChecked(False)
        self.person_birth_date.setDate(QDate(1980, 1, 1))
        self.national_id_status.setText("")
        self._populate_household_combo()
        Toast.show_toast(self, "أدخل بيانات الشخص الجديد", Toast.INFO)

    def _on_person_selected(self, item):
        """Load person data for editing (S12 - Edit Person)."""
        person_id = item.data(Qt.UserRole)
        for i, person in enumerate(self.context.persons):
            if person['person_id'] == person_id:
                self._editing_person_index = i
                self.person_form_title.setText("✏️ تعديل بيانات الشخص")

                self.person_first_name.setText(person['first_name'])
                self.person_father_name.setText(person.get('father_name', ''))
                self.person_last_name.setText(person['last_name'])
                self.person_national_id.setText(person.get('national_id') or '')
                self.person_phone.setText(person.get('phone') or '')
                self.person_is_contact.setChecked(person.get('is_contact_person', False))

                # Set gender
                idx = self.person_gender.findData(person.get('gender', 'male'))
                if idx >= 0:
                    self.person_gender.setCurrentIndex(idx)

                # Set birth date
                if person.get('birth_date'):
                    self.person_birth_date.setDate(QDate.fromString(person['birth_date'], "yyyy-MM-dd"))
                elif person.get('year_of_birth'):
                    self.person_birth_date.setDate(QDate(person['year_of_birth'], 1, 1))

                # Set household
                self._populate_household_combo()
                hh_id = person.get('household_id')
                if hh_id:
                    idx = self.person_household_combo.findData(hh_id)
                    if idx >= 0:
                        self.person_household_combo.setCurrentIndex(idx)

                self._validate_national_id()
                break

    def _save_person(self):
        """Save person data to context."""
        if not self.person_first_name.text().strip():
            QMessageBox.warning(self, "خطأ", "يجب إدخال الاسم الأول")
            return

        if not self.person_last_name.text().strip():
            QMessageBox.warning(self, "خطأ", "يجب إدخال اسم العائلة")
            return

        person = {
            "person_id": str(uuid.uuid4()) if self._editing_person_index is None else self.context.persons[self._editing_person_index]['person_id'],
            "first_name": self.person_first_name.text().strip(),
            "father_name": self.person_father_name.text().strip(),
            "last_name": self.person_last_name.text().strip(),
            "national_id": self.person_national_id.text().strip() or None,
            "gender": self.person_gender.currentData(),
            "birth_date": self.person_birth_date.date().toString("yyyy-MM-dd"),
            "year_of_birth": self.person_birth_date.date().year(),
            "phone": self.person_phone.text().strip() or None,
            "is_contact_person": self.person_is_contact.isChecked(),
            "household_id": self.person_household_combo.currentData()
        }

        if self._editing_person_index is not None:
            self.context.persons[self._editing_person_index] = person
            Toast.show_toast(self, "تم تحديث بيانات الشخص", Toast.SUCCESS)
        else:
            self.context.persons.append(person)
            Toast.show_toast(self, "تم إضافة الشخص", Toast.SUCCESS)

        self._refresh_persons_list()
        self._add_person()
        self.next_btn.setEnabled(True)

    def _delete_person(self):
        """Delete selected person."""
        current = self.persons_list.currentItem()
        if not current:
            return

        person_id = current.data(Qt.UserRole)

        # Check if person has relations
        has_relations = any(r['person_id'] == person_id for r in self.context.relations)
        if has_relations:
            reply = QMessageBox.question(
                self, "تحذير",
                "هذا الشخص مرتبط بعلاقات. سيتم حذف العلاقات أيضاً.\nهل تريد المتابعة؟",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # Remove relations
            self.context.relations = [r for r in self.context.relations if r['person_id'] != person_id]

        self.context.persons = [p for p in self.context.persons if p['person_id'] != person_id]
        self._refresh_persons_list()
        self._add_person()
        Toast.show_toast(self, "تم حذف الشخص", Toast.INFO)

    def _refresh_persons_list(self):
        """Refresh persons display list."""
        self.persons_list.clear()
        for person in self.context.persons:
            full_name = f"{person['first_name']} {person.get('father_name', '')} {person['last_name']}".strip()
            contact_badge = "📞 " if person.get('is_contact_person') else ""
            nid = person.get('national_id') or 'غير متوفر'
            item = QListWidgetItem(
                f"{contact_badge}👤 {full_name}\n"
                f"   الرقم الوطني: {nid}"
            )
            item.setData(Qt.UserRole, person['person_id'])
            self.persons_list.addItem(item)

    # ==================== Step 5: Relations (S14-S16) ====================

    def _create_relations_step(self) -> QWidget:
        """Create Step 5: Relations with linked Evidence (S14-S16)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Info
        info_label = QLabel(
            "حدد نوع علاقة كل شخص بالوحدة العقارية وأضف الأدلة الداعمة لكل علاقة"
        )
        info_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; padding: 8px;")
        layout.addWidget(info_label)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: Relations list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)

        rel_header = QHBoxLayout()
        rel_label = QLabel("العلاقات المسجلة:")
        rel_label.setStyleSheet("font-weight: bold;")
        rel_header.addWidget(rel_label)
        rel_header.addStretch()

        add_rel_btn = QPushButton("+ إضافة علاقة")
        add_rel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
        """)
        add_rel_btn.clicked.connect(self._add_relation)
        rel_header.addWidget(add_rel_btn)

        list_layout.addLayout(rel_header)

        self.relations_list = QListWidget()
        self.relations_list.setStyleSheet("QListWidget::item { padding: 10px; }")
        self.relations_list.itemClicked.connect(self._on_relation_selected)
        list_layout.addWidget(self.relations_list)

        del_rel_btn = QPushButton("🗑️ حذف العلاقة المحددة")
        del_rel_btn.clicked.connect(self._delete_relation)
        list_layout.addWidget(del_rel_btn)

        splitter.addWidget(list_frame)

        # Right: Relation form
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #F8FAFC; border-radius: 8px; padding: 12px;")
        form_layout = QVBoxLayout(form_frame)

        # Relation details
        rel_form_group = QGroupBox("تفاصيل العلاقة")
        rel_form = QFormLayout(rel_form_group)

        self.rel_person_combo = QComboBox()
        rel_form.addRow("الشخص:", self.rel_person_combo)

        self.rel_type_combo = QComboBox()
        rel_types = [
            ("owner", "مالك"), ("co_owner", "شريك في الملكية"),
            ("tenant", "مستأجر"), ("occupant", "شاغل"),
            ("heir", "وارث"), ("guardian", "ولي/وصي"), ("other", "أخرى")
        ]
        for code, ar in rel_types:
            self.rel_type_combo.addItem(ar, code)
        rel_form.addRow("نوع العلاقة:", self.rel_type_combo)

        self.rel_share = QSpinBox()
        self.rel_share.setRange(0, 2400)
        self.rel_share.setValue(2400)
        self.rel_share.setSuffix(" / 2400")
        rel_form.addRow("حصة الملكية:", self.rel_share)

        self.rel_start_date = QDateEdit()
        self.rel_start_date.setCalendarPopup(True)
        self.rel_start_date.setDate(QDate.currentDate())
        rel_form.addRow("تاريخ البداية:", self.rel_start_date)

        # Contract details (Low priority gap)
        self.rel_contract_number = QLineEdit()
        self.rel_contract_number.setPlaceholderText("رقم العقد (اختياري)")
        rel_form.addRow("رقم العقد:", self.rel_contract_number)

        self.rel_contract_date = QDateEdit()
        self.rel_contract_date.setCalendarPopup(True)
        self.rel_contract_date.setDate(QDate.currentDate())
        rel_form.addRow("تاريخ العقد:", self.rel_contract_date)

        self.rel_notes = QTextEdit()
        self.rel_notes.setMaximumHeight(60)
        rel_form.addRow("ملاحظات:", self.rel_notes)

        form_layout.addWidget(rel_form_group)

        # Evidence section - LINKED to relation (High priority gap fix)
        evidence_group = QGroupBox("الأدلة والوثائق المرتبطة بهذه العلاقة")
        ev_layout = QVBoxLayout(evidence_group)

        self.relation_evidence_list = QListWidget()
        self.relation_evidence_list.setMaximumHeight(120)
        ev_layout.addWidget(self.relation_evidence_list)

        ev_btn_layout = QHBoxLayout()
        add_evidence_btn = QPushButton("📎 إضافة وثيقة")
        add_evidence_btn.clicked.connect(self._add_evidence_to_relation)
        ev_btn_layout.addWidget(add_evidence_btn)

        remove_evidence_btn = QPushButton("🗑️ إزالة")
        remove_evidence_btn.clicked.connect(self._remove_evidence_from_relation)
        ev_btn_layout.addWidget(remove_evidence_btn)

        ev_btn_layout.addStretch()
        ev_layout.addLayout(ev_btn_layout)

        form_layout.addWidget(evidence_group)

        # Save relation button
        save_rel_btn = QPushButton("💾 حفظ العلاقة")
        save_rel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }}
        """)
        save_rel_btn.clicked.connect(self._save_relation)
        form_layout.addWidget(save_rel_btn)

        form_layout.addStretch()
        splitter.addWidget(form_frame)

        splitter.setSizes([350, 450])
        layout.addWidget(splitter)

        return widget

    def _populate_relations_persons(self):
        """Populate the persons combo for relations."""
        self.rel_person_combo.clear()
        for person in self.context.persons:
            full_name = f"{person['first_name']} {person['last_name']}"
            self.rel_person_combo.addItem(full_name, person['person_id'])

    def _add_relation(self):
        """Clear form for new relation."""
        self._editing_relation_index = None
        self._current_relation_evidences = []
        self.relation_evidence_list.clear()
        self.rel_share.setValue(2400)
        self.rel_start_date.setDate(QDate.currentDate())
        self.rel_contract_number.clear()
        self.rel_notes.clear()
        self._populate_relations_persons()

    def _on_relation_selected(self, item):
        """Load relation for editing."""
        rel_id = item.data(Qt.UserRole)
        for i, rel in enumerate(self.context.relations):
            if rel['relation_id'] == rel_id:
                self._editing_relation_index = i
                self._populate_relations_persons()

                # Set person
                idx = self.rel_person_combo.findData(rel['person_id'])
                if idx >= 0:
                    self.rel_person_combo.setCurrentIndex(idx)

                # Set type
                idx = self.rel_type_combo.findData(rel['relation_type'])
                if idx >= 0:
                    self.rel_type_combo.setCurrentIndex(idx)

                self.rel_share.setValue(rel.get('ownership_share', 2400))
                if rel.get('start_date'):
                    self.rel_start_date.setDate(QDate.fromString(rel['start_date'], "yyyy-MM-dd"))
                self.rel_contract_number.setText(rel.get('contract_number', ''))
                if rel.get('contract_date'):
                    self.rel_contract_date.setDate(QDate.fromString(rel['contract_date'], "yyyy-MM-dd"))
                self.rel_notes.setPlainText(rel.get('notes', ''))

                # Load evidences linked to this relation
                self._current_relation_evidences = rel.get('evidences', [])
                self._refresh_relation_evidence_list()
                break

    def _add_evidence_to_relation(self):
        """Add evidence linked to current relation."""
        dialog = AddEvidenceDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            evidence = dialog.get_evidence()
            if not hasattr(self, '_current_relation_evidences'):
                self._current_relation_evidences = []
            self._current_relation_evidences.append(evidence.to_dict())
            self._refresh_relation_evidence_list()
            Toast.show_toast(self, "تم إضافة الوثيقة", Toast.SUCCESS)

    def _remove_evidence_from_relation(self):
        """Remove selected evidence from relation."""
        current = self.relation_evidence_list.currentItem()
        if not current:
            return
        ev_id = current.data(Qt.UserRole)
        self._current_relation_evidences = [e for e in self._current_relation_evidences if e['evidence_id'] != ev_id]
        self._refresh_relation_evidence_list()

    def _refresh_relation_evidence_list(self):
        """Refresh evidence list for current relation."""
        self.relation_evidence_list.clear()
        doc_types = dict(AddEvidenceDialog.DOCUMENT_TYPES)
        for ev in getattr(self, '_current_relation_evidences', []):
            type_ar = doc_types.get(ev['document_type'], ev['document_type'])
            text = f"📄 {type_ar}"
            if ev.get('document_number'):
                text += f" - {ev['document_number']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, ev['evidence_id'])
            self.relation_evidence_list.addItem(item)

    def _save_relation(self):
        """Save person-unit relation with linked evidences."""
        if self.rel_person_combo.count() == 0:
            QMessageBox.warning(self, "خطأ", "لا يوجد أشخاص لتحديد العلاقة")
            return

        relation = {
            "relation_id": str(uuid.uuid4()) if not hasattr(self, '_editing_relation_index') or self._editing_relation_index is None else self.context.relations[self._editing_relation_index]['relation_id'],
            "person_id": self.rel_person_combo.currentData(),
            "person_name": self.rel_person_combo.currentText(),
            "relation_type": self.rel_type_combo.currentData(),
            "ownership_share": self.rel_share.value(),
            "start_date": self.rel_start_date.date().toString("yyyy-MM-dd"),
            "contract_number": self.rel_contract_number.text().strip() or None,
            "contract_date": self.rel_contract_date.date().toString("yyyy-MM-dd"),
            "notes": self.rel_notes.toPlainText().strip(),
            "evidences": getattr(self, '_current_relation_evidences', [])  # Linked evidences
        }

        if hasattr(self, '_editing_relation_index') and self._editing_relation_index is not None:
            self.context.relations[self._editing_relation_index] = relation
            Toast.show_toast(self, "تم تحديث العلاقة", Toast.SUCCESS)
        else:
            self.context.relations.append(relation)
            Toast.show_toast(self, "تم حفظ العلاقة", Toast.SUCCESS)

        self._refresh_relations_list()
        self._add_relation()
        self.next_btn.setEnabled(True)

    def _delete_relation(self):
        """Delete selected relation."""
        current = self.relations_list.currentItem()
        if not current:
            return
        rel_id = current.data(Qt.UserRole)
        self.context.relations = [r for r in self.context.relations if r['relation_id'] != rel_id]
        self._refresh_relations_list()
        self._add_relation()
        Toast.show_toast(self, "تم حذف العلاقة", Toast.INFO)

    def _refresh_relations_list(self):
        """Refresh relations display."""
        self.relations_list.clear()
        rel_type_map = {
            "owner": "مالك", "co_owner": "شريك", "tenant": "مستأجر",
            "occupant": "شاغل", "heir": "وارث", "guardian": "ولي", "other": "أخرى"
        }
        for rel in self.context.relations:
            type_ar = rel_type_map.get(rel['relation_type'], rel['relation_type'])
            ev_count = len(rel.get('evidences', []))
            item = QListWidgetItem(
                f"🔗 {rel['person_name']} - {type_ar}\n"
                f"   الحصة: {rel['ownership_share']}/2400 | الأدلة: {ev_count}"
            )
            item.setData(Qt.UserRole, rel['relation_id'])
            self.relations_list.addItem(item)

    # ==================== Step 6: Claim (S17-S18) ====================

    def _create_claim_step(self) -> QWidget:
        """Create Step 6: Claim Creation (S17-S18)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Auto-evaluation info (S17)
        eval_frame = QFrame()
        eval_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #FEF3C7;
                border: 1px solid #F59E0B;
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        eval_layout = QVBoxLayout(eval_frame)

        eval_title = QLabel("📋 تقييم العلاقات للمطالبة (S17)")
        eval_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        eval_layout.addWidget(eval_title)

        self.claim_eval_label = QLabel("")
        self.claim_eval_label.setWordWrap(True)
        eval_layout.addWidget(self.claim_eval_label)

        layout.addWidget(eval_frame)

        # Claim form (S18)
        claim_group = QGroupBox("بيانات المطالبة")
        claim_form = QFormLayout(claim_group)
        claim_form.setSpacing(12)

        self.claim_type_combo = QComboBox()
        claim_types = [("ownership", "ملكية"), ("occupancy", "إشغال"), ("tenancy", "إيجار")]
        for code, ar in claim_types:
            self.claim_type_combo.addItem(ar, code)
        claim_form.addRow("نوع المطالبة:", self.claim_type_combo)

        self.claim_priority_combo = QComboBox()
        priorities = [("low", "منخفض"), ("normal", "عادي"), ("high", "عالي"), ("urgent", "عاجل")]
        for code, ar in priorities:
            self.claim_priority_combo.addItem(ar, code)
        self.claim_priority_combo.setCurrentIndex(1)
        claim_form.addRow("الأولوية:", self.claim_priority_combo)

        self.claim_notes = QTextEdit()
        self.claim_notes.setMaximumHeight(100)
        claim_form.addRow("ملاحظات:", self.claim_notes)

        layout.addWidget(claim_group)

        # Create claim button
        create_claim_btn = QPushButton("✅ إنشاء المطالبة")
        create_claim_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px 28px;
                font-size: 12pt;
                font-weight: bold;
            }}
        """)
        create_claim_btn.clicked.connect(self._create_claim)
        layout.addWidget(create_claim_btn)

        layout.addStretch()
        return widget

    def _evaluate_for_claim(self):
        """Evaluate relations for claim creation (S17)."""
        owners = [r for r in self.context.relations if r['relation_type'] in ('owner', 'co_owner')]
        tenants = [r for r in self.context.relations if r['relation_type'] == 'tenant']
        occupants = [r for r in self.context.relations if r['relation_type'] == 'occupant']
        heirs = [r for r in self.context.relations if r['relation_type'] == 'heir']

        # Count total evidences
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)

        eval_text = f"📊 تحليل العلاقات المسجلة:\n\n"
        eval_text += f"• {len(owners)} مالك/شريك في الملكية\n"
        eval_text += f"• {len(tenants)} مستأجر\n"
        eval_text += f"• {len(occupants)} شاغل\n"
        eval_text += f"• {len(heirs)} وارث\n"
        eval_text += f"• {total_evidences} وثيقة داعمة\n\n"

        # Calculate total ownership share
        total_share = sum(r.get('ownership_share', 0) for r in owners)

        if owners:
            eval_text += f"✅ يمكن إنشاء مطالبة ملكية (الحصة الإجمالية: {total_share}/2400)"
            self.claim_type_combo.setCurrentIndex(0)
        elif heirs:
            eval_text += "✅ يمكن إنشاء مطالبة ملكية (إرث)"
            self.claim_type_combo.setCurrentIndex(0)
        elif tenants:
            eval_text += "✅ يمكن إنشاء مطالبة إيجار"
            self.claim_type_combo.setCurrentIndex(2)
        elif occupants:
            eval_text += "✅ يمكن إنشاء مطالبة إشغال"
            self.claim_type_combo.setCurrentIndex(1)
        else:
            eval_text += "⚠️ لم يتم تحديد علاقات - يمكن المتابعة يدوياً"

        self.claim_eval_label.setText(eval_text)

    def _create_claim(self):
        """Create the claim (S18)."""
        # Collect all claimant person IDs
        claimant_ids = [r['person_id'] for r in self.context.relations
                        if r['relation_type'] in ('owner', 'co_owner', 'heir')]
        if not claimant_ids:
            claimant_ids = [r['person_id'] for r in self.context.relations]

        # Collect all evidences
        all_evidences = []
        for rel in self.context.relations:
            all_evidences.extend(rel.get('evidences', []))

        self.context.claim_data = {
            "claim_type": self.claim_type_combo.currentData(),
            "priority": self.claim_priority_combo.currentData(),
            "notes": self.claim_notes.toPlainText().strip(),
            "status": "draft",
            "source": "OFFICE_SUBMISSION",
            "claimant_person_ids": claimant_ids,
            "evidence_ids": [e['evidence_id'] for e in all_evidences],
            "unit_id": self.context.unit.unit_id if self.context.unit else None,
            "building_id": self.context.building.building_id if self.context.building else None
        }

        Toast.show_toast(self, "تم إعداد المطالبة - انتقل للمراجعة النهائية", Toast.SUCCESS)
        self.next_btn.setEnabled(True)

    # ==================== Step 7: Review (S19-S21) ====================

    def _create_review_step(self) -> QWidget:
        """Create Step 7: Final Review with full validation (S19-S21)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        header = QHBoxLayout()
        review_title = QLabel("📋 المراجعة النهائية")
        review_title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header.addWidget(review_title)

        header.addStretch()

        # Reference number
        self.review_ref_label = QLabel("")
        self.review_ref_label.setStyleSheet(f"""
            background-color: {Config.SUCCESS_COLOR};
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: bold;
        """)
        header.addWidget(self.review_ref_label)

        layout.addLayout(header)

        # Validation status (S20 - full validation)
        self.validation_frame = QFrame()
        self.validation_frame.setStyleSheet("""
            QFrame { border-radius: 8px; padding: 12px; }
        """)
        val_layout = QVBoxLayout(self.validation_frame)
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        val_layout.addWidget(self.validation_label)
        layout.addWidget(self.validation_frame)

        # Scroll area for review content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        review_content = QWidget()
        review_layout = QVBoxLayout(review_content)
        review_layout.setSpacing(12)

        # Building section
        self.review_building = self._create_review_section("🏢 المبنى", "")
        review_layout.addWidget(self.review_building)

        # Unit section
        self.review_unit = self._create_review_section("🏠 الوحدة العقارية", "")
        review_layout.addWidget(self.review_unit)

        # Household section
        self.review_household = self._create_review_section("👨‍👩‍👧‍👦 الأسر", "")
        review_layout.addWidget(self.review_household)

        # Persons section
        self.review_persons = self._create_review_section("👤 الأشخاص", "")
        review_layout.addWidget(self.review_persons)

        # Relations section
        self.review_relations = self._create_review_section("🔗 العلاقات والأدلة", "")
        review_layout.addWidget(self.review_relations)

        # Claim section
        self.review_claim = self._create_review_section("📄 المطالبة", "")
        review_layout.addWidget(self.review_claim)

        review_layout.addStretch()
        scroll.setWidget(review_content)
        layout.addWidget(scroll)

        # Final submit button
        submit_btn = QPushButton("✅ تأكيد وإنهاء المسح")
        submit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.SUCCESS_COLOR};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 16px 32px;
                font-size: 14pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #059669;
            }}
        """)
        submit_btn.clicked.connect(self._finalize_survey)
        layout.addWidget(submit_btn)

        return widget

    def _create_review_section(self, title: str, content: str) -> QFrame:
        """Create a review section frame."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(frame)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: #374151; font-size: 11pt;")
        layout.addWidget(title_label)

        content_label = QLabel(content)
        content_label.setObjectName("content")
        content_label.setStyleSheet("color: #6B7280;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        return frame

    def _run_final_validation(self) -> tuple:
        """Run comprehensive final validation (S20)."""
        errors = []
        warnings = []

        # Required checks
        if not self.context.building:
            errors.append("لم يتم اختيار مبنى")

        if not self.context.unit and not self.context.is_new_unit:
            errors.append("لم يتم اختيار أو إنشاء وحدة عقارية")

        if len(self.context.households) == 0:
            warnings.append("لم يتم تسجيل أي أسرة")

        if len(self.context.persons) == 0:
            errors.append("لم يتم تسجيل أي شخص")

        if len(self.context.relations) == 0:
            warnings.append("لم يتم تحديد أي علاقات")

        # Check for contact person
        has_contact = any(p.get('is_contact_person') for p in self.context.persons)
        if not has_contact and len(self.context.persons) > 0:
            warnings.append("لم يتم تحديد شخص تواصل رئيسي")

        # Check evidences
        total_evidences = sum(len(r.get('evidences', [])) for r in self.context.relations)
        if total_evidences == 0:
            warnings.append("لم يتم إرفاق أي وثائق داعمة")

        # Check claim
        if not self.context.claim_data:
            warnings.append("لم يتم إنشاء المطالبة")

        return errors, warnings

    def _populate_review(self):
        """Populate the review step with all collected data (S19)."""
        # Reference number
        self.review_ref_label.setText(f"الرقم المرجعي: {self.context.reference_number}")

        # Run validation
        errors, warnings = self._run_final_validation()

        if errors:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FEE2E2;
                    border: 1px solid {Config.ERROR_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            val_text = "❌ أخطاء يجب تصحيحها:\n" + "\n".join(f"• {e}" for e in errors)
            if warnings:
                val_text += "\n\n⚠️ تحذيرات:\n" + "\n".join(f"• {w}" for w in warnings)
            self.validation_label.setText(val_text)
        elif warnings:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #FEF3C7;
                    border: 1px solid {Config.WARNING_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            self.validation_label.setText("⚠️ تحذيرات:\n" + "\n".join(f"• {w}" for w in warnings))
        else:
            self.validation_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #D1FAE5;
                    border: 1px solid {Config.SUCCESS_COLOR};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            self.validation_label.setText("✅ جميع البيانات مكتملة وجاهزة للحفظ")

        # Building
        if self.context.building:
            self.review_building.findChild(QLabel, "content").setText(
                f"رقم المبنى: {self.context.building.building_id}\n"
                f"النوع: {self.context.building.building_type_display}"
            )

        # Unit
        if self.context.unit:
            self.review_unit.findChild(QLabel, "content").setText(
                f"رقم الوحدة: {self.context.unit.unit_id}\n"
                f"النوع: {self.context.unit.unit_type_display}"
            )
        elif self.context.is_new_unit and self.context.new_unit_data:
            self.review_unit.findChild(QLabel, "content").setText(
                f"وحدة جديدة\n"
                f"النوع: {self.context.new_unit_data.get('unit_type', '-')}\n"
                f"الطابق: {self.context.new_unit_data.get('floor_number', '-')}\n"
                f"رقم الشقة: {self.context.new_unit_data.get('apartment_number', '-')}"
            )

        # Households
        hh_text = f"عدد الأسر: {len(self.context.households)}\n"
        total_persons_in_hh = sum(h.get('size', 0) for h in self.context.households)
        hh_text += f"إجمالي الأفراد: {total_persons_in_hh}\n"
        for hh in self.context.households:
            hh_text += f"• {hh['head_name']} ({hh['size']} فرد)\n"
        self.review_household.findChild(QLabel, "content").setText(hh_text)

        # Persons
        persons_text = f"عدد الأشخاص المسجلين: {len(self.context.persons)}\n"
        for p in self.context.persons:
            contact = "📞 " if p.get('is_contact_person') else ""
            persons_text += f"• {contact}{p['first_name']} {p['last_name']}\n"
        self.review_persons.findChild(QLabel, "content").setText(persons_text)

        # Relations
        rel_text = f"عدد العلاقات: {len(self.context.relations)}\n"
        total_ev = sum(len(r.get('evidences', [])) for r in self.context.relations)
        rel_text += f"إجمالي الوثائق: {total_ev}\n"
        rel_type_map = {"owner": "مالك", "co_owner": "شريك", "tenant": "مستأجر", "occupant": "شاغل", "heir": "وارث"}
        for r in self.context.relations:
            type_ar = rel_type_map.get(r['relation_type'], r['relation_type'])
            ev_count = len(r.get('evidences', []))
            rel_text += f"• {r['person_name']} - {type_ar} ({ev_count} وثائق)\n"
        self.review_relations.findChild(QLabel, "content").setText(rel_text)

        # Claim
        if self.context.claim_data:
            claim_types = {"ownership": "ملكية", "occupancy": "إشغال", "tenancy": "إيجار"}
            priorities = {"low": "منخفض", "normal": "عادي", "high": "عالي", "urgent": "عاجل"}
            self.review_claim.findChild(QLabel, "content").setText(
                f"نوع المطالبة: {claim_types.get(self.context.claim_data['claim_type'], '-')}\n"
                f"الأولوية: {priorities.get(self.context.claim_data['priority'], '-')}\n"
                f"الحالة: مسودة\n"
                f"عدد المطالبين: {len(self.context.claim_data.get('claimant_person_ids', []))}"
            )
        else:
            self.review_claim.findChild(QLabel, "content").setText("لم يتم إنشاء المطالبة بعد")

    def _finalize_survey(self):
        """Finalize and save the survey (S20-S21)."""
        errors, warnings = self._run_final_validation()

        if errors:
            QMessageBox.critical(
                self, "خطأ",
                "لا يمكن إنهاء المسح بسبب الأخطاء التالية:\n\n" +
                "\n".join(f"• {e}" for e in errors)
            )
            return

        if warnings:
            reply = QMessageBox.question(
                self, "تحذير",
                "هناك تحذيرات:\n" + "\n".join(f"• {w}" for w in warnings) +
                "\n\nهل تريد المتابعة على أي حال؟",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Commit to database (S21)
        try:
            self._commit_survey()
            self.context.status = "finalized"
            self.context.updated_at = datetime.now()

            QMessageBox.information(
                self, "نجاح",
                f"تم إنهاء المسح بنجاح!\n\n"
                f"الرقم المرجعي: {self.context.reference_number}\n"
                f"رقم المسح: {self.context.survey_id[:8]}"
            )

            self.survey_completed.emit(self.context.survey_id)

        except Exception as e:
            logger.error(f"Failed to finalize survey: {e}")
            QMessageBox.critical(self, "خطأ", f"فشل في حفظ المسح: {str(e)}")

    def _commit_survey(self):
        """
        Commit all survey data to database (S21 - Transactional save).
        Implements UC-005: Saves finalized survey to database.
        """
        logger.info(f"Committing survey {self.context.survey_id}")

        try:
            # 1. Create unit if new
            if self.context.is_new_unit and self.context.new_unit_data:
                unit_data = self.context.new_unit_data
                new_unit = Unit(
                    unit_type=unit_data.get('unit_type'),
                    floor_number=unit_data.get('floor_number'),
                    apartment_number=unit_data.get('apartment_number'),
                    area_sqm=unit_data.get('area'),
                    building_id=unit_data.get('building_id')
                )
                self.unit_repo.create(new_unit)
                self.context.unit = new_unit
                logger.info(f"  Created unit: {new_unit.unit_id}")

            # 2. Create/update persons
            for p_data in self.context.persons:
                person = Person(
                    first_name_ar=p_data['first_name'],
                    father_name_ar=p_data.get('father_name'),
                    last_name_ar=p_data['last_name'],
                    national_id=p_data.get('national_id'),
                    gender=p_data.get('gender'),
                    year_of_birth=p_data.get('year_of_birth'),
                    phone_primary=p_data.get('phone')
                )
                self.person_repo.create(person)
                p_data['db_person_id'] = person.person_id
                logger.info(f"  Created person: {person.person_id}")

            # 3. Create claim
            if self.context.claim_data:
                claim = Claim(
                    claim_type=self.context.claim_data['claim_type'],
                    priority=self.context.claim_data['priority'],
                    source=self.context.claim_data['source'],
                    unit_id=self.context.unit.unit_id if self.context.unit else None,
                    case_status='draft',
                    notes=self.context.claim_data.get('notes')
                )
                self.claim_repo.create(claim)
                logger.info(f"  Created claim: {claim.claim_id}")

            # 4. Save/update survey metadata to surveys table
            survey_data = self.context.to_dict()
            survey_data['status'] = 'finalized'  # Mark as finalized

            # Check if survey exists
            existing_survey = self.survey_repo.get_by_id(self.context.survey_id)

            if existing_survey:
                # Update existing survey (was draft, now finalized)
                self.survey_repo.update(self.context.survey_id, survey_data)
                logger.info(f"  Updated survey status to finalized: {self.context.survey_id}")
            else:
                # Create new survey record
                self.survey_repo.create(survey_data)
                logger.info(f"  Created finalized survey: {self.context.survey_id}")

            logger.info(f"Survey {self.context.survey_id} committed successfully")

        except Exception as e:
            logger.error(f"Transaction failed: {e}", exc_info=True)
            raise

    # ==================== Navigation ====================

    def _update_step_display(self):
        """Update step indicators."""
        # 1) Update step tab styles
        for i, label in enumerate(self.step_labels):
            if i < self.current_step:
                # Completed (مكتملة): شفاف + بوردر أزرق + نص أزرق
                label.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        border: 1px solid #3890DF;
                        border-radius: 17px;
                        padding: 7px 12px;
                        color: #3890DF;
                        font-weight: 600;
                        font-size: 9pt;
                        line-height: 18px;

                    }
                """)
            elif i == self.current_step:
                # Active (الحالية): أبيض + نص أزرق
                label.setStyleSheet("""
                    QLabel {
                        background-color: #FFFFFF;
                        border: 2px solid #3890DF;
                        border-radius: 17px;
                        padding: 7px 12px;
                        color: #3890DF;
                        font-weight: 600;
                        font-size: 8pt;
                        font-family: 'Noto Kufi Arabic';
                        line-height: 20px;

                    }
                """)
            else:
                # Inactive (غير نشطة): شفاف + بوردر أبيض + نص غامق
                label.setStyleSheet("""
                    QLabel {
                        background-color: #FFFFFF;
                        border: 1px solid #F0F7FF;
                        border-radius: 17px;
                        padding: 7px 12px;
                        color: #2C3E50;
                        font-weight: 600;
                        font-size: 8pt;
                        font-family: 'Noto Kufi Arabic';
                        line-height: 18px;

                    }
                """)

        # 2) Switch stacked content page (safe guard to avoid crashes during init)
        if hasattr(self, "content_stack") and self.content_stack is not None:
            try:
                self.content_stack.setCurrentIndex(self.current_step)
                # السابق يظهر فقط بعد أول خطوة (بعد تسجيل البناء)
                show_prev = self.current_step > self.STEP_BUILDING
                self.prev_btn.setVisible(show_prev)
                self.prev_btn.setEnabled(show_prev)

            except Exception:
                pass

        # 3) Prev button enable/disable (safe guard)
        if hasattr(self, "prev_btn") and self.prev_btn is not None:
            self.prev_btn.setEnabled(self.current_step > 0)

        # 4) Next button hide on final step (safe guard)
        if hasattr(self, "next_btn") and self.next_btn is not None:
            if self.current_step == self.STEP_REVIEW:
                self.next_btn.hide()
            else:
                self.next_btn.show()


    def _on_previous(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_display()
            self.next_btn.setEnabled(True)

    def _on_next(self):
        """Go to next step with validation."""
        if not self._validate_current_step():
            return

        if self.current_step < self.STEP_REVIEW:
            self.current_step += 1
            self._prepare_step(self.current_step)
            self._update_step_display()

    def _validate_current_step(self) -> bool:
        """Validate current step before proceeding."""
        if self.current_step == self.STEP_BUILDING:
            if not self.context.building:
                QMessageBox.warning(self, "خطأ", "يجب اختيار مبنى للمتابعة")
                return False

        elif self.current_step == self.STEP_UNIT:
            if not self.context.unit and not self.context.is_new_unit:
                QMessageBox.warning(self, "خطأ", "يجب اختيار أو إنشاء وحدة عقارية")
                return False
            if self.context.is_new_unit:
                self._save_new_unit_data()

        return True

    def _prepare_step(self, step: int):
        """Prepare data for a step."""
        if step == self.STEP_UNIT:
            self._load_units_for_building()

        elif step == self.STEP_HOUSEHOLD:
            unit_text = ""
            if self.context.unit:
                unit_text = f"🏠 الوحدة: {self.context.unit.unit_id}"
            elif self.context.is_new_unit:
                unit_text = "🏠 وحدة جديدة"
            self.household_unit_label.setText(unit_text)
            self._refresh_households_list()
            self.next_btn.setEnabled(len(self.context.households) > 0)

        elif step == self.STEP_PERSONS:
            self._populate_household_combo()
            self._refresh_persons_list()
            self._add_person()
            self.next_btn.setEnabled(len(self.context.persons) > 0)

        elif step == self.STEP_RELATIONS:
            self._populate_relations_persons()
            self._refresh_relations_list()
            self._add_relation()
            self.next_btn.setEnabled(len(self.context.relations) > 0)

        elif step == self.STEP_CLAIM:
            self._evaluate_for_claim()
            self.next_btn.setEnabled(False)

        elif step == self.STEP_REVIEW:
            self._populate_review()

    def _save_as_draft(self):
        """
        Save current survey as draft with persistence (S22).
        Implements UC-005: Saves draft to database for later resumption.
        """
        self.context.status = "draft"
        self.context.updated_at = datetime.now()

        try:
            # Save draft to database
            draft_data = self.context.to_dict()

            # Check if survey already exists
            existing_survey = self.survey_repo.get_by_id(self.context.survey_id)

            if existing_survey:
                # Update existing draft
                success = self.survey_repo.update(self.context.survey_id, draft_data)
                logger.info(f"Updated draft survey: {self.context.survey_id}")
            else:
                # Create new draft
                survey_id = self.survey_repo.create(draft_data)
                logger.info(f"Created new draft survey: {survey_id}")

            Toast.show_toast(
                self,
                f"✅ تم حفظ المسودة بنجاح\nالرقم المرجعي: {self.context.reference_number}",
                Toast.SUCCESS
            )
            self.survey_saved_draft.emit(self.context.survey_id)

        except Exception as e:
            logger.error(f"Failed to save draft: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "خطأ في الحفظ",
                f"فشل في حفظ المسودة:\n{str(e)}"
            )

    def _on_cancel(self):
        """Cancel the survey (S22)."""
        reply = QMessageBox.question(
            self, "تأكيد الإلغاء",
            "هل تريد إلغاء المسح؟\n\n"
            "يمكنك حفظه كمسودة للعودة إليه لاحقاً.",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )

        if reply == QMessageBox.Save:
            self._save_as_draft()
        elif reply == QMessageBox.Discard:
            self.survey_cancelled.emit()
        # Cancel = do nothing

    def refresh(self, data=None):
        """Reset the wizard for a new survey."""
        self.context = SurveyContext()
        self.current_step = 0
        self._editing_person_index = None

        # Clear all forms
        self.building_search.clear()
        self.buildings_list.clear()
        self.selected_building_frame.hide()

        # Reset button state
        self.next_btn.setEnabled(False)

        # Update display
        self.ref_badge.setText(f"الرقم المرجعي: {self.context.reference_number}")
        self.survey_badge.setText(f"#{self.context.survey_id[:8]}")
        self._update_step_display()
        self._load_buildings()

    def load_draft(self, draft_data: Dict):
        """Load a saved draft survey."""
        self.context = SurveyContext.from_dict(draft_data)
        self.current_step = 0

        # Update UI
        self.ref_badge.setText(f"الرقم المرجعي: {self.context.reference_number}")
        self.survey_badge.setText(f"#{self.context.survey_id[:8]}")
        self._update_step_display()

        Toast.show_toast(self, "تم تحميل المسودة", Toast.INFO)
