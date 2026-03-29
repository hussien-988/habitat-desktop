# -*- coding: utf-8 -*-
"""
Developer Reset Dialog - DEV_MODE only.
Deletes all test data from the central database via API.
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
from services.translation_manager import tr, get_layout_direction

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
        # Direct SQL mode: bypass API entirely
        if self.options.get("direct_sql"):
            self.progress.emit(0, tr("dialog.dev_reset.direct_sql_delete"))
            stats = self._reset_all_direct_sql()
            if stats:
                # Also clear local SQLite
                if self.db:
                    self.progress.emit(90, tr("dialog.dev_reset.clearing_local"))
                    stats["local_claims"] = self._clear_local_claims()
                self.finished.emit(stats)
            else:
                self.error.emit(tr("dialog.dev_reset.direct_sql_failed"))
            return

        from services.api_client import get_api_client
        api = get_api_client()
        if not api:
            self.error.emit(tr("dialog.dev_reset.api_unavailable"))
            return

        stats = {"local_claims": 0, "claims": 0, "assignments": 0, "surveys": 0, "buildings": 0}
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
                    self.progress.emit(base_pct, tr("dialog.dev_reset.clearing_local_sqlite"))
                    stats["local_claims"] = self._clear_local_claims()
                    self.progress.emit(end_pct, tr("dialog.dev_reset.cleared_local_count").format(count=stats['local_claims']))

                elif step == "claims":
                    self.progress.emit(base_pct, tr("dialog.dev_reset.deleting_claims"))
                    stats["claims"] = self._delete_claims(api, base_pct, end_pct)
                    self.progress.emit(end_pct, tr("dialog.dev_reset.deleted_claims_count").format(count=stats['claims']))

                elif step == "assignments":
                    self.progress.emit(base_pct, tr("dialog.dev_reset.deleting_assignments"))
                    stats["assignments"] = self._delete_assignments(api, base_pct, end_pct)
                    self.progress.emit(end_pct, tr("dialog.dev_reset.deleted_assignments_count").format(count=stats['assignments']))

                elif step == "surveys":
                    self.progress.emit(base_pct, tr("dialog.dev_reset.deleting_surveys"))
                    stats["surveys"] = self._delete_surveys(api, base_pct, end_pct)
                    self.progress.emit(end_pct, tr("dialog.dev_reset.deleted_surveys_count").format(count=stats['surveys']))

                elif step == "buildings":
                    self.progress.emit(base_pct, tr("dialog.dev_reset.deleting_buildings"))
                    stats["buildings"] = self._delete_buildings(api, base_pct, end_pct)
                    self.progress.emit(end_pct, tr("dialog.dev_reset.deleted_buildings_count").format(count=stats['buildings']))

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
                    tr("dialog.dev_reset.deleting_claims_progress").format(count=count)
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
                self.progress.emit(pct, tr("dialog.dev_reset.deleting_assignments_progress").format(count=count))
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
                        tr("dialog.dev_reset.deleting_surveys_progress").format(status=status, count=count)
                    )
                except Exception as e:
                    logger.warning(f"Survey listing error for status={status}: {e}")
                    break
        return count

    def _delete_buildings(self, api, base_pct: int, end_pct: int) -> int:
        count = 0
        api_failed = False
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
                        if "500" in str(e):
                            api_failed = True
                            break
                        logger.warning(f"Failed to delete building {b.get('id')}: {e}")
                if api_failed or deleted_in_batch == 0:
                    break
                pct = base_pct + (end_pct - base_pct) * min(count, 100) // 100
                self.progress.emit(pct, tr("dialog.dev_reset.deleting_buildings_progress").format(count=count))
            except Exception as e:
                logger.warning(f"Building listing error: {e}")
                break

        if api_failed:
            self.progress.emit(base_pct, tr("dialog.dev_reset.api_failed_direct_sql"))
            count += self._delete_buildings_direct_sql()

        return count

    def _delete_buildings_direct_sql(self) -> int:
        """Direct PostgreSQL deletion when API DELETE has bugs."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost", port=5432,
                dbname="TRRCMS_Dev", user="postgres", password="3123124"
            )
            conn.autocommit = False
            cur = conn.cursor()

            cur.execute('SELECT COUNT(*) FROM "Buildings"')
            building_count = cur.fetchone()[0]

            if building_count == 0:
                cur.close()
                conn.close()
                return 0

            # Delete in FK order
            cur.execute('DELETE FROM "PropertyUnits"')
            cur.execute('DELETE FROM "Buildings"')
            conn.commit()

            cur.close()
            conn.close()
            logger.info(f"Direct SQL: deleted {building_count} buildings + property units")
            return building_count
        except ImportError:
            logger.error("psycopg2 not installed")
            return 0
        except Exception as e:
            logger.error(f"Direct SQL delete failed: {e}")
            return 0

    def _reset_all_direct_sql(self) -> dict:
        """Delete ALL test data directly from PostgreSQL, preserving system tables."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost", port=5432,
                dbname="TRRCMS_Dev", user="postgres", password="3123124"
            )
            conn.autocommit = False
            cur = conn.cursor()

            # Count before delete
            counts = {}
            for table in ("Claims", "Surveys", "Buildings", "PropertyUnits", "Persons",
                          "Households", "Evidences", "PersonPropertyRelations"):
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                counts[table] = cur.fetchone()[0]

            self.progress.emit(10, tr("dialog.dev_reset.breaking_circular_fk"))

            # Break circular FKs
            cur.execute('UPDATE "Persons" SET "HouseholdId" = NULL')
            cur.execute('UPDATE "Buildings" SET "BuildingDocumentId" = NULL')

            self.progress.emit(20, tr("dialog.dev_reset.deleting_child_tables"))

            # Delete in FK dependency order (leaf → parent)
            tables_to_delete = [
                "Certificate",
                "Referrals",
                "EvidenceRelations",
                "Documents",
                "Evidences",
                "PersonPropertyRelations",
                "Households",
                "Surveys",
                "Claims",
                "BuildingAssignments",
                "PropertyUnits",
                "Persons",
                "BuildingDocuments",
                "Buildings",
                "AuditLogs",
            ]

            for i, table in enumerate(tables_to_delete):
                if self._cancelled:
                    conn.rollback()
                    cur.close()
                    conn.close()
                    return None
                try:
                    cur.execute(f'DELETE FROM "{table}"')
                    pct = 20 + (i + 1) * 60 // len(tables_to_delete)
                    self.progress.emit(pct, tr("dialog.dev_reset.deleting_table").format(table=table))
                except Exception as e:
                    logger.warning(f"Could not delete from {table}: {e}")
                    conn.rollback()
                    conn.autocommit = False

            conn.commit()
            cur.close()
            conn.close()

            logger.info(f"Direct SQL reset complete: {counts}")
            self.progress.emit(85, tr("dialog.dev_reset.postgresql_success"))

            return {
                "local_claims": 0,
                "claims": counts.get("Claims", 0),
                "assignments": 0,
                "surveys": counts.get("Surveys", 0),
                "buildings": counts.get("Buildings", 0),
                "direct_sql": True,
            }
        except ImportError:
            logger.error("psycopg2 not installed")
            self.error.emit(tr("dialog.dev_reset.psycopg2_missing"))
            return None
        except Exception as e:
            logger.error(f"Direct SQL reset failed: {e}", exc_info=True)
            return None


class DevResetDialog(QDialog):
    """
    Developer-only dialog for resetting test data in the central database.

    Only create/show this dialog when Config.DEV_MODE is True.
    """

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self._worker = None
        self._db = db
        self.CONFIRM_WORD = tr("dialog.dev_reset.confirm_word")

        self.setWindowTitle(tr("dialog.dev_reset.window_title"))
        self.setModal(True)
        self.setFixedWidth(480)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(get_layout_direction())

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
        title = QLabel(tr("dialog.dev_reset.title"))
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
        delete_label = QLabel(tr("dialog.dev_reset.will_delete"))
        delete_label.setFont(create_font(size=10, weight=QFont.Medium))
        delete_label.setStyleSheet("color: #374151;")
        layout.addWidget(delete_label)

        self.cb_local_claims = QCheckBox(tr("dialog.dev_reset.cb_local_claims"))
        self.cb_claims = QCheckBox(tr("dialog.dev_reset.cb_claims"))
        self.cb_assignments = QCheckBox(tr("dialog.dev_reset.cb_assignments"))
        self.cb_surveys = QCheckBox(tr("dialog.dev_reset.cb_surveys"))
        self.cb_buildings = QCheckBox(tr("dialog.dev_reset.cb_buildings"))
        self._api_checkboxes = [self.cb_local_claims, self.cb_claims, self.cb_assignments, self.cb_surveys, self.cb_buildings]
        for cb in self._api_checkboxes:
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
        self.cb_local_claims.setToolTip(tr("dialog.dev_reset.cb_local_claims_tooltip"))

        # --- Direct SQL option ---
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #E5E7EB;")
        layout.addWidget(sep2)

        self.cb_direct_sql = QCheckBox(tr("dialog.dev_reset.cb_direct_sql"))
        self.cb_direct_sql.setChecked(False)
        self.cb_direct_sql.setFont(create_font(size=10, weight=QFont.Medium))
        self.cb_direct_sql.setStyleSheet("""
            QCheckBox { color: #DC2626; spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; }
            QCheckBox::indicator:unchecked {
                border: 1.5px solid #FCA5A5; background: white;
            }
            QCheckBox::indicator:checked {
                border: 1.5px solid #DC2626;
                background-color: #DC2626;
            }
        """)
        self.cb_direct_sql.setToolTip(tr("dialog.dev_reset.cb_direct_sql_tooltip"))
        self.cb_direct_sql.toggled.connect(self._on_direct_sql_toggled)
        layout.addWidget(self.cb_direct_sql)

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
        safe_title = QLabel(tr("dialog.dev_reset.will_not_delete"))
        safe_title.setFont(create_font(size=9, weight=QFont.Medium))
        safe_title.setStyleSheet("color: #166534;")
        safe_items = QLabel(tr("dialog.dev_reset.safe_items"))
        safe_items.setFont(create_font(size=9))
        safe_items.setStyleSheet("color: #166534;")
        safe_layout.addWidget(safe_title)
        safe_layout.addWidget(safe_items)
        layout.addWidget(safe_frame)

        # --- Confirmation input ---
        confirm_label = QLabel(tr("dialog.dev_reset.type_to_confirm").format(word=self.CONFIRM_WORD))
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

        self.progress_label = QLabel(tr("dialog.dev_reset.preparing"))
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

        self.cancel_btn = QPushButton(tr("button.cancel"))
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

        self.reset_btn = QPushButton(tr("dialog.dev_reset.delete_data"))
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

    def _on_direct_sql_toggled(self, checked: bool):
        """When direct SQL is checked, disable individual API checkboxes."""
        for cb in self._api_checkboxes:
            cb.setChecked(True)
            cb.setEnabled(not checked)

    def _on_confirm_changed(self, text: str):
        self.reset_btn.setEnabled(text.strip() == self.CONFIRM_WORD)

    def _start_reset(self):
        if not any([
            self.cb_local_claims.isChecked(),
            self.cb_claims.isChecked(),
            self.cb_assignments.isChecked(),
            self.cb_surveys.isChecked(),
            self.cb_buildings.isChecked(),
            self.cb_direct_sql.isChecked(),
        ]):
            return

        # Lock UI
        self.reset_btn.setEnabled(False)
        self.cancel_btn.setText(tr("dialog.dev_reset.stop"))
        self.confirm_input.setEnabled(False)
        self.cb_local_claims.setEnabled(False)
        self.cb_claims.setEnabled(False)
        self.cb_assignments.setEnabled(False)
        self.cb_surveys.setEnabled(False)
        self.cb_buildings.setEnabled(False)
        self.cb_direct_sql.setEnabled(False)
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
            "direct_sql": self.cb_direct_sql.isChecked(),
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
        method = tr("dialog.dev_reset.method_direct") if stats.get("direct_sql") else "API"
        if stats.get("local_claims"):
            lines.append(tr("dialog.dev_reset.result_local").format(count=stats['local_claims']))
        if stats.get("claims"):
            lines.append(tr("dialog.dev_reset.result_claims").format(count=stats['claims'], method=method))
        if stats.get("assignments"):
            lines.append(tr("dialog.dev_reset.result_assignments").format(count=stats['assignments']))
        if stats.get("surveys"):
            lines.append(tr("dialog.dev_reset.result_surveys").format(count=stats['surveys']))
        if stats.get("buildings"):
            lines.append(tr("dialog.dev_reset.result_buildings").format(count=stats['buildings']))
        if not lines:
            lines.append(tr("dialog.dev_reset.no_data_found"))

        summary = "\n".join(lines)
        self.progress_label.setText(tr("dialog.dev_reset.completed"))
        self.log_view.append(f"\n--- {tr('dialog.dev_reset.result_header')} ---\n{summary}")

        self.cancel_btn.setText(tr("button.close"))
        self.cancel_btn.setEnabled(True)
        logger.info(f"Dev reset completed: {stats}")

    def _on_error(self, message: str):
        self.progress_label.setText(tr("dialog.dev_reset.error_prefix").format(message=message))
        self.log_view.append(f"\n[{tr('dialog.dev_reset.error_label')}] {message}")
        self.cancel_btn.setText(tr("button.close"))
        self.cancel_btn.setEnabled(True)
        logger.error(f"Dev reset error: {message}")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
