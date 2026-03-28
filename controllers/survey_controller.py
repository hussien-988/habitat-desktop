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

            # 3) Households (bundled in detail)
            all_households = [
                ClaimController._map_household_dto(h)
                for h in (detail.get("households") or [])
            ]
            # Keep only the survey's own household
            survey_hh_id = detail.get("householdId")
            if survey_hh_id and len(all_households) > 1:
                households = [h for h in all_households if h.get("household_id") == survey_hh_id]
                if not households:
                    households = all_households[:1]
            else:
                households = all_households

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
            contact_person_id = detail.get("contactPersonId")
            contact_person_dto = None
            try:
                contact_person_dto = api.get_contact_person(survey_id)
            except Exception as e:
                logger.warning(f"Contact person not available: {e}")

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
                # Fetch identification photos
                try:
                    evidences = api.get_survey_evidences(survey_id, evidence_type="identification")
                    if evidences:
                        from utils.helpers import download_evidence_file
                        photo_paths = []
                        for ev in evidences:
                            local_path = download_evidence_file(
                                ev.get("id", ""), ev.get("fileName", "photo")
                            )
                            if local_path:
                                photo_paths.append(local_path)
                        applicant["id_photo_paths"] = photo_paths
                except Exception as e:
                    logger.warning(f"Could not fetch ID photos: {e}")

            resolved_cp_id = contact_person_id or (
                contact_person_dto.get("id", "") if contact_person_dto else ""
            )

            survey_status = detail.get("status", 1)
            status_str = "finalized" if survey_status == 3 else "draft"

            resume_step = self._determine_resume_step(detail, households, persons)

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

