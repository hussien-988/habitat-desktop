# -*- coding: utf-8 -*-
"""
Duplicates Page — التكرارات
Conflict resolution queue powered by Backend Conflicts API.
Implements UC-007: Resolve Duplicate Properties
Implements UC-008: Resolve Person Duplicates

Features:
- Summary dashboard with animated count cards
- Conflict queue with filters (type, status, priority)
- Paginated conflict list from API
- Resolution actions: merge, keep separate, escalate
- Side-by-side comparison navigation
- Shimmer loading effects
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QRadioButton, QButtonGroup, QAbstractItemView,
    QSizePolicy, QTextEdit, QApplication, QComboBox,
    QScrollArea, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QThread, pyqtSignal as Signal,
    QTimer, QPropertyAnimation, QEasingCurve, QRect
)
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath

from repositories.database import Database
from services.duplicate_service import DuplicateService
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.design_system import Colors, PageDimensions
from ui.components.toast import Toast
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)

# Status display config
_STATUS_CONFIG = {
    "Pending": {"label": "معلق", "color": "#F59E0B", "bg": "#FEF3C7"},
    "PendingReview": {"label": "بانتظار المراجعة", "color": "#F59E0B", "bg": "#FEF3C7"},
    "InReview": {"label": "قيد المراجعة", "color": "#3B82F6", "bg": "#DBEAFE"},
    "Resolved": {"label": "تم الحل", "color": "#10B981", "bg": "#D1FAE5"},
    "Escalated": {"label": "مصعّد", "color": "#EF4444", "bg": "#FEE2E2"},
    "AutoResolved": {"label": "حل تلقائي", "color": "#8B5CF6", "bg": "#EDE9FE"},
}

_PRIORITY_CONFIG = {
    "Critical": {"label": "حرج", "color": "#DC2626", "bg": "#FEE2E2"},
    "High": {"label": "عالي", "color": "#EA580C", "bg": "#FFEDD5"},
    "Medium": {"label": "متوسط", "color": "#CA8A04", "bg": "#FEF9C3"},
    "Low": {"label": "منخفض", "color": "#16A34A", "bg": "#DCFCE7"},
}

_TYPE_CONFIG = {
    "PropertyDuplicate": {"label": "تكرار عقاري", "icon": "🏠"},
    "PersonDuplicate": {"label": "تكرار أشخاص", "icon": "👤"},
}

# Case-insensitive lookup indexes
_STATUS_LOOKUP = {k.lower(): v for k, v in _STATUS_CONFIG.items()}
_PRIORITY_LOOKUP = {k.lower(): v for k, v in _PRIORITY_CONFIG.items()}
_TYPE_LOOKUP = {k.lower(): v for k, v in _TYPE_CONFIG.items()}

RADIO_STYLE = f"""
    QRadioButton {{
        background: transparent;
        border: none;
        spacing: 0px;
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 2px solid #C4CDD5;
        background: {Colors.BACKGROUND};
    }}
    QRadioButton::indicator:hover {{
        border-color: {Colors.PRIMARY_BLUE};
    }}
    QRadioButton::indicator:checked {{
        width: 16px;
        height: 16px;
        border-radius: 8px;
        border: 4px solid {Colors.PRIMARY_BLUE};
        background: {Colors.PRIMARY_BLUE};
    }}
"""


class _ShimmerWidget(QWidget):
    """Animated shimmer placeholder for loading states."""

    def __init__(self, width=200, height=20, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(30)

    def _animate(self):
        self._offset = (self._offset + 4) % (self.width() * 2)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 6, 6)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor("#F3F4F6"))
        grad = QLinearGradient(self._offset - self.width(), 0, self._offset, 0)
        grad.setColorAt(0.0, QColor(243, 244, 246, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 180))
        grad.setColorAt(1.0, QColor(243, 244, 246, 0))
        painter.fillRect(self.rect(), grad)
        painter.end()

    def stop(self):
        self._timer.stop()


class _GlowCard(QFrame):
    """Summary card with subtle glow effect on hover. Clickable for filtering."""

    clicked = Signal()

    def __init__(self, title: str, count: int, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._active = False
        self._setup(title, count, color)

    def _setup(self, title: str, count: int, color: str):
        self.setFixedHeight(90)
        self.setMinimumWidth(160)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 white, stop:1 #FAFBFC);
                border-radius: 14px;
                border: 1px solid {color}33;
            }}
            QFrame:hover {{
                border: 1.5px solid {color}88;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 white, stop:1 {color}0D);
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow_color = QColor(color)
        shadow_color.setAlpha(30)
        shadow.setColor(shadow_color)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.count_label = QLabel(str(count))
        self.count_label.setFont(create_font(size=22, weight=FontManager.WEIGHT_BOLD))
        self.count_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        layout.addWidget(self.count_label)

        self.title_label = QLabel(title)
        self.title_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self.title_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        layout.addWidget(self.title_label)

    def update_count(self, count: int):
        self.count_label.setText(str(count))

    def set_active(self, active: bool):
        self._active = active
        color = self._color
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background: {color}15;
                    border-radius: 14px;
                    border: 2px solid {color};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 white, stop:1 #FAFBFC);
                    border-radius: 14px;
                    border: 1px solid {color}33;
                }}
                QFrame:hover {{
                    border: 1.5px solid {color}88;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 white, stop:1 {color}0D);
                }}
            """)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


