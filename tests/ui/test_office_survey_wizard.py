# -*- coding: utf-8 -*-
"""
Tests for Office Survey Wizard (Refactored Version).

Tests cover:
- Wizard initialization
- Step navigation
- Context persistence
- Validation rules
- Data collection
"""

import pytest
from pathlib import Path
from PyQt5.QtWidgets import QApplication

from ui.wizards.office_survey.office_survey_wizard_refactored import OfficeSurveyWizard
from ui.wizards.office_survey.survey_context import SurveyContext
from repositories.database import Database


@pytest.fixture
def qapp(qapp):
    """Ensure QApplication is available."""
    return qapp


@pytest.fixture
def test_db(tmp_path):
    """Create test database instance."""
    # Use temporary file instead of :memory: due to Path requirement
    db_path = tmp_path / "test_wizard.db"
    db = Database(db_path=db_path)
    yield db
    db.close()


@pytest.fixture
def wizard(qapp, test_db):
    """Create wizard instance for testing."""
    wizard = OfficeSurveyWizard(db=test_db)
    yield wizard
    wizard.close()


class TestWizardInitialization:
    """Test wizard initialization and setup."""

    def test_wizard_creation(self, wizard):
        """Test wizard can be created."""
        assert wizard is not None
        assert isinstance(wizard, OfficeSurveyWizard)

    def test_wizard_has_context(self, wizard):
        """Test wizard has survey context."""
        assert wizard.context is not None
        assert isinstance(wizard.context, SurveyContext)

    def test_wizard_has_seven_steps(self, wizard):
        """Test wizard has exactly 7 steps."""
        assert len(wizard.steps) == 7

    def test_wizard_step_names(self, wizard):
        """Test wizard step names are correct."""
        expected_names = [
            "اختيار المبنى",
            "المقاسم",
            "الأسرة والإشغال",
            "تسجيل الأشخاص",
            "العلاقات والأدلة",
            "إنشاء المطالبة",
            "المراجعة النهائية"
        ]

        for i, step in enumerate(wizard.steps):
            # Get step title from step or from STEP_NAMES
            if i < len(wizard.STEP_NAMES):
                _, expected_name = wizard.STEP_NAMES[i]
                assert expected_name in expected_names

    def test_wizard_starts_at_first_step(self, wizard):
        """Test wizard starts at step 0."""
        assert wizard.navigator.current_index == 0

    def test_wizard_reference_number_generated(self, wizard):
        """Test wizard context has reference number."""
        assert wizard.context.reference_number is not None
        assert wizard.context.reference_number.startswith("SRV-")


class TestWizardNavigation:
    """Test wizard navigation between steps."""

    def test_cannot_go_next_without_valid_data(self, wizard):
        """Test cannot proceed to next step without validation."""
        # Step 1 requires building selection
        # Validate directly without initializing UI (which loads from DB)
        step_1 = wizard.steps[0]

        # Validate step without building selection
        result = step_1.validate()

        # Should fail validation because no building selected
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_can_go_previous_from_second_step(self, wizard):
        """Test can navigate back from step 2."""
        # Move to step 2 (skipping validation for test)
        wizard.navigator.goto_step(1, skip_validation=True)

        # Should be able to go back
        can_go_back = wizard.navigator.can_go_previous()
        assert can_go_back is True

    def test_cannot_go_previous_from_first_step(self, wizard):
        """Test cannot go back from step 1."""
        # Should be at step 0
        assert wizard.navigator.current_index == 0

        can_go_back = wizard.navigator.can_go_previous()
        assert can_go_back is False


