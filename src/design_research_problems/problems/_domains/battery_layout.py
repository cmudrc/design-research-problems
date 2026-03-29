"""Shared physical layout helpers for battery-domain backends."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import floor, sqrt
from typing import Protocol

from design_research_problems.problems._domains.battery_defaults import BATTERY_BACKEND_DEFAULTS


@dataclass(frozen=True)
class BatteryCellSpec:
    """Physical constants for one cylindrical cell."""

    nominal_voltage_v: float
    """Nominal per-cell voltage in volts."""
    min_voltage_v: float
    """Minimum allowable per-cell voltage in volts."""
    max_voltage_v: float
    """Maximum allowable per-cell voltage in volts."""
    nominal_capacity_ah: float
    """Nominal per-cell capacity in amp-hours."""
    weight_kg: float
    """Single-cell mass in kilograms."""
    diameter_mm: float
    """Cell diameter in millimeters."""
    length_mm: float
    """Cell length in millimeters."""
    internal_resistance_ohm: float
    """Approximate internal resistance in ohms."""
    max_discharge_rate_c: float
    """Maximum discharge C-rate."""
    max_charge_rate_c: float
    """Maximum charge C-rate."""
    unit_cost_usd: float
    """Nominal unit cost in US dollars."""


@dataclass(frozen=True)
class BatteryRequirements:
    """Fixed benchmark requirements for a battery-pack problem."""

    target_voltage_v: float
    """Required pack voltage in volts."""
    minimum_capacity_ah: float
    """Minimum required pack capacity in amp-hours."""
    minimum_current_a: float
    """Minimum required continuous current in amps."""
    max_width_mm: float
    """Maximum allowed pack width in millimeters."""
    max_depth_mm: float
    """Maximum allowed pack depth in millimeters."""
    max_height_mm: float
    """Maximum allowed pack height in millimeters."""
    voltage_tolerance_v: float = 0.1
    """Allowed absolute voltage mismatch in volts."""


@dataclass(frozen=True)
class BatteryCellPlacement:
    """A single physical cell with logical topology indices and a grid coordinate."""

    cell_id: int
    """Stable cell identifier within one state."""
    stage_index: int
    """Zero-based series-stage index."""
    branch_index: int
    """Zero-based parallel-branch index."""
    x: int
    """Grid x-coordinate."""
    y: int
    """Grid y-coordinate."""
    z: int
    """Grid z-coordinate."""


@dataclass(frozen=True)
class BatteryLayoutSummary:
    """Deterministic geometry and layout metrics."""

    cell_count: int
    """Total number of cells in the pack."""
    num_cells_width: int
    """Span of occupied x indices plus one."""
    num_cells_depth: int
    """Span of occupied y indices plus one."""
    num_cells_height: int
    """Span of occupied z indices plus one."""
    design_width: float
    """Computed pack width in millimeters."""
    design_depth: float
    """Computed pack depth in millimeters."""
    design_height: float
    """Computed pack height in millimeters."""
    design_cost: float
    """Estimated pack cost in US dollars."""
    surface_area: float
    """Bounding-box surface area in square millimeters."""
    design_volume: float
    """Bounding-box volume in cubic millimeters."""
    moment_of_inertia_xx: float
    """Pack moment of inertia about the x-axis."""
    moment_of_inertia_yy: float
    """Pack moment of inertia about the y-axis."""
    moment_of_inertia_zz: float
    """Pack moment of inertia about the z-axis."""


class BatteryCoordinateLike(Protocol):
    """Coordinate-only protocol used by layout helpers."""

    @property
    def x(self) -> int:
        """Return the grid x-coordinate.

        Returns:
            Computed result for this callable.
        """
        ...

    @property
    def y(self) -> int:
        """Return the grid y-coordinate.

        Returns:
            Computed result for this callable.
        """
        ...

    @property
    def z(self) -> int:
        """Return the grid z-coordinate.

        Returns:
            Computed result for this callable.
        """
        ...


class BatteryStateWithCells(Protocol):
    """Minimal state interface used by frontier helpers."""

    @property
    def cells(self) -> tuple[BatteryCoordinateLike, ...]:
        """Return all battery cell placements.

        Returns:
            Computed result for this callable.
        """
        ...


CELL_SPEC_18650 = BatteryCellSpec(
    nominal_voltage_v=3.7,
    min_voltage_v=2.5,
    max_voltage_v=4.2,
    nominal_capacity_ah=2.5,
    weight_kg=0.045,
    diameter_mm=18.0,
    length_mm=65.0,
    internal_resistance_ohm=0.05,
    max_discharge_rate_c=10.0,
    max_charge_rate_c=2.0,
    unit_cost_usd=10.0,
)

MIN_SPACING_MM = 2.0
SAFETY_MARGIN_MM = 5.0
CELL_RADIUS_MM = CELL_SPEC_18650.diameter_mm / 2.0
CELL_SPACING_H_MM = CELL_SPEC_18650.diameter_mm + MIN_SPACING_MM
CELL_SPACING_V_MM = CELL_SPEC_18650.length_mm + MIN_SPACING_MM
HEX_X_SPACING_MM = CELL_SPACING_H_MM
HEX_Y_SPACING_MM = CELL_SPACING_H_MM * (sqrt(3.0) / 2.0)
HEX_OFFSET_X_MM = CELL_SPACING_H_MM / 2.0
DEFAULT_INTERCONNECT_RESISTANCE_OHM = BATTERY_BACKEND_DEFAULTS.electrical.ideal_series_threshold_ohm


def coordinate_key(cell: BatteryCoordinateLike) -> tuple[int, int, int]:
    """Return the physical coordinate key for one cell.

    Args:
        cell: Value for ``cell``.

    Returns:
        Computed result for this callable.
    """
    return (cell.x, cell.y, cell.z)


def sort_cell_placements(
    cells: tuple[BatteryCellPlacement, ...] | list[BatteryCellPlacement],
) -> tuple[BatteryCellPlacement, ...]:
    """Return cells sorted by logical slot and then coordinate.

    Args:
        cells: Value for ``cells``.

    Returns:
        Computed result for this callable.
    """
    return tuple(
        sorted(
            cells,
            key=lambda cell: (cell.stage_index, cell.branch_index, cell.z, cell.y, cell.x, cell.cell_id),
        )
    )


def next_cell_id(cells: Iterable[BatteryCellPlacement]) -> int:
    """Return the next stable cell identifier.

    Args:
        cells: Value for ``cells``.

    Returns:
        Computed result for this callable.
    """
    next_id = 0
    for cell in cells:
        next_id = max(next_id, cell.cell_id + 1)
    return next_id


def occupied_coordinates(cells: Iterable[BatteryCoordinateLike]) -> set[tuple[int, int, int]]:
    """Return all occupied grid coordinates.

    Args:
        cells: Value for ``cells``.

    Returns:
        Computed result for this callable.
    """
    return {coordinate_key(cell) for cell in cells}


def grid_index_limits(requirements: BatteryRequirements) -> tuple[int, int, int]:
    """Return the maximum in-bounds grid indices allowed by the benchmark envelope.

    Args:
        requirements: Value for ``requirements``.

    Returns:
        Computed result for this callable.
    """
    max_x = floor(
        (requirements.max_width_mm - CELL_SPEC_18650.diameter_mm - (2.0 * SAFETY_MARGIN_MM)) / HEX_X_SPACING_MM
    )
    max_y = floor(
        (requirements.max_depth_mm - CELL_SPEC_18650.diameter_mm - (2.0 * SAFETY_MARGIN_MM) - HEX_OFFSET_X_MM)
        / HEX_Y_SPACING_MM
    )
    max_z = floor(
        (requirements.max_height_mm - CELL_SPEC_18650.length_mm - (2.0 * SAFETY_MARGIN_MM)) / CELL_SPACING_V_MM
    )
    return (max(0, max_x), max(0, max_y), max(0, max_z))


def coordinate_is_in_bounds(
    coordinate: tuple[int, int, int],
    requirements: BatteryRequirements,
) -> bool:
    """Return whether one coordinate lies inside the legal grid envelope.

    Args:
        coordinate: Value for ``coordinate``.
        requirements: Value for ``requirements``.

    Returns:
        Computed result for this callable.
    """
    x_value, y_value, z_value = coordinate
    if x_value < 0 or y_value < 0 or z_value < 0:
        return False
    max_x, max_y, max_z = grid_index_limits(requirements)
    return x_value <= max_x and y_value <= max_y and z_value <= max_z


def coordinate_to_physical_mm(coordinate: tuple[int, int, int]) -> tuple[float, float, float]:
    """Convert one grid coordinate into the physical center position in millimeters.

    Args:
        coordinate: Value for ``coordinate``.

    Returns:
        Computed result for this callable.
    """
    x_value, y_value, z_value = coordinate
    x_offset = HEX_OFFSET_X_MM if (y_value % 2 == 1) else 0.0
    physical_x = (x_value * HEX_X_SPACING_MM) + x_offset + SAFETY_MARGIN_MM + CELL_RADIUS_MM
    physical_y = (y_value * HEX_Y_SPACING_MM) + SAFETY_MARGIN_MM + CELL_RADIUS_MM
    physical_z = (z_value * CELL_SPACING_V_MM) + SAFETY_MARGIN_MM + (CELL_SPEC_18650.length_mm / 2.0)
    return (physical_x, physical_y, physical_z)


def candidate_frontier_coordinates_from_cells(
    cells: Iterable[BatteryCoordinateLike],
    requirements: BatteryRequirements,
) -> tuple[tuple[int, int, int], ...]:
    """Return a finite deterministic set of free coordinates near the occupied region.

    Args:
        cells: Value for ``cells``.
        requirements: Value for ``requirements``.

    Returns:
        Computed result for this callable.
    """
    cells_tuple = tuple(cells)
    occupied = occupied_coordinates(cells_tuple)
    max_grid_x, max_grid_y, max_grid_z = grid_index_limits(requirements)
    max_x = max((cell.x for cell in cells_tuple), default=0)
    max_y = max((cell.y for cell in cells_tuple), default=0)
    max_z = max((cell.z for cell in cells_tuple), default=0)
    frontier_x = min(max_grid_x, max_x + 1)
    frontier_y = min(max_grid_y, max_y + 1)
    frontier_z = min(max_grid_z, max_z + 1)
    candidates: list[tuple[int, int, int]] = []
    for z_value in range(frontier_z + 1):
        for y_value in range(frontier_y + 1):
            for x_value in range(frontier_x + 1):
                coordinate = (x_value, y_value, z_value)
                if coordinate in occupied:
                    continue
                candidates.append(coordinate)
    return tuple(candidates)


def candidate_frontier_coordinates(
    state: BatteryStateWithCells,
    requirements: BatteryRequirements,
) -> tuple[tuple[int, int, int], ...]:
    """Return frontier coordinates for any battery state with cells.

    Args:
        state: Value for ``state``.
        requirements: Value for ``requirements``.

    Returns:
        Computed result for this callable.
    """
    return candidate_frontier_coordinates_from_cells(state.cells, requirements)


def compute_layout_summary(cells: Iterable[BatteryCoordinateLike]) -> BatteryLayoutSummary:
    """Compute deterministic layout, cost, and coarse inertial metrics.

    Args:
        cells: Value for ``cells``.

    Returns:
        Computed result for this callable.
    """
    cells_tuple = tuple(cells)
    if not cells_tuple:
        return BatteryLayoutSummary(
            cell_count=0,
            num_cells_width=0,
            num_cells_depth=0,
            num_cells_height=0,
            design_width=0.0,
            design_depth=0.0,
            design_height=0.0,
            design_cost=0.0,
            surface_area=0.0,
            design_volume=0.0,
            moment_of_inertia_xx=0.0,
            moment_of_inertia_yy=0.0,
            moment_of_inertia_zz=0.0,
        )

    max_x = max(cell.x for cell in cells_tuple)
    max_y = max(cell.y for cell in cells_tuple)
    max_z = max(cell.z for cell in cells_tuple)
    num_cells_width = max_x + 1
    num_cells_depth = max_y + 1
    num_cells_height = max_z + 1
    design_width = ((num_cells_width - 1) * HEX_X_SPACING_MM) + CELL_SPEC_18650.diameter_mm + (2.0 * SAFETY_MARGIN_MM)
    design_depth = (
        ((num_cells_depth - 1) * HEX_Y_SPACING_MM)
        + CELL_SPEC_18650.diameter_mm
        + (2.0 * SAFETY_MARGIN_MM)
        + HEX_OFFSET_X_MM
    )
    design_height = ((num_cells_height - 1) * CELL_SPACING_V_MM) + CELL_SPEC_18650.length_mm + (2.0 * SAFETY_MARGIN_MM)

    cell_count = len(cells_tuple)
    design_cost = float(cell_count) * CELL_SPEC_18650.unit_cost_usd
    surface_area = 2.0 * (
        (design_width * design_depth) + (design_width * design_height) + (design_depth * design_height)
    )
    design_volume = design_width * design_depth * design_height

    cylinder_mass = CELL_SPEC_18650.weight_kg
    cylinder_radius = CELL_SPEC_18650.diameter_mm / 2.0
    cylinder_length = CELL_SPEC_18650.length_mm
    i_xx_cell = (0.25 * cylinder_mass * (cylinder_radius**2)) + ((1.0 / 12.0) * cylinder_mass * (cylinder_length**2))
    i_yy_cell = i_xx_cell
    i_zz_cell = 0.5 * cylinder_mass * (cylinder_radius**2)

    positions = [coordinate_to_physical_mm(coordinate_key(cell)) for cell in cells_tuple]
    centroid_x = sum(position[0] for position in positions) / float(cell_count)
    centroid_y = sum(position[1] for position in positions) / float(cell_count)
    centroid_z = sum(position[2] for position in positions) / float(cell_count)

    moment_of_inertia_xx = float(cell_count) * i_xx_cell
    moment_of_inertia_yy = float(cell_count) * i_yy_cell
    moment_of_inertia_zz = float(cell_count) * i_zz_cell
    for physical_x, physical_y, physical_z in positions:
        delta_x = physical_x - centroid_x
        delta_y = physical_y - centroid_y
        delta_z = physical_z - centroid_z
        moment_of_inertia_xx += cylinder_mass * ((delta_y**2) + (delta_z**2))
        moment_of_inertia_yy += cylinder_mass * ((delta_x**2) + (delta_z**2))
        moment_of_inertia_zz += cylinder_mass * ((delta_x**2) + (delta_y**2))

    return BatteryLayoutSummary(
        cell_count=cell_count,
        num_cells_width=num_cells_width,
        num_cells_depth=num_cells_depth,
        num_cells_height=num_cells_height,
        design_width=design_width,
        design_depth=design_depth,
        design_height=design_height,
        design_cost=design_cost,
        surface_area=surface_area,
        design_volume=design_volume,
        moment_of_inertia_xx=moment_of_inertia_xx,
        moment_of_inertia_yy=moment_of_inertia_yy,
        moment_of_inertia_zz=moment_of_inertia_zz,
    )


__all__ = [
    "CELL_RADIUS_MM",
    "CELL_SPACING_H_MM",
    "CELL_SPACING_V_MM",
    "CELL_SPEC_18650",
    "DEFAULT_INTERCONNECT_RESISTANCE_OHM",
    "HEX_OFFSET_X_MM",
    "HEX_X_SPACING_MM",
    "HEX_Y_SPACING_MM",
    "MIN_SPACING_MM",
    "SAFETY_MARGIN_MM",
    "BatteryCellPlacement",
    "BatteryCellSpec",
    "BatteryCoordinateLike",
    "BatteryLayoutSummary",
    "BatteryRequirements",
    "BatteryStateWithCells",
    "candidate_frontier_coordinates",
    "candidate_frontier_coordinates_from_cells",
    "compute_layout_summary",
    "coordinate_is_in_bounds",
    "coordinate_key",
    "coordinate_to_physical_mm",
    "grid_index_limits",
    "next_cell_id",
    "occupied_coordinates",
    "sort_cell_placements",
]
