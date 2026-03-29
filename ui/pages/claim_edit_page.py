# -*- coding: utf-8 -*-
"""Claim edit page with collapsible sections."""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QSpacerItem, QSizePolicy, QFrame,
    QComboBox, QTextEdit, QPushButton, QFileDialog, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.toast import Toast
from ui.components.dialogs.modification_reason_dialog import ModificationReasonDialog
from services.translation_manager import tr, get_layout_direction
from services.api_worker import ApiWorker
from utils.logger import get_logger

logger = get_logger(__name__)

def _get_claim_status_options():
    return [
        (1, tr("page.claim_edit.status_new")),
        (2, tr("page.claim_edit.status_in_review")),
        (3, tr("page.claim_edit.status_completed")),
        (4, tr("page.claim_edit.status_suspended")),
        (5, tr("page.claim_edit.status_draft")),
    ]

def _get_priority_options():
    return [
        (1, tr("page.claim_edit.priority_low")),
        (2, tr("page.claim_edit.priority_normal")),
        (3, tr("page.claim_edit.priority_high")),
        (4, tr("page.claim_edit.priority_urgent")),
    ]


class ClaimEditPage(QWidget):
    """Edit claim details with collapsible sections."""

    save_completed = pyqtSignal()
    back_requested = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n

        # Data holders
        self._claim_id = None
        self._claim_dto = {}
        self._person_dto = {}
        self._unit_dto = {}
        self._building_dto = {}
        self._survey_id = None
        self._evidences = []
        # (evidence_access_denied removed — evidenceIds loaded from claim DTO)
        self._user_role = None

        # Original values for change detection
        self._original_person = {}
        self._original_unit = {}
        self._original_claim = {}

        self._setup_ui()
    # UI Setup

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        main_layout.setSpacing(16)
        self.setStyleSheet(StyleManager.page_background())

        # Header
        main_layout.addWidget(self._create_header())

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}"
            + StyleManager.scrollbar()
        )

        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(16)

        # S04: Personal info
        # Personal info
        self._person_section = self._create_person_section()
        self._body_layout.addWidget(self._person_section)

        # S05: Property unit
        self._unit_section = self._create_unit_section()
        self._body_layout.addWidget(self._unit_section)

        # S06: Evidence documents
        self._evidence_section = self._create_evidence_section()
        self._body_layout.addWidget(self._evidence_section)

        # S07: Claim status
        self._status_section = self._create_status_section()
        self._body_layout.addWidget(self._status_section)

        self._body_layout.addStretch()

        # Bottom action bar
        self._body_layout.addWidget(self._create_action_bar())

        scroll.setWidget(body)
        main_layout.addWidget(scroll)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(PageDimensions.PAGE_HEADER_HEIGHT)
        header.setStyleSheet(f"background-color: {Colors.BACKGROUND}; border: none;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._title_label = QLabel(tr("page.claim_edit.title"))
        self._title_label.setFont(create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold))
        self._title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; border: none;")
        layout.addWidget(self._title_label)

        layout.addStretch()
        return header
    # S04: Personal Information Section

    def _create_person_section(self) -> QFrame:
        section = self._create_section_frame(tr("page.claim_edit.section_personal"))

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self._person_first_name = self._add_field(grid, 0, 0, tr("page.claim_edit.first_name"))
        self._person_father_name = self._add_field(grid, 0, 1, tr("page.claim_edit.father_name"))
        self._person_family_name = self._add_field(grid, 1, 0, tr("page.claim_edit.family_name"))
        self._person_mother_name = self._add_field(grid, 1, 1, tr("page.claim_edit.mother_name"))
        self._person_national_id = self._add_field(grid, 2, 0, tr("page.claim_edit.national_id"))
        self._person_gender = self._add_combo_field(grid, 2, 1, tr("page.claim_edit.gender"),
                                                     [(1, tr("page.claim_edit.gender_male")), (2, tr("page.claim_edit.gender_female"))])
        self._person_dob = self._add_field(grid, 3, 0, tr("page.claim_edit.date_of_birth"))

        section.layout().addLayout(grid)
        return section
    # S05: Property Unit Section

    def _create_unit_section(self) -> QFrame:
        section = self._create_section_frame(tr("page.claim_edit.section_property"))

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self._unit_floor = self._add_field(grid, 0, 0, tr("page.claim_edit.floor"))
        self._unit_type = self._add_combo_field(grid, 0, 1, tr("page.claim_edit.unit_type"),
                                                 [(1, tr("page.claim_edit.unit_apartment")),
                                                  (2, tr("page.claim_edit.unit_shop")),
                                                  (3, tr("page.claim_edit.unit_office")),
                                                  (4, tr("page.claim_edit.unit_warehouse")),
                                                  (5, tr("page.claim_edit.unit_other"))])
        self._unit_status = self._add_combo_field(grid, 1, 0, tr("page.claim_edit.unit_status"),
                                                   [(1, tr("page.claim_edit.unit_occupied")),
                                                    (2, tr("page.claim_edit.unit_vacant")),
                                                    (3, tr("page.claim_edit.unit_damaged")),
                                                    (4, tr("page.claim_edit.unit_destroyed"))])
        self._unit_area = self._add_field(grid, 1, 1, tr("page.claim_edit.area_sqm"))
        self._unit_rooms = self._add_field(grid, 2, 0, tr("page.claim_edit.num_rooms"))
        self._unit_description = self._add_field(grid, 2, 1, tr("page.claim_edit.description"))

        section.layout().addLayout(grid)
        return section
    # S06: Evidence Documents Section

    def _create_evidence_section(self) -> QFrame:
        section = self._create_section_frame(tr("page.claim_edit.section_documents"))

        # Access denied message (hidden by default)
        self._evidence_denied_label = QLabel(
            tr("page.claim_edit.evidence_access_denied"))
        self._evidence_denied_label.setWordWrap(True)
        self._evidence_denied_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                padding: 12px;
                background-color: #FFF8E1;
                border-radius: 6px;
            }}
        """)
        self._evidence_denied_label.setVisible(False)
        section.layout().addWidget(self._evidence_denied_label)

        self._evidence_list_layout = QVBoxLayout()
        self._evidence_list_layout.setSpacing(8)
        section.layout().addLayout(self._evidence_list_layout)

        # Add button
        self._add_evidence_btn = QPushButton(tr("page.claim_edit.add_document"))
        self._add_evidence_btn.setCursor(Qt.PointingHandCursor)
        self._add_evidence_btn.setFixedHeight(36)
        self._add_evidence_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: 1px dashed {Colors.PRIMARY_BLUE};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #F0F7FF;
            }}
        """)
        self._add_evidence_btn.clicked.connect(self._on_add_evidence)
        section.layout().addWidget(self._add_evidence_btn)

        return section
    # S07: Status & Priority Section

    def _create_status_section(self) -> QFrame:
        section = self._create_section_frame(tr("page.claim_edit.section_status"))

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self._claim_status_combo = self._add_combo_field(
            grid, 0, 0, tr("page.claim_edit.claim_status"), _get_claim_status_options())
        self._claim_priority_combo = self._add_combo_field(
            grid, 0, 1, tr("page.claim_edit.priority"), _get_priority_options())

        # Notes fields
        self._notes_label = QLabel(tr("page.claim_edit.processing_notes"))
        self._notes_label.setStyleSheet(self._label_style())
        grid.addWidget(self._notes_label, 1, 0, 1, 2)

        self._processing_notes = QTextEdit()
        self._processing_notes.setMaximumHeight(80)
        self._processing_notes.setStyleSheet(self._textarea_style())
        grid.addWidget(self._processing_notes, 2, 0, 1, 2)

        self._remarks_label = QLabel(tr("page.claim_edit.public_remarks"))
        self._remarks_label.setStyleSheet(self._label_style())
        grid.addWidget(self._remarks_label, 3, 0, 1, 2)

        self._public_remarks = QTextEdit()
        self._public_remarks.setMaximumHeight(80)
        self._public_remarks.setStyleSheet(self._textarea_style())
        grid.addWidget(self._public_remarks, 4, 0, 1, 2)

        section.layout().addLayout(grid)
        return section
    # Action Bar

    def _create_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)
        layout.addStretch()

        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #F8FAFC; }}
        """)
        cancel_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr("page.claim_edit.save_changes"))
        save_btn.setFixedSize(160, 40)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #2A7BC8; }}
        """)
        save_btn.clicked.connect(self._on_save)
        layout.addWidget(save_btn)

        return bar
    # Data Loading

    def refresh(self, data=None):
        """Load claim data for editing. Called from navigate_to()."""
        if not data:
            return
        if isinstance(data, str):
            claim_id = data
            hint_survey_id = None
        else:
            claim_id = data.get("claim_id")
            hint_survey_id = data.get("survey_id")
        if not claim_id:
            return

        self._claim_id = claim_id
        self._title_label.setText(f"{tr('page.claim_edit.title')} — {claim_id[:8]}...")

        try:
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController()
            result = ctrl.get_claim_full_detail(claim_id, hint_survey_id=hint_survey_id)

            if not result.success:
                Toast.show_toast(self, f"{tr('page.claim_edit.error_prefix')}: {result.message}", Toast.ERROR)
                return

            detail = result.data
            self._claim_dto = detail.get("claim") or {}
            self._person_dto = detail.get("person") or {}
            self._unit_dto = detail.get("unit") or {}
            self._building_dto = detail.get("building") or {}
            self._survey_id = detail.get("survey_id")
            self._evidences = detail.get("evidences") or []
            # evidence_access_denied no longer needed — evidences loaded via claim DTO

            logger.debug(f"claim keys: {list(self._claim_dto.keys())}")
            logger.debug(f"person keys: {list(self._person_dto.keys())}")
            logger.debug(f"unit keys: {list(self._unit_dto.keys())}")
            logger.debug(f"survey_id={self._survey_id}, evidences={len(self._evidences)}")

            self._populate_fields()
            self._snapshot_originals()

        except Exception as e:
            logger.error(f"Failed to load claim {claim_id}: {e}", exc_info=True)
            Toast.show_toast(self, f"{tr('page.claim_edit.error_loading_claim')}: {e}", Toast.ERROR)

    def _populate_fields(self):
        """Fill all form fields from loaded DTOs."""
        # Person (S04)
        p = self._person_dto
        self._person_first_name.setText(
            p.get("firstNameArabic") or p.get("firstName") or p.get("first_name") or "")
        self._person_father_name.setText(
            p.get("fatherNameArabic") or p.get("fatherName") or p.get("father_name") or "")
        self._person_family_name.setText(
            p.get("familyNameArabic") or p.get("familyName") or p.get("family_name") or "")
        self._person_mother_name.setText(
            p.get("motherNameArabic") or p.get("motherName") or p.get("mother_name") or "")
        self._person_national_id.setText(
            p.get("nationalId") or p.get("national_id") or "")
        self._set_combo_value(self._person_gender,
                              p.get("gender") or p.get("genderId"))
        dob = p.get("dateOfBirth") or p.get("date_of_birth") or ""
        self._person_dob.setText(str(dob)[:10])

        # Unit (S05)
        u = self._unit_dto
        floor_val = u.get("floorNumber") or u.get("floor_number") or u.get("floor") or ""
        self._unit_floor.setText(str(floor_val) if floor_val != "" else "")
        self._set_combo_value(self._unit_type,
                              u.get("unitType") or u.get("unit_type") or u.get("type"))
        self._set_combo_value(self._unit_status,
                              u.get("status") or u.get("unitStatus") or u.get("unit_status"))
        area = u.get("areaSquareMeters") or u.get("areaSqm") or u.get("area") or ""
        self._unit_area.setText(str(area) if area else "")
        rooms = u.get("numberOfRooms") or u.get("number_of_rooms") or u.get("rooms") or ""
        self._unit_rooms.setText(str(rooms) if rooms else "")
        self._unit_description.setText(u.get("description") or "")

        # Claim (S07)
        c = self._claim_dto
        self._set_combo_value(self._claim_status_combo,
                              c.get("status") or c.get("caseStatus") or c.get("case_status"))
        self._set_combo_value(self._claim_priority_combo,
                              c.get("priority") or c.get("priorityId"))
        self._processing_notes.setPlainText(
            c.get("processingNotes") or c.get("processing_notes") or "")
        self._public_remarks.setPlainText(
            c.get("publicRemarks") or c.get("public_remarks") or "")

        # Evidence list (S06)
        self._refresh_evidence_list()

    def _snapshot_originals(self):
        """Save current field values for change detection."""
        self._original_person = {
            "first_name": self._person_first_name.text(),
            "father_name": self._person_father_name.text(),
            "last_name": self._person_family_name.text(),
            "mother_name": self._person_mother_name.text(),
            "national_id": self._person_national_id.text(),
            "gender": self._person_gender.currentData(),
            "birth_date": self._person_dob.text(),
        }
        self._original_unit = {
            "floorNumber": self._unit_floor.text(),
            "unitType": self._unit_type.currentData(),
            "status": self._unit_status.currentData(),
            "areaSquareMeters": self._unit_area.text(),
            "numberOfRooms": self._unit_rooms.text(),
            "description": self._unit_description.text(),
        }
        self._original_claim = {
            "caseStatus": self._claim_status_combo.currentData(),
            "priority": self._claim_priority_combo.currentData(),
            "processingNotes": self._processing_notes.toPlainText(),
            "publicRemarks": self._public_remarks.toPlainText(),
        }
    # Evidence Management (S06)

    def _refresh_evidence_list(self):
        """Rebuild evidence list from self._evidences."""
        # Clear existing
        while self._evidence_list_layout.count():
            item = self._evidence_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._evidence_denied_label.setVisible(False)
        self._add_evidence_btn.setEnabled(True)
        self._add_evidence_btn.setVisible(True)

        if not self._evidences:
            lbl = QLabel(tr("page.claim_edit.no_documents"))
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; border: none;")
            lbl.setAlignment(Qt.AlignCenter)
            self._evidence_list_layout.addWidget(lbl)
            return

        for ev in self._evidences:
            row = self._create_evidence_row(ev)
            self._evidence_list_layout.addWidget(row)

    def _create_evidence_row(self, ev: dict) -> QFrame:
        row = QFrame()
        row.setFixedHeight(40)
        row.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }}
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        desc = ev.get("description") or ev.get("fileName") or tr("page.claim_edit.document")
        ev_type = ev.get("evidenceType") or ev.get("type") or ""
        type_text = tr("page.claim_edit.ev_identification") if "identification" in str(ev_type).lower() else tr("page.claim_edit.ev_tenure")

        type_badge = QLabel(type_text)
        type_badge.setFixedWidth(50)
        type_badge.setAlignment(Qt.AlignCenter)
        type_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #EFF6FF;
                color: {Colors.PRIMARY_BLUE};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 6px;
                border: none;
            }}
        """)
        layout.addWidget(type_badge)

        name_label = QLabel(desc)
        name_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 12px; border: none;")
        layout.addWidget(name_label)

        layout.addStretch()

        del_btn = QPushButton(tr("action.delete"))
        del_btn.setFixedSize(60, 28)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #EF4444;
                border: 1px solid #EF4444;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
            }
        """)
        evidence_id = ev.get("id") or ev.get("evidenceId") or ""
        del_btn.clicked.connect(lambda checked, eid=evidence_id: self._on_delete_evidence(eid))
        layout.addWidget(del_btn)

        return row

    def _on_add_evidence(self):
        if not self._survey_id:
            Toast.show_toast(self, tr("page.claim_edit.no_survey_id"), Toast.WARNING)
            return

        from PyQt5.QtWidgets import QInputDialog
        ev_type, ok = QInputDialog.getItem(
            self, tr("page.claim_edit.document_type"), tr("page.claim_edit.choose_document_type"),
            [tr("page.claim_edit.ev_identification_option"), tr("page.claim_edit.ev_tenure_option")], 0, False
        )
        if not ok:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("page.claim_edit.choose_document"), "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.doc *.docx);;All Files (*)"
        )
        if not file_path:
            return

        try:
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController()

            if "Tenure" in ev_type:
                relation_id = self._get_tenure_relation_id()
                if not relation_id:
                    Toast.show_toast(self, tr("page.claim_edit.no_tenure_relation_id"), Toast.WARNING)
                    return
                result = ctrl.add_tenure_evidence(
                    self._survey_id, relation_id, file_path,
                    description=os.path.basename(file_path))
            else:
                person_id = self._person_dto.get("id") or self._claim_dto.get("primaryClaimantId")
                if not person_id:
                    Toast.show_toast(self, tr("page.claim_edit.no_linked_person"), Toast.WARNING)
                    return
                result = ctrl.add_identification_evidence(
                    self._survey_id, person_id, file_path,
                    description=os.path.basename(file_path))

            if result.success:
                Toast.show_toast(self, tr("page.claim_edit.document_added"), Toast.SUCCESS)
                self._reload_evidences()
            else:
                Toast.show_toast(self, f"{tr('page.claim_edit.error_prefix')}: {result.message}", Toast.ERROR)
        except Exception as e:
            Toast.show_toast(self, f"{tr('page.claim_edit.error_prefix')}: {e}", Toast.ERROR)

    def _get_tenure_relation_id(self) -> str:
        """Extract relation_id from loaded tenure evidences."""
        for ev in self._evidences:
            if "tenure" in str(ev.get("evidenceType", "")).lower():
                rid = ev.get("relationId") or ev.get("relation_id")
                if rid:
                    return str(rid)
        return ""

    def configure_for_role(self, role: str):
        self._user_role = role

    def _on_delete_evidence(self, evidence_id: str):
        if self._user_role and self._user_role not in ("admin", "data_manager"):
            return
        if not self._survey_id or not evidence_id:
            return
        try:
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController()
            result = ctrl.delete_evidence(self._survey_id, evidence_id)
            if result.success:
                Toast.show_toast(self, tr("page.claim_edit.document_deleted"), Toast.SUCCESS)
                self._reload_evidences()
            else:
                Toast.show_toast(self, f"{tr('page.claim_edit.error_prefix')}: {result.message}", Toast.ERROR)
        except Exception as e:
            Toast.show_toast(self, f"{tr('page.claim_edit.error_prefix')}: {e}", Toast.ERROR)

    def _reload_evidences(self):
        """Refresh evidence list from claim DTO evidenceIds."""
        if not self._claim_id:
            return

        self._reload_evidences_worker = ApiWorker(
            self._fetch_claim_evidences, self._claim_id
        )
        self._reload_evidences_worker.finished.connect(self._on_evidences_reloaded)
        self._reload_evidences_worker.error.connect(self._on_evidences_reload_error)
        self._reload_evidences_worker.start()

    @staticmethod
    def _fetch_claim_evidences(claim_id):
        """Fetch claim and all its evidences (runs in worker thread)."""
        from services.api_client import get_api_client
        api = get_api_client()
        claim = api.get_claim_by_id(claim_id)
        evidence_ids = claim.get("evidenceIds") or []
        evidences = []
        for eid in evidence_ids:
            try:
                ev = api.get_evidence_by_id(eid)
                if ev:
                    evidences.append(ev)
            except Exception:
                pass
        return evidences

    def _on_evidences_reloaded(self, evidences):
        """Handle reloaded evidences on main thread."""
        self._evidences = evidences
        self._refresh_evidence_list()

    def _on_evidences_reload_error(self, error_msg):
        """Handle evidence reload error."""
        logger.warning(f"Failed to reload evidences: {error_msg}")
        self._refresh_evidence_list()
    # Save (S08-S10)

    def _on_save(self):
        """Collect changes, show reason dialog, save via API."""
        changes = self._collect_changes()

        if not changes:
            Toast.show_toast(self, tr("page.claim_edit.no_changes"), Toast.INFO)
            return

        # S08: Modification reason dialog
        summary = self._build_change_summary(changes)
        dialog = ModificationReasonDialog(summary, parent=self)
        if dialog.exec_() != ModificationReasonDialog.Accepted:
            return
        reason = dialog.get_reason()

        # S09-S10: Save each section via API
        try:
            from controllers.claim_controller import ClaimController
            ctrl = ClaimController()
            errors = []

            # Save person changes (S04)
            if changes.get("person"):
                person_id = self._person_dto.get("id") or self._claim_dto.get("primaryClaimantId")
                if person_id:
                    result = ctrl.update_person(person_id, changes["person"])
                    if not result.success:
                        errors.append(f"{tr('page.claim_edit.person_label')}: {result.message}")

            # Save unit changes (S05) — include required buildingId for PUT
            if changes.get("unit"):
                unit_id = self._claim_dto.get("propertyUnitId")
                if unit_id:
                    unit_payload = dict(changes["unit"])
                    bld_id = (self._building_dto.get("id")
                              or self._building_dto.get("buildingId"))
                    if bld_id:
                        unit_payload["buildingId"] = bld_id
                    result = ctrl.update_property_unit(unit_id, unit_payload)
                    if not result.success:
                        errors.append(f"{tr('page.claim_edit.unit_label')}: {result.message}")

            # Save claim changes (S07)
            if changes.get("claim"):
                result = ctrl.update_claim(self._claim_id, changes["claim"], reason)
                if not result.success:
                    errors.append(f"{tr('page.claim_edit.claim_label')}: {result.message}")
            elif reason:
                # Even if no claim fields changed, record the reason
                result = ctrl.update_claim(self._claim_id, {}, reason)
                if not result.success:
                    errors.append(f"{tr('page.claim_edit.reason_label')}: {result.message}")

            if errors:
                Toast.show_toast(self, f"{tr('page.claim_edit.errors_prefix')}: {'; '.join(errors)}", Toast.WARNING)
            else:
                Toast.show_toast(self, tr("page.claim_edit.claim_updated"), Toast.SUCCESS)
                self._snapshot_originals()
                self.save_completed.emit()

        except Exception as e:
            logger.error(f"Save failed: {e}", exc_info=True)
            Toast.show_toast(self, f"{tr('page.claim_edit.error_saving')}: {e}", Toast.ERROR)

    def _collect_changes(self) -> dict:
        """Compare current fields to originals, return only changed sections."""
        changes = {}

        # Person changes — keys match api_client.update_person() snake_case expectations
        person_now = {
            "first_name": self._person_first_name.text(),
            "father_name": self._person_father_name.text(),
            "last_name": self._person_family_name.text(),
            "mother_name": self._person_mother_name.text(),
            "national_id": self._person_national_id.text(),
            "gender": self._person_gender.currentData(),
            "birth_date": self._person_dob.text(),
        }
        person_diff = {k: v for k, v in person_now.items()
                       if v != self._original_person.get(k)}
        if person_diff:
            changes["person"] = person_diff

        # Unit changes
        unit_now = {
            "floorNumber": self._safe_int(self._unit_floor.text()),
            "unitType": self._unit_type.currentData(),
            "status": self._unit_status.currentData(),
            "areaSquareMeters": self._safe_float(self._unit_area.text()),
            "numberOfRooms": self._safe_int(self._unit_rooms.text()),
            "description": self._unit_description.text(),
        }
        unit_diff = {}
        for k, v in unit_now.items():
            orig = self._original_unit.get(k)
            if k in ("floorNumber", "numberOfRooms"):
                orig = self._safe_int(orig)
            elif k == "areaSquareMeters":
                orig = self._safe_float(orig)
            if v != orig:
                unit_diff[k] = v
        if unit_diff:
            changes["unit"] = unit_diff

        # Claim changes
        claim_now = {
            "caseStatus": self._claim_status_combo.currentData(),
            "priority": self._claim_priority_combo.currentData(),
            "processingNotes": self._processing_notes.toPlainText(),
            "publicRemarks": self._public_remarks.toPlainText(),
        }
        claim_diff = {k: v for k, v in claim_now.items()
                      if v != self._original_claim.get(k)}
        if claim_diff:
            changes["claim"] = claim_diff

        return changes

    def _build_change_summary(self, changes: dict) -> list:
        """Build human-readable list of changes for the reason dialog."""
        _person_labels = {
            "first_name": tr("page.claim_edit.first_name"),
            "father_name": tr("page.claim_edit.father_name"),
            "last_name": tr("page.claim_edit.family_name"),
            "mother_name": tr("page.claim_edit.mother_name"),
            "national_id": tr("page.claim_edit.national_id"),
            "gender": tr("page.claim_edit.gender"),
            "birth_date": tr("page.claim_edit.date_of_birth"),
        }
        summary = []
        if "person" in changes:
            fields = ", ".join(_person_labels.get(k, k) for k in changes["person"])
            summary.append(f"{tr('page.claim_edit.change_personal')}: {fields}")
        if "unit" in changes:
            fields = ", ".join(changes["unit"].keys())
            summary.append(f"{tr('page.claim_edit.change_property')}: {fields}")
        if "claim" in changes:
            fields = ", ".join(changes["claim"].keys())
            summary.append(f"{tr('page.claim_edit.change_claim')}: {fields}")
        return summary
    # Helpers

    def _create_section_frame(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setLayoutDirection(get_layout_direction())
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.SURFACE};
                border: none;
                border-radius: 12px;
            }}
        """)
        self._add_shadow(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=14, weight=QFont.DemiBold))
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; border: none;")
        layout.addWidget(title_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"background-color: {Colors.BORDER_DEFAULT}; border: none;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        return frame

    @staticmethod
    def _add_shadow(widget):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 25))
        widget.setGraphicsEffect(shadow)

    def _add_field(self, grid: QGridLayout, row: int, col: int,
                   label_text: str) -> QLineEdit:
        container = QWidget()
        container.setStyleSheet("border: none;")
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(self._label_style())
        v.addWidget(lbl)

        inp = QLineEdit()
        inp.setStyleSheet(StyleManager.form_input())
        inp.setFixedHeight(43)
        v.addWidget(inp)

        grid.addWidget(container, row, col)
        return inp

    def _add_combo_field(self, grid: QGridLayout, row: int, col: int,
                         label_text: str, options: list) -> QComboBox:
        container = QWidget()
        container.setStyleSheet("border: none;")
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(self._label_style())
        v.addWidget(lbl)

        combo = QComboBox()
        for val, text in options:
            combo.addItem(text, val)
        combo.setStyleSheet(StyleManager.form_input())
        combo.setFixedHeight(43)
        v.addWidget(combo)

        grid.addWidget(container, row, col)
        return combo

    def _set_combo_value(self, combo: QComboBox, value):
        if value is None:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    @staticmethod
    def _label_style() -> str:
        return f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; font-weight: 600; border: none;"

    @staticmethod
    def _textarea_style() -> str:
        return f"""
            QTextEdit {{
                background-color: #F8FAFC;
                border: 1px solid #E0E6ED;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                color: #333;
            }}
            QTextEdit:focus {{
                border: 1px solid #2D9CDB;
                background-color: white;
            }}
        """

    @staticmethod
    def _safe_int(val) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_float(val) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def update_language(self, is_arabic=True):
        self._title_label.setText(tr("page.claim_edit.title"))
        self._notes_label.setText(tr("page.claim_edit.processing_notes"))
        self._remarks_label.setText(tr("page.claim_edit.public_remarks"))
        self._add_evidence_btn.setText(tr("page.claim_edit.add_document"))
        self._evidence_denied_label.setText(tr("page.claim_edit.evidence_access_denied"))
