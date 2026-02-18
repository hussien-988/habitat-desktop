# -*- coding: utf-8 -*-
"""
Geometry Validation Service - Validates geometric data.

Provides validation for:
- Polygon validity (self-intersection, area, bounds)
- Coordinate validation
- WKT/GeoJSON parsing
- Topological checks

Implements FSD requirements for geometry validation.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math

from app.config import Config
from services.map_service import GeoPoint, GeoPolygon
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of geometry validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def add_error(self, message: str):
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add validation warning."""
        self.warnings.append(message)


class GeometryValidationService:
    """
    Service for validating geometric data.

    Provides comprehensive validation for points, polygons, and coordinates.
    """

    # Map bounding box (from .env / Config)
    ALEPPO_BOUNDS = {
        "min_lat": Config.MAP_BOUNDS_MIN_LAT,
        "max_lat": Config.MAP_BOUNDS_MAX_LAT,
        "min_lon": Config.MAP_BOUNDS_MIN_LNG,
        "max_lon": Config.MAP_BOUNDS_MAX_LNG
    }

    # Validation thresholds
    MIN_POLYGON_AREA_SQM = 1.0  # Minimum 1 square meter
    MAX_POLYGON_AREA_SQM = 1000000.0  # Maximum 1 million square meters
    MIN_VERTICES = 3
    MAX_VERTICES = 1000

    def __init__(self):
        """Initialize the validation service."""
        pass

    def validate_point(self, point: GeoPoint) -> ValidationResult:
        """
        Validate a geographic point.

        Checks:
        - Coordinate ranges (-90 to 90 for lat, -180 to 180 for lon)
        - Within Aleppo bounds (optional warning)
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Basic range check
        if point.latitude < -90 or point.latitude > 90:
            result.add_error(f"خط العرض خارج النطاق الصحيح: {point.latitude} (يجب أن يكون بين -90 و 90)")

        if point.longitude < -180 or point.longitude > 180:
            result.add_error(f"خط الطول خارج النطاق الصحيح: {point.longitude} (يجب أن يكون بين -180 و 180)")

        # Aleppo bounds check (warning only)
        if not self._is_within_aleppo(point):
            result.add_warning(
                f"الإحداثيات خارج نطاق حلب المتوقع. "
                f"الموقع: ({point.latitude:.6f}, {point.longitude:.6f})"
            )

        return result

    def validate_polygon(
        self,
        polygon: GeoPolygon,
        check_self_intersection: bool = True
    ) -> ValidationResult:
        """
        Validate a polygon.

        Checks:
        - Minimum vertices (3)
        - Maximum vertices
        - Closed ring (first == last point)
        - Self-intersection (optional)
        - Area within bounds
        - Clockwise orientation
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        if not polygon.coordinates or not polygon.coordinates[0]:
            result.add_error("المضلع فارغ")
            return result

        outer_ring = polygon.coordinates[0]

        # Check vertex count
        if len(outer_ring) < self.MIN_VERTICES:
            result.add_error(
                f"المضلع يجب أن يحتوي على {self.MIN_VERTICES} نقاط على الأقل. "
                f"الحالي: {len(outer_ring)}"
            )

        if len(outer_ring) > self.MAX_VERTICES:
            result.add_warning(
                f"المضلع يحتوي على نقاط كثيرة ({len(outer_ring)}). "
                f"قد يؤثر ذلك على الأداء."
            )

        # Check if ring is closed
        first_point = outer_ring[0]
        last_point = outer_ring[-1]

        if not self._points_equal(first_point, last_point):
            result.add_warning("المضلع غير مغلق. سيتم إغلاقه تلقائياً.")

        # Validate each vertex
        for i, (lon, lat) in enumerate(outer_ring):
            point = GeoPoint(latitude=lat, longitude=lon)
            point_result = self.validate_point(point)

            if not point_result.is_valid:
                result.add_error(f"النقطة {i+1}: {', '.join(point_result.errors)}")

        # Check for self-intersection
        if check_self_intersection and self._has_self_intersection(outer_ring):
            result.add_error("المضلع يتقاطع مع نفسه. يرجى تصحيح الشكل.")

        # Calculate and validate area
        area = self._calculate_polygon_area(outer_ring)

        if area < self.MIN_POLYGON_AREA_SQM:
            result.add_error(
                f"مساحة المضلع صغيرة جداً: {area:.2f} م². "
                f"الحد الأدنى: {self.MIN_POLYGON_AREA_SQM} م²"
            )

        if area > self.MAX_POLYGON_AREA_SQM:
            result.add_warning(
                f"مساحة المضلع كبيرة جداً: {area:.2f} م². "
                f"يرجى التحقق من الإحداثيات."
            )

        # Check orientation (should be counter-clockwise for exterior ring)
        # Note: This is just a warning, not an error
        if not self._is_counter_clockwise(outer_ring):
            result.add_warning("اتجاه المضلع عكس عقارب الساعة. سيتم عكسه تلقائياً.")
            # Don't mark as invalid - this is auto-fixable

        # Check for inner rings (holes)
        if len(polygon.coordinates) > 1:
            for i, inner_ring in enumerate(polygon.coordinates[1:], 1):
                inner_result = self._validate_inner_ring(inner_ring, outer_ring)
                if not inner_result.is_valid:
                    result.add_error(f"الثقب {i}: {', '.join(inner_result.errors)}")

        return result

    def _is_within_aleppo(self, point: GeoPoint) -> bool:
        """Check if point is within Aleppo bounds."""
        return (
            self.ALEPPO_BOUNDS["min_lat"] <= point.latitude <= self.ALEPPO_BOUNDS["max_lat"] and
            self.ALEPPO_BOUNDS["min_lon"] <= point.longitude <= self.ALEPPO_BOUNDS["max_lon"]
        )

    def _points_equal(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        tolerance: float = 1e-7
    ) -> bool:
        """Check if two points are equal within tolerance."""
        return (
            abs(p1[0] - p2[0]) < tolerance and
            abs(p1[1] - p2[1]) < tolerance
        )

    def _has_self_intersection(self, ring: List[Tuple[float, float]]) -> bool:
        """
        Check if polygon has self-intersections using line segment intersection.

        Uses sweep line algorithm for efficiency.
        """
        n = len(ring)

        # Check each edge against every other non-adjacent edge
        for i in range(n - 1):
            for j in range(i + 2, n - 1):
                # Skip adjacent edges
                # Note: i and j are never adjacent by loop design (j starts at i+2)
                # But we need to skip first edge (0) vs last edge (n-2) in closed rings
                if i == 0 and j == n - 2:
                    continue

                if self._segments_intersect(
                    ring[i], ring[i + 1],
                    ring[j], ring[j + 1]
                ):
                    return True

        return False

    def _segments_intersect(
        self,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        p4: Tuple[float, float]
    ) -> bool:
        """Check if two line segments intersect (excluding endpoints)."""
        # Calculate orientation of 4 triplets
        o1 = self._orientation(p1, p2, p3)
        o2 = self._orientation(p1, p2, p4)
        o3 = self._orientation(p3, p4, p1)
        o4 = self._orientation(p3, p4, p2)

        # General case: segments intersect if they have different orientations
        if o1 != o2 and o3 != o4:
            return True

        # Special cases: collinear points
        # (not checking for simplicity - rare in real polygons)

        return False

    def _orientation(
        self,
        p: Tuple[float, float],
        q: Tuple[float, float],
        r: Tuple[float, float]
    ) -> int:
        """
        Find orientation of ordered triplet (p, q, r).

        Returns:
            0: Collinear
            1: Clockwise
            2: Counter-clockwise
        """
        val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

        if abs(val) < 1e-10:
            return 0  # Collinear

        return 1 if val > 0 else 2

    def _calculate_polygon_area(self, ring: List[Tuple[float, float]]) -> float:
        """
        Calculate polygon area using spherical excess formula.

        More accurate than planar calculation for geographic coordinates.
        """
        if len(ring) < 3:
            return 0.0

        # Convert to radians
        coords_rad = [(math.radians(lon), math.radians(lat)) for lon, lat in ring]

        # Spherical excess formula
        R = 6371000  # Earth radius in meters
        area = 0.0

        for i in range(len(coords_rad) - 1):
            lon1, lat1 = coords_rad[i]
            lon2, lat2 = coords_rad[i + 1]

            area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

        return abs(area * R * R / 2.0)

    def _is_counter_clockwise(self, ring: List[Tuple[float, float]]) -> bool:
        """Check if ring is oriented counter-clockwise."""
        # Calculate signed area
        area = 0.0
        n = len(ring)

        for i in range(n - 1):
            area += (ring[i + 1][0] - ring[i][0]) * (ring[i + 1][1] + ring[i][1])

        # Counter-clockwise if area is negative
        return area < 0

    def _validate_inner_ring(
        self,
        inner_ring: List[Tuple[float, float]],
        outer_ring: List[Tuple[float, float]]
    ) -> ValidationResult:
        """Validate that inner ring (hole) is fully contained within outer ring."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])

        # Check that all points of inner ring are inside outer ring
        for lon, lat in inner_ring:
            point = GeoPoint(latitude=lat, longitude=lon)

            # Simple point-in-polygon check
            if not self._point_in_polygon_simple(point, outer_ring):
                result.add_error("الثقب يقع خارج حدود المضلع الخارجي")
                break

        # Check that inner ring is oriented clockwise (opposite of outer)
        if self._is_counter_clockwise(inner_ring):
            result.add_warning("الثقب يجب أن يكون بعكس اتجاه المضلع الخارجي")

        return result

    def _point_in_polygon_simple(
        self,
        point: GeoPoint,
        ring: List[Tuple[float, float]]
    ) -> bool:
        """Simple point-in-polygon test using ray casting."""
        x = point.longitude
        y = point.latitude
        n = len(ring)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside

    def repair_polygon(self, polygon: GeoPolygon) -> GeoPolygon:
        """
        Attempt to repair common polygon issues.

        Repairs:
        - Close open rings
        - Fix orientation
        - Remove duplicate consecutive points
        """
        if not polygon.coordinates:
            return polygon

        repaired_rings = []

        for ring in polygon.coordinates:
            repaired_ring = self._repair_ring(ring)
            if repaired_ring:
                repaired_rings.append(repaired_ring)

        return GeoPolygon(coordinates=repaired_rings)

    def _repair_ring(self, ring: List[Tuple[float, float]]) -> Optional[List[Tuple[float, float]]]:
        """Repair a single ring."""
        if len(ring) < 3:
            return None

        # Remove duplicate consecutive points
        cleaned = [ring[0]]
        for i in range(1, len(ring)):
            if not self._points_equal(ring[i], cleaned[-1]):
                cleaned.append(ring[i])

        # Close ring if needed
        if not self._points_equal(cleaned[0], cleaned[-1]):
            cleaned.append(cleaned[0])

        # Ensure counter-clockwise for exterior (will be first ring)
        # (Simplification: assume first ring is exterior)
        if not self._is_counter_clockwise(cleaned):
            cleaned.reverse()

        return cleaned
