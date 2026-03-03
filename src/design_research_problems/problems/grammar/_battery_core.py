"""Shared helpers for battery-pack grammar problems."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, sqrt
from typing import Any, Protocol

from design_research_problems._exceptions import MissingOptionalDependencyError


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
class BatteryMetricSummary:
    """Deterministic geometry and coarse electrical metrics."""

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
    design_voltage: float
    """Idealized pack voltage in volts."""
    design_capacity: float
    """Idealized pack capacity in amp-hours."""
    analytic_current_limit: float
    """Coarse analytic current limit in amps."""


class SeriesParallelStateLike(Protocol):
    """Minimal state interface used by the shared battery helpers."""

    @property
    def series_count(self) -> int:
        """Return the series-stage count.

        Returns:
            Number of series stages in the pack.
        """
        ...

    @property
    def parallel_count(self) -> int:
        """Return the parallel-branch count.

        Returns:
            Number of parallel branches in the pack.
        """
        ...

    @property
    def cells(self) -> tuple[BatteryCellPlacement, ...]:
        """Return all battery cell placements.

        Returns:
            Ordered battery cell placements for the pack state.
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


def _coordinate_key(cell: BatteryCellPlacement) -> tuple[int, int, int]:
    """Return the physical coordinate key for one cell.

    Args:
        cell: One battery cell placement.

    Returns:
        Three-dimensional integer grid coordinate.
    """
    return (cell.x, cell.y, cell.z)


def sort_cell_placements(
    cells: tuple[BatteryCellPlacement, ...] | list[BatteryCellPlacement],
) -> tuple[BatteryCellPlacement, ...]:
    """Return cells sorted by logical slot and then coordinate.

    Args:
        cells: Cell placements to sort.

    Returns:
        Deterministically ordered cell placements.
    """
    return tuple(
        sorted(
            cells,
            key=lambda cell: (cell.stage_index, cell.branch_index, cell.z, cell.y, cell.x, cell.cell_id),
        )
    )


def next_cell_id(cells: tuple[BatteryCellPlacement, ...]) -> int:
    """Return the next stable cell identifier.

    Args:
        cells: Existing cell placements.

    Returns:
        Next integer cell identifier.
    """
    if not cells:
        return 0
    return max(cell.cell_id for cell in cells) + 1


def occupied_coordinates(cells: tuple[BatteryCellPlacement, ...]) -> set[tuple[int, int, int]]:
    """Return all occupied grid coordinates.

    Args:
        cells: Existing cell placements.

    Returns:
        Unique occupied grid coordinates.
    """
    return {_coordinate_key(cell) for cell in cells}


def validate_rectangular_topology(state: SeriesParallelStateLike) -> str | None:
    """Return a failure reason when the state violates rectangular SxP topology.

    Args:
        state: Battery pack state to validate.

    Returns:
        Human-readable failure reason, or ``None`` when the topology is valid.
    """
    if state.series_count < 1:
        return "Series count must be at least 1."
    if state.parallel_count < 1:
        return "Parallel count must be at least 1."
    if len(state.cells) != state.series_count * state.parallel_count:
        return "Cell count does not match the required SxP rectangle."
    expected_slots = {
        (stage_index, branch_index)
        for stage_index in range(state.series_count)
        for branch_index in range(state.parallel_count)
    }
    actual_slots = {(cell.stage_index, cell.branch_index) for cell in state.cells}
    if actual_slots != expected_slots:
        return "Cells do not fill the complete SxP slot rectangle."
    return None


def grid_index_limits(requirements: BatteryRequirements) -> tuple[int, int, int]:
    """Return the maximum in-bounds grid indices allowed by the benchmark envelope.

    Args:
        requirements: Fixed benchmark requirements.

    Returns:
        Maximum legal ``(x, y, z)`` grid indices.
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
        coordinate: Candidate grid coordinate.
        requirements: Fixed benchmark requirements.

    Returns:
        ``True`` when the coordinate lies within the legal grid.
    """
    x_value, y_value, z_value = coordinate
    if x_value < 0 or y_value < 0 or z_value < 0:
        return False
    max_x, max_y, max_z = grid_index_limits(requirements)
    return x_value <= max_x and y_value <= max_y and z_value <= max_z


def coordinate_to_physical_mm(
    coordinate: tuple[int, int, int],
) -> tuple[float, float, float]:
    """Convert one grid coordinate into the physical center position in millimeters.

    Args:
        coordinate: Grid coordinate to convert.

    Returns:
        Physical center position in millimeters.
    """
    x_value, y_value, z_value = coordinate
    x_offset = HEX_OFFSET_X_MM if (y_value % 2 == 1) else 0.0
    physical_x = (x_value * HEX_X_SPACING_MM) + x_offset + SAFETY_MARGIN_MM + CELL_RADIUS_MM
    physical_y = (y_value * HEX_Y_SPACING_MM) + SAFETY_MARGIN_MM + CELL_RADIUS_MM
    physical_z = (z_value * CELL_SPACING_V_MM) + SAFETY_MARGIN_MM + (CELL_SPEC_18650.length_mm / 2.0)
    return (physical_x, physical_y, physical_z)


