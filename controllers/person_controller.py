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
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal

from controllers.base_controller import BaseController, OperationResult
from models.person import Person
from repositories.person_repository import PersonRepository
from repositories.database import Database
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

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.repository = PersonRepository(db)

        self._current_person: Optional[Person] = None
        self._persons_cache: List[Person] = []
        self._current_filter = PersonFilter()

    # ==================== Properties ====================

    @property
    def current_person(self) -> Optional[Person]:
        """Get currently selected person."""
        return self._current_person

    @property
    def persons(self) -> List[Person]:
        """Get cached persons list."""
        return self._persons_cache

    # ==================== CRUD Operations ====================

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

            # Check for duplicates
            duplicate = self._check_duplicates(data)
            if duplicate:
                self.duplicate_found.emit(duplicate["person_uuid"], duplicate["match_type"])
                # Return warning but allow creation
                logger.warning(f"Potential duplicate found: {duplicate}")

            # Create person
            person = Person(**data)
            saved_person = self.repository.create(person)

            if saved_person:
                self._emit_completed("create_person", True)
                self.person_created.emit(saved_person.person_uuid)
                self._trigger_callbacks("on_person_created", saved_person)
                return OperationResult.ok(
                    data=saved_person,
                    message="Person created successfully",
                    message_ar="تم إنشاء الشخص بنجاح"
                )
            else:
                self._emit_error("create_person", "Failed to create person")
                return OperationResult.fail(
                    message="Failed to create person",
                    message_ar="فشل في إنشاء الشخص"
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

            # Get existing person
            existing = self.repository.get_by_uuid(person_uuid)
            if not existing:
                self._emit_error("update_person", "Person not found")
                return OperationResult.fail(
                    message="Person not found",
                    message_ar="الشخص غير موجود"
                )

            # Validate data
            validation_result = self._validate_person_data(data, is_update=True)
            if not validation_result.success:
                self._emit_error("update_person", validation_result.message)
                return validation_result

            # Update person
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            existing.updated_at = datetime.now()

            updated_person = self.repository.update(existing)

            if updated_person:
                self._emit_completed("update_person", True)
                self.person_updated.emit(person_uuid)
                self._trigger_callbacks("on_person_updated", updated_person)

                # Update current person if it's the one being edited
                if self._current_person and self._current_person.person_uuid == person_uuid:
                    self._current_person = updated_person

                return OperationResult.ok(
                    data=updated_person,
                    message="Person updated successfully",
                    message_ar="تم تحديث الشخص بنجاح"
                )
            else:
                self._emit_error("update_person", "Failed to update person")
                return OperationResult.fail(
                    message="Failed to update person",
                    message_ar="فشل في تحديث الشخص"
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

            # Check if person exists
            existing = self.repository.get_by_uuid(person_uuid)
            if not existing:
                self._emit_error("delete_person", "Person not found")
                return OperationResult.fail(
                    message="Person not found",
                    message_ar="الشخص غير موجود"
                )

            # Check if person has dependencies
            if self._has_dependencies(person_uuid):
                return OperationResult.fail(
                    message="Cannot delete person with active claims or relations",
                    message_ar="لا يمكن حذف شخص له مطالبات أو علاقات نشطة"
                )

            # Delete person
            success = self.repository.delete(person_uuid)

            if success:
                self._emit_completed("delete_person", True)
                self.person_deleted.emit(person_uuid)
                self._trigger_callbacks("on_person_deleted", person_uuid)

                # Clear current person if it was deleted
                if self._current_person and self._current_person.person_uuid == person_uuid:
                    self._current_person = None

                return OperationResult.ok(
                    data=True,
                    message="Person deleted successfully",
                    message_ar="تم حذف الشخص بنجاح"
                )
            else:
                self._emit_error("delete_person", "Failed to delete person")
                return OperationResult.fail(
                    message="Failed to delete person",
                    message_ar="فشل في حذف الشخص"
                )

        except Exception as e:
            error_msg = f"Error deleting person: {str(e)}"
            self._emit_error("delete_person", error_msg)
            return OperationResult.fail(message=error_msg)

    def get_person(self, person_uuid: str) -> OperationResult[Person]:
        """
        Get a person by UUID.

        Args:
            person_uuid: UUID of person

        Returns:
            OperationResult with Person or error
        """
        try:
            person = self.repository.get_by_uuid(person_uuid)

            if person:
                return OperationResult.ok(data=person)
            else:
                return OperationResult.fail(
                    message="Person not found",
                    message_ar="الشخص غير موجود"
                )

        except Exception as e:
            return OperationResult.fail(message=str(e))

    def get_person_by_national_id(self, national_id: str) -> OperationResult[Person]:
        """
        Get a person by national ID.

        Args:
            national_id: National ID

        Returns:
            OperationResult with Person or error
        """
        try:
            person = self.repository.get_by_national_id(national_id)

            if person:
                return OperationResult.ok(data=person)
            else:
                return OperationResult.fail(
                    message="Person not found",
                    message_ar="الشخص غير موجود"
                )

        except Exception as e:
            return OperationResult.fail(message=str(e))

    # ==================== Selection ====================

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

    # ==================== Search and Filter ====================

    def load_persons(self, filter_: Optional[PersonFilter] = None) -> OperationResult[List[Person]]:
        """
        Load persons with optional filter.

        Args:
            filter_: Optional filter criteria

        Returns:
            OperationResult with list of Persons
        """
        try:
            self._emit_started("load_persons")

            filter_ = filter_ or self._current_filter

            # Build query based on filter
            persons = self._query_persons(filter_)

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
        Get persons related to a unit.

        Args:
            unit_uuid: Unit UUID

        Returns:
            OperationResult with list of Persons
        """
        filter_ = PersonFilter(unit_uuid=unit_uuid)
        return self.load_persons(filter_)

    def get_persons_for_building(self, building_uuid: str) -> OperationResult[List[Person]]:
        """
        Get persons related to a building.

        Args:
            building_uuid: Building UUID

        Returns:
            OperationResult with list of Persons
        """
        filter_ = PersonFilter(building_uuid=building_uuid)
        return self.load_persons(filter_)

    def _query_persons(self, filter_: PersonFilter) -> List[Person]:
        """Execute person query with filter."""
        query = "SELECT * FROM persons WHERE 1=1"
        params = []

        if filter_.national_id:
            query += " AND national_id = ?"
            params.append(filter_.national_id)

        if filter_.phone_number:
            query += " AND (phone_number = ? OR phone_number_alt = ?)"
            params.extend([filter_.phone_number, filter_.phone_number])

        if filter_.full_name:
            query += " AND full_name LIKE ?"
            params.append(f"%{filter_.full_name}%")

        if filter_.gender:
            query += " AND gender = ?"
            params.append(filter_.gender)

        if filter_.nationality:
            query += " AND nationality = ?"
            params.append(filter_.nationality)

        if filter_.unit_uuid:
            query += """ AND person_uuid IN (
                SELECT person_uuid FROM relations WHERE unit_uuid = ?
            )"""
            params.append(filter_.unit_uuid)

        if filter_.building_uuid:
            query += """ AND person_uuid IN (
                SELECT r.person_uuid FROM relations r
                JOIN units u ON r.unit_uuid = u.unit_uuid
                WHERE u.building_uuid = ?
            )"""
            params.append(filter_.building_uuid)

        if filter_.search_text:
            query += " AND (full_name LIKE ? OR national_id LIKE ? OR phone_number LIKE ?)"
            search_param = f"%{filter_.search_text}%"
            params.extend([search_param, search_param, search_param])

        query += f" ORDER BY created_at DESC LIMIT {filter_.limit} OFFSET {filter_.offset}"

        cursor = self.db.cursor()
        cursor.execute(query, params)

        persons = []
        for row in cursor.fetchall():
            persons.append(Person.from_row(row))

        return persons

    # ==================== Validation ====================

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
        """Check for potential duplicate persons."""
        cursor = self.db.cursor()

        # Check by national ID
        if data.get("national_id"):
            cursor.execute(
                "SELECT person_uuid FROM persons WHERE national_id = ?",
                (data["national_id"],)
            )
            result = cursor.fetchone()
            if result:
                return {"person_uuid": result[0], "match_type": "national_id"}

        # Check by phone
        if data.get("phone_number"):
            cursor.execute(
                "SELECT person_uuid FROM persons WHERE phone_number = ? OR phone_number_alt = ?",
                (data["phone_number"], data["phone_number"])
            )
            result = cursor.fetchone()
            if result:
                return {"person_uuid": result[0], "match_type": "phone_number"}

        return None

    def _has_dependencies(self, person_uuid: str) -> bool:
        """Check if person has dependent records."""
        cursor = self.db.cursor()

        # Check for claims
        cursor.execute(
            "SELECT COUNT(*) FROM claims WHERE claimant_uuid = ?",
            (person_uuid,)
        )
        if cursor.fetchone()[0] > 0:
            return True

        # Check for active relations
        cursor.execute(
            "SELECT COUNT(*) FROM relations WHERE person_uuid = ?",
            (person_uuid,)
        )
        if cursor.fetchone()[0] > 0:
            return True

        return False

    # ==================== Statistics ====================

    def get_statistics(self) -> OperationResult[Dict[str, Any]]:
        """
        Get person statistics.

        Returns:
            OperationResult with statistics dictionary
        """
        try:
            count = self.repository.count()

            cursor = self.db.cursor()

            # By gender
            cursor.execute("""
                SELECT gender, COUNT(*) as count
                FROM persons
                WHERE gender IS NOT NULL
                GROUP BY gender
            """)
            by_gender = {row[0]: row[1] for row in cursor.fetchall()}

            # By nationality
            cursor.execute("""
                SELECT nationality, COUNT(*) as count
                FROM persons
                WHERE nationality IS NOT NULL
                GROUP BY nationality
                ORDER BY count DESC
                LIMIT 10
            """)
            by_nationality = {row[0]: row[1] for row in cursor.fetchall()}

            stats = {
                "total": count,
                "by_gender": by_gender,
                "by_nationality": by_nationality
            }

            return OperationResult.ok(data=stats)

        except Exception as e:
            return OperationResult.fail(message=str(e))
