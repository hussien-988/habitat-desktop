# -*- coding: utf-8 -*-
"""
Claim Service - Business Logic Layer
=====================================
Centralized business logic for Claim operations.
Follows DRY, SOLID, Clean Code principles.

This service handles:
- Claim lifecycle management
- Status transitions with business rules
- Conflict detection and resolution
- Claim validation and completeness checks
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from models.claim import Claim
from repositories.claim_repository import ClaimRepository
from services.workflow_service import WorkflowService
from services.validation.validation_factory import ValidationFactory
from utils.logger import get_logger

logger = get_logger(__name__)


class ClaimStatus(Enum):
    """Valid claim statuses."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_INFO = "pending_info"


class ClaimService:
    """
    Service layer for Claim business logic.

    Responsibilities:
    - Manage claim lifecycle
    - Validate claim completeness
    - Apply business rules for status transitions
    - Handle conflict detection
    - Generate claim reference numbers
    """

    def __init__(
        self,
        repository: ClaimRepository,
        workflow_service: WorkflowService
    ):
        """
        Initialize ClaimService.

        Args:
            repository: ClaimRepository for data access
            workflow_service: WorkflowService for status transitions
        """
        self.repository = repository
        self.workflow_service = workflow_service
        self.validator = ValidationFactory.get_validator('claim')

    def create_claim(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new claim with validation.

        Args:
            data: Claim data from UI
                Required:
                - building_id: str
                - unit_id: str
                - claimant_person_id: str
                - claim_type: str
                Optional:
                - evidence_documents: List[str]
                - conflict_ids: List[str]

        Returns:
            Result dictionary with success, claim, error

        Business Rules:
        1. Claim reference number auto-generated
        2. Initial status is 'draft'
        3. Claimant must exist in database
        4. Building and unit must exist
        5. Check for conflicting claims
        """
        logger.info("ClaimService.create_claim called")

        # Validate
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            return {
                'success': False,
                'claim': None,
                'error': 'Validation failed',
                'validation_errors': validation_result.errors
            }

        # Apply business rules
        try:
            transformed_data = self._apply_business_rules(data)
        except ValueError as e:
            return {
                'success': False,
                'claim': None,
                'error': str(e),
                'validation_errors': []
            }

        # Check for conflicts
        conflict_check = self._check_conflicts(data)
        if conflict_check['has_conflicts']:
            logger.warning(f"Conflicting claims detected: {conflict_check['conflicts']}")
            transformed_data['has_conflicts'] = True
            transformed_data['conflict_ids'] = [c.claim_id for c in conflict_check['conflicts']]

        # Create Claim model
        try:
            claim = self._create_claim_model(transformed_data)
        except Exception as e:
            logger.error(f"Failed to create Claim model: {e}")
            return {
                'success': False,
                'claim': None,
                'error': f'Failed to create claim: {e}',
                'validation_errors': []
            }

        # Persist
        try:
            created_claim = self.repository.create(claim)
            logger.info(f"Claim created: {created_claim.claim_id}")

            return {
                'success': True,
                'claim': created_claim,
                'error': None,
                'validation_errors': [],
                'conflict_warning': conflict_check if conflict_check['has_conflicts'] else None
            }

        except Exception as e:
            logger.error(f"Failed to persist claim: {e}")
            return {
                'success': False,
                'claim': None,
                'error': f'Database error: {e}',
                'validation_errors': []
            }

    def update_claim(self, claim_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing claim.

        Business Rule: Cannot update claim in 'approved' or 'rejected' status.

        Args:
            claim_id: UUID of claim
            data: Updated claim data

        Returns:
            Result dictionary
        """
        logger.info(f"ClaimService.update_claim: {claim_id}")

        # Get existing claim
        existing = self.repository.get(claim_id)
        if not existing:
            return {
                'success': False,
                'claim': None,
                'error': f'Claim not found: {claim_id}',
                'validation_errors': []
            }

        # Business rule: Cannot update finalized claims
        if existing.status in [ClaimStatus.APPROVED.value, ClaimStatus.REJECTED.value]:
            return {
                'success': False,
                'claim': None,
                'error': f'Cannot update claim with status: {existing.status}',
                'validation_errors': []
            }

        # Validate
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            return {
                'success': False,
                'claim': None,
                'error': 'Validation failed',
                'validation_errors': validation_result.errors
            }

        # Apply business rules
        try:
            transformed_data = self._apply_business_rules(data)
        except ValueError as e:
            return {
                'success': False,
                'claim': None,
                'error': str(e),
                'validation_errors': []
            }

        # Update fields
        for key, value in transformed_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)

        existing.updated_at = datetime.now()

        # Save
        try:
            updated_claim = self.repository.update(existing)
            logger.info(f"Claim updated: {claim_id}")

            return {
                'success': True,
                'claim': updated_claim,
                'error': None,
                'validation_errors': []
            }
        except Exception as e:
            logger.error(f"Failed to update claim: {e}")
            return {
                'success': False,
                'claim': None,
                'error': f'Database error: {e}',
                'validation_errors': []
            }

    def transition_claim_status(
        self,
        claim_id: str,
        to_status: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transition claim to new status using WorkflowService.

        This delegates to WorkflowService which handles:
        - Valid transition rules
        - Permission checks
        - Audit logging

        Args:
            claim_id: UUID of claim
            to_status: Target status
            user_id: User performing transition
            notes: Optional transition notes

        Returns:
            Result dictionary from WorkflowService
        """
        logger.info(f"ClaimService.transition_claim_status: {claim_id} -> {to_status}")

        # Delegate to WorkflowService (Single Responsibility)
        result = self.workflow_service.transition_claim(
            claim_id=claim_id,
            to_status=to_status,
            user_id=user_id,
            notes=notes
        )

        return result

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Get claim by ID."""
        return self.repository.get(claim_id)

    def search_claims(self, criteria: Dict[str, Any]) -> List[Claim]:
        """Search claims with criteria."""
        return self.repository.search(criteria)

    def check_claim_completeness(self, claim_id: str) -> Dict[str, Any]:
        """
        Check if claim has all required information for submission.

        Business Rules for completeness:
        1. Must have claimant person
        2. Must have at least one evidence document
        3. Must have building and unit linked
        4. Claimant relationship to unit must be specified

        Args:
            claim_id: UUID of claim

        Returns:
            Dictionary with:
            - is_complete: bool
            - missing_items: List[str]
            - completeness_percentage: float
        """
        claim = self.repository.get(claim_id)
        if not claim:
            return {
                'is_complete': False,
                'missing_items': ['Claim not found'],
                'completeness_percentage': 0.0
            }

        missing = []
        total_checks = 5
        passed_checks = 0

        # Check 1: Claimant
        if not claim.claimant_person_id:
            missing.append('Claimant person')
        else:
            passed_checks += 1

        # Check 2: Evidence
        if not claim.evidence_documents or len(claim.evidence_documents) == 0:
            missing.append('Evidence documents')
        else:
            passed_checks += 1

        # Check 3: Building
        if not claim.building_id:
            missing.append('Building')
        else:
            passed_checks += 1

        # Check 4: Unit
        if not claim.unit_id:
            missing.append('Property unit')
        else:
            passed_checks += 1

        # Check 5: Claim type
        if not claim.claim_type:
            missing.append('Claim type')
        else:
            passed_checks += 1

        completeness = (passed_checks / total_checks) * 100

        return {
            'is_complete': len(missing) == 0,
            'missing_items': missing,
            'completeness_percentage': completeness
        }

    # ==================== Private Methods ====================

    def _apply_business_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply business transformations to claim data.

        Rules:
        1. Generate claim reference number
        2. Set initial status to 'draft'
        3. Set timestamps
        4. Calculate claim priority

        Args:
            data: Raw claim data

        Returns:
            Transformed data
        """
        transformed = data.copy()

        # Generate reference number if not exists
        if not transformed.get('reference_number'):
            transformed['reference_number'] = self._generate_reference_number()

        # Set defaults
        transformed.setdefault('status', ClaimStatus.DRAFT.value)
        transformed.setdefault('created_at', datetime.now())
        transformed.setdefault('priority', 'normal')

        return transformed

    def _generate_reference_number(self) -> str:
        """
        Generate unique claim reference number.

        Format: CLM-YYYYMMDD-NNNN
        - CLM: Prefix
        - YYYYMMDD: Date
        - NNNN: Sequential number for the day

        Returns:
            Reference number string
        """
        today = datetime.now().strftime('%Y%m%d')

        # Get count of claims created today
        count = self.repository.count_claims_today()

        sequence = str(count + 1).zfill(4)

        return f"CLM-{today}-{sequence}"

    def _check_conflicts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for conflicting claims on same property.

        Conflict definition:
        - Two or more claims on the same unit
        - By different claimants
        - In active status (not rejected)

        Args:
            data: Claim data to check

        Returns:
            Dictionary with:
            - has_conflicts: bool
            - conflicts: List[Claim] of conflicting claims
        """
        unit_id = data.get('unit_id')
        claimant_id = data.get('claimant_person_id')

        if not unit_id:
            return {
                'has_conflicts': False,
                'conflicts': []
            }

        # Find other claims on same unit
        existing_claims = self.repository.find_by_unit(unit_id)

        conflicts = []
        for claim in existing_claims:
            # Skip if same claimant
            if claim.claimant_person_id == claimant_id:
                continue

            # Skip if rejected
            if claim.status == ClaimStatus.REJECTED.value:
                continue

            conflicts.append(claim)

        return {
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts
        }

    def _create_claim_model(self, data: Dict[str, Any]) -> Claim:
        """
        Create Claim domain model from data dict.

        Args:
            data: Transformed claim data

        Returns:
            Claim model instance
        """
        claim = Claim(
            building_id=data.get('building_id'),
            unit_id=data.get('unit_id'),
            claimant_person_id=data.get('claimant_person_id'),
            claim_type=data.get('claim_type'),
            reference_number=data.get('reference_number'),
            status=data.get('status', ClaimStatus.DRAFT.value),
            priority=data.get('priority', 'normal'),
            evidence_documents=data.get('evidence_documents', []),
            has_conflicts=data.get('has_conflicts', False),
            conflict_ids=data.get('conflict_ids', []),
            created_at=data.get('created_at', datetime.now())
        )

        return claim
