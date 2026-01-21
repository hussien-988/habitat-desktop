# -*- coding: utf-8 -*-
"""
Smoke tests to ensure application doesn't break after changes.
These tests verify basic functionality works.
"""
import sys
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all main modules can be imported."""
    try:
        from models.building import Building
        from models.person import Person
        from models.claim import Claim
        from models.unit import PropertyUnit
        from repositories.database import Database
        from services.auth_service import AuthService
        assert True
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")


def test_models_instantiation():
    """Test that models can be instantiated."""
    from models.building import Building
    from models.person import Person

    building = Building()
    assert building.building_id is not None

    person = Person()
    assert person.person_id is not None


def test_database_connection():
    """Test database connection."""
    from repositories.database import Database

    db = Database()
    assert db is not None


def test_ui_components_import():
    """Test that UI components can be imported."""
    try:
        from ui.components.primary_button import PrimaryButton
        from ui.components.input_field import InputField
        from ui.components.page_header import PageHeader
        assert True
    except ImportError as e:
        pytest.fail(f"UI component import failed: {e}")


def test_services_import():
    """Test that services can be imported."""
    try:
        from services.auth_service import AuthService
        from services.workflow_service import WorkflowService
        from services.validation.validation_factory import ValidationFactory
        assert True
    except ImportError as e:
        pytest.fail(f"Service import failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
