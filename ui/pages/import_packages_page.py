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
from app.config import Pages
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.loading_spinner import LoadingSpinnerOverlay
from ui.error_handler import ErrorHandler
from ui.design_system import PageDimensions, ScreenScale
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from controllers.import_controller import ImportController
from services.vocab_service import get_label as vocab_get_label
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from services.import_status_map import (
    status_meta, is_history_status, queue_sort_priority,
    HISTORY as _HISTORY_STATUSES,
)
from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# Status code -> color (kept for backwards-compat consumers)
_STATUS_COLORS = {code: status_meta(code)["color_hex"] for code in range(1, 13)}
# Status code -> bg color for pill badges
_STATUS_BG = {code: status_meta(code)["bg_rgba"] for code in range(1, 13)}

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

    # Derived from services/import_status_map.status_meta()
    @classmethod
    def _badge_style(cls, status_code):
        meta = status_meta(status_code)
        return {"bg": meta["bg_rgba"], "fg": meta["color_hex"], "border": meta["border_hex"]}

    def __init__(self, pkg_data: dict, parent=None):
        self._data = pkg_data
        self._is_selected = False
        status_code = pkg_data.get("status_code", 1)
        color = _STATUS_COLORS.get(status_code, "#6B7280")
        super().__init__(parent, card_height=110, status_color=color)

    def set_selected(self, selected: bool):
        """Toggle the card's selected look.

        AnimatedCard reads its bg from the instance-level `_CARD_BG` /
        `_CARD_BG_HOVER` attributes during paintEvent, so overriding them
        here is enough to visually mark the selection. Unset to restore
        the default.
        """
        if self._is_selected == selected:
            return
        self._is_selected = selected
        if selected:
            self._CARD_BG = "#DCEBFF"
            self._CARD_BG_HOVER = "#CDE2FF"
        else:
            self._CARD_BG = type(self)._CARD_BG
            self._CARD_BG_HOVER = type(self)._CARD_BG_HOVER
        self.update()

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
        apply_label_alignment(name_label)
        row1.addWidget(name_label)
        row1.addStretch()

        style = self._badge_style(status_code)
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
        apply_label_alignment(details)
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

    view_package = pyqtSignal(str)

    def __init__(self, db=None, i18n=None, parent=None, **kwargs):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.import_controller = ImportController(db)

        self._packages = []                # raw API response (pre-partition)
        self._queue_packages = []          # partitioned active queue
        self._history_packages = []        # partitioned history
        self._mode = "queue"               # "queue" | "history"
        self._current_page = 1
        self._rows_per_page = 20
        self._total_count = 0
        self._total_pages = 1
        self._user_role = "admin"
        self._loading = False
        self._card_widgets = []
        # Selection state — row click selects; bottom button starts processing.
        self._selected_pkg_id: str = ""
        self._selected_card = None

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
        self._header.set_help(Pages.IMPORT_PACKAGES)

        self._stat_active = StatPill(tr("page.import_packages.stat_active"))
        self._stat_active.set_count(0)
        self._header.add_stat_pill(self._stat_active)

        self._stat_history = StatPill(tr("page.import_packages.stat_history"))
        self._stat_history.set_count(0)
        self._header.add_stat_pill(self._stat_history)

        # Refresh button.
        self._refresh_btn = QPushButton(tr("page.import_packages.refresh"))
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setStyleSheet(StyleManager.refresh_button_dark())
        self._refresh_btn.clicked.connect(self._load_packages)
        self._header.add_action_widget(self._refresh_btn)

        # Single mode-toggle button. Label flips based on current mode:
        #   queue   -> "View Import History"
        #   history -> "Back to Active Packages"
        # The opposite-mode toggle is the only button shown here — there is
        # no useless "Active Queue" button when already in queue mode.
        self._btn_toggle = QPushButton(tr("page.import_packages.show_history"))
        self._btn_toggle.setCursor(Qt.PointingHandCursor)
        self._btn_toggle.setStyleSheet(StyleManager.refresh_button_dark())
        self._btn_toggle.clicked.connect(self._on_toggle_mode)
        self._header.add_action_widget(self._btn_toggle)

        # Upload-package button is always hidden for all users — packages
        # arrive via the field-collector workflow. The button is created
        # but never added to the header, and `_upload_btn` is exposed as
        # None so configure_for_role / update_language stay no-ops.
        self._upload_btn = None

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

        # Subtitle — text varies by mode (active vs history).
        self._subtitle = QLabel(tr("page.import_packages.subtitle_active"))
        self._subtitle.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._subtitle.setStyleSheet(
            "color: #607D8B; background: transparent; padding: 0 0 12px 0;"
        )
        apply_label_alignment(self._subtitle)
        content_layout.addWidget(self._subtitle)

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

        # Fixed action bar at the bottom: selected-package label + Start
        # Processing button. The button is the ONLY way to begin processing
        # a package — clicking a row now only sets the selection.
        self._action_bar = self._build_action_bar()
        content_layout.addWidget(self._action_bar)

        root.addWidget(content_area, 1)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _build_action_bar(self) -> QFrame:
        """Bottom action bar: selected-package label + Start Processing button.

        The button is disabled until the user clicks a package row. This is
        the single entry point into the 3-step wizard; no other path starts
        processing.
        """
        bar = QFrame()
        bar.setFixedHeight(ScreenScale.h(64))
        bar.setStyleSheet(
            "QFrame { background: #F7FAFF; border-top: 1px solid #E2EAF2;"
            " border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(12)

        self._selected_label = QLabel("")
        self._selected_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._selected_label.setStyleSheet(
            "color: #3890DF; background: transparent; border: none;"
        )
        apply_label_alignment(self._selected_label)
        self._selected_label.setVisible(False)
        layout.addWidget(self._selected_label, 1)

        self._start_btn = QPushButton(tr("page.import_packages.start_processing"))
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.setFixedHeight(ScreenScale.h(42))
        self._start_btn.setMinimumWidth(ScreenScale.w(220))
        self._start_btn.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._start_btn.setStyleSheet(
            "QPushButton { background: #3890DF; color: white; border: none;"
            " border-radius: 10px; padding: 10px 28px; font-size: 11pt;"
            " font-weight: 600; }"
            " QPushButton:hover { background: #1A74C8; }"
            " QPushButton:disabled { background: #CBD5E1; color: #F0F5FF; }"
        )
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_processing)
        layout.addWidget(self._start_btn)

        return bar

    def _on_start_processing(self):
        """User explicitly asked to start processing the selected package."""
        if not self._selected_pkg_id:
            return
        self._on_view_package(self._selected_pkg_id)

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
            # Backend /packages supports only a single status filter; fetch one
            # generously-sized page and partition client-side into active/history.
            # Revisit if a single package list exceeds the page size.
            result = self.import_controller.get_packages(
                page=1,
                page_size=100,
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

            def _status_of(pkg):
                raw = pkg.get("status", 0)
                if isinstance(raw, str) and raw.isdigit():
                    return int(raw)
                return int(raw) if isinstance(raw, int) else 0

            self._packages = items
            self._queue_packages = [p for p in items if not is_history_status(_status_of(p))]
            self._history_packages = [p for p in items if is_history_status(_status_of(p))]

            # Sort the active queue by operational urgency: in-progress
            # (Committing/Validating/Staging) first, then needs-user states,
            # then blocked states. Failed sits at the bottom so the user
            # never sees a Failed package above a Validating one.
            self._queue_packages.sort(key=lambda p: queue_sort_priority(_status_of(p)))

            self._total_count = total_count
            self._stat_active.set_count(len(self._queue_packages))
            self._stat_history.set_count(len(self._history_packages))

            mode_items = (self._queue_packages if self._mode == "queue"
                          else self._history_packages)
            mode_total = len(mode_items)
            self._total_pages = max(1, (mode_total + self._rows_per_page - 1) // self._rows_per_page)

            # Slice for current page
            start = (self._current_page - 1) * self._rows_per_page
            end = start + self._rows_per_page
            self._populate_cards(mode_items[start:end], mode_total)
        except Exception as exc:
            logger.error("Load packages exception: %s", exc)
        finally:
            self._loading = False
            self._spinner.hide_loading()

    def _on_toggle_mode(self):
        """Flip between active queue and history modes (single toggle button)."""
        new_mode = "history" if self._mode == "queue" else "queue"
        self._set_mode(new_mode)

    def _set_mode(self, mode: str):
        """Switch between active queue and history views."""
        if mode not in ("queue", "history") or mode == self._mode:
            return
        self._mode = mode
        self._current_page = 1
        if mode == "queue":
            self._empty_state.set_title(tr("page.import_packages.no_packages"))
            self._empty_state.set_description(tr("page.import_packages.no_packages_hint"))
            self._btn_toggle.setText(tr("page.import_packages.show_history"))
            self._subtitle.setText(tr("page.import_packages.subtitle_active"))
        else:
            self._empty_state.set_title(tr("page.import_packages.tab_history"))
            self._empty_state.set_description(tr("page.import_packages.history_empty"))
            self._btn_toggle.setText(tr("page.import_packages.show_queue"))
            self._subtitle.setText(tr("page.import_packages.subtitle_history"))
        self._load_packages()

    def _populate_cards(self, items, total_count):
        # Any pending selection is invalid once we repopulate — start fresh.
        self._clear_selection()
        self._clear_cards()

        if not items:
            self._stack.setCurrentIndex(1)
            self._update_pagination()
            return

        self._stack.setCurrentIndex(0)

        for idx, pkg in enumerate(items):
            card_data = self._pkg_to_card_data(pkg)
            card = _PackageCard(card_data)
            card.clicked.connect(lambda p=pkg, c=card: self._on_card_clicked(p, c))
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

        meta = status_meta(status_raw) if status_raw else None
        # Central status map is the source of truth for badge text. The vocab
        # service is only consulted as a last-resort if the status code is
        # unknown to our map (defensive — should not happen for codes 1..12).
        if meta:
            status_display = tr(meta["label_key"])
        else:
            status_display = vocab_get_label("import_status", status_raw) or tr("import_status.unknown")
            logger.warning(f"Unknown package status: {status_raw}")

        return {
            "package_name": pkg.get("fileName") or "N/A",
            "status_code": status_raw,
            "status_display": status_display,
            "created_date": date_str,
            "total_records": pkg.get("totalRecords"),
            "valid_records": pkg.get("validRecords"),
            "source": str(pkg.get("deviceId") or pkg.get("exportedBy") or "")[:24],
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

    def _on_card_clicked(self, pkg, card=None):
        """Row click = SELECTION ONLY. Processing starts on the bottom
        "بدء المعالجة" button. The user can change their selection freely
        before starting, and no API call is made during selection."""
        pkg_id = str(pkg.get("id") or pkg.get("packageId") or "")
        if not pkg_id:
            ErrorHandler.show_error(self, tr("page.import_packages.load_failed"))
            return
        self._select_package(pkg_id, card)

    def _select_package(self, pkg_id: str, card=None):
        """Mark a package as the active selection (visual + state)."""
        # Clear previous selection.
        if self._selected_card is not None:
            try:
                self._selected_card.set_selected(False)
            except Exception:
                pass
        self._selected_pkg_id = pkg_id
        self._selected_card = card
        if card is not None:
            try:
                card.set_selected(True)
            except Exception:
                pass
        self._update_action_bar()

    def _clear_selection(self):
        """Drop the current selection (called on refresh / mode switch)."""
        if self._selected_card is not None:
            try:
                self._selected_card.set_selected(False)
            except Exception:
                pass
        self._selected_pkg_id = ""
        self._selected_card = None
        self._update_action_bar()

    def _update_action_bar(self):
        """Enable / label the bottom action button from the current selection.

        Only ACTIONABLE statuses (Pending → Completed progression) enable
        the button. Dead-end statuses (Quarantined, Cancelled, Failed,
        ValidationFailed, PartiallyCompleted) leave the button disabled —
        opening the wizard for them used to show a brief info dialog and
        then bounce back to the list, which the user found annoying.
        """
        from services.import_status_map import (
            action_label_key, is_actionable_status,
        )

        has_sel = bool(self._selected_pkg_id)
        if has_sel and self._selected_card is not None:
            name = self._selected_card._data.get("package_name", "") or self._selected_pkg_id
            status_code = self._selected_card._data.get("status_code", 0)
            self._selected_label.setText(
                tr("page.import_packages.selected_prefix").format(name=name)
            )
            self._selected_label.setVisible(True)
            actionable = is_actionable_status(status_code) if status_code else True
            if status_code and actionable:
                # Actionable status — show the status-specific label
                # ("بدء المعالجة"، "عرض التقرير"، etc.) and enable click.
                self._start_btn.setVisible(True)
                self._start_btn.setEnabled(True)
                self._start_btn.setText(tr(action_label_key(status_code)))
                self._start_btn.setToolTip("")
            elif status_code:
                # Non-actionable terminal status (Quarantined, Failed,
                # Cancelled, ValidationFailed, PartiallyCompleted): hide
                # the action button entirely. No "view reason" pseudo-
                # action — the badge in the card already communicates
                # the state and clicking through used to flash a useless
                # bounce screen.
                self._start_btn.setVisible(False)
                self._start_btn.setEnabled(False)
                self._start_btn.setToolTip("")
            else:
                self._start_btn.setVisible(True)
                self._start_btn.setEnabled(True)
                self._start_btn.setText(tr("page.import_packages.start_processing"))
                self._start_btn.setToolTip("")
        else:
            self._start_btn.setVisible(True)
            self._start_btn.setEnabled(False)
            self._selected_label.clear()
            self._selected_label.setVisible(False)
            self._start_btn.setText(tr("page.import_packages.start_processing"))
            self._start_btn.setToolTip("")

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
        """Upload a .uhc package and route the wizard to the new package id.

        The wizard is only entered with a specific package id (via
        `view_package`). This handler picks a file, uploads via the
        controller, and forwards the returned id so the wizard routes by
        the package's current backend status.
        """
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("page.import_packages.upload_package"),
            "",
            "UHC Files (*.uhc);;All Files (*)",
        )
        if not file_path:
            return

        self._spinner.show_loading(tr("wizard.import.loading_staging"))
        try:
            result = self.import_controller.upload_package(file_path)
        finally:
            self._spinner.hide_loading()

        if not result.success:
            ErrorHandler.show_error(
                self,
                result.message_ar or tr("import.error.stage_failed"),
            )
            return

        # Extract the new package id and open the wizard on it.
        data = result.data or {}
        pkg_id = str(data.get("id") or data.get("packageId") or "")
        if pkg_id:
            self.view_package.emit(pkg_id)
        else:
            # Upload succeeded but server didn't return an id — refresh the
            # list so the user can pick the new package manually.
            self._load_packages()

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
        # Confirm + collect required reason (backend persists it for audit).
        if not ErrorHandler.confirm(
            self,
            tr("import.error.reset_confirm_body"),
            tr("import.error.reset_confirm_title"),
        ):
            return
        # Match the cancel/reset reason flow elsewhere — use the project's
        # BottomSheet design instead of the default QInputDialog.
        from ui.pages.import_wizard_page import _prompt_reason_via_bottom_sheet
        reason = _prompt_reason_via_bottom_sheet(
            self,
            title=tr("import.error.reset_reason_title"),
            field_label=tr("import.error.reset_reason_prompt"),
            submit_text=tr("action.retry"),
            cancel_text=tr("action.dismiss"),
        )
        if not reason:
            ErrorHandler.show_error(self, tr("import.error.reset_reason_required"))
            return

        self._spinner.show_loading()
        try:
            result = self.import_controller.reset_commit(package_id, reason=reason)
            if result.success:
                ErrorHandler.show_success(
                    self,
                    result.message_ar or tr("page.import_packages.reset_done"),
                )
                self._load_packages()
            else:
                ErrorHandler.show_error(
                    self,
                    result.message_ar or tr("page.import_packages.reset_failed"),
                )
        except Exception as e:
            ErrorHandler.show_error(self, str(e))
        finally:
            self._spinner.hide_loading()

    # -- Public API --------------------------------------------------------

    def refresh(self, data=None):
        self._current_page = 1
        self._spinner.hide_loading()
        self._load_packages()

    def configure_for_role(self, role):
        self._user_role = role
        if self._upload_btn is not None:
            can_upload = role in {"admin", "data_manager"}
            self._upload_btn.setVisible(can_upload)

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._header.set_title(tr("page.import_packages.title"))
        self._stat_active.set_label(tr("page.import_packages.stat_active"))
        self._stat_history.set_label(tr("page.import_packages.stat_history"))
        self._refresh_btn.setText(tr("page.import_packages.refresh"))
        if self._upload_btn is not None:
            self._upload_btn.setText(tr("page.import_packages.upload_package"))
        # Single toggle button — text mirrors the OPPOSITE mode.
        if self._mode == "queue":
            self._btn_toggle.setText(tr("page.import_packages.show_history"))
            self._subtitle.setText(tr("page.import_packages.subtitle_active"))
        else:
            self._btn_toggle.setText(tr("page.import_packages.show_queue"))
            self._subtitle.setText(tr("page.import_packages.subtitle_history"))

        self._rows_label.setText(tr("page.import_packages.rows_per_page"))
        self._start_btn.setText(tr("page.import_packages.start_processing"))
        self._update_action_bar()

        # Empty state
        if self._mode == "queue":
            self._empty_state.set_title(tr("page.import_packages.no_packages"))
            self._empty_state.set_description(tr("page.import_packages.no_packages_hint"))
        else:
            self._empty_state.set_title(tr("page.import_packages.tab_history"))
            self._empty_state.set_description(tr("page.import_packages.history_empty"))

        if self._packages:
            self._load_packages()
