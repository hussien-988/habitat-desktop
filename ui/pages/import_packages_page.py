# -*- coding: utf-8 -*-
"""Import packages page — dark header design system, card layout, spinner overlay."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QMenu, QAction, QStackedWidget, QPushButton,
    QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QCursor

from ui.components.animated_card import AnimatedCard, animate_card_entrance
from ui.components.empty_state import EmptyState
from ui.components.dark_header_zone import DarkHeaderZone
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.error_handler import ErrorHandler
from ui.design_system import PageDimensions, ScreenScale
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from controllers.import_controller import ImportController
from services.vocab_service import get_label as vocab_get_label
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger

logger = get_logger(__name__)

# Status code -> color
_STATUS_COLORS = {
    1:  "#6B7280",   # Pending
    2:  "#3890DF",   # Validating
    3:  "#F59E0B",   # Staging
    4:  "#EF4444",   # Validation Failed
    5:  "#DC2626",   # Quarantined
    6:  "#8B5CF6",   # Reviewing Conflicts
    7:  "#059669",   # Ready To Commit
    8:  "#3890DF",   # Committing
    9:  "#10B981",   # Completed
    10: "#EF4444",   # Failed
    11: "#F59E0B",   # Partially Completed
    12: "#9CA3AF",   # Cancelled
}

# Status code -> bg color for pill badges
_STATUS_BG = {
    1:  "rgba(107,114,128,0.12)",
    2:  "rgba(56,144,223,0.12)",
    3:  "rgba(245,158,11,0.12)",
    4:  "rgba(239,68,68,0.12)",
    5:  "rgba(220,38,38,0.12)",
    6:  "rgba(139,92,246,0.12)",
    7:  "rgba(5,150,105,0.12)",
    8:  "rgba(56,144,223,0.12)",
    9:  "rgba(16,185,129,0.12)",
    10: "rgba(239,68,68,0.12)",
    11: "rgba(245,158,11,0.12)",
    12: "rgba(156,163,175,0.12)",
}

_NAV_BTN_STYLE = """
    QPushButton {{
        background: {bg};
        border: 1px solid rgba(56, 144, 223, 30);
        border-radius: 6px;
        color: {fg};
        font-size: 13pt;
        font-weight: bold;
    }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:disabled {{
        background: #E8EDF2;
        color: #B0BEC5;
        border-color: #DDE3EA;
    }}
"""


class _PackageCard(AnimatedCard):
    """Import package card showing name, status, dates, record counts."""

    _STATUS_BADGE_STYLES = {
        1:  {"bg": "rgba(107,114,128,0.12)", "fg": "#6B7280", "border": "#D1D5DB"},
        2:  {"bg": "rgba(56,144,223,0.12)", "fg": "#3890DF", "border": "#93C5FD"},
        3:  {"bg": "rgba(245,158,11,0.12)", "fg": "#F59E0B", "border": "#FCD34D"},
        4:  {"bg": "rgba(239,68,68,0.12)", "fg": "#EF4444", "border": "#FCA5A5"},
        5:  {"bg": "rgba(220,38,38,0.12)", "fg": "#DC2626", "border": "#FCA5A5"},
        6:  {"bg": "rgba(139,92,246,0.12)", "fg": "#8B5CF6", "border": "#C4B5FD"},
        7:  {"bg": "rgba(5,150,105,0.12)", "fg": "#059669", "border": "#6EE7B7"},
        8:  {"bg": "rgba(56,144,223,0.12)", "fg": "#3890DF", "border": "#93C5FD"},
        9:  {"bg": "rgba(16,185,129,0.12)", "fg": "#10B981", "border": "#6EE7B7"},
        10: {"bg": "rgba(239,68,68,0.12)", "fg": "#EF4444", "border": "#FCA5A5"},
        11: {"bg": "rgba(245,158,11,0.12)", "fg": "#F59E0B", "border": "#FCD34D"},
        12: {"bg": "rgba(156,163,175,0.12)", "fg": "#9CA3AF", "border": "#D1D5DB"},
    }

    def __init__(self, pkg_data: dict, parent=None):
        self._data = pkg_data
        status_code = pkg_data.get("status_code", 1)
        color = _STATUS_COLORS.get(status_code, "#6B7280")
        super().__init__(parent, card_height=110, status_color=color)

    def _build_content(self, layout):
        from PyQt5.QtWidgets import QHBoxLayout, QLabel
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
        from ui.font_utils import create_font, FontManager
        from ui.design_system import Colors
        from services.translation_manager import tr

        d = self._data
        status_code = d.get("status_code", 1)

        # Row 1: Package name + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        name_label = QLabel(d.get("package_name", "N/A"))
        name_label.setFont(create_font(size=13, weight=QFont.Bold))
        name_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        name_label.setMaximumWidth(ScreenScale.w(500))
        row1.addWidget(name_label)
        row1.addStretch()

        style = self._STATUS_BADGE_STYLES.get(status_code, self._STATUS_BADGE_STYLES[1])
        status_text = d.get("status_display", "-")
        badge = QLabel(status_text)
        badge.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(22))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 11px; "
            f"padding: 0 10px; }}"
        )
        row1.addWidget(badge)
        layout.addLayout(row1)

        # Row 2: Date + record counts
        parts = []
        if d.get("created_date"):
            parts.append(d["created_date"])
        if d.get("valid_records") is not None:
            parts.append(f"{tr('import.valid_records')}: {d['valid_records']}")
        details = QLabel(" \u2009\u00b7\u2009 ".join(parts) if parts else "-")
        details.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        details.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        layout.addWidget(details)

        # Row 3: source chip
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        chip_style = (
            "QLabel {{ background-color: {bg}; color: {fg}; "
            "border: 1px solid {border}; border-radius: 4px; "
            "padding: 2px 8px; }}"
        )
        source = d.get("source", "")
        if source:
            chip = QLabel(source)
            chip.setFont(create_font(size=8, weight=FontManager.WEIGHT_MEDIUM))
            chip.setStyleSheet(chip_style.format(bg="#EEF2FF", fg="#4338CA", border="#E0E7FF"))
            chips_row.addWidget(chip)
        chips_row.addStretch()
        layout.addLayout(chips_row)


class ImportPackagesPage(QWidget):
    """Import Packages page with dark header, animated cards, pagination, spinner overlay."""

    open_wizard = pyqtSignal()
    view_package = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None, **kwargs):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_controller = ImportController(db)

        self._packages = []
        self._current_page = 1
        self._rows_per_page = 20
        self._total_count = 0
        self._total_pages = 1
        self._user_role = "admin"
        self._loading = False
        self._card_widgets = []

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    # -- UI Setup ----------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet("background-color: #f0f7ff;")
        self.setLayoutDirection(get_layout_direction())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Dark header
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.import_packages.title"))

        self._stat_total = StatPill(tr("page.import_packages.stat_total"))
        self._stat_total.set_count(0)
        self._header.add_stat_pill(self._stat_total)

        # Upload button
        self._upload_btn = QPushButton(tr("page.import_packages.process_new"))
        self._upload_btn.setCursor(Qt.PointingHandCursor)
        self._upload_btn.setStyleSheet(StyleManager.refresh_button_dark())
        self._upload_btn.clicked.connect(self._on_upload_clicked)
        self._header.add_action_widget(self._upload_btn)

        root.addWidget(self._header)

        # Accent line
        self._accent = AccentLine()
        root.addWidget(self._accent)

        # Content area
        content_area = QWidget()
        content_area.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 16,
            PageDimensions.content_padding_h(), 16,
        )
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Page 0: scroll area with card container
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)

        # Page 1: empty state
        self._empty_state = EmptyState(
            icon_name="upload_file",
            title=tr("page.import_packages.no_packages"),
            description=tr("page.import_packages.no_packages_hint"),
        )
        self._stack.addWidget(self._empty_state)

        content_layout.addWidget(self._stack, 1)

        # Pagination bar
        self._pagination_bar = self._build_footer()
        content_layout.addWidget(self._pagination_bar)

        root.addWidget(content_area, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(ScreenScale.h(54))
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-top: 1px solid #E8EDF2;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
            }
        """)

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        # Prev button
        self._prev_btn = QPushButton("\u25B7")
        self._prev_btn.setFixedSize(ScreenScale.w(34), ScreenScale.h(34))
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setStyleSheet(
            _NAV_BTN_STYLE.format(bg="#F0F7FF", fg="#3890DF", hover="#E0EFFF")
        )
        self._prev_btn.clicked.connect(self._go_prev)
        layout.addWidget(self._prev_btn)

        # Page info
        self._page_label = QLabel("0")
        self._page_label.setFont(create_font(size=10))
        self._page_label.setStyleSheet("color: #546E7A; background: transparent;")
        layout.addWidget(self._page_label)

        # Next button
        self._next_btn = QPushButton("\u25C1")
        self._next_btn.setFixedSize(ScreenScale.w(34), ScreenScale.h(34))
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setStyleSheet(
            _NAV_BTN_STYLE.format(bg="#F0F7FF", fg="#3890DF", hover="#E0EFFF")
        )
        self._next_btn.clicked.connect(self._go_next)
        layout.addWidget(self._next_btn)

        layout.addStretch()

        # Rows per page
        self._rows_label = QLabel(tr("page.import_packages.rows_per_page"))
        self._rows_label.setFont(create_font(size=9))
        self._rows_label.setStyleSheet("color: #78909C; background: transparent;")
        layout.addWidget(self._rows_label)

        self._rows_btn = QPushButton(str(self._rows_per_page))
        self._rows_btn.setFixedSize(ScreenScale.w(44), ScreenScale.h(30))
        self._rows_btn.setCursor(Qt.PointingHandCursor)
        self._rows_btn.setStyleSheet("""
            QPushButton {
                background: #F0F7FF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                color: #546E7A;
                font-size: 10pt;
            }
            QPushButton:hover { background: #E0EFFF; }
        """)
        self._rows_btn.clicked.connect(self._show_rows_menu)
        layout.addWidget(self._rows_btn)

        return footer

    # -- Data loading ------------------------------------------------------

    def _load_packages(self):
        if self._loading:
            return
        self._loading = True
        self._spinner.show_loading(tr("page.import_packages.loading_packages"))

        try:
            result = self.import_controller.get_packages(
                page=self._current_page,
                page_size=self._rows_per_page,
                status_filter=None,
            )

            items = []
            total_count = 0

            if result.success:
                data = result.data or {}
                if isinstance(data, dict):
                    items = data.get("items", [])
                    total_count = data.get("totalCount", len(items))
                elif isinstance(data, list):
                    items = data
                    total_count = len(items)
            else:
                logger.error("Failed to load packages: %s", result.message)
                ErrorHandler.show_error(
                    self,
                    result.message_ar or tr("page.import_packages.load_failed"),
                )

            self._packages = items
            self._total_count = total_count
            self._total_pages = max(1, (total_count + self._rows_per_page - 1) // self._rows_per_page)

            self._stat_total.set_count(total_count)

            self._populate_cards(items, total_count)
        except Exception as exc:
            logger.error("Load packages exception: %s", exc)
        finally:
            self._loading = False
            self._spinner.hide_loading()

    def _populate_cards(self, items, total_count):
        self._clear_cards()

        if not items:
            self._stack.setCurrentIndex(1)
            self._update_pagination()
            return

        self._stack.setCurrentIndex(0)

        for idx, pkg in enumerate(items):
            card_data = self._pkg_to_card_data(pkg)
            card = _PackageCard(card_data)
            card.clicked.connect(lambda p=pkg: self._on_card_clicked(p))
            self._cards_layout.insertWidget(
                self._cards_layout.count() - 1, card
            )
            self._card_widgets.append(card)

        self._update_pagination()
        animate_card_entrance(self._card_widgets)

        if not self._shimmer_timer.isActive():
            self._shimmer_timer.start()

    def _pkg_to_card_data(self, pkg: dict) -> dict:
        """Convert raw API package dict to card display dict."""
        status_raw = pkg.get("status", 0)
        if isinstance(status_raw, str) and status_raw.isdigit():
            status_raw = int(status_raw)

        date_raw = pkg.get("packageCreatedDate") or pkg.get("createdAtUtc") or ""
        date_str = str(date_raw)[:10] if date_raw else ""

        return {
            "package_name": pkg.get("fileName") or "N/A",
            "status_code": status_raw,
            "status_display": vocab_get_label("import_status", status_raw),
            "created_date": date_str,
            "total_records": None,
            "valid_records": None,
            "source": str(pkg.get("deviceId") or "")[:20],
        }

    def _clear_cards(self):
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            if hasattr(card, '_entrance_anim') and card._entrance_anim:
                try:
                    card._entrance_anim.stop()
                except RuntimeError:
                    pass
            try:
                card.clicked.disconnect()
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_card_shimmer(self):
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    # -- Pagination --------------------------------------------------------

    def _update_pagination(self):
        if self._total_count == 0:
            self._page_label.setText("0")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return

        start = (self._current_page - 1) * self._rows_per_page + 1
        end = min(start + self._rows_per_page - 1, self._total_count)
        self._page_label.setText(f"{start}-{end} / {self._total_count}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)

    def _go_prev(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_packages()

    def _go_next(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_packages()

    def _show_rows_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #546E7A;
                font-size: 10pt;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F0F7FF;
                color: #3890DF;
            }
        """)

        for size in (10, 20, 50):
            action = menu.addAction(str(size))
            if size == self._rows_per_page:
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda checked, s=size: self._set_rows_per_page(s)
                )

        menu.exec_(self._rows_btn.mapToGlobal(self._rows_btn.rect().bottomLeft()))

    def _set_rows_per_page(self, size):
        self._rows_per_page = size
        self._rows_btn.setText(str(size))
        self._current_page = 1
        self._load_packages()

    # -- Card click / context menu -----------------------------------------

    def _on_card_clicked(self, pkg):
        pkg_id = str(pkg.get("id") or pkg.get("packageId") or "")
        status = pkg.get("status", 0)
        if isinstance(status, str) and status.isdigit():
            status = int(status)

        if status == 9:
            ErrorHandler.show_info(self.window(), tr("page.import_packages.package_completed_msg"))
            return
        if status == 12:
            ErrorHandler.show_info(self.window(), tr("page.import_packages.package_cancelled_msg"))
            return

        self._on_view_package(pkg_id)

    def _show_card_context_menu(self, pkg, pkg_id):
        status = pkg.get("status", 0)
        if isinstance(status, str) and status.isdigit():
            status = int(status)

        menu = QMenu(self)
        menu.setLayoutDirection(get_layout_direction())
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 10px 16px;
                border-radius: 4px;
                color: #212B36;
                font-size: 10.5pt;
            }
            QMenu::item:selected {
                background-color: #F0F7FF;
            }
        """)

        # View
        view_action = QAction(tr("action.view"), self)
        view_action.triggered.connect(lambda: self._on_view_package(pkg_id))
        menu.addAction(view_action)

        # Cancel (only if not already cancelled/completed)
        if status not in (9, 12):
            cancel_action = QAction(tr("action.cancel"), self)
            cancel_action.triggered.connect(lambda: self._cancel_package(pkg_id))
            menu.addAction(cancel_action)

        # Quarantine (only if not completed/cancelled/quarantined)
        if status not in (5, 9, 12):
            quarantine_action = QAction(tr("action.quarantine"), self)
            quarantine_action.triggered.connect(lambda: self._quarantine_package(pkg_id))
            menu.addAction(quarantine_action)

        # Reset commit (admin only, only for stuck committing status=8)
        if self._user_role == "admin" and status == 8:
            reset_action = QAction(tr("page.import_packages.reset_commit"), self)
            reset_action.triggered.connect(lambda: self._reset_commit(pkg_id))
            menu.addAction(reset_action)

        menu.exec_(QCursor.pos())

    def _on_view_package(self, pkg_id):
        self._spinner.show_loading()
        self.view_package.emit(pkg_id)

    def _on_upload_clicked(self):
        self._spinner.show_loading()
        self.open_wizard.emit()

    # -- Package actions ---------------------------------------------------

    def _cancel_package(self, package_id):
        self._spinner.show_loading(tr("page.import_packages.cancelling"))
        try:
            result = self.import_controller.cancel_package(package_id)
            if result.success:
                ErrorHandler.show_success(self, result.message_ar or tr("page.import_packages.package_cancelled"))
                self._load_packages()
            else:
                ErrorHandler.show_error(self, result.message_ar or tr("page.import_packages.cancel_failed"))
        except Exception as e:
            ErrorHandler.show_error(self, tr("page.import_packages.cancel_failed_detail", error=str(e)))
        finally:
            self._spinner.hide_loading()

    def _quarantine_package(self, package_id):
        self._spinner.show_loading(tr("page.import_packages.quarantining"))
        try:
            result = self.import_controller.quarantine_package(package_id)
            if result.success:
                ErrorHandler.show_success(self, result.message_ar or tr("page.import_packages.package_quarantined"))
                self._load_packages()
            else:
                ErrorHandler.show_error(self, result.message_ar or tr("page.import_packages.quarantine_failed"))
        except Exception as e:
            ErrorHandler.show_error(self, tr("page.import_packages.quarantine_failed_detail", error=str(e)))
        finally:
            self._spinner.hide_loading()

    def _reset_commit(self, package_id):
        self._spinner.show_loading()
        try:
            result = self.import_controller.reset_commit(package_id)
            if result.success:
                ErrorHandler.show_success(self, result.message_ar or tr("page.import_packages.reset_done"))
                self._load_packages()
            else:
                ErrorHandler.show_error(self, result.message_ar or tr("page.import_packages.reset_failed"))
        except Exception as e:
            ErrorHandler.show_error(self, tr("page.import_packages.reset_failed_detail", error=str(e)))
        finally:
            self._spinner.hide_loading()

    # -- Public API --------------------------------------------------------

    def refresh(self, data=None):
        self._current_page = 1
        self._spinner.hide_loading()
        self._load_packages()

    def configure_for_role(self, role):
        self._user_role = role
        can_upload = role in {"admin", "data_manager"}
        self._upload_btn.setVisible(can_upload)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.import_packages.title"))
        self._stat_total.set_label(tr("page.import_packages.stat_total"))
        self._upload_btn.setText(tr("page.import_packages.process_new"))

        self._rows_label.setText(tr("page.import_packages.rows_per_page"))

        # Empty state
        self._empty_state.set_title(tr("page.import_packages.no_packages"))
        self._empty_state.set_description(tr("page.import_packages.no_packages_hint"))

        if self._packages:
            self._populate_cards(self._packages, self._total_count)
