# -*- coding: utf-8 -*-
"""Import wizard step 1: incoming packages selection."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QStackedWidget, QSizePolicy, QFileDialog,
    QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor

from ui.components.animated_card import EmptyStateAnimated
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.animation_utils import stagger_fade_in
from services.vocab_service import get_label as vocab_get_label
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger

logger = get_logger(__name__)

_POLL_INTERVAL_MS = 30_000  # 30 seconds


class _PackageCard(QFrame):
    """Card widget for a single incoming package."""

    clicked = pyqtSignal(str)  # package_id

    def __init__(self, pkg_data: dict, parent=None):
        super().__init__(parent)
        self._pkg_id = pkg_data.get("id") or pkg_data.get("packageId") or ""
        self._status = pkg_data.get("status", 1)
        self._selected = False
        self._setup_ui(pkg_data)

    def _setup_ui(self, pkg: dict):
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(ScreenScale.h(100))
        self._apply_style(selected=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(8)

        # Row 1: file name + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        file_name = pkg.get("fileName") or ""
        name_label = QLabel(file_name)
        name_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        name_label.setStyleSheet("color: #212B36; background: transparent; border: none;")
        row1.addWidget(name_label)

        row1.addStretch()

        status_code = pkg.get("status", 1)
        badge_text = vocab_get_label("import_status", status_code)
        badge = QLabel(badge_text)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(ScreenScale.w(80), ScreenScale.h(22))
        badge.setStyleSheet("""
            QLabel {
                background-color: #DBEAFE;
                color: #1D4ED8;
                border-radius: 11px;
                border: none;
            }
        """)
        row1.addWidget(badge)

        layout.addLayout(row1)

        # Row 2: metadata
        row2 = QHBoxLayout()
        row2.setSpacing(24)

        date_raw = pkg.get("packageCreatedDate") or pkg.get("createdAtUtc") or ""
        if date_raw:
            date_str = str(date_raw)[:16].replace("T", "  ")
            row2.addWidget(self._meta_label(tr("wizard.import.step1.date_label"), date_str))

        buildings = pkg.get("buildingCount", 0) or 0
        units = pkg.get("propertyUnitCount", 0) or 0
        persons = pkg.get("personCount", 0) or 0
        content = tr("wizard.import.step1.content_summary", buildings=buildings, units=units, persons=persons)
        row2.addWidget(self._meta_label(tr("wizard.import.step1.content_label"), content))

        device_id = pkg.get("deviceId") or ""
        if device_id:
            row2.addWidget(self._meta_label(tr("wizard.import.step1.device_label"), str(device_id)[:20]))

        row2.addStretch()
        layout.addLayout(row2)

    def _meta_label(self, title: str, value: str) -> QLabel:
        label = QLabel(f"{title} {value}")
        label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet("color: #637381; background: transparent; border: none;")
        return label

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #EBF3FF, stop:1 #E0EDFF);
                    border: 2px solid rgba(56, 144, 223, 0.3);
                    border-radius: 12px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #F7FAFF, stop:1 #F0F5FF);
                    border: 1px solid #E2EAF2;
                    border-radius: 12px;
                }
                QFrame:hover {
                    border-color: rgba(56, 144, 223, 0.3);
                    background: #F0F5FF;
                }
            """)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style(selected)

    def is_selected(self) -> bool:
        return self._selected

    def get_package_id(self) -> str:
        return self._pkg_id

    def get_status(self) -> int:
        return self._status

    def mousePressEvent(self, event):
        self.clicked.emit(self._pkg_id)
        super().mousePressEvent(event)