class _ConflictWorker(QThread):
    """Background worker for loading conflicts from API."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, service: DuplicateService, page=1, page_size=20, filters=None):
        super().__init__()
        self.service = service
        self.page = page
        self.page_size = page_size
        self.filters = filters or {}

    def run(self):
        try:
            result = self.service.get_conflicts(
                page=self.page,
                page_size=self.page_size,
                conflict_type=self.filters.get("conflict_type"),
                status=self.filters.get("status"),
                priority=self.filters.get("priority"),
                is_escalated=self.filters.get("is_escalated"),
            )
            summary = self.service.get_conflicts_summary()
            self.finished.emit({"conflicts": result, "summary": summary})
        except Exception as e:
            self.error.emit(str(e))


class _ResolutionWorker(QThread):
    """Background worker for executing resolution actions."""
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, service: DuplicateService, action: str,
                 conflict_id: str, justification: str, master_id: str = ""):
        super().__init__()
        self.service = service
        self.action = action
        self.conflict_id = conflict_id
        self.justification = justification
        self.master_id = master_id

    def run(self):
        try:
            if self.action == "merge":
                result = self.service.merge_conflict(
                    self.conflict_id, self.master_id, self.justification)
            elif self.action == "keep_separate":
                result = self.service.keep_separate(
                    self.conflict_id, self.justification)
            else:
                result = False
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DuplicatesPage(QWidget):
    """Duplicates/Conflicts resolution page with API-driven queue."""

    view_comparison_requested = pyqtSignal(object)
    return_to_import = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.duplicate_service = DuplicateService(db)
        self._worker = None
        self._user_id = None
        self._conflicts = []
        self._current_page = 1
        self._total_pages = 1
        self._page_size = 11
        self._selected_conflict_idx = -1
        self._detail_data = None
        self._exclude_resolved = False
        self._setup_ui()

    def set_user_id(self, user_id: str):
        self._user_id = user_id

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        main_layout.setSpacing(16)

        # Header
        header = self._build_header()
        main_layout.addLayout(header)

        # Return-to-import banner (hidden by default)
        self._import_banner = self._build_import_banner()
        main_layout.addWidget(self._import_banner)
        self._import_banner.setVisible(False)

        # Summary cards row
        self._summary_container = self._build_summary_cards()
        main_layout.addWidget(self._summary_container)

        # Filters row
        self._filters_container = self._build_filters()
        main_layout.addWidget(self._filters_container)

        # Shimmer loading placeholders
        self._shimmer_container = self._build_shimmer()
        main_layout.addWidget(self._shimmer_container)
        self._shimmer_container.setVisible(False)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(scroll_content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        scroll.setWidget(scroll_content)

        # Conflict list + detail panel
        self._conflict_list_card = self._build_conflict_list()
        self._content_layout.addWidget(self._conflict_list_card)

        # Resolution section
        self._resolution_card = self._build_resolution_section()
        self._content_layout.addWidget(self._resolution_card)
        self._resolution_card.setVisible(False)

        self._content_layout.addStretch()

        main_layout.addWidget(scroll, 1)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    # Header
    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel("التكرارات والتعارضات")
        title.setFont(create_font(size=FontManager.SIZE_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        self._refresh_btn = QPushButton("تحديث")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        self._refresh_btn.setFixedSize(90, 42)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #F4F6F8;
                color: {Colors.PRIMARY_BLUE};
                border: 1.5px solid {Colors.PRIMARY_BLUE}44;
                border-radius: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.PRIMARY_BLUE}11;
                border-color: {Colors.PRIMARY_BLUE};
            }}
        """)
        self._refresh_btn.clicked.connect(lambda: self.refresh())

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._refresh_btn)

        return header

    # Import Banner

    def _build_import_banner(self) -> QFrame:
        banner = QFrame()
        banner.setFixedHeight(48)
        banner.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.PRIMARY_BLUE}15;
                border: 1px solid {Colors.PRIMARY_BLUE}44;
                border-radius: 10px;
            }}
        """)

        layout = QHBoxLayout(banner)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        icon_lbl = QLabel("\u2190")
        icon_lbl.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        icon_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        msg_lbl = QLabel("تم الانتقال من صفحة الاستيراد — قم بحل التكرارات ثم عُد لمتابعة الاستيراد")
        msg_lbl.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        msg_lbl.setStyleSheet(f"color: {Colors.PRIMARY_BLUE}; background: transparent; border: none;")
        layout.addWidget(msg_lbl, 1)

        btn_return = QPushButton("العودة للاستيراد")
        btn_return.setCursor(Qt.PointingHandCursor)
        btn_return.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        btn_return.setFixedSize(150, 36)
        btn_return.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: #1A56DB;
            }}
        """)
        btn_return.clicked.connect(self.return_to_import.emit)
        layout.addWidget(btn_return)

        return banner

    def set_return_to_import(self, enabled: bool):
        """Show or hide the return-to-import banner."""
        self._import_banner.setVisible(enabled)

    # Summary Cards
    def _build_summary_cards(self) -> QFrame:
        container = QFrame()
        container.setStyleSheet("QFrame { background: transparent; border: none; }")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._card_total = _GlowCard("إجمالي التعارضات", 0, Colors.PRIMARY_BLUE)
        self._card_property = _GlowCard("تعارضات المقاسم", 0, "#F59E0B")
        self._card_person = _GlowCard("تكرار الأشخاص", 0, "#8B5CF6")
        self._card_resolved = _GlowCard("تم الحل", 0, "#10B981")
        self._card_overdue = _GlowCard("متأخر", 0, "#DC2626")

        self._summary_cards = [self._card_total, self._card_property, self._card_person,
                               self._card_resolved, self._card_overdue]
        for card in self._summary_cards:
            layout.addWidget(card)

        # Connect cards to filter actions
        self._card_total.clicked.connect(lambda: self._filter_by_card("all"))
        self._card_property.clicked.connect(lambda: self._filter_by_card("PropertyDuplicate"))
        self._card_person.clicked.connect(lambda: self._filter_by_card("PersonDuplicate"))
        self._card_resolved.clicked.connect(lambda: self._filter_by_card("Resolved"))
        self._card_overdue.clicked.connect(lambda: self._filter_by_card("overdue"))

        return container

    def _build_filters(self) -> QFrame:
        container = QFrame()
        container.setStyleSheet("""
            QFrame { background: white; border-radius: 12px; border: 1px solid #E5E7EB; }
        """)
        container.setFixedHeight(56)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        form_style = StyleManager.form_input()

        filter_label = QLabel("تصفية:")
        filter_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        filter_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        layout.addWidget(filter_label)

        self._type_filter = QComboBox()
        self._type_filter.addItem("جميع الأنواع", "")
        self._type_filter.addItem("تعارضات المقاسم", "PropertyDuplicate")
        self._type_filter.addItem("تكرار الأشخاص", "PersonDuplicate")
        self._type_filter.setStyleSheet(form_style)
        self._type_filter.setMinimumWidth(130)
        self._type_filter.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._type_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._type_filter)

        self._status_filter = QComboBox()
        self._status_filter.addItem("جميع الحالات", "")
        self._status_filter.addItem("معلق", "Pending")
        self._status_filter.addItem("بانتظار المراجعة", "PendingReview")
        self._status_filter.addItem("قيد المراجعة", "InReview")
        self._status_filter.addItem("تم الحل", "Resolved")
        self._status_filter.addItem("حل تلقائي", "AutoResolved")
        self._status_filter.setStyleSheet(form_style)
        self._status_filter.setMinimumWidth(130)
        self._status_filter.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._status_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._status_filter)

        self._priority_filter = QComboBox()
        self._priority_filter.addItem("جميع الأولويات", "")
        self._priority_filter.addItem("حرج", "Critical")
        self._priority_filter.addItem("عالي", "High")
        self._priority_filter.addItem("متوسط", "Medium")
        self._priority_filter.addItem("منخفض", "Low")
        self._priority_filter.setStyleSheet(form_style)
        self._priority_filter.setMinimumWidth(130)
        self._priority_filter.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._priority_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._priority_filter)

        layout.addStretch()

        return container

    # Shimmer Loading
    def _build_shimmer(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        self._shimmer_widgets = []
        for _ in range(4):
            row = QFrame()
            row.setStyleSheet("QFrame { background: white; border-radius: 12px; border: none; }")
            row.setFixedHeight(72)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 12, 16, 12)
            row_layout.setSpacing(16)

            s1 = _ShimmerWidget(60, 16)
            s2 = _ShimmerWidget(200, 16)
            s3 = _ShimmerWidget(100, 16)
            s4 = _ShimmerWidget(80, 24)
            self._shimmer_widgets.extend([s1, s2, s3, s4])

            row_layout.addWidget(s1)
            row_layout.addWidget(s2)
            row_layout.addStretch()
            row_layout.addWidget(s3)
            row_layout.addWidget(s4)

            layout.addWidget(row)

        return container

    # Conflict List Table
    def _build_conflict_list(self) -> QFrame:
        card = QFrame()
        card.setObjectName("conflictListCard")
        card.setFixedHeight(708)
        card.setStyleSheet("""
            QFrame#conflictListCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 18))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(10, 10, 10, 0)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setRowCount(11)
        self._table.setHorizontalHeaderLabels([
            "رقم التعارض",
            "النوع",
            "السجل الأول",
            "السجل الثاني",
            "نسبة التطابق",
            "الأولوية",
            "الحالة",
            "التاريخ",
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = self._table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setFixedHeight(56)
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        v_header = self._table.verticalHeader()
        v_header.setDefaultSectionSize(52)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: none;
                outline: none;
                font-size: 10.5pt;
                color: #212B36;
            }}
            QTableWidget::item {{
                padding: 8px 15px;
                border-bottom: 1px solid #F0F0F0;
                color: #212B36;
                font-size: 10.5pt;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.PRIMARY_BLUE}15;
                color: #1F2937;
            }}
            QTableWidget::item:hover {{
                background-color: #FAFBFC;
            }}
            QHeaderView {{
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }}
            QHeaderView::section {{
                background-color: #F8F9FA;
                padding: 12px;
                border: none;
                color: #637381;
                font-weight: 600;
                font-size: 11pt;
                height: 56px;
            }}
            QHeaderView::section:hover {{
                background-color: #EBEEF2;
            }}
        """ + StyleManager.scrollbar())

        self._table.selectionModel().selectionChanged.connect(self._on_row_selected)

        card_layout.addWidget(self._table)

        # Empty state
        self._empty_label = QLabel("لا توجد تعارضات حالياً")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._empty_label.setStyleSheet("""
            color: #9CA3AF;
            background: transparent;
            padding: 60px 20px;
        """)
        self._empty_label.setVisible(False)
        card_layout.addWidget(self._empty_label)

        # Footer with pagination
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-top: 1px solid #E1E8ED;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)
        footer.setFixedHeight(58)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 10, 10, 10)

        nav_btn_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #E1E8ED;
                border-radius: 4px;
                color: #637381;
                font-size: 10pt;
                font-weight: 600;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #EBEEF2;
            }
            QPushButton:disabled {
                color: #C1C7CD;
            }
        """

        self._prev_btn = QPushButton("السابق")
        self._prev_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setFixedHeight(36)
        self._prev_btn.setStyleSheet(nav_btn_style)
        self._prev_btn.clicked.connect(lambda: self._go_to_page(self._current_page - 1))

        self._page_label = QLabel("1 / 1")
        self._page_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._page_label.setAlignment(Qt.AlignCenter)
        self._page_label.setStyleSheet("color: #637381; font-size: 10pt; background: transparent; border: none;")

        self._next_btn = QPushButton("التالي")
        self._next_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setFixedHeight(36)
        self._next_btn.setStyleSheet(nav_btn_style)
        self._next_btn.clicked.connect(lambda: self._go_to_page(self._current_page + 1))

        footer_layout.addWidget(self._prev_btn)
        footer_layout.addWidget(self._page_label)
        footer_layout.addWidget(self._next_btn)
        footer_layout.addStretch()

        self._count_label = QLabel("عرض 0 من 0")
        self._count_label.setStyleSheet("color: #637381; font-size: 10pt; background: transparent; border: none;")
        footer_layout.addWidget(self._count_label)

        card_layout.addWidget(footer)

        return card

    # Resolution Section
    def _build_resolution_section(self) -> QFrame:
        card = QFrame()
        card.setObjectName("resolutionCard")
        card.setStyleSheet("""
            QFrame#resolutionCard {
                background-color: white;
                border-radius: 14px;
                border: none;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(QColor(0, 0, 0, 15))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(20, 18, 20, 18)

        # Title row with conflict info
        title_row = QHBoxLayout()
        self._resolution_title = QLabel("إجراء الحل")
        self._resolution_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._resolution_title.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")

        self._conflict_info_label = QLabel("")
        self._conflict_info_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._conflict_info_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        self._view_details_btn = QPushButton("عرض التفاصيل")
        self._view_details_btn.setCursor(Qt.PointingHandCursor)
        self._view_details_btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._view_details_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.PRIMARY_BLUE};
                background: {Colors.PRIMARY_BLUE}0D;
                border: 1px solid {Colors.PRIMARY_BLUE}33;
                border-radius: 8px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background: {Colors.PRIMARY_BLUE}1A;
                border-color: {Colors.PRIMARY_BLUE}66;
            }}
        """)
        self._view_details_btn.clicked.connect(self._on_view_details)

        title_row.addWidget(self._resolution_title)
        title_row.addWidget(self._conflict_info_label)
        title_row.addStretch()
        title_row.addWidget(self._view_details_btn)
        card_layout.addLayout(title_row)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #F3F4F6;")
        card_layout.addWidget(sep)

        # Comparison preview
        self._comparison_frame = QFrame()
        self._comparison_frame.setStyleSheet("""
            QFrame { background: #F8FAFC; border-radius: 10px; border: 1px solid #E5E7EB; }
        """)
        comp_layout = QHBoxLayout(self._comparison_frame)
        comp_layout.setContentsMargins(16, 12, 16, 12)
        comp_layout.setSpacing(20)

        # Record A
        self._record_a_frame = self._build_record_preview("السجل الأول")
        comp_layout.addWidget(self._record_a_frame, 1)

        # VS divider
        vs_label = QLabel("VS")
        vs_label.setAlignment(Qt.AlignCenter)
        vs_label.setFixedWidth(50)
        vs_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_BOLD))
        vs_label.setStyleSheet(f"""
            color: {Colors.PRIMARY_BLUE};
            background: {Colors.PRIMARY_BLUE}15;
            border-radius: 25px;
            padding: 8px;
            border: none;
        """)
        comp_layout.addWidget(vs_label)

        # Record B
        self._record_b_frame = self._build_record_preview("السجل الثاني")
        comp_layout.addWidget(self._record_b_frame, 1)

        card_layout.addWidget(self._comparison_frame)

        # Resolution options
        self._resolution_group = QButtonGroup(self)
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        resolution_options = [
            ("دمج السجلات", "merge", Colors.PRIMARY_BLUE),
            ("إبقاء منفصل", "keep_separate", "#10B981"),
        ]

        for idx, (label, value, color) in enumerate(resolution_options):
            radio = QRadioButton(label)
            radio.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            radio.setStyleSheet(RADIO_STYLE + """
                QRadioButton { padding: 8px 14px; }
            """)
            radio.setProperty("resolution_type", value)
            self._resolution_group.addButton(radio, idx)
            options_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

        options_layout.addStretch()

        # Master record selector (shown for merge)
        self._master_label = QLabel("السجل الرئيسي:")
        self._master_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        self._master_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")

        self._master_combo = QComboBox()
        self._master_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid #E5E7EB;
                border-radius: 8px;
                padding: 4px 12px;
                background: #FAFBFC;
                color: #374151;
                min-width: 180px;
            }}
            QComboBox:hover {{ border-color: {Colors.PRIMARY_BLUE}88; }}
        """)
        self._master_combo.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))

        options_layout.addWidget(self._master_label)
        options_layout.addWidget(self._master_combo)

        card_layout.addLayout(options_layout)

        self._resolution_group.buttonClicked.connect(self._on_resolution_type_changed)

        # Justification
        just_label = QLabel("مبرر القرار (مطلوب)")
        just_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        just_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        card_layout.addWidget(just_label)

        self._justification_edit = QTextEdit()
        self._justification_edit.setPlaceholderText("أدخل سبب قرار الحل...")
        self._justification_edit.setFixedHeight(72)
        self._justification_edit.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._justification_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1.5px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px;
                background: #FAFBFC;
                color: #333;
            }}
            QTextEdit:focus {{
                border-color: {Colors.PRIMARY_BLUE};
                background: white;
            }}
        """)
        card_layout.addWidget(self._justification_edit)

        # Action button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._action_btn = QPushButton("تنفيذ القرار")
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._action_btn.setFixedSize(160, 44)
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {Colors.PRIMARY_BLUE}, stop:1 #2E7BC8);
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2E7BC8, stop:1 #2568A8);
            }}
            QPushButton:pressed {{
                background-color: #2568A8;
            }}
            QPushButton:disabled {{
                background-color: #B0BEC5;
            }}
        """)
        self._action_btn.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self._action_btn)

        card_layout.addLayout(btn_layout)

        return card

    def _build_record_preview(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")
        layout.addWidget(title_lbl)

        id_lbl = QLabel("-")
        id_lbl.setObjectName("record_id")
        id_lbl.setFont(create_font(size=11, weight=FontManager.WEIGHT_BOLD))
        id_lbl.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent;")
        layout.addWidget(id_lbl)

        desc_lbl = QLabel("-")
        desc_lbl.setObjectName("record_desc")
        desc_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        desc_lbl.setStyleSheet(f"color: #6B7280; background: transparent;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        return frame

    # Data Loading
    def _get_active_filters(self) -> dict:
        filters = {}
        ct = self._type_filter.currentData()
        if ct:
            filters["conflict_type"] = ct
        st = self._status_filter.currentData()
        if st:
            filters["status"] = st
        pr = self._priority_filter.currentData()
        if pr:
            filters["priority"] = pr
        return filters

    def _load_conflicts(self):
        # Cancel previous worker if still running
        if self._worker and self._worker.isRunning():
            self._worker.finished.disconnect()
            self._worker.error.disconnect()
            self._worker.quit()
            self._worker.wait(500)

        self._shimmer_container.setVisible(True)
        self._conflict_list_card.setVisible(False)
        self._resolution_card.setVisible(False)

        self._worker = _ConflictWorker(
            self.duplicate_service,
            page=self._current_page,
            page_size=self._page_size,
            filters=self._get_active_filters(),
        )
        self._spinner.show_loading("جاري تحميل التعارضات...")
        self._worker.finished.connect(self._on_load_finished)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_load_finished(self, data: dict):
        self._spinner.hide_loading()
        # Stop shimmers
        for s in self._shimmer_widgets:
            s.stop()
        self._shimmer_container.setVisible(False)
        self._conflict_list_card.setVisible(True)

        # Update summary cards — show pending (unresolved) counts
        summary = data.get("summary", {})
        pending_total = summary.get("pendingReviewCount", summary.get("totalConflicts", 0))
        pending_property = summary.get("pendingPropertyDuplicates", summary.get("propertyDuplicateCount", 0))
        pending_person = summary.get("pendingPersonDuplicates", summary.get("personDuplicateCount", 0))
        self._card_total.update_count(pending_total)
        self._card_property.update_count(pending_property)
        self._card_person.update_count(pending_person)
        self._card_resolved.update_count(summary.get("resolvedCount", 0))
        self._card_overdue.update_count(summary.get("overdueCount", 0))

        # Update conflict list
        conflicts_data = data.get("conflicts", {})
        all_items = conflicts_data.get("items", [])
        self._total_pages = conflicts_data.get("totalPages", 1)
        total_count = conflicts_data.get("totalCount", 0)

        # Exclude resolved items when viewing from type cards
        if self._exclude_resolved:
            _resolved = {"resolved", "autoresolved"}
            self._conflicts = [
                c for c in all_items
                if c.get("status", "").lower() not in _resolved
            ]
        else:
            self._conflicts = all_items

        self._count_label.setText(f"عرض {len(self._conflicts)} من {total_count}")

        self._populate_table()
        self._update_pagination()

    def _on_load_error(self, error_msg: str):
        self._spinner.hide_loading()
        for s in self._shimmer_widgets:
            s.stop()
        self._shimmer_container.setVisible(False)
        self._conflict_list_card.setVisible(True)

        self._conflicts = []
        self._populate_table()
        Toast.show_toast(self, f"فشل تحميل التعارضات: {error_msg}", Toast.ERROR)
        logger.error(f"Conflict load error: {error_msg}")

    # Table Population
    def _populate_table(self):
        self._selected_conflict_idx = -1
        self._resolution_card.setVisible(False)

        # Clear all fixed rows
        for r in range(self._page_size):
            for c in range(self._table.columnCount()):
                self._table.setItem(r, c, QTableWidgetItem(""))
            self._table.setRowHeight(r, 52)

        if not self._conflicts:
            self._table.setVisible(False)
            self._empty_label.setVisible(True)
            return

        self._table.setVisible(True)
        self._empty_label.setVisible(False)

        for row_idx, conflict in enumerate(self._conflicts):
            # Conflict number
            num_item = QTableWidgetItem(conflict.get("conflictNumber", "-"))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
            self._table.setItem(row_idx, 0, num_item)

            # Type
            ctype = conflict.get("conflictType", "")
            type_cfg = _TYPE_LOOKUP.get(ctype.lower(), {"label": ctype, "icon": ""}) if ctype else {"label": "-", "icon": ""}
            type_item = QTableWidgetItem(f"{type_cfg['icon']} {type_cfg['label']}")
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            self._table.setItem(row_idx, 1, type_item)

            # First entity
            first_id = conflict.get("firstEntityIdentifier", conflict.get("firstEntityId", "-"))
            first_item = QTableWidgetItem(str(first_id))
            first_item.setTextAlignment(Qt.AlignCenter)
            first_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            self._table.setItem(row_idx, 2, first_item)

            # Second entity
            second_id = conflict.get("secondEntityIdentifier", conflict.get("secondEntityId", "-"))
            second_item = QTableWidgetItem(str(second_id))
            second_item.setTextAlignment(Qt.AlignCenter)
            second_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
            self._table.setItem(row_idx, 3, second_item)

            # Similarity score
            score = conflict.get("similarityScore", 0)
            score_pct = f"{score * 100:.0f}%" if isinstance(score, float) and score <= 1 else f"{score}%"
            score_item = QTableWidgetItem(score_pct)
            score_item.setTextAlignment(Qt.AlignCenter)
            score_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
            score_color = "#EF4444" if (score if isinstance(score, (int, float)) else 0) >= 0.9 else \
                          "#F59E0B" if (score if isinstance(score, (int, float)) else 0) >= 0.7 else "#6B7280"
            score_item.setForeground(QColor(score_color))
            self._table.setItem(row_idx, 4, score_item)

            # Priority
            priority = conflict.get("priority", "Medium")
            pri_cfg = _PRIORITY_LOOKUP.get(priority.lower(), {"label": priority, "color": "#6B7280"}) if priority else {"label": "-", "color": "#6B7280"}
            pri_item = QTableWidgetItem(pri_cfg["label"])
            pri_item.setTextAlignment(Qt.AlignCenter)
            pri_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            pri_item.setForeground(QColor(pri_cfg["color"]))
            self._table.setItem(row_idx, 5, pri_item)

            # Status
            status = conflict.get("status", "Pending")
            st_cfg = _STATUS_LOOKUP.get(status.lower(), {"label": status, "color": "#6B7280"}) if status else {"label": "-", "color": "#6B7280"}
            st_item = QTableWidgetItem(st_cfg["label"])
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            st_item.setForeground(QColor(st_cfg["color"]))
            self._table.setItem(row_idx, 6, st_item)

            # Date
            date_str = conflict.get("detectedDate", conflict.get("assignedDate", ""))
            if date_str and "T" in str(date_str):
                date_str = str(date_str).split("T")[0]
            date_item = QTableWidgetItem(str(date_str))
            date_item.setTextAlignment(Qt.AlignCenter)
            date_item.setFont(create_font(size=8, weight=FontManager.WEIGHT_REGULAR))
            date_item.setForeground(QColor("#9CA3AF"))
            self._table.setItem(row_idx, 7, date_item)

    # Selection & Resolution
    def _on_row_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._selected_conflict_idx = -1
            self._resolution_card.setVisible(False)
            return

        idx = rows[0].row()
        if idx >= len(self._conflicts):
            self._table.clearSelection()
            self._selected_conflict_idx = -1
            self._resolution_card.setVisible(False)
            return

        self._selected_conflict_idx = idx
        conflict = self._conflicts[self._selected_conflict_idx]

        # Show resolution card with animation
        self._resolution_card.setVisible(True)

        # Update conflict info
        cnum = conflict.get("conflictNumber", "")
        ctype = conflict.get("conflictType", "")
        type_label = _TYPE_LOOKUP.get(ctype.lower(), {"label": ctype}).get("label", ctype) if ctype else "-"
        self._conflict_info_label.setText(f"#{cnum} — {type_label}")

        # Update record previews
        first_id = conflict.get("firstEntityIdentifier", conflict.get("firstEntityId", "-"))
        second_id = conflict.get("secondEntityIdentifier", conflict.get("secondEntityId", "-"))

        a_id = self._record_a_frame.findChild(QLabel, "record_id")
        a_desc = self._record_a_frame.findChild(QLabel, "record_desc")
        b_id = self._record_b_frame.findChild(QLabel, "record_id")
        b_desc = self._record_b_frame.findChild(QLabel, "record_desc")

        if a_id:
            a_id.setText(str(first_id))
        if a_desc:
            a_desc.setText(f"معرف: {conflict.get('firstEntityId', '-')}")
        if b_id:
            b_id.setText(str(second_id))
        if b_desc:
            b_desc.setText(f"معرف: {conflict.get('secondEntityId', '-')}")

        # Update master record combo
        self._master_combo.clear()
        self._master_combo.addItem(f"السجل الأول: {first_id}", conflict.get("firstEntityId", ""))
        self._master_combo.addItem(f"السجل الثاني: {second_id}", conflict.get("secondEntityId", ""))

        # Reset justification
        self._justification_edit.clear()

        # Update resolution options visibility
        self._on_resolution_type_changed()

    def _on_resolution_type_changed(self):
        selected = self._resolution_group.checkedButton()
        if not selected:
            return
        res_type = selected.property("resolution_type")
        is_merge = res_type == "merge"
        self._master_label.setVisible(is_merge)
        self._master_combo.setVisible(is_merge)

    def _on_action_clicked(self):
        if self._selected_conflict_idx < 0 or self._selected_conflict_idx >= len(self._conflicts):
            Toast.show_toast(self, "يرجى اختيار تعارض من القائمة", Toast.WARNING)
            return

        justification = self._justification_edit.toPlainText().strip()
        if not justification:
            Toast.show_toast(self, "يرجى إدخال مبرر القرار", Toast.WARNING)
            return

        selected_radio = self._resolution_group.checkedButton()
        if not selected_radio:
            Toast.show_toast(self, "يرجى اختيار نوع الإجراء", Toast.WARNING)
            return

        resolution_type = selected_radio.property("resolution_type")
        conflict = self._conflicts[self._selected_conflict_idx]
        conflict_id = conflict.get("id", "")

        action_labels = {
            "merge": "دمج السجلات",
            "keep_separate": "إبقاء السجلات منفصلة",
        }
        action_label = action_labels.get(resolution_type, "تنفيذ الإجراء")

        from ui.components.dialogs.confirmation_dialog import ConfirmationDialog, DialogResult
        result = ConfirmationDialog.confirm(
            parent=self,
            title="تأكيد الإجراء",
            message=f"هل أنت متأكد من {action_label}؟\nلا يمكن التراجع عن هذا الإجراء."
        )
        if result != DialogResult.YES:
            return

        master_id = ""
        if resolution_type == "merge":
            master_id = self._master_combo.currentData()
            if not master_id:
                Toast.show_toast(self, "يرجى اختيار السجل الأساسي", Toast.WARNING)
                return

        self._action_btn.setEnabled(False)
        self._resolution_worker = _ResolutionWorker(
            self.duplicate_service, resolution_type,
            conflict_id, justification, master_id
        )
        self._resolution_worker.finished.connect(self._on_resolution_finished)
        self._resolution_worker.error.connect(self._on_resolution_error)
        self._resolution_worker.start()

    def _on_resolution_finished(self, success: bool):
        self._action_btn.setEnabled(True)
        if success:
            self._justification_edit.clear()
            Toast.show_toast(self, "تم تنفيذ الإجراء بنجاح", Toast.SUCCESS)
            self._load_conflicts()
        else:
            Toast.show_toast(self, "فشل تنفيذ الإجراء", Toast.ERROR)

    def _on_resolution_error(self, error_msg: str):
        self._action_btn.setEnabled(True)
        Toast.show_toast(self, f"فشل تنفيذ الإجراء: {error_msg}", Toast.ERROR)

    def _on_view_details(self):
        if self._selected_conflict_idx < 0:
            return
        conflict = self._conflicts[self._selected_conflict_idx]
        self.view_comparison_requested.emit(conflict)

    # Filter & Pagination
    def _filter_by_card(self, card_type: str):
        """Filter conflicts by clicking a summary card."""
        # Block signals to prevent multiple _on_filter_changed calls
        self._type_filter.blockSignals(True)
        self._status_filter.blockSignals(True)

        # Reset active state on all cards
        for card in self._summary_cards:
            card.set_active(False)

        # Track whether to exclude resolved items from display
        self._exclude_resolved = False

        if card_type == "all":
            self._type_filter.setCurrentIndex(0)
            self._status_filter.setCurrentIndex(0)
            self._exclude_resolved = True
            self._card_total.set_active(True)
        elif card_type == "PropertyDuplicate":
            self._type_filter.setCurrentIndex(self._type_filter.findData("PropertyDuplicate"))
            self._status_filter.setCurrentIndex(0)
            self._exclude_resolved = True
            self._card_property.set_active(True)
        elif card_type == "PersonDuplicate":
            self._type_filter.setCurrentIndex(self._type_filter.findData("PersonDuplicate"))
            self._status_filter.setCurrentIndex(0)
            self._exclude_resolved = True
            self._card_person.set_active(True)
        elif card_type == "Resolved":
            self._type_filter.setCurrentIndex(0)
            self._status_filter.setCurrentIndex(self._status_filter.findData("Resolved"))
            self._card_resolved.set_active(True)
        elif card_type == "overdue":
            self._type_filter.setCurrentIndex(0)
            self._status_filter.setCurrentIndex(0)
            self._card_overdue.set_active(True)

        # Unblock signals
        self._type_filter.blockSignals(False)
        self._status_filter.blockSignals(False)

        self._current_page = 1
        self._load_conflicts()

    def _on_filter_changed(self):
        # Reset card active states when user changes filter manually
        for card in self._summary_cards:
            card.set_active(False)
        self._exclude_resolved = False
        self._current_page = 1
        self._load_conflicts()

    def _go_to_page(self, page: int):
        if page < 1 or page > self._total_pages:
            return
        self._current_page = page
        self._load_conflicts()

    def _update_pagination(self):
        self._page_label.setText(f"{self._current_page} / {self._total_pages}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    # ─── Public API ──────────────────────────────────
    def refresh(self, data=None):
        logger.debug("Refreshing duplicates page")
        self._load_conflicts()

    def hideEvent(self, event):
        """Stop shimmer timers when page is hidden."""
        for s in self._shimmer_widgets:
            s.stop()
        super().hideEvent(event)

    def update_language(self, is_arabic: bool):
        pass
