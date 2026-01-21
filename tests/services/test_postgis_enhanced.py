# -*- coding: utf-8 -*-
"""
Tests for Enhanced PostGIS Spatial Queries.

Tests the new spatial query methods added in STEP 16:
- Building statistics in polygon
- Batch polygon containment checks
- Polygon intersection areas
- Buildings intersecting lines
- Nearest neighbor analysis

NOTE: These tests require actual PostGIS connection.
They will be skipped if PostGIS is not available.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from services.postgis_service import PostGISService, PostGISConfig


@pytest.fixture
def mock_postgis_service():
    """Create PostGIS service with mocked connection."""
    service = PostGISService()

    # Mock connection pool
    service._pool = MagicMock()

    # Mock connection context manager
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)

    service._pool.getconn.return_value = mock_conn

    return service, mock_conn, mock_cursor


class TestBuildingStatsInPolygon:
    """Test get_buildings_stats_in_polygon method."""

    def test_stats_with_buildings(self, mock_postgis_service):
        """Test getting stats for polygon with buildings."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock query result
        mock_cursor.fetchone.return_value = (
            15,  # total_count
            {'residential': 10, 'commercial': 5},  # by_type
            {'good': 8, 'damaged': 7},  # by_status
            125.5  # avg_distance_from_center
        )

        polygon_wkt = "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
        result = service.get_buildings_stats_in_polygon(polygon_wkt)

        assert result['total_count'] == 15
        assert result['by_type'] == {'residential': 10, 'commercial': 5}
        assert result['by_status'] == {'good': 8, 'damaged': 7}
        assert result['avg_distance_from_center'] == 125.5

    def test_stats_empty_polygon(self, mock_postgis_service):
        """Test stats for polygon with no buildings."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock empty result
        mock_cursor.fetchone.return_value = (0, None, None, None)

        polygon_wkt = "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
        result = service.get_buildings_stats_in_polygon(polygon_wkt)

        assert result['total_count'] == 0
        assert result['by_type'] == {}
        assert result['by_status'] == {}
        assert result['avg_distance_from_center'] == 0

    def test_stats_no_result(self, mock_postgis_service):
        """Test handling when query returns None."""
        service, mock_conn, mock_cursor = mock_postgis_service

        mock_cursor.fetchone.return_value = None

        polygon_wkt = "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
        result = service.get_buildings_stats_in_polygon(polygon_wkt)

        assert result['total_count'] == 0
        assert isinstance(result['by_type'], dict)
        assert isinstance(result['by_status'], dict)


class TestBatchPolygonChecks:
    """Test batch_check_buildings_in_polygons method."""

    def test_batch_check_multiple_polygons(self, mock_postgis_service):
        """Test checking multiple buildings against multiple polygons."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock query results - polygon 0 has 2 buildings, polygon 1 has 1
        mock_cursor.fetchall.return_value = [
            (0, 'building-uuid-1'),
            (0, 'building-uuid-2'),
            (1, 'building-uuid-3')
        ]

        polygons = [
            "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))",
            "POLYGON((37.15 36.20, 37.16 36.20, 37.16 36.21, 37.15 36.21, 37.15 36.20))"
        ]

        result = service.batch_check_buildings_in_polygons(polygons)

        assert '0' in result
        assert '1' in result
        assert len(result['0']) == 2
        assert len(result['1']) == 1
        assert 'building-uuid-1' in result['0']
        assert 'building-uuid-2' in result['0']
        assert 'building-uuid-3' in result['1']

    def test_batch_check_with_building_filter(self, mock_postgis_service):
        """Test batch check with specific building UUIDs."""
        service, mock_conn, mock_cursor = mock_postgis_service

        mock_cursor.fetchall.return_value = [
            (0, 'building-uuid-1')
        ]

        polygons = [
            "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
        ]
        building_uuids = ['building-uuid-1', 'building-uuid-2']

        result = service.batch_check_buildings_in_polygons(polygons, building_uuids)

        assert '0' in result
        assert 'building-uuid-1' in result['0']

    def test_batch_check_error_handling(self, mock_postgis_service):
        """Test error handling in batch check."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Simulate database error
        mock_cursor.execute.side_effect = Exception("Database error")

        polygons = [
            "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
        ]

        result = service.batch_check_buildings_in_polygons(polygons)

        assert result == {}


class TestPolygonIntersectionAreas:
    """Test get_polygon_intersection_areas method."""

    def test_intersection_areas_overlapping(self, mock_postgis_service):
        """Test intersection calculation for overlapping polygons."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock result: two 100m² polygons with 25m² overlap
        mock_cursor.fetchone.return_value = (
            25.0,    # intersection_area
            175.0,   # union_area
            100.0,   # area1
            100.0    # area2
        )

        polygon1 = "POLYGON((37.130 36.200, 37.131 36.200, 37.131 36.201, 37.130 36.201, 37.130 36.200))"
        polygon2 = "POLYGON((37.1305 36.200, 37.1315 36.200, 37.1315 36.201, 37.1305 36.201, 37.1305 36.200))"

        result = service.get_polygon_intersection_areas(polygon1, polygon2)

        assert result['intersection_area'] == 25.0
        assert result['union_area'] == 175.0
        assert result['polygon1_area'] == 100.0
        assert result['polygon2_area'] == 100.0
        assert result['overlap_percentage'] == 25.0  # 25/100 * 100

    def test_intersection_areas_no_overlap(self, mock_postgis_service):
        """Test intersection for non-overlapping polygons."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock result: no overlap
        mock_cursor.fetchone.return_value = (
            0.0,     # intersection_area
            200.0,   # union_area
            100.0,   # area1
            100.0    # area2
        )

        polygon1 = "POLYGON((37.130 36.200, 37.131 36.200, 37.131 36.201, 37.130 36.201, 37.130 36.200))"
        polygon2 = "POLYGON((37.140 36.200, 37.141 36.200, 37.141 36.201, 37.140 36.201, 37.140 36.200))"

        result = service.get_polygon_intersection_areas(polygon1, polygon2)

        assert result['intersection_area'] == 0.0
        assert result['overlap_percentage'] == 0.0

    def test_intersection_zero_area_handling(self, mock_postgis_service):
        """Test handling of zero-area polygons."""
        service, mock_conn, mock_cursor = mock_postgis_service

        mock_cursor.fetchone.return_value = (0.0, 0.0, 0.0, 0.0)

        polygon1 = "POLYGON((37.130 36.200, 37.131 36.200, 37.131 36.201, 37.130 36.201, 37.130 36.200))"
        polygon2 = "POLYGON((37.130 36.200, 37.131 36.200, 37.131 36.201, 37.130 36.201, 37.130 36.200))"

        result = service.get_polygon_intersection_areas(polygon1, polygon2)

        # Should not raise division by zero error
        assert result['overlap_percentage'] == 0.0


class TestBuildingsIntersectingLine:
    """Test find_buildings_intersecting_line method."""

    def test_find_buildings_on_line(self, mock_postgis_service):
        """Test finding buildings that intersect a line."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock query results
        mock_cursor.fetchall.return_value = [
            (
                'building-uuid-1',
                'POINT(37.13 36.20)',
                '{"type":"Point","coordinates":[37.13,36.20]}',
                'BUILD-001',
                'HOOD-01',
                'residential',
                'good',
                5.0  # distance
            ),
            (
                'building-uuid-2',
                'POINT(37.14 36.20)',
                '{"type":"Point","coordinates":[37.14,36.20]}',
                'BUILD-002',
                'HOOD-01',
                'commercial',
                'damaged',
                10.0  # distance
            )
        ]

        line = "LINESTRING(37.13 36.19, 37.15 36.21)"
        results = service.find_buildings_intersecting_line(line)

        assert len(results) == 2
        assert results[0].feature_id == 'building-uuid-1'
        assert results[0].distance == 5.0
        assert results[1].feature_id == 'building-uuid-2'
        assert results[1].distance == 10.0

    def test_find_buildings_with_buffer(self, mock_postgis_service):
        """Test finding buildings near a line with buffer."""
        service, mock_conn, mock_cursor = mock_postgis_service

        mock_cursor.fetchall.return_value = []

        line = "LINESTRING(37.13 36.19, 37.15 36.21)"
        buffer_meters = 50.0

        results = service.find_buildings_intersecting_line(line, buffer_meters)

        assert len(results) == 0


