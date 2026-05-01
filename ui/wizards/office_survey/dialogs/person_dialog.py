# -*- coding: utf-8 -*-
"""
Person Dialog - Dialog for creating/editing persons.

3-Tab structure:
- Tab 1: Personal information (names, birth place, birth date, gender, nationality, national ID, ID photos)
- Tab 2: Contact information (person role, email, mobile, landline)
- Tab 3: Relation & Evidence (occupancy nature, claim type, dates, ownership, documents)
"""

from typing import Dict, Any, Optional, List
import uuid

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QComboBox,
    QGridLayout, QTextEdit, QTabWidget,
    QRadioButton, QButtonGroup, QSizePolicy
)
from PyQt5.QtCore import Qt, QUrl, QTimer, QLocale, QDate
from PyQt5.QtGui import QColor, QPixmap, QRegExpValidator, QDoubleValidator, QIntValidator
from PyQt5.QtCore import QRegExp as QtRegExp

from app.config import Config
from services.validation_service import ValidationService
from services.api_client import get_api_client
from services.translation_manager import tr, get_layout_direction, get_language
from services.error_mapper import map_exception
from services.display_mappings import (
    get_relation_type_options, get_relationship_to_head_options,
    get_evidence_type_options,
    get_gender_options, get_nationality_options
)
from ui.components.rtl_combo import RtlCombo
from ui.components.centered_text_edit import CenteredTextEdit
from ui.components.toast import Toast
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.wizards.office_survey.wizard_styles import (
    FORM_FIELD_STYLE, make_editable_date_combo, read_int_from_combo,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonDialog(QDialog):
    """Dialog for creating or editing a person - 3 tabs."""

    def __init__(self, person_data: Optional[Dict] = None, existing_persons: List[Dict] = None, parent=None,
                 auth_token: Optional[str] = None, survey_id: Optional[str] = None,
                 household_id: Optional[str] = None, unit_id: Optional[str] = None,
                 read_only: bool = False, existing_person_mode: bool = False,
                 initial_tab: int = 0):
        super().__init__(parent)
        self._existing_person_mode = existing_person_mode
        self._initial_tab = initial_tab
        self.person_data = person_data
        self.existing_persons = existing_persons or []
        self.editing_mode = person_data is not None and not existing_person_mode
        self.read_only = read_only
        self.validation_service = ValidationService()
        self.uploaded_files = []
        self.relation_uploaded_files = []  # List[Dict]: {path, issue_date, hash}

        # API integration
        self._survey_id = survey_id
        self._household_id = household_id
        self._unit_id = unit_id
        self._api_service = get_api_client()
        if self._api_service and auth_token:
            self._api_service.set_access_token(auth_token)
        self._api_person_id = None
        self._api_relation_id = None
        self._evidence_ids = {}       # {normalized_path: evidence_id} for ID files
        self._server_evidences = []   # List[EvidenceDto] from server on edit
        self._pending_id_replacements = []    # deferred evidence_ids for ID file replacement
        self._pending_rel_replacements = []   # deferred evidence_ids for tenure file replacement
        self._field_styles = {}  # {widget: original_stylesheet} for error state restore

        self._overlay = None
        self._slide_anim = None
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        # Dynamic sizing: bottom-sheet style (centered, from bottom)
        # Use rect() (client area) not geometry() (includes window frame)
        parent_win = parent.window() if parent else None
        if parent_win:
            client_rect = parent_win.rect()
            panel_w = min(700, client_rect.width() - 40)
            panel_h = min(680, client_rect.height() - 30)
        else:
            panel_w = 700
            panel_h = 680
        self.setFixedSize(panel_w, panel_h)

        self._setup_ui()

        if (self.editing_mode or self._existing_person_mode) and person_data:
            self._load_person_data(person_data)

        if self.read_only:
            self._apply_read_only_mode()

        if self._existing_person_mode:
            self._apply_existing_person_mode()

        if self._initial_tab > 0:
            self.tab_widget.setCurrentIndex(self._initial_tab)

    def _refresh_token(self):
        """Refresh auth token from parent wizard window before API calls."""
        parent = self.parent()
        if parent:
            main_window = parent.window()
            if main_window and hasattr(main_window, '_api_token') and main_window._api_token:
                self._api_service.set_access_token(main_window._api_token)

    def showEvent(self, event):
        """Position as bottom sheet and animate slide-up."""
        super().showEvent(event)
        parent = self.parent()
        if not parent:
            return
        try:
            parent_win = parent.window()
            client_rect = parent_win.rect()
            panel_w = self.width()
            panel_h = self.height()

            # Position at bottom center using client area
            parent_global = parent_win.mapToGlobal(client_rect.topLeft())
            target_x = parent_global.x() + (client_rect.width() - panel_w) // 2
            target_y = parent_global.y() + client_rect.height() - panel_h - 10

            # Slide-up animation from bottom
            from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint
            start_y = parent_global.y() + client_rect.height()
            self.move(target_x, start_y)

            self._slide_anim = QPropertyAnimation(self, b"pos", self)
            self._slide_anim.setDuration(300)
            self._slide_anim.setStartValue(QPoint(target_x, start_y))
            self._slide_anim.setEndValue(QPoint(target_x, target_y))
            self._slide_anim.setEasingCurve(QEasingCurve.OutQuart)
            self._slide_anim.start()
        except Exception:
            pass

    # UI Setup

    def _setup_ui(self):
        """Setup dialog UI with 3 tabs."""
        self.setLayoutDirection(get_layout_direction())

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        # Side panel content frame
        content_frame = QFrame()
        content_frame.setObjectName("ContentFrame")
        content_frame.setStyleSheet("""
            QFrame#ContentFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F0F5FB, stop:1 #E8EFF8);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border-top: 1px solid rgba(56, 144, 223, 0.15);
            }
            QFrame#ContentFrame QLabel,
            QFrame#ContentFrame QRadioButton {
                background-color: transparent;
            }
        """)

        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(content_frame)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, -6)
        shadow.setColor(QColor(0, 0, 0, 100))
        content_frame.setGraphicsEffect(shadow)

        outer_layout.addWidget(content_frame)

        frame_layout = QVBoxLayout(content_frame)
        frame_layout.setSpacing(0)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        # Dark header bar
        header_bar = QFrame()
        header_bar.setFixedHeight(ScreenScale.h(50))
        header_bar.setObjectName("PanelHeader")
        header_bar.setStyleSheet("""
            QFrame#PanelHeader {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #EBF5FF, stop:0.5 #E0EEFB, stop:1 #D6E8F7);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(10)

        # Close button in header
        close_btn = QPushButton("\u2715")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(ScreenScale.w(30), ScreenScale.h(30))
        close_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 64, 100, 0.08);
                color: #3B82F6;
                border: 1px solid rgba(56, 144, 223, 0.15);
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(30, 64, 100, 0.15);
                color: #1E40AF;
            }
        """)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)

        # Title in dark header
        if self.read_only:
            title_text = tr("wizard.person_dialog.title_view")
        elif getattr(self, '_existing_person_mode', False):
            title_text = tr("wizard.person_dialog.title_link_existing")
        elif self.editing_mode:
            title_text = tr("wizard.person_dialog.title_edit")
        else:
            title_text = tr("wizard.person_dialog.title_add")
        self._dialog_title = QLabel(title_text)
        self._dialog_title.setFont(create_font(size=13, weight=FontManager.WEIGHT_SEMIBOLD))
        self._dialog_title.setStyleSheet("color: #1A365D; background: transparent; border: none;")
        header_layout.addWidget(self._dialog_title, 1)

        frame_layout.addWidget(header_bar)

        # Accent line
        accent_line = QFrame()
        accent_line.setFixedHeight(2)
        accent_line.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(56, 144, 223, 0),
                    stop:0.2 rgba(56, 144, 223, 120),
                    stop:0.5 rgba(91, 168, 240, 180),
                    stop:0.8 rgba(56, 144, 223, 120),
                    stop:1 rgba(56, 144, 223, 0));
            }
        """)
        frame_layout.addWidget(accent_line)

        # Content area with scroll
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(56, 144, 223, 0.30);
                border-radius: 3px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(56, 144, 223, 0.50);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content_inner = QWidget()
        content_inner.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(content_inner)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(20, 12, 20, 14)

        scroll.setWidget(content_inner)
        frame_layout.addWidget(scroll, 1)

        # Progress indicator (3 bars)
        self._setup_progress_indicator(main_layout)

        # Tab widget with hidden tab bar
        self.tab_widget = QTabWidget()
        self.tab_widget.tabBar().setVisible(False)
        self.tab_widget.setAutoFillBackground(False)
        self.tab_widget.setStyleSheet("""
            QTabWidget {
                background-color: transparent;
                border: none;
            }
            QTabWidget::pane {
                border: none;
                background-color: transparent;
                padding: 0px;
            }
            QTabWidget > QWidget {
                background-color: transparent;
            }
        """)

        self._setup_tab1_personal()
        self._setup_tab2_contact()
        self._setup_tab3_relation()

        # Ensure all tab pages and internal stacked widget are transparent
        from PyQt5.QtWidgets import QStackedWidget
        stacked = self.tab_widget.findChild(QStackedWidget)
        if stacked:
            stacked.setAutoFillBackground(False)
            stacked.setStyleSheet("background-color: transparent;")
        for i in range(self.tab_widget.count()):
            page = self.tab_widget.widget(i)
            page.setAutoFillBackground(False)

        # Connect field signals for live progress tracking
        self._connect_progress_signals()

        self.tab_widget.currentChanged.connect(self._update_progress)
        main_layout.addWidget(self.tab_widget)

        # Fixed bottom button bar (outside scroll area, always visible)
        self._btn_stack = QStackedWidget()
        self._btn_stack.setStyleSheet("background: transparent;")

        # Tab 1 buttons: Cancel | Next
        bar1 = QWidget()
        bar1.setStyleSheet("background: transparent;")
        bar1_layout = QHBoxLayout(bar1)
        bar1_layout.setContentsMargins(24, 10, 24, 14)
        bar1_layout.setSpacing(8)
        bar1_layout.addWidget(self._create_btn(tr("common.cancel"), primary=False, callback=self.reject))
        bar1_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab2))
        self._btn_stack.addWidget(bar1)

        # Tab 2 buttons: Previous | Next
        bar2 = QWidget()
        bar2.setStyleSheet("background: transparent;")
        bar2_layout = QHBoxLayout(bar2)
        bar2_layout.setContentsMargins(24, 10, 24, 14)
        bar2_layout.setSpacing(8)
        bar2_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab1))
        bar2_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab3))
        self._btn_stack.addWidget(bar2)

        # Tab 3 buttons: Previous | Save
        bar3 = QWidget()
        bar3.setStyleSheet("background: transparent;")
        bar3_layout = QHBoxLayout(bar3)
        bar3_layout.setContentsMargins(24, 10, 24, 14)
        bar3_layout.setSpacing(8)
        bar3_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab2_back))
        bar3_layout.addWidget(self._create_btn(tr("common.save"), primary=True, callback=self._on_final_save))
        self._btn_stack.addWidget(bar3)

        self.tab_widget.currentChanged.connect(self._btn_stack.setCurrentIndex)
        frame_layout.addWidget(self._btn_stack)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _apply_read_only_mode(self):
        """Disable all input fields and change buttons for read-only viewing."""
        from PyQt5.QtWidgets import QLineEdit, QComboBox, QTextEdit, QDoubleSpinBox, QRadioButton

        # Disable all input widgets
        for widget in self.findChildren(QLineEdit):
            widget.setReadOnly(True)
        for widget in self.findChildren(QComboBox):
            widget.setEnabled(False)
        for widget in self.findChildren(QTextEdit):
            widget.setReadOnly(True)
        for widget in self.findChildren(QDoubleSpinBox):
            widget.setReadOnly(True)
        for widget in self.findChildren(QRadioButton):
            widget.setEnabled(False)

        # Replace bottom bar buttons with navigation-only (no save)
        for i in range(self._btn_stack.count()):
            bar = self._btn_stack.widget(i)
            bar_layout = bar.layout()
            if not bar_layout:
                continue
            widgets_to_remove = []
            for j in range(bar_layout.count()):
                item = bar_layout.itemAt(j)
                if item and item.widget():
                    widgets_to_remove.append(item.widget())
            for w in widgets_to_remove:
                w.hide()
                bar_layout.removeWidget(w)
                w.setParent(None)
            if i == 0:
                bar_layout.addWidget(self._create_btn(tr("common.cancel"), primary=False, callback=self.reject))
                bar_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab2))
            elif i == 1:
                bar_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab1))
                bar_layout.addWidget(self._create_btn(tr("wizard.person_dialog.next"), primary=True, callback=self._go_to_tab3))
            else:
                bar_layout.addWidget(self._create_btn(tr("wizard.person_dialog.previous"), primary=False, callback=self._go_to_tab2_back))
                bar_layout.addWidget(self._create_btn(tr("common.cancel"), primary=True, callback=self.reject))

    def _apply_existing_person_mode(self):
        """Make Tab1 and Tab2 fields read-only when linking an existing person to a unit."""
        from PyQt5.QtWidgets import QComboBox
        read_only_style = " background-color: #F3F4F6;"
        for tab_idx in [0, 1]:
            tab = self.tab_widget.widget(tab_idx)
            for w in tab.findChildren(QLineEdit):
                w.setReadOnly(True)
                w.setStyleSheet(w.styleSheet() + read_only_style)
            for w in tab.findChildren(QComboBox):
                w.setEnabled(False)

    def _setup_progress_indicator(self, layout):
        """Create 3-bar progress indicator with gradient fill."""
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(6)
        self._progress_bars = []
        for _ in range(3):
            bar = QFrame()
            bar.setFixedHeight(ScreenScale.h(5))
            bar.setLayoutDirection(Qt.LeftToRight)  # Prevent RTL from flipping gradient
            bar.setStyleSheet("QFrame { background-color: rgba(56, 144, 223, 0.12); border-radius: 2px; }")
            self._progress_bars.append(bar)
            progress_layout.addWidget(bar)
        layout.addLayout(progress_layout)

    def _connect_progress_signals(self):
        """Connect all form field signals to update progress bars live."""
        # Tab 1 fields
        self.first_name.textChanged.connect(self._update_all_progress)
        self.last_name.textChanged.connect(self._update_all_progress)
        self.father_name.textChanged.connect(self._update_all_progress)
        self.mother_name.textChanged.connect(self._update_all_progress)
        self._gender_group.buttonClicked.connect(self._update_all_progress)
        self.nationality.currentIndexChanged.connect(self._update_all_progress)
        self.national_id.textChanged.connect(self._update_all_progress)

        # Tab 2 fields
        self.person_role.currentIndexChanged.connect(self._update_all_progress)
        self.email.textChanged.connect(self._update_all_progress)
        self.phone.textChanged.connect(self._update_all_progress)
        self.landline_digits.textChanged.connect(self._update_all_progress)

        # Tab 3 fields
        self.rel_type_combo.currentIndexChanged.connect(self._update_all_progress)
        self.rel_type_combo.currentIndexChanged.connect(self._on_claim_type_changed)
        self.ownership_share.textChanged.connect(self._update_all_progress)
        self.evidence_type.currentIndexChanged.connect(self._update_all_progress)
        self.evidence_desc.textChanged.connect(self._update_all_progress)
        self.notes.textChanged.connect(self._update_all_progress)

        # Clear inline errors when user starts typing
        self.first_name.textChanged.connect(lambda: self._clear_field_error(self.first_name, self._first_name_error))
        self.last_name.textChanged.connect(lambda: self._clear_field_error(self.last_name, self._last_name_error))
        self.father_name.textChanged.connect(lambda: self._clear_field_error(self.father_name, self._father_name_error))
        self.national_id.textChanged.connect(lambda: self._clear_field_error(self.national_id, self._nid_error))
        self.phone.textChanged.connect(lambda: self._clear_field_error(self.phone, self._mobile_error))
        self.landline_digits.textChanged.connect(lambda: self._clear_field_error(self.landline_digits, self._landline_error))
        self.email.textChanged.connect(lambda: self._clear_field_error(self.email, self._email_error))
        self.ownership_share.textChanged.connect(lambda: self._clear_field_error(self.ownership_share, self._ownership_error))

    def _calculate_tab_fill(self, tab_index: int) -> float:
        """Calculate fill percentage (0.0 to 1.0) for a given tab."""
        if tab_index == 0:
            fields = [
                bool(self.first_name.text().strip()),
                bool(self.last_name.text().strip()),
                bool(self.father_name.text().strip()),
                bool(self.mother_name.text().strip()),
                self._get_gender() is not None,
                self.nationality.currentIndex() > 0,
                bool(self.national_id.text().strip()),
            ]
        elif tab_index == 1:
            fields = [
                self.person_role.currentIndex() > 0,
                bool(self.email.text().strip()),
                bool(self.phone.text().strip()),
                bool(self.landline_digits.text().strip()),
            ]
        else:
            fields = [
                self.rel_type_combo.currentIndex() > 0,
                bool(self.ownership_share.text().strip()),
                self.evidence_type.currentIndex() > 0,
                bool(self.evidence_desc.text().strip()),
                bool(self.notes.toPlainText().strip()),
            ]
        filled = sum(fields)
        return filled / len(fields) if fields else 0.0

    def _update_bar_style(self, bar: QFrame, fill_pct: float):
        """Update a single progress bar with gradient fill."""
        if fill_pct <= 0:
            bar.setStyleSheet("QFrame { background-color: rgba(56, 144, 223, 0.12); border-radius: 2px; }")
        elif fill_pct >= 1.0:
            bar.setStyleSheet("QFrame { background-color: #3890DF; border-radius: 2px; }")
        else:
            # Gradient: blue up to fill_pct, then gray
            stop = round(fill_pct, 3)
            stop2 = round(fill_pct + 0.001, 3)
            bar.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:1, y1:0, x2:0, y2:0,
                        stop:0 #3890DF, stop:{stop} #3890DF,
                        stop:{stop2} rgba(255,255,255,0.1), stop:1 rgba(255,255,255,0.1));
                    border-radius: 2px;
                }}
            """)

    def _update_all_progress(self, *args):
        """Update all 3 progress bars based on field completion."""
        for i, bar in enumerate(self._progress_bars):
            pct = self._calculate_tab_fill(i)
            self._update_bar_style(bar, pct)

    def _update_progress(self, current_tab: int):
        """Update progress when tab changes (also recalc fill)."""
        self._update_all_progress()

    # Tab 1: Personal Information

    def _setup_tab1_personal(self):
        """Tab 1: Names, birth place, birth date, gender, nationality, national ID, ID photos."""
        tab = QWidget()
        tab.setLayoutDirection(get_layout_direction())
        tab.setStyleSheet("background-color: transparent;")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(6)

        label_style = "color: #1E293B; font-weight: 700; font-size: 11pt; background: transparent;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0

        # Row: First Name | Last Name
        grid.addWidget(self._label(tr("wizard.person_dialog.first_name"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.last_name"), label_style), row, 1)
        row += 1
        
        _name_validator = QRegExpValidator(QtRegExp("[\u0600-\u06FFa-zA-Z\\s.\\-']+"))

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText(tr("wizard.person_dialog.first_name_placeholder"))
        self.first_name.setValidator(_name_validator)
        self.first_name.setStyleSheet(self._input_style())
        self._first_name_error = QLabel("")
        self._first_name_error.setStyleSheet(self._error_label_style())
        self._first_name_error.setVisible(False)
        fn_container = QVBoxLayout()
        fn_container.setSpacing(2)
        fn_container.setContentsMargins(0, 0, 0, 0)
        fn_container.addWidget(self.first_name)
        fn_container.addWidget(self._first_name_error)
        grid.addLayout(fn_container, row, 0)

        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText(tr("wizard.person_dialog.last_name_placeholder"))
        self.last_name.setValidator(_name_validator)
        self.last_name.setStyleSheet(self._input_style())
        self._last_name_error = QLabel("")
        self._last_name_error.setStyleSheet(self._error_label_style())
        self._last_name_error.setVisible(False)
        ln_container = QVBoxLayout()
        ln_container.setSpacing(2)
        ln_container.setContentsMargins(0, 0, 0, 0)
        ln_container.addWidget(self.last_name)
        ln_container.addWidget(self._last_name_error)
        grid.addLayout(ln_container, row, 1)
        row += 1

        # Row: Father Name | Mother Name
        grid.addWidget(self._label(tr("wizard.person_dialog.father_name"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.mother_name"), label_style), row, 1)
        row += 1
        self.father_name = QLineEdit()
        self.father_name.setPlaceholderText(tr("wizard.person_dialog.father_name_placeholder"))
        self.father_name.setValidator(_name_validator)
        self.father_name.setStyleSheet(self._input_style())
        self._father_name_error = QLabel("")
        self._father_name_error.setStyleSheet(self._error_label_style())
        self._father_name_error.setVisible(False)
        fn_father_container = QVBoxLayout()
        fn_father_container.setSpacing(2)
        fn_father_container.setContentsMargins(0, 0, 0, 0)
        fn_father_container.addWidget(self.father_name)
        fn_father_container.addWidget(self._father_name_error)
        grid.addLayout(fn_father_container, row, 0)

        self.mother_name = QLineEdit()
        self.mother_name.setPlaceholderText(tr("wizard.person_dialog.mother_name_placeholder"))
        self.mother_name.setValidator(_name_validator)
        self.mother_name.setStyleSheet(self._input_style())
        grid.addWidget(self.mother_name, row, 1)
        row += 1

        # Row: Birth Date (col 0) | National ID (col 1)
        grid.addWidget(self._label(tr("wizard.person_dialog.birth_date"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.national_id") + " *", label_style), row, 1)
        row += 1
        birth_layout = QHBoxLayout()
        birth_layout.setSpacing(6)
        birth_layout.setContentsMargins(0, 0, 0, 0)

        from datetime import datetime as _dt
        self.birth_day_combo = make_editable_date_combo(
            items=[(str(d), d) for d in range(1, 32)],
            max_digits=2, placeholder=tr("wizard.person_dialog.day_placeholder"),
        )
        self.birth_month_combo = make_editable_date_combo(
            items=[(str(m), m) for m in range(1, 13)],
            max_digits=2, placeholder=tr("wizard.person_dialog.month_placeholder"),
        )
        self.birth_year_combo = make_editable_date_combo(
            items=[(str(y), y) for y in range(_dt.now().year, 1919, -1)],
            max_digits=4, placeholder=tr("wizard.person_dialog.year_placeholder"),
        )

        birth_layout.addWidget(self.birth_day_combo, 1)
        birth_layout.addWidget(self.birth_month_combo, 1)
        birth_layout.addWidget(self.birth_year_combo, 2)
        birth_container = QWidget()
        birth_container.setStyleSheet("background-color: transparent;")
        birth_container.setLayout(birth_layout)
        grid.addWidget(birth_container, row, 0)

        self.national_id = QLineEdit()
        self.national_id.setPlaceholderText("0000000000")
        self.national_id.setValidator(QRegExpValidator(QtRegExp(r"\d{0,11}")))
        self.national_id.setStyleSheet(self._input_style())
        self._nid_error = QLabel("")
        self._nid_error.setStyleSheet(self._error_label_style())
        self._nid_error.setVisible(False)
        nid_container = QVBoxLayout()
        nid_container.setSpacing(2)
        nid_container.setContentsMargins(0, 0, 0, 0)
        nid_container.addWidget(self.national_id)
        nid_container.addWidget(self._nid_error)
        grid.addLayout(nid_container, row, 1)
        row += 1

        # Row: Nationality (col 0) | Gender (col 1)
        grid.addWidget(self._label(tr("wizard.person_dialog.nationality"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.gender"), label_style), row, 1)
        row += 1
        self.nationality = RtlCombo()
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_nationality_options():
            self.nationality.addItem(display_name, code)
        self.nationality.setStyleSheet(self._input_style())
        grid.addWidget(self.nationality, row, 0)

        self.gender = self._build_gender_radios()
        grid.addWidget(self.gender, row, 1)
        row += 1

        # ID Document Type selector
        grid.addWidget(self._label(tr("wizard.person_dialog.id_document_type"), label_style), row, 0, 1, 2)
        row += 1
        self.id_doc_type_combo = QComboBox()
        from services.display_mappings import get_identification_document_type_options
        for code, label in get_identification_document_type_options():
            if code == 0:
                continue
            self.id_doc_type_combo.addItem(label, code)
        self.id_doc_type_combo.setStyleSheet(self._input_style())
        grid.addWidget(self.id_doc_type_combo, row, 0, 1, 2)
        row += 1

        # ID Photos upload
        grid.addWidget(self._label(tr("wizard.person_dialog.attach_id_photos"), label_style), row, 0, 1, 2)
        row += 1
        upload_frame = self._create_upload_frame(self._browse_files, "id_upload", button_text=tr("wizard.person_dialog.attach_id_photos"))
        grid.addWidget(upload_frame, row, 0, 1, 2)

        tab_layout.addLayout(grid)

        self.tab_widget.addTab(tab, "")

    # Tab 2: Contact Information

    def _setup_tab2_contact(self):
        """Tab 2: Person role, email, mobile, landline."""
        tab = QWidget()
        tab.setLayoutDirection(get_layout_direction())
        tab.setStyleSheet("background-color: transparent;")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(6)

        label_style = "color: #1E293B; font-weight: 700; font-size: 11pt; background: transparent;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0

        # Relationship to household head (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.person_role"), label_style), row, 0, 1, 2)
        row += 1
        self.person_role = RtlCombo()
        self.person_role.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_relationship_to_head_options():
            self.person_role.addItem(display_name, code)
        self.person_role.setStyleSheet(self._input_style())
        grid.addWidget(self.person_role, row, 0, 1, 2)
        row += 1

        # Email (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.email"), label_style), row, 0, 1, 2)
        row += 1
        self.email = QLineEdit()
        self.email.setPlaceholderText("*****@gmail.com")
        self.email.setValidator(QRegExpValidator(QtRegExp(r"[a-zA-Z0-9@._\-+]+")))
        self.email.setStyleSheet(self._input_style())
        self._email_error = QLabel("")
        self._email_error.setStyleSheet(self._error_label_style())
        self._email_error.setVisible(False)
        email_container = QVBoxLayout()
        email_container.setSpacing(2)
        email_container.setContentsMargins(0, 0, 0, 0)
        email_container.addWidget(self.email)
        email_container.addWidget(self._email_error)
        grid.addLayout(email_container, row, 0, 1, 2)
        row += 1

        # Landline (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.phone"), label_style), row, 0, 1, 2)
        row += 1
        landline_frame = QFrame()
        landline_frame.setStyleSheet("""
            QFrame {
                border: 1px solid rgba(56,144,223,0.2);
                border-radius: 8px;
                background-color: #f0f7ff;
                min-height: 36px; max-height: 36px;
            }
        """)
        landline_frame.setLayoutDirection(Qt.LeftToRight)
        land_layout = QHBoxLayout(landline_frame)
        land_layout.setContentsMargins(0, 0, 0, 0)
        land_layout.setSpacing(0)
        self.lbl_landline_prefix = QLabel("0")
        self.lbl_landline_prefix.setFixedWidth(ScreenScale.w(40))
        self.lbl_landline_prefix.setAlignment(Qt.AlignCenter)
        self.lbl_landline_prefix.setStyleSheet("""
            QLabel {
                color: #3890DF;
                font-size: 13px;
                font-weight: 600;
                border-right: 1px solid rgba(56,144,223,0.35);
                padding: 0 10px;
                background: transparent;
            }
        """)
        self.landline_digits = QLineEdit()
        self.landline_digits.setPlaceholderText("xxxxxxxxx")
        self.landline_digits.setValidator(QRegExpValidator(QtRegExp(r"\d{0,9}")))
        self.landline_digits.setLayoutDirection(Qt.LeftToRight)
        self.landline_digits.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                color: #2C3E50; font-size: 14px; padding: 0 10px;
            }
        """)
        land_layout.addWidget(self.lbl_landline_prefix)
        land_layout.addWidget(self.landline_digits)
        self._landline_error = QLabel("")
        self._landline_error.setStyleSheet(self._error_label_style())
        self._landline_error.setVisible(False)
        landline_container = QVBoxLayout()
        landline_container.setSpacing(2)
        landline_container.setContentsMargins(0, 0, 0, 0)
        landline_container.addWidget(landline_frame)
        landline_container.addWidget(self._landline_error)
        grid.addLayout(landline_container, row, 0, 1, 2)
        row += 1

        # Mobile (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.mobile"), label_style), row, 0, 1, 2)
        row += 1
        mobile_container = QFrame()
        mobile_container.setStyleSheet("""
            QFrame {
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 8px;
                background-color: #f0f7ff;
                min-height: 36px; max-height: 36px;
            }
        """)
        mobile_container.setLayoutDirection(Qt.LeftToRight)
        mobile_layout = QHBoxLayout(mobile_container)
        mobile_layout.setContentsMargins(0, 0, 0, 0)
        mobile_layout.setSpacing(0)

        prefix_label = QLabel("+963 | 09")
        prefix_label.setFixedWidth(ScreenScale.w(90))
        prefix_label.setAlignment(Qt.AlignCenter)
        prefix_label.setStyleSheet("""
            color: #6B7280;
            font-size: 14px; font-weight: 500;
            border: none; border-right: 1px solid rgba(56,144,223,0.35);
            background: transparent; padding: 0 8px;
        """)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("xxxxxxxx")
        self.phone.setValidator(QRegExpValidator(QtRegExp(r"\d{0,8}")))
        self.phone.setLayoutDirection(Qt.LeftToRight)
        self.phone.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                color: #2C3E50;
                font-size: 14px; padding: 0 10px;
            }
        """)

        mobile_layout.addWidget(prefix_label)
        mobile_layout.addWidget(self.phone)
        self._mobile_error = QLabel("")
        self._mobile_error.setStyleSheet(self._error_label_style())
        self._mobile_error.setVisible(False)
        mobile_outer = QVBoxLayout()
        mobile_outer.setSpacing(2)
        mobile_outer.setContentsMargins(0, 0, 0, 0)
        mobile_outer.addWidget(mobile_container)
        mobile_outer.addWidget(self._mobile_error)
        grid.addLayout(mobile_outer, row, 0, 1, 2)

        tab_layout.addLayout(grid)

        self.tab_widget.addTab(tab, "")

    # Tab 3: Relation & Evidence

    def _setup_tab3_relation(self):
        """Tab 3: Claim type, ownership share, dates, documents."""
        tab = QWidget()
        tab.setLayoutDirection(get_layout_direction())
        tab.setStyleSheet("background-color: transparent;")
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(6)

        label_style = "color: #1E293B; font-weight: 700; font-size: 11pt; background: transparent;"

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        row = 0

        # Row: Claim Type | Ownership Share
        grid.addWidget(self._label(tr("wizard.person_dialog.claim_type_label"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.ownership_share"), label_style), row, 1)
        row += 1
        self.rel_type_combo = RtlCombo()
        self.rel_type_combo.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_relation_type_options():
            self.rel_type_combo.addItem(display_name, code)
        self.rel_type_combo.setStyleSheet(self._input_style())
        grid.addWidget(self.rel_type_combo, row, 0)

        self.ownership_share = QLineEdit()
        self.ownership_share.setPlaceholderText(tr("wizard.person_dialog.ownership_share_placeholder"))
        self.ownership_share.setValidator(QIntValidator(0, 2400, self))
        self.ownership_share.editingFinished.connect(self._clamp_ownership_share)
        self.ownership_share.setStyleSheet(self._input_style())
        self.ownership_share.setEnabled(False)
        self._ownership_error = QLabel("")
        self._ownership_error.setStyleSheet(self._error_label_style())
        self._ownership_error.setVisible(False)
        ownership_container = QVBoxLayout()
        ownership_container.setSpacing(2)
        ownership_container.setContentsMargins(0, 0, 0, 0)
        ownership_container.addWidget(self.ownership_share)
        ownership_container.addWidget(self._ownership_error)
        grid.addLayout(ownership_container, row, 1)
        row += 1

        # Row: Start Date (3 fields) | Evidence Type
        grid.addWidget(self._label(tr("wizard.person_dialog.relation_start_date"), label_style), row, 0)
        grid.addWidget(self._label(tr("wizard.person_dialog.evidence_type"), label_style), row, 1)
        row += 1
        date_layout = QHBoxLayout()
        date_layout.setSpacing(6)
        date_layout.setContentsMargins(0, 0, 0, 0)
        input_style = self._input_style()

        self.start_day = RtlCombo()
        self.start_day.addItem(tr("wizard.person_dialog.day"), None)
        for d in range(1, 32):
            self.start_day.addItem(str(d), d)
        self.start_day.setStyleSheet(input_style)

        self.start_month = RtlCombo()
        self.start_month.addItem(tr("wizard.person_dialog.month"), None)
        _date_locale = QLocale(QLocale.Arabic if get_language() == "ar" else QLocale.English)
        for m in range(1, 13):
            self.start_month.addItem(_date_locale.monthName(m, QLocale.ShortFormat), m)
        self.start_month.setStyleSheet(input_style)

        self.start_year = RtlCombo()
        self.start_year.addItem(tr("wizard.person_dialog.year"), None)
        for y in range(QDate.currentDate().year(), 1939, -1):
            self.start_year.addItem(str(y), y)
        self.start_year.setStyleSheet(input_style)

        date_layout.addWidget(self.start_day, 1)
        date_layout.addWidget(self.start_month, 2)
        date_layout.addWidget(self.start_year, 2)
        date_container = QWidget()
        date_container.setStyleSheet("background-color: transparent;")
        date_container.setLayout(date_layout)
        grid.addWidget(date_container, row, 0)

        self.evidence_type = RtlCombo()
        self.evidence_type.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_evidence_type_options():
            if code == 0:
                continue
            self.evidence_type.addItem(display_name, code)
        self.evidence_type.setStyleSheet(self._input_style())
        grid.addWidget(self.evidence_type, row, 1)
        row += 1

        # Row: Evidence Description (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.evidence_description"), label_style), row, 0, 1, 2)
        row += 1
        self.evidence_desc = QLineEdit()
        self.evidence_desc.setPlaceholderText(tr("wizard.person_dialog.evidence_desc_placeholder"))
        self.evidence_desc.setStyleSheet(self._input_style())
        grid.addWidget(self.evidence_desc, row, 0, 1, 2)
        row += 1

        # Notes (full width)
        grid.addWidget(self._label(tr("wizard.person_dialog.notes_label"), label_style), row, 0, 1, 2)
        row += 1
        self.notes = CenteredTextEdit()
        self.notes.setPlaceholderText(tr("wizard.person_dialog.notes_placeholder"))
        self.notes.setPlaceholderStyleSheet(
            "color: rgba(180, 210, 240, 0.4); background: transparent; font-size: 16px; font-weight: 400;"
        )
        self.notes.setMaximumHeight(ScreenScale.h(80))
        self.notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 8px;
                padding: 10px;
                background-color: #FFFFFF;
                color: #2C3E50;
                font-size: 16px;
            }
            QTextEdit:focus {
                border: 1px solid rgba(56, 144, 223, 0.5);
            }
        """)
        self.notes.setLayoutDirection(get_layout_direction())
        grid.addWidget(self.notes, row, 0, 1, 2)
        row += 1

        # Document images section
        grid.addWidget(self._label(tr("wizard.person_dialog.document_images"), label_style), row, 0, 1, 2)
        row += 1

        # Radio buttons: has / no documents
        radio_layout = QHBoxLayout()
        self.rb_has_docs = QRadioButton(tr("wizard.person_dialog.has_documents"))
        self.rb_no_docs = QRadioButton(tr("wizard.person_dialog.no_documents"))
        self.rb_has_docs.setChecked(True)
        self._doc_radio_group = QButtonGroup(self)
        self._doc_radio_group.addButton(self.rb_has_docs, 1)
        self._doc_radio_group.addButton(self.rb_no_docs, 0)
        radio_layout.addWidget(self.rb_has_docs)
        radio_layout.addWidget(self.rb_no_docs)
        radio_layout.addStretch()

        radio_widget = QWidget()
        radio_widget.setStyleSheet("background-color: transparent;")
        radio_widget.setLayout(radio_layout)
        grid.addWidget(radio_widget, row, 0, 1, 2)
        row += 1

        # Upload frame for relation documents
        self._rel_upload_frame = self._create_upload_frame(self._browse_relation_files, "rel_upload", button_text=tr("wizard.person_dialog.attach_document"))
        # Add "Choose Existing Document" link to the upload frame
        choose_btn = QPushButton(tr("wizard.person_dialog.choose_existing_doc"))
        choose_btn.setStyleSheet("""
            QPushButton {
                color: rgba(100, 220, 160, 0.9);
                text-decoration: underline;
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 500;
                padding: 0px;
            }
            QPushButton:hover { color: rgba(130, 240, 180, 1.0); }
        """)
        choose_btn.setCursor(Qt.PointingHandCursor)
        choose_btn.clicked.connect(self._choose_existing_document)
        # Insert into the upload frame's row layout (before the trailing stretch)
        row_layout = self._rel_upload_frame.layout().itemAt(0).layout()
        row_layout.insertWidget(row_layout.count() - 1, choose_btn)
        grid.addWidget(self._rel_upload_frame, row, 0, 1, 2)

        # Toggle upload frame visibility based on radio
        self.rb_no_docs.toggled.connect(lambda checked: self._rel_upload_frame.setVisible(not checked))

        tab_layout.addLayout(grid)

        self.tab_widget.addTab(tab, "")

    # UI Helpers

    def _label(self, text: str, style: str) -> QLabel:
        """Create a styled label."""
        lbl = QLabel(text)
        lbl.setStyleSheet(style)
        return lbl

    def _create_btn(self, text: str, primary: bool = True, callback=None) -> QPushButton:
        """Create a styled action button."""
        btn = QPushButton(text)
        btn.setFixedHeight(ScreenScale.h(44))
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3890DF;
                    color: white;
                    border: 1px solid #3890DF;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #2E7BD6;
                    border-color: #2E7BD6;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFFFFF;
                    color: #374151;
                    border: 1px solid rgba(56, 144, 223, 0.2);
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #EBF5FF;
                    border-color: rgba(56, 144, 223, 0.4);
                }
            """)
        if callback:
            btn.clicked.connect(callback)
        return btn

    def _create_upload_frame(self, browse_callback, obj_name: str, button_text: str = None) -> QFrame:
        """Create a file upload frame with icon + blue text + thumbnail previews."""
        from ui.components.icon import Icon

        frame = QFrame()
        frame.setObjectName(obj_name)
        frame.setMinimumHeight(ScreenScale.h(55))
        frame.setStyleSheet(f"""
            QFrame#{obj_name} {{
                border: 2px dashed rgba(56, 144, 223, 0.3);
                border-radius: 8px;
                background-color: transparent;
            }}
        """)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(6)

        # Row: centered icon + text, thumbnails on the side
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        # Thumbnails container (left side in RTL = trailing end)
        thumbnails_container = QWidget()
        thumbnails_container.setStyleSheet("border: none; background: transparent;")
        thumbnails_layout = QHBoxLayout(thumbnails_container)
        thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        thumbnails_layout.setSpacing(6)
        row_layout.addWidget(thumbnails_container)

        row_layout.addStretch()

        # Upload icon (centered)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(ScreenScale.w(22), ScreenScale.h(22))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        upload_pixmap = Icon.load_pixmap("upload_file", size=20)
        if upload_pixmap and not upload_pixmap.isNull():
            icon_lbl.setPixmap(upload_pixmap)
        else:
            icon_lbl.setText("📎")
            icon_lbl.setStyleSheet("border: none; font-size: 16px; background: transparent;")
        icon_lbl.setCursor(Qt.PointingHandCursor)
        icon_lbl.mousePressEvent = lambda e: browse_callback()
        row_layout.addWidget(icon_lbl)

        # Blue underlined text (centered, next to icon)
        text_btn = QPushButton(button_text or tr("wizard.person_dialog.attach_id_photos"))
        text_btn.setStyleSheet("""
            QPushButton {
                color: rgba(140, 190, 240, 0.9);
                text-decoration: underline;
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 500;
                padding: 0px;
            }
            QPushButton:hover { color: rgba(180, 210, 250, 1.0); }
        """)
        text_btn.setCursor(Qt.PointingHandCursor)
        text_btn.clicked.connect(browse_callback)
        row_layout.addWidget(text_btn)

        row_layout.addStretch()

        frame_layout.addLayout(row_layout)

        # Store references
        frame._thumbnails_container = thumbnails_container
        frame._thumbnails_layout = thumbnails_layout
        frame._text_btn = text_btn
        return frame

    def _create_thumbnail_widget(self, file_path: str, remove_callback) -> QWidget:
        """Create a single thumbnail widget with image preview and X remove button."""
        container = QWidget()
        container.setFixedSize(ScreenScale.w(48), ScreenScale.h(48))
        container.setStyleSheet("border: none; background: transparent;")

        # Thumbnail image
        thumb = QLabel(container)
        thumb.setFixedSize(ScreenScale.w(44), ScreenScale.h(44))
        thumb.move(4, 4)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            QLabel {
                border: 1px solid rgba(56, 144, 223, 0.3);
                border-radius: 6px;
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        thumb.setCursor(Qt.PointingHandCursor)

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            thumb.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            thumb.setText("📄")

        # Click to open image in system viewer
        from PyQt5.QtGui import QDesktopServices
        def _open_file(e, fp=file_path):
            import os
            if not os.path.exists(fp):
                from ui.components.toast import Toast
                from services.translation_manager import tr as _tr
                Toast.show_toast(self, _tr("page.claim_details.cannot_download"), Toast.ERROR, duration=6000)
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(fp))
        thumb.mousePressEvent = _open_file

        # X remove button (small dark circle, top-left corner)
        x_btn = QLabel(container)
        x_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
        x_btn.move(0, 0)
        x_btn.setText("✕")
        x_btn.setAlignment(Qt.AlignCenter)
        x_btn.setStyleSheet("""
            QLabel {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border-radius: 9px;
                font-size: 10px;
                font-weight: bold;
                border: none;
            }
        """)
        x_btn.setCursor(Qt.PointingHandCursor)
        def _remove_file(e, fp=file_path):
            remove_callback(fp)
        x_btn.mousePressEvent = _remove_file

        return container

    def _update_upload_thumbnails(self, obj_name: str, file_paths: list):
        """Refresh thumbnail display in the specified upload frame."""
        frame = self.findChild(QFrame, obj_name)
        if not frame or not hasattr(frame, '_thumbnails_layout'):
            return

        layout = frame._thumbnails_layout
        # Clear existing thumbnails
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new thumbnails
        if obj_name == "id_upload":
            remove_fn = self._remove_uploaded_file
        else:
            remove_fn = self._remove_relation_file

        for fp in file_paths:
            thumb_widget = self._create_thumbnail_widget(fp, remove_fn)
            layout.addWidget(thumb_widget)

    def _remove_uploaded_file(self, file_path: str):
        """Remove an ID photo file and refresh thumbnails.
        In edit mode: defers delete for possible replacement via PUT.
        In create mode: deletes from server immediately."""
        import os
        norm = os.path.normpath(file_path)
        if norm in self._evidence_ids and self._survey_id:
            evidence_id = self._evidence_ids[norm]
            if self.editing_mode:
                self._pending_id_replacements.append(evidence_id)
                logger.info(f"Evidence {evidence_id} queued for replacement")
            else:
                try:
                    self._refresh_token()
                    self._api_service.delete_evidence(self._survey_id, evidence_id)
                    logger.info(f"Evidence deleted from server: {evidence_id}")
                except Exception as e:
                    logger.error(f"Failed to delete evidence {evidence_id}: {e}")
            del self._evidence_ids[norm]
        if file_path in self.uploaded_files:
            self.uploaded_files.remove(file_path)
        self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _remove_relation_file(self, file_path: str):
        """Remove a relation evidence file and refresh thumbnails.
        In edit mode: defers delete for possible replacement via PUT.
        In create mode: deletes from server immediately.
        Existing selected docs are just unlinked (not deleted)."""
        entry = next((f for f in self.relation_uploaded_files if f.get("path") == file_path), None)
        if entry and entry.get('_selected_existing'):
            # Existing doc: just remove from list, don't delete from server
            self.relation_uploaded_files = [f for f in self.relation_uploaded_files if f is not entry]
            self._refresh_relation_thumbnails()
            return
        if entry and entry.get("evidence_id") and self._survey_id:
            evidence_id = entry["evidence_id"]
            if self.editing_mode:
                self._pending_rel_replacements.append(evidence_id)
                logger.info(f"Tenure evidence {evidence_id} queued for replacement")
            else:
                try:
                    self._refresh_token()
                    self._api_service.delete_evidence(self._survey_id, evidence_id)
                    logger.info(f"Tenure evidence deleted from server: {evidence_id}")
                except Exception as e:
                    logger.error(f"Failed to delete tenure evidence: {e}")
        self.relation_uploaded_files = [f for f in self.relation_uploaded_files if f.get("path") != file_path]
        self._refresh_relation_thumbnails()

    # Editable combo + gender radio helpers

    def _make_editable_combo(self, items, max_digits: int, placeholder: str = "") -> QComboBox:
        combo = QComboBox()
        combo.setLayoutDirection(Qt.LeftToRight)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        for label, data in items:
            combo.addItem(label, data)
        line_edit = combo.lineEdit()
        if line_edit is not None:
            line_edit.setValidator(QRegExpValidator(QtRegExp(rf"\d{{0,{max_digits}}}")))
            line_edit.setAlignment(Qt.AlignCenter)
            if placeholder:
                line_edit.setPlaceholderText(placeholder)
        combo.setCurrentIndex(-1)
        combo.clearEditText()
        combo.setStyleSheet(self._input_style())
        return combo

    @staticmethod
    def _read_int_from_combo(combo: QComboBox):
        val = combo.currentData()
        if val is not None:
            return val
        text = combo.currentText().strip()
        if text.isdigit():
            try:
                return int(text)
            except ValueError:
                return None
        return None

    def _build_gender_radios(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(container)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(ScreenScale.w(14))

        self._gender_group = QButtonGroup(container)
        self._gender_group.setExclusive(True)
        self._gender_btns = []

        radio_css = f"""
            QRadioButton {{
                color: #2C3E50;
                background: transparent;
                font-size: 10pt;
                spacing: 6px;
                padding: 2px 4px;
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border: 1.5px solid #B0BEC5;
                border-radius: 9px;
                background: white;
            }}
            QRadioButton::indicator:checked {{
                border: 1.5px solid #3890DF;
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                    stop:0 #3890DF, stop:0.55 #3890DF,
                    stop:0.6 white, stop:1 white);
            }}
        """
        for code, label in get_gender_options():
            btn = QRadioButton(label)
            btn.setStyleSheet(radio_css)
            btn.setProperty("gender_code", code)
            lay.addWidget(btn)
            self._gender_group.addButton(btn)
            self._gender_btns.append(btn)
        lay.addStretch()
        return container

    def _get_gender(self):
        for btn in getattr(self, "_gender_btns", []):
            if btn.isChecked():
                return btn.property("gender_code")
        return None

    def _set_gender(self, code):
        for btn in getattr(self, "_gender_btns", []):
            if btn.property("gender_code") == code:
                btn.setChecked(True)
                return
        self._gender_group.setExclusive(False)
        for btn in getattr(self, "_gender_btns", []):
            btn.setChecked(False)
        self._gender_group.setExclusive(True)

    def _input_style(self) -> str:
        """Custom input style with light background."""
        return """
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 8px;
                padding: 6px;
                background-color: #FFFFFF;
                color: #2C3E50;
                font-size: 14px;
                min-height: 18px;
                max-height: 18px;
            }
            QComboBox {
                padding-left: 4px;
            }
            QComboBox QLineEdit {
                border: none;
                background: transparent;
                color: #2C3E50;
                padding: 0px 4px;
                min-height: 18px;
                max-height: 18px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
                border: 1px solid rgba(56, 144, 223, 0.5);
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #9CA3AF;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 0px;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                padding: 4px;
                selection-background-color: #EBF5FF;
                selection-color: #1E293B;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 6px 10px;
                border-radius: 6px;
                color: #1E293B;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #EBF5FF;
            }
            QComboBox QAbstractItemView QScrollBar:vertical {
                background: transparent;
                width: 5px;
                margin: 4px 0px;
                border-radius: 2px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical {
                background: rgba(56, 144, 223, 0.3);
                min-height: 30px;
                border-radius: 2px;
            }
            QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {
                background: rgba(56, 144, 223, 0.5);
            }
            QComboBox QAbstractItemView QScrollBar::add-line:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QComboBox QAbstractItemView QScrollBar::add-page:vertical,
            QComboBox QAbstractItemView QScrollBar::sub-page:vertical {
                background: none;
            }
        """

    def _error_label_style(self) -> str:
        """Style for inline validation error labels."""
        return f"color: {Colors.ERROR}; font-size: 11px; font-weight: 700; background: transparent; padding: 0px;"

    def _input_error_style(self) -> str:
        """Input style with red border for validation error state."""
        return """
            QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
                border: 2px solid #e74c3c;
                border-radius: 8px;
                padding: 6px;
                background-color: rgba(231, 76, 60, 0.06);
                color: #2C3E50;
                font-size: 14px;
                min-height: 18px;
                max-height: 18px;
            }
            QComboBox {
                padding-left: 4px;
            }
            QComboBox QLineEdit {
                border: none;
                background: transparent;
                color: #2C3E50;
                padding: 0px 4px;
                min-height: 18px;
                max-height: 18px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
                border: 2px solid #e74c3c;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid rgba(200, 220, 240, 0.6);
            }
        """

    def _set_field_error(self, field, error_label, message):
        """Show inline error: red border on field + small ⚠ indicator below."""
        if field not in self._field_styles:
            self._field_styles[field] = field.styleSheet()
        field.setStyleSheet(self._input_error_style())
        error_label.setText(message)
        error_label.setVisible(True)

    def _clear_field_error(self, field, error_label):
        """Clear inline error: restore original style."""
        if field in self._field_styles:
            field.setStyleSheet(self._field_styles[field])
        else:
            field.setStyleSheet(self._input_style())
        error_label.setText("")
        error_label.setVisible(False)

    def _clear_all_errors(self):
        """Clear all inline validation errors."""
        error_pairs = [
            (self.first_name, self._first_name_error),
            (self.last_name, self._last_name_error),
            (self.father_name, self._father_name_error),
            (self.national_id, self._nid_error),
            (self.phone, self._mobile_error),
            (self.landline_digits, self._landline_error),
            (self.email, self._email_error),
            (self.ownership_share, self._ownership_error),
        ]
        for field, label in error_pairs:
            if label.isVisible():
                self._clear_field_error(field, label)

    def _date_input_style(self) -> str:
        """Custom date input style with light blue background."""
        cal_img = str(Config.IMAGES_DIR / "calender.png").replace("\\", "/")
        return """
            QDateEdit {
                background-color: #f0f7ff;
                border: 1px solid #D0D7E2;
                border-radius: 8px;
                padding: 10px;
                color: #333;
                font-size: 14px;
                min-height: 20px;
                max-height: 20px;
            }
            QDateEdit:focus {
                border: 1px solid #D0D7E2;
            }
            QDateEdit::drop-down {
                border: none;
                width: 25px;
                subcontrol-position: right center;
            }
            QDateEdit::down-arrow {
                image: url(""" + cal_img + """);
                width: 16px;
                height: 16px;
            }
            /* Calendar popup styling */
            QCalendarWidget {
                background-color: #FFFFFF;
                border: 1px solid #D0D7E2;
                border-radius: 10px;
            }
            QCalendarWidget QToolButton {
                color: #333;
                background-color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #f0f7ff;
            }
            QCalendarWidget QToolButton::menu-indicator {
                image: none;
            }
            QCalendarWidget QToolButton#qt_calendar_prevmonth {
                qproperty-icon: none;
                qproperty-text: "<";
                color: #3890DF;
                font-weight: bold;
                font-size: 16px;
            }
            QCalendarWidget QToolButton#qt_calendar_nextmonth {
                qproperty-icon: none;
                qproperty-text: ">";
                color: #3890DF;
                font-weight: bold;
                font-size: 16px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #FFFFFF;
                border-bottom: 1px solid #D0D7E2;
                padding: 4px;
            }
            QCalendarWidget QAbstractItemView {
                background-color: #FFFFFF;
                color: #333;
                selection-background-color: #3890DF;
                selection-color: white;
                font-size: 12px;
                outline: none;
                border: none;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #333;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #B0BEC5;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #f8faff;
            }
            QCalendarWidget QMenu {
                background-color: #FFFFFF;
                border: 1px solid #D0D7E2;
                border-radius: 8px;
                color: #333;
            }
            QCalendarWidget QMenu::item:selected {
                background-color: #EBF5FF;
                color: #333;
            }
            QCalendarWidget QSpinBox {
                background-color: #FFFFFF;
                color: #333;
                border: 1px solid #D0D7E2;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 13px;
            }
        """

    # Tab Navigation

    def _go_to_tab2(self):
        """Tab 1 → Tab 2: Validate required fields + format check, then switch."""
        if self.read_only:
            self.tab_widget.setCurrentIndex(1)
            return
        self._clear_all_errors()
        from ui.components.toast import Toast

        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        father = self.father_name.text().strip()
        mother = self.mother_name.text().strip()

        if not first:
            Toast.show_toast(self, tr("wizard.person_dialog.enter_first_name"), Toast.ERROR)
            return
        if not last:
            Toast.show_toast(self, tr("wizard.person_dialog.enter_last_name"), Toast.ERROR)
            return
        if not father:
            Toast.show_toast(self, tr("wizard.person_dialog.enter_father_name"), Toast.ERROR)
            return
        if not mother:
            Toast.show_toast(self, tr("wizard.person_dialog.enter_mother_name"), Toast.ERROR)
            return

        nid = self.national_id.text().strip()
        if nid:
            if len(nid) != 11 or not nid.isdigit():
                Toast.show_toast(self, tr("wizard.person_dialog.nid_invalid"), Toast.ERROR)
                return

            original_nid = self.person_data.get('national_id') if self.person_data else None
            if nid != original_nid and self._api_service:
                try:
                    result = self._api_service.get_persons(national_id=nid, page_size=5)
                    items = result.get("items", [])
                    # Verify returned person's NID actually matches (API may not filter properly)
                    matching = [p for p in items
                                if (p.get('nationalId') or p.get('nationalNumber') or '') == nid]
                    if matching:
                        from ui.error_handler import ErrorHandler
                        name_parts = [
                            matching[0].get("firstNameArabic", ""),
                            matching[0].get("fatherNameArabic", ""),
                            matching[0].get("familyNameArabic", "")
                        ]
                        full_name = " ".join(p for p in name_parts if p)
                        msg = tr("wizard.person_dialog.nid_already_registered")
                        if full_name:
                            msg += f"\n{tr('wizard.person_dialog.name_label')}: {full_name}"
                        ErrorHandler.show_warning(self, msg, tr("common.warning"))
                        return
                except Exception:
                    pass

        self.tab_widget.setCurrentIndex(1)

    def _go_to_tab3(self):
        """Tab 2 → Tab 3: Validate contact format (optional fields), then switch."""
        import re
        if self.read_only:
            self.tab_widget.setCurrentIndex(2)
            return
        self._clear_all_errors()
        has_error = False
        # Optional format: mobile (if filled, must be 8 digits)
        if not self._validate_mobile(self.phone.text().strip()):
            self._set_field_error(self.phone, self._mobile_error, tr("wizard.person_dialog.invalid_mobile"))
            has_error = True
        # Optional format: landline (if filled, must be 7 digits)
        if not self._validate_landline(self.landline_digits.text().strip()):
            self._set_field_error(self.landline_digits, self._landline_error, tr("wizard.person_dialog.invalid_landline"))
            has_error = True
        # Optional format: email (if filled, must be valid)
        email_text = self.email.text().strip()
        if email_text and not re.match(r'^[a-zA-Z0-9@._\-+]+$', email_text):
            self._set_field_error(self.email, self._email_error, tr("wizard.person_dialog.invalid_email_chars"))
            has_error = True
        elif email_text and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email_text):
            self._set_field_error(self.email, self._email_error, tr("wizard.person_dialog.invalid_email"))
            has_error = True
        if has_error:
            return
        self.tab_widget.setCurrentIndex(2)

    def _go_to_tab1(self):
        """Tab 2 → Tab 1."""
        self.tab_widget.setCurrentIndex(0)

    def _go_to_tab2_back(self):
        """Tab 3 → Tab 2."""
        self.tab_widget.setCurrentIndex(1)

    # Keep legacy method name for backward compatibility
    def _save_person_and_switch_tab(self):
        """Legacy: validate and go to next tab."""
        self._go_to_tab2()

    # File Browsing

    def _browse_files(self):
        """Browse for ID photo files with duplicate detection."""
        from PyQt5.QtWidgets import QFileDialog
        import os
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            existing_names = {os.path.normpath(f) for f in self.uploaded_files}
            duplicates = []
            new_files = []
            for fp in file_paths:
                norm = os.path.normpath(fp)
                if norm in existing_names:
                    duplicates.append(fp)
                else:
                    new_files.append(fp)
                    existing_names.add(norm)
            if duplicates:
                dup_names = [os.path.basename(f) for f in duplicates]
                replace = self._show_duplicate_file_dialog(dup_names)
                if replace:
                    # Replace: add new files only (duplicates already exist)
                    self.uploaded_files.extend(new_files)
                # else: Cancel - don't add anything
            else:
                self.uploaded_files.extend(new_files)
            self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _browse_relation_files(self):
        """Browse for relation evidence files with dual-level duplicate detection."""
        from PyQt5.QtWidgets import QFileDialog
        import os
        import hashlib

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Documents (*.png *.jpg *.jpeg *.pdf *.doc *.docx *.mp3 *.wav *.ogg *.m4a)"
        )
        if not file_paths:
            return

        existing_paths = {os.path.normpath(f["path"]) for f in self.relation_uploaded_files}
        existing_hashes = {f["hash"] for f in self.relation_uploaded_files if f.get("hash")}

        duplicates = []
        new_files = []

        for fp in file_paths:
            norm = os.path.normpath(fp)
            # Level 1: Same path already added
            if norm in existing_paths:
                duplicates.append(fp)
                continue
            # Level 2: Same content (different path, same hash)
            file_hash = self._compute_file_hash(fp)
            if file_hash and file_hash in existing_hashes:
                duplicates.append(fp)
                continue
            new_files.append({"path": fp, "hash": file_hash})
            existing_paths.add(norm)
            if file_hash:
                existing_hashes.add(file_hash)

        if duplicates:
            dup_names = [os.path.basename(f) for f in duplicates]
            replace = self._show_duplicate_file_dialog(dup_names)
            if not replace:
                return

        if not new_files:
            return

        # Issue date: single file → direct dialog, multiple → ask same or separate
        if len(new_files) == 1:
            issue_date = self._show_issue_date_dialog(os.path.basename(new_files[0]["path"]))
            if issue_date is None:
                return
            new_files[0]["issue_date"] = issue_date
        elif len(new_files) > 1:
            use_same = self._ask_same_or_separate_dates(len(new_files))
            if use_same is None:
                return
            if use_same:
                issue_date = self._show_issue_date_dialog()
                if issue_date is None:
                    return
                for f in new_files:
                    f["issue_date"] = issue_date
            else:
                for f in new_files:
                    fname = os.path.basename(f["path"])
                    issue_date = self._show_issue_date_dialog(fname)
                    if issue_date is None:
                        continue
                    f["issue_date"] = issue_date
                new_files = [f for f in new_files if f.get("issue_date")]
                if not new_files:
                    return

        self.relation_uploaded_files.extend(new_files)
        self._refresh_relation_thumbnails()

    def _choose_existing_document(self):
        """Show EvidencePickerDialog to select existing survey documents."""
        if not self._survey_id:
            Toast.show_toast(self, tr("wizard.person_dialog.not_available_offline"), Toast.WARNING)
            return

        try:
            self._refresh_token()
            evidences = self._api_service.get_survey_evidences(self._survey_id, evidence_type="tenure")
        except Exception as e:
            logger.warning(f"Could not load existing docs: {e}")
            Toast.show_toast(self, tr("wizard.person_dialog.failed_load_docs"), Toast.ERROR)
            return

        if not evidences:
            Toast.show_toast(self, tr("wizard.person_dialog.no_existing_docs"), Toast.INFO)
            return

        already_linked = {
            f.get("evidence_id") for f in self.relation_uploaded_files
            if f.get("_selected_existing")
        }

        from ui.components.dialogs.evidence_picker_dialog import EvidencePickerDialog
        picker = EvidencePickerDialog(evidences, already_linked, parent=self)
        if picker.exec_() != QDialog.Accepted:
            return

        selected = picker.get_selected_data()
        if not selected:
            return

        for ev in selected:
            ev_id = self._extract_evidence_id(ev)
            file_name = ev.get('originalFileName') or ev.get('OriginalFileName') or ''
            issue_date = ev.get('documentIssuedDate') or ev.get('DocumentIssuedDate') or ''
            display = file_name or tr("wizard.person_dialog.document_label", doc_id=ev_id[:8])
            self.relation_uploaded_files.append({
                'path': '',
                'evidence_id': ev_id,
                'issue_date': str(issue_date)[:10] if issue_date else '',
                '_selected_existing': True,
                '_display_name': display,
            })

        self._refresh_relation_thumbnails()

    def _extract_evidence_id(self, ev: dict) -> str:
        """Extract evidence ID from API response dict."""
        return (ev.get('id') or ev.get('evidenceId')
                or ev.get('Id') or ev.get('EvidenceId') or '')

    def _refresh_relation_thumbnails(self):
        """Refresh relation document thumbnails including existing doc labels."""
        frame = self.findChild(QFrame, "rel_upload")
        if not frame or not hasattr(frame, '_thumbnails_layout'):
            return

        layout = frame._thumbnails_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for entry in self.relation_uploaded_files:
            if entry.get('_selected_existing'):
                # Existing doc: show as a styled label with remove button
                display = entry.get('_display_name', tr("wizard.person_dialog.document_default"))
                widget = self._create_existing_doc_widget(display, entry)
            elif entry.get('path'):
                widget = self._create_thumbnail_widget(entry['path'], self._remove_relation_file)
            else:
                continue
            layout.addWidget(widget)

    def _create_existing_doc_widget(self, display_name: str, entry: dict) -> QWidget:
        """Create a thumbnail widget for an existing server document with preview."""
        evidence_id = entry.get('evidence_id', '')

        container = QWidget()
        container.setFixedSize(ScreenScale.w(48), ScreenScale.h(48))
        container.setStyleSheet("border: none; background: transparent;")

        thumb = QLabel(container)
        thumb.setFixedSize(ScreenScale.w(44), ScreenScale.h(44))
        thumb.move(4, 4)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(
            "QLabel { border: 1px solid rgba(56, 144, 223, 0.3);"
            "border-radius: 6px; background-color: rgba(255,255,255,0.07); }"
        )
        thumb.setCursor(Qt.PointingHandCursor)
        thumb.setToolTip(display_name)

        ext = display_name.rsplit(".", 1)[-1].upper() if "." in display_name else "DOC"
        ext_colors = {"PDF": "#E53E3E", "JPG": "#3182CE", "JPEG": "#3182CE", "PNG": "#3182CE"}
        thumb.setText(ext[:4])
        thumb.setStyleSheet(
            thumb.styleSheet()
            + f"color: {ext_colors.get(ext, 'rgba(200,220,240,0.8)')};"
            "font-size: 11px; font-weight: bold;"
        )

        def _open_doc(e, eid=evidence_id, fn=display_name):
            from ui.components.evidence_viewer import download_and_open_evidence
            self._refresh_token()
            download_and_open_evidence(self, eid, fn)
        thumb.mousePressEvent = _open_doc

        x_btn = QLabel(container)
        x_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
        x_btn.move(0, 0)
        x_btn.setText("✕")
        x_btn.setAlignment(Qt.AlignCenter)
        x_btn.setStyleSheet("""
            QLabel {
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border-radius: 9px;
                font-size: 10px;
                font-weight: bold;
                border: none;
            }
        """)
        x_btn.setCursor(Qt.PointingHandCursor)
        def _remove(e, ent=entry):
            self._remove_existing_doc(ent)
        x_btn.mousePressEvent = _remove

        return container

    def _remove_existing_doc(self, entry: dict):
        """Remove a selected existing document (just unlink, don't delete from server)."""
        self.relation_uploaded_files = [
            f for f in self.relation_uploaded_files if f is not entry
        ]
        self._refresh_relation_thumbnails()

    def _show_duplicate_file_dialog(self, file_names: list) -> bool:
        """Show a small floating dialog for duplicate files. Returns True to replace, False to cancel."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QFont, QColor
        from ui.font_utils import create_font, FontManager

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(ScreenScale.w(300))

        # Container with white background + rounded corners
        container = QWidget(dlg)
        container.setObjectName("dup_container")
        container.setStyleSheet("""
            QWidget#dup_container {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(20, 20, 20, 16)
        c_layout.setSpacing(10)

        # Warning icon (small circle)
        icon_lbl = QLabel("⚠")
        icon_lbl.setFixedSize(ScreenScale.w(40), ScreenScale.h(40))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            background-color: #FEF3C7;
            border-radius: 20px;
            font-size: 18px;
        """)
        c_layout.addWidget(icon_lbl, 0, Qt.AlignCenter)

        # Title
        title_lbl = QLabel(tr("wizard.person_dialog.duplicate_files_title"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet("color: #1F2937; background: transparent;")
        c_layout.addWidget(title_lbl)

        # File names
        names_text = "\n".join(file_names[:3])
        if len(file_names) > 3:
            names_text += f"\n+{len(file_names) - 3} ..."
        msg_lbl = QLabel(names_text)
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        msg_lbl.setStyleSheet("color: #6B7280; background: transparent;")
        c_layout.addWidget(msg_lbl)

        c_layout.addSpacing(4)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedHeight(ScreenScale.h(34))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        cancel_btn.clicked.connect(dlg.reject)

        replace_btn = QPushButton(tr("wizard.person_dialog.replace_file"))
        replace_btn.setFixedHeight(ScreenScale.h(34))
        replace_btn.setCursor(Qt.PointingHandCursor)
        replace_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        replace_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        replace_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(replace_btn, 1)
        c_layout.addLayout(btn_row)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        return dlg.exec_() == QDialog.Accepted

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA-256 hash of a file for duplicate detection."""
        import hashlib
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (IOError, OSError) as e:
            logger.warning(f"Could not compute hash for {file_path}: {e}")
            return ""

    def _show_issue_date_dialog(self, filename: str = None) -> str:
        """Show a mini popup to enter document issue date. Returns ISO date string or None if cancelled."""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QPushButton, QGraphicsDropShadowEffect, QComboBox)
        from PyQt5.QtGui import QColor
        from ui.font_utils import create_font, FontManager
        from datetime import date as _date

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(ScreenScale.w(340))

        container = QWidget(dlg)
        container.setObjectName("date_container")
        container.setStyleSheet("""
            QWidget#date_container {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(20, 20, 20, 16)
        c_layout.setSpacing(12)

        title_lbl = QLabel(tr("wizard.person_dialog.issue_date_title"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet("color: #1F2937; background: transparent;")
        c_layout.addWidget(title_lbl)

        if filename:
            file_lbl = QLabel(filename)
            file_lbl.setAlignment(Qt.AlignCenter)
            file_lbl.setFont(create_font(size=9))
            file_lbl.setStyleSheet("color: #6B7280; background: transparent;")
            file_lbl.setWordWrap(True)
            c_layout.addWidget(file_lbl)

        combo_style = """
            QComboBox {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 6px 10px;
                background-color: #F9FAFB;
                font-size: 13px;
                min-height: 20px;
            }
            QComboBox:focus { border-color: #3B82F6; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center left; width: 20px; border: none; }
        """

        # Labels row
        labels_row = QHBoxLayout()
        labels_row.setSpacing(8)
        label_style = "color: #6B7280; font-size: 10px; font-weight: 600; background: transparent;"
        lbl_year = QLabel(tr("wizard.person_dialog.year"))
        lbl_year.setStyleSheet(label_style)
        lbl_year.setAlignment(Qt.AlignCenter)
        lbl_month = QLabel(tr("wizard.person_dialog.month"))
        lbl_month.setStyleSheet(label_style)
        lbl_month.setAlignment(Qt.AlignCenter)
        lbl_day = QLabel(tr("wizard.person_dialog.day"))
        lbl_day.setStyleSheet(label_style)
        lbl_day.setAlignment(Qt.AlignCenter)
        labels_row.addWidget(lbl_year, 2)
        labels_row.addWidget(lbl_month, 1)
        labels_row.addWidget(lbl_day, 1)
        c_layout.addLayout(labels_row)

        # Combo row
        date_row = QHBoxLayout()
        date_row.setSpacing(8)

        current_year = _date.today().year
        year_combo = QComboBox()
        year_combo.setStyleSheet(combo_style)
        year_combo.setLayoutDirection(Qt.LeftToRight)
        year_combo.addItem("--", None)
        for y in range(current_year, 1949, -1):
            year_combo.addItem(str(y), y)
        year_combo.setCurrentIndex(1)

        month_combo = QComboBox()
        month_combo.setStyleSheet(combo_style)
        month_combo.setLayoutDirection(Qt.LeftToRight)
        month_combo.addItem("--", None)
        for m in range(1, 13):
            month_combo.addItem(str(m), m)

        day_combo = QComboBox()
        day_combo.setStyleSheet(combo_style)
        day_combo.setLayoutDirection(Qt.LeftToRight)
        day_combo.addItem("--", None)
        for d in range(1, 32):
            day_combo.addItem(str(d), d)

        date_row.addWidget(year_combo, 2)
        date_row.addWidget(month_combo, 1)
        date_row.addWidget(day_combo, 1)
        c_layout.addLayout(date_row)

        c_layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setFixedHeight(ScreenScale.h(34))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        cancel_btn.clicked.connect(dlg.reject)

        confirm_btn = QPushButton(tr("common.confirm"))
        confirm_btn.setFixedHeight(ScreenScale.h(34))
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        confirm_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(confirm_btn, 1)
        c_layout.addLayout(btn_row)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        if dlg.exec_() == QDialog.Accepted:
            y = year_combo.currentData()
            m = month_combo.currentData()
            d = day_combo.currentData()
            if y:
                month = m if m else 1
                day = d if d else 1
                return f"{y:04d}-{month:02d}-{day:02d}"
            return ""
        return ""

    def _ask_same_or_separate_dates(self, file_count: int):
        """Ask user: same date for all files or separate? Returns True=same, False=separate, None=cancelled."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor
        from ui.font_utils import create_font, FontManager

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dlg.setAttribute(Qt.WA_TranslucentBackground)
        dlg.setFixedWidth(ScreenScale.w(340))
        result = [None]

        container = QWidget(dlg)
        container.setObjectName("date_ask_container")
        container.setStyleSheet("""
            QWidget#date_ask_container {
                background-color: #FFFFFF;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(20, 20, 20, 16)
        c_layout.setSpacing(12)

        title = QLabel(tr("wizard.person_dialog.date_question_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #1F2937; background: transparent;")
        c_layout.addWidget(title)

        subtitle = QLabel(tr("wizard.person_dialog.date_question_subtitle", count=file_count))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(create_font(size=9))
        subtitle.setStyleSheet("color: #6B7280; background: transparent;")
        subtitle.setWordWrap(True)
        c_layout.addWidget(subtitle)

        c_layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        same_btn = QPushButton(tr("wizard.person_dialog.same_date"))
        same_btn.setFixedHeight(ScreenScale.h(34))
        same_btn.setCursor(Qt.PointingHandCursor)
        same_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        same_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        same_btn.clicked.connect(lambda: (result.__setitem__(0, True), dlg.accept()))

        sep_btn = QPushButton(tr("wizard.person_dialog.separate_dates"))
        sep_btn.setFixedHeight(ScreenScale.h(34))
        sep_btn.setCursor(Qt.PointingHandCursor)
        sep_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_MEDIUM))
        sep_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        sep_btn.clicked.connect(lambda: (result.__setitem__(0, False), dlg.accept()))

        btn_row.addWidget(same_btn, 1)
        btn_row.addWidget(sep_btn, 1)
        c_layout.addLayout(btn_row)

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(container)

        if dlg.exec_() == QDialog.Accepted:
            return result[0]
        return None

    # Validation

    def _on_claim_type_changed(self):
        """Enable ownership share only when claim type is Owner (1)."""
        is_owner = self.rel_type_combo.currentData() == 1
        self.ownership_share.setEnabled(is_owner)
        if not is_owner:
            self.ownership_share.clear()
            self._clear_field_error(self.ownership_share, self._ownership_error)

    def _clamp_ownership_share(self):
        """Clamp ownership share to 0-2400 range on focus out."""
        try:
            val = int(self.ownership_share.text() or 0)
            if val > 2400:
                self.ownership_share.setText("2400")
            elif val < 0:
                self.ownership_share.setText("0")
        except ValueError:
            self.ownership_share.setText("")

    def _build_birth_date_iso(self) -> str:
        """Build ISO date string from birth date combo boxes."""
        y = read_int_from_combo(self.birth_year_combo)
        m = read_int_from_combo(self.birth_month_combo)
        d = read_int_from_combo(self.birth_day_combo)
        if y:
            month = m if m else 1
            day = d if d else 1
            return f"{y:04d}-{month:02d}-{day:02d}"
        return ""

    def _build_start_date_iso(self) -> str:
        """Build ISO date string from the 3 dropdown combos (year/month/day)."""
        y = self.start_year.currentData()
        m = self.start_month.currentData()
        d = self.start_day.currentData()
        if y:
            month = m if m else 1
            day = d if d else 1
            return f"{y:04d}-{month:02d}-{day:02d}"
        return None

    def _format_phone(self, value: str):
        """Format phone for API: adds 09 prefix to 8-digit raw input."""
        if not value:
            return None
        digits = ''.join(c for c in value if c.isdigit())
        if len(digits) == 8:
            return f"09{digits}"
        if len(digits) == 10 and digits.startswith("09"):
            return digits
        return None

    def _validate_mobile(self, value: str) -> bool:
        """Validate mobile number: exactly 8 digits (prefix 09 is fixed in UI)."""
        if not value:
            return True
        digits = ''.join(c for c in value if c.isdigit())
        return len(digits) == 8

    def _validate_landline(self, value: str) -> bool:
        """Validate landline local digits: exactly 9 digits."""
        if not value:
            return True
        digits = ''.join(c for c in value if c.isdigit())
        return len(digits) == 9

    def _validate_national_id(self):
        """Validate national ID format. Uniqueness is checked server-side (409). Returns (valid, error_key)."""
        nid = self.national_id.text().strip()
        if not nid:
            return False, "wizard.person_dialog.nid_required"
        if len(nid) != 11 or not nid.isdigit():
            return False, "wizard.person_dialog.nid_invalid"
        return True, None

    # Load / Save Data

    def _load_person_data(self, data: Dict):
        """Load person data into form fields."""
        # Tab 1
        self.first_name.setText(data.get('first_name') or '')
        self.father_name.setText(data.get('father_name') or '')
        self.mother_name.setText(data.get('mother_name') or '')
        self.last_name.setText(data.get('last_name') or '')
        self.national_id.setText(data.get('national_id') or '')

        # Birth date (3 combos)
        if data.get('birth_date'):
            parts = str(data['birth_date'])[:10].split('-')
            if len(parts) >= 1 and parts[0].isdigit():
                idx = self.birth_year_combo.findData(int(parts[0]))
                if idx >= 0:
                    self.birth_year_combo.setCurrentIndex(idx)
            if len(parts) >= 2 and parts[1].isdigit():
                idx = self.birth_month_combo.findData(int(parts[1]))
                if idx >= 0:
                    self.birth_month_combo.setCurrentIndex(idx)
            if len(parts) >= 3 and parts[2].isdigit():
                idx = self.birth_day_combo.findData(int(parts[2]))
                if idx >= 0:
                    self.birth_day_combo.setCurrentIndex(idx)

        # Gender
        self._set_gender(data.get('gender'))

        # Nationality
        nat = data.get('nationality')
        if nat:
            idx = self.nationality.findData(nat)
            if idx >= 0:
                self.nationality.setCurrentIndex(idx)

        # Tab 2
        phone_val = data.get('phone') or ''
        if phone_val.startswith('09'):
            phone_val = phone_val[2:]
        self.phone.setText(phone_val)
        self.email.setText(data.get('email') or '')
        _land_val = data.get('landline') or ''
        if _land_val.startswith('0'):
            self.landline_digits.setText(_land_val[1:])
        else:
            self.landline_digits.setText(_land_val)

        # Person role
        role = data.get('person_role') or data.get('relationship_type')
        if role:
            idx = self.person_role.findData(role)
            if idx >= 0:
                self.person_role.setCurrentIndex(idx)

        # Tab 3 - relation data
        rel = data.get('relation_data', {})

        rel_type = rel.get('rel_type')
        if rel_type:
            for i in range(self.rel_type_combo.count()):
                if self.rel_type_combo.itemData(i) == rel_type:
                    self.rel_type_combo.setCurrentIndex(i)
                    break

        if rel.get('start_date'):
            parts = rel['start_date'].split('-')
            if len(parts) >= 1:
                idx = self.start_year.findData(int(parts[0]))
                if idx >= 0:
                    self.start_year.setCurrentIndex(idx)
            if len(parts) >= 2:
                idx = self.start_month.findData(int(parts[1]))
                if idx >= 0:
                    self.start_month.setCurrentIndex(idx)
            if len(parts) >= 3:
                idx = self.start_day.findData(int(parts[2]))
                if idx >= 0:
                    self.start_day.setCurrentIndex(idx)

        if rel.get('ownership_share') is not None:
            self.ownership_share.setText(str(rel['ownership_share']))

        if rel.get('evidence_type') is not None:
            idx = self.evidence_type.findData(rel['evidence_type'])
            if idx >= 0:
                self.evidence_type.setCurrentIndex(idx)

        if rel.get('evidence_desc'):
            self.evidence_desc.setText(rel['evidence_desc'])

        if rel.get('notes'):
            self.notes.setPlainText(rel['notes'])

        # Restore document files from context (same wizard session)
        import os
        if data.get('_uploaded_files'):
            self.uploaded_files = [f for f in data['_uploaded_files'] if os.path.exists(f)]
            self._update_upload_thumbnails("id_upload", self.uploaded_files)

        if data.get('_evidence_ids'):
            self._evidence_ids = data['_evidence_ids']

        if data.get('_relation_uploaded_files'):
            self.relation_uploaded_files = [
                f for f in data['_relation_uploaded_files']
                if os.path.exists(f.get("path", "")) or f.get("evidence_id")
            ]
            self._refresh_relation_thumbnails()

        if data.get('_relation_id'):
            self._api_relation_id = data['_relation_id']

        # Fetch evidence count from server for logging
        if self._survey_id:
            try:
                evidences = self._api_service.get_survey_evidences(self._survey_id)
                person_id = data.get('person_id')
                id_count = sum(1 for e in evidences
                               if e.get('personId') == person_id
                               and not e.get('personPropertyRelationId'))
                rel_count = sum(1 for e in evidences
                                if e.get('personPropertyRelationId'))
                if id_count > 0 or rel_count > 0:
                    logger.info(f"Server evidences: {id_count} identification + {rel_count} tenure")
                self._server_evidences = evidences
            except Exception as e:
                logger.warning(f"Could not fetch evidences from server: {e}")

    def get_person_data(self) -> Dict[str, Any]:
        """Get all person data from all 3 tabs."""
        return {
            'person_id': self.person_data.get('person_id') if self.person_data else str(uuid.uuid4()),
            # Tab 1
            'first_name': self.first_name.text().strip(),
            'father_name': self.father_name.text().strip(),
            'mother_name': self.mother_name.text().strip(),
            'last_name': self.last_name.text().strip(),
            'national_id': self.national_id.text().strip() or None,
            'gender': self._get_gender(),
            'nationality': self.nationality.currentData(),
            'birth_date': self._build_birth_date_iso(),
            # Tab 2
            'person_role': self.person_role.currentData(),
            'relationship_type': self.person_role.currentData(),  # backward compat
            'phone': self._format_phone(self.phone.text().strip()),
            'email': self.email.text().strip() or None,
            'landline': ("0" + self.landline_digits.text().strip()) if self.landline_digits.text().strip() else None,
            'is_contact_person': False,
            # Tab 3
            'relation_data': {
                'rel_type': self.rel_type_combo.currentData(),
                'start_date': self._build_start_date_iso(),
                'ownership_share': int(self.ownership_share.text() or 0),
                'evidence_type': self.evidence_type.currentData() if self.evidence_type.currentIndex() > 0 else None,
                'evidence_desc': self.evidence_desc.text().strip() or None,
                'notes': self.notes.toPlainText().strip() or None,
                'has_documents': bool(self.relation_uploaded_files),
            },
            # Document files (internal, for same-session persistence)
            '_uploaded_files': list(self.uploaded_files),
            '_evidence_ids': dict(self._evidence_ids),
            '_relation_uploaded_files': [dict(f) for f in self.relation_uploaded_files],
            '_relation_id': self._api_relation_id or (
                self.person_data.get('_relation_id') if self.person_data else None
            ),
        }

    def get_api_person_id(self) -> Optional[str]:
        """Return the API-generated person ID after creation, or None."""
        return self._api_person_id

    def get_api_relation_id(self) -> Optional[str]:
        """Return the API-generated relation ID after linking, or None."""
        return self._api_relation_id

    def get_relation_uploaded_files(self) -> List[Dict]:
        """Return uploaded relation/tenure evidence files (with evidence_id if uploaded)."""
        return list(self.relation_uploaded_files)

    def _save_person(self):
        """Validate required fields + format checks, then save."""
        has_error = False
        # Required: first_name, last_name
        if not self.first_name.text().strip():
            self._set_field_error(self.first_name, self._first_name_error, tr("wizard.person_dialog.enter_first_name"))
            has_error = True
        if not self.last_name.text().strip():
            self._set_field_error(self.last_name, self._last_name_error, tr("wizard.person_dialog.enter_last_name"))
            has_error = True
        nid_valid, nid_error = self._validate_national_id()
        if not nid_valid:
            self._set_field_error(self.national_id, self._nid_error, tr(nid_error))
            self.tab_widget.setCurrentIndex(0)
            has_error = True
        if not self._validate_mobile(self.phone.text().strip()):
            self._set_field_error(self.phone, self._mobile_error, tr("wizard.person_dialog.invalid_mobile"))
            self.tab_widget.setCurrentIndex(1)
            has_error = True
        if not self._validate_landline(self.landline_digits.text().strip()):
            self._set_field_error(self.landline_digits, self._landline_error, tr("wizard.person_dialog.invalid_landline"))
            self.tab_widget.setCurrentIndex(1)
            has_error = True
        if has_error:
            return
        self.accept()

    # API Integration

    def _on_final_save(self):
        """Handle final save (from Tab 3) - validate, create person via API, link to unit, accept."""
        import re
        from ui.error_handler import ErrorHandler

        has_error = False
        # Required: first_name, last_name, father_name, mother_name
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        father = self.father_name.text().strip()
        mother = self.mother_name.text().strip()
        name_pattern = re.compile(r'^[\u0600-\u06FFa-zA-Z\s.\-\']+$')
        if not first:
            self._set_field_error(self.first_name, self._first_name_error, tr("wizard.person_dialog.enter_first_name"))
            self.tab_widget.setCurrentIndex(0)
            has_error = True
        elif not name_pattern.match(first):
            self._set_field_error(self.first_name, self._first_name_error, tr("wizard.person_dialog.invalid_first_name"))
            self.tab_widget.setCurrentIndex(0)
            has_error = True
        if not last:
            self._set_field_error(self.last_name, self._last_name_error, tr("wizard.person_dialog.enter_last_name"))
            self.tab_widget.setCurrentIndex(0)
            has_error = True
        elif not name_pattern.match(last):
            self._set_field_error(self.last_name, self._last_name_error, tr("wizard.person_dialog.invalid_last_name"))
            self.tab_widget.setCurrentIndex(0)
            has_error = True
        if not father:
            self._set_field_error(self.father_name, self._father_name_error, tr("wizard.person_dialog.father_name_required"))
            self.tab_widget.setCurrentIndex(0)
            has_error = True
        if not mother:
            if not has_error:
                self.tab_widget.setCurrentIndex(0)
            has_error = True
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("wizard.person_dialog.mother_name_required"), Toast.ERROR)

        nid_valid, nid_error = self._validate_national_id()
        if not nid_valid:
            self._set_field_error(self.national_id, self._nid_error, tr(nid_error))
            self.tab_widget.setCurrentIndex(0)
            has_error = True

        if has_error:
            return

        # Optional format: phone, landline, email (only validate if filled)
        if not self._validate_mobile(self.phone.text().strip()):
            self._set_field_error(self.phone, self._mobile_error, tr("wizard.person_dialog.invalid_mobile"))
            if not has_error:
                self.tab_widget.setCurrentIndex(1)
            has_error = True
        if not self._validate_landline(self.landline_digits.text().strip()):
            self._set_field_error(self.landline_digits, self._landline_error, tr("wizard.person_dialog.invalid_landline"))
            if not has_error:
                self.tab_widget.setCurrentIndex(1)
            has_error = True
        email_text = self.email.text().strip()
        if email_text and not re.match(r'^[a-zA-Z0-9@._\-+]+$', email_text):
            self._set_field_error(self.email, self._email_error, tr("wizard.person_dialog.invalid_email_chars"))
            if not has_error:
                self.tab_widget.setCurrentIndex(1)
            has_error = True
        elif email_text and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email_text):
            self._set_field_error(self.email, self._email_error, tr("wizard.person_dialog.invalid_email"))
            if not has_error:
                self.tab_widget.setCurrentIndex(1)
            has_error = True

        # Ownership share: required when claim type is Owner (1)
        ownership_text = self.ownership_share.text().strip()
        is_owner = self.rel_type_combo.currentData() == 1
        if is_owner and not ownership_text:
            self._set_field_error(self.ownership_share, self._ownership_error, tr("wizard.person_dialog.ownership_share_required"))
            if not has_error:
                self.tab_widget.setCurrentIndex(2)
            has_error = True
        elif ownership_text:
            try:
                ownership_val = int(ownership_text)
                if ownership_val < 0 or ownership_val > 2400:
                    self._set_field_error(self.ownership_share, self._ownership_error, tr("wizard.person_dialog.invalid_ownership_share"))
                    if not has_error:
                        self.tab_widget.setCurrentIndex(2)
                    has_error = True
            except ValueError:
                pass

        # Documents: required for Owner (rel_type=1)
        if is_owner:
            if not self.relation_uploaded_files:
                from ui.error_handler import ErrorHandler as _EH
                _EH.show_error(
                    self,
                    tr("wizard.person_dialog.ownership_docs_required"),
                    tr("common.error"))
                if not has_error:
                    self.tab_widget.setCurrentIndex(2)
                has_error = True

        if has_error:
            return

        self._spinner.show_loading(tr("component.loading.default"))
        try:
            self._on_final_save_api()
        finally:
            self._spinner.hide_loading()

    def _on_final_save_api(self):
        """Execute the API calls for final save (called after validation passes)."""
        from ui.error_handler import ErrorHandler

        if self._existing_person_mode:
            self._refresh_token()
            person_id = (self.person_data or {}).get('person_id', '')
            if not person_id:
                from ui.error_handler import ErrorHandler
                ErrorHandler.show_error(self, tr("wizard.person_dialog.person_id_missing"), tr("common.error"))
                return
            self._api_person_id = person_id
            person_data = self.get_person_data()
            # Only link to unit if person has a relation type (claim)
            # Otherwise person is just a household member
            relation_data = person_data.get('relation_data', {})
            rel_type = relation_data.get('rel_type') or person_data.get('relationship_type')

            link_success = True
            if rel_type and self._survey_id and self._unit_id:
                relation_data['person_id'] = person_id
                relation_data['rel_type'] = rel_type
                relation_data['is_contact'] = True
                try:
                    relation_response = self._api_service.link_person_to_unit(
                        self._survey_id, self._unit_id, relation_data
                    )
                    relation_id = (
                        relation_response.get("id") or relation_response.get("relationId") or
                        relation_response.get("Id") or relation_response.get("RelationId") or
                        relation_response.get("personPropertyRelationId") or ""
                    )
                    if relation_id:
                        self._api_relation_id = relation_id
                    new_tenure_files = [
                        f for f in self.relation_uploaded_files
                        if not f.get("evidence_id") and not f.get("_selected_existing")
                    ]
                    if relation_id and new_tenure_files:
                        saved = self.relation_uploaded_files
                        self.relation_uploaded_files = new_tenure_files
                        self._upload_tenure_files(relation_id)
                        self.relation_uploaded_files = saved

                    # Link existing selected documents to this relation
                    if relation_id:
                        for entry in self.relation_uploaded_files:
                            if not entry.get('_selected_existing') or not entry.get('evidence_id'):
                                continue
                            try:
                                self._api_service.link_evidence_to_relation(
                                    self._survey_id, entry['evidence_id'], relation_id
                                )
                                logger.info(f"Existing evidence {entry['evidence_id']} linked to relation {relation_id}")
                            except Exception as e:
                                logger.error(f"Failed to link existing evidence: {e}")
                                Toast.show_toast(
                                    self,
                                    tr("wizard.person_dialog.link_existing_doc_failed"),
                                    Toast.ERROR
                                )

                except Exception as e:
                    link_success = False
                    logger.error(f"Failed to link existing person to unit: {e}")
                    from ui.error_handler import ErrorHandler
                    ErrorHandler.show_error(
                        self, tr("wizard.person_dialog.link_failed", error_msg=map_exception(e)), tr("common.error")
                    )
            elif not rel_type:
                logger.info(f"No relation type set for person {person_id}, added as household member only")
            else:
                logger.warning(f"Skipping relation link: survey_id={self._survey_id}, unit_id={self._unit_id}")
            if not link_success:
                from ui.error_handler import ErrorHandler
                ErrorHandler.show_warning(
                    self, tr("wizard.person_dialog.link_failed_person_saved"), tr("common.warning")
                )
                return
            self.accept()
            return

        if not self.editing_mode:
            self._refresh_token()
            person_data = self.get_person_data()
            logger.info(f"Creating person via API: {person_data.get('first_name')} {person_data.get('last_name')}")

            # Step 1: Create person in household
            try:
                response = self._api_service.create_person_in_household(
                    person_data, self._survey_id, self._household_id
                )

                logger.info("Person created successfully via API")
                self._created_person_data = response

                person_id = (
                    response.get("id") or response.get("personId") or
                    response.get("Id") or response.get("PersonId") or ""
                )

                if not person_id:
                    logger.error(f"Could not find person ID in response. Keys: {list(response.keys())}")
                    ErrorHandler.show_error(self, tr("wizard.person_dialog.created_no_id"), tr("common.error"))
                    return

                self._api_person_id = person_id

            except Exception as e:
                from services.exceptions import ApiException
                if isinstance(e, ApiException) and e.status_code == 409:
                    from services.error_mapper import build_duplicate_person_message
                    ErrorHandler.show_warning(self, build_duplicate_person_message(e.response_data), tr("common.warning"))
                    return
                logger.error(f"Failed to create person via API: {e}")
                ErrorHandler.show_error(
                    self, tr("wizard.person_dialog.create_failed", error_msg=map_exception(e)), tr("common.error")
                )
                return

            # Step 1.5: Upload identification files
            if self.uploaded_files and self._survey_id and person_id:
                self._upload_identification_files(person_id)

            # Step 2: Link person to property unit only if relation type is set
            # Persons without rel_type are household members only
            link_success = True
            relation_data = person_data.get('relation_data', {})
            rel_type = relation_data.get('rel_type') or person_data.get('relationship_type')

            if rel_type and self._survey_id and self._unit_id and person_id:
                relation_data['person_id'] = person_id
                relation_data['rel_type'] = rel_type

                try:
                    relation_response = self._api_service.link_person_to_unit(
                        self._survey_id, self._unit_id, relation_data
                    )

                    logger.info(f"Person {person_id} linked to unit {self._unit_id}")

                    relation_id = (
                        relation_response.get("id") or relation_response.get("relationId") or
                        relation_response.get("Id") or relation_response.get("RelationId") or
                        relation_response.get("personPropertyRelationId") or
                        relation_response.get("PersonPropertyRelationId") or ""
                    )

                    if relation_id:
                        self._api_relation_id = relation_id

                    if relation_id and self.relation_uploaded_files:
                        self._upload_tenure_files(relation_id)

                except Exception as e:
                    link_success = False
                    logger.error(f"Failed to link person to unit: {e}")
                    ErrorHandler.show_error(
                        self, tr("wizard.person_dialog.link_failed", error_msg=map_exception(e)), tr("common.error")
                    )
            elif not rel_type:
                logger.info(f"No relation type for person {person_id}, added as household member only")
            else:
                logger.warning(f"Skipping relation link: survey_id={self._survey_id}, unit_id={self._unit_id}, person_id={person_id}")

            if not link_success:
                ErrorHandler.show_warning(
                    self,
                    tr("wizard.person_dialog.link_failed_person_saved"),
                    tr("common.warning")
                )

        # Handle evidence files in edit mode: replace via PUT, or upload/delete as needed
        if self.editing_mode:
            self._refresh_token()
            import os
            person_id = self.person_data.get('person_id')

            # Identification files: new files not yet on server
            new_id_files = [f for f in self.uploaded_files
                            if os.path.normpath(f) not in self._evidence_ids]

            if self._survey_id and person_id:
                # Replace: pair new files with pending replacement IDs (PUT)
                for file_path in list(new_id_files):
                    if not self._pending_id_replacements:
                        break
                    old_evidence_id = self._pending_id_replacements.pop(0)
                    try:
                        doc_type = self.id_doc_type_combo.currentData() if hasattr(self, 'id_doc_type_combo') else None
                        response = self._api_service.update_identification_document(
                            self._survey_id, old_evidence_id, person_id, file_path=file_path,
                            document_type=doc_type)
                        new_eid = (response.get("id") or response.get("evidenceId")
                                   or response.get("Id") or old_evidence_id)
                        self._evidence_ids[os.path.normpath(file_path)] = new_eid
                        new_id_files.remove(file_path)
                        logger.info(f"ID evidence replaced: {old_evidence_id} -> {new_eid}")
                    except Exception as e:
                        logger.error(f"Failed to replace ID evidence {old_evidence_id}: {e}")
                        self._pending_id_replacements.insert(0, old_evidence_id)

                # Upload remaining new files that had no replacement target (POST)
                if new_id_files:
                    saved = self.uploaded_files
                    self.uploaded_files = new_id_files
                    self._upload_identification_files(person_id)
                    self.uploaded_files = saved

                # Delete leftover pending IDs that were not replaced
                for old_id in self._pending_id_replacements:
                    try:
                        self._api_service.delete_evidence(self._survey_id, old_id)
                        logger.info(f"Orphaned ID evidence deleted: {old_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete orphaned ID evidence {old_id}: {e}")
                self._pending_id_replacements.clear()

            # Tenure files: new files without evidence_id (exclude existing selected)
            relation_id = self._api_relation_id
            new_rel_files = [f for f in self.relation_uploaded_files
                             if not f.get("evidence_id") and not f.get("_selected_existing")]

            if self._survey_id and relation_id:
                # Replace: pair new tenure files with pending replacement IDs (PUT)
                for file_entry in list(new_rel_files):
                    if not self._pending_rel_replacements:
                        break
                    old_evidence_id = self._pending_rel_replacements.pop(0)
                    try:
                        response = self._api_service.update_tenure_evidence(
                            self._survey_id, old_evidence_id, relation_id,
                            file_path=file_entry["path"],
                            issue_date=file_entry.get("issue_date", ""))
                        new_eid = (response.get("id") or response.get("evidenceId")
                                   or response.get("Id") or old_evidence_id)
                        file_entry["evidence_id"] = new_eid
                        new_rel_files.remove(file_entry)
                        logger.info(f"Tenure evidence replaced: {old_evidence_id} -> {new_eid}")
                    except Exception as e:
                        logger.error(f"Failed to replace tenure evidence {old_evidence_id}: {e}")
                        self._pending_rel_replacements.insert(0, old_evidence_id)

                # Upload remaining new tenure files (POST)
                if new_rel_files:
                    saved = self.relation_uploaded_files
                    self.relation_uploaded_files = new_rel_files
                    self._upload_tenure_files(relation_id)
                    self.relation_uploaded_files = saved

                # Link newly selected existing documents
                for entry in self.relation_uploaded_files:
                    if entry.get('_selected_existing') and entry.get('evidence_id'):
                        try:
                            self._api_service.link_evidence_to_relation(
                                self._survey_id, entry['evidence_id'], relation_id
                            )
                            logger.info(f"Existing evidence {entry['evidence_id']} linked to relation {relation_id}")
                        except Exception as e:
                            logger.error(f"Failed to link existing evidence: {e}")
                            Toast.show_toast(
                                self,
                                tr("wizard.person_dialog.link_existing_doc_failed"),
                                Toast.ERROR
                            )

                # Delete leftover pending tenure IDs
                for old_id in self._pending_rel_replacements:
                    try:
                        self._api_service.delete_evidence(self._survey_id, old_id)
                        logger.info(f"Orphaned tenure evidence deleted: {old_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete orphaned tenure evidence {old_id}: {e}")
                self._pending_rel_replacements.clear()

        self.accept()

    def _upload_identification_files(self, person_id: str):
        """Upload identification files for the created person."""
        import os
        if not self.uploaded_files:
            return

        from services.exceptions import ApiException

        for file_path in self.uploaded_files:
            try:
                doc_type = self.id_doc_type_combo.currentData() if hasattr(self, 'id_doc_type_combo') else None
                response = self._api_service.upload_identification_document(
                    self._survey_id, person_id, file_path,
                    document_type=doc_type,
                )
                evidence_id = (
                    response.get("id") or response.get("evidenceId") or
                    response.get("Id") or response.get("EvidenceId") or ""
                )
                if evidence_id:
                    self._evidence_ids[os.path.normpath(file_path)] = evidence_id
                logger.info(f"Identification uploaded: {file_path} (evidence_id={evidence_id})")
            except Exception as e:
                logger.error(f"Failed to upload identification file {file_path}: {e}")
                Toast.show_toast(self, map_exception(e), Toast.ERROR)

    def _upload_tenure_files(self, relation_id: str):
        """Upload new tenure files and link existing selected documents."""
        if not self.relation_uploaded_files:
            return

        from services.error_mapper import map_exception as _map_exc
        from services.exceptions import ApiException

        success_count = 0
        fail_count = 0

        # Upload new files
        for file_entry in self.relation_uploaded_files:
            if file_entry.get('_selected_existing'):
                continue
            file_path = file_entry.get("path", "")
            if not file_path:
                continue
            issue_date = file_entry.get("issue_date", "")
            file_hash = file_entry.get("hash", "")

            try:
                response = self._api_service.upload_relation_document(
                    survey_id=self._survey_id,
                    relation_id=relation_id,
                    file_path=file_path,
                    issue_date=issue_date,
                    file_hash=file_hash
                )
                evidence_id = (
                    response.get("id") or response.get("evidenceId") or
                    response.get("Id") or response.get("EvidenceId") or ""
                )
                if evidence_id:
                    file_entry["evidence_id"] = evidence_id
                success_count += 1
            except ApiException as e:
                if e.status_code == 409:
                    logger.info(f"Document already exists (duplicate hash): {file_path}")
                    success_count += 1
                else:
                    fail_count += 1
                    logger.error(f"Failed to upload {file_path}: {_map_exc(e)}")
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to upload {file_path}: {e}")

        # Link existing selected documents to this relation
        for file_entry in self.relation_uploaded_files:
            if not file_entry.get('_selected_existing'):
                continue
            ev_id = file_entry.get('evidence_id')
            if not ev_id:
                continue
            try:
                self._api_service.link_evidence_to_relation(
                    self._survey_id, ev_id, relation_id
                )
                success_count += 1
                logger.info(f"Existing evidence {ev_id} linked to relation {relation_id}")
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to link evidence {ev_id}: {e}")

        if fail_count > 0:
            logger.warning(f"Document upload: {success_count} succeeded, {fail_count} failed")
            Toast.show_toast(
                self,
                tr("wizard.person_dialog.upload_partial", success=success_count, failed=fail_count),
                Toast.WARNING
            )
        elif success_count > 0:
            logger.info(f"All {success_count} document(s) processed successfully")
