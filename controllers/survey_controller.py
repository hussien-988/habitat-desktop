# -*- coding: utf-8 -*-
"""
Survey Controller — fetches office survey data via Surveys/office API.

Uses the survey-centric approach: one detail call returns households, relations,
and evidence bundled together (properly scoped to a single survey).
Building, Unit, and Person details are enriched via separate calls.

DRY: Reuses BuildingController for building mapping (with admin name resolution)
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

    # ------------------------------------------------------------------
    # List: draft office surveys for the cards page
    # ------------------------------------------------------------------

    def load_office_surveys(self, status: str = "Draft", page: int = 1, page_size: int = 100) -> OperationResult:
        """
        Fetch paginated list of office surveys from API.

        Returns OperationResult with list of survey summary dicts.
        """
        try:
            from services.api_client import get_api_client
            api = get_api_client()
            response = api.get_office_surveys(status=status, page=page, page_size=page_size)
            surveys = response.get("surveys", [])
            logger.info(f"Loaded {len(surveys)} office surveys from API (status={status})")
            return OperationResult.ok(data=surveys)
        except Exception as e:
            logger.error(f"Failed to load office surveys: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    # ------------------------------------------------------------------
    # Detail: full survey context for ReviewStep / CaseDetailsPage
    # ------------------------------------------------------------------

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

            # 1) Building enrichment — use BuildingController (resolves admin names from JSON)
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

            # 2) Unit enrichment
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

            # 4) Persons from relations (scoped to THIS survey only)
            persons = []
            seen_person_ids = set()
            for rel in (detail.get("relations") or []):
                person_id = rel.get("personId")
                if not person_id or person_id in seen_person_ids:
                    continue
                seen_person_ids.add(person_id)
                try:
                    person_dto = api._request("GET", f"/v1/Persons/{person_id}")
                    persons.append(ClaimController._map_person_dto(person_dto, rel))
                except Exception as e:
                    logger.warning(f"Failed to fetch person {person_id}: {e}")

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

            # 7) Build claims list
            claims = []
            if detail.get("claimNumber") or (claim_dto and claim_dto.get("claimNumber")):
                claims.append({
                    "claim_id": detail.get("claimNumber") or claim_dto.get("claimNumber", ""),
                    "claim_type": claim_data.get("claim_type", ""),
                    "status": claim_data.get("case_status", ""),
                })

            context = {
                "building": building_data,
                "unit": unit_data,
                "households": households,
                "persons": persons,
                "claim_data": claim_data,
                "claims": claims,
            }
            logger.info(
                f"Built survey context: building={bool(building_data)}, "
                f"unit={bool(unit_data)}, households={len(households)}, "
                f"persons={len(persons)}"
            )
            return OperationResult.ok(data=context)

        except Exception as e:
            logger.error(f"Failed to get survey context: {e}", exc_info=True)
            return OperationResult.fail(message=str(e))

    # ------------------------------------------------------------------
    # Mapping: survey detail → claim_data dict for ReviewStep
    # ------------------------------------------------------------------

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
                claim_type = raw_type.lower().replace(" claim", "").strip() or raw_type
            priority = claim_dto.get("priority")
            source = claim_dto.get("claimSource") or source

        return {
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
            "evidence_count": summary.get("evidenceCount", 0),
        }

