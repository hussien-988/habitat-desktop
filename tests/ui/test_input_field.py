# -*- coding: utf-8 -*-
"""
Tests for InputField UI component.
"""
import sys
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ui.components.input_field import InputField


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def input_field(qapp):
    """Create an InputField instance."""
    field = InputField(placeholder="Enter text")
    return field


def test_input_field_creation(input_field):
    """Test input field can be created."""
    assert input_field is not None


def test_input_field_value(input_field):
    """Test getting and setting value."""
    input_field.setText("test value")
    assert input_field.text() == "test value"


def test_input_field_clear(input_field):
    """Test clearing input field."""
    input_field.setText("some text")
    input_field.clear()
    assert input_field.text() == ""


def test_input_field_enabled(input_field):
    """Test enabling/disabling input field."""
    assert input_field.isEnabled()

    input_field.setEnabled(False)
    assert not input_field.isEnabled()

    input_field.setEnabled(True)
    assert input_field.isEnabled()


def test_input_field_readonly(input_field):
    """Test readonly mode."""
    input_field.setReadOnly(True)
    assert input_field.isReadOnly()

    input_field.setReadOnly(False)
    assert not input_field.isReadOnly()
