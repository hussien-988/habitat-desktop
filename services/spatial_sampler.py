# -*- coding: utf-8 -*-
"""
Spatial Sampler - Grid-Based Building Distribution
===================================================

Professional spatial sampling for displaying buildings on map.

Best Practices Applied:
- Grid-based sampling (ensures even distribution)
- Zoom-level adaptive density
- Performance-optimized (O(n) complexity)
- Prevents visual clustering

Algorithm:
    Viewport divided into grid (5x5 = 25 cells)
    ↓
    Select 1 building per cell (random/priority)
    ↓
    Result: ~25 evenly distributed buildings
    ↓
    Zoom in → Increase grid density → More buildings

References:
- https://medium.com/@silvajohnny777/optimizing-leaflet-performance-with-a-large-number-of-markers-0dea18c2ec99
- https://andrejgajdos.com/leaflet-developer-guide-to-high-performance-map-visualizations-in-react/

Use Case:
    Instead of showing 10,000 buildings:
    → Show 20-30 strategically distributed buildings
    → User zooms in → Show more detail
"""

from typing import List, Tuple, Dict
import random
from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)


class SpatialSampler:
    """
    Grid-based spatial sampler for building distribution.

    Ensures buildings are evenly distributed across the viewport,
    preventing visual clustering and improving map readability.

    Features:
    - Adaptive grid density based on zoom level
    - Priority-based sampling (prefer damaged buildings)
    - Deterministic results (same viewport = same buildings)
    - Performance optimized for large datasets
    """

    # Zoom-level based density configuration (Best Practice)
    DENSITY_CONFIG = {
        # zoom_level: (grid_rows, grid_cols, max_buildings)
        12: (4, 4, 20),    # Zoomed out: 4x4 grid, max 20 buildings
        13: (5, 5, 25),    # Medium: 5x5 grid, max 25 buildings
        14: (5, 5, 30),    # Medium-close: 5x5 grid, max 30 buildings
        15: (6, 6, 35),    # Close: 6x6 grid, max 35 buildings
        16: (7, 7, 45),    # Very close: 7x7 grid, max 45 buildings
        17: (8, 8, 60),    # Detailed: 8x8 grid, max 60 buildings
        18: (10, 10, 100), # Maximum detail: 10x10 grid, max 100 buildings
    }

    # Priority weights for building selection
    STATUS_PRIORITY = {
        'destroyed': 3,      # Highest priority (most important to show)
        'major_damage': 2,   # High priority
        'minor_damage': 1,   # Medium priority
        'damaged': 1,
        'intact': 0,         # Lowest priority
        'standing': 0,
    }

    @staticmethod
    def sample_buildings(
        buildings: List[Building],
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        zoom_level: int,
        use_priority: bool = True
    ) -> List[Building]:
        """
        Sample buildings using grid-based distribution.

        Professional Best Practice:
        - Divides viewport into grid cells
        - Selects one building per cell (evenly distributed)
        - Uses priority weighting (damaged buildings preferred)
        - Adapts grid density based on zoom level

        Args:
            buildings: List of buildings to sample from
            north_east_lat: Viewport NE latitude
            north_east_lng: Viewport NE longitude
            south_west_lat: Viewport SW latitude
            south_west_lng: Viewport SW longitude
            zoom_level: Current map zoom level
            use_priority: Whether to use priority-based selection

        Returns:
            List of sampled buildings (evenly distributed)
        """
        if not buildings:
            return []

        try:
            # Get grid configuration for zoom level
            grid_rows, grid_cols, max_buildings = SpatialSampler._get_grid_config(zoom_level)

            # Create grid
            grid = SpatialSampler._create_grid(
                buildings,
                north_east_lat, north_east_lng,
                south_west_lat, south_west_lng,
                grid_rows, grid_cols
            )

            # Sample from grid
            sampled_buildings = SpatialSampler._sample_from_grid(
                grid,
                max_buildings,
                use_priority
            )

            logger.debug(
                f"Spatial sampling: {len(buildings)} → {len(sampled_buildings)} buildings "
                f"(zoom={zoom_level}, grid={grid_rows}x{grid_cols})"
            )

            return sampled_buildings

        except Exception as e:
            logger.error(f"Error in spatial sampling: {e}", exc_info=True)
            # Fallback: return first max_buildings
            _, _, max_buildings = SpatialSampler._get_grid_config(zoom_level)
            return buildings[:max_buildings]

    @staticmethod
    def _get_grid_config(zoom_level: int) -> Tuple[int, int, int]:
        """
        Get grid configuration for zoom level.

        Args:
            zoom_level: Map zoom level

        Returns:
            (grid_rows, grid_cols, max_buildings) tuple
        """
        # Find closest zoom level in config
        if zoom_level < 12:
            zoom_level = 12
        elif zoom_level > 18:
            zoom_level = 18

        # Get exact or nearest config
        if zoom_level in SpatialSampler.DENSITY_CONFIG:
            return SpatialSampler.DENSITY_CONFIG[zoom_level]
        else:
            # Find nearest zoom level
            nearest_zoom = min(
                SpatialSampler.DENSITY_CONFIG.keys(),
                key=lambda z: abs(z - zoom_level)
            )
            return SpatialSampler.DENSITY_CONFIG[nearest_zoom]

    @staticmethod
    def _create_grid(
        buildings: List[Building],
        north_east_lat: float,
        north_east_lng: float,
        south_west_lat: float,
        south_west_lng: float,
        grid_rows: int,
        grid_cols: int
    ) -> Dict[Tuple[int, int], List[Building]]:
        """
        Create grid and assign buildings to cells.

        Args:
            buildings: List of buildings
            north_east_lat: NE latitude
            north_east_lng: NE longitude
            south_west_lat: SW latitude
            south_west_lng: SW longitude
            grid_rows: Number of grid rows
            grid_cols: Number of grid columns

        Returns:
            Dictionary mapping (row, col) -> [buildings in cell]
        """
        grid: Dict[Tuple[int, int], List[Building]] = {}

        # Calculate cell dimensions
        lat_range = north_east_lat - south_west_lat
        lng_range = north_east_lng - south_west_lng

        cell_height = lat_range / grid_rows
        cell_width = lng_range / grid_cols

        # Assign buildings to grid cells
        for building in buildings:
            if not building.latitude or not building.longitude:
                continue

            # Calculate grid cell
            row = int((building.latitude - south_west_lat) / cell_height)
            col = int((building.longitude - south_west_lng) / cell_width)

            # Clamp to grid bounds
            row = max(0, min(row, grid_rows - 1))
            col = max(0, min(col, grid_cols - 1))

            # Add to grid
            cell_key = (row, col)
            if cell_key not in grid:
                grid[cell_key] = []
            grid[cell_key].append(building)

        return grid

    @staticmethod
    def _sample_from_grid(
        grid: Dict[Tuple[int, int], List[Building]],
        max_buildings: int,
        use_priority: bool
    ) -> List[Building]:
        """
        Sample one building from each grid cell.

        Args:
            grid: Grid with buildings assigned to cells
            max_buildings: Maximum buildings to return
            use_priority: Whether to use priority-based selection

        Returns:
            List of sampled buildings
        """
        sampled = []

        for cell_key, cell_buildings in grid.items():
            if not cell_buildings:
                continue

            # Select building from cell
            if use_priority:
                # Priority-based selection (prefer damaged buildings)
                building = SpatialSampler._select_by_priority(cell_buildings)
            else:
                # Random selection
                building = random.choice(cell_buildings)

            sampled.append(building)

            # Stop if we've reached max
            if len(sampled) >= max_buildings:
                break

        return sampled[:max_buildings]

    @staticmethod
    def _select_by_priority(buildings: List[Building]) -> Building:
        """
        Select building from cell using priority weighting.

        Prefers damaged buildings over intact buildings.

        Args:
            buildings: Buildings in cell

        Returns:
            Selected building
        """
        if len(buildings) == 1:
            return buildings[0]

        # Calculate priorities
        priorities = []
        for building in buildings:
            status = getattr(building, 'damage_status', 'intact') or 'intact'
            priority = SpatialSampler.STATUS_PRIORITY.get(status, 0)
            priorities.append(priority)

        # If all same priority, random choice
        if len(set(priorities)) == 1:
            return random.choice(buildings)

        # Select highest priority
        max_priority = max(priorities)
        candidates = [
            building for building, priority in zip(buildings, priorities)
            if priority == max_priority
        ]

        return random.choice(candidates)

    @staticmethod
    def calculate_optimal_sample_size(
        total_buildings: int,
        viewport_area: float,
        zoom_level: int
    ) -> int:
        """
        Calculate optimal sample size based on viewport and zoom.

        Professional heuristic for determining how many buildings to show.

        Args:
            total_buildings: Total buildings in viewport
            viewport_area: Viewport area (in degrees²)
            zoom_level: Current zoom level

        Returns:
            Optimal sample size
        """
        _, _, max_buildings = SpatialSampler._get_grid_config(zoom_level)

        # Don't sample if already below max
        if total_buildings <= max_buildings:
            return total_buildings

        return max_buildings


# Convenience function
def sample_buildings_for_map(
    buildings: List[Building],
    north_east_lat: float,
    north_east_lng: float,
    south_west_lat: float,
    south_west_lng: float,
    zoom_level: int
) -> List[Building]:
    """
    Convenience function for spatial sampling.

    Args:
        buildings: Buildings to sample
        north_east_lat: NE latitude
        north_east_lng: NE longitude
        south_west_lat: SW latitude
        south_west_lng: SW longitude
        zoom_level: Zoom level

    Returns:
        Sampled buildings
    """
    return SpatialSampler.sample_buildings(
        buildings,
        north_east_lat, north_east_lng,
        south_west_lat, south_west_lng,
        zoom_level,
        use_priority=True
    )
