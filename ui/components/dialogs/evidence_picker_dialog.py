# -*- coding: utf-8 -*-
"""
Evidence Picker Dialog — select existing evidence documents to link to a claim.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect,
    QScrollArea, QWidget, QCheckBox
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QColor, QIcon, QPixmap

from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from utils.logger import get_logger
from services.translation_manager import tr, get_layout_direction

logger = get_logger(__name__)


class EvidencePickerDialog(QDialog):
    """Dialog to pick existing evidence documents from survey and link them to a relation."""

    def __init__(self, available_evidences: list, already_linked_ids: set, parent=None):
        super().__init__(parent)
        self._available = available_evidences or []
        self._already_linked = already_linked_ids or set()
        self._checkboxes = []  # list of (checkbox, evidence_id, evidence_data)
        self._selected_ids = []

        self.setModal(True)
        from PyQt5.QtWidgets import QApplication
        _scr = QApplication.primaryScreen().availableGeometry()
        self.resize(min(540, int(_scr.width() * 0.45)), min(480, int(_scr.height() * 0.55)))
        self.setMinimumSize(400, 360)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        # White container with shadow
        container = QFrame()
        container.setObjectName("pickerContainer")
        container.setStyleSheet("""
            QFrame#pickerContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#pickerContainer QLabel {
                background-color: transparent;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # Header row: title + close button
        header = QHBoxLayout()
        header.setSpacing(0)

        title = QLabel(tr("dialog.evidence_picker.title"))
        title.setFont(create_font(size=16, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #9CA3AF;
                border: none; font-size: 18px; font-weight: bold;
            }
            QPushButton:hover { color: #374151; }
        """)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Filter out already linked evidences
        filtered = []
        for ev in self._available:
            ev_id = str(ev.get("id") or "")
            if ev_id and ev_id not in self._already_linked:
                filtered.append(ev)

        if not filtered:
            empty_label = QLabel(tr("dialog.evidence_picker.no_documents"))
            empty_label.setFont(create_font(size=13))
            empty_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)
            layout.addStretch()
        else:
            # Scrollable list
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QWidget { background: transparent; }
            """)

            list_widget = QWidget()
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(0, 0, 0, 0)
            list_layout.setSpacing(6)

            for ev in filtered:
                row = self._create_evidence_row(ev)
                list_layout.addWidget(row)

            list_layout.addStretch()
            scroll.setWidget(list_widget)
            layout.addWidget(scroll, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        confirm_btn = self._create_button(tr("dialog.evidence_picker.select"), primary=True)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(confirm_btn)

        cancel_btn = self._create_button(tr("button.cancel"), primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        outer.addWidget(container)

    def _create_evidence_row(self, ev: dict) -> QFrame:
        ev_id = str(ev.get("id") or "")
        file_name = ev.get("originalFileName") or ev.get("fileName") or tr("dialog.evidence_picker.document")
        ev_type = ev.get("evidenceType") or ev.get("type") or ""
        date_str = str(ev.get("createdAtUtc") or ev.get("uploadedAt") or "")[:10]

        # Type label
        type_labels = {
            1: tr("dialog.evidence_picker.type_identity"),
            2: tr("dialog.evidence_picker.type_tenure"),
            "identification": tr("dialog.evidence_picker.type_identity"),
            "tenure": tr("dialog.evidence_picker.type_tenure"),
            "other": tr("dialog.evidence_picker.type_other"),
        }
        type_display = type_labels.get(ev_type, str(ev_type) if ev_type else "")

        row = QFrame()
        row.setObjectName("evidenceRow")
        row.setStyleSheet(f"""
            QFrame#evidenceRow {{
                background-color: #F8FAFC;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 10px;
            }}
            QFrame#evidenceRow QLabel, QFrame#evidenceRow QCheckBox {{
                background-color: transparent;
                border: none;
            }}
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(10)

        # Checkbox
        cb = QCheckBox()
        cb.setStyleSheet("QCheckBox { spacing: 0px; }")
        row_layout.addWidget(cb)
        self._checkboxes.append((cb, ev_id, ev))

        # File info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(file_name)
        name_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_MEDIUM))
        name_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        meta_parts = []
        if type_display:
            meta_parts.append(type_display)
        if date_str:
            meta_parts.append(date_str)
        if meta_parts:
            meta_label = QLabel(" \u00b7 ".join(meta_parts))
            meta_label.setFont(create_font(size=10))
            meta_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
            info_layout.addWidget(meta_label)

        row_layout.addLayout(info_layout, 1)

        # File extension badge
        ext = file_name.rsplit(".", 1)[-1].upper() if "." in file_name else ""
        if ext:
            ext_colors = {"PDF": "#E53E3E", "JPG": "#3182CE", "JPEG": "#3182CE",
                          "PNG": "#3182CE", "DOC": "#718096", "DOCX": "#718096",
                          "MP3": "#7C3AED", "WAV": "#7C3AED", "OGG": "#7C3AED", "M4A": "#7C3AED"}
            bg = ext_colors.get(ext, "#718096")
            ext_badge = QLabel(ext)
            ext_badge.setFixedSize(ScreenScale.w(40), ScreenScale.h(22))
            ext_badge.setAlignment(Qt.AlignCenter)
            ext_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_BOLD))
            ext_badge.setStyleSheet(
                f"color: white; background-color: {bg}; border-radius: 4px;")
            row_layout.addWidget(ext_badge)

        row_layout.addWidget(self._make_view_btn(ev_id, file_name))

        return row

    def _make_view_btn(self, ev_id: str, file_name: str) -> QPushButton:
        import os
        from ui.components.evidence_viewer import download_and_open_evidence

        btn = QPushButton()
        btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        btn.setToolTip(tr("dialog.evidence_picker.view_document"))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #EFF6FF;
                border: 1px solid #BFDBFE;
                border-radius: 7px;
                padding: 0;
            }
            QPushButton:hover { background: #DBEAFE; border-color: #93C5FD; }
            QPushButton:pressed { background: #BFDBFE; }
        """)

        _root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        icon_path = os.path.join(_root, "assets", "images", "eye-open.png")
        if os.path.exists(icon_path):
            px = QPixmap(icon_path).scaled(17, 17, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            btn.setIcon(QIcon(px))
            btn.setIconSize(QSize(17, 17))
        else:
            btn.setText("\u29c9")
            btn.setStyleSheet("""
                QPushButton {
                    background: #EFF6FF; color: #3890DF;
                    border: 1px solid #BFDBFE; border-radius: 7px;
                    font-size: 14px; padding: 0;
                }
                QPushButton:hover { background: #DBEAFE; border-color: #93C5FD; }
            """)

        btn.clicked.connect(
            lambda _checked=False, eid=ev_id, fn=file_name:
                download_and_open_evidence(self, eid, fn)
        )
        return btn

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(ScreenScale.w(150), ScreenScale.h(44))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))

        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white; border: none; border-radius: 8px;
                }}
                QPushButton:hover {{ background-color: #2A7BC8; }}
                QPushButton:pressed {{ background-color: #1E6CB3; }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white; color: #6B7280;
                    border: none; border-radius: 8px;
                }
                QPushButton:hover { background-color: #F9FAFB; }
                QPushButton:pressed { background-color: #F3F4F6; }
            """)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(8)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 25))
            btn.setGraphicsEffect(shadow)

        return btn

    def _on_confirm(self):
        self._selected_ids = []
        selected_data = []
        for cb, ev_id, ev_data in self._checkboxes:
            if cb.isChecked():
                self._selected_ids.append(ev_id)
                selected_data.append(ev_data)
        logger.info(f"Evidence picker: selected {len(self._selected_ids)} documents")
        self.accept()

    def get_selected_ids(self) -> list:
        return self._selected_ids

    def get_selected_data(self) -> list:
        """Return full evidence data dicts for selected items."""
        result = []
        for cb, ev_id, ev_data in self._checkboxes:
            if cb.isChecked():
                result.append(ev_data)
        return result
