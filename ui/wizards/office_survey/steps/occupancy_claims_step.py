# -*- coding: utf-8 -*-
"""
Occupancy Claims Step - Merged Person + Relation step.

Replaces the old PersonStep (Step 4) and RelationStep (Step 5).
Allows user to add/view/delete persons with their relation data
using the 3-tab PersonDialog.
"""

from typing import Dict, Any, List
import uuid

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget,
    QDialog, QGridLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QColor

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.dialogs.person_dialog import PersonDialog

from app.config import Config
from services.api_client import get_api_client
from utils.logger import get_logger
from ui.error_handler import ErrorHandler
from ui.font_utils import FontManager, create_font
from ui.design_system import Colors, ScreenScale
from ui.wizards.office_survey.wizard_styles import (
    STEP_CARD_STYLE, IN_CARD_ACTION_STYLE,
    make_step_card, make_icon_header, PERSON_CARD_STYLE,
    EMPTY_STATE_ICON_STYLE,
)


def _is_owner_relation(relation_type) -> bool:
    """Check if a relation type indicates ownership (owner or heir).
    Handles both integer codes (from Vocabularies) and string values (legacy/API)."""
    if relation_type is None:
        return False
    if isinstance(relation_type, int):
        return relation_type in (1, 5)
    if isinstance(relation_type, str):
        return relation_type.lower() in ('owner', 'co_owner', 'coowner', 'heir')
    return False
from services.translation_manager import tr, get_layout_direction
from services.display_mappings import get_relation_type_display, get_relationship_to_head_display
from services.error_mapper import map_exception
from ui.components.toast import Toast

logger = get_logger(__name__)


