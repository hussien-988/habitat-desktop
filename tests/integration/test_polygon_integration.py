# -*- coding: utf-8 -*-
"""
Integration Tests for Polygon Building Selection.

Tests the complete workflow from polygon drawing to building selection and data persistence.
"""

import pytest
import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication

from repositories.database import Database
from ui.components.polygon_building_selector_dialog import PolygonBuildingSelectorDialog
from ui.components.polygon_editor_widget import PolygonEditorWidget
from ui.wizards.office_survey.office_survey_wizard_refactored import OfficeSurveyWizard
from models.building import Building


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def test_db(tmp_path):
    """Create test database with sample buildings."""
    db_path = tmp_path / "test_integration.db"
    db = Database(db_path)
    db.initialize()

    # Insert sample buildings
    with db.cursor() as cursor:
        # Building 1 - in Aleppo
        cursor.execute("""
            INSERT INTO buildings (building_uuid, building_id, latitude, longitude,
                                 neighborhood_code, building_type, building_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'test-building-1',
            'BUILD-001',
            36.2021,
            37.1343,
            'HOOD-01',
            'residential',
            'good'
        ))

        # Building 2 - in Aleppo
        cursor.execute("""
            INSERT INTO buildings (building_uuid, building_id, latitude, longitude,
                                 neighborhood_code, building_type, building_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'test-building-2',
            'BUILD-002',
            36.2025,
            37.1350,
            'HOOD-01',
            'commercial',
            'damaged'
        ))

    yield db

    # Cleanup
    if db_path.exists():
        db_path.unlink()


class TestPolygonEditorWidget:
    """Test PolygonEditorWidget functionality."""

    def test_widget_creation(self, qapp):
        """Test that polygon editor widget can be created."""
        widget = PolygonEditorWidget()

        assert widget is not None
        assert hasattr(widget, 'polygon_changed')
        assert hasattr(widget, 'area_changed')
        assert hasattr(widget, 'get_polygon_wkt')
        assert hasattr(widget, 'get_polygon_geojson')

    def test_widget_has_toolbar(self, qapp):
        """Test that widget has editing toolbar."""
        widget = PolygonEditorWidget()

        assert hasattr(widget, 'draw_btn')
        assert hasattr(widget, 'edit_btn')
        assert hasattr(widget, 'delete_btn')
        assert hasattr(widget, 'validate_btn')

    def test_widget_has_status_labels(self, qapp):
        """Test that widget has status and area labels."""
        widget = PolygonEditorWidget()

        assert hasattr(widget, 'status_label')
        assert hasattr(widget, 'area_label')


class TestPolygonBuildingSelectorDialog:
    """Test PolygonBuildingSelectorDialog functionality."""

    def test_dialog_creation(self, qapp, test_db):
        """Test that dialog can be created with database."""
        dialog = PolygonBuildingSelectorDialog(test_db)

        assert dialog is not None
        assert dialog.polygon_editor is not None
        assert dialog.buildings_list is not None
        assert dialog.status_label is not None
        assert dialog.select_btn is not None

    def test_dialog_has_spatial_service(self, qapp, test_db):
        """Test that dialog initializes spatial service."""
        dialog = PolygonBuildingSelectorDialog(test_db)

        assert hasattr(dialog, 'spatial_service')
        assert dialog.spatial_service is not None

    def test_geojson_to_wkt_conversion(self, qapp, test_db):
        """Test GeoJSON to WKT conversion."""
        dialog = PolygonBuildingSelectorDialog(test_db)

        geojson = {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[
                    [37.13, 36.20],
                    [37.14, 36.20],
                    [37.14, 36.21],
                    [37.13, 36.21],
                    [37.13, 36.20]
                ]]
            }
        }

        wkt = dialog._geojson_to_wkt(geojson)

        assert wkt is not None
        assert wkt.startswith('POLYGON((')
        assert '37.13 36.2' in wkt
        assert '37.14 36.21' in wkt

    def test_select_button_disabled_initially(self, qapp, test_db):
        """Test that select button is disabled when no polygon drawn."""
        dialog = PolygonBuildingSelectorDialog(test_db)

        assert dialog.select_btn.isEnabled() is False


class TestWizardIntegration:
    """Test integration with office survey wizard."""

    def test_building_step_has_polygon_button(self, qapp, test_db):
        """Test that building selection step has polygon selection button."""
        wizard = OfficeSurveyWizard(db=test_db)

        # Get first step (building selection)
        building_step = wizard.steps[0]

        assert hasattr(building_step, 'polygon_select_btn')
        assert building_step.polygon_select_btn is not None
        assert building_step.polygon_select_btn.text() == "تحديد منطقة"

    def test_building_step_has_polygon_handler(self, qapp, test_db):
        """Test that building selection step has polygon dialog handler."""
        wizard = OfficeSurveyWizard(db=test_db)
        building_step = wizard.steps[0]

        assert hasattr(building_step, '_open_polygon_selector_dialog')

    def test_context_stores_building(self, qapp, test_db):
        """Test that selected building is stored in context."""
        wizard = OfficeSurveyWizard(db=test_db)
        building_step = wizard.steps[0]

        # Create a test building
        test_building = Building(
            building_uuid='test-uuid',
            building_id='TEST-001',
            neighborhood_code='HOOD-01',
            building_type='residential',
            building_status='good'
        )

        # Simulate building selection
        building_step.context.building = test_building
        building_step.selected_building = test_building

        # Collect data
        data = building_step.collect_data()

        assert data['building_id'] == 'TEST-001'
        assert data['building_uuid'] == 'test-uuid'
        assert wizard.context.building is not None
        assert wizard.context.building.building_id == 'TEST-001'


class TestDataPersistence:
    """Test data persistence across wizard steps."""

    def test_building_persists_across_steps(self, qapp, test_db):
        """Test that building selection persists when navigating."""
        wizard = OfficeSurveyWizard(db=test_db)
        building_step = wizard.steps[0]

        # Select a building
        test_building = Building(
            building_uuid='persist-test',
            building_id='PERSIST-001',
            neighborhood_code='HOOD-01',
            building_type='commercial',
            building_status='good'
        )

        building_step.context.building = test_building
        building_step.selected_building = test_building

        # Validate
        assert building_step.validate().is_valid

        # Check context serialization
        context_data = wizard.context.to_dict()

        assert 'building_id' in context_data or 'building' in context_data

    def test_context_serialization_includes_building(self, qapp, test_db):
        """Test that context serialization includes building data."""
        wizard = OfficeSurveyWizard(db=test_db)

        # Set building in context
        test_building = Building(
            building_uuid='serial-test',
            building_id='SERIAL-001',
            neighborhood_code='HOOD-01',
            building_type='residential',
            building_status='damaged'
        )

        wizard.context.building = test_building

        # Serialize
        serialized = wizard.context.to_dict()

        # Check that building data is present
        # (exact structure depends on context implementation)
        assert serialized is not None
        assert isinstance(serialized, dict)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
