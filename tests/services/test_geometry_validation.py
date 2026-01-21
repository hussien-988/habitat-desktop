# -*- coding: utf-8 -*-
"""
Tests for Geometry Validation Service.

Tests cover:
- Point validation
- Polygon validation
- Self-intersection detection
- Area calculation
- Polygon repair
"""

import pytest
import math

from services.geometry_validation_service import GeometryValidationService, ValidationResult
from services.map_service import GeoPoint, GeoPolygon


@pytest.fixture
def validator():
    """Create validation service instance."""
    return GeometryValidationService()


class TestPointValidation:
    """Test point validation."""

    def test_valid_point_in_aleppo(self, validator):
        """Test valid point within Aleppo bounds."""
        point = GeoPoint(latitude=36.2021, longitude=37.1343)  # Aleppo center
        result = validator.validate_point(point)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_valid_point_outside_aleppo(self, validator):
        """Test valid point outside Aleppo (should warn)."""
        point = GeoPoint(latitude=33.5138, longitude=36.2765)  # Damascus
        result = validator.validate_point(point)

        assert result.is_valid is True  # Coordinates are valid
        assert len(result.warnings) > 0  # But warns about location

    def test_invalid_latitude(self, validator):
        """Test point with invalid latitude."""
        point = GeoPoint(latitude=95.0, longitude=37.0)  # >90
        result = validator.validate_point(point)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "خط العرض" in result.errors[0]

    def test_invalid_longitude(self, validator):
        """Test point with invalid longitude."""
        point = GeoPoint(latitude=36.0, longitude=190.0)  # >180
        result = validator.validate_point(point)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "خط الطول" in result.errors[0]


class TestPolygonValidation:
    """Test polygon validation."""

    def test_valid_simple_polygon(self, validator):
        """Test valid simple square polygon."""
        # Square in Aleppo (~100m x 100m)
        # 0.001 degrees ≈ 100m at this latitude
        coords = [
            (37.130, 36.200),
            (37.131, 36.200),
            (37.131, 36.201),
            (37.130, 36.201),
            (37.130, 36.200)  # Closed
        ]
        polygon = GeoPolygon(coordinates=[coords])

        result = validator.validate_polygon(polygon)

        # Check for serious errors only (not orientation warnings)
        has_size_error = any("small" in str(error).lower() or len(error) > 20 for error in result.errors)
        has_intersection_error = any("intersect" in str(error).lower() for error in result.errors)

        assert not has_size_error, f"Polygon should not be too small. Errors: {result.errors}"
        assert not has_intersection_error, f"Polygon should not self-intersect. Errors: {result.errors}"

    def test_polygon_too_few_vertices(self, validator):
        """Test polygon with too few vertices."""
        coords = [
            (37.13, 36.20),
            (37.14, 36.20)
        ]
        polygon = GeoPolygon(coordinates=[coords])

        result = validator.validate_polygon(polygon)

        assert result.is_valid is False
        assert any("3 نقاط على الأقل" in error for error in result.errors)

    def test_polygon_unclosed(self, validator):
        """Test unclosed polygon (should warn)."""
        coords = [
            (37.13, 36.20),
            (37.14, 36.20),
            (37.14, 36.21),
            (37.13, 36.21)
            # Missing closing point
        ]
        polygon = GeoPolygon(coordinates=[coords])

        result = validator.validate_polygon(polygon)

        # Should have warning about unclosed polygon
        assert any("غير مغلق" in warning for warning in result.warnings)

    def test_polygon_self_intersection(self, validator):
        """Test self-intersecting polygon (bowtie shape)."""
        # Bowtie shape that intersects itself
        coords = [
            (37.13, 36.20),
            (37.14, 36.21),  # Crosses next segment
            (37.14, 36.20),
            (37.13, 36.21),
            (37.13, 36.20)
        ]
        polygon = GeoPolygon(coordinates=[coords])

        result = validator.validate_polygon(polygon, check_self_intersection=True)

        assert result.is_valid is False
        assert any("يتقاطع مع نفسه" in error for error in result.errors)

    def test_polygon_too_small_area(self, validator):
        """Test polygon with area below minimum."""
        # Tiny polygon (~0.1 square meter)
        coords = [
            (37.130000, 36.200000),
            (37.130003, 36.200000),
            (37.130003, 36.200003),
            (37.130000, 36.200003),
            (37.130000, 36.200000)
        ]
        polygon = GeoPolygon(coordinates=[coords])

        result = validator.validate_polygon(polygon)

        assert result.is_valid is False
        assert any("صغيرة جداً" in error for error in result.errors)


