# -*- coding: utf-8 -*-
"""
Person Controller
=================
Controller for person management operations.

Handles:
- Person CRUD operations
- Person search and filtering
- Person validation (National ID, phone)
- Person-unit relationships
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from models.person import Person
from repositories.database import Database
from services.api_client import get_api_client
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PersonFilter:
    """Filter criteria for person search."""
    national_id: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    relation_type: Optional[str] = None
    unit_uuid: Optional[str] = None
    building_uuid: Optional[str] = None
    search_text: Optional[str] = None
    limit: int = 100
    offset: int = 0


class PersonController(BaseController):
    """
    Controller for person management.

    Provides a clean interface between UI and data layer for person operations.
    """

    # Signals
    person_created = pyqtSignal(str)  # person_uuid
    person_updated = pyqtSignal(str)  # person_uuid
    person_deleted = pyqtSignal(str)  # person_uuid
    persons_loaded = pyqtSignal(list)  # list of persons
    person_selected = pyqtSignal(object)  # Person object
    duplicate_found = pyqtSignal(str, str)  # person_uuid, match_type

    def __init__(self, db: Database = None, parent=None):
        super().__init__(parent)
        self.db = db
        self._api = get_api_client()

        self._current_person: Optional[Person] = None
        self._persons_cache: List[Person] = []
        self._current_filter = PersonFilter()

    @property
    def current_person(self) -> Optional[Person]:
        """Get currently selected person."""
        return self._current_person

    @property
    def persons(self) -> List[Person]:
        """Get cached persons list."""
        return self._persons_cache

    def create_person(self, data: Dict[str, Any]) -> OperationResult[Person]:
        """
        Create a new person.

        Args:
            data: Person data dictionary

        Returns:
            OperationResult with created Person or error
        """
        self._log_operation("create_person", data=data)

        try:
            self._emit_started("create_person")

            # Validate data
            validation_result = self._validate_person_data(data)
            if not validation_result.success:
                self._emit_error("create_person", validation_result.message)
                return validation_result

            # Create person via API
            result_dto = self._api.create_person(data)
            saved_person = self._api_dto_to_person(result_dto)

            self._emit_completed("create_person", True)
            self.person_created.emit(saved_person.person_uuid)
            self._trigger_callbacks("on_person_created", saved_person)
            return OperationResult.ok(
                data=saved_person,
                message="Person created successfully",
                message_ar="تم إنشاء الشخص بنجاح"
            )

        except Exception as e:
            error_msg = f"Error creating person: {str(e)}"
            self._emit_error("create_person", error_msg)
            return OperationResult.fail(message=error_msg)

    def update_person(self, person_uuid: str, data: Dict[str, Any]) -> OperationResult[Person]:
        """
        Update an existing person.

        Args:
            person_uuid: UUID of person to update
            data: Updated person data

        Returns:
            OperationResult with updated Person or error
        """
        self._log_operation("update_person", person_uuid=person_uuid, data=data)

        try:
            self._emit_started("update_person")

            # Validate data
            validation_result = self._validate_person_data(data, is_update=True)
            if not validation_result.success:
                self._emit_error("update_person", validation_result.message)
                return validation_result

            # Update person via API
            result_dto = self._api.update_person(person_uuid, data)
            updated_person = self._api_dto_to_person(result_dto)

            self._emit_completed("update_person", True)
            self.person_updated.emit(person_uuid)
            self._trigger_callbacks("on_person_updated", updated_person)

            if self._current_person and self._current_person.person_uuid == person_uuid:
                self._current_person = updated_person

            return OperationResult.ok(
                data=updated_person,
                message="Person updated successfully",
                message_ar="تم تحديث الشخص بنجاح"
            )

        except Exception as e:
            error_msg = f"Error updating person: {str(e)}"
            self._emit_error("update_person", error_msg)
            return OperationResult.fail(message=error_msg)

    def delete_person(self, person_uuid: str) -> OperationResult[bool]:
        """
        Delete a person.

        Args:
            person_uuid: UUID of person to delete

        Returns:
            OperationResult with success status
        """
        self._log_operation("delete_person", person_uuid=person_uuid)

        try:
            self._emit_started("delete_person")

            # Delete person via API
            self._api.delete_person(person_uuid)

            self._emit_completed("delete_person", True)
            self.person_deleted.emit(person_uuid)
            self._trigger_callbacks("on_person_deleted", person_uuid)

            if self._current_person and self._current_person.person_uuid == person_uuid:
                self._current_person = None

            return OperationResult.ok(
                data=True,
                message="Person deleted successfully",
                message_ar="تم حذف الشخص بنجاح"
            )

        except Exception as e:
            error_msg = f"Error deleting person: {str(e)}"
            self._emit_error("delete_person", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_person(self, person_uuid: str) -> OperationResult[Person]:
        """
        Get a person by UUID via API.

        Args:
            person_uuid: UUID of person

        Returns:
            OperationResult with Person or error
        """
        try:
            result = self._api.get_persons(search=person_uuid, page=1, page_size=1)
            items = result.get("items", []) if isinstance(result, dict) else []
            # Search by exact id match
            dto = next((p for p in items if p.get("id") == person_uuid), None)
            if dto:
                return OperationResult.ok(data=self._api_dto_to_person(dto))
            return OperationResult.fail(
                message="Person not found",
                message_ar="الشخص غير موجود"
            )
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_person_by_national_id(self, national_id: str) -> OperationResult[Person]:
        """
        Get a person by national ID via API.

        Args:
            national_id: National ID

        Returns:
            OperationResult with Person or error
        """
        try:
            result = self._api.get_persons(national_id=national_id, page=1, page_size=1)
            items = result.get("items", []) if isinstance(result, dict) else []
            if items:
                return OperationResult.ok(data=self._api_dto_to_person(items[0]))
            return OperationResult.fail(
                message="Person not found",
                message_ar="الشخص غير موجود"
            )
        except Exception as e:
            return OperationResult.fail(message=str(e))

    def select_person(self, person_uuid: str) -> OperationResult[Person]:
        """
        Select a person as current.

        Args:
            person_uuid: UUID of person to select

        Returns:
            OperationResult with selected Person
        """
        result = self.get_person(person_uuid)

        if result.success:
            self._current_person = result.data
            self.person_selected.emit(result.data)
            self._trigger_callbacks("on_person_selected", result.data)

        return result

    def clear_selection(self):
        """Clear current person selection."""
        self._current_person = None
        self.person_selected.emit(None)

    def load_persons(self, filter_: Optional[PersonFilter] = None) -> OperationResult[List[Person]]:
        """
        Load persons with optional filter via API.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Persons
        """
        try:
            self._emit_started("load_persons")

            filter_ = filter_ or self._current_filter

            result = self._api.get_persons(
                search=filter_.search_text,
                national_id=filter_.national_id,
                page=1,
                page_size=filter_.limit
            )
            items = result.get("items", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
            persons = [self._api_dto_to_person(dto) for dto in items]

            self._persons_cache = persons
            self._current_filter = filter_

            self._emit_completed("load_persons", True)
            self.persons_loaded.emit(persons)

            return OperationResult.ok(data=persons)

        except Exception as e:
            error_msg = f"Error loading persons: {str(e)}"
            self._emit_error("load_persons", error_msg)
            return OperationResult.fail(message=error_msg)

    def search_persons(self, search_text: str) -> OperationResult[List[Person]]:
        """
        Search persons by text.

        Args:
            search_text: Text to search for

        Returns:
            OperationResult with list of matching Persons
        """
        filter_ = PersonFilter(search_text=search_text)
        return self.load_persons(filter_)

    def get_persons_for_unit(self, unit_uuid: str) -> OperationResult[List[Person]]:
        """
        Get persons related to a unit via API.

        Args:
            unit_uuid: Unit UUID

        Returns:
            OperationResult with list of Persons
        """
        filter_ = PersonFilter(unit_uuid=unit_uuid)
        return self.load_persons(filter_)

    def get_persons_for_building(self, building_uuid: str) -> OperationResult[List[Person]]:
        """
        Get persons related to a building via API.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult with list of Persons
        """
        filter_ = PersonFilter(building_uuid=building_uuid)
        return self.load_persons(filter_)

    def _api_dto_to_person(self, dto: Dict[str, Any]) -> Person:
        """Convert API DTO (camelCase) to Person model."""
        return Person(
            person_uuid=dto.get("id") or dto.get("personUuid") or "",
            first_name=dto.get("firstNameArabic") or dto.get("firstName") or "",
            last_name=dto.get("familyNameArabic") or dto.get("familyName") or "",
            father_name=dto.get("fatherNameArabic") or dto.get("fatherName") or "",
            mother_name=dto.get("motherNameArabic") or dto.get("motherName") or "",
            full_name=dto.get("fullName") or (
                f"{dto.get('firstNameArabic', '')} {dto.get('familyNameArabic', '')}".strip()
            ),
            national_id=dto.get("nationalId") or dto.get("national_id") or "",
            gender=str(dto.get("gender") or ""),
            nationality=str(dto.get("nationality") or ""),
            birth_date=dto.get("dateOfBirth") or "",
            phone=dto.get("mobileNumber") or dto.get("phone") or "",
            landline=dto.get("phoneNumber") or dto.get("landline") or "",
            email=dto.get("email") or "",
        )

    def _validate_person_data(
        self,
        data: Dict[str, Any],
        is_update: bool = False
    ) -> OperationResult:
        """Validate person data."""
        errors = []

        # Required fields for new persons
        if not is_update:
            required = ["full_name"]
            for field in required:
                if not data.get(field):
                    errors.append(f"Missing required field: {field}")

        # Validate national ID format if provided
        if data.get("national_id"):
            if not self._validate_national_id(data["national_id"]):
                errors.append("Invalid national ID format")

        # Validate phone number format if provided
        if data.get("phone_number"):
            if not self._validate_phone_number(data["phone_number"]):
                errors.append("Invalid phone number format")

        if errors:
            return OperationResult.fail(
                message="; ".join(errors),
                message_ar="أخطاء التحقق من البيانات",
                errors=errors
            )

        return OperationResult.ok()

    def _validate_national_id(self, national_id: str) -> bool:
        """Validate Syrian/Iraqi national ID format."""
        # Remove spaces and dashes
        clean_id = national_id.replace(" ", "").replace("-", "")

        # Syrian ID: 11 digits
        # Iraqi ID: varies
        return len(clean_id) >= 9 and clean_id.isdigit()

    def _validate_phone_number(self, phone: str) -> bool:
        """Validate phone number format."""
        import re
        # Remove spaces and dashes
        clean_phone = phone.replace(" ", "").replace("-", "")

        # Syrian/Iraqi phone patterns
        pattern = r"^(\+?963|0)?9\d{8}$|^(\+?964|0)?7\d{9}$"
        return bool(re.match(pattern, clean_phone))

    def _check_duplicates(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check for potential duplicate persons via API."""
        try:
            if data.get("national_id"):
                result = self._api.get_persons(national_id=data["national_id"], page=1, page_size=1)
                items = result.get("items", []) if isinstance(result, dict) else []
                if items:
                    return {"person_uuid": items[0].get("id", ""), "match_type": "national_id"}
        except Exception:
            pass
        return None

    def get_statistics(self) -> OperationResult[Dict[str, Any]]:
        """
        Get person statistics via API.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            result = self._api.get_persons(page=1, page_size=1)
            total = result.get("totalCount", 0) if isinstance(result, dict) else 0
            stats = {"total": total}
            return OperationResult.ok(data=stats)
        except Exception as e:
            return OperationResult.fail(message=str(e))
