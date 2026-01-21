# -*- coding: utf-8 -*-
"""
Person Service - Business Logic Layer
======================================
Centralized business logic for Person operations.
Follows DRY, SOLID, Clean Code principles.

This service sits between Controllers and Repositories,
handling all business rules, validation, and data transformations.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from models.person import Person
from repositories.person_repository import PersonRepository
from services.validation.validation_factory import ValidationFactory
from utils.logger import get_logger

logger = get_logger(__name__)


class PersonService:
    """
    Service layer for Person business logic.

    Responsibilities:
    - Validate person data before persistence
    - Apply business rules (age calculation, name formatting)
    - Handle duplicate detection logic
    - Transform UI data to domain models
    - Coordinate with validation services
    """

    def __init__(self, repository: PersonRepository):
        """
        Initialize PersonService.

        Args:
            repository: PersonRepository instance for data access
        """
        self.repository = repository
        self.validator = ValidationFactory.get_validator('person')

    def create_person(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create person with complete validation and business rules.

        Args:
            data: Dictionary containing person data from UI
                Required fields:
                - first_name: str
                - father_name: str
                - grandfather_name: str (optional)
                - family_name: str
                - national_id: str (11 digits)
                - gender: str ('M' or 'F')
                - birth_year: int
                - nationality: str

        Returns:
            Dictionary with:
            - success: bool
            - person: Person object if successful
            - error: str if failed
            - validation_errors: List[str] if validation failed

        Business Rules Applied:
        1. National ID must be unique and valid (11 digits)
        2. Birth year must result in age between 0-120
        3. Full name is auto-generated from name parts
        4. Gender must be 'M' or 'F'
        5. Check for potential duplicates
        """
        logger.info(f"PersonService.create_person called with data: {data.get('first_name')}")

        # Step 1: Validate input data
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            logger.warning(f"Person validation failed: {validation_result.errors}")
            return {
                'success': False,
                'person': None,
                'error': 'Validation failed',
                'validation_errors': validation_result.errors
            }

        # Step 2: Apply business transformations
        try:
            transformed_data = self._apply_business_rules(data)
        except ValueError as e:
            logger.error(f"Business rule application failed: {e}")
            return {
                'success': False,
                'person': None,
                'error': str(e),
                'validation_errors': []
            }

        # Step 3: Check for duplicates
        duplicate_check = self._check_duplicates(transformed_data)
        if duplicate_check['has_duplicates']:
            logger.warning(f"Potential duplicate found: {duplicate_check['matches']}")
            # Note: Still proceed but return warning
            transformed_data['duplicate_warning'] = duplicate_check

        # Step 4: Create Person model
        try:
            person = self._create_person_model(transformed_data)
        except Exception as e:
            logger.error(f"Failed to create Person model: {e}")
            return {
                'success': False,
                'person': None,
                'error': f'Failed to create person model: {e}',
                'validation_errors': []
            }

        # Step 5: Persist to database
        try:
            created_person = self.repository.create(person)
            logger.info(f"Person created successfully: {created_person.person_id}")

            return {
                'success': True,
                'person': created_person,
                'error': None,
                'validation_errors': [],
                'duplicate_warning': duplicate_check if duplicate_check['has_duplicates'] else None
            }

        except Exception as e:
            logger.error(f"Failed to persist person: {e}")
            return {
                'success': False,
                'person': None,
                'error': f'Database error: {e}',
                'validation_errors': []
            }

    def update_person(self, person_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing person with validation.

        Args:
            person_id: UUID of person to update
            data: Updated person data

        Returns:
            Result dictionary similar to create_person
        """
        logger.info(f"PersonService.update_person called for ID: {person_id}")

        # Validate
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            return {
                'success': False,
                'person': None,
                'error': 'Validation failed',
                'validation_errors': validation_result.errors
            }

        # Get existing person
        existing_person = self.repository.get(person_id)
        if not existing_person:
            return {
                'success': False,
                'person': None,
                'error': f'Person not found: {person_id}',
                'validation_errors': []
            }

        # Apply business rules
        try:
            transformed_data = self._apply_business_rules(data)
        except ValueError as e:
            return {
                'success': False,
                'person': None,
                'error': str(e),
                'validation_errors': []
            }

        # Update person fields
        for key, value in transformed_data.items():
            if hasattr(existing_person, key):
                setattr(existing_person, key, value)

        # Save
        try:
            updated_person = self.repository.update(existing_person)
            logger.info(f"Person updated successfully: {person_id}")

            return {
                'success': True,
                'person': updated_person,
                'error': None,
                'validation_errors': []
            }
        except Exception as e:
            logger.error(f"Failed to update person: {e}")
            return {
                'success': False,
                'person': None,
                'error': f'Database error: {e}',
                'validation_errors': []
            }

    def get_person(self, person_id: str) -> Optional[Person]:
        """
        Get person by ID.

        Args:
            person_id: UUID of person

        Returns:
            Person object or None
        """
        return self.repository.get(person_id)

    def search_persons(self, criteria: Dict[str, Any]) -> List[Person]:
        """
        Search persons with criteria.

        Args:
            criteria: Search criteria dict
                - national_id: str
                - full_name: str
                - gender: str
                - nationality: str

        Returns:
            List of matching Person objects
        """
        return self.repository.search(criteria)

    def delete_person(self, person_id: str) -> Dict[str, Any]:
        """
        Delete person (soft delete).

        Args:
            person_id: UUID of person to delete

        Returns:
            Result dictionary
        """
        try:
            # Check if person exists
            person = self.repository.get(person_id)
            if not person:
                return {
                    'success': False,
                    'error': f'Person not found: {person_id}'
                }

            # Check if person has relationships (business rule)
            # TODO: Add relationship check via RelationService

            # Delete
            self.repository.delete(person_id)
            logger.info(f"Person deleted: {person_id}")

            return {
                'success': True,
                'error': None
            }

        except Exception as e:
            logger.error(f"Failed to delete person: {e}")
            return {
                'success': False,
                'error': f'Database error: {e}'
            }

    # ==================== Private Helper Methods ====================

    def _apply_business_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply business transformations to person data.

        Transformations:
        1. Generate full_name from name parts
        2. Calculate age from birth_year
        3. Normalize phone numbers
        4. Uppercase national_id

        Args:
            data: Raw person data

        Returns:
            Transformed data dictionary

        Raises:
            ValueError: If business rules are violated
        """
        transformed = data.copy()

        # 1. Generate full_name (Arabic format: First Father Grandfather Family)
        name_parts = [
            transformed.get('first_name', '').strip(),
            transformed.get('father_name', '').strip(),
            transformed.get('grandfather_name', '').strip(),
            transformed.get('family_name', '').strip()
        ]
        transformed['full_name'] = ' '.join(filter(None, name_parts))

        # 2. Calculate age from birth_year
        if 'birth_year' in transformed:
            birth_year = int(transformed['birth_year'])
            current_year = datetime.now().year
            age = current_year - birth_year

            if age < 0 or age > 120:
                raise ValueError(f"Invalid age calculated: {age}. Birth year: {birth_year}")

            transformed['age'] = age

        # 3. Normalize national_id (uppercase, remove spaces)
        if 'national_id' in transformed and transformed['national_id']:
            transformed['national_id'] = transformed['national_id'].upper().replace(' ', '')

        # 4. Normalize phone numbers (remove spaces, dashes)
        if 'phone_number' in transformed and transformed['phone_number']:
            phone = transformed['phone_number'].replace(' ', '').replace('-', '')
            transformed['phone_number'] = phone

        # 5. Set default values
        transformed.setdefault('status', 'active')
        transformed.setdefault('created_at', datetime.now())

        return transformed

    def _check_duplicates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for potential duplicate persons.

        Duplicate detection rules:
        1. Exact national_id match (if provided)
        2. Similar name + same birth_year
        3. Same phone_number

        Args:
            data: Person data to check

        Returns:
            Dictionary with:
            - has_duplicates: bool
            - matches: List of potential duplicate Person objects
            - match_reasons: List[str] explaining why each is a duplicate
        """
        matches = []
        match_reasons = []

        # Check 1: National ID (exact match)
        if data.get('national_id'):
            existing = self.repository.find_by_national_id(data['national_id'])
            if existing:
                matches.append(existing)
                match_reasons.append(f"Exact national ID match: {data['national_id']}")

        # Check 2: Similar name + birth year
        if data.get('full_name') and data.get('birth_year'):
            similar = self.repository.find_similar_names(
                data['full_name'],
                birth_year=data['birth_year']
            )
            for person in similar:
                if person not in matches:
                    matches.append(person)
                    match_reasons.append(f"Similar name and birth year")

        # Check 3: Phone number
        if data.get('phone_number'):
            by_phone = self.repository.find_by_phone(data['phone_number'])
            for person in by_phone:
                if person not in matches:
                    matches.append(person)
                    match_reasons.append(f"Same phone number: {data['phone_number']}")

        return {
            'has_duplicates': len(matches) > 0,
            'matches': matches,
            'match_reasons': match_reasons
        }

    def _create_person_model(self, data: Dict[str, Any]) -> Person:
        """
        Create Person domain model from data dict.

        Args:
            data: Transformed person data

        Returns:
            Person model instance

        Raises:
            Exception: If model creation fails
        """
        person = Person(
            first_name=data.get('first_name'),
            father_name=data.get('father_name'),
            grandfather_name=data.get('grandfather_name'),
            family_name=data.get('family_name'),
            full_name=data.get('full_name'),
            national_id=data.get('national_id'),
            gender=data.get('gender'),
            birth_year=data.get('birth_year'),
            age=data.get('age'),
            nationality=data.get('nationality'),
            phone_number=data.get('phone_number'),
            status=data.get('status', 'active')
        )

        return person
