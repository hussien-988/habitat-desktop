# -*- coding: utf-8 -*-
"""
Sync & Data Page — صفحة المزامنة والبيانات
Displays sync log history and field collector assignments.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QSizePolicy, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from ui.components.icon import Icon
from ui.design_system import Colors, PageDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger

logger = get_logger(__name__)


class SyncDataPage(QWidget):
    """Page displaying sync log history and field collector assignments."""

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._rows_container = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())
        self.setLayoutDirection(Qt.RightToLeft)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)

        # Header
        header = self._create_header()
        main_layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Sync card
        self._card = self._create_sync_card()
        scroll_layout.addWidget(self._card)

        # Assignments filter (above card)
        filter_section = self._create_assignments_filter()
        scroll_layout.addWidget(filter_section)

        # Assignments card (rows only)
        self._assignments_card = self._create_assignments_card()
        scroll_layout.addWidget(self._assignments_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("المزامنة والبيانات")
        title.setFont(create_font(
            size=FontManager.SIZE_TITLE,
            weight=QFont.Bold,
            letter_spacing=0
        ))
        title.setStyleSheet(StyleManager.label_title())
        layout.addWidget(title)

        breadcrumb_layout = QHBoxLayout()
        breadcrumb_layout.setSpacing(8)
        breadcrumb_layout.setContentsMargins(0, 0, 0, 0)

        subtitle_font = create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal,
            letter_spacing=0
        )
        style = f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;"

        part1 = QLabel("المطالبات المكتملة")
        part1.setFont(subtitle_font)
        part1.setStyleSheet(style)
        breadcrumb_layout.addWidget(part1)

        dot = QLabel("•")
        dot.setFont(subtitle_font)
        dot.setStyleSheet(style)
        breadcrumb_layout.addWidget(dot)

        part2 = QLabel("المزامنة والبيانات")
        part2.setFont(subtitle_font)
        part2.setStyleSheet(style)
        breadcrumb_layout.addWidget(part2)

        breadcrumb_layout.addStretch()
        layout.addLayout(breadcrumb_layout)

        return header

    def _create_sync_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("syncCard")
        card.setStyleSheet("""
            QFrame#syncCard {
                background-color: white;
                border-radius: 8px;
            }
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        self._rows_container = QVBoxLayout()
        self._rows_container.setSpacing(8)
        layout.addLayout(self._rows_container)

        self._empty_label = QLabel("لا توجد سجلات مزامنة")
        self._empty_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal
        ))
        self._empty_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setMinimumHeight(100)
        layout.addWidget(self._empty_label)

        return card

    # ------------------------------------------------------------------
    # Assignments filter (above card)
    # ------------------------------------------------------------------

    def _get_down_icon_path(self) -> str:
        """Get absolute path to down.png icon."""
        from pathlib import Path
        import sys

        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent.parent

        search_paths = [
            base_path / "assets" / "images" / "down.png",
            base_path / "assets" / "icons" / "down.png",
            base_path / "assets" / "down.png",
        ]
        for path in search_paths:
            if path.exists():
                return str(path).replace("\\", "/")
        return ""

    def _style_collector_combo(self, combo: QComboBox):
        """Apply professional styling to collector combo (same as field_work step1)."""
        combo.setFixedHeight(42)
        combo.setMinimumWidth(280)
        combo.setEditable(True)
        combo.lineEdit().setReadOnly(True)
        combo.lineEdit().setPlaceholderText("-- اختر باحث --")

        down_icon_path = self._get_down_icon_path()

        arrow_css = f"""
            QComboBox::down-arrow {{
                image: url({down_icon_path});
                width: 12px;
                height: 12px;
            }}
        """ if down_icon_path else f"""
            QComboBox::down-arrow {{
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #606266;
                width: 0;
                height: 0;
            }}
        """

        combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
                padding: 8px 14px;
                padding-left: 35px;
                background-color: {Colors.SEARCH_BAR_BG};
                color: #6c757d;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                subcontrol-position: right center;
            }}
            {arrow_css}
            QComboBox QAbstractItemView {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                background-color: white;
                selection-background-color: #EFF6FF;
                color: #6c757d;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                color: #6c757d;
            }}
            QScrollBar:vertical {{
                width: 0px;
            }}
            QScrollBar:horizontal {{
                height: 0px;
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 9pt;
                padding: 0px;
                color: #6c757d;
            }}
        """)

    def _create_assignments_filter(self) -> QWidget:
        """Create filter section above assignments card."""
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(section)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        # Title
        title = QLabel("تعيينات الباحثين الميدانيين")
        title.setFont(create_font(
            size=FontManager.SIZE_SUBHEADING,
            weight=FontManager.WEIGHT_SEMIBOLD
        ))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title)

        layout.addStretch()

        # Collector combo
        self._collector_combo = QComboBox()
        self._style_collector_combo(self._collector_combo)
        self._collector_combo.currentIndexChanged.connect(self._on_collector_changed)
        layout.addWidget(self._collector_combo)

        return section

    # ------------------------------------------------------------------
    # Assignments card (rows only — no title, no filter)
    # ------------------------------------------------------------------

    def _create_assignments_card(self) -> QFrame:
        """Card showing field collector assignment rows."""
        card = QFrame()
        card.setObjectName("assignmentsCard")
        card.setStyleSheet("""
            QFrame#assignmentsCard {
                background-color: white;
                border-radius: 8px;
            }
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        # Assignments rows container
        self._assignments_rows = QVBoxLayout()
        self._assignments_rows.setSpacing(6)
        layout.addLayout(self._assignments_rows)

        # Empty state
        self._assignments_empty = QLabel("اختر باحث لعرض التعيينات")
        self._assignments_empty.setFont(create_font(size=FontManager.SIZE_BODY))
        self._assignments_empty.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        self._assignments_empty.setAlignment(Qt.AlignCenter)
        self._assignments_empty.setMinimumHeight(60)
        layout.addWidget(self._assignments_empty)

        # Auto-refresh timer
        self._assignments_timer = QTimer(self)
        self._assignments_timer.timeout.connect(self._refresh_assignments)
        self._assignments_timer.start(30000)

        return card

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_collectors(self):
        """Load field collectors into combo box."""
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            collectors = api.get_field_collectors()
            items = (
                collectors if isinstance(collectors, list)
                else collectors.get("items", []) if isinstance(collectors, dict)
                else []
            )

            self._collector_combo.blockSignals(True)
            self._collector_combo.clear()
            self._collector_combo.addItem("-- اختر باحث --", "")
            for user in items:
                uid = user.get("id") or user.get("userId") or ""
                name = (
                    user.get("fullNameArabic")
                    or user.get("fullName")
                    or user.get("userName")
                    or uid
                )
                if uid:
                    self._collector_combo.addItem(name, uid)
            self._collector_combo.blockSignals(False)
        except Exception as e:
            logger.warning(f"Failed to load field collectors: {e}")

    def _on_collector_changed(self, index):
        """Handle collector selection change."""
        self._refresh_assignments()

    def _refresh_assignments(self):
        """Refresh assignments for selected collector."""
        while self._assignments_rows.count():
            item = self._assignments_rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        collector_id = self._collector_combo.currentData()
        if not collector_id:
            self._assignments_empty.setText("اختر باحث لعرض التعيينات")
            self._assignments_empty.show()
            return

        try:
            from services.api_client import get_api_client
            api = get_api_client()
            assignments = api.get_field_collector_assignments(collector_id)
            items = (
                assignments if isinstance(assignments, list)
                else assignments.get("items", []) if isinstance(assignments, dict)
                else []
            )

            if not items:
                self._assignments_empty.setText("لا توجد تعيينات لهذا الباحث")
                self._assignments_empty.show()
                return

            self._assignments_empty.hide()
            for assignment in items:
                row = self._create_assignment_row(assignment)
                self._assignments_rows.addWidget(row)

        except Exception as e:
            logger.warning(f"Failed to load assignments: {e}")
            self._assignments_empty.setText("فشل تحميل التعيينات")
            self._assignments_empty.show()

    def _create_assignment_row(self, assignment: dict) -> QFrame:
        """Create a row for a field collector assignment."""
        row = QFrame()
        row.setFixedHeight(48)
        row.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #D6DBE9;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Building code
        building_code = (
            assignment.get("buildingCode")
            or assignment.get("buildingId")
            or assignment.get("building_id")
            or "---"
        )
        id_label = QLabel(str(building_code)[:20])
        id_label.setFont(create_font(size=FontManager.SIZE_BODY))
        id_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(id_label)

        layout.addStretch()

        # Transfer status badge
        status = (
            assignment.get("transferStatusName")
            or assignment.get("transferStatus")
            or assignment.get("transfer_status")
            or "not_transferred"
        )
        # Normalize status (API may return int or string)
        status_str = str(status).lower().replace(" ", "_")
        status_config = {
            'not_transferred': ('في الانتظار', '#9CA3AF', '#F3F4F6'),
            'pending': ('في الانتظار', '#9CA3AF', '#F3F4F6'),
            '0': ('في الانتظار', '#9CA3AF', '#F3F4F6'),
            'transferring': ('قيد النقل', '#3890DF', '#EBF5FF'),
            'in_progress': ('قيد النقل', '#3890DF', '#EBF5FF'),
            '1': ('قيد النقل', '#3890DF', '#EBF5FF'),
            'transferred': ('تم النقل', '#10B981', '#ECFDF5'),
            'completed': ('تم النقل', '#10B981', '#ECFDF5'),
            '2': ('تم النقل', '#10B981', '#ECFDF5'),
            'failed': ('فشل', '#EF4444', '#FEF2F2'),
            '3': ('فشل', '#EF4444', '#FEF2F2'),
        }
        label, color, bg = status_config.get(status_str, status_config['not_transferred'])
        badge = QLabel(label)
        badge.setFont(create_font(size=FontManager.SIZE_CAPTION, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(24)
        badge.setMinimumWidth(80)
        badge.setStyleSheet(f"""
            padding: 2px 10px;
            border-radius: 12px;
            color: {color};
            background-color: {bg};
        """)
        layout.addWidget(badge)

        # Assignment date
        assigned_date = assignment.get("assignedDate") or assignment.get("created_at") or ""
        if assigned_date:
            date_str = str(assigned_date)[:10]
            date_label = QLabel(date_str)
            date_label.setFont(create_font(size=FontManager.SIZE_CAPTION))
            date_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            layout.addWidget(date_label)

        return row

    # ------------------------------------------------------------------
    # Sync log
    # ------------------------------------------------------------------

    def _create_sync_row(self, display_text: str, sync_date: str) -> QFrame:
        row = QFrame()
        row.setFixedHeight(48)
        row.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #D6DBE9;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(18, 18)
        icon_label.setAlignment(Qt.AlignCenter)
        pixmap = Icon.load_pixmap("fluent", size=18)
        if pixmap and not pixmap.isNull():
            icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        text_label = QLabel(display_text)
        text_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal
        ))
        text_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(text_label)

        layout.addStretch()

        date_label = QLabel(sync_date or "")
        date_label.setFont(create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal
        ))
        date_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(date_label)

        return row

    def _clear_rows(self):
        if self._rows_container:
            while self._rows_container.count():
                item = self._rows_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def _load_sync_log(self):
        """Load sync log from local database."""
        if not self.db:
            return []

        try:
            rows = self.db.fetch_all(
                "SELECT device_id, action, details, sync_date, status "
                "FROM sync_log ORDER BY sync_date DESC"
            )
            if not rows:
                return []
            return [
                (r.get('device_id', ''), r.get('action', ''), r.get('details', ''),
                 r.get('sync_date', ''), r.get('status', ''))
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Failed to load sync log: {e}")
            return []

    def refresh(self, data=None):
        """Refresh sync log display and field collector assignments."""
        self._clear_rows()

        rows = self._load_sync_log()

        if rows:
            self._empty_label.hide()
            for row in rows:
                device_id = row[0] or "---"
                action = row[1] or ""
                sync_date = row[3] or ""

                display_text = action if action else f"مزامنة من الجهاز {device_id}"

                row_widget = self._create_sync_row(display_text, sync_date)
                self._rows_container.addWidget(row_widget)
        else:
            self._empty_label.show()

        # Load field collectors
        self._load_collectors()
        self._refresh_assignments()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