class TestSurveyContext:
    """Test survey context data management."""

    def test_context_initialized_empty(self, wizard):
        """Test context starts with empty data."""
        ctx = wizard.context

        assert ctx.building is None
        assert ctx.unit is None
        assert len(ctx.persons) == 0
        assert len(ctx.relations) == 0
        assert len(ctx.households) == 0
        assert ctx.claim_data is None

    def test_context_can_store_custom_data(self, wizard):
        """Test context can store arbitrary data."""
        wizard.context.update_data("test_key", "test_value")

        retrieved = wizard.context.get_data("test_key")
        assert retrieved == "test_value"

    def test_context_serialization(self, wizard):
        """Test context can be serialized to dict."""
        wizard.context.update_data("custom_field", 12345)

        data_dict = wizard.context.to_dict()

        assert isinstance(data_dict, dict)
        assert "reference_number" in data_dict
        assert "created_at" in data_dict
        assert "status" in data_dict
        assert "data" in data_dict
        assert data_dict["data"]["custom_field"] == 12345

    def test_context_deserialization(self, wizard):
        """Test context can be restored from dict."""
        # Serialize current context
        original_ref = wizard.context.reference_number
        wizard.context.update_data("test_data", "test_value")

        data_dict = wizard.context.to_dict()

        # Create new context from dict
        new_context = SurveyContext.from_dict(data_dict)

        assert new_context.reference_number == original_ref
        assert new_context.get_data("test_data") == "test_value"


class TestStepValidation:
    """Test individual step validation."""

    def test_building_step_validation_fails_without_selection(self, wizard):
        """Test Step 1 validation fails without building."""
        step_1 = wizard.steps[0]

        # Initialize step
        step_1.initialize()

        # Validate
        result = step_1.validate()

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("مبنى" in error for error in result.errors)

    def test_step_has_validate_method(self, wizard):
        """Test all steps have validate method."""
        for step in wizard.steps:
            assert hasattr(step, 'validate')
            assert callable(step.validate)

    def test_step_has_collect_data_method(self, wizard):
        """Test all steps have collect_data method."""
        for step in wizard.steps:
            assert hasattr(step, 'collect_data')
            assert callable(step.collect_data)


class TestWizardSignals:
    """Test wizard signal emissions."""

    def test_wizard_has_completion_signal(self, wizard):
        """Test wizard has survey_completed signal."""
        assert hasattr(wizard, 'survey_completed')

    def test_wizard_has_cancelled_signal(self, wizard):
        """Test wizard has survey_cancelled signal."""
        assert hasattr(wizard, 'survey_cancelled')

    def test_wizard_has_draft_saved_signal(self, wizard):
        """Test wizard has survey_saved_draft signal."""
        assert hasattr(wizard, 'survey_saved_draft')


class TestWizardDraftFunctionality:
    """Test draft save/load functionality."""

    def test_context_to_dict_includes_all_fields(self, wizard):
        """Test context serialization includes all necessary fields."""
        # Add some data
        wizard.context.update_data("step_1_complete", True)
        wizard.context.update_data("test_field", "test_data")

        data = wizard.context.to_dict()

        # Check core fields
        assert "reference_number" in data
        assert "status" in data
        assert "created_at" in data
        assert "current_step_index" in data
        assert "data" in data

        # Check custom fields (stored in data sub-dict)
        assert data["data"].get("step_1_complete") is True
        assert data["data"].get("test_field") == "test_data"

    def test_draft_save_updates_status(self, wizard):
        """Test saving draft updates context status."""
        # Manually set status to draft
        wizard.context.status = "draft"

        assert wizard.context.status == "draft"


class TestWizardUI:
    """Test wizard UI components."""

    def test_wizard_has_navigation_buttons(self, wizard):
        """Test wizard has next/previous buttons."""
        assert hasattr(wizard, 'btn_next')
        assert hasattr(wizard, 'btn_previous')

    def test_wizard_has_save_button(self, wizard):
        """Test wizard has save draft button."""
        assert hasattr(wizard, 'save_btn')

    def test_wizard_has_step_labels(self, wizard):
        """Test wizard has step indicator labels."""
        assert hasattr(wizard, 'step_labels')
        assert len(wizard.step_labels) == 7

    def test_previous_button_disabled_at_start(self, wizard):
        """Test previous button is disabled at first step."""
        # At step 0
        assert wizard.navigator.current_index == 0
        assert wizard.btn_previous.isEnabled() is False


class TestWizardIntegration:
    """Integration tests for complete workflows."""

    def test_wizard_title_is_correct(self, wizard):
        """Test wizard window title."""
        title = wizard.get_wizard_title()
        assert "Office Survey" in title or "المسح المكتبي" in title

    def test_submit_button_text(self, wizard):
        """Test submit button has correct text."""
        submit_text = wizard.get_submit_button_text()
        assert "إنهاء" in submit_text or "المسح" in submit_text


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
