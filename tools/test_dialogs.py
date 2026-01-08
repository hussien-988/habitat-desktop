#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ملف تجريبي لاختبار جميع الحوارات (Dialogs) في UC-003

هذا الملف يعرض جميع الحوارات الجديدة بشكل تفاعلي للاختبار:
1. ValidationErrorDialog (S12b)
2. VocabularyIncompatibilityDialog (S12c)
3. CommitReportDialog (S17)
4. رسائل التأكيد والنجاح والخطأ

للتشغيل:
    python tools/test_dialogs.py
"""

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# Add parent directory to path for imports
sys.path.insert(0, '..')


class DialogTester(QWidget):
    """نافذة اختبار الحوارات - Dialog Tester Window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧪 اختبار حوارات UC-003")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)
        self.setLayoutDirection(Qt.RightToLeft)
        self._setup_ui()

    def _setup_ui(self):
        """إعداد الواجهة"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # العنوان
        title = QLabel("🧪 اختبار حوارات UC-003")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("اضغط على أي زر لاختبار الحوار المقابل")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; margin-bottom: 20px;")
        layout.addWidget(subtitle)

        # ═══════════════════════════════════════════════
        # القسم 1: حوارات UC-003 الرئيسية
        # ═══════════════════════════════════════════════
        section1 = QLabel("📋 حوارات UC-003 الرئيسية:")
        section1.setFont(QFont("Segoe UI", 12, QFont.Bold))
        section1.setStyleSheet("color: #1E40AF; margin-top: 10px;")
        layout.addWidget(section1)

        # زر اختبار S12b: Invalid Signature
        btn_s12b_sig = self._create_button(
            "❌ S12b: خطأ التوقيع الرقمي (Invalid Signature)",
            "#EF4444"
        )
        btn_s12b_sig.clicked.connect(self.test_validation_error_signature)
        layout.addWidget(btn_s12b_sig)

        # زر اختبار S12b: Invalid Hash
        btn_s12b_hash = self._create_button(
            "❌ S12b: خطأ البصمة SHA-256 (Invalid Hash)",
            "#DC2626"
        )
        btn_s12b_hash.clicked.connect(self.test_validation_error_hash)
        layout.addWidget(btn_s12b_hash)

        # زر اختبار S12c
        btn_s12c = self._create_button(
            "⚠️ S12c: عدم توافق المفردات (Vocabulary Incompatibility)",
            "#F59E0B"
        )
        btn_s12c.clicked.connect(self.test_vocabulary_incompatibility)
        layout.addWidget(btn_s12c)

        # زر اختبار S17
        btn_s17 = self._create_button(
            "✅ S17: تقرير الحفظ المفصل (Commit Report)",
            "#10B981"
        )
        btn_s17.clicked.connect(self.test_commit_report)
        layout.addWidget(btn_s17)

        # ═══════════════════════════════════════════════
        # القسم 2: حوارات عامة
        # ═══════════════════════════════════════════════
        section2 = QLabel("💬 حوارات عامة:")
        section2.setFont(QFont("Segoe UI", 12, QFont.Bold))
        section2.setStyleSheet("color: #1E40AF; margin-top: 20px;")
        layout.addWidget(section2)

        # زر Error Dialog
        btn_error = self._create_button(
            "🔴 رسالة خطأ (Error Dialog)",
            "#991B1B"
        )
        btn_error.clicked.connect(self.test_error_dialog)
        layout.addWidget(btn_error)

        # زر Info Dialog
        btn_info = self._create_button(
            "ℹ️ رسالة معلومات (Info Dialog)",
            "#0284C7"
        )
        btn_info.clicked.connect(self.test_info_dialog)
        layout.addWidget(btn_info)

        # زر Confirm Dialog
        btn_confirm = self._create_button(
            "⚠️ رسالة تأكيد (Confirm Dialog)",
            "#CA8A04"
        )
        btn_confirm.clicked.connect(self.test_confirm_dialog)
        layout.addWidget(btn_confirm)

        # ═══════════════════════════════════════════════
        # القسم 3: سيناريوهات الاستيراد
        # ═══════════════════════════════════════════════
        section3 = QLabel("🔄 سيناريوهات الاستيراد:")
        section3.setFont(QFont("Segoe UI", 12, QFont.Bold))
        section3.setStyleSheet("color: #1E40AF; margin-top: 20px;")
        layout.addWidget(section3)

        # زر سيناريو ناجح
        btn_success = self._create_button(
            "✅ سيناريو استيراد ناجح 100%",
            "#059669"
        )
        btn_success.clicked.connect(self.test_success_scenario)
        layout.addWidget(btn_success)

        # زر سيناريو جزئي
        btn_partial = self._create_button(
            "⚠️ سيناريو استيراد جزئي (مع تحذيرات)",
            "#D97706"
        )
        btn_partial.clicked.connect(self.test_partial_scenario)
        layout.addWidget(btn_partial)

        layout.addStretch()

        # زر الإغلاق
        btn_close = QPushButton("إغلاق")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-size: 12pt;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

    def _create_button(self, text: str, color: str) -> QPushButton:
        """إنشاء زر بتنسيق موحد"""
        btn = QPushButton(text)
        btn.setMinimumHeight(50)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-size: 11pt;
                font-weight: 600;
                text-align: right;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        return btn

    # ═══════════════════════════════════════════════════════════
    # اختبارات الحوارات
    # ═══════════════════════════════════════════════════════════

    def test_validation_error_signature(self):
        """اختبار حوار خطأ التوقيع الرقمي"""
        from ui.components.validation_error_dialog import ValidationErrorDialog

        error_details = {
            'error_type': 'invalid_signature',
            'package_id': 'PKG-20250108-TEST-001',
            'filename': 'test_survey_data.uhc',
            'file_size': 2457600,  # 2.4 MB
            'timestamp': '2025-01-08 14:30:00',
            'expected_signature': 'A1B2C3D4E5F6789...',
            'actual_signature': 'X9Y8Z7W6V5U4321...',
            'quarantine_path': '/data/quarantine/2025/01/08/',
            'audit_log_id': 'AL-20250108-001',
            'error_message': 'Digital signature verification failed. The package may have been tampered with.'
        }

        dialog = ValidationErrorDialog(
            error_type='invalid_signature',
            error_details=error_details,
            parent=self
        )
        dialog.exec_()

    def test_validation_error_hash(self):
        """اختبار حوار خطأ البصمة SHA-256"""
        from ui.components.validation_error_dialog import ValidationErrorDialog

        error_details = {
            'error_type': 'invalid_hash',
            'package_id': 'PKG-20250108-TEST-002',
            'filename': 'corrupted_data.uhc',
            'file_size': 5242880,  # 5 MB
            'timestamp': '2025-01-08 15:45:00',
            'expected_hash': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
            'actual_hash': 'f4c1d55409ed2c260bfgf5d9007gc03538bf52f5740c045db506002c8963c966',
            'quarantine_path': '/data/quarantine/2025/01/08/',
            'audit_log_id': 'AL-20250108-002',
            'error_message': 'SHA-256 checksum mismatch. File may be corrupted during transfer.'
        }

        dialog = ValidationErrorDialog(
            error_type='invalid_hash',
            error_details=error_details,
            parent=self
        )
        dialog.exec_()

    def test_vocabulary_incompatibility(self):
        """اختبار حوار عدم توافق المفردات"""
        from ui.components.vocabulary_incompatibility_dialog import VocabularyIncompatibilityDialog

        incompatible_vocabs = [
            {
                'name': 'building_types',
                'name_ar': 'أنواع المباني',
                'current_version': '1.0',
                'required_version': '2.1',
                'version_diff': 1.1,
                'impact': 'high'
            },
            {
                'name': 'damage_levels',
                'name_ar': 'مستويات الضرر',
                'current_version': '1.2',
                'required_version': '1.5',
                'version_diff': 0.3,
                'impact': 'medium'
            },
            {
                'name': 'occupancy_types',
                'name_ar': 'أنواع الإشغال',
                'current_version': '2.0',
                'required_version': '2.1',
                'version_diff': 0.1,
                'impact': 'low'
            }
        ]

        package_info = {
            'filename': 'survey_batch_old_vocab.uhc',
            'package_id': 'PKG-20250108-TEST-003',
            'timestamp': '2025-01-08 10:15:00'
        }

        dialog = VocabularyIncompatibilityDialog(
            incompatible_vocabs=incompatible_vocabs,
            package_info=package_info,
            parent=self
        )
        dialog.exec_()

    def test_commit_report(self):
        """اختبار تقرير الحفظ المفصل"""
        from ui.components.commit_report_dialog import CommitReportDialog

        commit_result = {
            'success': True,
            'imported': 247,
            'skipped': 12,
            'warnings': 5,
            'failed': 0,
            'records_by_type': {
                'buildings': 45,
                'units': 89,
                'persons': 78,
                'households': 23,
                'claims': 10,
                'documents': 2
            },
            'duration_seconds': 34.5
        }

        import_metadata = {
            'original_file': 'survey_batch_complete.uhc',
            'archive_path': '/data/archive/2025/01/08/survey_batch_complete.uhc',
            'package_id': 'PKG-20250108-TEST-004',
            'audit_log_id': 'AL-20250108-004'
        }

        dialog = CommitReportDialog(
            commit_result=commit_result,
            import_metadata=import_metadata,
            parent=self
        )
        dialog.exec_()

    def test_error_dialog(self):
        """اختبار حوار الخطأ العام"""
        from ui.components.dialogs import ErrorDialog

        dialog = ErrorDialog(
            title="❌ خطأ في تحميل الملف",
            message="حدث خطأ أثناء محاولة تحميل ملف الاستيراد:\n\nFileNotFoundError: [Errno 2] No such file or directory: 'test.uhc'\n\nتأكد من أن الملف موجود في المسار الصحيح.",
            parent=self
        )
        dialog.exec_()

    def test_info_dialog(self):
        """اختبار حوار المعلومات"""
        from ui.components.dialogs import InfoDialog

        dialog = InfoDialog(
            title="✅ تم الحفظ بنجاح",
            message="تم حفظ التقرير في:\n\nC:\\Users\\Desktop\\import_report_20250108_143000.txt\n\nيمكنك فتح الملف لعرض التفاصيل الكاملة.",
            parent=self
        )
        dialog.exec_()

    def test_confirm_dialog(self):
        """اختبار حوار التأكيد"""
        from ui.components.dialogs import ConfirmDialog

        dialog = ConfirmDialog(
            title="⚠️ تأكيد الاستيراد الجماعي",
            message="هل أنت متأكد من استيراد جميع السجلات الجديدة (استبدال المكررات)؟\n\nسيتم استيراد 45 سجل جديد.\n\nهذا الإجراء لا يمكن التراجع عنه.",
            parent=self
        )
        result = dialog.exec_()

        # عرض النتيجة
        from ui.components.dialogs import InfoDialog
        if result:
            InfoDialog(
                title="✅ تم التأكيد",
                message="لقد اخترت 'نعم' - سيتم المتابعة بالاستيراد",
                parent=self
            ).exec_()
        else:
            InfoDialog(
                title="❌ تم الإلغاء",
                message="لقد اخترت 'لا' - تم إلغاء العملية",
                parent=self
            ).exec_()

    def test_success_scenario(self):
        """سيناريو استيراد ناجح 100%"""
        from ui.components.commit_report_dialog import CommitReportDialog

        commit_result = {
            'success': True,
            'imported': 500,
            'skipped': 0,
            'warnings': 0,
            'failed': 0,
            'records_by_type': {
                'buildings': 100,
                'units': 200,
                'persons': 150,
                'households': 40,
                'claims': 8,
                'documents': 2
            },
            'duration_seconds': 67.3
        }

        import_metadata = {
            'original_file': 'perfect_import.uhc',
            'archive_path': '/data/archive/2025/01/08/perfect_import.uhc',
            'package_id': 'PKG-20250108-PERFECT',
            'audit_log_id': 'AL-20250108-PERFECT'
        }

        dialog = CommitReportDialog(
            commit_result=commit_result,
            import_metadata=import_metadata,
            parent=self
        )
        dialog.exec_()

    def test_partial_scenario(self):
        """سيناريو استيراد جزئي مع مشاكل"""
        from ui.components.commit_report_dialog import CommitReportDialog

        commit_result = {
            'success': False,
            'imported': 189,
            'skipped': 45,
            'warnings': 23,
            'failed': 11,
            'records_by_type': {
                'buildings': 40,
                'units': 78,
                'persons': 52,
                'households': 15,
                'claims': 3,
                'documents': 1
            },
            'duration_seconds': 42.1
        }

        import_metadata = {
            'original_file': 'problematic_import.uhc',
            'archive_path': '/data/archive/2025/01/08/problematic_import.uhc',
            'package_id': 'PKG-20250108-PARTIAL',
            'audit_log_id': 'AL-20250108-PARTIAL'
        }

        dialog = CommitReportDialog(
            commit_result=commit_result,
            import_metadata=import_metadata,
            parent=self
        )
        dialog.exec_()


def main():
    """تشغيل نافذة الاختبار"""
    app = QApplication(sys.argv)

    # Set RTL layout for the entire application
    app.setLayoutDirection(Qt.RightToLeft)

    tester = DialogTester()
    tester.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 اختبار حوارات UC-003 - Dialog Tester")
    print("=" * 80)
    print("")
    print("هذا الملف يعرض جميع الحوارات الجديدة للاختبار:")
    print("  1. ValidationErrorDialog (S12b)")
    print("  2. VocabularyIncompatibilityDialog (S12c)")
    print("  3. CommitReportDialog (S17)")
    print("  4. رسائل التأكيد والنجاح والخطأ")
    print("")
    print("=" * 80)
    print("")

    main()
