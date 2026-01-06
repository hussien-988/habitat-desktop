# -*- coding: utf-8 -*-
"""
Smoke tests for TRRCMS Desktop Application.
These tests verify basic functionality without requiring a GUI.
"""

import sys
import os
import unittest
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestModels(unittest.TestCase):
    """Test model classes."""

    def test_building_creation(self):
        """Test Building model creation and ID generation."""
        from models.building import Building

        building = Building(
            governorate_code="01",
            district_code="01",
            subdistrict_code="01",
            community_code="001",
            neighborhood_code="001",
            building_number="00001",
            building_type="residential",
            building_status="intact"
        )

        self.assertEqual(building.building_id, "01-01-01-001-001-00001")
        self.assertEqual(building.building_type, "residential")
        self.assertIsNotNone(building.building_uuid)

    def test_building_to_dict(self):
        """Test Building serialization."""
        from models.building import Building

        building = Building(building_number="00002")
        data = building.to_dict()

        self.assertIn("building_uuid", data)
        self.assertIn("building_id", data)
        self.assertIn("governorate_code", data)

    def test_person_creation(self):
        """Test Person model creation."""
        from models.person import Person

        person = Person(
            first_name_ar="محمد",
            father_name_ar="أحمد",
            last_name_ar="الحلبي",
            gender="male",
            national_id="12345678901"
        )

        self.assertEqual(person.full_name_ar, "محمد أحمد الحلبي")
        self.assertTrue(person.validate_national_id())
        self.assertIsNotNone(person.person_id)

    def test_person_invalid_national_id(self):
        """Test Person validation with invalid national ID."""
        from models.person import Person

        person = Person(national_id="12345")  # Only 5 digits
        self.assertFalse(person.validate_national_id())

    def test_claim_creation(self):
        """Test Claim model creation."""
        from models.claim import Claim

        claim = Claim(
            claim_type="ownership",
            priority="normal",
            source="OFFICE_SUBMISSION"
        )

        self.assertTrue(claim.claim_id.startswith("CL-"))
        self.assertEqual(claim.case_status, "draft")

    def test_property_unit_creation(self):
        """Test PropertyUnit model creation."""
        from models.unit import PropertyUnit

        unit = PropertyUnit(
            building_id="01-01-01-001-001-00001",
            unit_type="apartment",
            unit_number="001",
            floor_number=2
        )

        self.assertEqual(unit.unit_id, "01-01-01-001-001-00001-001")
        self.assertEqual(unit.unit_type_display, "Apartment")


class TestDatabase(unittest.TestCase):
    """Test database operations."""

    @classmethod
    def setUpClass(cls):
        """Set up test database."""
        from repositories.database import Database

        # Use a test database
        cls.test_db_path = PROJECT_ROOT / "data" / "test_trrcms.db"
        cls.db = Database(cls.test_db_path)
        cls.db.initialize()

    @classmethod
    def tearDownClass(cls):
        """Clean up test database."""
        cls.db.close()
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()

    def test_database_connection(self):
        """Test database connection."""
        conn = self.db.get_connection()
        self.assertIsNotNone(conn)

    def test_database_tables_exist(self):
        """Test that all required tables are created."""
        tables = ["users", "buildings", "property_units", "persons",
                  "person_unit_relations", "documents", "evidence", "claims"]

        for table in tables:
            result = self.db.fetch_one(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            self.assertIsNotNone(result, f"Table {table} should exist")


class TestRepositories(unittest.TestCase):
    """Test repository classes."""

    @classmethod
    def setUpClass(cls):
        """Set up test database and repositories."""
        from repositories.database import Database
        from repositories.building_repository import BuildingRepository
        from repositories.person_repository import PersonRepository

        cls.test_db_path = PROJECT_ROOT / "data" / "test_repos.db"
        cls.db = Database(cls.test_db_path)
        cls.db.initialize()

        cls.building_repo = BuildingRepository(cls.db)
        cls.person_repo = PersonRepository(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()

    def test_building_crud(self):
        """Test Building CRUD operations."""
        from models.building import Building

        # Create
        building = Building(
            building_number="99999",
            building_type="commercial",
            building_status="intact"
        )
        self.building_repo.create(building)

        # Read
        retrieved = self.building_repo.get_by_id(building.building_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.building_type, "commercial")

        # Update
        building.building_type = "residential"
        self.building_repo.update(building)

        retrieved = self.building_repo.get_by_id(building.building_id)
        self.assertEqual(retrieved.building_type, "residential")

        # Delete
        self.building_repo.delete(building.building_id)
        retrieved = self.building_repo.get_by_id(building.building_id)
        self.assertIsNone(retrieved)

    def test_person_crud(self):
        """Test Person CRUD operations."""
        from models.person import Person

        # Create
        person = Person(
            first_name_ar="اختبار",
            last_name_ar="تجريبي",
            national_id="99999999999"
        )
        self.person_repo.create(person)

        # Read
        retrieved = self.person_repo.get_by_id(person.person_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.first_name_ar, "اختبار")

        # Search
        results = self.person_repo.search(name="اختبار")
        self.assertGreater(len(results), 0)


class TestServices(unittest.TestCase):
    """Test service classes."""

    def test_validation_service(self):
        """Test ValidationService."""
        from services.validation_service import ValidationService

        validator = ValidationService()

        # Test national ID validation
        self.assertTrue(validator.validate_national_id("12345678901"))
        self.assertFalse(validator.validate_national_id("12345"))
        self.assertFalse(validator.validate_national_id("abcdefghijk"))

        # Test building ID validation
        self.assertTrue(validator.validate_building_id("01-01-01-001-001-00001"))
        self.assertFalse(validator.validate_building_id("invalid"))

    def test_workflow_service(self):
        """Test WorkflowService transitions."""
        from services.workflow_service import WorkflowService

        # Test valid transitions
        transitions = WorkflowService.TRANSITIONS

        # draft -> submitted is valid
        self.assertIn(
            ("submitted", "تقديم المطالبة"),
            transitions["draft"]
        )

        # approved is a terminal state
        self.assertEqual(len(transitions["approved"]), 0)


class TestI18n(unittest.TestCase):
    """Test internationalization."""

    def test_i18n_loading(self):
        """Test I18n translation loading."""
        from utils.i18n import I18n

        i18n = I18n()

        # Test Arabic
        i18n.set_language("ar")
        self.assertTrue(i18n.is_arabic())

        # Test key translation
        building_label = i18n.t("buildings")
        self.assertIsNotNone(building_label)

        # Test English
        i18n.set_language("en")
        self.assertFalse(i18n.is_arabic())


class TestConfig(unittest.TestCase):
    """Test configuration."""

    def test_config_values(self):
        """Test Config values are set."""
        from app.config import Config

        self.assertEqual(Config.APP_NAME, "UN-Habitat Syria")
        self.assertIsNotNone(Config.DB_PATH)
        self.assertIsNotNone(Config.PRIMARY_COLOR)

    def test_paths_exist(self):
        """Test that configured paths can be created."""
        from app.config import Config

        # These directories should be creatable
        Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

        self.assertTrue(Config.DATA_DIR.exists())
        self.assertTrue(Config.LOGS_DIR.exists())


def run_tests():
    """Run all smoke tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestModels))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestRepositories))
    suite.addTests(loader.loadTestsFromTestCase(TestServices))
    suite.addTests(loader.loadTestsFromTestCase(TestI18n))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
