# -*- coding: utf-8 -*-
"""
Developer Reset Dialog - DEV_MODE only.

Deletes all test data from the central database via API.
Accessible via Ctrl+Shift+R when Config.DEV_MODE is True.

Deletion order (respects FK constraints):
  1. Claims (independent entities - not cascaded by survey deletion)
  2. Building Assignments
  3. Surveys (cascades: households, persons, relations, evidence)
  4. Buildings (cascades: property units)
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QCheckBox, QLineEdit,
    QProgressBar, QTextEdit, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from ui.font_utils import create_font
from utils.logger import get_logger

logger = get_logger(__name__)


class _ResetWorker(QThread):
    """Background worker that performs the actual deletion via API."""

    progress = pyqtSignal(int, str)   # (percent 0-100, status message)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, options: dict, db=None):
        super().__init__()
        self.options = options
        self.db = db
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from services.api_client import get_api_client
        api = get_api_client()
        if not api:
            self.error.emit("API client غير متاح")
            return

        stats = {"local_claims": 0, "claims": 0, "assignments": 0, "surveys": 0, "buildings": 0}
        # Deletion order: local SQLite first, then API (claims → assignments → surveys → buildings)
        STEPS = ("local_claims", "claims", "assignments", "surveys", "buildings")
        steps = [k for k in STEPS if self.options.get(k)]
        total = len(steps)
        if total == 0:
            self.finished.emit(stats)
            return

        try:
            for step_idx, step in enumerate(steps):
                if self._cancelled:
                    break

                base_pct = step_idx * 100 // total
                end_pct = (step_idx + 1) * 100 // total

                if step == "local_claims":
                    self.progress.emit(base_pct, "جاري مسح السجلات المحلية (SQLite)...")
                    stats["local_claims"] = self._clear_local_claims()
                    self.progress.emit(end_pct, f"تم مسح {stats['local_claims']} سجل محلي")

                elif step == "claims":
                    self.progress.emit(base_pct, "جاري حذف المطالبات...")
                    stats["claims"] = self._delete_claims(api, base_pct, end_pct)
                    self.progress.emit(end_pct, f"تم حذف {stats['claims']} مطالبة")

                elif step == "assignments":
                    self.progress.emit(base_pct, "جاري حذف التعيينات الميدانية...")
                    stats["assignments"] = self._delete_assignments(api, base_pct, end_pct)
                    self.progress.emit(end_pct, f"تم حذف {stats['assignments']} تعيين ميداني")

                elif step == "surveys":
                    self.progress.emit(base_pct, "جاري حذف الاستبيانات...")
                    stats["surveys"] = self._delete_surveys(api, base_pct, end_pct)
                    self.progress.emit(end_pct, f"تم حذف {stats['surveys']} استبيان")

                elif step == "buildings":
                    self.progress.emit(base_pct, "جاري حذف المباني...")
                    stats["buildings"] = self._delete_buildings(api, base_pct, end_pct)
                    self.progress.emit(end_pct, f"تم حذف {stats['buildings']} مبنى")

            self.finished.emit(stats)

        except Exception as e:
            logger.error(f"Reset worker error: {e}", exc_info=True)
            self.error.emit(str(e))

    def _clear_local_claims(self) -> int:
        """Clear claims-related tables from local SQLite. Preserves users and vocabulary_terms."""
        if not self.db:
            return 0
        cleared = 0
        # Delete in FK order: junction/history tables first, then main claims table
        for table in ("claim_documents", "claim_history", "claims"):
            try:
                # Count before delete for reporting
                row = self.db.fetch_one(f"SELECT COUNT(*) FROM {table}")
                n = row[0] if row else 0
                self.db.execute(f"DELETE FROM {table}")
                cleared += n
                logger.info(f"Cleared {n} rows from local table: {table}")
            except Exception as e:
                logger.warning(f"Could not clear local table {table}: {e}")
        return cleared

    def _delete_claims(self, api, base_pct: int, end_pct: int) -> int:
        count = 0
        max_iterations = 500
        for _ in range(max_iterations):
            if self._cancelled:
                break
            try:
                claims = api.get_claims()
                if not claims:
                    break
                deleted_in_batch = 0
                for c in claims:
                    if self._cancelled:
                        break
                    try:
                        api.delete_claim(c.get("id", ""))
                        count += 1
                        deleted_in_batch += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete claim {c.get('id')}: {e}")
                if deleted_in_batch == 0:
                    break
                self.progress.emit(
                    base_pct + (end_pct - base_pct) * min(count, 100) // 100,
                    f"جاري حذف المطالبات... ({count})"
                )
            except Exception as e:
                logger.warning(f"Claims listing error: {e}")
                break
        return count

    def _delete_assignments(self, api, base_pct: int, end_pct: int) -> int:
        # Try to list assignments via buildings-for-assignment endpoint.
        # If the endpoint returns 404 or no results, skip silently.
        count = 0
        try:
            page = 1
            max_iterations = 200
            for _ in range(max_iterations):
                if self._cancelled:
                    break
                data = api.get_buildings_for_assignment(
                    has_active_assignment=True, page=page, page_size=100
                )
                items = data.get("items", [])
                if not items:
                    break
                deleted_in_batch = 0
                for item in items:
                    if self._cancelled:
                        break
                    assignment_id = item.get("assignmentId") or item.get("id")
                    if assignment_id:
                        try:
                            api.delete_building_assignment(assignment_id)
                            count += 1
                            deleted_in_batch += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete assignment {assignment_id}: {e}")
                if deleted_in_batch == 0:
                    break
                pct = base_pct + (end_pct - base_pct) * min(count, 100) // 100
                self.progress.emit(pct, f"جاري حذف التعيينات... ({count})")
                page += 1
        except Exception as e:
            logger.warning(f"Assignment listing error (skipping): {e}")
        return count

    # Known survey statuses returned by the backend.
    # The API returns empty surveys[] when no status is specified — must query per-status.
    _SURVEY_STATUSES = ["Draft", "Finalized", "Submitted", "UnderReview", "Verified"]

    def _delete_surveys(self, api, base_pct: int, end_pct: int) -> int:
        count = 0
        total_statuses = len(self._SURVEY_STATUSES)
        for status_idx, status in enumerate(self._SURVEY_STATUSES):
            if self._cancelled:
                break
            status_base = base_pct + (end_pct - base_pct) * status_idx // total_statuses
            max_iterations = 200
            for _ in range(max_iterations):
                if self._cancelled:
                    break
                try:
                    data = api.get_office_surveys(page=1, page_size=100, status=status)
                    surveys = data.get("surveys", data if isinstance(data, list) else [])
                    if not surveys:
                        break
                    deleted_in_batch = 0
                    for s in surveys:
                        if self._cancelled:
                            break
                        try:
                            api.delete_survey(s.get("id", ""))
                            count += 1
                            deleted_in_batch += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete survey {s.get('id')}: {e}")
                    if deleted_in_batch == 0:
                        break
                    self.progress.emit(
                        status_base,
                        f"جاري حذف الاستبيانات ({status})... ({count})"
                    )
                except Exception as e:
                    logger.warning(f"Survey listing error for status={status}: {e}")
                    break
        return count

    def _delete_buildings(self, api, base_pct: int, end_pct: int) -> int:
        count = 0
        max_iterations = 500
        for _ in range(max_iterations):
            if self._cancelled:
                break
            try:
                data = api.search_buildings(page=1, page_size=100)
                buildings = data.get("buildings", [])
                if not buildings:
                    break
                deleted_in_batch = 0
                for b in buildings:
                    if self._cancelled:
                        break
                    try:
                        api.delete_building(b.get("id", ""))
                        count += 1
                        deleted_in_batch += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete building {b.get('id')}: {e}")
                if deleted_in_batch == 0:
                    break
                pct = base_pct + (end_pct - base_pct) * min(count, 100) // 100
                self.progress.emit(pct, f"جاري حذف المباني... ({count})")
            except Exception as e:
                logger.warning(f"Building listing error: {e}")
                break
        return count


class DevResetDialog(QDialog):
    """
    Developer-only dialog for resetting test data in the central database.

    Only create/show this dialog when Config.DEV_MODE is True.
    """

    CONFIRM_WORD = "تأكيد"

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self._worker = None
        self._db = db

        self.setWindowTitle("أداة مطورين — إعادة تعيين بيانات الاختبار")
        self.setModal(True)
        self.setFixedWidth(480)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.RightToLeft)

        self._setup_ui()
        self._center_on_parent()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        container = QFrame()
        container.setObjectName("devResetContainer")
        container.setStyleSheet("""
            QFrame#devResetContainer {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E5E7EB;
            }
            QFrame#devResetContainer QLabel {
                border: none;
                background: transparent;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 60))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- Header ---
        header_row = QHBoxLayout()
        badge = QLabel("DEV")
        badge.setFixedSize(44, 22)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("""
            QLabel {
                background-color: #EF4444;
                color: white;
                border-radius: 4px;
                font-size: 9pt;
                font-weight: bold;
            }
        """)
        title = QLabel("إعادة تعيين بيانات الاختبار")
        title.setFont(create_font(size=14, weight=QFont.Bold))
        title.setStyleSheet("color: #111827;")
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(badge)
        layout.addLayout(header_row)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E5E7EB;")
        layout.addWidget(sep)

        # --- What will be deleted ---
        delete_label = QLabel("سيتم حذف:")
        delete_label.setFont(create_font(size=10, weight=QFont.Medium))
        delete_label.setStyleSheet("color: #374151;")
        layout.addWidget(delete_label)

        self.cb_local_claims = QCheckBox("سجلات SQLite المحلية — claims, claim_history")
        self.cb_claims = QCheckBox("المطالبات (Claims) — من الباكيند API")
        self.cb_assignments = QCheckBox("التعيينات الميدانية  (Building Assignments)")
        self.cb_surveys = QCheckBox("الاستبيانات + الأسر + الأشخاص + الأدلة")
        self.cb_buildings = QCheckBox("المباني + الوحدات العقارية")
        for cb in (self.cb_local_claims, self.cb_claims, self.cb_assignments, self.cb_surveys, self.cb_buildings):
            cb.setChecked(True)
            cb.setFont(create_font(size=10))
            cb.setStyleSheet("""
                QCheckBox { color: #1F2937; spacing: 8px; }
                QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; }
                QCheckBox::indicator:unchecked {
                    border: 1.5px solid #D1D5DB; background: white;
                }
                QCheckBox::indicator:checked {
                    border: 1.5px solid #EF4444;
                    background-color: #EF4444;
                    image: url(:/icons/check_white.png);
                }
            """)
            layout.addWidget(cb)
        self.cb_local_claims.setToolTip("سجلات المطالبات في قاعدة البيانات المحلية (data/trrcms.db) — السبب الرئيسي لظهور مطالبات 'غير محدد'")

        # --- What will NOT be deleted ---
        safe_frame = QFrame()
        safe_frame.setStyleSheet("""
            QFrame {
                background-color: #F0FDF4;
                border: 1px solid #BBF7D0;
                border-radius: 8px;
            }
            QFrame QLabel { background: transparent; }
        """)
        safe_layout = QVBoxLayout(safe_frame)
        safe_layout.setContentsMargins(12, 10, 12, 10)
        safe_layout.setSpacing(4)
        safe_title = QLabel("لن يتم المساس بـ:")
        safe_title.setFont(create_font(size=9, weight=QFont.Medium))
        safe_title.setStyleSheet("color: #166534;")
        safe_items = QLabel("المستخدمون  •  المفردات  •  التقسيمات الإدارية  •  الأحياء")
        safe_items.setFont(create_font(size=9))
        safe_items.setStyleSheet("color: #166534;")
        safe_layout.addWidget(safe_title)
        safe_layout.addWidget(safe_items)
        layout.addWidget(safe_frame)

        # --- Confirmation input ---
        confirm_label = QLabel(f'اكتب  "{self.CONFIRM_WORD}"  للمتابعة:')
        confirm_label.setFont(create_font(size=10))
        confirm_label.setStyleSheet("color: #374151;")
        layout.addWidget(confirm_label)

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText(self.CONFIRM_WORD)
        self.confirm_input.setFixedHeight(40)
        self.confirm_input.setFont(create_font(size=11))
        self.confirm_input.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #D1D5DB;
                border-radius: 8px;
                padding: 0 12px;
                color: #111827;
                background: white;
            }
            QLineEdit:focus {
                border-color: #EF4444;
            }
        """)
        self.confirm_input.textChanged.connect(self._on_confirm_changed)
        layout.addWidget(self.confirm_input)

        # --- Progress area (hidden initially) ---
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            QFrame QLabel { background: transparent; }
        """)
        prog_layout = QVBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(12, 10, 12, 10)
        prog_layout.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #E5E7EB;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #EF4444;
            }
        """)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_label = QLabel("جاري التحضير...")
        self.progress_label.setFont(create_font(size=9))
        self.progress_label.setStyleSheet("color: #6B7280;")
        self.progress_label.setAlignment(Qt.AlignCenter)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(80)
        self.log_view.setFont(create_font(size=9))
        self.log_view.setStyleSheet("""
            QTextEdit {
                border: none;
                background: transparent;
                color: #374151;
            }
        """)

        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.progress_label)
        prog_layout.addWidget(self.log_view)
        layout.addWidget(self.progress_frame)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.cancel_btn = QPushButton("إلغاء")
        self.cancel_btn.setFixedSize(120, 44)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFont(create_font(size=10))
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #6B7280;
                border: 1.5px solid #D1D5DB;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #F9FAFB; }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)

        self.reset_btn = QPushButton("حذف البيانات")
        self.reset_btn.setFixedSize(160, 44)
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setFont(create_font(size=10, weight=QFont.Medium))
        self.reset_btn.setEnabled(False)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:disabled {
                background-color: #FCA5A5;
                color: white;
            }
        """)
        self.reset_btn.clicked.connect(self._start_reset)

        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.reset_btn)
        layout.addLayout(btn_row)

        outer.addWidget(container)

    def _center_on_parent(self):
        parent = self.parent()
        if not parent:
            return
        self.adjustSize()
        target = parent.window() or parent
        rect = target.geometry()
        x = rect.x() + (rect.width() - self.width()) // 2
        y = rect.y() + (rect.height() - self.height()) // 2
        self.move(x, y)

    def _on_confirm_changed(self, text: str):
        self.reset_btn.setEnabled(text.strip() == self.CONFIRM_WORD)

    def _start_reset(self):
        if not any([
            self.cb_local_claims.isChecked(),
            self.cb_claims.isChecked(),
            self.cb_assignments.isChecked(),
            self.cb_surveys.isChecked(),
            self.cb_buildings.isChecked(),
        ]):
            return

        # Lock UI
        self.reset_btn.setEnabled(False)
        self.cancel_btn.setText("إيقاف")
        self.confirm_input.setEnabled(False)
        self.cb_local_claims.setEnabled(False)
        self.cb_claims.setEnabled(False)
        self.cb_assignments.setEnabled(False)
        self.cb_surveys.setEnabled(False)
        self.cb_buildings.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.adjustSize()
        self._center_on_parent()
        self.log_view.clear()

        options = {
            "local_claims": self.cb_local_claims.isChecked(),
            "claims": self.cb_claims.isChecked(),
            "assignments": self.cb_assignments.isChecked(),
            "surveys": self.cb_surveys.isChecked(),
            "buildings": self.cb_buildings.isChecked(),
        }

        self._worker = _ResetWorker(options, db=self._db)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self.reject()

    def _on_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self.log_view.append(message)

    def _on_finished(self, stats: dict):
        self.progress_bar.setValue(100)

        lines = []
        if stats.get("local_claims") is not None:
            lines.append(f"تم مسح {stats['local_claims']} سجل من SQLite المحلية")
        if stats.get("claims"):
            lines.append(f"تم حذف {stats['claims']} مطالبة (API)")
        if stats.get("assignments"):
            lines.append(f"تم حذف {stats['assignments']} تعيين ميداني")
        if stats.get("surveys"):
            lines.append(f"تم حذف {stats['surveys']} استبيان (وما يتبعه)")
        if stats.get("buildings"):
            lines.append(f"تم حذف {stats['buildings']} مبنى")
        if not lines:
            lines.append("لم يتم العثور على بيانات للحذف")

        summary = "\n".join(lines)
        self.progress_label.setText("اكتمل الحذف بنجاح")
        self.log_view.append(f"\n--- النتيجة ---\n{summary}")

        self.cancel_btn.setText("إغلاق")
        self.cancel_btn.setEnabled(True)
        logger.info(f"Dev reset completed: {stats}")

    def _on_error(self, message: str):
        self.progress_label.setText(f"خطأ: {message}")
        self.log_view.append(f"\n[خطأ] {message}")
        self.cancel_btn.setText("إغلاق")
        self.cancel_btn.setEnabled(True)
        logger.error(f"Dev reset error: {message}")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
