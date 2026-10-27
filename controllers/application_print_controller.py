# -*- coding: utf-8 -*-
"""
Application Print Controller
===========================
Builds the print model of a claim application from a survey context
(wizard review step, finalize popup or survey details page), filling what
the context lacks from the API: survey status/type/reference, claims and
every person's ID documents and tenure evidence. Runs inside an ApiWorker.
"""

from datetime import datetime
from typing import Dict, List, Optional

from controllers.base_controller import BaseController, OperationResult
from services.api_client import get_api_client
from services.display_mappings import (
    get_claim_status_display, get_claim_type_display, get_evidence_type_display,
    get_identification_document_type_display, get_occupancy_nature_display,
    get_relation_type_display, get_survey_type_display, get_unit_status_display,
    get_unit_type_display,
)
from services.printing.application_print_model import (
    ApplicationPrintModel, AttachmentItem, ClaimRow, PersonRow,
)
from services.printing.application_renderer import prepare_attachment_pages
from services.translation_manager import get_language, tr
from utils.helpers import (
    build_hierarchical_address, download_evidence_file, download_identification_document_file,
    format_gps_coordinates,
)
from utils.logger import get_logger

logger = get_logger(__name__)

_FINALIZED_STATUSES = ("3", "finalized")


def claim_row(claim: Dict, claimant: str = "") -> ClaimRow:
    """Printed row of an API claim; `claimant` is used when the claim has no name."""
    return ClaimRow(
        number=claim.get("claimNumber") or "",
        claimant=claim.get("primaryClaimantName") or claimant,
        claim_type=get_claim_type_display(claim["claimType"]) if claim.get("claimType") else "",
        status=get_claim_status_display(claim["status"]) if claim.get("status") else "",
    )


def _person_name(person: Dict, suffix: str = "") -> str:
    """Full name from first/father/last name keys (applicant keys end in "_ar")."""
    name = " ".join(filter(None, [
        person.get(f"first_name{suffix}"), person.get(f"father_name{suffix}"), person.get(f"last_name{suffix}"),
    ]))
    return name or person.get("full_name", "")


