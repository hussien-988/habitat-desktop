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
from utils.logger import get_logger

logger = get_logger(__name__)


class EvidenceDialog(QDialog):
    """Dialog for attaching evidence/documents."""

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

        self.setWindowTitle("إضافة دليل / وثيقة")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f7fa;
            }
        """)

        self._setup_ui()

        if evidence_data:
            self._load_evidence_data(evidence_data)

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Document type
        type_label = QLabel("نوع الوثيقة:")
        type_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(type_label)

        self.type_combo = QComboBox()
        for code, ar in self.DOCUMENT_TYPES:
            self.type_combo.addItem(ar, code)
        self.type_combo.setStyleSheet(self._input_style())
        layout.addWidget(self.type_combo)

        # Document number
        number_label = QLabel("رقم الوثيقة:")
        number_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(number_label)

        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("رقم الوثيقة (اختياري)")
        self.number_edit.setStyleSheet(self._input_style())
        layout.addWidget(self.number_edit)

        # Issue date
        date_label = QLabel("تاريخ الإصدار:")
        date_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(date_label)

        self.issue_date = QDateEdit()
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDate(QDate.currentDate())
        self.issue_date.setDisplayFormat("yyyy-MM-dd")
        self.issue_date.setStyleSheet(self._input_style())
        layout.addWidget(self.issue_date)

        # Issuing authority
        authority_label = QLabel("الجهة المصدرة:")
        authority_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(authority_label)

        self.authority_edit = QLineEdit()
        self.authority_edit.setPlaceholderText("الجهة المصدرة")
        self.authority_edit.setStyleSheet(self._input_style())
        layout.addWidget(self.authority_edit)

        # File selection
        file_frame = QGroupBox("ملف الوثيقة")
        file_layout = QHBoxLayout(file_frame)

        self.file_label = QLabel("لم يتم اختيار ملف")
        self.file_label.setStyleSheet("color: #7f8c8d;")
        file_layout.addWidget(self.file_label)

        browse_btn = QPushButton("استعراض...")
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
        notes_label = QLabel("ملاحظات:")
        notes_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(notes_label)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("ملاحظات (اختياري)")
        self.notes_edit.setMaximumHeight(80)
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

        cancel_btn = QPushButton("إلغاء")
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

        save_btn = QPushButton("إضافة")
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
            self, "اختر ملف الوثيقة", "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.doc *.docx);;All Files (*)"
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
        return {
            'evidence_id': self.evidence_data.get('evidence_id') if self.evidence_data else str(uuid.uuid4()),
            'document_type': self.type_combo.currentData(),
            'document_number': self.number_edit.text().strip() or None,
            'issue_date': self.issue_date.date().toString('yyyy-MM-dd'),
            'issuing_authority': self.authority_edit.text().strip() or None,
            'file_path': self.selected_file,
            'file_name': Path(self.selected_file).name if self.selected_file else None,
            'notes': self.notes_edit.toPlainText().strip() or None
        }
