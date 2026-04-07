# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QGraphicsDropShadowEffect, QToolButton, QWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint, pyqtSignal
from PyQt5.QtGui import QColor, QIcon

from app.config import Config
from utils.logger import get_logger
from services.translation_manager import tr, get_layout_direction
from ui.design_system import ScreenScale

logger = get_logger(__name__)


class _ResultsPopup(QWidget):
    """Floating popup that shows building search results below the search bar."""

    item_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 8)

        frame = QFrame()
        frame.setObjectName("ResultsFrame")
        frame.setStyleSheet("""
            QFrame#ResultsFrame {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 35))
        frame.setGraphicsEffect(shadow)

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        self.list_widget = QListWidget()
        self.list_widget.setLayoutDirection(get_layout_direction())
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
                font-size: 13px;
                color: #212B36;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 14px;
                border-bottom: 1px solid #F0F4F8;
            }
            QListWidget::item:last-child { border-bottom: none; }
            QListWidget::item:hover {
                background-color: #EEF4FF;
                color: #1E3A8A;
            }
            QListWidget::item:selected {
                background-color: #EEF4FF;
                color: #1E3A8A;
            }
        """)
        self.list_widget.itemClicked.connect(
            lambda item: self.item_selected.emit(item.data(Qt.UserRole))
        )
        inner.addWidget(self.list_widget)
        outer.addWidget(frame)

    def populate(self, buildings):
        self.list_widget.clear()
        for b in buildings:
            neighborhood = (b.neighborhood_name_ar or "").strip()
            display = b.building_id or b.building_uuid or ""
            if neighborhood:
                display = f"{display}  —  {neighborhood}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, b)
            self.list_widget.addItem(item)

        row_h = self.list_widget.sizeHintForRow(0) if self.list_widget.count() else 40
        total_h = min(row_h * self.list_widget.count() + 2, 220)
        self.list_widget.setFixedHeight(total_h)

    def show_below(self, anchor: QWidget):
        """Show the popup directly below the anchor widget."""
        pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 2))
        self.setFixedWidth(anchor.width())
        self.move(pos)
        self.show()