class TestNearestNeighborAnalysis:
    """Test get_nearest_neighbor_analysis method."""

    def test_nearest_neighbor_analysis(self, mock_postgis_service):
        """Test nearest neighbor analysis calculation."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock result
        mock_cursor.fetchone.return_value = (
            50.0,    # avg_distance
            45.0,    # median_distance
            10.0,    # min_distance
            150.0,   # max_distance
            100      # sample_count
        )

        result = service.get_nearest_neighbor_analysis(sample_size=100)

        assert result['avg_nearest_distance'] == 50.0
        assert result['median_nearest_distance'] == 45.0
        assert result['min_distance'] == 10.0
        assert result['max_distance'] == 150.0
        assert result['sample_size'] == 100

        # Clustering index = median / avg
        expected_clustering = 45.0 / 50.0
        assert abs(result['clustering_index'] - expected_clustering) < 0.01

    def test_nearest_neighbor_no_data(self, mock_postgis_service):
        """Test nearest neighbor analysis with no data."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Mock empty result
        mock_cursor.fetchone.return_value = (None, None, None, None, 0)

        result = service.get_nearest_neighbor_analysis()

        assert result['avg_nearest_distance'] == 0
        assert result['median_nearest_distance'] == 0
        assert result['sample_size'] == 0
        assert result['clustering_index'] == 1.0  # Default

    def test_clustering_index_calculation(self, mock_postgis_service):
        """Test clustering index interpretation."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Clustered pattern: median < avg (clustering_index < 1)
        mock_cursor.fetchone.return_value = (100.0, 70.0, 10.0, 200.0, 50)
        result = service.get_nearest_neighbor_analysis()
        assert result['clustering_index'] < 1.0  # Indicates clustering

        # Dispersed pattern: median > avg (clustering_index > 1)
        mock_cursor.fetchone.return_value = (100.0, 130.0, 10.0, 200.0, 50)
        result = service.get_nearest_neighbor_analysis()
        assert result['clustering_index'] > 1.0  # Indicates dispersion


class TestConnectionManagement:
    """Test connection lifecycle in enhanced methods."""

    def test_connection_returned_on_success(self, mock_postgis_service):
        """Test connection is properly returned after successful query."""
        service, mock_conn, mock_cursor = mock_postgis_service

        mock_cursor.fetchone.return_value = (0, None, None, None)

        polygon_wkt = "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"
        service.get_buildings_stats_in_polygon(polygon_wkt)

        # Verify connection was returned to pool
        service._pool.putconn.assert_called()

    def test_connection_returned_on_error(self, mock_postgis_service):
        """Test connection is returned even when query fails."""
        service, mock_conn, mock_cursor = mock_postgis_service

        # Simulate query error
        mock_cursor.execute.side_effect = Exception("Query error")

        polygon_wkt = "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"

        with pytest.raises(Exception):
            service.get_polygon_intersection_areas(polygon_wkt, polygon_wkt)

        # Connection should still be returned
        service._pool.putconn.assert_called()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
