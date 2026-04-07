# -*- coding: utf-8 -*-
"""
Evidence Dialog - Dialog for attaching evidence/documents.

Allows user to:
- Select document type
- Enter document metadata
- Attach file
- Add notes
"""

from typing import Dict, Any, Optional
import uuid

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDateEdit, QTextEdit, QGroupBox,
    QFrame, QFileDialog
)
from PyQt5.QtCore import Qt, QDate
from pathlib import Path

from app.config import Config
from services.vocab_service import get_options as vocab_get_options
from services.translation_manager import tr, get_layout_direction
from utils.logger import get_logger
from ui.design_system import ScreenScale

logger = get_logger(__name__)


class EvidenceDialog(QDialog):
    """Dialog for attaching evidence/documents."""

    # EvidenceType codes excluded from tenure evidence per API v1.7:
    # 1 = IdentificationDocument (moved to IdentificationDocument entity)
    # 5 = Photo (moved to IdentificationDocument entity)
    _EXCLUDED_EVIDENCE_TYPE_CODES = {1, 5}

    def __init__(self, evidence_data: Optional[Dict] = None, parent=None):
        """
        Initialize the dialog.

        Args:
            evidence_data: Optional existing evidence data for editing
            parent: Parent widget
        """
        super().__init__(parent)
        self.evidence_data = evidence_data
        self.selected_file = None
        self._slide_anim = None
        self._mode = "replace" if evidence_data and evidence_data.get("_replace_mode") else "create"
        self._original_evidence_id = evidence_data.get("evidence_id") if evidence_data else None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(get_layout_direction())

        parent_rect = parent.window().geometry() if parent else None
        if parent_rect:
            pw = min(500, parent_rect.width() - 40)
            ph = min(580, parent_rect.height() - 20)
        else:
            pw = 500
            ph = 580
        self.setFixedSize(pw, ph)

        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

        if evidence_data:
            self._load_evidence_data(evidence_data)

    def showEvent(self, event):
        """Side-panel slide-in."""
        super().showEvent(event)
        parent = self.parent()
        if not parent:
            return
        try:
            from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint
            pr = parent.window().geometry()
            is_rtl = get_layout_direction() == Qt.RightToLeft
            pw = self.width()
            pg = parent.window().mapToGlobal(parent.window().rect().topLeft())
            tx = pg.x() + 10 if is_rtl else pg.x() + pr.width() - pw - 10
            ty = pg.y() + (pr.height() - self.height()) // 2
            sx = tx + ((-pw) if is_rtl else pw)
            self.move(sx, ty)
            self._slide_anim = QPropertyAnimation(self, b"pos", self)
            self._slide_anim.setDuration(250)
            self._slide_anim.setStartValue(QPoint(sx, ty))
            self._slide_anim.setEndValue(QPoint(tx, ty))
            self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._slide_anim.start()
        except Exception:
            pass

    def _setup_ui(self):
        """Setup dialog UI as side panel."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("EvidenceCard")
        card.setStyleSheet("""
            QFrame#EvidenceCard {
                background-color: #FFFFFF;
                border-radius: 16px;
                border: 1px solid rgba(56, 144, 223, 0.10);
            }
        """)
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor
        sh = QGraphicsDropShadowEffect(card)
        sh.setBlurRadius(40)
        sh.setOffset(-4, 4)
        sh.setColor(QColor(10, 22, 40, 50))
        card.setGraphicsEffect(sh)
        outer.addWidget(card)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Dark header
        hdr = QFrame()
        hdr.setFixedHeight(ScreenScale.h(48))
        hdr.setObjectName("EvHdr")
        hdr.setStyleSheet("""
            QFrame#EvHdr {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0E2035, stop:1 #152F4E);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
        """)
        from PyQt5.QtWidgets import QPushButton
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(10)
        cbtn = QPushButton("\u2715")
        cbtn.setCursor(Qt.PointingHandCursor)
        cbtn.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        cbtn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(200, 220, 255, 0.85);
                border: 1px solid rgba(56, 144, 223, 0.15);
                border-radius: 7px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.15); color: white; }
        """)
        cbtn.clicked.connect(self.reject)
        hl.addWidget(cbtn)
        from ui.font_utils import create_font, FontManager
        tlbl = QLabel(tr("wizard.evidence_dialog.title"))
        tlbl.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        tlbl.setStyleSheet("color: white; background: transparent; border: none;")
        hl.addWidget(tlbl, 1)
        cl.addWidget(hdr)

        acc = QFrame()
        acc.setFixedHeight(2)
        acc.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(56, 144, 223, 0), stop:0.3 rgba(56, 144, 223, 100),
                stop:0.5 rgba(91, 168, 240, 160), stop:0.7 rgba(56, 144, 223, 100),
                stop:1 rgba(56, 144, 223, 0)); }
        """)
        cl.addWidget(acc)

        content = QWidget()
        content.setStyleSheet("background: #FAFBFD; border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;")
        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 18, 24, 18)
        cl.addWidget(content, 1)

        # Document type
        type_label = QLabel(tr("wizard.evidence_dialog.document_type"))
        type_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(type_label)

        self.type_combo = QComboBox()
        for code, label in vocab_get_options("EvidenceType"):
            if code in self._EXCLUDED_EVIDENCE_TYPE_CODES:
                continue
            self.type_combo.addItem(label, code)
        self.type_combo.setStyleSheet(self._input_style())
        layout.addWidget(self.type_combo)

        # Document number
        number_label = QLabel(tr("wizard.evidence_dialog.document_number"))
        number_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(number_label)

        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText(tr("wizard.evidence_dialog.document_number_placeholder"))
        self.number_edit.setStyleSheet(self._input_style())
        layout.addWidget(self.number_edit)

        # Issue date
        date_label = QLabel(tr("wizard.evidence_dialog.issue_date"))
        date_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(date_label)

        self.issue_date = QDateEdit()
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDate(QDate.currentDate())
        self.issue_date.setDisplayFormat("yyyy-MM-dd")
        self.issue_date.setStyleSheet(self._input_style())
        layout.addWidget(self.issue_date)

        # Issuing authority
        authority_label = QLabel(tr("wizard.evidence_dialog.issuing_authority"))
        authority_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(authority_label)

        self.authority_edit = QLineEdit()
        self.authority_edit.setPlaceholderText(tr("wizard.evidence_dialog.issuing_authority_placeholder"))
        self.authority_edit.setStyleSheet(self._input_style())
        layout.addWidget(self.authority_edit)

        # File selection
        file_frame = QGroupBox(tr("wizard.evidence_dialog.document_file"))
        file_layout = QHBoxLayout(file_frame)

        self.file_label = QLabel(tr("wizard.evidence_dialog.no_file_selected"))
        self.file_label.setStyleSheet("color: #7f8c8d;")
        file_layout.addWidget(self.file_label)

        browse_btn = QPushButton(tr("wizard.evidence_dialog.browse"))
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_frame)

        # Notes
        notes_label = QLabel(tr("wizard.evidence_dialog.notes"))
        notes_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(notes_label)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(tr("wizard.evidence_dialog.notes_placeholder"))
        self.notes_edit.setMaximumHeight(ScreenScale.h(80))
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
            }
        """)
        layout.addWidget(self.notes_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(tr("common.cancel"))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_text = tr("wizard.evidence_dialog.replace") if self._mode == "replace" else tr("wizard.evidence_dialog.add")
        save_btn = QPushButton(save_text)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #005A9C;
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _input_style(self) -> str:
        """Get input stylesheet."""
        return """
            QLineEdit, QComboBox, QDateEdit {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border-color: #3498db;
            }
        """

    def _browse_file(self):
        """Browse for file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("wizard.evidence_dialog.choose_file"), "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.doc *.docx *.mp3 *.wav *.ogg *.m4a);;All Files (*)"
        )
        if file_path:
            self.selected_file = file_path
            self.file_label.setText(Path(file_path).name)
            self.file_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

    def _load_evidence_data(self, evidence_data: Dict):
        """Load evidence data into form."""
        # Document type
        doc_type = evidence_data.get('document_type')
        if doc_type:
            idx = self.type_combo.findData(doc_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)

        # Document number
        if evidence_data.get('document_number'):
            self.number_edit.setText(evidence_data['document_number'])

        # Issue date
        if evidence_data.get('issue_date'):
            date = QDate.fromString(evidence_data['issue_date'], 'yyyy-MM-dd')
            if date.isValid():
                self.issue_date.setDate(date)

        # Issuing authority
        if evidence_data.get('issuing_authority'):
            self.authority_edit.setText(evidence_data['issuing_authority'])

        # File
        if evidence_data.get('file_path'):
            self.selected_file = evidence_data['file_path']
            self.file_label.setText(evidence_data.get('file_name', Path(self.selected_file).name))
            self.file_label.setStyleSheet(f"color: {Config.SUCCESS_COLOR};")

        # Notes
        if evidence_data.get('notes'):
            self.notes_edit.setPlainText(evidence_data['notes'])

    def get_evidence_data(self) -> Dict[str, Any]:
        """Get evidence data from form."""
        data = {
            'evidence_id': self.evidence_data.get('evidence_id') if self.evidence_data else str(uuid.uuid4()),
            'document_type': self.type_combo.currentData(),
            'document_number': self.number_edit.text().strip() or None,
            'issue_date': self.issue_date.date().toPyDate().isoformat(),
            'issuing_authority': self.authority_edit.text().strip() or None,
            'file_path': self.selected_file,
            'file_name': Path(self.selected_file).name if self.selected_file else None,
            'notes': self.notes_edit.toPlainText().strip() or None,
            '_replace_mode': self._mode == "replace",
            '_original_evidence_id': self._original_evidence_id,
        }
        return data

    def accept(self):
        """Validate and accept."""
        if self._mode == "replace" and not self.selected_file:
            from ui.components.toast import Toast
            Toast.show_toast(
                self, tr("wizard.evidence_dialog.file_required_for_replace"), Toast.WARNING)
            return
        super().accept()
