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

from controllers.base_controller import OperationResult
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
            return OperationResult.fail(message=str(e))
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
            detail = api.get_office_survey_detail(survey_id)

            building_data = {}
            building_id = detail.get("buildingId")
            if building_id:
                try:
                    building_dto = api.get_building_by_id(building_id)
                    bc = BuildingController(self.db)
                    building_obj = bc._api_dto_to_building(building_dto)
                    building_data = building_obj.to_dict()
                except Exception as e:
                    logger.warning(f"Failed to fetch building {building_id}: {e}")

            unit_data = {}
            unit_id = detail.get("propertyUnitId")
            if unit_id:
                try:
                    unit_dto = api._request("GET", f"/v1/PropertyUnits/{unit_id}")
                    unit_data = ClaimController._map_unit_dto(unit_dto)
                except Exception as e:
                    logger.warning(f"Failed to fetch unit {unit_id}: {e}")

            # 3) Households (bundled in detail — no extra call)
            households = [
                ClaimController._map_household_dto(h)
                for h in (detail.get("households") or [])
            ]

            # 4) Persons + relations from survey detail
            persons = []
            relations = []

            # Fetch household persons
            hh_id = households[0].get("household_id", "") if households else ""
            person_map = {}
            if hh_id:
                try:
                    all_persons_list = api.get_persons_for_household(survey_id, hh_id)
                    person_map = {p.get("id"): p for p in all_persons_list}
                except Exception as e:
                    logger.warning(f"Failed to fetch household persons: {e}")

            seen_person_ids = set()
            for rel in (detail.get("relations") or []):
                person_id = rel.get("personId")
                relations.append({
                    "relation_id": rel.get("id", ""),
                    "person_id": person_id or "",
                    "unit_id": rel.get("propertyUnitId", ""),
                    "relation_type": rel.get("relationType", ""),
                })
                if not person_id or person_id in seen_person_ids:
                    continue
                seen_person_ids.add(person_id)
                person_dto = person_map.get(person_id)
                if person_dto:
                    persons.append(ClaimController._map_person_dto(person_dto, rel))
                else:
                    logger.warning(f"Person {person_id} not found in household persons")

            # 5) Claim enrichment (if linked)
            claim_dto = None
            claim_id = detail.get("claimId")
            if claim_id:
                try:
                    claim_dto = api.get_claim_by_id(claim_id)
                except Exception as e:
                    logger.warning(f"Failed to fetch claim {claim_id}: {e}")

            # 6) Claim data mapped from survey detail + linked claim
            claim_data = self._map_survey_to_claim_data(detail, persons, claim_dto)

            # 7) Build applicant
            applicant = None
            contact_person_id = detail.get("contactPersonId")
            contact_person_dto = person_map.get(contact_person_id) if contact_person_id else None

            if contact_person_dto:
                applicant = {
                    "first_name_ar": contact_person_dto.get("firstNameArabic", ""),
                    "father_name_ar": contact_person_dto.get("fatherNameArabic", ""),
                    "last_name_ar": contact_person_dto.get("familyNameArabic", ""),
                    "mother_name_ar": contact_person_dto.get("motherNameArabic", ""),
                    "full_name": contact_person_dto.get("fullNameArabic", ""),
                    "national_id": contact_person_dto.get("nationalId", ""),
                    "phone": contact_person_dto.get("mobileNumber", ""),
                    "email": contact_person_dto.get("email", ""),
                    "landline": contact_person_dto.get("phoneNumber", ""),
                    "gender": contact_person_dto.get("gender"),
                    "nationality": contact_person_dto.get("nationality"),
                }
            else:
                full_name = detail.get("contactPersonFullName") or detail.get("intervieweeName") or ""
                if full_name:
                    name_parts = full_name.split()
                    applicant = {
                        "first_name_ar": name_parts[0] if len(name_parts) > 0 else "",
                        "father_name_ar": name_parts[1] if len(name_parts) > 1 else "",
                        "last_name_ar": " ".join(name_parts[2:]) if len(name_parts) > 2 else "",
                        "mother_name_ar": "",
                        "full_name": full_name,
                        "national_id": "", "phone": "", "email": "",
                    }
                elif persons:
                    p = persons[0]
                    applicant = {
                        "first_name_ar": p.get("first_name", ""),
                        "father_name_ar": p.get("father_name", ""),
                        "last_name_ar": p.get("last_name", ""),
                        "mother_name_ar": p.get("mother_name", ""),
                        "full_name": p.get("full_name", ""),
                        "national_id": p.get("national_id", ""),
                        "phone": "", "email": "",
                    }

            survey_status = detail.get("status", 1)
            status_str = "finalized" if survey_status == 3 else "draft"

            resume_step = self._determine_resume_step(detail, households, persons)

            # Fallback: if contact_person_id not in API, check local cache
            resolved_cp_id = contact_person_id or ""
            if not resolved_cp_id:
                try:
                    from repositories.survey_repository import SurveyRepository
                    repo = SurveyRepository(self.db)
                    cached_cp_id, cached_applicant = repo.get_contact_person_cache(survey_id)
                    if cached_cp_id:
                        resolved_cp_id = cached_cp_id
                        logger.info(f"contact_person_id restored from local cache: {cached_cp_id}")
                    if cached_applicant and not applicant:
                        applicant = cached_applicant
                except Exception as cache_err:
                    logger.warning(f"Local cache fallback failed: {cache_err}")

            context = {
                "survey_id": detail.get("id", ""),
                "status": status_str,
                "resume_step": resume_step,
                "data": {
                    "survey_id": detail.get("id", ""),
                    "survey_building_uuid": building_id or "",
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
            return OperationResult.fail(message=str(e))

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

