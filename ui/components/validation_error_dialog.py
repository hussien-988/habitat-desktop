# -*- coding: utf-8 -*-
"""Validation Error Dialog - displays detailed error information for validation failures."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app.config import Config
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager


class ValidationErrorDialog(QDialog):
    """Dialog to display detailed validation errors."""

    def __init__(self, error_type: str, error_details: dict, parent=None):
        super().__init__(parent)
        self.error_type = error_type
        self.error_details = error_details

        self.setWindowTitle("فشل التحقق من الحزمة")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Error icon and title
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #FEE2E2;
                border: 2px solid {Config.ERROR_COLOR};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)

        # Icon
        icon_label = QLabel("❌")
        icon_label.setStyleSheet("font-size: 48pt;")
        header_layout.addWidget(icon_label)

        # Title and subtitle
        title_layout = QVBoxLayout()

        title = QLabel("فشل التحقق من صحة الحزمة")
        title.setFont(create_font(size=16, weight=QFont.Bold, letter_spacing=0))
        title.setStyleSheet(f"color: {Config.ERROR_COLOR};")
        title_layout.addWidget(title)

        error_type_label = QLabel(self._get_error_type_text())
        error_type_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        error_type_label.setStyleSheet("color: #991B1B;")
        title_layout.addWidget(error_type_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addWidget(header_frame)

        # Scrollable details area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setSpacing(16)

        # Package Information Section
        self._add_section(details_layout, "📦 معلومات الحزمة", [
            ("اسم الملف:", self.error_details.get('filename', 'غير محدد')),
            ("معرف الحزمة:", self.error_details.get('package_id', 'غير محدد')),
            ("حجم الملف:", self._format_size(self.error_details.get('file_size', 0))),
            ("التاريخ:", self.error_details.get('timestamp', 'غير محدد')),
        ])

        # Error Details Section
        error_info = []
        if self.error_type == "invalid_signature":
            error_info = [
                ("التوقيع المتوقع:", self.error_details.get('expected_signature', 'N/A')[:32] + "..."),
                ("التوقيع الفعلي:", self.error_details.get('actual_signature', 'N/A')[:32] + "..."),
                ("السبب المحتمل:", "الحزمة قد تكون تالفة أو تم التلاعب بها"),
            ]
        elif self.error_type == "invalid_hash":
            error_info = [
                ("SHA-256 المتوقع:", self.error_details.get('expected_hash', 'N/A')[:32] + "..."),
                ("SHA-256 الفعلي:", self.error_details.get('actual_hash', 'N/A')[:32] + "..."),
                ("السبب المحتمل:", "الملف تالف أو تم تعديله أثناء النقل"),
            ]

        self._add_section(details_layout, "⚠️ تفاصيل الخطأ", error_info)

        # Quarantine Information
        self._add_section(details_layout, "🔒 معلومات العزل", [
            ("حالة الحزمة:", "تم عزلها (Quarantined)"),
            ("الموقع:", self.error_details.get('quarantine_path', '/data/quarantine/')),
            ("معرف السجل:", self.error_details.get('audit_log_id', 'N/A')),
        ])

        # Detailed Error Message
        details_label = QLabel("📋 رسالة الخطأ الكاملة:")
        details_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        details_label.setStyleSheet(f"color: {Config.TEXT_COLOR}; margin-top: 8px;")
        details_layout.addWidget(details_label)

        error_text = QTextEdit()
        error_text.setReadOnly(True)
        error_text.setPlainText(self.error_details.get('full_error', 'لا تتوفر تفاصيل إضافية'))
        error_text.setMaximumHeight(150)
        error_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #F9FAFB;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 8px;
                font-family: 'Courier New';
                font-size: 9pt;
            }}
        """)
        details_layout.addWidget(error_text)

        # Recommended Actions
        actions_label = QLabel("💡 الإجراءات الموصى بها:")
        actions_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        actions_label.setStyleSheet(f"color: {Config.TEXT_COLOR}; margin-top: 8px;")
        details_layout.addWidget(actions_label)

        recommendations = QLabel(self._get_recommendations())
        recommendations.setWordWrap(True)
        recommendations.setStyleSheet("""
            background-color: #FEF3C7;
            border: 1px solid #F59E0B;
            border-radius: 6px;
            padding: 12px;
            color: #92400E;
            line-height: 1.5;
        """)
        details_layout.addWidget(recommendations)

        details_layout.addStretch()

        scroll.setWidget(details_widget)
        layout.addWidget(scroll)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # View Log Button
        view_log_btn = QPushButton("📄 عرض سجل التدقيق")
        view_log_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.INFO_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #0284C7;
            }}
        """)
        view_log_btn.clicked.connect(self._on_view_log)
        button_layout.addWidget(view_log_btn)

        # Close Button
        close_btn = QPushButton("إغلاق")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.TEXT_LIGHT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #4B5563;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _add_section(self, parent_layout: QVBoxLayout, title: str, items: list):
        """Add an information section."""
        section_label = QLabel(title)
        section_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        section_label.setStyleSheet(f"color: {Config.TEXT_COLOR}; margin-top: 8px;")
        parent_layout.addWidget(section_label)

        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)

        for label, value in items:
            row_layout = QHBoxLayout()

            label_widget = QLabel(label)
            label_widget.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            label_widget.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            label_widget.setMinimumWidth(150)
            row_layout.addWidget(label_widget)

            value_widget = QLabel(str(value))
            value_widget.setWordWrap(True)
            value_widget.setStyleSheet(f"color: {Config.TEXT_COLOR};")
            row_layout.addWidget(value_widget, 1)

            info_layout.addLayout(row_layout)

        parent_layout.addWidget(info_frame)

    def _get_error_type_text(self) -> str:
        """Get human-readable error type."""
        if self.error_type == "invalid_signature":
            return "التوقيع الرقمي غير صالح"
        elif self.error_type == "invalid_hash":
            return "بصمة SHA-256 غير متطابقة"
        return "خطأ في التحقق"

    def _get_recommendations(self) -> str:
        """Get recommended actions based on error type."""
        if self.error_type == "invalid_signature":
            return (
                "• تأكد من أن الحزمة مصدرها التطبيق الرسمي للتابلت\n"
                "• تحقق من عدم تعديل الملف يدوياً بعد إنشائه\n"
                "• اتصل بمشرف النظام إذا استمرت المشكلة\n"
                "• لا تقم بتجاهل هذا الخطأ - قد يشير إلى محاولة تلاعب"
            )
        elif self.error_type == "invalid_hash":
            return (
                "• أعد تصدير البيانات من التابلت\n"
                "• تحقق من اتصال الشبكة أثناء نقل الملف\n"
                "• استخدم USB بدلاً من الشبكة إذا أمكن\n"
                "• افحص سلامة وسائط التخزين المستخدمة"
            )
        return "يرجى الاتصال بمشرف النظام للمساعدة."

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} بايت"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} كيلوبايت"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} ميجابايت"

    def _on_view_log(self):
        """Open audit log viewer."""
        # TODO: Implement audit log viewer
        from ui.components.toast import Toast
        Toast.show_toast(self.parent(), "سيتم فتح سجل التدقيق...", Toast.INFO)
