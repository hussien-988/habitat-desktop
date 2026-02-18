# -*- coding: utf-8 -*-
"""
Data Provider Abstraction Layer.

This module provides an abstract interface for data access that allows
switching between different data sources:
- MockDataProvider: Uses local in-memory/file data for development
- HttpDataProvider: Connects to a real REST API backend
- LocalDbDataProvider: Uses local SQLite/PostgreSQL (current implementation)

This pattern enables:
1. Frontend development without backend dependency
2. Easy switching between mock and real data
3. Offline-first capability
4. Testing with controlled data
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

from utils.logger import get_logger

logger = get_logger(__name__)


class DataProviderType(Enum):
    """Supported data provider types."""
    LOCAL_DB = "local_db"      # Current SQLite/PostgreSQL
    MOCK = "mock"              # Mock data for development
    HTTP_API = "http_api"      # REST API backend


@dataclass
class ApiResponse(Generic[TypeVar('T')]):
    """Standardized API response wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    total_count: Optional[int] = None
    page: int = 1
    page_size: int = 50
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def ok(cls, data: Any, total_count: int = None, page: int = 1, page_size: int = 50) -> 'ApiResponse':
        """Create a successful response."""
        return cls(
            success=True,
            data=data,
            total_count=total_count,
            page=page,
            page_size=page_size
        )

    @classmethod
    def error(cls, message: str, code: str = None) -> 'ApiResponse':
        """Create an error response."""
        return cls(
            success=False,
            error=message,
            error_code=code
        )


@dataclass
class QueryParams:
    """Standardized query parameters for list operations."""
    page: int = 1
    page_size: int = 50
    sort_by: Optional[str] = None
    sort_order: str = "asc"
    filters: Dict[str, Any] = field(default_factory=dict)
    search: Optional[str] = None