class OccupancyClaimsStep(BaseStep):
    """Step 4: Occupancy Claims - Person registration with relation data."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._api_service = get_api_client()

    def setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"background-color: {Colors.BACKGROUND};")

        layout = self.main_layout
        layout.setContentsMargins(0, 15, 0, 16)
        layout.setSpacing(15)

        persons_frame = make_step_card()
        persons_frame.setLayoutDirection(get_layout_direction())
        pf_layout = QVBoxLayout(persons_frame)
        pf_layout.setContentsMargins(20, 20, 20, 20)
        pf_layout.setSpacing(14)

        header_layout, header_title, header_subtitle = make_icon_header(
            tr("wizard.occupancy_claims.title"),
            tr("wizard.occupancy_claims.subtitle"),
            "user",
        )
        self._header_title = header_title
        self._header_subtitle = header_subtitle

        self._add_person_btn = QPushButton(tr("wizard.occupancy_claims.add_person"))
        self._add_person_btn.setLayoutDirection(get_layout_direction())
        self._add_person_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._add_person_btn.setStyleSheet(IN_CARD_ACTION_STYLE)
        self._add_person_btn.clicked.connect(self._add_person)
        header_layout.addWidget(self._add_person_btn)
        pf_layout.addLayout(header_layout)
        pf_layout.addSpacing(8)

        self._persons_grid_widget = QWidget()
        self._persons_grid_widget.setStyleSheet("background: transparent;")
        self.persons_grid = QGridLayout(self._persons_grid_widget)
        self.persons_grid.setSpacing(ScreenScale.w(12))
        self.persons_grid.setContentsMargins(0, 0, 0, 0)
        for c in range(3):
            self.persons_grid.setColumnStretch(c, 1)

        self._empty_state = self._create_empty_state()
        pf_layout.addWidget(self._empty_state)
        pf_layout.addWidget(self._persons_grid_widget, 1)
        pf_layout.addStretch(0)

        layout.addWidget(persons_frame, 1)

    def _create_empty_state(self) -> QWidget:
        """Create empty state widget shown when no persons are added."""
        from ui.components.icon import Icon
        from PyQt5.QtGui import QPixmap
        import os

        container = QWidget()
        container.setStyleSheet(f"background-color: transparent;")

        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(0, 40, 0, 40)

        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(15)

        # Icon with orange circle background (same as claim_step)
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(70), ScreenScale.h(70))
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet(EMPTY_STATE_ICON_STYLE)

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "assets", "images", "tdesign_no-result.png"
        )
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_container.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            no_result_pixmap = Icon.load_pixmap("tdesign_no-result", size=40)
            if no_result_pixmap and not no_result_pixmap.isNull():
                icon_container.setPixmap(no_result_pixmap)
            else:
                icon_container.setText("!")
                icon_container.setStyleSheet(icon_container.styleSheet() + "font-size: 28px; color: #1a1a1a;")

        # Title
        title_label = QLabel(tr("wizard.occupancy_claims.empty_title"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_TITLE, weight=FontManager.WEIGHT_BOLD))
        title_label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        # Description
        desc_label = QLabel(tr("wizard.occupancy_claims.empty_desc"))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFont(create_font(size=FontManager.WIZARD_EMPTY_DESC, weight=FontManager.WEIGHT_REGULAR))
        desc_label.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        self._empty_title_label = title_label
        self._empty_desc_label = desc_label

        center_layout.addWidget(icon_container, alignment=Qt.AlignCenter)
        center_layout.addWidget(title_label)
        center_layout.addWidget(desc_label)

        main_layout.addWidget(center_widget)

        return container

    @staticmethod
    def _thin_hline() -> QFrame:
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet("background-color: #E2EAF2; border: none;")
        return d

    def _get_context_ids(self):
        """Get survey_id, household_id, unit_id, and auth_token from context."""
        auth_token = None
        main_window = self.window()
        if main_window and hasattr(main_window, '_api_token'):
            auth_token = main_window._api_token

        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")

        unit_id = None
        if self.context.unit:
            unit_id = getattr(self.context.unit, 'unit_uuid', None)
        elif self.context.new_unit_data:
            unit_id = self.context.new_unit_data.get('unit_uuid')

        return auth_token, survey_id, household_id, unit_id

    def _add_person(self):
        """Open PersonDialog directly to add a new person."""
        auth_token, survey_id, household_id, unit_id = self._get_context_ids()

        dialog = PersonDialog(
            person_data=None,
            existing_persons=self.context.get_all_persons_for_nid_check(),
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id,
            household_id=household_id,
            unit_id=unit_id
        )

        if dialog.exec_() == QDialog.Accepted:
            person_data = dialog.get_person_data()
            api_id = dialog.get_api_person_id()
            if api_id:
                person_data['person_id'] = api_id
            elif not person_data.get('person_id'):
                person_data['person_id'] = str(uuid.uuid4())
            rel_id = dialog.get_api_relation_id()
            if rel_id:
                person_data['_relation_id'] = rel_id
            rel_files = dialog.get_relation_uploaded_files()
            if rel_files:
                person_data['_relation_uploaded_files'] = rel_files
            self.context.persons.append(person_data)
            self.context.finalize_response = None
            self._refresh_persons_list()
            logger.info(f"Person added: {person_data['first_name']} {person_data['last_name']} (id={person_data['person_id']})")

    def _view_person(self, person_id: str):
        """Show PersonDialog to view/edit a person."""
        person_data = None
        person_index = None

        for i, person in enumerate(self.context.persons):
            if person['person_id'] == person_id:
                person_data = person
                person_index = i
                break

        if not person_data:
            return

        auth_token, survey_id, household_id, unit_id = self._get_context_ids()

        is_applicant = person_data.get('_is_applicant', False) or person_data.get('_is_contact_person', False)
        if not is_applicant:
            contact_person_id = self.context.get_data('contact_person_id')
            if contact_person_id and person_data.get('person_id') == contact_person_id:
                is_applicant = True
        has_relation = bool(
            person_data.get('person_role')
            or person_data.get('relationship_type')
            or person_data.get('relation_data', {}).get('rel_type')
            or person_data.get('_relation_id')
        )

        if is_applicant:
            initial_tab = 0
            open_as_existing = False
        else:
            initial_tab = 2 if has_relation else 1
            # No relation yet → open in existing_person_mode so link_person_to_unit() is called
            open_as_existing = not has_relation

        person_data_copy = dict(person_data)
        if is_applicant and self.context.applicant:
            a = self.context.applicant
            # PersonDialog expects 'first_name' key; applicant context stores 'first_name_ar'
            for person_key, applicant_key in (
                ('first_name',  'first_name_ar'),
                ('father_name', 'father_name_ar'),
                ('mother_name', 'mother_name_ar'),
                ('last_name',   'last_name_ar'),
            ):
                if not person_data_copy.get(person_key) and a.get(applicant_key):
                    person_data_copy[person_key] = a[applicant_key]
            id_photos = a.get('id_photo_paths', [])
            if id_photos:
                person_data_copy['_uploaded_files'] = id_photos
            else:
                id_ev = a.get('id_photo_evidences', [])
                if id_ev:
                    person_data_copy['_id_photo_evidences'] = id_ev

        is_finalized = self.context.status == "finalized"

        dialog = PersonDialog(
            person_data=person_data_copy,
            existing_persons=self.context.get_all_persons_for_nid_check(),
            parent=self,
            auth_token=auth_token,
            survey_id=survey_id,
            household_id=household_id,
            unit_id=unit_id,
            existing_person_mode=open_as_existing,
            initial_tab=initial_tab,
            read_only=is_finalized,
        )

        if dialog.exec_() == QDialog.Accepted and not is_finalized:
            updated_data = dialog.get_person_data()
            updated_data['person_id'] = person_id

            rel_files = dialog.get_relation_uploaded_files()
            if rel_files:
                updated_data['_relation_uploaded_files'] = rel_files

            if open_as_existing:
                # PersonDialog handled link_person_to_unit() + evidence upload internally
                rel_id = dialog.get_api_relation_id()
                if rel_id:
                    updated_data['_relation_id'] = rel_id
            else:
                if person_id:
                    try:
                        self._set_auth_token()
                        if is_applicant and survey_id:
                            self._api_service.update_contact_person(
                                survey_id, person_id, updated_data)
                        elif survey_id and household_id:
                            self._api_service.update_person_in_survey(
                                survey_id, household_id, person_id, updated_data)
                        else:
                            logger.warning(f"Missing survey_id or household_id for person {person_id}")
                        logger.info(f"Person {person_id} updated via API")
                        relation_id = updated_data.get('_relation_id') or person_data.get('_relation_id')
                        if relation_id and survey_id:
                            try:
                                self._api_service.update_relation(survey_id, relation_id, updated_data)
                                logger.info(f"Relation {relation_id} updated via API")
                            except Exception as e:
                                logger.warning(f"Failed to update relation {relation_id}: {e}")
                        elif not relation_id and survey_id and unit_id:
                            rel_type = updated_data.get('relation_data', {}).get('rel_type')
                            if rel_type:
                                relation_data = dict(updated_data.get('relation_data', {}))
                                relation_data['person_id'] = person_id
                                relation_data['rel_type'] = rel_type
                                try:
                                    response = self._api_service.link_person_to_unit(
                                        survey_id, unit_id, relation_data)
                                    new_rel_id = (
                                        response.get('id') or response.get('relationId') or
                                        response.get('personPropertyRelationId') or '')
                                    if new_rel_id:
                                        updated_data['_relation_id'] = new_rel_id
                                        logger.info(f"Created relation for person {person_id}: {new_rel_id}")
                                        tenure_files = updated_data.get('_relation_uploaded_files', [])
                                        for f_entry in tenure_files:
                                            if f_entry.get('evidence_id'):
                                                continue
                                            f_path = f_entry.get('path', '')
                                            if not f_path:
                                                continue
                                            try:
                                                resp = self._api_service.upload_relation_document(
                                                    survey_id=survey_id,
                                                    relation_id=new_rel_id,
                                                    file_path=f_path,
                                                    issue_date=f_entry.get('issue_date', ''),
                                                    file_hash=f_entry.get('hash', ''))
                                                eid = (resp.get('id') or resp.get('evidenceId') or '')
                                                if eid:
                                                    f_entry['evidence_id'] = eid
                                                logger.info(f"Tenure file uploaded for relation {new_rel_id}: {f_path}")
                                            except Exception as ue:
                                                logger.error(f"Failed to upload tenure file {f_path}: {ue}")
                                        # Link existing selected documents to the new relation
                                        for f_entry in tenure_files:
                                            if not f_entry.get('_selected_existing') or not f_entry.get('evidence_id'):
                                                continue
                                            try:
                                                self._api_service.link_evidence_to_relation(
                                                    survey_id, f_entry['evidence_id'], new_rel_id
                                                )
                                                logger.info(f"Existing evidence {f_entry['evidence_id']} linked to relation {new_rel_id}")
                                            except Exception as le:
                                                logger.error(f"Failed to link existing evidence: {le}")
                                                Toast.show_toast(self, tr("wizard.person_dialog.link_existing_doc_failed"), Toast.ERROR)
                                except Exception as e:
                                    logger.error(f"Failed to create relation for person {person_id}: {e}")
                                    Toast.show_toast(self, map_exception(e), Toast.ERROR)
                    except Exception as e:
                        from services.error_mapper import is_duplicate_nid_error, build_duplicate_person_message
                        if is_duplicate_nid_error(e):
                            ErrorHandler.show_warning(self, build_duplicate_person_message(getattr(e, 'response_data', {})), tr("common.warning"))
                        else:
                            logger.error(f"Failed to update person via API: {e}")
                            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))
                        return

            if person_data.get('_is_applicant'):
                updated_data['_is_applicant'] = True
            self.context.persons[person_index] = updated_data
            self.context.finalize_response = None
            self._refresh_persons_list()
            logger.info(f"Person updated: {updated_data.get('first_name', '')} {updated_data.get('last_name', '')}")

    def _create_person_row_card(self, person: dict, index: int = 0) -> QFrame:
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect

        person_id = person.get('person_id', '')
        is_rtl = get_layout_direction() == Qt.RightToLeft
        cell_align = (
            Qt.AlignRight | Qt.AlignAbsolute | Qt.AlignVCenter
            if is_rtl else
            Qt.AlignLeft | Qt.AlignAbsolute | Qt.AlignVCenter
        )

        card = QFrame()
        card.setObjectName("personCard")
        card.setLayoutDirection(get_layout_direction())
        card.setStyleSheet(PERSON_CARD_STYLE)
        card.setCursor(Qt.PointingHandCursor)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(14)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)

        card.mousePressEvent = lambda ev, pid=person_id: (
            self._view_person(pid)
            if ev.button() == Qt.LeftButton
            and not any(c.underMouse() for c in card.findChildren(QPushButton))
            else None
        )

        layout = QVBoxLayout(card)
        layout.setSpacing(ScreenScale.h(6))
        layout.setContentsMargins(16, 14, 16, 12)

        def _labeled_cell(label_text: str, value_widget: QWidget) -> QWidget:
            wrap = QWidget()
            wrap.setLayoutDirection(card.layoutDirection())
            wrap.setStyleSheet("background: transparent;")
            vl = QVBoxLayout(wrap)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(3)
            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #64748B; background: transparent; border: none;")
            lbl.setAlignment(cell_align)
            if isinstance(value_widget, QLabel):
                value_widget.setAlignment(cell_align)
            vl.addWidget(lbl)
            vl.addWidget(value_widget)
            return wrap

        # Three-dot menu removed per UX request — clicking the card itself
        # already opens the person view (see card.mousePressEvent below),
        # so the "⋮ → عرض" affordance was redundant.

        # ── 3 rows × 2 cols info grid (identical structure to unit card) ──
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(ScreenScale.w(12))
        info_grid.setVerticalSpacing(ScreenScale.h(8))
        info_grid.setContentsMargins(0, 0, 0, 0)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)

        # Row 0: full name (13pt Bold) | role badge (colored pill like unit status)
        full_name = " ".join(filter(None, [
            person.get('first_name', ''),
            person.get('father_name', ''),
            person.get('last_name', ''),
        ])).strip() or "-"
        name_val = QLabel(full_name)
        name_val.setFont(create_font(size=15, weight=FontManager.WEIGHT_BOLD))
        name_val.setStyleSheet("color: #0F172A; background: transparent; border: none;")
        name_val.setWordWrap(True)
        info_grid.addWidget(_labeled_cell(tr("wizard.person_dialog.first_name"), name_val), 0, 0)

        role_key = person.get('person_role') or person.get('relationship_type')
        role_text = get_relationship_to_head_display(role_key) if role_key else "-"
        _ROLE_PALETTE = {
            'head':     ('#DBEAFE', '#1D4ED8'),
            'spouse':   ('#FAE8FF', '#7E22CE'),
            'wife':     ('#FAE8FF', '#7E22CE'),
            'husband':  ('#FAE8FF', '#7E22CE'),
            'son':      ('#DCFCE7', '#166534'),
            'daughter': ('#DCFCE7', '#166534'),
            'child':    ('#DCFCE7', '#166534'),
            'brother':  ('#FEF3C7', '#B45309'),
            'sister':   ('#FEF3C7', '#B45309'),
            'father':   ('#FFEDD5', '#C2410C'),
            'mother':   ('#FFEDD5', '#C2410C'),
            'other':    ('#E0E7FF', '#4338CA'),
        }
        badge_bg, badge_fg = _ROLE_PALETTE.get(
            str(role_key).lower() if role_key else '',
            ('#DBEAFE', '#1D4ED8'),
        )
        role_badge = QLabel(role_text)
        role_badge.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        role_badge.setStyleSheet(
            f"background-color: {badge_bg}; color: {badge_fg};"
            "padding: 4px 12px; border-radius: 10px; border: none;"
        )
        role_badge.setAlignment(Qt.AlignCenter)
        role_holder = QWidget()
        role_holder.setLayoutDirection(card.layoutDirection())
        role_holder.setStyleSheet("background: transparent;")
        rh = QHBoxLayout(role_holder)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(0)
        rh.addWidget(role_badge, 0)
        rh.addStretch(1)
        info_grid.addWidget(_labeled_cell(tr("wizard.person_dialog.person_role"), role_holder), 0, 1)

        # Row 1: father_name | mother_name
        father_val = QLabel(person.get('father_name') or '-')
        father_val.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        father_val.setStyleSheet("color: #1E293B; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.person_dialog.father_name"), father_val), 1, 0)

        mother_val = QLabel(person.get('mother_name') or '-')
        mother_val.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        mother_val.setStyleSheet("color: #1E293B; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.person_dialog.mother_name"), mother_val), 1, 1)

        # Row 2: phone | national_id
        phone_val = QLabel(person.get('phone') or '-')
        phone_val.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        phone_val.setStyleSheet("color: #1E293B; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.person_dialog.phone"), phone_val), 2, 0)

        nid_val = QLabel(person.get('national_id') or '-')
        nid_val.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        nid_val.setStyleSheet("color: #1E293B; background: transparent; border: none;")
        info_grid.addWidget(_labeled_cell(tr("wizard.person_dialog.national_id"), nid_val), 2, 1)

        layout.addLayout(info_grid)

        # ── Relation + docs: only rendered when there is actual content ──
        rel_data = person.get('relation_data', {}) or {}
        rel_type = rel_data.get('rel_type') or person.get('relationship_type') or person.get('person_role')
        rel_display = get_relation_type_display(rel_type) if rel_type else ''
        share = rel_data.get('ownership_share')
        if rel_display and share:
            rel_display = f"{rel_display} · {share}٪"
        has_docs = bool(rel_data.get('has_documents') or person.get('_relation_uploaded_files'))

        if rel_display or has_docs:
            layout.addWidget(self._thin_hline())

            bottom_row = QHBoxLayout()
            bottom_row.setContentsMargins(0, 0, 0, 0)
            bottom_row.setSpacing(8)

            if rel_display:
                rel_val = QLabel(rel_display)
                rel_val.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
                rel_val.setStyleSheet("color: #1E293B; background: transparent; border: none;")
                bottom_row.addWidget(
                    _labeled_cell(tr("wizard.occupancy_claims.rel_type_label"), rel_val), 1
                )
            else:
                bottom_row.addStretch(1)

            if has_docs:
                docs_lbl = QLabel("📎 " + tr("wizard.occupancy_claims.has_documents"))
                docs_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
                docs_lbl.setStyleSheet(
                    "QLabel { color: #10B981; background: #ECFDF5;"
                    " border: 1px solid #A7F3D0; border-radius: 6px;"
                    " padding: 3px 10px; }"
                )
                bottom_row.addWidget(
                    docs_lbl, 0,
                    Qt.AlignVCenter | (Qt.AlignLeft if is_rtl else Qt.AlignRight),
                )

            layout.addLayout(bottom_row)

        return card

    def _refresh_persons_list(self):
        while self.persons_grid.count():
            it = self.persons_grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        persons = self.context.persons or []
        has = len(persons) > 0
        self._empty_state.setVisible(not has)
        self._persons_grid_widget.setVisible(has)

        cols = 3
        for idx, person in enumerate(persons):
            card = self._create_person_row_card(person, idx)
            self.persons_grid.addWidget(card, idx // cols, idx % cols)

        remainder = len(persons) % cols
        if remainder:
            last_row = len(persons) // cols
            for c in range(remainder, cols):
                filler = QWidget()
                filler.setStyleSheet("background: transparent;")
                self.persons_grid.addWidget(filler, last_row, c)

    def _collect_relations_from_persons(self) -> List[Dict[str, Any]]:
        """Collect relation data from person records (stored in relation_data)."""
        relations = []
        for person in self.context.persons:
            rel_data = person.get('relation_data', {})
            rel_type = rel_data.get('rel_type') or person.get('relationship_type') or person.get('person_role')

            logger.info(
                f"Collecting relation for person {person.get('first_name', '?')}: "
                f"rel_data.rel_type={rel_data.get('rel_type')!r}, "
                f"relationship_type={person.get('relationship_type')!r}, "
                f"person_role={person.get('person_role')!r}, "
                f"resolved={rel_type!r} (type={type(rel_type).__name__}), "
                f"is_owner={_is_owner_relation(rel_type)}"
            )

            if not rel_type:
                continue

            tenure_files = person.get('_relation_uploaded_files') or []
            evidences = [
                {"evidence_id": f["evidence_id"], "issue_date": f.get("issue_date", "")}
                for f in tenure_files
                if f.get("evidence_id")
            ]

            relation = {
                "relation_id": str(uuid.uuid4()),
                "person_id": person.get('person_id'),
                "person_name": f"{person.get('first_name', '')} {person.get('last_name', '')}",
                "relation_type": rel_type,
                "ownership_share": rel_data.get('ownership_share', 0.0),
                "start_date": rel_data.get('start_date'),
                "evidence_type": rel_data.get('evidence_type'),
                "evidence_description": rel_data.get('evidence_desc'),
                "notes": rel_data.get('notes'),
                "has_documents": rel_data.get('has_documents', False) or bool(evidences),
                "evidences": evidences
            }
            relations.append(relation)

        return relations

    # API Integration

    def _fetch_persons_from_api(self):
        """Fetch persons from API and update context."""
        # Skip fetch if persons already exist locally to avoid overwriting
        # with raw API data (camelCase keys) that crashes the UI
        if self.context.persons:
            logger.info(f"Using {len(self.context.persons)} existing persons from context, skipping API fetch")
            return

        self._set_auth_token()

        survey_id = self.context.get_data("survey_id")
        household_id = self.context.get_data("household_id")

        if not survey_id or not household_id:
            logger.warning(f"Missing survey_id ({survey_id}) or household_id ({household_id}), skipping fetch")
            return

        logger.info(f"Fetching persons for survey {survey_id}, household {household_id}")

        try:
            persons = self._api_service.get_persons_for_household(survey_id, household_id)
            if persons:
                self.context.persons = [self._normalize_api_person(p) for p in persons]
                logger.info(f"Loaded {len(persons)} persons from API")
            else:
                logger.info("No persons found from API")
        except Exception as e:
            logger.error(f"Failed to fetch persons from API: {e}")

    @staticmethod
    def _normalize_api_person(p: dict) -> dict:
        """Map camelCase API person response to snake_case keys expected by the UI."""
        return {
            "person_id":       p.get("id") or p.get("person_id", ""),
            "first_name":      p.get("firstNameArabic") or p.get("first_name", ""),
            "last_name":       p.get("familyNameArabic") or p.get("last_name", ""),
            "father_name":     p.get("fatherNameArabic") or p.get("father_name", ""),
            "mother_name":     p.get("motherNameArabic") or p.get("mother_name", ""),
            "national_id":     p.get("nationalId") or p.get("national_id", ""),
            "birth_date":      p.get("dateOfBirth") or p.get("birth_date", ""),
            "gender":          p.get("gender"),
            "nationality":     p.get("nationality"),
            "phone":           p.get("mobileNumber") or p.get("phone", ""),
            "landline":        p.get("phoneNumber") or p.get("landline", ""),
            "email":           p.get("email", ""),
            "person_role":     p.get("relationType") or p.get("person_role"),
            "relationship_type": p.get("relationshipType") or p.get("relationship_type"),
            "_relation_id":    p.get("relationId") or p.get("_relation_id"),
            "relation_data":   p.get("relation_data", {}),
        }

    def _enrich_persons_with_server_evidences(self):
        """Fetch server evidences once and populate _relation_uploaded_files
        for persons that have a _relation_id but no local evidence entries."""
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            return

        needs_enrichment = any(
            p.get('_relation_id') and not p.get('_relation_uploaded_files')
            for p in self.context.persons
        )
        if not needs_enrichment:
            return

        try:
            self._set_auth_token()
            evidences = self._api_service.get_survey_evidences(survey_id)
        except Exception as e:
            logger.warning(f"Could not fetch survey evidences for enrichment: {e}")
            return

        relation_ev_map: dict = {}
        for ev in evidences:
            rel_id = (ev.get('personPropertyRelationId')
                      or ev.get('PersonPropertyRelationId'))
            if not rel_id:
                continue
            ev_id = (ev.get('id') or ev.get('evidenceId')
                     or ev.get('Id') or ev.get('EvidenceId') or '')
            if not ev_id:
                continue
            relation_ev_map.setdefault(rel_id, []).append({
                'path': '',
                'evidence_id': ev_id,
                'issue_date': (ev.get('documentIssuedDate')
                               or ev.get('DocumentIssuedDate') or ''),
                '_selected_existing': True,
                '_display_name': (ev.get('originalFileName') or ev.get('OriginalFileName') or ev_id),
            })

        for person in self.context.persons:
            rel_id = person.get('_relation_id')
            if not rel_id or person.get('_relation_uploaded_files'):
                continue
            server_files = relation_ev_map.get(rel_id, [])
            if server_files:
                person['_relation_uploaded_files'] = server_files
                logger.info(
                    f"Enriched {person.get('first_name', '?')} with "
                    f"{len(server_files)} server evidences"
                )

    def _process_claims_via_api(self):
        """Process claims by calling the finalize API."""
        self._set_auth_token()

        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            logger.warning("No survey_id found in context. Skipping process-claims.")
            ErrorHandler.show_warning(self, tr("wizard.error.no_survey_id"), tr("common.error"))
            return

        logger.info(f"Processing claims for survey {survey_id}")

        # Only send notes on first finalization to prevent duplication
        already_finalized = self.context.get_data("_survey_finalized_once")
        process_options = {
            "finalNotes": "" if already_finalized else "Survey completed from office wizard",
            "durationMinutes": 10,
            "autoCreateClaim": True
        }

        try:
            api_data = self._api_service.finalize_office_survey(survey_id, process_options)
            logger.info(f"Survey {survey_id} claims processed successfully")
            self.context.finalize_response = api_data
            self.context.update_data("_survey_finalized_once", True)

            claims_count = api_data.get("claimsCreatedCount", 0)
            created_claims = api_data.get("createdClaims", [])

            if api_data.get("claimCreated") or claims_count > 0:
                logger.info(f"Claims created: {claims_count}")
            else:
                reason = api_data.get('claimNotCreatedReason', 'Unknown')
                logger.warning(f"Claim not created. Reason: {reason}")

        except Exception as e:
            logger.error(f"Failed to process claims via API: {e}")
            from services.error_mapper import map_exception
            ErrorHandler.show_error(self, map_exception(e), tr("common.error"))

    # BaseStep interface

    # _make_icon_header is now shared via wizard_styles.make_icon_header

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        self._add_person_btn.setText(tr("wizard.occupancy_claims.add_person"))
        if hasattr(self, '_header_title'):
            self._header_title.setText(tr("wizard.occupancy_claims.title"))
            self._header_subtitle.setText(tr("wizard.occupancy_claims.subtitle"))
        if hasattr(self, '_empty_title_label'):
            self._empty_title_label.setText(tr("wizard.occupancy_claims.empty_title"))
            self._empty_desc_label.setText(tr("wizard.occupancy_claims.empty_desc"))
        self._refresh_persons_list()

    def validate(self) -> StepValidationResult:
        """Validate - at least one person required, at least one with a property relation."""
        result = self.create_validation_result()

        if len(self.context.persons) == 0:
            result.add_error(tr("wizard.person.min_one_required"))

        # Collect relations from person data into context
        self.context.relations = self._collect_relations_from_persons()
        self.context.claims = self._build_claims_preview()

        # At least one person must have a relation to the property (claim)
        if self.context.persons and not self.context.relations:
            result.add_error(tr("wizard.occupancy_claims.min_one_relation"))

        return result

    def _build_claims_preview(self) -> list:
        """Build a claims preview list from persons with relations, for ReviewStep display."""
        unit_id = None
        unit_display_id = None
        if self.context.unit:
            unit_id = getattr(self.context.unit, 'unit_uuid', None)
            unit_display_id = (
                getattr(self.context.unit, 'unit_number', None)
                or getattr(self.context.unit, 'unit_display_id', None)
            )
        elif self.context.new_unit_data:
            unit_id = self.context.new_unit_data.get('unit_uuid')
            unit_display_id = self.context.new_unit_data.get('unit_number')

        claims = []
        for person in self.context.persons:
            rel_data = person.get('relation_data', {})
            role_key = (
                rel_data.get('rel_type')
                or person.get('person_role')
                or person.get('relationship_type')
            )
            if not role_key:
                continue
            full_name = " ".join(filter(None, [
                person.get('first_name', ''),
                person.get('father_name', ''),
                person.get('last_name', ''),
            ]))
            tenure_files = person.get('_relation_uploaded_files') or []
            evidence_ids = [f['evidence_id'] for f in tenure_files if f.get('evidence_id')]
            claims.append({
                'person_name': full_name,
                'claimant_name': full_name,
                'unit_id': unit_id,
                'unit_display_id': unit_display_id,
                'claim_type': role_key,
                'business_nature': rel_data.get('contract_type'),
                'case_status': 'open',
                'source': rel_data.get('evidence_type'),
                'survey_date': rel_data.get('start_date'),
                'priority': rel_data.get('priority', 2) or 2,
                'notes': rel_data.get('notes', ''),
                'evidence_count': len(evidence_ids),
                'evidence_ids': evidence_ids,
            })
        return claims

    def collect_data(self) -> Dict[str, Any]:
        """Collect persons and relations data."""
        relations = self._collect_relations_from_persons()
        self.context.relations = relations
        return {
            "persons": self.context.persons,
            "persons_count": len(self.context.persons),
            "relations": relations,
            "relations_count": len(relations)
        }

    def reset(self):
        """Clear persons list for a new wizard session."""
        if not self._is_initialized:
            return
        self._refresh_persons_list()

    def populate_data(self):
        """Populate step with context data."""
        self._refresh_persons_list()

    def on_show(self):
        """Called when step is shown."""
        super().on_show()
        self._fetch_persons_from_api()
        self._enrich_persons_with_server_evidences()
        self._auto_relink_orphaned_persons()
        self._refresh_persons_list()

    def _auto_relink_orphaned_persons(self):
        """Re-create relations for persons that lost them after unit change.

        When user goes back to Step 2 and selects a different unit,
        cleanup_on_unit_change() deletes relations and sets _relation_id=None.
        This method detects those orphaned persons and re-links them
        to the current unit using their stored relation data.
        """
        _, survey_id, _, unit_id = self._get_context_ids()
        if not survey_id or not unit_id:
            return

        orphaned = [p for p in self.context.persons
                    if p.get('person_id') and not p.get('_relation_id')]
        if not orphaned:
            return

        logger.info(f"Found {len(orphaned)} persons without relations, auto-relinking to unit {unit_id}")
        self._set_auth_token()

        contact_person_id = self.context.get_data('contact_person_id')
        for person in orphaned:
            if person.get('_is_contact_person') or person.get('_is_applicant'):
                continue
            if contact_person_id and person.get('person_id') == contact_person_id:
                continue

            person_id = person['person_id']
            rel_data = person.get('relation_data', {})
            rel_type = rel_data.get('rel_type') or person.get('person_role') or person.get('relationship_type')

            if not rel_type:
                logger.warning(f"Skipping auto-relink for person {person_id}: no relation type")
                continue

            relation_data = {
                'person_id': person_id,
                'rel_type': rel_type,
                'ownership_share': rel_data.get('ownership_share', 0),
                'contract_type': rel_data.get('contract_type'),
                'evidence_desc': rel_data.get('evidence_desc'),
                'notes': rel_data.get('notes'),
                'has_documents': rel_data.get('has_documents', False),
            }

            try:
                response = self._api_service.link_person_to_unit(survey_id, unit_id, relation_data)
                new_relation_id = response.get('id') or response.get('relationId')
                person['_relation_id'] = new_relation_id
                logger.info(f"Auto-relinked person {person_id} to unit {unit_id}, new relation: {new_relation_id}")
            except Exception as e:
                logger.error(f"Failed to auto-relink person {person_id}: {e}")

    def on_next(self):
        """Called when user clicks Next."""
        pass

    def get_step_title(self) -> str:
        return tr("wizard.occupancy_claims.step_title")

    def get_step_description(self) -> str:
        return tr("wizard.occupancy_claims.step_description")