def candidate_frontier_coordinates(
    state: SeriesParallelStateLike,
    requirements: BatteryRequirements,
) -> tuple[tuple[int, int, int], ...]:
    """Return a finite deterministic set of free coordinates near the occupied region.

    Args:
        state: Battery pack state to expand from.
        requirements: Fixed benchmark requirements.

    Returns:
        Deterministic free coordinates near the current occupied frontier.
    """
    occupied = occupied_coordinates(state.cells)
    max_grid_x, max_grid_y, max_grid_z = grid_index_limits(requirements)
    max_x = max((cell.x for cell in state.cells), default=0)
    max_y = max((cell.y for cell in state.cells), default=0)
    max_z = max((cell.z for cell in state.cells), default=0)
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


def compute_metric_summary(
    state: SeriesParallelStateLike,
    requirements: BatteryRequirements,
) -> BatteryMetricSummary:
    """Compute deterministic layout, cost, and coarse electrical metrics.

    Args:
        state: Battery pack state to summarize.
        requirements: Fixed benchmark requirements.

    Returns:
        Deterministic metric summary for the pack state.
    """
    if not state.cells:
        return BatteryMetricSummary(
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
            design_voltage=0.0,
            design_capacity=0.0,
            analytic_current_limit=0.0,
        )

    max_x = max(cell.x for cell in state.cells)
    max_y = max(cell.y for cell in state.cells)
    max_z = max(cell.z for cell in state.cells)
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

    cell_count = len(state.cells)
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

    positions = [coordinate_to_physical_mm(_coordinate_key(cell)) for cell in state.cells]
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

    design_voltage = float(state.series_count) * CELL_SPEC_18650.nominal_voltage_v
    design_capacity = float(state.parallel_count) * CELL_SPEC_18650.nominal_capacity_ah
    max_thermal = surface_area * 1e-6 * 10000.0
    max_thermal_per_cell = max_thermal / float(cell_count)
    sqrt_arg = max_thermal_per_cell / CELL_SPEC_18650.internal_resistance_ohm
    max_current_per_cell = max(0.0, sqrt_arg) ** 0.5
    analytic_current_limit = max_current_per_cell * float(state.parallel_count)

    del requirements
    return BatteryMetricSummary(
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
        design_voltage=design_voltage,
        design_capacity=design_capacity,
        analytic_current_limit=analytic_current_limit,
    )


def import_pybamm() -> Any:
    """Import ``pybamm`` lazily for battery evaluation.

    Returns:
        Imported ``pybamm`` module.

    Raises:
        MissingOptionalDependencyError: If ``pybamm`` is not installed.
    """
    try:
        import pybamm
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "pybamm is required for battery grammar evaluation. Install it with: "
            "pip install design-research-problems[battery] or run: make install-pybamm"
        ) from exc
    return pybamm


def simulate_series_parallel_pack(
    pybamm_module: Any,
    requirements: BatteryRequirements,
    series_count: int,
    parallel_count: int,
) -> tuple[float, float, bool]:
    """Run a representative-cell PyBaMM simulation for an idealized SxP pack.

    Args:
        pybamm_module: Imported ``pybamm`` module object.
        requirements: Fixed benchmark requirements.
        series_count: Number of series stages.
        parallel_count: Number of parallel branches.

    Returns:
        Pack end voltage, delivered pack capacity, and feasibility flag.
    """
    cell_current = requirements.minimum_current_a / float(parallel_count)
    discharge_duration_seconds = (requirements.minimum_capacity_ah / requirements.minimum_current_a) * 3600.0
    model = pybamm_module.lithium_ion.SPM()
    parameter_values = model.default_parameter_values
    copy_method = getattr(parameter_values, "copy", None)
    if callable(copy_method):
        parameter_values = copy_method()
    parameter_values.update(
        {
            "Nominal cell capacity [A.h]": CELL_SPEC_18650.nominal_capacity_ah,
            "Current function [A]": cell_current,
        }
    )
    simulation = pybamm_module.Simulation(model, parameter_values=parameter_values)
    solution = simulation.solve([0.0, discharge_duration_seconds])
    elapsed_seconds = float(solution.t[-1])
    terminal_voltage = float(solution["Terminal voltage [V]"].entries[-1])
    delivered_capacity_ah = float(solution["Discharge capacity [A.h]"].entries[-1])
    pack_end_voltage = terminal_voltage * float(series_count)
    pack_delivered_capacity_ah = delivered_capacity_ah * float(parallel_count)
    reached_horizon = elapsed_seconds >= (discharge_duration_seconds * 0.999)
    meets_capacity = pack_delivered_capacity_ah + 1e-9 >= requirements.minimum_capacity_ah
    meets_voltage = pack_end_voltage + 1e-9 >= (float(series_count) * CELL_SPEC_18650.min_voltage_v)
    return (pack_end_voltage, pack_delivered_capacity_ah, reached_horizon and meets_capacity and meets_voltage)