class DataProvider(ABC):
    """
    Abstract base class for data providers.

    All data access in the application should go through implementations
    of this interface to allow easy switching between data sources.
    """

    @property
    @abstractmethod
    def provider_type(self) -> DataProviderType:
        """Return the type of this provider."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to data source."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to data source."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to data source."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check health status of data source."""
        pass

    # ==================== Buildings ====================

    @abstractmethod
    def get_buildings(self, params: QueryParams = None) -> ApiResponse:
        """Get list of buildings with pagination and filters."""
        pass

    @abstractmethod
    def get_building(self, building_id: str) -> ApiResponse:
        """Get single building by ID."""
        pass

    @abstractmethod
    def create_building(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new building."""
        pass

    @abstractmethod
    def update_building(self, building_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing building."""
        pass

    @abstractmethod
    def delete_building(self, building_id: str) -> ApiResponse:
        """Delete a building."""
        pass

    # ==================== Units ====================

    @abstractmethod
    def get_units(self, params: QueryParams = None) -> ApiResponse:
        """Get list of units with pagination and filters."""
        pass

    @abstractmethod
    def get_unit(self, unit_id: str) -> ApiResponse:
        """Get single unit by ID."""
        pass

    @abstractmethod
    def create_unit(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new unit."""
        pass

    @abstractmethod
    def update_unit(self, unit_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing unit."""
        pass

    @abstractmethod
    def delete_unit(self, unit_id: str) -> ApiResponse:
        """Delete a unit."""
        pass

    # ==================== Persons ====================

    @abstractmethod
    def get_persons(self, params: QueryParams = None) -> ApiResponse:
        """Get list of persons with pagination and filters."""
        pass

    @abstractmethod
    def get_person(self, person_id: str) -> ApiResponse:
        """Get single person by ID."""
        pass

    @abstractmethod
    def create_person(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new person."""
        pass

    @abstractmethod
    def update_person(self, person_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing person."""
        pass

    @abstractmethod
    def delete_person(self, person_id: str) -> ApiResponse:
        """Delete a person."""
        pass

    # ==================== Claims ====================

    @abstractmethod
    def get_claims(self, params: QueryParams = None) -> ApiResponse:
        """Get list of claims with pagination and filters."""
        pass

    @abstractmethod
    def get_claim(self, claim_id: str) -> ApiResponse:
        """Get single claim by ID."""
        pass

    @abstractmethod
    def create_claim(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new claim."""
        pass

    @abstractmethod
    def update_claim(self, claim_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing claim."""
        pass

    @abstractmethod
    def delete_claim(self, claim_id: str) -> ApiResponse:
        """Delete a claim."""
        pass

    # ==================== Relations ====================

    @abstractmethod
    def get_relations(self, params: QueryParams = None) -> ApiResponse:
        """Get list of person-unit relations."""
        pass

    @abstractmethod
    def get_relation(self, relation_id: str) -> ApiResponse:
        """Get single relation by ID."""
        pass

    @abstractmethod
    def create_relation(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new relation."""
        pass

    @abstractmethod
    def update_relation(self, relation_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing relation."""
        pass

    @abstractmethod
    def delete_relation(self, relation_id: str) -> ApiResponse:
        """Delete a relation."""
        pass

    # ==================== Documents ====================

    @abstractmethod
    def get_documents(self, params: QueryParams = None) -> ApiResponse:
        """Get list of documents."""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> ApiResponse:
        """Get single document by ID."""
        pass

    @abstractmethod
    def create_document(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new document."""
        pass

    @abstractmethod
    def update_document(self, document_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing document."""
        pass

    @abstractmethod
    def delete_document(self, document_id: str) -> ApiResponse:
        """Delete a document."""
        pass

    # ==================== Users & Auth ====================

    @abstractmethod
    def authenticate(self, username: str, password: str) -> ApiResponse:
        """Authenticate user and return token/session."""
        pass

    @abstractmethod
    def get_current_user(self) -> ApiResponse:
        """Get current authenticated user."""
        pass

    @abstractmethod
    def get_users(self, params: QueryParams = None) -> ApiResponse:
        """Get list of users (admin only)."""
        pass

    @abstractmethod
    def create_user(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new user."""
        pass

    @abstractmethod
    def update_user(self, user_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an existing user."""
        pass

    # ==================== Vocabularies ====================

    @abstractmethod
    def get_vocabularies(self) -> ApiResponse:
        """Get all controlled vocabularies."""
        pass

    @abstractmethod
    def get_vocabulary(self, vocab_name: str) -> ApiResponse:
        """Get specific vocabulary terms."""
        pass

    @abstractmethod
    def update_vocabulary_term(self, vocab_name: str, term_code: str, data: Dict[str, Any]) -> ApiResponse:
        """Update a vocabulary term."""
        pass

    # ==================== Dashboard & Statistics ====================

    @abstractmethod
    def get_dashboard_stats(self) -> ApiResponse:
        """Get dashboard statistics."""
        pass

    @abstractmethod
    def get_building_stats(self) -> ApiResponse:
        """Get building statistics."""
        pass

    @abstractmethod
    def get_claim_stats(self) -> ApiResponse:
        """Get claim statistics."""
        pass

    # ==================== Duplicates ====================

    @abstractmethod
    def get_duplicate_candidates(self, entity_type: str, params: QueryParams = None) -> ApiResponse:
        """Get duplicate candidates for review."""
        pass

    @abstractmethod
    def resolve_duplicate(self, resolution_data: Dict[str, Any]) -> ApiResponse:
        """Resolve a duplicate group."""
        pass

    # ==================== Import/Export ====================

    @abstractmethod
    def import_data(self, file_path: str, import_type: str) -> ApiResponse:
        """Import data from file."""
        pass

    @abstractmethod
    def export_data(self, export_type: str, filters: Dict[str, Any] = None) -> ApiResponse:
        """Export data to file."""
        pass

    # ==================== Assignments ====================

    @abstractmethod
    def get_building_assignments(self, params: QueryParams = None) -> ApiResponse:
        """Get building assignments."""
        pass

    @abstractmethod
    def create_assignment(self, data: Dict[str, Any]) -> ApiResponse:
        """Create a new building assignment."""
        pass

    @abstractmethod
    def update_assignment(self, assignment_id: str, data: Dict[str, Any]) -> ApiResponse:
        """Update an assignment."""
        pass

    # ==================== Audit ====================

    @abstractmethod
    def get_audit_log(self, params: QueryParams = None) -> ApiResponse:
        """Get audit log entries."""
        pass

    # ==================== Settings ====================

    @abstractmethod
    def get_security_settings(self) -> ApiResponse:
        """Get security settings."""
        pass

    @abstractmethod
    def update_security_settings(self, data: Dict[str, Any]) -> ApiResponse:
        """Update security settings."""
        pass


class DataProviderEvent:
    """Event types for data provider callbacks."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DATA_CHANGED = "data_changed"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"


class DataProviderEventEmitter:
    """Event emitter for data provider events."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, callback: Callable) -> None:
        """Register an event listener."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """Remove an event listener."""
        if event in self._listeners:
            self._listeners[event] = [cb for cb in self._listeners[event] if cb != callback]

    def emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all listeners."""
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event listener for {event}: {e}")
