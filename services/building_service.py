# -*- coding: utf-8 -*-
"""
Building Service - Business Logic Layer
========================================
Centralized business logic for Building operations.
Follows DRY, SOLID, Clean Code principles.

This service handles:
- Building ID generation (17 digits)
- Geometry validation (polygons via PostGIS)
- Administrative hierarchy validation
- Building assignment to field teams
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from models.building import Building
from repositories.building_repository import BuildingRepository
from services.postgis_service import PostGISService
from services.validation.validation_factory import ValidationFactory
from utils.logger import get_logger

logger = get_logger(__name__)


class BuildingService:
    """
    Service layer for Building business logic.

    Responsibilities:
    - Generate unique building IDs (17-digit format)
    - Validate building geometry (polygons)
    - Apply administrative hierarchy rules
    - Calculate building area from geometry
    - Handle building-field team assignments
    """

    def __init__(
        self,
        repository: BuildingRepository,
        postgis_service: Optional[PostGISService] = None
    ):
        """
        Initialize BuildingService.

        Args:
            repository: BuildingRepository for data access
            postgis_service: Optional PostGISService for spatial operations
        """
        self.repository = repository
        self.postgis_service = postgis_service
        self.validator = ValidationFactory.get_validator('building')

    def create_building(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create building with complete validation and business rules.

        Args:
            data: Building data from UI
                Required:
                - governorate_code: str (2 digits)
                - district_code: str (2 digits)
                - sub_district_code: str (2 digits)
                - neighborhood_code: str (3 digits)
                - block_code: str (3 digits)
                - building_number: str (5 digits)
                Optional:
                - building_geometry: str (WKT polygon)
                - building_type: str
                - construction_year: int

        Returns:
            Result dictionary with success, building, error

        Business Rules:
        1. Building ID auto-generated from hierarchy codes
        2. Building ID must be unique (17 digits)
        3. Geometry must be valid polygon (if provided)
        4. Area calculated from geometry
        5. All hierarchy codes must exist in vocabulary
        """
        logger.info("BuildingService.create_building called")

        # Step 1: Validate input
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            logger.warning(f"Building validation failed: {validation_result.errors}")
            return {
                'success': False,
                'building': None,
                'error': 'Validation failed',
                'validation_errors': validation_result.errors
            }

        # Step 2: Generate Building ID
        try:
            building_id = self._generate_building_id(data)
            data['building_id'] = building_id
        except ValueError as e:
            logger.error(f"Building ID generation failed: {e}")
            return {
                'success': False,
                'building': None,
                'error': str(e),
                'validation_errors': []
            }

        # Step 3: Check uniqueness
        existing = self.repository.get(building_id)
        if existing:
            return {
                'success': False,
                'building': None,
                'error': f'Building ID already exists: {building_id}',
                'validation_errors': []
            }

        # Step 4: Validate and process geometry
        if data.get('building_geometry'):
            geometry_result = self._process_geometry(data['building_geometry'])
            if not geometry_result['valid']:
                return {
                    'success': False,
                    'building': None,
                    'error': f"Invalid geometry: {geometry_result['error']}",
                    'validation_errors': []
                }
            # Add calculated area
            data['area_sqm'] = geometry_result['area_sqm']

        # Step 5: Apply business transformations
        try:
            transformed_data = self._apply_business_rules(data)
        except ValueError as e:
            return {
                'success': False,
                'building': None,
                'error': str(e),
                'validation_errors': []
            }

        # Step 6: Create Building model
        try:
            building = self._create_building_model(transformed_data)
        except Exception as e:
            logger.error(f"Failed to create Building model: {e}")
            return {
                'success': False,
                'building': None,
                'error': f'Failed to create building: {e}',
                'validation_errors': []
            }

        # Step 7: Persist
        try:
            created_building = self.repository.create(building)
            logger.info(f"Building created successfully: {created_building.building_id}")

            return {
                'success': True,
                'building': created_building,
                'error': None,
                'validation_errors': []
            }

        except Exception as e:
            logger.error(f"Failed to persist building: {e}")
            return {
                'success': False,
                'building': None,
                'error': f'Database error: {e}',
                'validation_errors': []
            }

    def update_building(self, building_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing building.

        Args:
            building_id: 17-digit building ID
            data: Updated building data

        Returns:
            Result dictionary
        """
        logger.info(f"BuildingService.update_building: {building_id}")

        # Validate
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            return {
                'success': False,
                'building': None,
                'error': 'Validation failed',
                'validation_errors': validation_result.errors
            }

        # Get existing
        existing = self.repository.get(building_id)
        if not existing:
            return {
                'success': False,
                'building': None,
                'error': f'Building not found: {building_id}',
                'validation_errors': []
            }

        # Validate geometry if changed
        if data.get('building_geometry'):
            geometry_result = self._process_geometry(data['building_geometry'])
            if not geometry_result['valid']:
                return {
                    'success': False,
                    'building': None,
                    'error': f"Invalid geometry: {geometry_result['error']}",
                    'validation_errors': []
                }
            data['area_sqm'] = geometry_result['area_sqm']

        # Apply business rules
        try:
            transformed_data = self._apply_business_rules(data)
        except ValueError as e:
            return {
                'success': False,
                'building': None,
                'error': str(e),
                'validation_errors': []
            }

        # Update fields
        for key, value in transformed_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)

        # Save
        try:
            updated_building = self.repository.update(existing)
            logger.info(f"Building updated: {building_id}")

            return {
                'success': True,
                'building': updated_building,
                'error': None,
                'validation_errors': []
            }
        except Exception as e:
            logger.error(f"Failed to update building: {e}")
            return {
                'success': False,
                'building': None,
                'error': f'Database error: {e}',
                'validation_errors': []
            }

    def get_building(self, building_id: str) -> Optional[Building]:
        """Get building by ID."""
        return self.repository.get(building_id)

    def search_buildings(self, criteria: Dict[str, Any]) -> List[Building]:
        """Search buildings with criteria."""
        return self.repository.search(criteria)

    def assign_to_field_team(
        self,
        building_id: str,
        team_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Assign building to field team.

        Business Rule: Building must be in 'pending' or 'unassigned' status.

        Args:
            building_id: Building to assign
            team_id: Field team UUID
            user_id: User performing assignment

        Returns:
            Result dictionary
        """
        building = self.repository.get(building_id)
        if not building:
            return {
                'success': False,
                'error': f'Building not found: {building_id}'
            }

        # Business rule: Check status
        if building.status not in ['pending', 'unassigned', 'draft']:
            return {
                'success': False,
                'error': f'Cannot assign building with status: {building.status}'
            }

        # Assign
        try:
            building.assigned_team_id = team_id
            building.status = 'assigned'
            building.assigned_at = datetime.now()
            building.assigned_by = user_id

            updated = self.repository.update(building)
            logger.info(f"Building {building_id} assigned to team {team_id}")

            return {
                'success': True,
                'building': updated,
                'error': None
            }

        except Exception as e:
            logger.error(f"Assignment failed: {e}")
            return {
                'success': False,
                'error': f'Database error: {e}'
            }

    # ==================== Private Methods ====================

    def _generate_building_id(self, data: Dict[str, Any]) -> str:
        """
        Generate 17-digit building ID from hierarchy codes.

        Format: GG-DD-SS-NNN-BBB-NNNNN
        - GG: Governorate (2 digits)
        - DD: District (2 digits)
        - SS: Sub-district (2 digits)
        - NNN: Neighborhood (3 digits)
        - BBB: Block (3 digits)
        - NNNNN: Building number (5 digits)

        Args:
            data: Building data with hierarchy codes

        Returns:
            17-digit building ID

        Raises:
            ValueError: If any code is missing or invalid format
        """
        required_codes = [
            ('governorate_code', 2),
            ('district_code', 2),
            ('sub_district_code', 2),
            ('neighborhood_code', 3),
            ('block_code', 3),
            ('building_number', 5)
        ]

        parts = []
        for field, length in required_codes:
            code = data.get(field)
            if not code:
                raise ValueError(f"Missing required field: {field}")

            # Ensure correct length (pad with zeros)
            code_str = str(code).zfill(length)
            if len(code_str) != length:
                raise ValueError(f"{field} must be {length} digits, got: {code}")

            parts.append(code_str)

        # Format: GG-DD-SS-NNN-BBB-NNNNN
        building_id = f"{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}-{parts[4]}-{parts[5]}"

        return building_id

    def _process_geometry(self, wkt: str) -> Dict[str, Any]:
        """
        Validate and process building geometry using PostGIS.

        Args:
            wkt: WKT string of polygon

        Returns:
            Dictionary with:
            - valid: bool
            - error: str (if invalid)
            - area_sqm: float (if valid)
        """
        if not self.postgis_service:
            # No PostGIS - basic validation only
            return {
                'valid': True,
                'error': None,
                'area_sqm': 0.0
            }

        # Use PostGIS for validation
        return self.postgis_service.validate_polygon(wkt)

    def _apply_business_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply business transformations.

        Rules:
        1. Set default status if not provided
        2. Generate reference number
        3. Set timestamps

        Args:
            data: Raw building data

        Returns:
            Transformed data
        """
        transformed = data.copy()

        # Default values
        transformed.setdefault('status', 'draft')
        transformed.setdefault('created_at', datetime.now())
        transformed.setdefault('survey_status', 'pending')

        # Generate reference number if not exists
        if not transformed.get('reference_number'):
            transformed['reference_number'] = self._generate_reference_number(
                transformed['building_id']
            )

        return transformed

    def _generate_reference_number(self, building_id: str) -> str:
        """
        Generate reference number for building.

        Format: BLD-{building_id}-{timestamp}

        Args:
            building_id: 17-digit building ID

        Returns:
            Reference number string
        """
        timestamp = datetime.now().strftime('%Y%m%d')
        return f"BLD-{building_id}-{timestamp}"

    def _create_building_model(self, data: Dict[str, Any]) -> Building:
        """
        Create Building domain model from data dict.

        Args:
            data: Transformed building data

        Returns:
            Building model instance
        """
        building = Building(
            building_id=data['building_id'],
            governorate_code=data['governorate_code'],
            district_code=data['district_code'],
            sub_district_code=data['sub_district_code'],
            neighborhood_code=data['neighborhood_code'],
            block_code=data['block_code'],
            building_number=data['building_number'],
            building_geometry=data.get('building_geometry'),
            area_sqm=data.get('area_sqm'),
            building_type=data.get('building_type'),
            construction_year=data.get('construction_year'),
            status=data.get('status', 'draft'),
            reference_number=data.get('reference_number')
        )

        return building