class ImportStep1Packages(QWidget):
    """Step 1: View and select incoming packages from field researchers."""

    package_selected = pyqtSignal(str)  # package_id
    upload_completed = pyqtSignal(str)  # package_id — auto-advance after upload
    new_packages_count = pyqtSignal(int)  # for notification badge
    back_requested = pyqtSignal()

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._selected_package_id = None
        self._selected_status = 0
        self._cards: list[_PackageCard] = []
        self._poll_timer = None
        self._dots_count = 0
        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()
        # Auto-polling disabled temporarily for import testing
        # self._start_polling()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(16)

        # Card container
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border-radius: 16px;
                border: 1px solid #E2EAF2;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 22))
        card.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # Header row: title + back button
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title = QLabel(tr("wizard.import.step1.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        header_row.addWidget(title)

        header_row.addStretch()

        back_btn = QPushButton(tr("wizard.import.step1.back_btn"))
        back_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        back_btn.setFixedHeight(ScreenScale.h(36))
        back_btn.setMinimumWidth(ScreenScale.w(100))
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(StyleManager.nav_button_secondary())
        back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(back_btn)

        card_layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Stacked widget: scroll (cards) vs empty state
        self._content_stack = QStackedWidget()

        # Page 0: Scroll area for package cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._cards_container)
        self._content_stack.addWidget(self._scroll)

        # Page 1: Empty state
        self._empty_label = EmptyStateAnimated(
            title=tr("wizard.import.step1.empty_state"),
        )
        self._content_stack.addWidget(self._empty_label)

        # Start with empty state visible
        self._content_stack.setCurrentIndex(1)
        card_layout.addWidget(self._content_stack, 1)

        main_layout.addWidget(card, 1)

    # -- Loading overlay -------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 200); }")
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(ScreenScale.w(240), ScreenScale.h(90))
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(6)

        self._loading_label = QLabel(tr("wizard.import.step1.loading"))
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_label)

        self._loading_dots = QLabel("")
        self._loading_dots.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._loading_dots.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_dots.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_dots)

        overlay_layout.addWidget(card)

        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)

        return overlay

    def _show_loading(self, message: str):
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)

    def _hide_loading(self):
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

    def _animate_dots(self):
        self._dots_count = (self._dots_count + 1) % 4
        self._loading_dots.setText("." * self._dots_count)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Data loading ----------------------------------------------------------

    def refresh(self, data=None):
        """Fetch pending packages from API and populate cards."""
        self._show_loading(tr("wizard.import.step1.loading_packages"))
        result = self.import_controller.get_packages(
            page=1, page_size=50
        )

        packages = []
        if result.success and result.data:
            raw = result.data
            if isinstance(raw, list):
                packages = raw
            elif isinstance(raw, dict):
                packages = raw.get("items", [])

        # Filter out terminal statuses (completed, partially completed, cancelled, failed)
        _TERMINAL_STATUSES = {9, 10, 11, 12}
        packages = [
            p for p in packages
            if p.get("status", 0) not in _TERMINAL_STATUSES
        ]

        self._populate_cards(packages)
        self.new_packages_count.emit(len(packages))
        self._hide_loading()

        logger.info(f"Step1: refreshed, {len(packages)} pending package(s)")

    def _populate_cards(self, packages: list):
        """Rebuild card widgets from package data."""
        # Clear existing cards
        for card in self._cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        # Remove stretch
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not packages:
            self._content_stack.setCurrentIndex(1)
            self._cards_layout.addStretch()
            self._selected_package_id = None
            self.package_selected.emit("")
            return

        self._content_stack.setCurrentIndex(0)

        for pkg in packages:
            card = _PackageCard(pkg, parent=self._cards_container)
            card.clicked.connect(self._on_card_clicked)
            self._cards.append(card)
            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()

        # Stagger entrance animation for package cards
        if self._cards:
            stagger_fade_in(self._cards)

        # Restore selection if still available
        if self._selected_package_id:
            found = False
            for c in self._cards:
                if c.get_package_id() == self._selected_package_id:
                    c.set_selected(True)
                    found = True
                    break
            if not found:
                self._selected_package_id = None
                self.package_selected.emit("")

    def _on_card_clicked(self, package_id: str):
        """Handle card selection."""
        for card in self._cards:
            is_match = card.get_package_id() == package_id
            card.set_selected(is_match)
            if is_match:
                self._selected_status = card.get_status()

        self._selected_package_id = package_id
        self.package_selected.emit(package_id)

    def get_selected_package_id(self) -> str:
        """Return the currently selected package ID."""
        return self._selected_package_id or ""

    def get_selected_status(self) -> int:
        """Return the currently selected package status code."""
        return self._selected_status

    def _start_polling(self):
        """Start auto-refresh timer."""
        if self._poll_timer is None:
            self._poll_timer = QTimer(self)
            self._poll_timer.timeout.connect(self.refresh)
        self._poll_timer.start(_POLL_INTERVAL_MS)

    def _stop_polling(self):
        """Stop auto-refresh timer."""
        if self._poll_timer is not None:
            self._poll_timer.stop()

    def _on_upload_file(self):
        """Upload .uhc file then auto-advance to processing."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("wizard.import.step1.select_file"), "", "UHC Files (*.uhc);;All Files (*)"
        )
        if not file_path:
            return

        from ui.components.message_dialog import MessageDialog

        self._show_loading(tr("wizard.import.step1.uploading_file"))
        result = self.import_controller.upload_package(file_path)
        self._hide_loading()

        if result.success:
            pkg_id = ""
            if result.data:
                pkg_id = result.data.get("id") or result.data.get("packageId") or ""
            logger.info(f"Upload succeeded, package_id={pkg_id}")
            self.refresh()
            if pkg_id:
                self._auto_select(pkg_id)
                self.upload_completed.emit(pkg_id)
            else:
                MessageDialog.success(self, tr("wizard.import.step1.upload_success_title"), result.message_ar or tr("wizard.import.step1.upload_success_msg"))
        else:
            MessageDialog.error(self, tr("wizard.import.step1.upload_error_title"), result.message_ar or tr("wizard.import.step1.upload_error_msg"))
            self.refresh()

    def _auto_select(self, package_id: str):
        """Auto-select a package card by ID."""
        for card in self._cards:
            is_match = card.get_package_id() == package_id
            card.set_selected(is_match)
            if is_match:
                self._selected_status = card.get_status()
        self._selected_package_id = package_id
        self.package_selected.emit(package_id)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())
        self._empty_label.set_title(tr("wizard.import.step1.empty_state"))
        self._loading_label.setText(tr("wizard.import.step1.loading"))

    def reset(self):
        """Reset to initial state."""
        self._selected_package_id = None
        for card in self._cards:
            card.set_selected(False)
        self._start_polling()
        self.refresh()