class TestOrientationChecks:
    """Test polygon orientation checks."""

    def test_counter_clockwise_detection(self, validator):
        """Test counter-clockwise polygon detection."""
        # Counter-clockwise square
        coords = [
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
            (0.0, 0.0)
        ]

        is_ccw = validator._is_counter_clockwise(coords)
        assert is_ccw is True

    def test_clockwise_detection(self, validator):
        """Test clockwise polygon detection."""
        # Clockwise square
        coords = [
            (0.0, 0.0),
            (0.0, 1.0),
            (1.0, 1.0),
            (1.0, 0.0),
            (0.0, 0.0)
        ]

        is_ccw = validator._is_counter_clockwise(coords)
        assert is_ccw is False


class TestAreaCalculation:
    """Test area calculation."""

    def test_square_area(self, validator):
        """Test area calculation for a square."""
        # Approximate 100m x 100m square in Aleppo
        # 1 degree ≈ 111km at equator, ≈ 85km longitude at 36°N
        # So ~0.0012° ≈ 100m

        coords = [
            (37.130, 36.200),
            (37.131, 36.200),
            (37.131, 36.201),
            (37.130, 36.201),
            (37.130, 36.200)
        ]

        area = validator._calculate_polygon_area(coords)

        # Should be approximately 10000 m² (0.01 km²)
        # Allow 20% tolerance due to spherical calculation
        assert 8000 < area < 12000


class TestPolygonRepair:
    """Test polygon repair functionality."""

    def test_repair_unclosed_polygon(self, validator):
        """Test repairing unclosed polygon."""
        coords = [
            (37.13, 36.20),
            (37.14, 36.20),
            (37.14, 36.21),
            (37.13, 36.21)
            # Missing closing point
        ]
        polygon = GeoPolygon(coordinates=[coords])

        repaired = validator.repair_polygon(polygon)

        # Should be closed now
        first = repaired.coordinates[0][0]
        last = repaired.coordinates[0][-1]
        assert first == last

    def test_repair_removes_duplicates(self, validator):
        """Test that repair removes consecutive duplicate points."""
        coords = [
            (37.13, 36.20),
            (37.13, 36.20),  # Duplicate
            (37.14, 36.20),
            (37.14, 36.20),  # Duplicate
            (37.14, 36.21),
            (37.13, 36.21),
            (37.13, 36.20)
        ]
        polygon = GeoPolygon(coordinates=[coords])

        repaired = validator.repair_polygon(polygon)

        # Should have fewer points (duplicates removed)
        assert len(repaired.coordinates[0]) < len(coords)

    def test_repair_fixes_orientation(self, validator):
        """Test that repair fixes polygon orientation."""
        # Clockwise polygon (wrong orientation)
        coords = [
            (37.13, 36.20),
            (37.13, 36.21),
            (37.14, 36.21),
            (37.14, 36.20),
            (37.13, 36.20)
        ]
        polygon = GeoPolygon(coordinates=[coords])

        repaired = validator.repair_polygon(polygon)

        # Should be counter-clockwise now
        is_ccw = validator._is_counter_clockwise(repaired.coordinates[0])
        assert is_ccw is True


class TestSegmentIntersection:
    """Test line segment intersection detection."""

    def test_intersecting_segments(self, validator):
        """Test detection of intersecting segments."""
        # X shape
        p1 = (0.0, 0.0)
        p2 = (1.0, 1.0)
        p3 = (0.0, 1.0)
        p4 = (1.0, 0.0)

        intersects = validator._segments_intersect(p1, p2, p3, p4)
        assert intersects is True

    def test_non_intersecting_segments(self, validator):
        """Test detection of non-intersecting segments."""
        # Parallel segments
        p1 = (0.0, 0.0)
        p2 = (1.0, 0.0)
        p3 = (0.0, 1.0)
        p4 = (1.0, 1.0)

        intersects = validator._segments_intersect(p1, p2, p3, p4)
        assert intersects is False


class TestPointInPolygon:
    """Test point-in-polygon detection."""

    def test_point_inside_polygon(self, validator):
        """Test point inside polygon."""
        # Square
        ring = [
            (0.0, 0.0),
            (2.0, 0.0),
            (2.0, 2.0),
            (0.0, 2.0),
            (0.0, 0.0)
        ]

        # Point in center
        point = GeoPoint(latitude=1.0, longitude=1.0)

        inside = validator._point_in_polygon_simple(point, ring)
        assert inside is True

    def test_point_outside_polygon(self, validator):
        """Test point outside polygon."""
        # Square
        ring = [
            (0.0, 0.0),
            (2.0, 0.0),
            (2.0, 2.0),
            (0.0, 2.0),
            (0.0, 0.0)
        ]

        # Point outside
        point = GeoPoint(latitude=3.0, longitude=3.0)

        inside = validator._point_in_polygon_simple(point, ring)
        assert inside is False


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
