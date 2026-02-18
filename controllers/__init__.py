# -*- coding: utf-8 -*-
"""
TRRCMS Controllers
==================
Controller layer for managing business logic and data operations.

This module provides controllers that act as intermediaries between
the UI (pages) and the data layer (repositories/services).

Controllers provide:
- Clean separation of concerns
- Standardized error handling via OperationResult
- Qt signals for UI updates
- Validation and business rules
- Caching and state management

Usage:
    from controllers import BuildingController, OperationResult

    controller = BuildingController(db)
    result = controller.create_building(data)
    if result.success:
        print(f"Created: {result.data.building_uuid}")
    else:
        print(f"Error: {result.message}")
"""

# Base controller and result types
from controllers.base_controller import (
    BaseController,
    OperationResult,
)

# Domain controllers
from controllers.building_controller import (
    BuildingController,
    BuildingFilter,
)

from controllers.claim_controller import (
    ClaimController,
    ClaimFilter,
)

from controllers.map_controller import (
    MapController,
    MapFilter,
    MapState,
)

from controllers.person_controller import (
    PersonController,
    PersonFilter,
)

from controllers.unit_controller import (
    UnitController,
    UnitFilter,
)

# All public exports
__all__ = [
    # Base
    "BaseController",
    "OperationResult",

    # Building
    "BuildingController",
    "BuildingFilter",

    # Claim
    "ClaimController",
    "ClaimFilter",

    # Map
    "MapController",
    "MapFilter",
    "MapState",

    # Person
    "PersonController",
    "PersonFilter",

    # Unit
    "UnitController",
    "UnitFilter",
]