class ApplicationPrintController(BaseController):
    """Assembles printable claim applications."""

    def build_model(self, context) -> OperationResult:
        """Print model of the survey in `context` (no attachment files yet)."""
        try:
            api = get_api_client()
            survey_id = context.get_data("survey_id")
            detail = self._survey_detail(api, survey_id)

            status = str(detail.get("status") or getattr(context, "status", "") or "").strip().lower()
            is_draft = status not in _FINALIZED_STATUSES
            unit_id = self._unit_id(context)

            model = ApplicationPrintModel(
                rtl=get_language() == "ar",
                is_draft=is_draft,
                reference_code=detail.get("referenceCode") or context.reference_number or "",
                survey_date=(detail.get("surveyDate") or "")[:10],
                survey_type=get_survey_type_display(detail["surveyType"]) if detail.get("surveyType") else "",
                print_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                building=self._building_rows(context),
                unit=self._unit_rows(context),
                applicant=self._applicant_rows(context),
                household=self._household_rows(context),
            )
            model.attachments = self._attachments(api, context, survey_id, unit_id)
            model.persons = self._person_rows(context, model.attachments)
            if not is_draft:
                model.claims = self._claim_rows(api, context, detail, unit_id)
            return OperationResult.ok(data=model)
        except Exception as e:
            logger.error(f"Failed to build the application print model: {e}", exc_info=True)
            return OperationResult.fail(str(e), tr("print.failed"))

    def prepare_attachments(self, model: ApplicationPrintModel) -> OperationResult:
        """Download the model's attachments and turn them into printable pages."""
        try:
            for item in model.attachments:
                if item.kind == "id_document":
                    item.local_path = download_identification_document_file(
                        item.person_id, item.document_id, item.file_name)
                else:
                    item.local_path = download_evidence_file(item.document_id, item.file_name)
            return OperationResult.ok(data=prepare_attachment_pages(model))
        except Exception as e:
            logger.error(f"Failed to prepare application attachments: {e}", exc_info=True)
            return OperationResult.fail(str(e), tr("print.failed"))

    # -- Survey --

    @staticmethod
    def _survey_detail(api, survey_id: Optional[str]) -> Dict:
        if not survey_id:
            return {}
        try:
            return api.get_office_survey_detail(survey_id) or {}
        except Exception as e:
            logger.warning(f"Print: survey detail unavailable for {survey_id}: {e}")
            return {}

    @staticmethod
    def _unit_id(context) -> Optional[str]:
        if context.unit:
            return getattr(context.unit, "unit_uuid", None)
        if context.new_unit_data:
            return context.new_unit_data.get("unit_uuid")
        return None

    # -- Form sections --

    @staticmethod
    def _building_rows(context) -> List:
        building = context.building
        if not building:
            return []
        return [
            (tr("print.col.building_code"), building.building_id_formatted or building.building_id or ""),
            (tr("wizard.building.type"), building.building_type_display),
            (tr("print.col.address"), build_hierarchical_address(building_obj=building, include_unit=False)),
            (tr("print.col.gps_coordinates"), format_gps_coordinates(building.latitude, building.longitude)),
            (tr("wizard.building.status"), building.building_status_display),
            (tr("wizard.building.units_count"), str(getattr(building, "number_of_units", "") or "")),
        ]

    @staticmethod
    def _unit_rows(context) -> List:
        unit = context.unit
        if unit:
            number = unit.unit_number or unit.apartment_number
            floor = unit.floor_number
            unit_type = get_unit_type_display(unit.unit_type) if unit.unit_type else ""
            status = get_unit_status_display(unit.apartment_status) if unit.apartment_status else ""
            area = unit.area_sqm
        elif context.new_unit_data:
            data = context.new_unit_data
            number = data.get("unit_number")
            floor = data.get("floor_number")
            unit_type = get_unit_type_display(data["unit_type"]) if data.get("unit_type") else ""
            status = ""
            area = data.get("area_sqm")
        else:
            return []
        try:
            area_text = tr("wizard.unit.area_format", value=f"{float(area):.2f}") if area else ""
        except (TypeError, ValueError):
            area_text = ""
        return [
            (tr("wizard.unit.number"), str(number or "")),
            (tr("wizard.unit.floor_number"), "" if floor is None else str(floor)),
            (tr("wizard.unit.type"), unit_type),
            (tr("wizard.unit.status"), status),
            (tr("wizard.unit.area"), area_text),
        ]

    @staticmethod
    def _applicant_rows(context) -> List:
        applicant = context.applicant or {}
        if not applicant:
            return []
        return [
            (tr("wizard.applicant.full_name"), _person_name(applicant, "_ar")),
            (tr("wizard.applicant.national_id"), applicant.get("national_id", "")),
            (tr("wizard.applicant.phone"), applicant.get("phone", "")),
            (tr("wizard.applicant.email"), applicant.get("email", "")),
        ]

    @staticmethod
    def _household_rows(context) -> List:
        if not context.households:
            return []
        household = context.households[0]
        nature = household.get("occupancy_nature")
        return [
            (tr("wizard.household.family_size"), str(household.get("size") or 0)),
            (tr("wizard.household.males"), str(household.get("male_count") or 0)),
            (tr("wizard.household.females"), str(household.get("female_count") or 0)),
            (tr("wizard.household.occupancy_nature"), get_occupancy_nature_display(nature) if nature else ""),
            (tr("wizard.household.occupancy_start_date"), (household.get("occupancy_start_date") or "")[:10]),
        ]

    @staticmethod
    def _person_rows(context, attachments: List[AttachmentItem]) -> List[PersonRow]:
        rows = []
        for person in context.persons or []:
            relation = person.get("relation_data") or {}
            rel_type = relation.get("rel_type") or person.get("person_role")
            share = relation.get("ownership_share")
            person_id = person.get("person_id")
            rows.append(PersonRow(
                name=_person_name(person),
                national_id=person.get("national_id", ""),
                relation=get_relation_type_display(rel_type) if rel_type else "",
                share="" if share in (None, "", 0) else str(share),
                documents=sum(1 for a in attachments if person_id and a.person_id == person_id),
            ))
        return rows

    @staticmethod
    def _claim_rows(api, context, detail: Dict, unit_id: Optional[str]) -> List[ClaimRow]:
        names = {p.get("person_id"): _person_name(p) for p in context.persons or []}
        rows = []
        for claim in detail.get("claims") or []:
            if unit_id and claim.get("propertyUnitId") and claim.get("propertyUnitId") != unit_id:
                continue  # a field package may carry claims on other units
            if not claim.get("claimNumber") and claim.get("id"):
                try:
                    claim = {**claim, **(api.get_claim_by_id(claim["id"]) or {})}
                except Exception as e:
                    logger.warning(f"Print: claim {claim.get('id')} unavailable: {e}")
            rows.append(claim_row(claim, names.get(claim.get("primaryClaimantId"), "")))
        return rows

    # -- Attachments --

    def _attachments(self, api, context, survey_id: Optional[str],
                     unit_id: Optional[str]) -> List[AttachmentItem]:
        """ID documents and tenure evidence of every person, in person order."""
        people = [(p.get("person_id"), _person_name(p), p.get("_relation_id"))
                  for p in context.persons or [] if p.get("person_id")]
        contact_id = context.get_data("contact_person_id")
        if contact_id and contact_id not in {pid for pid, _, _ in people}:
            applicant = context.applicant or {}
            people.insert(0, (contact_id, _person_name(applicant, "_ar"), None))

        relation_ids = self._relation_ids(api, survey_id, unit_id)
        items: List[AttachmentItem] = []
        seen_evidence = set()
        for person_id, name, relation_id in people:
            items.extend(self._id_documents(api, person_id, name))
            relation_id = relation_id or relation_ids.get(person_id)
            if survey_id and relation_id:
                for item in self._evidences(api, survey_id, relation_id, person_id, name):
                    if item.document_id not in seen_evidence:
                        seen_evidence.add(item.document_id)
                        items.append(item)
        return items

    @staticmethod
    def _relation_ids(api, survey_id: Optional[str], unit_id: Optional[str]) -> Dict[str, str]:
        if not survey_id or not unit_id:
            return {}
        try:
            return {
                r.get("personId"): r.get("id")
                for r in api.get_unit_relations(survey_id, unit_id) or []
                if r.get("personId") and r.get("id")
            }
        except Exception as e:
            logger.warning(f"Print: relations unavailable for unit {unit_id}: {e}")
            return {}

    @staticmethod
    def _id_documents(api, person_id: str, name: str) -> List[AttachmentItem]:
        try:
            documents = api.get_person_identification_documents_for_survey(person_id) or []
        except Exception as e:
            logger.warning(f"Print: ID documents unavailable for {person_id}: {e}")
            return []
        items = []
        for doc in documents:
            doc_id = doc.get("id") or ""
            if not doc_id:
                continue
            doc_type = doc.get("documentType")
            items.append(AttachmentItem(
                kind="id_document",
                doc_type=get_identification_document_type_display(doc_type) if doc_type else tr("print.id_document"),
                person=name,
                file_name=doc.get("originalFileName") or doc.get("fileName") or doc_id,
                person_id=person_id,
                document_id=doc_id,
            ))
        return items

    @staticmethod
    def _evidences(api, survey_id: str, relation_id: str, person_id: str,
                   name: str) -> List[AttachmentItem]:
        try:
            evidences = api.get_relation_evidences(survey_id, relation_id) or []
        except Exception as e:
            logger.warning(f"Print: evidence unavailable for relation {relation_id}: {e}")
            return []
        items = []
        for evidence in evidences:
            evidence_id = evidence.get("id") or evidence.get("evidenceId") or ""
            if not evidence_id:
                continue
            ev_type = evidence.get("evidenceType")
            items.append(AttachmentItem(
                kind="evidence",
                doc_type=get_evidence_type_display(ev_type) if ev_type else tr("print.evidence"),
                person=name,
                file_name=evidence.get("originalFileName") or evidence.get("fileName") or evidence_id,
                person_id=person_id,
                document_id=evidence_id,
            ))
        return items