class BuildingPickerDialog(QDialog):
    """Compact overlay dialog to select a building via map or fallback text search."""

    def __init__(self, db, api_service, auth_token=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._api_service = api_service
        self._auth_token = auth_token
        self._selected_building = None

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_api_search)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("QDialog { background-color: transparent; }")

        if parent:
            self.setGeometry(parent.window().geometry())

        self._popup = _ResultsPopup(self)
        self._popup.item_selected.connect(self._on_building_selected)

        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        overlay = QFrame()
        overlay.setStyleSheet("QFrame { background-color: rgba(0, 0, 0, 0.45); }")
        overlay.mousePressEvent = lambda e: self.reject()

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)
        overlay_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setFixedWidth(ScreenScale.w(440))
        card.setObjectName("BPCard")
        card.setStyleSheet("""
            QFrame#BPCard {
                background-color: #FFFFFF;
                border-radius: 20px;
            }
        """)
        card.mousePressEvent = lambda e: e.accept()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)

        # ── Header ──
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel(tr("component.building_picker.title"))
        title.setStyleSheet(
            "font-size: 15px; font-weight: 600; color: #1A1F1D;"
            " background: transparent; border: none;"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        close_btn = QPushButton("×")
        close_btn.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 14px;
                color: #6B7280;
                font-size: 18px;
            }
            QPushButton:hover { background-color: #F3F4F6; }
        """)
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(close_btn)
        card_layout.addLayout(header_row)

        # ── Search bar (wizard pattern: map link + input + icon) ──
        self._search_bar = QFrame()
        self._search_bar.setObjectName("searchBar")
        self._search_bar.setFixedHeight(ScreenScale.h(42))
        self._search_bar.setStyleSheet("""
            QFrame#searchBar {
                background-color: #F8FAFF;
                border: 1px solid #E5EAF6;
                border-radius: 8px;
            }
        """)
        self._search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(self._search_bar)
        sb.setContentsMargins(12, 6, 8, 6)
        sb.setSpacing(6)

        map_btn = QPushButton(tr("component.building_picker.select_from_map"))
        map_btn.setFlat(True)
        map_btn.setCursor(Qt.PointingHandCursor)
        map_btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                color: {Config.PRIMARY_COLOR};
                font-size: 7pt;
                font-weight: 600;
                text-decoration: underline;
                padding: 0;
            }}
            QPushButton:hover {{ color: #2070B8; }}
        """)
        map_btn.clicked.connect(self._open_map)
        sb.addWidget(map_btn)

        sep = QLabel("|")
        sep.setStyleSheet("color: #D1D5DB; background: transparent; border: none;")
        sb.addWidget(sep)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("component.building_picker.search_placeholder"))
        self.search_input.setLayoutDirection(get_layout_direction())
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 10pt;
                color: #2C3E50;
                padding: 0px 4px;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        sb.addWidget(self.search_input, 1)

        # Search icon — use real icon if available, fallback to text
        search_icon = QToolButton()
        search_icon.setFixedSize(ScreenScale.w(26), ScreenScale.h(26))
        search_icon.setCursor(Qt.PointingHandCursor)
        search_icon.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                font-size: 13px;
            }
            QToolButton:hover {
                background-color: #EEF6FF;
                border-radius: 6px;
            }
        """)
        try:
            from ui.components.icon import Icon
            pixmap = Icon.load_pixmap("search", size=20)
            if pixmap and not pixmap.isNull():
                search_icon.setIcon(QIcon(pixmap))
                search_icon.setIconSize(QSize(20, 20))
            else:
                search_icon.setText("🔍")
        except Exception:
            search_icon.setText("🔍")
        search_icon.clicked.connect(self._do_api_search)
        sb.addWidget(search_icon)

        card_layout.addWidget(self._search_bar)

        overlay_layout.addWidget(card)
        outer.addWidget(overlay)

    # ── Search logic ──

    def _on_search_changed(self, text: str):
        self._search_timer.stop()
        if len(text.strip()) < 2:
            self._popup.hide()
            return
        self._search_timer.start(300)

    def _do_api_search(self):
        text = self.search_input.text().strip()
        if len(text) < 2:
            return
        try:
            response = self._api_service.search_buildings(building_id=text, page_size=20)
            items = []
            if isinstance(response, dict):
                items = response.get("buildings") or response.get("items") or response.get("data") or []
            elif isinstance(response, list):
                items = response

            from models.building import Building
            buildings = []
            for dto in items:
                b = Building()
                b.building_uuid = dto.get("id") or dto.get("buildingUuid") or ""
                b.building_id = (
                    dto.get("buildingCode") or dto.get("buildingNumber") or
                    dto.get("buildingId") or ""
                )
                b.neighborhood_name_ar = (
                    dto.get("neighborhoodName") or dto.get("neighborhoodNameAr") or ""
                )
                buildings.append(b)

            if buildings:
                self._popup.populate(buildings)
                self._popup.show_below(self._search_bar)
            else:
                self._popup.hide()

        except Exception as e:
            logger.warning(f"Building search failed: {e}")
            self._popup.hide()

    # ── Actions ──

    def _on_building_selected(self, building):
        self._popup.hide()
        self._selected_building = building
        self.accept()

    def _open_map(self):
        self._popup.hide()
        try:
            from ui.components.building_map_dialog_v2 import BuildingMapDialog
            dlg = BuildingMapDialog(
                db=self.db,
                auth_token=self._auth_token,
                read_only=False,
                parent=self
            )
            if dlg.exec_() == QDialog.Accepted:
                building = dlg.get_selected_building()
                if building:
                    self._selected_building = building
                    self.accept()
        except Exception as e:
            logger.warning(f"Failed to open map dialog: {e}")

    def get_selected_building(self):
        return self._selected_building
