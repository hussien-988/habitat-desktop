# -*- coding: utf-8 -*-
"""
Vocabulary Incompatibility Report Dialog (UC-003 S12c)
Displays detailed incompatibility report for outdated vocabularies.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFrame, QScrollArea, QWidget, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app.config import Config
from ui.font_utils import create_font, FontManager


class VocabularyIncompatibilityDialog(QDialog):
    """
    Dialog to display detailed vocabulary incompatibility report (UC-003 S12c).

    Shows:
    - List of outdated vocabularies
    - Current version vs Required version
    - Impact assessment
    - Manual update options
    """

    def __init__(self, incompatible_vocabs: list, package_info: dict, parent=None):
        super().__init__(parent)
        self.incompatible_vocabs = incompatible_vocabs
        self.package_info = package_info

        self.setWindowTitle("تقرير عدم توافق المفردات")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Warning header
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #FEF3C7;
                border: 2px solid #F59E0B;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        header_layout = QHBoxLayout(header_frame)

        # Icon
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 48pt;")
        header_layout.addWidget(icon_label)

        # Title and subtitle
        title_layout = QVBoxLayout()

        title = QLabel("المفردات غير متوافقة")
        title.setFont(create_font(size=16, weight=QFont.Bold, letter_spacing=0))
        title.setStyleSheet("color: #92400E;")
        title_layout.addWidget(title)

        subtitle = QLabel(f"تحتوي الحزمة على {len(self.incompatible_vocabs)} مفردات قديمة تحتاج للتحديث")
        subtitle.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        subtitle.setStyleSheet("color: #B45309;")
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        layout.addWidget(header_frame)

        # Package Information
        pkg_label = QLabel("📦 معلومات الحزمة:")
        pkg_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(pkg_label)

        pkg_frame = QFrame()
        pkg_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        pkg_layout = QVBoxLayout(pkg_frame)

        pkg_items = [
            ("اسم الملف:", self.package_info.get('filename', 'غير محدد')),
            ("معرف الحزمة:", self.package_info.get('package_id', 'غير محدد')),
            ("إصدار التطبيق:", self.package_info.get('app_version', 'غير محدد')),
            ("تاريخ الإنشاء:", self.package_info.get('created_utc', 'غير محدد')),
        ]

        for label_text, value_text in pkg_items:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            label.setStyleSheet(f"color: {Config.TEXT_LIGHT};")
            label.setMinimumWidth(120)
            row.addWidget(label)

            value = QLabel(str(value_text))
            value.setStyleSheet(f"color: {Config.TEXT_COLOR};")
            row.addWidget(value, 1)

            pkg_layout.addLayout(row)

        layout.addWidget(pkg_frame)

        # Incompatible Vocabularies Table
        table_label = QLabel("📋 المفردات التي تحتاج للتحديث:")
        table_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(table_label)

        self.vocab_table = QTableWidget()
        self.vocab_table.setColumnCount(5)
        self.vocab_table.setHorizontalHeaderLabels([
            "اسم المفردات",
            "الإصدار الحالي",
            "الإصدار المطلوب",
            "الفرق",
            "التأثير"
        ])
        self.vocab_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.vocab_table.setAlternatingRowColors(True)
        self.vocab_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.vocab_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.vocab_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {Config.BORDER_COLOR};
                border-radius: 6px;
                gridline-color: #E5E7EB;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Config.PRIMARY_LIGHT};
            }}
            QHeaderView::section {{
                background-color: #F8FAFC;
                color: {Config.TEXT_LIGHT};
                font-weight: 600;
                padding: 10px;
                border: none;
                border-bottom: 1px solid {Config.BORDER_COLOR};
            }}
        """)

        # Populate table
        self.vocab_table.setRowCount(len(self.incompatible_vocabs))
        for i, vocab in enumerate(self.incompatible_vocabs):
            # Vocabulary name
            name_item = QTableWidgetItem(vocab.get('name', 'N/A'))
            name_item.setFont(create_font(size=9, weight=QFont.Bold, letter_spacing=0))
            self.vocab_table.setItem(i, 0, name_item)

            # Current version
            current_ver = vocab.get('current_version', '0')
            current_item = QTableWidgetItem(f"v{current_ver}")
            self.vocab_table.setItem(i, 1, current_item)

            # Required version
            required_ver = vocab.get('required_version', '0')
            required_item = QTableWidgetItem(f"v{required_ver}")
            required_item.setForeground(Config.ERROR_COLOR)
            self.vocab_table.setItem(i, 2, required_item)

            # Version difference
            try:
                diff = int(required_ver) - int(current_ver)
                diff_item = QTableWidgetItem(f"+{diff} إصدار" if diff > 0 else str(diff))
                diff_item.setForeground(Config.WARNING_COLOR)
                self.vocab_table.setItem(i, 3, diff_item)
            except:
                self.vocab_table.setItem(i, 3, QTableWidgetItem("غير محدد"))

            # Impact
            impact = vocab.get('impact', 'medium')
            impact_text = {"high": "🔴 عالي", "medium": "🟡 متوسط", "low": "🟢 منخفض"}.get(impact, impact)
            impact_item = QTableWidgetItem(impact_text)
            self.vocab_table.setItem(i, 4, impact_item)

        layout.addWidget(self.vocab_table)

        # Impact Assessment
        impact_label = QLabel("📊 تقييم التأثير:")
        impact_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(impact_label)

        impact_text = self._generate_impact_assessment()
        impact_display = QLabel(impact_text)
        impact_display.setWordWrap(True)
        impact_display.setStyleSheet(f"""
            background-color: #FEF3C7;
            border: 1px solid #F59E0B;
            border-radius: 6px;
            padding: 12px;
            color: #92400E;
        """)
        layout.addWidget(impact_display)

        # Recommended Actions
        actions_label = QLabel("💡 الإجراءات الموصى بها:")
        actions_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold, letter_spacing=0))
        layout.addWidget(actions_label)

        actions_text = (
            "1. قم بتحديث المفردات في قاعدة البيانات الرئيسية إلى الإصدارات المطلوبة\n"
            "2. استخدم صفحة 'إدارة المفردات' لتحديث كل مفردات على حدة\n"
            "3. بعد التحديث، أعد محاولة استيراد الحزمة\n"
            "4. تأكد من تحديث جميع الأجهزة اللوحية لاستخدام نفس إصدار المفردات"
        )
        actions_display = QLabel(actions_text)
        actions_display.setWordWrap(True)
        actions_display.setStyleSheet(f"""
            background-color: #DBEAFE;
            border: 1px solid {Config.INFO_COLOR};
            border-radius: 6px;
            padding: 12px;
            color: #1E40AF;
            line-height: 1.6;
        """)
        layout.addWidget(actions_display)

        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Go to Vocabulary Management
        vocab_mgmt_btn = QPushButton("📝 إدارة المفردات")
        vocab_mgmt_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Config.PRIMARY_DARK};
            }}
        """)
        vocab_mgmt_btn.clicked.connect(self._on_open_vocab_mgmt)
        button_layout.addWidget(vocab_mgmt_btn)

        # Export Report
        export_btn = QPushButton("📥 تصدير التقرير")
        export_btn.setStyleSheet(f"""
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
        export_btn.clicked.connect(self._on_export_report)
        button_layout.addWidget(export_btn)

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

    def _generate_impact_assessment(self) -> str:
        """Generate impact assessment text."""
        high_impact = sum(1 for v in self.incompatible_vocabs if v.get('impact') == 'high')
        medium_impact = sum(1 for v in self.incompatible_vocabs if v.get('impact') == 'medium')
        low_impact = sum(1 for v in self.incompatible_vocabs if v.get('impact') == 'low')

        text = f"• التأثير العالي: {high_impact} مفردات\n"
        text += f"• التأثير المتوسط: {medium_impact} مفردات\n"
        text += f"• التأثير المنخفض: {low_impact} مفردات\n\n"

        if high_impact > 0:
            text += "⚠️ تحذير: يوجد مفردات ذات تأثير عالي - يجب التحديث قبل الاستيراد"
        elif medium_impact > 0:
            text += "ℹ️ يُنصح بالتحديث قبل الاستيراد لتجنب مشاكل التوافق"
        else:
            text += "✓ التأثير منخفض - يمكن المتابعة بحذر"

        return text

    def _on_open_vocab_mgmt(self):
        """Open vocabulary management page."""
        from ui.components.toast import Toast
        Toast.show_toast(self.parent(), "سيتم فتح صفحة إدارة المفردات...", Toast.INFO)
        # TODO: Navigate to vocabulary management page
        self.accept()

    def _on_export_report(self):
        """Export incompatibility report to file."""
        from PyQt5.QtWidgets import QFileDialog
        from datetime import datetime

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ تقرير عدم التوافق",
            f"vocab_incompatibility_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("=" * 70 + "\n")
                    f.write("تقرير عدم توافق المفردات - TRRCMS\n")
                    f.write("=" * 70 + "\n\n")

                    f.write(f"اسم الملف: {self.package_info.get('filename', 'N/A')}\n")
                    f.write(f"معرف الحزمة: {self.package_info.get('package_id', 'N/A')}\n")
                    f.write(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                    f.write("-" * 70 + "\n")
                    f.write("المفردات غير المتوافقة:\n")
                    f.write("-" * 70 + "\n\n")

                    for vocab in self.incompatible_vocabs:
                        f.write(f"المفردات: {vocab.get('name', 'N/A')}\n")
                        f.write(f"  الإصدار الحالي: v{vocab.get('current_version', '0')}\n")
                        f.write(f"  الإصدار المطلوب: v{vocab.get('required_version', '0')}\n")
                        f.write(f"  التأثير: {vocab.get('impact', 'N/A')}\n\n")

                from ui.components.toast import Toast
                Toast.show_toast(self.parent(), f"تم حفظ التقرير في: {filename}", Toast.SUCCESS)
            except Exception as e:
                from ui.components.toast import Toast
                Toast.show_toast(self.parent(), f"خطأ في حفظ التقرير: {str(e)}", Toast.ERROR)
