# -*- coding: utf-8 -*-
"""
Survey Controller — fetches office survey data via Surveys/office API.

Uses the survey-centric approach: one detail call returns households, relations,
and evidence bundled together (properly scoped to a single survey).
Building, Unit, and Person details are enriched via separate calls.

Reuses BuildingController for building mapping (with admin name resolution)
and ClaimController's static methods for unit/person/household mapping.
"""

from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from controllers.base_controller import OperationResult
from services.error_mapper import map_exception
from utils.logger import get_logger

logger = get_logger(__name__)


class SurveyController:
    """Controller for survey-centric data fetching."""

    def __init__(self, db=None):
        self.db = db
    # List: draft office surveys for the cards page

    def load_office_surveys(
        self,
        status=None,
        page: int = 1,
        page_size: int = 30,
        sort_by: str = "SurveyDate",
        sort_direction: str = "desc",
        reference_code=None,
        contact_person_name=None,
        building_id=None,
        clerk_id=None,
    ) -> OperationResult:
        """
        Fetch paginated list of office surveys from API.

        Returns OperationResult with list of survey summary dicts.
        """
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            response = api.get_office_surveys(
                status=status,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_direction=sort_direction,
                reference_code=reference_code,
                contact_person_name=contact_person_name,
                building_id=building_id,
                clerk_id=clerk_id,
            )
            surveys = response.get("surveys", [])
            logger.info(f"Loaded {len(surveys)} office surveys from API (status={status})")
            return OperationResult.ok(data=surveys)
        except Exception as e:
            logger.error(f"Failed to load office surveys: {e}", exc_info=True)
            return OperationResult.fail(message=map_exception(e))
    # Detail: full survey context for ReviewStep / CaseDetailsPage

    def get_survey_full_context(self, survey_id: str) -> OperationResult:
        """
        Fetch complete survey data and return a dict compatible with SurveyContext.from_dict().

        Flow:
          1. GET /Surveys/office/{id} → households, relations, evidence, dataSummary (bundled)
          2. GET /Buildings/{buildingId} → full building details (enrichment)
          3. GET /PropertyUnits/{unitId} → full unit details (enrichment)
          4. GET /Persons/{personId} per relation → person names (enrichment)
        """
        try:
            from services.api_client import get_api_client
            from controllers.claim_controller import ClaimController
            from controllers.building_controller import BuildingController

            api = get_api_client()

            # Step 1: Get survey detail (must be first — all IDs come from here)
            detail = api.get_office_survey_detail(survey_id)

            # Extract IDs for parallel enrichment
            building_id = detail.get("buildingId")
            unit_id = detail.get("propertyUnitId")
            claim_id = detail.get("claimId")
            contact_person_id = detail.get("contactPersonId")

            households = []
            try:
                survey_households = api.get_households_for_survey(survey_id) or []
                if survey_households:
                    def _sort_key(h):
                        return (
                            h.get("lastModifiedAtUtc")
                            or h.get("createdAtUtc")
                            or ""
                        )
                    survey_households.sort(key=_sort_key, reverse=True)
                    latest = survey_households[0]
                    households = [ClaimController._map_household_dto(latest)]
                    logger.warning(
                        f"[HOUSEHOLD] survey {survey_id} has {len(survey_households)} "
                        f"household(s); using latest id={latest.get('id', '')}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to fetch households for survey {survey_id}: {e}"
                )
            hh_id = households[0].get("household_id", "") if households else ""

            # Step 2: Parallel enrichment — building, unit, persons, claim, contact
            building_data = {}
            unit_data = {}
            person_map = {}
            claim_dto = None
            contact_person_dto = None

            all_persons_list = []
            futures = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                if building_id:
                    futures['building'] = executor.submit(api.get_building_by_id, building_id)
                if unit_id:
                    futures['unit'] = executor.submit(api._request, "GET", f"/v1/PropertyUnits/{unit_id}")
                if hh_id:
                    futures['persons'] = executor.submit(api.get_persons_for_household, survey_id, hh_id)
                if claim_id:
                    futures['claim'] = executor.submit(api.get_claim_by_id, claim_id)
                futures['contact_person'] = executor.submit(api.get_contact_person, survey_id)

            # Collect results with individual error handling
            if 'building' in futures:
                try:
                    building_dto = futures['building'].result()
                    bc = BuildingController(self.db)
                    building_obj = bc._api_dto_to_building(building_dto)
                    building_data = building_obj.to_dict()
                except Exception as e:
                    logger.warning(f"Failed to fetch building {building_id}: {e}")

            if 'unit' in futures:
                try:
                    unit_dto = futures['unit'].result()
                    unit_data = ClaimController._map_unit_dto(unit_dto)
                except Exception as e:
                    logger.warning(f"Failed to fetch unit {unit_id}: {e}")

            if 'persons' in futures:
                try:
                    all_persons_list = futures['persons'].result() or []
                    person_map = {p.get("id"): p for p in all_persons_list}
                except Exception as e:
                    logger.warning(f"Failed to fetch household persons: {e}")

            if 'claim' in futures:
                try:
                    claim_dto = futures['claim'].result()
                except Exception as e:
                    logger.warning(f"Failed to fetch claim {claim_id}: {e}")

            survey_contact_person_dto = None
            if 'contact_person' in futures:
                try:
                    survey_contact_person_dto = futures['contact_person'].result()
                except Exception as e:
                    logger.warning(f"Failed to fetch survey contact person: {e}")

            # Build relations list from survey detail (kept for ownership tracking)
            relations = []
            relation_by_person_id = {}
            for rel in (detail.get("relations") or []):
                person_id = rel.get("personId")
                relations.append({
                    "relation_id": rel.get("id", ""),
                    "person_id": person_id or "",
                    "unit_id": rel.get("propertyUnitId", ""),
                    "relation_type": rel.get("relationType", ""),
                })
                if person_id:
                    relation_by_person_id.setdefault(person_id, rel)

            # Build persons list straight from the household persons endpoint
            # (which already includes the contact person via isContactPerson).
            persons = []
            contact_person_dto = None
            seen_person_ids = set()
            for person_dto in all_persons_list:
                pid = person_dto.get("id", "")
                rel = relation_by_person_id.get(pid, {})
                persons.append(ClaimController._map_person_dto(person_dto, rel))
                if pid:
                    seen_person_ids.add(pid)
                if person_dto.get("isContactPerson") and not contact_person_dto:
                    contact_person_dto = person_dto

            # Prefer the survey-scoped contact person (works for draft surveys
            # where the detail response omits contactPersonId, and for contact
            # persons that aren't household members).
            if survey_contact_person_dto:
                contact_person_dto = survey_contact_person_dto
                cp_id = survey_contact_person_dto.get("id", "")
                if cp_id and cp_id not in seen_person_ids:
                    rel = relation_by_person_id.get(cp_id, {})
                    persons.append(
                        ClaimController._map_person_dto(survey_contact_person_dto, rel)
                    )
                    seen_person_ids.add(cp_id)

            # Fallback: if neither source returned the contact person but the
            # survey detail referenced one, pick it up from person_map by id.
            if not contact_person_dto and contact_person_id:
                contact_person_dto = person_map.get(contact_person_id)

            # Claim data mapped from survey detail + linked claim
            claim_data = self._map_survey_to_claim_data(detail, persons, claim_dto)

            applicant = None
            if contact_person_dto:
                applicant = {
                    "first_name_ar": contact_person_dto.get("firstNameArabic") or "",
                    "father_name_ar": contact_person_dto.get("fatherNameArabic") or "",
                    "last_name_ar": contact_person_dto.get("familyNameArabic") or "",
                    "mother_name_ar": contact_person_dto.get("motherNameArabic") or "",
                    "full_name": contact_person_dto.get("fullNameArabic") or "",
                    "national_id": contact_person_dto.get("nationalId") or "",
                    "phone": contact_person_dto.get("mobileNumber") or "",
                    "email": contact_person_dto.get("email") or "",
                    "landline": contact_person_dto.get("phoneNumber") or "",
                    "gender": contact_person_dto.get("gender"),
                    "nationality": contact_person_dto.get("nationality"),
                    "birth_date": contact_person_dto.get("dateOfBirth") or "",
                }
                # Save identification document metadata (download on demand)
                # Identification documents belong to the person, not the survey
                target_person_id = contact_person_id or contact_person_dto.get("id", "")
                logger.warning(f"[ID-DOCS] Fetching identification documents for person={target_person_id}")
                if target_person_id:
                    try:
                        id_docs = api.get_person_identification_documents(target_person_id)
                        logger.warning(f"[ID-DOCS] API returned {len(id_docs) if id_docs else 0} document(s)")
                        if id_docs:
                            applicant["id_photo_evidences"] = [
                                {
                                    "id": doc.get("id", ""),
                                    "personId": doc.get("personId", target_person_id),
                                    "fileName": doc.get("fileName") or doc.get("originalFileName") or "",
                                    "mimeType": doc.get("mimeType") or "",
                                    "filePath": doc.get("filePath") or "",
                                }
                                for doc in id_docs
                            ]
                            logger.warning(f"[ID-DOCS] Stored {len(applicant['id_photo_evidences'])} entries in applicant.id_photo_evidences")
                    except Exception as e:
                        logger.warning(f"[ID-DOCS] Could not fetch identification documents: {e}")
                else:
                    logger.warning("[ID-DOCS] No target_person_id available — skipping fetch")

            resolved_cp_id = contact_person_id or (
                contact_person_dto.get("id", "") if contact_person_dto else ""
            )

            survey_status = detail.get("status", 1)
            status_str = "finalized" if survey_status == 3 else "draft"

            resume_step = self._determine_resume_step(detail, households, persons)

            context = {
                "survey_id": detail.get("id", ""),
                "reference_number": detail.get("referenceCode", ""),
                "status": status_str,
                "resume_step": resume_step,
                "data": {
                    "survey_id": detail.get("id", ""),
                    "survey_building_uuid": building_id or "",
                    "survey_property_unit_id": unit_id or "",
                    "household_id": hh_id,
                    "contact_person_id": resolved_cp_id,
                },
                "building": building_data,
                "unit": unit_data,
                "households": households,
                "persons": persons,
                "relations": relations,
                "claim_data": claim_data,
                "claims": [claim_data] if claim_data else [],
                "applicant": applicant,
            }
            logger.info(
                f"Built survey context: building={bool(building_data)}, "
                f"unit={bool(unit_data)}, households={len(households)}, "
                f"persons={len(persons)}, relations={len(relations)}"
            )
            return OperationResult.ok(data=context)

        except Exception as e:
            logger.error(f"Failed to get survey context: {e}", exc_info=True)
            return OperationResult.fail(message=map_exception(e))

    @staticmethod
    def _determine_resume_step(detail: dict, households: list, persons: list) -> int:
        """Determine which wizard step to resume from based on available data.

        Step mapping: 0=Building, 1=Applicant, 2=Unit, 3=Household, 4=Persons, 5=Review
        """
        if not detail.get("contactPersonId"):
            return 1
        if not detail.get("propertyUnitId"):
            return 2
        if not households:
            return 3
        if not persons:
            return 4
        return 5


    @staticmethod
    def _map_survey_to_claim_data(detail: dict, persons: List[dict],
                                  claim_dto: Optional[dict] = None) -> dict:
        """
        Map survey detail fields to the claim_data dict that ReviewStep expects.

        Args:
            detail: Survey detail from API (GET /Surveys/office/{id})
            persons: List of mapped person dicts
            claim_dto: Linked claim data from API (GET /Claims/{id}), if available

        ReviewStep reads: claim_type, priority, source, case_status, person_name,
        unit_display_id, business_nature, survey_date, notes, next_action_date,
        evidence_count.
        """
        # Primary claimant name from first person
        person_name = ""
        if persons:
            p = persons[0]
            parts = [p.get("first_name", ""), p.get("father_name", ""), p.get("last_name", "")]
            person_name = " ".join(part for part in parts if part)
            if not person_name:
                person_name = p.get("full_name", "")

        summary = detail.get("dataSummary") or {}

        # Read claim fields from linked claim (if available)
        claim_type = ""
        priority = None
        source = detail.get("source")  # integer from survey (e.g. 2 = office)
        if claim_dto:
            # Normalize API claim type string → display key
            # e.g. "Ownership Claim" → "ownership"
            raw_type = claim_dto.get("claimType", "")
            if raw_type:
                if isinstance(raw_type, int):
                    claim_type = raw_type
                else:
                    claim_type = raw_type.lower().replace(" claim", "").strip() or raw_type
            priority = claim_dto.get("priority")
            source = claim_dto.get("claimSource") or source

        # Evidence count: prefer dataSummary, fallback to counting from relations/evidences
        evidence_count = summary.get("evidenceCount", 0)
        if not evidence_count:
            for rel in (detail.get("relations") or []):
                evidence_count += len(rel.get("evidences") or rel.get("evidenceItems") or [])
        if not evidence_count:
            evidence_count = len(
                detail.get("evidences") or
                detail.get("tenureEvidences") or
                detail.get("evidence") or
                []
            )

        claim_id = (detail.get("claimId") or
                    (claim_dto.get("id") or claim_dto.get("claimId") if claim_dto else None))

        return {
            "claim_id": claim_id,
            "claim_type": claim_type,
            "priority": priority,
            "source": source,  # integer → vocab resolves (e.g. 2 → "تقديم مكتبي")
            "case_status": detail.get("status"),  # integer → claim_status vocab (1 → "مسودة")
            "person_name": person_name,
            "unit_display_id": detail.get("unitIdentifier") or "",
            "business_nature": detail.get("businessNature") or "",
            "survey_date": (detail.get("surveyDate") or "")[:10],
            "notes": detail.get("notes") or "",
            "next_action_date": "",
            "evidence_count": evidence_count,
        }

