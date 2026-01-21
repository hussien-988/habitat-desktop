# -*- coding: utf-8 -*-
"""
Tests for PrimaryButton UI component.
"""
import sys
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ui.components.primary_button import PrimaryButton


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def primary_button(qapp):
    """Create a PrimaryButton instance."""
    button = PrimaryButton("Test Button")
    return button


def test_button_creation(primary_button):
    """Test button can be created."""
    assert primary_button is not None
    assert primary_button.text() == "Test Button"


def test_button_click(primary_button, qtbot):
    """Test button click signal."""
    clicked = False

    def on_click():
        nonlocal clicked
        clicked = True

    primary_button.clicked.connect(on_click)
    qtbot.addWidget(primary_button)

    # Simulate click
    qtbot.mouseClick(primary_button, Qt.LeftButton)

    assert clicked is True


def test_button_enabled_disabled(primary_button):
    """Test button can be enabled/disabled."""
    assert primary_button.isEnabled()

    primary_button.setEnabled(False)
    assert not primary_button.isEnabled()

    primary_button.setEnabled(True)
    assert primary_button.isEnabled()


def test_button_text_change(primary_button):
    """Test button text can be changed."""
    primary_button.setText("New Text")
    assert primary_button.text() == "New Text"


def test_button_visibility(primary_button):
    """Test button visibility."""
    assert not primary_button.isVisible()  # Not shown yet

    primary_button.show()
    assert primary_button.isVisible()

    primary_button.hide()
    assert not primary_button.isVisible()
